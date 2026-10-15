"""冻结窗口的当前计算下界、上界和分件前缀。"""

from datetime import datetime

from core.services.workbench.run.compute import compute_candidate_run
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged


def test_freeze_window_bounds(run_case):
    case = run_case
    ids = {"before": case.op_id}
    for batch in ("inside", "after"):
        case.batch(batch)
        ids[batch] = case.operation(batch)
    case.plan(1, list(ids.values()))
    for batch, start, end in (
        ("before", "2026-09-09 07:00:00", "2026-09-09 08:00:00"),
        ("inside", "2026-09-09 10:00:00", "2026-09-09 11:00:00"),
        ("after", "2026-09-10 08:00:00", "2026-09-10 09:00:00"),
    ):
        case.conn.execute("UPDATE Schedule SET start_time=?,end_time=? WHERE op_id=?", (start, end, ids[batch]))
    case.conn.commit()
    settings = case.settings("B1", "inside", "after", hold_window={"start": "2026-09-09T08:00", "end": "2026-09-10T08:00"})
    result = unchanged(case, lambda: compute_candidate_run(case.conn, settings, case.projections()))
    assert result.schedule_input.frozen_op_ids == {ids["inside"]}
    for payload in result.candidate_payloads.values():
        held = next(row for row in payload.schedule_rows if row.op_id == ids["inside"])
        assert (held.start_time, held.end_time) == (datetime(2026, 9, 9, 10), datetime(2026, 9, 9, 11))


def test_piece_batches_hold_only_the_covered_piece_and_common_work():
    """分件批次里，时段盖住 A 件的工序时，前道只算 A 件和共同工序；B 件排在后面的工序不算，整批不会因此被跳过。
    不分件的批次和原来一样：工序号不超过时段里最大号的全部工序。"""
    from types import SimpleNamespace as Op

    from core.services.scheduler.run.freeze_window_prefixes import prefix_op_ids_for_anchors, window_anchors_by_batch

    ops = [Op(id=1, batch_id="B1", seq=10, piece_id=None), Op(id=2, batch_id="B1", seq=20, piece_id="A"),
           Op(id=3, batch_id="B1", seq=30, piece_id="A"), Op(id=4, batch_id="B1", seq=20, piece_id="B"),
           Op(id=5, batch_id="B1", seq=30, piece_id="B"), Op(id=6, batch_id="B1", seq=40, piece_id=None)]
    anchors = window_anchors_by_batch({3: {}}, {op.id: op for op in ops})
    assert anchors == {"B1": {"A": 30}}
    assert prefix_op_ids_for_anchors(ops, "B1", anchors["B1"]) == [1, 2, 3]
    assert prefix_op_ids_for_anchors(ops, "B1", {None: 40}) == [1, 2, 3, 4, 5, 6]
    plain = [Op(id=index, batch_id="B2", seq=index * 10, piece_id=None) for index in (1, 2, 3)]
    assert prefix_op_ids_for_anchors(plain, "B2", {None: 20}) == [1, 2]
