/* Current-source browser checks for calendar/catalog fields, scoped guards and outsourcing presentation. */
'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), out = process.argv[2];
if (!out) throw new Error('Pass an artifact directory');
fs.mkdirSync(out, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const names = ['resource-contract.js', 'resource-session.js', 'WorkbenchGuards.js', 'ResourceControls.jsx', 'WorkbenchGuardHost.jsx', 'ResourceForms.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControls.jsx', 'WorkbenchListControls.jsx', 'WorkbenchFormat.js', 'WorkbenchReferences.jsx', 'CalendarContract.js', 'CalendarFields.jsx',
  'CalendarDayDialog.jsx', 'CalendarRangeDialog.jsx', 'OutsourcingContract.js', 'OutsourcingSession.js', 'OutsourcingControls.jsx',
  'ResourceCatalogModel.js', 'ResourceCatalogEditor.jsx', 'ResourceCatalog.jsx'];
const sources = names.map(name => ({ path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const code = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true }).outputs.map(item => item.code).join('\n;\n');
const css = ['00-tokens.css', '21-table-frame.css', '22-shared-controls.css', '32-calendar-outsourcing.css']
  .map(name => fs.readFileSync(path.join(root, 'frontend/workbench/app/styles', name), 'utf8')).join('\n');
const fixture = `
const h=React.createElement; let app;
window.probe={closed:0,writes:0,size:0};
const context={write_token:'read-only-fixture',capabilities:{'calendar.upsert':true,'machine_group.create':true,'shift_profile.create':true}};
const command={phase:'idle',locked:false,busy:false,reset:()=>true,submit:async()=>{probe.writes++;}};
const day={date:'2026-09-12',explicit:false,stored:null,write_context:context,fields:{type:'work',hours:8.375,eff:62.5,allowNormal:'yes',allowUrgent:'no',note:''},effective:{is_working:true,window_start:'2026-09-12T08:00:00',window_end:'2026-09-12T16:22:30'}};
const target={batch:{business_code:'B-1',label:'验证批次'},supplier:{label:'供应商'},kind:'single',operations:[{business_code:'OP-1',label:'外协工序',piece:null}]};
const item={outsourcing_ref:'a'.repeat(48),target,sent:'2026-09-07T09:00:00',planned:'2026-09-09T12:00:00',returned:null,confirmedState:'in_transit'};
const api={preview:async()=>{const e=new Error('请核对本次原因。');e.fields=[{path:'reason',message:'原因需要核实。'}];throw e;}};
const pickerApi={read:async()=>({data:{items:Array.from({length:10},(_,i)=>({operation_ref:String(i).padStart(48,'a'),batch_ref:'b'.repeat(48),supplier_ref:'c'.repeat(48),business_code:'OP-'+i,label:'用于核对界面边界的外协工序长名称'.repeat(3),batch:{business_code:'B-1',label:'批次'},supplier:{label:'供应商'},can_register:true,issues:[]})),page:{number:1,size:10,total:10,pages:1}},meta:{snapshot_ref:'fixture'}})};
const adapter={list:async(kind,scope)=>({ok:true,schema_version:1,data:{entities:[],create_context:context,page:{number:scope.page,size:scope.size,total:0,pages:0,sort:[]}},meta:{source:'production',time_basis:'factory_local',snapshot_ref:'fixture',request_ref:'fixture',as_of:'2026-09-12T10:00:00'},warnings:[]})};
function Harness({mode}){
  const [open,setOpen]=React.useState(true),[selected,setSelected]=React.useState([]); const close=()=>{probe.closed++;setOpen(false);};
  const p={command,onClose:close,adapter,source:'production',refreshState:{},onRefresh:()=>{}};
  let content=null;
  if(open&&mode==='day')content=h(CalendarDayDialog,{...p,day});
  if(open&&mode==='range')content=h(CalendarRangeDialog,{...p,month:{year:2026,month:9}});
  if(open&&mode==='outsourcing')content=h('div',{className:'outsourcing-live'},h(OutsourcingControls.Editor,{api,item,command,onClose:close}));
  if(open&&mode==='catalog')content=h(ResourceCatalog,{kind:'machine_group',adapter,onClose:close});
  if(open&&mode==='shift')content=h(ResourceCatalog,{kind:'shift_profile',adapter,onClose:close});
  if(open&&mode==='picker')content=h('div',{className:'outsourcing-live',style:{width:'480px',maxWidth:'100%'}},h(OutsourcingControls.TargetPicker,{api:pickerApi,mode:'single',selected,onSelect:setSelected,onMode:()=>{},onOpen:()=>{}}));
  if(open&&mode==='pager')content=h(OutsourcingControls.Pager,{page:{number:1,size:10,total:200,pages:20},label:'外协登记',onPage:n=>{probe.page=n;},onSize:n=>{probe.size=n;}});
  if(open&&mode==='facts')content=h('div',{className:'outsourcing-live'},h(OutsourcingControls.Facts,{facts:item}));
  return h('div',{className:'plana'},content,h(WorkbenchGuardHost));
}
window.mount=mode=>{if(app)app.unmount();probe.closed=0;app=ReactDOM.createRoot(document.getElementById('root'));ReactDOM.flushSync(()=>app.render(h(Harness,{mode})));};
`;
const tags = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'))
  .map(file => '<script src="/static/' + file + '"></script>').join('');
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '<style>' + css + '</style></head><body class="aps-workbench"><div id="root"></div>' + tags + '<script src="/source.js"></script><script>' + fixture + '</script></body></html>';
const assets = new Map(manifest.files.map(item => ['/static/' + item.path, item]));
const server = http.createServer((req, res) => {
  if (req.url === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); return res.end(html); }
  if (req.url === '/source.js') { res.setHeader('Content-Type', 'application/javascript'); return res.end(code); }
  if (req.url === '/favicon.ico') { res.writeHead(204); return res.end(); }
  const asset = assets.get(req.url);
  if (!asset) { res.writeHead(404); return res.end(); }
  res.setHeader('Content-Type', asset.mime); res.end(fs.readFileSync(path.join(root, 'static', asset.path)));
});
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const report = { scope: 'current-source UI behavior with controlled read-only adapters', backend_tested: false,
  sources: sources.map(item => ({ path: 'frontend/workbench/' + item.path, sha256: sha(item.code) })), css_sha256: sha(css), cases: [], errors: [] };
let browser;
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
  report.browser = browser.version();
  const page = await browser.newPage({ viewport: { width: 1392, height: 924 } });
  page.on('pageerror', error => report.errors.push(error.message));
  await page.goto('http://127.0.0.1:' + server.address().port);
  const run = async (name, action) => { await action(); report.cases.push(name); };
  await run('calendar-error-focus-and-precision', async () => {
    await page.evaluate(() => mount('day'));
    const hours = page.getByLabel('可排工时（小时）', { exact: true });
    assert.equal(await hours.inputValue(), '8.375');
    await hours.fill('25'); await page.getByRole('button', { name: '保存配置', exact: true }).click();
    await page.waitForFunction(() => document.activeElement.name === 'hours');
    assert.equal(await hours.getAttribute('aria-invalid'), 'true');
    assert.equal(await page.locator('.wb-field-error').innerText(), '请输入有效数字。');
    assert.equal(await page.evaluate(() => probe.writes), 0);
  });
  await run('calendar-footer-cancel-retains-draft-and-one-confirm', async () => {
    await page.getByRole('button', { name: '取消', exact: true }).click();
    await page.getByRole('button', { name: '留在当前页面', exact: true }).click();
    assert.equal(await page.getByLabel('可排工时（小时）', { exact: true }).inputValue(), '25');
    await page.getByRole('button', { name: '取消', exact: true }).click();
    await page.getByRole('button', { name: '放弃未保存内容并继续', exact: true }).click();
    await page.waitForFunction(() => probe.closed === 1); assert.equal(await page.getByRole('dialog').count(), 0);
  });
  await run('calendar-range-invalid-date-focus', async () => {
    await page.evaluate(() => mount('range'));
    await page.getByLabel('开始日期', { exact: true }).fill('');
    await page.getByRole('button', { name: '预览变更', exact: true }).click();
    await page.waitForFunction(() => document.activeElement.type === 'date' && document.activeElement.getAttribute('aria-invalid') === 'true');
    assert.equal(await page.locator('.wb-field-error').count(), 1);
  });
  await run('outsourcing-general-errors-stay-general-and-focus-summary', async () => {
    await page.evaluate(() => mount('outsourcing'));
    await page.getByRole('button', { name: '预检核对', exact: true }).click();
    await page.waitForFunction(() => document.activeElement.querySelector('[role="alert"]'));
    assert.equal(await page.locator('[aria-invalid="true"]').count(), 0);
    assert.match(await page.getByRole('alert').innerText(), /请填写经办人/);
  });
  await run('outsourcing-server-field-errors-focus-exact-field', async () => {
    await page.getByLabel('外协经办人', { exact: true }).fill('张工');
    await page.getByLabel('外协核实原因', { exact: true }).fill('核对现有记录');
    await page.getByRole('button', { name: '预检核对', exact: true }).click();
    await page.waitForFunction(() => document.activeElement.getAttribute('aria-label') === '外协核实原因');
    assert.equal(await page.locator('.wb-field-error').innerText(), '原因需要核实。');
  });
  await run('catalog-shared-fields-and-scoped-modal-close', async () => {
    await page.evaluate(() => mount('catalog'));
    await page.getByRole('button', { name: '新增设备组', exact: true }).click();
    await page.getByRole('button', { name: '保存', exact: true }).click();
    await page.waitForFunction(() => document.activeElement.name === 'business_code');
    assert.equal(await page.locator('.wb-field-error').count(), 3);
    await page.getByLabel('名称', { exact: true }).fill('保留目录草稿');
    await page.getByRole('button', { name: '返回列表', exact: true }).click();
    await page.getByRole('button', { name: '留在当前页面', exact: true }).click();
    assert.equal(await page.getByLabel('名称', { exact: true }).inputValue(), '保留目录草稿');
    await page.getByRole('button', { name: '关闭', exact: true }).first().click();
    await page.getByRole('button', { name: '放弃未保存内容并继续', exact: true }).click();
    await page.waitForFunction(() => probe.closed === 1); assert.equal(await page.getByRole('dialog').count(), 0);
  });
  await run('catalog-cycle-generator-focuses-real-validation-field', async () => {
    await page.evaluate(() => mount('shift'));
    await page.getByRole('button', { name: '新增班次档', exact: true }).click();
    await page.getByLabel('轮换天数', { exact: true }).fill('0');
    await page.getByRole('button', { name: '生成逐日规则', exact: true }).click();
    await page.waitForFunction(() => document.activeElement.name === 'cycle_days');
    assert.equal(await page.locator('.wb-field-error').innerText(), '轮换天数必须为 1 至 366。');
  });
  await run('outsourcing-table-scroll-and-sticky-intersection', async () => {
    await page.evaluate(() => mount('picker'));
    await page.getByLabel('选择工序 OP-0', { exact: true }).waitFor();
    const geometry = await page.locator('.os-pick-scroll').evaluate(frame => {
      frame.scrollTop=120;frame.scrollLeft=90;
      const box=frame.getBoundingClientRect(),head=frame.querySelector('thead th').getBoundingClientRect(),operation=frame.querySelector('.os-operation-key').getBoundingClientRect(),action=frame.querySelector('thead th:last-child').getBoundingClientRect();
      return {width:box.width,height:box.height,scrollTop:frame.scrollTop,scrollLeft:frame.scrollLeft,top:head.top-box.top,left:head.left-box.left,operationLeft:operation.left-box.left,actionRight:action.right-box.right,caption:frame.querySelectorAll('caption').length,scopes:Array.from(frame.querySelectorAll('th')).every(th=>th.scope==='col')};
    });
    report.geometry=geometry;await page.screenshot({path:path.join(out,'outsourcing-scroll.png')});
    assert(geometry.scrollTop>0&&geometry.scrollLeft>0);assert(Math.abs(geometry.top)<2&&Math.abs(geometry.left)<2&&Math.abs(geometry.operationLeft-52)<2&&Math.abs(geometry.actionRight)<2);assert(geometry.scopes&&geometry.caption===1);
  });
  await run('outsourcing-page-sizes-and-null-return-semantics', async () => {
    await page.evaluate(() => mount('pager'));
    assert.deepEqual(await page.getByLabel('外协登记每页数量', { exact: true }).locator('option').evaluateAll(rows => rows.map(row => Number(row.value))), [2, 10, 20, 50, 100]);
    await page.getByLabel('外协登记每页数量', { exact: true }).selectOption('100');
    assert.equal(await page.evaluate(() => probe.size), 100);
    await page.evaluate(() => mount('facts'));
    assert.match(await page.locator('.os-facts').innerText(), /未回厂/);
    assert.match(await page.locator('.os-facts').innerText(), /2026-09-07 09:00:00/);
  });
  assert.deepEqual(report.errors, []);
  await page.screenshot({ path: path.join(out, 'final.png') });
  report.passed = true;
})().catch(error => { report.passed = false; report.failure = error.stack; process.exitCode = 1; }).finally(async () => {
  if (browser) await browser.close(); await new Promise(resolve => server.close(resolve));
  fs.writeFileSync(path.join(out, 'result.json'), JSON.stringify(report, null, 2)); console.log(JSON.stringify(report));
});
