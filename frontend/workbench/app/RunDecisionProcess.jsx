(function () {
  'use strict';
  // 优化过程只有共同优化一种存档（unified-optimization-process-v1），由 RunDecisionAPI.processDetails 校验。
  const C = window.RunCandidateControls, D = window.RunDecisionComparison;
  const queryKeys = ['process_candidate_ref', 'objective', 'record_kind', 'sort', 'order', 'page', 'size', 'snapshot_ref'];
  const stopLabels = { time_budget: '时间预算已用完', iteration_limit: '达到迭代上限', search_exhausted: '当前搜索已结束', baseline_scheduled: '保留原算法结果', all_candidates_rejected: '搜索候选全部被拒绝', no_improvement: '本阶段没有进一步改善', completed: '计算完成', reserved_for_later_phases: '为后续阶段保留预算', candidate_time_budget_reached: '候选预算已用完', disabled: '此阶段未启用', stages_exhausted: '可执行尝试已结束', graph_ready_uses_graph_candidate_phase: '改用按规则生成和调整排法的阶段' };
  const flagLabels = window.RunDecisionProcessChart.flagLabels;
  const number = value => value === null || value === undefined ? '—' : window.WorkbenchFormat.number(value, { digits: 3, trim: true });
  const savedText = value => value === null || value === undefined || value === '' ? '未记录' : String(value);
  const phaseText = window.RunDecisionProcessChart.phaseText;
  function Elapsed({ value }) { return <span title={value === null ? undefined : String(value) + ' ms'}>{value === null ? '—' : value < 1000 ? number(value) + ' 毫秒' : number(value / 1000) + ' 秒'}</span>; }
  function Primary({ value, objective }) { return <span title={value === null ? undefined : String(value)}>{number(value)}{value !== null && objective.unit && ' ' + objective.unit}</span>; }
  function Score({ value, objective, fieldOrder }) {
    return <details className="rd-process-facts"><summary>计算评分 · {value.length} 项</summary><dl>{value.map((item, index) => {
      const definition = objective.score_fields.find(field => field.key === fieldOrder[index]);
      return <div key={index}><dt>{definition ? definition.label : '分量 ' + (index + 1)}</dt><dd title={item === null ? undefined : String(item)}>{number(item)}{item !== null && definition && definition.unit && ' ' + definition.unit}</dd></div>;
    })}</dl></details>;
  }
  const countLabels = [['actual_decoder_calls', '真实排法计算次数'], ['new_decisions', '新排法决策'], ['decision_reuses', '复用已核验决策'],
    ['skipped_requests', '跳过执行次数'], ['failed_decoder_calls', '计算失败次数'], ['request_count', '不同计算请求']];
  const opportunityLabels = { searched: '已探索', paused_no_gain: '已暂停暂无改善的探索', not_searched_budget: '本次预算内未探索此方向', not_applicable: '该方向当前不适用' };
  const skipLabels = { ...stopLabels, estimated_decode_cost: '剩余预算不足以执行下一次计算', waiting_for_parent: '等待可继续探索的排法', stagnation: '当前探索暂无进一步改善' };
  const objectiveLabel = (data, name) => { const descriptor = data.objectives.find(value => value.name === name); return descriptor ? descriptor.label : '方向未记录'; };
  function Scope({ scope, scopeRef }) {
    return <><span>{window.RunDecisionProcessChart.sharedScopeText(scope)}</span><window.WorkbenchReference entries={{ '评价范围编号': scopeRef }} /></>;
  }
  function Origin({ origin, data }) {
    return <><span>{phaseText(origin.phase)} · {objectiveLabel(data, origin.search_objective)}</span>
      <details className="rd-process-facts"><summary>实际生成与派工</summary><dl>{[['strategy', '生成策略'], ['dispatch_mode', '派工模式'], ['dispatch_rule', '派工规则']].map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{savedText(origin[key])}</dd></div>)}</dl>
        <window.WorkbenchReference entries={{ '来源类型': origin.origin, '搜索阶段': origin.phase, '搜索方向': origin.search_objective }} /></details></>;
  }
  function CandidateTable({ data, overview, anchorRef, onAnchor }) {
    return <div className="rc-table wb-table-frame rd-process-candidate-frame" data-sticky-head data-sticky-key data-sticky-actions data-wb-scroll-key="decision-process-candidates"><table className="wb-table rd-process-source-table" aria-label="本次候选来源定位">
      <thead><tr>{['候选 / 业务方向', '首次发现', '实际生成来源', '来源定位'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{data.candidates.map(candidate => <tr key={candidate.candidate_ref} data-process-candidate={candidate.candidate_ref} data-selected={candidate.candidate_ref === anchorRef || undefined}>
        <td><strong>{candidate.label}</strong><small>{candidate.representative_objectives.map(name => objectiveLabel(data, name)).join(' · ')}</small>{candidate.candidate_ref === overview.recommendation.candidate_ref && <small>推荐</small>}</td>
        <td>首次发现于 <Elapsed value={candidate.first_found_elapsed_ms} /></td><td><Origin origin={candidate.origin} data={data} /></td>
        <td><C.Button className="btn link" aria-pressed={candidate.candidate_ref === anchorRef} onClick={() => onAnchor(candidate.candidate_ref)}>{candidate.candidate_ref === anchorRef ? '当前来源' : '定位来源'}</C.Button></td>
      </tr>)}</tbody></table></div>;
  }
  function Summary({ data }) {
    const direction = data.budget.objectives[data.selected_objective.name];
    return <><div className="rd-process-heading"><h3>共同优化过程</h3></div><dl className="rd-process-run-summary" aria-label="本次共同优化统计">
      <div><dt>总计算用时</dt><dd><Elapsed value={data.summary.elapsed_ms} /></dd></div><div><dt>首个完整解</dt><dd>{data.summary.first_complete_elapsed_ms === null ? '本次未产生完整解' : <Elapsed value={data.summary.first_complete_elapsed_ms} />}</dd></div>
      <div data-process-first-improvement-ms={data.summary.first_improvement_elapsed_ms}><dt>当前方向首次评分改善</dt><dd>{data.summary.first_improvement_elapsed_ms === null ? '本方向未发生评分改善' : <Elapsed value={data.summary.first_improvement_elapsed_ms} />}</dd></div>
      <div><dt>总计算预算</dt><dd>{number(data.budget.configured_seconds)} 秒</dd></div>{countLabels.map(([key, label]) => <div key={key} data-unified-count={key}><dt>{label}</dt><dd>{number(data.counts[key])}</dd></div>)}</dl>
      <p className="rd-process-chart-note">{skipLabels[data.stop_reason] || '停止原因已保存'}<window.WorkbenchReference entries={{ '停止原因': data.stop_reason }} /></p>
      <p className="rd-process-chart-note" data-process-opportunity={direction.objective_status}>{opportunityLabels[direction.objective_status]}{direction.budget_reason && <small>{skipLabels[direction.budget_reason] || '预算原因已保存'}</small>}</p>
    </>;
  }
  function Records({ data }) {
    const progress = data.filters.record_kind === 'progress', objective = data.selected_objective;
    return <div className="rc-table wb-table-frame rd-process-frame" data-sticky-head data-wb-scroll-key="decision-process-records"><table className={'wb-table rd-process-record-table ' + (progress ? 'rd-process-point-table' : 'rd-process-action-table')} aria-label={progress ? '进步曲线数值等价表' : '保存的搜索动作'}>
      <thead><tr>{(progress ? ['来源事件 / 阶段', '累计计算耗时', objective.primary_metric_label, '评价范围', '核验 / 评分'] : ['动作 / 阶段', '实际起止 / 耗时', '评估 / 已核验', '新决策 / 复用', '实际结果']).map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
      <tbody>{data.items.map((row, index) => progress ? <tr key={row.source_event_id + ':' + row.elapsed_ms + ':' + index} data-process-point={row.source_event_id}>
        <td><strong>来源事件 {row.source_event_id}</strong><small>{phaseText(row.phase)}</small>{row.flags.length > 0 && <small>{row.flags.map(flag => flagLabels[flag] || flag).join(' · ')}</small>}</td>
        <td><Elapsed value={row.elapsed_ms} /></td><td><Primary value={row.primary_value} objective={objective} /></td><td><Scope scope={data.scopes[row.scope_ref]} scopeRef={row.scope_ref} /></td>
        <td>{row.verified ? '已核验' : '未核验'}<Score value={row.score} objective={objective} fieldOrder={row.field_order} /></td>
      </tr> : <tr key={row.action_id} data-process-action={row.action_id}>
        <td><strong>动作 {row.action_id}</strong><small>{phaseText(row.phase)}</small>{row.initial_construction && <small>构建起始排法</small>}</td>
        <td><Elapsed value={row.started_elapsed_ms} /><small>至 <Elapsed value={row.finished_elapsed_ms} /></small><small>动作耗时 <Elapsed value={row.elapsed_ms} /></small></td>
        <td>{number(row.evaluation_count)} / {number(row.verified_evaluation_count)}</td><td>{number(row.new_decisions)} / {number(row.reused_decisions)}</td>
        <td>{row.skip_reason ? skipLabels[row.skip_reason] || '动作未执行' : row.improved_objectives.length ? '改善：' + row.improved_objectives.map(name => objectiveLabel(data, name)).join(' · ') : '本动作未带来评分改善'}{row.skip_reason && <window.WorkbenchReference entries={{ '动作未执行原因': row.skip_reason }} />}</td>
      </tr>)}</tbody></table></div>;
  }
  function Stages({ values }) {
    return <details className="rd-process-stages"><summary>当前方向阶段 · {values.length} 项</summary><div className="rc-table wb-table-frame rd-process-frame" data-sticky-head data-wb-scroll-key="decision-process-stages"><table className="wb-table rd-process-stage-table" aria-label="共同优化方向的阶段事实">
      <thead><tr>{['阶段', '实际开始 / 结束', '耗时 / 动作数', '评估 / 已核验', '新决策 / 复用'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{values.map(stage => <tr key={stage.phase} data-process-phase={stage.phase}>
        <td>{phaseText(stage.phase)}</td><td><Elapsed value={stage.start_elapsed_ms} /><small>至 <Elapsed value={stage.end_elapsed_ms} /></small></td><td><Elapsed value={stage.elapsed_ms} /><small>{number(stage.action_count)} 个动作</small></td><td>{number(stage.evaluation_count)} / {number(stage.verified_evaluation_count)}</td><td>{number(stage.new_decisions)} / {number(stage.reused_decisions)}</td>
      </tr>)}</tbody></table></div></details>;
  }
  function Source({ data }) {
    const source = data.source_event, candidate = data.candidate;
    return <details className="rd-process-facts"><summary>当前候选来源与方向记录</summary><p>{candidate.label} · 首次发现于 <Elapsed value={candidate.first_found_elapsed_ms} /></p><Origin origin={candidate.origin} data={data} />
      <window.WorkbenchReference entries={{ '来源候选': candidate.candidate_ref, '来源事件': source && source.event_id, '排产记录': data.run_ref }} />
      {source && <p>来源事件 {source.event_id} · 保存于 <Elapsed value={source.elapsed_ms} /> · {source.verified ? '已核验' : '未核验'}</p>}
      <h4>各方向实际探索</h4><dl>{data.objectives.map(descriptor => { const goal = data.budget.objectives[descriptor.name]; return <div key={descriptor.name}><dt>{descriptor.label}</dt><dd>{opportunityLabels[goal.objective_status]} · {number(goal.action_count)} 个动作</dd></div>; })}</dl>
      {data.bridges.length > 0 && <details className="rd-process-facts"><summary>参考排法接续 · {data.bridges.length} 项</summary><div className="wb-table-frame"><table className="wb-table rd-process-bridge-table" aria-label="保存的参考排法接续"><thead><tr>{['方向 / 阶段', '实际起止', '接续耗时', '原排法 / 计算事实'].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{data.bridges.map(bridge => <tr key={bridge.source_event_id}>
        <td>{objectiveLabel(data, bridge.search_objective)}<small>{phaseText(bridge.phase)}</small></td><td><Elapsed value={bridge.started_elapsed_ms} /><small>至 <Elapsed value={bridge.finished_elapsed_ms} /></small></td><td><Elapsed value={bridge.elapsed_ms} /></td>
        <td>{bridge.same_arrangement === null ? '原排法对应关系未记录' : bridge.same_arrangement ? '保留同一排法' : '取得另一排法'}<small>{bridge.decoder_executed ? '实际执行计算' : '未执行计算'}</small><window.WorkbenchReference entries={{ '来源事件': bridge.source_event_id, '接续前排法': bridge.before_entry_id, '接续后排法': bridge.after_entry_id, '参考方式': bridge.reference_kind }} /></td>
      </tr>)}</tbody></table></div></details>}
    </details>;
  }
  function Coverage({ data }) {
    const sampling = data.progress.sampling;
    return <div className="rd-process-coverage"><span>当前方向保留 {number(data.progress.points.length)} 个点 · 原进展 {number(sampling.event_total_count)} 个事件</span>
      <details className="rd-process-facts"><summary>进展记录说明</summary><p>按计算耗时分段保留最好结果，并保留关键首尾记录；最多保留 {sampling.point_budget} 个点。</p>
        <p>评价范围变化时分段显示；评分缺项保留未知值。</p><window.WorkbenchReference entries={{ '保存方式': sampling.policy }} /></details></div>;
  }
  function Pane({ result, query, onQuery, enabled }) {
    const overview = result.data, scope = overview.scope, runRef = overview.run.run_ref;
    const stored = Object.fromEntries(Object.entries(query).filter(([key]) => queryKeys.includes(key)));
    const shared = { comparison_mode: scope.comparison_mode, resource_view: scope.resource_view, selected_candidate_ref: scope.selected_candidate_ref, range_start: scope.range_start, range_end: scope.range_end,
      ...(scope.comparison_mode === 'candidates' ? { reference_candidate_ref: scope.reference.candidate_ref } : {}) };
    const q = window.RunDecisionAPI.processScope(runRef, { ...stored, ...shared, process_candidate_ref: stored.process_candidate_ref || scope.selected_candidate_ref || undefined }), key = JSON.stringify(q);
    const [paused, setPaused] = React.useState(false);
    React.useEffect(() => { setPaused(false); }, [runRef, key, result.meta.snapshot_ref]);
    const read = window.APSResourceSession.useQuery(signal => window.RunDecisionAPI.process(runRef, q, signal), [runRef, key, result.meta.snapshot_ref], enabled && !paused);
    const detail = read.result && (!q.process_candidate_ref || read.result.data.candidate.candidate_ref === q.process_candidate_ref) ? read.result : null, data = detail && detail.data;
    function update(change, paging = false) {
      const next = { ...q, ...change, page: paging ? change.page : 1 }; delete next.snapshot_ref;
      if (data && !next.objective) next.objective = data.selected_objective.name;
      if (paging && detail) next.snapshot_ref = detail.meta.snapshot_ref;
      setPaused(false); onQuery(Object.fromEntries(Object.entries(next).filter(([name]) => queryKeys.includes(name))));
    }
    function recordKind(value) { update({ record_kind: value, sort: value === 'progress' ? 'elapsed_ms' : 'rank' }); }
    function reload() { update({}); read.reload(); }
    if (!enabled) return null;
    const sorts = q.record_kind === 'progress' ? [['elapsed_ms', '累计耗时'], ['event_index', '保存事件顺序'], ['primary_value', '主目标值']] : [['rank', '动作顺序'], ['elapsed_ms', '动作耗时']];
    return <section className="rd-process" aria-label="候选优化过程" data-process-anchor={data ? data.candidate.candidate_ref : q.process_candidate_ref}>
      <div className="rd-detail-filters rd-process-actions">
        <div className="rc-tools rd-detail-actions">{data && <D.Export key={detail.meta.snapshot_ref} result={detail} initialSection="process" filterQuery={{ ...q, process_candidate_ref: data.candidate.candidate_ref }} />}<C.Button icon="refresh-cw" aria-label="刷新优化过程" disabled={read.loading} onClick={reload} /></div>
      </div>
      <C.ErrorBox error={read.error} />{read.loading && <div className="rc-tools"><span role="status">正在读取保存的优化过程。</span><C.Button icon="x" onClick={() => setPaused(true)}>取消读取</C.Button></div>}{paused && <p className="rc-muted" role="status">过程读取已取消，点击刷新继续。</p>}
      {data && <><Summary data={data} />
        <C.Reasons rows={detail.warnings} />
        <div className="rd-process-objective"><label>优化方向<select aria-label="优化方向" value={data.selected_objective.name} onChange={event => update({ objective: event.target.value })}>{data.objectives.map(descriptor => <option key={descriptor.name} value={descriptor.name}>{descriptor.label}</option>)}</select></label></div>
        <window.RunDecisionProcessChart.Chart key={data.selected_objective.name} progress={data.progress} objective={data.selected_objective} elapsedMs={data.summary.elapsed_ms}
          scopes={data.scopes} sourceEventId={data.source_event ? data.source_event.event_id : null} lastImprovementElapsedMs={data.summary.last_improvement_elapsed_ms} />
        <Coverage data={data} />
        <details className="rd-process-records"><summary>计算明细</summary><div className="rd-process-record-tools"><div className="rc-tabs" role="group" aria-label="优化过程记录视图">{[['attempts', '搜索动作'], ['progress', '曲线数据']].map(([value, label]) => <C.Button key={value} aria-pressed={q.record_kind === value} onClick={() => recordKind(value)}>{label}</C.Button>)}</div>
          <label>排序<select aria-label="优化过程排序" value={q.sort} onChange={event => update({ sort: event.target.value })}>{sorts.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>顺序<select aria-label="优化过程顺序" value={q.order} onChange={event => update({ order: event.target.value })}><option value="asc">升序</option><option value="desc">降序</option></select></label>
          </div>
        {data.items.length ? <Records data={data} /> : <p className="rc-empty">这个方向没有保存当前类别的过程记录。</p>}
        <div className="rc-heading rd-detail-pages"><span className="rc-muted">当前类别 {data.page.total} 条 · 本页 {data.items.length} 条</span><div className="rc-tools"><label>每页<select aria-label="优化过程每页条数" value={q.size} onChange={event => update({ size: Number(event.target.value) })}><option value="20">20 条</option><option value="50">50 条</option></select></label><C.Pager label="优化过程记录" page={data.page.number} pages={Math.max(1, Math.ceil(data.page.total / data.page.size))} disabled={read.loading} onPage={page => update({ page }, true)} /></div></div>
        <details className="rd-process-catalog"><summary>全部候选的来源定位 · {data.candidates.length} 项</summary><CandidateTable data={data} overview={overview} anchorRef={data.candidate.candidate_ref} onAnchor={candidateRef => update({ process_candidate_ref: candidateRef })} /></details>
        <Stages values={data.stages} /><Source data={data} />
        </details>
      </>}
    </section>;
  }
  window.RunDecisionProcess = { Pane, CandidateTable, Coverage, Summary, Records, Stages, Source, Scope, Score, Elapsed, Primary };
})();
