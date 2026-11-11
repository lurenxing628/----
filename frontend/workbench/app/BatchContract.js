import C from './resource-contract.js';
import WorkbenchTerms from './WorkbenchTerms.js';

const object = C.object;
const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
const text = value => typeof value === 'string';
const fields = ['quantity', 'due_date', 'priority', 'ready_status', 'ready_date', 'remark'];
const fieldNames = { quantity: '数量', due_date: '交期', priority: '优先级', ready_status: '齐套显示', ready_date: '齐套日期', remark: '备注' };
const actions = ['create', 'update', 'delete', 'operation_update', 'materials_update', 'split_confirm', 'sync_confirm', 'bulk_confirm', 'import_confirm'];
const priority = [['normal', '普通'], ['urgent', '急件'], ['critical', '特急']];
const ready = [['yes', '齐套'], ['partial', '部分齐套'], ['no', '未齐套']];
const statuses = [['pending', '待排'], ['scheduled', '已排'], ['processing', '加工中'], ['completed', '已完成'], ['cancelled', '已取消']];
const columns = [['business_code', '批次号', 155], ['part_no', '图号', 190], ['quantity', '数量', 80], ['due_date', '交期', 140],
  ['progress', '工序进度', 170], ['priority', '优先级', 115], ['ready_status', '齐套显示', 120], ['status', '状态', 115]];
function list(result, scope) {
  const d = result.data, p = d.page;
  if (p.number !== scope.page || p.size !== scope.size
      || scope.snapshot_ref && result.meta.snapshot_ref !== scope.snapshot_ref) throw C.failure('读到的批次列表不完整，请刷新后重试。');
  return result;
}
function detail(result, expected) {
  const d = result.data;
  if (d.ref !== expected)
    throw C.failure('读到的批次详情不完整或不是这个批次，请刷新后重试。');
  return result;
}
function receipt(result, action, expected, expectedOperationRef) {
  const data = result.data;
  const valid = ['bulk_confirm', 'import_confirm'].includes(action) ? object(data)
    : ref(data.entity_ref) && (action === 'create' || data.entity_ref === expected)
      && (action !== 'operation_update' || ref(data.operation_ref) && data.operation_ref === expectedOperationRef)
      && (action !== 'split_confirm' || ref(data.child_ref));
  if (!valid) {
    const message = action === 'operation_update' && ref(data.entity_ref) && data.entity_ref === expected && data.operation_ref !== expectedOperationRef
      ? '保存结果对应的不是当前工序。请刷新批次详情核对，不要重复提交。'
      : action === 'split_confirm' && ref(data.entity_ref) && data.entity_ref === expected && !ref(data.child_ref)
        ? '未读到拆分子批，请刷新批次核对。' : WorkbenchTerms.outcomes.unknown('保存');
    const error = C.failure(message); error.committed = 'unknown'; throw error;
  }
  return result;
}
function preview(result, action, expectedRef, input) {
  const data = result.data, name = 'batch.' + action + '_confirm';
  let valid = data.operation === name && text(data.preview_ref) && /^[A-Za-z0-9_-]{32}$/.test(data.preview_ref);
  if (valid && action === 'bulk') {
    const selected = new Set(input.refs);
    valid = data.action === input.action && Array.isArray(data.rows) && data.rows.length === input.refs.length
      && new Set(data.rows.map(row => row && row.entity_ref)).size === input.refs.length
      && data.rows.every(row => object(row) && selected.has(row.entity_ref));
  }
  if (valid && action === 'sync') valid = data.entity_ref === expectedRef;
  if (valid && action === 'split') valid = data.entity_ref === expectedRef && data.as_of_date === input.as_of_date;
  if (!valid) throw C.failure('读到的预检结果和所选批次或操作不一致，没有确认。请重新预检。');
  return data;
}
function reason(ctx, action, source) {
  if (source !== 'production') return '当前不是可写生产资料。';
  if (ctx && ctx.capabilities['batch.' + action] === true) return '';
  const blocked = ctx && ctx.blocked_reasons.find(row => row.action === 'batch.' + action);
  return blocked ? blocked.message : '当前资料不允许此操作。';
}
function readyStatus(entity) { return Object.prototype.hasOwnProperty.call(entity, 'display_ready_status') ? entity.display_ready_status : entity.fields.ready_status; }
function label(key, value) {
  const options = { priority, ready_status: ready, status: statuses }[key];
  return value === null || value === undefined || value === '' ? '未填写' : options ? (options.find(row => row[0] === value) || ['', '原标记待核对'])[1] : String(value);
}
function draft(entity) {
  return entity ? Object.fromEntries(fields.map(key => [key, entity.fields[key] == null ? '' : String(entity.fields[key])]))
    : { business_code: '', part_ref: '', quantity: '', due_date: '', priority: 'normal', ready_status: 'yes', ready_date: '', remark: '' };
}
function input(value, original) {
  const errors = inputErrors(value, original);
  if (errors.length) throw C.failure('请核对标红的项。', errors);
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
    if (!ref(value.part_ref)) errors.push({ path: 'part_ref', message: '请选择图号。' });
  }
  for (const key of fields) {
    if (original && String(original.fields[key] == null ? '' : original.fields[key]) === value[key]) continue;
    const next = value[key];
    if (key === 'quantity' && (!/^[0-9]+$/.test(next) || !Number.isSafeInteger(Number(next)) || Number(next) <= 0))
      errors.push({ path: 'fields.quantity', message: '数量必须是正整数。' });
    if (key.endsWith('_date') && next !== '' && !/^\d{4}-\d{2}-\d{2}$/.test(next))
      errors.push({ path: 'fields.' + key, message: '请按 2026-09-13 这样填写日期。' });
  }
  return errors;
}
const APSBatchContract = { ref, list, detail, receipt, preview, reason, readyStatus, label, draft, input, inputErrors, fields, fieldNames, actions, priority, ready, statuses, columns };

export {
  APSBatchContract,
  ref,
  list,
  detail,
  receipt,
  preview,
  reason,
  readyStatus,
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
