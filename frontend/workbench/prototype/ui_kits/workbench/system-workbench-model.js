(function (root) {
  'use strict';

  const SAMPLE_DATE = '2026-09-07';
  const STATES = Object.freeze({
    available: ['可用', 'success'], unavailable: ['不可用', 'danger'], unknown: ['未知', 'neutral'],
    disconnected: ['未连接', 'neutral'], failed: ['失败', 'danger'], blocked: ['受阻', 'warning'],
    pending: ['待执行', 'notice'], skipped: ['已跳过', 'warning'], verified: ['校验通过', 'success'],
    unverified: ['未校验', 'warning'], recorded: ['已记录', 'neutral']
  });
  const TYPES = Object.freeze({ manual: '手动备份', auto: '自动备份', restore: '数据库恢复',
    before_restore: '恢复前备份', cleanup: '备份清理', runtime: '运行日志', operation: '操作日志' });
  const LEVELS = Object.freeze({ INFO: '信息', WARNING: '警告', ERROR: '错误', DEBUG: '调试', CRITICAL: '严重' });
  const SOURCES = Object.freeze({ 'aps.log': '主日志（aps.log）', 'aps_error.log': '错误日志（aps_error.log）',
    'launcher.log': '启动日志（launcher.log）', OperationLogs: '操作记录' });
  const CHECKS = Object.freeze({
    runtime: '页面运行依赖', localScripts: '本地脚本文件', ui: '工作台组件', icons: '本地图标',
    styles: '系统管理样式', model: '管理资源模型', download: '本地文件导出', theme: '主题控制'
  });
  // Boundaries mirror SystemConfigService; these are sample values, not a production snapshot.
  const CONFIG_FIELDS = Object.freeze([
    { key: 'auto_backup_enabled', label: '自动备份', group: 'backup', kind: 'switch' },
    { key: 'auto_backup_interval_minutes', label: '备份检查间隔', group: 'backup', unit: '分钟', min: 1, max: 1440 },
    { key: 'auto_backup_cleanup_enabled', label: '清理过期备份', group: 'backup', kind: 'switch' },
    { key: 'auto_backup_keep_days', label: '备份保留时间', group: 'backup', unit: '天', min: 1, max: 365 },
    { key: 'auto_backup_cleanup_interval_minutes', label: '备份清理检查间隔', group: 'backup', unit: '分钟', min: 1, max: 1440 },
    { key: 'auto_log_cleanup_enabled', label: '清理操作日志', group: 'logs', kind: 'switch' },
    { key: 'auto_log_cleanup_keep_days', label: '操作日志保留时间', group: 'logs', unit: '天', min: 1, max: 365 },
    { key: 'auto_log_cleanup_interval_minutes', label: '日志清理检查间隔', group: 'logs', unit: '分钟', min: 1, max: 1440 }
  ].map(Object.freeze));
  const SAMPLE_CONFIG = Object.freeze({ auto_backup_enabled: 'yes', auto_backup_interval_minutes: '60',
    auto_backup_cleanup_enabled: 'yes', auto_backup_keep_days: '30', auto_backup_cleanup_interval_minutes: '1440',
    auto_log_cleanup_enabled: 'no', auto_log_cleanup_keep_days: '30', auto_log_cleanup_interval_minutes: '60' });

  const SAMPLE_NOTE = '这里显示的是样例数据，不是本机真实日志。';
  const scenarios = [
    ['auto', 'failed', '自动备份写入失败，本次未生成备份', '磁盘空间不足，临时副本没有成为正式备份。\n样例备份文件夹：C:\\APS-SAMPLE\\backups\\2026\\09\\设备产能数据归档\\aps_20260907_auto.db\n下一步：清理磁盘空间后重新备份。\n' + SAMPLE_NOTE],
    ['cleanup', 'skipped', '自动备份失败，本轮清理已跳过', '这一轮自动备份失败，所以清理没有执行，旧备份没有被删除。\n' + SAMPLE_NOTE],
    ['restore', 'failed', '恢复后结构检查没通过，已还原', '样例恢复出来的副本没通过数据表检查，已经回到恢复前的副本。\n这不是恢复成功的记录。\n' + SAMPLE_NOTE],
    ['restore', 'blocked', '数据库正在维护，恢复未执行', '数据库维护还没结束，本次操作没有改动数据库。\n' + SAMPLE_NOTE],
    ['auto', 'pending', '到期检查待触发', '打开页面时系统才会检查一次自动维护，没有后台定时任务。\n这一行是待执行的样例，不是排队中的任务。\n' + SAMPLE_NOTE],
    ['manual', 'verified', '手动备份完成完整性检查', '样例副本的完整性检查已通过。\n检查通过不等于已经演练过恢复。\n' + SAMPLE_NOTE],
    ['before_restore', 'verified', '恢复前保护副本已生成', '正式恢复前会先存一份恢复前副本。这条样例没有实际文件。\n' + SAMPLE_NOTE],
    ['manual', 'unverified', '历史副本只有文件基本信息', '还没有完整性检查证据，文件存在不等于副本可用。\n' + SAMPLE_NOTE],
    ['restore', 'failed', '结构检查和自动还原都失败', '请不要再操作数据库，联系维护人员并查看正式日志。\n' + SAMPLE_NOTE],
    ['cleanup', 'recorded', '过期副本按保底规则保留', '按保留天数清理时仍留下最新副本，这条没有执行删除。\n' + SAMPLE_NOTE]
  ];

  function sampleTime(index) {
    return new Date(Date.UTC(2026, 8, 7, 18, 0) - index * 3 * 3600000).toISOString().slice(0, 19).replace('T', ' ');
  }
  function buildSamples() {
    const backups = Array.from({ length: 24 }, (_, i) => {
      const [type, status, summary, body] = scenarios[i % scenarios.length];
      const hasFile = ['verified', 'unverified'].includes(status);
      return Object.freeze({ id: 'sample-backup-' + (i + 1), source: 'sample', time: sampleTime(i), type, status,
        summary, body, filename: hasFile ? 'aps_sample_' + String(i + 1).padStart(3, '0') + '_' + type + '.db' : null,
        sizeBytes: hasFile ? (82 + i) * 1024 * 1024 : null });
    });
    const logs = Array.from({ length: 64 }, (_, i) => {
      const [action, status, summary, body] = scenarios[i % scenarios.length];
      const type = i % 3 === 0 ? 'operation' : 'runtime';
      const level = status === 'failed' ? 'ERROR' : ['blocked', 'skipped', 'unverified'].includes(status) ? 'WARNING' : 'INFO';
      return Object.freeze({ id: 'sample-log-' + (i + 1), source: 'sample', time: sampleTime(i), type, status, level,
        file: type === 'operation' ? 'OperationLogs' : level === 'ERROR' ? 'aps_error.log' : i % 4 === 0 ? 'launcher.log' : 'aps.log',
        action, summary, body: '[管理样例] ' + body + (i === 8 ? '\n' + '恢复后的检查项没通过，这段样例说明需要完整显示。'.repeat(150) : '') });
    });
    return Object.freeze({ source: 'sample', backups: Object.freeze(backups), logs: Object.freeze(logs) });
  }
  const SAMPLES = buildSamples();
  const CURRENT = Object.freeze({ source: 'current', backups: null, logs: null });
  function dataset(source) {
    if (source === 'current') return CURRENT;
    if (source === 'sample') return SAMPLES;
    throw new Error('Unknown system workbench source');
  }
  function validateConfig(draft) {
    const errors = {}, value = {};
    CONFIG_FIELDS.forEach(field => {
      const raw = String(draft[field.key] == null ? '' : draft[field.key]).trim();
      if (field.kind === 'switch') {
        if (!['yes', 'no'].includes(raw)) errors[field.key] = '请选择启用或关闭';
        else value[field.key] = raw;
      } else if (!/^\d+$/.test(raw) || !Number.isSafeInteger(Number(raw))) errors[field.key] = '请输入整数';
      else if (Number(raw) < field.min || Number(raw) > field.max) errors[field.key] = '允许 ' + field.min + '–' + field.max + ' ' + field.unit;
      else value[field.key] = Number(raw);
    });
    return { valid: !Object.keys(errors).length, errors, value };
  }
  function dateError(filters) {
    for (const key of ['start', 'end']) {
      const date = filters[key];
      if (!date) continue;
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return '请按 2026-09-13 这样填日期';
      const stamp = new Date(date + 'T00:00:00Z');
      if (!Number.isFinite(stamp.getTime()) || stamp.toISOString().slice(0, 10) !== date) return '日期无效';
    }
    return filters.start && filters.end && filters.start > filters.end ? '开始日期不能晚于结束日期' : '';
  }
  function filterRows(rows, filters = {}) {
    if (rows === null) return { rows: null, error: '' };
    const error = dateError(filters);
    if (error) return { rows: [], error };
    const query = String(filters.query || '').trim().toLowerCase();
    const filtered = rows.filter(row => {
      if (['status', 'type', 'level', 'file'].some(key => filters[key] && row[key] !== filters[key])) return false;
      const day = row.time.slice(0, 10);
      if ((filters.start && day < filters.start) || (filters.end && day > filters.end)) return false;
      return !query || [row.time, row.summary, row.body, row.filename, row.file, row.action, TYPES[row.type]]
        .join(' ').toLowerCase().includes(query);
    }).sort((a, b) => b.time.localeCompare(a.time) || a.id.localeCompare(b.id));
    return { rows: filtered, error: '' };
  }
  function paginate(rows, page, pageSize) {
    const size = [10, 25, 50].includes(Number(pageSize)) ? Number(pageSize) : 10;
    if (rows === null) return { rows: null, total: null, pages: null, page: 1, start: null, end: null, pageSize: size };
    const pages = Math.max(1, Math.ceil(rows.length / size));
    const safe = Number.isFinite(Number(page)) ? Math.trunc(Number(page)) : 1;
    const current = Math.max(1, Math.min(pages, safe));
    return { rows: rows.slice((current - 1) * size, current * size), total: rows.length, pages, page: current,
      start: rows.length ? (current - 1) * size + 1 : 0, end: Math.min(current * size, rows.length), pageSize: size };
  }
  function canDownload(w) {
    return typeof w.Blob === 'function' && !!w.URL && typeof w.URL.createObjectURL === 'function' &&
      typeof w.URL.revokeObjectURL === 'function' && !!w.document && 'download' in w.document.createElement('a');
  }
  function inspectEnvironment(w, themeProps = {}) {
    const checks = [];
    const check = (id, test, good, bad) => {
      try { const ok = !!test(); checks.push({ id, label: CHECKS[id], status: ok ? 'available' : 'unavailable', detail: ok ? good : bad }); }
      catch (_) { checks.push({ id, label: CHECKS[id], status: 'unavailable', detail: bad }); }
    };
    check('runtime', () => w.React && typeof w.React.createElement === 'function' && w.ReactDOM && typeof w.ReactDOM.createRoot === 'function',
      'React 与 ReactDOM 已加载；只代表当前页面可渲染。', 'React 或 ReactDOM 未加载。');
    check('localScripts', () => {
      const sources = Array.from(w.document.querySelectorAll('script[src]')).map(script => script.getAttribute('src'));
      return sources.length > 0 && sources.every(src => src && !/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(src));
    }, '页面用到的脚本都在本机；这不等于逐个文件都做过完整性检查。', '页面用到了外部脚本，或者没有可核对的脚本清单。');
    check('ui', () => ['MetricStrip', 'Metric', 'DataTable', 'TransferButton', 'ControlButton'].every(key => w.APSWorkbenchUI && typeof w.APSWorkbenchUI[key] === 'function'),
      '指标、表格与操作组件已加载。', '工作台公共组件缺失。');
    check('icons', () => ['file-output', 'chevron-left', 'chevron-right', 'x', 'search', 'history'].every(key => w.APSFieldReports && Array.isArray(w.APSFieldReports.iconNodes && w.APSFieldReports.iconNodes[key])),
      '页面使用的本地 Lucide 图标已加载。', '本地图标资源缺失。');
    check('styles', () => {
      const node = w.document.querySelector('.sm-workbench');
      return node && w.getComputedStyle(node).getPropertyValue('--sm-workbench-ready').trim() === '1';
    }, '系统管理样式标记已生效；未进行像素或布局验收。', '未检测到系统管理样式标记。');
    check('model', () => w.APSSystemWorkbench === API && SAMPLES.logs.every(row => row.source === 'sample' && STATES[row.status]) && CURRENT.logs === null,
      '当前环境与固定管理样例分开；本机运行数据尚未读取。', '管理资源模型没有加载，或者读到的数据不完整。请刷新重试。');
    check('download', () => canDownload(w), '浏览器支持把文件存到本机；是否保存以浏览器下载结果为准。', '当前浏览器不支持下载文件，请用 Chrome 打开。');
    check('theme', () => ['light', 'dark'].includes(themeProps.theme) && (typeof themeProps.onToggleTheme === 'function' || typeof themeProps.onSetTheme === 'function'),
      '深色与浅色切换可用。', '本页暂时不能切换深色浅色。');
    return { schemaVersion: 1, scope: 'current-prototype', checkedAt: new Date().toISOString(),
      protocol: ['file:', 'http:', 'https:'].includes(w.location.protocol) ? w.location.protocol : 'other',
      service: 'disconnected', database: 'unknown', backupHealth: 'unknown', checks };
  }
  function diagnosticJSON(report) {
    // Explicit projection: never serialize location, storage, DOM, props, or raw exception messages.
    return JSON.stringify({ schemaVersion: 1, scope: 'current-prototype', checkedAt: report.checkedAt,
      protocol: report.protocol, service: 'disconnected', database: 'unknown', backupHealth: 'unknown',
      checks: report.checks.filter(item => CHECKS[item.id]).map(item => ({ id: item.id, status: item.status })),
      excluded: ['production-data', 'logs', 'paths', 'storage', 'credentials', 'management-samples'] }, null, 2);
  }
  function csvCell(value) {
    let text = String(value == null ? '' : value);
    if (/^[\s\uFEFF]*[=+@-]/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  }
  function sampleLogCSV(filters) {
    const result = filterRows(SAMPLES.logs, filters);
    if (result.error) throw new Error(result.error);
    const header = ['数据来源', '时间', '类型', '级别', '状态', '日志来源', '摘要', '详情'];
    const rows = result.rows.map(row => ['管理样例', row.time, TYPES[row.type], LEVELS[row.level] || row.level,
      STATES[row.status][0], SOURCES[row.file] || row.file, row.summary, row.body]);
    return '\uFEFF' + [header].concat(rows).map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
  }
  function download(w, filename, mime, text) {
    if (!canDownload(w)) throw new Error('当前浏览器不支持本地文件导出');
    let url, anchor;
    try {
      url = w.URL.createObjectURL(new w.Blob([text], { type: mime }));
      anchor = w.document.createElement('a'); anchor.href = url; anchor.download = filename;
      anchor.hidden = true; w.document.body.appendChild(anchor); anchor.click();
    } finally {
      if (anchor) anchor.remove();
      if (url) w.setTimeout(() => w.URL.revokeObjectURL(url), 1000);
    }
  }
  const API = Object.freeze({ schemaVersion: 1, SAMPLE_DATE, STATES, TYPES, LEVELS, SOURCES, CONFIG_FIELDS, SAMPLE_CONFIG,
    dataset, validateConfig, filterRows, paginate, inspectEnvironment, diagnosticJSON, canDownload, sampleLogCSV, csvCell, download });
  if (typeof module === 'object' && module.exports) module.exports = API;
  else root.APSSystemWorkbench = API;
})(typeof window === 'object' ? window : globalThis);
