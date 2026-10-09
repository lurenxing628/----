(function () {
  'use strict';

  // Load after OperatorCalendarContract.js and before ResourceWorkspace.jsx，所以反馈组件由宿主注入，
  // 和 OperatorMachinePermissions.jsx 一样，不在模块级引用后加载的文件。
  const C = window.APSResourceContract,
    O = window.APSOperatorCalendar,
    S = window.APSResourceSession;
  const {
    Button,
    ErrorBox,
    Issues,
    Modal,
    Field
  } = window.ResourceControls;
  function Segment({
    label,
    value,
    options,
    disabled,
    onChange
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "rm-format"
    }, /*#__PURE__*/React.createElement("span", {
      className: "seclabel"
    }, label), /*#__PURE__*/React.createElement("div", {
      className: "seg",
      role: "group",
      "aria-label": label
    }, options.map(([key, text]) => /*#__PURE__*/React.createElement("button", {
      key: key,
      type: "button",
      disabled: disabled,
      className: value === key ? 'on' : '',
      "aria-pressed": value === key,
      onClick: () => onChange(key)
    }, text))));
  }
  function RefreshResult({
    state,
    onRefresh
  }) {
    if (state && state.error) return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(ErrorBox, {
      error: state.error
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: onRefresh
    }, "\u5237\u65B0\u4FDD\u5B58\u7ED3\u679C"));
    return /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, state && state.done ? '已刷新，显示最新个人日历。' : state && state.loading ? '正在刷新…' : '请刷新保存结果，核对个人日历。');
  }
  const PATH = ref => 'entities/operator/' + ref + '/calendar';
  function todayMonth() {
    const now = new Date();
    return {
      year: now.getFullYear(),
      month: now.getMonth() + 1
    };
  }
  function monthDays(year, month) {
    return [31, year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1];
  }
  function monthKey(year, month) {
    return String(year).padStart(4, '0') + '-' + String(month).padStart(2, '0');
  }
  function DayEditor({
    day,
    draft,
    setDraft,
    disabled,
    error,
    onSave,
    onClear,
    saveReason,
    clearReason,
    clearing,
    onClearing
  }) {
    const rest = draft.type === 'rest';
    // 上班但工作时段全部移除：能保存，但排产按 0 工时不排这个人，与全局日历同一句提醒。
    const zeroHours = !rest && Array.isArray(draft.periods) && !draft.periods.length;
    // 清除单独设置与全局日历同一套两步：先点「清除单独设置」，再点「确认清除，恢复默认」才真正提交。
    if (clearing) return /*#__PURE__*/React.createElement("div", {
      className: "iopane on"
    }, /*#__PURE__*/React.createElement("div", {
      className: "chead"
    }, /*#__PURE__*/React.createElement("h3", {
      style: {
        margin: 0
      }
    }, day.date, " \xB7 \u6E05\u9664\u5355\u72EC\u8BBE\u7F6E")), /*#__PURE__*/React.createElement("p", null, "\u5C06\u6E05\u9664 ", /*#__PURE__*/React.createElement("b", null, day.date), " \u7684\u5355\u72EC\u8BBE\u7F6E\uFF0C\u8FD9\u4E00\u5929\u6062\u590D\u6309\u73ED\u6B21\u8F6E\u6362\u6216\u5168\u5C40\u5DE5\u4F5C\u65E5\u5386\u6392\u4EA7\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "wb-actions",
      style: {
        marginTop: 12
      }
    }, /*#__PURE__*/React.createElement(Button, {
      disabled: disabled,
      onClick: () => onClearing(false)
    }, "\u8FD4\u56DE\u7F16\u8F91"), /*#__PURE__*/React.createElement(Button, {
      icon: "trash-2",
      className: "btn danger",
      disabled: disabled,
      reason: clearReason,
      onClick: onClear
    }, "\u786E\u8BA4\u6E05\u9664\uFF0C\u6062\u590D\u9ED8\u8BA4")));
    return /*#__PURE__*/React.createElement("div", {
      className: "iopane on"
    }, /*#__PURE__*/React.createElement("div", {
      className: "chead"
    }, /*#__PURE__*/React.createElement("h3", {
      style: {
        margin: 0
      }
    }, day.date, " \xB7 ", day.explicit ? '已单独设置' : '未单独设置')), /*#__PURE__*/React.createElement(Segment, {
      label: "\u8FD9\u4E00\u5929",
      value: draft.type,
      disabled: disabled,
      options: [['work', '上班'], ['rest', '休息']],
      onChange: type => setDraft(O.switchType(day, draft, type))
    }), !rest && draft.periods == null && /*#__PURE__*/React.createElement("div", {
      className: "fgrid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u73ED\u6B21\u5F00\u59CB",
      path: "fields.shiftStart",
      error: error,
      required: true
    }, /*#__PURE__*/React.createElement("input", {
      type: "time",
      value: draft.shiftStart,
      disabled: disabled,
      onChange: event => setDraft({
        ...draft,
        shiftStart: event.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u73ED\u6B21\u7ED3\u675F",
      path: "fields.shiftEnd",
      error: error
    }, /*#__PURE__*/React.createElement("input", {
      type: "time",
      value: draft.shiftEnd,
      disabled: disabled,
      onChange: event => setDraft({
        ...draft,
        shiftEnd: event.target.value
      })
    }))), !rest && /*#__PURE__*/React.createElement(window.WorkPeriodFields, {
      value: draft.periods,
      start: draft.shiftStart,
      end: draft.shiftEnd,
      disabled: disabled,
      onChange: periods => setDraft({
        ...draft,
        periods
      })
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: zeroHours ? [window.APSWorkPeriods.zeroHoursNote] : []
    }), !rest && draft.periods == null && /*#__PURE__*/React.createElement("p", {
      className: "iohint"
    }, "\u5DE5\u65F6\u7531\u73ED\u6B21\u8D77\u6B62\u7B97\u51FA\u6765\uFF0C\u4E0D\u7528\u5355\u72EC\u586B\u3002\u7ED3\u675F\u65F6\u523B\u65E9\u4E8E\u5F00\u59CB\u65F6\u523B\u8868\u793A\u8DE8\u96F6\u70B9\u7684\u591C\u73ED\u3002 \u7559\u7A7A\u7ED3\u675F\u65F6\u523B\u65F6\uFF0C\u7531\u7CFB\u7EDF\u6309\u9ED8\u8BA4\u73ED\u6B21\u65F6\u957F\u63A8\u7B97\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "fgrid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u6548\u7387\uFF08%\uFF09",
      path: "fields.eff",
      error: error,
      required: true
    }, /*#__PURE__*/React.createElement("input", {
      type: "number",
      min: "0",
      max: "200",
      step: "any",
      "data-wb-step": "5",
      value: draft.eff,
      disabled: disabled,
      onChange: event => setDraft({
        ...draft,
        eff: event.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5907\u6CE8",
      path: "fields.note",
      error: error
    }, /*#__PURE__*/React.createElement("input", {
      type: "text",
      value: draft.note,
      disabled: disabled,
      onChange: event => setDraft({
        ...draft,
        note: event.target.value
      })
    }))), !rest && /*#__PURE__*/React.createElement("div", {
      className: "fgrid"
    }, /*#__PURE__*/React.createElement(Segment, {
      label: "\u5141\u8BB8\u666E\u901A\u4EF6",
      value: draft.allowNormal,
      disabled: disabled,
      options: [['yes', '可以'], ['no', '不可以']],
      onChange: allowNormal => setDraft({
        ...draft,
        allowNormal
      })
    }), /*#__PURE__*/React.createElement(Segment, {
      label: "\u5141\u8BB8\u6025\u4EF6",
      value: draft.allowUrgent,
      disabled: disabled,
      options: [['yes', '可以'], ['no', '不可以']],
      onChange: allowUrgent => setDraft({
        ...draft,
        allowUrgent
      })
    })), rest && /*#__PURE__*/React.createElement("p", {
      className: "iohint"
    }, "\u4F11\u606F\u65E5\u4E0D\u6392\u4EA7\uFF0C\u5DE5\u65F6\u6309 0 \u8BA1\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "wb-actions",
      style: {
        marginTop: 12
      }
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "check",
      className: "btn primary",
      disabled: disabled,
      reason: saveReason,
      onClick: onSave
    }, "\u4FDD\u5B58\u8FD9\u4E00\u5929"), day.explicit && /*#__PURE__*/React.createElement(Button, {
      icon: "minus",
      disabled: disabled,
      reason: clearReason,
      onClick: () => onClearing(true)
    }, "\u6E05\u9664\u5355\u72EC\u8BBE\u7F6E")));
  }
  function RangeClear({
    range,
    setRange,
    disabled,
    error,
    preview,
    onPreview,
    onConfirm,
    reason,
    busy
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "iopane on"
    }, /*#__PURE__*/React.createElement("div", {
      className: "chead"
    }, /*#__PURE__*/React.createElement("h3", {
      style: {
        margin: 0
      }
    }, "\u6309\u65E5\u671F\u8303\u56F4\u6E05\u9664")), /*#__PURE__*/React.createElement("p", {
      className: "iohint"
    }, "\u6E05\u9664\u540E\u8FD9\u4E9B\u65E5\u671F\u6062\u590D\u6210\u6309\u73ED\u6B21\u8F6E\u6362\u6216\u5168\u5C40\u5DE5\u4F5C\u65E5\u5386\u6392\u4EA7\u3002\u6587\u4EF6\u5BFC\u5165\u4E0D\u4F1A\u5220\u9664\u4EFB\u4F55\u65E5\u671F\uFF0C \u5BFC\u9519\u4E86\u5C31\u4ECE\u8FD9\u91CC\u6279\u91CF\u6E05\u6389\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "fgrid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u5F00\u59CB\u65E5\u671F",
      path: "start_date",
      error: error,
      required: true
    }, /*#__PURE__*/React.createElement("input", {
      type: "date",
      value: range.start_date,
      disabled: disabled,
      onChange: event => setRange({
        ...range,
        start_date: event.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u7ED3\u675F\u65E5\u671F",
      path: "end_date",
      error: error,
      required: true
    }, /*#__PURE__*/React.createElement("input", {
      type: "date",
      value: range.end_date,
      disabled: disabled,
      onChange: event => setRange({
        ...range,
        end_date: event.target.value
      })
    }))), /*#__PURE__*/React.createElement("div", {
      className: "wb-actions",
      style: {
        marginTop: 12
      }
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "list-checks",
      disabled: disabled,
      busy: busy,
      onClick: onPreview
    }, "\u9884\u68C0\u8981\u6E05\u9664\u7684\u65E5\u671F"), preview && /*#__PURE__*/React.createElement(Button, {
      icon: "trash-2",
      className: "btn danger",
      disabled: disabled,
      reason: reason,
      onClick: onConfirm
    }, "\u786E\u8BA4\u6E05\u9664 ", preview.data.count, " \u5929")), preview && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, preview.data.count ? '这段时间里单独设置过的日期：' + preview.data.days.map(day => day.date).join('、') : '这段时间里没有单独设置过的日期，不需要清除。'));
  }
  function OperatorCalendarPanel({
    adapter,
    entity,
    source,
    command,
    onClose,
    refreshState,
    onRefresh,
    Feedback
  }) {
    const ref = entity.ref;
    const [month, setMonth] = React.useState(todayMonth);
    const [editBase, setEditBase] = React.useState(null);
    const [selected, setSelected] = React.useState(null),
      [draft, setDraft] = React.useState(null);
    const [mode, setMode] = React.useState('day');
    const [range, setRange] = React.useState(() => ({
      start_date: monthKey(month.year, month.month) + '-01',
      end_date: monthKey(month.year, month.month) + '-' + monthDays(month.year, month.month)
    }));
    const [preview, setPreview] = React.useState(null),
      [busy, setBusy] = React.useState(false);
    const [error, setError] = React.useState(null),
      [clearing, setClearing] = React.useState(false);
    const mounted = React.useRef(true),
      lastResult = React.useRef(null);
    React.useEffect(() => {
      mounted.current = true;
      return () => {
        mounted.current = false;
      };
    }, []);
    const request = S.useQuery(async signal => {
      if (typeof adapter.query !== 'function') throw C.failure('dependency not wired: adapter.query');
      return O.month(await adapter.query(PATH(ref) + '/month', month, signal), {
        ...month,
        ref
      });
    }, [adapter, ref, month.year, month.month]);
    const result = request.result,
      data = result && result.data;
    if (result) lastResult.current = result;
    // 刷新本月时保留上一次读到的月历，不把整块清空闪烁；写入仍只认最新读到的 data。
    // 翻月时标题已经指向新月，旧月网格不能继续显示在新标题下。
    const previous = lastResult.current && lastResult.current.data;
    const baseline = data || (previous && previous.year === month.year && previous.month === month.month ? previous : null);
    const shown = data || (request.loading ? baseline : null);
    const done = command.phase === 'done',
      disabled = command.locked || done || request.loading || busy;
    // 刷新开始或失败时 data 会暂时为空，但不能因此把尚未保存的草稿判成 clean。
    // baseline 只给草稿身份和 dirty guard 用；保存仍由下方 data 门禁只使用最新写入上下文。
    const current = baseline && selected ? baseline.days.find(day => day.date === selected) : null;
    React.useEffect(() => {
      if (current && (!draft || draft.date !== current.date)) {
        setDraft({
          ...O.draftOf(current),
          date: current.date
        });
        setEditBase(current);
      }
    }, [current && current.date, current && current.calendar_ref]);
    const staleDraft = !!current && !!editBase && (current.calendar_ref !== editBase.calendar_ref || JSON.stringify(O.draftOf(current)) !== JSON.stringify(O.draftOf(editBase)));
    const dirty = !done && mode === 'day' && !!current && !!draft && draft.date === current.date && JSON.stringify(draft) !== JSON.stringify({
      ...O.draftOf(editBase || current),
      date: current.date
    });
    const owner = window.WorkbenchGuards.useDirtyGuard({
      dirty,
      message: window.WorkbenchTerms.personal_calendar + '有尚未保存的修改。',
      locked: command.locked
    });
    async function close(detail) {
      if (command.locked) return;
      if (!(detail && detail.guardConfirmed === true && detail.guardOwner === owner) && !(await window.WorkbenchGuards.confirmLeave({
        owner
      }))) return;
      onClose();
    }
    async function confirmDraftTransition() {
      if (disabled) return false;
      return window.WorkbenchGuards.confirmLeave({
        owner
      });
    }
    async function openDay(day) {
      if (disabled) return;
      if (mode === 'day' && day.date === selected) return;
      if (!(await confirmDraftTransition())) return;
      if (!command.reset()) return;
      setError(null);
      setMode('day');
      setClearing(false);
      setSelected(day.date);
      setEditBase(day);
      setDraft({
        ...O.draftOf(day),
        date: day.date
      });
    }
    async function changeMonth(next) {
      if (!next || !(await confirmDraftTransition())) return;
      if (!command.reset()) return;
      setError(null);
      setClearing(false);
      setSelected(null);
      setDraft(null);
      setMonth(next);
    }
    async function toggleMode() {
      const abandonDraft = dirty;
      if (!(await confirmDraftTransition())) return;
      if (!command.reset()) return;
      // Only a confirmed dirty transition abandons the day draft. Keep the established clean-mode round trip, but clear
      // a discarded draft's identity as well as its fields so returning from range mode cannot register it dirty again.
      setMode(value => value === 'range' ? 'day' : 'range');
      if (abandonDraft) {
        setSelected(null);
        setDraft(null);
      }
      setClearing(false);
      setError(null);
      setPreview(null);
    }
    function capability(action) {
      if (!data) return '请先读取这个月的个人日历。';
      if (source !== 'production') return '当前不是生产数据，不能修改个人日历。';
      return C.blocked(data.write_context, 'operator', action, source);
    }
    function save() {
      if (disabled || !current || staleDraft) return;
      try {
        setError(null);
        if (!command.reset()) return;
        command.submit('operator', 'calendar_upsert', ref, data.write_context, {
          date: current.date,
          fields: O.input(draft, editBase || current)
        });
      } catch (failure) {
        setError(failure);
      }
    }
    function clearDay() {
      if (disabled || !current || !current.explicit || !clearing) return;
      setError(null);
      if (!command.reset()) return;
      command.submit('operator', 'calendar_delete', ref, data.write_context, {
        date: current.date
      });
    }
    async function previewRange() {
      if (disabled) return;
      try {
        setError(null);
        setPreview(null);
        const input = O.rangeInput(range);
        if (!command.reset()) return;
        setBusy(true);
        const raw = await adapter.preview(PATH(ref) + '/range-preview', {
          input
        }, new AbortController().signal);
        if (mounted.current) setPreview(O.rangePreview(raw, input));
      } catch (failure) {
        if (mounted.current) setError(failure);
      } finally {
        if (mounted.current) setBusy(false);
      }
    }
    function confirmRange() {
      if (disabled || !preview || !preview.data.count) return;
      setError(null);
      if (!command.reset()) return;
      command.submit('operator', 'calendar_range_clear', ref, preview.data.write_context, preview.data.range);
    }
    const saveReason = staleDraft ? '这一天的配置已变化，请先采用最新配置后重新填写。' : capability('calendar_upsert');
    const clearReason = capability('calendar_delete');
    const rangeReason = !preview ? '请先预检要清除的日期。' : !preview.data.count ? '这段时间没有要清除的日期。' : capability('calendar_range_clear');
    return /*#__PURE__*/React.createElement("div", {
      className: "plana resource-calendar wb-operator-calendar"
    }, /*#__PURE__*/React.createElement(Modal, {
      title: (entity.business_code || '') + ' · ' + window.WorkbenchTerms.personal_calendar,
      icon: "calendar-days",
      onClose: close,
      guardOwner: owner,
      locked: command.locked,
      footer: /*#__PURE__*/React.createElement(Button, {
        onClick: close,
        reason: command.locked ? '结果还没确认，暂时不能关闭。' : ''
      }, done ? '完成' : '关闭')
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b scroll"
    }, /*#__PURE__*/React.createElement("p", {
      className: "iohint"
    }, window.WorkbenchTerms.personal_calendar, "\u53EA\u7BA1\u8FD9\u4E00\u4E2A\u4EBA\u3002\u67D0\u4E00\u5929\u8BBE\u4E86", window.WorkbenchTerms.personal_calendar, "\uFF0C\u8FD9\u4E00\u5929\u5C31\u6574\u5929\u6309\u8FD9\u91CC\u7684\u5B89\u6392\u6392\u4EA7\uFF0C \u4E0D\u518D\u5957\u7528\u4ED6\u7684\u73ED\u6B21\u8F6E\u6362\uFF0C\u4E5F\u4E0D\u770B\u5168\u5C40\u5DE5\u4F5C\u65E5\u5386\u3002\u6CA1\u6709\u5355\u72EC\u8BBE\u7F6E\u7684\u65E5\u671F\u663E\u793A\u300C\u6309\u73ED\u6B21\u300D\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "cal-top",
      style: {
        flexWrap: 'wrap'
      }
    }, /*#__PURE__*/React.createElement(Button, {
      className: "cal-nav",
      icon: "chevron-left",
      "aria-label": "\u4E0A\u4E00\u6708",
      disabled: disabled || !data || !data.previous_month,
      onClick: () => changeMonth(data.previous_month)
    }), /*#__PURE__*/React.createElement("span", {
      className: "cal-title"
    }, month.year, " \u5E74 ", month.month, " \u6708"), /*#__PURE__*/React.createElement(Button, {
      className: "cal-nav",
      icon: "chevron-right",
      "aria-label": "\u4E0B\u4E00\u6708",
      disabled: disabled || !data || !data.next_month,
      onClick: () => changeMonth(data.next_month)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u672C\u6708",
      busy: request.loading,
      disabled: disabled,
      onClick: request.reload
    }), /*#__PURE__*/React.createElement("span", {
      className: "tb-spacer",
      style: {
        flex: 1
      }
    }), /*#__PURE__*/React.createElement(Button, {
      icon: mode === 'range' ? 'calendar-days' : 'trash-2',
      disabled: disabled,
      onClick: toggleMode
    }, mode === 'range' ? '返回按天维护' : '按日期范围清除')), shown && /*#__PURE__*/React.createElement("p", {
      className: "muted",
      role: "status"
    }, "\u672C\u6708\u5355\u72EC\u8BBE\u7F6E\u4E86 ", /*#__PURE__*/React.createElement("b", null, shown.stats.configured), " \u5929\uFF0C \u5176\u4E2D\u4E0A\u73ED ", shown.stats.work_days, " \u5929\u3002"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: request.error
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: result && result.warnings || []
    }), request.loading && !shown && /*#__PURE__*/React.createElement(window.WorkbenchControls.EmptyState, {
      kind: "loading",
      title: '正在读取' + window.WorkbenchTerms.personal_calendar + '…'
    }), request.loading && shown && /*#__PURE__*/React.createElement("p", {
      role: "status",
      className: "muted"
    }, "\u6B63\u5728\u5237\u65B0\u672C\u6708\u2026"), shown && mode === 'day' && /*#__PURE__*/React.createElement("div", {
      className: "cal-grid",
      "aria-busy": request.loading || undefined
    }, ['一', '二', '三', '四', '五', '六', '日'].map(name => /*#__PURE__*/React.createElement("div", {
      className: "cal-wd",
      key: name
    }, name)), shown.cells.map((cell, index) => {
      if (!cell) return /*#__PURE__*/React.createElement("div", {
        key: 'empty-' + index,
        className: "cal-cell empty"
      });
      const meta = O.tag(cell);
      return /*#__PURE__*/React.createElement("button", {
        key: cell.date,
        type: "button",
        disabled: disabled,
        className: 'cal-cell ' + meta.tone + (cell.is_today ? ' today' : '') + (cell.date === selected ? ' sel' : ''),
        style: {
          minWidth: 0,
          textAlign: 'left',
          color: 'inherit',
          fontFamily: 'inherit'
        },
        "data-operator-calendar-date": cell.date,
        "aria-label": cell.date + ' ' + (cell.explicit ? '已单独设置' : '未单独设置') + ' ' + meta.text,
        onClick: () => openDay(cell)
      }, /*#__PURE__*/React.createElement("span", {
        className: "d"
      }, cell.day), /*#__PURE__*/React.createElement("span", {
        className: "tag",
        style: {
          whiteSpace: 'normal',
          overflowWrap: 'anywhere'
        }
      }, meta.text));
    })), data && mode === 'day' && current && draft && /*#__PURE__*/React.createElement(DayEditor, {
      day: current,
      draft: draft,
      setDraft: setDraft,
      disabled: disabled,
      error: error,
      onSave: save,
      onClear: clearDay,
      saveReason: saveReason,
      clearReason: clearReason,
      clearing: clearing && current.explicit,
      onClearing: value => {
        setClearing(value);
        setError(null);
      }
    }), data && mode === 'day' && !current && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u70B9\u4E00\u5929\u5F00\u59CB\u7EF4\u62A4\u3002"), data && mode === 'range' && /*#__PURE__*/React.createElement(RangeClear, {
      range: range,
      setRange: next => {
        setRange(next);
        setPreview(null);
      },
      disabled: disabled,
      error: error,
      preview: preview,
      onPreview: previewRange,
      onConfirm: confirmRange,
      reason: rangeReason,
      busy: busy
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(Feedback, {
      command: command
    }), staleDraft && !done && /*#__PURE__*/React.createElement("div", {
      role: "status"
    }, /*#__PURE__*/React.createElement("p", null, "\u8FD9\u4E00\u5929\u5DF2\u88AB\u4FEE\u6539\uFF0C\u65E7\u8349\u7A3F\u4E0D\u4F1A\u8986\u76D6\u6700\u65B0\u914D\u7F6E\u3002\u91C7\u7528\u6700\u65B0\u914D\u7F6E\u4F1A\u653E\u5F03\u672C\u6B21\u672A\u4FDD\u5B58\u7684\u5185\u5BB9\u3002"), /*#__PURE__*/React.createElement(Button, {
      disabled: command.locked || request.loading,
      onClick: () => {
        setDraft({
          ...O.draftOf(current),
          date: current.date
        });
        setEditBase(current);
        setError(null);
        command.reset();
      }
    }, "\u91C7\u7528\u6700\u65B0\u914D\u7F6E\u5E76\u91CD\u65B0\u586B\u5199")), done && /*#__PURE__*/React.createElement(RefreshResult, {
      state: refreshState,
      onRefresh: onRefresh
    }))));
  }
  window.OperatorCalendarPanel = OperatorCalendarPanel;
})();
