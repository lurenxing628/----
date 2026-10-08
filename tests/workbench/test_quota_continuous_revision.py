"""Continuous template revisions on real SQLite, copies, reports and import codecs."""

import sqlite3

import pytest

from core.infrastructure.migrations.v39 import run as retire_quota_locks
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_calibration_adoption_legacy_schema import objects as legacy_objects
from core.infrastructure.workbench_calibration_adoption_schema import contract_issues, objects
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.process.part_service import PartService
from core.services.process.template_hours import ProcessTemplateHours
from core.services.process.workflow_state import record_confirmation
from core.services.workbench.process.file_codec import encode_process_file
from core.services.workbench.process.files import WorkbenchProcessFileService
from core.services.workbench.process.route_apply import apply_route, prepare_route
from core.services.workbench.process.stage_apply import apply_hours, apply_source, prepare_source
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.calibration_adoption_support import INTENT, KEY, PREVIEW_INTENT, service, snapshot, token
from tests.workbench.calibration_adoption_support import adoption_case as _adoption_case  # noqa: F401
from tests.workbench.calibration_adoption_support import ready_adoption_case as _ready_case  # noqa: F401
from tests.workbench.template_lineage_support import completed, create
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage_case  # noqa: F401


def adopt(case, key=KEY):
    return service(case.conn).confirm(case.template_ref, token(case), key, INTENT)


def current(case):
    return ProcessTemplateHours(case.conn).current([case.template_ref])[case.template_ref]


def confirm_hours(case):
    with TransactionManager(case.conn).transaction():
        for stage in ('route', 'source', 'hours'):
            record_confirmation(case.conn, 'P1', stage)


def install_old_lock(case, audit):
    """Reconstruct the exact prior DDL with a real adopted row and matching lock."""
    with TransactionManager(case.conn).transaction():
        for name in objects():
            if name != 'WorkbenchCalibrationAdoptions':
                case.conn.execute('DROP TRIGGER "' + name + '"')
        case.conn.execute('ALTER TABLE WorkbenchCalibrationAdoptions RENAME TO adoption_test_copy')
        for sql in legacy_objects().values():
            case.conn.execute(sql)
        case.conn.execute('INSERT INTO WorkbenchCalibrationAdoptions SELECT * FROM adoption_test_copy')
        case.conn.execute('DROP TABLE adoption_test_copy')
        case.conn.execute('INSERT INTO WorkbenchCalibrationQuotaLocks VALUES (?,?,?,?)',
                          (case.template_ref, audit['adoption_ref'], audit['new_unit_hours'], audit['adopted_at']))


def import_hours(case, value, fmt):
    content = encode_process_file('hours', [{'business_code': 'P1', 'sequence': 1, 'unit_hours': value}], fmt).content
    files = WorkbenchProcessFileService(case.conn)
    preview, extra = files.preview_import('hours', content, file_format=fmt)
    body = preview.as_dict()
    assert 'file_sha256' not in body['request']
    assert body['summary']['update'] == 1 and body['summary']['rejected'] == 0
    assert 'skipped_count' not in extra
    assert body['rows'][0]['changes']['unit_hours']['after'] == value
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        result = files.confirm_import(preview, content, discard_group_refs=[], confirm_zero_unit_hours=False)
    assert result.result == 'committed'
    assert result.data['rows'][0]['result'] == 'committed'
    assert current(case)['unit_hours'] == value


def test_old_lock_migration_then_all_writers_preserve_existing_batches_and_plans(ready_adoption_case):
    case = ready_adoption_case
    audit = adopt(case)['data']
    install_old_lock(case, audit)
    before = snapshot(case.conn)
    retire_quota_locks(case.conn)
    after = snapshot(case.conn)
    assert not contract_issues(case.conn)
    assert 'WorkbenchCalibrationQuotaLocks' not in after
    assert {table: rows for table, rows in before.items() if table != 'WorkbenchCalibrationQuotaLocks'} == after
    ref, revision = case.template_ref, current(case)['revision']
    PartService(case.conn).update_internal_hours('P1', 1, 0, 4.5)
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        old = current(case)
        assert apply_hours(case.conn, {'operations': [{'ref': ref, 'setup_hours': 0, 'unit_hours': 5.5}],
                                      'groups': [], 'confirm_zero_unit_hours': False}, [old], [])
    confirm_hours(case)
    import_hours(case, 6.5, 'csv')
    import_hours(case, 7.5, 'xlsx')
    assert current(case)['ref'] == ref and current(case)['revision'] == revision + 4
    assert service(case.conn).repo.latest_adoption(ref)['new_unit_hours'] == 3
    for table in ('WorkbenchCalibrationAdoptions', 'WorkbenchCommandReceipts', 'BatchOperations', 'Schedule', 'ScheduleHistory'):
        assert snapshot(case.conn)[table] == before[table]
    confirm_hours(case)
    new_id = create(case, 'AFTER-REVISION')
    assert case.conn.execute('SELECT unit_hours FROM BatchOperations WHERE id=?', (new_id,)).fetchone()[0] == 7.5


