'use strict';
const assert = require('node:assert/strict');

async function resize(page, probe, separator, amount) {
  await separator.scrollIntoViewIfNeeded();
  const handle = await separator.elementHandle(); assert(handle);
  const before = await page.evaluate(node => {
    const th = node.closest('th'), table = th.closest('table'), events = [];
    const snapshot = () => ({value: Number(node.getAttribute('aria-valuenow')), connected: node.isConnected,
      disabled: node.getAttribute('aria-disabled'), dragging: node.getAttribute('data-dragging'),
      separator: node.getBoundingClientRect().toJSON(), table: table.getBoundingClientRect().toJSON(), table_style: table.getAttribute('style'),
      columns: [...table.querySelectorAll('thead th')].map(column => ({key: column.dataset.column, label: column.querySelector('.wb-th-title')?.textContent || '', width: column.getBoundingClientRect().width,
        inline: column.style.width, box_sizing: getComputedStyle(column).boxSizing,
        padding_left: getComputedStyle(column).paddingLeft, padding_right: getComputedStyle(column).paddingRight}))});
    const capture = event => events.push({type: event.type, at: performance.now(), x: event.clientX, y: event.clientY,
      pointer: event.pointerId, trusted: event.isTrusted, captured: node.hasPointerCapture(event.pointerId),
      target: event.target.tagName + '.' + event.target.className, snapshot: snapshot()});
    const names = ['pointerdown', 'pointermove', 'pointerup', 'pointercancel', 'gotpointercapture', 'lostpointercapture'];
    names.forEach(name => document.addEventListener(name, capture, true));
    const observer = new ResizeObserver(() => events.push({type: 'resize-observed', at: performance.now(), snapshot: snapshot()}));
    observer.observe(th);
    window.finalMasterResizeTrace = () => { names.forEach(name => document.removeEventListener(name, capture, true)); observer.disconnect();
      return {events, after: snapshot()}; };
    return snapshot();
  }, handle);
  await handle.dispose();
  const row = {variant: probe.variant, label: await separator.getAttribute('aria-label'), amount, before, passed: false};
  probe.report.column_resize = (probe.report.column_resize || []).concat(row);
  try {
    const rect = await separator.boundingBox(); assert(rect);
    probe.step('pointer-drag', separator, {dx: amount});
    await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height / 2); await page.mouse.down();
    await page.mouse.move(rect.x + rect.width / 2 + amount, rect.y + rect.height / 2, {steps: 8}); await page.mouse.up();
    await page.waitForFunction(({label, width}) => Math.abs(Number(document.querySelector('[aria-label="' + label + '"]').getAttribute('aria-valuenow')) - width) <= 2,
      {label: row.label, width: before.value + amount});
    row.passed = true;
  } finally { Object.assign(row, await page.evaluate(() => window.finalMasterResizeTrace())); }
}

module.exports = {resize};
