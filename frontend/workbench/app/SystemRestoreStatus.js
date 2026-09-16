(function () {
  'use strict';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const source = 'external_maintenance_journal';
  const labels = { accepted: '已接收', checking: '检查中', protecting: '生成保护副本', restoring: '恢复中', verifying: '完整性检查中',
    rolling_back: '还原中', succeeded: '已完成', failed: '操作失败', rolled_back: '恢复失败，已还原',
    rollback_failed: '还原失败，需人工核对', recovery_required: '结果不确定，需人工核对' };
  const origins = { selected_backup: '来自所选备份', protection_backup: '已还原到恢复前的保护副本', unchanged: '原数据库未被替换', unconfirmed: '未知，不能确认当前数据库内容' };
  function check(ok) { if (!ok) throw new Error('恢复状态不完整或互相矛盾，系统现在只能读不能写。请不要再操作，联系维护人员。'); }
  function validateHost(host) {
    check(object(host) && ['ready', 'draining', 'restoring', 'restart_required', 'recovery_required'].includes(host.state)
      && host.restart_required === (host.state !== 'ready') && host.automatic_resume === false
      && typeof host.operations_available === 'boolean' && (host.state === 'ready' || host.operations_available === false)
      && host.result_source === source && typeof host.references === 'string'
      && (host.request_key === null || typeof host.request_key === 'string' && /^[A-Za-z0-9_-]{16,128}$/.test(host.request_key)));
    return host;
  }
  function envelope(value) {
    check(object(value) && value.ok === true && value.schema_version === 1 && object(value.data) && object(value.meta)
      && value.meta.source === 'production' && value.meta.result_source === source && value.meta.time_basis === 'factory_local'
      && typeof value.meta.request_ref === 'string' && /^[a-f0-9]{32}$/.test(value.meta.request_ref) && Array.isArray(value.warnings));
    validateHost(value.data.host); return value.data;
  }
  function host(value) { const data = envelope(value); check(data.kind === 'restore_host'); return data.host; }
  function operation(op) {
    check(op.result_source === source && typeof op.restart_required === 'boolean'
      && Object.prototype.hasOwnProperty.call(origins, op.database_origin)
      && ['target_sha256', 'protection_sha256', 'database_after_sha256'].every(key => op[key] === null || /^[a-f0-9]{64}$/.test(op[key])));
    if (op.action === 'restore') {
      check(op.restart_scope === 'restoring_process' && op.references_require_reload === true);
      const expected = { succeeded: 'selected_backup', rolled_back: 'protection_backup', failed: 'unchanged' };
      check(op.database_origin === (expected[op.state] || 'unconfirmed'));
    }
    return op;
  }
  function referencePath(reference, kind = 'request') {
    check(['request', 'job'].includes(kind) && typeof reference === 'string'
      && (kind === 'job' ? /^[a-f0-9]{32}$/ : /^[A-Za-z0-9_-]{16,128}$/).test(reference));
    return (kind === 'job' ? '/jobs/' : '/results/') + reference;
  }
  function describe(host, op) {
    const stopped = !host || host.state !== 'ready';
    const uncertain = !op || !op.terminal || !host || host.state === 'recovery_required'
      || stopped && host.request_key !== op.request_key;
    return {
      title: !host ? '无法读取维护状态' : !stopped ? op && op.terminal ? '上次维护结果已确认' : '维护结果还没有确认' : uncertain ? '系统已暂停，维护结果待确认' : '维护已结束，请重启整个软件',
      state: op ? labels[op.state] : '尚未查到可确认的维护结果',
      origin: op ? origins[op.database_origin] : origins.unconfirmed,
      guidance: !host ? '还不能确认软件维护状态，当前页面已暂停业务读写。请点「查询结果」重试，保留已有记录，不要重复恢复。'
        : !stopped ? op && op.terminal ? '维护已完成，请刷新页面后继续使用。' : '上次维护操作还没有确认结果。请等待结果或点「查询结果」，不要重复提交。'
        : uncertain ? '恢复结果待核对，请保留操作编号和备份，联系维护人员；勿重复恢复。'
          : '请关闭整个 APS 软件后重新启动。',
      uncertain
    };
  }
  function download(host, result, error) {
    const payload = { scope: 'read_only_maintenance', result_source: source, host, result,
      query_error: error ? error.message : null, database_checked_by_page: false,
      note: '导出当前维护状态。' };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = '恢复维护诊断.json';
    try { document.body.appendChild(link); link.click(); } finally { link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
  }
  window.SystemRestoreStatus = { validateHost, envelope, host, operation, referencePath, describe, download, labels, origins };
})();
