'use strict';
const H = require('./az_contrast_modal_harness.cjs'), { assert } = H;
const selectors = [
  '[data-process-source-editor] .segm button.on.int', '[data-process-source-editor] .segm button.on.ext',
  '[data-process-source-editor] .segm button:not(.on)', '.stp.active .stp-n', '.stp.done .stp-n',
  '.stp:not(.active):not(.done) .stp-n', '.stp .stp-t', '.stp .stp-s', '.subtab.on .cnt', '.subtab:not(.on) .cnt',
  '.seg.re-mode button.on', '.seg.re-mode button:not(.on)', '.toolbar button.btn.primary', '.toolbar button.btn.danger'
];
async function colors(page, targets = selectors) {
  return page.evaluate(targets => {
    const parse = value => { const parts = value.match(/[\d.]+/g).map(Number); return parts.length === 3 ? parts.concat(1) : parts; };
    const over = (front, back) => {
      const alpha = front[3] + back[3] * (1 - front[3]);
      return alpha ? front.slice(0, 3).map((value, i) => (value * front[3] + back[i] * back[3] * (1 - front[3])) / alpha).concat(alpha) : [0, 0, 0, 0];
    };
    const luminance = value => value.slice(0, 3).map(channel => {
      const n = channel / 255; return n <= .04045 ? n / 12.92 : Math.pow((n + .055) / 1.055, 2.4);
    }).reduce((sum, n, i) => sum + n * [.2126, .7152, .0722][i], 0);
    return targets.flatMap(selector => [...document.querySelectorAll(selector)].map((node, index) => {
      const style = getComputedStyle(node); let bg = [0, 0, 0, 0], opacity = 1;
      for (let parent = node; parent; parent = parent.parentElement) {
        const current = getComputedStyle(parent);
        bg = over(bg, parse(current.backgroundColor)); opacity *= Number(current.opacity);
      }
      // These opaque-token controls must not conceal poor contrast behind opacity/filter effects.
      const foreground = over(parse(style.color), bg), a = luminance(foreground), b = luminance(bg);
      const button = node.closest('button');
      return { selector, index, text: node.textContent, color: style.color, background: style.backgroundColor,
        effectiveBackground: bg, ratio: (Math.max(a, b) + .05) / (Math.min(a, b) + .05), opacity,
        filter: style.filter, buttonFilter: button && getComputedStyle(button).filter,
        shadow: style.boxShadow, outline: style.outlineStyle, outlineColor: style.outlineColor,
        focusVisible: node.matches(':focus-visible'), disabled: !!(button && button.disabled) };
    }));
  }, targets);
}
function assertColors(samples) {
  assert(samples.length > 0, 'No contrast targets');
  selectors.forEach(selector => assert(samples.some(sample => sample.selector === selector), 'Missing control: ' + selector));
  for (const sample of samples) {
    assert.equal(sample.effectiveBackground[3], 1, sample.selector + ' needs a known opaque background');
    assert.equal(sample.opacity, 1, sample.selector + ' must not fade readable text');
    assert(sample.ratio >= 4.5, JSON.stringify(sample));
  }
}
async function keyboardFocus(page, selector) {
  for (let index = 0; index < 100; index++) {
    await page.keyboard.press('Tab');
    if (await page.evaluate(selector => document.activeElement.matches(selector), selector)) return;
  }
  throw new Error('Tab could not reach ' + selector);
}
(async () => {
  const h = await H.setup('contrast');
  try {
    for (const variant of H.variants) {
      const page = await h.page(variant), row = { variant: variant.name, passed: false, states: [] };
      h.report.cases.push(row);
      await page.evaluate(() => azMount('contrast')); await page.locator('[data-process-source-editor]').waitFor(); await H.settle(page);
      const sample = async name => {
        await H.settle(page); const samples = await colors(page); row.states.push({ name, samples });
        return samples;
      };
      const normal = await sample('normal'); await h.shot(page, variant.name + '-normal'); assertColors(normal);
      row.secondaryCopy = await colors(page, ['[data-secondary-copy]']);
      assert.equal(row.secondaryCopy.length, 4);
      for (const copy of row.secondaryCopy) {
        assert.equal(copy.color, variant.theme === 'dark' ? 'rgb(148, 163, 184)' : 'rgb(96, 112, 135)');
        assert.equal(copy.effectiveBackground[3], 1); assert.equal(copy.opacity, 1);
        assert(copy.ratio >= 4.5, JSON.stringify(copy));
      }
      assert.notEqual(normal[0].background, normal[1].background, 'Self-made and outsourced categories collapsed');
      assert.notEqual(normal[0].background, normal[2].background, 'Selected and unselected collapsed');
      const interactive = ['[data-process-source-editor] .segm button.on.int', '[data-process-source-editor] .segm button.on.ext',
        '.seg.re-mode button.on', '.stp.active', '.subtab.on'];
      for (const selector of interactive) {
        await page.locator(selector).hover(); assertColors(await sample('hover:' + selector));
        await page.mouse.down(); assertColors(await sample('active:' + selector)); await page.mouse.up();
        await page.mouse.move(2, 2); await keyboardFocus(page, selector);
        assertColors(await sample('focus:' + selector));
        const focused = (await colors(page, [selector]))[0];
        assert(focused.focusVisible && focused.outline === 'solid', 'Missing keyboard focus: ' + selector);
        assert.equal(focused.shadow, 'none', 'Unexpected inset border: ' + selector);
        assert.notEqual(focused.outlineColor, 'rgb(255, 255, 255)', 'White focus ring');
      }
      await h.shot(page, variant.name + '-focus');
      // Actual source controls must still update pressed/category state under mouse input.
      const source = page.locator('[data-process-source-editor] .segm').first();
      await source.getByRole('button', { name: '外协', exact: true }).click();
      assert.equal(await source.getByRole('button', { name: '外协', exact: true }).getAttribute('aria-pressed'), 'true');
      await source.getByRole('button', { name: '自制', exact: true }).click();
      await page.evaluate(() => az.disable(true)); await H.settle(page);
      const disabled = await sample('disabled'); await h.shot(page, variant.name + '-disabled'); assertColors(disabled);
      assert(disabled.every(item => item.disabled)); assert.notEqual(disabled[0].background, disabled[1].background);
      for (const selector of interactive) {
        await page.locator(selector).hover(); assertColors(await sample('disabled-hover:' + selector));
      }
      const geometry = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth > innerWidth,
        clipped: [...document.querySelectorAll('.segm button,.stp,.subtab,.seg button')].filter(node => node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1).map(node => node.textContent) }));
      row.geometry = geometry; assert(!geometry.overflow); assert.deepEqual(geometry.clipped, []);
      row.passed = true; await page.close();
    }
    assert.deepEqual(h.report.errors, []); assert.deepEqual(h.report.external, []);
  } finally { await h.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
