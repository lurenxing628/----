function SystemLive({ boot, theme, initialContext }) {
  const { ControlButton, MetricStrip, Metric } = window.APSWorkbenchUI;
  const model = window.APSSystemWorkbench;
  const [payload, setPayload] = React.useState(null), [error, setError] = React.useState('');
  const [loading, setLoading] = React.useState(true), [revision, refresh] = React.useReducer(value => value + 1, 0);
  const [start] = React.useState(() => window.SystemMaintenanceAPI.pageContext(initialContext));
  const [source, setSource] = React.useState(start.source), [tab, setTab] = React.useState(start.tab);
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
        detail: '管理资源模型已加载；独立管理样例不参与本机数据读写。' } : item) });
  }, [theme, revision]);
  React.useEffect(() => {
    if (source !== 'current' || readSuspended) { setLoading(false); if (readSuspended) { setPayload(null); setError(''); } return; }
    const controller = new AbortController(); setLoading(true); setError('');
    window.APSWorkbenchTransport.read(boot.overview_url, controller.signal).then(result => {
      if (!window.APSWorkbenchSystemContract.validate(result.data))
        throw new Error('读到的本机系统信息不完整，页面没有改动。请点「重新检查」重试。');
      setPayload(result);
    }).catch(problem => { if (problem.name !== 'AbortError') { setError(problem.message); setPayload(null); } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [revision, source, readSuspended]);
  const data = payload && payload.data, current = source === 'current';
  window.WorkbenchPageContext.useSnapshot({ source, tab, page_size: pageSize, records: recordContexts }, !readSuspended && (!current || !!data && !loading && !error));
  const tabs = [['overview', '概况'], ['backups', '备份恢复'], ['logs', '运行日志'], ['config', '配置']];
  const onTab = next => { setTab(next); setNotice(''); document.getElementById('sm-tab-' + next).focus(); };
  const exportDiagnostic = () => {
    try { window.APSWorkbenchTransport.downloadJSON('系统诊断.json', { instance: boot.instance_label,
      page_check: local, system: payload }); setNotice('已生成本次诊断文件并交给浏览器下载。'); }
    catch (problem) { setNotice('诊断导出失败：' + problem.message); }
  };
  const exportSampleLogs = filters => {
    try {
      const file = model.sampleLogCSV(filters);
      model.download(window, '管理样例日志.csv', 'text/csv;charset=utf-8', file);
      setNotice('已生成独立管理样例日志，不含本机记录。');
    } catch (problem) { setNotice('样例日志导出失败：' + problem.message); }
  };
  const ready = local.checks.filter(item => item.status === 'available').length;
  const stateLabel = state => ({ available: '可读取', empty: '暂无记录', partial: '需核对', missing: '文件夹不存在', error: '读取失败', not_read: '未读取' }[state] || '未知');
  return <div className={'sm-workbench' + (compact ? ' sm-compact' : '')} data-source={source} data-live="true">
    <header className="sm-header"><div><h2 className="wb-page-title">系统管理</h2><p className="wb-page-context">本机备份恢复、日志与自动维护</p></div><div className="sm-actions">
      <ControlButton className="sm-button sm-icon-button" size="sm" title="刷新本机状态" aria-label="重新检查" disabled={loading || !current || readSuspended} onClick={() => { refresh(); setNotice(''); }}><SMIcon name="refresh-cw" /></ControlButton>
      <SMExport disabled={!payload || loading || !current || readSuspended} onClick={exportDiagnostic}>导出诊断文件</SMExport>
    </div></header>
    <div className="sm-source-bar"><fieldset className="sm-choice"><legend>数据来源</legend>{[['current', '本机数据'], ['sample', '管理样例']].map(([value, label]) => <label key={value}>
      <input type="radio" name="sm-source" value={value} checked={source === value} onChange={() => { setSource(value); setNotice(''); }} />{label}</label>)}</fieldset>
      <span className="sm-source-note">{current ? boot.instance_label + (payload ? ' · 数据截至 ' + window.WorkbenchFormat.dateTime(payload.meta.as_of) : ' · 尚未完成读取') : '独立管理样例 · 不写入本机数据'}</span></div>
    <MetricStrip columns={4} className="sm-metrics"><Metric label="当前页面检查" value={ready + ' / ' + local.checks.length} helper="仅页面依赖与资源" />
      <Metric label="本机数据读取" value={!current ? '演示模式' : readSuspended ? '读取已暂停' : loading ? '读取中' : error ? '读取失败' : payload ? '已连接' : '未读取'} helper={current ? readSuspended ? '请先查询上次维护操作的结果' : '来自本机服务' : '独立固定样例'} tone={error && current ? 'danger' : undefined} />
      <Metric label="数据库状态" value={current && data ? stateLabel(data.database.state) : '未知'} helper="尚未执行完整性检查" tone={current && data && data.database.state === 'error' ? 'danger' : undefined} />
      <Metric label="备份健康" value="未校验" helper={current && data && data.backups.count != null ? data.backups.count + ' 个备份文件' : '文件存在不代表可恢复'} />
    </MetricStrip>
    {notice && <p className="sm-notice" role="status">{notice}</p>}
    {current && error && <div className="sm-notice sm-tone-danger" role="alert">{error}<ControlButton size="sm" onClick={refresh}>重试</ControlButton></div>}
    <div className="sm-tabs" role="tablist" aria-label="系统管理页签">{tabs.map(([key, label], index) => <button type="button" className={'sm-tab' + (tab === key ? ' sm-active' : '')}
      key={key} id={'sm-tab-' + key} role="tab" aria-selected={tab === key} aria-controls={'sm-panel-' + key} tabIndex={tab === key ? 0 : -1} onClick={() => onTab(key)} onKeyDown={event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return; event.preventDefault();
        onTab(tabs[event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length][0]);
      }}><SMIcon name={{ overview: 'circle-check', backups: 'folder-open', logs: 'history', config: 'square-pen' }[key]} />{label}</button>)}</div>
    <div className="sm-tab-panel" id={'sm-panel-' + tab} role="tabpanel" aria-labelledby={'sm-tab-' + tab}>
      <window.SystemMaintenanceWorkspace tab={tab} source={source} theme={theme} onSetTheme={value => window.APSWorkbenchTheme.set(value)}
        pageSize={pageSize} onPageSize={setPageSize} compact={compact} onCompact={setCompact} revision={revision}
        onChanged={refresh} onReadSuspendedChange={setReadSuspended} recordContexts={recordContexts} onRecordContext={recordContext}>
      {!current ? <>{tab === 'overview' ? <SMOverview report={local} source="sample" onTab={onTab} /> : tab === 'config' ? <SMConfiguration source="sample" theme={theme}
        onSetTheme={value => window.APSWorkbenchTheme.set(value)} pageSize={pageSize} onPageSize={setPageSize} compact={compact} onCompact={setCompact} /> :
        <SMRecords kind={tab} source="sample" pageSize={pageSize} onPageSize={setPageSize} exportLogs={exportSampleLogs} downloadReady={true} />}</> :
        loading ? <p role="status" className="sm-note">正在读取本机状态…</p> : !data ? <SMUnavailable title="本机状态未能读取">没有用管理样例替代本机数据。</SMUnavailable> :
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
    { tab: 'config', title: '自动维护规则', icon: 'square-pen', status: config.values ? '自动备份' + (config.values.auto_backup_enabled === 'yes' ? '已启用' : '已关闭') : '配置读取失败', description: config.message }
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
    <p className="sm-meta">检查时间 {window.WorkbenchFormat.instant(report.checkedAt)} · 不代表数据库或备份健康</p>
    <div className="wb-table-shell wb-table-frame" data-sticky-head><table className="wb-table sm-table sm-check-table">
      <caption className="wb-visually-hidden">当前页面环境自检，不代表数据库或备份健康</caption>
      <thead><tr><th scope="col">检查项</th><th scope="col">结果</th><th scope="col">检查范围</th></tr></thead>
      <tbody>{report.checks.map(item => <tr key={item.id}><th scope="row">{item.label}</th><td><SMStatus state={item.status} /></td><td>{item.detail}</td></tr>)}</tbody>
    </table></div></details></div>;
}

function SystemLiveFiles({ kind, data, pageSize, onPageSize }) {
  const { DataTable, ControlButton } = window.APSWorkbenchUI;
  const [page, setPage] = React.useState(1), [selected, setSelected] = React.useState(null);
  const opener = React.useRef(null), detail = React.useRef(null);
  React.useEffect(() => { if (selected && detail.current) detail.current.focus(); }, [selected]);
  const close = () => { setSelected(null); if (opener.current && opener.current.isConnected) opener.current.focus(); };
  const entries = data.files, pages = Math.max(1, Math.ceil(entries.length / pageSize)), current = Math.min(page, pages);
  const rows = entries.slice((current - 1) * pageSize, current * pageSize);
  const columns = [
    { key: 'modified_at', title: '文件修改时间', width: 176, nowrap: true, render: row => window.WorkbenchFormat.dateTime(row.modified_at) },
    { key: 'filename', title: kind === 'backups' ? '备份文件' : '日志文件', width: 'auto' },
    { key: 'status', title: '检查状态', width: 104, render: () => <SMStatus state="unverified" /> },
    { key: 'size_bytes', title: '大小', width: 120, align: 'right', nowrap: true, render: row => window.WorkbenchFormat.number(row.size_bytes / 1024, { digits: 1 }) + ' KB' },
    { key: 'detail', title: '详情', width: 60, render: row => <ControlButton size="sm" className="sm-button sm-icon-button" title="查看文件信息" aria-label={'查看文件信息 ' + row.filename}
      aria-controls="system-live-file-detail" aria-expanded={!!selected && selected.filename === row.filename} onClick={event => { opener.current = event.currentTarget; setSelected(row); }}><SMIcon name="chevron-right" /></ControlButton> }
  ].map(column => ({ ...column, sortable: false, filterable: false }));
  return <section className="sm-section"><div className="sm-section-head"><h3>{kind === 'backups' ? '备份与维护记录' : '运行日志与操作记录'}</h3>
    <span className="sm-meta">{data.files_truncated ? '仅列最近20个文件' : '已读取文件信息'}</span></div>
    <div className="sm-toolbar"><SMFilters kind={kind} filters={{ query: '', type: '', status: '', level: '', file: '', start: '', end: '' }} onChange={() => {}} disabled={true} />
      <div className="sm-actions sm-record-actions">{(kind === 'backups' ? ['新增备份', '恢复备份', '删除备份'] : ['导出日志 CSV', '正式诊断包']).map(label =>
        <SMDisabled key={label} label={label} reason={window.WorkbenchTerms.outcomes.unavailable} />)}</div></div>
    <p className="sm-note">{data.message}{kind === 'logs' && data.operation_record_count != null ? ' 当前共有 ' + data.operation_record_count + ' 条操作记录。' : ''}</p>
    {data.error && <p role="alert" className="sm-error">{data.error.message}</p>}
    {entries.length ? <DataTable className="sm-table sm-record-table" columns={columns} rows={rows} rowKey="filename" /> : <window.WorkbenchListControls.EmptyState kind={data.state === 'empty' ? 'empty' : 'error'} title={data.state === 'empty' ? '暂无文件' : '文件信息不可用'} hint={data.message} action={data.state !== 'empty' ? <a href="/workbench?view=system">重新进入系统管理</a> : undefined} />}
    <div className="sm-pager"><span className="sm-meta">已读取 {entries.length} 个文件{data.count != null ? ' · 文件夹共 ' + data.count + ' 个' : ' · 总数尚不能确认'}</span>
      <window.WorkbenchListControls.Pager page={current} pages={pages} total={entries.length} size={pageSize} sizes={[10, 25, 50]} unit="条" label="" onPage={setPage} onSize={size => { onPageSize(size); setPage(1); }} /></div>
    {selected && <section className="sm-detail" id="system-live-file-detail" ref={detail} tabIndex="-1" aria-label="本机文件信息" onKeyDown={event => { if (event.key === 'Escape') close(); }}><div className="sm-section-head"><h3 style={{overflowWrap:'anywhere',minWidth:0}}>{selected.filename}</h3><ControlButton size="sm" aria-label="关闭文件信息" onClick={close}><SMIcon name="x" /></ControlButton></div>
      <p>修改时间 {window.WorkbenchFormat.dateTime(selected.modified_at)} · {selected.size_bytes} 字节</p><p>仅查看文件信息，尚未读取或校验文件内容。</p></section>}
  </section>;
}

function SystemLiveConfig({ data }) {
  const model = window.APSSystemWorkbench;
  return <div className="sm-configuration"><section className="sm-section sm-maintenance-config"><div className="sm-section-head"><h3>本机自动维护配置</h3>
    <SMDisabled label="保存正式配置" reason={window.WorkbenchTerms.outcomes.unavailable} /></div><p className="sm-note">{data.message}</p>
    {data.error && <p className="sm-error" role="alert">{data.error.message}</p>}
    {!data.values ? <SMUnavailable title="配置未能读取">没有使用管理样例代替本机配置。</SMUnavailable> : <div className="sm-config-form"><div className="sm-config-groups">
      {[['backup', '备份规则'], ['logs', '操作日志规则']].map(([group, label]) => <fieldset className="sm-config-group" key={group}><legend>{label}</legend>
        {model.CONFIG_FIELDS.filter(field => field.group === group).map(field => <div className="sm-config-row" key={field.key}>
          <label htmlFor={'live-' + field.key}>{field.label}</label><div>{field.kind === 'switch' ? <label className="sm-draft-checkbox"><input id={'live-' + field.key} type="checkbox" checked={data.values[field.key] === 'yes'} disabled /><span>{data.values[field.key] === 'yes' ? '启用' : '关闭'}</span></label> :
            <div className="sm-number"><input id={'live-' + field.key} type="number" value={data.values[field.key]} readOnly /><span>{field.unit}</span></div>}
          {data.dirty_fields.includes(field.key) ? <small className="sm-error">{data.dirty_reasons[field.key]}</small> : data.defaulted_fields.includes(field.key) ? <small className="sm-meta">默认值，尚未保存</small> : <small className="sm-meta">已存配置</small>}</div>
        </div>)}</fieldset>)}
    </div></div>}
    <details className="sm-rules"><summary>生效范围与自动维护规则</summary><p>打开页面时系统才会检查一次自动维护，不保证在指定时刻执行。看概况不会触发备份或清理。</p></details>
  </section></div>;
}
