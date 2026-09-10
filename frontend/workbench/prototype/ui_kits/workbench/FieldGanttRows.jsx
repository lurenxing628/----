function fgChainTarget(kind, key) {
  return key ? { "data-chain-kind": kind, "data-chain-key": key, tabIndex: 0 } : {};
}

function fgTaskRowGroups(entries) {
  const groups = new Map();
  entries.forEach((entry) => {
    if (!groups.has(entry.t.id)) groups.set(entry.t.id, { plan: null, rows: [] });
    const group = groups.get(entry.t.id);
    if (entry.kind === "plan") group.plan = entry;
    else group.rows.push(entry);
  });
  // 原计划只在所属资源组出现一次；换资源后留紧凑参考行，不搬到实际资源下。
  return Array.from(groups.values()).map(({ plan, rows }) => ({ plan,
    rows: rows.length ? rows : [{ ...plan, kind: "reference", key: plan.key + ":reference" }] }));
}

function FieldGanttOwner({ owner, label, actual = false }) {
  return <div className="fg-row-resource"><span className={"fg-row-kind" + (actual ? " is-actual" : "")}>{label}</span>
    <span className="fg-owner-names"><span {...fgChainTarget("device", owner.machine)}>{owner.machine || "设备未填写"}</span>
      {" / "}<span {...fgChainTarget("person", owner.person)}>{owner.person || "人员未填写"}</span></span>
  </div>;
}

