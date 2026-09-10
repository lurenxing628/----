(function () {
  const ns=window.APSFieldReports;
  ns.createEditor=function(root,views){
    const q=s=>root.querySelector(s),{ms,number,tasks,state,corrections,getTask,complete,isOperationComplete,quantityLimit,validateReport}=ns.model;
    const formMarkup=ns.createForm(views),{esc,icons}=views;
    let active=null,calendarCleanup=null,lastFocus=null,nextId=5;
    const formValues=()=>Object.fromEntries(new FormData(q('#r-report-form')));
    const draftKey=e=>e.taskId+':'+(e.reportId||'new');
    const reportFor=(task,id)=>id?task.reports.find(r=>r.id===id):task.reports.find(r=>!complete(r));
    function matches(taskId,reportId){
      if(!active||active.taskId!==taskId)return false;
      const report=reportFor(getTask(taskId),reportId);return active.reportId===(report?report.id:null);
    }
    function syncTriggers(){
      root.querySelectorAll('[data-add],[data-edit]').forEach(button=>{
        const expanded=matches(button.dataset.add||button.dataset.task,button.dataset.edit||null);
        button.setAttribute('aria-expanded',String(expanded));
        button.title=expanded?'收起填报区':button.dataset.tooltip||button.getAttribute('aria-label');
      });
    }
    function stash(){
      if(active&&q('#r-report-form'))state.drafts[draftKey(active)]={values:formValues(),extraOpen:Boolean(q('.r-extra')&&q('.r-extra').open),revision:active.revision};
    }
    function close({discard=false,focus=true}={}){
      if(!active)return;
      if(discard)delete state.drafts[draftKey(active)];else stash();
      if(calendarCleanup){calendarCleanup();calendarCleanup=null;}
      const row=q('[data-inline-task="'+active.taskId+'"]');if(row){row.hidden=true;row.querySelector('[data-inline-slot]').innerHTML='';}
      root.querySelectorAll('.r-report-row.is-editing').forEach(el=>el.classList.remove('is-editing'));
      active=null;
      syncTriggers();
      if(focus){if(lastFocus&&lastFocus.isConnected)lastFocus.focus({preventScroll:true});else q('[data-add-current]').focus({preventScroll:true});}
    }
    function open(taskId,reportId,focus=true){
      const trigger=document.activeElement;
      close({focus:false});
      const t=getTask(taskId),r=reportFor(t,reportId);
      if(isOperationComplete(t)&&!r){state.status='该工序已全部完工';views.render();return;}
      const redraw=state.expanded!==taskId||!q('[data-inline-slot="'+taskId+'"]');
      state.selected=taskId;state.expanded=taskId;if(redraw)views.render();
      active={taskId,reportId:r?r.id:null,revision:r?r.revision:null};
      const draft=state.drafts[draftKey(active)];if(draft)active.revision=draft.revision;
      const title=r?(complete(r)?'更正报工':'补齐本次报工'):'本次报工';
      const content=formMarkup(t,r,draft&&draft.values);
      const slot=q('[data-inline-slot="'+taskId+'"]'),row=slot.closest('tr');
      const source=r?[...root.querySelectorAll('[data-report]')].find(el=>el.dataset.report===r.id):null;
      const anchor=source?(source.nextElementSibling&&source.nextElementSibling.classList.contains('r-report-meta-row')?source.nextElementSibling:source):q('[data-expand="'+taskId+'"]').closest('tr');
      anchor.insertAdjacentElement('afterend',row);row.hidden=false;
      lastFocus=trigger&&trigger.isConnected&&trigger.matches('button[data-add],button[data-edit],button[data-add-current]')?trigger:source?source.querySelector('[data-edit]'):q('[data-add="'+taskId+'"]')||q('[data-add-current]');
      slot.innerHTML='<div class="r-entry-heading"><h3 id="r-editor-title">'+title+'</h3><span class="r-caption">'+esc(t.batch)+' · '+esc(t.op)+(r?' · '+esc(r.reportNo):'')+'</span></div>'+content;
      if(source)source.classList.add('is-editing');
      icons();
      calendarCleanup=ns.mountCalendars(q('#r-report-form'),preview);if(draft&&q('.r-extra'))q('.r-extra').open=draft.extraOpen;preview();
      syncTriggers();
      if(focus){const target=source||slot;if(typeof target.scrollIntoView==='function')target.scrollIntoView({block:'nearest',inline:'nearest'});q('#r-qty-input').focus({preventScroll:true});}
    }
    function render(){
      const previous=active?{...active}:null;
      if(previous)close({focus:false});views.render();
      if(previous&&state.expanded===previous.taskId&&q('[data-inline-slot="'+previous.taskId+'"]'))open(previous.taskId,previous.reportId,false);
    }
    function toggle(taskId,reportId){
      if(matches(taskId,reportId)){close({focus:false});return false;}
      open(taskId,reportId);return Boolean(active);
    }
    function reasonNeeded(record,values){
      if(!record)return false;if(complete(record))return true;
      return ['qty','hours','start','end','machine','person'].some(key=>record[key]!==null&&record[key]!==''&&record[key]!==(['qty','hours'].includes(key)&&values[key]!==''?Number(values[key]):values[key]));
    }
    function preview(){
      if(!active)return;
      const v=formValues(),t=getTask(active.taskId),r=t.reports.find(x=>x.id===active.reportId),max=quantityLimit(t,active.reportId);
      const qty=v.qty===''?null:Number(v.qty),hours=v.hours===''?null:Number(v.hours),after=t.target-max+(qty===null?0:qty);
      q('#r-qty-input').max=String(max);q('[data-qty="max"]').title='填入本次最多可报数量：'+max+' 件';
      q('[data-qty="up"]').disabled=max===0||(qty!==null&&qty>=max);q('[data-qty="down"]').disabled=qty!==null&&qty<=0;
      q('[data-qty="min"]').disabled=qty===0;q('[data-qty="max"]').disabled=qty===max;
      q('#r-qty-preview').textContent='本次保存后 '+after+' / '+t.target+' 件 · 剩余 '+(t.target-after)+' 件';
      const span=v.start&&v.end?(ms(v.end)-ms(v.start))/3600000:null;
      q('#r-span-preview').textContent=span===null?'':!Number.isFinite(span)||span<=0?'请检查实际起止时间':'作业跨度 '+number(span)+' h'+(hours!==null?' · 工时差额 '+number(span-hours)+' h':'');
      if(r){const needed=reasonNeeded(r,v);q('[name="reason"]').required=needed;q('[data-reason-field]').hidden=!needed;q('.r-supplement-grid').classList.toggle('has-reason',needed);if(needed&&q('.r-extra'))q('.r-extra').open=true;}
      const resource=q('.r-extra-resource');if(resource)resource.textContent=v.machine+' / '+v.person;
    }
    function changeQuantity(action,focus=true){
      if(!active)return;
      const input=q('#r-qty-input'),max=quantityLimit(getTask(active.taskId),active.reportId),current=input.value===''?null:Number(input.value);
      const n=current===null||!Number.isFinite(current)?0:current;
      input.value=String(action==='max'?max:action==='min'?0:Math.max(0,Math.min(max,action==='up'?Math.floor(n)+1:Math.ceil(n)-1)));
      preview();if(focus)input.focus({preventScroll:true});
    }
    function error(text){q('#r-error').hidden=false;q('#r-error').textContent=text;}
    function finish(){
      close({discard:true,focus:false});views.render();
      const target=q('[data-expand="'+state.selected+'"]')||q('[data-add-current]');target.focus({preventScroll:true});
    }
    function save(){
      if(!active)return;
      const t=getTask(active.taskId);
      preview();const form=q('#r-report-form');if(!form.reportValidity())return;
      const v=formValues(),existing=t.reports.find(r=>r.id===active.reportId),qty=v.qty===''?null:Number(v.qty),hours=v.hours===''?null:Number(v.hours);
      if(existing&&existing.revision!==active.revision)return error('这条记录已被更新。请取消当前草稿，重新打开后核对。');
      const invalid=validateReport(t,{qty,hours,start:v.start,end:v.end,machine:v.machine,person:v.person},active.reportId,state.clock);
      if(invalid)return error(invalid);
      if(reasonNeeded(existing,v)&&!v.reason.trim())return error('请填写补录或更正原因。');
      state.clock+=60000;const time=new Date(state.clock).toISOString().slice(0,16);
      let identity=existing?{id:existing.id,reportNo:existing.reportNo}:null;
      while(!identity){const n=nextId++,id='r'+n,reportNo='BG-20260907-'+String(n).padStart(4,'0');if(!tasks.some(task=>task.reports.some(r=>r.id===id||r.reportNo===reportNo)))identity={id,reportNo};}
      const record={...identity,qty,start:v.start,end:v.end,hours,machine:v.machine,person:v.person,remark:v.remark.trim(),recorded:time,revision:existing?existing.revision+1:0};
      if(existing){corrections.push({time,taskId:t.id,batch:t.batch,previous:{...existing},next:{...record},text:(reasonNeeded(existing,v)?'报工更正：数量 '+(existing.qty===null?'待填':existing.qty)+' → '+(qty===null?'待填':qty)+' 件；'+v.reason.trim():'补齐本次报工记录')});t.reports[t.reports.indexOf(existing)]=record;}else t.reports.push(record);
      const action=existing&&complete(existing)?'更正已保存':'报工已保存';
      t.closed=isOperationComplete(t);state.filter='all';state.search='';q('#r-search').value='';state.expanded=t.id;state.selected=t.id;state.status=t.batch+' · '+action+(t.closed?'，本工序已完工':'')+'（示例）';finish();
    }
    function completeRest(){
      changeQuantity('max',false);const v=formValues();
      if(!v.start||!v.end||v.hours==='')return error('已填入本次最多可报数量。请补齐实际开工、完工和工时，再保存报工。');
      save();
    }
    return {open,toggle,close,render,preview,changeQuantity,completeRest,save,stash,get active(){return active;}};
  };
})();
