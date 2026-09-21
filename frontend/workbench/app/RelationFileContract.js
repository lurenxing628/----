(function () {
  'use strict';
  // Load after ResourceMaterialContract.js. 关联资料的文件契约：走 relation-files 路由，不做删除。
  const C = window.APSResourceContract, M = window.APSResourceMaterial;
  const labels = { operator_machine: '可操作设备' };
  const skills = { beginner: '初级', normal: '普通', expert: '熟练' };
  const primaries = { yes: '是', no: '否' };
  const scalar = value => value === null || typeof value === 'string';
  function displayValue(key, value) {
    if (key === 'skill_level') return C.own(skills, value) ? skills[value] : String(value) + '（原值）';
    if (key === 'is_primary') return C.own(primaries, value) ? primaries[value] : String(value) + '（原值）';
    return undefined;
  }
  function columns(data) {
    if (!Array.isArray(data.columns) || !data.columns.length || !data.columns.every(item => C.object(item)
        && typeof item.key === 'string' && /^[a-z][a-z0-9_]*$/.test(item.key)
        && !['id', 'entity_key', 'revision', 'entity_ref', 'write_token'].includes(item.key)
        && typeof item.label === 'string' && item.label.trim() && item.label !== item.key)
        || new Set(data.columns.map(item => item.key)).size !== data.columns.length)
      throw C.failure('预检缺少完整的业务列名，本批没有提交。');
    const keys = new Set(data.columns.map(item => item.key));
    const facts = value => value === null || C.object(value) && Object.keys(value).every(key => keys.has(key) && scalar(value[key]));
    if (!data.rows.every(row => facts(row.before) && facts(row.after) && Object.keys(row.changes).every(key => keys.has(key)
        && C.object(row.changes[key]) && C.own(row.changes[key], 'before') && C.own(row.changes[key], 'after')
        && scalar(row.changes[key].before) && scalar(row.changes[key].after))))
      throw C.failure('预检明细里有未说明的列，本批没有提交。');
  }
  function notes(data) {
    if (!data.rows.every(row => Array.isArray(row.notes) && row.notes.every(note => typeof note === 'string' && note.trim())))
      throw C.failure('预检的逐行说明不完整，本批没有提交。');
    // 需要人工核对的行必须说清原因，否则对话框只会让人盲勾。
    if (!data.rows.every(row => !row.requires_confirmation || row.notes.length))
      throw C.failure('预检里有需要核对的行却没有写明原因，本批没有提交。');
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
        + '把主操给了新设备，原来的会自动变成非主操。只读列仅供参考，不导入。',
      preview(raw, mode, expected, request) {
        const result = shared.preview(raw, mode, expected, request);
        columns(result.data);
        notes(result.data);
        return result;
      }
    };
  }
  window.APSRelationFile = { create, labels };
})();
