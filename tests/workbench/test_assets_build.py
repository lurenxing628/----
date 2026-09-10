"""Asset-only tests. No Flask, database, npm install or external services."""

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "scripts/workbench"
sys.path.insert(0, str(TOOLS))
from asset_sources import (
    asset_mime,
    css_references,
    digest,
    load_json,
    local_path,
    parse_entry,
    stylesheet_dependencies,
    verify_snapshot,
)
from build import build, check_prototype, read_inputs
from import_prototype import import_snapshot
from vendor_react import PINS


class WorkbenchAssetsBuildTest(unittest.TestCase):
    maxDiff = 2000
    @classmethod
    def setUpClass(cls):
        cls.node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
        if not cls.node:
            raise RuntimeError("Asset tests require a build-host Node, set WORKBENCH_NODE")
        cls.temp = tempfile.TemporaryDirectory(prefix=".asset-tests-", dir=str(TOOLS))
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        shutil.copytree(str(ROOT / "frontend/workbench/prototype"), str(cls.root / "frontend/workbench/prototype"))
        shutil.copytree(str(ROOT / "frontend/workbench/vendor"), str(cls.root / "frontend/workbench/vendor"))
        cls.app = cls.root / "frontend/workbench/app"
        cls.app.mkdir()
        cls.source = {
            "transport.js": "window.assetOrder = ['transport'];\n",
            "system-contract.js": "window.assetOrder.push('system-contract');\n",
            "theme.js": "window.assetThemeRuns = (window.assetThemeRuns || 0) + 1; document.documentElement.dataset.theme = 'dark';\n",
            "SystemLive.jsx": "function AssetsTestPanel() { return <SMUnavailable title='Offline asset test'>Local only</SMUnavailable>; }\n",
            "main.jsx": "window.assetOrder.push('main'); ReactDOM.createRoot(document.getElementById('root')).render(<AppShell active='system' title='Assets' theme='dark' showCapsule={false} onNav={value => { window.assetNav = value; }} onToggleTheme={() => { document.documentElement.dataset.theme = 'light'; }}><AssetsTestPanel /></AppShell>);\n",
        }
        # Keep real providers while recording order; an empty stub masks dependency errors.
        for name in ("transport.js", "system-contract.js"):
            cls.source[name] += (ROOT / "frontend/workbench/app" / name).read_text(encoding="utf-8")
        for name in load_json(TOOLS / "build-order.json")["live"]:
            if name not in cls.source:
                cls.source[name] = (ROOT / "frontend/workbench/app" / name).read_text(encoding="utf-8")
        for name, text in cls.source.items():
            (cls.app / name).write_text(text, encoding="utf-8")
        cls.output = cls.root / "static/workbench"
        cls.result = build(cls.root, cls.output, cls.node)
        cls.manifest = load_json(cls.output / "asset-manifest.json")

    def asset(self, name):
        return self.root / "static" / name

    def test_snapshot_paths_and_hashes(self):
        prototype, snapshot, paths, order = read_inputs(self.root)
        self.assertEqual(set(snapshot["entries"]), {"index", "trial"})
        self.assertEqual(len(paths), len(snapshot["files"]))
        for row in snapshot["files"]:
            self.assertEqual(row["source"], "前端设计/" + row["path"])
            self.assertEqual(row["target"], "frontend/workbench/prototype/" + row["path"])

    def test_rebuild_without_ignored_design_directory(self):
        self.assertFalse((self.root / "前端设计").exists())
        second = build(self.root, self.root / "second-output", self.node)
        self.assertEqual(self.result["build_id"], second["build_id"])

    def test_jsx_props_do_not_publish_shared_babel_helpers(self):
        for name in self.manifest["scripts"]:
            if "/app/" not in name:
                continue
            code = self.asset(name).read_text(encoding="utf-8")
            self.assertNotIn("function _extends(", code, name)
        controls = self.asset("workbench/app/WorkbenchControls.js").read_text(encoding="utf-8")
        self.assertIn("...position", controls)

    def test_reproducible_payload_and_manifest(self):
        target = self.root / "repeat-output"
        build(self.root, target, self.node)
        self.assertEqual((self.output / "asset-manifest.json").read_bytes(),
                         (target / "asset-manifest.json").read_bytes())
        for row in self.manifest["files"]:
            self.assertEqual(self.asset(row["path"]).read_bytes(),
                             (target / row["path"][len("workbench/"):]).read_bytes())

    def test_host_manifest_contract(self):
        self.assertEqual(self.manifest["schema_version"], 1)
        self.assertEqual(self.manifest["target"], "chrome109")
        self.assertEqual(self.manifest["theme_script"], "workbench/app/theme.js")
        self.assertNotIn(self.manifest["theme_script"], self.manifest["scripts"])
        expected_live = ["workbench/app/" + Path(name).with_suffix(".js").as_posix()
                         for name in load_json(TOOLS / "build-order.json")["live"]]
        self.assertEqual(self.manifest["scripts"][3:], expected_live)
        for key in ("styles", "scripts"):
            self.assertEqual(len(self.manifest[key]), len(set(self.manifest[key])))
            self.assertTrue(all(isinstance(name, str) and name.startswith("workbench/")
                                and ".." not in name.split("/") and "\\" not in name for name in self.manifest[key]))
        records = {row["path"]: row for row in self.manifest["files"]}
        self.assertEqual(len(records), 34 + len(expected_live))
        order = {name: index for index, name in enumerate([self.manifest["theme_script"]] + self.manifest["scripts"])}
        for name in order:
            for dependency in records[name]["dependencies"]:
                self.assertLess(order[dependency], order[name], "Dependencies must precede consumers without reordering scripts")
        foundation = self.manifest["scripts"][2]
        react, react_dom = self.manifest["scripts"][:2]
        self.assertEqual(records[react_dom]["dependencies"], [react])
        self.assertEqual(records[foundation]["dependencies"], [react],
                         "inspectEnvironment(w) reads its caller's object, not an implicit window; see test_foundation_dependency_scope")
        self.assertEqual(records[foundation]["dependency_symbols"], [{"path": react, "symbols": ["React"]}])
        self.assertIn({"path": react_dom, "symbols": ["ReactDOM"]},
                      records["workbench/app/main.js"]["dependency_symbols"])
        self.assertEqual(records["workbench/app/theme.js"]["dependencies"], [])
        self.assertEqual(records["workbench/app/transport.js"]["dependencies"], [])
        self.assertEqual(records["workbench/app/system-contract.js"]["dependencies"], ["workbench/app/transport.js"])
        self.assertEqual(records["workbench/app/SystemLive.js"]["dependencies"], sorted([foundation, react]),
                         "Derive the fixture's actual global reads, not every earlier script")
        self.assertEqual(records["workbench/app/SystemLive.js"]["dependency_symbols"],
                         sorted([{"path": foundation, "symbols": ["SMUnavailable"]},
                                 {"path": react, "symbols": ["React"]}], key=lambda item: item["path"]))

    def test_all_public_files_have_real_hash_and_bytes(self):
        records = {row["path"]: row for row in self.manifest["files"]}
        self.assertEqual(len(records), len(self.manifest["files"]))
        for name in self.manifest["styles"] + self.manifest["scripts"] + [self.manifest["theme_script"], self.manifest["icon"]]:
            self.assertIn(name, records)
        for row in records.values():
            data = self.asset(row["path"]).read_bytes()
            self.assertEqual(row["sha256"], digest(data))
            self.assertEqual(row["bytes"], len(data))
            self.assertEqual(row["mime"], asset_mime(row["path"]))
            self.assertEqual(row["dependencies"], sorted(set(row["dependencies"])))
            self.assertTrue(set(row["dependencies"]).issubset(records))
            self.assertNotIn(row["path"], row["dependencies"])
            self.assertTrue(row["source_files"])
            self.assertTrue(row["license_sources"])
            for origin in row["source_files"]:
                base = ROOT if origin["path"].startswith("scripts/workbench/") else self.root
                self.assertEqual(origin["sha256"], digest((base / origin["path"]).read_bytes()))
            for license in row["license_sources"]:
                self.assertIn(license["status"], ("documented", "unknown"))
                self.assertEqual(license["requires_review"], license["status"] == "unknown")
                if license["status"] == "unknown":
                    self.assertIsNone(license["source"])
                    self.assertEqual(license["identifiers"], [])
                    self.assertTrue(license["reason"])
                    continue
                source = license["source"]
                self.assertIn(source["asset_path"], records)
                self.assertTrue(source["path"].startswith("frontend/workbench/"))
                self.assertNotIn("..", source["path"].split("/"))
                self.assertEqual(source["sha256"], digest((self.root / source["path"]).read_bytes()))
                self.assertEqual(source["sha256"], records[source["asset_path"]]["sha256"])
                if "provenance" in license:
                    provenance = license["provenance"]
                    self.assertTrue(provenance["path"].startswith("frontend/workbench/"))
                    self.assertEqual(provenance["sha256"], digest((self.root / provenance["path"]).read_bytes()))
        self.assertNotIn('"https://', json.dumps(self.manifest), "Metadata references must be local, not new external URLs")
        with self.assertRaisesRegex(ValueError, "MIME"):
            asset_mime("workbench/unclassified.extension")

    def test_no_browser_compiler_development_runtime_or_source_entries(self):
        for row in self.manifest["files"]:
            self.assertNotIn("babel", row["path"].lower())
            self.assertNotIn("development", row["path"])
            self.assertFalse(row["path"].endswith((".jsx", ".html")))
        foundation = self.asset(self.manifest["scripts"][2]).read_text(encoding="utf-8")
        for name in ("SMIcon", "SMStatus", "SMFilters", "SMRecordDetail", "SMOverview", "SMRecords", "SMConfiguration", "AppShell"):
            self.assertIn("function " + name + "(", foundation)
        self.assertNotIn("function SMWorkbench(", foundation)
        self.assertNotIn("function SystemManagementScreen(", foundation)
        self.assertFalse("function App(" in foundation, "Old app is embedded in the live foundation")
        self.assertFalse("trial-root" in foundation, "Trial bootstrap is embedded in the live foundation")
        self.assertFalse("ReactDOM.createRoot(" in foundation, "Foundation must not mount a root")
        for item in self.manifest["foundation_sources"]:
            self.assertNotIn(item["path"], ("ui_kits/workbench/app.jsx", "ui_kits/workbench/trial-sample.js"))

    def test_entry_css_order_and_original_inline_rules(self):
        prototype = self.root / "frontend/workbench/prototype"
        entry = parse_entry(prototype / "ui_kits/workbench/index.html", prototype)
        expected = ["workbench/prototype/" + name for name in entry["styles"]]
        self.assertEqual(self.manifest["styles"][:len(expected)], expected)
        inline = self.asset("workbench/prototype/ui_kits/workbench/index.inline.css").read_text(encoding="utf-8")
        self.assertEqual(inline, "\n".join(item["text"] for item in entry["inline_styles"]))

    def test_nested_css_font_and_icon_resources_are_local(self):
        files = {row["path"] for row in self.manifest["files"]}
        records = {row["path"]: row for row in self.manifest["files"]}
        for name in files:
            if not name.endswith(".css"):
                continue
            file = self.asset(name)
            dependencies = []
            for ref in css_references(file.read_text(encoding="utf-8")):
                target = local_path(self.root / "static", file.parent, ref)
                self.assertIn(target.relative_to(self.root / "static").as_posix(), files)
                dependencies.append(target.relative_to(self.root / "static").as_posix())
            self.assertEqual(records[name]["dependencies"], sorted(set(dependencies)))
        self.assertIn("workbench/prototype/fonts/MicrosoftYaHei-Regular.ttf", files)
        self.assertIn("workbench/prototype/assets/logo-mark.svg", files)
        self.assertEqual(records["workbench/prototype/tokens/typography.css"]["dependencies"],
                         ["workbench/prototype/fonts/MicrosoftYaHei-Regular.ttf"])
        for content in (b'@import "https://example.invalid/a.css";', b'body {background:url(//example.invalid/a.png)}'):
            with self.assertRaisesRegex(ValueError, "External/absolute"):
                stylesheet_dependencies("workbench/example.css", content, files)
        with self.assertRaisesRegex(ValueError, "Unpublished"):
            stylesheet_dependencies("workbench/example.css", b'@import "missing.css";', files)

    def test_exact_production_package_integrity_and_licenses(self):
        vendor = self.root / "frontend/workbench/vendor"
        manifest = load_json(vendor / "vendor-manifest.json")
        verify_snapshot(vendor, manifest)
        for package in manifest["packages"]:
            self.assertEqual(package["version"], "18.3.1")
            self.assertEqual(package["integrity"], PINS[package["name"]])
            self.assertEqual(package["license"], "MIT")
            self.assertIn("Permission is hereby granted", (vendor / (package["name"] + ".LICENSE")).read_text())
        probe = "const vm=require('node:vm'),fs=require('node:fs');const c=vm.createContext({});c.self=c;vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);if(c.React.version!=='18.3.1')throw Error(c.React.version);"
        subprocess.run([self.node, "-e", probe, str(vendor / manifest["scripts"][0])], check=True)
        records = {row["path"]: row for row in self.manifest["files"]}
        for name in self.manifest["scripts"][:2]:
            self.assertEqual(records[name]["license_sources"][0]["identifiers"], ["MIT"])
            self.assertEqual(records[name]["license_sources"][0]["provenance"]["version"], "18.3.1")
        foundation = records[self.manifest["scripts"][2]]
        self.assertEqual([item["status"] for item in foundation["license_sources"]], ["unknown", "documented"])
        self.assertEqual(foundation["license_sources"][1]["identifiers"], ["ISC", "MIT"])
        for name in ["workbench/prototype/fonts/MicrosoftYaHei-Regular.ttf", "workbench/prototype/assets/logo-mark.svg",
                     "workbench/prototype/styles.css", "workbench/app/main.js"]:
            self.assertEqual(records[name]["license_sources"][0]["status"], "unknown")
            self.assertTrue(records[name]["license_sources"][0]["requires_review"])
        self.assertEqual(self.manifest["asset_metadata"]["requires_license_review"],
                         [row["path"] for row in self.manifest["files"] if any(item["requires_review"] for item in row["license_sources"])])

    def test_all_other_prototype_pages_still_compile(self):
        result = check_prototype(self.root, self.node)
        self.assertFalse(result["live_published"])
        self.assertGreater(result["compiled"], 60)

    def test_missing_live_source_fails_without_replacing_published_manifest(self):
        marker = (self.output / "asset-manifest.json").read_bytes()
        target = self.app / "main.jsx"
        target.unlink()
        try:
            with self.assertRaisesRegex(ValueError, "not ready.*main.jsx"):
                build(self.root, self.output, self.node)
            self.assertEqual(marker, (self.output / "asset-manifest.json").read_bytes())
        finally:
            target.write_text(self.source["main.jsx"], encoding="utf-8")

    def test_unlisted_live_source_is_not_silently_appended(self):
        file = self.app / "unlisted.js"
        file.write_text("window.extra = true;", encoding="utf-8")
        try:
            with self.assertRaisesRegex(ValueError, "unlisted=unlisted.js"):
                build(self.root, self.output, self.node)
        finally:
            file.unlink()

    def test_bad_jsx_does_not_touch_published_assets(self):
        target = self.app / "SystemLive.jsx"
        original = target.read_bytes()
        target.write_text("function Broken() { return <", encoding="utf-8")
        try:
            before = {file: file.read_bytes() for file in self.output.rglob("*") if file.is_file()}
            with self.assertRaisesRegex(ValueError, "compile failed"):
                build(self.root, self.output, self.node)
            self.assertEqual(before, {file: file.read_bytes() for file in self.output.rglob("*") if file.is_file()})
            target.write_text("function AssetsTestPanel() { return unprovidedAssetGlobal(); }", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unresolved script globals"):
                build(self.root, self.output, self.node)
            self.assertEqual(before, {file: file.read_bytes() for file in self.output.rglob("*") if file.is_file()})
        finally:
            target.write_bytes(original)

    def test_snapshot_drift_fails_closed(self):
        file = self.root / "frontend/workbench/prototype/ui_kits/workbench/AppShell.jsx"
        original = file.read_bytes()
        file.write_bytes(original + b"\n// drift\n")
        try:
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                build(self.root, self.output, self.node)
        finally:
            file.write_bytes(original)

    def test_importer_rejects_external_resources_and_preserves_local_changes(self):
        source = self.root / "frontend/workbench/prototype"
        target = self.root / "import-output"
        result = import_snapshot(source, target)
        self.assertEqual(len(result["files"]), 114)
        changed = target / "ui_kits/workbench/AppShell.jsx"
        changed.write_text("local modification", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Imported files changed"):
            import_snapshot(source, target)
        self.assertEqual(changed.read_text(encoding="utf-8"), "local modification")
        with self.assertRaisesRegex(ValueError, "External/absolute"):
            local_path(source, source, "https://example.invalid/runtime.js")

    def test_python_sources_parse_as_python38(self):
        for file in TOOLS.glob("*.py"):
            ast.parse(file.read_text(encoding="utf-8"), filename=str(file), feature_version=(3, 8))

    @unittest.skipUnless(os.environ.get("WORKBENCH_BROWSER"), "Set WORKBENCH_BROWSER for the asset-only browser probe")
    def test_chrome109_local_assets_and_component_mount(self):
        probe = r"""
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const http = require('node:http'), { chromium } = require('playwright');
const root = process.argv[1], manifest = JSON.parse(fs.readFileSync(path.join(root,'static/workbench/asset-manifest.json')));
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' +
  '<link rel="icon" href="/static/' + manifest.icon + '">' +
  manifest.styles.map(src=>'<link rel="stylesheet" href="/static/'+src+'">').join('') +
  '</head><body class="aps-workbench"><div id="root"></div>' +
  manifest.scripts.map(src=>'<script src="/static/'+src+'"></script>').join('') + '</body></html>';
const records = new Map(manifest.files.map(row=>[row.path,row]));
const server = http.createServer((req,res)=>{
  if(req.url==='/'){res.setHeader('Content-Type','text/html;charset=utf-8');res.end(html);return;}
  const file=path.resolve(root,'.'+new URL(req.url,'http://local').pathname);
  const asset=new URL(req.url,'http://local').pathname.slice('/static/'.length),record=records.get(asset);
  if(!record||!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',record.mime);res.end(fs.readFileSync(file));
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let browser;
  try {
    browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-background-networking']});
    assert(browser.version().startsWith('109.'),'Expected an actual Chromium 109 runtime');
    const errors=[],external=[],failed=[],badMimes=[],origin='http://127.0.0.1:'+server.address().port;
    for(const viewport of [{width:1392,height:924},{width:393,height:852}]) {
      const page=await browser.newPage({viewport});
      page.on('pageerror',error=>errors.push(error.message));
      page.on('response',response=>{
        if(response.status()>=400)failed.push(response.url());
        const name=new URL(response.url()).pathname.slice('/static/'.length),record=records.get(name);
        if(record && response.headers()['content-type']!==record.mime)badMimes.push(name);
      });
      await page.route('**/*',route=>{const url=route.request().url();if(!url.startsWith(origin+'/')){external.push(url);return route.abort();}return route.continue();});
      await page.goto(origin);await page.locator('.sm-empty').waitFor();await page.evaluate(()=>document.fonts.ready);
      const facts=await page.evaluate(()=>({react:React.version,dom:ReactDOM.version,babel:typeof Babel,themeRuns:assetThemeRuns,
        order:assetOrder,dsErrors:APSDesignSystem_edbc5d.__errors,theme:document.documentElement.dataset.theme,
        icons:document.querySelectorAll('svg.sm-icon path').length,rootChildren:document.querySelector('#root').children.length,
        font:document.fonts.check('13px "Microsoft YaHei"'),rawJSX:document.querySelectorAll('script[type="text/babel"]').length,
        shared:[typeof Ico,typeof NAV_GROUPS,typeof SMOverview,typeof SMRecords,typeof SMConfiguration],
        controls:['Table','Button','Meter'].map(name=>typeof APSDesignSystem_edbc5d[name])}));
      assert.equal(facts.react,'18.3.1');
      // This is the runtime label in npm react-dom@18.3.1's integrity-verified UMD.
      assert.equal(facts.dom,'18.3.1-next-f1338f8080-20240426');assert.equal(facts.babel,'undefined');
      assert.equal(facts.themeRuns,1);assert.deepEqual(facts.order,['transport','system-contract','main']);assert.deepEqual(facts.dsErrors,[]);
      assert.equal(facts.rootChildren,1);assert(facts.icons>0);assert(facts.font);assert.equal(facts.rawJSX,0);assert.equal(facts.theme,'dark');
      assert.deepEqual(facts.shared,['function','object','function','function','function']);
      assert.deepEqual(facts.controls,['function','function','function']);
      await page.locator('.hdr-pill').click();assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),'light');
      await page.locator('a[href="#batches"]').click();assert.equal(await page.evaluate(()=>window.assetNav),'batches');
      const samples=await page.evaluate(async()=>{
        const host=document.createElement('div');document.body.appendChild(host);const root=ReactDOM.createRoot(host),mounted=[];
        const common={source:'sample',pageSize:10,onPageSize:()=>{},onTab:()=>{},theme:'light',onSetTheme:()=>{},compact:true,onCompact:()=>{},
          report:{checkedAt:new Date().toISOString(),checks:[]},kind:'backups',exportLogs:()=>{},downloadReady:true};
        for(const [Component,selector] of [[SMOverview,'.sm-overview-layout'],[SMRecords,'.sm-record-table'],[SMConfiguration,'.sm-configuration']]){
          root.render(React.createElement(Component,common));await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
          mounted.push(!!host.querySelector(selector));
        }
        root.unmount();host.remove();return mounted;
      });
      assert.deepEqual(samples,[true,true,true]);
      await page.close();
    }
    assert.deepEqual(errors,[]);assert.deepEqual(external,[]);assert.deepEqual(failed,[]);assert.deepEqual(badMimes,[]);
    console.log(JSON.stringify({version:browser.version(),viewports:2,errors,external,failed}));
  } finally {if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        result = subprocess.run([self.node, "-e", probe, str(self.root)], text=True,
                                encoding="utf-8", capture_output=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr[-5000:])
        report = json.loads(result.stdout)
        self.assertEqual(report["viewports"], 2)
        self.assertEqual(report["external"], [])


if __name__ == "__main__":
    unittest.main()
