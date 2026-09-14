'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
assert(output && !path.resolve(output).startsWith(root + path.sep)); fs.mkdirSync(output, { recursive: true });
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const report = { sources: [], errors: [], cases: [], fixture: 'synthetic component reports', production_database_tested: false, win7_hardware_tested: false };
const names = ['WorkbenchFormat.js', 'PointContract.js', 'PointGanttModel.js', 'WorkbenchTerms.js', 'FieldContract.js', 'ActualGanttModel.js', 'ActualGanttWindow.js', 'ActualGanttCanvas.jsx'];
const sources = names.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
report.sources = sources.map(source => ({ path: source.path, sha256: hash(source.code) })); report.probe_sha256 = hash(fs.readFileSync(__filename));
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
report.target = built.target;
const assets = new Map(); built.outputs.forEach((item, i) => assets.set('/' + names[i], item.code));
for (const name of ['react-18.3.1.production.min.js', 'react-dom-18.3.1.production.min.js']) {
  const file = 'static/workbench/vendor/' + name, bytes = fs.readFileSync(path.join(root, file));
  report.sources.push({ path: file, sha256: hash(bytes) }); assets.set('/' + name, bytes);
}
assets.set('/mount.js', `
  const start=Date.parse('2026-09-08T00:00:00Z'), wire=offset=>new Date(start+offset*1000).toISOString().slice(0,19);
  const reports=Array.from({length:64},(_,i)=>({report_ref:'report-'+(i+1),report_no:'FG-'+(i+1),actual_start:wire(100+i*100),actual_end:wire(130+i*100),completed_quantity:1,effective_processing_hours:1,actual_machine_ref:'m',actual_operator_ref:'o'}));
  reports[3].actual_end=reports[3].actual_start;
  const task={task_ref:'task-1',batch_id:'B',sequence:1,process_label:'加工',piece_id:null,quantity:64,batch_quantity:64,start:wire(0),end:wire(90),machine_ref:'m',operator_ref:'o'};
  const item={task,execution:{execution_state:'partial',known_completed_quantity:64,remaining_quantity:1,confirmed_finish:null,reports,remaining_plan:{start:wire(6800),end:wire(6900)}}};
  const model={start,end:start+7000000,labels:new Map([['m','设备'],['o','人员']])};
  let mounted; window.selections=[]; window.fixtureDTO=JSON.stringify(item);
  window.mountKeyboard=function(mode='reports'){
    if(mounted)mounted.unmount(); window.selections=[];
    const row={item,reports:mode==='reports'?reports:[],baseline:mode==='reports'||mode==='plan-point',kind:mode==='remaining'?'remaining':'actual'};
    if(mode==='plan-point'){row.item=JSON.parse(JSON.stringify(item));Object.assign(row.item.task,{start:wire(90),end:wire(90),event_kind:'point',duration_seconds:0,occupies_resources:false});}
    window.probeRow=row;
    function Harness(){const[left,setLeft]=React.useState(0),[selected,setSelected]=React.useState(null);
      return React.createElement(React.Fragment,null,React.createElement('button',{id:'before'},'前一个控件'),
        React.createElement('div',{'data-actual-scroll':true,id:'board',onScroll:e=>setLeft(e.currentTarget.scrollLeft)},
          React.createElement('div',{id:'inner'},React.createElement('div',{id:'row'},React.createElement('div',{id:'frozen'},'工序'),React.createElement('div',{className:'fg-track'},
            React.createElement(ActualGanttCanvas.DenseRow,{row,model,width:12000,viewport:500,left,selected,onSelect:(item,report)=>{window.selections.push(report?report.report_ref:null);setSelected(item.task.task_ref)},onHover:()=>{},renderMark:()=>null}))))),
        React.createElement('button',{id:'after'},'后一个控件'));
    }
    mounted=ReactDOM.createRoot(document.getElementById('root'));mounted.render(React.createElement(Harness));
  };
`);
const styles = `body{margin:20px}#board{width:700px;height:220px;overflow:auto;position:relative;border:1px solid}#inner{width:12200px;height:500px;position:relative}#row{position:absolute;top:100px;display:flex;width:12200px;height:88px}#frozen{position:sticky;left:0;z-index:5;width:200px;flex:none;background:white}.fg-track{position:relative;flex:none;width:12000px;height:100%;overflow:hidden}.fg-row-canvas{position:absolute;top:0;height:100%;--wb-gantt-plan-fill:#aaa;--wb-gantt-plan-edge:#888;--wb-gantt-primary-fill:#77a;--wb-gantt-primary-edge:#337;--wb-gantt-reference-fill:#ccc;--wb-gantt-gold:#b70}`;
const scripts = ['react-18.3.1.production.min.js', 'react-dom-18.3.1.production.min.js', ...names, 'mount.js'];
const html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>' + styles + '</style></head><body><div id="root"></div>' + scripts.map(name => '<script src="/' + name + '"></script>').join('') + '</body></html>';
const server = http.createServer((req, res) => {
  if (req.url === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (req.url === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  if (!assets.has(req.url)) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', 'application/javascript'); res.end(assets.get(req.url));
});
async function visibleActive(page) {
  await page.waitForFunction(() => {
    const canvas=document.querySelector('canvas'), board=document.querySelector('#board'), mark=ActualGanttModel.marks(probeRow).find(mark=>mark.key===canvas.dataset.activeMark);
    const box=ActualGanttWindow.markBox(mark,model,12000), rect=canvas.getBoundingClientRect(), frame=board.getBoundingClientRect();
    return box.hitLeft>=board.scrollLeft-1 && box.hitLeft+box.hitWidth<=board.scrollLeft+500+1 && rect.top>=frame.top+51 && rect.bottom<=frame.bottom+1;
  });
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true }); report.browser = browser.version();
  try {
    const page = await browser.newPage({ viewport: { width: 1100, height: 650 } }); page.on('pageerror', error => report.errors.push(error.stack)); page.setDefaultTimeout(5000);
    await page.goto('http://127.0.0.1:' + server.address().port); await page.evaluate(() => mountKeyboard());
    const canvas = page.locator('canvas'); await canvas.waitFor(); await page.locator('#before').focus(); await page.keyboard.press('Tab');
    assert.equal(await canvas.evaluate(node => node === document.activeElement), true); await visibleActive(page);
    for (let i=0;i<=64;i++) {
      assert.equal(await canvas.getAttribute('data-active-mark'), i === 0 ? 'plan' : 'report-' + i);
      await page.keyboard.press(i % 2 ? 'Space' : 'Enter'); await visibleActive(page);
      if (i < 64) await page.keyboard.press('ArrowRight');
    }
    assert.deepEqual(await page.evaluate(() => selections), [null, ...Array.from({ length:64 }, (_, i) => 'report-' + (i+1))]);
    assert.ok((await canvas.getAttribute('aria-label')).includes('第 65 / 65 个色块'));
    assert.ok(await page.locator('#board').evaluate(node => node.scrollLeft > 10000));
    report.cases.push('All 65 marks including report 2, point report 4 and final interval report 64 select exact references and scroll into view');
    await page.keyboard.press('Home'); assert.equal(await canvas.getAttribute('data-active-mark'), 'plan'); await visibleActive(page);
    await page.keyboard.press('End'); assert.equal(await canvas.getAttribute('data-active-mark'), 'report-64'); await visibleActive(page);
    await page.keyboard.press('ArrowLeft'); assert.equal(await canvas.getAttribute('data-active-mark'), 'report-63');
    await page.keyboard.press('ArrowUp'); assert.equal(await canvas.getAttribute('data-active-mark'), 'report-62');
    await page.keyboard.press('ArrowDown'); assert.equal(await canvas.getAttribute('data-active-mark'), 'report-63');
    await page.keyboard.press('Tab'); assert.equal(await page.locator('#after').evaluate(node => node === document.activeElement), true);
    report.cases.push('Home/End and four arrows traverse without trapping Tab');
    await page.evaluate(() => mountKeyboard()); await canvas.waitFor();
    const pointer = await page.evaluate(() => {
      const mark=ActualGanttModel.marks(probeRow)[2], box=ActualGanttWindow.markBox(mark,model,12000), board=document.querySelector('#board');
      board.scrollLeft=box.hitLeft-100; return { left:board.scrollLeft, x:100+box.hitWidth/2 };
    });
    await page.waitForFunction(left => parseFloat(document.querySelector('canvas').style.left)===left, pointer.left);
    await canvas.click({ position: { x:pointer.x, y:30 } });
    assert.deepEqual(await page.evaluate(() => selections), ['report-2']);
    assert.equal(await page.locator('#board').evaluate(node => node.scrollLeft), pointer.left, 'Pointer focus cannot reveal another mark before hit testing');
    await page.keyboard.press('Enter'); assert.deepEqual(await page.evaluate(() => selections), ['report-2','report-2']);
    report.cases.push('Pointer focus keeps hit coordinates stable and Enter retains the clicked report');
    for (const mode of ['remaining', 'plan-point']) {
      await page.evaluate(mode => mountKeyboard(mode), mode); await canvas.waitFor(); await canvas.focus(); await visibleActive(page); await page.keyboard.press('Enter');
      assert.deepEqual(await page.evaluate(() => selections), [null]); assert.ok((await canvas.getAttribute('aria-label')).includes(mode === 'remaining' ? '已有剩余安排' : '原计划 · 零工时工序'));
    }
    report.cases.push('Remaining interval and plan point can be focused and activated');
    await page.evaluate(() => mountKeyboard('empty')); await canvas.waitFor();
    assert.equal(await canvas.getAttribute('tabindex'), '-1'); assert.equal(await canvas.getAttribute('aria-disabled'), 'true');
    await canvas.focus(); await page.keyboard.press('Enter'); assert.deepEqual(await page.evaluate(() => selections), []);
    await page.locator('#before').focus(); await page.keyboard.press('Tab'); assert.equal(await page.locator('#after').evaluate(node => node === document.activeElement), true);
    assert.equal(await page.evaluate(() => JSON.stringify(item)), await page.evaluate(() => fixtureDTO));
    report.cases.push('No marks disables selection; DTO is unchanged'); assert.deepEqual(report.errors, []);
    report.passed = true;
  } catch (error) { report.passed = false; report.failure = error.stack; process.exitCode = 1; }
  finally { await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(report, null, 2)); console.log(JSON.stringify(report)); }
})().catch(error => { console.error(error); server.close(); process.exitCode = 1; });
