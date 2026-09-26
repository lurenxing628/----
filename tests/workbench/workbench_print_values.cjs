'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { chromium } = require('playwright');
const { server, root } = require('./plan_ui_browser_harness.cjs');
const { compile } = require('../../scripts/workbench/compile.cjs');

async function main() {
  const report = { themes: [], errors: [], unexpected_requests: [] }, web = server(report);
  const sources = ['TrialControls.jsx', 'TrialResults.jsx', 'DashboardTimelineModel.js',
    'DashboardAnalysisPanels.jsx', 'DashboardCandidatePanels.jsx'];
  const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
    sources: sources.map(name => ({ path: name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') })) });
  await new Promise(resolve => web.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
    report.browser = browser.version();
    for (const theme of ['light', 'dark']) {
      const page = await browser.newPage({ viewport: { width: 1392, height: 924 } });
      page.on('pageerror', error => report.errors.push(error.message));
      await page.goto('http://127.0.0.1:' + web.address().port);
      // The harness also loads the published copy; keep only current source styles for this regression.
      await page.evaluate(() => document.querySelectorAll('link[href^="/static/workbench/app/styles/"]').forEach(link => link.remove()));
      for (const output of built.outputs) await page.addScriptTag({ content: output.code });
      await page.evaluate(theme => {
        document.documentElement.dataset.theme = theme;
        // Only view persistence and the unrelated timeline are replaced; table cells and Buttons are production components.
        window.TrialViewState = { useView: () => ({ value: { result_tab: 'tasks' } }), Notice: () => null };
        window.TrialGantt = { resourceNames: () => ref => ref };
        window.DashboardTimeline = () => null;
        const create = React.createElement, noop = () => {};
        const task = { task_ref: 'a'.repeat(48), batch_id: 'BATCH-PRINT-001', process_label: 'FINISH-TURNING', sequence: 1,
          piece_id: null, quantity: 10, machine_ref: 'MACHINE-PRINT-001', operator_ref: 'OPERATOR-PRINT-001',
          start: '2026-09-22T08:00:00', end: '2026-09-22T09:00:00', changed: false };
        const delivery = { batch_ref: 'b'.repeat(48), batch_id: 'BATCH-DELIVERY-002', part_label: 'PART-002',
          due_date: '2026-09-23', planned_finish: task.end, risk: 'on_time', priority: 'normal' };
        const overlap = { ...delivery, batch_id: 'BATCH-DOWNTIME-003', task_ref: task.task_ref,
          process_label: task.process_label, source: { planned_start: task.start, planned_end: task.end, overlap_hours: 1 } };
        const comparison = { ...delivery, batch_id: 'BATCH-COMPARE-004', before: delivery, after: delivery, delay_delta_hours: 0 };
        ReactDOM.createRoot(document.getElementById('fixture-root')).render(create(React.Fragment, null,
          create('div', { className: 'trial-workspace' }, create(TrialResults.Results, {
            data: { scope: {}, base_identity: {}, comparison: {}, tasks: [task] }, onSelect: noop })),
          create('div', { className: 'plana dashboard-live' },
            create(DashboardAnalysisPanels.Delivery, { data: { deliveries: [delivery] }, onSelect: noop, onCompare: noop }),
            create(DashboardAnalysisPanels.Downtime, { data: { overlaps: [overlap], downtimes: [] }, onSelect: noop }),
            create(DashboardCandidatePanels.Batches, { data: { batches: [comparison] }, onSelect: noop }))));
      }, theme);
      const values = ['BATCH-PRINT-001 · FINISH-TURNING 1', 'BATCH-DELIVERY-002', 'BATCH-DOWNTIME-003', 'BATCH-COMPARE-004'];
      for (const name of values) await page.getByRole('button', { name, exact: true }).waitFor();
      const snapshot = () => page.locator('table tbody tr td:first-child').evaluateAll(cells => cells.map(cell => cell.innerText));
      const screen = await snapshot();
      assert.equal(screen.length, 4);
      assert(await page.getByRole('button', { name: '对比候选方案', exact: true }).isVisible());
      await page.emulateMedia({ media: 'print' });
      assert.deepEqual(await snapshot(), screen, 'Print must retain the business identity in every table row');
      for (const name of values) assert(await page.getByRole('button', { name, exact: true }).isVisible(), name);
      assert.equal(await page.getByRole('button', { name: '对比候选方案', exact: true }).isVisible(), false);
      await page.pdf({ path: path.join(process.argv[2], theme + '.pdf'), format: 'A4', landscape: true });
      await page.emulateMedia({ media: 'screen' });
      assert.deepEqual(await snapshot(), screen);
      assert(await page.getByRole('button', { name: '对比候选方案', exact: true }).isVisible());
      report.themes.push(theme);
      await page.close();
    }
    assert.deepEqual(report.errors, []);
    assert.deepEqual(report.unexpected_requests, []);
    console.log(JSON.stringify({ browser: report.browser, themes: report.themes, errors: report.errors }));
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => web.close(resolve));
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
