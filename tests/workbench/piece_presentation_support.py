"""Build real piece candidates shared by downstream API tests."""

from tests.workbench.piece_chain_support import piece_layout
from tests.workbench.plan_catalog_support import candidate, scenario
from tests.workbench.run_candidate_support import compute

PIECES = ("第一件主体多字中文业务编号甲", "第二件主体多字中文业务编号乙", "第三件主体多字中文业务编号丙")


def real_case(case):
    ids = piece_layout(case)
    for old, new in zip(("item-A", "item-B", "item-C"), PIECES):
        case.conn.execute("UPDATE BatchOperations SET piece_id=? WHERE piece_id=?", (new, old))
    case.batch("B2", quantity=1)
    case.operation(batch="B2", seq=10, unit_hours=.5)
    case.conn.commit()
    for version in (1, 2, 3, 4):
        case.plan(version, [ids[None, 10]], end="2026-09-09T08:45:00")
    candidate(case.conn, 3, "critical_best", op_id=ids[None, 10])
    scenario(case.conn, "es-original-scene", 3, op_id=ids[None, 10])
    case.conn.commit()
    receipt = case.command("create", case.task(4, ids[None, 10]), case.values(
        3, actual_end="2026-09-09T08:45:00", effective_processing_hours=.75))
    assert receipt["ok"], receipt
    return ids, compute(case, case.settings("B1", "B2"))
