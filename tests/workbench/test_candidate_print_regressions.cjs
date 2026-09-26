'use strict';
// Source-only, memory-only regression on a newly launched host Chrome 109.
// No production server, database, existing browser or VM is contacted.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), http = require('node:http');
const { chromium } = require('playwright'), H = require('./plan_ui_browser_harness.cjs');
const UI = require('./run_ui_source.cjs');
const { compile } = require('../../scripts/workbench/compile.cjs');
const output = path.resolve(process.argv[2] || '');
assert(process.argv[2] && output !== H.root && !output.startsWith(H.root + path.sep));
fs.mkdirSync(output, { recursive: true });
for (const file of UI.dependencies(['RunCandidateAPI.js', 'RunCandidateModel.js', 'RunCandidateControls.jsx',
  'RunBaselineAPI.js', 'RunBaselineModel.js', 'RunBaselineControls.jsx', 'RunCandidateGantt.jsx'])) {
  if (!H.files.includes(file)) H.files.push(file);
}
const report = { platform: process.platform, execution: 'host-only-new-Chrome109-memory-fixture',
  win7_tested: false, production_persistence_tested: false, errors: [], external: [], unexpected_requests: [], cases: [], header: [] };
const ref = value => value.toString(16).padStart(48, '0');
function server() {
  const assets = new Map(), manifest = JSON.parse(fs.readFileSync(path.join(H.root, 'static/workbench/asset-manifest.json')));
  const sources = H.files.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(H.root, 'frontend/workbench/app', name), 'utf8') }));
  const built = compile({ babel_path: path.join(H.root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
  report.sources = sources.map(row => ({ path: row.path, sha256: H.hash(row.code) }));
  report.compile = { target: built.target, global_build: false };
  report.sharedAssets = [];
  const shared = manifest.scripts.filter(name => name.startsWith('workbench/vendor/') || name.startsWith('workbench/assets/foundation-'));
  const styles = manifest.styles.filter(name => !name.startsWith('workbench/app/styles/'));
  for (const name of [...new Set([...shared, ...styles, ...manifest.files.filter(row => !row.path.startsWith('workbench/app/')).map(row => row.path)])]) {
    const entry = manifest.files.find(row => row.path === name), raw = fs.readFileSync(path.join(H.root, 'static', name));
    const bytes = raw;
    assert.equal(H.hash(bytes), entry.sha256, 'Shared asset is not the manifest content: ' + name);
    report.sharedAssets.push({ path: name, raw_sha256: H.hash(raw), served_sha256: H.hash(bytes), canonical_lf: H.hash(raw) !== H.hash(bytes) });
    assets.set('/static/' + name, { bytes, mime: entry.mime });
  }
  const compiled = built.outputs.map((row, i) => { const url = '/fixture/' + H.files[i] + '.js'; assets.set(url, { bytes: row.code, mime: 'application/javascript' }); return url; });
  const currentStyles = fs.readdirSync(path.join(H.root, 'frontend/workbench/app/styles')).filter(name => name.endsWith('.css')).sort().map(name => {
    const source = 'frontend/workbench/app/styles/' + name, bytes = fs.readFileSync(path.join(H.root, source)), url = '/fixture/' + name;
    report.sources.push({ path: source, sha256: H.hash(bytes) }); assets.set(url, { bytes, mime: 'text/css' }); return url;
  });
  const html = '<!doctype html><html lang="zh-CN" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    [...styles.map(name => '/static/' + name), ...currentStyles].map(url => '<link rel="stylesheet" href="' + url + '">').join('') +
    '</head><body class="aps-workbench"><div id="fixture-root"></div>' + [...shared.map(name => '/static/' + name), ...compiled].map(url => '<script src="' + url + '"></script>').join('') + '</body></html>';
  return http.createServer((request, response) => {
    if (request.url === '/') { response.setHeader('Content-Type', 'text/html;charset=utf-8'); response.end(html); return; }
    if (request.url === '/favicon.ico') { response.writeHead(204); response.end(); return; }
    const item = assets.get(request.url);
    if (item) { response.setHeader('Content-Type', item.mime); response.end(item.bytes); }
    else { report.unexpected_requests.push(request.url); response.writeHead(404); response.end(); }
  });
}
function records() {
  const start = Date.parse('2026-09-26T08:00:00Z'), wire = value => new Date(value).toISOString().slice(0, 19);
  const tasks = Array.from({ length: 10 }, (_, i) => ({ row_ref: ref(i + 1), operation_ref: ref(i + 101), batch_ref: ref(i + 201),
    batch_label: 'PRINT-SERIAL-LONG-BATCH-' + String(i + 1).padStart(2, '0'), part_label: '纸面回归零件',
    sequence: i + 1, process_label: '候选打印工序 ' + (i + 1), piece_id: null, quantity: 1, batch_quantity: 1,
    machine: { ref: ref(501), label: '长资源名称：打印专用设备' }, operator: { ref: ref(601), label: '验收人员' },
    start: wire(start + i * 3600000), end: wire(start + (i + 1) * 3600000), source: 'internal', data_gaps: [] }));
  tasks.push({ ...tasks[0], row_ref: ref(11), operation_ref: ref(111), batch_ref: ref(211), batch_label: 'PRINT-POINT-MARKER',
    sequence: 11, process_label: '零工时验收点', start: wire(start + 9.5 * 3600000), end: wire(start + 9.5 * 3600000),
    event_kind: 'point', duration_seconds: 0, occupies_resources: false });
  return { tasks, task_span: { start: tasks[0].start, end: tasks[9].end }, candidate: { candidate_ref: ref(701), run_ref: ref(801) } };
}
async function settle(page) {
  await page.evaluate(async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))); });
}
async function mount(page, theme) {
  await page.evaluate(({ data, theme }) => {
    if (window.candidateTestRoot) window.candidateTestRoot.unmount();
    window.candidateTestState = { data, selected: null, theme, toggles: 0 };
    function Host() {
      const [selected, select] = React.useState(null), [currentTheme, setTheme] = React.useState(theme);
      React.useLayoutEffect(() => { document.documentElement.dataset.theme = currentTheme; }, [currentTheme]);
      candidateTestState.selected = selected && selected.row_ref; candidateTestState.theme = currentTheme;
      return React.createElement(React.Fragment, null, React.createElement(WorkbenchControlStyles), React.createElement(WorkbenchControls),
        React.createElement(WorkbenchNumberControls), React.createElement(AppShell, { active: 'analysis', operations: true, showCapsule: false,
          theme: currentTheme, title: '候选打印回归', onNav: () => {}, onToggleTheme: () => { candidateTestState.toggles++; setTheme(t => t === 'dark' ? 'light' : 'dark'); } },
        React.createElement('div', { className: 'plana run-candidate-workspace' },
          React.createElement('h1', null, '候选排产结果'), React.createElement('div', { className: 'rc-main' },
            React.createElement('div', null, React.createElement(RunCandidateGantt, { data, query: '', selected, onSelect: select }),
              React.createElement(RunCandidateGantt.TaskList, { tasks: data.tasks, selected, onSelect: select, planned: true }))),
          React.createElement('div', { className: 'test-scroll-spacer', 'aria-hidden': 'true' }))));
    }
    window.candidateTestRoot = ReactDOM.createRoot(document.getElementById('fixture-root'));
    candidateTestRoot.render(React.createElement(Host));
  }, { data: records(), theme });
  await page.waitForSelector('[data-candidate-lane]'); await settle(page);
}
async function screen(page) {
  return page.evaluate(() => {
    const board = document.querySelector('[data-candidate-gantt-scroll]');
    return { left: board.scrollLeft, top: board.scrollTop, zoom: document.querySelector('.rc-tools .wb-zoom-level').textContent,
      selected: candidateTestState.selected, theme: candidateTestState.theme,
      dimension: document.querySelector('.rc-tabs [aria-pressed=true]').textContent,
      rows: document.querySelectorAll('[data-candidate-track]').length, listRows: document.querySelectorAll('[data-candidate-task-list] [data-row-ref]').length };
  });
}
async function header(page, theme) {
  await mount(page, theme);
  const position = await page.evaluate(() => {
    const label = document.querySelector('.rc-lane-label'), head = document.querySelector('.top-header');
    const top = label.getBoundingClientRect().top, middle = head.getBoundingClientRect().height / 2;
    // The lane owns an inner scroll area; the shell itself scrolls at document level.
    window.scrollTo(0, scrollY + top - middle);
    return { originalLabelTop: top, targetY: middle, documentHeight: document.documentElement.scrollHeight };
  });
  await settle(page);
  const overlap = await page.evaluate(() => {
    const label = document.querySelector('.rc-lane-label'), head = document.querySelector('.top-header'), a = label.getBoundingClientRect(), b = head.getBoundingClientRect();
    const x = Math.max(a.left, b.left) + 20, y = Math.max(a.top, b.top) + Math.min(a.height, b.height, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)) / 2;
    return { label: { left: a.left, top: a.top, right: a.right, bottom: a.bottom }, header: { left: b.left, top: b.top, right: b.right, bottom: b.bottom },
      x, y, overlap: a.bottom > b.top && a.top < b.bottom, frontIsHeader: !!document.elementFromPoint(x, y)?.closest('.top-header'),
      stack: document.elementsFromPoint(x, y).slice(0, 8).map(node => node.className) };
  });
  assert(overlap.overlap && overlap.frontIsHeader, JSON.stringify({ position, overlap }));
  const before = await page.evaluate(() => candidateTestState.toggles);
  await page.locator('.top-header button.hdr-pill').click();
  assert.equal(await page.evaluate(() => candidateTestState.toggles), before + 1);
  await page.screenshot({ path: path.join(output, 'header-' + theme + '.png') });
  report.header.push({ theme, position, overlap, realHeaderButtonClicked: true });
  await page.evaluate(() => window.scrollTo(0, 0));
}
async function print(page, theme, landscape, batch) {
  await mount(page, theme);
  if (batch) await page.getByRole('button', { name: '批次', exact: true }).click();
  await page.locator('[data-candidate-lane]').first().focus(); await page.keyboard.press('Home');
  await page.getByRole('button', { name: '放大候选时间轴', exact: true }).click();
  await page.getByRole('button', { name: '放大候选时间轴', exact: true }).click();
  await page.locator('[data-candidate-gantt-scroll]').evaluate(node => { node.scrollLeft = Math.floor((node.scrollWidth - node.clientWidth) / 2); node.scrollTop = 144; });
  await settle(page);
  const before = await screen(page); assert.equal(before.zoom, '4×'); assert(before.left > 0); if (batch) assert(before.top > 0);
  await page.evaluate(() => {
    window.candidatePrintEvents = [];
    window.captureCandidatePrint = event => {
      const canvases = [...document.querySelectorAll('[data-candidate-lane]')];
      candidatePrintEvents.push({ event: event.type, trusted: event.isTrusted,
        rows: [...document.querySelectorAll('[data-candidate-task-list] [data-row-ref]')].map(n => n.dataset.rowRef),
        pointCount: document.querySelectorAll('[data-candidate-point-lane] [data-point-ref]').length,
        canvases: canvases.map(node => ({ width: node.width, itemCount: Number(node.dataset.itemCount), marks: node.__testMarks || [] })) });
    };
    window.addEventListener('beforeprint', captureCandidatePrint); window.addEventListener('afterprint', captureCandidatePrint);
  });
  const name = theme + '-' + (landscape ? 'landscape' : 'portrait'), filename = path.join(output, name + '.pdf');
  // Native printing comes first. Synthetic events or print-media preparation would mask lifecycle regressions.
  const bytes = await page.pdf({ path: filename, format: 'A4', landscape, printBackground: true });
  assert.equal(bytes.subarray(0, 5).toString(), '%PDF-');
  const events = await page.evaluate(() => {
    window.removeEventListener('beforeprint', captureCandidatePrint); window.removeEventListener('afterprint', captureCandidatePrint); return candidatePrintEvents;
  });
  assert.deepEqual(events.map(row => [row.event, row.trusted]), [['beforeprint', true], ['afterprint', true]]);
  assert.equal(events[0].rows.length, 11); assert.equal(new Set(events[0].rows).size, 11); assert.equal(events[0].pointCount, 1);
  assert.equal(events[0].canvases.reduce((sum, row) => sum + row.marks.length, 0), 10, 'All ten serial bars must be painted for native PDF');
  for (const canvas of events[0].canvases) {
    assert.equal(canvas.itemCount, canvas.marks.length);
    assert(canvas.marks.every(mark => mark[0] >= -0.01 && mark[0] + mark[2] <= canvas.width + 0.01), JSON.stringify(canvas));
  }
  await settle(page); const after = await screen(page); assert.deepEqual(after, before, 'Native PDF must restore both scroll axes and zoom');
  const screenSize = page.viewportSize(), paperWidth = Math.floor(((landscape ? 297 : 210) - 24) * 96 / 25.4);
  await page.emulateMedia({ media: 'print' }); await page.setViewportSize({ width: paperWidth, height: 1100 }); await settle(page);
  const paper = await page.evaluate(() => {
    const box = node => { const b = node.getBoundingClientRect(); return { left: b.left, right: b.right, width: b.width }; };
    const board = document.querySelector('[data-candidate-gantt-scroll]');
    return { viewport: innerWidth, document: document.documentElement.scrollWidth, board: box(board),
      axis: box(document.querySelector('.rc-axis')), ticks: [...document.querySelectorAll('.rc-tick')].map(node => ({ ...box(node), text: node.innerText })),
      tracks: [...document.querySelectorAll('.rc-bar-space')].map(box),
      canvases: [...document.querySelectorAll('[data-candidate-lane]')].map(node => ({ ...box(node), widthPixels: node.width, marks: node.__testMarks || [] })),
      pointLanes: [...document.querySelectorAll('[data-candidate-point-lane]')].map(box),
      points: [...document.querySelectorAll('[data-candidate-point-lane] [data-point-ref]')].map(box),
      rowRefs: [...document.querySelectorAll('[data-candidate-task-list] [data-row-ref]')].map(node => node.dataset.rowRef) };
  });
  assert(paper.document <= paper.viewport + 1 && paper.board.right <= paper.viewport + 1, JSON.stringify(paper));
  for (const box of [...paper.tracks, ...paper.canvases, ...paper.pointLanes, ...paper.points]) {
    assert(box.width > 0 && box.left >= paper.board.left - 1 && box.right <= paper.board.right + 1, JSON.stringify({ paper, box }));
  }
  assert.equal(paper.canvases.reduce((sum, row) => sum + row.marks.length, 0), 10);
  assert.equal(paper.points.length, 1); assert.equal(paper.rowRefs.length, 11);
  assert(paper.ticks.every(tick => tick.left >= paper.axis.left - 1 && tick.right <= paper.axis.right + 1), 'Printable time labels must fit the axis: ' + JSON.stringify({ axis: paper.axis, ticks: paper.ticks }));
  assert(paper.ticks.every((tick, index, ticks) => !index || ticks[index - 1].right <= tick.left + 1), 'Printable time labels must not overlap: ' + JSON.stringify(paper.ticks));
  await page.screenshot({ path: path.join(output, name + '-paper.png'), fullPage: true });
  await page.emulateMedia({ media: null }); await page.setViewportSize(screenSize); await settle(page);
  report.cases.push({ name, batch, filename, sha256: H.hash(bytes), before, after, events, paper });
}
async function main() {
  const web = server(); await new Promise(resolve => web.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + web.address().port;
  let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
    page.setDefaultTimeout(15000);
    await page.route('**/*', route => route.request().url().startsWith(origin + '/') ? route.continue() : route.abort());
    page.on('pageerror', error => report.errors.push(error.message));
    page.on('request', request => { if (!request.url().startsWith(origin + '/')) report.external.push(request.url()); });
    await page.goto(origin);
    await page.locator('link[href^="/static/workbench/app/styles/"]').evaluateAll(nodes => nodes.forEach(node => node.remove()));
    await page.addStyleTag({ content: '.test-scroll-spacer{height:1200px}@media print{.test-scroll-spacer{display:none}}' });
    await page.evaluate(() => {
      const transform = CanvasRenderingContext2D.prototype.setTransform, fill = CanvasRenderingContext2D.prototype.fillRect;
      CanvasRenderingContext2D.prototype.setTransform = function (...args) { if (this.canvas.hasAttribute('data-candidate-lane')) this.canvas.__testMarks = []; return transform.apply(this, args); };
      CanvasRenderingContext2D.prototype.fillRect = function (...args) { if (this.canvas.hasAttribute('data-candidate-lane')) this.canvas.__testMarks.push(args); return fill.apply(this, args); };
    });
    for (const theme of ['light', 'dark']) await header(page, theme);
    for (const theme of ['light', 'dark']) for (const landscape of [true, false]) await print(page, theme, landscape, theme === 'dark' && !landscape);
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []); assert.deepEqual(report.unexpected_requests, []);
  } finally { if (browser) await browser.close(); await new Promise(resolve => web.close(resolve)); }
}
main().catch(error => { report.failure = error.stack; process.exitCode = 1; }).finally(() => {
  fs.writeFileSync(path.join(output, 'candidate-print-regressions.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ cases: report.cases.length, headerCases: report.header.length, failure: report.failure || null, output }));
});
