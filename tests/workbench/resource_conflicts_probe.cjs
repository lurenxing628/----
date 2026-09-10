'use strict';
const assert=require('node:assert/strict');
const {select}=require('./custom_control_actions.cjs');

async function conflicts(page,context,state,helpers,report,origin){
  const {run,createEntity,openEdit,type,search,close,save,row,watch,readEntity}=helpers;
  const code='UI-RACE-'+state;
  const ref=await createEntity(page,'物料','material',code,async dialog=>{
    await type(dialog.locator('input[name="spec"]'),'Original spec');await type(dialog.locator('input[name="stock_qty"]'),'9.5');await select(dialog.locator('select[name="status"]'),'active');
  });
  await run(page,state,'two-window-stale-review-preserves-fields',async()=>{
    await openEdit(page,code);await type(page.getByRole('dialog').locator('input[name="label"]'),'Primary reviewed name');
    const other=await context.newPage();watch(other,state+'-other');
    try{
      await other.goto(origin+'/workbench?view=process');await other.getByRole('button',{name:'MAT-001',exact:true}).waitFor();await search(other,code);
      await openEdit(other,code);await type(other.getByRole('dialog').locator('input[name="spec"]'),'Other window spec');await type(other.getByRole('dialog').locator('input[name="unit"]'),'件');
      await save(other,'material','update');await close(other);
    }finally{await other.close();}
    const rejected=await save(page,'material','update',409);assert.equal(rejected.error.code,'stale_write');
    assert.equal(await page.getByRole('dialog').locator('input[name="label"]').inputValue(),'Primary reviewed name');
    await page.getByRole('button',{name:'重新读取最新资料',exact:true}).click();await page.getByRole('button',{name:'已核对，继续编辑',exact:true}).click();
    assert.equal(await page.getByRole('dialog').locator('input[name="spec"]').inputValue(),'Other window spec');
    assert.equal(await page.getByRole('dialog').locator('input[name="unit"]').inputValue(),'件');
    assert.equal(await page.getByRole('dialog').locator('input[name="label"]').inputValue(),'Primary reviewed name');
    await save(page,'material','update');await close(page);
    const actual=await readEntity(context,'material',ref);assert.equal(actual.label,'Primary reviewed name');assert.equal(actual.fields.spec,'Other window spec');assert.equal(actual.fields.stock_qty,9.5);
  });
  await run(page,state,'lost-response-reload-resolves-same-request',async()=>{
    const update='/api/workbench/v1/entities/material/'+ref+'/update', updateMatcher=url=>url.pathname===update;let intent,committed;
    const handler=async route=>{
      intent=route.request().postDataJSON();const response=await route.fetch();assert.equal(response.status(),200);committed=await response.json();
      report.commands.push({state,path:update,request_key:intent.request_key,result:committed.result,receipt_ref:committed.receipt_ref,status:200,evidence:'real-response-captured-before-disconnect'});
      await route.abort('failed');
    };
    const receiptMatcher=url=>url.pathname.startsWith('/api/workbench/v1/commands/');const missing=route=>route.abort('failed');
    await page.route(updateMatcher,handler);await page.route(receiptMatcher,missing);
    try{
      await openEdit(page,code);await type(page.getByRole('dialog').locator('input[name="label"]'),'Recovered after disconnect');
      await page.getByRole('dialog').getByRole('button',{name:'保存',exact:true}).click();await page.getByText('结果待核实。请保留当前页面，不要重新新建或重复保存。',{exact:true}).waitFor();
      await page.locator('.modal-bg').click({position:{x:5,y:5}});assert(await page.getByText('结果待核实。请保留当前页面，不要重新新建或重复保存。',{exact:true}).isVisible());
      assert.equal(committed.result,'committed');
      const storage=await page.evaluate(()=>sessionStorage.getItem('aps_workbench_resource_pending_v1'));
      assert.equal(JSON.parse(storage).request_key,intent.request_key);assert(!storage.includes('write_token'));assert(!storage.includes('Recovered after disconnect'));
      report.expected_failures.push({state,kind:'lost-success-response-and-receipt-connection',request_key:intent.request_key,paths:[update,'/api/workbench/v1/commands/'+intent.request_key]});
    }finally{await page.unroute(updateMatcher,handler);await page.unroute(receiptMatcher,missing);}
    page.on('dialog',dialog=>dialog.accept());await page.reload();
    await page.getByText('服务器已确认提交。',{exact:true}).waitFor();await close(page);
    await search(page,code);await row(page,code).waitFor();assert.equal((await readEntity(context,'material',ref)).label,'Recovered after disconnect');
    assert.equal(await page.evaluate(()=>sessionStorage.getItem('aps_workbench_resource_pending_v1')),null);
    await row(page,code).getByRole('button',{name:'删除',exact:true}).click();await save(page,'material','delete');await close(page);
  });
}
module.exports={conflicts};
