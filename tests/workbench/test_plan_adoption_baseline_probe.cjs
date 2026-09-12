'use strict';
// Isolated in-memory page, actual adopted SQLite DTOs supplied by the Python test.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = path.resolve(process.argv[2]);
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const report = { production: false, external: [], errors: [], sources: [], screenshots: [], fixtures: input.fixtures.length };
assert(!output.startsWith(root + path.sep), 'Browser artifacts must be outside checkout');
fs.mkdirSync(output, { recursive: true });
const files = ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'resource-contract.js', 'PointContract.js', 'PlanProcessOrder.js', 'PlanContract.js', 'PointGanttModel.js', 'PlanGanttModel.js', 'ResourceControls.jsx', 'PlanDetailsUI.jsx'];
const sources = files.map(name => ({path: 'frontend/workbench/app/' + name,
  code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8')}));
const compiled = compile({babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true});
report.sources = sources.map(row => ({path: row.path, sha256: crypto.createHash('sha256').update(row.code).digest('hex')}));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const vendor = manifest.scripts.filter(name => name.startsWith('workbench/vendor/'));
let browser;
(async () => {
  try {
    browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking']});
    report.browser = browser.version(); assert.match(report.browser, /^109\./);
    for (const viewport of [{width: 1366, height: 900}, {width: 390, height: 844}]) {
      const page = await browser.newPage({viewport});
      page.on('pageerror', error => report.errors.push(error.message));
      await page.route('**/*', route => { report.external.push(route.request().url()); return route.abort(); });
      await page.setContent('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"></head><body><div id="root"></div></body></html>');
      for (const name of vendor) await page.addScriptTag({content: fs.readFileSync(path.join(root, 'static', name), 'utf8')});
      for (const row of compiled.outputs) await page.addScriptTag({content: row.code});
      await page.addStyleTag({content: 'body{font:14px sans-serif;margin:12px;color:#222}aside{max-width:600px}section{border-bottom:1px solid #aaa;padding:8px 0}dl{display:grid;grid-template-columns:100px 1fr;gap:8px}dt,dd{margin:0;overflow-wrap:anywhere}button{min-height:32px}'});
      for (const [index, fixture] of input.fixtures.entries()) {
        const verified = await page.evaluate(fixture => {
          const payload = window.APSPlanContract.workspace(fixture.payload, fixture.plan_ref, fixture.scope);
          const data = payload.data, baseline = data.projections.baseline, original = JSON.stringify(data);
          const model = window.PlanGanttModel.layout(data, 'machine', '', true);
          const before = baseline.items.filter(row => row.before).map(row => row.before);
          if (before.some(row => !model.locations.has(row.task_ref))) throw new Error('Original baseline task missing from Gantt model');
          if (original !== JSON.stringify(data)) throw new Error('Gantt changed source DTO');
          if (window.mounted) window.mounted.unmount();
          window.mounted = ReactDOM.createRoot(document.getElementById('root'));
          const show = (task, before) => window.mounted.render(React.createElement(window.PlanDetailsUI.TaskDetail,
            {data, selected: {task, before}, onSelect: show}));
          show(before[0], true);
          return {basis: baseline.basis, taskRef: before[0].task_ref, before: before[0], after: baseline.items[0].after};
        }, fixture);
        assert(['candidate_adoption', 'trial_adoption'].includes(verified.basis));
        const inspector = page.locator('[data-plan-inspector]');
        await inspector.getByText('初始计划安排', {exact: true}).waitFor();
        assert((await inspector.textContent()).includes(verified.before.start.replace('T', ' ')));
        assert.equal(await inspector.locator('dt').filter({hasText: /^供应商$/}).evaluate(node => node.nextElementSibling.textContent), '未记录');
        await page.getByRole('button', {name: '查看当前安排', exact: true}).click();
        await inspector.getByText('当前所选计划安排', {exact: true}).waitFor();
        assert((await inspector.textContent()).includes(verified.after.start.replace('T', ' ')));
        const filename = path.join(output, viewport.width + '-' + index + '.png');
        await page.screenshot({path: filename, fullPage: true}); report.screenshots.push(filename);
      }
      await page.close();
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
  } finally {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(report, null, 2));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
