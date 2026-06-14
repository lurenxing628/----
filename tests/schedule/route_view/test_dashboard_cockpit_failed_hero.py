"""route 级测试：首页 hero 失败态独立门控 failed_run_applies_to_current_view（fusion-dashboard-cockpit 决策 1）。

5 场景钉死（经 ctx 捕获 workbench_summary.hero，hero 渲染在 s3，本步只验 route 计算门控）：
1. 当前正式位置 + result_status=failed → 显失败 hero；
2. 看历史旧版本（workbench_version≠最新）的失败结果 → 不显失败 hero；
3. 预览/对比（非 plain plan context）的失败结果 → 不显失败 hero；
4. 遗留别名 'fail' → 经 resolve_result_status 归一后仍判失败（禁裸 == 'failed'）；
5. 最新 failed + ?version=abc / ?version=999（坏/不存在版本，requested_history_error≠""）→ 不显失败 hero。

门控**不依赖** is_current_executable_official_version / summary_matches_identity（result_status=failed
时 executable 恒 False，复用会让失败 hero 永不可达）——故本测试 stub 的 plan context 即便 executable=True，
旧版本/预览/坏版本仍须把失败 hero 挡掉。
"""

from __future__ import annotations

import importlib
import sys
from typing import Any, Dict, List, Optional, cast

from core.infrastructure.database import ensure_schema
from core.models.schedule_history import ScheduleHistory
from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch):
    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_logs.mkdir(exist_ok=True)
    test_backups.mkdir(exist_ok=True)
    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    point_env_at_shared(monkeypatch)
    for name in list(sys.modules):
        if name == "app" or name.startswith("web.bootstrap.entrypoint") or name.startswith("web.bootstrap.factory"):
            sys.modules.pop(name, None)
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    return importlib.import_module("app").create_app()


def _adopted_official_context() -> Dict[str, Any]:
    # 即便 executable=True，门控仍须靠 旧版本/预览/坏版本 各自的条件挡住失败 hero
    return {
        "requested_plan_role": "adopted",
        "effective_plan_role": "adopted",
        "plan_role": "adopted",
        "source_table": "schedule",
        "is_current_executable_official_version": True,
        "can_dispatch": True,
        "can_write_feedback": True,
    }


def _preview_context() -> Dict[str, Any]:
    ctx = _adopted_official_context()
    ctx["is_scenario_preview"] = True
    return ctx


def _adopted_not_executable_context() -> Dict[str, Any]:
    # adopted/plain/当前最新位置，但 executable=False（result_status=failed 时真实即如此）：
    # 门控须独立于 executability 仍放行失败 hero
    ctx = _adopted_official_context()
    ctx["is_current_executable_official_version"] = False
    ctx["can_dispatch"] = False
    ctx["can_write_feedback"] = False
    return ctx


class _StubBatchService:
    def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
        pass

    def list(self, status=None):
        return []


def _make_history_service(records: List[ScheduleHistory]):
    class _StubHistoryService:
        def __init__(self, _conn, logger=None, op_logger=None, **_kwargs):
            pass

        def list_recent(self, limit=1):
            return records[:limit]

        def get_by_version(self, version):
            for record in records:
                if record.version == version:
                    return record
            return None

    return _StubHistoryService


def _capture_home_hero(
    tmp_path,
    monkeypatch,
    *,
    records: List[ScheduleHistory],
    plan_ctx: Dict[str, Any],
    path: str = "/",
) -> Dict[str, Any]:
    app = _build_app(tmp_path, monkeypatch)
    import web.bootstrap.request_services as request_services_mod
    import web.routes.dashboard as route_mod

    monkeypatch.setattr(request_services_mod, "BatchService", _StubBatchService)
    monkeypatch.setattr(request_services_mod, "ScheduleHistoryQueryService", _make_history_service(records))
    monkeypatch.setattr(route_mod, "_plan_resolution_context", lambda _services, _version: dict(plan_ctx))
    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    with app.test_request_context(path):
        app.preprocess_request()
        ctx = cast(Dict[str, Any], route_mod.index())
    return ctx["workbench_summary"]["hero"]


def _history(version: int, status: Optional[str]) -> ScheduleHistory:
    return ScheduleHistory(id=version, version=version, result_status=status, result_summary="{}")


def test_failed_hero_shown_for_current_official_failed(tmp_path, monkeypatch) -> None:
    hero = _capture_home_hero(
        tmp_path, monkeypatch,
        records=[_history(9, "failed")],
        plan_ctx=_adopted_official_context(),
    )
    assert hero["mode"] == "failed"
    assert hero["title"] == "最近一次排产没有成功"


def test_failed_hero_independent_of_executability(tmp_path, monkeypatch) -> None:
    # 防回归：门控不得重新耦合 is_current_executable_official_version——failed 时它恒 False，
    # 即便如此（executable=False）当前正式最新位置的失败仍须显示失败 hero。
    hero = _capture_home_hero(
        tmp_path, monkeypatch,
        records=[_history(9, "failed")],
        plan_ctx=_adopted_not_executable_context(),
    )
    assert hero["mode"] == "failed"


def test_failed_hero_hidden_for_old_version(tmp_path, monkeypatch) -> None:
    # 最新是 v10（成功），请求 ?version=5（失败旧版本）→ workbench_version≠最新 → 门控假
    hero = _capture_home_hero(
        tmp_path, monkeypatch,
        records=[_history(10, "success"), _history(5, "failed")],
        plan_ctx=_adopted_official_context(),
        path="/?version=5",
    )
    assert hero["mode"] != "failed"


def test_failed_hero_hidden_for_preview_context(tmp_path, monkeypatch) -> None:
    # 预览（非 plain plan context）→ 门控假，失败结果不冒充当前
    hero = _capture_home_hero(
        tmp_path, monkeypatch,
        records=[_history(9, "failed")],
        plan_ctx=_preview_context(),
    )
    assert hero["mode"] != "failed"


def test_failed_hero_shown_for_legacy_alias_fail(tmp_path, monkeypatch) -> None:
    # 'fail' 遗留别名经 resolve_result_status 归一 → 仍判失败
    hero = _capture_home_hero(
        tmp_path, monkeypatch,
        records=[_history(9, "fail")],
        plan_ctx=_adopted_official_context(),
    )
    assert hero["mode"] == "failed"


def test_failed_hero_hidden_for_bad_version_request(tmp_path, monkeypatch) -> None:
    # 最新 failed + ?version=abc（坏版本，requested_history_error≠""）→ 门控假，不与失败 hero 混淆
    bad = _capture_home_hero(
        tmp_path, monkeypatch,
        records=[_history(9, "failed")],
        plan_ctx=_adopted_official_context(),
        path="/?version=abc",
    )
    assert bad["mode"] != "failed"
    # ?version=999（不存在）同理
    missing = _capture_home_hero(
        tmp_path, monkeypatch,
        records=[_history(9, "failed")],
        plan_ctx=_adopted_official_context(),
        path="/?version=999",
    )
    assert missing["mode"] != "failed"
