'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const controls=require('./custom_control_actions.cjs');
const ready=JSON.parse(fs.readFileSync(process.argv[2])),root=ready.root,origin=ready.url;
const report={scope:'real-isolated-process-read-preview',input_method:'Playwright click and keyboard.type; fill only clears fields; injected read failure separately recorded',
  build_id:ready.assets.build_id,cases:[],screenshots:[],pagination:[],requests:[],errors:[],external:[],http_errors:[],expected_failures:[],timings:[]};
let page,state;
const workspace=()=>page.locator('[data-process-workspace]');
async function type(field,value){await field.click();await field.fill('');await field.type(value,{delay:1});}
async function list(action){const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/workbench/v1/entities/part');await action();const result=await response;assert.equal(result.status(),200,await result.text());await workspace().getByRole('table',{name:'零件工艺列表',exact:true}).and(page.locator('[aria-busy="false"]')).waitFor();return result.json();}
async function enter(restored=false){const tile=page.locator('.hb-tile').filter({hasText:/^工艺/});if(restored){await workspace().getByRole('table',{name:'零件工艺列表',exact:true}).and(page.locator('[aria-busy="false"]')).waitFor();await tile.click();}else await list(()=>tile.click());}
async function search(text){await type(workspace().getByRole('searchbox',{name:'搜索图号、名称、路线',exact:true}),text);return list(()=>workspace().getByRole('button',{name:'搜索',exact:true}).click());}
async function actionCapabilities(result){
  const create=()=>workspace().getByRole('button',{name:/^新增零件/}),importRoute=()=>workspace().getByRole('button',{name:/^导入工艺路线/});
  const posts=()=>report.requests.filter(row=>row.state===state&&row.method==='POST').length;
  assert.equal(result.meta.source,'production');assert.equal(result.data.capabilities.create,true);assert.equal(result.data.capabilities.import,true);
  assert.equal(result.data.create_context.capabilities['process.create'],true);assert.equal(posts(),0);
  assert(await create().isEnabled());assert(await importRoute().isEnabled());
  await create().click();let dialog=page.getByRole('dialog',{name:'新增零件',exact:true});await dialog.waitFor();
  assert.equal(await dialog.getByRole('textbox',{name:'图号',exact:true}).inputValue(),'');
  await dialog.getByRole('button',{name:'取消',exact:true}).click();await dialog.waitFor({state:'detached'});
  await importRoute().click();dialog=page.getByRole('dialog',{name:'导入工艺路线',exact:true});await dialog.waitFor();
  assert(await dialog.getByLabel('选择工艺路线文件',{exact:true}).isEnabled());
  await dialog.getByRole('button',{name:'取消',exact:true}).click();await dialog.waitFor({state:'detached'});assert.equal(posts(),0);
  const injections=[],pattern=origin+'/api/workbench/v1/entities/part?*';
  for(const mode of ['readonly-capabilities','invalid-source']){
    // Negative fixtures change only permission/source fields on a real GET response.
    const handler=async route=>{
      assert.equal(route.request().method(),'GET');const response=await route.fetch();assert.equal(response.status(),200);
      const body=await response.json();assert.equal(body.meta.source,'production');
      assert.equal(body.data.capabilities.create,true);assert.equal(body.data.capabilities.import,true);
      injections.push({mode,original_source:body.meta.source,original_create:body.data.capabilities.create,original_import:body.data.capabilities.import});
      if(mode==='readonly-capabilities'){body.data.capabilities.create=false;body.data.capabilities.import=false;body.data.create_context.capabilities['process.create']=false;}
      else body.meta.source='invalid-test-source';
      await route.fulfill({response,json:body});
    };
    await page.route(pattern,handler);
    try{
      await list(()=>workspace().getByRole('button',{name:'刷新工艺列表',exact:true}).click());
      if(mode==='invalid-source')await workspace().getByText('读到的数据不完整，请刷新重试。',{exact:true}).waitFor();
      assert(await create().isDisabled());assert(await importRoute().isDisabled());assert.equal(await page.getByRole('dialog').count(),0);assert.equal(posts(),0);
    }finally{await page.unroute(pattern,handler);}
    const restored=await list(()=>workspace().getByRole('button',{name:'刷新工艺列表',exact:true}).click());
    assert.equal(restored.meta.source,'production');assert.equal(restored.data.capabilities.create,true);assert.equal(restored.data.capabilities.import,true);
    assert(await create().isEnabled());assert(await importRoute().isEnabled());
  }
  assert.deepEqual(injections.map(row=>row.mode),['readonly-capabilities','invalid-source']);assert.equal(posts(),0);
  report.capability_checks=(report.capability_checks||[]).concat({state,source:result.meta.source,create:true,import:true,dialogs_cancelled:2,injections,posts:posts()});
}
async function open(code){await workspace().getByRole('button',{name:'查看 '+code,exact:true}).click();await page.getByRole('tablist',{name:'零件工艺步骤',exact:true}).waitFor();}
async function routeEntry(){await page.getByRole('tab',{name:/^1 工艺路线/}).click();await page.getByRole('button',{name:'录入路线',exact:true}).click();await page.getByRole('dialog',{name:/^录入工艺路线 · /}).waitFor();}
async function preflight(){const response=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/route-preview'));await page.getByRole('button',{name:'预检路线',exact:true}).click();const result=await response;assert.equal(result.status(),200,await result.text());await page.locator('[data-process-preview]').waitFor();return result.json();}
async function closeDetail(discard=false){
  await page.getByRole('button',{name:'关闭详情',exact:true}).click();
  if(discard){const prompt=page.getByRole('dialog',{name:'放弃未保存的工艺草稿？',exact:true});await prompt.waitFor();await prompt.getByRole('button',{name:'放弃草稿并关闭',exact:true}).click();}
  await page.getByRole('tablist',{name:'零件工艺步骤',exact:true}).waitFor({state:'detached'});
  assert.equal(await page.getByRole('dialog').count(),0);
}
async function readAllOperations(name,expected){
  const dialog=page.getByRole('dialog'),grid=dialog.getByRole('table',{name,exact:true});
  const rows=grid.locator('tbody tr'),numbers=grid.locator('tbody tr td:first-child b');
  const size=dialog.getByRole('combobox',{name:'每页条数',exact:true});
  const pager=size.locator('xpath=ancestor::nav');
  assert.equal(await size.inputValue(),'50');
  assert.deepEqual(await size.locator('option').evaluateAll(nodes=>nodes.map(node=>node.value)),['20','50','100']);
  for(const value of ['20','100','50']){
    await controls.select(size,value);assert.equal(await rows.count(),Number(value));
    assert.deepEqual(await numbers.allTextContents(),expected.slice(0,Number(value)));
    assert(await pager.getByText('共 '+expected.length+' 项 · 第 1 / '+Math.ceil(expected.length/Number(value))+' 页',{exact:true}).isVisible());
  }
  const sequences=[],pages=[],next=dialog.getByRole('button',{name:'下一页',exact:true}),count=Math.ceil(expected.length/50);
  for(let number=1;number<=count;number++){
    assert(await pager.getByText('共 '+expected.length+' 项 · 第 '+number+' / '+count+' 页',{exact:true}).isVisible());
    const values=await numbers.allTextContents(),wanted=expected.slice((number-1)*50,number*50);
    assert.equal(await rows.count(),wanted.length);assert(values.length>0&&values.length<=50);
    assert.deepEqual(values,wanted,name+' page '+number);
    assert.equal(await dialog.getByRole('button',{name:'上一页',exact:true}).isDisabled(),number===1);
    sequences.push(...values);pages.push({number,count:values.length,first:values[0],last:values.at(-1)});
    assert.equal(await next.isDisabled(),number===count);if(number<count)await next.click();
  }
  assert.deepEqual(sequences,expected);assert.equal(new Set(sequences).size,expected.length);
  report.pagination.push({state,table:name,page_size:50,next_clicks:count-1,total:sequences.length,pages,sequences});
}
async function shot(name){const file=state+'-'+name+'.png';await page.screenshot({path:path.join(root,'screenshots',file)});const geo=await page.evaluate(()=>({viewport:[innerWidth,innerHeight],scrollWidth:document.documentElement.scrollWidth,dialogs:Array.from(document.querySelectorAll('[role="dialog"]')).filter(n=>n.getClientRects().length&&getComputedStyle(n).visibility!=='hidden').map(n=>{const r=n.getBoundingClientRect();return{left:r.left,right:r.right,top:r.top,bottom:r.bottom};})}));assert(geo.scrollWidth<=geo.viewport[0]+1,JSON.stringify(geo));assert(geo.dialogs.length<=1,JSON.stringify(geo));assert(geo.dialogs.every(r=>r.left>=0&&r.right<=geo.viewport[0]+1&&r.top>=0&&r.bottom<=geo.viewport[1]+1),JSON.stringify(geo));report.screenshots.push({state,name,file,geometry:geo});}
async function run(name,fn){try{await fn();await shot(name);report.cases.push({state,name,passed:true});console.log(state+' / '+name+': passed');}catch(error){report.cases.push({state,name,passed:false,error:error.stack});await page.screenshot({path:path.join(root,'screenshots',state+'-'+name+'-FAILED.png')});throw error;}}
async function cases(){
  await run('query-paging-selection-custom-size',async()=>{
    assert.equal(await workspace().locator('tbody tr[data-process-ref]').count(),20);
    await workspace().getByRole('checkbox',{name:'全选当前页',exact:true}).check();
    await list(()=>workspace().getByRole('button',{name:'下一页',exact:true}).click());
    assert.equal(await workspace().locator('tbody tr[data-process-ref]').count(),11);
    assert.equal(await workspace().locator('[data-process-selection-count]').textContent(),'20');
    await workspace().getByRole('checkbox',{name:'全选当前页',exact:true}).check();assert.equal(await workspace().locator('[data-process-selection-count]').textContent(),'31');
    await workspace().getByRole('button',{name:'清除所有选择',exact:true}).click();
    await list(()=>controls.select(workspace().getByRole('combobox',{name:'每页条数',exact:true}),'50'));
    assert.equal(await workspace().locator('tbody tr[data-process-ref]').count(),31);
    const found=await search('热处理');assert.equal(found.data.page.total,1);await search('');
  });
  await run('stage-sort-empty-and-explicit-unavailable-actions',async()=>{
    const result=await list(()=>workspace().getByRole('tab',{name:/^待定归属/}).click());assert.equal(result.data.page.total,3);
    await list(()=>workspace().getByRole('tab',{name:/^已就绪/}).click());await workspace().getByText('当前筛选没有匹配的零件',{exact:true}).waitFor();
    await list(()=>workspace().getByRole('tab',{name:/^全部/}).click());
    let current;for(const order of ['ascending','descending','none']){current=await list(()=>workspace().getByRole('button',{name:'图号排序',exact:true}).click());assert.equal(await workspace().locator('th').filter({has:page.getByRole('button',{name:'图号排序',exact:true})}).getAttribute('aria-sort'),order);}
    await actionCapabilities(current);
  });
  await run('actual-template-stages-hours-and-group-preserved',async()=>{
    await search('PROC-001');await open('PROC-001');
    assert(await page.getByRole('tab',{name:/^1 工艺路线/,selected:true}).isVisible());
    assert(await page.getByRole('table',{name:'路线工序明细',exact:true}).isVisible());
    assert.equal(await page.getByRole('table',{name:'归属明细',exact:true}).count(),0);
    await page.getByRole('tab',{name:/^3 工时定额/}).click();
    assert.equal(await page.getByLabel('工序 10 单件工时',{exact:true}).inputValue(),'0.125');
    assert.equal(await page.getByLabel('工序 30 单件工时',{exact:true}).inputValue(),'0');
    assert(await page.getByLabel('工序 10 单件工时',{exact:true}).isDisabled());
    assert.equal(await page.getByLabel('工序 20 单件工时',{exact:true}).count(),0);assert.equal(await page.getByLabel('工序 10 外协周期',{exact:true}).count(),0);
    const colors=await page.locator('.process-detail .stp[aria-selected="false"] .stp-t').evaluateAll(nodes=>nodes.map(node=>({label:node.textContent,color:getComputedStyle(node).color,expected:getComputedStyle(node.closest('.modal').querySelector('.modal-h2')).color})));
    assert(colors.length===2&&colors.every(row=>row.color===row.expected),'Inactive steps must use readable theme text');report.step_colors=(report.step_colors||[]).concat({state,colors});
    for(const name of ['自制工时明细','外协周期明细']) assert(await page.getByRole('table',{name,exact:true}).evaluate(table=>table.getBoundingClientRect().width<=table.parentElement.clientWidth+1),'Hour columns must fit the normal desktop dialog: '+name);
    const group=page.getByRole('table',{name:'外协组原记录',exact:true}).getByRole('spinbutton');
    assert.equal(await group.inputValue(),'6.75');assert(await group.isDisabled());
    await shot('hours-and-group');await closeDetail();
    await open('PROC-001');await routeEntry();await type(page.getByRole('textbox',{name:'路线文字',exact:true}),'10车削;20热处理;40未建工种');
    const result=await preflight();assert.equal(result.data.counts.unknown,1);assert.equal(result.data.operations[2].source_suggestion,null);
    assert.deepEqual(result.data.changes.removed,[30]);assert(await page.getByRole('button',{name:/^确认保存路线/}).isEnabled());
    await shot('text-preview');await page.getByRole('button',{name:'取消',exact:true}).click();
    assert.equal(await page.getByRole('textbox',{name:'路线文字',exact:true}).count(),0);
    await routeEntry();assert.equal(await page.getByRole('textbox',{name:'路线文字',exact:true}).inputValue(),'10车削;20热处理;40未建工种');
    assert.equal(await page.locator('[data-process-preview]').count(),0);
    await page.getByRole('button',{name:'取消',exact:true}).click();await closeDetail(true);
  });
  await run('row-input-duplicate-validation-and-cancel',async()=>{
    await search('PROC-002');await open('PROC-002');await routeEntry();await page.getByRole('tab',{name:'逐行表格',exact:true}).click();
    await type(page.getByRole('textbox',{name:'第 1 行工序号',exact:true}),'10');await type(page.getByRole('combobox',{name:'第 1 行工种',exact:true}),'车削');
    await page.getByRole('button',{name:'新增工序',exact:true}).click();await type(page.getByRole('textbox',{name:'第 2 行工序号',exact:true}),'10');await type(page.getByRole('combobox',{name:'第 2 行工种',exact:true}),'检验');
    let result=await preflight();assert(!result.data.can_confirm_route);assert(result.data.diagnostics.some(x=>x.code==='duplicate_sequence'));
    await type(page.getByRole('textbox',{name:'第 2 行工序号',exact:true}),'30');result=await preflight();assert(result.data.can_confirm_route);assert.deepEqual(result.data.changes.added,[10,30]);
    await shot('row-preview');await page.getByRole('button',{name:'删除第 2 行',exact:true}).click();assert.equal(await page.locator('[data-process-preview]').count(),0);
    await page.keyboard.press('Escape');await routeEntry();
    assert.equal(await page.getByRole('textbox',{name:'第 1 行工序号',exact:true}).inputValue(),'10');
    assert.equal(await page.getByRole('combobox',{name:'第 1 行工种',exact:true}).inputValue(),'车削');
    assert.equal(await page.getByRole('table',{name:'逐行路线录入',exact:true}).locator('tbody tr').count(),1);
    await page.getByRole('button',{name:'取消',exact:true}).click();await closeDetail(true);
    await open('PROC-002');await page.getByRole('tab',{name:/^1 工艺路线/}).click();
    const empty=page.getByRole('table',{name:'路线工序明细',exact:true});assert.equal(await empty.locator('tbody tr').count(),1);
    assert(await empty.getByText('尚无工序记录。',{exact:true}).isVisible());await closeDetail();
  });
  await run('read-failure-retry-retains-draft',async()=>{
    await search('PROC-001');await open('PROC-001');await routeEntry();await type(page.getByRole('textbox',{name:'路线文字',exact:true}),'10车削20检验');
    const pattern='**/process/*/route-preview';let injected=false;
    const handler=async route=>{if(injected)return route.continue();injected=true;report.expected_failures.push({state,url:route.request().url(),status:500});return route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({ok:false,committed:false,error:{code:'storage_failure',message:'隔离测试：读取失败，未保存。',fields:[],retryable:true,request_ref:'injected'}})});};
    await page.route(pattern,handler);await page.getByRole('button',{name:'预检路线',exact:true}).click();await page.getByText('隔离测试：读取失败，未保存。',{exact:true}).waitFor();
    assert.equal(await page.getByRole('textbox',{name:'路线文字',exact:true}).inputValue(),'10车削20检验');await page.unroute(pattern,handler);
    const response=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/route-preview'));await page.getByRole('button',{name:'重试预检',exact:true}).click();assert.equal((await response).status(),200);await page.locator('[data-process-preview]').waitFor();
    await shot('recovered-preview');await page.getByRole('button',{name:'取消',exact:true}).click();await closeDetail(true);
  });
  await run('two-thousand-operation-detail-and-reload',async()=>{
    await search('PROC-LARGE');const begin=Date.now();await open('PROC-LARGE');
    const expected=Array.from({length:2000},(_,index)=>String(index+1));
    for(const [stage,name] of [[/^1 工艺路线/,'路线工序明细'],[/^2 归属/,'归属明细'],[/^3 工时定额/,'自制工时明细']]){
      await page.getByRole('tab',{name:stage}).click();await readAllOperations(name,expected);
    }
    report.timings.push({state,action:'2000-operation-detail',milliseconds:Date.now()-begin});await shot('large-detail');await closeDetail();
    await page.reload();await page.locator('.hb-tile').first().waitFor();await enter(true);
    assert.equal(await workspace().getByRole('searchbox',{name:'搜索图号、名称、路线',exact:true}).inputValue(),'PROC-LARGE');
    await search('PROC-001');await open('PROC-001');
    await page.getByRole('tab',{name:/^3 工时定额/}).click();assert.equal(await page.getByLabel('工序 10 单件工时',{exact:true}).inputValue(),'0.125');await closeDetail();
  });
}
(async()=>{let browser;try{browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true});report.browser=await browser.version();assert(report.browser.startsWith('109.'));
  for(const viewport of [{width:1920,height:1080},{width:1392,height:924}])for(const theme of ['light','dark']){state=viewport.width+'-'+theme;const context=await browser.newContext({viewport,timezoneId:'Asia/Shanghai'});await context.addInitScript(value=>{localStorage.setItem('aps_theme',value);localStorage.setItem('aps_kit_theme',value);},theme);page=await context.newPage();page.setDefaultTimeout(15000);
    page.on('pageerror',error=>report.errors.push({state,message:error.stack}));page.on('request',r=>{if(!r.url().startsWith(origin+'/')&&!r.url().startsWith('data:'))report.external.push(r.url());if(r.url().startsWith(origin+'/api/'))report.requests.push({state,method:r.method(),path:new URL(r.url()).pathname});});page.on('response',r=>{if(r.status()>=400)report.http_errors.push({state,url:r.url(),status:r.status()});});
    await page.goto(ready.resource_url);await page.locator('.hb-tile').first().waitFor();await enter();await cases();await context.close();}
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.external,[]);assert(report.http_errors.every(row=>report.expected_failures.some(expected=>expected.state===row.state&&expected.url===row.url&&expected.status===row.status)));
  assert(report.requests.some(row=>row.method==='POST'));assert(report.requests.every(row=>['GET','HEAD'].includes(row.method)||row.method==='POST'&&row.path.endsWith('/route-preview')));
}finally{if(browser)await browser.close();report.summary={cases:report.cases.length,failed:report.cases.filter(x=>!x.passed).length,screenshots:report.screenshots.length,read_requests:report.requests.length,previews:report.requests.filter(x=>x.method==='POST').length};fs.writeFileSync(path.join(root,'process-probe-results.json'),JSON.stringify(report,null,2)+'\n');}console.log(JSON.stringify(report.summary));})().catch(error=>{console.error(error);process.exitCode=1;});
