"""回归测试：Excel 预览基线令牌(preview_baseline)的比对与确认路由防护——preview_baseline_matches 对相等令牌返 True、不等返 False，
hmac.compare_digest 抛错时吞异常返 False 并以「检查结果状态比较失败」记日志；build_preview_baseline_token 必须带 rows、load_confirm_payload 缺基线用大白话报「检查结果已失效」；
并用 AST 静态扫描 web/routes：所有 excel 确认路由须先 load_confirm_payload 再 preview_baseline_is_stale 校验、且写库调用不得早于基线校验、基线令牌调用必须传 rows。"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from flask import Flask

from core.infrastructure.errors import ValidationError
from core.services.common.excel_service import ImportMode
from tests._support.paths import REPO_ROOT
from web.routes import excel_utils as excel_utils_mod
from web.routes.excel_utils import (
    build_preview_baseline_token,
    load_confirm_payload,
    parse_preview_rows_json,
    preview_baseline_matches,
)


def _baseline_kwargs():
    return {
        "existing_data": {"A001": {"编号": "A001", "值": 1}},
        "mode": ImportMode.APPEND,
        "id_column": "编号",
        "extra_state": {"scope": "unit-test"},
        "rows": [{"编号": "A001", "值": 2}],
    }


def test_preview_baseline_matches_returns_true_for_equal_token() -> None:
    kwargs = _baseline_kwargs()
    token = build_preview_baseline_token(**kwargs)
    app = Flask(__name__)

    with app.app_context():
        assert preview_baseline_matches(token, **kwargs) is True


def test_preview_baseline_matches_returns_false_for_different_token() -> None:
    kwargs = _baseline_kwargs()
    token = build_preview_baseline_token(**kwargs)
    app = Flask(__name__)

    with app.app_context():
        assert preview_baseline_matches(token + "-changed", **kwargs) is False


def test_preview_baseline_matches_returns_false_when_compare_digest_raises(monkeypatch) -> None:
    kwargs = _baseline_kwargs()
    token = build_preview_baseline_token(**kwargs)
    app = Flask(__name__)
    logged = []

    def _raise_compare_digest(*args, **kwargs):
        raise RuntimeError("compare exploded")

    def _fake_exception(message, *args, **kwargs):
        logged.append(message % args if args else str(message))

    monkeypatch.setattr(excel_utils_mod.hmac, "compare_digest", _raise_compare_digest)
    monkeypatch.setattr(app.logger, "exception", _fake_exception)

    with app.app_context():
        assert preview_baseline_matches(token, **kwargs) is False

    assert logged == ["检查结果状态比较失败"]


def test_preview_baseline_requires_rows() -> None:
    kwargs = _baseline_kwargs()
    kwargs.pop("rows")

    with pytest.raises(TypeError, match="rows"):
        build_preview_baseline_token(**kwargs)


def test_parse_preview_rows_json_rejects_plain_json_payload() -> None:
    with pytest.raises(ValidationError, match="检查数据解析失败|检查数据格式不正确"):
        parse_preview_rows_json('[{"编号": "A001"}]')


def test_load_confirm_payload_missing_baseline_uses_plain_language() -> None:
    with pytest.raises(ValidationError) as excinfo:
        load_confirm_payload("aps-preview-json-b64:W10=", "")

    message = str(excinfo.value)
    assert "检查结果已失效" in message
    assert "检查基线" not in message


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _route_decorator_path(node: ast.AST) -> str:
    if not isinstance(node, ast.Call) or not node.args:
        return ""
    if _call_name(node.func) not in {"post", "route"}:
        return ""
    first_arg = node.args[0]
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        return first_arg.value
    return ""


def _is_confirm_write_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    return _call_name(node.func) in {
        "apply_preview_rows",
        "apply_import_links",
        "delete_all_no_tx",
        "execute_preview_rows_transactional",
        "import_operator_calendar_from_preview_rows",
        "import_from_preview_rows",
        "upsert_and_parse_no_tx",
        "upsert_no_tx",
    }


def test_route_preview_baseline_calls_include_rows_fingerprint() -> None:
    checked_names = {"build_preview_baseline_token", "preview_baseline_is_stale"}
    missing_rows = []
    for path in sorted((REPO_ROOT / "web" / "routes").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _call_name(node.func) not in checked_names:
                continue
            rows_keywords = [keyword for keyword in node.keywords if keyword.arg == "rows"]
            if not rows_keywords or any(
                isinstance(keyword.value, ast.Constant) and keyword.value.value is None for keyword in rows_keywords
            ):
                rel = path.relative_to(REPO_ROOT).as_posix()
                missing_rows.append(f"{rel}:{node.lineno}")

    assert missing_rows == []


def test_confirm_routes_validate_preview_baseline_after_loading_payload() -> None:
    missing_validation = []
    wrong_order = []
    for path in sorted((REPO_ROOT / "web" / "routes").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            route_paths = [_route_decorator_path(decorator) for decorator in node.decorator_list]
            is_confirm_route = any(route_path.endswith("/confirm") for route_path in route_paths)
            rel = path.relative_to(REPO_ROOT).as_posix()
            if is_confirm_route and "excel" not in rel:
                continue
            payload_calls = [
                child.lineno
                for child in ast.walk(node)
                if isinstance(child, ast.Call) and _call_name(child.func) == "load_confirm_payload"
            ]
            baseline_calls = [
                child.lineno
                for child in ast.walk(node)
                if isinstance(child, ast.Call) and _call_name(child.func) == "preview_baseline_is_stale"
            ]
            write_calls = [child.lineno for child in ast.walk(node) if _is_confirm_write_call(child)]
            if is_confirm_route and not payload_calls:
                missing_validation.append(f"{rel}:{node.name}:load_confirm_payload")
            if is_confirm_route and not baseline_calls:
                missing_validation.append(f"{rel}:{node.name}:preview_baseline_is_stale")
            if payload_calls and baseline_calls and min(baseline_calls) < min(payload_calls):
                wrong_order.append(f"{rel}:{node.name}")
            if baseline_calls and write_calls and min(write_calls) < min(baseline_calls):
                wrong_order.append(f"{rel}:{node.name}:write_before_preview_baseline_is_stale")
            has_confirm_payload = any(
                isinstance(child, ast.Call) and _call_name(child.func) == "load_confirm_payload"
                for child in ast.walk(node)
            )
            if not has_confirm_payload:
                continue
            has_baseline_check = any(
                isinstance(child, ast.Call) and _call_name(child.func) == "preview_baseline_is_stale"
                for child in ast.walk(node)
            )
            if not has_baseline_check:
                missing_validation.append(f"{rel}:{node.name}")

    assert missing_validation == []
    assert wrong_order == []
