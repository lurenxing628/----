/* Isolated current-source components with simulated receipts; no HTTP/database persistence proof. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto');
const {chromium}=require('playwright'),{compile}=require('../../scripts/workbench/compile.cjs');
const root=path.resolve(__dirname,'../..'),output=process.argv[2];
if(!output)throw new Error('Pass an output directory');fs.mkdirSync(output,{recursive:true});
const manifest=JSON.parse(fs.readFileSync(path.join(root,'static/workbench/asset-manifest.json')));
const names=['resource-contract.js','resource-session.js','CalendarContract.js','WorkbenchFormat.js','WorkbenchTerms.js','WorkbenchReferences.jsx','WorkbenchGuards.js','ResourceControls.jsx', 'WorkbenchGuardHost.jsx','WorkbenchControlBridge.js', 'WorkbenchControls.jsx','WorkbenchListControls.jsx','ResourceDetailRelations.jsx','ResourceForms.jsx',
  'WorkbenchControlStyles.jsx','WorkbenchDatePickerModel.js','WorkbenchDatePicker.jsx','WorkbenchSelectMenu.jsx','WorkbenchNumberControls.jsx'];
const sources=names.map(name=>({path:'frontend/workbench/app/'+name,code:fs.readFileSync(path.join(root,'frontend/workbench/app',name),'utf8')}));
const compiled=compile({babel_path:path.join(root,'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),sources,check_combined:true}).outputs.map(row=>row.code).join('\n;\n');
const assets=new Map(manifest.files.map(item=>[item.path,item]));
const sharedStyles=fs.readdirSync(path.join(root,'frontend/workbench/app/styles')).filter(name=>/^(00|20|21|22)-/.test(name))
  .map(name=>({path:'frontend/workbench/app/styles/'+name,code:fs.readFileSync(path.join(root,'frontend/workbench/app/styles',name),'utf8')}));
const fixture=`
const h=React.createElement;let fixtureRoot;
window.stockFixture={calls:[],closed:0,adjusted:0,serial:0};
const ref=n=>n.toString(16).padStart(48,'0');
function context(kind,token,allowed=true){return {write_token:token,capabilities:{[kind+'.update']:allowed,[kind+'.delete']:false,[kind+'.create']:allowed},blocked_reasons:[]};}
function envelope(data,source='production'){return {ok:true,schema_version:1,data,meta:{source,time_basis:'factory_local',snapshot_ref:'stock-snapshot',request_ref:'stock-query',as_of:'2026-09-09T18:00:00'},warnings:[]};}
function record(kind,spec={}){return {kind,ref:ref(1),business_code:'MAT-001',label:spec.long?'高强度圆钢毛坯用于大型轴承零件'.repeat(7):'45号钢',status:kind==='op_type'?null:'active',
  fields:{spec:'原规格',stock_qty:8.375,unit:'kg',remark:'不可覆盖的原备注',hidden_legacy:'legacy-exact',...spec.fields},relationships:{},issues:[],write_context:context(kind,'initial-token',spec.allowed!==false)};}
function FormHarness({spec}){
  const kind=spec.kind||'material',original=React.useMemo(()=>record(kind,spec),[]);
  const [mode,setMode]=React.useState(spec.detail?'detail':spec.normal?'normal':'stock'),[visible,setVisible]=React.useState(false);
  const [write,setWrite]=React.useState(original.write_context),[review,setReview]=React.useState(null),[accepted,setAccepted]=React.useState(null),[refreshed,setRefreshed]=React.useState({});
  const adapter=React.useMemo(()=>({
    command:async(kind,action,ref,body)=>{stockFixture.calls.push({kind,action,ref,body});
      if(spec.behavior==='stale'&&stockFixture.calls.length===1)return {ok:false,committed:false,error:{code:'stale_write',message:'资料已变化，请重新读取并核对。',fields:[]}};
      if(spec.behavior==='pending')await new Promise(resolve=>{stockFixture.resolve=resolve;});
      return {ok:true,result:Object.keys(body.input).length?'committed':'unchanged',receipt_ref:'stock-receipt',replayed:false,data:{entity_ref:original.ref},warnings:[]};},
    relations:async(parent,scope)=>envelope({parent_ref:parent,parent_kind:'op_type',relation:scope.relation,basis:{code:'recorded',message:'真实关联口径的隔离夹具'},entities:[],page:{number:scope.page,size:scope.size,total:0,pages:1,sort:[{field:'business_code',direction:'asc'}]}})
  }),[]);
  const command=APSResourceSession.useCommand(adapter);
  React.useEffect(()=>{if(command.phase==='done')setRefreshed({done:true});},[command.phase]);
  function close(){stockFixture.closed++;setVisible(false);}
  stockFixture.switchStock=()=>setMode('stock');stockFixture.original=original;
  return h(React.Fragment,null,h('button',{id:'fixture-trigger',className:'btn',onClick:()=>setVisible(true)},'打开资源'),visible&&(
    mode==='detail'?h(ResourceForms.Detail,{adapter,kind,result:envelope(original,spec.source||'production'),onClose:close,onEdit:()=>setMode('normal'),onDelete:()=>{},
      onAdjustStock:spec.noAdjust?undefined:()=>{stockFixture.adjusted++;setMode('stock');}}):
    h(ResourceForms,{adapter,kind,action:spec.action||'update',entity:original,acceptedEntity:accepted,writeContext:write,source:spec.source||'production',command,stockOnly:mode==='stock',onClose:close,
      refreshState:refreshed,onRefresh:()=>setRefreshed({done:true}),contextReview:review,onReloadContext:()=>setReview(envelope({...original,label:'服务端新名称',fields:{...original.fields,stock_qty:18.625,unit:'件'},write_context:context(kind,'reviewed-token')})),
      onAcceptContext:()=>{setWrite(review.data.write_context);setAccepted(review.data);setReview(null);}})));
}
function OverlayHarness(){
  const [visible,setVisible]=React.useState(false),[locked,setLocked]=React.useState(false),[suspended,setSuspended]=React.useState(false),[filter,setFilter]=React.useState(false);
  const trigger=React.useRef(null),filterInput=React.useRef(null);
  stockFixture.setLocked=setLocked;stockFixture.setSuspended=setSuspended;
  React.useEffect(()=>{if(filter&&filterInput.current)filterInput.current.focus();},[filter]);
  function closeFilter(){setFilter(false);trigger.current.focus();}
  return h(React.Fragment,null,h('button',{id:'fixture-trigger',className:'btn',onClick:()=>setVisible(true)},'打开主窗口'),visible&&
    h(ResourceControls.Modal,{title:'主窗口',onClose:()=>{stockFixture.closed++;if(!stockFixture.keepOpen)setVisible(false);},locked,suspended,
      footer:h(ResourceControls.Button,{onClick:()=>{stockFixture.closed++;setVisible(false);},disabled:locked},'取消')},
      h('div',{className:'modal-b form'},h('label',null,'对话框内容',h('input',{'aria-label':'对话框内容',defaultValue:'可选中的内容'})),
        h('label',null,'日期',h('input',{type:'date','aria-label':'测试日期',defaultValue:'2026-09-09'})),
        h('label',null,'状态',h('select',{'aria-label':'测试状态',defaultValue:'active'},h('option',{value:'active'},'启用'),h('option',{value:'inactive'},'停用'))),
        h('button',{className:'btn',type:'button',ref:trigger,onClick:()=>setFilter(true)},'打开列筛选'),
        filter&&ReactDOM.createPortal(h('div',{'data-wb-table-filter':true,style:{position:'fixed',top:140,left:300,zIndex:15000,background:'var(--ui-card-bg)',border:'1px solid var(--ui-border)',padding:16},
          onKeyDown:event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();stockFixture.filterClosed=(stockFixture.filterClosed||0)+1;closeFilter();}}},
          h('label',null,'筛选值',h('input',{'aria-label':'列筛选条件',ref:filterInput})),
          h('select',{'aria-label':'筛选内部状态',defaultValue:'a'},h('option',{value:'a'},'全部'),h('option',{value:'b'},'仅启用')),
          h('button',{type:'button',className:'btn',onClick:closeFilter},'关闭列筛选')),trigger.current.closest('[role="dialog"]')))));
}
window.mountFixture=spec=>{
  if(fixtureRoot)fixtureRoot.unmount();stockFixture.calls=[];stockFixture.closed=0;stockFixture.adjusted=0;stockFixture.filterClosed=0;stockFixture.resolve=null;stockFixture.keepOpen=false;
  fixtureRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));
  fixtureRoot.render(h(spec.overlay?OverlayHarness:FormHarness,{spec,key:++stockFixture.serial}));
};
ReactDOM.createRoot(document.getElementById('controls-root')).render(h(React.Fragment,null,h(WorkbenchGuardHost),h(WorkbenchControlStyles),h(WorkbenchControls),h(WorkbenchNumberControls)));
`;
const html='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+
  '<link rel="icon" href="/static/'+manifest.icon+'"><script src="/static/'+manifest.theme_script+'"></script>'+manifest.styles.map(p=>'<link rel="stylesheet" href="/static/'+p+'">').join('')+'<style>'+sharedStyles.map(item=>item.code).join('\n')+'</style>'+
  '<style>body.aps-workbench{margin:0;background:var(--ui-bg);color:var(--ui-text)}main{padding:24px}main>h1{font-size:20px}.modal-b>label{display:block;margin-bottom:12px}.modal-b>label>input,.modal-b>label>select{display:block;max-width:320px;margin-top:4px}</style></head>'+ 
  '<body class="aps-workbench"><main class="plana"><h1>库存与弹窗组件验证</h1><div id="controls-root"></div><div id="fixture-root"></div></main>'+ 
  manifest.scripts.filter(p=>p.startsWith('workbench/vendor/')||p.startsWith('workbench/assets/foundation-')).map(p=>'<script src="/static/'+p+'"></script>').join('')+
  '<script src="/components.js"></script><script>'+fixture+'</script></body></html>';
const server=http.createServer((req,res)=>{const name=new URL(req.url,'http://fixture').pathname;
  if(name==='/'){res.setHeader('Content-Type','text/html;charset=utf-8');res.end(html);return;}
  if(name==='/components.js'){res.setHeader('Content-Type','application/javascript');res.end(compiled);return;}
  const asset=assets.get(name.slice('/static/'.length));if(!name.startsWith('/static/')||!asset){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',asset.mime);res.end(fs.readFileSync(path.join(root,'static',asset.path)));});
const result={scope:'isolated-current-source-stock-modal-components',production_persistence_tested:false,win7_hardware_tested:false,
  sources:sources.concat(sharedStyles).map(s=>({path:s.path,sha256:crypto.createHash('sha256').update(s.code).digest('hex')})),cases:[],errors:[],external:[]};
let page,variant;
const panel=()=>page.getByRole('dialog').filter({has:page.locator('.modal-head')});
const stock=()=>panel().locator('input[name="stock_qty"]');
async function mount(spec={}){await page.evaluate(spec=>mountFixture(spec),spec);await page.locator('#fixture-trigger').click();await panel().waitFor();}
async function save(){await panel().locator('.modal-f').getByRole('button',{name:'保存',exact:true}).click();}
async function lastInput(count=1){await page.waitForFunction(count=>stockFixture.calls.length===count,count);return page.evaluate(()=>stockFixture.calls.at(-1));}
async function backdrop(){await page.mouse.click(8,8);}
async function shot(name){await page.evaluate(()=>document.fonts.ready);
  const geometry=await panel().evaluate(el=>{const b=el.getBoundingClientRect();return {left:b.left,right:b.right,top:b.top,bottom:b.bottom,width:innerWidth,height:innerHeight,
    clipped:Array.from(el.querySelectorAll('button')).filter(x=>x.getClientRects().length&&x.scrollWidth>x.clientWidth+1).map(x=>x.textContent)};});
  assert(geometry.left>=0&&geometry.right<=geometry.width+1&&geometry.top>=0&&geometry.bottom<=geometry.height+1);assert.deepEqual(geometry.clipped,[]);
  const file=variant+'-'+name+'.png';await page.screenshot({path:path.join(output,file)});result.cases.push({variant,name:name+'-visual',passed:true,screenshot:file,geometry});}
async function run(name,fn){try{await fn();result.cases.push({variant,name,passed:true});}catch(error){result.cases.push({variant,name,passed:false,message:error.message});await page.screenshot({path:path.join(output,variant+'-'+name+'-failure.png')});throw error;}}
async function cases(){
  await run('detail-adjust-stock-callback',async()=>{await mount({detail:true});await panel().getByRole('button',{name:'调整库存',exact:true}).click();
    await page.getByRole('dialog',{name:'调整库存',exact:true}).waitFor();assert.equal(await page.evaluate(()=>stockFixture.adjusted),1);
    assert.equal(await panel().locator('form input').count(),1);assert.equal(await stock().inputValue(),'8.375');assert(await panel().getByText('kg',{exact:true}).isVisible());
    assert.equal(await panel().locator('input[name="label"],input[name="unit"],input[name="spec"],select').count(),0);
    const numberBox=await stock().boundingBox(),reloadBox=await panel().getByRole('button',{name:'刷新最新资料',exact:true}).boundingBox();assert(reloadBox.y-numberBox.y-numberBox.height>=8);
    await shot('stock-only');
    await stock().fill('12.625');await save();const call=await lastInput();assert.equal(call.kind,'material');assert.equal(call.action,'update');assert.equal(call.ref,'1'.padStart(48,'0'));
    assert.deepEqual(call.body.input,{fields:{stock_qty:12.625}});await panel().getByText('保存已完成。',{exact:true}).waitFor();await panel().getByText('已刷新到最新数据。',{exact:true}).waitFor();
    assert(await stock().isDisabled());assert.equal(await page.evaluate(()=>stockFixture.original.fields.unit),'kg');assert.equal(await page.evaluate(()=>stockFixture.original.fields.hidden_legacy),'legacy-exact');});
  await run('unchanged-unknown-and-explicit-zero',async()=>{await mount({fields:{stock_qty:null,unit:null}});assert.equal(await stock().inputValue(),'');assert(await panel().getByText('未知',{exact:true}).isVisible());
    assert.deepEqual(await page.evaluate(()=>stockFixture.calls),[]);await save();assert.deepEqual((await lastInput()).body.input,{});
    await mount({fields:{stock_qty:null}});await stock().fill('0');await save();assert.deepEqual((await lastInput()).body.input,{fields:{stock_qty:0}});});
  await run('invalid-numbers-not-cleared',async()=>{await mount();await stock().fill('');await save();assert.equal(await page.evaluate(()=>stockFixture.calls.length),0);assert(await stock().getAttribute('aria-invalid')==='true');
    await stock().fill('-1');await save();assert.equal(await page.evaluate(()=>stockFixture.calls.length),0);
    await stock().fill('');await stock().type('1e');await save();assert.equal(await page.evaluate(()=>stockFixture.calls.length),0);});
  await run('cancel-keeps-values-and-restores-focus',async()=>{await mount();await stock().fill('45.125');await panel().locator('.modal-f').getByRole('button',{name:'取消',exact:true}).click();
    await page.getByRole('dialog',{name:'离开前确认',exact:true}).getByRole('button',{name:'留在当前页面',exact:true}).click();assert.equal(await stock().inputValue(),'45.125');
    await panel().locator('.modal-f').getByRole('button',{name:'取消',exact:true}).click();await page.getByRole('button',{name:'放弃未保存内容并继续',exact:true}).click();
    assert.equal(await page.locator('.modal-bg').count(),0);assert.equal(await page.evaluate(()=>stockFixture.calls.length),0);assert.equal(await page.evaluate(()=>stockFixture.original.fields.stock_qty),8.375);
    assert(await page.locator('#fixture-trigger').evaluate(el=>document.activeElement===el));});
  await run('capability-blocked-and-unwired-entry',async()=>{await mount({detail:true,allowed:false});assert(await panel().getByRole('button',{name:'调整库存',exact:true}).isDisabled());
    await mount({detail:true,noAdjust:true});assert(await panel().getByRole('button',{name:'调整库存',exact:true}).isDisabled());
    await mount({allowed:false});assert(await panel().getByRole('button',{name:'保存',exact:true}).isDisabled());await panel().locator('form').evaluate(form=>form.requestSubmit());assert.equal(await page.evaluate(()=>stockFixture.calls.length),0);
    await mount({detail:true,source:'demo'});assert(await panel().getByRole('button',{name:'调整库存',exact:true}).isDisabled());});
  await run('stale-context-keeps-stock-draft',async()=>{await mount({behavior:'stale'});await stock().fill('17.875');await save();await panel().getByRole('alert').getByText('资料已变化，请重新读取并核对。',{exact:true}).waitFor();
    assert.equal(await stock().inputValue(),'17.875');await panel().getByRole('button',{name:'刷新最新资料',exact:true}).click();
    await panel().getByText('服务端新名称',{exact:false}).waitFor();assert.equal(await stock().inputValue(),'17.875');await shot('stale-draft');
    await panel().getByRole('button',{name:'已核对，继续编辑',exact:true}).click();assert.equal(await stock().inputValue(),'17.875');
    assert(await panel().getByText('18.625',{exact:true}).isVisible());assert(await panel().getByText('件',{exact:true}).isVisible());assert.equal(await panel().getByText('kg',{exact:true}).count(),0);
    await save();const call=await lastInput(2);assert.equal(call.body.write_token,'reviewed-token');
    assert.deepEqual(call.body.input,{fields:{stock_qty:17.875}});assert.equal(await page.evaluate(()=>stockFixture.original.fields.remark),'不可覆盖的原备注');});
  await run('stock-mode-drops-unrelated-unsaved-fields',async()=>{await mount({normal:true});await panel().locator('input[name="label"]').fill('不得提交的名称');await panel().locator('input[name="unit"]').fill('不得提交的单位');
    await page.evaluate(()=>stockFixture.switchStock());await page.getByRole('dialog',{name:'调整库存',exact:true}).waitFor();assert.equal(await panel().locator('input[name="label"]').count(),0);
    await stock().fill('10.125');await save();assert.deepEqual((await lastInput()).body.input,{fields:{stock_qty:10.125}});});
  await run('ordinary-editor-and-stock-mode-scope',async()=>{await mount({normal:true});await panel().locator('input[name="label"]').fill('正常改名');await save();assert.deepEqual((await lastInput()).body.input,{label:'正常改名'});
    await mount({kind:'op_type',fields:{category:'external',default_merge_mode:'separate'}});await page.getByRole('dialog',{name:'编辑外协工种',exact:true}).waitFor();assert.equal(await panel().locator('input[name="stock_qty"]').count(),0);});
  await run('op-type-basis-no-guessed-category',async()=>{for(const [category,basis] of [['internal','工时（换型＋单件）'],['external','周期（天）'],['broken','未明确'],['constructor','未明确']]){
    await mount({kind:'op_type',detail:true,fields:{category}});assert(await panel().getByText(basis,{exact:true}).isVisible());assert.equal(await panel().getByRole('button',{name:'调整库存',exact:true}).count(),0);}
    await shot('unknown-op-type');});
  await run('backdrop-cancel-and-content-click',async()=>{await mount();await stock().fill('13.75');await panel().getByText('当前库存',{exact:true}).click();assert.equal(await page.evaluate(()=>stockFixture.closed),0);
    await backdrop();await page.getByRole('button',{name:'放弃未保存内容并继续',exact:true}).click();assert.equal(await page.locator('.modal-bg').count(),0);assert.equal(await page.evaluate(()=>stockFixture.calls.length),0);assert(await page.locator('#fixture-trigger').evaluate(el=>document.activeElement===el));});
  await run('locked-submit-blocks-backdrop',async()=>{await mount({behavior:'pending'});await stock().fill('9.875');await save();await page.waitForFunction(()=>typeof stockFixture.resolve==='function');
    await backdrop();await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>stockFixture.closed),0);assert.equal(await page.locator('.modal-bg').count(),1);
    await page.evaluate(()=>stockFixture.resolve());await panel().getByText('保存已完成。',{exact:true}).waitFor();await backdrop();assert.equal(await page.locator('.modal-bg').count(),0);});
  await run('drag-out-and-drag-in-do-not-close',async()=>{await mount({overlay:true});const box=await panel().locator('.modal-head').boundingBox();
    await page.mouse.move(box.x+50,box.y+20);await page.mouse.down();await page.mouse.move(8,8);await page.mouse.up();assert.equal(await page.evaluate(()=>stockFixture.closed),0);
    await page.mouse.move(8,8);await page.mouse.down();await page.mouse.move(box.x+50,box.y+20);await page.mouse.up();assert.equal(await page.evaluate(()=>stockFixture.closed),0);
    await backdrop();assert.equal(await page.evaluate(()=>stockFixture.closed),1);});
  await run('locked-and-suspended-backdrop-callback',async()=>{await mount({overlay:true});await page.evaluate(()=>stockFixture.setLocked(true));await backdrop();assert.equal(await page.evaluate(()=>stockFixture.closed),0);
    await page.evaluate(()=>stockFixture.setLocked(false));await page.evaluate(()=>stockFixture.setSuspended(true));
    await page.locator('.modal-bg').evaluate(el=>{el.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,button:0}));el.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,button:0}));el.dispatchEvent(new MouseEvent('click',{bubbles:true}));});
    assert.equal(await page.evaluate(()=>stockFixture.closed),0);await page.evaluate(()=>stockFixture.setSuspended(false));await backdrop();assert.equal(await page.evaluate(()=>stockFixture.closed),1);});
  await run('lock-transition-does-not-complete-old-click',async()=>{await mount({overlay:true});await page.evaluate(()=>stockFixture.setLocked(true));await page.waitForFunction(()=>document.querySelector('.modal-x').disabled);
    await page.mouse.move(8,8);await page.mouse.down();await page.evaluate(()=>stockFixture.setLocked(false));await page.waitForFunction(()=>!document.querySelector('.modal-x').disabled);await page.mouse.up();
    assert.equal(await page.evaluate(()=>stockFixture.closed),0);await page.mouse.down();await page.evaluate(()=>stockFixture.setLocked(true));await page.waitForFunction(()=>document.querySelector('.modal-x').disabled);await page.mouse.up();
    assert.equal(await page.evaluate(()=>stockFixture.closed),0);await page.evaluate(()=>stockFixture.setLocked(false));await backdrop();assert.equal(await page.evaluate(()=>stockFixture.closed),1);});
  await run('backdrop-delegates-discard-decision',async()=>{await mount({overlay:true});await page.evaluate(()=>{stockFixture.keepOpen=true;});await backdrop();assert.equal(await page.evaluate(()=>stockFixture.closed),1);
    assert.equal(await page.locator('.modal-bg').count(),1);await page.evaluate(()=>{stockFixture.keepOpen=false;});await backdrop();assert.equal(await page.locator('.modal-bg').count(),0);});
  await run('filter-escape-first-then-modal',async()=>{await mount({overlay:true});await panel().getByRole('button',{name:'打开列筛选',exact:true}).click();await page.getByLabel('列筛选条件',{exact:true}).fill('设备A');
    await page.keyboard.press('Escape');assert.equal(await page.locator('[data-wb-table-filter]').count(),0);assert.equal(await page.evaluate(()=>stockFixture.closed),0);assert.equal(await page.evaluate(()=>stockFixture.filterClosed),1);
    assert(await panel().getByRole('button',{name:'打开列筛选',exact:true}).evaluate(el=>document.activeElement===el));await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>stockFixture.closed),1);
    assert(await page.locator('#fixture-trigger').evaluate(el=>document.activeElement===el));});
  await run('filter-select-escape-order',async()=>{await mount({overlay:true});await panel().getByRole('button',{name:'打开列筛选',exact:true}).click();await page.getByLabel('筛选内部状态',{exact:true}).click();
    await page.locator('.wb-control-popup').waitFor();await page.keyboard.press('Escape');assert.equal(await page.locator('.wb-control-popup').count(),0);assert.equal(await page.locator('[data-wb-table-filter]').count(),1);assert.equal(await page.evaluate(()=>stockFixture.closed),0);
    await page.keyboard.press('Escape');assert.equal(await page.locator('[data-wb-table-filter]').count(),0);assert.equal(await page.evaluate(()=>stockFixture.closed),0);});
  await run('existing-date-and-select-escape-order',async()=>{await mount({overlay:true});await page.getByLabel('测试状态',{exact:true}).click();await page.locator('.wb-control-popup').waitFor();await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>stockFixture.closed),0);
    const date=page.getByLabel('测试日期',{exact:true}),box=await date.boundingBox();await page.mouse.click(box.x+box.width-12,box.y+box.height/2);await page.locator('.wb-control-popup').waitFor();await page.keyboard.press('Escape');
    assert.equal(await page.locator('.wb-control-popup').count(),0);assert.equal(await page.evaluate(()=>stockFixture.closed),0);assert.equal(await date.inputValue(),'2026-09-09');
    await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>stockFixture.closed),1);});
  await run('tab-loop-and-long-stock-identity',async()=>{await mount({long:true});await panel().locator('.modal-x').focus();await page.keyboard.press('Shift+Tab');assert(await panel().locator('.modal-f').getByRole('button',{name:'保存',exact:true}).evaluate(el=>document.activeElement===el));
    await page.keyboard.press('Tab');assert(await panel().locator('.modal-x').evaluate(el=>document.activeElement===el));await shot('long-identity');await page.keyboard.press('Escape');assert(await page.locator('#fixture-trigger').evaluate(el=>document.activeElement===el));});
}
(async()=>{let browser;try{if(!process.env.WORKBENCH_BROWSER)throw new Error('Set WORKBENCH_BROWSER to actual Chromium 109');await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
  browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true});result.browser=browser.version();assert.match(result.browser,/^109\./);
  for(const viewport of [{width:1920,height:1080},{width:1392,height:924}])for(const theme of ['light','dark']){variant=viewport.width+'x'+viewport.height+'-'+theme;
    const context=await browser.newContext({viewport});await context.addInitScript(theme=>{localStorage.setItem('aps_theme',theme);localStorage.setItem('aps_kit_theme',theme);},theme);page=await context.newPage();page.setDefaultTimeout(12000);
    page.on('pageerror',error=>result.errors.push({variant,message:error.message}));page.on('console',message=>{if(message.type()==='error')result.errors.push({variant,message:message.text()});});
    await page.route('**/*',route=>{if(!route.request().url().startsWith(origin+'/')){result.external.push(route.request().url());return route.abort();}return route.continue();});
    await page.goto(origin,{waitUntil:'load'});await cases();await context.close();}
  assert.deepEqual(result.errors,[]);assert.deepEqual(result.external,[]);result.passed=true;
}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));fs.writeFileSync(path.join(output,'stock-modal-result.json'),JSON.stringify(result,null,2));}
console.log(JSON.stringify({passed:result.passed,browser:result.browser,cases:result.cases.length,output}));})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
