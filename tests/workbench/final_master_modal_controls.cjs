'use strict';
const assert = require('node:assert/strict');
const button = (scope, name) => scope.getByRole('button', {name, exact: true});

async function originalFocus(page, target) {
  const handle = await target.elementHandle(); assert(handle);
  try { await page.waitForFunction(node => node.isConnected && node === document.activeElement, handle); }
  finally { await handle.dispose(); }
}

async function focusTrap(page, probe, dialog) {
  const focusable = dialog.locator('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]');
  const count = await focusable.evaluateAll(nodes => nodes.filter(node => node.tabIndex >= 0 && node.getClientRects().length).length);
  assert(count > 2);
  for (const key of ['Tab', 'Shift+Tab']) for (let index = 0; index < count + 2; index++) {
    probe.step('press', 'modal active control', key); await page.keyboard.press(key);
    assert(await dialog.evaluate(node => node.contains(document.activeElement)), key + ' escaped modal');
  }
}

async function startScrollEvidence(page, probe, trigger, name) {
  probe.step('scrollIntoViewIfNeeded', trigger, 'Visible trigger setup before the position baseline');
  await trigger.scrollIntoViewIfNeeded();
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const owner = await trigger.elementHandle(); assert(owner);
  const before = await page.evaluate(owner => {
    const nodes = [...new Set([document.documentElement, document.body, ...document.querySelectorAll('.page-content,.main-content')])];
    const styles = node => Array.from(node.style).sort().map(name => [name, node.style.getPropertyValue(name), node.style.getPropertyPriority(name)]);
    const snapshot = () => nodes.map(node => ({tag: node.tagName, class: node.className, top: node.scrollTop, left: node.scrollLeft,
      height: node.clientHeight, scrollHeight: node.scrollHeight, styles: styles(node), overflow: getComputedStyle(node).overflow}));
    const events = [];
    const record = event => events.push({type: event.type, at: performance.now(), trusted: event.isTrusted, deltaY: event.deltaY,
      target: event.target === document ? '#document' : event.target.tagName + '.' + event.target.className, snapshot: snapshot()});
    document.addEventListener('wheel', record, {capture: true, passive: true});
    document.addEventListener('scroll', record, {capture: true, passive: true});
    window.finalMasterModalScroll = {snapshot, events, owner, rect: owner.getBoundingClientRect().toJSON(),
      dispose: () => { document.removeEventListener('wheel', record, true); document.removeEventListener('scroll', record, true); }};
    return {snapshot: snapshot(), rect: owner.getBoundingClientRect().toJSON()};
  }, owner);
  await owner.dispose();
  const row = {variant: probe.variant, name, before, samples: [], passed: false};
  probe.report.modal_scroll = (probe.report.modal_scroll || []).concat(row);
  return row;
}

const positions = snapshot => snapshot.map(({tag, class: className, top, left}) => ({tag, class: className, top, left}));
function assertPositions(snapshot, before, message) { assert.deepEqual(positions(snapshot), positions(before), message); }

async function wheel(page, probe, x, y, deltaY, row, name) {
  const start = await page.evaluate(() => window.finalMasterModalScroll.events.length);
  probe.step('wheel', name, {x, y, deltaY}); await page.mouse.move(x, y); await page.mouse.wheel(0, deltaY);
  await page.waitForFunction(start => window.finalMasterModalScroll.events.slice(start).some(event => event.type === 'wheel' && event.trusted), start);
  // Observe compositor-delivered scrolls too; comparing only the first two frames misses movement.
  await page.evaluate(() => new Promise(resolve => {
    const start = performance.now();
    function tick() { if (performance.now() - start >= 300) resolve(); else requestAnimationFrame(tick); }
    requestAnimationFrame(tick);
  }));
  const sample = await page.evaluate(start => ({events: window.finalMasterModalScroll.events.slice(start),
    snapshot: window.finalMasterModalScroll.snapshot()}), start);
  row.samples.push({name, ...sample}); return sample;
}

