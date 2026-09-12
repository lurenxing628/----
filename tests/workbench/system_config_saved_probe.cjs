/* Compile current components in memory. All API requests use a dedicated guarded Flask fixture. */
'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto');
const assert = require('node:assert/strict'), { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], scenario = process.argv[3], backend = new URL(process.argv[4]);
assert.equal(backend.hostname, '127.0.0.1'); assert.notEqual(backend.port, '60086');
const names = ['WorkbenchFormat.js', 'WorkbenchReferences.jsx', 'ResourceControls.jsx', 'WorkbenchListControls.jsx', 'SystemRestoreStatus.js', 'SystemMaintenanceAPI.js', 'SystemMaintenanceControls.jsx', 'SystemRestorePanel.jsx',
  'SystemMaintenanceRecords.jsx', 'SystemMaintenanceConfig.jsx', 'SystemMaintenanceWorkspace.jsx'];
const report = { data_source: 'real-temporary-flask-api', scenario, cases: [], errors: [], external: [], requests: [], source_sha256: {} };
const order = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json')));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype', order.babel.path), check_combined: true,
  sources: names.map(name => {
    let code = fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8');
    report.source_sha256[name] = crypto.createHash('sha256').update(code).digest('hex');
    if (name === 'SystemMaintenanceConfig.jsx' && process.env.SYSTEM_CONFIG_SAVED_REPLAY_OLD_EFFECT === '1') {
      assert(code.includes('(!changed || matchesDraft)'));
      code = code.replace('(!changed || matchesDraft)', '!changed');
      report.replayed_old_effect = true;
    }
    return { path: name, code };
  }) });
