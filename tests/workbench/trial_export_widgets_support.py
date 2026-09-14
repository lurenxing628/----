"""CZ export fixtures: real trial DTOs and byte/typed-row SQLite read-only proof."""

import csv
import hashlib
import io
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from flask import jsonify

from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.run_jobs_support import JobCase
from tests.workbench.trial_widgets_support import TrialWidgetServer, service, snapshot


class TrialExportServer(TrialWidgetServer):
    def __init__(self, root):
        super().__init__(root)
        with self.connect() as conn, self.app.app_context():
            case = JobCase(conn)
            ids = []
            for index in range(24):
                code = f'CZ-{index:03d}'
                case.batch(code, due_date='2026-09-08' if index == 23 else '2026-09-25',
                           priority=('normal', 'urgent', 'critical')[index % 3])
                for seq in range(1, 4):
                    ids.append(case.operation(code, seq=seq, unit_hours=1 / 180,
                                              op_type_name='精加工,核对"原文"\r\n第二行' if index == 0 else '精加工'))
            case.plan(14, ids, start='2026-09-09T08:00:00', end='2026-09-09T09:12:00')
            start = datetime(2026, 9, 9, 8)
            conn.executemany('UPDATE Schedule SET start_time=?,end_time=? WHERE version=14 AND op_id=?', [
                ((start + timedelta(minutes=i)).isoformat(), (start + timedelta(minutes=i + 1)).isoformat(), op_id)
                for i, op_id in enumerate(ids)])
            case.batch('CZ-NOT-READY', ready_status='no')
            case.operation('CZ-NOT-READY')
            case.batch('CZ-EXT')
            conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('CZEXT','外协表面处理','external')")
            conn.execute("INSERT INTO Suppliers(supplier_id,name) VALUES ('CZS','外协供应商')")
            external_id = case.operation('CZ-EXT', source='external', op_type_id='CZEXT', op_type_name='外协表面处理',
                                         supplier_id='CZS', ext_days=1.25, machine_id=None, operator_id=None)
            case.plan(15, [external_id], start='2026-09-09T08:00:00', end='2026-09-10T14:00:00')
            conn.execute('UPDATE Schedule SET machine_id=NULL,operator_id=NULL WHERE version=15')
            conn.commit()
            accepted = case.accept(key='CZ-partial-run-00000001', settings=case.settings('B1', 'CZ-NOT-READY'))
            partial_run = WorkbenchRunWorker(conn).execute(accepted['run_ref'])
            partial_ref = next(row['candidate_ref'] for row in partial_run['candidates'] if row['status'] == 'completed')
            api = service(conn)
            inputs = {'base': {'plan_ref': case.plan_ref(14)}, 'scope': {'query': 'does-not-match-visible-tasks'}}
            draft = self.create(api, inputs, 'large')
            task = next(t for t in draft['tasks'] if t['batch_id'] == 'CZ-023' and t['sequence'] == 3)
            draft = api.change(draft['draft_ref'], {'task_ref': task['task_ref'], 'machine_ref': self.refs['machines']['M3'],
                'operator_ref': self.refs['operators']['O3'], 'start': '2026-09-09T13:00:00'},
                draft['write_context']['write_token'], 'CZ-export-change-00000001')['data']
            saved = api.save(draft['draft_ref'], {'name': '=核对,"试调"\r\n完整场景'},
                             draft['write_context']['write_token'], 'CZ-export-save-00000001')['data']
            current = self.create(api, inputs, 'editing')
            candidate = self.create(api, {'base': {'candidate_ref': self.refs['candidate_ref']}}, 'candidate')
            partial = self.create(api, {'base': {'candidate_ref': partial_ref}}, 'partial')
            external = self.create(api, {'base': {'plan_ref': case.plan_ref(15)}}, 'external')
            assert partial['unplanned_operations'] and not partial['scope_complete']
            assert external['tasks'][0]['hours']['days'] == 1.25
            self.targets = [
                {'name': 'saved-plan', 'target': {'scenario_ref': saved['scenario_ref']}},
                {'name': 'editing-plan', 'target': {'draft_ref': current['draft_ref']}},
                {'name': 'editing-candidate', 'target': {'draft_ref': candidate['draft_ref']}},
                {'name': 'partial-candidate', 'target': {'draft_ref': partial['draft_ref']}},
                {'name': 'external-plan', 'target': {'draft_ref': external['draft_ref']}},
            ]
            self.before = snapshot(conn)
        self.initial = self.database_evidence()
        self.app.add_url_rule('/fixture/export-targets', 'cz_export_targets', lambda: jsonify(self.targets))
        self.app.add_url_rule('/fixture/export-proof', 'cz_export_proof', lambda: jsonify(self.database_evidence()))

    @staticmethod
    def create(api, inputs, suffix):
        preview = api.preview_create(inputs)
        return api.create(inputs, preview['write_context']['write_token'], 'CZ-export-create-' + suffix)['data']

    def database_evidence(self):
        with self.connect() as conn:
            values = snapshot(conn)
            schema = [tuple(row) for row in conn.execute('SELECT * FROM sqlite_master ORDER BY type,name')]
            integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
            foreign_keys = [tuple(row) for row in conn.execute('PRAGMA foreign_key_check')]
        files = {suffix: hashlib.sha256(path.read_bytes()).hexdigest() for suffix in ('', '-wal')
                 for path in [self.path.with_name(self.path.name + suffix)] if path.exists()}
        return {'database': str(self.path), 'typed_rows_sha256': hashlib.sha256(repr(values).encode('utf-8')).hexdigest(),
                'schema_sha256': hashlib.sha256(repr(schema).encode('utf-8')).hexdigest(), 'files': files,
                'table_counts': {key: len(rows) for key, rows in values.items()}, 'integrity': integrity,
                'foreign_keys': foreign_keys}

    def proof(self):
        result = super().proof()
        final = self.database_evidence()
        result.update(before=self.initial, after=final, all_database_rows_unchanged=self.initial == final)
        assert self.initial == final, 'Export or read changed isolated SQLite'
        return result


