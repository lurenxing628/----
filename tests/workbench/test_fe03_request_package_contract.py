"""FE-03: passive package imports and exact explicit factory registration."""

import ast
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from urllib.parse import unquote, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name("fe03_route_manifest.json")
REGISTRARS = (
    "material", "resource", "resource_relation", "resource_table", "material_action", "resource_action",
    "calendar", "batch", "process_read", "process_write", "process_collection", "process_table",
    "process_file", "plan_read", "execution", "actual_gantt", "preflight", "scheduling_job",
    "run_candidate", "run_candidate_adoption", "run_candidate_baseline", "run_history", "report",
    "calibration", "calibration_adoption", "dashboard", "outsourcing", "master_overview",
    "system_maintenance", "trial", "trial_adoption", "trial_adoption_history",
)


def route_manifest(app):
    return [{"rule": row.rule, "endpoint": row.endpoint, "methods": sorted(row.methods),
             "defaults": row.defaults, "strict_slashes": row.strict_slashes}
            for row in app.url_map.iter_rules() if row.endpoint.startswith("workbench.")]


def test_registration_keeps_all_named_static_imports_and_original_order():
    tree = ast.parse((ROOT / "web/routes/workbench/registration.py").read_text(encoding="utf-8"))
    expected = ["register_" + name + "_routes" for name in REGISTRARS]
    calls = [node.value for node in tree.body if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)]
    assert [node.func.id for node in calls if isinstance(node.func, ast.Name)] == expected
    assert all(len(node.args) == 1 and isinstance(node.args[0], ast.Name)
               and node.args[0].id == "bp" and not node.keywords for node in calls)
    imports = [alias.name for node in tree.body if isinstance(node, ast.ImportFrom) for alias in node.names]
    assert set(imports) == set(expected + ["bp"])
    assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in tree.body)
    package = ast.parse((ROOT / "web/routes/workbench/__init__.py").read_text(encoding="utf-8"))
    assert len(package.body) == 1 and isinstance(package.body[0], ast.Expr)
    assert isinstance(package.body[0].value, ast.Constant) and isinstance(package.body[0].value.value, str)


@pytest.mark.parametrize("module", ["api_responses", "pages", "system_actions", "materials"])
def test_importing_one_submodule_does_not_register_other_workspaces(module):
    script = dedent("""
        import importlib, json, sqlite3, sys
        from unittest.mock import patch
        with patch.object(sqlite3, "connect", side_effect=AssertionError("module import opened a DB")):
            import web.routes.workbench as package
            assert not hasattr(package, "bp")
            importlib.import_module("web.routes.workbench." + sys.argv[1])
            forbidden = ("registration", "actual_gantt", "trial_adoption", "calibration_adoption", "run_history")
            assert not any("web.routes.workbench." + name in sys.modules for name in forbidden)
            assert "web.bootstrap.factory" not in sys.modules
            from flask import Flask
            from web.routes.workbench.registration import bp
            from web.routes.workbench.pages import normalize_read_failure
            app = Flask("fe03-single-import")
            app.register_blueprint(bp)
            rows = [{"rule": row.rule, "endpoint": row.endpoint, "methods": sorted(row.methods),
                     "defaults": row.defaults, "strict_slashes": row.strict_slashes}
                    for row in app.url_map.iter_rules() if row.endpoint.startswith("workbench.")]
            assert app.after_request_funcs[None].count(normalize_read_failure) == 1
            response = app.test_client().get("/api/workbench/v1/fe03-missing")
            assert response.status_code == 404 and response.get_json()["ok"] is False
            print(json.dumps(rows))
    """)
    result = subprocess.run([sys.executable, "-c", script, module], cwd=str(ROOT),
                            capture_output=True, text=True, timeout=30, check=True)
    assert json.loads(result.stdout) == json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_two_factory_apps_keep_exact_routes_boundaries_and_admission_order(db_env, tmp_path, monkeypatch):
    from web.bootstrap import factory
    from web.routes.workbench.pages import normalize_read_failure

    connect = sqlite3.connect

    def isolated(database, *args, **kwargs):
        raw = os.fspath(database)
        if raw != ":memory:":
            path = unquote(urlparse(raw).path) if raw.startswith("file:") else raw
            Path(path).resolve().relative_to(tmp_path.resolve())
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated)
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    apps = []
    try:
        for name in ("first", "second"):
            monkeypatch.setenv("APS_DB_PATH", str(tmp_path / (name + ".db")))
            app = factory.create_app_core(ui_mode="default", enable_secret_key=False,
                                          enable_security_headers=False, enable_session_cookie_hardening=False)
            apps.append(app)
            app.config["TESTING"] = True
            assert route_manifest(app) == expected
            assert app.after_request_funcs[None].count(normalize_read_failure) == 1
            assert [hook.__name__ for hook in app.before_request_funcs[None]][:2] == ["admit_request", "_open_db"]
            client = app.test_client()
            for method, path, status in (("GET", "/api/workbench/v1/fe03-missing", 404),
                                         ("POST", "/api/workbench/v1/system/overview", 405)):
                response = client.open(path, method=method, buffered=True)
                assert response.status_code == status
                assert response.get_json()["ok"] is False
                assert response.headers["Cache-Control"] == "no-store"
            gate = app.extensions["workbench_request_lifecycle"]
            assert gate.status["active"] == 0
        assert apps[0] is not apps[1]
        assert apps[0].extensions["workbench_request_lifecycle"] is not apps[1].extensions["workbench_request_lifecycle"]
    finally:
        for app in apps:
            assert app.extensions["workbench_request_lifecycle"].shutdown()
