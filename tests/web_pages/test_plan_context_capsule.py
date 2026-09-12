"""壳层计划上下文胶囊契约（fusion-plan-context-capsule，4.2）。

钉死点：合同四类边界（_UNSET 未喂参「-」/ 喂 None 空串走词表缺失态 / 正常值 /
坏值）；builder 无 version 零渲染；history_row_capsule_fields 查不到诚实降级
（有意行为防误修）；URL fallback 不查库补；6 发布点喂参落点实证；dashboard
muted 行去重后版本号归胶囊单点。
"""

from __future__ import annotations

from contextlib import closing
from unittest.mock import patch

import pytest

from core.infrastructure.database import get_connection
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.services.system.maintenance import MaintenanceThrottle
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests._support.gantt_retirement import _business_state
from tests._support.paths import REPO_ROOT
from tests._support.workbench_browser_contract import browser_contract
from tests._support.workbench_web_contract import canonical_boot, retired_response
from web.viewmodels.plan_context_capsule import build_plan_context_capsule, history_row_capsule_fields
from web.viewmodels.scheduler_workbench_links import build_workbench_plan_context


@pytest.fixture(autouse=True)
def _isolate_maintenance_throttle(monkeypatch):
    # Each fresh database must initialize defaults before its read-only snapshot.
    monkeypatch.setattr(MaintenanceThrottle, "_last_check_ts", MaintenanceThrottle._last_check_ts)
    MaintenanceThrottle.reset()


# ---------- 合同四类边界（design 验收场景 1） ----------


def test_contract_unset_renders_dash():
    context = build_workbench_plan_context(version=7, plan_role="adopted")
    assert context["generated_at_label"] == "-"
    assert context["strategy_label"] == "-"


def test_contract_fed_none_or_empty_uses_vocabulary_missing_state():
    # 喂了 None/空串 ≠ 未喂参：旧历史行缺失值要诚实显示，不伪装成「无上下文」
    context = build_workbench_plan_context(version=7, plan_role="adopted", generated_at=None, strategy=None)
    assert context["generated_at_label"] == "-"  # format_public_datetime 空值口径
    assert context["strategy_label"] == "旧历史未记录"  # 词表单源缺失态
    context2 = build_workbench_plan_context(version=7, plan_role="adopted", generated_at="", strategy="")
    assert context2["strategy_label"] == "旧历史未记录"


def test_contract_normal_and_bad_values():
    context = build_workbench_plan_context(
        version=7, plan_role="adopted", generated_at="2026-06-01 08:00:00", strategy="weighted"
    )
    assert context["generated_at_label"] == "2026年6月1日 08:00"
    assert context["strategy_label"] == "综合优先级和交期"
    bad = build_workbench_plan_context(
        version=7, plan_role="adopted", generated_at="not-a-time", strategy="future_strategy"
    )
    assert bad["generated_at_label"] == "时间记录异常"
    assert bad["strategy_label"] == "历史记录异常"  # 词表单源未知态（不造第三套文案）


# ---------- builder ----------


def test_capsule_none_without_version():
    assert build_plan_context_capsule(build_workbench_plan_context()) is None
    assert build_plan_context_capsule({}) is None


def test_capsule_full_shape():
    context = build_workbench_plan_context(
        version=7,
        plan_role="adopted",
        date_from="2026-06-01",
        date_to="2026-06-05",
        generated_at="2026-06-01 08:00:00",
        strategy="weighted",
    )
    capsule = build_plan_context_capsule(context)
    assert capsule == {
        "version_label": "v7",
        "plan_role_label": "正式采用方案",
        "generated_at_label": "2026年6月1日 08:00",
        "strategy_label": "综合优先级和交期",
        "date_range_label": "2026-06-01 ～ 2026-06-05",
    }


def test_capsule_missing_fields_render_dash():
    capsule = build_plan_context_capsule(build_workbench_plan_context(version=9, plan_role="adopted"))
    assert capsule is not None
    assert capsule["generated_at_label"] == "-"
    assert capsule["strategy_label"] == "-"
    assert capsule["date_range_label"] == "-"


# ---------- history_row_capsule_fields（公共取数） ----------

_ROWS = [
    {"version": 7, "schedule_time": "2026-06-01 08:00:00", "strategy": "weighted"},
    {"version": 8, "schedule_time": None, "strategy": ""},
]


def test_capsule_fields_found_returns_raw_values():
    assert history_row_capsule_fields(_ROWS, 7) == {
        "generated_at": "2026-06-01 08:00:00",
        "strategy": "weighted",
    }
    # 行存在但值缺失：返回缺失值本身（喂进合同走词表缺失态，不是 _UNSET）
    assert history_row_capsule_fields(_ROWS, 8) == {"generated_at": None, "strategy": ""}


def test_capsule_fields_not_found_is_honest_degradation():
    # 查不到（如 limit-30 外旧版本）→ 空 dict → 胶囊「-」。这是有意降级不是漏查：
    # 胶囊是上下文回显，不为它另发查询（防后人误修成查库补数据）
    assert history_row_capsule_fields(_ROWS, 99) == {}
    assert history_row_capsule_fields(None, 7) == {}
    assert history_row_capsule_fields(_ROWS, "abc") == {}


