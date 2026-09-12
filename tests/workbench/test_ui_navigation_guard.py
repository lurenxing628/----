"""Real browser history and boot contracts for the consolidated workbench shell."""

from tests._support.workbench_browser_contract import browser_contract
from tests._support.workbench_web_contract import boot_payload

INPUTS = ("frontend/workbench/app/WorkbenchNavigation.js",)


def test_boot_navigation_rejects_missing_duplicate_or_mislabelled_entries(app_client):
    boot = boot_payload(app_client.get("/workbench"))
    observed = browser_contract("""
const N = window.WorkbenchNavigation, original = data.boot;
N.validateBoot(original);
const mutations = [
  boot => boot.nav_groups[1].items.pop(),
  boot => boot.nav_groups[1].items.push({...boot.nav_groups[0].items[0]}),
  boot => boot.nav_groups[1].items[0].label = '错误名称',
  boot => boot.nav_groups[1].items[0].icon = 'missing-icon',
  boot => boot.view_aliases.gantt = 'review',
  boot => delete boot.view_aliases.delay,
  boot => boot.enabled_views.push('delay'),
];
for (const mutate of mutations) {
  const boot = JSON.parse(JSON.stringify(original)); mutate(boot);
  let refused = false; try { N.validateBoot(boot); } catch (_) { refused = true; }
  expect(refused, 'Invalid navigation was accepted');
}
expect(N.title(original, {view: 'analysis', context: {source: 'run_history'}}) === '排产历史');
expect(N.title(original, {view: 'analysis', context: {source: 'run_history', run_ref: 'x'}}) === original.titles.analysis);
expect(N.historyView({view: 'analysis', context: {source: 'run_history'}}) === true);
expect(N.historyView({view: 'gantt', context: {source: 'run_history', candidate_ref: 'x'}}) === false);
expect(N.historyView({view: 'reports', context: {source: 'run_history'}}) === false);
expect(N.helpUrl(original, {view: 'analysis', context: {}}) === '/scheduler/config/manual?src=%2Fworkbench%3Fview%3Danalysis',
  'help must carry the current view so the manual can offer a way back');
return {refused: mutations.length};
""", scripts=INPUTS, data={"boot": boot})
    assert observed == {"refused": 7}


def test_history_guard_cancels_back_then_allows_back_and_forward_without_losing_draft(app_client):
    boot = boot_payload(app_client.get("/workbench"))
    observed = browser_contract("""
const N = window.WorkbenchNavigation, boot = data.boot;
let current = N.read(boot), dirty = false, resolveLeave = null, prompts = 0, restored = 0;
const errors = [], draft = document.createElement('input'); draft.value = '未保存批次说明'; document.body.appendChild(draft);
const control = N.guardHistory(boot, {hasDirty: () => dirty,
  confirmLeave: () => { prompts++; return new Promise(resolve => {resolveLeave = resolve;}); },
  onRestore: () => { restored++; current = N.read(boot); }, onError: error => errors.push(error.message)});
const move = (view, context) => { current = N.navigate(boot, current, view, context); control.sync(); };
const wait = async predicate => { for (let i = 0; i < 200; i++) { if (predicate()) return; await new Promise(resolve => setTimeout(resolve, 10)); } throw new Error('history transition timed out'); };
move('batches', {entity_ref: 'a'.repeat(48)});
move('analysis', {plan_ref: 'b'.repeat(48), range_start: '2026-05-06T00:00:00', range_end: '2026-05-07T00:00:00'});
const original = {url: location.href, key: current.key, context: JSON.stringify(N.read(boot).context)};
dirty = true; history.go(-2);
await wait(() => prompts === 1 && location.href === original.url);
expect(current.key === original.key && restored === 0 && draft.value === '未保存批次说明');
resolveLeave(false); await wait(() => !control.busy());
expect(location.href === original.url && JSON.stringify(N.read(boot).context) === original.context);
history.back(); await wait(() => prompts === 2 && location.href === original.url);
resolveLeave(true); await wait(() => restored === 1 && !control.busy());
expect(current.view === 'batches' && N.read(boot).context.entity_ref === 'a'.repeat(48));
history.forward(); await wait(() => prompts === 3 && N.read(boot).view === 'batches');
resolveLeave(false); await wait(() => !control.busy());
expect(current.view === 'batches' && N.read(boot).view === 'batches' && restored === 1);
dirty = false; history.forward(); await wait(() => restored === 2);
expect(current.view === 'analysis' && JSON.stringify(current.context) === original.context && prompts === 3);
control.dispose();
expect(errors.length === 0, errors.join(';'));
return {prompts, restored, draft: draft.value, context: current.context};
""", scripts=INPUTS, data={"boot": boot})
    assert observed["prompts"] == 3 and observed["restored"] == 2
    assert observed["draft"] == "未保存批次说明"
    assert observed["context"]["plan_ref"] == "b" * 48


