// APS Workbench · 基础资料 page shell — 结构切换（链式 / 平铺）+ 一级/二级 tab
// 两版对比：
//  · 链式（按产能链，整体描述主线）：工艺 · 物料 · 自制 · 外协 · 工作日历
//      自制 → 自制工种 / 设备 / 人员    外协 → 外协工种 / 供应商
//  · 平铺（按设计图/仓库）：工艺 · 物料 · 设备 · 人员 · 工作日历
//      工艺 → 零件工艺模板 / 工种配置 / 供应商配置
// URL 参数(?struct=&tab=&sub=) + 位置记忆(localStorage) + aria-current。本页不挂计划上下文胶囊。
(function () {
  const { useState, useEffect } = React;
  const B = () => window.BD;

  const CHAIN_TABS = [
    { id: "process", label: "工艺" },
    { id: "material", label: "物料" },
    { id: "internal", label: "自制", chain: "internal" },
    { id: "external", label: "外协", chain: "external" },
    { id: "calendar", label: "工作日历" },
  ];
  const FLAT_TABS = [
    { id: "process", label: "工艺" },
    { id: "material", label: "物料" },
    { id: "equipment", label: "设备" },
    { id: "personnel", label: "人员" },
    { id: "calendar", label: "工作日历" },
  ];
  const DEFAULT_SUB = { material: "materials", internal: "optype", external: "optype", process: "parts" };

  function readInit() {
    let struct = "chain", tab = "process";
    const subs = { ...DEFAULT_SUB };
    try {
      const qs = new URLSearchParams(window.location.search);
      struct = qs.get("struct") || localStorage.getItem("aps_bd_struct") || "chain";
      tab = qs.get("bdtab") || localStorage.getItem("aps_bd_tab") || "process";
      const savedSubs = JSON.parse(localStorage.getItem("aps_bd_subs") || "{}");
      Object.assign(subs, savedSubs);
      const urlSub = qs.get("bdsub");
      if (urlSub) subs[tab] = urlSub;
    } catch (e) {}
    if (struct !== "chain" && struct !== "flat") struct = "chain";
    const valid = (struct === "chain" ? CHAIN_TABS : FLAT_TABS).map((t) => t.id);
    if (valid.indexOf(tab) < 0) tab = "process";
    return { struct, tab, subs };
  }

  function BaseDataScreen({ onNav }) {
    const init = readInit();
    const [struct, setStruct] = useState(init.struct);
    const [tab, setTab] = useState(init.tab);
    const [subs, setSubs] = useState(init.subs);
    const [flash, showFlash, clear] = B().useFlash();

    const TABS = struct === "chain" ? CHAIN_TABS : FLAT_TABS;

    useEffect(() => {
      try {
        const qs = new URLSearchParams(window.location.search);
        qs.set("struct", struct);
        qs.set("bdtab", tab);
        if (subs[tab]) qs.set("bdsub", subs[tab]); else qs.delete("bdsub");
        window.history.replaceState(null, "", window.location.pathname + "?" + qs.toString());
        localStorage.setItem("aps_bd_struct", struct);
        localStorage.setItem("aps_bd_tab", tab);
        localStorage.setItem("aps_bd_subs", JSON.stringify(subs));
      } catch (e) {}
    }, [struct, tab, subs]);

    const changeStruct = (s) => {
      clear();
      setStruct(s);
      const valid = (s === "chain" ? CHAIN_TABS : FLAT_TABS).map((t) => t.id);
      if (valid.indexOf(tab) < 0) setTab("process");
      window.scrollTo({ top: 0 });
    };
    const changeTab = (t) => { clear(); setTab(t); window.scrollTo({ top: 0 }); };
    const setSub = (t, v) => { clear(); setSubs((s) => ({ ...s, [t]: v })); };

    const { PrimaryTabs, Seg, Flash } = B();

    return (
      <div>
        <section className="bd-intro" data-screen-label="基础资料">
          <div className="dash-head" style={{ marginBottom: 8 }}>
            <div>
              <div className="eyebrow">数据准备</div>
              <h3 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>基础资料</h3>
            </div>
            <p className="dash-note" style={{ maxWidth: 360 }}>排产前要备好的基础输入资料集中在这里维护。<strong style={{ color: "var(--ui-text)" }}>本页与具体排产版本无关</strong>，不挂计划上下文。</p>
          </div>
          <p className="bd-purpose">工序的<strong>归属</strong>在「工艺」里产生：<strong>自制</strong>工序走自制链（工时口径 → 工种 / 设备 / 人员），<strong>外协</strong>工序走外协链（周期口径 → 工种 / 供应商）。两条链资源与计量口径不同。</p>

          <div className="bd-structure-bar">
            <div className="sb-label">
              <strong>信息架构（两版对比）</strong>：
              {struct === "chain"
                ? "按产能链分顶层（整体描述主线）—— 工种/供应商/设备/人员按自制 · 外协两条链归集。"
                : "按设计图平铺 —— 工艺下挂「零件工艺模板 / 工种配置 / 供应商配置」，设备、人员各自独立。"}
            </div>
            <div className="sb-controls">
              <Seg options={[{ value: "chain", label: "链式（自制/外协）" }, { value: "flat", label: "平铺（设计图版）" }]} value={struct} onChange={changeStruct} ariaLabel="切换信息架构" />
            </div>
          </div>

          <PrimaryTabs tabs={TABS} value={tab} onChange={changeTab} />
        </section>

        <div style={{ marginTop: 20 }}>
          <Flash flash={flash} />
          {tab === "process" && struct === "chain" ? <ProcessTab flashFn={showFlash} /> : null}
          {tab === "process" && struct === "flat" ? <FlatProcess sub={subs.process} onSub={(v) => setSub("process", v)} flashFn={showFlash} /> : null}
          {tab === "material" ? <MaterialTab sub={subs.material} onSub={(v) => setSub("material", v)} flashFn={showFlash} /> : null}
          {tab === "internal" ? <ChainTab kind="internal" sub={subs.internal} onSub={(v) => setSub("internal", v)} flashFn={showFlash} /> : null}
          {tab === "external" ? <ChainTab kind="external" sub={subs.external} onSub={(v) => setSub("external", v)} flashFn={showFlash} /> : null}
          {tab === "equipment" ? <EquipmentModule flashFn={showFlash} /> : null}
          {tab === "personnel" ? <PersonnelModule flashFn={showFlash} /> : null}
          {tab === "calendar" ? <CalendarTab flashFn={showFlash} onNav={onNav} /> : null}
        </div>
      </div>
    );
  }

  /* ---------- 链式：自制 / 外协 二级 tab ---------- */
  function ChainTab({ kind, sub, onSub, flashFn }) {
    const { SubTabs } = B();
    const internal = kind === "internal";
    const tabs = internal
      ? [{ id: "optype", label: "自制工种" }, { id: "equipment", label: "设备" }, { id: "personnel", label: "人员" }]
      : [{ id: "optype", label: "外协工种" }, { id: "supplier", label: "供应商" }];
    const valid = tabs.map((t) => t.id);
    const active = valid.indexOf(sub) >= 0 ? sub : "optype";

    const note = internal
      ? <>自制链计量口径 = <strong>工时（换型 + 单件小时）</strong>。工序(自制) → 自制工种 → 设备（绑 1 个工种）+ 人员（多技能矩阵）。</>
      : <>外协链计量口径 = <strong>周期（天）</strong>。工序(外协) → 外协工种 → 连续外协工序组 → 供应商（绑外协工种，给默认周期）。</>;

    return (
      <div>
        <div className={"bd-chain-note tone-" + kind}><span className="cn-bar" /><span>{note}</span></div>
        <SubTabs tabs={tabs} value={active} onChange={onSub} />
        {active === "optype" ? <OpTypesModule scope={kind} flashFn={flashFn} /> : null}
        {active === "equipment" ? <EquipmentModule flashFn={flashFn} /> : null}
        {active === "personnel" ? <PersonnelModule flashFn={flashFn} /> : null}
        {active === "supplier" ? <SuppliersModule flashFn={flashFn} /> : null}
      </div>
    );
  }

  /* ---------- 平铺：工艺 = 零件工艺模板 / 工种配置 / 供应商配置 ---------- */
  function FlatProcess({ sub, onSub, flashFn }) {
    const { SubTabs } = B();
    const tabs = [{ id: "parts", label: "零件工艺模板" }, { id: "optype", label: "工种配置" }, { id: "supplier", label: "供应商配置" }];
    const valid = tabs.map((t) => t.id);
    const active = valid.indexOf(sub) >= 0 ? sub : "parts";
    return (
      <div>
        <SubTabs tabs={tabs} value={active} onChange={onSub} />
        {active === "parts" ? <ProcessTab flashFn={flashFn} /> : null}
        {active === "optype" ? <OpTypesModule scope="all" flashFn={flashFn} /> : null}
        {active === "supplier" ? <SuppliersModule flashFn={flashFn} /> : null}
      </div>
    );
  }

  window.BaseDataScreen = BaseDataScreen;
})();
