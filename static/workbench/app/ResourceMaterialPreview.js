(function () {
  'use strict';

  const M = window.APSResourceMaterial;
  const {
    Button
  } = window.ResourceControls;
  function value(key, item, contract) {
    if (item === null) return '空值';
    if (item === '') return '空白';
    if (contract.displayValue) {
      const formatted = contract.displayValue(key, item);
      if (formatted !== undefined) return formatted;
    }
    if (Array.isArray(item)) return item.length ? item.join('、') : '未绑定';
    if (typeof item === 'boolean') return item ? '是' : '否';
    if (contract.kind !== 'material') return window.APSResourceContract.fieldValue(contract.kind, key, item);
    if (key === 'status') return window.APSResourceContract.fieldValue('material', key, item);
    return String(item);
  }
  function Facts({
    facts,
    empty,
    changes,
    fields,
    contract
  }) {
    if (facts === null) return /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, empty);
    return /*#__PURE__*/React.createElement("dl", {
      className: "rm-facts"
    }, Object.keys(facts).map(key => /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, fields[key] || '数据'), /*#__PURE__*/React.createElement("dd", {
      className: Object.prototype.hasOwnProperty.call(changes, key) ? 'rm-changed' : ''
    }, value(key, facts[key], contract)))));
  }
  function Preview({
    data,
    mode,
    contract = M,
    label = '物料'
  }) {
    const fields = data.columns ? Object.fromEntries(data.columns.map(item => [item.key, item.label])) : contract.fields;
    const [filter, setFilter] = React.useState('all'),
      [page, setPage] = React.useState(1),
      [size, setSize] = React.useState(20);
    React.useEffect(() => {
      setFilter('all');
      setPage(1);
    }, [data.preview_ref]);
    const rows = data.rows.filter(row => filter === 'all' || (filter === 'rejected' ? row.result === 'rejected' : row.requires_confirmation));
    const pages = Math.max(1, Math.ceil(rows.length / size)),
      current = Math.min(page, pages);
    return /*#__PURE__*/React.createElement("section", {
      className: "rm-preview",
      "aria-label": label + '预检明细'
    }, /*#__PURE__*/React.createElement("div", {
      className: "rm-summary",
      role: "status"
    }, Object.keys(M.results).filter(key => key !== (mode === 'bulk' ? 'new' : 'delete') && (mode !== 'bulk' || !['update', 'unchanged'].includes(key))).map(key => /*#__PURE__*/React.createElement("span", {
      key: key
    }, M.results[key], " ", /*#__PURE__*/React.createElement("b", {
      className: key === 'rejected' && data.summary[key] ? 'rm-danger' : ''
    }, data.summary[key])))), /*#__PURE__*/React.createElement("div", {
      className: "rm-preview-toolbar"
    }, /*#__PURE__*/React.createElement("h3", null, "\u9010\u884C\u9884\u68C0"), /*#__PURE__*/React.createElement("label", null, "\u663E\u793A ", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u9884\u68C0\u660E\u7EC6\u7B5B\u9009",
      value: filter,
      onChange: event => {
        setFilter(event.target.value);
        setPage(1);
      }
    }, /*#__PURE__*/React.createElement("option", {
      value: "all"
    }, "\u5168\u90E8 ", data.rows.length, " \u884C"), /*#__PURE__*/React.createElement("option", {
      value: "rejected"
    }, "\u62D2\u7EDD\u884C ", data.summary.rejected), mode === 'import' && /*#__PURE__*/React.createElement("option", {
      value: "confirmation"
    }, "\u6D89\u53CA\u5F15\u7528\u7684\u66F4\u65B0 ", data.rows.filter(row => row.requires_confirmation).length)))), /*#__PURE__*/React.createElement("div", {
      className: "rm-table-wrap wb-table-frame",
      "data-sticky-head": true,
      tabIndex: "0",
      role: "region",
      "aria-label": "\u5B8C\u6574\u4FEE\u6539\u524D\u540E\u660E\u7EC6"
    }, /*#__PURE__*/React.createElement("table", {
      className: "rm-table wb-table"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, label, "\u9884\u68C0\u4FEE\u6539\u524D\u540E\u660E\u7EC6"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: '7%'
      }
    }, "\u884C\u53F7"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: '15%'
      }
    }, label, " / \u7ED3\u679C"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: '34%'
      }
    }, "\u4FEE\u6539\u524D"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: '34%'
      }
    }, "\u4FEE\u6539\u540E"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: '10%'
      }
    }, "\u5F15\u7528"))), /*#__PURE__*/React.createElement("tbody", null, rows.slice((current - 1) * size, current * size).map(row => /*#__PURE__*/React.createElement(React.Fragment, {
      key: row.row
    }, /*#__PURE__*/React.createElement("tr", {
      "data-material-row": contract.kind === 'material' ? row.row : undefined,
      "data-resource-row": row.row
    }, /*#__PURE__*/React.createElement("td", null, row.row), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("strong", null, row.business_code || '编号无效'), /*#__PURE__*/React.createElement("div", {
      className: row.result === 'rejected' ? 'rm-danger' : ''
    }, M.results[row.result])), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Facts, {
      facts: row.before,
      empty: row.result === 'new' ? '尚不存在' : '未取得原记录',
      changes: row.changes,
      fields: fields,
      contract: contract
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Facts, {
      facts: row.after,
      empty: row.action === 'delete' ? '删除后不再存在' : '未形成可提交内容',
      changes: row.changes,
      fields: fields,
      contract: contract
    })), /*#__PURE__*/React.createElement("td", null, row.reference_count, " \u9879")), (row.errors.length > 0 || row.requires_confirmation) && /*#__PURE__*/React.createElement("tr", {
      className: "rm-row-note"
    }, /*#__PURE__*/React.createElement("td", null), /*#__PURE__*/React.createElement("td", {
      colSpan: "4"
    }, row.errors.map((error, index) => /*#__PURE__*/React.createElement("div", {
      className: "rm-danger",
      key: index
    }, "\u7B2C ", row.row, " \u884C \xB7 ", fields[error.field] || '数据', "\uFF1A", error.message)), row.requires_confirmation && /*#__PURE__*/React.createElement("div", null, contract.kind === 'material' ? '涉及已有物料需求' : '涉及关键字段或已有引用', "\uFF0C\u9700\u6838\u5BF9\u4FEE\u6539\u524D\u540E\u5185\u5BB9\u3002"))))), !rows.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: "5"
    }, /*#__PURE__*/React.createElement(window.WorkbenchControls.EmptyState, {
      kind: filter === 'all' ? 'empty' : 'filtered',
      title: filter === 'all' ? '暂无预检行' : undefined,
      action: filter === 'all' ? undefined : /*#__PURE__*/React.createElement(Button, {
        onClick: () => {
          setFilter('all');
          setPage(1);
        }
      }, "\u6E05\u9664\u7B5B\u9009")
    })))))), /*#__PURE__*/React.createElement(window.WorkbenchControls.Pager, {
      page: current,
      pages: pages,
      total: rows.length,
      size: size,
      sizes: [20, 50, 100],
      unit: "\u884C",
      label: "\u9884\u68C0",
      sizeLabel: "\u9884\u68C0\u6BCF\u9875\u884C\u6570",
      onPage: setPage,
      onSize: next => {
        setSize(next);
        setPage(1);
      }
    }));
  }
  function Styles() {
    return null;
  }
  window.ResourceMaterialPreview = Preview;
  window.ResourceMaterialPreview.Styles = Styles;
})();
