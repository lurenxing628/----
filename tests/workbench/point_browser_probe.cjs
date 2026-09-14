'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { chromium } = require('playwright');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const report = { errors: [], external: [], screenshots: [], requests: [], actions: [], geometry: [], production_database: false };
let browser;
async function settled(page) { await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))); }
async function pointHit(page, locator, kind) {
  await locator.waitFor(); await locator.scrollIntoViewIfNeeded(); await settled(page);
  const box = await locator.boundingBox(); assert(box && box.width === 24 && box.height === 24, 'Fixed point hitbox');
  const ref = await locator.getAttribute('data-point-ref');
  const at = await locator.getAttribute('data-point-at');
  const center = { x: box.x + 12, y: box.y + 12 };
  const hit = await page.evaluate(({x, y, ref}) => document.elementFromPoint(x, y)?.closest('[data-point-ref]')?.dataset.pointRef === ref, {...center, ref});
  assert(hit, 'Point is topmost clickable target');
  await page.mouse.move(center.x, center.y);
  await page.getByRole('tooltip').filter({hasText: '零工时工序'}).waitFor();
  // A real click outside the visible diamond but inside its explicit hit region.
  await page.mouse.click(center.x + 10, center.y);
  await page.waitForFunction(({ref, kind}) => {
    const selected = window.pointHost.selected;
    return kind === 'trial' ? selected === ref : kind === 'plan' ? selected?.task.task_ref === ref : selected?.row_ref === ref;
  }, {ref, kind});
  report.actions.push({kind, type: 'mouse-hover-and-offset-click', ref, at, hitbox: box});
}
async function checkGeometry(page, kind) {
  const value = await page.evaluate(() => {
    const nodes = Array.from(document.querySelectorAll('[data-point-ref]')).map(n => ({ref: n.dataset.pointRef, box: n.getBoundingClientRect().toJSON()}));
    const overlap = [];
    for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i].box, b = nodes[j].box;
      if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > .5 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > .5) overlap.push([nodes[i].ref, nodes[j].ref]);
    }
    return {width: innerWidth, document: document.documentElement.scrollWidth, nodes: nodes.length, overlap};
  });
  assert(value.document <= value.width + 1, 'No page horizontal overflow: ' + JSON.stringify(value));
  assert.deepEqual(value.overlap, [], 'Point targets do not overlap');
  report.geometry.push({kind, ...value});
}
(async () => {
  try {
    browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking']});
    report.browser = browser.version(); assert.match(report.browser, /^109\./);
    for (const viewport of [{width: 1920, height: 1080}, {width: 1392, height: 924}]) for (const theme of ['light', 'dark']) {
      const page = await browser.newPage({viewport});
      page.on('pageerror', error => report.errors.push(error.message));
      page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
      await page.route('**/*', route => {
        if (new URL(route.request().url()).origin !== input.base) { report.external.push(route.request().url()); return route.abort(); }
        return route.continue();
      });
      page.on('response', response => { if (response.url().includes('/api/')) report.requests.push({url: response.url(), status: response.status(), method: response.request().method()}); });
      await page.goto(input.base); await page.waitForFunction(() => !!window.openPoint);
      for (const kind of ['plan', 'candidate', 'trial']) {
        const payload = await page.evaluate(spec => window.openPoint(spec), {kind, path: input.paths[kind], theme});
        await page.waitForFunction(kind => window.pointHost?.kind === kind && document.querySelector('[data-point-ref]'), kind);
        await settled(page); await checkGeometry(page, kind);
        const original = JSON.stringify(payload.data.tasks);
        if (input.identity.mixed && kind !== 'trial') {
          const canvas = page.locator(kind === 'plan' ? '[data-plan-dense-row]:not([data-point-row])' : '[data-candidate-lane]').first();
          await canvas.waitFor();
          const ink = await canvas.evaluate(n => {
            const pixels = n.getContext('2d').getImageData(0, 0, n.width, n.height).data;
            let count = 0; for (let i = 3; i < pixels.length; i += 4) if (pixels[i]) count++; return count;
          });
          assert(ink > 100, 'Normal bars canvas actually painted');
          const position = await canvas.evaluate((node, kind) => {
            const data = window.pointHost.data, w = node.getBoundingClientRect().width;
            const m = kind === 'plan' ? PlanGanttModel.layout(data, 'machine', '', false, w) : RunCandidateModel.layout(data, 'machine', '', w);
            const item = m.rows.find(r => !r.point).items[0];
            return {x: ((item.start + item.end) / 2 - m.start) / (m.end - m.start) * w, y: 24};
          }, kind);
          await canvas.click({position});
          assert(await page.evaluate(kind => !PointContract.isPoint(kind === 'plan' ? pointHost.selected?.task : pointHost.selected), kind));
          report.actions.push({kind, type: 'normal-canvas-pixel-and-click', painted_pixels: ink});
        }
        const search = page.getByRole('searchbox', {name: kind === 'plan' ? '搜索批次、工序、设备、人员' : kind === 'candidate' ? '搜索候选工序' : '搜索试调工序'});
        await search.click(); await search.type('Point 00'); await settled(page);
        report.actions.push({kind, type: 'keyboard-type-search', value: 'Point 00'});
        const marker = page.locator(kind === 'trial' ? '[data-point-ref][data-task-ref]' : '[data-point-ref]:not([data-before])').first();
        await pointHit(page, marker, kind);
        const detail = page.locator(kind === 'plan' ? '[data-plan-inspector]' : kind === 'candidate' ? '[data-candidate-point-facts]' : '.tt-detail');
        assert((await detail.textContent()).includes('0 小时'), 'Detail shows zero occupancy');
        if (kind === 'plan') {
          await page.getByRole('checkbox', {name: '显示初始计划', exact: true}).check(); await settled(page);
          await pointHit(page, page.locator('[data-point-ref][data-before]').first(), kind);
          assert((await detail.textContent()).includes('初始计划安排'));
          await page.getByRole('checkbox', {name: '显示初始计划', exact: true}).uncheck();
          await page.getByRole('button', {name: '查看当前安排', exact: true}).click();
        }
        const zoomName = kind === 'plan' ? '放大时间轴' : kind === 'candidate' ? '放大候选时间轴' : '放大甘特';
        await page.getByRole('button', {name: zoomName, exact: true}).click();
        await page.getByRole('button', {name: zoomName, exact: true}).click();
        if (kind === 'plan') await page.getByRole('button', {name: '定位选中任务', exact: true}).click();
        await settled(page); await pointHit(page, marker, kind);
        await marker.focus(); await marker.press('Enter'); await settled(page);
        assert.equal(await marker.getAttribute('aria-pressed'), 'true', 'Keyboard can select points');
        report.actions.push({kind, type: 'zoom-pan-point-click-and-keyboard'});
        if (kind === 'plan') await page.getByRole('button', {name: '显示完整时间范围', exact: true}).click();
        else {
          const shrink = kind === 'candidate' ? '缩小候选时间轴' : '缩小甘特';
          await page.getByRole('button', {name: shrink, exact: true}).click();
          await page.getByRole('button', {name: shrink, exact: true}).click();
        }
        if (kind === 'trial') {
          const originalPoint = await page.evaluate(() => pointHost.data.tasks.find(t => t.task_ref === pointHost.selected));
          await page.getByRole('button', {name: '调整此工序', exact: true}).click();
          const datetime = page.getByRole('textbox', {name: '调整开工', exact: true});
          // The unchanged local control bridge presents a text editor for datetime-local.
          const editor = await datetime.count() ? datetime : page.locator('input[aria-label="调整开工"]').first();
          await editor.click(); await editor.press('ControlOrMeta+A');
          const target = '2026-09-09T08:00:0' + (viewport.width === 1920 ? theme === 'light' ? 3 : 4 : theme === 'light' ? 5 : 6);
          if (await editor.getAttribute('type') === 'datetime-local') await editor.fill(target);
          else { await editor.type(target.replace('T', ' ')); await editor.press('Tab'); }
          await page.getByRole('button', {name: '保存调整', exact: true}).click();
          await page.waitForFunction(target => window.pointLastReceipt?.data.tasks.some(t => t.process_label === 'Point 00' && t.start === target && t.end === target), target);
          const changed = await page.evaluate(() => pointHost.data.tasks.find(t => t.task_ref === pointHost.selected));
          assert.equal(changed.operation_ref, originalPoint.operation_ref); assert.equal(changed.task_ref, originalPoint.task_ref);
          assert.equal(changed.duration_seconds, 0); assert.equal(changed.occupies_resources, false);
          const beforeAt = await page.locator('[data-baseline-ref="' + changed.task_ref + '"]').getAttribute('data-point-at');
          assert.equal(beforeAt, changed.original.start, 'Original marker retains its own timestamp');
          report.actions.push({kind, type: 'real-trial-change-command', start: changed.start, end: changed.end, operation_ref: changed.operation_ref});
        } else assert.equal(await page.evaluate(() => JSON.stringify(pointHost.data.tasks)), original, 'View interactions never change source tasks');
        await search.click(); await search.press('ControlOrMeta+A'); await search.press('Backspace'); await settled(page);
        await checkGeometry(page, kind);
        const filename = path.join(input.output, viewport.width + '-' + theme + '-' + kind + '.png');
        await page.screenshot({path: filename, fullPage: true}); report.screenshots.push(filename);
      }
      await page.close();
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
    assert(report.requests.some(r => r.method === 'POST' && r.status === 200), 'Actual trial commands reached routes');
  } finally {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(input.output, 'browser-result.json'), JSON.stringify(report, null, 2));
  }
  console.log(JSON.stringify({browser: report.browser, screenshots: report.screenshots.length, actions: report.actions.length}));
})().catch(error => { console.error(error); process.exitCode = 1; });
