(function () {
 "use strict";
 const ns=window.APSFieldReports;
 ns.createViews=function(root){
const q=s=>root.querySelector(s);
const {ms,fmt,number,labels,tasks,state,corrections,summary}=ns.model;
const esc=v=>String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon=n=>'<i data-lucide="'+n+'" aria-hidden="true"></i>';
const badge=status=>'<span class="r-badge '+status+'"><span class="r-dot"></span>'+labels[status]+'</span>';
function filtered(){return tasks.filter(t=>(state.filter==='all'||summary(t).status===state.filter)&&(!state.search||(t.batch+t.name+t.op+t.machine+t.person+t.reports.map(r=>r.reportNo+r.machine+r.person).join('')).toLowerCase().includes(state.search.toLowerCase())));}
function icons(){ns.paintIcons(root);root.querySelectorAll('[data-tooltip]').forEach(el=>el.title=el.dataset.tooltip);}
function endCell(t,s){
  if(s.end){const d=(ms(s.end)-ms(t.planEnd))/60000;return '<span class="r-time">'+fmt(s.end)+'</span><span class="r-sub '+(d>0?'r-amber':'r-green')+'">'+(d>0?'晚 '+number(d)+' 分钟':d<0?'提前 '+number(-d)+' 分钟':'按时完工')+'</span>';}
  const last=s.latest?s.reports.find(r=>r.end===s.latest):null;
  return '<span class="r-caption">'+(s.status==='none'?'待记录':'未全部完工')+'</span>'+(last?'<span class="r-sub">'+(last.qty>0?'最近 '+last.qty+' 件完工':'最近作业结束')+'</span><span class="r-sub r-time">'+fmt(s.latest)+'</span>':'');
 }
function timeline(t){
  const s=summary(t),dates=[t.planStart,t.planEnd,...s.reports.flatMap(r=>[r.start,...(r.end?[r.end]:[])])];
  const lo=Math.min(...dates.map(ms))-1800000,hi=Math.max(...dates.map(ms))+1800000,span=hi-lo;
  const ticks=Array.from({length:5},(_,i)=>{const time=new Date(lo+span*i/4).toISOString().slice(0,16);return '<span class="r-tick" style="left:'+i*25+'%">'+fmt(time)+'</span>';}).join('');
  const bar=(start,end,label,plan)=>end?'<span class="r-bar'+(plan?' plan':'')+'" style="left:'+((ms(start)-lo)/span*100)+'%;width:'+((ms(end)-ms(start))/span*100)+'%" data-tooltip="'+esc((plan?'计划':label)+' · '+fmt(start)+' 至 '+fmt(end))+'" role="img" aria-label="'+esc((plan?'计划':label)+'，'+fmt(start)+' 至 '+fmt(end))+'">'+(plan?'':'<span class="r-bar-label">'+esc(label)+'</span>')+'</span>':'<span class="r-start-marker" style="left:'+((ms(start)-lo)/span*100)+'%" role="img" aria-label="实际开工 '+fmt(start)+'，完工待填" title="实际开工 '+fmt(start)+'，完工待填"></span><span class="r-pending-end">完工待填</span>';
  return '<div class="r-timeline"><div class="r-caption">时间对照</div><div class="r-axis">'+ticks+'</div><div class="r-lane-label">整道工序计划</div><div class="r-lane">'+bar(t.planStart,t.planEnd,'',true)+'</div>'+s.reports.map((r,i)=>'<div class="r-lane-label">第 '+(i+1)+' 次实际'+(r.qty===null?'':' · '+r.qty+' 件')+'</div><div class="r-lane">'+bar(r.start,r.end,r.qty===null?'实际':r.qty+' 件',false)+'</div>').join('')+'</div><div class="r-legend" aria-label="时间对照图例"><span><i class="r-key plan" aria-hidden="true"></i>计划</span><span><i class="r-key actual" aria-hidden="true"></i>实际报工</span></div>';
 }
function detail(t){
  const s=summary(t);
  const rows=s.reports.map((r,i)=>{
    const info=Boolean(state.reportInfo[r.id]),finished=Boolean(r.end&&r.qty!==null&&r.hours!==null);
    return '<tr class="r-report-row" data-report="'+esc(r.id)+'"><td><span class="r-branch" aria-hidden="true"></span></td>'+
      '<td><span class="r-report-label">第 '+(i+1)+' 次报工</span><span class="r-sub">'+esc(r.machine)+' / '+esc(r.person)+'</span></td>'+
      '<td><b class="r-num">'+(r.qty===null?'待填':r.qty+' 件')+'</b><span class="r-sub">本次完成</span></td><td class="r-caption">-</td>'+
      '<td class="r-time">'+fmt(r.start)+'</td><td><span class="r-time">'+(r.end?fmt(r.end):'待补完工')+'</span><span class="r-sub">本次作业</span></td>'+
      '<td class="r-num">'+(r.hours===null?'待填':number(r.hours)+' h')+'</td><td><span class="r-report-status '+(finished?'r-green':'r-amber')+'">'+(finished?'本次已结束':'记录待补全')+'</span></td>'+
      '<td><span class="r-row-actions"><button class="r-icon" data-edit="'+esc(r.id)+'" data-task="'+t.id+'" aria-expanded="false" aria-controls="r-inline-'+t.id+'" aria-label="补录或更正第'+(i+1)+'次报工" data-tooltip="补录 / 更正">'+icon('square-pen')+'</button>'+
      '<button class="r-icon" data-report-info="'+esc(r.id)+'" aria-expanded="'+info+'" aria-controls="r-info-'+esc(r.id)+'" aria-label="第'+(i+1)+'次报工备注与录入时间" data-tooltip="备注与录入时间">'+icon(info?'chevron-down':'chevron-right')+'</button></span></td></tr>'+
      (info?'<tr class="r-report-meta-row"><td colspan="9"><dl class="r-record-meta" id="r-info-'+esc(r.id)+'" aria-label="报工记录信息">'+
        '<div class="r-record-field"><dt>报工编号</dt><dd>'+esc(r.reportNo)+'</dd></div>'+
        '<div class="r-record-field"><dt>录入 / 修改时间</dt><dd>'+fmt(r.recorded)+'</dd></div>'+
        '<div class="r-record-field"><dt>修订次数</dt><dd>'+r.revision+' 次</dd></div>'+
        '<div class="r-record-field r-record-note"><dt>作业备注</dt><dd>'+esc(r.remark||'未填写')+'</dd></div></dl></td></tr>':'');
  }).join('');
  const audit=corrections.filter(c=>c.taskId===t.id||s.reports.some(r=>r.reportNo===(c.previous&&c.previous.reportNo)));
  const facts=r=>r?[(r.qty===null?'待填':r.qty)+' 件',fmt(r.start),(fmt(r.end)||'完工待填'),(r.hours===null?'工时待填':number(r.hours)+' h'),r.machine+' / '+r.person].map(esc).join(' · '):'';
  const history=audit.length?'<details class="r-history"><summary>修订记录 · '+audit.length+' 条</summary>'+audit.slice().reverse().map(c=>'<div class="r-audit"><time>'+fmt(c.time)+'</time> · '+esc(c.text)+(c.previous?'<div class="r-sub">修改前：'+facts(c.previous)+'</div><div class="r-sub">修改后：'+facts(c.next)+'</div>':'')+'</div>').join('')+'</details>':'';
  return rows+'<tr class="r-report-footer"><td colspan="9"><div class="r-record-tools"><span class="r-caption">'+(s.reports.length?'共 '+s.reports.length+' 次报工':'暂无报工记录')+'</span><button class="r-link-action" data-timeline="'+t.id+'" aria-expanded="'+Boolean(state.timelines[t.id])+'" aria-controls="r-timeline-'+t.id+'">'+icon('chart-gantt')+(state.timelines[t.id]?'收起时间对照':'时间对照')+'</button></div>'+history+'<div id="r-timeline-'+t.id+'"'+(state.timelines[t.id]?'':' hidden')+'>'+(state.timelines[t.id]?timeline(t):'')+'</div></td></tr>';
}
function operationTable(list){
  if(!list.length)return '<div class="r-empty">没有符合条件的工序</div>';
  const rows=list.map(t=>{
    const s=summary(t),expanded=state.expanded===t.id;
    const action=s.status==='done'?'<span class="r-caption r-complete">'+icon('check')+'</span>':'<button class="r-icon" data-add="'+t.id+'" aria-expanded="false" aria-controls="r-inline-'+t.id+'" aria-label="填写'+t.batch+'报工" data-tooltip="行内报工">'+icon('square-pen')+'</button>';
    return '<tr class="r-task'+(expanded?' selected':'')+'"><td><button class="r-icon" data-expand="'+t.id+'" aria-label="'+(expanded?'收起':'展开')+t.batch+'报工记录" aria-expanded="'+expanded+'">'+icon(expanded?'chevron-down':'chevron-right')+'</button></td>'+
      '<td><button class="r-code" data-expand="'+t.id+'">'+t.batch+'</button><span class="r-sub">'+esc(t.op)+' · '+esc(t.name)+'</span><span class="r-sub">'+t.machine+' / '+t.person+'</span></td>'+
      '<td><span class="r-qty">'+s.qty+' / '+t.target+'</span> <span class="r-caption">件</span><div class="r-track" role="progressbar" aria-label="工序数量完成率" aria-valuenow="'+Math.round(s.qty/t.target*100)+'" aria-valuemin="0" aria-valuemax="100"><span style="width:'+s.qty/t.target*100+'%"></span></div><span class="r-sub">剩余 '+s.remaining+' 件</span></td>'+
      '<td><span class="r-time">'+fmt(t.planStart)+'</span><span class="r-sub r-time">'+fmt(t.planEnd)+'</span></td><td class="r-time">'+(s.start?fmt(s.start):'<span class="r-caption">待记录</span>')+'</td><td>'+endCell(t,s)+'</td>'+
      '<td class="r-num">'+(s.reports.some(r=>r.hours!==null)?number(s.hours)+' h':s.reports.length?'待填':'-')+'</td><td>'+badge(s.status)+(s.incomplete?'<span class="r-sub r-amber">记录待补全</span>':'')+'</td><td>'+action+'</td></tr>'+
      '<tr class="r-entry-row" data-inline-task="'+t.id+'" hidden><td colspan="9"><div class="r-inline-editor" id="r-inline-'+t.id+'" data-inline-slot="'+t.id+'" role="region" aria-label="'+t.batch+'行内报工"></div></td></tr>'+(expanded?detail(t):'');
  }).join('');
  return '<div class="r-scroll"><table class="r-table"><thead><tr><th></th><th>批次 / 工序</th><th>累计 / 应做</th><th>计划开工 / 完工</th><th>实际开工</th><th>实际完工<span class="r-sub">整道工序</span></th><th>累计工时</th><th>完成情况</th><th class="r-report-column" scope="col">报工</th></tr></thead><tbody>'+rows+'</tbody></table></div>';
}
function render(){
  const summaries=tasks.map(summary),count=s=>summaries.filter(x=>x.status===s).length;
  q('#r-kpis').innerHTML=[['待报工',count('none'),'道','r-amber'],['已登记开工',count('started'),'道','r-blue'],['部分完成',count('partial'),'道','r-amber'],['已完工',count('done'),'道','r-green'],['累计实报工时',number(summaries.reduce((n,s)=>n+s.hours,0)),'h','']].map(([label,value,unit,tone])=>'<div class="r-kpi wb-metric" data-tone="'+(tone==='r-blue'?'notice':tone==='r-amber'?'warning':tone==='r-green'?'success':'neutral')+'"><div class="r-kpi-label wb-metric-label">'+label+'</div><div class="r-kpi-number wb-metric-value '+tone+'">'+value+'<small class="wb-metric-unit">'+unit+'</small></div></div>').join('');
  q('#r-filters').innerHTML=[['all','全部',tasks.length],['none','待报工',count('none')],['partial','部分完成',count('partial')],['started','已开工',count('started')],['done','已完工',count('done')]].map(([id,label,n])=>'<button class="r-filter" data-filter="'+id+'" aria-pressed="'+(id===state.filter)+'">'+label+'<span class="r-count">'+n+'</span></button>').join('');
  const incomplete=summaries.reduce((n,s)=>n+s.incomplete,0);q('#r-incomplete').innerHTML=incomplete?icon('circle-alert')+incomplete+' 条报工记录待补全':'';
  const list=filtered();q('#r-view').innerHTML=operationTable(list);
  q('[data-export-reports]').disabled=!list.length;
  q('#r-clock').textContent=fmt(new Date(state.clock).toISOString().slice(0,16));q('#r-row-count').textContent='当前 '+list.length+' 道工序';q('#r-save-status').textContent=state.status;icons();
 }
return {esc,icon,filtered,icons,render};
 };
})();
