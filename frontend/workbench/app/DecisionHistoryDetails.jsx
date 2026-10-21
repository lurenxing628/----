(function () {
  'use strict';
  const A = window.DecisionHistoryAPI, C = window.RunHistoryControls, F = window.WorkbenchFormat;
  const savedSourceLabels = { run: '排产归档', trial: '试调归档', legacy: '旧正式摘要' };
  const stateLabels = { ...window.WorkbenchTerms.run_statuses, complete: '完整', partial: '部分资料', committed: '已正式采用', success: '成功',
    available: '可读取', current: '当前版本', historical: '历史版本', unavailable: '资料未保存', unknown: '待确认', not_applicable: '不适用' };
  const pairLabels = { equal: '相同', different: '有变化', unknown: '待确认' };
  const gateLabels = { comparable: '可按相同口径对照', different_conditions: '生产条件有变化', different_objective: '优化目标有变化',
    different_coverage: '统计范围或容量分母有变化', different_version: '指标版本或单位有变化', unavailable: '必要资料缺项' };
  const directionLabels = { better: '改善', worse: '变差', equal: '持平', neutral: '观测差值' };
  const timeBasisLabels = { accepted_at_factory_local: '排产受理时间（工厂本地）', adopted_at_factory_local: '采用时间（工厂本地）',
    committed_at_utc_to_factory_local: '回执提交时间（UTC 转工厂本地）', schedule_time_utc_to_factory_local: '旧记录时间（UTC 转工厂本地）' };
  const scopeLabels = { full_admission: '整次排产范围', full_candidate: '整份保存候选', saved_algorithm_batches: '保存算法批次',
    saved_schedule_resources: '保存安排的资源', candidate_search: '本候选搜索', fixed_resource_window: '固定资源窗口', fixed_changeover_window: '固定换型窗口',
    selected_batches: '选中批次范围', complete_trial: '整份保存试调', legacy_saved_algorithm_batches: '旧摘要算法批次',
    legacy_saved_schedule: '旧摘要保存安排', legacy_summary_counts: '旧摘要计数范围', legacy_completed_batches_only: '旧摘要已完成批次',
    legacy_input_to_summary: '旧记录受理至摘要', legacy_not_recorded: '旧摘要原范围' };
  const fieldLabels = { members: '成员集合', batch_refs: '选中批次', operation_refs: '工序成员', frozen_operation_refs: '不重排工序成员',
    start_date: '排产起日', end_date: '排产止日', ready_check: '齐套检查', material_strategy: '物料齐套规则', hold_window: '不重排时段',
    missing_resource_policy: '缺设备人员规则', completed_policy: '执行记录规则', quantity: '数量', due_date: '交期', priority: '优先级',
    ready_status: '齐套状态', ready_date: '齐套日期', status: '状态', piece_id: '分件编号', seq: '工序顺序', source: '安排类型',
    op_type_id: '工种', op_type_name: '工种名称', setup_hours: '准备定额', unit_hours: '单件加工定额', machine_id: '指定设备',
    operator_id: '指定人员', supplier_id: '外协供应商', ext_days: '外协周期', quantity_basis: '数量依据', target_quantity: '目标数量',
    remaining_quantity: '剩余数量', required_standard_hours: '应排标准工时', setup: '准备需求', processing: '加工需求',
    execution: '执行记录', baseline: '正式安排基准', locked: '保存的锁定标记', skills_declared: '技能登记状态', skills: '技能资格',
    machines: '设备集合', operators: '人员集合', suppliers: '供应商集合', qualifications: '资源资格', capacity: '容量',
    calendar: '工作日历', downtime: '停机时段', materials: '物料条件', arrivals: '到料记录', stages: '物料阶段',
    objective: '优化目标', objectives: '优化目标顺序', mode: '算法模式', rule: '排产规则', graph_weights: '图权重',
    budget: '计算预算', run_time_budget_seconds: '整轮计算预算（秒）', time_budget_seconds: '候选计算预算（秒）',
    batch_member: '所选批次成员', operation_member: '应排工序成员', part_no: '所属零件', sort_strategy: '排序策略',
    priority_weight: '优先级权重', due_weight: '交期权重', ready_weight: '齐套权重', prefer_primary_skill: '优先主技能',
    dispatch_mode: '工序派工方式', dispatch_rule: '工序派工规则', adopted_dispatch_rule: '实际采用派工规则', algo_mode: '算法模式',
    ortools_enabled: '启用约束求解', ortools_time_limit_seconds: '约束求解时限（秒）', graph_analysis_mode: '图分析方式',
    graph_block_on_cycle: '工艺循环拦截', graph_critical_weight: '关键路径权重', graph_impact_weight: '影响范围权重',
    graph_downstream_weight: '后续工序权重', graph_candidate_weight_count: '图分析候选数量', graph_selection_policy: '图分析选优策略',
    graph_overdue_tolerance_count: '超期批次数容差', graph_tardiness_tolerance_ratio: '总拖期比例容差', objective_name: '目标名称',
    generation_policy_version: '候选生成策略版本', selection_policy_version: '推荐选择策略版本', primary_objective: '主目标', target_objectives: '同时探索方向',
    algorithm_version: '算法版本', algorithm_profile: '算法配置', seed: '随机种子', profile: '搜索配置', enabled: '启用状态',
    seed_source: '随机种子来源', configured_time_budget_seconds: '配置计算预算（秒）', effective_time_budget_seconds: '实际计算预算（秒）',
    configured_max_iterations: '配置迭代上限', effective_max_iterations: '实际迭代上限', iteration_limit_source: '迭代上限来源',
    restart_after_iterations: '搜索重启间隔（轮次）', repair: '安排修复策略', acceptance: '改动接受策略', candidate_strategy_family: '候选策略组',
    ortools_warmstart_enabled: '约束求解热启动', strict_mode: '严格约束模式', neighborhoods: '实际搜索邻域',
    configured_neighborhoods: '配置搜索邻域', candidate_strategy_families: '候选策略组' };
  const plain = value => value === null ? '未记录' : typeof value === 'boolean' ? value ? '是' : '否' : String(value);
  const fieldLabel = row => row.entity.key === 'run_options' && row.field === 'time_budget_seconds' ? '总计算预算（秒）'
    : fieldLabels[row.field] || fieldLabels[row.field.split('.').pop().replace(/\[\d+\]$/, '')] || '保存的字段';
  const number = (value, unit = '', precision = 0) => value === null ? '未知' : A.numberText(value, unit, precision);
  const localTime = value => value === null ? '未记录' : F.dateTime(value, { seconds: true, fractions: true });
  function Reason({ value }) { return value ? <p className="dh-note">{value.message}</p> : null; }
  function Raw({ value }) { return <pre className="dh-saved-value">{JSON.stringify(value, null, 2)}</pre>; }
  function SavedSide({ value, field }) {
    const saved = value.value;
    const preview = saved === null ? '空值' : saved === false ? '否' : saved === true ? '是'
      : field === 'primary_objective' && typeof saved === 'string' ? window.RunGenerationContract.objectiveLabel(saved)
      : field === 'target_objectives' && Array.isArray(saved) && saved.length && saved.every(value => typeof value === 'string') ? saved.map(window.RunGenerationContract.objectiveLabel).join(' · ')
      : Array.isArray(saved) ? saved.length + ' 项' : typeof saved === 'object' ? '字段记录' : saved === '' ? '空文本' : String(saved);
    return <div data-history-saved-state={value.state} data-history-value-present={value.present}><span>{value.present ? preview : '未保存'}</span>{value.state !== 'known' && <Reason value={value.reason} />}</div>;
  }
  function Navigation({ entry, onOpen, canNavigate, busy }) {
    return <div className="dh-actions">{entry.navigation.map((target, index) => <div key={target.view + ':' + index}>
      <C.Button icon="arrow-right" disabled={busy || !canNavigate || !target.enabled} title={target.reason || undefined}
        onClick={() => onOpen(target)}>{target.label}</C.Button>{!target.enabled && target.reason && <p className="dh-note">{target.reason}</p>}
    </div>)}</div>;
  }
  function BatchQuantity({ value }) {
    return <span className="dh-quantity">批次原数量合计 {A.metricText(value, { precision: 0 })}{value.value === null && value.known_count > 0 && value.known_subtotal !== null && <small>已知小计 {A.numberText(value.known_subtotal, value.unit, 0)} · {value.unknown_count} 批待确认</small>}</span>;
  }
  function EntryIdentity({ entry, reference, onEndComparison, busy }) {
    return <div className="dh-selected-record"><div className="dh-detail-heading"><div><h3 data-history-detail-title tabIndex={-1}>{reference ? '记录对照' : entry.label}</h3>{!reference && <p className="dh-note">{A.sourceLabel(entry)} · {localTime(entry.occurred_at)} · {entry.source_kind === 'run' ? window.WorkbenchTerms.run_statuses[entry.state] || entry.state : stateLabels[entry.state] || entry.state}</p>}</div>
      <div className="dh-selected-scope">{number(entry.scope.batch_count, '批次')} · {number(entry.scope.operation_count, '工序')}<BatchQuantity value={entry.scope.batch_quantity} /></div></div>
      {reference && <div className="dh-comparison-pair"><span><small>当前记录</small><strong>{entry.label}</strong><span>{localTime(entry.occurred_at)} · {A.sourceLabel(entry)}</span></span><span><small>对照记录</small><strong>{reference.label}</strong><span>{localTime(reference.occurred_at)} · {A.sourceLabel(reference)}</span></span><C.Button disabled={busy} onClick={onEndComparison}>结束对照</C.Button></div>}
      {entry.source.reason && <Reason value={entry.source.reason} />}
    </div>;
  }
  function MetricValue({ value, definition }) {
    return <><strong className="dh-metric-value">{A.metricText(value, definition)}</strong>
      {value.value === null && value.known_count > 0 && value.known_subtotal !== null && <p className="dh-note">已知小计 {A.numberText(value.known_subtotal, value.unit, definition.precision)}</p>}
      {(!['full_admission', 'full_candidate', 'complete_trial'].includes(value.scope) || value.unknown_count > 0) && <p className="dh-metric-scope">{scopeLabels[value.scope] || '保存范围'}{value.unknown_count > 0 && ' · 另有 ' + value.unknown_count + ' 项待确认'}</p>}{value.value === null && <Reason value={value.reason} />}
    </>;
  }
  function MetricTable({ entry, reference, definitions, comparison, compare }) {
    return <div className="wb-table-frame dh-metric-table" tabIndex={0} aria-label="历史指标表格滚动区域"><table className="wb-table" aria-label="历史指标原值">
      <caption className="wb-visually-hidden">历史指标原值与对照</caption><thead><tr><th scope="col">结果指标</th><th scope="col">当前记录</th>{compare && <><th scope="col">对照记录</th><th scope="col">变化</th></>}</tr></thead>
      <tbody>{definitions.map(definition => {
        const selected = entry.metrics[definition.key], before = reference && reference.metrics[definition.key], delta = comparison.metric_deltas[definition.key];
        const comparable = Boolean(delta && delta.state === 'comparable');
        return <tr key={definition.key} data-history-metric={definition.key}><th scope="row">{definition.label}</th><td><MetricValue value={selected} definition={definition} /></td>{compare && <><td><MetricValue value={before} definition={definition} /></td>
          <td data-direction={comparable ? delta.direction : undefined}>{delta ? <><strong>{comparable ? window.RunDecisionComparison.deltaText(delta, { ...definition, unit: selected.unit }) : gateLabels[delta.state]}</strong>{comparable && delta.direction !== 'equal' && <p className="dh-note">{directionLabels[delta.direction]}</p>}</> : '待确认'}</td></>}</tr>;
      })}</tbody></table></div>;
  }
  function ResourceWindow({ entry, label, definitions }) {
    const value = entry.reading_context.resource_window, metrics = ['machine', 'operator'].map(kind => definitions.find(definition =>
      definition.source === 'archived_resource_calendar' && definition.key.startsWith(kind + '_')
      && /(?:utilization_ratio|balance_cv)$/.test(definition.key) && Object.prototype.hasOwnProperty.call(entry.metrics, definition.key))).filter(Boolean);
    return <div className="dh-resource-context"><h4>{label}统计时间</h4><p>{localTime(value.start)} 至 {localTime(value.end)}<small className="dh-note">（含开始、不含结束）</small></p>
      <p className="dh-note">{value.mode === 'absolute' ? '共同起止时间' : '各记录起点起 ' + number(value.days, '天')} · 设备 {value.cohort.machine_refs === null ? '未知' : value.cohort.machine_refs.length} · 人员 {value.cohort.operator_refs === null ? '未知' : value.cohort.operator_refs.length}</p><Reason value={value.reason} />
      {metrics.length > 0 && <div className="wb-table-frame dh-gate-table" tabIndex={0} aria-label={label + '资源容量表格滚动区域'}><table className="wb-table" aria-label={label + '资源容量与分母'}><caption className="wb-visually-hidden">{label}资源容量与分母</caption>
        <thead><tr><th scope="col">资源</th><th scope="col">窗口班内已占</th><th scope="col">窗口可排总时长</th><th scope="col">待确认工作</th></tr></thead><tbody>{metrics.map(definition => { const metric = entry.metrics[definition.key];
          return <tr key={definition.key}><th scope="row">{definition.key.startsWith('machine_') ? '设备' : '人员'}</th><td>{number(metric.numerator_hours, '小时', 3)}</td><td>{number(metric.denominator_hours, '小时', 3)}</td><td>{number(metric.unknown_workload_count, '项')}</td></tr>;
        })}</tbody></table></div>}
    </div>;
  }
  function PairRows({ rows, categories, label, compare = true }) {
    const names = Object.fromEntries(categories.map(category => [category.key, category.label]));
    return rows.length ? <div className="wb-table-frame dh-condition-table" tabIndex={0} aria-label={label + '表格滚动区域'}><table className="wb-table" aria-label={label}>
      <caption className="wb-visually-hidden">{label}保存值</caption><thead><tr><th scope="col">对象</th><th scope="col">条件</th>{compare && <th scope="col">对照记录</th>}<th scope="col">{compare ? '当前记录' : '保存值'}</th>{compare && <th scope="col">结果</th>}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={row.category + ':' + row.entity.key + ':' + row.field + ':' + index} data-history-condition-state={row.state}><td>{row.entity.label}<small className="dh-note">{names[row.category] || row.category}</small></td><th scope="row">{fieldLabel(row)}</th>
        {compare && <td><SavedSide value={row.before} field={row.field} /></td>}<td><SavedSide value={row.after} field={row.field} /></td>{compare && <td>{pairLabels[row.state]}</td>}</tr>)}</tbody></table></div> : <p className="dh-note">本页没有{label}。</p>;
  }
  function ConditionSummary({ value }) {
    const attention = value.summary.different + value.summary.unknown;
    return attention === 0 ? <p className="dh-note">生产条件相同，共 {value.summary.equal} 项</p> : <div className="dh-condition-summary"><p>生产条件变化 {value.summary.different} 项 · 待确认 {value.summary.unknown} 项</p>
      {value.categories.filter(category => category.summary.different + category.summary.unknown > 0).map(category => <span key={category.key}>{category.label} · 变化 {category.summary.different} 项 · 待确认 {category.summary.unknown} 项</span>)}</div>;
  }
  function Conditions({ value, onQuery, busy }) {
    return <><PairRows rows={value.rows} categories={value.categories} label="生产条件" /><div className="dh-page" data-history-condition-pager tabIndex={-1}><window.WorkbenchListControls.Pager page={value.page} sizes={[20, 50]} unit="项" label="生产条件" sizeLabel="生产条件每页数量" busy={busy} onPage={page => onQuery({ condition_page: page }, true)} onSize={size => onQuery({ condition_page: 1, condition_size: size }, true)} /></div></>;
  }
  function Conclusion({ comparison, definitions }) {
    const value = comparison.conclusion, names = Object.fromEntries(definitions.map(definition => [definition.key, definition.label]));
    return <div className="dh-conclusion"><h4>主要变化</h4><p data-history-conclusion={value.state} aria-live="polite"><strong>{value.message}</strong></p>
      {value.improved_metric_keys.length > 0 && <p>改善：{value.improved_metric_keys.map(key => names[key] || key).join('、')}</p>}{value.worsened_metric_keys.length > 0 && <p>增加的代价：{value.worsened_metric_keys.map(key => names[key] || key).join('、')}</p>}
      <ConditionSummary value={comparison.conditions} />{comparison.objective && comparison.objective.state !== 'equal' && <p className="dh-note">优化目标{pairLabels[comparison.objective.state]}</p>}
    </div>;
  }
  function Sources({ data, result }) {
    const entry = data.selection.entry, reference = data.selection.reference;
    return <details className="dh-source-details"><summary>数据来源</summary><div>历次排产 {data.totals.run} 次 · 已采用方案 {data.totals.official} 次</div><div>刷新时间：{F.dateTime(result.meta.as_of, { seconds: true, fractions: true })}</div><window.WorkbenchReference value={result.meta.snapshot_ref} label="历史快照" />
      {entry && <><dl className="dh-detail-meta"><div><dt>原正式基准</dt><dd>{entry.baseline.version === null ? '版本未记录' : entry.baseline.version === 0 ? '当时无正式计划' : '第 ' + entry.baseline.version + ' 版'}</dd></div>
        <div><dt>应排需求</dt><dd>{number(entry.scope.demand_hours, '小时', 3)}<Reason value={entry.scope.reason} /></dd></div><div><dt>时间来源</dt><dd>{timeBasisLabels[entry.time_basis] || plain(entry.time_basis)}</dd></div><div><dt>保存来源</dt><dd>{savedSourceLabels[entry.source.kind] || A.sourceLabel(entry)}</dd></div></dl>
        <Raw value={{ identity: entry.identity, times: entry.times, baseline: entry.baseline, source: entry.source, scope: entry.scope, reading_context: entry.reading_context, metrics: entry.metrics, issues: entry.issues }} /></>}
      {reference && <><h4>对照记录来源</h4><Raw value={{ identity: reference.identity, times: reference.times, source: reference.source, scope: reference.scope, reading_context: reference.reading_context, metrics: reference.metrics }} /></>}
      {entry && reference && <><h4>条件与指标依据</h4><Raw value={data.comparison} /></>}
    </details>;
  }
  function Details({ data, onQuery, onOpen, canNavigate, busy, onEndComparison, conditionsOpen = false, onConditionsToggle }) {
    const entry = data.selection.entry, reference = data.selection.reference;
    if (!entry || reference && reference.entry_ref === entry.entry_ref) return <div className="dh-selection-prompt" data-history-detail-title tabIndex={-1} aria-label="记录详情">{reference ? <><span>对照：{reference.label}，请选择另一条记录。</span><C.Button disabled={busy} onClick={onEndComparison}>结束对照</C.Button></> : '选择记录查看结果'}</div>;
    const definitions = data.metric_definitions.filter(definition => data.filters.metric_keys.includes(definition.key) && Object.prototype.hasOwnProperty.call(entry.metrics, definition.key)), compare = reference !== null;
    const configurations = data.comparison.configurations, configurationChanged = configurations.summary.different + configurations.summary.unknown > 0;
    return <section className="dh-detail" aria-label="记录详情" aria-busy={busy || undefined} data-history-detail={entry.entry_ref}>
      <EntryIdentity entry={entry} reference={reference} onEndComparison={onEndComparison} busy={busy} />
      {compare && <Conclusion comparison={data.comparison} definitions={definitions} />}
      <MetricTable entry={entry} reference={reference} definitions={definitions} comparison={data.comparison} compare={compare} />
      <div className="dh-next-step"><h4>下一步</h4><Navigation entry={entry} onOpen={onOpen} canNavigate={canNavigate} busy={busy} /></div>
      {compare && <><details className="dh-condition-details" open={conditionsOpen} onToggle={event => onConditionsToggle && onConditionsToggle(event.currentTarget.open)}><summary>生产条件详情 · {data.comparison.conditions.page.total} 项</summary><Conditions value={data.comparison.conditions} onQuery={onQuery} busy={busy} /></details>
        {data.comparison.objective && data.comparison.objective.state !== 'equal' && <details className="dh-condition-details"><summary>优化目标详情</summary><PairRows rows={[data.comparison.objective]} categories={data.comparison.configurations.categories} label="优化目标" /></details>}
        {configurations.rows.length > 0 && <details className="dh-condition-details"><summary>{configurationChanged ? <>算法设置变化 {configurations.summary.different} 项 · 待确认 {configurations.summary.unknown} 项</> : <>相同算法设置 · {configurations.summary.equal} 项</>}</summary>
          <PairRows rows={configurations.rows.filter(row => configurationChanged ? row.state !== 'equal' : row.state === 'equal')} categories={configurations.categories} label={configurationChanged ? '算法设置变化' : '相同设置'} />{configurationChanged && configurations.summary.equal > 0 && <details><summary>相同设置 · {configurations.summary.equal} 项</summary><PairRows rows={configurations.rows.filter(row => row.state === 'equal')} categories={configurations.categories} label="相同设置" /></details>}</details>}
      </>}
      {definitions.some(A.windowMetric) && <details className="dh-condition-details"><summary>统计时段与资源范围</summary><ResourceWindow entry={entry} label="所选" definitions={definitions} />{reference && <ResourceWindow entry={reference} label="对照" definitions={definitions} />}</details>}
    </section>;
  }
  window.DecisionHistoryDetails = { Details, Sources };
})();
