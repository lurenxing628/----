(function () {
  'use strict';

  // Load after CalendarFileContract.js and ResourceMaterialActions.jsx.
  const K = window.APSCalendarContract;
  const {
    Button,
    Field
  } = window.ResourceControls;
  function monthRange(month) {
    const key = K.monthKey(month.year, month.month);
    return {
      start_date: key + '-01',
      end_date: key + '-' + K.monthDays(month.year, month.month)
    };
  }
  function thisMonth() {
    const now = new Date();
    return {
      year: now.getFullYear(),
      month: now.getMonth() + 1
    };
  }
  function People({
    value,
    onChange,
    refs,
    disabled
  }) {
    return /*#__PURE__*/React.createElement("fieldset", {
      style: {
        border: 0,
        margin: 0,
        padding: 0
      },
      disabled: disabled
    }, /*#__PURE__*/React.createElement("legend", {
      className: "seclabel"
    }, "\u4EBA\u5458\u8303\u56F4"), [['all', '全部人员', '所有人员在这段时间里单独设置过的日期'], ['selected', '已选人员', refs.length + ' 人，含非当前页和当前筛选外的勾选记录']].map(([key, title, detail]) => /*#__PURE__*/React.createElement("label", {
      key: key,
      className: 'iorow' + (value === key ? ' on' : '')
    }, /*#__PURE__*/React.createElement("input", {
      type: "radio",
      name: "operator-calendar-people",
      value: key,
      checked: value === key,
      onChange: () => onChange(key)
    }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "iotitle"
    }, title), /*#__PURE__*/React.createElement("div", {
      className: "iosub"
    }, detail)))));
  }
  function ExportScope({
    value,
    onChange,
    disabled,
    refs = []
  }) {
    const id = React.useId();
    const set = (key, next) => onChange({
      ...value,
      [key]: next
    });
    return /*#__PURE__*/React.createElement(React.Fragment, null, value.people !== undefined && /*#__PURE__*/React.createElement(People, {
      value: value.people,
      onChange: next => set('people', next),
      refs: refs,
      disabled: disabled
    }), /*#__PURE__*/React.createElement("fieldset", {
      style: {
        border: 0,
        margin: 0,
        padding: 0
      },
      disabled: disabled
    }, /*#__PURE__*/React.createElement("legend", {
      className: "seclabel"
    }, "\u5BFC\u51FA\u8303\u56F4"), /*#__PURE__*/React.createElement("div", {
      className: "fgrid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u5F00\u59CB\u65E5\u671F",
      path: "start_date",
      required: true
    }, /*#__PURE__*/React.createElement("input", {
      id: id + '-from',
      type: "date",
      value: value.start_date,
      disabled: disabled,
      onChange: event => set('start_date', event.target.value)
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u7ED3\u675F\u65E5\u671F",
      path: "end_date",
      required: true
    }, /*#__PURE__*/React.createElement("input", {
      id: id + '-to',
      type: "date",
      value: value.end_date,
      disabled: disabled,
      onChange: event => set('end_date', event.target.value)
    }))), /*#__PURE__*/React.createElement("p", {
      className: "iohint"
    }, "\u53EA\u5BFC\u51FA\u8FD9\u6BB5\u65F6\u95F4\u91CC\u5355\u72EC\u914D\u7F6E\u8FC7\u7684\u65E5\u671F\u3002\u6CA1\u6709\u5355\u72EC\u914D\u7F6E\u8FC7\u7684\u65E5\u671F\u6309\u9ED8\u8BA4\u89C4\u5219\u7B97\uFF0C\u4E0D\u4F1A\u51FA\u73B0\u5728\u6587\u4EF6\u91CC\uFF0C \u6240\u4EE5\u5BFC\u51FA\u7684\u6587\u4EF6\u539F\u6837\u5BFC\u56DE\u6765\u4E0D\u4F1A\u6709\u4EFB\u4F55\u6539\u52A8\u3002")));
  }
  function CalendarFileActions({
    kind,
    month,
    request,
    ...props
  }) {
    const refs = Array.isArray(request && request.refs) ? request.refs : [];
    const people = kind === window.APSCalendarFile.peopleKind;
    const contract = React.useMemo(() => ({
      ...window.APSCalendarFile.create(kind),
      // 个人日历从人员列表打开，勾了人就默认只导这些人；全局日历没有这一维。
      exportScopeInitial: {
        ...monthRange(month || thisMonth()),
        ...(people ? {
          people: refs.length ? 'selected' : 'all'
        } : {})
      },
      ExportScope
    }), [kind, people, refs.length, month && month.year, month && month.month]);
    return /*#__PURE__*/React.createElement(window.ResourceFileActionFlow, {
      key: kind,
      ...props,
      request: request,
      contract: contract
    });
  }
  window.CalendarFileActions = CalendarFileActions;
  window.CalendarFileActions.ExportScope = ExportScope;
  window.CalendarFileActions.monthRange = monthRange;
})();
