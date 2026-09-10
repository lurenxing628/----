'use strict';
const assert=require('node:assert/strict');

async function resourceDetails(page,state,helpers){
  const {run,rail,search,row,shot,close,type,save}=helpers;
  await run(page,state,'real-internal-bindings-nested-back',async()=>{
    await rail(page,'自制工种');await search(page,'RT-IN');
    await row(page,'RT-IN').getByRole('button',{name:'查看绑定',exact:true}).click();
    await page.getByRole('button',{name:'查看设备 RT-M Lathe',exact:true}).waitFor();
    await page.getByRole('button',{name:'查看人员 RT-O Original operator',exact:true}).waitFor();
    await shot(page,state+'-internal-real-bindings');
    await page.getByRole('button',{name:'查看设备 RT-M Lathe',exact:true}).click();
    await page.getByRole('dialog',{name:'设备详情',exact:true}).waitFor();
    await page.getByRole('dialog').getByRole('button',{name:'Turning',exact:true}).click();
    await page.getByRole('button',{name:'查看人员 RT-O Original operator',exact:true}).waitFor();
    await page.getByRole('button',{name:'查看人员 RT-O Original operator',exact:true}).click();
    await page.getByRole('dialog',{name:'人员详情',exact:true}).waitFor();
    await shot(page,state+'-person-real-detail');
    await page.getByRole('button',{name:'返回上一条详情',exact:true}).click();
    await page.getByRole('dialog',{name:'自制工种详情',exact:true}).waitFor();
    await page.getByRole('button',{name:'返回上一条详情',exact:true}).click();
    await page.getByRole('dialog',{name:'设备详情',exact:true}).waitFor();
    await page.getByRole('button',{name:'返回上一条详情',exact:true}).click();
    await page.getByRole('dialog',{name:'自制工种详情',exact:true}).waitFor();
    await close(page);assert.equal(await page.getByRole('searchbox',{name:'搜索编号或名称'}).inputValue(),'RT-IN');
  });
  await run(page,state,'real-external-supplier-details',async()=>{
    await rail(page,'外协工种');await search(page,'RT-EX');
    await row(page,'RT-EX').getByRole('button',{name:'查看供应商',exact:true}).click();
    await page.getByRole('button',{name:'查看供应商 RT-S Original supplier',exact:true}).click();
    await page.getByRole('dialog',{name:'供应商详情',exact:true}).waitFor();
    await page.getByRole('dialog').getByRole('button',{name:'Heat treatment',exact:true}).click();
    await page.getByRole('button',{name:'查看供应商 RT-S Original supplier',exact:true}).waitFor();
    await shot(page,state+'-supplier-real-bindings');await close(page);
  });
  await run(page,state,'nested-edit-uses-child-kind-and-scope',async()=>{
    await rail(page,'供应商');await search(page,'RT-S');
    for(const name of ['Reviewed external '+state,'Heat treatment']){
      await row(page,'RT-S').getByRole('button',{name:'查看/编辑',exact:true}).click();
      await page.getByRole('dialog').getByRole('button',{name:name==='Heat treatment'?'Reviewed external '+state:'Heat treatment',exact:true}).click();
      await page.getByRole('dialog',{name:'外协工种详情',exact:true}).waitFor();
      await page.getByRole('dialog').getByRole('button',{name:'编辑',exact:true}).click();
      await type(page.getByRole('dialog').locator('input[name="label"]'),name);await save(page,'op_type','update');await close(page);
      await row(page,'RT-S').waitFor();assert.equal(await page.getByRole('searchbox',{name:'搜索编号或名称'}).inputValue(),'RT-S');
    }
  });
}
module.exports={resourceDetails};
