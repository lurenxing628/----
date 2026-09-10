'use strict';
const H = require('./az_contrast_modal_harness.cjs'), M = require('./secondary_copy_metrics.cjs');
const { assert } = H;
const selectors = M.surfaces.map(name => '[data-secondary-copy="' + name + '"]');
(async () => {
  const h = await H.setup('secondary_copy');
  try {
    for (const variant of H.variants) {
      const page = await h.page(variant), row = { variant: variant.name, passed: false, states: [] };
      h.report.cases.push(row);
      await page.evaluate(() => azMount('contrast')); await page.locator('[data-secondary-copy]').first().waitFor();
      // Include an absent attribute and repeated live transitions, not only a fresh dark mount.
      for (const theme of [variant.theme, null, 'dark', 'light', 'dark', null]) {
        await page.evaluate(theme => {
          if (theme === null) document.documentElement.removeAttribute('data-theme');
          else document.documentElement.dataset.theme = theme;
        }, theme);
        await H.settle(page);
        const samples = await M.measure(page, selectors), token = await M.tokens(page);
        row.states.push({ theme, samples, tokens: token }); M.readable(samples, selectors);
        samples.forEach(sample => assert.equal(sample.color, theme === 'dark' ? M.dark : M.light));
        assert.equal(token.root['--ui-muted'], theme === 'dark' ? '#94a3b8' : '#64748b');
      }
      await h.shot(page, variant.name + '-default-light');
      await page.evaluate(() => document.documentElement.dataset.theme = 'dark'); await H.settle(page);
      await h.shot(page, variant.name + '-switched-dark');
      await page.evaluate(() => { document.documentElement.dataset.theme = 'light'; document.body.classList.remove('aps-workbench'); });
      await H.settle(page);
      row.outsideWorkbench = await M.measure(page, selectors);
      row.outsideWorkbench.forEach(sample => assert.equal(sample.color, M.original, 'Override escaped workbench body'));
      assert.equal(row.outsideWorkbench.length, 4);
      row.passed = true; await page.close();
    }
    assert.deepEqual(h.report.errors, []); assert.deepEqual(h.report.external, []);
  } finally { await h.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
