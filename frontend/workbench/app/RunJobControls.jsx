(function () {
  'use strict';
  const { Button, Modal } = window.ResourceControls, A = window.RunJobAPI;
  const labels = { queued: '等待计算', running: '正在计算', complete: '计算完成', partial: '部分完成', failed: '计算失败', interrupted: '运行中断' };
  function Status({ run }) {
    return <span className={'pill ' + (run.state === 'complete' ? 'ok' : ['failed', 'partial', 'interrupted'].includes(run.state) ? 'warn' : 'off')} data-run-state={run.state} data-run-stage={run.stage}>
      <span className="dot" />{run.recovery_required ? '等待核对运行' : labels[run.state]}</span>;
  }
  function Scope({ preview }) {
    const value = preview.normalized_input;
    return <dl className="rj-scope"><div><dt>本次批次</dt><dd>{value.batch_refs.length} 批</dd></div>
      <div><dt>计划窗口</dt><dd>{value.start_date} 至 {value.end_date}</dd></div>
      <div><dt>齐套检查</dt><dd>{value.ready_check ? '开启' : '关闭'}</dd></div>
      <div><dt>缺资源工序</dt><dd>{value.missing_resource_policy === 'auto_assign' ? '自动分配' : '暂不排'}</dd></div>
      <div><dt>已有执行</dt><dd>保留开工和完工事实</dd></div></dl>;
  }
  function Reasons({ rows }) {
    const groups = new Map();
    rows.forEach(row => { const id = row.code + '\n' + row.message, group = groups.get(id); if (group) group.count += 1; else groups.set(id, { ...row, count: 1 }); });
    return <div className="rj-notice" role="status">{Array.from(groups.values()).slice(0, 20).map((row, index) => <div key={index}>
      {['run_worker_not_connected', 'run_schema_unavailable', 'execution_ledger_unavailable'].includes(row.code) ? A.message(row) : row.message}{row.count > 1 ? '（' + row.count + ' 项）' : ''}
    </div>)}{groups.size > 20 && <div>另有 {groups.size - 20} 类原因，请返回排产检查核对。</div>}</div>;
  }
  function Confirmation({ preview, busy, onConfirm, onClose }) {
    const [page, setPage] = React.useState(1), values = preview.normalized_input.batch_refs, pages = Math.max(1, Math.ceil(values.length / 20));
    return <Modal title="确认本次候选排产" icon="play" onClose={onClose} locked={busy} footer={<>
      <Button onClick={onClose} disabled={busy}>取消</Button><Button icon="play" className="btn primary" busy={busy} onClick={onConfirm}>确认开始排产</Button></>}>
      <div className="modal-body run-job-panel rj-confirm"><Scope preview={preview} />
        <div className="rj-notice">仅计算并保存候选，不替换正式计划。日历可行性尚未验证，最终结果以本次计算记录为准。</div>
        <details><summary>批次编号 · {values.length} 批</summary><ol className="rj-refs" start={(page - 1) * 20 + 1}>
          {values.slice((page - 1) * 20, page * 20).map(value => <li key={value}>{value}</li>)}</ol>
          <div className="rj-tools"><Button icon="chevron-left" aria-label="范围上一页" disabled={page === 1} onClick={() => setPage(page - 1)} />
            <span>{page} / {pages}</span><Button icon="chevron-right" aria-label="范围下一页" disabled={page === pages} onClick={() => setPage(page + 1)} /></div></details>
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
          if (typeof api.catalog !== 'function') throw new Error('候选目录尚未接入。');
          const response = await api.catalog(run.run_ref, query, controller.signal), data = A.catalog(response, run.run_ref, query);
          const saved = new Map(run.candidates.map(c => [c.candidate_ref, c]));
          if (data.run_state !== run.state || data.candidate_count !== saved.size || data.candidates.some(c => !saved.has(c.candidate_ref)
              || saved.get(c.candidate_ref).status !== c.persisted_status || saved.get(c.candidate_ref).task_count !== c.task_count)) throw new Error('候选目录与运行回执不一致。');
          if (!disposed) setCatalog({ ...data, snapshot_ref: response.meta.snapshot_ref });
        } catch (e) { if (!disposed) setError('候选目录暂时无法核实；运行回执仍保留 ' + run.candidates.length + ' 项候选。'); }
        finally { if (!disposed) setBusy(false); }
      }
      load(); return () => { disposed = true; controller.abort(); };
    }, [api, run.run_ref, run.state, query, revision]);
    if (!run.candidates.length) return <p className="rj-muted">{A.terminal(run) ? '本次没有保存候选结果。' : '候选结果尚未保存。'}</p>;
    const canOpen = typeof api.openCandidate === 'function', selected = new Set(run.candidates.filter(c => c.selected).map(c => c.candidate_ref));
    return <section aria-label="已保存候选"><div className="rj-heading"><h3>已保存候选 · {run.candidates.length} 项</h3>
      <Button icon="refresh-cw" aria-label="刷新候选目录" busy={busy} onClick={() => { setQuery({}); refresh(); }} /></div>
      {!canOpen && <p className="rj-muted">候选详情页面尚未接入，暂不能预览。</p>}
      {error && <div className="rj-notice" role="alert">{error}</div>}{busy && <p className="rj-muted" role="status">正在读取已保存候选。</p>}
      {catalog && <>
      <div className="rj-table"><table aria-label="已保存候选"><thead><tr><th>候选</th><th>状态</th><th>已保存工序</th><th>操作</th></tr></thead><tbody>
        {catalog.candidates.map(row => <tr key={row.candidate_ref} data-candidate-ref={row.candidate_ref}>
          <td><div className="rj-name"><span>{row.label || '生成时未记录名称'}{selected.has(row.candidate_ref) && <span className="rj-selected">本次选中</span>}</span><details className="rj-id"><summary aria-label={'候选记录编号 ' + row.candidate_ref}>编号</summary><code>{row.candidate_ref}</code></details></div></td>
          <td>{{ completed: '已完成', partial: '部分完成', failed: '失败', skipped: '已跳过' }[row.status]}{row.completeness === 'unknown' && <small>完整性尚未确认</small>}</td><td>{row.task_count}</td>
          <td><Button icon="eye" className="mini" reason={canOpen ? '' : '候选详情页面尚未接入，暂不能预览。'}
            onClick={() => api.openCandidate({ candidate_ref: row.candidate_ref, run_ref: row.run_ref })}>详情</Button></td></tr>)}</tbody></table></div>
      {catalog.page.total > 20 && <div className="rj-tools"><Button icon="chevron-left" aria-label="候选上一页" disabled={busy || catalog.page.number === 1}
        onClick={() => setQuery({ page: catalog.page.number - 1, snapshot_ref: catalog.snapshot_ref })} />
        <span>{catalog.page.number} / {Math.max(1, Math.ceil(catalog.page.total / 20))}</span><Button icon="chevron-right" aria-label="候选下一页" disabled={busy || !catalog.page.has_more}
          onClick={() => setQuery({ page: catalog.page.number + 1, snapshot_ref: catalog.snapshot_ref })} /></div>}</>}</section>;
  }
  function Record({ run, intent, paused, checking, verified, api }) {
    return <section aria-label="本次运行记录" className="rj-record"><div className="rj-heading"><h3>运行记录</h3>{run ? <Status run={run} /> : <span role="status">正在核实原请求</span>}</div>
      {(intent || run) && <details className="rj-identity"><summary>记录编号</summary>{intent && <div>请求编号：{intent.request_key}</div>}{run && <div>运行编号：{run.run_ref}</div>}</details>}
      {run && !verified && <p className="rj-muted">以下为上次已核实结果，本次查询尚未确认。</p>}
      {run && <><div className="rj-tools rj-muted">
        <span>受理：{run.accepted_at.replace('T', ' ')}</span>{run.started_at && <span>开始：{run.started_at.replace('T', ' ')}</span>}
        {run.finished_at && <span>结束：{run.finished_at.replace('T', ' ')}</span>}</div>
        {run.recovery_required && <p className="rj-notice">本机正在核对原执行记录，结果尚未确定，没有重新计算。</p>}
        {run.error && <div className="rj-notice" role="alert">{A.message(run.error)}</div>}<Candidates key={run.run_ref} run={run} api={api} /></>}
      {!A.terminal(run) && <p className="rj-muted" role="status">{paused ? '页面不可见，已暂停查询；返回后继续核实原运行。' : checking ? '正在查询原运行记录。' : '等待下一次查询，不会重复提交排产。'}</p>}
    </section>;
  }
  function Styles() {
    return <style>{`
      .plana.run-job-panel{padding:0;max-width:none;width:100%;min-width:0;color:var(--ui-text);font-size:13px;letter-spacing:0}
      .run-job-panel *{box-sizing:border-box;letter-spacing:0}
      .run-job-panel h2{font-size:16px;line-height:1.5;margin:0}.run-job-panel h3{font-size:14px;line-height:1.5;margin:0}
      .run-job-panel .rj-heading,.run-job-panel .rj-tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap;min-width:0}
      .run-job-panel .rj-heading{justify-content:space-between;padding:8px 0}.run-job-panel .rj-tools{padding:6px 0}
      .run-job-panel .rj-record{border-top:1px solid var(--ui-border);margin-top:10px;padding-bottom:8px}
      .run-job-panel .rj-muted{color:var(--ui-info-muted);font-size:12px;line-height:1.7}
      .run-job-panel .rj-notice{padding:10px 12px;margin:10px 0;border-left:3px solid var(--ui-warning);background:var(--ui-surface-muted);line-height:1.7;overflow-wrap:anywhere}
      .run-job-panel .rj-scope{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:0;padding:12px 0;border-top:1px solid var(--ui-border);border-bottom:1px solid var(--ui-border)}
      .run-job-panel dt{font-size:12px;color:var(--ui-info-muted)}.run-job-panel dd{margin:5px 0 0;overflow-wrap:anywhere}
      .run-job-panel .rj-identity{overflow-wrap:anywhere;font-size:12px;line-height:1.8;color:var(--ui-info-muted);font-variant-numeric:tabular-nums}
      .run-job-panel .rj-name{display:flex;align-items:baseline;gap:8px 16px;flex-wrap:wrap;min-width:0}.run-job-panel .rj-id{font-size:12px;color:var(--ui-info-muted);min-width:0}.run-job-panel .rj-id[open]{flex-basis:100%}.run-job-panel .rj-id code{display:block;overflow-wrap:anywhere;font-size:12px;color:var(--ui-text)}.run-job-panel .rj-id summary,.run-job-panel .rj-identity summary{margin:0}
      .run-job-panel .pill.ok{color:var(--ui-success-text);background:var(--ui-success-bg)}.run-job-panel .pill.warn{color:var(--ui-warning-text);background:var(--ui-warning-bg)}
      .run-job-panel .rj-table{width:100%;overflow:auto}.run-job-panel table{width:100%;table-layout:fixed;border-collapse:collapse}
      .run-job-panel th,.run-job-panel td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--ui-border);white-space:normal!important;overflow-wrap:anywhere;vertical-align:middle}
      .run-job-panel th:first-child{width:48%}.run-job-panel th{font-size:12px;color:var(--ui-info-muted)}
      .run-job-panel small{display:block;font-size:11px;line-height:1.7;color:var(--ui-info-muted)}.run-job-panel .rj-selected{margin-left:8px;color:var(--ui-success-text);font-size:12px}
      .run-job-panel button{max-width:100%;white-space:normal}.run-job-panel .rj-refs{padding-left:26px;font-size:12px;line-height:1.8;overflow-wrap:anywhere}
      .run-job-panel summary{cursor:pointer;font-weight:600;margin:10px 0}.run-job-panel.rj-confirm{padding:16px 22px;max-height:65vh;overflow:auto}
      @media(max-width:600px){.run-job-panel th:first-child{width:42%}.run-job-panel th,.run-job-panel td{padding:8px 4px}.run-job-panel.rj-confirm{padding:12px}}
    `}</style>;
  }
  window.RunJobControls = { Button, Confirmation, Scope, Reasons, Record, Styles };
})();
