'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), base = path.join(root, 'frontend/workbench/app');
const React = { createElement: (type, props, ...children) => ({ type, props: props || {}, children }), Fragment: 'fragment', createContext: () => ({}) };
const workbenchFormatStub = {
  number: (value) => value == null ? '未知' : String(value),
  // 与真 WorkbenchFormat.dateTime 一样：格式不对就抛错，不静默原样返回。
  dateTime: value => { if (value == null) return '未知'; if (!/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(value)) throw new TypeError('无法显示：日期时间格式不正确。'); return value.replace('T', ' '); },
  hours: value => String(value) + ' 小时'
};
const workbenchTermsStub = { report_actions: {}, outcomes: { unavailable: '此功能尚未开通。' } };
const controlMocks = { Issues: function Issues() {} };
const WorkbenchReference = function WorkbenchReference() {};
const context = {
  React,
  window: {
    React,
    __wbStubs: {
      'ResourceControls.jsx': controlMocks,
      'WorkbenchFormat.js': workbenchFormatStub,
      'WorkbenchTerms.js': workbenchTermsStub,
      'DashboardContract.js': { categories: { external: '外协', actual: '现场' } },
      'WorkbenchReferences.jsx': { WorkbenchReference, default: { WorkbenchReference } },
    },
  },
};
vm.createContext(context);
const files = ['ResourceControls.jsx', 'ReportEvidence.jsx', 'ReportTable.jsx', 'ReportControls.jsx', 'CalibrationControls.jsx', 'DashboardPanels.jsx', 'ReportAPI.js', 'ReportWorkspace.jsx'];
const built = compile({
  sources: files.map(file => ({ path: file, code: fs.readFileSync(path.join(base, file), 'utf8') })), check_combined: true });
for (const output of built.outputs) {
  if (output.path === 'ReportAPI.js' || output.path === 'ReportWorkspace.jsx') continue;
  const mod = vm.runInContext(output.code, context);
  if (output.path.endsWith('ResourceControls.jsx')) {
    controlMocks.MetricValue = mod.MetricValue;
    context.__wbRuntime.setStub('ResourceControls.jsx', controlMocks);
  }
}
const E = context.__wbRuntime.getModule('ReportEvidence.jsx'), T = context.__wbRuntime.getModule('ReportTable.jsx');
const ReportControls = context.__wbRuntime.getModule('ReportControls.jsx');
const CalibrationControls = context.__wbRuntime.getModule('CalibrationControls.jsx');
const DashboardPanels = context.__wbRuntime.getModule('DashboardPanels.jsx');
assert.equal(E.noFeedback({ production_reports: 0 }), true);
for (const summary of [{ production_reports: 1 }, { production_reports: null }, {}, null]) assert.equal(E.noFeedback(summary), false);
assert.equal(T.text(0), '0'); assert.equal(T.text(null), '未知');
const missing = E.actualValue(null, true);
assert.equal(missing.props['aria-label'], '暂无现场数据');
assert.equal(missing.children.join(''), '—');
assert.equal(E.actualValue(0, true), '0'); assert.equal(E.actualValue(null, false), '未知');
const tree = E.StructuredFacts({ value: { completed_quantity: 0, actual_start: null, raw_values: { remark: '保留来源' }, operation_ref: 'a'.repeat(48) } });
const flat = JSON.stringify(tree);
assert(flat.includes('本次完成数量')); assert(flat.includes('保留来源')); assert(flat.includes('未知'));
assert(!flat.includes('[object Object]'));
const reference = 'A1'.repeat(16), arrayReference = 'c3'.repeat(16), businessCode = 'b2'.repeat(16), requestKey = 'request-retained-in-full';
const diagnostic = E.StructuredFacts({ value: { code: 'missing_hours', rule: 'quota.minimum_samples', rule_code: 'R17',
  request_key: requestKey, diagnostic_code: 0, completed_quantity: 0, raw_values: {
    fingerprint: reference, batch_code: businessCode, operation_code: businessCode, remark: reference,
    description: '说明 ' + reference, completed_quantity: 0, operation_refs: [reference, null, 0], untyped_values: [arrayReference, 0]
  } } });
