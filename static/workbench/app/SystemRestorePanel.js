(function () {
  'use strict';

  const C = window.SystemMaintenanceControls,
    R = window.SystemRestoreStatus;
  function Styles() {
    return null;
  }
  function Panel({
    command,
    api,
    theme,
    onSetTheme
  }) {
    const {
      host,
      intent
    } = command;
    const original = intent && intent.request_key || host && host.request_key || '';
    const [reference, setReference] = React.useState(original),
      [kind, setKind] = React.useState('request');
    const [query, setQuery] = React.useState(null),
      [error, setError] = React.useState(null),
      [busy, setBusy] = React.useState(false),
      [notice, setNotice] = React.useState('');
    const screen = React.useRef(null),
      controller = React.useRef(null);
    React.useEffect(() => {
      if (!reference && original) setReference(original);
    }, [original]);
    React.useLayoutEffect(() => {
      const root = document.getElementById('root'),
        previous = root && root.inert,
        focus = document.activeElement;
      const savedURL = location.href,
        savedState = history.state;
      const stay = event => {
        event.stopImmediatePropagation();
        history.replaceState(savedState, '', savedURL);
      };
      if (root) root.inert = true;
      screen.current.focus();
      window.addEventListener('popstate', stay, true);
      return () => {
        if (root) root.inert = previous;
        window.removeEventListener('popstate', stay, true);
        if (controller.current) controller.current.abort();
        if (focus && focus.isConnected) focus.focus();
      };
    }, []);
    const result = query ? query.result : command.result;
    const op = result && result.kind === 'file_operation' ? result.operation : null;
    const description = R.describe(command.hostError ? null : host, op),
      waiting = busy || command.busy || command.hostBusy;
    const problem = error || command.hostError || command.storageError || command.error;
    async function lookup(event) {
      event.preventDefault();
      if (waiting) return;
      setBusy(true);
      setError(null);
      setNotice('');
      setQuery({
        reference,
        kind,
        result: null
      });
      controller.current = new AbortController();
      try {
        const value = await api.lookupReference(reference.trim(), kind, controller.current.signal);
        setQuery({
          reference: reference.trim(),
          kind,
          result: value
        });
      } catch (problem) {
        if (problem.name !== 'AbortError') setError(problem);
      } finally {
        await command.inspectHost();
        setBusy(false);
      }
    }
    const fields = [['结果来源', '来自本机数据库以外的维护记录，不是数据库里的业务结果'], ['该次维护记录的数据库来源', description.origin], ['选定备份', op && op.filename || (!query && command.selection ? command.selection.filename + '（页面上选的，还没有确认）' : '维护记录尚未确认')], ['恢复前保护副本', op && op.protection_filename || '保护副本状态待确认'], ['业务审计', op && op.audit_persisted ? '维护记录报告已留存；当前数据库内容仍需重启后读取' : '未确认留存'], ['软件状态', command.hostError || !host ? '无法读取维护状态，当前页面已暂停业务读写' : host.restart_required ? '业务操作已停用，须重启整个软件' : '维护状态还没有确认，当前页面已暂停业务读写']];
    return ReactDOM.createPortal(/*#__PURE__*/React.createElement("div", {
      className: "sm-workbench sm-maintenance-workspace plana sm-restore-screen",
      "data-restore-maintenance": "warm",
      ref: screen,
      tabIndex: -1
    }, /*#__PURE__*/React.createElement(Styles, null), /*#__PURE__*/React.createElement(C.Styles, null), /*#__PURE__*/React.createElement("header", {
      className: "sm-restore-bar"
    }, /*#__PURE__*/React.createElement("strong", null, "APS \u667A\u80FD\u6392\u4EA7 \xB7 \u7CFB\u7EDF\u7EF4\u62A4"), /*#__PURE__*/React.createElement("fieldset", {
      className: "sm-choice"
    }, /*#__PURE__*/React.createElement("legend", null, "\u4E3B\u9898"), [['light', '浅色'], ['dark', '深色']].map(([value, label]) => /*#__PURE__*/React.createElement("label", {
      key: value
    }, /*#__PURE__*/React.createElement("input", {
      type: "radio",
      name: "restore-theme",
      checked: theme === value,
      onChange: () => onSetTheme(value)
    }), label)))), /*#__PURE__*/React.createElement("main", {
      className: "sm-restore-content"
    }, /*#__PURE__*/React.createElement("h1", null, command.hostError ? '无法读取维护状态' : description.title), /*#__PURE__*/React.createElement("p", {
      className: "sm-meta"
    }, "\u7EF4\u62A4\u72B6\u6001"), /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u7EF4\u62A4\u7ED3\u679C"
    }, /*#__PURE__*/React.createElement("h2", {
      className: op && op.state === 'succeeded' && !description.uncertain ? 'sm-tone-success' : 'sm-tone-warning'
    }, description.state), /*#__PURE__*/React.createElement("p", {
      className: "sm-notice"
    }, description.guidance), /*#__PURE__*/React.createElement(C.ErrorBox, {
      error: problem
    }), waiting && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u67E5\u8BE2\u7EF4\u62A4\u72B6\u6001\uFF0C\u6CA1\u6709\u91CD\u65B0\u63D0\u4EA4\u6062\u590D\u3002"), notice && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, notice), op && /*#__PURE__*/React.createElement("p", null, op.message), result && result.kind === 'not_recorded' && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, result.message, " \u8BF7\u67E5\u8BE2\u7ED3\u679C\uFF0C\u52FF\u91CD\u590D\u63D0\u4EA4\u3002"), /*#__PURE__*/React.createElement("dl", {
      className: "sm-restore-facts"
    }, fields.map(([label, value]) => /*#__PURE__*/React.createElement("div", {
      key: label
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, value)))), original ? /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      label: "\u672C\u673A\u4FDD\u7559\u7684\u64CD\u4F5C\u7F16\u53F7",
      value: original
    }) : /*#__PURE__*/React.createElement("p", {
      className: "sm-meta"
    }, "\u6CA1\u6709\u8BFB\u5230\u64CD\u4F5C\u7F16\u53F7\uFF0C\u53EF\u4EE5\u5728\u4E0B\u9762\u8F93\u5165\u3002"), op && (!host || host.request_key !== op.request_key) && /*#__PURE__*/React.createElement("p", {
      className: "sm-note"
    }, "\u5F53\u524D\u663E\u793A\u5386\u53F2\u7EF4\u62A4\u8BB0\u5F55\uFF1B\u8F6F\u4EF6\u4ECD\u5904\u4E8E\u7EF4\u62A4\u505C\u6B62\u72B6\u6001\u3002"), op && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      label: "\u8FD9\u6761\u7ED3\u679C\u7684\u64CD\u4F5C\u7F16\u53F7",
      value: op.request_key
    }), /*#__PURE__*/React.createElement("p", {
      className: "sm-meta"
    }, "\u66F4\u65B0\u65F6\u95F4 ", window.WorkbenchFormat.dateTime(op.updated_at))), /*#__PURE__*/React.createElement("div", {
      className: "sm-actions"
    }, /*#__PURE__*/React.createElement(C.Button, {
      icon: "refresh-cw",
      busy: waiting,
      onClick: () => {
        setQuery(null);
        setError(null);
        intent ? command.lookup() : command.inspectHost();
      }
    }, window.WorkbenchTerms.actions.query_result), /*#__PURE__*/React.createElement(C.Button, {
      transfer: "export",
      onClick: () => {
        try {
          R.download(host, result, problem);
          setNotice('已导出本次维护诊断，不含数据库或完整业务日志。');
        } catch (problem) {
          setError(problem);
        }
      }
    }, "\u5BFC\u51FA\u7EF4\u62A4\u8BCA\u65AD"), /*#__PURE__*/React.createElement("a", {
      href: "/workbench?view=system"
    }, "\u8FD4\u56DE\u5DE5\u4F5C\u53F0")), /*#__PURE__*/React.createElement("p", {
      className: "sm-meta"
    }, "\u70B9\u300C\u8FD4\u56DE\u5DE5\u4F5C\u53F0\u300D\u4F1A\u91CD\u65B0\u67E5\u8BE2\u7EF4\u62A4\u72B6\u6001\uFF1B\u9700\u8981\u91CD\u542F\u6216\u4EBA\u5DE5\u6838\u5BF9\u65F6\u4ECD\u7136\u505C\u5728\u7EF4\u62A4\u9875\u3002")), /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u6309\u7F16\u53F7\u67E5\u8BE2"
    }, /*#__PURE__*/React.createElement("h2", null, "\u67E5\u8BE2\u5176\u4ED6\u7EF4\u62A4\u7ED3\u679C"), /*#__PURE__*/React.createElement("form", {
      onSubmit: lookup
    }, /*#__PURE__*/React.createElement("fieldset", {
      className: "sm-choice",
      style: {
        marginTop: 12
      }
    }, /*#__PURE__*/React.createElement("legend", null, "\u7F16\u53F7\u7C7B\u578B"), [['request', '操作编号'], ['job', '维护记录编号']].map(([value, label]) => /*#__PURE__*/React.createElement("label", {
      key: value
    }, /*#__PURE__*/React.createElement("input", {
      type: "radio",
      name: "restore-reference-kind",
      checked: kind === value,
      onChange: () => setKind(value)
    }), label))), /*#__PURE__*/React.createElement("div", {
      className: "sm-restore-query"
    }, /*#__PURE__*/React.createElement("label", {
      className: "sm-field"
    }, /*#__PURE__*/React.createElement("span", null, kind === 'request' ? '操作编号' : '维护记录编号'), /*#__PURE__*/React.createElement("input", {
      "aria-label": "\u67E5\u8BE2\u7F16\u53F7",
      value: reference,
      maxLength: 128,
      autoComplete: "off",
      spellCheck: false,
      onChange: event => setReference(event.target.value)
    })), /*#__PURE__*/React.createElement(C.Button, {
      icon: "search",
      type: "submit",
      busy: waiting,
      disabled: !reference.trim()
    }, "\u67E5\u8BE2\u7EF4\u62A4\u7ED3\u679C")))), op && /*#__PURE__*/React.createElement("details", {
      className: "sm-rules"
    }, /*#__PURE__*/React.createElement("summary", null, "\u7EF4\u62A4\u9636\u6BB5\u4E0E\u6838\u5BF9\u4FE1\u606F"), /*#__PURE__*/React.createElement("p", null, "\u7EF4\u62A4\u8BB0\u5F55\u7F16\u53F7\uFF1A", /*#__PURE__*/React.createElement("code", null, op.job_ref), " \xB7 \u7ED3\u679C\u4EE3\u7801\uFF1A", /*#__PURE__*/React.createElement("code", null, op.code)), op.history.map((step, index) => /*#__PURE__*/React.createElement("p", {
      key: index
    }, window.WorkbenchFormat.dateTime(step.time), " \xB7 ", R.labels[step.state])), [['所选备份 SHA-256', op.target_sha256], ['保护副本 SHA-256', op.protection_sha256], ['维护结束数据库 SHA-256', op.database_after_sha256]].map(([label, value]) => /*#__PURE__*/React.createElement("p", {
      key: label
    }, label, "\uFF1A", /*#__PURE__*/React.createElement("code", null, value || '未确认'))), /*#__PURE__*/React.createElement("p", null, "\u4E0A\u9762\u7684\u6307\u7EB9\u6765\u81EA\u7EF4\u62A4\u8BB0\u5F55\uFF0C\u672C\u9875\u6CA1\u6709\u91CD\u65B0\u6253\u5F00\u6216\u68C0\u67E5\u6570\u636E\u5E93\u3002\u6570\u636E\u5E93\u91CC\u65E7\u7684\u7ED3\u679C\u53EF\u80FD\u5DF2\u88AB\u6062\u590D\u8986\u76D6\u3002")))), document.body);
  }
  window.SystemRestorePanel = Panel;
})();
