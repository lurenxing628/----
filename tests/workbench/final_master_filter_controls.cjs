'use strict';
const assert = require('node:assert/strict');

async function settleScroll(page) {
  await page.waitForFunction(() => {
    const events = window.finalMasterFilterMovement.events;
    return events.length && performance.now() - events[events.length - 1].at >= 300;
  });
}

async function movement(page, probe, head, open) {
  const owner = await head.locator('.wb-th-filter').elementHandle(); assert(owner);
  const before = await page.evaluate(owner => {
    const ancestors = []; for (let node = owner; node; node = node.parentElement) ancestors.push(node);
    const snapshot = () => ancestors.map(node => ({tag: node.tagName, class: node.className,
      value: node.style.getPropertyValue('overflow-anchor'), priority: node.style.getPropertyPriority('overflow-anchor'),
      computed: getComputedStyle(node).overflowAnchor, connected: node.isConnected}));
    window.finalMasterFilterMovement = {owner, ancestors, snapshot}; return snapshot();
  }, owner);
  await owner.dispose();
  const row = {variant: probe.variant, column: await head.getAttribute('data-column-key'), before, passed: false};
  probe.report.filter_scroll = (probe.report.filter_scroll || []).concat(row);
  await open(head);
  const panel = page.locator('[data-wb-table-filter]'), options = panel.locator('.wb-table-facet-options');
  await options.waitFor();
  row.opened = await page.evaluate(() => {
    const value = window.finalMasterFilterMovement;
    value.panel = document.querySelector('[data-wb-table-filter]'); value.events = [];
    value.capture = event => value.events.push({type: event.type, trusted: event.isTrusted, at: performance.now(),
      target: event.target === document ? '#document' : event.target.tagName + '.' + event.target.className,
      top: document.scrollingElement.scrollTop, left: document.scrollingElement.scrollLeft});
    document.addEventListener('wheel', value.capture, {capture: true, passive: true});
    document.addEventListener('scroll', value.capture, {capture: true, passive: true});
    return value.snapshot();
  });
  try {
    assert(row.opened.every(node => node.value === 'none' && node.priority === 'important' && node.computed === 'none'));
    row.internal_before = await options.evaluate(node => ({top: node.scrollTop, height: node.clientHeight, scrollHeight: node.scrollHeight}));
    assert(row.internal_before.scrollHeight > row.internal_before.height + 20, 'Real facet values must fill a scrollable menu');
    const rect = await options.boundingBox(); assert(rect);
    probe.step('wheel', 'facet internal options', 160);
    await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height / 2); await page.mouse.wheel(0, 160);
    await page.waitForFunction(top => document.querySelector('.wb-table-facet-options')?.scrollTop > top, row.internal_before.top);
    await settleScroll(page);
    row.internal_after = await options.evaluate(node => ({top: node.scrollTop, height: node.clientHeight, scrollHeight: node.scrollHeight}));
    assert(await page.evaluate(() => window.finalMasterFilterMovement.panel === document.querySelector('[data-wb-table-filter]')),
      'Internal wheel replaced or closed the original facet menu');
    const initial = await page.evaluate(() => ({top: scrollY, left: scrollX, width: innerWidth,
      maximum: document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight}));
    assert(initial.maximum > 20, 'Real document must be scrollable for the outside-wheel assertion');
    const delta = initial.top > 20 ? -160 : 160;
    probe.step('wheel', 'outside facet menu', {x: initial.width - 40, y: 80, delta});
    await page.mouse.move(initial.width - 40, 80); await page.mouse.wheel(0, delta);
    await page.waitForFunction(top => Math.abs(scrollY - top) > 1, initial.top);
    await panel.waitFor({state: 'detached'});
    await settleScroll(page);
    row.after = await page.evaluate(() => window.finalMasterFilterMovement.snapshot());
    assert.deepEqual(row.after, before, 'Facet close did not restore exact ancestor overflow-anchor state');
  } finally {
    row.events = await page.evaluate(() => {
      const value = window.finalMasterFilterMovement;
      document.removeEventListener('wheel', value.capture, true); document.removeEventListener('scroll', value.capture, true);
      return value.events;
    });
  }
  assert.equal(row.events.filter(event => event.type === 'wheel' && event.trusted).length, 2, 'Both wheel gestures must be real browser events');
  row.passed = true;
}

module.exports = {movement};
