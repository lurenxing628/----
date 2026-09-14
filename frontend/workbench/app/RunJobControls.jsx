(function () {
  'use strict';
  const { Button, Modal } = window.ResourceControls, A = window.RunJobAPI;
  const labels = { queued: '等待计算', running: '正在计算', complete: '计算完成', partial: '部分完成', failed: '计算失败', interrupted: '排产中断' };
  function Progress({ run }) {
    const [now, setNow] = React.useState(Date.now);
    React.useEffect(() => {
      if (run.finished_at) return undefined;
      const timer = setInterval(() => { if (!document.hidden) setNow(Date.now()); }, 1000);
      return () => clearInterval(timer);
    }, [run.run_ref, run.finished_at]);
    const progress = run.progress, computing = !A.terminal(run) && !run.recovery_required;
    const percent = progress && progress.total > 0 ? Math.round(progress.done / progress.total * 100) : null;
    return <div className="rj-progress" data-run-progress><p><strong>{window.RunPresentation.stage(run)}</strong><span>已耗时 {window.RunPresentation.elapsed(run, now)}</span>
      {progress && <span data-run-progress-count>已算完 {progress.done} / {progress.total} 个候选方案 · 最近更新 {window.WorkbenchFormat.dateTime(progress.updated_at)}</span>}</p>
      {computing && <div className={'rj-bar' + (percent === null ? ' rj-bar-indeterminate' : '')} role="progressbar" aria-label="排产计算进度"
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent === null ? undefined : percent} aria-valuetext={percent === null ? '正在计算，进度未知' : '已算完 ' + progress.done + ' / ' + progress.total + ' 个候选方案'}>
        <i className="rj-bar-fill" style={percent === null ? undefined : { width: percent + '%' }} /></div>}
      {computing && <p className="rj-notice" role="status">计算还没结束，请不要关闭或刷新本页；切到别的页面会暂停查询，回来后自动续查。</p>}</div>;
  }
  function Status({ run }) {
    return <span className={'pill ' + (run.state === 'complete' ? 'ok' : ['failed', 'partial', 'interrupted'].includes(run.state) ? 'warn' : 'off')} data-run-state={run.state} data-run-stage={run.stage}>
      <span className="dot" />{run.recovery_required ? '等待核对排产记录' : labels[run.state]}</span>;
  }
  function Scope({ preview }) {
    const value = preview.normalized_input;
    return <dl className="rj-scope"><div><dt>本次批次</dt><dd>{value.batch_refs.length} 批</dd></div>
      <div><dt>排产日期</dt><dd>{value.start_date} 至 {value.end_date}</dd></div>
      <div><dt>齐套检查</dt><dd>{value.ready_check ? '开启' : '关闭'}</dd></div>
      <div><dt>缺资源工序</dt><dd>{value.missing_resource_policy === 'auto_assign' ? '自动分配' : '暂不排'}</dd></div>
      <div><dt>已有报工</dt><dd>保留已开工和已完工的记录</dd></div></dl>;
  }
  function Reasons({ rows }) {
    const groups = new Map();
    rows.forEach(row => { const id = row.code + '\n' + row.message, group = groups.get(id); if (group) group.count += 1; else groups.set(id, { ...row, count: 1 }); });
    return <div className="rj-notice" role="status">{Array.from(groups.values()).slice(0, 20).map((row, index) => <div key={index}>
      {['run_worker_not_connected', 'run_schema_unavailable', 'execution_ledger_unavailable'].includes(row.code) ? A.message(row) : row.message}{row.count > 1 ? '（' + row.count + ' 项）' : ''}
      <window.WorkbenchReference entries={A.details(row)} />
    </div>)}{groups.size > 20 && <div>另有 {groups.size - 20} 类原因，请返回排产检查核对。</div>}</div>;
  }
  function Confirmation({ preview, busy, onConfirm, onClose }) {
    const [page, setPage] = React.useState(1), values = preview.normalized_input.batch_refs, pages = Math.max(1, Math.ceil(values.length / 20));
    return <Modal title="确认本次候选排产" icon="play" onClose={onClose} locked={busy} footer={<>
      <Button onClick={onClose} disabled={busy}>取消</Button><Button icon="play" className="btn primary" busy={busy} onClick={onConfirm}>确认开始排产</Button></>}>
      <div className="modal-body run-job-panel rj-confirm"><Scope preview={preview} />
        <div className="rj-notice">只计算并保存候选方案，不替换正式计划。班表是否排得下还没核对，最终结果看这次排产记录。</div>
        <details className="wb-ref"><summary>批次内部编号 · {values.length} 批</summary><ol className="rj-refs" start={(page - 1) * 20 + 1}>
          {values.slice((page - 1) * 20, page * 20).map(value => <li key={value}>{value}</li>)}</ol>
          <window.WorkbenchListControls.Pager page={page} pages={pages} total={values.length} size={20} unit="批" label="范围" onPage={setPage} /></details>
        {!!preview.warnings.length && <Reasons rows={preview.warnings} />}</div>
    </Modal>;
  }
  function Candidates({ run, api }) {
    const [query, setQuery] = React.useState({}), [catalog, setCatalog] = React.useState(null), [error, setError] = React.useState('');
    const [busy, setBusy] = React.useState(false), [revision, refresh] = React.useReducer(v => v + 1, 0);
    React.useEffect(() => {
      if (!run.candidates.length) return undefined;
      const controller = new AbortController(); let disposed = false;
      setBusy(true); setCatalog(null); setError('');
      async function load() {
        try {
          if (typeof api.catalog !== 'function') throw new Error('dependency not wired: adapter.catalog');
          const response = await api.catalog(run.run_ref, query, controller.signal), data = A.catalog(response, run.run_ref, query);
          const saved = new Map(run.candidates.map(c => [c.candidate_ref, c]));
          if (data.run_state !== run.state || data.candidate_count !== saved.size || data.candidates.some(c => !saved.has(c.candidate_ref)
              || saved.get(c.candidate_ref).status !== c.persisted_status || saved.get(c.candidate_ref).task_count !== c.task_count)) throw new Error('候选方案列表与这次排产的结果不一致。');
          if (!disposed) setCatalog({ ...data, snapshot_ref: response.meta.snapshot_ref });
        } catch (e) { if (!disposed) setError('暂时读不到候选方案列表；这次排产的结果里仍有 ' + run.candidates.length + ' 个候选方案。'); }
        finally { if (!disposed) setBusy(false); }
      }
      load(); return () => { disposed = true; controller.abort(); };
    }, [api, run.run_ref, run.state, query, revision]);
    if (!run.candidates.length) return <p className="rj-muted">{A.terminal(run) ? '这次排产没有保存候选方案。' : '候选方案还没保存。'}</p>;
    const canOpen = typeof api.openCandidate === 'function', selected = new Set(run.candidates.filter(c => c.selected).map(c => c.candidate_ref));
    return <section aria-label="已保存候选方案"><div className="rj-heading"><h3>已保存候选方案 · {run.candidates.length} 项</h3>
      <Button icon="refresh-cw" aria-label="刷新候选方案列表" busy={busy} onClick={() => { setQuery({}); refresh(); }} /></div>
      {!canOpen && <p className="rj-muted">{window.WorkbenchTerms.outcomes.unavailable}</p>}
      {error && <div className="rj-notice" role="alert">{error}</div>}{busy && <p className="rj-muted" role="status">正在读取已保存候选方案。</p>}
      {catalog && <>
      <div className="rj-table wb-table-frame" data-sticky-head data-sticky-actions><table className="wb-table" aria-label="已保存候选"><caption className="wb-visually-hidden">已保存候选</caption><thead><tr><th scope="col" className="wb-col-key">候选</th><th scope="col">状态</th><th scope="col">已保存工序</th><th scope="col" className="wb-col-actions">操作</th></tr></thead><tbody>
        {catalog.candidates.map(row => <tr key={row.candidate_ref} data-candidate-ref={row.candidate_ref}>
          <td className="wb-col-key"><div className="rj-name"><span>{row.label || '生成时名称未填写'}{selected.has(row.candidate_ref) && <span className="rj-selected">本次选中</span>}</span><window.WorkbenchReference value={row.candidate_ref} /></div></td>
          <td>{{ completed: '已完成', partial: '部分完成', failed: '失败', skipped: '已跳过' }[row.status]}{row.completeness === 'unknown' && <small>完整性尚未确认</small>}</td><td>{row.task_count}</td>
          <td className="wb-col-actions"><Button icon="eye" className="mini" reasonDisplay="tooltip" reason={canOpen ? '' : window.WorkbenchTerms.outcomes.unavailable}
            onClick={() => api.openCandidate({ candidate_ref: row.candidate_ref, run_ref: row.run_ref })}>详情</Button></td></tr>)}</tbody></table></div>
      {catalog.page.total > 20 && <window.WorkbenchListControls.Pager page={catalog.page} size={20} unit="项" label="候选" busy={busy}
        onPage={page => setQuery({ page, snapshot_ref: catalog.snapshot_ref })} />}</>}</section>;
  }
  function Record({ run, intent, paused, checking, verified, api }) {
    return <section aria-label="这次排产记录" className="rj-record"><div className="rj-heading"><h3>排产记录</h3>{run ? <Status run={run} /> : <span role="status">正在查询上次排产的结果</span>}</div>
      {(intent || run) && <window.WorkbenchReference entries={{ ...(intent ? { '操作编号': intent.request_key } : {}), ...(run ? { '排产编号': run.run_ref } : {}) }} />}
      {run && !verified && <p className="rj-muted">下面是上次查到的结果，这次查询还没确认。</p>}
      {run && <><Progress run={run} /><div className="rj-tools rj-muted">
        <span>提交：{window.WorkbenchFormat.dateTime(run.accepted_at)}</span>{run.started_at && <span>开始：{window.WorkbenchFormat.dateTime(run.started_at)}</span>}
        {run.finished_at && <span>结束：{window.WorkbenchFormat.dateTime(run.finished_at)}</span>}</div>
        {run.recovery_required && <p className="rj-notice">正在核对上次的排产记录，结果还没确认，没有重新计算。</p>}
        {run.error && <div className="rj-notice" role="alert">{A.message(run.error)}</div>}<Candidates key={run.run_ref} run={run} api={api} /></>}
      {!A.terminal(run) && <p className={paused ? 'rj-notice' : 'rj-muted'} role="status">{paused ? '页面切走了，已暂停查询；回到本页会继续查上次排产的结果。' : checking ? '正在查询上次排产的记录。' : '等待下一次查询，不会重复提交排产。'}</p>}
    </section>;
  }
  function Styles() {
    return null;
  }
  window.RunJobControls = { Button, Confirmation, Scope, Reasons, Record, Styles };
})();
