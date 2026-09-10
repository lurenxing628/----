// APS Workbench · 统计分析 › 工时定额校准
// Compares 现场实际单件工时 (近N次中位数) vs 定额单件工时, sorted by deviation.
// This sample only marks adoption in local component state; it never writes 定额.
// Production adoption requires a separately connected writeback/audit flow.
// Lives in the 统计分析 layer
// alongside 执行复盘, NOT under 工艺 (工艺 only shows a small 实际校准 marker).
function CalibScreen({ onNav }) {
  const { Badge } = window.APSDesignSystem_edbc5d;
  const { ControlButton: Button, TransferButton, MetricStrip, Metric, DataTable: Table } = window.APSWorkbenchUI;
  const { useState } = React;

  const SEED = [
    { id: "P-1042-20", part: "P-1042", op: "20 数铣", type: "数铣", quota: "8.5", actual: "11.8", n: 8, dev: 39, state: "up", suggest: "11.8" },
    { id: "P-1042-30", part: "P-1042", op: "30 钳工", type: "钳工", quota: null, actual: "1.2", n: 6, dev: null, state: "seed", suggest: "1.2" },
    { id: "T-1009-10", part: "T-1009", op: "10 数铣", type: "数铣", quota: "9.0", actual: "9.4", n: 15, dev: 4, state: "ok", suggest: null },
    { id: "P-1042-50", part: "P-1042", op: "50 总检", type: "总检", quota: "0.0", actual: null, n: 2, dev: null, state: "few", suggest: null },
    { id: "T-1021-20", part: "T-1021", op: "20 钻孔", type: "钻孔", quota: "1.5", actual: "1.1", n: 11, dev: -27, state: "down", suggest: "1.1" },
  ];

  const [adopted, setAdopted] = useState({});
  const [onlyDev, setOnlyDev] = useState(false);
  const [q, setQ] = useState("");

  const devColor = (d) => (Math.abs(d) > 20 ? "var(--ui-danger-text)" : Math.abs(d) > 8 ? "var(--ui-warning-text)" : "var(--ui-success-text)");
  const devText = (r) => (r.dev == null ? "—" : (r.dev > 0 ? "+" : "") + r.dev + "%");

  const STATE_META = {
    up:   { tone: "danger",  label: "建议上调" },
    down: { tone: "danger",  label: "建议下调" },
    seed: { tone: "warning", label: "缺定额 · 可补建" },
    ok:   { tone: "ok",      label: "实际较定额" },
    few:  { tone: "secondary", label: "样本积累中" },
  };

  let rows = SEED.filter((r) => !q || (r.part + r.op + r.type).toLowerCase().includes(q.toLowerCase()));
  if (onlyDev) rows = rows.filter((r) => r.dev != null && Math.abs(r.dev) > 20);

  const summary = [
    { label: "在产工序", value: 126, helper: "正在排产、有实际工时回流的工序" },
    { sev: "danger",  label: "偏差 > 20%", value: 14,  helper: "实际与定额差距大，建议复核" },
    { label: "可采纳", value: 9, helper: "样本充足且偏差明确，仅演示采纳标记" },
    { sev: "warning", label: "样本不足",  value: 23,  helper: "实际次数太少，先继续积累" },
  ];

  const cols = [
    { key: "part", title: "图号 / 工序", width: 150, render: (r) => (
      <span><a className="bd-link" href="#" onClick={(e) => { e.preventDefault(); window.APSDetail && window.APSDetail.open(r.part); }} style={{ color: "var(--ui-primary)", fontWeight: 600, cursor: "pointer", textDecoration: "none" }}>{r.part}</a> <span className="muted" style={{ color: "var(--ui-muted)" }}>· {r.op}</span></span>
    ) },
    { key: "type", title: "工种", width: 90 },
    { key: "quota", title: "定额单件", width: 110, render: (r) => r.quota != null
      ? <span style={{ fontVariantNumeric: "tabular-nums" }}>{r.quota}<span className="muted" style={{ color: "var(--ui-muted)", marginLeft: 4 }}>h</span></span>
      : <span style={{ color: "var(--ui-muted)" }}>缺定额</span> },
    { key: "actual", title: "实际中位数", width: 160, render: (r) => r.actual != null
      ? <span style={{ fontVariantNumeric: "tabular-nums" }}>{r.actual} <span className="muted" style={{ color: "var(--ui-muted)" }}>h · {r.n} 次</span></span>
      : <span style={{ color: "var(--ui-muted)" }}>样本不足 · {r.n} 次</span> },
    { key: "dev", title: "偏差", width: 90, render: (r) => (
      <strong style={{ color: r.dev == null ? "var(--ui-muted)" : devColor(r.dev), fontVariantNumeric: "tabular-nums" }}>{devText(r)}</strong>
    ) },
    { key: "state", title: "状态", width: 150, render: (r) => {
      const m = STATE_META[r.state];
      return <Badge className="calib-badge" tone={m.tone} dot>{m.label}{r.state === "ok" ? " " + devText(r) : ""}</Badge>;
    } },
    { key: "act", title: "操作", width: 150, render: (r) => {
      if (adopted[r.id]) return <Badge className="calib-badge" tone="ok" dot>样例已采纳</Badge>;
      if (r.state === "ok") return <span className="muted" style={{ fontSize: 12, color: "var(--ui-muted)" }}>无需调整</span>;
      if (r.state === "few") return <Button variant="secondary" size="sm" disabled>采纳</Button>;
      return <Button variant="secondary" size="sm" onClick={() => setAdopted((a) => ({ ...a, [r.id]: true }))}>采纳 {r.suggest}</Button>;
    } },
  ];

  return (
    <section className="calib-workbench" aria-label="工时定额校准">
      <div className="dash-head">
        <div>
          <div className="eyebrow">统计分析 · 校准样例</div>
          <h3>工时定额校准</h3>
          <p className="dash-note" style={{ maxWidth: 920 }}>
            当前为校准样例，展示实际单件工时中位数与定额单件工时的对比。
            <strong>采纳只更新本页标记，未写入本机定额。</strong>
          </p>
        </div>
      </div>

      <MetricStrip>
        {summary.map((s, i) => (
          <Metric key={i} label={s.label} value={s.value} helper={s.helper} tone={s.sev} />
        ))}
      </MetricStrip>

      <section className="calib-list" aria-label="校准明细">
        <div className="table-tools">
          <h3>校准明细</h3>
          <input className="tool-input" aria-label="搜索校准明细" placeholder="搜索图号、工序、工种…" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="tool-right wb-actions">
            <Button variant={onlyDev ? "primary" : "secondary"} size="sm" aria-pressed={onlyDev} onClick={() => setOnlyDev((v) => !v)}>仅看偏差 &gt; 20%</Button>
            <TransferButton kind="export" onClick={() => window.APSDetail && window.APSDetail.toast("导出工时校准明细 · 示例操作")}>导出</TransferButton>
          </div>
        </div>
        <div className="bd-table-scroll wb-table-frame">
          <Table columns={cols} rows={rows} rowKey="id" />
        </div>
        <p className="bd-sec-sub" style={{ marginTop: 12, fontSize: 12, color: "var(--ui-muted)" }}>
          校准样例明细 · 在产工序总量 126 道为示例统计
        </p>
        <details className="calib-notes"><summary>采纳与定额维护说明</summary><p>当前样例不执行定额写回、留痕或工艺联动。正式接入后，才可对比近 N 次实际单件工时中位数（剔除暂停 / 异常），复核采纳后写回工序定额，并记录来源、采纳人、日期；定额室导入只覆盖未锁定项，工艺侧显示「实际校准」标记。</p></details>
      </section>
    </section>
  );
}

window.CalibScreen = CalibScreen;
