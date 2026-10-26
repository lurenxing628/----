'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const files = ['resource-contract.js', 'resource-session.js', 'BatchContract.js', 'BatchTable.jsx', 'BatchWorkspace.jsx'];
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })) });
const clone = value => JSON.parse(JSON.stringify(value));
const batchRef = 'a'.repeat(48), operationRef = 'b'.repeat(48), partRef = 'c'.repeat(48);
const scope = { page: 1, size: 20, sort: 'business_code', direction: 'asc', column_filters: {} };
const writeContext = { write_token: 'latest-batch', capabilities: { 'batch.delete': true, 'batch.bulk_confirm': true }, blocked_reasons: [] };
const full = { ref: batchRef, business_code: 'B001', label: '试件', status: 'pending',
  fields: { quantity: 10, due_date: null, priority: 'normal', ready_status: 'yes', ready_date: null, remark: null },
  relationships: { part_ref: partRef, part_no: 'P001', part_name: '试件', operation_count: 1, completed_count: 0, gap_count: 0,
    plan_reference_count: 0, execution_reference_count: 0, material_requirement_count: 0 },
  operations: [{ ref: operationRef, operation_ref: operationRef, business_code: '10', label: '车削', sequence: 10, source: 'internal', status: 'pending', completed: false,
    setup_hours: 1, unit_hours: 0.2, external_days: null, machine_ref: null, operator_ref: null, supplier_ref: null, op_type_ref: null,
    resources: {}, external_group: null, issues: [], editable: true }],
  all_operations_complete: false, protected: false, issues: [], write_context: writeContext,
  materials: { requirements: [] }, template: { complete: true, operation_count: 1, diagnostics: [] } };
const summary = clone(full); delete summary.operations; delete summary.materials; delete summary.template;
const envelope = data => ({ ok: true, schema_version: 1, data, warnings: [],
  meta: { request_ref: 'request', snapshot_ref: 'snapshot', source: 'production', time_basis: 'factory_local', as_of: '2026-10-18T02:00:00' } });
const listPayload = row => envelope({ entities: [row], create_context: clone(writeContext),
  page: { number: 1, size: 20, total: 1, pages: 1, sort: [{ field: 'business_code', direction: 'asc' }] } });
