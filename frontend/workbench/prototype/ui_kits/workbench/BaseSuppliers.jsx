// APS Workbench · 基础资料 › 外协 › 供应商配置模块（可复用）
// 列表 + 内联新增 + 主从详情编辑 + Excel 批量维护 + 引用保护删除
// 外协链口径 = 周期（天）：供应商绑外协工种，给默认周期。
(function () {
  const { useState } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;

  const SEED = [
    { supplier_id: "S001", name: "华表面处理厂", op_type: "电镀", default_days: 3, status: "active", remark: "主力外协", refs: ["工序"] },
    { supplier_id: "S002", name: "金鼎热处理", op_type: "热处理", default_days: 4, status: "active", remark: "", refs: ["工序"] },
    { supplier_id: "S003", name: "恒发发黑", op_type: "发黑", default_days: 2, status: "active", remark: "", refs: [] },
    { supplier_id: "S004", name: "蓝盾喷涂", op_type: "喷涂", default_days: 5, status: "disabled", remark: "停用整顿", refs: [] },
  ];
  const STATUS_OPTS = [{ value: "active", label: "启用" }, { value: "disabled", label: "停用" }];
  const statusZh = (s) => (s === "disabled" ? "停用" : "启用");

  function SuppliersModule({ flashFn }) {
    const [rows, setRows] = useState(SEED);
    const [view, setView] = useState("list");
    const [openId, setOpenId] = useState(null);
    const [wiz, setWiz] = useState(null);

    const open = (id) => { setOpenId(id); setView("detail"); window.scrollTo({ top: 0 }); };
    const back = () => { setView("list"); setOpenId(null); window.scrollTo({ top: 0 }); };
    const patch = (id, p) => setRows((arr) => arr.map((r) => (r.supplier_id === id ? { ...r, ...p } : r)));

    if (wiz) {
      const W = B().ExcelWizard;
      return <W wiz={wiz} onClose={() => setWiz(null)} onDone={(s) => flashFn("ok", "Excel 导入完成：" + s + "。")} />;
    }
    if (view === "detail") {
      const row = rows.find((r) => r.supplier_id === openId);
      return <SupplierDetail row={row} onBack={back} onSave={patch} flashFn={flashFn} />;
    }
    return <SuppliersList rows={rows} setRows={setRows} onOpen={open} onWiz={setWiz} flashFn={flashFn} />;
  }

  /* ============================================================ LIST */
  function SuppliersList({ rows, setRows, onOpen, onWiz, flashFn }) {
    const { Panel, Button, Badge, Table } = DS();
    const { Field, ActionCards, ConfirmButton, Pager, Empty, opTypeNames } = B();
    const extTypes = opTypeNames("external");
    const [q, setQ] = useState("");
    const [page, setPage] = useState(1);
    const perPage = 8;
    const [form, setForm] = useState({ supplier_id: "", name: "", op_type: "", default_days: "1", status: "active", remark: "" });
    const [errors, setErrors] = useState({});
    const setField = (patch) => { setForm((f) => ({ ...f, ...patch })); setErrors((e) => { const n = { ...e }; Object.keys(patch).forEach((k) => delete n[k]); return n; }); };

    const cards = [
      { title: "批量维护供应商", desc: "下载模板、上传检查、确认写入或导出供应商配置；手工新增继续用下方表单。",
        maintainLabel: "批量维护供应商", exportLabel: "导出当前供应商", cycle: true,
        wizard: { kind: "suppliers", title: "批量维护供应商配置", desc: "维护供应商编号、名称、对应工种、默认周期（天）与状态；默认周期必须大于 0。",
          sampleRows: [
            { row_num: 2, status: "update", message: "更新默认周期 3→4 天", data: { 供应商编号: "S001", 默认周期: 4 } },
            { row_num: 3, status: "new", message: "新增供应商", data: { 供应商编号: "S005", 名称: "鑫达阳极", 对应工种: "电镀" } },
            { row_num: 4, status: "error", message: "默认周期必须大于 0", data: { 供应商编号: "S006", 默认周期: 0 } },
          ] } },
    ];

    const list = rows.filter((r) => !q || (r.supplier_id + r.name + (r.op_type || "") + (r.remark || "")).toLowerCase().includes(q.toLowerCase()));
    const totalPages = Math.ceil(list.length / perPage);
    const pageRows = list.slice((page - 1) * perPage, page * perPage);

    const tryDelete = (r) => {
      if (r.refs && r.refs.length) { flashFn("danger", "无法删除供应商 " + r.name + "：仍被" + r.refs.join("、") + "引用，请先解除引用。"); return; }
      setRows((arr) => arr.filter((x) => x.supplier_id !== r.supplier_id));
      flashFn("ok", "已删除供应商 " + r.name + "。");
    };

    const cols = [
      { key: "supplier_id", title: "供应商编号", width: 130, render: (r) => <a className="bd-link" onClick={() => onOpen(r.supplier_id)}>{r.supplier_id}</a> },
      { key: "name", title: "名称", width: 170 },
      { key: "op_type", title: "对应工种", width: 120, render: (r) => r.op_type ? <Badge tone="warning">{r.op_type}</Badge> : <span className="muted">不绑定</span> },
      { key: "default_days", title: "默认周期", width: 110, align: "right", render: (r) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{r.default_days} 天</span> },
      { key: "status", title: "状态", width: 100, render: (r) => <Badge tone={r.status === "active" ? "ok" : "secondary"} dot>{statusZh(r.status)}</Badge> },
      { key: "remark", title: "备注", render: (r) => r.remark || <span className="muted">-</span> },
      { key: "act", title: "操作", width: 170, render: (r) => (
        <div className="bd-cell-actions">
          <Button variant="secondary" size="sm" onClick={() => onOpen(r.supplier_id)}>查看/编辑</Button>
          <ConfirmButton label="删除" title={"删除供应商 " + r.name + "？"}
            body={r.refs && r.refs.length
              ? <>该供应商已被 <strong>{r.refs.join("、")}</strong> 引用，删除会被拒绝。仍要尝试吗？</>
              : <>确认删除供应商 <strong>{r.name}</strong>（{r.supplier_id}）吗？</>}
            onConfirm={() => tryDelete(r)} />
        </div>
      ) },
    ];

    const submit = () => {
      const errs = {};
      if (!form.supplier_id) errs.supplier_id = "请填写供应商编号。";
      else if (rows.some((r) => r.supplier_id === form.supplier_id)) errs.supplier_id = "供应商编号 " + form.supplier_id + " 已存在。";
      if (!form.name) errs.name = "请填写名称。";
      if (Number(form.default_days) <= 0) errs.default_days = "默认周期必须大于 0。";
      if (Object.keys(errs).length) { setErrors(errs); return; }
      setErrors({});
      setRows((arr) => [{ ...form, default_days: Number(form.default_days), refs: [] }, ...arr]);
      flashFn("ok", "已添加供应商 " + form.name + "。");
      setForm({ supplier_id: "", name: "", op_type: "", default_days: "1", status: "active", remark: "" });
    };

    return (
      <div className="bd-card-gap">
        <ActionCards title="批量维护" subtitle="适合 Excel 下发或整批复核；手工新增继续使用下方表单。" cards={cards} onOpen={onWiz} />

        <Panel title="新增供应商">
          <div className="field-help bd-chain-note tone-external"><span className="cn-bar" /><span>默认周期必须填大于 0 的天数。若一个外协工种有多个启用供应商，请停用多余的，或确认编号排序后系统会选到你想要的那一个。</span></div>
          <div className="bd-form-grid">
            <Field label="供应商编号" required error={errors.supplier_id}><input className="bd-input" placeholder="如：S001" value={form.supplier_id} onChange={(e) => setField({ supplier_id: e.target.value })} /></Field>
            <Field label="名称" required error={errors.name}><input className="bd-input" placeholder="如：外协-表处理厂" value={form.name} onChange={(e) => setField({ name: e.target.value })} /></Field>
            <Field label="对应工种" hint="从外协工种里选；可不绑定。">
              <select className="bd-select" value={form.op_type} onChange={(e) => setForm({ ...form, op_type: e.target.value })}>
                <option value="">（不绑定）</option>
                {extTypes.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </Field>
            <Field label="默认周期（天）" required error={errors.default_days}><input className="bd-input num" style={{ maxWidth: 120 }} value={form.default_days} onChange={(e) => setField({ default_days: e.target.value })} /></Field>
            <Field label="状态" required>
              <select className="bd-select" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                {STATUS_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Field>
            <Field label="备注" wide><input className="bd-input" placeholder="可选" value={form.remark} onChange={(e) => setForm({ ...form, remark: e.target.value })} /></Field>
          </div>
          <div className={"bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")}>
            {Object.keys(errors).length ? <span className="bd-form-error">请修正标红的必填项</span> : null}
            <Button variant="primary" size="md" onClick={submit}>添加供应商</Button>
          </div>
        </Panel>

        <Panel title="供应商列表" description="外协计量口径是「周期（天）」：供应商给默认周期，零件的连续外协工序组在「工艺」详情里按此设/调周期。">
          <div className="bd-search">
            <Field label="搜索"><input className="bd-input" placeholder="输入供应商编号、名称、工种…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></Field>
          </div>
          {list.length ? (
            <>
              <Pager page={page} totalPages={totalPages} total={list.length} onPrev={() => setPage((p) => p - 1)} onNext={() => setPage((p) => p + 1)} />
              <div className="bd-table-scroll"><Table columns={cols} rows={pageRows} rowKey="supplier_id" /></div>
            </>
          ) : <Empty title="暂无供应商数据" desc="可在上方手动新增，或用 Excel 批量维护导入。" />}
        </Panel>
      </div>
    );
  }

  /* ============================================================ DETAIL */
  function SupplierDetail({ row, onBack, onSave, flashFn }) {
    const { Panel, Button, Badge } = DS();
    const { Field, opTypeNames } = B();
    const extTypes = opTypeNames("external");
    const [v, setV] = useState({ name: row.name, op_type: row.op_type || "", default_days: String(row.default_days), status: row.status, remark: row.remark || "" });
    const [errors, setErrors] = useState({});
    const setField = (patch) => { setV((s) => ({ ...s, ...patch })); setErrors((e) => { const n = { ...e }; Object.keys(patch).forEach((k) => delete n[k]); return n; }); };

    const save = () => {
      const errs = {};
      if (!v.name) errs.name = "请填写名称。";
      if (Number(v.default_days) <= 0) errs.default_days = "默认周期必须大于 0。";
      if (Object.keys(errs).length) { setErrors(errs); return; }
      setErrors({});
      onSave(row.supplier_id, { ...v, default_days: Number(v.default_days) });
      flashFn("ok", "已保存供应商 " + v.name + "。"); onBack();
    };

    return (
      <div className="bd-card-gap">
        <Panel title="供应商配置 · 详情" description="维护供应商名称、对应工种、默认周期与状态。供应商编号创建后不可更改。"
          headerRight={<Button variant="ghost" size="sm" onClick={onBack}>← 返回列表</Button>}>
          <div className="bd-meta-row">
            <span><span className="bd-meta-label">供应商编号：</span><strong>{row.supplier_id}</strong></span>
            <span><span className="bd-meta-label">状态：</span><Badge tone={v.status === "active" ? "ok" : "secondary"} dot>{statusZh(v.status)}</Badge></span>
            <span><span className="bd-meta-label">引用：</span>{row.refs && row.refs.length ? <Badge tone="secondary">{row.refs.join(" / ")}</Badge> : <span className="muted">无</span>}</span>
          </div>
        </Panel>

        <Panel title="编辑供应商">
          <div className="bd-form-grid">
            <Field label="供应商编号"><input className="bd-input" value={row.supplier_id} disabled /></Field>
            <Field label="名称" required error={errors.name}><input className="bd-input" value={v.name} onChange={(e) => setField({ name: e.target.value })} /></Field>
            <Field label="对应工种" hint="从外协工种里选；可不绑定。">
              <select className="bd-select" value={v.op_type} onChange={(e) => setV({ ...v, op_type: e.target.value })}>
                <option value="">（不绑定）</option>
                {extTypes.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </Field>
            <Field label="默认周期（天）" required error={errors.default_days}><input className="bd-input num" style={{ maxWidth: 120 }} value={v.default_days} onChange={(e) => setField({ default_days: e.target.value })} /></Field>
            <Field label="状态" required>
              <select className="bd-select" value={v.status} onChange={(e) => setV({ ...v, status: e.target.value })}>
                {STATUS_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Field>
            <Field label="备注" wide><input className="bd-input" placeholder="可选" value={v.remark} onChange={(e) => setV({ ...v, remark: e.target.value })} /></Field>
          </div>
          <div className={"bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")}>
            {Object.keys(errors).length ? <span className="bd-form-error">请修正标红的必填项</span> : null}
            <Button variant="secondary" size="md" onClick={onBack}>取消</Button>
            <Button variant="primary" size="md" onClick={save}>保存</Button>
          </div>
        </Panel>
      </div>
    );
  }

  window.SuppliersModule = SuppliersModule;
})();
