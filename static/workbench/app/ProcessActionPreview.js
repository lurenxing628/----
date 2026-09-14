(function () {
  'use strict';

  const {
    Button
  } = window.ResourceControls;
  function text(key, value) {
    if (value === null) return '未填写';
    if (value === '') return '空白';
    if (key === 'route_parsed') return value === 'yes' ? '已解析' : value === 'no' ? '未解析' : '原标记：' + String(value);
    if (key === 'source') return value === 'internal' ? '自制' : value === 'external' ? '外协' : String(value);
    if (typeof value === 'boolean') return value ? '是' : '否';
    return String(value);
  }
  function Facts({
    value,
    fields,
    empty
  }) {
    if (value === null) return /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, empty);
    return /*#__PURE__*/React.createElement("dl", {
      className: "rm-facts"
    }, Object.keys(value).map(key => /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, fields[key]), /*#__PURE__*/React.createElement("dd", {
      style: {
        whiteSpace: 'pre-wrap'
      }
    }, text(key, value[key])))));
  }
  function ProcessActionPreview({
    data,
    fields = window.APSProcessActions.fields,
    renderDetails
  }) {
    const [filter, setFilter] = React.useState('all'),
      [page, setPage] = React.useState(1);
    React.useEffect(() => {
      setPage(1);
      setFilter('all');
    }, [data.preview_ref]);
    const rows = data.rows.filter(row => filter === 'all' || row.result === filter),
      pages = Math.max(1, Math.ceil(rows.length / 50)),
      current = Math.min(page, pages);
    const labels = {
      new: '新增',
      update: '更新',
      unchanged: '不变',
      delete: '删除',
      rejected: '不能提交'
    };
    return /*#__PURE__*/React.createElement("section", {
      className: "rm-preview",
      "aria-label": "\u96F6\u4EF6\u64CD\u4F5C\u660E\u7EC6"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rm-summary",
      role: "status"
    }, Object.keys(labels).map(key => /*#__PURE__*/React.createElement("span", {
      key: key
    }, labels[key], " ", /*#__PURE__*/React.createElement("b", null, data.summary[key])))), /*#__PURE__*/React.createElement("div", {
      className: "rm-preview-toolbar"
    }, /*#__PURE__*/React.createElement("h3", null, "\u9010\u884C\u6838\u5BF9"), /*#__PURE__*/React.createElement("label", null, "\u663E\u793A ", /*#__PURE__*/React.createElement("select", {
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
    }, "\u4E0D\u80FD\u63D0\u4EA4 ", data.summary.rejected, " \u884C")))), /*#__PURE__*/React.createElement("div", {
      className: "rm-table-wrap"
    }, /*#__PURE__*/React.createElement("table", {
      className: "rm-table",
      "aria-label": "\u96F6\u4EF6\u64CD\u4F5C\u9884\u68C0"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "零件操作预检"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: '8%'
      }
    }, "\u884C\u53F7"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: '18%'
      }
    }, "\u96F6\u4EF6 / \u7ED3\u679C"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: '32%'
      }
    }, "\u539F\u8BB0\u5F55"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: '32%'
      }
    }, "\u4FEE\u6539\u540E"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: '10%'
      }
    }, "\u88AB\u4F7F\u7528"))), /*#__PURE__*/React.createElement("tbody", null, rows.slice((current - 1) * 50, current * 50).map(row => /*#__PURE__*/React.createElement(React.Fragment, {
      key: row.row
    }, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", null, row.row), /*#__PURE__*/React.createElement("td", null, row.business_code === null ? '原零件已不存在' : row.business_code, /*#__PURE__*/React.createElement("div", null, labels[row.result])), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Facts, {
      value: row.before,
      fields: fields,
      empty: "\u672A\u53D6\u5F97\u539F\u8BB0\u5F55"
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Facts, {
      value: row.after,
      fields: fields,
      empty: row.action === 'delete' ? '删除后不再存在' : '未形成修改'
    })), /*#__PURE__*/React.createElement("td", null, row.reference_count, " \u5904")), row.errors.length > 0 && /*#__PURE__*/React.createElement("tr", {
      className: "rm-row-note"
    }, /*#__PURE__*/React.createElement("td", {
      colSpan: 5
    }, row.errors.map((error, index) => /*#__PURE__*/React.createElement("div", {
      className: "rm-danger",
      key: index
    }, "\u7B2C ", row.row, " \u884C\uFF1A", error.message)))), renderDetails && row.route_summary && /*#__PURE__*/React.createElement("tr", {
      className: "rm-row-note"
    }, /*#__PURE__*/React.createElement("td", {
      colSpan: 5
    }, renderDetails(row))))), !rows.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: 5
    }, "\u6CA1\u6709\u5BF9\u5E94\u660E\u7EC6\u3002"))))), /*#__PURE__*/React.createElement("div", {
      className: "rm-pagination"
    }, /*#__PURE__*/React.createElement("span", null, "\u5171 ", rows.length, " \u884C \xB7 \u7B2C ", current, " / ", pages, " \u9875"), /*#__PURE__*/React.createElement("span", null, "\u6BCF\u9875 50 \u884C"), /*#__PURE__*/React.createElement(Button, {
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
  window.ProcessActionPreview = ProcessActionPreview;
})();
