/* Isolated global-style/component checks. No business API, persistence, or Win7 hardware proof. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const output = process.argv[2];
if (!output) throw new Error('Pass an artifact directory');
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const sourcePath = 'frontend/workbench/app/WorkbenchControlStyles.jsx';
const source = fs.readFileSync(path.join(root, sourcePath), 'utf8');
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: [{ path: sourcePath, code: source }], check_combined: true }).outputs[0].code;
const assets = new Map(manifest.files.map(item => [item.path, item]));
const fixture = `
function Fixture() {
  const [styled,setStyled]=React.useState(false),[check,setCheck]=React.useState(false),[state,setState]=React.useState('one');
  const [seg,setSeg]=React.useState('work'),[number,setNumber]=React.useState(8),[range,setRange]=React.useState(40);
  const [menu,setMenu]=React.useState('one'),[day,setDay]=React.useState(9);
  window.applyStyles=setStyled;
  const Button=APSWorkbenchUI.ControlButton;
  return React.createElement(React.Fragment,null,styled&&React.createElement(WorkbenchControlStyles),
    React.createElement('main',{className:'probe-layout'},
      React.createElement('section',{className:'plana probe-main'},
        React.createElement('h2',null,'统一控件样式检查'),
        React.createElement('div',{className:'toolbar'},
          React.createElement('button',{id:'plain-button',className:'btn'},'重新读取'),
          React.createElement('button',{id:'primary-button',className:'btn primary wb-action wb-primary'},'保存设置'),
          React.createElement('button',{id:'danger-button',className:'btn danger'},'删除资料'),
          React.createElement('button',{id:'disabled-button',className:'btn primary wb-primary',disabled:true},'不可操作'),
          React.createElement('button',{id:'mini-button',className:'mini'},'编辑'),
          React.createElement('label',{className:'field'},React.createElement('select',{id:'toolbar-select','aria-label':'工具栏筛选',defaultValue:'all'},React.createElement('option',{value:'all'},'全部状态'),React.createElement('option',{value:'active'},'启用'))),
          React.createElement('label',{className:'search'},React.createElement('span',{className:'ic'},React.createElement(SMIcon,{name:'search'})),React.createElement('input',{id:'search-input',type:'search','aria-label':'搜索资料',placeholder:'编号、名称'}))),
        React.createElement('div',{className:'probe-edit fgrid'},
          React.createElement('label',{className:'field'},'编辑文本',React.createElement('input',{id:'edit-text','aria-label':'编辑文本',defaultValue:'已登记资料'})),
          React.createElement('label',{className:'field'},'编辑选项',React.createElement('select',{id:'edit-select','aria-label':'编辑选项'},React.createElement('option',null,'现有工种名称'),React.createElement('option',null,'较长的工种名称需要完整呈现'))),
          React.createElement('label',{className:'field'},'日期',React.createElement('input',{id:'date',type:'date','aria-label':'日期',defaultValue:'2026-09-09'})),
          React.createElement('label',{className:'field'},'时间',React.createElement('input',{id:'time',type:'time','aria-label':'时间',defaultValue:'08:30'})),
          React.createElement('label',{className:'field'},'月份',React.createElement('input',{id:'month',type:'month','aria-label':'月份',defaultValue:'2026-09'})),
          React.createElement('label',{className:'field'},'工时',React.createElement('span',{className:'wb-number-parent',style:{display:'block'}},
            React.createElement('input',{id:'number',type:'number',step:1,className:'wb-number-input','aria-label':'工时',value:number,onChange:e=>setNumber(e.target.value)}),
            React.createElement('span',{className:'wb-number-stepper'},React.createElement('button',{type:'button',className:'wb-number-step','aria-label':'增加工时',onClick:()=>setNumber(Number(number)+1)},React.createElement('span',{style:{display:'flex',transform:'rotate(180deg)'}},React.createElement(SMIcon,{name:'chevron-down'}))),React.createElement('button',{type:'button',className:'wb-number-step','aria-label':'减少工时',onClick:()=>setNumber(Number(number)-1)},React.createElement(SMIcon,{name:'chevron-down'}))))),
          React.createElement('label',{className:'field'},'只读编号',React.createElement('input',{id:'readonly','aria-label':'只读编号',value:'R-001',readOnly:true})),
          React.createElement('label',{className:'field'},'无效输入',React.createElement('input',{id:'invalid','aria-label':'无效输入','aria-invalid':'true',defaultValue:'待修正'})),
          React.createElement('label',{className:'field full'},'备注',React.createElement('textarea',{id:'textarea','aria-label':'备注',defaultValue:'原始备注保留，不改写业务值。'}))),
        React.createElement('div',{className:'probe-row'},
          React.createElement('label',null,React.createElement('input',{id:'check',type:'checkbox',checked:check,onChange:e=>setCheck(e.target.checked)}),'已核对'),
          React.createElement('label',null,React.createElement('input',{id:'mixed',type:'checkbox',ref:el=>{if(el)el.indeterminate=true;}}),'部分选中'),
          React.createElement('label',null,React.createElement('input',{id:'check-disabled',type:'checkbox',disabled:true,checked:true,readOnly:true}),'已禁用'),
          React.createElement('label',null,React.createElement('input',{id:'radio-one',type:'radio',name:'source',checked:state==='one',onChange:()=>setState('one')}),'当前记录'),
          React.createElement('label',null,React.createElement('input',{id:'radio-two',type:'radio',name:'source',checked:state==='two',onChange:()=>setState('two')}),'历史记录')),
        React.createElement('div',{className:'probe-row'},React.createElement('label',null,'调整比重',React.createElement('input',{id:'range',type:'range',step:5,min:0,max:100,value:range,onChange:e=>setRange(e.target.value)})),React.createElement('output',{id:'range-value'},range),
          React.createElement('input',{id:'file',type:'file','aria-label':'选择文件'})),
        React.createElement('button',{id:'plain-semantic-button',className:'stp'},React.createElement('span',{className:'stp-t'},'普通步骤按钮')),
        React.createElement('div',{className:'seg'},['work','rest'].map(key=>React.createElement('button',{key,'aria-pressed':seg===key,className:seg===key?'on':'',onClick:()=>setSeg(key)},key==='work'?'工作日':'休息日'))),
        React.createElement('details',{id:'details'},React.createElement('summary',null,'生效范围与规则'),React.createElement('p',null,'当前为隔离控件验证，不写入任何业务资料。')),
        React.createElement('div',{className:'pager'},React.createElement('button',{className:'pg','aria-label':'上一页'},React.createElement(SMIcon,{name:'chevron-left'})),React.createElement('span',null,'第 1 / 5 页'),
          React.createElement('label',{className:'field'},React.createElement('input',{id:'jump',type:'number','aria-label':'跳转页码',defaultValue:1,style:{width:74}})),React.createElement('button',{className:'pg','aria-label':'下一页'},React.createElement(SMIcon,{name:'chevron-right'}))),
        React.createElement('section',{className:'sm-workbench probe-system'},React.createElement('h3',null,'系统页现有控件'),
          React.createElement(SMFilters,{kind:'backups',filters:{query:'',type:'',status:'',start:'',end:''},onChange:()=>{},disabled:false}),
          React.createElement('div',{className:'sm-actions'},React.createElement(Button,{id:'ds-button',className:'sm-button'},'公共设计组件'),React.createElement(Button,{id:'ds-disabled',className:'sm-button',disabled:true},'暂不可用'))),
        React.createElement('div',{className:'probe-preserved'},
          React.createElement('button',{id:'nav-row',className:'sm-work-row','data-preserved':'row'},React.createElement('span',null,'维护'),React.createElement('span',null,'整行维护入口'),React.createElement('span',null,'查看')),
          React.createElement('button',{id:'rail',className:'hb-tile int','data-preserved':'rail'},'自制工种导航'),
          React.createElement('button',{id:'cell',className:'cal-cell cfg','data-preserved':'calendar',style:{width:110}},React.createElement('span',{className:'d'},'9'),React.createElement('span',{className:'tag'},'工作日')),
          React.createElement('button',{id:'tab',className:'sm-tab sm-active',role:'tab','data-preserved':'tab'},'概况'),
          React.createElement('button',{id:'bar',className:'tr-bar','data-preserved':'gantt',style:{position:'relative',left:0,top:0,width:160,height:38}},'加工 018'))),
      React.createElement('aside',{className:'probe-popups'},
        React.createElement('section',{className:'wb-control-popup',id:'option-popup',style:{position:'relative'}},
          React.createElement('header',{className:'wb-popup-header'},React.createElement('strong',null,'选择工种')),
          React.createElement('input',{className:'wb-popup-search','aria-label':'搜索选项',placeholder:'搜索工种'}),
          React.createElement('div',{className:'wb-popup-group'},'现有工种'),
          ['one','two','three'].map((key,index)=>React.createElement('button',{className:'wb-popup-option',role:'option','aria-selected':menu===key,'data-active':menu===key,disabled:index===2,key,onClick:()=>setMenu(key)},React.createElement('span',null,['加工中心 M-03','外协检验与精密加工（较长名称完整显示）','历史工种，资料待核实'][index]),menu===key&&React.createElement(SMIcon,{name:'check'}))),
          React.createElement('p',{role:'status'},'无法核实的资料保持可读，不显示假零。'),React.createElement('footer',{className:'wb-popup-footer'},React.createElement('button',{className:'btn'},'关闭'))),
        React.createElement('section',{className:'wb-control-popup',id:'date-popup',style:{position:'relative'}},
          React.createElement('header',{className:'wb-popup-header'},React.createElement('button',{className:'wb-picker-nav','aria-label':'上一月'},React.createElement(SMIcon,{name:'chevron-left'})),React.createElement('strong',null,'2026 年 9 月'),React.createElement('button',{className:'wb-picker-nav','aria-label':'下一月'},React.createElement(SMIcon,{name:'chevron-right'}))),
          React.createElement('div',{className:'wb-picker-grid'},['一','二','三','四','五','六','日'].map(text=>React.createElement('span',{key:text,className:'wb-picker-weekday'},text)),Array.from({length:35},(_,index)=>React.createElement('button',{key:index,className:'wb-picker-day','aria-selected':day===index+1,'aria-current':index===8?'date':undefined,'data-outside':index>29,'aria-disabled':index===0||undefined,disabled:index>29,onClick:()=>{if(index!==0)setDay(index+1);}},index<30?index+1:index-29))),
          React.createElement('div',{className:'wb-picker-fields'},React.createElement('label',null,'小时',React.createElement('input',{type:'number',defaultValue:8})),React.createElement('label',null,'分钟',React.createElement('input',{type:'number',defaultValue:30}))),
          React.createElement('footer',{className:'wb-picker-actions'},React.createElement('button',{className:'btn'},'清除'),React.createElement('button',{className:'btn primary'},'确定'))))));
}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(Fixture));
`;
new (require('node:vm').Script)(fixture, { filename: 'control-style-fixture.js' });
const html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<link rel="icon" href="/static/' + manifest.icon + '">' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '<style>.probe-layout{display:grid;grid-template-columns:minmax(0,1fr) 304px;gap:28px;margin:24px;color:var(--ui-text)}.probe-main{min-width:0}.probe-main h2{font-size:20px;margin:0 0 20px}.probe-row{display:flex;align-items:center;gap:24px;flex-wrap:wrap;margin:18px 0}.probe-row label{display:inline-flex;align-items:center;gap:8px}.probe-edit{padding:18px 0}.probe-popups{display:flex;flex-direction:column;gap:20px}.probe-system{margin:24px 0}.probe-preserved{display:flex;align-items:center;flex-wrap:wrap;gap:12px}.probe-preserved #nav-row{width:100%}.probe-preserved #rail{flex:none;width:210px}.probe-main .toolbar{flex-wrap:wrap}.probe-main .probe-system .sm-actions{margin-top:12px}</style>' +
  '</head><body class="aps-workbench"><div id="root"></div>' +
  manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-')).map(file => '<script src="/static/' + file + '"></script>').join('') +
  '<script src="/styles-fixture.js"></script><script>' + fixture + '</script></body></html>';
const server = http.createServer((request,response) => {
  const name = new URL(request.url,'http://fixture').pathname;
  if (name === '/') { response.setHeader('Content-Type','text/html;charset=utf-8'); response.end(html); return; }
  if (name === '/styles-fixture.js') { response.setHeader('Content-Type','application/javascript'); response.end(compiled); return; }
  const asset = assets.get(name.slice('/static/'.length));
  if (!name.startsWith('/static/') || !asset) { response.writeHead(404); response.end(); return; }
  response.setHeader('Content-Type',asset.mime); response.end(fs.readFileSync(path.join(root,'static',asset.path)));
});
const result = { scope:'isolated-global-styles-and-components',production_persistence_tested:false,win7_hardware_tested:false,
  source:{path:sourcePath,sha256:crypto.createHash('sha256').update(source).digest('hex')},cases:[],errors:[],external:[],screenshots:[] };
let browser;
async function measure(page, selector, pseudo) {
  return page.locator(selector).evaluate((element,pseudo) => {
    const style = getComputedStyle(element,pseudo), rect=element.getBoundingClientRect();
    return {appearance:style.appearance,bg:style.backgroundColor,color:style.color,border:style.borderColor,radius:style.borderRadius,shadow:style.boxShadow,
      outline:style.outlineStyle,outlineColor:style.outlineColor,visibility:style.visibility,display:style.display,height:rect.height,width:rect.width,padding:style.padding,filter:style.filter,minHeight:style.minHeight};
  },pseudo);
}
async function main() {
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const url='http://127.0.0.1:'+server.address().port;
  browser=await chromium.launch({headless:true,executablePath:process.env.WORKBENCH_BROWSER});
  result.browser=await browser.version();
  for (const viewport of [{width:1920,height:1080},{width:1392,height:924}]) for (const theme of ['light','dark']) {
    const variant=viewport.width+'-'+theme, page=await browser.newPage({viewport});
    page.on('pageerror',error=>result.errors.push({variant,message:error.message}));
    page.on('console',message=>{if(message.type()==='error')result.errors.push({variant,message:message.text()});});
    page.on('request',request=>{if(!request.url().startsWith(url)&&!request.url().startsWith('data:'))result.external.push(request.url());});
    await page.goto(url); await page.waitForFunction(()=>typeof window.applyStyles==='function');
    await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
    await page.evaluate(()=>document.fonts.ready);
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>resolve(Promise.all(document.getAnimations().map(animation=>animation.finished))))));
    const before={};
    for(const id of ['nav-row','rail','cell','tab','bar'])before[id]=await measure(page,'#'+id);
    await page.evaluate(()=>window.applyStyles(true)); await page.locator('[data-workbench-control-styles]').waitFor({state:'attached'});
    async function check(name,fn) {try {await fn();result.cases.push({variant,name,passed:true});}catch(error){result.cases.push({variant,name,passed:false,message:error.message});await page.screenshot({path:path.join(output,variant+'-'+name+'-failure.png'),fullPage:true});throw error;}}
    await check('protected-semantic-controls',async()=>{for(const [id,old] of Object.entries(before)){const current=await measure(page,'#'+id);for(const key of ['height','width','padding','bg','border','radius'])assert.equal(current[key],old[key],id+' '+key);}});
    await check('command-sizing-and-no-native-appearance',async()=>{for(const id of ['plain-button','primary-button','danger-button','disabled-button','ds-button','toolbar-select','search-input','jump']){const value=await measure(page,'#'+id);assert.equal(value.appearance,'none',id);assert.equal(value.height,32,id);assert.equal(value.radius,'4px',id);}assert.equal((await measure(page,'#mini-button')).height,30);});
    await check('editing-fields-and-state-colors',async()=>{for(const id of ['edit-text','edit-select','date','time','month','number','readonly','invalid']){const value=await measure(page,'#'+id);assert.equal(value.height,36,id);assert.equal(value.appearance,'none',id);assert.equal(value.radius,'4px',id);}assert((await measure(page,'#textarea')).height>=76);assert.notEqual((await measure(page,'#readonly')).bg,(await measure(page,'#edit-text')).bg);assert.notEqual((await measure(page,'#invalid')).border,(await measure(page,'#edit-text')).border);assert.equal((await measure(page,'#plain-semantic-button .stp-t')).color,(await measure(page,'.probe-layout')).color,'Unstyled semantic button must use theme text, not browser black');});
    await check('checkbox-radio-native-semantics',async()=>{for(const id of ['check','mixed','radio-one','radio-two','check-disabled']){const value=await measure(page,'#'+id);assert.equal(value.appearance,'none',id);assert.equal(value.height,16,id);assert.equal(value.width,16,id);}await page.locator('#check').click();assert(await page.locator('#check').isChecked());assert.equal((await measure(page,'#check','::before')).visibility,'visible');await page.locator('#check').press('Space');assert(!(await page.locator('#check').isChecked()));assert.equal((await measure(page,'#mixed','::before')).visibility,'visible');await page.locator('#radio-two').click();assert(await page.locator('#radio-two').isChecked());assert(!(await page.locator('#radio-one').isChecked()));});
    await check('numeric-keyboard-and-range',async()=>{await page.locator('#number').focus();await page.locator('#number').press('ArrowUp');assert.equal(await page.locator('#number').inputValue(),'9');await page.locator('#range').focus();await page.locator('#range').press('ArrowRight');assert.equal(await page.locator('#range').inputValue(),'45');assert.equal((await measure(page,'#range')).appearance,'none');});
    await check('numeric-stepper-geometry',async()=>{await page.getByRole('button',{name:'增加工时'}).click();assert.equal(await page.locator('#number').inputValue(),'10');await page.getByRole('button',{name:'减少工时'}).click();assert.equal(await page.locator('#number').inputValue(),'9');const parent=await measure(page,'.wb-number-parent'),stepper=await measure(page,'.wb-number-stepper'),step=await measure(page,'.wb-number-step:first-child');assert.equal(stepper.height,34);assert.equal(parent.height,36);assert(step.height>=16&&step.height<=18);assert.equal(stepper.width,24);assert.equal((await measure(page,'#number')).padding,'5px 34px 5px 10px');});
    await check('focus-and-hover-no-white-inset',async()=>{await page.locator('#edit-text').focus();assert.equal((await measure(page,'#edit-text')).outline,'solid');await page.locator('#edit-text').hover();const field=await measure(page,'#edit-text');assert.equal(field.border,field.outlineColor);assert.equal(field.shadow,'none');await page.locator('#primary-button').hover();const hover=await measure(page,'#primary-button');assert.equal(hover.shadow,'none');await page.mouse.down();const active=await measure(page,'#primary-button');assert.equal(active.bg,hover.bg);assert.notEqual(active.color,active.bg);await page.mouse.up();});
    await check('details-file-and-readonly',async()=>{await page.locator('#details summary').click();assert(await page.locator('#details').getAttribute('open')!==null);
      // Chromium 109 returns host styles for this pseudo; check parsed rules plus rendered height instead.
      const fileRule=await page.evaluate(()=>{const sheet=document.querySelector('[data-workbench-control-styles]').sheet;const rule=Array.from(sheet.cssRules).find(rule=>rule.selectorText==='body.aps-workbench input[type="file"]::file-selector-button');return {supported:CSS.supports('selector(input::file-selector-button)'),appearance:rule.style.appearance,radius:rule.style.borderRadius};});
      assert(fileRule.supported);assert.equal(fileRule.appearance,'none');assert.equal(fileRule.radius,'var(--wb-control-radius)');assert.equal((await measure(page,'#file')).height,32);
      await page.locator('#file').setInputFiles({name:'material.csv',mimeType:'text/csv',buffer:Buffer.from('code,name\n001,test')});assert.equal(await page.locator('#file').evaluate(input=>input.files[0].name),'material.csv');await page.locator('#readonly').focus();await page.locator('#readonly').press('End');await page.keyboard.type('X');assert.equal(await page.locator('#readonly').inputValue(),'R-001');});
    await check('popup-theme-and-interaction',async()=>{await page.getByRole('option',{name:'外协检验与精密加工（较长名称完整显示）',exact:true}).click();assert.equal(await page.locator('#option-popup').getByRole('option',{selected:true}).textContent(),'外协检验与精密加工（较长名称完整显示）');await page.locator('.wb-picker-day').filter({hasText:/^15$/}).click();assert.equal(await page.locator('.wb-picker-day[aria-selected="true"]').textContent(),'15');const popup=await measure(page,'#option-popup');assert.equal(popup.bg,(await measure(page,'#edit-text')).bg);if(theme==='dark')assert.notEqual(popup.bg,'rgb(255, 255, 255)');});
    await check('unavailable-date-is-visually-distinct',async()=>{const unavailable=await measure(page,'.wb-picker-day[aria-disabled="true"]');assert.notEqual(unavailable.bg,(await measure(page,'.wb-picker-day:nth-last-child(10)')).bg);await page.locator('.wb-picker-day[aria-disabled="true"]').hover();assert.equal((await measure(page,'.wb-picker-day[aria-disabled="true"]')).bg,unavailable.bg);});
    await check('fixed-date-rows-and-option-trailing-check',async()=>{
      const values=await page.evaluate(()=>{const row=document.querySelector('.wb-popup-option[aria-selected="true"]'),span=row.querySelector('span'),svg=row.querySelector('svg'),group=document.querySelector('.wb-popup-group');return {dayHeights:Array.from(document.querySelectorAll('.wb-picker-day'),day=>day.getBoundingClientRect().height),spanMin:getComputedStyle(span).minWidth,spanFlex:getComputedStyle(span).flexGrow,trailing:Math.abs(svg.getBoundingClientRect().right-(row.getBoundingClientRect().right-9))<1,groupSize:getComputedStyle(group).fontSize};});
      values.dayHeights.forEach(height=>assert.equal(height,32));assert.equal(values.spanMin,'0px');assert.equal(values.spanFlex,'1');assert(values.trailing);assert.equal(values.groupSize,'12px');
    });
    await check('month-and-fractional-time-layout',async()=>{
      const geometry=await page.evaluate(()=>{
        const container=document.createElement('div');container.className='wb-control-popup';container.style.cssText='position:relative;width:320px';
        const month=document.createElement('div');month.className='wb-date-picker';month.dataset.pickerType='month';
        const grid=document.createElement('div');grid.className='wb-picker-grid';grid.style.gridTemplateColumns='repeat(3,minmax(0,1fr))';
        for(let index=0;index<12;index++){const button=document.createElement('button');button.className='wb-picker-day';button.textContent=(index+1)+' 月';grid.appendChild(button);}month.appendChild(grid);container.appendChild(month);
        const fields=document.createElement('div');fields.className='wb-picker-fields';fields.style.gridTemplateColumns='repeat(4,minmax(0,1fr))';
        for(const label of ['时','分','秒','毫秒']){const field=document.createElement('div');field.className='wb-picker-field';const name=document.createElement('label');name.textContent=label;field.appendChild(name);const input=document.createElement('input');input.type='text';input.value='00';field.appendChild(input);const actions=document.createElement('div');actions.className='wb-picker-actions';for(const text of ['-','+']){const button=document.createElement('button');button.className='btn wb-picker-nav';button.textContent=text;actions.appendChild(button);}field.appendChild(actions);fields.appendChild(field);}container.appendChild(fields);document.body.appendChild(container);
        const result={monthHeights:Array.from(grid.querySelectorAll('button'),button=>button.getBoundingClientRect().height),timeRows:Array.from(fields.children,field=>{const buttons=field.querySelectorAll('button');return {sameRow:buttons[0].offsetTop===buttons[1].offsetTop,overflow:field.scrollWidth>field.clientWidth+1};})};container.remove();return result;
      });
      geometry.monthHeights.forEach(height=>assert.equal(height,40));geometry.timeRows.forEach(row=>{assert(row.sameRow);assert(!row.overflow);});
    });
    await check('icons-and-live-theme',async()=>{
      const icons=()=>page.locator('input[type="date"],input[type="time"],input[type="month"],select').evaluateAll(elements=>elements.map(element=>{const style=getComputedStyle(element);return {image:style.backgroundImage,size:style.backgroundSize,repeat:style.backgroundRepeat,right:style.paddingRight};}));
      const before=await icons();before.forEach(item=>{assert(item.image.startsWith('url("data:image/svg+xml,'));assert.equal(item.size,'16px 16px');assert.equal(item.repeat,'no-repeat');assert.equal(item.right,'32px');});
      await page.evaluate(theme=>document.documentElement.dataset.theme=theme==='dark'?'light':'dark',theme);
      await page.waitForFunction(previous=>getComputedStyle(document.querySelector('#date')).backgroundImage!==previous,before[2].image);
      const changed=await icons();assert.notEqual(changed[0].image,before[0].image);
      await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
      await page.waitForFunction(previous=>getComputedStyle(document.querySelector('#toolbar-select')).backgroundImage===previous,before[0].image);
    });
    await check('geometry-and-long-labels',async()=>{const issues=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,clipped:Array.from(document.querySelectorAll('button:not([data-preserved]),.wb-popup-option')).filter(el=>el.getClientRects().length&&(el.scrollWidth>el.clientWidth+1||el.scrollHeight>el.clientHeight+1)).map(el=>el.textContent)}));assert(!issues.overflow,'document overflow');assert.deepEqual(issues.clipped,[],'clipped controls');});
    await page.mouse.move(0,0);await page.screenshot({path:path.join(output,variant+'-controls.png'),fullPage:true});result.screenshots.push(variant+'-controls.png');
    await page.locator('.probe-popups').screenshot({path:path.join(output,variant+'-popups.png')});result.screenshots.push(variant+'-popups.png');
    await page.close();
  }
  assert.deepEqual(result.errors,[]);assert.deepEqual(result.external,[]);
}
main().catch(error=>{result.failure=error.stack;process.exitCode=1;}).finally(async()=>{
  if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));
  fs.writeFileSync(path.join(output,'control-style-result.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify({cases:result.cases.length,passed:result.cases.filter(row=>row.passed).length,errors:result.errors,external:result.external,failure:result.failure||null,output},null,2));
});
