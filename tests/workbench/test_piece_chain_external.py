"""Real Greedy external groups cannot share a time block across pieces."""

import pytest

from core.services.workbench.run_worker import WorkbenchRunWorker
from tests.workbench.test_piece_chain_support import adopt_candidate, artifact, piece_layout
from tests.workbench.test_piece_chain_support import trial_case as trial_case  # noqa: F401
from tests.workbench.test_run_candidate_support import compute


@pytest.mark.parametrize("merged", [False, True])
def test_real_external_group_and_frozen_seeds_are_piece_local(trial_case, merged):
    case = trial_case
    ids = piece_layout(case, common=False)
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','Supplier','T1')")
    case.conn.execute("UPDATE BatchOperations SET source='external',supplier_id='S1',ext_days=0.25,"
                      "machine_id=NULL,operator_id=NULL")
    group = "G1" if merged else None
    if merged:
        case.conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) "
                          "VALUES ('G1','P1',20,30,'merged',0.25,'S1')")
    for seq in (20, 30):
        case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,ext_group_id) "
                          "VALUES ('P1',?,'T1','Turning','external','S1',0.25,?)", (seq, group))
    for index, piece in enumerate(("item-A", "item-B", "item-C")):
        ids[piece, 10] = case.operation(seq=10, piece_id=piece, op_code=piece + "-10", setup_hours=index,
                                       machine_id="M" + str(index + 1), operator_id="O" + str(index + 1))
    case.conn.commit()
    _, refs = compute(case)
    for ref in refs:
        rows = {row["op_id"]: row for row in artifact(case, ref)["results"]}
        assert len({rows[ids[piece, 20]]["start_time"] for piece in ("item-A", "item-B", "item-C")}) == 3
        for piece in ("item-A", "item-B", "item-C"):
            left, right = rows[ids[piece, 20]], rows[ids[piece, 30]]
            assert left["start_time"] == rows[ids[piece, 10]]["end_time"]
            assert (right["start_time"] == left["start_time"]) if merged else (right["start_time"] == left["end_time"])
            assert left["machine_id"] is None and left["operator_id"] is None
    adopt_candidate(case, refs[0])
    case.conn.execute("UPDATE Schedule SET lock_status='locked' WHERE op_id=?", (ids["item-B", 20],))
    case.conn.commit()
    accepted = case.accept(key="ef-frozen-external-run-0001")
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete", result
    adopt_candidate(case, result["candidates"][0]["candidate_ref"], "ef-frozen-external-adopt-0001")
