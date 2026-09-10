// APS Workbench · 基础资料 › 工作日历 tab — 新增/更新某一天（自定义日期选择器）+ 已配置日历（只读）
(function () {
  const { useState, useRef, useEffect } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;

  const TODAY = "2026-06-16";
  const SEED_ROWS = [
    { date: "2026-06-19", day_type: "workday", start: "08:00", end: "20:00", hours: 11, eff: 1.0, normal: "yes", urgent: "yes", remark: "周末前加班" },
    { date: "2026-06-22", day_type: "holiday", start: "", end: "", hours: 0, eff: 0, normal: "no", urgent: "no", remark: "厂休" },
    { date: "2026-06-25", day_type: "workday", start: "08:00", end: "17:00", hours: 8, eff: 0.9, normal: "yes", urgent: "yes", remark: "" },
    { date: "2026-06-28", day_type: "workday", start: "08:00", end: "12:00", hours: 4, eff: 1.0, normal: "no", urgent: "yes", remark: "调休·仅急件" },
  ];
  const dayTypeZh = (t) => (t === "holiday" ? "假期" : "工作日");
  const yesNo = (v) => (v === "yes" ? "是" : "否");

  function CalendarTab({ flashFn, onNav }) {
    const { Panel, Button, Table } = DS();
    const { Field, Empty } = B();
    const [rows, setRows] = useState(SEED_ROWS);
    const blank = { date: "", day_type: "workday", start: "08:00", end: "", hours: "", eff: "", normal: "yes", urgent: "yes", remark: "" };
    const [form, setForm] = useState(blank);
    const [errors, setErrors] = useState({});
    const setField = (patch) => { setForm((f) => ({ ...f, ...patch })); setErrors((e) => { const n = { ...e }; Object.keys(patch).forEach((k) => delete n[k]); return n; }); };

    const configured = new Set(rows.map((r) => r.date));

    const submit = () => {
      const errs = {};
      if (!form.date) errs.date = "请先选择日期。";
      if (form.eff !== "" && Number(form.eff) <= 0) errs.eff = "效率必须大于 0。";
      if (Object.keys(errs).length) { setErrors(errs); return; }
      setErrors({});
      const exists = configured.has(form.date);
      const row = { ...form, hours: form.hours === "" ? 0 : Number(form.hours), eff: form.eff === "" ? (form.day_type === "holiday" ? 0 : 1) : Number(form.eff) };
      setRows((arr) => exists ? arr.map((r) => (r.date === form.date ? row : r)) : [...arr, row].sort((a, b) => a.date.localeCompare(b.date)));
      flashFn("ok", (exists ? "已更新 " : "已新增 ") + form.date + " 的工作日历。");
      setForm(blank);
    };

    const cols = [
      { key: "date", title: "日期", width: 130, render: (r) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{r.date}</span> },
      { key: "day_type", title: "类型", width: 90, render: (r) => dayTypeZh(r.day_type) },
      { key: "start", title: "班次开始", width: 100, render: (r) => r.start || "08:00" },
      { key: "end", title: "班次结束", width: 100, render: (r) => r.end || <span className="muted">-</span> },
      { key: "hours", title: "可用工时", width: 100, align: "right" },
      { key: "eff", title: "效率", width: 90, align: "right", render: (r) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{Number(r.eff).toFixed(1)}</span> },
      { key: "normal", title: "允许普通件", width: 120, render: (r) => yesNo(r.normal) },
      { key: "urgent", title: "允许急件", width: 110, render: (r) => yesNo(r.urgent) },
      { key: "remark", title: "说明", render: (r) => r.remark || <span className="muted">-</span> },
    ];

    const headerRight = (
      <>
        <Button variant="secondary" size="sm" onClick={() => onNav && onNav("run")}>去执行排产</Button>
        <Button variant="secondary" size="sm">批量维护工作日历</Button>
      </>
    );

    return (
      <div className="bd-card-gap">
        <Panel title="工作日历配置" description="设置排产用的工作时间、效率和可排产优先级；未配置的日期按默认规则处理，也可在这里配置调休或加班。" headerRight={headerRight}>
          <div className="bd-flash tone-info" style={{ marginBottom: 4 }}>
            <span className="bd-flash-dot" />
            <span>默认规则：未配置的日期按 <strong>周一至周五 8 小时、周末不排产</strong> 处理；法定假期、调休和周末加班需要在这里手工维护。</span>
          </div>
        </Panel>

        <Panel title="新增 / 更新某一天" description="同一日期重复提交即为更新；保存后立即生效于排产。">
          <div className="bd-cal-form-grid">
            <Field label="日期" required wide error={errors.date}>
              <DatePicker value={form.date} configured={configured} onPick={(d) => setField({ date: d })} />
            </Field>
            <Field label="类型" required>
              <select className="bd-select" value={form.day_type} onChange={(e) => setForm({ ...form, day_type: e.target.value })}>
                <option value="workday">工作日</option>
                <option value="holiday">假期</option>
              </select>
            </Field>
            <Field label="班次开始"><input className="bd-input w-time" type="time" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} /></Field>
            <Field label="班次结束" hint="可选"><input className="bd-input w-time" type="time" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} /></Field>
            <Field label="可用工时（小时）"><input className="bd-input num" placeholder="如：8" value={form.hours} onChange={(e) => setForm({ ...form, hours: e.target.value })} /></Field>
            <Field label="效率（大于 0）" error={errors.eff}><input className="bd-input num" placeholder="如：1.0" value={form.eff} onChange={(e) => setField({ eff: e.target.value })} /></Field>
            <Field label="允许普通件" required>
              <select className="bd-select" value={form.normal} onChange={(e) => setForm({ ...form, normal: e.target.value })}><option value="yes">是</option><option value="no">否</option></select>
            </Field>
            <Field label="允许急件 / 特急" required>
              <select className="bd-select" value={form.urgent} onChange={(e) => setForm({ ...form, urgent: e.target.value })}><option value="yes">是</option><option value="no">否</option></select>
            </Field>
            <Field label="说明" wide><input className="bd-input" placeholder="可选" value={form.remark} onChange={(e) => setForm({ ...form, remark: e.target.value })} /></Field>
          </div>
          <div className={"bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")}>
            {Object.keys(errors).length ? <span className="bd-form-error">请修正标红的必填项</span> : null}
            <Button variant="primary" size="md" onClick={submit}>保存</Button>
          </div>
        </Panel>

        <Panel title="已配置日历" description="只读列表；要改某天，在上方表单填同一日期重新提交即可。">
          {rows.length ? <div className="bd-table-scroll"><Table columns={cols} rows={rows} rowKey="date" /></div>
            : <Empty title="暂无已配置的日历记录" desc="排产时会自动按默认规则处理：周一到周五 8 小时、周六周日不排产；法定假期、调休和周末加班要自己维护。" />}
        </Panel>
      </div>
    );
  }

  /* ---------- custom date picker ---------- */
  const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];
  const pad = (n) => String(n).padStart(2, "0");
  const ymd = (y, m, d) => y + "-" + pad(m + 1) + "-" + pad(d);

  function DatePicker({ value, configured, onPick }) {
    const { Button } = DS();
    const [open, setOpen] = useState(false);
    const init = value ? value.split("-") : TODAY.split("-");
    const [cur, setCur] = useState({ y: Number(init[0]), m: Number(init[1]) - 1 });
    const ref = useRef(null);

    useEffect(() => {
      if (!open) return;
      const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
      document.addEventListener("mousedown", onDoc);
      return () => document.removeEventListener("mousedown", onDoc);
    }, [open]);

    const firstDay = new Date(cur.y, cur.m, 1);
    const startOffset = (firstDay.getDay() + 6) % 7; // Monday-based
    const daysInMonth = new Date(cur.y, cur.m + 1, 0).getDate();
    const cells = [];
    for (let i = 0; i < startOffset; i++) cells.push(null);
    for (let d = 1; d <= daysInMonth; d++) cells.push(d);

    const hint = value ? (() => {
      const dt = new Date(value + "T00:00:00");
      const wd = WEEKDAYS[(dt.getDay() + 6) % 7];
      const isCfg = configured.has(value);
      return "已选：" + value + "（周" + wd + "）" + (isCfg ? " · 已配置，重提交将更新" : " · 未配置");
    })() : "";

    return (
      <div className="bd-date-field" ref={ref}>
        <div className="bd-date-input-row">
          <input className="bd-input w-sm" placeholder="如：2026-06-16" value={value} onChange={(e) => onPick(e.target.value)} />
          <Button variant="secondary" size="sm" onClick={() => setOpen((o) => !o)}>选择</Button>
        </div>
        {hint ? <div className="bd-hint" style={{ marginTop: 6 }}>{hint}</div> : null}
        {open ? (
          <div className="bd-cal-panel">
            <div className="bd-cal-header">
              <button type="button" className="bd-cal-nav" aria-label="上个月" onClick={() => setCur((c) => c.m === 0 ? { y: c.y - 1, m: 11 } : { y: c.y, m: c.m - 1 })}>‹</button>
              <span className="bd-cal-title">{cur.y} 年 {cur.m + 1} 月</span>
              <button type="button" className="bd-cal-nav" aria-label="下个月" onClick={() => setCur((c) => c.m === 11 ? { y: c.y + 1, m: 0 } : { y: c.y, m: c.m + 1 })}>›</button>
            </div>
            <div className="bd-cal-week">{WEEKDAYS.map((w) => <span className="bd-cal-wd" key={w}>{w}</span>)}</div>
            <div className="bd-cal-grid">
              {cells.map((d, i) => {
                if (d == null) return <span className="bd-cal-cell is-empty" key={"e" + i} />;
                const ds = ymd(cur.y, cur.m, d);
                const col = (startOffset + d - 1) % 7;
                const weekend = col >= 5;
                const cls = ["bd-cal-cell"];
                if (weekend) cls.push("is-weekend");
                if (configured.has(ds)) cls.push("is-configured");
                if (ds === TODAY) cls.push("is-today");
                if (ds === value) cls.push("is-selected");
                return <button type="button" className={cls.join(" ")} key={ds} onClick={() => { onPick(ds); setOpen(false); }}>{d}</button>;
              })}
            </div>
            <div className="bd-cal-foot">
              <span className="bd-cal-legend"><span className="lg-dot cfg" />已配置</span>
              <span className="bd-cal-legend"><span className="lg-dot we" />周末</span>
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  window.CalendarTab = CalendarTab;
})();
