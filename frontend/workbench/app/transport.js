(function () {
  'use strict';
  // 工作台唯一的传输通道：地址守卫、取消与超时、信封校验、统一错误对象、命令确定/不确定判定、下载与存盘、request_key。
  // 统一错误对象：{ message, code, fields, conflicts, committed, status, requestRef, requestKey, resultTarget }。
  const PREFIX = '/api/workbench/v1/';
  const REJECTED_STATUS = [400, 404, 409, 422, 503];
  // 工作台下载只有这四种文件；领域写 types: [T.types.csv] 这种形式。
  const types = Object.freeze({ csv: 'text/csv', xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    zip: 'application/zip', sqlite: 'application/vnd.sqlite3' });
  const ZIP = [0x50, 0x4b, 0x03, 0x04];
  // 后端导出的 CSV 一律带 UTF-8 BOM；XLSX 与 ZIP 都是 ZIP 容器；备份文件是 SQLite 库。
  const MAGIC = { [types.csv]: [0xef, 0xbb, 0xbf], [types.xlsx]: ZIP, [types.zip]: ZIP,
    [types.sqlite]: Array.from('SQLite format 3\0', character => character.charCodeAt(0)) };
  // 后端附件文件名的唯一后缀：导出都按格式拼 .csv / .xlsx，诊断包是 .zip，备份文件恒为 aps_backup_*.db。
  const EXTENSION = { [types.csv]: '.csv', [types.xlsx]: '.xlsx', [types.zip]: '.zip', [types.sqlite]: '.db' };
  const ENVELOPE_KEYS = 'data,meta,ok,schema_version,warnings', META_KEYS = 'as_of,request_ref,snapshot_ref,source,time_basis';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const text = value => typeof value === 'string';
  const essence = value => (value || '').split(';')[0].trim().toLowerCase();
  const faults = new WeakSet();
  function fault(message, details) {
    const error = Object.assign(new Error(message), { code: null, fields: [], conflicts: [], committed: false, status: null,
      requestRef: null, requestKey: null, resultTarget: null }, details);
    faults.add(error);
    return error;
  }
  const unknown = () => window.WorkbenchTerms.outcomes.pending('操作');
  const readCopy = { timeout: () => '读取超时，请稍后重试。', network: () => '无法连接本机服务，请确认应用仍在运行后重试。',
    format: () => '本机服务返回了非预期的数据格式。', parse: () => '本机服务返回的数据无法解析。', failed: () => '本机服务未能完成读取，请重试。' };
  // read：读取失败与写入无关；lookup：查回执失败时上次命令仍是“结果未知”；write：发出后没有服务端明确答复，一律按结果未知。
  const modes = {
    read: { committed: false, ...readCopy },
    lookup: { committed: 'unknown', ...readCopy },
    write: { committed: 'unknown', timeout: unknown, network: unknown, format: unknown, parse: unknown, failed: unknown }
  };
  function url(path, query = {}) {
    // 只接受以 /api/workbench/v1/ 开头的绝对路径；规范化后（如带 ..）仍须留在前缀内。
    const target = new URL(path, location.origin);
    if (!path.startsWith(PREFIX) || !target.pathname.startsWith(PREFIX)) throw fault('数据地址不属于本机工作台。');
    Object.keys(query).forEach(key => {
      if (query[key] !== undefined && query[key] !== null && query[key] !== '') target.searchParams.set(key, String(query[key]));
    });
    return target.href;
  }
  // 工厂本地秒级时间，按真实日历校验（与 PlanContract 的 localTime 同一口径，不带小数秒）。
  function localSecond(value) {
    if (!text(value) || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(value)) return false;
    const [year, month, day, hour, minute, second] = value.split(/[-T:]/).map(Number);
    const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
    const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    return year >= 1 && month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1] && hour < 24 && minute < 60 && second < 60;
  }
  // 成功信封唯一的校验点：唯一生产者是 web/api_responses.py 的 query_payload，顶层 5 个键、meta 5 个键都固定。
  function envelope(payload) {
    const meta = object(payload) && payload.meta;
    if (!object(payload) || Object.keys(payload).sort().join() !== ENVELOPE_KEYS || payload.ok !== true || payload.schema_version !== 1
        || !object(payload.data) || !object(meta) || Object.keys(meta).sort().join() !== META_KEYS
        || meta.source !== 'production' || meta.time_basis !== 'factory_local' || !text(meta.request_ref) || !/^[0-9a-f]{32}$/.test(meta.request_ref)
        || !(meta.snapshot_ref === null || text(meta.snapshot_ref) && /^[A-Za-z0-9_-]{32}$/.test(meta.snapshot_ref)) || !localSecond(meta.as_of)
        || !Array.isArray(payload.warnings) || !payload.warnings.every(item => object(item) && text(item.code) && text(item.message)))
      throw fault('读到的数据不完整，页面没有改动。请刷新后重试。', { code: 'invalid_response' });
    return payload;
  }
  const ERROR_KEYS = ['code', 'message', 'fields', 'retryable', 'request_ref', 'conflicts', 'row_number', 'request_key', 'result_target'];
  function failed(payload) {
    const e = object(payload) && payload.ok === false && payload.error;
    return object(e) && Object.keys(payload).every(key => ['ok', 'committed', 'error', 'status'].includes(key))
      && [false, true, 'unknown'].includes(payload.committed)
      && (payload.status === undefined || Number.isInteger(payload.status) && payload.status >= 400 && payload.status <= 599)
      && Object.keys(e).every(key => ERROR_KEYS.includes(key))
      && text(e.code) && e.code.length > 0 && text(e.message) && typeof e.retryable === 'boolean'
      && text(e.request_ref) && /^[0-9a-f]{32}$/.test(e.request_ref)
      && Array.isArray(e.fields) && e.fields.every(row => object(row) && Object.keys(row).length === 2 && text(row.path) && text(row.message))
      && (e.conflicts === undefined || Array.isArray(e.conflicts))
      && (e.row_number === undefined || Number.isSafeInteger(e.row_number))
      && (e.request_key === undefined || text(e.request_key)) && (e.result_target === undefined || text(e.result_target));
  }
  // 失败信封唯一的解析点：web/api_responses.py 的 failure_payload、pages.py 的统一兜底与 run_decision.py 的内嵌资源失败。
  function failure(payload, status) {
    if (!failed(payload) || !Number.isInteger(status) || status < 400 || status > 599 || payload.status !== undefined && payload.status !== status)
      return fault(modes.read.failed(), { code: 'invalid_response', status });
    const e = payload.error;
    return fault(e.message, { code: e.code, fields: e.fields, conflicts: e.conflicts || [], committed: payload.committed, status,
      requestRef: e.request_ref, requestKey: e.request_key || null, resultTarget: e.result_target || null });
  }
  function encode(body) {
    if (body instanceof FormData) return { body, headers: { Accept: 'application/json' } };
    try { return { body: JSON.stringify(body), headers: { Accept: 'application/json', 'Content-Type': 'application/json' } }; }
    catch (_) { throw fault('保存内容无法转换，本次没有提交。'); }
  }
  async function send(target, init, { signal, timeout = 20000 }, mode, consume) {
    const controller = new AbortController(), abort = () => controller.abort();
    let timedOut = false;
    if (signal) { if (signal.aborted) abort(); else signal.addEventListener('abort', abort, { once: true }); }
    const timer = setTimeout(() => { timedOut = true; abort(); }, timeout);
    try {
      const response = await fetch(target, { ...init, signal: controller.signal, credentials: 'same-origin', redirect: 'error', cache: 'no-store' });
      return await consume(response);
    } catch (error) {
      if (timedOut) throw fault(mode.timeout(), { code: 'timeout', committed: mode.committed });
      if (error.name === 'AbortError' || faults.has(error)) throw error;
      throw fault(mode.network(), { committed: mode.committed });
    } finally {
      clearTimeout(timer);
      if (signal) signal.removeEventListener('abort', abort);
    }
  }
  async function parse(response, mode) {
    if (essence(response.headers.get('content-type')) !== 'application/json')
      throw fault(mode.format(), { code: 'invalid_response', committed: mode.committed, status: response.status });
    try { return await response.json(); }
    catch (error) {
      if (error.name === 'AbortError') throw error;
      throw fault(mode.parse(), { code: 'invalid_response', committed: mode.committed, status: response.status });
    }
  }
  async function answer(response) {
    const payload = await parse(response, modes.read);
    if (failed(payload)) {
      if (response.status === 499 && payload.error.code === 'request_superseded') throw new DOMException('筛选条件已更新，前一次读取已取消。', 'AbortError');
      throw failure(payload, response.status);
    }
    if (!response.ok) throw fault(modes.read.failed(), { code: 'invalid_response', status: response.status });
    return envelope(payload);
  }
  async function read(path, query, { signal, timeout, lane } = {}) {
    const headers = lane ? { Accept: 'application/json', 'X-Workbench-Read-Lane': lane } : { Accept: 'application/json' };
    return send(url(path, query), { method: 'GET', headers }, { signal, timeout }, modes.read, answer);
  }
  async function preview(path, body, { signal, timeout } = {}) {
    return send(url(path), { method: 'POST', ...encode(body) }, { signal, timeout }, modes.read, answer);
  }
  // expect 是领域给出的回执地址；失败信封回显的 request_key / result_target 与本次提交对不上时不跟随，按结果未知处理。
  async function command(path, body, { timeout, expect } = {}) {
    return send(url(path), { method: 'POST', ...encode(body) }, { timeout }, modes.write, async response => {
      const payload = await parse(response, modes.write);
      if (failed(payload)) {
        const error = failure(payload, response.status);
        if ((error.requestKey !== null || error.resultTarget !== null) && (error.requestKey !== body.request_key || error.resultTarget !== expect))
          throw fault('返回的结果编号和上次提交对不上，这里没有读取其他结果。请点「查询结果」。',
            { code: 'invalid_response', committed: 'unknown', status: response.status, requestRef: error.requestRef });
        throw error;
      }
      if (!response.ok || !object(payload) || payload.ok !== true)
        throw fault(unknown(), { code: 'invalid_response', committed: 'unknown', status: response.status });
      return payload;
    });
  }
  // 回执查询返回原始 JSON，由领域校验；404 receipt_not_found 表示“没查到”，返回 null。
  async function lookup(path, { signal, timeout } = {}) {
    return send(url(path), { method: 'GET', headers: { Accept: 'application/json' } }, { signal, timeout }, modes.lookup, async response => {
      const payload = await parse(response, modes.lookup);
      if (failed(payload)) {
        if (response.status === 404 && payload.error.code === 'receipt_not_found') return null;
        throw Object.assign(failure(payload, response.status), { committed: 'unknown' });
      }
      if (!response.ok || !object(payload)) throw fault(modes.lookup.failed(), { code: 'invalid_response', committed: 'unknown', status: response.status });
      return payload;
    });
  }
  // 下载必须是带文件名的附件，文件名后缀要与实际文件类型一致；文件名只认后端附件头这一个来源。
  function filename(disposition, type, status) {
    const value = disposition || '';
    if (!/^attachment(?:;|$)/i.test(value)) throw fault('下载内容不是附件，没有保存文件。', { code: 'invalid_response', status });
    const extended = /(?:^|;)\s*filename\*\s*=\s*UTF-8''([^;]+)/i.exec(value);
    const plain = /(?:^|;)\s*filename\s*=\s*(?:"((?:[^"\\]|\\.)*)"|([^;]+))/i.exec(value);
    let name;
    try { name = extended ? decodeURIComponent(extended[1].trim()) : plain ? (plain[1] !== undefined ? plain[1].replace(/\\(.)/g, '$1') : plain[2].trim()) : ''; }
    catch (_) { throw fault('下载文件名编码无效，没有保存文件。', { code: 'invalid_response', status }); }
    if (!name) throw fault('下载内容缺少文件名，没有保存文件。', { code: 'invalid_response', status });
    if (/[\x00-\x1f\x7f/\\]/.test(name)) throw fault('下载文件名无效，没有保存文件。', { code: 'invalid_response', status });
    if (!name.toLowerCase().endsWith(EXTENSION[type])) throw fault('下载文件名后缀与文件类型不一致，没有保存文件。', { code: 'invalid_response', status });
    return name;
  }
  // types 是调用方允许的 MIME 列表；X-Workbench-* 等业务头由领域经 header(name) 核对。
  async function download(path, query, { signal, timeout, types }) {
    const init = { method: 'GET', headers: { Accept: types.concat('application/json').join(',') } };
    return send(url(path, query), init, { signal, timeout }, modes.read, async response => {
      const type = essence(response.headers.get('content-type'));
      if (type === 'application/json') {
        const payload = await parse(response, modes.read);
        if (failed(payload)) throw failure(payload, response.status);
        throw fault('下载内容格式不正确，没有保存成文件。', { code: 'invalid_response', status: response.status });
      }
      if (!response.ok) throw fault(modes.read.failed(), { code: 'invalid_response', status: response.status });
      if (!types.includes(type)) throw fault('下载内容格式不正确，没有保存成文件。', { code: 'invalid_response', status: response.status });
      const name = filename(response.headers.get('content-disposition'), type, response.status), blob = await response.blob();
      if (!blob.size) throw fault('下载文件是空的，没有当成导出成功。', { code: 'invalid_response', status: response.status });
      const head = new Uint8Array(await blob.slice(0, MAGIC[type].length).arrayBuffer());
      if (!MAGIC[type].every((byte, index) => head[index] === byte))
        throw fault('下载内容与文件类型不符，没有保存成文件。', { code: 'invalid_response', status: response.status });
      return { blob, contentType: type, filename: name, header: key => response.headers.get(key) };
    });
  }
  function saveBlob(name, blob) {
    const link = document.createElement('a'), href = URL.createObjectURL(blob);
    link.href = href; link.download = name;
    try { document.body.appendChild(link); link.click(); }
    finally { link.remove(); setTimeout(() => URL.revokeObjectURL(href), 1000); }
  }
  function downloadJSON(name, value) {
    saveBlob(name, new Blob([JSON.stringify(value, null, 2)], { type: 'application/json;charset=utf-8' }));
  }
  // 后端 request_key 规则是 [A-Za-z0-9_-]{16,128}；工作台统一写成“前缀-48 位小写十六进制”。
  function requestKey(prefix) {
    const bytes = new Uint8Array(24); window.crypto.getRandomValues(bytes);
    return prefix + '-' + Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');
  }
  // 唯一的“确定没有生效”判定：服务端在这些状态码里明确 committed:false，或请求在本地校验阶段就失败、从未发出（status 为 null）。
  // 查回执失败一律是 committed:'unknown'，不会落进这里。
  const rejected = error => error.committed === false
    && (REJECTED_STATUS.includes(error.status) && error.code !== 'request_key_conflict' || error.status === null);
  const uncertain = error => error.committed === 'unknown';
  function canonical(value) {
    return JSON.stringify(value, (_, item) => object(item) ? Object.keys(item).sort().reduce((out, key) => { out[key] = item[key]; return out; }, {}) : item);
  }
  const equal = (a, b) => canonical(a) === canonical(b);
  function raise(spec, fallback, extra) {
    const err = !spec ? fallback : typeof spec === 'function' ? spec() : new Error(spec);
    if (extra) Object.assign(err, extra);
    throw err;
  }
  const unflushedByKey = new Map();
  // 待确认意图的本机存储：统一读、校验、CAS 写、清除与同页事件通知，错误文案由各领域指定。
  function pendingStore({ key, storage = () => window.localStorage, event, raw = false, validate, validateWrite = validate,
      encode = value => value, same = equal, readError, corruptError = readError, invalidError = corruptError,
      conflictError, invalidWriteError = invalidError, writeError, removeError = writeError }) {
    function currentPending(target) {
      const pending = unflushedByKey.get(key);
      if (!pending) return null;
      if (target && pending.target && pending.target !== target) {
        unflushedByKey.delete(key);
        return null;
      }
      if (target && !pending.target) pending.target = target;
      return pending;
    }
    function readDisk(target, pending) {
      let text;
      try { text = target.getItem(key); } catch (error) { raise(readError, error, pending ? { saved: pending.value } : undefined); }
      if (text === null) return null;
      let value = text;
      if (!raw) {
        try { value = JSON.parse(text); } catch (error) { raise(corruptError, error); }
      }
      if (validate && !validate(value)) raise(invalidError);
      return value;
    }
    function effectiveRead() {
      let target = null;
      try { target = storage(); } catch (error) {
        const pending = currentPending(null);
        raise(readError, error, pending ? { saved: pending.value } : undefined);
      }
      const pending = currentPending(target), disk = readDisk(target, pending);
      if (!pending) return { target, disk, current: disk, pending: null };
      if (!same(disk, pending.disk)) {
        unflushedByKey.delete(key);
        return { target, disk, current: disk, pending: null };
      }
      return { target, disk, current: pending.value, pending };
    }
    function read() {
      const { target, current, pending } = effectiveRead();
      if (pending) {
        try {
          if (current === null) target.removeItem(key);
          else target.setItem(key, raw ? current : JSON.stringify(encode(current)));
          unflushedByKey.delete(key);
        } catch (error) { raise(current === null ? removeError : writeError, error, { saved: current }); }
      }
      return current;
    }
    function write(value, fallbackDisk) {
      if (value !== null && validateWrite && !validateWrite(value)) raise(invalidWriteError);
      let target = null;
      try {
        target = storage();
        if (value === null) target.removeItem(key);
        else target.setItem(key, raw ? value : JSON.stringify(encode(value)));
        unflushedByKey.delete(key);
      } catch (error) {
        if (fallbackDisk !== undefined) {
          unflushedByKey.set(key, { target: target && typeof target === 'object' ? target : null, disk: fallbackDisk, value });
          if (event) window.dispatchEvent(new CustomEvent(event, { detail: value }));
        }
        raise(value === null ? removeError : writeError, error, fallbackDisk !== undefined ? { saved: value } : undefined);
      }
      if (event) window.dispatchEvent(new CustomEvent(event, { detail: value }));
      return value;
    }
    function save(value, previous) {
      const settling = previous !== null && (previous.phase === 'pending' || previous.run_ref === null) && (value === null || value.phase !== 'pending');
      let disk, current;
      try { ({ disk, current } = effectiveRead()); }
      catch (error) {
        if (settling && (value === null || !validateWrite || validateWrite(value))) {
          let target = null;
          try { target = storage(); } catch (_) {}
          unflushedByKey.set(key, { target: target && typeof target === 'object' ? target : null, disk: previous, value });
          if (event) window.dispatchEvent(new CustomEvent(event, { detail: value }));
          if (error && typeof error === 'object') error.saved = value;
        }
        throw error;
      }
      if (!same(current, previous)) raise(conflictError);
      return write(value, settling ? disk : undefined);
    }
    return { read, write, save };
  }
  window.APSWorkbenchTransport = { types, url, read, preview, command, lookup, download, saveBlob, downloadJSON, requestKey, rejected, uncertain, envelope, failure, canonical, equal, pendingStore };
})();
