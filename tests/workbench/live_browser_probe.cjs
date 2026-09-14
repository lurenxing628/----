'use strict';

const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const {API_PATH,Recorder,trackReads,settleReads,realRead,tab,layout,diagnostic}=require('./live_browser_support.cjs');
const readyFile=process.argv[2];
if(!readyFile) throw new Error('Usage: node live_browser_probe.cjs <isolated-root/server-ready.json>');
const ready=JSON.parse(fs.readFileSync(readyFile,'utf8'));
const root=path.resolve(ready.root),origin=new URL(ready.url).origin,record=new Recorder(root);
const executablePath=process.env.WORKBENCH_BROWSER || '/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium';
const nav=[['process','基础资料'],['batches','批次管理'],['run','执行排产'],['analysis','选择排产方案'],['trial','试调'],
  ['gantt','计划甘特'],['field','现场记录'],['fieldgantt','现场实际甘特'],['review','执行复盘'],
  ['reports','报表中心'],['calib','工时定额校准'],['dashboard','值班台'],['basedata','资料总览']];

async function scenario(browser,viewport,theme) {
  const state=viewport.width+'x'+viewport.height+'-'+theme;
  const context=await browser.newContext({viewport,acceptDownloads:true});
  await context.addInitScript(theme=>{
    if(!localStorage.getItem('live_probe_seeded')){
      localStorage.setItem('aps_kit_theme',theme);localStorage.setItem('aps_theme',theme);localStorage.setItem('live_probe_seeded','1');
    }
  },theme);
  await context.route('**/*',route=>{
    const url=route.request().url();
    if(/^https?:/.test(url) && new URL(url).origin!==origin){record.report.external_requests.push({state,url});return route.abort();}
    return route.continue();
  });
  const page=await context.newPage();page.setDefaultTimeout(12000);trackReads(page);
  page.on('pageerror',error=>record.report.page_errors.push({state,error:error.message}));
  page.on('console',message=>{if(message.type()==='error')record.report.console_errors.push({state,text:message.text(),location:message.location()});});
  page.on('requestfailed',request=>record.report.failed_requests.push({state,url:request.url(),failure:request.failure()}));
  page.on('response',response=>{if(response.status()>=400)record.report.http_errors.push({state,url:response.url(),status:response.status()});});
  let last;
  try {
    const initial=await record.run(page,state,'initial-real-and-eight-checks',async()=>{
      last=await realRead(page,()=>page.goto(ready.system_url),record,ready.expected);
      await page.evaluate(()=>document.fonts.ready);
      record.equal(await page.locator('html').getAttribute('data-theme'),theme);
      const metric=page.locator('.wb-metric').filter({has:page.getByText('当前页面检查',{exact:true})});
      record.equal((await metric.locator('.wb-metric-value').innerText()).replace(/\s/g,''),'8/8','Initial render, before refresh or theme actions');
      const rows=page.locator('.sm-check-table tbody tr');record.equal(await rows.count(),8);
      record.equal(await rows.filter({hasText:'系统管理样式'}).locator('.sm-status').getAttribute('data-state'),'available');
      record.ok(!(await rows.filter({hasText:'管理资源模型'}).innerText()).includes('尚未读取'));
      record.ok((await page.locator('.sm-source-note').innerText()).includes(ready.expected.instance_label));
      record.report.first_render.push({state,checks:8,style:'available',before_theme_action:true});
      await layout(page,record);
    });
    if(!initial)return;
    await record.run(page,state,'initial-diagnostic-before-theme',()=>diagnostic(page,state,'initial',last,ready.expected,record));
    await record.run(page,state,'refresh-real-snapshot',async()=>{
      const previous=last.meta.snapshot_ref;
      last=await realRead(page,()=>page.getByRole('button',{name:'重新检查',exact:true}).click(),record,ready.expected);
      record.ok(last.meta.snapshot_ref!==previous,'Refresh has a new real snapshot');
    });
    await record.run(page,state,'theme-survives-reload',async()=>{
      const other=theme==='dark'?'light':'dark';
      await page.getByRole('button',{name:other==='dark'?'切换深色':'切换浅色',exact:true}).click();
      await page.waitForFunction(other=>document.documentElement.dataset.theme===other,other);
      record.equal(await page.evaluate(()=>localStorage.getItem('aps_kit_theme')),other);
      last=await realRead(page,()=>page.reload(),record,ready.expected);
      record.equal(await page.locator('html').getAttribute('data-theme'),other);
      await page.getByRole('button',{name:theme==='dark'?'切换深色':'切换浅色',exact:true}).click();
      await page.waitForFunction(theme=>document.documentElement.dataset.theme===theme,theme);
      record.equal(await page.evaluate(()=>localStorage.getItem('aps_kit_theme')),theme);
    });
    await record.run(page,state,'four-real-tabs',async()=>{
      for(const id of ['overview','backups','logs','config']){
        await tab(page,id,record);await layout(page,record);
        if(id==='backups'||id==='logs'){
          const selector=id==='backups'?'.sm-backups-table tbody td:nth-child(4) .sm-summary strong':'.sm-logs-table tbody td:nth-child(5) .sm-summary small';
          const cells=await page.locator(selector).evaluateAll(nodes=>nodes.map(node=>{
            const range=document.createRange();range.selectNodeContents(node);
            return {width:node.closest('td').getBoundingClientRect().width,textLines:range.getClientRects().length};
          }));
          record.ok(cells.length>0 && cells.every(cell=>cell.width>=300 && cell.textLines===1),'Normal filenames use the flexible column without arbitrary wrapping');
        }
        await record.shot(page,state,'tab-'+id);
      }
      record.equal(await page.locator('#sm-maintenance-auto_backup_interval_minutes').inputValue(),String(ready.expected.backup_interval_minutes));
    });
    for(const part of ['text','body']) await record.run(page,state,'maintenance-row-'+part,async()=>{
      for(const id of ['backups','logs','config']){
        await tab(page,'overview',record);
        const row=page.locator('.sm-work-row[data-sm-destination="'+id+'"]');
        if(part==='text')await row.locator('.sm-work-title').click();
        else {const box=await row.boundingBox();await row.click({position:{x:5,y:Math.floor(box.height/2)}});}
        await page.locator('#sm-panel-'+id).waitFor({state:'visible'});
        record.equal(await page.locator('#sm-tab-'+id).getAttribute('aria-selected'),'true','Whole-row destination: '+id+'/'+part);
        await settleReads(page);
      }
    });
    for(const [kind,name,option] of [['backups',ready.expected.backup_names[0],null],['logs','launcher.log','启动日志（launcher.log）']]) await record.run(page,state,'detail-escape-'+kind,async()=>{
      await tab(page,kind,record);
      if(kind==='logs'){
        await page.getByLabel('日志来源',{exact:true}).click();
        await page.locator('.wb-control-popup').getByRole('option',{name:option,exact:true}).click();
        const wait=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/workbench/v1/system/logs');
        await page.getByRole('button',{name:'查询',exact:true}).click();const response=await wait;
        record.equal(response.status(),200);const data=(await response.json()).data;
        record.ok(data.rows.length>0&&data.rows.every(row=>row.file===name),'Log source filter reads the actual selected file');
      }
      const row=page.locator('.sm-record-table tbody tr').filter({hasText:name}).first();
      const opener=row.getByRole('button');await opener.click();
      const detail=page.getByRole('region',{name:kind==='backups'?'备份详情':'日志详情',exact:true});await detail.waitFor({state:'visible'});
      record.ok(await detail.evaluate(node=>node===document.activeElement));
      record.ok((await detail.innerText()).includes(name));await record.shot(page,state,'open-detail-'+kind);
      await page.keyboard.press('Escape');await detail.waitFor({state:'detached'});
      record.ok(await opener.evaluate(node=>node===document.activeElement),'Escape restores original file-detail opener focus');
    });
    await record.run(page,state,'failure-only-interception-and-real-retry',async()=>{
      const message='隔离自动化：本次读取失败，请重试。';let remaining=1;
      const matcher=url=>url.origin===origin && url.pathname===API_PATH;
      const handler=route=>{
        if(!remaining)return route.continue();remaining--;
        // An explicit failed envelope, never fake success data; HTTP 200 avoids synthetic browser console errors.
        record.report.injected_failures.push({state,ok:false,http_status:200,url:route.request().url()});
        return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:false,committed:false,
          error:{code:'isolated_probe_failure',message,fields:[],retryable:true,request_ref:'0'.repeat(32)}})});
      };
      await page.route(matcher,handler);
      try {
        await page.getByRole('button',{name:'重新检查',exact:true}).click();
        const alert=page.getByRole('alert').filter({hasText:message});await alert.waitFor({state:'visible'});
        record.equal(await page.locator('.sm-workbench').getAttribute('data-source'),'current');
        record.ok((await page.locator('.sm-workbench').innerText()).includes(message),'Real source error remains explicit');
        last=await realRead(page,()=>alert.getByRole('button',{name:'重试',exact:true}).click(),record,ready.expected);
        record.equal(await alert.count(),0);
      } finally {await page.unroute(matcher,handler);}
    });
    await record.run(page,state,'malformed-200-contract-and-real-retry',async()=>{
      let remaining=1;
      const matcher=url=>url.origin===origin && url.pathname===API_PATH;
      const invalid={ok:true,schema_version:1,meta:{...last.meta,request_ref:'1'.repeat(32),snapshot_ref:'2'.repeat(32)},warnings:[],
        data:Object.fromEntries(['database','backups','logs','config','maintenance'].map(key=>[key,{state:'available'}]))};
      const handler=route=>{
        if(!remaining)return route.continue();remaining--;
        record.report.injected_failures.push({state,kind:'malformed-success-envelope',http_status:200,url:route.request().url()});
        return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(invalid)});
      };
      await page.route(matcher,handler);
      try {
        await page.getByRole('button',{name:'重新检查',exact:true}).click();
        const alert=page.locator('.sm-workbench [role="alert"]');await alert.waitFor({state:'visible'});
        record.ok((await alert.innerText()).length>4,'Malformed 200 is a visible error, not a blank page');
        record.ok((await alert.innerText()).includes('本机系统信息不完整'),'Reject malformed fields after accepting legitimate meta');
        record.equal(await page.locator('.top-title').innerText(),'系统管理');
        record.equal(await page.locator('.sm-workbench').getAttribute('data-source'),'current');
        record.ok(await page.getByRole('button',{name:'导出诊断文件',exact:true}).isDisabled());
        last=await realRead(page,()=>alert.getByRole('button',{name:'重试',exact:true}).click(),record,ready.expected);
        record.equal(await alert.count(),0);
      } finally {await page.unroute(matcher,handler);}
    });
    await record.run(page,state,'sample-isolation-and-real-return',async()=>{
      const calls=record.report.api_responses.length;
      let requests=0;const count=request=>{if(new URL(request.url()).pathname===API_PATH)requests++;};page.on('request',count);
      try {
        await page.locator('input[name="sm-source"][value="sample"]').check();
        await page.waitForFunction(()=>document.querySelector('.sm-workbench')?.dataset.source==='sample');
        record.ok(await page.getByRole('button',{name:'导出诊断文件',exact:true}).isDisabled());
        for(const id of ['overview','backups','logs','config']){await tab(page,id,record);await layout(page,record);}
        const input=page.locator('#sm-auto_backup_interval_minutes');await input.fill('123');
        await page.getByRole('button',{name:'检查参数',exact:true}).click();
        await page.locator('.sm-preview').waitFor({state:'visible'});
        record.equal(await input.inputValue(),'123');record.equal(requests,0,'Sample actions make no production API calls');
        record.equal(record.report.api_responses.length,calls);await record.shot(page,state,'sample-draft');
      } finally {page.off('request',count);}
      last=await realRead(page,()=>page.locator('input[name="sm-source"][value="current"]').check(),record,ready.expected);
      record.equal(await page.locator('#sm-maintenance-auto_backup_interval_minutes').inputValue(),String(ready.expected.backup_interval_minutes));
      record.equal(await page.locator('.sm-workbench').getAttribute('data-source'),'current');
    });
    await record.run(page,state,'real-diagnostic-content',()=>diagnostic(page,state,'after-sample',last,ready.expected,record));
    await record.run(page,state,'connected-navigation-keeps-real-readonly-data',async()=>{
      const markers={process:'[data-resource-workspace="true"]',batches:'[data-batch-workspace]',run:'[data-preflight-workspace]',
        analysis:'[data-plan-workspace]',trial:'.trial-workspace',gantt:'[data-plan-workspace]',field:'[data-field-workspace]',
        fieldgantt:'[data-actual-gantt]',review:'.er-workbench',reports:'.rw-workbench',calib:'.calibration-live',dashboard:'[data-dashboard-workspace]',basedata:'.master-overview'};
      for(const [id,label] of nav){
        const parent=id==='gantt'?'选择排产方案':id==='review'?'报表中心':null;
        if(parent){
          await page.locator('.sidebar-nav').getByRole('link',{name:parent,exact:true}).click();
          await settleReads(page);
        }
        const pending=page.waitForResponse(response=>new URL(response.url()).pathname.startsWith('/api/workbench/v1/')
          && (response.request().method()==='GET'||response.request().method()==='POST'&&new URL(response.url()).pathname==='/api/workbench/v1/entities/batch/query'));
        if(parent)await page.getByRole('tab',{name:label,exact:true}).click();
        else await page.locator('.sidebar-nav').getByRole('link',{name:label,exact:true}).click();
        if(id==='run') await page.getByRole('button',{name:'选择批次',exact:true}).click();
        const response=await pending;record.equal(response.status(),200);const payload=await response.json();record.equal(payload.ok,true);record.equal(payload.meta.source,'production');
        await page.locator('main '+markers[id]).waitFor({state:'visible'});
        if(id==='process'){
          await page.locator('[data-resource-workspace="true"] .wb-empty-empty').getByText('暂无记录',{exact:true}).waitFor();
          record.ok(await page.getByRole('button',{name:'新增物料',exact:true}).isEnabled(),'Resources have real create context');
        } else {
          record.equal(await page.locator('main [role="status"]').filter({hasText:'此功能尚未开通。'}).count(),0,'Current workspace must not regress to a legacy unavailable placeholder: '+id);
        }
        const url=new URL(page.url());record.equal(id==='trial'?url.pathname:url.searchParams.get('view'),id==='trial'?'/workbench/trial':id);
        await layout(page,record);
        await settleReads(page);
      }
      await page.goto(origin+'/workbench/trial');
      await page.locator('main .trial-workspace').waitFor({state:'visible'});
      await page.evaluate(()=>document.fonts.ready);
      record.equal(await page.locator('.top-title').innerText(),'试调');
      await settleReads(page);
      await page.goto(origin+'/workbench?view=delay');
      await page.locator('main [data-plan-workspace]').waitFor({state:'visible'});
      await page.evaluate(()=>document.fonts.ready);
      record.equal(await page.locator('.top-title').innerText(),'交付风险');
      await settleReads(page);
      last=await realRead(page,()=>page.locator('.sidebar-nav').getByRole('link',{name:'系统管理',exact:true}).click(),record,ready.expected);
      await layout(page,record);
    });
    await record.run(page,state,'no-console-network-or-layout-errors',async()=>{
      for(const key of ['page_errors','console_errors','external_requests','failed_requests','http_errors'])record.equal(record.report[key].filter(row=>row.state===state),[],key);
      await layout(page,record);
    });
  } finally {await context.close();}
}

(async()=>{
  let browser;
  try {
    browser=await chromium.launch({executablePath,headless:true,args:['--disable-background-networking']});
    record.report.browser_version=browser.version();record.report.isolated_root=root;record.report.assets=ready.assets;
    record.ok(browser.version().startsWith('109.'),'Use actual Chromium 109');
    for(const viewport of [{width:1920,height:1080},{width:1392,height:924}])for(const theme of ['light','dark'])await scenario(browser,viewport,theme);
  } catch(error) {record.report.cases.push({state:'infrastructure',name:'probe',status:'failed',error:error.stack});}
  finally {if(browser)await browser.close();const summary=record.save();console.log('WB_LIVE_PROBE '+JSON.stringify({root,...summary}));if(summary.failed)process.exitCode=1;}
})();
