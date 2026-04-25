from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from flask import Flask, g
from werkzeug.exceptions import RequestEntityTooLarge

import web.error_boundary as error_boundary_mod
from core.infrastructure.errors import BusinessError, ErrorCode
from web.error_handlers import register_error_handlers

REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_app(*, half_dead_container: bool = False) -> Flask:
    app = Flask(__name__, template_folder=str(REPO_ROOT / "templates"))
    app.config["TESTING"] = False
    app.jinja_env.filters["tojson_zh"] = lambda value, indent=2: json.dumps(value, ensure_ascii=False, indent=indent)

    if half_dead_container:

        @app.before_request
        def _break_request_container() -> None:
            g.db = object()

    @app.route("/boom")
    def _boom():
        raise RuntimeError("boom")

    @app.route("/too-large-native")
    def _too_large_native():
        raise RequestEntityTooLarge()

    @app.route("/app-error/<name>")
    def _app_error(name: str):
        mapping = {
            "validation": ErrorCode.VALIDATION_ERROR,
            "permission": ErrorCode.PERMISSION_DENIED,
            "not-found": ErrorCode.NOT_FOUND,
            "conflict": ErrorCode.DUPLICATE_ENTRY,
            "too-large": ErrorCode.FILE_TOO_LARGE,
        }
        code = mapping[name]
        raise BusinessError(code, f"error:{name}")

    register_error_handlers(app)
    return app


@pytest.mark.parametrize(
    ("name", "expected_status", "expected_code"),
    [
        ("validation", 400, ErrorCode.VALIDATION_ERROR.value),
        ("permission", 403, ErrorCode.PERMISSION_DENIED.value),
        ("not-found", 404, ErrorCode.NOT_FOUND.value),
        ("conflict", 409, ErrorCode.DUPLICATE_ENTRY.value),
        ("too-large", 413, ErrorCode.FILE_TOO_LARGE.value),
    ],
)
def test_error_handler_maps_business_error_codes_to_http_status_for_json(
    name: str,
    expected_status: int,
    expected_code: str,
) -> None:
    app = _build_app()

    with app.test_client() as client:
        response = client.get(f"/app-error/{name}", headers={"Accept": "application/json"})

    payload = response.get_json()
    assert response.status_code == expected_status
    assert payload["success"] is False
    assert payload["error"]["code"] == expected_code


@pytest.mark.parametrize(
    ("name", "expected_status", "expected_code"),
    [
        ("permission", 403, ErrorCode.PERMISSION_DENIED.value),
        ("not-found", 404, ErrorCode.NOT_FOUND.value),
        ("conflict", 409, ErrorCode.DUPLICATE_ENTRY.value),
    ],
)
def test_error_handler_maps_business_error_codes_to_http_status_for_html(
    name: str,
    expected_status: int,
    expected_code: str,
) -> None:
    app = _build_app()

    with app.test_client() as client:
        response = client.get(f"/app-error/{name}")

    body = response.get_data(as_text=True)
    assert response.status_code == expected_status
    assert expected_code in body
    assert f"error:{name}" not in body
    assert "发生错误" in body


def test_json_error_payload_hides_non_validation_internal_message() -> None:
    app = _build_app()

    @app.get("/non-validation-internal-error")
    def _non_validation_internal_error():
        raise BusinessError(
            ErrorCode.DB_QUERY_ERROR,
            "sqlite OperationalError at /tmp/private.db: secret_token could not be loaded",
        )

    with app.test_client() as client:
        response = client.get("/non-validation-internal-error", headers={"Accept": "application/json"})

    payload = response.get_json()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert response.status_code == 400
    assert payload["error"]["code"] == ErrorCode.DB_QUERY_ERROR.value
    assert payload["error"]["message"] == "数据访问失败，请稍后重试。"
    assert "sqlite" not in serialized
    assert "/tmp/private.db" not in serialized
    assert "secret_token" not in serialized


def test_validation_error_message_hides_path_after_chinese_colon() -> None:
    exc = BusinessError(
        ErrorCode.VALIDATION_ERROR,
        "文件错误：/tmp/private.xlsx",
        details={"field": "start_date"},
    )

    assert error_boundary_mod.user_visible_app_error_message(exc) == "开始日期填写不正确，请检查后重试。"
    assert error_boundary_mod.user_visible_app_error_details(exc) == {"field": "开始日期"}


def test_non_validation_public_chinese_slash_message_is_not_genericized() -> None:
    message = "外部/内部归属已存在，请改用覆盖/追加方式。"
    exc = BusinessError(ErrorCode.DUPLICATE_ENTRY, message)

    assert error_boundary_mod.user_visible_app_error_message(exc) == message


def test_error_handler_500_page_does_not_depend_on_main_site_routes() -> None:
    app = _build_app()

    with app.test_client() as client:
        response = client.get("/boom")

    body = response.get_data(as_text=True)
    assert response.status_code == 500
    assert "服务" in body
    assert "错误" in body


def test_error_handler_500_page_survives_half_dead_request_container() -> None:
    app = _build_app(half_dead_container=True)

    with app.test_client() as client:
        response = client.get("/boom")

    body = response.get_data(as_text=True)
    assert response.status_code == 500
    assert "服务" in body
    assert "错误" in body


