(function () {
  'use strict';
  const A = window.SystemMaintenanceAPI, C = window.SystemMaintenanceControls;
  const emptyFilters = { query: '', type: '', status: '', level: '', file: '', start: '', end: '' };
  const types = { manual: '手动备份', auto: '自动备份', before_restore: '恢复前保护副本', unknown: '类型未知', restore: '恢复', cleanup: '清理', runtime: '运行日志', operation: '操作记录' };
  const states = { unverified: '未校验', unknown: '结果未知', accepted: '已受理', checking: '检查中', protecting: '创建保护副本', restoring: '恢复中',
    verifying: '校验中', rolling_back: '回滚中', succeeded: '已完成', failed: '失败', rolled_back: '已回滚', rollback_failed: '回滚失败', recovery_required: '需人工核查' };
  function Filters({ kind, value, onChange, onSubmit, onReset, loading }) {
    const select = (key, label, choices) => <label className="sm-field" key={key}><span>{label}</span><select aria-label={label} value={value[key]} onChange={event => onChange({ ...value, [key]: event.target.value })}>
      <option value="">全部</option>{choices.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>;
    return <form className="sm-filters" onSubmit={event => { event.preventDefault(); onSubmit(); }}>
      <label className="sm-field sm-search"><span>搜索</span><span className="sm-search-input"><SMIcon name="search" /><input type="search" aria-label="搜索维护记录" maxLength={200} value={value.query}
        onChange={event => onChange({ ...value, query: event.target.value })} placeholder={kind === 'logs' ? '摘要、已读取详情、来源' : '备份文件名'} /></span></label>
      {select('type', '记录类型', Object.entries(types).filter(([key]) => kind === 'logs' ? ['runtime', 'operation'].includes(key) : !['runtime', 'operation'].includes(key)))}
      {select('status', '记录状态', kind === 'logs' ? [['recorded', '已记录']] : Object.entries(states))}
      {kind === 'logs' && <>{select('file', '日志来源', ['aps.log', 'aps_error.log', 'launcher.log', 'OperationLogs'].map(key => [key, key === 'OperationLogs' ? '操作记录' : key]))}
        {select('level', '日志级别', ['INFO', 'WARNING', 'WARN', 'ERROR', 'DEBUG', 'CRITICAL', 'UNKNOWN'].map(key => [key, key]))}</>}
      {['start', 'end'].map(key => <label className="sm-field" key={key}><span>{key === 'start' ? '开始日期' : '结束日期'}</span><input type="date" aria-label={key === 'start' ? '开始日期' : '结束日期'}
        value={value[key]} onChange={event => onChange({ ...value, [key]: event.target.value })} /></label>)}
      <div className="sm-actions" style={{ gridColumn: '1 / -1', justifyContent: 'flex-end' }}>
        <C.Button icon="x" aria-label="清除筛选" onClick={onReset} /><C.Button icon="search" type="submit" busy={loading}>查询</C.Button>
      </div>
    </form>;
  }
  function Sources({ data, kind }) {
    if (kind === 'backups') return data.sources.map((item, index) => <p className="sm-note" key={index}>{item.message} · {item.code}</p>);
    const labels = { available: '可读取', empty: '窗口内暂无记录', missing: '来源不存在', error: '来源读取失败' };
    return <div className="sm-log-sources" aria-label="日志读取窗口" style={{ borderBottom: '1px solid var(--ui-border)', paddingBottom: 12, marginBottom: 12 }}>
      <p className="sm-note">先读取各来源最近窗口，再按条件筛选；不是全历史日志。记录状态不代表业务执行成功。</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 24px' }}>{data.sources.map(item => <div key={item.source} style={{ flex: '1 1 210px', minWidth: 0, overflowWrap: 'anywhere', fontSize: 13 }}>
        <strong>{item.source === 'OperationLogs' ? '操作记录' : item.source}</strong><span className={['error', 'missing'].includes(item.state) ? 'sm-tone-warning' : 'sm-meta'}> · {labels[item.state]}</span>
        <div>最近 {item.window} 条 · {item.count === null ? '数量未知' : '读取 ' + item.count + ' 条'}{item.truncated ? ' · 窗口已截断' : ' · 未报告窗口截断'}</div>
        {item.boundary_unknown && <div className="sm-tone-warning">读取边界未能完整确认</div>}{item.message && <div className="sm-tone-warning">{item.message}</div>}
      </div>)}</div>
    </div>;
  }
  function Detail({ row, kind, data, reason, onAction, onDownload, downloadBusy, onClose }) {
    const ref = React.useRef(null);
    const file = kind === 'backups' && row.record_kind === 'backup_file', event = kind === 'backups' && !file;
    React.useEffect(() => { const previous = document.activeElement; ref.current.focus(); return () => { if (previous && previous.isConnected) previous.focus(); }; }, []);
    return <section className="sm-detail" role="region" aria-label={kind === 'logs' ? '日志详情' : file ? '备份详情' : '维护事件详情'} tabIndex={-1} ref={ref} onKeyDown={event => { if (event.key === 'Escape') onClose(); }}>
      <div className="sm-section-head"><h3 style={{ overflowWrap: 'anywhere', minWidth: 0 }}>{kind === 'logs' ? '日志详情' : file ? row.filename : row.summary}</h3><C.Button icon="x" aria-label="关闭详情" onClick={onClose} /></div>
      <div className="sm-detail-meta"><time>{row.time ? row.time.replace('T', ' ') : '时间未识别'}</time><span>{types[row.type]}</span><span>{kind === 'logs' ? row.file + ' · ' + row.level + ' · 已记录' : file ? '未校验 · ' + row.size_bytes + ' 字节' : states[row.status]}</span></div>
      {event && <p className="sm-note">{{ external_maintenance_journal: '外置维护记录', operation_audit: '操作审计', latest_job_state_only: '仅最近任务状态' }[row.event_source]} · {row.event_ref}</p>}
      <p style={{ overflowWrap: 'anywhere' }}>{row.summary}</p><pre style={{ fontSize: 13 }}>{row.body}</pre>
      {row.content_truncated && <p className="sm-tone-warning">本条详情已截断，不是完整原始内容。</p>}
      {file && <><p className="sm-note">备份文件存在不代表已校验通过或可以恢复。</p><div className="sm-actions">
        <C.Button transfer="export" disabled={!!reason} busy={downloadBusy} onClick={() => onDownload(row)}>下载备份</C.Button>
        <C.Button icon="rotate-ccw" reason={reason || A.blocked(data, 'restore')} onClick={() => onAction('restore', row)}>恢复备份</C.Button>
        <C.Button icon="trash-2" reason={reason || A.blocked(data, 'delete')} onClick={() => onAction('delete', row)}>删除备份</C.Button>
      </div>{A.blocked(data, 'restore') && <p className="sm-note">恢复禁用：{A.blocked(data, 'restore')}</p>}
        {A.blocked(data, 'delete') && <p className="sm-note">删除禁用：{A.blocked(data, 'delete')}</p>}</>}
    </section>;
  }
  function Records({ api, kind, pageSize, onPageSize, revision, command, active = true, initialContext, onReadContext }) {
    const [start] = React.useState(() => A.recordContext(initialContext, kind));
    const [draft, setDraft] = React.useState(start.filters), [filters, setFilters] = React.useState(start.filters);
    const [page, setPage] = React.useState(start.page), [snapshot, setSnapshot] = React.useState(''), [refresh, reload] = React.useReducer(value => value + 1, 0);
    const [selection, setSelection] = React.useState(start.selection), [confirm, setConfirm] = React.useState(null), [downloadBusy, setDownloadBusy] = React.useState(false);
    const [error, setError] = React.useState(null), [notice, setNotice] = React.useState('');
    const request = C.useRead(api, kind, { ...filters, page, page_size: pageSize, snapshot_ref: snapshot }, revision + ':' + refresh, active);
    const payload = request.data, data = payload && payload.data;
    const stableSelection = selection && (kind !== 'backups' || /^[a-f0-9]{64}$/.test(selection.key)
      && ['backup_file', 'restore_event', 'cleanup_event'].includes(selection.record_kind));
    const matches = stableSelection && data ? data.rows.filter(row => row.key === selection.key && (kind !== 'backups'
      || row.record_kind === selection.record_kind && (row.record_kind !== 'backup_file' || !selection.backup_ref || row.backup_ref === selection.backup_ref))) : [];
    const selected = matches.length === 1 ? matches[0] : null;
    function setSelected(row) { setSelection(row ? { key: row.key, ...(kind === 'backups' ? { record_kind: row.record_kind,
      ...(row.record_kind === 'backup_file' ? { backup_ref: row.backup_ref } : {}) } : {}) } : null); }
    React.useEffect(() => {
      if (selected && kind === 'backups' && selected.record_kind === 'backup_file' && !selection.backup_ref) setSelected(selected);
    }, [selected, selection, kind]);
    const previousVersion = React.useRef(revision + ':' + pageSize);
    React.useEffect(() => {
      const next = revision + ':' + pageSize; if (previousVersion.current === next) return;
      previousVersion.current = next; setPage(1); setSnapshot(''); setSelected(null); setConfirm(null);
    }, [revision, pageSize]);
    const savedScope = JSON.stringify(A.recordContext({ filters, page, selection }, kind));
    React.useLayoutEffect(() => {
      if (onReadContext && active && data && !request.loading && !request.error) onReadContext(kind, JSON.parse(savedScope));
    }, [onReadContext, kind, active, !!data, request.loading, request.error, savedScope]);
    React.useEffect(() => { if (!active || command.locked) setConfirm(null); }, [active, command.locked]);
    function apply(value) {
      if (value.start && value.end && value.start > value.end) { setError(new Error('开始日期不能晚于结束日期。')); return; }
      setError(null); setNotice(''); setFilters({ ...value }); setPage(1); setSnapshot(''); setSelected(null); reload();
    }
    function changePage(next) { setPage(next); setSnapshot(payload.meta.snapshot_ref); setSelected(null); setError(null); setNotice(''); }
    async function download(format) {
      setError(null); setNotice(''); setDownloadBusy(true);
      try { const file = await api.download(format, { ...filters, page: 1, page_size: pageSize, snapshot_ref: payload.meta.snapshot_ref }); setNotice('已生成并交给浏览器下载：' + file.filename + '（' + file.bytes + ' 字节）。'); }
      catch (problem) { setError(problem); } finally { setDownloadBusy(false); }
    }
    async function downloadBackup(row) {
      setError(null); setNotice(''); setDownloadBusy(true);
      try {
        const file = await api.downloadBackup(row, { ...filters, page: 1, page_size: pageSize, snapshot_ref: payload.meta.snapshot_ref });
        setNotice('已生成并交给浏览器下载：' + file.filename + '（' + file.bytes + ' 字节）。');
      } catch (problem) { setError(problem); } finally { setDownloadBusy(false); }
    }
    const writeReason = command.locked ? '原维护请求尚未确认，请先核实结果。' : request.loading || !data ? '请先读取有效的备份清单。' : '';
    const ask = (action, row) => {
      if (action !== 'create' && (!row || row.record_kind !== 'backup_file')) { setError(new Error('维护事件不是可操作的备份文件。')); return; }
      setConfirm({ action, row });
    };
    return <section className="sm-section" aria-label={kind === 'logs' ? '运行日志与操作记录' : '备份与恢复记录'}>
      <div className="sm-section-head"><h3>{kind === 'logs' ? '运行日志与操作记录' : '备份与恢复记录'}</h3><C.Button icon="refresh-cw" aria-label="重新读取清单" busy={request.loading} onClick={() => { setPage(1); setSnapshot(''); setSelected(null); reload(); }} /></div>
      <div className="sm-toolbar"><Filters kind={kind} value={draft} onChange={setDraft} onSubmit={() => apply(draft)} loading={request.loading} onReset={() => { setDraft({ ...emptyFilters }); apply(emptyFilters); }} />
        <div className="sm-actions sm-record-actions">{kind === 'backups' ? <C.Button icon="plus" reason={writeReason || A.blocked(data, 'create')} onClick={() => ask('create', null)}>创建备份</C.Button> : <>
          <C.Button transfer="export" disabled={!data || request.loading} busy={downloadBusy} onClick={() => download('csv')}>导出窗口 CSV</C.Button>
          <C.Button transfer="export" disabled={!data || request.loading} busy={downloadBusy} onClick={() => download('zip')}>脱敏诊断 ZIP</C.Button></>}</div>
      </div>
      <C.ErrorBox error={request.error || error} />{notice && <p className="sm-notice" role="status">{notice}</p>}
      {selection && data && !selected && <p className="sm-notice" role="status">{!stableSelection
        ? '原选择缺少可信的稳定记录标识或记录类型，未按旧令牌、同名文件或第一条记录定位。'
        : '原选择记录未通过当前返回页的唯一身份核对，未自动替换为其他记录。'}<C.Button icon="x" onClick={() => setSelected(null)}>清除原选择</C.Button></p>}
      {kind === 'backups' && data && A.blocked(data, 'create') && <p className="sm-note">文件动作禁用：{A.blocked(data, 'create')}</p>}
      {request.loading && <p className="sm-note" role="status">正在读取{kind === 'logs' ? '日志窗口' : '备份清单'}…</p>}
      {data && <><Sources data={data} kind={kind} /><div className="sm-meta">工厂本地时间 · 数据截至 {payload.meta.as_of.replace('T', ' ')}</div>
        {data.rows.length ? <div className="wb-table-shell" style={{ overflowX: 'auto' }}><table className={'wb-table sm-table sm-record-table sm-' + kind + '-table'}>
          <thead><tr><th>工厂本地时间</th><th>类型</th><th>状态</th>{kind === 'logs' && <th>级别</th>}<th>{kind === 'logs' ? '摘要 / 来源' : '文件'}</th>{kind === 'backups' && <th>大小</th>}<th>详情</th></tr></thead>
          <tbody>{data.rows.map(row => <tr key={row.key} data-record-kind={row.record_kind} tabIndex={0} aria-label={'查看详情 ' + row.summary} aria-expanded={!!selected && selected.key === row.key} style={{ cursor: 'pointer' }}
            onClick={() => setSelected(row)} onKeyDown={event => { if (event.target === event.currentTarget && ['Enter', ' '].includes(event.key)) { event.preventDefault(); setSelected(row); } }}>
            <td><time className="sm-time">{row.time ? row.time.replace('T', ' ') : '时间未识别'}</time></td><td>{types[row.type]}</td>
            <td><span className="sm-status sm-tone-neutral">{kind === 'logs' ? '已记录' : states[row.status]}</span></td>{kind === 'logs' && <td><span className={'sm-level sm-level-' + row.level}>{row.level}</span></td>}
            <td><div className="sm-summary"><strong style={{ fontSize: 14 }}>{row.summary}</strong>{kind === 'logs' && <small>{row.file}{row.content_truncated ? ' · 详情已截断' : ''}</small>}</div></td>
            {kind === 'backups' && <td style={{ textAlign: 'right' }}>{row.record_kind === 'backup_file' ? (row.size_bytes / 1024).toFixed(1) + ' KB' : '事件记录'}</td>}
            <td><C.Button icon="chevron-right" className="mini" aria-label={'查看详情 ' + row.summary} onClick={event => { event.stopPropagation(); setSelected(row); }} /></td>
          </tr>)}</tbody></table></div> : <SMUnavailable title="当前筛选下暂无记录">{kind === 'logs' ? '仅限已读取的日志窗口；来源缺失和读取失败另行列出。' : '仅限已读取的备份文件、恢复事件和清理记录。'}</SMUnavailable>}
        <div className="sm-pager"><span className="sm-meta">当前范围共 {data.page.total} 条</span><div className="sm-actions"><label className="sm-inline-label">每页<select aria-label="每页数量" value={pageSize} onChange={event => onPageSize(Number(event.target.value))}>{[10, 25, 50].map(size => <option key={size} value={size}>{size} 条</option>)}</select></label>
          <C.Button icon="chevron-left" aria-label="上一页" disabled={data.page.number <= 1} onClick={() => changePage(page - 1)} /><span className="sm-page-number">{data.page.number} / {data.page.pages}</span>
          <C.Button icon="chevron-right" aria-label="下一页" disabled={data.page.number >= data.page.pages} onClick={() => changePage(page + 1)} /></div></div>
        {selected && <Detail key={selected.key} row={selected} kind={kind} data={data} reason={writeReason} onAction={ask} onDownload={downloadBackup} downloadBusy={downloadBusy} onClose={() => setSelected(null)} />}
      </>}
      {confirm && <C.Confirm {...confirm} reason={writeReason || A.blocked(data, confirm.action)} onClose={() => setConfirm(null)} onConfirm={() => {
        const { action, row } = confirm, reason = writeReason || A.blocked(data, action); if (reason) { setError(new Error(reason)); return; }
        setConfirm(null); command.execute(action, row ? row.write_context.write_token : data.create_context.write_token, row ? { backup_ref: row.backup_ref } : {}, row ? { filename: row.filename } : null);
      }} />}
    </section>;
  }
  window.SystemMaintenanceRecords = Records;
})();
