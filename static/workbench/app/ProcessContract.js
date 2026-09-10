(function () {
  'use strict';

  const C = window.APSResourceContract;
  const text = value => typeof value === 'string';
  const nullableText = value => value === null || text(value);
  const ref = value => text(value) && /^[0-9a-f]{48}$/.test(value);
  const token = value => text(value) && value.length > 0;
  const nullableRef = value => value === null || ref(value);
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const storedSequence = value => Number.isSafeInteger(value) || text(value) && value.length > 0;
  function sequence(value) {
    if (typeof value === 'number') return Number.isSafeInteger(value) && value > 0;
    return text(value) && /^[1-9]\d*$/.test(value) && (value.length < 19 || value.length === 19 && value <= '9223372036854775807');
  }
  const number = value => value === null || Number.isFinite(value);
  const issues = value => Array.isArray(value) && value.every(row => C.object(row) && text(row.code) && text(row.message));
  const source = value => value === null || ['internal', 'external'].includes(value);
  const stages = [['', '全部', 'total'], ['route', '待导入路线', 'route'], ['source', '待分拣', 'source'], ['hours', '待填工时', 'hours'], ['ready', '已就绪', 'ready']];
  const sorts = [['business_code', '图号'], ['label', '零件名称'], ['operation_count', '工序数量'], ['stage', '进度']];
  const columns = sorts.map(([key, title], index) => ({
    key,
    title,
    numeric: key === 'operation_count',
    width: [160, 190, 118, 390][index]
  }));
  function ordering(scope) {
    const value = scope.sort === undefined ? 'business_code' : scope.sort;
    const rows = typeof value === 'string' ? [{
      field: value,
      direction: scope.direction || 'asc'
    }] : value;
    if (!Array.isArray(rows) || rows.length > columns.length || !rows.every(row => C.object(row) && columns.some(column => column.key === row.field) && ['asc', 'desc'].includes(row.direction) && Object.keys(row).every(key => ['field', 'direction'].includes(key))) || new Set(rows.map(row => row.field)).size !== rows.length || Array.isArray(value) && scope.direction && scope.direction !== 'asc') throw C.failure('工艺排序不完整，请重新选择排序。');
    return rows;
  }
  function capabilities(value) {
    return C.object(value) && ['route_preview', 'create', 'delete', 'stage_confirm', 'import', 'export'].every(key => typeof value[key] === 'boolean');
  }
  function entity(value) {
    if (!C.entity(value) || !ref(value.ref) || value.status !== null || !writeContext(value.write_context)) return false;
    const w = value.workflow;
    return ['route_raw', 'route_parsed', 'remark'].every(key => nullableText(value.fields[key])) && issues(value.issues) && ['batch_count', 'operation_count', 'internal_count', 'external_count', 'unclassified_count'].every(key => count(value.relationships[key])) && C.object(w) && ['legacy', 'managed'].includes(w.origin) && ['route', 'source', 'hours', 'ready'].includes(w.stage) && typeof w.ready === 'boolean' && stamp(w.route, ['present', 'missing', 'unconfirmed', 'confirmed']) && stamp(w.source, ['unconfirmed', 'locked', 'confirmed']) && stamp(w.hours, ['unconfirmed', 'locked', 'confirmed']) && w.ready === (w.stage === 'ready') && (!w.ready || ['route', 'source', 'hours'].every(key => w[key].state === 'confirmed'));
  }
  function stamp(value, states = ['unconfirmed', 'confirmed']) {
    return C.object(value) && states.includes(value.state) && nullableText(value.confirmed_at) && nullableText(value.confirmed_by) && (value.state !== 'confirmed' || token(value.confirmed_at));
  }
  function writeContext(value, action) {
    if (value === null) return !action;
    return C.object(value) && token(value.write_token) && C.object(value.capabilities) && Array.isArray(value.blocked_reasons) && (!action || value.capabilities['process.' + action] === true);
  }
  function operation(row) {
    return C.object(row) && ref(row.ref) && storedSequence(row.sequence) && text(row.label) && source(row.source) && ['op_type_ref', 'supplier_ref', 'external_group_ref'].every(key => nullableRef(row[key])) && ['op_type_label', 'supplier_label'].every(key => nullableText(row[key])) && ['setup_hours', 'unit_hours', 'external_days'].every(key => number(row[key])) && text(row.status) && issues(row.issues) && C.own(row, 'external_days_source') && [null, 'operation', 'group'].includes(row.external_days_source) && (row.external_days_source === 'operation' ? row.external_days !== null && row.external_days >= 0 && (row.source !== 'external' || row.external_days > 0) : row.external_days === null) && C.object(row.confirmation) && stamp(row.confirmation.source) && stamp(row.confirmation.hours);
  }
  function externalGroup(row) {
    return C.object(row) && ref(row.ref) && storedSequence(row.start_sequence) && storedSequence(row.end_sequence) && nullableText(row.merge_mode) && number(row.total_days) && nullableRef(row.supplier_ref) && nullableText(row.supplier_label) && nullableText(row.remark) && issues(row.issues);
  }
  function uniqueRefs(rows) {
    return new Set(rows.map(row => row.ref)).size === rows.length;
  }
  function within(value, start, end) {
    const ordered = (a, b) => a.length < b.length || a.length === b.length && a <= b;
    return [value, start, end].every(sequence) && ordered(String(start), String(value)) && ordered(String(value), String(end));
  }
  function cycleReferences(entity) {
    const groups = new Map(entity.external_groups.map(row => [row.ref, row])),
      invalid = new Set();
    for (const row of entity.operations) {
      if (row.external_group_ref === null) continue;
      const group = groups.get(row.external_group_ref);
      if (!group) return false;
      if (row.status === 'active' && (row.source !== 'external' || !within(row.sequence, group.start_sequence, group.end_sequence))) invalid.add(group.ref);
    }
    return entity.operations.every(row => row.external_days_source !== 'group' || row.source === 'external' && row.status === 'active' && groups.has(row.external_group_ref) && !invalid.has(row.external_group_ref) && groups.get(row.external_group_ref).merge_mode === 'merged' && groups.get(row.external_group_ref).total_days > 0 && !groups.get(row.external_group_ref).issues.length && !row.issues.some(item => ['sequence_invalid', 'external_group_invalid', 'external_group_part_mismatch'].includes(item.code)));
  }
  function groupCycle(row, groups) {
    if (row.external_days_source !== 'group') return null;
    const group = groups.find(item => item.ref === row.external_group_ref);
    if (!group || group.merge_mode !== 'merged' || !Number.isFinite(group.total_days) || group.total_days <= 0 || group.issues.length || row.external_days !== null || row.source !== 'external' || row.status !== 'active' || !within(row.sequence, group.start_sequence, group.end_sequence)) throw C.failure('工序周期与指定外协组不一致，请重新读取。');
    return '按外协组周期 · ' + group.start_sequence + ' 至 ' + group.end_sequence;
  }
  function list(result, scope) {
    C.query(result, 'list');
    const d = result.data,
      p = d.page;
    if (!d.entities.every(entity) || !uniqueRefs(d.entities) || !capabilities(d.capabilities) || d.create_context !== null && (!writeContext(d.create_context) || !C.object(d.create_context)) || !C.object(d.metrics) || !C.object(d.metrics.counts) || !stages.every(row => count(d.metrics.counts[row[2]])) || p.number !== scope.page || p.size !== scope.size || p.pages !== Math.max(1, Math.ceil(p.total / p.size)) && !(p.total === 0 && p.pages === 0) || p.sort.length !== ordering(scope).length || !p.sort.every((item, index) => C.object(item) && item.field === ordering(scope)[index].field && item.direction === ordering(scope)[index].direction)) throw C.failure('工艺列表、阶段或分页协议不完整，请重新读取。');
    if (scope.snapshot_ref && result.meta.snapshot_ref !== scope.snapshot_ref) throw C.failure('列表快照已变化，请刷新后重新翻页。');
    return result;
  }
  function detail(result, expectedRef) {
    C.query(result, 'entity');
    const d = result.data;
    if (!entity(d) || d.ref !== expectedRef || !capabilities(d.capabilities) || !Array.isArray(d.operations) || !d.operations.every(operation) || !uniqueRefs(d.operations) || !Array.isArray(d.external_groups) || !d.external_groups.every(externalGroup) || !uniqueRefs(d.external_groups) || !cycleReferences(d)) throw C.failure('工艺详情不完整或对象不一致，请重新读取。');
    return result;
  }
  function preview(result, expectedRef, body) {
    if (result && result.ok === false) throw result;
    if (!C.object(result) || result.ok !== true || result.schema_version !== 1 || !C.object(result.meta) || !['production', 'demo'].includes(result.meta.source) || result.meta.time_basis !== 'factory_local' || !token(result.meta.snapshot_ref) || !text(result.meta.request_ref) || !text(result.meta.as_of) || !Array.isArray(result.warnings)) throw C.failure('路线预检协议不匹配。');
    const d = result.data;
    if (!C.object(d) || d.part_ref !== expectedRef || d.mode !== body.mode || !text(d.route_raw) || !text(d.normalized_input) || !writeContext(d.write_context, d.can_confirm_route ? 'route_confirm' : null) || typeof d.can_confirm_route !== 'boolean' || !Array.isArray(d.operations) || !d.operations.every(row => C.object(row) && sequence(row.sequence) && text(row.op_type_name) && nullableRef(row.op_type_ref) && source(row.source_suggestion) && nullableRef(row.supplier_ref) && nullableText(row.supplier_label) && number(row.external_days) && (text(row.basis) || C.object(row.basis) || Array.isArray(row.basis)) && issues(row.issues)) || !Array.isArray(d.diagnostics) || !d.diagnostics.every(row => C.object(row) && text(row.code) && text(row.message) && ['error', 'warning'].includes(row.severity) && (!C.own(row, 'sequence') || sequence(row.sequence))) || !C.object(d.counts) || !['operations', 'recognized', 'unknown'].every(key => count(d.counts[key])) || d.counts.operations !== d.operations.length || d.counts.recognized + d.counts.unknown !== d.counts.operations || !C.object(d.baseline) || !count(d.baseline.operation_count) || !count(d.baseline.external_group_count) || typeof d.baseline.has_published_template !== 'boolean' || !C.object(d.changes) || !['added', 'removed', 'retained', 'same_sequence_changed'].every(key => Array.isArray(d.changes[key]) && d.changes[key].every(sequence)) || !Array.isArray(d.affected_groups) || !d.affected_groups.every(externalGroup) || !uniqueRefs(d.affected_groups)) throw C.failure('路线预检结果不完整或对象不一致，未视为有效输入。');
    if (d.can_confirm_route && d.diagnostics.some(row => row.severity === 'error')) throw C.failure('路线预检的诊断与确认标记矛盾，请重试。');
    return result;
  }
  function stagePreview(result, expectedRef, action) {
    if (!C.object(result) || result.ok !== true || result.schema_version !== 1 || !C.object(result.meta) || result.meta.source !== 'production' || result.meta.time_basis !== 'factory_local' || !token(result.meta.snapshot_ref) || !token(result.meta.request_ref) || !text(result.meta.as_of) || !Array.isArray(result.warnings)) throw C.failure('归属检查结果不完整，请重新检查。');
    const d = result.data;
    if (!C.object(d) || action !== 'source_confirm' || d.action !== action || d.part_ref !== expectedRef || !writeContext(d.write_context, action) || !Array.isArray(d.affected_groups) || !d.affected_groups.every(externalGroup) || !uniqueRefs(d.affected_groups)) throw C.failure('归属检查与当前零件不一致，请重新检查。');
    return result;
  }
  function previewBody(mode, routeRaw, rows, snapshot) {
    let body;
    if (mode === 'text') body = {
      mode,
      route_raw: routeRaw
    };else {
      const fields = [];
      const input = rows.map((row, index) => {
        const raw = row.seq.trim(),
          digits = raw.replace(/^0+/, '') || '0';
        let seq = null;
        if (!/^\d+$/.test(raw) || digits === '0') fields.push({
          path: 'rows.' + index + '.seq',
          message: '第 ' + (index + 1) + ' 行工序号必须是安全正整数。'
        });else if (digits.length > 16 || digits.length === 16 && digits > '9007199254740991') fields.push({
          path: 'rows.' + index + '.seq',
          message: '第 ' + (index + 1) + ' 行工序号超出安全整数范围，请改用整条文字预检；原值未改动。'
        });else seq = Number(digits);
        return {
          seq,
          op_type_name: row.op_type_name
        };
      });
      if (fields.length) throw C.failure('请核对逐行输入。', fields);
      body = {
        mode: 'rows',
        rows: input
      };
    }
    if (snapshot) body.snapshot_ref = snapshot;
    return body;
  }
  function reason(value, action, connected = false) {
    if (!value) return '请先读取当前工艺能力。';
    if (value[action] !== true) return action === 'stage_confirm' ? '服务尚未开放阶段确认，当前不能保存。' : '服务尚未开放此操作。';
    return connected ? '' : '此操作的事务接口尚未接入。';
  }
  function sourceLabel(value) {
    return value === 'internal' ? '自制' : value === 'external' ? '外协' : '未归类';
  }
  function valueText(value, unit = '') {
    return value === null ? '未填写' : String(value) + unit + (value <= 0 ? ' · 请复核' : '');
  }
  window.APSProcessContract = {
    stages,
    sorts,
    columns,
    ordering,
    externalGroup,
    groupCycle,
    list,
    detail,
    preview,
    stagePreview,
    previewBody,
    reason,
    sourceLabel,
    valueText
  };
})();
