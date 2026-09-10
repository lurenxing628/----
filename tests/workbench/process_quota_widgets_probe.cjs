/* DG: source-compiled components, real HTTP/SQLite, no fabricated quota locks. */
'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const config = JSON.parse(fs.readFileSync(0, 'utf8')), output = process.argv[2], root = path.resolve(__dirname, '../..');
const names = ['WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx', 'resource-api.js', 'resource-contract.js', 'resource-session.js', 'ResourceControls.jsx', 'ResourceTableFilterModel.js', 'ResourceTables.jsx',
  'ResourceDetailRelations.jsx', 'ResourceForms.jsx', 'ResourceMaterialContract.js', 'ResourceMaterialPreview.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchNumberControls.jsx',
  'ProcessContract.js', 'ProcessAPI.js', 'ProcessActionContract.js', 'ProcessActionPreview.jsx', 'ProcessFileContract.js', 'ProcessFilePreview.jsx', 'ProcessFileActions.jsx', 'ProcessControls.jsx',
  'ProcessStageEditor.jsx', 'ProcessSourceEditor.jsx', 'ProcessHoursEditor.jsx', 'ProcessRouteEntry.jsx', 'ProcessDetail.jsx',
  'CalibrationAPI.js', 'CalibrationControls.jsx', 'CalibrationAdoptionAPI.js', 'CalibrationAdoptionState.js', 'CalibrationAdoptionControls.jsx', 'CalibrationAdoptionAction.jsx', 'CalibrationDetail.jsx', 'CalibrationWorkspace.jsx'];
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const sources = names.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true }).outputs;
const scripts = new Map(compiled.map(row => ['/source/' + row.path, row.code]));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, { ...row, bytes: fs.readFileSync(path.join(root, 'static', row.path)) }]));
const record = { global_build: false, cases: [], screenshots: [], errors: [], external: [], responses: [], refreshes: 0, contract_rejections: 0,
  sources: sources.map(row => ({ path: row.path, sha256: hash(row.code) })) };
const boot = `const dgAdapter=APSProcessAPI.create();window.dgCompleted=[];
function Harness(){const [opened,setOpened]=React.useState(true);const mode=location.pathname;
return React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls),React.createElement(WorkbenchNumberControls),
  mode==='/calibration'?React.createElement(CalibrationWorkspace):opened?(mode==='/process'?React.createElement(ProcessDetail,{adapter:dgAdapter,partRef:${JSON.stringify(config.part_ref)},onClose:()=>setOpened(false),onCommitted:value=>dgCompleted.push(value)}):
  React.createElement(ProcessFileActions,{adapter:dgAdapter,kind:'hours',mode:'import',request:{source:'production',scope:{},recovery:!!dgAdapter.readPending()},onClose:()=>setOpened(false),onCommitted:value=>dgCompleted.push(value)})):
  React.createElement('button',{onClick:()=>setOpened(true)},'打开工时导入'));}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(Harness));`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '</head><body class="aps-workbench"><div id="root"></div>' + manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-')).map(file => '<script src="/static/' + file + '"></script>').join('') +
  [...scripts.keys()].map(file => '<script src="' + file + '"></script>').join('') + '<script>' + boot + '</script></body></html>';