function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  return value && typeof value === 'object' ? [value, ...nodes(value.children)] : [];
}
function visibleText(value) {
  if (Array.isArray(value)) return value.map(visibleText).join('');
  if (value && typeof value === 'object') return value.type === WorkbenchReference ? '' : visibleText(value.children);
  return value == null ? '' : String(value);
}
const referenceNodes = nodes(diagnostic).filter(node => node.type === WorkbenchReference);
const retained = Object.assign({}, ...referenceNodes.map(node => node.props.entries));
assert.equal(retained['原因代码'], 'missing_hours'); assert.equal(retained['规则'], 'quota.minimum_samples');
assert.equal(retained['规则代码'], 'R17'); assert.equal(retained['操作编号'], requestKey);
assert.equal(retained['诊断代码'], 0); assert.equal(retained.fingerprint, reference);
assert.equal(JSON.stringify(retained.operation_refs), JSON.stringify([reference, null, 0]));
assert(referenceNodes.some(node => node.props.value === arrayReference), 'Hexadecimal references inside raw arrays must also be collected');
const visible = visibleText(diagnostic);
for (const value of ['missing_hours', 'quota.minimum_samples', 'R17', requestKey]) assert(!visible.includes(value));
assert(visible.includes(businessCode), 'Business codes must remain visible even when they look hexadecimal');
assert(visible.includes('备注' + reference), 'A business remark is not an internal reference');
assert(visible.includes('说明 ' + reference), 'Only a complete hexadecimal value is collected');
assert(visible.includes('本次完成数量0')); assert(!visible.includes('fingerprint'));
assert(!visible.includes(arrayReference));
const calls = [];
controlMocks.Pager = () => null;
const reportPage = ReportControls.Page({ page: { number: 2, size: 10, pages: 4, total: 31 }, onChange: patch => calls.push(patch) });
assert.deepEqual(Array.from(reportPage.props.sizes), [10, 20, 50]);
reportPage.props.onSize(20); reportPage.props.onPage(3);
assert.equal(JSON.stringify(calls), '[{"page":1,"size":20},{"page":3}]');
const calibration = CalibrationControls.Page({ page: { number: 1, size: 37, total_pages: 2, total: 40 }, onChange() {} });
assert.deepEqual(Array.from(calibration.props.sizes), [10, 20, 37, 50]); assert.equal(calibration.props.pages, 2);
const categories = {
  external: { issues: [], unknown_count: 4, evaluation_gaps: [
    { source_ref: 'a', subject: '批次 A · 工序 10', code: 'association_missing', message: '关联资料缺失，请联系维护人员。' },
    { source_ref: 'b', subject: '批次 B · 工序 20', code: 'association_missing', message: '关联资料缺失，请联系维护人员。' },
    { source_ref: 'c', subject: '批次 C · 工序 30', code: 'unregistered', message: '请补充物流登记。' },
    { source_ref: 'd', subject: '批次 D · 工序 40', code: 'other_missing', message: '关联资料缺失，请联系维护人员。' }
  ] },
  actual: { issues: [], unknown_count: 1, evaluation_gaps: [
    { source_ref: 'e', subject: '批次 E · 工序 50', code: 'unreported', message: '暂无报工记录。' }
  ] }
};
const before = JSON.stringify(categories);
const grouped = DashboardPanels.Gaps({ categories, selected: 'external' });
const groupNodes = nodes(grouped), groupText = visibleText(grouped);
assert.equal(groupNodes.filter(node => node.props && node.props['data-gap-source']).length, 4, 'Every affected record remains in the table');
assert.equal(groupNodes.filter(node => node.type === 'p').length, 3, 'Only matching code and message share one explanation');
for (const gap of categories.external.evaluation_gaps) assert(groupText.includes(gap.subject));
assert(!groupText.includes('批次 E')); assert(groupText.includes('暂无法评估 · 4 项'));
assert.equal((groupText.match(/关联资料缺失，请联系维护人员。/g) || []).length, 2);
assert.equal(JSON.stringify(categories), before, 'Grouping must not alter source facts or counts');
assert.equal(nodes(DashboardPanels.Gaps({ categories, selected: 'all' })).filter(node => node.props && node.props['data-gap-source']).length, 5);
const operationCategories = JSON.parse(before);
operationCategories.external.evaluation_gaps.forEach((gap, index) => { gap.operation = {code:'OP（2026）_' + index, name:'表处理（外协）'}; });
const operationTree = DashboardPanels.Gaps({categories:operationCategories, selected:'external'});
const operationNodes = nodes(operationTree), operationText = visibleText(operationTree);
assert(operationText.includes('工序编号') && operationText.includes('工序名称'));
assert(operationText.includes('暂无法评估 · 4 道工序'));
assert(operationText.includes('OP（2026）_0') && operationText.includes('表处理（外协）'), 'Use separate source fields without parsing display punctuation');
assert(!operationText.includes('批次 A · 工序 10'), 'Structured rows do not repeat the combined subject');
assert(operationNodes.filter(node => node.type === 'details').every(node => !node.props.open), 'Start collapsed');
context.__wbRuntime.setStub('shared/ui/Metric.jsx', { MetricStrip: function MetricStrip() {}, Metric: function Metric() {} });
workbenchFormatStub.percent = value => String(value);
for (const count of [0, 18]) {
  const metrics = T.Metrics({topic:'delivery',summary:{production_reports:0,completion_rate:0,on_time_rate:0,
    confirmed_due:0,due:18,due_on_time:0,late_open:count,median_finish_minutes:null,finish_sample:0}});
  const late = nodes(metrics).find(node => node.props.label === '超时未确认完成');
  assert.equal(late.props.value, count);
  assert.equal(late.props.unit, '道');
  assert.equal(late.props.helper, '超过计划完工时间 10 分钟');
  assert.equal(late.props.tone, count ? 'warning' : undefined);
}
vm.runInContext(built.outputs.find(o => o.path === 'ReportAPI.js').code, context);
const ReportAPI = context.__wbRuntime.getModule('ReportAPI.js');
const operationDetail = { production_report_count: 0, unknown_record_count: 0,
  known_completed_quantity: null, remaining_quantity: 5, effective_processing_hours: null,
  known_effective_processing_hours: 0, unknown_hour_events: 0 };
