'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { chromium } = require('playwright');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const evidence = { errors: [], requests: [], captions: [], metrics: [], screenshots: [] };
async function main() {
  const browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
  evidence.browser = browser.version();
  try {
    const page = await browser.newPage({ viewport: { width: 1392, height: 900 }, timezoneId: 'America/New_York' });
    page.on('pageerror', error => evidence.errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') evidence.errors.push(message.text()); });
    page.on('request', request => evidence.requests.push({ url: request.url(), method: request.method() }));
    await page.goto(input.base + '/?view=analysis');
    await page.locator('[data-plan-workspace]').waitFor();
    await page.evaluate(() => APSWorkbenchTheme.set('dark'));
    await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
    await page.evaluate(() => {
      const original = APSPlanContract.workspace;
      const freeze = value => {
        if (value && typeof value === 'object' && !Object.isFrozen(value)) {
          Object.values(value).forEach(freeze); Object.freeze(value);
        }
        return value;
      };
      APSPlanContract.workspace = function (...args) {
        const result = original(...args);
        window.faCaptionDTO = freeze(result); window.faCaptionBefore = JSON.stringify(result);
        return result;
      };
    });
    let key = 0;
    for (const fixture of input.fixtures.concat(input.fixtures.slice(0, 1))) {
      await page.evaluate(({ planRef, scope, key }) => {
        window.faCaptionDTO = null;
        history.pushState({ workbench: { view: 'analysis', context: { plan_ref: planRef, ...scope }, key } }, '', '/?view=analysis');
        dispatchEvent(new PopStateEvent('popstate'));
      }, { planRef: input.plan_ref, scope: fixture.scope, key: ++key });
      await page.waitForFunction(() => window.faCaptionDTO !== null);
      const note = page.locator('[data-plan-workspace] .plan-scope-caption');
      await note.waitFor();
      const text = (await note.innerText()).trim();
      const suffix = fixture.scope.range_start ? ' · 显示所选时间段内的工序安排' : '';
      assert.equal(text, fixture.caption + suffix);
      const actual = await page.evaluate(() => {
        if (JSON.stringify(faCaptionDTO) !== faCaptionBefore) throw new Error('UI mutated the source DTO');
        return faCaptionDTO.data;
      });
      assert.deepEqual(actual, fixture.payload.data, 'Business span, scope, hours and task refs stay unchanged');
      assert.equal(await page.locator('[role=alert]').count(), 0);
      const metrics = await page.locator('[data-plan-workspace] .plan-scope > .wb-metrics > .wb-metric').evaluateAll(nodes => nodes.map(node => ({
        label: node.querySelector('.wb-metric-label').textContent, value: node.querySelector('.wb-metric-value').textContent,
        tone: node.dataset.tone, color: getComputedStyle(node.querySelector('.wb-metric-value')).color, neutral: getComputedStyle(node).color,
        background: getComputedStyle(node).backgroundColor, font: getComputedStyle(node.querySelector('.wb-metric-value')).font
      })));
      assert.equal(metrics.length, 4);
      assert.deepEqual(metrics.slice(0, 2).map(row => row.tone), ['primary', 'primary'], 'Other indicators keep their tones');
      for (const [index, risk, label] of [[2, 'overdue', '已确认预计超期'], [3, 'unknown', '交付风险暂无数据']]) {
        const count = actual.projections.delivery_risks.items.filter(row => row.risk === risk).length, metric = metrics[index];
        assert.equal(metric.label, label); assert.equal(metric.value, String(count));
        assert.equal(metric.tone, count === 0 ? 'neutral' : 'warn');
        assert.equal(metric.color === metric.neutral, count === 0, 'Known zero is neutral; positive risk remains a warning');
        assert.equal(metric.background, metrics[0].background); assert.equal(metric.font, metrics[0].font);
      }
      evidence.metrics.push({ name: fixture.name, metrics });
      await page.setViewportSize({ width: 1392, height: 900 });
      const metricFile = path.join(input.output, fixture.name + '-' + key + '-metrics-dark.png');
      await page.locator('[data-plan-workspace] .plan-scope > .wb-metrics').screenshot({ path: metricFile }); evidence.screenshots.push(metricFile);
      for (const width of [1392, 390]) {
        await page.setViewportSize({ width, height: 900 });
        assert.ok(await note.evaluate(node => node.scrollWidth <= node.clientWidth + 1), 'Caption fits its container');
        const file = path.join(input.output, fixture.name + '-' + key + '-' + width + '.png');
        await note.screenshot({ path: file }); evidence.screenshots.push(file);
      }
      evidence.captions.push({ name: fixture.name, text, task_count: actual.task_count });
    }
    assert.ok(evidence.browser.startsWith('109.'));
    assert.deepEqual(evidence.errors, []);
    assert.ok(evidence.requests.every(row => row.method === 'GET' && row.url.startsWith(input.base)));
  } finally { await browser.close(); }
}
main().catch(error => { evidence.failure = error.stack; process.exitCode = 1; console.error(error.stack); }).finally(() => {
  fs.writeFileSync(path.join(input.output, 'caption-result.json'), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence));
});
