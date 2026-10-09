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
  return { notice_checks: checked };
}

const result = spawnSync(process.execPath, [path.join(__dirname, '../_support/gantt_current_runtime.cjs')], {
  cwd: path.join(__dirname, '../..'), encoding: 'utf8', timeout: 30000,
  input: JSON.stringify({ root: path.join(__dirname, '../..'), program: `return (${contract.toString()})(h, assert);` })
});
assert.strictEqual(result.status, 0, result.stdout + result.stderr);
console.log(result.stdout);