def test_error_handler_request_entity_too_large_keeps_unified_file_too_large_contract() -> None:
    app = _build_app()

    with app.test_client() as client:
        response = client.get("/too-large-native", headers={"Accept": "application/json"})

    payload = response.get_json()
    assert response.status_code == 413
    assert payload["success"] is False
    assert payload["error"]["code"] == ErrorCode.FILE_TOO_LARGE.value
    assert "16MB" in payload["error"]["message"]


def test_error_boundary_import_does_not_load_scheduler_service_aggregate() -> None:
    script = """
import sys
import web.error_boundary
print("core.services.scheduler" in sys.modules)
print("core.services.scheduler.schedule_service" in sys.modules)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.splitlines() == ["False", "False"]


def test_error_boundary_field_label_lookup_does_not_load_scheduler_service_aggregate() -> None:
    script = """
import sys
import web.error_boundary
print(web.error_boundary.get_user_visible_field_label("objective"))
print("core.services.scheduler.schedule_service" in sys.modules)
print("core.services.scheduler.resource_dispatch_service" in sys.modules)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    lines = completed.stdout.splitlines()
    assert lines[0] == "优化目标"
    assert lines[1:] == ["False", "False"]


def test_json_error_payload_keeps_internal_details_out_of_public_response() -> None:
    app = _build_app()

    @app.get("/diagnostic-error")
    def _diagnostic_error():
        raise BusinessError(
            ErrorCode.VALIDATION_ERROR,
            "query_date格式不正确，应为 YYYY-MM-DD",
            details={
                "field": "query_date",
                "reason": "invalid_query_date",
                "file_path": "/tmp/private.xlsx",
                "sheet": "Sheet1",
            },
        )

    with app.test_client() as client:
        response = client.get("/diagnostic-error", headers={"Accept": "application/json"})

    payload = response.get_json()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert response.status_code == 400
    assert payload["error"]["message"] == "查询日期填写不正确，请检查后重试。"
    assert payload["error"]["details"] == {"field": "查询日期"}
    assert payload["error"]["diagnostics"] == {"reason": "invalid_query_date"}
    assert "file_path" not in serialized
    assert "/tmp/private.xlsx" not in serialized
    assert "Sheet1" not in serialized


def test_json_error_payload_does_not_expose_unknown_machine_field_or_unlisted_reason() -> None:
    app = _build_app()

    @app.get("/unknown-field-error")
    def _unknown_field_error():
        raise BusinessError(
            ErrorCode.VALIDATION_ERROR,
            "include_history 不合法（期望布尔值）",
            details={
                "field": "include_history",
                "reason": "private/sql/path",
            },
        )

    with app.test_client() as client:
        response = client.get("/unknown-field-error", headers={"Accept": "application/json"})

    payload = response.get_json()
    serialized = json.dumps(payload, ensure_ascii=False)
    assert response.status_code == 400
    assert payload["error"]["message"] == "参数填写不正确，请检查后重试。"
    assert "details" not in payload["error"]
    assert "diagnostics" not in payload["error"]
    assert "include_history" not in serialized
    assert "private/sql/path" not in serialized


def test_json_error_payload_keeps_invalid_query_keys_machine_readable() -> None:
    app = _build_app()

    @app.get("/invalid-query-keys-error")
    def _invalid_query_keys_error():
        raise BusinessError(
            ErrorCode.VALIDATION_ERROR,
            "scope_type 不合法",
            details={
                "field": "scope_type",
                "invalid_query_keys": ["scope_type", "secret_token", "operator_id"],
            },
        )

    with app.test_client() as client:
        response = client.get("/invalid-query-keys-error", headers={"Accept": "application/json"})

    payload = response.get_json()
    assert response.status_code == 400
    assert payload["error"]["details"]["invalid_query_keys"] == ["scope_type", "operator_id"]
    assert payload["error"]["details"]["invalid_query_labels"] == ["范围类型", "人员"]
    assert "secret_token" not in json.dumps(payload, ensure_ascii=False)


def test_html_error_payload_renders_invalid_query_labels_without_machine_keys() -> None:
    app = _build_app()

    @app.get("/invalid-query-keys-html")
    def _invalid_query_keys_html():
        raise BusinessError(
            ErrorCode.VALIDATION_ERROR,
            "scope_type 不合法",
            details={
                "field": "scope_type",
                "invalid_query_keys": ["scope_type", "secret_token", "operator_id"],
            },
        )

    with app.test_client() as client:
        response = client.get("/invalid-query-keys-html")

    body = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "范围类型" in body
    assert "人员" in body
    assert "scope_type" not in body
    assert "operator_id" not in body
    assert "secret_token" not in body
    assert "invalid_query_keys" not in body


def test_render_error_template_renders_rich_error_template_path() -> None:
    app = _build_app()

    with app.test_request_context("/boom"):
        body = error_boundary_mod.render_error_template(
            title="配置错误",
            code="400",
            message="请修复配置后重试",
            field_label="目标字段",
        )

    assert 'class="card"' in body
    assert "配置错误" in body
    assert "400" in body
    assert "目标字段" in body


def test_render_error_template_falls_back_to_minimal_page_when_template_render_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_app()

    monkeypatch.setattr(
        error_boundary_mod,
        "render_template",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with app.test_request_context("/boom"):
        body = error_boundary_mod.render_error_template(
            title="配置错误",
            code="400",
            message="请修复配置后重试",
            field_label="目标字段",
        )

    assert "配置错误" in body
    assert "400" in body
    assert "目标字段" in body
    assert "<!doctype html>" in body.lower()
