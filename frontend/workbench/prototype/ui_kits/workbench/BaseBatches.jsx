// APS Workbench · 批次管理 — 全功能复刻（列表 + 主从工作区）
// List (批量维护 / 新增 / 批量操作) → master-detail：① 基础信息 ② 同步工艺 ③ 工序概况 ④ 批次工序（设备/人员/工时/外协补齐）
// 参考「排产基础资料 · 零件工艺模板」的主从范式重做，未照搬仓库旧版（旧版把方案/配置/快照堆在列表页）。
(function () {
  const { useState, useEffect } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;
  const Draft = window.APSBatchDraft;
  if (!Draft) throw new Error("BaseBatches.jsx 需要先加载 batch-draft-model.js。");
  function useSessionState(key, initial) {
    const [, refresh] = useState(0);
    React.useLayoutEffect(() => Draft.subscribe(() => refresh((n) => n + 1)), []);
    return [Draft.getDraft(key, initial), (next) => Draft.setDraft(key, typeof next === "function" ? next(Draft.getDraft(key, initial)) : next)];
  }
  function BatchIcon({ name }) {
    const nodes = window.APSFieldReports.iconNodes[name];
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{nodes.map(([tag, attrs], i) => React.createElement(tag, { ...attrs, key: i }))}</svg>;
  }
  function BatchDateInput({ value, onChange }) {
    const ref = React.useRef(null);
    useEffect(() => {
      const el = ref.current;
      // Keep manual date entry unobstructed; the existing calendar button and ArrowDown still open the picker.
      const typingFocus = (e) => e.stopImmediatePropagation();
      const typingClick = (e) => e.stopPropagation();
      el.addEventListener("focus", typingFocus, true);
      el.addEventListener("click", typingClick);
      if (window.APSDatePicker) window.APSDatePicker.enhance(el);
      return () => { el.removeEventListener("focus", typingFocus, true); el.removeEventListener("click", typingClick); };
    }, []);
    useEffect(() => { if (ref.current.value !== value) ref.current.value = value || ""; }, [value]);
    return <span className="batch-date-control"><input ref={ref} className="bd-input" type="text" data-aps-date="true" placeholder="YYYY-MM-DD" defaultValue={value || ""} onInput={(e) => onChange(e.target.value)} /></span>;
  }

  /* ---------------- reference data ---------------- */
  const PRIORITY = {
    normal: { label: "普通", tone: "secondary" },
    urgent: { label: "急件", tone: "warning" },
    critical: { label: "特急", tone: "danger" },
  };
  const READY = {
    yes: { label: "齐套", tone: "ok" },
    partial: { label: "部分齐套", tone: "warning" },
    no: { label: "未齐套", tone: "danger" },
  };
  const STATUS = {
    pending: { label: "待排", tone: "secondary" },
    scheduled: { label: "已排", tone: "notice" },
    processing: { label: "加工中", tone: "warning" },
    completed: { label: "已完成", tone: "ok" },
    cancelled: { label: "已取消", tone: "secondary" },
  };

  // 图号（零件）来自共享数据源：“排产基础资料 · 零件工艺模板”。
  // 这里不再本地硬编码零件清单，统一读 window.BD（详见 BaseShared.jsx）。
  const partName = (pn) => window.BD.partName(pn);

  const MACHINES = [
    { value: "M-03", label: "M-03 五轴加工中心 · 精加工" },
    { value: "M-05", label: "M-05 卧式加工中心 · 预加工" },
    { value: "M-07", label: "M-07 立式加工中心 · 组装" },
    { value: "M-12", label: "M-12 三坐标检测 · 检验" },
    { value: "M-18", label: "M-18 数控车床 · 车加工" },
  ];
  const OPERATORS = [
    { value: "P-021", label: "P-021 张三 · 精加工" },
    { value: "P-024", label: "P-024 李四 · 组装" },
    { value: "P-030", label: "P-030 王五 · 检验" },
    { value: "P-033", label: "P-033 赵六 · 车加工" },
  ];
  const SUPPLIERS = [
    { value: "华表面处理", label: "华表面处理" },
    { value: "金鼎热处理", label: "金鼎热处理" },
  ];
  // 人员-设备关联（双向联动约束）：选了设备后，仅这些人员可与之组合。
  const MACHINE_OPERATORS = Draft.machineOperators;
  const labelOf = (list, v) => { const o = list.find((x) => x.value === v); return o ? o.label : v; };

  // 幽灵红：危险操作与建设性操作明显分离（方案 B 选择条内的「删除所选」）
  const GHOST_DANGER = { background: "var(--ui-card-bg)", borderColor: "var(--ui-border)", color: "var(--ui-danger)" };

  const io = (seq, op_type, machine, operator, setup, unit, done) =>
    ({ seq, op_code: null, op_type, source: "internal", machine, operator, setup, unit, done });
  const ex = (seq, op_type, supplier, ext_days, group, mode, total, done) =>
    ({ seq, op_code: null, op_type, source: "external", supplier, ext_days, group, mode, total, done });

  const SEED = [
    {
      batch_id: "B202605-018", part_no: "T-1008", quantity: 12, due_date: "2026-05-24", ready_date: "2026-05-22",
      priority: "critical", ready_status: "yes", status: "processing", remark: "客户催货",
      ops: [
        io(5, "数铣", "M-03", "P-021", 0.5, 1.2, true),
        io(10, "钳工", "M-07", "P-024", 0.3, 0.8, true),
        io(20, "数车", "M-18", "P-033", 0.4, 1.0, true),
        ex(30, "电镀", "华表面处理", 3, "G1", "separate", null, true),
        ex(35, "发黑", "华表面处理", 2, "G1", "separate", null, true),
        io(40, "总检", "M-12", "P-030", 0.2, 0.3, false),
        io(45, "表处理", "", "", 0.3, 0.6, false),
      ],
    },
    {
      batch_id: "B202605-021", part_no: "T-1009", quantity: 8, due_date: "2026-05-25", ready_date: "2026-05-23",
      priority: "urgent", ready_status: "partial", status: "scheduled", remark: "",
      ops: [
        io(5, "数铣", "M-03", "P-021", 0.5, 1.1, true),
        io(10, "钳工", "M-07", "P-024", 0.3, 0.7, true),
        io(20, "数车", "M-18", "P-033", 0.4, 1.0, false),
        io(30, "精磨", "M-05", "P-021", 0.6, 1.3, false),
        io(40, "总检", "M-12", "P-030", 0.2, 0.3, false),
      ],
    },
    {
      batch_id: "B202605-011", part_no: "T-1011", quantity: 6, due_date: "2026-05-25", ready_date: "",
      priority: "normal", ready_status: "yes", status: "pending", remark: "待复核外协周期",
      ops: [
        io(5, "数车", "M-18", "P-033", 0.3, 0.5, false),
        io(10, "钻孔", "M-05", "", 0.2, 0.4, false),
        ex(20, "热处理", "金鼎热处理", null, "G1", "merged", 6, false),
        ex(25, "喷涂", "", null, "G1", "merged", 6, false),
        io(30, "总检", "M-12", "P-030", 0.2, 0.3, false),
      ],
    },
    {
      batch_id: "B202605-024", part_no: "T-1014", quantity: 4, due_date: "2026-05-26", ready_date: "",
      priority: "normal", ready_status: "no", status: "pending", remark: "草稿，工序未生成", ops: [],
    },
    {
      batch_id: "B202605-017", part_no: "T-1008", quantity: 10, due_date: "2026-05-26", ready_date: "2026-05-20",
      priority: "normal", ready_status: "yes", status: "completed", remark: "",
      ops: [
        io(5, "数铣", "M-03", "P-021", 0.5, 1.2, true),
        io(10, "钳工", "M-07", "P-024", 0.3, 0.8, true),
        io(20, "数车", "M-18", "P-033", 0.4, 1.0, true),
        ex(30, "电镀", "华表面处理", 3, "G1", "separate", null, true),
        ex(35, "发黑", "华表面处理", 2, "G1", "separate", null, true),
        io(40, "总检", "M-12", "P-030", 0.2, 0.3, true),
        io(45, "表处理", "M-07", "P-024", 0.3, 0.6, true),
      ],
    },
  ].map((b) => ({ ...b, ops: b.ops.map((o) => ({ ...o, op_code: b.batch_id + "-" + String(o.seq).padStart(2, "0") })) }));
  Draft.initialize(SEED);

  const doneCount = (ops) => ops.filter((o) => o.done).length;
  const gapCount = Draft.gapCount;
  let lastContext = null;

  /* ============================================================ SCREEN */
  function BatchesScreen({ onNav, initialContext } = {}) {
    const [, refresh] = useState(0);
    React.useLayoutEffect(() => Draft.subscribe(() => refresh((n) => n + 1)), []);
    const batches = Draft.getBatches();
    const setBatches = (next) => Draft.replaceBatches(typeof next === "function" ? next(Draft.getBatches()) : next);
    const [view, setView] = useSessionState("view", "list");
    const [openId, setOpenId] = useSessionState("openId", null);
    const [location, setLocation] = useSessionState("location", null);
    const [wiz, setWiz] = useState(null);
    const [flash, showFlash, clear] = B().useFlash();
    const { Flash } = B();
    const flashFn = (tone, msg) => showFlash(tone, msg);
    React.useLayoutEffect(() => {
      if (!initialContext || initialContext === lastContext) return;
      lastContext = initialContext;
      if (!["gaps", "unready"].includes(initialContext.focus) && !Array.isArray(initialContext.batchIds)) return;
      setLocation({ focus: initialContext.focus || "", ...(Array.isArray(initialContext.batchIds) ? { batchIds: initialContext.batchIds.slice() } : {}) });
      ["q", "fStatus", "fReady"].forEach((key) => Draft.setDraft(key, ""));
      Draft.setDraft("columnFilters", {});
      Draft.setDraft("listModal", null);
      setView("list"); setOpenId(null);
    }, [initialContext]);

    const openDetail = (id) => { setOpenId(id); setView("detail"); window.scrollTo({ top: 0 }); };
    const back = () => { setView("list"); setOpenId(null); window.scrollTo({ top: 0 }); };
    const updateBatch = (id, patch) => setBatches((arr) => arr.map((b) => (b.batch_id === id ? { ...b, ...patch } : b)));
    const deleteBatch = (id) => setBatches((arr) => arr.filter((b) => b.batch_id !== id));

    let body;
    if (view === "detail" && batches.some((b) => b.batch_id === openId)) {
      body = <BatchDetail key={openId} batch={batches.find((b) => b.batch_id === openId)} focus={location && location.focus} onBack={back} onUpdate={updateBatch} onDelete={deleteBatch} flashFn={flashFn} />;
    } else {
      body = <BatchList batches={batches} setBatches={setBatches} location={location} onOpen={openDetail} onWiz={setWiz} flashFn={flashFn} />;
    }
    return (
      <div className="bd-card-gap batch-workbench">
        <div className="batch-session-bar">
          <span>原型会话 · 刷新页面即重置 · 未写入生产数据</span>
          {location ? <span className="batch-location">{location.focus === "gaps" ? "定位：工序待补齐" : location.focus === "unready" ? "定位：未齐套" : "定位：指定批次"}{Array.isArray(location.batchIds) ? " · " + location.batchIds.join("、") : ""}<button className="bd-link" onClick={() => setLocation(null)}>清除定位</button></span> : null}
          {onNav ? <button className="bd-link batch-return" onClick={() => onNav("run")}>返回排产</button> : null}
        </div>
        <Flash flash={flash} />
        {body}
        {wiz ? <BatchImportModal wiz={wiz} onClose={() => setWiz(null)} onDone={() => { flashFn("warning", "原型尚未接入 Excel 导入，未写入任何批次。"); setWiz(null); }} /> : null}
      </div>
    );
  }

  /* ============================================================ IMPORT MODAL（单步 · 弹窗） */
  function BatchImportModal({ wiz, onClose, onDone }) {
    const { ControlButton: Button, TransferButton } = window.APSWorkbenchUI;
    const { Field } = B();
    const modes = [
      { value: "overwrite", label: "已有批次就更新，没有的就新增" },
      { value: "append", label: "只新增没有的批次（已有的跳过）" },
      { value: "replace", label: "先清空全部批次，再按表格重导" },
    ];
    const [mode, setMode] = useState(modes[0].value);
    const [fileName, setFileName] = useState("");

    useEffect(() => {
      const onKey = (e) => { if (e.key === "Escape") onClose(); };
      document.addEventListener("keydown", onKey);
      return () => document.removeEventListener("keydown", onKey);
    }, []);

    const confirm = () => {
      if (!fileName) return;
      onDone();
    };

    return (
      <div className="bd-modal-backdrop" onClick={onClose}>
        <div className="bd-modal" role="dialog" aria-modal="true" style={{ width: "min(560px, 100%)" }} onClick={(e) => e.stopPropagation()}>
          <div className="bd-modal-head" style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "16px 18px 14px", borderBottom: "1px solid var(--ui-border)" }}>
            <span style={{ width: 38, height: 38, borderRadius: "var(--wb-radius-surface)", background: "var(--ui-primary-soft)", color: "var(--ui-primary)", display: "grid", placeItems: "center", flex: "none" }} aria-hidden="true">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 16V4M7 9l5-5 5 5" /><path d="M5 16v4h14v-4" /></svg>
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <h4 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>{wiz.title || "批量维护批次"}</h4>
              <div className="muted" style={{ fontSize: 12, marginTop: 2, lineHeight: 1.5 }}>{wiz.desc || "通过 Excel 成批新增或更新批次。"}</div>
            </div>
            <button className="bd-modal-x" onClick={onClose} aria-label="关闭" style={{ flex: "none", width: 30, height: 30, border: "none", background: "transparent", color: "var(--ui-muted)", cursor: "pointer", borderRadius: "var(--wb-radius-control)", display: "grid", placeItems: "center", fontSize: 18, lineHeight: 1 }}>×</button>
          </div>

          <div className="bd-modal-body" style={{ padding: "16px 18px", color: "var(--ui-text)" }}>
            {/* 模板下载 */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", border: "1px solid var(--ui-border)", borderRadius: "var(--wb-radius-surface)", background: "var(--ui-surface-muted)", marginBottom: 14 }}>
              <span style={{ width: 32, height: 32, borderRadius: "var(--wb-radius-surface)", background: "var(--ui-card-bg)", border: "1px solid var(--ui-border)", display: "grid", placeItems: "center", color: "var(--ui-success)", flex: "none" }} aria-hidden="true">
                <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5" /><path d="M9.5 13l1.8 1.8L15 11" /></svg>
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>批次导入模板.xlsx</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>含字段说明与示例行，按模板填写后上传</div>
              </div>
              <TransferButton kind="template" disabled title="原型尚未提供模板文件">下载模板</TransferButton>
            </div>

            {/* 导入模式 */}
            <div style={{ marginBottom: 14 }}>
              <Field label="导入模式">
                <select className="bd-select" value={mode} onChange={(e) => setMode(e.target.value)}>
                  {modes.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </Field>
            </div>

            {/* 上传 */}
            <div className="bd-upload">
              <input type="file" accept=".xlsx" aria-label="选择 Excel 文件"
                onChange={(e) => setFileName(e.target.files && e.target.files[0] ? e.target.files[0].name : "")} />
              <span className="up-file">{fileName ? fileName : <span className="muted">仅支持 .xlsx，表头不要改，只读第一个工作表</span>}</span>
            </div>

            <p className="muted" style={{ fontSize: 12, lineHeight: 1.6, margin: "13px 2px 0" }}>
              原型尚未接入 Excel 解析与写入，选择文件不会新增、覆盖或删除批次。
            </p>
          </div>

          <div className="bd-modal-foot">
            <Button variant="secondary" size="md" onClick={onClose}>取消</Button>
            <TransferButton kind="import" variant="primary" disabled={!fileName} onClick={confirm}>确认导入</TransferButton>
          </div>
        </div>
      </div>
    );
  }

  /* ---------------- generic popup card (弹出式卡片) ---------------- */
  const ICONBOX = { width: 38, height: 38, borderRadius: "var(--wb-radius-surface)", background: "var(--ui-primary-soft)", color: "var(--ui-primary)", display: "grid", placeItems: "center", flex: "none" };
  const MODAL_X = { flex: "none", width: 30, height: 30, border: "none", background: "transparent", color: "var(--ui-muted)", cursor: "pointer", borderRadius: "var(--wb-radius-control)", display: "grid", placeItems: "center", fontSize: 18, lineHeight: 1 };

  function Modal({ title, desc, icon, width = 560, onClose, footer, children }) {
    useEffect(() => {
      const onKey = (e) => { if (e.key === "Escape") onClose(); };
      document.addEventListener("keydown", onKey);
      return () => document.removeEventListener("keydown", onKey);
    }, []);
    return (
      <div className="bd-modal-backdrop" onClick={onClose}>
        <div className="bd-modal" role="dialog" aria-modal="true" aria-label={title} style={{ width: "min(" + width + "px, 100%)", maxHeight: "calc(100vh - 48px)", display: "flex", flexDirection: "column" }} onClick={(e) => e.stopPropagation()}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "16px 18px 14px", borderBottom: "1px solid var(--ui-border)", flex: "none" }}>
            {icon ? <span style={ICONBOX} aria-hidden="true">{icon}</span> : null}
            <div style={{ flex: 1, minWidth: 0 }}>
              <h4 style={{ margin: 0, fontSize: 17, fontWeight: 600 }}>{title}</h4>
              {desc ? <div className="muted" style={{ fontSize: 12, marginTop: 3, lineHeight: 1.55 }}>{desc}</div> : null}
            </div>
            <button className="bd-modal-x" onClick={onClose} aria-label="关闭" style={MODAL_X}>×</button>
          </div>
          <div style={{ padding: "16px 18px", color: "var(--ui-text)", overflowY: "auto", flex: 1, minHeight: 0 }}>{children}</div>
          {footer ? <div className="bd-modal-foot" style={{ flex: "none" }}>{footer}</div> : null}
        </div>
      </div>
    );
  }

  function BulkPreview({ preview, onCancel, onConfirm, error }) {
    const { ControlButton: Button } = window.APSWorkbenchUI;
    const title = { modify: "确认批量修改", copy: "确认复制批次", delete: "确认删除批次" }[preview.kind];
    return <Modal title={title} width={820} onClose={onCancel}
      desc={"共 " + preview.rows.length + " 条受影响记录；确认后仅修改本原型会话。"}
      footer={<>{error ? <span className="bd-inline-err" role="alert">{error}</span> : null}<Button variant="secondary" onClick={onCancel}>取消</Button><Button variant={preview.kind === "delete" ? "danger" : "primary"} onClick={onConfirm}>{preview.kind === "delete" ? "确认删除" : "确认变更"}</Button></>}>
      <div className="batch-preview-scroll"><table className="batch-preview-table"><thead><tr><th>批次 / 图号</th><th>字段</th><th>旧值</th><th>新值</th></tr></thead><tbody>
        {preview.rows.map((row) => row.fields.map((field, i) => <tr key={row.id + ":" + i} data-batch-preview={row.id}><td>{row.id}<br/><span className="muted">{row.part}</span></td><td>{field.label}</td><td>{field.before}</td><td>{field.after}</td></tr>))}
      </tbody></table></div>
    </Modal>;
  }

  // The shared table owns private filter state; local headers keep batch selection and filters in one session model.
  function BatchColumnHead({ column, rows, sort, setSort, filters, setFilters }) {
    const [open, setOpen] = useState(false);
    const active = Object.prototype.hasOwnProperty.call(filters, column.key);
    const values = Array.from(new Set(rows.map((row) => String(row[column.key])))).sort();
    const selected = active ? filters[column.key] : values;
    useEffect(() => {
      if (!open) return;
      const close = (e) => { if (e.key === "Escape") setOpen(false); };
      document.addEventListener("keydown", close);
      return () => document.removeEventListener("keydown", close);
    }, [open]);
    const clear = () => setFilters((current) => { const next = { ...current }; delete next[column.key]; return next; });
    return <span className="batch-col-head">
      <button type="button" className="batch-sort aps-th-sortable" title={"排序：" + column.title} onClick={() => setSort(sort && sort.key === column.key ? sort.dir === "asc" ? { key: column.key, dir: "desc" } : null : { key: column.key, dir: "asc" })}>
        <span>{column.title}</span><span className={"aps-sortglyph " + (sort && sort.key === column.key ? sort.dir : "")} />
      </button>
      <button type="button" className={"aps-filter-btn" + (active ? " on" : "")} aria-label={"筛选" + column.title} title={"筛选" + column.title} onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setOpen(open ? false : { left: Math.max(8, Math.min(r.left, window.innerWidth - 240)), top: Math.min(r.bottom + 5, window.innerHeight - 310) }); }}><BatchIcon name="chevron-down" /></button>
      {open ? ReactDOM.createPortal(<div className="batch-workbench"><span className="batch-filter-dismiss" onClick={() => setOpen(false)} /><span className="batch-column-pop" style={{ left: open.left, top: Math.max(8, open.top) }} role="dialog" aria-label={"筛选" + column.title}>
        <label><input type="checkbox" checked={values.every((v) => selected.includes(v))} onChange={(e) => e.target.checked ? clear() : setFilters({ ...filters, [column.key]: [] })} />全部</label>
        <span className="batch-column-values">{values.map((value) => <label key={value}><input type="checkbox" checked={selected.includes(value)} onChange={(e) => setFilters({ ...filters, [column.key]: e.target.checked ? [...selected, value] : selected.filter((v) => v !== value) })} />{Draft.display(column.key, value)}</label>)}</span>
        <button className="bd-link" onClick={clear}>清除本列</button><button className="bd-link" onClick={() => setOpen(false)}>完成</button>
      </span></div>, document.body) : null}
    </span>;
  }

  /* ---------------- anchored filter popover ---------------- */
  function FilterPop({ fStatus, setFStatus, fReady, setFReady, onClose }) {
    const { ControlButton: Button } = window.APSWorkbenchUI;
    const { Field } = B();
    useEffect(() => {
      const onKey = (e) => { if (e.key === "Escape") onClose(); };
      document.addEventListener("keydown", onKey);
      return () => document.removeEventListener("keydown", onKey);
    }, []);
    return (
      <>
        <div style={{ position: "fixed", inset: 0, zIndex: 50 }} onClick={onClose} />
        <div className="bd-pop" role="dialog" aria-label="筛选批次" onClick={(e) => e.stopPropagation()}>
          <p className="bd-pop-title">按条件筛选</p>
          <Field label="状态">
            <select className="bd-select" value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
              <option value="">（全部）</option>
              {Object.keys(STATUS).map((k) => <option key={k} value={k}>{STATUS[k].label}</option>)}
            </select>
          </Field>
          <Field label="齐套显示">
            <select className="bd-select" value={fReady} onChange={(e) => setFReady(e.target.value)}>
              <option value="">（全部）</option>
              {Object.keys(READY).map((k) => <option key={k} value={k}>{READY[k].label}</option>)}
            </select>
          </Field>
          <div className="bd-pop-foot">
            <Button variant="ghost" size="sm" onClick={() => { setFStatus(""); setFReady(""); }}>清除筛选</Button>
            <Button variant="primary" size="sm" onClick={onClose}>完成</Button>
          </div>
        </div>
      </>
    );
  }

  /* ============================================================ LIST */
  function BatchList({ batches, setBatches, location, onOpen, onWiz, flashFn }) {
    const { Badge } = DS();
    const { ControlButton: Button, TransferButton, DataTable: Table } = window.APSWorkbenchUI;
    const { Field, Empty } = B();
    const DateInput = BatchDateInput;
    const [q, setQ] = useSessionState("q", "");
    const [fStatus, setFStatus] = useSessionState("fStatus", "");
    const [fReady, setFReady] = useSessionState("fReady", "");
    const [columnFilters, setColumnFilters] = useSessionState("columnFilters", {});
    const [sort, setSort] = useSessionState("listSort", null);
    const [expanded, setExpanded] = useSessionState("expanded", {});
    const [modal, setModal] = useSessionState("listModal", null);    // "add" | "bulk"
    const [filterOpen, setFilterOpen] = useState(false);
    const [sel, setSel] = useSessionState("selection", {});
    const [bulk, setBulk] = useSessionState("bulkForm", { priority: "", due_date: "", remark: "" });
    const [preview, setPreview] = useSessionState("bulkPreview", null);
    const [bulkErr, setBulkErr] = useState(null); // { scope: "sel" | "edit", msg }
    const [form, setForm] = useSessionState("addForm", { batch_id: "", part_no: "", quantity: "", due_date: "", priority: "normal", ready_status: "yes", ready_date: "", remark: "" });
    const [errors, setErrors] = useState({});
    const setField = (patch) => { setForm((f) => ({ ...f, ...patch })); setErrors((e) => { const n = { ...e }; Object.keys(patch).forEach((k) => delete n[k]); return n; }); };
    const [PARTS] = B().usePartsStore(); // 共享零件库：在工艺模板新增/删除图号会实时反映到下拉
    // 行内提示：操作结果就近显示在工具条同一行（参照现场记录工具条的保存状态），无需把视线移到角落
    const [tip, setTip] = useState(null); // { tone: "ok"|"warning", msg, id }
    useEffect(() => {
      if (!tip) return;
      const ms = tip.tone === "warning" ? 5000 : 3200;
      const t = setTimeout(() => setTip(null), ms);
      return () => clearTimeout(t);
    }, [tip && tip.id]);
    const tipFn = (tone, msg) => setTip({ tone, msg, id: Date.now() });

    const cards = [
      { title: "批量维护批次", desc: "按计划表整批新增或更新批次：批次号、图号、数量、交期、优先级一次写入，生成失败的行计为错误不写入。",
        maintainLabel: "批量维护批次",
        wizard: { kind: "batches", title: "批量维护批次", desc: "确认写入后按行创建/更新批次；批次号已存在则按导入模式处理。", strict: true,
          sampleRows: [
            { row_num: 2, status: "new", message: "新增批次", data: { 批次号: "B202605-031", 图号: "T-1009", 数量: 8, 交期: "06-02" } },
            { row_num: 3, status: "update", message: "已存在，更新数量/交期", data: { 批次号: "B202605-018", 数量: 12, 交期: "05-24" } },
            { row_num: 4, status: "error", message: "图号 T-9999 不存在，需先在工艺模板登记", data: { 批次号: "B202605-032", 图号: "T-9999" } },
          ] } },
      { title: "导出批次清单", desc: "导出当前筛选下的批次（批次号、图号、数量、交期、优先级、齐套与状态），用于复核或离线分发。", exportLabel: "导出批次清单" },
    ];

    const filteredRows = Draft.query(batches, { status: fStatus, ready: fReady, search: q, location }, partName);
    const list = Draft.query(filteredRows, { columns: columnFilters, sort });
    const selIds = batches.filter((b) => sel[b.batch_id]).map((b) => b.batch_id);
    const selCount = selIds.length;
    const visibleSelected = list.filter((b) => sel[b.batch_id]).length;
    useEffect(() => { setBulkErr((e) => (e && e.scope === "sel" && selCount ? null : e)); }, [selCount]);
    useEffect(() => { setBulkErr((e) => (e && e.scope === "edit" && (bulk.priority || bulk.due_date || bulk.remark) ? null : e)); }, [bulk.priority, bulk.due_date, bulk.remark]);
    const toggleAll = (on) => setSel((s) => Draft.toggleVisible(s, list, on));

    const Progress = ({ ops }) => {
      if (!ops.length) return <span className="muted" style={{ fontSize: 12.5 }}>未生成</span>;
      const d = doneCount(ops), t = ops.length, pct = Math.round((d / t) * 100);
      const col = pct === 100 ? "var(--ui-success)" : pct === 0 ? "var(--ui-muted)" : "var(--ui-primary)";
      return (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ position: "relative", width: 54, height: 6, borderRadius: "var(--wb-radius-control)", background: "var(--ui-surface-soft)", overflow: "hidden", flex: "none" }}>
            <span style={{ position: "absolute", inset: 0, width: pct + "%", background: col, borderRadius: "var(--wb-radius-control)" }} />
          </span>
          <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 12.5, color: "var(--ui-muted)" }}>{d} / {t}</span>
        </div>
      );
    };

    const cols = [
      { key: "sel", title: <input type="checkbox" aria-label="全选当前筛选" ref={(el) => { if (el) el.indeterminate = visibleSelected > 0 && visibleSelected < list.length; }} checked={list.length > 0 && visibleSelected === list.length} onChange={(e) => toggleAll(e.target.checked)} />, width: 44,
        render: (r) => <input type="checkbox" aria-label={"选择 " + r.batch_id} checked={!!sel[r.batch_id]} onChange={(e) => setSel((s) => ({ ...s, [r.batch_id]: e.target.checked }))} /> },
      { key: "batch_id", title: "批次号", width: 150, render: (r) => <button className="bd-link batch-id-link" onClick={() => onOpen(r.batch_id)}>{r.batch_id}</button> },
      { key: "part_no", title: "图号", width: 150, render: (r) => <span><strong style={{ fontWeight: 600 }}>{r.part_no}</strong> <span className="muted" style={{ fontSize: 12 }}>{partName(r.part_no)}</span></span> },
      { key: "quantity", title: "数量", width: 70, align: "right", render: (r) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{r.quantity}</span> },
      { key: "due_date", title: "交期", width: 110, nowrap: true, render: (r) => r.due_date ? <span style={{ fontVariantNumeric: "tabular-nums" }}>{r.due_date}</span> : <span className="muted">-</span> },
      { key: "prog", title: "工序进度", width: 150, render: (r) => <div><Progress ops={r.ops} /><details open={!!expanded[r.batch_id]} onToggle={(e) => { if (e.currentTarget.open !== !!expanded[r.batch_id]) setExpanded((s) => ({ ...s, [r.batch_id]: e.currentTarget.open })); }}><summary aria-label={"展开工序 " + r.batch_id}>工序概况{gapCount(r.ops) ? " · 待补 " + gapCount(r.ops) : ""}</summary><div className="batch-inline-ops">{r.ops.length ? r.ops.map((op) => <div key={op.seq}>{op.seq} · {op.op_type}{Object.keys(Draft.opErrors(op)).length ? " · 待补齐" : ""}</div>) : "未生成工序"}</div></details></div> },
      { key: "priority", title: "优先级", width: 90, render: (r) => <Badge className="batch-badge" tone={PRIORITY[r.priority].tone} dot={r.priority !== "normal"}>{PRIORITY[r.priority].label}</Badge> },
      { key: "ready_status", title: "齐套显示", width: 96, render: (r) => <Badge className="batch-badge" tone={READY[r.ready_status].tone} dot>{READY[r.ready_status].label}</Badge> },
      { key: "status", title: "状态", width: 86, render: (r) => <Badge className="batch-badge" tone={STATUS[r.status].tone} dot>{STATUS[r.status].label}</Badge> },
      { key: "act", title: "操作", width: 140, render: (r) => (
        <div className="bd-cell-actions">
          <Button variant="secondary" size="sm" onClick={() => onOpen(r.batch_id)}>查看/编辑</Button>
          <button type="button" className="batch-delete-icon" title={"删除批次 " + r.batch_id} aria-label={"删除批次 " + r.batch_id} onClick={() => runBulk("delete", [r.batch_id])}><BatchIcon name="x" /></button>
        </div>
      ) },
    ];

    const submit = () => {
      const errs = Draft.validateBatch(form, batches, PARTS);
      if (Object.keys(errs).length) { setErrors(errs); return; }
      setErrors({});
      setBatches((arr) => [{ batch_id: form.batch_id.trim(), part_no: form.part_no, quantity: Number(form.quantity), due_date: form.due_date, ready_date: form.ready_date, priority: form.priority, ready_status: form.ready_status, remark: form.remark, status: "pending", ops: [] }, ...arr]);
      tipFn("ok", "已新增批次 " + form.batch_id + "（待排）");
      setForm({ batch_id: "", part_no: "", quantity: "", due_date: "", priority: "normal", ready_status: "yes", ready_date: "", remark: "" });
      setModal(null);
    };

    const runBulk = (kind, ids = selIds) => {
      const result = Draft.previewBulk(kind, ids, bulk);
      if (result.error) { setBulkErr({ scope: kind === "modify" ? "edit" : "sel", msg: result.error }); return; }
      setBulkErr(null); setPreview(result.preview);
    };
    const cancelPreview = () => { Draft.cancelBulk(); setPreview(null); setBulkErr(null); };
    const confirmPreview = () => {
      const result = Draft.confirmBulk(preview);
      if (result.error) { setBulkErr({ scope: "preview", msg: result.error }); return; }
      tipFn("ok", "已" + { modify: "修改", copy: "复制", delete: "删除" }[preview.kind] + " " + result.count + " 个批次（原型会话）");
      if (preview.kind === "delete") setSel((s) => { const next = { ...s }; preview.rows.forEach((r) => delete next[r.id]); return next; });
      if (preview.kind === "modify") setBulk({ priority: "", due_date: "", remark: "" });
      setPreview(null); setModal(null); setBulkErr(null);
    };

    const activeFilters = (fStatus ? 1 : 0) + (fReady ? 1 : 0);
    const filtered = fStatus || fReady || Object.keys(columnFilters).length;
    const tableCols = cols.map((column) => ({ ...column, sortable: false, filterable: false,
      title: ["sel", "prog", "act"].includes(column.key) ? column.title : <BatchColumnHead column={column} rows={filteredRows} sort={sort} setSort={setSort} filters={columnFilters} setFilters={setColumnFilters} /> }));

    return (
      <div className="bd-card-gap">
        <section className="batch-list" aria-label="批次列表">
          {/* 工具条：搜索 + 弹出式按钮 */}
          <div className="bd-listbar">
            <h3>批次列表</h3>
            <div className="bd-listbar-search">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
              <input className="bd-input" placeholder="搜索批次号、图号、零件名…" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <div className="bd-listbar-actions wb-actions">
              {tip ? (
                <span className="bd-listbar-tip" key={tip.id} style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, whiteSpace: "nowrap", marginRight: 2, color: tip.tone === "warning" ? "var(--ui-warning-text)" : "var(--ui-success-text)" }}>
                  <span style={{ width: 7, height: 7, borderRadius: "50%", flex: "none", background: tip.tone === "warning" ? "var(--ui-warning)" : "var(--ui-success)" }} />
                  {tip.msg}
                </span>
              ) : null}
              <div>
                <Button variant={filtered ? "primary" : "secondary"} size="md" onClick={() => setFilterOpen((o) => !o)}>
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6, verticalAlign: "-2px" }}><path d="M3 5h18l-7 8v5l-4 2v-7z" /></svg>
                  筛选{activeFilters ? <span className="bd-filter-count">{activeFilters}</span> : null}
                </Button>
                {filterOpen ? <FilterPop fStatus={fStatus} setFStatus={setFStatus} fReady={fReady} setFReady={setFReady} onClose={() => setFilterOpen(false)} /> : null}
              </div>
              <TransferButton kind="import" onClick={() => onWiz(cards[0].wizard)}>
                批量导入
              </TransferButton>
              <TransferButton kind="export" onClick={() => { tipFn("warning", selCount ? "原型尚未接入清单下载，未生成导出文件。" : "请先勾选要导出的批次"); }}>
                批量导出{selCount ? <span className="bd-filter-count">{selCount}</span> : null}
              </TransferButton>
              <Button variant="primary" size="md" onClick={() => setModal("add")}>
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6, verticalAlign: "-2px" }}><path d="M12 5v14M5 12h14" /></svg>
                新增批次
              </Button>
            </div>
          </div>

          {/* 生效中的筛选条件 */}
          {filtered ? (
            <div className="bd-filterchips">
              {fStatus ? <span className="bd-filterchip">状态：<b>{STATUS[fStatus].label}</b><button aria-label="清除状态筛选" onClick={() => setFStatus("")}>×</button></span> : null}
              {fReady ? <span className="bd-filterchip">齐套：<b>{READY[fReady].label}</b><button aria-label="清除齐套筛选" onClick={() => setFReady("")}>×</button></span> : null}
              {Object.keys(columnFilters).length ? <span>列筛选：{Object.keys(columnFilters).length} 项</span> : null}
              <button className="bd-link" style={{ fontSize: 12.5 }} onClick={() => { setFStatus(""); setFReady(""); setColumnFilters({}); }}>清除全部筛选</button>
            </div>
          ) : null}

          {list.length ? (
            <div className="bd-table-scroll wb-table-frame batch-list-table"><Table columns={tableCols} rows={list} rowKey="batch_id" /></div>
          ) : <Empty title={filtered || q || location ? "当前条件下暂无批次" : "暂无批次"} />}

          {selCount ? (
                <div className="bd-selbar">
                  <span className="selbar-count">已选 <strong>{selCount}</strong> 个批次{selCount > visibleSelected ? " · " + (selCount - visibleSelected) + " 个在当前筛选外" : ""}</span>
                  <div className="selbar-actions">
                    {bulkErr && bulkErr.scope === "sel" ? <span className="bd-inline-err">{bulkErr.msg}</span> : null}
                    <Button variant="secondary" size="md" onClick={() => { setBulkErr(null); setModal("bulk"); }}>批量修改</Button>
                    <Button variant="secondary" size="md" onClick={() => runBulk("copy")}>复制所选</Button>
                    <Button size="md" variant="secondary" style={GHOST_DANGER} onClick={() => runBulk("delete")}>删除所选</Button>
                    <Button size="md" variant="ghost" onClick={() => setSel({})}>清除选择</Button>
                  </div>
                </div>
          ) : null}
        </section>

        {/* ── 弹出式卡片：新增批次 ── */}
        {preview ? <BulkPreview preview={preview} onCancel={cancelPreview} onConfirm={confirmPreview} error={bulkErr && bulkErr.scope === "preview" ? bulkErr.msg : null} /> : null}
        {modal === "add" && !preview ? (
          <Modal title="新增批次" width={680} onClose={() => setModal(null)}
            desc="选图号 + 填数量与交期即可创建；工序在详情里按工艺模板生成后补齐资源。"
            icon={<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14" /></svg>}
            footer={<>
              {Object.keys(errors).length ? <span className="bd-form-error" style={{ marginRight: "auto" }}>请填写标红的必填项</span> : null}
              <Button variant="secondary" size="md" onClick={() => setModal(null)}>取消</Button>
              <Button variant="primary" size="md" onClick={submit}>创建批次</Button>
            </>}>
            <div className="bd-fieldset">
              <p className="bd-fieldset-label">标识</p>
              <div className="bd-grid-cols" style={{ gridTemplateColumns: "minmax(0,1.3fr) minmax(0,1.7fr) 110px" }}>
                <Field label="批次号" required error={errors.batch_id}><input className="bd-input" placeholder="如：B202605-031" value={form.batch_id} onChange={(e) => setField({ batch_id: e.target.value })} /></Field>
                <Field label="图号" required error={errors.part_no}>
                  <select className="bd-select" value={form.part_no} onChange={(e) => setField({ part_no: e.target.value })}>
                    <option value="">（请选择）</option>
                    {PARTS.map((p) => <option key={p.part_no} value={p.part_no}>{p.part_no} · {p.part_name}</option>)}
                  </select>
                </Field>
                <Field label="数量" required error={errors.quantity}><input className="bd-input num" type="number" min="1" step="1" placeholder="50" value={form.quantity} onChange={(e) => setField({ quantity: e.target.value })} /></Field>
              </div>
            </div>

            <div className="bd-fieldset">
              <p className="bd-fieldset-label">计划与齐套</p>
              <div className="bd-grid-cols" style={{ gridTemplateColumns: "repeat(2, minmax(0,1fr))" }}>
                <Field label="交期" error={errors.due_date} hint="可选；不填则不参与交期排序。"><DateInput value={form.due_date} onChange={(v) => setField({ due_date: v })} /></Field>
                <Field label="优先级">
                  <select className="bd-select" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
                    {Object.keys(PRIORITY).map((k) => <option key={k} value={k}>{PRIORITY[k].label}</option>)}
                  </select>
                </Field>
                <Field label="齐套显示">
                  <select className="bd-select" value={form.ready_status} onChange={(e) => setForm({ ...form, ready_status: e.target.value })}>
                    {Object.keys(READY).map((k) => <option key={k} value={k}>{READY[k].label}</option>)}
                  </select>
                </Field>
                <Field label="齐套日期" error={errors.ready_date}><DateInput value={form.ready_date} onChange={(v) => setField({ ready_date: v })} /></Field>
              </div>
              <div style={{ marginTop: 14 }}>
                <Field label="备注" wide><input className="bd-input" placeholder="可选" value={form.remark} onChange={(e) => setForm({ ...form, remark: e.target.value })} /></Field>
              </div>
            </div>

          </Modal>
        ) : null}

        {/* ── 弹出式卡片：批量修改 ── */}
        {modal === "bulk" && !preview ? (
          <Modal title="批量修改批次" width={560} onClose={() => setModal(null)}
            desc={"将对已选的 " + selCount + " 个批次生效 · 仅更新已填字段，留空不覆盖。"}
            icon={<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" /></svg>}
            footer={<>
              {bulkErr && bulkErr.scope === "edit" ? <span className="bd-inline-err" style={{ marginRight: "auto" }}>{bulkErr.msg}</span> : null}
              <Button variant="secondary" size="md" onClick={() => setModal(null)}>取消</Button>
              <Button variant="primary" size="md" onClick={() => runBulk("modify")}>预览变更</Button>
            </>}>
            <div className="bd-form-grid">
              <Field label="批量优先级（可选）">
                <select className="bd-select" value={bulk.priority} onChange={(e) => setBulk({ ...bulk, priority: e.target.value })}>
                  <option value="">（不修改）</option>
                  {Object.keys(PRIORITY).map((k) => <option key={k} value={k}>{PRIORITY[k].label}</option>)}
                </select>
              </Field>
              <Field label="批量交期（可选）"><DateInput value={bulk.due_date} onChange={(v) => setBulk({ ...bulk, due_date: v })} /></Field>
              <Field label="批量备注（可选）" wide><input className="bd-input" placeholder="填写则覆盖备注，留空不修改" value={bulk.remark} onChange={(e) => setBulk({ ...bulk, remark: e.target.value })} /></Field>
            </div>
          </Modal>
        ) : null}
      </div>
    );
  }

  /* ============================================================ DETAIL */
  function BatchDetail({ batch, focus, onBack, onUpdate, onDelete, flashFn }) {
    const { Panel, Badge } = DS();
    const { ControlButton: Button, DataTable: Table } = window.APSWorkbenchUI;
    const { Field, ConfirmButton, SummaryGrid, Empty } = B();
    const DateInput = BatchDateInput;
    const [base, setBase] = useSessionState("base:" + batch.batch_id, { quantity: batch.quantity, due_date: batch.due_date, priority: batch.priority, ready_status: batch.ready_status, ready_date: batch.ready_date, remark: batch.remark });
    const [strict, setStrict] = useSessionState("strict:" + batch.batch_id, false);
    const [errors, setErrors] = useState({});
    const dirty = Object.keys(base).some((key) => String(base[key]) !== String(batch[key]));
    const saveBase = () => {
      const errs = Draft.validateBatch({ ...batch, ...base }, Draft.getBatches(), null, batch.batch_id);
      setErrors(errs);
      if (Object.keys(errs).length) return;
      onUpdate(batch.batch_id, { ...base, quantity: Number(base.quantity) });
      Draft.clearDraft("base:" + batch.batch_id);
      flashFn("ok", "已保存批次基础信息（原型会话）。");
    };

    const ops = batch.ops;
    const internal = ops.filter((o) => o.source === "internal").length;
    const external = ops.filter((o) => o.source === "external").length;
    const gaps = gapCount(ops);

    const regenerate = () => {
      // 按零件工艺模板（共享数据源）刷新：以本批次图号去工艺模板取最新工序，而非批次旧快照。
      const tplPart = window.BD.findPart(batch.part_no);
      const tmpl = tplPart && tplPart.ops.length ? tplPart.ops : [];
      if (!tmpl.length) { flashFn("warning", "该图号暂无模板工序，未覆盖原批次。"); return; }
      if (strict && gapCount(tmpl)) { flashFn("warning", "模板有 " + gapCount(tmpl) + " 道工序资料不完整，未刷新。"); return; }
      batch.ops.forEach((op) => Draft.clearDraft("op:" + batch.batch_id + ":" + op.seq));
      onUpdate(batch.batch_id, { ops: tmpl.map((o) => ({ ...o, op_code: batch.batch_id + "-" + String(o.seq).padStart(2, "0"), done: false })) });
      flashFn(tmpl.length ? "ok" : "warning", tmpl.length ? "已按最新工艺模板刷新本批次工序（已清空之前补充的设备/人员/工时）。" : "该图号在工艺模板中暂无工序，请先到「排产基础资料」维护路线。");
    };

    const opCols = [
      { key: "op_code", title: "工序编码", width: 150, render: (r) => <code className="bd-code" title={r.op_code}>{r.op_code}</code> },
      { key: "seq", title: "工序", width: 70, align: "right", render: (r) => (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontVariantNumeric: "tabular-nums" }}>
          <span style={{ width: 3, height: 16, borderRadius: "var(--wb-radius-control)", background: r.source === "external" ? "var(--ui-warning)" : "var(--ui-primary)" }} />{r.seq}
        </span> ) },
      { key: "op_type", title: "工种", width: 96 },
      { key: "source", title: "归属", width: 84, render: (r) => <Badge className="batch-badge" tone="secondary">{r.source === "external" ? "外协" : "自制"}</Badge> },
      { key: "config", title: "资源补充", render: (r) => <OpConfigCell key={batch.batch_id + ":" + r.seq + ":" + r.source} op={r} batch={batch} onUpdate={onUpdate} flashFn={flashFn} /> },
      { key: "done", title: "完工", width: 96, render: (r) => {
        const idx = ops.findIndex((x) => x.seq === r.seq);
        const prevDone = idx === 0 || ops.slice(0, idx).every((x) => x.done);
        const tone = r.done ? "ok" : prevDone ? "notice" : "secondary";
        return <Badge className="batch-badge" tone={tone} dot>{r.done ? "已完工" : prevDone ? "进行中" : "待开工"}</Badge>;
      } },
    ];

    return (
      <div className="bd-card-gap batch-detail">
        <Panel className="wb-page-panel" title={"批次详情 · " + batch.batch_id} description="维护单个批次的基础信息，并补齐工序所需的设备、人员、工时与外协周期。"
          headerRight={<div className="bd-cell-actions">
            <Button variant="ghost" size="sm" onClick={onBack}>← 返回列表</Button>
            <ConfirmButton label="删除批次" variant="secondary" size="sm" title={"删除批次 " + batch.batch_id + "？"} body={<>删除本会话的 {batch.batch_id} / {batch.part_no}，数量 {batch.quantity}，以及 {batch.ops.length} 道工序和未提交草稿。不影响生产数据。确认删除吗？</>}
              onConfirm={() => { onDelete(batch.batch_id); flashFn("ok", "已删除批次 " + batch.batch_id + "。"); onBack(); }} />
          </div>}>
          <div className="bd-meta-row">
            <span><span className="bd-meta-label">图号：</span><strong>{batch.part_no}</strong> {partName(batch.part_no)}</span>
            <span><span className="bd-meta-label">数量：</span><strong style={{ fontVariantNumeric: "tabular-nums" }}>{batch.quantity}</strong></span>
            <span><span className="bd-meta-label">交期：</span><strong style={{ fontVariantNumeric: "tabular-nums" }}>{batch.due_date || "-"}</strong></span>
            <span><span className="bd-meta-label">优先级：</span><Badge className="batch-badge" tone={PRIORITY[batch.priority].tone} dot={batch.priority !== "normal"}>{PRIORITY[batch.priority].label}</Badge></span>
            <span><span className="bd-meta-label">齐套：</span><Badge className="batch-badge" tone={READY[batch.ready_status].tone} dot>{READY[batch.ready_status].label}</Badge></span>
            <span><span className="bd-meta-label">状态：</span><Badge className="batch-badge" tone={STATUS[batch.status].tone} dot>{STATUS[batch.status].label}</Badge></span>
          </div>
        </Panel>

        {/* zone 1 */}
        <Panel className={"wb-page-panel batch-base-form" + (focus === "unready" ? " batch-focus-target" : "")} title="① 批次基础信息">
          <div className="bd-form-grid">
            <Field label="批次号"><input className="bd-input" value={batch.batch_id} disabled /></Field>
            <Field label="图号"><input className="bd-input" value={batch.part_no + " · " + partName(batch.part_no)} disabled /></Field>
            <Field label="数量" required error={errors.quantity}><input className="bd-input num" type="number" min="1" step="1" value={base.quantity} onChange={(e) => setBase({ ...base, quantity: e.target.value })} /></Field>
            <Field label="交期" error={errors.due_date}><DateInput value={base.due_date} onChange={(v) => setBase({ ...base, due_date: v })} /></Field>
            <Field label="优先级">
              <select className="bd-select" value={base.priority} onChange={(e) => setBase({ ...base, priority: e.target.value })}>
                {Object.keys(PRIORITY).map((k) => <option key={k} value={k}>{PRIORITY[k].label}</option>)}
              </select>
            </Field>
            <Field label="齐套显示">
              <select className="bd-select" value={base.ready_status} onChange={(e) => setBase({ ...base, ready_status: e.target.value })}>
                {Object.keys(READY).map((k) => <option key={k} value={k}>{READY[k].label}</option>)}
              </select>
            </Field>
            <Field label="齐套日期" error={errors.ready_date}><DateInput value={base.ready_date} onChange={(v) => setBase({ ...base, ready_date: v })} /></Field>
            <Field label="备注" wide><input className="bd-input" placeholder="可选" value={base.remark} onChange={(e) => setBase({ ...base, remark: e.target.value })} /></Field>
          </div>
          <div className="bd-form-footer">{dirty ? <span className="batch-draft-label">有未提交编辑</span> : null}<Button variant="primary" size="md" disabled={!dirty} onClick={saveBase}>保存</Button></div>
        </Panel>

        {/* zone 2 */}
        <Panel className="wb-page-panel batch-sync-form" title="② 按工艺模板同步工序" description="工艺路线或模板调整后，可同步到本批次；同步会重建工序清单。">
          <div className="bd-form-grid">
            <label className="batch-strict"><input type="checkbox" checked={strict} onChange={(e) => setStrict(e.target.checked)} />资料不完整时停止刷新</label>
          </div>
          <div className="bd-flash tone-warning" style={{ marginTop: 4 }}>
            <span className="bd-flash-dot" /><span>刷新将覆盖本批次工序、资源补充、完工标记及未提交工序草稿；缺失字段保留待补，不填入默认工时或周期。</span>
          </div>
          <div className="bd-form-footer"><ConfirmButton variant="secondary" size="md" label="按最新工艺模板刷新本批次工序" title={"重建 " + batch.batch_id + " 的工序？"} body={"将用图号 " + batch.part_no + " 的当前模板覆盖现有 " + ops.length + " 道工序，并清除未提交工序草稿。"} confirmLabel="确认刷新工序" onConfirm={regenerate} /></div>
        </Panel>

        {/* zone 3 */}
        <Panel className="wb-page-panel" title="③ 工序概况">
          <SummaryGrid items={[
            { label: "工序总数", value: ops.length },
            { label: "自制工序", value: internal },
            { label: "外协工序", value: external },
            { label: "已完工", value: doneCount(ops), sev: "ok" },
            { label: "待补资源", value: gaps, sev: gaps ? "warning" : "ok" },
          ]} />
          {gaps ? <p className="bd-cell-note" style={{ marginTop: 12, color: "var(--ui-warning-text)" }}>仍有 {gaps} 道工序缺资源、工时或有效外协周期。</p> : null}
        </Panel>

        {/* zone 4 */}
        <Panel className={"wb-page-panel" + (focus === "gaps" ? " batch-focus-target" : "")} title="④ 批次工序">
          {ops.length ? (
            <div className="bd-table-scroll bd-op-table wb-table-frame"><Table columns={opCols} rows={ops.map((o) => ({ ...o, id: o.seq }))} rowKey="seq" /></div>
          ) : <Empty title="该批次尚未生成工序" desc="点击上方「按最新工艺模板刷新本批次工序」按零件路线生成。" />}
        </Panel>
      </div>
    );
  }

  /* ---------------- per-op inline editor ---------------- */
  function OpConfigCell({ op, batch, onUpdate, flashFn }) {
    const { ControlButton: Button } = window.APSWorkbenchUI;
    const { Field } = B();
    const ext = op.source === "external";
    const [v, setV] = useSessionState("op:" + batch.batch_id + ":" + op.seq, ext
      ? { supplier: op.supplier || "", ext_days: op.ext_days == null ? "" : String(op.ext_days) }
      : { machine: op.machine || "", operator: op.operator || "", setup: op.setup == null ? "" : String(op.setup), unit: op.unit == null ? "" : String(op.unit) });
    const [errors, setErrors] = useState({});
    const merged = ext && op.mode === "merged";

    const dirty = ext
      ? (v.supplier !== (op.supplier || "") || v.ext_days !== (op.ext_days == null ? "" : String(op.ext_days)))
      : (v.machine !== (op.machine || "") || v.operator !== (op.operator || "") || v.setup !== String(op.setup) || v.unit !== String(op.unit));

    const allowed = !ext && v.machine ? MACHINE_OPERATORS[v.machine] || [] : null;
    const mismatch = allowed && v.operator && !allowed.includes(v.operator);

    const save = () => {
      const errs = Draft.opErrors({ ...op, ...v });
      setErrors(errs);
      if (Object.keys(errs).length) return;
      onUpdate(batch.batch_id, { ops: batch.ops.map((o) => o.seq !== op.seq ? o : (ext
        ? { ...o, supplier: v.supplier, ext_days: v.ext_days === "" ? null : Number(v.ext_days) }
        : { ...o, machine: v.machine, operator: v.operator, setup: Number(v.setup), unit: Number(v.unit) })) });
      Draft.clearDraft("op:" + batch.batch_id + ":" + op.seq);
      flashFn("ok", "已保存工序 " + op.seq + " 的补充信息。");
    };

    if (ext) {
      return (
        <div className="bd-op-config" data-batch-op={op.seq} data-gap={Object.keys(Draft.opErrors(op)).length > 0 || undefined}>
          <div className="bd-op-config-row">
            <Field label="供应商" error={errors.supplier}>
              <select className={"bd-select" + (dirty ? " bd-cell-dirty" : "")} value={v.supplier} onChange={(e) => setV({ ...v, supplier: e.target.value })}>
                <option value="">（未选择）</option>
                {SUPPLIERS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </Field>
            <Field label="外协周期（天）" error={errors.ext_days}>
              <input className={"bd-cell-input num" + (dirty ? " bd-cell-dirty" : "")} placeholder={merged ? "按本工序" : "如：3"} value={v.ext_days} onChange={(e) => setV({ ...v, ext_days: e.target.value })} />
            </Field>
            <div className="bd-op-config-act"><Button variant={dirty ? "primary" : "secondary"} size="sm" disabled={!dirty} onClick={save}>保存</Button></div>
          </div>
          {merged ? <span className="bd-cell-note">属合并外协组 {op.group}；可单独填本工序周期，留空则跟随整组合计约 {op.total ?? "未设置"} 天。</span> : null}
        </div>
      );
    }
    return (
      <div className="bd-op-config" data-batch-op={op.seq} data-gap={Object.keys(Draft.opErrors(op)).length > 0 || undefined}>
        <div className="bd-op-config-row">
          <Field label="设备" error={errors.machine}>
            <select className={"bd-select" + (dirty ? " bd-cell-dirty" : "")} value={v.machine} onChange={(e) => setV({ ...v, machine: e.target.value })}>
              <option value="">（未选择）</option>
              {MACHINES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </Field>
          <Field label="人员" error={errors.operator}>
            <select className={"bd-select" + (dirty ? " bd-cell-dirty" : "") + (mismatch ? " " : "")} style={{ borderColor: mismatch ? "var(--ui-danger)" : undefined }} value={v.operator} onChange={(e) => setV({ ...v, operator: e.target.value })}>
              <option value="">（未选择）</option>
              {OPERATORS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </Field>
          <Field label="换型（小时）" error={errors.setup}><input className={"bd-cell-input num" + (dirty ? " bd-cell-dirty" : "")} value={v.setup} onChange={(e) => setV({ ...v, setup: e.target.value })} /></Field>
          <Field label="单件（小时）" error={errors.unit}><input className={"bd-cell-input num" + (dirty ? " bd-cell-dirty" : "")} value={v.unit} onChange={(e) => setV({ ...v, unit: e.target.value })} /></Field>
          <div className="bd-op-config-act"><Button variant={dirty ? "primary" : "secondary"} size="sm" disabled={!dirty} onClick={save}>保存</Button></div>
        </div>
        {mismatch
          ? <span className="bd-cell-error">所选人员不能操作 {v.machine}；可选：{(allowed || []).map((id) => labelOf(OPERATORS, id)).join("、") || "无"}。</span>
          : (allowed && allowed.length ? <span className="bd-cell-note">{v.machine} 可用人员：{allowed.map((id) => labelOf(OPERATORS, id)).join("、")}。</span> : null)}
      </div>
    );
  }

  window.BatchesScreen = BatchesScreen;
  window.BaseBatches = BatchesScreen;
})();
