/* Demo component fixtures. Synthetic production envelopes exercise write guards; no database is connected. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const output = process.argv[2];
if (!output) throw new Error('Pass an artifact directory');
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const names = ['WorkbenchGuards.js', 'WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchReferences.jsx', 'WorkbenchControlBridge.js',
  'resource-contract.js', 'resource-session.js', 'ResourceControls.jsx', 'WorkbenchControls.jsx', 'WorkbenchListControls.jsx', 'WorkbenchDetailPanel.jsx', 'WorkbenchGuardHost.jsx', 'ResourceForms.jsx',
  'ResourceMaterialContract.js', 'ResourceMaterialPreview.jsx', 'ResourceMaterialActions.jsx'];
const sources = names.map(name => ({path:'frontend/workbench/app/' + name,code:fs.readFileSync(path.join(root,'frontend/workbench/app',name),'utf8')}));
const compiled = compile({babel_path:path.join(root,'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),sources,check_combined:true});
const scripts = new Map(compiled.outputs.map((item,index)=>['/fixture/'+names[index]+'.js',item.code]));
const assets = new Map(manifest.files.map(item=>[item.path,item]));
const workbooks = JSON.parse(execFileSync(path.join(root,'.venv/bin/python'),['-B','-c',
  'import io,base64,json; from openpyxl import Workbook; w=Workbook(); w.active.append(["物料编号","名称","库存数量"]); t=io.BytesIO(); w.save(t); [w.active.append([str(i+1).zfill(4),"组件测试物料",8]) for i in range(2605)]; b=io.BytesIO(); w.save(b); print(json.dumps({"data":base64.b64encode(b.getvalue()).decode(),"template":base64.b64encode(t.getvalue()).decode()}))'],{env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},encoding:'utf8'}));
const fixtureCode = `
window.fixture={previews:[],commands:[],lookups:[],downloads:[],committed:[],closed:0,ready:false};
const token='Ab_-'.repeat(8), key='material-fixture-pending';
const ref=n=>n.toString(16).padStart(48,'0');
const envelope=(data,source)=>({ok:true,schema_version:1,data,meta:{source:source||'production',time_basis:'factory_local',snapshot_ref:token,request_ref:token,as_of:'2026-09-09T08:00:00'},warnings:[]});
function preview(spec,mode,format){
  const rows=Array.from({length:spec.rows||55},(_,i)=>{
    const before={business_code:'MAT-'+String(i+1).padStart(4,'0'),label:'物料 '+(i+1),spec:'精密零件毛坯 '+(i+1),unit:'件',stock_qty:i,status:'active',remark:'原备注完整保留，不能猜测其他来源',created_at:'2026-08-01 08:00:00'};
    const result=spec.rejectRow===i+1?'rejected':mode==='bulk'?'delete':i===0?'update':i%3===0?'unchanged':'new';
    return {row:i+1,business_code:before.business_code,entity_ref:ref(i+1),action:mode==='bulk'?'delete':result==='new'?'create':'update',result,
      before:result==='new'?null:before,after:mode==='bulk'?null:{...before,stock_qty:i+1,remark:'新备注：覆盖前必须逐项核对'},changes:result==='update'?{stock_qty:{before:i,after:i+1},remark:{before:before.remark,after:'新备注：覆盖前必须逐项核对'}}:{},
      errors:result==='rejected'?[{field:'stock_qty',message:'库存数量不是有效非负数；本行拒绝。'}]:[],requires_confirmation:mode==='import'&&i===0&&!spec.noConfirmation,reference_count:mode==='import'&&i===0?2:0};});
  const operation=mode==='bulk'?'material.bulk_delete':'material.import';
  const summary=Object.fromEntries(['new','update','unchanged','delete','rejected'].map(result=>[result,rows.filter(row=>row.result===result).length]));
  const data={preview_ref:token,expires_at:new Date(Date.now()+(spec.expired?-1000:900000)).toISOString(),operation,commit_policy:'atomic',summary,rows,can_confirm:!summary.rejected,
    write_context:{write_token:token,capabilities:{[operation]:spec.deny?false:!summary.rejected},blocked_reasons:[]}};
  if(mode==='import')Object.assign(data,{format:spec.wrongFormat?'xls':format,mode:'upsert',template_version:1,file_sha256:'a'.repeat(64)});
  if(spec.wrongRefs)data.rows[0].entity_ref=ref(999999);
  if(spec.malformed)data.summary.new++;
  return envelope(data,spec.source);
}
const receipt=spec=>({ok:true,result:'committed',replayed:false,receipt_ref:'demo-receipt',data:spec.mode==='bulk'?{deleted_count:spec.rows||55,rows:[]}:{rows:[],summary:{new:2,update:1,unchanged:0,delete:0,rejected:0}},warnings:[]});
let rendered;
function Harness({spec}){
  const adapter=React.useMemo(()=>({
    preview:async(path,body,signal)=>{fixture.previews.push({path,body:body instanceof FormData?{keys:Array.from(body.keys()),format:body.get('format'),mode:body.get('mode'),filename:body.get('file').name}:body});
      if(spec.delay)await new Promise(resolve=>setTimeout(resolve,spec.delay));
      if(signal.aborted)throw new DOMException('Aborted','AbortError');
      if(spec.previewError)throw {committed:false,error:{message:'当前列表快照已变化，请重读列表。',fields:[]}};
      if(path==='exports/material/preview')return envelope({export_ref:token,selection:body.selection,row_count:spec.wrongExportCount?2:body.selection==='selected'?body.refs.length:spec.rows||55,scope:body.scope,formats:['csv','xlsx'],expires_at:new Date(Date.now()+900000).toISOString()},spec.source);
      return preview(spec,spec.mode,body instanceof FormData?body.get('format'):null);
    },
    command:async(kind,action,ref,body)=>{fixture.commands.push({kind,action,ref,body});sessionStorage.setItem('fixture-command-count',String(Number(sessionStorage.getItem('fixture-command-count')||0)+1));
      if(spec.pending)return {ok:false,committed:'unknown',error:{message:'模拟连接中断',fields:[]}};
      if(spec.rejected)return {ok:false,committed:false,error:{message:'数据已变化，本批未写入。',fields:[]}};
      return receipt(spec);},
    lookup:async(request_key)=>{fixture.lookups.push(request_key);return fixture.ready?receipt(spec):{ok:true,state:'not_recorded',receipt:null,may_be_in_flight:true};},
    readPending:()=>{if(spec.unreadablePending)throw new Error('待核实记录无法读取。');const raw=sessionStorage.getItem(key);return raw?JSON.parse(raw):null;},
    savePending:intent=>sessionStorage.setItem(key,JSON.stringify({kind:intent.kind,action:intent.action,ref:intent.ref,request_key:intent.request_key})),
    clearPending:()=>sessionStorage.removeItem(key),
    download:async(path,scope)=>{fixture.downloads.push({path,scope});
      if(spec.badDownload)return {blob:new Blob(['<html>Error</html>']),contentType:'text/html',disposition:'attachment; filename="error.html"'};
      const template=path==='templates/material';
      const bytes=scope.format==='xlsx'?Uint8Array.from(atob(template?'${workbooks.template}':'${workbooks.data}'),c=>c.charCodeAt(0)):'\uFEFF物料编号,名称,库存数量\\r\\n'+(template?'':Array.from({length:spec.rows||55},(_,i)=>String(i+1).padStart(4,'0')+',组件测试物料,8\\r\\n').join(''));
      const filename=(path==='templates/material'?'物料导入模板':'物料完整导出')+'.'+scope.format;
      return {blob:new Blob([bytes]),contentType:scope.format==='csv'?'text/csv; charset=utf-8':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',disposition:"attachment; filename*=UTF-8''"+encodeURIComponent(filename)};
    }
  }),[]);
  const request=spec.recovery?{refs:[],scope:{},recovery:true}:{refs:Array.from({length:spec.selectionCount===undefined?(spec.rows||55):spec.selectionCount},(_,i)=>ref(i+1)),scope:{query:'当前页之外的选择',status:'active',sort:'business_code',direction:'desc',page:3,size:20,source:spec.source||'production',snapshot_ref:token}};
  return React.createElement(ResourceMaterialActions,{adapter,mode:spec.mode,request,onClose:()=>{fixture.closed++;rendered.unmount();},onCommitted:result=>fixture.committed.push(result)});
}
window.mountFixture=(spec,resume=false)=>{
  if(rendered)rendered.unmount();
  if(!resume){sessionStorage.removeItem(key);sessionStorage.setItem('fixture-command-count','0');}
  fixture.previews=[];fixture.commands=[];fixture.lookups=[];fixture.downloads=[];fixture.committed=[];fixture.closed=0;fixture.ready=false;
  sessionStorage.setItem('fixture-resume',JSON.stringify(spec));rendered=ReactDOM.createRoot(document.getElementById('fixture-root'));rendered.render(React.createElement(Harness,{spec}));
};
if(sessionStorage.getItem('fixture-resume'))mountFixture({...JSON.parse(sessionStorage.getItem('fixture-resume')),recovery:true},true);
`;
const html='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+
  '<link rel="icon" href="/static/'+manifest.icon+'"><script src="/static/'+manifest.theme_script+'"></script>'+manifest.styles.map(file=>'<link rel="stylesheet" href="/static/'+file+'">').join('')+
  '</head><body class="aps-workbench"><main style="padding:24px"><p>DEMO 组件测试 · 无数据库连接 · 无生产写入</p><div id="fixture-root"></div></main>'+
  manifest.scripts.filter(file=>file.startsWith('workbench/vendor/')||file.startsWith('workbench/assets/foundation-')).map(file=>'<script src="/static/'+file+'"></script>').join('')+
  Array.from(scripts.keys(),file=>'<script src="'+file+'"></script>').join('')+'<script>'+fixtureCode+'</script></body></html>';
const server=http.createServer((req,res)=>{
  const name=new URL(req.url,'http://fixture').pathname;
  if(name==='/'){res.setHeader('Content-Type','text/html;charset=utf-8');res.end(html);return;}
  if(scripts.has(name)){res.setHeader('Content-Type','application/javascript');res.end(scripts.get(name));return;}
  const asset=assets.get(name.slice('/static/'.length));
  if(!name.startsWith('/static/')||!asset){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',asset.mime);res.end(fs.readFileSync(path.join(root,'static',asset.path)));
});
const result={scope:'isolated-material-actions-components',data_source:'demo',simulates_production_envelopes:true,production_persistence_tested:false,
  sources:sources.map(item=>({path:item.path,sha256:crypto.createHash('sha256').update(item.code).digest('hex')})),cases:[],screenshots:[],errors:[],external:[]};
let page,variant;
async function mount(spec){await page.evaluate(spec=>mountFixture(spec),spec);await page.getByRole('dialog').waitFor();}
async function chooseCSV(){await page.getByRole('button',{name:'CSV (.csv)',exact:true}).click();await page.getByLabel('选择物料导入文件').setInputFiles({name:'材料.csv',mimeType:'text/csv',buffer:Buffer.from('物料编号,名称\n0001,材料\n')});}
async function preflight(){await page.getByRole('button',{name:'开始预检',exact:true}).click();await page.getByRole('heading',{name:'逐行预检',exact:true}).waitFor();}
async function shot(name){
  await page.evaluate(()=>document.fonts.ready);
  const geometry=await page.evaluate(()=>{const r=document.querySelector('[role=dialog]').getBoundingClientRect();return {width:innerWidth,height:innerHeight,scroll:document.documentElement.scrollWidth,dialog:{left:r.left,right:r.right,top:r.top,bottom:r.bottom},clipped:Array.from(document.querySelectorAll('.modal button,.rm-table th')).filter(el=>el.scrollWidth>el.clientWidth+1).map(el=>el.textContent)};});
  assert(geometry.scroll<=geometry.width+1);assert(geometry.dialog.left>=0&&geometry.dialog.right<=geometry.width+1&&geometry.dialog.top>=0&&geometry.dialog.bottom<=geometry.height+1);assert.deepEqual(geometry.clipped,[]);
  const filename=variant+'-'+name+'.png';await page.screenshot({path:path.join(output,filename)});result.screenshots.push({filename,geometry});
}
async function run(name,fn){try{await fn();result.cases.push({variant,name,passed:true});}catch(error){result.cases.push({variant,name,passed:false,error:error.message});await page.screenshot({path:path.join(output,variant+'-'+name+'-FAILED.png')});throw error;}}
async function download(button,name){const waiting=page.waitForEvent('download');await button.click();const file=await waiting;assert.equal(file.suggestedFilename(),name);const dest=path.join(output,variant+'-'+name);await file.saveAs(dest);assert.equal(await file.failure(),null);return dest;}
async function cases(){
  await run('no-automatic-preview-and-cancel',async()=>{await mount({mode:'import'});await chooseCSV();assert.equal(await page.evaluate(()=>fixture.previews.length),0);await shot('import-select');await page.getByRole('button',{name:'取消',exact:true}).click();assert.equal(await page.evaluate(()=>fixture.commands.length+fixture.committed.length),0);});
  await run('file-extension-content-validation',async()=>{await mount({mode:'import'});await page.getByLabel('选择物料导入文件').setInputFiles({name:'renamed.xlsx',mimeType:'application/octet-stream',buffer:Buffer.from('not an xlsx')});await page.getByRole('button',{name:'开始预检',exact:true}).click();await page.getByText('文件内容不是 XLSX 工作簿，请勿只修改扩展名。',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>fixture.previews.length),0);await chooseCSV();await page.getByRole('button',{name:'Excel (.xlsx)',exact:true}).click();await page.getByRole('button',{name:'开始预检',exact:true}).click();await page.getByText('请选择与文件格式一致的 .csv 或 .xlsx 文件。',{exact:true}).waitFor();});
  await run('full-preview-errors-pagination-atomic-guard',async()=>{
    await mount({mode:'import',rows:55,rejectRow:22});await chooseCSV();await preflight();
    assert.equal(await page.locator('tr[data-material-row]').count(),20);assert(await page.getByText('共 55 行 · 第 1 / 3 页',{exact:true}).isVisible());
    await page.getByRole('button',{name:'预检下一页',exact:true}).click();await page.locator('tr[data-material-row="22"]').waitFor();assert(await page.getByText(/库存数量不是有效非负数/).isVisible());
    await page.getByLabel('预检明细筛选').selectOption('rejected');assert.equal(await page.locator('tr[data-material-row]').count(),1);
    assert(await page.getByRole('button',{name:/^确认导入/}).isDisabled());await shot('import-errors');
    const body=await page.evaluate(()=>fixture.previews[0].body);assert.deepEqual(body,{keys:['file','format','mode'],format:'csv',mode:'upsert',filename:'材料.csv'});
    await page.getByRole('button',{name:'取消',exact:true}).click();assert.equal(await page.evaluate(()=>fixture.commands.length),0);
  });
  await run('referenced-import-explicit-confirm-and-callback',async()=>{
    await mount({mode:'import',rows:25});await chooseCSV();await preflight();assert(await page.getByRole('button',{name:/^确认导入/}).isDisabled());
    await page.getByLabel('预检明细筛选').selectOption('confirmation');assert.equal(await page.locator('tr[data-material-row]').count(),1);
    assert(await page.getByText('原备注完整保留，不能猜测其他来源',{exact:true}).isVisible());assert(await page.getByText('新备注：覆盖前必须逐项核对',{exact:true}).isVisible());
    await page.getByRole('checkbox',{name:'已核对被引用物料的修改前后内容，确认这些更新。',exact:true}).check();assert(await page.getByRole('button',{name:'确认导入',exact:true}).isEnabled());await shot('import-confirm');
    await page.getByRole('button',{name:'确认导入',exact:true}).click();await page.waitForFunction(()=>fixture.committed.length===1);
    const call=await page.evaluate(()=>fixture.commands[0]);assert.equal(call.kind,'material_import');assert.equal(call.action,'confirm');assert.equal(call.ref,'Ab_-'.repeat(8));assert.deepEqual(call.body.input,{preview_ref:call.ref});assert.equal(call.body.write_token,call.ref);
    await page.getByRole('button',{name:'完成',exact:true}).click();assert.equal(await page.evaluate(()=>sessionStorage.getItem('material-fixture-pending')),null);
  });
  await run('hidden-bulk-selection-over-2000',async()=>{
    await mount({mode:'bulk',rows:2605});await preflight();assert.equal(await page.locator('tr[data-material-row]').count(),20);
    const body=await page.evaluate(()=>fixture.previews[0].body);assert.equal(body.refs.length,2605);assert.equal(body.refs[2604],(2605).toString(16).padStart(48,'0'));assert.deepEqual(body.scope,{query:'当前页之外的选择',status:'active',sort:'business_code',direction:'desc'});assert.equal(body.page_size,20);assert(!('page' in body.scope));
    await page.getByLabel('预检每页行数').selectOption('100');assert.equal(await page.locator('tr[data-material-row]').count(),100);await page.getByLabel('预检每页行数').selectOption('20');
    await page.getByRole('checkbox',{name:'已核对完整删除范围及明细，确认删除这些物料。',exact:true}).check();await shot('bulk-delete');await page.getByRole('button',{name:'确认删除',exact:true}).click();await page.waitForFunction(()=>fixture.committed.length===1);assert.equal(await page.evaluate(()=>fixture.commands[0].kind),'material_bulk');
  });
  await run('unknown-lock-remount-restart-original-key',async()=>{
    await mount({mode:'bulk',rows:2,pending:true});await preflight();await page.getByRole('checkbox').check();await page.getByRole('button',{name:'确认删除',exact:true}).click();await page.getByRole('button',{name:'查询原请求回执',exact:true}).waitFor();
    assert(await page.getByRole('button',{name:/^取消/}).isDisabled());await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>fixture.closed),0);assert.equal(await page.getByRole('button',{name:'开始预检',exact:true}).count(),0);
    const intent=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('material-fixture-pending')));assert(!('input' in intent));assert(!('write_token' in intent));
    await page.reload();await page.getByRole('button',{name:'查询原请求回执',exact:true}).waitFor();assert.equal(await page.evaluate(()=>fixture.commands.length),0);assert.equal(await page.evaluate(()=>fixture.lookups[0]),intent.request_key);assert.equal(await page.evaluate(()=>sessionStorage.getItem('fixture-command-count')),'1');
    assert.equal(await page.getByText(/本次明确选中/).count(),0);assert.equal(await page.getByText(/当前为示例数据/).count(),0);assert.equal(await page.getByText(/尚未读取生产资料/).count(),0);assert.equal(await page.locator('[role="dialog"] input').count(),0);
    await shot('pending-recovered');await page.evaluate(()=>{fixture.ready=true;});await page.getByRole('button',{name:'查询原请求回执',exact:true}).click();await page.waitForFunction(()=>fixture.committed.length===1);assert.equal(await page.evaluate(()=>fixture.commands.length),0);await page.getByRole('button',{name:'完成',exact:true}).click();
  });
  await run('import-recovery-only-receipt-no-file-source-guess',async()=>{
    await mount({mode:'import',rows:2,pending:true});await chooseCSV();await preflight();await page.getByRole('checkbox').check();await page.getByRole('button',{name:'确认导入',exact:true}).click();await page.getByRole('button',{name:'查询原请求回执',exact:true}).waitFor();
    const key=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('material-fixture-pending')).request_key);await page.reload();await page.getByRole('button',{name:'查询原请求回执',exact:true}).waitFor();assert.equal(await page.locator('[role="dialog"] input').count(),0);assert.equal(await page.getByText(/当前为示例数据/).count(),0);assert.equal(await page.evaluate(()=>fixture.previews.length),0);assert.equal(await page.evaluate(()=>fixture.lookups[0]),key);
    await page.evaluate(()=>{fixture.ready=true;});await page.getByRole('button',{name:'查询原请求回执',exact:true}).click();await page.waitForFunction(()=>fixture.committed.length===1);await page.getByRole('button',{name:'完成',exact:true}).click();assert.equal(await page.evaluate(()=>sessionStorage.getItem('material-fixture-pending')),null);
  });
  await run('missing-or-unreadable-recovery-not-an-edit-form',async()=>{
    await mount({mode:'import',recovery:true});await page.getByText('未读到原请求标识；未执行其他物料操作。',{exact:true}).waitFor();assert.equal(await page.locator('[role="dialog"] input').count(),0);assert.equal(await page.getByRole('button',{name:'开始预检',exact:true}).count(),0);await page.getByRole('button',{name:'取消',exact:true}).click();
    await mount({mode:'import',recovery:true,unreadablePending:true});await page.getByText('待核实记录无法读取。',{exact:true}).waitFor();assert.equal(await page.locator('[role="dialog"] input').count(),0);assert(await page.getByRole('button',{name:/^取消/}).isDisabled());assert.equal(await page.evaluate(()=>fixture.previews.length+fixture.commands.length),0);
  });
  await run('stale-refusal-no-automatic-retry',async()=>{await mount({mode:'bulk',rows:2,rejected:true});await preflight();await page.getByRole('checkbox').check();await page.getByRole('button',{name:'确认删除',exact:true}).click();await page.getByText('数据已变化，本批未写入。',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>fixture.commands.length),1);assert.equal(await page.evaluate(()=>fixture.previews.length),1);assert.equal(await page.evaluate(()=>fixture.committed.length),0);assert(await page.getByRole('button',{name:/^确认删除/}).isDisabled());});
  await run('demo-write-guard',async()=>{await mount({mode:'bulk',rows:2,source:'demo'});await preflight();await page.getByRole('checkbox').check();assert(await page.getByRole('button',{name:/^确认删除/}).isDisabled());assert.equal(await page.evaluate(()=>fixture.commands.length),0);});
  await run('malformed-expired-and-capability-guards',async()=>{
    await mount({mode:'bulk',rows:2,malformed:true});await page.getByRole('button',{name:'开始预检',exact:true}).click();await page.getByText('预检统计与明细不一致，本批未提交。',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:/^确认删除/}).count(),0);
    for(const constraint of [{expired:true},{deny:true}]){await mount({mode:'bulk',rows:2,...constraint});await preflight();await page.getByRole('checkbox').check();assert(await page.getByRole('button',{name:/^确认删除/}).isDisabled());}
  });
  await run('preview-selection-and-format-mismatch-guards',async()=>{
    await mount({mode:'bulk',rows:2,wrongRefs:true});await page.getByRole('button',{name:'开始预检',exact:true}).click();await page.getByText('删除预览与明确选中的物料不一致，本批未提交。',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:/^确认删除/}).count(),0);
    await mount({mode:'import',rows:2,wrongFormat:true});await chooseCSV();await page.getByRole('button',{name:'开始预检',exact:true}).click();await page.getByText('导入预览的文件格式或增量模式不一致，本批未提交。',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:/^确认导入/}).count(),0);
  });
  await run('empty-selection-no-bulk-write-explicit-empty-export',async()=>{
    await mount({mode:'bulk',selectionCount:0});await page.getByRole('button',{name:'开始预检',exact:true}).click();await page.getByText('未选中物料，本次不会删除任何记录。',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>fixture.previews.length),0);
    await mount({mode:'export',rows:2,selectionCount:0});await page.getByRole('radio',{name:/已选物料/}).check();await page.getByRole('button',{name:'开始预检',exact:true}).click();await page.getByText('0',{exact:true}).waitFor();assert.deepEqual(await page.evaluate(()=>fixture.previews[0].body.refs),[]);assert.equal(await page.evaluate(()=>fixture.commands.length+fixture.committed.length),0);
    await mount({mode:'export',rows:2,selectionCount:0,wrongExportCount:true});await page.getByRole('radio',{name:/已选物料/}).check();await page.getByRole('button',{name:'开始预检',exact:true}).click();await page.getByText('导出预览数量与明确选中的物料不一致，未开始下载。',{exact:true}).waitFor();
  });
  await run('download-filename-and-cancel-before-save',async()=>{
    const facts=await page.evaluate(async()=>{
      const M=APSResourceMaterial;let bad=false,cancelled=false;
      try{M.filename('attachment; filename="wrong.xlsx"','csv');}catch(_){bad=true;}
      const controller=new AbortController(),blob=new Blob(['csv']);
      blob.slice=()=>({arrayBuffer:async()=>{controller.abort();return new ArrayBuffer(4);}});
      try{await M.saveDownload({blob,contentType:'text/csv',disposition:'attachment; filename="cancelled.csv"'},'csv',controller.signal);}catch(error){cancelled=error.name==='AbortError';}
      return {name:M.filename('attachment; filename="material.csv"','csv'),bad,cancelled};
    });assert.deepEqual(facts,{name:'material.csv',bad:true,cancelled:true});
  });
  await run('export-ranges-full-downloads-no-write-receipt',async()=>{
    await mount({mode:'export',rows:2605});assert.equal(await page.evaluate(()=>fixture.previews.length),0);assert.equal(await page.getByRole('button',{name:'下载文件',exact:true}).count(),0);
    await page.getByRole('radio',{name:/已选物料/}).check();await page.getByRole('button',{name:'CSV (.csv)',exact:true}).click();await page.getByRole('button',{name:'开始预检',exact:true}).click();await page.getByText('2605',{exact:true}).waitFor();
    const body=await page.evaluate(()=>fixture.previews[0].body);assert.equal(body.selection,'selected');assert.equal(body.refs.length,2605);await shot('export-selected');
    const csv=await download(page.getByRole('button',{name:'下载文件',exact:true}),'物料完整导出.csv');const csvText=fs.readFileSync(csv,'utf8');assert(csvText.includes('0001,组件测试物料,8'));assert.equal(csvText.trim().split('\r\n').length,2606);assert.equal(await page.evaluate(()=>fixture.commands.length+fixture.committed.length),0);
    await page.getByRole('radio',{name:/全部物料/}).check();assert.equal(await page.getByRole('button',{name:'下载文件',exact:true}).count(),0);await page.getByRole('button',{name:'Excel (.xlsx)',exact:true}).click();await page.getByRole('button',{name:'开始预检',exact:true}).click();await page.getByText('2605',{exact:true}).waitFor();
    const all=await page.evaluate(()=>fixture.previews[1].body);assert.equal(all.selection,'all');assert(!('refs' in all));
    const xlsx=await download(page.getByRole('button',{name:'下载文件',exact:true}),'物料完整导出.xlsx');const contents=execFileSync(path.join(root,'.venv/bin/python'),['-B','-c','import sys;from openpyxl import load_workbook;w=load_workbook(sys.argv[1],read_only=True);print(w.active["A2"].value,w.active.max_row);w.close()',xlsx],{encoding:'utf8'});assert.equal(contents.trim(),'0001 2606');
    await page.getByRole('radio',{name:/当前筛选结果/}).check();await page.getByRole('button',{name:'开始预检',exact:true}).click();await page.getByText('2605',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>fixture.previews[2].body.selection),'filtered');
  });
  await run('templates-and-error-downloads',async()=>{
    await mount({mode:'import'});await page.getByRole('button',{name:'CSV (.csv)',exact:true}).click();const template=await download(page.getByRole('button',{name:'下载模板',exact:true}),'物料导入模板.csv');assert.equal(fs.readFileSync(template,'utf8').trim().split('\r\n').length,1);assert.deepEqual(await page.evaluate(()=>fixture.downloads[0]),{path:'templates/material',scope:{format:'csv'}});assert.equal(await page.evaluate(()=>fixture.previews.length+fixture.commands.length+fixture.committed.length),0);
    await mount({mode:'import',badDownload:true});await page.getByRole('button',{name:'下载模板',exact:true}).click();await page.getByText('下载内容或文件类型不正确，未把错误响应保存为文件。',{exact:true}).waitFor();assert.equal(await page.getByText(/已交给浏览器下载/).count(),0);
  });
  await run('cancel-pending-read-does-not-write',async()=>{await mount({mode:'bulk',rows:2,delay:400});await page.getByRole('button',{name:'开始预检',exact:true}).click();await page.getByText('正在读取完整预检结果，尚未写入数据…',{exact:true}).waitFor();await page.getByRole('button',{name:'取消',exact:true}).click();assert.equal(await page.evaluate(()=>fixture.commands.length+fixture.committed.length),0);});
}
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
  try{
    browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-background-networking']});assert(browser.version().startsWith('109.'),'Actual Chromium109 required');result.browser=browser.version();
    const origin='http://127.0.0.1:'+server.address().port;
    for(const viewport of [{width:1920,height:1080},{width:1392,height:924}])for(const theme of ['light','dark']){
      variant=viewport.width+'x'+viewport.height+'-'+theme;const context=await browser.newContext({viewport,acceptDownloads:true});await context.addInitScript(theme=>{localStorage.setItem('aps_theme',theme);localStorage.setItem('aps_kit_theme',theme);},theme);page=await context.newPage();
      page.on('pageerror',error=>result.errors.push(error.message));page.on('console',message=>{if(message.type()==='error')result.errors.push(message.text());});
      await page.route('**/*',route=>{if(!route.request().url().startsWith(origin+'/')){result.external.push(route.request().url());return route.abort();}return route.continue();});
      await page.goto(origin);await cases();await context.close();
    }
    assert.deepEqual(result.errors,[]);assert.deepEqual(result.external,[]);
  }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));fs.writeFileSync(path.join(output,'material-actions-result.json'),JSON.stringify(result,null,2)+'\n');}
  console.log(JSON.stringify({output,browser:result.browser,cases:result.cases.length,screenshots:result.screenshots.length,errors:result.errors,scope:result.scope}));
})().catch(error=>{console.error(error);process.exitCode=1;});
