"""回归测试：批次详情路由 /scheduler/batches/<batch_id> 全程从 g.services 取 batch/schedule/machine/operator/supplier 等请求级服务，组装出含批次信息、工序、设备/人员下拉选项的渲染上下文（machine_options/operator_options 的 value 为对应 id）。"""

from __future__ import annotations

from types import SimpleNamespace

from flask import Flask, g


class _Model(SimpleNamespace):
    def to_dict(self):
        return dict(self.__dict__)


def _build_app(monkeypatch):
    import web.routes.domains.scheduler.scheduler_batch_detail as route_mod

    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    app = Flask(__name__)
    app.secret_key = "aps-batch-detail-route"
    app.register_blueprint(route_mod.bp, url_prefix="/scheduler")
    return app


def test_scheduler_batch_detail_route_uses_request_services(monkeypatch) -> None:
    app = _build_app(monkeypatch)
    client = app.test_client()

    batch = _Model(
        batch_id="B001",
        part_no="P001",
        quantity=1,
        status="pending",
        priority="normal",
        ready_status="yes",
        remark=None,
    )
    op = _Model(
        id=1,
        batch_id="B001",
        source="internal",
        machine_id="M1",
        operator_id="O1",
        supplier_id=None,
    )
    machine = _Model(machine_id="M1", name="设备1", status="active")
    operator = _Model(operator_id="O1", name="人员1", status="active")
    supplier = _Model(supplier_id="S1", name="供应商1", status="active")

    services = SimpleNamespace(
        batch_service=SimpleNamespace(get=lambda batch_id: batch),
        schedule_service=SimpleNamespace(
            list_batch_operations=lambda batch_id: [op],
            get_external_merge_hint=lambda _op_id: None,
        ),
        machine_service=SimpleNamespace(
            list=lambda status=None: [machine],
            get_optional=lambda _mid: None,
        ),
        operator_service=SimpleNamespace(
            list=lambda status=None: [operator],
            get_optional=lambda _oid: None,
        ),
        supplier_service=SimpleNamespace(
            list=lambda status=None: [supplier],
            get_optional=lambda _sid: None,
        ),
        config_service=SimpleNamespace(get_snapshot=lambda: SimpleNamespace(prefer_primary_skill="yes")),
        operator_machine_query_service=SimpleNamespace(
            list_simple_rows_for_machine_operator_sets=lambda _machines, _operators: [
                {"machine_id": "M1", "operator_id": "O1", "skill_level": "normal", "is_primary": "yes"}
            ]
        ),
        # 排程去向卡只需无版本即落 no_official_plan 清爽态——本用例只验资源选项装配，
        # 给 get_latest_version→0 stub 避免新增取数段落 error 兜底每跑记一条 AttributeError 栈。
        schedule_history_query_service=SimpleNamespace(get_latest_version=lambda: 0),
    )

    @app.before_request
    def _inject_services() -> None:
        g.services = services
        g.app_logger = app.logger
        g.op_logger = None

    response = client.get(
        "/scheduler/batches/B001",
        query_string={"next": "/scheduler/batches?status=&page=2"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["batch"]["batch_id"] == "B001"
    assert payload["operations"][0]["machine_id"] == "M1"
    assert payload["machine_options"][0]["value"] == "M1"
    assert payload["operator_options"][0]["value"] == "O1"
    # get_latest_version→0 显式落 no_official_plan 诚实空态（非 error 兜底）——把早退分支从隐式
    # smoke 升为显式断言：若守卫回退到取数段会因缺 schedule_plan_query_service 走 error 态而此断言红。
    assert payload["schedule_placement"]["state"] == "no_official_plan"
    assert payload["batch_return_url"] == "/scheduler/batches?status=&page=2"
    assert payload["batch_return_next"] == "/scheduler/batches?status=&page=2"


def test_scheduler_batch_detail_renders_schedule_placement_ok(monkeypatch) -> None:
    """排程去向卡正常态：stub 历史/计划服务 + g.db + 假 ExecutionFactProvider，
    验证 ok 态 op_rows 走单源 label、仅公开字段、定位甘特链接可用——不让绿建立在 error 兜底上。"""
    app = _build_app(monkeypatch)
    import web.routes.domains.scheduler.scheduler_batch_detail as route_mod

    class _FakeProvider:
        def __init__(self, *_a, **_k):
            pass

        def facts_by_op_id_for_plan_rows(self, rows, plan_fields, **kw):
            # 钉死 4.10 调用形态：路由须传完整计划身份的 plan_fields + 计划行带 schedule_id/version/
            # batch_id；只读卡不传 include_op_ids（缺事实工序走「暂未记录」而非 raise）。防未来改错。
            assert "include_op_ids" not in kw, "只读卡不应传 include_op_ids"
            assert set(plan_fields) == {"version", "source_table", "effective_plan_role", "scenario_id"}
            assert plan_fields["effective_plan_role"] == "adopted"
            assert all("schedule_id" in r and "version" in r and "batch_id" in r for r in rows)
            return {}  # 无事实 → 工序行走「暂未记录现场实际」

    monkeypatch.setattr(route_mod, "ExecutionFactProvider", _FakeProvider)

    client = app.test_client()
    batch = _Model(
        batch_id="B001", part_no="P001", quantity=1, status="scheduled",
        priority="normal", ready_status="yes", remark=None,
    )
    op = _Model(id=1, batch_id="B001", source="internal", machine_id="M1", operator_id="O1", supplier_id=None)
    machine = _Model(machine_id="M1", name="设备1", status="active")
    operator = _Model(operator_id="O1", name="人员1", status="active")
    supplier = _Model(supplier_id="S1", name="供应商1", status="active")
    resolution = SimpleNamespace(source_table="schedule", candidate_id=None, scenario_id=None, selected_role="adopted")
    plan_rows = [
        {
            "schedule_id": 100, "op_id": 1, "version": 8, "batch_id": "B001",
            "op_code": "OP10", "op_type_name": "车",
            "machine_id": "M1", "machine_name": "设备1",
            "operator_id": "O1", "operator_name": "人员1", "supplier_name": None,
            "start_time": "2026-06-01 08:00:00", "end_time": "2026-06-01 12:00:00",
        }
    ]

    services = SimpleNamespace(
        batch_service=SimpleNamespace(get=lambda batch_id: batch),
        schedule_service=SimpleNamespace(
            list_batch_operations=lambda batch_id: [op],
            get_external_merge_hint=lambda _op_id: None,
        ),
        machine_service=SimpleNamespace(list=lambda status=None: [machine], get_optional=lambda _mid: None),
        operator_service=SimpleNamespace(list=lambda status=None: [operator], get_optional=lambda _oid: None),
        supplier_service=SimpleNamespace(list=lambda status=None: [supplier], get_optional=lambda _sid: None),
        config_service=SimpleNamespace(get_snapshot=lambda: SimpleNamespace(prefer_primary_skill="yes")),
        operator_machine_query_service=SimpleNamespace(
            list_simple_rows_for_machine_operator_sets=lambda _m, _o: [
                {"machine_id": "M1", "operator_id": "O1", "skill_level": "normal", "is_primary": "yes"}
            ]
        ),
        schedule_history_query_service=SimpleNamespace(
            get_latest_version=lambda: 8,
            get_by_version=lambda _v: SimpleNamespace(schedule_time="2026-06-01 08:00:00", strategy="priority_first"),
        ),
        schedule_plan_query_service=SimpleNamespace(
            resolve_plan=lambda _v, _role: resolution,
            list_plan_detail_rows_all_for_resolution=lambda **_kw: plan_rows,
            get_plan_time_span_for_resolution=lambda **_kw: {"version": 8},
        ),
    )

    @app.before_request
    def _inject_services() -> None:
        g.services = services
        g.db = object()
        g.app_logger = app.logger
        g.op_logger = None

    payload = client.get("/scheduler/batches/B001").get_json()
    sp = payload["schedule_placement"]

    assert sp["state"] == "ok"
    assert sp["op_count"] == 1
    row = sp["op_rows"][0]
    assert row["op_label"] == "OP10"
    assert row["plan_machine_label"] == "M1 设备1"
    assert row["plan_operator_label"] == "O1 人员1"
    assert row["has_execution_record"] is False
    assert row["actual_summary_label"] == "暂未记录现场实际"
    # op_rows 仅 8 个公开字段，无 op_id/schedule_id/machine_id 等内部 raw 身份
    assert set(row.keys()) == {
        "op_label", "plan_machine_label", "plan_operator_label",
        "execution_status_label", "actual_start_time_label", "actual_end_time_label",
        "actual_summary_label", "has_execution_record",
    }
    # 版本 + 批次跨度日期齐全 → 定位甘特链接可用且带 gantt_batch
    assert sp["gantt_link"]["disabled"] is False
    assert "gantt_batch=B001" in sp["gantt_link"]["url"]
