(function () {
  'use strict';

  const C = window.OutsourcingContract,
    S = window.OutsourcingSession,
    P = window.OutsourcingControls,
    {
      Button,
      ErrorBox,
      Issues
    } = window.ResourceControls;
  function Records({
    api,
    selected,
    revision,
    onEdit,
    onClose,
    blocked
  }) {
    const [q, setQuery] = React.useState({
      page: 1,
      size: 10
    });
    const read = S.useRead(signal => api.read('history', q, selected, signal), [api, q, selected, revision]);
    const result = read.result,
      data = result && result.data,
      item = data && data.item;
    function reload() {
      const next = {
        ...q,
        page: 1
      };
      delete next.snapshot_ref;
      setQuery(next);
    }
    function change(patch, paging = false) {
      const next = {
        ...q,
        ...patch,
        page: paging ? patch.page : 1
      };
      delete next.snapshot_ref;
      if (paging) next.snapshot_ref = result.meta.snapshot_ref;
      setQuery(next);
    }
    return /*#__PURE__*/React.createElement("section", {
      className: "os-detail",
      "aria-label": "\u5916\u534F\u767B\u8BB0\u4E0E\u5386\u53F2"
    }, /*#__PURE__*/React.createElement("div", {
      className: "os-heading"
    }, /*#__PURE__*/React.createElement("h4", null, "\u767B\u8BB0\u8BE6\u60C5\u4E0E\u6838\u5B9E\u5386\u53F2"), /*#__PURE__*/React.createElement("div", {
      className: "os-tools"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u660E\u786E\u5237\u65B0\u539F\u767B\u8BB0\u5386\u53F2",
      busy: read.loading,
      onClick: reload
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": "\u6536\u8D77\u5916\u534F\u8BE6\u60C5",
      onClick: onClose
    }))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), read.loading && /*#__PURE__*/React.createElement("div", {
      className: "os-empty",
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u539F\u767B\u8BB0\u548C\u540C\u4E00\u5FEB\u7167\u5386\u53F2"), item && /*#__PURE__*/React.createElement("div", {
      "data-outsourcing-detail": item.outsourcing_ref
    }, /*#__PURE__*/React.createElement(P.Target, {
      target: item.target
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: item.issues
    }), /*#__PURE__*/React.createElement(P.Facts, {
      facts: item
    }), /*#__PURE__*/React.createElement("div", {
      className: "os-heading"
    }, /*#__PURE__*/React.createElement("span", {
      className: "os-muted"
    }, "\u6570\u636E\u622A\u81F3 ", P.when(result.meta.as_of), " \xB7 \u5DE5\u5382\u672C\u5730\u65F6\u95F4"), /*#__PURE__*/React.createElement(Button, {
      icon: "square-pen",
      disabled: blocked,
      reason: !item.can_preview ? '原来源已变化，历史保留，不能改绑新对象。' : '',
      onClick: () => onEdit(item)
    }, "\u6838\u5B9E / \u66F4\u6B63\u767B\u8BB0")), data.history.items.map((h, i) => /*#__PURE__*/React.createElement("details", {
      className: "os-history",
      key: h.fact_ref,
      "data-fact-ref": h.fact_ref
    }, /*#__PURE__*/React.createElement("summary", null, "\u7B2C ", data.history.page.total - (q.page - 1) * q.size - i, " \u6B21 \xB7 ", P.when(h.confirmed_at), " \xB7 ", h.declared_operator, " \xB7 ", C.states[h.after.confirmedState]), /*#__PURE__*/React.createElement(P.Facts, {
      facts: h.after,
      before: h.before
    }), /*#__PURE__*/React.createElement("p", null, h.reason), /*#__PURE__*/React.createElement("div", {
      className: "os-muted"
    }, "\u7CFB\u7EDF\u8BB0\u5F55\u4EBA ", h.local_operator, " \xB7 \u5386\u53F2\u5F15\u7528 ", h.fact_ref))), /*#__PURE__*/React.createElement(P.Pager, {
      page: data.history.page,
      label: "\u5916\u534F\u5386\u53F2",
      busy: read.loading,
      onPage: page => change({
        page
      }, true),
      onSize: size => change({
        size
      })
    })));
  }
  function Content({
    batchRef,
    outsourcingRef,
    onUpdated
  }) {
    const api = React.useMemo(() => C.create(), []),
      command = S.useCommand(api);
    const [q, setQuery] = React.useState(() => ({
      page: 1,
      size: 10,
      status: 'all',
      ...(batchRef ? {
        batch_ref: batchRef
      } : {})
    }));
    const [selected, setSelected] = React.useState(outsourcingRef || null),
      [dialog, setDialog] = React.useState(null),
      [revision, refresh] = React.useReducer(n => n + 1, 0);
    const read = S.useRead(signal => api.read('receipts', q, undefined, signal), [api, q, revision]);
    const result = read.result,
      data = result && result.data,
      blocked = command.busy || !!command.saved || !!command.storageError;
    function change(patch, paging = false) {
      const next = {
        ...q,
        ...patch,
        page: paging ? patch.page : 1
      };
      delete next.snapshot_ref;
      if (paging) next.snapshot_ref = result.meta.snapshot_ref;
      setQuery(next);
    }
    function reload() {
      change({});
      refresh();
    }
    function open(ref) {
      setSelected(ref);
      setDialog(null);
    }
    function finish() {
      const ref = command.saved && command.saved.phase === 'confirmed' && command.saved.receipt.data.outsourcing_ref;
      if (command.finish()) {
        setDialog(null);
        if (ref) setSelected(ref);
        reload();
        if (typeof onUpdated === 'function') onUpdated();
      }
    }
    return /*#__PURE__*/React.createElement("section", {
      className: "outsourcing-live",
      "aria-label": "\u771F\u5B9E\u5916\u534F\u767B\u8BB0",
      "data-outsourcing-workspace": true,
      "data-ready": !!data
    }, /*#__PURE__*/React.createElement(window.OutsourcingStyles, null), /*#__PURE__*/React.createElement("div", {
      className: "os-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5916\u534F\u53D1\u51FA\u4E0E\u56DE\u5382\u767B\u8BB0"), /*#__PURE__*/React.createElement("div", {
      className: "os-tools"
    }, /*#__PURE__*/React.createElement("label", null, "\u767B\u8BB0\u7B5B\u9009", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5916\u534F\u767B\u8BB0\u7B5B\u9009",
      value: q.status,
      disabled: read.loading,
      onChange: e => change({
        status: e.target.value
      })
    }, [['all', '全部登记'], ['awaiting', '待回厂'], ['overdue', '超期未回'], ['returned', '已回厂']].map(([k, label]) => /*#__PURE__*/React.createElement("option", {
      key: k,
      value: k
    }, label)))), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u660E\u786E\u5237\u65B0\u5916\u534F\u767B\u8BB0",
      busy: read.loading,
      disabled: command.busy,
      onClick: reload
    }), /*#__PURE__*/React.createElement(Button, {
      className: "btn primary",
      icon: "plus",
      disabled: blocked,
      onClick: () => setDialog({
        item: null
      })
    }, "\u65B0\u5EFA\u5916\u534F\u767B\u8BB0"))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: command.storageError
    }), command.storageError && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: command.sync
    }, "\u91CD\u8BFB\u539F\u5916\u534F\u8BF7\u6C42\u8BB0\u5F55"), command.saved && /*#__PURE__*/React.createElement("div", {
      className: "os-note warning"
    }, /*#__PURE__*/React.createElement("div", {
      className: "os-heading"
    }, /*#__PURE__*/React.createElement("span", null, command.saved.phase === 'pending' ? '存在未核实的原外协请求，不可换 key 重做。' : '原外协回执待完成核实。'), /*#__PURE__*/React.createElement(Button, {
      icon: "history",
      onClick: () => setDialog({
        item: null
      })
    }, command.saved.phase === 'confirmed' ? '查看已确认外协回执' : '核实原外协请求'))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), read.loading && /*#__PURE__*/React.createElement("div", {
      className: "os-empty",
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u5916\u534F\u771F\u5B9E\u767B\u8BB0"), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "os-muted"
    }, "\u6570\u636E\u622A\u81F3 ", P.when(result.meta.as_of), " \xB7 \u5DE5\u5382\u672C\u5730\u65F6\u95F4"), /*#__PURE__*/React.createElement("div", {
      className: "os-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "os-table"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u6279\u6B21 / \u6210\u5458"), /*#__PURE__*/React.createElement("th", null, "\u4F9B\u5E94\u5546 / \u72B6\u6001"), /*#__PURE__*/React.createElement("th", null, "\u5B9E\u9645\u53D1\u51FA"), /*#__PURE__*/React.createElement("th", null, "\u8BA1\u5212 / \u5B9E\u9645\u56DE\u5382"), /*#__PURE__*/React.createElement("th", null, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, data.items.map(r => /*#__PURE__*/React.createElement("tr", {
      key: r.outsourcing_ref,
      "data-outsourcing-ref": r.outsourcing_ref,
      "data-selected": selected === r.outsourcing_ref
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("b", null, P.value(r.target.batch.business_code), " \xB7 ", P.value(r.target.batch.label)), /*#__PURE__*/React.createElement("div", {
      className: "os-muted"
    }, r.target.kind === 'merged' ? '合并发出' : '单工序', " \xB7 ", r.target.operations.map(o => P.value(o.business_code)).join('、'))), /*#__PURE__*/React.createElement("td", null, P.value(r.target.supplier.label), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
      className: 'os-state ' + (r.overdue ? 'danger' : !r.awaiting_return ? 'success' : r.confirmedState === 'awaiting_confirmation' ? 'warning' : '')
    }, r.overdue ? '超期未回 · ' : '', C.states[r.confirmedState]))), /*#__PURE__*/React.createElement("td", null, P.when(r.sent)), /*#__PURE__*/React.createElement("td", null, P.when(r.planned), /*#__PURE__*/React.createElement("div", {
      className: "os-muted"
    }, P.when(r.returned))), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      className: "mini",
      icon: "search",
      "aria-label": '查看外协登记 ' + r.target.operations.map(o => P.value(o.business_code)).join('、'),
      onClick: () => open(r.outsourcing_ref)
    }, "\u8BE6\u60C5"))))))), !data.items.length && /*#__PURE__*/React.createElement("div", {
      className: "os-empty"
    }, data.page.total ? '当前页没有登记。' : '当前筛选没有外协登记。'), /*#__PURE__*/React.createElement(P.Pager, {
      page: data.page,
      label: "\u5916\u534F\u767B\u8BB0",
      busy: read.loading,
      onPage: page => change({
        page
      }, true),
      onSize: size => change({
        size
      })
    })), selected && /*#__PURE__*/React.createElement(Records, {
      key: selected + ':' + revision,
      api: api,
      selected: selected,
      revision: revision,
      onEdit: item => setDialog({
        item
      }),
      onClose: () => setSelected(null),
      blocked: blocked
    }), dialog && /*#__PURE__*/React.createElement(P.Editor, {
      key: command.saved ? command.saved.request_key : dialog.item ? dialog.item.latest_fact_ref : 'create',
      api: api,
      item: dialog.item,
      batchRef: batchRef,
      command: command,
      onClose: () => setDialog(null),
      onFinish: finish,
      onOpen: open
    }));
  }
  function OutsourcingWorkspace({
    batchRef,
    outsourcingRef,
    onUpdated
  }) {
    if (batchRef !== undefined && !C.ref(batchRef) || outsourcingRef !== undefined && !C.ref(outsourcingRef)) return /*#__PURE__*/React.createElement(ErrorBox, {
      error: new Error('外协登记上下文不是有效的原对象引用。')
    });
    return /*#__PURE__*/React.createElement(Content, {
      key: (batchRef || '') + ':' + (outsourcingRef || ''),
      batchRef: batchRef,
      outsourcingRef: outsourcingRef,
      onUpdated: onUpdated
    });
  }
  window.OutsourcingWorkspace = OutsourcingWorkspace;
})();
