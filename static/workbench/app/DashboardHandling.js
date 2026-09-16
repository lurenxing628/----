(function () {
  'use strict';

  const C = window.DashboardContract,
    P = window.DashboardPanels,
    {
      Button,
      Modal,
      ErrorBox
    } = window.ResourceControls;
  function draftFor(item) {
    return {
      target_status: item.handling.status,
      ...Object.fromEntries(C.fields.filter(k => k !== 'evidence_ref').map(k => [k, item.handling[k] || ''])),
      reason: ''
    };
  }
  function inputFor(draft, reopen) {
    const normalized = text => text.trim() || null;
    if (reopen) {
      C.check(normalized(draft.reason), '请填写重开原因。');
      return {
        reason: draft.reason.trim()
      };
    }
    const input = {
      target_status: draft.target_status,
      ...Object.fromEntries(C.fields.filter(k => k !== 'evidence_ref').map(k => [k, normalized(draft[k])]))
    };
    if (input.completed_at && /^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(input.completed_at)) input.completed_at += ':00';
    C.check(input.remark, '请填写原因说明。');
    if (input.target_status !== 'new') C.check(input.owner && input.deadline && input.action, '请填写责任人、期限和处置行动。');
    if (input.target_status === 'closed') C.check(input.completed_at && input.completion_evidence && input.evidence_reference_text, '关闭前请填写完成时间、具体完成结果和可核对凭据。');
    return input;
  }
  function Receipt({
    command,
    onFinish
  }) {
    const s = command.saved;
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: 'dy-note ' + (s.phase === 'confirmed' ? 'success' : 'warning'),
      role: "status"
    }, s.phase === 'confirmed' ? window.WorkbenchTerms.outcomes.done('处置', s.receipt.result === 'unchanged' ? '内容和原来一样，没有新增历史记录' : '处置和历史都已保存') : s.phase === 'rejected' ? '上次处置没有生效，填写内容已保留。改好后重新提交。' : window.WorkbenchTerms.outcomes.pending('处置')), /*#__PURE__*/React.createElement("p", null, s.subject), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '操作编号': s.request_key,
        '结果编号': s.phase === 'confirmed' ? s.receipt.receipt_ref : null
      }
    }), /*#__PURE__*/React.createElement(P.Facts, {
      handling: s.phase === 'confirmed' ? s.receipt.data.handling : C.expected(s)
    }), s.phase === 'pending' ? /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      icon: "refresh-cw",
      busy: command.busy,
      onClick: command.lookup
    }, "\u67E5\u8BE2\u7ED3\u679C") : /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      icon: "check",
      onClick: onFinish
    }, "\u5B8C\u6210"));
  }
  function Handling({
    item,
    command,
    onClose,
    onFinish
  }) {
    const [draft, setDraft] = React.useState(() => item ? draftFor(item) : null),
      [error, setError] = React.useState(null);
    const saved = command.saved,
      reopen = item && item.handling.status === 'closed';
    const update = (k, v) => {
      setDraft(previous => ({
        ...previous,
        [k]: v
      }));
      setError(null);
    };
    async function submit() {
      try {
        const input = inputFor(draft, reopen);
        await command.submit(item, reopen ? 'reopen' : 'transition', input);
      } catch (e) {
        setError(e);
      }
    }
    const action = reopen ? 'reopen' : 'transition',
      context = item && item.write_context;
    const disabledReason = !context || context.capabilities[action] !== true ? '这条记录现在不能处置，请刷新后重试。' : '';
    return /*#__PURE__*/React.createElement(Modal, {
      title: saved ? '上次处置结果' : reopen ? '独立重开处置' : '登记条目处置',
      icon: reopen ? 'refresh-cw' : 'square-pen',
      locked: command.busy,
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        reasonDisplay: "inline",
        onClick: onClose,
        disabled: command.busy
      }, saved && saved.phase === 'pending' ? '关闭并保留这次操作' : '关闭'), !saved && /*#__PURE__*/React.createElement(Button, {
        reasonDisplay: "inline",
        icon: "check",
        className: "btn primary",
        busy: command.busy,
        reason: disabledReason || (command.storageError ? '上次操作记录还没确认' : ''),
        onClick: submit
      }, reopen ? '确认独立重开' : '提交处置'))
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-dialog-body"
    }, /*#__PURE__*/React.createElement(ErrorBox, {
      error: error || command.error || command.storageError
    }), command.notice && /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, command.notice), saved ? /*#__PURE__*/React.createElement(Receipt, {
      command: command,
      onFinish: onFinish
    }) : item && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("h3", null, item.subject), /*#__PURE__*/React.createElement("div", {
      className: "dy-tools"
    }, /*#__PURE__*/React.createElement(P.Risk, {
      risk: item.risk
    }), /*#__PURE__*/React.createElement(P.Status, {
      handling: item.handling
    })), reopen ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, "\u91CD\u5F00\u540E\u72B6\u6001\u53D8\u4E3A\u8DDF\u8FDB\u4E2D\uFF0C\u672C\u6B21\u586B\u7684\u5B8C\u6210\u5185\u5BB9\u4F1A\u6E05\u9664\u3002\u539F\u6765\u7684\u5B8C\u6210\u65F6\u95F4\u3001\u7ED3\u679C\u548C\u51ED\u636E\u90FD\u7559\u5728\u5386\u53F2\u91CC\u3002"), /*#__PURE__*/React.createElement("label", {
      className: "dy-form"
    }, "\u91CD\u5F00\u539F\u56E0", /*#__PURE__*/React.createElement("textarea", {
      "aria-label": "\u91CD\u5F00\u539F\u56E0",
      value: draft.reason,
      maxLength: 4000,
      onChange: e => update('reason', e.target.value)
    })), /*#__PURE__*/React.createElement(P.Facts, {
      handling: item.handling
    })) : /*#__PURE__*/React.createElement("form", {
      className: "dy-form",
      onSubmit: e => {
        e.preventDefault();
        submit();
      }
    }, /*#__PURE__*/React.createElement("label", null, "\u76EE\u6807\u5904\u7F6E\u72B6\u6001", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u76EE\u6807\u5904\u7F6E\u72B6\u6001",
      value: draft.target_status,
      onChange: e => update('target_status', e.target.value),
      disabled: command.busy
    }, item.allowed_transitions.map(s => /*#__PURE__*/React.createElement("option", {
      key: s,
      value: s
    }, C.statuses[s])))), /*#__PURE__*/React.createElement("label", null, "\u8D23\u4EFB\u4EBA", /*#__PURE__*/React.createElement("input", {
      "aria-label": "\u8D23\u4EFB\u4EBA",
      value: draft.owner,
      maxLength: 200,
      onChange: e => update('owner', e.target.value),
      disabled: command.busy
    })), /*#__PURE__*/React.createElement("label", null, "\u8D23\u4EFB\u671F\u9650", /*#__PURE__*/React.createElement("input", {
      "aria-label": "\u8D23\u4EFB\u671F\u9650",
      type: "date",
      value: draft.deadline,
      onChange: e => update('deadline', e.target.value),
      disabled: command.busy
    })), /*#__PURE__*/React.createElement("label", null, "\u5B8C\u6210\u65F6\u95F4", /*#__PURE__*/React.createElement("input", {
      "aria-label": "\u5B8C\u6210\u65F6\u95F4",
      type: "datetime-local",
      step: "1",
      value: draft.completed_at,
      onChange: e => update('completed_at', e.target.value),
      disabled: command.busy
    })), ['action', 'remark', 'completion_evidence', 'evidence_reference_text'].map(k => /*#__PURE__*/React.createElement("label", {
      key: k,
      className: "wide"
    }, C.labels[k], /*#__PURE__*/React.createElement("textarea", {
      "aria-label": C.labels[k],
      value: draft[k],
      maxLength: 4000,
      onChange: e => update(k, e.target.value),
      disabled: command.busy
    })))))));
  }
  window.DashboardHandling = Handling;
})();
