(function () {
  'use strict';

  const C = window.FieldContract,
    {
      Button,
      ErrorBox,
      Feedback
    } = window.FieldControls;
  function FieldVoidEditor({
    task,
    record,
    adapter,
    command,
    retained,
    onDraft,
    onClose,
    onDone
  }) {
    const [draft, setDraft] = React.useState(() => retained ? retained.draft : {
      reason: '',
      declared_operator: ''
    });
    const [baseline] = React.useState(() => retained ? retained.baseline : {
      report_ref: record.report_ref,
      revision_ref: record.revision_ref
    });
    const [preview, setPreview] = React.useState(null),
      [error, setError] = React.useState(null),
      [reading, setReading] = React.useState(false);
    const form = React.useRef(null),
      inputRef = React.useRef(null),
      request = React.useRef(null);
    const changed = baseline.report_ref !== record.report_ref || baseline.revision_ref !== record.revision_ref;
    const locked = command.locked || command.phase === 'done' || reading || changed;
    React.useLayoutEffect(() => {
      if (onDraft) onDraft({
        draft,
        baseline,
        dirty: !!(draft.reason || draft.declared_operator)
      });
    }, [draft, baseline, onDraft]);
    React.useEffect(() => {
      form.current.scrollIntoView({
        block: 'start',
        inline: 'nearest'
      });
      inputRef.current.focus({
        preventScroll: true
      });
      return () => {
        if (request.current) request.current.abort();
      };
    }, []);
    React.useEffect(() => {
      if (command.phase !== 'done' || !['committed', 'unchanged'].includes(command.result.result)) return undefined;
      const timer = setTimeout(() => onDone({
        taskRef: task.task_ref,
        operationRef: task.operation_ref
      }), 0);
      return () => clearTimeout(timer);
    }, [command.phase, command.result, task.task_ref, task.operation_ref, onDone]);
    const input = () => ({
      original_revision_ref: baseline.revision_ref,
      reason: draft.reason.trim(),
      declared_operator: draft.declared_operator.trim()
    });
    function change(key, value) {
      setDraft(current => ({
        ...current,
        [key]: value
      }));
      setPreview(null);
      setError(null);
    }
    async function inspect() {
      if (locked || !form.current.reportValidity()) return;
      const controller = new AbortController();
      request.current = controller;
      setReading(true);
      setError(null);
      try {
        const result = await adapter.previewVoid(record.report_ref, input(), controller.signal),
          value = result.data;
        if (!value || !value.target_report || value.target_report.report_ref !== record.report_ref || value.target_report.original_revision_ref !== baseline.revision_ref || !value.before || !value.after || !Array.isArray(value.downstream_impacts) || typeof value.can_confirm !== 'boolean' || !value.write_context) throw window.APSResourceContract.failure('撤销预览与原报工不一致，请刷新后重试。');
        setPreview(value);
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure);
      } finally {
        if (!controller.signal.aborted) setReading(false);
      }
    }
    async function save() {
      if (locked || !preview || !preview.can_confirm || !form.current.reportValidity()) return;
      await command.submit('execution', 'report_void', record.report_ref, preview.write_context, input());
    }
    return /*#__PURE__*/React.createElement("form", {
      ref: form,
      className: "field-editor",
      "aria-label": "\u64A4\u9500\u8FD9\u6B21\u62A5\u5DE5",
      onSubmit: event => {
        event.preventDefault();
        inspect();
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "field-editor-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u64A4\u9500\u8FD9\u6B21\u62A5\u5DE5 \xB7 ", record.report_no)), /*#__PURE__*/React.createElement("p", null, "\u672C\u6B21\u6570\u91CF ", C.display(record.completed_quantity), " \u4EF6 \xB7 \u6709\u6548\u5DE5\u65F6 ", C.display(record.effective_processing_hours), " \u5C0F\u65F6\u3002\u64A4\u9500\u540E\u4E0D\u518D\u8BA1\u5165\u8FDB\u5EA6\u548C\u5DE5\u65F6\uFF0C\u539F\u8BB0\u5F55\u53CA\u66F4\u6B63\u5386\u53F2\u4FDD\u7559\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "field-extra"
    }, /*#__PURE__*/React.createElement(window.ResourceControls.Field, {
      label: "\u64A4\u9500\u539F\u56E0",
      path: "reason",
      error: error,
      required: true
    }, /*#__PURE__*/React.createElement("textarea", {
      ref: inputRef,
      "aria-label": "\u64A4\u9500\u539F\u56E0",
      required: true,
      maxLength: "2000",
      value: draft.reason,
      disabled: locked,
      onChange: event => change('reason', event.target.value)
    })), /*#__PURE__*/React.createElement(window.ResourceControls.Field, {
      label: "\u7ECF\u529E\u4EBA",
      path: "declared_operator",
      error: error
    }, /*#__PURE__*/React.createElement("input", {
      "aria-label": "\u64A4\u9500\u7ECF\u529E\u4EBA",
      maxLength: "2000",
      value: draft.declared_operator,
      disabled: locked,
      onChange: event => change('declared_operator', event.target.value)
    }))), preview && /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u64A4\u9500\u5F71\u54CD",
      className: "field-note"
    }, /*#__PURE__*/React.createElement("h4", null, "\u64A4\u9500\u540E"), /*#__PURE__*/React.createElement("p", null, "\u7D2F\u8BA1\u5B8C\u6210 ", C.quantity(preview.before.known_completed_quantity), " \u2192 ", C.quantity(preview.after.known_completed_quantity), " \u4EF6\uFF1B\u5269\u4F59 ", C.quantity(preview.after.remaining_quantity), " \u4EF6\uFF1B\u72B6\u6001 ", C.states[preview.after.execution_state], "\u3002"), preview.downstream_impacts.length > 0 && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      role: "alert"
    }, "\u4EE5\u4E0B\u5173\u8054\u8BB0\u5F55\u9700\u8981\u5148\u5904\u7406\uFF0C\u672C\u6B21\u4E0D\u80FD\u64A4\u9500\uFF1A"), /*#__PURE__*/React.createElement("ul", null, preview.downstream_impacts.map((item, index) => /*#__PURE__*/React.createElement("li", {
      key: index
    }, item.operation_label, "\uFF1A", item.message)))), preview.state === 'voided' && /*#__PURE__*/React.createElement("p", null, "\u8FD9\u6761\u62A5\u5DE5\u5DF2\u7ECF\u64A4\u9500\uFF0C\u4E0D\u4F1A\u91CD\u590D\u6263\u51CF\u3002")), changed && /*#__PURE__*/React.createElement("p", {
      role: "alert"
    }, "\u539F\u62A5\u5DE5\u5DF2\u53D8\u5316\uFF0C\u8BF7\u53D6\u6D88\u540E\u91CD\u65B0\u9009\u62E9\u3002"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(Feedback, {
      command: command,
      onDone: onDone
    }), /*#__PURE__*/React.createElement("div", {
      className: "field-footer"
    }, /*#__PURE__*/React.createElement(Button, {
      onClick: onClose,
      disabled: command.locked || reading
    }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
      type: "submit",
      icon: "search",
      busy: reading,
      disabled: locked
    }, "\u67E5\u770B\u64A4\u9500\u5F71\u54CD"), preview && /*#__PURE__*/React.createElement(Button, {
      icon: "rotate-ccw",
      className: "btn danger",
      disabled: locked || !preview.can_confirm,
      onClick: save
    }, "\u786E\u8BA4\u64A4\u9500\u8FD9\u6B21\u62A5\u5DE5")));
  }
  window.FieldVoidEditor = FieldVoidEditor;
})();
