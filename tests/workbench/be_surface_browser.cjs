'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], packet = JSON.parse(fs.readFileSync(path.join(output, 'dto.json')));
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const files = ['WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx', 'resource-contract.js', 'resource-api.js', 'resource-session.js', 'ResourceControls.jsx', 'CalendarContract.js',
  'PointContract.js', 'PointGanttModel.js', 'PointGantt.jsx', 'PlanProcessOrder.js', 'PlanContract.js', 'PlanAPI.js',
  'ActualGanttModel.js', 'ActualGanttContract.js', 'ActualGanttAPI.js', 'ActualGanttControls.jsx', 'ActualGanttCanvas.jsx', 'ActualGanttRows.jsx', 'ActualGanttWorkspace.jsx',
  'PreflightContract.js', 'PreflightAPI.js', 'PreflightControls.jsx', 'PreflightBatchPicker.jsx', 'PreflightWorkspace.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchNumberControls.jsx'];
const report = { errors: [], external: [], variants: [], screenshots: [], target: 'chrome109', static_build: false,
  data_source: 'private Flask API DTO replay; browser adapters do not access any DB', baseline_method: 'same DTO with previous 1320px root cap' };
const sources = files.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
report.sources = sources.map(source => ({ path: source.path, sha256: hash(source.code) }));
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
assert.deepEqual(built.target, { chrome: '109' });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json'))), assets = new Map();
report.shared_build_id = manifest.build_id;
manifest.files.forEach(file => { const bytes = fs.readFileSync(path.join(root, 'static', file.path)); assert.equal(hash(bytes), file.sha256); assets.set('/static/' + file.path, { bytes, mime: file.mime }); });
built.outputs.forEach((file, i) => assets.set('/be/' + files[i], { bytes: file.code, mime: 'application/javascript' }));
const scripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-')).map(file => '/static/' + file).concat(files.map(file => '/be/' + file));
const mount = `
  let mounted; window.loads=[]; window.exports=[]; window.preflightCalls=[]; window.navigations=[];
  window.packet=${JSON.stringify(packet)}; const clone=value=>JSON.parse(JSON.stringify(value));
  function shell(child,spec,active){return React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls),React.createElement(WorkbenchNumberControls),
    React.createElement(AppShell,{active,theme:spec.theme,onToggleTheme:()=>{},onNav:(...args)=>navigations.push(args),operations:true,title:active==='run'?'执行排产':'现场实际甘特'},child));}
  function mount(child,spec,active){if(mounted)mounted.unmount();document.documentElement.dataset.theme=spec.theme;mounted=ReactDOM.createRoot(document.getElementById('be-root'));mounted.render(shell(child,spec,active));}
  window.mountPreflight=spec=>{
    const response=clone(packet.preflight);
    if(spec.extra){response.data.run_blocked_reasons.push({code:'operation_blocked',message:'测试补充：同类原因仍保留原文。',operation_ref:response.data.tasks[22].operation_ref,batch_ref:response.data.tasks[22].batch_ref},
      {code:'be_tail_reason',message:'测试补充：末项原因不能因截断丢失。',operation_ref:response.data.tasks[22].operation_ref,batch_ref:response.data.tasks[22].batch_ref});}
    window.PreflightAPI.create=()=>({preflight:async input=>{preflightCalls.push(clone(input));return clone(response);}});
    mount(React.createElement(PreflightWorkspace,{initialContext:packet.preflight_input,onNavigate:(...args)=>navigations.push(args)}),spec,'run');
  };
  window.mountActual=spec=>{
    const response=clone(packet.actual);
    if(spec.otherResources){for(const [index,kind] of ['machine','operator'].entries()){
      const ref=String(index+8).repeat(48);response.data.resources.push({ref,kind,business_code:'BE-OTHER-'+kind,label:kind==='machine'?'另一设备':'另一人员'});
      response.data.items[0].execution.reports[0]['actual_'+kind+'_ref']=ref;}}
    if(spec.noReports){const e=response.data.items[0].execution;e.reports=[];e.execution_state='unreported';e.known_completed_quantity=0;e.remaining_quantity=e.target_quantity;response.data.report_count=0;}
    if(spec.unavailable){response.data.availability={state:'unavailable',reason:'报工记录不可用，实际状态无法核实。'};response.data.report_count=null;response.data.items.forEach(item=>item.execution=null);}
    const adapter={load:async input=>{loads.push(clone(input));return clone(response);},export:async input=>{exports.push(clone(input));const csv=await fetch('/be/actual.csv');return {blob:await csv.blob(),...packet.csv_headers};}};
    mount(React.createElement(ActualGanttWorkspace,{adapter,initialContext:{scope:packet.scope,fixture:spec.key},onNavigate:(...args)=>navigations.push(args)}),spec,'fieldgantt');
  };
  window.inspectModel=mode=>{const model=ActualGanttModel.layout(packet.actual.data,{mode,query:'',late:'all',collapsed:{},onlySelected:false},packet.actual.meta.as_of);
    return model.groups.map(group=>({id:group.id,count:group.reportCount,members:group.members.size,refs:Array.from(group.members.values()).flatMap(member=>member.reports.map(report=>report.report_ref))}));};
`;
assets.set('/be/mount.js', { bytes: mount, mime: 'application/javascript' });
assets.set('/be/actual.csv', { bytes: fs.readFileSync(path.join(output, 'actual.csv')), mime: 'text/csv' });
const html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
  + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') + '</head><body class="aps-workbench"><div id="be-root"></div>'
  + scripts.concat(['/be/mount.js']).map(url => '<script src="' + url + '"></script>').join('') + '</body></html>';
