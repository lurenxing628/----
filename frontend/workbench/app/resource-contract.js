import T from './shared/network/transport.js';
import { nonempty, failure } from './shared/contract/kit.js';
import WorkbenchTerms from './WorkbenchTerms.js';

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
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
// 统一错误对象只有一种形状，由 shared/contract/kit.js 的 failure 构造。
// 服务端说这次操作依据的资料已过期：需要用户刷新，不能静默复位后照旧重提。页面专属的过期码由调用方追加。
const staleCodes = ['stale_write', 'snapshot_stale'];
// stale / fieldErrors 的调用方在还没有错误时会传 null；字段行的形状已在 transport.envelopeFailure 校验。
const stale = (error, extraCodes = []) => !!error && (staleCodes.includes(error.code) || extraCodes.includes(error.code));
// 字段错误的唯一读取口径：后端 fields 与本地校验用同一套路径（从请求 input 算起、点号连接，不加 input. 前缀），
// 一个路径对应页面上的一个输入框；rows 是统一错误对象的 fields 或本地拼好的同形行，同一文案只读一次。
const fieldErrors = error => error && Array.isArray(error.fields) ? error.fields : [];
const fieldMessages = (rows, path) => Array.from(new Set(rows.filter(row => row.path === path).map(row => row.message)));
function blocked(context, kind, action, source) {
  if (source !== 'production') return '当前不是生产数据，不能保存。';
  if (!context || !nonempty(context.write_token)) return '还没读到可以保存的资料，请点「刷新最新资料」后重试。';
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
// 词表里的三项取值受库表 CHECK 约束（OpTypes.category、WorkbenchOpTypePolicies.default_merge_mode、人员与供应商资料的
// inactive_reason），导入预览的提议值也先过同一套资料准入，词表外的码进不来；其余项是数字或自由文本，照原值显示。
function fieldValue(kind, key, value) {
  if (value == null || value === '') return '未填写';
  const values = {
    category: WorkbenchTerms.op_type_categories, default_merge_mode: WorkbenchTerms.merge_modes,
    inactive_reason: { disabled: '停用', leave: '请假', pending_review: '待复核' }
  };
  if (key === 'status') return statusLabel(kind, value);
  if (key === 'category' && kind !== 'op_type') return String(value);
  return own(values, key) ? values[key][value] : String(value);
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
        if (key === 'default_days' || !create) bad('fields.' + key, key === 'stock_qty' ? '库存不能清除；原值未知时可以不改。' : '请填写默认周期。');
        return;
      }
      // 只把输入转成数；值域由后端校验，422 带字段路径标红。
      const n = Number(v);
      if (!Number.isFinite(n)) bad('fields.' + key, key === 'stock_qty' ? '请填写有效的库存数量。' : '请填写有效的周期天数。');
      else fields[key] = n;
    } else if (key === 'status') {
      if (v === '') bad('fields.status', '请明确选择状态。');
      else fields.status = v;
    } else if (key === 'category') {
      if (v === '') bad('fields.category', '请明确选择自制或外协。');
      else fields.category = v;
    } else if (key === 'default_merge_mode') {
      fields[key] = v === '' ? null : v;
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
  if (errors.length) throw failure('请核对标红的项。', { fields: errors });
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
// 批量删除回执带 deleted_count 与逐条 rows；其他回执没有删除记录，给空数组。只在 receipt() 判为 terminal 后调用。
function removedRefs(result) {
  return own(result.data, 'deleted_count') ? result.data.rows.map(row => row.entity_ref) : [];
}
// category keeps the source list; the entity's category belongs to input.fields.
function createIntent(kind, action, ref, input, listCategory) {
  return {
    kind, action, ref, request_key: T.requestKey('resource'), input, category: listCategory,
    ...(kind === 'batch' && action === 'operation_update' ? { operation_ref: input.operation_ref } : {})
  };
}
const APSResourceContract = {
  nodes, statuses, relations, own, blocked,
  stale, fieldErrors, fieldMessages, statusLabel, resourceName, codeLabel, nameLabel, fieldLabels, fieldValue,
  draft, rebaseDraft, input, receipt, resultRef, removedRefs, createIntent
};
export {
  APSResourceContract,
  nodes, statuses, relations, own, blocked,
  stale, fieldErrors, fieldMessages, statusLabel, resourceName, codeLabel, nameLabel, fieldLabels, fieldValue,
  draft, rebaseDraft, input, receipt, resultRef, removedRefs, createIntent
};
export default APSResourceContract;
