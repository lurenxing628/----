(function () {
 "use strict";
 window.APSDashboard = {};
 window.APSDashboard.planContext = Object.freeze({version:15,generated:'09-07 08:40',range:'09-07 至 09-14'});
 window.APSDashboard.createModel = function () {
 const stamp=s=>Date.parse(s.length===10?s+'T00:00:00Z':s+'Z');
 const short=s=>s?s.slice(5,16).replace('T',' '):'未填写';
 const num=n=>Number.isInteger(n)?String(n):n.toFixed(1);
 const NOW=stamp('2026-09-07T11:40:00');
 const batchData=[
  {id:'B202609-018',name:'回转壳体 A',part:'T-1008',qty:12,due:'2026-09-08',priority:'特急',resource:'M-03'},
  {id:'B202609-024',name:'端盖 C',part:'T-1011',qty:4,due:'2026-09-09',priority:'急件',resource:'M-03'},
  {id:'B202609-021',name:'回转壳体 B',part:'T-1009',qty:8,due:'2026-09-10',priority:'普通',resource:'M-03'},
  {id:'B202609-019',name:'轴套 F',part:'T-1006',qty:6,due:'2026-09-12',priority:'普通',resource:'M-12'},
  {id:'B202609-022',name:'连接板 G',part:'T-1015',qty:10,due:'2026-09-13',priority:'普通',resource:'M-05'}
 ];
 const plans={
  base:{name:'当前采用方案',subtitle:'保留当前工序安排',switches:10,moves:0,finishes:['2026-09-09T14:00','2026-09-10T10:00','2026-09-11T09:00','2026-09-12T16:00','2026-09-12T15:00'],peak03:96,peak08:80},
  balanced:{name:'优先保护急件',subtitle:'调整 2 道精加工工序',switches:12,moves:2,finishes:['2026-09-08T17:00','2026-09-09T16:00','2026-09-11T12:00','2026-09-12T16:00','2026-09-12T15:00'],peak03:90,peak08:87.5},
  total:{name:'总拖期优先',subtitle:'重排精加工顺序',switches:16,moves:0,finishes:['2026-09-09T08:00','2026-09-09T16:00','2026-09-10T16:00','2026-09-12T16:00','2026-09-12T15:00'],peak03:96,peak08:80}
 };
 const actualRows=[
  {id:'a1',batch:'B202609-018',name:'回转壳体 A',op:'20 粗铣',resource:'M-05',planStart:'2026-09-07T08:00',planEnd:'2026-09-07T10:00',quota:2,start:'2026-09-07T08:10',end:'2026-09-07T11:10',hours:3},
  {id:'a2',batch:'B202609-019',name:'轴套 F',op:'40 组装',resource:'M-07',planStart:'2026-09-07T06:30',planEnd:'2026-09-07T08:30',quota:2,start:'2026-09-07T06:40',end:'2026-09-07T09:40',hours:3},
  {id:'a3',batch:'B202609-024',name:'端盖 C',op:'10 下料',resource:'M-18',planStart:'2026-09-07T08:00',planEnd:'2026-09-07T09:00',quota:1,start:'',end:'',hours:null},
  {id:'a4',batch:'B202609-021',name:'回转壳体 B',op:'10 下料',resource:'M-18',planStart:'2026-09-07T09:30',planEnd:'2026-09-07T10:30',quota:1,start:'',end:'',hours:null}
 ];
 const externalRows=[
  {id:'e1',batch:'B202609-022',name:'连接板 G',supplier:'S-02 金鼎热处理',op:'热处理',sent:'2026-09-04T09:00',planned:'2026-09-07T09:00',returned:'',state:'在途',confirmed:'2026-09-07T11:20'},
  {id:'e2',batch:'B202609-026',name:'承压盘 D',supplier:'S-01 华表面处理',op:'电镀',sent:'2026-09-05T16:00',planned:'2026-09-07T16:00',returned:'',state:'在途',confirmed:'2026-09-07T10:50'},
  {id:'e3',batch:'B202609-019',name:'轴套 F',supplier:'S-02 金鼎热处理',op:'热处理',sent:'2026-09-03T10:00',planned:'2026-09-06T10:00',returned:'2026-09-06T09:30',state:'已回厂',confirmed:'2026-09-06T09:40'}
 ];
 const pendingRows=[
  {id:'B202609-042',name:'输出轴',qty:25,due:'2026-09-10',ready:'部分齐套',readyDate:'2026-09-08'},
  {id:'B202609-044',name:'定位环',qty:80,due:'2026-09-12',ready:'已齐套',readyDate:'2026-09-07'},
  {id:'B202609-047',name:'支撑座',qty:50,due:'2026-09-14',ready:'未齐套',readyDate:'2026-09-09'}
 ];
 const stop={resource:'M-05',start:'2026-09-09T08:00',end:'2026-09-09T12:00',reason:'计划检修',recorded:'2026-09-07T09:20'};
 const stopTasks=[{batch:'B202609-018',name:'回转壳体 A',op:'40 精铣',start:'2026-09-09T09:00',end:'2026-09-09T10:00'},{batch:'B202609-024',name:'端盖 C',op:'40 精铣',start:'2026-09-09T10:30',end:'2026-09-09T13:00'}];
 // Candidate arrays are declared result fixtures, not output from a live scheduling engine.
 const provenance=Object.freeze({id:'dashboard-september',label:'值班台 9 月独立样例',snapshot:'2026-09-07T11:40',planVersion:15});
 const state={caseId:'delivery',tab:'items',plan:'balanced',selectedBatch:'B202609-018',selectedItem:'',filter:'all',search:'',drafts:{},revision:0,clock:NOW,inputTime:NOW,status:'示例会话 · 未连接生产数据库'};
 const handling={};
 const recordLog={};
 const caseOrder=['delivery','actual','external','downtime','material','candidate'];
 const statuses=['待分析','跟进中','待验证','已关闭'];
 const entries=[];
 function addEntry(category,key,subject,detail,source,rowId){
  const id=provenance.id+':'+category+':'+key;
  entries.push(Object.freeze({id,category,subject,detail,source,rowId:rowId||key,provenance}));
  handling[id]={status:'待分析',owner:'',deadline:'',action:'',remark:'',completedAt:'',completionEvidence:'',evidenceRef:''};
  recordLog[id]=[];
 }
 function planRows(id='base') {return batchData.map((r,i)=>({...r,finish:plans[id].finishes[i],delta:(stamp(plans[id].finishes[i])-(stamp(r.due)+86400000))/3600000}));}
 function stats(id='base') {const rows=planRows(id),late=rows.filter(r=>r.delta>=0);return {late:late.length,total:late.reduce((s,r)=>s+Math.max(0,r.delta),0),worst:Math.max(0,...late.map(r=>r.delta)),rows};}
 function overrunRows(){return actualRows.filter(r=>r.hours!==null&&r.quota>0&&r.hours/r.quota>1.2);}
 function gaps(){return actualRows.filter(r=>stamp(r.planStart)<=NOW&&!r.start);}
 function awaiting(){return externalRows.filter(r=>!r.returned);}
 function extLate(){return awaiting().filter(r=>stamp(r.planned)<NOW);}
 function shortage(){return pendingRows.filter(r=>r.ready!=='已齐套');}
 function overlaps(){return stopTasks.map(r=>({...r,hours:Math.max(0,Math.min(stamp(r.end),stamp(stop.end))-Math.max(stamp(r.start),stamp(stop.start)))/3600000})).filter(r=>r.hours>0);}
 planRows().filter(r=>r.delta>=0).forEach(r=>addEntry('delivery',r.id,r.id+' · '+r.name,'预计晚 '+num(r.delta)+'h；交期 '+r.due,'v15 预置排程测算'));
 actualRows.forEach(r=>addEntry('actual',r.id,r.batch+' · '+r.op,r.hours===null?'计划已到，实际记录待回填':'实际 '+num(r.hours)+'h / 定额 '+num(r.quota)+'h','9 月人工回填样例'));
 awaiting().forEach(r=>addEntry('external',r.id,r.batch+' · '+r.op,r.supplier+'；计划回厂 '+short(r.planned),'9 月外协登记样例'));
 overlaps().forEach(r=>addEntry('downtime',r.batch,r.batch+' · '+r.op,stop.resource+' 检修重叠 '+num(r.hours)+'h','9 月检修窗口 + 原计划交集'));
 shortage().forEach(r=>addEntry('material',r.id,r.id+' · '+r.name,r.ready+'；预计齐套 '+r.readyDate,'9 月待排批次池'));
 ['balanced','total'].forEach(id=>addEntry('candidate',id,plans[id].name,plans[id].subtitle+'；预计晚交 '+stats(id).late+' 批','9 月预置候选；非实时算法结果'));
 state.selectedItem=entries[0].id;
 function entry(id){const r=entries.find(x=>x.id===id);if(!r)throw new Error('未找到这条值班台异常，未执行操作。');return r;}
 function items(category=state.caseId,filter=state.filter,search=state.search){
  const term=search.trim().toLowerCase();
  return entries.filter(r=>r.category===category&&(filter==='all'||filter==='open'&&handling[r.id].status!=='已关闭'||handling[r.id].status===filter)&&(!term||[r.subject,r.detail,handling[r.id].owner,handling[r.id].action,handling[r.id].remark].join(' ').toLowerCase().includes(term)));
 }
 function categoryProgress(category){const list=entries.filter(r=>r.category===category);return {total:list.length,closed:list.filter(r=>handling[r.id].status==='已关闭').length};}
 function validDate(value,dateOnly=false){
  const pattern=dateOnly?/^\d{4}-\d{2}-\d{2}$/:/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/;
  return pattern.test(value)&&Number.isFinite(stamp(value))&&new Date(stamp(value)).toISOString().slice(0,dateOnly?10:16)===value;
 }
 function appendHistory(id,action,before,after,remark){
  const r=entry(id);state.clock+=60000;
  const freeze=value=>Object.freeze({...value});
  recordLog[id].push(Object.freeze({sequence:recordLog[id].length+1,time:new Date(state.clock).toISOString().slice(0,16),action,subject:r.subject,source:r.source,provenance,before:freeze(before),after:freeze(after),remark}));
  state.status=action+' · '+r.subject+' · 仅值班台示例会话';
 }
 function updateHandling(id,values){
  entry(id);const before=handling[id];
  if(before.status==='已关闭')throw new Error('该条目已关闭，请先填写原因并重开；原关闭证据保留。');
  const next={};Object.keys(before).forEach(key=>{next[key]=String(values[key]===undefined?before[key]:values[key]).trim();});
  if(!statuses.includes(next.status))throw new Error('请选择有效的处置状态。');
  if(!next.remark)throw new Error('请填写证据备注，说明本次核实情况或安排。');
  if(next.deadline&&!validDate(next.deadline,true))throw new Error('请填写有效的责任期限。');
  if(next.status!=='待分析'&&(!next.owner||!next.deadline||!next.action))throw new Error('认领、跟进、待验证或关闭都必须填写责任人、期限和处置动作。');
  if(next.status==='已关闭'){
   if(!next.completedAt||!next.completionEvidence||!next.evidenceRef)throw new Error('关闭必须填写完成时间、具体完成结果和可核对凭据，不能仅写“已处理”。');
   if(!validDate(next.completedAt)||stamp(next.completedAt)>state.clock)throw new Error('完成时间必须有效，且不晚于当前示例时点。');
   if(/^(已处理|已完成|完成|已核实|已关闭|关闭|ok|done)[。.!！\s]*$/i.test(next.completionEvidence))throw new Error('请写明具体完成结果，不能只写“已处理”或“已完成”。');
  }
  if(next.completedAt&&!validDate(next.completedAt))throw new Error('请填写有效的完成时间。');
  if(JSON.stringify(before)===JSON.stringify(next))throw new Error('内容没有变化，未新增重复记录。');
  handling[id]=next;delete state.drafts[id];
  appendHistory(id,next.status==='已关闭'?'关闭条目':'更新处置',before,next,next.remark);
  return next;
 }
 function reopen(id,reason){
  entry(id);const before=handling[id],remark=String(reason||'').trim();
  if(before.status!=='已关闭')throw new Error('只有已关闭条目可以重开。');
  if(!remark)throw new Error('请填写重开原因。');
  const next={...before,status:'跟进中',remark,completedAt:'',completionEvidence:'',evidenceRef:''};
  handling[id]=next;delete state.drafts[id];appendHistory(id,'重开条目',before,next,remark);return next;
 }
 function recordInput(category,rowId,action,before,after){
  entries.filter(r=>r.category===category&&r.rowId===rowId).forEach(r=>appendHistory(r.id,action,before,after,'仅更新'+provenance.label+'，不写入现场报工样例。'));
  state.revision++;state.inputTime=state.clock;
 }
 const destinations={delivery:[['gantt','计划甘特'],['analysis','方案选择']],actual:[['fieldgantt','现场实际甘特'],['review','执行复盘']],external:[['process','基础资料']],downtime:[['gantt','计划甘特'],['process','基础资料']],material:[['batches','批次管理'],['process','基础资料']],candidate:[['analysis','方案选择'],['run','执行排产']]};
 function navigation(id,page){
  const r=entry(id),target=destinations[r.category].find(d=>d[0]===page);
  if(!target)throw new Error('此条目没有对应的页面入口。');
  const current=['fieldgantt','review'].includes(page),planSource=window.APSPlanWorkbench?'方案工作区独立样例':'5 月排产独立样例';
  const targetSource=current?'现场报工独立样例':['gantt','analysis'].includes(page)?planSource:['batches','run'].includes(page)?'批次管理 / 执行排产独立样例':'基础资料独立样例';
  const reason=provenance.label+'与'+targetSource+'不是同一数据源，未建立该条目映射，无法定位。即使批次编号相同，也不视为同一记录。';
  const context={origin:{page:'dashboard',source:provenance.id,snapshot:provenance.snapshot,category:r.category,item:r.id,subject:r.subject},navigation:{mode:'overview',locatable:false,reason}};
  if(current){context.source='current';context.search='';if(page==='review')context.scope={source:'current'};}
  return {page,label:target[1],targetSource,locatable:false,reason,context};
 }
 function caseInfo(id){
  const s=stats(),o=overrunRows(),g=gaps(),ex=extLate(),sh=shortage(),ov=overlaps();
  const p=categoryProgress(id),common={state:p.closed+'/'+p.total+' 已关闭',scope:'9 月样例采用方案 v15'};
  const cases={
   delivery:{kind:'交期风险',tone:'red',icon:'calendar-clock',title:s.late+' 批预计晚交，共同经过 M-03',lead:'回转壳体 A、端盖 C、回转壳体 B 存在交期风险。先核对共同工序，再比较保交期与资源调整的代价。',impact:'最长晚 '+num(s.worst)+'h',source:'排程测算',detail:'3 个晚交批次的关联工序',short:'先看共同工序与影响批次'},
   actual:{kind:'执行偏差',tone:o.length?'amber':'green',icon:'clipboard-list',title:o.length?o.length+' 道工序实际工时超过定额 20%，需复核':'已回填记录中暂无工时超过定额 20% 的工序',lead:'将人工回填的实际开工、完工和工时与计划逐项对照；实际工时超过定额的 120% 才计为工时超耗，未填记录保留为待回填，不判断为未开工。',impact:g.length+' 道待回填',source:'人工回填 + 对比',detail:'现场回填与计划偏差',short:'实际工时与定额对照'},
   external:{kind:'外协跟踪',tone:ex.length?'amber':'blue',icon:'truck',title:ex.length?ex.length+' 项外协超过计划回厂时点':'外协回厂记录已更新',lead:'回厂进展来自外协登记。供应商周期用于计划，实际回厂时间用于后续工序衔接，两者分别保留。',impact:awaiting().length+' 项未登记回厂',source:'人工登记',detail:'外协回厂与后续衔接',short:'计划、实际与确认时间'},
   downtime:{kind:'停机冲突',tone:ov.length?'amber':'green',icon:'wrench',title:'M-05 周三检修，与 '+ov.length+' 道原计划工序重叠',lead:'检修窗口在本版排产后登记。下方核对原计划的重叠区间，最终后移量以调整后的排程为准。',impact:num(ov.reduce((s,r)=>s+r.hours,0))+'h 区间重叠',source:'停机登记 + 计算',detail:'计划检修与排程重叠',short:'先确认受影响的工序'},
   material:{kind:'齐套缺口',tone:sh.length?'amber':'green',icon:'boxes',title:sh.length+' 批尚未齐套，需确认可排日期',lead:'从当前批次池读取齐套状态与齐套日期。齐套检查开启时，这些批次不应直接进入正常排程。',impact:pendingRows.length+' 批待排',source:'批次录入',detail:'待排批次与齐套状态',short:'齐套状态、交期与优先级'},
   candidate:{kind:'方案选择',tone:'blue',icon:'git-compare-arrows',title:'2 套备选方案，收益与代价不同',lead:'相同批次范围下对比候选排程：优先保护急件，或者优先降低总拖期。每个方案保留自己的指标与批次结果。',impact:'2 套备选',source:'候选结果示例',detail:'候选方案取舍',short:'先比较，再决定采用'}
  };
  return {...common,...cases[id]};
 }
 return {stamp,short,num,NOW,batchData,plans,actualRows,externalRows,pendingRows,stop,stopTasks,state,handling,recordLog,caseOrder,planRows,stats,overrunRows,gaps,awaiting,extLate,shortage,overlaps,caseInfo,provenance,entries,statuses,entry,items,categoryProgress,updateHandling,reopen,recordInput,destinations,navigation};
 };
})();