function hooks() {
  let cursor = 0; const slots = [], effects = [];
  const same = (a, b) => a && b && a.length === b.length && a.every((value, index) => value === b[index]);
  const useMemo = (fn, deps) => { const index = cursor++; if (!slots[index] || !same(slots[index].deps, deps)) slots[index] = { deps, value: fn() }; return slots[index].value; };
  const useEffect = (fn, deps) => { const index = cursor++, old = slots[index]; if (!old || !same(old.deps, deps)) {
    slots[index] = { deps, cleanup: old && old.cleanup }; effects.push(() => { if (slots[index].cleanup) slots[index].cleanup(); slots[index].cleanup = fn(); });
  } };
  return { React: { createElement: (type, props, ...children) => ({ type, props: { ...props, children } }), Fragment: 'fragment',
    useRef(value) { const index = cursor++; if (!slots[index]) slots[index] = { current: value }; return slots[index]; },
    useState(value) { const index = cursor++; if (!slots[index]) slots[index] = { value: typeof value === 'function' ? value() : value };
      return [slots[index].value, update => { slots[index].value = typeof update === 'function' ? update(slots[index].value) : update; }]; },
    useMemo, useCallback: (fn, deps) => useMemo(() => fn, deps), useEffect, useLayoutEffect: useEffect },
    render(fn) { cursor = 0; return fn(); }, flush() { while (effects.length) effects.shift()(); },
    unmount() { effects.length = 0; slots.forEach(slot => { if (slot.cleanup) { slot.cleanup(); slot.cleanup = null; } }); } };
}
function environment() {
  const h = hooks(), window = { ResourceControls: { Button: 'button', Modal: 'modal', ErrorBox: 'error-box', Icon: 'icon' }, BatchControls: { Field: 'field' },
    WorkbenchFormat: { number: String, date: value => value || '未填写' }, WorkbenchControls: { EmptyState: 'empty', Pager: 'pager' },
    WorkbenchTerms: { outcomes: { unavailable: '暂不可用' } }, WorkbenchGuards: { useDirtyGuard: () => ({}) }, WorkbenchPageContext: { useSnapshot() {} } };
  const context = vm.createContext({ window, React: h.React, AbortController, DOMException });
  built.outputs.forEach(file => vm.runInContext(file.code, context, { filename: file.path }));
  return { h, window, context };
}
function nodes(node) {
  if (!node || typeof node !== 'object') return [];
  return [node, ...(node.props.children || []).flat(Infinity).flatMap(nodes)];
}
const find = (node, type, match = () => true) => nodes(node).find(item => item.type === type && match(item.props));
function text(node) {
  if (Array.isArray(node)) return node.map(text).join('');
  return node && typeof node === 'object' ? text(node.props.children) : node == null || node === false ? '' : String(node);
}
const turns = async () => { for (let index = 0; index < 8; index++) await Promise.resolve(); };
function overview(adapter, initialRow = summary) {
  const env = environment();
  const table = env.h.render(() => env.window.BatchTable({ adapter, rows: [initialRow], scope, selected: [], setSelected() {} }));
  const child = nodes(table).find(node => typeof node.type === 'function' && node.type.name === 'OperationOverview');
  assert.ok(child, 'Every batch row owns its operation overview'); assert.equal(child.props.adapter, adapter);
  env.h.unmount(); const h = hooks(); env.context.React = h.React;
  let row = initialRow, node;
  const render = () => { node = h.render(() => child.type({ adapter, row })); return node; };
  return { ...env, h, render, flush: () => h.flush(), setRow(value) { row = value; },
    toggle(open) { node.props.onToggle({ currentTarget: { open } }); return render(); } };
}
async function calendarRefreshContracts() {
  const outputs = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
    sources: ['OperatorCalendarPanel.jsx', 'ResourceWorkspace.jsx', 'ResourceCalendar.jsx', 'ResourceLive.jsx']
      .map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })) }).outputs;
  function calendarEnvironment() {
    const env = environment(), w = env.window;
    Object.assign(w.ResourceControls, { Issues: 'issues', Field: 'field' });
    Object.assign(w.WorkbenchFormat, { dateTime: String });
    Object.assign(w.WorkbenchTerms, { personal_calendar: '个人日历', data_as_of: value => value });
    Object.assign(w.WorkbenchGuards, { confirmLeave: async () => true });
    Object.assign(w, { ResourceForms: { Feedback: 'feedback' }, ResourceTables: {}, ResourceRail: 'resource-rail',
      CalendarFields: { RefreshResult: 'calendar-refresh', Policy: 'calendar-policy' }, WorkPeriodFields: 'period-fields',
      CalendarDayDialog: 'calendar-day-dialog', CalendarFileActions: 'calendar-file-actions',
      APSOperatorCalendar: { month: value => value, draftOf: day => day.fields, tag: () => ({ tone: 'rest', text: '休息' }),
        input: value => value, rangeInput: value => value, rangePreview: value => value },
      APSCalendarContract: { path: 'calendar', month: value => value, tag: () => ({ tone: 'rest', text: '休息' }) } });
    outputs.forEach(output => vm.runInContext(output.code, env.context, { filename: output.path }));
    env.context.ResourceWorkspace = w.ResourceWorkspace;
    return env;
  }
  const stamp = month => String(month.year).padStart(4, '0') + '-' + String(month.month).padStart(2, '0') + '-01';
  function monthPayload(month, note = 'old', explicit = true) {
    const day = { date: stamp(month), day: 1, calendar_ref: explicit ? note : null, explicit, note,
      fields: { type: 'rest', periods: [], eff: '100', note } };
    return { data: { ...month, days: [day], cells: [day], as_of: '2026-10-20T09:00:00',
      stats: { configured: explicit ? 1 : 0, work_days: 0, weekend_rest: 1, overrides: 0 }, previous_month: null, next_month: null,
      write_context: { write_token: 'current', capabilities: { 'operator.calendar_upsert': true, 'operator.calendar_delete': true, 'operator.calendar_range_clear': true }, blocked_reasons: [] } },
      meta: { source: 'production' }, warnings: [] };
  }
  for (const action of ['calendar_upsert', 'calendar_delete', 'calendar_range_clear']) {
    const env = calendarEnvironment(), w = env.window, requests = [], submissions = [];
    let parentRetries = 0;
    const command = { phase: 'idle', locked: false, reset: () => true, clearRejection: () => false, submit: (...args) => submissions.push(args) };
    const props = { entity: { ref: batchRef, business_code: 'OP-1' }, source: 'production', command,
      onClose() {}, onRefresh: () => { parentRetries++; }, refreshState: {}, Feedback: 'feedback', adapter: {
        query(path, month, signal) {
          if (!requests.length) { requests.push({ path, month, signal }); return Promise.resolve(monthPayload(month)); }
          return new Promise((resolve, reject) => requests.push({ path, month, signal, resolve, reject }));
        },
        async preview(path, body) { return { data: { count: 1, days: [{ date: body.input.start_date }], range: body.input, write_context: {} } }; }
      } };
    let tree;
    const render = () => { tree = env.h.render(() => w.OperatorCalendarPanel(props)); env.h.flush(); return tree; };
    const settle = async () => { for (let index = 0; index < 3; index++) { render(); await turns(); } return render(); };
    const editor = () => nodes(tree).find(node => typeof node.type === 'function' && ['DayEditor', 'RangeClear'].includes(node.type.name));
    const refresh = () => nodes(tree).find(node => typeof node.type === 'function' && node.type.name === 'RefreshResult');
    await settle();
    if (action === 'calendar_range_clear') {
      await find(tree, 'button', props => text(props.children) === '按日期范围清除').props.onClick(); render();
      await editor().props.onPreview(); render(); editor().props.onConfirm();
    } else {
      await nodes(tree).find(node => node.props['data-operator-calendar-date']).props.onClick(); render();
      if (action === 'calendar_delete') { editor().props.onClearing(true); render(); editor().props.onClear(); }
      else { editor().props.setDraft({ ...editor().props.draft, note: 'saved' }); render(); editor().props.onSave(); }
    }
    assert.equal(submissions.length, 1); assert.equal(submissions[0][1], action);
    command.phase = 'done'; command.result = { receipt_ref: action }; props.refreshState = { done: true };
    await settle();
    assert.equal(requests.length, 2, 'A terminal receipt invalidates the personal month exactly once: ' + action);
    assert.equal(refresh().props.state.done, false, 'Parent success cannot announce a still-loading month');
    assert.equal(editor().props.disabled, true); assert(find(tree, 'feedback'));
    if (action === 'calendar_delete') assert.equal(editor().props.clearing, true);
    props.refreshState = { error: new Error('parent failed') }; render();
    refresh().props.onRefresh(); await settle();
    assert.equal(parentRetries, 1); assert.equal(requests.length, 2); assert.equal(requests[1].signal.aborted, false,
      'Retrying the failed parent never aborts a month still in flight');
    props.refreshState = { done: true }; requests[1].reject(new Error('month failed')); await settle();
    assert(editor(), 'A failed automatic read preserves the completed editor and receipt');
    assert.equal(editor().props.disabled, true); assert.equal(refresh().props.state.done, false);
    if (action === 'calendar_range_clear') { assert.equal(editor().props.preview.data.count, 1); assert.equal(editor().props.reason, ''); }
    else { assert.equal(editor().props.saveReason, ''); assert.equal(editor().props.clearReason, ''); }
    refresh().props.onRefresh(); await settle();
    assert.equal(parentRetries, 1); assert.equal(requests.length, 3, 'Only the failed local month is retried');
    requests[2].resolve(monthPayload(requests[2].month, 'fresh', action !== 'calendar_delete')); await settle();
    assert.equal(refresh().props.state.done, true);
    if (action === 'calendar_delete') assert.equal(editor().props.clearing, true, 'Successful deletion keeps the frozen clearing confirmation');
    assert(!text(tree).includes('这一天已被修改'), 'Completed drafts never show the unsaved-stale warning');
    render(); await turns(); assert.equal(requests.length, 3); env.h.unmount();
  }
  for (const restored of [false, true]) {
    const env = calendarEnvironment(), w = env.window, host = env.h, workspace = hooks(), calendar = hooks();
    const idle = { phase: 'idle', locked: false, reset: () => true }, calendarCommand = { ...idle };
    let pending = restored ? { kind: 'work_calendar_import', action: 'confirm', request_key: 'old-import' } : null;
    let months = 0, summaries = 0, note = 'old', rootTree, calendarTree, calendarProps;
    const rawQuery = w.APSResourceSession.useQuery;
    w.APSResourceSession.useCommand = adapter => adapter.family === 'calendar' ? calendarCommand : idle;
    w.APSResourceSession.useSummary = (adapter, revision, enabled = true) => rawQuery(signal => adapter.summary(signal), [adapter, revision], enabled);
    w.APSResourceSession.useCounts = (adapter, revision) => ({ summary: rawQuery(signal => adapter.summary(signal), [adapter, revision]) });
    w.APSResourceAPI = { create(family) { return { family,
      readPending: () => family === 'work_calendar_files' ? pending : null,
      async summary() { summaries++; return { data: {} }; },
      async query(path, month) { months++; return monthPayload(month, note); }
    }; } };
    w.APSProcessAPI = { create: () => ({ readPending: () => null }) };
    const now = new Date(), month = { year: now.getFullYear(), month: now.getMonth() + 1 };
    const props = { initialContext: restored ? undefined : { source: 'production', kind: 'calendar', month: stamp(month).slice(0, 7) } };
    function render() {
      env.context.React = host.React; rootTree = host.render(() => w.ResourceLive(props)); host.flush();
      const parent = find(rootTree, w.ResourceWorkspace);
      env.context.React = workspace.React;
      const parentTree = workspace.render(() => w.ResourceWorkspace(parent.props)); workspace.flush();
      calendarProps = find(parentTree, w.ResourceCalendar).props;
      env.context.React = calendar.React;
      calendarTree = calendar.render(() => w.ResourceCalendar(calendarProps)); calendar.flush();
    }
    const settle = async () => { for (let index = 0; index < 4; index++) { render(); await turns(); } render(); };
    await settle(); assert.equal(months, 1); assert.equal(summaries, 1);
    if (!restored) {
      for (const mode of ['export', 'import']) {
        calendarProps.onOpenFile(mode, { source: 'production', month }); await settle();
        const file = find(rootTree, 'calendar-file-actions'); assert.equal(file.props.request.onCommitted, undefined,
          'Calendar files use the host revision, never a second local callback');
        file.props.onClose(); await settle(); assert.equal(months, 1); assert.equal(summaries, 1, 'Cancelling or exporting never invalidates saved facts');
      }
      calendarProps.onOpenFile('import', { source: 'production', month }); await settle();
    }
    const file = find(rootTree, 'calendar-file-actions'); assert(file, 'A normal or restored import is owned by the shared host');
    pending = null; note = 'imported';
    file.props.onCommitted({ result: 'committed', receipt_ref: 'import-receipt' }); await settle();
    assert.equal(months, 2); assert.equal(summaries, 2, 'Each import refreshes the month and shared summary once');
    assert.equal(calendarProps.externalRevision, 1);
    nodes(calendarTree).find(node => node.props['data-calendar-date']).props.onClick(); await settle();
    const dayDialog = find(calendarTree, 'calendar-day-dialog'); assert.equal(dayDialog.props.day.note, 'imported',
      'A newly opened day editor starts from the imported month');
    dayDialog.props.onClose(); await settle();
    calendarCommand.phase = 'done'; calendarCommand.result = { receipt_ref: 'own-calendar-command' };
    await settle(); assert.equal(months, 3); assert.equal(summaries, 3,
      'A calendar-owned command reloads once; parent internal revision is not a second month invalidation');
    calendar.unmount(); workspace.unmount(); host.unmount();
  }
}
async function main() {
  const env = environment(), B = env.window.APSBatchContract;
  assert.equal(B.summary(summary), true); assert.equal(B.entity(summary), false);
  assert.equal(B.entity(full), true); assert.equal(B.summary(full), false);
  assert.equal(B.summary({ ...summary, operations: [] }), false, 'A summary never pretends to carry complete operations');
  assert.equal(B.entity({ ...summary, operations: [] }), false);
  for (const patch of [{ completed_count: 2 }, { gap_count: 2 }, { operation_count: -1 }])
    assert.equal(B.summary({ ...summary, relationships: { ...summary.relationships, ...patch } }), false);
  assert.equal(B.summary({ ...summary, all_operations_complete: true }), false);
  const completed = { ...summary, relationships: { ...summary.relationships, completed_count: 1 }, all_operations_complete: true };
  assert.equal(B.summary(completed), true); assert.equal(B.summary({ ...completed, all_operations_complete: false }), false);
  const zero = { ...summary, relationships: { ...summary.relationships, operation_count: 0 } };
  assert.equal(B.summary(zero), true); assert.equal(B.summary({ ...zero, all_operations_complete: true }), false);
  assert.equal(B.summary({ ...summary, protected: undefined }), false); assert.equal(B.summary({ ...summary, write_context: {} }), false);
  assert.equal(B.list(listPayload(summary), scope).data.entities[0], summary);
  assert.throws(() => B.list(listPayload(full), scope), /批次列表不完整/);
  assert.throws(() => B.list(listPayload(summary), { ...scope, snapshot_ref: 'different' }), /批次列表不完整/);
  assert.equal(B.detail(envelope(full), batchRef).data, full);
  assert.throws(() => B.detail(envelope(summary), batchRef), /批次详情不完整/);
  assert.throws(() => B.detail(envelope(full), 'd'.repeat(48)), /不是这个批次/);
  assert.equal(B.entity({ ...full, relationships: { ...full.relationships, operation_count: 2 }, operations: [full.operations[0], full.operations[0]] }), false);
  assert.equal(B.entity({ ...full, operations: [{ ...full.operations[0], completed: true }] }), false);
  const preview = envelope({ operation: 'batch.bulk_confirm', preview_ref: 'p'.repeat(32), write_context: clone(writeContext), commit_policy: 'atomic',
    action: 'delete', count: 1, rows: [{ entity_ref: batchRef, before: full, after: null }] });
  assert.equal(B.preview(preview, 'bulk', null, { refs: [batchRef], action: 'delete' }).count, 1);
  const incompletePreview = clone(preview); incompletePreview.data.rows[0].before = summary;
  assert.throws(() => B.preview(incompletePreview, 'bulk', null, { refs: [batchRef], action: 'delete' }), /预检结果/);

  // The workspace passes the same reader into list rows; its detail route stays separate.
  const workspace = environment(), adapter = {};
  workspace.window.APSResourceSession.useCommand = () => ({ phase: 'idle', locked: false });
  workspace.window.APSResourceSession.useQuery = () => ({ result: listPayload(summary), loading: false, error: null });
  const workspaceNode = workspace.h.render(() => workspace.window.BatchWorkspace({ adapter, initialContext: {} }));
  assert.equal(find(workspaceNode, workspace.window.BatchTable).props.adapter, adapter);
  const links = [], bulkPatches = [], nextWorkspace = environment(), hiddenRef = 'd'.repeat(48);
  nextWorkspace.window.APSResourceSession.useCommand = () => ({ phase: 'idle', locked: false, reset: () => true });
  nextWorkspace.window.APSResourceSession.useQuery = () => ({ result: listPayload(summary), loading: false, error: null });
  nextWorkspace.window.WorkbenchGuards.confirmLeave = async () => true;
  nextWorkspace.window.BatchForms = { Preview: 'batch-preview' };
  const nextProps = { adapter: { async preview(action, entityRef, input) {
    bulkPatches.push(input.patch);
    return envelope({ operation: 'batch.bulk_confirm', preview_ref: 'p'.repeat(32), write_context: clone(writeContext),
      commit_policy: 'atomic', action: input.action, count: input.refs.length,
      rows: input.refs.map(ref => ({ entity_ref: ref, before: { ...full, ref }, after: { ...full, ref } })) });
  } }, onNav: (...args) => links.push(args), initialContext: {} };
  let nextTree = nextWorkspace.h.render(() => nextWorkspace.window.BatchWorkspace(nextProps));
  find(nextTree, nextWorkspace.window.BatchTable).props.setSelected([batchRef, hiddenRef]);
  nextTree = nextWorkspace.h.render(() => nextWorkspace.window.BatchWorkspace(nextProps));
  find(nextTree, 'button', props => text(props.children) === '下一步 · 去排产').props.onClick();
  assert.deepEqual(clone(links.at(-1)), ['run', { scope: { source: 'production', batch_refs: [batchRef, hiddenRef] } }],
    'The next step carries the complete cross-page selection');
  const bulkModal = tree => find(tree, 'modal', props => props.title === '批量修改批次');
  const remarkInput = tree => find(find(tree, 'field', props => props.label === '批量备注'), 'input');
  for (const dismiss of [tree => bulkModal(tree).props.onClose(),
    tree => find(bulkModal(tree).props.footer, 'button', props => text(props.children) === '取消').props.onClick()]) {
    find(nextTree, 'button', props => text(props.children) === '批量修改').props.onClick();
    nextTree = nextWorkspace.h.render(() => nextWorkspace.window.BatchWorkspace(nextProps));
    assert.equal(remarkInput(nextTree).props.value, '');
    remarkInput(nextTree).props.onChange({ target: { value: 'PHASE6A-Bulk-X-应放弃' } });
    nextTree = nextWorkspace.h.render(() => nextWorkspace.window.BatchWorkspace(nextProps));
    assert.equal(remarkInput(nextTree).props.value, 'PHASE6A-Bulk-X-应放弃');
    await dismiss(nextTree);
    nextTree = nextWorkspace.h.render(() => nextWorkspace.window.BatchWorkspace(nextProps));
    assert.equal(bulkModal(nextTree), undefined);
  }
  find(nextTree, 'button', props => text(props.children) === '批量修改').props.onClick();
  nextTree = nextWorkspace.h.render(() => nextWorkspace.window.BatchWorkspace(nextProps));
  assert.equal(remarkInput(nextTree).props.value, '');
  await find(bulkModal(nextTree).props.footer, 'button', props => text(props.children) === '预览变更').props.onClick();
  assert.deepEqual(clone(bulkPatches), [{}]);
  nextTree = nextWorkspace.h.render(() => nextWorkspace.window.BatchWorkspace(nextProps));
  find(nextTree, 'batch-preview').props.onClose();
  nextTree = nextWorkspace.h.render(() => nextWorkspace.window.BatchWorkspace(nextProps));
  find(nextTree, nextWorkspace.window.BatchTable).props.setSelected([]);
  nextTree = nextWorkspace.h.render(() => nextWorkspace.window.BatchWorkspace(nextProps));
  find(nextTree, 'button', props => text(props.children) === '下一步 · 去排产').props.onClick();
  assert.deepEqual(clone(links.at(-1)), ['run', {}], 'An unselected next step opens a fresh form rather than resuming an old run result');
  nextWorkspace.h.unmount();
  for (const returnTarget of ['run', 'dashboard', { view: 'dashboard', context: { tab: 'analysis' } }]) {
    const returning = environment();
    returning.window.APSResourceSession.useCommand = () => ({ phase: 'idle', locked: false });
    returning.window.APSResourceSession.useQuery = () => ({ result: listPayload(summary), loading: false, error: null });
    const returnProps = { adapter, initialContext: { return_to: returnTarget }, onNav: (...args) => links.push(args) };
    let returned = returning.h.render(() => returning.window.BatchWorkspace(returnProps));
    find(returned, returning.window.BatchTable).props.setSelected([hiddenRef]);
    returned = returning.h.render(() => returning.window.BatchWorkspace(returnProps));
    find(returned, 'button', props => ['返回排产', '返回值班台'].includes(text(props.children))).props.onClick();
    assert.deepEqual(clone(links.at(-1)), typeof returnTarget === 'string' ? [returnTarget] : [returnTarget.view, returnTarget.context],
      'Returning to a source preserves its original navigation protocol'); returning.h.unmount();
  }

  const requests = [], reader = { detail(kind, ref, signal) { return new Promise((resolve, reject) => requests.push({ kind, ref, signal, resolve, reject })); } };
  const ui = overview(reader);
  ui.render(); ui.flush(); await turns(); assert.equal(requests.length, 0, 'Collapsed rows do not request details');
  ui.toggle(true); ui.flush(); await turns(); assert.match(text(ui.render()), /正在读取工序/);
  assert.equal(requests.length, 1); assert.equal(requests[0].kind, 'batch'); assert.equal(requests[0].ref, batchRef);
  assert.equal(requests[0].signal.aborted, false);
  requests[0].resolve(envelope(clone(full))); await turns(); assert.match(text(ui.render()), /10 · 车削/);
  ui.toggle(false); ui.flush(); ui.toggle(true); ui.flush(); await turns();
  assert.equal(requests.length, 1, 'Reopening the same successful row reuses its detail');
  ui.setRow(clone(summary));
  assert.doesNotMatch(text(ui.render()), /10 · 车削/); ui.flush(); await turns(); assert.equal(requests.length, 2, 'A refreshed row invalidates detail even when its ref is unchanged');
  ui.toggle(false); ui.flush(); assert.equal(requests[1].signal.aborted, true);
  const stale = clone(full); stale.operations[0].label = '旧响应'; requests[1].resolve(envelope(stale)); await turns();
  assert.doesNotMatch(text(ui.render()), /旧响应/);
  ui.toggle(true); ui.flush(); await turns(); assert.equal(requests.length, 3);
  const wrong = clone(full); wrong.ref = 'd'.repeat(48); requests[2].resolve(envelope(wrong)); await turns();
  const failed = ui.render(); assert.match(find(failed, 'error-box').props.error.message, /不是这个批次/);
  assert.doesNotMatch(text(failed), /尚未生成工序/);
  find(failed, 'button', props => text(props.children) === '重新读取工序').props.onClick();
  assert.match(text(ui.render()), /正在读取工序/); ui.flush(); await turns(); assert.equal(requests.length, 4);
  const current = clone(full); current.operations[0].label = '铣削'; requests[3].resolve(envelope(current)); await turns();
  assert.match(text(ui.render()), /10 · 铣削/);
  ui.setRow(zero); assert.match(text(ui.render()), /尚未生成工序/); ui.flush(); await turns();
  assert.equal(requests.length, 4); assert.doesNotMatch(text(ui.render()), /铣削/);
  ui.setRow(clone(summary)); ui.render(); ui.flush(); await turns(); assert.equal(requests.length, 5);
  ui.h.unmount(); assert.equal(requests[4].signal.aborted, true); requests[4].resolve(envelope(stale)); await turns();

  const empty = overview(reader, zero); empty.render(); empty.flush(); empty.toggle(true); empty.flush(); await turns();
  assert.match(text(empty.render()), /尚未生成工序/); assert.equal(requests.length, 5, 'Zero-operation rows keep their empty state without a detail request'); empty.h.unmount();
  const changed = overview(reader); changed.render(); changed.flush(); changed.toggle(true); changed.flush(); await turns();
  const emptied = clone(full); emptied.relationships.operation_count = 0; emptied.operations = [];
  requests[5].resolve(envelope(emptied)); await turns();
  assert.match(text(changed.render()), /尚未生成工序/, 'A newer empty detail also shows the empty state'); changed.h.unmount();
  await calendarRefreshContracts();
  console.log('batch summary/detail and lazy operation request contracts passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
