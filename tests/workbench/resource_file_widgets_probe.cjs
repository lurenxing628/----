/* Real Chromium109 component interactions with MOCK envelopes, not persistence proof. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {chromium} = require('playwright');
const {fixture} = require('./resource_file_fixture_probe.cjs');
const output = process.argv[2];
if (!output) throw new Error('Pass an artifact directory');
fs.mkdirSync(output, {recursive:true});
const {server,sources,workbook} = fixture();
const result = {scope:'resource-file-components',data_source:'mock',production_persistence_tested:false,global_controls:true,
  sources:sources.map(item=>({path:item.path,sha256:crypto.createHash('sha256').update(item.code).digest('hex')})),cases:[],screenshots:[],errors:[],external:[]};
const resources = [{kind:'op_type',category:'internal',label:'自制工种'},{kind:'op_type',category:'external',label:'外协工种'},
  {kind:'machine',label:'设备'},{kind:'operator',label:'人员'},{kind:'supplier',label:'供应商'}];
let page,variant,current;
async function mount(spec){current=spec;await page.evaluate(spec=>mountFixture(spec),spec);await page.getByRole('dialog').waitFor();}
async function file(format='csv'){
  await page.getByRole('button',{name:format==='csv'?'CSV (.csv)':'Excel (.xlsx)',exact:true}).click();
  await page.getByLabel('选择'+current.label+'导入文件').setInputFiles({name:'增量.'+format,mimeType:format==='csv'?'text/csv':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:format==='csv'?Buffer.from('编号,名称\r\n0001,新名称\r\n'):Buffer.from(workbook,'base64')});
}
async function start(preview=true){await page.getByRole('button',{name:'开始预检',exact:true}).click();if(preview)await page.getByRole('heading',{name:'逐行预检',exact:true}).waitFor();}
async function select(label,text){await page.getByLabel(label,{exact:true}).click();const menu=page.getByRole('listbox',{name:label,exact:true});await menu.waitFor();await menu.getByRole('option',{name:text,exact:true}).click();await menu.waitFor({state:'hidden'});}
async function download(button,name){const waiting=page.waitForEvent('download');await button.click();const file=await waiting;assert.equal(file.suggestedFilename(),name);const dest=path.join(output,variant+'-'+name);await file.saveAs(dest);assert.equal(await file.failure(),null);return dest;}
async function shot(name){
  await page.evaluate(()=>document.fonts.ready);
  if(await page.locator('.rm-check').count())await page.locator('.rm-check').scrollIntoViewIfNeeded();
  const geometry=await page.evaluate(()=>{const r=document.querySelector('[role=dialog]').getBoundingClientRect(),ack=document.querySelector('.rm-check'),body=document.querySelector('.rm-body');return {width:innerWidth,height:innerHeight,theme:document.documentElement.dataset.theme,scroll:document.documentElement.scrollWidth,dialog:{left:r.left,right:r.right,top:r.top,bottom:r.bottom},ackVisible:!ack||ack.getBoundingClientRect().bottom<=body.getBoundingClientRect().bottom+1,clipped:Array.from(document.querySelectorAll('.modal button,.rm-table th')).filter(el=>el.scrollWidth>el.clientWidth+1).map(el=>el.textContent),controls:Array.from(document.querySelectorAll('.rm-actions select')).map(el=>{const s=getComputedStyle(el);return {appearance:s.appearance,radius:s.borderRadius,height:s.height};})};});
  assert(geometry.scroll<=geometry.width+1);assert(geometry.dialog.left>=0&&geometry.dialog.right<=geometry.width+1&&geometry.dialog.top>=0&&geometry.dialog.bottom<=geometry.height+1);assert.deepEqual(geometry.clipped,[]);
  assert(geometry.ackVisible);
  geometry.controls.forEach(control=>{assert.equal(control.appearance,'none');assert.equal(control.radius,'4px');assert.equal(control.height,'32px');});
  const filename=variant+'-'+current.kind+'-'+(current.category||'')+'-'+name+'.png';await page.screenshot({path:path.join(output,filename)});result.screenshots.push({filename,geometry});
}
async function run(name,fn){try{await fn();result.cases.push({variant,name,passed:true});}catch(error){result.cases.push({variant,name,passed:false,error:error.message});await page.screenshot({path:path.join(output,variant+'-'+name+'-FAILED.png')});throw error;}}
async function resourceCases(resource){
  const name=resource.kind+'-'+(resource.category||'');
  await run(name+'-cancel-template-file-range',async()=>{
    await mount({...resource,mode:'import'});await file();assert.equal(await page.evaluate(()=>fixture.previews.length+fixture.commands.length),0);
    assert(await page.getByText(/空列或缺列保持原值/).isVisible());await shot('import-file');
    await page.getByRole('button',{name:'取消',exact:true}).click();assert.equal(await page.evaluate(()=>fixture.commands.length+fixture.committed.length),0);
    await mount({...resource,mode:'import'});await file();
    const dest=await download(page.getByRole('button',{name:'下载模板',exact:true}),resource.kind+'-template.csv');assert.equal(fs.readFileSync(dest,'utf8').trim().split('\r\n').length,1);
    assert.deepEqual(await page.evaluate(()=>fixture.downloads[0]),{path:'templates/'+resource.kind,scope:{format:'csv',...(resource.category?{category:resource.category}:{})}});
    await page.getByRole('button',{name:'Excel (.xlsx)',exact:true}).click();
    const xlsx=await download(page.getByRole('button',{name:'下载模板',exact:true}),resource.kind+'-template.xlsx');assert.deepEqual(fs.readFileSync(xlsx),Buffer.from(workbook,'base64'));
    await page.getByRole('button',{name:'完成',exact:true}).click();assert.equal(await page.evaluate(()=>fixture.commands.length+fixture.committed.length),0);
  });
  await run(name+'-ack-preview-reset-and-confirm',async()=>{
    await mount({...resource,mode:'import',rows:25});await file();await start();
    const body=await page.evaluate(()=>fixture.previews[0].body);assert.deepEqual(body.keys,['file','format','mode'].concat(resource.category?['category']:[]));assert.equal(body.category,resource.category||null);assert.equal(body.mode,'upsert');
    assert(await page.getByRole('button',{name:/^确认导入/}).isDisabled());await select('预检明细筛选','涉及关联的更新 1');
    assert.equal(await page.locator('tr[data-resource-row]').count(),1);assert(await page.getByText('原事实完整保留',{exact:true}).first().isVisible());
    const text=await page.locator('.rm-table').innerText();assert(!text.includes('[object Object]'));assert(!text.includes('entity_key'));assert(!text.includes('"skill_level"'));
    if(resource.kind==='operator')assert(text.includes('OT-0001、OT-0002')&&text.includes('技能级别：普通'));
    if(resource.kind==='machine')assert(text.includes('设备编号：M-0001')&&text.includes('legacy-grade（原值）'));
    if(resource.category==='external')assert(text.includes('合并设置'));
    await page.getByRole('checkbox').check();await page.getByRole('button',{name:'重新预检',exact:true}).click();await page.waitForFunction(()=>fixture.previews.length===2);await page.getByRole('heading',{name:'逐行预检',exact:true}).waitFor();
    assert(!(await page.getByRole('checkbox').isChecked()));assert(await page.getByRole('button',{name:/^确认导入/}).isDisabled());
    await page.getByRole('checkbox').check();await shot('import-confirm');await page.getByRole('button',{name:'确认导入',exact:true}).click();await page.waitForFunction(()=>fixture.committed.length===1);
    const call=await page.evaluate(()=>fixture.commands[0]);assert.equal(call.kind,resource.kind+'_import');assert.equal(call.action,'confirm');assert.deepEqual(Object.keys(call.body).sort(),['input','request_key','write_token']);assert.deepEqual(call.body.input,{preview_ref:call.ref});
    const intent=await page.evaluate(kind=>JSON.parse(sessionStorage.getItem('aps_workbench_resource_pending_v1_'+kind+'_files')),resource.kind);assert.equal(intent.category,resource.category);assert(!('input' in intent));assert(!('acknowledged' in intent));assert(!('write_token' in intent));
    await page.getByRole('button',{name:'完成',exact:true}).click();
  });
  await run(name+'-pagination-reject-is-atomic',async()=>{
    await mount({...resource,mode:'import',rows:55,rejectRow:22});await file('xlsx');await start();assert.equal(await page.locator('tr[data-resource-row]').count(),20);
    await page.getByRole('button',{name:'预检下一页',exact:true}).click();await page.locator('tr[data-resource-row="23"]').waitFor();
    await select('预检明细筛选','拒绝行 1');assert.equal(await page.locator('tr[data-resource-row]').count(),1);assert(await page.getByText(/关系业务编号不属于/).isVisible());assert(await page.getByRole('button',{name:/^确认导入/}).isDisabled());
    await page.getByLabel('预检明细筛选').focus();await page.keyboard.press('Enter');await page.keyboard.press('Home');await page.keyboard.press('Enter');assert.equal(await page.locator('tr[data-resource-row]').count(),20);
    await select('预检每页行数','50 行');assert.equal(await page.locator('tr[data-resource-row]').count(),50);await shot('rejected-rows');assert.equal(await page.evaluate(()=>fixture.commands.length),0);
  });
  await run(name+'-cross-page-bulk-selection',async()=>{
    await mount({...resource,mode:'bulk',rows:2605});await page.evaluate(()=>{fixture.request.refs.splice(0);fixture.request.scope.category='external';});await start();
    const body=await page.evaluate(()=>fixture.previews[0].body);assert.equal(body.refs.length,2605);assert.equal(body.refs[2604],(2605).toString(16).padStart(48,'0'));assert.equal(body.page_size,20);assert.deepEqual(body.scope,{query:'跨页查询',status:'active',sort:'business_code',direction:'desc',...(resource.category?{category:resource.category}:{})});
    assert(await page.getByRole('button',{name:/^确认删除/}).isDisabled());await select('预检每页行数','100 行');assert.equal(await page.locator('tr[data-resource-row]').count(),100);await page.getByRole('checkbox').check();await shot('bulk');await page.getByRole('button',{name:'确认删除',exact:true}).click();await page.waitForFunction(()=>fixture.committed.length===1);assert.equal(await page.evaluate(()=>fixture.commands[0].kind),resource.kind+'_bulk');
  });
  for(const mode of ['import','bulk'])await run(name+'-'+mode+'-unknown-reload-same-key',async()=>{
    await mount({...resource,mode,rows:2,pending:true});if(mode==='import')await file();await start();await page.getByRole('checkbox').check();await page.getByRole('button',{name:mode==='import'?'确认导入':'确认删除',exact:true}).click();await page.getByRole('button',{name:'查询结果',exact:true}).waitFor();
    const intent=await page.evaluate(kind=>JSON.parse(sessionStorage.getItem('aps_workbench_resource_pending_v1_'+kind+'_files')),resource.kind);assert.equal(intent.category,resource.category);
    assert(await page.getByRole('button',{name:/^取消/}).isDisabled());await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>fixture.closed),0);
    await page.evaluate(()=>mountFixture({...JSON.parse(sessionStorage.getItem('fixture-resume')),recovery:true},true));await page.getByRole('button',{name:'查询结果',exact:true}).waitFor();assert.equal(await page.evaluate(()=>fixture.commands.length+fixture.previews.length),0);assert.equal(await page.evaluate(()=>sessionStorage.getItem('fixture-command-count')),'1');
    await page.reload();await page.getByRole('button',{name:'查询结果',exact:true}).waitFor();assert.equal(await page.evaluate(()=>fixture.lookups[0]),intent.request_key);assert.equal(await page.evaluate(()=>fixture.commands.length+fixture.previews.length),0);assert.equal(await page.evaluate(()=>sessionStorage.getItem('fixture-command-count')),'1');
    assert((await page.locator('.modal-h2').innerText()).includes(resource.label));assert.equal(await page.locator('[role="dialog"] input').count(),0);assert.equal(await page.getByText(/当前为示例数据|尚未读取生产资料|本次勾选了/).count(),0);
    await shot(mode+'-recovery');await page.evaluate(()=>{fixture.ready=true;});await page.getByRole('button',{name:'查询结果',exact:true}).click();await page.waitForFunction(()=>fixture.committed.length===1);assert.equal(await page.evaluate(()=>fixture.commands.length),0);await page.getByRole('button',{name:'完成',exact:true}).click();
  });
  await run(name+'-three-export-scopes-download-bytes',async()=>{
    await mount({...resource,mode:'export',rows:2605});assert.equal(await page.evaluate(()=>fixture.previews.length),0);
    for(const selection of ['selected','all','filtered']){
      await page.getByRole('radio',{name:selection==='selected'?new RegExp('已选'+resource.label):selection==='all'?new RegExp('全部'+resource.label):/当前筛选结果/}).check();
      await page.getByRole('button',{name:'CSV (.csv)',exact:true}).click();await start(false);await page.getByText('2605',{exact:true}).waitFor();
      const body=await page.evaluate(()=>fixture.previews[fixture.previews.length-1].body);assert.equal(body.selection,selection);assert.equal(body.scope.category,resource.category);assert.equal(body.page_size,20);
      if(selection==='selected')assert.equal(body.refs.length,2605);else assert(!('refs' in body));
      const dest=await download(page.getByRole('button',{name:'下载文件',exact:true}),resource.kind+'-export.csv');assert.equal(fs.readFileSync(dest,'utf8').trim().split('\r\n').length,2606);
      const request=await page.evaluate(()=>fixture.downloads[fixture.downloads.length-1]);assert.deepEqual(request.scope,{export_ref:'Ab_-'.repeat(8),format:'csv'});
    }
    await shot('export');assert.equal(await page.evaluate(()=>fixture.commands.length+fixture.committed.length),0);
  });
}
async function guardCases(){
  for(const [name,spec,message] of [
    ['wrong-category',{kind:'op_type',category:'internal',label:'自制工种',wrongCategory:true},'预检工种类别与当前自制或外协范围不一致，本批没有提交。'],
    ['missing-columns',{missingColumns:true},'预检缺少完整的业务列名，本批没有提交。'],
    ['private-fields',{privateFacts:true},'预检明细里有未说明的列或不对外的关联内容，本批没有提交。'],
    ['nested-internal-fields',{nestedFacts:true},'预检明细里有未说明的列或不对外的关联内容，本批没有提交。'],
    ['bad-summary',{malformed:true},'预检统计与明细不一致，本批没有提交。'],
    ['wrong-refs',{wrongRefs:true},'删除预检与勾选的设备不一致，本批没有提交。'],
    ['stale-snapshot',{previewError:true},'列表快照已变化，请重读列表。']
  ])await run('guard-'+name,async()=>{await mount({kind:'machine',label:'设备',mode:'bulk',rows:2,...spec});await start(false);await page.getByText(message,{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:/^确认删除/}).count(),0);assert.equal(await page.evaluate(()=>fixture.commands.length),0);});
  await run('guard-missing-category-template-and-file',async()=>{await mount({kind:'op_type',label:'工种',mode:'import'});await file();await page.getByRole('button',{name:'下载模板',exact:true}).click();await page.getByText(/缺少工种类别/).waitFor();await start(false);await page.getByText(/缺少工种类别/).waitFor();assert.equal(await page.evaluate(()=>fixture.previews.length+fixture.downloads.length),0);});
  await run('guard-no-ack-required-import',async()=>{await mount({...resources[3],mode:'import',rows:2,noAck:true});await file();await start();assert.equal(await page.getByRole('checkbox').count(),0);await page.getByRole('button',{name:'确认导入',exact:true}).click();await page.waitForFunction(()=>fixture.committed.length===1);assert.deepEqual(await page.evaluate(()=>Object.keys(fixture.commands[0].body.input)),['preview_ref']);});
  await run('guard-category-export-mismatch',async()=>{await mount({...resources[1],mode:'export',wrongCategory:true});await page.getByRole('radio',{name:/全部外协工种/}).check();await start(false);await page.getByText('导出预检工种类别与当前范围不一致，没有开始下载。',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>fixture.downloads.length),0);});
  await run('guard-demo-expired-capability',async()=>{for(const spec of [{source:'demo'},{expired:true},{deny:true}]){await mount({...resources[2],mode:'bulk',rows:2,...spec});await start();await page.getByRole('checkbox').check();assert(await page.getByRole('button',{name:/^确认删除/}).isDisabled());assert.equal(await page.evaluate(()=>fixture.commands.length),0);}});
  await run('guard-empty-and-mismatched-selection',async()=>{await mount({...resources[2],mode:'bulk',selectionCount:0});await start(false);await page.getByText('未选中设备，请选择后重试。',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>fixture.previews.length),0);for(const wrongCount of [false,true]){await mount({...resources[2],mode:'export',selectionCount:0,wrongCount});await page.getByRole('radio',{name:/已选设备/}).check();await start(false);await page.getByText(wrongCount?'导出预检数量与勾选的设备不一致，没有开始下载。':'0',{exact:true}).waitFor();assert.deepEqual(await page.evaluate(()=>fixture.previews[0].body.refs),[]);}});
  await run('guard-malformed-receipt-locks',async()=>{await mount({...resources[2],mode:'bulk',rows:2,malformedReceipt:true});await start();await page.getByRole('checkbox').check();await page.getByRole('button',{name:'确认删除',exact:true}).click();await page.getByRole('button',{name:'查询结果',exact:true}).waitFor();assert(await page.getByRole('button',{name:/^取消/}).isDisabled());assert.equal(await page.evaluate(()=>fixture.committed.length),0);});
  await run('guard-rejected-does-not-retry',async()=>{await mount({...resources[3],mode:'bulk',rows:2,rejected:true});await start();await page.getByRole('checkbox').check();await page.getByRole('button',{name:'确认删除',exact:true}).click();await page.getByText('数据已变化，本批未写入。',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>fixture.commands.length),1);assert(await page.getByRole('button',{name:/^确认删除/}).isDisabled());});
  await run('guard-cancel-read-and-download',async()=>{for(const downloading of [false,true]){await mount({...resources[4],mode:downloading?'import':'bulk',rows:2,delay:500,downloadDelay:downloading});await page.getByRole('button',{name:downloading?'下载模板':'开始预检',exact:true}).click();await page.getByText(downloading?'正在读取下载文件…':'正在读取完整预检结果，尚未写入数据…',{exact:true}).waitFor();await page.getByRole('button',{name:'取消',exact:true}).click();await page.waitForFunction(()=>fixture.aborted===1);assert.equal(await page.evaluate(()=>fixture.commands.length+fixture.committed.length),0);}});
  await run('guard-mime-filename-signature',async()=>{for(const spec of [{badDownload:true},{badFilename:true}]){await mount({...resources[3],mode:'import',...spec});await page.getByRole('button',{name:'下载模板',exact:true}).click();await page.getByText(spec.badDownload?'下载内容或文件类型不正确，没有把错误内容保存成文件。':'下载文件名与所选格式不一致，没有保存文件。',{exact:true}).waitFor();assert.equal(await page.getByText(/已交给浏览器下载/).count(),0);}await mount({...resources[3],mode:'import'});await page.getByLabel('选择人员导入文件').setInputFiles({name:'invalid.xlsx',mimeType:'application/octet-stream',buffer:Buffer.from('not a workbook')});await start(false);await page.getByText('文件内容不是 XLSX 工作簿，请勿只修改扩展名。',{exact:true}).waitFor();assert.equal(await page.evaluate(()=>fixture.previews.length),0);});
}
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
  try{
    browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-background-networking']});result.browser=browser.version();assert.match(result.browser,/^109\./);
    const origin='http://127.0.0.1:'+server.address().port;
    for(const viewport of [{width:1920,height:1080},{width:1392,height:924}])for(const theme of ['light','dark']){
      variant=viewport.width+'x'+viewport.height+'-'+theme;const context=await browser.newContext({viewport,acceptDownloads:true});await context.addInitScript(theme=>{localStorage.setItem('aps_theme',theme);localStorage.setItem('aps_kit_theme',theme);},theme);page=await context.newPage();page.setDefaultTimeout(10000);
      page.on('pageerror',error=>result.errors.push(error.message));page.on('console',message=>{if(message.type()==='error')result.errors.push(message.text());});
      await page.route('**/*',route=>{if(!route.request().url().startsWith(origin+'/')){result.external.push(route.request().url());return route.abort();}return route.continue();});
      await page.goto(origin);for(const resource of resources)await resourceCases(resource);await guardCases();await context.close();
    }
    assert.deepEqual(result.errors,[]);assert.deepEqual(result.external,[]);
  }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));fs.writeFileSync(path.join(output,'resource-file-result.json'),JSON.stringify(result,null,2)+'\n');}
  console.log(JSON.stringify({output,browser:result.browser,cases:result.cases.length,screenshots:result.screenshots.length,errors:result.errors,scope:result.scope}));
})().catch(error=>{console.error(error);process.exitCode=1;});
