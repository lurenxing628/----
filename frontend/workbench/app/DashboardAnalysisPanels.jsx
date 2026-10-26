(function () {
  'use strict';
  const { Button, Issues, ErrorBox } = window.ResourceControls, M = window.DashboardTimelineModel;
  // Counts stay whole numbers; hours and other measured values keep two decimals.
  // 不足 0.01 的非零值写“不到 0.01”，不能读成 0。
  const tiny = v => typeof v === 'number' && v !== 0 && Number(Math.abs(v).toFixed(2)) === 0;
  const value = v => v === null || v === undefined ? '未知' : tiny(v) ? '不到 0.01' : typeof v === 'number' ? M.number(v, { digits: Number.isInteger(v) ? 0 : 2 }) : String(v);
  const T = window.WorkbenchTerms, risks = T.delivery_risks;
  const risk = row => row.risk === 'overdue' ? (tiny(row.delay_hours) ? '超期不到 0.01 小时' : '超期 ' + value(row.delay_hours) + ' 小时') : risks[row.risk] || risks.unknown;
  function Batch({ row, selected, onSelect }) { return <Button data-wb-print-value reasonDisplay="inline" className="mini" icon="search" data-analysis-select-batch={row.batch_ref}
    aria-pressed={selected === row.batch_ref} onClick={() => onSelect(row.batch_ref)}>{row.batch_id}</Button>; }
  function Delivery({ data, selected, onSelect, onCompare }) { return <>
    <section aria-label="影响批次"><div className="dy-heading"><h3>影响批次</h3><Button reasonDisplay="inline" icon="git-compare-arrows" onClick={onCompare}>对比候选方案</Button></div>
      <div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">影响批次交付</caption><thead><tr><th scope="col">批次 / 零件</th><th scope="col">交期</th><th scope="col">工序安排 / 预计完工</th><th scope="col">交付判断</th><th scope="col">优先级</th></tr></thead>
        <tbody>{data.deliveries.map(row => <tr key={row.batch_ref} data-analysis-delivery={row.batch_ref} data-selected={selected === row.batch_ref}>
          <td><Batch row={row} selected={selected} onSelect={onSelect} /><small>{value(row.part_label)}</small></td><td>{T.due_date(row.due_date, row.due_state, row.due_issue)}</td>
          <td>{T.delivery_completion_states[row.completion_state]}{row.planned_finish && <div>{M.timeLabel(row.planned_finish)}</div>}
            {row.partial_planned_finish && <small>{T.arrangement_labels.partial_finish}：{M.timeLabel(row.partial_planned_finish)}</small>}{row.unscheduled_operation_count > 0 && <small>{T.missing_arrangements(row.ordinary_unscheduled_operation_count, row.deferred_operation_count)}</small>}</td>
          <td>{risk(row)}</td><td>{({ normal: '普通', urgent: '急件', critical: '特急' })[row.priority] || '未知'}</td></tr>)}</tbody></table></div>
      {!data.deliveries.length && <window.WorkbenchListControls.EmptyState kind="empty" title="当前正式计划没有批次交付记录。" />}
    </section>
  </>; }
  function Downtime({ data, selected, onSelect }) { return <>
    <window.DashboardTimeline data={data} mode="downtime" selectedBatch={selected} onSelect={onSelect} />
    <section aria-label="直接重叠工序"><h3>直接重叠的工序</h3><div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">直接重叠的工序</caption><thead><tr><th scope="col">批次 / 工序</th><th scope="col">原计划开始</th><th scope="col">原计划结束</th><th scope="col">重叠时间</th></tr></thead>
      <tbody>{data.overlaps.map(row => <tr key={row.task_ref} data-overlap-task={row.task_ref} data-selected={selected === row.batch_ref}>
        <td><Batch row={row} selected={selected} onSelect={onSelect} /><small>{row.process_label}</small></td><td>{M.timeLabel(row.source.planned_start)}</td>
        <td>{M.timeLabel(row.source.planned_end)}</td><td>{value(row.source.overlap_hours)} 小时</td></tr>)}</tbody></table></div>
      {!data.overlaps.length && <window.WorkbenchListControls.EmptyState kind="empty" title="当前时间范围内没有计划与停机重叠。" />}
    </section>
    <section aria-label="停机登记依据"><h3>登记依据</h3>{data.downtimes.map(row => <dl className="dy-facts" key={row.downtime_ref}>
      <div><dt>设备</dt><dd>{value(row.machine_label)}</dd></div><div><dt>原因</dt><dd>{value(row.reason)}</dd></div>
      <div><dt>开始 / 结束</dt><dd>{M.timeLabel(row.start)} / {M.timeLabel(row.end)}</dd></div><div><dt>登记时间</dt><dd>{M.timeLabel(row.recorded_at)}</dd></div>
    </dl>)}</section>
  </>; }
  function Material({ data, showIssues = true }) {
    const p = data.pending;
    return <section aria-label="待排批次与齐套日期"><h3>待排批次与齐套日期</h3><div className="dy-context">待排 {value(p.count)} 批 · 本页 {p.items.length} 批 · 已确认待排 {p.known_count} 批</div>{showIssues && <Issues issues={p.issues} />}
      <div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">待排批次与齐套日期</caption><thead><tr><th scope="col">批次 / 零件</th><th scope="col">数量</th><th scope="col">交期</th><th scope="col">齐套状态</th><th scope="col">齐套日期</th></tr></thead><tbody>{p.items.map(row => <tr key={row.batch_ref} data-pending-batch={row.batch_ref}>
        <td><b>{row.batch_id}</b><small>{value(row.part_label)}</small></td><td>{value(row.quantity)}</td><td>{value(row.due_date)}</td>
        <td>{({ yes: '齐套', no: '未齐套', partial: '部分齐套' })[row.ready_status] || '未知'}</td><td>{value(row.ready_date)}</td></tr>)}</tbody></table></div>
      {!p.items.length && <window.WorkbenchListControls.EmptyState kind="empty" title={p.count === 0 ? '当前没有待排批次。' : '当前页没有待排批次。'} />}
      <div className="dy-context">当前范围：全部待排批次 · 齐套检查和缺设备人员的规则在「执行排产」里按本次选择设定，已保存候选方案的规则见「方案对比」。</div>
    </section>;
  }
  function Actual({ data, navigate }) {
    const tasks = new Map(data.tasks.map(task => [task.task_ref, task]));
    return <section aria-label="工序执行偏差"><h3>工序报工与定额对照</h3><div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">工序执行偏差</caption>
    <thead><tr><th scope="col">批次 / 工序</th><th scope="col">定额加工小时</th><th scope="col">有效加工小时</th><th scope="col">超耗判断</th><th scope="col">现场记录</th></tr></thead><tbody>{data.execution.map(row => {
      const source = row.source, task = tasks.get(source.task_ref), hours = source.hours, context = { plan_ref: data.plan.plan_ref, task_ref: task.task_ref, operation_ref: task.operation_ref };
      return <tr key={source.task_ref}><td>{task.batch_id + ' · ' + task.process_label}</td><td>{value(hours.quota_processing_hours)} 小时</td><td>{value(hours.effective_processing_hours)} 小时</td>
        <td>{hours.overrun === true ? '已确认超耗' : hours.overrun === false ? '未超耗' : '暂无数据'}</td><td><Button reasonDisplay="inline" icon="square-pen" onClick={() => navigate({ view: 'field', context, enabled: true })}>现场记录</Button>
          <Button reasonDisplay="inline" icon="chart-gantt" onClick={() => navigate({ view: 'fieldgantt', context, enabled: true })}>现场实际甘特</Button></td></tr>;
    })}</tbody></table></div></section>;
  }
  function Section({ section, planRef, resourceRef, locateBatchRef, enabled = true, label, render }) {
    const api = React.useMemo(() => window.DashboardAnalysisAPI.create(), []);
    const loadedPage = React.useRef(null);
    const base = React.useMemo(() => ({ section, page: 1, size: 20, ...(resourceRef ? { resource_ref: resourceRef } : {}),
      ...(locateBatchRef ? { locate_batch_ref: locateBatchRef } : {}) }), [section, planRef, resourceRef, locateBatchRef]);
    const [paging, setPaging] = React.useState(() => ({ base, query: base }));
    const query = React.useMemo(() => {
      if (paging.base === base) return paging.query;
      const loaded = loadedPage.current;
      // An in-page task selection keeps this read identity and its mounted timeline focus.
      if (section === 'timeline' && loaded && loaded.planRef === planRef && loaded.query.size === paging.query.size && loaded.batches.has(locateBatchRef)) return loaded.query;
      return { ...base, size: paging.query.size };
    }, [base, paging]);
    const read = window.DashboardSession.useRead(signal => api.read(planRef, signal, query), [api, planRef, query], enabled);
    const result = read.result, data = result && result.data;
    React.useEffect(() => {
      if (data && section === 'timeline') loadedPage.current = { planRef, query,
        batches: new Set(data.tasks.filter(task => task.source === 'internal' && task.machine_ref).map(task => task.batch_ref)) };
    }, [data, query, planRef, section]);
    function reload() { setPaging({ base, query: { ...base, size: query.size } }); }
    function page(number) {
      const next = { ...query, page: number, snapshot_ref: result.meta.snapshot_ref };
      delete next.locate_batch_ref;
      setPaging({ base, query: next });
    }
    function size(value) { setPaging({ base, query: { ...base, size: value } }); }
    if (!enabled) return null;
    return <section data-analysis-section={section} data-analysis-section-ready={!!data && !read.loading && !read.error} aria-busy={read.loading}>
      <div className="dy-heading"><h3>{label}</h3><Button reasonDisplay="inline" icon="refresh-cw" aria-label={'刷新' + label} busy={read.loading} onClick={reload}>刷新</Button></div>
      <ErrorBox error={read.error} />{read.loading && <p role="status">正在读取{label}。</p>}
      {data && <><div className="dy-context">本节共 {data.pagination.total} 项 · 第 {data.pagination.number} / {data.pagination.pages} 页</div>
        {render(data)}<window.DashboardPanels.Pager page={data.pagination} busy={read.loading} onPage={page} onSize={size} label={label} /></>}
    </section>;
  }
  function ResourceDays({ planRef, resourceRef, enabled }) {
    return <Section section="resource_days" planRef={planRef} resourceRef={resourceRef} enabled={enabled} label="资源逐日明细" render={data => <>
      <div className="dy-scroll"><table className="dy-analysis-table"><caption className="wb-sr-only">资源逐日明细</caption><thead><tr><th scope="col">日期 / 范围</th><th scope="col">可排时长（小时）</th><th scope="col">班内已占（小时）</th><th scope="col">占用比例</th><th scope="col">班外占用（小时）</th><th scope="col">资料状态</th></tr></thead>
        <tbody>{data.resources.flatMap(resource => resource.days.map(day => <tr key={day.date} data-resource-day={day.date}>
          <td>{day.date}<small>{M.timeLabel(day.start)} / {M.timeLabel(day.end)}</small></td><td>{value(day.available_hours)}</td><td>{value(day.inside_available_hours)}</td>
          <td>{window.WorkbenchFormat.percent(day.utilization)}</td><td>{value(day.outside_available_hours)}</td><td>{T.resource_states[day.window_metrics.state]}<Issues issues={day.window_metrics.issues} /></td>
        </tr>))}</tbody></table></div>{data.pagination.total === 0 && <window.WorkbenchListControls.EmptyState kind="empty" title="当前资源没有逐日资料。" />}
    </>} />;
  }
  function Workspace({ data, category, selected, onSelect, onCompare, navigate }) {
    const planRef = data.plan && data.plan.plan_ref, section = ['actual', 'downtime', 'material'].includes(category) ? category : 'delivery';
    const labels = { delivery: '批次交付明细', actual: '工序执行明细', downtime: '停机影响明细', material: '待排齐套明细' };
    return <>
      <Section section={section} planRef={planRef} label={labels[section]} render={analysis => section === 'material' ? <Material data={analysis} showIssues={false} />
        : !analysis.plan ? <window.WorkbenchListControls.EmptyState kind="empty" title="当前没有可分析的正式计划。" />
        : section === 'actual' ? <Actual data={analysis} navigate={navigate} /> : section === 'downtime' ? <Downtime data={analysis} selected={selected} onSelect={onSelect} />
        : <Delivery data={analysis} selected={selected} onSelect={onSelect} onCompare={onCompare} />} />
      {section === 'delivery' && data.plan && <Section section="timeline" planRef={planRef} locateBatchRef={selected} label="计划时间轴工序" render={analysis =>
        <window.DashboardTimeline data={analysis} selectedBatch={selected} onSelect={onSelect} />} />}
      {!['material', 'actual'].includes(section) && <Section section="pressure" planRef={planRef} label="资源压力明细" render={analysis =>
        <window.DashboardPanels.Pressure data={{ ...data, analysis }} showIssues={false} navigate={navigate} />} />}
    </>;
  }
  window.DashboardAnalysisPanels = { Delivery, Downtime, Material, Actual, Section, ResourceDays, Workspace, value, risk };
})();
