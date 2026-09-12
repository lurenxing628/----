'use strict';
// Read-only mock fixture: navigation, presentation and protocol rejection, not persistence.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..'),output=process.argv[2];
if(!output)throw new Error('Pass an output directory');
fs.mkdirSync(output,{recursive:true});
const manifest=JSON.parse(fs.readFileSync(path.join(root,'static/workbench/asset-manifest.json')));
const records=new Map(manifest.files.map(item=>[item.path,item]));
const fixture=`
const h=React.createElement,ref=n=>n.toString(16).padStart(48,'0');
const entity=(kind,n,code,label,fields={},relationships={})=>({kind,ref:ref(n),business_code:code,label,status:kind==='op_type'?null:'active',fields,relationships,issues:[],write_context:null});
window.detailFixture={requests:[],writes:0,failNext:false,stale:false};
const internal=entity('op_type',1,'OT-IN','精加工',{category:'internal',remark:'产能说明'});
internal.availability={basis:'enabled_authorized_matching',machines:11,operators:1};
const external=entity('op_type',2,'OT-EX','热处理',{category:'external',default_merge_mode:'separate'});
const machines=Array.from({length:12},(_,i)=>entity('machine',100+i,'EQ-'+String(i).padStart(2,'0'),i===0?'多轴加工中心 需要完整显示的设备名称'.repeat(5):'设备 '+i,{relation_source_label:'工种绑定'}, {op_type_ref:internal.ref,op_type:{ref:internal.ref,label:internal.label}}));
const operators=[entity('operator',300,'P-01','李明',{relation_source_label:'技能与设备授权',matching_machine_authorization_count:1,qualification_matches:true},{skill_refs:[internal.ref],skills:[{ref:internal.ref,label:internal.label}],legacy_machine_authorizations:[]})];
const suppliers=[entity('supplier',400,'S-01','热处理供应商',{default_days:2.75,relation_source_label:'旧单工种关联'}, {op_type_refs:[external.ref],op_types:[{ref:external.ref,label:external.label}]})];
const material=entity('material',500,'M-01','钢材',{stock_qty:2.75,unit:'kg'});
const all=[internal,external,...machines,...operators,...suppliers,material];
function envelope(data){return {ok:true,schema_version:1,data,meta:{source:'production',time_basis:'factory_local',snapshot_ref:'detail-fixture',request_ref:'mock',as_of:'2026-09-09T08:00:00'},warnings:[]};}
const pageData=(rows,scope)=>({entities:rows.slice((scope.page-1)*scope.size,scope.page*scope.size),page:{number:scope.page,size:scope.size,total:rows.length,pages:Math.max(1,Math.ceil(rows.length/scope.size)),sort:[{field:'business_code',direction:'asc'}]}});
window.detailAdapter={
  summary:async()=>envelope({counts:{part:0,material:1,internal_op_types:1,machine:12,operator:1,external_op_types:1,supplier:1}}),
  list:async(kind,scope)=>envelope({...pageData(all.filter(item=>item.kind===kind&&(!scope.category||item.fields.category===scope.category)),scope),create_context:null}),
  detail:async(kind,ref)=>{detailFixture.requests.push({kind,ref});const value=all.find(item=>item.kind===kind&&item.ref===ref);if(!value)throw new Error('Unknown fixture entity');return envelope(value);},
  relations:async(parent,scope)=>{detailFixture.requests.push({parent,...scope});if(detailFixture.failNext){detailFixture.failNext=false;throw new Error('模拟关联读取失败');}if(scope.snapshot_ref&&detailFixture.stale)throw new Error('关联资料已经变化');
    let rows=({machines,operators,suppliers})[scope.relation].filter(item=>!scope.query||item.business_code.includes(scope.query)||item.label.includes(scope.query));
    return envelope({...pageData(rows,scope),parent_ref:parent,parent_kind:'op_type',relation:scope.relation,basis:{code:'recorded_associations',message:'登记关联；不代表当前时段可排。'}});},
  command:async()=>{detailFixture.writes++;throw new Error('Read-only fixture must not write');}
};
ReactDOM.createRoot(document.getElementById('root')).render(h(React.Fragment,null,h(WorkbenchControlStyles),h(WorkbenchControls),h(WorkbenchNumberControls),
 h(AppShell,{active:'process',title:'只读详情测试',theme:document.documentElement.dataset.theme,showCapsule:false,onNav:()=>{}},h(ResourceWorkspace,{adapter:detailAdapter,initialNode:'op_int'}))));`;
