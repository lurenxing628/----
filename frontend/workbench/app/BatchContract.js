import WorkbenchTerms from './WorkbenchTerms.js';
import { object, ref48, token32, isDate, failure } from './shared/contract/kit.js';

// 定型对象：transport 校验过的信封——数据在 .data，数据版本在 .meta.snapshot_ref，提示在 .warnings，其余元信息在 .meta。
// 本文件另外保证：页码与数据版本、批次身份、预检操作与所选批次、回执终态和本次请求对得上；字段形状由后端唯一生产者保证。
const fields = ['quantity', 'due_date', 'priority', 'ready_status', 'ready_date', 'remark'];
const fieldNames = { quantity: '数量', due_date: '交期', priority: '优先级', ready_status: '齐套显示', ready_date: '齐套日期', remark: '备注' };
const actions = ['create', 'update', 'delete', 'operation_update', 'materials_update', 'split_confirm', 'sync_confirm', 'bulk_confirm', 'import_confirm'];
// 下拉与筛选的取值顺序和叫法都来自共同词表。
const priority = Object.entries(WorkbenchTerms.batch_priorities);
const ready = Object.entries(WorkbenchTerms.ready_statuses);
const statuses = Object.entries(WorkbenchTerms.batch_statuses);
const columns = [['business_code', '批次号', 155], ['part_no', '图号', 190], ['quantity', '数量', 80], ['due_date', '交期', 140],
  ['progress', '工序进度', 170], ['priority', '优先级', 115], ['ready_status', '齐套显示', 120], ['status', '状态', 115]];
