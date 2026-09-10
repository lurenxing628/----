// APS Workbench · 同一工序分开显示实际报工与剩余安排，原计划仅作基线。
const FG_HOUR = 3600000;

function fgIcon(name) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {window.APSFieldReports.iconNodes[name].map(([tag, attrs], index) => React.createElement(tag, { ...attrs, key: index }))}
  </svg>;
}

function fgTimeAxis(model) {
  const times = [model.state.clock];
  model.tasks.forEach((t) => {
    times.push(model.ms(t.planStart), model.ms(t.planEnd));
    if (t.remainingPlan) times.push(model.ms(t.remainingPlan.start), model.ms(t.remainingPlan.end));
    t.reports.forEach((r) => {
      times.push(model.ms(r.start));
      if (r.end) times.push(model.ms(r.end));
    });
  });
  const known = times.filter(Number.isFinite);
  const start = Math.floor(Math.min(...known) / FG_HOUR) * FG_HOUR;
  const end = (Math.ceil(Math.max(...known) / FG_HOUR) + 1) * FG_HOUR;
  const hours = Array.from({ length: (end - start) / FG_HOUR }, (_, i) => start + i * FG_HOUR);
  const days = [];
  hours.forEach((h) => {
    const day = new Date(h).toISOString().slice(0, 10);
    const last = days[days.length - 1];
    if (last && last.date === day) last.hours++;
    else days.push({ date: day, hours: 1 });
  });
  return { start, end, hours, days };
}

function fgReportTracks(reports, ms) {
  const tracks = [];
  reports.forEach((r) => {
    // 同一资源的非重叠记录共用轨道；换人、换设备、未知结束或重叠另起子行。
    let track = tracks.find((items) => {
      const last = items[items.length - 1];
      return last.machine === r.machine && last.person === r.person && last.end && ms(last.end) <= ms(r.start);
    });
    if (!track) { track = []; tracks.push(track); }
    track.push(r);
  });
  return tracks;
}

