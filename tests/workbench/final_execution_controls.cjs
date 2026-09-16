'use strict';
const assert = require('node:assert/strict');
const { run, controls } = require('./final_execution_browser_support.cjs');

async function assertSuggestedTimes(page, start, end, since) {
  const actualStart = await start.inputValue(), actualEnd = await end.inputValue();
  assert.equal(actualStart, actualEnd, 'A task without previous reports suggests the same current time');
  const time = await page.evaluate(value => ({ suggested: Date.parse(value), now: Date.now() }), actualStart);
  assert(time.suggested >= Math.floor(since / 1000) * 1000 && time.suggested <= time.now,
    'New report times must be current suggestions, not retained manual draft values');
  assert(await page.getByText('请核对预填时间；不确定的时间请清除。', { exact: true }).isVisible());
}

async function exercise(p) {
  const { page, ready } = p, ref = ready.expected.final_e.task_refs['1'];
  await page.goto(ready.workbench_url); await page.locator('.sidebar').waitFor();
  await p.read(() => page.locator('.sidebar a[href$="?view=field"]').click(), '/execution/tasks');
  await p.read(() => p.choose('现场每页数量', '50'), '/execution/tasks');
  await p.read(() => page.locator('[data-field-task="' + ref + '"] button[aria-expanded]').click(), '/execution/tasks/' + ref);
  const openedAt = await page.evaluate(() => Date.now());
  await page.getByRole('button', { name: '新增本次报工', exact: true }).click();
  const quantity = page.getByRole('spinbutton', { name: '本次完成数量', exact: true });
  const start = page.getByLabel('实际开工', { exact: true }), end = page.getByLabel('本次实际完工', { exact: true });
  const hours = page.getByRole('spinbutton', { name: '有效工时（小时）', exact: true });
  await p.step(['WBP-FIELD-007.A001', 'WBP-FIELD-013.A004'], 'typed-quantity-and-initial-focus', async () => {
    assert(await quantity.evaluate(node => document.activeElement === node));
    await assertSuggestedTimes(page, start, end, openedAt);
    assert.equal(await hours.inputValue(), '');
    await quantity.type('3'); assert.equal(await quantity.inputValue(), '3');
    assert.equal(await page.getByLabel('已知累计', { exact: true }).innerText(), '3');
  });
  for (const [action, button, expected] of [['A002', '增加本次完成数量', '4'], ['A003', '减少本次完成数量', '3']])
    await p.step(['WBP-FIELD-007.' + action], button, async () => {
      await page.getByRole('button', { name: button, exact: true }).click(); assert.equal(await quantity.inputValue(), expected);
    });
  await p.step(['WBP-FIELD-007.A004'], 'quantity-arrow-up-and-down', async () => {
    await quantity.focus(); await quantity.press('ArrowUp'); assert.equal(await quantity.inputValue(), '4');
    await quantity.press('ArrowDown'); assert.equal(await quantity.inputValue(), '3');
  });
  await p.step(['WBP-FIELD-007.A007'], 'minimum-maximum-zero-and-empty', async () => {
    await page.getByRole('button', { name: '最小', exact: true }).click(); assert.equal(await quantity.inputValue(), '0');
    await page.waitForFunction(() => document.querySelector('button[aria-label="减少本次完成数量"]').disabled);
    assert(await page.getByRole('button', { name: '减少本次完成数量', exact: true }).isDisabled());
    await page.getByRole('button', { name: '最大', exact: true }).click(); assert.equal(await quantity.inputValue(), '10');
    await quantity.fill(''); assert.equal(await quantity.inputValue(), '');
  });
  await p.step(['WBP-FIELD-008.A001', 'WBP-FIELD-008.A002', 'WBP-FIELD-009.A006'], 'manual-wall-clock-values-do-not-create-hours', async () => {
    await start.fill('2026-08-31T08:00'); await end.fill('2026-08-31T10:00');
    assert.equal(await hours.inputValue(), '');
    assert.equal(await page.getByLabel('作业时长', { exact: true }).innerText(), '2 小时');
    assert.equal(await page.getByLabel('工时差额', { exact: true }).innerText(), '未知');
  });
  let popup;
  await p.step(['WBP-FIELD-008.A003'], 'open-real-datetime-popup', async () => {
    popup = await controls.openPicker(start); await popup.locator('[data-picker-type="datetime-local"]').waitFor();
    await p.shot('datetime-open');
  });
  await p.step(['WBP-FIELD-008.A004'], 'previous-next-month-and-month-grid', async () => {
    await popup.getByRole('button', { name: '上个月', exact: true }).click();
    await popup.getByRole('grid', { name: '2026 年 7 月', exact: true }).waitFor();
    await popup.getByRole('button', { name: '下个月', exact: true }).click();
    await popup.getByRole('grid', { name: '2026 年 8 月', exact: true }).waitFor();
    await popup.getByRole('button', { name: '选择月份', exact: true }).click();
    assert.equal(await popup.getByRole('gridcell').count(), 12);
    await popup.getByRole('gridcell', { name: '2026-09', exact: true }).click();
    await popup.getByRole('grid', { name: '2026 年 9 月', exact: true }).waitFor();
  });
  await p.step(['WBP-FIELD-008.A005', 'WBP-FIELD-008.A008'], 'cross-month-grid-date-and-24h-60minute-boundaries', async () => {
    await popup.getByRole('gridcell', { name: '2026-08-31', exact: true }).click();
    const hour = popup.getByLabel('时', { exact: true }), minute = popup.getByLabel('分', { exact: true });
    await hour.fill('23'); await minute.fill('59');
    assert(await popup.getByRole('button', { name: '增加时', exact: true }).isDisabled());
    assert(await popup.getByRole('button', { name: '增加分', exact: true }).isDisabled());
    await hour.fill('24'); assert(await popup.getByRole('button', { name: '确认', exact: true }).isDisabled());
    await hour.fill('08'); await minute.fill('60'); assert(await popup.getByRole('button', { name: '确认', exact: true }).isDisabled());
    await minute.fill('00'); await popup.getByRole('button', { name: '确认', exact: true }).click();
    await popup.waitFor({ state: 'detached' }); assert.equal(await start.inputValue(), '2026-08-31T08:00');
  });
  await p.step(['WBP-FIELD-008.A006', 'WBP-FIELD-008.A007'], 'today-confirm-then-clear-time', async () => {
    popup = await controls.openPicker(start);
    const today = await page.evaluate(() => { const d = new Date(); return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-'); });
    await popup.getByRole('button', { name: '今天', exact: true }).click();
    await popup.getByRole('button', { name: '确认', exact: true }).click(); await popup.waitFor({ state: 'detached' });
    assert((await start.inputValue()).startsWith(today));
    popup = await controls.openPicker(start); await popup.getByRole('button', { name: '清除', exact: true }).click();
    await popup.waitFor({ state: 'detached' }); assert.equal(await start.inputValue(), '');
  });
  await start.fill('2026-08-31T08:00');
  for (const [name, close] of [['Escape', async () => page.keyboard.press('Escape')], ['outside', async () => quantity.click()]])
    await p.step(['WBP-FIELD-008.A009'], name + '-close', async () => {
      popup = await controls.openPicker(start); await close(); await popup.waitFor({ state: 'detached' });
      assert.equal(await start.inputValue(), '2026-08-31T08:00');
    });
  await p.step(['WBP-FIELD-008.A009'], 'internal-real-wheel-keeps-popup-and-picker-draft', async () => {
    popup = await controls.openPicker(start);
    await popup.getByLabel('时', { exact: true }).fill('24');
    const positions = [];
    for (const [target, delta] of [[popup, 160], [popup.getByLabel('时', { exact: true }), -80],
      [popup.getByLabel('分', { exact: true }), 80]]) {
      await target.hover();
      const before = await popup.evaluate(node => ({ top: node.scrollTop, height: node.clientHeight, scrollHeight: node.scrollHeight }));
      await page.mouse.wheel(0, delta);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert(await popup.isVisible());
      assert.equal(await popup.getByLabel('时', { exact: true }).inputValue(), '24');
      assert.equal(await start.inputValue(), '2026-08-31T08:00');
      positions.push({ before, after: await popup.evaluate(node => node.scrollTop), wheel: delta });
    }
    assert(positions.some(row => row.before.top !== row.after), 'At least one real internal scroll must move');
    await p.shot('datetime-internal-wheel');
    await page.keyboard.press('Escape'); await popup.waitFor({ state: 'detached' });
    return { positions };
  });
  await p.step(['WBP-FIELD-008.A009'], 'external-real-page-scroll-closes-with-owner-value-and-focus', async () => {
    popup = await controls.openPicker(start);
    const before = await page.evaluate(() => scrollY);
    const maximum = await page.evaluate(() => document.documentElement.scrollHeight - innerHeight);
    const delta = before >= 150 ? -150 : 150;
    assert(delta < 0 || maximum - before >= 150, 'The page needs room for a real 150px external scroll');
    await page.locator('.field-editor h3').hover(); await page.mouse.wheel(0, delta);
    await page.waitForFunction(top => scrollY !== top, before);
    await popup.waitFor({ state: 'detached' });
    assert.equal(await start.inputValue(), '2026-08-31T08:00');
    assert(await start.evaluate(node => document.activeElement === node));
    await page.waitForFunction(({ top, amount }) => amount < 0 ? scrollY <= top - 149 : scrollY >= top + 149,
      { top: before, amount: delta });
    const after = await page.evaluate(() => scrollY);
    await p.shot('datetime-external-scroll-closed');
    await page.locator('.field-editor h3').hover(); await page.mouse.wheel(0, -delta);
    await page.waitForFunction(top => Math.abs(scrollY - top) < 1, before);
    return { before, after, delta, maximum, reset: await page.evaluate(() => scrollY) };
  });
  await p.step(['WBP-FIELD-008.A009'], 'window-resize-closes-with-owner-value-and-focus', async () => {
    popup = await controls.openPicker(start);
    const viewport = page.viewportSize();
    await page.setViewportSize({ ...viewport, width: viewport.width - 10 });
    await popup.waitFor({ state: 'detached' });
    assert.equal(await start.inputValue(), '2026-08-31T08:00');
    assert(await start.evaluate(node => document.activeElement === node));
    await page.setViewportSize(viewport); await p.shot('datetime-resize-closed');
  });
  await p.step(['WBP-FIELD-009.A001', 'WBP-FIELD-009.A003', 'WBP-FIELD-009.A004', 'WBP-FIELD-009.A005'], 'hours-step-resources-remark-and-fold', async () => {
    await hours.fill('0.5'); await page.getByRole('button', { name: '增加有效工时（小时）', exact: true }).click();
    assert.equal(await hours.inputValue(), '0.6'); await hours.press('ArrowDown'); assert.equal(await hours.inputValue(), '0.5');
    await page.locator('.field-editor > details > summary').click();
    await p.choose('实际设备', ready.expected.final_e.machine_ref); await p.choose('实际人员', ready.expected.final_e.operator_ref);
    await page.getByLabel('作业备注', { exact: true }).fill('仅控件验收，不提交');
    await page.getByLabel('经办人', { exact: true }).fill('控件验收员');
    await p.shot('all-editable-fields');
    await page.locator('.field-editor > details > summary').click();
    assert.equal(await page.locator('.field-editor > details').getAttribute('open'), null);
    assert.equal(await page.getByLabel('作业时长', { exact: true }).innerText(), '2 小时');
    assert.equal(await page.getByLabel('工时差额', { exact: true }).innerText(), '1.5 小时');
  });
  await p.step(['WBP-FIELD-013.A003', 'WBP-FIELD-013.A005'], 'cancel-discards-draft-without-history-command', async () => {
    await page.getByRole('button', { name: '取消', exact: true }).click();
    const confirm = page.getByRole('dialog', { name: '离开前确认', exact: true });
    await confirm.waitFor();
    await confirm.getByRole('button', { name: '留在当前页面', exact: true }).click();
    await confirm.waitFor({ state: 'detached' });
    assert.equal(await start.inputValue(), '2026-08-31T08:00'); assert.equal(await hours.inputValue(), '0.5');
    await page.getByRole('button', { name: '取消', exact: true }).click();
    await confirm.getByRole('button', { name: '放弃未保存内容并继续', exact: true }).click();
    await confirm.waitFor({ state: 'detached' }); await page.locator('.field-editor').waitFor({ state: 'detached' });
    const reopenedAt = await page.evaluate(() => Date.now());
    await page.getByRole('button', { name: '新增本次报工', exact: true }).click();
    assert.equal(await quantity.inputValue(), ''); assert.equal(await hours.inputValue(), '');
    await assertSuggestedTimes(page, start, end, reopenedAt);
    await page.getByRole('button', { name: '清除实际开工', exact: true }).click();
    await page.getByRole('button', { name: '清除本次实际完工', exact: true }).click();
    assert.equal(await start.inputValue(), ''); assert.equal(await end.inputValue(), '');
    assert.equal(await page.getByLabel('作业时长', { exact: true }).innerText(), '未知');
    assert.equal(await page.getByLabel('工时差额', { exact: true }).innerText(), '未知');
    const entry = await page.evaluate(() => history.state.workbench.context);
    assert.equal(entry.draft, undefined); assert.equal(entry.editor, undefined);
  });
  assert(p.report.requests.every(request => request.method === 'GET'));
}
async function visuals(p) {
  const field = p.page.getByLabel('实际开工', { exact: true });
  await field.fill('2026-08-31T08:00'); const popup = await controls.openPicker(field);
  await p.shot('datetime-control-viewport'); await p.page.keyboard.press('Escape'); await popup.waitFor({ state: 'detached' });
}
run('controls', exercise, { visuals });
