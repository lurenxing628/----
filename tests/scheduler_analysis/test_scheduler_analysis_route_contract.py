"""回归测试：/scheduler/analysis 路由契约——须经 g.services.schedule_history_query_service 取版本/汇总并产出 versions/selected/trend_rows，summary 解析失败或趋势指标坏/缺时标记 parse_failed/incomplete 而绝不画成 0，请求的历史版本缺失时给 missing_history 解析态、显式旧版本走 get_by_version 而非 recent 下拉。"""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from flask import Flask, g


class _HistoryItem:
    def __init__(self, version: int, summary):
        self.version = int(version)
        self._summary = summary

    def to_dict(self):
        return {"version": self.version, "result_summary": self._summary}


class _HistoryServiceStub:
    def __init__(self, summary, *, versions=None, latest_version=3, recent_items=None):
        self.summary = summary
        self.versions = list(versions) if versions is not None else [{"version": 3}]
        self.latest_version = int(latest_version)
        self.recent_items = list(recent_items) if recent_items is not None else None
        self.version_limits = []
        self.version_queries = []
        self.latest_version_calls = 0
        self.recent_limits = []

    def list_versions(self, limit=50):
        self.version_limits.append(limit)
        return list(self.versions)

    def get_latest_version(self):
        self.latest_version_calls += 1
        return self.latest_version

    def get_by_version(self, version):
        self.version_queries.append(int(version))
        return _HistoryItem(int(version), self.summary)

    def list_recent(self, limit=400):
        self.recent_limits.append(limit)
        if self.recent_items is not None:
            return [_HistoryItem(int(version), summary) for version, summary in self.recent_items]
        return [_HistoryItem(3, self.summary)]


class _MissingSelectedHistoryService(_HistoryServiceStub):
    def get_by_version(self, version):
        self.version_queries.append(int(version))
        return None


def _build_app(monkeypatch, history_service: _HistoryServiceStub) -> Flask:
    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    import web.routes.domains.scheduler.scheduler_analysis as route_mod
    import web.routes.scheduler as _scheduler_routes  # noqa: F401

    monkeypatch.setattr(route_mod, "render_template", lambda _tpl, **ctx: ctx)

    app = Flask(__name__)
    app.secret_key = "aps-scheduler-analysis-route"
    app.register_blueprint(route_mod.bp, url_prefix="/scheduler")

    @app.before_request
    def _inject_services() -> None:
        g.services = SimpleNamespace(schedule_history_query_service=history_service)
        g.app_logger = app.logger
        g.op_logger = None

    return app


def test_scheduler_analysis_route_uses_request_services(monkeypatch) -> None:
    summary = {"warnings": ["冻结窗口存在跳批风险"], "algo": {"metrics": {"overdue_count": 1}}}
    history_service = _HistoryServiceStub(summary)
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/analysis?version=3")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["versions"][0]["version"] == 3
    assert payload["selected"]["version"] == 3
    assert payload["selected_summary"] == summary
    assert payload["trend_rows"][0]["version"] == 3
    assert payload["selected_summary_display"]["summary_parse_state"]["parse_failed"] is False
    assert payload["selected_summary_display"]["warning_total"] == 1
    assert payload["selected_summary_display"]["warnings_preview"] == ["冻结窗口存在跳批风险"]
    assert payload["trend_summary_state"] == {"incomplete": False, "parse_failed_count": 0, "version_parse_failed_count": 0, "metric_parse_failed_count": 0}
    assert "objective_label_for" not in payload
    json.dumps(payload, ensure_ascii=False)
    assert history_service.version_limits == [50]
    assert history_service.version_queries == [3]
    assert history_service.recent_limits == [400]


def test_scheduler_analysis_route_marks_parse_failure_and_incomplete_trend(monkeypatch) -> None:
    history_service = _HistoryServiceStub("{broken json")
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/analysis?version=3")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["selected_summary"] == {}
    assert payload["selected_summary_display"]["summary_parse_state"]["parse_failed"] is True
    assert payload["trend_summary_state"] == {"incomplete": True, "parse_failed_count": 1, "version_parse_failed_count": 0, "metric_parse_failed_count": 0}


def test_scheduler_analysis_route_marks_bad_trend_metric_without_drawing_zero(monkeypatch) -> None:
    summary = {"algo": {"metrics": {"overdue_count": "坏数据", "total_tardiness_hours": 8}}}
    history_service = _HistoryServiceStub(summary)
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/analysis?version=3")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["trend_summary_state"] == {"incomplete": True, "parse_failed_count": 0, "version_parse_failed_count": 0, "metric_parse_failed_count": 1}
    assert payload["trend_charts"]["overdue"] is None, "坏趋势指标不能画成 0"