function fgCsvCell(value) {
  let text = value == null ? "" : String(value);
  if (/^[\s]*[=+@-]/.test(text)) text = "'" + text;
  return '"' + text.replace(/"/g, '""') + '"';
}

function fgExportCsv(rows, context, labels, filtered, query = "") {
  const data = [["计划版本", "计划生成", "计划范围", "工序ID", "批次", "名称", "工序", "应做数量",
    "计划设备", "计划人员", "计划开工", "计划完工", "工序状态", "累计已知数量", "累计已知工时",
    "待补记录数", "整道实际完工", "报工ID", "报工单号", "本次数量", "本次开工", "本次结束",
    "本次有效工时", "实际设备", "实际人员", "备注", "登记时间", "修订", "剩余数量", "剩余计划开工", "剩余计划完工", "剩余计划设备", "剩余计划人员"]];
  rows.forEach(({ t, s }) => {
    const reports = s.reports.length ? s.reports : [null];
    reports.forEach((r) => data.push([context.version, context.generated, context.range, t.id, t.batch, t.name, t.op, t.target,
      t.machine, t.person, t.planStart, t.planEnd, labels[s.status], s.qty, s.hours, s.incomplete, s.end,
      r && r.id, r && r.reportNo, r && r.qty, r && r.start, r && r.end, r && r.hours,
      r && r.machine, r && r.person, r && r.remark, r && r.recorded, r && r.revision, s.remaining,
      t.remainingPlan && t.remainingPlan.start, t.remainingPlan && t.remainingPlan.end, t.remainingPlan && t.remainingPlan.machine, t.remainingPlan && t.remainingPlan.person]));
  });
  const csv = "\uFEFF" + data.map((row) => row.map(fgCsvCell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  try {
    link.href = url;
    link.download = "现场实际甘特-v" + context.version + (query ? "-搜索结果" : filtered ? "-" + (typeof filtered === 'string' ? filtered : "仅延后") : "-全部") + ".csv";
    document.body.appendChild(link);
    link.click();
  } finally {
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

function FieldGanttScreen(props = {}) {
  return <FieldGanttContent key={window.APSFieldGanttUI.contextKey(props.initialContext)} {...props} />;
}

function FieldGanttContent({ initialContext = {}, onSourceChange, onNav } = {}) {
  const { Panel } = window.APSDesignSystem_edbc5d;
  const { TransferButton } = window.APSWorkbenchUI;
  const { state, patch, changeSource } = useFieldGanttScreenState(initialContext, onSourceChange, onNav);
  const { view, source, search, showLinks, selectedTaskId, lateFilter, scope, collapsed, onlySelected, showDetails, showChain } = state;
  const api = window.APSFieldGanttUI;
  const [tip, setTip] = React.useState(null);
  const [exportError, setExportError] = React.useState("");
  const [hoverTarget, setHoverTarget] = React.useState(null);
  const gridRef = React.useRef(null);
  const boardRef = React.useRef(null);
  const shared = window.APSFieldReports;
  const exampleOn = source !== "current";
  const example = source === "dense" ? window.APSFieldGanttDensityExample : source === "complex" ? window.APSFieldGanttExample : null;
  const model = exampleOn ? example && example.model : shared && shared.model;
  const context = exampleOn ? example && example.context : shared && shared.planContext;
  const axis = model ? fgTimeAxis(model) : null;
  const viewport = useFieldGanttViewport({ boardRef, axis, sourceKey: source });
  const scoped = React.useMemo(() => model ? api.rows(model, source, scope, search) : { rows: [], error: '' },
    [model, source, scope, search]);
  const rows = scoped.rows;
  const visible = model ? api.filterRows(rows, model, lateFilter, onlySelected, selectedTaskId) : [];
  const { locateTask, rememberViewport, revealFocus } = useFieldGanttLocation({ model, axis, viewport, boardRef, gridRef, state, patch,
    visibleIds: visible.map(({ t }) => t.id) });
  if (!model || !context) return <Panel className="wb-page-panel" title="现场实际甘特 · 计划 vs 实际"><p role="alert">同会话报工数据尚未加载，无法显示现场实际甘特。</p></Panel>;
  const currentChains = exampleOn ? null : window.APSFieldGanttChains.resolveCurrent(model, context);
  const catalog = exampleOn ? example.criticalChains || [] : currentChains.catalog;
  const chain = !exampleOn && !hoverTarget ? currentChains.defaultChain : window.APSFieldGanttChains.choose(catalog, model, hoverTarget);
  const hasChainEdges = catalog.some(item => item.edges.length);
  const chainIds = new Set(showChain && chain ? chain.taskIds : []);
  const { ms, fmt, labels } = model;
  const gran = { hourw: viewport.hourw };
  const pos = (time) => (time - axis.start) / (axis.end - axis.start) * 100;
  const spanStyle = (start, end) => ({ left: pos(ms(start)) + "%", width: (ms(end) - ms(start)) / (axis.end - axis.start) * 100 + "%" });
  const delta = ({ t, s }) => {
    const value = s.status === "done" && s.end && t.planEnd ? (ms(s.end) - ms(t.planEnd)) / 60000 : NaN;
    return Number.isFinite(value) ? value : null;
  };
  const lateOf = (row) => api.deadlines(row, model).finishLate;
  const fmtDelta = (n) => (n > 0 ? "+" : n < 0 ? "−" : "±") + Math.abs(Math.round(n)) + "m";
  const query = search.trim().toLowerCase();
  const entries = [];
  visible.forEach((row) => {
    entries.push({ ...row, key: row.t.id + ":plan", kind: "plan", r: null });
    const tracks = fgReportTracks(row.s.reports, ms);
    (tracks.length ? tracks : [[]]).forEach((reports, index) => entries.push({ ...row,
      key: row.t.id + ":actual:" + index, kind: "actual", r: reports[0] || null, reports }));
    if (row.s.remaining > 0) entries.push({ ...row, key: row.t.id + ":remaining", kind: "remaining", r: null });
  });
  const resource = ({ t, r, kind }) => {
    const owner = kind === "remaining" && t.remainingPlan ? t.remainingPlan : r || t;
    return view === "batch" ? t.batch : view === "device" ? owner.machine || "实际设备未填写" : owner.person || "实际人员未填写";
  };
  const groupedEntries = new Map();
  entries.forEach(entry => {
    const name = resource(entry);
    if (!groupedEntries.has(name)) groupedEntries.set(name, []);
    groupedEntries.get(name).push(entry);
  });
  const lanes = Array.from(groupedEntries, ([name, members]) => {
    if (view === "batch") members.sort((a, b) => a.t.op.localeCompare(b.t.op, "zh-CN", { numeric: true }) || a.t.id.localeCompare(b.t.id));
    const tasks = [...new Map(members.map((entry) => [entry.t.id, entry])).values()];
    const reports = members.filter((entry) => entry.kind === "actual").flatMap((entry) => entry.reports);
    const hours = model.number(reports.reduce((n, r) => n + (r.hours == null ? 0 : r.hours), 0));
    const unknown = reports.filter((r) => r.hours == null).length;
    const scope = view === "device" ? new Set(tasks.map(({ t }) => t.batch)).size + " 个批次"
      : view === "person" ? new Set(members.map(({ t, r, kind }) => (kind === "remaining" && t.remainingPlan ? t.remainingPlan : r || t).machine).filter(Boolean)).size + " 台设备"
      : tasks.filter(({ s }) => s.status === "done").length + " / " + tasks.length + " 道已完工";
    return { name, entries: members, scope, collapsed: !!collapsed[api.groupKey(source, view, name)], counts: tasks.length + " 道工序 · " + reports.length + " 次报工",
      hours: "已知实报工时 " + hours + "h" + (unknown ? " · " + unknown + " 条工时待补" : "") };
  });
  const reportEntries = visible.flatMap((row) => row.s.reports.map((r) => ({ ...row, r, key: row.t.id + ":report:" + r.id })));
  const done = rows.filter(({ s }) => s.status === "done");
  const ds = done.map(delta).filter(Number.isFinite);
  const avg = ds.length ? ds.reduce((a, b) => a + b, 0) / ds.length : null;
  const late = rows.filter(lateOf).length;
  const lateCounts = Object.fromEntries(Object.keys(api.lateLabels).map(key => [key,
    key === 'all' ? rows.length : rows.filter(row => api.deadlines(row, model)[key]).length]));
  const stats = [
    { sev: "ok", label: "整道已完工", value: done.length, helper: "数量已齐且报工完整" },
    { sev: "notice", label: "已报工 · 未整道完工", value: rows.filter(({ s }) => s.status !== "done" && s.status !== "none").length, helper: "数量未齐或记录待补" },
    { sev: "warning", label: "待报工", value: rows.filter(({ s }) => s.status === "none").length, helper: "没有实际记录" },
    { sev: late ? "warning" : "ok", label: "平均整道完工偏差", value: avg == null ? "—" : fmtDelta(avg), helper: "仅已完工工序 · 延后 " + late + " 道" },
  ];
  const statusText = ({ t, s }) => labels[s.status] + " · 已知 " + s.qty + "/" + t.target + " 件" + (s.incomplete ? " · " + s.incomplete + " 条待补" : "");
  const reportText = (r) => (r.qty == null ? "数量未知" : r.qty + " 件") + " · " + (r.hours == null ? "工时未知" : r.hours + "h") + (!r.end ? " · 本次结束未填写" : "");
  const toneOf = (entry) => {
    if (entry.s.status !== "done" || !entry.s.end) return "doing";
    return delta(entry) <= 10 ? "ok" : delta(entry) <= 30 ? "warn" : "bad";
  };
  const details = ({ t, s, r, kind }) => [
    t.batch + " · " + t.name + " · " + t.op,
    "工序：" + statusText({ t, s }),
    "计划资源：" + t.machine + " / " + t.person,
    "计划：" + fmt(t.planStart) + " → " + fmt(t.planEnd),
    ...(kind === "remaining" && t.remainingPlan ? ["剩余安排：" + s.remaining + " 件 · " + fmt(t.remainingPlan.start) + " → " + fmt(t.remainingPlan.end),
      "剩余计划资源：" + t.remainingPlan.machine + " / " + t.remainingPlan.person] : []),
    ...(r ? ["本次报工：" + r.reportNo, "实际资源：" + (r.machine || "未填写") + " / " + (r.person || "未填写"),
      "本次实际：" + fmt(r.start) + " → " + (r.end ? fmt(r.end) : "本次结束未填写"), reportText(r),
      "登记：" + fmt(r.recorded) + " · 修订 " + r.revision, "备注：" + (r.remark || "—")] : []),
    "整道实际完工：" + (s.end ? fmt(s.end) : "未完工"),
    "整道完工偏差：" + (delta({ t, s }) != null ? fmtDelta(delta({ t, s })) : s.end ? "计划完工未知，不计算" : "未完工，不计算"),
  ];
  const enter = (entry, e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setTip({ key: entry.key, reference: e.currentTarget.dataset.reference === "plan-end",
      x: e.clientX == null ? rect.left : e.clientX, y: e.clientY == null ? rect.bottom : e.clientY });
  };
  const barProps = (entry) => ({ tabIndex: 0, role: "img", "aria-label": details(entry).join("；"), title: details(entry).join("\n"),
    "data-chain-kind": "task", "data-chain-key": entry.t.id,
    onClick: () => { setTip(null); locateTask(entry.t.id); },
    onMouseEnter: (e) => enter(entry, e), onMouseLeave: () => setTip(null), onFocus: (e) => { revealFocus(e.currentTarget); enter(entry, e); },
    onBlur: () => setTip(null), onKeyDown: (e) => { if (e.key === "Escape") setTip(null);
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setTip(null); locateTask(entry.t.id); } } });
  const tipEntry = tip && entries.concat(reportEntries).find((entry) => entry.key === tip.key);
  const switchView = (next) => { patch({ view: next }); setTip(null); setHoverTarget(null); };
  const readTarget = (node) => {
    const el = node && node.closest && node.closest('[data-chain-kind]');
    return el ? { kind: el.dataset.chainKind, key: el.dataset.chainKey } : null;
  };
  const preview = (node) => {
    if (node && node.closest && node.closest('.fg-chain-strip')) return;
    const next = readTarget(node);
    setHoverTarget((previous) => previous && next && previous.kind === next.kind && previous.key === next.key ? previous : next);
  };
  const toggleLane = name => patch(previous => {
    const key = api.groupKey(source, view, name), next = { ...previous.collapsed };
    if (next[key]) delete next[key]; else next[key] = true;
    return { collapsed: next };
  });
  const allCollapsed = lanes.length > 0 && lanes.every(lane => lane.collapsed);
  const selectedRow = rows.find(row => row.t.id === selectedTaskId);

  return (
    <Panel className="wb-page-panel fg-page" title={exampleOn ? "现场实际甘特 · " + (source === "dense" ? "密集演示" : "复杂演示") : "现场实际甘特 · 计划 vs 实际"}>
      <div className="fg-source-switch"><span>数据</span><div className="seg">
        {[["current", "当前报工"], ["complex", "复杂样例"], ["dense", "密集样例"]].map(([value, label]) => <button key={label} className={"seg-btn" + (source === value ? " on" : "")}
          disabled={value !== "current" && !(value === "dense" ? window.APSFieldGanttDensityExample : window.APSFieldGanttExample)} aria-pressed={source === value}
          onClick={() => { changeSource(value); setExportError(""); setTip(null); setHoverTarget(null); }}>{label}</button>)}
      </div><span className="fg-context" title={"生成 " + context.generated + " · " + context.range}>{exampleOn ? "演示计划" : "计划 v" + context.version} · 数据截至 {fmt(new Date(model.state.clock).toISOString().slice(0, 16))}</span>
        {state.returnTo && typeof onNav === 'function' && <button className="fg-return" onClick={() => {
          rememberViewport(); onNav(state.returnTo.view, { ...state.returnTo.context, returning: true });
        }}>{fgIcon('chevron-left')}回来源</button>}
      </div>
      {scope && <div className="fg-scope-context"><span>{scoped.analysis ? [scoped.analysis.rangeLabel,
        scope.batch, scope.resource, search && '搜索 ' + search].filter(Boolean).join(' · ') : '来源范围待核对'}</span>
        <button className="fg-icon-button" title="清除来源范围" aria-label="清除来源范围" onClick={() => patch({ scope: null, search: '', lateFilter: 'all', onlySelected: false })}>{fgIcon('x')}</button></div>}
      <dl className="fg-metrics" aria-label="当前范围概况">{stats.map(s => <div key={s.label} title={s.helper}>
        <dt>{s.label}</dt><dd className={"ds-value" + (s.label === "整道已完工" ? " fg-complete" : s.label === "待报工" ? " fg-pending" : "")}>{s.value}</dd></div>)}</dl>
      <section className="gb-workspace fg-workspace" aria-label="现场实际甘特工作区" onMouseOver={(e) => preview(e.target)} onMouseLeave={() => setHoverTarget(null)}
        onFocus={(e) => preview(e.target)} onBlur={(e) => preview(e.relatedTarget)}>
      <div className="gb-toolbar fg-toolbar">
        <div className="fg-toolbar-main" role="group" aria-label="甘特视图与数据筛选">
          <div className="fg-toolbar-query">
            <div className="gb-tb-group">
              <span className="gb-tb-label">视图</span>
              <div className="seg">
                {[["device", "设备"], ["person", "人员"], ["batch", "批次"]].map(([k, l]) =>
                  <button key={k} className={"seg-btn" + (view === k ? " on" : "")} aria-pressed={view === k} onClick={() => switchView(k)}>{l}</button>)}
              </div>
            </div>
            <label className="fg-search">{fgIcon("search")}<input type="search" aria-label="搜索现场甘特" placeholder="批次 / 工序 / 设备 / 人员" value={search} onChange={(e) => { patch({ search: e.target.value }); setTip(null); }} /></label>
            <span className="gb-tb-summary"><span>本视图</span><span><b>{lanes.length}</b> {view === "device" ? "台设备" : view === "person" ? "名人员" : "个批次"}</span><span>· <b>{visible.length}</b> 道工序</span><span>· <b>{visible.reduce((n, row) => n + row.s.reports.length, 0)}</b> 次报工</span></span>
          </div>
          <div className="gb-tb-actions wb-actions">
            <label className="fg-late-filter">晚期<select aria-label="晚期筛选" value={lateFilter} onChange={e => { patch({ lateFilter: e.target.value }); setTip(null); }}>
              {Object.entries(api.lateLabels).map(([key, label]) => <option key={key} value={key}>{label} ({lateCounts[key]})</option>)}
            </select></label>
            <TransferButton kind="export" disabled={!visible.length} title="导出当前筛选内的计划与逐次报工 CSV" onClick={() => {
              setExportError("");
              try { fgExportCsv(visible, context, labels, lateFilter === 'all' ? '' : api.lateLabels[lateFilter], query); }
              catch (error) { setExportError("导出失败：" + error.message); }
            }}>
              导出 CSV
            </TransferButton>
          </div>
        </div>
        <div className="fg-toolbar-chart" role="group" aria-label="甘特图例与图表工具">
          <div className="fg-legend">
            <span className="fg-lg"><i className="fg-sw-plan" />原计划基线</span>
            <span className="fg-lg"><i className="fg-sw-act" />实际报工</span>
            <span className="fg-lg"><i className="fg-sw-remaining" />剩余计划</span>
            {catalog.length ? <label className="fg-chain-toggle"><input type="checkbox" checked={showChain} onChange={e => patch({ showChain: e.target.checked })} />关键链</label>
              : <span className="fg-chain-unavailable" role="status">{fgIcon("circle-alert")}{currentChains ? currentChains.reason : "当前样例关键链数据未加载"}</span>}
          </div>
          <div className="fg-toolbar-chart-actions" role="group" aria-label="图表操作">
            <button className="gb-tb-btn" disabled={!lanes.length} onClick={() => patch(previous => {
              const next = { ...previous.collapsed };
              lanes.forEach(lane => { const key = api.groupKey(source, view, lane.name); if (allCollapsed) delete next[key]; else next[key] = true; });
              return { collapsed: next };
            })}>{fgIcon(allCollapsed ? 'unfold-vertical' : 'fold-vertical')}{allCollapsed ? '全部展开' : '全部折叠'}</button>
            <label className="fg-chain-toggle"><input type="checkbox" checked={onlySelected} disabled={!selectedRow && !onlySelected}
              onChange={e => patch({ onlySelected: e.target.checked })} />只看选中</label>
            <label className="fg-chain-toggle"><input type="checkbox" checked={showDetails} onChange={e => patch({ showDetails: e.target.checked })} />详情</label>
            <div className="fg-scale-controls">
              <span className="gb-tb-label">缩放</span>
              <div className="gb-zoom-ctl">
                <button className="gb-zoom-btn" disabled={!viewport.canZoomOut} onClick={() => { viewport.zoomOut(); setTip(null); }} title="缩小时间轴" aria-label="缩小时间轴">{fgIcon("minus")}</button>
                <span className="gb-zoom-lvl">{viewport.mode === "auto" ? "自动" : "手动"}</span>
                <button className="gb-zoom-btn" disabled={!viewport.canZoomIn} onClick={() => { viewport.zoomIn(); setTip(null); }} title="放大时间轴" aria-label="放大时间轴">{fgIcon("plus")}</button>
              </div>
              <span className="fg-tick-hint">刻度 {viewport.tickLabel}</span>
            </div>
            <div className="fg-position-controls">
              <button className="gb-tb-btn" onClick={viewport.fitAll} title="适应全部时间范围">{fgIcon("chart-gantt")}适应全部</button>
              <button className="gb-tb-btn" disabled={!visible.some(({ t }) => t.id === selectedTaskId)} onClick={() => locateTask(selectedTaskId)} title="定位选中工序">{fgIcon("search")}定位选中</button>
            </div>
          </div>
        </div>
      </div>
      {scoped.error && <p className="fg-error" role="alert">{scoped.error}</p>}
      {exportError && <p className="fg-error" role="alert">{exportError}</p>}
      {selectedTaskId && !selectedRow && <p className="fg-selection-note" role="status">选中工序不在当前范围内，未扩大来源筛选。</p>}
      {showDetails && <div className="fg-details" aria-label="工序详情">{selectedRow ? details(selectedRow).map((line, index) => <span key={index}>{line}</span>)
        : <span>计划生成 {context.generated} · {context.range}</span>}</div>}
      {!!catalog.length && showChain && <React.Fragment><FieldGanttChainStrip {...{ chain, model, gridRef, hoverTarget, selectedTaskId }} onLocate={locateTask} visibleIds={visible.map(({ t }) => t.id)} />
        <label className="fg-chain-toggle fg-lines-toggle"><input type="checkbox" checked={showLinks && hasChainEdges} disabled={!hasChainEdges} onChange={e => patch({ showLinks: e.target.checked })} />关键链连线</label></React.Fragment>}
      <div className={"gb fg-scope" + (showDetails ? " fg-show-details" : "")} data-viewport-mode={viewport.mode} style={{ "--fg-hourw": viewport.hourw + "px", "--fg-hours": axis.hours.length,
        "--gb-trackw": viewport.trackWidth + "px", "--fg-tickw": (viewport.tickHours || 1) * viewport.hourw + "px",
        "--fg-tick-offset": viewport.tickOffset + "px" }}>
        <div className="gb-board" ref={boardRef} role="region" aria-label="分次报工甘特" tabIndex={0} onScroll={rememberViewport}>
          <div className="gb-scale">
            <div className="gb-corner"><span className="fg-corner-main">{view === "batch" ? "批次 / 工序" : view === "person" ? "人员 / 任务" : "设备 / 任务"}<span className="gb-corner-sub">实际已报 / 剩余安排</span></span><span className="fg-corner-state">状态 / 偏差</span></div>
            <FieldGanttAxis {...{ axis, viewport, fmt }} clock={model.state.clock} />
          </div>
          <div className="gb-grid" ref={gridRef}>
            {!entries.length && !scoped.error && <div className="fg-empty" role="status">{onlySelected ? "选中工序不在当前筛选内" : lateFilter !== 'all' ? "当前范围没有“" + api.lateLabels[lateFilter] + "”工序" : query || scope ? "没有匹配的工序" : "暂无计划工序"}</div>}
            <FieldGanttRows {...{ lanes, view, model, gran, pos, spanStyle, barProps, toneOf, statusText, reportText, resource, chainIds, delta, fmtDelta, selectedTaskId }} onToggleLane={toggleLane} onSelectTask={locateTask} deadlines={row => api.deadlines(row, model)} />
            {chain && chain.edges.length > 0 && showLinks && showChain && <FieldGanttChainLines chain={chain} gridRef={gridRef} layoutKey={[view, viewport.trackWidth, lateFilter, query, onlySelected, JSON.stringify(collapsed), showDetails].join(":")} />}
          </div>
        </div>
      </div>
      </section>
      {tipEntry && <div className="gb-tip fg-tip on" role="tooltip" style={{ left: Math.max(8, Math.min(tip.x + 14, window.innerWidth - 376)),
        ...(tip.y > window.innerHeight / 2 ? { bottom: Math.max(8, window.innerHeight - tip.y + 16) } : { top: Math.max(8, tip.y + 16) }) }}>
        {(tip.reference ? [tipEntry.t.batch + " · " + tipEntry.t.op, "计划完工：" + tipEntry.t.planEnd.replace("T", " ")] : details(tipEntry))
          .map((line, i) => <div key={i}>{i === 0 ? <b>{line}</b> : line}</div>)}
      </div>}
    </Panel>
  );
}

window.FieldGanttScreen = FieldGanttScreen;
