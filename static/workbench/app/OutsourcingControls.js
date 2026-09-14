(function () {
  'use strict';

  const C = window.OutsourcingContract,
    S = window.OutsourcingSession,
    {
      Button,
      ErrorBox,
      Issues,
      Modal,
      Field,
      focusFirstInvalid
    } = window.ResourceControls;
  const {
    EmptyState
  } = window.WorkbenchListControls;
  const formPaths = ['sent', 'planned', 'returned', 'confirmedState', 'declared_operator', 'reason'];
  const value = v => v === null || v === undefined || v === '' ? '未填写' : typeof v === 'object' ? '原值格式不对' : String(v);
  const when = v => window.WorkbenchFormat.dateTime(v, {
    seconds: true
  });
  function Pager({
    page,
    busy,
    onPage,
    onSize,
    label
  }) {
    return /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
      page: page,
      sizes: [2, 10, 20, 50, 100].concat(page.size).filter((v, i, all) => all.indexOf(v) === i).sort((a, b) => a - b),
      label: label,
      sizeLabel: label + '每页数量',
      disabled: busy,
      onPage: onPage,
      onSize: onSize
    });
  }
  function Target({
    target
  }) {
    return /*#__PURE__*/React.createElement("section", {
      className: "os-target",
      "aria-label": "\u672C\u6B21\u5916\u534F\u6210\u5458"
    }, /*#__PURE__*/React.createElement("div", {
      className: "os-heading"
    }, /*#__PURE__*/React.createElement("b", null, value(target.batch.business_code), " \xB7 ", value(target.batch.label)), /*#__PURE__*/React.createElement("span", null, value(target.supplier.label), " \xB7 ", target.kind === 'merged' ? '合并发出' : '单工序', " \xB7 ", target.operations.length, " \u9053\u5DE5\u5E8F")), /*#__PURE__*/React.createElement("div", {
      className: "os-members"
    }, target.operations.map(o => /*#__PURE__*/React.createElement("span", {
      key: o.operation_ref
    }, value(o.business_code), " \xB7 ", value(o.label), o.piece !== null ? ' · 分件 ' + value(o.piece) : ''))));
  }
  function Facts({
    facts,
    before
  }) {
    return /*#__PURE__*/React.createElement("dl", {
      className: "os-facts"
    }, C.fields.map(k => /*#__PURE__*/React.createElement("div", {
      key: k
    }, /*#__PURE__*/React.createElement("dt", null, C.labels[k]), /*#__PURE__*/React.createElement("dd", null, before && before[k] !== facts[k] && /*#__PURE__*/React.createElement("del", null, k === 'confirmedState' ? C.states[before[k]] : k === 'returned' && before[k] === null ? '未回厂' : when(before[k])), /*#__PURE__*/React.createElement("span", null, k === 'confirmedState' ? C.states[facts[k]] : k === 'returned' && facts[k] === null ? '未回厂' : when(facts[k]))))));
  }
  function TargetPicker({
    api,
    mode,
    selected,
    onSelect,
    onMode,
    disabled,
    onOpen,
    batchRef
  }) {
    const [q, setQuery] = React.useState(() => ({
      page: 1,
      size: 10,
      ...(batchRef ? {
        batch_ref: batchRef
      } : {})
    }));
    const read = S.useRead(signal => api.read('targets', q, undefined, signal), [api, q]);
    const result = read.result,
      data = result && result.data;
    function change(patch, paging = false) {
      setQuery({
        ...q,
        ...patch,
        page: paging ? patch.page : 1,
        ...(paging ? {
          snapshot_ref: result.meta.snapshot_ref
        } : {})
      });
    }
    function reset() {
      const next = {
        ...q,
        page: 1
      };
      delete next.snapshot_ref;
      setQuery(next);
      onSelect([]);
    }
    function choose(row, checked) {
      onSelect(mode === 'single' ? [row] : checked ? selected.concat(row) : selected.filter(r => r.operation_ref !== row.operation_ref));
    }
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u9009\u62E9\u5916\u534F\u5DE5\u5E8F"
    }, /*#__PURE__*/React.createElement("div", {
      className: "os-heading"
    }, /*#__PURE__*/React.createElement("div", {
      className: "os-modes",
      role: "radiogroup",
      "aria-label": "\u53D1\u51FA\u65B9\u5F0F"
    }, [['single', '单工序'], ['merged', '合并发出']].map(([k, label]) => /*#__PURE__*/React.createElement("label", {
      key: k
    }, /*#__PURE__*/React.createElement("input", {
      type: "radio",
      name: "os-mode",
      value: k,
      checked: mode === k,
      disabled: disabled,
      onChange: () => {
        onSelect([]);
        onMode(k);
      }
    }), label))), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u53EF\u767B\u8BB0\u5DE5\u5E8F",
      busy: read.loading,
      disabled: disabled,
      onClick: reset
    })), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), read.loading && /*#__PURE__*/React.createElement(EmptyState, {
      kind: "loading",
      title: "\u6B63\u5728\u8BFB\u53D6\u5916\u534F\u5DE5\u5E8F"
    }), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "os-scroll os-pick-scroll wb-table-shell wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "os-pick-table wb-table"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u53EF\u767B\u8BB0\u7684\u5916\u534F\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-key"
    }, "\u9009\u62E9"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-key os-operation-key"
    }, "\u5DE5\u5E8F / \u540D\u79F0"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u6279\u6B21 / \u4F9B\u5E94\u5546"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-actions"
    }, "\u767B\u8BB0\u60C5\u51B5"))), /*#__PURE__*/React.createElement("tbody", null, data.items.map((r, index) => {
      const chosen = selected.some(s => s.operation_ref === r.operation_ref),
        first = selected[0];
      const other = mode === 'merged' && first && (first.batch_ref !== r.batch_ref || first.supplier_ref !== r.supplier_ref);
      return /*#__PURE__*/React.createElement("tr", {
        key: r.operation_ref || index,
        "data-target-ref": r.operation_ref,
        "data-selected": chosen,
        "aria-selected": chosen
      }, /*#__PURE__*/React.createElement("td", {
        className: "wb-col-key"
      }, /*#__PURE__*/React.createElement("input", {
        type: mode === 'single' ? 'radio' : 'checkbox',
        name: "os-member",
        "aria-label": '选择工序 ' + value(r.business_code),
        checked: chosen,
        disabled: disabled || !r.can_register || !!other || !chosen && selected.length >= 200,
        onChange: e => choose(r, e.target.checked)
      })), /*#__PURE__*/React.createElement("td", {
        className: "wb-col-key os-operation-key"
      }, /*#__PURE__*/React.createElement("b", null, value(r.business_code)), /*#__PURE__*/React.createElement("div", null, value(r.label))), /*#__PURE__*/React.createElement("td", null, r.batch ? (r.batch.business_code || '编号未填写') + ' · ' + (r.batch.label || '名称未填写') : '批次未读取', /*#__PURE__*/React.createElement("div", {
        className: "os-muted"
      }, r.supplier && r.supplier.label || '供应商名称未填写')), /*#__PURE__*/React.createElement("td", {
        className: "wb-col-actions"
      }, r.outsourcing_ref ? /*#__PURE__*/React.createElement(Button, {
        className: "mini",
        icon: "arrow-right",
        disabled: disabled,
        onClick: () => onOpen(r.outsourcing_ref)
      }, "\u6253\u5F00\u5DF2\u6709\u767B\u8BB0") : r.can_register ? other ? '不同批次 / 供应商' : '可登记' : '不可登记', /*#__PURE__*/React.createElement(Issues, {
        issues: r.issues
      })));
    })))), !data.items.length && /*#__PURE__*/React.createElement(EmptyState, {
      kind: "empty",
      title: "\u6CA1\u6709\u53EF\u8BFB\u53D6\u7684\u5916\u534F\u5DE5\u5E8F",
      hint: "\u53EF\u5237\u65B0\u5DE5\u5E8F\u5217\u8868\uFF0C\u6216\u8FD4\u56DE\u8D44\u6E90\u8D44\u6599\u6838\u5BF9\u5916\u534F\u5DE5\u827A\u3002"
    }), /*#__PURE__*/React.createElement(Pager, {
      page: data.page,
      label: "\u5DE5\u5E8F",
      busy: disabled || read.loading,
      onPage: page => change({
        page
      }, true)
    }), /*#__PURE__*/React.createElement("div", {
      className: "os-selected",
      "aria-label": "\u5DF2\u9009\u62E9\u6210\u5458"
    }, /*#__PURE__*/React.createElement("b", null, "\u5DF2\u9009 ", selected.length, " \u9053"), selected.map(r => /*#__PURE__*/React.createElement("span", {
      key: r.operation_ref
    }, value(r.business_code), " \xB7 ", value(r.label), /*#__PURE__*/React.createElement(Button, {
      className: "mini",
      icon: "x",
      "aria-label": '移除工序 ' + value(r.business_code),
      disabled: disabled,
      onClick: () => onSelect(selected.filter(s => s.operation_ref !== r.operation_ref))
    }))))));
  }
  function FormFields({
    draft,
    update,
    disabled,
    error
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "os-form"
    }, ['sent', 'planned', 'returned'].map(k => /*#__PURE__*/React.createElement(Field, {
      key: k,
      label: C.labels[k],
      path: k,
      error: error,
      required: k !== 'returned'
    }, /*#__PURE__*/React.createElement("input", {
      type: "datetime-local",
      step: "1",
      "aria-label": C.labels[k],
      value: draft[k],
      disabled: disabled,
      onChange: e => update(k, e.target.value)
    }))), /*#__PURE__*/React.createElement(Field, {
      label: "\u786E\u8BA4\u72B6\u6001",
      path: "confirmedState",
      error: error,
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5916\u534F\u786E\u8BA4\u72B6\u6001",
      value: draft.confirmedState,
      disabled: disabled,
      onChange: e => update('confirmedState', e.target.value)
    }, Object.entries(C.states).map(([k, label]) => /*#__PURE__*/React.createElement("option", {
      key: k,
      value: k
    }, label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u7ECF\u529E\u4EBA",
      path: "declared_operator",
      error: error,
      required: true
    }, /*#__PURE__*/React.createElement("input", {
      type: "text",
      "aria-label": "\u5916\u534F\u7ECF\u529E\u4EBA",
      maxLength: 200,
      value: draft.declared_operator,
      disabled: disabled,
      onChange: e => update('declared_operator', e.target.value)
    })), /*#__PURE__*/React.createElement("div", {
      className: "os-clear"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      disabled: disabled || !draft.returned,
      onClick: () => update('returned', '')
    }, "\u6E05\u9664\u5B9E\u9645\u56DE\u5382")), /*#__PURE__*/React.createElement(Field, {
      label: "\u672C\u6B21\u6838\u5B9E / \u66F4\u6B63\u539F\u56E0",
      path: "reason",
      error: error,
      required: true,
      full: true
    }, /*#__PURE__*/React.createElement("textarea", {
      "aria-label": "\u5916\u534F\u6838\u5B9E\u539F\u56E0",
      maxLength: 2000,
      value: draft.reason,
      disabled: disabled,
      onChange: e => update('reason', e.target.value)
    })));
  }
  function Pending({
    command
  }) {
    const v = command.saved,
      done = v.phase === 'confirmed';
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Target, {
      target: v.target
    }), /*#__PURE__*/React.createElement(Facts, {
      facts: v.after
    }), /*#__PURE__*/React.createElement("div", {
      className: 'os-note ' + (done ? 'success' : 'warning'),
      role: "status"
    }, done ? window.WorkbenchTerms.outcomes.done('外协登记', '回厂不等于工序完工') : v.phase === 'rejected' ? '上次外协登记没有生效，填写内容已保留。改好后重新提交。' : window.WorkbenchTerms.outcomes.pending('外协登记')), /*#__PURE__*/React.createElement("div", {
      "data-original-key": true
    }, /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '操作编号': v.request_key
      }
    })), /*#__PURE__*/React.createElement("dl", {
      className: "os-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u7ECF\u529E\u4EBA"), /*#__PURE__*/React.createElement("dd", null, v.input.declared_operator)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6838\u5B9E\u539F\u56E0"), /*#__PURE__*/React.createElement("dd", null, v.input.reason)), done && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u8BB0\u5F55\u4EBA"), /*#__PURE__*/React.createElement("dd", null, v.receipt.data.local_operator)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u786E\u8BA4\u65F6\u95F4"), /*#__PURE__*/React.createElement("dd", null, when(v.receipt.data.confirmed_at))))));
  }
  function Editor({
    api,
    item,
    command,
    onClose,
    onFinish,
    onOpen,
    batchRef
  }) {
    const [draft, setDraft] = React.useState(() => ({
      kind: 'single',
      sent: item ? item.sent : '',
      planned: item ? item.planned : '',
      returned: item && item.returned || '',
      confirmedState: item ? item.confirmedState : 'in_transit',
      declared_operator: '',
      reason: ''
    }));
    const [selected, setSelected] = React.useState([]),
      [preview, setPreview] = React.useState(null),
      [error, setError] = React.useState(null),
      [busy, setBusy] = React.useState(false);
    const alive = React.useRef(false),
      running = React.useRef(false),
      formRef = React.useRef(null),
      errorRef = React.useRef(null),
      initialDraft = React.useRef(JSON.stringify(draft)),
      editorId = React.useId();
    React.useEffect(() => {
      alive.current = true;
      return () => {
        alive.current = false;
      };
    }, []);
    const locked = busy || command.busy,
      saved = command.saved;
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({
      owner: 'outsourcing-' + editorId,
      dirty: !saved && (selected.length > 0 || JSON.stringify(draft) !== initialDraft.current),
      locked: command.busy,
      message: '外协登记有尚未保存的填写内容。'
    });
    async function close() {
      if (!locked && (await window.WorkbenchGuards.confirmLeave({
        owner: guardOwner
      }))) onClose();
    }
    async function openExisting(ref) {
      if (!locked && (await window.WorkbenchGuards.confirmLeave({
        owner: guardOwner
      }))) onOpen(ref);
    }
    React.useEffect(() => {
      if (error && !focusFirstInvalid(formRef.current) && errorRef.current) errorRef.current.focus();
    }, [error]);
    function update(k, v) {
      setDraft(d => ({
        ...d,
        [k]: v
      }));
      setPreview(null);
      setError(null);
    }
    async function review() {
      if (running.current || saved || command.storageError) return;
      running.current = true;
      setBusy(true);
      setError(null);
      try {
        const p = S.input(draft, selected, item),
          result = await api.preview(p);
        if (alive.current) setPreview(result);
      } catch (e) {
        if (alive.current) setError(e);
      } finally {
        running.current = false;
        if (alive.current) setBusy(false);
      }
    }
    const footer = saved ? /*#__PURE__*/React.createElement(React.Fragment, null, saved.phase === 'pending' ? /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      busy: command.busy,
      onClick: command.lookup
    }, "\u67E5\u8BE2\u7ED3\u679C") : /*#__PURE__*/React.createElement(Button, {
      className: "btn primary",
      icon: "check",
      disabled: locked,
      onClick: onFinish
    }, "\u5B8C\u6210")) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      disabled: locked,
      onClick: close
    }, "\u53D6\u6D88"), preview ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      icon: "square-pen",
      disabled: locked,
      onClick: () => setPreview(null)
    }, "\u8FD4\u56DE\u4FEE\u6539"), /*#__PURE__*/React.createElement(Button, {
      className: "btn primary",
      icon: "check",
      busy: locked,
      disabled: !!command.storageError,
      onClick: () => command.submit(preview)
    }, "\u786E\u8BA4\u4FDD\u5B58\u5916\u534F\u767B\u8BB0")) : /*#__PURE__*/React.createElement(Button, {
      className: "btn primary",
      icon: "search",
      busy: locked,
      disabled: !!command.storageError,
      onClick: review
    }, "\u9884\u68C0\u6838\u5BF9"));
    return /*#__PURE__*/React.createElement(Modal, {
      title: saved ? '外协登记结果' : item ? '核实 / 更正外协登记' : '新增外协登记',
      icon: "truck",
      onClose: onClose,
      guardOwner: guardOwner,
      locked: locked,
      footer: footer
    }, /*#__PURE__*/React.createElement("div", {
      className: "os-dialog-body",
      ref: formRef
    }, /*#__PURE__*/React.createElement("div", {
      tabIndex: -1,
      ref: errorRef
    }, /*#__PURE__*/React.createElement(ErrorBox, {
      error: command.storageError || error || command.error,
      excludePaths: saved || preview ? [] : formPaths
    })), saved ? /*#__PURE__*/React.createElement(Pending, {
      command: command
    }) : preview ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Target, {
      target: preview.data.target
    }), /*#__PURE__*/React.createElement(Facts, {
      facts: preview.data.after,
      before: preview.data.before
    }), /*#__PURE__*/React.createElement("dl", {
      className: "os-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u7ECF\u529E\u4EBA"), /*#__PURE__*/React.createElement("dd", null, preview.data.input.declared_operator)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6838\u5B9E\u539F\u56E0"), /*#__PURE__*/React.createElement("dd", null, preview.data.input.reason))), /*#__PURE__*/React.createElement("div", {
      className: "os-note"
    }, preview.data.execution.reason), /*#__PURE__*/React.createElement("div", {
      className: "os-muted"
    }, "\u6838\u5BF9\u65F6\u70B9 ", when(preview.meta.as_of))) : /*#__PURE__*/React.createElement(React.Fragment, null, item ? /*#__PURE__*/React.createElement(Target, {
      target: item.target
    }) : /*#__PURE__*/React.createElement(TargetPicker, {
      api: api,
      mode: draft.kind,
      selected: selected,
      onSelect: setSelected,
      onMode: v => update('kind', v),
      disabled: locked,
      onOpen: openExisting,
      batchRef: batchRef
    }), /*#__PURE__*/React.createElement(FormFields, {
      draft: draft,
      update: update,
      disabled: locked,
      error: error
    })), command.notice && /*#__PURE__*/React.createElement("div", {
      className: "os-note",
      role: "status"
    }, command.notice)));
  }
  window.OutsourcingControls = {
    value,
    when,
    Pager,
    Target,
    Facts,
    TargetPicker,
    FormFields,
    Pending,
    Editor
  };
})();
