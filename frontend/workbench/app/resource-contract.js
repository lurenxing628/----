import T from './shared/network/transport.js';

const nodes = {
  process: { kind: 'part', label: '工艺', icon: 'database', chain: 'input', unit: '项' },
  material: { kind: 'material', label: '物料', icon: 'box', chain: 'input', unit: '条' },
  op_int: { kind: 'op_type', label: '自制工种', icon: 'wrench', category: 'internal', chain: 'internal', unit: '个' },
  machine: { kind: 'machine', label: '设备', icon: 'machine', chain: 'internal', unit: '台' },
  operator: { kind: 'operator', label: '人员', icon: 'users', chain: 'internal', unit: '人' },
  op_ext: { kind: 'op_type', label: '外协工种', icon: 'wrench', category: 'external', chain: 'external', unit: '个' },
  supplier: { kind: 'supplier', label: '供应商', icon: 'truck', chain: 'external', unit: '家' },
  calendar: { kind: 'calendar', label: '工作日历', icon: 'calendar-days', chain: 'global', unit: '项' }
};
const statuses = {
  material: [['active', '启用'], ['inactive', '停用']],
  machine: [['active', '可用'], ['maintain', '停机'], ['inactive', '停用']],
  operator: [['active', '在岗'], ['leave', '请假'], ['inactive', '停用']],
  supplier: [['active', '启用'], ['pending_review', '待复核'], ['inactive', '停用']]
};
const textFields = {
  material: ['spec', 'unit', 'remark'], op_type: ['category', 'default_merge_mode', 'remark'],
  machine: [], operator: [], supplier: []
};
// 每种可编辑资料都登记关系表；空表表示这类资料没有关系字段。
const relations = {
  material: [], op_type: [],
  machine: [
    { key: 'op_type_refs', label: '可做工种', kind: 'op_type', category: 'internal', multiple: true },
    { key: 'group_ref', label: '设备组', kind: 'machine_group', catalog: true }
  ],
  operator: [
    { key: 'skill_refs', label: '技能工种', kind: 'op_type', category: 'internal', multiple: true },
    { key: 'shift_profile_ref', label: '班次', kind: 'shift_profile', catalog: true }
  ],
  supplier: [{ key: 'op_type_refs', label: '可做外协工种', kind: 'op_type', category: 'external', multiple: true }]
};
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = value => typeof value === 'string';
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
// 本地校验失败：请求没有发出（status 为 null），与 transport 的统一错误对象同一形状，transport.rejected 判为确定没有生效。
function failure(message, fields = []) {
  return Object.assign(new Error(message), { code: null, fields, conflicts: [], committed: false, status: null,
    requestRef: null, requestKey: null, resultTarget: null });
}
// 统一错误对象只有一种形状（transport.js 与上面的 failure）。
const message = error => error.message || '读取失败，请刷新后重试。';
// 服务端说这次操作依据的资料已过期：需要用户刷新，不能静默复位后照旧重提。页面专属的过期码由调用方追加。
const staleCodes = ['stale_write', 'snapshot_stale'];
// stale / fieldErrors 的调用方在还没有错误时会传 null；字段行的形状已在 transport.failure 校验。
const stale = (error, extraCodes = []) => !!error && (staleCodes.includes(error.code) || extraCodes.includes(error.code));
const fieldErrors = error => error && Array.isArray(error.fields) ? error.fields : [];
function blocked(context, kind, action, source) {
  if (source !== 'production') return '当前不是生产数据，不能保存。';
  if (!context || !text(context.write_token) || !context.write_token) return '还没读到可以保存的资料，请点「刷新最新资料」后重试。';
  const name = kind + '.' + action;
  // 后端每份写入上下文都带 capabilities 和 blocked_reasons（web/routes/workbench/write_context.py）；不带 action 的原因对所有动作生效。
  if (context.capabilities[name] !== true) {
    const reason = context.blocked_reasons.find(row => !row.action || row.action === name);
    return reason ? reason.message : '当前记录不允许此操作。';
  }
  return '';
}
// 后端只产出各类资料自己的固定状态（core/models/workbench_resource_status.py，其余值直接报存储损坏）。
function statusLabel(kind, status) {
  return statuses[kind].find(row => row[0] === status)[1];
}
function resourceName(kind, category) {
  const opNames = { internal: '自制工种', external: '外协工种' };
  return kind === 'op_type' ? (own(opNames, category) ? opNames[category] : '工种') :
    ({ material: '物料', machine: '设备', operator: '人员', supplier: '供应商' }[kind] || '资源');
}
function codeLabel(kind) {
  return { material: '物料编号', op_type: '工种编号', machine: '设备编号', operator: '工号' }[kind] || '编号';
}
function nameLabel(kind) { return kind === 'operator' ? '姓名' : kind === 'supplier' ? '供应商' : '名称'; }
function fieldLabels(kind, category) {
  const labels = { spec: '规格', unit: '单位', stock_qty: '库存数量', remark: '备注', category: '归属',
    status: '原状态', inactive_reason: '停用原因', default_days: '默认周期（天）' };
  if (kind === 'op_type' && category === 'internal') labels.remark = '产能备注';
  if (kind === 'op_type' && ['external', 'both'].includes(category)) labels.default_merge_mode = '默认周期规则';
  if (kind === 'machine') labels.category = '设备分类（只读）';
  return labels;
}
function fieldValue(kind, key, value) {
  if (value == null || value === '') return '未填写';
  const values = {
    category: { internal: '自制', external: '外协', both: '自制和外协都可' }, default_merge_mode: { separate: '分别设置', merged: '合并设置' },
    inactive_reason: { disabled: '停用', leave: '请假', pending_review: '待复核' }
  };
  if (key === 'status') return statusLabel(kind, value);
  if (key === 'category' && kind !== 'op_type') return String(value);
  return own(values, key) && own(values[key], value) ? values[key][value] : String(value);
}
// 新建工种时 category 来自所在的自制或外协列表；从工艺里新建工种不带归属，留空让用户明确选择。
function draft(kind, current, category = '') {
  const fields = current ? current.fields : {};
  const result = { business_code: current ? current.business_code : '', label: current ? current.label : '', fields: {}, relationships: {} };
  textFields[kind].forEach(key => { result.fields[key] = fields[key] == null ? '' : fields[key]; });
  if (kind === 'op_type' && !current) result.fields.category = category;
  if (statuses[kind]) result.fields.status = current ? current.status : '';
  if (kind === 'material') result.fields.stock_qty = fields.stock_qty == null ? '' : String(fields.stock_qty);
  if (kind === 'supplier') result.fields.default_days = fields.default_days == null ? '' : String(fields.default_days);
  // 已有记录的多选关系恒为编号数组、单选关系为编号或 null（core/services/workbench/resource/projection.py）。
  relations[kind].forEach(item => {
    const value = current ? current.relationships[item.key] : null;
    result.relationships[item.key] = value === null ? (item.multiple ? [] : '') : value;
  });
  return result;
}
function rebaseDraft(kind, value, before, after, category) {
  const original = draft(kind, before, category), fresh = draft(kind, after, category);
  ['business_code', 'label'].forEach(key => { if (value[key] !== original[key]) fresh[key] = value[key]; });
  ['fields', 'relationships'].forEach(section => {
    Object.keys(original[section]).forEach(key => {
      if (JSON.stringify(value[section][key]) !== JSON.stringify(original[section][key])) fresh[section][key] = value[section][key];
    });
  });
  return fresh;
}
function same(a, b) {
  if (Array.isArray(a) && Array.isArray(b)) return JSON.stringify(a.slice().sort()) === JSON.stringify(b.slice().sort());
  return a === b;
}
function input(kind, value, original, category) {
  if (!own(textFields, kind)) throw failure('不支持这类资料的表单。');
  const base = draft(kind, original, category), create = !original, errors = [];
  const result = {}, fields = {}, relationships = {};
  function bad(path, msg) { errors.push({ path, message: msg }); }
  if (create) {
    result.business_code = value.business_code.trim();
    if (!result.business_code) bad('business_code', '请填写编号。');
  }
  if (create || value.label !== base.label) {
    result.label = value.label.trim(); if (!result.label) bad('label', '请填写名称。');
  }
  const writable = textFields[kind].concat(statuses[kind] ? ['status'] : [],
    kind === 'material' ? ['stock_qty'] : kind === 'supplier' ? ['default_days'] : []);
  writable.filter(key => own(value.fields, key) && (key !== 'default_merge_mode' || ['external', 'both'].includes(value.fields.category))).forEach(key => {
    const v = value.fields[key];
    if (!create && same(v, base.fields[key])) return;
    if (key === 'stock_qty' || key === 'default_days') {
      if (typeof v === 'string' && v.trim() === '') {
        if (key === 'default_days' || !create) bad('fields.' + key, key === 'stock_qty' ? '库存不能清除；原值未知时可以不改。' : '请填写大于 0 的默认周期。');
        return;
      }
      const n = Number(v);
      if (!Number.isFinite(n) || n < 0 || (key === 'default_days' && n === 0)) bad('fields.' + key, key === 'stock_qty' ? '请填写有效的库存数量，不能小于 0。' : '请填写有效的周期天数，要大于 0。');
      else fields[key] = n;
    } else if (key === 'status') {
      if (!statuses[kind].some(item => item[0] === v)) bad('fields.status', '请明确选择状态。');
      else fields.status = v;
    } else if (key === 'category') {
      if (!['internal', 'external', 'both'].includes(v)) bad('fields.category', '请明确选择自制或外协。');
      else fields.category = v;
    } else if (key === 'default_merge_mode') {
      if (!['', 'separate', 'merged'].includes(v)) bad('fields.default_merge_mode', '请选择有效的周期规则。');
      else fields[key] = v === '' ? null : v;
    } else {
      const normalized = v.trim();
      if (!create || normalized) fields[key] = normalized === '' ? null : normalized;
    }
  });
  relations[kind].forEach(item => {
    const v = value.relationships[item.key];
    if (!create && same(v, base.relationships[item.key])) return;
    if (item.multiple) relationships[item.key] = v;
    else if (!create || v) relationships[item.key] = v === '' ? null : v;
  });
  if (Object.keys(fields).length) result.fields = fields;
  if (kind !== 'material' && Object.keys(relationships).length) result.relationships = relationships;
  if (errors.length) throw failure('请核对标红的项。', errors);
  return result;
}
// 失败已由 transport 抛出统一错误，这里只区分已完成的回执与仍待确认的结果。
function receipt(result) {
  if (!result || result.ok !== true || result.state === 'not_observed') return 'pending';
  // 命令结果已由 resource-api.js 的 terminal() 校验回执编号与 data。
  return ['committed', 'unchanged', 'partial'].includes(result.result) ? 'terminal' : 'pending';
}
// 只在命令已完成（receipt() 判为 terminal，data 已校验为对象）后调用；个人日历等命令不回 entity_ref，沿用意图里的记录编号。
function resultRef(result, fallback) {
  return result.data.entity_ref || fallback;
}
// category keeps the source list; the entity's category belongs to input.fields.
function createIntent(kind, action, ref, input, listCategory) {
  return {
    kind, action, ref, request_key: T.requestKey('resource'), input, category: listCategory,
    ...(kind === 'batch' && action === 'operation_update' ? { operation_ref: input.operation_ref } : {})
  };
}
const APSResourceContract = {
  nodes, statuses, relations, object, own, blocked,
  message, stale, fieldErrors, failure, statusLabel, resourceName, codeLabel, nameLabel, fieldLabels, fieldValue,
  draft, rebaseDraft, input, receipt, resultRef, createIntent
};
export {
  APSResourceContract,
  nodes, statuses, relations, object, own, blocked,
  message, stale, fieldErrors, failure, statusLabel, resourceName, codeLabel, nameLabel, fieldLabels, fieldValue,
  draft, rebaseDraft, input, receipt, resultRef, createIntent
};
export default APSResourceContract;
