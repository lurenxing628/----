'use strict';
// Native Chromium 109 print lifecycle, current component sources and memory-only records.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { chromium } = require('playwright'), H = require('./plan_ui_browser_harness.cjs');
const output = path.resolve(process.argv[2]);
assert(process.argv[2] && !output.startsWith(H.root + path.sep));
fs.mkdirSync(output, { recursive: true });
const report = { errors: [], unexpected_requests: [], external: [], cases: [], production_persistence_tested: false };
async function settle(page) {
  await page.evaluate(async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))); });
}
async function screen(page) {
  return page.evaluate(() => {
    const board = document.querySelector('[data-plan-scroll]');
    return { left: board.scrollLeft, top: board.scrollTop, width: board.clientWidth, height: board.clientHeight,
      query: document.querySelector('.plan-search input').value, context: fixture.context,
      zoom: document.querySelector('.plan-gantt .wb-zoom-level').textContent,
      selected: document.querySelector('[data-plan-inspector]').textContent,
      expanded: !!document.querySelector('.plan-expanded'), rows: document.querySelectorAll('.plan-lane').length };
  });
}
async function run(page, name, spec, expected) {
  await page.evaluate(spec => mountPlan(spec), { view: 'gantt', ...spec });
  await page.waitForSelector('[data-plan-gantt]'); await settle(page);
  if (expected.baseline) {
    await page.getByRole('checkbox', { name: '显示初始计划' }).check();
    await page.getByRole('checkbox', { name: '仅变更', exact: true }).check();
  }
  if (expected.expanded) await page.getByRole('button', { name: '展开甘特', exact: true }).click();
  await page.getByRole('button', { name: '放大时间轴', exact: true }).click();
  await page.getByRole('button', { name: '放大时间轴', exact: true }).click();
  await page.locator('[data-plan-scroll]').evaluate(node => { node.scrollLeft = (node.scrollWidth - node.clientWidth) / 2; node.scrollTop = Math.min(1800, node.scrollHeight - node.clientHeight); });
  await settle(page);
  const before = await screen(page);
  assert.equal(before.zoom, '4×');
  await page.evaluate(() => {
    window.printEvents = [];
    window.capturePrint = event => {
      const board = document.querySelector('[data-plan-scroll]'), bars = Array.from(document.querySelectorAll('[data-plan-task]'));
      const canvases = Array.from(document.querySelectorAll('[data-plan-dense-row]'));
      const pixels = canvases.map(node => {
        const bytes = node.getContext('2d').getImageData(0, 0, node.width, node.height).data;
        let count = 0; for (let i = 3; i < bytes.length; i += 4) if (bytes[i]) count++;
        return { count, width: node.width, left: node.style.left, cssWidth: node.style.width };
      });
      printEvents.push({ event: event.type, trusted: event.isTrusted, printing: document.querySelector('[data-plan-gantt]').dataset.printing === 'true',
        rows: document.querySelectorAll('.plan-lane').length, taskRefs: bars.map(node => node.dataset.planTask),
        baselineBars: bars.filter(node => node.hasAttribute('data-before')).length, pixels,
        drawCount: window.printCanvasMarks.length, count: document.querySelector('[data-plan-search-count]').textContent,
        left: board.scrollLeft, top: board.scrollTop });
    };
    window.addEventListener('beforeprint', capturePrint); window.addEventListener('afterprint', capturePrint);
  });
  const filename = path.join(output, name + '.pdf');
  // Do not call emulateMedia('print') or dispatch synthetic events: that would hide the missing synchronous prepare bug.
  const landscape = expected.landscape !== false;
  await page.pdf({ path: filename, format: 'A4', landscape, printBackground: true });
  const events = await page.evaluate(() => { window.removeEventListener('beforeprint', capturePrint); window.removeEventListener('afterprint', capturePrint); return printEvents; });
  assert.deepEqual(events.map(row => [row.event, row.trusted, row.printing]), [['beforeprint', true, true], ['afterprint', true, false]]);
  const printed = events[0];
  assert.equal(printed.count, expected.count);
  if (expected.dense) {
    assert.equal(printed.rows, 1); assert.equal(printed.pixels.length, 1);
    assert.equal(printed.drawCount, expected.tasks, 'All matching dense tasks must be painted, including those outside the screen viewport');
    assert(printed.pixels.every(row => row.count > 100 && row.left === '0px'));
  } else {
    assert.equal(printed.taskRefs.length, expected.tasks);
    assert.equal(new Set(printed.taskRefs).size, expected.tasks);
    assert.equal(printed.baselineBars, expected.baseline || 0);
    assert(printed.rows >= before.rows, 'Print must retain every visible screen row as well as matching offscreen rows');
  }
  await settle(page); const after = await screen(page);
  assert.deepEqual(after, before, 'Printing must preserve screen filters, selection, zoom and both scroll axes');
  const pdf = fs.readFileSync(filename), pages = (pdf.toString('latin1').match(/\/Type\s*\/Page\b/g) || []).length;
  assert(pdf.subarray(0, 5).equals(Buffer.from('%PDF-'))); assert(pages > 0);
  // Native PDF is produced above without any media warm-up. Now independently check the same responsive
  // print geometry at A4's content width, including the rightmost mark; screen-wide fixed pixels must fail.
  const screenSize = page.viewportSize();
  await page.emulateMedia({ media: 'print' });
  await page.setViewportSize({ width: Math.floor(((landscape ? 297 : 210) - 24) * 96 / 25.4), height: 794 });
  await settle(page);
  const paper = await page.evaluate(() => {
    const frame = document.querySelector('.plan-board-frame').getBoundingClientRect(), inner = document.querySelector('.plan-board-inner').getBoundingClientRect();
    const tracks = Array.from(document.querySelectorAll('.plan-track')).map(node => node.getBoundingClientRect());
    const marks = Array.from(document.querySelectorAll('[data-plan-task], [data-plan-dense-row]')).map(node => node.getBoundingClientRect());
    return { frameRight: frame.right, innerRight: inner.right, frameWidth: frame.width,
      trackRight: Math.max(...tracks.map(box => box.right)), markRight: Math.max(...marks.map(box => box.right)),
      viewport: innerWidth };
  });
  assert(paper.innerRight <= paper.frameRight + 1 && paper.trackRight <= paper.frameRight + 1 && paper.markRight <= paper.frameRight + 1, JSON.stringify(paper));
  assert(paper.frameRight <= paper.viewport + 1, JSON.stringify(paper));
  // Clear the override instead of forcing screen: the next native PDF must still activate real print CSS.
  await page.emulateMedia({ media: null }); await page.setViewportSize(screenSize); await settle(page);
  report.cases.push({ name, before, after, events, pdf: filename, pages, expected, paper });
}
async function main() {
  const web = H.server(report); await new Promise(resolve => web.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + web.address().port;
  const browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
  report.browser = browser.version();
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
    page.on('pageerror', error => report.errors.push(error.message));
    page.on('request', request => { if (!request.url().startsWith(origin)) report.external.push(request.url()); });
    await page.goto(origin);
    // The harness also loads built app CSS. Test the current source rules alone, so old print rules cannot mask a regression.
    await page.locator('link[href^="/static/workbench/app/styles/"]').evaluateAll(nodes => nodes.forEach(node => node.remove()));
    await page.evaluate(() => {
      window.printCanvasMarks = [];
      const original = CanvasRenderingContext2D.prototype.fillRect;
      CanvasRenderingContext2D.prototype.fillRect = function (...args) {
        if (this.canvas.hasAttribute('data-plan-dense-row')) printCanvasMarks.push(args);
        return original.apply(this, args);
      };
      // Installed before mounting the hook: clear once at the start of the native print event, before its flushSync.
      window.addEventListener('beforeprint', () => { window.printCanvasMarks = []; });
    });
    const ref = value => value.toString(16).padStart(48, '0');
    await run(page, 'dom-filtered', { theme: 'light', count: 120, concurrent: true,
      context: { plan_ref: ref(1), selected_task_ref: ref(30090), query: 'BATCH-000' } }, { tasks: 100, count: '100 / 120 道安排' });
    await run(page, 'dense-dark', { theme: 'dark', count: 400, dense: true,
      context: { plan_ref: ref(1), selected_task_ref: ref(30020), query: 'BATCH-00' } }, { dense: true, tasks: 400, count: '400 / 400 道安排' });
    await run(page, 'baseline-expanded', { theme: 'light', count: 120, concurrent: true,
      context: { plan_ref: ref(3), selected_task_ref: ref(70090), query: 'BATCH-000' } }, { expanded: true, baseline: 100, tasks: 200, count: '100 / 120 道安排' });
    await page.setViewportSize({ width: 1920, height: 1080 });
    await run(page, 'wide-expanded-landscape', { theme: 'light', count: 12,
      context: { plan_ref: ref(1), selected_task_ref: ref(30011) } }, { expanded: true, tasks: 12, count: '12 / 12 道安排' });
    await run(page, 'wide-expanded-portrait', { theme: 'dark', count: 400, dense: true,
      context: { plan_ref: ref(1), selected_task_ref: ref(30399) } }, { expanded: true, landscape: false, dense: true, tasks: 400, count: '400 / 400 道安排' });
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []); assert.deepEqual(report.unexpected_requests, []);
  } finally { await browser.close(); await new Promise(resolve => web.close(resolve)); }
}
main().catch(error => { report.failure = error.stack; process.exitCode = 1; }).finally(() => {
  fs.writeFileSync(path.join(output, 'plan-print-result.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ cases: report.cases.length, failure: report.failure || null, output }));
});
