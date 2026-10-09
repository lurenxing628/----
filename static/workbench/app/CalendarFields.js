(function () {
  'use strict';

  const {
    Button,
    ErrorBox,
    Field,
    Issues
  } = window.ResourceControls;
  const fieldPaths = ['fields.hours', 'fields.eff', 'fields.note', 'fields.shiftStart', 'fields.shiftEnd', 'fields.periods'];
  function Segment({
    label,
    value,
    options,
    onChange,
    disabled
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "field full"
    }, /*#__PURE__*/React.createElement("label", null, label), /*#__PURE__*/React.createElement("div", {
      className: "seg",
      role: "group",
      "aria-label": label,
      style: {
        flexWrap: 'wrap',
        maxWidth: '100%'
      }
    }, options.map(([key, text]) => /*#__PURE__*/React.createElement("button", {
      type: "button",
      key: key,
      className: value === key ? 'on' : '',
      "aria-pressed": value === key,
      disabled: disabled,
      onClick: () => onChange(key)
    }, text))));
  }
  function CalendarFields({
    value,
    onChange,
    disabled,
    error,
    noteEnabled = true,
    showSummary = true
  }) {
    const work = value.type === 'work';
    // 分段时段全部移除，或可排工时填 0：能保存，但排产按 0 工时排不进任何工序，先在表单里说清楚。
    const zeroHours = work && (Array.isArray(value.periods) ? !value.periods.length : String(value.hours).trim() !== '' && Number(value.hours) === 0);
    const change = (key, next) => onChange(key === 'type' ? window.APSCalendarContract.switchType(value, next) : {
      ...value,
      [key]: next
    });
    const id = React.useId();
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Segment, {
      label: "\u8FD9\u4E00\u5929\u662F\u5426\u6392\u4EA7",
      value: value.type,
      options: [["work", "工作日"], ["rest", "休息日"]],
      onChange: next => change('type', next),
      disabled: disabled
    }), /*#__PURE__*/React.createElement("div", {
      className: "fgrid cal-work-fields",
      style: work ? undefined : {
        opacity: .55
      }
    }, value.periods == null && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Field, {
      label: "\u73ED\u6B21\u5F00\u59CB",
      path: "fields.shiftStart",
      error: error
    }, /*#__PURE__*/React.createElement("input", {
      type: "time",
      value: value.shiftStart || '',
      disabled: disabled || !work,
      onChange: event => onChange({
        ...value,
        shiftStart: event.target.value,
        shiftEnd: ''
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u73ED\u6B21\u7ED3\u675F\uFF08\u7A7A\u767D\u6309\u5DE5\u65F6\u63A8\u7B97\uFF09",
      path: "fields.shiftEnd",
      error: error
    }, /*#__PURE__*/React.createElement("input", {
      type: "time",
      value: value.shiftEnd || '',
      disabled: disabled || !work,
      onChange: event => {
        const end = event.target.value,
          start = value.shiftStart;
        const minute = text => Number(text.slice(0, 2)) * 60 + Number(text.slice(3));
        onChange({
          ...value,
          shiftEnd: end,
          hours: end && start ? String(((minute(end) - minute(start) + 1439) % 1440 + 1) / 60) : value.hours
        });
      }
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u53EF\u6392\u5DE5\u65F6\uFF08\u5C0F\u65F6\uFF09",
      path: "fields.hours",
      error: error,
      required: work
    }, /*#__PURE__*/React.createElement("input", {
      id: id + '-hours',
      name: "hours",
      className: "cal-hours",
      type: "number",
      min: "0",
      max: "24",
      step: "any",
      "data-wb-step": "0.5",
      value: value.hours,
      disabled: disabled || !work,
      onChange: event => onChange({
        ...value,
        hours: event.target.value,
        shiftEnd: ''
      })
    }))), /*#__PURE__*/React.createElement(window.WorkPeriodFields, {
      value: value.periods,
      start: value.shiftStart,
      end: value.shiftEnd,
      disabled: disabled || !work,
      onChange: periods => onChange({
        ...value,
        periods,
        hours: String(window.APSWorkPeriods.hours(periods) ?? value.hours)
      })
    }), /*#__PURE__*/React.createElement(Field, {
      label: "\u6548\u7387\uFF08%\uFF09",
      path: "fields.eff",
      error: error,
      required: work
    }, /*#__PURE__*/React.createElement("input", {
      id: id + '-eff',
      name: "eff",
      className: "cal-eff",
      type: "number",
      min: "0",
      max: "200",
      step: "any",
      "data-wb-step": "5",
      value: value.eff,
      disabled: disabled || !work,
      onChange: event => change('eff', event.target.value)
    })), ['allowNormal', 'allowUrgent'].map(key => /*#__PURE__*/React.createElement("div", {
      className: "field",
      key: key
    }, /*#__PURE__*/React.createElement(Segment, {
      label: key === 'allowNormal' ? '允许普通件排产' : '允许急件排产',
      value: value[key],
      options: [["yes", "是"], ["no", "否"]],
      onChange: next => change(key, next),
      disabled: disabled || !work
    })))), /*#__PURE__*/React.createElement(Issues, {
      issues: zeroHours ? [window.APSWorkPeriods.zeroHoursNote] : []
    }), /*#__PURE__*/React.createElement(Field, {
      label: "\u5907\u6CE8",
      path: "fields.note",
      error: error,
      full: true
    }, /*#__PURE__*/React.createElement("input", {
      id: id + '-note',
      className: "cal-note",
      value: value.note,
      disabled: disabled || !noteEnabled,
      onChange: event => change('note', event.target.value)
    })), showSummary && /*#__PURE__*/React.createElement(ErrorBox, {
      error: error,
      excludePaths: fieldPaths
    }));
  }
  function Policy({
    value,
    raw = true
  }) {
    const fields = value.fields,
      stored = value.stored;
    const number = window.APSCalendarContract.displayNumber;
    const yesNo = item => ({
      yes: '可排',
      no: '不可排'
    })[item] || String(item);
    return /*#__PURE__*/React.createElement("div", {
      style: {
        overflowWrap: 'anywhere',
        lineHeight: 1.65
      }
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("b", null, value.explicit ? '单独设置' : '默认规则'), " \xB7 ", value.effective.is_working ? '可排产' : '不排产'), /*#__PURE__*/React.createElement("div", null, number(fields.hours), " \u5C0F\u65F6 \xB7 \u6548\u7387 ", number(fields.eff), "% \xB7 \u666E\u901A\u4EF6", fields.allowNormal === 'yes' ? '可排' : '不可排', " \xB7 \u6025\u4EF6", fields.allowUrgent === 'yes' ? '可排' : '不可排'), /*#__PURE__*/React.createElement("div", {
      className: "muted"
    }, "\u6709\u6548\u65F6\u6BB5\uFF1A", value.effective.periods != null ? window.APSWorkPeriods.describe(value.effective.periods) : window.WorkbenchFormat.dateTime(value.effective.window_start) + " 至 " + window.WorkbenchFormat.dateTime(value.effective.window_end)), raw && stored && /*#__PURE__*/React.createElement("div", {
      className: "muted"
    }, "\u539F\u59CB\u914D\u7F6E\uFF08\u53EA\u8BFB\uFF09\uFF1A", {
      workday: '工作日',
      holiday: '休息日'
    }[stored.day_type] || String(stored.day_type), "\uFF1B\u8D77\u6B62 ", stored.shift_start == null ? '未设置' : stored.shift_start, " / ", stored.shift_end == null ? '未设置' : stored.shift_end, "\uFF1B \u5DE5\u65F6 ", number(stored.shift_hours), "\uFF1B\u6548\u7387 ", typeof stored.efficiency === 'number' ? number(stored.efficiency * 100) + '%' : String(stored.efficiency), "\uFF1B\u666E\u901A\u4EF6", yesNo(stored.allow_normal), "\uFF1B\u6025\u4EF6", yesNo(stored.allow_urgent)), /*#__PURE__*/React.createElement("div", {
      className: "muted"
    }, "\u5907\u6CE8\uFF1A", fields.note || '未填写'));
  }
  function RefreshResult({
    state,
    onRefresh
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, state.loading ? '正在刷新工作日历…' : state.done ? '已刷新，显示最新工作日历。' : '最新工作日历尚未确认。'), /*#__PURE__*/React.createElement(ErrorBox, {
      error: state.error
    }), state.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: onRefresh
    }, "\u5237\u65B0\u4FDD\u5B58\u7ED3\u679C"));
  }
  window.CalendarFields = {
    Fields: CalendarFields,
    Segment,
    Policy,
    RefreshResult,
    fieldPaths
  };
})();
