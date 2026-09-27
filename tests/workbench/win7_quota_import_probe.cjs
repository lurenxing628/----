'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const {chromium}=require('playwright'),{connect}=require('./win7_workflow_transport.cjs');
const ready=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const report={passed:false,actions:[],responses:[],page_errors:[]};
const save=()=>fs.writeFileSync(path.join(ready.root,'quota-import.json'),JSON.stringify(report,null,2));
(async()=>{
 const browser=await connect(chromium,ready.win7_evidence_root),context=await browser.newContext({viewport:{width:1392,height:924}}),page=await context.newPage();page.setDefaultTimeout(30000);
 page.on('pageerror',e=>report.page_errors.push(e.message));
 const button=(name,owner=page)=>owner.getByRole('button',{name,exact:true});
 const read=async(suffix,action)=>{const pending=page.waitForResponse(r=>r.url().endsWith(suffix)&&r.request().method()==='POST');await action();const response=await pending,body=await response.json();report.responses.push({suffix,status:response.status(),body});assert.equal(response.status(),200,JSON.stringify(body));return body;};
 const step=async(name,action)=>{const row={name,passed:false};report.actions.push(row);try{await action();row.screenshot=path.join(ready.root,'screenshots',name+'.png');await page.screenshot({path:row.screenshot});row.passed=true;console.log(name+': passed');}catch(e){row.error=e.stack;throw e;}finally{save();}};
 const snapshot=name=>{const destination=path.join(ready.root,name+'.db');return JSON.parse(execFileSync(process.execPath,[path.join(__dirname,'win7_snapshot_cli.cjs'),ready.win7_evidence_root,ready.win7_slot,destination],{encoding:'utf8',timeout:90000}));};
 try{
  await page.goto('http://127.0.0.1:5000/workbench?view=calib');await page.bringToFront();await page.waitForFunction(()=>document.fonts.status==='loaded');
  await step('actual-calibration-adoption-lock',async()=>{
   await page.locator('.ca-table tr[data-ref="'+ready.expected.final_e.template_ref+'"]').getByRole('button',{name:'查看 P1 1 Turning',exact:true}).click();
   await page.locator('[data-sample-group=selected]').waitFor();await button('预检采用').click();const dialog=page.getByRole('dialog');
   await dialog.getByLabel('采用原因',{exact:true}).fill('Win7 Excel 导入保护：核对五条原始完工记录');await dialog.getByLabel('经办人',{exact:true}).fill('Win7 验收');
   await button('检查是否可采用',dialog).click();await dialog.getByText('检查通过，可以采用。',{exact:true}).waitFor();await dialog.getByRole('checkbox').check();
   const receipt=await read('/adopt',()=>button('确认采用并锁定',dialog).click());assert.equal(receipt.result,'committed');assert.equal(receipt.data.new_unit_hours,3);assert.equal(receipt.data.locked,true);report.adoption=receipt;
   await button('完成',dialog).click();
  });
  report.locked_snapshot=snapshot('after-adoption');
  for(const spec of [{file:'mixed.xlsx',changed:1,skipped:1,unchanged:0,result:'committed'},{file:'allskip.xlsx',changed:0,skipped:1,unchanged:0,result:'unchanged'},{file:'setup.csv',changed:1,skipped:0,unchanged:0,result:'committed'},{file:'setup_blank.csv',changed:1,skipped:0,unchanged:0,result:'committed'}]){
   await step(spec.file.replace('.','-'),async()=>{
    await page.goto('http://127.0.0.1:5000/workbench?view=process');await page.locator('[data-rail-node="process"]').click();await button('导入工时定额').click();const dialog=page.getByRole('dialog');
    await button(spec.file.endsWith('.xlsx')?'Excel (.xlsx)':'CSV (.csv)',dialog).click();await dialog.locator('input[type=file]').setInputFiles(path.join(ready.root,'uploads',spec.file));
    const preview=await read('/hours/preview',()=>button('开始预检',dialog).click());assert.equal(preview.data.can_confirm,true);assert.equal(preview.data.skipped_count,spec.skipped);
    const region=page.getByRole('region',{name:'工时导入预检',exact:true});let text=await region.innerText();assert(text.includes('可导入 '+spec.changed)&&text.includes('锁定跳过 '+spec.skipped)&&text.includes('原值相同 '+spec.unchanged));
    const receipt=await read('/hours/confirm',()=>button(spec.changed?'确认导入':'确认跳过并记录结果',dialog).click());assert.equal(receipt.result,spec.result);assert.equal(receipt.data.skipped_count,spec.skipped);
    text=await page.getByRole('region',{name:'工时导入结果',exact:true}).innerText();assert(text.includes('已导入 '+spec.changed)&&text.includes('锁定跳过 '+spec.skipped));
    if(spec.skipped)assert(text.includes('单件工时已锁定')&&text.includes('本行全部跳过'));
    report.actions.at(-1).receipt=receipt;report.actions.at(-1).snapshot=snapshot(spec.file.replace('.','-'));
    await button('完成',dialog).click();
   });
  }
  assert.deepEqual(report.page_errors,[]);report.passed=true;
 }catch(e){report.error=e.stack;console.error(e);process.exitCode=1;}finally{save();await context.close();await browser.close();}
})().catch(e=>{report.error=e.stack;save();console.error(e);process.exitCode=1});
