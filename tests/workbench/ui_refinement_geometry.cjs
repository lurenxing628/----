'use strict';

// Executed in a real page. Measurements retain rectangles so failures are reviewable.
function measure(view) {
  const rect = element => {
    const r = element.getBoundingClientRect();
    return {left:r.left, top:r.top, right:r.right, bottom:r.bottom, width:r.width, height:r.height};
  };
  const visible = element => {
    if (!element) return false;
    const r=rect(element),s=getComputedStyle(element);
    return r.width>0 && r.height>0 && s.display!=='none' && s.visibility!=='hidden';
  };
  const intersect=(a,b)=>a.left<b.right && b.left<a.right && a.top<b.bottom && b.top<a.bottom;
  const viewport={left:0,top:0,right:innerWidth,bottom:innerHeight};
  const shown=element=>visible(element) && intersect(rect(element),viewport)
    && (()=>{const box=clippingBox(element);return box.right>box.left&&box.bottom>box.top&&intersect(rect(element),box);})();
  function clippingBox(element) {
    const box={...viewport};
    for(let parent=element;parent;parent=parent.parentElement) {
      const style=getComputedStyle(parent),r=rect(parent);
      if(['auto','scroll','hidden','clip'].includes(style.overflowX)) {
        box.left=Math.max(box.left,r.left);box.right=Math.min(box.right,r.right);
      }
      if(['auto','scroll','hidden','clip'].includes(style.overflowY)) {
        box.top=Math.max(box.top,r.top);box.bottom=Math.min(box.bottom,r.bottom);
      }
    }
    return box;
  }
  const name=element=>(element.getAttribute('aria-label')||element.innerText||element.className||element.tagName).trim().slice(0,90);
  const checks=[];
  function add(id,ok,detail){checks.push({id,ok,detail});}
  const nav=[...document.querySelectorAll('.sidebar-nav .nav-item')].filter(visible);
  const last=nav[nav.length-1];
  add('G2',!!last && rect(last).bottom<=innerHeight && rect(last).top>=0,{last:last?{name:name(last),rect:rect(last)}:null});
  add('G4',document.documentElement.scrollWidth<=document.documentElement.clientWidth+1,
    {scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth});
  const primary=[...document.querySelectorAll('.btn.primary')].filter(element=>shown(element)&&!element.closest('[role="dialog"]'));
  add('G5',primary.length<=1,{buttons:primary.map(element=>({name:name(element),rect:rect(element)}))});
  const references=[],walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  while(walker.nextNode()) {
    const node=walker.currentNode,parent=node.parentElement;
    if(!parent||parent.closest('script,style,details.wb-ref')||!visible(parent))continue;
    const closed=parent.closest('details:not([open])');
    if(closed && !parent.closest('summary'))continue;
    const matches=node.textContent.match(/\b[0-9a-f]{32,}\b/gi);
    if(matches)references.push({text:node.textContent.trim().slice(0,160),matches,tag:parent.tagName});
  }
  add('G6',references.length===0,{references});
  const clipped=[];
  for(const element of document.querySelectorAll('.mo-tools label,.dy-metric strong,.dy-metric small,.mo-domains .wb-metric-value,.mo-domains .wb-metric-label')) {
    if(!shown(element))continue;
    const range=document.createRange();range.selectNodeContents(element);
    const clip=clippingBox(element);
    const bad=[...range.getClientRects()].filter(r=>r.width>0&&(r.left<clip.left-1||r.right>clip.right+1));
    if(bad.length)clipped.push({name:name(element),rect:rect(element),clip});
  }
  add('L1',clipped.length===0,{clipped});
  const overlaps=[];
  for(const selector of ['.mo-domains','.dy-metrics','.bd-chain']) {
    for(const group of document.querySelectorAll(selector)) {
      const nodes=[...group.children].filter(shown);
      for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++) {
        if(intersect(rect(nodes[i]),rect(nodes[j])))overlaps.push({group:selector,a:name(nodes[i]),b:name(nodes[j]),aRect:rect(nodes[i]),bRect:rect(nodes[j])});
      }
    }
  }
  add('L2',overlaps.length===0,{overlaps});
  const blocked=[];
  for(const element of document.querySelectorAll('.sidebar-nav a,.top-header button,.wb-col-actions button')) {
    if(!shown(element)||element.disabled)continue;
    const r=rect(element),clip=clippingBox(element),x=(Math.max(r.left,clip.left)+Math.min(r.right,clip.right))/2,
      y=(Math.max(r.top,clip.top)+Math.min(r.bottom,clip.bottom))/2,hit=document.elementFromPoint(x,y);
    if(!hit||!element.contains(hit))blocked.push({name:name(element),rect:r,clip,hit:hit?name(hit):null});
  }
  add('L3',blocked.length===0,{blocked});
  const tables=[...document.querySelectorAll('table')].filter(visible).map(table=>({name:name(table).slice(0,90),
    caption:!!table.querySelector('caption'),missingScope:[...table.querySelectorAll('th')].filter(th=>!th.hasAttribute('scope')).map(name)}));
  const disabled=[...document.querySelectorAll('button:disabled')].filter(visible).map(button=>({name:name(button),title:button.title,
    parentTitle:button.parentElement?.title||'',describedBy:button.getAttribute('aria-describedby'),
    visibleReasons:(button.getAttribute('aria-describedby')||'').split(/\s+/).map(id=>document.getElementById(id)).filter(visible).map(name)}));
  return {view,url:location.href,theme:document.documentElement.dataset.theme,viewport:{width:innerWidth,height:innerHeight},checks,
    observations:{tables,disabled,canvas:[...document.querySelectorAll('canvas')].map(canvas=>({label:name(canvas),tabIndex:canvas.tabIndex}))}};
}

