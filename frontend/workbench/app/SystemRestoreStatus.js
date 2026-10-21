(function () {
  'use strict';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const source = 'external_maintenance_journal';
  const labels = { accepted: '已接收', checking: '检查中', protecting: '生成保护副本', restoring: '恢复中', verifying: '完整性检查中',
    rolling_back: '还原中', succeeded: '已完成', failed: '操作失败', rolled_back: '恢复失败，已还原',
    rollback_failed: '还原失败，需人工核对', recovery_required: '结果不确定，需人工核对' };
  const hostLabels = { ready: '系统运行中', draining: '正在准备数据库恢复', restoring: '正在恢复数据库', restart_required: '恢复已结束，请重启软件', recovery_required: '恢复记录需要核对' };
  const origins = { selected_backup: '来自所选备份', protection_backup: '已还原到恢复前的保护副本', unchanged: '原数据库未被替换', unconfirmed: '维护记录尚未确认数据库来源' };
  const fileStates = { captured: '已读取原文件内容', verified: '与原文件内容一致', not_checked: '尚未核对', unavailable: '原内容核对资料缺失' };
  const sqliteStates = { passed: '完整性检查通过', not_checked: '尚未检查', unavailable: '完整性检查资料缺失' };
  const historicalDigests = [['历史所选备份 SHA-256', 'target_sha256'], ['历史保护副本 SHA-256', 'protection_sha256'], ['历史维护结束数据库 SHA-256', 'database_after_sha256']];
  function check(ok) { if (!ok) throw new Error('维护状态数据不完整或存在冲突，请重新查询并核对维护记录。'); }
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
      && Object.prototype.hasOwnProperty.call(origins, op.database_origin));
    const value = op.source_verification;
    check(object(value) && ['original_file_content_and_sqlite', 'legacy_record'].includes(value.basis)
      && ['target', 'protection'].every(key => Object.prototype.hasOwnProperty.call(fileStates, value[key]))
      && Object.prototype.hasOwnProperty.call(sqliteStates, value.sqlite_integrity));
    check(historicalDigests.every(([, key]) => value.basis === 'legacy_record'
      ? !Object.prototype.hasOwnProperty.call(op, key) || op[key] === null || typeof op[key] === 'string' && /^[a-f0-9]{64}$/.test(op[key])
      : !Object.prototype.hasOwnProperty.call(op, key)));
    if (op.action === 'restore') {
      check(op.restart_scope === 'restoring_process' && op.references_require_reload === true);
      const expected = { succeeded: 'selected_backup', rolled_back: 'protection_backup', failed: 'unchanged' };
      check(op.database_origin === (expected[op.state] || 'unconfirmed'));
    }
    return op;
  }
  function sourceFacts(op) {
    const value = op.source_verification;
    return [['所选备份内容', fileStates[value.target]], ['保护副本内容', fileStates[value.protection]], ['SQLite 完整性', sqliteStates[value.sqlite_integrity]]];
  }
  function legacyDigests(op) {
    return op.source_verification.basis === 'legacy_record' ? historicalDigests.filter(([, key]) => op[key]).map(([label, key]) => [label, op[key]]) : [];
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
      guidance: !host ? '恢复请求结果待确认，请查询维护记录。'
        : !stopped ? op && op.terminal ? '维护已完成，请刷新页面后继续使用。' : '上次维护操作还没有确认结果。请等待结果或点「查询结果」，不要重复提交。'
        : uncertain ? '恢复结果待核对，请保留操作编号和备份，联系维护人员；勿重复恢复。'
          : '请关闭整个 APS 软件后重新启动。',
      uncertain
    };
  }
  // 三种诊断文件各有一个名字：诊断包（日志 ZIP）、页面诊断（系统管理页）、维护诊断（恢复维护页）。
  const DIAGNOSTIC_FILENAME = '维护诊断.json';
  function download(host, result, error) {
    const payload = { scope: 'read_only_maintenance', result_source: source, host, result,
      query_error: error ? error.message : null, database_checked_by_page: false,
      note: '导出当前维护状态。' };
    window.APSWorkbenchTransport.downloadJSON(DIAGNOSTIC_FILENAME, payload);
  }
  window.SystemRestoreStatus = { validateHost, envelope, host, operation, sourceFacts, legacyDigests, referencePath, describe, download, labels, hostLabels, DIAGNOSTIC_FILENAME };
})();
