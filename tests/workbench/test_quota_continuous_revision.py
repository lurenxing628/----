"""Continuous template revisions on real SQLite, copies, reports and import codecs."""

import sqlite3

import pytest

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_calibration_adoption_schema import contract_issues
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.template_hours import ProcessTemplateHours
from core.services.process.workflow_state import record_confirmation
from core.services.workbench.process.file_codec import encode_process_file
from core.services.workbench.process.files import WorkbenchProcessFileService
from core.services.workbench.process.group_defaults import default_suppliers
from core.services.workbench.process.route_apply import apply_route, prepare_route
from core.services.workbench.process.stage_apply import (
    apply_prepared_hours,
    apply_source,
    prepare_hours,
    prepare_source,
    source_catalog,
)
from data.repositories.workbench_calibration_adoption_repo import WorkbenchCalibrationAdoptionRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository
from tests.workbench.calibration_adoption_support import INTENT, KEY, PREVIEW_INTENT, service, snapshot, token
from tests.workbench.calibration_adoption_support import adoption_case as _adoption_case  # noqa: F401
from tests.workbench.calibration_adoption_support import ready_adoption_case as _ready_case  # noqa: F401
from tests.workbench.process_route_support import load_route_reference_facts
from tests.workbench.template_lineage_support import completed, create
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage_case  # noqa: F401


def adopt(case, key=KEY):
    return service(case.conn).confirm(case.template_ref, token(case), key, INTENT)


def current(case):
    return WorkbenchProcessQueryRepository(case.conn, part_ref=case.ref('part', 'P1')).operations()[0]


def confirm_hours(case):
    with TransactionManager(case.conn).transaction():
        for stage in ('route', 'source', 'hours'):
            record_confirmation(case.conn, 'P1', stage)


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


def test_all_writers_preserve_existing_batches_and_plans_after_adoption(ready_adoption_case):
    case = ready_adoption_case
    adopt(case)
    before = snapshot(case.conn)
    assert not contract_issues(case.conn)
    ref, revision = case.template_ref, current(case)['revision']
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        old = current(case)
        ProcessTemplateHours(case.conn).revise_current(old, {'setup_hours': 0, 'unit_hours': 4.5},
                                                       expected_revision=old['revision'])
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        old = current(case)
        prepared = prepare_hours({'operations': [{'ref': ref, 'setup_hours': 0, 'unit_hours': 5.5}],
                                  'groups': [], 'confirm_zero_unit_hours': False}, [old], [], confirmations={})
        assert apply_prepared_hours(case.conn, prepared)
    confirm_hours(case)
    import_hours(case, 6.5, 'csv')
    import_hours(case, 7.5, 'xlsx')
    assert current(case)['ref'] == ref and current(case)['revision'] == revision + 4
    latest = service(case.conn).repo.latest_adoption(ref)
    assert latest is not None and latest['new_unit_hours'] == 3
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
    latest = service(case.conn).repo.latest_adoption(case.template_ref)
    assert latest is not None and latest['adoption_ref'] == second['adoption_ref']
    history = case.conn.execute('SELECT old_unit_hours,new_unit_hours FROM WorkbenchCalibrationAdoptions ORDER BY rowid').fetchall()
    assert [tuple(row) for row in history] == [(1, 3), (3, 6)]
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        old = current(case)
        ProcessTemplateHours(case.conn).revise_current(old, {'setup_hours': 0, 'unit_hours': 8},
                                                       expected_revision=old['revision'])
    assert current(case)['unit_hours'] == 8
    receipt = service(case.conn).receipt(case.template_ref, KEY)
    assert receipt is not None and receipt['data'] == first


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
        facts = load_route_reference_facts(case.conn)
        if entry == 'source':
            changes = prepare_source({'operations': [
                {'ref': old['ref'], 'op_type_ref': ref, 'source': 'internal', 'supplier_ref': None}]}, [old], identities,
                                     catalog=source_catalog(facts.references))
            apply_source(case.conn, changes, [old])
        else:
            preview, _ = prepare_route(case.conn, None, {'route': {'mode': 'rows', 'rows': [{'seq': 1, 'op_type_name': 'Milling'}]}}, [old],
                                       facts=facts)
            assert preview['can_confirm_route'], preview
            assert apply_route(case.conn, {'part_no': 'P1', 'route_raw': None, 'route_parsed': 'no'}, [old], preview, identities,
                               default_catalog_reader=lambda: default_suppliers(facts.references))
    new = current(case)
    assert new['id'] == old['id'] and new['ref'] == old['ref'] and new['revision'] > old['revision']
    assert new['op_type_id'] == 'T2' and new['setup_hours'] is None and new['unit_hours'] is None
    latest = service(case.conn).repo.latest_adoption(case.template_ref)
    assert latest is not None and latest['new_unit_hours'] == 3


def test_history_is_append_only_but_templates_are_revisable(ready_adoption_case):
    case = ready_adoption_case
    adopt(case)
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        case.conn.execute('UPDATE WorkbenchCalibrationAdoptions SET new_unit_hours=9')
    case.conn.rollback()
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        old = current(case)
        ProcessTemplateHours(case.conn).revise_current(old, {'setup_hours': 0, 'unit_hours': 9},
                                                       expected_revision=old['revision'])
    assert current(case)['unit_hours'] == 9
    latest = service(case.conn).repo.latest_adoption(case.template_ref)
    assert latest is not None and latest['new_unit_hours'] == 3


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


def test_template_ref_integer_lookup_keeps_exact_text_keys_and_missing_lineage_rows(schema_conn):
    conn = schema_conn
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('R10-P','test part')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('R10-B','R10-P',1)")
    template_id = conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,source,setup_hours,unit_hours) "
                               "VALUES ('R10-P',1,'turning','internal',0,1)").lastrowid
    operation_id = conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,setup_hours,unit_hours) "
                                "VALUES ('R10-O','R10-B',1,'turning','internal',0,1)").lastrowid
    template_ref = conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='template_operation' AND entity_key=? AND active=1",
                                (str(template_id),)).fetchone()[0]
    operation_ref = conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
                                 (str(operation_id),)).fetchone()[0]
    bad_templates, bad_operations = [], []
    for index, key in enumerate(('0{}', '{}x'), 1):
        template_bad, operation_bad = 'a' * 47 + str(index), 'b' * 47 + str(index)
        conn.execute("INSERT INTO WorkbenchEntityRefs(ref,kind,entity_key) VALUES (?,'template_operation',?)",
                     (template_bad, key.format(template_id)))
        conn.execute("INSERT INTO WorkbenchPlanSourceRefs(ref,kind,source_key) VALUES (?,'operation',?)",
                     (operation_bad, key.format(operation_id)))
        bad_templates.append(template_bad)
        bad_operations.append(operation_bad)
    conn.commit()
    lineage = WorkbenchTemplateLineageRepository(conn)
    templates = lineage.current_templates([template_ref] + bad_templates)
    assert templates[template_ref]['id'] == template_id
    assert all(templates[ref]['id'] is None and templates[ref]['template_operation_ref'] == ref for ref in bad_templates)
    instances = lineage.current_instances([operation_ref] + bad_operations)
    assert list(instances) == [operation_ref] and instances[operation_ref]['id'] == operation_id
    adoption = WorkbenchCalibrationAdoptionRepository(conn)
    template = adoption.template(template_ref)
    assert template is not None and template['id'] == template_id
    assert all(adoption.template(ref) is None for ref in bad_templates)
