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
      className: "rm-table-wrap",
      tabIndex: "0",
      role: "region",
      "aria-label": "\u5B8C\u6574\u4FEE\u6539\u524D\u540E\u660E\u7EC6"
    }, /*#__PURE__*/React.createElement("table", {
      className: "rm-table"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      style: {
        width: '7%'
      }
    }, "\u884C\u53F7"), /*#__PURE__*/React.createElement("th", {
      style: {
        width: '15%'
      }
    }, label, " / \u7ED3\u679C"), /*#__PURE__*/React.createElement("th", {
      style: {
        width: '34%'
      }
    }, "\u4FEE\u6539\u524D"), /*#__PURE__*/React.createElement("th", {
      style: {
        width: '34%'
      }
    }, "\u4FEE\u6539\u540E"), /*#__PURE__*/React.createElement("th", {
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
    }, "\u8BE5\u8303\u56F4\u6CA1\u6709\u9884\u68C0\u884C\u3002"))))), /*#__PURE__*/React.createElement("div", {
      className: "rm-pagination"
    }, /*#__PURE__*/React.createElement("span", null, "\u5171 ", rows.length, " \u884C \xB7 \u7B2C ", current, " / ", pages, " \u9875"), /*#__PURE__*/React.createElement("label", null, "\u6BCF\u9875 ", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u9884\u68C0\u6BCF\u9875\u884C\u6570",
      value: size,
      onChange: event => {
        setSize(Number(event.target.value));
        setPage(1);
      }
    }, [20, 50, 100].map(number => /*#__PURE__*/React.createElement("option", {
      key: number,
      value: number
    }, number, " \u884C")))), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      "aria-label": "\u9884\u68C0\u4E0A\u4E00\u9875",
      disabled: current <= 1,
      onClick: () => setPage(current - 1)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      "aria-label": "\u9884\u68C0\u4E0B\u4E00\u9875",
      disabled: current >= pages,
      onClick: () => setPage(current + 1)
    })));
  }
  function Styles() {
    return /*#__PURE__*/React.createElement("style", null, `
      .plana.rm-actions .modal.lg { width: min(620px,100%); }
      .plana.rm-actions.rm-wide .modal.lg { width: min(1120px,100%); }
      .plana.rm-actions .modal-b.scroll { max-height: min(70vh,760px); }
      .rm-actions .rm-body { color: var(--ui-text); padding-top: 18px; }
      .rm-actions .rm-body p { margin: 10px 0; overflow-wrap: anywhere; }
      .rm-actions .rm-body button,.rm-actions .rm-body select { min-height: 30px; }
      .rm-actions .rm-body select { color: var(--ui-text); background: var(--ui-card-bg); border: 1px solid var(--ui-border); border-radius: var(--wb-radius-control); padding: 4px 8px; }
      .rm-actions .rm-format { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin: 12px 0; }
      .rm-actions .rm-format .seg { display: inline-flex; flex: none; }
      .rm-actions .rm-format .seg button { width: 116px; min-width: 116px; white-space: nowrap; height: 32px; }
      .rm-actions .rm-preview-toolbar,.rm-actions .rm-pagination { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; padding: 10px 0; }
      .rm-actions .rm-preview-toolbar h3 { margin: 0 auto 0 0; font-size: 14px; font-weight: 600; }
      .rm-actions .rm-pagination > span:first-child { margin-right: auto; }
      .rm-actions .rm-summary { display: flex; flex-wrap: wrap; gap: 20px; padding: 12px 0; border-bottom: 1px solid var(--ui-border); }
      .rm-actions .rm-summary b { margin-left: 4px; font-variant-numeric: tabular-nums; }
      .rm-actions .rm-danger { color: var(--ui-danger-text); }
      .rm-actions .rm-table-wrap { overflow: auto; max-width: 100%; max-height: min(38vh,410px); border: 1px solid var(--ui-border); }
      .rm-actions .rm-table { width: 100%; min-width: 650px; table-layout: fixed; border-collapse: collapse; font-size: 12px; line-height: 1.65; }
      .rm-actions .rm-table th { position: sticky; top: 0; z-index: 1; background: var(--ui-surface-muted); text-align: left; font-weight: 500; }
      .rm-actions .rm-table th,.rm-actions .rm-table td { padding: 9px 10px; border-bottom: 1px solid var(--ui-border); vertical-align: top; overflow-wrap: anywhere; white-space: normal; }
      .rm-actions .rm-table td + td,.rm-actions .rm-table th + th { border-left: 1px solid var(--ui-border); }
      .rm-actions .rm-facts { display: grid; grid-template-columns: 64px minmax(0,1fr); gap: 4px 8px; margin: 0; }
      .rm-actions .rm-facts dt { color: var(--ui-muted); }
      .rm-actions .rm-facts dd { margin: 0; overflow-wrap: anywhere; }
      .rm-actions .rm-changed { color: var(--ui-primary); font-weight: 500; }
      .rm-actions .rm-row-note td { padding-top: 6px; padding-bottom: 6px; background: var(--ui-surface-muted); }
      .rm-actions .rm-check { display: flex; align-items: flex-start; gap: 8px; margin-top: 14px; }
      .rm-actions input[type=checkbox],.rm-actions input[type=radio] { width: 16px; height: 16px; flex: none; accent-color: var(--ui-primary); }
      .rm-actions .iorow input[type=radio] { margin: 0; }
      .rm-actions .rm-upload { position: relative; }
      .rm-actions .rm-upload input { position: absolute; inset: 0; opacity: 0; width: 100%; cursor: pointer; }
      .rm-actions .rm-upload:focus-within { outline: 2px solid var(--ui-primary); outline-offset: 2px; }
      .rm-actions .rm-upload[aria-disabled=true] { opacity: .65; cursor: default; }
      .rm-actions .drop .dt,.rm-actions .tmpl-t { overflow-wrap: anywhere; }
      .rm-actions .tmpl-row > div { min-width: 0; flex: 1; }
      .rm-actions .rm-request { font-family: monospace; font-size: 12px; overflow-wrap: anywhere; }
      @media(max-width:700px) { .plana.rm-actions .modal-bg { padding: 8px; } .rm-actions .tmpl-row { flex-wrap: wrap; } }
    `);
  }
  window.ResourceMaterialPreview = Preview;
  window.ResourceMaterialPreview.Styles = Styles;
})();
