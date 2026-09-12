'use strict';

const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {chromium}=require('playwright');
const {measure,measureTable,measureGantt}=require('./ui_refinement_geometry.cjs');
const {captureInteractions}=require('./ui_refinement_interactions.cjs');
const VIEWS=['dashboard','process','basedata','batches','run','analysis','trial','gantt','delay','field','fieldgantt','review','reports','calib','system'];
const SIZES=[{width:1366,height:768},{width:1280,height:720}];
const sha=buffer=>crypto.createHash('sha256').update(buffer).digest('hex');

async function settle(page) {
  await page.waitForFunction(()=>document.querySelector('#root')?.dataset.workbenchBoot==='ready');
  await page.waitForFunction(()=>![...document.querySelectorAll('[aria-busy="true"]')].some(e=>e.getBoundingClientRect().width>0));
  await page.evaluate(()=>document.fonts.ready);
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
}

async function selectedPlan(page) {
  const radio=page.locator('table[aria-label="可选排产方案"] tbody tr').filter({hasText:'当前正式'}).locator('input[type="radio"]');
  if(await radio.count())await radio.first().check();
  await settle(page);
}

async function capture(readyFile,outputDir) {
  const ready=JSON.parse(fs.readFileSync(readyFile,'utf8'));
  if(!ready.assets?.static||!ready.root||new URL(ready.url).hostname!=='127.0.0.1')throw new Error('An isolated run_live_server ready file is required');
  fs.mkdirSync(outputDir,{recursive:true});
  const manifestPath=path.join(ready.assets.static,'workbench/asset-manifest.json'),manifestBytes=fs.readFileSync(manifestPath),manifest=JSON.parse(manifestBytes);
  const executablePath=process.env.WORKBENCH_BROWSER||'/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium';
  const browser=await chromium.launch({executablePath,headless:true});
  const report={schema_version:1,kind:'workbench-ui-refinement',created_at:new Date().toISOString(),browser:browser.version(),
    source:{ready_file:path.resolve(readyFile),session:ready.session,build_id:manifest.build_id,manifest_sha256:sha(manifestBytes),
      assets_root:ready.assets.root,assets_hashes:ready.assets.hashes,loaded_python_sources:ready.loaded_python_sources,
      source_differences_at_freeze:ready.assets.source_differences,
      probe_sources:Object.fromEntries(['ui_refinement_capture.cjs','ui_refinement_geometry.cjs','ui_refinement_interactions.cjs']
        .map(name=>[name,sha(fs.readFileSync(path.join(__dirname,name)))]))},
    matrix:{views:VIEWS,sizes:SIZES,themes:['light','dark']},pages:[],interactions:[],densities:[],errors:[]};
  fs.writeFileSync(path.join(outputDir,'asset-manifest.json'),manifestBytes);
  try {
    for(const size of SIZES)for(const theme of ['light','dark'])for(const view of VIEWS) {
      const id=[view,size.width,size.height,theme].join('-');
      const context=await browser.newContext({viewport:size,locale:'zh-CN',deviceScaleFactor:1});
      await context.addInitScript(theme=>{localStorage.setItem('aps_kit_theme',theme);localStorage.setItem('aps_theme',theme);},theme);
      const page=await context.newPage();page.setDefaultTimeout(15000);
      const errors=[];page.on('pageerror',e=>errors.push(e.message));
      page.on('response',response=>{if(response.status()>=400)errors.push('HTTP '+response.status()+' '+response.url());});
      try {
        const target=view==='trial'?'/workbench/trial':'/workbench?view='+view;
        const response=await page.goto(ready.url+target,{waitUntil:'networkidle'});
        if(response.status()!==200)throw new Error('View HTTP '+response.status());
        await settle(page);
        const boot=await page.locator('#workbench-boot').textContent();
        fs.writeFileSync(path.join(outputDir,id+'.boot.json'),boot);
        const measurement=await page.evaluate(measure,view);
        measurement.id=id;measurement.boot_sha256=sha(boot);measurement.screenshot=id+'.png';measurement.errors=errors;
        await page.screenshot({path:path.join(outputDir,measurement.screenshot)});
        measurement.screenshot_sha256=sha(fs.readFileSync(path.join(outputDir,measurement.screenshot)));
        if(view==='batches')measurement.checks.push(await page.evaluate(measureTable));
        if(['analysis','gantt','delay'].includes(view)) {
          await selectedPlan(page);measurement.checks.push(await page.evaluate(measureGantt));
          measurement.selected_screenshot=id+'-selected.png';await page.screenshot({path:path.join(outputDir,measurement.selected_screenshot)});
          measurement.selected_screenshot_sha256=sha(fs.readFileSync(path.join(outputDir,measurement.selected_screenshot)));
        }
        if(view==='batches' && await page.getByRole('button',{name:'紧凑表格',exact:true}).count()) {
          const sample=()=>page.locator('tbody tr').first().locator('td').evaluateAll(cells=>cells.map(cell=>({text:cell.innerText,fontSize:getComputedStyle(cell).fontSize,height:cell.getBoundingClientRect().height})));
          const comfortable=await sample();await page.getByRole('button',{name:'紧凑表格',exact:true}).click();
          await page.waitForFunction(()=>document.documentElement.dataset.density==='compact');await settle(page);
          const compact=await sample(),table=await page.evaluate(measureTable);
          report.densities.push({id,comfortable,compact,table,ok:comfortable.length>0&&comfortable.length===compact.length
            && comfortable.every((cell,i)=>cell.fontSize===compact[i].fontSize&&compact[i].height<=cell.height)&&table.ok});
          await page.screenshot({path:path.join(outputDir,id+'-compact.png')});
        }
        report.pages.push(measurement);
        console.log(JSON.stringify({id,checks:measurement.checks.length,failures:measurement.checks.filter(c=>!c.ok).map(c=>c.id),errors:errors.length}));
      }catch(error){report.errors.push({id,error:error.message});console.log(JSON.stringify({id,error:error.message}));}
      finally{await context.close();fs.writeFileSync(path.join(outputDir,'report.json'),JSON.stringify(report,null,2));}
    }
    report.interactions=await captureInteractions(browser,ready,outputDir,settle,selectedPlan);
  }finally{await browser.close();}
  report.completed_at=new Date().toISOString();
  fs.writeFileSync(path.join(outputDir,'report.json'),JSON.stringify(report,null,2));
  if(report.errors.length)process.exitCode=1;
  return report;
}

if(require.main===module) {
  if(process.argv.length!==4)throw new Error('Usage: node ui_refinement_capture.cjs <server-ready.json> <evidence-dir>');
  capture(path.resolve(process.argv[2]),path.resolve(process.argv[3])).catch(error=>{console.error(error);process.exitCode=1;});
}
module.exports={VIEWS,SIZES,capture};
