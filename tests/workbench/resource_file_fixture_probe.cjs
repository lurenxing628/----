/* Component mock only. No Flask or database is connected. */
'use strict';
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
function fixture() {
  const names = ['resource-contract.js', 'resource-api.js', 'resource-session.js', 'ResourceControls.jsx', 'ResourceForms.jsx',
    'ResourceMaterialContract.js', 'ResourceFileContract.js', 'ResourceMaterialPreview.jsx', 'ResourceMaterialActions.jsx', 'ResourceFileActions.jsx',
    'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchControls.jsx'];
  const sources = names.map(name => ({path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8')}));
  const compiled = compile({babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true});
  const scripts = new Map(compiled.outputs.map((item, index) => ['/fixture/' + names[index] + '.js', item.code]));
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
  const assets = new Map(manifest.files.map(item => [item.path, item]));
  const workbook = execFileSync(path.join(root, '.venv/bin/python'), ['-B', '-c',
    'import io,base64;from openpyxl import Workbook;w=Workbook();w.active.append(["编号","名称"]);b=io.BytesIO();w.save(b);print(base64.b64encode(b.getvalue()).decode())'], {encoding: 'utf8'}).trim();
  const code = `
window.fixture={previews:[],commands:[],downloads:[],lookups:[],committed:[],closed:0,ready:false,aborted:0};
const token='Ab_-'.repeat(8),ref=n=>n.toString(16).padStart(48,'0');
const pendingKey=kind=>'aps_workbench_resource_pending_v1_'+kind+'_files';
const envelope=(data,source='production')=>({ok:true,schema_version:1,data,meta:{source,time_basis:'factory_local',snapshot_ref:token,request_ref:token,as_of:'2026-09-09T08:00:00'},warnings:[]});
const common={business_code:'编号',label:'名称',status:'状态',category:'归属或设备分类',remark:'备注',created_at:'创建时间（只读）'};
const fields={op_type:{default_merge_mode:'默认周期策略'},machine:{op_type_code:'自制工种编号',group_code:'设备组编号',machine_authorizations:'原设备授权（只读）'},operator:{skill_codes:'技能工种编号数组',shift_profile_code:'班次编号',skill_details:'原技能明细（只读）'},supplier:{op_type_codes:'外协工种编号数组',default_days:'默认周期'}};
function preview(spec,mode,format){
  const relation={op_type:{category:spec.category,default_merge_mode:spec.category==='external'?'merged':null},machine:{category:'原设备分类',op_type_code:'OT-0001',group_code:'G-0001',machine_authorizations:[{machine_code:'M-0001',operator_code:'O-0001',skill_level:'legacy-grade',is_primary:'no',created_at:'原授权时间'}]},operator:{skill_codes:['OT-0001','OT-0002'],shift_profile_code:'SHIFT-0001',skill_details:[{op_type_code:'OT-0001',skill_level:'normal',is_primary:'yes',created_at:'原技能时间'}]},supplier:{op_type_codes:['OUT-0001','OUT-0002'],default_days:3}}[spec.kind];
  const rows=Array.from({length:spec.rows||55},(_,i)=>{
    const before={business_code:'CODE-'+String(i+1).padStart(4,'0'),label:'原名称 '+(i+1),status:'active',remark:'原事实完整保留',created_at:'2026-08-01 08:00:00',...relation};
    const result=spec.rejectRow===i+1?'rejected':mode==='bulk'?'delete':i===0?'update':i%3===0?'unchanged':'new';
    return {row:i+2,business_code:before.business_code,entity_ref:ref(i+1),action:mode==='bulk'?'delete':result==='new'?'create':'update',result,
      before:result==='new'?null:before,after:mode==='bulk'?null:{...before,label:'修改后名称 '+(i+1)},changes:result==='update'?{label:{before:before.label,after:'修改后名称 '+(i+1)}}:{},
      errors:result==='rejected'?[{field:'business_code',message:'关系业务编号不属于当前工种类别；本行拒绝。'}]:[],requires_confirmation:mode==='import'&&i===0&&!spec.noAck,reference_count:mode==='import'&&i===0?2:0};
  });
  const operation=spec.kind+(mode==='bulk'?'.bulk_delete':'.import'),summary=Object.fromEntries(['new','update','unchanged','delete','rejected'].map(k=>[k,rows.filter(r=>r.result===k).length]));
  const data={preview_ref:token,expires_at:new Date(Date.now()+(spec.expired?-1000:900000)).toISOString(),operation,commit_policy:'atomic',summary,rows,can_confirm:!summary.rejected,
    scope:spec.kind==='op_type'?{category:spec.wrongCategory?(spec.category==='internal'?'external':'internal'):spec.category}:{},
    columns:Object.entries({...common,...fields[spec.kind]}).map(([key,label])=>({key,label})),write_context:{write_token:token,capabilities:{[operation]:!spec.deny},blocked_reasons:[]}};
  if(mode==='import')Object.assign(data,{format:spec.wrongFormat?'xls':format,mode:'upsert',template_version:1,file_sha256:'a'.repeat(64)});
  if(spec.malformed)data.summary.new++;
  if(spec.wrongRefs)rows[0].entity_ref=ref(999999);
  if(spec.missingColumns)delete data.columns;
  if(spec.privateFacts)rows[0].before.entity_key='private-entity-key';
  if(spec.nestedFacts)rows[0].before.label={entity_key:'private-entity-key'};
  return envelope(data,spec.source);
}
const receipt=spec=>({ok:true,result:'committed',replayed:false,receipt_ref:'mock-receipt',data:spec.mode==='bulk'?{deleted_count:spec.rows||55}:{summary:{new:1,update:1,unchanged:0,delete:0,rejected:0}},warnings:[]});
let rendered,knownAdapters=new Map();
function adapterFor(spec){
  if(knownAdapters.has(spec.kind))return knownAdapters.get(spec.kind);
  const adapter=APSResourceAPI.create(spec.kind+'_files');
  adapter.preview=async(path,body,signal)=>{
    fixture.previews.push({path,body:body instanceof FormData?{keys:Array.from(body.keys()),category:body.get('category'),format:body.get('format'),mode:body.get('mode'),filename:body.get('file').name}:body});
    if(spec.delay)await new Promise(resolve=>{const timer=setTimeout(resolve,spec.delay);signal.addEventListener('abort',()=>{fixture.aborted++;clearTimeout(timer);resolve();},{once:true});});
    if(signal.aborted)throw new DOMException('Aborted','AbortError');
    if(spec.previewError)throw {committed:false,error:{message:'列表快照已变化，请重读列表。',fields:[]}};
    if(path.startsWith('exports/'))return envelope({export_ref:token,selection:body.selection,row_count:spec.wrongCount?999:body.selection==='selected'?body.refs.length:spec.rows||55,scope:{...body.scope,...(spec.wrongCategory?{category:'wrong'}:{})},formats:['csv','xlsx'],expires_at:new Date(Date.now()+900000).toISOString()},spec.source);
    return preview(spec,spec.mode,body instanceof FormData?body.get('format'):null);
  };
  adapter.command=async(kind,action,ref,body)=>{
    fixture.commands.push({kind,action,ref,body});sessionStorage.setItem('fixture-command-count',String(Number(sessionStorage.getItem('fixture-command-count')||0)+1));
    if(spec.pending)return {ok:false,committed:'unknown',error:{message:'组件模拟连接中断',fields:[]}};
    if(spec.malformedReceipt)return {ok:true,result:'committed',data:{}};
    if(spec.rejected)return {ok:false,committed:false,error:{message:'数据已变化，本批未写入。',fields:[]}};
    return receipt(spec);
  };
  adapter.lookup=async key=>{fixture.lookups.push(key);return fixture.ready?receipt(spec):{ok:true,state:'not_recorded',receipt:null,may_be_in_flight:true};};
  adapter.download=async(path,scope,signal)=>{
    fixture.downloads.push({path,scope});
    if(spec.downloadDelay)await new Promise(resolve=>{const timer=setTimeout(resolve,500);signal.addEventListener('abort',()=>{fixture.aborted++;clearTimeout(timer);resolve();},{once:true});});
    if(spec.badDownload)return {blob:new Blob(['<html>Error</html>']),contentType:'text/html',disposition:'attachment; filename="error.html"'};
    const template=path.startsWith('templates/'),name=spec.kind+(template?'-template':'-export')+'.'+scope.format;
    const bytes=scope.format==='xlsx'?Uint8Array.from(atob('${workbook}'),c=>c.charCodeAt(0)):'\\uFEFF编号,名称\\r\\n'+(template?'':Array.from({length:spec.rows||55},(_,i)=>String(i+1).padStart(4,'0')+',组件模拟记录\\r\\n').join(''));
    return {blob:new Blob([bytes]),contentType:scope.format==='csv'?'text/csv; charset=utf-8':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',disposition:spec.badFilename?'attachment; filename="wrong.exe"':'attachment; filename="'+name+'"'};
  };
  knownAdapters.set(spec.kind,adapter);return adapter;
}
function Harness({spec}){
  const request=spec.recovery?{refs:[],scope:{},recovery:true}:{refs:Array.from({length:spec.selectionCount===undefined?(spec.rows||55):spec.selectionCount},(_,i)=>ref(i+1)),scope:{query:'跨页查询',status:'active',sort:'business_code',direction:'desc',page:3,size:20,source:spec.source||'production',snapshot_ref:token,...(spec.kind==='op_type'?{category:spec.category}:{})}};
  fixture.request=request;
  return React.createElement(ResourceFileActions,{kind:spec.kind,mode:spec.mode,request,adapter:adapterFor(spec),onClose:()=>{fixture.closed++;rendered.unmount();},onCommitted:r=>fixture.committed.push(r)});
}
window.mountFixture=(spec,resume=false)=>{
  if(rendered)rendered.unmount();
  if(!resume){knownAdapters=new Map();for(const kind of ['op_type','machine','operator','supplier'])sessionStorage.removeItem(pendingKey(kind));sessionStorage.setItem('fixture-command-count','0');}
  Object.assign(fixture,{previews:[],commands:[],downloads:[],lookups:[],committed:[],closed:0,ready:false,aborted:0});
  sessionStorage.setItem('fixture-resume',JSON.stringify(spec));rendered=ReactDOM.createRoot(document.getElementById('fixture-root'));rendered.render(React.createElement(Harness,{spec}));
};
ReactDOM.createRoot(document.getElementById('controls-root')).render(React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls)));
if(sessionStorage.getItem('fixture-resume'))mountFixture({...JSON.parse(sessionStorage.getItem('fixture-resume')),recovery:true},true);
`;
  const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<link rel="icon" href="/static/' + manifest.icon + '"><script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
    '</head><body class="aps-workbench"><main style="padding:24px"><p>组件 MOCK 证据 · 无数据库连接 · 不证明生产持久化</p><div id="fixture-root"></div><div id="controls-root"></div></main>' +
    manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-')).map(file => '<script src="/static/' + file + '"></script>').join('') +
    Array.from(scripts.keys(), file => '<script src="' + file + '"></script>').join('') + '<script>' + code + '</script></body></html>';
  const server = http.createServer((req,res) => {
    const name = new URL(req.url, 'http://fixture').pathname;
    if (name === '/') {res.setHeader('Content-Type','text/html;charset=utf-8');res.end(html);return;}
    if (scripts.has(name)) {res.setHeader('Content-Type','application/javascript');res.end(scripts.get(name));return;}
    const asset = assets.get(name.slice('/static/'.length));
    if (!name.startsWith('/static/') || !asset) {res.writeHead(404);res.end();return;}
    res.setHeader('Content-Type',asset.mime);res.end(fs.readFileSync(path.join(root,'static',asset.path)));
  });
  return {server,sources,workbook};
}
module.exports = {fixture,root};
