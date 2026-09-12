'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const configurations=[
  {node:'自制工种',kind:'op_type',category:'internal',values:{remark:'Imported capacity note'}},
  {node:'外协工种',kind:'op_type',category:'external',values:{remark:'Imported external note',default_merge_mode:'separate'}},
  {node:'设备',kind:'machine',values:{status:'active',op_type_code:'RT-IN',group_code:'RT-G'}},
  {node:'人员',kind:'operator',values:{status:'active',skill_codes:'["RT-IN"]',shift_profile_code:'RT-SH'}},
  {node:'供应商',kind:'supplier',values:{status:'active',default_days:'2.75',op_type_codes:'["RT-EX"]'}}
];
function csv(rows){const keys=Object.keys(rows[0]),cell=value=>'"'+String(value).replace(/"/g,'""')+'"';return [keys,...rows.map(row=>keys.map(key=>row[key]??''))].map(row=>row.map(cell).join(',')).join('\r\n');}
async function post(page,suffix,click){
  const response=page.waitForResponse(res=>new URL(res.url()).pathname.endsWith(suffix)&&res.request().method()==='POST');
  await click();const value=await response;assert.equal(value.status(),200,await value.text());return value.json();
}
async function finish(page){await page.getByRole('dialog').getByRole('button',{name:'完成',exact:true}).click();await page.getByRole('dialog').waitFor({state:'detached'});}
async function upload(page,config,rows,artifacts){
  await page.getByRole('button',{name:'导入',exact:true}).click();const dialog=page.getByRole('dialog');
  if(artifacts){
    const waiting=page.waitForEvent('download');await dialog.getByRole('button',{name:'下载模板',exact:true}).click();
    const download=await waiting,file=path.join(artifacts.root,'downloads',artifacts.state+'-'+config.kind+'-'+(config.category||'')+'-template-'+download.suggestedFilename());
    await download.saveAs(file);assert.equal(await download.failure(),null);artifacts.report.downloads.push(file);
    const template=fileRows(file,'xlsx');assert.equal(template.length,1);assert(template[0].length>=3);
  }
  await dialog.getByRole('button',{name:'CSV (.csv)',exact:true}).click();
  await dialog.locator('input[type="file"]').setInputFiles({name:'resources.csv',mimeType:'text/csv',buffer:Buffer.from(csv(rows))});
  const value=await post(page,'/imports/'+config.kind+'/preview',()=>dialog.getByRole('button',{name:'开始预检',exact:true}).click());
  assert.equal(value.data.summary.rejected,0);assert.equal(value.data.rows.length,rows.length);
  if(config.category)assert.equal(value.data.scope.category,config.category);
  return value.data;
}
async function confirmImport(page,config){
  const dialog=page.getByRole('dialog'),ack=dialog.locator('input[type="checkbox"]');
  if(await ack.count())await ack.check();
  const receipt=await post(page,'/imports/'+config.kind+'/confirm',()=>dialog.getByRole('button',{name:'确认导入',exact:true}).click());
  assert(['committed','unchanged'].includes(receipt.result));await finish(page);return receipt;
}
async function deleteSelection(page,config){
  await page.getByRole('button',{name:'批量删除',exact:true}).click();const dialog=page.getByRole('dialog');
  const preview=await post(page,'/entities/'+config.kind+'/bulk-preview',()=>dialog.getByRole('button',{name:'开始预检',exact:true}).click());
  assert.equal(preview.data.summary.rejected,0);
  const confirm=dialog.getByRole('button',{name:/^确认删除(?:：|$)/});assert(await confirm.isDisabled());
  await dialog.locator('input[type="checkbox"]').check();
  const receipt=await post(page,'/entities/'+config.kind+'/bulk-confirm',()=>confirm.click());
  assert.equal(receipt.data.deleted_count,preview.data.rows.length);await finish(page);return preview.data.rows;
}
function fileRows(file,format){
  const python=path.resolve(__dirname,'../../.venv/bin/python');
  const program='import csv,json,sys,openpyxl\npath,fmt=sys.argv[1:]\n' +
    'if fmt=="csv":\n with open(path,encoding="utf-8-sig",newline="") as stream: rows=list(csv.reader(stream))\n' +
    'else:\n wb=openpyxl.load_workbook(path,read_only=True,data_only=False)\n assert len(wb.worksheets)==1\n rows=list(wb.worksheets[0].iter_rows(values_only=True))\n wb.close()\n' +
    'print(json.dumps(rows,ensure_ascii=False))';
  const rows=JSON.parse(cp.execFileSync(python,['-B','-c',program,file,format],{encoding:'utf8',maxBuffer:8*1024*1024}));
  return rows.map(row=>row.map(value=>format==='csv'&&typeof value==='string'&&value.startsWith("'")?value.slice(1):value));
}
async function exportSelection(page,config,selection,format,expected,root,state,report){
  await page.getByRole('button',{name:'导出',exact:true}).click();const dialog=page.getByRole('dialog');
  await dialog.locator('input[type="radio"][value="'+selection+'"]').check();
  await dialog.getByRole('button',{name:format==='csv'?'CSV (.csv)':'Excel (.xlsx)',exact:true}).click();
  const preview=await post(page,'/exports/'+config.kind+'/preview',()=>dialog.getByRole('button',{name:'开始预检',exact:true}).click());
  assert.equal(preview.data.row_count,expected);if(config.category)assert.equal(preview.data.scope.category,config.category);
  const downloading=page.waitForEvent('download');await dialog.getByRole('button',{name:'下载文件',exact:true}).click();
  const download=await downloading,file=path.join(root,'downloads',state+'-'+config.kind+'-'+(config.category||'')+'-'+selection+'-'+download.suggestedFilename());
  await download.saveAs(file);assert.equal(await download.failure(),null);report.downloads.push(file);
  const rows=fileRows(file,format);assert.equal(rows.length,expected+1);await finish(page);return {file,rows};
}
async function resourceFiles(page,state,helpers,root,report){
  const {run,rail,search,shot,empty}=helpers;
  for(let index=0;index<configurations.length;index++){
    const config=configurations[index],prefix='IO-'+state+'-'+index+'-',label='IO '+state+' '+index+' ',rows=Array.from({length:22},(_,i)=>({business_code:prefix+String(i+1).padStart(3,'0'),label:label+(i+1),...config.values}));
    await rail(page,config.node);await search(page,'');
    await run(page,state,'resource-files-import-'+index,async()=>{
      const draft=await upload(page,config,rows,{root,state,report});assert.equal(draft.summary.new,22);
      await shot(page,state+'-resource-import-'+index);await confirmImport(page,config);await search(page,prefix);
      await page.getByRole('button',{name:rows[0].business_code,exact:true}).waitFor();
    });
    await run(page,state,'resource-files-cross-page-export-'+index,async()=>{
      await page.getByRole('checkbox',{name:'选择 '+rows[0].business_code+' '+rows[0].label,exact:true}).check();
      await page.getByRole('button',{name:'下一页',exact:true}).click();
      await page.getByRole('checkbox',{name:'选择 '+rows[21].business_code+' '+rows[21].label,exact:true}).check();
      const exported=await exportSelection(page,config,'selected','xlsx',2,root,state,report);
      const all=exported.rows.flat();assert(all.includes(rows[0].business_code));assert(all.includes(rows[21].business_code));
      assert(!all.includes(rows[1].business_code));await shot(page,state+'-resource-selection-'+index);
      await page.getByRole('button',{name:'导入',exact:true}).click();const dialog=page.getByRole('dialog');
      await dialog.getByRole('button',{name:'Excel (.xlsx)',exact:true}).click();await dialog.locator('input[type="file"]').setInputFiles(exported.file);
      const preview=await post(page,'/imports/'+config.kind+'/preview',()=>dialog.getByRole('button',{name:'开始预检',exact:true}).click());
      assert.equal(preview.data.summary.rejected,0);assert.equal(preview.data.summary.unchanged,2);await confirmImport(page,config);
    });
    await run(page,state,'resource-files-filtered-export-'+index,async()=>{
      const exported=await exportSelection(page,config,'filtered','csv',22,root,state,report);
      const all=exported.rows.flat();rows.forEach(row=>assert(all.includes(row.business_code)));
      // A file produced by the app must import again without changing any facts.
      await page.getByRole('button',{name:'导入',exact:true}).click();const dialog=page.getByRole('dialog');
      await dialog.getByRole('button',{name:'CSV (.csv)',exact:true}).click();await dialog.locator('input[type="file"]').setInputFiles(exported.file);
      const preview=await post(page,'/imports/'+config.kind+'/preview',()=>dialog.getByRole('button',{name:'开始预检',exact:true}).click());
      assert.equal(preview.data.summary.rejected,0);assert.equal(preview.data.summary.unchanged,22);await confirmImport(page,config);
      const url=new URL('/api/workbench/v1/entities/'+config.kind,page.url());if(config.category)url.searchParams.set('category',config.category);
      const fullResponse=await page.request.get(url.href);assert.equal(fullResponse.status(),200);const full=await fullResponse.json();
      const complete=await exportSelection(page,config,'all','csv',full.data.page.total,root,state,report);
      assert(complete.rows.length>23,'All export must include unchanged seed records beyond the current filter');
      if(config.category){const codes=complete.rows.flat();assert(!codes.includes(config.category==='internal'?'RT-EX':'RT-IN'));}
    });
    await run(page,state,'resource-files-bulk-delete-'+index,async()=>{
      const selected=await deleteSelection(page,config);assert.deepEqual(selected.map(row=>row.business_code),[rows[0].business_code,rows[21].business_code]);
      await search(page,prefix);await page.getByRole('button',{name:rows[1].business_code,exact:true}).waitFor();
      await page.getByRole('checkbox',{name:'全选当前页',exact:true}).check();
      const rest=await deleteSelection(page,config);assert.equal(rest.length,20);
      await empty(page);
    });
  }
}
module.exports={resourceFiles,exportSelection};
