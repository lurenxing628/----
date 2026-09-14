'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { chromium } = require('playwright');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const report = { errors: [], external: [], screenshots: [], requests: [], selections: [], geometry: [], main_page: false };
let browser;
async function settled(page) { await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))); }
async function size(page, kind) {
  const value = await page.evaluate(() => ({ width: innerWidth, document: document.documentElement.scrollWidth }));
  assert(value.document <= value.width + 1, JSON.stringify(value)); report.geometry.push({ kind, ...value });
}
async function candidateHit(page, piece) {
  const canvas = page.locator('[data-candidate-lane]').first(); await canvas.waitFor(); await canvas.scrollIntoViewIfNeeded();
  const point = await canvas.evaluate((node, piece) => {
    const data = pieceHost.data, w = node.getBoundingClientRect().width;
    const model = RunCandidateModel.layout(data, 'machine', piece, w), item = model.rows[0].items[0];
    const pixels = node.getContext('2d').getImageData(0, 0, node.width, node.height).data;
    let ink = 0; for (let i = 3; i < pixels.length; i += 4) if (pixels[i]) ink++;
    return { x: ((item.start + item.end) / 2 - model.start) / (model.end - model.start) * w, y: 24, ink };
  }, piece);
  assert(point.ink > 100, 'Candidate canvas must contain real bars');
  await canvas.hover({ position: { x: point.x, y: point.y } });
  assert((await page.getByRole('tooltip').innerText()).includes(piece));
  await canvas.click({ position: { x: point.x, y: point.y } });
}
(async () => {
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
    report.browser = browser.version();
    for (const [width, theme] of [[1920, 'light'], [1392, 'dark']]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } });
      page.setDefaultTimeout(15000);
      page.on('pageerror', error => report.errors.push(String(error)));
      page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
      page.on('request', request => {
        if (!request.url().startsWith(input.base + '/')) report.external.push(request.url());
        if (request.url().includes('/api/')) report.requests.push({ method: request.method(), url: request.url() });
      });
      await page.goto(input.base); await page.waitForFunction(() => !!window.openPiece);
      for (const kind of ['candidate', 'plan', 'trial', 'old']) {
        const payload = await page.evaluate(spec => openPiece(spec), { kind, theme, path: input.paths[kind] });
        await page.waitForFunction(kind => window.pieceHost?.kind === kind, kind); await settled(page);
        if (kind === 'plan' || kind === 'old') {
          assert.equal(await page.evaluate(() => pieceHost.asOf), payload.meta.as_of, 'Plan time markers must use the real HTTP data timestamp');
        }
        const original = JSON.stringify(payload.data.tasks);
        if (kind === 'old') {
          await page.locator('[data-plan-task]').first().click();
          const detail = await page.locator('[data-plan-inspector]').innerText();
          assert(detail.includes('本工序目标量') && detail.includes('未知') && detail.includes('没有拿当前批次数量代替'));
        } else for (const piece of input.pieces) {
          const name = kind === 'candidate' ? '搜索候选工序' : kind === 'plan' ? '搜索批次、工序、设备、人员' : '搜索试调工序';
          await page.getByRole('searchbox', { name, exact: true }).fill(piece); await settled(page);
          if (kind === 'candidate') await candidateHit(page, piece);
          if (kind === 'plan') {
            const bar = page.getByRole('button', { name: new RegExp('B1 · 20 Turning[\\s\\S]*' + piece) });
            assert.equal(await bar.count(), 1); await bar.hover();
            assert((await page.getByRole('tooltip').innerText()).includes(piece));
            await bar.click();
            const geometry = await bar.evaluate(node => {
              const task = pieceHost.selected.task, track = node.closest('.plan-track'), b = node.getBoundingClientRect(), parent = track.getBoundingClientRect();
              const model = PlanGanttModel.layout(pieceHost.data, 'machine', pieceHost.query, false, parent.width);
              return { width: b.width, expected: (PlanGanttModel.instant(task.end) - PlanGanttModel.instant(task.start)) / (model.end - model.start) * parent.width };
            });
            assert(Math.abs(geometry.width - geometry.expected) < 1, 'Piece label cannot inflate physical time bar');
            report.geometry.push({ kind, ...geometry });
          }
          if (kind === 'trial') {
            const label = page.getByRole('button', { name: '选择工序 B1 · 20 Turning · 分件 ' + piece, exact: true });
            assert.equal(await label.count(), 1); assert((await label.getAttribute('title')).includes(piece));
            await label.click();
            const bar = page.getByRole('button', { name: '安排时段 B1 · 20 Turning · 分件 ' + piece, exact: true });
            assert((await bar.getAttribute('title')).includes('本工序目标量 1 · 整批量 3'));
          }
          const detail = page.locator(kind === 'candidate' ? '.rc-detail' : kind === 'plan' ? '[data-plan-inspector]' : '.tt-detail');
          assert((await detail.innerText()).includes(piece));
          report.selections.push({ kind, width, theme, piece, visible_business_selection: true });
        }
        await settled(page); await size(page, kind);
        assert.equal(await page.evaluate(() => JSON.stringify(pieceHost.data.tasks)), original, 'View must not mutate real task DTOs');
        const filename = path.join(input.output, width + '-' + theme + '-' + kind + '.png');
        await page.screenshot({ path: filename, fullPage: true }); report.screenshots.push(filename);
      }
      await page.close();
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
  } finally {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(input.output, 'browser-report.json'), JSON.stringify(report, null, 2));
  }
  console.log(JSON.stringify({ screenshots: report.screenshots.length, selections: report.selections.length, main_page: false }));
})().catch(error => { console.error(error); process.exitCode = 1; });
