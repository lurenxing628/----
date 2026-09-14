(function () {
  'use strict';

  const present = value => value !== null && value !== undefined && value !== '';
  const text = value => typeof value === 'string' ? value : typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
  function WorkbenchReference({
    value,
    entries,
    label = '编号'
  }) {
    const rows = Object.entries(entries || {}).filter(([, item]) => present(item));
    if (present(value)) rows.unshift(['编号', value]);
    if (!rows.length) return null;
    return /*#__PURE__*/React.createElement("details", {
      className: "wb-ref"
    }, /*#__PURE__*/React.createElement("summary", null, label), /*#__PURE__*/React.createElement("dl", null, rows.map(([name, item], index) => /*#__PURE__*/React.createElement("div", {
      key: index
    }, /*#__PURE__*/React.createElement("dt", null, name), /*#__PURE__*/React.createElement("dd", null, /*#__PURE__*/React.createElement("code", null, text(item)))))));
  }
  function technical(message) {
    const trimmed = message.trim();
    // File names are actionable business context; their dots/underscores are not rule codes.
    const codes = trimmed.replace(/\b[\w.-]+\.(?:csv|tsv|xls|xlsx|txt|log|json|zip|db|bak|pdf|md)\b/gi, '');
    return /[0-9a-f]{32,}/i.test(message) || /\b[a-z][a-z0-9]*(?:[_.][a-z0-9]+)+\b/i.test(codes) || /(?:HTTP\s*[:：]?\s*[1-5]\d\d|状态码\s*[:：]?\s*[1-5]\d\d|\b\w*(?:Error|Exception)\b)/i.test(message) || /^[a-z][a-z0-9_.-]*$/i.test(codes) || /[\[{]\s*["']?[^\s\]}]+["']?\s*:/.test(message) || trimmed.startsWith('[') && trimmed.endsWith(']') || trimmed.startsWith('{') && trimmed.endsWith('}');
  }
  function WorkbenchError({
    error,
    fallback = '操作未完成，请核对后重试。',
    fields = [],
    excludePaths = [],
    hideMessage = false
  }) {
    if (!error) return null;
    const message = typeof error === 'string' ? error : typeof error.message === 'string' ? error.message : '';
    const entries = {},
      messages = [];
    if (message && technical(message)) entries['原始错误信息'] = message;
    if (!hideMessage) messages.push(message && !technical(message) ? message : fallback);
    const labels = {
      code: '错误编号',
      status: '状态码',
      request_key: '操作编号',
      request_ref: '结果编号',
      request_id: '操作标记',
      trace_id: '诊断编号'
    };
    Object.entries(labels).forEach(([key, label]) => {
      if (present(error[key])) entries[label] = error[key];
    });
    if (error.name && error.name !== 'Error') entries['错误类型'] = error.name;
    fields.forEach((field, index) => {
      if (!field || excludePaths.includes(field.path)) return;
      const detail = typeof field.message === 'string' ? field.message : '';
      if (!detail) return;
      if (technical(detail)) {
        entries['填写项说明 ' + (index + 1)] = detail;
        if (!messages.length) messages.push(fallback);
      } else if (!messages.includes(detail)) messages.push(detail);
      if (present(field.code)) entries['填写项编号 ' + (index + 1)] = field.code;
    });
    if (!messages.length && !Object.keys(entries).length) return null;
    return /*#__PURE__*/React.createElement("div", {
      className: "wb-error",
      role: "alert"
    }, messages.map((message, index) => /*#__PURE__*/React.createElement("div", {
      key: index
    }, message)), /*#__PURE__*/React.createElement(WorkbenchReference, {
      entries: entries
    }));
  }
  window.WorkbenchReference = WorkbenchReference;
  window.WorkbenchError = WorkbenchError;
})();
