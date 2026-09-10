"""FE-02: real decoding and rejection contracts, without static escape hatches."""

import math
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial import reject
from core.models.workbench_trial_codec import dump, fingerprint, load, load_object, require_object
from core.services.workbench import trial_base
from core.services.workbench.trial_adoption import WorkbenchTrialAdoptionService
from core.services.workbench.trial_capacity import _resource
from data.repositories.workbench_trial_raw_repo import WorkbenchTrialRawPlanRepository
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository
from tests.workbench.test_run_candidate_support import corrupt_update, edit_capture
from tests.workbench.trial_adoption_support import saved_scenario
from tests.workbench.trial_support import candidate, create, service, snapshot
from tests.workbench.trial_support import trial_case as trial_case


def test_lossless_nested_sqlite_snapshot_keeps_encoding_fingerprint_and_types():
    value = {"blob": b"\x00\xff", "rows": [None, True, 3, 3.0, -0.0, "2026-09-10"],
             "legacy_reals": {"positive": float("inf"), "negative": float("-inf"), "nan": float("nan")}}
    text = dump(value)
    restored = load_object(text, fingerprint(value))
    assert dump(restored) == text and fingerprint(restored) == fingerprint(value)
    assert type(restored["blob"]) is bytes and restored["blob"] == value["blob"]
    assert [type(item) for item in restored["rows"]] == [type(item) for item in value["rows"]]
    assert math.copysign(1, restored["rows"][4]) == -1
    assert math.isnan(restored["legacy_reals"]["nan"])


@pytest.mark.parametrize("value", [None, False, 0, 1.5, "text", [], [1], b"raw", float("inf")])
def test_scalar_codec_remains_lossless_but_object_reader_rejects_wrong_root(value):
    text = dump(value)
    assert dump(load(text)) == text
    with pytest.raises(WorkbenchCommandRejected) as error:
        load_object(text, fingerprint(value))
    assert error.value.code == "trial_snapshot_invalid"


@pytest.mark.parametrize("text,digest", [(None, None), (b"{}", None), ("{", None),
    ('{"$sqlite_blob":"!"}', None), ('{"$sqlite_real":"bad"}', None), ("{}", "wrong")])
def test_invalid_encoding_and_mismatched_fingerprint_are_rejected(text, digest):
    with pytest.raises(WorkbenchCommandRejected) as error:
        load_object(text, digest)
    assert error.value.code == "trial_snapshot_invalid"


def test_rejection_helpers_do_not_return_and_valid_objects_are_not_copied():
    original = {"tasks": []}
    assert require_object(original) is original
    with pytest.raises(WorkbenchCommandRejected) as error:
        reject("original_reason", "Original message", 422)
    assert error.value.code == "original_reason" and error.value.status == 422


@pytest.mark.parametrize("field", ["admission_json", "validation_json", "original_json", "current_json"])
def test_draft_object_columns_reject_scalar_without_writing(trial_case, field):
    case = trial_case
    draft = create(case)
    table = "WorkbenchTrialDrafts" if field in ("admission_json", "validation_json") else "WorkbenchTrialRows"
    values = {field: dump(7)}
    if field in ("admission_json", "original_json"):
        values[field.replace("_json", "_hash")] = fingerprint(7)
    sql = "UPDATE " + table + " SET " + ",".join(key + "=?" for key in values)
    corrupt_update(case.conn, table, sql, tuple(values.values()))
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchTrialRepository(case.conn).get(draft["draft_ref"])
    assert error.value.code == "trial_snapshot_invalid" and snapshot(case.conn) == before


@pytest.mark.parametrize("sql,params", [("SELECT 7 AS value", None), ("SELECT 7 AS value", ()),
    ("SELECT 7 AS value", {}), ("SELECT ? AS value", (7,)), ("SELECT :value AS value", {"value": 7})])
def test_raw_plan_params_follow_base_repository_contract(trial_case, sql, params):
    before = snapshot(trial_case.conn)
    assert WorkbenchTrialRawPlanRepository(trial_case.conn).fetchall(sql, params) == [{"value": 7}]
    assert snapshot(trial_case.conn) == before


@pytest.mark.parametrize("field,value", [("context_factory", None), ("context_factory", 1),
                                        ("context_validator", None), ("context_validator", {})])
def test_missing_authorization_callback_cannot_issue_write_context(trial_case, field, value):
    saved = saved_scenario(trial_case, changed=False)
    svc = WorkbenchTrialAdoptionService(trial_case.conn, integration_enabled=True,
        context_factory=lambda *args: {}, context_validator=lambda *args: None)
    setattr(svc, field, value)
    before = snapshot(trial_case.conn)
    with pytest.raises(RuntimeError, match="authorization callbacks"):
        svc._enabled()
    with pytest.raises(WorkbenchCommandRejected) as error:
        svc.preview(saved["scenario_ref"])
    assert error.value.code == "storage_failure" and snapshot(trial_case.conn) == before


