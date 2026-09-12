(function () {
  'use strict';

  const C = window.DashboardContract,
    P = window.DashboardPanels,
    {
      Button,
      ErrorBox
    } = window.ResourceControls;
  function History({
    read,
    selected,
    historyPage,
    onPage,
    onSelect,
    rows,
    onHandle
  }) {
    const [source, setSource] = React.useState(''),
      result = read.result,
      history = result && result.data.history,
      item = result && result.data.item;
    React.useEffect(() => setSource(''), [selected]);
    const options = rows.slice();
    if (item && !options.some(r => r.item_ref === item.item_ref)) options.push(item);
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5904\u7F6E\u5386\u53F2"
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-filters"
    }, /*#__PURE__*/React.createElement("label", {
      className: "dy-search"
    }, "\u5386\u53F2\u6761\u76EE", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u9009\u62E9\u5386\u53F2\u6761\u76EE",
      value: selected || '',
      onChange: e => onSelect(e.target.value || null)
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u8BF7\u9009\u62E9\u6761\u76EE"), options.map(row => /*#__PURE__*/React.createElement("option", {
      key: row.item_ref,
      value: row.item_ref
    }, row.subject, " \xB7 ", C.categories[row.category])))), item && /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      icon: item.handling.status === 'closed' ? 'refresh-cw' : 'square-pen',
      onClick: onHandle
    }, item.handling.status === 'closed' ? '独立重开' : '调整当前处置')), item && /*#__PURE__*/React.createElement("div", {
      className: "dy-tools"
    }, /*#__PURE__*/React.createElement(P.Risk, {
      risk: item.risk
    }), /*#__PURE__*/React.createElement(P.Status, {
      handling: item.handling
    }), /*#__PURE__*/React.createElement("span", null, "\u5F53\u524D\u5904\u7F6E\uFF0C\u975E\u5386\u53F2\u72B6\u6001")), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), read.loading && /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "loading",
      title: "\u6B63\u5728\u8BFB\u53D6\u539F\u6761\u76EE\u5386\u53F2"
    }), !selected && /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "empty",
      title: "\u5C1A\u672A\u9009\u62E9\u5386\u53F2\u6761\u76EE\u3002"
    }), history && /*#__PURE__*/React.createElement(React.Fragment, null, !history.items.length && /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "empty",
      title: "\u8BE5\u6761\u76EE\u5C1A\u65E0\u5904\u7F6E\u5386\u53F2\u3002"
    }), history.items.map(h => /*#__PURE__*/React.createElement("article", {
      className: "dy-history",
      key: h.history_ref,
      "data-history-sequence": h.sequence
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-heading"
    }, /*#__PURE__*/React.createElement("b", null, "\u7B2C ", h.sequence, " \u6B21 \xB7 ", C.statuses[h.before.status], " \u2192 ", C.statuses[h.after.status], h.action === 'reopen' ? ' · 独立重开' : ''), /*#__PURE__*/React.createElement("time", null, window.WorkbenchFormat.dateTime(h.recorded_at))), /*#__PURE__*/React.createElement("p", null, h.action === 'reopen' ? '重开原因：' + h.reason : '核实备注：' + h.after.remark), /*#__PURE__*/React.createElement("div", {
      className: "dy-muted"
    }, "\u767B\u8BB0\u4EBA ", h.local_operator), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '回执编号': h.receipt_ref
      }
    }), /*#__PURE__*/React.createElement("details", {
      className: "dy-evidence"
    }, /*#__PURE__*/React.createElement("summary", null, "\u53D8\u66F4\u524D\u540E\u53CA\u5B8C\u6210\u51ED\u636E"), /*#__PURE__*/React.createElement("div", {
      className: "dy-scroll"
    }, /*#__PURE__*/React.createElement("table", null, /*#__PURE__*/React.createElement("caption", {
      className: "wb-sr-only"
    }, "\u5904\u7F6E\u5B57\u6BB5\u53D8\u66F4\u8BB0\u5F55"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5B57\u6BB5"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u53D8\u66F4\u524D"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u53D8\u66F4\u540E"))), /*#__PURE__*/React.createElement("tbody", null, ['status', ...C.fields.filter(k => k !== 'evidence_ref')].map(k => /*#__PURE__*/React.createElement("tr", {
      key: k
    }, /*#__PURE__*/React.createElement("td", null, C.labels[k]), /*#__PURE__*/React.createElement("td", null, k === 'status' ? C.statuses[h.before[k]] : P.value(h.before[k])), /*#__PURE__*/React.createElement("td", null, k === 'status' ? C.statuses[h.after[k]] : P.value(h.after[k]))))))), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '变更前附件编号': h.before.evidence_ref,
        '变更后附件编号': h.after.evidence_ref
      }
    })), /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      className: "mini",
      icon: "search",
      "aria-label": '查看第 ' + h.sequence + ' 次原始依据',
      onClick: () => setSource(source === h.history_ref ? '' : h.history_ref)
    }, "\u539F\u59CB\u4F9D\u636E"), source === h.history_ref && /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, /*#__PURE__*/React.createElement("div", null, "\u5F53\u65F6\u6765\u6E90 \xB7 ", window.WorkbenchFormat.dateTime(h.source_snapshot.as_of)), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '历史来源编号': h.source_snapshot.snapshot_ref
      }
    }), /*#__PURE__*/React.createElement(P.Risk, {
      risk: h.source_snapshot.source.risk
    }), /*#__PURE__*/React.createElement(P.Evidence, {
      source: h.source_snapshot.source.source
    })))), /*#__PURE__*/React.createElement(P.Pager, {
      page: {
        ...history.page,
        number: historyPage
      },
      busy: read.loading,
      onPage: onPage,
      label: "\u5386\u53F2"
    })));
  }
  window.DashboardHistory = History;
})();
