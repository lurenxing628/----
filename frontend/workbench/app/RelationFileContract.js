import APSResourceContract from './resource-contract.js';
import APSResourceMaterial from './ResourceMaterialContract.js';

// 关联资料的文件契约：走 relation-files 路由，不做删除。
const C = APSResourceContract, M = APSResourceMaterial;
const labels = { operator_machine: '可操作设备' };
const skills = { beginner: '初级', normal: '普通', expert: '熟练' };
const primaries = { yes: '是', no: '否' };
function displayValue(key, value) {
  if (key === 'skill_level') return C.own(skills, value) ? skills[value] : String(value) + '（原值）';
  if (key === 'is_primary') return C.own(primaries, value) ? primaries[value] : String(value) + '（原值）';
  return undefined;
}
function create(kind) {
  if (!C.own(labels, kind)) throw C.failure('不支持这类关联资料的文件操作。');
  const label = labels[kind];
  const shared = M.create(kind, label);
  return {
    ...shared,
    displayValue,
    paths: {
      import: 'relation-files/' + kind + '/preview', export: 'relation-files/' + kind + '/export-preview',
      download: 'relation-files/' + kind + '/export', template: 'relation-files/' + kind + '/template'
    },
    // 勾选的是人员，一个人可能有多台设备，导出行数本来就不等于勾选条数。
    rowsMatchSelection: false,
    scopeLabel: '人员',
    confirmationHint: '这一行会牵动同一个人的其他设备，请核对修改前后内容。',
    acknowledgeHint: '已核对主操设备的连带影响和修改前后内容，确认这些更新。',
    templateHint: '空白表头模板，只有列名，没有示例数据。',
    importHint: '按「工号 + 设备编号」增量更新：已有的更新，没有的新增，文件里没写的关系不会删除。'
      + '空格子保持原值；技能等级填初级 / 普通 / 熟练，主操设备填是 / 否。同一个人只能有一台主操设备，'
      + '把主操给了新设备，原来的会自动变成非主操。只读列仅供参考，不导入。'
  };
}
const APSRelationFile = { create, labels };
export { APSRelationFile, create, labels };
export default APSRelationFile;
