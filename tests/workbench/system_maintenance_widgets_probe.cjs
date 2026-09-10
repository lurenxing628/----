/* Component-only in-memory Babel; no project build or normal backend is started. */
'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), assert = require('node:assert/strict');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], fixture = JSON.parse(fs.readFileSync(0, 'utf8'));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const order = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json')));
const names = ['SystemRestoreStatus.js', 'SystemMaintenanceAPI.js', 'SystemMaintenanceControls.jsx', 'SystemRestorePanel.jsx', 'SystemMaintenanceRecords.jsx', 'SystemMaintenanceConfig.jsx', 'SystemMaintenanceWorkspace.jsx'];
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype', order.babel.path), check_combined: true,
  sources: names.map(name => ({ path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') })) }).outputs;
const scripts = new Map(compiled.map(row => ['/probe/' + row.path, row.code]));
const report = { data_source: 'mock-with-temporary-backend-dto', production_persistence_tested: false, cases: [], variants: [], screenshots: [], requests: [], errors: [], external: [], dialogs: [] };
const clone = value => JSON.parse(JSON.stringify(value));
let mode, resultMode, downloadMode, receipts, config, failRead, host;
function reset() { mode = 'default'; resultMode = 'normal'; downloadMode = 'normal'; receipts = new Map(); config = clone(fixture.config); failRead = false;
  host = {state:'ready',request_key:null,restart_required:false,automatic_resume:false,operations_available:true,result_source:'external_maintenance_journal',references:'reload_from_database_after_process_restart'}; }
reset();
const boot = `
function ProbeApp(){const [tab,setTab]=React.useState('backups'),[source,setSource]=React.useState('current'),[size,setSize]=React.useState(10),[compact,setCompact]=React.useState(true),[theme,setTheme]=React.useState(document.documentElement.dataset.theme);
const tabs=[['overview','概况'],['backups','备份恢复'],['logs','运行日志'],['config','配置']];
const setColor=value=>{window.APSWorkbenchTheme.set(value);setTheme(value);};
return React.createElement(AppShell,{active:'system',title:'系统管理组件夹具（mock）',theme,showCapsule:false},
React.createElement('div',{className:'sm-workbench'+(compact?' sm-compact':''),'data-source':source},
React.createElement('header',{className:'sm-header'},React.createElement('div',null,React.createElement('h2',null,'系统管理'),React.createElement('p',null,'临时后端 DTO · 独立 mock 界面'))),
React.createElement('div',{className:'sm-source-bar'},['current','sample'].map(value=>React.createElement('label',{className:'sm-inline-label',key:value},React.createElement('input',{type:'radio',name:'source',checked:source===value,onChange:()=>setSource(value)}),value==='current'?'本机数据':'管理样例'))),
React.createElement('div',{className:'sm-tabs',role:'tablist'},tabs.map(([key,label])=>React.createElement('button',{type:'button',key,className:'sm-tab'+(tab===key?' sm-active':''),role:'tab','aria-selected':tab===key,onClick:()=>setTab(key)},label))),
React.createElement('div',{className:'sm-tab-panel'},React.createElement(window.SystemMaintenanceWorkspace,{tab,source,theme,onSetTheme:setColor,pageSize:size,onPageSize:setSize,compact,onCompact:setCompact,onReadSuspendedChange:value=>{window.systemReadSuspended=value;}},React.createElement('p',null,source==='sample'?'独立管理样例，不写本机数据。':'概况由 SystemLive 保留。')))),
React.createElement(window.WorkbenchControlStyles),React.createElement(window.WorkbenchControls),React.createElement(window.WorkbenchNumberControls));}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(ProbeApp));`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '</head><body class="aps-workbench"><div id="root"></div>' + manifest.scripts.filter(file => !file.endsWith('/main.js') && !names.some(name => file.endsWith('/' + name.replace(/jsx$/, 'js')))).map(file => '<script src="/static/' + file + '"></script>').join('') +
  compiled.map(row => '<script src="/probe/' + row.path + '"></script>').join('') + '<script>' + boot + '</script></body></html>';
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, row]));
function readCollection(kind, query) {
  const payload = clone(kind === 'logs' ? fixture.logs : mode === 'disabled' ? fixture.disabled : fixture.backups);
  if (kind === 'backups' && mode === 'enabled') payload.data.capabilities = clone(fixture.enabled.data.capabilities);
  let rows = kind === 'logs' ? fixture.log_pages.flatMap(page => page.data.rows) : payload.data.rows;
  rows = rows.filter(row => ['type', 'status', 'level', 'file'].every(key => !query[key] || query[key] === row[key]));
  if (query.query) rows = rows.filter(row => [row.summary, row.body, row.filename, row.file].join(' ').toLowerCase().includes(query.query.toLowerCase()));
  if (query.start) rows = rows.filter(row => row.time && row.time.slice(0, 10) >= query.start);
  if (query.end) rows = rows.filter(row => row.time && row.time.slice(0, 10) <= query.end);
  const size = Number(query.page_size || 10), number = Number(query.page || 1);
  payload.data.rows = clone(rows.slice((number - 1) * size, number * size));
  payload.data.page = { number, size, total: rows.length, pages: Math.max(1, Math.ceil(rows.length / size)) };
  return payload;
}
const server = http.createServer(async (request, response) => {
  const url = new URL(request.url, 'http://localhost'), query = Object.fromEntries(url.searchParams);
  if (url.pathname === '/') { response.setHeader('Content-Type', 'text/html;charset=utf-8'); return response.end(html); }
  if (url.pathname === '/favicon.ico') { response.writeHead(204); return response.end(); }
  if (scripts.has(url.pathname)) { response.setHeader('Content-Type', 'text/javascript'); return response.end(scripts.get(url.pathname)); }
  if (assets.has(url.pathname)) { const asset = assets.get(url.pathname); response.setHeader('Content-Type', asset.mime); return response.end(fs.readFileSync(path.join(root, 'static', asset.path))); }
  if (!url.pathname.startsWith('/api/workbench/v1/system/')) { response.writeHead(404); return response.end(); }
  let body = null;
  if (request.method === 'POST') { const chunks = []; for await (const chunk of request) chunks.push(chunk); body = JSON.parse(Buffer.concat(chunks)); }
  report.requests.push({ path: url.pathname, query, method: request.method, request_key: body && body.request_key, input_fields: body && Object.keys(body.input) });
  response.setHeader('Content-Type', 'application/json');
  const send = value => response.end(JSON.stringify(value));
  const reject = (code, status, committed = false) => { response.statusCode = status; return send({ ok: false, committed, error: { code, message: '测试错误：' + code, fields: [] } }); };
  if (url.pathname.endsWith('/restore-host')) return send({ok:true,schema_version:1,data:{kind:'restore_host',host},warnings:[],meta:{source:'production',result_source:'external_maintenance_journal',request_ref:'a'.repeat(32),time_basis:'factory_local'}});
  if (failRead && !url.pathname.includes('/results/') && !url.pathname.includes('/jobs/')) { failRead = false; return reject('snapshot_stale', 409); }
  if (url.pathname.includes('/logs/export/')) {
    if (downloadMode === 'json') return reject('snapshot_stale', 409);
    const format = url.pathname.split('/').pop();
    response.setHeader('Content-Type', downloadMode === 'mime' ? 'text/html' : format === 'csv' ? 'text/csv; charset=utf-8' : 'application/zip');
    if (downloadMode === 'disguised-json') return send({ ok: false, committed: false, error: { code: 'storage_failure', message: '错误 JSON 被标为文件' } });
    if (downloadMode === 'empty') return response.end();
    if (downloadMode === 'magic') return response.end(Buffer.from('not-a-log-file'));
    return response.end(Buffer.from(fixture.downloads[format], 'base64'));
  }
  if (url.pathname.includes('/results/') || url.pathname.includes('/jobs/')) {
    if (resultMode === 'not-found') return reject('entity_not_found', 404);
    if (resultMode === 'not-recorded') return send(fixture.not_recorded);
    let saved = receipts.get(url.pathname.split('/').pop());
    if (!saved) saved = Array.from(receipts.values()).find(value => value.data && value.data.operation && value.data.operation.job_ref === url.pathname.split('/').pop());
    return send(saved || fixture.not_recorded);
  }
  if (request.method === 'POST') {
    const action = url.pathname.endsWith('/config/save') ? 'config' : url.pathname.split('/').pop();
    if (resultMode === 'rejected') return reject('stale_write', 409);
    if (resultMode === 'unknown') return reject('storage_failure', 500, 'unknown');
    let value;
    if (action === 'config') {
      value = clone(resultMode === 'unchanged' ? fixture.unchanged : fixture.save);
      value.data.config.values = body.input;
      config = clone(fixture.saved_config); config.data.values = body.input;
      const lookup = clone(fixture.config_result); lookup.data.command = value; receipts.set(body.request_key, lookup);
    } else {
      value = clone(fixture[action]); value.data.operation.request_key = body.request_key;
      if (action === 'restore') { host = {...host,state:'restart_required',restart_required:true,operations_available:false,request_key:body.request_key}; value.data.host = clone(host); }
      if (['checking', 'rollback_failed', 'recovery_required', 'rolled_back', 'failed'].includes(resultMode)) {
        value.data.operation.state = resultMode; value.data.operation.code = resultMode; value.data.operation.message = 'fixture ' + resultMode;
        value.data.operation.terminal = ['rolled_back', 'failed'].includes(resultMode);
      }
      receipts.set(body.request_key, value);
    }
    if (resultMode === 'disconnect') { response.destroy(); return; }
    if (resultMode === 'wrong-kind') return send(action === 'config' ? fixture.create : fixture.save);
    return send(value);
  }
  return send(url.pathname.endsWith('/config') ? config : readCollection(url.pathname.split('/').pop(), query));
});
function passed(name, variant) { report.cases.push({ name, variant, passed: true }); }
async function shot(page, name) { const file = path.join(output, name + '.png'); await page.screenshot({ path: file, animations: 'disabled' }); report.screenshots.push(file); }
async function acknowledge(page) { await page.getByRole('button', { name: '确认结果', exact: true }).click(); await page.getByRole('region', { name: '维护原请求结果' }).waitFor({ state: 'detached' }); }
async function createBackup(page) { await page.getByRole('button', { name: '创建备份', exact: true }).click(); await page.getByRole('dialog').getByRole('button', { name: '确认创建', exact: true }).click(); }
async function newPage(browser, viewport, theme, intent) {
  const context = await browser.newContext({ viewport, acceptDownloads: true });
  await context.addInitScript(({ theme, intent }) => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); if (intent && !sessionStorage.getItem('seeded')) { localStorage.setItem('aps_workbench_system_pending_v1', JSON.stringify(intent)); sessionStorage.setItem('seeded', 'yes'); } }, { theme, intent });
  const page = await context.newPage(), origin = 'http://127.0.0.1:' + server.address().port;
  page.on('pageerror', error => report.errors.push(error.message)); page.on('dialog', async dialog => { report.dialogs.push(dialog.message()); await dialog.dismiss(); });
  await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
  await page.goto(origin); return { page, context, origin };
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    for (const viewport of [{ width: 1920, height: 1080 }, { width: 1392, height: 924 }]) for (const theme of ['light', 'dark']) {
      reset(); const variant = viewport.width + '-' + theme, { page, context } = await newPage(browser, viewport, theme);
      await page.locator('tbody tr').first().waitFor(); await shot(page, variant + '-backups');
      assert.equal(await page.getByRole('button', { name: '创建备份', exact: true }).isEnabled(), true);
      await page.locator('tbody tr').first().click(); const detail = page.getByRole('region', { name: '备份详情', exact: true });
      await detail.waitFor(); assert(await detail.getByRole('button', { name: /^恢复备份/ }).isDisabled());
      assert((await detail.textContent()).includes(fixture.backups.data.capabilities.restore_reason));
      await detail.scrollIntoViewIfNeeded(); await shot(page, variant + '-backup-detail'); await detail.press('Escape');
      await page.locator('tbody tr').first().press('Enter'); await detail.waitFor(); await detail.getByRole('button', { name: '关闭详情' }).click(); passed('whole-row-pointer-and-keyboard-default-restore-disabled', variant);
      await page.getByLabel('每页数量', { exact: true }).selectOption('10'); await page.getByRole('button', { name: '下一页', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('.sm-pager')?.textContent.includes('2 / 2'));
      await page.getByRole('button', { name: '上一页', exact: true }).click();
      await page.getByRole('searchbox', { name: '搜索维护记录' }).fill('fixture_01'); await page.getByRole('button', { name: '查询', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('.sm-pager')?.textContent.includes('共 1 条'));
      await page.getByRole('button', { name: '清除筛选', exact: true }).click(); await page.waitForFunction(total => document.querySelector('.sm-pager')?.textContent.includes('共 ' + total + ' 条'), fixture.backups.data.page.total); passed('server-pagination-and-query', variant);
      mode = 'disabled'; await page.getByRole('button', { name: '重新读取清单' }).click(); await page.getByText('文件动作禁用：' + fixture.disabled.data.capabilities.blocked_reason, { exact: true }).waitFor();
      assert(await page.getByRole('button', { name: /^创建备份/ }).isDisabled()); await shot(page, variant + '-journal-disabled'); passed('missing-journal-disables-file-actions', variant);
      await page.locator('tbody tr').first().click(); assert(await detail.getByRole('button', { name: /^删除备份/ }).isDisabled()); assert(await detail.getByRole('button', { name: /^恢复备份/ }).isDisabled());
      await detail.getByRole('button', { name: '关闭详情' }).click();
      await page.getByRole('tab', { name: '运行日志' }).click(); await page.getByLabel('日志来源').selectOption('aps.log'); await page.getByRole('button', { name: '查询', exact: true }).click();
      await page.getByRole('region', { name: '运行日志与操作记录' }).locator('tbody tr').first().waitFor();
      assert((await page.getByLabel('日志读取窗口').textContent()).includes('窗口已截断'));
      assert((await page.getByLabel('日志读取窗口').textContent()).includes('来源读取失败'));
      assert((await page.getByLabel('日志读取窗口').textContent()).includes('来源不存在'));
      await shot(page, variant + '-logs'); await page.locator('div:not([hidden]) > section[aria-label="运行日志与操作记录"] tbody tr').first().click();
      const logDetail = page.getByRole('region', { name: '日志详情', exact: true }); await logDetail.getByText('本条详情已截断，不是完整原始内容。').waitFor();
      await logDetail.scrollIntoViewIfNeeded(); await shot(page, variant + '-log-detail'); await logDetail.getByRole('button', { name: '关闭详情' }).click();
      await page.getByRole('tab', { name: '配置', exact: true }).click(); await page.getByLabel('备份检查间隔', { exact: true }).waitFor();
      await page.getByRole('tab', { name: '运行日志', exact: true }).click(); assert.equal(await page.getByLabel('日志来源').inputValue(), 'aps.log'); passed('bounded-truncated-missing-error-and-source-filter-retained', variant);
      await page.getByLabel('管理样例', { exact: true }).check(); const sampleStart = report.requests.length;
      await page.getByText('独立管理样例，不写本机数据。', { exact: true }).waitFor(); assert.equal(await page.getByRole('button', { name: '导出窗口 CSV' }).count(), 0);
      await page.getByLabel('本机数据', { exact: true }).check(); await page.getByRole('region', { name: '运行日志与操作记录' }).locator('tbody tr').first().waitFor();
      assert.equal(await page.getByLabel('日志来源').inputValue(), 'aps.log'); assert(report.requests.slice(sampleStart).every(row => row.method === 'GET')); passed('sample-mode-no-business-write-and-filter-retained', variant);
      await page.getByRole('region', { name: '运行日志与操作记录' }).locator('tbody tr').first().waitFor();
      for (const format of ['csv', 'zip']) {
        const wait = page.waitForEvent('download'); await page.getByRole('button', { name: format === 'csv' ? '导出窗口 CSV' : '脱敏诊断 ZIP' }).click();
        const download = await wait, file = path.join(output, variant + '.' + format); await download.saveAs(file);
        assert.deepEqual(fs.readFileSync(file), Buffer.from(fixture.downloads[format], 'base64'));
      }
      passed('blob-mime-magic-and-exact-window-downloads', variant);
      for (const bad of ['json', 'disguised-json', 'mime', 'empty', 'magic']) {
        downloadMode = bad; let downloaded = false; const handler = () => { downloaded = true; }; page.on('download', handler);
        await page.getByRole('button', { name: '导出窗口 CSV' }).click(); await page.getByRole('alert').waitFor();
        await page.waitForFunction(() => !document.querySelector('button[aria-busy="true"]')); assert.equal(downloaded, false); page.off('download', handler); passed('reject-download-' + bad, variant);
      }
      downloadMode = 'normal'; failRead = true; await page.getByRole('button', { name: '下一页', exact: true }).click(); await page.getByRole('alert').waitFor();
      assert(await page.getByRole('button', { name: '导出窗口 CSV' }).isDisabled()); await page.getByRole('button', { name: '重新读取清单' }).click();
      await page.getByRole('region', { name: '运行日志与操作记录' }).locator('tbody tr').first().waitFor(); passed('stale-page-explicit-refresh', variant);
      await page.getByLabel('日志来源').selectOption('OperationLogs'); await page.getByRole('region', { name: '运行日志与操作记录' }).getByLabel('记录类型').selectOption('operation'); await page.getByRole('button', { name: '查询', exact: true }).click();
      await page.waitForFunction(() => Array.from(document.querySelectorAll('.sm-pager')).some(node => node.getClientRects().length && node.textContent.includes('共 500 条')));
      await shot(page, variant + '-operation-logs'); passed('operation-log-source-and-window', variant);
      await page.getByRole('tab', { name: '配置', exact: true }).click(); await page.getByLabel('备份检查间隔', { exact: true }).waitFor();
      assert((await page.getByRole('heading', { name: '本机自动维护配置' }).locator('..').locator('..').textContent()).includes('旧配置异常'));
      const beforePreferences = report.requests.filter(row => row.method === 'POST').length;
      await page.getByLabel(theme === 'light' ? '深色' : '浅色', { exact: true }).check(); await page.getByLabel('紧凑行距', { exact: true }).uncheck();
      assert.equal(report.requests.filter(row => row.method === 'POST').length, beforePreferences);
      await page.getByLabel(theme === 'light' ? '浅色' : '深色', { exact: true }).check(); await page.getByLabel('紧凑行距', { exact: true }).check();
      await page.getByLabel('备份检查间隔', { exact: true }).fill('0'); await page.getByRole('button', { name: '保存维护配置', exact: true }).click();
      await page.getByText('配置校验未通过，请修正标出的字段。').waitFor(); assert.equal(report.requests.filter(row => row.method === 'POST').length, beforePreferences);
      await page.getByLabel('备份检查间隔', { exact: true }).fill('37'); await shot(page, variant + '-config');
      await page.getByRole('button', { name: '放弃草稿', exact: true }).click(); await page.getByRole('dialog').press('Escape');
      assert.equal(await page.getByLabel('备份检查间隔', { exact: true }).inputValue(), '37'); passed('draft-discard-modal-cancel', variant);
      await page.getByRole('tab', { name: '运行日志', exact: true }).click(); await page.getByRole('tab', { name: '配置', exact: true }).click();
      await page.getByRole('button', { name: '核对后沿用草稿' }).waitFor(); assert.equal(await page.getByLabel('备份检查间隔', { exact: true }).inputValue(), '37');
      await page.getByRole('button', { name: '核对后沿用草稿' }).click(); passed('config-draft-retained-with-explicit-rebase', variant);
      await page.getByRole('button', { name: '保存维护配置', exact: true }).click(); await page.getByText('八项维护配置已保存，事务和审计已留存。').waitFor();
      const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('aps_workbench_system_pending_v1')));
      assert.deepEqual(Object.keys(stored).sort(), ['action', 'request_key', 'summary']); assert.equal(stored.action, 'config');
      assert(!JSON.stringify(stored).includes('write_token')); assert(!JSON.stringify(stored).includes('/'));
      const postCount = report.requests.filter(row => row.method === 'POST').length; await page.reload();
      await page.getByText('八项维护配置已保存，事务和审计已留存。').waitFor(); assert.equal(report.requests.filter(row => row.method === 'POST').length, postCount);
      await shot(page, variant + '-config-receipt'); await acknowledge(page); passed('config-save-eight-fields-private-pending-reload-get-only', variant);
      assert(report.requests.filter(row => row.path.endsWith('/config/save')).every(row => row.input_fields.length === 8 && row.input_fields.every(key => key.startsWith('auto_'))));
      const geometry = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth, theme: document.documentElement.dataset.theme,
        sections: Array.from(document.querySelectorAll('.sm-section')).filter(node => node.getClientRects().length).map(node => ({ shadow: getComputedStyle(node).boxShadow, font: getComputedStyle(node).fontSize })),
        overflow: Array.from(document.querySelectorAll('.sm-maintenance-workspace button,.sm-maintenance-workspace input,.sm-maintenance-workspace select')).filter(node => node.getClientRects().length).map(node => { const r = node.getBoundingClientRect(); return { width: r.width, height: r.height, right: r.right }; }) }));
      assert(geometry.scroll <= viewport.width + 1); assert(geometry.sections.every(row => row.shadow === 'none')); assert(geometry.overflow.every(row => row.right <= viewport.width + 1 && row.width > 0));
      report.variants.push({ viewport, theme, geometry }); await context.close();
    }
    // Contract mutations are exercised against actual captured DTOs, not hand-invented response schemas.
    reset(); let test = await newPage(browser, { width: 1392, height: 924 }, 'light');
    const contract = await test.page.evaluate(dto => {
      const A = window.SystemMaintenanceAPI, checks = [];
      const fails = (name, fn) => { let rejected = false; try { fn(); } catch (_) { rejected = true; } if (!rejected) throw new Error(name); checks.push(name); };
      A.collection(dto.backups, 'backups'); A.collection(dto.logs, 'logs'); A.config(dto.config.data); A.receipt(dto.save); A.receipt(dto.unchanged);
      A.result(dto.restore, { action: 'restore', request_key: dto.restore.data.operation.request_key });
      let bad = JSON.parse(JSON.stringify(dto.backups)); delete bad.data.capabilities; fails('missing-capabilities', () => A.collection(bad, 'backups'));
      bad = JSON.parse(JSON.stringify(dto.logs)); bad.meta.source = 'sample'; fails('sample-as-production', () => A.collection(bad, 'logs'));
      fails('file-result-not-config-receipt', () => A.receipt(dto.restore));
      fails('wrong-result-key', () => A.result(dto.restore, { action: 'restore', request_key: 'wrong' }));
      fails('wrong-result-action', () => A.result(dto.restore, { action: 'delete', request_key: dto.restore.data.operation.request_key }));
      bad = JSON.parse(JSON.stringify(dto.restore)); bad.data.operation.state = 'rollback_failed'; fails('false-terminal', () => A.result(bad, { action: 'restore', request_key: bad.data.operation.request_key }));
      const memory = new Map(), store = { getItem: key => memory.has(key) ? memory.get(key) : null, setItem: (key, value) => memory.set(key, value), removeItem: key => memory.delete(key) };
      const pending = A.pending(store), intent = pending.begin('create'); fails('no-second-pending-key', () => pending.begin('delete')); pending.finish(intent);
      store.setItem(A.PENDING_KEY, '{bad'); fails('corrupt-storage-fail-closed', () => pending.read());
      store.setItem(A.PENDING_KEY, JSON.stringify({ ...intent, write_token: 'must-not-store' })); fails('reject-sensitive-pending-fields', () => pending.read());
      fails('storage-write-failure', () => A.pending({ ...store, getItem: () => null, setItem: () => { throw new Error('quota'); } }).begin('create'));
      if (A.normalize({ ...dto.config.data.values, auto_backup_keep_days: 366 }).valid) throw new Error('range validation');
      return checks;
    }, fixture);
    contract.forEach(name => passed(name, 'contract')); await test.context.close();
    test = await newPage(browser, { width: 1392, height: 924 }, 'light'); await test.page.locator('tbody tr').first().waitFor();
    await test.page.evaluate(async () => {
      const timer = window.setTimeout, A = window.SystemMaintenanceAPI, intent = { action: 'create', summary: '创建备份', request_key: 'system-' + '6'.repeat(48) };
      window.setTimeout = (fn, delay) => timer(fn, delay === 30000 ? 5 : delay);
      try {
        const api = A.create((url, options) => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))));
        let rejected = false; try { await api.command(intent, 'fixture-only-token', {}); } catch (error) { rejected = error.message.includes('超时') && !error.rejected; }
        if (!rejected) throw new Error('Timeout must stay uncertain, not rejected/committed');
      } finally { window.setTimeout = timer; }
    }); passed('bounded-timeout-remains-uncertain', 'contract'); await test.context.close();
    for (const scenario of ['normal', 'disconnect', 'not-recorded', 'not-found', 'wrong-kind', 'unknown', 'rejected', 'checking', 'rollback_failed', 'recovery_required', 'rolled_back', 'failed']) {
      reset(); resultMode = scenario; test = await newPage(browser, { width: 1392, height: 924 }, 'dark');
      await test.page.locator('tbody tr').first().waitFor(); await createBackup(test.page);
      await test.page.getByRole('region', { name: '维护原请求结果' }).waitFor();
      await test.page.waitForFunction(() => !document.querySelector('button[aria-busy="true"]'));
      const post = report.requests.filter(row => row.method === 'POST').at(-1), pending = await test.page.evaluate(() => JSON.parse(localStorage.getItem('aps_workbench_system_pending_v1')));
      assert.equal(post.request_key, pending.request_key);
      if (['normal', 'rolled_back', 'failed', 'rejected'].includes(scenario)) { await acknowledge(test.page); }
      else {
        if (['not-recorded', 'not-found'].includes(scenario)) { await test.page.reload(); }
        else await test.page.getByRole('button', { name: '核实原请求' }).click();
        await test.page.waitForFunction(() => !document.querySelector('button[aria-busy="true"]'));
        if (scenario === 'disconnect' || scenario === 'wrong-kind') await acknowledge(test.page);
        else {
          assert.equal(await test.page.getByRole('button', { name: '确认结果', exact: true }).count(), 0);
          assert(await test.page.getByRole('button', { name: /^创建备份/ }).isDisabled());
          const count = report.requests.filter(row => row.method === 'POST').length; await test.page.reload();
          await test.page.getByRole('region', { name: '维护原请求结果' }).waitFor(); await test.page.waitForFunction(() => !document.querySelector('button[aria-busy="true"]'));
          assert.equal(report.requests.filter(row => row.method === 'POST').length, count);
          assert.equal(await test.page.evaluate(() => JSON.parse(localStorage.getItem('aps_workbench_system_pending_v1')).request_key), pending.request_key);
          await shot(test.page, 'recovery-' + scenario);
        }
      }
      passed('original-key-result-' + scenario, 'recovery'); await test.context.close();
    }
    // Enabled restore and single-delete require the product modal, and remain mock browser actions.
    reset(); mode = 'enabled'; test = await newPage(browser, { width: 1392, height: 924 }, 'light');
    for (const action of ['delete', 'restore']) {
      await test.page.locator('tbody tr').first().waitFor(); await test.page.locator('tbody tr').first().click();
      await test.page.getByRole('button', { name: action === 'restore' ? '恢复备份' : '删除备份', exact: true }).click();
      const dialog = test.page.getByRole('dialog'), submit = dialog.getByRole('button', { name: action === 'restore' ? '确认恢复' : '确认删除', exact: true });
      assert(await submit.isDisabled()); await dialog.getByRole('checkbox').check();
      if (action === 'restore') { assert(await submit.isDisabled()); await dialog.getByRole('textbox').fill('恢复'); }
      await shot(test.page, action + '-confirmation'); await submit.click();
      if(action === 'delete') await test.page.getByRole('button', { name: '确认结果', exact: true }).waitFor();
      else await test.page.getByText('维护已结束，请重启整个软件', {exact:true}).waitFor();
      assert.equal(report.requests.filter(row => row.method === 'POST').at(-1).input_fields.join(','), 'backup_ref');
      if(action === 'delete') await acknowledge(test.page);
      else assert.equal(await test.page.getByRole('button', {name:'确认结果',exact:true}).count(),0);
      passed('enabled-' + action + '-confirmation', 'actions');
    }
    await test.context.close();
    reset(); resultMode = 'unchanged'; test = await newPage(browser, { width: 1392, height: 924 }, 'light');
    await test.page.getByRole('tab', { name: '配置', exact: true }).click(); await test.page.getByRole('button', { name: '保存维护配置', exact: true }).click();
    await test.page.getByText('配置没有变化，已留存无变更回执；未新增业务审计。').waitFor(); await acknowledge(test.page); passed('ordinary-unchanged-receipt', 'actions'); await test.context.close();
    reset(); const original = { request_key: 'system-' + '7'.repeat(48), action: 'restore', summary: '恢复所选备份' }, recovering = clone(fixture.restore);
    host = {...host,state:'restoring',restart_required:true,operations_available:false,request_key:original.request_key};
    Object.assign(recovering.data.operation, { request_key: original.request_key, state: 'restoring', terminal: false, code: 'restoring', database_origin:'unconfirmed', message: 'mock 恢复进行中' }); receipts.set(original.request_key, recovering);
    const readStart = report.requests.length; test = await newPage(browser, { width: 1392, height: 924 }, 'dark', original);
    await test.page.getByText('mock 恢复进行中', { exact: false }).waitFor();
    assert(await test.page.evaluate(() => document.getElementById('root').inert));
    await test.page.getByRole('button', { name: '核实原请求' }).click(); await test.page.waitForFunction(() => !document.querySelector('button[aria-busy="true"]'));
    assert(report.requests.slice(readStart).every(row => row.method === 'GET' && (/\/(results|jobs)\//.test(row.path) || row.path.endsWith('/restore-host'))));
    assert(report.requests.slice(readStart).some(row => row.path.includes('/jobs/')));
    await test.page.reload(); await test.page.getByText('mock 恢复进行中', { exact: false }).waitFor();
    assert(report.requests.slice(readStart).every(row => row.method === 'GET' && (/\/(results|jobs)\//.test(row.path) || row.path.endsWith('/restore-host'))));
    assert.equal(await test.page.evaluate(() => window.systemReadSuspended), true);
    await shot(test.page, 'restore-pending-get-only'); passed('restore-pending-suspends-database-reads-jobs-and-results-only', 'recovery');
    Object.assign(recovering.data.operation, { state: 'succeeded', terminal: true, code: 'verified', database_origin:'selected_backup' });
    host = {...host,state:'restart_required'};
    await test.page.getByRole('button', { name: '核实原请求' }).click(); await test.page.getByText('维护已结束，请重启整个软件',{exact:true}).waitFor();
    assert.equal(await test.page.getByRole('button', { name: '确认结果', exact: true }).count(),0);
    assert.equal(await test.page.evaluate(() => window.systemReadSuspended), true); passed('host-read-suspension-persists-after-terminal-until-process-restart', 'recovery'); await test.context.close();
    reset(); const corruptStart = report.requests.length; test = await newPage(browser, { width: 1392, height: 924 }, 'light', { invalid: true });
    await test.page.getByRole('alert').waitFor(); assert.equal(await test.page.evaluate(() => window.systemReadSuspended), true);
    assert(report.requests.slice(corruptStart).every(row=>row.path.endsWith('/restore-host'))); assert.equal(await test.page.getByRole('button', { name: /^创建备份/ }).count(), 0);
    passed('corrupt-pending-ui-blocks-reads-and-writes', 'recovery'); await test.context.close();
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []); assert.deepEqual(report.dialogs, []);
  } finally { if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'system-maintenance-ui-result.json'), JSON.stringify(report, null, 2)); }
  console.log(JSON.stringify({ output, cases: report.cases.length, variants: report.variants.length, screenshots: report.screenshots.length }));
})().catch(error => { console.error(error); process.exitCode = 1; });
