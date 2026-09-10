// APS Workbench · 基础资料 shared primitives  →  window.BD.*
// Reusable design-system pieces: tabs, fields, toggle, Excel 三步流向导,
// inline-edit helpers, flash, confirm dialog, empty state, pager, summary.
(function () {
  const { useState, useRef, useEffect } = React;
  const DS = () => window.APSDesignSystem_edbc5d;

  /* ---------- canonical 工种 seed (shared across 工艺 / 自制 / 外协 / 设备 / 人员 / 供应商) ---------- */
  const OP_TYPES_SEED = [
    { op_type_id: "OT001", name: "数铣", category: "internal", remark: "" },
    { op_type_id: "OT002", name: "数车", category: "internal", remark: "" },
    { op_type_id: "OT003", name: "钳工", category: "internal", remark: "" },
    { op_type_id: "OT004", name: "精磨", category: "internal", remark: "" },
    { op_type_id: "OT005", name: "钻孔", category: "internal", remark: "" },
    { op_type_id: "OT006", name: "总检", category: "internal", remark: "关键工序" },
    { op_type_id: "OT007", name: "标印", category: "internal", remark: "" },
    { op_type_id: "OT008", name: "表处理", category: "internal", remark: "" },
    { op_type_id: "OT051", name: "电镀", category: "external", remark: "" },
    { op_type_id: "OT052", name: "发黑", category: "external", remark: "" },
    { op_type_id: "OT053", name: "热处理", category: "external", remark: "" },
    { op_type_id: "OT054", name: "喷涂", category: "external", remark: "" },
  ];
  const opTypeNames = (cat) => OP_TYPES_SEED.filter((o) => !cat || o.category === cat).map((o) => o.name);

  /* ---------- segmented control (结构切换 / 二选一) ---------- */
  function Seg({ options, value, onChange, ariaLabel }) {
    return (
      <div className="bd-seg" role="group" aria-label={ariaLabel}>
        {options.map((o) => (
          <button key={o.value} type="button" className="bd-seg-btn" aria-pressed={value === o.value} onClick={() => onChange(o.value)}>
            {o.label}
          </button>
        ))}
      </div>
    );
  }

  /* ---------- status chips list (技能工种 / 多标签) ---------- */
  function Chips({ items, tone }) {
    if (!items || !items.length) return <span className="muted">-</span>;
    return (
      <span className="bd-chips">
        {items.map((t) => <span key={t} className={"bd-chip" + (tone ? " tone-" + tone : "")}>{t}</span>)}
      </span>
    );
  }

  /* ---------- multi-select checkbox group (人员技能工种) ---------- */
  function CheckGroup({ options, value, onChange }) {
    const set = new Set(value || []);
    const toggle = (v) => { const n = new Set(set); n.has(v) ? n.delete(v) : n.add(v); onChange(Array.from(n)); };
    return (
      <div className="bd-check-group">
        {options.map((o) => (
          <label key={o} className={"bd-check" + (set.has(o) ? " is-on" : "")}>
            <input type="checkbox" checked={set.has(o)} onChange={() => toggle(o)} />
            {o}
          </label>
        ))}
      </div>
    );
  }

  /* ---------- 一级 / 二级 tab ---------- */
  function PrimaryTabs({ tabs, value, onChange }) {
    return (
      <div className="bd-tabs" role="tablist" aria-label="基础资料分段">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            className="bd-tab"
            data-chain={t.chain || undefined}
            aria-current={value === t.id ? "page" : undefined}
            onClick={() => onChange(t.id)}
          >
            {t.label}
            {t.chain ? <span className="bd-tab-dot" /> : null}
          </button>
        ))}
      </div>
    );
  }

  function SubTabs({ tabs, value, onChange }) {
    return (
      <div className="bd-subtabs" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            className="bd-subtab"
            aria-current={value === t.id ? "true" : undefined}
            onClick={() => onChange(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
    );
  }

  /* ---------- form field ---------- */
  function Field({ label, required, hint, wide, error, children }) {
    return (
      <div className={"bd-field" + (wide ? " bd-wide" : "") + (error ? " is-error" : "")}>
        {label ? (
          <label>{label}{required ? <span className="req">*</span> : null}</label>
        ) : null}
        {children}
        {error ? <span className="bd-field-error">{error}</span> : (hint ? <span className="bd-hint">{hint}</span> : null)}
      </div>
    );
  }

  function StrictSeg({ checked, onChange, onText, offText, disabled, ariaLabel }) {
    const on = onText || "严格拦截";
    const off = offText || "宽松放行";
    return (
      <div className="bd-seg" role="group" aria-label={ariaLabel}>
        <button type="button" className="bd-seg-btn" aria-pressed={checked} disabled={disabled}
          style={{ "--bd-seg-accent": "var(--ui-warning)" }}
          onClick={() => !disabled && onChange(true)}>
          <span className="bd-seg-dot" />{on}
        </button>
        <button type="button" className="bd-seg-btn" aria-pressed={!checked} disabled={disabled}
          style={{ "--bd-seg-accent": "var(--ui-primary)" }}
          onClick={() => !disabled && onChange(false)}>
          <span className="bd-seg-dot" />{off}
        </button>
      </div>
    );
  }

  /* outcome accents for the 数据校验 preview line */
  const STRICT_OC = { wrap: { "--oc-bg": "var(--ui-warning-bg)", "--oc-border": "var(--ui-warning-border)", "--oc-text": "var(--ui-warning-text)", "--oc-accent": "var(--ui-warning)" }, ico: "!", lead: "严格拦截。", desc: "数据不正确就停下并提示原因，不生成工序。" };
  const LOOSE_OC  = { wrap: { "--oc-bg": "var(--ui-info-bg)",    "--oc-border": "var(--ui-info-border)",    "--oc-text": "var(--ui-info-text)",    "--oc-accent": "var(--ui-primary)" }, ico: "i", lead: "宽松放行。", desc: "能确认的工序先生成，缺项按默认值记录并提醒补正。" };

  function Toggle({ checked, onChange, label, help, onText, offText }) {
    const oc = checked ? STRICT_OC : LOOSE_OC;
    return (
      <div className="bd-toggle-field">
        <label>数据校验</label>
        <StrictSeg checked={checked} onChange={onChange} onText={onText} offText={offText} ariaLabel={label || "数据校验"} />
        <div className="bd-seg-outcome" style={oc.wrap}>
          <span className="oc-ico">{oc.ico}</span>
          <span><b>{oc.lead}</b>{oc.desc}</span>
        </div>
        {help ? (
          <details className="bd-toggle-help">
            <summary>查看详细规则</summary>
            <div>{help}</div>
          </details>
        ) : null}
      </div>
    );
  }

  /* ---------- date input wired to the page's APSDatePicker (not the native control) ---------- */
  function DateInput({ value, onChange, className, placeholder, disabled, min, max }) {
    const ref = useRef(null);
    useEffect(() => {
      const el = ref.current;
      if (el && window.APSDatePicker) window.APSDatePicker.enhance(el);
    }, []);
    // keep the (uncontrolled) DOM value in sync when the value prop changes externally (e.g. form reset)
    useEffect(() => {
      const el = ref.current;
      if (el && el.value !== (value || "")) el.value = value || "";
    }, [value]);
    return (
      <input ref={ref} type="date" className={className || "bd-input"}
        placeholder={placeholder} disabled={disabled} min={min} max={max}
        defaultValue={value || ""} onChange={(e) => onChange(e.target.value)} />
    );
  }

  /* ---------- flash ---------- */
  function useFlash() {
    const [flash, setFlash] = useState(null);
    const show = (tone, msg) => setFlash({ tone, msg, id: Date.now() });
    return [flash, show, () => setFlash(null)];
  }
  function Flash({ flash }) {
    const [closedId, setClosedId] = useState(null);
    useEffect(() => {
      if (!flash) return;
      const ms = (flash.tone === "danger" || flash.tone === "warning") ? 6000 : 3600;
      const t = setTimeout(() => setClosedId(flash.id), ms);
      return () => clearTimeout(t);
    }, [flash && flash.id]);
    if (!flash || closedId === flash.id) return null;
    // Portal to <body> so the fixed-position toast never sits as a flow sibling
    // (otherwise `.bd-card-gap > * + *` would push the page content down 16px).
    return ReactDOM.createPortal(
      <div className="bd-toast" role="status" aria-live="polite" key={flash.id}>
        <div className={"bd-flash tone-" + flash.tone}>
          <span className="bd-flash-dot" />
          <span>{flash.msg}</span>
          <button type="button" className="bd-toast-close" aria-label="关闭" onClick={() => setClosedId(flash.id)}>×</button>
        </div>
      </div>,
      document.body
    );
  }

  /* ---------- empty state ---------- */
  function Empty({ title, desc }) {
    return (
      <div className="bd-empty">
        <div className="be-title">{title}</div>
        {desc ? <div className="be-desc">{desc}</div> : null}
      </div>
    );
  }

  /* ---------- confirm dialog ---------- */
  function ConfirmButton({ label, variant = "danger", size = "sm", title, body, confirmLabel = "确认删除", onConfirm, btnStyle }) {
    const { ControlButton: Button } = window.APSWorkbenchUI;
    const [open, setOpen] = useState(false);
    return (
      <>
        <Button variant={variant} size={size} style={btnStyle} onClick={() => setOpen(true)}>{label}</Button>
        {open ? (
          <div className="bd-modal-backdrop" onClick={() => setOpen(false)}>
            <div className="bd-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
              <div className="bd-modal-head"><h4>{title || "确认删除"}</h4></div>
              <div className="bd-modal-body">{body}</div>
              <div className="bd-modal-foot">
                <Button variant="secondary" size="md" onClick={() => setOpen(false)}>取消</Button>
                <Button variant="danger" size="md" onClick={() => { setOpen(false); onConfirm && onConfirm(); }}>{confirmLabel}</Button>
              </div>
            </div>
          </div>
        ) : null}
      </>
    );
  }

  /* ---------- pager (display only) ---------- */
  function Pager({ page, totalPages, total, onPrev, onNext }) {
    if (!totalPages || totalPages <= 1) return null;
    return (
      <div className="bd-info-line">
        <span className="muted">第 {page} / {totalPages} 页（共 {total} 条）</span>
        {page > 1 ? <a className="bd-link" onClick={onPrev}>上一页</a> : null}
        {page < totalPages ? <a className="bd-link" onClick={onNext}>下一页</a> : null}
      </div>
    );
  }

  /* ---------- summary strip ---------- */
  function SummaryGrid({ items }) {
    const { MetricStrip, Metric } = window.APSWorkbenchUI;
    return (
      <MetricStrip columns={items.length}>
        {items.map((it) => (
          <Metric key={it.label} label={it.label} value={it.value} tone={it.sev} />
        ))}
      </MetricStrip>
    );
  }

  function InfoStrip({ cells }) {
    return (
      <div className="bd-info-strip">
        {cells.map((c) => (
          <div className="is-cell" key={c.k}>
            <span className="is-k">{c.k}</span>
            <span className="is-v">{c.v}</span>
          </div>
        ))}
      </div>
    );
  }

  /* ---------- Excel action cards ---------- */
  function ActionCards({ title, subtitle, cards, onOpen }) {
    const { TransferButton } = window.APSWorkbenchUI;
    return (
      <div className="bd-card-section">
        <h3 className="bd-sec-title">{title}</h3>
        <p className="bd-sec-sub">{subtitle}</p>
        <div className="bd-action-cards">
          {cards.map((c) => (
            <div className={"bd-action-card" + (c.cycle ? " tone-cycle" : "")} key={c.title}>
              <div className="ac-title">{c.title}</div>
              <div className="ac-desc">{c.desc}</div>
              <div className="ac-actions wb-actions">
                {c.wizard ? (
                  <TransferButton kind="import" onClick={() => onOpen(c.wizard)}>{c.maintainLabel || "批量维护"}</TransferButton>
                ) : null}
                {c.exportLabel ? (
                  <TransferButton kind="export">{c.exportLabel}</TransferButton>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  /* ---------- Excel 三步流向导 ---------- */
  const STATUS_META = {
    new: { label: "新增", tone: "success" },
    update: { label: "更新", tone: "primary" },
    unchanged: { label: "无变化", tone: "secondary" },
    skip: { label: "跳过", tone: "warning" },
    error: { label: "错误", tone: "danger" },
  };

  function ExcelWizard({ wiz, onClose, onDone }) {
    const { Panel, Badge } = DS();
    const { ControlButton: Button, TransferButton, DataTable: Table } = window.APSWorkbenchUI;
    const [step, setStep] = useState(1);
    const [fileName, setFileName] = useState("");
    const [mode, setMode] = useState((wiz.modeOptions && wiz.modeOptions[0].value) || "overwrite");
    const [strict, setStrict] = useState(false);
    const rows = wiz.sampleRows || DEFAULT_SAMPLE;
    const hasError = rows.some((r) => r.status === "error");

    const checkCols = [
      { key: "row_num", title: "行号", width: 70, align: "right", render: (r) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{r.row_num}</span> },
      { key: "status", title: "结果", width: 90, render: (r) => <Badge tone={STATUS_META[r.status].tone} dot>{STATUS_META[r.status].label}</Badge> },
      { key: "message", title: "问题或说明", render: (r) => <span style={{ color: r.status === "error" ? "var(--ui-danger-text)" : "inherit" }}>{r.message}</span> },
      { key: "detail", title: "详情", width: 90, render: (r) => <RowDetail r={r} /> },
    ];

    return (
      <Panel
        className="wb-page-panel"
        title={wiz.title}
        description={wiz.desc}
        headerRight={<Button variant="ghost" size="sm" onClick={onClose}>← 返回列表</Button>}
      >
        <div className="bd-wizard-steps">
          {["选择并上传", "检查结果", "写入系统"].map((s, i) => {
            const n = i + 1;
            const cls = step > n ? "is-done" : step === n ? "is-active" : "";
            return (
              <div className={"bd-wstep " + cls} key={s}>
                <span className="ws-num">{step > n ? "✓" : n}</span>{s}
              </div>
            );
          })}
        </div>

        {/* step 1 */}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
          <TransferButton kind="template">下载模板（.xlsx）</TransferButton>
          <TransferButton kind="export">导出当前数据</TransferButton>
        </div>
        <div className="bd-form-grid" style={{ marginBottom: 14 }}>
          <Field label="导入模式">
            <select className="bd-select" value={mode} onChange={(e) => setMode(e.target.value)} disabled={step > 1}>
              {(wiz.modeOptions || DEFAULT_MODES).map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </Field>
          {wiz.strict ? (
            <Field label="数据校验" hint="严格：不认识的工种/缺周期等会直接报错并停止；宽松会尽量写入并提示补正。">
              <StrictSeg checked={strict} onChange={setStrict} disabled={step > 1} ariaLabel="数据校验" />
            </Field>
          ) : null}
        </div>
        <div className="bd-upload" style={{ marginBottom: 16 }}>
          <input
            type="file" accept=".xlsx" disabled={step > 1}
            onChange={(e) => setFileName(e.target.files && e.target.files[0] ? e.target.files[0].name : "")}
            aria-label="选择 Excel 文件"
          />
          <span className="up-file">{fileName ? fileName : <span className="muted">仅支持 .xlsx，表头不要改，只读第一个工作表</span>}</span>
          {step === 1 ? (
            <TransferButton kind="import" variant="primary" disabled={!fileName} onClick={() => setStep(2)} style={{ marginLeft: "auto" }}>上传并检查</TransferButton>
          ) : null}
        </div>

        {/* step 2: check result */}
        {step >= 2 ? (
          <div style={{ marginBottom: 16 }}>
            <h3 className="bd-sec-title" style={{ fontSize: 15 }}>检查结果</h3>
            <p className="bd-sec-sub">行号对应 Excel 中的实际行数；把错误行全部修完才能写入。</p>
            <div className="bd-table-scroll wb-table-frame"><Table columns={checkCols} rows={rows} rowKey="row_num" /></div>
            {hasError ? (
              <div className="bd-flash tone-danger" style={{ marginTop: 12 }}>
                <span className="bd-flash-dot" /><span>仍有错误行，请修正后重新上传；检查阶段有错误时不能写入系统。</span>
              </div>
            ) : null}
            {step === 2 ? (
              <div className="bd-form-footer">
                <TransferButton kind="import" onClick={() => setStep(1)}>重新上传</TransferButton>
                <TransferButton kind="import" variant="primary" disabled={hasError} onClick={() => { setStep(3); }}>确认写入系统</TransferButton>
              </div>
            ) : null}
          </div>
        ) : null}

        {/* step 3: done */}
        {step >= 3 ? (
          <div className="bd-flash tone-ok" style={{ marginBottom: 4 }}>
            <span className="bd-flash-dot" />
            <span>{summarize(rows)} 已写入系统并记录操作留痕。建议再导出一次当前数据复核。</span>
          </div>
        ) : null}
        {step >= 3 ? (
          <div className="bd-form-footer">
            <TransferButton kind="import" onClick={() => { setStep(1); setFileName(""); }}>再导入一批</TransferButton>
            <Button variant="primary" size="md" onClick={() => { onDone && onDone(summarize(rows)); onClose(); }}>完成，返回列表</Button>
          </div>
        ) : null}
      </Panel>
    );
  }

  function summarize(rows) {
    const c = { new: 0, update: 0, skip: 0 };
    rows.forEach((r) => { if (c[r.status] != null) c[r.status]++; });
    const parts = [];
    if (c.new) parts.push("新增 " + c.new + " 条");
    if (c.update) parts.push("更新 " + c.update + " 条");
    if (c.skip) parts.push("跳过 " + c.skip + " 条");
    return parts.length ? parts.join("、") : "无变化";
  }

  function RowDetail({ r }) {
    const [open, setOpen] = useState(false);
    return (
      <details className="bd-row-detail" open={open} onToggle={(e) => setOpen(e.target.open)}>
        <summary className="bd-link" style={{ fontSize: 12 }}>查看数据</summary>
        <pre style={{ margin: "6px 0 0", fontSize: 11.5, background: "var(--ui-surface-muted)", border: "1px solid var(--ui-border)", borderRadius: "var(--wb-radius-surface)", padding: 8, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
{JSON.stringify(r.data || {}, null, 2)}
        </pre>
      </details>
    );
  }

  const DEFAULT_MODES = [
    { value: "overwrite", label: "更新已有，新增缺少" },
    { value: "append", label: "只导入新编号" },
    { value: "replace", label: "清空本类数据后重导" },
  ];
  const DEFAULT_SAMPLE = [
    { row_num: 2, status: "update", message: "已存在，更新 2 个字段", data: { 图号: "T-1008", 名称: "回转壳体 A" } },
    { row_num: 3, status: "new", message: "新增记录", data: { 图号: "T-1020", 名称: "端盖 E" } },
    { row_num: 4, status: "unchanged", message: "与系统一致，跳过", data: { 图号: "T-1009", 名称: "回转壳体 B" } },
    { row_num: 5, status: "skip", message: "模式为“只导入新编号”，已存在故跳过", data: { 图号: "T-1011" } },
  ];

  /* ============================================================ */
  /* 零件 / 图号 共享数据源 — 排产基础资料（工艺模板）与批次管理共用同一份  */
  /* 在工艺模板里新增/编辑/删除零件，批次的图号下拉会实时同步。            */
  /* ============================================================ */
  const PARTS_SEED = [
    {
      part_no: "T-1008", part_name: "回转壳体 A", remark: "主力件",
      route_raw: "5数铣 10钳 20数车 30外协电镀 35外协发黑 40总检 45表处理", parsed: true,
      ops: [
        { seq: 5, op_type: "数铣", source: "internal", setup: 0.5, unit: 1.2 },
        { seq: 10, op_type: "钳工", source: "internal", setup: 0.3, unit: 0.8 },
        { seq: 20, op_type: "数车", source: "internal", setup: 0.4, unit: 1.0 },
        { seq: 30, op_type: "电镀", source: "external", supplier: "华表面处理", group: "G1", ext_days: 3 },
        { seq: 35, op_type: "发黑", source: "external", supplier: "华表面处理", group: "G1", ext_days: 2 },
        { seq: 40, op_type: "总检", source: "internal", setup: 0.2, unit: 0.3 },
        { seq: 45, op_type: "表处理", source: "internal", setup: 0.3, unit: 0.6 },
      ],
      groups: [{ id: "G1", start: 30, end: 35, mode: "separate", total: null, strict: false, deletable: true }],
    },
    {
      part_no: "T-1009", part_name: "回转壳体 B", remark: "",
      route_raw: "5数铣 10钳 20数车 30精磨 40总检", parsed: true,
      ops: [
        { seq: 5, op_type: "数铣", source: "internal", setup: 0.5, unit: 1.1 },
        { seq: 10, op_type: "钳工", source: "internal", setup: 0.3, unit: 0.7 },
        { seq: 20, op_type: "数车", source: "internal", setup: 0.4, unit: 1.0 },
        { seq: 30, op_type: "精磨", source: "internal", setup: 0.6, unit: 1.3 },
        { seq: 40, op_type: "总检", source: "internal", setup: 0.2, unit: 0.3 },
      ],
      groups: [],
    },
    {
      part_no: "T-1011", part_name: "端盖 C", remark: "待复核外协周期",
      route_raw: "5数车 10钻孔 20外协热处理 25外协喷涂 30总检", parsed: false,
      ops: [
        { seq: 5, op_type: "数车", source: "internal", setup: 0.3, unit: 0.5 },
        { seq: 10, op_type: "钻孔", source: "internal", setup: 0.2, unit: 0.4 },
        { seq: 20, op_type: "热处理", source: "external", supplier: "金鼎热处理", group: "G1", ext_days: 4 },
        { seq: 25, op_type: "喷涂", source: "external", supplier: "—", group: "G1", ext_days: null },
        { seq: 30, op_type: "总检", source: "internal", setup: 0.2, unit: 0.3 },
      ],
      groups: [{ id: "G1", start: 20, end: 25, mode: "merged", total: 6, strict: false, deletable: true }],
    },
    {
      part_no: "T-1014", part_name: "法兰 D", remark: "草稿",
      route_raw: "", parsed: false, ops: [], groups: [],
    },
  ];

  let _parts = PARTS_SEED;
  const _partsSubs = new Set();
  const setParts = (updater) => {
    _parts = typeof updater === "function" ? updater(_parts) : updater;
    _partsSubs.forEach((fn) => fn());
  };
  // React hook: every screen that calls this re-renders when the shared list changes.
  const usePartsStore = () => {
    const [, force] = React.useState(0);
    React.useEffect(() => {
      const fn = () => force((n) => n + 1);
      _partsSubs.add(fn);
      return () => _partsSubs.delete(fn);
    }, []);
    return [_parts, setParts];
  };
  const partName = (pn) => (_parts.find((p) => p.part_no === pn) || {}).part_name || "";
  const findPart = (pn) => _parts.find((p) => p.part_no === pn) || null;

  window.BD = {
    PrimaryTabs, SubTabs, Field, Toggle, Seg, StrictSeg, DateInput, Flash, useFlash, Empty,
    ConfirmButton, Pager, SummaryGrid, InfoStrip, ActionCards, ExcelWizard,
    STATUS_META, DEFAULT_MODES,
    Chips, CheckGroup, OP_TYPES_SEED, opTypeNames,
    usePartsStore, partName, findPart, PARTS_SEED,
  };
})();