# ---------- 页面契约（真应用渲染） ----------


def _seed_history(db_path: str) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO ScheduleHistory (version, schedule_time, strategy, batch_count, op_count, result_status, result_summary, created_by)"
        " VALUES (7, '2026-06-01 08:00:00', 'weighted', 1, 1, 'success', '{}', 'pytest')"
    )
    conn.execute("INSERT INTO Parts (part_no, part_name) VALUES ('P1', '零件1')")
    conn.execute("INSERT INTO Batches (batch_id, part_no, quantity) VALUES ('B1', 'P1', 10)")
    conn.execute(
        "INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name) VALUES ('B1-10', 'B1', 10, '车')"
    )
    op_id = conn.execute("SELECT id FROM BatchOperations WHERE op_code='B1-10'").fetchone()[0]
    conn.execute(
        "INSERT INTO Schedule (op_id, start_time, end_time, version)"
        " VALUES (?, '2026-06-01 08:00:00', '2026-06-05 18:00:00', 7)",
        (op_id,),
    )
    conn.commit()
    conn.close()


def _retained_plan(client, version):
    """Keep raw history metadata while reading the same permanent plan identity."""
    canonical_boot(client, "/", "dashboard", {})
    before = _business_state(client)
    with closing(get_connection(client.application.config["DATABASE_PATH"])) as conn:
        row = dict(conn.execute("SELECT * FROM ScheduleHistory WHERE version=?", (version,)).fetchone())
        reference = WorkbenchPlanIdentityRepository(conn).get_plan_ref(WorkbenchPlanLocator(version, "adopted"))
    response = client.get("/api/workbench/v1/plans")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["meta"]["source"] == "production"
    entries = [plan for plan in payload["data"]["plans"] if plan["plan_ref"] == reference]
    assert len(entries) == 1 and entries[0]["version"] == version and entries[0]["kind"] == "official"
    assert not {"plan_role", "scenario_id", "source_table", "candidate_id"} & set(entries[0])
    capsule = build_plan_context_capsule(build_workbench_plan_context(
        version=version, plan_role="adopted", generated_at=row["schedule_time"], strategy=row["strategy"]))
    assert _business_state(client) == before
    return reference, capsule, before


def _retired_plan(client, path, version=7):
    """An inexpressible old scope stays explicit; metadata and exports are retained."""
    reference, capsule, before = _retained_plan(client, version)
    body = retired_response(client.get(path))
    assert "<dt>排产版本</dt><dd>" + str(version) + "</dd>" in body
    assert "<dt>方案</dt><dd>正式采用方案</dd>" in body
    assert "plan_role" not in body.replace("plan_role=adopted", "")
    assert _business_state(client) == before
    return reference, capsule, body


def test_dashboard_capsule_fed_and_chrome_deduped(app_client, db_env):
    _seed_history(db_env)
    reference, capsule, before = _retained_plan(app_client, 7)
    assert capsule["version_label"] == "v7"
    assert capsule["generated_at_label"] == "2026年6月1日 08:00"
    assert capsule["strategy_label"] == "综合优先级和交期"
    response = app_client.get("/api/workbench/v1/dashboard")
    assert response.status_code == 200
    plan = response.get_json()["data"]["plan"]
    assert plan["plan_ref"] == reference and plan["version"] == 7
    observed = browser_contract("""
for (let i=0;i<150 && !document.querySelector('.wb-current-plan');i++) await new Promise(resolve=>setTimeout(resolve,20));
const captions = document.querySelectorAll('.wb-current-plan');
expect(captions.length === 1, 'Current plan must have a single caption');
expect(captions[0].dataset.planRef === data.reference);
expect(captions[0].textContent.includes('正式 v7'));
const body = document.body.innerText.replace(captions[0].innerText,'');
expect(!body.includes('v7'), 'Version duplicated outside current-plan caption');
expect(!body.includes('当前查看版本') && !body.includes('当前查看排产'));
return captions[0].textContent;
""", app=app_client.application, data={"reference": reference})
    assert "正式 v7" in observed
    assert _business_state(app_client) == before


def test_gantt_capsule_fed(app_client, db_env):
    _seed_history(db_env)
    reference, capsule, before = _retained_plan(app_client, 7)
    canonical_boot(app_client, "/scheduler/gantt?version=7", "gantt", {"plan_ref": reference})
    response = app_client.get("/api/workbench/v1/plans/" + reference + "/workspace")
    assert response.status_code == 200
    assert response.get_json()["data"]["plan"]["version"] == 7
    assert capsule["version_label"] == "v7" and capsule["generated_at_label"] == "2026年6月1日 08:00"
    assert _business_state(app_client) == before


def test_analysis_capsule_fed(app_client, db_env):
    _seed_history(db_env)
    reference, capsule, before = _retained_plan(app_client, 7)
    canonical_boot(app_client, "/scheduler/analysis?version=7", "analysis", {"plan_ref": reference})
    assert capsule["generated_at_label"] == "2026年6月1日 08:00"
    assert _business_state(app_client) == before


