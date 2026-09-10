// APS Workbench · 基础资料 › 自制 › 设备模块（可复用）
// 列表 + 内联新增 + 主从编辑页 + 双 Excel（① 批量维护设备 ② 批量维护设备组/资源池）
// 自制链资源：设备绑 1 个自制工种，计量口径走工时。
(function () {
  const { useState } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;

  const SEED = [
    { code: "M-03", name: "五轴加工中心", op_type: "数铣", group: "精加工组", status: "active", refs: ["排产任务"] },
    { code: "M-05", name: "卧式加工中心", op_type: "数铣", group: "预加工组", status: "active", refs: ["排产任务"] },
    { code: "M-07", name: "立式加工中心", op_type: "数车", group: "预加工组", status: "active", refs: [] },
    { code: "M-12", name: "三坐标检测", op_type: "总检", group: "检验组", status: "active", refs: [] },
    { code: "M-18", name: "数控车床", op_type: "数车", group: "车加工组", status: "active", refs: [] },
    { code: "M-21", name: "精密磨床", op_type: "精磨", group: "—", status: "disabled", refs: [] },
  ];
  const STATUS_OPTS = [{ value: "active", label: "启用" }, { value: "disabled", label: "停用" }];
  const statusZh = (s) => (s === "disabled" ? "停用" : "启用");

  function EquipmentModule({ flashFn }) {
    const [rows, setRows] = useState(SEED);
    const [view, setView] = useState("list");
    const [openId, setOpenId] = useState(null);
    const [wiz, setWiz] = useState(null);

    const open = (id) => { setOpenId(id); setView("detail"); window.scrollTo({ top: 0 }); };
    const back = () => { setView("list"); setOpenId(null); window.scrollTo({ top: 0 }); };
    const patch = (id, p) => setRows((arr) => arr.map((r) => (r.code === id ? { ...r, ...p } : r)));

    if (wiz) {
      const W = B().ExcelWizard;
      return <W wiz={wiz} onClose={() => setWiz(null)} onDone={(s) => flashFn("ok", "Excel 导入完成：" + s + "。")} />;
    }
    if (view === "detail") {
      const row = rows.find((r) => r.code === openId);
      return <EquipmentDetail row={row} onBack={back} onSave={patch} flashFn={flashFn} />;
    }
    return <EquipmentList rows={rows} setRows={setRows} onOpen={open} onWiz={setWiz} flashFn={flashFn} />;
  }

  /* ============================================================ LIST */
  function EquipmentList({ rows, setRows, onOpen, onWiz, flashFn }) {
    const { Panel, Button, Badge, Table } = DS();
    const { Field, ActionCards, ConfirmButton, Pager, Empty, opTypeNames } = B();
    const intTypes = opTypeNames("internal");
    const [q, setQ] = useState("");
    const [page, setPage] = useState(1);
    const perPage = 8;
    const [form, setForm] = useState({ code: "", name: "", op_type: intTypes[0] || "", group: "", status: "active" });
    const [errors, setErrors] = useState({});
    const setField = (patch) => { setForm((f) => ({ ...f, ...patch })); setErrors((e) => { const n = { ...e }; Object.keys(patch).forEach((k) => delete n[k]); return n; }); };

    const cards = [
      { title: "批量维护设备", desc: "下载模板、上传检查、确认写入或导出设备台账；含编号、名称、所属工种、状态。",
        maintainLabel: "批量维护设备", exportLabel: "导出当前设备",
        wizard: { kind: "machine", title: "批量维护设备", desc: "维护设备编号、名称、所属自制工种与状态；所属工种必须是已存在的自制工种。",
          sampleRows: [
            { row_num: 2, status: "update", message: "更新所属工种 数车→数铣", data: { 设备编号: "M-07", 所属工种: "数铣" } },
            { row_num: 3, status: "new", message: "新增设备", data: { 设备编号: "M-22", 名称: "线切割", 所属工种: "钳工" } },
            { row_num: 4, status: "error", message: "所属工种「委外」不是自制工种", data: { 设备编号: "M-23", 所属工种: "委外" } },
          ] } },
      { title: "批量维护设备组", desc: "维护设备分组 / 资源池（设备 ↔ 设备组的归属），独立三步流，便于按组排产与统计。",
        maintainLabel: "批量维护设备组", exportLabel: "导出当前设备组",
        wizard: { kind: "machine_group", title: "批量维护设备组", desc: "维护设备组名称与组内设备成员；同一设备可只属于一个主组。",
          modeOptions: [{ value: "overwrite", label: "更新已有，新增缺少" }, { value: "replace", label: "清空设备组后重导" }],
          sampleRows: [
            { row_num: 2, status: "update", message: "精加工组 增加成员 M-05", data: { 设备组: "精加工组", 成员: "M-03,M-05" } },
            { row_num: 3, status: "new", message: "新增设备组 特种加工组", data: { 设备组: "特种加工组", 成员: "M-22" } },
          ] } },
    ];

    const list = rows.filter((r) => !q || (r.code + r.name + r.op_type + (r.group || "")).toLowerCase().includes(q.toLowerCase()));
    const totalPages = Math.ceil(list.length / perPage);
    const pageRows = list.slice((page - 1) * perPage, page * perPage);

    const tryDelete = (r) => {
      if (r.refs && r.refs.length) { flashFn("danger", "无法删除设备 " + r.code + "：仍被" + r.refs.join("、") + "引用，请先解除引用。"); return; }
      setRows((arr) => arr.filter((x) => x.code !== r.code));
      flashFn("ok", "已删除设备 " + r.code + "。");
    };

    const cols = [
      { key: "code", title: "设备编号", width: 120, render: (r) => <a className="bd-link" onClick={() => onOpen(r.code)}>{r.code}</a> },
      { key: "name", title: "设备名称", width: 170 },
      { key: "op_type", title: "所属工种", width: 120, render: (r) => <Badge tone="notice">{r.op_type}</Badge> },
      { key: "group", title: "设备组", width: 120, render: (r) => (r.group && r.group !== "—") ? r.group : <span className="muted">未分组</span> },
      { key: "status", title: "状态", width: 100, render: (r) => <Badge tone={r.status === "active" ? "ok" : "secondary"} dot>{statusZh(r.status)}</Badge> },
      { key: "act", title: "操作", width: 170, render: (r) => (
        <div className="bd-cell-actions">
          <Button variant="secondary" size="sm" onClick={() => onOpen(r.code)}>查看/编辑</Button>
          <ConfirmButton label="删除" title={"删除设备 " + r.code + "？"}
            body={r.refs && r.refs.length ? <>该设备已被 <strong>{r.refs.join("、")}</strong> 引用，删除会被拒绝。仍要尝试吗？</> : <>确认删除设备 <strong>{r.name}</strong>（{r.code}）吗？</>}
            onConfirm={() => tryDelete(r)} />
        </div>
      ) },
    ];

    const submit = () => {
      const errs = {};
      if (!form.code) errs.code = "请填写设备编号。";
      else if (rows.some((r) => r.code === form.code)) errs.code = "设备编号 " + form.code + " 已存在。";
      if (!form.name) errs.name = "请填写设备名称。";
      if (Object.keys(errs).length) { setErrors(errs); return; }
      setErrors({});
      setRows((arr) => [{ ...form, group: form.group || "—", refs: [] }, ...arr]);
      flashFn("ok", "已添加设备 " + form.code + "。");
      setForm({ code: "", name: "", op_type: intTypes[0] || "", group: "", status: "active" });
    };

    return (
      <div className="bd-card-gap">
        <ActionCards title="批量维护" subtitle="设备与设备组各走一套独立的 Excel 三步流；手工新增继续使用下方表单。" cards={cards} onOpen={onWiz} />

        <Panel title="设备列表" description="设备绑 1 个自制工种；按工种把设备并入对应产能，排产时落到设备上。"
          headerRight={null}>
          <div className="bd-form-grid">
            <Field label="设备编号" required error={errors.code}><input className="bd-input" placeholder="如：M-03" value={form.code} onChange={(e) => setField({ code: e.target.value })} /></Field>
            <Field label="设备名称" required error={errors.name}><input className="bd-input" placeholder="如：五轴加工中心" value={form.name} onChange={(e) => setField({ name: e.target.value })} /></Field>
            <Field label="所属工种" required hint="从自制工种里选 1 个。">
              <select className="bd-select" value={form.op_type} onChange={(e) => setForm({ ...form, op_type: e.target.value })}>
                {intTypes.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </Field>
            <Field label="设备组" hint="可选，留空=未分组。"><input className="bd-input" placeholder="如：精加工组" value={form.group} onChange={(e) => setForm({ ...form, group: e.target.value })} /></Field>
            <Field label="状态" required>
              <select className="bd-select" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                {STATUS_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Field>
          </div>
          <div className={"bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")}>
            {Object.keys(errors).length ? <span className="bd-form-error">请填写标红的必填项</span> : null}
            <Button variant="primary" size="md" onClick={submit}>新增设备</Button>
          </div>
        </Panel>

        <Panel title="设备台账">
          <div className="bd-search">
            <Field label="搜索"><input className="bd-input" placeholder="输入设备编号、名称、工种…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></Field>
          </div>
          {list.length ? (
            <>
              <Pager page={page} totalPages={totalPages} total={list.length} onPrev={() => setPage((p) => p - 1)} onNext={() => setPage((p) => p + 1)} />
              <div className="bd-table-scroll"><Table columns={cols} rows={pageRows} rowKey="code" /></div>
            </>
          ) : <Empty title="暂无设备数据" desc="可在上方手动新增，或用 Excel 批量维护导入。" />}
        </Panel>
      </div>
    );
  }

  /* ============================================================ DETAIL */
  function EquipmentDetail({ row, onBack, onSave, flashFn }) {
    const { Panel, Button, Badge } = DS();
    const { Field, opTypeNames } = B();
    const intTypes = opTypeNames("internal");
    const [v, setV] = useState({ name: row.name, op_type: row.op_type, group: row.group === "—" ? "" : row.group, status: row.status });
    const [errors, setErrors] = useState({});
    const setField = (patch) => { setV((s) => ({ ...s, ...patch })); setErrors((e) => { const n = { ...e }; Object.keys(patch).forEach((k) => delete n[k]); return n; }); };

    const save = () => {
      if (!v.name) { setErrors({ name: "请填写设备名称。" }); return; }
      setErrors({});
      onSave(row.code, { ...v, group: v.group || "—" });
      flashFn("ok", "已保存设备 " + row.code + "。"); onBack();
    };

    return (
      <div className="bd-card-gap">
        <Panel title="设备 · 详情" description="维护设备名称、所属工种、设备组与状态。设备编号创建后不可更改。"
          headerRight={<Button variant="ghost" size="sm" onClick={onBack}>← 返回列表</Button>}>
          <div className="bd-meta-row">
            <span><span className="bd-meta-label">设备编号：</span><strong>{row.code}</strong></span>
            <span><span className="bd-meta-label">所属工种：</span><Badge tone="notice">{v.op_type}</Badge></span>
            <span><span className="bd-meta-label">状态：</span><Badge tone={v.status === "active" ? "ok" : "secondary"} dot>{statusZh(v.status)}</Badge></span>
          </div>
        </Panel>
        <Panel title="编辑设备">
          <div className="bd-form-grid">
            <Field label="设备编号"><input className="bd-input" value={row.code} disabled /></Field>
            <Field label="设备名称" required error={errors.name}><input className="bd-input" value={v.name} onChange={(e) => setField({ name: e.target.value })} /></Field>
            <Field label="所属工种" required>
              <select className="bd-select" value={v.op_type} onChange={(e) => setV({ ...v, op_type: e.target.value })}>
                {intTypes.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </Field>
            <Field label="设备组"><input className="bd-input" placeholder="留空=未分组" value={v.group} onChange={(e) => setV({ ...v, group: e.target.value })} /></Field>
            <Field label="状态" required>
              <select className="bd-select" value={v.status} onChange={(e) => setV({ ...v, status: e.target.value })}>
                {STATUS_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Field>
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

  window.EquipmentModule = EquipmentModule;
})();
