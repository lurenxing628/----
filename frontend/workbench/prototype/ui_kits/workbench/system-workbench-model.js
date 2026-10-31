(function (root) {
  'use strict';

  const STATES = Object.freeze({
    available: ['可用', 'success'],
    unavailable: ['不可用', 'danger'],
    unknown: ['未知', 'neutral']
  });
  const CHECKS = Object.freeze({
    styles: '系统管理样式',
    download: '本地文件导出'
  });

  function canDownload(w) {
    return typeof w.Blob === 'function' && !!w.URL && typeof w.URL.createObjectURL === 'function' &&
      typeof w.URL.revokeObjectURL === 'function' && !!w.document && 'download' in w.document.createElement('a');
  }

  function inspectEnvironment(w) {
    const checks = [];
    const check = (id, test, good, bad) => {
      try {
        const ok = !!test();
        checks.push({ id, label: CHECKS[id], status: ok ? 'available' : 'unavailable', detail: ok ? good : bad });
      } catch (_) {
        checks.push({ id, label: CHECKS[id], status: 'unavailable', detail: bad });
      }
    };
    check('styles', () => {
      const node = w.document.querySelector('.sm-workbench');
      return node && w.getComputedStyle(node).getPropertyValue('--sm-workbench-ready').trim() === '1';
    }, '系统管理样式标记已生效；未进行像素或布局验收。', '未检测到系统管理样式标记。');
    check('download', () => canDownload(w), '浏览器支持把文件存到本机；是否保存以浏览器下载结果为准。', '当前浏览器不支持下载文件，请用 Chrome 打开。');
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

  function csvCell(value) {
    let text = String(value == null ? '' : value);
    if (/^[\s\uFEFF]*[=+@-]/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  }

  const API = Object.freeze({ schemaVersion: 1, STATES, inspectEnvironment, canDownload, csvCell });
  if (typeof module === 'object' && module.exports) module.exports = API;
  else root.APSSystemWorkbench = API;
})(typeof window === 'object' ? window : globalThis);
