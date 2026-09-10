"""回归测试（审计 D12）：全局 AppError 处理器的业务错误日志必须携带请求上下文
（method/path/endpoint），同文案 AppError 从不同接口抛出时日志可区分来源；
无请求上下文时降级为占位符而不是抛错；响应体与状态码保持既有行为不变。"""

from __future__ import annotations

import logging

from flask import Flask

from core.errors import ValidationError
from web.error_handlers import _request_log_context, register_error_handlers


def _build_app() -> Flask:
    app = Flask(__name__)
    register_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise ValidationError("参数不合法")

    @app.get("/boom-details")
    def boom_details():
        raise ValidationError("参数不合法", internal_details={"reason": "internal"})

    return app


def test_app_error_log_contains_request_context(caplog) -> None:
    app = _build_app()
    client = app.test_client()

    with caplog.at_level(logging.WARNING):
        resp = client.get("/boom", headers={"Accept": "application/json"})

    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload["success"] is False
    assert "参数不合法" in str(payload)

    messages = [record.getMessage() for record in caplog.records if "业务错误" in record.getMessage()]
    assert messages, caplog.text
    line = messages[0]
    assert "参数不合法" in line
    assert "method=GET" in line
    assert "path=/boom" in line
    assert "endpoint=boom" in line


def test_app_error_log_with_internal_details_still_contains_request_context(caplog) -> None:
    app = _build_app()
    client = app.test_client()

    with caplog.at_level(logging.WARNING):
        resp = client.get("/boom-details", headers={"Accept": "application/json"})

    assert resp.status_code == 400
    messages = [record.getMessage() for record in caplog.records if "业务错误" in record.getMessage()]
    assert messages, caplog.text
    line = messages[0]
    assert "path=/boom-details" in line
    assert "internal_details=" in line


def test_request_log_context_without_request_context_returns_placeholder() -> None:
    assert _request_log_context() == "method=- path=- endpoint=-"
