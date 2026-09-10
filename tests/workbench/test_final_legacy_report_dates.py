"""Paired old-public and legacy date contracts after removing the web back-edge."""

import ast
import unittest
from datetime import date, timedelta
from pathlib import Path

from core.infrastructure.errors import ValidationError
from core.services.report import date_input
from core.services.report.date_range_limits import REPORT_EXPLICIT_DATE_RANGE_MAX_DAYS
from web.routes import report_plan_preview
from web.routes.workbench import legacy_navigation_plan
from web.routes.workbench.legacy_page_contract import LegacyNavigationInvalid


class LegacyReportDateTests(unittest.TestCase):
    def test_old_public_names_export_the_same_core_functions(self):
        self.assertIs(report_plan_preview.validate_ymd_date, date_input.validate_ymd_date)
        self.assertIs(report_plan_preview.validate_explicit_report_date_range,
                      date_input.validate_explicit_report_date_range)
        self.assertIs(legacy_navigation_plan.validate_explicit_report_date_range,
                      date_input.validate_explicit_report_date_range)

    def test_single_date_preserves_normalization_and_original_format_tolerance(self):
        for raw, expected in ((" 2026/09/09 ", "2026-09-09"),
                              ("2026-9-9", "2026-9-9"), ("2024-02-29", "2024-02-29")):
            for function in (report_plan_preview.validate_ymd_date, date_input.validate_ymd_date):
                with self.subTest(raw=raw, function=function):
                    self.assertEqual(function(raw, "开始日期"), expected)

    def test_single_date_preserves_error_message_field_and_cause(self):
        cases = (("", "缺少开始日期或结束日期。", "日期范围", None),
                 ("2026-02-29", "日期格式不正确，请按 2026-03-13 或 2026/03/13 这样的格式填写。", "开始日期", ValueError))
        for raw, message, field, cause in cases:
            for function in (report_plan_preview.validate_ymd_date, date_input.validate_ymd_date):
                with self.subTest(raw=raw, function=function), self.assertRaises(ValidationError) as raised:
                    function(raw, "开始日期")
                self.assertEqual((raised.exception.message, raised.exception.field), (message, field))
                if cause is None:
                    self.assertIsNone(raised.exception.__cause__)
                else:
                    self.assertIsInstance(raised.exception.__cause__, cause)

    def test_old_and_legacy_valid_ranges_match_including_exact_maximum(self):
        start = date(2026, 1, 1)
        last = start + timedelta(days=REPORT_EXPLICIT_DATE_RANGE_MAX_DAYS - 1)
        self.assertEqual(REPORT_EXPLICIT_DATE_RANGE_MAX_DAYS, 62)
        for first, end in (("2026/09/09", "2026/09/10"), (start.isoformat(), last.isoformat()),
                           ("2026-9-9", "2026-9-9")):
            expected = (first.replace("/", "-"), end.replace("/", "-"))
            with self.subTest(first=first, end=end):
                self.assertEqual(report_plan_preview.validate_explicit_report_date_range(first, end), expected)
                self.assertEqual(legacy_navigation_plan.report_dates({"date_from": first, "date_to": end}), expected)
                self.assertEqual(legacy_navigation_plan.report_dates({"start_date": first, "end_date": end}), expected)

    def test_old_and_legacy_invalid_ranges_match_without_defaulting(self):
        cases = (("", "2026-01-01", "缺少开始日期或结束日期。", "日期范围"),
                 ("2026-01-01", "", "缺少开始日期或结束日期。", "日期范围"),
                 ("2026-02-30", "2026-03-01", "日期格式不正确，请按 2026-03-13 或 2026/03/13 这样的格式填写。", "开始日期"),
                 ("2026-01-01", "bad", "日期格式不正确，请按 2026-03-13 或 2026/03/13 这样的格式填写。", "结束日期"),
                 ("2026-01-02", "2026-01-01", "结束日期不能早于开始日期", "结束日期"),
                 ("2026-01-01", "2026-03-04", "日期范围不能超过 62 天", "日期范围"))
        for first, end, message, field in cases:
            with self.subTest(first=first, end=end, entry="old-public"), self.assertRaises(ValidationError) as raised:
                report_plan_preview.validate_explicit_report_date_range(first, end)
            self.assertEqual((raised.exception.message, raised.exception.field), (message, field))
            for args in ({"date_from": first, "date_to": end}, {"start_date": first, "end_date": end}):
                with self.subTest(args=args, entry="legacy"), self.assertRaises(ValidationError) as raised:
                    legacy_navigation_plan.report_dates(args)
                self.assertEqual((raised.exception.message, raised.exception.field), (message, field))

    def test_conflicting_aliases_remain_errors_including_unpadded_spelling(self):
        for primary, alias in (("date_from", "start_date"), ("date_to", "end_date")):
            for left, right in (("2026-09-09", "2026-09-10"), ("2026-9-9", "2026-09-09")):
                with self.subTest(primary=primary, left=left), self.assertRaises(LegacyNavigationInvalid) as raised:
                    legacy_navigation_plan.report_dates({primary: left, alias: right})
                self.assertEqual(raised.exception.description, "旧入口包含冲突的日期别名，未选择其中一组继续。")

    def test_equal_aliases_normalize_and_empty_inputs_keep_no_explicit_range(self):
        args = {"date_from": " 2026/09/09 ", "start_date": "2026-09-09",
                "date_to": "2026/09/10", "end_date": " 2026-09-10 "}
        self.assertEqual(legacy_navigation_plan.report_dates(args), ("2026-09-09", "2026-09-10"))
        self.assertIsNone(legacy_navigation_plan.report_dates({}))
        self.assertIsNone(legacy_navigation_plan.report_dates({"date_from": " ", "date_to": ""}))

    def test_core_has_no_web_dependency_and_legacy_has_no_old_report_back_edge(self):
        root = Path(__file__).resolve().parents[2]
        for relative, forbidden in (("core/services/report/date_input.py", ("web", "flask", "werkzeug")),
                                     ("web/routes/workbench/legacy_navigation_plan.py", ("web.routes.report_plan_preview",))):
            tree = ast.parse((root / relative).read_text(encoding="utf-8"))
            modules = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            modules.extend(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
            self.assertFalse([name for name in modules for prefix in forbidden
                              if name == prefix or name.startswith(prefix + ".")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