def test_scheduler_analysis_route_does_not_plot_missing_trend_metric_as_zero(monkeypatch) -> None:
    selected_summary = {"algo": {"metrics": {"overdue_count": 1}}}
    recent_items = [
        (4, {"algo": {"metrics": {"overdue_count": 1}}}),
        (3, {"algo": {"metrics": {"overdue_count": 2}}}),
    ]
    history_service = _HistoryServiceStub(selected_summary, recent_items=recent_items)
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/analysis?version=3")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["trend_summary_state"] == {"incomplete": False, "parse_failed_count": 0, "version_parse_failed_count": 0, "metric_parse_failed_count": 0}
    assert payload["trend_charts"]["tardiness"] is None, "缺少拖期小时不能画成 0"


def test_scheduler_analysis_route_marks_bad_attempt_and_trace_metrics(monkeypatch) -> None:
    selected_summary = {
        "algo": {
            "comparison_metric": "source_table",
            "best_score_schema": [{"index": 1, "key": "overdue_count", "label": "超期批次"}],
            "metrics": {"overdue_count": 1, "source_table": "candidate_rows"},
            "attempts": [
                {
                    "candidate_id": "bad",
                    "strategy": "greedy",
                    "failed_ops": "坏数据",
                    "metrics": {"overdue_count": "坏数据"},
                }
            ],
            "improvement_trace": [
                {"elapsed_ms": 1, "metrics": {"overdue_count": "坏数据"}},
                {"elapsed_ms": "坏时间", "metrics": {"overdue_count": 3}},
                {"elapsed_ms": 2, "metrics": {"overdue_count": 2}},
            ],
        }
    }
    history_service = _HistoryServiceStub(selected_summary)
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/analysis?version=3")
    payload = response.get_json()

    assert response.status_code == 200
    attempts = payload["attempts"]
    assert attempts[0]["primary_value_parse_failed"] is True
    assert attempts[0]["primary_value"] is None
    assert attempts[0]["bar_pct"] is None
    assert attempts[0]["failed_ops_parse_failed"] is True
    assert attempts[0]["failed_ops"] is None
    assert payload["trace_chart"]["metric_parse_failed"] is True
    assert not payload["trace_chart"].get("points"), "坏优化过程指标不能画成 0"


def test_scheduler_analysis_route_projects_attempts_before_template(monkeypatch) -> None:
    selected_summary = {
        "algo": {
            "comparison_metric": "overdue_count",
            "metrics": {"overdue_count": 1},
            "attempts": [
                {
                    "tag": "候选 OP010",
                    "source": "candidate_id=7",
                    "source_label": "内部方案 OP020",
                    "strategy": "greedy",
                    "dispatch_mode": "sgs",
                    "dispatch_rule": "cr",
                    "failed_ops": 0,
                    "metrics": {
                        "overdue_count": 1,
                        "source_table": "candidate_rows",
                    },
                    "score": [1, "op:SECRET"],
                }
            ],
            "candidate_comparison": {
                "enabled": True,
                "planned_candidate_count": 1,
                "completed_candidate_count": 1,
                "failed_candidate_count": 0,
                "adopted_candidate_key": "graph_w1_of_2",
                "baseline_best_candidate_key": "baseline",
                "critical_best_candidate_key": "graph_w1_of_2",
                "candidates": [
                    {
                        "candidate_key": "graph_w1_of_2",
                        "label": "graph_w1_of_2",
                        "status": "completed",
                        "score": [1, "op:SECRET-CANDIDATE"],
                        "metrics": {"overdue_count": 1, "source_table": "candidate_rows"},
                        "roles": ["adopted", "critical_best"],
                        "source_table": "candidate_rows",
                    }
                ],
            },
        }
    }
    history_service = _HistoryServiceStub(selected_summary)
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/analysis?version=3")
    payload = response.get_json()

    assert response.status_code == 200
    attempt = payload["attempts"][0]
    assert attempt["display_tag"] == "方案 1"
    assert attempt["tag"] == ""
    assert attempt["score"] == [1]
    assert attempt["metrics"] == {"overdue_count": 1}
    selected_attempt = payload["selected_summary"]["algo"]["attempts"][0]
    assert selected_attempt["score"] == [1]
    assert selected_attempt["metrics"] == {"overdue_count": 1}
    assert payload["selected_summary"]["algo"]["comparison_metric"] == "overdue_count"
    selected_candidate = payload["selected_summary"]["algo"]["candidate_comparison"]["candidates"][0]
    assert selected_candidate == {
        "label": "重点工序优先方案 1/2",
        "status": "completed",
        "score": [1],
        "metrics": {"overdue_count": 1},
        "roles": ["adopted", "critical_best"],
    }
    rendered = json.dumps(
        {
            "attempts": payload["attempts"],
            "selected_summary": payload["selected_summary"],
            "best_score_schema_display": payload["best_score_schema_display"],
            "candidate_comparison_display": payload["candidate_comparison_display"],
        },
        ensure_ascii=False,
    )
    for forbidden in (
        "OP010",
        "OP020",
        "op:",
        "SECRET",
        "candidate_id",
        "candidate_key",
        "source_table",
        "candidate_rows",
        "graph_w1_of_2",
    ):
        assert forbidden not in rendered


