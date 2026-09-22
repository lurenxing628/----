(function (root) {
  'use strict';

  const STATES = Object.freeze({
    available: ['可用', 'success'],
    unavailable: ['不可用', 'danger'],
    unknown: ['未知', 'neutral']
  });
  const CHECKS = Object.freeze({
    runtime: '页面运行依赖',
    localScripts: '本地脚本文件',
    ui: '工作台组件',
    icons: '本地图标',
    styles: '系统管理样式',
    model: '页面支持模型',
    download: '本地文件导出',
    theme: '主题控制'
  });

  function canDownload(w) {
    return typeof w.Blob === 'function' && !!w.URL && typeof w.URL.createObjectURL === 'function' &&
      typeof w.URL.revokeObjectURL === 'function' && !!w.document && 'download' in w.document.createElement('a');
  }

  function inspectEnvironment(w, themeProps = {}) {
    const checks = [];
    const check = (id, test, good, bad) => {
      try {
        const ok = !!test();
        checks.push({ id, label: CHECKS[id], status: ok ? 'available' : 'unavailable', detail: ok ? good : bad });
      } catch (_) {
        checks.push({ id, label: CHECKS[id], status: 'unavailable', detail: bad });
      }
    };
    check('runtime', () => w.React && typeof w.React.createElement === 'function' && w.ReactDOM && typeof w.ReactDOM.createRoot === 'function',
      'React 与 ReactDOM 已加载；只代表当前页面可渲染。', 'React 或 ReactDOM 未加载。');
    check('localScripts', () => {
      const sources = Array.from(w.document.querySelectorAll('script[src]')).map(script => script.getAttribute('src'));
      return sources.length > 0 && sources.every(src => src && !/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(src));
    }, '页面用到的脚本都在本机；这不等于逐个文件都做过完整性检查。', '页面用到了外部脚本，或者没有可核对的脚本清单。');
    check('ui', () => ['MetricStrip', 'Metric', 'TransferButton', 'ControlButton'].every(key => w.APSWorkbenchUI && typeof w.APSWorkbenchUI[key] === 'function'),
      '指标与操作组件已加载。', '工作台公共组件缺失。');
    check('icons', () => ['file-output', 'folder-open'].every(key => w.APSFieldReports && Array.isArray(w.APSFieldReports.iconNodes && w.APSFieldReports.iconNodes[key])),
      '页面使用的本地图标已加载。', '本地图标资源缺失。');
    check('styles', () => {
      const node = w.document.querySelector('.sm-workbench');
      return node && w.getComputedStyle(node).getPropertyValue('--sm-workbench-ready').trim() === '1';
    }, '系统管理样式标记已生效；未进行像素或布局验收。', '未检测到系统管理样式标记。');
    check('model', () => w.APSSystemWorkbench === API && typeof API.csvCell === 'function',
      '页面支持模型已加载；本机运行数据尚未读取。', '页面支持模型没有加载。请刷新重试。');
    check('download', () => canDownload(w), '浏览器支持把文件存到本机；是否保存以浏览器下载结果为准。', '当前浏览器不支持下载文件，请用 Chrome 打开。');
    check('theme', () => ['light', 'dark'].includes(themeProps.theme) && (typeof themeProps.onToggleTheme === 'function' || typeof themeProps.onSetTheme === 'function'),
      '深色与浅色切换可用。', '本页暂时不能切换深色浅色。');
    return {
      schemaVersion: 1,
      scope: 'current-prototype',
      checkedAt: new Date().toISOString(),
      protocol: ['file:', 'http:', 'https:'].includes(w.location.protocol) ? w.location.protocol : 'other',
      service: 'disconnected',
      database: 'unknown',
      backupHealth: 'unknown',
      checks
    };
  }

  function diagnosticJSON(report) {
    // Explicit projection: never serialize location, storage, DOM, props, raw exceptions or business data.
    return JSON.stringify({
      schemaVersion: 1,
      scope: 'current-prototype',
      checkedAt: report.checkedAt,
      protocol: report.protocol,
      service: 'disconnected',
      database: 'unknown',
      backupHealth: 'unknown',
      checks: report.checks.filter(item => CHECKS[item.id]).map(item => ({ id: item.id, status: item.status })),
      excluded: ['production-data', 'logs', 'paths', 'storage', 'credentials']
    }, null, 2);
  }

  function csvCell(value) {
    let text = String(value == null ? '' : value);
    if (/^[\s\uFEFF]*[=+@-]/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  }

  function download(w, filename, mime, text) {
    if (!canDownload(w)) throw new Error('当前浏览器不支持本地文件导出');
    let url, anchor;
    try {
      url = w.URL.createObjectURL(new w.Blob([text], { type: mime }));
      anchor = w.document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      anchor.hidden = true;
      w.document.body.appendChild(anchor);
      anchor.click();
    } finally {
      if (anchor) anchor.remove();
      if (url) w.setTimeout(() => w.URL.revokeObjectURL(url), 1000);
    }
  }

  const API = Object.freeze({ schemaVersion: 1, STATES, inspectEnvironment, diagnosticJSON, canDownload, csvCell, download });
  if (typeof module === 'object' && module.exports) module.exports = API;
  else root.APSSystemWorkbench = API;
})(typeof window === 'object' ? window : globalThis);
