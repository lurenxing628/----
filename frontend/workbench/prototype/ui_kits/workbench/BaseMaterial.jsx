// APS Workbench · 基础资料 › 物料 tab — 二级 tab：物料主数据（整表行内编辑）/ 批次物料需求（齐套判定）
(function () {
  const { useState } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;

  const SEED_MATERIALS = [
    { material_id: "MAT001", name: "45# 圆钢", spec: "Φ30", unit: "kg", stock: 1200, status: "active", remark: "" },
    { material_id: "MAT002", name: "铸铝件", spec: "ZL104", unit: "件", stock: 80, status: "active", remark: "外购" },
    { material_id: "MAT003", name: "密封圈", spec: "Φ25×3", unit: "件", stock: 0, status: "active", remark: "缺料" },
    { material_id: "MAT004", name: "不锈钢板", spec: "δ5", unit: "kg", stock: 540, status: "disabled", remark: "停用中" },
  ];
  const STATUS_OPTS = [{ value: "active", label: "可用" }, { value: "disabled", label: "停用" }];

  const SEED_BATCHES = [
    { id: "B202605-018", part: "T-1008", qty: 12, ready: "partial", ready_date: "—",
      reqs: [
        { id: 1, material_id: "MAT001", name: "45# 圆钢", spec: "Φ30", unit: "kg", required: 120, received: 120 },
        { id: 2, material_id: "MAT002", name: "铸铝件", spec: "ZL104", unit: "件", required: 12, received: 6 },
        { id: 3, material_id: "MAT003", name: "密封圈", spec: "Φ25×3", unit: "件", required: 24, received: 0 },
      ] },
    { id: "B202605-021", part: "T-1009", qty: 8, ready: "yes", ready_date: "06-09",
      reqs: [{ id: 1, material_id: "MAT001", name: "45# 圆钢", spec: "Φ30", unit: "kg", required: 80, received: 80 }] },
    { id: "B202605-019", part: "T-1006", qty: 6, ready: "no", ready_date: "—", reqs: [] },
  ];

  function readyState(required, received) {
    const req = Number(required) || 0, rec = Number(received);
    if (req <= 0) return { key: "yes", label: "齐套", tone: "ok" };
    if (rec >= req) return { key: "yes", label: "齐套", tone: "ok" };
    if (rec > 0) return { key: "partial", label: "部分齐套", tone: "notice" };
    return { key: "no", label: "未齐套", tone: "danger" };
  }

  function MaterialTab({ sub, onSub, flashFn }) {
    const { SubTabs } = B();
    const tabs = [{ id: "materials", label: "物料主数据" }, { id: "batch", label: "批次物料需求" }];
    return (
      <div>
        <SubTabs tabs={tabs} value={sub} onChange={onSub} />
        {sub === "batch" ? <BatchMaterials flashFn={flashFn} /> : <MaterialMaster flashFn={flashFn} />}
      </div>
    );
  }

  /* ============================================================ 2A 物料主数据 */
  function MaterialMaster({ flashFn }) {
    const { Panel, Button, Badge, Table } = DS();
    const { Field, ConfirmButton, Pager, Empty } = B();
    const [rows, setRows] = useState(SEED_MATERIALS);
    const [edits, setEdits] = useState({});
    const [form, setForm] = useState({ material_id: "", name: "", spec: "", unit: "", stock: "0", status: "active", remark: "" });
    const [errors, setErrors] = useState({});
    const setField = (patch) => { setForm((f) => ({ ...f, ...patch })); setErrors((e) => { const n = { ...e }; Object.keys(patch).forEach((k) => delete n[k]); return n; }); };
    const [page, setPage] = useState(1);
    const perPage = 8;

    const getVal = (r, k) => (edits[r.material_id] && k in edits[r.material_id] ? edits[r.material_id][k] : r[k]);
    const isDirty = (r) => edits[r.material_id] && Object.keys(edits[r.material_id]).some((k) => String(edits[r.material_id][k]) !== String(r[k]));
    const setCell = (id, k, v) => setEdits((e) => ({ ...e, [id]: { ...(e[id] || {}), [k]: v } }));

    const saveRow = (r) => {
      const patch = edits[r.material_id] || {};
      if (Number(patch.stock ?? r.stock) < 0) { return; } // 负库存已在单元格就近标红提示
      setRows((arr) => arr.map((x) => (x.material_id === r.material_id ? { ...x, ...patch } : x)));
      setEdits((e) => { const n = { ...e }; delete n[r.material_id]; return n; });
      flashFn("ok", "已保存物料 " + r.material_id + "。");
    };

    const cols = [
      { key: "material_id", title: "物料编号", width: 120, render: (r) => <code className="bd-code">{r.material_id}</code> },
      { key: "name", title: "名称", width: 160, render: (r) => <input className="bd-cell-input" value={getVal(r, "name")} onChange={(e) => setCell(r.material_id, "name", e.target.value)} /> },
      { key: "spec", title: "规格", width: 120, render: (r) => <input className="bd-cell-input" value={getVal(r, "spec")} onChange={(e) => setCell(r.material_id, "spec", e.target.value)} /> },
      { key: "unit", title: "单位", width: 90, render: (r) => <input className="bd-cell-input" value={getVal(r, "unit")} onChange={(e) => setCell(r.material_id, "unit", e.target.value)} /> },
      { key: "stock", title: "库存", width: 110, align: "right", render: (r) => { const neg = Number(getVal(r, "stock")) < 0; return (<><input className={"bd-cell-input num" + (neg ? " is-error" : "")} type="number" min="0" step="0.01" value={getVal(r, "stock")} onChange={(e) => setCell(r.material_id, "stock", e.target.value)} />{neg ? <span className="bd-cell-error">库存不能为负数</span> : null}</>); } },
      { key: "status", title: "状态", width: 120, render: (r) => (
        <select className="bd-cell-input" value={getVal(r, "status")} onChange={(e) => setCell(r.material_id, "status", e.target.value)}>
          {STATUS_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select> ) },
      { key: "remark", title: "备注", render: (r) => <input className="bd-cell-input" placeholder="可选" value={getVal(r, "remark")} onChange={(e) => setCell(r.material_id, "remark", e.target.value)} /> },
      { key: "act", title: "操作", width: 150, render: (r) => (
        <div className="bd-cell-actions">
          <Button variant={isDirty(r) ? "primary" : "secondary"} size="sm" disabled={!isDirty(r)} onClick={() => saveRow(r)}>保存</Button>
          <ConfirmButton label="删除" title={"删除物料 " + r.material_id + "？"} body="若该物料已被批次物料需求引用，删除将失败。确认删除吗？"
            onConfirm={() => { setRows((arr) => arr.filter((x) => x.material_id !== r.material_id)); flashFn("ok", "已删除物料 " + r.material_id + "。"); }} />
        </div>
      ) },
    ];

    const submit = () => {
      const errs = {};
      if (!form.material_id) errs.material_id = "请填写物料编号。";
      else if (rows.some((r) => r.material_id === form.material_id)) errs.material_id = "物料编号 " + form.material_id + " 已存在。";
      if (!form.name) errs.name = "请填写名称。";
      if (Object.keys(errs).length) { setErrors(errs); return; }
      setErrors({});
      setRows((arr) => [{ ...form, stock: Number(form.stock) || 0 }, ...arr]);
      flashFn("ok", "已创建物料 " + form.material_id + "。");
      setForm({ material_id: "", name: "", spec: "", unit: "", stock: "0", status: "active", remark: "" });
    };

    const totalPages = Math.ceil(rows.length / perPage);
    const pageRows = rows.slice((page - 1) * perPage, page * perPage);

    return (
      <div className="bd-card-gap">
        <Panel title="物料主数据" description="维护物料编号、名称、规格、库存和状态。列表整表行内编辑，改完点对应行的「保存」。">
          <div className="bd-form-grid">
            <Field label="物料编号" required error={errors.material_id}><input className="bd-input" placeholder="如：MAT001" value={form.material_id} onChange={(e) => setField({ material_id: e.target.value })} /></Field>
            <Field label="名称" required error={errors.name}><input className="bd-input" placeholder="如：圆钢" value={form.name} onChange={(e) => setField({ name: e.target.value })} /></Field>
            <Field label="规格"><input className="bd-input" placeholder="如：Φ30" value={form.spec} onChange={(e) => setForm({ ...form, spec: e.target.value })} /></Field>
            <Field label="单位"><input className="bd-input" placeholder="如：kg / 件" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} /></Field>
            <Field label="库存" hint="默认 0，不能为负。"><input className="bd-input num" type="number" min="0" step="0.01" value={form.stock} onChange={(e) => setForm({ ...form, stock: e.target.value })} /></Field>
            <Field label="状态" required>
              <select className="bd-select" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                {STATUS_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Field>
            <Field label="备注" wide><input className="bd-input" placeholder="可选备注" value={form.remark} onChange={(e) => setForm({ ...form, remark: e.target.value })} /></Field>
          </div>
          <div className={"bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")}>
            {Object.keys(errors).length ? <span className="bd-form-error">请填写标红的必填项</span> : null}
            <Button variant="primary" size="md" onClick={submit}>创建</Button>
          </div>
        </Panel>

        <Panel title="物料列表">
          <Pager page={page} totalPages={totalPages} total={rows.length} onPrev={() => setPage((p) => p - 1)} onNext={() => setPage((p) => p + 1)} />
          {rows.length ? <div className="bd-table-scroll"><Table columns={cols} rows={pageRows} rowKey="material_id" /></div>
            : <Empty title="暂无物料数据" desc="可在上方手动新增。" />}
        </Panel>
      </div>
    );
  }

  /* ============================================================ 2B 批次物料需求 */
  function BatchMaterials({ flashFn }) {
    const { Panel, Button, Badge, Table } = DS();
    const { Field, SummaryGrid, InfoStrip, ConfirmButton, Empty } = B();
    const [batches, setBatches] = useState(SEED_BATCHES);
    const [picked, setPicked] = useState("");
    const [opened, setOpened] = useState(null);
    const [add, setAdd] = useState({ material_id: "", required: "", received: "" });
    const [addErr, setAddErr] = useState({});
    const setAddField = (patch) => { setAdd((a) => ({ ...a, ...patch })); setAddErr((e) => { const n = { ...e }; Object.keys(patch).forEach((k) => delete n[k]); return n; }); };

    const overview = batches.reduce((a, b) => { a[b.ready] = (a[b.ready] || 0) + 1; return a; }, {});
    const batch = batches.find((b) => b.id === opened);

    const setReq = (bid, rid, patch) =>
      setBatches((arr) => arr.map((b) => b.id === bid ? { ...b, reqs: b.reqs.map((r) => r.id === rid ? { ...r, ...patch } : r) } : b));

    const reqCols = [
      { key: "id", title: "编号", width: 64, align: "right", render: (r) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{r.id}</span> },
      { key: "material_id", title: "物料编号", width: 120, render: (r) => <code className="bd-code">{r.material_id}</code> },
      { key: "name", title: "名称", width: 130 },
      { key: "spec", title: "规格", width: 100, render: (r) => r.spec || "-" },
      { key: "unit", title: "单位", width: 80, render: (r) => r.unit || "-" },
      { key: "required", title: "需求数量", width: 120, align: "right", render: (r) => <input className="bd-cell-input num" type="number" min="0.000001" step="0.01" value={r.required} onChange={(e) => setReq(batch.id, r.id, { required: e.target.value })} /> },
      { key: "received", title: "到料数量", width: 120, align: "right", render: (r) => <input className="bd-cell-input num" type="number" min="0" step="0.01" value={r.received} onChange={(e) => setReq(batch.id, r.id, { received: e.target.value })} /> },
      { key: "ready", title: "齐套状态", width: 110, render: (r) => { const s = readyState(r.required, r.received); return <Badge tone={s.tone} dot>{s.label}</Badge>; } },
      { key: "act", title: "操作", width: 150, render: (r) => (
        <div className="bd-cell-actions">
          <Button variant="secondary" size="sm" onClick={() => flashFn("ok", "已保存需求 #" + r.id + "，齐套状态已重算。")}>保存</Button>
          <ConfirmButton label="删除" title="删除该物料需求？" body="删除后批次齐套状态会自动按剩余需求重算。确认删除吗？"
            onConfirm={() => { setBatches((arr) => arr.map((b) => b.id === batch.id ? { ...b, reqs: b.reqs.filter((x) => x.id !== r.id) } : b)); flashFn("ok", "已删除该物料需求。"); }} />
        </div>
      ) },
    ];

    const doAdd = () => {
      const errs = {};
      if (!add.material_id) errs.material_id = "请选择物料。";
      if (!add.required || Number(add.required) <= 0) errs.required = "需求数量必须大于 0。";
      if (Object.keys(errs).length) { setAddErr(errs); return; }
      setAddErr({});
      const mat = SEED_MATERIALS.find((m) => m.material_id === add.material_id) || {};
      const nid = (batch.reqs.reduce((m, r) => Math.max(m, r.id), 0) || 0) + 1;
      const received = add.received === "" ? Number(add.required) : Number(add.received);
      setBatches((arr) => arr.map((b) => b.id === batch.id ? { ...b, reqs: [...b.reqs, { id: nid, material_id: add.material_id, name: mat.name || "", spec: mat.spec || "", unit: mat.unit || "", required: Number(add.required), received }] } : b));
      flashFn("ok", "已新增物料需求。");
      setAdd({ material_id: "", required: "", received: "" });
    };

    return (
      <div className="bd-card-gap">
        <Panel title="选择批次" description="选一个批次查看并管理其物料需求；存在物料需求记录时，系统按到料情况自动更新齐套状态。">
          <div className="bd-search">
            <Field label="批次"><select className="bd-select" style={{ minWidth: 280 }} value={picked} onChange={(e) => setPicked(e.target.value)}>
              <option value="">（请选择批次）</option>
              {batches.map((b) => <option key={b.id} value={b.id}>{b.id}（{b.part}×{b.qty}）</option>)}
            </select></Field>
            <Button variant="primary" size="md" disabled={!picked} onClick={() => setOpened(picked)}>查看</Button>
          </div>
        </Panel>

        {!batch ? (
          <Panel title="齐套概览">
            <SummaryGrid items={[
              { label: "齐套", value: overview.yes || 0, sev: "ok" },
              { label: "部分齐套", value: overview.partial || 0, sev: "notice" },
              { label: "未齐套", value: overview.no || 0, sev: "danger" },
            ]} />
            <p className="bd-sec-sub" style={{ marginTop: 14 }}>请在上方选择一个批次，查看并管理其物料需求。某批次存在物料需求记录时，系统会按到料情况自动更新齐套显示。</p>
          </Panel>
        ) : (
          <>
            <Panel title="批次信息" headerRight={<Button variant="secondary" size="sm">打开批次详情</Button>}>
              <InfoStrip cells={[
                { k: "批次号", v: batch.id },
                { k: "图号", v: batch.part },
                { k: "数量", v: batch.qty },
                { k: "当前齐套状态", v: <Badge tone={readyStateOfBatch(batch).tone} dot>{readyStateOfBatch(batch).label}</Badge> },
                { k: "齐套日期", v: batch.ready_date || "暂无" },
              ]} />
            </Panel>

            <Panel title="新增物料需求">
              <div className="bd-form-grid">
                <Field label="物料" required error={addErr.material_id}>
                  <select className="bd-select" value={add.material_id} onChange={(e) => setAddField({ material_id: e.target.value })}>
                    <option value="">（请选择）</option>
                    {SEED_MATERIALS.map((m) => <option key={m.material_id} value={m.material_id}>{m.material_id} · {m.name}</option>)}
                  </select>
                </Field>
                <Field label="需求数量" required hint="必须大于 0。" error={addErr.required}><input className="bd-input num" type="number" min="0.000001" step="0.01" placeholder="如：10" value={add.required} onChange={(e) => setAddField({ required: e.target.value })} /></Field>
                <Field label="到料数量" hint="留空 = 已到齐；填不足数量才显示未齐套。"><input className="bd-input num" type="number" min="0" step="0.01" placeholder="留空=已到齐" value={add.received} onChange={(e) => setAdd({ ...add, received: e.target.value })} /></Field>
              </div>
              <div className={"bd-form-footer" + (Object.keys(addErr).length ? " has-error" : "")}>
                {Object.keys(addErr).length ? <span className="bd-form-error">请修正标红的必填项</span> : null}
                <Button variant="primary" size="md" onClick={doAdd}>新增</Button>
              </div>
            </Panel>

            <Panel title="物料需求列表" description="改动需求数量或到料数量后，齐套状态会自动重算。">
              {batch.reqs.length ? <div className="bd-table-scroll"><Table columns={reqCols} rows={batch.reqs} rowKey="id" /></div>
                : <Empty title="该批次还没有物料需求" desc="没有物料明细时默认按齐套显示。新增后系统会按到料数量更新齐套显示。" />}
            </Panel>
          </>
        )}
      </div>
    );
  }

  function readyStateOfBatch(batch) {
    if (!batch.reqs.length) return { label: "齐套", tone: "ok" };
    const states = batch.reqs.map((r) => readyState(r.required, r.received).key);
    if (states.every((s) => s === "yes")) return { label: "齐套", tone: "ok" };
    if (states.some((s) => s === "yes" || s === "partial")) return { label: "部分齐套", tone: "notice" };
    return { label: "未齐套", tone: "danger" };
  }

  window.MaterialTab = MaterialTab;
})();
