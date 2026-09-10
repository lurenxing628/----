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
      C.check(normalized(draft.reason), '请填写独立重开原因。');
      return {
        reason: draft.reason.trim()
      };
    }
    const input = {
      target_status: draft.target_status,
      ...Object.fromEntries(C.fields.filter(k => k !== 'evidence_ref').map(k => [k, normalized(draft[k])]))
    };
    if (input.completed_at && /^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(input.completed_at)) input.completed_at += ':00';
    C.check(input.remark, '请填写原因和本次核实备注。');
    if (input.target_status !== 'new') C.check(input.owner && input.deadline && input.action, '请填写责任人、期限和处置行动。');
    if (input.target_status === 'closed') C.check(input.completed_at && input.completion_evidence && input.evidence_reference_text, '关闭须填写完成时间、具体结果和可核对凭据。');
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
    }, s.phase === 'confirmed' ? '已确认：' + (s.receipt.result === 'unchanged' ? '无变化，未重复增加历史。' : '处置与历史已保存。') : s.phase === 'rejected' ? '本次明确未写入。' : '结果尚未确认，仅查询原请求。'), /*#__PURE__*/React.createElement("p", null, s.subject), /*#__PURE__*/React.createElement("div", {
      className: "dy-evidence"
    }, /*#__PURE__*/React.createElement("p", null, "\u539F\u8BF7\u6C42 ", s.request_key), s.phase === 'confirmed' && /*#__PURE__*/React.createElement("p", null, "\u56DE\u6267 ", s.receipt.receipt_ref)), /*#__PURE__*/React.createElement(P.Facts, {
      handling: s.phase === 'confirmed' ? s.receipt.data.handling : C.expected(s)
    }), s.phase === 'pending' ? /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      busy: command.busy,
      onClick: command.lookup
    }, "\u67E5\u8BE2\u539F\u56DE\u6267") : /*#__PURE__*/React.createElement(Button, {
      icon: "check",
      onClick: onFinish
    }, "\u5B8C\u6210\u6838\u5B9E\u5E76\u5237\u65B0"));
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
    const disabledReason = !context || context.capabilities[action] !== true ? '没有有效处置能力，请明确刷新条目。' : '';
    return /*#__PURE__*/React.createElement(Modal, {
      title: saved ? '处置请求核实' : reopen ? '独立重开处置' : '登记条目处置',
      icon: reopen ? 'refresh-cw' : 'square-pen',
      locked: command.busy,
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: onClose,
        disabled: command.busy
      }, saved && saved.phase === 'pending' ? '关闭并保留请求' : '关闭窗口'), !saved && /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        className: "btn primary",
        busy: command.busy,
        reason: disabledReason || (command.storageError ? '恢复记录尚未核实' : ''),
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
    }, "\u91CD\u5F00\u540E\u8F6C\u4E3A\u8DDF\u8FDB\u4E2D\uFF0C\u672C\u8F6E\u5B8C\u6210\u5B57\u6BB5\u6E05\u7A7A\uFF1B\u65E7\u5B8C\u6210\u65F6\u95F4\u3001\u7ED3\u679C\u548C\u51ED\u636E\u4FDD\u7559\u5728\u5386\u53F2\u3002"), /*#__PURE__*/React.createElement("label", {
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
    })))), /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, "\u51ED\u636E\u6587\u5B57\u5C1A\u672A\u6838\u9A8C\u4E3A\u9644\u4EF6\u3002\u5904\u7F6E\u72B6\u6001\u4E0D\u6539\u62A5\u5DE5\u4E8B\u5B9E\uFF0C\u5173\u95ED\u4E0D\u5220\u9664\u98CE\u9669\u3002"))));
  }
  window.DashboardHandling = Handling;
})();