def test_explicit_initial_navigation_survives_repeated_guarded_history_and_back_during_prompt(app_client):
    import json

    navigation = {"version": 1, "view": "gantt", "context": {
        "plan_ref": "c" * 48, "range_start": "2026-05-01T00:00:00", "range_end": "2026-05-04T00:00:00"}}
    boot = boot_payload(app_client.get("/workbench", query_string={"view": "gantt", "nav": json.dumps(navigation)}))
    observed = browser_contract("""
const N = window.WorkbenchNavigation, boot = data.boot;
const initialURL = '/workbench?view=gantt&nav=' + encodeURIComponent(JSON.stringify(boot.navigation));
history.replaceState(null, '', initialURL);
let current = N.read(boot), resolveLeave = null, prompts = 0, restored = 0;
const errors = [], control = N.guardHistory(boot, {hasDirty: () => true,
  confirmLeave: () => { prompts++; return new Promise(resolve => {resolveLeave = resolve;}); },
  onRestore: () => { restored++; current = N.read(boot); }, onError: error => errors.push(error.message)});
const wait = async predicate => { for (let i = 0; i < 200; i++) { if (predicate()) return; await new Promise(resolve => setTimeout(resolve, 10)); } throw new Error('explicit history transition timed out'); };
current = N.navigate(boot, current, 'batches', {entity_ref: 'd'.repeat(48)}); control.sync();
current = N.navigate(boot, current, 'analysis', {plan_ref: 'e'.repeat(48)}); control.sync();
for (let round = 0; round < 3; round++) {
  const before = prompts; history.go(-2);
  await wait(() => prompts === before + 1 && N.read(boot).key === 2);
  if (round === 0) {
    history.back();
    await new Promise(resolve => setTimeout(resolve, 100));
    expect(N.read(boot).key === 2 && prompts === before + 1, 'Repeated back escaped pending confirmation');
  }
  resolveLeave(true); await wait(() => !control.busy() && current.key === 0);
  expect(current.view === 'gantt' && JSON.stringify(current.context) === JSON.stringify(boot.navigation.context));
  expect(location.pathname + location.search === initialURL, 'Explicit nav URL was rewritten');
  history.go(2); await wait(() => prompts === before + 2 && N.read(boot).key === 0);
  resolveLeave(true); await wait(() => !control.busy() && current.key === 2);
  expect(current.view === 'analysis' && current.context.plan_ref === 'e'.repeat(48));
}
control.dispose(); expect(errors.length === 0, errors.join(';'));
return {prompts, restored, key: current.key};
""", scripts=INPUTS, data={"boot": boot})
    assert observed == {"prompts": 6, "restored": 6, "key": 2}


def test_view_tab_resumes_saved_context_and_first_visit_uses_explicit_source(app_client):
    boot = boot_payload(app_client.get("/workbench"))
    observed = browser_contract("""
const N = window.WorkbenchNavigation, boot = data.boot;
let page = N.read(boot);
const saved = {scope: {plan_ref: 'a'.repeat(48), query: 'OP', plan_finish_date_from: '2026-09-09'},
  table: {topic: 'delivery', page: 2, size: 20}, selected: 'b'.repeat(48), detailView: {page: 3, size: 10}};
page = N.navigate(boot, page, 'review', saved);
page = N.navigate(boot, page, 'field', {task_ref: 'c'.repeat(48)});
page = N.navigate(boot, page, 'reports', {scope: {plan_ref: 'd'.repeat(48)}, topic: 'records'});
const fallback = {scope: {plan_ref: 'd'.repeat(48)}, topic: 'delivery'};
page = N.navigate(boot, page, 'review', fallback, true);
expect(JSON.stringify(page.context) === JSON.stringify(saved),
  'Tab switch must restore the whole saved context of the target tab instead of mixing in the current range');
expect(page.context.scope.plan_ref === 'a'.repeat(48) && page.context.table.page === 2 && page.context.selected === 'b'.repeat(48));
const first = {scope: {plan_ref: 'e'.repeat(48)}};
page = N.navigate(boot, page, 'calib', first, true);
expect(JSON.stringify(page.context) === JSON.stringify(first), 'First visit discarded its explicit source');
const drilled = {scope: {plan_ref: 'f'.repeat(48), query: 'new'}, table: {page: 1, size: 20}};
page = N.navigate(boot, page, 'review', drilled);
expect(JSON.stringify(page.context) === JSON.stringify(drilled), 'Explicit drill/return was replaced by cached state');
let rejected = false; try { N.navigate(boot, page, 'reports', fallback, 'true'); } catch (_) { rejected = true; }
expect(rejected, 'Invalid resume policy was silently accepted');
return {saved_restored: true, first_source_kept: true, explicit_source_kept: true, invalid_policy_rejected: rejected};
""", scripts=INPUTS, data={"boot": boot})
    assert observed == {"saved_restored": True, "first_source_kept": True,
                        "explicit_source_kept": True, "invalid_policy_rejected": True}
