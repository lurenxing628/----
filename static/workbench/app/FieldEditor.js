(function () {
  'use strict';

  const C = window.FieldContract,
    {
      Button,
      ErrorBox,
      Feedback
    } = window.FieldControls;
  function FieldEditor({
    task,
    record,
    legacy,
    action,
    adapter,
    command,
    retained,
    onDraft,
    onClose,
    onDone
  }) {
    const [draft, setDraft] = React.useState(() => {
        if (retained) return {
          ...retained.draft
        };
        const value = C.draft(record);
        if (legacy) {
          value.actual_end = legacy.event_time.replace(' ', 'T');
          value.completed_quantity = legacy.quantity_done === null ? '' : String(legacy.quantity_done);
        }
        return value;
      }),
      [error, setError] = React.useState(null);
    const currentBaseline = {
      task_ref: task.task_ref,
      plan_ref: task.plan_ref,
      report_ref: record ? record.report_ref : null,
      revision_ref: record ? record.revision_ref : null,
      legacy_ref: legacy ? legacy.legacy_fact_ref : null
    };
    const [baseline] = React.useState(() => retained ? retained.baseline : currentBaseline);
    const changed = JSON.stringify(baseline) !== JSON.stringify(currentBaseline);
    React.useLayoutEffect(() => {
      if (typeof onDraft === 'function') onDraft({
        draft,
        baseline
      });
    }, [draft, baseline, onDraft]);
    const form = React.useRef(null),
      first = React.useRef(null),
      title = legacy ? '补齐原始完工记录' : action === 'create' ? '本次报工' : action === 'supplement' ? '补齐本次报工' : '更正报工';
    const context = record ? record.write_context : task.execution.write_context;
    const disabled = command.locked || command.phase === 'done' || changed;
    const reason = changed ? '原记录或任务已变化，暂存内容未写入；请取消后重新核对。' : C.blocked(context, action);
    React.useEffect(() => {
      first.current.focus({
        preventScroll: true
      });
    }, []);
    function change(key, value) {
      setDraft(current => ({
        ...current,
        [key]: value
      }));
      setError(null);
    }
    async function save(value) {
      if (disabled || reason) return;
      try {
        if (!form.current.reportValidity()) return;
        const input = C.input(value, record, action);
        if (legacy) {
          if (!value.reason.trim()) throw window.APSResourceContract.failure('请填写旧完工事实的补齐原因。');
          input.legacy_fact_ref = legacy.legacy_fact_ref;
          input.reason = value.reason.trim();
        }
        setError(null);
        await command.submit('execution', action, record ? record.report_ref : task.task_ref, context, input);
      } catch (error) {
        setError(error);
      }
    }
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
      original: record ? {
        relationships: {
          [key]: record[key],
          [key.replace('_ref', '_label')]: record[key.replace('_ref', '_label')]
        }
      } : null,
      onChange: value => change(key, value)
    });
    const remaining = task.execution.remaining_quantity;
    const amount = value => value !== '' && Number.isFinite(Number(value)) ? Number(value) : null;
    const quantity = amount(draft.completed_quantity),
      effectiveHours = amount(draft.effective_processing_hours);
    const previousQuantity = record && record.completed_quantity !== null ? record.completed_quantity : 0;
    const cumulative = quantity === null || !Number.isSafeInteger(quantity) || quantity < 0 || task.execution.known_completed_quantity === null ? null : task.execution.known_completed_quantity - previousQuantity + quantity;
    const start = draft.actual_start ? Date.parse(draft.actual_start + 'Z') : NaN;
    const end = draft.actual_end ? Date.parse(draft.actual_end + 'Z') : NaN;
    const span = Number.isFinite(start) && Number.isFinite(end) && end >= start ? (end - start) / 3600000 : null;
    const difference = span !== null && effectiveHours !== null ? span - effectiveHours : null;
    const displayHours = value => value === null ? '未核对' : Math.round(value * 1000) / 1000 + ' h';
    return /*#__PURE__*/React.createElement("form", {
      ref: form,
      className: "field-editor",
      "aria-label": title,
      onSubmit: event => {
        event.preventDefault();
        save(draft);
      }
    }, /*#__PURE__*/React.createElement("h3", null, title, record ? ' · ' + record.report_no : ''), /*#__PURE__*/React.createElement("div", {
      className: "field-entry-grid"
    }, /*#__PURE__*/React.createElement("section", null, /*#__PURE__*/React.createElement("h4", null, "\u4EA7\u51FA\u6570\u91CF"), /*#__PURE__*/React.createElement("label", null, "\u672C\u6B21\u5B8C\u6210\u6570\u91CF", /*#__PURE__*/React.createElement("input", {
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
      disabled: disabled || remaining === null,
      onClick: () => change('completed_quantity', String(remaining))
    }, "\u6700\u5927")), /*#__PURE__*/React.createElement("p", {
      className: "field-note"
    }, "\u5DF2\u77E5\u7D2F\u8BA1\u9884\u89C8 ", /*#__PURE__*/React.createElement("output", {
      "aria-label": "\u5DF2\u77E5\u7D2F\u8BA1\u9884\u89C8"
    }, cumulative === null ? '未核对' : cumulative), " / \u6267\u884C\u76EE\u6807 ", C.quantity(task.execution.target_quantity), " \u4EF6", task.execution.unknown_record_count > 0 && /*#__PURE__*/React.createElement("small", null, " \xB7 \u539F\u8BB0\u5F55\u6570\u91CF\u5F85\u8865 ", task.execution.unknown_record_count, " \u6761"))), /*#__PURE__*/React.createElement("section", null, /*#__PURE__*/React.createElement("h4", null, "\u5B9E\u9645\u8D77\u6B62"), /*#__PURE__*/React.createElement("div", {
      className: "field-time-grid"
    }, [['actual_start', '实际开工'], ['actual_end', '本次实际完工']].map(([key, label]) => /*#__PURE__*/React.createElement("label", {
      key: key
    }, label, /*#__PURE__*/React.createElement("input", {
      type: "datetime-local",
      step: "60",
      "aria-label": label,
      value: draft[key],
      disabled: readonly(key),
      onChange: event => change(key, event.target.value)
    }))))), /*#__PURE__*/React.createElement("section", null, /*#__PURE__*/React.createElement("h4", null, "\u5DE5\u65F6\u6838\u5BF9"), /*#__PURE__*/React.createElement("label", null, "\u6709\u6548\u5DE5\u65F6 (h)", /*#__PURE__*/React.createElement("input", {
      type: "number",
      min: "0",
      step: "any",
      "data-wb-step": "0.1",
      "aria-label": "\u6709\u6548\u5DE5\u65F6 (h)",
      value: draft.effective_processing_hours,
      disabled: readonly('effective_processing_hours'),
      onChange: event => change('effective_processing_hours', event.target.value)
    })), /*#__PURE__*/React.createElement("p", {
      className: "field-note"
    }, "\u4F5C\u4E1A\u8DE8\u5EA6 ", /*#__PURE__*/React.createElement("output", {
      "aria-label": "\u4F5C\u4E1A\u8DE8\u5EA6"
    }, displayHours(span))), /*#__PURE__*/React.createElement("p", {
      className: "field-note",
      style: difference !== null && difference < 0 ? {
        color: 'var(--ui-danger-text)'
      } : undefined
    }, "\u5DE5\u65F6\u5DEE\u989D ", /*#__PURE__*/React.createElement("output", {
      "aria-label": "\u5DE5\u65F6\u5DEE\u989D"
    }, displayHours(difference))))), /*#__PURE__*/React.createElement("details", {
      open: action !== 'create' || !!legacy
    }, /*#__PURE__*/React.createElement("summary", null, "\u5B9E\u9645\u8BBE\u5907 / \u4EBA\u5458 / \u5907\u6CE8", record || legacy ? ' / 原因' : ''), /*#__PURE__*/React.createElement("div", {
      className: "field-extra"
    }, choices('actual_machine_ref', '实际设备', 'machine'), choices('actual_operator_ref', '实际人员', 'operator'), /*#__PURE__*/React.createElement("label", null, "\u4F5C\u4E1A\u5907\u6CE8", /*#__PURE__*/React.createElement("textarea", {
      "aria-label": "\u4F5C\u4E1A\u5907\u6CE8",
      maxLength: "2000",
      value: draft.remark,
      disabled: readonly('remark'),
      onChange: event => change('remark', event.target.value)
    })), (record || legacy) && /*#__PURE__*/React.createElement("label", null, action === 'supplement' || legacy ? '补齐原因' : '更正原因', /*#__PURE__*/React.createElement("textarea", {
      required: true,
      "aria-label": "\u8865\u9F50\u6216\u66F4\u6B63\u539F\u56E0",
      maxLength: "2000",
      value: draft.reason,
      disabled: disabled,
      onChange: event => change('reason', event.target.value)
    })), /*#__PURE__*/React.createElement("label", null, "\u73B0\u573A\u58F0\u660E\u4EBA", /*#__PURE__*/React.createElement("input", {
      "aria-label": "\u73B0\u573A\u58F0\u660E\u4EBA",
      maxLength: "2000",
      value: draft.declared_operator,
      disabled: disabled,
      onChange: event => change('declared_operator', event.target.value)
    })))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(Feedback, {
      command: command,
      onDone: onDone
    }), reason && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, reason), /*#__PURE__*/React.createElement("div", {
      className: "field-footer"
    }, /*#__PURE__*/React.createElement(Button, {
      onClick: onClose,
      disabled: command.locked
    }, "\u53D6\u6D88"), action === 'create' && !legacy && /*#__PURE__*/React.createElement(Button, {
      icon: "check-check",
      disabled: disabled || remaining === null || !!reason,
      onClick: () => {
        const value = {
          ...draft,
          completed_quantity: String(remaining)
        };
        setDraft(value);
        save(value);
      }
    }, "\u5269\u4F59\u5168\u90E8\u5B8C\u5DE5"), /*#__PURE__*/React.createElement(Button, {
      type: "submit",
      icon: "check",
      className: "btn primary",
      busy: disabled,
      reason: reason
    }, action === 'correct' ? '保存更正' : '保存报工')));
  }
  window.FieldEditor = FieldEditor;
})();
