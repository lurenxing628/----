(function () {
  'use strict';
  const C = window.TrialContract, ROOT = '/api/workbench/v1', BASE = ROOT + '/trial';
  const PENDING_KEY = 'aps_workbench_trial_pending_v1';
  const validKey = v => typeof v === 'string' && /^trial-[a-f0-9]{48}$/.test(v);
  function pending() {
    let value; try { value = localStorage.getItem(PENDING_KEY); }
    catch (_) { throw new Error('无法读取试调请求恢复记录，写入已暂停。'); }
    C.check(value === null || validKey(value), '试调请求恢复记录损坏，未删除或覆盖原记录。'); return value;
  }
  function reserve() {
    C.check(pending() === null, '存在尚未核实的试调请求，请先查询原请求。');
    const bytes = new Uint8Array(24); crypto.getRandomValues(bytes);
    const key = 'trial-' + Array.from(bytes, n => n.toString(16).padStart(2, '0')).join('');
    try { localStorage.setItem(PENDING_KEY, key); } catch (_) { throw new Error('无法保存试调请求恢复记录，本次未发送。'); }
    C.check(pending() === key, '试调请求恢复记录写入失败，本次未发送。'); return key;
  }
  function clear(key) {
    C.check(pending() === key, '试调恢复记录已变化，未清理其他请求。');
    try { localStorage.removeItem(PENDING_KEY); } catch (_) { throw new Error('原请求已核实，但恢复记录无法清理，请重新查询。'); }
  }
  async function request(path, options = {}) {
    C.check(path.startsWith(ROOT + '/'));
    const controller = new AbortController(), abort = () => controller.abort(), signal = options.signal;
    if (signal) { if (signal.aborted) abort(); else signal.addEventListener('abort', abort, { once: true }); }
    const timer = setTimeout(abort, 60000);
    try {
      const response = await fetch(path, { method: options.body === undefined ? 'GET' : 'POST', signal: controller.signal,
        credentials: 'same-origin', cache: 'no-store', redirect: 'error', headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }) });
      C.check((response.headers.get('Content-Type') || '').split(';')[0] === 'application/json', '服务响应不是有效试调数据。');
      const value = await response.json();
      if (!response.ok || value.ok !== true) {
        const error = new Error(value.error && value.error.message || '本机服务未能完成试调请求。');
        error.code = value.error && value.error.code; error.fields = value.error && value.error.fields;
        error.rejected = response.status >= 400 && response.status < 500 && value.ok === false && value.committed === false;
        throw error;
      }
      return value;
    } catch (error) {
      if (controller.signal.aborted && !(signal && signal.aborted)) throw new Error('试调请求超时；写入结果须查询原请求核实。');
      throw error;
    } finally { clearTimeout(timer); if (signal) signal.removeEventListener('abort', abort); }
  }
  async function read(path, q = {}, signal) {
    const value = await request(ROOT + path + (Object.keys(q).length ? '?' + new URLSearchParams(q) : ''), { signal });
    C.envelope(value, q); return value;
  }
  async function preview(input, signal) {
    C.base(input.base); C.scope(input.scope || {});
    const v = await request(BASE + '/drafts/preview', { body: input, signal }), d = C.envelope(v);
    C.check(JSON.stringify(d.base) === JSON.stringify(input.base) && d.tasks_complete === true && C.count(d.task_count)
      && d.write_context && d.write_context.capabilities['trial.create'] === true && typeof d.write_context.write_token === 'string');
    C.validation(d.validation); return v;
  }
  async function command(intent, token, key) {
    C.check(validKey(key) && typeof token === 'string');
    const suffix = intent.action === 'create' ? '/drafts' : '/drafts/' + intent.draft_ref + '/' + intent.action;
    return C.receipt(await request(BASE + suffix, { body: { request_key: key, write_token: token, input: intent.input } }), intent);
  }
  async function lookup(key) {
    C.check(validKey(key)); const v = await read('/trial/commands/' + key), d = v.data;
    C.check(['committed', 'not_observed'].includes(d.state) && d.can_retry_automatically === false);
    if (d.state === 'committed') C.receipt(d.receipt); else C.check(d.receipt === null);
    return d;
  }
  window.TrialAPI = { read, preview, command, lookup, pending, reserve, clear, PENDING_KEY };
})();
