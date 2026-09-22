function SystemLive({ boot, theme, initialContext }) {
  const { ControlButton, MetricStrip, Metric } = window.APSWorkbenchUI;
  const model = window.APSSystemWorkbench;
  const [payload, setPayload] = React.useState(null), [error, setError] = React.useState('');
  const [loading, setLoading] = React.useState(true), [revision, refresh] = React.useReducer(value => value + 1, 0);
  const [start] = React.useState(() => window.SystemMaintenanceAPI.pageContext(initialContext));
  const [tab, setTab] = React.useState(start.tab);
  const [notice, setNotice] = React.useState(''), [pageSize, setPageSize] = React.useState(start.page_size);
  const [density, setDensity] = React.useState(() => window.WorkbenchDensity.get());
  React.useEffect(() => window.WorkbenchDensity.subscribe(setDensity), []);
  const compact = density.density === 'compact', setCompact = value => window.WorkbenchDensity.set(value ? 'compact' : 'comfortable');
  const [recordContexts, setRecordContexts] = React.useState(start.records);
  const recordContext = React.useCallback((kind, value) => setRecordContexts(previous => JSON.stringify(previous[kind]) === JSON.stringify(value) ? previous : { ...previous, [kind]: value }), []);
  const [readSuspended, setReadSuspended] = React.useState(true);
  const [local, setLocal] = React.useState(() => ({ checks: [], checkedAt: new Date().toISOString() }));
  React.useLayoutEffect(() => {
    const report = model.inspectEnvironment(window, { theme, onSetTheme: value => window.APSWorkbenchTheme.set(value) });
    setLocal({ schemaVersion: report.schemaVersion, scope: 'workbench-page', checkedAt: report.checkedAt, protocol: report.protocol,
      checks: report.checks.map(item => item.id === 'model' && item.status === 'available' ? { ...item,
        detail: '页面模型已加载；本机数据由各页签单独读取。' } : item) });
  }, [theme, revision]);
  // 系统管理只读本机数据；维护操作结果没确认前暂停读取，不用别的数据顶替。
  React.useEffect(() => {
    if (readSuspended) { setLoading(false); setPayload(null); setError(''); return; }
    const controller = new AbortController(); setLoading(true); setError('');
    window.APSWorkbenchTransport.read(boot.overview_url, controller.signal).then(result => {
      if (!window.APSWorkbenchSystemContract.validate(result.data))
        throw new Error('读到的本机系统信息不完整，页面没有改动。请点「重新检查」重试。');
      setPayload(result);
    }).catch(problem => { if (problem.name !== 'AbortError') { setError(problem.message); setPayload(null); } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [revision, readSuspended]);
  const data = payload && payload.data;
  window.WorkbenchPageContext.useSnapshot({ tab, page_size: pageSize, records: recordContexts }, !readSuspended && !!data && !loading && !error);
  const tabs = [['overview', '概况'], ['backups', '备份恢复'], ['logs', '运行日志'], ['config', '配置']];
  const onTab = next => { setTab(next); setNotice(''); document.getElementById('sm-tab-' + next).focus(); };
  const diagnosticName = '页面诊断.json';
  const exportDiagnostic = () => {
    try { window.APSWorkbenchTransport.downloadJSON(diagnosticName, { instance: boot.instance_label,
      page_check: local, system: payload }); setNotice(window.WorkbenchTerms.download_started(diagnosticName)); }
    catch (problem) { setNotice('页面诊断导出失败：' + problem.message); }
  };
  const ready = local.checks.filter(item => item.status === 'available').length;
  const stateLabel = state => ({ available: '可读取', empty: '暂无记录', partial: '需核对', missing: '文件夹不存在', error: '读取失败', not_read: '未读取' }[state] || '未知');
  return <div className={'sm-workbench' + (compact ? ' sm-compact' : '')} data-source="current" data-live="true">
    <header className="sm-header"><div><h2 className="wb-page-title">系统管理</h2><p className="wb-page-context">本机备份恢复、日志与自动维护</p></div><div className="sm-actions">
      <ControlButton className="sm-button sm-icon-button" size="sm" title="重新检查" aria-label="重新检查" disabled={loading || readSuspended} onClick={() => { refresh(); setNotice(''); }}><SMIcon name="refresh-cw" /></ControlButton>
      <SMExport disabled={!payload || loading || readSuspended} onClick={exportDiagnostic}>导出页面诊断</SMExport>
    </div></header>
    <div className="sm-source-bar"><span className="sm-source-note">{boot.instance_label + (payload ? ' · ' + window.WorkbenchTerms.data_as_of(window.WorkbenchFormat.dateTime(payload.meta.as_of)) : ' · 尚未完成读取')}</span></div>
    <MetricStrip columns={4} className="sm-metrics"><Metric label="当前页面检查" value={ready + ' / ' + local.checks.length} helper="仅页面依赖与资源" />
      <Metric label="本机数据读取" value={readSuspended ? '读取已暂停' : loading ? '读取中' : error ? '读取失败' : payload ? '已连接' : '未读取'} helper={readSuspended ? '请先查询上次维护操作的结果' : '来自本机数据'} tone={error ? 'danger' : undefined} />
      <Metric label="数据库状态" value={data ? stateLabel(data.database.state) : '未知'} helper="尚未执行完整性检查" tone={data && data.database.state === 'error' ? 'danger' : undefined} />
      <Metric label="备份校验" value="未校验" helper={data && data.backups.count != null ? data.backups.count + ' 个备份文件' : '尚未校验'} />
    </MetricStrip>
    {notice && <p className="sm-notice" role="status">{notice}</p>}
    {error && <div className="sm-notice sm-tone-danger" role="alert">{error}<ControlButton size="sm" onClick={refresh}>重试</ControlButton></div>}
    <div className="sm-tabs" role="tablist" aria-label="系统管理页签">{tabs.map(([key, label], index) => <button type="button" className={'sm-tab' + (tab === key ? ' sm-active' : '')}
      key={key} id={'sm-tab-' + key} role="tab" aria-selected={tab === key} aria-controls={'sm-panel-' + key} tabIndex={tab === key ? 0 : -1} onClick={() => onTab(key)} onKeyDown={event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return; event.preventDefault();
        onTab(tabs[event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length][0]);
      }}><SMIcon name={{ overview: 'circle-check', backups: 'folder-open', logs: 'history', config: 'square-pen' }[key]} />{label}</button>)}</div>
    <div className="sm-tab-panel" id={'sm-panel-' + tab} role="tabpanel" aria-labelledby={'sm-tab-' + tab}>
      <window.SystemMaintenanceWorkspace tab={tab} theme={theme} onSetTheme={value => window.APSWorkbenchTheme.set(value)}
        pageSize={pageSize} onPageSize={setPageSize} compact={compact} onCompact={setCompact} revision={revision}
        onChanged={refresh} onReadSuspendedChange={setReadSuspended} recordContexts={recordContexts} onRecordContext={recordContext}>
        {loading ? <p role="status" className="sm-note">正在读取本机状态…</p> : !data ? <SMUnavailable title="本机状态未能读取">页面没有用其他数据代替，请点「重新检查」重试。</SMUnavailable> :
        <SystemLiveOverview data={data} report={local} onTab={onTab} />}
      </window.SystemMaintenanceWorkspace>
    </div>
  </div>;
}

function SystemLiveOverview({ data, report, onTab }) {
  const backup = data.backups, logs = data.logs, config = data.config;
  const entries = [
    { tab: 'backups', title: '备份与恢复', icon: 'folder-open', status: backup.count == null ? '备份信息待核对' : backup.count + ' 个备份文件 · 未校验', description: backup.message },
    { tab: 'logs', title: '运行日志', icon: 'history', status: logs.operation_record_count == null ? '操作记录数量未知' : logs.operation_record_count + ' 条操作记录', description: logs.message },
    { tab: 'config', title: '自动维护规则', icon: 'square-pen', status: config.values ? '自动备份' + (config.values.auto_backup_enabled === 'yes' ? '已开启' : '已关闭') : '配置读取失败', description: config.message }
  ];
  return <div className="sm-overview-layout"><section className="sm-section sm-maintenance"><div className="sm-section-head"><h3>本机维护事项</h3><span className="sm-meta">备份、日志与维护规则</span></div>
    {entries.map(item => <button key={item.tab} type="button" className="sm-work-row" data-sm-destination={item.tab} title={'查看' + item.title} aria-label={'查看' + item.title}
      aria-describedby={'sm-work-summary-' + item.tab} onClick={() => onTab(item.tab)}><span className="sm-work-icon"><SMIcon name={item.icon} /></span>
      <span className="sm-work-copy"><span className="sm-work-title">{item.title}</span><span className="sm-work-summary" id={'sm-work-summary-' + item.tab}>
        <strong className={data[item.tab === 'config' ? 'config' : item.tab].state === 'error' ? 'sm-tone-danger' : 'sm-meta'}>{item.status}</strong>
        <span className="sm-work-description">{item.description}</span></span></span><span className="sm-work-arrow" aria-hidden="true"><SMIcon name="chevron-right" /></span></button>)}
    <details className="sm-rules"><summary>最近自动维护结果</summary>{data.maintenance.jobs.map(job => <p key={job.kind}>
      {{ auto_backup: '自动备份', auto_backup_cleanup: '备份清理', auto_log_cleanup: '操作日志清理' }[job.kind]}：
      {job.last_run_time ? window.WorkbenchFormat.dateTime(job.last_run_time) : '暂无可确认的执行时间'} · {job.result ? ({ completed: '已记录完成', failed: '失败', partial: '部分异常', skipped: '已跳过', invalid: '结果异常', unknown: '结果待核对', not_recorded: '未留存结果' }[job.result.status]) : '未读取结果'}
    </p>)}</details>
  </section><details className="sm-section sm-environment"><summary>页面环境自检<span className="sm-meta">{report.checks.filter(item => item.status === 'available').length} / {report.checks.length} 项可用</span></summary>
    <p className="sm-meta">检查时间 {window.WorkbenchFormat.instant(report.checkedAt)}</p>
    <div className="wb-table-shell wb-table-frame" data-sticky-head><table className="wb-table sm-table sm-check-table">
      <caption className="wb-visually-hidden">当前页面环境检查</caption>
      <thead><tr><th scope="col">检查项</th><th scope="col">结果</th><th scope="col">检查范围</th></tr></thead>
      <tbody>{report.checks.map(item => <tr key={item.id}><th scope="row">{item.label}</th><td><SMStatus state={item.status} /></td><td>{item.detail}</td></tr>)}</tbody>
    </table></div></details></div>;
}
