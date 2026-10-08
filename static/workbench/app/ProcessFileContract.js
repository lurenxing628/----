(function () {
  'use strict';

  const C = window.APSResourceContract,
    A = window.APSProcessActions,
    P = window.APSProcessContract;
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const text = value => typeof value === 'string';
  const scalar = value => value === null || text(value) || typeof value === 'boolean' || Number.isFinite(value);
  const results = ['new', 'update', 'unchanged', 'delete', 'rejected'];
  const sequence = value => Number.isSafeInteger(value) && value > 0 || text(value) && /^[1-9]\d*$/.test(value) && (value.length < 19 || value.length === 19 && value <= '9223372036854775807');
  function kind(value) {
    if (!['route', 'hours'].includes(value)) throw C.failure('文件类型必须是工艺路线或工时定额。');
    return value;
  }
  function operation(value) {
    return 'process_' + kind(value) + '_import.confirm';
  }
  function envelope(raw) {
    if (raw && raw.ok === false) throw raw;
    if (!C.object(raw) || raw.ok !== true || raw.schema_version !== 1 || !C.object(raw.data) || !C.object(raw.meta) || !['production', 'demo'].includes(raw.meta.source) || raw.meta.time_basis !== 'factory_local' || !A.token(raw.meta.snapshot_ref) || !text(raw.meta.request_ref) || !text(raw.meta.as_of) || !Array.isArray(raw.warnings)) throw C.failure('工艺文件读取结果不完整，请重新预检。');
    return raw;
  }
  function columns(value) {
    return Array.isArray(value) && value.length > 0 && value.every(row => C.object(row) && text(row.key) && /^[a-z][a-z0-9_]*$/.test(row.key) && !['id', 'entity_key', 'entity_ref', 'write_token', 'revision'].includes(row.key) && text(row.label) && row.label.trim() && row.label !== row.key) && new Set(value.map(row => row.key)).size === value.length;
  }
  function routeSummary(value) {
    return value === null || C.object(value) && C.object(value.counts) && ['operations', 'recognized', 'unknown'].every(key => count(value.counts[key])) && value.counts.operations === value.counts.recognized + value.counts.unknown && typeof value.can_confirm_route === 'boolean' && Array.isArray(value.diagnostics) && value.diagnostics.every(row => C.object(row) && text(row.code) && text(row.message) && ['error', 'warning'].includes(row.severity) && (!C.own(row, 'sequence') || sequence(row.sequence))) && Array.isArray(value.operations) && value.operations.length === value.counts.operations && value.operations.every(row => C.object(row) && sequence(row.sequence) && text(row.op_type_name) && row.op_type_name.trim() && [null, 'internal', 'external'].includes(row.source_suggestion) && (row.supplier_label === null || text(row.supplier_label)) && (row.external_days === null || Number.isFinite(row.external_days) && row.external_days > 0)) && Array.isArray(value.differences) && value.differences.every(row => C.object(row) && sequence(row.sequence) && ['added', 'removed', 'changed', 'retained'].includes(row.change) && (row.before === null || text(row.before)) && (row.after === null || text(row.after)) && (row.before !== null || row.after !== null)) && (!value.can_confirm_route || value.differences.filter(row => row.after !== null).length === value.operations.length && value.operations.every(op => value.differences.some(row => row.sequence === op.sequence && row.after === op.op_type_name))) && (!value.can_confirm_route || !value.diagnostics.some(row => row.severity === 'error'));
  }
  function publicColumns(data) {
    if (!columns(data.columns)) throw C.failure('文件预检缺少明确的业务列名。');
    const keys = new Set(data.columns.map(row => row.key));
    const facts = value => value === null || C.object(value) && Object.keys(value).every(key => keys.has(key) && scalar(value[key]));
    if (data.rows.some(row => !facts(row.before) || !facts(row.after) || Object.keys(row.changes).some(key => !keys.has(key) || !C.object(row.changes[key]) || !C.own(row.changes[key], 'before') || !C.own(row.changes[key], 'after') || !scalar(row.changes[key].before) || !scalar(row.changes[key].after)))) throw C.failure('文件预检里有没说明的列或不完整的修改，不能确认。');
  }
  function hoursCounts(data) {
    return {
      changed: data.summary.new + data.summary.update,
      unchanged: data.summary.unchanged,
      rejected: data.summary.rejected
    };
  }
  function preview(raw, requestedKind, format, request) {
    const result = envelope(raw),
      d = result.data;
    if (d.kind !== kind(requestedKind) || d.operation !== operation(requestedKind) || !A.token(d.preview_ref) || !Number.isFinite(Date.parse(d.expires_at)) || d.commit_policy !== 'atomic' || typeof d.can_confirm !== 'boolean' || d.format !== format || d.mode !== 'upsert' || d.template_version !== 1 || !text(d.instructions) || typeof d.zero_review_required !== 'boolean' || !C.object(d.scope) || !C.object(d.write_context) || !A.token(d.write_context.write_token) || !C.object(d.write_context.capabilities) || !Array.isArray(d.write_context.blocked_reasons) || !C.object(d.summary) || !results.every(key => count(d.summary[key])) || !Array.isArray(d.rows) || !d.rows.every(row => C.object(row) && count(row.row) && row.row > 0 && results.includes(row.result) && row.result !== 'delete' && (row.entity_ref === null || A.ref(row.entity_ref)) && (row.business_code === null || text(row.business_code)) && C.object(row.changes) && count(row.reference_count) && typeof row.requires_confirmation === 'boolean' && Array.isArray(row.errors) && row.errors.every(error => C.object(error) && text(error.message)) && routeSummary(row.route_summary) && (!C.own(row, 'sequence') || sequence(row.sequence))) || new Set(d.rows.map(row => row.row)).size !== d.rows.length || !results.every(key => d.summary[key] === d.rows.filter(row => row.result === key).length) || d.can_confirm && (d.summary.rejected !== 0 || d.rows.some(row => row.route_summary && !row.route_summary.can_confirm_route)) || !Array.isArray(d.affected_groups) || !d.affected_groups.every(group => P.externalGroup(group) && A.ref(group.part_ref) && text(group.business_code)) || new Set(d.affected_groups.map(group => group.ref)).size !== d.affected_groups.length) throw C.failure('文件预检内容、原记录或统计不完整，不能确认导入。');
    publicColumns(d);
    if (requestedKind === 'hours' && (d.summary.new !== 0 || d.summary.delete !== 0 || d.rows.some(row => row.result !== 'rejected' && !sequence(row.sequence)))) throw C.failure('工时文件包含无效的工序或新增行，请重新预检。');
    if (request.target_ref && (!A.ref(request.target_ref) || d.rows.some(row => row.entity_ref !== request.target_ref && row.result !== 'rejected') || d.affected_groups.some(group => group.part_ref !== request.target_ref))) throw C.failure('文件包含其他零件，不能从当前详情提交。');
    return result;
  }
  function confirmInput(data, groupRefs, zero) {
    if (!Array.isArray(groupRefs) || new Set(groupRefs).size !== groupRefs.length || groupRefs.length !== data.affected_groups.length || data.affected_groups.some(group => !groupRefs.includes(group.ref))) throw C.failure('请逐项核对并勾选全部受影响的外协组，未自动解除任何组。');
    if (typeof zero !== 'boolean' || data.zero_review_required && !zero) throw C.failure('单件工时为 0，排产只计算换型工时。请按 0 导入。');
    return {
      preview_ref: data.preview_ref,
      discard_group_refs: groupRefs.slice(),
      confirm_zero_unit_hours: zero
    };
  }
  function exportBody(request, selection, format) {
    if (!['all', 'filtered', 'explicit'].includes(selection) || !['csv', 'xlsx'].includes(format)) throw C.failure('请先选择导出范围和文件格式。');
    if (request.target_ref) {
      if (selection !== 'explicit' || !A.ref(request.target_ref) || !A.token(request.snapshot_ref) || !Number.isSafeInteger(request.page_size) || request.page_size < 1 || request.page_size > 200) throw C.failure('当前详情只导出这条零件，请刷新详情后再试。');
      return {
        format,
        selection,
        scope: {},
        snapshot_ref: request.snapshot_ref,
        page_size: request.page_size,
        target_ref: request.target_ref,
        refs: [request.target_ref]
      };
    }
    return {
      ...A.listContext(request),
      format,
      selection,
      ...(selection === 'explicit' ? {
        refs: A.selection(request.refs, true)
      } : {})
    };
  }
  function exportPreview(raw, requestedKind, body) {
    const result = envelope(raw),
      d = result.data;
    if (!A.token(d.export_ref) || d.selection !== body.selection || d.kind !== kind(requestedKind) || !count(d.row_count) || !count(d.part_count) || !Number.isFinite(Date.parse(d.expires_at)) || d.format !== body.format || !columns(d.columns) || !C.object(d.scope) || d.target_ref !== (body.target_ref || null) || body.target_ref && Object.keys(d.scope).length !== 0 || body.selection === 'filtered' && window.ResourceTableFilterModel.signature(A.scope(d.scope)) !== window.ResourceTableFilterModel.signature(A.scope(body.scope)) || body.selection === 'explicit' && d.part_count !== body.refs.length || requestedKind === 'route' && d.row_count !== d.part_count) throw C.failure('导出预检的类型、范围或数量不完整，未下载文件。');
    return result;
  }
  function receipt(result, intent, requestedKind, previewData, targetRef) {
    if (!intent || intent.kind !== 'process_' + kind(requestedKind) + '_import' || intent.action !== 'confirm' || intent.ref !== undefined && !A.token(intent.ref) || C.receipt(result) !== 'terminal' || !['committed', 'unchanged'].includes(result.result) || result.data.kind !== requestedKind || !Array.isArray(result.data.rows) || !result.data.rows.every(row => C.object(row) && count(row.row) && row.row > 0 && A.ref(row.entity_ref) && text(row.business_code) && ['committed', 'unchanged'].includes(row.result) && (!C.own(row, 'sequence') || sequence(row.sequence))) || !C.object(result.data.summary) || !results.every(key => count(result.data.summary[key])) || result.data.summary.rejected !== 0 || result.data.summary.delete !== 0 || results.reduce((sum, key) => sum + result.data.summary[key], 0) !== result.data.rows.length || new Set(result.data.rows.map(row => row.row)).size !== result.data.rows.length || !Array.isArray(result.data.affected_refs) || !result.data.affected_refs.every(A.ref) || new Set(result.data.affected_refs).size !== result.data.affected_refs.length || result.data.rows.some(row => !result.data.affected_refs.includes(row.entity_ref)) || result.data.affected_refs.some(ref => !result.data.rows.some(row => row.entity_ref === ref)) || result.result === 'unchanged' && (result.data.summary.new !== 0 || result.data.summary.update !== 0 || result.data.rows.some(row => row.result !== 'unchanged')) || targetRef && result.data.affected_refs.some(ref => ref !== targetRef)) throw C.failure(window.WorkbenchTerms.outcomes.pending('导入'));
    if (previewData && (result.data.rows.length !== previewData.rows.length || result.data.rows.some((row, index) => row.row !== previewData.rows[index].row || row.business_code !== previewData.rows[index].business_code || previewData.rows[index].entity_ref !== null && row.entity_ref !== previewData.rows[index].entity_ref || C.own(previewData.rows[index], 'sequence') && row.sequence !== previewData.rows[index].sequence))) throw C.failure('导入结果和预检的文件行不一致。请点「查询结果」核对，不要重复提交。');
    if (requestedKind === 'hours') {
      const counts = hoursCounts(result.data);
      if (result.data.summary.new !== 0 || result.data.rows.some(row => !sequence(row.sequence)) || counts.changed !== result.data.rows.filter(row => row.result === 'committed').length || result.result === 'committed' !== counts.changed > 0) throw C.failure('实际导入数量和文件不一致。请点「查询结果」核对，不要重复提交。');
    }
    return result.data;
  }
  window.APSProcessFiles = {
    kind,
    operation,
    preview,
    confirmInput,
    exportBody,
    exportPreview,
    receipt,
    hoursCounts
  };
})();
