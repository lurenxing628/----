'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app/WorkbenchNavigation.js'), 'utf8');
const boot = {titles: {dashboard: 'Dashboard', reports: 'Reports', trial: 'Trial', process: 'Resources'}, entry_url: '/workbench', trial_url: '/workbench/trial'};
let checks = 0;
function runtime(state = null, url = 'http://127.0.0.1:59991/workbench') {
  let location = new URL(url), now = 0;
  const panes = [];
  const entries = [{state, url: location.href}], frames = new Map(), events = new Map(), timers = new Map();
  // Inner panes are addressed by data-wb-scroll-key, so the fake .main-content answers querySelectorAll like the real element.
  const main = {scrollTop: 0, scrollLeft: 0, querySelectorAll: () => panes};
  let index = 0, frame = 0, timer = 0;
  const context = vm.createContext({URL, performance: {now: () => now}, document: {querySelector: () => main},
    get location() { return location; },
    history: {get state() { return entries[index].state; },
      replaceState(next, _title, nextURL) { entries[index] = {state: structuredClone(next), url: new URL(nextURL, location).href}; location = new URL(entries[index].url); },
      pushState(next, _title, nextURL) { entries.splice(++index); entries.push({state: structuredClone(next), url: new URL(nextURL, location).href}); location = new URL(entries[index].url); }},
    scrollY: 0, scrollX: 0, scrollTo(x, y) { context.scrollX = x; context.scrollY = y; },
    requestAnimationFrame(fn) { frames.set(++frame, fn); return frame; }, cancelAnimationFrame(id) { frames.delete(id); },
    setTimeout(fn, delay) { timers.set(++timer, {fn, delay}); return timer; }, clearTimeout(id) { timers.delete(id); },
    addEventListener(name, fn) { if (!events.has(name)) events.set(name, new Set()); events.get(name).add(fn); },
    removeEventListener(name, fn) { if (events.has(name)) events.get(name).delete(fn); }});
  context.window = context;
  vm.runInContext(source, context);
  const pane = key => { const node = {scrollTop: 0, scrollLeft: 0, getAttribute: name => name === 'data-wb-scroll-key' ? key : null}; panes.push(node); return node; };
  return {context, main, panes, pane, api: context.WorkbenchNavigation, entries, timers,
    runTimers() { const pending = [...timers.values()]; timers.clear(); pending.forEach(item => item.fn()); },
    back() { index--; location = new URL(entries[index].url); },
    forward() { index++; location = new URL(entries[index].url); },
    flush() { for (let step = 0; frames.size && step < 250; step++) { const pending = [...frames.values()]; frames.clear(); now += 16; pending.forEach(fn => fn()); } },
    event(name) { [...(events.get(name) || [])].forEach(fn => fn()); },
    setState(next) { entries[index].state = next; }};
}
function check(name, run) { run(); checks++; }
check('initial page has no business scope', () => { const r = runtime(); assert.equal(r.api.read(boot).view, 'dashboard'); });
check('trial has a separate URL', () => { const r = runtime(null, 'http://127.0.0.1:59991/workbench/trial'); assert.equal(r.api.read(boot).view, 'trial'); assert.equal(r.api.href(boot, 'trial'), '/workbench/trial'); });
check('unknown target refuses to navigate', () => { const r = runtime(); assert.throws(() => r.api.navigate(boot, r.api.read(boot), 'unknown', {})); assert.equal(r.entries.length, 1); });
check('invalid contexts never become a broad scope', () => { for (const context of [null, [], 1, '']) { const r = runtime({workbench: {view: 'dashboard', context, key: 0}}); assert.throws(() => r.api.read(boot)); } });
check('malformed saved state is visible', () => { for (const saved of [null, false, 0, [], {view: 'reports', context: {}, key: 0}]) { const r = runtime({workbench: saved}); assert.throws(() => r.api.read(boot)); } });
check('invalid saved keys are rejected', () => { for (const key of [-1, 0.5, '2', Infinity]) { const r = runtime({workbench: {view: 'dashboard', context: {}, key}}); assert.throws(() => r.api.read(boot)); } });
check('scope snapshot and opaque object references survive navigation and reload', () => {
  const r = runtime(), context = {scope: {batch_ref: 'opaque-batch', snapshot_ref: 'opaque-version'}, returnTo: {view: 'trial', context: {draft_ref: 'opaque-draft'}}};
  r.api.navigate(boot, r.api.read(boot), 'reports', context);
  assert.deepEqual(JSON.parse(JSON.stringify(r.api.read(boot).context)), context);
  const reload = runtime(r.context.history.state, r.context.location.href); assert.deepEqual(JSON.parse(JSON.stringify(reload.api.read(boot).context)), context);
});
check('sidebar return restores scope and both scrolling surfaces', () => {
  const r = runtime(); r.api.navigate(boot, r.api.read(boot), 'reports', {scope: {batch_ref: 'exact-only'}});
  r.context.scrollY = 120; r.main.scrollTop = 850; r.main.scrollLeft = 12;
  r.api.navigate(boot, r.api.read(boot), 'process', {}); r.context.scrollY = 0; r.main.scrollTop = 0;
  const returned = r.api.navigate(boot, r.api.read(boot), 'reports');
  assert.equal(returned.context.scope.batch_ref, 'exact-only'); let done = 0; r.api.restore(returned, () => done++); r.flush();
  assert.equal(done, 1); assert.equal(r.context.scrollY, 120); assert.equal(r.main.scrollTop, 850); assert.equal(r.main.scrollLeft, 12);
});
check('explicit fresh scope resets scroll without discarding old history', () => {
  const r = runtime(); r.api.navigate(boot, r.api.read(boot), 'reports', {scope: {batch_ref: 'old'}}); r.main.scrollTop = 100;
  const next = r.api.navigate(boot, r.api.read(boot), 'reports', {scope: {batch_ref: 'new'}}); assert.equal(next.context.scope.batch_ref, 'new');
  r.api.restore(next, () => {}); r.flush(); assert.equal(r.main.scrollTop, 0); r.back(); assert.equal(r.api.read(boot).context.scope.batch_ref, 'old');
});
check('page-specific history state is restored, not copied to another page', () => {
  const r = runtime({workbench: {view: 'dashboard', key: 0, context: {}}, original: {tab: 2}});
  r.api.navigate(boot, r.api.read(boot), 'process', {}); assert.equal(r.context.history.state.original, undefined);
  r.api.navigate(boot, r.api.read(boot), 'dashboard'); assert.equal(r.context.history.state.original.tab, 2);
});
check('replacing trial context preserves auxiliary state', () => {
  const r = runtime({workbench: {view: 'trial', key: 4, context: {}}, trialAdoptionHistory: {page: 3}}, 'http://127.0.0.1:59991/workbench/trial');
  r.api.replaceContext(boot, r.api.read(boot), {draft_ref: 'same-draft'}); assert.equal(r.context.history.state.trialAdoptionHistory.page, 3);
  assert.equal(r.api.read(boot).context.draft_ref, 'same-draft');
});
check('stale component may not overwrite a newer route', () => { const r = runtime(), first = r.api.read(boot); r.api.navigate(boot, first, 'reports', {}); assert.throws(() => r.api.replaceContext(boot, first, {})); });
check('corrupt sidebar history is rejected before widening a scope', () => { const r = runtime({workbenchPages: []}); assert.throws(() => r.api.navigate(boot, r.api.read(boot), 'reports')); });
check('installing history protection does not eagerly rewrite or consume invalid sidebar cache', () => {
  const r = runtime({workbenchPages: []}), original = JSON.stringify(r.context.history.state);
  const protection = r.api.guardHistory(boot, {hasDirty: () => false, confirmLeave: () => Promise.resolve(true), onRestore() {}, onError() {}});
  assert.equal(JSON.stringify(r.context.history.state), original);
  assert.throws(() => r.api.navigate(boot, r.api.read(boot), 'reports'));
  protection.dispose();
});
check('return context preserves report-owned scroll', () => { const r = runtime(); const next = r.api.navigate(boot, r.api.read(boot), 'reports', {scroll: {windowTop: 140, mainTop: 200}}); r.api.restore(next, () => {}); r.flush(); assert.equal(r.main.scrollTop, 200); assert.equal(r.context.scrollY, 140); });
check('inner panes keep their own scroll and unknown keys are skipped', () => {
  const r = runtime(); r.api.navigate(boot, r.api.read(boot), 'reports', {});
  const board = r.pane('plan-board'), inspector = r.pane('plan-inspector'), untracked = r.pane('');
  board.scrollLeft = 900; board.scrollTop = 40; inspector.scrollTop = 120; untracked.scrollTop = 7;
  r.api.navigate(boot, r.api.read(boot), 'process', {});
  board.scrollLeft = 0; board.scrollTop = 0; inspector.scrollTop = 0;
  const returned = r.api.navigate(boot, r.api.read(boot), 'reports');
  assert.deepEqual(returned.scroll.containers, {'plan-board': [900, 40], 'plan-inspector': [0, 120]});
  assert.equal(returned.scroll.mainTop, 0);
  const missing = r.pane('plan-catalog');
  let done = 0; r.api.restore(returned, () => done++); r.flush();
  assert.equal(done, 1); assert.equal(board.scrollLeft, 900); assert.equal(board.scrollTop, 40);
  assert.equal(inspector.scrollTop, 120); assert.equal(missing.scrollTop, 0);
});
check('a page without remembered panes restores the window surfaces only', () => {
  const r = runtime(); const board = r.pane('plan-board'); board.scrollTop = 55;
  let done = 0; r.api.restore({scroll: {mainTop: 30}}, () => done++); r.flush();
  assert.equal(done, 1); assert.equal(r.main.scrollTop, 30); assert.equal(board.scrollTop, 55);
});
check('user input cancels delayed restoration exactly once', () => { const r = runtime(); let done = 0; const cancel = r.api.restore({scroll: {mainTop: 200}}, () => done++); r.event('pointerdown'); r.flush(); cancel(); assert.equal(done, 1); assert.equal(r.main.scrollTop, 0); });
function navURL(value) { return 'http://127.0.0.1:59991/workbench?view=reports&nav=' + encodeURIComponent(JSON.stringify(value)); }
const explicitBoot = {...boot, navigation: {version: 1, view: 'reports', context: {scope: {batch_ref: 'specific'}}}};
check('explicit versioned URL retains its exact object without history', () => {
  const r = runtime(null, navURL(explicitBoot.navigation));
  assert.equal(r.api.read(explicitBoot).context.scope.batch_ref, 'specific');
});
check('explicit URL supersedes another object left in browser history', () => {
  const r = runtime({workbench: {view: 'reports', key: 8, context: {scope: {batch_ref: 'other'}}}}, navURL(explicitBoot.navigation));
  assert.equal(r.api.read(explicitBoot).context.scope.batch_ref, 'specific'); assert.equal(r.api.read(explicitBoot).key, 0);
});
check('matching explicit URL restores subsequent verified page selections', () => {
  const r = runtime(null, navURL(explicitBoot.navigation));
  r.api.replaceContext(explicitBoot, r.api.read(explicitBoot), {scope: {batch_ref: 'selected-later'}});
  assert.equal(r.api.read(explicitBoot).context.scope.batch_ref, 'selected-later');
});
check('invalid explicit payload cannot fall back to broader history', () => {
  for (const value of [null, [], {version: true, view: 'reports', context: {}}, {version: 2, view: 'reports', context: {}},
    {version: 1, view: 'dashboard', context: {}}, {version: 1, view: 'reports', context: []}, {version: 1, view: 'reports', context: {}, extra: 1}]) {
    const r = runtime(null, navURL(value)); assert.throws(() => r.api.read(boot));
  }
});
check('malformed JSON and repeated nav or view are rejected', () => {
  for (const query of ['view=reports&nav=%7B', 'view=reports&nav=null&nav=null', 'view=reports&view=dashboard']) {
    const r = runtime(null, 'http://127.0.0.1:59991/workbench?' + query); assert.throws(() => r.api.read(boot));
  }
});
check('trial path cannot contradict an explicit view', () => {
  const r = runtime(null, 'http://127.0.0.1:59991/workbench/trial?view=reports'); assert.throws(() => r.api.read(boot));
});
check('leaving an explicit URL drops its old navigation parameter', () => {
  const r = runtime(null, navURL(explicitBoot.navigation));
  r.api.navigate(explicitBoot, r.api.read(explicitBoot), 'process', {}); assert.equal(r.context.location.searchParams.has('nav'), false);
  r.back(); assert.equal(r.api.read(explicitBoot).context.scope.batch_ref, 'specific');
});
check('explicit URL requires matching server-validated navigation', () => {
  const r = runtime(null, navURL(explicitBoot.navigation));
  for (const navigation of [undefined, null, {}, {...explicitBoot.navigation, context: {scope: {batch_ref: 'other'}}},
    {...explicitBoot.navigation, context: {...explicitBoot.navigation.context, extra: 1}}]) {
    assert.throws(() => r.api.read({...boot, navigation}));
  }
});
check('server key ordering does not change exact JSON meaning', () => {
  const navigation = {context: {scope: {batch_ref: 'specific'}}, view: 'reports', version: 1};
  const r = runtime(null, navURL(navigation));
  assert.equal(r.api.read(explicitBoot).context.scope.batch_ref, 'specific');
});
check('arrays preserve order and types when binding server navigation', () => {
  const navigation = {version: 1, view: 'reports', context: {values: ['a', 'b'], count: 0, enabled: false}};
  const r = runtime(null, navURL(navigation)), expected = {...boot, navigation};
  assert.deepEqual(JSON.parse(JSON.stringify(r.api.read(expected).context)), navigation.context);
  for (const context of [{...navigation.context, values: ['b', 'a']}, {...navigation.context, count: '0'},
    {...navigation.context, enabled: 0}]) assert.throws(() => r.api.read({...boot, navigation: {...navigation, context}}));
});
check('help link carries the view id for the manual chapter next to the return address', () => {
  const r = runtime(), help = {...boot, help_url: '/scheduler/config/manual'};
  assert.equal(r.api.helpUrl(help, {view: 'reports', context: {}}), '/scheduler/config/manual?src=%2Fworkbench%3Fview%3Dreports&page=reports');
  assert.equal(r.api.helpUrl(help, {view: 'trial', context: {}}), '/scheduler/config/manual?src=%2Fworkbench%2Ftrial&page=trial');
});
check('continuous scrolling writes history once per throttle window; flush writes at once and cancel drops the write', () => {
  const r = runtime(); let writes = 0;
  const memory = r.api.scrollMemory(() => writes++);
  for (let step = 0; step < 10; step++) memory.schedule();
  assert.equal(writes, 0); assert.equal(r.timers.size, 1); assert.equal([...r.timers.values()][0].delay, 200);
  r.runTimers(); assert.equal(writes, 1);
  memory.schedule(); memory.flush(); assert.equal(writes, 2); assert.equal(r.timers.size, 0);
  memory.schedule(); memory.cancel(); r.runTimers(); assert.equal(writes, 2);
  assert.throws(() => r.api.scrollMemory(null)); assert.throws(() => r.api.scrollMemory(() => {}, -1));
});
check('a sub-throttle scroll snapshot is restored only when its original history entry becomes current again', () => {
  const r = runtime(), report = r.api.navigate(boot, r.api.read(boot), 'reports', {}), board = r.pane('report-table');
  r.context.scrollY = 20; r.main.scrollTop = 100; board.scrollLeft = 30; r.api.remember(boot, report);
  r.api.navigate(boot, r.api.read(boot), 'process', {});
  r.back();
  r.context.scrollY = 240; r.main.scrollTop = 900; board.scrollLeft = 760;
  const latest = r.api.captureScroll();
  r.back();
  assert.equal(r.api.read(boot).view, 'dashboard');
  assert.notEqual(r.context.history.state.workbench.scroll && r.context.history.state.workbench.scroll.mainTop, 900,
    'the Back target must not receive the outgoing entry scroll');
  r.forward();
  const returned = r.api.read(boot); r.api.remember(boot, returned, latest); r.main.scrollTop = 0; board.scrollLeft = 0;
  const refreshed = r.api.read(boot); r.api.restore(refreshed, () => {}); r.flush();
  assert.equal(r.context.scrollY, 240); assert.equal(r.main.scrollTop, 900); assert.equal(board.scrollLeft, 760);
});
process.stdout.write(JSON.stringify({checks, passed: checks, browser: false, production: false}) + '\n');
