(function () {
  'use strict';

  const C = window.APSResourceContract,
    M = window.APSResourceMaterial;
  const labels = {
    op_type: '工种',
    machine: '设备',
    operator: '人员',
    supplier: '供应商'
  };
  const scalar = value => value === null || typeof value === 'string' || typeof value === 'boolean' || typeof value === 'number' && Number.isFinite(value);
  const detailFields = {
    skill_details: {
      op_type_code: '工种编号',
      skill_level: '技能级别',
      is_primary: '是否主要',
      created_at: '创建时间'
    },
    machine_authorizations: {
      machine_code: '设备编号',
      operator_code: '工号',
      skill_level: '技能级别',
      is_primary: '是否主要',
      created_at: '创建时间'
    }
  };
  function publicValue(key, value) {
    if (C.own(detailFields, key)) {
      const fields = Object.keys(detailFields[key]);
      return Array.isArray(value) && value.every(item => C.object(item) && Object.keys(item).length === fields.length && fields.every(field => C.own(item, field) && scalar(item[field])));
    }
    if (['skill_codes', 'op_type_codes', 'explicit_op_type_codes'].includes(key)) return Array.isArray(value) && value.every(item => typeof item === 'string');
    return scalar(value);
  }
  function displayValue(key, value) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      if (key === 'default_days') return value + ' 天';
      if (key === 'default_hours') return value + ' 小时';
    }
    if (!C.own(detailFields, key)) return undefined;
    if (!value.length) return '未选';
    return value.map(item => Object.keys(detailFields[key]).map(field => {
      let text = item[field];
      if (text === null) text = '未填写';else if (text === '') text = '空白';else if (field === 'skill_level') text = text === 'normal' ? '普通' : String(text) + '（原值）';else if (field === 'is_primary') text = text === 'yes' ? '主要' : text === 'no' ? '非主要' : String(text) + '（原值）';
      return detailFields[key][field] + '：' + text;
    }).join(' · ')).join('；');
  }
  function category(kind, request) {
    if (kind !== 'op_type') return undefined;
    const value = request.scope && request.scope.category;
    if (!['internal', 'external'].includes(value)) throw C.failure('缺少工种类别，请关闭向导，重新打开自制或外协工种。');
    return value;
  }
  function columns(data) {
    if (!Array.isArray(data.columns) || !data.columns.length || !data.columns.every(item => C.object(item) && typeof item.key === 'string' && /^[a-z][a-z0-9_]*$/.test(item.key) && !['id', 'entity_key', 'revision', 'entity_ref', 'write_token'].includes(item.key) && typeof item.label === 'string' && item.label.trim() && item.label !== item.key) || new Set(data.columns.map(item => item.key)).size !== data.columns.length) throw C.failure('预检缺少完整的业务列名，本批没有提交。');
    const keys = new Set(data.columns.map(item => item.key));
    const facts = value => value === null || C.object(value) && Object.keys(value).every(key => keys.has(key) && publicValue(key, value[key]));
    if (!data.rows.every(row => facts(row.before) && facts(row.after) && Object.keys(row.changes).every(key => keys.has(key) && C.object(row.changes[key]) && C.own(row.changes[key], 'before') && C.own(row.changes[key], 'after') && publicValue(key, row.changes[key].before) && publicValue(key, row.changes[key].after)))) throw C.failure('预检明细里有未说明的列或不对外的关联内容，本批没有提交。');
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
      importHint: '按业务编号增量更新：编号已有的更新，没有的新增，文件以外的记录不会删除。空列或缺列保持原值；要清除某一项，请在格子里填 \\N（大写）。关联列填业务编号；要填多个，请按 ["OT1","OT2"] 这样用方括号和引号写，填 [] 表示清除全部关联。只读列只核对，不覆盖。',
      preview(raw, mode, expected, request) {
        const result = shared.preview(raw, mode, expected);
        columns(result.data);
        if (kind === 'op_type' && (!C.object(result.data.scope) || result.data.scope.category !== category(kind, request))) throw C.failure('预检工种类别与当前自制或外协范围不一致，本批没有提交。');
        return result;
      },
      exportPreview(raw, selection, request) {
        const result = shared.exportPreview(raw, selection);
        if (kind === 'op_type' && (!C.object(result.data.scope) || result.data.scope.category !== category(kind, request))) throw C.failure('导出预检工种类别与当前范围不一致，没有开始下载。');
        return result;
      }
    };
  }
  window.APSResourceFile = {
    create
  };
})();
