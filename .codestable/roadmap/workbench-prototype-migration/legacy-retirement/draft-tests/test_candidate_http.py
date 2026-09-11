"""Private candidate HTTP: normal registration, real parsers and one real import.

Only the reviewed template-target functions are loaded from candidate source in
memory. Product files, production startup and services are not switched by flags.
"""

import ast
import copy
import importlib
import io
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qsl, urlsplit

from candidate_sources import PAYLOAD, RENDER_TARGETS, REPO, render_source

sys.path.insert(0, str(REPO))

from flask import Flask, g
from test_dispatch_samples import DISPATCH, PRESENTATION
from werkzeug.datastructures import MultiDict

from core.services.common.excel_templates import build_xlsx_bytes
from core.services.common.plan_query import SchedulePlanQueryService
from core.services.scheduler.gantt_service import GanttService
from tests.workbench.final_legacy_navigation_support import prepare_database
from tests.workbench.plan_read_support import connect
from web.bootstrap.factory import _register_all_blueprints
from web.routes.workbench.navigation_boot import read_navigation


class FormFields(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fields, self.textarea = {}, None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "input" and values.get("name"):
            self.fields[values["name"]] = values.get("value", "")
        if tag == "textarea" and values.get("name"):
            self.textarea = values["name"]
            self.fields[self.textarea] = ""

    def handle_data(self, data):
        if self.textarea:
            self.fields[self.textarea] += data

    def handle_endtag(self, tag):
        if tag == "textarea":
            self.textarea = None


class CandidateHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aps-g-candidate-http-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "candidate.db"
        prepare_database(self.path)
        self.app = Flask("private-candidate-http", template_folder=str(PAYLOAD / "templates"))
        self.app.config.update(TESTING=True, SECRET_KEY="private-session", BASE_DIR=str(REPO),
                               EXCEL_TEMPLATE_DIR=self.temp.name)
        _register_all_blueprints(self.app)
        self._load_candidate_renderers()

        @self.app.before_request
        def database():
            g.db = connect(self.path)
            g.op_logger = None
            g.app_logger = None
            plan_query = SchedulePlanQueryService(g.db)
            g.services = SimpleNamespace(schedule_plan_query_service=plan_query,
                                          gantt_service=GanttService(g.db, plan_query_service=plan_query))

        @self.app.teardown_request
        def close_database(_error):
            if hasattr(g, "db"):
                g.db.close()

        self.original = dict(self.app.view_functions)
        DISPATCH.install_legacy_retirement(self.app)
        self.client = self.app.test_client()

    def _load_candidate_renderers(self):
        route_endpoints = {"config_manual_page": "scheduler.config_manual_page",
                           "week_plan_print_page": "scheduler.week_plan_print_page"}
        for path, old, new in RENDER_TARGETS:
            _before, source, _line = render_source(path, old, new)
            module = importlib.import_module(path[:-3].replace("/", "."))
            for node in ast.parse(source).body:
                if not isinstance(node, ast.FunctionDef):
                    continue
                if not any(isinstance(child, ast.Str) and child.s == new for child in ast.walk(node)):
                    continue
                candidate = copy.deepcopy(node)
                candidate.decorator_list = []
                namespace = dict(module.__dict__)
                exec(compile(ast.Module(body=[candidate], type_ignores=[]), str(PAYLOAD / path), "exec"), namespace)
                function = namespace[candidate.name]
                if candidate.name in route_endpoints:
                    self.app.view_functions[route_endpoints[candidate.name]] = function
                else:
                    replacement = patch.object(module, candidate.name, function)
                    replacement.start()
                    self.addCleanup(replacement.stop)

    def state(self):
        conn = connect(self.path)
        try:
            return list(conn.iterdump())
        finally:
            conn.close()

    def test_all_113_post_and_39_nonpage_get_handlers_remain_same_functions(self):
        import json
        matrix = json.loads((PAYLOAD.parent / "routes-matrix.json").read_text(encoding="utf-8"))["routes"]
        old = [row for row in matrix if row["endpoint"] != "static" and not row["endpoint"].startswith("workbench.")]
        posts = [row for row in old if row["methods"] == ["POST"]]
        others = [row for row in old if row["methods"] == ["GET"] and row["endpoint"] not in DISPATCH.PAGE_POLICIES]
        self.assertEqual((len(posts), len(others)), (113, 39))
        for row in posts + others:
            self.assertIs(self.app.view_functions[row["endpoint"]], self.original[row["endpoint"]])
        self.assertEqual(len(PRESENTATION.RESULT_ENDPOINTS), 24)

    def test_real_legacy_get_redirect_and_410_do_not_mutate_database(self):
        before = self.state()
        response = self.client.get("/scheduler/gantt?version=3&start_date=2026-09-09&end_date=2026-09-10")
        self.assertEqual(response.status_code, 302)
        args = MultiDict(parse_qsl(urlsplit(response.location).query))
        navigation = read_navigation("gantt", args)
        self.assertIsNotNone(navigation)
        assert navigation is not None
        self.assertEqual(navigation["context"]["range_end"], "2026-09-11T00:00:00")
        for url in ("/scheduler/gantt?version=3&gantt_resource=PRIVATE-M1", "/scheduler/config"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 410)
            self.assertNotIn("PRIVATE-", response.get_data(as_text=True))
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(self.state(), before)

    def test_actual_preview_confirm_rejection_and_persistence_keep_business_contract(self):
        before = self.state()
        workbook = build_xlsx_bytes(["工号", "姓名", "状态", "班组", "备注"], [["G-NEW", "新增人员", "在岗", None, "原备注"]])
        response = self.client.post("/excel-demo/preview", data={"mode": "append", "file": (io.BytesIO(workbook.getvalue()), "人员.xlsx")})
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("原入口提交结果", html)
        self.assertIn("新增人员", html)
        self.assertNotIn("static/js/", html)
        self.assertEqual(before, self.state())
        parsed = FormFields()
        parsed.feed(html)
        form = parsed.fields
        self.assertTrue(form["preview_baseline"])
        self.assertTrue(form["raw_rows_json"])
        rejected = self.client.post("/excel-demo/confirm", data={**form, "preview_baseline": "stale"})
        self.assertEqual(rejected.status_code, 200)
        self.assertIn("数据已变化", rejected.get_data(as_text=True))
        self.assertEqual(before, self.state())
        response = self.client.post("/excel-demo/confirm", data=form)
        self.assertEqual(response.status_code, 302)
        conn = connect(self.path)
        try:
            row = conn.execute("SELECT name,status,remark FROM Operators WHERE operator_id='G-NEW'").fetchone()
            self.assertEqual(tuple(row), ("新增人员", "active", "原备注"))
            self.assertIsNotNone(conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='operator' AND entity_key='G-NEW'").fetchone())
        finally:
            conn.close()

    def test_actual_manual_route_uses_new_presentation_and_keeps_original_download(self):
        response = self.client.get("/scheduler/config/manual")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("说明书正文", html)
        self.assertIn("说明书目录", html)
        self.assertNotIn("config_manual.js", html)
        response = self.client.get("/scheduler/config/manual/download")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers.get("Content-Disposition", ""))
        self.assertEqual(response.data, (REPO / "static/docs/scheduler_manual.md").read_bytes())
        response.close()

    def test_actual_print_handler_keeps_task_identity_scope_and_print_action(self):
        before = self.state()
        response = self.client.get("/scheduler/week-plan/print?version=3&week_start=2026-09-07&group_by=machine&day=2026-09-09")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for value in ("v3", "CAT-B", "2026-09-09", "window.print()", "备注"):
            self.assertIn(value, html)
        self.assertNotIn("static/css/", html)
        self.assertEqual(self.state(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
