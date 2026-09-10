(function () {
  'use strict';
  var states = ['available', 'empty', 'partial', 'missing', 'error', 'not_read'];
  var jobs = ['auto_backup', 'auto_backup_cleanup', 'auto_log_cleanup'];
  var results = ['completed', 'failed', 'partial', 'skipped', 'invalid', 'unknown', 'not_recorded'];
  var switches = ['auto_backup_enabled', 'auto_backup_cleanup_enabled', 'auto_log_cleanup_enabled'];
  var numbers = ['auto_backup_interval_minutes', 'auto_backup_keep_days', 'auto_backup_cleanup_interval_minutes',
    'auto_log_cleanup_keep_days', 'auto_log_cleanup_interval_minutes'];
  function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
  function text(value) { return typeof value === 'string'; }
  function count(value) { return Number.isSafeInteger(value) && value >= 0; }
  function countOrNull(value) { return value === null || count(value); }
  function error(value) { return value === null || (object(value) && text(value.message) && text(value.code)); }
  function section(value) {
    return object(value) && states.includes(value.state) && text(value.message) && error(value.error);
  }
  function files(value) {
    return countOrNull(value.count) && typeof value.files_truncated === 'boolean' && Array.isArray(value.files) && value.files.every(function (file) {
      return object(file) && text(file.filename) && !!file.filename && text(file.modified_at) && !!file.modified_at && count(file.size_bytes);
    });
  }
  function fields(value) {
    return Array.isArray(value) && value.every(function (key) { return switches.includes(key) || numbers.includes(key); });
  }
  function config(value) {
    if (value.values === null) return true;
    return object(value.values) && switches.every(function (key) { return ['yes', 'no'].includes(value.values[key]); })
      && numbers.every(function (key) { return count(value.values[key]); })
      && fields(value.defaulted_fields) && fields(value.dirty_fields) && object(value.dirty_reasons)
      && value.dirty_fields.every(function (key) { return text(value.dirty_reasons[key]); });
  }
  function maintenance(value) {
    return Array.isArray(value.jobs) && value.jobs.length === jobs.length && jobs.every(function (kind) {
      var matches = value.jobs.filter(function (job) { return object(job) && job.kind === kind; });
      if (matches.length !== 1) return false;
      var job = matches[0];
      return (job.last_run_time === null || text(job.last_run_time))
        && (job.result === null || (object(job.result) && results.includes(job.result.status)));
    });
  }
  function validate(data) {
    return object(data) && ['database', 'backups', 'logs', 'config', 'maintenance'].every(function (key) { return section(data[key]); })
      && files(data.backups) && files(data.logs) && countOrNull(data.logs.operation_record_count)
      && config(data.config) && maintenance(data.maintenance);
  }
  window.APSWorkbenchSystemContract = { validate: validate };
})();
