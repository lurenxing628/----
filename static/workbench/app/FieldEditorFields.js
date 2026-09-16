(function () {
  'use strict';

  const C = window.FieldContract,
    {
      Button
    } = window.FieldControls;
  function FieldEditorFields({
    task,
    record,
    legacy,
    action,
    adapter,
    draft,
    suggestions,
    disabled,
    first,
    change,
    error
  }) {
    const Field = window.ResourceControls.Field;
    const readonly = key => disabled || action === 'supplement' && record[key] !== null && record[key] !== '';
    const choices = (key, label, kind) => /*#__PURE__*/React.createElement(window.ResourceControls.Choice, {
      adapter: adapter,
      field: {
        key,
        label,
        kind
      },
      value: draft[key],
      disabled: readonly(key),
      error: error,
      original: record ? {
        relationships: {
          [key]: record[key],
          [key.replace('_ref', '_label')]: record[key.replace('_ref', '_label')]
        }
      } : null,
      onChange: value => change(key, value)
    });
    const amount = value => value !== '' && Number.isFinite(Number(value)) ? Number(value) : null;
    const quantity = amount(draft.completed_quantity),
      effectiveHours = amount(draft.effective_processing_hours);
    const previousQuantity = record && record.completed_quantity !== null ? record.completed_quantity : 0;
    const cumulative = quantity === null || !Number.isSafeInteger(quantity) || quantity < 0 || task.execution.known_completed_quantity === null ? null : task.execution.known_completed_quantity - previousQuantity + quantity;
    const start = draft.actual_start ? Date.parse(draft.actual_start + 'Z') : NaN,
      end = draft.actual_end ? Date.parse(draft.actual_end + 'Z') : NaN;
    const span = Number.isFinite(start) && Number.isFinite(end) && end >= start ? (end - start) / 3600000 : null;
    const difference = span !== null && effectiveHours !== null ? span - effectiveHours : null;
    // Span and difference are checked against entered hours; keep up to three decimals instead of a one-decimal summary.
    const hours = value => window.WorkbenchFormat.hours(value, {
      digits: 3,
      trim: true
    });
    const timeHints = Object.keys(suggestions).length > 0;
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "field-entry-grid"
    }, /*#__PURE__*/React.createElement("section", null, /*#__PURE__*/React.createElement("h4", null, "\u4EA7\u51FA\u6570\u91CF"), /*#__PURE__*/React.createElement(Field, {
      label: "\u672C\u6B21\u5B8C\u6210\u6570\u91CF",
      path: "completed_quantity",
      error: error
    }, /*#__PURE__*/React.createElement("input", {
      ref: first,
      type: "number",
      min: "0",
      step: "1",
      "aria-label": "\u672C\u6B21\u5B8C\u6210\u6570\u91CF",
      value: draft.completed_quantity,
      disabled: readonly('completed_quantity'),
      onChange: event => change('completed_quantity', event.target.value)
    })), /*#__PURE__*/React.createElement("div", {
      className: "field-quantity-tools"
    }, /*#__PURE__*/React.createElement("span", null, "\u4EF6"), /*#__PURE__*/React.createElement(Button, {
      disabled: readonly('completed_quantity'),
      onClick: () => change('completed_quantity', '0')
    }, "\u6700\u5C0F"), action === 'create' && /*#__PURE__*/React.createElement(Button, {
      disabled: disabled || task.execution.remaining_quantity === null,
      onClick: () => change('completed_quantity', String(task.execution.remaining_quantity))
    }, "\u6700\u5927")), /*#__PURE__*/React.createElement("p", {
      className: "field-note"
    }, "\u5DF2\u77E5\u7D2F\u8BA1 ", /*#__PURE__*/React.createElement("output", {
      "aria-label": "\u5DF2\u77E5\u7D2F\u8BA1"
    }, cumulative === null ? '未核对' : cumulative), " / \u6267\u884C\u76EE\u6807 ", C.quantity(task.execution.target_quantity), " \u4EF6", task.execution.unknown_record_count > 0 && /*#__PURE__*/React.createElement("small", null, " \xB7 \u539F\u8BB0\u5F55\u6570\u91CF\u5F85\u8865 ", task.execution.unknown_record_count, " \u6761"))), /*#__PURE__*/React.createElement("section", null, /*#__PURE__*/React.createElement("h4", null, "\u5B9E\u9645\u8D77\u6B62"), timeHints && /*#__PURE__*/React.createElement("p", {
      className: "field-suggestion",
      role: "status"
    }, "\u8BF7\u6838\u5BF9\u9884\u586B\u65F6\u95F4\uFF1B\u4E0D\u786E\u5B9A\u7684\u65F6\u95F4\u8BF7\u6E05\u9664\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "field-time-grid"
    }, [['actual_start', '实际开工'], ['actual_end', '本次实际完工']].map(([key, label]) => /*#__PURE__*/React.createElement("div", {
      key: key
    }, /*#__PURE__*/React.createElement(Field, {
      label: label,
      path: key,
      error: error,
      hint: suggestions[key] ? '建议来源：' + suggestions[key] : undefined
    }, /*#__PURE__*/React.createElement("input", {
      type: "datetime-local",
      step: "1",
      "aria-label": label,
      value: draft[key],
      disabled: readonly(key),
      onChange: event => change(key, event.target.value)
    })), /*#__PURE__*/React.createElement(Button, {
      disabled: readonly(key) || !draft[key],
      "aria-label": '清除' + label,
      onClick: () => change(key, '')
    }, "\u6E05\u9664"))))), /*#__PURE__*/React.createElement("section", null, /*#__PURE__*/React.createElement("h4", null, "\u5DE5\u65F6\u6838\u5BF9"), /*#__PURE__*/React.createElement(Field, {
      label: "\u6709\u6548\u5DE5\u65F6\uFF08\u5C0F\u65F6\uFF09",
      path: "effective_processing_hours",
      error: error
    }, /*#__PURE__*/React.createElement("input", {
      type: "number",
      min: "0",
      step: "any",
      "data-wb-step": "0.1",
      "aria-label": "\u6709\u6548\u5DE5\u65F6\uFF08\u5C0F\u65F6\uFF09",
      value: draft.effective_processing_hours,
      disabled: readonly('effective_processing_hours'),
      onChange: event => change('effective_processing_hours', event.target.value)
    })), /*#__PURE__*/React.createElement("p", {
      className: "field-note"
    }, "\u4F5C\u4E1A\u65F6\u957F ", /*#__PURE__*/React.createElement("output", {
      "aria-label": "\u4F5C\u4E1A\u65F6\u957F"
    }, hours(span))), /*#__PURE__*/React.createElement("p", {
      className: 'field-note' + (difference !== null && difference < 0 ? ' field-hours-warning' : '')
    }, "\u5DE5\u65F6\u5DEE\u989D ", /*#__PURE__*/React.createElement("output", {
      "aria-label": "\u5DE5\u65F6\u5DEE\u989D"
    }, hours(difference))))), /*#__PURE__*/React.createElement("details", {
      open: action !== 'create' || !!legacy
    }, /*#__PURE__*/React.createElement("summary", null, "\u5B9E\u9645\u8BBE\u5907 / \u4EBA\u5458 / \u5907\u6CE8", record || legacy ? ' / 原因' : ''), /*#__PURE__*/React.createElement("div", {
      className: "field-extra"
    }, choices('actual_machine_ref', '实际设备', 'machine'), choices('actual_operator_ref', '实际人员', 'operator'), /*#__PURE__*/React.createElement(Field, {
      label: "\u4F5C\u4E1A\u5907\u6CE8",
      path: "remark",
      error: error
    }, /*#__PURE__*/React.createElement("textarea", {
      "aria-label": "\u4F5C\u4E1A\u5907\u6CE8",
      maxLength: "2000",
      value: draft.remark,
      disabled: readonly('remark'),
      onChange: event => change('remark', event.target.value)
    })), (record || legacy) && /*#__PURE__*/React.createElement(Field, {
      label: action === 'supplement' || legacy ? '补齐原因' : '更正原因',
      path: "reason",
      error: error,
      required: true
    }, /*#__PURE__*/React.createElement("textarea", {
      required: true,
      "aria-label": "\u8865\u9F50\u6216\u66F4\u6B63\u539F\u56E0",
      maxLength: "2000",
      value: draft.reason,
      disabled: disabled,
      onChange: event => change('reason', event.target.value)
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u7ECF\u529E\u4EBA",
      path: "declared_operator",
      error: error
    }, /*#__PURE__*/React.createElement("input", {
      "aria-label": "\u7ECF\u529E\u4EBA",
      maxLength: "2000",
      value: draft.declared_operator,
      disabled: disabled,
      onChange: event => change('declared_operator', event.target.value)
    })))));
  }
  window.FieldEditorFields = FieldEditorFields;
})();
