from __future__ import annotations

import json
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
    assert f"error:{name}" in body


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
