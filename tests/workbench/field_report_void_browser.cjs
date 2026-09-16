'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), { spawn } = require('node:child_process');
const { chromium } = require('playwright'), H = require('./field_workspace_probe_harness.cjs');
const output = path.resolve(process.argv[2] || '');
assert(process.argv[2] && !output.startsWith(H.root + '/'));
fs.mkdirSync(output, { recursive: true });
const result = { cases: [], errors: [], screenshots: [], production_db: false, global_build: false };
let backend, server, browser, page;
const button = name => page.getByRole('button', { name, exact: true });
const table = () => page.getByRole('table', { name: '逐次报工记录', exact: true });
async function run(name, action) { await action(); result.cases.push({ name, passed: true }); }
async function open(sequence) {
  await page.getByRole('button', { name: new RegExp('^查看报工 B1 ' + sequence + ' Turning') }).click();
  await table().waitFor();
}
async function inspect() {
  const response = page.waitForResponse(item => item.url().endsWith('/void-preview'));
  await button('查看撤销影响').click();
  const body = await (await response).json(); assert.equal(body.ok, true, JSON.stringify(body)); return body.data;
}
async function screenshot(name) {
  const file = path.join(output, name + '.png'); await page.screenshot({ path: file }); result.screenshots.push(file);
}
async function main() {
  try {
    backend = spawn(path.join(H.root, '.venv/bin/python'), ['-m', 'tests.workbench.field_workspace_probe_server', path.join(output, 'db')], { cwd: H.root, stdio: ['ignore', 'pipe', 'pipe'] });
    let stderr = ''; backend.stderr.on('data', chunk => stderr += chunk);
    const ready = await new Promise((resolve, reject) => {
      let text = ''; backend.stdout.on('data', chunk => { text += chunk; try { resolve(JSON.parse(text.split('\n')[0])); } catch (_) {} });
      backend.on('exit', code => reject(new Error('Fixture exited ' + code + ': ' + stderr)));
    });
    server = H.createServer(ready.url, result); await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true }); result.browser = browser.version();
    page = await browser.newPage({ viewport: { width: 1392, height: 924 } }); page.setDefaultTimeout(12000);
    page.on('pageerror', error => result.errors.push(error.stack));
    await page.goto('http://127.0.0.1:' + server.address().port); await page.locator('[data-field-task]').first().waitFor();
    await open(4);
    await run('visible withdrawal uses the local rotate icon and keeps delete semantics separate', async () => {
      const action = table().getByRole('button', { name: /^撤销 / }).first();
      assert.equal(await action.innerText(), '撤销'); assert.equal(await action.locator('[data-wb-icon="rotate-ccw"] path').count(), 2);
      await action.click(); await page.getByRole('form', { name: '撤销这次报工' }).waitFor();
      assert.equal(await button('确认撤销这次报工').count(), 0);
    });
    await run('a reason produces a read-only before and after preview for exactly one report', async () => {
      await page.getByLabel('撤销原因', { exact: true }).fill('该次记录误登记了其他工序的产出');
      await page.getByLabel('撤销经办人', { exact: true }).fill('浏览器测试员');
      const data = await inspect(); assert(data.can_confirm);
      assert.equal(data.before.known_completed_quantity, 6); assert.equal(data.after.known_completed_quantity, 5);
      assert.equal(await table().locator('tbody > tr').count(), 6); await screenshot('void-preview-light');
    });
    await run('changing the reason invalidates the confirmation preview', async () => {
      await page.getByLabel('撤销原因', { exact: true }).fill('原记录重复登记，保留撤销原因');
      assert.equal(await button('确认撤销这次报工').count(), 0); await inspect();
    });
    await run('confirmation appends once and refreshed UI retains the original history', async () => {
      const response = page.waitForResponse(item => item.url().endsWith('/void'));
      await button('确认撤销这次报工').click(); const body = await (await response).json();
      assert.equal(body.result, 'committed'); assert.equal(body.data.state, 'voided');
      await page.getByRole('form', { name: '撤销这次报工' }).waitFor({ state: 'hidden' });
      await page.getByText('已撤销报工 · 1 条', { exact: true }).waitFor();
      assert.equal(await table().locator('tbody > tr').count(), 5);
      await page.getByText('已撤销报工 · 1 条', { exact: true }).click();
      assert((await page.locator('.field-detail').innerText()).includes('原数量 1 件 · 原有效工时 0.5 小时'));
      await page.setViewportSize({ width: 1280, height: 720 });
      const clipped = await table().locator('.field-report-actions button').evaluateAll(buttons => buttons.some(button => {
        const buttonBox = button.getBoundingClientRect(), cell = button.closest('td').getBoundingClientRect();
        return buttonBox.left < cell.left - 1 || buttonBox.right > cell.right + 1 || button.scrollWidth > button.clientWidth + 1;
      })); assert.equal(clipped, false, 'withdrawal action text must fit the actions column');
      await screenshot('void-history-1280');
    });
    await run('real downstream production is explained and disables confirmation', async () => {
      await open(1); await table().getByRole('button', { name: /^撤销 / }).first().click();
      await page.getByLabel('撤销原因', { exact: true }).fill('检查后道依赖的拒绝路径');
      const data = await inspect(); assert.equal(data.can_confirm, false); assert(data.downstream_impacts.length > 0);
      assert(await button('确认撤销这次报工').isDisabled());
      assert((await page.getByRole('region', { name: '撤销影响' }).innerText()).includes('需要先处理'));
      await screenshot('void-blocked-1280');
      await button('深色：关').click();
      await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
      assert(await button('确认撤销这次报工').isDisabled()); await screenshot('void-blocked-dark-1280');
    });
    assert.deepEqual(result.errors, []);
    fs.writeFileSync(path.join(output, 'report-void-result.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify({ passed: true, cases: result.cases.length, output }));
  } finally {
    if (browser) await browser.close(); if (server) await new Promise(resolve => server.close(resolve)); if (backend) backend.kill();
  }
}
main().catch(error => { fs.writeFileSync(path.join(output, 'report-void-result.json'), JSON.stringify({ ...result, failure: error.stack }, null, 2)); console.error(error); process.exitCode = 1; });
