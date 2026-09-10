(function () {
  'use strict';

  const C = window.OutsourcingContract,
    S = window.OutsourcingSession,
    {
      Button,
      ErrorBox,
      Issues,
      Modal
    } = window.ResourceControls;
  const value = v => v === null || v === undefined || v === '' ? '未填写' : typeof v === 'object' ? '原值格式待核实' : String(v);
  const when = v => v ? value(v).replace('T', ' ') : '未回厂';
  function Pager({
    page,
    busy,
    onPage,
    onSize,
    label
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "os-pager"
    }, /*#__PURE__*/React.createElement("span", null, page.total, " \u9879 \xB7 \u7B2C ", page.number, " / ", Math.max(1, page.pages), " \u9875"), onSize && /*#__PURE__*/React.createElement("label", null, "\u6BCF\u9875", /*#__PURE__*/React.createElement("select", {
      "aria-label": label + '每页数量',
      value: page.size,
      disabled: busy,
      onChange: e => onSize(Number(e.target.value))
    }, [2, 10, 20, 50, 100].concat(page.size).filter((v, i, a) => a.indexOf(v) === i).sort((a, b) => a - b).map(n => /*#__PURE__*/React.createElement("option", {
      key: n
    }, n)))), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      "aria-label": label + '上一页',
      disabled: busy || page.number <= 1,
      onClick: () => onPage(page.number - 1)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      "aria-label": label + '下一页',
      disabled: busy || page.number >= page.pages,
      onClick: () => onPage(page.number + 1)
    }));
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
    }, /*#__PURE__*/React.createElement("dt", null, C.labels[k]), /*#__PURE__*/React.createElement("dd", null, before && before[k] !== facts[k] && /*#__PURE__*/React.createElement("del", null, k === 'confirmedState' ? C.states[before[k]] : when(before[k])), /*#__PURE__*/React.createElement("span", null, k === 'confirmedState' ? C.states[facts[k]] : when(facts[k]))))));
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
      "aria-label": "\u9009\u62E9\u771F\u5B9E\u5916\u534F\u5DE5\u5E8F"
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
      "aria-label": "\u660E\u786E\u5237\u65B0\u53EF\u767B\u8BB0\u5DE5\u5E8F",
      busy: read.loading,
      disabled: disabled,
      onClick: reset
    })), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), read.loading && /*#__PURE__*/React.createElement("div", {
      className: "os-empty",
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u771F\u5B9E\u5916\u534F\u5DE5\u5E8F"), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "os-scroll os-pick-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "os-pick-table"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u9009\u62E9"), /*#__PURE__*/React.createElement("th", null, "\u5DE5\u5E8F / \u540D\u79F0"), /*#__PURE__*/React.createElement("th", null, "\u6279\u6B21 / \u4F9B\u5E94\u5546"), /*#__PURE__*/React.createElement("th", null, "\u767B\u8BB0\u60C5\u51B5"))), /*#__PURE__*/React.createElement("tbody", null, data.items.map((r, index) => {
      const chosen = selected.some(s => s.operation_ref === r.operation_ref),
        first = selected[0];
      const other = mode === 'merged' && first && (first.batch_ref !== r.batch_ref || first.supplier_ref !== r.supplier_ref);
      return /*#__PURE__*/React.createElement("tr", {
        key: r.operation_ref || index,
        "data-target-ref": r.operation_ref,
        "data-selected": chosen
      }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("input", {
        type: mode === 'single' ? 'radio' : 'checkbox',
        name: "os-member",
        "aria-label": '选择工序 ' + value(r.business_code),
        checked: chosen,
        disabled: disabled || !r.can_register || !!other || !chosen && selected.length >= 200,
        onChange: e => choose(r, e.target.checked)
      })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("b", null, value(r.business_code)), /*#__PURE__*/React.createElement("div", null, value(r.label))), /*#__PURE__*/React.createElement("td", null, r.batch ? (r.batch.business_code || '批次编号未知') + ' · ' + (r.batch.label || '批次名称未知') : '批次名称未知', /*#__PURE__*/React.createElement("div", {
        className: "os-muted"
      }, r.supplier && r.supplier.label || '供应商名称未知')), /*#__PURE__*/React.createElement("td", null, r.outsourcing_ref ? /*#__PURE__*/React.createElement(Button, {
        className: "mini",
        icon: "arrow-right",
        disabled: disabled,
        onClick: () => onOpen(r.outsourcing_ref)
      }, "\u6253\u5F00\u539F\u767B\u8BB0") : r.can_register ? other ? '不同批次 / 供应商' : '可登记' : '不可登记', /*#__PURE__*/React.createElement(Issues, {
        issues: r.issues
      })));
    }))), !data.items.length && /*#__PURE__*/React.createElement("div", {
      className: "os-empty"
    }, "\u6CA1\u6709\u53EF\u8BFB\u53D6\u7684\u5916\u534F\u5DE5\u5E8F\u3002")), /*#__PURE__*/React.createElement(Pager, {
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
    disabled
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "os-form"
    }, ['sent', 'planned', 'returned'].map(k => /*#__PURE__*/React.createElement("label", {
      key: k
    }, C.labels[k], /*#__PURE__*/React.createElement("input", {
      type: "datetime-local",
      step: "1",
      "aria-label": C.labels[k],
      value: draft[k],
      disabled: disabled,
      onChange: e => update(k, e.target.value)
    }))), /*#__PURE__*/React.createElement("label", null, "\u786E\u8BA4\u72B6\u6001", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5916\u534F\u786E\u8BA4\u72B6\u6001",
      value: draft.confirmedState,
      disabled: disabled,
      onChange: e => update('confirmedState', e.target.value)
    }, Object.entries(C.states).map(([k, label]) => /*#__PURE__*/React.createElement("option", {
      key: k,
      value: k
    }, label)))), /*#__PURE__*/React.createElement("label", null, "\u58F0\u660E\u4EBA", /*#__PURE__*/React.createElement("input", {
      type: "text",
      "aria-label": "\u5916\u534F\u58F0\u660E\u4EBA",
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
    }, "\u6E05\u7A7A\u5B9E\u9645\u56DE\u5382")), /*#__PURE__*/React.createElement("label", {
      className: "wide"
    }, "\u672C\u6B21\u6838\u5B9E / \u66F4\u6B63\u539F\u56E0", /*#__PURE__*/React.createElement("textarea", {
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
    }, done ? '已确认：外协登记已保存，回厂不等于工序完工。' : v.phase === 'rejected' ? '本次明确未写入。' : '结果尚未确认，仅查询原请求。'), /*#__PURE__*/React.createElement("dl", {
      className: "os-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u539F\u8BF7\u6C42"), /*#__PURE__*/React.createElement("dd", {
      "data-original-key": true
    }, v.request_key)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u58F0\u660E\u4EBA"), /*#__PURE__*/React.createElement("dd", null, v.input.declared_operator)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6838\u5B9E\u539F\u56E0"), /*#__PURE__*/React.createElement("dd", null, v.input.reason)), done && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u7CFB\u7EDF\u8BB0\u5F55\u4EBA"), /*#__PURE__*/React.createElement("dd", null, v.receipt.data.local_operator)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u786E\u8BA4\u65F6\u95F4"), /*#__PURE__*/React.createElement("dd", null, when(v.receipt.data.confirmed_at))))));
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
      running = React.useRef(false);
    React.useEffect(() => {
      alive.current = true;
      return () => {
        alive.current = false;
      };
    }, []);
    const locked = busy || command.busy,
      saved = command.saved;
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
    }, "\u67E5\u8BE2\u539F\u56DE\u6267") : /*#__PURE__*/React.createElement(Button, {
      className: "btn primary",
      icon: "check",
      disabled: locked,
      onClick: onFinish
    }, "\u5B8C\u6210\u6838\u5B9E\u5E76\u5237\u65B0")) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      disabled: locked,
      onClick: onClose
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
    }, "\u9884\u89C8\u6838\u5BF9"));
    return /*#__PURE__*/React.createElement(Modal, {
      title: saved ? '外协登记回执' : item ? '核实 / 更正外协登记' : '新建外协登记',
      icon: "truck",
      onClose: onClose,
      locked: locked,
      footer: footer
    }, /*#__PURE__*/React.createElement("div", {
      className: "os-dialog-body"
    }, /*#__PURE__*/React.createElement(ErrorBox, {
      error: command.storageError || error || command.error
    }), saved ? /*#__PURE__*/React.createElement(Pending, {
      command: command
    }) : preview ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Target, {
      target: preview.data.target
    }), /*#__PURE__*/React.createElement(Facts, {
      facts: preview.data.after,
      before: preview.data.before
    }), /*#__PURE__*/React.createElement("dl", {
      className: "os-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u58F0\u660E\u4EBA"), /*#__PURE__*/React.createElement("dd", null, preview.data.input.declared_operator)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6838\u5B9E\u539F\u56E0"), /*#__PURE__*/React.createElement("dd", null, preview.data.input.reason))), /*#__PURE__*/React.createElement("div", {
      className: "os-note"
    }, preview.data.execution.reason), /*#__PURE__*/React.createElement("div", {
      className: "os-muted"
    }, "\u6838\u5BF9\u65F6\u70B9 ", when(preview.meta.as_of), " \xB7 \u5DE5\u5382\u672C\u5730\u65F6\u95F4")) : /*#__PURE__*/React.createElement(React.Fragment, null, item ? /*#__PURE__*/React.createElement(Target, {
      target: item.target
    }) : /*#__PURE__*/React.createElement(TargetPicker, {
      api: api,
      mode: draft.kind,
      selected: selected,
      onSelect: setSelected,
      onMode: v => update('kind', v),
      disabled: locked,
      onOpen: onOpen,
      batchRef: batchRef
    }), /*#__PURE__*/React.createElement(FormFields, {
      draft: draft,
      update: update,
      disabled: locked
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
