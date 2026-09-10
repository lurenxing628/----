(function () {
 "use strict";
 const ns=window.APSDashboard;
 const model=ns.model=ns.createModel();
 ns.mount=function (root,onNav) {
 root.innerHTML=ns.markup;
 const q=s=>root.querySelector(s);
 const {stamp,short,num,actualRows,externalRows,state,handling,recordLog,stats,plans,caseInfo}=model;
 const {render,icons,esc,icon,badge,note,detailLinks,statusTone}=ns.createViews(root,model);
 const listeners=[];
 const on=(type,handler)=>{root.addEventListener(type,handler);listeners.push([type,handler]);};
 let lastFocus=null,modalKind=null,modalId=null,modalNavigation=null;
 let disabledRegions=[],previousOverflow=null;
 function lockBackground(){
  disabledRegions=[...document.querySelectorAll('.dashboard-shell .sidebar,.dashboard-shell .top-header,.dashboard-shell .kit-foot'),q('.d-body')].map(el=>({el,inert:el.hasAttribute('inert')}));
  disabledRegions.forEach(({el})=>el.setAttribute('inert',''));
  previousOverflow=document.body.style.overflow;
  document.body.style.overflow='hidden';
 }
 function unlockBackground(){
  disabledRegions.forEach(({el,inert})=>{if(!inert)el.removeAttribute('inert');});
  disabledRegions=[];
  if(previousOverflow!==null)document.body.style.overflow=previousOverflow;
  previousOverflow=null;
 }
 const field=(label,name,value,type='text',wide=false)=>'<label class="d-field'+(wide?' wide':'')+'"><span>'+label+'</span><input name="'+name+'" type="'+type+'" value="'+esc(value)+'"'+(type==='number'?' min="0" step="0.1"':'')+'></label>';
 const textarea=(label,name,value)=>'<label class="d-field wide"><span>'+label+'</span><textarea name="'+name+'">'+esc(value)+'</textarea></label>';
 function handlingForm(id){
  const r=model.entry(id),h=handling[id],draft=state.drafts[id]||h,closed=h.status==='已关闭';
  return note(r.source+' · '+model.provenance.label+' · '+model.provenance.snapshot.replace('T',' '))+'<p class="d-note">'+esc(r.detail)+'</p><fieldset class="d-handling-fields"'+(closed?' disabled':'')+'><div class="d-form-grid"><label class="d-field"><span>处置状态</span><select name="status">'+model.statuses.map(s=>'<option'+(draft.status===s?' selected':'')+'>'+s+'</option>').join('')+'</select></label>'+field('责任人','owner',draft.owner)+field('责任期限','deadline',draft.deadline,'date')+field('处置动作','action',draft.action)+textarea('证据备注','remark',draft.remark)+'</div><fieldset class="d-completion-fields"><legend>关闭凭据（关闭时全部必填）</legend><div class="d-form-grid">'+field('完成时间','completedAt',draft.completedAt,'datetime-local')+field('凭据编号 / 文件位置','evidenceRef',draft.evidenceRef)+textarea('具体完成结果','completionEvidence',draft.completionEvidence)+'</div></fieldset></fieldset>'+note('示例当前时点 '+new Date(state.clock).toISOString().slice(0,16).replace('T',' ')+'；完成凭据为人工声明，关闭不改计算风险。')+(closed?'<div class="d-actions"><button type="button" class="d-button" data-reopen-item="'+id+'">重开条目</button></div>':'')+'<div class="d-related-pages"><span class="d-caption">关联页面 · 未建立条目映射</span><div class="d-actions">'+detailLinks(r)+'</div></div>';
 }
 function openModal(kind,id,page){
  if(q('#d-modal-layer').hidden)lastFocus=document.activeElement;else unlockBackground();
  modalKind=kind;modalId=id||null;modalNavigation=null;
  let title='',body='',submit='保存记录';
  if(kind==='actual'){
   const r=actualRows.find(x=>x.id===id);title='值班台样例回填 · '+r.batch;
   body='<p class="d-note" style="margin-bottom:13px">'+r.op+' · '+r.resource+' · 定额 '+r.quota+'h</p><div class="d-form-grid">'+field('实际开工','start',r.start,'datetime-local')+field('实际完工','end',r.end,'datetime-local')+field('实际工时（h）','hours',r.hours===null?'':r.hours,'number',true)+'</div><p class="d-input-source">仅更新'+esc(model.provenance.label)+'，不写入现场报工样例。</p>';
  }else if(kind==='external'){
   const r=externalRows.find(x=>x.id===id);title='外协回厂登记 · '+r.batch;
   body='<p class="d-note" style="margin-bottom:13px">'+r.supplier+' · '+r.op+'</p><div class="d-form-grid">'+field('发出时间','sent',r.sent,'datetime-local')+field('计划回厂','planned',r.planned,'datetime-local')+field('实际回厂','returned',r.returned,'datetime-local')+'<label class="d-field"><span>确认状态</span><select name="confirmedState"><option'+(r.state==='在途'?' selected':'')+'>在途</option><option'+(r.state==='已回厂'?' selected':'')+'>已回厂</option><option'+(r.state==='待确认'?' selected':'')+'>待确认</option></select></label></div><p class="d-input-source">未来录入项 / 人工确认，不由外协周期推算实际值</p>';
  }else if(kind==='handling'){
   const r=model.entry(id);state.selectedItem=id;title='条目处置 · '+r.subject;body=handlingForm(id);submit=handling[id].status==='已关闭'?'返回清单':'保存处置';
  }else if(kind==='reopen'){
   title='重开 · '+model.entry(id).subject;submit='确认重开';body=textarea('重开原因','reason','')+note('保留原关闭记录与凭据；本轮重新填写完成证据，不沿用旧凭据直接关闭。');
  }else if(kind==='navigation'){
   modalNavigation=model.navigation(id,page);title='关联页面 · '+modalNavigation.label;submit='打开'+modalNavigation.label+'概览';
   body='<p class="d-note">'+esc(model.entry(id).subject)+'</p>'+note(modalNavigation.reason)+'<p class="d-note">目标来源：'+esc(modalNavigation.targetSource)+'。仅打开页面概览，不筛选或高亮其他样例批次，不代表该异常已定位或已处理。</p>';
  }else if(kind==='plan'){
   const s=stats(state.plan),p=plans[state.plan];title='方案摘要 · '+p.name;submit='返回比较';
   body='<p class="d-confirm">'+badge('候选结果示例','blue')+'</p><dl class="d-fact-grid" style="margin-top:15px"><div><dt>预计晚交</dt><dd>'+s.late+' 批</dd></div><div><dt>总拖期</dt><dd>'+num(s.total)+'h</dd></div><div><dt>换型</dt><dd>'+p.switches+' 次</dd></div><div><dt>换设备工序</dt><dd>'+p.moves+' 道</dd></div></dl><p class="d-note" style="margin-top:14px">保留当前方案与其他候选，实际采用应在完整排程校验后确认。此样板未调用后台试算或写回正式计划。</p>';
  }
  q('#d-modal-layer').innerHTML='<form class="d-modal" id="d-edit-form" role="dialog" aria-modal="true" aria-labelledby="d-modal-title"><div class="d-modal-head"><h3 id="d-modal-title">'+esc(title)+'</h3><button type="button" class="d-icon" data-close-modal aria-label="关闭">'+icon('x')+'</button></div><div class="d-modal-body">'+body+'<div class="d-form-error" id="d-form-error" role="alert" hidden></div></div><div class="d-modal-foot"><button type="button" class="d-button" data-close-modal>取消</button><button type="submit" class="d-button primary">'+submit+'</button></div></form>';
  q('#d-modal-layer').hidden=false;lockBackground();icons();
  const focus=[...q('#d-edit-form').querySelectorAll('input,select,textarea,button')].find(el=>!el.matches(':disabled'));if(focus)focus.focus({preventScroll:true});
 }
 function closeModal(){q('#d-modal-layer').hidden=true;q('#d-modal-layer').innerHTML='';unlockBackground();modalKind=null;modalId=null;if(lastFocus&&lastFocus.isConnected)lastFocus.focus({preventScroll:true});else{const target=q('[data-tab="'+state.tab+'"]');if(target)target.focus({preventScroll:true});}}
 function error(text){q('#d-form-error').hidden=false;q('#d-form-error').textContent=text;}
 on('submit',event=>{
  if(event.target.id!=='d-edit-form')return;event.preventDefault();
  if(modalKind==='plan'){closeModal();return;}
  if(modalKind==='navigation'){
   try{if(typeof onNav!=='function')throw new Error('页面导航尚未接入，未离开值班台。');if(onNav(modalNavigation.page,modalNavigation.context)===false)throw new Error('目标页面未接受导航，未完成跳转。');}
   catch(e){return error(e.message);}
   closeModal();return;
  }
  const form=event.target,values=Object.fromEntries(new FormData(form));
  if(modalKind==='handling'||modalKind==='reopen'){
   if(modalKind==='handling'&&handling[modalId].status==='已关闭'){closeModal();return;}
   try{if(modalKind==='reopen')model.reopen(modalId,values.reason);else model.updateHandling(modalId,values);}
   catch(e){return error(e.message);}
   render();closeModal();return;
  }
  if(modalKind==='actual'){
   const r=actualRows.find(x=>x.id===modalId);let hoursValue=values.hours.trim()===''?null:Number(values.hours);
   if(values.end&&!values.start)return error('请同时填写实际开工时间。');
   if(values.end&&stamp(values.end)<=stamp(values.start))return error('实际完工必须晚于实际开工。');
   if((values.start&&stamp(values.start)>state.clock)||(values.end&&stamp(values.end)>state.clock))return error('实际时间不能晚于示例当前时点。');
   if(hoursValue!==null&&(!Number.isFinite(hoursValue)||hoursValue<0))return error('工时必须为非负数。');
   if(hoursValue===null&&values.start&&values.end)hoursValue=Math.round((stamp(values.end)-stamp(values.start))/3600000*10)/10;
   const before={start:r.start,end:r.end,hours:r.hours},after={start:values.start,end:values.end,hours:hoursValue};
   Object.assign(r,after);model.recordInput('actual',r.id,'更新样例回填',before,after);
  }else if(modalKind==='external'){
   const r=externalRows.find(x=>x.id===modalId);
   if(!values.sent||!values.planned)return error('请填写发出时间和计划回厂时间。');
   if(stamp(values.planned)<stamp(values.sent))return error('计划回厂不能早于发出时间。');
   if(values.returned&&stamp(values.returned)<stamp(values.sent))return error('实际回厂不能早于发出时间。');
   if(stamp(values.sent)>state.clock||(values.returned&&stamp(values.returned)>state.clock))return error('发出和实际回厂不能晚于示例当前时点。');
   if((values.confirmedState==='已回厂')!==Boolean(values.returned))return error('已回厂状态与实际回厂时间必须同时填写；未回厂时请保留实际时间为空。');
   const before={sent:r.sent,planned:r.planned,returned:r.returned,state:r.state,confirmed:r.confirmed},after={sent:values.sent,planned:values.planned,returned:values.returned,state:values.confirmedState,confirmed:new Date(state.clock+60000).toISOString().slice(0,16)};
   Object.assign(r,after);model.recordInput('external',r.id,'更新样例外协登记',before,after);
  }
  render();closeModal();
 });
 function selectCase(id,tab='items'){state.caseId=id;state.tab=tab;const list=model.items(id);state.selectedItem=list.length?list[0].id:'';render();q('#d-cases [data-case="'+id+'"]').focus({preventScroll:true});}
 on('click',event=>{
  const b=event.target.closest('button');if(!b||!root.contains(b))return;
  if(b.dataset.case)return selectCase(b.dataset.case);
  if(b.dataset.navCase)return selectCase(b.dataset.navCase);
  if(b.dataset.tab){state.tab=b.dataset.tab;render();return;}
  if(b.dataset.batch){state.selectedBatch=b.dataset.batch;const entry=model.entries.find(r=>r.category===state.caseId&&r.subject.startsWith(b.dataset.batch+' · '));if(entry)state.selectedItem=entry.id;render();const target=q('[data-batch="'+state.selectedBatch+'"]');if(target)target.focus({preventScroll:true});return;}
  if(b.hasAttribute('data-view-compare')){state.tab='compare';render();q('[data-tab="compare"]').focus({preventScroll:true});return;}
  if(b.dataset.handleItem)return openModal('handling',b.dataset.handleItem);
  if(b.dataset.reopenItem)return openModal('reopen',b.dataset.reopenItem);
  if(b.dataset.itemNav)return openModal('navigation',b.dataset.itemNav,b.dataset.page);
  if(b.dataset.itemHistory){if(!q('#d-modal-layer').hidden)closeModal();state.selectedItem=b.dataset.itemHistory;state.tab='records';render();q('[data-tab="records"]').focus({preventScroll:true});return;}
  if(b.hasAttribute('data-clear-filter')){state.filter='all';state.search='';render();q('[name="d-status-filter"]').focus();return;}
  if(b.dataset.editActual)return openModal('actual',b.dataset.editActual);
  if(b.dataset.editExternal)return openModal('external',b.dataset.editExternal);
  if(b.hasAttribute('data-preview-plan'))return openModal('plan');
  if(b.hasAttribute('data-close-modal')){if(modalKind==='handling')delete state.drafts[modalId];return closeModal();}
 });
 function captureDraft(){if(modalKind==='handling'&&handling[modalId].status!=='已关闭')state.drafts[modalId]=Object.fromEntries(new FormData(q('#d-edit-form')));}
 on('input',event=>{
  if(event.target.closest('#d-edit-form'))captureDraft();
  if(event.target.name==='d-item-search'){state.search=event.target.value;render();q('[name="d-item-search"]').focus({preventScroll:true});}
 });
 on('change',event=>{
  if(event.target.closest('#d-edit-form'))captureDraft();
  if(event.target.name==='d-plan-choice'){state.plan=event.target.value;render();const target=q('input[name="d-plan-choice"][value="'+state.plan+'"]');if(target)target.focus({preventScroll:true});}
  if(event.target.name==='d-status-filter'){state.filter=event.target.value;render();q('[name="d-status-filter"]').focus({preventScroll:true});}
  if(event.target.name==='d-history-item'){state.selectedItem=event.target.value;render();q('[name="d-history-item"]').focus({preventScroll:true});}
  if(event.target.name==='d-category'){selectCase(event.target.value);q('[name="d-category"]').focus({preventScroll:true});}
 });
 on('keydown',event=>{
  if(event.key==='Escape'&&!q('#d-modal-layer').hidden){event.preventDefault();if(modalKind==='handling')delete state.drafts[modalId];closeModal();return;}
  if(event.key==='Tab'&&!q('#d-modal-layer').hidden){const list=[...q('#d-edit-form').querySelectorAll('button,input,select,textarea')].filter(e=>!e.matches(':disabled')),first=list[0],last=list[list.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}
  if(event.target.matches('[data-tab]')&&['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){const tabs=[...root.querySelectorAll('[data-tab]')],i=tabs.indexOf(event.target),n=event.key==='Home'?0:event.key==='End'?tabs.length-1:(i+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;event.preventDefault();state.tab=tabs[n].dataset.tab;render();tabs[n].focus();}
 });
 render();
 return function () {unlockBackground();listeners.forEach(([type,handler])=>root.removeEventListener(type,handler));root.innerHTML="";};
 };
})();
