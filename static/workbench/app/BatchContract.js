(function () {
  'use strict';

  const C = window.APSResourceContract,
    object = C.object;
  const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
  const finite = value => value === null || typeof value === 'number' && Number.isFinite(value);
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const text = value => typeof value === 'string',
    nullableText = value => value === null || text(value);
  const fields = ['quantity', 'due_date', 'priority', 'ready_status', 'ready_date', 'remark'];
  const fieldNames = {
    quantity: '数量',
    due_date: '交期',
    priority: '优先级',
    ready_status: '齐套显示',
    ready_date: '齐套日期',
    remark: '备注'
  };
  const actions = ['create', 'update', 'delete', 'operation_update', 'sync_confirm', 'bulk_confirm', 'import_confirm'];
  const priority = [['normal', '普通'], ['urgent', '急件'], ['critical', '特急']];
  const ready = [['yes', '齐套'], ['partial', '部分齐套'], ['no', '未齐套']];
  const statuses = [['pending', '待排'], ['scheduled', '已排'], ['processing', '加工中'], ['completed', '已完成'], ['cancelled', '已取消']];
  const columns = [['business_code', '批次号', 155], ['part_no', '图号', 190], ['quantity', '数量', 80], ['due_date', '交期', 140], ['progress', '工序进度', 170], ['priority', '优先级', 115], ['ready_status', '齐套显示', 120], ['status', '状态', 115]];
  const issueRows = rows => Array.isArray(rows) && rows.every(row => object(row) && text(row.code) && text(row.message));
  function context(value) {
    return value === null || object(value) && text(value.write_token) && !!value.write_token && object(value.capabilities) && Array.isArray(value.blocked_reasons);
  }
  function operation(row) {
    return object(row) && ref(row.ref) && row.operation_ref === row.ref && text(row.business_code) && text(row.label) && (Number.isSafeInteger(row.sequence) || text(row.sequence)) && nullableText(row.source) && nullableText(row.status) && typeof row.completed === 'boolean' && row.completed === (row.status === 'completed') && ['setup_hours', 'unit_hours', 'external_days'].every(key => finite(row[key])) && ['machine_ref', 'operator_ref', 'supplier_ref', 'op_type_ref'].every(key => row[key] === null || ref(row[key])) && object(row.resources) && (row.external_group === null || object(row.external_group) && ref(row.external_group.ref) && finite(row.external_group.total_days)) && issueRows(row.issues) && typeof row.editable === 'boolean';
  }
  function entity(row) {
    return C.entity(row) && ref(row.ref) && context(row.write_context) && object(row.fields) && finite(row.fields.quantity) && fields.slice(1).every(key => nullableText(row.fields[key])) && ref(row.relationships.part_ref) && text(row.relationships.part_no) && text(row.relationships.part_name) && ['operation_count', 'completed_count', 'gap_count', 'plan_reference_count', 'execution_reference_count', 'material_requirement_count'].every(key => count(row.relationships[key])) && Array.isArray(row.operations) && row.operations.every(operation) && new Set(row.operations.map(op => op.ref)).size === row.operations.length && row.relationships.operation_count === row.operations.length && row.relationships.completed_count === row.operations.filter(op => op.completed).length && row.all_operations_complete === (!!row.operations.length && row.operations.every(op => op.completed)) && typeof row.protected === 'boolean' && issueRows(row.issues);
  }
  function list(result, scope) {
    C.query(result, 'list');
    const d = result.data,
      p = d.page;
    if (!d.entities.every(entity) || !context(d.create_context) || !d.create_context || p.number !== scope.page || p.size !== scope.size || p.pages !== Math.max(1, Math.ceil(p.total / p.size)) || p.sort.length !== 1 || p.sort[0].field !== scope.sort || p.sort[0].direction !== scope.direction || scope.snapshot_ref && result.meta.snapshot_ref !== scope.snapshot_ref) throw C.failure('批次列表字段或范围不完整，请重新读取。');
    return result;
  }
  function detail(result, expected) {
    C.query(result, 'entity');
    const d = result.data;
    if (!entity(d) || d.ref !== expected || !object(d.materials) || !Array.isArray(d.materials.requirements) || !d.materials.requirements.every(row => object(row) && ref(row.material_ref) && finite(row.required_quantity) && finite(row.available_quantity)) || !object(d.template)) throw C.failure('批次详情与实际对象不一致或字段不完整。');
    return result;
  }
  function receipt(result, action, expected) {
    if (C.receipt(result) !== 'terminal') throw C.failure('批次保存结果尚未核实。');
    const data = result.data;
    const valid = ['bulk_confirm', 'import_confirm'].includes(action) ? Array.isArray(data.items) && data.items.length === data.count && data.items.every(row => ref(row.entity_ref) && ['committed', 'unchanged', 'skipped'].includes(row.result)) : ref(data.entity_ref) && (action === 'create' || data.entity_ref === expected);
    if (!valid) {
      const error = C.failure('回执与批次对象不一致，结果待核实。');
      error.committed = 'unknown';
      throw error;
    }
    return result;
  }
  function preview(result, action, expectedRef, input) {
    const data = result && result.data,
      name = 'batch.' + action + '_confirm';
    let valid = object(result) && result.ok === true && result.schema_version === 1 && object(result.meta) && result.meta.source === 'production' && object(data) && data.operation === name && text(data.preview_ref) && /^[A-Za-z0-9_-]{32}$/.test(data.preview_ref) && context(data.write_context) && data.write_context && data.write_context.capabilities[name] === true && data.commit_policy === 'atomic';
    if (valid && action === 'bulk') valid = data.action === input.action && Array.isArray(data.rows) && data.count === input.refs.length && data.rows.length === data.count && new Set(data.rows.map(row => row.entity_ref)).size === data.count && data.rows.every(row => input.refs.includes(row.entity_ref) && entity(row.before) && row.before.ref === row.entity_ref && (input.action === 'delete' ? row.after === null : object(row.after) && object(row.after.fields) && Array.isArray(row.after.operations)));
    if (valid && action === 'sync') valid = data.entity_ref === expectedRef && data.strict_mode === input.strict_mode && Array.isArray(data.before) && data.before.every(operation) && Array.isArray(data.after) && data.after.every(row => object(row) && text(row.label) && ['setup_hours', 'unit_hours', 'external_days'].every(key => finite(row[key])));
    if (!valid) throw C.failure('批次预览与所选对象或操作不一致，不能确认。');
    return data;
  }
  function reason(ctx, action, source) {
    if (source !== 'production') return '当前不是可写生产资料。';
    if (!ctx || ctx.capabilities['batch.' + action] !== true) return (ctx && ctx.blocked_reasons.find(row => row.action === 'batch.' + action) || {}).message || '当前资料不允许此操作。';
    return '';
  }
  function label(key, value) {
    const options = {
      priority,
      ready_status: ready,
      status: statuses
    }[key];
    return value === null || value === undefined || value === '' ? '未填写' : options ? (options.find(row => row[0] === value) || ['', '原标记待核对'])[1] : String(value);
  }
  function draft(entity) {
    return entity ? Object.fromEntries(fields.map(key => [key, entity.fields[key] == null ? '' : String(entity.fields[key])])) : {
      business_code: '',
      part_ref: '',
      quantity: '',
      due_date: '',
      priority: 'normal',
      ready_status: 'yes',
      ready_date: '',
      remark: ''
    };
  }
  function input(value, original) {
    const errors = inputErrors(value, original);
    if (errors.length) throw C.failure('请检查标记的批次字段。', errors);
    const patch = {};
    for (const key of fields) {
      if (original && String(original.fields[key] == null ? '' : original.fields[key]) === value[key]) continue;
      let next = value[key];
      if (key === 'quantity') {
        next = Number(next);
      } else if (key.endsWith('_date')) {
        next = next === '' ? null : next;
      } else if (key === 'remark') next = next.trim() || null;
      patch[key] = next;
    }
    if (original) return {
      fields: patch
    };
    return {
      business_code: value.business_code.trim(),
      part_ref: value.part_ref,
      fields: patch
    };
  }
  function inputErrors(value, original) {
    const errors = [];
    if (!original) {
      if (!value.business_code.trim()) errors.push({
        path: 'business_code',
        message: '请填写批次号。'
      });
      if (!ref(value.part_ref)) errors.push({
        path: 'part_ref',
        message: '请选择图号。'
      });
    }
    for (const key of fields) {
      if (original && String(original.fields[key] == null ? '' : original.fields[key]) === value[key]) continue;
      const next = value[key];
      if (key === 'quantity' && (!/^[0-9]+$/.test(next) || !Number.isSafeInteger(Number(next)) || Number(next) <= 0)) errors.push({
        path: 'fields.quantity',
        message: '数量必须是正整数。'
      });
      if (key.endsWith('_date') && next !== '' && !/^\d{4}-\d{2}-\d{2}$/.test(next)) errors.push({
        path: 'fields.' + key,
        message: '日期格式应为 YYYY-MM-DD。'
      });
    }
    return errors;
  }
  window.APSBatchContract = {
    ref,
    context,
    operation,
    entity,
    list,
    detail,
    receipt,
    preview,
    reason,
    label,
    draft,
    input,
    inputErrors,
    fields,
    fieldNames,
    actions,
    priority,
    ready,
    statuses,
    columns
  };
})();
