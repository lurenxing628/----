/* Isolated real React input fixtures. No database, production persistence or Win7 hardware proof. */
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
const sourcePaths = ['WorkbenchControlBridge.js','WorkbenchControlStyles.jsx','WorkbenchNumberControls.jsx'].map(file=>'frontend/workbench/app/'+file);
const sources = sourcePaths.map(file=>({path:file,code:fs.readFileSync(path.join(root,file),'utf8')}));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources, check_combined: true }).outputs.map(item=>item.code).join('\n;\n');
const assets = new Map(manifest.files.map(asset => [asset.path, asset]));
const fixtureCSS = `
body.aps-workbench{margin:0;background:var(--ui-bg);color:var(--ui-text);font:14px 'Microsoft YaHei',Arial,sans-serif;letter-spacing:0}
main{padding:24px;max-width:1180px;margin:auto}h1{font-size:20px;margin:0 0 20px}form{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
.fixture-field{display:flex;flex-direction:column;gap:6px;min-width:0}.fixture-field input{box-sizing:border-box;width:100%;height:34px;padding:6px 9px;border:1px solid #aebbc9;background:#fff;color:#172033;border-radius:3px;font:inherit}
body.aps-workbench .fixture-field[hidden]{display:none !important}
.pair{grid-column:span 2;display:grid;grid-template-columns:1fr 1fr;gap:14px}.pair input{height:40px}.wide{grid-column:1/-1}fieldset{border:0;padding:0;margin:0}.fixture-positioned{position:absolute;left:0;right:0}.position-wrap{position:relative;height:60px}
`;
const fixture = `
window.fixture={changes:[],submits:0,native:[],serial:0};
const h=React.createElement; let appRoot, controlsRoot;
const originalNodes=new Map();
function Harness({spec}) {
  const [values,setValues]=React.useState(Object.fromEntries(spec.inputs.map(item=>[item.id,item.value===undefined?'':item.value])));
  const [patch,setPatch]=React.useState({}), [removed,setRemoved]=React.useState([]);
  window.changeFixture=(id,value)=>setValues(current=>({...current,[id]:value}));
  window.patchFixture=(id,value)=>setPatch(current=>({...current,[id]:{...current[id],...value}}));
  window.removeFixture=id=>setRemoved(current=>current.concat(id));
  window.restoreFixture=id=>setRemoved(current=>current.filter(item=>item!==id));
  function field(item) {
    const config={...item,...patch[item.id]}, input=h('input',{...config.attrs,id:item.id,key:item.id,type:'number',value:values[item.id],min:config.min,max:config.max,step:config.step,
      readOnly:config.readOnly,disabled:config.disabled,'aria-label':config.ariaLabel,className:config.inputClass || 'fixture-original',style:config.inputStyle,
      onChange:event=>{fixture.changes.push({id:item.id,value:event.target.value});setValues(current=>({...current,[item.id]:event.target.value}));}});
    if(config.wrapLabel)return h('label',{className:'fixture-field',key:item.id},h('span',null,config.label||item.id),input);
    return h('div',{className:'fixture-field '+(config.className||''),key:item.id,style:config.parentStyle},
      h('label',{htmlFor:item.id},config.label||item.id),input);
  }
  return h('form',{id:'fixture-form',onSubmit:event=>{event.preventDefault();fixture.submits++;}},
    spec.inputs.filter(item=>!removed.includes(item.id)).map(field),
    h('fieldset',{disabled:!!patch.fieldset?.disabled},h('div',{className:'fixture-field'},h('label',{htmlFor:'fieldset-number'},'禁用字段组'),h('input',{id:'fieldset-number',type:'number',defaultValue:'8'}))),
    h('div',{className:'wb-control-popup fixture-field',hidden:true},h('label',{htmlFor:'popup-number'},'日期弹层数字'),h('input',{id:'popup-number',type:'number',defaultValue:'2026'})),
    h('div',{id:'pair',className:'pair fixture-field'},h('label',{htmlFor:'pair-a'},'同行甲'),h('label',{htmlFor:'pair-b'},'同行乙'),
      h('input',{id:'pair-a',type:'number',defaultValue:'2'}),h('input',{id:'pair-b',type:'number',defaultValue:'3'})),
    h('div',{className:'position-wrap'},h('div',{id:'positioned',className:'fixture-field fixture-positioned'},h('label',{htmlFor:'position-number'},'定位字段'),h('input',{id:'position-number',type:'number',defaultValue:'3'}))),
    h('button',{type:'submit',className:'wide wb-control'},'表单提交'));
}
window.mountFixture=spec=>{
  if(controlsRoot){controlsRoot.unmount();controlsRoot=null;}if(appRoot)appRoot.unmount();
  fixture.changes=[];fixture.submits=0;fixture.native=[];originalNodes.clear();
  appRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));ReactDOM.flushSync(()=>appRoot.render(h(Harness,{spec,key:++fixture.serial})));
  document.querySelectorAll('input').forEach(input=>originalNodes.set(input.id,input));
  window.mountControls();
};
window.mountControls=()=>{controlsRoot=ReactDOM.createRoot(document.getElementById('controls-root'));controlsRoot.render(h(React.StrictMode,null,h(WorkbenchControlStyles),h(WorkbenchNumberControls)));};
window.unmountControls=()=>{controlsRoot.unmount();controlsRoot=null;};
window.originalsIntact=()=>Array.from(originalNodes).filter(([id])=>document.getElementById(id)).every(([id,node])=>document.getElementById(id)===node);
document.addEventListener('input',event=>fixture.native.push({type:event.type,id:event.target.id,value:event.target.value}));
document.addEventListener('change',event=>fixture.native.push({type:event.type,id:event.target.id,value:event.target.value}));
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<link rel="icon" href="/static/' + manifest.icon + '"><script src="/static/' + manifest.theme_script + '"></script>' +
  manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') + '<style>' + fixtureCSS + '</style></head>' +
  '<body class="aps-workbench"><main><h1>数字输入控件 · 隔离验证</h1><div id="fixture-root"></div><div id="controls-root"></div></main>' +
  manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'))
    .map(file => '<script src="/static/' + file + '"></script>').join('') + '<script src="/number-controls.js"></script><script>' + fixture + '</script></body></html>';
const server = http.createServer((req, res) => {
  const name = new URL(req.url, 'http://fixture').pathname;
  if (name === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (name === '/number-controls.js') { res.setHeader('Content-Type', 'application/javascript'); res.end(compiled); return; }
  const asset = assets.get(name.slice('/static/'.length));
  if (!name.startsWith('/static/') || !asset) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', asset.mime); res.end(fs.readFileSync(path.join(root, 'static', asset.path)));
});
const result = { scope: 'isolated-react-component', production_persistence_tested: false, win7_hardware_tested: false,
  css_scope: 'current source WorkbenchControlStyles and WorkbenchControlBridge; global host not mounted',
  sources: sources.map(item=>({path:item.path,sha256:crypto.createHash('sha256').update(item.code).digest('hex')})), cases: [], errors: [], external: [] };
let page, variant;
const up = name => page.getByRole('button', { name: '增加' + name, exact: true });
const down = name => page.getByRole('button', { name: '减少' + name, exact: true });
async function mount(inputs) {
  await page.evaluate(inputs => mountFixture({ inputs }), inputs);
  await page.waitForFunction(() => document.querySelectorAll('.wb-number-stepper').length === document.querySelectorAll('input[type=number]:not(.wb-control-popup input)').length);
}
async function value(id, expected) {
  await page.waitForFunction(({id,expected}) => document.getElementById(id).value === expected, {id,expected});
}
async function run(name, callback) {
  try { await callback(); result.cases.push({ variant, name, passed: true }); }
  catch (error) { result.cases.push({ variant, name, passed: false, message: error.message }); await page.screenshot({ path: path.join(output, variant + '-' + name + '-failure.png') }); throw error; }
}
async function screenshot(name) {
  await page.evaluate(() => document.fonts.ready);
  const geometry = await page.evaluate(() => Array.from(document.querySelectorAll('.wb-number-stepper')).map(stepper => {
    const box = stepper.getBoundingClientRect(), inputs = Array.from(stepper.parentElement.querySelectorAll(':scope > input'));
    const input = inputs.find(input => { const r = input.getBoundingClientRect(); return Math.abs(r.right - box.right) < 2 && Math.abs(r.top - box.top) < 2; });
    return { matched: !!input, width: box.width, height: box.height, visible: box.width > 0 && box.height > 0, input: input?.id };
  }));
  assert(geometry.every(item => item.matched && item.width >= 18 && item.width <= 22 && item.height >= 20), 'buttons remain inside their own input');
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'no document overflow');
  const file = variant + '-' + name + '.png'; await page.screenshot({ path: path.join(output, file), fullPage: true });
  result.cases.push({ variant, name: name + '-visual', screenshot: file, geometry, passed: true });
}
async function cases() {
  await run('mount-preserves-original', async () => {
    await mount([{id:'quantity',label:'库存数量',value:'0',min:'0',max:'9',step:'1'}, {id:'decimal',label:'每日工时',value:'0.1',step:'0.1'},
      {id:'negative',label:'偏差',value:'-3.5',step:'0.5'}, {id:'readonly',label:'只读数量',value:'7',readOnly:true},
      {id:'disabled',label:'停用数量',value:'9',disabled:true}, {id:'blank',label:'待录数量',value:'',step:'any'}]);
    assert(await page.evaluate(() => originalsIntact()));
    assert.deepEqual(await page.evaluate(() => fixture.changes), []);
    assert.equal(await page.locator('#quantity').inputValue(), '0'); assert.equal(await page.locator('#blank').inputValue(), '');
    assert.equal(await page.locator('.wb-control-popup .wb-number-stepper').count(), 0);
    assert.equal(await page.locator('#popup-number').isVisible(),false);
    assert.equal(await page.locator('#positioned').evaluate(el => getComputedStyle(el).position), 'absolute');
    assert(await up('只读数量').isDisabled()); assert(await down('停用数量').isDisabled());
    await screenshot('initial');
  });
  await run('controlled-value-and-native-events', async () => {
    await up('库存数量').click(); await value('quantity','1'); await down('库存数量').click(); await value('quantity','0');
    assert(await down('库存数量').isDisabled());
    assert.deepEqual(await page.evaluate(() => fixture.changes), [{id:'quantity',value:'1'},{id:'quantity',value:'0'}]);
    assert.deepEqual(await page.evaluate(() => fixture.native.map(event=>event.type)), ['input','change','input','change']);
    assert.equal(await page.evaluate(() => fixture.submits),0); assert(await page.evaluate(() => originalsIntact()));
  });
  await run('decimal-negative-and-keyboard', async () => {
    await up('每日工时').click({clickCount:1}); await value('decimal','0.2');
    await up('每日工时').click(); await value('decimal','0.3'); await down('每日工时').click(); await value('decimal','0.2');
    await down('偏差').click(); await value('negative','-4'); await up('偏差').click(); await value('negative','-3.5');
    await page.locator('#decimal').fill('2.4'); await page.locator('#decimal').press('ArrowUp'); await value('decimal','2.5');
    await up('每日工时').focus(); await up('每日工时').press('Space'); await value('decimal','2.6');
    assert.equal(await page.evaluate(() => fixture.submits),0);
  });
  await run('step-any-precision-and-bounds', async () => {
    await mount([{id:'any',label:'任意精度',value:'0.1234',step:'any'}, {id:'bound',label:'任意步长边界',value:'0.3',step:'any',min:'0.2',max:'1.4'}]);
    await up('任意精度').click(); await value('any','1.1234'); await down('任意精度').click(); await value('any','0.1234');
    await up('任意步长边界').click(); await value('bound','1.3'); await up('任意步长边界').click(); await value('bound','1.4');
    assert(await up('任意步长边界').isDisabled()); await down('任意步长边界').click(); await value('bound','0.4');
    await down('任意步长边界').click(); await value('bound','0.2'); assert(await down('任意步长边界').isDisabled());
  });
  await run('native-step-base-scientific-empty', async () => {
    await mount([{id:'base',label:'非零基数',value:'0.4',min:'0.3',step:'0.2'}, {id:'science',label:'科学计数',value:'1e-7',step:'1e-7'},
      {id:'empty',label:'空值',value:'',min:'3',max:'9',step:'2'}, {id:'reversed',label:'矛盾边界',value:'5',min:'10',max:'1',step:'any'}]);
    await up('非零基数').click(); await value('base','0.5'); await up('科学计数').click();
    assert.equal(await page.locator('#science').evaluate(el=>el.valueAsNumber),2e-7);
    const expected = await page.locator('#empty').evaluate(input=>{const p=document.createElement('input');p.type='number';p.min=input.min;p.max=input.max;p.step=input.step;p.value='';p.stepUp();return p.value;});
    await up('空值').click(); await value('empty',expected); assert(await up('矛盾边界').isDisabled()); assert(await down('矛盾边界').isDisabled());
  });
  await run('bad-input-keeps-edit-buffer', async () => {
    await mount([{id:'bad',label:'未输完整',value:'',step:'any'}]);
    await page.locator('#bad').focus(); await page.locator('#bad').type('1e');
    assert(await page.locator('#bad').evaluate(el=>el.validity.badInput));
    await page.waitForFunction(()=>document.querySelector('#bad').parentElement.querySelectorAll('button:disabled').length===2);
    const before = await page.evaluate(()=>fixture.changes.length);
    await page.waitForTimeout(100); assert.equal(await page.evaluate(()=>fixture.changes.length),before);
    assert(await page.locator('#bad').evaluate(el=>el.validity.badInput));
    await page.locator('#bad').fill(''); await page.locator('#bad').type('1e999');
    assert(await up('未输完整').isDisabled()); assert(await down('未输完整').isDisabled());
    await page.locator('#bad').fill('2'); await up('未输完整').click(); await value('bad','3');
  });
  await run('dynamic-disabled-constraints-and-label', async () => {
    await mount([{id:'dynamic',label:'可变字段',value:'4',min:'0',max:'5',step:'1'}]);
    await page.evaluate(()=>patchFixture('dynamic',{disabled:true})); await page.waitForFunction(()=>document.querySelector('#dynamic').parentElement.querySelectorAll('button:disabled').length===2);
    await page.evaluate(()=>patchFixture('dynamic',{disabled:false,readOnly:true})); assert(await up('可变字段').isDisabled());
    await page.evaluate(()=>patchFixture('dynamic',{readOnly:false,max:'4',label:'新字段名'}));
    await up('新字段名').waitFor(); assert(await up('新字段名').isDisabled()); await down('新字段名').click(); await value('dynamic','3');
    await page.evaluate(()=>patchFixture('fieldset',{disabled:true})); await page.waitForFunction(()=>document.querySelector('#fieldset-number').parentElement.querySelectorAll('button:disabled').length===2);
    await page.evaluate(()=>patchFixture('fieldset',{disabled:false})); await up('禁用字段组').click(); await value('fieldset-number','9');
  });
  await run('shared-parent-label-and-no-form-submit', async () => {
    await up('同行甲').click(); await value('pair-a','3'); await down('同行乙').click(); await value('pair-b','2');
    assert.equal(await page.locator('#pair > .wb-number-stepper').count(),2);
    await page.locator('label[for="pair-a"]').click(); assert(await page.locator('#pair-a').evaluate(el=>document.activeElement===el));
    assert.equal(await page.evaluate(()=>fixture.submits),0); await screenshot('shared-parent');
  });
  await run('react-rerender-removal-and-remount', async () => {
    await page.evaluate(()=>changeFixture('dynamic','1')); await down('新字段名').click(); await value('dynamic','0');
    assert(await page.evaluate(()=>originalsIntact()));
    await page.evaluate(()=>removeFixture('dynamic')); await page.waitForFunction(()=>!document.querySelector('#dynamic'));
    assert.equal(await page.getByRole('button',{name:'增加新字段名',exact:true}).count(),0);
    await page.evaluate(()=>restoreFixture('dynamic')); await up('新字段名').click(); await value('dynamic','1');
    await page.evaluate(()=>unmountControls()); assert.equal(await page.locator('.wb-number-stepper').count(),0);
    assert.equal(await page.locator('#pair.wb-number-parent').count(),0); assert.equal(await page.locator('#dynamic.wb-number-input').count(),0);
    assert.equal(await page.locator('#positioned').getAttribute('style'),null);
    assert.equal(await page.locator('#positioned').evaluate(el=>getComputedStyle(el).position),'absolute');
    await page.evaluate(()=>mountControls()); await up('新字段名').click(); await value('dynamic','2');
  });
  await run('owned-classes-and-native-validation', async () => {
    await mount([{id:'preserved',label:'原有标记',value:'3',inputClass:'keep wb-number-input',className:'wb-number-parent wb-number-parent-static keep-parent',attrs:{required:true,'aria-describedby':'hint'}}]);
    await page.locator('#preserved').evaluate(input=>input.setCustomValidity('原有业务校验'));
    await up('原有标记').click(); await value('preserved','4'); assert.equal(await page.locator('#preserved').evaluate(el=>el.validationMessage),'原有业务校验');
    await page.evaluate(()=>unmountControls()); assert.equal(await page.locator('#preserved').getAttribute('class'),'keep wb-number-input');
    assert(await page.locator('#preserved').evaluate(el=>el.parentElement.classList.contains('keep-parent')&&el.parentElement.classList.contains('wb-number-parent-static')));
    assert.equal(await page.locator('#preserved').getAttribute('aria-describedby'),'hint');
    await page.evaluate(()=>mountControls()); await up('原有标记').waitFor();
  });
  await run('body-scope-and-layout-resize', async () => {
    await page.evaluate(()=>document.body.classList.remove('aps-workbench'));
    await page.waitForFunction(()=>document.querySelectorAll('.wb-number-stepper').length===0);
    await page.evaluate(()=>document.body.classList.add('aps-workbench')); await up('原有标记').waitFor();
    await page.locator('main').evaluate(el=>el.style.width='800px'); await page.waitForTimeout(100); await screenshot('resized');
  });
  await run('wrapped-label-popup-reclassification-and-hidden', async () => {
    await mount([{id:'wrapped',label:'内嵌标签字段',value:'0',wrapLabel:true}]);
    await up('内嵌标签字段').click(); await value('wrapped','1'); assert.equal(await page.evaluate(()=>fixture.changes.length),1);
    await page.locator('#wrapped').evaluate(input=>input.parentElement.classList.add('wb-control-popup'));
    await page.waitForFunction(()=>!document.querySelector('#wrapped').parentElement.querySelector('.wb-number-stepper'));
    assert.equal(await page.locator('#wrapped').inputValue(),'1');
    await page.locator('#wrapped').evaluate(input=>input.parentElement.classList.remove('wb-control-popup'));
    await down('内嵌标签字段').click(); await value('wrapped','0');
    await page.locator('#wrapped').evaluate(input=>input.parentElement.hidden=true);
    await page.waitForFunction(()=>document.querySelector('#wrapped').parentElement.querySelector('.wb-number-stepper').style.display==='none');
    await page.locator('#wrapped').evaluate(input=>input.parentElement.hidden=false); await up('内嵌标签字段').click(); await value('wrapped','1');
    assert.equal(await page.evaluate(()=>fixture.submits),0);
  });
  await run('uncontrolled-reset-retains-native-default', async () => {
    await up('同行甲').click(); await value('pair-a','3');
    await page.locator('#fixture-form').evaluate(form=>form.reset()); await value('pair-a','2');
    await down('同行甲').click(); await value('pair-a','1');
    assert.equal(await page.locator('#pair-a').getAttribute('value'),'2');
  });
  await run('two-hundred-inputs-one-live-control-each', async () => {
    const start=Date.now();
    await mount(Array.from({length:200},(_,index)=>({id:'many-'+index,label:'批量数值'+index,value:String(index),step:'any'})));
    const elapsed=Date.now()-start;
    assert.equal(await page.locator('.wb-number-stepper').count(),204);
    await up('批量数值199').click(); await value('many-199','200');
    assert.equal(await page.evaluate(()=>fixture.changes.length),1); assert(await page.evaluate(()=>originalsIntact()));
    await page.evaluate(()=>{for(let index=0;index<200;index++)changeFixture('many-'+index,String(index+1));});
    await value('many-100','101'); await down('批量数值100').click(); await value('many-100','100');
    assert.equal(await page.locator('.wb-number-stepper').count(),204);
    result.cases.push({variant,name:'two-hundred-mount-timing',milliseconds:elapsed,passed:true,win7_performance_proof:false});
  });
  await run('observer-settles-without-portal-loop', async () => {
    const count=await page.evaluate(async()=>{let count=0;const observer=new MutationObserver(rows=>count+=rows.length);observer.observe(document.body,{attributes:true,childList:true,subtree:true});await new Promise(resolve=>setTimeout(resolve,300));observer.disconnect();return count;});
    assert(count<12,'idle portal mutation loop: '+count);
    assert.equal(await page.evaluate(()=>fixture.submits),0);
  });
  await run('explicit-increment-keeps-arbitrary-validity', async () => {
    await mount([{id:'custom',label:'独立微调',value:'8.375',step:'any',min:'0',max:'24',attrs:{'data-wb-step':'0.5'}}]);
    assert.equal(await page.locator('#custom').getAttribute('step'),'any');
    assert.equal(await page.locator('#custom').evaluate(input=>input.validity.stepMismatch),false);
    assert.deepEqual(await page.evaluate(()=>fixture.changes),[]);
    await up('独立微调').click(); await value('custom','8.875');
    await page.locator('#custom').press('ArrowDown'); await value('custom','8.375');
    await page.locator('#custom').press('ArrowUp'); await value('custom','8.875');
    await down('独立微调').click(); await value('custom','8.375');
    await page.evaluate(()=>patchFixture('custom',{attrs:{'data-wb-step':'5'}}));
    await up('独立微调').click(); await value('custom','13.375');
    assert(await page.evaluate(()=>originalsIntact())); assert.equal(await page.evaluate(()=>fixture.submits),0);
  });
  await run('explicit-increment-empty-bad-input-and-popup', async () => {
    await mount([{id:'custom',label:'空白微调',value:'',step:'any',attrs:{'data-wb-step':'0.5'}}]);
    assert(await up('空白微调').isDisabled()); assert(await down('空白微调').isDisabled());
    await page.locator('#custom').press('ArrowUp'); await value('custom','');
    assert.deepEqual(await page.evaluate(()=>fixture.changes),[]);
    await page.locator('#custom').type('1e'); await page.locator('#custom').press('ArrowDown');
    assert(await page.locator('#custom').evaluate(input=>input.validity.badInput));
    await page.locator('#custom').fill('0'); await up('空白微调').click(); await value('custom','0.5');
    await page.locator('#custom').evaluate(input=>input.parentElement.classList.add('wb-control-popup'));
    await page.waitForFunction(()=>!document.querySelector('#custom').parentElement.querySelector('.wb-number-stepper'));
    await page.locator('#custom').press('ArrowUp'); await value('custom','1.5');
    await page.locator('#custom').evaluate(input=>input.parentElement.classList.remove('wb-control-popup'));
    await down('空白微调').click(); await value('custom','1');
  });
}
(async () => {
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin='http://127.0.0.1:'+server.address().port;
  const executablePath=process.env.WORKBENCH_BROWSER;
  if(!executablePath)throw new Error('Set WORKBENCH_BROWSER to actual Chromium 109');
  let browser;
  try {
    browser=await chromium.launch({executablePath,headless:true}); result.browser=browser.version(); assert.match(result.browser,/^109\./);
    for(const viewport of [{width:1920,height:1080},{width:1392,height:924}]) for(const theme of ['light','dark']) {
      variant=viewport.width+'x'+viewport.height+'-'+theme;
      const context=await browser.newContext({viewport,acceptDownloads:false});
      await context.addInitScript(theme=>{localStorage.setItem('aps_theme',theme);localStorage.setItem('aps_kit_theme',theme);},theme);
      page=await context.newPage();
      page.on('pageerror',error=>result.errors.push({variant,message:error.message}));
      page.on('console',message=>{if(message.type()==='error')result.errors.push({variant,message:message.text()});});
      await page.route('**/*',route=>{if(!route.request().url().startsWith(origin+'/')){result.external.push(route.request().url());return route.abort();}return route.continue();});
      await page.goto(origin,{waitUntil:'load'});
      assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),theme);
      await cases(); await context.close();
    }
    assert.deepEqual(result.errors,[]); assert.deepEqual(result.external,[]);
    result.passed=true;
  } finally {
    if(browser)await browser.close(); await new Promise(resolve=>server.close(resolve));
    fs.writeFileSync(path.join(output,'number-result.json'),JSON.stringify(result,null,2));
  }
  console.log(JSON.stringify({passed:result.passed,browser:result.browser,cases:result.cases.length,output}));
})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
