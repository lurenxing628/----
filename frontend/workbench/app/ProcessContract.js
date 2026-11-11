import C from './resource-contract.js';
import WorkbenchFormat from './WorkbenchFormat.js';

const text = value => typeof value === 'string';
const token = value => text(value) && value.length > 0;
const stages = [['', '全部', 'total'], ['route', '待导入路线', 'route'], ['source', '待定归属', 'source'], ['hours', '待填工时', 'hours'], ['ready', '已就绪', 'ready']];
const sorts = [['business_code', '图号'], ['label', '零件名称'], ['operation_count', '工序数量'], ['stage', '进度']];
const columns = sorts.map(([key, title], index) => ({ key, title, numeric: key === 'operation_count', width: [140, 150, 90, 350][index] }));
function ordering(scope) {
  const value = scope.sort === undefined ? 'business_code' : scope.sort;
  const rows = typeof value === 'string' ? [{ field: value, direction: scope.direction || 'asc' }] : value;
  if (!Array.isArray(rows) || rows.length > columns.length || !rows.every(row => C.object(row)
      && columns.some(column => column.key === row.field) && ['asc', 'desc'].includes(row.direction)
      && Object.keys(row).every(key => ['field', 'direction'].includes(key))) || new Set(rows.map(row => row.field)).size !== rows.length
      || Array.isArray(value) && scope.direction && scope.direction !== 'asc') throw C.failure('工艺排序不完整，请重新选择排序。');
  return rows;
}
function writeContext(value, action) {
  if (value === null) return !action;
  return C.object(value) && token(value.write_token)
    && (!action || C.object(value.capabilities) && value.capabilities['process.' + action] === true);
}
const groupIndex = groups => new Map(groups.map(row => [row.ref, row]));
function groupCycle(row, groups) {
  if (row.external_days_source !== 'group') return null;
  const group = groups.get(row.external_group_ref);
  return '整段 ' + String(group.total_days) + ' 天 · 工序 ' + group.start_sequence + ' 至 ' + group.end_sequence;
}
function list(result, scope) {
  const d = result.data, p = d.page;
  if (p.number !== scope.page || p.size !== scope.size)
    throw C.failure('读到的工艺列表不完整，请刷新后重试。');
  if (scope.snapshot_ref && result.meta.snapshot_ref !== scope.snapshot_ref)
    throw C.failure('翻页位置已失效，请回到第 1 页重新查询。');
  return result;
}
function detail(result, expectedRef) {
  const d = result.data;
  if (d.ref !== expectedRef)
    throw C.failure('读到的工艺详情不完整或不是这个零件，请刷新后重试。');
  return result;
}
function preview(result, expectedRef, body) {
  const d = result.data;
  if (d.part_ref !== expectedRef || d.mode !== body.mode
      || !writeContext(d.write_context, d.can_confirm_route ? 'route_confirm' : null))
    throw C.failure('读到的路线预检结果不完整或不是这个零件，本次不作为有效输入。');
  return result;
}
function stagePreview(result, expectedRef, action) {
  const d = result.data;
  if (!['source_confirm', 'groups_confirm'].includes(action) || d.action !== action || d.part_ref !== expectedRef
      || !writeContext(d.write_context, action))
    throw C.failure('归属检查与当前零件不一致，请重新检查。');
  return result;
}
function previewBody(mode, routeRaw, rows, snapshot) {
  let body;
  if (mode === 'text') body = { mode, route_raw: routeRaw };
  else {
    const fields = [];
    const input = rows.map((row, index) => {
      const raw = row.seq.trim(), digits = raw.replace(/^0+/, '') || '0';
      let seq = null;
      if (!/^\d+$/.test(raw) || digits === '0') fields.push({ path: 'rows.' + index + '.seq', message: '第 ' + (index + 1) + ' 行工序号必须是正整数。' });
      else if (digits.length > 16 || digits.length === 16 && digits > '9007199254740991')
        fields.push({ path: 'rows.' + index + '.seq', message: '第 ' + (index + 1) + ' 行工序号太大，请改用整条文字预检；原值没有改动。' });
      else seq = Number(digits);
      return { seq, op_type_name: row.op_type_name };
    });
    if (fields.length) throw C.failure('请核对逐行输入。', fields);
    body = { mode: 'rows', rows: input };
  }
  if (snapshot) body.snapshot_ref = snapshot;
  return body;
}
function sourceLabel(value) { return value === 'internal' ? '自制' : value === 'external' ? '外协' : '未归类'; }
function valueText(value) { return value === null ? '未填写' : WorkbenchFormat.number(value, { digits: 4, trim: true }) + (value <= 0 ? ' · 请复核' : ''); }
const stageNames = { route: '工艺路线', source: '归属', hours: '工时定额', ready: '已就绪' };
function workflowStateLabel(key, state) {
  if (state === 'confirmed') return '已确认';
  if (state === 'locked') return key === 'source' ? '待路线确认' : '待归属确认';
  if (state === 'present') return '已有记录，待确认';
  if (state === 'missing') return '待录入';
  if (state === 'unconfirmed') return '待确认';
  return '状态未明确';
}
function stageLabel(key) { return C.own(stageNames, key) ? stageNames[key] : '阶段未明确'; }
const APSProcessContract = { stages, columns, ordering, groupIndex, groupCycle, list, detail, preview, stagePreview, previewBody, sourceLabel, valueText, workflowStateLabel, stageLabel };

export {
  APSProcessContract,
  stages,
  columns,
  ordering,
  groupIndex,
  groupCycle,
  list,
  detail,
  preview,
  stagePreview,
  previewBody,
  sourceLabel,
  valueText,
  workflowStateLabel,
  stageLabel
};
export default APSProcessContract;
