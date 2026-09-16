(function () {
  'use strict';

  const BASE = '/api/workbench/v1/system',
    PENDING_KEY = 'aps_workbench_system_pending_v1';
  const actions = {
    create: '新增备份',
    delete: '删除所选备份',
    restore: '恢复所选备份',
    config: '保存八项维护配置'
  };
  const states = ['accepted', 'checking', 'protecting', 'restoring', 'verifying', 'rolling_back', 'succeeded', 'failed', 'rolled_back', 'rollback_failed', 'recovery_required'];
  const terminalStates = ['succeeded', 'failed', 'rolled_back'];
  const fields = [['auto_backup_enabled', '自动备份', 'backup'], ['auto_backup_interval_minutes', '备份检查间隔', 'backup'], ['auto_backup_cleanup_enabled', '清理过期备份', 'backup'], ['auto_backup_keep_days', '备份保留时间', 'backup'], ['auto_backup_cleanup_interval_minutes', '备份清理检查间隔', 'backup'], ['auto_log_cleanup_enabled', '清理操作日志', 'logs'], ['auto_log_cleanup_keep_days', '操作日志保留时间', 'logs'], ['auto_log_cleanup_interval_minutes', '日志清理检查间隔', 'logs']].map(([key, label, group]) => ({
    key,
    label,
    group,
    switch: key.endsWith('_enabled'),
    max: key.endsWith('_days') ? 365 : 1440,
    unit: key.endsWith('_days') ? '天' : '分钟'
  }));
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const text = value => typeof value === 'string',
    nonempty = value => text(value) && value.length > 0;
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const context = value => object(value) && nonempty(value.write_token);
  function check(valid, message = '读到的维护数据不完整，页面没有改动。请刷新后重试。') {
    if (!valid) throw new Error(message);
  }
  function envelope(value) {
    check(object(value) && value.ok === true && value.schema_version === 1 && object(value.data) && object(value.meta) && value.meta.source === 'production' && value.meta.time_basis === 'factory_local' && nonempty(value.meta.snapshot_ref) && nonempty(value.meta.as_of) && Array.isArray(value.warnings));
    return value.data;
  }
  function config(value, writable = true) {
    check(object(value) && object(value.values) && object(value.stored_values) && object(value.dirty_reasons) && Array.isArray(value.dirty_fields) && Array.isArray(value.defaulted_fields) && (!writable || context(value.write_context)));
    check(fields.every(field => field.switch ? ['yes', 'no'].includes(value.values[field.key]) : count(value.values[field.key])));
    check(value.dirty_fields.concat(value.defaulted_fields).every(key => fields.some(field => field.key === key)) && value.dirty_fields.every(key => text(value.dirty_reasons[key])) && fields.every(field => value.stored_values[field.key] === null || text(value.stored_values[field.key])));
    return value;
  }
  function backupFile(row) {
    return object(row) && row.record_kind === 'backup_file' && !['event_ref', 'event_source', 'file_capabilities'].some(key => Object.prototype.hasOwnProperty.call(row, key)) && /^[a-f0-9]{64}$/.test(row.key) && nonempty(row.filename) && count(row.size_bytes) && nonempty(row.backup_ref) && context(row.write_context) && ['manual', 'auto', 'before_restore', 'unknown'].includes(row.type) && row.status === 'unverified' && row.file_exists === true && row.verification_state === 'not_checked' && row.last_run_result === null;
  }
  function maintenanceEvent(row) {
    if (!object(row) || !['restore_event', 'cleanup_event'].includes(row.record_kind)) return false;
    const caps = row.file_capabilities;
    return object(caps) && Object.keys(caps).length === 3 && ['download', 'restore', 'delete'].every(key => caps[key] === false) && !['backup_ref', 'write_context', 'filename', 'size_bytes', '_signature', 'file_exists', 'verification_state'].some(key => Object.prototype.hasOwnProperty.call(row, key)) && nonempty(row.event_ref) && (row.record_kind === 'restore_event' ? row.type === 'restore' && states.includes(row.status) && row.event_source === 'external_maintenance_journal' && /^[a-f0-9]{32}$/.test(row.event_ref) : row.type === 'cleanup' && ['succeeded', 'failed', 'unknown'].includes(row.status) && ['operation_audit', 'latest_job_state_only'].includes(row.event_source));
  }
  function collection(value, kind) {
    const data = envelope(value),
      page = data.page;
    check(object(page) && ['number', 'size', 'total', 'pages'].every(key => count(page[key])) && page.number >= 1 && [10, 25, 50].includes(page.size) && page.pages === Math.max(1, Math.ceil(page.total / page.size)) && page.number <= page.pages && Array.isArray(data.rows) && data.rows.length === Math.min(page.size, Math.max(0, page.total - (page.number - 1) * page.size)) && Array.isArray(data.sources) && data.scope === (kind === 'backups' ? 'backup-files-and-maintenance-events' : 'bounded-log-windows'));
    check(new Set(data.rows.map(row => row.key)).size === data.rows.length && data.rows.every(row => object(row) && nonempty(row.key) && (row.time === null || nonempty(row.time)) && text(row.summary) && text(row.body) && (kind === 'backups' ? backupFile(row) || maintenanceEvent(row) : ['runtime', 'operation'].includes(row.type) && row.status === 'recorded' && text(row.level) && text(row.file) && typeof row.content_truncated === 'boolean')));
    if (kind === 'backups') {
      const caps = data.capabilities;
      check(object(caps) && ['create', 'delete', 'restore'].every(key => typeof caps[key] === 'boolean') && text(caps.blocked_reason) && text(caps.restore_reason) && context(data.create_context));
      check(data.sources.every(item => object(item) && nonempty(item.code) && nonempty(item.message)));
    } else check(data.sources.every(item => object(item) && nonempty(item.source) && ['available', 'empty', 'missing', 'error'].includes(item.state) && [200, 500].includes(item.window) && (item.count === null || count(item.count)) && typeof item.truncated === 'boolean'));
    return value;
  }
  function receipt(value) {
    check(object(value) && value.ok === true && ['committed', 'unchanged'].includes(value.result) && nonempty(value.receipt_ref) && typeof value.replayed === 'boolean' && Array.isArray(value.warnings) && object(value.data) && typeof value.data.audit_persisted === 'boolean');
    config(value.data.config, false);
    check(value.data.audit_persisted === (value.result === 'committed'));
    return {
      kind: 'config',
      command: value,
      terminal: true
    };
  }
  function result(value, intent) {
    const external = object(value) && object(value.meta) && value.meta.result_source === 'external_maintenance_journal';
    const data = external ? window.SystemRestoreStatus.envelope(value) : envelope(value);
    if (data.host) window.SystemRestoreStatus.validateHost(data.host);
    if (data.kind === 'not_recorded') {
      check(text(data.message));
      return {
        ...data,
        terminal: false
      };
    }
    if (data.kind === 'config') {
      check(intent.action === 'config');
      return receipt(data.command);
    }
    const op = data.operation;
    check(data.kind === 'file_operation' && intent.action !== 'config' && object(op) && /^[a-f0-9]{32}$/.test(op.job_ref) && op.request_key === intent.request_key && op.action === intent.action && states.includes(op.state) && op.terminal === terminalStates.includes(op.state) && nonempty(op.code) && text(op.message) && nonempty(op.updated_at) && typeof op.audit_persisted === 'boolean' && typeof op.replayed === 'boolean' && (op.filename === null || text(op.filename)) && (op.protection_filename === null || text(op.protection_filename)) && Array.isArray(op.history) && op.history.every(item => object(item) && states.includes(item.state) && nonempty(item.time)));
    window.SystemRestoreStatus.operation(op);
    return {
      ...data,
      terminal: op.terminal
    };
  }
  function blocked(data, action) {
    if (!data || !object(data.capabilities)) return '还没有读到本机可以做哪些文件操作。';
    const caps = data.capabilities,
      reason = action === 'restore' ? caps.restore_reason || caps.blocked_reason : caps.blocked_reason;
    return reason || (caps[action] === true ? '' : '系统不允许这项文件操作，也没有给出原因。');
  }
  function normalize(draft) {
    const values = {},
      errors = {};
    fields.forEach(field => {
      const raw = draft[field.key];
      if (field.switch) {
        if (!['yes', 'no'].includes(raw)) errors[field.key] = '请选择启用或关闭。';
        values[field.key] = raw;
      } else {
        const valid = /^\d+$/.test(String(raw)) && Number.isSafeInteger(Number(raw)) && Number(raw) >= 1 && Number(raw) <= field.max;
        if (!valid) errors[field.key] = '请输入 1 至 ' + field.max + ' 的整数。';
        values[field.key] = Number(raw);
      }
    });
    return {
      values,
      errors,
      valid: !Object.keys(errors).length
    };
  }
  function validIntent(value) {
    return object(value) && Object.keys(value).length === 3 && /^system-[a-f0-9]{48}$/.test(value.request_key) && Object.prototype.hasOwnProperty.call(actions, value.action) && value.summary === actions[value.action];
  }
  function pending(storage = window.localStorage) {
    return {
      read() {
        const raw = storage.getItem(PENDING_KEY);
        if (raw === null) return null;
        let value;
        try {
          value = JSON.parse(raw);
        } catch (_) {
          throw new Error('上次操作记录损坏，请联系维护人员核对。');
        }
        check(validIntent(value), '本机存的上次操作记录不完整，已停止新的操作。请不要再操作，联系维护人员。');
        return value;
      },
      begin(action) {
        check(Object.prototype.hasOwnProperty.call(actions, action), '未知维护动作。');
        check(!this.read(), '还有一次操作没有确认结果，不能重新发起。请先点「查询结果」。');
        const bytes = new Uint8Array(24);
        window.crypto.getRandomValues(bytes);
        const value = {
          request_key: 'system-' + Array.from(bytes, n => n.toString(16).padStart(2, '0')).join(''),
          action,
          summary: actions[action]
        };
        storage.setItem(PENDING_KEY, JSON.stringify(value));
        check(this.read().request_key === value.request_key, '操作编号没能存下来，这次没有发起操作。请刷新后重试。');
        return value;
      },
      finish(intent) {
        const saved = this.read();
        check(saved && saved.request_key === intent.request_key, '上次操作记录已变化，没有删除其他记录。请刷新后重新确认。');
        storage.removeItem(PENDING_KEY);
      }
    };
  }
  function errorResponse(value, status) {
    const valid = object(value) && value.ok === false && object(value.error) && text(value.error.message) && text(value.error.code);
    const problem = new Error(valid ? value.error.message : '没有读到有效的维护结果，这次没有改动。请点「查询结果」。');
    problem.code = valid ? value.error.code : 'invalid_response';
    problem.status = status;
    problem.rejected = valid && value.committed === false && status >= 400 && status < 500 && ['invalid_input', 'stale_write', 'constraint_conflict', 'entity_not_found'].includes(problem.code);
    return problem;
  }
  function inspectPending() {
    try {
      return {
        intent: pending().read(),
        storageError: null
      };
    } catch (storageError) {
      return {
        intent: null,
        storageError
      };
    }
  }
  function parameters(input) {
    const params = new URLSearchParams();
    Object.entries(input || {}).forEach(([key, value]) => {
      if (value !== '' && value !== undefined && value !== null) params.set(key, value);
    });
    return params.toString() ? '?' + params : '';
  }
  function recordSelection(selection, kind) {
    if (selection === undefined || selection === null) return null;
    check(object(selection) && Object.keys(selection).every(key => ['key', 'backup_ref', 'record_kind'].includes(key)) && (selection.key === undefined || nonempty(selection.key)) && (selection.record_kind === undefined || ['backup_file', 'restore_event', 'cleanup_event'].includes(selection.record_kind)) && (selection.backup_ref === undefined || nonempty(selection.backup_ref) && (selection.record_kind === undefined || selection.record_kind === 'backup_file')), '原先选中的记录已失效，请重新选择。');
    check(kind !== 'logs' || nonempty(selection.key) && selection.backup_ref === undefined && selection.record_kind === undefined, '原先选中的日志记录编号不对，请重新选择。');
    const recordKind = selection.record_kind || (kind === 'backups' && selection.backup_ref ? 'backup_file' : undefined);
    return {
      ...(selection.key !== undefined ? {
        key: selection.key
      } : {}),
      ...(recordKind ? {
        record_kind: recordKind
      } : {})
    };
  }
  function recordContext(value = {}, kind) {
    check(object(value) && Object.keys(value).every(key => ['filters', 'page', 'snapshot_ref', 'selection'].includes(key)), '上次的筛选和翻页状态无法恢复。请刷新后重新筛选。');
    const filters = {
      query: '',
      type: '',
      status: '',
      level: '',
      file: '',
      start: '',
      end: '',
      ...(value.filters || {})
    };
    check((value.filters === undefined || object(value.filters)) && Object.keys(filters).every(key => ['query', 'type', 'status', 'level', 'file', 'start', 'end'].includes(key) && text(filters[key]) && filters[key].length <= 200), '上次的筛选条件无法恢复。请刷新后重新筛选。');
    const page = value.page === undefined ? 1 : value.page,
      snapshot = value.snapshot_ref === undefined ? '' : value.snapshot_ref;
    check(count(page) && page >= 1 && page <= 100000 && text(snapshot), '上次的页码或数据版本无法恢复。请刷新后重新翻页。');
    return {
      filters,
      page,
      selection: recordSelection(value.selection, kind)
    };
  }
  function pageContext(value = {}) {
    check(object(value) && Object.keys(value).every(key => ['source', 'tab', 'page_size', 'records'].includes(key)), '上次的页面状态无法恢复。请从侧栏重新打开系统管理。');
    const source = value.source === undefined ? 'current' : value.source,
      tab = value.tab === undefined ? 'overview' : value.tab;
    const size = value.page_size === undefined ? 10 : value.page_size,
      records = value.records === undefined ? {} : value.records;
    check(['current', 'sample'].includes(source) && ['overview', 'backups', 'logs', 'config'].includes(tab) && [10, 25, 50].includes(size) && object(records) && Object.keys(records).every(key => ['backups', 'logs'].includes(key)), '上次的页面状态不完整，无法恢复。请从侧栏重新打开系统管理。');
    return {
      source,
      tab,
      page_size: size,
      records: Object.fromEntries(Object.entries(records).map(([kind, item]) => [kind, recordContext(item, kind)]))
    };
  }
  function create(fetcher = window.fetch.bind(window)) {
    async function exchange(path, options, consume) {
      const controller = new AbortController(),
        external = options.signal;
      const abort = () => controller.abort();
      let expired = false;
      if (external) {
        if (external.aborted) abort();else external.addEventListener('abort', abort, {
          once: true
        });
      }
      const timer = setTimeout(() => {
        expired = true;
        abort();
      }, 30000);
      try {
        const response = await fetcher(BASE + path, {
          credentials: 'same-origin',
          cache: 'no-store',
          redirect: 'error',
          ...options,
          signal: controller.signal
        });
        return await consume(response);
      } catch (problem) {
        if (expired) throw new Error(window.WorkbenchTerms.outcomes.pending('维护操作'));
        throw problem;
      } finally {
        clearTimeout(timer);
        if (external) external.removeEventListener('abort', abort);
      }
    }
    async function request(path, options = {}) {
      return exchange(path, options, async response => {
        const mime = (response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase();
        if (mime !== 'application/json') throw new Error(window.WorkbenchTerms.outcomes.unknown('维护操作'));
        const payload = await response.json();
        if (!response.ok || payload.ok !== true) throw errorResponse(payload, response.status);
        return payload;
      });
    }
    return {
      async host(signal) {
        return window.SystemRestoreStatus.host(await request('/restore-host', {
          signal
        }));
      },
      async read(kind, input, signal) {
        check(['backups', 'logs', 'config'].includes(kind));
        const value = await request('/' + kind + parameters(input), {
          signal
        });
        if (kind === 'config') config(envelope(value));else {
          collection(value, kind);
          const query = input || {};
          check(value.data.page.number === (query.page === undefined ? 1 : query.page) && value.data.page.size === (query.page_size === undefined ? 10 : query.page_size) && (!query.snapshot_ref || value.meta.snapshot_ref === query.snapshot_ref), '读到的维护记录和刚才的筛选不一致，页面没有改动。请刷新后重试。');
        }
        return value;
      },
      async command(intent, token, input) {
        check(validIntent(intent) && nonempty(token));
        const payload = await request(intent.action === 'config' ? '/config/save' : '/backups/' + intent.action, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            request_key: intent.request_key,
            write_token: token,
            input
          })
        });
        return intent.action === 'config' ? receipt(payload) : result(payload, intent);
      },
      async lookup(intent, jobRef, signal) {
        check(validIntent(intent) && (!jobRef || /^[a-f0-9]{32}$/.test(jobRef)));
        return result(await request(jobRef ? '/jobs/' + jobRef : '/results/' + intent.request_key, {
          signal
        }), intent);
      },
      async lookupReference(reference, kind = 'request', signal) {
        const path = window.SystemRestoreStatus.referencePath(reference, kind);
        const value = await request(path, {
            signal
          }),
          op = value.data && value.data.operation;
        if (op && path.startsWith('/jobs/')) check(op.job_ref === reference, '返回的维护记录不是所查询的记录。');
        return result(value, {
          action: op && op.action,
          request_key: path.startsWith('/jobs/') ? op && op.request_key : reference
        });
      },
      async download(format, input, signal) {
        check(['csv', 'zip'].includes(format) && nonempty(input.snapshot_ref), '还没有读到日志，不能导出。请先点「查询」。');
        return exchange('/logs/export/' + format + parameters(input), {
          signal
        }, async response => {
          const blob = await response.blob(),
            mime = (response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase();
          check(blob instanceof Blob && blob.size > 0, '下载内容为空，没有保存文件。请刷新后重试。');
          const prefix = await blob.slice(0, 8192).text();
          if (mime === 'application/json' || /^[\s\ufeff]*[\[{]/.test(prefix)) {
            let payload;
            try {
              payload = JSON.parse(prefix);
            } catch (_) {
              throw new Error('下载返回的不是日志文件，没有保存。请刷新后重试。');
            }
            throw errorResponse(payload, response.status);
          }
          const expected = format === 'csv' ? 'text/csv' : 'application/zip';
          check(response.ok && mime === expected && blob.type.split(';')[0].trim().toLowerCase() === expected, '下载的文件类型不对，没有保存。请刷新后重试。');
          const magic = new Uint8Array(await blob.slice(0, 4).arrayBuffer());
          check(format === 'zip' ? magic[0] === 80 && magic[1] === 75 && magic[2] === 3 && magic[3] === 4 : magic[0] === 239 && magic[1] === 187 && magic[2] === 191 && prefix.startsWith('来源,时间,'), '下载内容与日志文件格式不符。');
          const filename = format === 'csv' ? '系统日志片段.csv' : '系统诊断包-已脱敏.zip';
          const url = URL.createObjectURL(blob),
            link = document.createElement('a');
          link.href = url;
          link.download = filename;
          try {
            document.body.appendChild(link);
            link.click();
          } finally {
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          }
          return {
            filename,
            bytes: blob.size
          };
        });
      },
      async downloadBackup(row, input, signal) {
        check(object(row) && row.record_kind === 'backup_file' && !['event_ref', 'event_source'].some(key => Object.prototype.hasOwnProperty.call(row, key)) && nonempty(row.backup_ref) && nonempty(row.filename) && count(row.size_bytes) && object(input) && nonempty(input.snapshot_ref), '请先读取备份清单再选择文件。');
        return exchange('/backups/' + encodeURIComponent(row.backup_ref) + '/download' + parameters(input), {
          signal
        }, async response => {
          const blob = await response.blob(),
            mime = (response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase();
          const prefix = await blob.slice(0, 8192).text();
          if (mime === 'application/json' || /^[\s\ufeff]*[\[{]/.test(prefix)) {
            let payload;
            try {
              payload = JSON.parse(prefix);
            } catch (_) {
              throw new Error('备份下载返回的不是备份文件，没有保存。请刷新后重试。');
            }
            throw errorResponse(payload, response.status);
          }
          check(response.ok && mime === 'application/vnd.sqlite3' && blob.size > 0 && blob.size === row.size_bytes && Number(response.headers.get('Content-Length')) === blob.size, '备份下载状态、类型或大小与原清单不一致。');
          const disposition = response.headers.get('Content-Disposition') || '',
            match = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
          check(/^attachment;/i.test(disposition) && match && decodeURIComponent(match[1]) === row.filename && response.headers.get('X-APS-Backup-Ref') === row.backup_ref, '下载到的不是刚才选中的备份文件，没有保存。');
          check((await blob.slice(0, 16).text()) === 'SQLite format 3\u0000', '下载内容不是备份数据库文件，没有保存。');
          const url = URL.createObjectURL(blob),
            link = document.createElement('a');
          link.href = url;
          link.download = row.filename;
          try {
            document.body.appendChild(link);
            link.click();
          } finally {
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          }
          return {
            filename: row.filename,
            bytes: blob.size
          };
        });
      }
    };
  }
  window.SystemMaintenanceAPI = {
    create,
    pending,
    inspectPending,
    PENDING_KEY,
    fields,
    actions,
    states,
    terminalStates,
    collection,
    config,
    receipt,
    result,
    blocked,
    normalize,
    recordContext,
    pageContext,
    backupFile,
    maintenanceEvent
  };
})();
