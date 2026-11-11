import APSResourceContract from './resource-contract.js';
import APSResourceMaterial from './ResourceMaterialContract.js';
import WorkbenchFormat from './WorkbenchFormat.js';

const C = APSResourceContract, M = APSResourceMaterial;
const labels = { op_type: '工种', machine: '设备', operator: '人员', supplier: '供应商' };
const detailFields = {
  skill_details: { op_type_code: '工种编号', skill_level: '技能级别', is_primary: '是否主要', created_at: '创建时间' },
  machine_authorizations: { machine_code: '设备编号', operator_code: '工号', skill_level: '技能级别', is_primary: '是否主要', created_at: '创建时间' }
};
function displayValue(key, value) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    if (key === 'default_days') return WorkbenchFormat.number(value, { digits: 4, trim: true }) + ' 天';
    if (key === 'default_hours') return WorkbenchFormat.hours(value, { digits: 4, trim: true });
  }
  if (!C.own(detailFields, key)) return undefined;
  if (!value.length) return '未选';
  return value.map(item => Object.keys(detailFields[key]).map(field => {
    let text = item[field];
    if (text === null) text = '未填写';
    else if (text === '') text = '空白';
    else if (field === 'skill_level') text = text === 'normal' ? '普通' : String(text) + '（原值）';
    else if (field === 'is_primary') text = text === 'yes' ? '主要' : text === 'no' ? '非主要' : String(text) + '（原值）';
    return detailFields[key][field] + '：' + text;
  }).join(' · ')).join('；');
}
function category(kind, request) {
  if (kind !== 'op_type') return undefined;
  const value = request.scope && request.scope.category;
  if (!['internal', 'external'].includes(value)) throw C.failure('缺少工种类别，请关闭向导，重新打开自制或外协工种。');
  return value;
}
function create(kind) {
  if (!C.own(labels, kind)) throw C.failure('不支持这类基础资料的文件操作。');
  const shared = M.create(kind, labels[kind]);
  return {
    ...shared,
    displayValue,
    resourceLabel: value => C.resourceName(kind, value),
    category: request => category(kind, request),
    templateHint: '空白表头模板，不含示例数据。空列不改动；要清除某一项，请在格子里填 \\N（大写）。',
    importHint: '按业务编号增量更新：编号已有的更新，没有的新增，文件以外的记录不会删除。空列或缺列保持原值；要清除某一项，请在格子里填 \\N（大写）。关联列填业务编号；多个编号用顿号分开，例如 OT1、OT2，填清除表示移除全部关联。只读列仅供参考，不导入；设备权限需在人员详情设置。',
    preview(raw, mode, expected, request) {
      const result = shared.preview(raw, mode, expected);
      if (kind === 'op_type') {
        const invalid = mode === 'import'
          ? result.data.category !== category(kind, request) || C.own(result.data, 'scope')
          : !C.object(result.data.scope) || result.data.scope.category !== category(kind, request);
        if (invalid)
          throw C.failure('预检工种类别与当前自制或外协范围不一致，本批没有提交。');
      }
      return result;
    },
    exportPreview(raw, selection, request) {
      const result = shared.exportPreview(raw, selection);
      if (kind === 'op_type' && (!C.object(result.data.scope) || result.data.scope.category !== category(kind, request)))
        throw C.failure('导出预检工种类别与当前范围不一致，没有开始下载。');
      return result;
    }
  };
}
const APSResourceFile = { create };
export { APSResourceFile, create };
export default APSResourceFile;
