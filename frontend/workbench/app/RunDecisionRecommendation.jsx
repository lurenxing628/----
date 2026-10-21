(function () {
  'use strict';
  const C = window.RunCandidateControls, T = window.WorkbenchTerms;
  const titles = { complete: '推荐方案', schedulable_scope: '推荐方案', partial: '推荐的部分安排' };
  const supports = { batch: '查看批次', operation: '查看工序', preparation: '查看准备', changeover: '查看切换' };
  const states = { comparable: '可比较', different_coverage: '比较范围不同', unavailable: '资料待确认', not_applicable: '本范围不适用' };
  const countText = value => value === null ? '未记录' : window.RunCandidateModel.number(value);
  function amount(value, item) {
    if (value === null) return item.state === 'not_applicable' ? states.not_applicable : '资料待确认';
    return item.unit === '%' ? window.WorkbenchFormat.percent(value)
      : window.WorkbenchFormat.number(value, { digits: item.precision, trim: true }) + (item.unit ? ' ' + item.unit : '');
  }
  function difference(item) {
    return item.state === 'not_applicable' ? states.not_applicable : window.RunDecisionComparison.deltaText(item, item);
  }
  function Support({ targets, onSupport, compact = false }) {
    return onSupport && targets.length ? <span className="rd-supports">{(compact ? targets.slice(0, 1) : targets).map((target, index) => {
      const resourceKind = target.drill.detail_query && target.drill.detail_query.resource_kind || target.drill.resource_kind;
      const action = target.kind === 'resource' ? resourceKind === 'machine' ? '查看设备' : resourceKind === 'operator' ? '查看人员' : '查看明细' : supports[target.kind] || '查看明细';
      const label = (target.side === 'reference' ? '当前基准 · ' : '') + action;
      return <C.Button key={index} icon="search" className="btn link" aria-label={label} title={target.label || label} onClick={() => onSupport(target)}>{compact && target.side === 'reference' ? '查看基准' : compact ? action : label}</C.Button>;
    })}</span> : null;
  }
  function TradeoffItems({ items, onSupport }) {
    return <ul>{items.map(item => <li key={item.metric_key} data-recommendation-metric={item.metric_key}>
      <span><strong>{item.label}</strong><span className={'rd-change rd-' + item.direction}>{difference(item)}</span></span>
      <Support targets={item.supporting_refs} onSupport={onSupport} compact /></li>)}</ul>;
  }
  function Differences({ items, onSupport }) {
    const reasons = Array.from(new Set(items.filter(item => item.reason).map(item => item.reason.message)));
    return <div className="wb-table-frame"><table className="wb-table rd-recommend-differences" aria-label="推荐方案全部差值与明细">
      <thead><tr><th scope="col">指标与解释</th><th scope="col">当前基准</th><th scope="col">推荐方案</th><th scope="col">差值 / 状态</th><th scope="col">查看明细</th></tr></thead>
      <tbody>{items.map(item => {
        const reasonNumber = item.reason ? reasons.indexOf(item.reason.message) + 1 : 0;
        return <tr key={item.metric_key} data-recommendation-difference={item.metric_key}><th scope="row"><strong>{item.label}</strong><small title={item.text} aria-describedby={item.reason ? 'rd-recommend-reason-' + reasonNumber : undefined}>{item.reason && item.text === item.label + '：' + item.reason.message ? states[item.state] : item.text}{item.reason && '（说明 ' + reasonNumber + '）'}</small></th>
        <td>{amount(item.reference_value, item)}</td><td>{amount(item.selected_value, item)}</td><td><span className={'rd-change rd-' + item.direction}>{difference(item)}</span><small>{states[item.state]}</small></td>
        <td><Support targets={item.supporting_refs} onSupport={onSupport} /></td></tr>; })}</tbody>
    </table>{reasons.map((message, index) => <p className="rc-muted" key={message} id={'rd-recommend-reason-' + (index + 1)}>说明 {index + 1}：{message}</p>)}</div>;
  }
  function SelectionEvidence({ basis, data }) {
    const name = reference => { const row = data.candidates.find(candidate => candidate.candidate_ref === reference); return row ? row.label || '候选名称未填写' : '资料未记录'; };
    const unified = window.RunGenerationContract.unified(basis), G = window.RunGenerationContract;
    return <><h4>{unified ? '共同优化的推荐规则与数值' : '排产时的推荐规则与数值'}</h4><dl className="rd-selection-facts">
      {unified ? <>
        <div><dt>主目标</dt><dd>{G.objectiveLabel(basis.primary_objective)}</dd></div>
        <div><dt>本轮推荐</dt><dd>{name(basis.selected_candidate_ref)}<window.WorkbenchReference value={basis.selected_candidate_ref} label="候选永久编号" /></dd></div>
        {basis.target_objectives.map(objective => {
          const reference = basis.objective_winners[objective], reason = basis.objective_winner_reasons[objective];
          return <div key={objective} data-selection-objective={objective}><dt>{G.objectiveLabel(objective)}代表</dt><dd>{reference === null ? '本轮未保存该方向代表' : name(reference)}
            <window.WorkbenchReference label="方向代表记录" entries={{ '业务方向': objective, '候选永久编号': reference, '代表缺项说明': reason }} /></dd></div>;
        })}
        <div><dt>推荐评分范围</dt><dd><C.ScoringScope value={basis.scoring_scope} /></dd></div>
        <div><dt>选择记录</dt><dd>{basis.evidence_state === 'complete' ? '已保存完整评分依据' : '已保存部分评分依据'}<window.WorkbenchReference label="查看保存的选择依据" entries={{
          '生成策略版本': basis.generation_policy_version, '选择规则版本': basis.selection_policy_version,
          '选择原因': basis.reason_code, '主目标指标顺序': basis.objective_field_order[basis.primary_objective], '主目标保存评分': basis.selected_score
        }} /></dd></div>
      </> : <><div><dt>目标最优候选</dt><dd>{name(basis.raw_score_best_candidate_ref)}</dd></div><div><dt>健康比较原方案</dt><dd>{name(basis.health_reference_candidate_ref)}</dd></div></>}
      {basis.explanation.entries.map(entry => <div key={entry.key} data-selection-evidence={entry.key}>
      <dt>{entry.label}</dt><dd>{entry.text}<small className="rd-evidence-values">{[['reference_value', '参考值'], ['selected_value', '本项值'], ['value', '记录值'], ['limit', '采用上限'], ['tolerance', '采用容差']].filter(([key]) => entry[key] !== null).map(([key, label]) => {
        const unit = key === 'tolerance' ? entry.tolerance_unit : entry.unit, value = unit === '%' ? window.WorkbenchFormat.percent(entry[key]) : window.WorkbenchFormat.number(entry[key], { digits: 6, trim: true });
        return <span key={key} title={String(entry[key])}>{label} {value}{unit && unit !== '%' && ' ' + unit}</span>;
      })}</small></dd></div>)}</dl>
      {basis.explanation.issues.length > 0 && <div className="rc-notice"><strong>推荐理由缺少资料</strong><ul>{basis.explanation.issues.map(issue => <li key={issue.code}>{issue.message}</li>)}</ul></div>}</>;
  }
  function RemainingMetrics({ work, definitions, label, className = 'rd-remaining-work', completion = false }) {
    const metrics = definitions.filter(row => Object.prototype.hasOwnProperty.call(work.metrics, row.key));
    const reasons = Array.from(new Set(metrics.filter(row => work.metrics[row.key].reason).map(row => work.metrics[row.key].reason.message)));
    const Metric = window.RunDecisionComparison.Metric;
    return <><div className="wb-table-frame"><table className={'wb-table ' + className} aria-label={label}><thead><tr><th scope="col">剩余需求指标</th><th scope="col">保存值与缺项</th></tr></thead><tbody>{metrics.map(definition => <tr key={definition.key} {...(completion ? { 'data-completion-metric': definition.key } : {})}><th scope="row">{definition.label}</th><td><Metric metric={work.metrics[definition.key]} definition={definition} showReason={false} /></td></tr>)}</tbody></table></div>
      {reasons.map(message => <p className="rc-muted" key={message}>{message}</p>)}</>;
  }
  function CompletionEvidence({ scope, data, candidateRef, onSupport }) {
    return <><h4>工序安排与未安排工序</h4><dl className="rd-selection-facts">{[
      ['complete_batch_count', '工序已排齐', '批'], ['incomplete_batch_count', '工序未排齐', '批'],
      ['ordinary_incomplete_batch_count', '其他未排齐', '批'], ['deferred_batch_count', '仅因缺料未排齐', '批'],
      ['unknown_batch_count', '工序安排待确认', '批'], ['unplanned_operation_count', '其他未安排工序', '道'], ['deferred_operation_count', '缺料未安排工序', '道'],
    ].map(([key, label, unit]) => <div key={key}><dt>{label}</dt><dd>{countText(scope[key])} {unit}</dd></div>)}</dl>
      {scope.source_available && scope.remaining_work.operation_count > 0 && scope.drill && <Support targets={[{ kind: 'preparation', label: '查看未安排工序', ref: null, candidate_ref: candidateRef, drill: scope.drill }]} onSupport={onSupport} />}
      <RemainingMetrics work={scope.remaining_work} definitions={data.metric_definitions} label="推荐方案剩余准备与加工需求" /></>;
  }
  function Panel({ data, onSelect, onSupport, compact = false }) {
    const recommendation = data.recommendation, comparison = recommendation.current_comparison;
    const selected = data.candidates.find(row => row.candidate_ref === recommendation.candidate_ref), scope = recommendation.completion_scope;
    const completionSummary = scope ? T.completion_summary(scope) : '';
    const mainBenefit = comparison.benefits.find(item => item.value !== null && item.value !== 0), mainCost = comparison.costs.find(item => item.value !== null && item.value !== 0);
    const mainCause = (selected && data.selection_basis && data.selection_basis.explanation && data.selection_basis.explanation.headline) || recommendation.headline;
    const sameReference = comparison.reference.kind === 'candidate' && comparison.reference.candidate_ref === recommendation.candidate_ref;
    const supplement = data.scope.reference_state === 'available' && !sameReference ? [mainBenefit && mainBenefit.label + '，' + difference(mainBenefit), mainCost && mainCost.label + '，' + difference(mainCost)].filter(Boolean).join('；') : '';
    const tradeoffs = <div className="rd-tradeoffs" aria-label={'推荐方案相对' + (data.baseline.label || '当前查看基准')}>
      <h4 className="rd-tradeoffs-title">当前比较：推荐方案相对{data.baseline.label || '当前查看基准'}</h4>
      {[['benefits', '主要收益', 'better'], ['costs', '主要代价', 'worse']].map(([key, label, tone]) => <div className={'rd-tradeoff rd-' + tone} key={key}><span className="rd-tradeoff-heading">{label}</span>
        {comparison[key].length ? <TradeoffItems items={comparison[key]} onSupport={onSupport} /> : <p>{data.scope.reference_state === 'available' ? '暂无明确' + label.slice(2) : window.RunDecisionComparison.referenceNotice(data)}</p>}</div>)}
    </div>;
    return <section className={'rd-recommendation' + (compact ? ' rd-recommendation-compact' : '')} aria-label="推荐方案与推荐理由" data-recommendation-type={recommendation.recommendation_type}>
      <div className="rd-recommend-main"><div className="rd-recommend-heading"><h3>{selected ? (compact ? '本次建议：' : titles[recommendation.recommendation_type] + '：') + selected.label : '本次排产暂无推荐方案'}</h3>
        {selected && <C.Button icon="search" className="btn link" aria-label={'查看推荐方案：' + selected.label} onClick={() => onSelect(selected)}>{compact ? '查看方案' : '查看推荐方案'}</C.Button>}</div>
        {!compact && selected && completionSummary && <small className="rd-recommend-coverage">{completionSummary}</small>}
      </div>
      <p className="rd-recommend-cause">{mainCause}</p>{compact && supplement && <small className="rd-recommend-tradeoff">相对{data.baseline.label || '当前对照'}：{supplement}</small>}
      {!compact && tradeoffs}
      <details className="rd-recommend-evidence"><summary>{compact ? '推荐详情' : '查看推荐规则、全部差值与明细'}</summary>{compact && <>{selected && completionSummary && <p>{completionSummary}</p>}{tradeoffs}</>}<SelectionEvidence basis={data.selection_basis} data={data} />
        {scope && <CompletionEvidence scope={scope} data={data} candidateRef={recommendation.candidate_ref} onSupport={onSupport} />}
        <h4>推荐方案相对{data.baseline.label || '当前查看基准'}的全部差值</h4>{comparison.common_completed_delivery && <p>交付变化比较双方工序都已排齐的 {countText(comparison.common_completed_delivery.batch_count)} 批。</p>}
        <Differences items={comparison.all_differences} onSupport={onSupport} />
      </details>
    </section>;
  }
  window.RunDecisionRecommendation = { Panel, SelectionEvidence, CompletionEvidence, RemainingMetrics, titles, amount, difference, Support, TradeoffItems, Differences };
})();
