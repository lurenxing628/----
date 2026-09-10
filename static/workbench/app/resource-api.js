(function () {
  'use strict';

  const prefix = '/api/workbench/v1/';
  const kinds = new Set(['material', 'op_type', 'machine', 'operator', 'supplier', 'machine_group', 'shift_profile']);
  const fileKinds = new Set(['material', 'op_type', 'machine', 'operator', 'supplier']);
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  function problem(message, committed, details) {
    const error = new Error(message);
    error.committed = committed;
    if (details) error.error = details;
    return error;
  }
  function endpoint(path) {
    if (typeof path !== 'string') throw problem('数据地址不正确。', false);
    const target = new URL(path.startsWith('/') ? path : prefix + path, location.origin);
    if (target.origin !== location.origin || !target.pathname.startsWith(prefix) || target.username || target.password) throw problem('数据地址不属于本机工作台。', false);
    return target.href;
  }
  function resource(kind, ref) {
    if (!kinds.has(kind)) throw problem('不支持此类资源入口。', false);
    if (ref != null && !/^[0-9a-f]{48}$/.test(ref)) throw problem('资源引用无效，请重新选择。', false);
    return 'entities/' + kind + (ref == null ? '' : '/' + ref);
  }
  function queryPath(path, scope = {}) {
    const target = new URL(endpoint(path));
    Object.keys(scope).forEach(key => {
      if (scope[key] !== undefined && scope[key] !== null && scope[key] !== '') target.searchParams.set(key, String(scope[key]));
    });
    return target.href;
  }
  function tableScope(scope = {}) {
    if (!object(scope)) throw problem('列表范围必须是完整对象。', false);
    const result = {
      ...scope
    };
    ['status', 'category', 'snapshot_ref'].forEach(key => {
      if (result[key] === '' || result[key] === null || result[key] === undefined) delete result[key];
    });
    if (Object.prototype.hasOwnProperty.call(result, 'column_filters')) {
      if (!object(result.column_filters)) throw problem('列筛选范围不完整，未切换到全量列表。', false);
      if (!Object.keys(result.column_filters).length) delete result.column_filters;
    }
    return result;
  }
  function failure(payload) {
    return object(payload) && payload.ok === false && [false, true, 'unknown'].includes(payload.committed) && object(payload.error) && typeof payload.error.message === 'string' && Array.isArray(payload.error.fields);
  }
  function terminal(payload) {
    return object(payload) && payload.ok === true && ['committed', 'unchanged', 'partial'].includes(payload.result) && typeof payload.receipt_ref === 'string' && !!payload.receipt_ref && typeof payload.replayed === 'boolean' && object(payload.data) && Array.isArray(payload.warnings);
  }
  async function send(url, {
    method = 'GET',
    body,
    signal,
    readOnly = false,
    binary = false
  } = {}) {
    const target = new URL(url, location.href);
    if (target.origin !== location.origin || !target.pathname.startsWith(prefix)) throw problem('数据地址不属于本机工作台。', false);
    const writing = method !== 'GET' && !readOnly;
    const headers = {
      Accept: binary ? 'application/octet-stream,application/json' : 'application/json'
    };
    let payload = body;
    if (body !== undefined && !(body instanceof FormData)) {
      try {
        payload = JSON.stringify(body);
      } catch (_) {
        throw problem('保存内容无法编码，本次未提交。', false);
      }
      headers['Content-Type'] = 'application/json';
    }
    if (signal && signal.aborted) throw problem('请求已取消，本次未发送。', false);
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    if (signal) signal.addEventListener('abort', abort, {
      once: true
    });
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, 20000);
    try {
      const response = await fetch(target.href, {
        method,
        body: payload,
        headers,
        signal: controller.signal,
        credentials: 'same-origin',
        redirect: 'error',
        cache: 'no-store'
      });
      const type = (response.headers.get('content-type') || '').toLowerCase();
      if (binary && response.ok && !type.includes('application/json')) {
        if (!['text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'].some(value => type.startsWith(value))) throw problem('下载内容格式不正确，未作为文件保存。', false);
        const blob = await response.blob();
        if (!blob.size) throw problem('下载文件为空，未视为导出成功。', false);
        return {
          blob,
          contentType: type,
          disposition: response.headers.get('content-disposition') || ''
        };
      }
      if (!type.includes('application/json')) throw problem('本机服务返回了非预期的数据格式。', writing ? 'unknown' : false);
      const result = await response.json();
      if (failure(result)) throw problem(result.error.message, result.committed, result.error);
      if (!response.ok) throw problem('本机服务未能确认本次请求的结果。', writing ? 'unknown' : false);
      return result;
    } catch (error) {
      if (error && [false, true, 'unknown'].includes(error.committed)) throw error;
      const message = timedOut ? '本机请求超时。' : error && error.name === 'AbortError' ? '请求连接已中断。' : '无法取得本机服务的有效响应。';
      throw problem(message + (writing ? '保存结果待核实，请查询原请求回执，不要重复提交。' : '请重新读取。'), writing ? 'unknown' : false);
    } finally {
      clearTimeout(timer);
      if (signal) signal.removeEventListener('abort', abort);
    }
  }
  function production(result) {
    if (!object(result) || result.ok !== true || result.schema_version !== 1 || !object(result.data) || !object(result.meta) || result.meta.source !== 'production' || result.meta.time_basis !== 'factory_local' || typeof result.meta.snapshot_ref !== 'string' || !result.meta.snapshot_ref || typeof result.meta.request_ref !== 'string' || !result.meta.request_ref || typeof result.meta.as_of !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(result.meta.as_of) || !Array.isArray(result.warnings)) throw problem('本机资源数据协议不匹配，未使用样例替代。', false);
    return result;
  }
  function validIntent(value) {
    if (!object(value) || typeof value.request_key !== 'string' || !/^resource-[0-9a-f]{48}$/.test(value.request_key)) return false;
    if (value.kind === 'calendar') return typeof value.ref === 'string' && (['upsert', 'delete'].includes(value.action) && /^\d{4}-\d{2}-\d{2}$/.test(value.ref) || value.action === 'confirm' && /^[0-9a-f]{32}$/.test(value.ref));
    if (value.kind === 'process') return value.category === undefined && (value.action === 'create' && value.ref === null || ['route_confirm', 'source_confirm', 'hours_confirm'].includes(value.action) && typeof value.ref === 'string' && /^[0-9a-f]{48}$/.test(value.ref));
    if (['process_bulk', 'process_route_import', 'process_hours_import'].includes(value.kind)) return value.action === 'confirm' && typeof value.ref === 'string' && /^[A-Za-z0-9_-]{32}$/.test(value.ref) && value.category === undefined;
    if (value.kind === 'batch') return value.category === undefined && (value.action === 'create' && value.ref === null || ['update', 'delete', 'operation_update', 'sync_confirm'].includes(value.action) && typeof value.ref === 'string' && /^[0-9a-f]{48}$/.test(value.ref) || ['bulk_confirm', 'import_confirm'].includes(value.action) && typeof value.ref === 'string' && /^[A-Za-z0-9_-]{32}$/.test(value.ref));
    if (value.kind === 'execution') return value.category === undefined && typeof value.ref === 'string' && (['create', 'supplement', 'correct'].includes(value.action) && /^[0-9a-f]{48}$/.test(value.ref) || value.action === 'import_confirm' && /^[A-Za-z0-9_-]{32}$/.test(value.ref));
    const file = typeof value.kind === 'string' && /^(material|op_type|machine|operator|supplier)_(import|bulk)$/.exec(value.kind);
    if (file) return value.action === 'confirm' && typeof value.ref === 'string' && /^[A-Za-z0-9_-]{32}$/.test(value.ref) && (file[1] === 'op_type' ? ['internal', 'external'].includes(value.category) : value.category === undefined);
    return kinds.has(value.kind) && ['create', 'update', 'delete'].includes(value.action) && (value.action === 'create' ? value.ref === null : typeof value.ref === 'string' && /^[0-9a-f]{48}$/.test(value.ref)) && (value.category === undefined || ['internal', 'external'].includes(value.category));
  }
  function matchesNamespace(namespace, intent) {
    if (namespace === 'resources') return kinds.has(intent.kind);
    if (namespace === 'calendar') return intent.kind === 'calendar';
    if (namespace === 'process') return ['process', 'process_bulk', 'process_route_import', 'process_hours_import'].includes(intent.kind);
    if (namespace === 'batches') return intent.kind === 'batch';
    if (namespace === 'execution') return intent.kind === 'execution';
    if (namespace === 'catalog') return ['machine_group', 'shift_profile'].includes(intent.kind);
    const kind = namespace.slice(0, -6);
    return fileKinds.has(kind) && [kind + '_import', kind + '_bulk'].includes(intent.kind);
  }
  function create(namespace = 'resources') {
    if (!['resources', 'calendar', 'catalog', 'process', 'batches', 'execution'].includes(namespace) && !Array.from(fileKinds).some(kind => namespace === kind + '_files')) throw problem('资源操作工作区不正确。', false);
    const pendingKey = 'aps_workbench_resource_pending_v1' + (namespace === 'resources' ? '' : '_' + namespace);
    const api = {
      async query(path, scope, signal) {
        return production(await send(queryPath(path, scope), {
          signal
        }));
      },
      async preview(path, body, signal) {
        return production(await send(endpoint(path), {
          method: 'POST',
          body,
          signal,
          readOnly: true
        }));
      },
      async execute(path, body, signal) {
        const result = await send(endpoint(path), {
          method: 'POST',
          body,
          signal
        });
        if (!terminal(result)) throw problem('保存回执不完整，结果待核实。', 'unknown');
        return result;
      },
      list(kind, scope, signal) {
        const normalized = tableScope(scope);
        return normalized.column_filters ? api.preview(resource(kind) + '/query', normalized, signal) : api.query(resource(kind), normalized, signal);
      },
      facets(kind, request, signal) {
        return api.preview(resource(kind) + '/facets', {
          ...request,
          scope: tableScope(request.scope)
        }, signal);
      },
      facetSelection(kind, request, signal) {
        return api.preview(resource(kind) + '/facet-selection', {
          ...request,
          scope: tableScope(request.scope)
        }, signal);
      },
      choices(kind, scope, signal) {
        return api.list(kind, scope, signal);
      },
      detail(kind, ref, signal) {
        return api.query(resource(kind, ref), {}, signal);
      },
      relations(ref, scope, signal) {
        return api.query(resource('op_type', ref) + '/relations', scope, signal);
      },
      summary(signal) {
        return api.query('resources/summary', {}, signal);
      },
      command(kind, action, ref, body, signal) {
        if (!['create', 'update', 'delete'].includes(action) || action === 'create' !== (ref === null)) throw problem('保存操作与所选对象不一致。', false);
        return api.execute(resource(kind, ref) + '/' + action, body, signal);
      },
      async lookup(key, signal) {
        if (typeof key !== 'string' || !/^[A-Za-z0-9_-]{16,128}$/.test(key)) throw problem('原请求标识无效。', false);
        const result = await send(endpoint('commands/' + key), {
          signal
        });
        if (terminal(result) || result && result.ok === true && result.state === 'not_recorded' && result.receipt === null && result.may_be_in_flight === true) return result;
        throw problem('原请求回执无法确认，请保留当前页面继续核实。', 'unknown');
      },
      download(path, scope, signal) {
        return send(queryPath(path, scope), {
          signal,
          binary: true
        });
      },
      readPending() {
        try {
          const raw = sessionStorage.getItem(pendingKey);
          if (raw === null) return null;
          const intent = JSON.parse(raw);
          if (!validIntent(intent) || !matchesNamespace(namespace, intent)) throw new Error('invalid');
          return intent;
        } catch (_) {
          throw problem('待核实请求记录无法读取，请先检查浏览器存储，暂不能继续保存。', 'unknown');
        }
      },
      savePending(intent) {
        if (!validIntent(intent) || !matchesNamespace(namespace, intent)) throw problem('原请求标识无法保留，本次未提交。', false);
        const stored = {
          kind: intent.kind,
          action: intent.action,
          ref: intent.ref,
          request_key: intent.request_key
        };
        if (intent.category !== undefined) stored.category = intent.category;
        try {
          sessionStorage.setItem(pendingKey, JSON.stringify(stored));
        } catch (_) {
          throw problem('无法保留原请求标识，本次未提交；请检查浏览器存储。', false);
        }
      },
      clearPending() {
        try {
          sessionStorage.removeItem(pendingKey);
        } catch (_) {
          throw problem('已核实结果，但本机待核实标记清理失败；重新打开后可再次查询原回执。', false);
        }
      }
    };
    return api;
  }
  window.APSResourceAPI = {
    create
  };
})();
