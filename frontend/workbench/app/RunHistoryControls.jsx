(function () {
  'use strict';
  const A = window.RunHistoryAPI;
  const labels = { all: '全部状态', queued: '等待计算', running: '正在计算', complete: '计算完成', partial: '部分完成', failed: '计算失败', interrupted: '已中断' };
  const fields = { start_date: '排产起日', end_date: '排产止日', ready_check: '齐套检查', missing_resource_policy: '缺资源策略', completed_policy: '执行策略', batch_count: '所选批次' };
  function Button({ className = '', ...props }) { return <window.ResourceControls.Button {...props} className={'btn wb-action ' + className} />; }
  const timeLabel = v => v === null ? '未记录' : v.replace('T', ' ');
  const number = v => v.toLocaleString('zh-CN');
  function ErrorBox({ error }) {
    return error ? <div className="rh-notice rh-error" role="alert">{error.code === 'snapshot_stale' && <strong>历史来源已变化或快照已失效。 </strong>}
      {error.message || '排产历史读取失败，未显示替代结果。'}</div> : null;
  }
  function Filters({ value, busy, onApply }) {
    const [draft, setDraft] = React.useState(value), [error, setError] = React.useState(null);
    React.useEffect(() => { setDraft(value); setError(null); }, [value]);
    const set = patch => { setDraft(v => ({ ...v, ...patch })); setError(null); };
    function submit(e) {
      e.preventDefault();
      try {
        const q = { ...draft, page: 1 }; delete q.snapshot_ref;
        if (!q.accepted_from && !q.accepted_to) { delete q.accepted_from; delete q.accepted_to; }
        const next = A.scope(q); onApply(next); setError(null);
      } catch (failure) { setError(failure); }
    }
    return <form className="rh-filters" aria-label="排产历史筛选" onSubmit={submit} noValidate><div className="rh-filter-row">
      <label>运行状态<select aria-label="历史运行状态" value={draft.state} disabled={busy} onChange={e => set({ state: e.target.value })}>
        {['all', ...A.states].map(state => <option key={state} value={state}>{labels[state]}</option>)}</select></label>
      <label>受理起日<input type="date" aria-label="历史受理起日" value={draft.accepted_from || ''} disabled={busy} onChange={e => set({ accepted_from: e.target.value })} /></label>
      <label>受理止日<input type="date" aria-label="历史受理止日" value={draft.accepted_to || ''} disabled={busy} onChange={e => set({ accepted_to: e.target.value })} /></label>
      <label>排序<select aria-label="历史排序字段" value={draft.sort} disabled={busy} onChange={e => set({ sort: e.target.value })}>
        <option value="accepted_at">受理时间</option><option value="started_at">开始时间</option><option value="finished_at">结束时间</option></select></label>
      <label>顺序<select aria-label="历史排序方向" value={draft.order} disabled={busy} onChange={e => set({ order: e.target.value })}>
        <option value="desc">从新到旧</option><option value="asc">从旧到新</option></select></label>
      <div className="rh-tools"><Button type="submit" icon="search" aria-label="查询排产历史" busy={busy}>查询</Button>
        <Button icon="x" aria-label="清除历史筛选" disabled={busy} onClick={() => { setError(null); onApply(A.scope({ size: value.size })); }} /></div>
    </div><ErrorBox error={error} /></form>;
  }
  function Status({ run }) {
    const tone = run.recovery_required || ['partial', 'interrupted'].includes(run.state) ? 'rh-warning' : run.state === 'failed' ? 'rh-danger' : run.state === 'complete' ? 'rh-success' : '';
    return <div><strong className={'rh-state ' + tone}>{run.recovery_required ? '恢复待核对' : labels[run.state]}</strong>
      <small>{run.recovery_required ? run.recovery_reason.message : { queued: '尚未开始计算', running: '运行尚未结束', complete: '计算结束，约束未核验',
        partial: '保留部分结果，须查看候选', failed: '未保存可用候选', interrupted: '运行中断，未自动重跑' }[run.state]}</small>
      {run.recovery_required && <small>原状态：{labels[run.state]}</small>}</div>;
  }
  function ScopeSummary({ value }) {
    return <div><span>{value.start_date || '起日未记录'} 至 {value.end_date || '止日未记录'}</span>
      <small>选批 {value.batch_count === null ? '未记录' : number(value.batch_count) + ' 个'} · 齐套{value.ready_check === null ? '未记录' : value.ready_check ? '开启' : '关闭'}</small>
      <details><summary>排产设置</summary><small>缺资源：{{ auto_assign: '自动分配', exclude: '暂不排' }[value.missing_resource_policy] || '未记录'} · {value.completed_policy === 'preserve_actuals' ? '保留开工和完工记录' : '执行策略未记录'}</small></details>
      {!!value.data_gaps.length && <details><summary className="rh-warning">受理资料缺项 {value.data_gaps.length}</summary>
        {value.data_gaps.map(g => <small key={g.field}>{fields[g.field]}：{g.message}</small>)}</details>}</div>;
  }
  function Table({ runs, onOpen, canNavigate }) {
    return <div className="rh-table" tabIndex={0} aria-label="排产历史表格滚动区域"><table aria-label="排产历史">
      <colgroup>{[19, 18, 25, 19, 6, 6, 7].map((width, i) => <col key={i} style={{ width: width + '%' }} />)}</colgroup>
      <thead><tr><th>受理时间</th><th>运行状态</th><th>排产范围</th><th>开始 / 结束时间</th><th className="rh-num">候选数</th><th className="rh-num">安排数</th><th>操作</th></tr></thead>
      <tbody>{runs.map(run => <tr key={run.run_ref} data-run-ref={run.run_ref} data-run-state={run.state}>
        <td><time>{timeLabel(run.accepted_at)}</time><details className="rh-id"><summary aria-label={'运行记录编号 ' + run.run_ref}>记录编号</summary><code>{run.run_ref}</code></details></td><td><Status run={run} /></td>
        <td><ScopeSummary value={run.scope_summary} /></td><td><time>{run.started_at === null ? '尚未开始' : timeLabel(run.started_at)}</time>
          <small>{run.finished_at === null ? '尚未结束' : timeLabel(run.finished_at)}</small></td>
        <td className={'rh-num' + (run.counts_final && run.candidate_count > 0 ? ' rh-accent' : '')}>{number(run.candidate_count)}{!run.counts_final && <small>非最终</small>}</td>
        <td className="rh-num">{number(run.task_count)}{!run.counts_final && <small>非最终</small>}</td>
        <td><Button icon="arrow-right" aria-label={'查看运行 ' + run.run_ref} disabled={!canNavigate} onClick={() => onOpen(run)} /></td>
      </tr>)}</tbody></table></div>;
  }
  function Pager({ page, busy, onChange }) {
    const pages = Math.max(1, Math.ceil(page.total / page.size)), sizes = Array.from(new Set([10, 20, 50, page.size])).sort((a, b) => a - b);
    return <div className="rh-pagination"><span>筛选命中 {number(page.total)} 次 · 第 {page.number} / {pages} 页</span><div className="rh-tools">
      <label>每页<select aria-label="历史每页数量" value={page.size} disabled={busy} onChange={e => onChange({ page: 1, size: Number(e.target.value) }, false)}>
        {sizes.map(size => <option key={size} value={size}>{size}</option>)}</select></label>
      <Button icon="chevron-left" aria-label="历史上一页" disabled={busy || page.number <= 1} onClick={() => onChange({ page: page.number - 1 }, true)} />
      <Button icon="chevron-right" aria-label="历史下一页" disabled={busy || !page.has_more} onClick={() => onChange({ page: page.number + 1 }, true)} /></div></div>;
  }
  function Styles() {
    return <style>{`
      .plana.run-history-workspace{width:100%;min-width:0;max-width:none;padding:0;color:var(--ui-text);font-size:13px;letter-spacing:0}
      .run-history-workspace *{box-sizing:border-box;letter-spacing:0}.run-history-workspace h2{font-size:17px;line-height:1.6;margin:0}
      .run-history-workspace .rh-heading,.run-history-workspace .rh-tools,.run-history-workspace .rh-pagination{display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-width:0}
      .run-history-workspace .rh-heading,.run-history-workspace .rh-pagination{justify-content:space-between;padding:12px 0}.run-history-workspace .rh-heading{border-bottom:1px solid var(--ui-border)}
      .run-history-workspace .rh-muted,.run-history-workspace small{color:var(--ui-info-muted);font-size:12px;line-height:1.7}.run-history-workspace small{display:block;overflow-wrap:anywhere}
      .run-history-workspace .rh-filters{padding:14px 0;border-bottom:1px solid var(--ui-border)}.run-history-workspace .rh-filter-row{display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap}
      .run-history-workspace label{display:grid;gap:6px;font-size:12px;color:var(--ui-info-muted)}.run-history-workspace .rh-filter-row select{width:126px}.run-history-workspace input[type=date]{width:156px}
      .run-history-workspace select,.run-history-workspace input{font:inherit;color:var(--ui-text);background:var(--ui-surface);border:1px solid var(--ui-border);border-radius:4px;min-height:32px;max-width:100%;padding:5px 8px}
      .run-history-workspace button{max-width:100%;white-space:nowrap}.run-history-workspace .rh-pagination label{display:flex;align-items:center;gap:8px}.run-history-workspace .rh-pagination select{width:74px}
      .run-history-workspace .rh-source{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:10px 0;line-height:1.8;color:var(--ui-info-muted);font-size:12px}
      .run-history-workspace .rh-notice{padding:10px 12px;margin:10px 0;background:var(--ui-surface-muted);border-left:3px solid var(--ui-warning);line-height:1.7;overflow-wrap:anywhere}
      .run-history-workspace .rh-error,.run-history-workspace .rh-danger{color:var(--ui-danger-text)}.run-history-workspace .rh-error{border-color:var(--ui-danger)}
      .run-history-workspace .rh-warning{color:var(--ui-warning-text)}.run-history-workspace .rh-success{color:var(--ui-success-text)}.run-history-workspace .rh-accent{color:var(--ui-primary);font-weight:600}
      .run-history-workspace .rh-state{font-size:13px;font-weight:600}.run-history-workspace .rh-table{width:100%;overflow:auto;max-height:calc(100vh - 400px);min-height:130px;border-top:1px solid var(--ui-border);border-bottom:1px solid var(--ui-border)}
      .run-history-workspace .rh-table .btn{width:32px;height:32px;min-width:32px;padding:0;flex:none}
      .run-history-workspace table{border-collapse:separate;border-spacing:0;table-layout:fixed;width:100%;min-width:960px}.run-history-workspace th,.run-history-workspace td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--ui-border);vertical-align:middle;white-space:normal!important;overflow-wrap:anywhere;line-height:1.7}
      .run-history-workspace th{position:sticky;top:0;z-index:1;background:var(--ui-surface-muted);font-size:12px;color:var(--ui-info-muted);font-weight:500}.run-history-workspace tbody tr:last-child td{border-bottom:0}
      .run-history-workspace tbody tr:hover{background:var(--ui-surface-muted)}.run-history-workspace code{display:block;overflow-wrap:anywhere;font-size:12px;line-height:1.7;color:var(--ui-text);margin-top:4px;font-family:ui-monospace,monospace}.run-history-workspace .rh-id{color:var(--ui-info-muted)}
      .run-history-workspace time,.run-history-workspace .rh-num{font-variant-numeric:tabular-nums}.run-history-workspace .rh-num{text-align:right}.run-history-workspace td.rh-num{font-size:15px}
      .run-history-workspace summary{cursor:pointer;font-size:12px}.run-history-workspace .rh-empty{padding:48px 12px;text-align:center;border-block:1px solid var(--ui-border);line-height:1.8;color:var(--ui-info-muted)}
      .run-history-workspace .rh-empty strong{display:block;font-size:14px;color:var(--ui-text);margin-bottom:6px}.run-history-workspace .rh-pagination{font-size:12px;color:var(--ui-info-muted)}
      @media(max-width:760px){.run-history-workspace .rh-filter-row{gap:10px}.run-history-workspace .rh-table{max-height:500px}.run-history-workspace input[type=date]{width:148px}}
    `}</style>;
  }
  window.RunHistoryControls = { Button, ErrorBox, Filters, Table, Pager, Styles, timeLabel };
})();
