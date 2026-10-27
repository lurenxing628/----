(function () {
  'use strict';
  const prefix = '/api/workbench/v1/';
  const kinds = new Set(['material', 'op_type', 'machine', 'operator', 'supplier', 'machine_group', 'shift_profile']);
  const fileKinds = new Set(['material', 'op_type', 'machine', 'operator', 'supplier']);
  // 只有增量导入和导出、没有批量删除的文件家族：关联资料与日历。
  const importOnlyKinds = new Set(['operator_machine', 'work_calendar', 'operator_calendar']);
  // 个人日历的三个写入动作；意图里保持 kind=operator，保存后的刷新逻辑才认得出该读哪一页。
  const calendarActions = new Map([['calendar_upsert', 'upsert'], ['calendar_delete', 'delete'],
    ['calendar_range_clear', 'range-clear']]);
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const T = window.APSWorkbenchTransport, failure = window.APSResourceContract.failure;
  // 资源家族的文件只有 CSV 与 XLSX 两种。
  const fileTypes = [T.types.csv, T.types.xlsx];
  // 本地查不到确定结果：保持“结果未知”，由用户点「查询结果」。
  const unconfirmed = message => Object.assign(failure(message), { committed: 'unknown' });
  // 资源家族沿用相对路径；拼成工作台绝对路径后再交给 transport。
  const absolute = path => path.startsWith('/') ? path : prefix + path;
  function resource(kind, ref) {
    if (!kinds.has(kind)) throw failure('不支持这类基础资料。');
    if (ref != null && !/^[0-9a-f]{48}$/.test(ref)) throw failure('这条记录已失效，请重新选择。');
    return 'entities/' + kind + (ref == null ? '' : '/' + ref);
  }
  function tableScope(scope = {}) {
    if (!object(scope)) throw failure('列表范围不完整，请刷新后重试。');
    const result = { ...scope };
    ['status', 'category', 'snapshot_ref'].forEach(key => { if (result[key] === '' || result[key] === null || result[key] === undefined) delete result[key]; });
    if (Object.prototype.hasOwnProperty.call(result, 'column_filters')) {
      if (!object(result.column_filters)) throw failure('列筛选范围不完整，请刷新列表后重新筛选。');
      if (!Object.keys(result.column_filters).length) delete result.column_filters;
    }
    return result;
  }
  function terminal(payload) {
    return payload.ok === true && ['committed', 'unchanged', 'partial'].includes(payload.result)
      && typeof payload.receipt_ref === 'string' && !!payload.receipt_ref && typeof payload.replayed === 'boolean'
      && object(payload.data) && Array.isArray(payload.warnings);
  }
  function validIntent(value, recovery = false) {
    if (!object(value) || typeof value.request_key !== 'string' || !/^resource-[0-9a-f]{48}$/.test(value.request_key)) return false;
    const previewRef = pattern => recovery && value.ref === undefined || typeof value.ref === 'string' && pattern.test(value.ref);
    if (value.kind === 'operator' && (value.action === 'machine_permissions' || calendarActions.has(value.action)))
      return value.category === undefined && typeof value.ref === 'string' && /^[0-9a-f]{48}$/.test(value.ref);
    if (value.kind === 'machine' && ['downtime_create', 'downtime_update', 'downtime_cancel'].includes(value.action))
      return value.category === undefined && typeof value.ref === 'string' && /^[0-9a-f]{48}$/.test(value.ref);
    if (value.kind === 'calendar') return (
      ['upsert', 'delete'].includes(value.action) && typeof value.ref === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value.ref)
      || value.action === 'confirm' && previewRef(/^[0-9a-f]{32}$/)
      || value.action === 'defaults' && value.ref === 'calendar-defaults');
    if (value.kind === 'process') return value.category === undefined && (value.action === 'create' && value.ref === null
      || ['route_confirm', 'source_confirm', 'hours_confirm', 'groups_confirm'].includes(value.action) && typeof value.ref === 'string' && /^[0-9a-f]{48}$/.test(value.ref));
    if (['process_bulk', 'process_route_import', 'process_hours_import'].includes(value.kind)) return value.action === 'confirm'
      && previewRef(/^[A-Za-z0-9_-]{32}$/) && value.category === undefined;
    if (value.kind === 'batch') return value.category === undefined && (value.action === 'create' && value.ref === null
      || ['update', 'delete', 'operation_update', 'materials_update', 'split_confirm', 'sync_confirm'].includes(value.action) && typeof value.ref === 'string' && /^[0-9a-f]{48}$/.test(value.ref)
      || ['bulk_confirm', 'import_confirm'].includes(value.action) && previewRef(/^[A-Za-z0-9_-]{32}$/));
    if (value.kind === 'execution') return value.category === undefined
      && (['create', 'supplement', 'correct', 'report_void'].includes(value.action) && typeof value.ref === 'string' && /^[0-9a-f]{48}$/.test(value.ref)
        || value.action === 'import_confirm' && previewRef(/^[A-Za-z0-9_-]{32}$/));
    const importOnly = typeof value.kind === 'string' && /^(.+)_import$/.exec(value.kind);
    if (importOnly && importOnlyKinds.has(importOnly[1])) return value.action === 'confirm' && value.category === undefined
      && previewRef(/^[A-Za-z0-9_-]{32}$/);
    const file = typeof value.kind === 'string' && /^(material|op_type|machine|operator|supplier)_(import|bulk)$/.exec(value.kind);
    if (file) return value.action === 'confirm' && previewRef(/^[A-Za-z0-9_-]{32}$/)
      && (file[1] === 'op_type' ? ['internal', 'external'].includes(value.category) : value.category === undefined);
    return kinds.has(value.kind) && ['create', 'update', 'delete'].includes(value.action)
      && (value.action === 'create' ? value.ref === null : typeof value.ref === 'string' && /^[0-9a-f]{48}$/.test(value.ref))
      && (value.category === undefined || ['internal', 'external', 'both'].includes(value.category));
  }
  function pendingRecord(intent) {
    const stored = { kind: intent.kind, action: intent.action, request_key: intent.request_key };
    // A retained preview ref is also its confirmation credential; recovery only looks up the request key.
    if (intent.ref !== undefined && !(typeof intent.ref === 'string' && /^[A-Za-z0-9_-]{32}$/.test(intent.ref))) stored.ref = intent.ref;
    if (intent.category !== undefined) stored.category = intent.category;
    return stored;
  }
  function matchesNamespace(namespace, intent) {
    if (namespace === 'resources') return kinds.has(intent.kind);
    if (namespace === 'calendar') return intent.kind === 'calendar';
    if (namespace === 'process') return ['process', 'process_bulk', 'process_route_import', 'process_hours_import'].includes(intent.kind);
    if (namespace === 'batches') return intent.kind === 'batch';
    if (namespace === 'execution') return intent.kind === 'execution';
    if (namespace === 'catalog') return ['machine_group', 'shift_profile'].includes(intent.kind);
    const kind = namespace.slice(0, -6);
    if (importOnlyKinds.has(kind)) return intent.kind === kind + '_import';
    return fileKinds.has(kind) && [kind + '_import', kind + '_bulk'].includes(intent.kind);
  }
  function create(namespace = 'resources') {
    if (!['resources', 'calendar', 'catalog', 'process', 'batches', 'execution'].includes(namespace)
        && ![...fileKinds, ...importOnlyKinds].some(kind => namespace === kind + '_files')) throw failure('基础资料操作入口不正确。');
    const pendingKey = 'aps_workbench_resource_pending_v1' + (namespace === 'resources' ? '' : '_' + namespace);
    const api = {
      query(path, scope, signal) { return T.read(absolute(path), scope, { signal, timeout: 20000 }); },
      preview(path, body, signal) { return T.preview(absolute(path), body, { signal, timeout: 20000 }); },
      async execute(path, body) {
        const result = await T.command(absolute(path), body, { timeout: 20000, expect: prefix + 'commands/' + body.request_key });
        if (!terminal(result)) throw unconfirmed('保存结果不完整，还没确认。请点「查询结果」，不要重复提交。');
        return result;
      },
      list(kind, scope, signal) {
        const normalized = tableScope(scope);
        return normalized.column_filters ? api.preview(resource(kind) + '/query', normalized, signal) : api.query(resource(kind), normalized, signal);
      },
      facets(kind, request, signal) { return api.preview(resource(kind) + '/facets', { ...request, scope: tableScope(request.scope) }, signal); },
      facetSelection(kind, request, signal) { return api.preview(resource(kind) + '/facet-selection', { ...request, scope: tableScope(request.scope) }, signal); },
      choices(kind, scope, signal) { return api.list(kind, scope, signal); },
      detail(kind, ref, signal) { return api.query(resource(kind, ref), {}, signal); },
      relations(ref, scope, signal) { return api.query(resource('op_type', ref) + '/relations', scope, signal); },
      summary(signal) { return api.query('resources/summary', {}, signal); },
      async downtimes(ref, signal) {
        const result = await api.query(resource('machine', ref) + '/downtimes', {}, signal), data = result.data;
        if (data.entity_ref !== ref || !Array.isArray(data.rows) || !object(data.reasons) || !object(data.write_context)
            || !data.rows.every(row => /^[0-9a-f]{48}$/.test(row.ref) && typeof row.start_time === 'string' && typeof row.end_time === 'string'))
          throw failure('设备停机资料不完整，请刷新后重试。');
        return result;
      },
      command(kind, action, ref, body) {
        if (kind === 'machine' && ['downtime_create', 'downtime_update', 'downtime_cancel'].includes(action) && ref !== null)
          return api.execute(resource(kind, ref) + '/downtimes/' + action.slice(9), body);
        if (kind === 'operator' && action === 'machine_permissions' && ref !== null)
          return api.execute(resource(kind, ref) + '/machine-permissions/confirm', body);
        if (kind === 'operator' && calendarActions.has(action) && ref !== null)
          return api.execute(resource(kind, ref) + '/calendar/' + calendarActions.get(action), body);
        if (!['create', 'update', 'delete'].includes(action) || (action === 'create') !== (ref === null))
          throw failure('保存操作与所选记录不一致。');
        return api.execute(resource(kind, ref) + '/' + action, body);
      },
      // key 来自已校验的本机意图（validIntent）；回执查询失败一律保持“结果未知”。
      async lookup(key) {
        const result = await T.lookup(prefix + 'commands/' + key, { timeout: 20000 });
        if (result && (terminal(result) || result.ok === true && result.state === 'not_recorded' && result.receipt === null && result.may_be_in_flight === true)) return result;
        throw unconfirmed('上次操作的结果还没确认，请保留当前页面并点「查询结果」。');
      },
      download(path, scope, signal, options = {}) { return T.download(absolute(path), scope, { types: fileTypes, timeout: 20000, ...options, signal }); },
      readPending() {
        try {
          const raw = sessionStorage.getItem(pendingKey);
          if (raw === null) return null;
          const intent = JSON.parse(raw);
          if (!validIntent(intent, true) || !matchesNamespace(namespace, intent)) throw new Error('invalid');
          return intent;
        } catch (_) { throw unconfirmed('读不到上次操作记录，请重新打开页面；暂时不能继续保存。'); }
      },
      savePending(intent) {
        if (!validIntent(intent) || !matchesNamespace(namespace, intent)) throw failure('操作编号无法保存，本次没有提交。');
        try { sessionStorage.setItem(pendingKey, JSON.stringify(pendingRecord(intent))); }
        catch (_) { throw failure('本次没有提交：操作编号没能保存，请重新打开页面。'); }
      },
      clearPending() {
        try { sessionStorage.removeItem(pendingKey); }
        catch (_) { throw failure('结果已确认，但上次操作记录没清掉；重新打开页面后可以再点「查询结果」。'); }
      }
    };
    return api;
  }
  window.APSResourceAPI = { create };
})();
