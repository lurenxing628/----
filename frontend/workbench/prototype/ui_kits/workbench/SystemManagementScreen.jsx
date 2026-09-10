// Host contract: theme + onToggleTheme (or onSetTheme). No backend adapter or production actions.
// Local Lucide 1.8.0 nodes; license: assets/lucide-LICENSE. No runtime package dependency.
const SM_TOOL_ICONS = {
  'refresh-cw': [['path', { d: 'M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8' }], ['path', { d: 'M21 3v5h-5' }], ['path', { d: 'M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16' }], ['path', { d: 'M8 16H3v5' }]],
  'rotate-ccw': [['path', { d: 'M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8' }], ['path', { d: 'M3 3v5h5' }]]
};
function SMIcon({ name }) {
  const nodes = SM_TOOL_ICONS[name] || (window.APSFieldReports && window.APSFieldReports.iconNodes && window.APSFieldReports.iconNodes[name]);
  if (!nodes) return null;
  return <svg className="sm-icon" data-sm-icon={name} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {nodes.map(([tag, attrs], index) => React.createElement(tag, { ...attrs, key: index }))}
  </svg>;
}
function SMStatus({ state }) {
  const [label, tone] = window.APSSystemWorkbench.STATES[state] || ['未知', 'neutral'];
  return <span className={'sm-status sm-tone-' + tone} data-state={state}>{label}</span>;
}
function SMUnavailable({ title, children }) {
  return <div className="sm-empty"><SMIcon name="folder-open" /><h4>{title}</h4><p>{children}</p></div>;
}
function SMDisabled({ label, reason }) {
  const { ControlButton } = window.APSWorkbenchUI;
  return <span className="sm-disabled" title={reason}><ControlButton className="sm-button" size="sm" disabled aria-label={label + '：' + reason}>{label}</ControlButton></span>;
}
function SMExport({ disabled, onClick, children }) {
  const { TransferButton, ControlButton } = window.APSWorkbenchUI;
  const ready = window.APSFieldReports && window.APSFieldReports.iconNodes && window.APSFieldReports.iconNodes['file-output'];
  return ready ? <TransferButton className="sm-button" kind="export" disabled={disabled} onClick={onClick}>{children}</TransferButton> :
    <ControlButton className="sm-button" disabled title="本地导出图标资源缺失">{children}</ControlButton>;
}
function SMOverview({ report, source, onTab }) {
  const { DataTable } = window.APSWorkbenchUI;
  const items = [
    { tab: 'backups', icon: 'folder-open', title: '备份与恢复', action: '查看备份恢复',
      status: source === 'sample' ? '自动备份失败，清理已跳过' : '备份状态未知',
      description: source === 'sample' ? '写入失败未生成副本；旧备份未清理。' : '备份清单、文件大小与最近执行结果尚未读取。' },
    { tab: 'logs', icon: 'history', title: '运行日志', action: '查看运行日志',
      status: source === 'sample' ? '恢复校验失败，需要保留故障证据' : '运行日志未读取',
      description: source === 'sample' ? '部分记录回滚成功，另有回滚失败记录待排查。' : '运行文件日志与操作记录分开查询。' },
    { tab: 'config', icon: 'square-pen', title: '自动维护策略', action: '查看配置',
      description: source === 'sample' ? '样例：备份间隔 60 分钟，保留 30 天；操作日志清理关闭。' : '自动备份与清理开关、检查间隔、保留天数未知。' }
  ];
  const columns = [{ key: 'label', title: '检查项' }, { key: 'status', title: '结果', render: row => <SMStatus state={row.status} /> }, { key: 'detail', title: '检查范围' }]
    .map(column => ({ ...column, sortable: false, filterable: false }));
  return <div className="sm-overview-layout">
    <section className="sm-section sm-maintenance">
      <div className="sm-section-head"><h3>{source === 'sample' ? '管理样例 · 待处理事项' : '本机维护事项'}</h3><span className="sm-meta">备份、日志与维护策略</span></div>
      {items.map(item => <button key={item.tab} type="button" className="sm-work-row" data-sm-destination={item.tab}
        title={item.action} aria-label={item.action} aria-describedby={'sm-work-summary-' + item.tab} onClick={() => onTab(item.tab)}>
        <span className="sm-work-icon"><SMIcon name={item.icon} /></span>
        <span className="sm-work-copy"><span className="sm-work-title">{item.title}</span>
          <span className="sm-work-summary" id={'sm-work-summary-' + item.tab}>
            {item.status && <strong className={source === 'sample' ? 'sm-tone-danger' : 'sm-meta'}>{item.status}</strong>}
            <span className="sm-work-description">{item.description}</span>
          </span>
        </span>
        <span className="sm-work-arrow" aria-hidden="true"><SMIcon name="chevron-right" /></span>
      </button>)}
    </section>
    <section className="sm-section sm-environment">
      <div className="sm-section-head"><div><h3>页面环境自检</h3><p className="sm-meta">{report ? '检查时间 ' + new Date(report.checkedAt).toLocaleString('zh-CN', { hour12: false }) : '尚未检查'} · 不代表数据库或备份健康</p></div></div>
      <DataTable className="sm-table sm-check-table" columns={columns} rows={report ? report.checks : []} rowKey="id" />
    </section>
  </div>;
}
function SMFilters({ kind, filters, onChange, disabled }) {
  const model = window.APSSystemWorkbench;
  const { ControlButton } = window.APSWorkbenchUI;
  const select = (key, label, entries) => <label className="sm-field" key={key}><span>{label}</span><select name={'sm-' + key} value={filters[key]} disabled={disabled} onChange={e => onChange({ [key]: e.target.value })}>
    <option value="">全部{label}</option>{entries.map(([value, title]) => <option key={value} value={value}>{title}</option>)}
  </select></label>;
  return <div className="sm-filters">
    <label className="sm-field sm-search"><span>搜索</span><span className="sm-search-input"><SMIcon name="search" /><input name="sm-query" type="search" value={filters.query} disabled={disabled} placeholder={kind === 'logs' ? '摘要、完整详情、文件' : '文件名、故障原因'} onChange={e => onChange({ query: e.target.value })} /></span></label>
    {select('type', '类型', (kind === 'logs' ? ['runtime', 'operation'] : ['manual', 'auto', 'before_restore', 'restore', 'cleanup']).map(key => [key, model.TYPES[key]]))}
    {select('status', '状态', ['failed', 'blocked', 'pending', 'skipped', 'verified', 'unverified', 'recorded'].map(key => [key, model.STATES[key][0]]))}
    {kind === 'logs' && select('level', '级别', ['ERROR', 'WARNING', 'INFO'].map(key => [key, key]))}
    {kind === 'logs' && select('file', '记录集', ['aps_error.log', 'aps.log', 'launcher.log', 'OperationLogs'].map(key => [key, key]))}
    <label className="sm-field"><span>开始日期</span><input type="date" data-aps-skip="true" name="sm-start" value={filters.start} disabled={disabled} onChange={e => onChange({ start: e.target.value })} /></label>
    <label className="sm-field"><span>结束日期</span><input type="date" data-aps-skip="true" name="sm-end" value={filters.end} disabled={disabled} onChange={e => onChange({ end: e.target.value })} /></label>
    <ControlButton className="sm-button sm-icon-button" size="sm" disabled={disabled} title="清除筛选" aria-label="清除筛选" onClick={() => onChange({ query: '', status: '', type: '', level: '', file: '', start: '', end: '' })}><SMIcon name="x" /></ControlButton>
  </div>;
}
function SMPager({ pager, onPage, pageSize, onPageSize }) {
  const { ControlButton } = window.APSWorkbenchUI;
  return <div className="sm-pager">
    <span className="sm-meta">{pager.total === null ? '总数未知 · 未连接' : '第 ' + pager.start + '–' + pager.end + ' 条 / 共 ' + pager.total + ' 条管理样例'}</span>
    <div className="sm-actions"><label className="sm-inline-label">每页<select name="sm-page-size" value={pageSize} onChange={e => onPageSize(Number(e.target.value))}>{[10, 25, 50].map(n => <option key={n} value={n}>{n} 条</option>)}</select></label>
      <ControlButton className="sm-button sm-icon-button" size="sm" title="上一页" aria-label="上一页" disabled={pager.total === null || pager.page <= 1} onClick={() => onPage(pager.page - 1)}><SMIcon name="chevron-left" /></ControlButton>
      <span className="sm-page-number">{pager.total === null ? '未知' : pager.page + ' / ' + pager.pages}</span>
      <ControlButton className="sm-button sm-icon-button" size="sm" title="下一页" aria-label="下一页" disabled={pager.total === null || pager.page >= pager.pages} onClick={() => onPage(pager.page + 1)}><SMIcon name="chevron-right" /></ControlButton>
    </div>
  </div>;
}
function SMRecordDetail({ row, onClose, kind }) {
  const { ControlButton } = window.APSWorkbenchUI;
  const ref = React.useRef(null);
  React.useEffect(() => { if (ref.current) ref.current.focus(); }, [row.id]);
  return <section id="sm-record-detail" className="sm-detail" tabIndex="-1" ref={ref} aria-label="管理样例详情" onKeyDown={event => { if (event.key === 'Escape') onClose(); }}>
    <div className="sm-section-head"><h3>管理样例 · {kind === 'logs' ? '日志详情' : '备份恢复详情'}</h3><ControlButton className="sm-button sm-icon-button" size="sm" title="关闭详情" aria-label="关闭详情" onClick={onClose}><SMIcon name="x" /></ControlButton></div>
    <div className="sm-detail-meta"><time>{row.time}</time><SMStatus state={row.status} /><span>{row.file || row.filename || '未生成文件'}</span></div>
    <h4>{row.summary}</h4><pre>{row.body}</pre>
    {kind === 'backups' && <details className="sm-rules"><summary>恢复校验要求</summary><p>目标备份、维护窗口、恢复前副本、恢复后结构校验与结果留痕均未接入。恢复和回滚失败必须分别记录。</p></details>}
  </section>;
}
function SMRecords({ kind, source, pageSize, onPageSize, exportLogs, downloadReady }) {
  const model = window.APSSystemWorkbench, { DataTable, ControlButton } = window.APSWorkbenchUI;
  const [filters, setFilters] = React.useState({ query: '', type: '', status: '', level: '', file: '', start: '', end: '' });
  const [page, setPage] = React.useState(1), [selected, setSelected] = React.useState(null);
  const opener = React.useRef(null);
  const results = React.useMemo(() => model.filterRows(model.dataset(source)[kind], filters), [source, kind, filters]);
  const pager = model.paginate(results.rows, page, pageSize), connected = source === 'sample';
  const changeFilters = patch => { setFilters(previous => ({ ...previous, ...patch })); setPage(1); setSelected(null); };
  const closeDetail = () => { setSelected(null); if (opener.current && opener.current.isConnected) opener.current.focus(); };
  const columns = [
    { key: 'time', title: '时间（样例北京时间）', render: row => <time className="sm-time">{row.time}</time> },
    { key: 'type', title: '类型', render: row => model.TYPES[row.type] },
    { key: 'status', title: '状态', render: row => <SMStatus state={row.status} /> },
    ...(kind === 'logs' ? [{ key: 'level', title: '级别', render: row => <span className={'sm-level sm-level-' + row.level}>{row.level}</span> }] : []),
    { key: 'summary', title: kind === 'logs' ? '摘要 / 记录集' : '记录 / 文件', render: row => <div className="sm-summary"><strong>{row.summary}</strong><small>{kind === 'logs' ? row.file : row.filename || '未生成文件'}</small></div> },
    ...(kind === 'backups' ? [{ key: 'sizeBytes', title: '大小', align: 'right', render: row => row.sizeBytes === null ? '不适用' : (row.sizeBytes / 1024 / 1024).toFixed(1) + ' MB' }] : []),
    { key: 'detail', title: '详情', render: row => <ControlButton className="sm-button sm-icon-button sm-quiet-button" size="sm" title="查看详情" aria-label={'查看详情 ' + row.id} data-sm-detail={row.id} aria-controls="sm-record-detail" aria-expanded={!!selected && selected.id === row.id} onClick={e => { opener.current = e.currentTarget; setSelected(row); }}><SMIcon name="chevron-right" /></ControlButton> }
  ].map(column => ({ ...column, sortable: false, filterable: false }));
  return <section className="sm-section">
    <div className="sm-section-head"><h3>{kind === 'logs' ? '运行日志与操作记录' : '备份与恢复记录'}</h3><span className="sm-meta">{connected ? '固定样例截至 ' + model.SAMPLE_DATE + ' 18:00' : '本机记录尚未读取'}</span></div>
    <div className="sm-toolbar"><SMFilters kind={kind} filters={filters} onChange={changeFilters} disabled={!connected} />
      <div className="sm-actions sm-record-actions">{kind === 'logs' ? <><SMExport disabled={!connected || !downloadReady || !!results.error || !results.rows.length} onClick={() => exportLogs(filters, results.rows.length)}>导出样例日志 CSV</SMExport>
        <SMDisabled label="正式诊断包" reason="未接入本机日志读取与 ZIP 构包；本地诊断 JSON 不含正式日志" /></> : <>
        <SMDisabled label="立即备份" reason="未接入本机备份执行、数据库与备份目录" /><SMDisabled label="恢复备份" reason="未接入目标文件、维护窗口与恢复后校验" /><SMDisabled label="删除备份" reason="未读取真实文件清单，未接入删除执行与结果留痕" /></>}</div>
    </div>
    <p className="sm-note">{kind === 'logs' ? '运行文件日志只读；操作记录单独归类。' : connected ? '含待执行、受阻情境，不等同于已有备份文件清单。' : '文件清单与完整性校验结果尚未读取。'}</p>
    {results.error && <p className="sm-error" role="alert">{results.error}</p>}
    {!connected ? <SMUnavailable title={kind === 'logs' ? '本机日志尚未读取' : '本机备份记录尚未读取'}>本原型尚未接入本机记录。总数未知，不能判断记录为空或读取失败。</SMUnavailable> : results.rows.length === 0 ?
      <SMUnavailable title={results.error ? '筛选条件无效' : '没有符合条件的管理样例'}>{results.error || '调整日期或清除筛选条件。'}</SMUnavailable> :
      <DataTable className={'sm-table sm-record-table sm-' + kind + '-table'} columns={columns} rows={pager.rows} rowKey="id" />}
    <SMPager pager={pager} pageSize={pageSize} onPage={next => { setPage(next); setSelected(null); }} onPageSize={size => { onPageSize(size); setPage(1); setSelected(null); }} />
    {selected && <SMRecordDetail row={selected} onClose={closeDetail} kind={kind} />}
  </section>;
}
function SMConfiguration({ source, theme, onToggleTheme, onSetTheme, pageSize, onPageSize, compact, onCompact }) {
  const model = window.APSSystemWorkbench, { ControlButton } = window.APSWorkbenchUI;
  const [draft, setDraft] = React.useState(() => ({ ...model.SAMPLE_CONFIG }));
  const [preview, setPreview] = React.useState(null), [validated, setValidated] = React.useState(false);
  const [themeError, setThemeError] = React.useState('');
  const validation = model.validateConfig(draft);
  const themeReady = ['light', 'dark'].includes(theme) && (typeof onSetTheme === 'function' || typeof onToggleTheme === 'function');
  const changeTheme = next => {
    if (next === theme || !themeReady) return;
    setThemeError('');
    try { if (typeof onSetTheme === 'function') onSetTheme(next); else onToggleTheme(); }
    catch (_) { setThemeError('主题切换未完成，请检查宿主主题回调。'); }
  };
  return <div className="sm-configuration">
    <section className="sm-section sm-preferences">
      <div className="sm-section-head"><h3>即时页面偏好</h3><span className="sm-meta">主题沿用工作台；列表设置仅当前页面会话</span></div>
      <div className="sm-session-settings"><fieldset className="sm-choice"><legend>主题</legend>{[['light', '浅色'], ['dark', '深色']].map(([value, label]) => <label key={value}><input type="radio" name="sm-theme" value={value} checked={theme === value} disabled={!themeReady} onChange={() => changeTheme(value)} />{label}</label>)}</fieldset>
        <label className="sm-inline-label">每页条数<select name="sm-config-page-size" value={pageSize} onChange={e => onPageSize(Number(e.target.value))}>{[10, 25, 50].map(n => <option key={n} value={n}>{n} 条</option>)}</select></label>
        <label className="sm-inline-label"><input type="checkbox" name="sm-compact" checked={compact} onChange={e => onCompact(e.target.checked)} />紧凑行距</label></div>
      {!themeReady && <p className="sm-note">主题不可用：宿主需要传入 theme 与 onToggleTheme 或 onSetTheme。</p>}
      {themeError && <p className="sm-error" role="alert">{themeError}</p>}
    </section>
    <section className="sm-section sm-maintenance-config">
      <div className="sm-section-head"><h3>{source === 'sample' ? '样例草稿 · 自动维护参数' : '本机自动维护配置'}</h3><SMDisabled label="保存正式配置" reason="未读取本机正式配置快照，也未接入配置保存与校验结果" /></div>
      <div className="sm-config-main">{source !== 'sample' ? <SMUnavailable title="本机正式配置尚未读取">自动备份开关、检查间隔、保留时间及旧配置异常均未知。</SMUnavailable> :
        <form className="sm-config-form" noValidate onSubmit={event => { event.preventDefault(); setValidated(true); setPreview(validation.valid ? validation.value : null); }}>
          <div className="sm-config-groups">{[['backup', '备份策略'], ['logs', '操作日志策略']].map(([group, label]) => <fieldset className="sm-config-group" key={group}><legend>{label}</legend>
            {model.CONFIG_FIELDS.filter(field => field.group === group).map(field => <div className="sm-config-row" key={field.key}>
              <label htmlFor={'sm-' + field.key}>{field.label}</label><div>
                {field.kind === 'switch' ? <label className="sm-draft-checkbox"><input id={'sm-' + field.key} name={field.key} type="checkbox" checked={draft[field.key] === 'yes'} onChange={e => { setDraft({ ...draft, [field.key]: e.target.checked ? 'yes' : 'no' }); setPreview(null); }} /><span>{draft[field.key] === 'yes' ? '启用' : '关闭'}</span></label> :
                  <div className="sm-number"><input id={'sm-' + field.key} name={field.key} type="number" step="1" min={field.min} max={field.max} value={draft[field.key]} aria-invalid={validated && !!validation.errors[field.key]} aria-describedby={'sm-help-' + field.key} onChange={e => { setDraft({ ...draft, [field.key]: e.target.value }); setPreview(null); }} /><span>{field.unit}</span></div>}
                {field.kind !== 'switch' && <small id={'sm-help-' + field.key} className={validated && validation.errors[field.key] ? 'sm-error' : 'sm-meta'}>{validated && validation.errors[field.key] || field.min + '–' + field.max + ' ' + field.unit}</small>}
              </div></div>)}
          </fieldset>)}</div>
          <div className="sm-form-footer"><span className="sm-meta">样例草稿 · 未保存</span><div className="sm-actions">
            <ControlButton className="sm-button" size="sm" onClick={() => { setDraft({ ...model.SAMPLE_CONFIG }); setValidated(false); setPreview(null); }}><SMIcon name="rotate-ccw" />还原样例</ControlButton>
            <ControlButton className="sm-button sm-primary-button" variant="primary" size="sm" type="submit"><SMIcon name="check" />检查参数</ControlButton></div></div>
          {validated && !validation.valid && <p className="sm-error" role="alert">样例配置校验未通过，请修正标出的字段。</p>}
          {preview && <div className="sm-preview" role="status"><h4 className="sm-tone-success">样例草稿检查通过 · 未保存</h4><dl>{model.CONFIG_FIELDS.map(field => <React.Fragment key={field.key}><dt>{field.label}</dt><dd>{field.kind === 'switch' ? preview[field.key] === 'yes' ? '启用' : '关闭' : preview[field.key] + ' ' + field.unit}</dd></React.Fragment>)}</dl></div>}
        </form>}</div><details className="sm-rules sm-config-help"><summary>生效范围与自动维护规则</summary><dl><div><dt>当前编辑</dt><dd>{source === 'sample' ? '独立管理样例' : '本机正式配置未读取'}</dd></div><div><dt>触发方式</dt><dd>由访问请求触发检查</dd></div><div><dt>日志清理对象</dt><dd>操作记录，不含运行文件日志</dd></div></dl><p>备份与清理由访问请求触发，不是后台定时任务。间隔为检查周期，不保证指定时刻执行；正常退出时的备份也受自动备份开关控制。</p><p>日志清理只针对操作记录，不清空运行文件日志。备份失败时跳过本轮备份清理，保留策略不能删除全部近期副本。</p></details>
    </section>
  </div>;
}
function SMWorkbench({ theme, onToggleTheme, onSetTheme }) {
  const model = window.APSSystemWorkbench, { MetricStrip, Metric, ControlButton } = window.APSWorkbenchUI;
  const [source, setSource] = React.useState('current'), [tab, setTab] = React.useState('overview');
  const [report, setReport] = React.useState(null), [notice, setNotice] = React.useState(null);
  const [pageSize, setPageSize] = React.useState(10), [compact, setCompact] = React.useState(true);
  const tabs = [['overview', '概况'], ['backups', '备份恢复'], ['logs', '运行日志'], ['config', '配置']];
  const recheck = () => { const result = model.inspectEnvironment(window, { theme, onToggleTheme, onSetTheme }); setReport(result); return result; };
  React.useEffect(() => { recheck(); }, [theme, onToggleTheme, onSetTheme]);
  const exportFile = (name, mime, content, message) => {
    try { model.download(window, name, mime, content); setNotice({ tone: 'notice', text: message + '，已交给浏览器下载；是否保存以浏览器结果为准。' }); }
    catch (_) { setNotice({ tone: 'danger', text: '本地导出失败。请检查浏览器下载能力；没有生成正式诊断包或修改系统数据。' }); }
  };
  const onTab = next => { setTab(next); setNotice(null); document.getElementById('sm-tab-' + next).focus(); };
  const exportLogs = (filters, count) => exportFile('aps-management-sample-logs.csv', 'text/csv;charset=utf-8', model.sampleLogCSV(filters), '已生成 ' + count + ' 条筛选后的管理样例日志 CSV（含所有分页）');
  const localReady = report ? report.checks.filter(item => item.status === 'available').length : null;
  const downloadReady = report && report.checks.some(item => item.id === 'download' && item.status === 'available');
  return <div className={'sm-workbench' + (compact ? ' sm-compact' : '')} data-source={source}>
    <header className="sm-header"><div><h2>系统管理</h2><p>本机备份恢复、日志与自动维护</p></div>
      <div className="sm-actions"><ControlButton className="sm-button sm-icon-button" size="sm" title="重新检查" aria-label="重新检查" onClick={() => { recheck(); setNotice({ tone: 'notice', text: '已重新检查当前页面依赖，未请求生产接口。' }); }}><SMIcon name="refresh-cw" /></ControlButton>
        <SMExport disabled={!downloadReady} onClick={() => { const current = recheck(); exportFile('aps-current-prototype-diagnostic.json', 'application/json;charset=utf-8', model.diagnosticJSON(current), '已生成当前原型诊断 JSON（不含样例与正式日志）'); }}>导出当前诊断 JSON</SMExport></div>
    </header>
    <div className="sm-source-bar"><fieldset className="sm-choice"><legend>数据来源</legend>{[['current', '当前原型'], ['sample', '管理样例']].map(([value, label]) => <label key={value}><input type="radio" name="sm-source" value={value} checked={source === value} onChange={() => { setSource(value); setNotice(null); }} />{label}</label>)}</fieldset>
      <span className="sm-source-note">{source === 'current' ? '本原型尚未读取本机运行数据 · 数据库、备份与日志状态未知' : '独立固定样例 · 2026-09-07 · 非当前机器运行数据'}</span></div>
    <MetricStrip columns={4} className="sm-metrics"><Metric label="当前页面检查" value={localReady === null ? '待检查' : localReady + ' / ' + report.checks.length} helper="仅页面依赖与资源" />
      <Metric label="本机数据接入" value="未连接" helper="未发起本机状态读取" /><Metric label="数据库状态" value="未知" helper="当前原型未接入" /><Metric label="备份健康" value="未知" helper="没有本机校验结果" /></MetricStrip>
    {notice && <div className={'sm-notice sm-tone-' + notice.tone} role={notice.tone === 'danger' ? 'alert' : 'status'}>{notice.text}</div>}
    <div className="sm-tabs" role="tablist" aria-label="系统管理页签">{tabs.map(([key, label], index) => <button type="button" className={'sm-tab' + (tab === key ? ' sm-active' : '')} key={key} id={'sm-tab-' + key} role="tab" aria-selected={tab === key} aria-controls={'sm-panel-' + key} tabIndex={tab === key ? 0 : -1} onClick={() => onTab(key)} onKeyDown={event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault(); const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      onTab(tabs[next][0]);
    }}><SMIcon name={{ overview: 'circle-check', backups: 'folder-open', logs: 'history', config: 'square-pen' }[key]} />{label}</button>)}</div>
    <div className="sm-tab-panel" id={'sm-panel-' + tab} role="tabpanel" aria-labelledby={'sm-tab-' + tab}>
      {tab === 'overview' && <SMOverview report={report} source={source} onTab={onTab} />}
      {['backups', 'logs'].includes(tab) && <SMRecords key={tab + source} kind={tab} source={source} pageSize={pageSize} onPageSize={setPageSize} exportLogs={exportLogs} downloadReady={downloadReady} />}
      {tab === 'config' && <SMConfiguration source={source} theme={theme} onToggleTheme={onToggleTheme} onSetTheme={onSetTheme} pageSize={pageSize} onPageSize={setPageSize} compact={compact} onCompact={setCompact} />}
    </div>
  </div>;
}
function SystemManagementScreen(props) {
  const ui = window.APSWorkbenchUI, ds = window.APSDesignSystem_edbc5d;
  if (!window.APSSystemWorkbench || !ui || !ds || !['MetricStrip', 'Metric', 'DataTable', 'TransferButton', 'ControlButton'].every(key => typeof ui[key] === 'function') || typeof ds.Table !== 'function' || typeof ds.Button !== 'function') return <section className="sm-workbench"><h2>系统管理</h2><p role="alert">页面模型或公共工作台组件未加载，系统管理不可用。本原型尚未读取本机运行数据。</p></section>;
  return <SMWorkbench {...props} />;
}
window.SystemManagementScreen = SystemManagementScreen;
