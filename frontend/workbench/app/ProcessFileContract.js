(function () {
  'use strict';
  const C = window.APSResourceContract, A = window.APSProcessActions, P = window.APSProcessContract;
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const text = value => typeof value === 'string';
  const scalar = value => value === null || text(value) || typeof value === 'boolean' || Number.isFinite(value);
  const results = ['new', 'update', 'unchanged', 'delete', 'rejected'];
  const sequence = value => Number.isSafeInteger(value) && value > 0 || text(value) && /^[1-9]\d*$/.test(value)
    && (value.length < 19 || value.length === 19 && value <= '9223372036854775807');
  function kind(value) { if (!['route', 'hours'].includes(value)) throw C.failure('文件类型必须是工艺路线或工时定额。'); return value; }
  function operation(value) { return 'process_' + kind(value) + '_import.confirm'; }
  function envelope(raw) {
    if (raw && raw.ok === false) throw raw;
    if (!C.object(raw) || raw.ok !== true || raw.schema_version !== 1 || !C.object(raw.data) || !C.object(raw.meta)
        || !['production', 'demo'].includes(raw.meta.source) || raw.meta.time_basis !== 'factory_local' || !A.token(raw.meta.snapshot_ref)
        || !text(raw.meta.request_ref) || !text(raw.meta.as_of) || !Array.isArray(raw.warnings)) throw C.failure('工艺文件读取结果不完整，请重新预检。');
    return raw;
  }
  function columns(value) {
    return Array.isArray(value) && value.length > 0 && value.every(row => C.object(row) && text(row.key) && /^[a-z][a-z0-9_]*$/.test(row.key)
      && !['id', 'entity_key', 'entity_ref', 'write_token', 'revision'].includes(row.key) && text(row.label) && row.label.trim() && row.label !== row.key)
      && new Set(value.map(row => row.key)).size === value.length;
  }
  function routeSummary(value) {
    return value === null || C.object(value) && C.object(value.counts) && ['operations', 'recognized', 'unknown'].every(key => count(value.counts[key]))
      && value.counts.operations === value.counts.recognized + value.counts.unknown && typeof value.can_confirm_route === 'boolean'
      && Array.isArray(value.diagnostics) && value.diagnostics.every(row => C.object(row) && text(row.code) && text(row.message)
        && ['error', 'warning'].includes(row.severity) && (!C.own(row, 'sequence') || sequence(row.sequence)))
      && (!value.can_confirm_route || !value.diagnostics.some(row => row.severity === 'error'));
  }
  function publicColumns(data) {
    if (!columns(data.columns)) throw C.failure('文件预检缺少明确的业务列名。');
    const keys = new Set(data.columns.map(row => row.key));
    const facts = value => value === null || C.object(value) && Object.keys(value).every(key => keys.has(key) && scalar(value[key]));
    if (data.rows.some(row => !facts(row.before) || !facts(row.after) || Object.keys(row.changes).some(key => !keys.has(key)
        || !C.object(row.changes[key]) || !C.own(row.changes[key], 'before') || !C.own(row.changes[key], 'after')
        || !scalar(row.changes[key].before) || !scalar(row.changes[key].after)))) throw C.failure('文件预检含有未说明的字段或不完整修改，未允许确认。');
  }
  const skipFields = ['code', 'template_operation_ref', 'adoption_ref', 'reason', 'message'];
  function quotaSkips(data) {
    const rows = new Map(data.rows.map(row => [row.row, row]));
    if (!count(data.skipped_count) || !Array.isArray(data.skipped_rows) || !Array.isArray(data.skipped_refs)
        || data.skipped_count !== data.skipped_rows.length || data.skipped_count !== data.skipped_refs.length
        || new Set(data.skipped_refs).size !== data.skipped_count || new Set(data.skipped_rows.map(row => row && row.row)).size !== data.skipped_count
        || data.skipped_rows.some((skip, index) => {
          const row = C.object(skip) && rows.get(skip.row);
          return !row || row.result !== 'unchanged' || !sequence(row.sequence) || !text(row.business_code) || !row.business_code.trim()
            || skip.code !== 'calibration_quota_locked' || !A.ref(skip.template_operation_ref) || !A.ref(skip.adoption_ref)
            || !text(skip.reason) || !skip.reason.trim() || !text(skip.message) || !skip.message.trim()
            || data.skipped_refs[index] !== skip.template_operation_ref || !C.object(row.skip_reason)
            || skipFields.some(key => row.skip_reason[key] !== skip[key]);
        }))
      throw C.failure('工时锁定跳过的数量、工序或原因不完整，请重新核实，未认定全部导入。');
    const skips = new Map(data.skipped_rows.map(skip => [skip.row, skip]));
    if (data.rows.some(row => C.own(row, 'skip_reason') && !skips.has(row.row)))
      throw C.failure('工时锁定跳过明细有遗漏，请重新核实。');
    return skips;
  }
  function hoursCounts(data) {
    return { changed: data.summary.new + data.summary.update, skipped: data.skipped_count,
      unchanged: data.summary.unchanged - data.skipped_count, rejected: data.summary.rejected };
  }
  function preview(raw, requestedKind, format, request) {
    const result = envelope(raw), d = result.data;
    if (d.kind !== kind(requestedKind) || d.operation !== operation(requestedKind) || !A.token(d.preview_ref)
        || !Number.isFinite(Date.parse(d.expires_at)) || d.commit_policy !== 'atomic' || typeof d.can_confirm !== 'boolean'
        || d.format !== format || d.mode !== 'upsert' || d.template_version !== 1 || !text(d.file_sha256) || !/^[0-9a-f]{64}$/.test(d.file_sha256)
        || !text(d.instructions) || typeof d.zero_review_required !== 'boolean' || !C.object(d.scope)
        || !C.object(d.write_context) || !A.token(d.write_context.write_token) || !C.object(d.write_context.capabilities) || !Array.isArray(d.write_context.blocked_reasons)
        || !C.object(d.summary) || !results.every(key => count(d.summary[key])) || !Array.isArray(d.rows)
        || !d.rows.every(row => C.object(row) && count(row.row) && row.row > 0 && results.includes(row.result) && row.result !== 'delete'
          && (row.entity_ref === null || A.ref(row.entity_ref)) && (row.business_code === null || text(row.business_code))
          && C.object(row.changes) && count(row.reference_count) && typeof row.requires_confirmation === 'boolean'
          && Array.isArray(row.errors) && row.errors.every(error => C.object(error) && text(error.message))
          && routeSummary(row.route_summary) && (!C.own(row, 'sequence') || sequence(row.sequence)))
        || new Set(d.rows.map(row => row.row)).size !== d.rows.length || !results.every(key => d.summary[key] === d.rows.filter(row => row.result === key).length)
        || d.can_confirm && (d.summary.rejected !== 0 || d.rows.some(row => row.route_summary && !row.route_summary.can_confirm_route)) || !Array.isArray(d.affected_groups)
        || !d.affected_groups.every(group => P.externalGroup(group) && A.ref(group.part_ref) && text(group.business_code))
        || new Set(d.affected_groups.map(group => group.ref)).size !== d.affected_groups.length)
      throw C.failure('文件预检内容、原记录或统计不完整，不能确认导入。');
    publicColumns(d);
    if (requestedKind === 'hours') {
      const skips = quotaSkips(d);
      if (d.summary.new !== 0 || d.summary.delete !== 0 || d.rows.some(row => row.result !== 'rejected' && !sequence(row.sequence))
          || d.rows.some(row => skips.has(row.row) && (row.requires_confirmation || Object.keys(row.changes).length || !C.object(row.before) || !C.object(row.after)
              || Object.keys(row.before).length !== Object.keys(row.after).length || Object.keys(row.before).some(key => row.before[key] !== row.after[key]))))
        throw C.failure('工时锁定行仍包含修改或确认要求，不能确认导入。');
    }
    if (request.target_ref && (!A.ref(request.target_ref) || d.rows.some(row => row.entity_ref !== request.target_ref && row.result !== 'rejected')
        || d.affected_groups.some(group => group.part_ref !== request.target_ref))) throw C.failure('文件包含其他零件，不能从当前详情提交。');
    return result;
  }
  function confirmInput(data, groupRefs, zero) {
    if (!Array.isArray(groupRefs) || new Set(groupRefs).size !== groupRefs.length || groupRefs.length !== data.affected_groups.length
        || data.affected_groups.some(group => !groupRefs.includes(group.ref))) throw C.failure('请逐项核对并勾选全部受影响的外协组，未自动解除任何组。');
    if (typeof zero !== 'boolean' || data.zero_review_required && !zero) throw C.failure('存在单件工时为 0 的记录，请明确复核。');
    return { preview_ref: data.preview_ref, discard_group_refs: groupRefs.slice(), confirm_zero_unit_hours: zero };
  }
  function exportBody(request, selection, format) {
    if (!['all', 'filtered', 'explicit'].includes(selection) || !['csv', 'xlsx'].includes(format)) throw C.failure('请先选择导出范围和文件格式。');
    if (request.target_ref) {
      if (selection !== 'explicit' || !A.ref(request.target_ref) || !A.token(request.snapshot_ref) || !Number.isSafeInteger(request.page_size)
          || request.page_size < 1 || request.page_size > 200) throw C.failure('当前详情只导出原零件，请重读详情后再试。');
      return { format, selection, scope: {}, snapshot_ref: request.snapshot_ref, page_size: request.page_size, target_ref: request.target_ref, refs: [request.target_ref] };
    }
    return { ...A.listContext(request), format, selection, ...(selection === 'explicit' ? { refs: A.selection(request.refs, true) } : {}) };
  }
  function exportPreview(raw, requestedKind, body) {
    const result = envelope(raw), d = result.data;
    if (!A.token(d.export_ref) || d.selection !== body.selection || d.kind !== kind(requestedKind) || !count(d.row_count) || !count(d.part_count)
        || !Number.isFinite(Date.parse(d.expires_at)) || d.format !== body.format || !columns(d.columns) || !C.object(d.scope)
        || d.target_ref !== (body.target_ref || null) || body.target_ref && Object.keys(d.scope).length !== 0
        || body.selection === 'filtered' && window.ResourceTableFilterModel.signature(A.scope(d.scope)) !== window.ResourceTableFilterModel.signature(A.scope(body.scope))
        || body.selection === 'explicit' && d.part_count !== body.refs.length
        || requestedKind === 'route' && d.row_count !== d.part_count)
      throw C.failure('导出预检的类型、范围或数量不完整，未下载文件。');
    return result;
  }
  function receipt(result, intent, requestedKind, previewData, targetRef) {
    if (!intent || intent.kind !== 'process_' + kind(requestedKind) + '_import' || intent.action !== 'confirm' || !A.token(intent.ref)
        || C.receipt(result) !== 'terminal' || !['committed', 'unchanged'].includes(result.result) || result.data.kind !== requestedKind
        || !Array.isArray(result.data.rows) || !result.data.rows.every(row => C.object(row) && count(row.row) && row.row > 0 && A.ref(row.entity_ref)
          && text(row.business_code) && ['committed', 'unchanged'].includes(row.result) && (!C.own(row, 'sequence') || sequence(row.sequence)))
        || !C.object(result.data.summary) || !results.every(key => count(result.data.summary[key])) || result.data.summary.rejected !== 0 || result.data.summary.delete !== 0
        || results.reduce((sum, key) => sum + result.data.summary[key], 0) !== result.data.rows.length
        || new Set(result.data.rows.map(row => row.row)).size !== result.data.rows.length || !Array.isArray(result.data.affected_refs)
        || !result.data.affected_refs.every(A.ref) || new Set(result.data.affected_refs).size !== result.data.affected_refs.length
        || result.data.rows.some(row => !result.data.affected_refs.includes(row.entity_ref))
        || result.data.affected_refs.some(ref => !result.data.rows.some(row => row.entity_ref === ref))
        || result.result === 'unchanged' && (result.data.summary.new !== 0 || result.data.summary.update !== 0 || result.data.rows.some(row => row.result !== 'unchanged'))
        || targetRef && result.data.affected_refs.some(ref => ref !== targetRef))
      throw C.failure('导入回执没有完整确认本次文件，请继续查询原请求。');
    if (previewData && (result.data.rows.length !== previewData.rows.length || result.data.rows.some((row, index) => row.row !== previewData.rows[index].row
        || row.business_code !== previewData.rows[index].business_code || previewData.rows[index].entity_ref !== null && row.entity_ref !== previewData.rows[index].entity_ref
        || C.own(previewData.rows[index], 'sequence') && row.sequence !== previewData.rows[index].sequence)))
      throw C.failure('导入回执与预检的完整文件行不一致，请继续核实原请求。');
    if (requestedKind === 'hours') {
      const skips = quotaSkips(result.data), counts = hoursCounts(result.data);
      if (result.data.summary.new !== 0 || result.data.rows.some(row => !sequence(row.sequence))
          || counts.changed !== result.data.rows.filter(row => row.result === 'committed').length
          || (result.result === 'committed') !== (counts.changed > 0)
          || previewData && (skips.size !== previewData.skipped_count || previewData.skipped_rows.some(skip =>
            !skips.has(skip.row) || skipFields.some(key => skip[key] !== skips.get(skip.row)[key]))))
        throw C.failure('实际导入数量或锁定跳过原因与原文件不一致，请继续查询原请求。');
    }
    return result.data;
  }
  window.APSProcessFiles = { kind, operation, preview, confirmInput, exportBody, exportPreview, receipt, hoursCounts };
})();
