(function () {
  'use strict';

  const {
    Button,
    Icon,
    ErrorBox
  } = window.ResourceControls;
  const text = (value, missing = '未知') => value === null || value === undefined ? missing : String(value);
  const hours = (value, missing = '未填写') => value === null ? missing : text(value) + ' 小时';
  const source = value => ({
    internal: '自制',
    external: '外协',
    unknown: '未确认'
  })[value] || '未确认';
  const writeReason = '采用与锁定前要先读取真实预检并确认；只影响以后新增的工序模板，不改已有批次、历史计划和现场记录。';
  function useRead(load, identity, adapter, enabled = true) {
    const [state, setState] = React.useState({
      result: null,
      error: null,
      busy: true,
      identity
    });
    React.useEffect(() => {
      const controller = new AbortController();
      let active = true;
      setState({
        result: null,
        error: null,
        busy: enabled,
        identity
      });
      if (enabled) Promise.resolve().then(() => load(controller.signal)).then(result => {
        if (active) setState({
          result,
          error: null,
          busy: false,
          identity
        });
      }, error => {
        if (active) setState({
          result: null,
          error,
          busy: false,
          identity
        });
      });
      return () => {
        active = false;
        controller.abort();
      };
    }, [identity, adapter, enabled]);
    return state.identity === identity ? state : {
      result: null,
      error: null,
      busy: enabled
    };
  }
  function Styles() {
    return null;
  }
  function Filters({
    value,
    onChange,
    disabled
  }) {
    const [query, setQuery] = React.useState(value.query);
    React.useEffect(() => setQuery(value.query), [value.query]);
    return /*#__PURE__*/React.createElement("form", {
      className: "ca-tools",
      "aria-label": "\u6821\u51C6\u7B5B\u9009",
      onSubmit: event => {
        event.preventDefault();
        onChange({
          query
        });
      }
    }, /*#__PURE__*/React.createElement("label", {
      className: "ca-search"
    }, /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u6821\u51C6\u660E\u7EC6",
      placeholder: "\u641C\u7D22\u56FE\u53F7\u3001\u96F6\u4EF6\u540D\u3001\u5DE5\u5E8F\u6216\u5E8F\u53F7",
      maxLength: 200,
      value: query,
      disabled: disabled,
      onChange: event => setQuery(event.target.value)
    })), /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      type: "submit",
      "aria-label": "\u641C\u7D22",
      disabled: disabled
    }), /*#__PURE__*/React.createElement("label", null, "\u5DE5\u5E8F\u6765\u6E90", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5DE5\u5E8F\u6765\u6E90",
      disabled: disabled,
      value: value.source || '',
      onChange: event => onChange({
        source: event.target.value || null,
        query
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u5168\u90E8\u6765\u6E90"), /*#__PURE__*/React.createElement("option", {
      value: "internal"
    }, "\u81EA\u5236"), /*#__PURE__*/React.createElement("option", {
      value: "external"
    }, "\u5916\u534F"), /*#__PURE__*/React.createElement("option", {
      value: "unknown"
    }, "\u672A\u786E\u8BA4"))), /*#__PURE__*/React.createElement("label", null, "\u72B6\u6001", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5EFA\u8BAE\u72B6\u6001",
      disabled: disabled,
      value: value.status,
      onChange: event => onChange({
        status: event.target.value,
        query
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "all"
    }, "\u5168\u90E8\u72B6\u6001"), /*#__PURE__*/React.createElement("option", {
      value: "suggested"
    }, "\u5DF2\u6709\u5EFA\u8BAE"), /*#__PURE__*/React.createElement("option", {
      value: "insufficient_data"
    }, "\u6570\u636E\u4E0D\u8DB3"))), /*#__PURE__*/React.createElement("label", {
      className: "ca-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: value.deviation === 'over_20_percent',
      disabled: disabled,
      onChange: event => onChange({
        deviation: event.target.checked ? 'over_20_percent' : 'all',
        query
      })
    }), "\u4EC5\u770B\u504F\u5DEE > 20%"), /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": "\u6E05\u9664\u7B5B\u9009",
      disabled: disabled,
      onClick: () => {
        setQuery('');
        onChange({
          query: '',
          source: null,
          status: 'all',
          deviation: 'all',
          column_filters: {}
        });
      }
    }));
  }
  function Page({
    page,
    onChange,
    disabled,
    label = ''
  }) {
    return /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
      page: page.number,
      pages: Math.max(1, page.total_pages),
      total: page.total,
      size: page.size,
      sizes: Array.from(new Set([10, 20, 50, page.size])).sort((a, b) => a - b),
      disabled: disabled,
      label: label,
      onPage: number => onChange({
        page: number
      }),
      onSize: size => onChange({
        size,
        page: 1
      })
    });
  }
  function Table({
    rows,
    selected,
    onSelect,
    onPart,
    disabled,
    canView,
    scope,
    adapter,
    onSort,
    onFilter,
    widths,
    onResize,
    total
  }) {
    const columns = [['part_no', '图号 / 零件', 240], ['operation_label', '工序 / 来源', 210], ['old_unit_hours', '原定额（小时/件）', 175], ['suggested_unit_hours', '建议（小时/件）', 160], ['sample_count', '可用记录数', 125], ['absolute_deviation_percent', '偏差', 125], ['status', '状态', 125]];
    const width = (key, value) => widths[key] || value;
    return /*#__PURE__*/React.createElement("div", {
      className: "ca-table-scroll wb-table-frame",
      tabIndex: 0,
      role: "region",
      "aria-label": "\u6821\u51C6\u660E\u7EC6\u6EDA\u52A8\u533A\u57DF"
    }, /*#__PURE__*/React.createElement("table", {
      className: "ca-table",
      "aria-label": "\u6821\u51C6\u660E\u7EC6",
      style: {
        minWidth: 60 + columns.reduce((sum, [key,, value]) => sum + width(key, value), 0)
      }
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u5F53\u524D\u7B5B\u9009\u8303\u56F4\u7684\u6821\u51C6\u5EFA\u8BAE\uFF1B\u5EFA\u8BAE\u4E0D\u76F4\u63A5\u4FEE\u6539\u5DF2\u6709\u6279\u6B21\u5B9A\u989D\u3002"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, columns.map(([key, title, value]) => /*#__PURE__*/React.createElement("th", {
      key: key,
      scope: "col",
      style: {
        width: width(key, value)
      },
      "aria-sort": scope.sort === key ? scope.direction === 'asc' ? 'ascending' : 'descending' : 'none'
    }, /*#__PURE__*/React.createElement(window.ResourceTableHeader, {
      column: {
        key,
        title
      },
      kind: "calibration",
      scope: scope,
      adapter: adapter,
      sort: scope.sort,
      direction: scope.direction,
      sortActive: true,
      onSort: onSort,
      onFilter: rule => onFilter(key, rule),
      filter: scope.column_filters[key],
      matchingCount: total,
      width: width(key, value),
      onResize: value => onResize(key, Math.min(16384, value)),
      disabled: disabled,
      scopeTransform: window.CalibrationAPI.facetScope
    }))), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "ca-action"
    }, "\u8BE6\u60C5"))), /*#__PURE__*/React.createElement("tbody", null, rows.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.suggestion_ref,
      "data-ref": row.suggestion_ref,
      "data-selected": selected === row.suggestion_ref
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      className: "lnk",
      "aria-label": '查看零件 ' + row.part_no,
      disabled: disabled || !canView || row.capabilities.view !== true || typeof onPart !== 'function',
      onClick: () => onPart(row)
    }, row.part_no), /*#__PURE__*/React.createElement("small", null, row.part_name)), /*#__PURE__*/React.createElement("td", null, row.sequence, " \xB7 ", row.operation_label, /*#__PURE__*/React.createElement("small", null, source(row.source))), /*#__PURE__*/React.createElement("td", {
      className: "ca-number"
    }, text(row.old_unit_hours, '未填写')), /*#__PURE__*/React.createElement("td", {
      className: "ca-number"
    }, text(row.suggested_unit_hours, '暂无建议')), /*#__PURE__*/React.createElement("td", {
      className: "ca-number"
    }, row.sample_count), /*#__PURE__*/React.createElement("td", {
      className: "ca-number",
      style: {
        color: row.over_20_percent ? 'var(--ui-danger-text)' : 'var(--ui-info-muted)'
      }
    }, row.deviation_percent === null ? '未计算' : (row.deviation_percent > 0 ? '+' : '') + row.deviation_percent + '%'), /*#__PURE__*/React.createElement("td", null, row.status === 'insufficient_data' ? '数据不足' : '待复核'), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      className: "mini",
      "aria-label": '查看 ' + row.part_no + ' ' + row.sequence + ' ' + row.operation_label,
      disabled: disabled,
      reasonDisplay: "tooltip",
      reason: canView && row.capabilities.view === true ? '' : '查看权限尚未确认，暂不能打开。',
      onClick: () => onSelect(row.suggestion_ref)
    })))))), !rows.length && /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "empty",
      title: "\u5F53\u524D\u7B5B\u9009\u6CA1\u6709\u8BB0\u5F55",
      hint: "\u8C03\u6574\u56FE\u53F7\u3001\u5DE5\u5E8F\u6765\u6E90\u6216\u5EFA\u8BAE\u72B6\u6001\u540E\u91CD\u65B0\u67E5\u8BE2\u3002"
    }));
  }
  window.CalibrationControls = {
    Button,
    Icon,
    ErrorBox,
    Styles,
    Filters,
    Page,
    Table,
    useRead,
    text,
    hours,
    source,
    writeReason
  };
})();
