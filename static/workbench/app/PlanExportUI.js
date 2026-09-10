(function () {
  'use strict';

  const {
    Button,
    Modal,
    ErrorBox
  } = window.ResourceControls;
  const C = window.APSResourceContract,
    P = window.APSPlanContract,
    M = window.PlanGanttModel;
  function filename(disposition, format) {
    const unicode = /filename\*=UTF-8''([^;]+)/i.exec(disposition),
      plain = /filename="([^"\r\n]+)"|filename=([^;\s]+)/i.exec(disposition);
    const name = unicode ? decodeURIComponent(unicode[1]) : plain && (plain[1] || plain[2]);
    if (!name || /[/\\\u0000-\u001f]/.test(name) || !name.toLowerCase().endsWith('.' + format)) throw C.failure('导出文件名不正确，已停止下载。');
    return name;
  }
  function PlanExportUI({
    adapter,
    result,
    query,
    matched,
    disabled
  }) {
    const [format, setFormat] = React.useState(null),
      [busy, setBusy] = React.useState(false),
      [error, setError] = React.useState(null),
      [notice, setNotice] = React.useState('');
    const active = React.useRef(null);
    React.useEffect(() => () => {
      if (active.current) active.current.abort();
    }, [adapter, result]);
    const reason = disabled || !result ? '先读取所选计划，才能导出当前内容。' : !result.data.plan.capabilities.export || typeof adapter.export !== 'function' ? '当前还不能导出所选计划。' : '';
    function cancel() {
      if (active.current) active.current.abort();
      active.current = null;
      setBusy(false);
      setFormat(null);
    }
    async function download() {
      if (busy || reason) return;
      const controller = new AbortController();
      active.current = controller;
      setBusy(true);
      setError(null);
      setNotice('');
      try {
        const scope = {
          format,
          snapshot_ref: result.meta.snapshot_ref
        };
        if (result.data.scope.range_start !== null) {
          scope.range_start = result.data.scope.range_start;
          scope.range_end = result.data.scope.range_end;
        }
        P.exportScope(result.data.plan.plan_ref, scope);
        const output = P.download(await adapter.export(result.data.plan.plan_ref, scope, controller.signal), format);
        if (controller.signal.aborted || active.current !== controller) return;
        if (!(output.blob instanceof Blob)) throw C.failure('导出附件不是有效文件。');
        const name = filename(output.disposition, format),
          url = URL.createObjectURL(output.blob),
          anchor = document.createElement('a');
        try {
          anchor.href = url;
          anchor.download = name;
          document.body.appendChild(anchor);
          anchor.click();
        } finally {
          anchor.remove();
          window.setTimeout(() => URL.revokeObjectURL(url), 1000);
        }
        setNotice('已发起下载：' + name);
        setFormat(null);
      } catch (failure) {
        if (!controller.signal.aborted && active.current === controller) setError(failure);
      } finally {
        if (active.current === controller) {
          active.current = null;
          setBusy(false);
        }
      }
    }
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      transfer: "export",
      reason: reason,
      busy: busy,
      onClick: () => {
        setFormat('csv');
        setError(null);
        setNotice('');
      }
    }, "\u5BFC\u51FA"), notice && /*#__PURE__*/React.createElement("span", {
      role: "status",
      className: "plan-muted"
    }, notice), format && result && /*#__PURE__*/React.createElement(Modal, {
      title: "\u5BFC\u51FA\u8BA1\u5212",
      icon: "download",
      onClose: cancel,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: cancel
      }, busy ? '取消导出' : '取消'), /*#__PURE__*/React.createElement(Button, {
        transfer: "export",
        className: "btn primary",
        busy: busy,
        onClick: download
      }, "\u4E0B\u8F7D ", format.toUpperCase()))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b plan-export-summary"
    }, /*#__PURE__*/React.createElement(window.PlanSegmentUI, {
      value: format,
      options: [["csv", "CSV"], ["xlsx", "XLSX"]],
      label: "\u8BA1\u5212\u5BFC\u51FA\u683C\u5F0F",
      disabled: busy,
      onChange: setFormat
    }), /*#__PURE__*/React.createElement("p", null, /*#__PURE__*/React.createElement("strong", null, result.data.plan.display_name)), /*#__PURE__*/React.createElement("p", null, "\u5BFC\u51FA\u65F6\u95F4\u8303\u56F4\uFF1A", M.timeLabel(result.data.time_scope.range_start), " \u2192 ", M.timeLabel(result.data.time_scope.range_end), "\uFF08\u4E0D\u542B\u7ED3\u675F\u65F6\u523B\uFF09"), /*#__PURE__*/React.createElement("p", null, "\u5171 ", result.data.task_count, " \u9053\u5DE5\u5E8F\u5B89\u6392\uFF0C\u6309\u5F53\u524D\u8BFB\u53D6\u7684\u8BA1\u5212\u5185\u5BB9\u5BFC\u51FA\u3002CSV \u4E3A\u5DE5\u5E8F\u5B89\u6392\u8868\uFF0CXLSX \u53E6\u542B\u8BA1\u5212\u5206\u6790\u8868\u3002"), query.trim() && /*#__PURE__*/React.createElement("p", {
      className: "plan-danger"
    }, "\u641C\u7D22\u201C", query, "\u201D\u627E\u5230 ", matched, " \u9053\u5B89\u6392\uFF0C\u53EA\u5F71\u54CD\u7518\u7279\u56FE\u663E\u793A\u3002\u672C\u6B21\u5BFC\u51FA\u4ECD\u5305\u542B\u6B64\u65F6\u95F4\u8303\u56F4\u5185\u7684\u5168\u90E8 ", result.data.task_count, " \u9053\u5B89\u6392\uFF0C\u4E0D\u662F\u641C\u7D22\u7ED3\u679C\u3002"), /*#__PURE__*/React.createElement("p", {
      className: "plan-muted"
    }, "\u5F53\u524D\u8BFB\u53D6\u7684\u8BA1\u5212\u5185\u5BB9\u65E0\u6CD5\u6838\u5BF9\u65F6\u4F1A\u505C\u6B62\u4E0B\u8F7D\uFF0C\u8BF7\u5237\u65B0\u540E\u91CD\u65B0\u786E\u8BA4\u5BFC\u51FA\uFF1B\u4E0D\u4F1A\u81EA\u52A8\u66F4\u6362\u8BA1\u5212\u6216\u7EE7\u7EED\u4E0B\u8F7D\u3002"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }))));
  }
  window.PlanExportUI = PlanExportUI;
})();
