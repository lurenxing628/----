// APS Workbench · 基础资料列表 archetype (equipment / process / personnel / material / system)
// One list pattern, parameterised by module — search + status badges + right-aligned tabular numbers.
const BD_MODULES = {
  batches: {
    title: "批次管理",
    desc: "批次列表：图号 + 数量（右对齐 tabular）+ 交期 + 状态徽标，列表/详情同款 archetype。",
    add: "新增批次", count: "个",
    cols: [
      { key: "code", title: "批次号", nowrap: true, strong: true },
      { key: "part", title: "图号", nowrap: true },
      { key: "qty", title: "数量", align: "right" },
      { key: "due", title: "交期", nowrap: true },
      { key: "prog", title: "工序进度", nowrap: true },
      { key: "state", title: "状态", kind: "badge" },
      { key: "act", title: "操作", kind: "act" },
    ],
    rows: [
      { id:1, code:"B202605-018", part:"T-1008", qty:12, due:"05-24 12:00", prog:"30 / 60", state:"超期", tone:"danger" },
      { id:2, code:"B202605-021", part:"T-1009", qty:8,  due:"05-25 08:00", prog:"20 / 50", state:"接近满载", tone:"warning" },
      { id:3, code:"B202605-019", part:"T-1006", qty:6,  due:"05-25 14:00", prog:"40 / 50", state:"正常", tone:"success" },
      { id:4, code:"B202605-017", part:"T-1004", qty:10, due:"05-26 10:00", prog:"10 / 40", state:"外协在途", tone:"notice" },
      { id:5, code:"B202605-024", part:"T-1011", qty:4,  due:"05-26 16:00", prog:"待排", state:"待排", tone:"secondary" },
    ],
  },
  field: {
    title: "现场记录",
    desc: "排产计划对应工序的实际开工 / 完工时间与工时回填（不接 MES）：计划列只读，实际三列就地填，供工时校准与执行复盘。",
    add: "导入实际工时", count: "道",
    cols: [
      { key: "batch", title: "批次", nowrap: true, strong: true },
      { key: "op", title: "工序" },
      { key: "res", title: "资源", nowrap: true },
      { key: "actStart", title: "实际开工", nowrap: true },
      { key: "actEnd", title: "实际完工", nowrap: true },
      { key: "hours", title: "工时", align: "right" },
      { key: "state", title: "状态", kind: "badge" },
    ],
    rows: [
      { id:1, batch:"B202605-019", op:"50 检验", res:"M-12 / 王五", actStart:"06-11 08:05", actEnd:"06-11 09:18", hours:"1.2", state:"已回填", tone:"success" },
      { id:2, batch:"B202605-018", op:"30 精加工", res:"M-03 / 张三", actStart:"06-11 08:10", actEnd:"—", hours:"—", state:"进行中", tone:"notice" },
      { id:3, batch:"B202605-024", op:"30 精加工", res:"M-03 / 张三", actStart:"—", actEnd:"—", hours:"—", state:"待回填", tone:"secondary" },
      { id:4, batch:"B202605-017", op:"50 检验", res:"M-12 / 王五", actStart:"—", actEnd:"—", hours:"—", state:"待回填", tone:"secondary" },
    ],
  },
  equipment: {
    title: "设备管理",
    desc: "基础资料的列表 archetype：搜索 + 状态徽标 + 数字列右对齐（tabular），与全站表格规范一致。",
    add: "新增设备", count: "台",
    cols: [
      { key: "code", title: "设备编号", nowrap: true, strong: true },
      { key: "name", title: "设备名称" },
      { key: "group", title: "工序组", nowrap: true },
      { key: "tasks", title: "本周任务", align: "right" },
      { key: "util", title: "利用率", align: "right", kind: "util" },
      { key: "state", title: "状态", kind: "badge" },
      { key: "act", title: "操作", kind: "act" },
    ],
    rows: [
      { id:1, code:"M-03", name:"五轴加工中心", group:"精加工", tasks:12, util:96, state:"接近满载", tone:"warning" },
      { id:2, code:"M-05", name:"卧式加工中心", group:"预加工", tasks:9, util:89, state:"接近满载", tone:"warning" },
      { id:3, code:"M-07", name:"立式加工中心", group:"组装", tasks:7, util:72, state:"正常", tone:"success" },
      { id:4, code:"M-12", name:"三坐标检测", group:"检验", tasks:5, util:58, state:"正常", tone:"success" },
      { id:5, code:"M-18", name:"数控车床", group:"车加工", tasks:3, util:34, state:"有余量", tone:"secondary" },
      { id:6, code:"M-21", name:"线切割", group:"特种加工", tasks:0, util:0, state:"停机维护", tone:"danger" },
    ],
  },
  process: {
    title: "工艺管理",
    desc: "工艺路线列表：图号 + 工序数 + 标准工时（右对齐 tabular）+ 外协标识，列表/详情同款 archetype。",
    add: "新增工艺", count: "项",
    cols: [
      { key: "code", title: "图号", nowrap: true, strong: true },
      { key: "name", title: "零件名称" },
      { key: "ops", title: "工序数", align: "right" },
      { key: "hours", title: "标准工时", align: "right" },
      { key: "out", title: "外协", kind: "badge" },
      { key: "state", title: "状态", kind: "badge2" },
      { key: "act", title: "操作", kind: "act" },
    ],
    rows: [
      { id:1, code:"T-1008", name:"回转壳体 A", ops:6, hours:"42.5h", out:"含外协", outTone:"notice", state:"已确认", tone:"success" },
      { id:2, code:"T-1009", name:"回转壳体 B", ops:5, hours:"38.0h", out:"无", outTone:"secondary", state:"已确认", tone:"success" },
      { id:3, code:"T-1011", name:"端盖 C", ops:4, hours:"21.0h", out:"含外协", outTone:"notice", state:"待复核", tone:"warning" },
      { id:4, code:"T-1014", name:"法兰 D", ops:3, hours:"12.5h", out:"无", outTone:"secondary", state:"草稿", tone:"secondary" },
    ],
  },
  personnel: {
    title: "人员管理",
    desc: "人员与班组列表：本周排班工时右对齐，技能与在岗状态以徽标呈现。",
    add: "新增人员", count: "人",
    cols: [
      { key: "code", title: "工号", nowrap: true, strong: true },
      { key: "name", title: "姓名" },
      { key: "team", title: "班组", nowrap: true },
      { key: "hours", title: "本周排班", align: "right" },
      { key: "skill", title: "主技能", nowrap: true },
      { key: "state", title: "状态", kind: "badge" },
      { key: "act", title: "操作", kind: "act" },
    ],
    rows: [
      { id:1, code:"P-021", name:"张三", team:"一班", hours:"42h", skill:"精加工", state:"接近满载", tone:"warning" },
      { id:2, code:"P-024", name:"李四", team:"一班", hours:"31h", skill:"组装", state:"有余量", tone:"success" },
      { id:3, code:"P-030", name:"王五", team:"二班", hours:"38h", skill:"检验", state:"正常", tone:"success" },
      { id:4, code:"P-033", name:"赵六", team:"二班", hours:"0h", skill:"车加工", state:"请假", tone:"danger" },
    ],
  },
  material: {
    title: "物料管理",
    desc: "物料齐套列表：齐套率右对齐着色，未齐套的批次结果不可信，需先补料。",
    add: "登记物料", count: "项",
    cols: [
      { key: "code", title: "物料号", nowrap: true, strong: true },
      { key: "name", title: "名称" },
      { key: "batch", title: "关联批次", nowrap: true },
      { key: "rate", title: "齐套率", align: "right", kind: "util" },
      { key: "state", title: "状态", kind: "badge" },
      { key: "act", title: "操作", kind: "act" },
    ],
    rows: [
      { id:1, code:"WL-2201", name:"45# 钢棒料", batch:"B202605-018", rate:100, state:"已齐套", tone:"success" },
      { id:2, code:"WL-2208", name:"铸铝件", batch:"B202605-021", rate:80, state:"待补料", tone:"warning" },
      { id:3, code:"WL-2215", name:"密封圈", batch:"B202605-017", rate:60, state:"缺料", tone:"danger" },
    ],
  },
  system: {
    title: "系统管理",
    desc: "系统操作记录：备份 / 历史 / 日志同款列表，时间与状态固定列位，便于追溯。",
    add: "立即备份", count: "条",
    cols: [
      { key: "time", title: "时间", nowrap: true, strong: true },
      { key: "type", title: "类型", nowrap: true },
      { key: "detail", title: "说明" },
      { key: "state", title: "状态", kind: "badge" },
      { key: "act", title: "操作", kind: "act" },
    ],
    rows: [
      { id:1, time:"05-23 18:40", type:"排产生成", detail:"生成 v12，覆盖 86 个批次", state:"成功", tone:"success" },
      { id:2, time:"05-23 12:00", type:"数据备份", detail:"自动备份 aps_20260523.db", state:"成功", tone:"success" },
      { id:3, time:"05-22 22:10", type:"Excel 导入", detail:"导入批次 24 条，跳过 2 条", state:"有跳过", tone:"warning" },
    ],
  },
};

