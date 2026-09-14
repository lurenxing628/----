'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const auxiliary=require('./resource_aux_probe.cjs');
const {conflicts}=require('./resource_conflicts_probe.cjs');
const {select}=require('./custom_control_actions.cjs');
const {resourceFiles}=require('./resource_files_live_probe.cjs');
const {resourceDetails}=require('./resource_details_live_probe.cjs');
const {resourceTableControls}=require('./resource_table_live_probe.cjs');
const ready=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),root=ready.root,origin=ready.url;
const report={scope:'real-Flask-isolated-database',input_method:'browser-keyboard-and-controls',cases:[],screenshots:[],visual_checks:[],downloads:[],errors:[],console_errors:[],http_errors:[],failed_requests:[],external:[],commands:[],expected_failures:[]};
function equal(a,b){assert.deepEqual(a,b);}
async function shot(page,name){
  await page.evaluate(()=>document.fonts.ready);
  const file=path.join(root,'screenshots',name+'.png');await page.screenshot({path:file,fullPage:false,animations:'disabled'});
  const visual=await page.evaluate(()=>({viewport:[innerWidth,innerHeight],dialogs:Array.from(document.querySelectorAll('[role="dialog"][aria-modal="true"]')).map(node=>{
    const r=node.getBoundingClientRect(),style=getComputedStyle(node);return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,opacity:style.opacity,background:style.backgroundColor};})}));
  assert(visual.dialogs.every(r=>r.left>=0&&r.right<=visual.viewport[0]+1&&r.top>=0&&r.bottom<=visual.viewport[1]+1&&r.opacity==='1'),'Dialog framing/opacity '+JSON.stringify(visual));
  report.visual_checks.push({name,...visual});report.screenshots.push(file);
}
async function run(page,state,name,fn){
  const row={state,name,status:'passed'};
  try{await fn();await shot(page,state+'-'+name);}
  catch(error){row.status='failed';row.error=error.stack;await shot(page,state+'-'+name+'-FAILED').catch(()=>{});throw error;}
  finally{report.cases.push(row);console.log(state+' / '+name+': '+row.status);}
}
async function type(field,text){await field.click();await field.fill('');await field.pressSequentially(text,{delay:5});}
async function search(page,query){await type(page.getByRole('searchbox',{name:'搜索编号或名称'}),query);await page.getByRole('button',{name:'搜索',exact:true}).click();}
async function rail(page,label){
  await page.locator('.hb-tile').filter({has:page.locator('.hb-tname').getByText(label,{exact:true})}).click();
  await page.getByRole('button',{name:'新增'+label,exact:true}).waitFor();
  await page.getByRole('button',{name:'新增'+label,exact:true}).isEnabled();
}
function row(page,code){return page.locator('.wb-table tbody tr').filter({has:page.getByRole('button',{name:code,exact:true})});}
async function empty(page){
  const state=page.locator('.wb-table tbody .wb-empty-filtered');await state.waitFor();
  await state.getByText('当前筛选没有匹配项',{exact:true}).waitFor();
  assert(await state.getByRole('button',{name:'清除筛选',exact:true}).isEnabled());
  equal(await page.locator('.wb-table tbody input[type="checkbox"]').count(),0);
}
async function openEdit(page,code){
  await row(page,code).getByRole('button',{name:/^(查看\/编辑|查看绑定|查看供应商)$/}).click();
  await page.getByRole('dialog').getByRole('button',{name:'编辑',exact:true}).click();
  await page.getByRole('dialog').locator('input[name="label"]').waitFor();
}
async function editor(page){const dialog=page.getByRole('dialog');await dialog.waitFor();return dialog;}
async function close(page,{discard=false}={}){
  const dialogs=page.getByRole('dialog');assert.equal(await dialogs.count(),1,'Close must start from one active resource dialog');
  const dialog=page.getByRole('dialog',{name:await dialogs.locator('.modal-h2').innerText(),exact:true});
  await dialog.locator('.modal-f').getByRole('button',{name:/^(关闭|取消)$/,exact:true}).click();
  if(discard){
    const confirmation=page.getByRole('dialog',{name:'离开前确认',exact:true});await confirmation.waitFor();
    await confirmation.getByRole('button',{name:'放弃未保存内容并继续',exact:true}).click();
    await confirmation.waitFor({state:'detached'});
  }
  await dialog.waitFor({state:'detached'});assert.equal(await page.getByRole('dialog').count(),0);
}
async function save(page,kind,action,status=200){
  const wait=page.waitForResponse(res=>new URL(res.url()).pathname.endsWith('/'+action)&&res.request().method()==='POST'&&res.url().includes('/entities/'+kind+'/'));
  if(action==='delete')await page.getByRole('dialog').getByRole('checkbox',{name:'我已核对要删除的资料及其关联关系',exact:true}).check();
  await page.getByRole('dialog').locator('.modal-f').getByRole('button',{name:action==='delete'?'确认删除':'保存',exact:true}).click();
  const response=await wait,payload=await response.json();equal(response.status(),status);
  if(status===200){assert(['committed','unchanged'].includes(payload.result));await page.getByText('已刷新到最新数据。',{exact:true}).waitFor();}
  else{equal(payload.committed,false);report.expected_failures.push({status,code:payload.error.code,path:new URL(response.url()).pathname});}
  return payload;
}
async function layout(page){
  const bounds=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,
    controls:Array.from(document.querySelectorAll('[role="dialog"] button,[role="dialog"] input,[role="dialog"] select')).filter(n=>n.getClientRects().length).map(n=>{const r=n.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom};})}));
  assert(bounds.scroll<=bounds.width+1,JSON.stringify(bounds));assert(bounds.controls.every(r=>r.left>=0&&r.right<=bounds.width+1),JSON.stringify(bounds));
}
async function readEntity(context,kind,ref){const response=await context.request.get(origin+'/api/workbench/v1/entities/'+kind+'/'+ref);equal(response.status(),200);return (await response.json()).data;}
function watch(page,state){
  page.on('pageerror',error=>report.errors.push({state,error:error.message}));
  page.on('console',message=>{if(message.type()==='error')report.console_errors.push({state,message:message.text(),url:message.location().url});});
  page.on('requestfailed',request=>report.failed_requests.push({state,url:request.url(),method:request.method(),error:request.failure().errorText}));
  page.on('response',response=>{if(response.status()>=400)report.http_errors.push({state,url:response.url(),status:response.status()});});
  page.on('response',async res=>{if(res.request().method()==='POST'&&res.url().includes('/api/workbench/')){
    let body=null,result;try{body=res.request().postDataJSON();}catch(_){}try{result=await res.json();}catch(_){return;}
    report.commands.push({state,path:new URL(res.url()).pathname,request_key:body&&body.request_key,result:result.result,receipt_ref:result.receipt_ref,status:res.status()});
  }});
}
async function createEntity(page,label,kind,code,fields){
  await rail(page,label);await page.getByRole('button',{name:'新增'+label,exact:true}).click();
  const dialog=await editor(page);await type(dialog.locator('input[name="business_code"]'),code);await type(dialog.locator('input[name="label"]'),'UI '+code);
  await fields(dialog);await layout(page);await shot(page,code+'-filled');
  const saved=await save(page,kind,'create');await close(page);await search(page,code);await row(page,code).waitFor();
  return saved.data.entity_ref;
}
async function editAndDelete(page,context,label,kind,code,ref){
  const original=await readEntity(context,kind,ref);
  await openEdit(page,code);const cancelled=await editor(page);
  await type(cancelled.locator('input[name="label"]'),'Cancelled name');
  await cancelled.locator('.modal-f').getByRole('button',{name:'取消',exact:true}).click();
  const confirmation=page.getByRole('dialog',{name:'离开前确认',exact:true});await confirmation.waitFor();
  await confirmation.getByRole('button',{name:'留在当前页面',exact:true}).click();await confirmation.waitFor({state:'detached'});
  equal(await page.getByRole('dialog').locator('input[name="label"]').inputValue(),'Cancelled name');
  await close(page,{discard:true});
  equal((await readEntity(context,kind,ref)).label,original.label);
  await openEdit(page,code);const dialog=await editor(page);
  assert(!(await dialog.locator('input[name="business_code"]').isEditable()));await type(dialog.locator('input[name="label"]'),'Changed '+code);
  await save(page,kind,'update');await close(page);const changed=await readEntity(context,kind,ref);equal(changed.label,'Changed '+code);
  equal(changed.fields,original.fields);equal(changed.relationships,original.relationships);
  await row(page,code).getByRole('button',{name:'删除',exact:true}).click();await editor(page);await save(page,kind,'delete');await close(page);
  await empty(page);
}
async function scenario(browser,viewport,theme){
  const state=viewport.width+'-'+theme,context=await browser.newContext({viewport,acceptDownloads:true});
  await context.addInitScript(theme=>{localStorage.setItem('aps_theme',theme);localStorage.setItem('aps_kit_theme',theme);},theme);
  await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&new URL(url).origin!==origin){report.external.push(url);return route.abort();}return route.continue();});
  const page=await context.newPage();page.setDefaultTimeout(12000);
  watch(page,state);
  try{
    await page.goto(ready.resource_url);await page.getByRole('button',{name:'MAT-001',exact:true}).waitFor();await page.evaluate(()=>document.fonts.ready);
    await run(page,state,'initial-and-pagination',async()=>{
      assert(await page.locator('body').evaluate(node=>node.classList.contains('aps-workbench')));
      assert(await page.locator('input,select,button').evaluateAll(nodes=>nodes.filter(node=>node.getClientRects().length).every(node=>getComputedStyle(node).appearance==='none')));
      equal(await page.locator('html').getAttribute('data-theme'),theme);assert(await page.evaluate(()=>{const form=new FormData();form.append('probe','1');return form.get('probe')==='1'&&new DOMException('probe','AbortError').name==='AbortError';}));
      await page.getByRole('checkbox',{name:'选择 MAT-001 Material 1',exact:true}).check();
      await page.getByRole('button',{name:'下一页',exact:true}).click();await page.getByRole('button',{name:'MAT-021',exact:true}).waitFor();
      await page.getByRole('checkbox',{name:'全选当前页',exact:true}).check();
      await search(page,'MAT-040');await page.getByRole('button',{name:'MAT-040',exact:true}).waitFor();
      await page.getByText('含非当前页记录',{exact:true}).waitFor();
      await page.getByRole('button',{name:'清除所有选择',exact:true}).click();await layout(page);
    });
    await run(page,state,'invalid-form-and-cancel',async()=>{
      await page.getByRole('button',{name:'新增物料',exact:true}).click();await editor(page);
      const before=report.commands.length;await page.getByRole('dialog').getByRole('button',{name:'保存',exact:true}).click();
      await page.getByRole('dialog').getByRole('alert').first().waitFor();equal(report.commands.length,before);await close(page);
    });
    const cases=[
      ['物料','material',async dialog=>{await type(dialog.locator('input[name="spec"]'),'D25');await type(dialog.locator('input[name="unit"]'),'kg');await type(dialog.locator('input[name="stock_qty"]'),'3.75');await dialog.getByRole('button',{name:'增加库存数量',exact:true}).click();await dialog.getByRole('button',{name:'减少库存数量',exact:true}).click();await select(dialog.locator('select[name="status"]'),'active');}],
      ['自制工种','op_type',async dialog=>{assert((await dialog.locator('.modal-h2').innerText()).includes('自制工种'));assert.equal(await dialog.locator('select[name="default_merge_mode"]').count(),0);await type(dialog.locator('textarea[name="remark"]'),'Capacity note');}],
      ['设备','machine',async dialog=>{await select(dialog.getByLabel('绑定工种',{exact:true}),{label:'Turning'});await select(dialog.getByLabel('设备组',{exact:true}),{label:'Group A'});await select(dialog.locator('select[name="status"]'),'maintain');}],
      ['人员','operator',async dialog=>{await dialog.getByRole('checkbox',{name:'Turning',exact:true}).check();await select(dialog.getByLabel('班次',{exact:true}),{label:'Night shift'});await select(dialog.locator('select[name="status"]'),'leave');}],
      ['外协工种','op_type',async dialog=>{assert((await dialog.locator('.modal-h2').innerText()).includes('外协工种'));await select(dialog.locator('select[name="default_merge_mode"]'),'merged');await type(dialog.locator('textarea[name="remark"]'),'External note');}],
      ['供应商','supplier',async dialog=>{await dialog.getByRole('checkbox',{name:'Heat treatment',exact:true}).check();await type(dialog.locator('input[name="default_days"]'),'2.5');await select(dialog.locator('select[name="status"]'),'pending_review');}]
    ];
    for(let index=0;index<cases.length;index++){
      const [label,kind,fields]=cases[index],code='UI-'+state+'-'+index;let ref;
      await run(page,state,'create-'+index,async()=>{ref=await createEntity(page,label,kind,code,fields);});
      await run(page,state,'cancel-update-delete-'+index,()=>editAndDelete(page,context,label,kind,code,ref));
    }
    await run(page,state,'retained-unknown-material',async()=>{
      await rail(page,'物料');await search(page,'MAT-011');await openEdit(page,'MAT-011');
      const dialog=await editor(page);equal(await dialog.locator('input[name="stock_qty"]').inputValue(),'');await save(page,'material','update');await close(page);
    });
    await run(page,state,'theme-and-navigation',async()=>{
      await page.locator('.sidebar-nav').getByRole('link',{name:'系统管理',exact:true}).click();await page.locator('.sm-workbench[data-live="true"]').waitFor();
      await page.locator('.sidebar-nav').getByRole('link',{name:'基础资料',exact:true}).click();
      await row(page,'MAT-011').waitFor();equal(await page.getByRole('searchbox',{name:'搜索编号或名称'}).inputValue(),'MAT-011');
      await search(page,'');await page.getByRole('button',{name:'MAT-001',exact:true}).waitFor();
      equal(await page.locator('html').getAttribute('data-theme'),theme);await layout(page);
    });
    const helpers={run,close,type,rail,search,shot,layout,empty,recordExpected:row=>report.expected_failures.push({state,...row})};
    await resourceTableControls(page,state,{...helpers,row,save,createEntity,openEdit},root,report);
    await resourceDetails(page,state,{...helpers,row,save});
    await auxiliary.catalog(page,state,helpers);
    await auxiliary.calendar(page,state,helpers);
    await auxiliary.files(page,state,helpers,root,report);
    await conflicts(page,context,state,{...helpers,createEntity,editAndDelete,openEdit,save,row,watch,readEntity},report,origin);
    await resourceFiles(page,state,helpers,root,report);
  }finally{await context.close();}
}
(async()=>{
  let browser;
  try{
    browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-background-networking']});
    report.browser=browser.version();assert(report.browser.startsWith('109.'));report.build_id=ready.assets.build_id;
    for(const viewport of [{width:1920,height:1080},{width:1392,height:924}])for(const theme of ['light','dark'])await scenario(browser,viewport,theme);
    equal(report.errors,[]);equal(report.external,[]);
    const expectedPaths=new Set(report.expected_failures.flatMap(item=>item.paths||[item.path]).filter(Boolean));
    const expected=row=>row.url&&expectedPaths.has(new URL(row.url).pathname);
    report.unexpected_http_errors=report.http_errors.filter(row=>!expected(row));
    report.unexpected_console_errors=report.console_errors.filter(row=>!expected(row));
    report.unexpected_failed_requests=report.failed_requests.filter(row=>!expected(row)&&!(row.method==='GET'&&row.error==='net::ERR_ABORTED'));
    equal(report.unexpected_http_errors,[]);equal(report.unexpected_console_errors,[]);equal(report.unexpected_failed_requests,[]);
  }catch(error){report.runner_error=error.stack;console.error(error);process.exitCode=1;}
  finally{if(browser)await browser.close();report.summary={cases:report.cases.length,failed:report.cases.filter(row=>row.status==='failed').length,commands:report.commands.length,screenshots:report.screenshots.length};
    fs.writeFileSync(path.join(root,'resource-probe-results.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report.summary));}
})();
