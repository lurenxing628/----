'use strict';
// Short-screen application layout (issue 2026-09-14-wbui-double-scroll-1366, plan B) against the real isolated Flask app.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const ready=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),root=path.resolve(ready.root),origin=new URL(ready.url).origin;
const executablePath=process.env.WORKBENCH_BROWSER||'/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium';
const SHORT_MAX=820; // --wb-short-screen-max
const report={scope:'short-screen-application-layout',build_id:ready.assets&&ready.assets.build_id,browser:'',cases:[],errors:[],external:[]};
const frameSelector={batches:'.batch-workspace.wb-fill-viewport > .wb-table-frame',process:'.process-workspace.wb-fill-viewport > .wb-table-frame'};

async function settle(page){
  await page.waitForFunction(()=>!document.querySelector('[aria-busy="true"]'),null,{timeout:20000});
  await page.evaluate(()=>document.fonts.ready);
}
async function measure(page,selector){
  return page.evaluate(selector=>{
    const frame=document.querySelector(selector);if(!frame)throw new Error('Missing table frame: '+selector);
    const rect=frame.getBoundingClientRect(),main=document.querySelector('main.page-content');
    const chain=[];for(let el=frame;el&&el!==main.parentElement;el=el.parentElement){const cs=getComputedStyle(el);chain.push({cls:el.className||el.tagName,display:cs.display,flex:cs.flex,minHeight:cs.minHeight,height:Math.round(el.getBoundingClientRect().height),scroll:el.scrollHeight});}
    const below=[...frame.parentElement.children].filter(el=>{const r=el.getBoundingClientRect();return r.height>0&&r.bottom>innerHeight+1;}).map(el=>el.className);
    return {innerHeight,windowScrollHeight:document.scrollingElement.scrollHeight,frameTop:rect.top,frameBottom:rect.bottom,frameHeight:rect.height,
      frameMaxHeight:getComputedStyle(frame).maxHeight,frameScrollHeight:frame.scrollHeight,frameClientHeight:frame.clientHeight,
      mainScrollHeight:main.scrollHeight,mainClientHeight:main.clientHeight,mainOverflowY:getComputedStyle(main).overflowY,
      scrollKey:main.getAttribute('data-wb-scroll-key'),below,chain};
  },selector);
}
function assertFits(geometry,label){
  assert(geometry.windowScrollHeight<=geometry.innerHeight+1,label+': window must not scroll '+JSON.stringify(geometry));
  assert.equal(geometry.frameMaxHeight,'none',label+': table frame is no longer capped by --wb-table-max-height');
  assert(geometry.frameBottom<=geometry.innerHeight+1,label+': table frame ends inside the viewport '+JSON.stringify(geometry));
  assert(geometry.frameHeight>=180,label+': table frame keeps at least 180px');
  assert.deepEqual(geometry.below,[],label+': nothing in the workspace is pushed below the fold');
  assert.equal(geometry.scrollKey,'page-content',label+': the fallback scroller is covered by scroll memory');
}

(async()=>{
  const browser=await chromium.launch({executablePath,headless:true});
  try {
    assert(browser.version().startsWith('109.'),'Actual Chromium 109 required');report.browser=browser.version();
    // 1366x640 is a maximised browser on a 1366x768 screen once the tab strip, address bar and taskbar are subtracted.
    for(const viewport of [{width:1366,height:768},{width:1366,height:640},{width:1280,height:720},{width:1920,height:1080}]) {
      const short=viewport.height<=SHORT_MAX,size=viewport.width+'x'+viewport.height;
      for(const view of ['batches','process']) {
        const state=view+'@'+size;
        const context=await browser.newContext({viewport});
        await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&new URL(url).origin!==origin){report.external.push({state,url});return route.abort();}return route.continue();});
        const page=await context.newPage();page.setDefaultTimeout(15000);
        page.on('pageerror',error=>report.errors.push({state,error:error.message}));
        page.on('console',message=>{if(message.type()==='error')report.errors.push({state,text:message.text()});});
        await page.goto(origin+'/workbench?view='+view);
        if(view==='process'){
          // ?view=process lands on the default node (物料); the process chip exists in both the compact strip and the full rail.
          const chip=page.locator('[data-rail-node="process"]');await chip.waitFor();await settle(page);
          assert.equal(await page.getByRole('button',{name:'展开产能链'}).count(),short?1:0,state+': landing on a node collapses the rail only on short screens');
          await chip.click();
        }
        await page.locator(frameSelector[view]).waitFor();await settle(page);
        const toggle=page.getByRole('button',{name:/^(展开|收起)产能链$/});
        const geometry=await measure(page,frameSelector[view]);
        const record={state,short,geometry,checks:[]};
        if(short){
          assertFits(geometry,state);record.checks.push('window-fixed','frame-fills','nothing-below-fold');
          if(view==='process'){
            assert.equal(await toggle.innerText(),'展开产能链',state+': rail starts collapsed with the node selected');
            assert.equal(await page.locator('.hb-cal-block').count(),0,state+': full rail hidden while collapsed');
            assert.equal(await page.locator('.rail-compact [data-rail-node="process"]').getAttribute('aria-pressed'),'true');
            assert.equal(await page.locator('.rail-compact [data-rail-node]').count(),8,state+': seven nodes plus the calendar chip');
            await toggle.click();await page.locator('.hb-cal-block').waitFor();
            const expanded=await measure(page,frameSelector[view]);record.expanded=expanded;
            assert(expanded.windowScrollHeight<=expanded.innerHeight+1,state+': window still fixed with the rail expanded');
            assert(expanded.mainScrollHeight>expanded.mainClientHeight&&expanded.mainOverflowY==='auto',state+': page-content takes over scrolling as the fallback '+JSON.stringify(expanded));
            await page.locator('main.page-content').evaluate(main=>{main.scrollTop=main.scrollHeight;});
            await page.getByRole('button',{name:'收起产能链'}).click();await page.locator('.rail-compact').waitFor();
            assertFits(await measure(page,frameSelector[view]),state+' (re-collapsed)');
            record.checks.push('rail-collapsed-by-default','rail-expand-fallback-scroll','rail-recollapse');
          }
        } else {
          assert.notEqual(geometry.frameMaxHeight,'none',state+': tall screens keep the capped table frame');
          assert.equal(await toggle.count(),0,state+': tall screens have no rail toggle');
          if(view==='process')assert.equal(await page.locator('.hb-cal-block').count(),1,state+': full rail on tall screens');
          record.checks.push('tall-screen-unchanged');
        }
        const screenshot='short-screen-'+view+'-'+size+'.png';await page.screenshot({path:path.join(root,screenshot)});record.screenshot=screenshot;
        report.cases.push(record);await context.close();
      }
    }
  } catch(error) {report.errors.push({fatal:error.message});throw error;}
  finally {await browser.close();fs.writeFileSync(path.join(root,'probe-results.json'),JSON.stringify(report,null,2));}
})().catch(error=>{console.error(error);process.exit(1);});