function FieldGanttRows({ lanes, view, model, gran, pos, spanStyle, barProps, toneOf, statusText, reportText, resource, chainIds,
  delta, fmtDelta, selectedTaskId, onToggleLane, onSelectTask, deadlines }) {
  const { ms, fmt } = model;
  const sizeClass = (start, end) => {
    const pixels = end ? (ms(end) - ms(start)) / 3600000 * gran.hourw : 0;
    return pixels < 70 ? " is-narrow" : pixels < 200 ? " is-compact" : "";
  };
  return lanes.map((lane) => <section className="fg-lane" key={lane.name} data-view={view} data-resource={lane.name} data-collapsed={!!lane.collapsed}
    aria-label={(view === "device" ? "设备 " : view === "person" ? "人员 " : "批次 ") + lane.name}>
    <div className="fg-lane-head">
      <h2 className="fg-lane-name">{onToggleLane && <button className="fg-icon-button fg-lane-toggle" aria-expanded={!lane.collapsed}
        aria-label={(lane.collapsed ? '展开 ' : '折叠 ') + lane.name} title={(lane.collapsed ? '展开 ' : '折叠 ') + lane.name}
        onClick={() => onToggleLane(lane.name)}>{fgIcon(lane.collapsed ? 'chevron-right' : 'chevron-down')}</button>}
        <span>{view === "device" ? "设备" : view === "person" ? "人员" : "批次"}</span>
        <strong {...fgChainTarget(view, lane.name)}>{lane.name}</strong></h2>
      <div className="fg-lane-summary"><span>{lane.scope}</span><span>{lane.counts}</span><span>{lane.hours}</span></div>
    </div>
    {!lane.collapsed && fgTaskRowGroups(lane.entries).map(({ plan, rows }) => {
      const owners = new Set();
      return rows.map((entry, index) => {
        const { t, s, r, kind, reports = [] } = entry, future = kind === "remaining" && t.remainingPlan;
        const first = index === 0, baseline = first && plan;
        const hasReference = !!baseline || kind === "actual" && reports.length > 0;
        const actualQty = reports.reduce((n, report) => n + (report.qty == null ? 0 : report.qty), 0);
        const actualHours = reports.reduce((n, report) => n + (report.hours == null ? 0 : report.hours), 0);
        const quantityUnknown = reports.some((report) => report.qty == null);
        const hoursText = reports.some((report) => report.hours == null) ? "工时待补" : model.number(actualHours) + "h";
        const owner = future || r || t, ownerKey = JSON.stringify([owner.machine, owner.person]);
        const showOwner = !owners.has(ownerKey);
        owners.add(ownerKey);
        const plannedKey = JSON.stringify([t.machine, t.person]);
        const showPlanOwner = baseline && !owners.has(plannedKey);
        if (showPlanOwner) owners.add(plannedKey);
        const chainClass = chainIds.has(t.id) ? " is-chain-task" : "";
        const deviation = first && delta ? delta(entry) : null;
        const taskTarget = fgChainTarget("task", t.id);
        const timing = deadlines ? deadlines(entry) : {};
        return <div className={"gb-row fg-" + kind + "-row" + (first ? " fg-group-first" : "") + (baseline ? " fg-plan-row" : "")
          + (selectedTaskId === t.id ? " is-selected-task" : "")} key={entry.key}
          data-task-id={t.id} data-kind={kind} data-resource={lane.name} data-status={s.status}>
          <div className="gb-res"><div className="gb-res-main">
            {first && <div className="gb-res-name">
              {view !== "batch" && <React.Fragment><span className="fg-batch-name" {...fgChainTarget("batch", t.batch)}>{t.batch}</span>{" · "}</React.Fragment>}
              <span className="fg-task-name" {...taskTarget} role={onSelectTask ? 'button' : undefined}
                title={t.batch + ' · ' + t.op + ' · ' + t.name} onClick={onSelectTask ? () => onSelectTask(t.id) : undefined}
                onKeyDown={onSelectTask ? e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelectTask(t.id); } } : undefined}>{t.op}{" · "}{t.name}</span>
            </div>}
            {kind !== "reference" && <div className={"fg-row-heading" + (kind === "actual" ? " is-actual" : "")}>
              <span>{kind === "remaining" ? "剩余安排" : "实际已报"}</span>
              <strong>{kind === "remaining" ? s.remaining + " 件" : quantityUnknown ? "数量待补" : actualQty + " 件"}</strong>
            </div>}
            {showOwner && <FieldGanttOwner owner={owner} label={future ? "剩余计划" : r ? "实际" : "原计划"} actual={!!r} />}
            {showPlanOwner && <FieldGanttOwner owner={t} label="原计划" />}
            {kind !== "reference" && <div className={"fg-row-status" + (s.incomplete ? " has-unknown" : "")}>{(kind === "actual" ? reports.length
              ? reports.length + " 次报工 · 已知 " + actualQty + " 件 / " + hoursText + (reports.some((report) => !report.end) ? " · 结束待补" : "")
              : "尚未报工" : s.incomplete ? "实际记录待补 · 剩余按已知数量" : "未完成 " + s.remaining + " / " + t.target + " 件").split(" · ").map((phrase, i) =>
                <React.Fragment key={i}>{i > 0 ? " · " : ""}<span className="fg-status-phrase">{phrase}</span></React.Fragment>)}</div>}
          </div><div className="fg-state">
            {first ? <div className={"fg-state-badge tone-" + toneOf(entry)} data-status={s.status} title={statusText(entry)} aria-label={statusText(entry)}>
              <span className="fg-state-label">{model.labels[s.status]}</span>
              {deviation != null && fmtDelta && <span className="fg-state-delta" aria-label={"整道完工偏差 " + fmtDelta(deviation)}>
                {deviation > 10 ? "延后 " : ""}{fmtDelta(deviation)}</span>}
              {timing.unclosed && <span className="fg-deadline-label"><span>到期</span><span>未确认完成</span></span>}
              {timing.forecastLate && <span className="fg-deadline-label">剩余预计晚</span>}
            </div> : kind === "remaining" && <span className="fg-state-pending">{future ? "待开工" : "待续排"}</span>}
            {first && kind === "remaining" && <span className="fg-state-pending">{future ? "待开工" : "待续排"}</span>}
          </div></div>
          <div className="fg-track">
            <span className="fg-now" data-clock={model.state.clock} style={{ left: pos(model.state.clock) + "%" }} />
            {hasReference && <div className="fg-reference-band" aria-hidden="true" />}
            {baseline && <div className={"fg-plan" + chainClass} style={spanStyle(t.planStart, t.planEnd)}
              data-start={t.planStart} data-end={t.planEnd} {...barProps(plan)} {...taskTarget} />}
            {hasReference && <span className="fg-ref" style={{ left: pos(ms(t.planEnd)) + "%" }}
              {...barProps(plan || { ...entry, key: t.id + ":plan", kind: "plan", r: null })} {...taskTarget}
              data-reference="plan-end" data-plan-end={t.planEnd} title={"计划完工 " + t.planEnd.replace("T", " ")}
              aria-label={"计划完工 " + t.planEnd.replace("T", " ")} />}
            {kind === "remaining" ? future ? <div className={"fg-remaining" + sizeClass(future.start, future.end) + chainClass}
              style={spanStyle(future.start, future.end)} data-start={future.start} data-end={future.end} {...barProps(entry)} {...taskTarget}>
              <span className="fg-act-lab">剩余 {s.remaining} 件</span>
              <span className="fg-bar-meta"><span className="fg-bar-facts">{fmt(future.start)} → {fmt(future.end)}</span></span>
            </div> : <div className="fg-unscheduled" {...barProps(entry)} {...taskTarget}><strong>待续排</strong>
              <span>{s.remaining} 件{s.incomplete ? " · 实际记录待补" : ""}</span></div> : kind === "actual" && <React.Fragment>
              {!reports.length && <span className="fg-no-reports">暂无实际报工</span>}
              {reports.map((report) => {
                const props = { ...barProps({ ...entry, r: report, key: t.id + ":report:" + report.id }), ...taskTarget,
                  "data-report-id": report.id, "data-start": report.start, "data-end": report.end };
                return report.end ? <div key={report.id} className={"fg-act" + sizeClass(report.start, report.end) + chainClass}
                  style={spanStyle(report.start, report.end)} {...props}>
                  <span className="fg-act-lab">第 {s.reports.indexOf(report) + 1} 次报工<em>{report.reportNo}</em></span>
                  <span className="fg-bar-meta"><span className="fg-bar-facts">{reportText(report)}</span></span>
                </div> : <div key={report.id} className={"fg-start" + chainClass} style={{ left: pos(ms(report.start)) + "%" }} {...props} />;
              })}
            </React.Fragment>}
          </div>
        </div>;
      });
    })}
  </section>);
}
window.FieldGanttRows = FieldGanttRows;
