function SystemLive({
  boot,
  theme,
  initialContext
}) {
  const {
    ControlButton,
    MetricStrip,
    Metric
  } = window.APSWorkbenchUI;
  const model = window.APSSystemWorkbench;
  const [payload, setPayload] = React.useState(null),
    [error, setError] = React.useState('');
  const [loading, setLoading] = React.useState(true),
    [revision, refresh] = React.useReducer(value => value + 1, 0);
  const [start] = React.useState(() => window.SystemMaintenanceAPI.pageContext(initialContext));
  const [source, setSource] = React.useState(start.source),
    [tab, setTab] = React.useState(start.tab);
  const [notice, setNotice] = React.useState(''),
    [pageSize, setPageSize] = React.useState(start.page_size);
  const [density, setDensity] = React.useState(() => window.WorkbenchDensity.get());
  React.useEffect(() => window.WorkbenchDensity.subscribe(setDensity), []);
  const compact = density.density === 'compact',
    setCompact = value => window.WorkbenchDensity.set(value ? 'compact' : 'comfortable');
  const [recordContexts, setRecordContexts] = React.useState(start.records);
  const recordContext = React.useCallback((kind, value) => setRecordContexts(previous => JSON.stringify(previous[kind]) === JSON.stringify(value) ? previous : {
    ...previous,
    [kind]: value
  }), []);
  const [readSuspended, setReadSuspended] = React.useState(true);
  const [local, setLocal] = React.useState(() => ({
    checks: [],
    checkedAt: new Date().toISOString()
  }));
  React.useLayoutEffect(() => {
    const report = model.inspectEnvironment(window, {
      theme,
      onSetTheme: value => window.APSWorkbenchTheme.set(value)
    });
    setLocal({
      schemaVersion: report.schemaVersion,
      scope: 'workbench-page',
      checkedAt: report.checkedAt,
      protocol: report.protocol,
      checks: report.checks.map(item => item.id === 'model' && item.status === 'available' ? {
        ...item,
        detail: '管理资源模型已加载；独立管理样例不参与本机数据读写。'
      } : item)
    });
  }, [theme, revision]);
  React.useEffect(() => {
    if (source !== 'current' || readSuspended) {
      setLoading(false);
      if (readSuspended) {
        setPayload(null);
        setError('');
      }
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError('');
    window.APSWorkbenchTransport.read(boot.overview_url, controller.signal).then(result => {
      if (!window.APSWorkbenchSystemContract.validate(result.data)) throw new Error('读到的本机系统信息不完整，页面没有改动。请点「重新检查」重试。');
      setPayload(result);
    }).catch(problem => {
      if (problem.name !== 'AbortError') {
        setError(problem.message);
        setPayload(null);
      }
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [revision, source, readSuspended]);
  const data = payload && payload.data,
    current = source === 'current';
  window.WorkbenchPageContext.useSnapshot({
    source,
    tab,
    page_size: pageSize,
    records: recordContexts
  }, !readSuspended && (!current || !!data && !loading && !error));
  const tabs = [['overview', '概况'], ['backups', '备份恢复'], ['logs', '运行日志'], ['config', '配置']];
  const onTab = next => {
    setTab(next);
    setNotice('');
    document.getElementById('sm-tab-' + next).focus();
  };
  const exportDiagnostic = () => {
    try {
      window.APSWorkbenchTransport.downloadJSON('系统诊断.json', {
        instance: boot.instance_label,
        page_check: local,
        system: payload
      });
      setNotice('已生成本次诊断文件并交给浏览器下载。');
    } catch (problem) {
      setNotice('诊断导出失败：' + problem.message);
    }
  };
  const exportSampleLogs = filters => {
    try {
      const file = model.sampleLogCSV(filters);
      model.download(window, '管理样例日志.csv', 'text/csv;charset=utf-8', file);
      setNotice('已生成独立管理样例日志，不含本机记录。');
    } catch (problem) {
      setNotice('样例日志导出失败：' + problem.message);
    }
  };
  const ready = local.checks.filter(item => item.status === 'available').length;
  const stateLabel = state => ({
    available: '可读取',
    empty: '暂无记录',
    partial: '需核对',
    missing: '文件夹不存在',
    error: '读取失败',
    not_read: '未读取'
  })[state] || '未知';
  return /*#__PURE__*/React.createElement("div", {
    className: 'sm-workbench' + (compact ? ' sm-compact' : ''),
    "data-source": source,
    "data-live": "true"
  }, /*#__PURE__*/React.createElement("header", {
    className: "sm-header"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h2", {
    className: "wb-page-title"
  }, "\u7CFB\u7EDF\u7BA1\u7406"), /*#__PURE__*/React.createElement("p", {
    className: "wb-page-context"
  }, "\u672C\u673A\u5907\u4EFD\u6062\u590D\u3001\u65E5\u5FD7\u4E0E\u81EA\u52A8\u7EF4\u62A4")), /*#__PURE__*/React.createElement("div", {
    className: "sm-actions"
  }, /*#__PURE__*/React.createElement(ControlButton, {
    className: "sm-button sm-icon-button",
    size: "sm",
    title: "\u5237\u65B0\u672C\u673A\u72B6\u6001",
    "aria-label": "\u91CD\u65B0\u68C0\u67E5",
    disabled: loading || !current || readSuspended,
    onClick: () => {
      refresh();
      setNotice('');
    }
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "refresh-cw"
  })), /*#__PURE__*/React.createElement(SMExport, {
    disabled: !payload || loading || !current || readSuspended,
    onClick: exportDiagnostic
  }, "\u5BFC\u51FA\u8BCA\u65AD\u6587\u4EF6"))), /*#__PURE__*/React.createElement("div", {
    className: "sm-source-bar"
  }, /*#__PURE__*/React.createElement("fieldset", {
    className: "sm-choice"
  }, /*#__PURE__*/React.createElement("legend", null, "\u6570\u636E\u6765\u6E90"), [['current', '本机数据'], ['sample', '管理样例']].map(([value, label]) => /*#__PURE__*/React.createElement("label", {
    key: value
  }, /*#__PURE__*/React.createElement("input", {
    type: "radio",
    name: "sm-source",
    value: value,
    checked: source === value,
    onChange: () => {
      setSource(value);
      setNotice('');
    }
  }), label))), /*#__PURE__*/React.createElement("span", {
    className: "sm-source-note"
  }, current ? boot.instance_label + (payload ? ' · 数据截至 ' + window.WorkbenchFormat.dateTime(payload.meta.as_of) : ' · 尚未完成读取') : '独立管理样例 · 不写入本机数据')), /*#__PURE__*/React.createElement(MetricStrip, {
    columns: 4,
    className: "sm-metrics"
  }, /*#__PURE__*/React.createElement(Metric, {
    label: "\u5F53\u524D\u9875\u9762\u68C0\u67E5",
    value: ready + ' / ' + local.checks.length,
    helper: "\u4EC5\u9875\u9762\u4F9D\u8D56\u4E0E\u8D44\u6E90"
  }), /*#__PURE__*/React.createElement(Metric, {
    label: "\u672C\u673A\u6570\u636E\u8BFB\u53D6",
    value: !current ? '演示模式' : readSuspended ? '读取已暂停' : loading ? '读取中' : error ? '读取失败' : payload ? '已连接' : '未读取',
    helper: current ? readSuspended ? '请先查询上次维护操作的结果' : '来自本机服务' : '独立固定样例',
    tone: error && current ? 'danger' : undefined
  }), /*#__PURE__*/React.createElement(Metric, {
    label: "\u6570\u636E\u5E93\u72B6\u6001",
    value: current && data ? stateLabel(data.database.state) : '未知',
    helper: "\u5C1A\u672A\u6267\u884C\u5B8C\u6574\u6027\u68C0\u67E5",
    tone: current && data && data.database.state === 'error' ? 'danger' : undefined
  }), /*#__PURE__*/React.createElement(Metric, {
    label: "\u5907\u4EFD\u6821\u9A8C",
    value: "\u672A\u6821\u9A8C",
    helper: current && data && data.backups.count != null ? data.backups.count + ' 个备份文件' : '尚未校验'
  })), notice && /*#__PURE__*/React.createElement("p", {
    className: "sm-notice",
    role: "status"
  }, notice), current && error && /*#__PURE__*/React.createElement("div", {
    className: "sm-notice sm-tone-danger",
    role: "alert"
  }, error, /*#__PURE__*/React.createElement(ControlButton, {
    size: "sm",
    onClick: refresh
  }, "\u91CD\u8BD5")), /*#__PURE__*/React.createElement("div", {
    className: "sm-tabs",
    role: "tablist",
    "aria-label": "\u7CFB\u7EDF\u7BA1\u7406\u9875\u7B7E"
  }, tabs.map(([key, label], index) => /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: 'sm-tab' + (tab === key ? ' sm-active' : ''),
    key: key,
    id: 'sm-tab-' + key,
    role: "tab",
    "aria-selected": tab === key,
    "aria-controls": 'sm-panel-' + key,
    tabIndex: tab === key ? 0 : -1,
    onClick: () => onTab(key),
    onKeyDown: event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      onTab(tabs[event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length][0]);
    }
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: {
      overview: 'circle-check',
      backups: 'folder-open',
      logs: 'history',
      config: 'square-pen'
    }[key]
  }), label))), /*#__PURE__*/React.createElement("div", {
    className: "sm-tab-panel",
    id: 'sm-panel-' + tab,
    role: "tabpanel",
    "aria-labelledby": 'sm-tab-' + tab
  }, /*#__PURE__*/React.createElement(window.SystemMaintenanceWorkspace, {
    tab: tab,
    source: source,
    theme: theme,
    onSetTheme: value => window.APSWorkbenchTheme.set(value),
    pageSize: pageSize,
    onPageSize: setPageSize,
    compact: compact,
    onCompact: setCompact,
    revision: revision,
    onChanged: refresh,
    onReadSuspendedChange: setReadSuspended,
    recordContexts: recordContexts,
    onRecordContext: recordContext
  }, !current ? /*#__PURE__*/React.createElement(React.Fragment, null, tab === 'overview' ? /*#__PURE__*/React.createElement(SMOverview, {
    report: local,
    source: "sample",
    onTab: onTab
  }) : tab === 'config' ? /*#__PURE__*/React.createElement(SMConfiguration, {
    source: "sample",
    theme: theme,
    onSetTheme: value => window.APSWorkbenchTheme.set(value),
    pageSize: pageSize,
    onPageSize: setPageSize,
    compact: compact,
    onCompact: setCompact
  }) : /*#__PURE__*/React.createElement(SMRecords, {
    kind: tab,
    source: "sample",
    pageSize: pageSize,
    onPageSize: setPageSize,
    exportLogs: exportSampleLogs,
    downloadReady: true
  })) : loading ? /*#__PURE__*/React.createElement("p", {
    role: "status",
    className: "sm-note"
  }, "\u6B63\u5728\u8BFB\u53D6\u672C\u673A\u72B6\u6001\u2026") : !data ? /*#__PURE__*/React.createElement(SMUnavailable, {
    title: "\u672C\u673A\u72B6\u6001\u672A\u80FD\u8BFB\u53D6"
  }, "\u6CA1\u6709\u7528\u7BA1\u7406\u6837\u4F8B\u66FF\u4EE3\u672C\u673A\u6570\u636E\u3002") : /*#__PURE__*/React.createElement(SystemLiveOverview, {
    data: data,
    report: local,
    onTab: onTab
  }))));
}
function SystemLiveOverview({
  data,
  report,
  onTab
}) {
  const backup = data.backups,
    logs = data.logs,
    config = data.config;
  const entries = [{
    tab: 'backups',
    title: '备份与恢复',
    icon: 'folder-open',
    status: backup.count == null ? '备份信息待核对' : backup.count + ' 个备份文件 · 未校验',
    description: backup.message
  }, {
    tab: 'logs',
    title: '运行日志',
    icon: 'history',
    status: logs.operation_record_count == null ? '操作记录数量未知' : logs.operation_record_count + ' 条操作记录',
    description: logs.message
  }, {
    tab: 'config',
    title: '自动维护规则',
    icon: 'square-pen',
    status: config.values ? '自动备份' + (config.values.auto_backup_enabled === 'yes' ? '已启用' : '已关闭') : '配置读取失败',
    description: config.message
  }];
  return /*#__PURE__*/React.createElement("div", {
    className: "sm-overview-layout"
  }, /*#__PURE__*/React.createElement("section", {
    className: "sm-section sm-maintenance"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sm-section-head"
  }, /*#__PURE__*/React.createElement("h3", null, "\u672C\u673A\u7EF4\u62A4\u4E8B\u9879"), /*#__PURE__*/React.createElement("span", {
    className: "sm-meta"
  }, "\u5907\u4EFD\u3001\u65E5\u5FD7\u4E0E\u7EF4\u62A4\u89C4\u5219")), entries.map(item => /*#__PURE__*/React.createElement("button", {
    key: item.tab,
    type: "button",
    className: "sm-work-row",
    "data-sm-destination": item.tab,
    title: '查看' + item.title,
    "aria-label": '查看' + item.title,
    "aria-describedby": 'sm-work-summary-' + item.tab,
    onClick: () => onTab(item.tab)
  }, /*#__PURE__*/React.createElement("span", {
    className: "sm-work-icon"
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: item.icon
  })), /*#__PURE__*/React.createElement("span", {
    className: "sm-work-copy"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sm-work-title"
  }, item.title), /*#__PURE__*/React.createElement("span", {
    className: "sm-work-summary",
    id: 'sm-work-summary-' + item.tab
  }, /*#__PURE__*/React.createElement("strong", {
    className: data[item.tab === 'config' ? 'config' : item.tab].state === 'error' ? 'sm-tone-danger' : 'sm-meta'
  }, item.status), /*#__PURE__*/React.createElement("span", {
    className: "sm-work-description"
  }, item.description))), /*#__PURE__*/React.createElement("span", {
    className: "sm-work-arrow",
    "aria-hidden": "true"
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "chevron-right"
  })))), /*#__PURE__*/React.createElement("details", {
    className: "sm-rules"
  }, /*#__PURE__*/React.createElement("summary", null, "\u6700\u8FD1\u81EA\u52A8\u7EF4\u62A4\u7ED3\u679C"), data.maintenance.jobs.map(job => /*#__PURE__*/React.createElement("p", {
    key: job.kind
  }, {
    auto_backup: '自动备份',
    auto_backup_cleanup: '备份清理',
    auto_log_cleanup: '操作日志清理'
  }[job.kind], "\uFF1A", job.last_run_time ? window.WorkbenchFormat.dateTime(job.last_run_time) : '暂无可确认的执行时间', " \xB7 ", job.result ? {
    completed: '已记录完成',
    failed: '失败',
    partial: '部分异常',
    skipped: '已跳过',
    invalid: '结果异常',
    unknown: '结果待核对',
    not_recorded: '未留存结果'
  }[job.result.status] : '未读取结果')))), /*#__PURE__*/React.createElement("details", {
    className: "sm-section sm-environment"
  }, /*#__PURE__*/React.createElement("summary", null, "\u9875\u9762\u73AF\u5883\u81EA\u68C0", /*#__PURE__*/React.createElement("span", {
    className: "sm-meta"
  }, report.checks.filter(item => item.status === 'available').length, " / ", report.checks.length, " \u9879\u53EF\u7528")), /*#__PURE__*/React.createElement("p", {
    className: "sm-meta"
  }, "\u68C0\u67E5\u65F6\u95F4 ", window.WorkbenchFormat.instant(report.checkedAt)), /*#__PURE__*/React.createElement("div", {
    className: "wb-table-shell wb-table-frame",
    "data-sticky-head": true
  }, /*#__PURE__*/React.createElement("table", {
    className: "wb-table sm-table sm-check-table"
  }, /*#__PURE__*/React.createElement("caption", {
    className: "wb-visually-hidden"
  }, "\u5F53\u524D\u9875\u9762\u73AF\u5883\u68C0\u67E5"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
    scope: "col"
  }, "\u68C0\u67E5\u9879"), /*#__PURE__*/React.createElement("th", {
    scope: "col"
  }, "\u7ED3\u679C"), /*#__PURE__*/React.createElement("th", {
    scope: "col"
  }, "\u68C0\u67E5\u8303\u56F4"))), /*#__PURE__*/React.createElement("tbody", null, report.checks.map(item => /*#__PURE__*/React.createElement("tr", {
    key: item.id
  }, /*#__PURE__*/React.createElement("th", {
    scope: "row"
  }, item.label), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(SMStatus, {
    state: item.status
  })), /*#__PURE__*/React.createElement("td", null, item.detail))))))));
}
function SystemLiveFiles({
  kind,
  data,
  pageSize,
  onPageSize
}) {
  const {
    DataTable,
    ControlButton
  } = window.APSWorkbenchUI;
  const [page, setPage] = React.useState(1),
    [selected, setSelected] = React.useState(null);
  const opener = React.useRef(null),
    detail = React.useRef(null);
  React.useEffect(() => {
    if (selected && detail.current) detail.current.focus();
  }, [selected]);
  const close = () => {
    setSelected(null);
    if (opener.current && opener.current.isConnected) opener.current.focus();
  };
  const entries = data.files,
    pages = Math.max(1, Math.ceil(entries.length / pageSize)),
    current = Math.min(page, pages);
  const rows = entries.slice((current - 1) * pageSize, current * pageSize);
  const columns = [{
    key: 'modified_at',
    title: '文件修改时间',
    width: 176,
    nowrap: true,
    render: row => window.WorkbenchFormat.dateTime(row.modified_at)
  }, {
    key: 'filename',
    title: kind === 'backups' ? '备份文件' : '日志文件',
    width: 'auto'
  }, {
    key: 'status',
    title: '检查状态',
    width: 104,
    render: () => /*#__PURE__*/React.createElement(SMStatus, {
      state: "unverified"
    })
  }, {
    key: 'size_bytes',
    title: '大小',
    width: 120,
    align: 'right',
    nowrap: true,
    render: row => window.WorkbenchFormat.number(row.size_bytes / 1024, {
      digits: 1
    }) + ' KB'
  }, {
    key: 'detail',
    title: '详情',
    width: 60,
    render: row => /*#__PURE__*/React.createElement(ControlButton, {
      size: "sm",
      className: "sm-button sm-icon-button",
      title: "\u67E5\u770B\u6587\u4EF6\u4FE1\u606F",
      "aria-label": '查看文件信息 ' + row.filename,
      "aria-controls": "system-live-file-detail",
      "aria-expanded": !!selected && selected.filename === row.filename,
      onClick: event => {
        opener.current = event.currentTarget;
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
  }, /*#__PURE__*/React.createElement("h3", null, kind === 'backups' ? '备份与维护记录' : '运行日志与操作记录'), /*#__PURE__*/React.createElement("span", {
    className: "sm-meta"
  }, data.files_truncated ? '仅列最近20个文件' : '已读取文件信息')), /*#__PURE__*/React.createElement("div", {
    className: "sm-toolbar"
  }, /*#__PURE__*/React.createElement(SMFilters, {
    kind: kind,
    filters: {
      query: '',
      type: '',
      status: '',
      level: '',
      file: '',
      start: '',
      end: ''
    },
    onChange: () => {},
    disabled: true
  }), /*#__PURE__*/React.createElement("div", {
    className: "sm-actions sm-record-actions"
  }, (kind === 'backups' ? ['新增备份', '恢复备份', '删除备份'] : ['导出日志 CSV', '正式诊断包']).map(label => /*#__PURE__*/React.createElement(SMDisabled, {
    key: label,
    label: label,
    reason: window.WorkbenchTerms.outcomes.unavailable
  })))), /*#__PURE__*/React.createElement("p", {
    className: "sm-note"
  }, data.message, kind === 'logs' && data.operation_record_count != null ? ' 当前共有 ' + data.operation_record_count + ' 条操作记录。' : ''), data.error && /*#__PURE__*/React.createElement("p", {
    role: "alert",
    className: "sm-error"
  }, data.error.message), entries.length ? /*#__PURE__*/React.createElement(DataTable, {
    className: "sm-table sm-record-table",
    columns: columns,
    rows: rows,
    rowKey: "filename"
  }) : /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
    kind: data.state === 'empty' ? 'empty' : 'error',
    title: data.state === 'empty' ? '暂无文件' : '文件信息不可用',
    hint: data.message,
    action: data.state !== 'empty' ? /*#__PURE__*/React.createElement("a", {
      href: "/workbench?view=system"
    }, "\u91CD\u65B0\u8FDB\u5165\u7CFB\u7EDF\u7BA1\u7406") : undefined
  }), /*#__PURE__*/React.createElement("div", {
    className: "sm-pager"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sm-meta"
  }, "\u5DF2\u8BFB\u53D6 ", entries.length, " \u4E2A\u6587\u4EF6", data.count != null ? ' · 文件夹共 ' + data.count + ' 个' : ' · 总数尚不能确认'), /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
    page: current,
    pages: pages,
    total: entries.length,
    size: pageSize,
    sizes: [10, 25, 50],
    unit: "\u6761",
    label: "",
    onPage: setPage,
    onSize: size => {
      onPageSize(size);
      setPage(1);
    }
  })), selected && /*#__PURE__*/React.createElement("section", {
    className: "sm-detail",
    id: "system-live-file-detail",
    ref: detail,
    tabIndex: "-1",
    "aria-label": "\u672C\u673A\u6587\u4EF6\u4FE1\u606F",
    onKeyDown: event => {
      if (event.key === 'Escape') close();
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "sm-section-head"
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      overflowWrap: 'anywhere',
      minWidth: 0
    }
  }, selected.filename), /*#__PURE__*/React.createElement(ControlButton, {
    size: "sm",
    "aria-label": "\u5173\u95ED\u6587\u4EF6\u4FE1\u606F",
    onClick: close
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "x"
  }))), /*#__PURE__*/React.createElement("p", null, "\u4FEE\u6539\u65F6\u95F4 ", window.WorkbenchFormat.dateTime(selected.modified_at), " \xB7 ", selected.size_bytes, " \u5B57\u8282"), /*#__PURE__*/React.createElement("p", null, "\u4EC5\u67E5\u770B\u6587\u4EF6\u4FE1\u606F\uFF0C\u5C1A\u672A\u8BFB\u53D6\u6216\u6821\u9A8C\u6587\u4EF6\u5185\u5BB9\u3002")));
}
function SystemLiveConfig({
  data
}) {
  const model = window.APSSystemWorkbench;
  return /*#__PURE__*/React.createElement("div", {
    className: "sm-configuration"
  }, /*#__PURE__*/React.createElement("section", {
    className: "sm-section sm-maintenance-config"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sm-section-head"
  }, /*#__PURE__*/React.createElement("h3", null, "\u672C\u673A\u81EA\u52A8\u7EF4\u62A4\u914D\u7F6E"), /*#__PURE__*/React.createElement(SMDisabled, {
    label: "\u4FDD\u5B58\u6B63\u5F0F\u914D\u7F6E",
    reason: window.WorkbenchTerms.outcomes.unavailable
  })), /*#__PURE__*/React.createElement("p", {
    className: "sm-note"
  }, data.message), data.error && /*#__PURE__*/React.createElement("p", {
    className: "sm-error",
    role: "alert"
  }, data.error.message), !data.values ? /*#__PURE__*/React.createElement(SMUnavailable, {
    title: "\u914D\u7F6E\u672A\u80FD\u8BFB\u53D6"
  }, "\u6CA1\u6709\u4F7F\u7528\u7BA1\u7406\u6837\u4F8B\u4EE3\u66FF\u672C\u673A\u914D\u7F6E\u3002") : /*#__PURE__*/React.createElement("div", {
    className: "sm-config-form"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sm-config-groups"
  }, [['backup', '备份规则'], ['logs', '操作日志规则']].map(([group, label]) => /*#__PURE__*/React.createElement("fieldset", {
    className: "sm-config-group",
    key: group
  }, /*#__PURE__*/React.createElement("legend", null, label), model.CONFIG_FIELDS.filter(field => field.group === group).map(field => /*#__PURE__*/React.createElement("div", {
    className: "sm-config-row",
    key: field.key
  }, /*#__PURE__*/React.createElement("label", {
    htmlFor: 'live-' + field.key
  }, field.label), /*#__PURE__*/React.createElement("div", null, field.kind === 'switch' ? /*#__PURE__*/React.createElement("label", {
    className: "sm-draft-checkbox"
  }, /*#__PURE__*/React.createElement("input", {
    id: 'live-' + field.key,
    type: "checkbox",
    checked: data.values[field.key] === 'yes',
    disabled: true
  }), /*#__PURE__*/React.createElement("span", null, data.values[field.key] === 'yes' ? '启用' : '关闭')) : /*#__PURE__*/React.createElement("div", {
    className: "sm-number"
  }, /*#__PURE__*/React.createElement("input", {
    id: 'live-' + field.key,
    type: "number",
    value: data.values[field.key],
    readOnly: true
  }), /*#__PURE__*/React.createElement("span", null, field.unit)), data.dirty_fields.includes(field.key) ? /*#__PURE__*/React.createElement("small", {
    className: "sm-error"
  }, data.dirty_reasons[field.key]) : data.defaulted_fields.includes(field.key) ? /*#__PURE__*/React.createElement("small", {
    className: "sm-meta"
  }, "\u9ED8\u8BA4\u503C\uFF0C\u5C1A\u672A\u4FDD\u5B58") : /*#__PURE__*/React.createElement("small", {
    className: "sm-meta"
  }, "\u5DF2\u5B58\u914D\u7F6E")))))))), /*#__PURE__*/React.createElement("details", {
    className: "sm-rules"
  }, /*#__PURE__*/React.createElement("summary", null, "\u751F\u6548\u8303\u56F4\u4E0E\u81EA\u52A8\u7EF4\u62A4\u89C4\u5219"), /*#__PURE__*/React.createElement("p", null, "\u81EA\u52A8\u7EF4\u62A4\u5728\u6253\u5F00\u9875\u9762\u65F6\u68C0\u67E5\u662F\u5426\u5230\u671F\u3002"))));
}
