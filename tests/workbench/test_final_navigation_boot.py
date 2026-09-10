"""Server navigation validation, not browser migration or retained-data acceptance."""

import copy
import json
import unittest
from unittest.mock import patch

from werkzeug.datastructures import MultiDict

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_trial import create_input
from tests.workbench.final_navigation_support import END, INVALID_CONTEXTS, REF, START, VALID_CONTEXTS, nav_args
from web.routes.workbench.navigation_boot import (
    EMPTY_CONTEXT_VIEWS,
    SUPPORTED_VIEWS,
    WorkbenchNavigationInvalid,
    read_navigation,
)


class NavigationBootTests(unittest.TestCase):
    def test_absent_nav_is_none_and_does_not_invent_identity(self):
        self.assertIsNone(read_navigation("gantt", MultiDict()))
        self.assertIsNone(read_navigation("gantt", MultiDict({"view": "gantt"})))
        self.assertIsNone(read_navigation("trial", MultiDict()))
        self.assertIsNone(read_navigation("trial", MultiDict({"view": "trial"})))

    def test_absent_nav_still_validates_all_outer_query_fields(self):
        invalid = [MultiDict({"version": "7", "plan_role": "adopted"}),
                   MultiDict({"scope": "all"}), MultiDict({"plan_ref": REF}),
                   MultiDict([("view", "gantt"), ("view", "gantt")]),
                   MultiDict({"view": "analysis"})]
        for args in invalid:
            with self.subTest(args=list(args.items(multi=True))):
                with self.assertRaises(WorkbenchNavigationInvalid):
                    read_navigation("gantt", args)
        with self.assertRaises(WorkbenchNavigationInvalid):
            read_navigation("trial", MultiDict({"view": "gantt"}))

    def test_valid_contexts_preserve_exact_values_and_query(self):
        for view, context in VALID_CONTEXTS:
            with self.subTest(view=view, context=context):
                args = nav_args(view, context)
                before = list(args.items(multi=True))
                result = read_navigation(view, args)
                self.assertEqual(result, {"version": 1, "view": view, "context": context})
                self.assertEqual(json.loads(canonical_json(result)), result)
                self.assertEqual(list(args.items(multi=True)), before)

    def test_explicit_empty_context_is_landing_not_a_ref_fallback(self):
        for view in SUPPORTED_VIEWS:
            with self.subTest(view=view):
                result = read_navigation(view, nav_args(view, {}))
                assert result is not None
                self.assertEqual(result["context"], {})

    def test_invalid_contexts_fail_with_named_error(self):
        for view, context in INVALID_CONTEXTS:
            with self.subTest(view=view, context=context):
                with self.assertRaises(WorkbenchNavigationInvalid):
                    read_navigation(view, nav_args(view, context))

    def test_empty_only_views_reject_explicit_identity_instead_of_dropping(self):
        for view in EMPTY_CONTEXT_VIEWS:
            with self.subTest(view=view):
                with self.assertRaises(WorkbenchNavigationInvalid):
                    read_navigation(view, nav_args(view, {"plan_ref": REF}))

    def test_root_shape_and_version_are_exact(self):
        base = {"version": 1, "view": "gantt", "context": {"plan_ref": REF}}
        invalid = [None, [], "text", {}, {**base, "extra": 1}, {**base, "version": True},
                   {**base, "version": 1.0}, {**base, "version": "1"}, {**base, "version": 2},
                   {**base, "view": "analysis"}, {**base, "context": []}]
        for key in base:
            missing = copy.deepcopy(base)
            del missing[key]
            invalid.append(missing)
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(WorkbenchNavigationInvalid):
                    read_navigation("gantt", MultiDict({"nav": json.dumps(value)}))

    def test_duplicate_json_keys_at_all_layers_are_rejected(self):
        bodies = [
            '{"version":1,"version":1,"view":"gantt","context":{}}',
            '{"version":1,"view":"gantt","context":{},"context":{}}',
            '{"version":1,"view":"gantt","context":{"plan_ref":"' + REF + '","plan_ref":"' + REF + '"}}',
            '{"version":1,"view":"reports","context":{"scope":{"plan_ref":"' + REF + '","query":"x","query":"x"}}}',
        ]
        for body in bodies:
            view = "reports" if '"reports"' in body else "gantt"
            with self.subTest(body=body):
                with self.assertRaises(WorkbenchNavigationInvalid):
                    read_navigation(view, MultiDict({"nav": body}))

    def test_outer_query_is_exact_and_not_flattened(self):
        for key in ("nav", "view"):
            args = nav_args("gantt", {"plan_ref": REF})
            args.add(key, args[key])
            with self.subTest(duplicate=key):
                with self.assertRaises(WorkbenchNavigationInvalid):
                    read_navigation("gantt", args)
        with self.assertRaises(WorkbenchNavigationInvalid):
            read_navigation("gantt", nav_args("gantt", {"plan_ref": REF}, version="7"))
        with self.assertRaises(WorkbenchNavigationInvalid):
            read_navigation("gantt", nav_args("analysis", {"plan_ref": REF}))

    def test_trial_path_can_omit_outer_view_but_not_mismatch_it(self):
        args = nav_args("trial", {"draft_ref": REF})
        del args["view"]
        result = read_navigation("trial", args)
        assert result is not None
        self.assertEqual(result["context"], {"draft_ref": REF})
        args["view"] = "gantt"
        with self.assertRaises(WorkbenchNavigationInvalid):
            read_navigation("trial", args)

    def test_invalid_json_numbers_unicode_and_inactive_view_are_named_errors(self):
        bodies = ["", "{", "null", '[1,2]', '{"version":NaN}', '{"version":Infinity}',
                  '{"version":1e309,"view":"gantt","context":{}}',
                  '{"version":1,"view":"reports","context":{"scope":{"plan_ref":"' + REF + '","query":"\\ud800"}}}']
        for body in bodies:
            view = "reports" if '"reports"' in body else "gantt"
            with self.subTest(body=body):
                with self.assertRaises(WorkbenchNavigationInvalid):
                    read_navigation(view, MultiDict({"nav": body}))
        with self.assertRaises(WorkbenchNavigationInvalid):
            read_navigation("unknown", nav_args("unknown", {}))

    def test_ref_existence_stays_with_domain_reader_and_no_database_is_opened(self):
        unknown = "f" * 48
        with patch("sqlite3.connect", side_effect=AssertionError("navigation must not open a DB")):
            result = read_navigation("gantt", nav_args("gantt", {"plan_ref": unknown}))
        assert result is not None
        self.assertEqual(result["context"]["plan_ref"], unknown)


