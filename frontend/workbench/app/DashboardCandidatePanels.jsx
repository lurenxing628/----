(function () {
  'use strict';
  const { Button, Modal } = window.ResourceControls;
  // 计量值保留两位小数；不足 0.01 的非零值写“不到 0.01”，不能读成 0（与执行排产候选对比的“不到 0.001”同一规则）。
  const tiny = v => typeof v === 'number' && v !== 0 && Number(Math.abs(v).toFixed(2)) === 0;
  const number = v => tiny(v) ? '不到 0.01' : window.WorkbenchFormat.number(v, { digits: Number.isInteger(v) ? 0 : 2 });
  const signed = (v, scale = 1) => v === null ? '未知' : v === 0 ? '0' : (v > 0 ? '+' : '-') + number(Math.abs(v * scale));
  const T = window.WorkbenchTerms, risks = T.delivery_risks;
  const risk = row => row.risk === 'overdue' ? (tiny(row.delay_hours) ? '超期不到 0.01 小时' : '超期 ' + number(row.delay_hours) + ' 小时') : risks[row.risk] || risks.unknown;
  function DeliveryValue({ summary, metric }) {
    const value = summary[metric], subtotal = metric === 'overdue_count' ? summary.known_overdue_count : summary.known_tardiness_hours;
    return <>{summary.state === 'not_applicable' ? '不适用' : number(value)}{value === null && summary.state !== 'not_applicable' && <small>已知小计 {number(subtotal)} · 未知 {summary.unknown_due_count} 批</small>}</>;
  }
  function TradeoffValue({ value, item }) {
    return value === null ? item.state === 'not_applicable' ? '不适用' : '未知'
      : item.unit === '%' ? window.WorkbenchFormat.percent(value)
        : window.WorkbenchFormat.number(value, { digits: item.precision, trim: true }) + (item.unit ? ' ' + item.unit : '');
  }
  function TradeoffEvidence({ item }) {
    const scopes = { common_completed_batches: '两份安排都已排齐工序的批次', fixed_resource_window: '同一时间范围内的设备与人员',
      fixed_changeover_window: '同一时间范围内设备上相邻工序的工种变化', full_admission: '本次所选批次的全部工序' };
    return <details className="wb-ref"><summary>比较范围与关联记录</summary>
      <p>{scopes[item.scope] || '比较范围未记录'}</p>
      {item.compared_batch_count > 0 && <p>可对照 {item.compared_batch_count} 批，展示最多 3 个编号</p>}
      {item.sample_compared_batch_refs.map(ref => <window.WorkbenchReference key={ref} value={ref} label="对照批次" />)}
      {item.supporting_refs.filter(target => target.ref !== null).map((target, index) => <window.WorkbenchReference key={index} value={target.ref} label={target.label || '关联记录'} />)}
    </details>;
  }
  function Tradeoffs({ data }) {
    const value = data.tradeoffs;
    return <section className="dy-tradeoffs" aria-label="方案收益与代价"><h3>方案收益与代价</h3>
      {data.baseline.available ? <div className="dy-tradeoff-grid">{[['benefits', '主要收益', 'success', '收益'], ['costs', '主要代价', 'warning', '代价']].map(([key, label, tone, kind]) => <div key={key} className="dy-tradeoff" data-tone={value[key].length ? tone : 'neutral'}><h4>{label}</h4>
        {value[key].length ? <ul>{value[key].map(item => <li key={item.metric_key}><strong>{item.label}</strong><p>{item.text}</p>{item.reason && <small>{item.reason.message}</small>}</li>)}</ul>
          : <p>本范围暂无已确认的{kind}。</p>}</div>)}</div> : <p className="dy-tradeoff-unavailable">排产时没有正式计划，收益与代价暂无法比较。</p>}
      <details className="dy-tradeoff-details"><summary>全部差值与比较依据 · {value.all_differences.length} 项</summary><div className="dy-scroll"><table className="dy-analysis-table" aria-label="所选候选全部取舍差值">
        <thead><tr><th scope="col">指标 / 范围</th><th scope="col">排产时的正式计划</th><th scope="col">所选候选方案</th><th scope="col">变化 / 说明</th></tr></thead>
        <tbody>{value.all_differences.map(item => <tr key={item.metric_key} data-comparison-tradeoff={item.metric_key}>
          <th scope="row">{item.label}<TradeoffEvidence item={item} /></th><td><TradeoffValue value={item.reference_value} item={item} /></td>
          <td><TradeoffValue value={item.selected_value} item={item} /></td><td>{item.text}{item.reason && <small>{item.reason.message}</small>}</td>
        </tr>)}</tbody></table></div></details>
    </section>;
  }
  function Finish({ row }) {
    const missing = T.missing_arrangements(row.ordinary_unscheduled_operation_count, row.deferred_operation_count);
    return <>{row.planned_finish ? <span title={window.WorkbenchFormat.dateTime(row.planned_finish, { seconds: true, fractions: true })}>{window.WorkbenchFormat.compactDateTime(row.planned_finish)}</span> : T.delivery_completion_states[row.completion_state]}
      {row.planned_finish && <small>{T.delivery_completion_states[row.completion_state]}</small>}{missing && <small>{missing}</small>}
      {!row.planned_finish && row.partial_planned_finish && <small>{T.arrangement_labels.partial_finish}：{window.WorkbenchFormat.compactDateTime(row.partial_planned_finish)}</small>}</>;
  }
  function Peak({ value }) { return value.peak_utilization !== null ? <>{window.WorkbenchFormat.percent(value.peak_utilization)}</> : value.state === 'available' ? <>没有可排时间</> : <>可排时间未记录</>; }
  function Metrics({ data }) {
    const old = data.summary.before, selected = data.summary.after;
    return <section className="dy-comparison-metrics" aria-label="所选候选比较"><Tradeoffs data={data} /><h3>批次交付对比汇总</h3><div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">批次交付对比汇总</caption><thead><tr><th scope="col">指标</th><th scope="col">{window.WorkbenchTerms.baseline_plan}</th><th scope="col">所选候选方案</th></tr></thead><tbody>
      <tr><td>{T.overdue_count}</td><td><DeliveryValue summary={old} metric="overdue_count" /></td><td><DeliveryValue summary={selected} metric="overdue_count" /></td></tr>
      <tr><td>{T.total_tardiness_hours}（小时）</td><td><DeliveryValue summary={old} metric="total_tardiness_hours" /></td><td><DeliveryValue summary={selected} metric="total_tardiness_hours" /></td></tr>
      <tr><td>同范围{T.changeover_count}</td><td>{number(old.changeovers.value)}{old.changeovers.value === null && old.changeovers.reason && <small>{old.changeovers.reason}</small>}</td>
        <td>{number(selected.changeovers.value)}{selected.changeovers.value === null && selected.changeovers.reason && <small>{selected.changeovers.reason}</small>}</td></tr>
    </tbody></table></div>
      {data.resource_common && <div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">设备与人员占用汇总</caption><thead><tr><th>资源类型</th><th>原安排班内已占 / 可排（小时）</th><th>候选班内已占 / 可排（小时）</th><th>候选占用比例</th></tr></thead><tbody>{['machine', 'operator'].map(kind => {
        const before = data.resource_common.before[kind], after = data.resource_common.after[kind];
        return <tr key={kind}><td>{T.resource_kinds[kind]} · {after.resource_count} 项</td><td>{number(before.occupied_hours)} / {number(before.available_hours)}</td><td>{number(after.occupied_hours)} / {number(after.available_hours)}</td><td>{window.WorkbenchFormat.percent(after.utilization_ratio)}</td></tr>;
      })}</tbody></table></div>}
      <details className="dy-evidence"><summary>交期数据范围与资源计算详情</summary><p>排产时的正式计划：{T.delivery_coverage(old)}</p><p>候选方案：{T.delivery_coverage(selected)}</p>
        <p>使用排产时保存的班表，在同一时间范围内对照全部候选和当时正式计划涉及的设备、人员。这里统计所选批次的占用。</p>
        <div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">逐资源日峰值对照</caption><thead><tr><th>资源</th><th>原安排日峰值占用比例</th><th>候选日峰值占用比例</th></tr></thead><tbody>
          {data.resources.map(row => <tr key={row.resource_ref} data-comparison-resource={row.resource_ref}><td>{T.resource_kinds[row.kind]} · {row.label || T.name_missing}</td><td><Peak value={row.before} /></td><td><Peak value={row.after} /></td></tr>)}
        </tbody></table></div>
        {data.resource_common && <div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">资源计算详情</caption><thead><tr><th>资源类型</th><th>候选班内工序累计 / 可排时间</th><th>候选资源占用差异</th></tr></thead><tbody>{['machine', 'operator'].map(kind => {
          const after = data.resource_common.after[kind];
          return <tr key={kind}><td>{T.resource_kinds[kind]}</td><td>{window.WorkbenchFormat.percent(after.demand_ratio)}</td><td>{after.balance_state === 'not_applicable' ? '不适用' : number(after.balance_cv)}{after.balance_reason && <small>{after.balance_reason.message}</small>}</td></tr>;
        })}</tbody></table></div>}<p>资源占用差异按各资源的可排时间加权，比较占用比例的离散程度；数值越小，占用比例越接近。</p>
      </details>
      {!data.resource_scope_complete && <div className="dy-note warning">有 {data.resource_scope_unknown_rows} 条安排读不到所在资源，这部分没有计入负荷，实际占用可能更高。</div>}
    </section>;
  }
  function Batches({ data, selected, onSelect }) { return <section aria-label="逐批交期变化"><h3>逐批交期变化</h3><div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">逐批交期变化</caption>
    <thead><tr><th scope="col">批次 / 零件</th><th scope="col">交期</th><th scope="col">原安排 / 预计完工</th><th scope="col">候选安排 / 预计完工</th><th scope="col">原 / 候选交付判断</th><th scope="col">超期变化（小时）</th></tr></thead><tbody>{data.batches.map(row => <tr key={row.batch_ref} data-comparison-batch={row.batch_ref} data-selected={selected === row.batch_ref}>
      <td><Button data-wb-print-value reasonDisplay="inline" className="mini" icon="search" aria-pressed={selected === row.batch_ref} onClick={() => onSelect(row.batch_ref)}>{row.batch_id}</Button><small>{row.part_label || '名称未填写'}</small></td>
      <td>{T.due_date(row.after.due_date, row.after.due_state, row.after.due_issue)}</td><td><Finish row={row.before} /></td>
      <td><Finish row={row.after} /></td><td>{risk(row.before)} / {risk(row.after)}</td><td>{row.after.due_state === 'unspecified' ? '不适用' : signed(row.delay_delta_hours)}</td>
    </tr>)}</tbody></table></div></section>; }
  function Summary({ data, onClose }) { return <Modal title="候选方案摘要" icon="chart-gantt" onClose={onClose} footer={<Button reasonDisplay="inline" icon="arrow-left" onClick={onClose}>返回比较</Button>}>
    <div className="modal-b form dy-candidate-summary"><h3>{data.candidate.label || window.WorkbenchTerms.name_missing}</h3><dl className="dy-facts">
      <div><dt>{window.WorkbenchTerms.baseline_plan}</dt><dd>{data.baseline.baseline_ref ? '已读到排产时的正式计划' : '排产时没有正式计划'}</dd></div>
      <div><dt>{T.overdue_count}</dt><dd><DeliveryValue summary={data.summary.after} metric="overdue_count" /></dd></div><div><dt>{T.total_tardiness_hours}（小时）</dt><dd><DeliveryValue summary={data.summary.after} metric="total_tardiness_hours" /></dd></div>
      <div><dt>同范围{T.changeover_count}</dt><dd>{number(data.summary.after.changeovers.value)}</dd></div><div><dt>换设备工序</dt><dd>{number(data.machine_changes.count)} · 已确认 {data.machine_changes.known_count} · 未知 {data.machine_changes.unknown_count}</dd></div>
    </dl><p className="dy-context">{T.delivery_coverage(data.summary.after)}</p><Tradeoffs data={data} /><window.WorkbenchReference entries={{ '候选编号': data.candidate.candidate_ref, '排产时正式计划编号': data.baseline.baseline_ref }} /><details className="wb-ref"><summary>换设备工序编号</summary>{data.machine_changes.operation_refs.map(ref => <p key={ref}>{ref}</p>)}{!data.machine_changes.operation_refs.length && <p>没有已确认换设备的工序。</p>}</details></div>
  </Modal>; }
  window.DashboardCandidatePanels = { Metrics, Batches, Summary, Tradeoffs, number, signed, risk };
})();
