"""Draft-only plumbing/template checks; these are not real-backend acceptance."""

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

from flask import Flask, flash, render_template, request

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "draft-payload"
sys.path.insert(0, str(ROOT.parents[3]))
PRESENTATION_SPEC = importlib.util.spec_from_file_location(
    "web.routes.workbench.legacy_presentation", PAYLOAD / "web/routes/workbench/legacy_presentation.py")
if PRESENTATION_SPEC is None or PRESENTATION_SPEC.loader is None:
    raise RuntimeError("Draft presentation is missing.")
PRESENTATION = importlib.util.module_from_spec(PRESENTATION_SPEC)
sys.modules[PRESENTATION_SPEC.name] = PRESENTATION
PRESENTATION_SPEC.loader.exec_module(PRESENTATION)
SPEC = importlib.util.spec_from_file_location(
    "retirement_dispatch_sample", PAYLOAD / "web/routes/workbench/legacy_dispatch.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Draft dispatcher is missing.")
DISPATCH = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DISPATCH
SPEC.loader.exec_module(DISPATCH)
REF = "a" * 48


class DispatcherSamples(unittest.TestCase):
    def setUp(self):
        self.app = Flask("retirement_sample", template_folder=str(PAYLOAD / "templates"))
        self.app.config.update(TESTING=True, SECRET_KEY="draft-only-memory-session")
        self.calls = []
        self.converted = []

        def original(**values):
            self.calls.append((request.endpoint, request.method, list(request.form.items(multi=True)), values))
            return "ORIGINAL:" + request.endpoint

        for endpoint in DISPATCH.PAGE_POLICIES:
            self.app.add_url_rule("/sample/" + endpoint, endpoint, original, methods=["GET", "POST"])
        self.app.add_url_rule("/system/health", "health", lambda: ("{\"status\":\"ok\"}", 200, {"Content-Type": "application/json"}))
        self.app.add_url_rule("/download", "download", lambda: (b"file-bytes", 200, {"Content-Disposition": "attachment; filename=data.xlsx"}))
        self.app.add_url_rule("/api/workbench/v1/example", "api", lambda: {"ok": True})
        self.restyled = {"scheduler.week_plan_print_page": lambda: "NEW PRINT: not executable",
                         "scheduler.config_manual_page": lambda: "NEW MANUAL"}

    def convert(self, legacy):
        self.converted.append(legacy)
        if DISPATCH.PAGE_POLICIES[legacy.endpoint] == "retired":
            return DISPATCH.LegacyGetDecision("retired", reason_code="no_equivalent", message="旧入口已退役。")
        return DISPATCH.LegacyGetDecision("redirect", view="gantt", context={"plan_ref": REF})

    @staticmethod
    def destination(decision):
        nav = {"version": 1, "view": decision.view, "context": decision.context}
        return "/workbench?" + urlencode({"view": decision.view, "nav": json.dumps(nav)})

    def install(self, **overrides):
        values = {"convert_get": self.convert, "build_destination": self.destination,
                  "render_retired": lambda decision: render_template("workbench/retired.html", decision=decision),
                  "restyled_views": self.restyled, **overrides}
        DISPATCH.install_legacy_page_adapters(self.app, **values)

    def test_get_passes_all_original_query_values_to_converter(self):
        self.install()
        response = self.app.test_client().get("/sample/scheduler.gantt_page?version=7&plan_role=score_best&start_date=2026-09-10")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.converted[0].query, (("version", "7"), ("plan_role", "score_best"), ("start_date", "2026-09-10")))
        nav = json.loads(parse_qs(urlsplit(response.location).query)["nav"][0])
        self.assertEqual(nav["context"], {"plan_ref": REF})
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_post_parsing_and_confirmation_are_not_replaced_with_410(self):
        self.install()
        response = self.app.test_client().post("/sample/scheduler.excel_batches_page", data={"mode": "replace", "raw_rows_json": "original-payload", "preview_baseline": "original-baseline"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "ORIGINAL:scheduler.excel_batches_page")
        self.assertEqual(dict(self.calls[0][2]), {"mode": "replace", "raw_rows_json": "original-payload", "preview_baseline": "original-baseline"})
        self.assertEqual(self.converted, [])

    def test_head_and_duplicate_query(self):
        self.install()
        client = self.app.test_client()
        response = client.head("/sample/scheduler.gantt_page")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.get_data(), b"")
        self.assertEqual(client.get("/sample/scheduler.gantt_page?version=7&version=7").status_code, 400)
        self.assertEqual(client.get("/sample/scheduler.week_plan_print_page?day=a&day=a").status_code, 400)

    def test_retired_page_never_calls_original_renderer(self):
        self.install()
        response = self.app.test_client().get("/sample/scheduler.config_page")
        self.assertEqual(response.status_code, 410)
        self.assertIn("旧入口已退役", response.get_data(as_text=True))
        self.assertEqual(self.calls, [])

    def test_new_print_and_manual_are_required_and_used(self):
        before = dict(self.app.view_functions)
        with self.assertRaises(RuntimeError):
            self.install(restyled_views={})
        self.assertEqual(before, self.app.view_functions)
        self.install()
        self.assertEqual(self.app.test_client().get("/sample/scheduler.week_plan_print_page").get_data(as_text=True), "NEW PRINT: not executable")

    def test_non_page_health_download_and_json_are_untouched(self):
        before = {name: self.app.view_functions[name] for name in ("health", "download", "api", "static")}
        self.install()
        self.assertEqual(before, {name: self.app.view_functions[name] for name in before})
        client = self.app.test_client()
        self.assertEqual(client.get("/system/health").get_json(), {"status": "ok"})
        self.assertEqual(client.get("/download").data, b"file-bytes")
        self.assertEqual(client.get("/api/workbench/v1/example").get_json(), {"ok": True})

    def test_incomplete_registration_and_double_install_fail_closed(self):
        del self.app.view_functions["scheduler.config_page"]
        before = dict(self.app.view_functions)
        with self.assertRaises(RuntimeError):
            self.install()
        self.assertEqual(before, self.app.view_functions)

    def test_second_install_and_bad_destination_are_not_fallbacks(self):
        self.install(build_destination=lambda decision: "https://example.invalid/")
        with self.assertRaises(RuntimeError):
            self.install()
        with self.assertRaises(RuntimeError):
            self.app.test_client().get("/sample/scheduler.gantt_page")
        self.assertEqual(self.calls, [])


