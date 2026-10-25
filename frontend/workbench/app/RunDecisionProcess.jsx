(function () {
  'use strict';
  const C = window.RunCandidateControls, D = window.RunDecisionComparison;
  const queryKeys = ['process_candidate_ref', 'objective', 'record_kind', 'sort', 'order', 'page', 'size', 'snapshot_ref'];
  const unifiedVersion = 'unified-optimization-process-v1';
  const countLabels = [['decoder_invocations', '排法计算次数'], ['evaluated', '尝试评估次数'], ['accepted', '搜索保留次数'], ['current_accepted', '更新搜索当前排法次数'], ['strict_improvements', '评分改善次数'], ['rejected', '搜索拒绝次数'], ['unverified_trials', '未核验尝试次数']];
  const metricLabels = { overdue_count: ['超期批次', '批'], total_tardiness_hours: ['总拖期', '小时'], weighted_tardiness_hours: ['加权拖期', '小时'], makespan_hours: ['安排时长', '小时'], changeover_count: ['算法工种切换次数', '次'] };
  const stopLabels = { time_budget: '时间预算已用完', iteration_limit: '达到迭代上限', search_exhausted: '当前搜索已结束', baseline_scheduled: '保留原算法结果', all_candidates_rejected: '搜索候选全部被拒绝', no_improvement: '本阶段没有进一步改善', completed: '计算完成', reserved_for_later_phases: '为后续阶段保留预算', candidate_time_budget_reached: '候选预算已用完', disabled: '此阶段未启用', stages_exhausted: '可执行尝试已结束', graph_ready_uses_graph_candidate_phase: '改用按规则生成和调整排法的阶段' };
  const flagLabels = window.RunDecisionProcessChart.flagLabels;
  const rejectionLabels = { same_fingerprint: '结果与已评估候选相同', validation_error: '候选校验未通过', candidate_rejected: '候选未通过接受检查', not_better: '未改善当前比较结果', no_strict_improvement: '评分没有进一步改善' };
  const sourceLabels = { own_search: '本候选求解', reused: '复用保存结果', not_started: '未开始求解', failed: '求解失败', budget_skipped: '计算期间预算已用完' };
  const comparisonLabels = { incumbent: '当时最优结果', current_solution: '当时搜索的当前结果', reference_capture: '当时保存的参考结果', none: '未设置比较对象' };
  const comparisonStates = { comparable: '同一评价范围', different_coverage: '评价批次不同', unavailable: '比较资料未保存', unverified: '本次尝试未核验', no_reference: '没有比较对象' };
  const number = value => value === null || value === undefined ? '—' : window.WorkbenchFormat.number(value, { digits: 3, trim: true });
  const savedText = value => value === null || value === undefined || value === '' ? '未记录' : String(value);
  const phaseText = window.RunDecisionProcessChart.phaseText;
  const stageStatuses = { completed: '已完成', skipped: '已跳过', failed: '失败' };
  const statusText = value => window.WorkbenchTerms.candidate_statuses[value] || savedText(value);
  function Elapsed({ value }) { return <span title={value === null ? undefined : String(value) + ' ms'}>{value === null ? '—' : value < 1000 ? number(value) + ' 毫秒' : number(value / 1000) + ' 秒'}</span>; }
  function Primary({ value, objective }) { return <span title={value === null ? undefined : String(value)}>{number(value)}{value !== null && objective.unit && ' ' + objective.unit}</span>; }
  function Completion({ value }) {
    const labels = { expected_operation_count: '本次参与计算工序', missing_operation_count: '本次计算范围内未安排工序', unexpected_result_count: '本次计算范围外结果', complete_batch_count: '本次计算范围内已排齐批次', incomplete_batch_count: '本次计算范围内未排齐批次' };
    return <><details className="rd-process-facts rd-process-completion"><summary>本次参与计算 {number(value.expected_operation_count)} 道工序{value.missing_operation_count > 0 && ' · 未安排 ' + number(value.missing_operation_count) + ' 道'}</summary>
      <dl>{Object.entries(labels).map(([key, label]) => <div key={key}><dt>{label}</dt><dd title={value[key] === null ? undefined : String(value[key])}>{number(value[key])}</dd></div>)}</dl></details>
      <small>本次计算范围内已排齐 {number(value.complete_batch_count)} 批{value.incomplete_batch_count > 0 && ' · 未排齐 ' + number(value.incomplete_batch_count) + ' 批'}{value.unexpected_result_count > 0 && ' · 范围外结果 ' + number(value.unexpected_result_count)}</small></>;
  }
  function Metrics({ values }) {
    return <details className="rd-process-facts"><summary>计算保存的最终统计</summary><dl>{Object.entries(metricLabels).map(([key, [label, unit]]) => <div key={key}><dt>{label}</dt><dd title={values[key] === null ? undefined : String(values[key])}>{number(values[key])}{values[key] !== null && ' ' + unit}</dd></div>)}</dl></details>;
  }
  function Score({ value, objective, fieldOrder = null }) {
    return <details className="rd-process-facts"><summary>计算评分 · {value.length} 项</summary><dl>{value.map((item, index) => {
      const definition = objective.score_fields.find(field => fieldOrder ? field.key === fieldOrder[index] : field.index === index);
      return <div key={index}><dt>{definition ? definition.label : '分量 ' + (index + 1)}</dt><dd title={item === null ? undefined : String(item)}>{number(item)}{item !== null && definition && definition.unit && ' ' + definition.unit}</dd></div>;
    })}</dl></details>;
  }
  function AttemptComparison({ row, objective }) {
    const comparison = row.comparison;
    if (comparison === null) return null;
    const labels = { failed_ops: ['未安排工序', '道'], ...metricLabels }, values = { failed_ops: row.failed_ops, ...row.metrics };
    const metric = (value, unit) => number(value) + (value !== null && unit ? ' ' + unit : '');
    const change = (value, unit) => value === null ? '—' : D.deltaText({ value, state: comparison.state }, { unit, precision: 3, source: 'saved_algorithm' });
    return <details className="rd-process-facts"><summary>当时比较与指标变化</summary><p>{comparisonLabels[comparison.kind]} · {comparisonStates[comparison.state]}</p>
      <p>本次评价：{window.RunDecisionProcessChart.scopeText(comparison.objective_scope)}；比较对象评价：{window.RunDecisionProcessChart.scopeText(comparison.reference_scope)}</p>
      <div className="wb-table-frame"><table className="wb-table rd-process-comparison-table" aria-label="尝试相对当时比较对象的保存变化"><thead><tr><th scope="col">指标</th><th scope="col">当时比较对象</th><th scope="col">本次尝试</th><th scope="col">变化</th></tr></thead><tbody>{Object.entries(labels).map(([key, [label, unit]]) => <tr key={key} data-attempt-comparison-metric={key}><th scope="row">{label}</th><td title={comparison.reference_metrics && comparison.reference_metrics[key] !== null ? String(comparison.reference_metrics[key]) : undefined}>{metric(comparison.reference_metrics ? comparison.reference_metrics[key] : null, unit)}</td><td title={values[key] === null ? undefined : String(values[key])}>{metric(values[key], unit)}</td><td title={comparison.metric_deltas && comparison.metric_deltas[key] !== null ? String(comparison.metric_deltas[key]) : undefined}>{change(comparison.metric_deltas ? comparison.metric_deltas[key] : null, unit)}</td></tr>)}</tbody></table></div>
      {comparison.reference_completion && <div>当时比较对象的工序安排：<Completion value={comparison.reference_completion} /></div>}{comparison.reference_score && <Score value={comparison.reference_score} objective={objective} />}
      <window.WorkbenchReference entries={{ '比较对象类型': comparison.kind, '比较状态': comparison.state, '计算目标': comparison.objective_name }} />
    </details>;
  }
  function CandidateTable({ data, overview, anchorRef, onAnchor }) {
    if (data.process_version === unifiedVersion) return <UnifiedCandidates data={data} overview={overview} anchorRef={anchorRef} onAnchor={onAnchor} />;
    return <div className="rc-table wb-table-frame rd-process-candidate-frame" data-sticky-head data-sticky-key data-sticky-actions data-wb-scroll-key="decision-process-candidates"><table className="wb-table rd-process-candidate-table" aria-label="本次全部候选计算来源与结果"><caption className="wb-visually-hidden">本次全部候选的计算元数据与算法保存统计</caption>
      <thead><tr><th scope="col" className="wb-col-key">候选 / 角色</th><th scope="col">计算来源</th><th scope="col">计算耗时 / 停止原因</th><th scope="col">本次计算结果</th><th scope="col" className="wb-col-actions">查看过程</th></tr></thead><tbody>{data.candidates.map(candidate => {
        const owner = data.candidates.find(row => row.candidate_ref === candidate.source_candidate_ref), roles = [];
        if (candidate.candidate_ref === overview.recommendation.candidate_ref) roles.push('计算时推荐');
        if (candidate.candidate_ref === overview.scope.selected_candidate_ref) roles.push('当前方案');
        if (candidate.candidate_ref === overview.scope.reference.candidate_ref) roles.push('当前比较基准');
        return <tr key={candidate.candidate_ref} data-process-candidate={candidate.candidate_ref} data-selected={candidate.candidate_ref === anchorRef || undefined}>
          <td className="wb-col-key"><strong>{candidate.label || '候选名称未填写'}</strong><small>{statusText(candidate.status)}{roles.length > 0 && ' · ' + roles.join(' · ')}</small></td>
          <td><span>{sourceLabels[candidate.source_kind]}{candidate.source_kind === 'reused' && ' · ' + (owner ? owner.label || '来源名称未填写' : '来源候选未记录')}</span>
            <details className="rd-process-facts"><summary>算法与派工记录</summary><dl><div><dt>算法</dt><dd>{savedText(candidate.algo_mode)}</dd></div><div><dt>策略</dt><dd>{savedText(candidate.used_strategy)}</dd></div><div><dt>搜索配置</dt><dd>{savedText(candidate.algorithm_profile)}</dd></div><div><dt>派工模式</dt><dd>{savedText(candidate.dispatch_mode)}</dd></div><div><dt>配置规则</dt><dd>{savedText(candidate.configured_dispatch_rule)}</dd></div><div><dt>实际规则</dt><dd>{savedText(candidate.adopted_dispatch_rule)}</dd></div></dl></details>
            <window.WorkbenchReference entries={{ '当前候选': candidate.candidate_ref, '求解来源候选': candidate.source_candidate_ref }} /></td>
          <td><span>本候选 <Elapsed value={candidate.own_elapsed_ms} /></span><small>来源求解 <Elapsed value={candidate.source_solver_elapsed_ms} /></small><small>{candidate.stop_reason ? candidate.stop_reason.message : '停止原因未记录'}</small></td>
          <td><Completion value={candidate.completion} /><Metrics values={candidate.final_metrics} /></td>
          <td className="wb-col-actions"><C.Button className="btn link" disabled={!onAnchor || !overview.candidates.some(row => row.candidate_ref === candidate.candidate_ref)} aria-pressed={candidate.candidate_ref === anchorRef} onClick={() => onAnchor(candidate.candidate_ref)}>{candidate.candidate_ref === anchorRef ? '当前方案' : '查看此候选'}</C.Button></td>
        </tr>;
      })}</tbody></table></div>;
  }
  function Coverage({ data }) {
    if (data.process_version === unifiedVersion) {
      const sampling = data.progress.sampling;
      return <div className="rd-process-coverage"><span>当前方向保留 {number(data.progress.points.length)} 个点 · 原进展 {number(sampling.event_total_count)} 个事件</span>
        <details className="rd-process-facts"><summary>进展记录说明</summary><p>按计算耗时分段保留最好结果，并保留关键首尾记录；最多保留 {sampling.point_budget} 个点。</p>
          <p>评价范围变化时分段显示；评分缺项保留未知值。</p><window.WorkbenchReference entries={{ '保存方式': sampling.policy }} /></details></div>;
    }
    const summary = data.summary, sampling = summary.sampling, endpoints = data.progress.coverage.endpoint_coverage;
    const reasons = [data.source.reason, summary.coverage.reason, data.progress.coverage.reason].filter(Boolean);
    const uniqueReasons = reasons.filter((reason, index) => reasons.findIndex(item => item.code === reason.code && item.message === reason.message) === index);
    const flag = value => value === null ? '未记录' : value ? '已覆盖' : '未覆盖';
    return <div className="rd-process-coverage">
      <span>已保存代表尝试 {number(summary.saved_attempt_count)} 条 · 进展事件 {number(sampling.event_total_count)} 个 · 图表显示 {number(summary.retained_point_count)} 个点</span>
      <details className="rd-process-facts"><summary>进展记录说明</summary><p>{sampling.policy === 'elapsed_equal_width_bucket_end_best_v1' ? '按计算耗时分段保留最好结果，并保留关键首尾记录。' : sampling.policy === 'legacy_saved_events' ? '按旧记录中保存的结果显示。' : sampling.policy === 'not_applicable' ? '这个候选没有独立计算过程。' : '记录方式未保存。'}</p>
        <p>首次有效：{flag(endpoints.first_valid)} · 本次计算范围首次排齐：{flag(endpoints.first_expected_complete)} · 最终记录：{flag(endpoints.final)}</p>
        <dl><div><dt>图表最多保留</dt><dd>{sampling.point_budget} 点</dd></div>{sampling.bucket_count !== null && <div><dt>时间分段数</dt><dd>{sampling.bucket_count}</dd></div>}{sampling.bucket_width_ms !== null && <div><dt>每段时长</dt><dd>{number(sampling.bucket_width_ms / 1000)} 秒</dd></div>}</dl><window.WorkbenchReference entries={{ '保存方式': sampling.policy }} /></details>
      {uniqueReasons.map(reason => <small key={reason.code + ':' + reason.message}>{reason.message}</small>)}
    </div>;
  }
  function Counts({ summary }) {
    return <details className="rd-process-facts"><summary>计算统计</summary>{summary.legacy_best_updates !== null && <p>旧记录更新结果 {number(summary.legacy_best_updates)} 次（含同分），评分改善次数未记录。</p>}<div className="wb-table-frame"><table className="wb-table rd-process-count-table" aria-label="本候选与来源计算次数"><thead><tr><th scope="col">记录项</th><th scope="col">本候选</th><th scope="col">来源计算</th></tr></thead><tbody>{countLabels.map(([key, label]) => <tr key={key}><th scope="row">{label}</th><td>{number(summary.own_counts[key])}</td><td>{number(summary.solver_counts[key])}</td></tr>)}</tbody></table></div></details>;
  }
  function Rejections({ values }) {
    const entries = values ? Object.entries(values) : null;
    return <details className="rd-process-facts"><summary>搜索拒绝原因{entries !== null && entries.length > 0 && ' · ' + entries.length + ' 类'}</summary>{entries === null ? <p className="rc-muted">拒绝原因未保存。</p> : entries.length ? <dl>{entries.map(([code, count]) => <div key={code}><dt>{rejectionLabels[code] || code}</dt><dd>{number(count)} 次<window.WorkbenchReference entries={{ '保存原因码': code }} /></dd></div>)}</dl> : <p className="rc-muted">没有记录到拒绝原因。</p>}</details>;
  }
  function Stages({ values }) {
    return <details className="rd-process-stages"><summary>搜索阶段 · {values.length} 项</summary>{values.length ? <div className="rc-table wb-table-frame rd-process-frame" data-sticky-head data-wb-scroll-key="decision-process-stages"><table className="wb-table rd-process-stage-table" aria-label="保存的搜索阶段汇总"><caption className="wb-visually-hidden">每阶段实际起止、计数与停止事实</caption>
      <thead><tr>{['阶段 / 状态', '实际开始 / 结束', '耗时 / 进入次数', '评估 / 搜索保留 / 评分改善 / 拒绝', '停止原因'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{values.map((stage, index) => <tr key={stage.phase + ':' + index} data-process-phase={stage.phase}><td><strong>{phaseText(stage.phase)}</strong><small>{stageStatuses[stage.status] || savedText(stage.status)}</small></td>
        <td><Elapsed value={stage.start_elapsed_ms} /><small>至 <Elapsed value={stage.end_elapsed_ms} /></small></td><td><Elapsed value={stage.elapsed_ms} /><small>进入 {number(stage.visits)} 次</small></td><td>{number(stage.evaluated)} / {number(stage.accepted)} / {number(stage.strict_improvements)} / {number(stage.rejected)}</td><td>{stopLabels[stage.stop_reason] || (stage.stop_reason === null ? '停止原因未记录' : '其他停止原因')}<window.WorkbenchReference entries={{ '搜索阶段': stage.phase, '停止原因': stage.stop_reason }} /></td></tr>)}</tbody>
    </table></div> : <p className="rc-muted">保存资料没有阶段起止记录。</p>}</details>;
  }
  function Records({ data }) {
    if (data.process_version === unifiedVersion) return <UnifiedRecords data={data} />;
    const progress = data.filters.record_kind === 'progress', objective = data.objective;
    const fields = progress ? [['elapsed_ms', '累计计算耗时'], ['primary_value', '主目标值'], ['verified', '核验状态']] : [['event_index', '计算事件'], ['elapsed_ms', '累计计算耗时'], ['primary_value', '主目标值'], ['accepted', '搜索保留情况'], ['verified', '核验状态'], ['strict_improved', '评分改善判断'], ['comparison', '当时比较资料']];
    const missing = fields.filter(([key]) => data.items.some(row => row[key] === null)).map(([, label]) => label);
    return <>{missing.length > 0 && <p className="rc-muted" data-process-missing role="status">本页部分保存记录缺少：{missing.join('、')}。未记录的数值与状态显示 —。</p>}
      <div className="rc-table wb-table-frame rd-process-frame" data-sticky-head data-wb-scroll-key="decision-process-records"><table className={'wb-table rd-process-record-table ' + (progress ? 'rd-process-point-table' : 'rd-process-attempt-table')} aria-label={progress ? '进步曲线数值等价表' : '已保存的代表尝试'}><caption className="wb-visually-hidden">{progress ? '保存曲线点与图表使用同一值' : '保存的代表搜索尝试，按当前条件排序'}</caption>
      <thead><tr>{(progress ? ['事件 / 阶段', '累计计算耗时', objective.primary_metric_label || '主目标未记录', '工序安排', '核验 / 计算详情'] : ['保存记录 / 排名', '尝试来源 / 策略', objective.primary_metric_label || '主目标未记录', '工序安排 / 累计耗时', '搜索结果 / 指标变化']).map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
      <tbody>{data.items.map(row => progress ? <tr key={row.event_index} data-process-point={row.event_index}>
        <td><strong>事件 {row.event_index}</strong><small>{phaseText(row.phase)}</small><details className="rd-process-facts"><summary>阶段记录</summary><p>第 {number(row.phase_visit)} 次 · 比较编号 {savedText(row.segment)}</p><window.WorkbenchReference entries={{ '搜索阶段': row.phase }} /></details></td>
        <td><Elapsed value={row.elapsed_ms} /></td><td><Primary value={row.primary_value} objective={objective} /><small>评价范围：{window.RunDecisionProcessChart.scopeText(row.objective_scope)}</small></td>
        <td><Completion value={row.completion} />{row.flags.length > 0 && <small>{row.flags.map(flag => flagLabels[flag] || flag).join(' · ')}</small>}</td><td>{row.verified === null ? '—' : row.verified ? '已核验' : '未核验'}<Score value={row.score} objective={objective} /></td>
      </tr> : <React.Fragment key={row.saved_index}><tr data-process-attempt={row.saved_index} data-process-attempt-event={row.event_index}>
        <td><strong>保存 {row.saved_index}</strong><small>代表排名 {number(row.rank)}</small><small>{row.event_index === null ? '—' : '计算事件 ' + row.event_index}</small></td>
        <td><span>{savedText(row.source_label)}</span><details className="rd-process-facts"><summary>策略记录</summary><dl><div><dt>权重配置</dt><dd>{savedText(row.weight_profile_slug)}</dd></div><div><dt>策略</dt><dd>{savedText(row.strategy)}</dd></div><div><dt>派工</dt><dd>{savedText(row.dispatch_mode)} · {savedText(row.dispatch_rule)}</dd></div><div><dt>结果</dt><dd>{statusText(row.candidate_status)}</dd></div></dl><window.WorkbenchReference entries={{ '保存的来源类型': row.candidate_origin }} /></details></td>
        <td><Primary value={row.primary_value} objective={objective} /><small>评价范围：{window.RunDecisionProcessChart.scopeText(row.objective_scope)}</small></td>
        <td><Completion value={row.completion} /><small>累计耗时 <Elapsed value={row.elapsed_ms} /></small>{(row.failed_ops === null || row.failed_ops > 0) && <small>未安排工序 {number(row.failed_ops)}</small>}</td>
        <td><span>{row.accepted === null ? '—' : row.accepted ? '已留作继续搜索' : '未留作继续搜索'}</span><small>{row.verified === null ? '—' : row.verified ? '已核验' : '未核验'}</small><small>{row.strict_improved === null ? '—' : row.strict_improved ? '优于当时比较对象' : '未优于当时比较对象'}</small><Score value={row.score} objective={objective} /></td>
      </tr>{row.comparison !== null && <tr data-process-attempt-comparison={row.saved_index}><td colSpan={5}><AttemptComparison row={row} objective={objective} /></td></tr>}</React.Fragment>)}</tbody>
    </table></div></>;
  }
  const unifiedCountLabels = [['actual_decoder_calls', '真实排法计算次数'], ['new_decisions', '新排法决策'], ['decision_reuses', '复用已核验决策'],
    ['skipped_requests', '跳过执行次数'], ['failed_decoder_calls', '计算失败次数'], ['request_count', '不同计算请求']];
  const opportunityLabels = { searched: '已探索', paused_no_gain: '已暂停暂无改善的探索', not_searched_budget: '本次预算内未探索此方向', not_applicable: '该方向当前不适用' };
  const skipLabels = { ...stopLabels, estimated_decode_cost: '剩余预算不足以执行下一次计算', waiting_for_parent: '等待可继续探索的排法', stagnation: '当前探索暂无进一步改善' };
  const objectiveLabel = (data, name) => { const descriptor = data.objectives.find(value => value.name === name); return descriptor ? descriptor.label : '方向未记录'; };
  function UnifiedScope({ scope, scopeRef }) {
    return <><span>{window.RunDecisionProcessChart.sharedScopeText(scope)}</span><window.WorkbenchReference entries={{ '评价范围编号': scopeRef }} /></>;
  }
  function UnifiedOrigin({ origin, data }) {
    return <><span>{phaseText(origin.phase)} · {objectiveLabel(data, origin.search_objective)}</span>
      <details className="rd-process-facts"><summary>实际生成与派工</summary><dl>{[['strategy', '生成策略'], ['dispatch_mode', '派工模式'], ['dispatch_rule', '派工规则']].map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{savedText(origin[key])}</dd></div>)}</dl>
        <window.WorkbenchReference entries={{ '来源类型': origin.origin, '搜索阶段': origin.phase, '搜索方向': origin.search_objective }} /></details></>;
  }
  function UnifiedCandidates({ data, overview, anchorRef, onAnchor }) {
    return <div className="rc-table wb-table-frame rd-process-candidate-frame" data-sticky-head data-sticky-key data-sticky-actions data-wb-scroll-key="decision-process-candidates"><table className="wb-table rd-process-source-table" aria-label="本次候选来源定位">
      <thead><tr>{['候选 / 业务方向', '首次发现', '实际生成来源', '来源定位'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{data.candidates.map(candidate => <tr key={candidate.candidate_ref} data-process-candidate={candidate.candidate_ref} data-selected={candidate.candidate_ref === anchorRef || undefined}>
        <td><strong>{candidate.label}</strong><small>{candidate.representative_objectives.map(name => objectiveLabel(data, name)).join(' · ')}</small>{candidate.candidate_ref === overview.recommendation.candidate_ref && <small>推荐</small>}</td>
        <td>首次发现于 <Elapsed value={candidate.first_found_elapsed_ms} /></td><td><UnifiedOrigin origin={candidate.origin} data={data} /></td>
        <td><C.Button className="btn link" disabled={!onAnchor} aria-pressed={candidate.candidate_ref === anchorRef} onClick={() => onAnchor(candidate.candidate_ref)}>{candidate.candidate_ref === anchorRef ? '当前来源' : '定位来源'}</C.Button></td>
      </tr>)}</tbody></table></div>;
  }
  function UnifiedSummary({ data }) {
    const direction = data.budget.objectives[data.selected_objective.name];
    return <><div className="rd-process-heading"><h3>共同优化过程</h3></div><dl className="rd-process-run-summary" aria-label="本次共同优化统计">
      <div><dt>总计算用时</dt><dd><Elapsed value={data.summary.elapsed_ms} /></dd></div><div><dt>首个完整解</dt><dd>{data.summary.first_complete_elapsed_ms === null ? '本次未产生完整解' : <Elapsed value={data.summary.first_complete_elapsed_ms} />}</dd></div>
      <div data-process-first-improvement-ms={data.summary.first_improvement_elapsed_ms}><dt>当前方向首次评分改善</dt><dd>{data.summary.first_improvement_elapsed_ms === null ? '本方向未发生评分改善' : <Elapsed value={data.summary.first_improvement_elapsed_ms} />}</dd></div>
      <div><dt>总计算预算</dt><dd>{number(data.budget.configured_seconds)} 秒</dd></div>{unifiedCountLabels.map(([key, label]) => <div key={key} data-unified-count={key}><dt>{label}</dt><dd>{number(data.counts[key])}</dd></div>)}</dl>
      <p className="rd-process-chart-note">{skipLabels[data.stop_reason] || '停止原因已保存'}<window.WorkbenchReference entries={{ '停止原因': data.stop_reason }} /></p>
      <p className="rd-process-chart-note" data-process-opportunity={direction.objective_status}>{opportunityLabels[direction.objective_status]}{direction.budget_reason && <small>{skipLabels[direction.budget_reason] || '预算原因已保存'}</small>}</p>
    </>;
  }
  function UnifiedRecords({ data }) {
    const progress = data.filters.record_kind === 'progress', objective = data.selected_objective;
    return <div className="rc-table wb-table-frame rd-process-frame" data-sticky-head data-wb-scroll-key="decision-process-records"><table className={'wb-table rd-process-record-table ' + (progress ? 'rd-process-point-table' : 'rd-process-action-table')} aria-label={progress ? '进步曲线数值等价表' : '保存的搜索动作'}>
      <thead><tr>{(progress ? ['来源事件 / 阶段', '累计计算耗时', objective.primary_metric_label, '评价范围', '核验 / 评分'] : ['动作 / 阶段', '实际起止 / 耗时', '评估 / 已核验', '新决策 / 复用', '实际结果']).map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
      <tbody>{data.items.map((row, index) => progress ? <tr key={row.source_event_id + ':' + row.elapsed_ms + ':' + index} data-process-point={row.source_event_id}>
        <td><strong>来源事件 {row.source_event_id}</strong><small>{phaseText(row.phase)}</small>{row.flags.length > 0 && <small>{row.flags.map(flag => flagLabels[flag] || flag).join(' · ')}</small>}</td>
        <td><Elapsed value={row.elapsed_ms} /></td><td><Primary value={row.primary_value} objective={objective} /></td><td><UnifiedScope scope={data.scopes[row.scope_ref]} scopeRef={row.scope_ref} /></td>
        <td>{row.verified ? '已核验' : '未核验'}<Score value={row.score} objective={objective} fieldOrder={row.field_order} /></td>
      </tr> : <tr key={row.action_id} data-process-action={row.action_id}>
        <td><strong>动作 {row.action_id}</strong><small>{phaseText(row.phase)}</small>{row.initial_construction && <small>构建起始排法</small>}</td>
        <td><Elapsed value={row.started_elapsed_ms} /><small>至 <Elapsed value={row.finished_elapsed_ms} /></small><small>动作耗时 <Elapsed value={row.elapsed_ms} /></small></td>
        <td>{number(row.evaluation_count)} / {number(row.verified_evaluation_count)}</td><td>{number(row.new_decisions)} / {number(row.reused_decisions)}</td>
        <td>{row.skip_reason ? skipLabels[row.skip_reason] || '动作未执行' : row.improved_objectives.length ? '改善：' + row.improved_objectives.map(name => objectiveLabel(data, name)).join(' · ') : '本动作未带来评分改善'}{row.skip_reason && <window.WorkbenchReference entries={{ '动作未执行原因': row.skip_reason }} />}</td>
      </tr>)}</tbody></table></div>;
  }
  function UnifiedStages({ values }) {
    return <details className="rd-process-stages"><summary>当前方向阶段 · {values.length} 项</summary><div className="rc-table wb-table-frame rd-process-frame" data-sticky-head data-wb-scroll-key="decision-process-stages"><table className="wb-table rd-process-stage-table" aria-label="共同优化方向的阶段事实">
      <thead><tr>{['阶段', '实际开始 / 结束', '耗时 / 动作数', '评估 / 已核验', '新决策 / 复用'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{values.map(stage => <tr key={stage.phase} data-process-phase={stage.phase}>
        <td>{phaseText(stage.phase)}</td><td><Elapsed value={stage.start_elapsed_ms} /><small>至 <Elapsed value={stage.end_elapsed_ms} /></small></td><td><Elapsed value={stage.elapsed_ms} /><small>{number(stage.action_count)} 个动作</small></td><td>{number(stage.evaluation_count)} / {number(stage.verified_evaluation_count)}</td><td>{number(stage.new_decisions)} / {number(stage.reused_decisions)}</td>
      </tr>)}</tbody></table></div></details>;
  }
  function UnifiedSource({ data }) {
    const source = data.source_event, candidate = data.candidate;
    return <details className="rd-process-facts"><summary>当前候选来源与方向记录</summary><p>{candidate.label} · 首次发现于 <Elapsed value={candidate.first_found_elapsed_ms} /></p><UnifiedOrigin origin={candidate.origin} data={data} />
      <window.WorkbenchReference entries={{ '来源候选': candidate.candidate_ref, '来源事件': source && source.event_id, '排产记录': data.run_ref }} />
      {source && <p>来源事件 {source.event_id} · 保存于 <Elapsed value={source.elapsed_ms} /> · {source.verified ? '已核验' : '未核验'}</p>}
      <h4>各方向实际探索</h4><dl>{data.objectives.map(descriptor => { const goal = data.budget.objectives[descriptor.name]; return <div key={descriptor.name}><dt>{descriptor.label}</dt><dd>{opportunityLabels[goal.objective_status]} · {number(goal.action_count)} 个动作</dd></div>; })}</dl>
      {data.bridges.length > 0 && <details className="rd-process-facts"><summary>参考排法接续 · {data.bridges.length} 项</summary><div className="wb-table-frame"><table className="wb-table rd-process-bridge-table" aria-label="保存的参考排法接续"><thead><tr>{['方向 / 阶段', '实际起止', '接续耗时', '原排法 / 计算事实'].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{data.bridges.map(bridge => <tr key={bridge.source_event_id}>
        <td>{objectiveLabel(data, bridge.search_objective)}<small>{phaseText(bridge.phase)}</small></td><td><Elapsed value={bridge.started_elapsed_ms} /><small>至 <Elapsed value={bridge.finished_elapsed_ms} /></small></td><td><Elapsed value={bridge.elapsed_ms} /></td>
        <td>{bridge.same_arrangement === null ? '原排法对应关系未记录' : bridge.same_arrangement ? '保留同一排法' : '取得另一排法'}<small>{bridge.decoder_executed ? '实际执行计算' : '未执行计算'}</small><window.WorkbenchReference entries={{ '来源事件': bridge.source_event_id, '接续前排法': bridge.before_entry_id, '接续后排法': bridge.after_entry_id, '参考方式': bridge.reference_kind }} /></td>
      </tr>)}</tbody></table></div></details>}
    </details>;
  }
  function Pane({ adapter, result, query = {}, onQuery, onSelectCandidate, enabled = false }) {
    const overview = result.data, scope = overview.scope, runRef = overview.run.run_ref;
    const unified = !!overview.selection_basis && overview.selection_basis.generation_policy_version === 'unified_search_v1';
    const stored = Object.fromEntries(Object.entries(query).filter(([key]) => queryKeys.includes(key)));
    if (!unified) {
      if (stored.process_candidate_ref && stored.process_candidate_ref !== scope.selected_candidate_ref) { stored.page = 1; delete stored.snapshot_ref; }
      delete stored.process_candidate_ref; delete stored.objective;
    }
    const shared = { comparison_mode: scope.comparison_mode, resource_view: scope.resource_view, selected_candidate_ref: scope.selected_candidate_ref, range_start: scope.range_start, range_end: scope.range_end,
      ...(scope.comparison_mode === 'candidates' ? { reference_candidate_ref: scope.reference.candidate_ref } : {}) };
    const q = window.RunDecisionAPI.processScope(runRef, { ...stored, ...shared, process_candidate_ref: (unified && stored.process_candidate_ref || scope.selected_candidate_ref) || undefined }), key = JSON.stringify(q);
    const [paused, setPaused] = React.useState(false);
    React.useEffect(() => { setPaused(false); }, [runRef, key, result.meta.snapshot_ref]);
    const read = window.APSResourceSession.useQuery(signal => adapter.process(runRef, q, signal), [adapter, runRef, key, result.meta.snapshot_ref], enabled && !paused);
    const detail = read.result && (!q.process_candidate_ref || read.result.data.candidate.candidate_ref === q.process_candidate_ref) ? read.result : null, data = detail && detail.data;
    function update(change, paging = false) {
      const next = { ...q, ...change, page: paging ? change.page : 1 }; delete next.snapshot_ref;
      if (!unified) delete next.process_candidate_ref;
      else if (data && !next.objective) next.objective = data.selected_objective.name;
      if (paging && detail) next.snapshot_ref = detail.meta.snapshot_ref;
      setPaused(false); onQuery(Object.fromEntries(Object.entries(next).filter(([name]) => queryKeys.includes(name))));
    }
    function recordKind(value) { update({ record_kind: value, sort: value === 'progress' ? 'elapsed_ms' : 'rank' }); }
    function selectCandidate(candidateRef) { const candidate = overview.candidates.find(row => row.candidate_ref === candidateRef); if (!candidate) return;
      if (unified) update({ process_candidate_ref: candidateRef });
      else if (onSelectCandidate) { setPaused(false); onSelectCandidate(candidate); } }
    function reload() { update({}); read.reload(); }
    if (!enabled) return null;
    const sorts = q.record_kind === 'progress' ? [['elapsed_ms', '累计耗时'], ['event_index', '保存事件顺序'], ['primary_value', '主目标值']] : unified ? [['rank', '动作顺序'], ['elapsed_ms', '动作耗时']] : [['rank', '代表排名'], ['elapsed_ms', '尝试耗时'], ['primary_value', '主目标值']];
    const profileEntries = data && !unified ? Object.entries(data.source.profile) : null;
    return <section className="rd-process" aria-label="候选优化过程" data-process-anchor={data ? data.candidate.candidate_ref : q.process_candidate_ref}>
      <div className="rd-detail-filters rd-process-actions">
        <div className="rc-tools rd-detail-actions">{data && <D.Export key={detail.meta.snapshot_ref} adapter={adapter} result={detail} initialSection="process" filterQuery={{ ...q, process_candidate_ref: data.candidate.candidate_ref }} />}<C.Button icon="refresh-cw" aria-label="刷新优化过程" disabled={read.loading} onClick={reload} /></div>
      </div>
      <C.ErrorBox error={read.error} />{read.loading && <div className="rc-tools"><span role="status">正在读取保存的优化过程。</span><C.Button icon="x" onClick={() => setPaused(true)}>取消读取</C.Button></div>}{paused && <p className="rc-muted" role="status">过程读取已取消，点击刷新继续。</p>}
      {data && <>{unified ? <UnifiedSummary data={data} /> : <div className="rd-process-heading"><div><h3>计算进展</h3><span>本轮目标：{data.objective.label || '计算目标未记录'} · 来源计算 <Elapsed value={data.summary.source_solver_elapsed_ms} />{data.summary.solver_counts.evaluated !== null && ' · 已评估 ' + number(data.summary.solver_counts.evaluated) + ' 次'}</span></div></div>}
        <C.Reasons rows={detail.warnings} />
        {unified && <div className="rd-process-objective"><label>优化方向<select aria-label="优化方向" value={data.selected_objective.name} onChange={event => update({ objective: event.target.value })}>{data.objectives.map(descriptor => <option key={descriptor.name} value={descriptor.name}>{descriptor.label}</option>)}</select></label></div>}
        {!unified && data.source.kind === 'reused' && <p className="rd-process-chart-note">此方案沿用 {(overview.candidates.find(row => row.candidate_ref === data.source.source_candidate_ref) || data.candidates.find(row => row.candidate_ref === data.source.source_candidate_ref) || {}).label || '已保存方案'} 的计算结果。</p>}
        <window.RunDecisionProcessChart.Chart key={unified ? data.selected_objective.name : undefined} progress={data.progress} objective={unified ? data.selected_objective : data.objective}
          elapsedMs={unified ? data.summary.elapsed_ms : data.summary.source_solver_elapsed_ms} attempts={unified ? undefined : data.attempts}
          scopes={unified ? data.scopes : null} sourceEventId={unified && data.source_event ? data.source_event.event_id : null}
          {...(unified ? { lastImprovementElapsedMs: data.summary.last_improvement_elapsed_ms } : {})} />
        <Coverage data={data} />
        <details className="rd-process-records"><summary>计算明细</summary><div className="rd-process-record-tools"><div className="rc-tabs" role="group" aria-label="优化过程记录视图">{[['attempts', unified ? '搜索动作' : '已保存代表尝试'], ['progress', '曲线数据']].map(([value, label]) => <C.Button key={value} aria-pressed={q.record_kind === value} onClick={() => recordKind(value)}>{label}</C.Button>)}</div>
          <label>排序<select aria-label="优化过程排序" value={q.sort} onChange={event => update({ sort: event.target.value })}>{sorts.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>顺序<select aria-label="优化过程顺序" value={q.order} onChange={event => update({ order: event.target.value })}><option value="asc">升序</option><option value="desc">降序</option></select></label>
          </div>
        {data.items.length ? <Records data={data} /> : <p className="rc-empty">{unified ? '这个方向没有保存当前类别的过程记录。' : '这个候选没有保存当前类别的过程记录。'}</p>}
        <div className="rc-heading rd-detail-pages"><span className="rc-muted">当前类别 {data.page.total} 条 · 本页 {data.items.length} 条</span><div className="rc-tools"><label>每页<select aria-label="优化过程每页条数" value={q.size} onChange={event => update({ size: Number(event.target.value) })}><option value="20">20 条</option><option value="50">50 条</option></select></label><C.Pager label="优化过程记录" page={data.page.number} pages={Math.max(1, Math.ceil(data.page.total / data.page.size))} disabled={read.loading} onPage={page => update({ page }, true)} /></div></div>
        <details className="rd-process-catalog"><summary>{unified ? '全部候选的来源定位' : '全部候选的计算来源与结果'} · {data.candidates.length} 项</summary><CandidateTable data={data} overview={overview} anchorRef={data.candidate.candidate_ref} onAnchor={unified || onSelectCandidate ? selectCandidate : undefined} /></details>
        {unified ? <><UnifiedStages values={data.stages} /><UnifiedSource data={data} /></> : <><Stages values={data.stages} /><Counts summary={data.summary} /><Rejections values={data.summary.rejection_summary} />
        <details className="rd-process-facts"><summary>计算来源与配置</summary><div className="rd-process-identity"><span>{sourceLabels[data.source.kind]} · 本候选 <Elapsed value={data.summary.own_elapsed_ms} /> · 来源计算 <Elapsed value={data.summary.source_solver_elapsed_ms} /></span><span>{data.summary.stop_reason ? data.summary.stop_reason.message : '停止原因未记录'}</span><window.WorkbenchReference entries={{ '过程查看候选': data.candidate.candidate_ref, '计算来源候选': data.source.source_candidate_ref, '排产记录': data.run_ref }} /></div>{profileEntries.length ? <dl>{profileEntries.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value === null ? '未记录' : typeof value === 'object' ? JSON.stringify(value) : typeof value === 'boolean' ? value ? '是' : '否' : String(value)}</dd></div>)}</dl> : <p className="rc-muted">没有保存搜索配置。</p>}</details></>}
        </details>
      </>}
    </section>;
  }
  window.RunDecisionProcess = { Pane, CandidateTable, Coverage, Counts, Rejections, Stages, Records, Completion, Score, AttemptComparison, Elapsed, Primary,
    UnifiedSummary, UnifiedRecords, UnifiedCandidates, UnifiedStages, UnifiedSource, UnifiedScope };
})();
