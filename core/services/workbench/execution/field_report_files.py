"""Original-byte import planning and full-cohort exports; AJ validates all facts."""

import uuid
from typing import Any, Dict, List, NamedTuple, Optional, Union

from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution_input import REPORT_FIELDS, REQUIRED_FIELDS
from core.services.workbench.facts.execution_projection import (
    COMPLETION_BASIS_TEXT,
    DATA_QUALITY_TEXT,
    EXECUTION_STATE_TEXT,
)
from data.repositories.workbench_field_query_repo import WorkbenchFieldQueryRepository

from .field_report_files_codec import encode_reports
from .field_report_files_identity import identity_values, matched_task, task_index


def _report_values(report):
    return {key: report.get(key, '' if key == 'remark' else None) for key in REPORT_FIELDS}


class ReportIndex(NamedTuple):
    by_no: Dict[str, Dict[str, Any]]
    # Old blank-number Excel imports, report numbers by saved content.
    by_excel_content: Dict[str, List[str]]


def report_index(reports):
    """Index one operation's saved reports once for all of its imported rows."""
    by_no, by_excel_content = {}, {}
    for report in reports:
        by_no[report['report_no']] = report
        if report.get('source') == 'excel' and report['report_no'].startswith('BG-X-'):
            by_excel_content.setdefault(content_text(_report_values(report)), []).append(report['report_no'])
    return ReportIndex(by_no, by_excel_content)


