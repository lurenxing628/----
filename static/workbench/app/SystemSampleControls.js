// Current sample presenters use the shared controls; sample records remain read-only.
function SMDisabled({
  label,
  reason
}) {
  return /*#__PURE__*/React.createElement("span", {
    className: "sm-disabled"
  }, /*#__PURE__*/React.createElement(window.ResourceControls.Button, {
    icon: label.includes('删除') ? 'trash-2' : undefined,
    className: "btn sm-button",
    reason: reason,
    reasonDisplay: "tooltip",
    "aria-label": label + '：' + reason
  }, label));
}
function SMRecords({
  kind,
  source,
  pageSize,
  onPageSize,
  exportLogs,
  downloadReady
}) {
  const model = window.APSSystemWorkbench,
    {
      DataTable,
      ControlButton
    } = window.APSWorkbenchUI;
  const [filters, setFilters] = React.useState({
    query: '',
    type: '',
    status: '',
    level: '',
    file: '',
    start: '',
    end: ''
  });
  const [page, setPage] = React.useState(1),
    [selected, setSelected] = React.useState(null);
  const opener = React.useRef(null);
  const results = React.useMemo(() => model.filterRows(model.dataset(source)[kind], filters), [source, kind, filters]);
  const pager = model.paginate(results.rows, page, pageSize),
    connected = source === 'sample';
  const changeFilters = patch => {
    setFilters(previous => ({
      ...previous,
      ...patch
    }));
    setPage(1);
    setSelected(null);
  };
  const closeDetail = () => {
    setSelected(null);
    if (opener.current && opener.current.isConnected) opener.current.focus();
  };
  const columns = [{
    key: 'time',
    title: '时间',
    render: row => /*#__PURE__*/React.createElement("time", {
      className: "sm-time"
    }, row.time)
  }, {
    key: 'type',
    title: '类型',
    render: row => model.TYPES[row.type]
  }, {
    key: 'status',
    title: '状态',
    render: row => /*#__PURE__*/React.createElement(SMStatus, {
      state: row.status
    })
  }, ...(kind === 'logs' ? [{
    key: 'level',
    title: '级别',
    render: row => /*#__PURE__*/React.createElement("span", {
      className: 'sm-level sm-level-' + row.level
    }, model.LEVELS[row.level] || row.level)
  }] : []), {
    key: 'summary',
    title: kind === 'logs' ? '摘要 / 来源' : '记录 / 文件',
    render: row => /*#__PURE__*/React.createElement("div", {
      className: "sm-summary"
    }, /*#__PURE__*/React.createElement("strong", null, row.summary), /*#__PURE__*/React.createElement("small", null, kind === 'logs' ? model.SOURCES[row.file] || row.file : row.filename || '未生成文件'))
  }, ...(kind === 'backups' ? [{
    key: 'sizeBytes',
    title: '大小',
    align: 'right',
    render: row => row.sizeBytes === null ? '不适用' : (row.sizeBytes / 1024 / 1024).toFixed(1) + ' MB'
  }] : []), {
    key: 'detail',
    title: '详情',
    render: row => /*#__PURE__*/React.createElement(ControlButton, {
      className: "sm-button sm-icon-button sm-quiet-button",
      size: "sm",
      title: "\u67E5\u770B\u8BE6\u60C5",
      "aria-label": '查看详情 ' + row.id,
      "data-sm-detail": row.id,
      "aria-controls": "sm-record-detail",
      "aria-expanded": !!selected && selected.id === row.id,
      onClick: e => {
        opener.current = e.currentTarget;
        setSelected(row);
      }
    }, /*#__PURE__*/React.createElement(SMIcon, {
      name: "chevron-right"
    }))
  }].map(column => ({
    ...column,
    sortable: false,
    filterable: false
  }));
  return /*#__PURE__*/React.createElement("section", {
    className: "sm-section"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sm-section-head"
  }, /*#__PURE__*/React.createElement("h3", null, kind === 'logs' ? '运行日志与操作记录' : '备份与维护记录'), /*#__PURE__*/React.createElement("span", {
    className: "sm-meta"
  }, connected ? '固定样例截至 ' + model.SAMPLE_DATE + ' 18:00' : '本机记录尚未读取')), /*#__PURE__*/React.createElement("div", {
    className: "sm-toolbar"
  }, /*#__PURE__*/React.createElement(SMFilters, {
    kind: kind,
    filters: filters,
    onChange: changeFilters,
    disabled: !connected
  }), /*#__PURE__*/React.createElement("div", {
    className: "sm-actions sm-record-actions"
  }, kind === 'logs' ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(SMExport, {
    disabled: !connected || !downloadReady || !!results.error || !results.rows.length,
    onClick: () => exportLogs(filters, results.rows.length)
  }, "\u5BFC\u51FA\u6837\u4F8B\u65E5\u5FD7 CSV"), /*#__PURE__*/React.createElement(SMDisabled, {
    label: "\u6B63\u5F0F\u8BCA\u65AD\u5305",
    reason: "\u6B64\u529F\u80FD\u5C1A\u672A\u5F00\u901A\u3002\u5F53\u524D\u53EA\u80FD\u5BFC\u51FA\u4E0A\u9762\u7684\u6837\u4F8B\u65E5\u5FD7 CSV\u3002"
  })) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(SMDisabled, {
    label: "\u65B0\u589E\u5907\u4EFD",
    reason: "\u6B64\u529F\u80FD\u5C1A\u672A\u5F00\u901A\u3002\u5F53\u524D\u53EA\u663E\u793A\u6837\u4F8B\u8BB0\u5F55\u3002"
  }), /*#__PURE__*/React.createElement(SMDisabled, {
    label: "\u6062\u590D\u5907\u4EFD",
    reason: "\u6B64\u529F\u80FD\u5C1A\u672A\u5F00\u901A\u3002\u5F53\u524D\u53EA\u663E\u793A\u6837\u4F8B\u8BB0\u5F55\u3002"
  }), /*#__PURE__*/React.createElement(SMDisabled, {
    label: "\u5220\u9664\u5907\u4EFD",
    reason: "\u6B64\u529F\u80FD\u5C1A\u672A\u5F00\u901A\u3002\u5F53\u524D\u53EA\u663E\u793A\u6837\u4F8B\u8BB0\u5F55\u3002"
  })))), /*#__PURE__*/React.createElement("p", {
    className: "sm-note"
  }, kind === 'logs' ? '运行文件日志只读；操作记录单独归类。' : connected ? '含待执行、受阻情境，不等同于已有备份文件清单。' : '文件清单与完整性校验结果尚未读取。'), results.error && /*#__PURE__*/React.createElement("p", {
    className: "sm-error",
    role: "alert"
  }, results.error), !connected ? /*#__PURE__*/React.createElement(SMUnavailable, {
    title: kind === 'logs' ? '本机日志尚未读取' : '本机备份记录尚未读取'
  }, "\u672C\u539F\u578B\u4E0D\u8BFB\u53D6\u672C\u673A\u8BB0\u5F55\uFF0C\u6240\u4EE5\u603B\u6570\u672A\u77E5\u3002\u73B0\u5728\u65E0\u6CD5\u5224\u65AD\u662F\u6CA1\u6709\u8BB0\u5F55\uFF0C\u8FD8\u662F\u8BFB\u53D6\u5931\u8D25\u3002") : results.rows.length === 0 ? /*#__PURE__*/React.createElement(SMUnavailable, {
    title: results.error ? '筛选条件无效' : '没有符合条件的管理样例'
  }, results.error || '调整日期或清除筛选条件。') : /*#__PURE__*/React.createElement(DataTable, {
    className: 'sm-table sm-record-table sm-' + kind + '-table',
    columns: columns,
    rows: pager.rows,
    rowKey: "id"
  }), /*#__PURE__*/React.createElement(SMPager, {
    pager: pager,
    pageSize: pageSize,
    onPage: next => {
      setPage(next);
      setSelected(null);
    },
    onPageSize: size => {
      onPageSize(size);
      setPage(1);
      setSelected(null);
    }
  }), selected && /*#__PURE__*/React.createElement(SMRecordDetail, {
    row: selected,
    onClose: closeDetail,
    kind: kind
  }));
}
function SMConfiguration({
  source,
  theme,
  onToggleTheme,
  onSetTheme,
  pageSize,
  onPageSize,
  compact,
  onCompact
}) {
  const model = window.APSSystemWorkbench,
    {
      ControlButton
    } = window.APSWorkbenchUI;
  const [draft, setDraft] = React.useState(() => ({
    ...model.SAMPLE_CONFIG
  }));
  const [preview, setPreview] = React.useState(null),
    [validated, setValidated] = React.useState(false);
  const [themeError, setThemeError] = React.useState('');
  const validation = model.validateConfig(draft);
  const themeReady = ['light', 'dark'].includes(theme) && (typeof onSetTheme === 'function' || typeof onToggleTheme === 'function');
  const changeTheme = next => {
    if (next === theme || !themeReady) return;
    setThemeError('');
    try {
      if (typeof onSetTheme === 'function') onSetTheme(next);else onToggleTheme();
    } catch (_) {
      setThemeError('主题没有切换成功，页面其他内容没有改动。请刷新页面后重试。');
    }
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "sm-configuration"
  }, /*#__PURE__*/React.createElement("section", {
    className: "sm-section sm-preferences"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sm-section-head"
  }, /*#__PURE__*/React.createElement("h3", null, "\u5373\u65F6\u9875\u9762\u504F\u597D"), /*#__PURE__*/React.createElement("span", {
    className: "sm-meta"
  }, "\u4E3B\u9898\u6CBF\u7528\u5DE5\u4F5C\u53F0\uFF1B\u5217\u8868\u8BBE\u7F6E\u53EA\u5728\u5F53\u524D\u9875\u9762\u6709\u6548")), /*#__PURE__*/React.createElement("div", {
    className: "sm-session-settings"
  }, /*#__PURE__*/React.createElement("fieldset", {
    className: "sm-choice"
  }, /*#__PURE__*/React.createElement("legend", null, "\u4E3B\u9898"), [['light', '浅色'], ['dark', '深色']].map(([value, label]) => /*#__PURE__*/React.createElement("label", {
    key: value
  }, /*#__PURE__*/React.createElement("input", {
    type: "radio",
    name: "sm-theme",
    value: value,
    checked: theme === value,
    disabled: !themeReady,
    onChange: () => changeTheme(value)
  }), label))), /*#__PURE__*/React.createElement("label", {
    className: "sm-inline-label"
  }, "\u6BCF\u9875\u6761\u6570", /*#__PURE__*/React.createElement("select", {
    name: "sm-config-page-size",
    value: pageSize,
    onChange: e => onPageSize(Number(e.target.value))
  }, [10, 25, 50].map(n => /*#__PURE__*/React.createElement("option", {
    key: n,
    value: n
  }, n, " \u6761")))), /*#__PURE__*/React.createElement("label", {
    className: "sm-inline-label"
  }, /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    name: "sm-compact",
    checked: compact,
    onChange: e => onCompact(e.target.checked)
  }), "\u7D27\u51D1\u884C\u8DDD")), !themeReady && /*#__PURE__*/React.createElement("p", {
    className: "sm-note"
  }, "\u672C\u9875\u6682\u65F6\u4E0D\u80FD\u5207\u6362\u4E3B\u9898\uFF0C\u8BF7\u5230\u5DE5\u4F5C\u53F0\u5207\u6362\u6DF1\u8272\u6216\u6D45\u8272\u3002"), themeError && /*#__PURE__*/React.createElement("p", {
    className: "sm-error",
    role: "alert"
  }, themeError)), /*#__PURE__*/React.createElement("section", {
    className: "sm-section sm-maintenance-config"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sm-section-head"
  }, /*#__PURE__*/React.createElement("h3", null, source === 'sample' ? '样例草稿 · 自动维护参数' : '本机自动维护配置'), /*#__PURE__*/React.createElement(SMDisabled, {
    label: "\u4FDD\u5B58\u6B63\u5F0F\u914D\u7F6E",
    reason: "\u6B64\u529F\u80FD\u5C1A\u672A\u5F00\u901A\u3002\u5F53\u524D\u53EA\u80FD\u68C0\u67E5\u6837\u4F8B\u8349\u7A3F\u3002"
  })), /*#__PURE__*/React.createElement("div", {
    className: "sm-config-main"
  }, source !== 'sample' ? /*#__PURE__*/React.createElement(SMUnavailable, {
    title: "\u672C\u673A\u6B63\u5F0F\u914D\u7F6E\u5C1A\u672A\u8BFB\u53D6"
  }, "\u81EA\u52A8\u5907\u4EFD\u5F00\u5173\u3001\u68C0\u67E5\u95F4\u9694\u3001\u4FDD\u7559\u65F6\u95F4\u53CA\u65E7\u914D\u7F6E\u5F02\u5E38\u5747\u672A\u77E5\u3002") : /*#__PURE__*/React.createElement("form", {
    className: "sm-config-form",
    noValidate: true,
    onSubmit: event => {
      event.preventDefault();
      setValidated(true);
      setPreview(validation.valid ? validation.value : null);
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "sm-config-groups"
  }, [['backup', '备份规则'], ['logs', '操作日志规则']].map(([group, label]) => /*#__PURE__*/React.createElement("fieldset", {
    className: "sm-config-group",
    key: group
  }, /*#__PURE__*/React.createElement("legend", null, label), model.CONFIG_FIELDS.filter(field => field.group === group).map(field => /*#__PURE__*/React.createElement("div", {
    className: "sm-config-row",
    key: field.key
  }, /*#__PURE__*/React.createElement("label", {
    htmlFor: 'sm-' + field.key
  }, field.label), /*#__PURE__*/React.createElement("div", null, field.kind === 'switch' ? /*#__PURE__*/React.createElement("label", {
    className: "sm-draft-checkbox"
  }, /*#__PURE__*/React.createElement("input", {
    id: 'sm-' + field.key,
    name: field.key,
    type: "checkbox",
    checked: draft[field.key] === 'yes',
    onChange: e => {
      setDraft({
        ...draft,
        [field.key]: e.target.checked ? 'yes' : 'no'
      });
      setPreview(null);
    }
  }), /*#__PURE__*/React.createElement("span", null, draft[field.key] === 'yes' ? '启用' : '关闭')) : /*#__PURE__*/React.createElement("div", {
    className: "sm-number"
  }, /*#__PURE__*/React.createElement("input", {
    id: 'sm-' + field.key,
    name: field.key,
    type: "number",
    step: "1",
    min: field.min,
    max: field.max,
    value: draft[field.key],
    "aria-invalid": validated && !!validation.errors[field.key],
    "aria-describedby": 'sm-help-' + field.key,
    onChange: e => {
      setDraft({
        ...draft,
        [field.key]: e.target.value
      });
      setPreview(null);
    }
  }), /*#__PURE__*/React.createElement("span", null, field.unit)), field.kind !== 'switch' && /*#__PURE__*/React.createElement("small", {
    id: 'sm-help-' + field.key,
    className: validated && validation.errors[field.key] ? 'sm-error' : 'sm-meta'
  }, validated && validation.errors[field.key] || field.min + '–' + field.max + ' ' + field.unit))))))), /*#__PURE__*/React.createElement("div", {
    className: "sm-form-footer"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sm-meta"
  }, "\u6837\u4F8B\u8349\u7A3F \xB7 \u672A\u4FDD\u5B58"), /*#__PURE__*/React.createElement("div", {
    className: "sm-actions"
  }, /*#__PURE__*/React.createElement(ControlButton, {
    className: "sm-button",
    size: "sm",
    onClick: () => {
      setDraft({
        ...model.SAMPLE_CONFIG
      });
      setValidated(false);
      setPreview(null);
    }
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "rotate-ccw"
  }), "\u8FD8\u539F\u6837\u4F8B"), /*#__PURE__*/React.createElement(ControlButton, {
    className: "sm-button sm-primary-button",
    variant: "primary",
    size: "sm",
    type: "submit"
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "check"
  }), "\u68C0\u67E5\u53C2\u6570"))), validated && !validation.valid && /*#__PURE__*/React.createElement("p", {
    className: "sm-error",
    role: "alert"
  }, "\u6837\u4F8B\u914D\u7F6E\u68C0\u67E5\u672A\u901A\u8FC7\uFF0C\u586B\u5199\u5185\u5BB9\u5DF2\u4FDD\u7559\u3002\u8BF7\u4FEE\u6B63\u6807\u51FA\u7684\u9879\u3002"), preview && /*#__PURE__*/React.createElement("div", {
    className: "sm-preview",
    role: "status"
  }, /*#__PURE__*/React.createElement("h4", {
    className: "sm-tone-success"
  }, "\u6837\u4F8B\u8349\u7A3F\u68C0\u67E5\u901A\u8FC7 \xB7 \u672A\u4FDD\u5B58"), /*#__PURE__*/React.createElement("dl", null, model.CONFIG_FIELDS.map(field => /*#__PURE__*/React.createElement(React.Fragment, {
    key: field.key
  }, /*#__PURE__*/React.createElement("dt", null, field.label), /*#__PURE__*/React.createElement("dd", null, field.kind === 'switch' ? preview[field.key] === 'yes' ? '启用' : '关闭' : preview[field.key] + ' ' + field.unit))))))), /*#__PURE__*/React.createElement("details", {
    className: "sm-rules sm-config-help"
  }, /*#__PURE__*/React.createElement("summary", null, "\u751F\u6548\u8303\u56F4\u4E0E\u81EA\u52A8\u7EF4\u62A4\u89C4\u5219"), /*#__PURE__*/React.createElement("dl", null, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5F53\u524D\u7F16\u8F91"), /*#__PURE__*/React.createElement("dd", null, source === 'sample' ? '独立管理样例' : '本机正式配置未读取')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u89E6\u53D1\u65B9\u5F0F"), /*#__PURE__*/React.createElement("dd", null, "\u6253\u5F00\u9875\u9762\u65F6\u68C0\u67E5\u4E00\u6B21")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u65E5\u5FD7\u6E05\u7406\u8303\u56F4"), /*#__PURE__*/React.createElement("dd", null, "\u64CD\u4F5C\u8BB0\u5F55\uFF0C\u4E0D\u542B\u8FD0\u884C\u6587\u4EF6\u65E5\u5FD7"))), /*#__PURE__*/React.createElement("p", null, "\u6253\u5F00\u9875\u9762\u65F6\u7CFB\u7EDF\u624D\u4F1A\u68C0\u67E5\u4E00\u6B21\u5907\u4EFD\u548C\u6E05\u7406\uFF0C\u6CA1\u6709\u540E\u53F0\u5B9A\u65F6\u4EFB\u52A1\u3002\u95F4\u9694\u53EA\u662F\u68C0\u67E5\u5468\u671F\uFF0C\u4E0D\u4FDD\u8BC1\u5728\u6307\u5B9A\u65F6\u523B\u6267\u884C\uFF1B\u6B63\u5E38\u9000\u51FA\u65F6\u7684\u5907\u4EFD\u4E5F\u53D7\u81EA\u52A8\u5907\u4EFD\u5F00\u5173\u63A7\u5236\u3002"), /*#__PURE__*/React.createElement("p", null, "\u65E5\u5FD7\u6E05\u7406\u53EA\u6E05\u64CD\u4F5C\u8BB0\u5F55\uFF0C\u4E0D\u6E05\u9664\u8FD0\u884C\u6587\u4EF6\u65E5\u5FD7\u3002\u5907\u4EFD\u5931\u8D25\u65F6\u4F1A\u8DF3\u8FC7\u672C\u8F6E\u5907\u4EFD\u6E05\u7406\uFF0C\u4FDD\u5E95\u89C4\u5219\u4E0D\u4F1A\u5220\u6389\u5168\u90E8\u8FD1\u671F\u526F\u672C\u3002"))));
}
