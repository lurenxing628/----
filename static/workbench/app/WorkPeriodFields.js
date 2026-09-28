(function () {
  'use strict';

  const {
    validate,
    hours,
    duration
  } = window.APSWorkPeriods;
  function Fields({
    value,
    onChange,
    disabled,
    start = '08:00',
    end = '16:00',
    label = '工作时段'
  }) {
    const {
      Button,
      Field
    } = window.ResourceControls;
    if (value == null) return /*#__PURE__*/React.createElement("div", {
      className: "field full"
    }, /*#__PURE__*/React.createElement(Button, {
      disabled: disabled,
      onClick: () => onChange([{
        start: start || '08:00',
        end: end || '16:00',
        day_offset: 0
      }])
    }, "\u5206\u6BB5\u8BBE\u7F6E\u5DE5\u4F5C\u65F6\u95F4"), /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, " \u53EF\u5206\u522B\u586B\u5199\u4E0A\u5348\u3001\u4E0B\u5348\u6216\u591C\u73ED\uFF0C\u4E2D\u95F4\u4F11\u606F\u4E0D\u8BA1\u5DE5\u65F6\u3002"));
    const change = (index, key, next) => onChange(value.map((row, i) => i === index ? {
      ...row,
      [key]: next
    } : row));
    const error = validate(value),
      total = hours(value);
    return /*#__PURE__*/React.createElement("div", {
      className: "field full",
      role: "group",
      "aria-label": label
    }, /*#__PURE__*/React.createElement("b", null, label), value.map((row, index) => /*#__PURE__*/React.createElement("div", {
      className: "fgrid",
      key: index
    }, /*#__PURE__*/React.createElement(Field, {
      label: label + '第 ' + (index + 1) + ' 段开始日期'
    }, /*#__PURE__*/React.createElement("select", {
      value: row.day_offset,
      disabled: disabled || index === 0,
      onChange: event => change(index, 'day_offset', Number(event.target.value))
    }, /*#__PURE__*/React.createElement("option", {
      value: 0
    }, "\u5F53\u5929"), /*#__PURE__*/React.createElement("option", {
      value: 1
    }, "\u6B21\u65E5"))), /*#__PURE__*/React.createElement(Field, {
      label: label + '第 ' + (index + 1) + ' 段开始'
    }, /*#__PURE__*/React.createElement("input", {
      type: "time",
      value: row.start,
      disabled: disabled,
      onChange: event => change(index, 'start', event.target.value)
    })), /*#__PURE__*/React.createElement(Field, {
      label: label + '第 ' + (index + 1) + ' 段结束'
    }, /*#__PURE__*/React.createElement("input", {
      type: "time",
      value: row.end,
      disabled: disabled,
      onChange: event => change(index, 'end', event.target.value)
    })), /*#__PURE__*/React.createElement("div", {
      className: "field"
    }, /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, row.start && row.end && row.end <= row.start ? '跨到下一天结束' : '当天结束'), /*#__PURE__*/React.createElement(Button, {
      disabled: disabled,
      onClick: () => onChange(value.filter((_, i) => i !== index))
    }, "\u79FB\u9664\u7B2C ", index + 1, " \u6BB5")))), /*#__PURE__*/React.createElement("div", {
      className: "wb-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      disabled: disabled || value.length >= 8,
      onClick: () => onChange([...value, {
        start: '',
        end: '',
        day_offset: 0
      }])
    }, "\u65B0\u589E\u5DE5\u4F5C\u65F6\u6BB5"), /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, error || '实际工作 ' + duration(total) + '；时段之间不排产。')));
  }
  window.WorkPeriodFields = Fields;
})();
