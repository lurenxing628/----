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

  const fields = w.FieldEditorFields;
  w.FieldEditorFields = () => null; // This regression concerns the form/footer ownership, not the field inputs.
  const task = { task_ref: h.reference(1), plan_ref: h.reference(2), operation_ref: h.reference(3), execution: { reports: [], write_context: null } };
  const retained = { baseline: { task_ref: h.reference(4), plan_ref: task.plan_ref, report_ref: null, revision_ref: null, legacy_ref: null },
    draft: w.FieldContract.draft(null), initialDraft: w.FieldContract.draft(null), suggestions: {} };
  once(h.render(w.FieldEditor, { task, retained, action: 'create', adapter: {}, command: idle }), '原记录或任务已变化，暂存内容未写入；请取消后重新核对。', 2);
  w.FieldEditorFields = fields;
  const day = { date: '2026-10-10', explicit: false, fields: { type: 'work', hours: 8, eff: 100, allowNormal: 'yes', allowUrgent: 'yes', note: '', periods: null },
    effective: { is_working: true, window_start: '2026-10-10T08:00:00', window_end: '2026-10-10T16:00:00', periods: null } };
  once(h.render(w.CalendarDayDialog, { adapter: {}, day, source: 'production', command: idle }), missingContext, 1);
  once(h.render(w.ProcessGroupEditor, { adapter: { command() {}, stagePreview() {} }, command: idle,
    result: { data: { operations: [], external_groups: [], workflow: { route: { state: 'confirmed' } }, capabilities: { stage_confirm: true } }, meta: { source: 'production' } }
  }), '请先新增、修改或解除外协段。', 2);

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

  const dashboardRead = w.DashboardSession.useRead, dashboardCommand = w.DashboardSession.useCommand;
  w.DashboardSession.useCommand = () => ({ busy: false, saved: null, storageError: null });
  w.DashboardSession.useRead = (_load, _deps, enabled = true) => ({ result: null, loading: false, error: enabled ? new Error('值班台读取失败，请刷新重试。') : null });
  once(h.render(w.WorkbenchDashboardWorkspace, {}), '值班台读取失败，请刷新重试。');
  w.DashboardSession.useRead = dashboardRead; w.DashboardSession.useCommand = dashboardCommand;
  const calibrationRead = w.CalibrationControls.useRead, adoption = w.CalibrationAdoptionAction, stale = w.WorkbenchTerms.outcomes.stale;
  w.CalibrationControls.useRead = () => ({ result: null, busy: false, error: null });
  w.CalibrationAdoptionAction = () => null;
  const staleTree = h.render(w.CalibrationWorkspace, {}, { Workspace: { 3: h.reference(1), 7: new Error(stale), 9: true } });
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
  const staleCommand = await resourceCommand({ command: async () => staleResult },
    command => command.submit('calendar', 'upsert', day.date, { write_token: 'fixture' }, { date: day.date }));
  assert.strictEqual(staleCommand.phase, 'rejected');
  const staleCalendar = h.render(w.CalendarDayDialog, { adapter: {}, day, source: 'production', command: staleCommand });
  once(staleCalendar, stale, 1);
  assert(visible(staleCalendar).includes(w.WorkbenchTerms.refresh_latest), 'A stale calendar must retain its refresh action');

  const resourceRead = w.APSResourceSession.useQuery, resourceUseCommand = w.APSResourceSession.useCommand;
  w.APSResourceSession.useQuery = () => ({ result: null, loading: false, error: null });
  w.APSResourceSession.useCommand = () => staleCommand;
  const editor = { action: 'create', base: null, ref: null, draft: w.APSResourceCatalogModel.draft(null),
    context: { write_token: 'fixture', capabilities: { create: true } }, source: 'production' };
  const staleCatalog = h.render(w.ResourceCatalog, { kind: 'machine_group', adapter: {} }, { ResourceCatalog: { 1: editor, 6: true } });
  once(staleCatalog, stale, 1);
  assert(visible(staleCatalog).includes(w.WorkbenchTerms.refresh_latest), 'A stale catalog must retain its refresh action');
  w.APSResourceSession.useCommand = resourceUseCommand;
  const restored = await resourceCommand({ readPending: () => ({ kind: 'machine_group', action: 'create', request_key: 'resource-' + '1'.repeat(48), input: {} }) });
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
  const externalIssue = { code: 'outsourcing_unavailable', message: '真实外协登记结构尚未完整接入；未补表或改动原资料。' };
  const candidateIssue = { code: 'run_schema_unavailable', message: '排产记录结构不完整，请联系维护人员。' };
  const summary = (state = 'no_data', issues = []) => ({ state, risk_count: ['unavailable', 'not_connected'].includes(state) ? null : 0,
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
        resource_pressure: { state: 'unavailable', resources: null, issues: [] },
        candidate_catalog: { state: 'no_data', selection: null, run_count: 0, runs: [], issues: [], page: { has_more: false } }, analysis_error: null,
        analysis: { plan: null, state: 'unavailable', time_scope: null, tasks: [], resources: [], downtimes: [], overlaps: [], deliveries: [], execution: [],
          issues: [planIssue], as_of: asOf, capabilities: { view: true, adopt: false }, basis: 'current_official_plan_and_readiness_sources',
          pending: { state: 'unavailable', count: null, known_count: 0, items: [], issues: [materialIssue], basis: 'stored_pending_batch_pool' },
          pressure: { count: null, known_count: 0, resource_count: 0, threshold: 0.9, unknown_resources: 0, zero_capacity_resources: 0,
            basis: 'same_range_daily_peak_available_occupancy' } } } };
  }
  async function dashboardResult(payload, category) {
    const q = w.DashboardContract.scope({ category }), scope = { kind: 'dashboard', ...q }; delete scope.page;
    payload.data.scope = scope;
    const result = await w.DashboardContract.create(async () => ({ ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => payload })).list(q);
    assert.strictEqual(result.data.analysis_error, null, 'The representative analysis DTO must pass the actual API contract');
    return result;
  }
  function dashboardTree(result, category, command = { busy: false, saved: null, storageError: null }, states = {}, detail = null) {
    let readIndex = 0;
    w.DashboardSession.useCommand = () => command;
    w.DashboardSession.useRead = () => ({ result: ++readIndex === 1 ? result : readIndex === 2 ? detail : null, loading: false, error: null });
    return h.render(w.WorkbenchDashboardWorkspace, { initialContext: { scope: { category }, tab: 'analysis', ...(detail ? { item_ref: detail.data.item.item_ref } : {}) } }, states);
  }
  const unavailable = dashboardFixture();
  // Run schema and outsourcing schema failures remain separate even when the formal-plan source fails.
  Object.assign(unavailable.data.categories.external, summary('unavailable', [externalIssue]), { handling_supported: false,
    ...Object.fromEntries(['receipt_count', 'current_receipt_count', 'awaiting_return_count', 'overdue_count', 'returned_count',
      'awaiting_confirmation_count', 'unregistered_count', 'source_gap_count'].map(key => [key, null])),
    entry: { view: 'outsourcing', target: '/api/workbench/v1/outsourcing/receipts', enabled: false } });
  unavailable.data.categories.candidate = summary('unavailable', [candidateIssue]);
  unavailable.data.candidate_catalog = { state: 'unavailable', runs: [], page: null, run_count: null, issues: [candidateIssue] };
  const unavailableTree = dashboardTree(await dashboardResult(unavailable, 'all'), 'all');
  for (const issue of [planIssue, materialIssue, externalIssue, candidateIssue]) once(unavailableTree, issue.message);
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
  const gap = { source_ref: h.reference(21), subject: 'DB1 · Turning', code: 'downtime_unknown', message: '停机记录或设备资料填得不对，还判断不了。' };
  Object.assign(d.categories.downtime, { risk_count: null, unknown_count: 1, evaluation_gaps: [gap] });
  d.plan = plan; Object.assign(a, { plan, state: 'available', time_scope: timeScope, issues: [pressureIssue, analysisIssue] });
  const analysisTask = { plan_ref: plan.plan_ref, task_ref: gap.source_ref, operation_ref: h.reference(22), batch_ref: h.reference(23),
    batch_id: 'DB1', process_label: 'Turning', source: 'internal', machine_ref: h.reference(24),
    start: timeScope.range_start, end: timeScope.range_end, span_hours: 2 };
  a.tasks = [analysisTask];
  a.resources = [{ resource_ref: analysisTask.machine_ref, label: 'Lathe', kind: 'machine', state: 'unavailable',
    peak_utilization: null, unknown_days: 1, zero_capacity_days: 0, task_refs: [analysisTask.task_ref],
    days: [{ date: '2026-10-09', start: timeScope.range_start, end: timeScope.range_end, occupied_hours: 2, overlap_hours: 0,
      available_hours: null, inside_available_hours: null, outside_available_hours: null, utilization: null }] }];
  a.downtimes = [{ downtime_ref: h.reference(25), machine_ref: analysisTask.machine_ref, start: '2026-10-09T09:00:00', end: '2026-10-09T09:00:00',
    recorded_at: '2026-10-09T07:00:00', recorded_at_basis: 'local_time', valid: false }];
  a.pressure.resource_count = 1; a.pressure.unknown_resources = 1;
  a.pending = { state: 'available', count: 0, known_count: 0, items: [], issues: [], basis: 'stored_pending_batch_pool' };
  d.resource_pressure = { state: 'partial', plan_ref: plan.plan_ref, time_scope: timeScope, issues: [pressureIssue], resources: [{
    resource_ref: analysisTask.machine_ref, label: 'Lathe', kind: 'machine', operation_count: 1, arranged_hours: 2, occupied_hours: 2,
    available_hours: null, available_occupied_hours: null, overlap_hours: 0, outside_available_hours: null, utilization: null,
    capacity_shortfall_hours: null, capacity_insufficient: null, has_overlap: false, segments: [], issues: [resourceIssue] }] };
  const independentTree = dashboardTree(await dashboardResult(independent, 'all'), 'all');
  for (const issue of [pressureIssue, analysisIssue, resourceIssue]) once(independentTree, issue.message);
  const evidence = h.walk(independentTree).find(node => node.props['data-gap-source'] === gap.source_ref);
  assert(evidence && h.text(evidence).includes(gap.subject), 'Analysis ownership must retain category evaluation-gap evidence');
  once(h.render(w.DashboardPanels.Pressure, { data: d, canNavigate: true }), pressureIssue.message);

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