class PresentationSamples(unittest.TestCase):
    def setUp(self):
        self.app = Flask("retirement_presentation", template_folder=str(PAYLOAD / "templates"))
        self.app.secret_key = "draft-only-memory-session"
        self.app.add_url_rule("/", "scheduler.excel_batches_preview", lambda: None)
        PRESENTATION.install_legacy_presentation(self.app)

    def render(self, template, **values):
        with self.app.test_request_context():
            flash("原请求存在问题，未宣称全部成功。", "warning")
            return render_template(template, **values)

    @staticmethod
    def row(status="new"):
        return SimpleNamespace(row_num=2, status=SimpleNamespace(value=status), message="已检查",
                               data={"批次号": "B-001", "source_row_id": "PRIVATE-HIDDEN"}, changes={})

    def result(self, **changes):
        values = {"title": "批次检查结果", "preview_rows": [self.row()], "raw_rows_json": "encoded-original-rows",
                  "preview_baseline": "exact-original-baseline", "mode": "replace", "filename": "original.xlsx",
                  "auto_generate_ops": True, "strict_mode_supported": True, "strict_mode": False,
                  "confirm_url": "/scheduler/excel/batches/confirm", **changes}
        return self.render("workbench/legacy_result.html", **values)

    def test_confirmation_preserves_all_original_fields_and_has_no_old_assets(self):
        html = self.result()
        for name in ("mode", "filename", "preview_baseline", "raw_rows_json", "auto_generate_ops", "strict_mode"):
            self.assertIn('name="' + name + '"', html)
        for value in ("encoded-original-rows", "exact-original-baseline", "original.xlsx", 'value="replace"', 'value="no"', 'value="1"'):
            self.assertIn(value, html)
        self.assertIn('action="/scheduler/excel/batches/confirm"', html)
        self.assertIn('type="checkbox" required', html)
        self.assertIn("原请求存在问题", html)
        self.assertIn("B-001", html)
        self.assertNotIn("PRIVATE-HIDDEN", html)
        self.assertNotIn("source_row_id", html)
        for forbidden in ("static/css/", "static/js/", "excel_handler.js", "components/ui_macros", "scheduler-nav"):
            self.assertNotIn(forbidden, html)

    def test_missing_baseline_bad_rows_or_absent_rows_do_not_offer_confirmation(self):
        for change in ({"preview_baseline": None}, {"preview_rows": [self.row("error")]},
                       {"preview_rows": [self.row("unknown")]}, {"preview_rows": None}, {"raw_rows_json": None}):
            with self.subTest(change=change):
                self.assertNotIn('data-legacy-confirmation="true"', self.result(**change))

    def test_print_keeps_repeated_identity_warning_fields_and_blank_remark(self):
        row = {"日期": "2026-09-10", "批次号": "B-001", "图号": "P-001", "工序": "10", "设备": "M1", "人员": "张三", "时段": "08:00-12:00"}
        html = self.render("workbench/print.html", title="周派工单", sheets=[{"resource_label": "M1", "rows": [row]}],
                           version=7, plan_role_label="历史正式方案", identity_warning="不得下发执行", generated_at_label="2026-09-09 08:00",
                           range_label="2026-09-07 至 2026-09-13", filter_scope_label="仅含批次 B-001", group_by_label="设备",
                           links={"switch_view_url": "/scheduler/week-plan/print?group_by=operator", "switch_view_label": "按人员", "back_url": "/scheduler/week-plan"}, has_history=True)
        head = html.split("<thead>", 1)[1].split("</thead>", 1)[0]
        for text in ("v7", "历史正式方案", "不得下发执行", "仅含批次 B-001", "2026-09-09 08:00"):
            self.assertIn(text, head)
        self.assertIn('class="col-remark"', html)
        self.assertIn("<td></td>", html)
        self.assertIn("window.print()", html)
        self.assertNotIn("现场状态", html)
        self.assertNotIn("static/css/", html)

    def test_generic_error_has_no_blueprint_or_script_dependency(self):
        html = self.render("error.html", title="读取失败", message="无效入口", occurred_at="2026-09-10 08:00")
        self.assertIn("无效入口", html)
        self.assertIn("2026-09-10 08:00", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("static/css/", html)

    def test_manual_full_source_anchors_and_download_survive_without_javascript(self):
        source = "# 系统说明\n开头原文\n## 1. **设备**\n逐字内容<script>bad</script>\n```\n# 不是章节\n```\n"
        blocks = PRESENTATION.manual_blocks(source)
        self.assertEqual("".join(block["source"] for block in blocks), source)
        html = self.render("workbench/manual.html", manual_mode="full", manual_text=source,
                           download_url="/scheduler/config/manual/download", back_url="/workbench", related_manuals=[])
        for value in ('id="1-设备"', 'href="#1-设备"', "/scheduler/config/manual/download", "逐字内容", "# 不是章节"):
            self.assertIn(value, html)
        self.assertNotIn("<script>bad", html)
        self.assertNotIn("config_manual.js", html)

    def test_manual_page_related_content_and_missing_file_warning_are_preserved(self):
        html = self.render("workbench/manual.html", manual_mode="page", fallback_text="## 当前主题\n原有正文",
                           current_manual={"title": "当前主题", "full_manual_label": "整本章节"},
                           full_manual_section_url="/scheduler/config/manual#1-设备", download_url="",
                           related_manuals=[{"title": "关联主题", "url": "/scheduler/config/manual?page=x", "summary": "原有摘要",
                                             "preview_sections": [{"title": "小节", "body_md": "关联内容"}]}])
        for value in ("原有正文", "关联主题", "原有摘要", "关联内容", "当前不可下载", "#1-设备"):
            self.assertIn(value, html)

    def test_all_24_result_endpoints_show_only_defined_template_fields(self):
        self.assertEqual(len(PRESENTATION.RESULT_ENDPOINTS), 24)
        for endpoint in PRESENTATION.RESULT_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                row = SimpleNamespace(data={"source_row_id": "PRIVATE-HIDDEN", "scenario_id": "PRIVATE-HIDDEN"}, changes={})
                self.assertEqual(PRESENTATION.preview_fields(row, endpoint), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
