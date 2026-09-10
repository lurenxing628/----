// APS Workbench · 基础资料 › 工种配置模块（可复用）
// scope: "internal" 自制工种 | "external" 外协工种 | "all" 全部工种(带归属列+筛选)
// 列表 + 内联新增 + 主从详情编辑 + Excel 批量维护 + 引用保护删除
(function () {
  const { useState } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;

  // 每个 scope 独立维护一份种子（含引用锁定演示）
  const SEED = [
    { op_type_id: "OT001", name: "数铣", category: "internal", remark: "", refs: ["工序", "设备"] },
    { op_type_id: "OT002", name: "数车", category: "internal", remark: "", refs: ["工序", "设备"] },
    { op_type_id: "OT003", name: "钳工", category: "internal", remark: "", refs: ["工序", "人员"] },
    { op_type_id: "OT004", name: "精磨", category: "internal", remark: "", refs: [] },
    { op_type_id: "OT005", name: "钻孔", category: "internal", remark: "", refs: [] },
    { op_type_id: "OT006", name: "总检", category: "internal", remark: "关键工序", refs: ["工序", "人员"] },
    { op_type_id: "OT007", name: "标印", category: "internal", remark: "", refs: [] },
    { op_type_id: "OT008", name: "表处理", category: "internal", remark: "", refs: ["工序"] },
    { op_type_id: "OT051", name: "电镀", category: "external", remark: "", refs: ["工序", "供应商"] },
    { op_type_id: "OT052", name: "发黑", category: "external", remark: "", refs: ["供应商"] },
    { op_type_id: "OT053", name: "热处理", category: "external", remark: "", refs: ["工序", "供应商"] },
    { op_type_id: "OT054", name: "喷涂", category: "external", remark: "", refs: [] },
  ];

  const catZh = (c) => (c === "external" ? "外协" : "自制");
  const catTone = (c) => (c === "external" ? "warning" : "notice");

  function OpTypesModule({ scope = "internal", flashFn }) {
    const init = scope === "all" ? SEED : SEED.filter((o) => o.category === scope);
    const [rows, setRows] = useState(init);
    const [view, setView] = useState("list");
    const [openId, setOpenId] = useState(null);
    const [wiz, setWiz] = useState(null);

    const open = (id) => { setOpenId(id); setView("detail"); window.scrollTo({ top: 0 }); };
    const back = () => { setView("list"); setOpenId(null); window.scrollTo({ top: 0 }); };
    const patch = (id, p) => setRows((arr) => arr.map((r) => (r.op_type_id === id ? { ...r, ...p } : r)));

    if (wiz) {
      const W = B().ExcelWizard;
      return <W wiz={wiz} onClose={() => setWiz(null)} onDone={(s) => flashFn("ok", "Excel 导入完成：" + s + "。")} />;
    }
    if (view === "detail") {
      const row = rows.find((r) => r.op_type_id === openId);
      return <OpTypeDetail row={row} scope={scope} onBack={back} onSave={patch} flashFn={flashFn} />;
    }
    return <OpTypesList rows={rows} setRows={setRows} scope={scope} onOpen={open} onWiz={setWiz} flashFn={flashFn} />;
  }

  /* ============================================================ LIST */
  function OpTypesList({ rows, setRows, scope, onOpen, onWiz, flashFn }) {
    const { Panel, Button, Badge, Table } = DS();
    const { Field, ActionCards, ConfirmButton, Pager, Empty } = B();
    const [q, setQ] = useState("");
    const [filter, setFilter] = useState("all");
    const [page, setPage] = useState(1);
    const perPage = 8;
    const defCat = scope === "external" ? "external" : "internal";
    const [form, setForm] = useState({ op_type_id: "", name: "", category: defCat, remark: "" });
    const [errors, setErrors] = useState({});
    const setField = (patch) => { setForm((f) => ({ ...f, ...patch })); setErrors((e) => { const n = { ...e }; Object.keys(patch).forEach((k) => delete n[k]); return n; }); };

    const cards = [
      { title: "批量维护工种", desc: "下载模板、上传检查、确认写入或导出" + (scope === "all" ? "全部" : catZh(scope)) + "工种配置；手工新增继续用下方表单。",
        maintainLabel: "批量维护工种", exportLabel: "导出当前工种", cycle: scope === "external",
        wizard: { kind: "op_types", title: "批量维护工种配置", desc: "维护工种编号、名称、归属（自制/外协）与备注；写入前会逐行检查。",
          sampleRows: [
            { row_num: 2, status: "update", message: "已存在，更新名称", data: { 工种编号: "OT003", 名称: "钳工", 归属: "自制" } },
            { row_num: 3, status: "new", message: "新增工种", data: { 工种编号: "OT009", 名称: "去毛刺", 归属: "自制" } },
            { row_num: 4, status: "error", message: "归属只能是 自制 / 外协", data: { 工种编号: "OT010", 归属: "委外" } },
          ] } },
    ];

    const list = rows
      .filter((r) => scope !== "all" || filter === "all" || r.category === filter)
      .filter((r) => !q || (r.op_type_id + r.name + (r.remark || "")).toLowerCase().includes(q.toLowerCase()));
    const totalPages = Math.ceil(list.length / perPage);
    const pageRows = list.slice((page - 1) * perPage, page * perPage);

    const tryDelete = (r) => {
      if (r.refs && r.refs.length) { flashFn("danger", "无法删除工种 " + r.name + "：仍被" + r.refs.join("、") + "引用，请先解除引用。"); return; }
      setRows((arr) => arr.filter((x) => x.op_type_id !== r.op_type_id));
      flashFn("ok", "已删除工种 " + r.name + "。");
    };

    const cols = [
      { key: "op_type_id", title: "工种编号", width: 130, render: (r) => <a className="bd-link" onClick={() => onOpen(r.op_type_id)}>{r.op_type_id}</a> },
      { key: "name", title: "工种名称", width: 160 },
      scope === "all" ? { key: "category", title: "归属", width: 100, render: (r) => <Badge tone={catTone(r.category)} dot>{catZh(r.category)}</Badge> } : null,
      { key: "remark", title: "备注", render: (r) => r.remark || <span className="muted">-</span> },
      { key: "act", title: "操作", width: 170, render: (r) => (
        <div className="bd-cell-actions">
          <Button variant="secondary" size="sm" onClick={() => onOpen(r.op_type_id)}>查看/编辑</Button>
          <ConfirmButton label="删除" title={"删除工种 " + r.name + "？"}
            body={r.refs && r.refs.length
              ? <>该工种已被 <strong>{r.refs.join("、")}</strong> 引用，删除会被拒绝以保护排产数据。仍要尝试吗？</>
              : <>确认删除工种 <strong>{r.name}</strong>（{r.op_type_id}）吗？</>}
            onConfirm={() => tryDelete(r)} />
        </div>
      ) },
    ].filter(Boolean);

    const submit = () => {
      const errs = {};
      if (!form.op_type_id) errs.op_type_id = "请填写工种编号。";
      else if (rows.some((r) => r.op_type_id === form.op_type_id)) errs.op_type_id = "工种编号 " + form.op_type_id + " 已存在。";
      if (!form.name) errs.name = "请填写工种名称。";
      if (Object.keys(errs).length) { setErrors(errs); return; }
      setErrors({});
      setRows((arr) => [{ ...form, refs: [] }, ...arr]);
      flashFn("ok", "已添加" + catZh(form.category) + "工种 " + form.name + "。");
      setForm({ op_type_id: "", name: "", category: defCat, remark: "" });
    };

    const title = scope === "internal" ? "自制工种" : scope === "external" ? "外协工种" : "工种配置";
    const desc = scope === "all"
      ? "工种是一张表，按归属（自制 / 外协）区分；自制工种供自制链使用，外协工种供外协链使用。"
      : "本 tab 只显示「" + catZh(scope) + "」工种；新建时归属预设为" + catZh(scope) + "，供路线文字生成工序与下游资源绑定时使用。";

    return (
      <div className="bd-card-gap">
        <ActionCards title="批量维护" subtitle="适合 Excel 下发或整批复核；手工新增继续使用下方表单。" cards={cards} onOpen={onWiz} />

        <Panel title={"新增" + (scope === "all" ? "工种" : catZh(scope) + "工种")}>
          <div className="bd-form-grid">
            <Field label="工种编号" required error={errors.op_type_id}><input className="bd-input" placeholder="如：OT001" value={form.op_type_id} onChange={(e) => setField({ op_type_id: e.target.value })} /></Field>
            <Field label="工种名称" required error={errors.name}><input className="bd-input" placeholder="如：数车 / 数铣 / 钳 / 电镀" value={form.name} onChange={(e) => setField({ name: e.target.value })} /></Field>
            <Field label="归属" required hint={scope === "all" ? "决定它进入自制链还是外协链。" : "本 tab 固定为" + catZh(scope) + "。"}>
              <select className="bd-select" value={form.category} disabled={scope !== "all"} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                <option value="internal">自制</option>
                <option value="external">外协</option>
              </select>
            </Field>
            <Field label="备注"><input className="bd-input" placeholder="可选" value={form.remark} onChange={(e) => setForm({ ...form, remark: e.target.value })} /></Field>
          </div>
          <div className={"bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")}>
            {Object.keys(errors).length ? <span className="bd-form-error">请填写标红的必填项</span> : null}
            <Button variant="primary" size="md" onClick={submit}>添加工种</Button>
          </div>
        </Panel>

        <Panel title={title + "列表"} description={desc}>
          <div className="bd-search">
            <Field label="搜索"><input className="bd-input" placeholder="输入工种编号、名称…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></Field>
            {scope === "all" ? (
              <Field label="归属筛选">
                <B_Seg options={[{ value: "all", label: "全部" }, { value: "internal", label: "自制" }, { value: "external", label: "外协" }]} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} ariaLabel="按归属筛选工种" />
              </Field>
            ) : null}
          </div>
          {list.length ? (
            <>
              <Pager page={page} totalPages={totalPages} total={list.length} onPrev={() => setPage((p) => p - 1)} onNext={() => setPage((p) => p + 1)} />
              <div className="bd-table-scroll"><Table columns={cols} rows={pageRows} rowKey="op_type_id" /></div>
            </>
          ) : <Empty title="暂无工种数据" desc="可在上方手动新增，或用 Excel 批量维护导入。" />}
        </Panel>
      </div>
    );
  }

  /* ============================================================ DETAIL */
  function OpTypeDetail({ row, scope, onBack, onSave, flashFn }) {
    const { Panel, Button, Badge } = DS();
    const { Field } = B();
    const [v, setV] = useState({ name: row.name, category: row.category, remark: row.remark || "" });
    const [errors, setErrors] = useState({});
    const setField = (patch) => { setV((s) => ({ ...s, ...patch })); setErrors((e) => { const n = { ...e }; Object.keys(patch).forEach((k) => delete n[k]); return n; }); };
    const save = () => {
      if (!v.name) { setErrors({ name: "请填写工种名称。" }); return; }
      setErrors({});
      onSave(row.op_type_id, v); flashFn("ok", "已保存工种 " + v.name + "。"); onBack();
    };

    return (
      <div className="bd-card-gap">
        <Panel title="工种配置 · 详情" description="维护工种名称、归属与备注。工种编号创建后不可更改。"
          headerRight={<Button variant="ghost" size="sm" onClick={onBack}>← 返回列表</Button>}>
          <div className="bd-meta-row">
            <span><span className="bd-meta-label">工种编号：</span><strong>{row.op_type_id}</strong></span>
            <span><span className="bd-meta-label">归属：</span><Badge tone={catTone(v.category)} dot>{catZh(v.category)}</Badge></span>
            <span><span className="bd-meta-label">引用：</span>{row.refs && row.refs.length ? <Badge tone="secondary">{row.refs.join(" / ")}</Badge> : <span className="muted">无</span>}</span>
          </div>
        </Panel>

        <Panel title="编辑工种">
          <div className="bd-form-grid">
            <Field label="工种编号"><input className="bd-input" value={row.op_type_id} disabled /></Field>
            <Field label="工种名称" required error={errors.name}><input className="bd-input" value={v.name} onChange={(e) => setField({ name: e.target.value })} /></Field>
            <Field label="归属" required hint={scope === "all" ? "改归属会切换它所属的产能链。" : "本 tab 固定为" + catZh(scope) + "。"}>
              <select className="bd-select" value={v.category} disabled={scope !== "all"} onChange={(e) => setField({ category: e.target.value })}>
                <option value="internal">自制</option>
                <option value="external">外协</option>
              </select>
            </Field>
            <Field label="备注" wide><input className="bd-input" placeholder="可选" value={v.remark} onChange={(e) => setV({ ...v, remark: e.target.value })} /></Field>
          </div>
          <div className={"bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")}>
            {Object.keys(errors).length ? <span className="bd-form-error">请填写标红的必填项</span> : null}
            <Button variant="secondary" size="md" onClick={onBack}>取消</Button>
            <Button variant="primary" size="md" onClick={save}>保存</Button>
          </div>
        </Panel>
      </div>
    );
  }

  function B_Seg(props) { const S = window.BD.Seg; return <S {...props} />; }

  window.OpTypesModule = OpTypesModule;
})();