function list(result, scope) {
  const d = result.data, p = d.page;
  if (p.number !== scope.page || p.size !== scope.size
      || scope.snapshot_ref && result.meta.snapshot_ref !== scope.snapshot_ref) throw failure('读到的批次列表不完整，请刷新后重试。');
  return result;
}
function detail(result, expected) {
  const d = result.data;
  if (d.ref !== expected)
    throw failure('读到的批次详情不完整或不是这个批次，请刷新后重试。');
  return result;
}
// 回执在命令发出之后核对：对不上时结果未知，本机待确认记录不能清。
function receipt(result, action, expected, expectedOperationRef) {
  const data = result.data;
  const valid = ['bulk_confirm', 'import_confirm'].includes(action) ? object(data)
    : ref48(data.entity_ref) && (action === 'create' || data.entity_ref === expected)
      && (action !== 'operation_update' || ref48(data.operation_ref) && data.operation_ref === expectedOperationRef)
      && (action !== 'split_confirm' || ref48(data.child_ref));
  if (!valid) {
    const message = action === 'operation_update' && ref48(data.entity_ref) && data.entity_ref === expected && data.operation_ref !== expectedOperationRef
      ? '保存结果对应的不是当前工序。请刷新批次详情核对，不要重复提交。'
      : action === 'split_confirm' && ref48(data.entity_ref) && data.entity_ref === expected && !ref48(data.child_ref)
        ? '未读到拆分子批，请刷新批次核对。' : WorkbenchTerms.outcomes.unknown('保存');
    throw failure(message, { committed: 'unknown' });
  }
  return result;
}
function preview(result, action, expectedRef, input) {
  const data = result.data, name = 'batch.' + action + '_confirm';
  let valid = data.operation === name && token32(data.preview_ref);
  if (valid && action === 'bulk') {
    const selected = new Set(input.refs);
    valid = data.action === input.action && Array.isArray(data.rows) && data.rows.length === input.refs.length
      && new Set(data.rows.map(row => row && row.entity_ref)).size === input.refs.length
      && data.rows.every(row => object(row) && selected.has(row.entity_ref));
  }
  if (valid && action === 'import') valid = data.mode === input.mode;
  if (valid && action === 'sync') valid = data.entity_ref === expectedRef;
  if (valid && action === 'split') valid = data.entity_ref === expectedRef && data.as_of_date === input.as_of_date;
  if (!valid) throw failure('读到的预检结果和所选批次或操作不一致，没有确认。请重新预检。');
  return data;
}
function reason(ctx, action, source) {
  if (source !== 'production') return '当前不是可写生产资料。';
  if (ctx && ctx.capabilities['batch.' + action] === true) return '';
  const blocked = ctx && ctx.blocked_reasons.find(row => row.action === 'batch.' + action);
  return blocked ? blocked.message : '当前资料不允许此操作。';
}
// 列筛选值与全选结果都钉在列表这次读取的数据版本上；版本变了就让用户刷新，不把别的版本的值并进来。
function facets(result, scope) {
  if (result.meta.snapshot_ref !== scope.snapshot_ref) throw failure(WorkbenchTerms.outcomes.stale);
  return result;
}
function selection(result, snapshot) {
  if (result.meta.snapshot_ref !== snapshot) throw failure(WorkbenchTerms.outcomes.stale);
  return result.data.refs;
}
function label(key, value) {
  const options = { priority, ready_status: ready, status: statuses }[key];
  return value === null || value === undefined || value === '' ? '未填写' : options ? options.find(row => row[0] === value)[1] : String(value);
}
// 有效齐套（display_ready_status）由后端按当前日期和物料记录算出；算不出时是 null，要去核对物料需求，显示“待核对”（与资料总览一致）。
// 字段原值（fields.ready_status、物料需求行的 ready_status）为空才是“未填写”，仍用 label。
function readyLabel(value) { return value === null ? '待核对' : label('ready_status', value); }
function draft(entity) {
  return entity ? Object.fromEntries(fields.map(key => [key, entity.fields[key] == null ? '' : String(entity.fields[key])]))
    : { business_code: '', part_ref: '', quantity: '', due_date: '', priority: 'normal', ready_status: 'yes', ready_date: '', remark: '' };
}
function input(value, original) {
  const errors = inputErrors(value, original);
  if (errors.length) throw failure('请核对标红的项。', { fields: errors });
  const patch = {};
  for (const key of fields) {
    if (original && String(original.fields[key] == null ? '' : original.fields[key]) === value[key]) continue;
    let next = value[key];
    if (key === 'quantity') {
      next = Number(next);
    } else if (key.endsWith('_date')) {
      next = next === '' ? null : next;
    } else if (key === 'remark') { next = next.trim(); if (next === '') next = null; }
    patch[key] = next;
  }
  if (original) return { fields: patch };
  return { business_code: value.business_code.trim(), part_ref: value.part_ref, fields: patch };
}
function inputErrors(value, original) {
  const errors = [];
  if (!original) {
    if (!value.business_code.trim()) errors.push({ path: 'business_code', message: '请填写批次号。' });
    if (!ref48(value.part_ref)) errors.push({ path: 'part_ref', message: '请选择图号。' });
  }
  for (const key of fields) {
    if (original && String(original.fields[key] == null ? '' : original.fields[key]) === value[key]) continue;
    const next = value[key];
    if (key === 'quantity' && (!next.trim() || !Number.isFinite(Number(next))))
      errors.push({ path: 'fields.quantity', message: '请填写有效的数量。' });
    if (key.endsWith('_date') && next !== '' && !isDate(next))
      errors.push({ path: 'fields.' + key, message: '请按 2026-09-13 这样填写日期。' });
  }
  return errors;
}
const APSBatchContract = { list, detail, receipt, preview, facets, selection, reason, readyLabel, label, draft, input, inputErrors, fields, fieldNames, actions, priority, ready, statuses, columns };

export {
  APSBatchContract,
  list,
  detail,
  receipt,
  preview,
  facets,
  selection,
  reason,
  readyLabel,
  label,
  draft,
  input,
  inputErrors,
  fields,
  fieldNames,
  actions,
  priority,
  ready,
  statuses,
  columns
};
export default APSBatchContract;
