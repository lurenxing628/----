"""Real parser/ref/scope preservation; no mounted production routes or browser."""

import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import NotFound

from core.models.workbench_plan_reference import WorkbenchPlanLocator
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests.workbench.final_legacy_navigation_support import legacy, prepare_database, token_app
from tests.workbench.plan_catalog_support import history
from tests.workbench.plan_read_support import connect
from web.plan_context_token import plan_context_token
from web.routes.workbench.legacy_navigation import build_legacy_destination, resolve_legacy_get
from web.routes.workbench.legacy_page_contract import PAGE_POLICIES, LegacyNavigationInvalid
from web.routes.workbench.navigation_boot import read_navigation


class LegacyNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aps-g-legacy-private-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "navigation.db"
        prepare_database(self.path)
        self.conn = connect(self.path)
        self.addCleanup(self.conn.close)
        self.before = list(self.conn.iterdump())
        self.statements = []
        self.conn.set_trace_callback(self.statements.append)
        self.conn.execute("PRAGMA query_only=ON")

    def decision(self, endpoint="scheduler.gantt_page", args=None, path=None):
        result = resolve_legacy_get(self.conn, legacy(endpoint, args, path))
        assert result is not None
        return result

    def read_target(self, decision):
        url = build_legacy_destination(decision)
        args = MultiDict(parse_qsl(urlsplit(url).query))
        result = read_navigation(args["view"], args)
        assert result is not None
        self.assertEqual(result["context"], dict(decision.context))
        self.assertNotIn("PRIVATE-", unquote(url))
        return result["context"]

    def assert_locator(self, decision, version, role="adopted", scenario_id=None):
        context = self.read_target(decision)
        locator = WorkbenchPlanIdentityRepository(self.conn).resolve_plan(context["plan_ref"])
        self.assertEqual(locator, WorkbenchPlanLocator(version, role, scenario_id))
        return context

    def test_explicit_latest_and_blank_inputs_bind_one_actual_version(self):
        for value in ("3", "latest", "", None):
            args = {} if value is None else {"version": value}
            with self.subTest(version=value):
                self.assert_locator(self.decision(args=args), 3)

    def test_candidate_and_same_source_role_keep_requested_identity(self):
        for role in ("adopted", "baseline_best", "critical_best"):
            with self.subTest(role=role):
                self.assert_locator(self.decision(args={"version": "3", "plan_role": role}), 3, role)

    def test_missing_role_is_explicit_retirement_not_adopted_fallback(self):
        result = self.decision(args={"version": "1", "plan_role": "critical_best"})
        self.assertEqual((result.kind, result.reason_code), ("retired", "requested_role_unavailable"))
        self.assertFalse(result.context)

    def test_explicit_missing_bad_version_and_bad_role_never_become_latest(self):
        with self.assertRaises(NotFound):
            self.decision(args={"version": "999"})
        for args in ({"version": "abc"}, {"version": "0"}, {"plan_role": "PRIVATE-BAD"}):
            with self.subTest(args=args):
                with self.assertRaises(LegacyNavigationInvalid) as failure:
                    self.decision(args=args)
                self.assertNotIn("PRIVATE-", str(failure.exception))

    def test_active_scenario_maps_to_public_ref_without_exposing_private_id(self):
        args = {"version": "3", "plan_role": "adopted", "scenario_id": "PRIVATE-ACTIVE"}
        result = self.decision(args=args)
        self.assert_locator(result, 3, scenario_id="PRIVATE-ACTIVE")
        self.assertNotIn("PRIVATE-", str(result.public_context))
        with token_app().app_context():
            token = plan_context_token("PRIVATE-ACTIVE")
            token_result = self.decision(args={"version": "3", "plan_context_token": token})
            self.assertEqual(result.context, token_result.context)
            with self.assertRaises(LegacyNavigationInvalid):
                self.decision(args={**args, "plan_context_token": plan_context_token("PRIVATE-EXPIRED")})

    def test_expired_published_mismatched_and_lost_token_do_not_reselect(self):
        for args in ({"version": "3", "scenario_id": "PRIVATE-EXPIRED"},
                     {"version": "3", "scenario_id": "PRIVATE-PUBLISHED"},
                     {"version": "2", "scenario_id": "PRIVATE-ACTIVE"}):
            with self.subTest(args=args), self.assertRaises(LegacyNavigationInvalid):
                self.decision(args=args)
        with token_app().app_context():
            token = plan_context_token("PRIVATE-ACTIVE")
        with token_app().app_context(), self.assertRaises(LegacyNavigationInvalid):
            self.decision(args={"version": "3", "plan_context_token": token})

    def test_gantt_inclusive_dates_map_to_exact_half_open_range(self):
        args = {"version": "3", "start_date": "2026/09/09", "end_date": "2026/09/10", "offset_weeks": "bad-ignored-by-old-parser"}
        context = self.assert_locator(self.decision(args=args), 3)
        self.assertEqual(context["range_start"], "2026-09-09T00:00:00")
        self.assertEqual(context["range_end"], "2026-09-11T00:00:00")

    def test_week_monday_offset_and_one_sided_date_use_existing_parser(self):
        context = self.read_target(self.decision(args={"week_start": "2026-09-09", "offset_weeks": "1"}))
        self.assertEqual((context["range_start"], context["range_end"]),
                         ("2026-09-14T00:00:00", "2026-09-21T00:00:00"))
        context = self.read_target(self.decision(args={"start_date": "2026-09-09"}))
        self.assertEqual(context["range_end"], "2026-09-16T00:00:00")

    def test_invalid_range_and_capacity_limit_do_not_become_full_span(self):
        for args in ({"start_date": "2026-02-30"}, {"offset_weeks": "one"},
                     {"start_date": "2026-09-10", "end_date": "2026-09-09"},
                     {"start_date": "2026-01-01", "end_date": "2026-04-01"},
                     {"start_date": "9999-12-31", "end_date": "9999-12-31"}):
            with self.subTest(args=args), self.assertRaises(LegacyNavigationInvalid):
                self.decision(args=args)

    def test_analysis_only_full_plan_scope_can_redirect(self):
        self.assert_locator(self.decision("scheduler.analysis_page", {"version": "2"}), 2)
        for args in ({"date_from": "2026-09-09", "date_to": "2026-09-10"},
                     {"start_date": "2026-09-09"},
                     {"machine_id": "PRIVATE-M1"}, {"query": "CAT-B"}):
            with self.subTest(args=args):
                self.assertEqual(self.decision("scheduler.analysis_page", args).kind, "retired")

    def test_unknown_duplicate_and_unsupported_gantt_filters_are_never_dropped(self):
        with self.assertRaises(LegacyNavigationInvalid):
            self.decision(args=(("version", "3"), ("version", "3")))
        for args in ({"gantt_batch": "CAT-B"}, {"gantt_resource": "PRIVATE-M1"},
                     {"gantt_zoom": "day"}, {"view": "machine"}, {"unknown": ""}):
            with self.subTest(args=args):
                self.assertEqual(self.decision(args=args).kind, "retired")

    def test_resource_details_select_persisted_refs_and_category(self):
        cases = (("equipment.detail_page", "machine_id", "PRIVATE-M1", "machine"),
                 ("personnel.detail_page", "operator_id", "PRIVATE-O1", "operator"),
                 ("process.part_detail", "part_no", "CAT-P", "part"),
                 ("process.op_type_detail", "op_type_id", "PRIVATE-T1", "op_type"),
                 ("process.supplier_detail", "supplier_id", "PRIVATE-S1", "supplier"),
                 ("scheduler.batch_detail", "batch_id", "CAT-B", "batch"))
        for endpoint, key, value, kind in cases:
            with self.subTest(endpoint=endpoint):
                context = self.read_target(self.decision(endpoint, path={key: value}))
                row = self.conn.execute("SELECT kind,entity_key FROM WorkbenchEntityRefs WHERE ref=?", (context["entity_ref"],)).fetchone()
                self.assertEqual(tuple(row), (kind, value))
                if kind == "op_type":
                    self.assertEqual(context["category"], "external")
        with self.assertRaises(NotFound):
            self.decision("equipment.detail_page", path={"machine_id": "missing"})

    def test_all_51_page_policies_and_nonpage_passthrough_are_explicit(self):
        self.assertEqual(len(PAGE_POLICIES), 51)
        details = {"equipment.detail_page", "personnel.detail_page", "process.part_detail",
                   "process.op_type_detail", "process.supplier_detail", "scheduler.batch_detail", "personnel.operator_calendar_page"}
        for endpoint, policy in PAGE_POLICIES.items():
            if endpoint not in details:
                with self.subTest(endpoint=endpoint):
                    result = self.decision(endpoint)
                    self.assertIn(result.kind, ("redirect", "retired", "restyle"))
                    if policy == "retired":
                        self.assertEqual(result.kind, "retired")
        for endpoint in ("reports.overdue_export", "scheduler.gantt_data", "health", "static"):
            self.assertIsNone(resolve_legacy_get(self.conn, legacy(endpoint, {"arbitrary": "unchanged"})))

    def test_operator_calendar_valid_path_is_retired_not_malformed_or_another_calendar(self):
        result = self.decision("personnel.operator_calendar_page", {"month": "2026-09"}, {"operator_id": "PRIVATE-O1"})
        self.assertEqual((result.kind, result.reason_code), ("retired", "operator_calendar_scope_retired"))
        self.assertFalse(result.context)
        assert result.message is not None
        self.assertNotIn("PRIVATE-O1", result.message)
        with self.assertRaises(NotFound):
            self.decision("personnel.operator_calendar_page", path={"operator_id": "missing"})

    def test_reports_keep_old_download_scope_and_do_not_claim_new_finish_dates_equal(self):
        args = {"version": "3", "date_from": "2026/09/09", "date_to": "2026/09/10", "machine_id": "PRIVATE-M1"}
        result = self.decision("reports.execution_review_page", args)
        self.assertEqual(result.kind, "retired")
        # 旧报表导出接口已随旧路由层删除：退役页不再提供“按原条件下载旧报表”链接，也不得泄露私有条件。
        self.assertEqual(result.links, ())
        self.assertNotIn("PRIVATE-", str(result.public_context))
        with token_app().app_context():
            result = self.decision("reports.overdue_page", {"version": "3", "scenario_id": "PRIVATE-ACTIVE"})
            self.assertEqual(result.links, ())
            self.assertNotIn("PRIVATE-", str(result.public_context) + str(result.message))

    def test_conflicting_date_and_resource_aliases_are_errors(self):
        for args in ({"date_from": "2026-09-09", "start_date": "2026-09-10", "date_to": "2026-09-11"},
                     {"machine_id": "PRIVATE-M1", "operator_id": "PRIVATE-O1"},
                     {"resource_type": "machine", "resource_id": "PRIVATE-M1", "scope_id": "other"}):
            with self.subTest(args=args), self.assertRaises(LegacyNavigationInvalid):
                self.decision("reports.overdue_page", args)

    def test_read_snapshot_preserves_all_rows_and_outer_transaction(self):
        self.conn.execute("BEGIN")
        self.decision(args={"version": "3"})
        self.assertTrue(self.conn.in_transaction)
        self.conn.rollback()
        self.assertEqual(self.before, list(self.conn.iterdump()))
        writes = [sql for sql in self.statements if sql.lstrip().upper().startswith(("INSERT ", "UPDATE ", "DELETE ", "REPLACE ", "CREATE ", "DROP "))]
        self.assertEqual(writes, [])

    def test_missing_permanent_mapping_is_not_repaired_or_replaced(self):
        self.conn.execute("PRAGMA query_only=OFF")
        self.conn.execute("UPDATE WorkbenchPlanSourceRefs SET active=0 WHERE kind='official' AND version=3")
        self.conn.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE kind='machine' AND entity_key='PRIVATE-M1'")
        self.conn.commit()
        self.conn.execute("PRAGMA query_only=ON")
        before = list(self.conn.iterdump())
        self.assertEqual(self.decision(args={"version": "3"}).reason_code, "identity_unavailable")
        self.assertEqual(self.decision("equipment.detail_page", path={"machine_id": "PRIVATE-M1"}).reason_code, "identity_missing")
        self.assertEqual(list(self.conn.iterdump()), before)

    def test_public_ref_survives_reopen_and_newer_version_does_not_rebind_it(self):
        before = self.read_target(self.decision(args={"version": "3"}))
        writer = connect(self.path)
        try:
            history(writer, 4, op_id=1)
            writer.commit()
        finally:
            writer.close()
        after = self.read_target(self.decision(args={"version": "3"}))
        self.assertEqual(before, after)
        reopened = connect(self.path)
        try:
            self.assertEqual(WorkbenchPlanIdentityRepository(reopened).resolve_plan(before["plan_ref"]), WorkbenchPlanLocator(3, "adopted"))
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
