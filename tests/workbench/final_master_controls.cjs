'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');
const {Probe} = require('./final_master_probe_support.cjs');
const modalControls = require('./final_master_modal_controls.cjs');
const {observeFocus} = require('./final_master_focus_trace.cjs');
const filterControls = require('./final_master_filter_controls.cjs');
const {resize: resizeWithTrace} = require('./final_master_resize_trace.cjs');
const processResize = require('./final_master_process_resize.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2]));
const p = new Probe(ready, 'controls');
p.continueOnFailure = true;
p.report.not_applicable = [];
const ids = (family, numbers) => numbers.map(number => 'WBP-SH-' + family + '-C' + String(number).padStart(2, '0'));
const b = (scope, name) => scope.getByRole('button', {name, exact: true});
const menu = () => page.locator('[data-wb-table-filter]');
let page;
async function open(view = 'process') {
  p.step('goto', 'about:blank', 'Independent control scenario; history restoration is tested separately');
  await page.goto('about:blank');
  p.step('goto', '/workbench?view=' + view);
  await page.goto(ready.url + '/workbench?view=' + view);
  await page.locator('.sidebar').waitFor();
  await page.locator(view === 'batches' ? '[data-batch-workspace] .wb-table[aria-busy="false"]' : '[data-resource-workspace] .wb-table[aria-busy="false"]').waitFor();
}
async function rail(label) {
  await p.click(page.locator('.hb-tile').filter({has: page.locator('.hb-tname').getByText(label, {exact: true})}));
  await page.locator('.wb-table[aria-busy="false"]').waitFor();
}
async function list(kind, action) {
  const waiting = page.waitForResponse(async response => ['/api/workbench/v1/entities/' + kind, '/api/workbench/v1/entities/' + kind + '/query'].includes(new URL(response.url()).pathname) && await response.finished() === null);
  const [response] = await Promise.all([waiting, action()]); assert.equal(response.status(), 200);
  const body = await response.json(); assert.equal(body.meta.source, 'production');
  await page.locator('.wb-table[aria-busy="false"]').waitFor(); return body;
}
async function facet(header) {
  const waiting = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/facets') || new URL(response.url()).pathname.includes('/process-table/facets/'));
  const [response] = await Promise.all([waiting, p.click(header.locator('.wb-th-filter'))]); assert.equal(response.status(), 200);
  await menu().locator('.wb-table-facet-options[aria-busy="false"]').waitFor(); return response.json();
}
async function resize(separator, amount) {
  await resizeWithTrace(page, p, separator, amount);
}
async function observeFilter(head, kind) {
  const owner = await head.locator('.wb-th-filter').elementHandle(); assert(owner);
  await page.evaluate(({owner, kind, column}) => {
    const panel = document.querySelector('[data-wb-table-filter]'), events = [];
    const describe = node => node ? {tag: node === document ? '#document' : node.tagName, class: node.className, label: node.getAttribute && node.getAttribute('aria-label')} : null;
    const scrolls = () => [...new Set([document.scrollingElement, ...document.querySelectorAll('.main-content,.card-scroll,.wb-table-shell')])]
      .filter(Boolean).map(node => ({...describe(node), top: node.scrollTop, left: node.scrollLeft, height: node.clientHeight, scrollHeight: node.scrollHeight}));
    function ownerState() {
      const area = document.querySelector(kind === 'part' ? '[data-process-workspace]' : '[data-resource-workspace]');
      const current = area && area.querySelector('[data-column-key="' + column + '"] .wb-th-filter');
      const scope = history.state && history.state.workbench && history.state.workbench.context.read_view && history.state.workbench.context.read_view.scope;
      const base = scope ? kind === 'part' ? window.APSProcessActions.facetScope(scope, column) : window.ResourceTableFilterModel.toolbarScope(scope) : null;
      return {same_node: current === owner, connected: owner.isConnected, disabled: owner.disabled, expanded: owner.getAttribute('aria-expanded'),
        scope_from_history: scope || null, derived_identity: base ? window.ResourceTableFilterModel.signature({kind, column, scope: base}) : null,
        identity_basis: 'Actual saved scope with the product scopeTransform/signature; not React internals', rect: owner.getBoundingClientRect().toJSON(),
        table_busy: area && area.querySelector('.wb-table').getAttribute('aria-busy')};
    }
    const initial = scrolls(), initialOwner = ownerState();
    const capture = event => events.push({type: event.type, at: performance.now(), utc: new Date().toISOString(), target: describe(event.target),
      key: event.key, deltaY: event.deltaY, checked: event.target.checked, trusted: event.isTrusted,
      active: describe(document.activeElement), owner: ownerState(), panel_connected: panel.isConnected, scrolls: scrolls()});
    const names = ['scroll', 'wheel', 'pointerdown', 'pointerup', 'input', 'change', 'keydown', 'focusin'];
    names.forEach(name => document.addEventListener(name, capture, true));
    const observer = new MutationObserver(records => {
      const attributes = records.filter(row => row.type === 'attributes' && (row.target === owner || row.attributeName === 'aria-busy'))
        .map(row => ({target: describe(row.target), attribute: row.attributeName, value: row.target.getAttribute(row.attributeName)}));
      if (attributes.length) events.push({type: 'attributes', at: performance.now(), utc: new Date().toISOString(), attributes, owner: ownerState(), scrolls: scrolls()});
      if (!panel.isConnected) { events.push({type: 'menu-removed', at: performance.now(), utc: new Date().toISOString(), owner: ownerState(), scrolls: scrolls()}); observer.disconnect(); }
    });
    observer.observe(document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['aria-busy', 'aria-expanded', 'disabled']});
    window.finalMasterFilterObservation = () => { names.forEach(name => document.removeEventListener(name, capture, true)); observer.disconnect();
      return {initial, initial_owner: initialOwner, events, final: scrolls(), final_owner: ownerState(), connected: panel.isConnected}; };
  }, {owner, kind, column: await head.getAttribute('data-column-key')});
  await owner.dispose();
}
async function headers(kind, isProcess) {
  if (isProcess) await rail('工艺');
  const scope = page.locator(isProcess ? '[data-process-workspace]' : '[data-resource-workspace]');
  const head = scope.locator('.wb-resource-th[data-column-key="business_code"]');
  for (const direction of ['ascending', 'descending', 'none']) {
    await list(kind, () => p.click(head.locator('.wb-th-sort')));
    assert.equal(await head.locator('xpath=ancestor::th').getAttribute('aria-sort'), direction);
  }
  const data = await facet(head); assert(data.data.options.length > 0);
  await p.shot(isProcess ? 'native-process-filter' : 'resource-filter');
  const all = menu().getByRole('checkbox', {name: '全选', exact: true});
  assert(await all.isChecked());
  const requestsStart = p.report.requests.length, responsesStart = p.report.responses.length;
  await observeFilter(head, kind);
  const empty = await list(kind, () => p.click(all)); assert.equal(empty.data.page.total, 0);
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const observation = await page.evaluate(() => window.finalMasterFilterObservation());
  p.report.facet_after_empty = (p.report.facet_after_empty || []).concat({variant: p.variant, kind, still_open: await menu().isVisible(), observation,
    requests: p.report.requests.slice(requestsStart), responses: p.report.responses.slice(responsesStart), actual_page: empty.data.page});
  assert(await menu().isVisible(), 'Filtering must not unmount its own header/menu');
  const restored = await list(kind, () => p.click(all)); assert.equal(restored.data.page.total, data.data.row_count);
  assert(await menu().isVisible(), 'Restoring all column values must keep the filter menu open');
  await p.type(menu().getByRole('textbox', {name: isProcess ? '搜索图号列值' : '搜索物料编号列值', exact: true}), 'not-a-real-code');
  await menu().getByText('没有匹配的列值', {exact: true}).waitFor();
  await p.press(menu().getByRole('textbox'), 'Escape'); await menu().waitFor({state: 'detached'});
  await facet(head); await list(kind, () => p.click(b(menu(), '清除'))); await menu().waitFor({state: 'detached'});
  await resize(head.getByRole('separator'), 24);
  if (isProcess) {
    await processResize.verify(page, p, scope, head);
    for (const key of ['label', 'operation_count', 'stage']) {
      const column = scope.locator('.wb-resource-th[data-column-key="' + key + '"]');
      const values = await facet(column); assert(values.data.options.length > 0);
      const filtered = await list(kind, () => p.click(menu().locator('.wb-table-facet-option input').first()));
      assert.equal(filtered.data.page.total, values.data.row_count - values.data.options[0].count);
      assert(await menu().isVisible(), 'Filtering another column must retain its filter menu');
      await p.press(menu().getByRole('textbox'), 'Escape'); await menu().waitFor({state: 'detached'});
      await facet(column); await list(kind, () => p.click(b(menu(), '清除'))); await menu().waitFor({state: 'detached'});
    }
    await p.type(scope.getByRole('searchbox'), 'FC-P-'); await list(kind, () => p.click(b(scope, '搜索')));
    const values = await facet(head); assert.equal(values.data.row_count, 43);
    const rows = await scope.locator('tbody tr[data-process-ref]').count();
    await p.type(menu().getByRole('textbox'), '003');
    await menu().locator('.wb-table-facet-option').filter({hasText: 'FC-P-003'}).waitFor();
    assert.equal(await scope.locator('tbody tr[data-process-ref]').count(), rows);
    await p.press(menu().getByRole('textbox'), 'Escape'); await menu().waitFor({state: 'detached'});
  }
  await filterControls.movement(page, p, head, facet);
}
async function batchHeaders() {
  const scope = page.locator('[data-batch-workspace]');
  const quantity = b(scope, '数量').locator('xpath=ancestor::th');
  for (const direction of ['ascending', 'descending', 'none']) {
    await list('batch', () => p.click(b(quantity, '数量')));
    assert.equal(await quantity.getAttribute('aria-sort'), direction);
  }
  const th = b(scope, '批次号').locator('xpath=ancestor::th');
  await p.click(b(th, '筛选批次号'));
  const dialog = page.getByRole('dialog', {name: '筛选批次号', exact: true});
  await b(dialog, '全选列值').waitFor();
  await p.fill(dialog.getByRole('searchbox'), 'PROC');
  assert.equal(await dialog.locator('.batch-value-list label').count(), 1);
  await p.click(b(dialog, '全部不选')); await p.click(b(dialog, '全选列值'));
  assert(await dialog.getByRole('checkbox').first().isChecked());
  await p.click(b(dialog, '全部不选')); await p.click(dialog.getByRole('checkbox').first());
  const filtered = await list('batch', () => p.click(b(dialog, '完成'))); assert.equal(filtered.data.page.total, 1);
  await p.click(b(th, '筛选批次号')); await list('batch', () => p.click(b(page.getByRole('dialog', {name: '筛选批次号', exact: true}), '清除本列')));
  await resize(scope.getByRole('separator', {name: '调整批次号列宽', exact: true}), 24);
}
async function dates() {
  const trigger = b(page, '新增批次'), finishTrace = await observeFocus(page, p, trigger, 'batch-date-natural-focus');
  try { await dateActions(trigger); }
  finally { await finishTrace(); }
}
async function dateActions(trigger) {
  await p.click(trigger);
  const dialog = page.getByRole('dialog', {name: '新增批次', exact: true}), field = dialog.getByLabel('交期', {exact: true});
  await p.fill(field, '2027-01-03'); assert.equal(await field.inputValue(), '2027-01-03');
  const fieldRect = await field.boundingBox(); assert(fieldRect);
  p.step('pointer-click', field, 'visible left year segment'); await field.click({position: {x: 18, y: fieldRect.height / 2}});
  p.step('pressSequentially', field, '2028'); await field.pressSequentially('2028');
  await p.press(field, 'ArrowRight'); p.step('pressSequentially', field, '12'); await field.pressSequentially('12');
  p.step('pressSequentially', field, '07'); await field.pressSequentially('07');
  await p.press(field, 'Tab'); assert.equal(await field.inputValue(), '2028-12-07');
  await p.fill(field, '2027-01-03');
  const constraints = await field.evaluate(node => ({min: node.min, max: node.max, disabled: node.disabled, readOnly: node.readOnly}));
  p.report.not_applicable.push({variant: p.variant, actions: ids('008', [10, 11, 13]), reason: 'Actual batch due-date input defines no min/max/readOnly; no fake attributes or isolated component were injected', observed: constraints,
    source: 'frontend/workbench/app/BatchControls.jsx:21'});
  async function picker() {
    const rect = await field.boundingBox(); assert(rect);
    p.step('pointer-click', field, 'date icon'); await field.click({position: {x: rect.width - 16, y: rect.height / 2}});
    const popup = page.locator('.wb-control-popup'); await popup.waitFor(); return popup;
  }
  let popup = await picker(); await p.click(b(popup, '下个月')); await popup.getByRole('grid', {name: '2027 年 2 月', exact: true}).waitFor();
  await p.click(b(popup, '上个月')); await popup.getByRole('grid', {name: '2027 年 1 月', exact: true}).waitFor();
  await p.click(b(popup, '选择月份')); await p.click(popup.getByRole('gridcell', {name: '2027-03', exact: true}));
  await p.shot('date-month-selection');
  const day = popup.getByRole('gridcell', {name: '2027-03-03', exact: true});
  await modalControls.originalFocus(page, day);
  await p.press(day, 'ArrowRight'); await p.press(popup.getByRole('gridcell', {name: '2027-03-04', exact: true}), 'Enter');
  await popup.waitFor({state: 'detached'}); assert.equal(await field.inputValue(), '2027-03-04');
  popup = await picker(); await p.click(b(popup, '今天')); await popup.waitFor({state: 'detached'});
  const today = await page.evaluate(() => { const now = new Date(); return [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'), String(now.getDate()).padStart(2, '0')].join('-'); });
  assert.equal(await field.inputValue(), today);
  popup = await picker(); await p.click(b(popup, '清空')); await popup.waitFor({state: 'detached'}); assert.equal(await field.inputValue(), '');
  popup = await picker(); p.step('press', 'nested date popup', 'Escape'); await page.keyboard.press('Escape');
  await popup.waitFor({state: 'detached'}); assert(await dialog.isVisible());
  await modalControls.focusTrap(page, p, dialog); await p.click(b(dialog, '取消'));
  await dialog.waitFor({state: 'detached'}); await modalControls.originalFocus(page, trigger);
}
async function main() {
  const variants = ['1920x1080-light', '1920x1080-dark', '1392x924-light', '1392x924-dark'];
  const selectedVariants = process.env.FINAL_MASTER_CONTROL_VARIANTS ? process.env.FINAL_MASTER_CONTROL_VARIANTS.split(',') : variants;
  assert(selectedVariants.length && new Set(selectedVariants).size === selectedVariants.length && selectedVariants.every(value => variants.includes(value)));
  p.report.selected_variants = selectedVariants;
  const browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true});
  p.report.browser = browser.version(); assert(p.report.browser.startsWith('109.'));
  try {
    for (const [width, height] of [[1920, 1080], [1392, 924]]) for (const theme of ['light', 'dark']) {
      if (!selectedVariants.includes(width + 'x' + height + '-' + theme)) continue;
      const context = await browser.newContext({viewport: {width, height}, locale: 'en-US', timezoneId: 'Asia/Shanghai'});
      page = await context.newPage(); p.attach(page, width + 'x' + height + '-' + theme); await open();
      if (theme === 'dark') await p.click(b(page, '切换深色'));
      const modals = modalControls.checks(page, p, rail);
      const scenarios = [
        ['resource-headers', 'process', ids('006', [10, 11, 12]), () => headers('material', false)],
        ['process-headers', 'process', ids('007', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]), () => headers('part', true)],
        ['resource-modal-closures', 'process', ids('009', [1, 2, 3, 4, 5, 6, 7, 8]), modals.closures],
        ['resource-nested-dialogs', 'process', ids('009', [10]), modals.nested],
        ['resource-long-modal-scroll', 'process', ids('009', [7, 8]), modals.longBody],
        ['batch-headers', 'batches', ids('006', [1, 2, 3, 4, 6, 7, 8, 9]), batchHeaders],
        ['batch-native-date-and-focus', 'batches', [...ids('008', [1, 2, 3, 4, 5, 6, 7, 8, 9]), ...ids('009', [13, 14])], dates]
      ];
      const selected = process.env.FINAL_MASTER_CONTROLS_CASES ? process.env.FINAL_MASTER_CONTROLS_CASES.split(',') : scenarios.map(row => row[0]);
      assert(selected.length && new Set(selected).size === selected.length && selected.every(name => scenarios.some(row => row[0] === name)));
      p.report.selected_scenarios = selected;
      for (const [name, view, actions, run] of scenarios) if (selected.includes(name)) { await open(view); await p.run(actions, name, run); }
      await context.close();
    }
  } finally { await browser.close(); await Promise.all(p.pending); p.save(); }
  assert.deepEqual(p.report.external, []); assert.equal(p.report.summary.failed, 0);
  assert.deepEqual(p.report.errors.filter(row => !row.expected), []);
  console.log(JSON.stringify(p.report.summary));
}
main().catch(error => {p.report.fatal = error.stack; p.save(); console.error(error); process.exitCode = 1;});
