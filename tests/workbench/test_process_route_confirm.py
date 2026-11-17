"""Route changes, inline confirmation columns and all 12 write-entry invalidation contracts."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_commands import normalize_process_input, process_number
from core.models.workbench_process_table_query import ProcessTablePageRequest
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.facts.table_cells import text_cell
from core.services.workbench.process.mutations import WorkbenchProcessMutationService
from core.services.workbench.process.queries import WorkbenchProcessQueryService
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from core.services.workbench.resource.readiness import process_readiness
from tests.workbench.process_commands_support import (
    CONFIRMED_AT,
    group_rows,
    hours_input,
    identity_for,
    op_ref,
    op_rows,
    prepare_stages,
    ref_for,
    route_input,
    run_stage,
    source_input,
    stage_database,
    storage,
)
from tests.workbench.process_file_api_support import file_api_fixture
from tests.workbench.process_route_support import read_only_probe
from tests.workbench.process_stage_api_support import success
from web.runtime_host import install_wall_clock

_stage_fixture = stage_database
_file_api_fixture = file_api_fixture


def _part_row(conn, part_no="PROC-001"):
    return dict(conn.execute("SELECT * FROM Parts WHERE part_no=?", (part_no,)).fetchone())


def _ready_part(conn):
    suffix = uuid.uuid4().hex
    run_stage(conn, "route_confirm", route_input(conn), key="ready-rt-" + suffix)
    run_stage(conn, "source_confirm", source_input(conn), key="ready-sc-" + suffix)
    run_stage(conn, "hours_confirm", hours_input(conn), key="ready-hr-" + suffix)
    part = _part_row(conn)
    assert part["hours_confirmed_at"] is not None


def _update_resource(conn, kind, code, payload):
    reader = WorkbenchResourceQueryService(conn, kind)
    identity = reader.identities.find_active(kind, code)
    assert identity is not None
    normalized = reader.domain.normalize_input("update", payload)

    def guard():
        prep = reader.preparation_for("update", normalized, ref=identity.ref)
        checked = prep.state(kind, identity.entity_key)
        return reader.domain.prepare("update", normalized, checked, prep)

    return WorkbenchCommandService(conn).execute(
        request_key="res-" + uuid.uuid4().hex,
        action=f"{kind}.update",
        context_ref=identity.ref,
        normalized_input=normalized,
        guard=guard,
        mutate=reader.domain.apply_prepared,
    )


def test_route_review_reuses_current_facts_for_parser_and_choices(stage_conn, monkeypatch):
    from core.services.workbench.process.route_preview import ProcessRoutePreviewService
    from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository

    calls = []
    original = ProcessRoutePreviewService.preview

    def parse(service, body):
        calls.append(body)
        return original(service, body)

    def reread(*args, **kwargs):
        raise AssertionError("route references must come from current process facts")

    monkeypatch.setattr(ProcessRoutePreviewService, "preview", parse)
    identity = identity_for(stage_conn)
    reader = WorkbenchProcessQueryService(stage_conn, part_ref=identity.ref)
    with reader.read_snapshot() as scope:
        facts = scope.facts()
        assert [row["part_no"] for row in facts.raw.parts] == ["PROC-001"]
        assert {row["part_no"] for row in facts.raw.operations} == {"PROC-001"}
        assert {row["part_no"] for row in facts.raw.groups} == {"PROC-001"}
        assert set(facts.workflow.parts) == {"PROC-001"}
        monkeypatch.setattr(WorkbenchProcessQueryRepository, "catalog_references", reread)
        monkeypatch.setattr(WorkbenchProcessQueryRepository, "identities", reread)
        preview, _, affected = scope.prepare_route(identity, {"mode": "text", "route_raw": "10车削30检验"})
        mixed_preview, _, _ = scope.prepare_route(identity, {"mode": "text", "route_raw": "10车削20:热处理"})
    assert len(calls) == 2 and preview["can_confirm_route"]
    assert not mixed_preview["can_confirm_route"]
    assert "explicit_route_invalid" in {row["code"] for row in mixed_preview["diagnostics"]}
    assert [row["ref"] for row in affected] == [ref_for(stage_conn, "template_external_group", "PROC-G")]


def test_group_impact_is_readonly_and_exact_ack_is_required(stage_conn):
    payload = route_input(stage_conn, "10车削30检验")
    del payload["discard_group_refs"]
    before = storage(stage_conn)
    service = WorkbenchProcessMutationService(stage_conn)
    reader = WorkbenchProcessQueryService(stage_conn)
    with reader.read_snapshot() as scope:
        identity = identity_for(stage_conn)
        facts = scope.facts()
        checked = service.checked_facts(scope.resolve(identity.ref), facts)
        normalized = service.normalize("route_confirm", payload)
        with read_only_probe(stage_conn):
            prepared = service.prepare_review("route_confirm", normalized, checked, facts=facts)
        affected = sorted(row["ref"] for row in prepared.affected)
    assert affected == [ref_for(stage_conn, "template_external_group", "PROC-G")] and storage(stage_conn) == before
    with pytest.raises(WorkbenchCommandRejected):
        run_stage(stage_conn, "route_confirm", {**payload, "discard_group_refs": []})
    assert storage(stage_conn) == before
    old, old_ref = op_rows(stage_conn), op_ref(stage_conn, 20)
    run_stage(stage_conn, "route_confirm", {**payload, "discard_group_refs": affected})
    assert group_rows(stage_conn) == {}
    assert op_rows(stage_conn)[20] == {
        **old[20],
        "ext_group_id": None,
        "status": "deleted",
        "source_confirmed_at": None,
        "hours_confirmed_at": None,
    }
    assert op_ref(stage_conn, 20) == old_ref


def test_hours_confirm_with_external_and_zero_unit_hours_acknowledgement(stage_conn):
    prepare_stages(stage_conn)
    payload = hours_input(stage_conn)
    unacknowledged = {**payload, "confirm_zero_unit_hours": False}
    with pytest.raises(WorkbenchCommandRejected) as exc:
        run_stage(stage_conn, "hours_confirm", unacknowledged, key="hours-zero-unconfirmed")
    assert exc.value.code == "zero_unit_hours_confirmation_required"
    assert exc.value.status == 422
    assert exc.value.fields == ("operations." + op_ref(stage_conn, 30) + ".unit_hours",)

    confirmed = run_stage(stage_conn, "hours_confirm", payload, key="hours-zero-confirmed")
    assert confirmed["result"] == "committed"

    repeated = run_stage(stage_conn, "hours_confirm", unacknowledged, key="hours-zero-unchanged")
    assert repeated["result"] == "unchanged"


def test_hours_input_admits_the_same_number_domain_the_readers_accept():
    assert process_number((1 << 53) - 1, "operations.x.unit_hours") == float((1 << 53) - 1)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        process_number(float(1 << 53), "operations.x.unit_hours")
    assert (exc.value.code, exc.value.status, str(exc.value)) == ("invalid_input", 422, "工时超出有效数字范围。")
    assert exc.value.fields == ("operations.x.unit_hours",)


_CYCLE_RANGE = "外协周期必须大于 0 天且不超过 36500 天（100 年）。"


@pytest.mark.parametrize("value", [0, -1, 36500.5, float("inf"), float("nan"), True, "3"],
                         ids=["zero", "negative", "beyond-100-years", "inf", "nan", "bool", "text"])
def test_stage_cycles_refuse_values_outside_the_external_days_domain(value):
    """工时确认的本序周期与整组周期、外协段确认的整组周期都按同一值域拒收。"""
    ref = "a" * 48
    payloads = [
        ("hours_confirm", {"operations": [{"ref": ref, "external_days": value}], "groups": [],
                           "confirm_zero_unit_hours": False}, "operations." + ref + ".external_days"),
        ("hours_confirm", {"operations": [], "groups": [{"ref": ref, "total_days": value}],
                           "confirm_zero_unit_hours": False}, "groups." + ref + ".total_days"),
        ("groups_confirm", {"groups": [{"ref": None, "operation_refs": [ref], "supplier_ref": "b" * 48,
                                        "total_days": value}], "discard_group_refs": []}, "groups.0.total_days"),
    ]
    for action, payload, path in payloads:
        with pytest.raises(WorkbenchCommandRejected) as exc:
            normalize_process_input(action, payload)
        assert (exc.value.code, exc.value.status, str(exc.value), exc.value.fields) == (
            "invalid_input", 422, _CYCLE_RANGE, (path,))


def test_hours_confirm_stores_a_100_year_group_cycle_and_refuses_one_beyond(stage_conn):
    prepare_stages(stage_conn)
    payload = hours_input(stage_conn)
    payload["groups"][0]["total_days"] = 36500.5
    before = storage(stage_conn)
    with pytest.raises(WorkbenchCommandRejected) as exc:
        run_stage(stage_conn, "hours_confirm", payload, key="hours-cycle-beyond-century")
    assert str(exc.value) == _CYCLE_RANGE and storage(stage_conn) == before
    payload["groups"][0]["total_days"] = 36500
    assert run_stage(stage_conn, "hours_confirm", payload, key="hours-cycle-century")["result"] == "committed"
    assert group_rows(stage_conn)["PROC-G"]["total_days"] == 36500.0


def test_text_and_rows_route_inputs_preserve_padded_operation_name_and_bound_choices(schema_conn):
    schema_conn.executemany(
        "INSERT INTO OpTypes(op_type_id, name, category) VALUES (?, ?, 'internal')",
        [("OT-A", "A"), ("OT-B", "B")],
    )
    schema_conn.execute(
        "INSERT INTO Parts(part_no, part_name, route_raw, route_parsed) VALUES ('PROC-001', '轴套', NULL, 'no')"
    )
    schema_conn.commit()

    run_stage(
        schema_conn,
        "route_confirm",
        {"route": {"mode": "text", "route_raw": '10: " A "'}, "discard_group_refs": []},
        key="route-padded-init",
    )
    op_b_ref = ref_for(schema_conn, "op_type", "OT-B")
    run_stage(
        schema_conn,
        "source_confirm",
        {
            "operations": [
                {
                    "ref": op_ref(schema_conn, 10),
                    "source": "internal",
                    "op_type_ref": op_b_ref,
                    "supplier_ref": None,
                    "confirmed": True,
                }
            ],
            "discard_group_refs": [],
        },
        key="source-padded-bind-b",
    )
    run_stage(
        schema_conn,
        "hours_confirm",
        {
            "operations": [{"ref": op_ref(schema_conn, 10), "setup_hours": 1.5, "unit_hours": 0.25}],
            "groups": [],
            "confirm_zero_unit_hours": False,
        },
        key="hours-padded-fill",
    )

    identity = identity_for(schema_conn)
    reader = WorkbenchProcessQueryService(schema_conn, part_ref=identity.ref)
    text_route = {"mode": "text", "route_raw": '10: " A "'}
    rows_route = {"mode": "rows", "rows": [{"seq": 10, "op_type_name": " A "}]}
    for key_suffix, route_body in (("text", text_route), ("rows", rows_route)):
        with reader.read_snapshot() as scope:
            preview, _, affected = scope.prepare_route(identity, route_body)
        assert affected == []
        assert preview["can_confirm_route"] is True
        assert preview["route_raw"] == '10: " A "'
        assert preview["normalized_input"] == '10: " A "'
        assert preview["changes"] == {"added": [], "removed": [], "retained": [10], "same_sequence_changed": []}
        (op_preview,) = preview["operations"]
        assert op_preview["op_type_name"] == " A "
        assert op_preview["op_type_ref"] == op_b_ref
        assert op_preview["replace_existing_choices"] is False

        outcome = run_stage(
            schema_conn,
            "route_confirm",
            {"route": route_body, "discard_group_refs": []},
            key=f"route-padded-reconfirm-{key_suffix}",
        )
        assert outcome["result"] == "unchanged"
        persisted = op_rows(schema_conn)[10]
        assert persisted["op_type_name"] == " A "
        assert persisted["op_type_id"] == "OT-B"
        assert persisted["source"] == "internal"
        assert (persisted["setup_hours"], persisted["unit_hours"]) == (1.5, 0.25)


def test_twelve_write_entries_invalidation_and_single_sql_process_readiness(stage_conn):
    from core.services.process.template_hours import ProcessTemplateHours
    from core.services.workbench.calibration.adoption_policy import adopt_checked_quota
    from core.services.workbench.process.file_codec import encode_process_file
    from core.services.workbench.process.files import WorkbenchProcessFileService
    from core.services.workbench.process.part_actions import WorkbenchProcessPartActionService
    from data.repositories.workbench_calibration_adoption_repo import WorkbenchCalibrationAdoptionRepository

    conn = stage_conn

    # 入口 1：part_actions.apply_create 新建受管空零件
    part_svc = WorkbenchProcessPartActionService(conn)
    with TransactionManager(conn).transaction(begin_immediate=True):
        part_model = part_svc.prepare_create(
            {"business_code": "MANAGED-EMPTY", "label": "空件", "route_raw": None, "remark": None}
        )
        created = part_svc.apply_create(part_model).data
    assert created["workflow"]["origin"] == "managed" and created["workflow"]["stage"] == "route"
    assert created["workflow"]["route"]["state"] == "missing"

    # 入口 2 & 3：file_route 新建与修改已有零件路线回退 source/hours（仅改名称/备注或带未变路线行不回退）
    _ready_part(conn)
    ready_before_file = _part_row(conn)
    files = WorkbenchProcessFileService(conn)
    for unchanged_route_rows in (
        [{"business_code": "PROC-001", "remark": "仅改备注"}],
        [{"business_code": "PROC-001", "route_raw": "10车削20热处理30检验", "remark": "带未变路线改备注"}],
        [{"business_code": "PROC-001", "route_raw": "10车削20热处理30检验", "remark": "带未变路线改备注"}],
    ):
        unchanged_csv = encode_process_file("route", unchanged_route_rows, "csv").content
        preview_unchanged, _ = files.preview_import(
            "route", unchanged_csv, file_format="csv", mode="upsert", target_ref=None
        )
        with TransactionManager(conn).transaction(begin_immediate=True):
            files.confirm_import(preview_unchanged, discard_group_refs=[], confirm_zero_unit_hours=False, confirmed_at=CONFIRMED_AT)
        after_unchanged = _part_row(conn)
        assert after_unchanged["source_confirmed_at"] == ready_before_file["source_confirmed_at"]
        assert after_unchanged["hours_confirmed_at"] == ready_before_file["hours_confirmed_at"]

    route_csv = encode_process_file(
        "route",
        [
            {"business_code": "PROC-001", "route_raw": "10车削20热处理30检验40车削"},
            {"business_code": "FILE-MANAGED", "label": "导入件", "route_raw": "10车削"},
        ],
        "csv",
    ).content
    preview_rt, _ = files.preview_import("route", route_csv, file_format="csv", mode="upsert", target_ref=None)
    with TransactionManager(conn).transaction(begin_immediate=True):
        files.confirm_import(preview_rt, discard_group_refs=[], confirm_zero_unit_hours=False, confirmed_at=CONFIRMED_AT)
    p1 = _part_row(conn)
    assert p1["route_confirmed_at"] is not None
    assert p1["source_confirmed_at"] is None and p1["hours_confirmed_at"] is None
    assert _part_row(conn, "FILE-MANAGED")["route_confirmed_at"] is not None

    # 入口 4：route_confirm 改回原路线 10车削20热处理30检验 后，仍须重认 source 与 hours
    run_stage(conn, "source_confirm", source_input(conn), key="reconfirm-source-0001")
    hrs_with_40 = hours_input(conn)
    for item in hrs_with_40["operations"]:
        if item.get("setup_hours") is None and "setup_hours" in item:
            item.update(setup_hours=1.0, unit_hours=0.5)
    run_stage(conn, "hours_confirm", hrs_with_40, key="reconfirm-hours-00001")
    assert _part_row(conn)["hours_confirmed_at"] is not None
    run_stage(
        conn,
        "route_confirm",
        {"route": {"mode": "text", "route_raw": "10车削20热处理30检验"}, "discard_group_refs": []},
        key="route-back-to-three-01",
    )
    assert _part_row(conn)["source_confirmed_at"] is None and _part_row(conn)["hours_confirmed_at"] is None

    # 入口 5 & 7：source_confirm 仅改第 20 道外协供应商 -> 第 10/30 道 hours 保留确认，第 20 道与零件 hours 回退
    _ready_part(conn)
    src_payload = source_input(conn)
    sup2_ref = ref_for(conn, "supplier", "PROC-S2")
    for item in src_payload["operations"]:
        if item["ref"] == op_ref(conn, 20):
            item["supplier_ref"] = sup2_ref
    run_stage(conn, "source_confirm", src_payload, key="source-change-sup2-001")
    assert _part_row(conn)["source_confirmed_at"] is not None and _part_row(conn)["hours_confirmed_at"] is None
    ops = op_rows(conn)
    assert ops[10]["hours_confirmed_at"] is not None and ops[30]["hours_confirmed_at"] is not None
    assert ops[20]["source_confirmed_at"] is not None and ops[20]["hours_confirmed_at"] is None

    # 入口 6 & 9 & 10：file_hours 合并组周期导入回退整组成员（20）及零件工时确认
    run_stage(conn, "hours_confirm", hours_input(conn), key="hours-reconfirm-sup2-1")
    assert _part_row(conn)["hours_confirmed_at"] is not None
    grp_csv = encode_process_file("hours", [{"business_code": "PROC-001", "sequence": 20, "group_total_days": 8.5}], "csv").content
    preview_grp, _ = files.preview_import("hours", grp_csv, file_format="csv", mode="upsert", target_ref=None)
    with TransactionManager(conn).transaction(begin_immediate=True):
        files.confirm_import(preview_grp, discard_group_refs=[], confirm_zero_unit_hours=False, confirmed_at=CONFIRMED_AT)
    assert _part_row(conn)["hours_confirmed_at"] is None
    assert op_rows(conn)[20]["hours_confirmed_at"] is None
    assert op_rows(conn)[10]["hours_confirmed_at"] is not None

    # 入口 8 & 10（校准采纳）：adopt_checked_quota 异值回退工时确认且返回 hours_confirmed_at=None；同值保留
    run_stage(conn, "hours_confirm", hours_input(conn), key="hours-before-adopt-001")
    adopt_repo = WorkbenchCalibrationAdoptionRepository(conn)
    tmpl_ref = op_ref(conn, 10)
    with TransactionManager(conn).transaction(begin_immediate=True):
        tmpl = adopt_repo.template(tmpl_ref)
        assert tmpl is not None
        same_after = adopt_checked_quota(adopt_repo, tmpl, tmpl["unit_hours"])
        assert same_after["hours_confirmed_at"] is not None
        assert _part_row(conn)["hours_confirmed_at"] is not None
        diff_after = adopt_checked_quota(adopt_repo, tmpl, 0.75)
        assert diff_after["hours_confirmed_at"] is None
    assert _part_row(conn)["hours_confirmed_at"] is None
    assert op_rows(conn)[10]["hours_confirmed_at"] is None

    # 直接修订 ProcessTemplateHours.revise_current 回退
    run_stage(conn, "hours_confirm", hours_input(conn), key="hours-before-direct-revise")
    with TransactionManager(conn).transaction(begin_immediate=True):
        cur_op = WorkbenchProcessQueryService(conn, part_ref=identity_for(conn).ref).repo.operations()[0]
        ProcessTemplateHours(conn).revise_current(cur_op, {"unit_hours": 0.5})
    assert _part_row(conn)["hours_confirmed_at"] is None and op_rows(conn)[10]["hours_confirmed_at"] is None

    # 入口 11：工种改名回退 source/hours；扩为 both 不回退；在用工种收窄类别被正规准入 409 拒绝且保留确认
    run_stage(conn, "hours_confirm", hours_input(conn), key="hours-before-optype-01")
    _update_resource(conn, "op_type", "PROC-IN", {"fields": {"category": "both"}})
    assert _part_row(conn)["hours_confirmed_at"] is not None
    _update_resource(conn, "op_type", "PROC-IN", {"label": "精密车削"})
    assert _part_row(conn)["source_confirmed_at"] is None and _part_row(conn)["hours_confirmed_at"] is None
    assert op_rows(conn)[10]["source_confirmed_at"] is None
    assert op_rows(conn)[20]["source_confirmed_at"] is not None

    run_stage(conn, "source_confirm", source_input(conn), key="src-after-rename-0001")
    run_stage(conn, "hours_confirm", hours_input(conn), key="hrs-after-rename-0001")
    part_before_narrow = _part_row(conn)
    op10_before_narrow = op_rows(conn)[10]
    with pytest.raises(WorkbenchCommandRejected) as narrow_exc:
        _update_resource(conn, "op_type", "PROC-IN", {"fields": {"category": "external"}})
    assert narrow_exc.value.status == 409 and narrow_exc.value.code == "constraint_conflict"
    assert _part_row(conn)["source_confirmed_at"] == part_before_narrow["source_confirmed_at"]
    assert _part_row(conn)["hours_confirmed_at"] == part_before_narrow["hours_confirmed_at"]
    assert op_rows(conn)[10]["source_confirmed_at"] == op10_before_narrow["source_confirmed_at"]
    assert op_rows(conn)[10]["hours_confirmed_at"] == op10_before_narrow["hours_confirmed_at"]

    # 入口 12：供应商缩减工种能力精准回退使用该能力的直连/merged 工序，新增能力不回退
    conn.execute("INSERT INTO OpTypes(op_type_id, name, category) VALUES ('PROC-EX2', '表面处理', 'external')")
    conn.commit()
    run_stage(conn, "source_confirm", source_input(conn), key="src-before-sup-cap-01")
    run_stage(conn, "hours_confirm", hours_input(conn), key="hrs-before-sup-cap-01")
    ex_ref = ref_for(conn, "op_type", "PROC-EX")
    ex2_ref = ref_for(conn, "op_type", "PROC-EX2")
    _update_resource(conn, "supplier", "PROC-S2", {"relationships": {"op_type_refs": [ex_ref, ex2_ref]}})
    assert _part_row(conn)["hours_confirmed_at"] is not None
    _update_resource(conn, "supplier", "PROC-S2", {"relationships": {"op_type_refs": [ex2_ref]}})
    assert _part_row(conn)["source_confirmed_at"] is None and op_rows(conn)[20]["source_confirmed_at"] is None

    # process_readiness 单条 SQL 聚合核验
    total_parts = conn.execute("SELECT COUNT(*) FROM Parts").fetchone()[0]
    sql_trace = []
    conn.set_trace_callback(sql_trace.append)
    try:
        readiness = process_readiness(conn, total_parts)
    finally:
        conn.set_trace_callback(None)
    assert len(sql_trace) == 1
    c = readiness["counts"]
    assert c["total"] == total_parts
    assert c["route"] + c["source"] + c["hours"] + c["ready"] == total_parts
    assert c["legacy"] + c["managed"] == total_parts


def test_page_parts_sql_sort_matches_advanced_filter_for_whitespace_and_nfc_labels(schema_conn):
    schema_conn.execute("INSERT INTO OpTypes(op_type_id, name, category) VALUES ('OT-1', '车削', 'internal')")
    schema_conn.executemany(
        "INSERT INTO Parts(part_no, part_name, route_raw, route_parsed) VALUES (?, ?, NULL, 'no')",
        [
            ("P-BLANK", "   "),
            ("PROC-001", "轴  套"),
            ("P-SS", "轴 A"),
            ("P-PAD", "  轴 A  "),
            ("P-NFD", "Cafe\u0301"),
            ("P-NFC", "Café"),
            ("P  套", "同标签"),
            ("P A", "同标签"),
        ],
    )
    schema_conn.commit()
    run_stage(
        schema_conn,
        "route_confirm",
        {"route": {"mode": "text", "route_raw": "10车削"}, "discard_group_refs": []},
        key="sort-seed-route-01",
    )

    all_matching_filter = {"stage": {"mode": "exclude", "values": [text_cell("已就绪").key]}}
    reader = WorkbenchProcessQueryService(schema_conn)
    with reader.read_snapshot() as scope:
        for sort_spec, direction in (
            ("label", "asc"),
            ("label", "desc"),
            ("business_code", "asc"),
            ("business_code", "desc"),
            ("operation_count", "desc"),
            ("stage", "desc"),
            ([{"field": "label", "direction": "desc"}, {"field": "business_code", "direction": "desc"}], "asc"),
        ):
            sql_req = ProcessTablePageRequest(sort=sort_spec, direction=direction, size=50)
            adv_req = ProcessTablePageRequest(
                sort=sort_spec, direction=direction, size=50, column_filters=all_matching_filter
            )
            sql_codes = [row["business_code"] for row in scope.page(sql_req)["entities"]]
            adv_codes = [row["business_code"] for row in scope.page(adv_req)["entities"]]
            assert sql_codes == adv_codes
            if sort_spec == "label" and direction == "asc":
                assert sql_codes[0] == "P-BLANK"
                assert sql_codes.index("P-SS") < sql_codes.index("PROC-001")
                assert sql_codes.index("P A") < sql_codes.index("P  套")


def _utc_text(moment):
    # 独立于实现的换算：工厂本地时刻按本机时区对应的 UTC 时刻，微秒精度，Z 结尾。
    return datetime.fromtimestamp(moment.timestamp(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def test_route_confirmation_time_is_the_app_clock_in_utc(file_api):
    fixed = datetime(2035, 1, 2, 3, 4, 5, 678901)
    install_wall_clock(file_api.client.application, lambda: fixed)
    file_api.confirm("route_confirm", {"route": file_api.route(), "discard_group_refs": []})
    detail = file_api.detail()
    assert detail["data"]["workflow"]["route"]["confirmed_at"] == _utc_text(fixed)
    assert detail["meta"]["as_of"] == "2035-01-02T03:04:05"


def test_route_file_confirms_every_saved_route_with_one_reading_of_the_app_clock(file_api):
    rows = [{"business_code": code, "label": "New part " + code, "route_raw": "10车削"}
            for code in ("FILE-A", "FILE-B")]
    preview = file_api.preview_rows("route", rows)
    assert preview["data"]["can_confirm"], preview
    readings = []

    def clock():
        # Every reading moves one second on, so a per-row reading would stamp the rows differently.
        readings.append(datetime(2035, 1, 2, 3, 4, 5, 678901) + timedelta(seconds=len(readings)))
        return readings[-1]

    install_wall_clock(file_api.client.application, clock)
    success(file_api.file_post("route", "confirm", file_api.file_body(preview)))
    assert len(readings) == 1
    stamps = [row["route_confirmed_at"] for row in file_api.rows("Parts", "part_no IN ('FILE-A','FILE-B')")]
    assert stamps == [_utc_text(readings[0])] * 2
