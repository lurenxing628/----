"""手拼链接收编契约（fusion-handrolled-links-adoption）：
history 行级 5 链接与 analysis 版本选择器 2 甘特链入 WorkbenchLink。

钉死点：有计划行版本 5 链接带 adopted 身份+span 日期（URL 形态逐目标对照）；
无计划行版本日期必填链接禁用并给原因（比裸链接点过去看空页更诚实，有意行为
变化）；span 读取异常该行禁用其余行正常；analysis 场景预览用公开 token
（roadmap 第 11 条点名缺陷的正向钉死），裸 preview 禁用明示。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from flask import Flask

from web.routes.system_history import _load_history_span_dates
from web.viewmodels.system_history_links import build_history_version_links


def _query_values(url: str) -> Dict[str, str]:
    return {key: values[-1] for key, values in parse_qs(urlparse(url).query).items()}


_SPAN_7 = {"version": 7, "start_time": "2026-06-01 08:00:00", "end_time": "2026-06-05 18:00:00",
           "start_date": "2026-06-01", "end_date": "2026-06-05"}


class _SpanService:
    """get_plan_time_span 最小合同桩（贴真实 ScheduleTimeSpanRow 形态）。"""

    def __init__(self, spans: Dict[int, Optional[Dict[str, str]]], *, boom_versions=()):
        self._spans = spans
        self._boom = set(boom_versions)
        self.calls: List[int] = []

    def get_plan_time_span(self, version: int, role: Optional[str] = None):
        self.calls.append(int(version))
        if int(version) in self._boom:
            raise ValueError(f"v{version} 缺 adopted 计划")
        return self._spans.get(int(version))


# ---------- history 行级链接装配 ----------


def test_history_links_full_shape_with_span():
    links = build_history_version_links(7, span=_SPAN_7)
    assert [link["label"] for link in links] == ["设备甘特图", "人员甘特图", "周计划", "资源排班", "优化分析"]
    by_label = {link["label"]: link for link in links}

    machine = by_label["设备甘特图"]
    assert not machine["disabled"]
    assert urlparse(machine["url"]).path == "/scheduler/gantt"
    q = _query_values(machine["url"])
    assert q["view"] == "machine"
    assert q["version"] == "7"
    assert q["plan_role"] == "adopted"
    assert q["start_date"] == "2026-06-01"
    assert q["end_date"] == "2026-06-05"

    assert _query_values(by_label["人员甘特图"]["url"])["view"] == "operator"

    week = _query_values(by_label["周计划"]["url"])
    assert week["week_start"] == "2026-06-01"
    assert week["date_from"] == "2026-06-01"

    dispatch = _query_values(by_label["资源排班"]["url"])
    assert dispatch["version"] == "7"
    assert dispatch["period_preset"] == "custom"

    analysis = _query_values(by_label["优化分析"]["url"])
    assert analysis == {"version": "7", "plan_role": "adopted", "date_from": "2026-06-01", "date_to": "2026-06-05"}


def test_history_links_disable_date_required_targets_when_no_plan_rows():
    links = build_history_version_links(9, span=None)  # 失败/模拟运行：无计划行
    by_label = {link["label"]: link for link in links}
    for label in ("设备甘特图", "人员甘特图", "周计划", "资源排班"):
        link = by_label[label]
        assert link["disabled"], label
        assert link["url"] == ""
        assert "日期" in link["disabled_reason"]
    # analysis 不要求日期范围，仍可点
    assert not by_label["优化分析"]["disabled"]


def test_history_links_span_error_disables_row_with_explicit_reason():
    # 路由层 IO：resolve 数据态 ValueError → (None, 错误文案)，不炸整页
    svc = _SpanService({}, boom_versions={5})
    span, span_error = _load_history_span_dates(svc, 5, {})
    assert span is None and "读取失败" in span_error
    links = build_history_version_links(5, span=span, span_error=span_error)
    by_label = {link["label"]: link for link in links}
    for label in ("设备甘特图", "人员甘特图", "周计划", "资源排班"):
        assert by_label[label]["disabled"], label
        assert "读取失败" in by_label[label]["disabled_reason"]
    assert not by_label["优化分析"]["disabled"]


def test_history_links_span_cache_dedupes_same_version():
    svc = _SpanService({7: {"start_time": "2026-06-01 08:00:00", "end_time": "2026-06-05 18:00:00"}})
    cache: Dict[int, Any] = {}
    _load_history_span_dates(svc, 7, cache)
    _load_history_span_dates(svc, 7, cache)
    assert svc.calls == [7]


def test_history_links_invalid_version_returns_empty():
    assert build_history_version_links(None, span=None) == []
    assert build_history_version_links("abc", span=None) == []
    assert build_history_version_links(0, span=None) == []
    svc = _SpanService({})
    assert _load_history_span_dates(svc, None, {}) == (None, "")
    assert svc.calls == []


# ---------- analysis 版本选择器（身份缺陷修复钉死） ----------


class _AnalysisServices:
    """build_version_picker_gantt_links 的最小服务桩（贴 resolve_plan_view/get_plan_time_span 合同）。"""

    class _PlanQuery:
        def resolve_plan_view(self, version, role, scenario_id=None):
            from types import SimpleNamespace

            if scenario_id:
                return SimpleNamespace(
                    to_dict=lambda: {
                        "selected_role": role,
                        "scenario_id": scenario_id,
                        "is_scenario_preview": True,
                        "status": "scenario_preview",
                    }
                )
            return SimpleNamespace(
                to_dict=lambda: {"selected_role": role or "adopted", "scenario_id": None}
            )

        def get_plan_time_span(self, version, role=None):
            return {"start_time": "2026-06-01 08:00:00", "end_time": "2026-06-05 18:00:00"}

        def get_plan_time_span_for_view(self, version, role, scenario_id=None):
            return self.get_plan_time_span(version, role)

    def __init__(self):
        self.schedule_plan_query_service = self._PlanQuery()


def test_version_picker_scenario_preview_keeps_scenario_id():
    from web.routes.domains.scheduler.scheduler_analysis_links import build_version_picker_gantt_links

    app = Flask(__name__)
    with app.app_context():
        links = build_version_picker_gantt_links(
            _AnalysisServices(), 7, plan_role="adopted", scenario_id="S1"
        )
    assert len(links) == 2
    for link in links:
        assert not link["disabled"], link
        q = _query_values(link["url"])
        # roadmap 第 11 条点名缺陷的正向钉死：场景预览跳甘特不再掉回正式视角，但公开 URL 不能裸带内部 id
        assert "scenario_id" not in q
        assert q["plan_context_token"]
        assert "S1" not in q["plan_context_token"]
        assert q["version"] == "7"


def test_version_picker_none_version_returns_empty():
    from web.routes.domains.scheduler.scheduler_analysis_links import build_version_picker_gantt_links

    assert build_version_picker_gantt_links(_AnalysisServices(), None, plan_role="adopted", scenario_id=None) == []


class _ValidationErrorServices:
    """get_plan_time_span 抛 ValueError（get_plan_time_span_dates 包成 ValidationError）：
    模拟「版本日期跨度不可解」的预期数据缺失。"""

    class _PlanQuery(_AnalysisServices._PlanQuery):
        def get_plan_time_span(self, version, role=None):
            raise ValueError("该版本日期跨度不可解")

        def get_plan_time_span_for_view(self, version, role, scenario_id=None):
            raise ValueError("该版本日期跨度不可解")

    def __init__(self):
        self.schedule_plan_query_service = self._PlanQuery()


class _UnexpectedErrorServices:
    """get_plan_time_span 抛 KeyError（非 ValueError）：模拟非预期编程错误，走 except Exception。"""

    class _PlanQuery(_AnalysisServices._PlanQuery):
        def get_plan_time_span(self, version, role=None):
            raise KeyError("unexpected programming error")

        def get_plan_time_span_for_view(self, version, role, scenario_id=None):
            raise KeyError("unexpected programming error")

    def __init__(self):
        self.schedule_plan_query_service = self._PlanQuery()


def test_version_picker_validation_error_disables_links_without_logging(monkeypatch):
    # #5 ValidationError 分支：预期数据缺失 → 链接禁用 + 提示，不记日志（不是 bug 不刷日志）
    from flask import Flask

    from web.routes.domains.scheduler.scheduler_analysis_links import build_version_picker_gantt_links

    app = Flask(__name__)
    logged = []
    monkeypatch.setattr(app.logger, "exception", lambda *a, **k: logged.append((a, k)))
    with app.app_context():
        links = build_version_picker_gantt_links(
            _ValidationErrorServices(), 7, plan_role="adopted", scenario_id=None
        )

    assert len(links) == 2
    for link in links:
        assert link["disabled"], link  # 日期跨度读不到 → 链接禁用
    assert logged == [], "预期的数据缺失（ValidationError）不应记 exception 日志"


def test_version_picker_unexpected_error_logs_exception_and_disables(monkeypatch):
    # #5 except Exception 分支：非预期错误 → 同样降级禁用链接，但必须 logger.exception 留堆栈
    from flask import Flask

    from web.routes.domains.scheduler.scheduler_analysis_links import build_version_picker_gantt_links

    app = Flask(__name__)
    logged = []
    monkeypatch.setattr(app.logger, "exception", lambda *a, **k: logged.append((a, k)))
    with app.app_context():
        links = build_version_picker_gantt_links(
            _UnexpectedErrorServices(), 7, plan_role="adopted", scenario_id=None
        )

    assert len(links) == 2
    for link in links:
        assert link["disabled"], link
    assert len(logged) == 1, "非预期异常应 logger.exception 记录一次"


# ---------- 页面契约（真应用渲染） ----------


def _seed_history_with_plan_rows(db_path: str) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)"
        " VALUES (7, 'weighted', 1, 1, 'success', '{}', 'pytest')"
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
    # v8：有历史但无计划行（模拟失败运行）→ 日期必填链接禁用
    conn.execute(
        "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)"
        " VALUES (8, 'weighted', 0, 0, 'failed', '{}', 'pytest')"
    )
    conn.commit()
    conn.close()


def test_history_page_renders_workbench_links_and_disabled_state(app_client, db_env):
    _seed_history_with_plan_rows(db_env)
    html = app_client.get("/system/history").get_data(as_text=True)
    # v7 行：5 链接可点且带身份与日期
    assert "/scheduler/gantt?view=machine&amp;version=7&amp;plan_role=adopted" in html
    assert "start_date=2026-06-01" in html
    assert "week_start=2026-06-01" in html
    # v8 行：日期必填链接禁用并带原因 title
    assert 'class="table-action-link is-disabled"' in html
    assert "还没有确认日期范围" in html
    # 收编范围外的裸链接原样（分页/去补充不动）
    assert "history_version_links" not in html  # 旧宏名零残留（防回潮锚点）


def test_analysis_version_picker_links_keep_plan_identity(app_client, db_env):
    _seed_history_with_plan_rows(db_env)
    html = app_client.get("/scheduler/analysis?version=7").get_data(as_text=True)
    assert "查看设备甘特图" in html
    assert "/scheduler/gantt?view=machine&amp;version=7&amp;plan_role=adopted" in html
    assert "start_date=2026-06-01" in html
