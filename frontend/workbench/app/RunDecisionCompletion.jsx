(function () {
  'use strict';
  const C = window.RunCandidateControls, M = window.RunCandidateModel, T = window.WorkbenchTerms;
  const queryKeys = ['completion_filter', 'sort', 'order', 'page', 'size', 'snapshot_ref'];
  const filters = [['all', '全部批次'], ['complete', '工序已排齐'], ['unfinished', '工序未排齐'], ['ordinary', '其他未排齐'], ['deferred', '仅因缺料未排齐'], ['unknown', '工序安排待确认']];
  const issueLabels = { material_deferred: '工序因缺料暂未安排', operations_unscheduled: '尚有工序未安排', operations_missing: '排产时工序资料未记录',
    schedule_time_invalid: '安排时间无效', saved_plan_incomplete: '候选方案的工序安排记录不完整', due_date_missing: '交期未记录',
    due_date_invalid: '交期无效', due_date_unspecified: '未指定交期', part_label_missing: '零件名称未填写' };
  const countText = value => value === null ? '未记录' : M.number(value);
  const hasRemaining = work => work.operation_count > 0;

  function Remaining({ work, definitions, label }) {
    if (!hasRemaining(work)) return null;
    return <details className="rd-completion-demand"><summary>未安排工序需求 · {countText(work.operation_count)} 道</summary>
      <window.RunDecisionRecommendation.RemainingMetrics work={work} definitions={definitions} label={label + '剩余准备与加工需求'} className="rd-completion-demand-table" completion />
    </details>;
  }
  function Issues({ row, definitions }) {
    return <details className="rd-completion-issues"><summary>{row.issues.length ? '批次资料说明 · ' + row.issues.length + ' 项' : '批次工序数量明细'}</summary>
      <dl>{[['scheduled_operation_count', '已排工序'], ['unplanned_operation_count', '其他未安排工序'], ['deferred_operation_count', '缺料未安排工序']].map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{countText(row[key])} 道</dd></div>)}<div><dt>剩余工序</dt><dd>{countText(row.remaining_work.operation_count)} 道</dd></div></dl>
      {row.issues.length > 0 && <ul>{row.issues.map((code, index) => <li key={code + ':' + index}>{issueLabels[code] || code}</li>)}</ul>}
      {!hasRemaining(row.remaining_work) && <window.RunDecisionRecommendation.RemainingMetrics work={row.remaining_work} definitions={definitions} label={(row.batch_label || '本批次') + '剩余准备与加工需求'} className="rd-completion-demand-table" completion />}
    </details>;
  }
  function Support({ data, work, drill, batchRef, label, onSupport }) {
    return hasRemaining(work) && drill ? <C.Button icon="search" className="btn link" aria-label={label}
      onClick={() => onSupport({ kind: 'preparation', label, ref: batchRef || null, candidate_ref: data.candidate.candidate_ref, drill })}>{label}</C.Button> : null;
  }
  function Summary({ data, definitions, onSupport }) {
    const summary = data.summary, text = T.completion_summary(summary);
    return <div className="rd-completion-summary" aria-label="当前方案全部批次的工序安排摘要" data-completion-source-available={data.source.available}>
      {text && <p>{text}</p>}
      <div className="rc-tools"><Remaining work={summary.remaining_work} definitions={definitions} label="当前方案全部未安排工序" />
        <Support data={data} work={summary.remaining_work} drill={summary.drill} label="查看未安排工序" onSupport={onSupport} />
        <details className="rd-completion-issues"><summary>批次数量明细</summary><dl>{[
          ['complete_batch_count', '工序已排齐', '批'], ['incomplete_batch_count', '工序未排齐', '批'],
          ['ordinary_incomplete_batch_count', '其他未排齐', '批'], ['deferred_batch_count', '仅因缺料未排齐', '批'],
          ['unknown_batch_count', '工序安排待确认', '批'], ['unplanned_operation_count', '其他未安排工序', '道'], ['deferred_operation_count', '缺料未安排工序', '道'],
        ].map(([key, label, unit]) => <div key={key}><dt>{label}</dt><dd>{countText(summary[key])} {unit}</dd></div>)}</dl>
          {!hasRemaining(summary.remaining_work) && <window.RunDecisionRecommendation.RemainingMetrics work={summary.remaining_work} definitions={definitions} label="当前方案全部未安排工序的剩余准备与加工需求" className="rd-completion-demand-table" completion />}</details></div>
    </div>;
  }
  function Table({ data, definitions, onSupport }) {
    return <div className="rc-table wb-table-frame rd-completion-frame" data-sticky-head data-sticky-key data-sticky-actions data-wb-scroll-key="decision-completion-batches">
      <table className="wb-table rd-completion-table" aria-label="候选方案逐批工序安排"><caption className="wb-visually-hidden">当前方案选中批次的工序安排与未安排工序需求</caption>
        <thead><tr><th scope="col" className="wb-col-key">批次 / 零件</th><th scope="col">工序安排状态</th><th scope="col">工序数量</th><th scope="col">未安排准备与加工</th><th scope="col" className="wb-col-actions">查看明细</th></tr></thead>
        <tbody>{data.items.map(row => <tr key={row.batch_ref} data-completion-batch={row.batch_ref}>
          <td className="wb-col-key"><strong>{row.batch_label || '批次编号未记录'}</strong><small>{row.part_no || '图号未记录'} · {row.part_label || '零件名称未填写'}</small><small>数量 {countText(row.quantity)} 件</small><window.WorkbenchReference value={row.batch_ref} /></td>
          <td><strong>{T.delivery_completion_states[row.completion_state]}</strong><Issues row={row} definitions={definitions} /></td>
          <td><span>已排 {countText(row.scheduled_operation_count)} 道</span>{row.unplanned_operation_count !== 0 && <small>其他未安排 {countText(row.unplanned_operation_count)} 道</small>}{row.deferred_operation_count !== 0 && <small>缺料未安排 {countText(row.deferred_operation_count)} 道</small>}</td>
          <td><Remaining work={row.remaining_work} definitions={definitions} label={row.batch_label || '本批次'} /></td>
          <td className="wb-col-actions"><Support data={data} work={row.remaining_work} drill={row.remaining_drill} batchRef={row.batch_ref} label="查看未安排工序" onSupport={onSupport} /></td>
        </tr>)}</tbody>
      </table>
    </div>;
  }
  function Pane({ result, query, onQuery, onSupport, enabled }) {
    const overview = result.data, scope = overview.scope, runRef = overview.run.run_ref;
    const shared = { comparison_mode: scope.comparison_mode, resource_view: scope.resource_view, selected_candidate_ref: scope.selected_candidate_ref,
      range_start: scope.range_start, range_end: scope.range_end, ...(scope.comparison_mode === 'candidates' ? { reference_candidate_ref: scope.reference.candidate_ref } : {}) };
    const stored = Object.fromEntries(Object.entries(query).filter(([key]) => queryKeys.includes(key)));
    const q = window.RunDecisionAPI.completionScope(runRef, { ...stored, ...shared }), key = JSON.stringify(q);
    const read = window.APSResourceSession.useQuery(signal => window.RunDecisionAPI.completionBatches(runRef, q, signal), [runRef, key, result.meta.snapshot_ref], enabled);
    const detail = read.result && read.result.data.candidate.candidate_ref === q.selected_candidate_ref ? read.result : null, data = detail && detail.data;
    function update(change, paging = false) {
      const next = { ...q, ...change, page: paging ? change.page : 1 }; delete next.snapshot_ref;
      if (paging && detail) next.snapshot_ref = detail.meta.snapshot_ref;
      onQuery(Object.fromEntries(Object.entries(next).filter(([name]) => queryKeys.includes(name))));
    }
    function reload() { update({}); read.reload(); }
    if (!enabled) return null;
    return <section className="rd-completion" aria-label="候选方案批次工序安排" data-completion-anchor={q.selected_candidate_ref}>
      <div className="rd-detail-filters">
        <label>工序安排<select aria-label="批次工序安排筛选" value={q.completion_filter} onChange={event => update({ completion_filter: event.target.value })}>{filters.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>批次顺序<select aria-label="工序安排批次顺序" value={q.order} onChange={event => update({ order: event.target.value })}><option value="asc">编号升序</option><option value="desc">编号降序</option></select></label>
        <div className="rc-tools rd-detail-actions"><C.Button icon="refresh-cw" aria-label="刷新批次工序安排" disabled={read.loading} onClick={reload} /></div>
      </div>
      <C.ErrorBox error={read.error} />{read.loading && <p className="rc-muted" role="status">正在读取当前方案的批次工序安排。</p>}
      {data && <>
        <Summary data={data} definitions={overview.metric_definitions} onSupport={onSupport} /><C.Reasons rows={detail.warnings} />
        <p className="rc-muted rd-impact-basis">本表统计排进计划的工序；现场完工进度见现场记录。</p>
        {data.items.length ? <Table data={data} definitions={overview.metric_definitions} onSupport={onSupport} /> : <div className="rc-empty"><p>{data.page.total > 0 ? '当前页没有批次。' : '当前方案没有符合筛选的批次。'}</p><C.Button onClick={() => data.page.total > 0 ? update({ page: 1 }, true) : update({ completion_filter: 'all' })}>{data.page.total > 0 ? '返回第 1 页' : '清除筛选'}</C.Button></div>}
        <div className="rc-heading rd-detail-pages"><span className="rc-muted">当前类别 {data.page.total} 批 · 本页 {data.items.length} 批</span>
          <div className="rc-tools"><label>每页<select aria-label="工序安排批次每页条数" value={q.size} onChange={event => update({ size: Number(event.target.value) })}><option value="20">20 批</option><option value="50">50 批</option></select></label><C.Pager label="工序安排批次" page={data.page.number} pages={Math.max(1, Math.ceil(data.page.total / data.page.size))} disabled={read.loading} onPage={page => update({ page }, true)} /></div></div>
      </>}
    </section>;
  }
  window.RunDecisionCompletion = { Pane };
})();
