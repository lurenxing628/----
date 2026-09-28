'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { chromium } = require('playwright'), H = require('./plan_ui_browser_harness.cjs');
const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')), output = path.resolve(process.argv[3]);
fs.mkdirSync(output, { recursive: true });
for (const file of ['WorkbenchGuards.js', 'RunCandidateAPI.js', 'RunCandidateModel.js', 'FieldContract.js',
  'TrialContract.js', 'TrialControls.jsx', 'TrialViewState.js', 'TrialGantt.jsx', 'TrialDetails.jsx']) {
  if (!H.files.includes(file)) H.files.push(file);
}
const report = { errors: [], unexpected_requests: [], writes_to_server: 0, win7_tested: false };
const server = H.server(report);
(async () => {
  let browser;
  try {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
    report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    const page = await browser.newPage({ viewport: { width: 1392, height: 924 } });
    page.on('pageerror', error => report.errors.push(error.message));
    await page.goto('http://127.0.0.1:' + server.address().port);
    await page.evaluate(data => {
      const task = data.tasks[0], alternate = { ...data.resources.machines[0], ref: 'e'.repeat(48), business_code: 'M2', label: '另一台设备' };
      data.resources.machines.push(alternate);
      data.resources.authorizations.push({ machine_ref: alternate.ref, operator_ref: task.operator_ref });
      window.editorCalls = [];
      const commands = { busy: false, blocked: false, key: null, error: null,
        execute: async intent => { editorCalls.push(JSON.parse(JSON.stringify(intent))); return true; } };
      ReactDOM.createRoot(document.getElementById('fixture-root')).render(React.createElement(TrialDetails, {
        data, selected: task.task_ref, commands, onSelect() {}, onEditing() {}, onRecheck() {},
        guardOwner: 'microsecond-editor-regression', editorRevision: 1,
      }));
    }, input);
    await page.getByRole('button', { name: '调整此工序', exact: true }).click();
    const time = page.getByLabel('调整开工', { exact: true });
    assert.equal(await time.inputValue(), input.tasks[0].start);
    await page.getByLabel('调整设备', { exact: true }).selectOption('e'.repeat(48));
    await page.getByRole('button', { name: '保存调整', exact: true }).click();
    await page.getByRole('button', { name: '调整此工序', exact: true }).waitFor();
    let calls = await page.evaluate(() => editorCalls);
    assert.equal(calls.length, 1); assert.equal(calls[0].input.start, input.tasks[0].start);
    assert.equal(calls[0].input.machine_ref, 'e'.repeat(48));
    await page.getByRole('button', { name: '调整此工序', exact: true }).click();
    await time.fill('2026-09-09T13:00:00.000001');
    await page.getByRole('button', { name: '保存调整', exact: true }).click();
    await page.getByRole('button', { name: '调整此工序', exact: true }).waitFor();
    calls = await page.evaluate(() => editorCalls);
    assert.equal(calls.length, 2); assert.equal(calls[1].input.start, '2026-09-09T13:00:00.000001');
    await page.getByRole('button', { name: '调整此工序', exact: true }).click();
    await time.fill('2026-02-30T13:00:00.123456');
    await page.getByRole('button', { name: '保存调整', exact: true }).click();
    assert.equal((await page.evaluate(() => editorCalls)).length, 2);
    await page.getByText(/开工时间请按/).waitFor();
    await page.screenshot({ path: path.join(output, 'invalid-date-kept-for-correction.png'), fullPage: true });
    assert.deepEqual(report.errors, []); assert.deepEqual(report.unexpected_requests, []);
    report.resource_change_preserved_time = true;
    report.one_microsecond_input_preserved = true;
    report.invalid_date_not_submitted = true;
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(report, null, 2));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
