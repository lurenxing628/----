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
    return /*#__PURE__*/React.createElement("div", {
      className: "mo-pager"
    }, /*#__PURE__*/React.createElement("span", null, page.total, " \u6761 \xB7 \u7B2C ", page.number, " / ", page.pages, " \u9875"), onSize && /*#__PURE__*/React.createElement("label", null, "\u6BCF\u9875", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u4E3B\u6570\u636E\u6BCF\u9875\u6761\u6570",
      value: page.size,
      disabled: disabled,
      onChange: event => onSize(Number(event.target.value))
    }, [20, 50, 100].map(size => /*#__PURE__*/React.createElement("option", {
      key: size,
      value: size
    }, size)))), /*#__PURE__*/React.createElement(Button, {
      className: "btn mo-icon",
      icon: "chevron-left",
      "aria-label": detail ? '详情上一页' : '主数据上一页',
      disabled: disabled || page.number <= 1,
      onClick: () => onPage(page.number - 1)
    }), /*#__PURE__*/React.createElement(Button, {
      className: "btn mo-icon",
      icon: "chevron-right",
      "aria-label": detail ? '详情下一页' : '主数据下一页',
      disabled: disabled || page.number >= page.pages,
      onClick: () => onPage(page.number + 1)
    }));
  }
  function Table({
    data,
    selected,
    onSelect,
    onMaintain,
    onFilter,
    loading,
    error,
    navigation
  }) {
    const columns = C.columns[data.scope.view],
      rows = data.rows;
    return /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("div", {
      className: "wb-table-shell"
    }, /*#__PURE__*/React.createElement("table", {
      className: "wb-table mo-table",
      "aria-label": "\u4E3B\u6570\u636E\u6E05\u5355",
      "aria-busy": loading,
      style: {
        minWidth: columns.reduce((sum, item) => sum + item[2], 48)
      }
    }, /*#__PURE__*/React.createElement("colgroup", null, columns.map(([key,, width]) => /*#__PURE__*/React.createElement("col", {
      key: key,
      style: {
        width
      }
    })), /*#__PURE__*/React.createElement("col", {
      style: {
        width: 48
      }
    })), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, columns.map(([key, title]) => /*#__PURE__*/React.createElement("th", {
      key: key
    }, /*#__PURE__*/React.createElement("div", {
      className: "mo-column"
    }, /*#__PURE__*/React.createElement("span", null, title), /*#__PURE__*/React.createElement(Button, {
      className: "btn mo-icon",
      icon: "search",
      "aria-label": '筛选列 ' + title,
      title: '筛选列 ' + title,
      "aria-pressed": !!data.scope.column_filters[key],
      onClick: () => onFilter(key),
      disabled: loading
    })))), /*#__PURE__*/React.createElement("th", null, "\u7EF4\u62A4"))), /*#__PURE__*/React.createElement("tbody", null, rows.map(item => /*#__PURE__*/React.createElement("tr", {
      key: item.key,
      "aria-selected": !!selected && selected.key === item.key,
      "data-master-ref": item.entity_ref || item.ref
    }, columns.map(([key]) => /*#__PURE__*/React.createElement("td", {
      key: key
    }, key === 'business_code' ? /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "mo-link",
      "aria-label": '查看 ' + item.business_code + (item.title ? ' ' + item.title : ''),
      onClick: event => onSelect(item, event.currentTarget),
      disabled: loading
    }, item.business_code) : key === 'status' ? /*#__PURE__*/React.createElement("span", {
      className: "mo-status",
      "data-status": item.status
    }, C.cell(item, key)) : C.cell(item, key))), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      className: "btn mo-icon",
      icon: "arrow-right",
      "aria-label": '维护 ' + item.business_code,
      reason: item.target.unavailable_reason || (!navigation ? '维护导航尚未接入。' : ''),
      disabled: loading,
      onClick: () => onMaintain(item.target)
    }))))))), !rows.length && /*#__PURE__*/React.createElement("div", {
      className: "mo-empty"
    }, /*#__PURE__*/React.createElement("strong", null, loading ? '正在读取主数据' : error ? '主数据读取失败' : '当前范围没有记录')));
  }
  window.MasterOverviewTable = {
    Tabs,
    Pager,
    Table
  };
})();
