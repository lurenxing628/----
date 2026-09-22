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
  const [tab, setTab] = React.useState(start.tab);
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
        detail: '页面模型已加载；本机数据由各页签单独读取。'
      } : item)
    });
  }, [theme, revision]);
  // 系统管理只读本机数据；维护操作结果没确认前暂停读取，不用别的数据顶替。
  React.useEffect(() => {
    if (readSuspended) {
      setLoading(false);
      setPayload(null);
      setError('');
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
  }, [revision, readSuspended]);
  const data = payload && payload.data;
  window.WorkbenchPageContext.useSnapshot({
    tab,
    page_size: pageSize,
    records: recordContexts
  }, !readSuspended && !!data && !loading && !error);
  const tabs = [['overview', '概况'], ['backups', '备份恢复'], ['logs', '运行日志'], ['config', '配置']];
  const onTab = next => {
    setTab(next);
    setNotice('');
    document.getElementById('sm-tab-' + next).focus();
  };
  const diagnosticName = '页面诊断.json';
  const exportDiagnostic = () => {
    try {
      window.APSWorkbenchTransport.downloadJSON(diagnosticName, {
        instance: boot.instance_label,
        page_check: local,
        system: payload
      });
      setNotice(window.WorkbenchTerms.download_started(diagnosticName));
    } catch (problem) {
      setNotice('页面诊断导出失败：' + problem.message);
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
    "data-source": "current",
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
    title: "\u91CD\u65B0\u68C0\u67E5",
    "aria-label": "\u91CD\u65B0\u68C0\u67E5",
    disabled: loading || readSuspended,
    onClick: () => {
      refresh();
      setNotice('');
    }
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "refresh-cw"
  })), /*#__PURE__*/React.createElement(SMExport, {
    disabled: !payload || loading || readSuspended,
    onClick: exportDiagnostic
  }, "\u5BFC\u51FA\u9875\u9762\u8BCA\u65AD"))), /*#__PURE__*/React.createElement("div", {
    className: "sm-source-bar"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sm-source-note"
  }, boot.instance_label + (payload ? ' · ' + window.WorkbenchTerms.data_as_of(window.WorkbenchFormat.dateTime(payload.meta.as_of)) : ' · 尚未完成读取'))), /*#__PURE__*/React.createElement(MetricStrip, {
    columns: 4,
    className: "sm-metrics"
  }, /*#__PURE__*/React.createElement(Metric, {
    label: "\u5F53\u524D\u9875\u9762\u68C0\u67E5",
    value: ready + ' / ' + local.checks.length,
    helper: "\u4EC5\u9875\u9762\u4F9D\u8D56\u4E0E\u8D44\u6E90"
  }), /*#__PURE__*/React.createElement(Metric, {
    label: "\u672C\u673A\u6570\u636E\u8BFB\u53D6",
    value: readSuspended ? '读取已暂停' : loading ? '读取中' : error ? '读取失败' : payload ? '已连接' : '未读取',
    helper: readSuspended ? '请先查询上次维护操作的结果' : '来自本机数据',
    tone: error ? 'danger' : undefined
  }), /*#__PURE__*/React.createElement(Metric, {
    label: "\u6570\u636E\u5E93\u72B6\u6001",
    value: data ? stateLabel(data.database.state) : '未知',
    helper: "\u5C1A\u672A\u6267\u884C\u5B8C\u6574\u6027\u68C0\u67E5",
    tone: data && data.database.state === 'error' ? 'danger' : undefined
  }), /*#__PURE__*/React.createElement(Metric, {
    label: "\u5907\u4EFD\u6821\u9A8C",
    value: "\u672A\u6821\u9A8C",
    helper: data && data.backups.count != null ? data.backups.count + ' 个备份文件' : '尚未校验'
  })), notice && /*#__PURE__*/React.createElement("p", {
    className: "sm-notice",
    role: "status"
  }, notice), error && /*#__PURE__*/React.createElement("div", {
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
  }, loading ? /*#__PURE__*/React.createElement("p", {
    role: "status",
    className: "sm-note"
  }, "\u6B63\u5728\u8BFB\u53D6\u672C\u673A\u72B6\u6001\u2026") : !data ? /*#__PURE__*/React.createElement(SMUnavailable, {
    title: "\u672C\u673A\u72B6\u6001\u672A\u80FD\u8BFB\u53D6"
  }, "\u9875\u9762\u6CA1\u6709\u7528\u5176\u4ED6\u6570\u636E\u4EE3\u66FF\uFF0C\u8BF7\u70B9\u300C\u91CD\u65B0\u68C0\u67E5\u300D\u91CD\u8BD5\u3002") : /*#__PURE__*/React.createElement(SystemLiveOverview, {
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
    status: config.values ? '自动备份' + (config.values.auto_backup_enabled === 'yes' ? '已开启' : '已关闭') : '配置读取失败',
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