const server = http.createServer((req, res) => {
  if (req.url === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (req.url === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  const asset = assets.get(req.url); if (!asset) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
async function shot(page, name) {
  await page.evaluate(() => { window.scrollTo(0, 0); return new Promise(resolve => requestAnimationFrame(resolve)); });
  const file = path.join(output, name + '.png'); await page.screenshot({ path: file, fullPage: true }); report.screenshots.push(file);
}
async function ready(page) {
  await page.locator('[data-actual-scroll]').waitFor();
  await page.waitForFunction(() => {
    const board = document.querySelector('[data-actual-scroll]'), row = document.querySelector('.fg-axis');
    return row && Math.abs(row.getBoundingClientRect().width - board.clientWidth) < 1;
  });
}
async function bounds(page, selector) {
  return page.locator(selector).evaluate(node => {
    const root = node.getBoundingClientRect(), parent = node.parentElement, box = parent.getBoundingClientRect(), css = getComputedStyle(parent);
    const main = document.querySelector('.page-content'), mainBox = main.getBoundingClientRect(), style = getComputedStyle(main);
    return { width: root.width, left: root.left, right: root.right, parentAvailable: box.width - parseFloat(css.paddingLeft) - parseFloat(css.paddingRight),
      mainAvailable: mainBox.width - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight), maxWidth: getComputedStyle(node).maxWidth,
      overflow: document.documentElement.scrollWidth > innerWidth + 1 };
  });
}
async function geometry(page) {
  return page.locator('[data-report-ref]').first().evaluate(node => {
    const track = node.parentElement.getBoundingClientRect(), bar = node.getBoundingClientRect();
    return { width: bar.width, track: track.width, ratio: bar.width / track.width, title: node.title };
  });
}
async function preflight(page, variant) {
  await page.evaluate(spec => mountPreflight(spec), variant);
  await page.getByRole('button', { name: '开始排产检查', exact: true }).click();
  await page.locator('[data-reason-group=operation_blocked]').waitFor();
  assert.equal(await page.locator('[data-reason-group=operation_blocked]').innerText(), '19道工序缺必填资料');
  assert.equal(await page.locator('[data-reason-group=execution_review_required]').innerText(), '2道工序已有执行记录待核对');
  assert.equal(await page.getByRole('button', { name: /^开始排产：/ }).isDisabled(), true);
  assert.deepEqual(await page.evaluate(() => preflightCalls[preflightCalls.length - 1]), packet.preflight_input);
  const rect = await bounds(page, '[data-preflight-workspace]');
  assert.equal(rect.overflow, false); assert.equal(rect.maxWidth, 'none'); assert.ok(Math.abs(rect.width - rect.mainAvailable) < 1);
  const compact = await page.locator('.pf-alert').boundingBox(), footer = await page.locator('.pf-footer').boundingBox();
  assert.ok(compact.height < 190); assert.ok(footer.y >= compact.y + compact.height);
  variant.preflight = { ...rect, alertHeight: compact.height, footerBottom: footer.y + footer.height };
  await shot(page, variant.key + '-preflight');
  await page.locator('.pf-detail > summary').first().click();
  assert.equal(await page.getByRole('table', { name: '排产前检查明细' }).locator('tbody tr').count(), 23);
  await page.locator('.pf-reasons > summary').click();
  const rows = await page.locator('.pf-reason-list p').evaluateAll(nodes => nodes.map(node => ({ code: node.dataset.reasonCode,
    operation_ref: node.dataset.operationRef, batch_ref: node.dataset.batchRef, text: node.textContent })));
  const reasons = packet.preflight.data.run_blocked_reasons.concat(packet.preflight.data.warnings);
  assert.equal(rows.length, reasons.length);
  reasons.forEach(reason => assert.ok(rows.some(row => row.code === reason.code && row.operation_ref === reason.operation_ref && row.batch_ref === reason.batch_ref && row.text.includes(reason.message))));
  assert.ok(rows.filter(row => row.operation_ref).every(row => row.text.includes('CAT-B')));
  await shot(page, variant.key + '-preflight-details');
}
async function actual(page, variant) {
  await page.evaluate(spec => mountActual(spec), variant); await ready(page);
  await page.locator('[data-actual-gantt]').evaluate(node => { node.style.maxWidth = '1320px'; }); await ready(page);
  const before = await bounds(page, '[data-actual-gantt]'), oldBar = await geometry(page);
  await page.locator('[data-actual-gantt]').evaluate(node => { node.style.maxWidth = ''; }); await ready(page);
  const after = await bounds(page, '[data-actual-gantt]'), bar = await geometry(page);
  assert.equal(after.maxWidth, 'none'); assert.equal(after.overflow, false); assert.ok(Math.abs(after.width - after.mainAvailable) < 1);
  if (variant.width === 1920) { assert.equal(before.width, 1320); assert.ok(after.width - before.width > 300); }
  assert.ok(Math.abs(bar.ratio - oldBar.ratio) < .0001); assert.equal(bar.title, oldBar.title);
  const data = packet.actual.data, execution = data.items[0].execution, reportRow = execution.reports[0];
  const ratio = (Date.parse(reportRow.actual_end) - Date.parse(reportRow.actual_start)) / (Date.parse(data.axis_span.end) - Date.parse(data.axis_span.start));
  assert.ok(Math.abs(bar.ratio - ratio) < .0001);
  variant.actual = { before, after, oldBar, bar, groups: {} };
  for (const [mode, label] of [['machine', '设备'], ['operator', '人员'], ['batch', '批次']]) {
    await page.getByRole('button', { name: label, exact: true }).click();
    const groups = await page.evaluate(mode => inspectModel(mode), mode); variant.actual.groups[mode] = groups;
    assert.equal(groups.reduce((count, group) => count + group.count, 0), 1);
    assert.equal(await page.locator('[data-actual-mark=plan]').count(), 1);
    assert.ok((await page.locator('[data-actual-count]').innerText()).includes('1 / 1'));
    if (mode !== 'batch') {
      assert.equal(groups.length, 2); assert.equal(groups.find(group => group.id === 'unbound').count, 1);
      assert.equal(groups.find(group => group.id !== 'unbound').count, 0);
      assert.ok((await page.locator('[data-task-row][data-kind=actual] .fg-wait').innerText()).includes('本' + label + '暂无报工；报工在“' + label + '未填写”分组'));
      assert.equal(await page.locator('[data-task-row][data-kind=actual] .fg-row-caption').filter({ hasText: /^暂无逐次报工$/ }).count(), 0);
      assert.equal(await page.locator('[data-report-ref]').getAttribute('data-report-ref'), reportRow.report_ref);
      await page.getByRole('button', { name: '全部折叠', exact: true }).click();
      const headers = await page.locator('[data-resource] .fg-group-summary').allTextContents();
      assert.ok(headers.some(text => text.includes('0 次报工')) && headers.some(text => text.includes('1 次报工')));
      await page.getByRole('button', { name: '全部展开', exact: true }).click();
    } else { assert.equal(groups.length, 1); assert.equal(await page.locator('[data-kind=actual] .fg-wait').count(), 0); }
    await shot(page, variant.key + '-actual-' + mode);
  }
  await page.locator('[data-report-ref]').click(); await page.getByRole('checkbox', { name: '详情', exact: true }).check();
  assert.ok((await page.getByLabel('工序详情', { exact: true }).innerText()).includes('BG-00000001'));
  assert.ok((await page.getByLabel('工序详情', { exact: true }).innerText()).includes('完成依据：逐次报工记录'));
  assert.ok(!(await page.getByLabel('工序详情', { exact: true }).innerText()).includes('投影'));
  await shot(page, variant.key + '-actual-selected');
  await page.getByRole('checkbox', { name: '只看选中', exact: true }).check(); await page.getByLabel('搜索现场甘特').fill('BG-00000001');
  await page.getByRole('button', { name: '全部折叠', exact: true }).click();
  await page.getByRole('button', { name: '导出 CSV', exact: true }).click();
  const download = page.waitForEvent('download'); await page.getByRole('button', { name: '下载 CSV', exact: true }).click();
  const downloaded = await download, file = path.join(output, variant.key + '-export.csv'); await downloaded.saveAs(file);
  assert.equal(hash(fs.readFileSync(file)), hash(fs.readFileSync(path.join(output, 'actual.csv'))));
  assert.deepEqual(await page.evaluate(() => exports[exports.length - 1]), packet.export_scope);
  assert.deepEqual(await page.evaluate(() => loads[loads.length - 1]), packet.scope);
  variant.actual.export_scope_unchanged = true;
}
async function edgeCases(page) {
  await page.evaluate(() => mountPreflight({ theme: 'dark', extra: true }));
  await page.getByRole('button', { name: '开始排产检查', exact: true }).click();
  await page.locator('[data-reason-group=be_tail_reason]').waitFor();
  assert.equal(await page.locator('[data-reason-group=operation_blocked]').innerText(), '19道工序缺必填资料');
  await page.locator('.pf-reasons > summary').click();
  assert.ok((await page.locator('.pf-reason-list').innerText()).includes('同类原因仍保留原文'));
  assert.ok((await page.locator('.pf-reason-list').innerText()).includes('末项原因不能因截断丢失'));
  await page.evaluate(() => mountActual({ theme: 'dark', key: 'other-resources', otherResources: true })); await ready(page);
  for(const label of ['设备','人员']) {
    await page.getByRole('button',{name:label,exact:true}).click();
    assert.equal(await page.locator('[data-kind=actual] .fg-wait').innerText(),'本'+label+'暂无报工；报工在其他'+label+'下');
  }
  await page.evaluate(() => mountActual({ theme: 'dark', key: 'no-reports', noReports: true })); await ready(page);
  for(const label of ['设备','人员','批次']) {
    await page.getByRole('button',{name:label,exact:true}).click();
    assert.equal(await page.locator('[data-kind=actual] .fg-wait').innerText(),label==='批次'?'暂无实际报工':'本'+label+'暂无报工');
  }
  await page.evaluate(() => mountActual({ theme: 'dark', key: 'unavailable', unavailable: true })); await ready(page);
  assert.ok((await page.locator('[data-actual-gantt]').innerText()).includes('报工记录不可用，实际状态无法核实。'));
  assert.equal(await page.getByRole('button', { name: '导出 CSV', exact: true }).isDisabled(), true);
  assert.ok((await page.locator('.fg-group-summary').innerText()).includes('执行记录不可用'));
  report.edge_cases = ['duplicate operation count stays unique', 'same-code detail and trailing reason retained', 'reports under other bound resources',
    'no reports in task or resource', 'unavailable reason and disabled export retained'];
}
async function main() {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port; let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true }); report.browser = browser.version(); assert.ok(report.browser.startsWith('109.'));
    for (const width of [1920, 1392]) for (const theme of ['light', 'dark']) {
      const variant = { width, theme, key: width + '-' + theme, passed: false }; report.variants.push(variant);
      const context = await browser.newContext({ viewport: { width, height: 1080 }, timezoneId: 'Asia/Shanghai' }), page = await context.newPage(); page.setDefaultTimeout(12000);
      page.on('pageerror', error => report.errors.push(error.message)); page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/') && !route.request().url().startsWith('blob:')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      try { await page.goto(origin); await preflight(page, variant); await actual(page, variant); if (width === 1392 && theme === 'dark') await edgeCases(page); variant.passed = true; }
      catch (error) { await shot(page, variant.key + '-FAILED'); throw error; } finally { await context.close(); }
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
  } finally { if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); }
}
main().catch(error => { report.error = error.stack; process.exitCode = 1; console.error(error.stack); }).finally(() => {
  fs.writeFileSync(path.join(output, 'be-surfaces.json'), JSON.stringify(report, null, 2)); console.log(JSON.stringify({ output, variants: report.variants.length, errors: report.errors }));
});
