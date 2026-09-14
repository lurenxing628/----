/* Real ResourceLive callback and service-produced counts; process editor/transport are mocks. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const [output, fixturePath] = process.argv.slice(2);
if (!output || !fixturePath) throw new Error('Pass output directory and service fixture JSON');
fs.mkdirSync(output, { recursive: true });
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const manifestBytes = fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json'));
const manifest = JSON.parse(manifestBytes), order = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json')));
const assets = new Map(manifest.files.map(item => [item.path, { ...item, bytes: fs.readFileSync(path.join(root, 'static', item.path)) }]));
const sources = ['resource-session.js', 'ResourceRail.jsx', 'ResourceWorkspace.jsx', 'ResourceLive.jsx'].map(name => ({
  path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8')
}));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype', order.babel.path), sources }).outputs;
const overrides = new Map(compiled.map(item => ['workbench/' + item.path.replace(/\.jsx$/, '.js'), item.code]));
const scripts = manifest.scripts.filter(name => !name.endsWith('/main.js') && !name.includes('/Process'));
const facts = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
const fixture = `
window.processRailFixture = { facts: ${JSON.stringify(facts).replace(/</g, '\\u003c')}, mode: 'legacy', next: 'legacy', reads: 0, navigations: [] };
function envelope(data) { return {ok:true,schema_version:1,data,meta:{source:'demo',time_basis:'factory_local',snapshot_ref:'component-fixture',request_ref:'fixture',as_of:'2026-09-09T12:00:00'},warnings:[]}; }
const adapter = {readPending:()=>null,
  summary:async()=>{const state=processRailFixture;state.reads++;
    if(state.mode==='failed') throw new Error('Fixture summary failure');
    if(state.mode==='delayed') return new Promise(resolve=>{state.resolve=()=>resolve(envelope(state.facts.ready));});
    const data=JSON.parse(JSON.stringify(state.facts[state.mode] || state.facts.ready));
    if(state.mode==='missing') delete data.readiness.items.process;
    if(state.mode==='malformed') data.readiness.items.process.counts.ready=null;
    if(state.mode==='mismatch') data.readiness.items.process.counts.total=42;
    if(state.mode==='old-placeholder') data.readiness.items.process={status:'unknown',counts:{total:1},issues:[]};
    return envelope(data);
  }, list:async()=>envelope({entities:[],page:{number:1,size:20,total:0,pages:1,sort:[]},create_context:null})};
window.APSResourceAPI={create:()=>({...adapter})};
window.APSProcessAPI={create:()=>({readPending:()=>({fixture:true})})};
window.ProcessWorkspace=({onCommitted})=>React.createElement('button',{id:'fixture-process-commit',onClick:()=>{
  processRailFixture.mode=processRailFixture.next;onCommitted({ok:true,committed:true,result:'committed'});
}},'Fixture process commit');
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(AppShell,
  {active:'process',title:'Process summary callback fixture',theme:document.documentElement.dataset.theme,showCapsule:false,onNav:()=>{}},
  React.createElement(ResourceLive,{onNavigate:key=>processRailFixture.navigations.push(key)})));
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(name => '<link rel="stylesheet" href="/static/' + name + '">').join('') +
  '</head><body class="aps-workbench"><div id="root"></div>' + scripts.map(name => '<script src="/static/' + name + '"></script>').join('') +
  '<script>' + fixture + '</script></body></html>';
const server = http.createServer((req, res) => {
  if (req.url === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (req.url === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  const name = new URL(req.url, 'http://fixture').pathname.slice('/static/'.length);
  if (overrides.has(name)) { res.setHeader('Content-Type', 'application/javascript'); res.end(overrides.get(name)); return; }
  const asset = assets.get(name);
  if (!asset) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
const report = { scope: 'source-only-ResourceLive-callback-mock-with-service-facts', checks: 0, cases: [], errors: [], external: [],
  build_id: manifest.build_id, manifest_sha256: hash(manifestBytes), sources: sources.map(item => ({ path: item.path, sha256: hash(item.code) })) };
function check(value, message) { report.checks++; assert(value, message); }
async function commit(page, mode, wait = true) {
  const before = await page.evaluate(mode => { processRailFixture.next = mode; return processRailFixture.reads; }, mode);
  await page.locator('#fixture-process-commit').click();
  await page.waitForFunction(before => processRailFixture.reads > before, before);
  if (wait) await page.waitForFunction(() => document.querySelector('.rail').getAttribute('aria-busy') === 'false');
}
async function inspect(page) {
  const value = await page.evaluate(() => {
    const rail = document.querySelector('.rail');
    const nodes = Array.from(rail.querySelectorAll('.hb-tmeta,.hb-tname,.hb-r-tag,.hb-rl2,.hb-cl2'));
    const overflow = nodes.filter(node => node.scrollWidth > node.clientWidth + 1).map(node => node.textContent);
    const boxes = Array.from(rail.querySelectorAll('.hb-hub > .hb-block')).map(node => {
      const r = node.getBoundingClientRect(); return { left:r.left, right:r.right, top:r.top, bottom:r.bottom };
    });
    return { overflow, boxes, scroll: document.documentElement.scrollWidth, width: innerWidth };
  });
  check(value.overflow.length === 0, JSON.stringify(value));
  check(value.scroll <= value.width + 1, JSON.stringify(value));
  for (let i = 0; i < value.boxes.length; i++) for (let j = i + 1; j < value.boxes.length; j++) {
    const a = value.boxes[i], b = value.boxes[j];
    check(Math.min(a.right,b.right)-Math.max(a.left,b.left)<1 || Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)<1, 'Rail sections overlap');
  }
  return value;
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); check(report.browser.startsWith('109.'), 'Actual Chromium 109 required');
    const origin = 'http://127.0.0.1:' + server.address().port;
    for (const viewport of [{width:1920,height:1080}, {width:1392,height:924}]) for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({ viewport });
      await context.addInitScript(theme => { localStorage.setItem('aps_theme',theme); localStorage.setItem('aps_kit_theme',theme); }, theme);
      const page = await context.newPage();
      page.on('pageerror', error => report.errors.push(error.message));
      page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      await page.goto(origin);
      await page.locator('#fixture-process-commit').waitFor();
      await page.waitForFunction(() => document.querySelector('.rail').getAttribute('aria-busy') === 'false');
      await page.evaluate(() => document.fonts.ready);
      const tile = page.locator('[data-rail-node="process"]');
      check((await tile.innerText()).includes('存量 1 项未确认；含路线资料 1 项'), 'Legacy evidence must not become confirmation');
      for (const mode of ['route','source','hours','ready','mixed','stale','empty','unavailable']) {
        await commit(page, mode);
        const item = facts[mode].readiness.items.process, counts = item.counts, text = await tile.innerText();
        check(text.includes(item.status === 'unavailable' ? '工艺阶段暂无数据' : item.status === 'zero' ? '暂无零件' : '工艺已确认 ' + counts.ready + ' / ' + counts.total + ' 项'), mode + ': ' + text);
        if (!['unavailable','zero'].includes(item.status)) {
          check(text.includes('待路线 ' + counts.route + ' / 待归属 ' + counts.source + ' / 待工时 ' + counts.hours), mode);
          check(text.includes('已确认：路线 ' + counts.route_confirmed + ' / 归属 ' + counts.source_confirmed + ' / 工时 ' + counts.hours_confirmed), mode);
        }
        check(await page.locator('.hb-rl2').innerText() === '暂无数据', 'Process confirmation is not scheduling readiness');
        check((await page.locator('.rail-foot').innerText()).includes('静态资料不是排产检查'), 'Static boundary must remain visible');
        check(await page.locator('.hb-r-floor i').count() === 0, 'No invented percentage');
        check(!text.includes('阶段未知') && !text.includes('100%'), 'No obsolete placeholder or vacuous ratio');
        if (mode === 'ready' || mode === 'mixed') {
          const geometry = await inspect(page);
          const screenshot = viewport.width + '-' + theme + '-' + mode + '.png';
          await page.locator('.rail').screenshot({ path: path.join(output, screenshot) });
          if (mode === 'mixed') report.cases.push({ viewport, theme, geometry, screenshot });
        }
      }
      for (const mode of ['missing','malformed','mismatch','old-placeholder','failed']) {
        await commit(page, mode);
        check((await tile.innerText()).includes('工艺阶段暂无数据'), mode);
        check(!(await tile.innerText()).includes('工艺已确认'), mode);
      }
      await commit(page, 'delayed', false);
      check((await tile.innerText()).includes('工艺阶段未读取'), 'Refresh must not retain old confirmation counts');
      await page.evaluate(() => processRailFixture.resolve());
      await page.waitForFunction(() => document.querySelector('.rail').getAttribute('aria-busy') === 'false');
      check((await tile.innerText()).includes('工艺已确认 1 / 1 项'), 'Successful callback refresh reaches new facts');
      await page.getByRole('button', { name: '下一步 · 批次管理' }).click();
      check((await page.evaluate(() => processRailFixture.navigations)).includes('batches'), 'Batch navigation preserved');
      await context.close();
    }
    check(report.errors.length === 0, JSON.stringify(report.errors));
    check(report.external.length === 0, JSON.stringify(report.external));
    check(hash(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json'))) === report.manifest_sha256, 'Published manifest must remain untouched');
  } catch (error) { report.failure = error.stack || String(error); process.exitCode = 1; }
  finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(output, 'component-result.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ ...report, output }));
  }
})();
