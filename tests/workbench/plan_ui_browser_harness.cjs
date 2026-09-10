'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto'), http = require('node:http'), assert = require('node:assert/strict');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const files = ['WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx', 'resource-contract.js', 'resource-session.js', 'ResourceControls.jsx', 'PointContract.js', 'PlanContract.js', 'PointGanttModel.js', 'PointGantt.jsx',
  'PlanGanttModel.js', 'PlanLayout.jsx', 'PlanGanttCanvas.jsx', 'PlanGantt.jsx', 'PlanCatalogUI.jsx', 'PlanDetailsUI.jsx', 'PlanExportUI.jsx', 'PlanWorkspace.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchNumberControls.jsx'];
const fixtureScript = `
const F = window.PlanUIFixtures;
let mounted;
function Harness({spec}) {
  const [view,setView] = React.useState(spec.view || 'analysis'), [theme,setTheme] = React.useState(spec.theme || 'light');
  const [adapterVersion,setAdapterVersion] = React.useState(0), [context,setContext] = React.useState(spec.context || {});
  fixture.replaceAdapter = () => setAdapterVersion(n=>n+1);
  const adapter = React.useMemo(()=>{
    async function call(type,reference,scope,signal) {
      const record={type,ref:reference,scope:F.clone(scope),aborted:false}; fixture.calls.push(record);
      const f = fixture;
      signal.addEventListener('abort',()=>{record.aborted=true;},{once:true});
      if (f.spec.hold===type || type==='workspace' && reference===f.spec.holdRef) await new Promise(resolve=>f.held.push(resolve));
      const failure = f.spec[type+'Failure'];
      if(failure) throw {message:failure,committed:false};
      return record;
    }
    return {
      catalog:async(scope,signal)=>{
        await call('catalog',null,scope,signal);
        const value=F.catalog(scope,fixture.spec);
        if(fixture.spec.badCatalog)value.data.page.total=999;
        return value;
      },
      workspace:async(reference,scope,signal)=>{
        await call('workspace',reference,scope,signal);
        const value=F.workspace(reference,scope,fixture.spec);
        if(fixture.spec.badWorkspace)delete value.data.projections.calendar;
        if(fixture.spec.wrongPlan)value.data.plan.plan_ref=F.ref(777);
        return value;
      },
      export:async(reference,scope,signal)=>{
        await call('export',reference,scope,signal);
        const csv=scope.format==='csv',name='计划读取范围.'+scope.format;
        return {blob:new Blob([csv?'批次,工序\\n内存夹具,1\\n':'XLSX adapter fixture bytes; serialization verified by H tests']),
          contentType:csv?'text/csv;charset=utf-8':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          disposition:'attachment; filename*=UTF-8\\'\\''+encodeURIComponent(name)};
      },
      command:()=>{fixture.writes++;throw new Error('UI has no write permission');}
    };
  },[adapterVersion]);
  fixture.adapter = adapter;
  React.useLayoutEffect(()=>{document.documentElement.dataset.theme=theme;},[theme]);
  const navigate=(next,ctx)=>{fixture.navigations.push({next,context:ctx});setView(next);if(ctx)setContext(ctx);};
  return React.createElement(React.Fragment,null,
    React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls),React.createElement(WorkbenchNumberControls),
    React.createElement(AppShell,{active:view,onNav:navigate,theme,onToggleTheme:()=>setTheme(t=>t==='light'?'dark':'light'),operations:true,showCapsule:false,title:view==='gantt'?'设备 / 人员 / 批次甘特':'选择排产方案'},
      React.createElement(PlanWorkspace,{adapter,view,onNavigate:navigate,initialContext:context,disabled:!!spec.disabled})));
}
window.mountPlan = spec => {
  if(mounted)mounted.unmount();
  window.fixture={spec,calls:[],held:[],writes:0,navigations:[]};
  mounted=ReactDOM.createRoot(document.getElementById('fixture-root'));
  mounted.render(React.createElement(Harness,{spec}));
};
`;
function server(report) {
  const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
  const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
  report.compile = { target: built.target, global_build: false, babel: built.babel_version };
  report.sources = sources.map(item => ({ path: item.path, sha256: hash(item.code) }));
  report.probes = ['plan_ui_browser_harness.cjs', 'plan_ui_browser_probe.cjs', 'plan_ui_model_probe.cjs', 'test_plan_ui.py'].map(name => ({
    path: 'tests/workbench/' + name, sha256: hash(fs.readFileSync(path.join(__dirname, name))) }));
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json'))), assets = new Map();
  report.style_build_id = manifest.build_id;
  for (const item of manifest.files) {
    const bytes = fs.readFileSync(path.join(root, 'static', item.path)); assert.equal(hash(bytes), item.sha256, 'Concurrent shared asset build: retry after build settles');
    assets.set('/static/' + item.path, { bytes, mime: item.mime });
  }
  const compiled = built.outputs.map((item, index) => { const url = '/fixture/' + files[index] + '.js'; assets.set(url, { bytes: item.code, mime: 'application/javascript' }); return url; });
  const probe = 'tests/workbench/plan_ui_fixtures.cjs';
  const fixtureBytes = fs.readFileSync(path.join(root, probe)); report.sources.push({ path: probe, sha256: hash(fixtureBytes) });
  assets.set('/fixture/data.js', { bytes: fixtureBytes, mime: 'application/javascript' });
  assets.set('/fixture/harness.js', { bytes: fixtureScript, mime: 'application/javascript' });
  const sharedScripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
  const css = manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('');
  const scripts = sharedScripts.map(file => '/static/' + file).concat(compiled, ['/fixture/data.js', '/fixture/harness.js']).map(url => '<script src="' + url + '"></script>').join('');
  const html = '<!doctype html><html lang="zh-CN" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + css + '</head><body class="aps-workbench"><div id="fixture-root"></div>' + scripts + '</body></html>';
  return http.createServer((request, response) => {
    if (request.url === '/' || request.url.startsWith('/?')) {
      response.setHeader('Content-Type', 'text/html;charset=utf-8');
      response.end(request.url === '/?preview=1' ? html.replace('</body>', '<script>mountPlan({});</script></body>') : html); return;
    }
    if (request.url === '/favicon.ico') { response.writeHead(204); response.end(); return; }
    const item = assets.get(request.url);
    if (item) { response.setHeader('Content-Type', item.mime); response.end(item.bytes); }
    else { report.unexpected_requests.push(request.url); response.writeHead(404); response.end(); }
  });
}
module.exports = { server, files, root, hash };
