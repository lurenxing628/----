'use strict';
const {SIDEBAR, settle, navigate, shell, hash} = require('./final_foundation_live_probe.cjs');
const {chooseOfficial, caption, remembered} = require('./final_foundation_live_actions.cjs');
const {bootCases, injectBoot} = require('./final_foundation_live_boot_cases.cjs');

function sourceAsset(record, source) {
  const matches = record.assets.files.filter(row => (row.source_files || []).some(item => item.path === source));
  record.equal(matches.length, 1, 'Fault must target an actual private-build source asset');
  return record.ready.url + '/static/' + matches[0].path;
}
async function loadedScript(page, asset, record) {
  const matches = await page.locator('script[src]').evaluateAll((nodes, expected) => nodes.map(node => node.src)
    .filter(source => new URL(source).pathname === new URL(expected).pathname), asset);
  record.equal(matches.length, 1, 'Fault targets the actual loaded script URL, including its cache version');
  return matches[0];
}
async function bootFault(browser, state, record, fault) {
  const focused = bootCases.find(row => row.id === fault);
  record.ok(focused || ['missing-main', 'missing-react', 'malformed-boot'].includes(fault), 'Known fault definition required');
  const entry = await record.context(browser, state, 'fault:' + fault);
  const {page, context} = entry;
  await record.run(page, state, focused ? 'boot_contract_fault' : 'fault', fault, async () => {
    await page.goto(record.ready.workbench_url); await settle(page, record);
    if (await page.locator('html').getAttribute('data-theme') !== state.theme) await page.getByRole('button', {name: /^切换(?:深色|浅色)$/}).click();
    record.equal(await page.locator('html').getAttribute('data-theme'), state.theme);
    let target;
    if (fault === 'missing-main') target = sourceAsset(record, 'frontend/workbench/app/main.jsx');
    else if (fault === 'missing-react') {
      const matches = record.assets.scripts.filter(name => /\/react-\d.*\.production\.min\.js$/.test(name));
      record.equal(matches.length, 1); target = record.ready.url + '/static/' + matches[0];
    } else target = record.ready.workbench_url;
    if (['missing-main', 'missing-react'].includes(fault)) target = await loadedScript(page, target, record);
    let hits = 0;
    const handler = async route => {
      hits++;
      record.data.fault_events.push({state: state.id, kind: fault, injection_hit: hits, url: route.request().url()});
      if (['missing-main', 'missing-react'].includes(fault)) return route.abort('failed');
      const response = await route.fetch(), original = await response.text();
      const expression = /(<script\b[^>]*\bid=["']workbench-boot["'][^>]*>)[\s\S]*?(<\/script>)/g;
      record.equal(Array.from(original.matchAll(expression)).length, 1, 'Only the actual boot JSON script is replaced');
      const injected = focused ? injectBoot(original, focused).body : original.replace(expression, '$1{FOUNDATION_MALFORMED_BOOT$2');
      record.data.fault_events.push({state: state.id, kind: fault, original_html_sha256: hash(original), injected_html_sha256: hash(injected)});
      return route.fulfill({response, body: injected});
    };
    await page.route(target, handler);
    await record.flush(page);
    await page.reload();
    record.equal(hits, 1, 'Fault injection must hit the real versioned response');
    await page.locator('#root[data-workbench-boot="failed"]').waitFor({timeout: 20000});
    const error = await page.getByRole('alert').allTextContents();
    record.equal(await page.locator('html').getAttribute('data-theme'), state.theme);
    record.ok(error.some(value => /资源|启动|信息.*读取|消息.*格式|没有打开成功/.test(value)), 'Boot failure is readable without main');
    record.ok(await page.getByRole('link', {name: '重新加载', exact: true}).isVisible());
    const faultShot = await record.shot(page, state, fault + '-injected', 'fault');
    const navDuringFault = await page.locator('.sidebar-nav a.nav-item').count();
    await page.unroute(target, handler);
    await page.getByRole('link', {name: '重新加载', exact: true}).click();
    await settle(page, record); await shell(page, 'dashboard', record); await navigate(page, 'basedata', record);
    return {injected: true, injection_hits: hits, business_success_evidence: false, target, error, nav_during_fault: navDuringFault,
      boot_navigation_not_applicable: 'Main protocol: boot failure requires readable error and real reload, not an unstarted synthetic navigation shell',
      fault_screenshot: faultShot.file, nav_after_real_retry: SIDEBAR.length};
  });
  await record.flush(page); await context.close();
}
async function renderFault(browser, state, record) {
  const entry = await record.context(browser, state, 'fault:workspace-render-throw');
  const {page, context} = entry;
  await record.run(page, state, 'fault', 'workspace-render-throw', async () => {
    await page.goto(record.ready.workbench_url); await settle(page, record);
    if (await page.locator('html').getAttribute('data-theme') !== state.theme) await page.getByRole('button', {name: /^切换(?:深色|浅色)$/}).click();
    const selected = await chooseOfficial(entry, record), before = await remembered(page);
    const target = await loadedScript(page, sourceAsset(record, 'frontend/workbench/app/PlanWorkspace.jsx'), record);
    let hits = 0;
    const handler = async route => {
      hits++;
      record.data.fault_events.push({state: state.id, kind: 'workspace-render-throw', injection_hit: hits, url: route.request().url()});
      const response = await route.fetch(), original = await response.text();
      const injected = original + '\n;(function(){const Original=window.PlanWorkspace;window.__foundationRenderFail=true;window.PlanWorkspace=function FoundationInjectedFailure(props){if(window.__foundationRenderFail)throw new Error("FOUNDATION_INJECTED_RENDER");return React.createElement(Original,props);};})();\n';
      record.data.fault_events.push({state: state.id, kind: 'workspace-render-throw', original_sha256: hash(original), injected_sha256: hash(injected)});
      return route.fulfill({response, body: injected});
    };
    await page.route(target, handler); await record.flush(page); await page.reload();
    record.equal(hits, 1, 'Workspace render injection must hit the real versioned response');
    await page.getByRole('region', {name: '工作区读取失败', exact: true}).waitFor();
    record.equal(await page.locator('.sidebar-nav a.nav-item').count(), SIDEBAR.length);
    record.ok((await page.getByRole('alert').innerText()).includes('页面显示出错。请点「重新打开此工作区」；仍不行请刷新页面。'));
    record.equal((await remembered(page)).route.context.plan_ref, selected.reference);
    const faultShot = await record.shot(page, state, 'workspace-render-throw-injected', 'fault');
    await navigate(page, 'basedata', record);
    await page.goBack(); await page.getByRole('region', {name: '工作区读取失败', exact: true}).waitFor();
    record.equal((await remembered(page)).route.context.plan_ref, selected.reference);
    // Only fault injection state is changed; ordinary cases never call product hooks or mutate history.
    await page.evaluate(() => { window.__foundationRenderFail = false; });
    await page.getByRole('button', {name: '重新打开此工作区', exact: true}).click();
    await settle(page, record); await shell(page, 'analysis', record);
    const after = await caption(page, state, selected.reference, record);
    record.equal((await remembered(page)).route.context.plan_ref, before.route.context.plan_ref);
    await page.unroute(target, handler);
    return {injected: true, injection_hits: hits, business_success_evidence: false, target, nav_during_fault: SIDEBAR.length, before,
      fault_screenshot: faultShot.file, recovered_plan: after.plan, same_object_retry: true};
  });
  await record.flush(page); await context.close();
}
async function faults(browser, state, record) {
  for (const kind of ['missing-main', 'missing-react', 'malformed-boot']) await bootFault(browser, state, record, kind);
  await renderFault(browser, state, record);
}
async function focusedBootFaults(browser, state, record) {
  for (const specification of bootCases) await bootFault(browser, state, record, specification.id);
}
module.exports = {faults, focusedBootFaults};
