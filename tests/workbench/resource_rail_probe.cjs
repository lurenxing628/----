/* Isolated components with summaries produced by real services on a new fixture DB. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const [output, fixturePath] = process.argv.slice(2);
if (!output || !fixturePath) throw new Error('Pass an artifact directory and service-generated fixture JSON');
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const order = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json')));
const records = new Map(manifest.files.map(item => [item.path, item]));
const sourceNames = ['resource-session.js', 'ResourceRail.jsx', 'ResourceWorkspace.jsx'];
const sources = sourceNames.map(name => ({path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8')}));
// Compile only the component-under-test into memory; do not publish or edit build-order.
const compiled = compile({babel_path: path.join(root, 'frontend/workbench/prototype', order.babel.path), sources}).outputs;
const overrides = new Map(compiled.map(item => ['workbench/' + item.path.replace(/\.jsx$/, '.js'), item.code]));
let scripts = manifest.scripts.filter(name => !name.endsWith('/main.js') && !name.endsWith('/ResourceRail.js'));
scripts.splice(scripts.indexOf('workbench/app/ResourceWorkspace.js'), 0, 'workbench/app/ResourceRail.js');
const facts = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
const fixture = `
window.railFixture = {facts:${JSON.stringify(facts).replace(/</g, '\\u003c')}, mode:'initial', reads:0, navigations:[], deferred:[]};
function envelope(data) { return {ok:true,schema_version:1,data,meta:{source:'demo',time_basis:'factory_local',snapshot_ref:'isolated-summary',request_ref:'fixture-request',as_of:'2026-09-09T12:00:00'},warnings:[]}; }
window.railAdapter = {
  summary: async signal => {
    const state=railFixture; state.reads++;
    if(state.mode==='failed') throw new Error('Fixture summary read failed');
    if(state.mode==='delayed') return new Promise(resolve=>state.deferred.push(()=>resolve(envelope(state.facts.initial))));
    if(state.mode==='legacy') return envelope({counts:state.facts.initial.counts,metrics:state.facts.initial.metrics});
    if(state.mode==='malformed') {const data=JSON.parse(JSON.stringify(state.facts.initial)); data.calendar.days[2].effective.hours='invalid';return envelope(data);}
    if(state.mode==='false-ready') {const data=JSON.parse(JSON.stringify(state.facts.initial));data.readiness.ratio=100;data.readiness.status='ready';return envelope(data);}
    return envelope(state.facts[state.mode]);
  },
  list: async()=>envelope({entities:[],page:{number:1,size:20,total:0,pages:1,sort:[]},create_context:null})
};
function Harness() {
  const [revision,setRevision]=React.useState(0);
  railFixture.refresh=()=>setRevision(value=>value+1);
  return React.createElement(AppShell,{active:'process',title:'Resource rail component fixture',theme:document.documentElement.dataset.theme,showCapsule:false,onNav:()=>{}},
    React.createElement(ResourceWorkspace,{adapter:railAdapter,initialNode:'process',externalRevision:revision,onNavigate:key=>railFixture.navigations.push(key),
      renderCalendar:({onCommitted})=>React.createElement('button',{id:'fixture-calendar-commit',onClick:()=>{railFixture.mode='changed';onCommitted();}},'Fixture calendar commit')}));
}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(Harness));
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(name => '<link rel="stylesheet" href="/static/' + name + '">').join('') +
  '</head><body class="aps-workbench"><div id="root"></div>' + scripts.map(name => '<script src="/static/' + name + '"></script>').join('') +
  '<script>' + fixture + '</script></body></html>';
const server = http.createServer((req, res) => {
  if(req.url === '/') {res.setHeader('Content-Type','text/html;charset=utf-8');res.end(html);return;}
  if(req.url === '/favicon.ico') {res.writeHead(204);res.end();return;}
  const name = new URL(req.url, 'http://fixture').pathname.slice('/static/'.length);
  if(overrides.has(name)) {res.setHeader('Content-Type','application/javascript');res.end(overrides.get(name));return;}
  if(!records.has(name)) {res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',records.get(name).mime);
  res.end(fs.readFileSync(path.join(root,'static',name)));
});
async function mode(page, name) {
  const reads=await page.evaluate(name=>{const reads=railFixture.reads;railFixture.mode=name;railFixture.refresh();return reads;},name);
  await page.waitForFunction(reads=>railFixture.reads>reads&&document.querySelector('.rail').getAttribute('aria-busy')==='false',reads);
}
async function inspect(page, viewport) {
  const geometry=await page.evaluate(()=>{
    const rail=document.querySelector('.rail'), bounds=rail.getBoundingClientRect();
    const boxes=Array.from(rail.querySelectorAll('.hb-hub > .hb-block')).map(node=>{const r=node.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};});
    const overflow=Array.from(rail.querySelectorAll('.hb-tname,.hb-tmeta,.hb-csv,.hb-csl,.hb-sl,.hb-rl2,.hb-r-tag,.hb-cl2')).filter(node=>node.scrollWidth>node.clientWidth+1).map(node=>({text:node.textContent,width:node.clientWidth,scroll:node.scrollWidth}));
    return {width:innerWidth,scroll:document.documentElement.scrollWidth,rail:{left:bounds.left,right:bounds.right,height:bounds.height},boxes,overflow,theme:document.documentElement.dataset.theme};
  });
  assert(geometry.scroll<=viewport.width+1,JSON.stringify(geometry));
  assert(geometry.boxes.every(box=>box.width>0&&box.height>0&&box.left>=geometry.rail.left-1&&box.right<=geometry.rail.right+1));
  assert.deepEqual(geometry.overflow,[],'Rail text must fit its actual parent');
  for(let i=0;i<geometry.boxes.length;i++) for(let j=i+1;j<geometry.boxes.length;j++) {
    const a=geometry.boxes[i],b=geometry.boxes[j];
    assert(Math.min(a.right,b.right)-Math.max(a.left,b.left)<1||Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)<1,'Rail sections overlap');
  }
  return geometry;
}
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let browser;
  const result={scope:'isolated-component-with-service-generated-fixture',build_id:manifest.build_id,sources:sources.map(item=>({path:item.path,sha256:crypto.createHash('sha256').update(item.code).digest('hex')})),cases:[],errors:[],external:[]};
  try {
    browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-background-networking']});
    assert(browser.version().startsWith('109.'),'Actual Chromium 109 required');result.browser=browser.version();
    const origin='http://127.0.0.1:'+server.address().port;
    for(const viewport of [{width:1920,height:1080},{width:1392,height:924},{width:1366,height:768},{width:1280,height:720}]) for(const theme of ['light','dark']) {
      const context=await browser.newContext({viewport,timezoneId:'America/Los_Angeles'});
      await context.addInitScript(theme=>{localStorage.setItem('aps_theme',theme);localStorage.setItem('aps_kit_theme',theme);},theme);
      const page=await context.newPage();
      page.on('pageerror',error=>result.errors.push(error.message));
      page.on('console',message=>{if(message.type()==='error')result.errors.push(message.text());});
      await page.route('**/*',route=>{if(!route.request().url().startsWith(origin+'/')){result.external.push(route.request().url());return route.abort();}return route.continue();});
      await page.goto(origin);
      // Short screens (<= 820px, --wb-short-screen-max) start collapsed once a node is selected; expand to inspect the full rail.
      const toggle=page.getByRole('button',{name:'展开产能链'});
      if(viewport.height<=820){await toggle.waitFor();assert.equal(await page.locator('.hb-cal-block').count(),0,'Short screens with a selected node start collapsed');
        assert.equal(await page.locator('[data-rail-node="process"]').getAttribute('aria-pressed'),'true','Compact chips keep the node selection');
        await toggle.click();await page.getByRole('button',{name:'收起产能链'}).waitFor();}
      else assert.equal(await toggle.count(),0,'Tall screens have no rail toggle');
      await page.locator('[data-calendar-date="2026-09-09"]').waitFor();
      await page.evaluate(()=>document.fonts.ready);
      const rail=page.locator('.rail');
      assert((await rail.innerText()).includes('工厂日期 2026-09-09'),'Server factory date, not browser timezone');
      assert.equal(await page.locator('.hb-rl2').innerText(),'暂无数据');
      assert.equal(await page.locator('.hb-r-floor i').count(),0,'No invented ratio bar');
      assert((await page.locator('[data-rail-node="process"]').innerText()).includes('0 项'));
      assert((await page.locator('[data-rail-node="process"]').innerText()).includes('暂无零件'));
      assert((await page.locator('[data-rail-node="machine"]').innerText()).includes('停用 1'));
      assert((await page.locator('[data-rail-node="operator"]').innerText()).includes('未知 1'));
      assert((await page.locator('[data-rail-node="op_int"]').innerText()).includes('未关联设备 1'));
      assert((await page.locator('[data-rail-node="op_ext"]').innerText()).includes('周期规则未设 1'));
      const night=page.locator('[data-calendar-date="2026-09-09"]');
      assert((await night.innerText()).includes('7.0 小时'));assert((await night.getAttribute('title')).includes('普通件 不允许'));
      assert((await night.getAttribute('title')).includes('2026-09-10 06:30:00'));
      assert.equal(await night.getAttribute('data-calendar-source'),'explicit');
      assert.equal(await page.locator('[data-calendar-date="2026-09-07"]').getAttribute('data-calendar-source'),'service_default');
      assert((await page.locator('.hb-cal-stats').innerText()).includes('未填写'));
      const geometry=await inspect(page,viewport);assert.equal(geometry.theme,theme);
      const screenshot=viewport.width+'x'+viewport.height+'-'+theme+'.png';
      await page.screenshot({path:path.join(output,screenshot)});
      for(const key of ['material','op_int','machine','operator','op_ext','supplier','process']) {
        await page.locator('[data-rail-node="'+key+'"]').click();
        assert.equal(await page.locator('[data-rail-node="'+key+'"]').getAttribute('aria-pressed'),'true');
      }
      await page.locator('.hb-cal-block').click();
      await page.locator('#fixture-calendar-commit').click();
      await page.waitForFunction(()=>document.querySelector('[data-rail-node="machine"]').textContent.includes('停用 2'));
      assert((await page.locator('[data-calendar-date="2026-09-12"]').innerText()).includes('3.0 小时'),'Calendar commit refreshes summary');
      await page.locator('.hb-r-next').click();assert.deepEqual(await page.evaluate(()=>railFixture.navigations),['batches']);
      await mode(page,'broken');
      assert.equal(await night.getAttribute('data-calendar-status'),'unavailable');
      assert((await page.locator('[data-calendar-week-hours]').innerText()).includes('本周有效 暂无数据'));
      assert((await page.locator('[data-calendar-date="2026-09-12"]').innerText()).includes('3.0 小时'));
      await mode(page,'legacy');assert((await page.locator('.hb-cal-block').innerText()).includes('暂无数据'));
      assert((await page.locator('[data-rail-node="machine"]').innerText()).includes('6 台'),'Backward compatible count envelope');
      await mode(page,'malformed');assert((await page.locator('.hb-cal-block').innerText()).includes('读到的班表汇总不完整'));
      assert((await page.locator('[data-rail-node="machine"]').innerText()).includes('6 台'));
      await mode(page,'false-ready');assert.equal(await page.locator('.hb-rl2').innerText(),'暂无数据');
      assert(!(await rail.innerText()).includes('100%'));
      await mode(page,'failed');assert((await rail.innerText()).includes('Fixture summary read failed'));
      assert.equal(await page.locator('.hb-rl2').innerText(),'暂无数据');
      assert(!(await page.locator('[data-rail-node="machine"]').innerText()).includes('6 台'),'Failed refresh clears stale totals');
      await page.evaluate(()=>{railFixture.mode='delayed';railFixture.refresh();});
      await page.waitForFunction(()=>railFixture.deferred.length===1);
      assert.equal(await page.locator('.hb-rl2').innerText(),'未读取');
      await mode(page,'changed');
      await page.evaluate(()=>railFixture.deferred.splice(0).forEach(resolve=>resolve()));
      assert((await page.locator('[data-rail-node="machine"]').innerText()).includes('停用 2'),'Late old response cannot overwrite new summary');
      await inspect(page,viewport);
      result.cases.push({viewport,theme,geometry,screenshot,checks:['factory-date','explicit-default-zero','night-efficiency-permissions','unknown-stages','inactive-unknown','navigation','calendar-commit-refresh','bad-day-isolation','legacy-shape','malformed-shape','reject-false-ready','failed-refresh','stale-response']});
      await context.close();
    }
    assert.deepEqual(result.errors,[]);assert.deepEqual(result.external,[]);
  } finally {
    if(browser)await browser.close();
    await new Promise(resolve=>server.close(resolve));
    fs.writeFileSync(path.join(output,'component-result.json'),JSON.stringify(result,null,2)+'\n');
  }
  console.log(JSON.stringify({output,browser:result.browser,cases:result.cases.length,scope:result.scope,errors:result.errors,external:result.external}));
})().catch(error=>{console.error(error);process.exitCode=1;});
