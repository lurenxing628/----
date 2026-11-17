import C from './resource-contract.js';
import M from './ResourceMaterialContract.js';
import { failure } from './shared/contract/kit.js';
import WorkbenchTerms from './WorkbenchTerms.js';

// 关联资料的文件契约：走 relation-files 路由，不做删除。
const labels = { operator_machine: '可操作设备' };
function displayValue(key, value) {
  if (key === 'skill_level') return WorkbenchTerms.skill_levels[value];
  if (key === 'is_primary') return WorkbenchTerms.primary_machine[value];
  return undefined;
}
function create(kind) {
  if (!C.own(labels, kind)) throw failure('不支持这类关联资料的文件操作。');
  const label = labels[kind];
  // 勾选的是人员，一个人可能有多台设备，导出行数本来就不等于勾选条数。
  const shared = M.create(kind, label, { rowsMatchSelection: false });
  return {
    ...shared,
    displayValue,
    paths: {
      import: 'relation-files/' + kind + '/preview', export: 'relation-files/' + kind + '/export-preview',
      download: 'relation-files/' + kind + '/export', template: 'relation-files/' + kind + '/template'
    },
    scopeLabel: '人员',
    templateHint: '空白表头模板，只有列名，没有示例数据。',
    importHint: '按「工号 + 设备编号」增量更新：已有的更新，没有的新增，文件里没写的关系不会删除。'
      + '空格子保持原值；技能等级填初级 / 普通 / 熟练，主操设备填是 / 否。一个人可以有多台主操设备，'
      + '每一行只改这一台设备。只读列仅供参考，不导入。'
  };
}
const APSRelationFile = { create, labels };
export { APSRelationFile, create, labels };
export default APSRelationFile;
