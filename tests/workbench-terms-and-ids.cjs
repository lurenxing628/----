'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const babel = require(path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'));
const React = { createElement(type, props, ...children) {
  const values = { ...props, children: children.flat(Infinity) };
  return typeof type === 'function' ? type(values) : { type, props: values };
} };
const context = vm.createContext({ window: {}, React });
for (const name of ['WorkbenchTerms.js', 'WorkbenchReferences.jsx']) {
  const source = fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8');
  vm.runInContext(name.endsWith('.jsx') ? babel.transform(source, { presets: ['react'] }).code : source, context);
}
const T = context.window.WorkbenchTerms, Ref = context.window.WorkbenchReference, ErrorBox = context.window.WorkbenchError;
function text(tree, omitReferences = false) {
  if (tree === null || tree === undefined || tree === false) return '';
  if (typeof tree !== 'object') return String(tree);
  if (omitReferences && tree.type === 'details' && tree.props.className === 'wb-ref') return '';
  return tree.props.children.map(child => text(child, omitReferences)).join('\n');
}
assert.equal(T.overdue_count, '预计超期批次');
assert.equal(T.total_tardiness_hours, '总拖期');
assert.equal(T.candidate, '候选方案');
assert.equal(T.actions.save, '保存');
assert.deepEqual(JSON.parse(JSON.stringify(T)), {
  overdue_count: '预计超期批次', delay_hours: '超期时长', total_tardiness_hours: '总拖期', utilization: '利用率',
  candidate: '候选方案', official_plan: '正式计划', trial: '试调', trial_draft: '试调草稿', trial_scenario: '试调方案',
  hours_unit: '小时', handler: '经办人', recorder: '记录人', owner: '责任人',
  refresh_latest: '刷新最新资料', accept_latest: '已核对，继续编辑', personal_calendar: '个人日历',
  name_missing: '名称未填写', legacy_field_records: '历史现场记录', shared_operation: '共同工序', overdue: '超期',
  current_official: '当前正式', historical_official: '历史正式', baseline_plan: '排产时的正式计划', initial_plan: '初始计划',
  run_statuses: { queued: '等待计算', running: '正在计算', complete: '计算完成', partial: '部分完成', failed: '计算失败', interrupted: '已中断' },
  candidate_statuses: { completed: '已完成', partial: '部分完成', failed: '失败', skipped: '已跳过' },
  material_strategies: { strict: '整批齐套', stage: '按工序齐套', split: '预检分批开工' },
  execution_states: { unreported: '待报工', started: '已开工', partial: '部分完成', paused: '已暂停', exception: '异常', complete: '已完工' },
  data_quality: { complete: '完整', incomplete: '不完整', legacy_incomplete: '历史资料不完整', invalid: '需复核' },
  delivery_risks: { overdue: '预计超期', on_time: '预计按期', unknown: '暂无数据' },
  report_actions: { create: '新增', supplement: '补齐', correct: '更正' },
  actions: { add: '新增', save: '保存', confirm: '确认', cancel: '取消', clear: '清除', import: '导入', export: '导出', download: '下载',
    refresh: '刷新', query_result: '查询结果', adopt: '采用' },
  outcomes: { stale: '数据已更新，请刷新后重试。刚才的选择已保留。', unavailable: '此功能尚未开通。',
    failure: '操作没有完成。请刷新重试；仍不行请联系维护人员，并告知下方编号。' }
});
assert(Object.isFrozen(T.outcomes));
// 执行状态、数据完整性、交付判断各只留一套叫法：现场记录、排产候选、试调、值班台都从这里取。
assert(Object.isFrozen(T.execution_states) && Object.isFrozen(T.data_quality) && Object.isFrozen(T.delivery_risks));
assert.equal(T.outcomes.pending('保存'), '上次保存的结果还没查到，可能已经生效。请点「查询结果」，不要重复提交。');
assert.equal(T.outcomes.rejected('采用', '批次号重复'), '上次采用没有生效：批次号重复。填写内容已保留，改好后重新提交。');
assert.equal(T.outcomes.rejected('采用', '批次号重复。'), '上次采用没有生效：批次号重复。填写内容已保留，改好后重新提交。');
assert.equal(T.outcomes.done('导入'), '导入已完成。');
assert.equal(T.outcomes.done('导入', '请到批次管理查看'), '导入已完成。请到批次管理查看。');
assert.equal(T.outcomes.unknown('提交'), '提交结果不确定，可能已经生效。请刷新后核对，不要重复提交。');
assert.equal(T.plan_version(3), '正式 v3');
assert.equal(T.download_started('批次.xlsx'), '已交给浏览器下载：批次.xlsx');
assert.equal(T.data_as_of('2026-09-21 16:00'), '数据截至 2026-09-21 16:00');
assert(Object.isFrozen(T));
assert(Object.isFrozen(T.actions));
assert.equal(Ref({}), null);
assert.equal(Ref({ entries: { '资源编号': null, '操作编号': '' } }), null);
const hash = '0123456789abcdef'.repeat(3);
const refs = Ref({ entries: { '排产编号': hash, '操作编号': 'request-123' } });
assert.equal(refs.type, 'details');
assert.equal(refs.props.className, 'wb-ref');
assert.equal(refs.props.open, undefined);
assert(text(refs).includes(hash));
assert.equal(text(refs, true), '');
assert(text(Ref({ value: 0 })).includes('0'));
assert(text(Ref({ value: '<script>bad()</script>' })).includes('<script>bad()</script>'));
assert.equal(Ref({ value: 'r1' }).props.dangerouslySetInnerHTML, undefined);
assert.equal(ErrorBox({ error: null }), null);
const original = Object.freeze({ message: '请先填写批次数量。', code: 'quantity.required', request_key: hash });
const business = ErrorBox({ error: original, fields: [{ path: 'quantity', message: original.message }] });
assert.equal(text(business, true).match(/请先填写批次数量。/g).length, 1);
assert(!text(business, true).includes(hash));
assert(!text(business, true).includes('quantity.required'));
assert(text(business).includes(hash));
assert(text(business).includes('quantity.required'));
for (const message of ['工艺表.xlsx 缺少工序列，请修正后重试。', 'route_template.xlsx 缺少工序列，请修正后重试。', '无法读取 aps.db，请检查文件是否仍在原位置。']) {
  const tree = ErrorBox({ error: { message, code: 'file.invalid' } });
  assert(text(tree, true).includes(message), 'Keep actionable file context');
  assert(!text(tree, true).includes('file.invalid'));
  assert(text(tree).includes('file.invalid'));
}
for (const message of ['HTTP 503: request_failed', 'TypeError: 无法读取', '{"message":"bad"}', '[1,2]', '{}', '引用 ' + hash + ' 已过期', 'request_failed', '资格检查 qualification.empty']) {
  const tree = ErrorBox({ error: { message }, fallback: '保存未完成，请重试。' });
  assert(text(tree, true).includes('保存未完成，请重试。'));
  assert(!text(tree, true).includes(message));
  assert(text(tree).includes(message));
}
const filtered = ErrorBox({ error: { message: '必填项未完成。' }, hideMessage: true, fields: [
  { path: 'quantity', message: '请填写数量。' }, { path: 'due_date', message: '请选择交期。' }, { path: 'due_date', message: '请选择交期。' }
], excludePaths: ['quantity'] });
assert(!text(filtered, true).includes('请填写数量。'));
assert(!text(filtered, true).includes('必填项未完成。'));
assert.equal(text(filtered, true).match(/请选择交期。/g).length, 1);
const diagnosticOnly = ErrorBox({ error: original, hideMessage: true });
assert.equal(text(diagnosticOnly, true).trim(), '');
assert(text(diagnosticOnly).includes(hash));
process.stdout.write('WorkbenchTerms and references contracts passed (isolated React element fixture).\n');