report.compile = { target: compiled.target, global_build: false };
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, { mime: row.mime, data: fs.readFileSync(path.join(root, 'static', row.path)) }]));
const scripts = new Map(compiled.outputs.map(row => ['/probe/' + row.path, row.code]));
const boot = `
window.configSavedNetwork = { queue: [], held: {} };
function ConfigSavedProbe() {
  const [tab, setTab] = React.useState('config'), [source, setSource] = React.useState('current'), [revision, bump] = React.useReducer(v => v + 1, 0);
  const [theme, setTheme] = React.useState('light'), [pageSize, setSize] = React.useState(10), [compact, setCompact] = React.useState(true);
  const api = React.useMemo(() => {
    const live = window.SystemMaintenanceAPI.create();
    // This config-only fixture has no restore host; capability is an explicit UI stub.
    return {...live, host: async () => ({state:'ready',request_key:null,restart_required:false,automatic_resume:false,
      operations_available:true,result_source:'external_maintenance_journal',references:'reload_from_database_after_process_restart'}), read(kind, input, signal) {
      const tag = window.configSavedNetwork.queue.shift();
      if (!tag) return live.read(kind, input, signal);
      const held = {signal}; window.configSavedNetwork.held[tag] = held;
      // Deliberately ignore abort here: prove useRead rejects even a late, non-cancellable delivery.
      return live.read(kind, input).then(value => new Promise(resolve => {
        held.value = value; held.release = () => { held.released = true; resolve(value); };
      }));
    }};
  }, []);
  window.configSavedProbe = { bump, setTab, setSource };
  return React.createElement('div', {className: 'sm-workbench'},
    React.createElement('nav', null, ['config', 'overview'].map(value => React.createElement('button', {key: value, onClick: () => setTab(value)}, value))),
    React.createElement(window.SystemMaintenanceWorkspace, {api, tab, source, revision, theme, pageSize, compact,
      onSetTheme: setTheme, onPageSize: setSize, onCompact: setCompact}, React.createElement('p', null, 'overview')));
}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(ConfigSavedProbe));`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '<style>' + ['00-tokens.css', '21-table-frame.css', '22-shared-controls.css', '37-system.css'].map(name => fs.readFileSync(path.join(root, 'frontend/workbench/app/styles', name), 'utf8')).join('\n') + '</style></head><body class="aps-workbench"><div id="root"></div>' + manifest.scripts.filter(file => !file.endsWith('/main.js')).map(file => '<script src="/static/' + file + '"></script>').join('') + compiled.outputs.map(row => '<script src="/probe/' + row.path + '"></script>').join('') + '<script>' + boot + '</script></body></html>';
const server = http.createServer(async (request, response) => {
  const url = new URL(request.url, 'http://localhost');
  if (url.pathname === '/') { response.setHeader('Content-Type', 'text/html;charset=utf-8'); return response.end(html); }
  if (url.pathname === '/favicon.ico') { response.writeHead(204); return response.end(); }
  if (scripts.has(url.pathname)) { response.setHeader('Content-Type', 'text/javascript'); return response.end(scripts.get(url.pathname)); }
  if (assets.has(url.pathname)) { const row = assets.get(url.pathname); response.setHeader('Content-Type', row.mime); return response.end(row.data); }
  if (!url.pathname.startsWith('/api/workbench/v1/system/')) { response.writeHead(404); return response.end(); }
  const chunks = []; for await (const chunk of request) chunks.push(chunk);
  const body = Buffer.concat(chunks), input = body.length ? JSON.parse(body) : null;
  const record = { method: request.method, path: url.pathname, input: input && input.input, request_key: input && input.request_key };
  report.requests.push(record);
  const upstream = http.request(new URL(request.url, backend), { method: request.method, headers: { 'Content-Type': 'application/json' } }, reply => {
    const bytes = []; reply.on('data', chunk => bytes.push(chunk)); reply.on('end', () => {
      const data = Buffer.concat(bytes); record.status = reply.statusCode;
      const payload = JSON.parse(data);
      if (url.pathname.endsWith('/config')) record.read_values = payload.data && payload.data.values;
      if (url.pathname.endsWith('/config/save')) record.result = payload.result;
      response.writeHead(reply.statusCode, { 'Content-Type': 'application/json' }); response.end(data);
    });
  });
  upstream.on('error', error => { report.errors.push(error.message); response.writeHead(502); response.end('{}'); });
  upstream.end(body);
});
const save = page => page.getByRole('button', { name: /^保存维护配置/ });
const interval = page => page.getByLabel('备份检查间隔', { exact: true });
const passed = name => report.cases.push({ name, passed: true });
async function ready(page) { await page.waitForFunction(() => { const node = document.querySelector('#sm-maintenance-auto_backup_interval_minutes'); return node && !node.disabled; }); }
async function settled(page) { await page.waitForFunction(() => { const section = document.querySelector('.sm-maintenance-config'); return section && !section.textContent.includes('正在读取八项维护配置'); }); }
async function clean(page, expected) {
  await page.waitForFunction(value => { const section = document.querySelector('.sm-maintenance-config'); return section && !section.textContent.includes('有未保存修改') && !section.textContent.includes('当前草稿尚未覆盖') && section.textContent.includes('已存值：' + value); }, expected);
  assert.equal(await interval(page).inputValue(), String(expected));
  assert(await page.getByRole('button', { name: '放弃草稿', exact: true }).isDisabled());
}
async function acknowledge(page) { await page.getByRole('button', { name: '确认结果', exact: true }).click(); await page.getByRole('region', { name: '维护原请求结果' }).waitFor({ state: 'detached' }); }
const flush = page => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
const pending = page => page.evaluate(() => JSON.parse(localStorage.getItem(window.SystemMaintenanceAPI.PENDING_KEY)));
const read = page => page.evaluate(() => window.SystemMaintenanceAPI.create().read('config', {}));
async function externalSave(page, changes) {
  return page.evaluate(async changes => {
    const A = window.SystemMaintenanceAPI, api = A.create(), snapshot = await api.read('config', {});
    const bytes = crypto.getRandomValues(new Uint8Array(24));
    const intent = { action: 'config', summary: A.actions.config, request_key: 'system-' + Array.from(bytes, n => n.toString(16).padStart(2, '0')).join('') };
    const result = await api.command(intent, snapshot.data.write_context.write_token, {...snapshot.data.values, ...changes});
    return { values: result.command.data.config.values, result: result.command.result };
  }, changes);
}
async function revision(page) { await page.evaluate(() => window.configSavedProbe.bump()); await flush(page); await settled(page); }
async function conflict(page, value) {
  await page.getByRole('button', { name: '核对后沿用草稿', exact: true }).waitFor();
  assert.equal(await interval(page).inputValue(), String(value)); assert(await save(page).isDisabled());
  await page.getByText('有未保存修改', { exact: true }).waitFor();
}
async function hold(page, tag) { await page.evaluate(tag => window.configSavedNetwork.queue.push(tag), tag); }
async function held(page, tag) { await page.waitForFunction(tag => !!window.configSavedNetwork.held[tag]?.value, tag); }
async function release(page, tag) { await page.evaluate(tag => window.configSavedNetwork.held[tag].release(), tag); await flush(page); }
async function resetPage(page) { await externalSave(page, {auto_backup_interval_minutes: 120}); await page.reload(); await ready(page); }
const helpers = { assert, report, output, save, interval, ready, settled, clean, passed, acknowledge, flush, pending, read, externalSave, revision, conflict, hold, held, release, resetPage };
async function minimal(page) {
  await ready(page); assert.equal(await interval(page).inputValue(), '120');
  await interval(page).fill('121'); await page.getByText('有未保存修改', { exact: true }).waitFor();
  await save(page).click(); await page.getByText('八项维护配置已保存，事务和审计已留存。').waitFor();
  assert(await save(page).isDisabled()); assert(await interval(page).isDisabled());
  passed('200-receipt-does-not-unlock-before-acknowledgement');
  await acknowledge(page); await flush(page); await settled(page); await flush(page);
  report.confirmed_readback = await page.evaluate(() => ({
    draft: document.querySelector('#sm-maintenance-auto_backup_interval_minutes').value,
    stored: Array.from(document.querySelectorAll('.sm-config-row')).find(row => row.querySelector('label').textContent === '备份检查间隔').textContent,
    footer: document.querySelector('.sm-form-footer > .sm-meta').textContent
  }));
  assert.equal(report.confirmed_readback.footer, '当前值已读取', JSON.stringify(report.confirmed_readback));
  await ready(page); await clean(page, 121);
  assert(report.requests.some(row => row.method === 'GET' && row.read_values && row.read_values.auto_backup_interval_minutes === 121));
  passed('120-to-121-confirmed-readback-becomes-clean-baseline');
  await page.getByRole('button', { name: '重新读取配置', exact: true }).click(); await ready(page);
  assert.equal(await page.getByRole('dialog').count(), 0); await clean(page, 121);
  passed('refresh-after-save-does-not-ask-to-discard');
  assert.equal(report.requests.filter(row => row.method === 'POST').length, 1);
  await page.screenshot({ path: path.join(output, 'system_config_saved_121.png'), fullPage: true });
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    const context = await browser.newContext({ viewport: { width: 1392, height: 924 } });
    const page = await context.newPage(), origin = 'http://127.0.0.1:' + server.address().port;
    page.setDefaultTimeout(10000); page.on('pageerror', error => report.errors.push(error.message));
    await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
    await page.goto(origin);
    if (scenario === 'minimal') await minimal(page);
    else if (scenario === 'races') await require('./system_config_saved_races.cjs')(page, helpers);
    else await require('./system_config_saved_states.cjs')[scenario](page, helpers);
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []); await context.close();
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(output, 'system_config_saved_result.json'), JSON.stringify(report, null, 2));
  }
  console.log(JSON.stringify({ output, cases: report.cases.length, browser: report.browser }));
})().catch(error => { console.error(error); process.exitCode = 1; });