class TrialTaskOriginNavigationTests(unittest.TestCase):
    def origin(self):
        return {"plan_ref": REF, "operation_ref": "b" * 48, "task_ref": "c" * 48}

    def test_same_plan_and_draft_targets_preserve_exact_values_without_writes(self):
        origin = self.origin()
        contexts = ({"base": {"plan_ref": REF}, "task_origin": origin},
                    {"base": {"plan_ref": REF}, "scope": {"range_start": START, "range_end": END,
                     "query": "same plan display", "batch_refs": ["d" * 48]}, "task_origin": origin},
                    {"draft_ref": "e" * 48, "task_origin": origin})
        for context in contexts:
            args = nav_args("trial", context)
            before = copy.deepcopy(context), list(args.items(multi=True))
            with self.subTest(context=context), patch("sqlite3.connect", side_effect=AssertionError("navigation must not open a DB")):
                result = read_navigation("trial", args)
            self.assertEqual(result, {"version": 1, "view": "trial", "context": context})
            self.assertEqual((context, list(args.items(multi=True))), before)
            assert result is not None
            self.assertEqual(read_navigation("trial", MultiDict({"nav": canonical_json(result)})), result)

    def test_origin_requires_exactly_three_keys(self):
        origin = self.origin()
        invalid = [None, [], "task", False, {}, {**origin, "ticket": REF}, {**origin, "scenario_ref": REF}]
        invalid.extend({key: value} for key, value in origin.items())
        invalid.extend({key: value for key, value in origin.items() if key != missing} for missing in origin)
        for value in invalid:
            for target in ({"base": {"plan_ref": REF}}, {"draft_ref": "e" * 48}):
                with self.subTest(origin=value, target=target), self.assertRaises(WorkbenchNavigationInvalid):
                    read_navigation("trial", nav_args("trial", {**target, "task_origin": value}))

    def test_every_origin_ref_uses_the_existing_permanent_ref_format(self):
        for key in self.origin():
            for value in (None, False, 48, [], {}, "", "a" * 47, "a" * 49, "A" * 48, "g" * 48, REF + " ", "latest"):
                origin = {**self.origin(), key: value}
                with self.subTest(key=key, value=value), self.assertRaises(WorkbenchNavigationInvalid):
                    read_navigation("trial", nav_args("trial", {"draft_ref": "e" * 48, "task_origin": origin}))

    def test_candidate_scenario_different_base_and_ambiguous_targets_are_rejected(self):
        targets = ({}, {"base": {"candidate_ref": REF}}, {"base": {"plan_ref": "d" * 48}},
                   {"scenario_ref": REF}, {"draft_ref": "e" * 48, "scenario_ref": REF},
                   {"base": {"plan_ref": REF}, "draft_ref": "e" * 48},
                   {"base": {"plan_ref": REF, "candidate_ref": "d" * 48}},
                   {"base": {"plan_ref": REF}, "ticket": REF}, {"draft_ref": "e" * 48, "scope": {}},
                   {"draft_ref": None}, {"base": None})
        for target in targets:
            with self.subTest(target=target), self.assertRaises(WorkbenchNavigationInvalid):
                read_navigation("trial", nav_args("trial", {**target, "task_origin": self.origin()}))

    def test_origin_does_not_loosen_existing_display_scope_or_other_views(self):
        for scope in ({"range_start": START}, {"range_start": None, "range_end": None},
                      {"range_start": END, "range_end": START}, {"query": "x" * 201}, {"task_ref": REF}):
            with self.subTest(scope=scope), self.assertRaises(WorkbenchNavigationInvalid):
                read_navigation("trial", nav_args("trial", {"base": {"plan_ref": REF}, "scope": scope, "task_origin": self.origin()}))
        for view in ("gantt", "reports", "process", "dashboard"):
            with self.subTest(view=view), self.assertRaises(WorkbenchNavigationInvalid):
                read_navigation(view, nav_args(view, {"task_origin": self.origin()}))

    def test_duplicate_origin_and_nested_reference_keys_are_rejected(self):
        origin = canonical_json(self.origin())
        base = '"draft_ref":"' + "e" * 48 + '"'
        bodies = ('{"version":1,"view":"trial","context":{' + base + ',"task_origin":' + origin + ',"task_origin":' + origin + '}}',
                  '{"version":1,"view":"trial","context":{' + base + ',"task_origin":' + origin[:-1] + ',"plan_ref":"' + REF + '"}}}')
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(WorkbenchNavigationInvalid):
                read_navigation("trial", MultiDict({"nav": body}))

    def test_origin_is_navigation_only_not_a_create_command_extension(self):
        context = {"base": {"plan_ref": REF}, "task_origin": self.origin()}
        with patch("web.routes.workbench.navigation_boot.create_input", wraps=create_input) as validate:
            self.assertIsNotNone(read_navigation("trial", nav_args("trial", context)))
        validate.assert_called_once_with({"base": {"plan_ref": REF}})
        with self.assertRaises(WorkbenchCommandRejected):
            create_input(context)
        with patch("web.routes.workbench.navigation_boot.create_input", side_effect=AssertionError("draft navigation is not create")):
            self.assertIsNotNone(read_navigation("trial", nav_args("trial", {"draft_ref": "e" * 48, "task_origin": self.origin()})))

    def test_without_origin_candidate_and_saved_scenario_inputs_stay_valid(self):
        for context in ({"base": {"candidate_ref": REF}}, {"scenario_ref": REF}, {"draft_ref": REF}):
            with self.subTest(context=context):
                self.assertEqual(read_navigation("trial", nav_args("trial", context)),
                                 {"version": 1, "view": "trial", "context": context})


if __name__ == "__main__":
    unittest.main(verbosity=2)
