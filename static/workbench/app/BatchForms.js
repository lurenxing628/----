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
      if (!result || !result.data || !Array.isArray(result.data.parts) || !result.data.parts.every(row => B.ref(row.ref))) throw C.failure('图号列表没有读到，请刷新后重试。');
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
      }, entity ? '保存基础信息' : '确认新增'))
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
    }, "\u5237\u65B0\u5E76\u6838\u5BF9"), review && /*#__PURE__*/React.createElement("div", {
      className: "batch-band"
    }, /*#__PURE__*/React.createElement(Issues, {
      issues: [{
        message: '已读到最新资料，您填写的内容没有被覆盖。'
      }]
    }), entity && /*#__PURE__*/React.createElement("dl", null, B.fields.map(key => /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, B.fieldNames[key]), /*#__PURE__*/React.createElement("dd", null, window.BatchControls.display(key, review.data.fields[key]))))), /*#__PURE__*/React.createElement(Button, {
      onClick: acceptReview,
      disabled: locked
    }, "\u91C7\u7528\u6700\u65B0\u8D44\u6599"))));
  }
  function SyncPreview({
    preview
  }) {
    const changeNames = {
      added: '新增',
      removed: '删除',
      updated: '修改',
      unchanged: '内容不变'
    };
    const operation = row => row ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, row.label, " \xB7 ", row.source === 'external' ? '外协' : '自制'), row.source === 'internal' ? /*#__PURE__*/React.createElement("div", null, "\u6362\u578B ", window.WorkbenchFormat.hours(row.setup_hours, ENTERED_HOURS), " / \u5355\u4EF6 ", window.WorkbenchFormat.hours(row.unit_hours, ENTERED_HOURS)) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, row.external_group && row.external_group.merge_mode === 'merged' ? '整组周期 ' + window.WorkbenchFormat.number(row.external_group.total_days, ENTERED_DAYS) : '本序周期 ' + window.WorkbenchFormat.number(row.external_days, ENTERED_DAYS), " \u5929"), /*#__PURE__*/React.createElement("div", null, "\u4F9B\u5E94\u5546\uFF1A", (row.supplier || row.resources && row.resources.supplier || {}).label || '未填写'))) : '—';
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "batch-sync-summary"
    }, Object.entries(changeNames).map(([key, label]) => /*#__PURE__*/React.createElement("span", {
      key: key
    }, label, " ", /*#__PURE__*/React.createElement("b", null, preview.change_counts[key]), " \u9053"))), /*#__PURE__*/React.createElement("div", {
      className: "batch-preview wb-table-frame",
      "data-sticky-head": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table batch-sync-table",
      "aria-label": "\u5DE5\u5E8F\u66F4\u65B0\u524D\u540E\u5BF9\u7167"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u5DE5\u5E8F\u66F4\u65B0\u524D\u540E\u5BF9\u7167"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 90
      }
    }, "\u5DE5\u5E8F / \u53D8\u5316"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5F53\u524D\u6279\u6B21\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u66F4\u65B0\u540E"))), /*#__PURE__*/React.createElement("tbody", null, preview.changes.map((row, index) => /*#__PURE__*/React.createElement("tr", {
      key: index
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("div", null, row.sequence, row.piece_id ? ' · ' + row.piece_id : ''), /*#__PURE__*/React.createElement("div", null, changeNames[row.change])), /*#__PURE__*/React.createElement("td", null, operation(row.before)), /*#__PURE__*/React.createElement("td", null, operation(row.after))))))), /*#__PURE__*/React.createElement("div", {
      className: "batch-sync-resources"
    }, /*#__PURE__*/React.createElement("h3", null, "\u8BBE\u5907\u548C\u4EBA\u5458\u6307\u5B9A"), preview.cleared_resources.length ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", null, "\u4EE5\u4E0B ", preview.cleared_resources.length, " \u9053\u5DE5\u5E8F\u7684\u6307\u5B9A\u5C06\u88AB\u6E05\u9664\uFF0C\u66F4\u65B0\u540E\u53EF\u91CD\u65B0\u6307\u5B9A\u3002"), /*#__PURE__*/React.createElement("ul", null, preview.cleared_resources.map(row => /*#__PURE__*/React.createElement("li", {
      key: row.operation_ref
    }, row.business_code, "\uFF1A", [row.machine && '设备 ' + row.machine.label, row.operator && '人员 ' + row.operator.label].filter(Boolean).join('；'))))) : /*#__PURE__*/React.createElement("p", null, "\u5F53\u524D\u5DE5\u5E8F\u6CA1\u6709\u8BBE\u5907\u6216\u4EBA\u5458\u6307\u5B9A\uFF0C\u65E0\u9700\u6E05\u9664\u3002")), /*#__PURE__*/React.createElement("p", null, "\u786E\u8BA4\u540E\uFF0C\u5C06\u7528\u4E0A\u8868\u4E2D\u7684\u5DE5\u827A\u5DE5\u5E8F\u66FF\u6362\u672C\u6279\u6B21\u73B0\u6709\u5DE5\u5E8F\u3002"));
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
    const deleting = action === 'bulk_confirm' && preview.action === 'delete';
    return /*#__PURE__*/React.createElement(Modal, {
      title: action === 'sync_confirm' ? '确认更新批次工序' : '确认批量' + {
        update: '修改',
        delete: '删除',
        copy: '复制'
      }[preview.action],
      icon: deleting ? 'trash-2' : 'check',
      locked: command.locked,
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: onClose,
        disabled: command.locked
      }, command.phase === 'done' ? '关闭' : '取消'), command.phase !== 'done' && /*#__PURE__*/React.createElement(Button, {
        icon: deleting ? 'trash-2' : 'check',
        className: "btn primary",
        disabled: disabled || command.locked,
        onClick: () => command.submit('batch', action, subject, preview.write_context, {
          preview_ref: preview.preview_ref
        })
      }, action === 'sync_confirm' ? '确认更新工序' : deleting ? '确认删除' : '确认变更'))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b"
    }, action === 'sync_confirm' ? /*#__PURE__*/React.createElement(SyncPreview, {
      preview: preview
    }) : /*#__PURE__*/React.createElement("div", {
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
    }, "\u786E\u8BA4\u540E"))), /*#__PURE__*/React.createElement("tbody", null, preview.rows.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.entity_ref
    }, /*#__PURE__*/React.createElement("td", null, value(row.before)), /*#__PURE__*/React.createElement("td", null, value(row.after))))))), /*#__PURE__*/React.createElement(Issues, {
      issues: preview.warnings || []
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: command,
      action: deleting ? 'delete' : 'save'
    })));
  }
  window.BatchForms = {
    BaseEditor,
    Preview
  };
})();
