(function () {
  'use strict';

  const B = window.APSBatchContract,
    C = window.APSResourceContract,
    S = window.APSResourceSession;
  const {
    Button,
    Modal,
    ErrorBox,
    Issues
  } = window.ResourceControls;
  const {
    BaseFields
  } = window.BatchControls;
  // The confirmation table shows quotas as entered (up to four decimals), never as a one-decimal summary.
  const ENTERED_HOURS = {
      digits: 4,
      trim: true
    },
    ENTERED_DAYS = {
      digits: 1,
      trim: true
    };
  function BaseEditor({
    adapter,
    entity: original,
    createContext,
    source,
    command,
    onClose,
    onCommitted,
    disabled = false
  }) {
    const [entity, setEntity] = React.useState(original),
      [value, setValue] = React.useState(() => B.draft(original));
    const [context, setContext] = React.useState(original ? original.write_context : createContext);
    const [review, setReview] = React.useState(null),
      [error, setError] = React.useState(null),
      [loading, setLoading] = React.useState(false);
    const form = React.useId(),
      action = entity ? 'update' : 'create',
      seen = React.useRef(null);
    const formElement = React.useRef(null),
      [submitted, setSubmitted] = React.useState(false);
    const paths = ['business_code', 'part_ref', ...B.fields.map(key => 'fields.' + key)];
    const currentError = error || command.error;
    const fieldErrors = [...(submitted ? B.inputErrors(value, entity) : []), ...C.fieldErrors(currentError)];
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({
      dirty: command.phase !== 'done' && JSON.stringify(value) !== JSON.stringify(B.draft(entity)),
      locked: command.locked,
      message: '批次资料尚未保存，离开会丢失本次填写。'
    });
    React.useEffect(() => {
      if (currentError) window.ResourceControls.focusFirstInvalid(formElement.current);
    }, [currentError]);
    async function close(detail) {
      if (command.locked) return;
      if (detail && detail.guardConfirmed === true && detail.guardOwner === guardOwner || (await window.WorkbenchGuards.confirmLeave({
        owner: guardOwner
      }))) onClose();
    }
    const choices = S.useQuery(async signal => {
      const result = await adapter.choices(signal);
      if (!result || !result.data || !Array.isArray(result.data.parts) || !result.data.parts.every(row => B.ref(row.ref))) throw C.failure('图号目录未能正确读取。');
      return result;
    }, [adapter], !entity);
    React.useEffect(() => {
      if (command.phase !== 'done' || seen.current === command.result.receipt_ref) return;
      try {
        B.receipt(command.result, action, entity && entity.ref);
        seen.current = command.result.receipt_ref;
        onCommitted(command.result);
      } catch (error) {
        setError(error);
      }
    }, [command.phase, command.result]);
    const locked = disabled || command.locked || command.phase === 'done' || loading;
    async function reload() {
      setLoading(true);
      setError(null);
      try {
        setReview(entity ? B.detail(await adapter.detail('batch', entity.ref), entity.ref) : B.list(await adapter.list('batch', {
          page: 1,
          size: 20,
          sort: 'business_code',
          direction: 'asc'
        }), {
          page: 1,
          size: 20,
          sort: 'business_code',
          direction: 'asc'
        }));
      } catch (error) {
        setError(error);
      } finally {
        setLoading(false);
      }
    }
    function acceptReview() {
      if (entity) {
        const next = review.data,
          previous = B.draft(entity),
          fresh = B.draft(next);
        setValue(current => Object.fromEntries(Object.keys(current).map(key => [key, current[key] === previous[key] ? fresh[key] : current[key]])));
        setEntity(next);
        setContext(next.write_context);
      } else setContext(review.data.create_context);
      setReview(null);
      setError(null);
      command.reset();
    }
    async function submit(event) {
      event.preventDefault();
      if (locked || review || B.reason(context, action, source)) return;
      setSubmitted(true);
      try {
        const payload = B.input(value, entity);
        if (!Object.keys(payload.fields).length) throw C.failure('没有需要保存的变更。');
        setError(null);
        await command.submit('batch', action, entity ? entity.ref : null, context, payload);
      } catch (error) {
        setError(error);
      }
    }
    return /*#__PURE__*/React.createElement(Modal, {
      title: entity ? '编辑批次基础信息' : '新增批次',
      icon: "box",
      guardOwner: guardOwner,
      locked: command.locked,
      onClose: close,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: close,
        disabled: command.locked
      }, command.phase === 'done' ? '关闭' : '取消'), command.phase !== 'done' && /*#__PURE__*/React.createElement(Button, {
        type: "submit",
        form: form,
        icon: "check",
        className: "btn primary",
        disabled: locked || !!review || !entity && !choices.result,
        reasonDisplay: "inline",
        reason: B.reason(context, action, source)
      }, entity ? '保存基础信息' : '创建批次'))
    }, /*#__PURE__*/React.createElement("form", {
      id: form,
      ref: formElement,
      className: "modal-b form",
      onSubmit: submit,
      noValidate: true
    }, /*#__PURE__*/React.createElement(BaseFields, {
      value: value,
      setValue: next => {
        setValue(next);
        setError(null);
      },
      entity: entity,
      disabled: locked,
      choices: choices.result && choices.result.data,
      error: currentError,
      errors: fieldErrors
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error,
      excludePaths: paths
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: choices.error
    }), /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: command,
      excludePaths: error ? [] : paths
    }), command.phase !== 'done' && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: locked,
      onClick: reload
    }, "\u91CD\u65B0\u8BFB\u53D6\u5E76\u6838\u5BF9"), review && /*#__PURE__*/React.createElement("div", {
      className: "batch-band"
    }, /*#__PURE__*/React.createElement(Issues, {
      issues: [{
        message: '最新资料已读回，未覆盖已填写内容。'
      }]
    }), entity && /*#__PURE__*/React.createElement("dl", null, B.fields.map(key => /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, B.fieldNames[key]), /*#__PURE__*/React.createElement("dd", null, window.BatchControls.display(key, review.data.fields[key]))))), /*#__PURE__*/React.createElement(Button, {
      onClick: acceptReview,
      disabled: locked
    }, "\u91C7\u7528\u6700\u65B0\u8D44\u6599\u7EE7\u7EED\u7F16\u8F91"))));
  }
  function Preview({
    preview,
    command,
    onClose,
    onCommitted,
    disabled
  }) {
    const seen = React.useRef(null),
      [error, setError] = React.useState(null);
    const action = preview.operation.split('.')[1],
      subject = action === 'bulk_confirm' ? preview.preview_ref : preview.entity_ref;
    React.useEffect(() => {
      if (command.phase !== 'done' || seen.current === command.result.receipt_ref) return;
      try {
        B.receipt(command.result, action, subject);
        seen.current = command.result.receipt_ref;
        onCommitted(command.result);
      } catch (error) {
        setError(error);
      }
    }, [command.phase, command.result]);
    const value = row => row ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, [row.business_code, row.relationships.part_no, ...B.fields.map(key => window.BatchControls.display(key, row.fields[key]))].join(' · ')), row.operations.map((op, index) => /*#__PURE__*/React.createElement("div", {
      key: index
    }, op.business_code, " \xB7 ", op.sequence, " \xB7 ", op.label, " \xB7 ", op.source === 'external' ? '外协' : '自制', " \xB7", Object.values(op.resources).filter(Boolean).map(resource => resource.label).join(' / '), " \xB7 \u6362\u578B ", window.WorkbenchFormat.hours(op.setup_hours, ENTERED_HOURS), " / \u5355\u4EF6 ", window.WorkbenchFormat.hours(op.unit_hours, ENTERED_HOURS), " / \u5468\u671F ", window.WorkbenchFormat.number(op.external_days, ENTERED_DAYS), " \xB7 ", B.label('status', op.status))), /*#__PURE__*/React.createElement("div", null, "\u7269\u6599\u9700\u6C42 ", row.relationships.material_requirement_count, " \u9879")) : '删除';
    return /*#__PURE__*/React.createElement(Modal, {
      title: action === 'sync_confirm' ? '确认刷新批次工序' : '确认批量' + {
        update: '修改',
        delete: '删除',
        copy: '复制'
      }[preview.action],
      icon: "check",
      locked: command.locked,
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: onClose,
        disabled: command.locked
      }, command.phase === 'done' ? '关闭' : '取消'), command.phase !== 'done' && /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        className: "btn primary",
        disabled: disabled || command.locked,
        onClick: () => command.submit('batch', action, subject, preview.write_context, {
          preview_ref: preview.preview_ref
        })
      }, "\u786E\u8BA4\u53D8\u66F4"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b"
    }, /*#__PURE__*/React.createElement("div", {
      className: "batch-preview wb-table-frame",
      "data-sticky-head": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u6279\u6B21\u53D8\u66F4\u524D\u540E\u5BF9\u7167"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u539F\u8BB0\u5F55"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u786E\u8BA4\u540E"))), /*#__PURE__*/React.createElement("tbody", null, action === 'bulk_confirm' ? preview.rows.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.entity_ref
    }, /*#__PURE__*/React.createElement("td", null, value(row.before)), /*#__PURE__*/React.createElement("td", null, value(row.after)))) : /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", null, preview.before.map(row => /*#__PURE__*/React.createElement("div", {
      key: row.ref
    }, row.sequence, " \xB7 ", row.label, " \xB7 ", B.label('status', row.status)))), /*#__PURE__*/React.createElement("td", null, preview.after.map((row, index) => /*#__PURE__*/React.createElement("div", {
      key: index
    }, row.sequence, " \xB7 ", row.label, " \xB7 \u6362\u578B ", window.WorkbenchFormat.hours(row.setup_hours, ENTERED_HOURS), " / \u5355\u4EF6 ", window.WorkbenchFormat.hours(row.unit_hours, ENTERED_HOURS), " / \u5468\u671F ", window.WorkbenchFormat.number(row.external_days, ENTERED_DAYS)))))))), action === 'sync_confirm' && /*#__PURE__*/React.createElement("p", null, "\u5237\u65B0\u4F1A\u66FF\u6362\u73B0\u6709\u5DE5\u5E8F\u53CA\u8D44\u6E90\u8865\u5145\uFF1B\u7F3A\u5931\u5DE5\u65F6\u4FDD\u7559\u672A\u586B\u5199\uFF0C\u5DF2\u6709\u8BA1\u5212\u6216\u6267\u884C\u5F15\u7528\u65F6\u4E0D\u80FD\u5237\u65B0\u3002"), /*#__PURE__*/React.createElement(Issues, {
      issues: preview.warnings || []
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: command
    })));
  }
  window.BatchForms = {
    BaseEditor,
    Preview
  };
})();
