'use strict';
const {NAV, settle, shell, navigate, geometry} = require('./final_foundation_live_probe.cjs');

async function firstViews(entry, record) {
  const {page, state} = entry;
  await page.goto(record.ready.workbench_url); await settle(page, record);
  if (await page.locator('html').getAttribute('data-theme') !== state.theme) await page.getByRole('button', {name: /^切换(?:深色|浅色)$/}).click();
  record.equal(await page.locator('html').getAttribute('data-theme'), state.theme);
  for (const [view] of NAV) {
    await record.run(page, state, 'first_view', 'first-' + view, async () => {
      await record.flush(page);
      const actual = await navigate(page, view, record);
      const reads = () => record.data.api_responses.slice(actual.current_view_read_start).filter(row => row.page_id === page.foundationPageId && row.state === state.id && row.phase === 'normal'
        && row.status === 200 && row.body.meta && row.body.meta.source === 'production');
      const deadline = Date.now() + 12000;
      while (view !== 'run' && reads().length === 0 && Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 40)); await record.flush(page);
      }
      if (['analysis', 'gantt'].includes(view)) {
        await page.locator('[data-plan-gantt]').waitFor();
        await page.locator('.wb-current-plan[data-plan-ref]').waitFor();
      }
      if (['reports', 'review'].includes(view)) await page.locator('.rw-workbench[data-ready="true"]').waitFor();
      await settle(page, record);
      const layout = await geometry(page, record);
      const responses = reads();
      if (view === 'run') {
        record.ok(await page.locator('[data-preflight-workspace]').isVisible());
        record.ok(await page.getByRole('button', {name: '选择批次', exact: true}).isEnabled());
      } else record.ok(responses.length > 0, 'This first view must issue a real production-backed read: ' + view);
      return {view, ...actual, layout, production_reads: responses.map(row => ({url: row.url, file: row.file, sha256: row.sha256})),
        backend_read_not_applicable: view === 'run' ? 'Empty preflight form deliberately does not read production facts until scope selection/check; no run is admitted by this shell test.' : null,
        alerts: await page.getByRole('alert').allTextContents()};
    });
  }
}

