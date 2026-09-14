(function () {
  'use strict';

  // Classic scripts: contract -> controls/session -> forms/tables -> workspace.
  // Queries keep QuerySuccess envelopes; failures may be returned or thrown.
  // choices(kind, {query,category,page,size,snapshot_ref}, signal) uses real refs.
  // openImport/openExport/openBulk/openCalendar/openCatalog receive
  // (kind, {refs,scope,entity?,onCommitted,onClosed?}, signal). Resolve {state:'cancelled'}
  // or {state:'opened'} for host-owned dialogs, or an explicit CommandResult.
  // openCatalog's opened dialog calls onClosed on cancel, onCommitted(receipt)
  // on success; its host owns uncertain requests and receipt reconciliation.
  // Optional summary(signal) -> QuerySuccess<{counts}>; count keys are part,
  // material, internal_op_types, machine, operator, external_op_types, supplier.
  const nodes = {
    process: {
      kind: 'part',
      label: '工艺',
      icon: 'database',
      chain: 'input',
      unit: '项'
    },
    material: {
      kind: 'material',
      label: '物料',
      icon: 'box',
      chain: 'input',
      unit: '条'
    },
    op_int: {
      kind: 'op_type',
      label: '自制工种',
      icon: 'wrench',
      category: 'internal',
      chain: 'internal',
      unit: '个'
    },
    machine: {
      kind: 'machine',
      label: '设备',
      icon: 'machine',
      chain: 'internal',
      unit: '台'
    },
    operator: {
      kind: 'operator',
      label: '人员',
      icon: 'users',
      chain: 'internal',
      unit: '人'
    },
    op_ext: {
      kind: 'op_type',
      label: '外协工种',
      icon: 'wrench',
      category: 'external',
      chain: 'external',
      unit: '个'
    },
    supplier: {
      kind: 'supplier',
      label: '供应商',
      icon: 'truck',
      chain: 'external',
      unit: '家'
    },
    calendar: {
      kind: 'calendar',
      label: '工作日历',
      icon: 'calendar-days',
      chain: 'global',
      unit: '项'
    }
  };
  const statuses = {
    material: [['active', '启用'], ['inactive', '停用']],
    machine: [['active', '可用'], ['maintain', '停机'], ['inactive', '停用'], ['unknown', '旧状态 / 原因未知']],
    operator: [['active', '在岗'], ['leave', '请假'], ['inactive', '停用'], ['unknown', '旧状态 / 原因未知']],
    supplier: [['active', '启用'], ['pending_review', '待复核'], ['inactive', '停用'], ['unknown', '旧状态 / 原因未知']]
  };
  const textFields = {
    material: ['spec', 'unit', 'remark'],
    op_type: ['category', 'default_merge_mode', 'remark'],
    machine: [],
    operator: [],
    supplier: []
  };
  const relations = {
    machine: [{
      key: 'op_type_ref',
      label: '绑定工种',
      kind: 'op_type',
      category: 'internal'
    }, {
      key: 'group_ref',
      label: '设备组',
      kind: 'machine_group',
      catalog: true
    }],
    operator: [{
      key: 'skill_refs',
      label: '技能工种',
      kind: 'op_type',
      category: 'internal',
      multiple: true
    }, {
      key: 'shift_profile_ref',
      label: '班次',
      kind: 'shift_profile',
      catalog: true
    }],
    supplier: [{
      key: 'op_type_refs',
      label: '可做外协工种',
      kind: 'op_type',
      category: 'external',
      multiple: true
    }]
  };
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const text = value => typeof value === 'string';
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
  function failure(message, fields = []) {
    const error = new Error(message);
    error.fields = fields;
    error.committed = false;
    return error;
  }
  function message(error) {
    return error && error.error && error.error.message || error && error.message || '读取失败，请刷新后重试。';
  }
  function fieldErrors(error) {
    const list = error && error.error && error.error.fields || error && error.fields || [];
    return Array.isArray(list) ? list.filter(row => row && text(row.path) && text(row.message)) : [];
  }
  function entity(value) {
    return object(value) && text(value.ref) && !!value.ref && text(value.business_code) && text(value.label) && (text(value.status) || value.status === null) && object(value.fields) && object(value.relationships) && Array.isArray(value.issues) && (value.write_context === null || object(value.write_context)) && (!own(value, 'availability') || value.fields.category === 'internal' && availability(value.availability));
  }
  function availability(value) {
    return object(value) && value.basis === 'enabled_authorized_matching' && count(value.machines) && count(value.operators);
  }
  function query(result, shape) {
    if (result && result.ok === false) throw result;
    if (!object(result) || result.ok !== true || result.schema_version !== 1 || !object(result.meta) || !['production', 'demo'].includes(result.meta.source) || result.meta.time_basis !== 'factory_local' || !text(result.meta.snapshot_ref) || !result.meta.snapshot_ref || !text(result.meta.request_ref) || !text(result.meta.as_of) || !Array.isArray(result.warnings)) throw failure('读到的数据不完整，请刷新重试。');
    if (shape === 'entity') {
      if (!entity(result.data)) throw failure('读到的详情不完整，请刷新后重试。');
    } else if (shape === 'summary') {
      if (!object(result.data) || !object(result.data.counts) || !Object.values(result.data.counts).every(value => value === null || count(value))) throw failure('读到的统计数据不完整，请刷新后重试。');
    } else {
      const data = result.data,
        page = data && data.page;
      if (!object(data) || !Array.isArray(data.entities) || !data.entities.every(entity) || new Set(data.entities.map(row => row.ref)).size !== data.entities.length || !object(page) || !count(page.number) || page.number < 1 || !count(page.size) || page.size < 1 || !count(page.total) || !count(page.pages) || !Array.isArray(page.sort) || data.entities.length > page.size || data.entities.length > page.total) throw failure('读到的列表或分页数据不完整，请刷新后重试。');
    }
    return result;
  }
  function blocked(context, kind, action, source) {
    if (source !== 'production') return '当前不是生产数据，不能保存。';
    if (!context || !text(context.write_token) || !context.write_token) return '还没读到可以保存的资料，请点「刷新最新资料」后重试。';
    const name = kind + '.' + action;
    if (!context.capabilities || context.capabilities[name] !== true) {
      const reasons = Array.isArray(context.blocked_reasons) ? context.blocked_reasons : [];
      const reason = reasons.find(row => row && (!row.action || row.action === name));
      return reason && reason.message || '当前记录不允许此操作。';
    }
    return '';
  }
  function requestKey() {
    if (!window.crypto || typeof window.crypto.getRandomValues !== 'function') throw failure('本次没有提交。当前浏览器不支持，请用 Chrome 打开本页。');
    const bytes = new Uint8Array(24);
    window.crypto.getRandomValues(bytes);
    return 'resource-' + Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');
  }
  function statusLabel(kind, status, fields = {}) {
    const match = (statuses[kind] || []).find(row => row[0] === status);
    let label = match ? match[1] : status === 'active' ? '启用' : '旧状态 / 原因未知';
    if (fields.inactive_reason === 'unknown' && status !== 'active' && status !== 'unknown') label += '（旧原因未知）';
    return label;
  }
  function resourceName(kind, category) {
    const opNames = {
      internal: '自制工种',
      external: '外协工种'
    };
    return kind === 'op_type' ? own(opNames, category) ? opNames[category] : '工种' : {
      material: '物料',
      machine: '设备',
      operator: '人员',
      supplier: '供应商'
    }[kind] || '资源';
  }
  function codeLabel(kind) {
    return {
      material: '物料编号',
      op_type: '工种编号',
      machine: '设备编号',
      operator: '工号'
    }[kind] || '编号';
  }
  function nameLabel(kind) {
    return kind === 'operator' ? '姓名' : kind === 'supplier' ? '供应商' : '名称';
  }
  function fieldLabels(kind, category) {
    const labels = {
      spec: '规格',
      unit: '单位',
      stock_qty: '库存数量',
      remark: '备注',
      category: '归属',
      status: '原状态',
      legacy_status: '原始状态（只读）',
      inactive_reason: '停用原因',
      default_days: '默认周期（天）'
    };
    if (kind === 'op_type' && category === 'internal') labels.remark = '产能备注';
    if (kind === 'op_type' && category === 'external') labels.default_merge_mode = '默认周期规则';
    if (kind === 'machine') labels.category = '设备分类（只读）';
    return labels;
  }
  function fieldValue(kind, key, value) {
    if (value == null || value === '') return '未填写';
    const values = {
      category: {
        internal: '自制',
        external: '外协'
      },
      default_merge_mode: {
        separate: '分别设置',
        merged: '合并设置'
      },
      inactive_reason: {
        unknown: '未知',
        disabled: '停用',
        leave: '请假',
        pending_review: '待复核'
      },
      legacy_status: {
        inactive: '原停用状态，原因未登记'
      }
    };
    if (key === 'status') return statusLabel(kind, value);
    if (key === 'category' && kind !== 'op_type') return String(value);
    return own(values, key) && own(values[key], value) ? values[key][value] : String(value);
  }
  function draft(kind, current, category) {
    const fields = current ? current.fields : {};
    const result = {
      business_code: current ? current.business_code : '',
      label: current ? current.label : '',
      fields: {},
      relationships: {}
    };
    (textFields[kind] || []).forEach(key => {
      result.fields[key] = fields[key] == null ? '' : fields[key];
    });
    if (kind === 'op_type' && !current) result.fields.category = category || '';
    if (statuses[kind]) result.fields.status = current ? current.status || 'unknown' : '';
    if (kind === 'material') result.fields.stock_qty = fields.stock_qty == null ? '' : String(fields.stock_qty);
    if (kind === 'supplier') result.fields.default_days = fields.default_days == null ? '' : String(fields.default_days);
    (relations[kind] || []).forEach(item => {
      const value = current && current.relationships[item.key];
      result.relationships[item.key] = item.multiple ? Array.isArray(value) ? value.slice() : [] : value || '';
    });
    return result;
  }
  function rebaseDraft(kind, value, before, after, category) {
    const original = draft(kind, before, category),
      fresh = draft(kind, after, category);
    ['business_code', 'label'].forEach(key => {
      if (value[key] !== original[key]) fresh[key] = value[key];
    });
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
    const base = draft(kind, original, category),
      create = !original,
      errors = [];
    const result = {},
      fields = {},
      relationships = {};
    function bad(path, msg) {
      errors.push({
        path,
        message: msg
      });
    }
    if (create) {
      result.business_code = value.business_code.trim();
      if (!result.business_code) bad('business_code', '请填写编号。');
    }
    if (create || value.label !== base.label) {
      result.label = value.label.trim();
      if (!result.label) bad('label', '请填写名称。');
    }
    const writable = (textFields[kind] || []).concat(statuses[kind] ? ['status'] : [], kind === 'material' ? ['stock_qty'] : kind === 'supplier' ? ['default_days'] : []);
    writable.filter(key => own(value.fields, key) && (key !== 'default_merge_mode' || value.fields.category === 'external')).forEach(key => {
      const v = value.fields[key];
      if (!create && same(v, base.fields[key])) return;
      if (key === 'stock_qty' || key === 'default_days') {
        if (typeof v === 'string' && v.trim() === '') {
          if (key === 'default_days' || !create) bad('fields.' + key, key === 'stock_qty' ? '库存不能清除；原值未知时可以不改。' : '请填写大于 0 的默认周期。');
          return;
        }
        const n = Number(v);
        if (!Number.isFinite(n) || n < 0 || key === 'default_days' && n === 0) bad('fields.' + key, key === 'stock_qty' ? '请填写有效的库存数量，不能小于 0。' : '请填写有效的周期天数，要大于 0。');else fields[key] = n;
      } else if (key === 'status') {
        if (!(statuses[kind] || []).some(item => item[0] === v && v !== 'unknown')) bad('fields.status', '请明确选择状态。');else fields.status = v;
      } else if (key === 'category') {
        if (!['internal', 'external'].includes(v)) bad('fields.category', '请明确选择自制或外协。');else fields.category = v;
      } else if (key === 'default_merge_mode') {
        if (!['', 'separate', 'merged'].includes(v)) bad('fields.default_merge_mode', '请选择有效的周期规则。');else fields[key] = v || null;
      } else {
        const normalized = v.trim();
        if (!create || normalized) fields[key] = normalized || null;
      }
    });
    (relations[kind] || []).forEach(item => {
      const v = value.relationships[item.key];
      if (!create && same(v, base.relationships[item.key])) return;
      if (item.multiple) relationships[item.key] = v.slice();else if (!create || v) relationships[item.key] = v || null;
    });
    if (Object.keys(fields).length) result.fields = fields;
    if (kind !== 'material' && Object.keys(relationships).length) result.relationships = relationships;
    if (errors.length) throw failure('请核对标红的项。', errors);
    return result;
  }
  function receipt(result) {
    if (result && result.state === 'not_recorded') return 'pending';
    if (result && result.ok === false) return result.committed === false ? 'rejected' : 'pending';
    if (!result || result.ok !== true) return 'pending';
    if (['committed', 'unchanged', 'partial'].includes(result.result) && text(result.receipt_ref) && result.receipt_ref && object(result.data) && Array.isArray(result.warnings)) return 'terminal';
    return 'pending';
  }
  function resultRef(result, fallback) {
    const data = result && result.data || {};
    return data.entity_ref || data.ref || data.entity && data.entity.ref || fallback;
  }
  window.APSResourceContract = {
    nodes,
    statuses,
    relations,
    object,
    own,
    entity,
    query,
    blocked,
    requestKey,
    message,
    fieldErrors,
    failure,
    statusLabel,
    resourceName,
    codeLabel,
    nameLabel,
    fieldLabels,
    fieldValue,
    availability,
    draft,
    rebaseDraft,
    input,
    receipt,
    resultRef
  };
})();
