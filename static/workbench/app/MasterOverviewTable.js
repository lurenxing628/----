(function () {
  'use strict';

  const C = window.APSMasterOverviewContract,
    {
      Button
    } = window.ResourceControls;
  function Tabs({
    values,
    value,
    onChange,
    label,
    disabled
  }) {
    function key(event, index) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? values.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + values.length) % values.length;
      onChange(values[next][0]);
      event.currentTarget.parentElement.children[next].focus();
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "mo-tabs",
      role: "tablist",
      "aria-label": label
    }, values.map(([id, title, count], index) => /*#__PURE__*/React.createElement("button", {
      key: id,
      type: "button",
      role: "tab",
      "aria-selected": id === value,
      disabled: disabled,
      tabIndex: id === value ? 0 : -1,
      onKeyDown: event => key(event, index),
      onClick: () => onChange(id)
    }, title, count !== undefined && /*#__PURE__*/React.createElement("span", null, count))));
  }
  function Pager({
    page,
    onPage,
    onSize,
    disabled,
    detail = false
  }) {
    return /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
      page: page,
      sizes: detail ? [10] : [20, 50, 100],
      onPage: onPage,
      onSize: onSize,
      disabled: disabled,
      unit: "\u6761",
      label: detail ? '详情' : '基础资料'
    });
  }
  function Table({
    data,
    selected,
    onSelect,
    onMaintain,
    onFilter,
    onClear,
    onRetry,
    loading,
    error,
    navigation
  }) {
    const columns = C.columns[data.scope.view],
      rows = data.rows;
    const filtered = data.scope.query !== '' || data.scope.domain !== 'all' || data.scope.status !== 'all' || Object.keys(data.scope.column_filters).length > 0;
    return /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "wb-table mo-table",
      "aria-label": "\u8D44\u6599\u6E05\u5355",
      "aria-busy": loading,
      style: {
        minWidth: columns.reduce((sum, item) => sum + item[2], 64)
      }
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-sr-only"
    }, "\u8D44\u6599\u6E05\u5355"), /*#__PURE__*/React.createElement("colgroup", null, columns.map(([key,, width]) => /*#__PURE__*/React.createElement("col", {
      key: key,
      style: {
        width
      }
    })), /*#__PURE__*/React.createElement("col", {
      style: {
        width: 64
      }
    })), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, columns.map(([key, title]) => /*#__PURE__*/React.createElement("th", {
      scope: "col",
      key: key,
      className: key === 'business_code' ? 'wb-col-key' : ''
    }, /*#__PURE__*/React.createElement("div", {
      className: "mo-column"
    }, /*#__PURE__*/React.createElement("span", null, title), /*#__PURE__*/React.createElement(Button, {
      className: "btn mo-icon wb-column-filter",
      icon: "search",
      "aria-label": '筛选列 ' + title,
      title: '筛选列 ' + title,
      "aria-pressed": !!data.scope.column_filters[key],
      onClick: () => onFilter(key),
      disabled: loading
    })))), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-actions"
    }, "\u7EF4\u62A4"))), /*#__PURE__*/React.createElement("tbody", null, rows.map(item => /*#__PURE__*/React.createElement("tr", {
      key: item.key,
      "aria-selected": !!selected && selected.key === item.key,
      "data-master-ref": item.entity_ref || item.ref
    }, columns.map(([key]) => /*#__PURE__*/React.createElement("td", {
      key: key,
      className: key === 'business_code' ? 'wb-col-key' : ''
    }, key === 'business_code' ? /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "mo-link",
      "aria-label": '查看 ' + item.business_code + (item.title ? ' ' + item.title : ''),
      onClick: event => onSelect(item, event.currentTarget),
      disabled: loading
    }, item.business_code) : key === 'status' ? /*#__PURE__*/React.createElement("span", {
      className: "mo-status",
      "data-status": item.status
    }, C.cell(item, key)) : C.cell(item, key))), /*#__PURE__*/React.createElement("td", {
      className: "wb-col-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      className: "btn mo-icon",
      icon: "arrow-right",
      "aria-label": '维护 ' + item.business_code,
      reasonDisplay: "inline",
      reason: item.target.unavailable_reason || (!navigation ? window.WorkbenchTerms.outcomes.unavailable : ''),
      disabled: loading,
      onClick: () => onMaintain(item.target)
    })))))), !rows.length && /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: loading ? 'loading' : error ? 'error' : filtered ? 'filtered' : 'empty',
      title: loading ? '正在读取基础资料' : error ? '基础资料读取失败' : '当前范围没有记录',
      action: error ? /*#__PURE__*/React.createElement(Button, {
        onClick: onRetry
      }, "\u5237\u65B0\u57FA\u7840\u8D44\u6599") : filtered ? /*#__PURE__*/React.createElement(Button, {
        onClick: onClear
      }, "\u6E05\u9664\u7B5B\u9009\u5E76\u67E5\u770B\u6E05\u5355") : null
    }));
  }
  window.MasterOverviewTable = {
    Tabs,
    Pager,
    Table
  };
})();