def public_snapshot(value):
    if isinstance(value, dict):
        return {key: public_snapshot(item) for key, item in value.items() if key != 'write_context'}
    if isinstance(value, list):
        return [public_snapshot(item) for item in value]
    return value


HEADERS = ['方案', '方案状态', '约束说明（非取舍评估）', '对比基准方案', '换型次数（次）',
           '批次', '产品', '数量（件）', '优先级', '交期（截至日）', '对比基准完工', '方案完工',
           '超期（小时）', '完工提前（小时，负数为延后）', '工序调整', '换设备', '交付风险',
           '草稿编号', '试调方案编号', '原来源编号', '试调方案保存时间', '核对提示']
STATES = {'editing': '可继续试调', 'saved': '已保存', 'discarded': '已放弃', 'valid': '通过', 'warning': '有提示', 'blocked': '有冲突，不能采用'}
PRIORITIES = {'normal': '普通', 'urgent': '急件', 'critical': '特急'}
RISKS = {'on_time': '可按期', 'overdue': '预计超期', 'unavailable': '有冲突，不能评估', 'invalid_data': '交期数据无效'}
MISSING = object()


def translated(value, labels):
    return None if value is None else labels.get(value, '未识别（' + str(value) + '）')


def expected_note(data):
    return ('完整{}批次、{}道安排、{}道未排；不受分页或显示筛选限制。'.format(
        len(data['comparison']['batches']), data['task_count'], len(data['unplanned_operations'])) +
        '对比基准是原试调来源；交期截至日次日零点不含；时间与工厂现场一致；负数提前量表示延后。' +
        ('数据是试调方案保存时的内容。' if data.get('scenario_ref') else '数据是本次页面读到的内容，导出时不刷新。') +
        '未知不等于 0，空白表示不适用；数值保留原精度。' + data['comparison']['changeover_reason'] +
        '文字统一加一个单引号，防止表格把它当公式或改写编号；按标准 CSV 解码后只去掉开头这一个引号。完整任务、资源变更、班表、报工和调整记录见“导出原始数据”（不含系统内部数据）。')


def expected_rows(data):
    validation, comparison = data['validation'], data['comparison']
    constraints = ('试调约束：{}；整体状态：{}；问题{}项，完整原因见原始数据；未评估方案取舍。'.format(
        STATES[validation['constraints_status']], STATES[validation['status']], len(validation['issues'])))
    source = ('计划：' + data['base']['plan_ref'] if 'plan_ref' in data['base'] else '排产候选：' + data['base']['candidate_ref'])
    for batch in comparison['batches']:
        yield [data.get('name') or '未命名试调草稿', STATES[data['status']], constraints,
               data['base_identity'].get('display_name') or '上次排产的候选方案',
               '未评估' if comparison['changeovers'] is None else comparison['changeovers'],
               batch['batch_id'], batch['part_name'], batch['quantity'], translated(batch['priority'], PRIORITIES),
               batch['due_date'], batch['baseline_finish'], batch['finish'], batch['late_hours'], batch['improvement_hours'],
               batch['changed'], batch['moved'], RISKS[batch['risk']], data['draft_ref'], data.get('scenario_ref', MISSING),
               source, (data.get('saved_at') or '未记录') if data.get('scenario_ref') else MISSING, expected_note(data)]


def verify_download(item):
    """Decode with Python's standard CSV parser, then compare every cell against DTO semantics."""
    data = json.loads(Path(item['dto']).read_text(encoding='utf-8'))
    payload = Path(item['path']).read_bytes()
    assert payload.startswith(b'\xef\xbb\xbf') and not payload.startswith(b'\xef\xbb\xbf' * 2)
    assert payload.endswith(b'\r\n')
    reader = csv.reader(io.StringIO(payload.decode('utf-8-sig'), newline=''), strict=True)
    header, rows = next(reader), list(reader)
    assert header == HEADERS and len(header) == 22, 'Prototype 16 columns plus six bounded evidence/risk columns only'
    assert len(rows) == len(data['comparison']['batches']), 'Exactly one row per complete batch, never mixed record types'
    for number, (actual, expected) in enumerate(zip(rows, expected_rows(data)), 2):
        assert len(actual) == len(HEADERS)
        for title, text, value in zip(HEADERS, actual, expected):
            if value is MISSING:
                assert text == '', (number, title, text)
            elif type(value) in (int, float):
                assert text and not text.startswith("'"), (number, title, text)
                assert Decimal(text) == Decimal(str(value)), (number, title, text, value)
            else:
                decoded = '未知' if value is None else ('是' if value else '否') if type(value) is bool else value
                assert text == "'" + decoded, (number, title, text, decoded)
    for batch in data['comparison']['batches']:
        tasks = [task for task in data['tasks'] if task['batch_ref'] == batch['batch_ref']]
        assert batch['changed'] == any(task['changed'] for task in tasks)
        assert batch['moved'] == any(task['machine_ref'] != task['original']['machine_ref'] for task in tasks)
    return {'file': item['path'], 'rows': len(rows), 'columns': len(header), 'cells_checked': len(rows) * len(header),
            'standard_csv_strict': True, 'every_cell_matches_dto': True, 'text_prefix_reversible': True}
