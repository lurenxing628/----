(function () {
  'use strict';

  const C = window.APSResourceContract,
    K = window.APSCalendarContract;
  const {
    Button,
    ErrorBox,
    Modal,
    focusFirstInvalid
  } = window.ResourceControls;
  const {
    Fields,
    Policy,
    RefreshResult
  } = window.CalendarFields;
  const Feedback = window.ResourceForms.Feedback;
  function CalendarDayDialog({
    adapter,
    day,
    source,
    command,
    onClose,
    refreshState,
    onRefresh
  }) {
    const [base, setBase] = React.useState(day),
      [value, setValue] = React.useState(() => K.draft(day));
    const [error, setError] = React.useState(null),
      [review, setReview] = React.useState(null),
      [reading, setReading] = React.useState(false);
    const [clearing, setClearing] = React.useState(false),
      [readError, setReadError] = React.useState(null);
    const original = React.useRef(day),
      mounted = React.useRef(true),
      controller = React.useRef(null),
      formRef = React.useRef(null),
      formId = React.useId();
    React.useEffect(() => {
      mounted.current = true;
      return () => {
        mounted.current = false;
        if (controller.current) controller.current.abort();
      };
    }, []);
    const done = command.phase === 'done',
      disabled = command.locked || done || reading;
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({
      owner: 'calendar-day-' + formId,
      dirty: !done && JSON.stringify(value) !== JSON.stringify(K.draft(original.current)),
      locked: command.locked,
      message: '工作日历有尚未保存的修改。'
    });
    async function close() {
      if (!command.locked && !reading && (await window.WorkbenchGuards.confirmLeave({
        owner: guardOwner
      }))) onClose();
    }
    React.useEffect(() => {
      if (error || command.error) focusFirstInvalid(formRef.current);
    }, [error, command.error]);
    const reason = K.stale(command) ? '资料已变化，请重新读取并核对。' : review ? '请先核对最新资料。' : C.blocked(base.write_context, 'calendar', clearing ? 'delete' : 'upsert', source);
    async function reloadContext() {
      if (disabled) return;
      setReading(true);
      setReadError(null);
      setReview(null);
      controller.current = new AbortController();
      try {
        const year = Number(base.date.slice(0, 4)),
          month = Number(base.date.slice(5, 7));
        const result = K.month(await adapter.query(K.path + '/month', {
          year,
          month
        }, controller.current.signal), year, month);
        if (mounted.current) setReview({
          day: result.data.days.find(row => row.date === base.date),
          source: result.meta.source
        });
      } catch (failure) {
        if (mounted.current) setReadError(failure);
      } finally {
        if (mounted.current) setReading(false);
      }
    }
    async function save(event) {
      event.preventDefault();
      if (disabled || reason) return;
      try {
        const input = clearing ? {
          date: base.date
        } : {
          date: base.date,
          fields: K.input(value, original.current)
        };
        setError(null);
        await command.submit('calendar', clearing ? 'delete' : 'upsert', base.date, base.write_context, input);
      } catch (failure) {
        setError(failure);
      }
    }
    function accept() {
      if (!review || review.source !== 'production' || !command.reset()) return;
      const previous = K.draft(original.current),
        merged = K.draft(review.day);
      Object.keys(previous).forEach(key => {
        if (value[key] !== previous[key]) merged[key] = value[key];
      });
      original.current = review.day;
      setValue(merged);
      setBase(review.day);
      setReview(null);
      setReadError(null);
      setError(null);
    }
    return /*#__PURE__*/React.createElement(Modal, {
      title: base.date + ' · 工作日历',
      icon: "calendar-days",
      onClose: onClose,
      guardOwner: guardOwner,
      locked: command.locked || reading,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        disabled: command.locked || reading,
        onClick: close
      }, done ? '关闭' : '取消'), !done && !clearing && base.explicit && /*#__PURE__*/React.createElement(Button, {
        icon: "minus",
        disabled: disabled || !!review,
        onClick: () => setClearing(true)
      }, "\u6E05\u9664\u914D\u7F6E"), !done && clearing && /*#__PURE__*/React.createElement(Button, {
        disabled: disabled,
        onClick: () => setClearing(false)
      }, "\u8FD4\u56DE\u7F16\u8F91"), !done && /*#__PURE__*/React.createElement(Button, {
        type: "submit",
        form: formId,
        className: "btn primary",
        icon: clearing ? 'minus' : 'check',
        busy: disabled,
        reason: reason
      }, clearing ? '确认清除，恢复默认' : '保存配置'))
    }, /*#__PURE__*/React.createElement("form", {
      id: formId,
      ref: formRef,
      className: "modal-b form scroll",
      onSubmit: save,
      noValidate: true
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        borderBottom: '1px solid var(--ui-border)',
        paddingBottom: 12,
        marginBottom: 16
      }
    }, /*#__PURE__*/React.createElement(Policy, {
      value: base
    })), clearing ? /*#__PURE__*/React.createElement("p", null, "\u5C06\u6E05\u9664 ", /*#__PURE__*/React.createElement("b", null, base.date), " \u7684\u5168\u5C40\u65E5\u5386\u914D\u7F6E\uFF0C\u6539\u7528\u8BE5\u65E5\u671F\u7684\u9ED8\u8BA4\u89C4\u5219\u3002\u4EBA\u5458\u4E13\u5C5E\u65E5\u5386\u548C\u73ED\u6B21\u4E0D\u53D8\u3002") : /*#__PURE__*/React.createElement(Fields, {
      value: value,
      error: error || command.error,
      showSummary: false,
      disabled: disabled,
      onChange: next => {
        setValue(next);
        setError(null);
      }
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error,
      excludePaths: clearing ? [] : window.CalendarFields.fieldPaths
    }), /*#__PURE__*/React.createElement(Feedback, {
      command: command,
      excludePaths: clearing ? [] : window.CalendarFields.fieldPaths
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: readError
    }), !done && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      busy: reading,
      disabled: command.locked,
      onClick: reloadContext
    }, "\u91CD\u65B0\u8BFB\u53D6\u6700\u65B0\u8D44\u6599"), review && /*#__PURE__*/React.createElement("div", {
      className: "match-note",
      style: {
        display: 'block'
      }
    }, /*#__PURE__*/React.createElement("p", null, "\u6700\u65B0\u8D44\u6599\u5DF2\u8BFB\u53D6\uFF0C\u5DF2\u586B\u5199\u7684\u5185\u5BB9\u4FDD\u6301\u4E0D\u53D8\u3002\u8BF7\u6838\u5BF9\u540E\u7EE7\u7EED\u7F16\u8F91\u3002"), /*#__PURE__*/React.createElement(Policy, {
      value: review.day
    }), /*#__PURE__*/React.createElement(Button, {
      disabled: disabled,
      reason: C.blocked(review.day.write_context, 'calendar', clearing ? 'delete' : 'upsert', review.source),
      onClick: accept
    }, "\u5DF2\u6838\u5BF9\uFF0C\u7EE7\u7EED\u7F16\u8F91")), reason && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, reason), done && /*#__PURE__*/React.createElement(RefreshResult, {
      state: refreshState,
      onRefresh: onRefresh
    })));
  }
  window.CalendarDayDialog = CalendarDayDialog;
})();
