'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const files = ['WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx', 'WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchReferences.jsx', 'resource-contract.js', 'resource-api.js', 'resource-session.js', 'WorkbenchGuards.js', 'ResourceControls.jsx', 'WorkbenchGuardHost.jsx', 'PointContract.js', 'PointGanttModel.js', 'PointGantt.jsx',
  'FieldContract.js', 'FieldDraftModel.js', 'FieldAPI.js', 'FieldControls.jsx', 'FieldFilters.jsx', 'FieldEditorFields.jsx', 'FieldEditor.jsx', 'FieldDetail.jsx', 'FieldTable.jsx', 'FieldFiles.jsx', 'FieldWorkspace.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchListControls.jsx', 'WorkbenchNumberControls.jsx'];
const script = `
let mounted;
window.probe = {calls:[],writes:[],lookups:[],nav:[]};
async function mountField(spec={}) {
  if(mounted)mounted.unmount();
  const base=FieldAPI.create(), initial=spec.mock?await base.list({size:100}):null;
  const clone=value=>JSON.parse(JSON.stringify(value));
  const api=spec.mock?{...base,
    list:async(scope)=>{probe.calls.push(scope);if(window.mockReadFailure)throw {committed:false,message:'模拟读取失败'};const result=clone(initial);const size=Number(scope.size||20),page=Number(scope.page||1);result.data.tasks=result.data.tasks.slice((page-1)*size,page*size);result.data.page={number:page,size,total:26,pages:Math.ceil(26/size)};if(window.mockWrongProjection)result.data.tasks[0].execution.operation_ref='f'.repeat(48);return result;},
    detail:async(ref)=>{const result=clone(initial);result.data={task:result.data.tasks.find(task=>task.task_ref===ref),scope:result.data.scope};return result;},
    command:async(kind,action,ref,body)=>{probe.writes.push({kind,action,ref,body});throw {committed:'unknown',message:'模拟连接中断，等待核实'};},
    lookup:async(key)=>{probe.lookups.push(key);return window.mockReceipt||{ok:true,state:'not_recorded',receipt:null,may_be_in_flight:true};}
  }:base;
  function Harness(){
    const [view,setView]=React.useState('field'),[context,setContext]=React.useState({return_to:'analysis'}),[theme,setTheme]=React.useState(spec.theme||'light');
    React.useLayoutEffect(()=>{document.documentElement.dataset.theme=theme;},[theme]);
    function navigate(view,context){probe.nav.push({view,context});setContext(context||{});setView(view);}
    return React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls),React.createElement(WorkbenchNumberControls),React.createElement(WorkbenchGuardHost),
      React.createElement(AppShell,{active:'field',onNav:navigate,theme,onToggleTheme:()=>setTheme(value=>value==='light'?'dark':'light'),operations:true,showCapsule:false,title:'现场记录'},
        view==='field'?React.createElement(FieldWorkspace,{adapter:api,onNavigate:navigate,initialContext:context}):React.createElement('button',{id:'probe-return',onClick:()=>navigate('field',context)},'返回现场记录')));
  }
  mounted=ReactDOM.createRoot(document.getElementById('root'));mounted.render(React.createElement(Harness));
}
window.mountField=mountField;
mountField({theme:new URLSearchParams(location.search).get('theme')||'light',mock:new URLSearchParams(location.search).has('mock')});
`;
function createServer(upstream, report) {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
  const sources = files.map(file => ({path:'frontend/workbench/app/'+file,code:fs.readFileSync(path.join(root,'frontend/workbench/app',file),'utf8')}));
  const built = compile({babel_path:path.join(root,'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),sources,check_combined:true});
  report.sources = sources.map(item=>({path:item.path,sha256:crypto.createHash('sha256').update(item.code).digest('hex')}));
  for(const directory of ['core/services/workbench','web/routes/workbench','core/models','data/repositories','core/infrastructure']) {
    fs.readdirSync(path.join(root,directory)).filter(file=>/^(field_workspace|field_report_files|execution_ledger|production_report|workbench_execution|execution\.|execution_files)/.test(file)&&file.endsWith('.py')).forEach(file=>{
      const target=directory+'/'+file;report.sources.push({path:target,sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,target))).digest('hex')});
    });
  }
  report.compile={global_build:false,target:built.target};
  const assets = new Map();
  manifest.files.forEach(item=>assets.set('/static/'+item.path,{mime:item.mime,bytes:fs.readFileSync(path.join(root,'static',item.path))}));
  built.outputs.forEach((item,index)=>assets.set('/probe/'+files[index]+'.js',{mime:'application/javascript',bytes:item.code}));
  const styles=fs.readdirSync(path.join(root,'frontend/workbench/app/styles')).filter(file=>file.endsWith('.css')).sort();
  styles.forEach(file=>{const bytes=fs.readFileSync(path.join(root,'frontend/workbench/app/styles',file));assets.set('/probe/'+file,{mime:'text/css',bytes});report.sources.push({path:'frontend/workbench/app/styles/'+file,sha256:crypto.createHash('sha256').update(bytes).digest('hex')});});
  report.static_foundation_build_id=manifest.build_id;
  assets.set('/probe/harness.js',{mime:'application/javascript',bytes:script});
  const shared=manifest.scripts.filter(file=>file.startsWith('workbench/vendor/')||file.startsWith('workbench/assets/foundation-'));
  const html='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+manifest.styles.map(file=>'<link rel="stylesheet" href="/static/'+file+'">').concat(styles.map(file=>'<link rel="stylesheet" href="/probe/'+file+'">')).join('')+'</head><body class="aps-workbench"><div id="root"></div>'+shared.map(file=>'/static/'+file).concat(files.map(file=>'/probe/'+file+'.js'),['/probe/harness.js']).map(file=>'<script src="'+file+'"></script>').join('')+'</body></html>';
  return http.createServer((req,res)=>{
    if(req.url.startsWith('/api/')) {
      const proxied=http.request(upstream+req.url,{method:req.method,headers:{...req.headers,host:new URL(upstream).host}},reply=>{res.writeHead(reply.statusCode,reply.headers);reply.pipe(res);});
      req.pipe(proxied);proxied.on('error',error=>{res.writeHead(502);res.end(error.message);});return;
    }
    if(req.url==='/'||req.url.startsWith('/?')){res.setHeader('Content-Type','text/html;charset=utf-8');res.end(html);return;}
    if(req.url==='/favicon.ico'){res.writeHead(204);res.end();return;}
    const item=assets.get(req.url);if(item){res.setHeader('Content-Type',item.mime);res.end(item.bytes);}else{res.writeHead(404);res.end();}
  });
}
module.exports={root,createServer};
