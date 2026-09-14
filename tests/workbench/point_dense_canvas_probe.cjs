'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { chromium } = require('playwright');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const report = { errors: [], external: [], requests: [], variants: [], boundaries: [], screenshots: [],
  scope: 'real-sqlite-engine-adoption-plan-component', global_build: false, production_database: false };
let browser;
async function settled(page) {
  await page.evaluate(async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))); });
}
async function open(page, theme) {
  await page.goto(input.base);
  await page.waitForFunction(() => !!window.openPoint);
  await page.evaluate(spec => openPoint(spec), {kind: 'plan', path: input.path, theme});
  await page.locator('[data-plan-scroll]').waitFor(); await settled(page);
}
async function geometry(page) {
  return page.evaluate(() => {
    const board = document.querySelector('[data-plan-scroll]'), track = document.querySelector('.plan-track');
    const width = track.getBoundingClientRect().width, left = board.scrollLeft;
    const label = parseFloat(getComputedStyle(board).getPropertyValue('--plan-label')), viewport = board.clientWidth - label;
    const data = pointHost.data, model = PlanGanttModel.layout(data, 'machine', '', false, width), scale = width / (model.end - model.start);
    const start = model.start + left / scale, end = model.start + (left + viewport) / scale;
    const rows = Array.from(document.querySelectorAll('.plan-lane')).map(lane => {
      const row = model.rows.find(r => r.top + 52 === parseFloat(lane.style.top));
      const visible = row.point ? PointGanttModel.visible(row.items, start, end, scale) : PlanGanttModel.visibleItems(row.items, start, end);
      const canvas = lane.querySelector('[data-plan-dense-row]');
      let ink = 0;
      if (canvas) { const bytes = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data; for (let i = 3; i < bytes.length; i += 4) if (bytes[i]) ink++; }
      const interior = visible.filter(i => (i.start - model.start) * scale - left > 30 && (i.start - model.start) * scale - left < viewport - 30);
      const item = interior[Math.floor(interior.length / 2)];
      const box = canvas && canvas.getBoundingClientRect().toJSON();
      return {top: row.top, point: row.point, visible: visible.length, total: row.items.length, dense: !!canvas, ink, box,
        refs: row.items.map(i => i.task.task_ref), overlap: row.overlap,
        min_spacing: row.items.slice(1).reduce((m, i, n) => Math.min(m, (i.start - row.items[n].start) * scale), Infinity),
        target: item && {ref: item.task.task_ref, start: item.task.start, end: item.task.end,
          x: (item.start - model.start) * scale - left, center_x: ((item.start + item.end) / 2 - model.start) * scale - left}};
    });
    const normal = {...data, tasks: data.tasks.filter(t => !PointContract.isPoint(t))};
    const normalModel = PlanGanttModel.layout(normal, 'machine', '', false, width);
    return {width, viewport, left, document_width: document.documentElement.scrollWidth, window_width: innerWidth, rows,
      conflicts: [...model.conflicts], normal_conflicts: [...normalModel.conflicts],
      normal_tracks: model.rows.filter(r => !r.point).map(r => r.items.map(i => [i.task.task_ref, i.start, i.end])),
      isolated_normal_tracks: normalModel.rows.map(r => r.items.map(i => [i.task.task_ref, i.start, i.end])),
      dense_point_rows: rows.filter(r => r.point && r.dense).length};
  });
}
function verify(state, dense) {
  assert(state.document_width <= state.window_width + 1, 'No document horizontal overflow');
  assert.deepEqual(state.normal_tracks, state.isolated_normal_tracks, 'Points do not add normal overlap tracks or change normal times');
  assert.deepEqual(state.conflicts, state.normal_conflicts, 'Points do not create conflict colors');
  assert.equal(state.conflicts.length, 0, 'Real sequential schedule has no fabricated conflicts');
  for (const row of state.rows) {
    assert.equal(row.dense, row.visible > 70, 'Actual DOM branch must match actual visible item threshold');
    if (row.dense) assert(row.ink > 100, 'Canvas contains real painted pixels');
    if (row.point) { assert(row.min_spacing >= 28 - .001, 'Point hit areas have at least 28px spacing'); assert.equal(row.overlap, 0); }
  }
  if (dense) assert(state.dense_point_rows > 0, 'PlanGantt must actually choose point DenseRow');
  return state.rows.find(r => r.point && r.dense && r.target);
}
const selected = page => page.evaluate(() => pointHost.selected && pointHost.selected.task.task_ref);
async function choose(page, ref) { await page.waitForFunction(ref => pointHost.selected?.task.task_ref === ref, ref); }
async function hoverAbsent(page) { await settled(page); assert.equal(await page.getByRole('tooltip').count(), 0); }
async function interact(page, state) {
  const row = verify(state, true), canvas = page.locator('[data-plan-dense-row][data-point-row]').filter({visible: true}).first();
  assert(row && row.target);
  const {target, box} = row, x = box.x + target.x, y = box.y + 27;
  // Real pointer offsets, not model-only hit() calls: inside/outside a fixed 24px square.
  for (const [dx, dy] of [[-11, 0], [11, 0], [0, -11], [0, 11]]) {
    await page.mouse.move(x + dx, y + dy);
    await page.getByRole('tooltip').filter({hasText: '零工时工序'}).waitFor();
    await page.mouse.click(x + dx, y + dy); await choose(page, target.ref);
  }
  for (const [dx, dy] of [[-13, 0], [13, 0], [0, -13], [0, 13]]) {
    await page.mouse.move(x + dx, y + dy); await hoverAbsent(page);
    await page.mouse.click(x + dx, y + dy); assert.equal(await selected(page), target.ref, 'Outside point hitbox never chooses adjacent task');
  }
  const normal = state.rows.find(r => !r.point && r.dense && r.target);
  assert(normal, 'Real normal intervals also execute DenseRow');
  await page.mouse.click(normal.box.x + normal.target.center_x, normal.box.y + 27); await choose(page, normal.target.ref);
  assert(await page.evaluate(() => !PointContract.isPoint(pointHost.selected.task)));
  await page.mouse.click(x + 13, y); assert.equal(await selected(page), normal.target.ref, 'Miss outside 24px cannot reselect point');
  await page.mouse.click(x + 11, y); await choose(page, target.ref);
  assert((await page.locator('[data-plan-inspector]').textContent()).includes('0 小时'));
  await canvas.focus();
  const index = row.refs.indexOf(target.ref);
  for (const [key, ref] of [['ArrowRight', row.refs[index + 1]], ['ArrowLeft', target.ref], ['Home', row.refs[0]],
    ['End', row.refs[row.refs.length - 1]], ['Home', row.refs[0]], ['Enter', row.refs[1]], [' ', row.refs[2]]]) {
    await canvas.press(key); await choose(page, ref);
  }
  return {visible: row.visible, total: row.total, ink: row.ink, normal_ink: normal.ink, fixed_hit_size: 24,
    inside_offsets: [-11, 11], outside_offsets: [-13, 13], keyboard: ['ArrowRight', 'ArrowLeft', 'Home', 'End', 'Enter', 'Space']};
}
async function shot(page, name) {
  const file = path.join(input.output, name + '.png'); await page.screenshot({path: file, fullPage: true}); report.screenshots.push(file);
}
async function makePage(viewport) {
  const page = await browser.newPage({viewport});
  page.on('pageerror', error => report.errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
  await page.route('**/*', route => {
    if (new URL(route.request().url()).origin !== input.base) { report.external.push(route.request().url()); return route.abort(); }
    return route.continue();
  });
  page.on('response', r => { if (r.url().includes('/api/')) report.requests.push({url: r.url(), method: r.request().method(), status: r.status()}); });
  return page;
}
(async () => {
  try {
    browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking']});
    report.browser = browser.version(); assert.match(report.browser, /^109\./);
    for (const viewport of [{width: 3600, height: 1200}, {width: 4096, height: 1440}]) for (const theme of ['light', 'dark']) {
      const page = await makePage(viewport), variant = {viewport, theme, phases: [], passed: false}; report.variants.push(variant);
      await open(page, theme); const original = await page.evaluate(() => JSON.stringify(pointHost.data));
      for (const phase of ['fit', 'zoom', 'pan']) {
        if (phase === 'zoom') await page.getByRole('button', {name: '放大时间轴', exact: true}).click();
        if (phase === 'pan') { const pan = page.getByRole('slider', {name: '时间轴水平位置'}); await pan.focus(); await pan.press('End'); }
        await settled(page); const state = await geometry(page);
        if (phase === 'zoom') assert(state.width > state.viewport * 1.9);
        if (phase === 'pan') assert(state.left > state.viewport * .9, 'Real slider keyboard pans to far end');
        variant.phases.push({phase, state, actions: await interact(page, state)});
        await shot(page, viewport.width + '-' + theme + '-' + phase);
      }
      await page.getByRole('button', {name: '放大时间轴', exact: true}).click(); await settled(page);
      const sparse = await geometry(page); verify(sparse, false); assert.equal(sparse.dense_point_rows, 0, 'Higher zoom naturally returns to DOM markers');
      const marker = page.locator('[data-point-ref]').first(); await marker.scrollIntoViewIfNeeded();
      const box = await marker.boundingBox(); assert.equal(box.width, 24); assert.equal(box.height, 24);
      await marker.click(); await marker.press('Enter'); assert.equal(await marker.getAttribute('aria-pressed'), 'true');
      variant.sparse = sparse;
      assert.equal(await page.evaluate(() => JSON.stringify(pointHost.data)), original, 'Zoom, pan, selection and keyboard never mutate official DTO');
      variant.passed = true; await page.close();
    }
    for (const viewport of [{width: 1920, height: 1080}, {width: 1392, height: 924}]) {
      const page = await makePage(viewport); await open(page, 'light');
      const state = await geometry(page); verify(state, false); assert.equal(state.dense_point_rows, 0, 'Normal viewport cannot fit 71 targets with 28px spacing');
      report.boundaries.push({browser_viewport: viewport, ...state}); await shot(page, viewport.width + '-non-dense-boundary'); await page.close();
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
  } catch (error) { report.failure = error.stack; throw error; }
  finally {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(input.output, 'browser-result.json'), JSON.stringify(report, null, 2));
  }
  console.log(JSON.stringify({browser: report.browser, variants: report.variants.length, screenshots: report.screenshots.length}));
})().catch(error => { console.error(error); process.exitCode = 1; });
