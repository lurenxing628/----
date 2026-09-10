// APS Workbench · router + readiness gate + theme
const TITLES = {
  dashboard: "值班台",
  gantt: "设备 / 人员 / 批次甘特",
  run: "执行排产",
  analysis: "选择排产方案",
  delay: "延期说明",
  review: "执行复盘",
  reports: "报表中心",
  calib: "工时定额校准",
  batches: "批次管理",
  process: "基础资料",
  field: "现场记录",
  fieldgantt: "现场实际甘特 · 计划 vs 实际",
  basedata: "主数据总览",
  system: "系统管理",
};

function App() {
  const ready = useBundleReady();
  const [view, setView] = React.useState(() => {
    const target = new URLSearchParams(window.location.search).get('view');
    return Object.prototype.hasOwnProperty.call(TITLES, target) ? target : 'dashboard';
  });
  const [viewContext, setViewContext] = React.useState({});
  const route = React.useRef({ view, contexts: {}, positions: {} });
  const [analysisScope, setAnalysisScope] = React.useState({ source: 'current' });
  const [theme, setTheme] = React.useState(() => document.documentElement.getAttribute("data-theme") || "light");
  const [, refreshPlan] = React.useReducer(n => n + 1, 0);

  const nav = React.useCallback((v, supplied, historyMode = 'push') => {
    if (!Object.prototype.hasOwnProperty.call(TITLES, v)) return;
    const previous = route.current.view;
    route.current.positions[previous] = window.scrollY;
    const context = supplied === undefined ? route.current.contexts[v] || {} : supplied;
    route.current.contexts[v] = context; route.current.view = v;
    if (['review', 'reports'].includes(v) && context.scope) setAnalysisScope(context.scope);
    setView(v); setViewContext(context);
    if (historyMode === 'push') {
      const url = new URL(window.location.href); url.searchParams.set('view', v);
      window.history.pushState({ view: v }, '', url);
    }
    const position = supplied === undefined || context.returning ? route.current.positions[v] || 0 : 0;
    requestAnimationFrame(() => requestAnimationFrame(() => window.scrollTo({ top: position, behavior: 'instant' })));
  }, []);
  React.useEffect(() => {
    const pop = () => { const target = new URLSearchParams(location.search).get('view'); nav(Object.prototype.hasOwnProperty.call(TITLES, target) ? target : 'dashboard', undefined, 'none'); };
    const update = () => refreshPlan();
    window.addEventListener('popstate', pop); window.addEventListener('aps-plan-change', update); window.addEventListener('storage', update);
    return () => { window.removeEventListener('popstate', pop); window.removeEventListener('aps-plan-change', update); window.removeEventListener('storage', update); };
  }, [nav]);
  React.useEffect(() => {
    const sync = event => {
      if (event.type === 'storage' && event.key !== 'aps_kit_theme' && event.key !== null) return;
      try {
        const next = localStorage.getItem('aps_kit_theme') === 'dark' ? 'dark' : 'light';
        setTheme(next); document.documentElement.setAttribute('data-theme', next);
      } catch (error) { console.error('读取主题偏好失败：', error); }
    };
    window.addEventListener('storage', sync); window.addEventListener('pageshow', sync); window.addEventListener('focus', sync);
    return () => { window.removeEventListener('storage', sync); window.removeEventListener('pageshow', sync); window.removeEventListener('focus', sync); };
  }, []);

  // 详情抽屉调用：跳到甘特图并高亮指定批次的关键链
  React.useEffect(() => {
    window.APSFocusBatchInGantt = (batch) => {
      window.__apsPendingGanttFocus = batch || null;
      nav("gantt");
      requestAnimationFrame(() => window.dispatchEvent(new CustomEvent("aps-gantt-focus", { detail: batch })));
    };
    return () => { try { delete window.APSFocusBatchInGantt; } catch (e) {} };
  }, []);
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("aps_kit_theme", next); } catch (e) {}
  };

  if (!ready) return <BootScreen />;

  // Active sidebar highlight: contextual drill-ins map to their parent.
  const activeId = view === "delay" ? "analysis" : view;

  let screen;
  switch (view) {
    case "dashboard": screen = <DashboardScreen onNav={nav} />; break;
    case "gantt": screen = <GanttScreen onNav={nav} mode="gantt" initialContext={viewContext} />; break;
    case "run": screen = <GanttScreen onNav={nav} mode="run" />; break;
    case "analysis": screen = <AnalysisScreen onNav={nav} />; break;
    case "delay": screen = <DelayScreen onNav={nav} initialContext={viewContext} />; break;
    case "review": screen = <ExecutionReviewScreen onNav={nav} scope={analysisScope} onScopeChange={setAnalysisScope} initialContext={viewContext} />; break;
    case "reports": screen = <ReportsScreen onNav={nav} scope={analysisScope} onScopeChange={setAnalysisScope} initialContext={viewContext} />; break;
    case "calib": screen = <CalibScreen onNav={nav} />; break;
    case "batches": screen = <BatchesScreen onNav={nav} initialContext={viewContext} />; break;
    case "process": screen = <ProcessNative onNav={nav} />; break;
    case "field": screen = <FieldRecordScreen />; break;
    case "fieldgantt": screen = <FieldGanttScreen onNav={nav} initialContext={viewContext} onSourceChange={source => setViewContext(context => { const next = { ...context, source }; route.current.contexts.fieldgantt = next; return next; })} />; break;
    case "basedata": screen = <MasterDataOverview onNav={nav} />; break;
    case "system": screen = <SystemManagementScreen theme={theme} onToggleTheme={toggleTheme} />; break;
    default: screen = <DashboardScreen onNav={nav} />;
  }

  const flush = view === "process";
  const operations = ["review", "reports", "basedata", "system"].includes(view);
  const source = viewContext.scope ? viewContext.scope.source : viewContext.source;
  const demonstration = view === "fieldgantt" && source && source !== "current";
  const planning = ['analysis', 'gantt', 'delay'].includes(view);
  const plan = window.APSPlanWorkbench.read(window.localStorage), selected = window.APSPlanWorkbench.selected(plan);
  const planContext = planning ? { version: plan.version, label: '方案样例', name: selected.name, status: window.APSPlanWorkbench.same(selected, plan.adopted) ? '已采用' : '候选预览', range: '09-08 至 09-09' }
    : view === 'dashboard' ? { ...window.APSDashboard.planContext, label: '值班台样例', name: '独立演示数据', status: '示例' }
    : view === 'field' || view === 'fieldgantt' ? { ...window.APSFieldReports.planContext, label: '现场记录样例', name: '计划 / 实际', status: '示例' } : undefined;
  return (
    <AppShell active={activeId} onNav={nav} theme={theme} onToggleTheme={toggleTheme} title={TITLES[view] || "值班台"} showCapsule={!!planContext && !demonstration} flush={flush} operations={operations}
      dashboard={view === "dashboard"} field={view === "field" || view === "fieldgantt"}
      planContext={planContext}>
      {screen}
      {flush ? null : <footer className="kit-foot">本页面使用示例数据，不代表真实生产结果；正式使用以系统实时数据为准。</footer>}
    </AppShell>
  );
}

