(function () {
 "use strict";
 const ns=window.APSFieldReports={};
const ms=s=>Date.parse(s+'Z');
const fmt=s=>s?s.slice(5,16).replace('T',' '):'';
const number=n=>Number.isInteger(n)?String(n):n.toFixed(1);
const NOW=ms('2026-09-07T16:30');
const labels={none:'待报工',started:'已登记开工',partial:'部分完成',done:'已完工'};
const tasks=[
  {id:'t1',batch:'B202609-031',name:'回转壳体 A',op:'30 精加工',target:10,machine:'M-03',person:'张三',planStart:'2026-09-07T08:00',planEnd:'2026-09-07T15:30',closed:false,reports:[{id:'r1',qty:6,start:'2026-09-07T08:10',end:'2026-09-07T12:10',hours:3.5,machine:'M-03',person:'张三',remark:'首批 6 件加工完成；剩余 4 件下午继续。',recorded:'2026-09-07T12:20',revision:0}]},
  {id:'t2',batch:'B202609-032',name:'回转壳体 B',op:'20 预加工',target:12,machine:'M-05',person:'李四',planStart:'2026-09-07T08:00',planEnd:'2026-09-08T11:00',closed:false,reports:[{id:'r2',qty:5,start:'2026-09-07T08:00',end:'2026-09-07T11:00',hours:2.5,machine:'M-05',person:'李四',remark:'已完成 5 件。',recorded:'2026-09-07T11:15',revision:0}]},
  {id:'t3',batch:'B202609-029',name:'定位环',op:'50 检验',target:6,machine:'M-12',person:'王五',planStart:'2026-09-07T08:00',planEnd:'2026-09-07T09:45',closed:true,reports:[{id:'r3',qty:6,start:'2026-09-07T08:00',end:'2026-09-07T09:30',hours:1.5,machine:'M-12',person:'王五',remark:'全部检验完成。',recorded:'2026-09-07T09:40',revision:0}]},
  {id:'t4',batch:'B202609-034',name:'端盖',op:'40 组装',target:8,machine:'M-07',person:'赵六',planStart:'2026-09-07T13:00',planEnd:'2026-09-08T10:00',closed:false,reports:[{id:'r4',qty:null,start:'2026-09-07T13:30',end:'',hours:null,machine:'M-07',person:'赵六',remark:'已登记实际开工。',recorded:'2026-09-07T13:40',revision:0}]},
  {id:'t5',batch:'B202609-036',name:'支撑座',op:'10 下料',target:20,machine:'M-18',person:'刘七',planStart:'2026-09-07T14:00',planEnd:'2026-09-07T16:00',closed:false,reports:[]}
 ];
tasks.forEach(t=>t.reports.forEach(r=>{r.reportNo='BG-20260907-'+r.id.slice(1).padStart(4,'0');}));
const state={filter:'all',search:'',selected:'t1',expanded:'t1',timelines:{},reportInfo:{},drafts:{},clock:NOW,status:'示例会话 · 未连接生产数据'};
const corrections=[];
const getTask=id=>tasks.find(t=>t.id===id);
const ordered=t=>t.reports.slice().sort((a,b)=>ms(a.start)-ms(b.start));
const complete=r=>Boolean(r.start&&r.end&&r.qty!==null&&r.hours!==null);
const isOperationComplete=t=>t.reports.length>0&&t.reports.every(complete)&&t.reports.reduce((n,r)=>n+r.qty,0)===t.target;
tasks.forEach(t=>{t.closed=isOperationComplete(t);});
const quantityLimit=(task,existingId)=>task.target-task.reports.filter(r=>r.id!==existingId).reduce((sum,r)=>sum+(r.qty===null?0:r.qty),0);
function summary(t){
  const reports=ordered(t),qty=reports.reduce((n,r)=>n+(r.qty===null?0:r.qty),0),hours=reports.reduce((n,r)=>n+(r.hours===null?0:r.hours),0);
  const start=reports.length?reports[0].start:'',ends=reports.filter(r=>r.end).map(r=>r.end).sort(),latest=ends.length?ends[ends.length-1]:'';
  const done=isOperationComplete(t),status=done?'done':qty>0?'partial':reports.length?'started':'none';
  return {qty,hours,start,latest,end:done?latest:'',remaining:t.target-qty,status,reports,incomplete:reports.filter(r=>!complete(r)).length};
 }
function validateReport(t,record,existingId,clock){
  const {qty,hours,start,end,machine,person}=record,others=t.reports.filter(r=>r.id!==existingId);
  const validDate=s=>/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(s)&&Number.isFinite(ms(s))&&new Date(ms(s)).toISOString().slice(0,16)===s;
  if(!start||!validDate(start))return '请填写有效的实际开工日期和时间。';
  if(end&&!validDate(end))return '请填写有效的本次实际完工日期和时间。';
  if(ms(start)>clock||(end&&ms(end)>clock))return '实际时间不能晚于示例时点 '+fmt(new Date(clock).toISOString().slice(0,16))+'。';
  if(end&&ms(end)<=ms(start))return '本次实际完工必须晚于实际开工。';
  if(qty!==null&&(!Number.isInteger(qty)||qty<0))return '完成数量必须是非负整数。';
  if(hours!==null&&(!Number.isFinite(hours)||hours<0))return '有效工时必须是非负数。';
  if(!end&&(qty!==null||hours!==null))return '填写本次完成数量或工时后，请同时填写本次实际完工。';
  if(end&&(qty===null||hours===null))return '本次作业已结束，请补齐完成数量和有效工时。';
  if(end&&hours>(ms(end)-ms(start))/3600000+0.001)return '有效加工工时不能大于本次作业跨度。';
  if(qty>0&&hours===0)return '有完成数量时，有效加工工时不能为零。';
  const total=others.reduce((n,r)=>n+(r.qty===null?0:r.qty),0)+(qty===null?0:qty);
  if(total>t.target)return '累计完成将超过应做数量，请核对本次新增数量。';
  if(others.some(r=>Math.max(ms(start),ms(r.start))<Math.min(end?ms(end):Infinity,r.end?ms(r.end):Infinity)))return '本次实际时段与已有报工重叠，请核对记录。';
  if(total===t.target&&(!end||others.some(r=>!complete(r))))return '报齐数量前，请先补齐已有报工的实际完工、数量和工时。';
  if(!['M-03','M-05','M-07','M-12','M-18'].includes(machine))return '实际设备不在当前样板设备清单中。';
  if(!['张三','李四','王五','赵六','刘七'].includes(person))return '实际人员不在当前样板人员清单中。';
  return '';
 }
ns.planContext={version:15,generated:"09-07 08:40",range:"09-07 ～ 09-08"};
ns.model={ms,fmt,number,labels,tasks,state,corrections,getTask,ordered,complete,isOperationComplete,summary,quantityLimit,validateReport};
})();
