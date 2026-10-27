(function () {
  'use strict';
  const T = window.APSWorkbenchTransport, BASE = '/api/workbench/v1/system', PENDING_KEY = 'aps_workbench_system_pending_v1';
  const actions = { create: '新增备份', delete: '删除所选备份', restore: '恢复所选备份', config: '保存八项维护配置' };
  const states = ['accepted', 'checking', 'protecting', 'restoring', 'verifying', 'rolling_back', 'succeeded', 'failed', 'rolled_back', 'rollback_failed', 'recovery_required'];
  const terminalStates = ['succeeded', 'failed', 'rolled_back'];
  const fields = [
    ['auto_backup_enabled', '自动备份', 'backup'], ['auto_backup_interval_minutes', '备份检查间隔', 'backup'],
    ['auto_backup_cleanup_enabled', '清理过期备份', 'backup'], ['auto_backup_keep_days', '备份保留时间', 'backup'],
    ['auto_backup_cleanup_interval_minutes', '备份清理检查间隔', 'backup'], ['auto_log_cleanup_enabled', '清理操作日志', 'logs'],
    ['auto_log_cleanup_keep_days', '操作日志保留时间', 'logs'], ['auto_log_cleanup_interval_minutes', '日志清理检查间隔', 'logs']
  ].map(([key, label, group]) => ({ key, label, group, switch: key.endsWith('_enabled'), max: key.endsWith('_days') ? 365 : 1440, unit: key.endsWith('_days') ? '天' : '分钟' }));
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const text = value => typeof value === 'string', nonempty = value => text(value) && value.length > 0;
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const context = value => object(value) && nonempty(value.write_token);
  function check(valid, message = '读到的维护数据不完整，页面没有改动。请刷新后重试。') { if (!valid) throw new Error(message); }
  // 存储值损坏时后端直接拒绝读取，这里只会读到八项有效值和尚未保存的默认项。
  function config(value, writable = true) {
    check(object(value) && object(value.values) && Array.isArray(value.defaulted_fields) && (!writable || context(value.write_context)));
    check(fields.every(field => field.switch ? ['yes', 'no'].includes(value.values[field.key]) : count(value.values[field.key])));
    check(value.defaulted_fields.every(key => fields.some(field => field.key === key)));
    return value;
  }
  function backupFile(row) {
    return object(row) && row.record_kind === 'backup_file' && !['event_ref', 'event_source', 'file_capabilities'].some(key => Object.prototype.hasOwnProperty.call(row, key))
      && nonempty(row.key) && nonempty(row.filename) && count(row.size_bytes) && nonempty(row.backup_ref) && context(row.write_context)
      && ['manual', 'auto', 'before_restore', 'unknown'].includes(row.type) && row.status === 'unverified'
      && row.file_exists === true && row.verification_state === 'not_checked' && row.last_run_result === null;
  }
  function maintenanceEvent(row) {
    if (!object(row) || !['restore_event', 'cleanup_event'].includes(row.record_kind)) return false;
    const caps = row.file_capabilities;
    return object(caps) && Object.keys(caps).length === 3 && ['download', 'restore', 'delete'].every(key => caps[key] === false)
      && !['backup_ref', 'write_context', 'filename', 'size_bytes', '_signature', 'file_exists', 'verification_state'].some(key => Object.prototype.hasOwnProperty.call(row, key))
      && nonempty(row.event_ref) && (row.record_kind === 'restore_event' ? row.type === 'restore' && states.includes(row.status)
        && row.event_source === 'external_maintenance_journal' && /^[a-f0-9]{32}$/.test(row.event_ref)
        : row.type === 'cleanup' && ['succeeded', 'failed', 'unknown'].includes(row.status) && ['operation_audit', 'latest_job_state_only'].includes(row.event_source));
  }
  // 清单读取已由 transport 校验过信封；翻页和导出还要用这次读取的数据版本。
  function collection(value, kind) {
    const data = value.data, page = data.page;
    check(nonempty(value.meta.snapshot_ref) && object(page) && ['number', 'size', 'total', 'pages'].every(key => count(page[key])) && page.number >= 1
      && [10, 25, 50].includes(page.size) && page.pages === Math.max(1, Math.ceil(page.total / page.size)) && page.number <= page.pages
      && Array.isArray(data.rows) && data.rows.length === Math.min(page.size, Math.max(0, page.total - (page.number - 1) * page.size))
      && Array.isArray(data.sources) && data.scope === (kind === 'backups' ? 'backup-files-and-maintenance-events' : 'bounded-log-windows'));
    check(new Set(data.rows.map(row => row.key)).size === data.rows.length && data.rows.every(row => object(row)
      && nonempty(row.key) && (row.time === null || nonempty(row.time)) && text(row.summary) && text(row.body)
      && (kind === 'backups' ? backupFile(row) || maintenanceEvent(row)
        : ['runtime', 'operation'].includes(row.type) && row.status === 'recorded' && text(row.level) && text(row.file) && typeof row.content_truncated === 'boolean')));
    if (kind === 'backups') {
      const caps = data.capabilities;
      check(object(caps) && ['create', 'delete', 'restore'].every(key => typeof caps[key] === 'boolean')
        && text(caps.blocked_reason) && text(caps.restore_reason) && context(data.create_context));
      check(data.sources.every(item => object(item) && nonempty(item.code) && nonempty(item.message)));
    } else check(data.sources.every(item => object(item) && nonempty(item.source) && ['available', 'empty', 'missing', 'error'].includes(item.state)
      && [200, 500].includes(item.window) && (item.count === null || count(item.count)) && typeof item.truncated === 'boolean'));
    return value;
  }
  function receipt(value) {
    check(object(value) && value.ok === true && ['committed', 'unchanged'].includes(value.result) && nonempty(value.receipt_ref)
      && typeof value.replayed === 'boolean' && Array.isArray(value.warnings) && object(value.data) && typeof value.data.audit_persisted === 'boolean');
    config(value.data.config, false);
    check(value.data.audit_persisted === (value.result === 'committed'));
    return { kind: 'config', command: value, terminal: true };
  }
  function result(value, intent) {
    // 回执查询拿到的是原始 JSON：维护期间由维护日志服务器作答，平时是标准信封。
    const external = object(value) && object(value.meta) && value.meta.result_source === 'external_maintenance_journal';
    if (!external) T.envelope(value);
    const data = external ? window.SystemRestoreStatus.envelope(value) : value.data;
    if (!external && data.host) window.SystemRestoreStatus.validateHost(data.host);
    if (data.kind === 'not_recorded') { check(text(data.message)); return { ...data, terminal: false }; }
    if (data.kind === 'config') { check(intent.action === 'config'); return receipt(data.command); }
    const op = data.operation;
    check(data.kind === 'file_operation' && intent.action !== 'config' && object(op) && /^[a-f0-9]{32}$/.test(op.job_ref)
      && op.request_key === intent.request_key && op.action === intent.action && states.includes(op.state)
      && op.terminal === terminalStates.includes(op.state) && nonempty(op.code) && text(op.message) && nonempty(op.updated_at)
      && typeof op.audit_persisted === 'boolean' && typeof op.replayed === 'boolean'
      && (op.filename === null || text(op.filename)) && (op.protection_filename === null || text(op.protection_filename))
      && Array.isArray(op.history) && op.history.every(item => object(item) && states.includes(item.state) && nonempty(item.time)));
    window.SystemRestoreStatus.operation(op);
    return { ...data, terminal: op.terminal };
  }
  function blocked(data, action) {
    if (!data || !object(data.capabilities)) return '还没有读到本机可以做哪些文件操作。';
    const caps = data.capabilities, reason = action === 'restore' ? caps.restore_reason || caps.blocked_reason : caps.blocked_reason;
    return reason || (caps[action] === true ? '' : '系统不允许这项文件操作，也没有给出原因。');
  }
  function normalize(draft) {
    const values = {}, errors = {};
    fields.forEach(field => {
      const raw = draft[field.key];
      if (field.switch) { if (!['yes', 'no'].includes(raw)) errors[field.key] = '请选择启用或关闭。'; values[field.key] = raw; }
      else {
        const valid = /^\d+$/.test(String(raw)) && Number.isSafeInteger(Number(raw)) && Number(raw) >= 1 && Number(raw) <= field.max;
        if (!valid) errors[field.key] = '请输入 1 至 ' + field.max + ' 的整数。';
        values[field.key] = Number(raw);
      }
    });
    return { values, errors, valid: !Object.keys(errors).length };
  }
  function validIntent(value) {
    return object(value) && Object.keys(value).length === 3 && /^system-[a-f0-9]{48}$/.test(value.request_key)
      && Object.prototype.hasOwnProperty.call(actions, value.action) && value.summary === actions[value.action];
  }
  function pending(storage = window.localStorage) {
    return {
      read() {
        const raw = storage.getItem(PENDING_KEY); if (raw === null) return null;
        let value; try { value = JSON.parse(raw); } catch (_) { throw new Error('上次操作记录损坏，请联系维护人员核对。'); }
        check(validIntent(value), '本机存的上次操作记录不完整，已停止新的操作。请不要再操作，联系维护人员。'); return value;
      },
      begin(action) {
        check(Object.prototype.hasOwnProperty.call(actions, action), '未知维护动作。');
        check(!this.read(), '还有一次操作没有确认结果，不能重新发起。请先点「查询结果」。');
        const value = { request_key: T.requestKey('system'), action, summary: actions[action] };
        storage.setItem(PENDING_KEY, JSON.stringify(value));
        return value;
      },
      finish(intent) {
        const saved = this.read(); check(!saved || saved.request_key === intent.request_key, '上次操作记录已变化，没有删除其他记录。请刷新后重新确认。');
        if (saved) storage.removeItem(PENDING_KEY);
      }
    };
  }
  function inspectPending() {
    try { return { intent: pending().read(), storageError: null }; }
    catch (storageError) { return { intent: null, storageError }; }
  }
  function recordSelection(selection, kind) {
    if (selection === undefined || selection === null) return null;
    // 唯一写方 SystemMaintenanceRecords 只存 { key, record_kind }（日志只存 key）。
    check(object(selection) && Object.keys(selection).every(key => ['key', 'record_kind'].includes(key)) && nonempty(selection.key)
      && (kind === 'logs' || ['backup_file', 'restore_event', 'cleanup_event'].includes(selection.record_kind)), '原先选中的记录已失效，请重新选择。');
    check(kind !== 'logs' || selection.record_kind === undefined, '原先选中的日志记录编号不对，请重新选择。');
    return { key: selection.key, ...(kind === 'logs' ? {} : { record_kind: selection.record_kind }) };
  }
  function recordContext(value = {}, kind) {
    check(object(value) && Object.keys(value).every(key => ['filters', 'page', 'selection'].includes(key)), '上次的筛选和翻页状态无法恢复。请刷新后重新筛选。');
    const filters = { query: '', type: '', status: '', level: '', file: '', start: '', end: '', ...value.filters };
    check((value.filters === undefined || object(value.filters)) && Object.keys(filters).every(key => ['query', 'type', 'status', 'level', 'file', 'start', 'end'].includes(key)
      && text(filters[key]) && filters[key].length <= 200), '上次的筛选条件无法恢复。请刷新后重新筛选。');
    const page = value.page === undefined ? 1 : value.page;
    check(count(page) && page >= 1 && page <= 100000, '上次的页码无法恢复。请刷新后重新翻页。');
    return { filters, page, selection: recordSelection(value.selection, kind) };
  }
  function pageContext(value) {
    check(object(value) && Object.keys(value).every(key => ['tab', 'page_size', 'records'].includes(key)), '上次的页面状态无法恢复。请从侧栏重新打开系统管理。');
    const tab = value.tab === undefined ? 'overview' : value.tab;
    const size = value.page_size === undefined ? 10 : value.page_size;
    const records = value.records === undefined ? {} : value.records;
    check(['overview', 'backups', 'logs', 'config'].includes(tab) && [10, 25, 50].includes(size)
      && object(records) && Object.keys(records).every(key => ['backups', 'logs'].includes(key)), '上次的页面状态不完整，无法恢复。请从侧栏重新打开系统管理。');
    return { tab, page_size: size, records: Object.fromEntries(Object.entries(records).map(([kind, item]) => [kind, recordContext(item, kind)])) };
  }
  // 维护读取、提交和下载都按 30 秒等待。维护状态与回执查询是原始 JSON，交给 result / SystemRestoreStatus 校验。
  const TIMEOUT = 30000;
  async function host() {
    try { return window.SystemRestoreStatus.host(await T.lookup(BASE + '/restore-host', { timeout: TIMEOUT })); }
    catch (problem) {
      const message = problem.status === 404 ? '维护状态接口未注册（HTTP 404），请检查服务启动配置。'
        : '维护状态查询失败' + (problem.status ? '（HTTP ' + problem.status + '）' : '') + '：' + problem.message;
      const error = new Error(message); error.code = problem.code; error.status = problem.status; throw error;
    }
  }
  // input 是页面按当前筛选组装的查询对象（配置页传 {}），不会缺省。
  async function read(kind, input, signal) {
    check(['backups', 'logs', 'config'].includes(kind));
    const value = await T.read(BASE + '/' + kind, input, { signal, timeout: TIMEOUT });
    if (kind === 'config') config(value.data); else {
      collection(value, kind);
      check(value.data.page.number === (input.page === undefined ? 1 : input.page)
        && value.data.page.size === (input.page_size === undefined ? 10 : input.page_size)
        && (!input.snapshot_ref || value.meta.snapshot_ref === input.snapshot_ref), '读到的维护记录和刚才的筛选不一致，页面没有改动。请刷新后重试。');
    }
    return value;
  }
  async function command(intent, token, input) {
    check(validIntent(intent) && nonempty(token));
    const payload = await T.command(BASE + (intent.action === 'config' ? '/config/save' : '/backups/' + intent.action),
      { request_key: intent.request_key, write_token: token, input }, { timeout: TIMEOUT, expect: BASE + '/results/' + intent.request_key });
    return intent.action === 'config' ? receipt(payload) : result(payload, intent);
  }
  async function lookup(intent) {
    check(validIntent(intent));
    return result(await T.lookup(BASE + '/results/' + intent.request_key, { timeout: TIMEOUT }), intent);
  }
  async function lookupReference(reference, kind, signal) {
    const path = window.SystemRestoreStatus.referencePath(reference, kind);
    const value = await T.lookup(BASE + path, { signal, timeout: TIMEOUT }), op = value.data && value.data.operation;
    if (op && path.startsWith('/jobs/')) check(op.job_ref === reference, '返回的维护记录不是所查询的记录。');
    return result(value, { action: op && op.action, request_key: path.startsWith('/jobs/') ? op && op.request_key : reference });
  }
  // 文件名只认后端附件头给的名字，非空与后缀由 transport 校验；这里只核对本领域的内容与业务头。
  // format 只会是 csv / zip，input 带着已读日志的数据版本，都由 SystemMaintenanceRecords 传入。
  async function download(format, input) {
    const file = await T.download(BASE + '/logs/export/' + format, input, { timeout: TIMEOUT, types: [T.types[format]] });
    if (format === 'csv') check((await file.blob.slice(0, 8192).text()).startsWith('来源,时间,'), '下载内容与日志文件格式不符。');
    T.saveBlob(file.filename, file.blob);
    return { filename: file.filename, bytes: file.blob.size };
  }
  // row 是已校验清单里的备份文件行，input 带着这次清单的数据版本，都由 SystemMaintenanceRecords 传入。
  async function downloadBackup(row, input) {
    const file = await T.download(BASE + '/backups/' + encodeURIComponent(row.backup_ref) + '/download', input, { timeout: TIMEOUT, types: [T.types.sqlite] });
    check(file.blob.size === row.size_bytes && Number(file.header('Content-Length')) === file.blob.size, '备份下载状态、类型或大小与原清单不一致。');
    check(file.header('X-APS-Backup-Ref') === row.backup_ref, '下载到的不是刚才选中的备份文件，没有保存。');
    T.saveBlob(file.filename, file.blob);
    return { filename: file.filename, bytes: file.blob.size };
  }
  window.SystemMaintenanceAPI = { host, read, command, lookup, lookupReference, download, downloadBackup,
    pending, inspectPending, PENDING_KEY, fields, actions, collection, blocked, normalize, recordContext, pageContext };
})();
