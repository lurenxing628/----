"""Continuous template revisions on real SQLite, copies, reports and import codecs."""

import pytest

from core.infrastructure.schema_structure import SchemaStructure
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_calibration_adoption_schema import contract_issues
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_route import normalize_route_preview_input
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
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository
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
    preview, extra = files.preview_import('hours', content, file_format=fmt, mode='upsert', target_ref=None)
    body = preview.as_dict()
    assert 'file_sha256' not in body['request']
    assert body['summary']['update'] == 1 and body['summary']['rejected'] == 0
    assert 'skipped_count' not in extra
    assert body['rows'][0]['changes']['unit_hours']['after'] == value
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        result = files.confirm_import(preview, discard_group_refs=[], confirm_zero_unit_hours=False)
    assert result.result == 'committed'
    assert result.data['rows'][0]['result'] == 'committed'
    assert current(case)['unit_hours'] == value


def test_all_writers_preserve_existing_batches_and_plans_after_adoption(ready_adoption_case):
    case = ready_adoption_case
    adopt(case)
    before = snapshot(case.conn)
    assert not contract_issues(SchemaStructure(case.conn))
    ref, revision = case.template_ref, current(case)['revision']
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        old = current(case)
        ProcessTemplateHours(case.conn).revise_current(old, {'setup_hours': 0, 'unit_hours': 4.5})
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        old = current(case)
        prepared = prepare_hours({'operations': [{'ref': ref, 'setup_hours': 0, 'unit_hours': 5.5}],
                                  'groups': [], 'confirm_zero_unit_hours': False}, [old], [],
                                 confirmations={'P1': {ref: {'hours': {'state': 'confirmed'}}}})
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
        ProcessTemplateHours(case.conn).revise_current(old, {'setup_hours': 0, 'unit_hours': 8})
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
    ref = case.ref('op_type', 'T2')
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        old = current(case)
        facts = load_route_reference_facts(case.conn)
        if entry == 'source':
            changes = prepare_source({'operations': [
                {'ref': old['ref'], 'op_type_ref': ref, 'source': 'internal', 'supplier_ref': None}]}, [old], facts.identities,
                                     catalog=source_catalog(facts.references))
            apply_source(case.conn, changes, [old])
        else:
            preview, _ = prepare_route(
                None,
                [old],
                facts=facts,
                normalized=normalize_route_preview_input({'mode': 'rows', 'rows': [{'seq': 1, 'op_type_name': 'Milling'}]}),
            )
            assert preview['can_confirm_route'], preview
            assert apply_route(case.conn, {'part_no': 'P1', 'route_raw': None, 'route_parsed': 'no'}, [old], preview, facts.identities,
                               default_catalog_reader=lambda: default_suppliers(facts.references))
    new = current(case)
    assert new['id'] == old['id'] and new['ref'] == old['ref'] and new['revision'] > old['revision']
    assert new['op_type_id'] == 'T2' and new['setup_hours'] is None and new['unit_hours'] is None
    latest = service(case.conn).repo.latest_adoption(case.template_ref)
    assert latest is not None and latest['new_unit_hours'] == 3


def test_history_is_append_only_but_templates_are_revisable(ready_adoption_case):
    case = ready_adoption_case
    adopt(case)
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        old = current(case)
        ProcessTemplateHours(case.conn).revise_current(old, {'setup_hours': 0, 'unit_hours': 9})
    assert current(case)['unit_hours'] == 9
    latest = service(case.conn).repo.latest_adoption(case.template_ref)
    assert latest is not None and latest['new_unit_hours'] == 3


def test_import_rejects_preview_made_stale_by_a_newer_import_without_a_file_hash(ready_adoption_case):
    case = ready_adoption_case
    adopt(case)
    confirm_hours(case)
    files = WorkbenchProcessFileService(case.conn)
    content = encode_process_file('hours', [{'business_code': 'P1', 'sequence': 1, 'unit_hours': 5}], 'csv').content
    preview, _ = files.preview_import('hours', content, file_format='csv', mode='upsert', target_ref=None)
    assert 'file_sha256' not in preview.as_dict()['request']
    changed = encode_process_file('hours', [{'business_code': 'P1', 'sequence': 1, 'unit_hours': 6}], 'csv').content
    other, _ = files.preview_import('hours', changed, file_format='csv', mode='upsert', target_ref=None)
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        files.confirm_import(other, discard_group_refs=[], confirm_zero_unit_hours=False)
    assert current(case)['unit_hours'] == 6
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        with TransactionManager(case.conn).transaction(begin_immediate=True):
            files.confirm_import(preview, discard_group_refs=[], confirm_zero_unit_hours=False)
    assert rejected.value.code == 'stale_write'
    assert current(case)['unit_hours'] == 6