let fault = false, blockReceipts = false, origin, browser;
const server = http.createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost');
  if (['/calibration', '/process', '/import'].includes(url.pathname)) { response.setHeader('Content-Type', 'text/html;charset=utf-8'); return response.end(html); }
  if (url.pathname === '/favicon.ico') { response.writeHead(204); return response.end(); }
  if (scripts.has(url.pathname)) { response.setHeader('Content-Type', 'text/javascript'); return response.end(scripts.get(url.pathname)); }
  if (assets.has(url.pathname)) { const asset = assets.get(url.pathname); response.setHeader('Content-Type', asset.mime); return response.end(asset.bytes); }
  if (url.pathname.startsWith('/api/')) {
    if (blockReceipts && url.pathname.includes('/commands/')) return response.destroy();
    const chunks = []; request.on('data', data => chunks.push(data)); request.on('end', () => {
      const body = Buffer.concat(chunks), headers = { cookie: request.headers.cookie || '' };
      if (body.length) { headers['Content-Type'] = request.headers['content-type']; headers['Content-Length'] = body.length; }
      const upstream = http.request(config.api_origin + request.url, { method: request.method, headers }, incoming => {
        const parts = []; incoming.on('data', data => parts.push(data)); incoming.on('end', () => {
          const bytes = Buffer.concat(parts), json = incoming.headers['content-type']?.includes('application/json');
          if (json) record.responses.push({ path: url.pathname, method: request.method,
            case: /(?:^|;\s*)dg_case=([^;]+)/.exec(headers.cookie)?.[1],
            input: headers['Content-Type']?.includes('application/json') ? JSON.parse(body.toString()) : null,
            payload: JSON.parse(bytes.toString()) });
          if (fault && url.pathname.endsWith('/hours/confirm')) return response.destroy();
          response.writeHead(incoming.statusCode, incoming.headers); response.end(bytes);
        });
      }); upstream.on('error', error => { record.errors.push(error.message); response.destroy(); }); upstream.end(body);
    }); return;
  }
  response.writeHead(404); response.end();
});
const button = (page, name) => page.getByRole('button', { name, exact: true });
async function shot(page, name, viewport) {
  const geometry = await page.evaluate(() => {
    const dialog = document.querySelector('.rm-actions [role=dialog]');
    const rect = node => { const r = node.getBoundingClientRect(); return { x: r.x, y: r.y, right: r.right, bottom: r.bottom }; };
    const shown = node => node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden';
    return { width: document.documentElement.scrollWidth, theme: document.documentElement.dataset.theme, dialog: rect(dialog),
      clipped: [...dialog.querySelectorAll('button,td,th,input,select')].filter(shown).filter(node => !['INPUT', 'SELECT'].includes(node.tagName) && node.scrollWidth > node.clientWidth + 2).map(node => node.textContent),
      footer: [...dialog.querySelectorAll('.modal-f button')].map(rect), text: dialog.innerText };
  });
  assert(geometry.width <= viewport.width && geometry.dialog.x >= 0 && geometry.dialog.y >= 0 && geometry.dialog.right <= viewport.width && geometry.dialog.bottom <= viewport.height);
  assert.deepEqual(geometry.clipped, []);
  geometry.footer.forEach((a, index) => geometry.footer.slice(index + 1).forEach(b => assert(!(a.x < b.right - 1 && a.right > b.x + 1 && a.y < b.bottom - 1 && a.bottom > b.y + 1))));
  const filename = path.join(output, name + '.png'); await page.screenshot({ path: filename, animations: 'disabled' });
  record.screenshots.push({ filename, geometry });
}
async function contextFor(name, viewport, theme) {
  const context = await browser.newContext({ viewport }); await context.addCookies([{ name: 'dg_case', value: name, url: origin }]);
  await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
  const page = await context.newPage(); page.setDefaultTimeout(12000); page.on('pageerror', error => record.errors.push(error.message));
  await context.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { record.external.push(route.request().url()); return route.abort(); } return route.continue(); });
  return { context, page };
}
async function adopt(page, reason) {
  await page.goto(origin + '/calibration'); await page.locator('.calibration-live[data-ready=true]').waitFor();
  await page.locator('.ca-table tr[data-ref="' + config.template_ref + '"] button').click();
  await page.locator('[data-sample-group=selected]').waitFor(); await button(page, '预览采用').click();
  const dialog = page.getByRole('dialog'); await dialog.getByLabel('采用原因', { exact: true }).fill(reason);
  await dialog.getByLabel('声明人', { exact: true }).fill('DG工时复核员'); await button(page, '读取真实预览').click();
  await dialog.getByText('当前预览可采用：来源、旧定额和合格样本已核对。', { exact: true }).waitFor();
  await dialog.getByRole('checkbox').check(); const saved = page.waitForResponse(response => response.url().endsWith('/adopt'));
  await button(page, '确认采用并锁定').click(); const receipt = await (await saved).json();
  assert.equal(receipt.result, 'committed'); assert.equal(receipt.data.new_unit_hours, 3); assert(receipt.data.locked);
  await dialog.getByText('已核实采用，新定额 3 h / 件，模板定额已锁定。', { exact: true }).waitFor();
  await button(page, '完成核实').click();
}
async function openImport(page, detail) {
  await page.goto(origin + (detail ? '/process' : '/import'));
  if (detail) { await page.getByRole('tab', { name: /工时定额/ }).click(); await button(page, '导入工时定额').click(); }
  await page.getByLabel('选择工时定额文件', { exact: true }).waitFor();
}
async function preview(page, filename) {
  const fmt = filename.split('.').pop(); await button(page, fmt === 'csv' ? 'CSV (.csv)' : 'Excel (.xlsx)').click();
  await page.getByLabel('选择工时定额文件', { exact: true }).setInputFiles({ name: filename,
    mimeType: fmt === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: Buffer.from(config.files[filename], 'base64') });
  const wait = page.waitForResponse(response => response.url().endsWith('/hours/preview')); await button(page, '开始预检').click();
  const response = await wait; assert.equal(response.status(), 200); const result = await response.json();
  await page.getByRole('region', { name: '工时导入预检', exact: true }).waitFor(); return result;
}
async function rowChecks(page, changed, skipped, unchanged, receipt = false) {
  const region = page.getByRole('region', { name: receipt ? '工时导入回执' : '工时导入预检', exact: true });
  await region.waitFor(); const summary = await region.locator('.rm-summary').innerText();
  assert(summary.includes((receipt ? '已导入' : '可导入') + ' ' + changed)); assert(summary.includes('锁定跳过 ' + skipped)); assert(summary.includes('原值相同 ' + unchanged));
  assert.equal(await region.locator('[data-quota-result=skipped]').count(), skipped);
  if (skipped) { assert((await region.innerText()).includes('单件工时已锁定')); assert((await region.innerText()).includes('本行全部跳过')); }
  assert(!(await region.innerText()).includes('全成功'));
}
async function contractChecks(page, preview, receipt, intent) {
  record.contract_rejections = await page.evaluate(({ preview, receipt, intent }) => {
    const F = APSProcessFiles, clone = value => JSON.parse(JSON.stringify(value)); let rejected = 0;
    const changes = [d => { delete d.skipped_count; }, d => { d.skipped_count++; }, d => { d.skipped_refs[0] = 'f'.repeat(48); },
      d => { d.skipped_rows[0].row = 999; }, d => { delete d.skipped_rows[0].reason; }, d => { d.skipped_rows[0].code = 'unknown'; },
      d => { d.rows[0].skip_reason.reason = 'different'; }, d => { d.rows[0].result = 'committed'; }, d => { d.rows[0].sequence = null; }];
    for (const mutate of changes) for (const mode of ['preview', 'receipt']) {
      const copy = clone(mode === 'preview' ? preview : receipt); mutate(copy.data);
      try { if (mode === 'preview') F.preview(copy, 'hours', copy.data.format, {}); else F.receipt(copy, intent, 'hours', preview.data); }
      catch (_) { rejected++; }
    }
    F.preview(preview, 'hours', preview.data.format, {}); F.receipt(receipt, intent, 'hours', preview.data);
    const changedReason = clone(receipt); changedReason.data.skipped_rows[0].reason = changedReason.data.rows[0].skip_reason.reason = 'another adoption';
    try { F.receipt(changedReason, intent, 'hours', preview.data); } catch (_) { rejected++; }
    return rejected;
  }, { preview, receipt, intent });
  assert.equal(record.contract_rejections, 19);
}
async function happy(layout, viewport, theme) {
  const name = layout + '-' + theme + '-' + viewport.width, reason = '核对五个整道完工样本后采纳单件工时：' + name;
  const { context, page } = await contextFor(name, viewport, theme); await adopt(page, reason); await openImport(page, layout === 'mixed');
  const data = await preview(page, layout + (theme === 'light' ? '.csv' : '.xlsx')); const changed = layout === 'mixed' ? 1 : 0;
  await rowChecks(page, changed, 1, 0); await page.getByLabel('查找图号或工序').fill('P1');
  await page.getByLabel('工时明细筛选', { exact: true }).selectOption('skipped');
  assert.equal(await page.locator('[data-quota-row]').count(), 1); assert((await page.locator('[data-quota-row]').innerText()).includes('工序 1'));
  await page.getByLabel('工时明细筛选', { exact: true }).selectOption('all'); await shot(page, name + '-preview', viewport);
  await page.locator('.rm-preview-toolbar').hover(); await page.mouse.wheel(0, 450);
  await shot(page, name + '-preview-details', viewport);
  const lose = name === 'mixed-dark-1392'; fault = lose; blockReceipts = lose;
  const wait = lose ? null : page.waitForResponse(response => response.url().endsWith('/hours/confirm'));
  await button(page, changed ? '确认导入' : '确认跳过并记录结果').click();
  let result;
  if (lose) { await button(page, '查询原请求回执').waitFor(); await shot(page, name + '-pending', viewport);
    result = record.responses.filter(row => row.path.endsWith('/hours/confirm')).slice(-1)[0].payload; }
  else { result = await (await wait).json(); await rowChecks(page, changed, 1, 0, true); await shot(page, name + '-receipt', viewport); }
  assert.equal(result.result, changed ? 'committed' : 'unchanged');
  assert.equal((await page.evaluate(() => window.dgCompleted)).length, 0, 'Receipt must stay visible until Finish');
  const stored = await page.evaluate(() => JSON.parse(sessionStorage.getItem('aps_workbench_resource_pending_v1_process')));
  assert(stored && stored.request_key); if (!record.contract_rejections) await contractChecks(page, data, result, stored);
  fault = false; blockReceipts = false;
  const lookup = page.waitForResponse(response => response.url().endsWith('/commands/' + stored.request_key));
  page.once('dialog', dialog => dialog.accept()); await page.reload(); const replay = await (await lookup).json();
  assert(replay.replayed); assert.deepEqual(replay.data, result.data); assert.equal(replay.receipt_ref, result.receipt_ref);
  await rowChecks(page, changed, 1, 0, true); await page.getByText('采纳原因：' + reason, { exact: true }).waitFor();
  await shot(page, name + '-refreshed-receipt', viewport); record.refreshes++; if (lose) record.lost_response_recovered = true;
  await button(page, '完成').click();
  if (layout === 'mixed') await page.getByText('服务器已确认提交，已重新读取工艺详情。', { exact: true }).waitFor();
  assert.equal(await page.evaluate(() => sessionStorage.getItem('aps_workbench_resource_pending_v1_process')), null);
  record.cases.push({ name, layout, viewport, theme, reason, request_key: stored.request_key, receipt: result }); await context.close();
}
async function boundaries() {
  const viewport = { width: 1392, height: 924 }; let { context, page } = await contextFor('setup', viewport, 'light');
  await adopt(page, '仅改单件以外的换型时间，不解除校准锁');
  for (const name of ['setup', 'setup_blank']) { await openImport(page, false); await preview(page, name + '.csv'); await rowChecks(page, 1, 0, 0);
    await button(page, '确认导入').click(); await rowChecks(page, 1, 0, 0, true); await shot(page, name + '-receipt', viewport); await button(page, '完成').click(); }
  record.setup_equal = record.setup_blank = true; await context.close();
  ({ context, page } = await contextFor('noop', viewport, 'dark')); await adopt(page, '锁定跳过和原值相同分别核对');
  await openImport(page, false); await preview(page, 'noop.xlsx'); await rowChecks(page, 0, 1, 1);
  await button(page, '确认导入').click(); await rowChecks(page, 0, 1, 1, true); await shot(page, 'noop-receipt', viewport); record.noop = true; await context.close();
  ({ context, page } = await contextFor('drift', viewport, 'light')); await openImport(page, false); const old = await preview(page, 'mixed.csv');
  assert.equal(old.data.skipped_count, 0); const other = await context.newPage(); await adopt(other, '预检之后真实采纳，旧预检必须拒绝'); await other.close();
  const wait = page.waitForResponse(response => response.url().endsWith('/hours/confirm')); await button(page, '确认导入').click();
  const failed = await wait; assert.equal(failed.status(), 409); assert.equal((await failed.json()).committed, false);
  await page.getByText('本次未导入，请重新预检后再确认。', { exact: true }).waitFor(); assert(await page.getByRole('button', { name: /^确认导入：/ }).isDisabled());
  const fresh = page.waitForResponse(response => response.url().endsWith('/hours/preview')); await button(page, '重新预检').click();
  assert.equal((await (await fresh).json()).data.skipped_count, 1); await rowChecks(page, 1, 1, 0);
  await button(page, '确认导入').click(); await rowChecks(page, 1, 1, 0, true); await shot(page, 'drift-repreview-receipt', viewport); record.drift = true; await context.close();
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); origin = 'http://127.0.0.1:' + server.address().port;
  try { browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    record.browser = browser.version(); assert(record.browser.startsWith('109.'));
    for (const layout of ['mixed', 'allskip']) for (const viewport of [{ width: 1920, height: 1080 }, { width: 1392, height: 924 }]) for (const theme of ['light', 'dark']) await happy(layout, viewport, theme);
    await boundaries(); assert.deepEqual(record.errors, []); assert.deepEqual(record.external, []);
  } finally { if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'process-quota-ui.json'), JSON.stringify(record, null, 2)); }
  console.log(JSON.stringify({ browser: record.browser, cases: record.cases.length, screenshots: record.screenshots.length, refreshes: record.refreshes }));
})().catch(error => { console.error(error); process.exitCode = 1; });
