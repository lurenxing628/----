(function () {
  'use strict';
  const C = window.SystemMaintenanceControls, R = window.SystemRestoreStatus;
  function Styles() {
    return null;
  }
  function Panel({ command, api, theme, onSetTheme }) {
    const { host, intent } = command;
    const original = intent && intent.request_key || host && host.request_key || '';
    const [reference, setReference] = React.useState(original), [kind, setKind] = React.useState('request');
    const [query, setQuery] = React.useState(null), [error, setError] = React.useState(null), [busy, setBusy] = React.useState(false), [notice, setNotice] = React.useState('');
    const screen = React.useRef(null), controller = React.useRef(null);
    React.useEffect(() => { if (!reference && original) setReference(original); }, [original]);
    React.useLayoutEffect(() => {
      const root = document.getElementById('root'), previous = root && root.inert, focus = document.activeElement;
      const savedURL = location.href, savedState = history.state;
      const stay = event => { event.stopImmediatePropagation(); history.replaceState(savedState, '', savedURL); };
      if (root) root.inert = true;
      screen.current.focus(); window.addEventListener('popstate', stay, true);
      return () => { if (root) root.inert = previous; window.removeEventListener('popstate', stay, true);
        if (controller.current) controller.current.abort(); if (focus && focus.isConnected) focus.focus(); };
    }, []);
    const result = query ? query.result : command.result;
    const op = result && result.kind === 'file_operation' ? result.operation : null;
    const description = R.describe(command.hostError ? null : host, op), waiting = busy || command.busy || command.hostBusy;
    const problem = error || command.hostError || command.storageError || command.error;
    async function lookup(event) {
      event.preventDefault(); if (waiting) return;
      setBusy(true); setError(null); setNotice(''); setQuery({ reference, kind, result: null });
      controller.current = new AbortController();
      try { const value = await api.lookupReference(reference.trim(), kind, controller.current.signal); setQuery({ reference: reference.trim(), kind, result: value }); }
      catch (problem) { if (problem.name !== 'AbortError') setError(problem); }
      finally { await command.inspectHost(); setBusy(false); }
    }
    const fields = [
      ['结果来源', '本机数据库外的维护记录，不是当前数据库业务回执'],
      ['该次维护记录的数据库来源', description.origin],
      ['选定备份', op && op.filename || (!query && command.selection ? command.selection.filename + '（页面选择，尚未核实）' : '维护记录尚未确认')],
      ['恢复前保护副本', op && op.protection_filename || '未查到已留存证据，不代表已创建'],
      ['业务审计', op && op.audit_persisted ? '维护记录报告已留存；当前数据库内容仍需重启后读取' : '未确认留存'],
      ['软件状态', command.hostError || !host ? '无法读取维护状态，当前页面已暂停业务读写' : host.restart_required ? '业务操作已停用，须重启整个软件' : '维护状态尚未核实，当前页面已暂停业务读写']
    ];
    return ReactDOM.createPortal(<div className="sm-workbench sm-maintenance-workspace plana sm-restore-screen" data-restore-maintenance="warm" ref={screen} tabIndex={-1}>
      <Styles /><C.Styles />
      <header className="sm-restore-bar"><strong>APS 智能排产 · 系统维护</strong><fieldset className="sm-choice"><legend>主题</legend>{[['light', '浅色'], ['dark', '深色']].map(([value, label]) =>
        <label key={value}><input type="radio" name="restore-theme" checked={theme === value} onChange={() => onSetTheme(value)} />{label}</label>)}</fieldset></header>
      <main className="sm-restore-content"><h1>{command.hostError ? '无法读取维护状态' : description.title}</h1><p className="sm-meta">只读维护状态 · 不读取业务数据库</p>
        <section aria-label="维护结果"><h2 className={op && op.state === 'succeeded' && !description.uncertain ? 'sm-tone-success' : 'sm-tone-warning'}>{description.state}</h2>
          <p className="sm-notice">{description.guidance}</p>
          <C.ErrorBox error={problem} />{waiting && <p role="status">正在核实维护状态，没有重新提交恢复。</p>}
          {notice && <p role="status">{notice}</p>}
          {op && <p>{op.message}</p>}{result && result.kind === 'not_recorded' && <p role="status">{result.message} 查不到不代表没有执行。</p>}
          <dl className="sm-restore-facts">{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
          {original ? <window.WorkbenchReference label="本机保留的原请求" value={original} /> : <p className="sm-meta">未读取到原请求，可在下方输入原请求标识。</p>}
          {op && (!host || host.request_key !== op.request_key) && <p className="sm-note">这条记录不能代表当前数据库状态，也不会解除软件的维护停止状态。</p>}
          {op && <><window.WorkbenchReference label="当前结果的原请求" value={op.request_key} /><p className="sm-meta">更新时间 {window.WorkbenchFormat.dateTime(op.updated_at)}</p></>}
          <div className="sm-actions"><C.Button icon="refresh-cw" busy={waiting} onClick={() => { setQuery(null); setError(null); intent ? command.lookup() : command.inspectHost(); }}>核实原请求</C.Button>
            <C.Button transfer="export" onClick={() => { try { R.download(host, result, problem); setNotice('已导出本次维护诊断，不含数据库或完整业务日志。'); } catch (problem) { setError(problem); } }}>导出维护诊断</C.Button>
            <a href="/workbench?view=system">返回工作台</a></div><p className="sm-meta">返回入口会重新核实维护状态；需要重启或核查时仍停留在维护页。</p>
        </section>
        <section aria-label="按标识查询"><h2>查询其他维护结果</h2><form onSubmit={lookup}>
          <fieldset className="sm-choice" style={{ marginTop: 12 }}><legend>标识类型</legend>{[['request', '原请求标识'], ['job', '维护记录编号']].map(([value, label]) =>
            <label key={value}><input type="radio" name="restore-reference-kind" checked={kind === value} onChange={() => setKind(value)} />{label}</label>)}</fieldset>
          <div className="sm-restore-query"><label className="sm-field"><span>{kind === 'request' ? '原请求标识' : '维护记录编号'}</span><input aria-label="查询标识" value={reference} maxLength={128} autoComplete="off" spellCheck={false} onChange={event => setReference(event.target.value)} /></label>
            <C.Button icon="search" type="submit" busy={waiting} disabled={!reference.trim()}>查询维护结果</C.Button></div>
        </form></section>
        {op && <details className="sm-rules"><summary>维护阶段与核对信息</summary><p>维护记录编号：<code>{op.job_ref}</code> · 结果代码：<code>{op.code}</code></p>
          {op.history.map((step, index) => <p key={index}>{window.WorkbenchFormat.dateTime(step.time)} · {R.labels[step.state]}</p>)}
          {[['所选备份 SHA-256', op.target_sha256], ['保护副本 SHA-256', op.protection_sha256], ['维护结束数据库 SHA-256', op.database_after_sha256]].map(([label, value]) => <p key={label}>{label}：<code>{value || '未确认'}</code></p>)}
          <p>上述指纹来自维护记录，本页面没有重新打开或校验数据库。数据库内旧回执可能已被恢复覆盖。</p></details>}
      </main>
    </div>, document.body);
  }
  window.SystemRestorePanel = Panel;
})();
