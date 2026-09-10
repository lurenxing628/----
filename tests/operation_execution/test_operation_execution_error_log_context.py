"""回归测试（审计 D11）：现场记录/实际情况路由的 except Exception 日志必须带可区分上下文——
按 op_id 与按 task_key 的两对端点不再写完全相同的日志文案，异常日志携带 op_id / task_key /
action，多人并发提交时能定位是哪道工序哪张任务卡的现场反馈失败；响应行为保持不变（500 + 中文提示）。"""

from __future__ import annotations

import json
import logging

from flask import Flask

import web.routes.domains.scheduler.scheduler_resource_dispatch_execution_routes as routes_mod


def _boom(*_args, **_kwargs):
    raise RuntimeError("unexpected boom")


def _call_view(view, *args, path: str = "/scheduler/resource-dispatch/execution"):
    app = Flask(__name__)
    with app.test_request_context(path):
        return view(*args)


def _assert_500_payload(resp_tuple, message_fragment: str) -> None:
    resp, status = resp_tuple
    assert status == 500
    payload = json.loads(resp.get_data(as_text=True))
    assert payload["success"] is False
    assert message_fragment in str(payload)


def test_events_by_op_id_logs_op_id(monkeypatch, caplog) -> None:
    monkeypatch.setattr(routes_mod, "_event_target_from_request", _boom)
    with caplog.at_level(logging.ERROR):
        result = _call_view(routes_mod.resource_dispatch_execution_events, 77)

    _assert_500_payload(result, "现场记录加载失败")
    assert "现场记录加载失败（op_id=77）" in caplog.text


def test_events_by_task_key_logs_task_key(monkeypatch, caplog) -> None:
    monkeypatch.setattr(routes_mod, "_execution_svc", _boom)
    with caplog.at_level(logging.ERROR):
        result = _call_view(routes_mod.resource_dispatch_execution_events_by_task, "exec_abc123")

    _assert_500_payload(result, "现场记录加载失败")
    assert "现场记录加载失败（task_key=exec_abc123）" in caplog.text


def test_actual_by_op_id_logs_op_id(monkeypatch, caplog) -> None:
    monkeypatch.setattr(routes_mod, "_json_payload", _boom)
    with caplog.at_level(logging.ERROR):
        result = _call_view(routes_mod.resource_dispatch_execution_actual, 88)

    _assert_500_payload(result, "填写实际情况失败")
    assert "填写实际情况失败（op_id=88）" in caplog.text


def test_actual_by_task_key_logs_task_key(monkeypatch, caplog) -> None:
    monkeypatch.setattr(routes_mod, "_json_payload", _boom)
    with caplog.at_level(logging.ERROR):
        result = _call_view(routes_mod.resource_dispatch_execution_actual_by_task, "exec_def456")

    _assert_500_payload(result, "填写实际情况失败")
    assert "填写实际情况失败（task_key=exec_def456）" in caplog.text


def test_legacy_feedback_logs_op_id_and_action(monkeypatch, caplog) -> None:
    """start/finish/pause/resume/report-exception 五端点共用的提交日志同样要能区分工序与动作。"""
    monkeypatch.setattr(routes_mod, "_json_payload", _boom)
    with caplog.at_level(logging.ERROR):
        result = _call_view(routes_mod.resource_dispatch_execution_start, 99)

    _assert_500_payload(result, "现场记录提交失败")
    assert "现场记录提交失败（op_id=99, action=start）" in caplog.text


def test_op_id_and_task_key_log_lines_are_distinguishable(monkeypatch, caplog) -> None:
    """同一种失败在两个端点产生的日志文案不再逐字相同（D11 的原始病灶）。"""
    monkeypatch.setattr(routes_mod, "_event_target_from_request", _boom)
    monkeypatch.setattr(routes_mod, "_execution_svc", _boom)
    with caplog.at_level(logging.ERROR):
        _call_view(routes_mod.resource_dispatch_execution_events, 1)
        _call_view(routes_mod.resource_dispatch_execution_events_by_task, "exec_k1")

    messages = [record.getMessage() for record in caplog.records if "现场记录加载失败" in record.getMessage()]
    assert len(messages) == 2
    assert messages[0] != messages[1]