function latestPlan(record, state, reference) {
  return record.data.api_responses.findLast(row => row.state === state.id && row.body.meta && row.body.meta.source === 'production'
    && row.body.data && row.body.data.plan && row.body.data.plan.plan_ref === reference);
}
async function caption(page, state, reference, record) {
  await page.locator('.wb-current-plan[data-plan-ref="' + reference + '"]').waitFor();
  await settle(page, record);
  const response = latestPlan(record, state, reference);
  record.ok(response, 'Header identity must be justified by the real backend plan workspace response');
  const plan = response.body.data.plan, node = page.locator('.wb-current-plan');
  record.equal(await node.locator('.wb-current-name').innerText(), plan.display_name);
  record.equal(await node.locator('.wb-current-name').getAttribute('title'), plan.display_name);
  record.ok((await node.innerText()).includes(plan.is_current_official ? '当前正式' : '历史正式'));
  record.ok((await node.innerText()).includes('正式 v' + plan.version));
  record.ok((await node.locator('.wb-current-range').innerText()).includes('计划时间'));
  return {plan, caption: await node.innerText(), workspace_response: response.file};
}
async function chooseOfficial(entry, record) {
  const {page, state} = entry;
  await navigate(page, 'analysis', record);
  await page.getByRole('button', {name: '展开计划目录', exact: true}).click();
  const table = page.locator('table[aria-label="可选排产方案"][aria-busy="false"]');
  await table.waitFor();
  const current = table.getByRole('row').filter({hasText: '当前正式'});
  record.equal(await current.count(), 1, 'The real mixed seed has exactly one current official plan');
  const radio = current.getByRole('radio');
  const label = await radio.getAttribute('aria-label');
  const alreadySelected = await radio.isChecked();
  await radio.check(); await settle(page, record);
  const collapse = page.getByRole('button', {name: '收起计划目录', exact: true});
  if (await collapse.count()) await collapse.click();
  record.equal(await page.locator('.plan-catalog').getAttribute('data-collapsed'), 'true');
  await page.locator('.wb-current-plan[data-plan-ref]').waitFor();
  const reference = await page.locator('.wb-current-plan').getAttribute('data-plan-ref');
  const real = await caption(page, state, reference, record);
  record.equal(real.plan.version, record.ready.expected.official_version);
  record.equal(real.plan.kind, 'official'); record.equal(real.plan.is_current_official, true);
  record.equal(label, '选择 ' + real.plan.display_name);
  await page.waitForFunction(ref => history.state && history.state.workbench && history.state.workbench.context.plan_ref === ref, reference);
  return {reference, already_selected_by_actual_default: alreadySelected, ...real};
}
async function remembered(page) {
  return page.evaluate(() => ({url: location.href, route: history.state && history.state.workbench,
    theme: document.documentElement.getAttribute('data-theme'),
    scroll: {mainTop: document.querySelector('.main-content').scrollTop, mainLeft: document.querySelector('.main-content').scrollLeft,
      windowTop: window.scrollY, windowLeft: window.scrollX},
    caption: document.querySelector('.wb-current-plan') && {reference: document.querySelector('.wb-current-plan').dataset.planRef,
      text: document.querySelector('.wb-current-plan').innerText},
    query: document.querySelector('input[aria-label="搜索批次、工序、设备、人员"]')?.value}));
}
async function assertRestored(entry, original, record, view = 'gantt') {
  const {page, state} = entry;
  await settle(page, record); await shell(page, view, record);
  await caption(page, state, original.caption.reference, record);
  try {
    await page.waitForFunction(expected => {
      const input = document.querySelector('input[aria-label="搜索批次、工序、设备、人员"]');
      const main = document.querySelector('.main-content');
      return input && input.value === expected.query && Math.abs(main.scrollTop - expected.scroll.mainTop) <= 2
        && Math.abs(window.scrollY - expected.scroll.windowTop) <= 2;
    }, original);
  } finally {
    record.data.restoration_observations.push({state: state.id, expected: original, actual: await remembered(page)});
    record.save();
  }
  const restored = await remembered(page);
  record.equal(restored.url, original.url); record.equal(restored.route.context, original.route.context);
  record.equal(restored.caption, original.caption); record.equal(restored.theme, original.theme);
  return restored;
}
async function userScroll(page, record) {
  const box = await page.locator('.main-content').boundingBox();
  const before = await remembered(page);
  // Boards size to their content, so a one-row Gantt fits a 1920x1080 viewport and has nothing to scroll.
  // Record that state instead of waiting for a wheel movement that cannot happen; taller states still scroll.
  const room = await page.evaluate(() => {
    const main = document.querySelector('.main-content'), root = document.documentElement;
    return {main: main.scrollHeight - main.clientHeight, window: root.scrollHeight - innerHeight};
  });
  if (room.main <= 1 && room.window <= 1) {
    record.data.scroll_actions.push({state: page.foundationState, before, after: before, room, skipped: 'page fits the viewport'}); record.save();
    return before;
  }
  await page.mouse.move(box.x + box.width - 8, Math.min(box.y + box.height - 24, 820));
  await page.mouse.wheel(0, 360);
  await page.waitForFunction(old => document.querySelector('.main-content').scrollTop > old.scroll.mainTop || window.scrollY > old.scroll.windowTop, before);
  await page.evaluate(() => new Promise((resolve, reject) => {
    let previous = '', since = performance.now();
    const started = since;
    function sample() {
      const main = document.querySelector('.main-content'), now = performance.now();
      const current = JSON.stringify([main.scrollTop, main.scrollLeft, scrollY, scrollX]);
      if (current !== previous) { previous = current; since = now; }
      if (now - since >= 180) return resolve();
      if (now - started >= 5000) return reject(new Error('Actual mouse-wheel scrolling did not settle'));
      requestAnimationFrame(sample);
    }
    requestAnimationFrame(sample);
  }));
  await page.waitForFunction(() => {
    const value = history.state && history.state.workbench && history.state.workbench.scroll;
    return value && Math.abs(value.mainTop - document.querySelector('.main-content').scrollTop) <= 2
      && Math.abs(value.windowTop - scrollY) <= 2 && Math.abs(value.windowLeft - scrollX) <= 2;
  });
  const after = await remembered(page);
  record.data.scroll_actions.push({state: page.foundationState, before, after, room}); record.save();
  record.ok(after.scroll.mainTop > before.scroll.mainTop || after.scroll.windowTop > before.scroll.windowTop, 'Actual mouse wheel moved the real page');
  return after;
}

