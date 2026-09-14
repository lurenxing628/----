(function () {
  'use strict';

  const C = window.APSResourceContract,
    P = window.APSProcessContract,
    M = window.ResourceTableFilterModel;
  const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
  const token = value => typeof value === 'string' && /^[A-Za-z0-9_-]{32}$/.test(value);
  const fields = {
    business_code: '图号',
    label: '零件名称',
    route_raw: '原始路线',
    route_parsed: '路线解析标记',
    remark: '备注',
    operation_count: '工序数量',
    external_group_count: '外协组数量'
  };
  function filters(value) {
    if (value === undefined) return {};
    if (!C.object(value) || Object.keys(value).some(key => !P.columns.some(column => column.key === key) || !C.object(value[key]))) throw C.failure('工艺列筛选不完整，未改为全量范围。');
    return Object.fromEntries(Object.keys(value).map(key => [key, M.rule(value[key])]));
  }
  function scope(value = {}) {
    if (!C.object(value) || value.query !== undefined && typeof value.query !== 'string' || value.stage !== undefined && value.stage !== null && value.stage !== '' && !['route', 'source', 'hours', 'ready'].includes(value.stage)) throw C.failure('工艺列表范围不完整。');
    const result = {
      query: value.query || '',
      sort: P.ordering(value),
      column_filters: filters(value.column_filters)
    };
    if (value.stage) result.stage = value.stage;
    return result;
  }
  function facetScope(value, column) {
    const result = scope(value);
    delete result.sort;
    delete result.column_filters[column];
    return result;
  }
  function selection(refs, allowEmpty = false) {
    if (!Array.isArray(refs) || !allowEmpty && !refs.length || !refs.every(ref) || new Set(refs).size !== refs.length) throw C.failure('请重新选择零件；不能用图号代替原零件记录。');
    return refs.slice();
  }
  function listContext(request) {
    if (!request || !token(request.snapshot_ref) || !Number.isSafeInteger(request.page_size) || request.page_size < 1 || request.page_size > 200) throw C.failure('请先刷新零件列表，再操作。');
    return {
      scope: scope(request.scope),
      snapshot_ref: request.snapshot_ref,
      page_size: request.page_size
    };
  }
  function deleteBody(request) {
    return {
      ...listContext(request),
      refs: selection(request.refs)
    };
  }
  function createInput(draft) {
    const errors = [],
      value = {};
    ['business_code', 'label'].forEach(key => {
      value[key] = typeof draft[key] === 'string' ? draft[key].trim() : '';
      if (!value[key]) errors.push({
        path: key,
        message: key === 'business_code' ? '请填写图号。' : '请填写零件名称。'
      });
    });
    ['route_raw', 'remark'].forEach(key => {
      if (typeof draft[key] !== 'string') errors.push({
        path: key,
        message: '请填写文字或留空。'
      });else if (draft[key] !== '') value[key] = draft[key];
    });
    if (errors.length) throw C.failure('请核对新增零件的内容。', errors);
    return value;
  }
  function createReason(context, source) {
    if (source !== 'production') return '尚未读取可保存的零件资料。';
    if (!C.object(context) || !token(context.write_token) || !C.object(context.capabilities) || context.capabilities['process.create'] !== true) return '现在不能新增零件，请刷新列表后重试。';
    return '';
  }
  function deletePreview(raw, request) {
    const expected = selection(request.refs),
      result = window.APSResourceMaterial.create('part', '零件').preview(raw, 'bulk', expected);
    const d = result.data;
    if (!C.object(d.scope) || M.signature(scope(d.scope)) !== M.signature(scope(request.scope)) || !Array.isArray(d.columns) || !d.columns.length || !d.columns.every(row => C.object(row) && C.own(fields, row.key) && typeof row.label === 'string' && row.label.trim()) || new Set(d.columns.map(row => row.key)).size !== d.columns.length) throw C.failure('删除预检与原筛选范围或业务列不一致，请重新预检。');
    if (result.data.rows.some(row => row.action !== 'delete' || !['delete', 'rejected'].includes(row.result))) throw C.failure('删除预检含有其他操作，本批未提交。');
    const validFacts = value => value === null || C.object(value) && Object.keys(value).every(key => C.own(fields, key) && (value[key] === null || typeof value[key] === 'string' || Number.isFinite(value[key])));
    if (result.data.rows.some(row => !validFacts(row.before) || row.after !== null || Object.keys(row.changes).length || row.before && Object.keys(row.before).some(key => !d.columns.some(column => column.key === key)))) throw C.failure('删除预检中的原零件资料不完整，本批未提交。');
    return result;
  }
  function blocked(result, source, capability) {
    if (!result) return '请先完成预检。';
    if (source !== 'production' || result.meta.source !== 'production') return '尚未读取可保存的工艺资料。';
    const data = result.data;
    if (!data.can_confirm || data.summary.rejected) return '预检含有不能提交的行，本次全部不提交。';
    if (data.write_context.capabilities[capability] !== true) {
      const reasons = data.write_context.blocked_reasons || [];
      return (reasons.find(item => item.action === capability) || {}).message || '本次未取得确认许可，请重新预检。';
    }
    if (Date.now() >= Date.parse(data.expires_at)) return '预检已过期，请重新预检。';
    return '';
  }
  function receipt(result, intent, expectedRefs) {
    if (!intent || C.receipt(result) !== 'terminal' || result.result !== 'committed') throw C.failure(window.WorkbenchTerms.outcomes.pending('操作'));
    const data = result.data;
    if (intent.kind === 'process' && intent.action === 'create' && intent.ref === null) {
      if (!ref(data.entity_ref) || typeof data.business_code !== 'string' || !data.business_code || !C.object(data.workflow) || data.workflow.origin !== 'managed' || data.workflow.ready !== false || data.workflow.stage !== 'route') throw C.failure('新增结果不完整，没有自动打开这条零件。请点「查询结果」核对，不要重复提交。');
      if (intent.input && data.business_code !== intent.input.business_code) throw C.failure('新增结果的图号和您录入的不一致。请点「查询结果」核对，不要重复提交。');
    } else if (intent.kind === 'process_bulk' && intent.action === 'confirm' && token(intent.ref)) {
      if (!Number.isSafeInteger(data.deleted_count) || data.deleted_count < 1 || !Array.isArray(data.rows) || data.rows.length !== data.deleted_count || !data.rows.every(row => C.object(row) && ref(row.entity_ref) && row.result === 'committed') || new Set(data.rows.map(row => row.entity_ref)).size !== data.rows.length || expectedRefs && (data.rows.length !== expectedRefs.length || data.rows.some((row, index) => row.entity_ref !== expectedRefs[index]))) throw C.failure('删除结果没有逐条对上，不算部分成功。请点「查询结果」核对，不要重复提交。');
    } else throw C.failure('保存结果和当前操作不一致。请点「查询结果」核对，不要重复提交。');
    return data;
  }
  function restored(intent) {
    if (!intent) return null;
    if (intent.kind === 'process' && intent.action === 'create' && intent.ref === null) return {
      mode: 'create',
      recovery: true
    };
    if (intent.kind === 'process_bulk' && intent.action === 'confirm' && token(intent.ref)) return {
      mode: 'bulk',
      recovery: true
    };
    if (['process_route_import', 'process_hours_import'].includes(intent.kind) && intent.action === 'confirm' && token(intent.ref)) return {
      mode: 'import',
      fileKind: intent.kind === 'process_route_import' ? 'route' : 'hours',
      recovery: true
    };
    if (intent.kind === 'process' && ref(intent.ref) && ['route_confirm', 'source_confirm', 'hours_confirm'].includes(intent.action)) return {
      ref: intent.ref
    };
    return null;
  }
  window.APSProcessActions = {
    fields,
    ref,
    token,
    scope,
    facetScope,
    filters,
    selection,
    listContext,
    deleteBody,
    createInput,
    createReason,
    deletePreview,
    blocked,
    receipt,
    restored
  };
})();
