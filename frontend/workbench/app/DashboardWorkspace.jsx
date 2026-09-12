(function () {
  'use strict';
  const C = window.DashboardContract, S = window.DashboardSession, P = window.DashboardPanels, { Button, ErrorBox } = window.ResourceControls;
  function durableScope(query) { const result = { ...query }; delete result.snapshot_ref; return result; }
  async function readList(api, query, signal) {
    if (query.page === 1 || query.snapshot_ref) return api.list(query, signal);
    const first = await api.list({ ...query, page: 1 }, signal);
    return api.list({ ...query, snapshot_ref: first.meta.snapshot_ref }, signal);
  }
  function Content({ start, onNavigate }) {
    const api = React.useMemo(() => C.create(), []), command = S.useCommand(api);
    const [q, setQuery] = React.useState(start.q), [tab, setTab] = React.useState(start.tab), [selected, setSelected] = React.useState(start.selected);
    const [historyPage, setHistoryPage] = React.useState(start.historyPage), [revision, refresh] = React.useReducer(n => n + 1, 0);
    const [dialog, setDialog] = React.useState(false), [navError, setNavError] = React.useState(null);
    const [navigationConfirmation, setNavigationConfirmation] = React.useState(null);
    const [outsourcing, setOutsourcing] = React.useState(null), [registrationChanged, setRegistrationChanged] = React.useState(false);
    const [analysisBatch, setAnalysisBatch] = React.useState(start.analysisBatch);
    const [comparisonState, setComparisonState] = React.useState({ context: start.comparison, caption: null });
    const onComparisonState = React.useCallback(value => setComparisonState(previous => C.equal(previous, value) ? previous : value), []);
    const analysisApi = React.useMemo(() => window.DashboardAnalysisAPI.create(), []);
    const list = S.useRead(signal => readList(api, q, signal), [api, q, revision]);
    const result = list.result, data = result && result.data, snapshot = result && result.meta.snapshot_ref;
    const analysisRead = S.useRead(signal => analysisApi.read(data && data.plan ? data.plan.plan_ref : null, signal),
      [analysisApi, data && data.plan && data.plan.plan_ref, revision], !!data && !list.loading && !list.error && !outsourcing);
    const analysisData = analysisRead.result && analysisRead.result.data;
    const detailQuery = React.useMemo(() => ({ ...q, snapshot_ref: snapshot }), [q, snapshot]);
    const handlingAvailable = q.category !== 'external' || !!data && data.categories.external.handling_supported === true;
    const detail = S.useRead(signal => api.detail(selected, detailQuery, undefined, signal), [api, selected, detailQuery], handlingAvailable && !!selected && !!snapshot);
    const history = S.useRead(signal => api.detail(selected, detailQuery, historyPage, signal), [api, selected, detailQuery, historyPage, tab], handlingAvailable && tab === 'records' && !!selected && !!snapshot);
    const item = detail.result && detail.result.data.item;
    function choose(ref) { setSelected(ref); setHistoryPage(1); }
    function change(patch, paging = false) {
      const next = { ...q, ...patch, page: paging ? patch.page : 1 }; delete next.snapshot_ref;
      if (paging) next.snapshot_ref = snapshot;
      setQuery(C.scope(next)); if (!paging) { choose(null); setDialog(false); } refresh();
    }
    function reload() { const next = { ...q, page: 1 }; delete next.snapshot_ref; setQuery(next); setHistoryPage(1); setRegistrationChanged(false); refresh(); }
    function category(k) { change({ category: k }); setAnalysisBatch(null); setComparisonState({ context: {}, caption: null }); setTab(k === 'candidate' ? 'compare' : 'items'); }
    function showAnalysis(k) { category(k); setTab('analysis'); }
    function readContext() { return { scope: durableScope(q), tab,
      ...(selected ? { item_ref: selected, history_page: historyPage } : {}), ...(analysisBatch ? { analysis_batch_ref: analysisBatch } : {}),
      ...(Object.keys(comparisonState.context).length ? { comparison: comparisonState.context } : {}) }; }
    function openTarget(n, current, overview = false) {
      P.navigationTarget(n, onNavigate);
      const context = { ...(overview ? {} : n.context), return_to: { view: 'dashboard', context: current } };
      if (n.view === 'outsourcing') { setOutsourcing(context); return; }
      if (n.view === 'batches' && context.batch_ref) context.entity_ref = context.batch_ref;
      C.check(onNavigate(n.view, context) !== false, '目标页面未接受导航，原条目仍保留。');
    }
    function navigate(n, origin) {
      try {
        setNavError(null);
        const label = P.navigationTarget(n, onNavigate), current = readContext();
        if (!n.enabled) {
          C.check(origin && origin === item && origin.item_ref === selected && origin.navigation.includes(n), '不可定位的原条目来源不一致，未打开其他对象。');
          setNavigationConfirmation({ navigation: n, item: origin, current, label });
        } else openTarget(n, current);
      } catch (error) { setNavError(error); }
    }
    function confirmNavigation() {
      try {
        openTarget(navigationConfirmation.navigation, navigationConfirmation.current, true);
        setNavigationConfirmation(null);
      } catch (error) { setNavError(error); }
    }
    function finish() { if (command.finish()) { setDialog(false); reload(); } }
    const currentSummary = data && q.category !== 'all' && data.categories[q.category];
    const external = q.category === 'external', activeTabs = external ? handlingAvailable ? { items: '处置清单', records: '处置历史' } : { items: '登记与核实历史' } : S.tabs;
    const activeTab = Object.prototype.hasOwnProperty.call(activeTabs, tab) ? tab : 'items', tabKeys = Object.keys(activeTabs);
    window.WorkbenchPageContext.useSnapshot(readContext(), !!data && !list.loading && !list.error && !detail.error);
    const comparing = !external && activeTab === 'compare', showingAnalysis = !external && activeTab === 'analysis';
    const plan = !list.loading && !list.error && !outsourcing && !comparing && (showingAnalysis
      ? !analysisRead.loading && !analysisRead.error && analysisData && analysisData.plan : data && data.plan);
    const caption = comparing ? !list.loading && !list.error && !outsourcing ? comparisonState.caption : null : plan && plan.kind === 'official' && plan.is_current_official === true ? {
      reference: plan.plan_ref, label: '当前方案', name: plan.display_name, status: '当前正式',
      ...(Number.isSafeInteger(plan.version) && plan.version > 0 ? { version: '正式 v' + plan.version } : {})
    } : null;
    window.WorkbenchCaption.useCaption(caption);
    if (outsourcing) return <div className="plana dashboard-live" data-dashboard-outsourcing data-return-item={outsourcing.return_to.context.item_ref}><window.DashboardStyles />
      <header className="dy-heading"><h2>外协物流登记</h2><Button icon="arrow-left" onClick={() => setOutsourcing(null)}>返回原值班台条目</Button></header>
      <div className="dy-note">外协物流登记概览 · 物流登记不替代风险处置。</div><window.WorkbenchReference entries={{ '原登记编号': outsourcing.outsourcing_ref }} />
      {typeof window.OutsourcingWorkspace === 'function' ? <window.OutsourcingWorkspace outsourcingRef={outsourcing.outsourcing_ref} onUpdated={() => setRegistrationChanged(true)} /> : <div className="dy-note warning" role="status">外协登记模块尚未加载。</div>}
    </div>;
    return <div className="plana dashboard-live" data-dashboard-workspace data-ready={!!data} data-analysis-ready={!!analysisData && !analysisRead.loading && !analysisRead.error} aria-busy={list.loading}><window.DashboardStyles />
      <header className="dy-heading"><div><h2 className="wb-page-title">计划员值班台</h2><div className="dy-context wb-page-context"><span>{comparing ? comparisonState.caption ? comparisonState.caption.name + ' · ' + comparisonState.caption.status : '尚未核实所选候选方案' : data ? data.plan ? data.plan.display_name + ' · 当前正式' : data.categories.delivery.state === 'no_official_plan' ? '当前无正式计划' : '正式计划未能读取' : '正式计划未加载'}</span><span>{data ? '数据截至 ' + window.WorkbenchFormat.dateTime(data.as_of) + ' · 工厂本地时间' : '数据尚未读取'}</span></div></div><div className="dy-tools"><Button icon="refresh-cw" aria-label="明确刷新值班台" busy={list.loading} disabled={command.busy} onClick={reload} />
        {command.saved && <Button icon="history" onClick={() => setDialog(true)}>{command.saved.phase === 'confirmed' ? '查看已确认回执' : '核实原处置请求'}</Button>}</div></header>
      
      <ErrorBox error={command.storageError} />{command.storageError && <Button icon="refresh-cw" onClick={command.sync}>重读原请求记录</Button>}
      {registrationChanged && <div className="dy-note warning" role="status">原物流登记已更新；当前保留离开时的筛选、条目与历史页，请明确刷新风险与处置。</div>}
      {!dialog && command.saved && <div className={'dy-note ' + (command.saved.phase === 'confirmed' ? 'success' : 'warning')}>{command.saved.phase === 'confirmed' ? '原处置回执已确认，完成核实后刷新风险与处置。' : '存在原处置请求；结果未核实前不可新建处置。'}</div>}
      <P.Overview data={data} analysis={analysisData} onCategory={category} onAnalysis={showAnalysis} /><ErrorBox error={analysisRead.error} />
      <div className="dy-work"><P.Rail data={data} category={q.category} onCategory={category} /><div className="dy-main">
        <div className="dy-section-head"><h3>{C.categories[q.category]}</h3>{currentSummary && q.category !== 'candidate' && <P.CategoryState summary={currentSummary} />}
          <label className="dy-category-picker">异常类别<select aria-label="异常类别" value={q.category} onChange={event => category(event.target.value)}>
            {Object.entries(C.categories).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select></label></div>
        <div className="dy-tabs" role="tablist" aria-label="问题详情视图">{Object.entries(activeTabs).map(([key, label], index) => <button type="button" key={key} id={'dy-tab-' + key} role="tab" className="dy-tab" aria-controls="dy-content" aria-selected={activeTab === key} tabIndex={activeTab === key ? 0 : -1}
          onClick={() => setTab(key)} onKeyDown={e => { if (e.altKey || e.ctrlKey || e.metaKey) return; let next; if (e.key === 'ArrowRight') next = (index + 1) % tabKeys.length; if (e.key === 'ArrowLeft') next = (index + tabKeys.length - 1) % tabKeys.length;
            if (e.key === 'Home') next = 0; if (e.key === 'End') next = tabKeys.length - 1; if (next !== undefined) { e.preventDefault(); setTab(tabKeys[next]); document.getElementById('dy-tab-' + tabKeys[next]).focus(); } }}>{label}</button>)}</div>
        <div className="dy-panel" role="tabpanel" id="dy-content" aria-labelledby={'dy-tab-' + activeTab}>
          <ErrorBox error={list.error || navError} />{list.error && <Button icon="refresh-cw" onClick={reload}>明确重读当前筛选</Button>}{list.loading && <window.WorkbenchListControls.EmptyState kind="loading" title="正在读取真实风险、资源与候选目录" />}
          {external && <P.ExternalRegistration summary={currentSummary} onUpdated={reload} />}
          {data && <><P.Gaps categories={data.categories} selected={q.category} />
            {external && <P.ExternalHandlingState summary={currentSummary} />}
            {handlingAvailable && activeTab === 'items' && <div className={item ? 'wb-detail-layout dy-detail-layout' : ''}><div><P.Filters query={q} busy={list.loading} onChange={change} /><P.List data={data} selected={selected} onSelect={choose} query={q} onClear={() => change({ query: '', status: 'all' })} />
              <P.Pager page={data.page} busy={list.loading} onPage={page => change({ page }, true)} onSize={size => change({ size })} />
              <ErrorBox error={detail.error} />{detail.loading && <window.WorkbenchListControls.EmptyState kind="loading" title="正在读取原条目详情" />}
              </div>{item && <P.Detail item={item} onClose={() => choose(null)} onHandle={() => setDialog(true)} onHistory={() => setTab('records')} navigate={navigate} canNavigate={typeof onNavigate === 'function'} />}</div>}
            {!external && tab === 'analysis' && <>
              {analysisRead.loading && <p role="status">正在读取同一正式计划的分析依据。</p>}
              {analysisRead.error && <Button icon="refresh-cw" onClick={reload}>明确重读分析</Button>}
              {analysisData && <><ErrorBox error={analysisRead.error} /><window.ResourceControls.Issues issues={analysisData.issues} />
                {q.category === 'material' ? <window.DashboardAnalysisPanels.Material data={analysisData} /> : analysisData.plan && (q.category === 'downtime'
                  ? <window.DashboardAnalysisPanels.Downtime data={analysisData} selected={analysisBatch} onSelect={setAnalysisBatch} />
                  : q.category === 'actual' ? <window.DashboardAnalysisPanels.Actual data={analysisData} navigate={navigate} />
                  : <window.DashboardAnalysisPanels.Delivery data={analysisData} selected={analysisBatch} onSelect={setAnalysisBatch} onCompare={() => setTab('compare')} />)}
                {!['material', 'actual'].includes(q.category) && <P.Pressure data={data} navigate={navigate} canNavigate={typeof onNavigate === 'function'} />}
              </>}
            </>}
            {!external && tab === 'compare' && (['candidate', 'delivery', 'all'].includes(q.category) ? <>
              <window.DashboardCandidates key={q.category} catalog={data.candidate_catalog} initialContext={comparisonState.context} onState={onComparisonState}
                selectedBatch={analysisBatch} onSelectBatch={setAnalysisBatch} issueBatchRef={q.category === 'delivery' ? analysisBatch || item && item.source.batch_ref || null : null} />
              <P.Candidates data={data} navigate={navigate} canNavigate={typeof onNavigate === 'function'} />
            </> : <section aria-label="本问题候选状态"><h3>本问题尚无独立候选结果</h3><p>未借用其他问题的候选作为本问题结论。</p>
              <Button icon="git-compare-arrows" onClick={() => category('candidate')}>查看现有候选方案</Button></section>)}
            {handlingAvailable && activeTab === 'records' && <window.DashboardHistory read={history} selected={selected} rows={data.items} historyPage={historyPage} onPage={setHistoryPage} onSelect={choose} onHandle={() => setDialog(true)} />}
          </>}
        </div></div></div><footer className="dy-footer"><span>正式计划 / 执行记录 / 资源日历 / 齐套事实 / 外协登记</span><span>风险与处置独立 · 外协回厂不等于工序完工</span></footer>
      {dialog && (command.saved || item) && <window.DashboardHandling key={command.saved ? command.saved.request_key : item.item_ref} item={item} command={command} onClose={() => setDialog(false)} onFinish={finish} />}
      {navigationConfirmation && <P.NavigationConfirmation entry={navigationConfirmation} error={navError}
        onClose={() => setNavigationConfirmation(null)} onConfirm={confirmNavigation} />}
    </div>;
  }
  function WorkbenchDashboardWorkspace({ initialContext = {}, onNavigate }) {
    let start; try {
      C.check(C.object(initialContext));
      const { analysis_batch_ref, comparison, ...base } = initialContext;
      C.check(analysis_batch_ref === undefined || C.ref(analysis_batch_ref));
      start = { ...S.context(base), analysisBatch: analysis_batch_ref || null,
        comparison: window.DashboardCandidateComparisonAPI.context(comparison === undefined ? {} : comparison) };
      start.q = durableScope(start.q);
    } catch (error) { return <div className="plana dashboard-live"><window.DashboardStyles /><h2 className="wb-page-title">计划员值班台</h2><ErrorBox error={error} /></div>; }
    return <Content key={JSON.stringify(start)} start={start} onNavigate={onNavigate} />;
  }
  window.WorkbenchDashboardWorkspace = WorkbenchDashboardWorkspace;
})();
