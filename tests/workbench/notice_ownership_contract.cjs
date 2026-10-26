'use strict';
const assert = require('node:assert/strict'), path = require('node:path'), { spawnSync } = require('node:child_process');

// Exercise the shipped components, including their real Button/ErrorBox children.
async function contract(h, assert) {
  const w = h.runtime, idle = { phase: 'idle', locked: false, error: null, result: null };
  w.React.useReducer = (reducer, value, init) => [init ? init(value) : value, () => {}];
  w.ReactDOM = { createPortal: element => element };
  w.localStorage = { getItem: () => null };
  w.fetch = () => { throw new Error('Unexpected network request'); };
  function visible(node) {
    if (node == null || typeof node === 'boolean') return '';
    if (Array.isArray(node)) return node.map(visible).join('');
    if (typeof node !== 'object') return String(node);
    const p = node.props;
    if (p.hidden || /\bwb-visually-hidden\b/.test(p.className || '') || p.style && (p.style.display === 'none' || p.style.visibility === 'hidden')) return '';
    if (node.type === 'details' && !p.open) return visible([node.children].flat(Infinity).find(n => n && n.type === 'summary'));
    return visible(node.children);
  }
  let checked = 0;
  function once(tree, message, blockedButtons = 0) {
    assert.strictEqual(visible(tree).split(message).length - 1, 1, visible(tree));
    if (blockedButtons) {
      const buttons = h.walk(tree).filter(n => n.type === 'button' && n.props['data-wb-disabled-reason'] === message);
      assert.strictEqual(buttons.length, blockedButtons);
      for (const { props } of buttons) {
        assert(props.disabled || props['aria-disabled'], 'Removing duplicate text must not enable the action');
        assert(props['aria-describedby'], 'The blocked action must retain its accessible reason');
        const descriptions = props['aria-describedby'].split(/\s+/).map(id => h.walk(tree).find(n => n.props.id === id));
        assert(descriptions.some(node => node && h.text(node).includes(message)), 'The accessible reason must resolve to its explanation');
      }
    }
    checked++;
  }
  const missingContext = '还没读到可以保存的资料，请点「刷新最新资料」后重试。';
  once(h.render(w.ResourceForms, { adapter: { command() {} }, kind: 'material', source: 'production', command: idle }), missingContext, 1);
  once(h.render(w.SystemMaintenanceControls.Confirm, { action: 'create', reason: '当前操作不可用，请先刷新。' }), '当前操作不可用，请先刷新。', 1);

  const adoptionScope = { scenario_ref: h.reference(40), draft_ref: h.reference(41), task_count: 3,
    baseline: { plan_ref: h.reference(42), version: 1 } }, adoptionCalls = { inspect: 0, submit: 0, lookup: 0 };
  const adoptionSession = { saved: null, result: null, preview: null, consent: true, disabled: false,
    sourceError: '', storageError: '', error: '', notice: '', busy: false, original: adoptionScope,
    draft: { reason: '核对完整安排', declared_operator: '经办人' }, close() {}, setConsent() {}, change() {}, finish() {}, sync() {},
    inspect() { adoptionCalls.inspect++; }, submit() { adoptionCalls.submit++; }, lookup() { adoptionCalls.lookup++; } };
  const adoptionDialog = patch => h.render(w.TrialAdoptionControls.Dialog,
    { session: { ...adoptionSession, ...patch }, scenarioRef: adoptionScope.scenario_ref, name: '已保存试调' });
  const adoptionButton = (tree, label) => h.walk(tree).find(node => node.type === 'button' && visible(node) === label);
  const uncheckedAdoption = adoptionDialog({});
  once(uncheckedAdoption, '当前采用条件尚未完成预检。');
  assert(adoptionButton(uncheckedAdoption, '确认正式采用').props.disabled, 'Saving a scenario alone must not authorize adoption');
  const allowedAdoption = adoptionDialog({ preview: { ...adoptionScope, validation: { can_adopt: true, issues: [] } } });
  once(allowedAdoption, '本次采用预检已通过，请核对采用原因和经办人后确认。');
  const confirmAdoption = adoptionButton(allowedAdoption, '确认正式采用');
  assert(!confirmAdoption.props.disabled && !confirmAdoption.props['aria-disabled']);
  confirmAdoption.props.onClick({ currentTarget: {}, preventDefault() {} });
  assert.strictEqual(adoptionCalls.submit, 1, 'The existing confirmation callback remains the sole submit action');
  const rejectedAdoption = adoptionDialog({ preview: { scenario_ref: adoptionScope.scenario_ref,
    validation: { can_adopt: false, issues: [{ code: 'source_changed', message: '现场资料已变化。' }] } } });
  once(rejectedAdoption, '本次采用预检未通过，请按提示处理后重新预检。');
  assert(adoptionButton(rejectedAdoption, '确认正式采用').props.disabled);
  adoptionButton(rejectedAdoption, '重新预检').props.onClick({ currentTarget: {}, preventDefault() {} });
  assert.strictEqual(adoptionCalls.inspect, 1);
  const pendingAdoption = adoptionDialog({ saved: { scenario_ref: adoptionScope.scenario_ref, phase: 'pending',
    preview: adoptionScope, input: adoptionSession.draft, request_key: 'trial-adoption-existing' } });
  assert(!adoptionButton(pendingAdoption, '确认正式采用'), 'A pending submitted action stays in result lookup');
  adoptionButton(pendingAdoption, '查询结果').props.onClick({ currentTarget: {}, preventDefault() {} });
  assert.strictEqual(adoptionCalls.lookup, 1);

  const fields = w.FieldEditorFields;
  w.FieldEditorFields = () => null; // This regression concerns the form/footer ownership, not the field inputs.
  const task = { task_ref: h.reference(1), plan_ref: h.reference(2), operation_ref: h.reference(3), execution: { reports: [], write_context: null } };
  const retained = { baseline: { task_ref: h.reference(4), plan_ref: task.plan_ref, report_ref: null, revision_ref: null, legacy_ref: null },
    draft: w.FieldContract.draft(null), initialDraft: w.FieldContract.draft(null), suggestions: {} };
  once(h.render(w.FieldEditor, { task, retained, action: 'create', adapter: {}, command: idle }), '原记录或任务已变化，暂存内容未写入；请取消后重新核对。', 2);
  w.FieldEditorFields = fields;
  const day = { date: '2026-10-10', explicit: false, stored: null, fields: { type: 'work', hours: 8, eff: 100, allowNormal: 'yes', allowUrgent: 'yes', note: '', periods: null },
    effective: { is_working: true, window_start: '2026-10-10T08:00:00', window_end: '2026-10-10T16:00:00', periods: null } };
  once(h.render(w.CalendarDayDialog, { adapter: {}, day, source: 'production', command: idle }), missingContext, 1);
  const groupProps = { adapter: { command() {}, stagePreview() {} }, command: idle,
    result: { data: { operations: [], external_groups: [], workflow: { route: { state: 'confirmed' } }, capabilities: { stage_confirm: true } }, meta: { source: 'production' } } };
  once(h.render(w.ProcessGroupEditor, groupProps), '请先新增、修改或解除外协段。', 2);
  // A retained leave prompt follows the draft. useState slots: useDraft 0-4 (draft 1), usePage 5-7, editing 8, picker 9, discard 10.
  const groupUnsaved = '本次外协段修改尚未保存。';
  assert(!visible(h.render(w.ProcessGroupEditor, groupProps, { ProcessGroupEditor: { 10: true } })).includes(groupUnsaved), 'A clean draft has nothing unsaved to warn about');
  once(h.render(w.ProcessGroupEditor, groupProps, { ProcessGroupEditor: { 1: { groups: [], discard_group_refs: [h.reference(43)] }, 10: true } }), groupUnsaved);

  // A group-wide restriction is shown once; a restore-specific restriction still remains visible.
  const readMaintenance = w.SystemMaintenanceControls.useRead;
  const file = { key: '1'.repeat(64), record_kind: 'backup_file', backup_ref: h.reference(5), filename: 'backup.db', type: 'backup', status: 'available', size_bytes: 10 };
  const sharedReason = '请先完成当前文件操作。', restoreReason = '这个备份暂时不能恢复，请核对文件。';
  const maintenance = { capabilities: { create: false, delete: false, restore: false, blocked_reason: sharedReason, restore_reason: restoreReason },
    rows: [file], sources: [], page: { number: 1, page_size: 10, total: 1, pages: 1 } };
  w.SystemMaintenanceControls.useRead = () => ({ data: { data: maintenance, meta: { as_of: '2026-10-10T08:00:00' } }, loading: false, error: null });
  const backupTree = h.render(w.SystemMaintenanceRecords, { api: {}, kind: 'backups', pageSize: 10, revision: 0, command: idle },
    { Records: { 5: { key: file.key, record_kind: file.record_kind, backup_ref: file.backup_ref } } });
  once(backupTree, sharedReason, 2); once(backupTree, restoreReason, 1);
  w.SystemMaintenanceControls.useRead = () => ({ data: { data: { rows: [], sources: [], page: { number: 1, size: 10, total: 0, pages: 1 } },
    meta: { as_of: '2026-10-10T08:00:00' } }, loading: false, error: null });
  assert(visible(h.render(w.SystemMaintenanceRecords, { api: {}, kind: 'logs', pageSize: 10, revision: 0, command: idle })).includes('运行日志与操作记录'),
    'The logs collection does not carry backup capabilities');
  w.SystemMaintenanceControls.useRead = readMaintenance;

  // A failed status read stays in system management; only a real stop or pending restore takes over the page.
  const readyHost = { state: 'ready', request_key: null, restart_required: false, automatic_resume: false,
    operations_available: true, result_source: 'external_maintenance_journal', references: 'reload_from_database_after_process_restart' };
  let hostReads = 0;
  const maintenanceAPI = { host: async () => { hostReads++; return readyHost; } };
  const maintenanceTree = (states, tab = 'overview') => h.render(w.SystemMaintenanceWorkspace,
    { api: maintenanceAPI, tab, theme: 'light', onSetTheme: () => {}, pageSize: 10, children: '系统概况内容' },
    { Workspace: { 6: readyHost, 8: false, ...states } });
  const restoreScreen = tree => h.walk(tree).find(node => node.props['data-restore-maintenance'] === 'warm');
  const statusFailure = new Error('维护状态接口未连接，请重新查询。');
  const failedStatus = maintenanceTree({ 6: null, 7: statusFailure });
  assert(!restoreScreen(failedStatus), 'A normal status-query error must not open the full-screen restore panel');
  const inlineStatus = h.walk(failedStatus).find(node => node.props['data-system-status-error']);
  assert(inlineStatus && visible(inlineStatus).includes(statusFailure.message), 'The local error retains its concrete cause');
  assert(h.walk(inlineStatus).some(node => node.type === 'a' && node.props.href === '/workbench?view=dashboard'
    && visible(node) === '返回工作台'), 'Status-query failure must keep a working navigation exit');
  const retryStatus = h.walk(inlineStatus).find(node => node.type === 'button' && visible(node) === '重新查询');
  assert(retryStatus, 'Status-query failure retains a local recovery action');
  await retryStatus.props.onClick({ currentTarget: {} });
  assert.strictEqual(hostReads, 1);
  const recoveredState = Object.fromEntries(h.updates().filter(update => update.name === 'Workspace').map(update => [update.index, update.value]));
  const recoveredStatus = maintenanceTree(recoveredState);
  assert(!restoreScreen(recoveredStatus) && visible(recoveredStatus).includes('系统概况内容'), 'A successful recheck reopens the ordinary system view');

  w.SystemMaintenanceControls.useRead = () => ({ data: { data: { ...maintenance,
    capabilities: { create: true, delete: true, restore: true, blocked_reason: '', restore_reason: '' } },
    meta: { as_of: '2026-10-10T08:00:00' } }, loading: false, error: null });
  const busyMaintenance = maintenanceTree({ 6: { ...readyHost, operations_available: false } }, 'backups');
  assert(!restoreScreen(busyMaintenance), 'Temporary unavailability of file operations is not a restore');
  const createBackup = h.walk(busyMaintenance).find(node => node.type === 'button' && visible(node) === '新增备份');
  assert(createBackup && (createBackup.props.disabled || createBackup.props['aria-disabled']), 'Unavailable file operations stay blocked');
  assert.strictEqual(createBackup.props['data-wb-disabled-reason'], '当前维护操作暂不可用，请重新查询状态。', 'Disabled operations explain the actual host restriction');
  assert(!visible(busyMaintenance).includes('上次维护操作还没有确认结果'), 'A host restriction must not invent an earlier pending operation');
  const retryMaintenance = h.walk(busyMaintenance).find(node => node.type === 'button' && visible(node) === '重新查询维护状态');
  assert(retryMaintenance, 'A temporary maintenance lock must offer a host recheck');
  await retryMaintenance.props.onClick({ currentTarget: {} });
  const availableAgain = maintenanceTree(Object.fromEntries(h.updates().filter(update => update.name === 'Workspace').map(update => [update.index, update.value])), 'backups');
  const recoveredCreate = h.walk(availableAgain).find(node => node.type === 'button' && visible(node) === '新增备份');
  assert(recoveredCreate && !recoveredCreate.props.disabled && !recoveredCreate.props['aria-disabled'], 'Rechecking a released maintenance lock enables operations');
  w.SystemMaintenanceControls.useRead = readMaintenance;
  const storageFailure = new Error('浏览器未允许保存维护操作编号。');
  const storageStatus = maintenanceTree({ 2: storageFailure });
  assert(!restoreScreen(storageStatus) && visible(storageStatus).includes('系统概况内容'), 'Local storage failure does not stop a ready server or read-only views');
  once(storageStatus, storageFailure.message);
  once(maintenanceTree({ 2: storageFailure }, 'backups'), storageFailure.message, 1);

  const restoreIntent = { request_key: 'system-' + '2'.repeat(48), action: 'restore', summary: '恢复所选备份' };
  for (const states of [{ 1: restoreIntent }, { 6: { ...readyHost, state: 'restart_required', restart_required: true,
    operations_available: false, request_key: restoreIntent.request_key }, 7: statusFailure }]) {
    const stopped = maintenanceTree(states), screen = restoreScreen(stopped);
    assert(screen, 'An unconfirmed restore or previously confirmed stopped host must keep the maintenance screen');
    assert(!visible(stopped).includes('系统概况内容'));
    assert(h.walk(screen).some(node => node.type === 'a' && node.props.href === '/workbench?view=dashboard'
      && visible(node) === '重新检查启动状态'), 'A real restore offers a restart-state check, not a false return promise');
  }
  const restoredResult = { kind: 'file_operation', terminal: true, operation: { ...restoreIntent, state: 'succeeded', terminal: true,
    job_ref: '3'.repeat(32), updated_at: '2026-10-10T08:00:00', history: [], message: '恢复已完成', audit_persisted: true,
    database_origin: 'selected_backup', filename: 'backup.db', protection_filename: 'before_restore.db', replayed: true } };
  const previousRestore = maintenanceTree({ 1: restoreIntent, 3: restoredResult });
  assert(!restoreScreen(previousRestore) && visible(previousRestore).includes('系统概况内容'), 'A historical terminal restore with a ready host must not trap the current session');

  // Both page refresh and reconnection recheck the same host even without a saved command.
  const originalEffect = w.React.useEffect, originalAdd = w.addEventListener, originalRemove = w.removeEventListener;
  let lastDeps, dispose, online;
  w.React.useEffect = (effect, deps) => {
    if (!deps || !deps.includes(maintenanceAPI) || lastDeps && deps.length === lastDeps.length && deps.every((value, index) => value === lastDeps[index])) return;
    if (dispose) dispose(); lastDeps = deps; dispose = effect();
  };
  w.addEventListener = (type, handler) => { if (type === 'online') online = handler; };
  w.removeEventListener = () => {};
  const refreshWorkspace = revision => h.render(w.SystemMaintenanceWorkspace,
    { api: maintenanceAPI, tab: 'overview', theme: 'light', pageSize: 10, revision }, { Workspace: { 6: readyHost, 8: false } });
  const beforeRefresh = hostReads;
  refreshWorkspace(0); refreshWorkspace(0); refreshWorkspace(1);
  assert.strictEqual(hostReads - beforeRefresh, 2, 'A page refresh must requery maintenance status, while an unchanged render must not');
  online({ type: 'online' });
  assert.strictEqual(hostReads - beforeRefresh, 3, 'Reconnection must requery maintenance status without a pending operation');
  if (dispose) dispose();
  w.React.useEffect = originalEffect; w.addEventListener = originalAdd; w.removeEventListener = originalRemove;

  const hostRequests = [], racingAPI = { host: () => new Promise((resolve, reject) => hostRequests.push({ resolve, reject })) };
  const racingTree = h.render(w.SystemMaintenanceWorkspace, { api: racingAPI, tab: 'overview', theme: 'light', pageSize: 10 },
    { Workspace: { 6: null, 7: statusFailure, 8: false } });
  const retryRacing = h.walk(racingTree).find(node => node.type === 'button' && visible(node) === '重新查询');
  const olderRead = retryRacing.props.onClick({ currentTarget: {} }), newerRead = retryRacing.props.onClick({ currentTarget: {} });
  hostRequests[1].resolve(readyHost); await newerRead;
  hostRequests[0].reject(statusFailure); await olderRead;
  const latestHostState = Object.fromEntries(h.updates().filter(update => update.name === 'Workspace').map(update => [update.index, update.value]));
  assert.strictEqual(latestHostState[6], readyHost);
  assert.strictEqual(latestHostState[7], null, 'An earlier failed host query must not overwrite a later successful refresh');
  assert.strictEqual(latestHostState[8], false);

  // Trust the server's explicit non-commit result, including admission failures reported as HTTP 503.
  const responseFor = committed => ({ ok: false, status: 503, headers: { get: () => 'application/json' },
    json: async () => ({ ok: false, committed, error: { code: 'maintenance_active', message: '当前维护窗口忙，恢复没有执行。' } }) });
  for (const committed of [false, 'unknown', undefined]) {
    const rejectedAPI = w.SystemMaintenanceAPI.create(async () => responseFor(committed));
    await assert.rejects(rejectedAPI.command(restoreIntent, 'write-context', {}), error => error.rejected === (committed === false));
  }
  const originalStorage = w.localStorage, originalCrypto = w.crypto, originalOutcome = w.SystemMaintenanceControls.Outcome;
  const savedMaintenance = new Map(); let rejectedCommand, rejectedLookups = 0;
  w.localStorage = { getItem: key => savedMaintenance.get(key) || null, setItem: (key, value) => savedMaintenance.set(key, value), removeItem: key => savedMaintenance.delete(key) };
  w.crypto = { getRandomValues: bytes => bytes.fill(34) };
  w.SystemMaintenanceControls.Outcome = ({ command }) => { rejectedCommand = command; return null; };
  const deniedAPI = { host: async () => readyHost, command: w.SystemMaintenanceAPI.create(async () => responseFor(false)).command,
    lookup: async () => { rejectedLookups++; return { kind: 'not_recorded', terminal: false }; } };
  h.render(w.SystemMaintenanceWorkspace, { api: deniedAPI, tab: 'overview', theme: 'light', pageSize: 10 }, { Workspace: { 6: readyHost, 8: false } });
  await rejectedCommand.execute('restore', 'write-context', {});
  await rejectedCommand.lookup();
  assert.strictEqual(rejectedLookups, 0, 'Reconnection must not replace a confirmed rejection with an absent journal record');
  const deniedState = Object.fromEntries(h.updates().filter(update => update.name === 'Workspace').map(update => [update.index, update.value]));
  assert.strictEqual(deniedState[3].kind, 'rejected');
  assert.strictEqual(deniedState[1], null);
  assert.strictEqual(w.SystemMaintenanceAPI.pending().read(), null, 'Explicit rejection clears the persisted pending intent before any page reload');
  w.SystemMaintenanceControls.Outcome = originalOutcome;
  const deniedTree = maintenanceTree(deniedState);
  assert(!restoreScreen(deniedTree) && visible(deniedTree).includes('系统拒绝了这次提交，没有开始恢复。'), 'The rejection remains readable after unlocking');
  assert(!h.walk(deniedTree).some(node => node.type === 'button' && visible(node) === '确认结果'));
  assert(!restoreScreen(maintenanceTree({})), 'A full reload after a rejected restore must not recreate pending maintenance');
  w.SystemMaintenanceControls.Outcome = ({ command }) => { rejectedCommand = command; return null; };
  const uncertainAPI = { ...deniedAPI, command: w.SystemMaintenanceAPI.create(async () => responseFor('unknown')).command };
  h.render(w.SystemMaintenanceWorkspace, { api: uncertainAPI, tab: 'overview', theme: 'light', pageSize: 10 }, { Workspace: { 6: readyHost, 8: false } });
  await rejectedCommand.execute('restore', 'write-context', {});
  assert.strictEqual(w.SystemMaintenanceAPI.pending().read().request_key, restoreIntent.request_key, 'An unknown submission result must retain its original pending intent');
  w.SystemMaintenanceControls.Outcome = originalOutcome;
  assert(restoreScreen(maintenanceTree({})), 'Reload must continue protecting an unknown restore result');
  savedMaintenance.clear();
  const otherIntent = { ...restoreIntent, request_key: 'system-' + '4'.repeat(48) };
  w.SystemMaintenanceAPI.pending().finish(restoreIntent); // Another tab already confirmed this operation.
  savedMaintenance.set(w.SystemMaintenanceAPI.PENDING_KEY, JSON.stringify(otherIntent));
  assert.throws(() => w.SystemMaintenanceAPI.pending().finish(restoreIntent), /上次操作记录已变化/);
  assert.strictEqual(w.SystemMaintenanceAPI.pending().read().request_key, otherIntent.request_key, 'A different pending operation must be retained');
  w.localStorage = originalStorage; w.crypto = originalCrypto;

  const dashboardRead = w.DashboardSession.useRead, dashboardCommand = w.DashboardSession.useCommand;
  w.DashboardSession.useCommand = () => ({ busy: false, saved: null, storageError: null });
  w.DashboardSession.useRead = (_load, _deps, enabled = true) => ({ result: null, loading: false, error: enabled ? new Error('值班台读取失败，请刷新重试。') : null });
  once(h.render(w.WorkbenchDashboardWorkspace, { initialContext: {} }), '值班台读取失败，请刷新重试。');
  w.DashboardSession.useRead = dashboardRead; w.DashboardSession.useCommand = dashboardCommand;
  const calibrationRead = w.CalibrationControls.useRead, adoption = w.CalibrationAdoptionAction, stale = w.WorkbenchTerms.outcomes.stale;
  w.CalibrationControls.useRead = () => ({ result: null, busy: false, error: null });
  w.CalibrationAdoptionAction = () => null;
  // Restored read state occupies slot 1; the selected record, error and stale flag follow it.
  const staleTree = h.render(w.CalibrationWorkspace, { initialContext: {} }, { Workspace: { 4: h.reference(1), 8: new Error(stale), 10: true } });
  once(staleTree, stale);
  assert(visible(staleTree).includes('刷新所选记录'), 'The detail must retain its recovery action');
  once(h.render(w.CalibrationDetail, { selected: h.reference(1), error: new Error('历史报工与归档不一致，请核对来源后刷新。'), stale: true }),
    '历史报工与归档不一致，请核对来源后刷新。');
  w.CalibrationControls.useRead = calibrationRead; w.CalibrationAdoptionAction = adoption;

  // These are real resource-command states: a rejected write result and a restored pending intent.
  async function resourceCommand(adapter, submit) {
    let command;
    function CommandProbe() { command = w.APSResourceSession.useCommand(adapter); return null; }
    h.render(CommandProbe, {});
    if (submit) { await submit(command); h.render(CommandProbe, {}); }
    return command;
  }
  w.crypto = { getRandomValues: values => { values.fill(1); return values; } };
  const staleResult = { ok: false, committed: false, error: { code: 'stale_write', message: stale, fields: [] } };
  const staleCommand = await resourceCommand({ command: async () => staleResult, savePending() {}, clearPending() {} },
    command => command.submit('calendar', 'upsert', day.date, { write_token: 'fixture' }, { date: day.date }));
  assert.strictEqual(staleCommand.phase, 'rejected');
  const staleCalendar = h.render(w.CalendarDayDialog, { adapter: {}, day, source: 'production', command: staleCommand });
  once(staleCalendar, stale, 1);
  assert(visible(staleCalendar).includes(w.WorkbenchTerms.refresh_latest), 'A stale calendar must retain its refresh action');

  const resourceRead = w.APSResourceSession.useQuery, resourceUseCommand = w.APSResourceSession.useCommand;
  w.APSResourceSession.useQuery = () => ({ result: null, loading: false, error: null });
  w.APSResourceSession.useCommand = () => staleCommand;
  const initialDraft = w.APSResourceCatalogModel.draft(null);
  const editor = { action: 'create', base: null, ref: null, draft: initialDraft, baseline: JSON.stringify(initialDraft),
    context: { write_token: 'fixture', capabilities: { create: true } }, source: 'production' };
  const staleCatalog = h.render(w.ResourceCatalog, { kind: 'machine_group', adapter: {} }, { ResourceCatalog: { 1: editor, 6: true } });
  once(staleCatalog, stale, 1);
  assert(visible(staleCatalog).includes(w.WorkbenchTerms.refresh_latest), 'A stale catalog must retain its refresh action');
  w.APSResourceSession.useCommand = resourceUseCommand;
  const restored = await resourceCommand({ readPending: () => ({ kind: 'machine_group', action: 'create', request_key: 'resource-' + '1'.repeat(48), input: {} }), savePending() {}, clearPending() {} });
  assert.strictEqual(restored.phase, 'pending');
  assert.strictEqual(restored.locked, true);
  w.APSResourceSession.useCommand = () => restored;
  once(h.render(w.ResourceCatalog, { kind: 'machine_group', adapter: {} }), '操作结果还没确认，请保留当前页面。', 2);
  w.APSResourceSession.useQuery = resourceRead; w.APSResourceSession.useCommand = resourceUseCommand;

  // Match the production DTO source relationships, then validate them through the shipped API contract.
  // An inactive batch identity makes all three plan categories unavailable; material and run/outsourcing
  // catalogs retain their independent sources (analysis_projection.py / catalogs.py / external.py).
  const planIssue = { code: 'identity_missing', message: '批次编号缺失，无法评估交付风险。请到批次管理核对。' };
  const materialIssue = { code: 'identity_missing', message: '来源关联资料缺失，暂时无法评估，请联系维护人员核对。' };
  const candidateIssue = { code: 'run_schema_unavailable', message: '排产记录结构不完整，请联系维护人员。' };
  const summary = (state = 'no_data', issues = []) => ({ state, risk_count: state === 'unavailable' ? null : 0,
    known_risk_count: 0, unknown_count: 0, closed_count: 0, handling_count: 0, issues, evaluation_gaps: [] });
  function dashboardFixture() {
    const categories = Object.fromEntries(Object.keys(w.DashboardContract.categories).filter(key => key !== 'all').map(key => [key, summary()]));
    for (const key of ['delivery', 'actual', 'downtime']) categories[key] = summary('unavailable', [planIssue]);
    categories.material = summary('unavailable', [materialIssue]); categories.candidate.risk_count = null;
    Object.assign(categories.external, { kind: 'outsourcing_receipts', tracking_basis: 'manual_receipt_facts', handling_supported: true,
      ...Object.fromEntries(['receipt_count', 'current_receipt_count', 'awaiting_return_count', 'overdue_count', 'returned_count',
        'awaiting_confirmation_count', 'unregistered_count', 'source_gap_count'].map(key => [key, 0])),
      entry: { view: 'outsourcing', target: '/api/workbench/v1/outsourcing/receipts', enabled: true } });
    const asOf = '2026-10-10T08:00:00';
    return { ok: true, schema_version: 1, warnings: [], meta: { request_ref: '1'.repeat(32), snapshot_ref: 'S'.repeat(32), source: 'production', time_basis: 'factory_local', as_of: asOf },
      data: { as_of: asOf, plan: null, items: [], categories, page: { number: 1, size: 20, total: 0, pages: 1 },
        resource_pressure: { state: 'unavailable', resource_count: null, detail_target: '/api/workbench/v1/dashboard/analysis?section=pressure', issues: [] },
        candidate_catalog: { state: 'no_data', selection: null, run_count: 0, runs: [], issues: [], page: { has_more: false } }, analysis_error: null,
        analysis: { plan: null, state: 'unavailable', time_scope: null, resource_common: null, tasks: [], resources: [], downtimes: [], overlaps: [], deliveries: [], execution: [],
          issues: [planIssue], as_of: asOf, capabilities: { view: true, adopt: false }, basis: 'current_official_plan_and_readiness_sources',
          pending: { state: 'unavailable', count: null, known_count: 0, items: [], issues: [materialIssue], basis: 'stored_pending_batch_pool' },
          pressure: { count: null, known_count: 0, resource_count: 0, threshold: 0.9, unknown_resources: 0, zero_capacity_resources: 0,
            basis: 'same_range_daily_peak_available_occupancy' } } } };
  }
  function analysisPage(source, section, resourceRef) {
    const analysis = JSON.parse(JSON.stringify(source));
    const totals = Object.fromEntries(['tasks', 'resources', 'downtimes', 'overlaps', 'deliveries', 'execution'].map(key => [key, source[key].length]));
    totals.pending = source.pending.known_count;
    const resource = source.resources.find(row => row.resource_ref === resourceRef);
    totals.resource_days = resource ? resource.days.length : 0;
    const key = { delivery: 'deliveries', actual: 'execution', material: 'pending', pressure: 'resources', timeline: 'tasks', resource_days: 'resource_days' }[section];
    const total = key ? totals[key] : section === 'downtime' ? Math.max(totals.downtimes, totals.overlaps) : 0;
    analysis.pagination = { section, number: 1, size: 20, total, pages: Math.max(1, Math.ceil(total / 20)), totals };
    const allowed = { tasks: ['timeline', 'actual', 'downtime'], resources: ['pressure', 'resource_days'], downtimes: ['downtime'], overlaps: ['downtime'], deliveries: ['delivery', 'timeline'], execution: ['actual'] };
    for (const [key, sections] of Object.entries(allowed)) if (!sections.includes(section)) analysis[key] = [];
    if (section !== 'material') analysis.pending.items = [];
    if (section === 'pressure') analysis.resources = analysis.resources.map(row => ({ ...row, days: [], task_refs: [] }));
    if (section === 'resource_days') analysis.resources = resource ? [{ ...resource, task_refs: [] }] : [];
    return analysis;
  }
  async function dashboardResult(payload, category) {
    const q = w.DashboardContract.scope({ category }), scope = { kind: 'dashboard', ...q }; delete scope.page;
    const input = JSON.parse(JSON.stringify(payload)), detailAnalysis = input.data.analysis;
    input.data.scope = scope; input.data.analysis = analysisPage(detailAnalysis, 'overview');
    const result = await w.DashboardContract.create(async () => ({ ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => input })).list(q);
    assert.strictEqual(result.data.analysis_error, null, 'The representative analysis DTO must pass the actual API contract');
    result.detailAnalysis = detailAnalysis;
    return result;
  }
  function dashboardTree(result, category, command = { busy: false, saved: null, storageError: null }, states = {}, detail = null) {
    let readIndex = 0;
    w.DashboardSession.useCommand = () => command;
    w.DashboardSession.useRead = (_load, dependencies, enabled = true) => {
      const query = dependencies && dependencies[2];
      if (query && query.section) return { result: enabled ? { ...result, data: analysisPage(result.detailAnalysis, query.section, query.resource_ref) } : null, loading: false, error: null };
      return { result: ++readIndex === 1 ? result : readIndex === 3 ? detail : null, loading: false, error: null };
    };
    return h.render(w.WorkbenchDashboardWorkspace, { initialContext: { scope: { category }, tab: 'analysis', ...(detail ? { item_ref: detail.data.item.item_ref } : {}) } }, states);
  }
  const unavailable = dashboardFixture();
  // Run schema failures remain separate even when the formal-plan source fails.
  unavailable.data.categories.candidate = summary('unavailable', [candidateIssue]);
  unavailable.data.candidate_catalog = { state: 'unavailable', runs: [], page: null, run_count: null, issues: [candidateIssue] };
  const unavailableTree = dashboardTree(await dashboardResult(unavailable, 'all'), 'all');
  for (const issue of [planIssue, materialIssue, candidateIssue]) once(unavailableTree, issue.message);
  const materialUnavailableTree = dashboardTree(await dashboardResult(dashboardFixture(), 'material'), 'material');
  once(materialUnavailableTree, materialIssue.message);
  const itemsOnly = h.render(w.DashboardPanels.Gaps, { categories: unavailable.data.categories, selected: 'delivery' });
  once(itemsOnly, planIssue.message);

  // With a loaded plan, an invalid downtime supplies both an analysis-specific issue and a resource issue.
  const pressureIssue = { code: 'assignment_calendar_unavailable', message: '无法计算此安排的班表产能，请到工作日历核对。', operation_count: 1 };
  const analysisIssue = { code: 'downtime_invalid', message: '有停机记录的起止时间或状态填得不对，没有画成有效的停机条。' };
  const resourceIssue = { code: 'downtime_invalid', message: '设备停机时间或状态有误，产能算不出来。请到资料总览核对设备停机。' };
  const independent = dashboardFixture(), d = independent.data, a = d.analysis;
  const plan = { plan_ref: h.reference(20), kind: 'official', is_current_official: true, display_name: '正式采用方案', version: 1 };
  const timeScope = { range_start: '2026-10-09T08:00:00', range_end: '2026-10-09T10:00:00', time_basis: 'factory_local', boundary: 'half_open' };
  for (const key of ['delivery', 'actual', 'downtime', 'material']) d.categories[key] = summary('loaded');
  Object.assign(d.categories.delivery, { due_eligible_count: 0, excluded_due_count: 0, invalid_due_count: 0,
    due_evaluation_count: 0, assessed_count: 0 });
  const gap = { source_ref: h.reference(21), subject: 'DB1 · Turning', code: 'downtime_unknown', message: '停机记录或设备资料填得不对，还判断不了。' };
  Object.assign(d.categories.downtime, { risk_count: null, unknown_count: 1, evaluation_gaps: [gap] });
  d.plan = plan; Object.assign(a, { plan, state: 'available', time_scope: timeScope, issues: [pressureIssue, analysisIssue] });
  const analysisTask = { plan_ref: plan.plan_ref, task_ref: gap.source_ref, operation_ref: h.reference(22), batch_ref: h.reference(23),
    batch_id: 'DB1', process_label: 'Turning', source: 'internal', machine_ref: h.reference(24), operator_ref: null,
    start: timeScope.range_start, end: timeScope.range_end, span_hours: 2 };
  a.tasks = [analysisTask];
  // These unknown-capacity facts come from ResourceTaskIndex/resource_summary for this exact task and invalid downtime.
  const resourceWindow = {
    "occupied_hours": null, "summed_load_hours": null, "outside_calendar_hours": null, "overlap_hours": null, "span_occupied_hours": 2.0,
    "span_summed_hours": 2.0, "span_overlap_hours": 0.0, "overlap_span_hours": 0.0, "known_occupied_hours": null,
    "known_summed_load_hours": null, "known_outside_calendar_hours": null, "known_overlap_hours": null, "known_span_occupied_hours": 2.0,
    "known_span_summed_hours": 2.0, "known_span_overlap_hours": 0.0, "known_overlap_span_hours": 0.0,
    "resource_ref": "000000000000000000000000000000000000000000000018", "resource_kind": "machine", "label": "Lathe", "state": "partial",
    "available_hours": null, "known_available_hours": null, "utilization_ratio": null, "demand_ratio": null, "known_utilization_ratio": null,
    "known_demand_ratio": null, "peak_utilization": null, "known_peak_utilization": null, "high_pressure": null, "zero_capacity_task": null,
    "conflict": false, "unknown_days": 1, "zero_capacity_days": 0, "task_count": 1, "operation_count": 1, "known_task_count": 1,
    "known_operation_count": 1, "work_available": true, "work_state": "complete", "unknown_workload_count": 0, "numerator_hours": null,
    "denominator_hours": null, "issues": [{"code": "downtime_invalid", "message": "设备停机时间或状态有误，产能算不出来。请到资料总览核对设备停机。"}],
    "metric_version": "available_occupancy_v1", "source": "current_transaction_snapshot"
  };
  const machineResourceSummary = {
    "resource_count": 1, "known_capacity_count": 0, "unknown_capacity_count": 1, "unknown_workload_count": 0,
    "unknown_workload_resource_count": 0, "available_hours": null, "known_available_hours": null, "occupied_hours": null,
    "known_occupied_hours": null, "summed_load_hours": null, "known_summed_load_hours": null, "outside_calendar_hours": null,
    "known_outside_calendar_hours": null, "overlap_hours": null, "known_overlap_hours": null, "span_occupied_hours": 2.0,
    "known_span_occupied_hours": 2.0, "span_summed_hours": 2.0, "known_span_summed_hours": 2.0, "span_overlap_hours": 0.0,
    "known_span_overlap_hours": 0.0, "overlap_span_hours": 0.0, "known_overlap_span_hours": 0.0, "task_count": 1, "known_task_count": 1,
    "operation_count": 1, "known_operation_count": 1, "used_resource_count": 1, "known_used_resource_count": 1, "high_pressure_count": null,
    "known_high_pressure_count": 0, "zero_capacity_task_count": null, "known_zero_capacity_task_count": 0, "conflict_resource_count": 0,
    "known_conflict_resource_count": 0, "unknown_day_resource_count": 1, "known_unknown_day_resource_count": 1, "peak_utilization": null,
    "known_peak_utilization": null, "numerator_hours": null, "denominator_hours": null, "known_numerator_hours": null,
    "known_denominator_hours": null, "utilization_ratio": null, "demand_ratio": null, "known_utilization_ratio": null,
    "known_demand_ratio": null, "balance_cv": null, "known_balance_cv": null, "balance_state": "unavailable",
    "balance_reason": {"code": "resource_balance_incomplete", "message": "部分资源的完整容量或占用缺项，均衡度显示覆盖不足。"}, "state": "partial",
    "issues": [{"code": "downtime_invalid", "message": "设备停机时间或状态有误，产能算不出来。请到资料总览核对设备停机。"}]
  };
  const operatorResourceSummary = {
    "resource_count": 0, "known_capacity_count": 0, "unknown_capacity_count": 0, "unknown_workload_count": 1,
    "unknown_workload_resource_count": 0, "available_hours": 0.0, "known_available_hours": 0.0, "occupied_hours": null,
    "known_occupied_hours": null, "summed_load_hours": null, "known_summed_load_hours": null, "outside_calendar_hours": null,
    "known_outside_calendar_hours": null, "overlap_hours": null, "known_overlap_hours": null, "span_occupied_hours": null,
    "known_span_occupied_hours": null, "span_summed_hours": null, "known_span_summed_hours": null, "span_overlap_hours": null,
    "known_span_overlap_hours": null, "overlap_span_hours": null, "known_overlap_span_hours": null, "task_count": null,
    "known_task_count": null, "operation_count": null, "known_operation_count": null, "used_resource_count": null,
    "known_used_resource_count": 0, "high_pressure_count": null, "known_high_pressure_count": 0, "zero_capacity_task_count": null,
    "known_zero_capacity_task_count": 0, "conflict_resource_count": null, "known_conflict_resource_count": 0, "unknown_day_resource_count": 0,
    "known_unknown_day_resource_count": 0, "peak_utilization": null, "known_peak_utilization": null, "numerator_hours": null,
    "denominator_hours": 0.0, "known_numerator_hours": null, "known_denominator_hours": null, "utilization_ratio": null, "demand_ratio": null,
    "known_utilization_ratio": null, "known_demand_ratio": null, "balance_cv": null, "known_balance_cv": null, "balance_state": "unavailable",
    "balance_reason": {"code": "resource_balance_incomplete", "message": "部分资源的完整容量或占用缺项，均衡度显示覆盖不足。"}, "state": "unavailable",
    "issues": [{"code": "resource_identity_unknown", "message": "保存任务缺少永久资源身份，资源汇总保留覆盖缺口。", "field": "operator"}]
  };
  a.resource_common = {
    "metric_version": "decision-resource-v3", "source": "current_transaction_snapshot", "start": "2026-10-09T08:00:00",
    "end": "2026-10-09T10:00:00", "time_basis": "factory_local", "cohort_basis": "current_official_plan",
    "cohort": [{"ref": "000000000000000000000000000000000000000000000018", "kind": "machine", "label": "Lathe"}],
    machine: machineResourceSummary, operator: operatorResourceSummary
  };
  a.resources = [{ resource_ref: analysisTask.machine_ref, label: 'Lathe', kind: 'machine', state: 'partial', window_metrics: resourceWindow, issues: [resourceIssue],
    peak_utilization: null, unknown_days: 1, zero_capacity_days: 0, task_refs: [analysisTask.task_ref],
    days: [{ date: '2026-10-09', start: timeScope.range_start, end: timeScope.range_end, occupied_hours: 2, overlap_hours: 0,
      available_hours: null, inside_available_hours: null, outside_available_hours: null, utilization: null,
      window_metrics: { ...resourceWindow, date: '2026-10-09', start: timeScope.range_start, end: timeScope.range_end } }] }];
  a.downtimes = [{ downtime_ref: h.reference(25), machine_ref: analysisTask.machine_ref, start: '2026-10-09T09:00:00', end: '2026-10-09T09:00:00',
    recorded_at: '2026-10-09T07:00:00', recorded_at_basis: 'local_time', valid: false }];
  a.pressure.resource_count = 1; a.pressure.unknown_resources = 1;
  a.pending = { state: 'available', count: 0, known_count: 0, items: [], issues: [], basis: 'stored_pending_batch_pool' };
  d.resource_pressure = { state: 'partial', plan_ref: plan.plan_ref, time_scope: timeScope, issues: [pressureIssue], resource_count: 1,
    detail_target: '/api/workbench/v1/dashboard/analysis?section=pressure' };
  const independentTree = dashboardTree(await dashboardResult(independent, 'all'), 'all');
  for (const issue of [pressureIssue, analysisIssue]) once(independentTree, issue.message);
  // The resource-specific cause has one owner in its native, keyboard-expandable details.
  const resourceRow = h.walk(independentTree).find(node => node.type === 'tr' && node.props['data-resource-ref'] === analysisTask.machine_ref);
  const resourceDetails = resourceRow && h.walk(resourceRow).find(node => node.type === 'details');
  const resourceSummary = resourceDetails && [resourceDetails.children].flat(Infinity).find(node => node && node.type === 'summary');
  assert(resourceDetails && !resourceDetails.props.open && resourceSummary && visible(resourceSummary), 'The resource cause retains a visible native disclosure');
  assert(!visible(independentTree).includes(resourceIssue.message), 'The initially collapsed resource cause is not duplicated in the page summary');
  const resourceNotices = h.walk(independentTree).filter(node => /\bwb-issues\b/.test(node.props.className || '') && visible(node).includes(resourceIssue.message));
  assert.strictEqual(resourceNotices.length, 1, 'The independent resource cause must have exactly one owner');
  assert(h.walk(resourceDetails).includes(resourceNotices[0]) && resourceNotices[0].props.role === 'status', 'The resource disclosure retains its accessible concrete cause');
  once({ ...resourceDetails, props: { ...resourceDetails.props, open: true } }, resourceIssue.message);
  const evidence = h.walk(independentTree).find(node => node.props['data-gap-source'] === gap.source_ref);
  assert(evidence && h.text(evidence).includes(gap.subject), 'Analysis ownership must retain category evaluation-gap evidence');
  once(h.render(w.DashboardPanels.Pressure, { data: d }), pressureIssue.message);
  // A loaded run catalog renders each run's open action (a removed navigation flag must not stay referenced in the row).
  const runRef = h.reference(24), runNavigations = [];
  const candidatesTree = h.render(w.DashboardPanels.Candidates, { navigate: target => runNavigations.push(target), data: { candidate_catalog: {
    state: 'loaded', run_count: 1, issues: [], page: { total: 1, has_more: false },
    runs: [{ run_ref: runRef, accepted_at: '2026-01-05T08:00:00', state: 'completed', candidate_count: 2, scope_summary: { batch_count: 3 } }] } } });
  const runRow = h.walk(candidatesTree).find(node => node.type === 'tr' && node.props['data-run-ref'] === runRef);
  const openRun = runRow && h.walk(runRow).find(node => node.type === 'button' && visible(node) === '查看候选');
  assert(openRun && !openRun.props.disabled && !openRun.props['aria-disabled'], 'Each listed run keeps an enabled open action');
  openRun.props.onClick({ currentTarget: {}, preventDefault() {} });
  assert.strictEqual(JSON.stringify(runNavigations), JSON.stringify([{ view: 'analysis', context: { run_ref: runRef }, enabled: true }]));

  // An unknown stored batch status is an independent pending-pool issue, not a material read failure.
  const pendingIssue = { code: 'batch_status_unknown', message: '有批次的状态填得不对，待排总数算不出来。' };
  a.pending = { ...a.pending, state: 'partial', count: null, unknown_status_count: 1, issues: [pendingIssue] };
  const materialGap = { source_ref: h.reference(23), subject: 'DB1 · Part', code: 'readiness_unknown', message: '齐套数据读不完整，算不出缺多少，也不能当作齐套。' };
  Object.assign(d.categories.material, { risk_count: null, unknown_count: 1, evaluation_gaps: [materialGap] });
  const materialIndependentTree = dashboardTree(await dashboardResult(independent, 'material'), 'material');
  once(materialIndependentTree, pendingIssue.message);
  assert(h.walk(materialIndependentTree).some(node => node.props['data-gap-source'] === materialGap.source_ref), 'The material evaluation gap must remain available');
  once(h.render(w.DashboardAnalysisPanels.Material, { data: a }), pendingIssue.message);
  w.DashboardSession.useRead = dashboardRead; w.DashboardSession.useCommand = dashboardCommand;

  // Drive the actual command hooks through a rejected response, using in-memory storage only.
  async function rejection(useCommand, api, submit) {
    const originalReact = w.React, slots = [], effects = [], listeners = new Map(), storage = new Map();
    let cursor = 0;
    w.React = { ...originalReact,
      useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = typeof initial === 'function' ? initial() : initial;
        return [slots[i], value => { slots[i] = typeof value === 'function' ? value(slots[i]) : value; }]; },
      useRef(initial) { const i = cursor++; if (!(i in slots)) slots[i] = { current: initial }; return slots[i]; },
      useEffect(effect) { const i = cursor++; if (!(i in slots)) { slots[i] = true; effects.push(effect); } }
    };
    w.localStorage = { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) };
    w.addEventListener = (key, callback) => listeners.set(key, callback);
    w.removeEventListener = key => listeners.delete(key);
    w.dispatchEvent = event => { if (listeners.has(event.type)) listeners.get(event.type)(event); };
    w.crypto = { getRandomValues: values => { values.fill(1); return values; } };
    w.navigator = { locks: { request: async (_key, _options, callback) => callback({}) } };
    try {
      let command = useCommand(api);
      const cleanups = effects.map(effect => effect());
      await submit(command); cursor = 0; command = useCommand(api);
      cleanups.forEach(cleanup => { if (typeof cleanup === 'function') cleanup(); });
      assert.strictEqual(command.storageError, null);
      return command;
    } finally { w.React = originalReact; }
  }
  const failure = '来源资料已变化，请刷新后重试。';
  const rejectedResponse = async () => ({ ok: false, status: 409, headers: { get: () => 'application/json' },
    json: async () => ({ ok: false, committed: false, error: { code: 'stale_write', message: failure, fields: [] } }) });
  const handling = { status: 'new', ...Object.fromEntries(w.DashboardContract.fields.map(key => [key, null])) };
  const item = { item_ref: h.reference(6), subject: '测试风险', handling, source: {}, risk: {}, write_context: { write_token: 'fixture', capabilities: { transition: true } } };
  const dashboardRejected = await rejection(w.DashboardSession.useCommand, w.DashboardContract.create(rejectedResponse),
    command => command.submit(item, 'transition', { target_status: 'following', owner: '经办人', deadline: '2026-10-11', action: '核对', remark: '说明' }));
  assert.strictEqual(dashboardRejected.saved.phase, 'rejected');
  const dashboardOutcome = h.render(w.DashboardHandling, { command: dashboardRejected });
  once(dashboardOutcome, failure); once(dashboardOutcome, '上次处置没有生效');
  assert(visible(dashboardOutcome).includes('完成'), 'The retained rejected action must still be finishable');
  const dashboardPending = h.render(w.DashboardHandling, { command: { ...dashboardRejected, saved: { ...dashboardRejected.saved, phase: 'pending' }, error: null } });
  once(dashboardPending, w.WorkbenchTerms.outcomes.pending('处置'));
  assert(visible(dashboardPending).includes('查询结果'));

  const after = { sent: '2026-10-09T08:00:00', planned: '2026-10-11T08:00:00', returned: null, confirmedState: 'in_transit' };
  const target = { kind: 'single', batch_ref: h.reference(7), supplier_ref: h.reference(8), operation_refs: [h.reference(9)], grouping_basis: 'explicit_receipt_membership',
    batch: { ref: h.reference(7), business_code: 'B1', label: '批次' }, supplier: { ref: h.reference(8), label: '供应商' }, operations: [{ operation_ref: h.reference(9), business_code: 'OP1', label: '工序' }] };
  const input = { ...after, target: w.OutsourcingContract.target(target), declared_operator: '经办人', reason: '登记说明' };
  const preview = { ok: true, schema_version: 1, warnings: [], meta: { source: 'production', time_basis: 'factory_local', snapshot_ref: null, as_of: '2026-10-10T08:00:00' },
    data: { input, target, before: null, after, outsourcing_ref: null, can_confirm: true, write_context: { write_token: 'fixture', capabilities: { confirm: true } },
      execution: { automatically_reported: false, operation_refs: target.operation_refs, service: 'WorkbenchProductionReportService', reason: '回厂仍需报工' } } };
  const outsourcingRejected = await rejection(w.OutsourcingSession.useCommand, w.OutsourcingContract.create(rejectedResponse), command => command.submit(preview));
  assert.strictEqual(outsourcingRejected.saved, null);
  const outsourcingOutcome = h.render(w.OutsourcingControls.Editor, { api: {}, command: outsourcingRejected });
  once(outsourcingOutcome, failure); once(outsourcingOutcome, '上次外协登记没有生效');
  assert(visible(outsourcingOutcome).includes('预检核对'), 'A rejected registration must return to the editable form');
  const outsourcingPending = h.render(w.OutsourcingControls.Editor, { api: {}, command: { ...outsourcingRejected, error: null, notice: '',
    saved: { phase: 'pending', target, after, input, request_key: 'outsourcing-' + '1'.repeat(48) } } });
  once(outsourcingPending, w.WorkbenchTerms.outcomes.pending('外协登记'));
  assert(visible(outsourcingPending).includes('查询结果'));

  // Start with an actual local-storage read failure. Neither domain may send a command until it recovers.
  function storageCommand(useCommand) {
    let command, serverCalls = 0;
    w.localStorage = { getItem() { throw new Error('Storage unavailable'); } };
    function InitialCommand() { command = useCommand({ command() { serverCalls++; } }); return null; }
    h.render(InitialCommand, {});
    assert(command.storageError && !command.saved);
    return { command, calls: () => serverCalls };
  }
  function recovery(tree, command, inDialog) {
    once(tree, command.storageError.message);
    const buttons = h.walk(tree).filter(node => node.type === 'button' && visible(node) === '刷新上次操作记录');
    assert.strictEqual(buttons.length, 1, 'The sole visible error owner must retain its recovery action');
    assert(!buttons[0].props.disabled && !buttons[0].props['aria-disabled']);
    const dialogs = h.walk(tree).filter(node => node.props.role === 'dialog');
    assert.strictEqual(dialogs.length, inDialog ? 1 : 0);
    if (inDialog) assert(h.walk(dialogs[0]).includes(buttons[0]), 'Recovery must be reachable inside the modal');
    w.localStorage = { getItem: () => null };
    buttons[0].props.onClick({ currentTarget: {}, preventDefault() {} });
    assert(h.updates().some(update => update.value === null), 'Refresh must actually retry and clear the storage failure');
  }
  const storageDashboard = storageCommand(dashboardCommand);
  await storageDashboard.command.submit(item, 'transition', {});
  assert.strictEqual(storageDashboard.calls(), 0);
  const storageResult = await dashboardResult(dashboardFixture(), 'delivery');
  recovery(dashboardTree(storageResult, 'delivery', storageDashboard.command), storageDashboard.command, false);
  const currentItem = { ...item, category: 'delivery', risk: { active: true }, allowed_transitions: ['new', 'following'] };
  const dashboardStorageModal = dashboardTree(storageResult, 'delivery', storageDashboard.command, { Content: { 4: true } }, { data: { item: currentItem } });
  recovery(dashboardStorageModal, storageDashboard.command, true);
  const blockedHandling = h.walk(dashboardStorageModal).find(node => node.type === 'button' && visible(node) === '提交处置');
  assert(blockedHandling && blockedHandling.props.disabled && blockedHandling.props['aria-describedby'], 'Storage failure must keep handling disabled with an accessible explanation');
  // A retained open flag during a refresh does not hide the error when no actual modal can be rendered.
  recovery(dashboardTree(storageResult, 'delivery', storageDashboard.command, { Content: { 4: true } }), storageDashboard.command, false);
  w.DashboardSession.useRead = dashboardRead; w.DashboardSession.useCommand = dashboardCommand;

  const outsourcingRead = w.OutsourcingSession.useRead, outsourcingCommand = w.OutsourcingSession.useCommand;
  const storageOutsourcing = storageCommand(outsourcingCommand);
  await storageOutsourcing.command.submit(preview);
  assert.strictEqual(storageOutsourcing.calls(), 0);
  w.OutsourcingSession.useRead = () => ({ result: null, loading: false, error: null });
  w.OutsourcingSession.useCommand = () => storageOutsourcing.command;
  recovery(h.render(w.OutsourcingWorkspace, {}), storageOutsourcing.command, false);
  const outsourcingStorageModal = h.render(w.OutsourcingWorkspace, {}, { Content: { 2: { item: null } } });
  recovery(outsourcingStorageModal, storageOutsourcing.command, true);
  const blockedPreview = h.walk(outsourcingStorageModal).find(node => node.type === 'button' && visible(node) === '预检核对');
  assert(blockedPreview && blockedPreview.props.disabled, 'Storage failure must keep registration precheck disabled');
  w.OutsourcingSession.useRead = outsourcingRead; w.OutsourcingSession.useCommand = outsourcingCommand;
  return { notice_checks: checked };
}

const result = spawnSync(process.execPath, [path.join(__dirname, '../_support/gantt_current_runtime.cjs')], {
  cwd: path.join(__dirname, '../..'), encoding: 'utf8', timeout: 30000,
  input: JSON.stringify({ root: path.join(__dirname, '../..'), program: `return (${contract.toString()})(h, assert);` })
});
assert.strictEqual(result.status, 0, result.stdout + result.stderr);
console.log(result.stdout);
