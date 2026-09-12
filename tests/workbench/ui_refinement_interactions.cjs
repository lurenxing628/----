'use strict';

const path=require('node:path'),fs=require('node:fs'),crypto=require('node:crypto');
const {measure,measureTable,measureGantt}=require('./ui_refinement_geometry.cjs');
const CASES=[['batch-table-scroll','batches'],['batch-validation','batches'],['plan-selected','gantt'],['run-picker','run'],
  ['field-expanded','field'],['dashboard-detail','dashboard'],['trial-new','trial'],['calibration-detail','calib']];

async function action(page,id,settle,selectPlan) {
  if(id==='batch-table-scroll')return page.evaluate(measureTable);
  if(id==='batch-validation') {
    await page.getByRole('button',{name:'新增批次',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'创建批次',exact:true}).click();await settle(page);
    return page.evaluate(()=>{const invalid=[...document.querySelectorAll('[role="dialog"] [aria-invalid="true"]')];
      return {id:'I2',ok:invalid.length>=3 && invalid.includes(document.activeElement),detail:{invalid:invalid.map(e=>e.getAttribute('aria-label')||e.name||e.id),focused:document.activeElement.id}};});
  }
  if(id==='plan-selected'){await selectPlan(page);return page.evaluate(measureGantt);}
  if(id==='run-picker') {
    await page.getByRole('button',{name:'选择批次',exact:true}).click();
    const row=page.locator('.pf-picker-row').filter({hasText:'B1'});await row.locator('input[type="checkbox"]').check();
    return {id:'I4',ok:await row.locator('input[type="checkbox"]').isChecked(),detail:{selected_batch:'B1'}};
  }
  if(id==='field-expanded') {
    await page.getByRole('button',{name:/^查看报工 HOST-000 /}).click();await settle(page);
    const rows=page.locator('table').filter({hasText:'报工编号'}).last().locator('tbody tr');
    await rows.first().waitFor();
    return {id:'I5',ok:await rows.count()>0,detail:{ledger_rows:await rows.count()}};
  }
  if(id==='dashboard-detail') {
    await page.getByRole('button',{name:/^查看 B1 .*齐套缺口$/}).click();await settle(page);
    return page.evaluate(()=>{
      const panel=document.querySelector('.wb-detail,.dy-detail'),r=panel?.getBoundingClientRect();
      return {id:'I6',ok:!!r&&r.top>=0&&r.top<innerHeight&&panel.contains(document.activeElement),
        detail:{top:r?.top,bottom:r?.bottom,focusedInside:!!panel&&panel.contains(document.activeElement)}};
    });
  }
  if(id==='trial-new') {
    await page.getByRole('button',{name:'新建试调',exact:true}).click();await settle(page);
    return page.evaluate(()=>{const dialog=document.querySelector('[role="dialog"]'),r=dialog?.getBoundingClientRect();
      return {id:'I7',ok:!!r&&r.top>=0&&r.bottom<=innerHeight&&dialog.contains(document.activeElement),
        detail:{top:r?.top,bottom:r?.bottom,radioCount:dialog?.querySelectorAll('input[type="radio"]').length}};});
  }
  if(id==='calibration-detail') {
    await page.getByRole('button',{name:'查看 P1 1 Turning',exact:true}).click();await settle(page);
    const close=page.getByRole('button',{name:'关闭P1 · 1 Turning',exact:true});
    await close.waitFor();
    return {id:'I8',ok:await close.isVisible(),detail:{close_visible:await close.isVisible()}};
  }
  throw new Error('Unknown interaction '+id);
}

async function captureInteractions(browser,ready,outputDir,settle,selectPlan) {
  const results=[];
  for(const [id,view] of CASES) {
    const context=await browser.newContext({viewport:{width:1366,height:768},locale:'zh-CN',deviceScaleFactor:1});
    const page=await context.newPage();page.setDefaultTimeout(15000);
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    const result={id,view,theme:'light',viewport:{width:1366,height:768},errors,checks:[],interaction_mode:'Playwright click/check plus explicit scroll measurement'};
    try {
      await page.goto(ready.url+(view==='trial'?'/workbench/trial':'/workbench?view='+view),{waitUntil:'networkidle'});await settle(page);
      result.checks.push(await action(page,id,settle,selectPlan));
      const facts=await page.evaluate(measure,view);
      result.checks.push(facts.checks.find(check=>check.id==='G6'));result.observations=facts.observations;
      result.screenshot='interaction-'+id+'.png';await page.screenshot({path:path.join(outputDir,result.screenshot)});
      result.screenshot_sha256=crypto.createHash('sha256').update(fs.readFileSync(path.join(outputDir,result.screenshot))).digest('hex');
    }catch(error){errors.push(error.message);}
    finally{await context.close();results.push(result);console.log(JSON.stringify({interaction:id,failures:result.checks.filter(c=>!c.ok).map(c=>c.id),errors}));}
  }
  return results;
}

module.exports={CASES,captureInteractions};
