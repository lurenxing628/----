// Current sample presenters use the shared controls; sample records remain read-only.
function SMDisabled({ label, reason }) {
  return <span className="sm-disabled"><window.ResourceControls.Button icon={label.includes('删除') ? 'trash-2' : undefined}
    className="btn sm-button" reason={reason} reasonDisplay="tooltip" aria-label={label + '：' + reason}>{label}</window.ResourceControls.Button></span>;
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
    { key: 'time', title: '时间', render: row => <time className="sm-time">{row.time}</time> },
    { key: 'type', title: '类型', render: row => model.TYPES[row.type] },
    { key: 'status', title: '状态', render: row => <SMStatus state={row.status} /> },
    ...(kind === 'logs' ? [{ key: 'level', title: '级别', render: row => <span className={'sm-level sm-level-' + row.level}>{model.LEVELS[row.level] || row.level}</span> }] : []),
    { key: 'summary', title: kind === 'logs' ? '摘要 / 来源' : '记录 / 文件', render: row => <div className="sm-summary"><strong>{row.summary}</strong><small>{kind === 'logs' ? model.SOURCES[row.file] || row.file : row.filename || '未生成文件'}</small></div> },
    ...(kind === 'backups' ? [{ key: 'sizeBytes', title: '大小', align: 'right', render: row => row.sizeBytes === null ? '不适用' : (row.sizeBytes / 1024 / 1024).toFixed(1) + ' MB' }] : []),
    { key: 'detail', title: '详情', render: row => <ControlButton className="sm-button sm-icon-button sm-quiet-button" size="sm" title="查看详情" aria-label={'查看详情 ' + row.id} data-sm-detail={row.id} aria-controls="sm-record-detail" aria-expanded={!!selected && selected.id === row.id} onClick={e => { opener.current = e.currentTarget; setSelected(row); }}><SMIcon name="chevron-right" /></ControlButton> }
  ].map(column => ({ ...column, sortable: false, filterable: false }));
  return <section className="sm-section">
    <div className="sm-section-head"><h3>{kind === 'logs' ? '运行日志与操作记录' : '备份与维护记录'}</h3><span className="sm-meta">{connected ? '固定样例截至 ' + model.SAMPLE_DATE + ' 18:00' : '本机记录尚未读取'}</span></div>
    <div className="sm-toolbar"><SMFilters kind={kind} filters={filters} onChange={changeFilters} disabled={!connected} />
      <div className="sm-actions sm-record-actions">{kind === 'logs' ? <><SMExport disabled={!connected || !downloadReady || !!results.error || !results.rows.length} onClick={() => exportLogs(filters, results.rows.length)}>导出样例日志 CSV</SMExport>
        <SMDisabled label="正式诊断包" reason="此功能尚未开通。当前只能导出上面的样例日志 CSV。" /></> : <>
        <SMDisabled label="新增备份" reason="此功能尚未开通。当前只显示样例记录。" /><SMDisabled label="恢复备份" reason="此功能尚未开通。当前只显示样例记录。" /><SMDisabled label="删除备份" reason="此功能尚未开通。当前只显示样例记录。" /></>}</div>
    </div>
    <p className="sm-note">{kind === 'logs' ? '运行文件日志只读；操作记录单独归类。' : connected ? '含待执行、受阻情境，不等同于已有备份文件清单。' : '文件清单与完整性校验结果尚未读取。'}</p>
    {results.error && <p className="sm-error" role="alert">{results.error}</p>}
    {!connected ? <SMUnavailable title={kind === 'logs' ? '本机日志尚未读取' : '本机备份记录尚未读取'}>本原型不读取本机记录，所以总数未知。现在无法判断是没有记录，还是读取失败。</SMUnavailable> : results.rows.length === 0 ?
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
    catch (_) { setThemeError('主题没有切换成功，页面其他内容没有改动。请刷新页面后重试。'); }
  };
  return <div className="sm-configuration">
    <section className="sm-section sm-preferences">
      <div className="sm-section-head"><h3>即时页面偏好</h3><span className="sm-meta">主题沿用工作台；列表设置只在当前页面有效</span></div>
      <div className="sm-session-settings"><fieldset className="sm-choice"><legend>主题</legend>{[['light', '浅色'], ['dark', '深色']].map(([value, label]) => <label key={value}><input type="radio" name="sm-theme" value={value} checked={theme === value} disabled={!themeReady} onChange={() => changeTheme(value)} />{label}</label>)}</fieldset>
        <label className="sm-inline-label">每页条数<select name="sm-config-page-size" value={pageSize} onChange={e => onPageSize(Number(e.target.value))}>{[10, 25, 50].map(n => <option key={n} value={n}>{n} 条</option>)}</select></label>
        <label className="sm-inline-label"><input type="checkbox" name="sm-compact" checked={compact} onChange={e => onCompact(e.target.checked)} />紧凑行距</label></div>
      {!themeReady && <p className="sm-note">本页暂时不能切换主题，请到工作台切换深色或浅色。</p>}
      {themeError && <p className="sm-error" role="alert">{themeError}</p>}
    </section>
    <section className="sm-section sm-maintenance-config">
      <div className="sm-section-head"><h3>{source === 'sample' ? '样例草稿 · 自动维护参数' : '本机自动维护配置'}</h3><SMDisabled label="保存正式配置" reason="此功能尚未开通。当前只能检查样例草稿。" /></div>
      <div className="sm-config-main">{source !== 'sample' ? <SMUnavailable title="本机正式配置尚未读取">自动备份开关、检查间隔、保留时间及旧配置异常均未知。</SMUnavailable> :
        <form className="sm-config-form" noValidate onSubmit={event => { event.preventDefault(); setValidated(true); setPreview(validation.valid ? validation.value : null); }}>
          <div className="sm-config-groups">{[['backup', '备份规则'], ['logs', '操作日志规则']].map(([group, label]) => <fieldset className="sm-config-group" key={group}><legend>{label}</legend>
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
          {validated && !validation.valid && <p className="sm-error" role="alert">样例配置检查未通过，填写内容已保留。请修正标出的项。</p>}
          {preview && <div className="sm-preview" role="status"><h4 className="sm-tone-success">样例草稿检查通过 · 未保存</h4><dl>{model.CONFIG_FIELDS.map(field => <React.Fragment key={field.key}><dt>{field.label}</dt><dd>{field.kind === 'switch' ? preview[field.key] === 'yes' ? '启用' : '关闭' : preview[field.key] + ' ' + field.unit}</dd></React.Fragment>)}</dl></div>}
        </form>}</div><details className="sm-rules sm-config-help"><summary>生效范围与自动维护规则</summary><dl><div><dt>当前编辑</dt><dd>{source === 'sample' ? '独立管理样例' : '本机正式配置未读取'}</dd></div><div><dt>触发方式</dt><dd>打开页面时检查一次</dd></div><div><dt>日志清理范围</dt><dd>操作记录，不含运行文件日志</dd></div></dl><p>打开页面时系统才会检查一次备份和清理，没有后台定时任务。间隔只是检查周期，不保证在指定时刻执行；正常退出时的备份也受自动备份开关控制。</p><p>日志清理只清操作记录，不清除运行文件日志。备份失败时会跳过本轮备份清理，保底规则不会删掉全部近期副本。</p></details>
    </section>
  </div>;
}