async function measureTable() {
  const frame=document.querySelector('.batch-list-table.wb-table-frame,.batch-list-table .wb-table-frame,.wb-table-frame');
  if(!frame)return {id:'G1',ok:false,detail:{reason:'missing bounded table frame'}};
  const head=frame.querySelector('thead th');
  if(!head)return {id:'G1',ok:false,detail:{reason:'missing table header'}};
  const old={x:frame.scrollLeft,y:frame.scrollTop};
  const next=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  frame.scrollTop=Math.min(100,frame.scrollHeight-frame.clientHeight);frame.scrollLeft=frame.scrollWidth;await next();
  const f=frame.getBoundingClientRect(),h=head.getBoundingClientRect();
  const action=[...frame.querySelectorAll('tbody .wb-col-actions button,tbody .wb-col-actions a')].find(element=>{
    const r=element.getBoundingClientRect();return !element.disabled&&r.top>=h.bottom&&r.bottom<=Math.min(f.bottom,innerHeight)&&r.width>0;
  });
  if(!action){frame.scrollLeft=old.x;frame.scrollTop=old.y;return {id:'G1',ok:false,detail:{reason:'missing visible row action after scrolling'}};}
  const a=action.getBoundingClientRect();
  const x=(Math.max(a.left,f.left)+Math.min(a.right,f.right))/2,y=(a.top+a.bottom)/2,hit=document.elementFromPoint(x,y);
  const detail={frameHeight:frame.clientHeight,scrollHeight:frame.scrollHeight,scrollTop:frame.scrollTop,scrollLeft:frame.scrollLeft,
    frameTop:f.top,headTop:h.top,actionLeft:a.left,actionRight:a.right,frameRight:f.right,
    actionHit:!!hit&&action.contains(hit),overflowY:getComputedStyle(frame).overflowY};
  const ok=frame.clientHeight<=innerHeight && frame.scrollTop>0 && frame.scrollLeft>0 && Math.abs(h.top-f.top)<=3
    && a.left>=f.left-1 && a.right<=f.right+1 && detail.actionHit;
  frame.scrollLeft=old.x;frame.scrollTop=old.y;await next();
  return {id:'G1',ok,detail};
}

function measureGantt() {
  const lane=document.querySelector('[data-plan-gantt] .plan-lane');
  const row=lane?.querySelector('[data-plan-task],canvas')||document.querySelector('[data-plan-gantt] [data-plan-task],.plan-gantt [data-plan-task],.pg-row,.gb-row');
  if(!row)return {id:'G3',ok:false,detail:{reason:'missing selected plan first row'}};
  const r=row.getBoundingClientRect(),clip={left:0,right:innerWidth,top:0,bottom:innerHeight};
  for(let parent=row.parentElement;parent;parent=parent.parentElement) {
    const s=getComputedStyle(parent),box=parent.getBoundingClientRect();
    if(['auto','scroll','hidden','clip'].includes(s.overflowX)){clip.left=Math.max(clip.left,box.left);clip.right=Math.min(clip.right,box.right);}
    if(['auto','scroll','hidden','clip'].includes(s.overflowY)){clip.top=Math.max(clip.top,box.top);clip.bottom=Math.min(clip.bottom,box.bottom);}
  }
  const visibleHeight=Math.min(r.bottom,clip.bottom)-Math.max(r.top,clip.top),visibleWidth=Math.min(r.right,clip.right)-Math.max(r.left,clip.left);
  const label=lane?.querySelector('.plan-resource'),labelRect=label?.getBoundingClientRect(),laneRect=lane?.getBoundingClientRect();
  const labelVisible=!labelRect||(labelRect.top>=clip.top-1&&labelRect.bottom<=clip.bottom+1&&labelRect.left>=0&&labelRect.right<=innerWidth);
  const laneVisible=!laneRect||(laneRect.top>=clip.top-1&&laneRect.bottom<=clip.bottom+1);
  return {id:'G3',ok:r.width>0&&r.height>0&&r.top>=clip.top-1&&r.bottom<=clip.bottom+1&&r.left>=clip.left-1&&r.right<=clip.right+1&&labelVisible&&laneVisible,
    detail:{top:r.top,bottom:r.bottom,height:r.height,visibleHeight,visibleWidth,clip,labelVisible,laneVisible,
      label:labelRect?{top:labelRect.top,bottom:labelRect.bottom}:null,lane:laneRect?{top:laneRect.top,bottom:laneRect.bottom}:null}};
}

module.exports={measure,measureTable,measureGantt};
