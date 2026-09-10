// APS Workbench · 基础资料 › 工艺 tab — 零件工艺模板（主从工作区）
// List → master-detail (5 zones): 基础信息 / 重新生成 / 工序概况 / 工序清单(自制行内编辑) / 连续外协工序组
(function () {
  const { useState } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;

  // 零件工艺模板的数据来自 BaseShared 的共享零件库（window.BD.usePartsStore），
  // 与批次管理的图号下拉是同一份数据源。

  const sourceZh = (s) => (s === "external" ? "外协" : "自制");

  function ProcessTab({ flashFn }) {
    const [parts, setParts] = window.BD.usePartsStore();
    const [view, setView] = useState("list");
    const [openPart, setOpenPart] = useState(null);
    const [wiz, setWiz] = useState(null);

    const openDetail = (pn) => { setOpenPart(pn); setView("detail"); window.scrollTo({ top: 0 }); };
    const back = () => { setView("list"); setOpenPart(null); window.scrollTo({ top: 0 }); };

    const updatePart = (pn, patch) =>
      setParts((arr) => arr.map((p) => (p.part_no === pn ? { ...p, ...patch } : p)));

    if (wiz) {
      const W = B().ExcelWizard;
      return <W wiz={wiz} onClose={() => setWiz(null)} onDone={(s) => flashFn("ok", "Excel 导入完成：" + s + "。")} />;
    }
    if (view === "detail") {
      const part = parts.find((p) => p.part_no === openPart);
      return <ProcessDetail part={part} onBack={back} onUpdate={updatePart} flashFn={flashFn} />;
    }
    return <ProcessList parts={parts} setParts={setParts} onOpen={openDetail} onWiz={setWiz} flashFn={flashFn} />;
  }

  /* ============================================================ LIST */
  function ProcessList({ parts, setParts, onOpen, onWiz, flashFn }) {
    const { Panel, Button, Badge, Table } = DS();
    const { Field, ActionCards, Toggle, ConfirmButton } = B();
    const [q, setQ] = useState("");
    const [sel, setSel] = useState({});
    const [form, setForm] = useState({ part_no: "", part_name: "", route_raw: "", remark: "", strict: false });
    const [errors, setErrors] = useState({});
    const setField = (patch) => { setForm((f) => ({ ...f, ...patch })); setErrors((e) => { const n = { ...e }; Object.keys(patch).forEach((k) => delete n[k]); return n; }); };

    const cards = [
      { title: "批量维护路线文字", desc: "维护图号、名称和路线文字，系统会按路线生成零件工序清单和连续外协工序组。", maintainLabel: "批量维护路线", exportLabel: "导出当前路线",
        wizard: { kind: "routes", title: "批量维护路线文字", desc: "确认写入后按路线文字生成工序清单；生成失败的行计为错误，不写入。", strict: true } },
      { title: "批量维护工序工时", desc: "维护自制工序的换型时间和单件工时；可选择只补空工时。", maintainLabel: "批量维护工时", exportLabel: "导出当前工时",
        wizard: { kind: "hours", title: "批量维护工序工时", desc: "维护自制工序换型/单件工时。", modeOptions: [{ value: "overwrite", label: "更新已有工时" }, { value: "fill", label: "只补空工时" }],
          sampleRows: [
            { row_num: 2, status: "update", message: "更新换型/单件工时", data: { 图号: "T-1008", 工序: 5, 换型: 0.5, 单件: 1.2 } },
            { row_num: 3, status: "unchanged", message: "工时一致，跳过", data: { 图号: "T-1009", 工序: 10 } },
            { row_num: 4, status: "skip", message: "外协工序无工时，跳过", data: { 图号: "T-1008", 工序: 30 } },
          ] } },
      { title: "导出工序清单", desc: "导出当前零件工序、归属、供应商和外协周期，用于复核。", exportLabel: "导出工序清单" },
    ];

    const list = parts.filter((p) => !q || (p.part_no + p.part_name + p.route_raw).toLowerCase().includes(q.toLowerCase()));
    const selCount = Object.values(sel).filter(Boolean).length;
    const toggleAll = (on) => { const m = {}; if (on) list.forEach((p) => (m[p.part_no] = true)); setSel(m); };

    const cols = [
      { key: "sel", title: <input type="checkbox" aria-label="全选" checked={list.length > 0 && selCount === list.length} onChange={(e) => toggleAll(e.target.checked)} />, width: 44,
        render: (r) => <input type="checkbox" aria-label={"选择 " + r.part_no} checked={!!sel[r.part_no]} onChange={(e) => setSel((s) => ({ ...s, [r.part_no]: e.target.checked }))} /> },
      { key: "part_no", title: "图号", width: 130, render: (r) => <a className="bd-link" onClick={() => onOpen(r.part_no)}>{r.part_no}</a> },
      { key: "part_name", title: "名称", width: 150 },
      { key: "route_raw", title: "路线文字", render: (r) => r.route_raw ? <span title={r.route_raw} style={{ display: "block", maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.route_raw}</span> : <span className="muted">-</span> },
      { key: "parsed", title: "工序清单", width: 110, render: (r) => <Badge tone={r.parsed ? "ok" : "warning"} dot>{r.parsed ? "已解析" : "未解析"}</Badge> },
      { key: "act", title: "操作", width: 160, render: (r) => (
        <div className="bd-cell-actions">
          <Button variant="secondary" size="sm" onClick={() => onOpen(r.part_no)}>查看/编辑</Button>
          <ConfirmButton label="删除" title={"删除零件 " + r.part_no + "？"} body={<>如果该零件已被批次引用，将<strong>拒绝删除</strong>以保护已有排产数据。确认删除吗？</>}
            onConfirm={() => { setParts((arr) => arr.filter((p) => p.part_no !== r.part_no)); flashFn("ok", "已删除零件 " + r.part_no + "。"); }} />
        </div>
      ) },
    ];

    const submit = () => {
      const errs = {};
      if (!form.part_no) errs.part_no = "请填写图号。";
      else if (parts.some((p) => p.part_no === form.part_no)) errs.part_no = "图号 " + form.part_no + " 已存在。";
      if (!form.part_name) errs.part_name = "请填写名称。";
      if (Object.keys(errs).length) { setErrors(errs); return; }
      setErrors({});
      setParts((arr) => [{ part_no: form.part_no, part_name: form.part_name, route_raw: form.route_raw, remark: form.remark, parsed: !!form.route_raw, ops: [], groups: [] }, ...arr]);
      flashFn("ok", "已添加零件 " + form.part_no + (form.route_raw ? "，并尝试生成工序清单。" : "。"));
      setForm({ part_no: "", part_name: "", route_raw: "", remark: "", strict: false });
    };

    return (
      <div className="bd-card-gap">
        <ActionCards title="批量维护" subtitle="适合 Excel 下发或整批复核；手工新增继续使用下方表单。" cards={cards} onOpen={onWiz} />

        <Panel title="新增零件">
          <div className="bd-form-grid">
            <Field label="图号" required error={errors.part_no}><input className="bd-input" placeholder="如：A1234" value={form.part_no} onChange={(e) => setField({ part_no: e.target.value })} /></Field>
            <Field label="名称" required error={errors.part_name}><input className="bd-input" placeholder="如：壳体-大" value={form.part_name} onChange={(e) => setField({ part_name: e.target.value })} /></Field>
            <Field label="路线文字" hint="可选，填写后会尝试生成工序清单。" wide><input className="bd-input" placeholder="如：5数铣10钳20数车35标印40总检45表处理" value={form.route_raw} onChange={(e) => setForm({ ...form, route_raw: e.target.value })} /></Field>
            <Field label="备注"><input className="bd-input" placeholder="可选" value={form.remark} onChange={(e) => setForm({ ...form, remark: e.target.value })} /></Field>
            <Toggle checked={form.strict} onChange={(v) => setForm({ ...form, strict: v })} label="资料不完整就停下（严格模式）"
              help="勾选后：路线里有不认识的工种、没有启用的外协供应商，或外协周期无效时，会直接提示错误并停止创建。不勾选：零件会先保存，缺周期等可补项先按 1 天记录并提醒补正。" />
          </div>
          <div className={"bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")}>
            {Object.keys(errors).length ? <span className="bd-form-error">请填写标红的必填项</span> : null}
            <Button variant="primary" size="md" onClick={submit}>添加零件</Button>
          </div>
        </Panel>

        <Panel title="零件工艺模板" description="批量操作可批量删除零件；若零件已被批次引用，将禁止删除以避免影响已有排产数据。">
          <div className="bd-search">
            <Field label="搜索"><input className="bd-input" placeholder="输入图号、名称…" value={q} onChange={(e) => setQ(e.target.value)} /></Field>
          </div>
          {list.length ? (
            <>
              <div className="bd-table-scroll"><Table columns={cols} rows={list} rowKey="part_no" /></div>
              <div className="bd-action-bar">
                <span className="muted">已选 <strong style={{ fontVariantNumeric: "tabular-nums" }}>{selCount}</strong> 个零件</span>
                <ConfirmButton label="批量删除" title="批量删除所选零件？" body="若所选零件存在批次引用，对应行将删除失败并提示。确认继续吗？"
                  onConfirm={() => { setParts((arr) => arr.filter((p) => !sel[p.part_no])); setSel({}); flashFn("ok", "已批量删除 " + selCount + " 个零件。"); }} />
              </div>
            </>
          ) : (
            <B_Empty title="还没有零件数据" desc="可以手动新增，或用上方 Excel 批量维护导入。" />
          )}
        </Panel>
      </div>
    );
  }

  /* ============================================================ DETAIL */
  function ProcessDetail({ part, onBack, onUpdate, flashFn }) {
    const { Panel, Button, Badge, Table } = DS();
    const { Field, Toggle, ConfirmButton } = B();
    const [base, setBase] = useState({ part_name: part.part_name, route_raw: part.route_raw, remark: part.remark });
    const [reparse, setReparse] = useState({ route_raw: part.route_raw, strict: false });

    const internal = part.ops.filter((o) => o.source === "internal").length;
    const external = part.ops.filter((o) => o.source === "external").length;

    const opCols = [
      { key: "seq", title: "工序", width: 80, align: "right", render: (r) => (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontVariantNumeric: "tabular-nums" }}>
          <span style={{ width: 3, height: 16, borderRadius: 2, background: r.source === "external" ? "var(--ui-warning)" : "var(--ui-primary)" }} />{r.seq}
        </span> ) },
      { key: "op_type", title: "工种", width: 110 },
      { key: "source", title: "归属", width: 90, render: (r) => <Badge tone={r.source === "external" ? "warning" : "notice"} dot>{sourceZh(r.source)}</Badge> },
      { key: "config", title: "配置", render: (r) => r.source === "internal"
        ? <InternalHoursCell op={r} part={part} onUpdate={onUpdate} flashFn={flashFn} />
        : <span className="bd-cell-note">周期由连续外协工序组统一管理</span> },
      { key: "ext", title: "外协信息", width: 220, render: (r) => r.source === "external"
        ? <div className="bd-cell-note">
            <div>供应商：{r.supplier || "-"}</div>
            {r.group ? <div>连续外协工序组：{r.group}</div> : null}
            <div>周期：{r.ext_days != null ? r.ext_days + " 天" : <span style={{ color: "var(--ui-warning-text)" }}>待补</span>}</div>
          </div>
        : <span className="muted">-</span> },
    ];

    return (
      <div className="bd-card-gap">
        <Panel
          title="零件工艺模板 · 详情"
          description="维护单个零件的路线文字、工序清单、自制工时和连续外协工序周期。"
          headerRight={<Button variant="ghost" size="sm" onClick={onBack}>← 返回列表</Button>}
        >
          <div className="bd-meta-row">
            <span><span className="bd-meta-label">图号：</span><strong>{part.part_no}</strong></span>
            <span><span className="bd-meta-label">名称：</span><strong>{part.part_name}</strong></span>
            <span><span className="bd-meta-label">工序清单：</span><Badge tone={part.parsed ? "ok" : "warning"} dot>{part.parsed ? "已解析" : "未解析"}</Badge></span>
          </div>
        </Panel>

        {/* zone 1 */}
        <Panel title="① 零件基础信息">
          <div className="bd-form-grid">
            <Field label="图号"><input className="bd-input" value={part.part_no} disabled /></Field>
            <Field label="名称" required><input className="bd-input" value={base.part_name} onChange={(e) => setBase({ ...base, part_name: e.target.value })} /></Field>
            <Field label="路线文字" wide hint="可含空格、逗号、顿号、破折号等分隔符；生成工序清单时会统一处理。"><input className="bd-input" value={base.route_raw} onChange={(e) => setBase({ ...base, route_raw: e.target.value })} /></Field>
            <Field label="备注"><input className="bd-input" placeholder="可选" value={base.remark} onChange={(e) => setBase({ ...base, remark: e.target.value })} /></Field>
          </div>
          <div className="bd-form-footer">
            <Button variant="primary" size="md" onClick={() => { onUpdate(part.part_no, base); flashFn("ok", "已保存基础信息。"); }}>保存</Button>
          </div>
        </Panel>

        {/* zone 2 */}
        <Panel title="② 按路线重新生成工序清单" description="保存后系统会按这段路线文字重新生成工序清单；若生成失败，原工序清单不会被改动。">
          <div className="bd-form-grid">
            <Field label="用于生成工序清单的路线文字" wide><input className="bd-input" value={reparse.route_raw} onChange={(e) => setReparse({ ...reparse, route_raw: e.target.value })} /></Field>
            <Toggle checked={reparse.strict} onChange={(v) => setReparse({ ...reparse, strict: v })} label="资料不完整就停下（严格模式）"
              help="勾选后：不认识的工种、未启用外协供应商或外协周期无效时直接报错并停止生成。不勾选：能确认的工序继续处理，缺周期先按 1 天记录并提醒补正。" />
          </div>
          <div className="bd-form-footer">
            <Button variant="secondary" size="md" onClick={() => { onUpdate(part.part_no, { route_raw: reparse.route_raw, parsed: true }); flashFn("ok", "已按路线重新生成工序清单。"); }}>按路线重新生成工序清单</Button>
          </div>
        </Panel>

        {/* zone 3 */}
        <Panel title="③ 工序概况">
          <div className="bd-summary-grid">
            <div className="bd-summary-item sev-notice"><span className="si-label">工序总数</span><span className="si-value">{part.ops.length}</span></div>
            <div className="bd-summary-item sev-notice"><span className="si-label">自制工序</span><span className="si-value">{internal}</span></div>
            <div className="bd-summary-item sev-notice"><span className="si-label">外协工序</span><span className="si-value">{external}</span></div>
          </div>
          {part.ops.length === 0 ? <p className="bd-sec-sub" style={{ marginTop: 12 }}>还没有工序：请在上方填写路线文字并点击“按路线重新生成工序清单”。</p> : null}
        </Panel>

        {/* zone 4 */}
        <Panel title="④ 工序清单" description="蓝色=自制工序，橙色=外协工序。自制工序可逐行编辑换型/单件工时。">
          {part.ops.length ? (
            <div className="bd-table-scroll">
              <Table columns={opCols} rows={part.ops.map((o) => ({ ...o, id: o.seq }))} rowKey="seq" />
            </div>
          ) : <B_Empty title="暂无工序清单" desc="先在上方按路线生成工序清单。" />}
        </Panel>

        {/* zone 5 */}
        <Panel title="⑤ 连续外协工序周期" description="每个连续外协工序组单独设置周期模式与周期（天）。">
          {part.groups.length ? part.groups.map((g) => (
            <ExternalGroup key={g.id} group={g} part={part} onUpdate={onUpdate} flashFn={flashFn} />
          )) : <B_Empty title="暂无外协工序组" desc="当前模板中没有连续外协工序。" />}
        </Panel>
      </div>
    );
  }

  function InternalHoursCell({ op, part, onUpdate, flashFn }) {
    const { Button } = DS();
    const { Field } = B();
    const [v, setV] = useState({ setup: op.setup, unit: op.unit });
    const dirty = String(v.setup) !== String(op.setup) || String(v.unit) !== String(op.unit);
    const save = () => {
      onUpdate(part.part_no, { ops: part.ops.map((o) => (o.seq === op.seq ? { ...o, setup: Number(v.setup) || 0, unit: Number(v.unit) || 0 } : o)) });
      flashFn("ok", "已保存工序 " + op.seq + " 的工时。");
    };
    return (
      <div className="bd-inline-grid">
        <Field label="换型（小时）"><input className={"bd-cell-input num" + (dirty ? " bd-cell-dirty" : "")} style={{ width: 90 }} value={v.setup} onChange={(e) => setV({ ...v, setup: e.target.value })} /></Field>
        <Field label="单件（小时）"><input className={"bd-cell-input num" + (dirty ? " bd-cell-dirty" : "")} style={{ width: 90 }} value={v.unit} onChange={(e) => setV({ ...v, unit: e.target.value })} /></Field>
        <Button variant={dirty ? "primary" : "secondary"} size="sm" disabled={!dirty} onClick={save}>保存</Button>
      </div>
    );
  }

  function ExternalGroup({ group, part, onUpdate, flashFn }) {
    const { Button, Table } = DS();
    const { Field, ConfirmButton } = B();
    const gops = part.ops.filter((o) => o.group === group.id && o.source === "external");
    const [g, setG] = useState({ mode: group.mode, total: group.total ?? "", strict: group.strict });
    const [days, setDays] = useState(() => { const m = {}; gops.forEach((o) => (m[o.seq] = o.ext_days ?? "")); return m; });

    const saveGroup = () => {
      onUpdate(part.part_no, {
        groups: part.groups.map((x) => (x.id === group.id ? { ...x, mode: g.mode, total: g.total === "" ? null : Number(g.total), strict: g.strict } : x)),
        ops: part.ops.map((o) => (o.group === group.id ? { ...o, ext_days: days[o.seq] === "" ? null : Number(days[o.seq]) } : o)),
      });
      flashFn("ok", "已保存外协组 " + group.id + " 设置。");
    };

    const cols = [
      { key: "seq", title: "工序", width: 70, align: "right", render: (r) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{r.seq}</span> },
      { key: "op_type", title: "工种", width: 110 },
      { key: "ext_days", title: "周期（天，仅分别设置使用）", align: "right", render: (r) => (
        <input className="bd-cell-input num" style={{ width: 120 }} placeholder="如：1" value={days[r.seq]} disabled={g.mode === "merged"} onChange={(e) => setDays({ ...days, [r.seq]: e.target.value })} /> ) },
      { key: "hint", title: "提示", render: () => <span className="bd-cell-note">{g.mode === "merged" ? "合并设置：此处周期不生效，以整组周期为准。" : "分别设置：每道外协工序单独计时。"}</span> },
    ];

    return (
      <div className="bd-group-box">
        <div className="bd-group-head">
          <div>
            <div className="gh-title">连续外协工序组：{group.id}（{group.start} – {group.end}）</div>
            <div className="gh-meta">模式：{g.mode === "merged" ? "合并设置" : "分别设置"}</div>
          </div>
          {group.deletable
            ? <ConfirmButton label="删除此组" title={"删除外协工序组 " + group.id + "？"} body="删除后该组工序将回到未配置周期状态。确认删除吗？"
                onConfirm={() => { onUpdate(part.part_no, { groups: part.groups.filter((x) => x.id !== group.id) }); flashFn("ok", "已删除外协组 " + group.id + "。"); }} />
            : <span className="muted" style={{ fontSize: 12.5 }}>不可删除（只有排在最前或最后的外协组才能删除）</span>}
        </div>
        <div className="bd-form-grid">
          <Field label="周期模式">
            <select className="bd-select" value={g.mode} onChange={(e) => setG({ ...g, mode: e.target.value })}>
              <option value="separate">分别设置</option>
              <option value="merged">合并设置</option>
            </select>
          </Field>
          <Field label="整组周期（天，仅合并设置使用）" hint="选“合并设置”后整组只按这里计算；选“分别设置”时此处不生效。"><input className="bd-input num" style={{ maxWidth: 130 }} placeholder="如：3" value={g.total} disabled={g.mode !== "merged"} onChange={(e) => setG({ ...g, total: e.target.value })} /></Field>
          <window.BD.Toggle checked={g.strict} onChange={(v) => setG({ ...g, strict: v })} label="资料不完整就停下（严格模式）"
            help="勾选后：分别设置时每道外协工序都必须填正确周期，填空/非数字/≤0 会报错。不勾选：继续保存并把没填好的周期先按 1 天记录。" />
        </div>
        <div className="bd-form-footer"><Button variant="primary" size="md" onClick={saveGroup}>保存外协组设置</Button></div>
        {gops.length ? <div className="bd-table-scroll" style={{ marginTop: 14 }}><Table columns={cols} rows={gops.map((o) => ({ ...o, id: o.seq }))} rowKey="seq" /></div> : <p className="bd-sec-sub" style={{ marginTop: 12 }}>该组暂无外协工序。</p>}
      </div>
    );
  }

  function B_Empty(props) { const E = window.BD.Empty; return <E {...props} />; }

  window.ProcessTab = ProcessTab;
})();
