'use strict';
// Isolated UI fixture. This verifies input semantics and rendering, not database writes.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass an output directory');
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const records = new Map(manifest.files.map(item => [item.path, item]));
const fixture = `
function Fixture() {
  const [values,setValues]=React.useState({choice:'alpha',date:'2026-09-09',month:'2026-09',time:'08:30',stamp:'2026-09-09T08:30',number:'3.75',check:false,radio:'a',range:'35'});
  const [dialog,setDialog]=React.useState(false),[disabled,setDisabled]=React.useState(false),[removed,setRemoved]=React.useState(false);
  window.controlValues=values;
  const h=React.createElement,change=key=>event=>setValues(v=>({...v,[key]:event.target.type==='checkbox'?event.target.checked:event.target.value}));
  const field=(name,type)=>h('label',{className:'field'},name,h('input',{type,value:values[name],onChange:change(name),'aria-label':name,min:type==='number'?'0':undefined,step:type==='number'?'any':undefined,disabled}));
  const select=h('label',{className:'field'},'选择项',h('select',{'aria-label':'选择项',value:values.choice,onChange:change('choice'),disabled},
    h('option',{value:'alpha'},'Alpha'),h('option',{value:'blocked',disabled:true},'停用选项'),h('option',{value:'beta'},'Beta'),
    h('optgroup',{label:'更多选项'},Array.from({length:70},(_,i)=>h('option',{key:i,value:'item-'+i},'Item '+String(i).padStart(2,'0')+(i===20?' 长名称需要完整显示且不能越出窗口边界的设备组':''))))));
  const content=h('div',{className:'modal-b form',style:{display:'grid',gridTemplateColumns:'repeat(2,minmax(0,1fr))',gap:16}},
    !removed&&select,field('number','number'),field('date','date'),field('month','month'),field('time','time'),field('stamp','datetime-local'),
    h('label',null,h('input',{type:'checkbox','aria-label':'勾选',checked:values.check,onChange:change('check'),disabled}),'勾选'),
    h('div',null,['a','b'].map(value=>h('label',{key:value},h('input',{type:'radio',name:'radio',value,'aria-label':'单选'+value,checked:values.radio===value,onChange:change('radio'),disabled}),value))),
    field('range','range'),h('label',{className:'field'},'附件',h('input',{type:'file','aria-label':'附件',disabled})),
    h('label',{className:'field'},'备注',h('textarea',{'aria-label':'备注',defaultValue:'测试备注',disabled})),
    h('details',null,h('summary',null,'附加设置'),h('p',null,'展开内容')));
  return h(React.Fragment,null,h(WorkbenchControlStyles),h(WorkbenchControls),h(WorkbenchNumberControls),
    h('main',{className:'plana',style:{padding:24,maxWidth:1050,margin:'0 auto'}},h('h2',null,'统一交互控件'),
      h('div',{className:'wb-actions',style:{marginBottom:20}},h('button',{className:'btn primary',onClick:()=>setDialog(true)},'打开编辑'),
        h('button',{className:'btn',onClick:()=>setDisabled(v=>!v)},'切换禁用'),h('button',{className:'btn',onClick:()=>setRemoved(v=>!v)},'移除选择器')),
      dialog?h(ResourceControls.Modal,{title:'控件编辑',icon:'square-pen',onClose:()=>setDialog(false),footer:h('button',{className:'btn',onClick:()=>setDialog(false)},'返回')},content):content,
      h('output',{'data-values':true},JSON.stringify(values))));
}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(Fixture));`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(p => '<link rel="stylesheet" href="/static/' + p + '">').join('') +
  '</head><body class="aps-workbench"><div id="root"></div>' + manifest.scripts.filter(p => !p.endsWith('/main.js')).map(p => '<script src="/static/' + p + '"></script>').join('') + '<script>' + fixture + '</script></body></html>';
