"""Scope-aware dependency checks using pinned local Babel; never publish assets."""

import ast
import os
import shutil
import unittest
from pathlib import Path

from scripts.workbench.asset_sources import script_dependencies

ROOT = Path(__file__).resolve().parents[2]
BABEL = ROOT / "frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js"
VENDORS = ["workbench/vendor/react.js", "workbench/vendor/react-dom.js"]


class AssetScriptScopesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
        if not cls.node or not BABEL.is_file():
            raise RuntimeError("Scope tests require build-host Node and the pinned local Babel")

    def analyze(self, *sources):
        payload = {name: b"" for name in VENDORS}
        payload.update({name: code.encode("utf-8") for name, code in sources})
        return script_dependencies(self.node, BABEL, payload, VENDORS + [name for name, _ in sources], VENDORS)

    def test_real_plan_contract_callback_is_local(self):
        code = (ROOT / "frontend/workbench/app/PlanContract.js").read_text(encoding="utf-8")
        self.assertIn("window => day(window.policy_date)", code)
        name = "workbench/app/PlanContract.js"
        point = "workbench/app/PointContract.js"
        process_order = "workbench/app/PlanProcessOrder.js"
        point_code = (ROOT / "frontend" / point).read_text(encoding="utf-8")
        process_order_code = (ROOT / "frontend" / process_order).read_text(encoding="utf-8")
        resource = ("resource.js", "window.APSResourceContract = {};")
        terms = ("terms.js", "window.WorkbenchTerms = {};")
        with self.assertRaisesRegex(ValueError, "Unresolved script globals.*PlanProcessOrder"):
            self.analyze(resource, terms, (point, point_code), (name, code))
        with self.assertRaisesRegex(ValueError, "Script dependency must load earlier: .*PlanProcessOrder"):
            self.analyze(resource, terms, (point, point_code), (name, code), (process_order, process_order_code))
        result = self.analyze(resource, terms, (point, point_code), (process_order, process_order_code), (name, code))
        self.assertEqual(result[name], [
            {"path": "resource.js", "symbols": ["APSResourceContract"]},
            {"path": "terms.js", "symbols": ["WorkbenchTerms"]},
            {"path": process_order, "symbols": ["PlanProcessOrder"]},
            {"path": point, "symbols": ["PointContract"]},
        ])
        self.assertEqual(result[process_order], [])

    def test_shadow_browser_names_in_local_scopes(self):
        templates = [
            "[{}].map(NAME => NAME.policy_date);",
            "function check(NAME) { return NAME.policy_date; } check({});",
            "function check() { return NAME.policy_date; var NAME; }",
            "{ const NAME = {}; NAME.policy_date = 1; }",
            "try { throw {}; } catch (NAME) { NAME.policy_date; }",
            "function check({NAME}) { return () => NAME.policy_date; }",
            "function check(NAME) { return function nested() { return NAME.policy_date; }; }",
        ]
        for name in ("window", "self", "globalThis"):
            for template in templates:
                with self.subTest(name=name, template=template):
                    self.assertEqual(self.analyze(("local.js", template.replace("NAME", name)))["local.js"], [])

    def test_local_root_and_w_are_not_global_providers_or_reads(self):
        for name in ("root", "w"):
            for declaration in ("const NAME = {}; NAME.APSOnlyLocal = NAME.React;",
                                "function check(NAME) { NAME.APSOnlyLocal = NAME.React; } check({});"):
                with self.subTest(name=name, declaration=declaration):
                    code = declaration.replace("NAME", name)
                    self.assertEqual(self.analyze(("local.js", code))["local.js"], [])
                    with self.assertRaisesRegex(ValueError, "Unresolved script globals.*APSOnlyLocal"):
                        self.analyze(("local.js", code), ("reader.js", "window.APSOnlyLocal;"))

    def test_iife_window_alias_provides_and_reads(self):
        for name in ("root", "w", "window", "self", "globalThis", "host"):
            code = "(function(NAME) { NAME.APSApi = NAME.React; })(window);".replace("NAME", name)
            with self.subTest(name=name):
                result = self.analyze(("provider.js", code), ("reader.js", "window.APSApi;"))
                self.assertEqual(result["provider.js"], [{"path": VENDORS[0], "symbols": ["React"]}])
                self.assertEqual(result["reader.js"], [{"path": "provider.js", "symbols": ["APSApi"]}])

    def test_window_alias_is_not_limited_to_aps_names(self):
        code = "(function(root) { root.applicationContract = root.React; })(window);"
        result = self.analyze(("provider.js", code), ("reader.js", "window.applicationContract;"))
        self.assertEqual(result["reader.js"], [{"path": "provider.js", "symbols": ["applicationContract"]}])

    def test_umd_browser_guard_and_alias_initializers(self):
        for source in ("window", "self", "globalThis", "this", "typeof window === 'object' ? window : globalThis",
                       "typeof window !== 'undefined' ? window : this", "typeof window === 'undefined' ? null : window"):
            with self.subTest(source=source):
                code = "(function(root) { const w = root; w.APSApi = w.React; })(" + source + ");"
                result = self.analyze(("provider.js", code), ("reader.js", "window.APSApi;"))
                self.assertEqual(result["reader.js"], [{"path": "provider.js", "symbols": ["APSApi"]}])

    def test_local_function_parameters_follow_actual_arguments(self):
        templates = [
            "function inspect(w) { return w.APSMissing; } inspect(window);",
            "const inspect = function(root) { return root.APSMissing; }; inspect(self);",
            "const inspect = root => root.APSMissing; inspect(globalThis);",
            "function outer(root) { function inspect(w) { return w.APSMissing; } inspect(root); } outer(window);",
            "(function(root) { function inspect(w) { return w.APSMissing; } inspect(root); })(window);",
        ]
        for code in templates:
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, "Unresolved script globals.*APSMissing"):
                self.analyze(("reader.js", code))

    def test_nested_shadow_bindings_do_not_leak_between_scopes(self):
        code = """
        (function(root) {
          const w = root;
          function local(root) { const w = root; return w.APSLocal; }
          local({});
          { const w = {}; w.APSLocal = {}; }
          w.APSApi = w.React;
          function first() { function inspect(w) { return w.APSLocal; } inspect({}); }
          function second() { function inspect(w) { return w.ReactDOM; } inspect(root); }
          first(); second();
        })(window);
        """
        result = self.analyze(("provider.js", code), ("reader.js", "window.APSApi;"))
        self.assertEqual(result["provider.js"], [
            {"path": VENDORS[1], "symbols": ["ReactDOM"]}, {"path": VENDORS[0], "symbols": ["React"]}])

    def test_unresolved_globals_remain_rejected_with_shadowing(self):
        for expression in ("missingGlobal()", "window.APSMissing", "self['APSMissing']", "globalThis.APSMissing",
                           "window?.APSMissing", "(() => { const root = window; return root.APSMissing; })()"):
            code = "[{}].map(window => window.policy_date); " + expression + ";"
            with self.subTest(expression=expression), self.assertRaisesRegex(ValueError, "Unresolved script globals"):
                self.analyze(("reader.js", code))

    def test_ambiguous_or_reassigned_window_alias_fails_closed(self):
        for code in ("const root = document.hidden ? window : {}; root.APSMaybe = {};",
                     "let w = window; w = {}; w.APSMaybe = {};",
                     "let root = {}; root = window; root.APSMaybe = {};",
                     "function inspect(w) { w.APSMaybe = {}; } inspect(window); inspect({});"):
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, "Ambiguous script global alias"):
                self.analyze(("ambiguous.js", code))

    def test_dynamic_window_member_is_not_silently_ignored(self):
        with self.assertRaisesRegex(ValueError, "Unresolved dynamic script global"):
            self.analyze(("reader.js", "const key = document.title; window[key];"))
        self.assertEqual(self.analyze(("local.js", "function inspect(window, key) { return window[key]; }"))["local.js"], [])

    def test_shadowed_typeof_guard_does_not_prove_a_window_alias(self):
        code = "(function(window) { const root = typeof window === 'object' ? window : {}; root.APSLocal = {}; })({});"
        with self.assertRaisesRegex(ValueError, "Unresolved script globals.*APSLocal"):
            self.analyze(("local.js", code), ("reader.js", "globalThis.APSLocal;"))

    def test_provider_order_remains_enforced(self):
        with self.assertRaisesRegex(ValueError, "Script dependency must load earlier: reader.js -> provider.js"):
            self.analyze(("reader.js", "(function(w) { w.APSApi; })(window);"),
                         ("provider.js", "(function(root) { root.APSApi = {}; })(self);"))
        with self.assertRaisesRegex(ValueError, "Script dependency must load earlier"):
            script_dependencies(self.node, BABEL, {name: b"" for name in VENDORS}, list(reversed(VENDORS)), VENDORS)

    def test_duplicate_real_providers_remain_rejected(self):
        for first, second in (("window.APSApi = {};", "(function(root) { root.APSApi = {}; })(window);"),
                              ("var APSApi = {};", "(function(w) { w.APSApi = {}; })(self);"),
                              ("window.React = {};", "")):
            with self.subTest(first=first, second=second), self.assertRaisesRegex(ValueError, "Duplicate script global provider"):
                self.analyze(("first.js", first), ("second.js", second))

    def test_local_writes_do_not_trigger_duplicate_provider_guard(self):
        for name in ("window", "self", "globalThis", "root", "w"):
            code = "function local(NAME) { NAME.APSApi = {}; } local({});".replace("NAME", name)
            with self.subTest(name=name):
                self.assertEqual(self.analyze(("global.js", "window.APSApi = {};"), ("local.js", code))["local.js"], [])

    def test_real_imported_umd_still_provides_model(self):
        code = (ROOT / "frontend/workbench/prototype/ui_kits/workbench/system-workbench-model.js").read_text(encoding="utf-8")
        result = self.analyze(("model.js", code), ("reader.js", "window.APSSystemWorkbench;"))
        self.assertEqual(result["reader.js"], [{"path": "model.js", "symbols": ["APSSystemWorkbench"]}])

    def test_python38_syntax(self):
        for file in (ROOT / "scripts/workbench/asset_sources.py", Path(__file__)):
            ast.parse(file.read_text(encoding="utf-8"), filename=str(file), feature_version=(3, 8))


if __name__ == "__main__":
    unittest.main()
