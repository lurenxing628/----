'use strict';
const assert = require('node:assert/strict');
const {resize} = require('./final_master_resize_trace.cjs');
const {originalFocus} = require('./final_master_modal_controls.cjs');

async function geometry(scope) {
  return scope.locator('table.wb-table').evaluate(table => ({width: table.getBoundingClientRect().width,
    inline: table.style.width, minimum: table.style.minWidth,
    columns: [...table.querySelectorAll('thead th')].map(node => ({key: node.dataset.column,
      width: node.getBoundingClientRect().width, inline: node.style.width}))}));
}

function precise(before, after, key, expected) {
  assert.equal(after.minimum, '0px');
  assert.deepEqual(after.columns.map(row => row.key), ['__selection', 'business_code', 'label', 'operation_count', 'stage', '__actions']);
  for (const row of after.columns) {
    const old = before.columns.find(item => item.key === row.key); assert(old);
    assert(Math.abs(row.width - (row.key === key ? expected : old.width)) <= 1,
      'Resizing ' + key + ' unexpectedly changed column ' + row.key + ': ' + row.width);
    assert(Math.abs(row.width - Number.parseFloat(row.inline)) <= 1, 'Rendered column differs from its pinned width');
  }
  assert(Math.abs(after.width - after.columns.reduce((total, row) => total + row.width, 0)) <= 1, 'Table width must equal all pinned columns');
  assert(Math.abs(Number.parseFloat(after.inline) - after.width) <= 1, 'Actual table did not use its explicit total width');
}

async function verify(page, probe, scope, head) {
  const separator = head.getByRole('separator'), key = 'business_code';
  const report = {variant: probe.variant, contracts: [], passed: false};
  probe.report.process_resize = (probe.report.process_resize || []).concat(report);
  const label = await separator.getAttribute('aria-label');
  const first = probe.report.column_resize.filter(row => row.variant === probe.variant && row.label === label).slice(-1)[0];
  assert(first && first.passed && first.amount === 24);
  const initialAfter = await geometry(scope);
  precise(first.before, initialAfter, key, first.before.value + 24);
  report.contracts.push({name: 'initial-drag-all-columns-preserved', before: first.before, after: initialAfter, passed: true});
  await originalFocus(page, head.locator('.wb-th-filter'));
  probe.step('press', 'focused filter owner', 'Tab'); await page.keyboard.press('Tab');
  await originalFocus(page, separator);
  for (const [pressed, delta] of [['ArrowRight', 8], ['Shift+ArrowRight', 32], ['ArrowLeft', -8], ['Home', null], ['ArrowLeft', 0]]) {
    const before = await geometry(scope), value = Number(await separator.getAttribute('aria-valuenow'));
    const expected = pressed === 'Home' ? 56 : value + delta;
    probe.step('press', 'focused process separator', pressed); await page.keyboard.press(pressed);
    await page.waitForFunction(({label, expected}) => Number(document.querySelector('[aria-label="' + label + '"]').getAttribute('aria-valuenow')) === expected,
      {label: await separator.getAttribute('aria-label'), expected});
    const after = await geometry(scope); precise(before, after, key, expected);
    assert(await separator.evaluate(node => node === document.activeElement), 'Keyboard resize lost separator focus');
    report.contracts.push({name: pressed === 'Home' ? 'minimum-width' : pressed + '-' + delta, before, after, expected, passed: true});
  }
  await probe.shot('process-resize-minimum');
  for (const amount of [24, 24, -12]) {
    const before = await geometry(scope), expected = Number(await separator.getAttribute('aria-valuenow')) + amount;
    await resize(page, probe, separator, amount);
    const after = await geometry(scope); precise(before, after, key, expected);
    report.contracts.push({name: 'repeat-drag-' + amount, before, after, expected, passed: true});
  }
  const before = await geometry(scope), start = Number(await separator.getAttribute('aria-valuenow'));
  const styles = () => page.evaluate(() => ['cursor', 'user-select'].map(name => [name,
    document.body.style.getPropertyValue(name), document.body.style.getPropertyPriority(name)]));
  const styleBefore = await styles(), rect = await separator.boundingBox(); assert(rect);
  probe.step('pointer-drag-cancel', separator, {dx: 40, cancel: 'Escape'});
  await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height / 2); await page.mouse.down();
  try {
    await page.mouse.move(rect.x + rect.width / 2 + 40, rect.y + rect.height / 2, {steps: 8});
    await page.waitForFunction(({label, value}) => { const node = document.querySelector('[aria-label="' + label + '"]');
      return node.getAttribute('data-dragging') === 'true' && Number(node.getAttribute('aria-valuenow')) === value;
    }, {label: await separator.getAttribute('aria-label'), value: start + 40});
    assert.equal(Number(await separator.getAttribute('aria-valuenow')), start + 40);
    probe.step('press', 'active pointer drag', 'Escape'); await page.keyboard.press('Escape');
    await page.waitForFunction(({label, start}) => { const node = document.querySelector('[aria-label="' + label + '"]');
      return node.getAttribute('data-dragging') === null && Number(node.getAttribute('aria-valuenow')) === start;
    }, {label: await separator.getAttribute('aria-label'), start});
  } finally { await page.mouse.up(); }
  const after = await geometry(scope); precise(before, after, key, start);
  assert.deepEqual(await styles(), styleBefore, 'Cancel did not restore cursor and selection styles');
  report.contracts.push({name: 'escape-cancel-drag', before, after, expected: start, passed: true});
  const other = scope.locator('.wb-resource-th[data-column-key="label"]').getByRole('separator');
  const otherBefore = await geometry(scope), expected = Number(await other.getAttribute('aria-valuenow')) + 24;
  await resize(page, probe, other, 24);
  const otherAfter = await geometry(scope); precise(otherBefore, otherAfter, 'label', expected);
  report.contracts.push({name: 'other-column-repeat', before: otherBefore, after: otherAfter, expected, passed: true});
  await probe.shot('process-resize-repeated-and-canceled');
  report.passed = true;
}

module.exports = {verify};
