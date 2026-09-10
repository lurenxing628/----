(function () {
  'use strict';
  const { Button, Icon } = window.ResourceControls;
  function ErrorBox({ error }) { return error ? <div className="rc-notice rc-error" role="alert">{error.message || '候选读取失败，未显示替代结果。'}</div> : null; }
  function Reasons({ rows = [] }) {
    const groups = new Map();
    rows.forEach(r => { const key = [r.field, r.code, r.message].join('\n'); if (!groups.has(key)) groups.set(key, { ...r, count: 0 }); groups.get(key).count++; });
    const [page, setPage] = React.useState(1), values = Array.from(groups.values()), pages = Math.max(1, Math.ceil(values.length / 20)), current = Math.min(page, pages);
    if (!values.length) return null;
    return <details className="rc-reasons"><summary>原因与数据缺项 · {rows.length} 项</summary>
      {values.slice((current - 1) * 20, current * 20).map((r, i) => <div key={i}>{r.field && <code>{r.field} · </code>}{r.message}{r.count > 1 && '（' + r.count + ' 项）'}</div>)}
      {pages > 1 && <Pager page={current} pages={pages} onPage={setPage} label="原因" />}</details>;
  }
  function Pager({ page, pages, onPage, disabled, label }) {
    return <div className="rc-tools"><Button icon="chevron-left" aria-label={label + '上一页'} disabled={disabled || page <= 1} onClick={() => onPage(page - 1)} />
      <span>{page} / {pages}</span><Button icon="chevron-right" aria-label={label + '下一页'} disabled={disabled || page >= pages} onClick={() => onPage(page + 1)} /></div>;
  }
  function Metric({ metric, suffix = '' }) {
    return metric.value === null ? <details className="rc-metric rc-muted"><summary title={metric.reason.message}>未知</summary><small>{metric.reason.message}</small></details> :
      <span>{window.RunCandidateModel.number(metric.value)}{suffix}</span>;
  }
  function Status({ candidate }) {
    return <span className={'pill ' + (candidate.status === 'completed' && candidate.completeness === 'complete' ? 'ok' : 'warn')} data-candidate-status={candidate.status}>
      <span className="dot" />{{ completed: '已完成', partial: '部分完成', failed: '失败', skipped: '已跳过' }[candidate.status]}
      {candidate.completeness === 'unknown' && ' · 完整性未知'}</span>;
  }
  function Catalog({ result, selectedRef, busy, query, onQuery, onSelect }) {
    const d = result && result.data;
    return <section aria-label="候选比较"><div className="rc-heading"><h3>候选比较{d && ' · ' + d.candidate_count + ' 项'}</h3>
      <div className="rc-tools"><label>状态 <select aria-label="候选状态" value={query.status || 'all'} disabled={busy} onChange={e => onQuery({ status: e.target.value })}>
        {[['all', '全部'], ['completed', '已完成'], ['partial', '部分完成'], ['failed', '失败'], ['skipped', '已跳过']].map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></label>
        <label>排序 <select aria-label="候选排序" value={query.sort || 'sequence'} disabled={busy} onChange={e => onQuery({ sort: e.target.value })}>
          <option value="sequence">生成顺序</option><option value="label">名称</option><option value="task_count">安排数</option></select></label></div></div>
      {d && <><div className="rc-table"><table aria-label="候选比较"><thead><tr><th>候选方案</th><th>状态</th><th>安排</th><th>超期批次</th><th>总拖期 h</th><th>跨度 h</th><th>操作</th></tr></thead><tbody>
        {d.candidates.map(c => <tr key={c.candidate_ref} data-candidate-ref={c.candidate_ref} aria-selected={c.candidate_ref === selectedRef}>
          <td><div className="rc-name"><span>{c.label || '生成时名称未记录'}</span><details className="rc-id"><summary aria-label={'候选记录编号 ' + c.candidate_ref}>编号</summary><code>{c.candidate_ref}</code></details></div></td><td><Status candidate={c} /></td><td>{c.task_count}</td>
          {['overdue_count', 'total_tardiness_hours', 'makespan_hours'].map(k => <td key={k}><Metric metric={c.metrics[k]} /></td>)}
          <td><Button icon="search" className="mini" aria-label={'查看候选 ' + c.candidate_ref} disabled={busy || d.capabilities.view !== true || c.capabilities.view !== true} onClick={() => onSelect(c)}>查看</Button></td></tr>)}</tbody></table></div>
        {!d.candidates.length && <p className="rc-muted">此运行在当前筛选下没有候选记录。</p>}
        {!d.catalog_complete && <p className="rc-notice">本次运行尚未结束，候选目录尚不完整。</p>}
        <div className="rc-heading"><span className="rc-muted">交付指标仅覆盖完成批次；资源指标仅覆盖已排结果，缺项不按零计算。</span>
          <Pager page={d.page.number} pages={Math.max(1, Math.ceil(d.page.total / d.page.size))} disabled={busy} label="候选" onPage={page => onQuery({ page }, true)} /></div></>}
    </section>;
  }
  function Generation({ data, analysis }) {
    const g = data.generation, input = g.input, M = window.RunCandidateModel;
    return <section aria-label="生成时范围"><div className="rc-heading"><div className="rc-tools"><h3>当前：{data.candidate.label || '名称未记录'}</h3><Status candidate={data.candidate} /><span className="rc-pending">生成时未分配正式版本</span></div>
      <span>生成窗口：{input.start_date || '未记录'} 至 {input.end_date || '未记录'}</span></div>
      <div className="rc-source-summary"><details className="rc-reasons rc-generation"><summary>生成资料与记录编号</summary><dl className="rc-meta">
        <div><dt>生成受理 / 结束</dt><dd>{M.timeLabel(g.accepted_at)}<small>{M.timeLabel(g.finished_at)}</small></dd></div>
        <div><dt>齐套检查 / 缺资源</dt><dd>{input.ready_check === null ? '未记录' : input.ready_check ? '开启' : '关闭'} / {{ auto_assign: '自动分配', exclude: '暂不排' }[input.missing_resource_policy] || '未记录'}</dd></div>
        <div><dt>已有执行 / 当时的正式计划</dt><dd>{input.completed_policy === 'preserve_actuals' ? '保留已有开工和完工记录' : '执行策略未记录'}<small>{g.baseline.captured_task_count === null ? '正式计划安排数未知' : '已保留 ' + g.baseline.captured_task_count + ' 道正式计划安排'}</small></dd></div></dl>
      <div className="rc-muted">名称、资源、交期和执行状态来自生成时保存的资料，未读取后来的修改。{analysis ? analysis.baseline.reason && analysis.baseline.reason.message : g.baseline.reason.message}</div>
      <div className="rc-muted">{analysis ? '受理时选批：' + analysis.batches.map(row => row.batch_id).join(' / ') : '原始选批清单尚未核对，不能用可见安排反推生成时的完整选批范围。'}</div>
      <div>运行记录编号：<code>{g.run_ref}</code></div><div>候选记录编号：<code>{data.candidate.candidate_ref}</code></div>
        <dl className="rc-meta">{window.RunCandidateAPI.metricKeys.map(k => <div key={k}><dt>{M.metricLabels[k]}</dt><dd><Metric metric={data.candidate.metrics[k]} /></dd></div>)}
          <div><dt>实际工时 / 成本</dt><dd>未知<small>当前候选接口未提供实际工时与成本事实。</small></dd></div></dl></details>
      <span className="rc-muted">{analysis ? '完整受理范围 ' + analysis.batch_refs.length + ' 批' : '完整受理范围待核对'}</span>
      <Reasons rows={[...data.data_gaps, ...data.candidate.data_gaps, ...g.data_gaps, ...data.blocked_reasons, ...data.candidate.blocked_reasons]} /></div>
    </section>;
  }
  function Detail({ task, onClose }) {
    const M = window.RunCandidateModel;
    return <aside className="rc-detail" aria-label="候选工序详情"><div className="rc-heading"><h3>工序详情</h3>{task && <Button icon="x" aria-label="关闭工序详情" onClick={onClose} />}</div>
      {!task ? <p className="rc-muted">尚未选择工序</p> : <><strong>{task.batch_label || '批次名称未记录'} · {task.process_label || '工序名称未记录'}</strong>
        <dl>{[['零件', task.part_label], ['工序顺序', M.number(task.sequence)],
          ['分件', task.piece_id === null ? task.data_gaps.some(g => g.field === 'piece_id') ? '分件未记录' : '共同工序' : task.piece_id],
          ['本工序目标量', M.number(task.quantity)], ['生成时整批量', M.number(task.batch_quantity)], ['交期', task.due_date],
          ['开始', task.start && M.timeLabel(task.start)], ['结束', task.end && M.timeLabel(task.end)], ['设备', task.machine && task.machine.label], ['人员', task.operator && task.operator.label],
          ['外协商', task.supplier && task.supplier.label], ['来源', task.source === 'internal' ? '内部' : task.source === 'external' ? '外协' : null],
          ['生成时锁定', typeof task.locked === 'boolean' ? task.locked ? '是' : '否' : null], ['安排状态', task.reason ? task.reason.message : '已保存候选安排'],
          ['安排记录编号', task.row_ref], ['工序编号', task.operation_ref], ['批次编号', task.batch_ref]].map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v == null ? '未记录' : v}</dd></div>)}</dl>
        <h4>生成时的开工和完工记录</h4>{task.execution_at_generation ? <dl>{Object.entries(task.execution_at_generation).map(([k, v]) => <div key={k}><dt>{M.executionLabels[k]}</dt><dd>{v === null ? '未知' : M.executionValue(v)}</dd></div>)}</dl> : <p className="rc-muted">未保留生成时的开工和完工记录，不能推断为未开工。</p>}
        <p className="rc-muted">实际工时、成本：未知；接口未提供事实，安排时间跨度不等于实际工时。</p><Reasons rows={task.data_gaps} /></>}
    </aside>;
  }
  function Styles() {
    return <style>{`
      .plana.run-candidate-workspace{padding:0;max-width:none;width:100%;min-width:0;color:var(--ui-text);font-size:13px;letter-spacing:0}
      .run-candidate-workspace *{box-sizing:border-box;letter-spacing:0}.run-candidate-workspace h2{font-size:17px;margin:0;line-height:1.6}.run-candidate-workspace h3{font-size:14px;margin:0;line-height:1.6}.run-candidate-workspace h4{font-size:13px}
      .run-candidate-workspace section{border-bottom:1px solid var(--ui-border);padding:6px 0}.run-candidate-workspace .rc-heading,.run-candidate-workspace .rc-tools{display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-width:0}.run-candidate-workspace .rc-heading{justify-content:space-between;padding:6px 0}
      .run-candidate-workspace .rc-muted,.run-candidate-workspace dt{color:var(--ui-info-muted);font-size:12px;line-height:1.7}.run-candidate-workspace small{display:block;color:var(--ui-info-muted);font-size:11px;line-height:1.6;overflow-wrap:anywhere}.run-candidate-workspace code{overflow-wrap:anywhere;font-size:11px}
      .run-candidate-workspace .rc-meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(195px,1fr));gap:12px;margin:8px 0}.run-candidate-workspace dd{margin:4px 0 10px;overflow-wrap:anywhere}.run-candidate-workspace .rc-pending{color:var(--ui-warning-text);font-size:12px}
      .run-candidate-workspace .rc-notice{background:var(--ui-surface-muted);border-left:3px solid var(--ui-warning);padding:10px 12px;line-height:1.7;margin:8px 0;overflow-wrap:anywhere}.run-candidate-workspace .rc-error{color:var(--ui-danger-text);border-color:var(--ui-danger)}
      .run-candidate-workspace .rc-reasons{font-size:12px;line-height:1.8;margin:8px 0;overflow-wrap:anywhere}.run-candidate-workspace summary{cursor:pointer;font-weight:600}
      .run-candidate-workspace .rc-name,.run-candidate-workspace .rc-source-summary{display:flex;align-items:baseline;gap:8px 16px;flex-wrap:wrap;min-width:0}.run-candidate-workspace .rc-name>span{min-width:0}.run-candidate-workspace .rc-id{font-size:12px;color:var(--ui-info-muted);min-width:0}.run-candidate-workspace .rc-id[open]{flex-basis:100%}.run-candidate-workspace .rc-id code{display:block;font-size:12px;color:var(--ui-text)}
      .run-candidate-workspace .rc-source-summary .rc-reasons{margin:4px 0}.run-candidate-workspace .rc-source-summary .rc-reasons[open]{flex-basis:100%}.run-candidate-workspace .rc-metric summary{font-weight:400}.run-candidate-workspace .rc-scope{display:flex;align-items:baseline;gap:6px 16px;flex-wrap:wrap;padding:6px 0;border-bottom:1px solid var(--ui-border);line-height:1.7;overflow-wrap:anywhere}.run-candidate-workspace .rc-scope details{font-size:12px;color:var(--ui-info-muted)}.run-candidate-workspace .rc-scope details[open]{flex-basis:100%}
      .run-candidate-workspace .pill.ok{color:var(--ui-success-text);background:var(--ui-success-bg)}.run-candidate-workspace .pill.warn{color:var(--ui-warning-text);background:var(--ui-warning-bg)}
      .run-candidate-workspace .rc-table{width:100%;overflow:auto}.run-candidate-workspace table{width:100%;table-layout:fixed;border-collapse:collapse;min-width:760px}.run-candidate-workspace th,.run-candidate-workspace td{padding:8px;border-bottom:1px solid var(--ui-border);text-align:left;white-space:normal!important;overflow-wrap:anywhere;vertical-align:middle}.run-candidate-workspace th{color:var(--ui-info-muted);font-size:12px}.run-candidate-workspace th:first-child{width:27%}.run-candidate-workspace tr[aria-selected=true]{background:var(--ui-primary-soft)}
      .run-candidate-workspace .rc-main{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:16px}.run-candidate-workspace .rc-main>div{min-width:0}.run-candidate-workspace .rc-detail{min-width:0;border-left:1px solid var(--ui-border);padding-left:16px}.run-candidate-workspace .rc-detail dl>div{padding:4px 0;border-bottom:1px solid var(--ui-border)}
      .run-candidate-workspace input,.run-candidate-workspace select{font:inherit;max-width:100%;color:var(--ui-text);background:var(--ui-surface);border:1px solid var(--ui-border);border-radius:4px;min-height:32px;padding:5px 8px}.run-candidate-workspace input[type=range]{padding:0;min-height:20px}.run-candidate-workspace input[type=search]{width:240px}.run-candidate-workspace button{max-width:100%;white-space:normal}.run-candidate-workspace .rc-range{padding:10px 0;display:flex;align-items:end;gap:10px;flex-wrap:wrap}.run-candidate-workspace .rc-range label{display:grid;gap:5px;font-size:12px}
      .run-candidate-workspace .rc-tabs{display:flex;gap:3px;flex-wrap:wrap}.run-candidate-workspace .rc-tabs button[aria-pressed=true],.run-candidate-workspace .rc-tabs button[aria-selected=true]{background:var(--ui-primary-soft);color:var(--ui-primary);border-color:var(--ui-primary)}
      .run-candidate-workspace .rc-empty{padding:24px 0;color:var(--ui-info-muted)}.run-candidate-workspace .rc-list{height:320px;overflow:auto;position:relative;border-top:1px solid var(--ui-border)}.run-candidate-workspace .rc-list-row{height:44px;display:grid;grid-template-columns:1.2fr 1fr 1.5fr 1.5fr 80px;align-items:center;gap:10px;padding:0 8px;border-bottom:1px solid var(--ui-border);font-size:12px;min-width:720px}.run-candidate-workspace .rc-list-row>span{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.run-candidate-workspace .rc-list-row[aria-selected=true]{background:var(--ui-primary-soft)}
      @media(max-width:1050px){.run-candidate-workspace .rc-main{grid-template-columns:minmax(0,1fr)}.run-candidate-workspace .rc-detail{border-left:0;border-top:1px solid var(--ui-border);padding:0}.run-candidate-workspace .rc-detail dl{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}
    `}</style>;
  }
  function Delivery({ data, onLast }) {
    const M = window.RunCandidateModel;
    const [page, setPage] = React.useState(1), summary = data.summary;
    const pages = Math.max(1, Math.ceil(data.items.length / 20)), current = Math.min(page, pages);
    const reasons = { operations_unscheduled: '尚有工序未安排', operations_missing: '受理时工序未记录',
      schedule_time_invalid: '安排时间无效', saved_plan_incomplete: '候选结果不完整', due_date_missing: '交期未记录',
      due_date_invalid: '交期无效', due_date_unspecified: '未指定交期', part_label_missing: '零件标签未记录' };
    return <section aria-label="候选逐批交付风险"><h3>逐批交付风险</h3>
      <dl className="rc-meta">{[[summary.overdue_count, '已核实预计超期'], [summary.total_tardiness_hours, '完整范围拖期 h'],
        [summary.unknown_count, '交付待核实'], [summary.batch_count, '关联批次']].map(([value, label]) => <div key={label}><dt>{label}</dt><dd>{M.number(value)}</dd></div>)}</dl>
      <p className="rc-muted">依据：受理时资料和同批完整候选安排。不是实际完工或发货；未核实等待、停机或缺料根因。</p>
      {data.issues.map((issue, index) => <p className="rc-notice" key={index}>{issue.message}</p>)}
      <div className="rc-table"><table aria-label="候选交付风险列表"><thead><tr>{['批次 / 零件', '批量 / 工序覆盖', '交付截至日', '全批计划完工', '预计交付', '末端工序 / 依据'].map(label => <th key={label}>{label}</th>)}</tr></thead>
        <tbody>{data.items.slice((current - 1) * 20, current * 20).map(row => <tr key={row.batch_ref}>
          <td>{row.batch_id}<small>{row.part_no || '图号未记录'} · {row.part_label || '名称未记录'}</small></td>
          <td>{M.number(row.quantity)} 件<small>{row.scheduled_operation_count} / {row.operation_count} 道</small></td>
          <td>{row.due_date || '未记录'}</td><td>{row.planned_finish ? M.timeLabel(row.planned_finish) : '无法核实'}
            {row.partial_planned_finish && <small>已安排部分：{M.timeLabel(row.partial_planned_finish)}，非全批完工</small>}</td>
          <td>{({ overdue: '预计超期', on_time: '预计按期', unknown: '无法核实' })[row.risk]}<small>{M.number(row.delay_hours)} h</small></td>
          <td>{row.last_operations.map(task => <Button key={task.row_ref} icon="search" className="mini" onClick={() => onLast(task)}
            aria-label={'定位末端工序 ' + row.batch_id + ' ' + task.sequence + (task.piece_id ? ' ' + task.piece_id : '')}>
            {M.number(task.sequence)} {task.process_label || '工序未记录'}{task.piece_id && ' · ' + task.piece_id}</Button>)}
            {row.issues.map((code, index) => <small key={index}>{reasons[code] || '受理时依据不完整，交付结论待核实'}</small>)}</td>
        </tr>)}{!data.items.length && <tr><td colSpan={6}>{data.items_complete ? '当前读取范围没有批次。' : '交付依据未完整记录，不能认定为零风险。'}</td></tr>}</tbody></table></div>
      <Pager page={current} pages={pages} onPage={setPage} label="候选交付风险" />
    </section>;
  }
  window.RunCandidateControls = { Button, Icon, ErrorBox, Reasons, Pager, Metric, Status, Catalog, Generation, Detail, Delivery, Styles };
})();
