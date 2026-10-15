"""Complete-plan task identities survive reordering, filters and role selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.services.common.plan_query import SchedulePlanQueryService
from core.services.common.plan_task_identity import assign_task_ids, public_task_id, row_identity
from core.services.scheduler._sched_display_utils import bad_time_row_sample
from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.operation_execution.operation_execution_state_revision_support import _connect, _seed_plan
from tests.workbench.plan_catalog_support import candidate, selection

_PLAN_IDENTITY = {"version": 1, "effective_plan_role": "adopted", "source_table": "schedule"}


def _full_plan_rows(rows):
    return assign_task_ids(rows, plan_identity=_PLAN_IDENTITY)


def test_task_identity_rejects_invalid_unicode_in_public_source():
    with pytest.raises(UnicodeEncodeError):
        _full_plan_rows([{"op_code": "OP\ud80010", "batch_id": "B001", "piece_id": "P1", "seq": 10}])


def test_task_identity_distinguishes_rows_and_keeps_internal_keys_out_of_public_ids():
    base = {"op_code": "OP,10 / 首件", "batch_id": "B001", "piece_id": "P1", "seq": 10}
    rows = _full_plan_rows([dict(base, schedule_id=999991, op_id=999991),
                            dict(base, schedule_id=999992, op_id=999992)])
    ids = [public_task_id(row) for row in rows]
    assert len(set(ids)) == 2
    assert all("999991" not in value and "999992" not in value for value in ids)
    assert all("," not in value and "/" not in value for value in ids)
    without_code = _full_plan_rows([dict(base, op_code="", op_id="INTERNAL-OP-ID-987654")])[0]
    assert without_code["task_id"].startswith("task_B001_")
    assert "INTERNAL-OP-ID" not in without_code["task_id"]


def test_row_identity_distinguishes_same_operation_and_time_on_different_resources():
    base = {"op_id": "INTERNAL-OP-ID-987654", "start_time": "2026-05-04 08:00:00",
            "end_time": "2026-05-04 10:00:00"}
    keys = {row_identity(dict(base, machine_id=machine, operator_id=operator))
            for machine, operator in (("M1", "O1"), ("M2", "O2"), ("M2", "O1"), ("M1", "O2"))}
    assert len(keys) == 4


def test_complete_plan_ids_preserve_cold_order_and_existing_references():
    base = {"op_code": "", "piece_id": "P1", "seq": 10,
            "start_time": "2026-05-04 08:00:00", "end_time": "2026-05-06 10:00:00",
            "operator_id": "OP001"}
    permanent_ref = "a" * 48
    full_source = [
        dict(base, schedule_id=991, op_id=999991, batch_id="B001", machine_id="MC001"),
        dict(base, schedule_id=701, op_id=999701, batch_id="B002", machine_id="MC002",
             task_id="task_original_issued", task_ref="b" * 48),
        dict(base, schedule_id=801, op_id=999801, batch_id="B003", machine_id="MC002",
             public_task_id="task_original_public"),
        dict(base, schedule_id=901, op_id=999901, batch_id="B004", machine_id="MC001", task_ref=permanent_ref),
    ]
    assigned = _full_plan_rows(full_source)
    expected = {row["schedule_id"]: row["task_id"] for row in assigned}
    cold = _full_plan_rows([dict(row) for row in reversed(full_source)])
    assert {row["schedule_id"]: row["task_id"] for row in cold} == expected
    assert assigned[1]["task_id"] == "task_original_issued"
    assert assigned[1]["task_ref"] == full_source[1]["task_ref"]
    assert assigned[2]["task_id"] == full_source[2]["public_task_id"]
    assert assigned[3]["task_id"] == "task_" + permanent_ref
    assert assigned[3]["task_ref"] == permanent_ref
    assert "task_id" not in full_source[0]


def test_selected_plan_roles_keep_their_own_permanent_task_references(tmp_path: Path):
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        candidate(conn, 1, "adopted", source="schedule")
        shared = candidate(conn, 1, "baseline_best", op_id=10)
        selection(conn, 1, "critical_best", shared, source="candidate_rows")
        conn.commit()
        scope = {"version": 1, "source_table": "candidate_rows", "candidate_id": shared}
        source_rows = SchedulePlanQueryRepository(conn).list_detail_rows_all(**scope)
        references = WorkbenchPlanIdentityRepository(conn)
        roles = ("baseline_best", "critical_best")
        plans = {role: references.get_plan_ref(WorkbenchPlanLocator(1, role)) for role in roles}
        expected_ids = {
            role: {row_id: "task_" + task_ref for row_id, task_ref in
                   references.get_task_refs(plans[role], source_rows).items()} for role in roles}
        assert plans[roles[0]] != plans[roles[1]]
        assert expected_ids[roles[0]] != expected_ids[roles[1]]
        query = SchedulePlanQueryService(conn)
        for role in roles:
            rows = query.public_task_rows_for_resolution(**scope, effective_plan_role=role)
            assert {row["schedule_id"]: row["task_id"] for row in rows} == expected_ids[role]
        with pytest.raises(ValueError, match="多个角色"):
            query.public_task_rows_for_resolution(**scope)
        for role in roles:
            rows = query.public_task_rows_for_resolution(**scope, plan_ref=plans[role])
            assert {row["schedule_id"]: row["task_id"] for row in rows} == expected_ids[role]
            assert (query.task_id_for_row(source_rows[0], **scope, plan_ref=plans[role])
                    == expected_ids[role][source_rows[0]["schedule_id"]])
            rows = query.list_plan_detail_rows_all(version=1, role=role)
            assert {row["schedule_id"]: row["task_id"] for row in rows} == expected_ids[role]
        with pytest.raises(ValueError, match="角色"):
            query.public_task_rows_for_resolution(**scope, effective_plan_role="critical_best",
                                                  plan_ref=plans["baseline_best"])
    finally:
        conn.close()


def test_bad_time_sample_keeps_public_location_and_hides_raw_time_and_internal_ids():
    row = _full_plan_rows([{"schedule_id": 17, "op_id": 23, "op_code": "OP-B001-10", "batch_id": "B001",
                            "start_time": "2026-03-02 99:00:00", "end_time": "2026-03-02 13:00:00"}])[0]
    sample = bad_time_row_sample(row)
    assert sample is not None
    assert "工序编码=OP-B001-10" in sample and "批次号=B001" in sample and "字段=开始时间" in sample
    assert all(value not in sample for value in ("排程记录编号=17", "工序编号=23", "99:00:00", "start_time", "end_time"))
