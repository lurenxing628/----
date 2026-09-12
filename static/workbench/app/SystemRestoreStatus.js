(function () {
  'use strict';

  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const source = 'external_maintenance_journal';
  const labels = {
    accepted: '已受理',
    checking: '检查中',
    protecting: '创建保护副本',
    restoring: '恢复中',
    verifying: '校验中',
    rolling_back: '回滚中',
    succeeded: '已完成',
    failed: '操作失败',
    rolled_back: '恢复失败，已回滚',
    rollback_failed: '回滚失败，需人工核查',
    recovery_required: '结果未知，需人工核查'
  };
  const origins = {
    selected_backup: '来自所选备份',
    protection_backup: '已回滚到恢复前保护副本',
    unchanged: '原数据库未被替换',
    unconfirmed: '未知，不能确认当前数据库内容'
  };
  function check(ok) {
    if (!ok) throw new Error('恢复状态不完整或相互矛盾，系统保持只读；请保留现场。');
  }
  function validateHost(host) {
    check(object(host) && ['ready', 'draining', 'restoring', 'restart_required', 'recovery_required'].includes(host.state) && host.restart_required === (host.state !== 'ready') && host.automatic_resume === false && typeof host.operations_available === 'boolean' && (host.state === 'ready' || host.operations_available === false) && host.result_source === source && typeof host.references === 'string' && (host.request_key === null || typeof host.request_key === 'string' && /^[A-Za-z0-9_-]{16,128}$/.test(host.request_key)));
    return host;
  }
  function envelope(value) {
    check(object(value) && value.ok === true && value.schema_version === 1 && object(value.data) && object(value.meta) && value.meta.source === 'production' && value.meta.result_source === source && value.meta.time_basis === 'factory_local' && typeof value.meta.request_ref === 'string' && /^[a-f0-9]{32}$/.test(value.meta.request_ref) && Array.isArray(value.warnings));
    validateHost(value.data.host);
    return value.data;
  }
  function host(value) {
    const data = envelope(value);
    check(data.kind === 'restore_host');
    return data.host;
  }
  function operation(op) {
    check(op.result_source === source && typeof op.restart_required === 'boolean' && Object.prototype.hasOwnProperty.call(origins, op.database_origin) && ['target_sha256', 'protection_sha256', 'database_after_sha256'].every(key => op[key] === null || /^[a-f0-9]{64}$/.test(op[key])));
    if (op.action === 'restore') {
      check(op.restart_scope === 'restoring_process' && op.references_require_reload === true);
      const expected = {
        succeeded: 'selected_backup',
        rolled_back: 'protection_backup',
        failed: 'unchanged'
      };
      check(op.database_origin === (expected[op.state] || 'unconfirmed'));
    }
    return op;
  }
  function referencePath(reference, kind = 'request') {
    check(['request', 'job'].includes(kind) && typeof reference === 'string' && (kind === 'job' ? /^[a-f0-9]{32}$/ : /^[A-Za-z0-9_-]{16,128}$/).test(reference));
    return (kind === 'job' ? '/jobs/' : '/results/') + reference;
  }
  function describe(host, op) {
    const stopped = !host || host.state !== 'ready';
    const uncertain = !op || !op.terminal || !host || host.state === 'recovery_required' || stopped && host.request_key !== op.request_key;
    return {
      title: !host ? '无法读取维护状态' : !stopped ? op && op.terminal ? '原维护结果已核实' : '维护结果尚未核实' : uncertain ? '系统已暂停，维护结果待核实' : '维护已结束，请重启整个软件',
      state: op ? labels[op.state] : '尚未查到可确认的维护结果',
      origin: op ? origins[op.database_origin] : origins.unconfirmed,
      guidance: !host ? '尚不能确认软件维护状态，当前页面已暂停业务读写。请重试核实原请求，保留已有记录，不要重复恢复。' : !stopped ? op && op.terminal ? '当前软件服务可用。确认这条原结果后，重新读取本机资料；旧页面引用不能沿用。' : '原维护请求尚未核实。请等待结果或查询原请求，不要重新提交。' : uncertain ? '请保留原请求标识、备份和保护副本，交给维护人员核查。未核实记录会继续阻止启动；不要重复恢复，也不要自行改维护标记。' : '请先关闭整个 APS 软件，再重新启动。只刷新或关闭浏览器不算重启；重新启动后再读取本机资料。',
      uncertain
    };
  }
  function download(host, result, error) {
    const payload = {
      scope: 'read_only_maintenance',
      result_source: source,
      host,
      result,
      query_error: error ? error.message : null,
      database_checked_by_page: false,
      note: '仅含本次读取的外置维护状态，不含数据库或完整日志；导出不会修改维护标记。'
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: 'application/json;charset=utf-8'
    });
    const url = URL.createObjectURL(blob),
      link = document.createElement('a');
    link.href = url;
    link.download = 'aps-restore-maintenance-diagnostic.json';
    try {
      document.body.appendChild(link);
      link.click();
    } finally {
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  }
  window.SystemRestoreStatus = {
    validateHost,
    envelope,
    host,
    operation,
    referencePath,
    describe,
    download,
    labels,
    origins
  };
})();