async function navigationChain(entry, record) {
  const {page, state} = entry;
  let selected;
  await record.run(page, state, 'interaction', 'catalog-official-caption', async () => {
    selected = await chooseOfficial(entry, record); return selected;
  });
  if (!selected) return null;
  await record.run(page, state, 'interaction', 'delivery-risk-parent-navigation', async () => {
    await page.getByRole('tablist', {name: '计划中心视图', exact: true}).getByRole('tab', {name: '交付风险', exact: true}).click(); await settle(page, record);
    const actual = await shell(page, 'delay', record);
    const current = await caption(page, state, selected.reference, record);
    const layout = await geometry(page, record);
    record.equal((await remembered(page)).route.context.plan_ref, selected.reference);
    await page.getByRole('tablist', {name: '计划中心视图', exact: true}).getByRole('tab', {name: '选择排产方案', exact: true}).click(); await settle(page, record);
    await shell(page, 'analysis', record); await caption(page, state, selected.reference, record);
    return {title: actual.title, parent_active: 'analysis', reference: selected.reference, caption: current.caption, layout};
  });
  await record.run(page, state, 'interaction', 'real-typing-navigation-back-reload', async () => {
    await page.getByRole('tablist', {name: '计划中心视图', exact: true}).getByRole('tab', {name: '设备 / 人员 / 批次甘特', exact: true}).click(); await settle(page, record);
    await shell(page, 'gantt', record); await caption(page, state, selected.reference, record);
    const input = page.getByRole('searchbox', {name: '搜索批次、工序、设备、人员', exact: true});
    await input.click(); await input.press('Meta+A'); await input.press('Backspace');
    const beforeKeys = record.data.trusted_keys.length;
    await input.pressSequentially('CAT-B', {delay: 35});
    record.equal(await page.locator('[data-plan-gantt]').count(), 1, 'Typing must not duplicate the mounted Gantt workspace');
    record.equal(await page.locator('input[aria-label="搜索批次、工序、设备、人员"]').count(), 1, 'Typing must retain exactly one search input');
    await page.waitForFunction(() => history.state.workbench.context.query === 'CAT-B');
    const typed = record.data.trusted_keys.slice(beforeKeys).filter(row => row.state === state.id && row.key.length === 1);
    record.equal(typed.map(row => row.key).join(''), 'CAT-B'); record.ok(typed.every(row => row.trusted), 'Recorded browser key events are trusted');
    const saved = await userScroll(page, record);
    await navigate(page, 'basedata', record); record.equal(await page.locator('.wb-current-plan').count(), 0, 'Unrelated page must not display the previous plan caption');
    await page.goBack(); await assertRestored(entry, saved, record);
    await record.flush(page); await page.reload(); await assertRestored(entry, saved, record);
    const reloaded = await remembered(page);
    await page.getByRole('tablist', {name: '计划中心视图', exact: true}).getByRole('tab', {name: '选择排产方案', exact: true}).click();
    await settle(page, record); await shell(page, 'analysis', record); await caption(page, state, selected.reference, record);
    record.equal((await remembered(page)).route.context, saved.route.context, 'Plan-center tabs share the current object and typed query');
    const sidebarSaved = await userScroll(page, record);
    await navigate(page, 'basedata', record); await navigate(page, 'analysis', record);
    await assertRestored(entry, sidebarSaved, record, 'analysis');
    await page.getByRole('tablist', {name: '计划中心视图', exact: true}).getByRole('tab', {name: '设备 / 人员 / 批次甘特', exact: true}).click();
    await settle(page, record); await shell(page, 'gantt', record); await caption(page, state, selected.reference, record);
    record.equal((await remembered(page)).route.context, saved.route.context, 'Returning through the real plan-center entry preserves the object and query');
    return {reference: selected.reference, typed, saved, reloaded, sidebar_saved: sidebarSaved};
  });
  await record.run(page, state, 'interaction', 'theme-keyboard-focus-and-explicit-refresh', async () => {
    const toggle = page.getByRole('button', {name: /^切换(?:深色|浅色)$/});
    await toggle.click(); await toggle.press('Tab'); await page.keyboard.press('Shift+Tab');
    record.ok(await toggle.evaluate(node => node === document.activeElement), 'Actual tab/shift-tab returns keyboard focus to the theme button');
    await page.keyboard.press('Enter');
    record.equal(await page.locator('html').getAttribute('data-theme'), state.theme);
    record.ok(await toggle.evaluate(node => node === document.activeElement), 'Theme toggle keeps keyboard focus');
    await caption(page, state, selected.reference, record);
    await page.getByRole('button', {name: '刷新所选计划', exact: true}).click(); await settle(page, record);
    await caption(page, state, selected.reference, record);
    record.equal(await page.getByRole('searchbox', {name: '搜索批次、工序、设备、人员', exact: true}).inputValue(), 'CAT-B');
    const query = await remembered(page);
    record.equal(query.route.context.plan_ref, selected.reference);
    record.ok(!Object.hasOwn(query.route.context, 'snapshot_ref'), 'Explicit real refresh leaves a durable context for process restart');
    return query;
  });
  await page.mouse.move(1000, 120); await page.mouse.wheel(0, -3000);
  await page.waitForFunction(() => document.querySelector('.main-content').scrollTop === 0 && scrollY === 0);
  const stable = await userScroll(page, record);
  record.equal(stable.route.context.plan_ref, selected.reference);
  record.ok(!Object.hasOwn(stable.route.context, 'snapshot_ref'));
  entry.restartState = stable;
  return stable;
}
module.exports = {firstViews, chooseOfficial, caption, remembered, assertRestored, navigationChain};
