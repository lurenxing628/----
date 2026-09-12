(function () {
  'use strict';
  const C = window.DashboardContract, { Button, Issues } = window.ResourceControls;
  const navigationLabels = { gantt: '计划甘特', fieldgantt: '现场实际', batches: '批次资料', analysis: '候选方案', field: '现场报工', outsourcing: '外协物流登记' };
  function navigationTarget(n, onNavigate) {
    C.check(C.object(n) && Object.prototype.hasOwnProperty.call(navigationLabels, n.view)
      && C.object(n.context) && typeof n.enabled === 'boolean', '导航目标未知或上下文无效，未打开默认页面。');
    C.check(n.view === 'outsourcing' ? typeof window.OutsourcingWorkspace === 'function' : typeof onNavigate === 'function', '对象导航尚未接入，原条目仍保留。');
    C.check(n.enabled || typeof n.reason === 'string' && n.reason.trim().length > 0, '原对象不可定位的原因缺失，未打开其他对象。');
    return navigationLabels[n.view];
  }
  const value = v => v === null || v === undefined || v === '' ? '未填写' : typeof v === 'boolean' ? v ? '是' : '否' : String(v);
  const hours = v => window.WorkbenchFormat.hours(v, 2);
  function Risk({ risk }) { return <span className={'dy-badge ' + (risk.active === true ? 'danger' : risk.active === false ? 'success' : 'warning')}>{risk.active === true ? '风险仍在' : risk.active === false ? '当前无风险' : '风险未知'}</span>; }
  function Status({ handling }) { return <span className={'dy-badge ' + ({ new: 'neutral', following: 'info', awaiting_verification: 'warning', closed: 'success' }[handling.status])}>{C.statuses[handling.status]}</span>; }
  function CategoryState({ summary }) {
    if (!summary) return <span>未加载</span>;
    return <><span>{C.states[summary.state]}{summary.risk_count === null ? ' · 总风险未知' : ' · ' + summary.risk_count + ' 项风险'}</span>
      {summary.risk_count === null && summary.known_risk_count > 0 && <small>已确认 {summary.known_risk_count} 项风险</small>}</>;
  }
  function Overview({ data, analysis, onCategory, onAnalysis }) { return <div className="dy-metrics" aria-label="风险概览">{['delivery', 'pressure', 'actual', 'external', 'downtime', 'material', 'pending'].map(k => {
    if (k === 'pressure' || k === 'pending') {
      const p = analysis && analysis[k === 'pressure' ? 'pressure' : 'pending'];
      return <button type="button" className="dy-metric" key={k} onClick={() => onAnalysis(k === 'pressure' ? 'delivery' : 'material')}>
        <span>{k === 'pressure' ? '资源压力' : '待排批次'}</span><strong>{!p ? '未读取' : p.count === null ? '未知' : p.count}</strong>
        <small>{k === 'pressure' ? '≥90% · 同范围日峰值' : '本机待排批次池'}</small>
        {p && k === 'pressure' && (p.unknown_resources > 0 || p.zero_capacity_resources > 0) && <small>容量未知 {p.unknown_resources} · 零可用 {p.zero_capacity_resources}</small>}
      </button>;
    }
    const s = data && data.categories[k]; return <button type="button" className="dy-metric" key={k} onClick={() => onCategory(k)}><span>{C.categories[k]}</span>
      <strong className={s && s.risk_count > 0 ? 'dy-danger' : 'dy-muted'}>{!s ? '未加载' : s.risk_count === null ? C.states[s.state] === '已读取' ? '未知' : C.states[s.state] : s.risk_count}</strong>
      <small>{!s ? '等待读取' : k === 'external' ? s.awaiting_return_count === null ? '外协风险投影未读取' : '待回厂 ' + s.awaiting_return_count + ' · 超期 ' + s.overdue_count + ' · 待确认 ' + s.awaiting_confirmation_count :
        s.risk_count === null ? s.known_risk_count > 0 ? '已确认风险 ' + s.known_risk_count + ' 项' : '总风险未评估' : '已关闭处置 ' + s.closed_count + ' 项'}</small></button>;
  })}</div>; }
  function Rail({ data, category, onCategory }) { return <aside className="dy-rail" aria-label="风险类别"><h3>需要关注</h3>{Object.entries(C.categories).map(([k, label]) => <button
    type="button" className="dy-category" key={k} aria-pressed={category === k} onClick={() => onCategory(k)}><b>{label}</b>
    <small>{k === 'all' ? '风险与处置分别核对' : k === 'candidate' ? data ? C.states[data.candidate_catalog.state] + ' · 目录不计风险' : '未加载' : <CategoryState summary={data && data.categories[k]} />}</small></button>)}</aside>; }
  function Filters({ query, busy, onChange }) {
    const [draft, setDraft] = React.useState(query.query); React.useEffect(() => setDraft(query.query), [query.query]);
    return <form className="dy-filters" onSubmit={e => { e.preventDefault(); onChange({ query: draft }); }}>
      <label className="dy-search">条目搜索<input type="search" aria-label="搜索条目、责任人、行动或备注" value={draft} maxLength={200} onChange={e => setDraft(e.target.value)} /></label>
      <label>处置状态<select aria-label="处置状态" value={query.status} onChange={e => onChange({ status: e.target.value })}><option value="all">全部状态</option><option value="open">未关闭</option>{Object.entries(C.statuses).map(([k, label]) => <option value={k} key={k}>{label}</option>)}</select></label>
      <label>排序<select aria-label="排序" value={query.sort} onChange={e => onChange({ sort: e.target.value })}>{[['subject', '对象'], ['category', '风险类别'], ['status', '处置状态'], ['deadline', '责任期限']].map(([k, label]) => <option key={k} value={k}>{label}</option>)}</select></label>
      <Button reasonDisplay="inline" icon="chevron-down" className={'btn dy-sort-' + query.direction} aria-label={query.direction === 'asc' ? '改为降序' : '改为升序'} onClick={() => onChange({ direction: query.direction === 'asc' ? 'desc' : 'asc' })} />
      <Button reasonDisplay="inline" type="submit" icon="search" aria-label="执行条目搜索" busy={busy} /><Button reasonDisplay="inline" icon="x" aria-label="清除条目筛选" onClick={() => { setDraft(''); onChange({ query: '', status: 'all' }); }} />
    </form>;
  }
  function Pager({ page, busy, onPage, onSize, label = '清单' }) { return <window.WorkbenchListControls.Pager page={page} sizes={[10, 20, 50, 100].concat([page.size]).filter((v, i, a) => a.indexOf(v) === i).sort((a, b) => a - b)} busy={busy} onPage={onPage} onSize={onSize} label={label} sizeLabel="每页条目数" unit="项" />; }
  function List({ data, selected, onSelect, query, onClear }) {
    const filtered = !!query && (query.query !== '' || query.status !== 'all');
    if (!data.items.length) return <window.WorkbenchListControls.EmptyState kind={filtered ? 'filtered' : 'empty'} title={data.page.total === 0 ? '当前筛选没有条目。' : '当前页没有条目。'} hint={data.categories.external.state === 'not_connected' ? '外协风险投影尚未接入，不代表零风险。' : '仅表示当前读取范围；未读取或无法评估的来源仍单独列示。'} action={filtered ? <Button reasonDisplay="inline" icon="x" onClick={onClear}>清除筛选并查看处置清单</Button> : null} />;
    return <div className="wb-table-frame dy-scroll" data-sticky-head data-sticky-actions><table className="wb-table dy-table"><caption className="wb-sr-only">值班台风险与处置清单</caption><thead><tr><th scope="col" className="wb-col-key">对象 / 类别</th><th scope="col">风险事实</th><th scope="col">处置状态</th><th scope="col">责任人 / 期限</th><th scope="col" className="wb-col-actions">操作</th></tr></thead><tbody>{data.items.map(row => <tr key={row.item_ref} data-item-ref={row.item_ref} data-category={row.category} data-selected={selected === row.item_ref}>
      <td className="wb-col-key"><b>{row.subject}</b><div className="dy-muted">{C.categories[row.category]}</div></td><td><Risk risk={row.risk} /><div>{row.risk.message}</div></td>
      <td><Status handling={row.handling} /><div className="dy-muted">历史 {row.handling.history_count} 条</div></td><td>{value(row.handling.owner)}<div className={row.handling.deadline_overdue ? 'dy-danger' : 'dy-muted'}>{value(row.handling.deadline)}{row.handling.deadline_overdue ? ' · 处置逾期' : ''}</div></td>
      <td className="wb-col-actions"><Button reasonDisplay="inline" className="mini" icon="search" aria-label={'查看 ' + row.subject + ' ' + C.categories[row.category]} onClick={() => onSelect(row.item_ref)}>详情</Button></td></tr>)}</tbody></table></div>;
  }
  function Gaps({ categories, selected }) {
    const rows = Object.entries(categories).filter(([key]) => selected === 'all' || key === selected), seen = new Set(), issues = [];
    let count = 0;
    rows.forEach(([, summary]) => summary.issues.forEach(issue => { count += 1; const key = JSON.stringify(issue); if (!seen.has(key)) { seen.add(key); issues.push(issue); } }));
    return <><Issues issues={issues} />{count > issues.length && <details className="dy-evidence"><summary>查看各来源读取状态</summary><dl className="dy-facts">{rows.filter(([, summary]) => summary.issues.length).map(([key, summary]) => <div key={key}><dt>{C.categories[key]}</dt><dd><CategoryState summary={summary} /></dd></div>)}</dl></details>}
      {rows.map(([key, summary]) => summary.evaluation_gaps.length > 0 && <details key={key} className="dy-evidence"><summary>{C.categories[key]} · 无法评估 {summary.unknown_count} 项</summary>
        {summary.evaluation_gaps.map(gap => <p key={gap.source_ref}>{gap.subject}：{gap.message}</p>)}</details>)}</>;
  }
  function Facts({ handling }) { return <><dl className="dy-facts">{['status', ...C.fields.filter(k => k !== 'evidence_ref')].map(k => <div key={k}><dt>{C.labels[k]}</dt><dd>{k === 'status' ? C.statuses[handling.status] : k === 'completed_at' ? window.WorkbenchFormat.dateTime(handling[k]) : value(handling[k])}</dd></div>)}</dl>{handling.evidence_ref ? <window.WorkbenchReference entries={{ '已核验附件编号': handling.evidence_ref }} /> : <p className="dy-muted">未关联已核验附件</p>}</>; }
  function Evidence({ source }) { return <window.DashboardEvidence.Evidence source={source} />; }
  function Detail({ item, onHandle, onHistory, navigate, canNavigate, onClose }) { return <window.WorkbenchDetailPanel title="风险条目详情" subtitle={item.subject + ' · ' + C.categories[item.category]} detailKey={item.item_ref} onClose={onClose}><section className="dy-detail" aria-label="条目详情" data-detail-ref={item.item_ref}>
    <div className="dy-heading"><h3>{item.subject} · {C.categories[item.category]}</h3><div className="dy-tools"><Risk risk={item.risk} /><Status handling={item.handling} /></div></div>
    <p>{item.risk.message}</p><Facts handling={item.handling} /><Evidence source={item.source} /><div className="dy-tools">
      <Button reasonDisplay="inline" icon={item.handling.status === 'closed' ? 'refresh-cw' : 'square-pen'} onClick={onHandle}>{item.handling.status === 'closed' ? '独立重开' : '登记处置'}</Button>
      <Button reasonDisplay="inline" icon="history" onClick={onHistory}>查看处置历史</Button>{item.navigation.map((n, i) => <Button reasonDisplay="inline" key={i} icon="arrow-right" onClick={() => navigate(n, item)}>{n.view === 'outsourcing' ? '原外协物流登记' : navigationLabels[n.view] || '未知导航目标'}</Button>)}
      {item.category === 'actual' && item.navigation.some(n => n.enabled && n.command_context === 'read_execution_write_context') && <Button reasonDisplay="inline" icon="arrow-right" reason={!canNavigate ? '现场报工入口尚未接入' : ''} onClick={() => navigate({ ...item.navigation[0], view: 'field' })}>现场报工</Button>}
    </div>{item.category === 'external' && <div className="dy-note">关闭风险处置不代表已回厂，也不代表工序完工。物流事实与处置历史分别保留。</div>}{item.handling.status === 'closed' && <div className="dy-note">处置已关闭，风险按当前真实来源继续评估。</div>}</section></window.WorkbenchDetailPanel>; }
  function NavigationConfirmation({ entry, error, onClose, onConfirm }) {
    const { Modal, ErrorBox } = window.ResourceControls, { item, navigation, label } = entry;
    return <Modal title="原对象暂不可定位" icon="circle-alert" onClose={onClose} footer={<>
      <Button reasonDisplay="inline" icon="x" onClick={onClose}>取消</Button><Button reasonDisplay="inline" icon="arrow-right" onClick={onConfirm}>打开{label}概览</Button></>}>
      <div className="modal-b scroll" style={{ overflowWrap: 'anywhere' }}><h3>{item.subject} · {C.categories[item.category]}</h3><p role="status">{navigation.reason}</p>
        <div className="dy-context">{item.source_state === 'current' ? '当前来源' : '原来源当前未评估'}</div><window.WorkbenchReference entries={{ '原条目编号': item.item_ref }} />
        <Evidence source={item.source} /><p>原条目与处置状态保持不变。</p><ErrorBox error={error} /></div>
    </Modal>;
  }
  function Pressure({ data, navigate, canNavigate }) {
    const p = data.resource_pressure, rows = p.resources;
    return <section aria-label="真实资源压力"><div className="dy-heading"><h3>正式计划资源压力</h3>{data.plan && <Button reasonDisplay="inline" icon="arrow-right" reason={!canNavigate ? '对象导航尚未接入' : ''} onClick={() => navigate({ view: 'gantt', context: { plan_ref: data.plan.plan_ref }, enabled: true })}>计划甘特</Button>}</div>
      <div className="dy-context">{data.plan ? data.plan.display_name : data.categories.delivery.state === 'no_official_plan' ? '无正式计划' : '正式计划未能读取'} · {p.time_scope ? window.WorkbenchFormat.dateTime(p.time_scope.range_start) + ' 至 ' + window.WorkbenchFormat.dateTime(p.time_scope.range_end) + ' · 工厂本地 · 左闭右开' : '时间范围未读取'}</div>
      <Issues issues={p.issues} /><div className="dy-note">占用小时不是有效加工工时；可用产能未知时利用率保持未知。停机和日历按同一正式计划核对。</div>
      {!rows || !rows.length ? <window.WorkbenchListControls.EmptyState kind="empty" title={!rows ? '资源压力无法评估，未显示零负荷。' : '当前正式计划没有资源占用数据。'} /> : <div className="dy-scroll"><table className="dy-resource"><caption className="wb-sr-only">正式计划资源压力</caption><thead><tr><th scope="col">资源</th><th scope="col">占用 / 安排</th><th scope="col">可用</th><th scope="col">{window.WorkbenchTerms.utilization}</th><th scope="col">重叠占用</th><th scope="col">日历外占用</th><th scope="col">容量缺口</th></tr></thead><tbody>{rows.map(r => <tr key={r.kind + r.resource_ref} data-resource-ref={r.resource_ref}><td><b>{r.label || '名称未提供'}</b><div className="dy-muted">{r.kind === 'machine' ? '设备' : '人员'} · {r.operation_count} 道工序</div></td>
        <td>{hours(r.occupied_hours)} / {hours(r.arranged_hours)}</td><td>{hours(r.available_hours)}</td><td>{window.WorkbenchFormat.percent(r.utilization)}{r.utilization !== null && <div className={'dy-meter' + (r.capacity_insufficient || r.has_overlap ? ' hot' : '')}><i style={{ width: Math.min(100, Math.max(0, r.utilization * 100)) + '%' }} /></div>}</td>
        <td className={r.has_overlap ? 'dy-danger' : ''}>{hours(r.overlap_hours)}</td><td className={r.outside_available_hours > 0 ? 'dy-warning' : ''}>{hours(r.outside_available_hours)}</td><td>{hours(r.capacity_shortfall_hours)}<Issues issues={r.issues} /></td></tr>)}</tbody></table></div>}
    </section>;
  }
  function Candidates({ data, navigate, canNavigate }) {
    const c = data.candidate_catalog, runStates = { queued: '排队中', running: '计算中', complete: '计算完成', partial: '部分完成', failed: '失败', interrupted: '已中断' };
    return <section aria-label="真实候选目录"><div className="dy-heading"><h3>候选方案目录</h3><Button reasonDisplay="inline" icon="history" reason={!canNavigate ? '候选导航尚未接入' : ''} onClick={() => navigate({ view: 'analysis', context: { source: 'run_history' }, enabled: true })}>完整运行目录</Button></div>
      <div className="dy-note">已保存运行目录 · 非当前正式计划</div><Issues issues={c.issues} />
      {c.state === 'unavailable' ? <window.WorkbenchListControls.EmptyState kind="empty" title="候选目录未能读取。" hint="请使用页面刷新重试，当前不能判断候选数量。" /> : !c.runs.length ? <window.WorkbenchListControls.EmptyState kind="empty" title="尚无排产运行记录。" /> : <><div className="dy-scroll"><table><caption className="wb-sr-only">候选方案运行目录</caption><thead><tr><th scope="col">运行受理时间</th><th scope="col">计算状态</th><th scope="col">候选数量</th><th scope="col">范围</th><th scope="col">操作</th></tr></thead><tbody>{c.runs.map(r => <tr key={r.run_ref} data-run-ref={r.run_ref}><td>{window.WorkbenchFormat.dateTime(r.accepted_at)}</td><td>{runStates[r.state] || '状态未知'}</td><td>{r.candidate_count}</td><td>{r.scope_summary ? value(r.scope_summary.batch_count) + ' 个批次' : '范围未知'}</td><td><Button reasonDisplay="inline" icon="arrow-right" reason={!canNavigate ? '候选导航尚未接入' : ''} onClick={() => navigate({ view: 'analysis', context: { run_ref: r.run_ref }, enabled: true })}>查看候选</Button></td></tr>)}</tbody></table></div>
        <div className="dy-pager">目录 {c.page.total} 次 · 当前 {c.runs.length} 次{c.page.has_more ? ' · 还有更多，请进入完整运行目录' : ''}</div></>}
    </section>;
  }
  function ExternalRegistration({ summary, onUpdated }) { return <>{summary && <section aria-label="外协真实汇总"><dl className="dy-facts">
    {[['receipt_count', '保留登记'], ['current_receipt_count', '来源有效登记'], ['awaiting_return_count', '待回厂'], ['overdue_count', '超期未回'], ['returned_count', '已回厂'],
      ['awaiting_confirmation_count', '待确认'], ['unregistered_count', '未登记工序'], ['source_gap_count', '来源缺口']].map(([k, label]) => <div key={k}><dt>{label}</dt><dd data-external-count={k}>{summary[k] === null ? '未知' : summary[k]}</dd></div>)}
    </dl><div className="dy-context">已确认风险 {summary.known_risk_count} 项{summary.risk_count === null ? ' · 总风险未知' : ''} · 登记与核实历史独立保留</div></section>}
    {typeof window.OutsourcingWorkspace === 'function' ? <window.OutsourcingWorkspace onUpdated={onUpdated} /> : <div className="dy-note warning" role="status">外协登记模块尚未加载。</div>}</>; }
  function ExternalHandlingState({ summary }) { return <section aria-label="外协风险处置"><h3>外协风险处置</h3>
    {summary.handling_supported ? <div className="dy-context">已登记处置 {summary.handling_count} 项 · 已关闭处置 {summary.closed_count} 项 · 关闭不改变真实回厂状态</div> : <div className="dy-note warning" role="status">{summary.handling_state === 'unavailable' ? '外协处置台账不可用' : '外协风险处置尚未接入'} · 处置数量未知，未显示为零。</div>}
    <Issues issues={summary.handling_issues || []} /></section>; }
  window.DashboardPanels = { Overview, Rail, Filters, Pager, List, Gaps, Facts, Evidence, Detail, NavigationConfirmation, navigationTarget, Pressure, Candidates, Risk, Status, CategoryState, value, ExternalRegistration, ExternalHandlingState };
})();
