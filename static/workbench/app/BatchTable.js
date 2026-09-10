(function () {
  'use strict';

  const B = window.APSBatchContract,
    C = window.APSResourceContract,
    S = window.APSResourceSession;
  const {
    Button,
    Modal,
    ErrorBox
  } = window.ResourceControls;
  function ColumnFilter({
    adapter,
    scope,
    field,
    onApply,
    onClose
  }) {
    const [selected, setSelected] = React.useState(null),
      [search, setSearch] = React.useState('');
    const read = S.useQuery(async signal => {
      const result = await adapter.facets(scope, field, signal),
        data = result && result.data;
      if (!data || data.field !== field || !Array.isArray(data.values) || result.meta.snapshot_ref !== scope.snapshot_ref) throw C.failure('列筛选与列表范围不一致。');
      return result;
    }, [adapter, scope, field]);
    const all = read.result && read.result.data.values,
      chosen = selected || scope.column_filters && scope.column_filters[field] || all || [];
    return /*#__PURE__*/React.createElement(Modal, {
      title: '筛选' + B.columns.find(row => row[0] === field)[1],
      icon: "filter",
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: () => onApply(undefined)
      }, "\u6E05\u9664\u672C\u5217"), /*#__PURE__*/React.createElement(Button, {
        onClick: onClose
      }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        disabled: !all,
        onClick: () => onApply(chosen)
      }, "\u5B8C\u6210"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b"
    }, /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u5217\u503C",
      value: search,
      onChange: event => setSearch(event.target.value)
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), all && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      onClick: () => setSelected(all)
    }, "\u5168\u9009\u5217\u503C"), /*#__PURE__*/React.createElement(Button, {
      onClick: () => setSelected([])
    }, "\u5168\u90E8\u4E0D\u9009"), /*#__PURE__*/React.createElement("div", {
      className: "batch-value-list"
    }, all.filter(value => B.label(field, value).toLowerCase().includes(search.toLowerCase())).map((value, index) => /*#__PURE__*/React.createElement("label", {
      key: index
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: chosen.includes(value),
      onChange: event => setSelected(event.target.checked ? chosen.concat([value]) : chosen.filter(item => item !== value))
    }), B.label(field, value)))))));
  }
  function BatchTable({
    rows,
    scope,
    selected,
    setSelected,
    onOpen,
    onDelete,
    onSort,
    onFilter,
    loading,
    disabled
  }) {
    const checkbox = React.useRef(null),
      all = rows.length > 0 && rows.every(row => selected.includes(row.ref));
    const [widths, setWidths] = React.useState(Object.fromEntries(B.columns.map(([key,, width]) => [key, width]))),
      drag = React.useRef(null);
    function resize(key, value) {
      setWidths(current => ({
        ...current,
        [key]: Math.max(80, Math.min(600, value))
      }));
    }
    React.useEffect(() => {
      if (checkbox.current) checkbox.current.indeterminate = !all && rows.some(row => selected.includes(row.ref));
    }, [rows, selected, all]);
    return /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame card-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      style: {
        width: Object.values(widths).reduce((sum, width) => sum + width, 204),
        minWidth: '100%'
      },
      "aria-label": "\u6279\u6B21\u5217\u8868",
      "aria-busy": loading
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      style: {
        width: 44
      }
    }, /*#__PURE__*/React.createElement("input", {
      ref: checkbox,
      type: "checkbox",
      "aria-label": "\u5168\u9009\u5F53\u524D\u9875",
      checked: all,
      disabled: disabled || !rows.length,
      onChange: event => setSelected(event.target.checked ? Array.from(new Set(selected.concat(rows.map(row => row.ref)))) : selected.filter(ref => !rows.some(row => row.ref === ref)))
    })), B.columns.map(([key, name]) => /*#__PURE__*/React.createElement("th", {
      key: key,
      style: {
        width: widths[key],
        position: 'relative'
      },
      "aria-sort": scope.sort === key ? scope.direction === 'asc' ? 'ascending' : 'descending' : 'none'
    }, key === 'progress' ? name : /*#__PURE__*/React.createElement("div", {
      className: "batch-head"
    }, /*#__PURE__*/React.createElement(Button, {
      className: "linkbtn",
      disabled: disabled,
      onClick: () => onSort(key),
      title: '排序' + name
    }, name), /*#__PURE__*/React.createElement(Button, {
      className: "linkbtn",
      icon: "filter",
      "aria-label": '筛选' + name,
      onClick: () => onFilter(key),
      disabled: disabled
    })), /*#__PURE__*/React.createElement("span", {
      role: "separator",
      tabIndex: disabled ? -1 : 0,
      "aria-label": '调整' + name + '列宽',
      "aria-orientation": "vertical",
      "aria-valuenow": widths[key],
      "aria-valuemin": 80,
      "aria-valuemax": 600,
      className: "batch-column-resizer",
      onKeyDown: event => {
        if (!disabled && ['ArrowLeft', 'ArrowRight'].includes(event.key)) {
          event.preventDefault();
          resize(key, widths[key] + (event.key === 'ArrowLeft' ? -12 : 12));
        }
      },
      onPointerDown: event => {
        if (disabled || event.button !== 0) return;
        drag.current = {
          key,
          x: event.clientX,
          width: widths[key]
        };
        event.currentTarget.setPointerCapture(event.pointerId);
        event.preventDefault();
      },
      onPointerMove: event => {
        if (drag.current && drag.current.key === key) resize(key, drag.current.width + event.clientX - drag.current.x);
      },
      onPointerUp: () => {
        drag.current = null;
      },
      onPointerCancel: () => {
        drag.current = null;
      }
    }))), /*#__PURE__*/React.createElement("th", {
      style: {
        width: 160
      }
    }, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, rows.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.ref
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      "aria-label": '选择 ' + row.business_code,
      checked: selected.includes(row.ref),
      disabled: disabled,
      onChange: event => setSelected(event.target.checked ? selected.concat(row.ref) : selected.filter(ref => ref !== row.ref))
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      className: "linkbtn",
      onClick: () => onOpen(row.ref),
      disabled: disabled
    }, row.business_code)), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("strong", null, row.relationships.part_no), /*#__PURE__*/React.createElement("div", {
      className: "muted"
    }, row.label)), /*#__PURE__*/React.createElement("td", null, B.label('', row.fields.quantity)), /*#__PURE__*/React.createElement("td", null, B.label('', row.fields.due_date)), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("div", {
      className: "batch-progress"
    }, /*#__PURE__*/React.createElement("progress", {
      value: row.relationships.completed_count,
      max: row.relationships.operation_count || 1
    }), /*#__PURE__*/React.createElement("span", null, row.relationships.completed_count, " / ", row.relationships.operation_count)), /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u5DE5\u5E8F\u6982\u51B5", row.relationships.gap_count ? ' · 待补 ' + row.relationships.gap_count : ''), row.operations.length ? row.operations.map(op => /*#__PURE__*/React.createElement("div", {
      key: op.ref
    }, op.sequence, " \xB7 ", op.label, op.issues.length ? ' · 待补齐' : '')) : '尚未生成工序')), ['priority', 'ready_status', 'status'].map(key => /*#__PURE__*/React.createElement("td", {
      key: key
    }, /*#__PURE__*/React.createElement("span", {
      className: 'pill ' + (key === 'ready_status' ? row.fields[key] === 'yes' ? 'ok' : 'warn' : key === 'priority' ? row.fields[key] === 'normal' ? 'off' : 'warn' : row.status === 'completed' ? 'ok' : row.status === 'processing' ? 'warn' : 'off')
    }, B.label(key, key === 'status' ? row.status : row.fields[key])))), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("div", {
      className: "batch-head"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "square-pen",
      onClick: () => onOpen(row.ref),
      disabled: disabled
    }, "\u67E5\u770B/\u7F16\u8F91"), /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": '删除批次 ' + row.business_code,
      onClick: () => onDelete(row),
      disabled: disabled,
      reason: B.reason(row.write_context, 'delete', 'production')
    }))))), !rows.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: 10,
      style: {
        padding: 24,
        textAlign: 'center'
      }
    }, loading ? '正在读取批次…' : '当前条件下暂无批次')))));
  }
  BatchTable.ColumnFilter = ColumnFilter;
  window.BatchTable = BatchTable;
})();
