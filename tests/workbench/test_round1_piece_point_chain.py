"""Managed worker -> adopted points -> trial -> re-adoption -> new connection."""

from contextlib import closing

from core.infrastructure.database import get_connection
from core.services.workbench.plan_point_evidence import official_point_work
from tests.workbench.ea_zero_duration_support import adoption_service, trial_adoption_service
from tests.workbench.test_round1_piece_point_support import (
    adopt,
    artifact,
    candidate,
    layout,
    operation_ref,
    workspace,
)
from tests.workbench.test_round1_piece_point_support import point_case as point_case
from tests.workbench.test_run_candidate_adoption_support import INTENT
from tests.workbench.trial_support import change, create, service, snapshot
from tests.workbench.trial_support import trial_case as trial_case


def test_managed_mixed_piece_points_adopt_move_save_read_and_recover(point_case):
    case = point_case
    ids = layout(case)
    ref = candidate(case)
    payload = artifact(case, ref)["validated_payload"]["schedule_rows"]
    assert {row["op_id"] for row in payload} == set(ids.values())
    points = {row["op_id"] for row in payload if row["start_time"] == row["end_time"]}
    assert points == {op_id for (_, seq), op_id in ids.items() if seq in (20, 40, 50)}
    first = adopt(case, ref)
    plan = first["data"]["official_plan"]
    original = workspace(case.conn, plan["plan_ref"])
    work = official_point_work(case.conn, plan["version"])
    for (piece, seq), op_id in ids.items():
        if op_id in points:
            assert work[op_id]["witness"].quantity == (1 if piece else 3)
            assert work[op_id]["operation"]["piece_id"] == piece
            assert work[op_id]["execution"]["operation_ref"] == operation_ref(case, op_id)
    moved_ref = operation_ref(case, ids["item-B", 50])
    draft = create(case, {"base": {"plan_ref": plan["plan_ref"]}}, key="r1a-trial-create-0001")
    assert draft["validation"]["constraints_status"] == "valid", draft["validation"]
    index = next(i for i, task in enumerate(draft["tasks"]) if task["operation_ref"] == moved_ref)
    changed = change(case, draft, task=index, start="2026-09-09T13:00:00", key="r1a-trial-move-0001")["data"]
    assert changed["validation"]["constraints_status"] == "valid", changed["validation"]
    saved = service(case.conn).save(changed["draft_ref"], {"name": "R1-A piece point"},
        changed["write_context"]["write_token"], "r1a-trial-save-0001")["data"]
    second = adopt(case, saved["scenario_ref"], trial=True, key="r1a-adopt-trial-0001")
    second_plan = second["data"]["official_plan"]
    assert second_plan["source_scenario_ref"] == saved["scenario_ref"]
    with closing(get_connection(str(case.path))) as reopened:
        recovered = workspace(reopened, second_plan["plan_ref"])
        assert {task["operation_ref"] for task in recovered["tasks"]} == {
            task["operation_ref"] for task in original["tasks"]}
        moved = next(task for task in recovered["tasks"] if task["operation_ref"] == moved_ref)
        assert moved["start"] == moved["end"] == "2026-09-09T13:00:00"
        assert moved["event_kind"] == "point" and moved["occupies_resources"] is False
        assert recovered["projections"]["baseline"]["state"] == "available"
        before = snapshot(reopened)
        for svc, source, key, receipt in (
                (adoption_service, ref, "r1a-adopt-candidate-0001", first),
                (trial_adoption_service, saved["scenario_ref"], "r1a-adopt-trial-0001", second)):
            replay = svc(reopened).adopt(source, "expired", key, INTENT)
            assert replay["replayed"] and replay["receipt_ref"] == receipt["receipt_ref"]
        assert snapshot(reopened) == before
        assert reopened.execute("SELECT version FROM SchemaVersion").fetchone()[0] == 31
        assert not reopened.execute("PRAGMA foreign_key_check").fetchall()
