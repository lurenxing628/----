(function () {
  'use strict';

  const C = window.FieldContract,
    M = window.FieldDraftModel,
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
    const [initial] = React.useState(() => M.initialize({
      task,
      record,
      legacy,
      action,
      retained
    }));
    const [draft, setDraft] = React.useState(initial.draft),
      [suggestions, setSuggestions] = React.useState(initial.suggestions);
    const [error, setError] = React.useState(null),
      [continueAfter, setContinueAfter] = React.useState(false);
    const currentBaseline = {
      task_ref: task.task_ref,
      plan_ref: task.plan_ref,
      report_ref: record ? record.report_ref : null,
      revision_ref: record ? record.revision_ref : null,
      legacy_ref: legacy ? legacy.legacy_fact_ref : null
    };
    const [baseline] = React.useState(() => retained ? retained.baseline : currentBaseline);
    const changed = JSON.stringify(baseline) !== JSON.stringify(currentBaseline);
    const dirty = JSON.stringify(draft) !== JSON.stringify(initial.initialDraft);
    React.useLayoutEffect(() => {
      if (typeof onDraft === 'function') onDraft({
        draft,
        baseline,
        initialDraft: initial.initialDraft,
        suggestions,
        dirty
      });
    }, [draft, baseline, suggestions, dirty, initial, onDraft]);
    const form = React.useRef(null),
      first = React.useRef(null);
    const title = legacy ? '补齐原始完工记录' : action === 'create' ? '本次报工' : action === 'supplement' ? '补齐本次报工' : '更正报工';
    const context = record ? record.write_context : task.execution.write_context;
    const disabled = command.locked || command.phase === 'done' || changed;
    const reason = changed ? '原记录或任务已变化，暂存内容未写入；请取消后重新核对。' : C.blocked(context, action);
    const shownError = error || command.error;
    React.useEffect(() => {
      form.current.scrollIntoView({
        block: 'start',
        inline: 'nearest'
      });
      first.current.focus({
        preventScroll: true
      });
    }, []);
    React.useEffect(() => {
      if (shownError) window.ResourceControls.focusFirstInvalid(form.current);
    }, [shownError]);
    React.useEffect(() => {
      if (command.phase !== 'done' || !['committed', 'unchanged'].includes(command.result.result)) return undefined;
      const timer = setTimeout(() => onDone({
        continueAfter,
        previousContext: context,
        taskRef: task.task_ref,
        operationRef: task.operation_ref
      }), 0);
      return () => clearTimeout(timer);
    }, [command.phase, command.result, continueAfter, context, task.task_ref, task.operation_ref, onDone]);
    function change(key, value) {
      setDraft(current => ({
        ...current,
        [key]: value
      }));
      setError(null);
      setSuggestions(current => {
        const next = {
          ...current
        };
        delete next[key];
        return next;
      });
    }
    async function save(value, next = false) {
      if (disabled || reason) return;
      try {
        const input = C.input(value, record, action);
        if (legacy) {
          if (!value.reason.trim()) throw window.APSResourceContract.failure('请填写旧完工事实的补齐原因。', [{
            path: 'reason',
            message: '请填写旧完工事实的补齐原因。'
          }]);
          input.legacy_fact_ref = legacy.legacy_fact_ref;
          input.reason = value.reason.trim();
        }
        if (!form.current.reportValidity()) return;
        setError(null);
        setContinueAfter(next);
        await command.submit('execution', action, record ? record.report_ref : task.task_ref, context, input);
      } catch (failure) {
        setError(failure);
      }
    }
    function copy() {
      const value = M.copyPrevious(draft, task);
      setDraft(value);
      setError(null);
      setSuggestions(Object.fromEntries(['actual_start', 'actual_end'].filter(key => value[key]).map(key => [key, '复制自同任务上一条报工，请重新核对'])));
    }
    const remaining = task.execution.remaining_quantity,
      fresh = action === 'create' && !legacy;
    const mapped = C.fields.concat(['reason', 'declared_operator']);
    return /*#__PURE__*/React.createElement("form", {
      ref: form,
      className: "field-editor",
      "aria-label": title,
      noValidate: true,
      onSubmit: event => {
        event.preventDefault();
        save(draft);
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "field-editor-heading"
    }, /*#__PURE__*/React.createElement("h3", null, title, record ? ' · ' + record.report_no : ''), fresh && /*#__PURE__*/React.createElement(Button, {
      disabled: disabled,
      reason: !M.previous(task) ? '同任务同工序暂无可复制的有效报工。' : '',
      reasonDisplay: "inline",
      onClick: copy
    }, "\u590D\u5236\u4E0A\u4E00\u6761")), /*#__PURE__*/React.createElement(window.FieldEditorFields, {
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
      error: shownError
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error,
      excludePaths: mapped
    }), /*#__PURE__*/React.createElement(Feedback, {
      command: command,
      onDone: onDone,
      excludePaths: mapped
    }), reason && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, reason), /*#__PURE__*/React.createElement("div", {
      className: "field-footer"
    }, /*#__PURE__*/React.createElement(Button, {
      onClick: onClose,
      disabled: command.locked
    }, "\u53D6\u6D88"), fresh && /*#__PURE__*/React.createElement(Button, {
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
    }, "\u5269\u4F59\u5168\u90E8\u5B8C\u5DE5"), fresh && /*#__PURE__*/React.createElement(Button, {
      disabled: disabled,
      reason: reason,
      onClick: () => save(draft, true)
    }, "\u4FDD\u5B58\u5E76\u7EE7\u7EED"), /*#__PURE__*/React.createElement(Button, {
      type: "submit",
      icon: "check",
      className: "btn primary",
      disabled: disabled,
      busy: command.locked,
      reason: reason
    }, action === 'correct' ? '保存更正' : '保存报工')));
  }
  window.FieldEditor = FieldEditor;
})();
