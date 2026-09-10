// APS Workbench · 基础资料 › 自制 › 人员模块（可复用）
// 列表 + 内联新增（多技能复选）+ 主从编辑页 + 双 Excel（① 批量维护人员 ② 技能矩阵）
// 自制链资源：人员掌握多个自制工种（技能矩阵，多对多）。
(function () {
  const { useState } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;

  const SEED = [
    { code: "P-021", name: "张三", skills: ["数铣", "数车"], status: "active", refs: ["排班"] },
    { code: "P-024", name: "李四", skills: ["钳工", "总检"], status: "active", refs: [] },
    { code: "P-030", name: "王五", skills: ["数车", "精磨", "钻孔"], status: "active", refs: ["排班"] },
    { code: "P-033", name: "赵六", skills: ["总检"], status: "leave", refs: [] },
    { code: "P-040", name: "钱七", skills: ["数铣", "钳工", "标印"], status: "active", refs: [] },
  ];
  const STATUS_OPTS = [{ value: "active", label: "在岗" }, { value: "leave", label: "请假" }, { value: "disabled", label: "停用" }];
  const statusZh = (s) => (s === "leave" ? "请假" : s === "disabled" ? "停用" : "在岗");
  const statusTone = (s) => (s === "leave" ? "danger" : s === "disabled" ? "secondary" : "ok");

  function PersonnelModule({ flashFn }) {
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
      return <PersonnelDetail row={row} onBack={back} onSave={patch} flashFn={flashFn} />;
    }
    return <PersonnelList rows={rows} setRows={setRows} onOpen={open} onWiz={setWiz} flashFn={flashFn} />;
  }

  /* ============================================================ LIST */
  function PersonnelList({ rows, setRows, onOpen, onWiz, flashFn }) {
    const { Panel, Button, Badge, Table } = DS();
    const { Field, ActionCards, ConfirmButton, Pager, Empty, Chips, CheckGroup, opTypeNames } = B();
    const intTypes = opTypeNames("internal");
    const [q, setQ] = useState("");
    const [page, setPage] = useState(1);
    const perPage = 8;
    const [form, setForm] = useState({ code: "", name: "", skills: [], status: "active" });
    const [errors, setErrors] = useState({});
    const setField = (patch) => { setForm((f) => ({ ...f, ...patch })); setErrors((e) => { const n = { ...e }; Object.keys(patch).forEach((k) => delete n[k]); return n; }); };
    const [showMatrix, setShowMatrix] = useState(false);

    const cards = [
      { title: "批量维护人员", desc: "下载模板、上传检查、确认写入或导出人员台账；含工号、姓名、状态。",
        maintainLabel: "批量维护人员", exportLabel: "导出当前人员",
        wizard: { kind: "operator", title: "批量维护人员", desc: "维护工号、姓名与在岗状态；技能工种在「技能矩阵」里单独维护。",
          sampleRows: [
            { row_num: 2, status: "update", message: "更新状态 在岗→请假", data: { 工号: "P-033", 状态: "请假" } },
            { row_num: 3, status: "new", message: "新增人员", data: { 工号: "P-041", 姓名: "孙八" } },
          ] } },
      { title: "批量维护技能矩阵", desc: "维护人员 ↔ 自制工种的多对多技能矩阵，独立三步流；决定谁能上哪道工序。",
        maintainLabel: "批量维护技能矩阵", exportLabel: "导出技能矩阵",
        wizard: { kind: "skill_matrix", title: "批量维护技能矩阵", desc: "每行 = 一个人对一个工种是否掌握；工号、工种必须已存在。",
          modeOptions: [{ value: "overwrite", label: "更新已有，新增缺少" }, { value: "replace", label: "清空矩阵后重导" }],
          sampleRows: [
            { row_num: 2, status: "new", message: "张三 + 钳工", data: { 工号: "P-021", 工种: "钳工", 掌握: "是" } },
            { row_num: 3, status: "update", message: "李四 − 总检", data: { 工号: "P-024", 工种: "总检", 掌握: "否" } },
            { row_num: 4, status: "error", message: "工种「车铣复合」不是自制工种", data: { 工号: "P-030", 工种: "车铣复合" } },
          ] } },
    ];

    const list = rows.filter((r) => !q || (r.code + r.name + r.skills.join("")).toLowerCase().includes(q.toLowerCase()));
    const totalPages = Math.ceil(list.length / perPage);
    const pageRows = list.slice((page - 1) * perPage, page * perPage);

    const tryDelete = (r) => {
      if (r.refs && r.refs.length) { flashFn("danger", "无法删除人员 " + r.name + "：仍被" + r.refs.join("、") + "引用，请先解除引用。"); return; }
      setRows((arr) => arr.filter((x) => x.code !== r.code));
      flashFn("ok", "已删除人员 " + r.name + "。");
    };

    const cols = [
      { key: "code", title: "工号", width: 110, render: (r) => <a className="bd-link" onClick={() => onOpen(r.code)}>{r.code}</a> },
      { key: "name", title: "姓名", width: 120 },
      { key: "skills", title: "技能工种（可多个）", render: (r) => <Chips items={r.skills} tone="internal" /> },
      { key: "status", title: "状态", width: 100, render: (r) => <Badge tone={statusTone(r.status)} dot>{statusZh(r.status)}</Badge> },
      { key: "act", title: "操作", width: 170, render: (r) => (
        <div className="bd-cell-actions">
          <Button variant="secondary" size="sm" onClick={() => onOpen(r.code)}>查看/编辑</Button>
          <ConfirmButton label="删除" title={"删除人员 " + r.name + "？"}
            body={r.refs && r.refs.length ? <>该人员已被 <strong>{r.refs.join("、")}</strong> 引用，删除会被拒绝。仍要尝试吗？</> : <>确认删除人员 <strong>{r.name}</strong>（{r.code}）吗？</>}
            onConfirm={() => tryDelete(r)} />
        </div>
      ) },
    ];

    const submit = () => {
      const errs = {};
      if (!form.code) errs.code = "请填写工号。";
      else if (rows.some((r) => r.code === form.code)) errs.code = "工号 " + form.code + " 已存在。";
      if (!form.name) errs.name = "请填写姓名。";
      if (Object.keys(errs).length) { setErrors(errs); return; }
      setErrors({});
      setRows((arr) => [{ ...form, refs: [] }, ...arr]);
      flashFn("ok", "已添加人员 " + form.name + (form.skills.length ? "（技能：" + form.skills.join("、") + "）" : "") + "。");
      setForm({ code: "", name: "", skills: [], status: "active" });
    };

    return (
      <div className="bd-card-gap">
        <ActionCards title="批量维护" subtitle="人员台账与技能矩阵各走一套独立的 Excel 三步流；手工新增继续使用下方表单。" cards={cards} onOpen={onWiz} />

        <Panel title="人员列表" description="人员可掌握多个自制工种（技能矩阵），决定他能上哪道自制工序。">
          <div className="bd-form-grid">
            <Field label="工号" required error={errors.code}><input className="bd-input" placeholder="如：P-021" value={form.code} onChange={(e) => setField({ code: e.target.value })} /></Field>
            <Field label="姓名" required error={errors.name}><input className="bd-input" placeholder="如：张三" value={form.name} onChange={(e) => setField({ name: e.target.value })} /></Field>
            <Field label="状态" required>
              <select className="bd-select" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                {STATUS_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Field>
            <Field label="技能工种（可多选）" wide hint="从自制工种里勾选；也可稍后在「技能矩阵」里批量维护。">
              <CheckGroup options={intTypes} value={form.skills} onChange={(v) => setForm({ ...form, skills: v })} />
            </Field>
          </div>
          <div className={"bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")}>
            {Object.keys(errors).length ? <span className="bd-form-error">请填写标红的必填项</span> : null}
            <Button variant="primary" size="md" onClick={submit}>新增人员</Button>
          </div>
        </Panel>

        <Panel title="人员台账" headerRight={<Button variant="secondary" size="sm" onClick={() => setShowMatrix((s) => !s)}>{showMatrix ? "收起技能矩阵" : "查看技能矩阵"}</Button>}>
          <div className="bd-search">
            <Field label="搜索"><input className="bd-input" placeholder="输入工号、姓名、技能…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></Field>
          </div>
          {showMatrix ? <SkillMatrix rows={rows} types={intTypes} /> : null}
          {list.length ? (
            <>
              <Pager page={page} totalPages={totalPages} total={list.length} onPrev={() => setPage((p) => p - 1)} onNext={() => setPage((p) => p + 1)} />
              <div className="bd-table-scroll"><Table columns={cols} rows={pageRows} rowKey="code" /></div>
            </>
          ) : <Empty title="暂无人员数据" desc="可在上方手动新增，或用 Excel 批量维护导入。" />}
        </Panel>
      </div>
    );
  }

  /* ---------- 技能矩阵（只读，人员 × 工种） ---------- */
  function SkillMatrix({ rows, types }) {
    return (
      <div style={{ marginBottom: 16 }}>
        <p className="bd-sec-sub">人员 × 自制工种掌握情况（只读视图，维护走「批量维护技能矩阵」）。</p>
        <div className="bd-matrix-scroll">
          <table className="bd-matrix">
            <thead>
              <tr><th>人员</th>{types.map((t) => <th key={t}>{t}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.code}>
                  <th>{r.name} <span className="muted" style={{ fontWeight: 400 }}>{r.code}</span></th>
                  {types.map((t) => <td key={t} className={r.skills.includes(t) ? "mx-on" : "mx-off"}>{r.skills.includes(t) ? "●" : "·"}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  /* ============================================================ DETAIL */
  function PersonnelDetail({ row, onBack, onSave, flashFn }) {
    const { Panel, Button, Badge } = DS();
    const { Field, CheckGroup, opTypeNames } = B();
    const intTypes = opTypeNames("internal");
    const [v, setV] = useState({ name: row.name, skills: row.skills.slice(), status: row.status });
    const [errors, setErrors] = useState({});
    const setField = (patch) => { setV((s) => ({ ...s, ...patch })); setErrors((e) => { const n = { ...e }; Object.keys(patch).forEach((k) => delete n[k]); return n; }); };

    const save = () => {
      if (!v.name) { setErrors({ name: "请填写姓名。" }); return; }
      setErrors({});
      onSave(row.code, v);
      flashFn("ok", "已保存人员 " + v.name + "。"); onBack();
    };

    return (
      <div className="bd-card-gap">
        <Panel title="人员 · 详情" description="维护姓名、技能工种与在岗状态。工号创建后不可更改。"
          headerRight={<Button variant="ghost" size="sm" onClick={onBack}>← 返回列表</Button>}>
          <div className="bd-meta-row">
            <span><span className="bd-meta-label">工号：</span><strong>{row.code}</strong></span>
            <span><span className="bd-meta-label">状态：</span><Badge tone={statusTone(v.status)} dot>{statusZh(v.status)}</Badge></span>
            <span><span className="bd-meta-label">技能数：</span><strong style={{ fontVariantNumeric: "tabular-nums" }}>{v.skills.length}</strong></span>
          </div>
        </Panel>
        <Panel title="编辑人员">
          <div className="bd-form-grid">
            <Field label="工号"><input className="bd-input" value={row.code} disabled /></Field>
            <Field label="姓名" required error={errors.name}><input className="bd-input" value={v.name} onChange={(e) => setField({ name: e.target.value })} /></Field>
            <Field label="状态" required>
              <select className="bd-select" value={v.status} onChange={(e) => setV({ ...v, status: e.target.value })}>
                {STATUS_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </Field>
            <Field label="技能工种（可多选）" wide hint="从自制工种里勾选。">
              <CheckGroup options={intTypes} value={v.skills} onChange={(s) => setV({ ...v, skills: s })} />
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

  window.PersonnelModule = PersonnelModule;
})();
