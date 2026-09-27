'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const {chromium}=require('playwright');
const {connect}=require('./win7_workflow_transport.cjs');
const ready=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const cases=JSON.parse(fs.readFileSync(path.join(ready.win7_evidence_root,'error-inputs/manifest.json'),'utf8')).filter(row=>ready.matrix_kinds.includes(row.kind)&&(!ready.matrix_case_names||ready.matrix_case_names.includes(row.name)));
const report={scope:'Real Win7 file-input/preview/cancel with read-only guest database snapshots',cases:[],requests:[],http_errors:[],page_errors:[],snapshots:[],passed:false};
const save=()=>fs.writeFileSync(path.join(ready.root,'error-matrix-report.json'),JSON.stringify(report,null,2));
const configs={
 material:{node:'物料',button:'导入',endpoint:'/imports/material/preview'},
 machine:{node:'设备',button:'导入',endpoint:'/imports/machine/preview'},
 calendar:{node:'工作日历',button:'导入日历',endpoint:'/calendar-files/work_calendar/preview'},
 operator_calendar:{node:'人员',button:'导入个人日历',endpoint:'/calendar-files/operator_calendar/preview'},
 relation:{node:'人员',button:'导入可操作设备',endpoint:'/relation-files/operator_machine/preview'},
 route:{node:'工艺',button:'导入工艺路线',endpoint:'/process-files/route/preview'},
 hours:{node:'工艺',button:'导入工时定额',endpoint:'/process-files/hours/preview'},
 batch:{button:'批量导入',endpoint:'/entities/batch/import-preview',batch:true},
 field:{button:'报工文件',endpoint:'/execution/files/preview',field:true},
};
function snapshot(name){
 const file=path.join(ready.root,name+'.db');
 const value=JSON.parse(execFileSync(process.execPath,[path.join(__dirname,'win7_snapshot_cli.cjs'),ready.win7_evidence_root,ready.win7_slot,file],{encoding:'utf8',timeout:90000}));
 report.snapshots.push(value);return file;
}
async function cancel(page){
 const dialog=page.getByRole('dialog').first();await dialog.getByRole('button',{name:'取消',exact:true}).click();
 const generic=page.getByRole('dialog',{name:'离开前确认',exact:true});
 const process=page.getByRole('dialog',{name:'放弃本次文件导入？',exact:true});
 if(await generic.isVisible())await generic.getByRole('button',{name:'放弃未保存内容并继续',exact:true}).click();
 if(await process.isVisible())await process.getByRole('button',{name:'放弃导入并关闭',exact:true}).click();
 await page.getByRole('dialog').waitFor({state:'detached'});
}
(async()=>{
 const before=snapshot('matrix-before');
 const browser=await connect(chromium,ready.win7_evidence_root),context=await browser.newContext({viewport:{width:1920,height:1080}}),page=await context.newPage();
 // Chrome109 may evict the inspector body during large-upload rejection.
 // Observe a clone of the real error response; never alter the response or retry.
 await context.addInitScript(()=>{
  const original=window.fetch;window.win7ErrorResponseEvidence=[];
  window.fetch=async function(...args){const response=await original.apply(this,args);
   if(response.status>=400&&response.url.includes('/api/workbench/')){
    const entry={url:response.url,status:response.status};window.win7ErrorResponseEvidence.push(entry);
    response.clone().json().then(body=>entry.body=body,error=>entry.capture_error=String(error));
   }
   return response;
  };
 });
 page.setDefaultTimeout(20000);
 page.on('pageerror',e=>report.page_errors.push(e.message));
 page.on('request',r=>{if(r.url().includes('/api/workbench/'))report.requests.push({case:report.current,method:r.method(),url:r.url()});});
 page.on('response',r=>{if(r.status()>=400)report.http_errors.push({case:report.current,status:r.status(),url:r.url()});});
 try{
  let currentKind;
  for(const item of cases){
   report.current=item.kind+'/'+item.name;
   const result={...item,passed:false};report.cases.push(result);const config=configs[item.kind];
   try{
    if(currentKind!==item.kind){
     await page.goto('about:blank');await page.goto('http://127.0.0.1:5000/workbench?view='+(config.batch?'batches':config.field?'field':'process'));
     if(config.batch)await page.locator('[data-batch-workspace]').waitFor();
     else if(config.field)await page.locator('[data-field-workspace]').waitFor();
     else {
      await page.locator('[data-rail-node]').first().waitFor();
      const node= config.node==='工艺'?page.locator('[data-rail-node="process"]'):config.node==='工作日历'?page.locator('section.rail').getByRole('button',{name:/^工作日历(?: · 全局)?$/}):page.locator('[data-rail-node]').filter({has:page.getByText(config.node,{exact:true})});
      await node.click();
     }
     currentKind=item.kind;
    }
    await page.getByRole('button',{name:config.button,exact:true}).click();
    const dialog=page.getByRole('dialog').first();await dialog.waitFor();
    if(!config.batch&&!config.field)await dialog.getByRole('button',{name:'Excel (.xlsx)',exact:true}).click();
    assert.equal(crypto.createHash('sha256').update(fs.readFileSync(item.file)).digest('hex'),item.sha256);
    await dialog.locator('input[type="file"]').setInputFiles(item.file);
    const previewButton=dialog.getByRole('button',{name:'开始预检',exact:true});
    if(await previewButton.isEnabled()){
     const observationOffset=await page.evaluate(()=>window.win7ErrorResponseEvidence.length);
     const responsePromise=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith(config.endpoint)&&r.request().method()==='POST',{timeout:20000}).then(r=>r,()=>null);
     await previewButton.click();
     const response=await responsePromise;
     if(response){
      result.status=response.status();
      try{result.response=await response.json();}
      catch(error){
       assert(['oversized-file','oversized-valid-workbook'].includes(item.name)&&[413,422].includes(result.status),'Only a real upload-size error may use guest response observation');result.inspector_capture_error=error.message;
       const lookup={url:response.url(),status:result.status,offset:observationOffset};
       await page.waitForFunction(({url,status,offset})=>window.win7ErrorResponseEvidence.slice(offset).some(row=>row.url===url&&row.status===status&&row.body),lookup);
       result.response=await page.evaluate(({url,status,offset})=>window.win7ErrorResponseEvidence.slice(offset).filter(row=>row.url===url&&row.status===status&&row.body).slice(-1)[0].body,lookup);
       result.response_evidence='Unmodified real guest fetch response clone';
      }
      assert(result.status<500,'Server error');
     }
     else result.client_validation=true;
    }else result.client_validation=true;
    result.ui_text=await dialog.innerText();
    const payload=result.response;
    if(result.client_validation){
     assert(['empty-file','oversized-file','oversized-valid-workbook'].includes(item.name),'Unexpected absence of a server response');
     assert(/文件为空|请选择不超过|文件超过\s*\d+\s*MB|超过.*上限|文件大小不能超过|文件内容不是 XLSX 工作簿/.test(result.ui_text),'Client rejection must show its actual reason');
     if(item.name==='oversized-valid-workbook')assert(!result.ui_text.includes('文件内容不是 XLSX 工作簿'),'A valid workbook must reach the size guard');
    }
    if(item.name==='oversized-valid-workbook')assert(/超过|过大|上限|不能超过/.test(result.ui_text),'The file-size guard must explain its rejection');
    if(item.expected_valid){
     assert.equal(result.status,200,JSON.stringify(payload));assert.equal(payload.data.can_confirm,true,JSON.stringify(payload));
     if(item.extra_sheet)assert.equal(payload.data.rows.length,1);
     if(item.expected_date)assert(JSON.stringify(payload.data).includes(item.expected_date));
    }else {
     assert(!payload||result.status>=400||payload.data.can_confirm===false,JSON.stringify(payload));
     const confirm=dialog.getByRole('button',{name:/^(确认导入|按 0 导入)$/});
     if(await confirm.count())assert(await confirm.isDisabled(),'Invalid input must not enable confirm');
     assert(/文件|表头|列|公式|重复|库存|日期|预检|问题|超过|上限|没有|无效|不接受|不能为空/.test(result.ui_text));
    }
    result.screenshot=path.join(ready.root,'screenshots',item.kind+'-'+item.name+'.png');await page.screenshot({path:result.screenshot});
    await cancel(page);result.passed=true;
    console.log(report.current+': passed');
   }catch(error){result.error=error.stack;throw error;}finally{save();}
  }
  const after=snapshot('matrix-after');
  const python=process.env.WIN7_HOST_PYTHON;assert(python);
  const check='import sqlite3,json,sys\na=sqlite3.connect(sys.argv[1]);b=sqlite3.connect(sys.argv[2])\ntables=["Materials","OpTypes","Machines","Operators","Suppliers","WorkCalendar","OperatorCalendar","OperatorMachine","Parts","PartOperations","Batches","BatchOperations","Schedule","OperationExecutionEvents","WorkbenchCommandReceipts"]\nchecked=[]\nfor name in tables:\n if not a.execute("SELECT 1 FROM sqlite_master WHERE name=?",(name,)).fetchone(): continue\n assert a.execute("SELECT * FROM "+name+" ORDER BY rowid").fetchall()==b.execute("SELECT * FROM "+name+" ORDER BY rowid").fetchall(),name\n checked.append(name)\nassert b.execute("PRAGMA integrity_check").fetchone()[0]=="ok"\nassert not b.execute("PRAGMA foreign_key_check").fetchall()\nprint(json.dumps({"unchanged_tables":checked,"integrity":"ok","foreign_keys":[]}))';
  report.no_write_proof=JSON.parse(execFileSync(python,['-B','-c',check,before,after],{encoding:'utf8',timeout:30000}));
  assert.deepEqual(report.page_errors,[]);report.passed=true;
 }catch(error){report.error=error.stack;console.error(error);process.exitCode=1;}
 finally{save();await context.close();await browser.close();}
})().catch(e=>{report.error=e.stack;save();console.error(e);process.exitCode=1});
