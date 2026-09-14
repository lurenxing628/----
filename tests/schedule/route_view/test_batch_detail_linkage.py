"""批次联动和排程去向保留真实来源及公开投影；旧模板退役，不复原脚本或伪造 HTML。"""

from __future__ import annotations

import json
from contextlib import closing
from urllib.parse import parse_qs, urlsplit

from core.infrastructure.database import get_connection
from tests._support.gantt_retirement import _business_state
from tests._support.schedule_retirement import assert_retired_scope, capture_schedule_context, initialize_read_fixture
from web.viewmodels.scheduler_batch_schedule_placement import build_schedule_placement


def _seed_linkage(client):
    """Seed one real batch and its authorized machine/operator pair."""
    from core.services.scheduler.config.config_service import ConfigService
    from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository

    initialize_read_fixture(client.application)
    with closing(get_connection(client.application.config["DATABASE_PATH"])) as conn:
        ConfigService(conn).set_prefer_primary_skill("yes")
        conn.executescript("""
            INSERT INTO Parts(part_no,part_name) VALUES ('P-LINK','联动零件');
            INSERT INTO Machines(machine_id,name,status) VALUES ('MC1','Machine1','active');
            INSERT INTO Operators(operator_id,name,status) VALUES ('OP1','Operator1','active');
            INSERT INTO OperatorMachine(operator_id,machine_id,is_primary,skill_level)
                VALUES ('OP1','MC1','yes','expert');
            INSERT INTO Batches(batch_id,part_no,quantity,status,ready_status)
                VALUES ('B_TEST','P-LINK',1,'pending','yes');
            INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,machine_id,operator_id,setup_hours)
                VALUES ('OP-LINK','B_TEST',1,'OT','internal','MC1','OP1',1);
        """)
        conn.commit()
        op_id = conn.execute("SELECT id FROM BatchOperations WHERE op_code='OP-LINK'").fetchone()[0]
        identity = WorkbenchIdentityRepository(conn).find_active("batch", "B_TEST")
        assert identity is not None
        ref = identity.ref
    return op_id, ref


def test_batch_detail_linkage(app_client) -> None:
    from core.services.equipment import MachineService
    from core.services.personnel import OperatorService
    from web.routes.domains.scheduler.scheduler_batch_detail import _build_machine_options, _build_operator_options
    from web.routes.domains.scheduler.scheduler_ops import _operation_id_from_token

    client = app_client
    op_id, ref = _seed_linkage(client)
    before = _business_state(client)
    context = capture_schedule_context(
        client, endpoint="scheduler.batch_detail", path="/scheduler/batches/B_TEST?lazy_select=1",
        template="scheduler/batch_detail.html", path_values={"batch_id": "B_TEST"},
    )
    assert context["batch"]["batch_id"] == "B_TEST"
    assert [row["id"] for row in context["operations"]] == [op_id]
    assert context["machine_operators"] == {"MC1": ["OP1"]}
    assert context["operator_machines"] is None
    assert context["machine_operator_meta"]["MC1"]["OP1"] == {"is_primary": "yes", "skill_level": "expert"}
    assert context["lazy_select_enabled"] is True
    operation, = context["operations"]
    action = context["operation_update_actions"][operation["form_key"]]
    assert urlsplit(action).path.startswith("/scheduler/ops/update-token/")
    with client.application.app_context():
        assert _operation_id_from_token(urlsplit(action).path.rsplit("/", 1)[1]) == op_id

    with closing(get_connection(client.application.config["DATABASE_PATH"])) as conn:
        machines = _build_machine_options(MachineService(conn), {"MISSING_MC"})
        operators = _build_operator_options(OperatorService(conn), {"MISSING_OP"})
    for rows, missing in ((machines, "MISSING_MC"), (operators, "MISSING_OP")):
        orphan, = [row for row in rows if row["value"] == missing]
        assert orphan == {"value": missing, "label": missing + "（已删除）", "disabled": True, "orphan": True}

    assert_retired_scope(client, "/scheduler/batches/B_TEST?lazy_select=1", message="没有跳转，也没有丢掉任何条件")
    response = client.get("/scheduler/batches/B_TEST")
    assert response.status_code == 302
    target = response.headers["Location"]
    navigation = json.loads(parse_qs(urlsplit(target).query)["nav"][0])
    assert navigation == {"version": 1, "view": "batches", "context": {"entity_ref": ref}}
    detail = client.get("/api/workbench/v1/entities/batch/" + ref)
    assert detail.status_code == 200, detail.get_data(as_text=True)
    assert detail.get_json()["data"]["ref"] == ref
    assert detail.get_json()["data"]["business_code"] == "B_TEST"
    assert _business_state(client) == before


def _placement_row(machine="M1 设备1", operator="O1 人员1"):
    """Public row inputs retain no-record and external-resource display values."""
    return {
        "op_label": "OP10", "plan_machine_label": machine, "plan_operator_label": operator,
        "execution_status_label": "待开工", "actual_start_time_label": "暂无实际开工",
        "actual_end_time_label": "暂无实际完工", "actual_summary_label": "暂未记录现场实际",
        "has_execution_record": False,
    }


def test_batch_detail_schedule_placement_ok_renders_card(app_client) -> None:
    row = _placement_row()
    notice = "有 1 条排程记录的开始或结束时间缺失或写法不对，时间跨度只按可解析记录计算；已排工序数量仍是全量。"
    with app_client.application.test_request_context("/scheduler/batches/B_TEST"):
        placement = build_schedule_placement(
            state="ok", batch_id="B_TEST", version=8, op_count=1, op_rows=[row],
            span_from_date="2026-06-01", span_to_date="2026-06-01",
            span_label="2026年6月1日 08:00 ～ 2026年6月1日 12:00",
            span_status="partial", span_bad_time_count=1, span_notice=notice,
            generated_at="2026-06-01 08:00:00", strategy="priority_first", history_present=True,
        )
    assert placement["state"] == "ok" and placement["version_label"] == "v8"
    assert placement["op_count"] == 1 and placement["op_rows"] == [row]
    assert placement["op_rows"][0]["actual_summary_label"] == "暂未记录现场实际"
    assert placement["op_rows"][0]["has_execution_record"] is False
    assert placement["span_notice"] == notice and placement["span_bad_time_count"] == 1
    link = placement["gantt_link"]
    assert not link["disabled"] and link["label"] == "在甘特中定位本批次"
    query = parse_qs(urlsplit(link["url"]).query)
    assert query["version"] == ["8"]
    assert query["gantt_batch"] == ["B_TEST"]
    assert query["start_date"] == ["2026-06-01"] and query["end_date"] == ["2026-06-01"]


def test_batch_detail_schedule_placement_disabled_link_and_empty_states(app_client) -> None:
    external = _placement_row("外协 鑫源机械", "外协/未分配")
    with app_client.application.test_request_context("/scheduler/batches/B_TEST"):
        disabled = build_schedule_placement(
            state="ok", batch_id="B_TEST", version=8, op_count=1, op_rows=[external],
            span_label="时间记录异常", span_status="invalid",
        )
        not_placed = build_schedule_placement(state="not_placed")
    assert disabled["state"] == "ok" and disabled["op_rows"] == [external]
    assert disabled["op_rows"][0]["plan_machine_label"] == "外协 鑫源机械"
    assert disabled["gantt_link"]["disabled"] is True and not disabled["gantt_link"]["url"]
    assert not_placed["state"] == "not_placed"
    assert not_placed["message"] == "本批次未排入最新方案"
    assert not_placed["op_count"] == 0 and not_placed["op_rows"] == []
    assert not_placed["gantt_link"] is None
