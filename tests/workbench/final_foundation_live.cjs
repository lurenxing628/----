'use strict';
const fs = require('node:fs'), path = require('node:path');
const control = JSON.parse(fs.readFileSync(process.argv[2])), root = control.root;
if (control.source_guard) {
  const Module = require('node:module'), originalLoad = Module._load;
  // Reject original-tree modules before evaluation, including dependency resolution fallbacks.
  Module._load = function(request, parent, isMain) {
    const resolved = Module._resolveFilename(request, parent, isMain);
    if (path.isAbsolute(resolved)) {
      const actual = fs.realpathSync(resolved);
      for (const forbidden of control.source_guard.forbidden_roots) {
        if (actual === forbidden || actual.startsWith(forbidden + path.sep)) throw new Error('Original source module rejected: ' + actual);
      }
    }
    return originalLoad.apply(this, arguments);
  };
}
const {chromium} = require('playwright');
const {Record, write, settle} = require('./final_foundation_live_probe.cjs');
const {firstViews, navigationChain, assertRestored, remembered} = require('./final_foundation_live_actions.cjs');
const {faults, focusedBootFaults} = require('./final_foundation_live_faults.cjs');
const {canonicalNavigation, restartCanonical, routeState} = require('./final_foundation_live_navigation.cjs');

const record = new Record(root, control.initial);
const execution = control.execution;
record.data.expected = execution;
function sourceBinding() {
  if (!control.source_guard) return {required: false};
  const guard = control.source_guard, source = path.resolve(__dirname, '../..');
  record.equal(source, guard.expected_root, 'Node entrypoint must also come from the expected frozen source');
  for (const [relative, digest] of Object.entries(guard.test_snapshot.files)) {
    const file = fs.realpathSync(path.join(source, relative));
    record.ok(file.startsWith(source + path.sep), 'Copied tests cannot resolve to the original source');
    record.equal(require('node:crypto').createHash('sha256').update(fs.readFileSync(file)).digest('hex'), digest, relative);
  }
  const modules = Object.keys(require.cache);
  for (const file of modules) for (const forbidden of guard.forbidden_roots) {
    record.ok(file !== forbidden && !file.startsWith(forbidden + path.sep), 'Node cannot import the original source');
  }
  return {expected_root: source, test_snapshot_sha256: guard.test_snapshot.sha256, loaded_modules: modules,
    original_source_fallback: false};
}
const matrix = [{width: 1392, height: 924}, {width: 1920, height: 1080}].flatMap(size => ['light', 'dark'].map(theme => ({...size, theme, id: `${size.width}x${size.height}-${theme}`})));
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function waitRestart(entries, browser) {
  record.equal(entries.length, execution.restart_pages); record.ok(browser.isConnected());
  const pages = [];
  for (const entry of entries) pages.push({state: entry.state.id, page_id: entry.page.foundationPageId,
    context_id: entry.context.foundationContextId, alive: !entry.page.isClosed(),
    saved: entry.family === 'canonical' ? await routeState(entry.page) : await remembered(entry.page)});
  write(path.join(root, 'foundation-restart-request.json'), {nonce: control.nonce, browser_pid: process.pid, pages});
  console.log('FOUNDATION_RESTART_REQUESTED ' + process.pid);
  const file = path.join(root, 'foundation-restart-ready.json'), deadline = Date.now() + 150000;
  while (!fs.existsSync(file)) {
    record.ok(browser.isConnected() && entries.every(entry => !entry.page.isClosed()), 'Browser/pages must stay alive while only Python host restarts');
    if (Date.now() > deadline) throw new Error('Main host restart handshake timed out');
    await sleep(100);
  }
  const restarted = JSON.parse(fs.readFileSync(file));
  record.equal(restarted.nonce, control.nonce); record.equal(restarted.browser_pid, process.pid);
  record.equal(restarted.ready.url, control.initial.url); record.ok(restarted.ready.pid !== control.initial.pid && restarted.old_pid_stopped);
  record.data.restart = {before_pid: control.initial.pid, after_pid: restarted.ready.pid, same_origin: restarted.ready.url, browser_pid: process.pid, pages_preserved: pages};
  for (const entry of entries) {
    if (entry.family === 'canonical') { await restartCanonical(entry, record); continue; }
    await record.run(entry.page, entry.state, 'host_restart', 'same-page-context-after-host-restart', async () => {
      record.ok(entry.restartState, 'The normal user chain must have produced a durable original context');
      record.ok(!entry.page.isClosed()); await entry.page.bringToFront();
      const before = await remembered(entry.page);
      record.equal(before.route.context, entry.restartState.route.context);
      await entry.page.reload(); await settle(entry.page, record);
      return {same_page: true, original: entry.restartState, reloaded: await assertRestored(entry, entry.restartState, record)};
    });
  }
}

async function main() {
  const entries = [];
  record.data.source_binding_before = sourceBinding();
  const browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true,
    args: ['--disable-background-networking', '--disable-component-update']});
  record.data.browser_version = browser.version(); record.ok(record.data.browser_version.startsWith('109.'));
  try {
    for (const state of matrix) {
      if (execution.groups.includes('legacy')) {
        const entry = await record.context(browser, state); entries.push(entry);
        await firstViews(entry, record);
        try { await navigationChain(entry, record); }
        catch (error) { record.data.cases.push({state: state.id, kind: 'interaction', name: 'prepare-restart-context', status: 'failed', error: String(error.stack || error)}); }
        await faults(browser, state, record);
      }
      if (execution.groups.includes('canonical')) entries.push(...await canonicalNavigation(browser, state, record, control.navigation));
      if (execution.groups.includes('boot')) await focusedBootFaults(browser, state, record);
    }
    if (execution.restart_pages) await waitRestart(entries, browser);
    record.equal(record.data.external_requests, []); record.equal(record.data.normal_errors, []);
    if (execution.groups.includes('legacy')) record.ok(record.data.scroll_actions.some(row => !row.skipped), 'At least one supported viewport must exercise real main-content scrolling');
    for (const [kind, count] of Object.entries(execution.case_kinds)) record.equal(record.data.cases.filter(row => row.kind === kind).length, count);
    record.equal(record.data.cases.length, execution.total_cases);
    record.equal(new Set(record.data.cases.map(row => [row.state, row.kind, row.name].join(':'))).size, execution.total_cases);
    record.ok(record.data.cases.every(row => row.status === 'passed'), 'Inspect separately recorded failed cases');
    record.data.complete = true;
  } catch (error) {
    record.data.error = String(error.stack || error); console.error(record.data.error); process.exitCode = 1;
  } finally {
    for (const entry of entries) {
      await record.flush(entry.page);
    }
    for (const context of browser.contexts()) await context.close();
    await browser.close(); await Promise.all(record.pending);
    record.data.source_binding_after = sourceBinding();
    if (record.data.normal_errors.length || record.data.external_requests.length || record.data.cases.some(row => row.status !== 'passed')) {
      record.data.complete = false; process.exitCode = 1;
    }
    record.data.summary = {cases: record.data.cases.length, failed: record.data.cases.filter(row => row.status !== 'passed').length,
      screenshots: record.data.screenshots.length, production_responses: record.data.api_responses.filter(row => row.phase === 'normal' && row.body.meta && row.body.meta.source === 'production').length};
    record.save(); console.log(JSON.stringify({root, complete: record.data.complete, ...record.data.summary}));
  }
}
main().catch(error => { record.data.error = String(error.stack || error); record.save(); console.error(error); process.exitCode = 1; });
