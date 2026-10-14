'use strict';
const assert = require('node:assert/strict'), path = require('node:path'), { spawnSync } = require('node:child_process');

// Run the delivered bundle, with HTTP and storage fixtures instead of a browser/server.
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
      body: options.body ? JSON.parse(options.body) : null };
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
        completed_policy: value.completed_policy, hold_window: null, hold_window_source: 'explicit' },
      effective_start: value.start_date + 'T00:00:00', eligible_tasks: 0, auto_assign_required: 0, skipped_tasks: 0 });
  }
  // A persistent root-only hook fixture executes the real component's effects and event callbacks.
  function hooks() {
    let cursor = 0; const slots = [], effects = [];
    const same = (a, b) => a && b && a.length === b.length && a.every((value, i) => value === b[i]);
    const memo = (fn, deps) => { const i = cursor++; if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { deps, value: fn() }; return slots[i].value; };
    w.React.useState = initial => { const i = cursor++; if (!slots[i]) slots[i] = { value: typeof initial === 'function' ? initial() : initial };
      return [slots[i].value, value => { slots[i].value = typeof value === 'function' ? value(slots[i].value) : value; }]; };
    w.React.useRef = value => { const i = cursor++; if (!slots[i]) slots[i] = { current: value }; return slots[i]; };
    w.React.useMemo = memo; w.React.useCallback = (fn, deps) => memo(() => fn, deps);
    w.React.useReducer = (fn, initial) => { const [value, set] = w.React.useState(initial); return [value, action => set(old => fn(old, action))]; };
    w.React.useEffect = (fn, deps) => { const i = cursor++, old = slots[i]; if (!old || !same(old.deps, deps)) {
      slots[i] = { deps, cleanup: old && old.cleanup }; effects.push(() => { if (slots[i].cleanup) slots[i].cleanup(); slots[i].cleanup = fn(); }); } };
    return { render(component, props) { cursor = 0; return component(props); },
      flush() { while (effects.length) effects.shift()(); },
      unmount() { slots.forEach(slot => { if (slot.cleanup) slot.cleanup(); }); } };
  }
  const turns = async () => { for (let i = 0; i < 30; i++) await Promise.resolve(); };
  const nodes = tree => tree == null || typeof tree !== 'object' ? [] : Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props.children)];
  const text = tree => tree == null || typeof tree === 'boolean' ? '' : typeof tree !== 'object' ? String(tree) : Array.isArray(tree) ? tree.map(text).join('') : text(tree.props.children);
  w.WorkbenchPageContext.useSnapshot = () => {};
  const workspace = hooks();
  route = request => request.path.endsWith('/preferences') ? request.method === 'GET' ? preferences(input) : receipt(request.body.input) : checked(request.body);
  requests.length = 0;
  workspace.render(w.PreflightWorkspace, {}); workspace.flush(); await turns();
  let tree = workspace.render(w.PreflightWorkspace, {});
  assert.deepStrictEqual(requests.map(row => [row.method, row.path]), [['GET', '/api/workbench/v1/scheduling/preferences'], ['POST', '/api/workbench/v1/scheduling/preflight']],
    'Opening restores saved input and only runs the read-only preflight');
  h.equal(requests[1].body, input);
  assert.strictEqual(nodes(tree).find(node => node.type === 'input' && node.props['aria-label'] === '计划开始日期').props.value, input.start_date);
  nodes(tree).find(node => node.type === 'input' && node.props['aria-label'] === '计划结束日期').props.onChange({ target: { value: '2026-10-18' } });
  tree = workspace.render(w.PreflightWorkspace, {});
  const recheck = nodes(tree).find(node => node.type === w.PreflightControls.Button && ['重新检查', '开始排产检查'].includes(text(node)));
  requests.length = 0; await recheck.props.onClick();
  assert.deepStrictEqual(requests.map(row => [row.method, row.path]), [['GET', '/api/workbench/v1/scheduling/preferences'], ['POST', '/api/workbench/v1/scheduling/preferences'], ['POST', '/api/workbench/v1/scheduling/preflight']],
    'A changed selection is saved before the next check');
  h.equal(requests[1].body.input, requests[2].body);
  assert.strictEqual(requests[2].body.end_date, '2026-10-18');
  tree = workspace.render(w.PreflightWorkspace, {});
  route = request => request.method === 'GET' ? preferences(input) : { ok: true, data: { input } };
  requests.length = 0;
  await nodes(tree).find(node => node.type === w.PreflightControls.Button && text(node) === '重新检查').props.onClick();
  assert.deepStrictEqual(requests.map(row => row.path), ['/api/workbench/v1/scheduling/preferences', '/api/workbench/v1/scheduling/preferences'],
    'A failed save must stop the next preflight');
  assert(nodes(workspace.render(w.PreflightWorkspace, {})).some(node => node.type === w.PreflightControls.ErrorBox && node.props.error),
    'The workspace must expose the save failure');
  workspace.unmount();

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
  const panel = hooks(), props = { preflight: checked(input).data };
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

  // Drive the actual polling effect with a virtual clock: no 32-second wall-clock sleep.
  const NativeDate = w.Date;
  async function polling({ found = true, failed = false, knownRef = true, recovery = false, finishedAt = Infinity } = {}) {
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
    w.localStorage = { getItem: key => storage.has(key) ? storage.get(key) : null,
      setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) };
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
      return envelope({ found, run: found ? done ? complete : running : null, data_context_ref: dataContext, resolution: found ? 'found' : 'unresolved' });
    };
    const state = hooks(), props = { preflight: null };
    let view;
    const render = () => { view = state.render(w.RunJobPanel, props); state.flush(); };
    render(); await turns(); render();
    return { lookups, posts,
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
  return { preferences: 'read/write contracts', workspace: 'restore and save-before-check', run: 'preview-before-confirmed-accept',
    poll: { backend_finished_ms: 32000, ui_found_ms: detectedAt, unresolved: '2/4/8/16/30 seconds then paused', visibility: 'suspend/resume' }, bundle: 'static/workbench/app/main.js' };
}
const root = path.join(__dirname, '../..');
const result = spawnSync(process.execPath, [path.join(root, 'tests/_support/gantt_current_runtime.cjs')], {
  cwd: root, encoding: 'utf8', timeout: 30000, input: JSON.stringify({ root, program: `return (${contract.toString()})(h, assert);` })
});
assert.strictEqual(result.status, 0, result.stdout + result.stderr);
console.log(result.stdout);