async function locked(page, probe, row, name) {
  await page.waitForFunction(() => [document.documentElement, document.body].every(node => getComputedStyle(node).overflow === 'hidden'));
  const sample = await wheel(page, probe, 8, 80, 700, row, name);
  assertPositions(sample.snapshot, row.before.snapshot, 'Background moved while a visible modal was open');
  sample.events.forEach(event => assertPositions(event.snapshot, row.before.snapshot, 'Background moved transiently behind modal'));
  sample.snapshot.slice(0, 2).forEach((node, index) => {
    const other = styles => styles.filter(([name]) => !/^overflow(?:-[xy])?$/.test(name));
    assert.deepEqual(other(node.styles), other(row.before.snapshot[index].styles), 'Scroll lock changed an unrelated inline style');
  });
}

async function finishScrollEvidence(page, probe, row) {
  await page.waitForFunction(() => { const value = window.finalMasterModalScroll; return value.owner.isConnected && document.activeElement === value.owner; });
  row.after_close = await page.evaluate(() => ({snapshot: window.finalMasterModalScroll.snapshot(),
    rect: window.finalMasterModalScroll.owner.getBoundingClientRect().toJSON(), same_owner_focused: document.activeElement === window.finalMasterModalScroll.owner}));
  assertPositions(row.after_close.snapshot, row.before.snapshot, 'Closing the last modal changed the original background position');
  assert.deepEqual(row.after_close.rect, row.before.rect, 'Original focused trigger changed position');
  row.after_close.snapshot.forEach((node, index) => assert.deepEqual(node.styles, row.before.snapshot[index].styles, 'Original inline values or priorities were not restored'));
  const html = row.after_close.snapshot[0], direction = html.scrollHeight - html.height - html.top > 10 ? 1 : -1;
  assert(html.scrollHeight > html.height + 10, 'Actual background needs scrollable content for this assertion');
  const sample = await wheel(page, probe, 250, 80, direction * 240, row, 'background after last modal closed');
  assert(sample.events.some(event => event.type === 'scroll' && event.snapshot.some((node, index) =>
    node.top !== row.after_close.snapshot[index].top || node.left !== row.after_close.snapshot[index].left)), 'Background did not resume ordinary wheel scrolling');
  assert.notDeepEqual(positions(sample.snapshot), positions(row.after_close.snapshot), 'Background wheel ended at the unchanged position');
  row.passed = true;
  await page.evaluate(() => window.finalMasterModalScroll.dispose());
}

