"""D05 arithmetic uses actual ledger DTOs; lineage is explicitly test-asserted."""

from dataclasses import replace

import pytest

from core.models.workbench_calibration import CalibrationCandidate, CalibrationLineage, CalibrationQuery
from core.services.workbench.calibration import filtered_suggestions
from core.services.workbench.calibration_method import build_suggestion, summarize_samples
from core.services.workbench.calibration_samples import review_sample
from tests.workbench.calibration_support import calibration_case as case_fixture
from tests.workbench.calibration_support import complete_reports, ledger_fixture, reviewed
from tests.workbench.execution_ledger_support import NOW


@pytest.mark.parametrize("count", [0, 1, 4, 5, 20, 25])
def test_minimum_latest_twenty_and_median(calibration_case, count):
    case = calibration_case
    values = [index / 100 for index in range(1, count + 1)]
    samples = reviewed(case, complete_reports(case, values)[0]) if count else []
    summary = summarize_samples(samples)
    assert summary["sample_count"] == min(count, 20)
    assert summary["eligible_sample_count"] == count
    assert summary["suggested_unit_hours"] == (None if count < 5 else pytest.approx((values[-min(count, 20)] + values[-1]) / 2))
    assert sum(row["selected"] for row in samples) == min(count, 20)
    if count == 25:
        assert all(row["exclusion_reasons"][0]["code"] == "outside_recent_20" for row in samples[:5])


@pytest.mark.parametrize("old,suggested,expected", [(1, 1.2, False), (1, 1.200001, True),
    (1, .8, False), (1, .799999, True), (1, 0, True), (0, 1, False), (None, 1, False), (1e-310, 1, True)])
def test_strict_absolute_twenty_and_zero_unknown(calibration_case, old, suggested, expected):
    case = calibration_case
    template = replace(case.template, old_unit_hours=old)
    rows = reviewed(case, complete_reports(case, [suggested] * 5)[0], template=template)
    result = build_suggestion(template, summarize_samples(rows), generated_at=NOW.isoformat())
    assert result["suggested_unit_hours"] == suggested
    assert result["over_20_percent"] is expected
    if old in (0, None) or old == 1e-310:
        assert result["deviation_percent"] is None
    assert result["capabilities"]["adopt"] is False and result["capabilities"]["lock"] is False
    assert result["write_context"]["capabilities"] == [] and result["write_context"]["write_token"] is None


def test_sample_is_hour_sum_divided_by_quantity_not_record_average(calibration_case):
    case = calibration_case
    case.plan(2, [case.op_id])
    task = case.task(2, case.op_id)
    case.command("create", task, case.values(4, effective_processing_hours=1))
    case.command("create", task, case.values(6, effective_processing_hours=0,
                 actual_start="2026-09-09T10:00:00", actual_end="2026-09-09T11:00:00"))
    sample = reviewed(case, [case.op_id])[0]
    assert sample["unit_hours"] == .1 and sample["completed_quantity"] == 10
    assert sample["effective_processing_hours"] == 1 and sample["eligible"]
    assert len(sample["reports"]) == 2 and len(sample["report_revision_refs"]) == 2


@pytest.mark.parametrize("patch,code", [({"effective_processing_hours": None}, "processing_hours_unknown"),
    ({"completed_quantity": None}, "quantity_unknown"), ({"completed_quantity": 0}, "quantity_not_positive"),
    ({"completed_quantity": 9}, "operation_not_complete"), ({"actual_machine_ref": None}, "execution_data_incomplete")])
def test_missing_zero_and_partial_are_not_samples(calibration_case, patch, code):
    case = calibration_case
    case.plan(2, [case.op_id])
    case.command("create", case.task(2, case.op_id), {**case.values(10), **patch})
    sample = reviewed(case, [case.op_id])[0]
    assert not sample["eligible"]
    assert code in {row["code"] for row in sample["exclusion_reasons"]}


@pytest.mark.parametrize("kind", ["missing", "revision", "operation", "unconfirmed", "external"])
def test_no_guessed_template_binding(calibration_case, kind):
    case = calibration_case
    complete_reports(case, [.1])
    projection = case.ledger.get_task(case.task(2, case.op_id))
    template = case.template
    lineage = CalibrationLineage(template.operation_ref, template.revision, "test-origin")
    if kind == "missing":
        lineage = None
    elif kind == "revision":
        lineage = replace(lineage, template_revision=template.revision + 1)
    elif kind == "operation":
        lineage = replace(lineage, template_operation_ref="f" * 48)
    elif kind == "unconfirmed":
        lineage = replace(lineage, evidence_ref="")
    else:
        template = replace(template, source="external")
    sample = review_sample(CalibrationCandidate(projection, "P1", "B1", "OP1", "internal", lineage), template=template, as_of=NOW)
    assert not sample["eligible"] and summarize_samples([sample])["sample_count"] == 0


@pytest.mark.parametrize("event_type,code", [("pause", "pause_contamination"), ("exception", "known_exception")])
def test_actual_legacy_pause_and_exception_excluded(calibration_case, event_type, code):
    case = calibration_case
    ids, _ = complete_reports(case, [.1])
    case.event(case.op_id, "start", version=2)
    case.event(case.op_id, event_type, version=2, time="2026-09-09T08:30:00")
    if event_type == "pause":
        case.event(case.op_id, "resume", version=2, time="2026-09-09T09:00:00")
    sample = reviewed(case, ids)[0]
    assert not sample["eligible"] and code in {row["code"] for row in sample["exclusion_reasons"]}
    assert sample["legacy_facts"]


def test_remark_keywords_are_not_anomaly_evidence(calibration_case):
    case = calibration_case
    ids, reports = complete_reports(case, [.1])
    report = reports[0]
    case.command("correct", report["report_ref"], {"original_revision_ref": report["revision_ref"], "reason": "verified note",
                                                "remark": "异常/暂停 are words, not structured facts"})
    sample = reviewed(case, ids)[0]
    assert sample["eligible"] and len(sample["reports"][0]["correction_history"]) == 2


def test_newest_invalid_does_not_displace_older_valid_twenty(calibration_case):
    case = calibration_case
    ids, _ = complete_reports(case, [.1] * 25)
    samples = reviewed(case, ids)
    for sample in samples[-3:]:
        sample["eligible"] = False
        sample["exclusion_reasons"] = [{"code": "test_known_exception", "message": "test-only exclusion"}]
    summary = summarize_samples(samples)
    assert summary["eligible_sample_count"] == 22 and summary["sample_count"] == 20
    assert samples[2]["selected"] and not samples[-1]["selected"]


def test_outlier_uses_median_not_mean(calibration_case):
    case = calibration_case
    samples = reviewed(case, complete_reports(case, [.1, .1, .2, .3, 2])[0])
    assert summarize_samples(samples)["suggested_unit_hours"] == .2


def test_deviation_filter_excludes_exact_twenty_and_unknown_base(calibration_case):
    case = calibration_case
    samples = reviewed(case, complete_reports(case, [1.2] * 5)[0])
    summary = summarize_samples(samples)
    rows = [build_suggestion(replace(case.template, old_unit_hours=old), summary, generated_at=NOW.isoformat())
            for old in (1, .5, 0, None)]
    selected = filtered_suggestions(rows, CalibrationQuery(deviation="over_20_percent"))
    assert len(selected) == 1 and selected[0]["old_unit_hours"] == .5


def test_duplicate_execution_instance_is_not_counted_twice(calibration_case):
    case = calibration_case
    sample = reviewed(case, complete_reports(case, [.1])[0])[0]
    with pytest.raises(ValueError, match="重复"):
        summarize_samples([sample, sample])
