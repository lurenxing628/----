'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass a temporary output directory');
fs.mkdirSync(output, { recursive: true });
const names = ['frontend/workbench/app/resource-contract.js', 'frontend/workbench/app/WorkbenchGuards.js', 'frontend/workbench/app/ResourceControls.jsx', 'frontend/workbench/app/WorkbenchGuardHost.jsx',
  'tests/workbench/dirty_guard_fixture.jsx'];
const sources = names.map(name => ({ path: name, code: fs.readFileSync(path.join(root, name), 'utf8') }));
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = built.outputs.map(row => row.code).join('\n;\n'), assets = new Map();
for (const name of ['react', 'react-dom']) assets.set('/' + name + '.js', fs.readFileSync(path.join(root, 'static/workbench/vendor/' + name + '-18.3.1.production.min.js')));
const html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>body{font:16px sans-serif}.modal-bg{position:fixed;inset:0;display:grid;place-items:center;background:#0005}.modal{background:white;padding:24px;min-width:500px;max-width:90vw}.modal-head,.modal-f{display:flex;gap:12px}input,button{margin:8px;padding:8px}</style></head><body><div id="root"></div><script src="/react.js"></script><script src="/react-dom.js"></script><script src="/components.js"></script></body></html>';
const server = http.createServer((request, response) => {
  const route = new URL(request.url, 'http://fixture').pathname;
  if (route === '/' || route === '/left') { response.setHeader('Content-Type', 'text/html;charset=utf-8'); response.end(html); }
  else if (route === '/components.js') { response.setHeader('Content-Type', 'application/javascript'); response.end(scripts); }
  else if (assets.has(route)) { response.setHeader('Content-Type', 'application/javascript'); response.end(assets.get(route)); }
  else { response.writeHead(204); response.end(); }
});
const report = { global_build: false, database_access: false, cases: [], errors: [], external: [], nativeDialogs: [], sources: sources.map(row => ({ path: row.path,
  sha256: crypto.createHash('sha256').update(row.code).digest('hex') })) };
let browser, page;
const dialog = () => page.getByRole('dialog', { name: '离开前确认', exact: true });
const button = name => page.getByRole('button', { name, exact: true });
async function reset() { await page.reload(); await page.getByLabel('A', { exact: true }).waitFor(); }
async function run(name, action) { await reset(); const errors = report.errors.length; await action(); assert.equal(report.errors.length, errors); report.cases.push({ name, passed: true }); }
async function result(expected) { await page.waitForFunction(value => JSON.stringify(guardResults) === JSON.stringify(value), expected); }
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
  report.browser = browser.version(); page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
  page.on('pageerror', error => report.errors.push(error.message));
  page.on('request', request => { if (!request.url().startsWith(origin)) report.external.push(request.url()); });
  // A deliberate page reload between cases acknowledges the native browser leave warning.
  page.on('dialog', event => { report.nativeDialogs.push(event.type()); event.accept(); });
  await page.goto(origin);
  await run('unchanged-and-restored-input-leave-without-confirmation', async () => {
    await button('离开全部').click(); await result([true]); assert.equal(await dialog().count(), 0);
    await page.getByLabel('A', { exact: true }).fill('草稿'); await page.getByLabel('A', { exact: true }).fill('');
    await button('离开全部').click(); await result([true, true]); assert.equal(await dialog().count(), 0);
  });
  await run('scope-cancel-retains-input-and-focus', async () => {
    await page.getByLabel('B', { exact: true }).fill('保留 B'); await button('离开 A').click(); await result([true]);
    await page.getByLabel('A', { exact: true }).fill('保留 A'); await button('离开 A').click();
    assert((await dialog().innerText()).includes('A 未保存')); assert(!(await dialog().innerText()).includes('B 未保存'));
    await button('留在当前页面').click(); await result([true, false]);
    assert.equal(await page.getByLabel('A', { exact: true }).inputValue(), '保留 A');
    assert.equal(await page.getByLabel('B', { exact: true }).inputValue(), '保留 B');
    await page.waitForFunction(() => document.activeElement.id === 'request-a');
  });
  await run('all-owners-and-escape-cancel-without-recursion', async () => {
    await page.getByLabel('A', { exact: true }).fill('A1'); await page.getByLabel('B', { exact: true }).fill('B1');
    await button('离开全部').click(); assert((await dialog().innerText()).includes('A 未保存')); assert((await dialog().innerText()).includes('B 未保存'));
    await page.keyboard.press('Escape'); await result([false]); assert.equal(await dialog().count(), 0);
  });
  await run('allow-once-and-concurrent-request-denied', async () => {
    await page.getByLabel('A', { exact: true }).fill('A1'); await button('离开全部').click();
    await page.evaluate(() => askGuard({ owner: 'B' })); // clean scope is independent
    await page.evaluate(() => { askGuard({ owner: 'A' }); }); await result([true, false]);
    await button('放弃未保存内容并继续').click(); await result([true, false, true]); assert.equal(await dialog().count(), 0);
    assert(await page.evaluate(() => WorkbenchGuards.hasDirty()), 'approval must not mutate editor facts');
  });
  await run('pending-command-cannot-be-discarded', async () => {
    await page.getByLabel('A pending', { exact: true }).check(); await button('离开全部').click();
    await page.getByRole('dialog', { name: '上次操作还没有确认结果', exact: true }).waitFor(); assert.equal(await button('放弃未保存内容并继续').count(), 0);
    await button('留在当前页面').click(); await result([false]); assert(await page.getByLabel('A pending', { exact: true }).isChecked());
  });
  await run('external-leave-and-owner-exclusions', async () => {
    const prevented = () => page.evaluate(() => { const event = new Event('beforeunload', { cancelable: true }); dispatchEvent(event); return event.defaultPrevented; });
    assert.equal(await prevented(), false); await page.getByLabel('A', { exact: true }).fill('A1'); assert.equal(await prevented(), true);
    assert.equal(await page.evaluate(() => WorkbenchGuards.hasDirty({ excludeOwners: ['A'] })), false);
    await page.getByLabel('A', { exact: true }).fill(''); assert.equal(await prevented(), false);
  });
  await run('same-owner-multiple-registrations-unregister-independently', async () => {
    assert(await page.evaluate(() => {
      const first = WorkbenchGuards.register({ owner: 'shared', dirty: true, message: '第一份' });
      const second = WorkbenchGuards.register({ owner: 'shared', dirty: true, message: '第二份' });
      first(); const retained = WorkbenchGuards.hasDirty({ owner: 'shared' }); second();
      return retained && !WorkbenchGuards.hasDirty({ owner: 'shared' });
    }));
  });
  await run('readonly-modal-not-blocked-by-another-editor', async () => {
    await page.getByLabel('A', { exact: true }).fill('A1'); await button('打开只读弹窗').click(); await page.keyboard.press('Escape');
    assert.equal(await page.getByRole('dialog').count(), 0); assert.equal(await page.getByLabel('A', { exact: true }).inputValue(), 'A1');
  });
  await run('external-confirmation-grants-only-one-unload', async () => {
    await page.getByLabel('A', { exact: true }).fill('A1');
    const count = report.nativeDialogs.length;
    await button('外部离开').click(); await dialog().waitFor(); await button('留在当前页面').click();
    assert.equal(new URL(page.url()).pathname, '/'); assert.equal(report.nativeDialogs.length, count);
    await button('外部离开').click(); await dialog().waitFor(); await button('放弃未保存内容并继续').click();
    await page.waitForURL(origin + '/left'); assert.equal(report.nativeDialogs.length, count, 'No duplicate beforeunload prompt after explicit confirmation');
    await page.getByLabel('A', { exact: true }).fill('新页面未保存'); await page.reload();
    assert.equal(report.nativeDialogs.length, count + 1, 'Later external departure must still warn');
    await page.goto(origin);
  });
  await run('unused-external-permit-expires-without-clearing-drafts', async () => {
    await page.getByLabel('A', { exact: true }).fill('A1');
    await page.evaluate(() => { window.externalAttempt = WorkbenchGuards.leaveExternal(() => {}); });
    await dialog().waitFor(); await button('放弃未保存内容并继续').click();
    await page.evaluate(() => window.externalAttempt); await page.waitForTimeout(20);
    assert(await page.evaluate(() => { const event = new Event('beforeunload', { cancelable: true }); dispatchEvent(event); return event.defaultPrevented; }));
    assert(await page.evaluate(() => WorkbenchGuards.hasDirty()));
  });
  await run('modal-footer-and-escape-confirm-once', async () => {
    await button('打开编辑弹窗').click(); await page.getByLabel('弹窗输入').fill('保持'); await page.keyboard.press('Escape'); await dialog().waitFor();
    await page.keyboard.press('Escape'); assert.equal(await dialog().count(), 0); assert.equal(await page.getByLabel('弹窗输入').inputValue(), '保持');
    await button('取消编辑').click(); await dialog().waitFor(); await button('放弃未保存内容并继续').click();
    await page.waitForFunction(() => !document.querySelector('[role="dialog"]'));
    await button('打开编辑弹窗').click(); await page.getByLabel('弹窗输入').fill('再次'); await page.keyboard.press('Escape'); await dialog().waitFor();
    await button('放弃未保存内容并继续').click(); await page.waitForFunction(() => !document.querySelector('[role="dialog"]'));
    await page.waitForFunction(() => document.activeElement.id === 'open-edit');
  });
  report.passed = true;
})().catch(error => { report.passed = false; report.failure = error.stack; process.exitCode = 1; }).finally(async () => {
  if (page && !report.passed) await page.screenshot({ path: path.join(output, 'failure.png') }).catch(() => {});
  fs.writeFileSync(path.join(output, 'dirty-guard-result.json'), JSON.stringify(report, null, 2));
  if (browser) await browser.close(); server.close(); console.log(JSON.stringify(report));
});
