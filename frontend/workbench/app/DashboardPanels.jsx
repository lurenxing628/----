(function () {
  'use strict';
  const C = window.DashboardContract, { Button, Issues } = window.ResourceControls;
  // 跳转标签与侧栏视图标题保持同名（web/routes/workbench/navigation_metadata.py VIEW_TITLES）；outsourcing 是页内目标，侧栏没有对应条目。
  const navigationLabels = { gantt: '计划甘特', fieldgantt: '现场实际甘特', batches: '批次管理', analysis: '选择排产方案', field: '现场记录', run: '执行排产', outsourcing: '外协物流登记' };
  function navigationTarget(n, onNavigate) {
    C.check(C.object(n) && Object.prototype.hasOwnProperty.call(navigationLabels, n.view)
      && C.object(n.context) && typeof n.enabled === 'boolean', '这条记录的跳转目标不对，页面没有跳转。请刷新后重试。');
    C.check(n.view === 'outsourcing' ? typeof window.OutsourcingWorkspace === 'function' : typeof onNavigate === 'function', 'dependency not wired: window.OutsourcingWorkspace / props.onNavigate');
    C.check(n.enabled || typeof n.reason === 'string' && n.reason.trim().length > 0, '这条记录暂时打不开，页面没有跳转。请刷新后重试。');
    return navigationLabels[n.view];
  }
  const value = v => v === null || v === undefined || v === '' ? '未填写' : typeof v === 'boolean' ? v ? '是' : '否' : String(v);
  const hours = v => window.WorkbenchFormat.hours(v, 2);
  function Risk({ risk }) { return <span className={'dy-badge ' + (risk.active === true ? 'danger' : risk.active === false ? 'success' : 'warning')}>{risk.active === true ? '风险仍在' : risk.active === false ? '当前无风险' : '风险未知'}</span>; }
  function Status({ handling }) { return <span className={'dy-badge ' + ({ new: 'neutral', following: 'info', awaiting_verification: 'warning', closed: 'success' }[handling.status])}>{C.statuses[handling.status]}</span>; }
  function CategoryState({ summary }) {
    if (!summary) return <span>未读取</span>;
    return <><span>{C.states[summary.state]}{summary.risk_count === null ? ' · 总风险未知' : ' · ' + summary.risk_count + ' 项风险'}</span>
      {summary.risk_count === null && summary.known_risk_count > 0 && <small>已确认 {summary.known_risk_count} 项风险</small>}</>;
  }
  function Overview({ data, analysis, onCategory, onAnalysis }) { return <div className="dy-metrics" aria-label="风险概览">{['delivery', 'pressure', 'actual', 'external', 'downtime', 'material', 'pending'].map(k => {
    if (k === 'pressure' || k === 'pending') {
      const p = analysis && analysis[k === 'pressure' ? 'pressure' : 'pending'];
      return <button type="button" className="dy-metric" key={k} onClick={() => onAnalysis(k === 'pressure' ? 'delivery' : 'material')}>
        <span>{k === 'pressure' ? '资源压力' : '待排批次'}</span><strong>{!p ? '未读取' : p.count === null ? '未知' : p.count}</strong>
        <small>{k === 'pressure' ? '≥90% · 同范围日峰值' : '本机全部待排批次'}</small>
        {p && k === 'pressure' && (p.unknown_resources > 0 || p.zero_capacity_resources > 0) && <small>容量未知 {p.unknown_resources} · 零可用 {p.zero_capacity_resources}</small>}
      </button>;
    }
    const s = data && data.categories[k]; return <button type="button" className="dy-metric" key={k} onClick={() => onCategory(k)}><span>{C.categories[k]}</span>
      <strong className={s && s.risk_count > 0 ? 'dy-danger' : 'dy-muted'}>{!s ? '未读取' : s.risk_count === null ? C.states[s.state] === '已读取' ? '未知' : C.states[s.state] : s.risk_count}</strong>
      <small>{!s ? '未读取' : k === 'external' ? s.awaiting_return_count === null ? '外协风险未读取' : '待回厂 ' + s.awaiting_return_count + ' · 超期 ' + s.overdue_count + ' · 待确认 ' + s.awaiting_confirmation_count :
        s.risk_count === null ? s.known_risk_count > 0 ? '已确认风险 ' + s.known_risk_count + ' 项' : '总风险未评估' : '已关闭处置 ' + s.closed_count + ' 项'}</small></button>;
  })}</div>; }
  function Rail({ data, category, onCategory }) { return <aside className="dy-rail" aria-label="风险类别"><h3>需要关注</h3>{Object.entries(C.categories).map(([k, label]) => <button
    type="button" className="dy-category" key={k} aria-pressed={category === k} onClick={() => onCategory(k)}><b>{label}</b>
    <small>{k === 'all' ? '' : k === 'candidate' ? data ? C.states[data.candidate_catalog.state] : '未读取' : <CategoryState summary={data && data.categories[k]} />}</small></button>)}</aside>; }
  function Filters({ query, busy, onChange }) {
    const [draft, setDraft] = React.useState(query.query); React.useEffect(() => setDraft(query.query), [query.query]);
    return <form className="dy-filters" onSubmit={e => { e.preventDefault(); onChange({ query: draft }); }}>
      <label className="dy-search">条目搜索<input type="search" aria-label="搜索条目、责任人、行动或备注" value={draft} maxLength={200} onChange={e => setDraft(e.target.value)} /></label>
      <label>处置状态<select aria-label="处置状态" value={query.status} onChange={e => onChange({ status: e.target.value })}><option value="all">全部状态</option><option value="open">未关闭</option>{Object.entries(C.statuses).map(([k, label]) => <option value={k} key={k}>{label}</option>)}</select></label>
      <label>排序<select aria-label="排序" value={query.sort} onChange={e => onChange({ sort: e.target.value })}>{[['subject', '涉及记录'], ['category', '风险类别'], ['status', '处置状态'], ['deadline', '责任期限']].map(([k, label]) => <option key={k} value={k}>{label}</option>)}</select></label>
      <Button reasonDisplay="inline" icon="chevron-down" className={'btn dy-sort-' + query.direction} aria-label={query.direction === 'asc' ? '改为降序' : '改为升序'} onClick={() => onChange({ direction: query.direction === 'asc' ? 'desc' : 'asc' })} />
      <Button reasonDisplay="inline" type="submit" icon="search" aria-label="执行条目搜索" busy={busy} /><Button reasonDisplay="inline" icon="x" aria-label="清除条目筛选" onClick={() => { setDraft(''); onChange({ query: '', status: 'all' }); }} />
    </form>;
  }
  function Pager({ page, busy, onPage, onSize, label = '清单' }) { return <window.WorkbenchListControls.Pager page={page} sizes={[10, 20, 50, 100].concat([page.size]).filter((v, i, a) => a.indexOf(v) === i).sort((a, b) => a - b)} busy={busy} onPage={onPage} onSize={onSize} label={label} sizeLabel="每页条目数" unit="项" />; }
  function List({ data, selected, onSelect, query, onClear }) {
    const filtered = !!query && (query.query !== '' || query.status !== 'all');
    if (!data.items.length) return <window.WorkbenchListControls.EmptyState kind={filtered ? 'filtered' : 'empty'} title={data.page.total === 0 ? '当前筛选没有条目。' : '当前页没有条目。'} hint={data.categories.external.state === 'not_connected' ? '外协风险功能尚未启用。' : undefined} action={filtered ? <Button reasonDisplay="inline" icon="x" onClick={onClear}>清除筛选并查看处置清单</Button> : null} />;
    return <div className="wb-table-frame dy-scroll" data-sticky-head data-sticky-actions><table className="wb-table dy-table"><caption className="wb-sr-only">值班台风险与处置清单</caption><thead><tr><th scope="col" className="wb-col-key">涉及记录 / 类别</th><th scope="col">风险说明</th><th scope="col">处置状态</th><th scope="col">责任人 / 期限</th><th scope="col" className="wb-col-actions">操作</th></tr></thead><tbody>{data.items.map(row => <tr key={row.item_ref} data-item-ref={row.item_ref} data-category={row.category} data-selected={selected === row.item_ref}>
      <td className="wb-col-key"><b>{row.subject}</b><div className="dy-muted">{C.categories[row.category]}</div></td><td><Risk risk={row.risk} /><div>{row.risk.message}</div></td>
      <td><Status handling={row.handling} /><div className="dy-muted">历史 {row.handling.history_count} 条</div></td><td>{value(row.handling.owner)}<div className={row.handling.deadline_overdue ? 'dy-danger' : 'dy-muted'}>{value(row.handling.deadline)}{row.handling.deadline_overdue ? ' · 处置超期' : ''}</div></td>
      <td className="wb-col-actions"><Button reasonDisplay="inline" className="mini" icon="search" aria-label={'查看 ' + row.subject + ' ' + C.categories[row.category]} onClick={() => onSelect(row.item_ref)}>详情</Button></td></tr>)}</tbody></table></div>;
  }
  function Gaps({ categories, selected }) {
    const rows = Object.entries(categories).filter(([key]) => selected === 'all' || key === selected), seen = new Set(), issues = [];
    let count = 0;
    rows.forEach(([, summary]) => summary.issues.forEach(issue => { count += 1; const key = JSON.stringify(issue); if (!seen.has(key)) { seen.add(key); issues.push(issue); } }));
    return <><Issues issues={issues} />{count > issues.length && <details className="dy-evidence"><summary>查看各来源读取状态</summary><dl className="dy-facts">{rows.filter(([, summary]) => summary.issues.length).map(([key, summary]) => <div key={key}><dt>{C.categories[key]}</dt><dd><CategoryState summary={summary} /></dd></div>)}</dl></details>}
      {rows.map(([key, summary]) => {
        if (!summary.evaluation_gaps.length) return null;
        const groups = new Map();
        summary.evaluation_gaps.forEach(gap => {
          const reason = JSON.stringify([gap.code, gap.message]);
          if (!groups.has(reason)) groups.set(reason, { message: gap.message, items: [] });
          groups.get(reason).items.push(gap);
        });
        const operationGaps = summary.evaluation_gaps.every(gap => gap.operation);
        return <details key={key} className="dy-evidence dy-gap-evidence"><summary>{C.categories[key]}暂无法评估 · {summary.unknown_count} {operationGaps ? '道工序' : '项'}</summary>
          {Array.from(groups, ([reason, group]) => {
            const operations = group.items.every(gap => gap.operation);
            return <div key={reason} className="dy-gap-group"><p className="dy-gap-reason">{group.message}</p>
              <div className="dy-gap-table-scroll" tabIndex={0} role="region" aria-label={C.categories[key] + '问题明细'}>
                <table className="dy-gap-table"><thead><tr>{operations ? <><th scope="col">工序编号</th><th scope="col">工序名称</th></> : <th scope="col">相关记录</th>}</tr></thead>
                  <tbody>{group.items.map(gap => <tr key={gap.source_ref} data-gap-source={gap.source_ref}>
                    {operations ? <><td title={gap.operation.code || undefined}>{gap.operation.code || '—'}</td><td title={gap.operation.name || undefined}>{gap.operation.name || '—'}</td></> : <td title={gap.subject}>{gap.subject}</td>}
                  </tr>)}</tbody></table>
              </div></div>;
          })}</details>;
      })}</>;
  }
  function Facts({ handling }) { return <><dl className="dy-facts">{['status', ...C.fields.filter(k => k !== 'evidence_ref')].map(k => <div key={k}><dt>{C.labels[k]}</dt><dd>{k === 'status' ? C.statuses[handling.status] : k === 'completed_at' ? window.WorkbenchFormat.dateTime(handling[k]) : value(handling[k])}</dd></div>)}</dl>{handling.evidence_ref ? <window.WorkbenchReference entries={{ '已核验附件编号': handling.evidence_ref }} /> : <p className="dy-muted">未关联已核验附件</p>}</>; }
  function Evidence({ source }) { return <window.DashboardEvidence.Evidence source={source} />; }
  function Detail({ item, onHandle, onHistory, navigate, canNavigate, onClose }) { return <window.WorkbenchDetailPanel title="风险条目详情" subtitle={item.subject + ' · ' + C.categories[item.category]} detailKey={item.item_ref} onClose={onClose}><section className="dy-detail" aria-label="条目详情" data-detail-ref={item.item_ref}>
    <div className="dy-heading"><h3>{item.subject} · {C.categories[item.category]}</h3><div className="dy-tools"><Risk risk={item.risk} /><Status handling={item.handling} /></div></div>
    <p>{item.risk.message}</p><Facts handling={item.handling} /><Evidence source={item.source} /><div className="dy-tools">
      <Button reasonDisplay="inline" icon={item.handling.status === 'closed' ? 'refresh-cw' : 'square-pen'} onClick={onHandle}>{item.handling.status === 'closed' ? '独立重开' : '登记处置'}</Button>
      <Button reasonDisplay="inline" icon="history" onClick={onHistory}>查看处置历史</Button>{item.navigation.map((n, i) => <Button reasonDisplay="inline" key={i} icon="arrow-right" onClick={() => navigate(n, item)}>{n.view === 'outsourcing' ? '外协物流登记' : navigationLabels[n.view] || '未知跳转目标'}</Button>)}
      {item.category === 'actual' && item.navigation.some(n => n.enabled && n.command_context === 'read_execution_write_context') && <Button reasonDisplay="inline" icon="arrow-right" reason={!canNavigate ? window.WorkbenchTerms.outcomes.unavailable : ''} onClick={() => navigate({ ...item.navigation[0], view: 'field' })}>{navigationLabels.field}</Button>}
    </div></section></window.WorkbenchDetailPanel>; }
  function NavigationConfirmation({ entry, error, onClose, onConfirm }) {
    const { Modal, ErrorBox } = window.ResourceControls, { item, navigation, label } = entry;
    return <Modal title="这条记录暂时打不开" icon="circle-alert" onClose={onClose} footer={<>
      <Button reasonDisplay="inline" icon="x" onClick={onClose}>取消</Button><Button reasonDisplay="inline" icon="arrow-right" onClick={onConfirm}>打开{label}概览</Button></>}>
      <div className="modal-b scroll" style={{ overflowWrap: 'anywhere' }}><h3>{item.subject} · {C.categories[item.category]}</h3><p role="status">{navigation.reason}</p>
        <div className="dy-context">{item.source_state === 'current' ? '当前来源' : '这条来源现在没有评估'}</div><window.WorkbenchReference entries={{ '条目编号': item.item_ref }} />
        <Evidence source={item.source} /><p>这条记录和它的处置状态都没有变。</p><ErrorBox error={error} /></div>
    </Modal>;
  }
  function Pressure({ data, navigate, canNavigate }) {
    const p = data.resource_pressure, rows = p.resources;
    return <section aria-label="资源压力"><div className="dy-heading"><h3>正式计划资源压力</h3>{data.plan && <Button reasonDisplay="inline" icon="arrow-right" reason={!canNavigate ? window.WorkbenchTerms.outcomes.unavailable : ''} onClick={() => navigate({ view: 'gantt', context: { plan_ref: data.plan.plan_ref }, enabled: true })}>计划甘特</Button>}</div>
      <div className="dy-context">{data.plan ? data.plan.display_name : data.categories.delivery.state === 'no_official_plan' ? '无正式计划' : '正式计划未能读取'} · {p.time_scope ? window.WorkbenchFormat.dateTime(p.time_scope.range_start) + ' 至 ' + window.WorkbenchFormat.dateTime(p.time_scope.range_end) + ' · 含起日，不含止日' : '时间范围未读取'}</div>
      <Issues issues={p.issues} />
      {!rows || !rows.length ? <window.WorkbenchListControls.EmptyState kind="empty" title={!rows ? '资源压力暂时无法计算。' : '当前正式计划没有资源占用数据。'} /> : <div className="dy-scroll"><table className="dy-resource"><caption className="wb-sr-only">正式计划资源压力</caption><thead><tr><th scope="col">资源</th><th scope="col">班表内占用（小时）</th><th scope="col">可用</th><th scope="col">整窗占用率</th><th scope="col">重叠时段</th><th scope="col">班表外占用</th><th scope="col">容量缺口</th></tr></thead><tbody>{rows.map(r => <tr key={r.kind + r.resource_ref} data-resource-ref={r.resource_ref}><td><b>{r.label || '名称未填写'}</b><div className="dy-muted">{r.kind === 'machine' ? '设备' : '人员'} · {r.operation_count} 道工序</div></td>
        <td>{hours(r.available_occupied_hours)}</td><td>{hours(r.available_hours)}</td><td>{window.WorkbenchFormat.percent(r.utilization)}{r.utilization !== null && <div className={'dy-meter' + (r.capacity_insufficient || r.has_overlap ? ' hot' : '')}><i style={{ width: Math.min(100, Math.max(0, r.utilization * 100)) + '%' }} /></div>}</td>
        <td className={r.has_overlap ? 'dy-danger' : ''}>{hours(r.overlap_hours)}</td><td className={r.outside_available_hours > 0 ? 'dy-warning' : ''}>{hours(r.outside_available_hours)}</td><td>{hours(r.capacity_shortfall_hours)}<Issues issues={r.issues} /></td></tr>)}</tbody></table></div>}
    </section>;
  }
  function Candidates({ data, navigate, canNavigate }) {
    const c = data.candidate_catalog, runStates = { queued: '排队中', running: '计算中', complete: '计算完成', partial: '部分完成', failed: '失败', interrupted: '已中断' };
    return <section aria-label="候选方案列表"><div className="dy-heading"><h3>候选方案列表</h3><div className="dy-tools"><Button reasonDisplay="inline" icon="history" reason={!canNavigate ? window.WorkbenchTerms.outcomes.unavailable : ''} onClick={() => navigate({ view: 'analysis', context: { source: 'run_history' }, enabled: true })}>排产记录</Button>
      <Button reasonDisplay="inline" icon="play" reason={!canNavigate ? window.WorkbenchTerms.outcomes.unavailable : ''} onClick={() => navigate({ view: 'run', context: {}, enabled: true })}>去执行排产</Button></div></div>
      <div className="dy-note">已保存的候选方案</div><Issues issues={c.issues} />
      {c.state === 'unavailable' ? <window.WorkbenchListControls.EmptyState kind="empty" title="候选方案列表读不到。" hint="请点「刷新」重试。" /> : !c.runs.length ? <window.WorkbenchListControls.EmptyState kind="empty" title="还没有排产记录。" /> : <><div className="dy-scroll"><table><caption className="wb-sr-only">候选方案排产记录</caption><thead><tr><th scope="col">排产提交时间</th><th scope="col">计算状态</th><th scope="col">候选数量</th><th scope="col">范围</th><th scope="col">操作</th></tr></thead><tbody>{c.runs.map(r => <tr key={r.run_ref} data-run-ref={r.run_ref}><td>{window.WorkbenchFormat.dateTime(r.accepted_at)}</td><td>{runStates[r.state] || '状态未知'}</td><td>{r.candidate_count}</td><td>{r.scope_summary ? value(r.scope_summary.batch_count) + ' 个批次' : '范围未知'}</td><td><Button reasonDisplay="inline" icon="arrow-right" reason={!canNavigate ? window.WorkbenchTerms.outcomes.unavailable : ''} onClick={() => navigate({ view: 'analysis', context: { run_ref: r.run_ref }, enabled: true })}>查看候选</Button></td></tr>)}</tbody></table></div>
        <div className="dy-pager">排产记录 {c.page.total} 次 · 当前显示 {c.runs.length} 次{c.page.has_more ? ' · 还有更多，请点「排产记录」查看' : ''}</div></>}
    </section>;
  }
  function ExternalRegistration({ summary, onUpdated }) { return <>{summary && <section aria-label="外协汇总"><dl className="dy-facts">
    {[['receipt_count', '全部登记'], ['current_receipt_count', '来源仍有效的登记'], ['awaiting_return_count', '待回厂'], ['overdue_count', '超期未回'], ['returned_count', '已回厂'],
      ['awaiting_confirmation_count', '待确认'], ['unregistered_count', '未登记工序'], ['source_gap_count', '来源缺口']].map(([k, label]) => <div key={k}><dt>{label}</dt><dd data-external-count={k}>{summary[k] === null ? '未知' : summary[k]}</dd></div>)}
    </dl><div className="dy-context">已确认风险 {summary.known_risk_count} 项{summary.risk_count === null ? ' · 总风险未知' : ''}</div></section>}
    {typeof window.OutsourcingWorkspace === 'function' ? <window.OutsourcingWorkspace onUpdated={onUpdated} /> : <div className="dy-note warning" role="status">{window.WorkbenchTerms.outcomes.unavailable}</div>}</>; }
  function ExternalHandlingState({ summary }) { return <section aria-label="外协风险处置"><h3>外协风险处置</h3>
    {summary.handling_supported ? <div className="dy-context">已登记处置 {summary.handling_count} 项 · 已关闭处置 {summary.closed_count} 项</div> : <div className="dy-note warning" role="status">{summary.handling_state === 'unavailable' ? '外协处置记录读不到' : '外协风险处置尚未开通'}</div>}
    <Issues issues={summary.handling_issues || []} /></section>; }
  window.DashboardPanels = { Overview, Rail, Filters, Pager, List, Gaps, Facts, Evidence, Detail, NavigationConfirmation, navigationTarget, Pressure, Candidates, Risk, Status, CategoryState, value, ExternalRegistration, ExternalHandlingState };
})();
