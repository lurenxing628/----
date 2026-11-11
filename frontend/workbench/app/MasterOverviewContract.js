const domains = [['part', '零件'], ['route', '工艺路线'], ['opType', '工种'], ['equipment', '设备'],
  ['personnel', '人员'], ['material', '物料'], ['supplier', '供应商'], ['calendar', '日历配置']];
const statuses = { attention: '待维护', checked: '已检查', inactive: '停用', unknown: '未检查' };
const domainIds = domains.map(row => row[0]), statusKeys = Object.keys(statuses);
const defaults = { view: 'issues', domain: 'all', status: 'all', query: '', sort: 'issue_count', direction: 'desc', size: 20, column_filters: {} };
const common = [['business_code', '编号', 148], ['label', '名称', 178], ['domain', '资料类别', 96]];
const columns = {
  entities: common.concat([['status', '检查状态', 92], ['filled_fields', '已填项', 80], ['checked_fields', '检查项', 80],
    ['relation_count', '关联项', 76], ['issue_count', '待维护项', 82], ['summary', '检查结果', 214]]),
  issues: common.concat([['title', '待维护项', 180], ['evidence', '当前记录', 260]])
};
const object = value => !!value && typeof value === 'object' && !Array.isArray(value);
const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
const issueKey = value => typeof value === 'string' && value.length > 0;
function fail(message) { throw new Error(message || '读到的基础资料不完整，请刷新后重试。'); }
function canonical(value) {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (object(value)) return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
  return JSON.stringify(value);
}
function scope(value) {
  if (!object(value) || Object.keys(value).some(key => !Object.hasOwnProperty.call(defaults, key))) fail('基础资料的筛选条件不正确，当前筛选没有变化。请重新选择。');
  if (value.column_filters !== undefined && !object(value.column_filters)) fail('列筛选条件格式不对，当前筛选没有变化。请重新填写。');
  const result = { ...defaults, ...value, column_filters: { ...value.column_filters } };
  if (!['issues', 'entities'].includes(result.view) || result.domain !== 'all' && !domainIds.includes(result.domain)
    || result.status !== 'all' && !statusKeys.includes(result.status) || ![20, 50, 100].includes(result.size)
    || !['business_code', 'label', 'issue_count', 'relation_count'].includes(result.sort) || !['asc', 'desc'].includes(result.direction)
    || typeof result.query !== 'string' || result.query.length > 1000) fail('基础资料的筛选范围无效，当前筛选没有变化。请重新选择。');
  const allowed = columns[result.view].map(row => row[0]).concat(result.view === 'issues' ? ['status', 'action', 'rule'] : []);
  if (Object.keys(result.column_filters).some(key => !allowed.includes(key) || typeof result.column_filters[key] !== 'string' || result.column_filters[key].length > 1000)) fail('列筛选条件无效，当前筛选没有变化。请重新填写。');
  return result;
}
function target(value) {
  if (!object(value) || !['process', 'batches'].includes(value.view) || !object(value.context)) fail('维护目标不完整。');
  const c = value.context;
  if (value.view === 'batches') { if (!ref(c.entity_ref)) fail('这条批次记录已失效，请重新选择。'); return value; }
  if (c.source !== 'production' || !['material', 'op_type', 'machine', 'operator', 'supplier', 'part', 'calendar'].includes(c.kind)) fail('维护目标的来源或类型不正确，页面没有跳转。请刷新后重试。');
  if (value.unavailable_reason !== undefined) { if (typeof value.unavailable_reason !== 'string' || !value.unavailable_reason) fail(); return value; }
  if (c.kind === 'calendar') {
    if (typeof c.month !== 'string' || !/^\d{4}-\d{2}$/.test(c.month) || typeof c.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(c.date)) fail('工作日历的定位日期不正确，页面没有跳转。请刷新后重试。');
  } else if (!ref(c.entity_ref)) fail('这条记录已失效，请重新选择。');
  if (c.category !== undefined && (c.kind !== 'op_type' || !['internal', 'external'].includes(c.category))) fail('工种类别不正确。');
  if (c.stage !== undefined && !['route', 'source', 'hours'].includes(c.stage)) fail('工艺阶段不正确。');
  for (const key of ['template_operation_ref', 'template_external_group_ref']) if (c[key] !== undefined && !ref(c[key])) fail('模板定位编号不正确，页面没有跳转。请刷新后重试。');
  return value;
}
function bound(result) {
  if (!result.meta.snapshot_ref) fail();
}
function list(result, expected, snapshot) {
  bound(result);
  const data = result.data;
  if (expected && canonical(data.scope) !== canonical(expected)) fail('读到的数据和当前筛选不一致，请刷新后重试。');
  if (snapshot && result.meta.snapshot_ref !== snapshot) fail('数据已更新，请刷新后重试。刚才的选择已保留。');
  if (!object(data.page) || !object(data.scope)) fail();
  return result;
}
function detail(result, expected, selection, section, snapshot) {
  bound(result);
  const data = result.data;
  if (!object(data)) fail('详情和所选资料对不上，页面没有切换。请刷新后重试。');
  if (canonical(data.scope) !== canonical(expected) || result.meta.snapshot_ref !== snapshot
    || data.section !== section || !object(data.entity) || data.entity.ref !== selection.entity_ref || data.entity.domain !== selection.domain) fail('详情和所选资料对不上，页面没有切换。请刷新后重试。');
  return result;
}
function value(input) {
  if (input === null || input === undefined) return '未知';
  if (Array.isArray(input)) return input.length ? input.map(value).join('、') : '无';
  if (object(input)) {
    const keys = Object.keys(input);
    return keys.length ? keys.map(key => key + '：' + value(input[key])).join('；') : '无';
  }
  return String(input);
}
function cell(item, column) {
  if (column === 'domain') return (domains.find(row => row[0] === item.domain) || [null, '批次'])[1];
  if (column === 'status') return statuses[item.status];
  return value(item[column]);
}
const APSMasterOverviewContract = { domains, statuses, columns, scope, target, list, detail, value, cell, ref, issueKey, fail, canonical };

export {
  APSMasterOverviewContract,
  domains,
  statuses,
  columns,
  scope,
  target,
  list,
  detail,
  value,
  cell,
  ref,
  issueKey,
  fail,
  canonical
};
export default APSMasterOverviewContract;
