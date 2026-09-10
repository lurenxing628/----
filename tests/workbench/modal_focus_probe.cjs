/* Current-source component proof with simulated adapters, no business service or database. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const http = require('node:http'), crypto = require('node:crypto'), { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass an output directory');
fs.mkdirSync(output, { recursive: true });
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const names = ['resource-contract.js', 'resource-session.js', 'CalendarContract.js', 'ResourceControls.jsx', 'ResourceForms.jsx', 'ProcessOpTypeCreate.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx',
  'WorkbenchSelectMenu.jsx', 'WorkbenchControls.jsx', 'WorkbenchNumberControls.jsx'];
const sources = names.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(
  name === 'ResourceControls.jsx' && process.env.AY_BASELINE ? process.env.AY_BASELINE : path.join(root, 'frontend/workbench/app', name), 'utf8') }));
sources.push({ path: 'tests/workbench/modal_focus_fixture.jsx', code: fs.readFileSync(path.join(__dirname, 'modal_focus_fixture.jsx'), 'utf8') });
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
fs.mkdirSync(path.join(output, 'sources'), { recursive: true });
sources.forEach(row => fs.writeFileSync(path.join(output, 'sources', path.basename(row.path)), row.code));
fs.writeFileSync(path.join(output, 'components.js'), built.outputs.map(row => row.code).join('\n;\n'));
const manifestBytes = fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')), manifest = JSON.parse(manifestBytes);
const shared = manifest.scripts.filter(name => name.startsWith('workbench/vendor/') || name.startsWith('workbench/assets/foundation-'));
const assets = new Map();
for (const record of manifest.files) {
  const name = record.path, bytes = fs.readFileSync(path.join(root, 'static', name));
  assert.equal(hash(bytes), record.sha256, 'Shared build is changing: retry after it settles');
  assets.set('/static/' + name, { bytes, mime: record.mime });
}
const report = { scope: 'actual-resource-components-simulated-adapter', global_build: false, database_access: false,
  target: built.target, style_build_id: manifest.build_id, manifest_sha256: hash(manifestBytes),
  sources: sources.map(row => ({ path: row.path, sha256: hash(row.code) })), cases: [], errors: [], external: [] };
report.runtime_mode = process.env.AY_REACT_DEV ? 'development-strict-effects' : 'vendored-production';
if (process.env.AY_REACT_DEV) {
  report.development_runtime = ['react', 'react-dom'].map(name => {
    const base = path.join(process.env.AY_REACT_DEV, name), pkg = JSON.parse(fs.readFileSync(path.join(base, 'package.json')));
    assert.equal(pkg.version, '18.3.1');
    const production = '/static/workbench/vendor/' + name + '-18.3.1.production.min.js';
    assert.equal(hash(fs.readFileSync(path.join(base, 'umd', name + '.production.min.js'))), hash(assets.get(production).bytes));
    const bytes = fs.readFileSync(path.join(base, 'umd', name + '.development.js'));
    assets.set(production, { bytes, mime: 'application/javascript' });
    return { name, version: pkg.version, sha256: hash(bytes) };
  });
}
const html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' +
  manifest.styles.map(name => '<link rel="stylesheet" href="/static/' + name + '">').join('') + '</head><body class="aps-workbench">' +
  '<main class="plana"><button id="outside">Outside</button><div id="controls-root"></div><div id="fixture-root"></div></main>' +
  shared.map(name => '<script src="/static/' + name + '"></script>').join('') + '<script src="/components.js"></script></body></html>';
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://fixture').pathname;
  if (url === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (url === '/components.js') { res.setHeader('Content-Type', 'application/javascript'); res.end(built.outputs.map(row => row.code).join('\n;\n')); return; }
  if (url === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  const asset = assets.get(url);
  if (!asset) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
let browser, page, variant;
const dialog = level => page.getByRole('dialog', { name: '层 ' + level, exact: true });
const focused = selector => page.locator(selector).evaluate(node => node === document.activeElement);
async function mount(spec = {}) { await page.evaluate(spec => mountFocus(spec), spec); await page.locator('#flow-trigger').click(); }
async function empty() { await page.evaluate(() => unmountFocus()); await page.waitForFunction(() => !document.querySelector('.modal-bg')); }
async function run(name, fn) {
  const errors = report.errors.length;
  try { await fn(); assert.equal(report.errors.length, errors, 'Unhandled browser errors'); report.cases.push({ variant, name, passed: true }); }
  catch (error) { report.cases.push({ variant, name, passed: false, message: error.message }); await page.screenshot({ path: path.join(output, variant + '-' + name + '-failure.png') }); throw error; }
}
async function shot(name) {
  const geometry = await page.locator('.modal-bg > [role="dialog"]:visible').evaluateAll(nodes => nodes.map(node => {
    const rect = node.getBoundingClientRect(); return { title: node.querySelector('.modal-h2').textContent, left: rect.left, right: rect.right,
      top: rect.top, bottom: rect.bottom, width: innerWidth, height: innerHeight };
  }));
  for (const box of geometry) assert(box.left >= 0 && box.right <= box.width + 1 && box.top >= 0 && box.bottom <= box.height + 1);
  const file = variant + '-' + name + '.png'; await page.screenshot({ path: path.join(output, file) });
  report.cases.push({ variant, name, passed: true, screenshot: file, geometry });
}
async function saveResource(spec = {}) {
  await mount({ flow: true, ...spec }); await page.locator('#child-trigger').click();
  await page.locator('input[name="business_code"]').fill('AY-OP-NEW'); await page.locator('input[name="label"]').fill('AY待建工种');
  await page.locator('select[name="category"]').click(); await page.locator('.wb-control-popup').getByRole('option', { name: '自制', exact: true }).click();
  await page.getByRole('dialog', { name: '新增自制工种', exact: true }).locator('.modal-f').getByRole('button', { name: '保存', exact: true }).click();
}
async function cases() {
  await run('resource-save-close-restores-visible-parent', async () => {
    await saveResource(process.env.AY_UNSUSPENDED ? { suspend: false } : {}); await page.getByText('已重新读取最新数据。', { exact: true }).waitFor(); await shot('saved-resource');
    await page.getByRole('dialog', { name: '新增自制工种', exact: true }).locator('.modal-f').getByRole('button', { name: '关闭', exact: true }).click();
    await page.waitForFunction(() => document.activeElement.id === 'child-trigger');
    assert.deepEqual(await page.evaluate(() => focusFixture.closed), ['resource']);
    assert.equal(await page.evaluate(() => focusFixture.calls.length), 1); assert.equal(await page.evaluate(() => focusFixture.receipts.length), 1);
    await shot('resource-closed-parent-restored');
    await page.getByRole('button', { name: '关闭详情', exact: true }).click(); assert(await focused('#flow-trigger'));
    assert(await page.evaluate(() => document.documentElement.style.getPropertyValue('overflow') !== 'hidden'), 'Hidden mounted dialogs cannot lock the background'); await empty();
  });
  if (process.env.AY_SMOKE) return;
  await run('launcher-disabled-in-opening-commit-restores-on-close', async () => {
    await mount({ disableTrigger: true }); assert(await page.locator('#flow-trigger').isDisabled());
    await page.keyboard.press('Escape'); await page.waitForFunction(() => document.activeElement.id === 'flow-trigger');
    assert(await page.locator('#flow-trigger').isEnabled()); await empty();
  });
  await run('nested-modal-scroll-lock-restores-inline-priorities', async () => {
    const state = () => page.evaluate(() => [document.documentElement, document.body].map(node =>
      ['overflow', 'overflow-x', 'overflow-y'].map(name => [name, node.style.getPropertyValue(name), node.style.getPropertyPriority(name)])));
    await page.evaluate(() => {
      document.documentElement.style.setProperty('overflow-x', 'auto');
      document.documentElement.style.setProperty('overflow-y', 'scroll', 'important');
      document.body.style.setProperty('overflow', 'auto', 'important');
    });
    const before = await state();
    await mount({ portal: true, strict: true });
    const locked = await state();
    assert(locked.every(properties => properties.every(([, value, priority]) => value === 'hidden' && priority === 'important')));
    await page.locator('#next-1').click(); await page.locator('#next-2').click();
    await page.evaluate(() => document.body.style.setProperty('padding-top', '3px'));
    await page.keyboard.press('Escape'); await page.keyboard.press('Escape'); assert.deepEqual(await state(), locked);
    await page.keyboard.press('Escape'); await page.waitForFunction(() => document.activeElement.id === 'flow-trigger');
    assert.deepEqual(await state(), before);
    assert.equal(await page.evaluate(() => document.body.style.paddingTop), '3px', 'Unlock must preserve unrelated inline changes');
    await empty(); assert.deepEqual(await state(), before);
    await page.evaluate(() => { document.documentElement.style.removeProperty('overflow'); document.body.style.removeProperty('overflow'); document.body.style.removeProperty('padding-top'); });
  });
  await run('resource-unsuspended-parent-save-close', async () => {
    await saveResource({ suspend: false }); await page.getByText('已重新读取最新数据。', { exact: true }).waitFor();
    await page.getByRole('dialog', { name: '新增自制工种', exact: true }).locator('.modal-f').getByRole('button', { name: '关闭', exact: true }).click();
    assert(await focused('#child-trigger')); await empty();
  });
  await run('pending-receipt-remount-stays-locked', async () => {
    await saveResource({ pending: true }); await page.getByRole('button', { name: '查询原请求回执', exact: true }).waitFor();
    await page.keyboard.press('Escape'); await page.mouse.click(4, 4); assert.deepEqual(await page.evaluate(() => focusFixture.closed), []);
    const intent = await page.evaluate(() => focusFixture.calls[0].body.request_key);
    await page.evaluate(() => { ReactDOM.flushSync(() => focusFixture.parentUnmount()); });
    await page.locator('#flow-trigger').click(); await page.locator('#child-trigger').click();
    await page.getByRole('button', { name: '查询原请求回执', exact: true }).waitFor();
    await page.keyboard.press('Escape'); assert.deepEqual(await page.evaluate(() => focusFixture.closed), []);
    await page.evaluate(() => { focusFixture.resolved = true; });
    await page.getByRole('button', { name: '查询原请求回执', exact: true }).click();
    await page.getByText('服务器已确认提交。', { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => focusFixture.calls.length), 1);
    assert((await page.evaluate(() => focusFixture.lookups)).every(key => key === intent));
    await page.getByRole('dialog', { name: '新增工种', exact: true }).locator('.modal-f').getByRole('button', { name: '取消', exact: true }).click();
    assert(await focused('#child-trigger')); await empty();
  });
  for (const portal of [false, true]) await run('three-layers-' + (portal ? 'portal' : 'nested-dom'), async () => {
    await mount({ portal }); await page.locator('#next-1').click(); await page.locator('#next-2').click();
    assert(await focused('#input-3'));
    await page.locator('#outside').evaluate(node => node.focus()); assert(await focused('#input-3'));
    await dialog(3).locator('.modal-x').focus(); await page.keyboard.press('Shift+Tab'); assert(await focused('#end-3'));
    await page.keyboard.press('Tab'); assert(await dialog(3).locator('.modal-x').evaluate(node => node === document.activeElement));
    await page.keyboard.press('Escape'); assert.deepEqual(await page.evaluate(() => focusFixture.closed), [3]); assert(await focused('#next-2'));
    await page.keyboard.press('Escape'); assert.deepEqual(await page.evaluate(() => focusFixture.closed), [3, 2]); assert(await focused('#next-1'));
    await page.keyboard.press('Escape'); assert(await focused('#flow-trigger')); await empty();
  });
  await run('same-commit-initial-portals-and-effect-remount', async () => {
    for (let index = 0; index < 6; index++) {
      await mount({ initial: true, portal: true, strict: true }); assert(await focused('#input-3'));
      assert.equal(await page.evaluate(() => focusFixture.effects.setup), process.env.AY_REACT_DEV ? 2 : 1);
      await page.evaluate(() => ReactDOM.flushSync(() => focusFixture.setOpen(false))); assert(await focused('#flow-trigger'));
      await page.locator('#flow-trigger').click(); assert(await focused('#input-3'));
      await empty(); assert.equal(await page.evaluate(() => focusFixture.effects.setup), await page.evaluate(() => focusFixture.effects.cleanup));
    }
  });
  await run('rapid-child-toggle-and-close-both-same-commit', async () => {
    await mount({ portal: true }); await page.locator('#next-1').click();
    await page.evaluate(() => {
      for (let index = 0; index < 30; index++) ReactDOM.flushSync(() => focusFixture.layers[1].setChild(index % 2 === 1));
    });
    assert(await focused('#input-2'));
    await page.evaluate(() => {
      ReactDOM.flushSync(() => focusFixture.layers[1].setChild(false));
      ReactDOM.flushSync(() => focusFixture.setOpen(false));
    });
    assert(await focused('#flow-trigger')); await empty();
  });
  await run('independent-sibling-parent-removed-first', async () => {
    await mount({ siblings: true }); await page.locator('#child-trigger').click(); assert(await focused('#sibling-input'));
    await page.evaluate(() => ReactDOM.flushSync(() => focusFixture.removeParent())); assert(await focused('#sibling-input'));
    await page.getByRole('button', { name: '关闭独立子窗', exact: true }).click(); assert(await focused('#flow-trigger')); await empty();
  });
  await run('rapid-suspended-toggle-and-parent-unmount', async () => {
    await mount({ portal: true }); await page.locator('#next-1').click();
    await page.evaluate(() => {
      for (let index = 0; index < 30; index++) ReactDOM.flushSync(() => focusFixture.layers[2].setSuspended(index % 2 === 0));
    });
    assert(await focused('#input-2'));
    await page.evaluate(() => ReactDOM.flushSync(() => focusFixture.layers[2].setSuspended(true))); assert(await focused('#next-1'));
    await page.keyboard.press('Tab'); assert(await dialog(1).evaluate(node => node.contains(document.activeElement)));
    await page.evaluate(() => ReactDOM.flushSync(() => focusFixture.layers[2].setSuspended(false))); assert(await focused('#input-2'));
    await page.evaluate(() => ReactDOM.flushSync(() => focusFixture.setOpen(false))); assert(await focused('#flow-trigger')); await empty();
  });
  await run('non-top-does-not-close-or-consume-input', async () => {
    await mount({ portal: true }); await page.locator('#next-1').click();
    await dialog(1).locator('.modal-x').evaluate(node => node.click()); assert.deepEqual(await page.evaluate(() => focusFixture.closed), []);
    await dialog(1).evaluate(node => { const bg = node.parentElement; for (const type of ['pointerdown', 'pointerup']) bg.dispatchEvent(new PointerEvent(type, { button: 0, bubbles: true })); bg.click(); });
    assert.deepEqual(await page.evaluate(() => focusFixture.closed), []);
    await page.locator('#input-2').fill('top-only'); await page.keyboard.press('Escape');
    assert.deepEqual(await page.evaluate(() => focusFixture.closed), [2]); assert(await focused('#next-1')); await empty();
  });
  await run('custom-dropdown-date-and-filter-consume-first', async () => {
    await mount({ portal: true }); await page.locator('#next-1').click();
    await page.getByLabel('选择 2', { exact: true }).click(); await page.locator('.wb-control-popup').waitFor();
    await page.keyboard.press('Escape'); assert.equal(await page.locator('.wb-control-popup').count(), 0); assert.deepEqual(await page.evaluate(() => focusFixture.closed), []);
    await page.getByLabel('选择 2', { exact: true }).click(); await page.locator('.wb-control-popup').waitFor();
    await page.keyboard.press('Tab'); assert.equal(await page.locator('.wb-control-popup').count(), 0);
    assert(await dialog(2).evaluate(node => node.contains(document.activeElement)));
    const date = page.getByLabel('日期 2', { exact: true }), box = await date.boundingBox(); await page.mouse.click(box.x + box.width - 12, box.y + box.height / 2);
    await page.locator('.wb-control-popup').waitFor();
    await page.locator('.wb-control-popup').getByRole('textbox', { name: '年份', exact: true }).click();
    for (const key of ['Tab', 'Shift+Tab']) for (let index = 0; index < 25; index++) {
      await page.keyboard.press(key); assert(await page.locator('.wb-control-popup').evaluate(node => node.contains(document.activeElement)));
    }
    await page.keyboard.press('Escape'); assert.equal(await page.locator('.wb-control-popup').count(), 0); assert(await date.evaluate(node => node === document.activeElement));
    await page.locator('#filter-2').click(); await page.getByLabel('列筛选条件').fill('AY'); await page.keyboard.press('Escape');
    assert.equal(await page.locator('[data-wb-table-filter]').count(), 0); assert.deepEqual(await page.evaluate(() => focusFixture.closed), []);
    await empty();
  });
  await run('later-control-listeners-still-consume-before-modal', async () => {
    await mount({ portal: true }); await page.locator('#next-1').click();
    await page.evaluate(() => mountFocusControls());
    await page.getByLabel('选择 2', { exact: true }).click(); await page.locator('.wb-control-popup').waitFor();
    await page.keyboard.press('Escape'); assert.equal(await page.locator('.wb-control-popup').count(), 0);
    assert.deepEqual(await page.evaluate(() => focusFixture.closed), []);
    await page.keyboard.press('Escape'); assert.deepEqual(await page.evaluate(() => focusFixture.closed), [2]); await empty();
  });
  await run('disabled-hidden-trigger-safe-restore', async () => {
    await mount({ portal: true }); await page.locator('#next-1').click();
    await page.locator('#next-1').evaluate(node => { node.disabled = true; });
    await page.keyboard.press('Escape'); assert(await dialog(1).evaluate(node => node.contains(document.activeElement) && !document.activeElement.disabled));
    await empty();
    await mount({ portal: true }); await page.locator('#next-1').click();
    await page.locator('#next-1').evaluate(node => { node.style.visibility = 'hidden'; });
    await page.keyboard.press('Escape'); assert(await dialog(1).evaluate(node => node.contains(document.activeElement) && getComputedStyle(document.activeElement).visibility === 'visible'));
    await empty();
  });
  await run('trigger-lost-focusability-safe-restore', async () => {
    await mount({ portal: true, generic: true }); await page.locator('#next-1').click();
    await page.locator('#next-1').evaluate(node => node.removeAttribute('tabindex'));
    await page.keyboard.press('Escape');
    assert(await dialog(1).evaluate(node => node.contains(document.activeElement) && document.activeElement.id !== 'next-1'));
    await empty();
  });
  await run('locked-backdrop-drag-and-empty-tab', async () => {
    await mount(); await page.evaluate(() => ReactDOM.flushSync(() => focusFixture.layers[1].setLocked(true)));
    await page.keyboard.press('Escape'); await page.mouse.click(4, 4); assert.deepEqual(await page.evaluate(() => focusFixture.closed), []);
    await page.evaluate(() => ReactDOM.flushSync(() => focusFixture.layers[1].setLocked(false)));
    const box = await dialog(1).locator('.modal-head').boundingBox();
    await page.mouse.move(box.x + 20, box.y + 15); await page.mouse.down(); await page.mouse.move(4, 4); await page.mouse.up();
    await page.mouse.move(4, 4); await page.mouse.down(); await page.mouse.move(box.x + 20, box.y + 15); await page.mouse.up();
    assert.deepEqual(await page.evaluate(() => focusFixture.closed), []);
    await dialog(1).evaluate(node => { node.querySelectorAll('button,input,select').forEach(item => { item.disabled = true; }); node.focus(); });
    await page.keyboard.press('Tab'); assert(await dialog(1).evaluate(node => node === document.activeElement));
    await page.keyboard.press('Shift+Tab'); assert(await dialog(1).evaluate(node => node === document.activeElement));
    await page.mouse.click(4, 4); assert.deepEqual(await page.evaluate(() => focusFixture.closed), [1]); await empty();
  });
  await run('listeners-fully-unbound', async () => {
    await empty(); await page.locator('#outside').focus(); await page.keyboard.press('Escape'); assert(await focused('#outside'));
    const listeners = await page.evaluate(() => window.focusListeners.filter(row => row.active && ['modalKeydown', 'retainModalFocus'].includes(row.name)));
    assert.deepEqual(listeners, []);
    assert.equal(await page.evaluate(() => focusListeners.filter(row => row.name === 'modalKeydown').length > 0), true);
  });
}
(async () => {
  try {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const origin = 'http://127.0.0.1:' + server.address().port;
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER || '/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium', headless: true });
    report.browser = browser.version(); assert.match(report.browser, /^109\./);
    const variants = process.env.AY_SMOKE ? [[1920, 1080, 'light']] : [[1920, 1080, 'light'], [1920, 1080, 'dark'], [1392, 924, 'light'], [1392, 924, 'dark']];
    for (const [width, height, theme] of variants) {
      variant = width + '-' + theme;
      const context = await browser.newContext({ viewport: { width, height } });
      await context.addInitScript(theme => {
        document.addEventListener('DOMContentLoaded', () => { document.documentElement.dataset.theme = theme; });
        localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme);
        window.focusListeners = [];
        const add = document.addEventListener, remove = document.removeEventListener;
        document.addEventListener = function (type, listener, options) {
          if (type === 'keydown' || type === 'focusin') focusListeners.push({ type, listener, options, name: listener.name, active: true });
          return add.call(this, type, listener, options);
        };
        document.removeEventListener = function (type, listener, options) {
          focusListeners.filter(row => row.type === type && row.listener === listener && row.options === options).forEach(row => { row.active = false; });
          return remove.call(this, type, listener, options);
        };
      }, theme);
      page = await context.newPage(); page.setDefaultTimeout(10000);
      page.on('pageerror', error => report.errors.push({ variant, message: error.message, stack: error.stack }));
      page.on('console', message => { if (message.type() === 'error') report.errors.push({ variant, message: message.text() }); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      await page.goto(origin); report.react_version = await page.evaluate(() => React.version); assert.match(report.react_version, /^18\./);
      await cases(); await context.close(); console.log('AY_MODAL_FOCUS_VARIANT ' + variant);
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []); report.passed = true;
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(output, 'modal-focus-result.json'), JSON.stringify(report, null, 2));
  }
  console.log(JSON.stringify({ passed: report.passed, browser: report.browser, cases: report.cases.length, output }));
})().catch(error => { console.error(error); process.exitCode = 1; server.close(); });
