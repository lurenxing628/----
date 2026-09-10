"""Original-byte import planning and full-cohort exports; AJ validates all facts."""

import hashlib
import uuid
from typing import List, Optional, Union

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution_input import REQUIRED_FIELDS
from core.services.workbench.field_report_files_codec import decode_reports, encode_reports
from core.services.workbench.field_report_files_identity import identity_values, matched_task, task_indexes


class FieldReportFileService:
    def __init__(self, conn, *, context_factory=None):
        from core.services.workbench.production_report import WorkbenchProductionReportService

        self.conn = conn
        self.production = WorkbenchProductionReportService(conn, context_factory=context_factory)

    def _resource_index(self):
        rows = self.conn.execute("""SELECT e.ref,e.kind,e.entity_key,
            CASE WHEN e.kind='machine' THEN m.name ELSE o.name END AS label
            FROM WorkbenchEntityRefs e
            LEFT JOIN Machines m ON e.kind='machine' AND m.machine_id=e.entity_key
            LEFT JOIN Operators o ON e.kind='operator' AND o.operator_id=e.entity_key
            WHERE e.active=1 AND e.kind IN ('machine','operator')""")
        result = {}
        for ref, kind, code, label in rows:
            for value in (code, label):
                if type(value) is str and value:
                    result.setdefault((kind, value), set()).add(ref)
        return result

    @staticmethod
    def _resource(index, kind, value):
        if not value:
            return None
        options = index.get((kind, value), set())
        if len(options) != 1:
            raise WorkbenchCommandRejected('invalid_input', '实际资源名称或编号不存在或有重名歧义，请核对。', 422)
        return next(iter(options))

    def _items(self, content, tasks):
        rows = decode_reports(content)
        by_scope, by_ref = task_indexes(tasks)
        resources, items, positions = self._resource_index(), [], []
        digest = hashlib.sha256(content).hexdigest()
        for row in rows:
            value = row['values']
            if row['errors']:
                row['result'] = 'rejected'
                continue
            if all(value.get(key) in (None, '') for key in ('actual_start', 'actual_end', 'completed_quantity', 'effective_processing_hours')):
                row['result'] = 'blank'
                continue
            try:
                task = matched_task(row, by_scope, by_ref)
                items.append(self._row_item(row, task, resources, digest))
                positions.append(row['row'])
                row['result'] = 'pending'
            except WorkbenchCommandRejected as exc:
                row['result'] = 'rejected'
                row['errors'].append({'row': row['row'], 'message': str(exc), 'code': exc.code})
        return rows, items, positions

    def _row_item(self, row, task, resources, digest):
        value = row['values']
        payload = {key: value[key] for key in ('actual_start', 'actual_end', 'completed_quantity', 'effective_processing_hours', 'remark') if value[key] not in (None, '')}
        for kind in ('machine', 'operator'):
            selected = self._resource(resources, kind, value[kind + '_label'])
            if selected is not None:
                payload['actual_' + kind + '_ref'] = selected
        payload.update(source='excel', report_no=value['report_no'] or 'BG-X-' + digest[:32] + '-' + str(row['row']))
        existing = next((report for report in task['execution']['reports'] if report['report_no'] == payload['report_no']), None)
        if existing and existing.get('legacy_fact_ref'):
            payload.update(legacy_fact_ref=existing['legacy_fact_ref'], reason='Excel 核对已关联的原始完工记录')
        return {'action': 'create', 'ref': task['task_ref'], 'payload': payload}

    def preview(self, content, cohort):
        rows, items, positions = self._items(content, cohort['tasks'])
        check = None
        if not any(row['errors'] for row in rows):
            try:
                check = self._checked_rows(items, rows, positions)
            except WorkbenchCommandRejected as exc:
                self._preview_error(exc, rows, positions)
        rejected = sum(bool(row['errors']) for row in rows)
        summary = {'total': len(rows), 'blank': sum(row['result'] == 'blank' for row in rows), 'rejected': rejected,
                   'changed': check['summary']['changed'] if check else 0, 'unchanged': check['summary']['unchanged'] if check else 0}
        public = [{'row': row['row'], 'result': row['result'], 'errors': row['errors']} for row in rows]
        return {'rows': public, 'summary': summary, 'can_confirm': not rejected and bool(items), 'commit_policy': 'atomic',
                'file_sha256': hashlib.sha256(content).hexdigest(), 'items': items,
                'snapshot': check['snapshot'] if check else None, 'scope': cohort['scope']}

    def _checked_rows(self, items, rows, positions):
        check = self.production.preview_batch(items) if items else {'rows': [], 'summary': {'total': 0, 'changed': 0, 'unchanged': 0}, 'can_confirm': True, 'snapshot': {}}
        mapped = dict(zip(positions, check['rows']))
        for row in rows:
            if row['row'] in mapped:
                item = mapped[row['row']]
                row['result'] = item['result'] if item['result'] == 'unchanged' else item['action']
        return check

    @staticmethod
    def _preview_error(exc, rows, positions):
        number = getattr(exc, 'row_number', None)
        original = positions[number - 1] if type(number) is int and 1 <= number <= len(positions) else positions[0] if positions else 1
        target = next((row for row in rows if row['row'] == original), None)
        if target is None:
            raise exc
        target['result'] = 'rejected'
        target['errors'].append({'row': original, 'message': str(exc), 'code': exc.code})

    @staticmethod
    def rows(cohort, template=False):
        result = []
        for task in cohort['tasks']:
            p = task['execution']
            if template and p['execution_state'] == 'complete':
                continue
            reports = p['reports']
            if template:
                reports = [row for row in reports if any(row[key] is None for key in REQUIRED_FIELDS)] or [None]
            for report in reports:
                result.append(FieldReportFileService._export_row(report, task, template))
        return result

    @staticmethod
    def _export_row(report, task, template):
        row = report or {}
        return {'report_no': row.get('report_no') or 'BG-T-' + uuid.uuid4().hex,
                               'batch_id': task['batch_id'], 'operation_label': task['operation_label'],
                               'completed_quantity': row.get('completed_quantity'), 'actual_start': row.get('actual_start'),
                               'actual_end': row.get('actual_end'), 'effective_processing_hours': row.get('effective_processing_hours'),
                               'machine_label': row.get('actual_machine_label') or (task['planned_machine_label'] if template else None),
                               'operator_label': row.get('actual_operator_label') or (task['planned_operator_label'] if template else None),
                'remark': row.get('remark', ''), **identity_values(task)}

    def download(self, cohort, template=False):
        rows = self.rows(cohort, template)
        summaries: List[List[Optional[Union[str, int, float]]]] = [['批次号', '工序', '应做数量', '累计完成', '剩余数量', '工序状态', '完成依据', '资料完整性']]
        metadata: List[List[Optional[Union[str, int, float]]]] = [['报工编号', '录入时间', '报工来源', '补齐及更正次数']]
        labels = {'unreported': '待报工', 'started': '已登记开工', 'partial': '部分完成', 'paused': '已暂停', 'exception': '异常', 'complete': '已完工'}
        for task in cohort['tasks']:
            p = task['execution']
            summaries.append([task['batch_id'], task['operation_label'], p['target_quantity'], p['known_completed_quantity'],
                              p['remaining_quantity'], labels[p['execution_state']],
                              {'complete_reports': '完整逐次报工', 'legacy_finish_event': '原始完工事实'}.get(p['completion_basis']),
                              {'complete': '完整', 'incomplete': '待补', 'legacy_incomplete': '旧记录待补', 'invalid': '需复核'}[p['data_quality']]])
            for report in p['reports']:
                corrections = sum(item['action'] in ('supplement', 'correct') for item in report['correction_history'])
                metadata.append([report['report_no'], report['recorded_at'], 'Excel' if report['source'] == 'excel' else '手工', corrections])
        return encode_reports(rows, template=template, summaries=() if template else summaries,
                              metadata=() if template else metadata, format_version=2), len(rows)
