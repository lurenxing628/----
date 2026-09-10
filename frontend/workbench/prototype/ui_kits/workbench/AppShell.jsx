// APS Workbench · App shell — grouped, iconised sidebar (workflow stages) + header
// Sidebar structure mirrors the approved prototype: pages grouped by stage.

function Ico({ name }) {
  const P = {
    box: <><path d="M3 7l9-4 9 4v10l-9 4-9-4V7z"/><path d="M3 7l9 4 9-4M12 11v10"/></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.6 3.6 3 8 3s8-1.4 8-3V5"/><path d="M4 12c0 1.6 3.6 3 8 3s8-1.4 8-3"/></>,
    play: <><circle cx="12" cy="12" r="9"/><path d="M10 8.5l6 3.5-6 3.5v-7z"/></>,
    home: <><path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/></>,
    gantt: <><path d="M4 7h10M4 12h15M4 17h7"/></>,
    chart: <><path d="M4 5v15h16"/><path d="M7 14l4-4 3 3 5-6"/></>,
    users: <><circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 3-5 6-5s6 1.7 6 5"/><path d="M16 5.5a3 3 0 010 6M21.5 20c0-2.2-1.2-3.6-3.2-4.3"/></>,
    clipboard: <><rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9.5 4V3.2h5V4"/><path d="M9 10.5h6M9 14.5h4"/></>,
    file: <><path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/><path d="M10 13h6M10 17h6"/></>,
    grid: <><rect x="4" y="4" width="7" height="7" rx="1.2"/><rect x="13" y="4" width="7" height="7" rx="1.2"/><rect x="4" y="13" width="7" height="7" rx="1.2"/><rect x="13" y="13" width="7" height="7" rx="1.2"/></>,
    settings: <><path d="M4 7h9M18 7h2M4 17h2M11 17h9"/><circle cx="15" cy="7" r="2.2"/><circle cx="8" cy="17" r="2.2"/></>,
    scale: <><path d="M12 4v16M7 21h10"/><path d="M5 8h14M12 4l7 4M12 4L5 8"/><path d="M5 8l-2.6 5h5.2zM19 8l-2.6 5h5.2z"/></>,
  };
  return (
    <svg className="nav-ico" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
      strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{P[name]}</svg>
  );
}

const NAV_GROUPS = [
  { title: "① 数据准备", items: [
    { id: "process", label: "基础资料", icon: "database" },
    { id: "batches", label: "批次管理", icon: "box" },
  ]},
  { title: "② 执行排产", items: [
    { id: "run", label: "执行排产", icon: "play" },
    { id: "analysis", label: "选择排产方案", icon: "chart" },
    { id: "trial", label: "方案试调", icon: "gantt", href: "trial-sample.html" },
    { id: "gantt", label: "设备 / 人员 / 批次甘特", icon: "gantt" },
  ]},
  { title: "③ 现场", items: [
    { id: "field", label: "现场记录", icon: "clipboard" },
    { id: "fieldgantt", label: "现场实际甘特", icon: "gantt" },
  ]},
  { title: "④ 统计分析", items: [
    { id: "review", label: "执行复盘", icon: "chart" },
    { id: "reports", label: "报表中心", icon: "file" },
    { id: "calib", label: "工时定额校准", icon: "scale" },
  ]},
  { title: "基础数据 · 系统", items: [
    { id: "dashboard", label: "值班台", icon: "home" },
    { id: "basedata", label: "主数据总览", icon: "grid" },
    { id: "system", label: "系统管理", icon: "settings" },
  ]},
];

function AppShell({ active, onNav, theme, onToggleTheme, title, showCapsule = true, flush = false, dashboard = false, field = false, operations = false,
  planContext = {}, children }) {
  const analysisWorkspace = active === "reports" || active === "review";
  return (
    <div className={"app-container" + (dashboard ? " dashboard-shell" : "") + (field ? " field-shell" : "") + (operations ? " operations-shell" : "") + (analysisWorkspace ? " analysis-workspace" : "")}>
      <aside className="sidebar">
        <div className="sidebar-header">
          <span className="brand-tile" aria-label="APS 智能排产">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="#fff" aria-hidden="true">
              <rect x="4" y="6" width="10" height="3.2" rx="1.6"/>
              <rect x="7" y="10.4" width="12" height="3.2" rx="1.6" fillOpacity="0.92"/>
              <rect x="4" y="14.8" width="8" height="3.2" rx="1.6" fillOpacity="0.78"/>
            </svg>
          </span>
          <span className="brand-word">APS 智能排产</span>
        </div>
        <nav className="sidebar-nav">
          {NAV_GROUPS.map((g) => (
            <div className="nav-group" key={g.title}>
              <div className="nav-group-title">{g.title}</div>
              {g.items.map((it) => (
                <a
                  key={it.id}
                  href={it.href || "#" + it.id}
                  title={it.label}
                  onClick={(e) => { if (!it.href) { e.preventDefault(); onNav(it.id); } }}
                  className={"nav-item" + (active === it.id ? " active" : "")}
                  aria-current={active === it.id ? "page" : undefined}
                >
                  <Ico name={it.icon} />
                  <span className="nav-label">{it.label}</span>
                </a>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      <div className="main-content">
        <header className="top-header">
          <h2 className="top-title">{title}</h2>
          <div className="cap-rich" style={showCapsule ? undefined : { display: "none" }}>
            <strong>{planContext.label}</strong><i className="cap-sep">·</i>
            <span>{planContext.name}</span><span className={planContext.status === '已采用' ? 'cap-ok' : 'cap-preview'}>{planContext.status}</span><i className="cap-sep">·</i>
            <span className="cap-muted">正式 v{planContext.version}</span><i className="cap-sep">·</i>
            <span className="cap-muted">范围 {planContext.range}</span>
          </div>
          <div className="header-controls">
            <button type="button" className="hdr-pill" onClick={onToggleTheme}>深色：{theme === "dark" ? "开" : "关"}</button>
          </div>
        </header>
        <main className="page-content" style={flush ? { padding: 0, flex: 1, minHeight: 0, display: "flex", flexDirection: "column" } : undefined}>{children}</main>
      </div>
    </div>
  );
}

window.AppShell = AppShell;
