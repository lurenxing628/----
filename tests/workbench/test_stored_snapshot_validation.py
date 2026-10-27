"""Stored JSON and DTO snapshots retain their exact rejection boundaries."""

from copy import deepcopy

import pytest

from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution import ExecutionProjection
from core.models.workbench_execution_input import MAX_OPERATIONS
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench.facts import run_input_codec
from core.services.workbench.facts.candidate_values import stored_json
from core.services.workbench.facts.run_input_codec import prepare_execution_projections, restore_execution_projections
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture  # noqa: F401


def test_stored_json_preserves_types_and_rejects_nested_duplicates_and_nonfinite_values():
    value = stored_json('{"rows":[null,false,1,1.0,"1"],"nested":{"name":"中文"}}')
    assert [type(item) for item in value["rows"]] == [type(None), bool, int, float, str]
    assert value["nested"] == {"name": "中文"}
    assert stored_json('[null,false,1,1.0]', list) == [None, False, 1, 1.0]
    for invalid in (
        '{"a":1,"a":2}', '{"rows":[{"a":1,"a":2}]}', r'{"a":1,"\u0061":2}',
        '{"value":NaN}', '{"value":Infinity}', '{"value":-Infinity}', '{"value":1e999}', '{"rows":[-1e400]}',
        '[]', 'null', 'false', '1', '{', None, b'{}',
    ):
        with pytest.raises(WorkbenchCommandRejected) as error:
            stored_json(invalid)
        assert (error.value.code, error.value.status) == ("candidate_artifact_invalid", 500), invalid


def test_saved_execution_requires_exact_projection_and_report_fields(ledger_case):
    case = ledger_case
    task_ref = case.task(1, case.op_id)
    case.command("create", task_ref, case.values(2))
    original = case.task_projection(task_ref).to_dict()
    before = content_text(original)
    assert [row.to_dict() for row in restore_execution_projections([original])] == [original]
    assert content_text(original) == before
    legacy = dict(original)
    legacy.pop("voided_reports")
    assert restore_execution_projections([legacy])[0].voided_reports == []

    invalid = []
    for field in ("execution_state", "target_quantity"):
        row = deepcopy(original)
        row.pop(field)
        invalid.append(row)
    invalid.append(dict(original, unexpected="extra projection field"))
    report_missing = deepcopy(original)
    report_missing["reports"][0].pop("remark")
    invalid.append(report_missing)
    report_extra = deepcopy(original)
    report_extra["reports"][0]["unexpected"] = "extra report field"
    invalid.append(report_extra)
    for row in invalid:
        for decode in (prepare_execution_projections, restore_execution_projections):
            with pytest.raises(CandidateRunInputError) as error:
                decode([row])
            assert error.value.code == "execution_snapshot_invalid"
    for quantity in (True, 1.0):
        for decode in (prepare_execution_projections, restore_execution_projections):
            with pytest.raises(CandidateRunInputError) as error:
                decode([dict(original, target_quantity=quantity)])
            assert error.value.code == "execution_projection_type"


def test_prepared_execution_retains_all_fields_without_materializing_public_dtos(ledger_case, monkeypatch):
    case = ledger_case
    task_ref = case.task(1, case.op_id)
    created = case.command("create", task_ref, case.values(2))["data"]["rows"][0]
    case.command("correct", created["report_ref"], {"original_revision_ref": created["revision_ref"],
                 "completed_quantity": 3, "reason": "保留原修订链"})
    original = case.task_projection(task_ref).to_dict()
    before = content_text(original)
    calls = []
    for dto in (run_input_codec.ExecutionProjection, run_input_codec.ProductionReport):
        original_init = dto.__init__

        def observed(self, *args, _init=original_init, **kwargs):
            calls.append(type(self).__name__)
            _init(self, *args, **kwargs)

        monkeypatch.setattr(dto, "__init__", observed)
    prepared = prepare_execution_projections([original])
    assert calls == []
    row = prepared[0]
    values = dict(row, reports=[dict(report) for report in row["reports"]])
    assert content_text(values) == before
    restored = restore_execution_projections([original])
    assert calls == ["ProductionReport", "ExecutionProjection"]
    assert content_text(restored[0].to_dict()) == before
    assert content_text(original) == before


def _unreported_snapshot():
    return ExecutionProjection(
        operation_ref="1" * 48, current_task_ref=None, comparison_task_ref=None, plan_identity=None,
        target_quantity=3, target_basis="batch", known_completed_quantity=0, quantity_complete=True,
        unknown_record_count=0, records_complete=True, first_actual_start=None, confirmed_finish=None,
        execution_state="unreported", completion_basis=None, data_quality="complete", remaining_quantity=3,
    ).to_dict()


def test_worker_snapshot_restore_prepares_full_archived_scope_once_without_losing_rows(monkeypatch):
    original = _unreported_snapshot()
    payload = [dict(original, operation_ref=f"{index:048x}") for index in range(MAX_OPERATIONS + 1)]
    prepare = run_input_codec.prepare_execution_projections
    preparations = []

    def prepare_once(rows, *, max_operations):
        preparations.append((len(rows), max_operations))
        return prepare(rows, max_operations=max_operations)

    monkeypatch.setattr(run_input_codec, "prepare_execution_projections", prepare_once)
    restored = restore_execution_projections(payload)
    assert preparations == [(MAX_OPERATIONS + 1, None)]
    assert len(restored) == MAX_OPERATIONS + 1
    assert [row.operation_ref for row in restored] == [row["operation_ref"] for row in payload]
    assert all(type(row) is ExecutionProjection and row.remaining_quantity == 3 for row in restored)
    assert payload[0] == dict(original, operation_ref="0" * 48)
    with pytest.raises(CandidateRunInputError, match="工序执行快照条数超出上限或格式不对"):
        prepare(payload)


def test_worker_snapshot_restore_rejects_duplicate_operations_and_invalid_top_level():
    row = _unreported_snapshot()
    for payload in ([row, dict(row, operation_ref="2" * 48), row], [row, row]):
        with pytest.raises(CandidateRunInputError) as exc:
            restore_execution_projections(payload)
        assert exc.value.code == "execution_snapshot_invalid"
    for payload in (None, {}, (), "[]"):
        with pytest.raises(CandidateRunInputError) as exc:
            restore_execution_projections(payload)
        assert exc.value.code == "execution_snapshot_invalid"
    assert restore_execution_projections([]) == []
