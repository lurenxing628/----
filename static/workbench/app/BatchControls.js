(function () {
  'use strict';

  const B = window.APSBatchContract;
  // Lucide v1.8.0 ISC: icons/funnel, copy, arrow-left. Existing assets/lucide-LICENSE applies.
  Object.assign(window.APSFieldReports.iconNodes, {
    filter: [['path', {
      d: 'M10 20a1 1 0 0 0 .553.895l2 1A1 1 0 0 0 14 21v-7a2 2 0 0 1 .517-1.341L21.74 4.67A1 1 0 0 0 21 3H3a1 1 0 0 0-.742 1.67l7.225 7.989A2 2 0 0 1 10 14z'
    }]],
    copy: [['rect', {
      width: '14',
      height: '14',
      x: '8',
      y: '8',
      rx: '2',
      ry: '2'
    }], ['path', {
      d: 'M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2'
    }]],
    'arrow-left': [['path', {
      d: 'm12 19-7-7 7-7'
    }], ['path', {
      d: 'M19 12H5'
    }]]
  });
  const Field = window.ResourceControls.Field;
  function display(key, value) {
    if (key === 'quantity') return window.WorkbenchFormat.number(value, {
      digits: 0
    });
    if (key === 'due_date' || key === 'ready_date') return window.WorkbenchFormat.date(value);
    return B.label(key, value);
  }
  function BaseFields({
    value,
    setValue,
    disabled,
    entity,
    choices,
    error,
    errors
  }) {
    const set = (key, next) => setValue(current => ({
      ...current,
      [key]: next
    }));
    const path = key => ['business_code', 'part_ref'].includes(key) ? key : 'fields.' + key;
    const input = (key, label, type = 'text') => /*#__PURE__*/React.createElement(Field, {
      key: key,
      label: label,
      path: path(key),
      error: error,
      errors: errors,
      required: key === 'business_code' || key === 'quantity'
    }, /*#__PURE__*/React.createElement("input", {
      type: type,
      value: value[key],
      disabled: disabled,
      min: type === 'number' ? 1 : undefined,
      step: type === 'number' ? 1 : undefined,
      onChange: event => set(key, event.target.value)
    }));
    const select = (key, label, options) => /*#__PURE__*/React.createElement(Field, {
      label: label,
      path: path(key),
      error: error,
      errors: errors
    }, /*#__PURE__*/React.createElement("select", {
      value: value[key],
      disabled: disabled,
      onChange: event => set(key, event.target.value)
    }, !options.some(row => row[0] === value[key]) && /*#__PURE__*/React.createElement("option", {
      value: value[key]
    }, "\u539F\u503C\u5F85\u6838\u5BF9"), options.map(([key, label]) => /*#__PURE__*/React.createElement("option", {
      key: key,
      value: key
    }, label))));
    return /*#__PURE__*/React.createElement("div", {
      className: "fgrid batch-fields"
    }, entity ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Field, {
      label: "\u6279\u6B21\u53F7"
    }, /*#__PURE__*/React.createElement("input", {
      disabled: true,
      value: entity.business_code
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u56FE\u53F7"
    }, /*#__PURE__*/React.createElement("input", {
      disabled: true,
      value: entity.relationships.part_no + ' · ' + entity.label
    }))) : /*#__PURE__*/React.createElement(React.Fragment, null, input('business_code', '批次号'), /*#__PURE__*/React.createElement(Field, {
      label: "\u56FE\u53F7",
      path: "part_ref",
      error: error,
      errors: errors,
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      value: value.part_ref,
      disabled: disabled || !choices,
      onChange: event => set('part_ref', event.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u8BF7\u9009\u62E9\u56FE\u53F7"), choices && choices.parts.map(row => /*#__PURE__*/React.createElement("option", {
      key: row.ref,
      value: row.ref
    }, row.business_code, " \xB7 ", row.label))))), input('quantity', '数量', 'number'), input('due_date', '交期', 'date'), select('priority', '优先级', B.priority), select('ready_status', '齐套显示', B.ready), input('ready_date', '齐套日期', 'date'), input('remark', '备注'));
  }
  function Styles() {
    return null;
  }
  window.BatchControls = {
    Field,
    BaseFields,
    Styles,
    display
  };
})();