def test_calibration_median_and_deviation_use_exact_decimal_ratios(adoption_case):
    from datetime import datetime, timedelta

    from tests.workbench.template_lineage_support import calibration

    case = adoption_case
    # 6 batches of quantity=3 with totals [0, 0, 2.0, 2.003, 9, 9]:
    # Quantized sample unit_hours are [0.0, 0.0, 0.667, 0.668, 3.0, 3.0] (median -> 0.6675 -> 0.668),
    # whereas exact ratios [0, 0, 2/3, 2.003/3, 3, 3] have median 4.003/6 = 0.667166... -> 0.667.
    totals = [0.0, 0.0, 2.0, 2.003, 9.0, 9.0]
    ids = [create(case, f'EXACT-MEDIAN-{idx:03d}', quantity=3) for idx in range(len(totals))]
    case.plan(2, ids)
    for idx, (op_id, total_hours) in enumerate(zip(ids, totals)):
        end = datetime(2026, 9, 9, 10) + timedelta(minutes=idx)
        start = end - timedelta(hours=int(total_hours) + 2)
        case.command(
            'create',
            case.task(2, op_id),
            case.values(
                3,
                effective_processing_hours=total_hours,
                actual_start=start.isoformat(),
                actual_end=end.isoformat(),
            ),
        )
    facts = calibration(case)
    row = facts['rows'][0]
    assert '_raw_suggested_unit_hours' not in row
    assert row['suggested_unit_hours'] == 0.667

    # Revise template old_unit_hours to 0.5, then complete 5 batches of quantity=2 with split reports
    # (1.2h + 5e-17h): float effective_processing_hours rounds to 1.2 and unit_hours rounds to 0.6 (exact 20%),
    # while exact Decimal sum (1.2 + 5e-17) / 2 = 0.600000000000000025 exceeds old_unit_hours by strictly > 20%.
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        ProcessTemplateHours(case.conn).revise_current(current(case), {'setup_hours': 0, 'unit_hours': 0.5})
    split_ids = [create(case, f'EXACT-DEV-{idx:03d}', quantity=2) for idx in range(5)]
    case.plan(3, split_ids)
    for idx, op_id in enumerate(split_ids):
        t0 = datetime(2026, 9, 9, 11) + timedelta(minutes=idx * 5)
        t1 = t0 + timedelta(hours=2)
        t2 = t1 + timedelta(minutes=1)
        task_ref = case.task(3, op_id)
        case.command(
            'create',
            task_ref,
            case.values(1, effective_processing_hours=1.2, actual_start=t0.isoformat(), actual_end=t1.isoformat()),
        )
        case.command(
            'create',
            task_ref,
            case.values(1, effective_processing_hours=5e-17, actual_start=t1.isoformat(), actual_end=t2.isoformat()),
        )
    revised_facts = calibration(case)
    revised_row = revised_facts['rows'][0]
    samples = revised_facts['samples_by_template'][case.template_ref]
    selected_samples = [item for item in samples if item['selected']]
    assert len(selected_samples) == 5
    assert all(item['effective_processing_hours'] == 1.2 and item['unit_hours'] == 0.6 for item in selected_samples)
    assert revised_row['suggested_unit_hours'] == 0.6
    assert revised_row['deviation_percent'] == 20.0
    assert revised_row['over_20_percent'] is True

    # Also verify split reports beyond the default 28-digit Decimal precision (1.2h + 5e-29h):
    # exact Fraction sum (1.2 + 5e-29) / 2 relative to old_unit_hours=0.5 still exceeds 20% strictly.
    with TransactionManager(case.conn).transaction(begin_immediate=True):
        ProcessTemplateHours(case.conn).revise_current(current(case), {'setup_hours': 1, 'unit_hours': 0.5})
    deep_ids = [create(case, f'EXACT-FRAC-{idx:03d}', quantity=2) for idx in range(5)]
    case.plan(4, deep_ids)
    for idx, op_id in enumerate(deep_ids):
        t0 = datetime(2026, 9, 9, 12) + timedelta(minutes=idx * 5)
        t1 = t0 + timedelta(hours=2)
        t2 = t1 + timedelta(minutes=1)
        task_ref = case.task(4, op_id)
        case.command(
            'create',
            task_ref,
            case.values(1, effective_processing_hours=1.2, actual_start=t0.isoformat(), actual_end=t1.isoformat()),
        )
        case.command(
            'create',
            task_ref,
            case.values(1, effective_processing_hours=5e-29, actual_start=t1.isoformat(), actual_end=t2.isoformat()),
        )
    deep_facts = calibration(case)
    deep_row = deep_facts['rows'][0]
    deep_selected = [item for item in deep_facts['samples_by_template'][case.template_ref] if item['selected']]
    assert len(deep_selected) == 5
    assert all(item['effective_processing_hours'] == 1.2 and item['unit_hours'] == 0.6 for item in deep_selected)
    assert deep_row['suggested_unit_hours'] == 0.6
    assert deep_row['deviation_percent'] == 20.0
    assert deep_row['over_20_percent'] is True
