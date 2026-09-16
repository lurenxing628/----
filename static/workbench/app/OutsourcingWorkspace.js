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
  const {
    EmptyState
  } = window.WorkbenchListControls;
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
      "aria-label": "\u5237\u65B0\u767B\u8BB0\u5386\u53F2",
      busy: read.loading,
      onClick: reload
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": "\u6536\u8D77\u5916\u534F\u8BE6\u60C5",
      onClick: onClose
    }))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), read.loading && /*#__PURE__*/React.createElement(EmptyState, {
      kind: "loading",
      title: "\u6B63\u5728\u8BFB\u53D6\u8FD9\u6761\u767B\u8BB0\u548C\u5B83\u7684\u5386\u53F2"
    }), item && /*#__PURE__*/React.createElement("div", {
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
    }, "\u6570\u636E\u622A\u81F3 ", P.when(result.meta.as_of)), /*#__PURE__*/React.createElement(Button, {
      icon: "square-pen",
      disabled: blocked,
      reason: !item.can_preview ? '来源资料已变化，请重新核对工序。' : '',
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
    }, "\u8BB0\u5F55\u4EBA ", h.local_operator), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '历史编号': h.fact_ref
      }
    }))), /*#__PURE__*/React.createElement(P.Pager, {
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
      "aria-label": "\u5916\u534F\u767B\u8BB0",
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
      "aria-label": "\u5237\u65B0\u5916\u534F\u767B\u8BB0",
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
    }, "\u65B0\u589E\u5916\u534F\u767B\u8BB0"))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: command.storageError
    }), command.storageError && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: command.sync
    }, "\u5237\u65B0\u4E0A\u6B21\u64CD\u4F5C\u8BB0\u5F55"), command.saved && /*#__PURE__*/React.createElement("div", {
      className: "os-note warning"
    }, /*#__PURE__*/React.createElement("div", {
      className: "os-heading"
    }, /*#__PURE__*/React.createElement("span", null, command.saved.phase === 'pending' ? '上次外协登记还没确认结果，不能重新提交。' : '上次外协登记的结果已经出来了，请点「完成」。'), /*#__PURE__*/React.createElement(Button, {
      icon: "history",
      onClick: () => setDialog({
        item: null
      })
    }, command.saved.phase === 'confirmed' ? '查看已确认的结果' : '查询上次登记结果'))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), read.loading && /*#__PURE__*/React.createElement(EmptyState, {
      kind: "loading",
      title: "\u6B63\u5728\u8BFB\u53D6\u5916\u534F\u767B\u8BB0"
    }), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "os-muted"
    }, "\u6570\u636E\u622A\u81F3 ", P.when(result.meta.as_of)), /*#__PURE__*/React.createElement("div", {
      className: "os-scroll os-register-scroll wb-table-shell wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "os-table wb-table"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u5916\u534F\u53D1\u51FA\u4E0E\u56DE\u5382\u767B\u8BB0"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-key"
    }, "\u6279\u6B21 / \u6210\u5458"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u4F9B\u5E94\u5546 / \u72B6\u6001"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5B9E\u9645\u53D1\u51FA"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u8BA1\u5212 / \u5B9E\u9645\u56DE\u5382"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-actions"
    }, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, data.items.map(r => /*#__PURE__*/React.createElement("tr", {
      key: r.outsourcing_ref,
      "data-outsourcing-ref": r.outsourcing_ref,
      "data-selected": selected === r.outsourcing_ref,
      "aria-selected": selected === r.outsourcing_ref
    }, /*#__PURE__*/React.createElement("td", {
      className: "wb-col-key"
    }, /*#__PURE__*/React.createElement("b", null, P.value(r.target.batch.business_code), " \xB7 ", P.value(r.target.batch.label)), /*#__PURE__*/React.createElement("div", {
      className: "os-muted"
    }, r.target.kind === 'merged' ? '合并发出' : '单工序', " \xB7 ", r.target.operations.map(o => P.value(o.business_code)).join('、'))), /*#__PURE__*/React.createElement("td", null, P.value(r.target.supplier.label), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
      className: 'os-state ' + (r.overdue ? 'danger' : !r.awaiting_return ? 'success' : r.confirmedState === 'awaiting_confirmation' ? 'warning' : '')
    }, r.overdue ? '超期未回 · ' : '', C.states[r.confirmedState]))), /*#__PURE__*/React.createElement("td", null, P.when(r.sent)), /*#__PURE__*/React.createElement("td", null, P.when(r.planned), /*#__PURE__*/React.createElement("div", {
      className: "os-muted"
    }, r.returned === null ? '未回厂' : P.when(r.returned))), /*#__PURE__*/React.createElement("td", {
      className: "wb-col-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      className: "mini",
      icon: "search",
      "aria-label": '查看外协登记 ' + r.target.operations.map(o => P.value(o.business_code)).join('、'),
      onClick: () => open(r.outsourcing_ref)
    }, "\u8BE6\u60C5"))))))), !data.items.length && /*#__PURE__*/React.createElement(EmptyState, {
      kind: q.status === 'all' ? 'empty' : 'filtered',
      title: data.page.total ? '当前页没有登记' : '当前筛选没有外协登记',
      hint: "\u53EF\u4EE5\u8C03\u6574\u7B5B\u9009\u67E5\u770B\u5DF2\u6709\u767B\u8BB0\uFF1B\u6709\u53EF\u767B\u8BB0\u7684\u5916\u534F\u5DE5\u5E8F\u65F6\u4E5F\u53EF\u4EE5\u65B0\u589E\u767B\u8BB0\u3002",
      action: q.status !== 'all' ? /*#__PURE__*/React.createElement(Button, {
        disabled: read.loading,
        onClick: () => change({
          status: 'all'
        })
      }, "\u67E5\u770B\u5168\u90E8\u767B\u8BB0") : undefined
    }), /*#__PURE__*/React.createElement(P.Pager, {
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
      error: new Error('本页数据已过期，请刷新后重试。')
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