def test_week_plan_capsule_fed(app_client, db_env):
    _seed_history(db_env)
    _reference, capsule, body = _retired_plan(app_client, "/scheduler/week-plan?version=7")
    assert capsule["generated_at_label"] == "2026年6月1日 08:00"
    assert "未改用新报表默认范围" in body


def test_reports_capsule_fed(app_client, db_env):
    _seed_history(db_env)
    _reference, capsule, body = _retired_plan(app_client, "/reports/overdue?version=7")
    assert capsule["generated_at_label"] == "2026年6月1日 08:00"
    assert 'href="/reports/overdue/export?version=7&amp;plan_role=adopted"' in body
    download = app_client.get("/reports/overdue/export?version=7&plan_role=adopted")
    assert download.status_code == 400
    assert "当前版本没有可导出的超期结果" in download.get_data(as_text=True)
    assert "Content-Disposition" not in download.headers
    with closing(get_connection(db_env)) as conn:
        conn.execute("UPDATE Batches SET due_date='2026-06-01' WHERE batch_id='B1'")
        conn.commit()
    before = _business_state(app_client)
    download = app_client.get("/reports/overdue/export?version=7&plan_role=adopted")
    assert download.status_code == 200
    assert "attachment" in download.headers["Content-Disposition"]
    assert download.data.startswith(b"PK")
    assert _business_state(app_client) == before


def _seed_two_versions(db_path: str) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    # v7 旧版本（早时间/weighted）、v8 最新版本（晚时间/greedy）
    conn.execute(
        "INSERT INTO ScheduleHistory (version, schedule_time, strategy, batch_count, op_count, result_status, result_summary, created_by)"
        " VALUES (7, '2026-06-01 08:00:00', 'weighted', 1, 1, 'success', '{}', 'pytest')"
    )
    conn.execute(
        "INSERT INTO ScheduleHistory (version, schedule_time, strategy, batch_count, op_count, result_status, result_summary, created_by)"
        " VALUES (8, '2026-06-10 09:00:00', 'greedy', 1, 1, 'success', '{}', 'pytest')"
    )
    conn.execute("INSERT INTO Parts (part_no, part_name) VALUES ('P1', '零件1')")
    conn.execute("INSERT INTO Batches (batch_id, part_no, quantity) VALUES ('B1', 'P1', 10)")
    conn.execute(
        "INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name) VALUES ('B1-10', 'B1', 10, '车')"
    )
    op_id = conn.execute("SELECT id FROM BatchOperations WHERE op_code='B1-10'").fetchone()[0]
    for version, start, end in (
        (7, "2026-06-01 08:00:00", "2026-06-05 18:00:00"),
        (8, "2026-06-10 09:00:00", "2026-06-12 18:00:00"),
    ):
        conn.execute(
            "INSERT INTO Schedule (op_id, start_time, end_time, version) VALUES (?, ?, ?, ?)",
            (op_id, start, end, version),
        )
    conn.commit()
    conn.close()


def test_reports_index_old_version_capsule_shows_that_version(app_client, db_env):
    _seed_two_versions(db_env)
    reference, capsule, body = _retired_plan(app_client, "/reports/?version=7")
    assert capsule["version_label"] == "v7"
    assert capsule["generated_at_label"] == "2026年6月1日 08:00"
    assert capsule["strategy_label"] == "综合优先级和交期"
    assert "2026年6月10日 09:00" not in str(capsule)
    assert "<dd>8</dd>" not in body
    with closing(get_connection(db_env)) as conn:
        assert WorkbenchPlanIdentityRepository(conn).resolve_plan(reference) == WorkbenchPlanLocator(7, "adopted")


def test_resource_dispatch_capsule_fed(app_client, db_env):
    _seed_history(db_env)
    _reference, capsule, body = _retired_plan(app_client, "/scheduler/resource-dispatch?version=7")
    assert capsule["generated_at_label"] == "2026年6月1日 08:00"
    assert "未改用新报表默认范围" in body


def test_basic_data_page_renders_no_capsule(app_client, db_env):
    _seed_history(db_env)
    boot = canonical_boot(app_client, "/material/materials", "process", {"source": "production"})
    assert "plan_ref" not in boot["navigation"]["context"]
    source = (REPO_ROOT / "frontend/workbench/app/WorkbenchCaption.jsx").read_text(encoding="utf-8")
    assert 'if (!value) return <div className="cap-rich" />' in source


def test_url_fallback_renders_base_fields_without_query(app_client, db_env):
    _seed_history(db_env)
    canonical_boot(app_client, "/", "dashboard", {})
    before = _business_state(app_client)
    from core.services.workbench.legacy_navigation_queries import LegacyNavigationQueries

    with patch.object(LegacyNavigationQueries, "bind_plan", side_effect=AssertionError("Retired control must not query a plan")):
        body = retired_response(app_client.get("/system/history?version=7"))
    assert "未忽略条件后跳转" in body
    assert "2026年6月1日 08:00" not in body
    assert 'class="aps-plan-capsule"' not in body
    assert _business_state(app_client) == before