class FieldReportFileService:
    def __init__(self, conn, *, production):
        self.conn = conn
        self.queries = WorkbenchFieldQueryRepository(conn)
        self.production = production

    def _resource_index(self):
        result = {'codes': {}, 'labels': {}}
        for row in self.queries.active_resource_index_rows():
            for index, value in (('codes', row["entity_key"]), ('labels', row["label"])):
                if type(value) is str and value:
                    result[index].setdefault((row["kind"], value), set()).add(row["ref"])
        return result

    @staticmethod
    def _resource(index, kind, value):
        if not value:
            return None
        options = index['codes'].get((kind, value)) or index['labels'].get((kind, value), set())
        if len(options) != 1:
            raise WorkbenchCommandRejected('invalid_input', '填的设备或人员在系统里找不到，或者有重名分不清，请核对。', 422)
        return next(iter(options))

    def _items(self, tasks, rows, *, source_ref):
        by_ref = task_index(tasks)
        resources, items, positions, indexes = self._resource_index(), [], [], {}
        for row in rows:
            value = row['values']
            if row['errors']:
                row['result'] = 'rejected'
                continue
            if all(value.get(key) in (None, '') for key in ('actual_start', 'actual_end', 'completed_quantity', 'effective_processing_hours')):
                row['result'] = 'blank'
                continue
            try:
                task = matched_task(row, by_ref)
                task_ref = task['task_ref']
                if task_ref not in indexes:
                    indexes[task_ref] = report_index(task['execution']['reports'])
                items.append(self._row_item(row, task_ref, indexes[task_ref], resources, source_ref))
                positions.append(row['row'])
                row['result'] = 'pending'
            except WorkbenchCommandRejected as exc:
                row['result'] = 'rejected'
                row['errors'].append({'row': row['row'], 'message': str(exc), 'code': exc.code})
        return rows, items, positions

    def _row_item(self, row, task_ref, reports, resources, source_ref):
        value = row['values']
        payload = {key: value[key] for key in ('actual_start', 'actual_end', 'completed_quantity', 'effective_processing_hours', 'remark') if value[key] not in (None, '')}
        for kind in ('machine', 'operator'):
            selected = self._resource(resources, kind, value[kind + '_label'])
            if selected is not None:
                payload['actual_' + kind + '_ref'] = selected
        payload.update(source='excel')
        payload['report_no'] = value['report_no'] or self._source_report_number(row, reports, payload, source_ref)
        return {'action': 'create', 'ref': task_ref, 'payload': payload}

    @staticmethod
    def _source_report_number(row, reports, payload, source_ref):
        number = 'BG-X-' + source_ref + '-' + str(row['row'])
        if number in reports.by_no:
            return number
        # Older blank-number imports saved their generated number, not the original file.
        # Recover an existing number only from one complete matching report in this operation.
        matches = reports.by_excel_content.get(content_text(_report_values(payload)), [])
        if len(matches) > 1:
            raise WorkbenchCommandRejected('invalid_input', '已有多条内容相同的导入报工，请填写要核对的原报工编号。', 422)
        return matches[0] if matches else number

    def prepare_source(self, source, cohort):
        """Rebuild current business checks from the retained original file facts."""
        return self.prepare_preview(cohort, source.parsed(), source_ref=source.source_ref)

    def prepare_preview(self, cohort, decoded, *, source_ref):
        """Return the public preview and its private, already checked batch facts."""
        rows, items, positions = self._items(cohort['tasks'], decoded, source_ref=source_ref)
        check, preparation = None, None
        if not any(row['errors'] for row in rows):
            try:
                check, preparation = self._checked_rows(items, rows, positions)
            except WorkbenchCommandRejected as exc:
                self._preview_error(exc, rows, positions)
        rejected = sum(bool(row['errors']) for row in rows)
        summary = {'total': len(rows), 'blank': sum(row['result'] == 'blank' for row in rows), 'rejected': rejected,
                   'changed': check['summary']['changed'] if check else 0, 'unchanged': check['summary']['unchanged'] if check else 0}
        public = [{'row': row['row'], 'result': row['result'], 'errors': row['errors']} for row in rows]
        return {'rows': public, 'summary': summary, 'can_confirm': not rejected and bool(items), 'commit_policy': 'atomic',
                'actual_source_ref': source_ref, 'items': items,
                'snapshot': check['snapshot'] if check else None, 'scope': cohort['scope']}, preparation

    def _checked_rows(self, items, rows, positions):
        preparation = self.production.prepare_batch(items) if items else None
        check = preparation.public() if preparation else {'rows': [], 'summary': {'total': 0, 'changed': 0, 'unchanged': 0}, 'can_confirm': True, 'snapshot': {}}
        mapped = dict(zip(positions, check['rows']))
        for row in rows:
            if row['row'] in mapped:
                item = mapped[row['row']]
                row['result'] = item['result'] if item['result'] == 'unchanged' else item['action']
        return check, preparation

    @staticmethod
    def _preview_error(exc, rows, positions):
        number = exc.row_number
        original = positions[number - 1] if type(number) is int and 1 <= number <= len(positions) else positions[0] if positions else 1
        target = next((row for row in rows if row['row'] == original), None)
        if target is None:
            raise exc
        target['result'] = 'rejected'
        target['errors'].append({'row': original, 'message': str(exc), 'code': exc.code, 'conflicts': exc.conflicts})

    @staticmethod
    def rows(cohort, template, *, resource_codes):
        result = []
        for task in cohort['tasks']:
            p = task['execution']
            if template and p['execution_state'] == 'complete':
                continue
            reports = p['reports']
            if template:
                reports = [row for row in reports if any(row[key] is None for key in REQUIRED_FIELDS)] or [None]
            for report in reports:
                result.append(FieldReportFileService._export_row(report, task, template, resource_codes))
        return result

    @staticmethod
    def _export_row(report, task, template, codes):
        row = report or {}
        return {'report_no': row.get('report_no') or 'BG-T-' + uuid.uuid4().hex,
                               'batch_id': task['batch_id'], 'operation_label': task['operation_label'],
                               'completed_quantity': row.get('completed_quantity'), 'actual_start': row.get('actual_start'),
                               'actual_end': row.get('actual_end'), 'effective_processing_hours': row.get('effective_processing_hours'),
                               'machine_label': codes.get(row.get('actual_machine_ref') or (task['planned_machine_ref'] if template else None)),
                               'operator_label': codes.get(row.get('actual_operator_ref') or (task['planned_operator_ref'] if template else None)),
                'remark': row.get('remark', ''), **identity_values(task)}

    @staticmethod
    def download(cohort, template, *, resource_codes):
        rows = FieldReportFileService.rows(cohort, template, resource_codes=resource_codes)
        if template:
            return encode_reports(rows, summaries=(), metadata=()), len(rows)
        summaries: List[List[Optional[Union[str, int, float]]]] = [['批次号', '工序', '应做数量', '累计完成', '剩余数量', '工序状态', '完成依据', '资料完整性']]
        metadata: List[List[Optional[Union[str, int, float]]]] = [['报工编号', '录入时间', '报工来源', '补齐及更正次数']]
        for task in cohort['tasks']:
            p = task['execution']
            summaries.append([task['batch_id'], task['operation_label'], p['target_quantity'], p['known_completed_quantity'],
                              p['remaining_quantity'], EXECUTION_STATE_TEXT[p['execution_state']],
                              COMPLETION_BASIS_TEXT.get(p['completion_basis']),
                              DATA_QUALITY_TEXT[p['data_quality']]])
            for report in p['reports']:
                corrections = sum(item['action'] in ('supplement', 'correct') for item in report['correction_history'])
                metadata.append([report['report_no'], report['recorded_at'], 'Excel' if report['source'] == 'excel' else '手工', corrections])
        # 模板和导出都带说明表，两者的差别只剩要不要另外附汇总与录入信息。
        return encode_reports(rows, summaries=summaries, metadata=metadata), len(rows)
