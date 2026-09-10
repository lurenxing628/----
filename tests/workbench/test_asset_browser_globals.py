"""Browser-global allowlist regressions; no app, database or published assets."""

import ast
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from scripts.workbench.asset_sources import script_dependencies

ROOT = Path(__file__).resolve().parents[2]
BABEL = ROOT / "frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js"
VENDORS = ["workbench/vendor/react.js", "workbench/vendor/react-dom.js"]
BROWSER_GLOBALS = ("devicePixelRatio", "pageYOffset", "scrollX", "scrollY", "queueMicrotask", "PopStateEvent")

# CSSOM View, section 4: both names are [Replaceable] readonly attribute double.
# https://www.w3.org/TR/2016/WD-cssom-view-1-20160317/#dom-window-devicepixelratio
# https://www.w3.org/TR/2016/WD-cssom-view-1-20160317/#dom-window-pageyoffset
# The optional runtime test below proves availability in actual Chromium 109.
CHROME109_PROBE = r"""
const assert = require('node:assert/strict'), { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER,
    headless: true, args: ['--disable-background-networking']});
  try {
    const report = {browser: browser.version(), samples: [], external: [], errors: []};
    assert.match(report.browser, /^109\./, 'An actual Chromium 109 runtime is required');
    for (const scale of [1, 2]) {
      const context = await browser.newContext({deviceScaleFactor: scale});
      try {
        await context.route('**/*', route => {report.external.push(route.request().url()); return route.abort();});
        const page = await context.newPage();
        page.on('pageerror', error => report.errors.push(error.message));
        const sample = await page.evaluate(() => ({
          url: location.href, scripts: document.scripts.length, userAgent: navigator.userAgent,
          own: Object.prototype.hasOwnProperty.call(window, 'devicePixelRatio'),
          type: typeof devicePixelRatio,
          values: [devicePixelRatio, window.devicePixelRatio, self.devicePixelRatio, globalThis.devicePixelRatio],
          offsetOwn: Object.prototype.hasOwnProperty.call(window, 'pageYOffset'),
          offsetType: typeof pageYOffset,
          offsets: [pageYOffset, window.pageYOffset, self.pageYOffset, globalThis.pageYOffset],
          horizontal: [scrollX, window.scrollX, self.scrollX, globalThis.scrollX],
          vertical: [scrollY, window.scrollY, self.scrollY, globalThis.scrollY],
          microtaskTypes: [typeof queueMicrotask, typeof window.queueMicrotask, typeof self.queueMicrotask, typeof globalThis.queueMicrotask],
          popstateTypes: [typeof PopStateEvent, typeof window.PopStateEvent, typeof self.PopStateEvent, typeof globalThis.PopStateEvent],
          project: typeof window.APSResourceContract, unknown: typeof window.unprovidedAssetGlobal
        }));
        assert.equal(sample.url, 'about:blank');
        assert.equal(sample.scripts, 0);
        assert.match(sample.userAgent, /HeadlessChrome\/109\./);
        assert.equal(sample.own, true);
        assert.equal(sample.type, 'number');
        assert.deepEqual(sample.values, [scale, scale, scale, scale]);
        assert.equal(sample.offsetOwn, true);
        assert.equal(sample.offsetType, 'number');
        assert.deepEqual(sample.offsets, [0, 0, 0, 0]);
        assert.deepEqual(sample.horizontal, [0, 0, 0, 0]);
        assert.deepEqual(sample.vertical, [0, 0, 0, 0]);
        assert.deepEqual(sample.microtaskTypes, ['function', 'function', 'function', 'function']);
        assert.deepEqual(sample.popstateTypes, ['function', 'function', 'function', 'function']);
        sample.popstate = await page.evaluate(() => {
          let observed;
          window.addEventListener('popstate', e => { observed = { state: e.state, native: e instanceof PopStateEvent }; }, { once: true });
          window.dispatchEvent(new PopStateEvent('popstate', { state: { proof: 1 } }));
          return { ...observed, url: location.href };
        });
        assert.deepEqual(sample.popstate, { state: { proof: 1 }, native: true, url: 'about:blank' });
        sample.microtaskOrder = await page.evaluate(() => new Promise(resolve => {
          const values = ['sync'];
          queueMicrotask(() => values.push('microtask'));
          queueMicrotask(() => resolve(values));
          values.push('sync-end');
        }));
        assert.deepEqual(sample.microtaskOrder, ['sync', 'sync-end', 'microtask']);
        assert.equal(sample.project, 'undefined');
        assert.equal(sample.unknown, 'undefined');
        sample.scrolledOffsets = await page.evaluate(() => {
          document.body.style.height = '3000px';
          document.body.style.width = '3000px';
          window.scrollTo(80, 120);
          return [pageYOffset, window.pageYOffset, self.pageYOffset, globalThis.pageYOffset, scrollY, scrollX];
        });
        assert.deepEqual(sample.scrolledOffsets, [120, 120, 120, 120, 120, 80]);
        report.samples.push(sample);
      } finally {await context.close();}
    }
    assert.deepEqual(report.external, []);
    assert.deepEqual(report.errors, []);
    console.log(JSON.stringify(report));
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
"""


class AssetBrowserGlobalsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
        if not cls.node or not BABEL.is_file():
            raise RuntimeError("Browser-global tests require build-host Node and the pinned local Babel")

    def analyze(self, *sources):
        payload = {name: b"" for name in VENDORS}
        payload.update({name: code.encode("utf-8") for name, code in sources})
        return script_dependencies(self.node, BABEL, payload, VENDORS + [name for name, _ in sources], VENDORS)

    def test_native_free_and_browser_member_reads(self):
        for name in BROWSER_GLOBALS:
            for expression in (name, "window." + name, "self." + name, "globalThis." + name,
                               "window['" + name + "']", "window?." + name):
                with self.subTest(expression=expression):
                    self.assertEqual(self.analyze(("view.js", expression + ";"))["view.js"], [])

    def test_native_reads_through_proven_browser_aliases(self):
        for name in ("root", "w", "host"):
            code = "(function(NAME) { const view = NAME; return [view.devicePixelRatio, view.pageYOffset, view.scrollX, view.scrollY, view.queueMicrotask, view.PopStateEvent]; })(window);"
            with self.subTest(name=name):
                self.assertEqual(self.analyze(("canvas.js", code.replace("NAME", name)))["canvas.js"], [])

    def test_browser_builtin_does_not_allow_project_unknown_or_misspelled_names(self):
        for name in ("APSResourceContract", "unprovidedAssetGlobal", "devicePixelratio", "pageYoffset", "scrollx", "scrolly", "queueMicroTask", "PopstateEvent"):
            for expression in (name, "window." + name, "(function(root) { return root." + name + "; })(window)"):
                with self.subTest(expression=expression):
                    with self.assertRaisesRegex(ValueError, "Unresolved script globals.*" + name):
                        self.analyze(("canvas.js", "window.devicePixelRatio; window.pageYOffset; " + expression + ";"))

    def test_browser_builtin_preserves_project_and_vendor_dependencies(self):
        result = self.analyze(("model.js", "window.PlanGanttModel = {};"),
                              ("canvas.js", "window.devicePixelRatio; window.pageYOffset; window.PlanGanttModel; React.useRef;"))
        self.assertEqual(result["canvas.js"], [
            {"path": "model.js", "symbols": ["PlanGanttModel"]},
            {"path": VENDORS[0], "symbols": ["React"]},
        ])

    def test_browser_builtin_does_not_relax_project_load_order(self):
        with self.assertRaisesRegex(ValueError, "Script dependency must load earlier: canvas.js -> model.js"):
            self.analyze(("canvas.js", "window.devicePixelRatio; window.pageYOffset; window.PlanGanttModel;"),
                         ("model.js", "window.PlanGanttModel = {};"))

    def test_browser_builtin_name_can_be_shadowed_without_publishing_local_properties(self):
        code = "function inspect(devicePixelRatio) { return devicePixelRatio.APSLocal; } inspect({});"
        self.assertEqual(self.analyze(("local.js", code))["local.js"], [])
        with self.assertRaisesRegex(ValueError, "Unresolved script globals.*APSLocal"):
            self.analyze(("local.js", code), ("reader.js", "window.APSLocal;"))

    def test_current_plan_canvas_compiles_and_keeps_real_dependencies(self):
        source = ROOT / "frontend/workbench/app/PlanGanttCanvas.jsx"
        code = source.read_text(encoding="utf-8")
        self.assertIn("window.devicePixelRatio", code)
        request = {"babel_path": str(BABEL), "sources": [{"path": "app/PlanGanttCanvas.jsx", "code": code}]}
        compiled = subprocess.run([self.node, str(ROOT / "scripts/workbench/compile.cjs")],
                                  input=json.dumps(request), text=True, encoding="utf-8",
                                  capture_output=True, timeout=30)
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        report = json.loads(compiled.stdout)
        self.assertEqual(report["babel_version"], "7.29.0")
        self.assertEqual(report["target"], {"chrome": "109"})
        name = "workbench/app/PlanGanttCanvas.js"
        point_sources = [("workbench/app/" + helper, (source.parent / helper).read_text(encoding="utf-8"))
                         for helper in ("PointContract.js", "PointGanttModel.js")]
        result = self.analyze(*point_sources, ("model.js", "window.PlanGanttModel = {};"),
                              (name, report["outputs"][0]["code"]))
        self.assertEqual(result[name], [
            {"path": "model.js", "symbols": ["PlanGanttModel"]},
            {"path": "workbench/app/PointContract.js", "symbols": ["PointContract"]},
            {"path": "workbench/app/PointGanttModel.js", "symbols": ["PointGanttModel"]},
            {"path": VENDORS[0], "symbols": ["React"]},
        ])

    def test_python38_syntax(self):
        for file in (ROOT / "scripts/workbench/asset_sources.py", Path(__file__)):
            ast.parse(file.read_text(encoding="utf-8"), filename=str(file), feature_version=(3, 8))

    @unittest.skipUnless(os.environ.get("WORKBENCH_BROWSER"), "Set WORKBENCH_BROWSER to actual Chromium 109")
    def test_actual_chrome109_native_global_without_application_scripts(self):
        probe = subprocess.run([self.node, "-e", CHROME109_PROBE], text=True, encoding="utf-8",
                               capture_output=True, timeout=60)
        self.assertEqual(probe.returncode, 0, probe.stderr[-5000:])
        report = json.loads(probe.stdout)
        self.assertTrue(report["browser"].startswith("109."))
        self.assertEqual(len(report["samples"]), 2)
        self.assertEqual(report["external"], [])
        self.assertEqual(report["errors"], [])
        print("WB_BROWSER_GLOBALS " + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    unittest.main()
