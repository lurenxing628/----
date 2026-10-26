'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), { spawnSync } = require('node:child_process');
const { compile } = require('../../scripts/workbench/compile.cjs');

// Run the delivered bundle, or the changed source with --source, using real HTTP/storage adapters.
async function contract(h, assert) {
  const w = h.runtime, C = w.PreflightContract;
  const batch = h.reference(1), other = h.reference(2), inputRef = 'i'.repeat(32), writeToken = 'w'.repeat(32);
  const input = C.input({ batch_refs: [batch, other], start_date: '2026-10-11', end_date: '2026-10-17',
    ready_check: true, material_strategy: 'stage', missing_resource_policy: 'exclude', completed_policy: 'preserve_actuals', hold_window: null });
  const envelope = data => ({ ok: true, schema_version: 1, data, warnings: [], meta: { source: 'production',
    time_basis: 'factory_local', request_ref: 'a'.repeat(32), snapshot_ref: 's'.repeat(32), as_of: '2026-10-11T08:00:00' } });
  const jobScope = { start_date: input.start_date, end_date: input.end_date, ready_check: input.ready_check,
    material_strategy: input.material_strategy, missing_resource_policy: input.missing_resource_policy,
    completed_policy: input.completed_policy, hold_window: input.hold_window, batch_count: input.batch_refs.length,
    operation_count: 0, batches: input.batch_refs.map((batch_ref, index) => ({batch_ref,batch_id:'B'+(index+1),part_no:null,part_label:null})),
    objective:'min_overdue',objective_label:'减少超期批次',selection:'explicit_batches',basis:'captured_at_run_admission',data_gaps:[] };
  const timed = { accepted_at:'2026-10-11T08:00:00.000000',started_at:'2026-10-11T08:00:00.100000',finished_at:'2026-10-11T08:00:00.189123' };
  assert.equal(w.RunPresentation.elapsed(timed),'0.089123 秒','Real saved microseconds survive the elapsed display');
  assert.equal(w.RunPresentation.elapsed({...timed,started_at:'2026-10-11T08:00:00',finished_at:'2026-10-11T08:00:01'}),'1 秒','Second-precision history does not invent fractions');
  assert.equal(w.RunPresentation.elapsed({...timed,started_at:'2026-10-11T08:00:00',finished_at:'2026-10-11T08:00:00'}),'起止记录在同一秒（记录精确到秒）','A same-second old record states its saved precision');
  assert.equal(w.RunPresentation.elapsed({...timed,started_at:'2026-10-11T08:00:00.100',finished_at:'2026-10-11T08:00:00.189123'}),'0.089 秒','Elapsed precision uses the coarser saved endpoint');
  assert.equal(w.RunPresentation.elapsed({...timed,started_at:'2026-03-08T01:30:00',finished_at:'2026-03-08T02:30:00'}),'1 小时 0 分钟 0 秒','Factory duration uses the saved fields even across browser DST');
  const preferences = (value, token = writeToken) => envelope({ input: value, write_context: { write_token: token,
    expires_at: '2026-10-11T09:00:00', capabilities: { 'scheduling.preferences.save': true }, blocked_reasons: [] } });
  const receipt = value => ({ ok: true, result: 'committed', receipt_ref: 'receipt', replayed: false, data: { input: value }, warnings: [] });
  const response = (value, status = 200) => ({ ok: true, status, headers: { get: () => 'application/json' }, json: async () => value });
  const requests = [];
  let route;
  w.location.origin = 'http://localhost';
  w.crypto = { getRandomValues: bytes => { bytes.fill(7); return bytes; } };
  w.fetch = async (url, options) => {
    const request = { path: new URL(url, w.location.href).pathname, method: options.method || 'GET',
      body: options.body ? JSON.parse(options.body) : null, signal: options.signal };
    requests.push(request); return response(await route(request), request.path.endsWith('/runs') && request.method === 'POST' ? 202 : 200);
  };
  const api = w.PreflightAPI.create();

  // An earlier read must not become the write credential; each save reads the current context.
  let reads = 0;
  route = request => request.method === 'GET' ? preferences(null, (++reads === 1 ? 'o' : 'n').repeat(32)) : receipt(request.body.input);
  await api.preferences(); await api.savePreferences(input);
  assert.deepStrictEqual(requests.map(row => row.method), ['GET', 'GET', 'POST']);
  assert.strictEqual(requests[2].body.write_token, 'n'.repeat(32));
  assert(/^preferences-[0-9a-f]{48}$/.test(requests[2].body.request_key));
  h.equal(requests[2].body.input, input);
  requests.length = 0;
  route = () => preferences(input);
  h.equal(await api.savePreferences({ ...input, batch_refs: [other, batch] }), input);
  assert.deepStrictEqual(requests.map(row => row.method), ['GET'], 'The same normalized selection must not create a write');

  // Bad reads and uncertain/inconsistent writes stop the caller; none substitutes defaults.
  const invalidRead = preferences(input); invalidRead.data.write_context.capabilities['scheduling.preferences.save'] = false;
  route = () => invalidRead;
  await assert.rejects(api.preferences(), /读取不完整/);
  await assert.rejects(api.savePreferences(input), /读取不完整/);
  const malformed = envelope({ input: { ...input, batch_refs: ['missing'] }, write_context: preferences(input).data.write_context });
  route = () => malformed;
  await assert.rejects(api.preferences(), /请核对/);
  route = request => request.method === 'GET' ? preferences(null) : { ok: true, data: { input } };
  await assert.rejects(api.savePreferences(input), error => error.committed === 'unknown' && /保存结果不完整/.test(error.message));
  route = request => request.method === 'GET' ? preferences(null) : receipt({ ...input, end_date: '2026-10-18' });
  await assert.rejects(api.savePreferences(input), /保存的排产范围与本次选择不一致/);

  function checked(value) {
    const counts = Object.fromEntries(['ready_tasks', 'auto_assign_required', 'skipped_tasks', 'blocked_tasks', 'protected_tasks',
      'eligible_tasks', 'selected_batches', 'selected_tasks', 'no_route_batches', 'unready_batches', 'missing_resource_tasks',
      'actual_fact_tasks', 'held_tasks', 'hold_window_tasks'].map(key => [key, 0]));
    counts.selected_batches = value.batch_refs.length;
    return envelope({ input_ref: inputRef, input_expires_at: '2026-10-11T09:00:00', normalized_input: value, counts, tasks: [],
      blockers: [], warnings: [], run_blocked_reasons: [{ code: 'preview_required', message: '请核对本次排产条件。' }],
      calendar_check: 'not_evaluated', config_scope: 'single_run', run_blocked: true,
      write_context: { write_token: null, capabilities: { 'scheduling.run': false } }, no_route_batches: [], unready_batches: [],
      included_batches: [], excluded_batches: value.batch_refs.map(batch_ref => ({ batch_ref, batch_id: 'B1' })),
      scope: { source: 'production', batch_refs: value.batch_refs }, effective_config: { ready_check: value.ready_check,
        material_strategy: value.material_strategy, missing_resource_policy: value.missing_resource_policy,
        completed_policy: value.completed_policy, hold_window: value.hold_window === undefined ? null : value.hold_window,
        hold_window_source: value.hold_window === undefined ? 'default' : 'explicit' },
      effective_start: value.start_date + 'T00:00:00', eligible_tasks: 0, auto_assign_required: 0, skipped_tasks: 0 });
  }
  // A persistent root-only hook fixture executes the real component's effects and event callbacks.
  function hooks() {
    let cursor = 0; const slots = [], effects = [];
    const same = (a, b) => a && b && a.length === b.length && a.every((value, i) => value === b[i]);
    const memo = (fn, deps) => { const i = cursor++; if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { deps, value: fn() }; return slots[i].value; };
    const useState = initial => { const i = cursor++; if (!slots[i]) slots[i] = { value: typeof initial === 'function' ? initial() : initial };
      return [slots[i].value, value => { slots[i].value = typeof value === 'function' ? value(slots[i].value) : value; }]; };
    const useRef = value => { const i = cursor++; if (!slots[i]) slots[i] = { current: value }; return slots[i]; };
    const useEffect = (fn, deps) => { const i = cursor++, old = slots[i]; if (!old || !same(old.deps, deps)) {
      slots[i] = { deps, cleanup: old && old.cleanup }; effects.push(() => { if (slots[i].cleanup) slots[i].cleanup(); slots[i].cleanup = fn(); }); } };
    const fixture = { useState, useRef, useMemo: memo, useCallback: (fn, deps) => memo(() => fn, deps), useEffect,
      useReducer: (fn, initial) => { const [value, set] = useState(initial); return [value, action => set(old => fn(old, action))]; } };
    return { render(component, props) { cursor = 0; Object.assign(w.React, fixture); return component(props); },
      flush() { while (effects.length) effects.shift()(); },
      unmount() { slots.forEach(slot => { if (slot.cleanup) slot.cleanup(); }); } };
  }
  const turns = async () => { for (let i = 0; i < 30; i++) await Promise.resolve(); };
  const nodes = tree => tree == null || typeof tree !== 'object' ? [] : Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props.children)];
  const text = tree => tree == null || typeof tree === 'boolean' ? '' : typeof tree !== 'object' ? String(tree) : Array.isArray(tree) ? tree.map(text).join('') : text(tree.props.children);
  w.WorkbenchPageContext.useSnapshot = () => {};
  const workspace = hooks(), noRunPanel = () => null, preflightProps = { initialContext: {}, renderRunPanel: noRunPanel };
  route = request => request.path.endsWith('/preferences') ? request.method === 'GET' ? preferences(input) : receipt(request.body.input) : checked(request.body);
  requests.length = 0;
  workspace.render(w.PreflightWorkspace, preflightProps); workspace.flush(); await turns();
  let tree = workspace.render(w.PreflightWorkspace, preflightProps);
  assert.deepStrictEqual(requests.map(row => [row.method, row.path]), [['GET', '/api/workbench/v1/scheduling/preferences'], ['POST', '/api/workbench/v1/scheduling/preflight']],
    'Opening restores saved input and only runs the read-only preflight');
  h.equal(requests[1].body, input);
  assert.strictEqual(nodes(tree).find(node => node.type === 'input' && node.props['aria-label'] === '计划开始日期').props.value, input.start_date);
  nodes(tree).find(node => node.type === 'input' && node.props['aria-label'] === '计划结束日期').props.onChange({ target: { value: '2026-10-18' } });
  tree = workspace.render(w.PreflightWorkspace, preflightProps);
  const recheck = nodes(tree).find(node => node.type === w.PreflightControls.Button && ['重新检查', '开始排产检查'].includes(text(node)));
  requests.length = 0; await recheck.props.onClick();
  assert.deepStrictEqual(requests.map(row => [row.method, row.path]), [['GET', '/api/workbench/v1/scheduling/preferences'], ['POST', '/api/workbench/v1/scheduling/preferences'], ['POST', '/api/workbench/v1/scheduling/preflight']],
    'A changed selection is saved before the next check');
  h.equal(requests[1].body.input, requests[2].body);
  assert.strictEqual(requests[2].body.end_date, '2026-10-18');
  tree = workspace.render(w.PreflightWorkspace, preflightProps);
  route = request => request.method === 'GET' ? preferences(input) : { ok: true, data: { input } };
  requests.length = 0;
  await nodes(tree).find(node => node.type === w.PreflightControls.Button && text(node) === '重新检查').props.onClick();
  assert.deepStrictEqual(requests.map(row => row.path), ['/api/workbench/v1/scheduling/preferences', '/api/workbench/v1/scheduling/preferences'],
    'A failed save must stop the next preflight');
  assert(nodes(workspace.render(w.PreflightWorkspace, preflightProps)).some(node => node.type === w.PreflightControls.ErrorBox && node.props.error),
    'The workspace must expose the save failure');
  workspace.unmount();

  // A fresh form restores saved rules, while a batch-only navigation replaces only the saved selection.
  for (const hold of [undefined, null, { start: '2026-10-11T08:00', end: '2026-10-11T12:00' }]) {
    const saved = C.input({ ...input, time_budget_seconds: 17, hold_window: hold });
    const savedBefore = h.clone(saved);
    for (const [context, refs] of [[{}, saved.batch_refs], [{ scope: { source: 'production', batch_refs: [other] } }, [other]],
      [{ entity_ref: other }, [other]], [{ scope: { source: 'production', batch_refs: [] } }, []]]) {
      const state = hooks(), props = { initialContext: context, renderRunPanel: noRunPanel }, expected = C.input({ ...saved, batch_refs: refs });
      route = request => request.path.endsWith('/preferences') ? preferences(saved) : checked(request.body);
      requests.length = 0;
      state.render(w.PreflightWorkspace, props); state.flush(); await turns();
      const restored = state.render(w.PreflightWorkspace, props), rules = nodes(restored).find(node => node.type === w.PreflightControls.Rules);
      h.equal(rules.props.value, expected);
      h.equal(saved, savedBefore);
      assert.deepStrictEqual(requests.map(row => row.path), ['/api/workbench/v1/scheduling/preferences',
        ...(refs.length ? ['/api/workbench/v1/scheduling/preflight'] : [])], 'Opening only reads preferences and checks the exact new scope');
      if (refs.length) h.equal(requests[1].body, expected);
      assert(!requests.some(row => row.path.endsWith('/preferences') && row.method === 'POST'), 'Opening never saves preferences');
      state.unmount();
    }
  }
  for (const context of [{ scope: { source: 'sample', batch_refs: [other] } }, { scope: { source: 'production', batch_refs: [other] }, unknown: true }]) {
    const state = hooks(), props = { initialContext: context, renderRunPanel: noRunPanel };
    route = () => preferences(input); requests.length = 0;
    state.render(w.PreflightWorkspace, props); state.flush(); await turns();
    assert(nodes(state.render(w.PreflightWorkspace, props)).some(node => node.type === w.PreflightControls.ErrorBox && node.props.error),
      'An invalid explicit navigation remains invalid instead of restoring a wider saved scope');
    assert.equal(requests.length, 1); state.unmount();
  }
  const explicitState = hooks(), explicitProps = { initialContext: C.input({ ...input, batch_refs: [other], start_date: '2026-10-12', hold_window: null }), renderRunPanel: noRunPanel };
  route = request => request.path.endsWith('/preferences') ? preferences(input) : checked(request.body); requests.length = 0;
  explicitState.render(w.PreflightWorkspace, explicitProps); explicitState.flush(); await turns();
  h.equal(requests[1].body, explicitProps.initialContext); explicitState.unmount();
  const emptyState = hooks(), emptyProps = { initialContext: {}, renderRunPanel: noRunPanel };
  route = () => preferences(null); requests.length = 0;
  emptyState.render(w.PreflightWorkspace, emptyProps); emptyState.flush(); await turns();
  assert.equal(requests.length, 1, 'Without saved preferences, an empty fresh form does not check all batches'); emptyState.unmount();

  const pickerState = hooks(), pickerCalls = [], selections = [], completedRef = h.reference(40);
  const completedRow = { ref: completedRef, business_code: 'DONE-001', label: '旧完工批次', status: 'completed',
    fields: { due_date: '2026-10-10', priority: 'normal', ready_status: 'yes' }, relationships: { part_no: 'P1', operation_count: 1 } };
  const pickerProps = { selected: [], onChange: refs => selections.push(refs), disabled: false, adapter: {
    async list(scope) { pickerCalls.push({ kind: 'list', scope }); return envelope({ entities: [completedRow], page: { number: 1, size: 20, total: 1, pages: 1 } }); },
    async selection(scope) { pickerCalls.push({ kind: 'selection', scope }); return envelope({ refs: [completedRef], count: 1 }); }
  } };
  pickerState.render(w.PreflightBatchPicker, pickerProps); pickerState.flush(); await turns();
  let pickerTree = pickerState.render(w.PreflightBatchPicker, pickerProps);
  assert(text(pickerTree).includes(w.APSBatchContract.label('status', 'completed')), 'Completed rows expose their actual status');
  nodes(pickerTree).find(node => node.type === 'input' && node.props.type === 'checkbox').props.onChange();
  h.equal(selections.at(-1), [completedRef]);
  for (const label of ['全部待排', '仅齐套', '全选当前筛选']) {
    await nodes(pickerTree).find(node => node.type === w.PreflightControls.Button && text(node) === label).props.onClick();
    pickerTree = pickerState.render(w.PreflightBatchPicker, pickerProps);
    h.equal(selections.at(-1), [completedRef]);
  }
  assert(pickerCalls.every(call => JSON.stringify(call.scope.column_filters.status) === JSON.stringify(['pending', 'scheduled', 'processing', 'completed'])),
    'Visible and shortcut selections retain completed batches for official-scope coverage');
  pickerState.unmount();

  // The automatic run preview may open confirmation, but accept only belongs to the final callback.
  const store = new Map(); w.localStorage = { getItem: key => store.has(key) ? store.get(key) : null,
    setItem: (key, value) => store.set(key, value), removeItem: key => store.delete(key) };
  w.navigator = { locks: { request: async (_key, _options, fn) => fn({}) } };
  w.document.hidden = false;
  const runRef = h.reference(3), dataContext = JSON.stringify({database_scope:'/tmp/aps-context.db',successful_restores:[]}), admitted = { run_ref: runRef, job_ref: runRef, state: 'queued', stage: 'queued', progress: null,
    plans: [], plan_catalog_connected: false, candidates: [], result_persisted: false, accepted_at: '2026-10-11T08:00:00',
    started_at: null, finished_at: null, receipt_ref: null, error: null, recovery_required: false, scope_summary: jobScope };
  route = request => request.path.endsWith('/runs/preview') ? envelope({ input_ref: inputRef, normalized_input: input, data_context_ref: dataContext,
    calendar_check: 'not_evaluated', warnings: [], write_context: { write_token: writeToken, expires_at: '2026-10-11T09:00:00', capabilities: { 'scheduling.run': true }, blocked_reasons: [] } }) :
    { ok: true, result: 'accepted', job_ref: runRef, run_ref: runRef, status_target: '/api/workbench/v1/scheduling/runs/' + runRef,
      receipt_ref: 'a'.repeat(32), replayed: false, data: admitted, data_context_ref: dataContext };
  assert(w.RunJobAPI.validIntent({schema_version:2,input_ref:inputRef,request_key:'run-'+ 'b'.repeat(48),run_ref:null,data_context_ref:'d'.repeat(64)}), 'Legacy stored generation IDs remain readable');
  assert(!w.RunJobAPI.validIntent({schema_version:2,input_ref:inputRef,request_key:'run-'+ 'b'.repeat(48),run_ref:null,data_context_ref:JSON.stringify({database_scope:'/tmp/aps-context.db',successful_restores:[true]})}), 'Restore identities keep their actual type');
  const panel = hooks(), props = { preflight: checked(input).data, onNavigate() {} };
  requests.length = 0;
  panel.render(w.RunJobPanel, props); panel.flush(); await turns();
  tree = panel.render(w.RunJobPanel, props);
  const confirmation = nodes(tree).find(node => node.type === w.RunJobControls.Confirmation);
  assert(confirmation, 'A valid preflight automatically opens the existing confirmation');
  assert.deepStrictEqual(requests.map(row => row.path), ['/api/workbench/v1/scheduling/runs/preview']);
  assert.strictEqual(store.size, 0, 'Preview must not create a durable run intent');
  assert.equal(confirmation.props.batches.length, input.batch_refs.length);
  assert(confirmation.props.batches.every(row=>row.batch_id==='B1'),'Confirmation receives this preflight business batch names');
  await confirmation.props.onConfirm();
  assert.deepStrictEqual(requests.map(row => row.path), ['/api/workbench/v1/scheduling/runs/preview', '/api/workbench/v1/scheduling/runs']);
  assert.strictEqual(requests[1].body.input_ref, inputRef); assert.strictEqual(requests[1].body.write_token, writeToken);
  assert(/^run-[0-9a-f]{48}$/.test(requests[1].body.request_key));
  const acceptedRecord = nodes(panel.render(w.RunJobPanel, props)).find(node => node.type === w.RunJobControls.Record).props;
  assert.strictEqual(acceptedRecord.run.run_ref, runRef); assert.strictEqual(acceptedRecord.intent.run_ref, runRef);
  assert.strictEqual(acceptedRecord.verified, true, 'The 202 receipt must be confirmed and attached to its saved intent');
  panel.unmount();

  // A busy cross-tab lock keeps this confirmation for a retry in the same dialog.
  store.clear(); requests.length = 0; w.navigator = { locks: { request: async (_key, _options, fn) => fn(null) } };
  const contended = hooks();
  contended.render(w.RunJobPanel, props); contended.flush(); await turns();
  await nodes(contended.render(w.RunJobPanel, props)).find(node => node.type === w.RunJobControls.Confirmation).props.onConfirm();
  const kept = nodes(contended.render(w.RunJobPanel, props)).find(node => node.type === w.RunJobControls.Confirmation);
  assert(kept && kept.props.preview && !kept.props.busy, 'Lock contention keeps the confirmation and its preview');
  assert(/另一个页面正在提交排产/.test(kept.props.error));
  assert.deepStrictEqual(requests.map(row => row.path), ['/api/workbench/v1/scheduling/runs/preview']); assert.strictEqual(store.size, 0);
  w.navigator = { locks: { request: async (_key, _options, fn) => fn({}) } };
  await kept.props.onConfirm();
  assert.deepStrictEqual(requests.map(row => row.path), ['/api/workbench/v1/scheduling/runs/preview', '/api/workbench/v1/scheduling/runs'],
    'After the lock is released the same confirmation submits without another preview');
  contended.unmount();

  // A 202 admission is published even when the local run reference cannot be saved; the failure stays a storage error.
  store.clear(); requests.length = 0;
  w.localStorage = { getItem: key => store.has(key) ? store.get(key) : null, removeItem: key => store.delete(key),
    setItem: (key, value) => { if (key === w.RunJobAPI.PENDING_KEY && store.has(key)) throw new Error('QuotaExceededError'); store.set(key, value); } };
  const unattached = hooks();
  unattached.render(w.RunJobPanel, props); unattached.flush(); await turns();
  await nodes(unattached.render(w.RunJobPanel, props)).find(node => node.type === w.RunJobControls.Confirmation).props.onConfirm();
  const unattachedTree = unattached.render(w.RunJobPanel, props), unattachedRecord = nodes(unattachedTree).find(node => node.type === w.RunJobControls.Record).props;
  assert.deepStrictEqual(requests.map(row => row.path), ['/api/workbench/v1/scheduling/runs/preview', '/api/workbench/v1/scheduling/runs']);
  assert.strictEqual(unattachedRecord.run.run_ref, runRef); assert.strictEqual(unattachedRecord.verified, true, 'The accepted run is shown before the local attach');
  assert.strictEqual(unattachedRecord.intent.run_ref, null); assert.strictEqual(JSON.parse(store.get(w.RunJobAPI.PENDING_KEY)).run_ref, null);
  const unattachedAlerts = nodes(unattachedTree).filter(node => node.props && node.props.role === 'alert').map(text);
  assert(unattachedAlerts.some(value => value.startsWith('排产已接收，但本机没能保存这次排产的编号。请不要重新提交，到排产记录页查看结果。')), 'The attach failure is reported as an accepted run with a storage problem');
  assert(!unattachedAlerts.some(value => value.includes(w.WorkbenchTerms.outcomes.pending('排产'))), 'The attach failure is not shown as an unconfirmed submission');
  assert(!nodes(unattachedTree).some(node => node.type === w.RunJobControls.Confirmation), 'An admitted run closes its confirmation');
  unattached.unmount();
  w.localStorage = { getItem: key => store.has(key) ? store.get(key) : null, setItem: (key, value) => store.set(key, value), removeItem: key => store.delete(key) };

  const options = seconds => ({ generation_policy_version: 'unified_search_v1', primary_objective: 'min_overdue',
    target_objectives: ['min_overdue', 'min_tardiness', 'min_changeover'], time_budget_seconds: seconds, algo_mode: 'improve', graph_analysis_mode: 'off' });
  let checkNumber = 0;
  function budgetChecked(value, seconds = value.time_budget_seconds === undefined ? 17 : value.time_budget_seconds) {
    const result = checked(C.input({ ...value, time_budget_seconds: seconds }));
    result.data.input_ref = String(++checkNumber).padStart(32, '0'); result.data.run_options = options(seconds);
    return result;
  }
  const previewFor = result => envelope({ input_ref: result.data.input_ref, normalized_input: result.data.normalized_input,
    run_options: result.data.run_options, data_context_ref: dataContext, calendar_check: 'not_evaluated', warnings: [],
    write_context: { write_token: result.data.input_ref.replace(/^0/, 'p'), expires_at: '2026-10-11T09:00:00', capabilities: { 'scheduling.run': true }, blocked_reasons: [] } });
  const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };
  const modern = budgetChecked(input);
  C.result(modern, input);
  h.equal(C.input({ ...input, time_budget_seconds: 1000000 }).time_budget_seconds, 1000000);
  for (const invalid of [true, 0, -1, 1.5, '10']) assert.throws(() => C.input({ ...input, time_budget_seconds: invalid }), /请核对/);
  const mismatch = h.clone(modern); mismatch.data.run_options.time_budget_seconds = 30;
  assert.throws(() => C.result(mismatch, input), /排产检查结果/);
  const configBlocked = h.clone(modern); configBlocked.data.run_options = null;
  configBlocked.data.blockers = [{ code: 'config_error', message: '配置读取失败。' }];
  C.result(configBlocked, modern.data.normalized_input);
  const blockedPreview = previewFor(configBlocked);
  blockedPreview.data.write_context = { write_token: null, expires_at: null, capabilities: { 'scheduling.run': false }, blocked_reasons: configBlocked.data.blockers };
  w.RunJobAPI.preview(blockedPreview, configBlocked.data.input_ref);
  assert.throws(() => C.result({ ...configBlocked, data: { ...configBlocked.data, blockers: [] } }, modern.data.normalized_input), /排产检查结果/);
  assert.throws(() => w.RunJobAPI.preview(previewFor(configBlocked), configBlocked.data.input_ref), /排产数据/, '成功preview必须有实际run_options');
  const usedIntent = { input_ref: modern.data.input_ref, request_key: 'run-' + 'a'.repeat(48), run_ref: null };
  const used = w.RunJobAPI.create(async () => ({ ok: false, status: 409, headers: { get: () => 'application/json' }, json: async () => ({
    ok: false, committed: false, error: { code: 'input_already_used', message: '这份排产检查已受理过。', fields: [], retryable: false, request_ref: 'a'.repeat(32) }
  }) }));
  await assert.rejects(() => used.accept(usedIntent, writeToken), error => error.code === 'input_already_used' && w.RunJobAPI.isRejected(error), '已消费检查的新请求是确定拒绝，沿已有Panel清理pending路径');
  assert.equal(w.RunPresentation.stage({ ...admitted, stage: 'computing', scope_summary: { ...jobScope, run_options: options(17) } }), '正在共同优化方案');
  assert.equal(w.RunPresentation.stage({ ...admitted, stage: 'computing' }), '正在计算', 'Old saved progress keeps its original presentation');

  // The actual SchedulingWorkspace callback connects the persistent parent and panel hook frames.
  async function confirmationFlow({ preflightWait, previewWait } = {}) {
    store.clear(); requests.length = 0;
    const checks = new Map(), rootFrame = hooks(), parentFrame = hooks(), childFrame = hooks();
    let parentTree, childTree;
    route = request => {
      if (request.path.endsWith('/preferences')) return preferences(input);
      if (request.path.endsWith('/preflight')) {
        const result = budgetChecked(request.body); checks.set(result.data.input_ref, result);
        if (preflightWait && request.body.time_budget_seconds === preflightWait.seconds) { preflightWait.result = result; return preflightWait.promise; }
        return result;
      }
      if (request.path.endsWith('/runs/preview')) {
        const result = checks.get(request.body.input_ref), value = previewFor(result);
        if (previewWait && result.data.run_options.time_budget_seconds === previewWait.seconds) { previewWait.result = value; return previewWait.promise; }
        return value;
      }
      assert.equal(request.path, '/api/workbench/v1/scheduling/runs');
      const result = checks.get(request.body.input_ref), run = { ...admitted, scope_summary: { ...jobScope, run_options: result.data.run_options } };
      return { ok: true, result: 'accepted', job_ref: runRef, run_ref: runRef, status_target: '/api/workbench/v1/scheduling/runs/' + runRef,
        receipt_ref: 'a'.repeat(32), replayed: false, data: run, data_context_ref: dataContext };
    };
    const pageContext = {};
    function render() {
      const rootTree = rootFrame.render(w.RunWorkspace, { onNavigate() {}, initialContext: pageContext }); rootFrame.flush();
      const parent = nodes(rootTree).find(node => node.type === w.PreflightWorkspace);
      parentTree = parentFrame.render(w.PreflightWorkspace, parent.props); parentFrame.flush();
      const child = nodes(parentTree).find(node => node.type === w.RunJobPanel);
      childTree = childFrame.render(w.RunJobPanel, child.props); childFrame.flush();
    }
    async function settle() { for (let i = 0; i < 3; i++) { render(); await turns(); } render(); }
    await settle();
    return { settle, render, confirmation: () => nodes(childTree).find(node => node.type === w.RunJobControls.Confirmation),
      parent: () => parentTree, child: () => childTree, stop() { childFrame.unmount(); parentFrame.unmount(); rootFrame.unmount(); } };
  }
  const firstBudget = { seconds: 30, ...deferred() }, flow = await confirmationFlow({ preflightWait: firstBudget });
  let dialog = flow.confirmation();
  assert(dialog); assert.equal(dialog.props.timeBudget, 17, 'The saved effective budget supplies the custom initial value');
  assert.deepEqual(requests.map(row => row.path), ['/api/workbench/v1/scheduling/preferences', '/api/workbench/v1/scheduling/preflight', '/api/workbench/v1/scheduling/runs/preview']);
  const staleConfirm = dialog.props.onConfirm;
  const obsoleteBudget = dialog.props.onBudgetChange(30); await flow.settle();
  dialog = flow.confirmation();
  assert(dialog && dialog.props.preview === null && dialog.props.busy, 'The parent clearing data preserves the same modal and retires its old preview');
  await staleConfirm(); assert(!requests.some(row => row.path.endsWith('/runs')), 'A saved old confirm callback cannot submit its retired credential');
  const budgetRead = requests.at(-1); assert.equal(budgetRead.body.time_budget_seconds, 30);
  await dialog.props.onBudgetChange(10); await flow.settle();
  dialog = flow.confirmation();
  assert(dialog && dialog.props.preview); assert.equal(dialog.props.preview.run_options.time_budget_seconds, 10);
  assert(budgetRead.signal.aborted, 'The newer budget cancels the parent request belonging to the old choice');
  const newest = dialog.props.preview;
  firstBudget.resolve(firstBudget.result); await obsoleteBudget; await flow.settle();
  assert.equal(flow.confirmation().props.preview.input_ref, newest.input_ref, 'A late preflight cannot replace the current confirmation');
  assert.equal(requests.filter(row => row.path.endsWith('/runs/preview')).length, 2, 'Only the initial and latest valid check obtain a preview');
  assert.equal(requests.filter(row => row.path.endsWith('/preferences')).length, 1, 'Budget changes neither save nor reread preferences');
  assert.equal(store.size, 0, 'Budget checks and previews create no durable pending intent');
  h.equal(requests.filter(row => row.path.endsWith('/preflight')).at(-1).body, { ...input, time_budget_seconds: 10 });
  await flow.confirmation().props.onConfirm();
  const latestAccept = requests.at(-1);
  assert.equal(latestAccept.path, '/api/workbench/v1/scheduling/runs');
  assert.equal(latestAccept.body.input_ref, newest.input_ref); assert.equal(latestAccept.body.write_token, newest.write_context.write_token);
  assert(/^run-[0-9a-f]{48}$/.test(latestAccept.body.request_key)); assert(store.has(w.RunJobAPI.PENDING_KEY)); flow.stop();

  const closingBudget = { seconds: 30, ...deferred() }, closing = await confirmationFlow({ preflightWait: closingBudget });
  const closedRead = closing.confirmation().props.onBudgetChange(30); await closing.settle();
  closing.confirmation().props.onClose(); await closing.settle();
  assert(!closing.confirmation()); assert(requests.at(-1).signal.aborted);
  assert(!text(closing.parent()).includes('正在读取批次'), 'Closing immediately releases the parent reading state');
  closingBudget.resolve(closingBudget.result); await closedRead; await closing.settle();
  assert(!closing.confirmation()); assert.equal(requests.filter(row => row.path.endsWith('/runs/preview')).length, 1);
  assert.equal(store.size, 0); closing.stop();

  const latePreview = { seconds: 30, ...deferred() }, closedPreview = await confirmationFlow({ previewWait: latePreview });
  const previewRead = closedPreview.confirmation().props.onBudgetChange(30); await closedPreview.settle();
  assert(closedPreview.confirmation().props.preview === null);
  closedPreview.confirmation().props.onClose(); await closedPreview.settle();
  latePreview.resolve(latePreview.result); await previewRead; await closedPreview.settle();
  assert(!closedPreview.confirmation(), 'A finished parent check and late preview cannot reopen the closed session');
  assert.equal(store.size, 0); closedPreview.stop();

  const unmountBudget = { seconds: 30, ...deferred() }, unmounted = await confirmationFlow({ preflightWait: unmountBudget });
  const unmountedRead = unmounted.confirmation().props.onBudgetChange(30); await unmounted.settle(); unmounted.stop();
  unmountBudget.resolve(unmountBudget.result); await unmountedRead; await turns();
  assert.equal(requests.filter(row => row.path.endsWith('/runs/preview')).length, 1, 'Unmount prevents continuation from starting a preview');
  assert.equal(store.size, 0);

  // Custom input commits only on blur/Enter, and the real modal permits closing during reads.
  const controlFrame = hooks(), controlProps = { preflight: modern.data, preview: previewFor(modern).data, timeBudget: 17,
    effective: modern.data.effective_config, busy: true, onBudgetChange() {}, onConfirm() {}, onClose() {} };
  let controlTree = controlFrame.render(w.RunJobControls.Confirmation, controlProps); controlFrame.flush();
  assert.equal(controlTree.props.locked, false);
  const footer = nodes(controlTree.props.footer);
  assert.equal(footer.find(node => text(node) === '取消').props.disabled, false);
  const budgetNode = nodes(controlTree).find(node => typeof node.type === 'function' && node.type.name === 'Budget');
  const budgetFrame = hooks(), customCalls = [], budgetProps = { ...budgetNode.props, onChange: value => customCalls.push(value) };
  let budgetTree = budgetFrame.render(budgetNode.type, budgetProps); budgetFrame.flush();
  assert.equal(nodes(budgetTree).find(node => node.type === 'select').props.value, 'custom');
  for (const value of ['2', '27']) {
    nodes(budgetTree).find(node => node.type === 'input').props.onChange({ target: { value } });
    budgetTree = budgetFrame.render(budgetNode.type, budgetProps); budgetFrame.flush();
  }
  assert.deepEqual(customCalls, []);
  nodes(budgetTree).find(node => node.type === 'input').props.onBlur(); assert.deepEqual(customCalls, [27]);
  nodes(budgetTree).find(node => node.type === 'input').props.onChange({ target: { value: '0' } });
  budgetTree = budgetFrame.render(budgetNode.type, budgetProps);
  nodes(budgetTree).find(node => node.type === 'input').props.onBlur(); assert.deepEqual(customCalls, [27]);
  budgetTree = budgetFrame.render(budgetNode.type, budgetProps); assert(text(budgetTree).includes('至少 1 秒的整数'));
  nodes(budgetTree).find(node => node.type === 'input').props.onChange({ target: { value: '1000000' } });
  budgetTree = budgetFrame.render(budgetNode.type, budgetProps);
  nodes(budgetTree).find(node => node.type === 'input').props.onKeyDown({ key: 'Enter', preventDefault() {} });
  assert.deepEqual(customCalls, [27, 1000000]); budgetFrame.unmount(); controlFrame.unmount();

  // Drive the actual polling effect with a virtual clock: no 32-second wall-clock sleep.
  const NativeDate = w.Date;
  async function polling({ found = true, failed = false, knownRef = true, recovery = false, finishedAt = Infinity, replaced = false, failRecent = false } = {}) {
    let now = 0, nextTimer = 0; const timers = new Map(), listeners = new Map(), lookups = [], posts = [], storage = new Map();
    const epoch = NativeDate.parse('2026-10-11T08:00:00'), intent = { schema_version: 2, input_ref: inputRef,
      request_key: 'run-' + 'b'.repeat(48), run_ref: knownRef ? runRef : null, data_context_ref: dataContext };
    storage.set(w.RunJobAPI.PENDING_KEY, JSON.stringify(intent));
    w.Date = class extends NativeDate { constructor(...args) { super(...(args.length ? args : [epoch + now])); } static now() { return epoch + now; } };
    w.setTimeout = (fn, delay) => { const id = ++nextTimer; timers.set(id, { fn, at: now + delay }); return id; };
    w.clearTimeout = id => timers.delete(id);
    w.document.hidden = false;
    w.document.addEventListener = (name, fn) => listeners.set(name, fn);
    w.document.removeEventListener = (name, fn) => { if (listeners.get(name) === fn) listeners.delete(name); };
    w.localStorage = { getItem: key => storage.has(key) ? storage.get(key) : null, removeItem: key => storage.delete(key),
      setItem: (key, value) => { if (failRecent && key === w.RunJobAPI.RECENT_KEY) throw new Error('QuotaExceededError'); storage.set(key, value); } };
    route = request => {
      if (request.method === 'POST') posts.push(request);
      assert.strictEqual(request.path, '/api/workbench/v1/scheduling/requests/' + intent.request_key);
      lookups.push(now);
      if (failed) throw new TypeError('offline');
      const done = now >= finishedAt, running = { ...admitted, state: 'running', stage: recovery ? 'awaiting_reconciliation' : 'computing',
        recovery_required: recovery, started_at: '2026-10-11T08:00:00' };
      const complete = { ...running, state: 'complete', stage: 'finished', result_persisted: true,
        finished_at: '2026-10-11T08:00:32', receipt_ref: h.reference(4),
        candidates: [{ candidate_ref: h.reference(5), label: '方案一', status: 'completed', task_count: 1, selected: true }] };
      return envelope({ found, run: found ? done ? complete : running : null, data_context_ref: dataContext, resolution: found ? 'found' : replaced ? 'context_replaced' : 'unresolved' });
    };
    const state = hooks(), props = { preflight: null, onNavigate() {} };
    let view;
    const render = () => { view = state.render(w.RunJobPanel, props); state.flush(); };
    render(); await turns(); render();
    return { lookups, posts, storage, view: () => view,
      record: () => nodes(view).find(node => node.type === w.RunJobControls.Record).props,
      async advance(target) {
        while (true) {
          const next = [...timers].filter(([, value]) => value.at <= target).sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0];
          if (!next) break;
          now = next[1].at; timers.delete(next[0]); await next[1].fn(); await turns(); render();
        }
        now = target; await turns(); render();
      },
      async visible(value) { w.document.hidden = !value; listeners.get('visibilitychange')(); await turns(); render(); },
      stop() { state.unmount(); assert.strictEqual(timers.size, 0, 'Unmount must cancel the remaining poll'); }
    };
  }
  const live = await polling({ finishedAt: 32000 });
  await live.advance(65000);
  const detectedAt = live.lookups.at(-1);
  console.log(JSON.stringify({ backend_finished_ms: 32000, ui_found_ms: detectedAt, lookup_ms: live.lookups }));
  assert(detectedAt >= 32000 && detectedAt <= 34000, 'A known active run must be checked every 2 seconds and discover 32s completion by 34s; observed ' + detectedAt + 'ms');
  assert(live.lookups.slice(1).every((value, index) => value - live.lookups[index] === 2000));
  assert.strictEqual(live.record().run.state, 'complete'); assert.strictEqual(live.posts.length, 0);
  const terminalLookups = live.lookups.length; await live.advance(120000);
  assert.strictEqual(live.lookups.length, terminalLookups, 'A terminal run must stop polling'); live.stop();
  for (const options of [{ found: false, knownRef: false }, { found: false }, { failed: true }]) {
    const unsettled = await polling(options); await unsettled.advance(120000);
    assert.deepStrictEqual(unsettled.lookups, [0, 2000, 6000, 14000, 30000, 60000], 'Unknown receipts, not-found runs and failures retain the existing backoff');
    assert.strictEqual(unsettled.record().retryPaused, true, 'An unresolved result pauses after 60 seconds');
    assert.strictEqual(unsettled.posts.length, 0); unsettled.stop();
  }
  const hidden = await polling({ finishedAt: 22000 }); await hidden.advance(3000); await hidden.visible(false);
  assert.strictEqual(hidden.record().paused, true); await hidden.advance(20000);
  assert.deepStrictEqual(hidden.lookups, [0, 2000], 'A hidden page must suspend its polling');
  await hidden.visible(true);
  assert.deepStrictEqual(hidden.lookups, [0, 2000, 20000], 'Returning to the page immediately checks the existing run');
  await hidden.advance(60000);
  assert.deepStrictEqual(hidden.lookups, [0, 2000, 20000, 22000], 'Resumed polling returns to 2 seconds and stops at terminal');
  assert.strictEqual(hidden.posts.length, 0); hidden.stop();
  const recovery = await polling({ recovery: true }); await recovery.advance(120000);
  console.log(JSON.stringify({ recovery_lookup_ms: recovery.lookups, retry_paused: recovery.record().retryPaused, posts: recovery.posts.length }));
  assert.deepStrictEqual(recovery.lookups, [0, 2000, 6000, 14000, 30000, 60000, 90000, 120000], 'A found run awaiting reconciliation retains capped backoff');
  assert.strictEqual(recovery.record().retryPaused, false, 'A found recovery record must not be treated as an unresolved receipt');
  assert.strictEqual(recovery.record().run.recovery_required, true); assert.strictEqual(recovery.posts.length, 0); recovery.stop();
  // A verified terminal answer survives a failed local finish; the failure is a storage error, not a lookup failure.
  for (const replaced of [false, true]) {
    const unfinished = await polling({ finishedAt: 0, found: !replaced, replaced, failRecent: true }); await unfinished.advance(120000);
    const record = unfinished.record();
    assert.deepStrictEqual(unfinished.lookups, [0], 'A local finish failure stops polling instead of retrying the lookup');
    assert.strictEqual(record.resolution, replaced ? 'context_replaced' : 'found'); assert.strictEqual(record.verified, !replaced);
    assert.strictEqual(replaced ? record.run : record.run.state, replaced ? null : 'complete');
    assert(nodes(unfinished.view()).some(node => node.props && node.props.role === 'alert' && text(node).startsWith('QuotaExceededError')), 'The finish failure is shown as a storage error');
    assert(unfinished.storage.has(w.RunJobAPI.PENDING_KEY)); assert.strictEqual(unfinished.posts.length, 0); unfinished.stop();
  }
  return { preferences: 'read/write contracts', workspace: 'restore and save-before-check', run: 'preview-before-confirmed-accept',
    budget: 'effective initial value, preflight→preview, latest owner, close/unmount isolation, completed custom input and unchanged durable protocol',
    poll: { backend_finished_ms: 32000, ui_found_ms: detectedAt, unresolved: '2/4/8/16/30 seconds then paused', visibility: 'suspend/resume' }, runtime: h.mode || 'delivered-bundle' };
}
const root = path.join(__dirname, '../..');
if (process.argv.includes('--source')) {
  const document = { body: { style: {} }, documentElement: { setAttribute() {} }, addEventListener() {}, removeEventListener() {},
    getElementById: id => id === 'workbench-boot' ? { textContent: '{}' } : { setAttribute() {}, replaceChildren() {} }, createElement: () => ({ setAttribute() {} }) };
  const runtime = vm.createContext({ console, document, URL, URLSearchParams, Map, Set, Date, setTimeout, clearTimeout, setInterval, clearInterval, AbortController, FormData, innerWidth: 1280, innerHeight: 800 });
  Object.assign(runtime, { window: runtime, self: runtime, addEventListener() {}, removeEventListener() {}, dispatchEvent() {}, location: { href: 'http://localhost/workbench' },
    CustomEvent: class { constructor(type, value) { this.type = type; this.detail = value.detail; } } });
  for (const file of ['static/workbench/vendor/react-18.3.1.production.min.js', 'static/workbench/app/main.js']) vm.runInContext(fs.readFileSync(path.join(root, file), 'utf8'), runtime, { filename: file });
  const files = ['RunGenerationContract.js', 'RunPresentation.js', 'PreflightContract.js', 'PreflightAPI.js', 'PreflightBatchPicker.jsx', 'PreflightWorkspace.jsx', 'RunJobAPI.js', 'RunJobControls.jsx', 'RunJobPanel.jsx', 'SchedulingWorkspace.jsx'];
  for (const output of compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
    sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') })) }).outputs) vm.runInContext(output.code, runtime, { filename: output.path });
  const h = { runtime, mode: 'current-source', reference: number => number.toString(16).padStart(48, '0'), clone: value => JSON.parse(JSON.stringify(value)),
    equal: (left, right) => assert.equal(JSON.stringify(left), JSON.stringify(right)) };
  contract(h, assert).then(result => console.log(JSON.stringify({ mode: 'current-source', result })), error => { console.error(error.stack); process.exitCode = 1; });
} else {
  const result = spawnSync(process.execPath, [path.join(root, 'tests/_support/gantt_current_runtime.cjs')], {
    cwd: root, encoding: 'utf8', timeout: 30000, input: JSON.stringify({ root, program: `return (${contract.toString()})(h, assert);` })
  });
  assert.strictEqual(result.status, 0, result.stdout + result.stderr);
  console.log(result.stdout);
}
