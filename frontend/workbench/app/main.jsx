(function () {
  'use strict';
  const root = document.getElementById('root');
  const fail = message => {
    root.setAttribute('data-workbench-boot', 'failed');
    const alert = document.createElement('p'); alert.setAttribute('role', 'alert'); alert.textContent = message;
    const retry = document.createElement('a'); retry.href = location.href; retry.textContent = '重新加载'; root.replaceChildren(alert, retry);
  };
  let boot;
  try {
    boot = JSON.parse(document.getElementById('workbench-boot').textContent);
    if (!boot || typeof boot !== 'object' || Array.isArray(boot)) throw new Error('Invalid boot object');
  }
  catch (_) { fail('工作台启动信息无法读取，请重新打开本机应用。'); return; }
  if (boot.messages !== undefined && (!Array.isArray(boot.messages) || boot.messages.some(value => !value
      || typeof value.category !== 'string' || typeof value.message !== 'string'))) {
    fail('工作台返回消息格式不正确，请重新加载后核对原操作结果。'); return;
  }
  if (boot.schema_version !== 1 || !window.React || !window.ReactDOM || !window.APSWorkbenchUI
      || !window.APSWorkbenchTheme || !window.APSWorkbenchTransport || !window.APSWorkbenchSystemContract || typeof SystemLive !== 'function'
      || typeof window.ResourceLive !== 'function' || typeof window.WorkbenchControls !== 'function'
      || typeof window.WorkbenchControlStyles !== 'function' || typeof window.WorkbenchNumberControls !== 'function'
      || typeof window.PlanWorkspace !== 'function' || typeof window.ReportWorkspace !== 'function'
      || typeof window.ReviewWorkspace !== 'function' || typeof window.BatchWorkspace !== 'function'
      || typeof window.MasterOverviewWorkspace !== 'function' || typeof window.SystemMaintenanceWorkspace !== 'function'
      || typeof window.FieldWorkspace !== 'function' || typeof window.ActualGanttWorkspace !== 'function'
      || typeof window.PreflightWorkspace !== 'function' || typeof window.RunWorkspace !== 'function'
      || typeof window.PlanCenterWorkspace !== 'function' || typeof window.RunCandidateWorkspace !== 'function'
      || typeof window.RunHistoryWorkspace !== 'function' || typeof window.CalibrationWorkspace !== 'function'
      || typeof window.RunAdoptionAction !== 'function' || typeof window.WorkbenchTrialWorkspace !== 'function'
      || typeof window.TrialAdoptionAction !== 'function' || typeof window.WorkbenchDashboardWorkspace !== 'function'
      || !window.WorkbenchNavigation || !window.WorkbenchCaption || !window.WorkbenchPageContext || !window.WorkbenchBoundary) {
    fail('工作台资源未完整加载，请检查本机安装文件。'); return;
  }
  function href(view) {
    return window.WorkbenchNavigation.href(boot, view);
  }
  function WorkbenchShell({ view, theme, navigate, messages, dismissMessage, children }) {
    const active = view === 'delay' ? 'analysis' : view;
    return <div className="app-container operations-shell">
      <aside className="sidebar"><div className="sidebar-header">
        <span className="brand-tile" aria-label="APS 智能排产"><svg viewBox="0 0 24 24" width="18" height="18" fill="#fff" aria-hidden="true">
          <rect x="4" y="6" width="10" height="3.2" rx="1.6" /><rect x="7" y="10.4" width="12" height="3.2" rx="1.6" fillOpacity="0.92" /><rect x="4" y="14.8" width="8" height="3.2" rx="1.6" fillOpacity="0.78" />
        </svg></span><span className="brand-word">APS 智能排产</span>
      </div><nav className="sidebar-nav">{NAV_GROUPS.map(group => <div className="nav-group" key={group.title}>
        <div className="nav-group-title">{group.title}</div>{group.items.map(item => <a key={item.id}
          href={href(item.id)} title={item.label} className={'nav-item' + (active === item.id ? ' active' : '')}
          aria-current={active === item.id ? 'page' : undefined} onClick={event => {
            if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            event.preventDefault(); navigate(item.id);
          }}><Ico name={item.icon} /><span className="nav-label">{item.label}</span></a>)}
      </div>)}</nav></aside>
      <div className="main-content"><header className="top-header"><h2 className="top-title">{boot.titles[view] || '工作区不存在'}</h2>
        <window.WorkbenchCaption.Caption /><div className="header-controls"><button type="button" className="hdr-pill"
          onClick={() => window.APSWorkbenchTheme.set(theme === 'dark' ? 'light' : 'dark')}>深色：{theme === 'dark' ? '开' : '关'}</button></div>
      </header><main className="page-content">
        <style>{`.wb-server-messages { display: grid; gap: 8px; margin-bottom: 16px; }
          .wb-server-message { display: flex; align-items: flex-start; gap: 12px; padding: 10px 12px; border: 1px solid var(--ui-border); border-left: 3px solid var(--ui-primary); border-radius: 4px; background: var(--ui-surface); color: var(--ui-text); }
          .wb-server-message[data-kind="error"],.wb-server-message[data-kind="danger"] { border-left-color: #dc3545; }
          .wb-server-message[data-kind="warning"] { border-left-color: #b77900; }
          .wb-server-message[data-kind="success"] { border-left-color: #15803d; }
          .wb-server-message p { flex: 1; min-width: 0; margin: 0; overflow-wrap: anywhere; }
          .wb-server-message button { flex: 0 0 28px; width: 28px; height: 28px; display: grid; place-items: center; padding: 0; color: inherit; background: transparent; border: 0; border-radius: 4px; cursor: pointer; }
          .wb-server-message button:focus-visible { outline: 2px solid var(--ui-primary); outline-offset: 2px; }`}</style>
        {messages.length > 0 && <section className="wb-server-messages" aria-label="操作结果">{messages.map((value, index) =>
          <div className="wb-server-message" data-kind={value.category} key={index} role={['error', 'danger', 'warning'].includes(value.category) ? 'alert' : 'status'}>
            <p>{value.message}</p><button type="button" aria-label="关闭消息" title="关闭消息" onClick={() => dismissMessage(index)}><Ico name="x" /></button>
          </div>)}</section>}
        {children}</main></div>
    </div>;
  }
  function App() {
    function currentPage() {
      try { return window.WorkbenchNavigation.read(boot); }
      catch (error) { return { view: boot.view, context: {}, key: 0, error: error.message }; }
    }
    const [page, setPage] = React.useState(currentPage);
    const [messages, setMessages] = React.useState(boot.messages || []);
    const activePage = React.useRef(page), restoring = React.useRef(true);
    activePage.current = page;
    const { view, context } = page;
    const initialContext = Object.keys(context).length ? context : undefined;
    const batchAdapter = React.useMemo(() => window.APSBatchAPI.create(), []);
    const [preference, setPreference] = React.useState(window.APSWorkbenchTheme.get());
    React.useEffect(() => {
      root.setAttribute('data-workbench-boot', 'ready');
      window.dispatchEvent(new Event('aps-workbench-ready'));
    }, []);
    React.useEffect(() => window.APSWorkbenchTheme.subscribe(setPreference), []);
    React.useEffect(() => {
      const previous = history.scrollRestoration; history.scrollRestoration = 'manual';
      let frame = 0;
      const save = () => {
        if (restoring.current || activePage.current.error) return;
        try { window.WorkbenchNavigation.remember(boot, activePage.current); }
        catch (error) { setPage(old => ({ ...old, error: error.message })); }
      };
      const scroll = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(save); };
      const restore = () => { restoring.current = true; cancelAnimationFrame(frame); setMessages([]); setPage(currentPage()); };
      window.addEventListener('popstate', restore); window.addEventListener('pagehide', save);
      document.addEventListener('scroll', scroll, true);
      return () => {
        cancelAnimationFrame(frame); history.scrollRestoration = previous;
        window.removeEventListener('popstate', restore); window.removeEventListener('pagehide', save);
        document.removeEventListener('scroll', scroll, true);
      };
    }, []);
    React.useEffect(() => {
      restoring.current = true;
      if (page.error) { restoring.current = false; return undefined; }
      return window.WorkbenchNavigation.restore(page, () => { restoring.current = false; });
    }, [page.view, page.key, page.error]);
    React.useEffect(() => { document.title = (boot.titles[view] || '工作区不存在') + ' · APS 智能排产'; }, [view]);
    const navigate = (target, nextContext) => {
      if (target === view && nextContext === undefined && !page.error) return;
      try {
        if (page.error) { location.assign(href(target)); return; }
        const next = window.WorkbenchNavigation.navigate(boot, page, target, nextContext);
        restoring.current = true; setMessages([]); setPage(next);
      } catch (error) { setPage(old => ({ ...old, error: error.message })); }
    };
    const rememberTrialTarget = nextContext => {
      window.TrialContract.target(nextContext);
      const entry = currentPage();
      if (entry.view !== 'trial' || entry.key !== page.key) throw new Error('当前页面已变化，未覆盖其他页面的恢复记录。');
      window.WorkbenchNavigation.replaceContext(boot, entry, nextContext);
    };
    const rememberPage = React.useCallback(nextContext => {
      if (activePage.current.view !== view || activePage.current.key !== page.key) return;
      try { window.WorkbenchNavigation.replaceContext(boot, activePage.current, nextContext); }
      catch (error) { setPage(old => ({ ...old, error: error.message })); }
    }, [view, page.key]);
    return <><window.WorkbenchControlStyles /><window.WorkbenchControls /><window.WorkbenchNumberControls /><window.WorkbenchCaption.Styles />
    <window.WorkbenchPageContext.Provider key={view + ':' + page.key} remember={rememberPage}>
    <window.WorkbenchCaption.Provider key={view + ':' + page.key}>
    <WorkbenchShell view={view} theme={preference.theme} navigate={navigate} messages={messages}
      dismissMessage={index => setMessages(items => items.filter((_value, current) => current !== index))}>
      {preference.error && <p role="alert" className="sm-error">{preference.error}</p>}
      <window.WorkbenchBoundary key={view + ':' + page.key}>
      {page.error ? <p role="alert" className="sm-error">{page.error}</p>
      : view === 'dashboard' ? <window.WorkbenchDashboardWorkspace key={view + ':' + page.key} onNavigate={navigate} initialContext={initialContext} />
      : view === 'system' ? <SystemLive boot={boot} theme={preference.theme} initialContext={initialContext} /> : view === 'process' ? <window.ResourceLive key={view + ':' + page.key} onNavigate={navigate} initialContext={initialContext} />
      : view === 'batches' ? <window.BatchWorkspace key={view + ':' + page.key} adapter={batchAdapter} onNav={navigate} initialContext={initialContext} />
      : view === 'analysis' || view === 'gantt' || view === 'delay' ? <window.PlanCenterWorkspace key={view + ':' + page.key} view={view} onNavigate={navigate} initialContext={initialContext} />
      : view === 'reports' ? <window.ReportWorkspace key={view + ':' + page.key} onNav={navigate} initialContext={initialContext} />
      : view === 'review' ? <window.ReviewWorkspace key={view + ':' + page.key} onNav={navigate} initialContext={initialContext} />
      : view === 'calib' ? <window.CalibrationWorkspace key={view + ':' + page.key} onNavigate={navigate} initialContext={initialContext} />
      : view === 'basedata' ? <window.MasterOverviewWorkspace key={view + ':' + page.key} onNavigate={navigate} initialContext={initialContext} />
      : view === 'field' ? <window.FieldWorkspace key={view + ':' + page.key} onNavigate={navigate} initialContext={initialContext} />
      : view === 'fieldgantt' ? <window.ActualGanttWorkspace key={view + ':' + page.key} onNavigate={navigate} initialContext={initialContext} />
      : view === 'run' ? <window.RunWorkspace key={view + ':' + page.key} onNavigate={navigate} initialContext={initialContext} />
      : view === 'trial' ? <window.WorkbenchTrialWorkspace key={view + ':' + page.key} onNavigate={navigate} initialTarget={initialContext} onTargetChange={rememberTrialTarget}
        renderAdoption={props => <window.TrialAdoptionAction {...props} />} />
      : <section className="wb-page-panel" aria-label={boot.titles[view] || '工作区不存在'}>
        <h2>{boot.titles[view] || '工作区不存在'}</h2><p role="status">该工作区尚未接入真实数据，暂不提供业务操作。</p>
      </section>}
      </window.WorkbenchBoundary>
    </WorkbenchShell></window.WorkbenchCaption.Provider></window.WorkbenchPageContext.Provider></>;
  }
  ReactDOM.createRoot(root).render(<App />);
})();
