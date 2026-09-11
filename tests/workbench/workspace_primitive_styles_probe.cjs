/* AH: isolated component mocks with actual app shell classes and published CSS. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const http = require('node:http'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass an artifact directory');
fs.mkdirSync(output, { recursive: true });
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const files = ['WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx', 'resource-contract.js', 'resource-session.js', 'ResourceControls.jsx', 'ResourceTables.jsx', 'ResourceForms.jsx',
  'BatchContract.js', 'BatchControls.jsx', 'BatchForms.jsx', 'BatchOperationEditor.jsx', 'BatchDetail.jsx', 'BatchTable.jsx', 'BatchFiles.jsx', 'BatchWorkspace.jsx',
  'PointContract.js', 'PlanProcessOrder.js', 'PlanContract.js', 'PointGanttModel.js', 'PointGantt.jsx', 'PlanGanttModel.js', 'PlanLayout.jsx', 'PlanGanttCanvas.jsx', 'PlanGantt.jsx', 'PlanCatalogUI.jsx', 'PlanDetailsUI.jsx', 'PlanExportUI.jsx', 'PlanWorkspace.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchNumberControls.jsx'];
const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const report = { scope: 'workspace-primitives-app-shell-component-mock', production_persistence_tested: false,
  compile: { global_build: false, target: built.target }, sources: sources.map(row => ({ path: row.path, sha256: hash(row.code) })),
  cases: [], legacy_checks: [], negative_controls: [], screenshots: [], errors: [], external: [] };
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json'))), assets = new Map();
report.style_build_id = manifest.build_id;
report.styles = manifest.styles;
for (const item of manifest.files) {
  const bytes = fs.readFileSync(path.join(root, 'static', item.path));
  assert.equal(hash(bytes), item.sha256, 'Shared asset changed while being read; rerun after build settles');
  assets.set('/static/' + item.path, { bytes, mime: item.mime });
}
const scripts = built.outputs.map((item, i) => {
  const url = '/fixture/' + files[i] + '.js'; assets.set(url, { bytes: item.code, mime: 'application/javascript' }); return url;
});
const dataFile = 'tests/workbench/plan_ui_fixtures.cjs', dataBytes = fs.readFileSync(path.join(root, dataFile));
report.sources.push({ path: dataFile, sha256: hash(dataBytes) });
assets.set('/fixture/plan-data.js', { bytes: dataBytes, mime: 'application/javascript' });
// The wrapper reproduces main.jsx's DOM, not the prototype AppShell or a plana host.
const fixture = `
const F = window.PlanUIFixtures, ref = F.ref, clone = F.clone, el = React.createElement;
const context = () => ({write_token:'memory-token',capabilities:Object.fromEntries(APSBatchContract.actions.map(a=>['batch.'+a,true])),blocked_reasons:[]});
function batch(n) {
  return {ref:ref(n),business_code:'AH-'+String(n).padStart(3,'0'),label:'传动轴组件',status:'pending',
    fields:{quantity:10,due_date:'2026-10-01',priority:'normal',ready_status:'no',ready_date:null,remark:null},
    relationships:{part_ref:ref(300),part_no:'PART-20066',part_name:'传动轴组件',operation_count:0,completed_count:0,gap_count:0,plan_reference_count:0,execution_reference_count:0,material_requirement_count:0},
    operations:[],all_operations_complete:false,issues:[],protected:false,write_context:context(),materials:{requirements:[],count:0},template:{origin:'legacy',ready:false}};
}
function batchAdapter() {
  return {
    list:async(kind,scope)=>{state.reads++;const rows=state.rows.filter(r=>!scope.status||r.status===scope.status);return F.envelope({entities:clone(rows.slice((scope.page-1)*scope.size,scope.page*scope.size)),
      page:{number:scope.page,size:scope.size,total:rows.length,pages:Math.max(1,Math.ceil(rows.length/scope.size)),sort:[{field:scope.sort,direction:scope.direction}]},create_context:context()});},
    detail:async(kind,id)=>F.envelope(clone(state.rows.find(r=>r.ref===id))),
    choices:async()=>F.envelope({parts:[{ref:ref(300),business_code:'PART-20066',label:'传动轴组件'}]}),
    facets:async(scope,field)=>F.envelope({field,values:[10,20,30],count:3}),
    importPreview:async(file,mode)=>F.envelope({operation:'batch.import_confirm',mode,preview_ref:'p'.repeat(32),write_context:context(),count:4,can_confirm:true,commit_policy:'atomic',deleted:[],warnings:[],
      rows:Array.from({length:4},(_,i)=>({row:i+2,business_code:'IMPORT-'+i,action:'create',before:null,errors:[],input:{fields:{quantity:3,remark:'待核对的导入资料'}}}))}),
    command:async(kind,action,id,body)=>{state.commands.push({action,input:clone(body.input)});if(action==='create'){const row=batch(state.rows.length+1);row.business_code=body.input.business_code;row.fields=clone(body.input.fields);state.rows.push(row);id=row.ref;}
      else if(action==='update')Object.assign(state.rows.find(r=>r.ref===id).fields,body.input.fields);else throw new Error('Unsupported mock write: '+action);
      return {ok:true,result:'committed',receipt_ref:'receipt-'+state.commands.length,replayed:false,data:{entity_ref:id},warnings:[]};},
    readPending:()=>null,savePending:()=>{},clearPending:()=>{}
  };
}
function shell(child,legacy) {
  return el('div',{className:'app-container operations-shell'},
    el('aside',{className:'sidebar'},el('div',{className:'sidebar-header'},el('span',{className:'brand-word'},'APS 智能排产'))),
    el('div',{className:'main-content'},el('header',{className:'top-header'},el('h2',{className:'top-title'},'工作区')),
      el('main',{className:'page-content'},legacy?el('section',{className:'plana','data-legacy-host':true},child):child)));
}
let mounted;
window.mountPrimitive = (kind,legacy=false) => {
  if(mounted)mounted.unmount();
  window.state={rows:Array.from({length:25},(_,i)=>batch(i+1)),commands:[],reads:0};
  const adapter=kind==='batch'?batchAdapter():{catalog:async scope=>F.catalog(scope),workspace:async(reference,scope)=>F.workspace(reference,scope),export:async()=>{throw new Error('No download in style probe');}};
  const child=kind==='batch'?el(BatchWorkspace,{adapter}):el(PlanWorkspace,{adapter,view:'gantt',planRef:ref(1)});
  mounted=ReactDOM.createRoot(document.getElementById('fixture-root'));
  mounted.render(el(React.Fragment,null,el(WorkbenchControlStyles),el(WorkbenchControls),el(WorkbenchNumberControls),shell(child,legacy)));
};
`;
new (require('node:vm').Script)(fixture);
assets.set('/fixture/harness.js', { bytes: fixture, mime: 'application/javascript' });
const scriptUrls = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'))
  .map(file => '/static/' + file).concat(scripts, ['/fixture/plan-data.js', '/fixture/harness.js']);
const html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '</head><body class="aps-workbench"><div id="fixture-root"></div>' + scriptUrls.map(url => '<script src="' + url + '"></script>').join('') + '</body></html>';
const server = http.createServer((req, res) => {
  if (req.url === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (req.url === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  const item = assets.get(req.url);
  if (!item) { report.errors.push('Unexpected request: ' + req.url); res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', item.mime); res.end(item.bytes);
});
let page, variant;
const button = name => page.getByRole('button', { name, exact: true });
async function mount(kind, legacy = false) {
  await page.evaluate(({ kind, legacy }) => mountPrimitive(kind, legacy), { kind, legacy });
  await (kind === 'batch' ? button('AH-001') : page.locator('.plan-board')).waitFor();
  await page.evaluate(() => document.fonts.ready);
}
async function geometry(kind, legacy = false) {
  const value = await page.evaluate(({ kind }) => {
    const root = document.querySelector('[data-' + kind + '-workspace]'), style = getComputedStyle(root), parent = root.parentElement;
    const rect = el => { const r = el.getBoundingClientRect(); return { x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom }; };
    const parentStyle = getComputedStyle(parent);
    return { viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,scope:root.classList.contains('plana'),
      ancestor:!!parent.closest('.plana'),padding:[style.paddingTop,style.paddingRight,style.paddingBottom,style.paddingLeft],maxWidth:style.maxWidth,
      root:rect(root),available:parent.clientWidth-parseFloat(parentStyle.paddingLeft)-parseFloat(parentStyle.paddingRight),
      containers:[...document.querySelectorAll('.main-content,.page-content')].map(el=>({name:el.className,width:el.clientWidth,scroll:el.scrollWidth})),
      toolbars:[...root.querySelectorAll('.toolbar')].map(el=>({display:getComputedStyle(el).display,align:getComputedStyle(el).alignItems})),
      pager:root.querySelector('.pager')&&{display:getComputedStyle(root.querySelector('.pager')).display,select:rect(root.querySelector('.pager select'))} };
  }, { kind });
  assert(value.scope && value.ancestor === legacy, JSON.stringify(value));
  assert.deepEqual(value.padding, ['0px', '0px', '0px', '0px']); assert.equal(value.maxWidth, 'none');
  assert(Math.abs(value.root.width - value.available) <= 1, JSON.stringify(value));
  assert(value.documentWidth <= value.viewport + 1, JSON.stringify(value));
  value.containers.forEach(row => assert(row.scroll <= row.width + 1, JSON.stringify(row)));
  value.toolbars.forEach(row => { assert.equal(row.display, 'flex'); assert.equal(row.align, 'center'); });
  if (value.pager) { assert.equal(value.pager.display, 'flex'); assert(value.pager.select.width >= 70 && value.pager.select.width <= 220, JSON.stringify(value.pager)); }
  return value;
}
async function modalGeometry() {
  await page.locator('.modal-bg').evaluate(el => Promise.all(el.getAnimations().map(animation => animation.finished)));
  const result = await page.getByRole('dialog').evaluate(el => {
    const rect = node => { const r=node.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}; };
    const bg=el.parentElement, style=getComputedStyle(bg);
    return {viewport:{width:innerWidth,height:innerHeight},backdrop:rect(bg),position:style.position,display:style.display,
      dialog:rect(el),center:document.elementFromPoint(innerWidth/2,innerHeight/2)?.closest('[role="dialog"]')===el,
      corner:document.elementFromPoint(2,2)===bg};
  });
  const { viewport:v, backdrop:b, dialog:d } = result;
  assert.equal(result.position, 'fixed', JSON.stringify(result)); assert.equal(result.display, 'grid');
  assert(Math.abs(b.x) <= 1 && Math.abs(b.y) <= 1 && Math.abs(b.width-v.width) <= 1 && Math.abs(b.height-v.height) <= 1, JSON.stringify(result));
  assert(Math.abs(d.x+d.width/2-v.width/2) <= 1 && Math.abs(d.y+d.height/2-v.height/2) <= 1, JSON.stringify(result));
  assert(d.x >= 0 && d.y >= 0 && d.right <= v.width+1 && d.bottom <= v.height+1 && result.center && result.corner, JSON.stringify(result));
  return result;
}
async function contrast() {
  const rows = await page.evaluate(() => {
    const color=value=>{const nums=value.match(/[\d.]+/g).map(Number);return [nums[0],nums[1],nums[2],nums.length>3?nums[3]:1];};
    const blend=(fg,bg)=>fg.slice(0,3).map((v,i)=>v*fg[3]+bg[i]*(1-fg[3]));
    const luminance=rgb=>rgb.map(v=>{v/=255;return v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4);}).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
    return [...document.querySelectorAll('[role="dialog"] .modal-h2,[role="dialog"] .field>label,[role="dialog"] p,[role="dialog"] strong,[role="dialog"] button:not(:disabled),.pager>span,.plan-muted')]
      .filter(el=>el.getClientRects().length && el.textContent.trim()).map(el=>{
        const chain=[];for(let node=el;node;node=node.parentElement)chain.unshift(node);
        let bg=[255,255,255],opacity=1;
        for(const node of chain){const s=getComputedStyle(node);bg=blend(color(s.backgroundColor),bg);opacity*=Number(s.opacity);}
        const s=getComputedStyle(el),fg=blend(color(s.color),bg),a=luminance(fg),b=luminance(bg);
        return {text:el.textContent.trim().slice(0,50),ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),opacity,color:s.color,background:bg};
      }).filter(row=>row.opacity>.99);
  });
  assert(rows.length > 0); rows.forEach(row=>assert(row.ratio>=4.5, JSON.stringify(row))); return rows;
}
async function shot(kind, name, modal = false) {
  await page.waitForFunction(() => document.getAnimations().every(animation =>
    typeof animation.transitionProperty !== 'string' || (!animation.pending && animation.playState !== 'running')));
  const layout=await geometry(kind), dialog=modal?await modalGeometry():null, colors=await contrast();
  const file=variant+'-'+kind+'-'+name+'.png';
  await page.screenshot({path:path.join(output,file),fullPage:!modal,animations:'disabled'});
  report.screenshots.push({file,layout,dialog,colors});
}
async function scrollCheck(selector, force = false) {
  if (force) {
    const resizer=page.getByRole('separator',{name:'调整图号列宽'});await resizer.focus();for(let i=0;i<35;i++)await resizer.press('ArrowRight');
  }
  const result=await page.locator(selector).evaluate(el=>{el.scrollLeft=200;return {width:el.clientWidth,scroll:el.scrollWidth,left:el.scrollLeft,overflow:getComputedStyle(el).overflowX};});
  assert(['auto','scroll'].includes(result.overflow) && result.scroll>result.width && result.left>0, JSON.stringify(result));
  return result;
}
async function negative(kind) {
  const before=await modalGeometry();
  const broken=await page.evaluate(kind=>{const root=document.querySelector('[data-'+kind+'-workspace]');root.classList.remove('plana');const result=getComputedStyle(root.querySelector('.modal-bg')).position;root.classList.add('plana');return result;},kind);
  assert.notEqual(broken,'fixed','Regression control must fail without workspace primitive scope');
  report.negative_controls.push({kind,variant,removed_scope_position:broken,fixed_position:before.position});
}
async function batchCases() {
  await mount('batch'); await shot('batch','list');
  await button('新增批次').click(); await page.getByLabel('图号',{exact:true}).selectOption('12c'.padStart(48,'0'));
  await page.getByLabel('批次号',{exact:true}).fill('AH-CREATED'); await page.getByLabel('数量',{exact:true}).fill('7');
  await shot('batch','create',true);if(variant==='1920-light')await negative('batch');
  await button('创建批次').click();await page.getByText('服务器已确认提交。',{exact:true}).waitFor();
  await shot('batch','receipt',true);assert.equal(await page.evaluate(()=>state.commands[0].action),'create');
  await page.getByRole('dialog').getByRole('button',{name:'关闭',exact:true}).last().click();
  await page.waitForFunction(()=>state.reads>1 && state.rows.length===26);
  await button('AH-001').click();await button('编辑基础信息').click();await shot('batch','edit',true);
  await page.getByLabel('备注',{exact:true}).fill('AH edit');await button('保存基础信息').click();await page.getByText('服务器已确认提交。',{exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>state.commands[1].action),'update');await page.getByRole('dialog').getByRole('button',{name:'关闭',exact:true}).last().click();
  await button('返回列表').click();await button('筛选').click();await shot('batch','filter',true);await button('完成').click();
  await button('筛选数量').click();await page.getByText('全选列值',{exact:true}).waitFor();await shot('batch','column-filter',true);await button('取消').click();
  await button('批量导入').click();await shot('batch','import',true);
  await page.getByLabel('选择 Excel 文件').setInputFiles({name:'ah.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:Buffer.from('Explicit style-only mock')});
  await button('预览导入').click();await page.getByRole('table',{name:'批次导入预览'}).waitFor();await shot('batch','import-preview',true);
  await scrollCheck('.batch-preview');await button('取消').click();await scrollCheck('.wb-table-frame',true);await geometry('batch');
  const reads=await page.evaluate(()=>state.reads);await button('下一页').click();await page.waitForFunction(n=>state.reads>n,reads);await button('AH-021').waitFor();
  await mount('batch',true);report.legacy_checks.push({variant,kind:'batch',layout:await geometry('batch',true)});
  await button('新增批次').click();await modalGeometry();
}
async function planCases() {
  await mount('plan');await shot('plan','workspace');await button('导出').click();await shot('plan','export',true);
  if(variant==='1920-light')await negative('plan');
  await button('取消').click();await button('放大时间轴').click();await scrollCheck('.plan-board');await geometry('plan');
  await mount('plan',true);report.legacy_checks.push({variant,kind:'plan',layout:await geometry('plan',true)});
  await button('导出').click();await modalGeometry();
}
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
  try {
    browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-background-networking']});
    report.browser=browser.version();assert(report.browser.startsWith('109.'));
    const origin='http://127.0.0.1:'+server.address().port;
    for(const width of [1920,1392])for(const theme of ['light','dark']){
      const context=await browser.newContext({viewport:{width,height:1080}});page=await context.newPage();variant=width+'-'+theme;page.setDefaultTimeout(12000);
      page.on('pageerror',error=>report.errors.push(error.message));page.on('console',msg=>{if(msg.type()==='error')report.errors.push(msg.text());});
      await page.route('**/*',route=>{if(!route.request().url().startsWith(origin+'/')){report.external.push(route.request().url());return route.abort();}return route.continue();});
      await page.goto(origin);await page.evaluate(theme=>{document.documentElement.dataset.theme=theme;document.documentElement.style.colorScheme=theme;},theme);
      for(const [kind,run] of [['batch',batchCases],['plan',planCases]]){
        try{await run();report.cases.push({variant,kind,passed:true});}
        catch(error){report.cases.push({variant,kind,passed:false,error:error.message});await page.screenshot({path:path.join(output,variant+'-'+kind+'-FAILED.png'),fullPage:true});throw error;}
      }
      await context.close();
    }
    assert.deepEqual(report.errors,[]);assert.deepEqual(report.external,[]);
  }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));fs.writeFileSync(path.join(output,'primitive-styles-result.json'),JSON.stringify(report,null,2));}
  console.log(JSON.stringify({output,browser:report.browser,cases:report.cases.length,screenshots:report.screenshots.length}));
})().catch(error=>{console.error(error);process.exitCode=1;});
