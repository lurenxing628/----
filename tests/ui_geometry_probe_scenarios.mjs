/** Read-only current-workbench actions; no API replacement or business commands. */
async function prepareCurrentScenario(expected) {
  const pause = () => new Promise(resolve => setTimeout(resolve, 25));
  const frame = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const visible = element => {
    if (!element) return false;
    const box = element.getBoundingClientRect(), style = getComputedStyle(element);
    return box.width > 0 && box.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  };
  async function until(predicate, label) {
    const start = Date.now();
    while (!predicate()) {
      if (Date.now() - start > 5000) throw new Error(expected.case + ': ' + label);
      await pause();
    }
    await frame();
  }
  async function present(selector) {
    await until(() => visible(document.querySelector(selector)), 'missing visible ' + selector);
    return document.querySelector(selector);
  }
  async function click(selector) {
    const element = await present(selector);
    await until(() => !element.disabled, 'disabled ' + selector);
    element.click(); await frame();
  }
  async function button(text, scope = 'body') {
    let match;
    await until(() => {
      const matches = [...document.querySelectorAll(scope + ' button')].filter(node => visible(node)
        && (node.getAttribute('aria-label') === text || node.textContent.trim() === text));
      if (matches.length !== 1) return false;
      match = matches[0]; return !match.disabled;
    }, 'unique enabled button ' + text);
    match.click(); await frame();
  }
  async function value(selector, text) {
    const element = await present(selector);
    const prototype = element.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, text);
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    await frame();
    if (element.value !== text) throw new Error('Input did not retain ' + selector);
  }
  async function openDetails(prefix, scope = 'body') {
    let summary;
    await until(() => {
      const rows = [...document.querySelectorAll(scope + ' details > summary')]
        .filter(node => visible(node) && node.textContent.trim().startsWith(prefix));
      if (rows.length !== 1) return false;
      summary = rows[0]; return true;
    }, 'unique details ' + prefix);
    if (!summary.parentElement.open) { summary.click(); await frame(); }
  }
  async function tableReady(selector) {
    await until(() => {
      const table = document.querySelector(selector);
      return visible(table) && table.getAttribute('aria-busy') !== 'true'
        && table.querySelectorAll('tbody tr').length > 0 && !table.textContent.includes('正在读取');
    }, 'nonempty ready table ' + selector);
  }
  async function preflight() {
    await present('[data-preflight-workspace]');
    await value('input[aria-label="计划开始日期"]', '2026-05-06');
    await value('input[aria-label="计划结束日期"]', '2026-05-06');
    await button('选择批次');
    let choice;
    await until(() => {
      const rows = [...document.querySelectorAll('.pf-picker-row')].filter(row => row.textContent.includes(expected.identity.batch_id));
      if (rows.length !== 1) return false;
      choice = rows[0].querySelector('input[type="checkbox"]'); return visible(choice) && !choice.disabled;
    }, 'fixture batch checkbox');
    if (!choice.checked) { choice.click(); await frame(); }
    if (!choice.checked) throw new Error('Fixture batch was not selected');
    await button('收起范围');
    await button('开始排产检查');
    await openDetails('检查明细');
    await tableReady('table[aria-label="排产检查明细"]');
  }
  async function plan() {
    await planCatalog();
    await until(() => visible(document.querySelector('.plan-projections table'))
      && document.querySelector('[data-plan-workspace]').textContent.includes(expected.identity.batch_id), 'bound plan data');
  }
  async function planCatalog() {
    await present('.plan-catalog');
    if (document.querySelector('.plan-catalog button[aria-label="展开计划目录"]'))
      await button('展开计划目录', '.plan-catalog');
    await tableReady('table[aria-label="可选排产方案"]');
  }
  async function gantt() {
    await plan();
    const label = expected.dimension === 'operator' ? '人员' : '设备';
    await button(label, '[aria-label="甘特分组"]');
    await value('input[aria-label="搜索批次、工序、设备、人员"]', expected.identity.batch_id);
    const selector = '[data-plan-task="' + expected.identity.task_ref + '"]:not([data-before])';
    await click(selector);
    await present('[data-plan-inspector]');
    const pressed = [...document.querySelectorAll('[aria-label="甘特分组"] button[aria-pressed="true"]')];
    if (pressed.length !== 1 || pressed[0].textContent.trim() !== label) throw new Error('Wrong Gantt resource dimension');
  }
  async function logs() {
    await click('#sm-tab-logs');
    await value('#sm-panel-logs select[aria-label="日志来源"]', 'OperationLogs');
    await button('查询', '#sm-panel-logs');
    await tableReady('.sm-logs-table');
    let row;
    await until(() => {
      const matches = [...document.querySelectorAll('.sm-logs-table tbody tr')]
        .filter(node => node.querySelector('.sm-summary strong')?.textContent === expected.log_summary);
      if (matches.length !== 1) return false;
      row = matches[0]; return visible(row);
    }, 'unique persisted log ' + expected.log_summary);
    row.click(); await frame();
    const detail = await present('.sm-detail[aria-label="日志详情"] pre');
    if (expected.plugin_audit && detail.textContent !== expected.identity.startup_public_body)
      throw new Error('Visible plugin diagnostic differs from the persisted public startup audit');
    if (!expected.plugin_audit && detail.textContent !== expected.identity.normal_public_body)
      throw new Error('Visible historical log differs from its persisted public projection');
    if (detail.textContent.includes(expected.identity.private_path_canary)
      || detail.closest('.sm-detail').textContent.includes('本条详情已截断'))
      throw new Error('Plugin/log detail leaked a private value or was truncated');
  }
  async function invalidHistory() {
    await planCatalog();
    const rows = [...document.querySelectorAll('table[aria-label="可选排产方案"] tbody tr')]
      .filter(row => row.querySelector('td:nth-child(2)')?.textContent.trim() === '2');
    if (rows.length !== 1 || !rows[0].querySelector('input[type="radio"]')?.disabled
      || !rows[0].textContent.includes('这次排产的摘要无效，确认不了计划是否完整。请刷新后重试。'))
      throw new Error('Malformed version 2 was not visible and unavailable');
  }
  async function batchImport() {
    await until(() => document.querySelector('[data-batch-workspace]')?.textContent.includes(expected.identity.batch_id), 'fixture batch list');
    await button('批量导入', '[data-batch-workspace]');
    await present('[role="dialog"] input[type="file"]');
  }
  async function processCreate() {
    await click('[data-rail-node="process"]');
    await tableReady('table[aria-label="零件工艺列表"]');
    await until(() => document.querySelector('table[aria-label="零件工艺列表"]').textContent.includes(expected.identity.part_no), 'fixture part');
    await button('新增零件', '[data-process-workspace]');
  }
  async function field() {
    await tableReady('table[aria-label="现场任务列表"]');
    await value('input[aria-label="搜索批次或工序"]', expected.identity.batch_id);
    await value('input[aria-label="计划完工起日"]', '2026-05-06');
    await value('input[aria-label="计划完工止日"]', '2026-05-06');
    await click('button[aria-label="查询现场记录"]');
    await tableReady('table[aria-label="现场任务列表"]');
  }
  async function catalog() {
    await present('.rw-workbench[data-ready="true"]');
    await openDetails('其他报表');
    await value('select[aria-label="其他报表"]', expected.catalog);
    if (['utilization', 'downtime'].includes(expected.catalog)) {
      await value('input[aria-label="统计窗口起日"]', '2026-05-06');
      await value('input[aria-label="统计窗口止日"]', '2026-05-06');
      await click('button[aria-label="读取目录范围"]');
      await until(() => document.querySelector('[aria-label="其他报表目录"]').textContent
        .includes('统计窗口：2026-05-06 至 2026-05-06'), 'exact catalog date window');
    }
    await until(() => !document.querySelector('[aria-label="其他报表目录"]').textContent.includes('正在读取目录报表'), 'catalog read completion');
    await tableReady('[aria-label="其他报表目录"] table');
    if (document.querySelector('select[aria-label="其他报表"]').value !== expected.catalog) throw new Error('Wrong report catalog kind');
  }
  await until(() => document.querySelector('#root')?.dataset.workbenchBoot === 'ready', 'React boot ready');
  if (document.documentElement.dataset.theme !== 'dark') {
    // This probe targets the current main shell; archived AppShell fixtures keep their own status-label contract.
    const toggles = [...document.querySelectorAll('#root[data-workbench-boot="ready"] .top-header button')]
      .filter(node => visible(node) && !node.disabled && node.textContent.replace(/^[☀☾]/, '').trim() === '切换深色');
    if (toggles.length !== 1) throw new Error('Missing unique current workbench theme control');
    toggles[0].click();
  }
  await until(() => document.documentElement.dataset.theme === 'dark', 'real workbench dark theme');
  const actions = { preflight, plan, gantt, 'system-logs': logs, 'invalid-history': invalidHistory,
    history: planCatalog, 'batch-import': batchImport,
    'batch-material': () => openDetails('物料齐套原记录'), 'system-config': () => click('#sm-tab-config'),
    'process-create': processCreate, 'report-catalog': catalog, field };
  if (expected.action) {
    if (!actions[expected.action]) throw new Error('Unknown geometry action ' + expected.action);
    await actions[expected.action]();
  }
  if (expected.ready) await present(expected.ready);
  for (const selector of expected.selectors) await present(selector);
  for (const text of expected.texts) await until(() => document.body.innerText.includes(text), 'expected visible text ' + text);
  await frame();
  return { case: expected.case, action: expected.action, ready: true, theme: document.documentElement.dataset.theme };
}

export function buildScenarioPreparationExpression(expected) {
  return '(' + prepareCurrentScenario.toString() + ')(' + JSON.stringify(expected) + ')';
}
