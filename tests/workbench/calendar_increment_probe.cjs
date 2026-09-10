/* WBP-PROC-024: real controlled CalendarFields, without HTTP or database writes. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass an artifact directory');
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const files = ['resource-contract.js', 'ResourceControls.jsx', 'CalendarContract.js', 'CalendarFields.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchNumberControls.jsx'];
const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
const code = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources, check_combined: true }).outputs.map(item => item.code).join('\n;\n');
const assets = new Map(manifest.files.map(item => [item.path, item]));
const fixture = `
const h=React.createElement;
window.fixture={changes:[],payloads:[],submits:0,errors:[],serial:0};
let appRoot,controlsRoot;
function Harness({spec}) {
  const original=React.useMemo(()=>({explicit:true,fields:{type:'work',hours:8.375,eff:62.5,allowNormal:'yes',allowUrgent:'no',note:'保留原有精度',...spec.fields}}),[]);
  const [draft,setDraft]=React.useState(()=>APSCalendarContract.draft(original));
  const [disabled,setDisabled]=React.useState(false),[visible,setVisible]=React.useState(true),[error,setError]=React.useState(null);
  fixture.draft=draft;fixture.original=original;fixture.disable=setDisabled;fixture.show=setVisible;
  const change=value=>{fixture.changes.push({...value});setDraft(value);setError(null);};
  return h('div',{className:'plana'},h('h1',null,'日历微调验证'),
    h('div',{id:'fixture-scroll',style:{overflowY:'auto',maxHeight:spec.nested?'240px':'none'}},
      h('form',{id:'calendar-fixture',className:'modal lg',style:{width:'min(900px,100%)',maxHeight:'none',margin:'0 auto'},onSubmit:event=>{
        event.preventDefault();fixture.submits++;try{fixture.payloads.push(APSCalendarContract.input(draft,original));setError(null);}catch(error){fixture.errors.push(error);setError(error);}}},
        h('div',{className:'modal-b form'},visible&&h(CalendarFields.Fields,{value:draft,onChange:change,disabled,error})),
        h('div',{className:'modal-f'},h('button',{type:'submit',className:'btn primary'},'保存配置')))));
}
window.mountControls=()=>{controlsRoot=ReactDOM.createRoot(document.getElementById('controls-root'));controlsRoot.render(h(React.StrictMode,null,h(WorkbenchControlStyles),h(WorkbenchNumberControls)));};
window.unmountControls=()=>{controlsRoot.unmount();controlsRoot=null;};
window.mountFixture=spec=>{
  if(controlsRoot)unmountControls();if(appRoot)appRoot.unmount();fixture.changes=[];fixture.payloads=[];fixture.submits=0;fixture.errors=[];
  appRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));
  ReactDOM.flushSync(()=>appRoot.render(h(Harness,{spec,key:++fixture.serial})));
  fixture.originalInputs=Array.from(document.querySelectorAll('input[type=number]'));mountControls();window.scrollTo(0,0);
};
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<link rel="icon" href="/static/' + manifest.icon + '"><script src="/static/' + manifest.theme_script + '"></script>' +
  manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '<style>body.aps-workbench{margin:0;background:var(--ui-bg);color:var(--ui-text)}main{padding:24px;min-height:2300px;box-sizing:border-box}h1{font-size:20px;margin:0 0 20px}#fixture-scroll{max-width:1100px;margin:auto}</style></head>' +
  '<body class="aps-workbench"><main><div id="fixture-root"></div><div id="controls-root"></div></main>' +
  manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'))
    .map(file => '<script src="/static/' + file + '"></script>').join('') + '<script src="/calendar-fixture.js"></script><script>' + fixture + '</script></body></html>';
const server = http.createServer((req, res) => {
  const name = new URL(req.url, 'http://fixture').pathname;
  if (name === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (name === '/calendar-fixture.js') { res.setHeader('Content-Type', 'application/javascript'); res.end(code); return; }
  const asset = assets.get(name.slice('/static/'.length));
  if (!name.startsWith('/static/') || !asset) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', asset.mime); res.end(fs.readFileSync(path.join(root, 'static', asset.path)));
});
const result = { issue: 'WBP-PROC-024', scope: 'controlled-CalendarFields-current-source', production_persistence_tested: false, win7_hardware_tested: false,
  sources: sources.map(item => ({ path: item.path, sha256: crypto.createHash('sha256').update(item.code).digest('hex') })), cases: [], errors: [], external: [], wheel: [] };
let page, variant;
const input = kind => page.locator('input[name="' + kind + '"]');
const label = kind => kind === 'hours' ? '可排工时（小时）' : '效率（%）';
const up = kind => page.getByRole('button', { name: '增加' + label(kind), exact: true });
const down = kind => page.getByRole('button', { name: '减少' + label(kind), exact: true });
async function value(kind, expected) {
  await page.waitForFunction(({kind,expected}) => document.querySelector('input[name="'+kind+'"]').value === expected, {kind,expected});
  assert.equal(await input(kind).evaluate(el => el.validity.stepMismatch), false);
}
async function mount(spec = {}) {
  await page.evaluate(spec => mountFixture(spec), spec);
  await page.waitForFunction(() => document.querySelectorAll('.wb-number-stepper').length === 2);
  await up('hours').waitFor();
}
async function run(name, fn) {
  try { await fn(); result.cases.push({variant,name,passed:true}); }
  catch(error) {
    const state=await page.evaluate(()=>({scrollY,focused:document.activeElement.name,draft:fixture.draft,
      localScroll:document.getElementById('fixture-scroll').scrollTop,changes:fixture.changes}));
    result.cases.push({variant,name,passed:false,message:error.message,state});
    await page.screenshot({path:path.join(output,variant+'-'+name+'-failure.png')}); throw error;
  }
}
async function shot(name) {
  await page.evaluate(() => document.fonts.ready);
  const geometry = await page.evaluate(() => ({ width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
    steppers:Array.from(document.querySelectorAll('.wb-number-stepper')).map(el => {
      const b=el.getBoundingClientRect(),i=el.parentElement.querySelector('input').getBoundingClientRect();
      return {width:b.width,top:b.top,inputTop:i.top,right:b.right,inputRight:i.right,bottom:b.bottom,inputBottom:i.bottom};}) }));
  assert(geometry.scrollWidth <= geometry.width);
  assert(geometry.steppers.every(b => b.width >= 18 && b.width <= 22 && Math.abs(b.top-b.inputTop)<2 && Math.abs(b.right-b.inputRight)<2 && b.bottom<=b.inputBottom));
  const file=variant+'-'+name+'.png'; await page.screenshot({path:path.join(output,file)}); result.cases.push({variant,name:name+'-visual',passed:true,screenshot:file,geometry});
}
async function cases() {
  await run('untouched-facts-and-validity', async () => {
    await mount(); await value('hours','8.375'); await value('eff','62.5');
    assert.equal(await input('hours').getAttribute('step'),'any'); assert.equal(await input('eff').getAttribute('step'),'any');
    assert.equal(await input('hours').getAttribute('data-wb-step'),'0.5'); assert.equal(await input('eff').getAttribute('data-wb-step'),'5');
    assert.deepEqual(await page.evaluate(()=>fixture.changes),[]);
    await page.getByRole('button',{name:'保存配置',exact:true}).click();
    assert.deepEqual(await page.evaluate(()=>fixture.payloads),[{}]);
    const created=await page.evaluate(()=>APSCalendarContract.input(fixture.draft,null));
    assert.equal(created.hours,8.375); assert.equal(created.eff,62.5); await shot('original-precision');
  });
  await run('buttons-preserve-offset-decimals', async () => {
    await mount(); await up('hours').click(); await value('hours','8.875'); await down('hours').click(); await value('hours','8.375');
    await up('eff').click(); await value('eff','67.5'); await down('eff').click(); await value('eff','62.5');
    assert.equal(await page.evaluate(()=>fixture.changes.length),4); assert.equal(await page.evaluate(()=>fixture.submits),0);
    assert(await page.evaluate(()=>fixture.originalInputs.every((node,index)=>node===document.querySelectorAll('input[type=number]')[index])));
  });
  await run('arrows-use-same-increments-and-repeat', async () => {
    await mount(); await input('hours').press('ArrowUp'); await value('hours','8.875'); await input('hours').press('ArrowDown'); await value('hours','8.375');
    await input('eff').press('ArrowUp'); await value('eff','67.5'); await input('eff').press('ArrowDown'); await value('eff','62.5');
    await input('hours').focus(); await page.keyboard.down('ArrowUp'); await page.keyboard.down('ArrowUp'); await page.keyboard.up('ArrowUp'); await value('hours','9.375');
    await input('hours').press('ArrowDown'); await value('hours','8.875'); assert.equal(await page.evaluate(()=>fixture.submits),0);
  });
  await run('typed-precision-remains-saveable', async () => {
    await mount(); await input('hours').fill('8.4375'); await input('eff').fill('62.125');
    await page.getByRole('button',{name:'保存配置',exact:true}).click();
    assert.deepEqual(await page.evaluate(()=>fixture.payloads),[{hours:8.4375,eff:62.125}]);
    await up('hours').click(); await value('hours','8.9375'); await up('eff').click(); await value('eff','67.125');
    await shot('incremented-precision');
  });
  await run('zero-and-clamped-boundaries', async () => {
    await mount({fields:{hours:0,eff:0}}); await value('hours','0'); await value('eff','0');
    assert(await down('hours').isDisabled()); assert(await down('eff').isDisabled());
    await up('hours').click(); await value('hours','0.5'); await input('eff').press('ArrowUp'); await value('eff','5');
    await input('hours').fill('23.875'); await input('eff').fill('199.75');
    await up('hours').click(); await value('hours','24'); await input('eff').press('ArrowUp'); await value('eff','200');
    assert(await up('hours').isDisabled()); assert(await up('eff').isDisabled());
    const count=await page.evaluate(()=>fixture.changes.length); await input('hours').press('ArrowUp'); await input('eff').press('ArrowUp');
    assert.equal(await page.evaluate(()=>fixture.changes.length),count);
    await input('hours').press('ArrowDown'); await value('hours','23.5'); await down('eff').click(); await value('eff','195');
    await input('hours').fill('0.125'); await input('eff').fill('2.5');
    await down('hours').click(); await value('hours','0'); await input('eff').press('ArrowDown'); await value('eff','0');
  });
  await run('empty-is-not-zero', async () => {
    await mount(); await input('hours').fill(''); await input('eff').fill('');
    assert(await up('hours').isDisabled()); assert(await down('eff').isDisabled());
    const count=await page.evaluate(()=>fixture.changes.length);
    await input('hours').press('ArrowUp'); await input('eff').press('ArrowDown');
    await value('hours',''); await value('eff',''); assert.equal(await page.evaluate(()=>fixture.changes.length),count);
    await page.getByRole('button',{name:'保存配置',exact:true}).click(); assert.deepEqual(await page.evaluate(()=>fixture.payloads),[]);
    assert.equal(await page.locator('[role=alert]').count(),1); await shot('empty-validation');
  });
  await run('incomplete-and-nonfinite-input-preserved', async () => {
    await mount();
    for(const kind of ['hours','eff']) for(const bad of ['1e','1e999','-']) {
      await input(kind).fill(''); await input(kind).type(bad);
      assert(await input(kind).evaluate(el=>el.validity.badInput));
      const count=await page.evaluate(()=>fixture.changes.length);
      await input(kind).press('ArrowUp'); await input(kind).press('ArrowDown');
      assert(await input(kind).evaluate(el=>el.validity.badInput)); assert.equal(await page.evaluate(()=>fixture.changes.length),count);
      assert(await up(kind).isDisabled()); assert(await down(kind).isDisabled());
    }
    await input('hours').fill('8.375'); await input('eff').fill('62.5'); await up('eff').click(); await value('eff','67.5');
  });
  await run('disabled-readonly-and-rest-state', async () => {
    await mount(); await page.evaluate(()=>fixture.disable(true));
    await page.waitForFunction(()=>document.querySelectorAll('.wb-number-step:disabled').length===4);
    assert.deepEqual(await page.evaluate(()=>fixture.changes),[]);
    await page.evaluate(()=>fixture.disable(false)); await input('hours').evaluate(el=>el.readOnly=true);
    await input('eff').evaluate(el=>el.readOnly=true);
    await page.waitForFunction(()=>document.querySelectorAll('.wb-number-step:disabled').length===4);
    await input('hours').press('ArrowUp'); await input('eff').press('ArrowDown'); await value('hours','8.375'); await value('eff','62.5');
    assert.deepEqual(await page.evaluate(()=>fixture.changes),[]);
    await input('hours').evaluate(el=>el.readOnly=false); await input('eff').evaluate(el=>el.readOnly=false);
    await page.getByRole('button',{name:'休息日',exact:true}).click();
    assert(await input('hours').isDisabled()); assert(await up('eff').isDisabled());
    await page.getByRole('button',{name:'工作日',exact:true}).click(); await value('hours','8.375'); await value('eff','62.5');
    await up('hours').click(); await value('hours','8.875');
  });
  await run('field-and-control-remount-no-duplicate-arrows', async () => {
    await mount(); await up('hours').click(); await value('hours','8.875');
    await page.evaluate(()=>fixture.show(false)); await page.waitForFunction(()=>!document.querySelector('.wb-number-stepper'));
    await page.evaluate(()=>fixture.show(true)); await up('hours').waitFor(); await value('hours','8.875');
    await input('hours').press('ArrowDown'); await value('hours','8.375');
    await page.evaluate(()=>unmountControls()); assert.equal(await page.locator('.wb-number-stepper').count(),0);
    await page.evaluate(()=>mountControls()); await up('hours').waitFor();
    await input('eff').press('ArrowUp'); await value('eff','67.5'); await input('eff').press('ArrowDown'); await value('eff','62.5');
    assert.equal(await page.locator('.wb-number-stepper').count(),2); assert.equal(await page.evaluate(()=>fixture.changes.length),4);
  });
  await run('focused-wheel-scrolls-page-without-editing', async () => {
    await mount(); await input('hours').click(); const before=await input('hours').inputValue();
    await page.mouse.wheel(0,120); await page.waitForFunction(()=>scrollY>0);
    assert.equal(await input('hours').inputValue(),before); assert(await input('hours').evaluate(el=>document.activeElement===el));
    assert.deepEqual(await page.evaluate(()=>fixture.changes),[]);
    await input('eff').click(); const old=await input('eff').inputValue();
    await page.evaluate(()=>window.scrollTo(0,80)); await page.waitForFunction(()=>scrollY===80); await input('eff').hover();
    const scrollBefore=await page.evaluate(()=>scrollY); assert(scrollBefore>0,'upward wheel starts below the top boundary');
    await page.mouse.wheel(0,-40); await page.waitForFunction(before=>scrollY<before,scrollBefore);
    assert.equal(await input('eff').inputValue(),old); assert.deepEqual(await page.evaluate(()=>fixture.changes),[]);
  });
  await run('focused-wheel-keeps-invalid-edit-buffer', async () => {
    await mount(); await input('hours').fill(''); await input('hours').type('1e'); await input('hours').hover();
    const count=await page.evaluate(()=>fixture.changes.length); await page.mouse.wheel(0,120); await page.waitForFunction(()=>scrollY>0);
    assert(await input('hours').evaluate(el=>el.validity.badInput&&document.activeElement===el));
    assert.equal(await page.evaluate(()=>fixture.changes.length),count);
  });
  await run('nested-wheel-scrolls-local-container', async () => {
    await mount({nested:true}); await input('hours').click();
    await page.locator('#fixture-scroll').evaluate(el=>el.scrollTop=0); await input('hours').hover();
    const before=await page.evaluate(()=>({page:scrollY,local:document.getElementById('fixture-scroll').scrollTop}));
    await page.mouse.wheel(0,30);
    await page.waitForFunction(()=>document.getElementById('fixture-scroll').scrollTop>0);
    const after=await page.evaluate(()=>({page:scrollY,local:document.getElementById('fixture-scroll').scrollTop}));
    assert(after.local>before.local,'wheel scrolls the nested container; native chaining may also scroll the page');
    result.wheel.push({variant,kind:'nested-native-scroll',before,after});
    await value('hours','8.375'); await value('eff','62.5');
    assert.deepEqual(await page.evaluate(()=>fixture.changes),[]);
  });
}
(async () => {
  let browser;
  try {
    if (!process.env.WORKBENCH_BROWSER) throw new Error('Set WORKBENCH_BROWSER to actual Chromium 109');
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve)); const origin='http://127.0.0.1:'+server.address().port;
    browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true}); result.browser=browser.version(); assert.match(result.browser,/^109\./);
    for(const viewport of [{width:1920,height:1080},{width:1392,height:924}]) for(const theme of ['light','dark']) {
      variant=viewport.width+'x'+viewport.height+'-'+theme;
      const context=await browser.newContext({viewport}); await context.addInitScript(theme=>{localStorage.setItem('aps_theme',theme);localStorage.setItem('aps_kit_theme',theme);},theme);
      page=await context.newPage(); page.on('pageerror',error=>result.errors.push({variant,message:error.message}));
      page.on('console',message=>{if(message.type()==='error')result.errors.push({variant,message:message.text()});});
      await page.route('**/*',route=>{if(!route.request().url().startsWith(origin+'/')){result.external.push(route.request().url());return route.abort();}return route.continue();});
      await page.goto(origin,{waitUntil:'load'}); assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),theme);
      await cases(); await context.close();
    }
    assert.deepEqual(result.errors,[]); assert.deepEqual(result.external,[]); result.passed=true;
  } finally {
    if(browser)await browser.close(); await new Promise(resolve=>server.close(resolve));
    fs.writeFileSync(path.join(output,'calendar-increment-result.json'),JSON.stringify(result,null,2));
  }
  console.log(JSON.stringify({passed:result.passed,browser:result.browser,cases:result.cases.length,output}));
})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