function checks(page, probe, rail) {
  async function closures() {
    const trigger = button(page, '新增物料');
    for (const method of ['x', 'cancel', 'backdrop', 'escape']) {
      const row = await startScrollEvidence(page, probe, trigger, 'material-' + method);
      await probe.click(trigger);
      const dialog = page.getByRole('dialog', {name: '新增物料', exact: true});
      await dialog.locator('input[name="business_code"]').waitFor();
      await probe.type(dialog.locator('input[name="business_code"]'), 'FC-CANCEL-' + method);
      await focusTrap(page, probe, dialog); await locked(page, probe, row, 'material backdrop');
      await probe.shot('material-modal-' + method);
      if (method === 'x') await probe.click(dialog.locator('.modal-head').getByRole('button', {name: '关闭', exact: true}));
      else if (method === 'cancel') await probe.click(button(dialog, '取消'));
      else if (method === 'backdrop') { probe.step('pointer-click', '.modal-bg', {x: 5, y: 5}); await page.locator('.modal-bg:visible').click({position: {x: 5, y: 5}}); }
      else { probe.step('press', 'modal active control', 'Escape'); await page.keyboard.press('Escape'); }
      await dialog.waitFor({state: 'detached'}); await finishScrollEvidence(page, probe, row);
    }
  }
  async function nested() {
    await rail('设备'); const trigger = button(page, '新增设备');
    const row = await startScrollEvidence(page, probe, trigger, 'nested-device-catalog'); await probe.click(trigger);
    const parent = page.getByRole('dialog', {name: '新增设备', exact: true}), field = parent.getByLabel('绑定工种', {exact: true});
    await field.locator('option').filter({hasText: /^Turning$/}).waitFor({state: 'attached'});
    await locked(page, probe, row, 'parent before nested select');
    await probe.click(field); const popup = page.locator('.wb-control-popup'); await popup.waitFor();
    await probe.shot('nested-select'); await probe.press(popup.getByRole('option').first(), 'Escape');
    await popup.waitFor({state: 'detached'}); assert(await parent.isVisible());
    await probe.click(button(parent, '维护设备组'));
    const child = page.locator('.resource-catalog [role="dialog"]'); await child.waitFor();
    await focusTrap(page, probe, child); await locked(page, probe, row, 'nested catalog backdrop'); await probe.shot('nested-catalog');
    probe.step('press', 'nested modal', 'Escape'); await page.keyboard.press('Escape');
    await child.waitFor({state: 'detached'}); await parent.waitFor();
    await originalFocus(page, button(parent, '维护设备组'));
    await locked(page, probe, row, 'parent after nested catalog closed');
    await probe.click(button(parent, '取消')); await parent.waitFor({state: 'detached'});
    await finishScrollEvidence(page, probe, row);
  }
  async function longBody() {
    await rail('人员'); const trigger = button(page, '新增人员');
    const row = await startScrollEvidence(page, probe, trigger, 'nested-unsaved-shift-pattern'); await probe.click(trigger);
    const parent = page.getByRole('dialog', {name: '新增人员', exact: true}), catalogTrigger = button(parent, '维护班次');
    await probe.click(catalogTrigger);
    const child = page.locator('.resource-catalog [role="dialog"]'); await child.waitFor();
    await probe.click(button(child, '编辑 RT-SH')); await child.getByLabel('轮换天数', {exact: true}).waitFor();
    await probe.fill(child.getByLabel('轮换天数', {exact: true}), 31); await probe.click(button(child, '调整逐日规则'));
    await child.locator('.rc-pattern-table tbody tr').nth(30).waitFor({state: 'attached'});
    const body = child.locator('.modal-b.scroll');
    const initial = await body.evaluate(node => ({top: node.scrollTop, height: node.clientHeight, scrollHeight: node.scrollHeight}));
    assert(initial.scrollHeight > initial.height + 100, 'Actual draft must make the body scrollable');
    await locked(page, probe, row, 'long nested dialog backdrop');
    const rect = await body.boundingBox(); assert(rect);
    const sample = await wheel(page, probe, rect.x + rect.width - 16, rect.y + rect.height / 2, 700, row, 'long modal internal body');
    row.internal_body = {before: initial, after: await body.evaluate(node => ({top: node.scrollTop, height: node.clientHeight, scrollHeight: node.scrollHeight}))};
    assert(row.internal_body.after.top > initial.top, 'Ordinary wheel did not scroll the actual long modal body');
    assertPositions(sample.snapshot, row.before.snapshot, 'Internal modal wheel escaped into background');
    sample.events.forEach(event => assertPositions(event.snapshot, row.before.snapshot, 'Internal wheel moved background transiently'));
    await probe.shot('long-nested-shift-body');
    await probe.click(child.locator('.modal-f').getByRole('button', {name: '关闭', exact: true}));
    await child.getByRole('alert').filter({hasText: '有尚未保存的修改'}).waitFor();
    await locked(page, probe, row, 'unsaved draft confirmation still locked');
    await probe.click(button(child, '放弃修改')); await child.waitFor({state: 'detached'}); await parent.waitFor();
    await originalFocus(page, catalogTrigger); await locked(page, probe, row, 'parent after long draft discarded');
    await probe.click(button(parent, '取消')); await parent.waitFor({state: 'detached'});
    await finishScrollEvidence(page, probe, row);
  }
  return {closures, nested, longBody};
}

module.exports = {checks, focusTrap, originalFocus};