function useBundleReady() {
  const [ready, setReady] = React.useState(!!(window.APSDesignSystem_edbc5d && window.APSDesignSystem_edbc5d.Panel));
  React.useEffect(() => {
    if (ready) return;
    const id = setInterval(() => {
      if (window.APSDesignSystem_edbc5d && window.APSDesignSystem_edbc5d.Panel) { setReady(true); clearInterval(id); }
    }, 120);
    return () => clearInterval(id);
  }, [ready]);
  return ready;
}

function BootScreen() {
  return (
    <div style={{ minHeight: "70vh", display: "grid", placeItems: "center", color: "var(--ui-muted)", fontFamily: "var(--font-family)" }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ width: 40, height: 40, margin: "0 auto 12px", borderRadius: "var(--wb-radius-control)", background: "var(--ui-primary)", display: "grid", placeItems: "center" }}>
          <svg viewBox="0 0 24 24" width="24" height="24" fill="#fff" aria-hidden="true">
            <rect x="4" y="6" width="10" height="3.2" rx="1.6"/>
            <rect x="7" y="10.4" width="12" height="3.2" rx="1.6" fillOpacity="0.92"/>
            <rect x="4" y="14.8" width="8" height="3.2" rx="1.6" fillOpacity="0.78"/>
          </svg>
        </div>
        <div>正在加载设计系统组件…</div>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
