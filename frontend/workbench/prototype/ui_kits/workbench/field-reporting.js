(function () {
 "use strict";
 const ns=window.APSFieldReports;
 ns.mount=function(root){
  root.innerHTML=ns.markup;
  const q=s=>root.querySelector(s),{tasks,state,corrections,summary,validateReport,isOperationComplete}=ns.model;
  const views=ns.createViews(root),{esc,icon,filtered,icons}=views;
  const tools={workbook:ns.workbook,importer:ns.createImportTools};
  const listeners=[],on=(type,handler)=>{root.addEventListener(type,handler);listeners.push([type,handler]);};
  let disabledRegions=[],previousOverflow=null,importJob=null,focusBefore=null;
function lockBackground(){
  const shell=root.closest('.app-container');
  const regions=[q('.r-body'),...(shell?shell.querySelectorAll('.sidebar,.top-header,.kit-foot'):[])];
  disabledRegions=regions.map(el=>({el,inert:el.hasAttribute('inert')}));
  disabledRegions.forEach(({el})=>el.setAttribute('inert',''));
  previousOverflow=document.body.style.overflow;document.body.style.overflow='hidden';
}
function unlockBackground(){
  disabledRegions.forEach(({el,inert})=>{if(!inert)el.removeAttribute('inert');});disabledRegions=[];
  if(previousOverflow!==null)document.body.style.overflow=previousOverflow;previousOverflow=null;
}
  const reportEditor=ns.createEditor(root,views);
  const render=()=>reportEditor.render();
  function closeImport(){
    if(!importJob)return;importJob=null;q('#r-editor-layer').hidden=true;q('#r-editor-layer').innerHTML='';unlockBackground();delete root.dataset.editor;
    if(focusBefore&&focusBefore.isConnected)focusBefore.focus({preventScroll:true});
  }
  const closeEditor=()=>importJob?closeImport():reportEditor.close({discard:true});
function getImportTools(){return tools.importer({XLSX:tools.workbook,tasks,validate:validateReport,clock:()=>state.clock,isOperationComplete});}
function downloadWorkbook(workbook,name){
  const data=tools.workbook.write(workbook,{type:'array',bookType:'xlsx'}),blob=new Blob([data],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}),url=URL.createObjectURL(blob);
  const link=document.createElement('a');link.href=url;link.download=name;root.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);
 }
function downloadTemplate(){downloadWorkbook(getImportTools().buildTemplate(),'现场分次报工模板.xlsx');}
function downloadReports(){
  const selected=filtered();if(!selected.length)return;
  try{
    const x=tools.workbook,template=getImportTools().buildTemplate();
    const headers=x.utils.sheet_to_json(template.Sheets[template.SheetNames[0]],{header:1})[0];
    const records=[headers],metadata=[['报工编号','记录ID','批次号','工序','录入 / 修改时间','修订次数']];
    const totals=[['批次号','名称','工序','应做数量','累计完成','剩余数量','工序状态','计划设备','计划人员','计划开工','计划完工','实际开工','整道实际完工','最近作业结束','累计有效工时(h)','待补记录数']];
    selected.forEach(t=>{
      const s=summary(t);
      s.reports.forEach(r=>{
        records.push([r.reportNo,t.batch,t.op,r.qty===null?'':r.qty,r.start,r.end,r.hours===null?'':r.hours,r.machine,r.person,r.remark]);
        metadata.push([r.reportNo,r.id,t.batch,t.op,r.recorded,r.revision]);
      });
      totals.push([t.batch,t.name,t.op,t.target,s.qty,s.remaining,ns.model.labels[s.status],t.machine,t.person,t.planStart,t.planEnd,s.start,s.end,s.latest,t.reports.some(r=>r.hours!==null)?s.hours:'',s.incomplete]);
    });
    const book=x.utils.book_new();
    const sheets=[['报工记录',records,[25,20,18,18,23,23,23,18,18,45]],['工序汇总',totals,[20,22,18,12,12,12,18,14,14,23,23,23,23,23,22,14]],['录入信息',metadata,[25,30,20,18,23,12]]];
    sheets.forEach(([name,rows,widths])=>{const sheet=x.utils.aoa_to_sheet(rows);sheet['!cols']=widths.map(wch=>({wch}));x.utils.book_append_sheet(book,sheet,name);});
    downloadWorkbook(book,'现场报工导出-'+new Date(state.clock).toISOString().slice(0,10)+'.xlsx');
    state.status='已导出 '+selected.length+' 道工序 · '+(records.length-1)+' 条已保存报工（示例）';
  }catch(error){state.status='导出失败：'+error.message;}
  render();
}
function downloadImportErrors(){
  if(!importJob||!importJob.result)return;
  const x=tools.workbook,book=x.utils.book_new();x.utils.book_append_sheet(book,x.utils.aoa_to_sheet([['行号','问题'],...importJob.result.errors.map(e=>[e.row,e.message])]),'导入问题');downloadWorkbook(book,'报工导入问题.xlsx');
 }
function openImport(){
  reportEditor.close({focus:false});if(importJob)closeImport();focusBefore=document.activeElement;importJob={file:null,result:null,busy:false};root.dataset.editor='import';
  q('#r-editor-layer').innerHTML='<section class="r-editor" role="dialog" aria-modal="true" aria-labelledby="r-import-title"><header class="r-editor-head"><h2 id="r-import-title">批量导入报工</h2><button class="r-icon" data-close aria-label="关闭导入窗口">'+icon('x')+'</button></header><div class="r-editor-body"><div class="r-template-row"><div><h3>现场分次报工模板.xlsx</h3><span class="r-sub">已带入待报工批次、工序与资源</span></div><button class="r-action wb-action wb-transfer" data-wb-transfer="template" data-download-template>'+icon('file-down')+'下载模板</button></div><div class="r-field"><span>报工文件</span><div class="bd-upload"><button type="button" class="r-action r-upload-select" data-choose-file aria-controls="r-import-file">'+icon('folder-open')+'选择 Excel 文件</button><input type="file" accept=".xlsx" id="r-import-file" aria-label="选择报工 Excel 文件" hidden><span class="up-file" id="r-import-name">尚未选择文件</span></div></div><div class="r-meta" style="margin-top:12px;margin-bottom:0"><span>.xlsx · 首个工作表 · 最多 5000 条</span><span>追加报工 / 补全未完成记录</span></div><div id="r-import-result" aria-live="polite"></div></div><footer class="r-editor-foot"><span class="r-caption">仅导入到本次示例会话</span><span class="r-inline"><button class="r-action" data-close>取消</button><button class="r-action primary wb-action wb-transfer wb-primary" data-wb-transfer="import" data-import-run disabled>'+icon('file-input')+'直接导入</button></span></footer></section>';
  q('#r-editor-layer').hidden=false;lockBackground();icons();q('[data-choose-file]').focus({preventScroll:true});
 }
function showImportResult(result){
  const errors=result.errors||[];
  q('#r-import-result').innerHTML=errors.length?'<div class="r-import-status r-red">'+icon('circle-alert')+'未写入任何数据 · '+errors.length+' 个问题</div><table class="r-import-result-table"><thead><tr><th>Excel 行号</th><th>问题</th></tr></thead><tbody>'+errors.slice(0,8).map(e=>'<tr><td>'+esc(e.row)+'</td><td>'+esc(e.message)+'</td></tr>').join('')+'</tbody></table><div class="r-detail-bottom"><span>'+(errors.length>8?'另有 '+(errors.length-8)+' 个问题':'修改文件后可重新导入')+'</span><button class="r-action" data-import-errors>'+icon('download')+'下载问题清单</button></div>':'<div class="r-import-status r-green">'+icon('circle-check')+((result.added||result.supplemented||result.finished)?'导入完成':'没有新增报工')+'</div><div class="r-inline-stats"><span>新增 <b>'+result.added+'</b> 条</span><span>补全 <b>'+result.supplemented+'</b> 条</span><span>重复 <b>'+result.duplicates+'</b> 条</span><span>自动完工 <b>'+(result.finished||0)+'</b> 道</span></div><span class="r-sub">空白记录 '+result.blank+' 条 · 已有实际记录未被覆盖</span>';
  const button=q('[data-import-run]');button.disabled=false;button.textContent=errors.length?'重新导入':'完成';q('#r-import-file').disabled=false;q('[data-choose-file]').disabled=false;icons();
 }
async function runImport(){
  if(!importJob||importJob.busy)return;if(importJob.result&&!importJob.result.errors.length){closeEditor();return;}
  const job=importJob,file=job.file;if(!file)return;
  job.busy=true;q('[data-import-run]').disabled=true;q('[data-import-run]').textContent='正在导入';q('#r-import-file').disabled=true;q('[data-choose-file]').disabled=true;q('#r-import-result').innerHTML='';
  try{
   if(!/\.xlsx$/i.test(file.name))throw new Error('请选择 .xlsx 格式的 Excel 文件。');
   if(file.size>8*1024*1024)throw new Error('文件超过 8 MB，请按日期或车间拆分后导入。');
   const bytes=await file.arrayBuffer();if(importJob!==job)return;
   const header=new Uint8Array(bytes);if(header[0]!==80||header[1]!==75||header[2]!==3||header[3]!==4)throw new Error('文件不是有效的 .xlsx 工作簿。');
   const workbook=tools.workbook.read(bytes,{type:'array',cellDates:false,cellFormula:true});
   const result=getImportTools().planImport(workbook);job.result=result;
   result.finished=result.errors.length?0:result.tasks.filter((t,i)=>isOperationComplete(t)&&!isOperationComplete(tasks[i])).length;
   const changed=result.tasks.find((t,i)=>JSON.stringify(t)!==JSON.stringify(tasks[i]));
   if(!result.errors.length&&changed){
    tasks.splice(0,tasks.length,...result.tasks);state.clock+=60000;
    (result.revisions||[]).forEach(r=>corrections.push({...r,time:new Date(state.clock).toISOString().slice(0,16)}));
    state.filter='all';state.search='';q('#r-search').value='';if(changed){state.selected=changed.id;state.expanded=changed.id;}
    state.status='Excel 导入：新增 '+result.added+' 条、补全 '+result.supplemented+' 条、自动完工 '+result.finished+' 道（示例）';render();
   }
   showImportResult(result);
  }catch(e){if(importJob!==job)return;job.result={errors:[{row:'文件',message:e.message||'文件解析失败，请检查工作簿内容。'}]};showImportResult(job.result);}
  finally{if(importJob===job)job.busy=false;}
 }
  on('click',event=>{
    const b=event.target.closest('button');if(!b||!root.contains(b)||b.disabled)return;
    if(b.dataset.qty){event.preventDefault();return reportEditor.changeQuantity(b.dataset.qty);}
    if(b.hasAttribute('data-complete-rest')){event.preventDefault();return reportEditor.completeRest();}
    if(b.hasAttribute('data-choose-file')){if(importJob&&!importJob.busy){q('#r-import-file').value='';q('#r-import-file').click();}return;}
    if(b.hasAttribute('data-open-import'))return openImport();
    if(b.hasAttribute('data-download-template'))return downloadTemplate();
    if(b.hasAttribute('data-export-reports'))return downloadReports();
    if(b.hasAttribute('data-import-run'))return runImport();
    if(b.hasAttribute('data-import-errors'))return downloadImportErrors();
    if(b.dataset.timeline){state.timelines[b.dataset.timeline]=!state.timelines[b.dataset.timeline];render();q('[data-timeline="'+b.dataset.timeline+'"]').focus({preventScroll:true});return;}
    if(b.dataset.reportInfo){state.reportInfo[b.dataset.reportInfo]=!state.reportInfo[b.dataset.reportInfo];render();[...root.querySelectorAll('[data-report-info]')].find(el=>el.dataset.reportInfo===b.dataset.reportInfo).focus({preventScroll:true});return;}
    if(b.dataset.filter){state.filter=b.dataset.filter;render();q('[data-filter="'+state.filter+'"]').focus({preventScroll:true});return;}
    if(b.dataset.expand){state.selected=b.dataset.expand;state.expanded=state.expanded===b.dataset.expand?'':b.dataset.expand;render();q('[data-expand="'+b.dataset.expand+'"]').focus({preventScroll:true});return;}
    if(b.dataset.add||b.dataset.edit){
      const opened=reportEditor.toggle(b.dataset.add||b.dataset.task,b.dataset.edit||null);
      if(!opened&&b.isConnected)b.focus({preventScroll:true});return;
    }
    if(b.hasAttribute('data-add-current')){const t=filtered().find(t=>t.id===state.selected&&!isOperationComplete(t))||filtered().find(t=>!isOperationComplete(t));if(t)return reportEditor.open(t.id,null);state.status='当前筛选中没有待报工工序';render();return;}
    if(b.hasAttribute('data-close'))return closeEditor();
    if(b.hasAttribute('data-save')){event.preventDefault();return reportEditor.save();}
  });
  on('input',event=>{if(event.target.id==='r-search'){state.search=event.target.value;render();}else if(event.target.closest('#r-report-form'))reportEditor.preview();});
  on('change',event=>{
    if(event.target.id==='r-import-file'){const file=event.target.files&&event.target.files[0];importJob={file,result:null,busy:false};q('#r-import-name').textContent=file?file.name:'尚未选择文件';q('[data-import-run]').disabled=!file;q('[data-import-run]').textContent='直接导入';q('#r-import-result').innerHTML='';return;}
    if(event.target.closest('#r-report-form'))reportEditor.preview();
  });
  on('submit',event=>{if(event.target.id==='r-report-form'){event.preventDefault();reportEditor.save();}});
  on('keydown',event=>{
    if(event.defaultPrevented)return;
    if(event.target.name==='qty'&&['ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();return reportEditor.changeQuantity(event.key==='ArrowUp'?'up':'down');}
    if(event.key==='Escape'){if(importJob)closeImport();else reportEditor.close();return;}
    if(event.key!=='Tab'||!importJob)return;
    const controls=[...q('.r-editor').querySelectorAll('button,input,select,textarea')].filter(e=>!e.disabled&&e.type!=='hidden'&&!e.hidden&&!e.closest('[hidden]')&&getComputedStyle(e).display!=='none'&&getComputedStyle(e.parentElement).display!=='none');
    const first=controls[0],last=controls[controls.length-1];
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  });
  q('#r-search').value=state.search;render();
  return function(){reportEditor.close({focus:false});closeImport();listeners.forEach(([type,handler])=>root.removeEventListener(type,handler));root.innerHTML='';};
 };
})();
