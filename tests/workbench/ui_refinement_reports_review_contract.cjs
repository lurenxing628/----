'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), base = path.join(root, 'frontend/workbench/app');
const React = { createElement: (type, props, ...children) => ({ type, props: props || {}, children }), Fragment: 'fragment', createContext: () => ({}) };
const context = { React, window: { React, ResourceControls: {}, ReportControls: {}, WorkbenchFormat: {
  number: (value) => value == null ? '未知' : String(value),
  // 与真 WorkbenchFormat.dateTime 一样：格式不对就抛错，不静默原样返回。
  dateTime: value => { if (value == null) return '未知'; if (!/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(value)) throw new TypeError('无法显示：日期时间格式不正确。'); return value.replace('T', ' '); },
  hours: value => String(value) + ' 小时'
}, WorkbenchTerms: { report_actions: {}, outcomes: { unavailable: '此功能尚未开通。' } } } };
vm.createContext(context);
context.window.DashboardContract = { categories: { external: '外协', actual: '现场' } };
context.window.ResourceControls.Issues = function Issues() {};
const controlMocks = context.window.ResourceControls;
const files = ['ResourceControls.jsx', 'ReportEvidence.jsx', 'ReportTable.jsx', 'ReportControls.jsx', 'CalibrationControls.jsx', 'DashboardPanels.jsx'];
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: files.map(file => ({ path: file, code: fs.readFileSync(path.join(base, file), 'utf8') })), check_combined: true });
for (const output of built.outputs) {
  vm.runInContext(output.code, context);
  if (output.path.endsWith('ResourceControls.jsx')) context.window.ResourceControls = { ...controlMocks, MetricValue: context.window.ResourceControls.MetricValue };
}
const E = context.window.ReportEvidence, T = context.window.ReportTable;
context.window.WorkbenchReference = function WorkbenchReference() {};
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
  if (value && typeof value === 'object') return value.type === context.window.WorkbenchReference ? '' : visibleText(value.children);
  return value == null ? '' : String(value);
}
const referenceNodes = nodes(diagnostic).filter(node => node.type === context.window.WorkbenchReference);
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
context.window.WorkbenchListControls = { Pager: () => null };
const reportPage = context.window.ReportControls.Page({ page: { number: 2, size: 10, pages: 4, total: 31 }, onChange: patch => calls.push(patch) });
assert.deepEqual(Array.from(reportPage.props.sizes), [10, 20, 50]);
reportPage.props.onSize(20); reportPage.props.onPage(3);
assert.equal(JSON.stringify(calls), '[{"page":1,"size":20},{"page":3}]');
const calibration = context.window.CalibrationControls.Page({ page: { number: 1, size: 37, total_pages: 2, total: 40 }, onChange() {} });
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
const grouped = context.window.DashboardPanels.Gaps({ categories, selected: 'external' });
const groupNodes = nodes(grouped), groupText = visibleText(grouped);
assert.equal(groupNodes.filter(node => node.props && node.props['data-gap-source']).length, 4, 'Every affected record remains in the table');
assert.equal(groupNodes.filter(node => node.type === 'p').length, 3, 'Only matching code and message share one explanation');
for (const gap of categories.external.evaluation_gaps) assert(groupText.includes(gap.subject));
assert(!groupText.includes('批次 E')); assert(groupText.includes('暂无法评估 · 4 项'));
assert.equal((groupText.match(/关联资料缺失，请联系维护人员。/g) || []).length, 2);
assert.equal(JSON.stringify(categories), before, 'Grouping must not alter source facts or counts');
assert.equal(nodes(context.window.DashboardPanels.Gaps({ categories, selected: 'all' })).filter(node => node.props && node.props['data-gap-source']).length, 5);
const operationCategories = JSON.parse(before);
operationCategories.external.evaluation_gaps.forEach((gap, index) => { gap.operation = {code:'OP（2026）_' + index, name:'表处理（外协）'}; });
const operationTree = context.window.DashboardPanels.Gaps({categories:operationCategories, selected:'external'});
const operationNodes = nodes(operationTree), operationText = visibleText(operationTree);
assert(operationText.includes('工序编号') && operationText.includes('工序名称'));
assert(operationText.includes('暂无法评估 · 4 道工序'));
assert(operationText.includes('OP（2026）_0') && operationText.includes('表处理（外协）'), 'Use separate source fields without parsing display punctuation');
assert(!operationText.includes('批次 A · 工序 10'), 'Structured rows do not repeat the combined subject');
assert(operationNodes.filter(node => node.type === 'details').every(node => !node.props.open), 'Start collapsed');
context.window.APSWorkbenchUI = {MetricStrip:function MetricStrip(){}, Metric:function Metric(){}};
context.window.WorkbenchFormat.percent = value => String(value);
for (const count of [0, 18]) {
  const metrics = T.Metrics({topic:'delivery',summary:{production_reports:0,completion_rate:0,on_time_rate:0,
    confirmed_due:0,due:18,due_on_time:0,late_open:count,median_finish_minutes:null,finish_sample:0}});
  const late = nodes(metrics).find(node => node.props.label === '超时未确认完成');
  assert.equal(late.props.value, count);
  assert.equal(late.props.unit, '道');
  assert.equal(late.props.helper, '超过计划完工时间 10 分钟');
  assert.equal(late.props.tone, count ? 'warning' : undefined);
}
vm.runInContext(fs.readFileSync(path.join(base, 'ReportAPI.js'), 'utf8'), context);
const operationDetail = { production_report_count: 0, unknown_record_count: 0,
  known_completed_quantity: null, remaining_quantity: 5, effective_processing_hours: null,
  known_effective_processing_hours: 0, unknown_hour_events: 0 };
const narrowDetail = { ok: true, meta: { source: 'production', snapshot_ref: 'same-snapshot' },
  data: { plan: { is_current_official: true }, detail: { operation: operationDetail, records: [] } } };
assert.equal(context.window.ReportAPI.validateDetail(narrowDetail), narrowDetail, 'Detail only requires its operation, records, plan and metadata');
assert.throws(() => context.window.ReportAPI.validate(narrowDetail), /报表数据不完整/);
assert.throws(() => context.window.ReportAPI.validateDetail({ ...narrowDetail, data: { ...narrowDetail.data,
  detail: { operation: { ...operationDetail, production_report_count: -1 }, records: [] } } }), /工序详情不完整/);
process.stdout.write('reports-review display contracts passed\n');
