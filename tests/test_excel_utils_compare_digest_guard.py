from __future__ import annotations

from flask import Flask

from core.services.common.excel_service import ImportMode
from web.routes import excel_utils as excel_utils_mod
from web.routes.excel_utils import build_preview_baseline_token, preview_baseline_matches


def _baseline_kwargs():
    return {
        "existing_data": {"A001": {"编号": "A001", "值": 1}},
        "mode": ImportMode.APPEND,
        "id_column": "编号",
        "extra_state": {"scope": "unit-test"},
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

    assert logged == ["预览基线签名比较失败"]
