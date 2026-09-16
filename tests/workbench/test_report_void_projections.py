"""Consumer checks: no actual timeline, recap, risk hours or calibration sample survives voiding."""

from types import SimpleNamespace

from core.models.workbench_calibration import CalibrationCandidate, CalibrationLineage
from core.services.workbench.actual_gantt import ActualGanttService
from core.services.workbench.actual_gantt_scope import ActualGanttScope
from core.services.workbench.calibration_samples import review_sample
from core.services.workbench.dashboard_execution import _hours
from core.services.workbench.review_records import project_records
from core.services.workbench.run_input_projection_codec import restore_execution_projections
from tests.workbench.calibration_adoption_support import (
    INTENT,
    KEY,
    _ledger_fixture,
    _lineage_case,
    service,
    token,
)
from tests.workbench.calibration_adoption_support import (
    adoption_case as _adoption_case,
)
from tests.workbench.calibration_adoption_support import (
    ready_adoption_case as _ready_adoption_case,
)
from tests.workbench.execution_ledger_support import NOW
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture
from tests.workbench.run_candidate_baseline_support import baseline, original_plan
from tests.workbench.run_candidate_support import candidate_case as _candidate_case
from tests.workbench.run_candidate_support import compute
from tests.workbench.test_execution_report_void import intent, report


def test_all_actual_consumers_use_effective_reports_after_void(ledger_case):
    case = ledger_case
    case.install()
    row = report(case, case.values(10))
    p = case.ledger.get_task(case.task(1, case.op_id))
    template = SimpleNamespace(operation_ref='a' * 48, revision=1, source='internal')
    lineage = CalibrationLineage(template.operation_ref, 1, 'fixture-lineage')
    def sample(projection):
        return review_sample(CalibrationCandidate(projection, 'P1', 'B1', 'OP1', 'internal', lineage), template=template, as_of=NOW)
    assert sample(p)['eligible']
    reader = ActualGanttService(case.conn)
    with reader.read_snapshot():
        before, _ = reader.workspace(ActualGanttScope(case.plan_ref(1)))
    assert before['report_count'] == 1
    case.command('report_void', row['report_ref'], intent(row))
    p = case.ledger.get_task(case.task(1, case.op_id))
    with reader.read_snapshot():
        actual, _ = reader.workspace(ActualGanttScope(case.plan_ref(1)))
    assert actual['report_count'] == 0 and actual['items'][0]['execution']['reports'] == []
    operation = dict(operation_ref=p.operation_ref, batch_ref=case.ref('batch', 'B1'), batch_label='B1', operation_label='1 Turning')
    records = project_records(p.to_dict(), operation, {'machine': {}, 'operator': {}}, NOW)
    assert records == []
    assert _hours(p.to_dict(), {'unit_hours': .1})['effective_processing_hours'] is None
    reviewed = sample(p)
    assert not reviewed['eligible'] and reviewed['report_refs'] == [] and reviewed['effective_processing_hours'] is None
    codes = {reason['code'] for reason in reviewed['exclusion_reasons']}
    # 没有有效报工时只给一条缺报工原因，不再叠加 operation_not_complete（见 calibration_samples._execution_reasons）。
    assert 'production_reports_missing' in codes and 'operation_not_complete' not in codes
    assert restore_execution_projections([p.to_dict()])[0] == p


def test_pre_void_snapshot_shape_has_only_explicit_empty_audit_upgrade(ledger_case):
    case = ledger_case
    case.install()
    report(case)
    p = case.ledger.get_task(case.task(1, case.op_id))
    old = p.to_dict()
    del old['voided_reports']
    restored = restore_execution_projections([old])[0]
    assert restored == p and restored.voided_reports == []


def test_candidate_baseline_reprojects_its_captured_voids_not_current_reports(candidate_case):
    case = candidate_case
    original_plan(case)
    row = case.command('create', case.task(7, case.op_id), case.values(1))['data']['rows'][0]
    case.command('report_void', row['report_ref'], intent(row))
    _, refs = compute(case)
    original = baseline(case, refs[0])
    item = original[0]['comparisons'][0]
    assert item['execution_at_generation']['execution_state'] == 'unreported'
    assert item['execution_at_generation']['known_completed_quantity'] == 0
    assert not item['execution_affected']
    case.command('create', case.task(7, case.op_id), case.values(1))
    assert baseline(case, refs[0]) == original


def test_previously_adopted_calibration_sample_is_a_visible_void_dependency(ready_adoption_case):
    case = ready_adoption_case
    row = case.reports[-1]
    preview = case.writer.preview('report_void', row['report_ref'], intent(row))
    assert preview['can_confirm']
    service(case.conn).confirm(case.template_ref, token(case), KEY, INTENT)
    blocked = case.writer.preview('report_void', row['report_ref'], intent(row))
    assert not blocked['can_confirm']
    impact = next(item for item in blocked['downstream_impacts'] if item['code'] == 'adopted_quota_report_required')
    assert impact['template_operation_ref'] == case.template_ref and impact['adoption_ref']
