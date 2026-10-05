'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('playwright');
const directory=__dirname, info=JSON.parse(fs.readFileSync(path.join(directory,'browser-targets.json'),'utf8'));
const repetitions=Number(process.env.APS_PERF_REPETITIONS||7);
const selectors={material:'.wb-table[aria-busy="false"]',plan:'.plan-main',actual:'[data-actual-scroll]',candidate:'.rc-main'};
const init=String.raw`(() => {
  window.__apsPerf={ready:null,requests:[],errors:[]};
  const original=window.fetch;
  window.fetch=function(...args){const start=performance.now();return original.apply(this,args).then(response=>{
    window.__apsPerf.requests.push({url:String(args[0]),status:response.status,start,end:performance.now()});return response;});};
  const params=new URLSearchParams(location.search),view=params.get('view');
  const selector=view==='process'?'.wb-table[aria-busy="false"]':view==='gantt'?'.plan-main':view==='fieldgantt'?'[data-actual-scroll]':'.rc-main';
  let waiting=false;
  function detect(){
    if(waiting||window.__apsPerf.ready!==null)return;
    const node=document.querySelector(selector);
    if(!node||!node.getClientRects().length)return;
    if(view==='process'&&!node.textContent.includes('MAT-001'))return;
    waiting=true;
    requestAnimationFrame(()=>requestAnimationFrame(()=>{window.__apsPerf.ready=performance.now();observer.disconnect();}));
  }
  const observer=new MutationObserver(detect);
  document.addEventListener('DOMContentLoaded',()=>{observer.observe(document.documentElement,{childList:true,subtree:true,attributes:true});detect();});
})();`;
function url(target,topic){
  if(topic==='material')return target.url+'/workbench?view=process';
  if(topic==='actual')return target.url+'/workbench?view=fieldgantt';
  if(topic==='candidate')return target.url+'/workbench?view=run&nav='+encodeURIComponent(JSON.stringify({version:1,view:'run',context:{run_ref:target.run_ref}}));
  const view={plan:'gantt',actual:'fieldgantt',candidate:'analysis'}[topic];
  const context=topic==='candidate'?{run_ref:target.run_ref,candidate_ref:target.candidate_ref}:{plan_ref:target.plan_ref};
  return target.url+'/workbench?view='+view+'&nav='+encodeURIComponent(JSON.stringify({version:1,view,context}));
}
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-gpu','--no-sandbox']});
 const rows=[];
 try{
  for(let iteration=0;iteration<repetitions;iteration++){
   for(const variant of iteration%2?['after','before']:['before','after']){
    for(const topic of Object.keys(selectors)){
     const context=await browser.newContext({viewport:{width:1440,height:900}}),page=await context.newPage(),errors=[];
     page.on('pageerror',e=>errors.push(e.message));
     await context.addInitScript({content:init});
     await page.goto(url(info[variant],topic),{waitUntil:'domcontentloaded',timeout:30000});
     if(topic==='candidate'){
       const candidate=page.locator('[data-candidate-ref="'+info[variant].candidate_ref+'"]');
       await candidate.getByRole('button',{name:'详情',exact:true}).click({timeout:30000});
     }
     try{await page.waitForFunction(()=>window.__apsPerf&&window.__apsPerf.ready!==null,{},{timeout:30000});}
     catch(e){await fs.promises.writeFile(path.join(directory,'browser-'+variant+'-'+topic+'-failure.html'),await page.content());throw e;}
     const metrics=await page.evaluate(()=>({...window.__apsPerf,navigation:performance.getEntriesByType('navigation')[0].toJSON()}));
     assert.deepStrictEqual(errors,[],variant+' '+topic);
     const bad=metrics.requests.filter(r=>r.status>=400);assert.deepStrictEqual(bad,[],variant+' '+topic+' HTTP errors');
     rows.push({variant,topic,iteration,ready_ms:metrics.ready,api_requests:metrics.requests,navigation:metrics.navigation});
     fs.writeFileSync(path.join(directory,'browser-raw.json'),JSON.stringify(rows,null,2)+'\n');
     console.log(iteration,variant,topic,metrics.ready.toFixed(1),metrics.requests.length);
     await context.close();
    }
   }
  }
 }finally{await browser.close();}
 console.log('BROWSER_PAIRED_COMPLETE');
})().catch(e=>{console.error(e);process.exitCode=1;});
