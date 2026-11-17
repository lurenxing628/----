import T from './shared/network/transport.js';
import { pendingStore, storageSlot } from './shared/session/pending-store.js';
import SystemRestoreStatus from './SystemRestoreStatus.js';
import { object, text, nonempty, failure, checker } from './shared/contract/kit.js';

const BASE = '/api/workbench/v1/system', PENDING_KEY = 'aps_workbench_system_pending_v1', EVENT = 'aps-workbench-system-pending-changed';
const actions = { create: '新增备份', delete: '删除所选备份', restore: '恢复所选备份', config: '保存八项维护配置' };
const terminalStates = ['succeeded', 'failed', 'rolled_back'];
const fields = [
  ['auto_backup_enabled', '自动备份', 'backup'], ['auto_backup_interval_minutes', '备份检查间隔', 'backup'],
  ['auto_backup_cleanup_enabled', '清理过期备份', 'backup'], ['auto_backup_keep_days', '备份保留时间', 'backup'],
  ['auto_backup_cleanup_interval_minutes', '备份清理检查间隔', 'backup'], ['auto_log_cleanup_enabled', '清理操作日志', 'logs'],
  ['auto_log_cleanup_keep_days', '操作日志保留时间', 'logs'], ['auto_log_cleanup_interval_minutes', '日志清理检查间隔', 'logs']
].map(([key, label, group]) => ({ key, label, group, switch: key.endsWith('_enabled'), unit: key.endsWith('_days') ? '天' : '分钟' }));
const count = value => Number.isSafeInteger(value) && value >= 0;
const INVALID = '读到的维护数据不完整，页面没有改动。请刷新后重试。';
// 维护命令回执与结果查询都在命令发出之后：核对不过时结果未知，本机待确认记录不能清。
const check = checker(INVALID), checkResult = checker(INVALID, { committed: 'unknown' });
function collection(value, kind) {
  const data = value.data;
  check(nonempty(value.meta.snapshot_ref)
    && data.scope === (kind === 'backups' ? 'backup-files-and-maintenance-events' : 'bounded-log-windows'));
  return value;
}
function receipt(value) {
  checkResult(object(value) && value.ok === true && ['committed', 'unchanged'].includes(value.result) && nonempty(value.receipt_ref));
  return { kind: 'config', command: value, terminal: true };
}
function result(value, intent) {
  // 回执查询拿到的是原始 JSON：维护期间由维护日志服务器作答，平时是标准信封。
  const external = object(value) && object(value.meta) && value.meta.result_source === 'external_maintenance_journal';
  if (!external) T.envelope(value, T.modes.lookup);
  const data = external ? SystemRestoreStatus.envelope(value) : value.data;
  if (data.kind === 'not_recorded') { checkResult(text(data.message)); return { ...data, terminal: false }; }
  if (data.kind === 'config') { checkResult(intent.action === 'config'); return receipt(data.command); }
  const op = data.operation;
  checkResult(data.kind === 'file_operation' && intent.action !== 'config' && object(op)
    && op.request_key === intent.request_key && op.action === intent.action);
  return { ...data, terminal: terminalStates.includes(op.state) };
}
function blocked(data, action) {
  if (!data) return '还没有读到本机可以做哪些文件操作。';
  const caps = data.capabilities;
  return caps[action] === true ? '' : (action === 'restore' ? caps.restore_reason || caps.blocked_reason : caps.blocked_reason);
}
// 只把间隔与保留天数转成整数；取值范围由后端校验，422 带字段路径。开关由勾选框直接给出 yes/no。
function normalize(draft) {
  const values = {}, errors = {};
  fields.forEach(field => {
    const raw = draft[field.key];
    if (field.switch) values[field.key] = raw;
    else {
      if (!/^-?\d+$/.test(String(raw)) || !Number.isSafeInteger(Number(raw))) errors[field.key] = '请输入整数。';
      values[field.key] = Number(raw);
    }
  });
  return { values, errors, valid: !Object.keys(errors).length };
}
function validIntent(value) {
  return object(value) && Object.keys(value).length === 3 && /^system-[a-f0-9]{48}$/.test(value.request_key)
    && Object.prototype.hasOwnProperty.call(actions, value.action) && value.summary === actions[value.action];
}
const CONFLICT_MESSAGE = '上次操作记录已变化，没有删除其他记录。请刷新后重新确认。';
const emptySession = () => ({
  intent: null, startedHere: false, result: null, error: null,
  storageError: null, selection: null, dismissPending: false
});
const sessionSlot = storageSlot(() => window.localStorage, 'system', PENDING_KEY, emptySession, (slot, prev) => {
  if (prev.intent || prev.result || prev.storageError) Object.assign(slot, prev);
});
const store = pendingStore({
  key: PENDING_KEY, event: EVENT, validate: validIntent,
  corruptError: '上次操作记录损坏，请联系维护人员核对。',
  invalidError: '本机存的上次操作记录不完整，已停止新的操作。请不要再操作，联系维护人员。',
  conflictError: CONFLICT_MESSAGE,
  writeError: '本机没能更新上次维护操作记录。请不要再操作，联系维护人员。'
});
const maintenancePending = {
  subscribe: store.subscribe,
  session() { return { ...sessionSlot() }; },
  read() {
    const disk = store.read(), current = sessionSlot();
    current.storageError = null;
    current.dismissPending = false;
    if (!disk) {
      if (current.intent && !(current.result && current.result.kind === 'rejected')) Object.assign(current, emptySession());
      else if (current.intent) current.intent = null;
      return null;
    }
    if (!current.intent || current.intent.request_key !== disk.request_key) {
      Object.assign(current, emptySession(), { intent: disk });
    }
    return disk;
  },
  flush() {
    const current = sessionSlot();
    let disk;
    try {
      disk = store.flush();
    } catch (error) {
      current.storageError = error;
      throw error;
    }
    current.storageError = null;
    const dismiss = current.dismissPending;
    current.dismissPending = false;
    if (!disk) {
      if (!dismiss && current.result && current.result.kind === 'rejected') {
        current.intent = null;
      } else {
        Object.assign(current, emptySession());
      }
      return null;
    }
    if (!current.intent || current.intent.request_key !== disk.request_key) {
      Object.assign(current, emptySession(), { intent: disk });
    }
    return disk;
  },
  begin(action, selection = null) {
    const current = sessionSlot();
    check(!(current.intent && current.storageError), '还有一次操作没有确认结果，不能重新发起。请先点「查询结果」。');
    let created;
    try {
      created = store.save({ request_key: T.requestKey('system'), action, summary: actions[action] }, null);
    } catch (error) {
      if (error.conflict === true) throw failure('还有一次操作没有确认结果，不能重新发起。请先点「查询结果」。');
      throw error;
    }
    Object.assign(current, emptySession(), { intent: created, startedHere: action === 'restore', selection });
    return created;
  },
  settle(intent, value, error = null) {
    const current = sessionSlot();
    const sameKey = Boolean(current.intent && current.intent.request_key === intent.request_key);
    if (current.intent) {
      if (!sameKey) return null;
    } else {
      let disk = null;
      try { disk = store.read(); } catch (_) { return null; }
      if (!disk || disk.request_key !== intent.request_key) return null;
    }
    const terminal = Boolean(value && value.terminal);
    if (sameKey && current.result && current.result.terminal && !terminal) return null;
    Object.assign(current, {
      intent,
      startedHere: sameKey ? current.startedHere : false,
      result: terminal ? value : null,
      error: terminal ? error : (error || (sameKey ? current.error : null)),
      storageError: sameKey ? current.storageError : null,
      selection: sameKey ? current.selection : null,
      dismissPending: sameKey ? current.dismissPending : false
    });
    return current;
  },
  finish(intent, dismiss = false) {
    const current = sessionSlot();
    try {
      store.save(null, intent);
    } catch (error) {
      if (current.intent && current.intent.request_key === intent.request_key) {
        if (error.conflict === true) Object.assign(current, emptySession());
        else { current.storageError = error; current.dismissPending = Boolean(dismiss); }
      }
      throw error;
    }
    if (current.intent && current.intent.request_key === intent.request_key) {
      if (!dismiss && current.result && current.result.kind === 'rejected') {
        current.intent = null; current.storageError = null; current.dismissPending = false;
      } else {
        Object.assign(current, emptySession());
      }
    }
  }
};
function inspectPending() {
  try {
    const intent = maintenancePending.read(), current = sessionSlot();
    return {
      intent,
      result: current.result,
      error: current.error,
      startedHere: current.startedHere,
      selection: current.selection,
      storageError: current.storageError,
      dismissPending: current.dismissPending
    };
  } catch (storageError) {
    const current = sessionSlot();
    return {
      intent: current.intent,
      result: current.result,
      error: current.error,
      startedHere: current.startedHere,
      selection: current.selection,
      storageError,
      dismissPending: current.dismissPending
    };
  }
}
function recordSelection(selection, kind) {
  if (selection === undefined || selection === null) return null;
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
// 键集已由 WorkbenchNavigation.admit 按受控导航声明准入；这里核对取值。
function pageContext(value) {
  const tab = value.tab === undefined ? 'overview' : value.tab;
  const size = value.page_size === undefined ? 10 : value.page_size;
  const records = value.records === undefined ? {} : value.records;
  check(['overview', 'backups', 'logs', 'config'].includes(tab) && [10, 25, 50].includes(size)
    && object(records) && Object.keys(records).every(key => ['backups', 'logs'].includes(key)), '上次的页面状态不完整，无法恢复。请从侧栏重新打开系统管理。');
  return { tab, page_size: size, records: Object.fromEntries(Object.entries(records).map(([kind, item]) => [kind, recordContext(item, kind)])) };
}
const TIMEOUT = 30000;
async function host() {
  try { return SystemRestoreStatus.host(await T.lookup(BASE + '/restore-host', {}, { timeout: TIMEOUT })); }
  catch (problem) {
    // 只给 404 换成能照着处理的中文说明，状态码留在错误对象里；其余错误原样交给错误框判定能否上屏。
    if (problem.status === 404) throw failure('维护状态接口未注册，请检查服务启动配置。', { code: problem.code, status: problem.status, committed: problem.committed });
    throw problem;
  }
}
async function read(kind, input, signal) {
  check(['backups', 'logs', 'config'].includes(kind));
  const value = await T.read(BASE + '/' + kind, input, { signal, timeout: TIMEOUT });
  if (kind !== 'config') {
    collection(value, kind);
    check(value.data.page.number === (input.page === undefined ? 1 : input.page)
      && value.data.page.size === (input.page_size === undefined ? 10 : input.page_size)
      && (!input.snapshot_ref || value.meta.snapshot_ref === input.snapshot_ref), '读到的维护记录和刚才的筛选不一致，页面没有改动。请刷新后重试。');
  }
  return value;
}
async function command(intent, token, input) {
  const payload = await T.command(BASE + (intent.action === 'config' ? '/config/save' : '/backups/' + intent.action),
    { request_key: intent.request_key, write_token: token, input }, { timeout: TIMEOUT, expect: BASE + '/results/' + intent.request_key });
  return intent.action === 'config' ? receipt(payload) : result(payload, intent);
}
async function lookup(intent) {
  return result(await T.lookup(BASE + '/results/' + intent.request_key, {}, { timeout: TIMEOUT }), intent);
}
async function lookupReference(reference, kind, signal) {
  const path = SystemRestoreStatus.referencePath(reference, kind);
  const value = await T.lookup(BASE + path, {}, { signal, timeout: TIMEOUT }), op = value.data && value.data.operation;
  if (op && path.startsWith('/jobs/')) checkResult(op.job_ref === reference, '返回的维护记录不是所查询的记录。');
  return result(value, { action: op && op.action, request_key: path.startsWith('/jobs/') ? op && op.request_key : reference });
}
async function download(format, input) {
  const file = await T.download(BASE + '/logs/export/' + format, input, { timeout: TIMEOUT, types: [T.types[format]] });
  if (format === 'csv') check((await file.blob.slice(0, 8192).text()).startsWith('来源,时间,'), '下载内容与日志文件格式不符。');
  T.saveBlob(file.filename, file.blob);
  return { filename: file.filename, bytes: file.blob.size };
}
async function downloadBackup(row, input) {
  const file = await T.download(BASE + '/backups/' + encodeURIComponent(row.backup_ref) + '/download', input, { timeout: TIMEOUT, types: [T.types.sqlite] });
  check(file.blob.size === row.size_bytes && Number(file.header('Content-Length')) === file.blob.size, '备份下载状态、类型或大小与原清单不一致。');
  check(file.header('X-APS-Backup-Ref') === row.backup_ref, '下载到的不是刚才选中的备份文件，没有保存。');
  T.saveBlob(file.filename, file.blob);
  return { filename: file.filename, bytes: file.blob.size };
}
const SystemMaintenanceAPI = {
  host,
  read,
  command,
  lookup,
  lookupReference,
  download,
  downloadBackup,
  pending: maintenancePending,
  inspectPending,
  PENDING_KEY,
  EVENT,
  fields,
  actions,
  collection,
  blocked,
  normalize,
  recordContext,
  pageContext
};

export {
  SystemMaintenanceAPI,
  host,
  read,
  command,
  lookup,
  lookupReference,
  download,
  downloadBackup,
  maintenancePending as pending,
  inspectPending,
  PENDING_KEY,
  EVENT,
  fields,
  actions,
  collection,
  blocked,
  normalize,
  recordContext,
  pageContext
};
export default SystemMaintenanceAPI;
