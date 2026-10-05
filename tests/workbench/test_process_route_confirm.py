"""Route changes require acknowledgement before discarding an outsourcing group."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.process.mutations import WorkbenchProcessMutationService
from tests.workbench.process_commands_support import (
    group_rows,
    identity_for,
    op_ref,
    op_rows,
    ref_for,
    route_input,
    run_stage,
    stage_database,
    storage,
)
from tests.workbench.process_route_support import read_only_probe

_stage_fixture = stage_database


@pytest.mark.parametrize("change", ("remove",))
def test_group_impact_is_readonly_and_exact_ack_is_required(stage_conn, change):
    if change in ("insert_in_range", "restore"):
        stage_conn.execute("UPDATE ExternalGroups SET end_seq=25 WHERE group_id='PROC-G'")
    if change == "restore":
        stage_conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,source,status,ext_group_id) VALUES ('PROC-001',25,'历史','external','deleted','PROC-G')")
    stage_conn.commit()
    text = {"remove": "10车削30检验", "rename": "10车削20改名30检验", "insert_in_range": "10车削20热处理25新序30检验", "restore": "10车削20热处理25历史30检验"}[change]
    payload = route_input(stage_conn, text)
    del payload["discard_group_refs"]
    before = storage(stage_conn)
    service = WorkbenchProcessMutationService(stage_conn)
    with read_only_probe(stage_conn):
        affected = service.affected_groups("route_confirm", payload, identity_for(stage_conn))
    assert affected == [ref_for(stage_conn, "template_external_group", "PROC-G")] and storage(stage_conn) == before
    for acknowledgement in ([],):
        with pytest.raises(WorkbenchCommandRejected):
            run_stage(stage_conn, "route_confirm", {**payload, "discard_group_refs": acknowledgement})
        assert storage(stage_conn) == before
    old, old_ref = op_rows(stage_conn), op_ref(stage_conn, 20)
    run_stage(stage_conn, "route_confirm", {**payload, "discard_group_refs": affected})
    assert group_rows(stage_conn) == {}
    assert op_rows(stage_conn)[20] == {**old[20], "ext_group_id": None,
        **({"status": "deleted"} if change == "remove" else {"op_type_name": "改名"} if change == "rename" else {})}
    assert op_ref(stage_conn, 20) == old_ref