function BasicDataScreen({ module = "equipment" }) {
  const { Panel, Badge } = window.APSDesignSystem_edbc5d;
  const { ControlButton: Button, TransferButton, DataTable: Table } = window.APSWorkbenchUI;
  const [q, setQ] = React.useState("");
  const m = BD_MODULES[module] || BD_MODULES.equipment;

  const D = window.APSDetail;
  const codeKey = { batches: "code", field: "batch", equipment: "code", process: "code", personnel: "code", material: "code" }[module];
  const openRow = (r) => {
    const code = codeKey ? r[codeKey] : null;
    if (code && D && D.has(code)) D.open(code);
    else if (D) D.toast((code || "该记录") + " · 明细在正式系统中按编号联动展示（示例界面）");
  };

  const cols = m.cols.map((c) => ({
    key: c.key, title: c.title, align: c.align, nowrap: c.nowrap,
    render: (r) => {
      if (c.strong) {
        if (D && D.has(r[c.key])) return <a href="#" onClick={(e) => { e.preventDefault(); D.open(r[c.key]); }} style={{ color: "var(--ui-primary)", fontWeight: 700, fontVariantNumeric: "tabular-nums", textDecoration: "none" }}>{r[c.key]}</a>;
        return <strong>{r[c.key]}</strong>;
      }
      if (c.kind === "util") {
        const v = r[c.key];
        const col = v >= 90 ? "var(--ui-danger-text)" : v >= 75 ? "var(--ui-warning-text)" : v < 75 && v > 0 ? "var(--ui-text)" : "var(--ui-danger-text)";
        return <span style={{ color: v === 0 ? "var(--ui-danger-text)" : col, fontVariantNumeric: "tabular-nums" }}>{v}%</span>;
      }
      if (c.kind === "badge") return <Badge tone={r.tone} dot>{r[c.key]}</Badge>;
      if (c.kind === "badge2") return <Badge tone={r.tone}>{r[c.key]}</Badge>;
      if (c.key === "out") return <Badge tone={r.outTone}>{r.out}</Badge>;
      if (c.kind === "act") return <a href="#" onClick={(e) => { e.preventDefault(); openRow(r); }} style={{ color: "var(--ui-primary)", fontSize: 13 }}>详情</a>;
      return r[c.key];
    },
  }));
  const rows = m.rows.filter((r) => !q || Object.values(r).join("").toLowerCase().includes(q.toLowerCase()));

  return (
    <Panel
      className="wb-page-panel"
      title={m.title}
      description={m.desc}
      headerRight={<div className="wb-actions">
        <TransferButton kind="import" onClick={() => D && D.toast("批量导入 " + m.title + " · 示例操作")}>导入 Excel</TransferButton>
        {module === "field"
          ? <TransferButton kind="import" variant="primary" onClick={() => D && D.toast(m.add + " · 示例操作（演示界面）")}>{m.add}</TransferButton>
          : <Button variant="primary" size="sm" onClick={() => D && D.toast(m.add + " · 示例操作（演示界面）")}>{m.add}</Button>}
      </div>}
    >
      <div className="table-tools">
        <input className="tool-input" placeholder="搜索…" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="tool-right">
          <Badge tone="secondary">共 {m.rows.length} {m.count}</Badge>
        </div>
      </div>
      <Table columns={cols} rows={rows} rowKey="id" />
    </Panel>
  );
}

window.BasicDataScreen = BasicDataScreen;
