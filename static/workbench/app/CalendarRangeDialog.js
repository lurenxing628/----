(function () {
  'use strict';

  const C = window.APSResourceContract,
    K = window.APSCalendarContract;
  const {
    Button,
    ErrorBox,
    Issues,
    Modal,
    Field,
    focusFirstInvalid
  } = window.ResourceControls;
  const {
    Pager,
    EmptyState
  } = window.WorkbenchListControls;
  const {
    Fields,
    Segment,
    Policy,
    RefreshResult
  } = window.CalendarFields;
  const Feedback = window.ResourceForms.Feedback;
  function RangePreview({
    result,
    page,
    setPage,
    onBack,
    disabled
  }) {
    const data = result.data,
      size = 10,
      pages = Math.max(1, Math.ceil(data.days.length / size));
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "match-note",
      style: {
        display: 'block'
      }
    }, /*#__PURE__*/React.createElement("b", null, "\u5168\u90E8\u547D\u4E2D ", data.counts.selected, " \u5929"), " \xB7 \u53D8\u66F4 ", data.counts.changed, " \u5929 \xB7 \u4E0D\u53D8 ", data.counts.unchanged, " \u5929", /*#__PURE__*/React.createElement("div", null, data.request.start_date, " \u81F3 ", data.request.end_date, " \xB7 ", {
      all: '范围内每天',
      weekday: '仅周一至周五',
      weekend: '仅周六、周日'
    }[data.request.scope]), /*#__PURE__*/React.createElement("div", null, "\u786E\u8BA4\u4F5C\u7528\u4E8E\u5168\u90E8 ", data.counts.selected, " \u5929\uFF0C\u5305\u542B\u5176\u4ED6\u5206\u9875\u65E5\u671F\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "muted"
    }, "\u9884\u89C8\u6709\u6548\u81F3 ", window.WorkbenchFormat.dateTime(data.expires_at))), /*#__PURE__*/React.createElement(Pager, {
      page: {
        number: page,
        pages,
        total: data.days.length,
        size
      },
      sizes: [size],
      unit: "\u5929",
      label: "\u9884\u89C8",
      onPage: setPage,
      showPageSelect: true
    }), !data.days.length && /*#__PURE__*/React.createElement(EmptyState, {
      kind: "filtered",
      title: "\u5F53\u524D\u8303\u56F4\u6CA1\u6709\u547D\u4E2D\u65E5\u671F",
      hint: "\u8FD4\u56DE\u4FEE\u6539\u65E5\u671F\u8303\u56F4\u6216\u9002\u7528\u65E5\u671F\u540E\uFF0C\u518D\u9884\u89C8\u3002",
      action: /*#__PURE__*/React.createElement(Button, {
        disabled: disabled,
        onClick: onBack
      }, "\u4FEE\u6539\u65E5\u671F\u8303\u56F4")
    }), /*#__PURE__*/React.createElement("div", {
      className: "card-scroll wb-table-shell wb-table-frame cal-preview-scroll",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table cal-preview-table"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u5DE5\u4F5C\u65E5\u5386\u6279\u91CF\u7EF4\u62A4\u9884\u89C8\uFF1A\u7B2C ", page, " \u9875\uFF0C\u786E\u8BA4\u5C06\u4F5C\u7528\u4E8E\u5168\u90E8 ", data.counts.selected, " \u5929"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-key",
      style: {
        width: 105
      }
    }, "\u65E5\u671F"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u53D8\u66F4\u524D"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u53D8\u66F4\u540E"))), /*#__PURE__*/React.createElement("tbody", null, data.days.slice((page - 1) * size, page * size).map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.date
    }, /*#__PURE__*/React.createElement("td", {
      className: "wb-col-key"
    }, /*#__PURE__*/React.createElement("b", null, row.date), /*#__PURE__*/React.createElement("div", {
      className: "muted"
    }, row.changed ? '将变更' : '不变')), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Policy, {
      value: row.before
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Policy, {
      value: row.after
    }))))))));
  }
  function CalendarRangeDialog({
    adapter,
    month,
    source,
    command,
    onClose,
    refreshState,
    onRefresh
  }) {
    const [range, setRange] = React.useState({
      start_date: K.monthKey(month.year, month.month) + '-01',
      end_date: K.monthKey(month.year, month.month) + '-' + K.monthDays(month.year, month.month),
      scope: 'all',
      operation: 'upsert'
    });
    const [value, setValue] = React.useState({
      type: 'work',
      hours: '8',
      eff: '100',
      allowNormal: 'yes',
      allowUrgent: 'yes',
      note: ''
    });
    const [replaceNote, setReplaceNote] = React.useState(false);
    const [result, setResult] = React.useState(null),
      [loading, setLoading] = React.useState(false),
      [error, setError] = React.useState(null),
      [page, setPage] = React.useState(1);
    const controller = React.useRef(null),
      mounted = React.useRef(true),
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
      disabled = command.locked || done || loading;
    const original = React.useRef(JSON.stringify({
      range,
      value,
      replaceNote
    }));
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({
      owner: 'calendar-range-' + formId,
      dirty: !done && JSON.stringify({
        range,
        value,
        replaceNote
      }) !== original.current,
      locked: command.locked,
      message: '批量日历维护有尚未保存的范围或规则。'
    });
    async function close() {
      if (!command.locked && !loading && (await window.WorkbenchGuards.confirmLeave({
        owner: guardOwner
      }))) onClose();
    }
    React.useEffect(() => {
      if (error) focusFirstInvalid(formRef.current);
    }, [error]);
    const reason = K.stale(command) ? '预览已失效，请重新预览并核对全部日期。' : !result ? '请先预览全部命中日期。' : !result.data.counts.selected ? '当前范围没有命中日期。' : C.blocked(result.data.write_context, 'calendar', 'confirm', result.meta.source);
    async function preview(event) {
      if (event) event.preventDefault();
      if (disabled) return;
      try {
        if (source !== 'production') throw C.failure('当前不是生产数据，不能执行日历维护。');
        if (!K.isDate(range.start_date) || !K.isDate(range.end_date) || range.start_date > range.end_date) throw C.failure('请选择正确的开始和结束日期。', [{
          path: !K.isDate(range.start_date) ? 'start_date' : 'end_date',
          message: '日期须有效，且结束日期不能早于开始日期。'
        }]);
        const fields = range.operation === 'delete' ? {} : K.input(value);
        if (!replaceNote) delete fields.note;
        if (!command.reset()) return;
        setError(null);
        setResult(null);
        setLoading(true);
        controller.current = new AbortController();
        const next = K.preview(await adapter.preview(K.path + '/range/preview', {
          input: {
            ...range,
            fields
          }
        }, controller.current.signal));
        if (mounted.current) {
          setResult(next);
          setPage(1);
        }
      } catch (failure) {
        if (mounted.current) setError(failure);
      } finally {
        if (mounted.current) setLoading(false);
      }
    }
    function back() {
      if (!disabled && command.reset()) {
        setResult(null);
        setError(null);
      }
    }
    return /*#__PURE__*/React.createElement("div", {
      className: 'calendar-range-dialog' + (result ? ' is-preview' : '')
    }, /*#__PURE__*/React.createElement(Modal, {
      title: "\u6279\u91CF\u7EF4\u62A4\u5DE5\u4F5C\u65E5\u5386",
      icon: "calendar-days",
      onClose: onClose,
      guardOwner: guardOwner,
      locked: command.locked || loading,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        disabled: command.locked || loading,
        onClick: close
      }, done ? '关闭' : '取消'), !done && result && /*#__PURE__*/React.createElement(Button, {
        disabled: disabled,
        onClick: back
      }, "\u8FD4\u56DE\u4FEE\u6539\u8303\u56F4"), !done && (!result || K.stale(command)) && /*#__PURE__*/React.createElement(Button, {
        type: "submit",
        form: formId,
        icon: "list-checks",
        className: "btn primary",
        busy: disabled
      }, K.stale(command) ? '重新预览' : '预览全部日期'), !done && result && /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        className: "btn primary",
        busy: disabled,
        reason: reason,
        onClick: () => command.submit('calendar', 'confirm', result.data.preview_ref, result.data.write_context, {
          preview_ref: result.data.preview_ref
        })
      }, "\u786E\u8BA4\u5168\u90E8 ", result.data.counts.selected, " \u5929"))
    }, /*#__PURE__*/React.createElement("form", {
      id: formId,
      ref: formRef,
      className: "modal-b form scroll",
      onSubmit: preview,
      noValidate: true
    }, !result && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "fgrid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u5F00\u59CB\u65E5\u671F",
      path: "start_date",
      error: error,
      required: true
    }, /*#__PURE__*/React.createElement("input", {
      id: formId + '-from',
      type: "date",
      value: range.start_date,
      disabled: disabled,
      onChange: event => {
        setRange({
          ...range,
          start_date: event.target.value
        });
        setError(null);
      }
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u7ED3\u675F\u65E5\u671F",
      path: "end_date",
      error: error,
      required: true
    }, /*#__PURE__*/React.createElement("input", {
      id: formId + '-to',
      type: "date",
      value: range.end_date,
      disabled: disabled,
      onChange: event => {
        setRange({
          ...range,
          end_date: event.target.value
        });
        setError(null);
      }
    }))), /*#__PURE__*/React.createElement(Button, {
      disabled: disabled,
      icon: "calendar-days",
      onClick: () => setRange({
        ...range,
        start_date: K.monthKey(month.year, month.month) + '-01',
        end_date: K.monthKey(month.year, month.month) + '-' + K.monthDays(month.year, month.month)
      })
    }, "\u5F53\u524D\u6574\u6708"), /*#__PURE__*/React.createElement(Segment, {
      label: "\u5E94\u7528\u5230",
      value: range.scope,
      disabled: disabled,
      options: [["all", "范围内每天"], ["weekday", "仅周一至周五"], ["weekend", "仅周六、周日"]],
      onChange: scope => setRange({
        ...range,
        scope
      })
    }), /*#__PURE__*/React.createElement(Segment, {
      label: "\u7EF4\u62A4\u65B9\u5F0F",
      value: range.operation,
      disabled: disabled,
      options: [["upsert", "设置日历"], ["delete", "清除配置，恢复默认"]],
      onChange: operation => setRange({
        ...range,
        operation
      })
    }), range.operation === 'upsert' ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("label", {
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        margin: '12px 0'
      }
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: replaceNote,
      disabled: disabled,
      style: {
        width: 15,
        height: 15
      },
      onChange: event => setReplaceNote(event.target.checked)
    }), "\u540C\u65F6\u66FF\u6362\u5907\u6CE8\uFF08\u7559\u7A7A\u5373\u6E05\u9664\uFF09"), /*#__PURE__*/React.createElement(Fields, {
      value: value,
      error: error,
      showSummary: false,
      onChange: next => {
        setValue(next);
        setError(null);
      },
      disabled: disabled,
      noteEnabled: replaceNote
    })) : /*#__PURE__*/React.createElement("p", null, "\u6E05\u9664\u8303\u56F4\u5185\u547D\u4E2D\u65E5\u671F\u7684\u5168\u5C40\u65E5\u5386\u914D\u7F6E\uFF0C\u6062\u590D\u9ED8\u8BA4\u89C4\u5219\u3002\u4EBA\u5458\u4E13\u5C5E\u65E5\u5386\u548C\u73ED\u6B21\u4E0D\u53D8\u3002")), loading && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u5168\u90E8\u547D\u4E2D\u65E5\u671F\u5E76\u8BA1\u7B97\u53D8\u66F4\u524D\u540E\u914D\u7F6E\u2026"), result && /*#__PURE__*/React.createElement(RangePreview, {
      result: result,
      page: page,
      setPage: setPage,
      onBack: back,
      disabled: disabled
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error,
      excludePaths: result ? [] : ['start_date', 'end_date'].concat(range.operation === 'upsert' ? window.CalendarFields.fieldPaths : [])
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: result && result.warnings || []
    }), /*#__PURE__*/React.createElement(Feedback, {
      command: command
    }), done && /*#__PURE__*/React.createElement(RefreshResult, {
      state: refreshState,
      onRefresh: onRefresh
    }))));
  }
  window.CalendarRangeDialog = CalendarRangeDialog;
})();
