(function () {
  'use strict';

  const C = window.APSResourceContract;
  const {
    Button,
    Status,
    Relation
  } = window.ResourceControls;
  const cell = (entity, key) => entity.fields[key] == null ? /*#__PURE__*/React.createElement("span", {
    className: "muted"
  }, "\u672A\u77E5") : typeof entity.fields[key] === 'number' ? window.WorkbenchFormat.number(entity.fields[key], {
    digits: 1
  }) : String(entity.fields[key]);
  const columns = {
    material: [{
      key: 'spec',
      title: '规格',
      render: entity => cell(entity, 'spec')
    }, {
      key: 'stock_qty',
      title: '库存',
      width: 135,
      numeric: true,
      render: entity => /*#__PURE__*/React.createElement(React.Fragment, null, cell(entity, 'stock_qty'), entity.fields.stock_qty != null && entity.fields.unit ? ' ' + entity.fields.unit : '')
    }],
    machine: [{
      key: 'op_type_ref',
      title: '绑定工种',
      render: entity => /*#__PURE__*/React.createElement(Relation, {
        entity: entity,
        field: "op_type_ref"
      })
    }, {
      key: 'group_ref',
      title: '设备组',
      width: 130,
      render: entity => /*#__PURE__*/React.createElement(Relation, {
        entity: entity,
        field: "group_ref"
      })
    }],
    operator: [{
      key: 'skill_refs',
      title: '技能工种',
      render: entity => /*#__PURE__*/React.createElement(Relation, {
        entity: entity,
        field: "skill_refs"
      })
    }, {
      key: 'shift_profile_ref',
      title: '班次',
      width: 130,
      render: entity => /*#__PURE__*/React.createElement(Relation, {
        entity: entity,
        field: "shift_profile_ref"
      })
    }],
    supplier: [{
      key: 'op_type_refs',
      title: '可做外协工种',
      render: entity => /*#__PURE__*/React.createElement(Relation, {
        entity: entity,
        field: "op_type_refs"
      })
    }, {
      key: 'default_days',
      title: '默认周期（天）',
      width: 125,
      numeric: true,
      render: entity => cell(entity, 'default_days')
    }]
  };
  function available(entity, key) {
    if (!C.availability(entity.availability)) {
      const issue = entity.issues.find(item => item.code === 'resource_availability_unavailable');
      return /*#__PURE__*/React.createElement("span", {
        className: "muted",
        title: issue ? issue.message : '可用数量尚未读取。'
      }, issue ? '暂无数据' : '未读取');
    }
    return /*#__PURE__*/React.createElement("span", {
      title: key === 'machines' ? '已启用且关联此工种的设备数。' : '具备对应技能和设备授权的在岗人数（去重）。'
    }, entity.availability[key]);
  }
  function opColumns(category) {
    if (category === 'internal') return [{
      key: 'available_machines',
      title: '可用设备',
      width: 110,
      numeric: true,
      render: entity => available(entity, 'machines')
    }, {
      key: 'available_operators',
      title: '可用人员',
      width: 110,
      numeric: true,
      render: entity => available(entity, 'operators')
    }, {
      key: 'remark',
      title: '产能备注',
      render: entity => cell(entity, 'remark')
    }];
    if (category === 'external') return [{
      key: 'default_merge_mode',
      title: '默认周期规则',
      width: 150,
      render: entity => C.fieldValue('op_type', 'default_merge_mode', entity.fields.default_merge_mode)
    }, {
      key: 'remark',
      title: '备注',
      render: entity => cell(entity, 'remark')
    }];
    return [{
      key: 'category',
      title: '归属',
      width: 90,
      render: entity => entity.fields.category === 'internal' ? '自制' : entity.fields.category === 'external' ? '外协' : '待归类'
    }, {
      key: 'remark',
      title: '备注',
      render: entity => cell(entity, 'remark')
    }];
  }
  function ResourceTables({
    kind,
    category,
    entities,
    source,
    selected = [],
    onSelect,
    onOpen,
    onDelete,
    disabled = false,
    headerDisabled = disabled,
    loading = false,
    error,
    onRetry,
    onClear,
    adapter,
    scope,
    matchingCount,
    sort = 'business_code',
    direction = 'asc',
    sortActive = true,
    onSort,
    onColumnFilter
  }) {
    const selectAll = React.useRef(null),
      all = entities.length > 0 && entities.every(item => selected.includes(item.ref));
    const table = React.useRef(null),
      [widths, setWidths] = React.useState(null);
    React.useEffect(() => {
      if (selectAll.current) selectAll.current.indeterminate = !all && entities.some(item => selected.includes(item.ref));
    }, [all, entities, selected]);
    const opCategory = category || (entities.length && entities.every(item => item.fields.category === entities[0].fields.category) ? entities[0].fields.category : null);
    const cols = [{
      key: 'business_code',
      title: C.codeLabel(kind),
      width: 130,
      sortable: true,
      render: entity => /*#__PURE__*/React.createElement("button", {
        type: "button",
        className: "lnk",
        style: {
          border: 0,
          padding: 0,
          background: 'none',
          font: 'inherit',
          textAlign: 'left'
        },
        disabled: disabled,
        onClick: () => onOpen(entity.ref)
      }, entity.business_code)
    }, {
      key: 'label',
      title: C.nameLabel(kind),
      width: 160,
      sortable: true,
      render: entity => entity.label
    }, ...(kind === 'op_type' ? opColumns(opCategory) : columns[kind] || []), ...(kind === 'op_type' ? [] : [{
      key: 'status',
      title: '状态',
      width: 145,
      render: entity => /*#__PURE__*/React.createElement(Status, {
        kind: kind,
        entity: entity
      })
    }])];
    function resize(key, width) {
      if (headerDisabled || !Number.isFinite(width)) return;
      const current = {};
      table.current.querySelectorAll('thead th[data-column]').forEach(cell => {
        current[cell.dataset.column] = cell.getBoundingClientRect().width;
      });
      setWidths({
        ...current,
        [key]: Math.max(56, width)
      });
    }
    const filtered = !!(scope && (scope.query || scope.status || Object.keys(scope.column_filters || {}).length));
    return /*#__PURE__*/React.createElement("div", {
      className: "card"
    }, /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame wb-table-shell",
      "data-sticky-head": true,
      "data-sticky-actions": true,
      style: {
        '--wb-table-min': '850px'
      }
    }, /*#__PURE__*/React.createElement("table", {
      ref: table,
      className: "tbl wb-table",
      "aria-label": C.resourceName(kind, opCategory) + '列表',
      style: widths ? {
        width: Object.values(widths).reduce((sum, width) => sum + width, 0),
        minWidth: 0
      } : undefined,
      "aria-busy": loading
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, C.resourceName(kind, opCategory), "\u5217\u8868\uFF0C\u7F16\u53F7\u4E0E\u64CD\u4F5C\u5217\u56FA\u5B9A\u3002"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "cbx",
      "data-column": "__selection",
      style: widths ? {
        width: widths.__selection
      } : undefined
    }, /*#__PURE__*/React.createElement("input", {
      ref: selectAll,
      type: "checkbox",
      "aria-label": "\u5168\u9009\u5F53\u524D\u9875",
      checked: all,
      disabled: disabled || !entities.length,
      onChange: event => {
        const visible = new Set(entities.map(item => item.ref));
        onSelect(event.target.checked ? Array.from(new Set(selected.concat(Array.from(visible)))) : selected.filter(ref => !visible.has(ref)));
      }
    })), cols.map(col => /*#__PURE__*/React.createElement("th", {
      key: col.key,
      scope: "col",
      "data-column": col.key,
      className: col.key === 'business_code' ? 'wb-col-key' : col.numeric ? 'r' : '',
      style: {
        width: widths ? widths[col.key] : col.width
      },
      "aria-sort": sortActive && sort === col.key ? direction === 'asc' ? 'ascending' : 'descending' : 'none'
    }, /*#__PURE__*/React.createElement(window.ResourceTableHeader, {
      column: col,
      kind: kind,
      scope: scope,
      adapter: adapter,
      matchingCount: matchingCount,
      sort: sort,
      direction: direction,
      sortActive: sortActive,
      onSort: onSort,
      filter: scope && scope.column_filters && scope.column_filters[col.key] || null,
      onFilter: rule => onColumnFilter(col.key, rule),
      width: widths ? widths[col.key] : col.width,
      onResize: width => resize(col.key, width),
      disabled: headerDisabled
    }))), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "actcol wb-col-actions",
      "data-column": "__actions",
      style: {
        width: widths ? widths.__actions : 216
      }
    }, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, entities.map(entity => /*#__PURE__*/React.createElement("tr", {
      key: entity.ref
    }, /*#__PURE__*/React.createElement("td", {
      className: "cbx"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      "aria-label": '选择 ' + entity.business_code + ' ' + entity.label,
      checked: selected.includes(entity.ref),
      disabled: disabled,
      onChange: event => onSelect(event.target.checked ? selected.concat(entity.ref) : selected.filter(ref => ref !== entity.ref))
    })), cols.map(col => /*#__PURE__*/React.createElement("td", {
      key: col.key,
      className: col.key === 'business_code' ? 'wb-col-key' : col.numeric ? 'r' : '',
      style: {
        overflowWrap: 'anywhere',
        whiteSpace: 'normal'
      }
    }, col.render(entity), col.key === 'label' && entity.issues.some(issue => issue.scope !== 'collection') && /*#__PURE__*/React.createElement("span", {
      className: "muted",
      style: {
        display: 'block',
        fontSize: 12
      }
    }, "\u5F85\u6838\u5BF9 ", entity.issues.filter(issue => issue.scope !== 'collection').length, " \u9879"))), /*#__PURE__*/React.createElement("td", {
      className: "actcol wb-col-actions"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rowact"
    }, /*#__PURE__*/React.createElement(Button, {
      className: "mini",
      icon: "search",
      disabled: disabled,
      onClick: () => onOpen(entity.ref)
    }, kind === 'op_type' ? entity.fields.category === 'internal' ? '查看绑定' : entity.fields.category === 'external' ? '查看供应商' : '查看/编辑' : '查看/编辑'), /*#__PURE__*/React.createElement(Button, {
      className: "mini danger",
      icon: "trash-2",
      reasonDisplay: "inline",
      reason: disabled ? '正在处理，请稍候。' : C.blocked(entity.write_context, kind, 'delete', source),
      onClick: () => onDelete(entity.ref)
    }, "\u5220\u9664"))))), !entities.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: cols.length + 2
    }, /*#__PURE__*/React.createElement(window.WorkbenchControls.EmptyState, {
      kind: loading ? 'loading' : error ? 'error' : filtered ? 'filtered' : 'empty',
      error: error,
      action: error ? /*#__PURE__*/React.createElement(Button, {
        onClick: onRetry
      }, "\u5237\u65B0") : filtered ? /*#__PURE__*/React.createElement(Button, {
        onClick: onClear
      }, "\u6E05\u9664\u7B5B\u9009") : undefined
    })))))));
  }
  function Pager({
    page,
    onPage,
    onSize,
    disabled
  }) {
    return /*#__PURE__*/React.createElement(window.WorkbenchControls.Pager, {
      page: page,
      sizes: Array.from(new Set([20, 50, 100, page.size])).sort((a, b) => a - b),
      unit: "\u9879",
      label: "",
      sizeLabel: "\u6BCF\u9875\u6761\u6570",
      showPageJump: true,
      onPage: onPage,
      onSize: onSize,
      disabled: disabled
    });
  }
  ResourceTables.Pager = Pager;
  window.ResourceTables = ResourceTables;
})();
