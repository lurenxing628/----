'use strict';
const path = require('node:path');
const {settle, shell, geometry} = require('./final_foundation_live_probe.cjs');

const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const field = (value, key) => key.split('.').reduce((at, part) => at == null ? undefined : at[part], value);
const timeLabel = value => String(value).replace('T', ' ');
function subset(value, expected, record, label) {
  for (const [key, item] of Object.entries(expected)) {
    if (item && typeof item === 'object' && !Array.isArray(item)) {
      record.ok(value && value[key] && typeof value[key] === 'object', label + '.' + key);
      subset(value[key], item, record, label + '.' + key);
    } else record.equal(value && value[key], item, label + '.' + key);
  }
}
function savedContext(current, recipe, record) {
  if (current.route == null) {
    record.equal(recipe.view, 'trial', 'Only the non-snapshot trial workspace may leave initial history empty');
    return {persisted: false, proof: 'Actual URL boot, page-specific DTO and visible trial identity; history was not fabricated'};
  }
  record.equal(current.route.view, recipe.view);
  subset(current.route.context, recipe.payload.context, record, 'restored context');
  return {persisted: true, proof: 'Actual history context plus actual URL boot and page-specific DTO'};
}
async function routeState(page) {
  return page.evaluate(() => ({url: location.href, route: history.state && history.state.workbench,
    theme: document.documentElement.getAttribute('data-theme')}));
}
async function prepareTheme(entry, record) {
  const warm = await record.page(entry.context, entry.state);
  try {
    await warm.page.goto(record.ready.workbench_url); await settle(warm.page, record);
    if (await warm.page.locator('html').getAttribute('data-theme') !== entry.state.theme) {
      await warm.page.getByRole('button', {name: /^深色：/}).click();
    }
    record.equal(await warm.page.locator('html').getAttribute('data-theme'), entry.state.theme);
  } finally { await record.flush(warm.page); await warm.page.close(); }
}
function responses(record, page, after) {
  return record.data.api_responses.slice(after).filter(row => row.page_id === page.foundationPageId);
}
async function dtoResponse(page, specification, record, after, expectedStatus = 200) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    await Promise.all(record.pending);
    const rows = responses(record, page, after).filter(row => row.method === specification.method && new URL(row.url).pathname === specification.path);
    if (rows.length) {
      const row = rows[rows.length - 1], url = new URL(row.url);
      record.equal(row.status, expectedStatus, 'The actual domain request must succeed or fail exactly as planned');
      for (const [name, expected] of Object.entries(specification.request_query || {})) {
        record.equal(url.searchParams.getAll(name), [String(expected)], 'Actual DTO request scope: ' + name);
      }
      if (specification.request_json) record.equal(JSON.parse(row.request_body), specification.request_json, 'Actual preview POST input');
      if (expectedStatus === 200) {
        record.equal(row.body.meta.source, 'production');
        for (const [name, expected] of Object.entries(specification.response_fields || {})) record.equal(field(row.body, name), expected, name);
        if (specification.response_scope) subset(row.body.data.scope, specification.response_scope, record, 'response.scope');
      }
      return row;
    }
    await pause(25);
  }
  throw new Error('No actual page-specific domain response: ' + specification.method + ' ' + specification.path);
}
async function boot(page, response, recipe, record) {
  record.ok(response, 'A real document response is required'); record.equal(response.status(), recipe.html_status);
  await settle(page, record); await shell(page, recipe.view, record);
  const value = JSON.parse(await page.locator('#workbench-boot').textContent());
  const url = new URL(page.url());
  record.equal(value.navigation, recipe.payload, 'Server boot must preserve the canonical URL object');
  record.equal(JSON.parse(url.searchParams.get('nav')), recipe.payload, 'Never replace the explicit URL context');
  return value.navigation;
}
async function caption(page, recipe, dto, record) {
  const target = page.locator('.wb-current-plan');
  if (recipe.caption.applicable === false) {
    record.equal(await target.count(), 0, 'A source preview must not invent a draft caption');
    record.equal(await page.locator('[data-trial-workspace]').getAttribute('data-open-ref'), '');
    return {applicable: false, reason: recipe.caption.reason};
  }
  await target.waitFor(); const data = dto.body.data;
  const draft = recipe.caption.identity === 'draft', plan = data.plan;
  const name = draft ? data.name || (data.base_identity.display_name || '原排产候选')
    + (data.base_identity.plan_ref && data.base_identity.version ? ' · v' + data.base_identity.version : '') : plan.display_name;
  const expected = {reference: recipe.caption.reference, name,
    label: draft ? '当前草稿' : recipe.view === 'reports' ? '报表计划' : '当前方案',
    status: draft ? '试调草稿 · 可继续试调' : recipe.view === 'reports' ? '当前正式采用' : '当前正式',
    version: draft ? '创建时正式基线 v' + data.baseline.version : '正式 v' + plan.version};
  record.equal(await target.getAttribute('data-plan-ref'), expected.reference);
  record.equal(await target.locator('.wb-current-name').innerText(), name);
  record.equal(await target.locator('strong').innerText(), expected.label);
  record.equal(await target.locator('.cap-preview').innerText(), expected.status);
  record.ok((await target.innerText()).includes(expected.version), 'Header version follows the actual response');
  const range = await target.locator('.wb-current-range').innerText();
  const bounds = draft ? [data.time_scope.start, data.time_scope.end] : recipe.view === 'reports'
    ? [data.scope.plan_finish_date_from, data.scope.plan_finish_date_to] : [data.scope.range_start, data.scope.range_end];
  for (const value of bounds) record.ok(range.includes(timeLabel(value)), 'Header range follows the actual response');
  if (draft) record.equal(await page.locator('[data-trial-workspace]').getAttribute('data-open-ref'), data.draft_ref);
  return {...expected, range};
}
async function positiveRead(entry, response, record, after, transition) {
  const {page, recipe, state} = entry;
  const navigation = await boot(page, response, recipe, record);
  record.equal(await page.locator('html').getAttribute('data-theme'), state.theme);
  if (recipe.dto.trigger) await page.getByRole('button', {name: '核对原来源', exact: true}).click();
  const dto = await dtoResponse(page, recipe.dto, record, after);
  await settle(page, record);
  const current = await routeState(page);
  const contextEvidence = savedContext(current, recipe, record);
  for (const row of responses(record, page, after)) {
    if (row.status === 200 && row.body.data && row.body.data.plan) {
      const reference = recipe.payload.context.plan_ref || recipe.payload.context.scope && recipe.payload.context.scope.plan_ref;
      if (reference) record.equal(row.body.data.plan.plan_ref, reference, 'No successful replacement plan');
    }
  }
  return {transition, navigation, actual_state: current, context_evidence: contextEvidence, dto: {file: dto.file, sha256: dto.sha256, url: dto.url,
    method: dto.method, page_id: dto.page_id}, caption: await caption(page, recipe, dto, record),
    geometry: await geometry(page, record), same_page_id: page.foundationPageId, context_id: entry.context.foundationContextId};
}
async function positive(browser, state, recipe, record) {
  const entry = {...await record.context(browser, state), recipe, family: 'canonical'};
  const {page} = entry;
  await prepareTheme(entry, record);
  await record.run(page, state, 'canonical_navigation', recipe.id + '--direct_url', async () => {
    const after = record.data.api_responses.length;
    const response = await page.goto(record.ready.url + recipe.url_suffix);
    return positiveRead(entry, response, record, after, 'direct_url');
  });
  entry.originalUrl = page.url();
  const copy = {...await record.page(entry.context, state), recipe};
  try {
    await record.run(copy.page, state, 'canonical_navigation', recipe.id + '--copy_url_new_tab', async () => {
      record.ok(copy.page !== page && copy.context === entry.context);
      record.equal(await copy.page.evaluate(() => history.state), null, 'New tab must have no inherited page history');
      const after = record.data.api_responses.length, response = await copy.page.goto(page.url());
      record.equal(copy.page.url(), entry.originalUrl);
      return positiveRead(copy, response, record, after, 'copy_url_new_tab');
    });
  } finally { await record.flush(copy.page); await copy.page.close(); }
  await record.run(page, state, 'canonical_navigation', recipe.id + '--same_tab_f5', async () => {
    await record.flush(page); const after = record.data.api_responses.length, before = await routeState(page);
    // Full document reload is the F5 semantic operation; no claim of a physical F5 key event.
    const response = await page.reload();
    record.equal(page.url(), entry.originalUrl);
    return {reload_mechanism: 'Playwright page.reload (full document F5 semantics)', before,
      ...await positiveRead(entry, response, record, after, 'same_tab_f5')};
  });
  entry.restartState = await routeState(page);
  return entry;
}
async function rejectNavigation(browser, state, recipe, record) {
  const entry = await record.context(browser, state, 'boundary:' + recipe.id), {page} = entry;
  try {
    await record.run(page, state, 'canonical_navigation', recipe.id + '--http400', async () => {
      const after = record.data.api_responses.length, response = await page.goto(record.ready.url + recipe.url_suffix);
      record.equal(response.status(), 400); await record.flush(page);
      record.equal(await page.locator('#workbench-boot').count(), 0);
      record.equal(responses(record, page, after).length, 0, 'Invalid host navigation must not bootstrap domain reads');
      record.ok(await page.getByRole('heading', {name: '工作台暂不可用', exact: true}).isVisible());
      const alerts = await page.getByRole('alert').allTextContents(); record.ok(alerts.some(value => value.trim().length > 5));
      const recovery = page.getByRole('navigation', {name: '恢复入口', exact: true});
      record.ok(await recovery.getByRole('link', {name: '重新加载', exact: true}).isVisible());
      const shot = await record.shot(page, state, recipe.id + '--http400-rejected', 'fault');
      page.foundationPhase = 'normal';
      await recovery.getByRole('link', {name: '打开工作台', exact: true}).click();
      await settle(page, record); await shell(page, 'dashboard', record);
      return {html_status: response.status(), error_screenshot: shot.file, alerts, recovery_by_real_link: true,
        expected_failure_not_business_success: true};
    });
  } finally { await record.flush(page); await entry.context.close(); }
}
function missingDTO(recipe) {
  const scope = recipe.payload.context;
  if (recipe.view === 'trial') return {method: 'POST', path: '/api/workbench/v1/trial/drafts/preview', request_json: scope};
  if (recipe.view === 'reports') return {method: 'GET', path: '/api/workbench/v1/analytics', request_query: scope.scope};
  const {plan_ref, ...range} = scope;
  return {method: 'GET', path: '/api/workbench/v1/plans/' + plan_ref + '/workspace', request_query: range};
}
async function unknownObject(browser, state, recipe, record) {
  const entry = await record.context(browser, state, 'boundary:' + recipe.id), {page} = entry;
  try {
    await prepareTheme(entry, record);
    await record.run(page, state, 'canonical_navigation', recipe.id + '--domain404', async () => {
      let after = record.data.api_responses.length;
      await boot(page, await page.goto(record.ready.url + recipe.url_suffix), recipe, record);
      record.equal(await page.locator('html').getAttribute('data-theme'), state.theme);
      if (recipe.view === 'trial') await page.getByRole('button', {name: '核对原来源', exact: true}).click();
      const specification = missingDTO(recipe), first = await dtoResponse(page, specification, record, after, 404);
      record.equal(first.body.error.code, recipe.domain_error_code);
      const assertFailure = async start => {
        await record.flush(page);
        const rows = responses(record, page, start);
        record.equal(await page.locator('.wb-current-plan').count(), 0, 'Unknown explicit object must not show another caption');
        record.ok((await page.getByRole('alert').allTextContents()).some(value => value.trim().length > 5));
        record.equal(rows.filter(row => row.status === 200 && row.body.data &&
          (row.body.data.plan || row.body.data.draft_ref || row.body.data.base && row.body.data.task_count !== undefined)), [], 'No substituted object DTO');
        record.equal(JSON.parse(new URL(page.url()).searchParams.get('nav')), recipe.payload);
      };
      await assertFailure(after);
      const shot = await record.shot(page, state, recipe.id + '--domain404-first', 'fault');
      after = record.data.api_responses.length;
      const label = recipe.view === 'trial' ? '核对原来源' : recipe.view === 'reports' ? '重新读取' : '重新读取所选计划';
      await page.getByRole('button', {name: label, exact: true}).click();
      const retry = await dtoResponse(page, specification, record, after, 404);
      record.equal(retry.body.error.code, recipe.domain_error_code); await assertFailure(after);
      return {missing_ref_verified_by_actual_404: recipe.missing_ref, first: first.file, retry: retry.file,
        failure_screenshot: shot.file, same_object_retry: true, expected_failure_not_business_success: true};
    });
  } finally { await record.flush(page); await entry.context.close(); }
}
async function canonicalNavigation(browser, state, record, plan) {
  record.equal(path.resolve(plan.source.root), path.resolve(record.root), 'Recipes must use this fixture, never a unit fixture');
  const entries = [];
  for (const recipe of plan.cases) {
    if (recipe.group === 'canonical-positive') entries.push(await positive(browser, state, recipe, record));
    else if (recipe.group === 'canonical-http400') await rejectNavigation(browser, state, recipe, record);
    else if (recipe.group === 'canonical-domain-failure') await unknownObject(browser, state, recipe, record);
    else throw new Error('Unknown canonical group: ' + recipe.group);
  }
  return entries;
}
async function restartCanonical(entry, record) {
  const {page, state, recipe} = entry;
  await record.run(page, state, 'canonical_navigation', recipe.id + '--same_tab_same_port_new_host_pid', async () => {
    record.ok(!page.isClosed()); record.equal(await routeState(page), entry.restartState, 'No history rewrite while the host is stopped');
    await page.bringToFront(); await record.flush(page);
    const after = record.data.api_responses.length, response = await page.reload();
    record.equal(page.url(), entry.originalUrl);
    return {before: entry.restartState, ...await positiveRead(entry, response, record, after, 'same_tab_same_port_new_host_pid')};
  });
}
module.exports = {canonicalNavigation, restartCanonical, routeState, subset, missingDTO, savedContext};
