'use strict';
// 人员页上的「导入/导出可操作设备」：模板、主操连带提示、拒绝行挡住确认、导出回导不改事实。
// 全程只动本轮自己建的人员和设备，跑完删干净，不碰种子里的 RT-O / RT-M。
const assert=require('node:assert/strict'),path=require('node:path');
const PREVIEW='/relation-files/operator_machine/preview',CONFIRM='/relation-files/operator_machine/confirm';
const EXPORT='/relation-files/operator_machine/export-preview';
function csv(rows){const keys=Object.keys(rows[0]),cell=value=>'"'+String(value).replace(/"/g,'""')+'"';return [keys,...rows.map(row=>keys.map(key=>row[key]??''))].map(row=>row.map(cell).join(',')).join('\r\n');}
async function post(page,suffix,click){
  const response=page.waitForResponse(res=>new URL(res.url()).pathname.endsWith(suffix)&&res.request().method()==='POST');
  await click();const value=await response;assert.equal(value.status(),200,await value.text());return value.json();
}
async function dismiss(page,discard=false){
  await page.getByRole('dialog').getByRole('button',{name:/^(完成|取消)$/}).first().click();
  if(discard){const guard=page.getByRole('dialog',{name:'离开前确认',exact:true});await guard.waitFor();
    await guard.getByRole('button',{name:'放弃未保存内容并继续',exact:true}).click();}
  await page.getByRole('dialog').waitFor({state:'detached'});
}
async function save(page,suffix,dialog){
  const acknowledgement=dialog.locator('input[type="checkbox"]');
  if(await acknowledgement.count())await acknowledgement.check();
  const receipt=await post(page,suffix,()=>dialog.getByRole('button',{name:'确认导入',exact:true}).click());
  assert(['committed','unchanged'].includes(receipt.result),JSON.stringify(receipt));await dismiss(page);return receipt;
}
async function seedEntities(page,kind,rows){
  await page.getByRole('button',{name:'导入',exact:true}).click();const dialog=page.getByRole('dialog');
  await dialog.getByRole('button',{name:'CSV (.csv)',exact:true}).click();
  await dialog.locator('input[type="file"]').setInputFiles({name:kind+'.csv',mimeType:'text/csv',buffer:Buffer.from(csv(rows))});
  const preview=await post(page,'/imports/'+kind+'/preview',()=>dialog.getByRole('button',{name:'开始预检',exact:true}).click());
  assert.equal(preview.data.summary.rejected,0);assert.equal(preview.data.summary.new,rows.length);
  await save(page,'/imports/'+kind+'/confirm',dialog);
}
async function removeEntities(page,kind,count){
  await page.getByRole('checkbox',{name:'全选当前页',exact:true}).check();
  await page.getByRole('button',{name:'批量删除',exact:true}).click();const dialog=page.getByRole('dialog');
  const preview=await post(page,'/entities/'+kind+'/bulk-preview',()=>dialog.getByRole('button',{name:'开始预检',exact:true}).click());
  assert.equal(preview.data.summary.rejected,0);assert.equal(preview.data.rows.length,count);
  await dialog.locator('input[type="checkbox"]').check();
  const receipt=await post(page,'/entities/'+kind+'/bulk-confirm',()=>dialog.getByRole('button',{name:/^确认删除(?:：|$)/}).click());
  assert.equal(receipt.data.deleted_count,count);await dismiss(page);
}
async function upload(page,rows){
  await page.getByRole('button',{name:'导入可操作设备',exact:true}).click();const dialog=page.getByRole('dialog');
  await dialog.getByRole('button',{name:'CSV (.csv)',exact:true}).click();
  await dialog.locator('input[type="file"]').setInputFiles({name:'relations.csv',mimeType:'text/csv',buffer:Buffer.from(csv(rows))});
  const value=await post(page,PREVIEW,()=>dialog.getByRole('button',{name:'开始预检',exact:true}).click());
  return {dialog,data:value.data};
}
async function relationFiles(page,state,helpers,root,report){
  const {run,rail,search,shot,empty}=helpers;
  const prefix='RL-'+state+'-',operator=prefix+'O1',first=prefix+'M2',second=prefix+'M3';
  await run(page,state,'relation-files-seed-entities',async()=>{
    await rail(page,'设备');await search(page,'');
    await seedEntities(page,'machine',[first,second].map(code=>({business_code:code,label:'关系探针设备 '+code,status:'active',op_type_code:'RT-IN'})));
    await rail(page,'人员');await search(page,'');
    await seedEntities(page,'operator',[{business_code:operator,label:'关系探针人员',status:'active'}]);
    await search(page,prefix);await page.getByRole('button',{name:operator,exact:true}).waitFor();
  });
  await run(page,state,'relation-files-template-download',async()=>{
    await page.getByRole('button',{name:'导入可操作设备',exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'批量导入 · 可操作设备',exact:true});
    await dialog.waitFor();
    const waiting=page.waitForEvent('download');
    await dialog.getByRole('button',{name:'下载模板',exact:true}).click();
    const download=await waiting,file=path.join(root,'downloads',state+'-relation-'+download.suggestedFilename());
    await download.saveAs(file);assert.equal(await download.failure(),null);report.downloads.push(file);
    assert.equal(download.suggestedFilename(),'可操作设备导入模板.xlsx');
    await shot(page,state+'-relation-import-blank');await dismiss(page);
  });
  await run(page,state,'relation-files-rejected-blocks-confirm',async()=>{
    const {dialog,data}=await upload(page,[{工号:operator,设备编号:prefix+'NONE',技能等级:'',主操设备:''}]);
    assert.equal(data.summary.rejected,1);assert.equal(data.can_confirm,false);
    assert(await dialog.getByRole('button',{name:'确认导入',exact:true}).isDisabled());
    await dialog.getByText('系统里找不到这个编号，这一行没有导入。请先在基础资料里维护好再导入。').first().waitFor();
    await shot(page,state+'-relation-import-rejected');await dismiss(page,true);
  });
  await run(page,state,'relation-files-create-links',async()=>{
    const {dialog,data}=await upload(page,[
      {工号:operator,设备编号:first,技能等级:'熟练',主操设备:'是'},
      {工号:operator,设备编号:second,技能等级:'普通',主操设备:'否'}]);
    assert.equal(data.summary.rejected,0);assert.equal(data.summary.new,2);
    // 这个人原来没有主操设备，所以没有谁被顶掉，不该弹出需要核对的提示。
    assert(data.rows.every(row=>!row.requires_confirmation&&!row.notes.length));
    await dialog.getByText('熟练',{exact:true}).first().waitFor();
    assert.equal((await save(page,CONFIRM,dialog)).result,'committed');
  });
  await run(page,state,'relation-files-primary-handover',async()=>{
    // 第一行不填主操，靠同一份文件里的第二行把主操拿走；两行都要在预检里说清会发生什么。
    const {dialog,data}=await upload(page,[
      {工号:operator,设备编号:first,技能等级:'',主操设备:''},
      {工号:operator,设备编号:second,技能等级:'',主操设备:'是'}]);
    assert.equal(data.summary.rejected,0);assert.deepEqual(data.rows.map(row=>row.result),['update','update']);
    assert.deepEqual(data.rows[0].changes.is_primary,{before:'yes',after:'no'});
    assert.deepEqual(data.rows[1].changes.is_primary,{before:'no',after:'yes'});
    assert(data.rows.every(row=>row.requires_confirmation&&row.notes.length));
    await dialog.getByText('确认后 '+first+' 不再是这个人的主操设备。').first().waitFor();
    await dialog.getByText('这一行没有填主操设备，但同一份文件把主操给了别的设备，所以这里会变成非主操。').first().waitFor();
    await shot(page,state+'-relation-import-handover');
    assert.equal((await save(page,CONFIRM,dialog)).result,'committed');
  });
  await run(page,state,'relation-files-export-round-trip',async()=>{
    await page.getByRole('button',{name:'导出可操作设备',exact:true}).click();
    const dialog=page.getByRole('dialog');
    await dialog.locator('input[type="radio"][value="filtered"]').check();
    await dialog.getByRole('button',{name:'CSV (.csv)',exact:true}).click();
    const preview=await post(page,EXPORT,()=>dialog.getByRole('button',{name:'开始预检',exact:true}).click());
    // 筛选出的只有这一个人，但他名下有两台设备，导出按关系行数算。
    assert.equal(preview.data.row_count,2);
    const downloading=page.waitForEvent('download');
    await dialog.getByRole('button',{name:'下载文件',exact:true}).click();
    const download=await downloading,file=path.join(root,'downloads',state+'-relation-'+download.suggestedFilename());
    await download.saveAs(file);assert.equal(await download.failure(),null);report.downloads.push(file);
    assert.equal(download.suggestedFilename(),'可操作设备清单.csv');
    await shot(page,state+'-relation-export');await dismiss(page);
    await page.getByRole('button',{name:'导入可操作设备',exact:true}).click();
    const back=page.getByRole('dialog');
    await back.getByRole('button',{name:'CSV (.csv)',exact:true}).click();
    await back.locator('input[type="file"]').setInputFiles(file);
    const again=await post(page,PREVIEW,()=>back.getByRole('button',{name:'开始预检',exact:true}).click());
    assert.equal(again.data.summary.rejected,0);assert.equal(again.data.summary.unchanged,2);
    assert.equal((await save(page,CONFIRM,back)).result,'unchanged');
  });
  await run(page,state,'relation-files-cleanup',async()=>{
    // 人员和设备只要还带着可操作设备关联就删不掉，先在「编辑可操作设备」里逐条解除，
    // 这也顺带证明文件导进来的关联在界面上解得掉。解干净后再删实体，数据库回到进入这段场景之前的样子。
    await page.getByRole('button',{name:operator,exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'编辑可操作设备',exact:true}).click();
    const permissions=page.getByRole('dialog');
    await permissions.getByRole('button',{name:'解除关联',exact:true}).first().click();
    await permissions.getByRole('button',{name:'解除关联',exact:true}).first().click();
    await permissions.getByText('尚未设置可操作设备。',{exact:true}).waitFor();
    await post(page,'/machine-permissions/preview',()=>permissions.getByRole('button',{name:'预览变更',exact:true}).click());
    const saved=await post(page,'/machine-permissions/confirm',()=>permissions.getByRole('button',{name:'确认保存设备关联',exact:true}).click());
    assert.equal(saved.result,'committed');
    await permissions.getByRole('button',{name:/^(关闭|取消)$/}).first().click();
    await page.getByRole('dialog').waitFor({state:'detached'});
    await removeEntities(page,'operator',1);await empty(page);
    await rail(page,'设备');await search(page,prefix);await removeEntities(page,'machine',2);await empty(page);
  });
}
module.exports={relationFiles};
