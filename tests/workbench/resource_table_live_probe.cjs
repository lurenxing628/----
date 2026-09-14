'use strict';
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const {exportSelection}=require('./resource_files_live_probe.cjs');
const configs=[
  {node:'物料',kind:'material',columns:['business_code','label','spec','stock_qty','status']},
  {node:'自制工种',kind:'op_type',category:'internal',columns:['business_code','label','available_machines','available_operators','remark']},
  {node:'设备',kind:'machine',columns:['business_code','label','op_type_ref','group_ref','status']},
  {node:'人员',kind:'operator',columns:['business_code','label','skill_refs','shift_profile_ref','status']},
  {node:'外协工种',kind:'op_type',category:'external',columns:['business_code','label','default_merge_mode','remark']},
  {node:'供应商',kind:'supplier',columns:['business_code','label','op_type_refs','default_days','status']}
];
const header=(page,key)=>page.locator('th[data-column="'+key+'"]');
const menu=page=>page.locator('[data-wb-table-filter]');
async function listChange(page,kind,action){
  const pending=page.waitForResponse(response=>{const u=new URL(response.url());return [
    '/api/workbench/v1/entities/'+kind,'/api/workbench/v1/entities/'+kind+'/query'].includes(u.pathname);});
  await action();const response=await pending;assert.equal(response.status(),200,await response.text());const result=await response.json();
  await page.locator('.wb-table[aria-busy="false"]').waitFor();return result;
}
async function openFilter(page,key){
  const pending=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/facets')&&response.request().postDataJSON().column===key);
  await header(page,key).locator('.wb-th-filter').click();const response=await pending;assert.equal(response.status(),200,await response.text());
  await menu(page).locator('.wb-table-facet-options[aria-busy="false"]').waitFor();return response.json();
}
async function clearFilter(page,kind,key){
  if(!await menu(page).count())await openFilter(page,key);
  const result=await listChange(page,kind,()=>menu(page).getByRole('button',{name:'清除',exact:true}).click());
  await menu(page).waitFor({state:'detached'});return result;
}
async function resourceTableControls(page,state,helpers,root,report){
  const {run,rail,search,shot,type,row,close,save,createEntity,openEdit}=helpers;
  report.table_actions=report.table_actions||[];
  for(let index=0;index<configs.length;index++){
    const config=configs[index];await rail(page,config.node);await search(page,'');
    await run(page,state,'table-controls-'+index,async()=>{
      assert.deepEqual(await page.locator('.wb-resource-th').evaluateAll(nodes=>nodes.map(node=>node.dataset.columnKey)),config.columns);
      for(const key of config.columns){
        const th=header(page,key),sort=th.locator('.wb-th-sort');
        for(const direction of ['ascending','descending','none']){
          await listChange(page,config.kind,()=>sort.click());assert.equal(await th.getAttribute('aria-sort'),direction);
        }
        const facets=await openFilter(page,key),option=facets.data.options[0];assert(option);
        await shot(page,state+'-table-menu-'+index+'-'+key);
        const empty=await listChange(page,config.kind,()=>menu(page).getByRole('checkbox',{name:'全选',exact:true}).uncheck());
        assert.equal(empty.data.page.total,0);assert(await menu(page).isVisible(),'Filtering must not unmount its own header/menu');
        const selected=await listChange(page,config.kind,()=>menu(page).locator('[data-facet-key="'+option.key+'"] input').check());
        assert.equal(selected.data.page.total,option.count);assert(await menu(page).isVisible());
        await menu(page).getByRole('button',{name:'关闭列筛选',exact:true}).click();await menu(page).waitFor({state:'detached'});
        assert.equal(await th.locator('.wb-th-filter').getAttribute('aria-pressed'),'true');
        if(key==='business_code'){
          const codes=selected.data.entities.map(item=>item.business_code);assert.equal(codes.length,1);
          const exported=await exportSelection(page,config,'filtered','csv',1,root,state+'-table-'+index,report);
          assert.deepEqual(exported.rows.slice(1).map(record=>record[0]),codes);
        }
        const reset=await clearFilter(page,config.kind,key);assert.equal(reset.data.page.total,facets.data.row_count);
        const grip=th.getByRole('separator');await grip.scrollIntoViewIfNeeded();
        const before=(await th.boundingBox()).width,box=await grip.boundingBox();
        await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2+24,box.y+box.height/2,{steps:5});await page.mouse.up();
        assert(Math.abs((await th.boundingBox()).width-before-24)<=2,'Pointer resize '+key);
        await grip.focus();await grip.press('ArrowLeft');assert(Math.abs((await th.boundingBox()).width-before-16)<=2,'Keyboard resize '+key);
        await grip.press('ArrowLeft');await grip.press('ArrowLeft');
        report.table_actions.push({state,kind:config.kind,category:config.category,column:key,sort_cycle:true,filter_total:option.count,empty_filter:true,clear:true,pointer_resize:true,keyboard_resize:true});
      }
    });
  }
  await run(page,state,'multi-column-and-empty-filter',async()=>{
    await rail(page,'物料');await search(page,'');const code=await openFilter(page,'business_code');
    const chosen=code.data.options.find(item=>item.label==='MAT-001');assert(chosen);
    await listChange(page,'material',()=>menu(page).getByRole('checkbox',{name:'全选',exact:true}).uncheck());
    await listChange(page,'material',()=>menu(page).locator('[data-facet-key="'+chosen.key+'"] input').check());
    await menu(page).getByRole('button',{name:'关闭列筛选',exact:true}).click();await openFilter(page,'status');
    await listChange(page,'material',()=>menu(page).getByRole('checkbox',{name:'全选',exact:true}).uncheck());
    const empty=await listChange(page,'material',()=>menu(page).getByRole('checkbox',{name:'停用',exact:true}).check());assert.equal(empty.data.page.total,0);
    const restored=await clearFilter(page,'material','status');assert.equal(restored.data.page.total,1);
    const all=await clearFilter(page,'material','business_code');assert.equal(all.data.page.total,50);
  });
  await run(page,state,'stock-quick-action-validation-save-and-backdrop-cancel',async()=>{
    await search(page,'MAT-011');
    async function stockDialog(code='MAT-011'){await row(page,code).getByRole('button',{name:'查看/编辑',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'调整库存',exact:true}).click();return page.getByRole('dialog',{name:'调整库存',exact:true});}
    let dialog=await stockDialog();assert.equal(await dialog.locator('input[name="spec"]').count(),0);assert.equal(await dialog.locator('input[name="unit"]').count(),0);
    const commands=report.commands.length;await type(dialog.locator('input[name="stock_qty"]'),'12.75');
    await page.locator('.modal-bg').click({position:{x:5,y:5}});
    const confirmation=page.getByRole('dialog',{name:'离开前确认',exact:true});await confirmation.waitFor();
    assert.equal(await dialog.locator('input[name="stock_qty"]').inputValue(),'12.75');assert.equal(report.commands.length,commands);
    await confirmation.getByRole('button',{name:'放弃未保存内容并继续',exact:true}).click();
    await confirmation.waitFor({state:'detached'});await dialog.waitFor({state:'detached'});assert.equal(report.commands.length,commands);
    dialog=await stockDialog();assert.equal(await dialog.locator('input[name="stock_qty"]').inputValue(),'');
    const unchanged=await save(page,'material','update');assert.equal(unchanged.result,'unchanged');await close(page);
    await search(page,'MAT-001');dialog=await stockDialog('MAT-001');assert.equal(await dialog.locator('input[name="stock_qty"]').inputValue(),'1.25');
    await type(dialog.locator('input[name="stock_qty"]'),'8.375');await save(page,'material','update');await close(page);
    dialog=await stockDialog('MAT-001');assert.equal(await dialog.locator('input[name="stock_qty"]').inputValue(),'8.375');await shot(page,state+'-stock-quick-action');
    const beforeClear=report.commands.length;await dialog.locator('input[name="stock_qty"]').fill('');await dialog.getByRole('button',{name:'保存',exact:true}).click();
    await dialog.getByText('库存不能清除；原值未知时可以不改。',{exact:true}).first().waitFor();assert.equal(report.commands.length,beforeClear);
    await type(dialog.locator('input[name="stock_qty"]'),'1.25');await save(page,'material','update');await close(page);
  });
  await run(page,state,'accepted-category-change-does-not-reuse-internal-filters',async()=>{
    const code='UI-CATEGORY-'+state,ref=await createEntity(page,'自制工种','op_type',code,async dialog=>type(dialog.locator('textarea[name="remark"]'),'Original category remark'));
    await listChange(page,'op_type',()=>header(page,'available_machines').locator('.wb-th-sort').click());
    const facets=await openFilter(page,'available_machines'),key=facets.data.options[0].key;
    await listChange(page,'op_type',()=>menu(page).getByRole('checkbox',{name:'全选',exact:true}).uncheck());
    await listChange(page,'op_type',()=>menu(page).locator('[data-facet-key="'+key+'"] input').check());
    await menu(page).getByRole('button',{name:'关闭列筛选',exact:true}).click();await openEdit(page,code);
    await type(page.getByRole('dialog').locator('textarea[name="remark"]'),'Reviewed category remark');
    const endpoint=new URL('/api/workbench/v1/entities/op_type/'+ref,page.url()).href;
    const detail=await page.request.get(endpoint);assert.equal(detail.status(),200);const current=await detail.json();
    const request_key='resource-'+crypto.randomBytes(24).toString('hex');
    const response=await page.request.post(endpoint+'/update',{data:{request_key,write_token:current.data.write_context.write_token,input:{fields:{category:'external'}}}});
    assert.equal(response.status(),200,await response.text());const receipt=await response.json();
    report.commands.push({state,path:new URL(endpoint).pathname+'/update',request_key,result:receipt.result,receipt_ref:receipt.receipt_ref,status:200,evidence:'external-fixture-maintenance-not-a-prototype-control'});
    await save(page,'op_type','update',409);
    await page.getByRole('button',{name:'刷新最新资料',exact:true}).click();await page.getByRole('button',{name:'已核对，继续编辑',exact:true}).click();
    await page.getByRole('dialog',{name:'编辑外协工种',exact:true}).waitFor();assert.equal(await page.getByRole('dialog').locator('textarea[name="remark"]').inputValue(),'Reviewed category remark');
    await save(page,'op_type','update');await close(page);await helpers.empty(page);
    await rail(page,'外协工种');await search(page,code);await row(page,code).getByRole('button',{name:'删除',exact:true}).click();await save(page,'op_type','delete');await close(page);
  });
}
module.exports={resourceTableControls};