def test_scheduler_analysis_route_sanitizes_internal_metric_values_before_template(monkeypatch) -> None:
    selected_summary = {
        "algo": {
            "comparison_metric": "overdue_count",
            "metrics": {"overdue_count": 1},
            "config_snapshot": {
                "sort_strategy": "priority_first",
                "dispatch_mode": "sgs",
                "dispatch_rule": "op:SECRET-RULE",
                "objective": "min_overdue",
                "time_budget_seconds": 10,
                "source_table": "config_debug",
            },
            "resource_pool": {
                "enabled": "yes",
                "attempted": True,
                "degraded": True,
                "degradation_reason": "自动分配设备人员所需资料不完整。",
                "sample": ["op:SECRET-RESOURCE"],
            },
            "attempts": [
                {
                    "tag": "graph_w1_of_2",
                    "strategy": "greedy",
                    "dispatch_mode": "sgs",
                    "dispatch_rule": "cr",
                    "failed_ops": 0,
                    "metrics": {"overdue_count": "op:SECRET-METRIC OP010"},
                    "score": [1],
                }
            ],
            "improvement_trace": [
                {
                    "elapsed_ms": 1,
                    "metrics": {"overdue_count": "op:SECRET-TRACE OP020"},
                }
            ],
        }
    }
    history_service = _HistoryServiceStub(selected_summary)
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/analysis?version=3")
    payload = response.get_json()

    assert response.status_code == 200
    attempt = payload["attempts"][0]
    assert attempt["display_tag"] == "重点工序优先方案 1/2"
    assert attempt["primary_value_parse_failed"] is True
    assert attempt["metrics"] == {"overdue_count": "记录异常"}
    assert payload["trace_chart"] == {"metric_parse_failed": True, "chart": None}
    rendered = json.dumps(
        {
            "attempts": payload["attempts"],
            "selected_summary": payload["selected_summary"],
            "algo_config_snapshot_dispatch_rule_label": payload["algo_config_snapshot_dispatch_rule_label"],
            "trace_chart": payload["trace_chart"],
        },
        ensure_ascii=False,
    )
    for forbidden in (
        "op:",
        "OP010",
        "OP020",
        "SECRET",
        "source_table",
        "config_debug",
        "graph_w1_of_2",
    ):
        assert forbidden not in rendered


def test_scheduler_analysis_route_surfaces_missing_requested_history(monkeypatch) -> None:
    summary = {"algo": {"metrics": {"overdue_count": 1}}}
    history_service = _MissingSelectedHistoryService(summary)
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/analysis?version=9")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["selected"] is None
    assert payload["selected_summary"] is None
    assert payload["selected_history_resolution"]["requested_version"] == 9
    assert payload["selected_history_resolution"]["history_missing"] is True
    assert "9" in str(payload["selected_history_resolution"]["message"] or "")
    assert payload["version_resolution"]["status"] == "missing_history"
    assert payload["version_resolution"]["requested_version"] == 9
    assert payload["version_resolution"]["selected_version"] is None
    assert payload["trend_rows"][0]["version"] == 3
    assert all(int(item["version"]) != 9 for item in payload["versions"])
    assert history_service.version_queries == [9]


def test_scheduler_analysis_default_latest_does_not_synthesize_missing_selected(monkeypatch) -> None:
    history_service = _MissingSelectedHistoryService(
        {"algo": {"metrics": {"overdue_count": 1}}},
        versions=[{"version": 7}],
        latest_version=7,
    )
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/analysis")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["selected"] is None
    assert payload["selected_summary"] is None
    assert payload["selected_history_resolution"]["history_missing"] is True
    assert payload["selected_history_resolution"]["requested_version"] == 7
    assert payload["version_resolution"]["selected_version"] == 7
    assert history_service.version_queries == [7]


def test_scheduler_analysis_explicit_old_version_uses_history_lookup_not_recent_dropdown(monkeypatch) -> None:
    summary = {"algo": {"metrics": {"overdue_count": 0}}, "warnings": []}
    recent_versions = [{"version": version} for version in range(60, 10, -1)]
    history_service = _HistoryServiceStub(summary, versions=recent_versions, latest_version=60)
    app = _build_app(monkeypatch, history_service)
    client = app.test_client()

    response = client.get("/scheduler/analysis?version=1")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["version_resolution"]["status"] == "ok"
    assert payload["version_resolution"]["selected_version"] == 1
    assert payload["selected"]["version"] == 1
    assert payload["selected_summary"] == summary
    assert any(int(item["version"]) == 1 for item in payload["versions"])
    assert history_service.version_limits == [50]
    assert history_service.version_queries == [1]
    assert history_service.latest_version_calls == 0