def test_repeated_adoption_uses_fresh_samples_of_the_current_version(ready_adoption_case):
    case = ready_adoption_case
    first = adopt(case)['data']
    assert first['old_unit_hours'] == 1 and first['new_unit_hours'] == 3
    blocked = service(case.conn).preview(case.template_ref, PREVIEW_INTENT)
    assert not blocked['validation']['can_adopt']
    assert [row['code'] for row in blocked['validation']['issues']] == ['insufficient_samples']
    completed(case, [2, 4, 6, 8, 10], prefix='SECOND', version=3)
    second = adopt(case, KEY + '-second')['data']
    assert second['old_unit_hours'] == 3 and second['new_unit_hours'] == 6
    assert second['template_revision_before'] == first['template_revision_after']
    assert second['template_revision_after'] == first['template_revision_after'] + 1
    assert service(case.conn).repo.latest_adoption(case.template_ref)['adoption_ref'] == second['adoption_ref']
    history = case.conn.execute('SELECT old_unit_hours,new_unit_hours FROM WorkbenchCalibrationAdoptions ORDER BY rowid').fetchall()
    assert [tuple(row) for row in history] == [(1, 3), (3, 6)]
    PartService(case.conn).update_internal_hours('P1', 1, 0, 8)
    assert current(case)['unit_hours'] == 8
    assert service(case.conn).receipt(case.template_ref, KEY)['data'] == first


def test_same_value_adoption_history_invalidates_old_preview(adoption_case):
    case = adoption_case
    completed(case, [1] * 5)
    write_token = token(case)
    old_revision = current(case)['revision']
    service(case.conn).confirm(case.template_ref, write_token, KEY, INTENT)
    assert current(case)['revision'] == old_revision
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        service(case.conn).confirm(case.template_ref, write_token, KEY + '-stale', INTENT)
    assert rejected.value.code == 'stale_write'
    adopt(case, KEY + '-fresh')
    assert case.conn.execute('SELECT count(*) FROM WorkbenchCalibrationAdoptions').fetchone()[0] == 2


@pytest.mark.parametrize('entry', ['source', 'route'])
def test_actual_work_type_change_clears_old_hours_without_lock(ready_adoption_case, entry):
    case = ready_adoption_case
    adopt(case)
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T2','Milling')")
    case.conn.commit()
    identities = WorkbenchIdentityRepository(case.conn)
    ref = case.ref('op_type', 'T2')
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        old = current(case)
        if entry == 'source':
            changes, _ = prepare_source(case.conn, None, {'operations': [
                {'ref': old['ref'], 'op_type_ref': ref, 'source': 'internal', 'supplier_ref': None}]}, [old], identities)
            apply_source(case.conn, changes, [old])
        else:
            preview, _ = prepare_route(case.conn, None, {'route': {'mode': 'rows', 'rows': [{'seq': 1, 'op_type_name': 'Milling'}]}}, [old])
            assert preview['can_confirm_route'], preview
            assert apply_route(case.conn, {'part_no': 'P1', 'route_raw': None, 'route_parsed': 'no'}, [old], preview, identities)
    new = current(case)
    assert new['id'] == old['id'] and new['ref'] == old['ref'] and new['revision'] > old['revision']
    assert new['op_type_id'] == 'T2' and new['setup_hours'] is None and new['unit_hours'] is None
    assert service(case.conn).repo.latest_adoption(case.template_ref)['new_unit_hours'] == 3


def test_history_is_append_only_but_templates_are_revisable(ready_adoption_case):
    case = ready_adoption_case
    adopt(case)
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        case.conn.execute('UPDATE WorkbenchCalibrationAdoptions SET new_unit_hours=9')
    case.conn.rollback()
    PartService(case.conn).update_internal_hours('P1', 1, 0, 9)
    assert current(case)['unit_hours'] == 9
    assert service(case.conn).repo.latest_adoption(case.template_ref)['new_unit_hours'] == 3


def test_import_rechecks_changes_and_rolls_back_without_a_file_hash(ready_adoption_case):
    case = ready_adoption_case
    adopt(case)
    confirm_hours(case)
    files = WorkbenchProcessFileService(case.conn)
    content = encode_process_file('hours', [{'business_code': 'P1', 'sequence': 1, 'unit_hours': 5}], 'csv').content
    preview, _ = files.preview_import('hours', content, file_format='csv')
    changed = encode_process_file('hours', [{'business_code': 'P1', 'sequence': 1, 'unit_hours': 6}], 'csv').content
    with pytest.raises(WorkbenchCommandRejected, match='预检'):
        with TransactionManager(case.conn).transaction(begin_immediate=True):
            files.confirm_import(preview, changed, discard_group_refs=[], confirm_zero_unit_hours=False)
    assert current(case)['unit_hours'] == 3


def test_migration_failure_rolls_back_old_history_and_lock(ready_adoption_case, monkeypatch):
    case = ready_adoption_case
    install_old_lock(case, adopt(case)['data'])
    before = snapshot(case.conn)
    definitions = objects()
    definitions['wb_calibration_adoption_no_replace'] = 'CREATE TRIGGER invalid_sql'
    monkeypatch.setattr('core.infrastructure.migrations.v39.objects', lambda: definitions)
    with pytest.raises(sqlite3.DatabaseError):
        retire_quota_locks(case.conn)
    assert snapshot(case.conn) == before


@pytest.mark.parametrize('type_name,expected', [('Turning', 3), ('Milling', None)])
def test_legacy_route_save_retains_hours_only_for_the_same_type(ready_adoption_case, type_name, expected):
    case = ready_adoption_case
    audit = adopt(case)['data']
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T2','Milling')")
    case.conn.commit()
    PartService(case.conn).reparse_and_save('P1', '1:' + type_name)
    row = case.conn.execute("SELECT setup_hours,unit_hours FROM PartOperations WHERE part_no='P1' AND status='active'").fetchone()
    assert row['unit_hours'] == expected
    assert row['setup_hours'] == (0 if type_name == 'Turning' else None)
    assert service(case.conn).receipt(case.template_ref, KEY)['data'] == audit
