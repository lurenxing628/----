'use strict';
const path = require('node:path'), { spawnNodeSync } = require('../_support/spawn_node.cjs');

// Exercise the shipped components, including their real Button/ErrorBox children.
async function contract(h, assert) {
  const w = h.runtime, idle = { phase: 'idle', locked: false, error: null, result: null };
  w.ReactDOM = { createPortal: element => element };
  w.localStorage = h.memoryStorage();
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
  const ResourceForms = h.module('ResourceForms.jsx').ResourceForms;
  const SystemMaintenanceControls = h.module('SystemMaintenanceControls.jsx').SystemMaintenanceControls;
  const TrialAdoptionControls = h.module('TrialAdoptionControls.jsx').TrialAdoptionControls;
  const FieldContract = h.module('FieldContract.js');
  const FieldEditor = h.module('FieldEditor.jsx').FieldEditor;
  const CalendarDayDialog = h.module('CalendarDayDialog.jsx').CalendarDayDialog;
  const ProcessGroupEditor = h.module('ProcessGroupEditor.jsx').ProcessGroupEditor;
  const SystemMaintenanceRecords = h.module('SystemMaintenanceRecords.jsx').SystemMaintenanceRecords;
  const SystemMaintenanceAPI = h.module('SystemMaintenanceAPI.js');
  const SystemMaintenanceWorkspace = h.module('SystemMaintenanceWorkspace.jsx').SystemMaintenanceWorkspace;
  const APSWorkbenchTransport = h.module('shared/network/transport.js');
  const DashboardSession = h.module('DashboardSession.js');
  const WorkbenchDashboardWorkspace = h.module('DashboardWorkspace.jsx').WorkbenchDashboardWorkspace;
  const WorkbenchTerms = h.module('WorkbenchTerms.js');
  const CalibrationWorkspace = h.module('CalibrationWorkspace.jsx').CalibrationWorkspace;
  const CalibrationDetail = h.module('CalibrationDetail.jsx').CalibrationDetail;
  const APSResourceSession = h.module('shared/session/command-session.js');
  const ResourceCatalog = h.module('ResourceCatalog.jsx').ResourceCatalog;
  const DashboardContract = h.module('DashboardContract.js');
  const DashboardPanels = h.module('DashboardPanels.jsx').DashboardPanels;
  const DashboardHandling = h.module('DashboardHandling.jsx').DashboardHandling;
  const OutsourcingContract = h.module('OutsourcingContract.js');
  const OutsourcingSession = h.module('OutsourcingSession.js');
  const OutsourcingControls = h.module('OutsourcingControls.jsx').OutsourcingControls;
  const OutsourcingWorkspace = h.module('OutsourcingWorkspace.jsx').OutsourcingWorkspace;
  // 用户可见的错误都是 kit 统一错误对象（transport、领域契约、本机存储边界都用它）；其余错误只显示通用句。
  const kit = h.module('shared/contract/kit.js');
  const missingContext = '还没读到可以保存的资料，请点「刷新最新资料」后重试。';
  once(h.render(ResourceForms, { kind: 'material', source: 'production', command: idle }), missingContext, 1);
  once(h.render(SystemMaintenanceControls.Confirm, { action: 'create', reason: '当前操作不可用，请先刷新。' }), '当前操作不可用，请先刷新。', 1);

  const adoptionScope = { scenario_ref: h.reference(40), draft_ref: h.reference(41), task_count: 3,
    baseline: { plan_ref: h.reference(42), version: 1 } }, adoptionCalls = { inspect: 0, submit: 0, lookup: 0 };
  const adoptionSession = { saved: null, result: null, preview: null, consent: true, disabled: false,
    sourceError: null, storageError: null, error: null, notice: '', busy: false, original: adoptionScope,
    draft: { reason: '核对完整安排', declared_operator: '经办人' }, close() {}, setConsent() {}, change() {}, finish() {}, sync() {},
    inspect() { adoptionCalls.inspect++; }, submit() { adoptionCalls.submit++; }, lookup() { adoptionCalls.lookup++; } };
  const adoptionDialog = patch => h.render(TrialAdoptionControls.Dialog,
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
  // 本机采用记录写不进去时，storageError 是 kit 错误：原句经错误框上屏一次，并挡住预检。
  const storageCopy = '本次采用未通过，但本机没能保存这次操作记录。';
  const storageAdoption = adoptionDialog({ storageError: kit.failure(storageCopy) });
  once(storageAdoption, storageCopy);
  assert(adoptionButton(storageAdoption, '重新预检').props.disabled);

  h.setStub('FieldEditorFields.jsx', () => null); // This regression concerns the form/footer ownership, not the field inputs.
  const task = { task_ref: h.reference(1), plan_ref: h.reference(2), operation_ref: h.reference(3), execution: { reports: [], write_context: null } };
  const retained = { baseline: { task_ref: h.reference(4), plan_ref: task.plan_ref, report_ref: null, revision_ref: null },
    draft: FieldContract.draft(null), initialDraft: FieldContract.draft(null), suggestions: {} };
  once(h.render(FieldEditor, { task, retained, action: 'create', command: idle }), '原记录或任务已变化，暂存内容未写入；请取消后重新核对。', 2);
  h.setStub('FieldEditorFields.jsx', undefined);
  const dayPeriods = [{ start: '08:00', end: '16:00', day_offset: 0 }];
  const day = { date: '2026-10-10', explicit: false, stored: null, default_periods: dayPeriods,
    fields: { type: 'work', hours: 8, eff: 100, allowNormal: 'yes', allowUrgent: 'yes', note: '', periods: dayPeriods },
    effective: { is_working: true, window_start: '2026-10-10T08:00:00', window_end: '2026-10-10T16:00:00', periods: dayPeriods } };
  once(h.render(CalendarDayDialog, { day, source: 'production', command: idle }), missingContext, 1);
  const groupProps = { command: idle, onDirty() {},
    result: { data: { operations: [], external_groups: [], workflow: { route: { state: 'confirmed' } } }, meta: { source: 'production' } } };
  once(h.render(ProcessGroupEditor, groupProps), '请先新增、修改或解除外协段。', 2);
  // A retained leave prompt follows the draft: closing a clean draft just returns, closing after an edit asks first.
  const groupUnsaved = '本次外协段修改尚未保存。', button = (tree, label) => h.walk(tree).find(node => node.type === 'button' && visible(node) === label);
  const click = node => node.props.onClick({ currentTarget: {}, preventDefault() {}, stopPropagation() {} });
  let groupClosed = 0;
  const groupEditor = h.mount(ProcessGroupEditor, { ...groupProps, command: { ...idle, clearRejection: () => false }, onClose: () => { groupClosed++; } });
  click(button(groupEditor.tree, '返回工时'));
  assert.strictEqual(groupClosed, 1, 'A clean draft closes without a leave prompt');
  assert(!visible(groupEditor.update()).includes(groupUnsaved), 'A clean draft has nothing unsaved to warn about');
  click(button(groupEditor.tree, '新增外协段'));
  click(button(groupEditor.update(), '返回工时'));
  assert.strictEqual(groupClosed, 1, 'An edited draft asks before leaving');
  once(groupEditor.update(), groupUnsaved);
  groupEditor.unmount();

  // A group-wide restriction is shown once; a restore-specific restriction still remains visible.
  const file = { key: '1'.repeat(64), record_kind: 'backup_file', backup_ref: h.reference(5), filename: 'backup.db', type: 'backup', status: 'available', size_bytes: 10 };
  const sharedReason = '请先完成当前文件操作。', restoreReason = '这个备份暂时不能恢复，请核对文件。';
  const maintenance = { scope: 'backup-files-and-maintenance-events', capabilities: { create: false, delete: false, restore: false, blocked_reason: sharedReason, restore_reason: restoreReason },
    rows: [file], sources: [], page: { number: 1, size: 10, total: 1, pages: 1 } };
  // The record lists answer at the network; SystemMaintenanceAPI.read and the transport check them.
  const maintenanceAsOf = { as_of: '2026-10-10T08:00:00' };
  let backupList = maintenance;
  const recordRoutes = { 'GET /api/workbench/v1/system/backups': () => h.route.envelope(backupList, maintenanceAsOf),
    'GET /api/workbench/v1/system/logs': () => h.route.envelope({ scope: 'bounded-log-windows', rows: [], sources: [], page: { number: 1, size: 10, total: 0, pages: 1 } }, maintenanceAsOf) };
  h.serve(recordRoutes);
  const recordProps = { pageSize: 10, revision: 0, command: idle, active: true, onReadContext() {} };
  const backups = h.mount(SystemMaintenanceRecords, { ...recordProps, kind: 'backups' });
  h.walk(await backups.settle()).find(node => node.type === 'tr' && node.props['data-record-kind'] === file.record_kind).props.onClick();
  const backupTree = backups.update();
  once(backupTree, sharedReason, 2); once(backupTree, restoreReason, 1);
  backups.unmount();
  const logs = h.mount(SystemMaintenanceRecords, { ...recordProps, kind: 'logs' });
  assert(visible(await logs.settle()).includes('运行日志与操作记录'), 'The logs collection does not carry backup capabilities');
  logs.unmount();

  // A failed status read stays in system management; only a real stop or pending restore takes over the page.
  const readyHost = { state: 'ready', request_key: null, restart_required: false, automatic_resume: false,
    operations_available: true, result_source: 'external_maintenance_journal', references: 'reload_from_database_after_process_restart' };
  // The maintenance host, its journal and the restore command answer at the network the way the external maintenance journal does;
  // the shipped SystemMaintenanceAPI, SystemRestoreStatus and transport check every answer. Each query takes the next queued answer
  // (a thunk returning a body, a Response or a promise); with nothing queued the host is ready and the journal has no record.
  // Production mounts always pass revision, record contexts and the change/suspension callbacks.
  const M = SystemMaintenanceAPI, journal = data => ({ ok: true, schema_version: 1, data, meta: { source: 'production', result_source: 'external_maintenance_journal' } });
  const hostAnswer = value => journal({ kind: 'restore_host', host: value }), statusMessage = '维护状态接口未连接，请重新查询。';
  const statusFailure = () => h.route.json(h.route.failure('maintenance_status_unavailable', statusMessage, { committed: 'unknown', retryable: true }), 503);
  let hostAnswers = [], journalAnswers = [], commandAnswers = [];
  const next = (queue, fallback) => (queue.length ? queue.shift() : fallback)();
  const maintenanceCalls = h.serve({ ...recordRoutes,
    'GET /api/workbench/v1/system/restore-host': () => next(hostAnswers, () => hostAnswer(readyHost)),
    'GET /api/workbench/v1/system/results/*': () => next(journalAnswers, () => journal({ kind: 'not_recorded', message: '维护记录里还没有这次操作。' })),
    'POST /api/workbench/v1/system/backups/restore': () => next(commandAnswers, () => { throw new Error('Unexpected restore command'); }) });
  const queries = path => maintenanceCalls.calls.filter(call => call.path === '/api/workbench/v1/system/' + path).length;
  const originalStorage = w.localStorage, originalCrypto = w.crypto, originalNavigator = w.navigator;
  w.crypto = { getRandomValues: bytes => bytes.fill(34) };
  w.navigator = { locks: { request: async (_key, _options, callback) => callback({}) } };
  const workspaceProps = { theme: 'light', onSetTheme: () => {}, pageSize: 10, revision: 0, recordContexts: {}, onChanged() {}, onReadSuspendedChange() {}, onRecordContext() {}, children: '系统概况内容' };
  // Each page opens on its own browser storage; the maintenance session a page keeps belongs to that storage.
  async function maintenancePage({ tab = 'overview', storage = h.memoryStorage() } = {}) {
    w.localStorage = storage;
    const page = h.mount(SystemMaintenanceWorkspace, { ...workspaceProps, tab });
    await page.settle();
    return page;
  }
  const restoreScreen = tree => h.walk(tree).find(node => node.props['data-restore-maintenance'] === 'warm');
  const statusError = tree => h.walk(tree).find(node => node.props['data-system-status-error']);
  hostAnswers = [statusFailure];
  const failedPage = await maintenancePage(), failedStatus = failedPage.tree;
  assert(!restoreScreen(failedStatus), 'A normal status-query error must not open the full-screen restore panel');
  const inlineStatus = statusError(failedStatus);
  assert(inlineStatus && visible(inlineStatus).includes(statusMessage), 'The local error retains its concrete cause');
  assert(h.walk(inlineStatus).some(node => node.type === 'a' && node.props.href === '/workbench?view=dashboard'
    && visible(node) === '返回工作台'), 'Status-query failure must keep a working navigation exit');
  const retryStatus = button(inlineStatus, '重新查询');
  assert(retryStatus, 'Status-query failure retains a local recovery action');
  const hostQueriesBeforeRetry = queries('restore-host');
  await click(retryStatus);
  assert.strictEqual(queries('restore-host') - hostQueriesBeforeRetry, 1);
  const recoveredStatus = await failedPage.settle();
  assert(!restoreScreen(recoveredStatus) && visible(recoveredStatus).includes('系统概况内容'), 'A successful recheck reopens the ordinary system view');
  failedPage.unmount();
  // 浏览器连不上本机服务时，状态查询显示 transport 的中文说明，浏览器的英文原文不上屏。
  hostAnswers = [() => { throw new TypeError('Failed to fetch'); }];
  const unreachablePage = await maintenancePage(), unreachable = unreachablePage.tree;
  assert(visible(statusError(unreachable)).includes(APSWorkbenchTransport.modes.lookup.network()));
  assert(!visible(unreachable).includes('Failed to fetch'), 'An internal status error never shows its English text');
  unreachablePage.unmount();

  backupList = { ...maintenance, capabilities: { create: true, delete: true, restore: true, blocked_reason: '', restore_reason: '' } };
  hostAnswers = [() => hostAnswer({ ...readyHost, operations_available: false })];
  const busyPage = await maintenancePage({ tab: 'backups' }), busyMaintenance = busyPage.tree;
  assert(!restoreScreen(busyMaintenance), 'Temporary unavailability of file operations is not a restore');
  const createBackup = button(busyMaintenance, '新增备份');
  assert(createBackup && (createBackup.props.disabled || createBackup.props['aria-disabled']), 'Unavailable file operations stay blocked');
  assert.strictEqual(createBackup.props['data-wb-disabled-reason'], '当前维护操作暂不可用，请重新查询状态。', 'Disabled operations explain the actual host restriction');
  assert(!visible(busyMaintenance).includes('上次维护操作还没有确认结果'), 'A host restriction must not invent an earlier pending operation');
  const retryMaintenance = button(busyMaintenance, '重新查询维护状态');
  assert(retryMaintenance, 'A temporary maintenance lock must offer a host recheck');
  await click(retryMaintenance);
  const recoveredCreate = button(await busyPage.settle(), '新增备份');
  assert(recoveredCreate && !recoveredCreate.props.disabled && !recoveredCreate.props['aria-disabled'], 'Rechecking a released maintenance lock enables operations');
  busyPage.unmount(); backupList = maintenance;
  // An unreadable local record (here an incomplete one) is a storage failure: the ready server and its read-only views stay open.
  const brokenStorage = () => h.memoryStorage([[M.PENDING_KEY, JSON.stringify({ request_key: 'system-incomplete' })]]);
  w.localStorage = brokenStorage(); const storageFailure = M.inspectPending().storageError;
  assert(kit.isFailure(storageFailure), 'The incomplete local record is reported by the maintenance store itself');
  for (const tab of ['overview', 'backups']) {
    const storagePage = await maintenancePage({ tab, storage: brokenStorage() }), storageStatus = storagePage.tree;
    assert(!restoreScreen(storageStatus), 'Local storage failure does not stop a ready server');
    if (tab === 'overview') { assert(visible(storageStatus).includes('系统概况内容'), 'Local storage failure keeps the read-only views'); once(storageStatus, storageFailure.message); }
    else once(storageStatus, storageFailure.message, 1);
    storagePage.unmount();
  }

  // An unconfirmed restore on disk, or a host that already stopped for one, keeps the maintenance screen.
  const restoreIntent = { request_key: 'system-' + '2'.repeat(48), action: 'restore', summary: '恢复所选备份' };
  const intentStorage = () => h.memoryStorage([[M.PENDING_KEY, JSON.stringify(restoreIntent)]]);
  const stoppedHost = { ...readyHost, state: 'restart_required', restart_required: true, operations_available: false, request_key: restoreIntent.request_key };
  const stoppedPages = [() => maintenancePage({ storage: intentStorage() }), async () => {
    hostAnswers = [() => hostAnswer(stoppedHost)];
    const page = await maintenancePage();
    // A later status query fails; the stop the host already confirmed still owns the page.
    hostAnswers = [statusFailure]; w.dispatchEvent({ type: 'online' }); await page.settle();
    assert.strictEqual(hostAnswers.length, 0); return page;
  }];
  for (const open of stoppedPages) {
    const page = await open(), stopped = page.tree, screen = restoreScreen(stopped);
    assert(screen, 'An unconfirmed restore or previously confirmed stopped host must keep the maintenance screen');
    assert(!visible(stopped).includes('系统概况内容'));
    assert(h.walk(screen).some(node => node.type === 'a' && node.props.href === '/workbench?view=dashboard'
      && visible(node) === '重新检查启动状态'), 'A real restore offers a restart-state check, not a false return promise');
    page.unmount();
  }
  // The journal confirms an earlier restore that another session started; with a ready host this page stays usable.
  journalAnswers = [() => journal({ kind: 'file_operation', operation: { ...restoreIntent, state: 'succeeded', terminal: true,
    job_ref: '3'.repeat(32), updated_at: '2026-10-10T08:00:00', history: [], message: '恢复已完成', audit_persisted: true,
    database_origin: 'selected_backup', filename: 'backup.db', protection_filename: 'before_restore.db', replayed: true } })];
  const previousPage = await maintenancePage({ storage: intentStorage() });
  assert.strictEqual(journalAnswers.length, 0);
  assert(!restoreScreen(previousPage.tree) && visible(previousPage.tree).includes('系统概况内容'), 'A historical terminal restore with a ready host must not trap the current session');
  previousPage.unmount();

  // Both page refresh and reconnection recheck the same host even without a saved command; an unmounted page stops listening.
  const refreshPage = await maintenancePage(), afterMount = queries('restore-host');
  refreshPage.render({ ...workspaceProps, tab: 'overview', revision: 0 }); await refreshPage.settle();
  assert.strictEqual(queries('restore-host'), afterMount, 'An unchanged render must not requery maintenance status');
  refreshPage.render({ ...workspaceProps, tab: 'overview', revision: 1 }); await refreshPage.settle();
  assert.strictEqual(queries('restore-host') - afterMount, 1, 'A page refresh must requery maintenance status');
  w.dispatchEvent({ type: 'online' }); await refreshPage.settle();
  assert.strictEqual(queries('restore-host') - afterMount, 2, 'Reconnection must requery maintenance status without a pending operation');
  refreshPage.unmount(); w.dispatchEvent({ type: 'online' });
  assert.strictEqual(queries('restore-host') - afterMount, 2, 'An unmounted page no longer rechecks on reconnection');

  // Two rechecks race: the earlier failure answers last and must not overwrite the later success.
  hostAnswers = [statusFailure];
  const racingPage = await maintenancePage(), racingAnswers = [];
  const heldHost = () => { const answer = h.route.deferred(); racingAnswers.push(answer); return answer.promise; };
  hostAnswers = [heldHost, heldHost];
  const retryRacing = button(statusError(racingPage.tree), '重新查询');
  const olderRead = click(retryRacing), newerRead = click(retryRacing);
  await racingPage.settle(); assert.strictEqual(racingAnswers.length, 2);
  racingAnswers[1].resolve(hostAnswer(readyHost)); await newerRead; await racingPage.settle();
  racingAnswers[0].resolve(statusFailure()); await olderRead;
  const latestHost = await racingPage.settle();
  assert(!statusError(latestHost), 'An earlier failed host query must not overwrite a later successful refresh');
  assert(visible(latestHost).includes('系统概况内容') && !visible(latestHost).includes('正在查询维护状态…'));
  racingPage.unmount();

  // Trust the server's explicit non-commit result (committed:false on any valid 4xx/5xx failure envelope, including 500 and 503);
  // committed:'unknown' and malformed failure envelopes (such as missing committed) are never definite rejections.
  const maintenanceBusy = (committed, status = 503) => () => h.route.json({ ok: false, committed,
    error: { code: 'maintenance_active', message: '当前维护窗口忙，恢复没有执行。', fields: [], retryable: status >= 500 && committed !== 'unknown', request_ref: '1'.repeat(32) } }, status);
  for (const [committed, status, definite] of [[false, 503, true], [false, 409, true], [false, 500, true], ['unknown', 503, false], [undefined, 503, false]]) {
    commandAnswers = [maintenanceBusy(committed, status)];
    await assert.rejects(M.command(restoreIntent, 'write-context', {}), error => APSWorkbenchTransport.rejected(error) === definite,
      'committed ' + committed + ' with HTTP ' + status + (definite ? ' is' : ' is not') + ' a definite rejection');
  }
  // The page's own restore command, reached through the record list it hands the command to.
  let restoreCommand;
  const restoreFrom = async (storage, answer) => {
    h.setStub('SystemMaintenanceRecords.jsx', function SystemMaintenanceRecords({ command }) { restoreCommand = command; return null; });
    const page = await maintenancePage({ tab: 'backups', storage });
    commandAnswers = [answer]; await restoreCommand.execute('restore', 'write-context', {});
    await page.settle(); h.setStub('SystemMaintenanceRecords.jsx', undefined);
    return page;
  };
  const rejectedStorage = h.memoryStorage(), rejectedPage = await restoreFrom(rejectedStorage, maintenanceBusy(false));
  const journalBeforeLookup = queries('results/' + restoreIntent.request_key);
  await restoreCommand.lookup();
  assert.strictEqual(queries('results/' + restoreIntent.request_key), journalBeforeLookup, 'Reconnection must not replace a confirmed rejection with an absent journal record');
  assert.strictEqual(M.pending.read(), null, 'Explicit rejection clears the persisted pending intent before any page reload');
  const deniedTree = rejectedPage.tree;
  assert(!restoreScreen(deniedTree) && visible(deniedTree).includes('系统拒绝了这次提交，没有开始恢复。'), 'The rejection remains readable after unlocking');
  assert(!button(deniedTree, '确认结果'));
  rejectedPage.unmount();
  const reloadedRejection = await maintenancePage({ storage: rejectedStorage });
  assert(!restoreScreen(reloadedRejection.tree), 'A full reload after a rejected restore must not recreate pending maintenance');
  reloadedRejection.unmount();
  const unknownStorage = h.memoryStorage(), unknownPage = await restoreFrom(unknownStorage, maintenanceBusy('unknown'));
  assert.strictEqual(M.pending.read().request_key, restoreIntent.request_key, 'An unknown submission result must retain its original pending intent');
  unknownPage.unmount();
  const reloadedUnknown = await maintenancePage({ storage: unknownStorage });
  assert(restoreScreen(reloadedUnknown.tree), 'Reload must continue protecting an unknown restore result');
  reloadedUnknown.unmount();
  unknownStorage.removeItem(M.PENDING_KEY);
  const otherIntent = { ...restoreIntent, request_key: 'system-' + '4'.repeat(48) };
  SystemMaintenanceAPI.pending.finish(restoreIntent); // Another tab already confirmed this operation.
  unknownStorage.setItem(SystemMaintenanceAPI.PENDING_KEY, JSON.stringify(otherIntent));
  assert.throws(() => SystemMaintenanceAPI.pending.finish(restoreIntent), /上次操作记录已变化/);
  assert.strictEqual(SystemMaintenanceAPI.pending.read().request_key, otherIntent.request_key, 'A different pending operation must be retained');
  w.localStorage = originalStorage; w.crypto = originalCrypto; w.navigator = originalNavigator;
  w.fetch = () => { throw new Error('Unexpected network request'); };

  // 系统管理页自己的两处失败提示同样只经 WorkbenchError：本机状态读取的错误经 transport 都是 kit 错误对象，原文上屏；
  // 页面诊断导出时浏览器抛的异常不是 kit 错误对象，只显示中文兜底句，原文进折叠区。
  // 维护状态与本机状态都在网络层作答：维护状态确认就绪后，本机状态才解除暂停开始读取。
  const SystemLive = h.module('SystemLive.jsx').SystemLive, liveReadFailure = '本机状态接口未连接，请重试。';
  const livePayload = { database: { state: 'available' },
    backups: { state: 'available', count: 0, message: '' }, logs: { state: 'available', operation_record_count: 0, message: '' },
    config: { state: 'available', values: null, message: '' }, maintenance: { jobs: [] } };
  let overviewAnswers = [];
  h.serve({ 'GET /api/workbench/v1/system/restore-host': () => hostAnswer(readyHost),
    'GET /api/workbench/v1/system/overview': () => next(overviewAnswers, () => h.route.envelope(livePayload, maintenanceAsOf)) });
  const liveProps = { boot: { overview_url: '/api/workbench/v1/system/overview', instance_label: '本机实例' }, theme: 'light', initialContext: {} };
  const folded = (tree, raw) => h.walk(tree).some(node => node.type === 'code' && h.text(node) === raw);
  overviewAnswers = [() => h.route.json(h.route.failure('storage_failure', liveReadFailure), 503)];
  const failedLive = h.mount(SystemLive, liveProps);
  once(await failedLive.settle(), liveReadFailure);
  failedLive.unmount();
  const live = h.mount(SystemLive, liveProps), exportButton = button(await live.settle(), '导出页面诊断');
  assert(exportButton && !exportButton.props.disabled);
  // 浏览器拒绝下载：把下载链接放进页面时抛 DOMException，不是 kit 错误对象。
  const originalCreate = w.document.createElement, originalBody = w.document.body;
  w.document.createElement = () => ({ click() {}, remove() {} });
  w.document.body = { ...originalBody, appendChild() { throw new DOMException('The operation is insecure.', 'SecurityError'); } };
  try { click(exportButton); } finally { w.document.createElement = originalCreate; w.document.body = originalBody; }
  const refusedExport = live.update();
  once(refusedExport, '页面诊断导出失败，请重试。');
  assert(!visible(refusedExport).includes('The operation is insecure.') && folded(refusedExport, 'The operation is insecure.'), 'The browser export error stays in the folded details');
  live.unmount();

  const stale = WorkbenchTerms.outcomes.stale;
  // The duty board's own read fails at the network; its error box owns the backend reason.
  h.serve({ 'GET /api/workbench/v1/dashboard': () => h.route.json(h.route.failure('dashboard_unavailable', '值班台读取失败，请刷新重试。'), 503) });
  const failedBoard = h.mount(WorkbenchDashboardWorkspace, { initialContext: {} });
  once(await failedBoard.settle(), '值班台读取失败，请刷新重试。');
  failedBoard.unmount();
  h.setStub('CalibrationAdoptionAction.jsx', () => null);
  // A stale export of the selected record: only the stale notice with its keep-selection explanation shows, and the
  // detail keeps its recovery action. The list, the selected detail and the export answer at the network.
  const calibrationSnapshot = 'c'.repeat(32), selectedRecord = h.reference(1), calibrationAsOf = { snapshot_ref: calibrationSnapshot, as_of: '2026-10-10T08:00:00' };
  const suggestion = { template_operation_ref: selectedRecord, part_no: 'P-01', sequence: 10, operation_label: '车削', old_unit_hours: 1, suggested_unit_hours: null,
    sample_count: 0, candidate_count: 0, sample_refs: [], exclusion_reasons: [] };
  h.serve({ 'GET /api/workbench/v1/calibration': () => h.route.envelope({ capabilities: { view: true, export: true },
      summary: { total: 1, over_20_percent: 0, suggested: 0, insufficient_data: 1 }, items: [], page: { number: 1, size: 20, total_pages: 1, total: 1 },
      source_constraints: [], exports: { formats: ['csv', 'xlsx'] } }, calibrationAsOf),
    'GET /api/workbench/v1/calibration/export': () => h.route.json(h.route.failure('snapshot_stale', stale), 409),
    'GET /api/workbench/v1/calibration/*': () => h.route.envelope({ suggestion, samples: [] }, calibrationAsOf) });
  const calibration = h.mount(CalibrationWorkspace, { initialContext: { selected: selectedRecord } });
  click(button(await calibration.settle(), '导出全部筛选'));
  const staleTree = await calibration.settle();
  once(staleTree, stale);
  assert(visible(staleTree).includes('刷新所选记录'), 'The detail must retain its recovery action');
  calibration.unmount();
  once(h.render(CalibrationDetail, { selected: h.reference(1), error: kit.failure('历史报工与归档不一致，请核对来源后刷新。'), stale: true }),
    '历史报工与归档不一致，请核对来源后刷新。');
  h.setStub('CalibrationAdoptionAction.jsx', undefined);

  // These are real resource-command states: a rejected write result and a restored pending intent.
  // Commands run through the real namespace API, transport and session storage; only the network answer is replaced.
  const APSResourceAPI = h.module('resource-api.js');
  async function resourceCommand(namespace, submit) {
    let command;
    function CommandProbe() { command = APSResourceSession.useCommand(APSResourceAPI.forNamespace(namespace)); return null; }
    h.render(CommandProbe, {});
    if (submit) { await submit(command); h.render(CommandProbe, {}); }
    return command;
  }
  w.crypto = { getRandomValues: values => { values.fill(1); return values; } };
  // A committed:false 409 is a definite rejection.
  w.sessionStorage = h.memoryStorage();
  h.serve({ 'POST /api/workbench/v1/calendar/upsert': () => h.route.json(h.route.failure('stale_write', stale), 409) });
  const staleCommand = await resourceCommand('calendar',
    command => command.submit('calendar', 'upsert', day.date, { write_token: 'fixture' }, { date: day.date }));
  assert.strictEqual(staleCommand.phase, 'rejected');
  const staleCalendar = h.render(CalendarDayDialog, { day, source: 'production', command: staleCommand });
  once(staleCalendar, stale, 1);
  assert(visible(staleCalendar).includes(WorkbenchTerms.refresh_latest), 'A stale calendar must retain its refresh action');

  // A rejected catalog save: the stale answer sends the editor to review, the save action carries the stale reason once and the
  // refresh action stays. The list with its create context and the save answer at the network.
  const catalogList = { entities: [], page: { number: 1, size: 20, total: 0, pages: 1 },
    create_context: { write_token: 'fixture', capabilities: { 'machine_group.create': true }, blocked_reasons: [] } };
  h.serve({ 'GET /api/workbench/v1/entities/machine_group': () => h.route.envelope(catalogList),
    'POST /api/workbench/v1/entities/machine_group/create': () => h.route.json(h.route.failure('stale_write', stale), 409) });
  w.sessionStorage = h.memoryStorage();
  const catalog = h.mount(ResourceCatalog, { kind: 'machine_group', onClose() {} });
  click(button(await catalog.settle(), '新增设备组'));
  const catalogField = (tree, label) => h.walk(tree).find(node => ['input', 'select'].includes(node.type) && node.props['aria-label'] === label);
  catalogField(await catalog.settle(), '编号').props.onChange({ target: { value: 'G-01' } });
  catalogField(catalog.update(), '名称').props.onChange({ target: { value: '一号设备组' } });
  catalogField(catalog.update(), '状态').props.onChange({ target: { value: 'active' } });
  await h.walk(catalog.update()).find(node => node.type === 'form').props.onSubmit({ preventDefault() {} });
  const staleCatalog = await catalog.settle();
  once(staleCatalog, stale, 1);
  assert(visible(staleCatalog).includes(WorkbenchTerms.refresh_latest), 'A stale catalog must retain its refresh action');
  catalog.unmount();
  h.setStub('shared/session/query.js', { useQuery: () => ({ result: null, loading: false, error: null }) });
  w.sessionStorage = h.memoryStorage([[APSResourceAPI.forNamespace('catalog').pendingKey,
    JSON.stringify({ kind: 'machine_group', action: 'create', request_key: 'resource-' + '1'.repeat(48), ref: null })]]);
  const restored = await resourceCommand('catalog');
  assert.strictEqual(restored.phase, 'pending');
  assert.strictEqual(restored.locked, true);
  h.setStub('shared/session/command-session.js', { useCommand: () => restored });
  once(h.render(ResourceCatalog, { kind: 'machine_group' }), '操作结果还没确认，请保留当前页面。', 2);
  h.setStub('shared/session/query.js', undefined); h.setStub('shared/session/command-session.js', undefined);

  // Match the production DTO source relationships, then validate them through the shipped API contract.
  // An inactive batch identity makes all three plan categories unavailable; material and run/outsourcing
  // catalogs retain their independent sources (analysis_projection.py / catalogs.py / external.py).
  const planIssue = { code: 'identity_missing', message: '批次编号缺失，无法评估交付风险。请到批次管理核对。' };
  const materialIssue = { code: 'identity_missing', message: '来源关联资料缺失，暂时无法评估，请联系维护人员核对。' };
  const candidateIssue = { code: 'run_result_inconsistent', message: '排产记录、提交结果和候选方案的条数对不上，这里不返回结果。请刷新重试；仍不行请联系维护人员。' };
  const summary = (state = 'no_data', issues = []) => ({ state, risk_count: state === 'unavailable' ? null : 0,
    known_risk_count: 0, unknown_count: 0, closed_count: 0, handling_count: 0, issues, evaluation_gaps: [] });
  function dashboardFixture() {
    const categories = Object.fromEntries(Object.keys(DashboardContract.categories).filter(key => key !== 'all').map(key => [key, summary()]));
    for (const key of ['delivery', 'actual', 'downtime']) categories[key] = summary('unavailable', [planIssue]);
    categories.material = summary('unavailable', [materialIssue]); categories.candidate.risk_count = null;
    Object.assign(categories.external, { kind: 'outsourcing_receipts', tracking_basis: 'manual_receipt_facts',
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
  // The duty board answers at the network: the list with its overview analysis, each analysis section and the item detail pass
  // the shipped DashboardContract, DashboardAnalysisAPI and transport. Each list read takes the next queued answer, else `input`.
  let boardListAnswers = [];
  function dashboardEnvelope(payload, category) {
    const q = DashboardContract.scope({ category }), scope = { kind: 'dashboard', ...q }; delete scope.page;
    const input = JSON.parse(JSON.stringify(payload)), detailAnalysis = input.data.analysis;
    input.data.scope = scope; if (detailAnalysis) input.data.analysis = analysisPage(detailAnalysis, 'overview');
    return { input, detailAnalysis, q };
  }
  async function dashboardPage(payload, category, { tab = 'analysis', item = null } = {}) {
    const { input, detailAnalysis, q } = dashboardEnvelope(payload, category), answer = data => ({ ...input, data });
    h.serve({ 'GET /api/workbench/v1/dashboard': () => next(boardListAnswers, () => input),
      'GET /api/workbench/v1/dashboard/analysis': call => answer(analysisPage(detailAnalysis, call.query.section, call.query.resource_ref)),
      'GET /api/workbench/v1/dashboard/items/*': () => answer({ scope: input.data.scope, as_of: input.data.as_of, item }) });
    if (detailAnalysis) assert.strictEqual((await DashboardContract.list(q)).data.analysis_error, null, 'The representative analysis DTO must pass the actual API contract');
    const page = h.mount(WorkbenchDashboardWorkspace, { initialContext: { scope: { category }, tab, ...(item ? { item_ref: item.item_ref } : {}) } });
    await page.settle();
    return page;
  }
  async function dashboardTree(payload, category) {
    const page = await dashboardPage(payload, category), tree = page.tree;
    page.unmount();
    return tree;
  }
  const unavailable = dashboardFixture();
  // Saved-run consistency failures remain separate even when the formal-plan source fails.
  unavailable.data.categories.candidate = summary('unavailable', [candidateIssue]);
  unavailable.data.candidate_catalog = { state: 'unavailable', runs: [], page: null, run_count: null, issues: [candidateIssue] };
  const unavailableTree = await dashboardTree(unavailable, 'all');
  for (const issue of [planIssue, materialIssue, candidateIssue]) once(unavailableTree, issue.message);
  const materialUnavailableTree = await dashboardTree(dashboardFixture(), 'material');
  once(materialUnavailableTree, materialIssue.message);
  const itemsOnly = h.render(DashboardPanels.Gaps, { categories: unavailable.data.categories, selected: 'delivery' });
  once(itemsOnly, planIssue.message);

  // 影响分析读不出来时只经 WorkbenchError 上屏：后端拒绝原因经契约定型成 kit 错误对象照常显示；
  // 契约本地撞上的非 kit 错误（信封里分析缺失又没给原因）显示中文兜底句，英文原文只进折叠区。
  async function analysisFailure(patch) {
    const payload = dashboardFixture(); Object.assign(payload.data, patch);
    const { input, q } = dashboardEnvelope(payload, 'all');
    h.serve({ 'GET /api/workbench/v1/dashboard': () => input });
    return { payload, result: await DashboardContract.list(q) };
  }
  const rejectedAnalysis = await analysisFailure({ analysis: null, analysis_error: '分析超过读取上限。' });
  assert(kit.isFailure(rejectedAnalysis.result.data.analysis_error) && rejectedAnalysis.result.data.analysis === null);
  once(await dashboardTree(rejectedAnalysis.payload, 'all'), '分析超过读取上限。');
  const brokenAnalysis = await analysisFailure({ analysis: null }), brokenCause = brokenAnalysis.result.data.analysis_error;
  assert(brokenCause.name === 'TypeError' && !kit.isFailure(brokenCause));
  const brokenAnalysisTree = await dashboardTree(brokenAnalysis.payload, 'all');
  once(brokenAnalysisTree, '影响分析读取失败，请刷新后重试。');
  assert(!visible(brokenAnalysisTree).includes(brokenCause.message) && folded(brokenAnalysisTree, brokenCause.message), 'An internal analysis error stays in the folded details');

  // With a loaded plan, a broken work calendar supplies both an analysis-level pressure issue and a resource issue.
  const pressureIssue = { code: 'assignment_calendar_unavailable', message: '无法计算此安排的班表产能，请到工作日历核对。', operation_count: 1 };
  const resourceIssue = { code: 'calendar_invalid', message: '工作日历或人员班表有误，这部分产能算不出来。请到工作日历核对。' };
  const independent = dashboardFixture(), d = independent.data, a = d.analysis;
  const plan = { plan_ref: h.reference(20), kind: 'official', is_current_official: true, display_name: '正式采用方案', version: 1 };
  const timeScope = { range_start: '2026-10-09T08:00:00', range_end: '2026-10-09T10:00:00', time_basis: 'factory_local', boundary: 'half_open' };
  for (const key of ['delivery', 'actual', 'downtime', 'material']) d.categories[key] = summary('loaded');
  Object.assign(d.categories.delivery, { due_eligible_count: 0, excluded_due_count: 0, invalid_due_count: 0,
    due_evaluation_count: 0, assessed_count: 0 });
  const gap = { source_ref: h.reference(21), subject: 'DB1 · Turning', code: 'downtime_unknown', message: '停机记录或设备资料填得不对，还判断不了。' };
  Object.assign(d.categories.downtime, { risk_count: null, unknown_count: 1, evaluation_gaps: [gap] });
  d.plan = plan; Object.assign(a, { plan, state: 'available', time_scope: timeScope, issues: [pressureIssue] });
  const analysisTask = { plan_ref: plan.plan_ref, task_ref: gap.source_ref, operation_ref: h.reference(22), batch_ref: h.reference(23),
    batch_id: 'DB1', process_label: 'Turning', source: 'internal', machine_ref: h.reference(24), operator_ref: null,
    start: timeScope.range_start, end: timeScope.range_end, span_hours: 2 };
  a.tasks = [analysisTask];
  // These unknown-capacity facts come from ResourceTaskIndex/resource_summary for this exact task and its broken calendar day.
  const resourceWindow = {
    "occupied_hours": null, "summed_load_hours": null, "outside_calendar_hours": null, "overlap_hours": null, "span_occupied_hours": 2.0,
    "span_summed_hours": 2.0, "span_overlap_hours": 0.0, "overlap_span_hours": 0.0, "known_occupied_hours": null,
    "known_summed_load_hours": null, "known_outside_calendar_hours": null, "known_overlap_hours": null, "known_span_occupied_hours": 2.0,
    "known_span_summed_hours": 2.0, "known_span_overlap_hours": 0.0, "known_overlap_span_hours": 0.0,
    "resource_ref": "000000000000000000000000000000000000000000000018", "resource_kind": "machine", "label": "Lathe", "state": "partial",
    "available_hours": null, "known_available_hours": null, "utilization_ratio": null, "demand_ratio": null, "known_utilization_ratio": null,
    "known_demand_ratio": null, "peak_utilization": null, "known_peak_utilization": null, "high_pressure": null, "zero_capacity_task": null,
    "conflict": false, "unknown_days": 1, "zero_capacity_days": 0, "task_count": 1, "operation_count": 1, "known_task_count": 1,
    "known_operation_count": 1, "work_available": true, "work_state": "complete", "numerator_hours": null,
    "denominator_hours": null, "issues": [{"code": "calendar_invalid", "message": "工作日历或人员班表有误，这部分产能算不出来。请到工作日历核对。"}],
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
    "issues": [{"code": "calendar_invalid", "message": "工作日历或人员班表有误，这部分产能算不出来。请到工作日历核对。"}]
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
    "metric_version": "decision-resource-v4", "source": "current_transaction_snapshot", "start": "2026-10-09T08:00:00",
    "end": "2026-10-09T10:00:00", "time_basis": "factory_local", "cohort_basis": "current_official_plan",
    "cohort": [{"ref": "000000000000000000000000000000000000000000000018", "kind": "machine", "label": "Lathe"}],
    machine: machineResourceSummary, operator: operatorResourceSummary
  };
  a.resources = [{ resource_ref: analysisTask.machine_ref, label: 'Lathe', kind: 'machine', state: 'partial', window_metrics: resourceWindow, issues: [resourceIssue],
    peak_utilization: null, unknown_days: 1, zero_capacity_days: 0, task_refs: [analysisTask.task_ref],
    // Each day row is the shared window row itself, with only its date and bounds.
    days: [{ ...resourceWindow, date: '2026-10-09', start: timeScope.range_start, end: timeScope.range_end }] }];
  a.downtimes = [{ downtime_ref: h.reference(25), machine_ref: analysisTask.machine_ref, start: '2026-10-09T09:00:00', end: '2026-10-09T09:30:00',
    recorded_at: '2026-10-09T07:00:00', recorded_at_basis: 'local_time' }];
  a.pressure.resource_count = 1; a.pressure.unknown_resources = 1;
  a.pending = { state: 'available', count: 0, known_count: 0, items: [], issues: [], basis: 'stored_pending_batch_pool' };
  d.resource_pressure = { state: 'partial', plan_ref: plan.plan_ref, time_scope: timeScope, issues: [pressureIssue], resource_count: 1,
    detail_target: '/api/workbench/v1/dashboard/analysis?section=pressure' };
  const independentTree = await dashboardTree(independent, 'all');
  once(independentTree, pressureIssue.message);
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
  // The pressure cause is owned once by the analysis area above; the pressure panel itself no longer repeats it.
  assert(!h.text(h.render(DashboardPanels.Pressure, { data: d })).includes(pressureIssue.message), 'The pressure panel does not duplicate the analysis-owned pressure cause');
  // A loaded run catalog renders each run's open action (a removed navigation flag must not stay referenced in the row).
  const runRef = h.reference(24), runNavigations = [];
  const candidatesTree = h.render(DashboardPanels.Candidates, { navigate: target => runNavigations.push(target), data: { candidate_catalog: {
    state: 'loaded', run_count: 1, issues: [], page: { total: 1, has_more: false },
    runs: [{ run_ref: runRef, accepted_at: '2026-01-05T08:00:00', state: 'completed', candidate_count: 2, scope_summary: { batch_count: 3 } }] } } });
  const runRow = h.walk(candidatesTree).find(node => node.type === 'tr' && node.props['data-run-ref'] === runRef);
  const openRun = runRow && h.walk(runRow).find(node => node.type === 'button' && visible(node) === '查看候选');
  assert(openRun && !openRun.props.disabled && !openRun.props['aria-disabled'], 'Each listed run keeps an enabled open action');
  openRun.props.onClick({ currentTarget: {}, preventDefault() {} });
  assert.strictEqual(JSON.stringify(runNavigations), JSON.stringify([{ view: 'analysis', context: { run_ref: runRef }, enabled: true }]));

  // A material evaluation gap stays available as evidence under the material tab.
  const materialGap = { source_ref: h.reference(23), subject: 'DB1 · Part', code: 'readiness_unknown', message: '齐套数据读不完整，算不出缺多少，也不能当作齐套。' };
  Object.assign(d.categories.material, { risk_count: null, unknown_count: 1, evaluation_gaps: [materialGap] });
  const materialIndependentTree = await dashboardTree(independent, 'material');
  assert(h.walk(materialIndependentTree).some(node => node.props['data-gap-source'] === materialGap.source_ref), 'The material evaluation gap must remain available');

  // Drive the actual command hooks through a rejected response, using in-memory storage only: a probe mounts the hook,
  // its effects subscribe to the store, and unmounting runs their cleanups.
  w.crypto = { getRandomValues: values => { values.fill(1); return values; } };
  w.navigator = { locks: { request: async (_key, _options, callback) => callback({}) } };
  async function rejection(useCommand, submit) {
    let command;
    function CommandProbe() { command = useCommand(); return null; }
    w.localStorage = h.memoryStorage(); h.serve(rejectedResponse);
    const probe = h.mount(CommandProbe, {});
    await probe.settle(); await submit(command); await probe.settle(); probe.unmount();
    assert.strictEqual(command.storageError, null);
    return command;
  }
  const failure = '来源资料已变化，请刷新后重试。';
  // Only the network answer is stubbed: the real contracts send the command and the transport's Q2-A verdict rejects it.
  const rejectedResponse = () => h.route.json(h.route.failure('stale_write', failure), 409);
  const handling = { status: 'new', ...Object.fromEntries(DashboardContract.fields.map(key => [key, null])) };
  const item = { item_ref: h.reference(6), subject: '测试风险', handling, source: {}, risk: {}, write_context: { write_token: 'fixture', capabilities: { transition: true } } };
  const dashboardRejected = await rejection(DashboardSession.useCommand,
    command => command.submit(item, 'transition', { target_status: 'following', owner: '经办人', deadline: '2026-10-11', action: '核对', remark: '说明' }));
  assert.strictEqual(dashboardRejected.saved.phase, 'rejected');
  const dashboardOutcome = h.render(DashboardHandling, { command: dashboardRejected });
  once(dashboardOutcome, failure); once(dashboardOutcome, '上次处置没有生效');
  assert(visible(dashboardOutcome).includes('完成'), 'The retained rejected action must still be finishable');
  const dashboardPending = h.render(DashboardHandling, { command: { ...dashboardRejected, saved: { ...dashboardRejected.saved, phase: 'pending' }, error: null } });
  once(dashboardPending, WorkbenchTerms.outcomes.pending('处置'));
  assert(visible(dashboardPending).includes('查询结果'));

  const after = { sent: '2026-10-09T08:00:00', planned: '2026-10-11T08:00:00', returned: null, confirmedState: 'in_transit' };
  const target = { kind: 'single', batch_ref: h.reference(7), supplier_ref: h.reference(8), operation_refs: [h.reference(9)], grouping_basis: 'explicit_receipt_membership',
    batch: { ref: h.reference(7), business_code: 'B1', label: '批次' }, supplier: { ref: h.reference(8), label: '供应商' }, operations: [{ operation_ref: h.reference(9), business_code: 'OP1', label: '工序' }] };
  const input = { ...after, target: OutsourcingContract.target(target), declared_operator: '经办人', reason: '登记说明' };
  const preview = { ok: true, schema_version: 1, warnings: [], meta: { request_ref: '1'.repeat(32), source: 'production', time_basis: 'factory_local', snapshot_ref: null, as_of: '2026-10-10T08:00:00' },
    data: { input, target, before: null, after, outsourcing_ref: null, can_confirm: true, write_context: { write_token: 'fixture', capabilities: { confirm: true } },
      execution: { automatically_reported: false, operation_refs: target.operation_refs, service: 'WorkbenchProductionReportService', reason: '回厂仍需报工' } } };
  const outsourcingRejected = await rejection(OutsourcingSession.useCommand, command => command.submit(preview));
  assert.strictEqual(outsourcingRejected.saved, null);
  const outsourcingOutcome = h.render(OutsourcingControls.Editor, { command: outsourcingRejected });
  once(outsourcingOutcome, failure); once(outsourcingOutcome, '上次外协登记没有生效');
  assert(visible(outsourcingOutcome).includes('预检核对'), 'A rejected registration must return to the editable form');
  const outsourcingPending = h.render(OutsourcingControls.Editor, { command: { ...outsourcingRejected, error: null, notice: '',
    saved: { phase: 'pending', target, after, input, request_key: 'outsourcing-' + '1'.repeat(48) } } });
  once(outsourcingPending, WorkbenchTerms.outcomes.pending('外协登记'));
  assert(visible(outsourcingPending).includes('查询结果'));

  // Start with an actual local-storage read failure. Neither domain may send a command until it recovers.
  const failStorage = () => { w.localStorage = Object.assign(h.memoryStorage(), { failGet: new Error('Storage unavailable') }); };
  function storageCommand(useCommand) {
    let command, serverCalls = 0;
    failStorage();
    w.fetch = async () => { serverCalls++; throw new Error('Unexpected network request'); };
    function InitialCommand() { command = useCommand(); return null; }
    h.render(InitialCommand, {});
    assert(command.storageError && !command.saved);
    return { command, calls: () => serverCalls };
  }
  // The page's own storage failure is shown once with its recovery action; refreshing after the storage recovers clears it.
  async function recovery(page, message, inDialog) {
    const tree = page.tree;
    once(tree, message);
    const buttons = h.walk(tree).filter(node => node.type === 'button' && visible(node) === '刷新上次操作记录');
    assert.strictEqual(buttons.length, 1, 'The sole visible error owner must retain its recovery action');
    assert(!buttons[0].props.disabled && !buttons[0].props['aria-disabled']);
    const dialogs = h.walk(tree).filter(node => node.props.role === 'dialog');
    assert.strictEqual(dialogs.length, inDialog ? 1 : 0);
    if (inDialog) assert(h.walk(dialogs[0]).includes(buttons[0]), 'Recovery must be reachable inside the modal');
    w.localStorage = h.memoryStorage();
    click(buttons[0]);
    assert(!visible(await page.settle()).includes(message), 'Refresh must actually retry and clear the storage failure');
  }
  const storageDashboard = storageCommand(DashboardSession.useCommand);
  await storageDashboard.command.submit(item, 'transition', {});
  assert.strictEqual(storageDashboard.calls(), 0);
  const dashboardStorageMessage = storageDashboard.command.storageError.message;
  const storageBoard = await dashboardPage(dashboardFixture(), 'delivery');
  await recovery(storageBoard, dashboardStorageMessage, false);
  storageBoard.unmount();
  const currentItem = { ...item, category: 'delivery', risk: { active: true }, allowed_transitions: ['new', 'following'], navigation: [] };
  // The handling dialog opened from the item detail owns the storage failure while it is open.
  failStorage();
  const modalBoard = await dashboardPage(dashboardFixture(), 'delivery', { tab: 'items', item: currentItem });
  click(button(modalBoard.tree, '登记处置'));
  const dashboardStorageModal = modalBoard.update();
  const blockedHandling = button(dashboardStorageModal, '提交处置');
  assert(blockedHandling && blockedHandling.props.disabled && blockedHandling.props['aria-describedby'], 'Storage failure must keep handling disabled with an accessible explanation');
  await recovery(modalBoard, dashboardStorageMessage, true);
  modalBoard.unmount();
  // A retained open flag during a refresh does not hide the error when no actual modal can be rendered.
  failStorage();
  const refreshingBoard = await dashboardPage(dashboardFixture(), 'delivery', { tab: 'items', item: currentItem });
  click(button(refreshingBoard.tree, '登记处置')); refreshingBoard.update();
  const heldList = h.route.deferred(); boardListAnswers = [() => heldList.promise];
  click(h.walk(refreshingBoard.tree).find(node => node.type === 'button' && node.props['aria-label'] === '刷新值班台'));
  await refreshingBoard.settle();
  await recovery(refreshingBoard, dashboardStorageMessage, false);
  refreshingBoard.unmount(); heldList.resolve(h.route.json({}));

  const storageOutsourcing = storageCommand(OutsourcingSession.useCommand);
  await storageOutsourcing.command.submit(preview);
  assert.strictEqual(storageOutsourcing.calls(), 0);
  const outsourcingStorageMessage = storageOutsourcing.command.storageError.message;
  // Registrations and selectable operations answer at the network; OutsourcingContract and the transport check them.
  const outsourcingPageOf = items => ({ items, page: { number: 1, size: 10, total: items.length, pages: 1 } });
  const targetReads = [];
  h.serve({ 'GET /api/workbench/v1/outsourcing/receipts': () => h.route.envelope(outsourcingPageOf([])),
    'GET /api/workbench/v1/outsourcing/targets': call => { targetReads.push(call.query); return h.route.envelope(outsourcingPageOf([]), { snapshot_ref: 't'.repeat(32) }); } });
  failStorage();
  const outsourcingPage = h.mount(OutsourcingWorkspace, {}); await outsourcingPage.settle();
  await recovery(outsourcingPage, outsourcingStorageMessage, false);
  outsourcingPage.unmount();
  // The registration dialog is open when the browser stops reading the local record (another tab's change arrives).
  const outsourcingModal = h.mount(OutsourcingWorkspace, {});
  click(button(await outsourcingModal.settle(), '新增外协登记'));
  await outsourcingModal.settle();
  failStorage(); w.dispatchEvent({ type: 'storage', key: 'aps_outsourcing_pending_v1' });
  const outsourcingStorageModal = outsourcingModal.update();
  const blockedPreview = button(outsourcingStorageModal, '预检核对');
  assert(blockedPreview && blockedPreview.props.disabled, 'Storage failure must keep registration precheck disabled');
  await recovery(outsourcingModal, outsourcingStorageMessage, true);
  outsourcingModal.unmount();

  // 有查找条件却查不到工序：空态带「清除筛选」，点它清空查找条件，列表按清空后的条件重新读取。
  const picking = { ...outsourcingRejected, error: null, notice: '' };
  const picker = h.mount(OutsourcingControls.Editor, { command: picking });
  h.walk(await picker.settle()).find(node => node.type === 'input' && node.props['aria-label'] === '查找外协工序').props.onChange({ target: { value: '不存在的工序' } });
  const filteredTargets = await picker.settle();
  assert.strictEqual(targetReads.at(-1).query, '不存在的工序');
  once(filteredTargets, '没有匹配的外协工序');
  const clearFilter = button(filteredTargets, '清除筛选');
  assert(clearFilter && !clearFilter.props.disabled && !clearFilter.props['aria-disabled'], 'A filtered empty list must offer an enabled way back');
  const readsBeforeClear = targetReads.length;
  click(clearFilter);
  const unfiltered = await picker.settle();
  assert.strictEqual(targetReads.length - readsBeforeClear, 1, 'The list is read again under the cleared query');
  assert(!Object.hasOwn(targetReads.at(-1), 'query') && targetReads.at(-1).page === '1', 'The cleared query reads the first page without a search term');
  once(unfiltered, '没有可读取的外协工序');
  assert(!button(unfiltered, '清除筛选'));
  picker.unmount();

  // 校准采用、排产采用的本机记录错误交给显示层：kit 错误显示原句，浏览器异常这类程序内部错误只显示兜底句，英文原文不上屏。
  // 弹窗收会话交给它的错误对象；行内提示读真实会话自己的本机记录错误：先是浏览器读不了本机记录，再是刷新记录时拿不到跨页锁。
  w.localStorage = h.memoryStorage();
  const internalStorage = new TypeError("Cannot read properties of undefined (reading 'getItem')"), fallbackCopy = '操作未完成，请核对后重试。';
  const CalibrationAdoptionControls = h.module('CalibrationAdoptionControls.jsx').CalibrationAdoptionControls;
  const CalibrationAdoptionAction = h.module('CalibrationAdoptionAction.jsx').CalibrationAdoptionAction;
  const CalibrationAdoptionState = h.module('CalibrationAdoptionState.js');
  const RunAdoptionControls = h.module('RunAdoptionControls.jsx').RunAdoptionControls;
  const RunAdoptionAction = h.module('RunAdoptionAction.jsx').RunAdoptionAction;
  const RunAdoptionAPI = h.module('RunAdoptionAPI.js');
  const calibrationSession = { saved: null, preview: null, consent: false, busy: false, error: null, notice: '', draft: { reason: '', declared_operator: '' },
    setConsent() {}, change() {}, inspect() {}, submit() {}, finish() {}, lookup() {}, sync() {}, close() {} };
  const runDialogProps = { value: { candidate_ref: h.reference(45) }, intent: null, result: null, preview: null, candidateDisplay: null,
    draft: { reason: '', declared_operator: '' }, consent: false, busy: false, error: null, notice: '', replacedInfo: null,
    onReadStorage() {}, onChange() {}, onConsent() {}, onClose() {}, onPreview() {}, onConfirm() {}, onLookup() {}, onFinish() {},
    onCancelRejected() {}, onDismissReplaced() {}, onNavigate() {} };
  const dialogSurfaces = [
    ['已收到采用结果，但本机没能保存这次操作记录。', storageError => h.render(CalibrationAdoptionControls.Dialog, { session: { ...calibrationSession, storageError }, detail: null, stale: false, onRefresh() {} })],
    ['存不下采用的操作记录，没有开始新的采用。请重新打开页面。', storageError => h.render(RunAdoptionControls.Dialog, { ...runDialogProps, storageError })]];
  for (const [storageText, surface] of dialogSurfaces) {
    once(surface(kit.failure(storageText)), storageText);
    const internalTree = surface(internalStorage);
    once(internalTree, fallbackCopy);
    assert(!visible(internalTree).includes(internalStorage.message), 'An internal storage error never shows its English text');
  }
  const refusedRead = Object.assign(h.memoryStorage(), { failGet: new DOMException('The operation is insecure.', 'SecurityError') });
  const locks = w.navigator, refusedLock = 'The request is not allowed by the user agent.';
  for (const [Action, props, readRecord] of [[CalibrationAdoptionAction, { detail: null, stale: false, onRefresh() {} }, CalibrationAdoptionState.read],
    [RunAdoptionAction, { candidateRef: h.reference(46), candidateCatalog: [] }, RunAdoptionAPI.pending.read]]) {
    w.localStorage = refusedRead;
    const readFailure = (() => { try { readRecord(); } catch (error) { return error; } })();
    assert(kit.isFailure(readFailure), 'The adoption store reports an unreadable record with its own copy');
    const action = h.mount(Action, props);
    once(await action.settle(), readFailure.message);
    w.localStorage = h.memoryStorage();
    w.navigator = { locks: { request: async () => { throw new DOMException(refusedLock, 'NotAllowedError'); } } };
    click(button(action.tree, '刷新上次操作记录'));
    const internalTree = await action.settle();
    once(internalTree, fallbackCopy);
    assert(!visible(internalTree).includes(refusedLock), 'An internal storage error never shows its English text');
    action.unmount(); w.navigator = locks;
  }
  return { notice_checks: checked };
}

const repoRoot = path.join(__dirname, '../..');
const result = spawnNodeSync([path.join(__dirname, '../_support/gantt_current_runtime.cjs')], {
  cwd: repoRoot, timeout: 30000,
  input: JSON.stringify({ root: repoRoot, program: `return (${contract.toString()})(h, assert);` })
}, 'Notice ownership contract');
console.log(result.stdout);