const narrowDetail = { ok: true, meta: { source: 'production', snapshot_ref: 'same-snapshot' },
  data: { plan: { is_current_official: true }, detail: { operation: operationDetail, records: [] } } };
assert.equal(ReportAPI.validate(narrowDetail), narrowDetail, 'Detail only requires its operation, records, plan and metadata');
const states = [];
let cursor = 0, readState = null;
Object.assign(React, {
  useState(initial) {
    const index = cursor++;
    if (!(index in states)) states[index] = typeof initial === 'function' ? initial() : initial;
    return [states[index], next => { states[index] = typeof next === 'function' ? next(states[index]) : next; }];
  },
  useReducer(reducer, initial) {
    const index = cursor++;
    if (!(index in states)) states[index] = initial;
    return [states[index], action => { states[index] = reducer(states[index], action); }];
  },
  useRef(initial) {
    const index = cursor++;
    if (!(index in states)) states[index] = { current: initial };
    return states[index];
  },
  useEffect() {},
  useLayoutEffect() {}
});
Object.assign(workbenchTermsStub, {
  current_official: '当前正式计划',
  historical_official: '历史正式计划',
  plan_version: value => '第 ' + value + ' 版',
  data_as_of: value => '数据截至 ' + value
});
controlMocks.EmptyState = function EmptyState() { return null; };
context.__wbRuntime.setStubs({
  'WorkbenchCaption.jsx': { useCaption() {} },
  'WorkbenchPageContext.jsx': { useSnapshot() {} },
  'resource-contract.js': { failure: message => new Error(message) },
  'ReviewCharts.jsx': function ReviewCharts() { return null; },
  'ReportDetail.jsx': function ReportDetail() { return null; },
  'ReportCatalog.jsx': function ReportCatalog() { return null; },
});
context.__wbRuntime.setStub('ReportControls.jsx', { ...ReportControls, useRead: () => readState });
vm.runInContext(built.outputs.find(o => o.path === 'ReportWorkspace.jsx').code, context);
const { ReportWorkspace } = context.__wbRuntime.getModule('ReportWorkspace.jsx');
function renderReportWorkspace(props) {
  cursor = 0;
  let node = ReportWorkspace(props);
  while (node && typeof node.type === 'function') node = node.type(node.props);
  return node;
}
readState = {
  busy: false, error: null,
  result: {
    meta: { as_of: '2026-10-01T08:00:00', snapshot_ref: 'snap-1' },
    data: {
      plan: { plan_ref: 'a'.repeat(48), display_name: '正式计划', is_current_official: true, version: 1 },
      scope: { source: 'production' }, topic: 'delivery',
      summary: { production_reports: 1, completion_rate: 1, on_time_rate: 1, confirmed_due: 1, due: 1, due_on_time: 1, late_open: 0, median_finish_minutes: 0, finish_sample: 1 },
      choices: {}, items: [],
      page: { number: 1, size: 20, pages: 2, total: 25, sort: [{ field: 'planned_end', direction: 'asc' }] },
      data_gaps: ['缺口一'], exports: { url: '/api/export' }
    }
  }
};
const initialReportTree = nodes(renderReportWorkspace({ initialContext: { catalogOpen: true }, onNav() {} }));
const initialPager = initialReportTree.find(node => node.type === ReportControls.Page);
assert(initialPager && initialPager.props.busy === false);
initialPager.props.onChange({ page: 2 });
readState = { busy: true, error: null, result: null };
const loadingReportTree = nodes(renderReportWorkspace({ initialContext: { catalogOpen: true }, onNav() {} }));
const loadingSort = loadingReportTree.find(node => node.type === ReportControls.Sort);
const loadingPager = loadingReportTree.find(node => node.type === ReportControls.Page);
const limitationsDetails = loadingReportTree.find(node => node.type === 'details' && node.props.className === 'rw-limitations');
const catalogDetails = loadingReportTree.find(node => node.type === 'details' && node.props.className === 'rw-catalog');
assert(loadingSort && loadingSort.props.state.page === 2, 'Sort remains mounted with updated page state while loading');
assert(loadingPager && loadingPager.props.busy === true && loadingPager.props.page.number === 2 && loadingPager.props.page.size === 20, 'Pager remains mounted while loading next page');
assert(limitationsDetails && catalogDetails && catalogDetails.props.open === true, 'Details shells remain mounted and preserve open state while loading');
process.stdout.write('reports-review display contracts passed\n');
