(function () {
  'use strict';

  const C = window.APSResourceContract,
    P = window.APSWorkPeriods,
    S = window.APSResourceSession;
  const {
    Button,
    ErrorBox,
    Modal
  } = window.ResourceControls;
  function CalendarDefaultsDialog({
    adapter,
    command,
    onClose,
    refreshState,
    onRefresh
  }) {
    const request = S.useQuery(async signal => {
      const result = await adapter.query('/api/workbench/v1/calendar/defaults', {}, signal),
        data = result.data;
      if (!data || !Array.isArray(data.periods) || !data.periods.length || P.validate(data.periods) || !Number.isFinite(data.hours) || !data.write_context) throw C.failure('默认工作时间读取不完整，请刷新后重试。');
      return result;
    }, [adapter]);
    const [base, setBase] = React.useState(null),
      [periods, setPeriods] = React.useState(null),
      [error, setError] = React.useState(null);
    const discarded = React.useRef(null);
    const formId = React.useId(),
      done = command.phase === 'done',
      disabled = command.locked || done || request.loading;
    React.useEffect(() => {
      if (!base && request.result && request.result !== discarded.current && !request.loading) {
        setBase(request.result);
        setPeriods(P.clone(request.result.data.periods));
      }
    }, [request.result, request.loading, base]);
    const owner = window.WorkbenchGuards.useDirtyGuard({
      owner: 'calendar-defaults-' + formId,
      dirty: !done && !!base && JSON.stringify(periods) !== JSON.stringify(base.data.periods),
      locked: command.locked,
      message: '默认工作时间有尚未保存的修改。'
    });
    async function close() {
      if (!command.locked && (await window.WorkbenchGuards.confirmLeave({
        owner
      }))) onClose();
    }
    const reason = !base ? '请先读取默认工作时间。' : C.blocked(base.data.write_context, 'calendar', 'defaults', base.meta.source);
    async function save(event) {
      event.preventDefault();
      if (disabled || reason) return;
      const issue = P.validate(periods) || (!periods.length ? '至少填写一个工作时段。' : '');
      if (issue) {
        setError(C.failure(issue));
        return;
      }
      setError(null);
      await command.submit('calendar', 'defaults', 'calendar-defaults', base.data.write_context, {
        periods: P.clone(periods)
      });
    }
    function reload() {
      if (!command.reset()) return;
      discarded.current = request.result;
      setBase(null);
      setPeriods(null);
      setError(null);
      request.reload();
    }
    return /*#__PURE__*/React.createElement(Modal, {
      title: "\u4FEE\u6539\u9ED8\u8BA4\u5DE5\u4F5C\u65F6\u95F4",
      icon: "calendar-days",
      onClose: close,
      guardOwner: owner,
      locked: command.locked,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        disabled: command.locked,
        onClick: close
      }, done ? '关闭' : '取消'), !done && /*#__PURE__*/React.createElement(Button, {
        type: "submit",
        form: formId,
        className: "btn primary",
        disabled: disabled,
        reason: reason
      }, "\u4FDD\u5B58\u9ED8\u8BA4\u5DE5\u4F5C\u65F6\u95F4"))
    }, /*#__PURE__*/React.createElement("form", {
      id: formId,
      className: "modal-b form scroll",
      onSubmit: save,
      noValidate: true
    }, /*#__PURE__*/React.createElement("p", null, "\u4FDD\u5B58\u540E\uFF0C\u6240\u6709\u672A\u5355\u72EC\u8BBE\u7F6E\u7684\u5DE5\u4F5C\u65E5\u4F7F\u7528\u8FD9\u4E9B\u65F6\u6BB5\uFF1B\u5DF2\u6709\u5355\u65E5\u73ED\u8868\u548C\u4E2A\u4EBA\u73ED\u8868\u6309\u5404\u81EA\u8BBE\u7F6E\u6267\u884C\uFF0C\u5468\u672B\u9ED8\u8BA4\u4F11\u606F\u3002"), periods && /*#__PURE__*/React.createElement(window.WorkPeriodFields, {
      value: periods,
      onChange: setPeriods,
      disabled: disabled,
      label: "\u9ED8\u8BA4\u5DE5\u4F5C\u65F6\u6BB5"
    }), request.loading && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u9ED8\u8BA4\u5DE5\u4F5C\u65F6\u95F4\u2026"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: request.error || error
    }), /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: command
    }), !done && (request.error || command.phase === 'rejected') && /*#__PURE__*/React.createElement(Button, {
      disabled: command.locked,
      icon: "refresh-cw",
      onClick: reload
    }, "\u91C7\u7528\u6700\u65B0\u8BBE\u7F6E\uFF0C\u91CD\u65B0\u586B\u5199"), done && /*#__PURE__*/React.createElement(window.CalendarFields.RefreshResult, {
      state: refreshState,
      onRefresh: onRefresh
    })));
  }
  window.CalendarDefaultsDialog = CalendarDefaultsDialog;
})();