def test_enabled_returns_the_exact_callbacks_checked():
    factory = lambda *args: {"write_token": "checked"}
    validator = lambda *args: None
    svc = WorkbenchTrialAdoptionService(None, integration_enabled=True,
                                       context_factory=factory, context_validator=validator)
    checked_factory, checked_validator = svc._enabled()
    assert checked_factory is factory and checked_validator is validator


def test_absent_plan_identity_rejects_before_source_lookup(trial_case, monkeypatch):
    monkeypatch.setattr(trial_base.WorkbenchPlanQueryService, "_selected",
                        lambda *args: (None, SimpleNamespace(plan_identity=None), None))
    before = snapshot(trial_case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        trial_base._plan(trial_case.conn, "f" * 48)
    assert error.value.code == "plan_unavailable" and snapshot(trial_case.conn) == before


@pytest.mark.parametrize("table", ["PartOperations", "ExternalGroups"])
def test_missing_candidate_table_rejects_without_substituting_current_facts(trial_case, table):
    intent = candidate(trial_case)
    edit_capture(trial_case, "facts_json", lambda facts: facts["tables"].pop(table))
    before = snapshot(trial_case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(trial_case.conn).preview_create(intent)
    assert error.value.code == "trial_base_incomplete" and snapshot(trial_case.conn) == before


@pytest.mark.parametrize("state", ["available", "empty", "unavailable"])
@pytest.mark.parametrize("point", [False, True])
def test_capacity_keeps_unknown_zero_and_point_semantics(state, point):
    start = datetime(2026, 9, 10, 8)
    end = start + timedelta(hours=2)
    calendar = {"state": "unavailable" if state == "unavailable" else "available",
                "windows": [{"start": start.isoformat(), "end": end.isoformat(),
                             "allow_normal": True, "allow_urgent": True}] if state == "available" else []}
    result = _resource("machine", "f" * 48, [(start, start if point else start + timedelta(hours=1))], calendar)
    assert result["utilization"] == ((0 if point else 0.5) if state == "available" else None)
    assert result["occupied_hours"] == (0 if point else 1)
    assert result["available_hours"] == (None if state == "unavailable" else 2 if state == "available" else 0)


@pytest.mark.parametrize("fault", [None, "identity", "sequence"])
def test_batch_predecessors_keep_order_and_explicit_rejection_issues(fault):
    ops = {key: {"id": key, "batch_id": "B1", "piece_id": None, "seq": key} for key in (3, 1, 2)}
    rows = [{"task_ref": str(key), "original": {"operation": ops[key], "predecessor_operation_refs": []}}
            for key in (3, 1, 2)]
    refs, issues = {key: str(key) for key in ops}, []
    if fault == "identity":
        del refs[1]
    elif fault == "sequence":
        ops[2]["seq"] = ops[1]["seq"]
    trial_base._predecessors(rows, ops, refs, issues)
    actual = {row["task_ref"]: row["original"]["predecessor_operation_refs"] for row in rows}
    assert actual == ({"1": [], "2": [], "3": []} if fault == "sequence" else
                      {"1": [], "2": [] if fault == "identity" else ["1"], "3": ["2"]})
    assert [item["code"] for item in issues] == ([] if fault is None else
                                               ["dependency_ambiguous" if fault == "sequence" else "dependency_identity_missing"])


@pytest.mark.parametrize("kind", ["root", "tasks", "task", "row_ref", "duplicate", "detail"])
def test_saved_scenario_rejects_wrong_shapes_and_duplicate_rows_without_repair(trial_case, kind):
    case = trial_case
    saved = saved_scenario(case, changed=False)
    value = dict(saved)
    if kind == "root":
        value = []
    elif kind == "tasks":
        value["tasks"] = 1
    elif kind == "task":
        value["tasks"] = [1]
    elif kind == "row_ref":
        value["tasks"] = [dict(saved["tasks"][0], row_ref=None)]
    elif kind == "duplicate":
        value["tasks"] = saved["tasks"] * 2
    else:
        corrupt_update(case.conn, "WorkbenchTrialScenarioRows",
                       "UPDATE WorkbenchTrialScenarioRows SET payload_json='7'")
    corrupt_update(case.conn, "WorkbenchTrialScenarios",
                   "UPDATE WorkbenchTrialScenarios SET snapshot_json=?,snapshot_hash=?",
                   (dump(value), fingerprint(value)))
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchTrialRepository(case.conn).scenario(saved["scenario_ref"])
    assert error.value.code == "trial_snapshot_invalid" and snapshot(case.conn) == before