const html='<!doctype html><html><head><meta charset="utf-8"><script src="/static/'+manifest.theme_script+'"></script>'+manifest.styles.map(name=>'<link rel="stylesheet" href="/static/'+name+'">').join('')+'</head><body class="aps-workbench"><div id="root"></div>'+manifest.scripts.filter(name=>!name.endsWith('/main.js')).map(name=>'<script src="/static/'+name+'"></script>').join('')+'<script>'+fixture+'</script></body></html>';
const server=http.createServer((req,res)=>{
  if(req.url==='/'){res.setHeader('Content-Type','text/html;charset=utf-8');res.end(html);return;}
  if(req.url==='/favicon.ico'){res.writeHead(204);res.end();return;}
  const name=new URL(req.url,'http://fixture').pathname.slice('/static/'.length),record=records.get(name);
  if(!record){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',record.mime);res.end(fs.readFileSync(path.join(root,'static',name)));
});
const report={scope:'read-only-component-mock',build_id:manifest.build_id,cases:[],screenshots:[],errors:[],external:[]};
async function shot(page,state,name){
  await page.evaluate(()=>document.fonts.ready);
  const file=path.join(output,state+'-'+name+'.png');await page.screenshot({path:file});report.screenshots.push(file);
  const geometry=await page.evaluate(()=>{
    const modal=document.querySelector('[role="dialog"]'),box=modal&&modal.getBoundingClientRect();
    return {width:innerWidth,height:innerHeight,scroll:document.documentElement.scrollWidth,box:box&&{left:box.left,right:box.right,top:box.top,bottom:box.bottom},
      overflow:Array.from(document.querySelectorAll('.wb-resource-relation-content,.wb-resource-association-head')).filter(node=>node.scrollWidth>node.clientWidth+1).map(node=>node.textContent),
      native:Array.from(document.querySelectorAll('button,input,select')).filter(node=>node.getClientRects().length&&getComputedStyle(node).appearance!=='none').map(node=>node.tagName)};
  });
  assert(geometry.scroll<=geometry.width+1);assert.deepEqual(geometry.native,[]);assert.deepEqual(geometry.overflow,[]);
  if(geometry.box)assert(geometry.box.left>=0&&geometry.box.right<=geometry.width+1&&geometry.box.top>=0&&geometry.box.bottom<=geometry.height+1);
}
async function close(page){await page.getByRole('dialog').locator('.modal-f').getByRole('button',{name:'关闭',exact:true}).click();await page.getByRole('dialog').waitFor({state:'detached'});}
async function rail(page,label){await page.locator('.hb-tile').filter({has:page.locator('.hb-tname').getByText(label,{exact:true})}).click();}
async function run(page,state,name,fn){let passed=false;try{await fn();await shot(page,state,name);passed=true;}finally{report.cases.push({state,name,passed});}}
(async()=>{let browser;try{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
  browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-background-networking']});report.browser=browser.version();assert(report.browser.startsWith('109.'));
  for(const viewport of [{width:1920,height:1080},{width:1392,height:924}])for(const theme of ['light','dark']){
    const state=viewport.width+'-'+theme,context=await browser.newContext({viewport});
    await context.addInitScript(theme=>{localStorage.setItem('aps_theme',theme);localStorage.setItem('aps_kit_theme',theme);},theme);
    const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',error=>report.errors.push(error.message));
    await page.route('**/*',route=>{if(!route.request().url().startsWith(origin+'/')){report.external.push(route.request().url());return route.abort();}return route.continue();});
    await page.goto(origin);
    await run(page,state,'readonly-view-first',async()=>{
      const view=page.getByRole('button',{name:'查看绑定',exact:true});await view.click();
      assert.equal((await view.boundingBox()).height,30,'Resource row action must use the compact 30px control height');
      await page.getByRole('button',{name:/^查看设备 EQ-00 /}).waitFor();
      const edit=page.getByRole('dialog').getByRole('button',{name:'编辑',exact:true});
      assert(await edit.isDisabled());
      const reason=await edit.getAttribute('aria-describedby');assert(reason,'Read-only edit must identify its visible reason');
      const description=page.locator('[id="'+reason+'"]');
      assert(await description.isVisible());assert.equal(await description.innerText(),'尚未读取可用于保存的资料，请重新读取最新资料。');
      assert.equal(await page.getByRole('dialog').locator('input[name="label"]').count(),0);
      assert.equal(await page.locator('.wb-resource-association[aria-label="关联设备"] .wb-resource-relation').count(),5);
    });
    await run(page,state,'nested-details-and-back',async()=>{
      await page.getByRole('button',{name:/^查看设备 EQ-00 /}).click();await page.getByRole('dialog',{name:'设备详情',exact:true}).waitFor();
      await page.getByRole('dialog').getByRole('button',{name:'精加工',exact:true}).click();await page.getByRole('dialog',{name:'自制工种详情',exact:true}).waitFor();
      await page.getByRole('button',{name:'返回上一条详情',exact:true}).click();await page.getByRole('dialog',{name:'设备详情',exact:true}).waitFor();
      await page.getByRole('button',{name:'返回上一条详情',exact:true}).click();await page.getByRole('button',{name:/^查看设备 EQ-00 /}).waitFor();
    });
    await run(page,state,'paged-search-and-stale-retry',async()=>{
      await page.getByRole('button',{name:'关联设备下一页',exact:true}).click();await page.getByRole('button',{name:/^查看设备 EQ-05 /}).waitFor();
      assert.equal(await page.evaluate(()=>detailFixture.requests.filter(item=>item.relation==='machines').at(-1).snapshot_ref),'detail-fixture');
      await page.evaluate(()=>{detailFixture.stale=true;});await page.getByRole('button',{name:'关联设备下一页',exact:true}).click();await page.getByText('关联资料已经变化',{exact:true}).waitFor();
      assert.equal(await page.locator('.wb-resource-association[aria-label="关联设备"] .wb-resource-relation').count(),0);
      await page.getByRole('button',{name:'重新读取关联设备',exact:true}).click();await page.getByRole('button',{name:/^查看设备 EQ-00 /}).waitFor();
      const search=page.getByRole('searchbox',{name:'搜索关联设备',exact:true});await search.click();await search.pressSequentially('EQ-11');await search.press('Enter');
      await page.getByRole('button',{name:/^查看设备 EQ-11 /}).waitFor();assert.equal(await page.locator('.wb-resource-association[aria-label="关联设备"] .wb-resource-relation').count(),1);
    });
    await run(page,state,'suppliers-and-related-op-type',async()=>{
      await close(page);await rail(page,'外协工种');await page.getByRole('button',{name:'查看供应商',exact:true}).click();
      await page.getByRole('button',{name:/^查看供应商 S-01 /}).click();await page.getByRole('dialog',{name:'供应商详情',exact:true}).waitFor();
      await page.getByRole('dialog').getByRole('button',{name:'热处理',exact:true}).click();await page.getByRole('dialog',{name:'外协工种详情',exact:true}).waitFor();
    });
    await run(page,state,'material-readonly-and-focus-restored',async()=>{
      await close(page);await rail(page,'物料');const button=page.getByRole('button',{name:'查看/编辑',exact:true});await button.click();
      await page.getByRole('dialog',{name:'物料详情',exact:true}).waitFor();await close(page);assert(await button.evaluate(node=>document.activeElement===node));
      assert.equal(await page.evaluate(()=>detailFixture.writes),0);
    });
    await run(page,state,'units-and-invalid-relation-protocol',async()=>{
      const result=await page.evaluate(async()=>{
        const contract=APSResourceFile.create('supplier');const unit=[contract.displayValue('default_days',2.75),contract.displayValue('default_days',0),contract.displayValue('default_hours',8.375)];
        const scope={relation:'machines',page:1,size:5,query:''},parent='1'.padStart(48,'0'),original=await detailAdapter.relations(parent,scope);
        ResourceDetailRelations.query(original,parent,scope);
        const faults=[value=>value.data.parent_ref='2'.padStart(48,'0'),value=>value.data.relation='suppliers',value=>value.data.entities[0].kind='supplier',value=>value.data.entities[0].write_context={write_token:'forbidden'},value=>value.data.entities[0].ref='bad',value=>value.data.page.number=2,value=>value.data.page.size=20,value=>value.data.page.pages=9,value=>value.data.page.total=0,value=>value.data.entities.push(value.data.entities[0]),value=>value.meta.time_basis='utc',value=>value.data.basis=null];
        return {unit,rejected:faults.map(fault=>{const bad=JSON.parse(JSON.stringify(original));fault(bad);try{ResourceDetailRelations.query(bad,parent,scope);return false;}catch(_){return true;}})};
      });
      assert.deepEqual(result.unit,['2.75 天','0 天','8.375 小时']);assert(result.rejected.every(Boolean));
    });
    await context.close();
  }
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.external,[]);
}catch(error){report.runner_error=error.stack;throw error;}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));fs.writeFileSync(path.join(output,'details-result.json'),JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify({output,browser:report.browser,cases:report.cases.length,errors:report.errors}));})().catch(error=>{console.error(error);process.exitCode=1;});
