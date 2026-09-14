'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], ready = JSON.parse(fs.readFileSync(path.join(output, 'ready.json')));
const files = ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchReferences.jsx', 'WorkbenchCaption.jsx', 'WorkbenchPageContext.jsx', 'resource-contract.js', 'resource-api.js', 'resource-session.js', 'ResourceControls.jsx', 'CalendarContract.js', 'PointContract.js', 'PointGanttModel.js', 'PointGantt.jsx', 'PlanProcessOrder.js', 'PlanContract.js', 'PlanAPI.js',
  'FieldContract.js', 'ActualGanttModel.js', 'ActualGanttWindow.js', 'ActualGanttContract.js', 'ActualGanttAPI.js', 'ActualGanttControls.jsx', 'ActualGanttCanvas.jsx', 'ActualGanttRows.jsx', 'ActualGanttWorkspace.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx', 'WorkbenchControls.jsx', 'WorkbenchNumberControls.jsx', 'WorkbenchListControls.jsx'];
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const report = { errors: [], external: [], screenshots: [], cases: [], real_api_reads: 0, compile_global_build: false,
  win7_hardware_tested: false, production_database_tested: false, dense_data_source: 'explicit_memory_fixture', sources: [] };
function server() {
  const assets = new Map(), manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
  report.shared_style_build_id = manifest.build_id;
  manifest.files.forEach(item => { const bytes = fs.readFileSync(path.join(root, 'static', item.path)); assert.equal(hash(bytes), item.sha256, 'Shared asset changed during probe'); assets.set('/static/' + item.path, { bytes, mime: item.mime }); });
  const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
  report.sources = sources.map(source => ({ path: source.path, sha256: hash(source.code) }));
  report.probe_sha256 = hash(fs.readFileSync(__filename));
  const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
    sources, check_combined: true });
  report.target = built.target;
  built.outputs.forEach((item, i) => assets.set('/fixture/' + files[i], { bytes: item.code, mime: 'application/javascript' }));
  const scripts = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'))
    .map(file => '/static/' + file).concat(files.map(file => '/fixture/' + file));
  const harness = `
    let mounted; window.navigations=[];
    window.mountActual = async function(spec={}) {
      if(mounted)mounted.unmount();
      const response=await fetch('/api/workbench/v1/actual-gantt?plan_ref=${ready.plan_ref}');
      window.liveResponse=await response.json();
      let adapter;
      if(spec.dense || spec.unavailable || spec.malformed || spec.remaining || spec.narrow) {
        const dto=JSON.parse(JSON.stringify(window.liveResponse));
        if(spec.dense) {
          const template=dto.data.items[0], fixed=n=>n.toString(16).padStart(48,'0');
          dto.data.items=Array.from({length:10000},(_,i)=>{
            const row=JSON.parse(JSON.stringify(template)); row.task.task_ref=fixed(100000+i);row.task.operation_ref=fixed(200000+i);row.task.sequence=i+1;row.task.process_label='精密加工 '+(i+1);
            const e=row.execution;e.operation_ref=row.task.operation_ref;e.current_task_ref=row.task.task_ref;e.comparison_task_ref=row.task.task_ref;
            e.reports=e.reports.slice(0,1);e.reports[0].report_ref=fixed(300000+i);e.reports[0].operation_ref=row.task.operation_ref;e.reports[0].recorded_against_task_ref=row.task.task_ref;
            e.reports[0].actual_start='2026-09-08T22:00:00';e.reports[0].actual_end='2026-09-08T23:00:00';e.reports[0].completed_quantity=2;
            return row;
          });dto.data.task_count=10000;dto.data.report_count=10000;
          dto.data.critical_chain={state:'unavailable',reason_code:'modified_component_fixture',reason:'合成密集组件数据没有真实引擎关键链凭据。',task_refs:[],edges:[]};
        }
        if(spec.remaining)dto.data.items[0].execution.remaining_plan={start:'2026-09-09T01:00:00',end:'2026-09-09T02:00:00',machine_ref:dto.data.items[0].task.machine_ref,operator_ref:dto.data.items[0].task.operator_ref};
        if(spec.narrow){const report=dto.data.items[0].execution.reports[0]; report.actual_end=new Date(Date.parse(report.actual_start+'Z')+1000).toISOString().slice(0,19);}
        if(spec.unavailable){dto.data.availability={state:'unavailable',reason_code:'execution_ledger_unavailable',reason:'新报工执行投影尚未安装，实际与剩余状态不可核实。'};dto.data.report_count=null;dto.data.items.forEach(i=>i.execution=null);}
        if(spec.malformed)dto.data.items[0].execution.comparison_task_ref='f'.repeat(48);
        window.actualProbeData=dto.data;
        adapter={load:async()=>dto,export:async()=>{throw Error('Synthetic fixture cannot export production CSV');}};
      }
      if(spec.windowTransition) {
        adapter={load:async scope=>{
          await new Promise(resolve=>setTimeout(resolve,20));
          const dto=JSON.parse(JSON.stringify(liveResponse)), shifted=!!scope.plan_finish_date_from;
          const start=shifted?'2026-09-10T12:00:00':'2026-09-08T22:00:00',end=shifted?'2026-09-10T13:00:00':'2026-09-09T06:00:00';
          dto.data.items[0].task.start=start;dto.data.items[0].task.end=end;
          dto.data.plan_span={...dto.data.plan_span,start,end};
          for(const key of Object.keys(dto.data.scope))if(key!=='kind')dto.data.scope[key]=key==='source'?'production':key==='batch_ids'?(scope[key]||[]):scope[key]==null?null:scope[key];
          dto.data.critical_chain={state:'unavailable',reason_code:'modified_component_fixture',reason:'显示视窗切换夹具没有引擎链证据。',task_refs:[],edges:[]};
          window.actualProbeData=dto.data;return dto;
        }};
      }
      function Harness(){const[theme,setTheme]=React.useState(spec.theme||'light');React.useLayoutEffect(()=>{document.documentElement.dataset.theme=theme},[theme]);
        return React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchControls),React.createElement(WorkbenchNumberControls),
          React.createElement(AppShell,{active:'fieldgantt',theme,onToggleTheme:()=>setTheme(t=>t==='light'?'dark':'light'),onNav:(view,context)=>navigations.push({view,context}),operations:true,title:'现场实际甘特'},
            React.createElement(ActualGanttWorkspace,{adapter,initialContext:spec.context||(spec.noPlan?{fixture:spec.key||''}:{plan_ref:'${ready.plan_ref}',fixture:spec.key||''}),onNavigate:(view,context)=>navigations.push({view,context})})));}
      mounted=ReactDOM.createRoot(document.getElementById('fixture-root'));mounted.render(React.createElement(Harness));
    };`;
  assets.set('/fixture/mount.js', { bytes: harness, mime: 'application/javascript' });
  const currentStyles = fs.readdirSync(path.join(root, 'frontend/workbench/app/styles')).filter(name => name.endsWith('.css')).sort().map(name => {
    const stylePath = 'frontend/workbench/app/styles/' + name, styleBytes = fs.readFileSync(path.join(root, stylePath)), url = '/fixture/' + name;
    report.sources.push({ path: stylePath, sha256: hash(styleBytes) }); assets.set(url, { bytes: styleBytes, mime: 'text/css' });
    return '<link rel="stylesheet" href="' + url + '">';
  }).join('');
  const html = '<!doctype html><html lang="zh-CN" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') + currentStyles + '</head><body class="aps-workbench"><div id="fixture-root"></div>'
    + scripts.concat(['/fixture/mount.js']).map(url => '<script src="' + url + '"></script>').join('') + '</body></html>';
  return http.createServer((req, res) => {
    if (req.url.startsWith('/api/workbench/')) {
      const target = new URL(req.url, ready.url);
      const forwarded = http.request(target, { method: req.method, headers: { accept: req.headers.accept || 'application/json' } }, remote => {
        res.writeHead(remote.statusCode, remote.headers); remote.pipe(res);
      }); forwarded.on('error', e => { res.writeHead(502); res.end(e.message); }); req.pipe(forwarded); return;
    }
    if (req.url === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
    if (req.url === '/favicon.ico') { res.writeHead(204); res.end(); return; }
    const asset = assets.get(req.url); if (!asset) { res.writeHead(404); res.end(); return; }
    res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
  });
}
async function wait(page) { await page.locator('[data-actual-scroll]').waitFor(); await page.waitForFunction(() => document.querySelectorAll('.fg-virtual-row').length > 0); }
async function shot(page, name, fullPage = true) { const file = path.join(output, name + '.png'); await page.screenshot({ path: file, fullPage }); report.screenshots.push(file); }
async function action(name, fn) { await fn(); report.cases.push(name); }
async function main() {
  const web = server(); await new Promise(resolve => web.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + web.address().port, browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
  report.browser = browser.version();
  try {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, timezoneId: 'America/New_York' });
    page.on('pageerror', error => report.errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
    page.on('request', request => { if (!request.url().startsWith(origin) && !request.url().startsWith('blob:')) report.external.push(request.url()); });
    page.on('response', response => { if (response.url().includes('/api/workbench/v1/actual-gantt?') && response.status() === 200) report.real_api_reads++; });
    await page.goto(origin);
    for (const size of [1920, 1392]) for (const theme of ['light', 'dark']) {
      await page.setViewportSize({ width: size, height: size === 1920 ? 1080 : 900 });
      await page.evaluate(spec => mountActual(spec), { theme, key: size + theme }); await wait(page);
      const originalDTO = await page.evaluate(() => JSON.stringify(liveResponse.data));
      await action(size + '-' + theme + '-layout', async () => {
        assert.equal(await page.locator('[data-actual-mark=point]').count(), 1);
        assert.equal(await page.locator('[data-actual-mark=plan]').count(), 1);
        assert.ok(await page.getByText('待续排', { exact: false }).count());
        assert.equal(await page.locator('.fg-reference-band').count(), 0);
        assert.equal(await page.locator('.fg-tick').evaluateAll(nodes => nodes.some(node => node.scrollWidth > node.clientWidth + 1)), false);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1); assert.equal(overflow, false);
        const expected = await page.evaluate(() => {
          const data = liveResponse.data, start = Date.parse(data.axis_span.start + 'Z'), end = Date.parse(data.axis_span.end + 'Z');
          const pad = Math.max(60000, (end - start) * .04), label = at => new Date(at).toISOString().slice(0, 19).replace('T', ' ');
          return {start: label(start - pad), end: label(end + pad), axis_span: data.axis_span, pad,
            hours: data.items.map(item => item.execution.reports.map(row => row.effective_processing_hours))};
        });
        assert.equal(expected.axis_span.start, '2026-09-08T22:00:00', 'Original business axis start stays unchanged');
        const axis = await page.locator('.fg-foot').innerText(); assert.ok(axis.includes(expected.start) && axis.includes(expected.end), 'Only display axis receives point clearance');
        assert.equal(await page.evaluate(() => JSON.stringify(liveResponse.data)), originalDTO, 'Display layout never mutates the source DTO, axis_span or hours');
        const envelope = await page.evaluate(async () => (await (await fetch('/api/workbench/v1/actual-gantt?plan_ref=' + liveResponse.data.plan.plan_ref)).json()));
        const fresh = envelope.data, original = JSON.parse(originalDTO);
        assert.equal(fresh.critical_chain.snapshot_ref, envelope.meta.snapshot_ref, 'Each chain binds its own response capability');
        const facts = { ...fresh, critical_chain: { ...fresh.critical_chain, snapshot_ref: original.critical_chain.snapshot_ref } };
        assert.equal(JSON.stringify(facts), originalDTO, 'Only the expiring read capability may change; every chain, task, report and business field is retained');
        assert.deepEqual(fresh.items.map(item => item.execution.reports.map(row => row.effective_processing_hours)), expected.hours, 'Display padding never inflates processing hours');
        report.cases.push({name: size + '-' + theme + '-axis-padding', axis_span: expected.axis_span, display_start: expected.start, display_end: expected.end, pad_ms: expected.pad, dto_unchanged: true});
        assert.equal(await page.locator('.fg-clock').count(), 1); assert.ok(await page.locator('[data-plan-end="2026-09-09T06:00:00"]').count());
      });
      await shot(page, size + '-' + theme);
    }
    await action('selection-details-and-report-ref', async () => {
      await page.locator('[data-report-ref]').first().click();
      await page.getByRole('checkbox', { name: '详情', exact: true }).check();
      await page.getByLabel('选择报工详情').selectOption({ label: 'FG-003' });
      assert.ok((await page.getByLabel('工序详情').innerText()).includes('本次结束未填写'));
      await page.getByRole('button', { name: '定位本次报工', exact: true }).click();
      await page.waitForFunction(() => { const node = document.querySelector('[data-actual-mark=point]'), board = document.querySelector('[data-actual-scroll]');
        if (!node) return false; const point = node.getBoundingClientRect(), box = board.getBoundingClientRect(); return point.top > box.top + 52 && point.bottom < box.bottom; });
      await page.getByRole('checkbox', { name: '只看选中', exact: true }).check();
      assert.ok((await page.locator('[data-actual-count]').innerText()).includes('1 / 1'));
      await page.getByRole('checkbox', { name: '只看选中', exact: true }).uncheck();
    });
    await action('views-collapse-zoom-scroll-frozen', async () => {
      for (const name of ['人员', '批次', '设备']) await page.getByRole('button', { name, exact: true }).click();
      await page.getByRole('button', { name: '全部折叠', exact: true }).click();
      assert.equal(await page.locator('[data-task-row]').count(), 0);
      await page.getByRole('button', { name: '全部展开', exact: true }).click();
      await page.getByRole('button', { name: '放大时间轴', exact: true }).click();
      await page.getByRole('button', { name: '放大时间轴', exact: true }).click();
      await page.getByLabel('时间轴水平位置').focus(); await page.keyboard.press('End');
      await page.waitForFunction(() => document.querySelector('[data-actual-scroll]').scrollLeft > 0);
      assert.ok(await page.evaluate(() => { const board = document.querySelector('[data-actual-scroll]'), fixed = document.querySelector('[data-task-row] .fg-frozen');
        const a = board.getBoundingClientRect(), b = fixed.getBoundingClientRect(); return Math.abs(a.left - b.left) < 2 && document.elementFromPoint(b.left + 60, b.top + 20).closest('.fg-frozen'); }));
      await shot(page, 'horizontal-frozen');
      await page.getByRole('button', { name: '定位选中工序', exact: true }).click();
      await page.getByRole('button', { name: '适应全部', exact: true }).click();
    });
    await action('server-range-and-local-export-real-csv', async () => {
      await page.evaluate(() => {
        window.calendarEvents = [];
        const state = (event, target) => calendarEvents.push({ event, target: target && target.outerHTML ? target.outerHTML.slice(0, 500) : String(target),
          at: performance.now(), popup: !!document.querySelector('.wb-control-popup'), x: scrollX, y: scrollY });
        for (const type of ['pointerdown', 'click', 'focusin', 'scroll']) document.addEventListener(type, event => state(type, event.target), true);
        new MutationObserver(() => {
          const present = !!document.querySelector('.wb-control-popup');
          if (window.calendarPopupPresent !== present) { window.calendarPopupPresent = present; state('popup-' + present, document.activeElement); }
        }).observe(document.body, { childList: true, subtree: true });
      });
      for (const label of ['计划完工开始日', '计划完工结束日']) {
        const input = page.getByLabel(label);
        await page.mouse.move(1300, 110); await page.mouse.wheel(0, -2000);
        await page.waitForFunction(() => scrollY === 0);
        await input.focus();
        await input.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        try {
          const box = await input.boundingBox(); assert(box.y >= 60, 'Date owner must be below the fixed header before opening');
          await input.click({ position: { x: box.width - 12, y: box.height / 2 } });
          await page.locator('.wb-control-popup').waitFor();
          assert.equal(await page.locator('.wb-control-popup').evaluate(node => getComputedStyle(node).backgroundColor), await page.locator('.fg-toolbar').evaluate(node => getComputedStyle(node).backgroundColor));
          await shot(page, 'calendar-' + label, false);
          assert(await page.locator('.wb-control-popup').isVisible(), 'A calendar viewport screenshot must not dismiss the opened picker');
          await page.getByRole('gridcell', { name: '2026-09-09', exact: true }).click();
          assert.equal(await input.inputValue(), '2026-09-09');
        } catch (error) {
          report.calendar_events = await page.evaluate(() => calendarEvents);
          await shot(page, 'calendar-failure', false);
          throw error;
        }
      }
      report.calendar_events = await page.evaluate(() => calendarEvents);
      const label = await page.locator('[aria-label="资源范围"] option').filter({ hasText: '五分厂实际改换设备' }).getAttribute('value');
      await page.getByLabel('资源范围', { exact: true }).selectOption(label);
      await page.getByRole('button', { name: '应用范围', exact: true }).click(); await wait(page);
      await page.getByLabel('搜索现场甘特').fill('FG-003');
      await page.getByRole('button', { name: '导出 CSV', exact: true }).click();
      const pending = page.waitForEvent('download'); await page.getByRole('button', { name: '下载 CSV', exact: true }).click();
      const download = await pending, file = path.join(output, 'actual.csv'); await download.saveAs(file);
      const csv = fs.readFileSync(file, 'utf8'); assert.ok(csv.includes('FG-001') && csv.includes('FG-002') && csv.includes('FG-003')); assert.equal(csv.trim().split('\r\n').length, 4);
      await page.getByLabel('搜索现场甘特').fill('not present'); assert.ok((await page.locator('[data-actual-count]').innerText()).includes('0 / 1'));
      await page.getByLabel('搜索现场甘特').fill('');
      await page.getByLabel('晚期筛选').selectOption('finishLate'); assert.ok((await page.locator('[data-actual-count]').innerText()).includes('0 / 1'));
      await page.getByLabel('晚期筛选').selectOption('unclosed'); assert.ok((await page.locator('[data-actual-count]').innerText()).includes('1 / 1'));
      await page.getByLabel('晚期筛选').selectOption('all');
      await page.getByRole('button', { name: '现场记录', exact: true }).click(); assert.equal(await page.evaluate(() => navigations.at(-1).view), 'field');
      assert.equal(await page.evaluate(() => navigations.at(-1).context.return_to.context.return_to), undefined);
    });
    await action('default-current-plan-and-demo-never-substituted', async () => {
      await page.evaluate(() => mountActual({ noPlan: true, key: 'default' })); await wait(page);
      await page.evaluate(() => mountActual({ context: { scope: { source: 'demo' } } }));
      await page.getByRole('alert').waitFor(); assert.equal(await page.locator('[data-actual-scroll]').count(), 0);
      assert.ok((await page.getByRole('alert').innerText()).includes('未将演示范围替换为生产范围'));
    });
    await action('field-producer-only-normalizes-empty-batches-with-original-return-context', async () => {
      for (const batches of [[], ['CAT-B']]) {
        await page.evaluate(context => mountActual({ context }), { plan_ref: ready.plan_ref, scope: { source: 'production', batch_ids: batches } });
        await wait(page); await page.getByRole('button', { name: '现场记录', exact: true }).click();
        const field = await page.evaluate(() => navigations.at(-1));
        assert.equal(field.view, 'field'); assert.equal(field.context.plan_ref, ready.plan_ref);
        assert.equal(field.context.scope.source, 'production');
        if (batches.length) assert.deepEqual(field.context.scope.batch_ids, batches);
        else assert.equal(Object.prototype.hasOwnProperty.call(field.context.scope, 'batch_ids'), false);
        assert.deepEqual(field.context.return_to.context.scope.batch_ids, batches);
        await page.getByRole('button', { name: '计划甘特', exact: true }).click();
        assert.deepEqual(await page.evaluate(() => navigations.at(-1).context.scope.batch_ids), batches);
      }
      for (const batches of ['[]', { batch_id: 'CAT-B' }, [7]]) {
        await page.evaluate(context => mountActual({ context }), { plan_ref: ready.plan_ref, scope: { batch_ids: batches } });
        await page.getByRole('alert').waitFor(); assert.equal(await page.locator('[data-actual-scroll]').count(), 0);
        await page.getByRole('button', { name: '现场记录', exact: true }).click();
        assert.deepEqual(await page.evaluate(() => navigations.at(-1).context.scope.batch_ids), batches, 'Malformed scope cannot be dropped into an unrestricted read');
      }
    });
    await action('mobile-fit-and-long-resource', async () => {
      await page.setViewportSize({ width: 390, height: 844 }); await page.evaluate(() => mountActual({ key: 'mobile' })); await wait(page);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
      await shot(page, '390-light'); await page.setViewportSize({ width: 1392, height: 900 });
    });
    await action('default-plan-window-and-four-pixel-hit', async () => {
      await page.evaluate(() => mountActual({ narrow: true, key: 'narrow' })); await wait(page);
      const windowGeometry = await page.evaluate(() => {
        const board = document.querySelector('[data-actual-scroll]'), frame = board.getBoundingClientRect(), baseline = document.querySelector('[data-actual-mark=plan]').getBoundingClientRect();
        const label = parseFloat(board.style.getPropertyValue('--fg-label'));
        return { first: baseline.left, last: baseline.right, visibleStart: frame.left + label, visibleEnd: frame.right, scrollWidth: board.scrollWidth, viewportWidth: board.clientWidth };
      });
      assert(windowGeometry.first >= windowGeometry.visibleStart - 1 && windowGeometry.last <= windowGeometry.visibleEnd + 1, 'Default window fully contains the original plan');
      assert(windowGeometry.scrollWidth > windowGeometry.viewportWidth, 'Default display zooms into plan instead of fitting distant as_of');
      const mark = page.locator('[data-duration-ms="1000"]').first(); await mark.waitFor();
      const geometry = await mark.evaluate(node => ({ hit: node.getBoundingClientRect().width, face: node.querySelector('.fg-mark-face').getBoundingClientRect().width, duration: Number(node.dataset.durationWidth) }));
      assert.equal(geometry.hit, 4); assert(geometry.duration > 0 && geometry.duration < 1);
      assert(Math.abs(geometry.face - geometry.duration) < .02, 'Painted duration never grows to the hitbox');
      await mark.click({ position: { x: 3, y: 20 } });
      assert.equal(await mark.getAttribute('aria-pressed'), 'true');
      await page.getByRole('button', { name: '适应全部', exact: true }).click();
      assert.equal(await page.locator('[data-actual-scroll]').evaluate(node => node.scrollLeft), 0);
      assert.equal(await page.locator('[data-actual-scroll]').evaluate(node => Math.round(node.scrollWidth - node.clientWidth)), 0, 'Fit includes the complete model axis');
      report.narrow_hit_geometry = geometry; report.default_window_geometry = windowGeometry;
    });
    await action('applied-scope-reinitializes-from-new-response', async () => {
      await page.evaluate(() => mountActual({ windowTransition: true, key: 'scope-transition' })); await wait(page);
      const originalWidth = await page.locator('.fg-ticks').evaluate(node => node.getBoundingClientRect().width);
      await page.getByLabel('计划完工开始日', { exact: true }).fill('2026-09-10');
      await page.getByLabel('计划完工结束日', { exact: true }).fill('2026-09-10');
      await page.getByRole('button', { name: '应用范围', exact: true }).click();
      await page.waitForFunction(() => window.actualProbeData.plan_span.start === '2026-09-10T12:00:00' && !!document.querySelector('[data-actual-mark=plan]'));
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const geometry = await page.evaluate(() => {
        const board=document.querySelector('[data-actual-scroll]'),frame=board.getBoundingClientRect(),bar=document.querySelector('[data-actual-mark=plan]').getBoundingClientRect();
        return {start:bar.left,end:bar.right,visibleStart:frame.left+parseFloat(board.style.getPropertyValue('--fg-label')),visibleEnd:frame.right,width:document.querySelector('.fg-ticks').getBoundingClientRect().width};
      });
      assert(geometry.width > originalWidth * 5, 'One-hour new scope gets its own zoom instead of retaining old eight-hour scope');
      assert(geometry.start >= geometry.visibleStart - 1 && geometry.end <= geometry.visibleEnd + 1, 'The new plan range is fully visible');
      report.scope_transition_geometry = {originalWidth,...geometry};
    });
    await action('10000-task-virtualization-canvas-and-user-scroll', async () => {
      await page.evaluate(() => mountActual({ dense: true, key: 'dense' })); await wait(page);
      report.dense_count = 10000; report.virtual_rows = await page.locator('.fg-virtual-row').count(); assert.ok(report.virtual_rows < 60);
      report.canvas_pixels = await page.locator('[data-actual-canvas]').first().evaluate(canvas => { const d = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data; let count = 0; for (let i = 3; i < d.length; i += 4) if (d[i]) count++; return count; });
      assert.ok(report.canvas_pixels > 0);
      const denseDTO = await page.evaluate(() => JSON.stringify(actualProbeData));
      const canvas = page.locator('[data-actual-canvas]').first();
      const hit = await canvas.evaluate(node => {
        const item = actualProbeData.items.find(item => item.task.task_ref === node.closest('[data-task-row]').dataset.taskRow);
        const row = item.execution.reports[0], clock = value => Date.parse(value.replace(' ', 'T') + 'Z');
        const axis = Array.from(document.querySelectorAll('.fg-foot > span')).map(n => clock(n.textContent));
        const width = node.closest('.fg-track').getBoundingClientRect().width, left = document.querySelector('[data-actual-scroll]').scrollLeft;
        const start = (clock(row.actual_start) - axis[0]) / (axis[1] - axis[0]) * width - left;
        const end = (clock(row.actual_end) - axis[0]) / (axis[1] - axis[0]) * width - left;
        const center = (start + end) / 2, outside = end + 2, dpr = node.width / node.getBoundingClientRect().width;
        const alpha = x => node.getContext('2d').getImageData(Math.floor(x * dpr), Math.floor(25 * dpr), 1, 1).data[3];
        return {start, end, center, outside, width, viewport: node.getBoundingClientRect().width, left,
          actual_start: row.actual_start, actual_end: row.actual_end, axis, center_alpha: alpha(center), outside_alpha: alpha(outside)};
      });
      assert(hit.start < hit.center && hit.center < hit.end && hit.outside < hit.viewport);
      assert(hit.center_alpha > 0 && hit.outside_alpha === 0, 'Actual interval pixels stop at true duration boundary');
      assert.equal(await page.locator('[data-task-row].is-selected').count(), 0);
      await canvas.hover({position: {x: hit.outside, y: 25}}); assert.equal(await page.getByRole('tooltip').count(), 0);
      await canvas.click({position: {x: hit.outside, y: 25}}); assert.equal(await page.locator('[data-task-row].is-selected').count(), 0, 'Outside the real interval cannot select a task');
      await canvas.hover({position: {x: hit.center, y: 25}}); await page.getByRole('tooltip').waitFor();
      await canvas.click({position: {x: hit.center, y: 25}});
      await page.getByRole('checkbox', { name: '详情', exact: true }).check(); assert.ok(!(await page.getByLabel('工序详情').innerText()).includes('未选中工序'));
      assert.equal(await page.evaluate(() => JSON.stringify(actualProbeData)), denseDTO, 'Precise interval hit testing does not alter DTO, axis or hours');
      report.dense_hit_geometry = hit;
      const board = page.locator('[data-actual-scroll]'); await board.focus(); await page.keyboard.press('Control+End');
      await page.waitForFunction(() => document.querySelector('[data-actual-scroll]').scrollTop > 100000);
      assert.ok(await page.locator('.fg-virtual-row').count() < 60);
      await shot(page, '10000-end');
      await page.getByLabel('搜索现场甘特').fill('精密加工 10000'); assert.ok((await page.locator('[data-actual-count]').innerText()).includes('1 / 10000'));
      await page.getByRole('button', { name: '定位选中工序', exact: true }).isDisabled();
    });
    await action('existing-remaining-and-unavailable-fail-closed', async () => {
      await page.evaluate(() => mountActual({ remaining: true, key: 'remaining' })); await wait(page);
      assert.equal(await page.locator('[data-actual-mark=remaining]').count(), 1);
      await shot(page, 'remaining-evidence-fixture');
      await page.evaluate(() => mountActual({ unavailable: true, key: 'unavailable' })); await wait(page);
      assert.equal(await page.getByRole('button', { name: '导出 CSV', exact: true }).isDisabled(), true);
      assert.ok((await page.locator('[data-actual-gantt]').innerText()).includes('新报工执行投影尚未安装'));
      await shot(page, 'unavailable');
      await page.evaluate(() => mountActual({ malformed: true, key: 'malformed' }));
      await page.getByRole('alert').waitFor(); assert.equal(await page.locator('[data-actual-scroll]').count(), 0);
    });
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
    await page.close();
  } finally { await browser.close(); await new Promise(resolve => web.close(resolve)); }
}
main().catch(error => { report.runner_error = error.stack; process.exitCode = 1; console.error(error.stack); }).finally(() => {
  fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(report, null, 2)); console.log(JSON.stringify(report));
});
