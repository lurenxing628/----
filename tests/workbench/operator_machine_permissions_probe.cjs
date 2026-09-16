'use strict';
// Browser control regression with an explicit mock adapter; database proof lives in pytest.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const order = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json')));
const { compile } = require('../../scripts/workbench/compile.cjs');
const sourceNames = ['resource-api.js', 'OperatorMachinePermissions.jsx', 'ResourceForms.jsx'];
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype', order.babel.path),
  sources: sourceNames.map(name => ({ path: name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') })) }).outputs;
const fixture = `
const ref=n=>n.toString(16).padStart(48,'0'), context={write_token:'edit',capabilities:{'operator.update':true},blocked_reasons:[]};
const source=[{machine_ref:ref(1),business_code:'M1',label:'铣床',skill_level:'旧等级',is_primary:'非主操'},
 {machine_ref:ref(2),business_code:'M2',label:'车床',skill_level:'expert',is_primary:'yes'}];
const envelope=data=>({ok:true,schema_version:1,data,warnings:[],meta:{source:'production',time_basis:'factory_local',snapshot_ref:'mock',request_ref:'mock',as_of:'2026-09-15T08:00:00'}});
window.permissionFixture={preview:null,command:null};
const adapter={choices:async()=>envelope({entities:[{ref:ref(3),business_code:'M3',label:'磨床'}],page:{total:1}}),
 preview:async(path,body)=>{permissionFixture.preview=body;return envelope({operator_ref:ref(9),preview_ref:'preview',write_context:{write_token:'confirm',capabilities:{'operator.machine_permissions':true}},
 rows:body.machine_permissions.map(row=>({entity_ref:row.machine_ref,business_code:'设备',label:'测试设备',result:'update',changes:{},after:row}))});},
 command:async(kind,action,ref,body)=>{permissionFixture.command={kind,action,ref,body};return {ok:true,result:'committed',receipt_ref:'receipt',replayed:false,data:{entity_ref:ref},warnings:[]};}};
function Fixture(){const command=APSResourceSession.useCommand(adapter);return React.createElement('div',{className:'plana resource-workspace'},React.createElement(OperatorMachinePermissions,{adapter,
 entity:{ref:ref(9),business_code:'O1',label:'操作员',write_context:context,relationships:{machine_permissions:source}},source:'production',command,onClose:()=>{},refreshState:{done:true},Feedback:ResourceForms.Feedback}));}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls),React.createElement(WorkbenchNumberControls),React.createElement(Fixture)));
`;
const records = new Map(manifest.files.map(row => [row.path, row]));
const html = '<!doctype html><html><head><meta charset="utf-8">' + manifest.styles.map(name => '<link rel="stylesheet" href="/static/' + name + '">').join('')
  + '<style>' + fs.readFileSync(path.join(root, 'frontend/workbench/app/styles/31-batches-resources.css'), 'utf8') + '</style></head><body class="aps-workbench"><div id="root"></div>'
  + manifest.scripts.filter(name => !name.endsWith('/main.js')).map(name => '<script src="/static/' + name + '"></script>').join('')
  + compiled.map(row => '<script>' + row.code + '</script>').join('') + '<script>' + fixture + '</script></body></html>';
const server = http.createServer((req, res) => {
  if (req.url === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (req.url === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  const name = new URL(req.url, 'http://fixture').pathname.slice('/static/'.length), record = records.get(name);
  if (!record) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', record.mime); res.end(fs.readFileSync(path.join(root, 'static', name)));
});
const report = { scope: 'component-mock-current-sources', cases: [], errors: [] };
(async () => { let browser;
  try {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const origin = 'http://127.0.0.1:' + server.address().port;
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
    for (const width of [1392, 1280]) for (const theme of ['light', 'dark']) {
      const page = await browser.newPage({ viewport: { width, height: width === 1392 ? 924 : 720 } });
      page.on('pageerror', error => report.errors.push(error.message));
      await page.goto(origin); await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
      await page.getByRole('button', { name: '预览变更', exact: true }).waitFor();
      assert.equal(await page.getByRole('combobox', { name: '技能等级 M1', exact: true }).inputValue(), JSON.stringify('旧等级'));
      await page.getByRole('combobox', { name: '选择关联设备', exact: true }).selectOption('3'.padStart(48, '0'));
      await page.getByRole('button', { name: '新增关联', exact: true }).click();
      await page.getByRole('combobox', { name: '主操设备 M3', exact: true }).selectOption(JSON.stringify('yes'));
      assert.equal(await page.getByRole('combobox', { name: '主操设备 M2', exact: true }).inputValue(), JSON.stringify('no'));
      assert.equal(await page.getByRole('combobox', { name: '主操设备 M1', exact: true }).inputValue(), JSON.stringify('非主操'));
      await page.getByRole('row').filter({ hasText: 'M2 · 车床' }).getByRole('button', { name: '解除关联', exact: true }).click();
      await page.getByRole('button', { name: '预览变更', exact: true }).click();
      await page.getByRole('button', { name: '确认保存设备关联', exact: true }).waitFor();
      const preview = await page.evaluate(() => permissionFixture.preview);
      assert.equal(preview.machine_permissions.length, 2);
      assert.deepEqual(preview.machine_permissions[0], { machine_ref: '1'.padStart(48, '0'), skill_level: '旧等级', is_primary: '非主操' });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
      await page.screenshot({ path: path.join(output, width + '-' + theme + '.png') });
      await page.getByRole('button', { name: '确认保存设备关联', exact: true }).click();
      await page.getByText('已刷新人员资料，设备关联已保存。', { exact: true }).waitFor();
      const command = await page.evaluate(() => permissionFixture.command);
      assert.equal(command.kind, 'operator'); assert.equal(command.action, 'machine_permissions');
      assert.deepEqual(command.body.input, { preview_ref: 'preview' });
      assert(await page.getByRole('combobox', { name: '技能等级 M1', exact: true }).isDisabled());
      report.cases.push({ width, theme, passed: true }); await page.close();
    }
    assert.deepEqual(report.errors, []);
  } finally {
    if (browser) await browser.close(); server.close();
    fs.writeFileSync(path.join(output, 'permissions-result.json'), JSON.stringify(report, null, 2));
  }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