const server = http.createServer((req, res) => {
  if (req.url === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  if (req.url === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  const name = new URL(req.url, 'http://fixture').pathname.slice('/static/'.length), record = records.get(name);
  if (!record) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', record.mime); res.end(fs.readFileSync(path.join(root, 'static', name)));
});
const result = { scope:'isolated-React-controlled-fixture', build_id:manifest.build_id, cases:[], screenshots:[], errors:[], external:[] };
async function shot(page, state, name) {
  await page.evaluate(() => document.fonts.ready);
  const file = path.join(output, state + '-' + name + '.png');
  await page.screenshot({ path:file, animations:'disabled' }); result.screenshots.push(file);
  const geometry = await page.evaluate(() => ({ width:innerWidth,height:innerHeight,scroll:document.documentElement.scrollWidth,
    popups:Array.from(document.querySelectorAll('.wb-control-popup')).map(node => {const r=node.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,scroll:node.scrollWidth};}) }));
  assert(geometry.scroll <= geometry.width + 1, JSON.stringify(geometry));
  assert(geometry.popups.every(r => r.left>=0 && r.right<=geometry.width+1 && r.top>=0 && r.bottom<=geometry.height+1 && r.scroll<=r.width+1), JSON.stringify(geometry));
}
async function popup(page, input) {
  const rect = await input.boundingBox(); await input.click({position:{x:rect.width-16,y:rect.height/2}});
  await page.locator('.wb-control-popup').waitFor();
}
(async () => {
  let browser;
  try {
    await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
    const origin='http://127.0.0.1:'+server.address().port;
    browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-background-networking']});
    result.browser=browser.version();assert(result.browser.startsWith('109.'));
    for (const viewport of [{width:1920,height:1080},{width:1392,height:924}]) for (const theme of ['light','dark']) {
      const state=viewport.width+'-'+theme,context=await browser.newContext({viewport});
      await context.addInitScript(value=>{localStorage.setItem('aps_theme',value);localStorage.setItem('aps_kit_theme',value);},theme);
      const page=await context.newPage();page.setDefaultTimeout(10000);
      page.on('pageerror',error=>result.errors.push(error.stack));
      page.on('console',message=>{if(message.type()==='error')result.errors.push(message.text());});
      await page.route('**/*',route=>{if(!route.request().url().startsWith(origin+'/')){result.external.push(route.request().url());return route.abort();}return route.continue();});
      try {
        await page.goto(origin);await page.getByRole('button',{name:'打开编辑',exact:true}).waitFor();
        await page.waitForFunction(()=>document.querySelector('.wb-number-stepper'));
        const appearances=await page.locator('input,select,textarea,button,summary').evaluateAll(nodes=>nodes.map(n=>({tag:n.tagName,type:n.type,appearance:getComputedStyle(n).appearance})));
        assert(appearances.every(row=>row.appearance==='none'),JSON.stringify(appearances));
        await shot(page,state,'all-controls');
        const choice=page.getByRole('combobox',{name:'选择项',exact:true});await choice.click();await page.getByRole('listbox').waitFor();
        const blocked=await page.getByRole('listbox').getByRole('option',{name:'停用选项',exact:true}).boundingBox();
        await page.mouse.click(blocked.x+10,blocked.y+10);assert.equal(await choice.inputValue(),'alpha');
        await shot(page,state,'select-expanded');await page.getByRole('listbox').getByRole('option',{name:'Beta',exact:true}).click();assert.equal(await choice.inputValue(),'beta');
        assert.equal(await page.evaluate(()=>controlValues.choice),'beta');
        await choice.focus();await page.keyboard.press('ArrowDown');await page.keyboard.press('Home');await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');
        assert.equal(await choice.inputValue(),'beta');
        await choice.click();await page.keyboard.press('End');await page.keyboard.press('Enter');assert.equal(await choice.inputValue(),'item-69');
        await choice.click();await page.keyboard.type('Alpha');await page.keyboard.press('Enter');assert.equal(await choice.inputValue(),'alpha');
        await choice.click();await page.keyboard.press('Tab');assert.equal(await page.locator('.wb-control-popup').count(),0);
        await page.getByRole('checkbox',{name:'勾选',exact:true}).check();await page.getByRole('radio',{name:'单选b',exact:true}).check();
        assert.equal(await page.evaluate(()=>controlValues.check),true);assert.equal(await page.evaluate(()=>controlValues.radio),'b');
        await page.getByRole('button',{name:'增加number',exact:true}).click();assert.equal(await page.getByLabel('number',{exact:true}).inputValue(),'4.75');
        await page.getByRole('button',{name:'减少number',exact:true}).click();assert.equal(await page.evaluate(()=>controlValues.number),'3.75');
        await page.getByRole('button',{name:'打开编辑',exact:true}).click();const parent=page.getByRole('dialog',{name:'控件编辑',exact:true});await parent.waitFor();
        await parent.getByLabel('选择项',{exact:true}).click();await page.keyboard.press('Escape');assert(await parent.isVisible());assert.equal(await page.locator('.wb-control-popup').count(),0);
        await popup(page,parent.getByLabel('date',{exact:true}));await shot(page,state,'date-expanded');await page.keyboard.press('Escape');assert(await parent.isVisible());
        await popup(page,parent.getByLabel('date',{exact:true}));await page.locator('.wb-picker-day').filter({hasText:/^15$/}).click();assert.equal(await page.evaluate(()=>controlValues.date),'2026-09-15');
        await parent.getByLabel('date',{exact:true}).fill('2026-09-17');assert.equal(await page.evaluate(()=>controlValues.date),'2026-09-17');
        await popup(page,parent.getByLabel('month',{exact:true}));await shot(page,state,'month-expanded');await page.keyboard.press('Escape');
        await popup(page,parent.getByLabel('time',{exact:true}));await shot(page,state,'time-expanded');
        const minuteUp=page.locator('.wb-control-popup').getByRole('button',{name:'增加分',exact:true});
        await minuteUp.focus();await page.keyboard.press('Enter');assert.equal(await page.locator('.wb-control-popup').getByLabel('分',{exact:true}).inputValue(),'31');
        assert.equal(await page.evaluate(()=>controlValues.time),'08:30');await page.keyboard.press('Escape');
        await popup(page,parent.getByLabel('stamp',{exact:true}));await shot(page,state,'datetime-expanded');
        const confirm=page.locator('.wb-control-popup').getByRole('button',{name:'确定',exact:true});
        const confirmBox=await confirm.boundingBox();assert(confirmBox&&confirmBox.y+confirmBox.height<=viewport.height-7);
        await confirm.click();assert.equal(await page.evaluate(()=>controlValues.stamp),'2026-09-09T08:30');
        await parent.getByLabel('date',{exact:true}).focus();await page.keyboard.press('Alt+ArrowDown');await page.locator('.wb-control-popup').waitFor();
        await page.getByRole('button',{name:'清空',exact:true}).click();assert.equal(await page.evaluate(()=>controlValues.date),'');assert(await parent.isVisible());
        await parent.getByRole('button',{name:'返回',exact:true}).click();await parent.waitFor({state:'detached'});
        await page.getByRole('button',{name:'切换禁用',exact:true}).click();await shot(page,state,'disabled-controls');
        assert(await choice.isDisabled());assert(await page.getByRole('button',{name:'增加number',exact:true}).isDisabled());
        await page.getByRole('button',{name:'切换禁用',exact:true}).click();await choice.click();await page.getByRole('button',{name:'移除选择器',exact:true}).click();
        assert.equal(await page.locator('.wb-control-popup').count(),0);assert.equal(await choice.count(),0);
        result.cases.push({state,viewport,theme,passed:true,custom_select_keyboard_and_mouse:true,parent_modal_escape:true,date_mouse_and_keyboard:true,native_appearance:false});
      } catch(error) { result.cases.push({state,passed:false,error:error.stack});await shot(page,state,'FAILED').catch(()=>{});throw error; }
      finally {await context.close();}
    }
    assert.deepEqual(result.errors,[]);assert.deepEqual(result.external,[]);
  } finally {
    if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));
    fs.writeFileSync(path.join(output,'controls-result.json'),JSON.stringify(result,null,2)+'\n');
  }
  console.log(JSON.stringify({output,browser:result.browser,build_id:result.build_id,cases:result.cases.length,screenshots:result.screenshots.length,errors:result.errors}));
})().catch(error=>{console.error(error);process.exitCode=1;});
