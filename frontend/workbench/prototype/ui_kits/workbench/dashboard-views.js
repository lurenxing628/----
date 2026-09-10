(function () {
 "use strict";
 window.APSDashboard.createViews = function (root,model) {
 const q=s=>root.querySelector(s);
 const {stamp,short,num,NOW,batchData,plans,actualRows,externalRows,pendingRows,stop,stopTasks,state,handling,recordLog,caseOrder,planRows,stats,overrunRows,gaps,awaiting,extLate,shortage,overlaps,caseInfo,items,entries,statuses,categoryProgress,destinations}=model;
 const esc=v=>String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const icon=n=>{
  const nodes=window.APSDashboard.iconNodes[n];
  if(!nodes)throw new Error('Unknown dashboard icon: '+n);
  return '<svg class="lucide" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+nodes.map(([tag,attrs])=>'<'+tag+' '+Object.entries(attrs).map(([key,value])=>key+'="'+esc(value)+'"').join(' ')+'></'+tag+'>').join('')+'</svg>';
 };
 const badge=(label,tone='neutral')=>'<span class="d-badge '+tone+'"><span class="d-dot"></span>'+esc(label)+'</span>';
 function icons(){
  root.querySelectorAll('[data-lucide]').forEach(el=>{el.outerHTML=icon(el.dataset.lucide);});
  root.querySelectorAll('[data-tooltip]').forEach(el=>{el.title=el.dataset.tooltip;});
 }
 function table(heads,rows){return '<div class="d-scroll wb-table-shell"><table class="d-table wb-table"><thead><tr>'+heads.map(h=>'<th scope="col">'+h+'</th>').join('')+'</tr></thead><tbody>'+rows.join('')+'</tbody></table></div>';}
 function tr(cells,cls=''){return '<tr'+(cls?' class="'+cls+'"':'')+'>'+cells.map(c=>'<td>'+c+'</td>').join('')+'</tr>';}
 function batchLink(r){return '<button class="d-batch" data-batch="'+r.id+'">'+r.id+'</button><span class="d-sub">'+esc(r.name)+'</span>';}
 function section(title,body,caption=''){return '<section class="d-section"><div class="d-section-head"><h3>'+title+'</h3>'+(caption?'<span class="d-caption">'+caption+'</span>':'')+'</div>'+body+'</section>';}
 function note(text){return '<div class="d-evidence-line">'+icon('info')+'<span>'+esc(text)+'</span></div>';}
 function axis(start,end){return '<div class="d-time-head">资源 / 时段</div><div class="d-time-axis">'+Array.from({length:5},(_,i)=>'<span class="d-tick" style="left:'+i*25+'%">'+String(start+(end-start)*i/4).padStart(2,'0')+':00</span>').join('')+'</div>';}
 function bar(start,end,label,cls='',attrs=''){
  const left=Math.max(0,Math.min(100,start)),right=Math.max(left,Math.min(100,end));
  if(right<=left)return '';
  const tag=attrs.includes('data-batch=')?'button':'span';
  return '<'+tag+(tag==='span'?' role="img"':'')+' class="d-timebar '+cls+'" style="left:'+left+'%;width:'+(right-left)+'%" '+attrs+'><span class="d-timebar-label">'+label+'</span></'+tag+'>';
 }
 function resourceTimeline(){
  const jobs=[{id:'B202609-018',start:8,end:11.5},{id:'B202609-024',start:11.5,end:14},{id:'B202609-021',start:14,end:15.68}];
  const bars=jobs.map(j=>bar((j.start-8)/8*100,(j.end-8)/8*100,j.id.slice(-3),'hot'+(state.selectedBatch===j.id?' focus':''),'data-batch="'+j.id+'" aria-label="查看 '+j.id+' 精加工排程" data-tooltip="'+j.id+' · 精加工 · '+num(j.end-j.start)+'h"')).join('');
  return '<div class="d-scroll"><div class="d-time-grid">'+axis(8,16)+'<div class="d-lane-label"><b>M-03</b><span class="d-sub">精加工 · 96%</span></div><div class="d-lane">'+bars+'</div><div class="d-lane-label"><b>M-08</b><span class="d-sub">同类精加工设备</span></div><div class="d-lane">'+bar(87.5,100,'其他','','data-tooltip="其他计划任务 · 15:00 至 16:00" aria-label="其他计划任务15点至16点"')+'</div></div></div>'+note('共同使用 M-03 是关联线索；空闲时段能否接活，还需校验人员、工艺和前后序。');
 }
 function deliveryPanel(){
  const s=stats(),rows=s.rows.filter(r=>r.delta>=0);
  const rowHtml=rows.map(r=>tr([batchLink(r),short(r.due),'<span class="d-num">'+short(r.finish)+'</span>',badge('晚 '+num(r.delta)+'h','red'),esc(r.priority)],state.selectedBatch===r.id?'selected':''));
  return '<div class="d-summary-line"><span><b class="d-danger">'+s.late+'</b> 批预计超期</span><span>最长 <b>'+num(s.worst)+'</b> h</span><span>总拖期 <b>'+num(s.total)+'</b> h</span></div>'+section('关联资源的关键时段',resourceTimeline(),'09-08 · 计划跨度')+section('影响批次',table(['批次 / 零件','交期','计划完工','交期偏差','优先级'],rowHtml),'按晚交小时排序')+'<div class="d-proposal"><div><h3>先比较“优先保护急件”方案</h3><p>2 批可恢复准时；普通批次 '+batchData[2].id.slice(-3)+' 的预计晚交会增加。</p></div><button class="d-button primary" data-view-compare>'+icon('git-compare-arrows')+'对比调整方案</button></div>';
 }
 function actualPanel(){
  const complete=actualRows.filter(r=>r.start&&r.end&&r.hours!==null),o=overrunRows();
  const rowHtml=actualRows.map(r=>{
   const delta=r.hours!==null?(r.hours/r.quota-1)*100:null;
   return tr(['<span class="d-num">'+r.batch+'</span><span class="d-sub">'+r.op+'</span>',num(r.quota)+'h',r.hours===null?'未回填':num(r.hours)+'h',delta===null?badge('待回填','neutral'):badge((delta>0?'+':'')+num(delta)+'%',delta>20?'amber':'green'),'<button class="d-link" data-edit-actual="'+r.id+'">'+icon('square-pen')+'回填</button>']);
  });
  const timeline=actualRows.slice(0,2).map(r=>{
   const h=s=>(stamp(s)-stamp('2026-09-07'))/3600000;
   return '<div class="d-lane-label"><b>'+r.batch.slice(-3)+'</b><span class="d-sub">'+r.op+'</span></div><div class="d-lane">'+bar((h(r.planStart)-6)/8*100,(h(r.planEnd)-6)/8*100,'','plan','aria-label="'+r.batch+' 计划时段" data-tooltip="计划 '+short(r.planStart)+' 至 '+short(r.planEnd)+'"')+(r.start&&r.end?bar((h(r.start)-6)/8*100,(h(r.end)-6)/8*100,'实际','actual','aria-label="'+r.batch+' 实际时段" data-tooltip="实际 '+short(r.start)+' 至 '+short(r.end)+'"'):'')+'</div>';
  }).join('');
  return '<div class="d-summary-line"><span>已回填 <b>'+complete.length+'/'+actualRows.length+'</b> 道</span><span>工时偏差 &gt;20% <b class="d-warn">'+o.length+'</b> 道</span></div>'+section('计划与实际时间对照','<div class="d-scroll"><div class="d-time-grid">'+axis(6,14)+timeline+'</div></div><div class="d-legend" aria-label="时间对照图例"><span><i class="d-key plan" aria-hidden="true"></i>计划</span><span><i class="d-key actual" aria-hidden="true"></i>人工回填实际</span></div>','09-07')+section('工序回填与工时偏差',table(['批次 / 工序','定额总工时','实际工时','偏差','记录'],rowHtml))+note('实际工时偏高是校准线索，不自动改定额；未填写的实际记录不当作零工时。');
 }
 function externalPanel(){
  const rows=externalRows.map(r=>{
   const delay=(!r.returned?Math.max(0,(NOW-stamp(r.planned))/3600000):0);
   return tr(['<span class="d-num">'+r.batch+'</span><span class="d-sub">'+r.op+' · '+r.supplier.split(' ')[0]+'</span>',short(r.planned),r.returned?short(r.returned):badge(r.state,delay?'amber':'blue'),r.returned?'已登记':delay?'超时 '+num(delay)+'h':'未到计划时点','<button class="d-link" data-edit-external="'+r.id+'">登记</button>']);
  });
  const first=externalRows.find(r=>!r.returned)||externalRows[0];
  return '<div class="d-summary-line"><span>待回厂 <b>'+awaiting().length+'</b> 项</span><span>超过计划时点 <b class="d-warn">'+extLate().length+'</b> 项</span><span>已回厂 <b class="d-good">'+externalRows.filter(r=>r.returned).length+'</b> 项</span></div>'+section('外协登记与回厂计划',table(['批次 / 外协工序','计划回厂','实际 / 状态','时间判断','操作'],rows))+section('当前跟踪依据','<dl class="d-fact-grid"><div><dt>供应商</dt><dd>'+esc(first.supplier)+'</dd></div><div><dt>发出时间</dt><dd>'+short(first.sent)+'</dd></div><div><dt>最近确认</dt><dd>'+short(first.confirmed)+'</dd></div><div><dt>录入状态</dt><dd>'+esc(first.state)+'</dd></div></dl>')+note('回厂时间录入后可作为后续排程的已知约束；后续工序是否延期，仍需结合剩余工序与可用资源重新测算。')+'<div class="d-proposal"><div><h3>保留计划与实际两个时间</h3><p>不使用供应商默认周期替代实际回厂记录。</p></div><button class="d-button primary" data-edit-external="'+first.id+'">'+icon('square-pen')+'登记回厂情况</button></div>';
 }
 function downtimePanel(){
  const rows=overlaps();
  const lane='<div class="d-scroll"><div class="d-time-grid">'+axis(8,16)+'<div class="d-lane-label"><b>M-05</b><span class="d-sub">检修与原计划</span></div><div class="d-lane"><span class="d-stop" style="left:0;width:50%"></span>'+bar(12.5,25,'018','hot','data-batch="B202609-018" aria-label="查看批次018原计划"')+bar(31.25,62.5,'024','hot','data-batch="B202609-024" aria-label="查看批次024原计划"')+'</div></div></div><div class="d-legend"><span class="d-danger">检修 08:00–12:00</span><span>任务条：原计划工序</span></div>';
  return '<div class="d-summary-line"><span>检修窗口 <b>4</b> h</span><span>重叠工序 <b class="d-warn">'+rows.length+'</b> 道</span><span>重叠合计 <b>'+num(rows.reduce((s,r)=>s+r.hours,0))+'</b> h</span></div>'+section('检修窗口与原计划',lane,'09-09 · 周三')+section('直接重叠的工序',table(['批次 / 工序','原计划开始','原计划结束','重叠时长'],rows.map(r=>tr(['<span class="d-num">'+r.batch+'</span><span class="d-sub">'+r.op+'</span>',short(r.start),short(r.end),badge(num(r.hours)+'h','amber')],state.selectedBatch===r.batch?'selected':''))))+note('2.5h 是时段交集，不是批次最终延期量。最终影响取决于后续空档、人员和工序依赖。')+section('登记依据','<dl class="d-fact-grid"><div><dt>设备</dt><dd>'+stop.resource+'</dd></div><div><dt>原因</dt><dd>'+stop.reason+'</dd></div><div><dt>开始 / 结束</dt><dd>09-09 08:00 / 12:00</dd></div><div><dt>登记时间</dt><dd>'+short(stop.recorded)+'</dd></div></dl>');
 }
 function materialPanel(){
  const s=shortage(),ready=pendingRows.length-s.length;
  return '<div class="d-summary-line"><span>待排 <b>'+pendingRows.length+'</b> 批</span><span>已齐套 <b class="d-good">'+ready+'</b> 批</span><span>尚未齐套 <b class="d-warn">'+s.length+'</b> 批</span></div>'+section('待排批次与齐套日期',table(['批次 / 零件','数量','交期','齐套状态','齐套日期'],pendingRows.map(r=>tr(['<span class="d-num">'+r.id+'</span><span class="d-sub">'+r.name+'</span>',r.qty,short(r.due),badge(r.ready,r.ready==='已齐套'?'green':'amber'),short(r.readyDate)]))))+section('本次排产约束','<dl class="d-fact-grid"><div><dt>齐套检查</dt><dd>开启</dd></div><div><dt>缺资源工序</dt><dd>按匹配规则自动分配</dd></div><div><dt>已开工工序</dt><dd>锁定原计划</dd></div><div><dt>当前范围</dt><dd>当前待排批次池</dd></div></dl>')+note('齐套信息来自批次录入。尚未齐套不是缺料数量；具体缺什么、何时可补齐，应回到物料与批次资料核实。');
 }
 function comparePanel(){
  if(!['delivery','candidate'].includes(state.caseId))return section('这条问题需要先更新输入','<p class="d-note">'+(state.caseId==='external'?'先确认外协实际回厂记录，再重排后续工序。':state.caseId==='actual'?'先复核实际工时与执行记录，再确定是否需要重排或校准定额。':state.caseId==='downtime'?'先按检修窗口避让原计划，再比较调整后的交期与资源指标。':'先确认齐套状态和日期，再比较可执行的排产方案。')+'</p>')+note('当前没有这条问题的独立候选结果，不借用其他问题的方案冒充。')+'<button class="d-button" data-nav-case="candidate">'+icon('git-compare-arrows')+'查看现有候选方案</button>';
  const base=stats('base'),chosen=stats(state.plan),plan=plans[state.plan];
  const opts=Object.keys(plans).map(id=>{const s=stats(id);return '<label class="d-option"><span class="d-option-top"><input type="radio" name="d-plan-choice" value="'+id+'"'+(state.plan===id?' checked':'')+'>'+plans[id].name+'</span><p>'+plans[id].subtitle+'</p><span class="d-choice-value">'+s.late+' <span class="d-unit">批晚交</span></span></label>';}).join('');
  const comparisons=[['超期批次',base.late,chosen.late,'批'],['总拖期',base.total,chosen.total,'h'],['换型次数',plans.base.switches,plan.switches,'次'],['M-03 峰值负荷',plans.base.peak03,plan.peak03,'%'],['M-08 峰值负荷',plans.base.peak08,plan.peak08,'%']];
  const rows=comparisons.map(([label,b,c,unit])=>{const diff=c-b;return tr([label,'<span class="d-num">'+num(b)+unit+'</span>','<span class="d-num">'+num(c)+unit+'</span>','<span class="'+(diff<0?'d-good':diff>0?'d-warn':'d-muted')+' d-num">'+(diff===0?'持平':(diff>0?'+':'')+num(diff)+unit)+'</span>']);});
  const batches=chosen.rows.slice(0,3).map((r,i)=>{const old=base.rows[i],gain=Math.max(0,old.delta)-Math.max(0,r.delta);return tr([batchLink(r),old.delta>=0?'晚 '+num(old.delta)+'h':'准时',r.delta>=0?badge('晚 '+num(r.delta)+'h','amber'):badge('准时','green'),'<span class="'+(gain>=0?'d-good':'d-warn')+'">'+(gain>=0?'减少 ':'增加 ')+num(Math.abs(gain))+'h</span>'],state.selectedBatch===r.id?'selected':'');});
  const reason=state.plan==='balanced'?'两批急件恢复准时；普通批次 021 晚交增加 3h，同时换型增加 2 次、M-08 峰值负荷上升。':state.plan==='total'?'总拖期降低到 8h，但特急批次 018 仍晚交；换型增加 6 次。不能只看总量就替用户决定。':'当前方案作为比较基准，不做任何调整。';
  return section('同一批次范围下比较','<div class="d-compare-options">'+opts+'</div>','预置候选结果示例')+section('整体收益与代价',table(['指标','当前方案','所选方案','变化'],rows))+section('逐批交期变化',table(['批次 / 零件','当前','所选','晚交变化'],batches))+'<div class="d-proposal"><div><h3>'+plan.name+'</h3><p>'+reason+'</p></div><button class="d-button primary" data-preview-plan>'+icon('chart-gantt')+'查看方案摘要</button></div>'+note(state.revision?'人工录入已经变化；这份候选快照未重新计算。':'以上为预置候选结果，不是本页面实时调用排产算法生成的结果。');
 }
 function sourceRows(){
  const common=[['批次资料','批次管理','数量、交期、优先级'],['工序与资源','基础资料 / 批次工序','工艺顺序、工时、资源匹配']];
  if(state.caseId==='actual')return [['计划起止','采用方案 v15','计划开工、计划完工'],['实际起止 / 工时','现场记录 · 人工回填','实际开工、实际完工、工时'],['偏差','系统对比','实际值与计划 / 定额之差']];
  if(state.caseId==='external')return [['外协承接与周期','基础资料 / 批次工序','供应商、工种、外协周期'],['实际回厂 / 确认状态','外协登记 · 人工填写','本样板包含的未来录入项'],['后续交期影响','剩余工序重新排程','未重排时不自动下结论']];
  if(state.caseId==='downtime')return [['检修开始 / 结束','设备停机登记','本样板包含的未来录入项'],['原计划工序时段','采用方案 v15','批次、设备、工序起止'],['直接重叠','时段交集计算','去重工序数与重叠小时']];
  if(state.caseId==='material')return [['批次齐套状态 / 日期','批次管理 · 人工填写','已齐套 / 部分齐套 / 未齐套'],['齐套检查开关','执行排产','决定是否作为本次排产门槛'],['具体物料缺口','物料明细','不能从批次状态推导缺料数量']];
  return common.concat([['计划完工与指标','方案排程结果','本样板使用预置结果'],['候选收益与代价','同范围方案对比','按批次明细与方案指标计算']]);
 }
 const statusTone=value=>value==='已关闭'?'green':value==='待验证'?'amber':value==='跟进中'?'blue':'amber';
 function itemActions(r){
  const h=handling[r.id];
  return '<div class="d-item-actions"><button class="d-link" data-handle-item="'+r.id+'">'+icon('square-pen')+(h.status==='已关闭'?'查看处置':'处置')+'</button><button class="d-link" data-item-history="'+r.id+'">历史 '+recordLog[r.id].length+'</button></div>';
 }
 function itemPanel(){
  const list=items(),count=categoryProgress(state.caseId);
  const filters='<div class="d-item-toolbar"><label>状态<select name="d-status-filter">'+[['all','全部状态'],['open','未关闭'],...statuses.map(s=>[s,s])].map(([id,label])=>'<option value="'+id+'"'+(state.filter===id?' selected':'')+'>'+label+'</option>').join('')+'</select></label><label class="d-item-search">查找<input name="d-item-search" type="search" value="'+esc(state.search)+'" placeholder="批次、责任人、处置动作" /></label><span class="d-caption" id="d-filter-count" aria-live="polite">显示 '+list.length+' / '+count.total+' 条</span></div>';
  const rows=list.map(r=>{
   const h=handling[r.id],overdue=h.status!=='已关闭'&&h.deadline&&stamp(h.deadline)+86400000<=state.clock;
   return '<tr data-item="'+r.id+'"'+(r.id===state.selectedItem?' class="selected"':'')+'><td><strong>'+esc(r.subject)+'</strong><span class="d-sub">发现时：'+esc(r.detail)+'</span></td><td>'+esc(h.owner||'未认领')+'<span class="d-sub'+(overdue?' d-danger':'')+'">'+esc(h.deadline||'期限未填')+(overdue?' · 处置逾期':'')+'</span></td><td>'+esc(h.action||'尚未安排')+'<span class="d-sub">'+esc(h.remark||'无证据备注')+'</span></td><td>'+badge(h.status,statusTone(h.status))+'</td><td>'+itemActions(r)+'</td></tr>';
  });
  return filters+(rows.length?'<div class="d-item-table">'+table(['异常 / 依据','责任人 / 期限','处置动作 / 证据备注','处置状态','操作'],rows)+'</div>':'<div class="d-empty" role="status">当前筛选没有匹配条目。<button class="d-link" data-clear-filter>清除筛选</button></div>')+note('当前类别 '+count.closed+' / '+count.total+' 条人工关闭；上方风险指标仍取原始样例数据，关闭不等于风险消失。');
 }
 function detailLinks(r){return destinations[r.category].map(([page,label])=>'<button type="button" class="d-button" data-item-nav="'+r.id+'" data-page="'+page+'">'+icon('chart-gantt')+label+'概览</button>').join('');}
 const historyLabels={status:'处置状态',owner:'责任人',deadline:'期限',action:'处置动作',remark:'证据备注',completedAt:'完成时间',completionEvidence:'具体完成结果',evidenceRef:'可核对凭据',start:'实际开工',end:'实际完工',hours:'实际工时',sent:'发出时间',planned:'计划回厂',returned:'实际回厂',state:'回厂状态',confirmed:'确认时间'};
 function historyRecord(r){
  const keys=[...new Set([...Object.keys(r.before),...Object.keys(r.after)])].filter(key=>r.before[key]!==r.after[key]);
  const changes=keys.map(key=>tr([esc(historyLabels[key]||key),esc(r.before[key]===null?'未填':r.before[key]||'未填'),esc(r.after[key]===null?'未填':r.after[key]||'未填')]));
  return '<article class="d-record"><div><b>#'+r.sequence+'</b><time>'+r.time.replace('T',' ')+'</time></div><div><strong>'+esc(r.action)+'</strong><p class="d-sub">'+esc(r.remark)+'</p><details class="d-history-change"><summary>核对变更前后</summary>'+table(['字段','变更前','变更后'],changes)+'</details><span class="d-sub">'+esc(r.source)+' · '+esc(r.provenance.label)+' · 示例时间</span></div></article>';
 }
 function recordsPanel(){
  const list=entries.filter(r=>r.category===state.caseId),selected=list.find(r=>r.id===state.selectedItem)||list[0];
  state.selectedItem=selected.id;
  const h=handling[selected.id],log=recordLog[selected.id];
  return '<label class="d-history-picker">历史条目<select name="d-history-item">'+list.map(r=>'<option value="'+r.id+'"'+(r.id===selected.id?' selected':'')+'>'+esc(r.subject)+'</option>').join('')+'</select></label>'+section(esc(selected.subject),'<div class="d-actions">'+badge(h.status,statusTone(h.status))+itemActions(selected)+'</div>'+(log.length?log.slice().reverse().map(historyRecord).join(''):'<p class="d-note">该条目尚无处置或输入变更记录。</p>'),'共 '+log.length+' 条记录')+section('数据来源',note(selected.source+' · '+model.provenance.label+' · 快照 '+model.provenance.snapshot.replace('T',' '))+table(['数据','来源页面','口径'],sourceRows().map(r=>tr(r.map(esc)))))+note('历史只核对本次会话的人工声明与输入变更，不代表凭据已核验或生产计划已修改。');
 }
 function render(){
  const info=caseInfo(state.caseId),s=stats();
  const pressureCount=[plans.base.peak03,plans.base.peak08].filter(value=>value>=90).length;
  const metrics=[['交期风险',s.late,'批','delivery','d-danger'],['资源压力',pressureCount,'台','delivery','d-warn'],['外协待回厂',awaiting().length,'项','external',''],['现场待回填',gaps().length,'道','actual',''],['待排批次',pendingRows.length,'批','material','']];
  q('#d-metrics').innerHTML=metrics.map(([label,value,unit,id,tone])=>'<button class="d-metric wb-metric" data-tone="'+(tone==='d-danger'?'danger':tone==='d-warn'?'warning':'neutral')+'" data-case="'+id+'"><span class="d-metric-label wb-metric-label">'+label+'</span><span class="d-metric-line wb-metric-line"><strong class="d-metric-value wb-metric-value '+tone+'">'+value+'</strong><span class="d-unit wb-metric-unit">'+unit+'</span></span></button>').join('');
  q('#d-cases').innerHTML=caseOrder.map(id=>{const c=caseInfo(id),p=categoryProgress(id);return '<button class="d-case" data-case="'+id+'" aria-pressed="'+(state.caseId===id)+'"><span class="d-case-top"><span class="d-case-marker '+(c.tone==='red'?'d-danger':c.tone==='amber'?'d-warn':'d-muted')+'">'+icon(c.icon)+c.kind+'</span><span>'+p.total+' 条</span></span><span class="d-case-bottom"><span>'+c.state+'</span><span>'+c.impact+'</span></span></button>';}).join('');
  q('[name="d-category"]').innerHTML=caseOrder.map(id=>'<option value="'+id+'"'+(state.caseId===id?' selected':'')+'>'+caseInfo(id).kind+' · '+categoryProgress(id).total+' 条</option>').join('');
  q('#d-detail-head').innerHTML='<div class="d-case-meta"><span class="d-actions">'+badge(info.kind,info.tone)+'<span class="d-caption">'+info.source+'</span></span><span class="d-caption">'+info.state+'</span></div><h2 id="d-detail-title">'+info.detail+'</h2>'+(state.tab==='items'?'':'<p class="d-lead">'+info.lead+'</p>');
  root.querySelectorAll('[data-tab]').forEach(el=>{const active=el.dataset.tab===state.tab;el.setAttribute('aria-selected',String(active));el.tabIndex=active?0:-1;});
  q('#d-content').setAttribute('aria-labelledby','d-tab-'+state.tab);
  const builders={delivery:deliveryPanel,actual:actualPanel,external:externalPanel,downtime:downtimePanel,material:materialPanel,candidate:comparePanel};
  q('#d-content').innerHTML=state.tab==='items'?itemPanel():state.tab==='records'?recordsPanel():state.tab==='compare'?comparePanel():builders[state.caseId]();
  q('#d-input-changed').hidden=state.revision===0;
  q('#d-input-time').textContent=new Date(state.inputTime).toISOString().slice(11,16);
  const context=window.APSDashboard.planContext;
  q('#d-plan-label').textContent='样例采用方案 v'+context.version;
  q('#d-plan-generated').textContent=context.generated;
  q('#d-plan-range').textContent=context.range;
  q('#d-status').textContent=state.status;
  root.querySelectorAll('.d-option').forEach(el=>el.classList.toggle('selected',el.querySelector('input').checked));
  icons();
 }
 return {render,icons,esc,icon,badge,note,detailLinks,statusTone};
 };
})();
