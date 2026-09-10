"""A4 keeps old helper identities without borrowing the route assembly directory."""

from __future__ import annotations

import ast

from flask import Flask

from tests._support.dependency_boundaries import assert_import_orders, assert_no_import_prefixes
from tests._support.paths import REPO_ROOT
from web.routes import (
    enum_display,
    excel_utils,
    form_values,
    history_summary_logging,
    navigation_utils,
    normalizers,
    pagination,
)
from web.routes.helpers import enum_display as leaf_enum
from web.routes.helpers import excel_utils as leaf_excel
from web.routes.helpers import form_values as leaf_form
from web.routes.helpers import history_summary_logging as leaf_history
from web.routes.helpers import navigation_utils as leaf_navigation
from web.routes.helpers import normalizers as leaf_normalizers
from web.routes.helpers import pagination as leaf_pagination

PAIRS = (
    (enum_display, leaf_enum), (excel_utils, leaf_excel), (form_values, leaf_form),
    (history_summary_logging, leaf_history), (navigation_utils, leaf_navigation),
    (normalizers, leaf_normalizers), (pagination, leaf_pagination),
)


def test_old_helper_objects_and_import_orders_remain_identical():
    for legacy, canonical in PAIRS:
        tree = ast.parse(REPO_ROOT.joinpath(canonical.__file__).read_text(encoding="utf-8"))
        names = [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
        for name in names:
            assert getattr(legacy, name) is getattr(canonical, name)
        assert_import_orders(legacy.__name__, canonical.__name__, names)


def test_helper_leaves_do_not_import_route_assembly_or_scheduler_domains():
    root = REPO_ROOT / "web/routes/helpers"
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.parse((root / "__init__.py").read_text()).body)
    for path in root.glob("*.py"):
        assert_no_import_prefixes(path, ("web.routes",))
    old_modules = {"web.routes." + legacy.__name__.rsplit(".", 1)[-1] for legacy, _ in PAIRS}
    for path in (REPO_ROOT / "web/routes/domains/scheduler").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in old_modules, (path, node.lineno)
                assert not (node.level == 3 and "web.routes." + (node.module or "") in old_modules), (path, node.lineno)
    compatibility_paths = {legacy.__file__ for legacy, _ in PAIRS}
    for path in (REPO_ROOT / "web/routes").glob("*.py"):
        if str(path) in compatibility_paths:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in old_modules, (path, node.lineno)
                assert not (node.level == 1 and "web.routes." + (node.module or "") in old_modules), (path, node.lineno)


def test_excel_hmac_patch_is_the_real_execution_object(monkeypatch):
    assert excel_utils.hmac is leaf_excel.hmac
    calls = []
    monkeypatch.setattr(excel_utils.hmac, "compare_digest", lambda left, right: calls.append((left, right)) or True)
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "a4-test"
    with app.app_context():
        assert excel_utils.preview_baseline_matches(
            "token", existing_data={}, mode=excel_utils.ImportMode.APPEND, id_column="id", rows=[]
        )
    assert len(calls) == 1
