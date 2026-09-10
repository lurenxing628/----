/* @ds-bundle: {"format":3,"namespace":"APSDesignSystem_edbc5d","components":[{"name":"GanttBar","sourcePath":"components/data/GanttBar.jsx"},{"name":"Kpi","sourcePath":"components/data/Kpi.jsx"},{"name":"RiskCard","sourcePath":"components/data/RiskCard.jsx"},{"name":"Table","sourcePath":"components/data/Table.jsx"},{"name":"Badge","sourcePath":"components/feedback/Badge.jsx"},{"name":"HeroCard","sourcePath":"components/feedback/HeroCard.jsx"},{"name":"Meter","sourcePath":"components/feedback/Meter.jsx"},{"name":"Button","sourcePath":"components/forms/Button.jsx"},{"name":"Panel","sourcePath":"components/layout/Panel.jsx"}],"sourceHashes":{"components/data/GanttBar.jsx":"af711d331b8d","components/data/Kpi.jsx":"0796b335f776","components/data/RiskCard.jsx":"34688ea34c16","components/data/Table.jsx":"b8ce21fa6e56","components/feedback/Badge.jsx":"95babf8d351f","components/feedback/HeroCard.jsx":"06925f21eadd","components/feedback/Meter.jsx":"cfa39fef90ce","components/forms/Button.jsx":"ef1606117249","components/layout/Panel.jsx":"0eafe1237899","ui_kits/workbench/AnalysisScreen.jsx":"b236d4ef1a07","ui_kits/workbench/AppShell.jsx":"aaf62b6d8b17","ui_kits/workbench/BaseBatches.jsx":"e5e226d5b0ec","ui_kits/workbench/BaseCalendar.jsx":"0c0fa4bfe5e8","ui_kits/workbench/BaseDataScreen.jsx":"7c9bcac0744d","ui_kits/workbench/BaseEquipment.jsx":"b8fc4a35f2cb","ui_kits/workbench/BaseMaterial.jsx":"4d3e6fee4724","ui_kits/workbench/BaseOpTypes.jsx":"d44aa1564e3e","ui_kits/workbench/BasePersonnel.jsx":"a3b49cf25e4b","ui_kits/workbench/BaseProcess.jsx":"eeb553c994b2","ui_kits/workbench/BaseShared.jsx":"0c9635e793ce","ui_kits/workbench/BaseSuppliers.jsx":"bb93fa8f2092","ui_kits/workbench/BasicDataScreen.jsx":"46f07a6e11f4","ui_kits/workbench/CalibScreen.jsx":"19caf188e9be","ui_kits/workbench/DashboardScreen.jsx":"2f6c2a44c34e","ui_kits/workbench/DelayScreen.jsx":"d18768c872ac","ui_kits/workbench/FieldGanttScreen.jsx":"13f4ceb0f56e","ui_kits/workbench/FieldRecordScreen.jsx":"c6ae98b21a31","ui_kits/workbench/GanttBoard.jsx":"907fe47e5aa3","ui_kits/workbench/GanttScreen.jsx":"ee08dea830d7","ui_kits/workbench/ProcessNative.jsx":"c7795d4e1c7a","ui_kits/workbench/ReportsScreen.jsx":"7cc88ed4facd","ui_kits/workbench/app.jsx":"50a295bfa716","ui_kits/workbench/datepicker/aps-datepicker.js":"233eb63c42b7","ui_kits/workbench/detail-drawer.js":"7aa377f2227a","ui_kits/workbench/plana-logic.js":"3da27bb14554","ui_kits/workbench/table-enhance.js":"7975209c4f0b"},"inlinedExternals":[],"unexposedExports":[{"name":"injectTableToolsCSS","sourcePath":"components/data/Table.jsx"}]} */

(() => {

const __ds_ns = (window.APSDesignSystem_edbc5d = window.APSDesignSystem_edbc5d || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/data/GanttBar.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * APS GanttBar — a scheduling bar matching the product's frappe-gantt
 * visuals: a near-rectangular fill (4px radius), thin slate stroke, and
 * a white label with a dark halo. Status drives the fill from the gantt
 * palette; `overdue` adds the heavy red stroke; `external` makes the
 * border dashed; `critical` adds the gold key-chain outline; `dim` fades
 * non-focused bars during 沿链巡检.
 *
 * Position inside a relative lane with `left` / `width` (CSS lengths).
 */
const FILL = {
  normal: "var(--gantt-normal)",
  urgent: "var(--gantt-urgent)",
  critical: "var(--gantt-critical)",
  success: "var(--ui-success)",
  primary: "var(--ui-primary)"
};
function GanttBar({
  status = "normal",
  left = "0%",
  width = "20%",
  top = 10,
  overdue = false,
  external = false,
  critical = false,
  dim = false,
  children,
  style = {},
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    title: typeof children === "string" ? children : undefined,
    style: {
      position: "absolute",
      left,
      width,
      top,
      height: 30,
      borderRadius: 4,
      padding: "0 10px",
      display: "flex",
      alignItems: "center",
      background: FILL[status] || FILL.normal,
      color: "#fff",
      fontFamily: "var(--font-family)",
      fontSize: 12,
      fontWeight: 500,
      lineHeight: 1,
      whiteSpace: "nowrap",
      overflow: "hidden",
      textOverflow: "ellipsis",
      border: external ? "1.5px dashed rgba(15,23,42,0.45)" : "1px solid rgba(15,23,42,0.16)",
      boxShadow: overdue ? "inset 0 0 0 2px var(--gantt-critical)" : "none",
      outline: critical ? "2px solid #d4a017" : "none",
      outlineOffset: critical ? "1px" : 0,
      opacity: dim ? 0.4 : 1,
      textShadow: "0 1px 1px rgba(15,23,42,0.45)",
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { GanttBar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/GanttBar.jsx", error: String((e && e.message) || e) }); }

// components/data/Kpi.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * APS Kpi — a compact metric tile for non-severity numbers (totals,
 * rates). Muted label, 28px BOLD (700) tabular numeral — the same
 * callout-numeral weight the 值班台 risk grid uses, so KPI figures sit
 * in one numeric language with the dashboard. Optional helper + trailing
 * badge. Flat card, no sparkline, no gradient.
 */
function Kpi({
  label,
  value,
  helper,
  badge = null,
  valueColor = "var(--ui-text)",
  style = {},
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6,
      padding: "16px",
      border: "1px solid var(--ui-border)",
      borderRadius: 6,
      background: "var(--ui-card-bg)",
      boxShadow: "var(--ui-shadow-sm)",
      fontFamily: "var(--font-family)",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 13,
      color: "var(--ui-muted)"
    }
  }, label), badge), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 28,
      fontWeight: 700,
      lineHeight: 1.2,
      color: valueColor,
      fontVariantNumeric: "tabular-nums"
    }
  }, value), helper ? /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "var(--ui-muted)",
      lineHeight: 1.5
    }
  }, helper) : null);
}
Object.assign(__ds_scope, { Kpi });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/Kpi.jsx", error: String((e && e.message) || e) }); }

// components/data/RiskCard.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * APS RiskCard — one cell of the dashboard health-check grid.
 * Flush-left stack (layout "B1"): a muted label sits at the top-left, the
 * big tabular number + an optional unit (个/项/道…) reads directly beneath
 * it, and the helper is pinned to the foot — all three sharing one left
 * edge so the column scans cleanly. The number leads the hierarchy by size
 * and colour; the unit nudges the visual weight off the hard-left. A left
 * 4px severity bar (ok/notice/warning/danger) carries the status; an
 * optional nav chip sits top-right.
 *
 * Hover = soft shadow-lift; the brand ring is reserved for real
 * :focus-visible (keyboard), drawn with the severity bar still on top.
 */
const SEV = {
  ok: "var(--ui-success)",
  notice: "var(--ui-primary)",
  warning: "var(--ui-warning)",
  danger: "var(--ui-danger)"
};
const VAL = {
  ok: "var(--ui-success)",
  notice: "var(--ui-primary)",
  warning: "var(--ui-warning)",
  danger: "var(--ui-danger)"
};
function RiskCard({
  severity = "ok",
  label,
  value,
  unit,
  helper,
  href,
  disabled = false,
  style = {},
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const [keyFocus, setKeyFocus] = React.useState(false);
  const interactive = !!href && !disabled;
  const bar = SEV[severity] || SEV.ok;
  const raised = interactive && (hover || keyFocus);
  const boxShadow = keyFocus ? "var(--ui-focus-ring)" : raised ? "var(--ui-shadow-md)" : "var(--ui-shadow-sm)";
  const base = {
    display: "flex",
    flexDirection: "column",
    minHeight: 140,
    padding: "15px 18px",
    border: "1px solid var(--ui-border)",
    borderLeft: `4px solid ${bar}`,
    borderRadius: 8,
    background: raised ? "var(--ui-surface-raised)" : "var(--ui-surface-muted)",
    color: "var(--ui-text)",
    textDecoration: "none",
    fontFamily: "var(--font-family)",
    cursor: interactive ? "pointer" : "default",
    opacity: disabled ? 0.7 : 1,
    outline: "none",
    boxShadow,
    transform: raised ? "translateY(-1px)" : "none",
    transition: "box-shadow .15s ease, transform .15s ease, background-color .15s ease"
  };
  const inner = /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12.5,
      fontWeight: 600,
      color: "var(--ui-muted)",
      letterSpacing: "0.02em"
    }
  }, label), interactive ? /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      flex: "none",
      width: 22,
      height: 22,
      borderRadius: 6,
      display: "grid",
      placeItems: "center",
      fontSize: 13,
      lineHeight: 1,
      color: raised ? "#fff" : "var(--ui-muted)",
      background: raised ? "var(--ui-primary)" : "var(--ui-surface-soft)",
      transform: raised ? "translateX(1px)" : "none",
      transition: "color .15s ease, background-color .15s ease, transform .15s ease"
    }
  }, "\u2192") : null), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 12,
      display: "flex",
      alignItems: "baseline"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 36,
      fontWeight: 700,
      color: VAL[severity] || "var(--ui-text)",
      fontVariantNumeric: "tabular-nums",
      lineHeight: 1
    }
  }, value), unit ? /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 5,
      fontSize: 14,
      fontWeight: 600,
      color: "var(--ui-muted)"
    }
  }, unit) : null), helper ? /*#__PURE__*/React.createElement("span", {
    style: {
      marginTop: "auto",
      paddingTop: 12,
      fontSize: 12,
      color: "var(--ui-muted)",
      lineHeight: 1.55,
      textWrap: "pretty"
    }
  }, helper) : null);
  if (interactive) {
    return /*#__PURE__*/React.createElement("a", _extends({
      href: href,
      style: base,
      onMouseEnter: () => setHover(true),
      onMouseLeave: () => setHover(false),
      onFocus: e => {
        try {
          if (e.currentTarget.matches(":focus-visible")) setKeyFocus(true);
        } catch (_) {
          setKeyFocus(true);
        }
      },
      onBlur: () => setKeyFocus(false)
    }, rest), inner);
  }
  return /*#__PURE__*/React.createElement("div", _extends({
    style: base,
    "aria-disabled": disabled || undefined
  }, rest), inner);
}
Object.assign(__ds_scope, { RiskCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/RiskCard.jsx", error: String((e && e.message) || e) }); }

// components/data/Table.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * APS Table — the modernized data table. Light head (#f8fafc, slate
 * head text), 10/12px cells, hairline rows, row hover, even-row zebra.
 * Numeric columns right-align with tabular figures (认知原则 ⑤). A column
 * may render a cell via `render(row)` — e.g. returning a <Badge>.
 *
 * Interactive by default (style unchanged): click a header to sort
 * (asc → desc → off), hover a header for the funnel to filter that
 * column, drag a column's right edge to resize. Per-column opt-out via
 * `sortable:false` / `filterable:false`; supply `sortValue(row)` /
 * `filterValue(row)` for columns whose cells render custom nodes.
 *
 * columns: [{ key, title, align?, width?, nowrap?, render?,
 *             sortable?, filterable?, sortValue?, filterValue?, filterFacets? }]
 *
 * A column that is visually two-in-one (e.g. “计划 开工 → 完工”) can
 * declare `filterFacets: [{ key, label, value(row) }]` — the funnel then
 * offers a tab per facet, each an independent checkbox filter (AND across
 * facets). `sortValue(row)` still drives the single sort order.
 */

const CSS_ID = "aps-rtable-tools-css";
const TABLE_TOOLS_CSS = `
.aps-th { position: relative; }
.aps-th-inner { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; }
.aps-th-sortable { cursor: pointer; }
.aps-th-label { overflow: hidden; text-overflow: ellipsis; }
.aps-sortglyph { display:inline-block; width:7px; height:13px; position:relative; flex:none; color:currentColor; opacity:.3; transition:opacity .12s; }
.aps-sortglyph::before, .aps-sortglyph::after { content:''; position:absolute; left:0; border-left:3.5px solid transparent; border-right:3.5px solid transparent; }
.aps-sortglyph::before { top:2px; border-bottom:4px solid currentColor; }
.aps-sortglyph::after { bottom:2px; border-top:4px solid currentColor; }
.aps-th:hover .aps-sortglyph { opacity:.55; }
.aps-sortglyph.asc, .aps-sortglyph.desc { opacity:1; }
.aps-sortglyph.asc::after { opacity:.2; }
.aps-sortglyph.desc::before { opacity:.2; }
.aps-filter-btn { display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px; border:0; background:transparent; border-radius:4px; cursor:pointer; color:inherit; opacity:0; padding:0; flex:none; transition:opacity .12s, background-color .12s, color .12s; }
.aps-th:hover .aps-filter-btn { opacity:.55; }
.aps-filter-btn:hover { background: var(--ui-surface-muted); opacity:1; }
.aps-filter-btn.on { opacity:1; color: var(--ui-primary); background: var(--ui-primary-soft); }
.aps-th-resize { position:absolute; top:0; right:0; height:100%; width:10px; cursor:col-resize; user-select:none; touch-action:none; z-index:4; }
.aps-th-resize::after { content:''; position:absolute; right:3px; top:22%; height:56%; width:2px; border-radius:2px; background:transparent; transition:background-color .12s; }
.aps-th-resize:hover::after, .aps-th-resize.dragging::after { background: var(--ui-primary); }
.aps-filter-pop { position:fixed; z-index:9999; background: var(--ui-card-bg); border:1px solid var(--ui-border); border-radius:8px; box-shadow: var(--ui-shadow-md); padding:8px; width:206px; box-sizing:border-box; }
.aps-filter-pop input { width:100%; height:32px; padding:0 10px; border:1px solid var(--ui-border); border-radius:6px; background: var(--ui-card-bg); font-family:inherit; font-size:13px; color: var(--ui-text); box-sizing:border-box; }
.aps-filter-pop input:focus { outline:none; border-color: var(--ui-primary); box-shadow: var(--ui-focus-ring); }
.aps-fp-foot { display:flex; justify-content:space-between; align-items:center; margin-top:7px; }
.aps-fp-clear { border:0; background:transparent; color: var(--ui-muted); font-size:12px; cursor:pointer; font-family:inherit; padding:2px 4px; border-radius:4px; }
.aps-fp-clear:hover { color: var(--ui-text); background: var(--ui-surface-muted); }
.aps-fp-count { font-size:11.5px; color: var(--ui-muted); font-variant-numeric:tabular-nums; }
.aps-filter-pop input[type="checkbox"] { width:15px; height:15px; flex:none; margin:0; padding:0; accent-color: var(--ui-primary); cursor:pointer; }
.aps-fp-list { max-height:220px; overflow:auto; margin-top:7px; display:flex; flex-direction:column; gap:1px; border-top:1px solid var(--ui-border); padding-top:6px; }
.aps-fp-opt { display:flex; align-items:center; gap:8px; padding:5px 6px; border-radius:5px; cursor:pointer; font-size:13px; color:var(--ui-text); user-select:none; }
.aps-fp-opt:hover { background: var(--ui-surface-muted); }
.aps-fp-opt-label { flex:1 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.aps-fp-opt-count { flex:none; color: var(--ui-muted); font-size:11.5px; font-variant-numeric:tabular-nums; }
.aps-fp-all { font-weight:600; border-bottom:1px solid var(--ui-border); border-radius:0; margin-bottom:2px; padding-bottom:7px; }
.aps-fp-empty { padding:14px 6px; text-align:center; color: var(--ui-muted); font-size:12px; }
.aps-fp-tabs { display:flex; gap:2px; padding:2px; margin-bottom:8px; background: var(--ui-surface-soft); border-radius:7px; }
.aps-fp-tab { flex:1 1 0; min-width:0; display:inline-flex; align-items:center; justify-content:center; gap:5px; height:26px; padding:0 8px; border:0; border-radius:5px; background:transparent; color: var(--ui-muted); font-family:inherit; font-size:12.5px; font-weight:600; cursor:pointer; transition:background-color .12s, color .12s, box-shadow .12s; }
.aps-fp-tab:hover { color: var(--ui-text); }
.aps-fp-tab.on { background: var(--ui-card-bg); color: var(--ui-text); box-shadow: var(--ui-shadow-sm); }
.aps-fp-tab-dot { width:5px; height:5px; border-radius:50%; background: var(--ui-primary); flex:none; }
.aps-sort-facets { display:inline-flex; align-items:center; gap:3px; flex:none; }
.aps-sort-facetbtn { display:inline-flex; align-items:center; gap:3px; height:18px; padding:0 7px; border:1px solid var(--ui-border); border-radius:4px; background: var(--ui-card-bg); color: var(--ui-muted); font-family:inherit; font-size:10.5px; font-weight:600; line-height:1; letter-spacing:.02em; cursor:pointer; opacity:0; transition:background-color .12s, color .12s, border-color .12s, opacity .12s; }
.aps-th:hover .aps-sort-facetbtn { opacity:1; }
.aps-sort-facetbtn:hover { color: var(--ui-text); border-color: var(--ui-primary); }
.aps-sort-facetbtn.on { opacity:1; background: var(--ui-primary-soft); color: var(--ui-primary); border-color: var(--ui-primary); }
.aps-sort-facetarrow { font-size:9px; line-height:1; }
`;
function injectTableToolsCSS() {
  if (typeof document === "undefined" || document.getElementById(CSS_ID)) return;
  const el = document.createElement("style");
  el.id = CSS_ID;
  el.textContent = TABLE_TOOLS_CSS;
  document.head.appendChild(el);
}
const FUNNEL = /*#__PURE__*/React.createElement("svg", {
  width: "13",
  height: "13",
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: "2.2",
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": "true"
}, /*#__PURE__*/React.createElement("path", {
  d: "M3 5h18l-7 8v5l-4 2v-7z"
}));
function rawOf(col, row) {
  return col.sortValue ? col.sortValue(row) : row[col.key];
}
function textOf(col, row) {
  const v = col.filterValue ? col.filterValue(row) : row[col.key];
  return v == null ? "" : String(v);
}
function cmpVals(a, b) {
  if (typeof a === "number" && typeof b === "number") return a - b;
  const sa = a == null ? "" : String(a);
  const sb = b == null ? "" : String(b);
  return sa.localeCompare(sb, "zh-Hans-CN", {
    numeric: true,
    sensitivity: "base"
  });
}
function Table({
  columns = [],
  rows = [],
  rowKey = "id",
  style = {},
  ...rest
}) {
  React.useEffect(injectTableToolsCSS, []);
  const [sort, setSort] = React.useState(null); // { key, dir: "asc"|"desc" }
  const [filters, setFilters] = React.useState({}); // { key: string[] } selected values — absent = all shown
  const [widths, setWidths] = React.useState({}); // { key: px }
  const [openFilter, setOpenFilter] = React.useState(null); // key
  const [popPos, setPopPos] = React.useState(null); // {left, top}

  const meta = React.useMemo(() => columns.map(c => {
    const hasData = rows.some(r => {
      const v = r[c.key];
      return v != null && typeof v !== "object";
    });
    const declaredFacets = c.filterFacets && c.filterFacets.length ? c.filterFacets : null;
    const declaredSortFacets = c.sortFacets && c.sortFacets.length ? c.sortFacets : null;
    const filterable = c.filterable != null ? c.filterable : hasData || !!c.filterValue || !!declaredFacets;
    let facets = null;
    if (filterable) {
      facets = declaredFacets ? declaredFacets.map(f => ({
        fkey: c.key + "::" + f.key,
        label: f.label,
        value: row => {
          const v = f.value ? f.value(row) : row[f.key];
          return v == null ? "" : String(v);
        }
      })) : [{
        fkey: c.key,
        label: typeof c.title === "string" ? c.title : "本列",
        value: row => textOf(c, row)
      }];
    }
    const sortFacets = declaredSortFacets ? declaredSortFacets.map(f => ({
      skey: c.key + "::" + f.key,
      label: f.label,
      value: row => f.value ? f.value(row) : row[f.key]
    })) : null;
    return {
      ...c,
      _sortable: c.sortable != null ? c.sortable : hasData || !!c.sortValue || !!sortFacets,
      _sortFacets: sortFacets,
      _filterable: !!facets,
      _facets: facets
    };
  }), [columns, rows]);

  // facet lookup by its unique key
  const facetByKey = React.useMemo(() => {
    const m = {};
    meta.forEach(c => c._facets && c._facets.forEach(f => m[f.fkey] = f));
    return m;
  }, [meta]);

  // distinct values per facet (for the Excel-style checkbox filter)
  const distinct = React.useMemo(() => {
    const out = {};
    meta.forEach(c => {
      if (!c._facets) return;
      c._facets.forEach(f => {
        const m = new Map();
        rows.forEach(r => {
          const t = f.value(r);
          m.set(t, (m.get(t) || 0) + 1);
        });
        out[f.fkey] = [...m.entries()].map(([value, count]) => ({
          value,
          count
        })).sort((a, b) => cmpVals(a.value, b.value));
      });
    });
    return out;
  }, [meta, rows]);

  // ---- derive view (filter then sort) ----
  let view = rows;
  const active = Object.entries(filters).filter(([, arr]) => Array.isArray(arr));
  if (active.length) {
    view = view.filter(row => active.every(([fk, arr]) => {
      const f = facetByKey[fk];
      return f ? arr.indexOf(f.value(row)) !== -1 : true;
    }));
  }
  if (sort) {
    const col = meta.find(c => c.key === sort.key);
    if (col) {
      const sf = col._sortFacets && col._sortFacets[sort.sfi || 0];
      const valOf = sf ? row => sf.value(row) : row => rawOf(col, row);
      view = [...view].sort((ra, rb) => cmpVals(valOf(ra), valOf(rb)));
      if (sort.dir === "desc") view.reverse();
    }
  }
  function toggleSort(key) {
    const col = meta.find(c => c.key === key);
    const facets = col && col._sortFacets;
    setSort(s => {
      // Facet columns cycle: f0 asc → f0 desc → f1 asc → … → off
      if (facets && facets.length > 1) {
        if (!s || s.key !== key) return {
          key,
          sfi: 0,
          dir: "asc"
        };
        if (s.dir === "asc") return {
          key,
          sfi: s.sfi,
          dir: "desc"
        };
        if (s.sfi < facets.length - 1) return {
          key,
          sfi: s.sfi + 1,
          dir: "asc"
        };
        return null;
      }
      if (!s || s.key !== key) return {
        key,
        sfi: 0,
        dir: "asc"
      };
      if (s.dir === "asc") return {
        key,
        sfi: 0,
        dir: "desc"
      };
      return null;
    });
  }

  // Facet sort buttons (开工 / 完工): each is an independent sort toggle —
  // first click sorts asc by that sub-field, second desc, third clears.
  function toggleSortFacet(key, sfi) {
    setSort(s => {
      if (!s || s.key !== key || (s.sfi || 0) !== sfi) return {
        key,
        sfi,
        dir: "asc"
      };
      if (s.dir === "asc") return {
        key,
        sfi,
        dir: "desc"
      };
      return null;
    });
  }
  function openFilterAt(e, key) {
    e.stopPropagation();
    if (openFilter === key) {
      setOpenFilter(null);
      return;
    }
    const r = e.currentTarget.getBoundingClientRect();
    let left = r.left;
    const w = 240;
    if (left + w > window.innerWidth - 8) left = window.innerWidth - 8 - w;
    setPopPos({
      left: Math.max(8, left),
      top: r.bottom + 6
    });
    setOpenFilter(key);
  }
  function startResize(e, key) {
    e.preventDefault();
    e.stopPropagation();
    const handle = e.currentTarget;
    const th = handle.closest("th");
    const startX = e.clientX;
    const startW = th.getBoundingClientRect().width;
    handle.classList.add("dragging");
    const move = ev => {
      const w = Math.max(56, Math.round(startW + ev.clientX - startX));
      setWidths(prev => ({
        ...prev,
        [key]: w
      }));
    };
    const up = () => {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
      handle.classList.remove("dragging");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }

  // close filter popover on outside click / Escape
  React.useEffect(() => {
    if (!openFilter) return undefined;
    const onDown = e => {
      if (!e.target.closest("[data-aps-fpop]") && !e.target.closest("[data-aps-fbtn]")) setOpenFilter(null);
    };
    const onKey = e => {
      if (e.key === "Escape") setOpenFilter(null);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [openFilter]);
  const activeCol = openFilter ? meta.find(c => c.key === openFilter) : null;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      overflow: "auto",
      border: "1px solid var(--ui-border)",
      borderRadius: 8,
      background: "var(--ui-card-bg)"
    }
  }, /*#__PURE__*/React.createElement("table", _extends({
    "data-aps-rtable": "1",
    style: {
      width: "100%",
      borderCollapse: "collapse",
      fontFamily: "var(--font-family)",
      fontSize: 14,
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, meta.map(c => {
    const w = widths[c.key] != null ? widths[c.key] : c.width;
    const pinned = widths[c.key] != null;
    const justify = c.align === "right" ? "flex-end" : c.align === "center" ? "center" : "flex-start";
    const sorted = sort && sort.key === c.key ? sort.dir : null;
    const facetSort = c._sortable && c._sortFacets;
    const plainSortable = c._sortable && !facetSort;
    const hasFilter = c._facets && c._facets.some(f => Array.isArray(filters[f.fkey]));
    return /*#__PURE__*/React.createElement("th", {
      key: c.key,
      className: "aps-th",
      style: {
        position: "sticky",
        top: 0,
        zIndex: 2,
        textAlign: c.align || "left",
        padding: "10px 12px",
        background: "var(--ui-table-head-bg)",
        color: "var(--ui-muted)",
        fontWeight: 600,
        fontSize: 13,
        whiteSpace: "nowrap",
        borderBottom: "1px solid var(--ui-border)",
        width: w,
        minWidth: pinned ? w : undefined,
        maxWidth: pinned ? w : undefined
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "aps-th-inner" + (plainSortable ? " aps-th-sortable" : ""),
      style: {
        justifyContent: justify,
        width: "100%"
      },
      onClick: plainSortable ? () => toggleSort(c.key) : undefined
    }, /*#__PURE__*/React.createElement("span", {
      className: "aps-th-label"
    }, c.title), facetSort ? /*#__PURE__*/React.createElement("span", {
      className: "aps-sort-facets"
    }, c._sortFacets.map((f, fi) => {
      const on = sorted && (sort.sfi || 0) === fi;
      return /*#__PURE__*/React.createElement("button", {
        type: "button",
        key: f.skey,
        className: "aps-sort-facetbtn" + (on ? " on" : ""),
        title: "按" + f.label + "排序",
        onClick: e => {
          e.stopPropagation();
          toggleSortFacet(c.key, fi);
        }
      }, f.label, on ? /*#__PURE__*/React.createElement("span", {
        className: "aps-sort-facetarrow"
      }, sort.dir === "desc" ? "↓" : "↑") : null);
    })) : null, plainSortable ? /*#__PURE__*/React.createElement("span", {
      className: "aps-sortglyph" + (sorted ? " " + sorted : "")
    }) : null, c._filterable ? /*#__PURE__*/React.createElement("button", {
      type: "button",
      "data-aps-fbtn": "1",
      className: "aps-filter-btn" + (hasFilter ? " on" : ""),
      title: "\u7B5B\u9009",
      onClick: e => openFilterAt(e, c.key)
    }, FUNNEL) : null), /*#__PURE__*/React.createElement("span", {
      className: "aps-th-resize",
      onMouseDown: e => startResize(e, c.key)
    }));
  }))), /*#__PURE__*/React.createElement("tbody", null, view.map((row, i) => /*#__PURE__*/React.createElement(Row, {
    key: row[rowKey] ?? i,
    row: row,
    columns: meta,
    even: i % 2 === 1
  })))), activeCol && popPos ? /*#__PURE__*/React.createElement(FilterPop, {
    key: activeCol.key,
    facets: activeCol._facets,
    distinctMap: distinct,
    filters: filters,
    pos: popPos,
    matches: view.length,
    onChange: (fkey, arr) => {
      const all = distinct[fkey] || [];
      setFilters(f => {
        const n = {
          ...f
        };
        if (!arr || arr.length >= all.length) delete n[fkey];else n[fkey] = arr;
        return n;
      });
    },
    onClear: () => {
      setFilters(f => {
        const n = {
          ...f
        };
        activeCol._facets.forEach(ff => delete n[ff.fkey]);
        return n;
      });
      setOpenFilter(null);
    }
  }) : null);
}
function FilterPop({
  facets,
  distinctMap,
  filters,
  pos,
  matches,
  onChange,
  onClear
}) {
  const [fi, setFi] = React.useState(0);
  const [q, setQ] = React.useState("");
  const searchRef = React.useRef(null);
  const allRef = React.useRef(null);
  const facet = facets[Math.min(fi, facets.length - 1)];
  const options = distinctMap[facet.fkey] || [];
  const selected = filters[facet.fkey];
  React.useEffect(() => {
    if (searchRef.current) searchRef.current.focus();
  }, []);
  const allValues = options.map(o => o.value);
  const checkedSet = selected ? new Set(selected) : new Set(allValues);
  const ql = q.trim().toLowerCase();
  const labelOf = v => v === "" ? "(空白)" : v;
  const shown = ql ? options.filter(o => labelOf(o.value).toLowerCase().includes(ql)) : options;
  const shownChecked = shown.filter(o => checkedSet.has(o.value)).length;
  const allOn = shown.length > 0 && shownChecked === shown.length;
  const someOn = shownChecked > 0 && shownChecked < shown.length;
  React.useEffect(() => {
    if (allRef.current) allRef.current.indeterminate = someOn;
  });
  function selectFacet(i) {
    setFi(i);
    setQ("");
  }
  function toggle(value) {
    const next = new Set(checkedSet);
    if (next.has(value)) next.delete(value);else next.add(value);
    onChange(facet.fkey, [...next]);
  }
  function toggleAll() {
    const next = new Set(checkedSet);
    if (allOn) shown.forEach(o => next.delete(o.value));else shown.forEach(o => next.add(o.value));
    onChange(facet.fkey, [...next]);
  }
  return /*#__PURE__*/React.createElement("div", {
    "data-aps-fpop": "1",
    className: "aps-filter-pop",
    style: {
      left: pos.left,
      top: pos.top
    }
  }, facets.length > 1 ? /*#__PURE__*/React.createElement("div", {
    className: "aps-fp-tabs"
  }, facets.map((f, i) => /*#__PURE__*/React.createElement("button", {
    type: "button",
    key: f.fkey,
    className: "aps-fp-tab" + (i === fi ? " on" : ""),
    onClick: () => selectFacet(i)
  }, f.label, Array.isArray(filters[f.fkey]) ? /*#__PURE__*/React.createElement("span", {
    className: "aps-fp-tab-dot"
  }) : null))) : null, /*#__PURE__*/React.createElement("input", {
    ref: searchRef,
    type: "text",
    placeholder: "搜索 " + facet.label + "…",
    value: q,
    onChange: e => setQ(e.target.value)
  }), /*#__PURE__*/React.createElement("div", {
    className: "aps-fp-list"
  }, /*#__PURE__*/React.createElement("label", {
    className: "aps-fp-opt aps-fp-all"
  }, /*#__PURE__*/React.createElement("input", {
    ref: allRef,
    type: "checkbox",
    checked: allOn,
    onChange: toggleAll
  }), /*#__PURE__*/React.createElement("span", {
    className: "aps-fp-opt-label"
  }, "(\u5168\u9009)"), /*#__PURE__*/React.createElement("span", {
    className: "aps-fp-opt-count"
  }, options.length)), shown.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "aps-fp-empty"
  }, "\u65E0\u5339\u914D\u9879") : shown.map(o => /*#__PURE__*/React.createElement("label", {
    className: "aps-fp-opt",
    key: o.value
  }, /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    checked: checkedSet.has(o.value),
    onChange: () => toggle(o.value)
  }), /*#__PURE__*/React.createElement("span", {
    className: "aps-fp-opt-label",
    title: labelOf(o.value)
  }, labelOf(o.value)), /*#__PURE__*/React.createElement("span", {
    className: "aps-fp-opt-count"
  }, o.count)))), /*#__PURE__*/React.createElement("div", {
    className: "aps-fp-foot"
  }, /*#__PURE__*/React.createElement("span", {
    className: "aps-fp-count"
  }, matches, " \u884C\u5339\u914D"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "aps-fp-clear",
    onClick: onClear
  }, "\u6E05\u9664")));
}
function Row({
  row,
  columns,
  even
}) {
  const [hover, setHover] = React.useState(false);
  const bg = hover ? "var(--ui-table-row-hover-bg)" : even ? "var(--ui-table-row-even-bg)" : "transparent";
  return /*#__PURE__*/React.createElement("tr", {
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      background: bg,
      transition: "background-color .12s ease"
    }
  }, columns.map(c => {
    const num = c.align === "right";
    return /*#__PURE__*/React.createElement("td", {
      key: c.key,
      style: {
        textAlign: c.align || "left",
        padding: "10px 12px",
        borderBottom: "1px solid var(--ui-border)",
        color: "var(--ui-text)",
        verticalAlign: "middle",
        fontVariantNumeric: num ? "tabular-nums" : "normal",
        whiteSpace: c.nowrap ? "nowrap" : "normal"
      }
    }, c.render ? c.render(row) : row[c.key]);
  }));
}
Object.assign(__ds_scope, { injectTableToolsCSS, Table });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/Table.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * APS Badge — the status pill used in table cells and inline.
 * Two channels in one chip: tinted fill + bold text, plus an optional
 * `dot` for the third (colour-blind-safe) channel. Severity tones map
 * to the four-level system: ok→success, notice→info, warning, danger.
 */
const TONES = {
  primary: {
    bg: "var(--badge-primary-bg)",
    fg: "var(--badge-primary-text)",
    dot: "var(--ui-primary)"
  },
  secondary: {
    bg: "var(--badge-secondary-bg)",
    fg: "var(--badge-secondary-text)",
    dot: "#94a3b8"
  },
  success: {
    bg: "var(--badge-success-bg)",
    fg: "var(--badge-success-text)",
    dot: "var(--ui-success)"
  },
  warning: {
    bg: "var(--badge-warning-bg)",
    fg: "var(--badge-warning-text)",
    dot: "var(--ui-warning)"
  },
  danger: {
    bg: "var(--badge-danger-bg)",
    fg: "var(--badge-danger-text)",
    dot: "var(--ui-danger)"
  },
  // severity aliases
  ok: {
    bg: "var(--badge-success-bg)",
    fg: "var(--badge-success-text)",
    dot: "var(--ui-success)"
  },
  notice: {
    bg: "var(--badge-primary-bg)",
    fg: "var(--badge-primary-text)",
    dot: "var(--ui-primary)"
  }
};
function Badge({
  tone = "secondary",
  dot = false,
  children,
  style = {},
  ...rest
}) {
  const t = TONES[tone] || TONES.secondary;
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: dot ? "0.35em" : 0,
      padding: "0.25em 0.6em",
      fontFamily: "var(--font-family)",
      fontSize: "0.75em",
      fontWeight: 700,
      lineHeight: 1,
      whiteSpace: "nowrap",
      verticalAlign: "baseline",
      borderRadius: "0.25rem",
      background: t.bg,
      color: t.fg,
      ...style
    }
  }, rest), dot ? /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      width: "0.5em",
      height: "0.5em",
      borderRadius: "50%",
      background: t.dot,
      flex: "none"
    }
  }) : null, children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Badge.jsx", error: String((e && e.message) || e) }); }

// components/feedback/HeroCard.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * APS HeroCard — the dashboard's single most-urgent command card.
 * Shares the RiskCard design language: a NEUTRAL muted surface, a thin
 * 1px border, a 4px left severity bar, an 8px radius and a soft shadow.
 * Colour is reserved for the bar, the eyebrow severity dot+label, and the
 * big call-out NUMBERS — never a filled background tint.
 *
 * Number language (matches the 7-cell risk grid): the most-urgent figure is
 * pulled out of the sentence into a large, severity-coloured, tabular numeral.
 * `lead` is the primary number on the left (largest); `anchor` is an optional
 * secondary number on the right (smaller) that supplies the "how bad" figure.
 * The whole card is vertically centred so both numbers, the narrative and the
 * actions all share one centre-of-gravity line.
 *
 * Severity has four levels: ok (green) / notice (blue) / warning / danger.
 */
const SEV = {
  ok: {
    bar: "var(--ui-success)",
    accent: "var(--ui-success)",
    word: "正常"
  },
  notice: {
    bar: "var(--ui-primary)",
    accent: "var(--ui-primary)",
    word: "提示"
  },
  warning: {
    bar: "var(--ui-warning)",
    accent: "var(--ui-warning)",
    word: "需关注"
  },
  danger: {
    bar: "var(--ui-danger)",
    accent: "var(--ui-danger)",
    word: "紧急"
  }
};
function NumberColumn({
  data,
  side,
  accent
}) {
  // side: "lead" (primary, left, flush-left) | "anchor" (secondary, right, centred)
  const isLead = side === "lead";
  const numSize = isLead ? 50 : 34;
  const unitSize = isLead ? 16 : 13;
  const numColor = data.color || accent;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      flex: "none",
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      alignItems: isLead ? "flex-start" : "center",
      textAlign: isLead ? "left" : "center",
      ...(isLead ? {
        paddingRight: 22,
        borderRight: "1px solid var(--ui-border)"
      } : {
        paddingLeft: 22,
        borderLeft: "1px solid var(--ui-border)"
      })
    }
  }, data.caption ? /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12.5,
      fontWeight: 600,
      color: "var(--ui-muted)",
      whiteSpace: "nowrap",
      minHeight: 18,
      lineHeight: "18px"
    }
  }, data.caption) : null, /*#__PURE__*/React.createElement("span", {
    style: {
      display: "flex",
      alignItems: "baseline",
      justifyContent: isLead ? "flex-start" : "center",
      marginTop: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: numSize,
      fontWeight: 700,
      color: numColor,
      fontVariantNumeric: "tabular-nums",
      lineHeight: 1
    }
  }, data.value), data.unit ? /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: unitSize,
      fontWeight: 600,
      color: "var(--ui-muted)",
      marginLeft: 6
    }
  }, data.unit) : null), data.sub ? /*#__PURE__*/React.createElement("span", {
    style: {
      marginTop: 8,
      fontSize: 12,
      color: "var(--ui-muted)",
      minHeight: 16
    }
  }, data.sub) : null);
}
function HeroCard({
  severity = "notice",
  eyebrow,
  title,
  impact,
  evidence,
  lead,
  anchor,
  actions = null,
  style = {},
  ...rest
}) {
  const s = SEV[severity] || SEV.notice;
  return /*#__PURE__*/React.createElement("section", _extends({
    style: {
      display: "flex",
      alignItems: "center",
      gap: 24,
      flexWrap: "wrap",
      padding: "20px 22px",
      border: "1px solid var(--ui-border)",
      borderLeft: `4px solid ${s.bar}`,
      borderRadius: 8,
      background: "var(--ui-surface-muted)",
      boxShadow: "var(--ui-shadow-sm)",
      fontFamily: "var(--font-family)",
      color: "var(--ui-text)",
      ...style
    }
  }, rest), lead ? /*#__PURE__*/React.createElement(NumberColumn, {
    data: lead,
    side: "lead",
    accent: s.accent
  }) : null, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: "1 1 320px",
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      marginBottom: 9
    }
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      width: 7,
      height: 7,
      borderRadius: "50%",
      background: s.accent,
      flex: "none"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      fontWeight: 700,
      color: s.accent,
      letterSpacing: "0.04em",
      whiteSpace: "nowrap"
    }
  }, s.word), eyebrow ? /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      color: "var(--ui-muted)",
      fontWeight: 600,
      letterSpacing: "0.02em",
      whiteSpace: "nowrap"
    }
  }, "\xB7 ", eyebrow) : null), /*#__PURE__*/React.createElement("h4", {
    style: {
      margin: 0,
      fontSize: 18,
      fontWeight: 700,
      color: "var(--ui-text)",
      lineHeight: 1.42,
      textWrap: "pretty"
    }
  }, title), impact ? /*#__PURE__*/React.createElement("p", {
    style: {
      margin: "9px 0 0",
      fontSize: 14,
      color: "var(--ui-text)",
      lineHeight: 1.6,
      textWrap: "pretty"
    }
  }, impact) : null, evidence ? /*#__PURE__*/React.createElement("p", {
    style: {
      margin: "7px 0 0",
      fontSize: 13,
      color: "var(--ui-muted)",
      lineHeight: 1.6,
      textWrap: "pretty"
    }
  }, evidence) : null), anchor ? /*#__PURE__*/React.createElement(NumberColumn, {
    data: anchor,
    side: "anchor",
    accent: s.accent
  }) : null, actions ? /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 10,
      flexWrap: "wrap",
      flex: "none",
      alignSelf: "center"
    }
  }, actions) : null);
}
Object.assign(__ds_scope, { HeroCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/HeroCard.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Meter.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const FILL = {
  primary: "var(--ui-primary)",
  success: "var(--ui-success)",
  warning: "var(--ui-warning)",
  danger: "var(--ui-danger)"
};

/**
 * APS Meter — resource-load / progress bar. Flat track + flat fill, no
 * gradient. Auto-tones by value when `tone` is omitted (load thresholds
 * mirror the product: >=90 danger, >=75 warning, else success).
 */
function Meter({
  value = 0,
  tone,
  height = 8,
  style = {},
  ...rest
}) {
  const v = Math.max(0, Math.min(100, value));
  const auto = v >= 90 ? "danger" : v >= 75 ? "warning" : "success";
  const t = tone || auto;
  return /*#__PURE__*/React.createElement("div", _extends({
    role: "progressbar",
    "aria-valuenow": v,
    "aria-valuemin": 0,
    "aria-valuemax": 100,
    style: {
      height,
      borderRadius: 999,
      background: "var(--ui-surface-soft)",
      overflow: "hidden",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      display: "block",
      height: "100%",
      width: `${v}%`,
      borderRadius: "inherit",
      background: FILL[t] || FILL.primary,
      transition: "width .2s ease"
    }
  }));
}
Object.assign(__ds_scope, { Meter });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Meter.jsx", error: String((e && e.message) || e) }); }

// components/forms/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * APS Button — mirrors the product's .btn contract.
 * Flat, 36px tall (sm 30px), 6px radius, 1px border, subtle shadow that
 * deepens on hover; press nudges down 1px. One filled `primary` per view.
 */
function Button({
  variant = "secondary",
  size = "md",
  disabled = false,
  type = "button",
  leadingIcon = null,
  children,
  style = {},
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const [active, setActive] = React.useState(false);
  const base = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "0.375rem",
    minHeight: size === "sm" ? 30 : 36,
    padding: size === "sm" ? "0.25rem 0.6rem" : "0.5rem 0.95rem",
    border: "1px solid transparent",
    borderRadius: "var(--ui-radius)",
    fontFamily: "var(--font-family)",
    fontSize: size === "sm" ? "0.75rem" : "0.875rem",
    fontWeight: 500,
    lineHeight: 1.2,
    whiteSpace: "nowrap",
    cursor: disabled ? "not-allowed" : "pointer",
    transition: "background-color .15s, color .15s, border-color .15s, box-shadow .15s, transform .12s",
    transform: active && !disabled ? "translateY(1px)" : "none",
    opacity: disabled ? 0.6 : 1
  };
  const variants = {
    primary: {
      background: hover && !disabled ? "var(--ui-primary-hover)" : "var(--ui-primary)",
      borderColor: hover && !disabled ? "var(--ui-primary-hover)" : "var(--ui-primary)",
      color: "#fff",
      boxShadow: disabled ? "none" : hover ? "var(--ui-shadow-md)" : "var(--ui-shadow-sm)"
    },
    secondary: {
      background: hover && !disabled ? "var(--ui-surface-muted)" : "var(--ui-card-bg)",
      borderColor: hover && !disabled ? "#cbd5e1" : "var(--ui-border)",
      color: "var(--ui-text)",
      boxShadow: disabled ? "none" : hover ? "var(--ui-shadow-md)" : "var(--ui-shadow-sm)"
    },
    success: {
      background: "var(--ui-success)",
      borderColor: "var(--ui-success)",
      color: "#fff",
      filter: hover && !disabled ? "brightness(0.95)" : "none",
      boxShadow: disabled ? "none" : "var(--ui-shadow-sm)"
    },
    danger: {
      background: "var(--ui-danger)",
      borderColor: "var(--ui-danger)",
      color: "#fff",
      filter: hover && !disabled ? "brightness(0.95)" : "none",
      boxShadow: disabled ? "none" : "var(--ui-shadow-sm)"
    },
    ghost: {
      background: hover && !disabled ? "var(--ui-surface-muted)" : "transparent",
      borderColor: hover && !disabled ? "var(--ui-border)" : "transparent",
      color: hover && !disabled ? "var(--ui-text)" : "var(--ui-muted)",
      boxShadow: "none"
    }
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    disabled: disabled,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => {
      setHover(false);
      setActive(false);
    },
    onMouseDown: () => setActive(true),
    onMouseUp: () => setActive(false),
    style: {
      ...base,
      ...variants[variant],
      ...style
    }
  }, rest), leadingIcon ? /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      display: "inline-flex"
    }
  }, leadingIcon) : null, children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Button.jsx", error: String((e && e.message) || e) }); }

// components/layout/Panel.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * APS Panel — the standard content container (.card). White, 1px border,
 * 6px radius, subtle shadow. Optional header (title + description on the
 * left, actions on the right) sits on a muted strip. Flat — no glass,
 * no big radius. Pages are a stack of these.
 */
function Panel({
  title,
  description,
  headerRight = null,
  children,
  style = {},
  bodyStyle = {},
  ...rest
}) {
  return /*#__PURE__*/React.createElement("section", _extends({
    style: {
      background: "var(--ui-card-bg)",
      border: "1px solid var(--ui-border)",
      borderRadius: 6,
      boxShadow: "var(--ui-shadow-sm)",
      overflow: "hidden",
      fontFamily: "var(--font-family)",
      color: "var(--ui-text)",
      ...style
    }
  }, rest), (title || headerRight) && /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 16,
      flexWrap: "wrap",
      padding: "12px 16px",
      background: "var(--ui-surface-muted)",
      borderBottom: "1px solid var(--ui-border)"
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: 0,
      fontSize: 16,
      fontWeight: 600,
      color: "var(--ui-text)",
      lineHeight: 1.3
    }
  }, title), description ? /*#__PURE__*/React.createElement("p", {
    style: {
      margin: "4px 0 0",
      fontSize: 13,
      color: "var(--ui-muted)",
      lineHeight: 1.5
    }
  }, description) : null), headerRight ? /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8,
      flexWrap: "wrap",
      alignItems: "center"
    }
  }, headerRight) : null), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 16,
      ...bodyStyle
    }
  }, children));
}
Object.assign(__ds_scope, { Panel });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/layout/Panel.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/AnalysisScreen.jsx
try { (() => {
// APS Workbench · 排产分析 · 周计划 / 方案对比 (scheduler/analysis)
// 推荐结论 → 方案卡片（可选中）→ 指标对比可视化 → 瓶颈负荷矩阵 → 对比明细表
// 五个区块共享同一份方案数据，选中态贯穿卡片 / 对比条 / 明细表高亮。
//
// ┌─ 数据模型决策（供后续 Claude Code 实现，前端此处仍为示例数据）────────────┐
// │ DECISION 2026-06-23: 一次排产 = 一个「方案集」，该次生成的全部候选方案都落库。 │
// │  • 模型：排产任务 1:N 方案；每条方案存 生成参数 / 指标汇总 / 排程明细 / 状态。  │
// │  • 状态：候选 / 已采用 / 已弃用；同一任务下只能有一个「已采用」，采用时写回正式计划。│
// │  • 保留策略：非采用的候选方案【全部永久保留】，不自动清理 / 不做摘要降级。      │
// │    清理完全交给操作者手动执行（硬盘存满时由人决定清哪批），系统不主动删。        │
// │  ⇒ 实现时：采用 = 给方案打「已采用」标记 + 写回正式计划，绝不删除其余候选。      │
// └────────────────────────────────────────────────────────────────────┘

// ---- 方案数据（示例）。所有指标均为「越低越好」，便于统一对比与标注最优。----
const AN_SCHEMES = [{
  id: "focus",
  name: "关键工序优先",
  tag: "已采用",
  tone: "success",
  rec: true,
  verdict: "综合最优 —— 交期、瓶颈负荷、换型三者最平衡。",
  fail: 0,
  late: 2,
  delay: 18,
  sw: 12,
  span: 5.8,
  m03: 96,
  m05: 84,
  m07: 71,
  headline: "先看结论：这套方案最适合现在的交期压力",
  summary: "三套方案没有谁全面碾压：保交期优先晚交最少，却把 M-03 推到 99%、换型多到 16 次；基准方案负荷最松，但晚交最多。关键工序优先在交期、瓶颈负荷与换型之间取得最佳平衡，因此推荐采用。",
  pros: ["晚交压到 2 个、总拖期 18h，接近保交期方案", "M-03 峰值 96%，留出抢修与插单余量", "关键工序优先，现场执行顺序更稳定"],
  cons: ["换型较基准多 2 次（12 vs 10）", "M-03 负荷偏高，需重点盯防"]
}, {
  id: "baseline",
  name: "基准方案",
  tag: "对照基准",
  tone: "secondary",
  rec: false,
  verdict: "换型最少、负荷最松，但晚交批次最多、总拖期最长。",
  fail: 0,
  late: 3,
  delay: 24,
  sw: 10,
  span: 5.6,
  m03: 92,
  m05: 80,
  m07: 68,
  headline: "这是对照基准：换型最省、负荷最松，但交期最弱",
  summary: "基准方案换型只有 10 次、瓶颈负荷最低，胜在稳和省；代价是晚交 3 个批次、总拖期 24h，都是三套里最差的。适合换型成本极高、交期压力不大的场景。",
  pros: ["换型次数最少，仅 10 次", "M-03 峰值 92%，瓶颈最松、抢修余量大", "与现有算法一致，无迁移成本"],
  cons: ["晚交 3 个批次，为三套最多", "总拖期 24h，比推荐方案多 6h"]
}, {
  id: "ontime",
  name: "保交期优先",
  tag: "备选",
  tone: "notice",
  rec: false,
  verdict: "交期表现最好，代价是把瓶颈推到极限、换型显著增多。",
  fail: 0,
  late: 1,
  delay: 12,
  sw: 16,
  span: 6.2,
  m03: 99,
  m05: 90,
  m07: 76,
  headline: "交期最优，代价是把瓶颈推到极限",
  summary: "保交期优先把晚交压到 1 个、总拖期 12h，交期表现三套最好；代价是 M-03 峰值冲到 99%、换型增至 16 次。适合交期是硬约束、可以接受高换型和满负荷的紧急批次。",
  pros: ["晚交仅 1 个、总拖期 12h，交期三套最优", "适合交期硬约束的紧急批次"],
  cons: ["换型增至 16 次，较基准多 6 次", "M-03 峰值 99%，几乎满负荷、无抢修余量", "瓶颈一旦异常极易连锁拖期"]
}];

// 对比指标元数据（越低越好）
const AN_METRICS = [{
  key: "late",
  title: "超期批次",
  unit: "个",
  suf: "",
  better: "fewer"
}, {
  key: "delay",
  title: "总拖期",
  unit: "小时",
  suf: "h",
  better: "fewer"
}, {
  key: "sw",
  title: "换型次数",
  unit: "次",
  suf: "",
  better: "fewer"
}, {
  key: "span",
  title: "总工期",
  unit: "天",
  suf: "天",
  better: "fewer"
}];
function AnalysisScreen({
  onNav
}) {
  const {
    Panel,
    Badge,
    Button,
    Table,
    Kpi
  } = window.APSDesignSystem_edbc5d;
  const D = window.APSDetail;
  const recommended = AN_SCHEMES.find(s => s.rec) || AN_SCHEMES[0];
  const [sel, setSel] = React.useState(recommended.id);
  const cur = AN_SCHEMES.find(s => s.id === sel) || recommended;
  const base = AN_SCHEMES.find(s => s.id === "baseline");
  const bestId = key => AN_SCHEMES.reduce((b, s) => s[key] < b[key] ? s : b, AN_SCHEMES[0]).id;
  const maxOf = key => Math.max.apply(null, AN_SCHEMES.map(s => s[key]));

  // delta vs 基准（越低越好 → 负数=好）
  function Delta({
    d
  }) {
    if (d === 0) return /*#__PURE__*/React.createElement("span", {
      className: "sc-delta flat"
    }, "\u6301\u5E73");
    const good = d < 0;
    return /*#__PURE__*/React.createElement("span", {
      className: "sc-delta " + (good ? "good" : "bad")
    }, good ? "▼" : "▲", Math.abs(d) % 1 === 0 ? Math.abs(d) : Math.abs(d).toFixed(1));
  }

  // ---- 方案卡片的四个迷你指标 ----
  const cardMetrics = [{
    key: "late",
    label: "超期批次",
    suf: ""
  }, {
    key: "delay",
    label: "总拖期",
    suf: "h"
  }, {
    key: "sw",
    label: "换型次数",
    suf: ""
  }, {
    key: "span",
    label: "总工期",
    suf: "天"
  }];

  // ---- 明细表 ----
  const fmt = {
    late: v => v,
    delay: v => v + " 小时",
    sw: v => v,
    span: v => v + " 天"
  };
  const numCell = (key, suf) => r => {
    const best = r[key] === Math.min.apply(null, AN_SCHEMES.map(s => s[key]));
    return /*#__PURE__*/React.createElement("span", {
      className: best ? "cell-best" : undefined,
      style: {
        fontVariantNumeric: "tabular-nums"
      }
    }, r[key], suf);
  };
  const cols = [{
    key: "name",
    title: "方案",
    nowrap: true,
    render: r => /*#__PURE__*/React.createElement("a", {
      href: "#",
      onClick: e => {
        e.preventDefault();
        setSel(r.id);
        D && D.open && D.has && D.has(r.name) && D.open(r.name);
      },
      style: {
        color: r.id === sel ? "var(--ui-primary)" : "var(--ui-text)",
        fontWeight: 700,
        textDecoration: "none",
        cursor: "pointer"
      }
    }, r.name)
  }, {
    key: "tag",
    title: "标签",
    render: r => /*#__PURE__*/React.createElement(Badge, {
      tone: r.tone,
      dot: r.rec
    }, r.rec ? "推荐" : r.tag)
  }, {
    key: "fail",
    title: "失败工序",
    align: "right",
    render: r => /*#__PURE__*/React.createElement("span", {
      style: {
        color: "var(--ui-success)",
        fontVariantNumeric: "tabular-nums"
      }
    }, r.fail)
  }, {
    key: "late",
    title: "超期批次",
    align: "right",
    render: numCell("late", "")
  }, {
    key: "delay",
    title: "总拖期",
    align: "right",
    nowrap: true,
    render: numCell("delay", "h")
  }, {
    key: "span",
    title: "总工期",
    align: "right",
    nowrap: true,
    render: numCell("span", "天")
  }, {
    key: "sw",
    title: "换型次数",
    align: "right",
    render: numCell("sw", "")
  }, {
    key: "m03",
    title: "M-03 峰值",
    align: "right",
    nowrap: true,
    render: r => /*#__PURE__*/React.createElement("span", {
      style: {
        color: r.m03 >= 98 ? "var(--ui-danger)" : r.m03 >= 90 ? "var(--ui-warning)" : "var(--ui-text)",
        fontVariantNumeric: "tabular-nums"
      }
    }, r.m03, "%")
  }];

  // ---- 瓶颈负荷矩阵 ----
  const loadRes = [{
    key: "m03",
    name: "M-03",
    role: "关键瓶颈"
  }, {
    key: "m05",
    name: "M-05",
    role: "次瓶颈"
  }, {
    key: "m07",
    name: "M-07",
    role: "常规"
  }];
  const loadTone = v => v >= 98 ? "danger" : v >= 90 ? "warning" : v >= 80 ? "notice" : "ok";
  const loadColor = {
    danger: "var(--ui-danger)",
    warning: "var(--ui-warning)",
    notice: "var(--ui-primary)",
    ok: "var(--ui-success)"
  };
  const loadBg = {
    danger: "var(--ui-danger-bg)",
    warning: "var(--ui-warning-bg)",
    notice: "var(--ui-info-bg)",
    ok: "var(--ui-success-bg)"
  };

  // ---- 结论卡与选中方案联动：KPI 相对基准方案的描述文本 ----
  const relText = (curV, baseV, unit) => {
    if (cur.id === "baseline") return "作为对照基准";
    const d = +(curV - baseV).toFixed(1);
    if (d === 0) return "与基准持平";
    const abs = Math.abs(d) % 1 === 0 ? Math.abs(d) : Math.abs(d).toFixed(1);
    return "较基准" + (d < 0 ? "少 " : "多 ") + abs + " " + unit;
  };
  const lateColor = cur.late < base.late ? "var(--ui-success)" : cur.late > base.late ? "var(--ui-danger)" : undefined;
  const delayColor = cur.delay < base.delay ? "var(--ui-success)" : cur.delay > base.delay ? "var(--ui-danger)" : undefined;
  const swColor = cur.sw > base.sw ? "var(--ui-warning)" : cur.sw < base.sw ? "var(--ui-success)" : undefined;
  const m03Helper = cur.m03 >= 98 ? "峰值 " + cur.m03 + "% 几乎满载、需严盯" : cur.m03 >= 90 ? "峰值 " + cur.m03 + "% 偏高、需盯防" : "峰值 " + cur.m03 + "% 尚有余量";
  return /*#__PURE__*/React.createElement(Panel, {
    title: "\u65B9\u6848\u5BF9\u6BD4",
    description: "\u5148\u7ED9\u63A8\u8350\u7ED3\u8BBA\uFF0C\u518D\u7528\u65B9\u6848\u5361\u7247\u3001\u6307\u6807\u5BF9\u6BD4\u548C\u8D1F\u8377\u77E9\u9635\u628A\u597D\u5904\u4E0E\u4EE3\u4EF7\u6446\u6E05\u695A\uFF0C\u6700\u540E\u624D\u662F\u660E\u7EC6\u8868 \u2014\u2014 \u4E1A\u52A1\u7528\u6237\u4E0D\u5FC5\u81EA\u5DF1\u5728\u8868\u91CC\u505A\u6570\u5B66\u9898\u3002",
    headerRight: /*#__PURE__*/React.createElement(Badge, {
      tone: "primary",
      dot: true
    }, "\u7CFB\u7EDF\u5EFA\u8BAE")
  }, /*#__PURE__*/React.createElement("section", {
    className: "recommend"
  }, /*#__PURE__*/React.createElement("div", {
    className: "rec-main"
  }, /*#__PURE__*/React.createElement("div", {
    className: "rec-chips"
  }, cur.rec ? /*#__PURE__*/React.createElement(Badge, {
    tone: "primary"
  }, "\u5EFA\u8BAE\u91C7\u7528\uFF1A", cur.name) : /*#__PURE__*/React.createElement(Badge, {
    tone: cur.tone,
    dot: true
  }, "\u5F53\u524D\u67E5\u770B\uFF1A", cur.name), cur.rec ? /*#__PURE__*/React.createElement(Badge, {
    tone: "success",
    dot: true
  }, "\u7EFC\u5408\u8BC4\u4F30") : /*#__PURE__*/React.createElement(Badge, {
    tone: "secondary"
  }, "\u7CFB\u7EDF\u63A8\u8350\uFF1A", recommended.name)), /*#__PURE__*/React.createElement("h4", null, cur.headline), /*#__PURE__*/React.createElement("p", null, cur.summary), /*#__PURE__*/React.createElement("div", {
    className: "rec-gc"
  }, /*#__PURE__*/React.createElement("div", {
    className: "gc-col"
  }, /*#__PURE__*/React.createElement("h5", null, cur.rec ? "为什么推荐它" : "它的优势"), /*#__PURE__*/React.createElement("div", {
    className: "gc-list"
  }, cur.pros.map((t, i) => /*#__PURE__*/React.createElement("div", {
    className: "gc-li",
    key: i
  }, /*#__PURE__*/React.createElement("span", {
    className: "gc-dot good"
  }), t)))), /*#__PURE__*/React.createElement("div", {
    className: "gc-col"
  }, /*#__PURE__*/React.createElement("h5", null, "\u8981\u63A5\u53D7\u7684\u4EE3\u4EF7"), /*#__PURE__*/React.createElement("div", {
    className: "gc-list"
  }, cur.cons.map((t, i) => /*#__PURE__*/React.createElement("div", {
    className: "gc-li",
    key: i
  }, /*#__PURE__*/React.createElement("span", {
    className: "gc-dot cost"
  }), t))))), /*#__PURE__*/React.createElement("div", {
    className: "rec-actions"
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    onClick: () => onNav("gantt")
  }, "\u67E5\u770B\u7518\u7279\u56FE"), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    onClick: () => onNav("delay")
  }, "\u67E5\u770B\u5EF6\u671F\u8BF4\u660E"), /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    onClick: () => D && D.toast && D.toast("已采用「" + cur.name + "」并写回正式计划（示例）")
  }, "\u91C7\u7528\u6B64\u65B9\u6848"))), /*#__PURE__*/React.createElement("div", {
    className: "rec-stats"
  }, /*#__PURE__*/React.createElement(Kpi, {
    label: "\u8D85\u671F\u6279\u6B21\u6570",
    value: cur.late,
    valueColor: lateColor,
    helper: relText(cur.late, base.late, "个")
  }), /*#__PURE__*/React.createElement(Kpi, {
    label: "\u603B\u62D6\u671F",
    value: cur.delay + "h",
    valueColor: delayColor,
    helper: relText(cur.delay, base.delay, "小时")
  }), /*#__PURE__*/React.createElement(Kpi, {
    label: "\u6362\u578B\u6B21\u6570",
    value: cur.sw,
    valueColor: swColor,
    helper: relText(cur.sw, base.sw, "次")
  }), /*#__PURE__*/React.createElement(Kpi, {
    label: "M-03 \u5CF0\u503C\u8D1F\u8377",
    value: cur.m03 + "%",
    valueColor: loadColor[loadTone(cur.m03)],
    helper: m03Helper
  }))), /*#__PURE__*/React.createElement("div", {
    className: "sec-head",
    style: {
      marginTop: 24
    }
  }, /*#__PURE__*/React.createElement("h4", null, "\u4E09\u5957\u5019\u9009\u65B9\u6848"), /*#__PURE__*/React.createElement("span", {
    className: "sec-meta"
  }, "\u70B9\u51FB\u5361\u7247\u9009\u4E2D \xB7 \u4E0B\u65B9\u5BF9\u6BD4\u968F\u4E4B\u9AD8\u4EAE")), /*#__PURE__*/React.createElement("div", {
    className: "scheme-row"
  }, AN_SCHEMES.map(s => /*#__PURE__*/React.createElement("article", {
    key: s.id,
    className: "scheme-card" + (s.id === sel ? " sel" : ""),
    onClick: () => setSel(s.id),
    role: "button",
    tabIndex: 0,
    onKeyDown: e => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        setSel(s.id);
      }
    }
  }, s.rec ? /*#__PURE__*/React.createElement("span", {
    className: "sc-ribbon"
  }, "\u2605 \u63A8\u8350") : null, /*#__PURE__*/React.createElement("div", {
    className: "sc-head"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sc-name"
  }, s.name), /*#__PURE__*/React.createElement(Badge, {
    tone: s.tone,
    dot: s.id === sel
  }, s.id === sel ? "已选中" : s.tag)), /*#__PURE__*/React.createElement("div", {
    className: "sc-verdict"
  }, s.verdict), /*#__PURE__*/React.createElement("div", {
    className: "sc-grid"
  }, cardMetrics.map(m => {
    const isBest = s[m.key] === Math.min.apply(null, AN_SCHEMES.map(x => x[m.key]));
    const d = s.id === "baseline" ? null : +(s[m.key] - base[m.key]).toFixed(1);
    return /*#__PURE__*/React.createElement("div", {
      className: "sc-metric",
      key: m.key
    }, /*#__PURE__*/React.createElement("span", {
      className: "sc-m-label"
    }, m.label), /*#__PURE__*/React.createElement("span", {
      className: "sc-m-val" + (isBest ? " best" : "")
    }, s[m.key], m.suf ? /*#__PURE__*/React.createElement("span", {
      className: "u"
    }, m.suf) : null, d !== null ? /*#__PURE__*/React.createElement(Delta, {
      d: d
    }) : null));
  })), /*#__PURE__*/React.createElement("div", {
    className: "sc-foot"
  }, /*#__PURE__*/React.createElement(Button, {
    variant: s.id === sel ? "primary" : "secondary",
    size: "sm",
    style: {
      width: "100%"
    },
    onClick: e => {
      e.stopPropagation();
      setSel(s.id);
      onNav("gantt");
    }
  }, s.id === sel ? "查看此方案甘特" : "选中并查看"))))), /*#__PURE__*/React.createElement("div", {
    className: "sec-head",
    style: {
      marginTop: 24
    }
  }, /*#__PURE__*/React.createElement("h4", null, "\u6307\u6807\u5BF9\u6BD4 ", /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      fontWeight: 400,
      color: "var(--ui-muted)"
    }
  }, "\xB7 \u8D8A\u77ED\u8D8A\u597D\uFF0C\u7EFF\u8272\u4E3A\u8BE5\u9879\u6700\u4F18")), /*#__PURE__*/React.createElement("span", {
    className: "sec-meta"
  }, "\u5F53\u524D\u9009\u4E2D\uFF1A", cur.name)), /*#__PURE__*/React.createElement("div", {
    className: "cmp-grid"
  }, AN_METRICS.map(m => {
    const mx = maxOf(m.key);
    const bId = bestId(m.key);
    return /*#__PURE__*/React.createElement("div", {
      className: "cmp-card",
      key: m.key
    }, /*#__PURE__*/React.createElement("div", {
      className: "cmp-title"
    }, /*#__PURE__*/React.createElement("strong", null, m.title), /*#__PURE__*/React.createElement("span", {
      className: "cmp-unit"
    }, "\u5355\u4F4D\uFF1A", m.unit)), /*#__PURE__*/React.createElement("div", {
      className: "cmp-rows"
    }, AN_SCHEMES.map(s => {
      const isBest = s.id === bId;
      const on = s.id === sel;
      return /*#__PURE__*/React.createElement("div", {
        className: "cmp-row" + (on ? " on" : "") + (isBest ? " best" : ""),
        key: s.id
      }, /*#__PURE__*/React.createElement("span", {
        className: "cmp-name"
      }, s.name), /*#__PURE__*/React.createElement("span", {
        className: "cmp-track"
      }, /*#__PURE__*/React.createElement("span", {
        className: "cmp-fill",
        style: {
          width: Math.max(6, s[m.key] / mx * 100) + "%"
        }
      })), /*#__PURE__*/React.createElement("span", {
        className: "cmp-val"
      }, s[m.key], m.suf, isBest ? /*#__PURE__*/React.createElement("span", {
        className: "star"
      }, "\u2605") : null));
    })));
  })), /*#__PURE__*/React.createElement("div", {
    className: "sec-head",
    style: {
      marginTop: 24
    }
  }, /*#__PURE__*/React.createElement("h4", null, "\u74F6\u9888\u8D44\u6E90\u5CF0\u503C\u8D1F\u8377 ", /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      fontWeight: 400,
      color: "var(--ui-muted)"
    }
  }, "\xB7 \u4E09\u5957\u65B9\u6848\u5BF9\u540C\u4E00\u8D44\u6E90\u7684\u5360\u7528")), /*#__PURE__*/React.createElement("span", {
    className: "sec-meta"
  }, "\u226598% \u7EA2 \xB7 \u226590% \u6A59 \xB7 \u226580% \u84DD")), /*#__PURE__*/React.createElement("div", {
    className: "load-matrix"
  }, /*#__PURE__*/React.createElement("div", {
    className: "lm-corner"
  }, "\u8D44\u6E90"), AN_SCHEMES.map(s => /*#__PURE__*/React.createElement("div", {
    className: "lm-colhead",
    key: s.id,
    style: {
      color: s.id === sel ? "var(--ui-primary)" : undefined
    }
  }, s.name, /*#__PURE__*/React.createElement("small", null, s.id === sel ? "当前选中" : s.rec ? "推荐" : s.tag))), loadRes.map(res => {
    const peak = Math.max.apply(null, AN_SCHEMES.map(s => s[res.key]));
    return /*#__PURE__*/React.createElement(React.Fragment, {
      key: res.key
    }, /*#__PURE__*/React.createElement("div", {
      className: "lm-res"
    }, res.name, /*#__PURE__*/React.createElement("small", null, res.role)), AN_SCHEMES.map(s => {
      const v = s[res.key];
      const tone = loadTone(v);
      const on = s.id === sel;
      return /*#__PURE__*/React.createElement("div", {
        className: "lm-cell",
        key: s.id
      }, /*#__PURE__*/React.createElement("div", {
        className: "lm-cell-top" + (on ? " on" : "")
      }, v, "%", v === peak && peak >= 90 ? /*#__PURE__*/React.createElement("span", {
        className: "tag",
        style: {
          color: loadColor[tone],
          background: loadBg[tone]
        }
      }, "\u5CF0\u503C") : null), /*#__PURE__*/React.createElement("span", {
        className: "cmp-track"
      }, /*#__PURE__*/React.createElement("span", {
        className: "cmp-fill",
        style: {
          width: v + "%",
          opacity: 1,
          background: loadColor[tone]
        }
      })));
    }));
  })), /*#__PURE__*/React.createElement("div", {
    className: "sub-title",
    style: {
      marginTop: 24
    }
  }, "\u5BF9\u6BD4\u660E\u7EC6\u8868 ", /*#__PURE__*/React.createElement("span", null, "\xB7 \u5148\u770B\u4EA4\u671F\u3001\u62D6\u671F\u3001\u6362\u578B\u8FD9\u4E9B\u4E1A\u52A1\u6307\u6807\uFF1B\u7EFF\u8272\u4E3A\u8BE5\u5217\u6700\u4F18")), /*#__PURE__*/React.createElement(Table, {
    columns: cols,
    rows: AN_SCHEMES,
    rowKey: "id"
  }));
}
window.AnalysisScreen = AnalysisScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/AnalysisScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/AppShell.jsx
try { (() => {
// APS Workbench · App shell — grouped, iconised sidebar (workflow stages) + header
// Sidebar structure mirrors the approved prototype: pages grouped by stage.

function Ico({
  name
}) {
  const P = {
    box: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M3 7l9-4 9 4v10l-9 4-9-4V7z"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M3 7l9 4 9-4M12 11v10"
    })),
    database: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("ellipse", {
      cx: "12",
      cy: "5",
      rx: "8",
      ry: "3"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M4 5v14c0 1.6 3.6 3 8 3s8-1.4 8-3V5"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M4 12c0 1.6 3.6 3 8 3s8-1.4 8-3"
    })),
    play: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
      cx: "12",
      cy: "12",
      r: "9"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M10 8.5l6 3.5-6 3.5v-7z"
    })),
    home: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M3 11l9-7 9 7"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M5 10v10h14V10"
    })),
    gantt: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M4 7h10M4 12h15M4 17h7"
    })),
    chart: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M4 5v15h16"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M7 14l4-4 3 3 5-6"
    })),
    users: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
      cx: "9",
      cy: "8",
      r: "3"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M3 20c0-3.3 3-5 6-5s6 1.7 6 5"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M16 5.5a3 3 0 010 6M21.5 20c0-2.2-1.2-3.6-3.2-4.3"
    })),
    clipboard: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("rect", {
      x: "6",
      y: "4",
      width: "12",
      height: "17",
      rx: "2"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M9.5 4V3.2h5V4"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M9 10.5h6M9 14.5h4"
    })),
    file: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M7 3h7l5 5v13H7z"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M14 3v5h5"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M10 13h6M10 17h6"
    })),
    grid: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("rect", {
      x: "4",
      y: "4",
      width: "7",
      height: "7",
      rx: "1.2"
    }), /*#__PURE__*/React.createElement("rect", {
      x: "13",
      y: "4",
      width: "7",
      height: "7",
      rx: "1.2"
    }), /*#__PURE__*/React.createElement("rect", {
      x: "4",
      y: "13",
      width: "7",
      height: "7",
      rx: "1.2"
    }), /*#__PURE__*/React.createElement("rect", {
      x: "13",
      y: "13",
      width: "7",
      height: "7",
      rx: "1.2"
    })),
    settings: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M4 7h9M18 7h2M4 17h2M11 17h9"
    }), /*#__PURE__*/React.createElement("circle", {
      cx: "15",
      cy: "7",
      r: "2.2"
    }), /*#__PURE__*/React.createElement("circle", {
      cx: "8",
      cy: "17",
      r: "2.2"
    })),
    scale: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
      d: "M12 4v16M7 21h10"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M5 8h14M12 4l7 4M12 4L5 8"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M5 8l-2.6 5h5.2zM19 8l-2.6 5h5.2z"
    }))
  };
  return /*#__PURE__*/React.createElement("svg", {
    className: "nav-ico",
    viewBox: "0 0 24 24",
    width: "18",
    height: "18",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.75",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true"
  }, P[name]);
}
const NAV_GROUPS = [{
  title: "① 数据准备",
  items: [{
    id: "process",
    label: "基础资料",
    icon: "database"
  }, {
    id: "batches",
    label: "批次管理",
    icon: "box"
  }]
}, {
  title: "② 执行排产",
  items: [{
    id: "run",
    label: "执行排产",
    icon: "play"
  }, {
    id: "analysis",
    label: "选择排产方案",
    icon: "chart"
  }, {
    id: "gantt",
    label: "设备 / 人员 / 批次甘特",
    icon: "gantt"
  }]
}, {
  title: "③ 现场",
  items: [{
    id: "field",
    label: "现场记录",
    icon: "clipboard"
  }, {
    id: "fieldgantt",
    label: "现场实际甘特",
    icon: "gantt"
  }]
}, {
  title: "④ 统计分析",
  items: [{
    id: "reports",
    label: "执行复盘 · 报表中心",
    icon: "file"
  }, {
    id: "calib",
    label: "工时定额校准",
    icon: "scale"
  }]
}, {
  title: "基础数据 · 系统",
  items: [{
    id: "dashboard",
    label: "值班台",
    icon: "home"
  }, {
    id: "basedata",
    label: "主数据总览",
    icon: "grid"
  }, {
    id: "system",
    label: "系统管理",
    icon: "settings"
  }]
}];
function AppShell({
  active,
  onNav,
  theme,
  onToggleTheme,
  title,
  showCapsule = true,
  flush = false,
  children
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "app-container"
  }, /*#__PURE__*/React.createElement("aside", {
    className: "sidebar"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sidebar-header"
  }, /*#__PURE__*/React.createElement("span", {
    className: "brand-tile",
    "aria-label": "APS \u667A\u80FD\u6392\u4EA7"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 24 24",
    width: "18",
    height: "18",
    fill: "#fff",
    "aria-hidden": "true"
  }, /*#__PURE__*/React.createElement("rect", {
    x: "4",
    y: "6",
    width: "10",
    height: "3.2",
    rx: "1.6"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "7",
    y: "10.4",
    width: "12",
    height: "3.2",
    rx: "1.6",
    "fill-opacity": "0.92"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "4",
    y: "14.8",
    width: "8",
    height: "3.2",
    rx: "1.6",
    "fill-opacity": "0.78"
  }))), /*#__PURE__*/React.createElement("span", {
    className: "brand-word"
  }, "APS \u667A\u80FD\u6392\u4EA7")), /*#__PURE__*/React.createElement("nav", {
    className: "sidebar-nav"
  }, NAV_GROUPS.map(g => /*#__PURE__*/React.createElement("div", {
    className: "nav-group",
    key: g.title
  }, /*#__PURE__*/React.createElement("div", {
    className: "nav-group-title"
  }, g.title), g.items.map(it => /*#__PURE__*/React.createElement("a", {
    key: it.id,
    href: "#" + it.id,
    onClick: e => {
      e.preventDefault();
      onNav(it.id);
    },
    className: "nav-item" + (active === it.id ? " active" : ""),
    "aria-current": active === it.id ? "page" : undefined
  }, /*#__PURE__*/React.createElement(Ico, {
    name: it.icon
  }), /*#__PURE__*/React.createElement("span", {
    className: "nav-label"
  }, it.label))))))), /*#__PURE__*/React.createElement("div", {
    className: "main-content"
  }, /*#__PURE__*/React.createElement("header", {
    className: "top-header"
  }, /*#__PURE__*/React.createElement("h2", {
    className: "top-title"
  }, title), /*#__PURE__*/React.createElement("div", {
    className: "cap-rich",
    style: showCapsule ? undefined : {
      visibility: "hidden"
    }
  }, /*#__PURE__*/React.createElement("strong", null, "\u7B2C 3 \u7248"), /*#__PURE__*/React.createElement("i", {
    className: "cap-sep"
  }, "\xB7"), /*#__PURE__*/React.createElement("span", null, "\u6B63\u5F0F\u91C7\u7528\u65B9\u6848"), /*#__PURE__*/React.createElement("i", {
    className: "cap-sep"
  }, "\xB7"), /*#__PURE__*/React.createElement("span", null, "\u4F18\u5316\u6392\u4EA7"), /*#__PURE__*/React.createElement("span", {
    className: "cap-ok"
  }, "\u6210\u529F"), /*#__PURE__*/React.createElement("i", {
    className: "cap-sep"
  }, "\xB7"), /*#__PURE__*/React.createElement("span", {
    className: "cap-muted"
  }, "\u751F\u6210\u4E8E 06-10 14:30"), /*#__PURE__*/React.createElement("i", {
    className: "cap-sep"
  }, "\xB7"), /*#__PURE__*/React.createElement("span", {
    className: "cap-muted"
  }, "\u8303\u56F4 05-04 \uFF5E 05-10")), /*#__PURE__*/React.createElement("div", {
    className: "header-controls"
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "hdr-pill",
    onClick: onToggleTheme
  }, "\u6DF1\u8272\uFF1A", theme === "dark" ? "开" : "关"))), /*#__PURE__*/React.createElement("main", {
    className: "page-content",
    style: flush ? {
      padding: 0,
      flex: 1,
      minHeight: 0,
      display: "flex",
      flexDirection: "column"
    } : undefined
  }, children)));
}
window.AppShell = AppShell;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/AppShell.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/BaseBatches.jsx
try { (() => {
// APS Workbench · 批次管理 — 全功能复刻（列表 + 主从工作区）
// List (批量维护 / 新增 / 批量操作) → master-detail：① 基础信息 ② 同步工艺 ③ 工序概况 ④ 批次工序（设备/人员/工时/外协补齐）
// 参考「排产基础资料 · 零件工艺模板」的主从范式重做，未照搬仓库旧版（旧版把方案/配置/快照堆在列表页）。
(function () {
  const {
    useState,
    useEffect
  } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;

  /* ---------------- reference data ---------------- */
  const PRIORITY = {
    normal: {
      label: "普通",
      tone: "secondary"
    },
    urgent: {
      label: "急件",
      tone: "warning"
    },
    critical: {
      label: "特急",
      tone: "danger"
    }
  };
  const READY = {
    yes: {
      label: "齐套",
      tone: "ok"
    },
    partial: {
      label: "部分齐套",
      tone: "warning"
    },
    no: {
      label: "未齐套",
      tone: "danger"
    }
  };
  const STATUS = {
    pending: {
      label: "待排",
      tone: "secondary"
    },
    scheduled: {
      label: "已排",
      tone: "notice"
    },
    processing: {
      label: "加工中",
      tone: "warning"
    },
    completed: {
      label: "已完成",
      tone: "ok"
    },
    cancelled: {
      label: "已取消",
      tone: "secondary"
    }
  };

  // 图号（零件）来自共享数据源：“排产基础资料 · 零件工艺模板”。
  // 这里不再本地硬编码零件清单，统一读 window.BD（详见 BaseShared.jsx）。
  const partName = pn => window.BD.partName(pn);
  const MACHINES = [{
    value: "M-03",
    label: "M-03 五轴加工中心 · 精加工"
  }, {
    value: "M-05",
    label: "M-05 卧式加工中心 · 预加工"
  }, {
    value: "M-07",
    label: "M-07 立式加工中心 · 组装"
  }, {
    value: "M-12",
    label: "M-12 三坐标检测 · 检验"
  }, {
    value: "M-18",
    label: "M-18 数控车床 · 车加工"
  }];
  const OPERATORS = [{
    value: "P-021",
    label: "P-021 张三 · 精加工"
  }, {
    value: "P-024",
    label: "P-024 李四 · 组装"
  }, {
    value: "P-030",
    label: "P-030 王五 · 检验"
  }, {
    value: "P-033",
    label: "P-033 赵六 · 车加工"
  }];
  const SUPPLIERS = [{
    value: "华表面处理",
    label: "华表面处理"
  }, {
    value: "金鼎热处理",
    label: "金鼎热处理"
  }];
  // 人员-设备关联（双向联动约束）：选了设备后，仅这些人员可与之组合。
  const MACHINE_OPERATORS = {
    "M-03": ["P-021"],
    "M-05": ["P-021", "P-024"],
    "M-07": ["P-024"],
    "M-12": ["P-030"],
    "M-18": ["P-033"]
  };
  const labelOf = (list, v) => {
    const o = list.find(x => x.value === v);
    return o ? o.label : v;
  };

  // 幽灵红：危险操作与建设性操作明显分离（方案 B 选择条内的「删除所选」）
  const GHOST_DANGER = {
    background: "var(--ui-card-bg)",
    borderColor: "var(--ui-border)",
    color: "var(--ui-danger)"
  };
  const io = (seq, op_type, machine, operator, setup, unit, done) => ({
    seq,
    op_code: null,
    op_type,
    source: "internal",
    machine,
    operator,
    setup,
    unit,
    done
  });
  const ex = (seq, op_type, supplier, ext_days, group, mode, total, done) => ({
    seq,
    op_code: null,
    op_type,
    source: "external",
    supplier,
    ext_days,
    group,
    mode,
    total,
    done
  });
  const SEED = [{
    batch_id: "B202605-018",
    part_no: "T-1008",
    quantity: 12,
    due_date: "2026-05-24",
    ready_date: "2026-05-22",
    priority: "critical",
    ready_status: "yes",
    status: "processing",
    remark: "客户催货",
    ops: [io(5, "数铣", "M-03", "P-021", 0.5, 1.2, true), io(10, "钳工", "M-07", "P-024", 0.3, 0.8, true), io(20, "数车", "M-18", "P-033", 0.4, 1.0, true), ex(30, "电镀", "华表面处理", 3, "G1", "separate", null, true), ex(35, "发黑", "华表面处理", 2, "G1", "separate", null, true), io(40, "总检", "M-12", "P-030", 0.2, 0.3, false), io(45, "表处理", "", "", 0.3, 0.6, false)]
  }, {
    batch_id: "B202605-021",
    part_no: "T-1009",
    quantity: 8,
    due_date: "2026-05-25",
    ready_date: "2026-05-23",
    priority: "urgent",
    ready_status: "partial",
    status: "scheduled",
    remark: "",
    ops: [io(5, "数铣", "M-03", "P-021", 0.5, 1.1, true), io(10, "钳工", "M-07", "P-024", 0.3, 0.7, true), io(20, "数车", "M-18", "P-033", 0.4, 1.0, false), io(30, "精磨", "M-05", "P-021", 0.6, 1.3, false), io(40, "总检", "M-12", "P-030", 0.2, 0.3, false)]
  }, {
    batch_id: "B202605-011",
    part_no: "T-1011",
    quantity: 6,
    due_date: "2026-05-25",
    ready_date: "",
    priority: "normal",
    ready_status: "yes",
    status: "pending",
    remark: "待复核外协周期",
    ops: [io(5, "数车", "M-18", "P-033", 0.3, 0.5, false), io(10, "钻孔", "M-05", "", 0.2, 0.4, false), ex(20, "热处理", "金鼎热处理", null, "G1", "merged", 6, false), ex(25, "喷涂", "", null, "G1", "merged", 6, false), io(30, "总检", "M-12", "P-030", 0.2, 0.3, false)]
  }, {
    batch_id: "B202605-024",
    part_no: "T-1014",
    quantity: 4,
    due_date: "2026-05-26",
    ready_date: "",
    priority: "normal",
    ready_status: "no",
    status: "pending",
    remark: "草稿，工序未生成",
    ops: []
  }, {
    batch_id: "B202605-017",
    part_no: "T-1008",
    quantity: 10,
    due_date: "2026-05-26",
    ready_date: "2026-05-20",
    priority: "normal",
    ready_status: "yes",
    status: "completed",
    remark: "",
    ops: [io(5, "数铣", "M-03", "P-021", 0.5, 1.2, true), io(10, "钳工", "M-07", "P-024", 0.3, 0.8, true), io(20, "数车", "M-18", "P-033", 0.4, 1.0, true), ex(30, "电镀", "华表面处理", 3, "G1", "separate", null, true), ex(35, "发黑", "华表面处理", 2, "G1", "separate", null, true), io(40, "总检", "M-12", "P-030", 0.2, 0.3, true), io(45, "表处理", "M-07", "P-024", 0.3, 0.6, true)]
  }].map(b => ({
    ...b,
    ops: b.ops.map(o => ({
      ...o,
      op_code: b.batch_id + "-" + String(o.seq).padStart(2, "0")
    }))
  }));
  const doneCount = ops => ops.filter(o => o.done).length;
  const needsRes = o => o.source === "internal" ? !o.machine || !o.operator : !o.supplier || o.mode !== "merged" && o.ext_days == null;
  const gapCount = ops => ops.filter(needsRes).length;

  /* ============================================================ SCREEN */
  function BatchesScreen() {
    const [batches, setBatches] = useState(SEED);
    const [view, setView] = useState("list");
    const [openId, setOpenId] = useState(null);
    const [wiz, setWiz] = useState(null);
    const [flash, showFlash, clear] = B().useFlash();
    const {
      Flash
    } = B();
    const flashFn = (tone, msg) => showFlash(tone, msg);
    const openDetail = id => {
      setOpenId(id);
      setView("detail");
      window.scrollTo({
        top: 0
      });
    };
    const back = () => {
      setView("list");
      setOpenId(null);
      window.scrollTo({
        top: 0
      });
    };
    const updateBatch = (id, patch) => setBatches(arr => arr.map(b => b.batch_id === id ? {
      ...b,
      ...patch
    } : b));
    const deleteBatch = id => setBatches(arr => arr.filter(b => b.batch_id !== id));
    let body;
    if (view === "detail") {
      body = /*#__PURE__*/React.createElement(BatchDetail, {
        batch: batches.find(b => b.batch_id === openId),
        onBack: back,
        onUpdate: updateBatch,
        onDelete: deleteBatch,
        flashFn: flashFn
      });
    } else {
      body = /*#__PURE__*/React.createElement(BatchList, {
        batches: batches,
        setBatches: setBatches,
        onOpen: openDetail,
        onWiz: setWiz,
        flashFn: flashFn
      });
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(Flash, {
      flash: flash
    }), body, wiz ? /*#__PURE__*/React.createElement(BatchImportModal, {
      wiz: wiz,
      onClose: () => setWiz(null),
      onDone: s => {
        flashFn("ok", "批次导入完成：" + s + "。");
        setWiz(null);
      }
    }) : null);
  }

  /* ============================================================ IMPORT MODAL（单步 · 弹窗） */
  function BatchImportModal({
    wiz,
    onClose,
    onDone
  }) {
    const {
      Button
    } = DS();
    const {
      Field
    } = B();
    const modes = [{
      value: "overwrite",
      label: "已有批次就更新，没有的就新增"
    }, {
      value: "append",
      label: "只新增没有的批次（已有的跳过）"
    }, {
      value: "replace",
      label: "先清空全部批次，再按表格重导"
    }];
    const [mode, setMode] = useState(modes[0].value);
    const [fileName, setFileName] = useState("");
    useEffect(() => {
      const onKey = e => {
        if (e.key === "Escape") onClose();
      };
      document.addEventListener("keydown", onKey);
      return () => document.removeEventListener("keydown", onKey);
    }, []);
    const confirm = () => {
      if (!fileName) return;
      onDone(fileName + " · 共 126 行（新增 118 / 更新 8）");
    };
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-modal-backdrop",
      onClick: onClose
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-modal",
      role: "dialog",
      "aria-modal": "true",
      style: {
        width: "min(560px, 100%)"
      },
      onClick: e => e.stopPropagation()
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-modal-head",
      style: {
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        padding: "16px 18px 14px",
        borderBottom: "1px solid var(--ui-border)"
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 38,
        height: 38,
        borderRadius: 10,
        background: "var(--ui-primary-soft)",
        color: "var(--ui-primary)",
        display: "grid",
        placeItems: "center",
        flex: "none"
      },
      "aria-hidden": "true"
    }, /*#__PURE__*/React.createElement("svg", {
      viewBox: "0 0 24 24",
      width: "20",
      height: "20",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "1.8",
      strokeLinecap: "round",
      strokeLinejoin: "round"
    }, /*#__PURE__*/React.createElement("path", {
      d: "M12 16V4M7 9l5-5 5 5"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M5 16v4h14v-4"
    }))), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("h4", {
      style: {
        margin: 0,
        fontSize: 16,
        fontWeight: 600
      }
    }, wiz.title || "批量维护批次"), /*#__PURE__*/React.createElement("div", {
      className: "muted",
      style: {
        fontSize: 12.5,
        marginTop: 2,
        lineHeight: 1.5
      }
    }, wiz.desc || "通过 Excel 成批新增或更新批次。")), /*#__PURE__*/React.createElement("button", {
      className: "bd-modal-x",
      onClick: onClose,
      "aria-label": "\u5173\u95ED",
      style: {
        flex: "none",
        width: 30,
        height: 30,
        border: "none",
        background: "transparent",
        color: "var(--ui-muted)",
        cursor: "pointer",
        borderRadius: 8,
        display: "grid",
        placeItems: "center",
        fontSize: 18,
        lineHeight: 1
      }
    }, "\xD7")), /*#__PURE__*/React.createElement("div", {
      className: "bd-modal-body",
      style: {
        padding: "16px 18px",
        color: "var(--ui-text)"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "12px 14px",
        border: "1px solid var(--ui-border)",
        borderRadius: 10,
        background: "var(--ui-surface-muted)",
        marginBottom: 14
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 32,
        height: 32,
        borderRadius: 8,
        background: "var(--ui-card-bg)",
        border: "1px solid var(--ui-border)",
        display: "grid",
        placeItems: "center",
        color: "var(--ui-success)",
        flex: "none"
      },
      "aria-hidden": "true"
    }, /*#__PURE__*/React.createElement("svg", {
      viewBox: "0 0 24 24",
      width: "17",
      height: "17",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "1.8",
      strokeLinecap: "round",
      strokeLinejoin: "round"
    }, /*#__PURE__*/React.createElement("path", {
      d: "M7 3h7l5 5v13H7z"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M14 3v5h5"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M9.5 13l1.8 1.8L15 11"
    }))), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 13,
        fontWeight: 600
      }
    }, "\u6279\u6B21\u5BFC\u5165\u6A21\u677F.xlsx"), /*#__PURE__*/React.createElement("div", {
      className: "muted",
      style: {
        fontSize: 11.5,
        marginTop: 2
      }
    }, "\u542B\u5B57\u6BB5\u8BF4\u660E\u4E0E\u793A\u4F8B\u884C\uFF0C\u6309\u6A21\u677F\u586B\u5199\u540E\u4E0A\u4F20")), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "sm"
    }, "\u4E0B\u8F7D\u6A21\u677F")), /*#__PURE__*/React.createElement("div", {
      style: {
        marginBottom: 14
      }
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u5BFC\u5165\u6A21\u5F0F"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: mode,
      onChange: e => setMode(e.target.value)
    }, modes.map(o => /*#__PURE__*/React.createElement("option", {
      key: o.value,
      value: o.value
    }, o.label))))), /*#__PURE__*/React.createElement("div", {
      className: "bd-upload"
    }, /*#__PURE__*/React.createElement("input", {
      type: "file",
      accept: ".xlsx",
      "aria-label": "\u9009\u62E9 Excel \u6587\u4EF6",
      onChange: e => setFileName(e.target.files && e.target.files[0] ? e.target.files[0].name : "")
    }), /*#__PURE__*/React.createElement("span", {
      className: "up-file"
    }, fileName ? fileName : /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "\u4EC5\u652F\u6301 .xlsx\uFF0C\u8868\u5934\u4E0D\u8981\u6539\uFF0C\u53EA\u8BFB\u7B2C\u4E00\u4E2A\u5DE5\u4F5C\u8868"))), /*#__PURE__*/React.createElement("p", {
      className: "muted",
      style: {
        fontSize: 12,
        lineHeight: 1.6,
        margin: "13px 2px 0"
      }
    }, "\u5BFC\u5165\u91C7\u7528", /*#__PURE__*/React.createElement("strong", {
      style: {
        color: "var(--ui-text)",
        fontWeight: 600
      }
    }, "\u300C\u6309\u6279\u6B21\u53F7\u589E\u91CF\u66F4\u65B0\u300D"), "\uFF1A\u6279\u6B21\u53F7\u5DF2\u5B58\u5728\u5219\u6309\u6240\u9009\u6A21\u5F0F\u66F4\u65B0\uFF0C\u4E0D\u5B58\u5728\u5219\u65B0\u589E\uFF1B\u56FE\u53F7\u672A\u5728\u5DE5\u827A\u6A21\u677F\u767B\u8BB0\u7684\u884C\u4F1A\u88AB\u8BB0\u4E3A\u9519\u8BEF\u5E76\u8DF3\u8FC7\u3002")), /*#__PURE__*/React.createElement("div", {
      className: "bd-modal-foot"
    }, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "md",
      onClick: onClose
    }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      disabled: !fileName,
      onClick: confirm
    }, "\u786E\u8BA4\u5BFC\u5165"))));
  }

  /* ---------------- generic popup card (弹出式卡片) ---------------- */
  const ICONBOX = {
    width: 38,
    height: 38,
    borderRadius: 10,
    background: "var(--ui-primary-soft)",
    color: "var(--ui-primary)",
    display: "grid",
    placeItems: "center",
    flex: "none"
  };
  const MODAL_X = {
    flex: "none",
    width: 30,
    height: 30,
    border: "none",
    background: "transparent",
    color: "var(--ui-muted)",
    cursor: "pointer",
    borderRadius: 8,
    display: "grid",
    placeItems: "center",
    fontSize: 18,
    lineHeight: 1
  };
  function Modal({
    title,
    desc,
    icon,
    width = 560,
    onClose,
    footer,
    children
  }) {
    useEffect(() => {
      const onKey = e => {
        if (e.key === "Escape") onClose();
      };
      document.addEventListener("keydown", onKey);
      return () => document.removeEventListener("keydown", onKey);
    }, []);
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-modal-backdrop",
      onClick: onClose
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-modal",
      role: "dialog",
      "aria-modal": "true",
      style: {
        width: "min(" + width + "px, 100%)",
        maxHeight: "calc(100vh - 48px)",
        display: "flex",
        flexDirection: "column"
      },
      onClick: e => e.stopPropagation()
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        padding: "16px 18px 14px",
        borderBottom: "1px solid var(--ui-border)",
        flex: "none"
      }
    }, icon ? /*#__PURE__*/React.createElement("span", {
      style: ICONBOX,
      "aria-hidden": "true"
    }, icon) : null, /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("h4", {
      style: {
        margin: 0,
        fontSize: 16,
        fontWeight: 600
      }
    }, title), desc ? /*#__PURE__*/React.createElement("div", {
      className: "muted",
      style: {
        fontSize: 12.5,
        marginTop: 3,
        lineHeight: 1.55
      }
    }, desc) : null), /*#__PURE__*/React.createElement("button", {
      className: "bd-modal-x",
      onClick: onClose,
      "aria-label": "\u5173\u95ED",
      style: MODAL_X
    }, "\xD7")), /*#__PURE__*/React.createElement("div", {
      style: {
        padding: "16px 18px",
        color: "var(--ui-text)",
        overflowY: "auto",
        flex: 1,
        minHeight: 0
      }
    }, children), footer ? /*#__PURE__*/React.createElement("div", {
      className: "bd-modal-foot",
      style: {
        flex: "none"
      }
    }, footer) : null));
  }

  /* ---------------- anchored filter popover ---------------- */
  function FilterPop({
    fStatus,
    setFStatus,
    fReady,
    setFReady,
    onClose
  }) {
    const {
      Button
    } = DS();
    const {
      Field
    } = B();
    useEffect(() => {
      const onKey = e => {
        if (e.key === "Escape") onClose();
      };
      document.addEventListener("keydown", onKey);
      return () => document.removeEventListener("keydown", onKey);
    }, []);
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      style: {
        position: "fixed",
        inset: 0,
        zIndex: 50
      },
      onClick: onClose
    }), /*#__PURE__*/React.createElement("div", {
      className: "bd-pop",
      role: "dialog",
      "aria-label": "\u7B5B\u9009\u6279\u6B21",
      onClick: e => e.stopPropagation()
    }, /*#__PURE__*/React.createElement("p", {
      className: "bd-pop-title"
    }, "\u6309\u6761\u4EF6\u7B5B\u9009"), /*#__PURE__*/React.createElement(Field, {
      label: "\u72B6\u6001"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: fStatus,
      onChange: e => setFStatus(e.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\uFF08\u5168\u90E8\uFF09"), Object.keys(STATUS).map(k => /*#__PURE__*/React.createElement("option", {
      key: k,
      value: k
    }, STATUS[k].label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u9F50\u5957\u663E\u793A"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: fReady,
      onChange: e => setFReady(e.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\uFF08\u5168\u90E8\uFF09"), Object.keys(READY).map(k => /*#__PURE__*/React.createElement("option", {
      key: k,
      value: k
    }, READY[k].label)))), /*#__PURE__*/React.createElement("div", {
      className: "bd-pop-foot"
    }, /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      size: "sm",
      onClick: () => {
        setFStatus("");
        setFReady("");
      }
    }, "\u6E05\u9664\u7B5B\u9009"), /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "sm",
      onClick: onClose
    }, "\u5B8C\u6210"))));
  }

  /* ============================================================ LIST */
  function BatchList({
    batches,
    setBatches,
    onOpen,
    onWiz,
    flashFn
  }) {
    const {
      Panel,
      Button,
      Badge,
      Table
    } = DS();
    const {
      Field,
      ActionCards,
      Toggle,
      StrictSeg,
      Seg,
      DateInput,
      ConfirmButton,
      Empty
    } = B();
    const [q, setQ] = useState("");
    const [fStatus, setFStatus] = useState("");
    const [fReady, setFReady] = useState("");
    const [modal, setModal] = useState(null); // "add" | "bulk"
    const [filterOpen, setFilterOpen] = useState(false);
    const [sel, setSel] = useState({});
    const [bulk, setBulk] = useState({
      priority: "",
      due_date: "",
      remark: ""
    });
    const [bulkErr, setBulkErr] = useState(null); // { scope: "sel" | "edit", msg }
    const [form, setForm] = useState({
      batch_id: "",
      part_no: "",
      quantity: "",
      due_date: "",
      priority: "normal",
      ready_status: "yes",
      ready_date: "",
      remark: "",
      strict: false,
      ready_check: false
    });
    const [errors, setErrors] = useState({});
    const setField = patch => {
      setForm(f => ({
        ...f,
        ...patch
      }));
      setErrors(e => {
        const n = {
          ...e
        };
        Object.keys(patch).forEach(k => delete n[k]);
        return n;
      });
    };
    const [PARTS] = B().usePartsStore(); // 共享零件库：在工艺模板新增/删除图号会实时反映到下拉
    // 行内提示：操作结果就近显示在工具条同一行（参照现场记录工具条的保存状态），无需把视线移到角落
    const [tip, setTip] = useState(null); // { tone: "ok"|"warning", msg, id }
    useEffect(() => {
      if (!tip) return;
      const ms = tip.tone === "warning" ? 5000 : 3200;
      const t = setTimeout(() => setTip(null), ms);
      return () => clearTimeout(t);
    }, [tip && tip.id]);
    const tipFn = (tone, msg) => setTip({
      tone,
      msg,
      id: Date.now()
    });
    const cards = [{
      title: "批量维护批次",
      desc: "按计划表整批新增或更新批次：批次号、图号、数量、交期、优先级一次写入，生成失败的行计为错误不写入。",
      maintainLabel: "批量维护批次",
      wizard: {
        kind: "batches",
        title: "批量维护批次",
        desc: "确认写入后按行创建/更新批次；批次号已存在则按导入模式处理。",
        strict: true,
        sampleRows: [{
          row_num: 2,
          status: "new",
          message: "新增批次",
          data: {
            批次号: "B202605-031",
            图号: "T-1009",
            数量: 8,
            交期: "06-02"
          }
        }, {
          row_num: 3,
          status: "update",
          message: "已存在，更新数量/交期",
          data: {
            批次号: "B202605-018",
            数量: 12,
            交期: "05-24"
          }
        }, {
          row_num: 4,
          status: "error",
          message: "图号 T-9999 不存在，需先在工艺模板登记",
          data: {
            批次号: "B202605-032",
            图号: "T-9999"
          }
        }]
      }
    }, {
      title: "导出批次清单",
      desc: "导出当前筛选下的批次（批次号、图号、数量、交期、优先级、齐套与状态），用于复核或离线分发。",
      exportLabel: "导出批次清单"
    }];
    const list = batches.filter(b => (!fStatus || b.status === fStatus) && (!fReady || b.ready_status === fReady) && (!q || (b.batch_id + b.part_no + partName(b.part_no)).toLowerCase().includes(q.toLowerCase())));
    const selIds = Object.keys(sel).filter(k => sel[k]);
    const selCount = selIds.length;
    useEffect(() => {
      setBulkErr(e => e && e.scope === "sel" && selCount ? null : e);
    }, [selCount]);
    useEffect(() => {
      setBulkErr(e => e && e.scope === "edit" && (bulk.priority || bulk.due_date || bulk.remark) ? null : e);
    }, [bulk.priority, bulk.due_date, bulk.remark]);
    const toggleAll = on => {
      const m = {};
      if (on) list.forEach(b => m[b.batch_id] = true);
      setSel(m);
    };
    const Progress = ({
      ops
    }) => {
      if (!ops.length) return /*#__PURE__*/React.createElement("span", {
        className: "muted",
        style: {
          fontSize: 12.5
        }
      }, "\u672A\u751F\u6210");
      const d = doneCount(ops),
        t = ops.length,
        pct = Math.round(d / t * 100);
      const col = pct === 100 ? "var(--ui-success)" : pct === 0 ? "var(--ui-muted)" : "var(--ui-primary)";
      return /*#__PURE__*/React.createElement("div", {
        style: {
          display: "flex",
          alignItems: "center",
          gap: 8
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          position: "relative",
          width: 54,
          height: 6,
          borderRadius: 999,
          background: "var(--ui-surface-soft)",
          overflow: "hidden",
          flex: "none"
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          position: "absolute",
          inset: 0,
          width: pct + "%",
          background: col,
          borderRadius: 999
        }
      })), /*#__PURE__*/React.createElement("span", {
        style: {
          fontVariantNumeric: "tabular-nums",
          fontSize: 12.5,
          color: "var(--ui-muted)"
        }
      }, d, " / ", t));
    };
    const cols = [{
      key: "sel",
      title: /*#__PURE__*/React.createElement("input", {
        type: "checkbox",
        "aria-label": "\u5168\u9009",
        checked: list.length > 0 && selCount === list.length,
        onChange: e => toggleAll(e.target.checked)
      }),
      width: 44,
      render: r => /*#__PURE__*/React.createElement("input", {
        type: "checkbox",
        "aria-label": "选择 " + r.batch_id,
        checked: !!sel[r.batch_id],
        onChange: e => setSel(s => ({
          ...s,
          [r.batch_id]: e.target.checked
        }))
      })
    }, {
      key: "batch_id",
      title: "批次号",
      width: 130,
      render: r => /*#__PURE__*/React.createElement("a", {
        className: "bd-link",
        onClick: () => onOpen(r.batch_id)
      }, r.batch_id)
    }, {
      key: "part_no",
      title: "图号",
      width: 150,
      render: r => /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("strong", {
        style: {
          fontWeight: 600
        }
      }, r.part_no), " ", /*#__PURE__*/React.createElement("span", {
        className: "muted",
        style: {
          fontSize: 12
        }
      }, partName(r.part_no)))
    }, {
      key: "quantity",
      title: "数量",
      width: 70,
      align: "right",
      render: r => /*#__PURE__*/React.createElement("span", {
        style: {
          fontVariantNumeric: "tabular-nums"
        }
      }, r.quantity)
    }, {
      key: "due_date",
      title: "交期",
      width: 110,
      nowrap: true,
      render: r => r.due_date ? /*#__PURE__*/React.createElement("span", {
        style: {
          fontVariantNumeric: "tabular-nums"
        }
      }, r.due_date) : /*#__PURE__*/React.createElement("span", {
        className: "muted"
      }, "-")
    }, {
      key: "prog",
      title: "工序进度",
      width: 130,
      render: r => /*#__PURE__*/React.createElement(Progress, {
        ops: r.ops
      })
    }, {
      key: "priority",
      title: "优先级",
      width: 90,
      render: r => /*#__PURE__*/React.createElement(Badge, {
        tone: PRIORITY[r.priority].tone,
        dot: r.priority !== "normal"
      }, PRIORITY[r.priority].label)
    }, {
      key: "ready_status",
      title: "齐套显示",
      width: 96,
      render: r => /*#__PURE__*/React.createElement(Badge, {
        tone: READY[r.ready_status].tone,
        dot: true
      }, READY[r.ready_status].label)
    }, {
      key: "status",
      title: "状态",
      width: 86,
      render: r => /*#__PURE__*/React.createElement(Badge, {
        tone: STATUS[r.status].tone,
        dot: true
      }, STATUS[r.status].label)
    }, {
      key: "act",
      title: "操作",
      width: 170,
      render: r => /*#__PURE__*/React.createElement("div", {
        className: "bd-cell-actions"
      }, /*#__PURE__*/React.createElement(Button, {
        variant: "secondary",
        size: "sm",
        onClick: () => onOpen(r.batch_id)
      }, "\u67E5\u770B/\u7F16\u8F91"), /*#__PURE__*/React.createElement(ConfirmButton, {
        label: "\u5220\u9664",
        title: "删除批次 " + r.batch_id + "？",
        body: /*#__PURE__*/React.createElement(React.Fragment, null, "\u5220\u9664\u4F1A\u4E00\u5E76\u6E05\u9664\u8BE5\u6279\u6B21\u4E0B\u7684", /*#__PURE__*/React.createElement("strong", null, "\u5DE5\u5E8F\u4E0E\u6392\u7A0B\u8BB0\u5F55"), "\u3002\u5DF2\u8FDB\u5165\u52A0\u5DE5/\u5DF2\u5B8C\u6210\u7684\u6279\u6B21\u8BF7\u8C28\u614E\u64CD\u4F5C\u3002\u786E\u8BA4\u5220\u9664\u5417\uFF1F"),
        onConfirm: () => {
          setBatches(arr => arr.filter(b => b.batch_id !== r.batch_id));
          tipFn("ok", "已删除批次 " + r.batch_id);
        }
      }))
    }];
    const submit = () => {
      const errs = {};
      if (!form.batch_id) errs.batch_id = "请填写批次号。";else if (batches.some(b => b.batch_id === form.batch_id)) errs.batch_id = "批次号 " + form.batch_id + " 已存在。";
      if (!form.part_no) errs.part_no = "请选择图号。";
      if (!form.quantity) errs.quantity = "请填写数量。";
      if (Object.keys(errs).length) {
        setErrors(errs);
        return;
      }
      setErrors({});
      setBatches(arr => [{
        batch_id: form.batch_id,
        part_no: form.part_no,
        quantity: Number(form.quantity) || 0,
        due_date: form.due_date,
        ready_date: form.ready_date,
        priority: form.priority,
        ready_status: form.ready_status,
        remark: form.remark,
        status: "pending",
        ops: []
      }, ...arr]);
      tipFn("ok", "已新增批次 " + form.batch_id + "（待排）");
      setForm({
        batch_id: "",
        part_no: "",
        quantity: "",
        due_date: "",
        priority: "normal",
        ready_status: "yes",
        ready_date: "",
        remark: "",
        strict: false,
        ready_check: false
      });
      setModal(null);
    };
    const runBulk = kind => {
      if (!selCount) {
        setBulkErr({
          scope: "sel",
          msg: "请先勾选要操作的批次。"
        });
        return;
      }
      if (kind === "delete") {
        setBulkErr(null);
        setBatches(arr => arr.filter(b => !sel[b.batch_id]));
        setSel({});
        tipFn("ok", "已删除所选 " + selCount + " 个批次");
        return;
      }
      if (kind === "copy") {
        setBulkErr(null);
        setBatches(arr => {
          const add = arr.filter(b => sel[b.batch_id]).map(b => {
            const m = b.batch_id.match(/(\d+)$/);
            const next = m ? b.batch_id.slice(0, m.index) + String(Number(m[1]) + 1).padStart(m[1].length, "0") : b.batch_id + "-copy";
            return {
              ...b,
              batch_id: next,
              status: "pending",
              ops: b.ops.map(o => ({
                ...o,
                op_code: next + "-" + String(o.seq).padStart(2, "0"),
                done: false
              }))
            };
          });
          return [...add, ...arr];
        });
        tipFn("ok", "已复制所选 " + selCount + " 个批次");
        return;
      }
      // modify
      if (!bulk.priority && !bulk.due_date && !bulk.remark) {
        setBulkErr({
          scope: "edit",
          msg: "请至少填写一个要修改的字段。"
        });
        return;
      }
      setBulkErr(null);
      setBatches(arr => arr.map(b => sel[b.batch_id] ? {
        ...b,
        ...(bulk.priority ? {
          priority: bulk.priority
        } : {}),
        ...(bulk.due_date ? {
          due_date: bulk.due_date
        } : {}),
        ...(bulk.remark ? {
          remark: bulk.remark
        } : {})
      } : b));
      tipFn("ok", "已批量修改所选 " + selCount + " 个批次");
      setBulk({
        priority: "",
        due_date: "",
        remark: ""
      });
      setModal(null);
    };
    const activeFilters = (fStatus ? 1 : 0) + (fReady ? 1 : 0);
    const filtered = fStatus || fReady;
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(Panel, {
      title: "\u6279\u6B21\u5217\u8868",
      description: "\u6279\u6B21\u662F\u6392\u4EA7\u7684\u6700\u5C0F\u5355\u4F4D\u3002\u65B0\u589E\u3001\u6279\u91CF\u7EF4\u62A4\u4E0E\u7B5B\u9009\u5DF2\u6536\u8FDB\u4E0A\u65B9\u6309\u94AE\uFF0C\u5217\u8868\u4FDD\u6301\u7B80\u6D01\uFF1B\u6279\u6B21\u53F7\u8054\u52A8\u8BE6\u60C5\uFF0C\u5220\u9664\u4F1A\u4E00\u5E76\u6E05\u9664\u8BE5\u6279\u6B21\u7684\u5DE5\u5E8F\u4E0E\u6392\u7A0B\u8BB0\u5F55\u3002"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-listbar"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-listbar-search"
    }, /*#__PURE__*/React.createElement("svg", {
      viewBox: "0 0 24 24",
      width: "16",
      height: "16",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "2",
      strokeLinecap: "round",
      strokeLinejoin: "round"
    }, /*#__PURE__*/React.createElement("circle", {
      cx: "11",
      cy: "11",
      r: "7"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M21 21l-4.3-4.3"
    })), /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u641C\u7D22\u6279\u6B21\u53F7\u3001\u56FE\u53F7\u3001\u96F6\u4EF6\u540D\u2026",
      value: q,
      onChange: e => setQ(e.target.value)
    })), /*#__PURE__*/React.createElement("div", {
      className: "bd-listbar-actions"
    }, tip ? /*#__PURE__*/React.createElement("span", {
      className: "bd-listbar-tip",
      key: tip.id,
      style: {
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        fontSize: 12.5,
        whiteSpace: "nowrap",
        marginRight: 2,
        color: tip.tone === "warning" ? "var(--ui-warning-text)" : "var(--ui-success-text)"
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 7,
        height: 7,
        borderRadius: "50%",
        flex: "none",
        background: tip.tone === "warning" ? "var(--ui-warning)" : "var(--ui-success)"
      }
    }), tip.msg) : null, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(Button, {
      variant: filtered ? "primary" : "secondary",
      size: "md",
      onClick: () => setFilterOpen(o => !o)
    }, /*#__PURE__*/React.createElement("svg", {
      viewBox: "0 0 24 24",
      width: "14",
      height: "14",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "1.8",
      strokeLinecap: "round",
      strokeLinejoin: "round",
      style: {
        marginRight: 6,
        verticalAlign: "-2px"
      }
    }, /*#__PURE__*/React.createElement("path", {
      d: "M3 5h18l-7 8v5l-4 2v-7z"
    })), "\u7B5B\u9009", activeFilters ? /*#__PURE__*/React.createElement("span", {
      className: "bd-filter-count"
    }, activeFilters) : null), filterOpen ? /*#__PURE__*/React.createElement(FilterPop, {
      fStatus: fStatus,
      setFStatus: setFStatus,
      fReady: fReady,
      setFReady: setFReady,
      onClose: () => setFilterOpen(false)
    }) : null), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "md",
      onClick: () => onWiz(cards[0].wizard)
    }, /*#__PURE__*/React.createElement("svg", {
      viewBox: "0 0 24 24",
      width: "14",
      height: "14",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "1.8",
      strokeLinecap: "round",
      strokeLinejoin: "round",
      style: {
        marginRight: 6,
        verticalAlign: "-2px"
      }
    }, /*#__PURE__*/React.createElement("path", {
      d: "M12 3v11m0 0l-4-4m4 4l4-4M5 19h14"
    })), "\u6279\u91CF\u5BFC\u5165"), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "md",
      onClick: () => {
        if (!selCount) {
          tipFn("warning", "请先勾选要导出的批次");
          return;
        }
        tipFn("ok", "已导出所选 " + selCount + " 个批次清单");
      }
    }, /*#__PURE__*/React.createElement("svg", {
      viewBox: "0 0 24 24",
      width: "14",
      height: "14",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "1.8",
      strokeLinecap: "round",
      strokeLinejoin: "round",
      style: {
        marginRight: 6,
        verticalAlign: "-2px"
      }
    }, /*#__PURE__*/React.createElement("path", {
      d: "M12 16V4M7 9l5-5 5 5"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M5 16v4h14v-4"
    })), "\u6279\u91CF\u5BFC\u51FA", selCount ? /*#__PURE__*/React.createElement("span", {
      className: "bd-filter-count"
    }, selCount) : null), /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: () => setModal("add")
    }, /*#__PURE__*/React.createElement("svg", {
      viewBox: "0 0 24 24",
      width: "14",
      height: "14",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "2",
      strokeLinecap: "round",
      strokeLinejoin: "round",
      style: {
        marginRight: 6,
        verticalAlign: "-2px"
      }
    }, /*#__PURE__*/React.createElement("path", {
      d: "M12 5v14M5 12h14"
    })), "\u65B0\u589E\u6279\u6B21"))), filtered ? /*#__PURE__*/React.createElement("div", {
      className: "bd-filterchips"
    }, fStatus ? /*#__PURE__*/React.createElement("span", {
      className: "bd-filterchip"
    }, "\u72B6\u6001\uFF1A", /*#__PURE__*/React.createElement("b", null, STATUS[fStatus].label), /*#__PURE__*/React.createElement("button", {
      "aria-label": "\u6E05\u9664\u72B6\u6001\u7B5B\u9009",
      onClick: () => setFStatus("")
    }, "\xD7")) : null, fReady ? /*#__PURE__*/React.createElement("span", {
      className: "bd-filterchip"
    }, "\u9F50\u5957\uFF1A", /*#__PURE__*/React.createElement("b", null, READY[fReady].label), /*#__PURE__*/React.createElement("button", {
      "aria-label": "\u6E05\u9664\u9F50\u5957\u7B5B\u9009",
      onClick: () => setFReady("")
    }, "\xD7")) : null, /*#__PURE__*/React.createElement("a", {
      className: "bd-link",
      style: {
        fontSize: 12.5
      },
      onClick: () => {
        setFStatus("");
        setFReady("");
      }
    }, "\u6E05\u9664\u5168\u90E8")) : null, list.length ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "bd-table-scroll"
    }, /*#__PURE__*/React.createElement(Table, {
      columns: cols,
      rows: list,
      rowKey: "batch_id"
    })), selCount ? /*#__PURE__*/React.createElement("div", {
      className: "bd-selbar"
    }, /*#__PURE__*/React.createElement("span", {
      className: "selbar-count"
    }, "\u5DF2\u9009 ", /*#__PURE__*/React.createElement("strong", null, selCount), " \u4E2A\u6279\u6B21"), /*#__PURE__*/React.createElement("div", {
      className: "selbar-actions"
    }, bulkErr && bulkErr.scope === "sel" ? /*#__PURE__*/React.createElement("span", {
      className: "bd-inline-err"
    }, bulkErr.msg) : null, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "md",
      onClick: () => {
        setBulkErr(null);
        setModal("bulk");
      }
    }, "\u6279\u91CF\u4FEE\u6539"), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "md",
      onClick: () => runBulk("copy")
    }, "\u590D\u5236\u6240\u9009"), /*#__PURE__*/React.createElement(ConfirmButton, {
      label: "\u5220\u9664\u6240\u9009",
      size: "md",
      variant: "secondary",
      btnStyle: GHOST_DANGER,
      title: "\u5220\u9664\u6240\u9009\u6279\u6B21\uFF1F",
      body: "\u4F1A\u4E00\u5E76\u6E05\u9664\u8FD9\u4E9B\u6279\u6B21\u4E0B\u7684\u5DE5\u5E8F\u4E0E\u6392\u7A0B\u8BB0\u5F55\uFF08\u5982\u6709\uFF09\u3002\u786E\u8BA4\u7EE7\u7EED\u5417\uFF1F",
      onConfirm: () => runBulk("delete")
    }))) : null) : /*#__PURE__*/React.createElement(Empty, {
      title: filtered || q ? "当前条件下暂无批次" : "暂无批次",
      desc: filtered || q ? "可调整筛选或搜索，或用「新增批次」「批量维护」录入。" : "点击右上角「新增批次」录入，或用「批量维护」按计划表整批导入。"
    })), modal === "add" ? /*#__PURE__*/React.createElement(Modal, {
      title: "\u65B0\u589E\u6279\u6B21",
      width: 680,
      onClose: () => setModal(null),
      desc: "\u9009\u56FE\u53F7 + \u586B\u6570\u91CF\u4E0E\u4EA4\u671F\u5373\u53EF\u521B\u5EFA\uFF1B\u5DE5\u5E8F\u5728\u8BE6\u60C5\u91CC\u6309\u5DE5\u827A\u6A21\u677F\u751F\u6210\u540E\u8865\u9F50\u8D44\u6E90\u3002",
      icon: /*#__PURE__*/React.createElement("svg", {
        viewBox: "0 0 24 24",
        width: "20",
        height: "20",
        fill: "none",
        stroke: "currentColor",
        strokeWidth: "1.8",
        strokeLinecap: "round",
        strokeLinejoin: "round"
      }, /*#__PURE__*/React.createElement("path", {
        d: "M12 5v14M5 12h14"
      })),
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, Object.keys(errors).length ? /*#__PURE__*/React.createElement("span", {
        className: "bd-form-error",
        style: {
          marginRight: "auto"
        }
      }, "\u8BF7\u586B\u5199\u6807\u7EA2\u7684\u5FC5\u586B\u9879") : null, /*#__PURE__*/React.createElement(Button, {
        variant: "secondary",
        size: "md",
        onClick: () => setModal(null)
      }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
        variant: "primary",
        size: "md",
        onClick: submit
      }, "\u521B\u5EFA\u6279\u6B21"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-fieldset"
    }, /*#__PURE__*/React.createElement("p", {
      className: "bd-fieldset-label"
    }, "\u6807\u8BC6"), /*#__PURE__*/React.createElement("div", {
      className: "bd-grid-cols",
      style: {
        gridTemplateColumns: "minmax(0,1.3fr) minmax(0,1.7fr) 110px"
      }
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u6279\u6B21\u53F7",
      required: true,
      error: errors.batch_id
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1AB202605-031",
      value: form.batch_id,
      onChange: e => setField({
        batch_id: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u56FE\u53F7",
      required: true,
      error: errors.part_no
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: form.part_no,
      onChange: e => setField({
        part_no: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\uFF08\u8BF7\u9009\u62E9\uFF09"), PARTS.map(p => /*#__PURE__*/React.createElement("option", {
      key: p.part_no,
      value: p.part_no
    }, p.part_no, " \xB7 ", p.part_name)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u6570\u91CF",
      required: true,
      error: errors.quantity
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input num",
      type: "number",
      min: "1",
      step: "1",
      placeholder: "50",
      value: form.quantity,
      onChange: e => setField({
        quantity: e.target.value
      })
    })))), /*#__PURE__*/React.createElement("div", {
      className: "bd-fieldset"
    }, /*#__PURE__*/React.createElement("p", {
      className: "bd-fieldset-label"
    }, "\u8BA1\u5212\u4E0E\u9F50\u5957"), /*#__PURE__*/React.createElement("div", {
      className: "bd-grid-cols",
      style: {
        gridTemplateColumns: "repeat(2, minmax(0,1fr))"
      }
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u4EA4\u671F",
      hint: "\u53EF\u9009\uFF1B\u4E0D\u586B\u5219\u4E0D\u53C2\u4E0E\u4EA4\u671F\u6392\u5E8F\u3002"
    }, /*#__PURE__*/React.createElement(DateInput, {
      value: form.due_date,
      onChange: v => setForm({
        ...form,
        due_date: v
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u4F18\u5148\u7EA7"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: form.priority,
      onChange: e => setForm({
        ...form,
        priority: e.target.value
      })
    }, Object.keys(PRIORITY).map(k => /*#__PURE__*/React.createElement("option", {
      key: k,
      value: k
    }, PRIORITY[k].label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u9F50\u5957\u663E\u793A"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: form.ready_status,
      onChange: e => setForm({
        ...form,
        ready_status: e.target.value
      })
    }, Object.keys(READY).map(k => /*#__PURE__*/React.createElement("option", {
      key: k,
      value: k
    }, READY[k].label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u9F50\u5957\u65E5\u671F",
      hint: "\u5F00\u542F\u9F50\u5957\u68C0\u67E5\u65F6\u7528\u4E8E\u6821\u9A8C\uFF1B\u53EF\u7559\u7A7A\u3002"
    }, /*#__PURE__*/React.createElement(DateInput, {
      value: form.ready_date,
      onChange: v => setForm({
        ...form,
        ready_date: v
      })
    }))), /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 14
      }
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u5907\u6CE8",
      wide: true
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u53EF\u9009",
      value: form.remark,
      onChange: e => setForm({
        ...form,
        remark: e.target.value
      })
    })))), /*#__PURE__*/React.createElement("div", {
      className: "bd-switch-list",
      style: {
        marginTop: 16,
        paddingTop: 16,
        borderTop: "1px dashed var(--ui-border)"
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-switch-row bd-switch-row--flat"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-switch-main"
    }, /*#__PURE__*/React.createElement("span", {
      className: "bd-switch-label"
    }, "\u6570\u636E\u6821\u9A8C"), /*#__PURE__*/React.createElement("span", {
      className: "bd-switch-note"
    }, form.strict ? "按零件路线生成工序时，缺工种、缺供应商或外协周期不正确会停止创建并提示原因。" : "能确认的工序先生成，缺外协周期先按 1 天记录并提醒补正。")), /*#__PURE__*/React.createElement("div", {
      className: "bd-switch-ctrl"
    }, /*#__PURE__*/React.createElement(StrictSeg, {
      checked: form.strict,
      onChange: v => setForm({
        ...form,
        strict: v
      }),
      ariaLabel: "\u6570\u636E\u6821\u9A8C"
    }))))) : null, modal === "bulk" ? /*#__PURE__*/React.createElement(Modal, {
      title: "\u6279\u91CF\u4FEE\u6539\u6279\u6B21",
      width: 560,
      onClose: () => setModal(null),
      desc: "将对已选的 " + selCount + " 个批次生效 · 仅更新已填字段，留空不覆盖。",
      icon: /*#__PURE__*/React.createElement("svg", {
        viewBox: "0 0 24 24",
        width: "20",
        height: "20",
        fill: "none",
        stroke: "currentColor",
        strokeWidth: "1.8",
        strokeLinecap: "round",
        strokeLinejoin: "round"
      }, /*#__PURE__*/React.createElement("path", {
        d: "M12 20h9"
      }), /*#__PURE__*/React.createElement("path", {
        d: "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"
      })),
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, bulkErr && bulkErr.scope === "edit" ? /*#__PURE__*/React.createElement("span", {
        className: "bd-inline-err",
        style: {
          marginRight: "auto"
        }
      }, bulkErr.msg) : null, /*#__PURE__*/React.createElement(Button, {
        variant: "secondary",
        size: "md",
        onClick: () => setModal(null)
      }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
        variant: "primary",
        size: "md",
        onClick: () => runBulk("modify")
      }, "\u4FEE\u6539\u6240\u9009"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u6279\u91CF\u4F18\u5148\u7EA7\uFF08\u53EF\u9009\uFF09"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: bulk.priority,
      onChange: e => setBulk({
        ...bulk,
        priority: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\uFF08\u4E0D\u4FEE\u6539\uFF09"), Object.keys(PRIORITY).map(k => /*#__PURE__*/React.createElement("option", {
      key: k,
      value: k
    }, PRIORITY[k].label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u6279\u91CF\u4EA4\u671F\uFF08\u53EF\u9009\uFF09"
    }, /*#__PURE__*/React.createElement(DateInput, {
      value: bulk.due_date,
      onChange: v => setBulk({
        ...bulk,
        due_date: v
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u6279\u91CF\u5907\u6CE8\uFF08\u53EF\u9009\uFF09",
      wide: true
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u586B\u5199\u5219\u8986\u76D6\u5907\u6CE8\uFF0C\u7559\u7A7A\u4E0D\u4FEE\u6539",
      value: bulk.remark,
      onChange: e => setBulk({
        ...bulk,
        remark: e.target.value
      })
    })))) : null);
  }

  /* ============================================================ DETAIL */
  function BatchDetail({
    batch,
    onBack,
    onUpdate,
    onDelete,
    flashFn
  }) {
    const {
      Panel,
      Button,
      Badge,
      Table
    } = DS();
    const {
      Field,
      Toggle,
      DateInput,
      ConfirmButton,
      SummaryGrid,
      Empty
    } = B();
    const [base, setBase] = useState({
      quantity: batch.quantity,
      due_date: batch.due_date,
      priority: batch.priority,
      ready_status: batch.ready_status,
      ready_date: batch.ready_date,
      remark: batch.remark
    });
    const [strict, setStrict] = useState(false);
    const ops = batch.ops;
    const internal = ops.filter(o => o.source === "internal").length;
    const external = ops.filter(o => o.source === "external").length;
    const gaps = gapCount(ops);
    const regenerate = () => {
      // 按零件工艺模板（共享数据源）刷新：以本批次图号去工艺模板取最新工序，而非批次旧快照。
      const tplPart = window.BD.findPart(batch.part_no);
      const tmpl = tplPart && tplPart.ops.length ? tplPart.ops : [];
      onUpdate(batch.batch_id, {
        ops: tmpl.map(o => ({
          ...o,
          op_code: batch.batch_id + "-" + String(o.seq).padStart(2, "0"),
          done: false
        }))
      });
      flashFn(tmpl.length ? "ok" : "warning", tmpl.length ? "已按最新工艺模板刷新本批次工序（已清空之前补充的设备/人员/工时）。" : "该图号在工艺模板中暂无工序，请先到「排产基础资料」维护路线。");
    };
    const opCols = [{
      key: "op_code",
      title: "工序编码",
      width: 150,
      render: r => /*#__PURE__*/React.createElement("code", {
        className: "bd-code",
        title: r.op_code
      }, r.op_code)
    }, {
      key: "seq",
      title: "工序",
      width: 70,
      align: "right",
      render: r => /*#__PURE__*/React.createElement("span", {
        style: {
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          fontVariantNumeric: "tabular-nums"
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          width: 3,
          height: 16,
          borderRadius: 2,
          background: r.source === "external" ? "var(--ui-warning)" : "var(--ui-primary)"
        }
      }), r.seq)
    }, {
      key: "op_type",
      title: "工种",
      width: 96
    }, {
      key: "source",
      title: "归属",
      width: 84,
      render: r => /*#__PURE__*/React.createElement(Badge, {
        tone: r.source === "external" ? "warning" : "notice",
        dot: true
      }, r.source === "external" ? "外协" : "自制")
    }, {
      key: "config",
      title: "资源补充",
      render: r => /*#__PURE__*/React.createElement(OpConfigCell, {
        op: r,
        batch: batch,
        onUpdate: onUpdate,
        flashFn: flashFn
      })
    }, {
      key: "done",
      title: "完工",
      width: 96,
      render: r => {
        const idx = ops.findIndex(x => x.seq === r.seq);
        const prevDone = idx === 0 || ops.slice(0, idx).every(x => x.done);
        const tone = r.done ? "ok" : prevDone ? "notice" : "secondary";
        return /*#__PURE__*/React.createElement(Badge, {
          tone: tone,
          dot: true
        }, r.done ? "已完工" : prevDone ? "进行中" : "待开工");
      }
    }];
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(Panel, {
      title: "批次详情 · " + batch.batch_id,
      description: "\u7EF4\u62A4\u5355\u4E2A\u6279\u6B21\u7684\u57FA\u7840\u4FE1\u606F\uFF0C\u5E76\u8865\u9F50\u5DE5\u5E8F\u6240\u9700\u7684\u8BBE\u5907\u3001\u4EBA\u5458\u3001\u5DE5\u65F6\u4E0E\u5916\u534F\u5468\u671F\u3002",
      headerRight: /*#__PURE__*/React.createElement("div", {
        className: "bd-cell-actions"
      }, /*#__PURE__*/React.createElement(Button, {
        variant: "ghost",
        size: "sm",
        onClick: onBack
      }, "\u2190 \u8FD4\u56DE\u5217\u8868"), /*#__PURE__*/React.createElement(ConfirmButton, {
        label: "\u5220\u9664\u6279\u6B21",
        size: "sm",
        title: "删除批次 " + batch.batch_id + "？",
        body: /*#__PURE__*/React.createElement(React.Fragment, null, "\u5220\u9664\u4F1A\u4E00\u5E76\u6E05\u9664\u8BE5\u6279\u6B21\u7684", /*#__PURE__*/React.createElement("strong", null, "\u5DE5\u5E8F\u4E0E\u6392\u7A0B\u8BB0\u5F55"), "\u3002\u786E\u8BA4\u5220\u9664\u5417\uFF1F"),
        onConfirm: () => {
          onDelete(batch.batch_id);
          flashFn("ok", "已删除批次 " + batch.batch_id + "。");
          onBack();
        }
      }))
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-meta-row"
    }, /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u56FE\u53F7\uFF1A"), /*#__PURE__*/React.createElement("strong", null, batch.part_no), " ", partName(batch.part_no)), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u6570\u91CF\uFF1A"), /*#__PURE__*/React.createElement("strong", {
      style: {
        fontVariantNumeric: "tabular-nums"
      }
    }, batch.quantity)), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u4EA4\u671F\uFF1A"), /*#__PURE__*/React.createElement("strong", {
      style: {
        fontVariantNumeric: "tabular-nums"
      }
    }, batch.due_date || "-")), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u4F18\u5148\u7EA7\uFF1A"), /*#__PURE__*/React.createElement(Badge, {
      tone: PRIORITY[batch.priority].tone,
      dot: batch.priority !== "normal"
    }, PRIORITY[batch.priority].label)), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u9F50\u5957\uFF1A"), /*#__PURE__*/React.createElement(Badge, {
      tone: READY[batch.ready_status].tone,
      dot: true
    }, READY[batch.ready_status].label)), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u72B6\u6001\uFF1A"), /*#__PURE__*/React.createElement(Badge, {
      tone: STATUS[batch.status].tone,
      dot: true
    }, STATUS[batch.status].label)))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u2460 \u6279\u6B21\u57FA\u7840\u4FE1\u606F",
      description: "\u6279\u6B21\u53F7\u4E0E\u56FE\u53F7\u521B\u5EFA\u540E\u4E0D\u53EF\u6539\uFF1B\u5982\u9700\u6362\u56FE\u53F7\u8BF7\u65B0\u5EFA\u6279\u6B21\u3002"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u6279\u6B21\u53F7"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      value: batch.batch_id,
      disabled: true
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u56FE\u53F7"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      value: batch.part_no + " · " + partName(batch.part_no),
      disabled: true
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u6570\u91CF",
      required: true
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input num",
      type: "number",
      min: "1",
      value: base.quantity,
      onChange: e => setBase({
        ...base,
        quantity: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u4EA4\u671F"
    }, /*#__PURE__*/React.createElement(DateInput, {
      value: base.due_date,
      onChange: v => setBase({
        ...base,
        due_date: v
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u4F18\u5148\u7EA7"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: base.priority,
      onChange: e => setBase({
        ...base,
        priority: e.target.value
      })
    }, Object.keys(PRIORITY).map(k => /*#__PURE__*/React.createElement("option", {
      key: k,
      value: k
    }, PRIORITY[k].label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u9F50\u5957\u663E\u793A"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: base.ready_status,
      onChange: e => setBase({
        ...base,
        ready_status: e.target.value
      })
    }, Object.keys(READY).map(k => /*#__PURE__*/React.createElement("option", {
      key: k,
      value: k
    }, READY[k].label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u9F50\u5957\u65E5\u671F"
    }, /*#__PURE__*/React.createElement(DateInput, {
      value: base.ready_date,
      onChange: v => setBase({
        ...base,
        ready_date: v
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5907\u6CE8",
      wide: true
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u53EF\u9009",
      value: base.remark,
      onChange: e => setBase({
        ...base,
        remark: e.target.value
      })
    }))), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer"
    }, /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: () => {
        onUpdate(batch.batch_id, {
          quantity: Number(base.quantity) || 0,
          due_date: base.due_date,
          priority: base.priority,
          ready_status: base.ready_status,
          ready_date: base.ready_date,
          remark: base.remark
        });
        flashFn("ok", "已保存批次基础信息。");
      }
    }, "\u4FDD\u5B58"))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u2461 \u6309\u5DE5\u827A\u6A21\u677F\u540C\u6B65\u5DE5\u5E8F",
      description: "\u5DE5\u827A\u8DEF\u7EBF\u6216\u6A21\u677F\u8C03\u6574\u540E\uFF0C\u53EF\u540C\u6B65\u5230\u672C\u6279\u6B21\uFF1B\u540C\u6B65\u4F1A\u91CD\u5EFA\u5DE5\u5E8F\u6E05\u5355\u3002"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Toggle, {
      checked: strict,
      onChange: setStrict,
      label: "\u8D44\u6599\u4E0D\u5B8C\u6574\u5C31\u505C\u4E0B\uFF08\u4E25\u683C\u6A21\u5F0F\uFF09",
      help: "\u52FE\u9009\u540E\uFF1A\u7F3A\u5DE5\u79CD\u3001\u7F3A\u4F9B\u5E94\u5546\u6216\u5916\u534F\u5468\u671F\u4E0D\u6B63\u786E\u65F6\u505C\u6B62\u5237\u65B0\u5E76\u63D0\u793A\u539F\u56E0\u3002\u4E0D\u52FE\u9009\uFF1A\u80FD\u786E\u8BA4\u7684\u5DE5\u5E8F\u7EE7\u7EED\u751F\u6210\uFF0C\u7F3A\u5916\u534F\u5468\u671F\u5148\u6309 1 \u5929\u8BB0\u5F55\u5E76\u63D0\u9192\u8865\u6B63\u3002"
    })), /*#__PURE__*/React.createElement("div", {
      className: "bd-flash tone-warning",
      style: {
        marginTop: 4
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "bd-flash-dot"
    }), /*#__PURE__*/React.createElement("span", null, "\u5237\u65B0\u4F1A\u6E05\u7A7A\u672C\u6279\u6B21\u5DF2\u8865\u7684\u8BBE\u5907\u3001\u4EBA\u5458\u3001\u5DE5\u65F6\u3001\u4F9B\u5E94\u5546\u548C\u5916\u534F\u5468\u671F\u3002\u8BF7\u786E\u8BA4\u8FD9\u4E9B\u5185\u5BB9\u53EF\u4EE5\u91CD\u65B0\u586B\u5199\u3002")), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer"
    }, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "md",
      onClick: regenerate
    }, "\u6309\u6700\u65B0\u5DE5\u827A\u6A21\u677F\u5237\u65B0\u672C\u6279\u6B21\u5DE5\u5E8F"))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u2462 \u5DE5\u5E8F\u6982\u51B5"
    }, /*#__PURE__*/React.createElement(SummaryGrid, {
      items: [{
        label: "工序总数",
        value: ops.length,
        sev: "notice"
      }, {
        label: "自制工序",
        value: internal,
        sev: "notice"
      }, {
        label: "外协工序",
        value: external,
        sev: "notice"
      }, {
        label: "已完工",
        value: doneCount(ops),
        sev: "ok"
      }, {
        label: "待补资源",
        value: gaps,
        sev: gaps ? "warning" : "ok"
      }]
    }), gaps ? /*#__PURE__*/React.createElement("p", {
      className: "bd-cell-note",
      style: {
        marginTop: 12,
        color: "var(--ui-warning-text)"
      }
    }, "\u4ECD\u6709 ", gaps, " \u9053\u5DE5\u5E8F\u7F3A\u8BBE\u5907/\u4EBA\u5458\u6216\u5916\u534F\u4F9B\u5E94\u5546/\u5468\u671F\uFF1B\u6392\u4EA7\u524D\u8BF7\u5728\u4E0B\u65B9\u8865\u9F50\uFF0C\u6216\u5728\u9AD8\u7EA7\u8BBE\u7F6E\u4E2D\u5F00\u542F\u81EA\u52A8\u5206\u914D\u3002") : null), /*#__PURE__*/React.createElement(Panel, {
      title: "\u2463 \u6279\u6B21\u5DE5\u5E8F",
      description: "\u84DD\u8272=\u81EA\u5236\uFF08\u8865\u8BBE\u5907/\u4EBA\u5458/\u5DE5\u65F6\uFF09\uFF0C\u6A59\u8272=\u5916\u534F\uFF08\u8865\u4F9B\u5E94\u5546/\u5468\u671F\uFF09\u3002\u8BBE\u5907\u4E0E\u4EBA\u5458\u7684\u7EC4\u5408\u987B\u6EE1\u8DB3\u300C\u4EBA\u5458-\u8BBE\u5907\u5173\u8054\u300D\u3002"
    }, ops.length ? /*#__PURE__*/React.createElement("div", {
      className: "bd-table-scroll bd-op-table"
    }, /*#__PURE__*/React.createElement(Table, {
      columns: opCols,
      rows: ops.map(o => ({
        ...o,
        id: o.seq
      })),
      rowKey: "seq"
    })) : /*#__PURE__*/React.createElement(Empty, {
      title: "\u8BE5\u6279\u6B21\u5C1A\u672A\u751F\u6210\u5DE5\u5E8F",
      desc: "\u70B9\u51FB\u4E0A\u65B9\u300C\u6309\u6700\u65B0\u5DE5\u827A\u6A21\u677F\u5237\u65B0\u672C\u6279\u6B21\u5DE5\u5E8F\u300D\u6309\u96F6\u4EF6\u8DEF\u7EBF\u751F\u6210\u3002"
    })));
  }

  /* ---------------- per-op inline editor ---------------- */
  function OpConfigCell({
    op,
    batch,
    onUpdate,
    flashFn
  }) {
    const {
      Button
    } = DS();
    const {
      Field
    } = B();
    const ext = op.source === "external";
    const [v, setV] = useState(ext ? {
      supplier: op.supplier || "",
      ext_days: op.ext_days == null ? "" : String(op.ext_days)
    } : {
      machine: op.machine || "",
      operator: op.operator || "",
      setup: String(op.setup),
      unit: String(op.unit)
    });
    const merged = ext && op.mode === "merged";
    const dirty = ext ? v.supplier !== (op.supplier || "") || v.ext_days !== (op.ext_days == null ? "" : String(op.ext_days)) : v.machine !== (op.machine || "") || v.operator !== (op.operator || "") || v.setup !== String(op.setup) || v.unit !== String(op.unit);
    const allowed = !ext && v.machine ? MACHINE_OPERATORS[v.machine] || [] : null;
    const mismatch = allowed && v.operator && !allowed.includes(v.operator);
    const save = () => {
      if (mismatch) {
        return;
      } // 不匹配时已在控件下方就近显示红字提示，无需再弹提示
      onUpdate(batch.batch_id, {
        ops: batch.ops.map(o => o.seq !== op.seq ? o : ext ? {
          ...o,
          supplier: v.supplier,
          ext_days: v.ext_days === "" ? null : Number(v.ext_days)
        } : {
          ...o,
          machine: v.machine,
          operator: v.operator,
          setup: Number(v.setup) || 0,
          unit: Number(v.unit) || 0
        })
      });
      flashFn("ok", "已保存工序 " + op.seq + " 的补充信息。");
    };
    if (ext) {
      return /*#__PURE__*/React.createElement("div", {
        className: "bd-op-config"
      }, /*#__PURE__*/React.createElement("div", {
        className: "bd-op-config-row"
      }, /*#__PURE__*/React.createElement(Field, {
        label: "\u4F9B\u5E94\u5546"
      }, /*#__PURE__*/React.createElement("select", {
        className: "bd-select" + (dirty ? " bd-cell-dirty" : ""),
        value: v.supplier,
        onChange: e => setV({
          ...v,
          supplier: e.target.value
        })
      }, /*#__PURE__*/React.createElement("option", {
        value: ""
      }, "\uFF08\u672A\u9009\u62E9\uFF09"), SUPPLIERS.map(s => /*#__PURE__*/React.createElement("option", {
        key: s.value,
        value: s.value
      }, s.label)))), /*#__PURE__*/React.createElement(Field, {
        label: "\u5916\u534F\u5468\u671F\uFF08\u5929\uFF09"
      }, /*#__PURE__*/React.createElement("input", {
        className: "bd-cell-input num" + (dirty ? " bd-cell-dirty" : ""),
        placeholder: merged ? "按本工序" : "如：3",
        value: v.ext_days,
        onChange: e => setV({
          ...v,
          ext_days: e.target.value
        })
      })), /*#__PURE__*/React.createElement("div", {
        className: "bd-op-config-act"
      }, /*#__PURE__*/React.createElement(Button, {
        variant: dirty ? "primary" : "secondary",
        size: "sm",
        disabled: !dirty,
        onClick: save
      }, "\u4FDD\u5B58"))), merged ? /*#__PURE__*/React.createElement("span", {
        className: "bd-cell-note"
      }, "\u5C5E\u5408\u5E76\u5916\u534F\u7EC4 ", op.group, "\uFF1B\u53EF\u5355\u72EC\u586B\u672C\u5DE5\u5E8F\u5468\u671F\uFF0C\u7559\u7A7A\u5219\u8DDF\u968F\u6574\u7EC4\u5408\u8BA1\u7EA6 ", op.total ?? "未设置", " \u5929\u3002") : null);
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-op-config"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-op-config-row"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u8BBE\u5907"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select" + (dirty ? " bd-cell-dirty" : ""),
      value: v.machine,
      onChange: e => setV({
        ...v,
        machine: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\uFF08\u672A\u9009\u62E9\uFF09"), MACHINES.map(m => /*#__PURE__*/React.createElement("option", {
      key: m.value,
      value: m.value
    }, m.label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u4EBA\u5458"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select" + (dirty ? " bd-cell-dirty" : "") + (mismatch ? " " : ""),
      style: {
        borderColor: mismatch ? "var(--ui-danger)" : undefined
      },
      value: v.operator,
      onChange: e => setV({
        ...v,
        operator: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\uFF08\u672A\u9009\u62E9\uFF09"), OPERATORS.map(p => /*#__PURE__*/React.createElement("option", {
      key: p.value,
      value: p.value
    }, p.label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u6362\u578B\uFF08\u5C0F\u65F6\uFF09"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-cell-input num" + (dirty ? " bd-cell-dirty" : ""),
      value: v.setup,
      onChange: e => setV({
        ...v,
        setup: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5355\u4EF6\uFF08\u5C0F\u65F6\uFF09"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-cell-input num" + (dirty ? " bd-cell-dirty" : ""),
      value: v.unit,
      onChange: e => setV({
        ...v,
        unit: e.target.value
      })
    })), /*#__PURE__*/React.createElement("div", {
      className: "bd-op-config-act"
    }, /*#__PURE__*/React.createElement(Button, {
      variant: dirty ? "primary" : "secondary",
      size: "sm",
      disabled: !dirty,
      onClick: save
    }, "\u4FDD\u5B58"))), mismatch ? /*#__PURE__*/React.createElement("span", {
      className: "bd-cell-error"
    }, "\u6240\u9009\u4EBA\u5458\u4E0D\u80FD\u64CD\u4F5C ", v.machine, "\uFF1B\u53EF\u9009\uFF1A", (allowed || []).map(id => labelOf(OPERATORS, id)).join("、") || "无", "\u3002") : allowed && allowed.length ? /*#__PURE__*/React.createElement("span", {
      className: "bd-cell-note"
    }, v.machine, " \u53EF\u7528\u4EBA\u5458\uFF1A", allowed.map(id => labelOf(OPERATORS, id)).join("、"), "\u3002") : null);
  }
  window.BatchesScreen = BatchesScreen;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/BaseBatches.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/BaseCalendar.jsx
try { (() => {
// APS Workbench · 基础资料 › 工作日历 tab — 新增/更新某一天（自定义日期选择器）+ 已配置日历（只读）
(function () {
  const {
    useState,
    useRef,
    useEffect
  } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;
  const TODAY = "2026-06-16";
  const SEED_ROWS = [{
    date: "2026-06-19",
    day_type: "workday",
    start: "08:00",
    end: "20:00",
    hours: 11,
    eff: 1.0,
    normal: "yes",
    urgent: "yes",
    remark: "周末前加班"
  }, {
    date: "2026-06-22",
    day_type: "holiday",
    start: "",
    end: "",
    hours: 0,
    eff: 0,
    normal: "no",
    urgent: "no",
    remark: "厂休"
  }, {
    date: "2026-06-25",
    day_type: "workday",
    start: "08:00",
    end: "17:00",
    hours: 8,
    eff: 0.9,
    normal: "yes",
    urgent: "yes",
    remark: ""
  }, {
    date: "2026-06-28",
    day_type: "workday",
    start: "08:00",
    end: "12:00",
    hours: 4,
    eff: 1.0,
    normal: "no",
    urgent: "yes",
    remark: "调休·仅急件"
  }];
  const dayTypeZh = t => t === "holiday" ? "假期" : "工作日";
  const yesNo = v => v === "yes" ? "是" : "否";
  function CalendarTab({
    flashFn,
    onNav
  }) {
    const {
      Panel,
      Button,
      Table
    } = DS();
    const {
      Field,
      Empty
    } = B();
    const [rows, setRows] = useState(SEED_ROWS);
    const blank = {
      date: "",
      day_type: "workday",
      start: "08:00",
      end: "",
      hours: "",
      eff: "",
      normal: "yes",
      urgent: "yes",
      remark: ""
    };
    const [form, setForm] = useState(blank);
    const [errors, setErrors] = useState({});
    const setField = patch => {
      setForm(f => ({
        ...f,
        ...patch
      }));
      setErrors(e => {
        const n = {
          ...e
        };
        Object.keys(patch).forEach(k => delete n[k]);
        return n;
      });
    };
    const configured = new Set(rows.map(r => r.date));
    const submit = () => {
      const errs = {};
      if (!form.date) errs.date = "请先选择日期。";
      if (form.eff !== "" && Number(form.eff) <= 0) errs.eff = "效率必须大于 0。";
      if (Object.keys(errs).length) {
        setErrors(errs);
        return;
      }
      setErrors({});
      const exists = configured.has(form.date);
      const row = {
        ...form,
        hours: form.hours === "" ? 0 : Number(form.hours),
        eff: form.eff === "" ? form.day_type === "holiday" ? 0 : 1 : Number(form.eff)
      };
      setRows(arr => exists ? arr.map(r => r.date === form.date ? row : r) : [...arr, row].sort((a, b) => a.date.localeCompare(b.date)));
      flashFn("ok", (exists ? "已更新 " : "已新增 ") + form.date + " 的工作日历。");
      setForm(blank);
    };
    const cols = [{
      key: "date",
      title: "日期",
      width: 130,
      render: r => /*#__PURE__*/React.createElement("span", {
        style: {
          fontVariantNumeric: "tabular-nums"
        }
      }, r.date)
    }, {
      key: "day_type",
      title: "类型",
      width: 90,
      render: r => dayTypeZh(r.day_type)
    }, {
      key: "start",
      title: "班次开始",
      width: 100,
      render: r => r.start || "08:00"
    }, {
      key: "end",
      title: "班次结束",
      width: 100,
      render: r => r.end || /*#__PURE__*/React.createElement("span", {
        className: "muted"
      }, "-")
    }, {
      key: "hours",
      title: "可用工时",
      width: 100,
      align: "right"
    }, {
      key: "eff",
      title: "效率",
      width: 90,
      align: "right",
      render: r => /*#__PURE__*/React.createElement("span", {
        style: {
          fontVariantNumeric: "tabular-nums"
        }
      }, Number(r.eff).toFixed(1))
    }, {
      key: "normal",
      title: "允许普通件",
      width: 120,
      render: r => yesNo(r.normal)
    }, {
      key: "urgent",
      title: "允许急件",
      width: 110,
      render: r => yesNo(r.urgent)
    }, {
      key: "remark",
      title: "说明",
      render: r => r.remark || /*#__PURE__*/React.createElement("span", {
        className: "muted"
      }, "-")
    }];
    const headerRight = /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "sm",
      onClick: () => onNav && onNav("run")
    }, "\u53BB\u6267\u884C\u6392\u4EA7"), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "sm"
    }, "\u6279\u91CF\u7EF4\u62A4\u5DE5\u4F5C\u65E5\u5386"));
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(Panel, {
      title: "\u5DE5\u4F5C\u65E5\u5386\u914D\u7F6E",
      description: "\u8BBE\u7F6E\u6392\u4EA7\u7528\u7684\u5DE5\u4F5C\u65F6\u95F4\u3001\u6548\u7387\u548C\u53EF\u6392\u4EA7\u4F18\u5148\u7EA7\uFF1B\u672A\u914D\u7F6E\u7684\u65E5\u671F\u6309\u9ED8\u8BA4\u89C4\u5219\u5904\u7406\uFF0C\u4E5F\u53EF\u5728\u8FD9\u91CC\u914D\u7F6E\u8C03\u4F11\u6216\u52A0\u73ED\u3002",
      headerRight: headerRight
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-flash tone-info",
      style: {
        marginBottom: 4
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "bd-flash-dot"
    }), /*#__PURE__*/React.createElement("span", null, "\u9ED8\u8BA4\u89C4\u5219\uFF1A\u672A\u914D\u7F6E\u7684\u65E5\u671F\u6309 ", /*#__PURE__*/React.createElement("strong", null, "\u5468\u4E00\u81F3\u5468\u4E94 8 \u5C0F\u65F6\u3001\u5468\u672B\u4E0D\u6392\u4EA7"), " \u5904\u7406\uFF1B\u6CD5\u5B9A\u5047\u671F\u3001\u8C03\u4F11\u548C\u5468\u672B\u52A0\u73ED\u9700\u8981\u5728\u8FD9\u91CC\u624B\u5DE5\u7EF4\u62A4\u3002"))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u65B0\u589E / \u66F4\u65B0\u67D0\u4E00\u5929",
      description: "\u540C\u4E00\u65E5\u671F\u91CD\u590D\u63D0\u4EA4\u5373\u4E3A\u66F4\u65B0\uFF1B\u4FDD\u5B58\u540E\u7ACB\u5373\u751F\u6548\u4E8E\u6392\u4EA7\u3002"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-cal-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u65E5\u671F",
      required: true,
      wide: true,
      error: errors.date
    }, /*#__PURE__*/React.createElement(DatePicker, {
      value: form.date,
      configured: configured,
      onPick: d => setField({
        date: d
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u7C7B\u578B",
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: form.day_type,
      onChange: e => setForm({
        ...form,
        day_type: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "workday"
    }, "\u5DE5\u4F5C\u65E5"), /*#__PURE__*/React.createElement("option", {
      value: "holiday"
    }, "\u5047\u671F"))), /*#__PURE__*/React.createElement(Field, {
      label: "\u73ED\u6B21\u5F00\u59CB"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input w-time",
      type: "time",
      value: form.start,
      onChange: e => setForm({
        ...form,
        start: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u73ED\u6B21\u7ED3\u675F",
      hint: "\u53EF\u9009"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input w-time",
      type: "time",
      value: form.end,
      onChange: e => setForm({
        ...form,
        end: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u53EF\u7528\u5DE5\u65F6\uFF08\u5C0F\u65F6\uFF09"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input num",
      placeholder: "\u5982\uFF1A8",
      value: form.hours,
      onChange: e => setForm({
        ...form,
        hours: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u6548\u7387\uFF08\u5927\u4E8E 0\uFF09",
      error: errors.eff
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input num",
      placeholder: "\u5982\uFF1A1.0",
      value: form.eff,
      onChange: e => setField({
        eff: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5141\u8BB8\u666E\u901A\u4EF6",
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: form.normal,
      onChange: e => setForm({
        ...form,
        normal: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "yes"
    }, "\u662F"), /*#__PURE__*/React.createElement("option", {
      value: "no"
    }, "\u5426"))), /*#__PURE__*/React.createElement(Field, {
      label: "\u5141\u8BB8\u6025\u4EF6 / \u7279\u6025",
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: form.urgent,
      onChange: e => setForm({
        ...form,
        urgent: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "yes"
    }, "\u662F"), /*#__PURE__*/React.createElement("option", {
      value: "no"
    }, "\u5426"))), /*#__PURE__*/React.createElement(Field, {
      label: "\u8BF4\u660E",
      wide: true
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u53EF\u9009",
      value: form.remark,
      onChange: e => setForm({
        ...form,
        remark: e.target.value
      })
    }))), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")
    }, Object.keys(errors).length ? /*#__PURE__*/React.createElement("span", {
      className: "bd-form-error"
    }, "\u8BF7\u4FEE\u6B63\u6807\u7EA2\u7684\u5FC5\u586B\u9879") : null, /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: submit
    }, "\u4FDD\u5B58"))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u5DF2\u914D\u7F6E\u65E5\u5386",
      description: "\u53EA\u8BFB\u5217\u8868\uFF1B\u8981\u6539\u67D0\u5929\uFF0C\u5728\u4E0A\u65B9\u8868\u5355\u586B\u540C\u4E00\u65E5\u671F\u91CD\u65B0\u63D0\u4EA4\u5373\u53EF\u3002"
    }, rows.length ? /*#__PURE__*/React.createElement("div", {
      className: "bd-table-scroll"
    }, /*#__PURE__*/React.createElement(Table, {
      columns: cols,
      rows: rows,
      rowKey: "date"
    })) : /*#__PURE__*/React.createElement(Empty, {
      title: "\u6682\u65E0\u5DF2\u914D\u7F6E\u7684\u65E5\u5386\u8BB0\u5F55",
      desc: "\u6392\u4EA7\u65F6\u4F1A\u81EA\u52A8\u6309\u9ED8\u8BA4\u89C4\u5219\u5904\u7406\uFF1A\u5468\u4E00\u5230\u5468\u4E94 8 \u5C0F\u65F6\u3001\u5468\u516D\u5468\u65E5\u4E0D\u6392\u4EA7\uFF1B\u6CD5\u5B9A\u5047\u671F\u3001\u8C03\u4F11\u548C\u5468\u672B\u52A0\u73ED\u8981\u81EA\u5DF1\u7EF4\u62A4\u3002"
    })));
  }

  /* ---------- custom date picker ---------- */
  const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];
  const pad = n => String(n).padStart(2, "0");
  const ymd = (y, m, d) => y + "-" + pad(m + 1) + "-" + pad(d);
  function DatePicker({
    value,
    configured,
    onPick
  }) {
    const {
      Button
    } = DS();
    const [open, setOpen] = useState(false);
    const init = value ? value.split("-") : TODAY.split("-");
    const [cur, setCur] = useState({
      y: Number(init[0]),
      m: Number(init[1]) - 1
    });
    const ref = useRef(null);
    useEffect(() => {
      if (!open) return;
      const onDoc = e => {
        if (ref.current && !ref.current.contains(e.target)) setOpen(false);
      };
      document.addEventListener("mousedown", onDoc);
      return () => document.removeEventListener("mousedown", onDoc);
    }, [open]);
    const firstDay = new Date(cur.y, cur.m, 1);
    const startOffset = (firstDay.getDay() + 6) % 7; // Monday-based
    const daysInMonth = new Date(cur.y, cur.m + 1, 0).getDate();
    const cells = [];
    for (let i = 0; i < startOffset; i++) cells.push(null);
    for (let d = 1; d <= daysInMonth; d++) cells.push(d);
    const hint = value ? (() => {
      const dt = new Date(value + "T00:00:00");
      const wd = WEEKDAYS[(dt.getDay() + 6) % 7];
      const isCfg = configured.has(value);
      return "已选：" + value + "（周" + wd + "）" + (isCfg ? " · 已配置，重提交将更新" : " · 未配置");
    })() : "";
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-date-field",
      ref: ref
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-date-input-row"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input w-sm",
      placeholder: "\u5982\uFF1A2026-06-16",
      value: value,
      onChange: e => onPick(e.target.value)
    }), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "sm",
      onClick: () => setOpen(o => !o)
    }, "\u9009\u62E9")), hint ? /*#__PURE__*/React.createElement("div", {
      className: "bd-hint",
      style: {
        marginTop: 6
      }
    }, hint) : null, open ? /*#__PURE__*/React.createElement("div", {
      className: "bd-cal-panel"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-cal-header"
    }, /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "bd-cal-nav",
      "aria-label": "\u4E0A\u4E2A\u6708",
      onClick: () => setCur(c => c.m === 0 ? {
        y: c.y - 1,
        m: 11
      } : {
        y: c.y,
        m: c.m - 1
      })
    }, "\u2039"), /*#__PURE__*/React.createElement("span", {
      className: "bd-cal-title"
    }, cur.y, " \u5E74 ", cur.m + 1, " \u6708"), /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "bd-cal-nav",
      "aria-label": "\u4E0B\u4E2A\u6708",
      onClick: () => setCur(c => c.m === 11 ? {
        y: c.y + 1,
        m: 0
      } : {
        y: c.y,
        m: c.m + 1
      })
    }, "\u203A")), /*#__PURE__*/React.createElement("div", {
      className: "bd-cal-week"
    }, WEEKDAYS.map(w => /*#__PURE__*/React.createElement("span", {
      className: "bd-cal-wd",
      key: w
    }, w))), /*#__PURE__*/React.createElement("div", {
      className: "bd-cal-grid"
    }, cells.map((d, i) => {
      if (d == null) return /*#__PURE__*/React.createElement("span", {
        className: "bd-cal-cell is-empty",
        key: "e" + i
      });
      const ds = ymd(cur.y, cur.m, d);
      const col = (startOffset + d - 1) % 7;
      const weekend = col >= 5;
      const cls = ["bd-cal-cell"];
      if (weekend) cls.push("is-weekend");
      if (configured.has(ds)) cls.push("is-configured");
      if (ds === TODAY) cls.push("is-today");
      if (ds === value) cls.push("is-selected");
      return /*#__PURE__*/React.createElement("button", {
        type: "button",
        className: cls.join(" "),
        key: ds,
        onClick: () => {
          onPick(ds);
          setOpen(false);
        }
      }, d);
    })), /*#__PURE__*/React.createElement("div", {
      className: "bd-cal-foot"
    }, /*#__PURE__*/React.createElement("span", {
      className: "bd-cal-legend"
    }, /*#__PURE__*/React.createElement("span", {
      className: "lg-dot cfg"
    }), "\u5DF2\u914D\u7F6E"), /*#__PURE__*/React.createElement("span", {
      className: "bd-cal-legend"
    }, /*#__PURE__*/React.createElement("span", {
      className: "lg-dot we"
    }), "\u5468\u672B"))) : null);
  }
  window.CalendarTab = CalendarTab;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/BaseCalendar.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/BaseDataScreen.jsx
try { (() => {
// APS Workbench · 基础资料 page shell — 结构切换（链式 / 平铺）+ 一级/二级 tab
// 两版对比：
//  · 链式（按产能链，整体描述主线）：工艺 · 物料 · 自制 · 外协 · 工作日历
//      自制 → 自制工种 / 设备 / 人员    外协 → 外协工种 / 供应商
//  · 平铺（按设计图/仓库）：工艺 · 物料 · 设备 · 人员 · 工作日历
//      工艺 → 零件工艺模板 / 工种配置 / 供应商配置
// URL 参数(?struct=&tab=&sub=) + 位置记忆(localStorage) + aria-current。本页不挂计划上下文胶囊。
(function () {
  const {
    useState,
    useEffect
  } = React;
  const B = () => window.BD;
  const CHAIN_TABS = [{
    id: "process",
    label: "工艺"
  }, {
    id: "material",
    label: "物料"
  }, {
    id: "internal",
    label: "自制",
    chain: "internal"
  }, {
    id: "external",
    label: "外协",
    chain: "external"
  }, {
    id: "calendar",
    label: "工作日历"
  }];
  const FLAT_TABS = [{
    id: "process",
    label: "工艺"
  }, {
    id: "material",
    label: "物料"
  }, {
    id: "equipment",
    label: "设备"
  }, {
    id: "personnel",
    label: "人员"
  }, {
    id: "calendar",
    label: "工作日历"
  }];
  const DEFAULT_SUB = {
    material: "materials",
    internal: "optype",
    external: "optype",
    process: "parts"
  };
  function readInit() {
    let struct = "chain",
      tab = "process";
    const subs = {
      ...DEFAULT_SUB
    };
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
    const valid = (struct === "chain" ? CHAIN_TABS : FLAT_TABS).map(t => t.id);
    if (valid.indexOf(tab) < 0) tab = "process";
    return {
      struct,
      tab,
      subs
    };
  }
  function BaseDataScreen({
    onNav
  }) {
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
        if (subs[tab]) qs.set("bdsub", subs[tab]);else qs.delete("bdsub");
        window.history.replaceState(null, "", window.location.pathname + "?" + qs.toString());
        localStorage.setItem("aps_bd_struct", struct);
        localStorage.setItem("aps_bd_tab", tab);
        localStorage.setItem("aps_bd_subs", JSON.stringify(subs));
      } catch (e) {}
    }, [struct, tab, subs]);
    const changeStruct = s => {
      clear();
      setStruct(s);
      const valid = (s === "chain" ? CHAIN_TABS : FLAT_TABS).map(t => t.id);
      if (valid.indexOf(tab) < 0) setTab("process");
      window.scrollTo({
        top: 0
      });
    };
    const changeTab = t => {
      clear();
      setTab(t);
      window.scrollTo({
        top: 0
      });
    };
    const setSub = (t, v) => {
      clear();
      setSubs(s => ({
        ...s,
        [t]: v
      }));
    };
    const {
      PrimaryTabs,
      Seg,
      Flash
    } = B();
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("section", {
      className: "bd-intro",
      "data-screen-label": "\u57FA\u7840\u8D44\u6599"
    }, /*#__PURE__*/React.createElement("div", {
      className: "dash-head",
      style: {
        marginBottom: 8
      }
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "eyebrow"
    }, "\u6570\u636E\u51C6\u5907"), /*#__PURE__*/React.createElement("h3", {
      style: {
        margin: 0,
        fontSize: 22,
        fontWeight: 600
      }
    }, "\u57FA\u7840\u8D44\u6599")), /*#__PURE__*/React.createElement("p", {
      className: "dash-note",
      style: {
        maxWidth: 360
      }
    }, "\u6392\u4EA7\u524D\u8981\u5907\u597D\u7684\u57FA\u7840\u8F93\u5165\u8D44\u6599\u96C6\u4E2D\u5728\u8FD9\u91CC\u7EF4\u62A4\u3002", /*#__PURE__*/React.createElement("strong", {
      style: {
        color: "var(--ui-text)"
      }
    }, "\u672C\u9875\u4E0E\u5177\u4F53\u6392\u4EA7\u7248\u672C\u65E0\u5173"), "\uFF0C\u4E0D\u6302\u8BA1\u5212\u4E0A\u4E0B\u6587\u3002")), /*#__PURE__*/React.createElement("p", {
      className: "bd-purpose"
    }, "\u5DE5\u5E8F\u7684", /*#__PURE__*/React.createElement("strong", null, "\u5F52\u5C5E"), "\u5728\u300C\u5DE5\u827A\u300D\u91CC\u4EA7\u751F\uFF1A", /*#__PURE__*/React.createElement("strong", null, "\u81EA\u5236"), "\u5DE5\u5E8F\u8D70\u81EA\u5236\u94FE\uFF08\u5DE5\u65F6\u53E3\u5F84 \u2192 \u5DE5\u79CD / \u8BBE\u5907 / \u4EBA\u5458\uFF09\uFF0C", /*#__PURE__*/React.createElement("strong", null, "\u5916\u534F"), "\u5DE5\u5E8F\u8D70\u5916\u534F\u94FE\uFF08\u5468\u671F\u53E3\u5F84 \u2192 \u5DE5\u79CD / \u4F9B\u5E94\u5546\uFF09\u3002\u4E24\u6761\u94FE\u8D44\u6E90\u4E0E\u8BA1\u91CF\u53E3\u5F84\u4E0D\u540C\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "bd-structure-bar"
    }, /*#__PURE__*/React.createElement("div", {
      className: "sb-label"
    }, /*#__PURE__*/React.createElement("strong", null, "\u4FE1\u606F\u67B6\u6784\uFF08\u4E24\u7248\u5BF9\u6BD4\uFF09"), "\uFF1A", struct === "chain" ? "按产能链分顶层（整体描述主线）—— 工种/供应商/设备/人员按自制 · 外协两条链归集。" : "按设计图平铺 —— 工艺下挂「零件工艺模板 / 工种配置 / 供应商配置」，设备、人员各自独立。"), /*#__PURE__*/React.createElement("div", {
      className: "sb-controls"
    }, /*#__PURE__*/React.createElement(Seg, {
      options: [{
        value: "chain",
        label: "链式（自制/外协）"
      }, {
        value: "flat",
        label: "平铺（设计图版）"
      }],
      value: struct,
      onChange: changeStruct,
      ariaLabel: "\u5207\u6362\u4FE1\u606F\u67B6\u6784"
    }))), /*#__PURE__*/React.createElement(PrimaryTabs, {
      tabs: TABS,
      value: tab,
      onChange: changeTab
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        marginTop: 20
      }
    }, /*#__PURE__*/React.createElement(Flash, {
      flash: flash
    }), tab === "process" && struct === "chain" ? /*#__PURE__*/React.createElement(ProcessTab, {
      flashFn: showFlash
    }) : null, tab === "process" && struct === "flat" ? /*#__PURE__*/React.createElement(FlatProcess, {
      sub: subs.process,
      onSub: v => setSub("process", v),
      flashFn: showFlash
    }) : null, tab === "material" ? /*#__PURE__*/React.createElement(MaterialTab, {
      sub: subs.material,
      onSub: v => setSub("material", v),
      flashFn: showFlash
    }) : null, tab === "internal" ? /*#__PURE__*/React.createElement(ChainTab, {
      kind: "internal",
      sub: subs.internal,
      onSub: v => setSub("internal", v),
      flashFn: showFlash
    }) : null, tab === "external" ? /*#__PURE__*/React.createElement(ChainTab, {
      kind: "external",
      sub: subs.external,
      onSub: v => setSub("external", v),
      flashFn: showFlash
    }) : null, tab === "equipment" ? /*#__PURE__*/React.createElement(EquipmentModule, {
      flashFn: showFlash
    }) : null, tab === "personnel" ? /*#__PURE__*/React.createElement(PersonnelModule, {
      flashFn: showFlash
    }) : null, tab === "calendar" ? /*#__PURE__*/React.createElement(CalendarTab, {
      flashFn: showFlash,
      onNav: onNav
    }) : null));
  }

  /* ---------- 链式：自制 / 外协 二级 tab ---------- */
  function ChainTab({
    kind,
    sub,
    onSub,
    flashFn
  }) {
    const {
      SubTabs
    } = B();
    const internal = kind === "internal";
    const tabs = internal ? [{
      id: "optype",
      label: "自制工种"
    }, {
      id: "equipment",
      label: "设备"
    }, {
      id: "personnel",
      label: "人员"
    }] : [{
      id: "optype",
      label: "外协工种"
    }, {
      id: "supplier",
      label: "供应商"
    }];
    const valid = tabs.map(t => t.id);
    const active = valid.indexOf(sub) >= 0 ? sub : "optype";
    const note = internal ? /*#__PURE__*/React.createElement(React.Fragment, null, "\u81EA\u5236\u94FE\u8BA1\u91CF\u53E3\u5F84 = ", /*#__PURE__*/React.createElement("strong", null, "\u5DE5\u65F6\uFF08\u6362\u578B + \u5355\u4EF6\u5C0F\u65F6\uFF09"), "\u3002\u5DE5\u5E8F(\u81EA\u5236) \u2192 \u81EA\u5236\u5DE5\u79CD \u2192 \u8BBE\u5907\uFF08\u7ED1 1 \u4E2A\u5DE5\u79CD\uFF09+ \u4EBA\u5458\uFF08\u591A\u6280\u80FD\u77E9\u9635\uFF09\u3002") : /*#__PURE__*/React.createElement(React.Fragment, null, "\u5916\u534F\u94FE\u8BA1\u91CF\u53E3\u5F84 = ", /*#__PURE__*/React.createElement("strong", null, "\u5468\u671F\uFF08\u5929\uFF09"), "\u3002\u5DE5\u5E8F(\u5916\u534F) \u2192 \u5916\u534F\u5DE5\u79CD \u2192 \u8FDE\u7EED\u5916\u534F\u5DE5\u5E8F\u7EC4 \u2192 \u4F9B\u5E94\u5546\uFF08\u7ED1\u5916\u534F\u5DE5\u79CD\uFF0C\u7ED9\u9ED8\u8BA4\u5468\u671F\uFF09\u3002");
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "bd-chain-note tone-" + kind
    }, /*#__PURE__*/React.createElement("span", {
      className: "cn-bar"
    }), /*#__PURE__*/React.createElement("span", null, note)), /*#__PURE__*/React.createElement(SubTabs, {
      tabs: tabs,
      value: active,
      onChange: onSub
    }), active === "optype" ? /*#__PURE__*/React.createElement(OpTypesModule, {
      scope: kind,
      flashFn: flashFn
    }) : null, active === "equipment" ? /*#__PURE__*/React.createElement(EquipmentModule, {
      flashFn: flashFn
    }) : null, active === "personnel" ? /*#__PURE__*/React.createElement(PersonnelModule, {
      flashFn: flashFn
    }) : null, active === "supplier" ? /*#__PURE__*/React.createElement(SuppliersModule, {
      flashFn: flashFn
    }) : null);
  }

  /* ---------- 平铺：工艺 = 零件工艺模板 / 工种配置 / 供应商配置 ---------- */
  function FlatProcess({
    sub,
    onSub,
    flashFn
  }) {
    const {
      SubTabs
    } = B();
    const tabs = [{
      id: "parts",
      label: "零件工艺模板"
    }, {
      id: "optype",
      label: "工种配置"
    }, {
      id: "supplier",
      label: "供应商配置"
    }];
    const valid = tabs.map(t => t.id);
    const active = valid.indexOf(sub) >= 0 ? sub : "parts";
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(SubTabs, {
      tabs: tabs,
      value: active,
      onChange: onSub
    }), active === "parts" ? /*#__PURE__*/React.createElement(ProcessTab, {
      flashFn: flashFn
    }) : null, active === "optype" ? /*#__PURE__*/React.createElement(OpTypesModule, {
      scope: "all",
      flashFn: flashFn
    }) : null, active === "supplier" ? /*#__PURE__*/React.createElement(SuppliersModule, {
      flashFn: flashFn
    }) : null);
  }
  window.BaseDataScreen = BaseDataScreen;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/BaseDataScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/BaseEquipment.jsx
try { (() => {
// APS Workbench · 基础资料 › 自制 › 设备模块（可复用）
// 列表 + 内联新增 + 主从编辑页 + 双 Excel（① 批量维护设备 ② 批量维护设备组/资源池）
// 自制链资源：设备绑 1 个自制工种，计量口径走工时。
(function () {
  const {
    useState
  } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;
  const SEED = [{
    code: "M-03",
    name: "五轴加工中心",
    op_type: "数铣",
    group: "精加工组",
    status: "active",
    refs: ["排产任务"]
  }, {
    code: "M-05",
    name: "卧式加工中心",
    op_type: "数铣",
    group: "预加工组",
    status: "active",
    refs: ["排产任务"]
  }, {
    code: "M-07",
    name: "立式加工中心",
    op_type: "数车",
    group: "预加工组",
    status: "active",
    refs: []
  }, {
    code: "M-12",
    name: "三坐标检测",
    op_type: "总检",
    group: "检验组",
    status: "active",
    refs: []
  }, {
    code: "M-18",
    name: "数控车床",
    op_type: "数车",
    group: "车加工组",
    status: "active",
    refs: []
  }, {
    code: "M-21",
    name: "精密磨床",
    op_type: "精磨",
    group: "—",
    status: "disabled",
    refs: []
  }];
  const STATUS_OPTS = [{
    value: "active",
    label: "启用"
  }, {
    value: "disabled",
    label: "停用"
  }];
  const statusZh = s => s === "disabled" ? "停用" : "启用";
  function EquipmentModule({
    flashFn
  }) {
    const [rows, setRows] = useState(SEED);
    const [view, setView] = useState("list");
    const [openId, setOpenId] = useState(null);
    const [wiz, setWiz] = useState(null);
    const open = id => {
      setOpenId(id);
      setView("detail");
      window.scrollTo({
        top: 0
      });
    };
    const back = () => {
      setView("list");
      setOpenId(null);
      window.scrollTo({
        top: 0
      });
    };
    const patch = (id, p) => setRows(arr => arr.map(r => r.code === id ? {
      ...r,
      ...p
    } : r));
    if (wiz) {
      const W = B().ExcelWizard;
      return /*#__PURE__*/React.createElement(W, {
        wiz: wiz,
        onClose: () => setWiz(null),
        onDone: s => flashFn("ok", "Excel 导入完成：" + s + "。")
      });
    }
    if (view === "detail") {
      const row = rows.find(r => r.code === openId);
      return /*#__PURE__*/React.createElement(EquipmentDetail, {
        row: row,
        onBack: back,
        onSave: patch,
        flashFn: flashFn
      });
    }
    return /*#__PURE__*/React.createElement(EquipmentList, {
      rows: rows,
      setRows: setRows,
      onOpen: open,
      onWiz: setWiz,
      flashFn: flashFn
    });
  }

  /* ============================================================ LIST */
  function EquipmentList({
    rows,
    setRows,
    onOpen,
    onWiz,
    flashFn
  }) {
    const {
      Panel,
      Button,
      Badge,
      Table
    } = DS();
    const {
      Field,
      ActionCards,
      ConfirmButton,
      Pager,
      Empty,
      opTypeNames
    } = B();
    const intTypes = opTypeNames("internal");
    const [q, setQ] = useState("");
    const [page, setPage] = useState(1);
    const perPage = 8;
    const [form, setForm] = useState({
      code: "",
      name: "",
      op_type: intTypes[0] || "",
      group: "",
      status: "active"
    });
    const [errors, setErrors] = useState({});
    const setField = patch => {
      setForm(f => ({
        ...f,
        ...patch
      }));
      setErrors(e => {
        const n = {
          ...e
        };
        Object.keys(patch).forEach(k => delete n[k]);
        return n;
      });
    };
    const cards = [{
      title: "批量维护设备",
      desc: "下载模板、上传检查、确认写入或导出设备台账；含编号、名称、所属工种、状态。",
      maintainLabel: "批量维护设备",
      exportLabel: "导出当前设备",
      wizard: {
        kind: "machine",
        title: "批量维护设备",
        desc: "维护设备编号、名称、所属自制工种与状态；所属工种必须是已存在的自制工种。",
        sampleRows: [{
          row_num: 2,
          status: "update",
          message: "更新所属工种 数车→数铣",
          data: {
            设备编号: "M-07",
            所属工种: "数铣"
          }
        }, {
          row_num: 3,
          status: "new",
          message: "新增设备",
          data: {
            设备编号: "M-22",
            名称: "线切割",
            所属工种: "钳工"
          }
        }, {
          row_num: 4,
          status: "error",
          message: "所属工种「委外」不是自制工种",
          data: {
            设备编号: "M-23",
            所属工种: "委外"
          }
        }]
      }
    }, {
      title: "批量维护设备组",
      desc: "维护设备分组 / 资源池（设备 ↔ 设备组的归属），独立三步流，便于按组排产与统计。",
      maintainLabel: "批量维护设备组",
      exportLabel: "导出当前设备组",
      wizard: {
        kind: "machine_group",
        title: "批量维护设备组",
        desc: "维护设备组名称与组内设备成员；同一设备可只属于一个主组。",
        modeOptions: [{
          value: "overwrite",
          label: "更新已有，新增缺少"
        }, {
          value: "replace",
          label: "清空设备组后重导"
        }],
        sampleRows: [{
          row_num: 2,
          status: "update",
          message: "精加工组 增加成员 M-05",
          data: {
            设备组: "精加工组",
            成员: "M-03,M-05"
          }
        }, {
          row_num: 3,
          status: "new",
          message: "新增设备组 特种加工组",
          data: {
            设备组: "特种加工组",
            成员: "M-22"
          }
        }]
      }
    }];
    const list = rows.filter(r => !q || (r.code + r.name + r.op_type + (r.group || "")).toLowerCase().includes(q.toLowerCase()));
    const totalPages = Math.ceil(list.length / perPage);
    const pageRows = list.slice((page - 1) * perPage, page * perPage);
    const tryDelete = r => {
      if (r.refs && r.refs.length) {
        flashFn("danger", "无法删除设备 " + r.code + "：仍被" + r.refs.join("、") + "引用，请先解除引用。");
        return;
      }
      setRows(arr => arr.filter(x => x.code !== r.code));
      flashFn("ok", "已删除设备 " + r.code + "。");
    };
    const cols = [{
      key: "code",
      title: "设备编号",
      width: 120,
      render: r => /*#__PURE__*/React.createElement("a", {
        className: "bd-link",
        onClick: () => onOpen(r.code)
      }, r.code)
    }, {
      key: "name",
      title: "设备名称",
      width: 170
    }, {
      key: "op_type",
      title: "所属工种",
      width: 120,
      render: r => /*#__PURE__*/React.createElement(Badge, {
        tone: "notice"
      }, r.op_type)
    }, {
      key: "group",
      title: "设备组",
      width: 120,
      render: r => r.group && r.group !== "—" ? r.group : /*#__PURE__*/React.createElement("span", {
        className: "muted"
      }, "\u672A\u5206\u7EC4")
    }, {
      key: "status",
      title: "状态",
      width: 100,
      render: r => /*#__PURE__*/React.createElement(Badge, {
        tone: r.status === "active" ? "ok" : "secondary",
        dot: true
      }, statusZh(r.status))
    }, {
      key: "act",
      title: "操作",
      width: 170,
      render: r => /*#__PURE__*/React.createElement("div", {
        className: "bd-cell-actions"
      }, /*#__PURE__*/React.createElement(Button, {
        variant: "secondary",
        size: "sm",
        onClick: () => onOpen(r.code)
      }, "\u67E5\u770B/\u7F16\u8F91"), /*#__PURE__*/React.createElement(ConfirmButton, {
        label: "\u5220\u9664",
        title: "删除设备 " + r.code + "？",
        body: r.refs && r.refs.length ? /*#__PURE__*/React.createElement(React.Fragment, null, "\u8BE5\u8BBE\u5907\u5DF2\u88AB ", /*#__PURE__*/React.createElement("strong", null, r.refs.join("、")), " \u5F15\u7528\uFF0C\u5220\u9664\u4F1A\u88AB\u62D2\u7EDD\u3002\u4ECD\u8981\u5C1D\u8BD5\u5417\uFF1F") : /*#__PURE__*/React.createElement(React.Fragment, null, "\u786E\u8BA4\u5220\u9664\u8BBE\u5907 ", /*#__PURE__*/React.createElement("strong", null, r.name), "\uFF08", r.code, "\uFF09\u5417\uFF1F"),
        onConfirm: () => tryDelete(r)
      }))
    }];
    const submit = () => {
      const errs = {};
      if (!form.code) errs.code = "请填写设备编号。";else if (rows.some(r => r.code === form.code)) errs.code = "设备编号 " + form.code + " 已存在。";
      if (!form.name) errs.name = "请填写设备名称。";
      if (Object.keys(errs).length) {
        setErrors(errs);
        return;
      }
      setErrors({});
      setRows(arr => [{
        ...form,
        group: form.group || "—",
        refs: []
      }, ...arr]);
      flashFn("ok", "已添加设备 " + form.code + "。");
      setForm({
        code: "",
        name: "",
        op_type: intTypes[0] || "",
        group: "",
        status: "active"
      });
    };
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(ActionCards, {
      title: "\u6279\u91CF\u7EF4\u62A4",
      subtitle: "\u8BBE\u5907\u4E0E\u8BBE\u5907\u7EC4\u5404\u8D70\u4E00\u5957\u72EC\u7ACB\u7684 Excel \u4E09\u6B65\u6D41\uFF1B\u624B\u5DE5\u65B0\u589E\u7EE7\u7EED\u4F7F\u7528\u4E0B\u65B9\u8868\u5355\u3002",
      cards: cards,
      onOpen: onWiz
    }), /*#__PURE__*/React.createElement(Panel, {
      title: "\u8BBE\u5907\u5217\u8868",
      description: "\u8BBE\u5907\u7ED1 1 \u4E2A\u81EA\u5236\u5DE5\u79CD\uFF1B\u6309\u5DE5\u79CD\u628A\u8BBE\u5907\u5E76\u5165\u5BF9\u5E94\u4EA7\u80FD\uFF0C\u6392\u4EA7\u65F6\u843D\u5230\u8BBE\u5907\u4E0A\u3002",
      headerRight: null
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u8BBE\u5907\u7F16\u53F7",
      required: true,
      error: errors.code
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1AM-03",
      value: form.code,
      onChange: e => setField({
        code: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u8BBE\u5907\u540D\u79F0",
      required: true,
      error: errors.name
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1A\u4E94\u8F74\u52A0\u5DE5\u4E2D\u5FC3",
      value: form.name,
      onChange: e => setField({
        name: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u6240\u5C5E\u5DE5\u79CD",
      required: true,
      hint: "\u4ECE\u81EA\u5236\u5DE5\u79CD\u91CC\u9009 1 \u4E2A\u3002"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: form.op_type,
      onChange: e => setForm({
        ...form,
        op_type: e.target.value
      })
    }, intTypes.map(n => /*#__PURE__*/React.createElement("option", {
      key: n,
      value: n
    }, n)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u8BBE\u5907\u7EC4",
      hint: "\u53EF\u9009\uFF0C\u7559\u7A7A=\u672A\u5206\u7EC4\u3002"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1A\u7CBE\u52A0\u5DE5\u7EC4",
      value: form.group,
      onChange: e => setForm({
        ...form,
        group: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u72B6\u6001",
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: form.status,
      onChange: e => setForm({
        ...form,
        status: e.target.value
      })
    }, STATUS_OPTS.map(o => /*#__PURE__*/React.createElement("option", {
      key: o.value,
      value: o.value
    }, o.label))))), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")
    }, Object.keys(errors).length ? /*#__PURE__*/React.createElement("span", {
      className: "bd-form-error"
    }, "\u8BF7\u586B\u5199\u6807\u7EA2\u7684\u5FC5\u586B\u9879") : null, /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: submit
    }, "\u65B0\u589E\u8BBE\u5907"))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u8BBE\u5907\u53F0\u8D26"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-search"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u641C\u7D22"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u8F93\u5165\u8BBE\u5907\u7F16\u53F7\u3001\u540D\u79F0\u3001\u5DE5\u79CD\u2026",
      value: q,
      onChange: e => {
        setQ(e.target.value);
        setPage(1);
      }
    }))), list.length ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Pager, {
      page: page,
      totalPages: totalPages,
      total: list.length,
      onPrev: () => setPage(p => p - 1),
      onNext: () => setPage(p => p + 1)
    }), /*#__PURE__*/React.createElement("div", {
      className: "bd-table-scroll"
    }, /*#__PURE__*/React.createElement(Table, {
      columns: cols,
      rows: pageRows,
      rowKey: "code"
    }))) : /*#__PURE__*/React.createElement(Empty, {
      title: "\u6682\u65E0\u8BBE\u5907\u6570\u636E",
      desc: "\u53EF\u5728\u4E0A\u65B9\u624B\u52A8\u65B0\u589E\uFF0C\u6216\u7528 Excel \u6279\u91CF\u7EF4\u62A4\u5BFC\u5165\u3002"
    })));
  }

  /* ============================================================ DETAIL */
  function EquipmentDetail({
    row,
    onBack,
    onSave,
    flashFn
  }) {
    const {
      Panel,
      Button,
      Badge
    } = DS();
    const {
      Field,
      opTypeNames
    } = B();
    const intTypes = opTypeNames("internal");
    const [v, setV] = useState({
      name: row.name,
      op_type: row.op_type,
      group: row.group === "—" ? "" : row.group,
      status: row.status
    });
    const [errors, setErrors] = useState({});
    const setField = patch => {
      setV(s => ({
        ...s,
        ...patch
      }));
      setErrors(e => {
        const n = {
          ...e
        };
        Object.keys(patch).forEach(k => delete n[k]);
        return n;
      });
    };
    const save = () => {
      if (!v.name) {
        setErrors({
          name: "请填写设备名称。"
        });
        return;
      }
      setErrors({});
      onSave(row.code, {
        ...v,
        group: v.group || "—"
      });
      flashFn("ok", "已保存设备 " + row.code + "。");
      onBack();
    };
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(Panel, {
      title: "\u8BBE\u5907 \xB7 \u8BE6\u60C5",
      description: "\u7EF4\u62A4\u8BBE\u5907\u540D\u79F0\u3001\u6240\u5C5E\u5DE5\u79CD\u3001\u8BBE\u5907\u7EC4\u4E0E\u72B6\u6001\u3002\u8BBE\u5907\u7F16\u53F7\u521B\u5EFA\u540E\u4E0D\u53EF\u66F4\u6539\u3002",
      headerRight: /*#__PURE__*/React.createElement(Button, {
        variant: "ghost",
        size: "sm",
        onClick: onBack
      }, "\u2190 \u8FD4\u56DE\u5217\u8868")
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-meta-row"
    }, /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u8BBE\u5907\u7F16\u53F7\uFF1A"), /*#__PURE__*/React.createElement("strong", null, row.code)), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u6240\u5C5E\u5DE5\u79CD\uFF1A"), /*#__PURE__*/React.createElement(Badge, {
      tone: "notice"
    }, v.op_type)), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u72B6\u6001\uFF1A"), /*#__PURE__*/React.createElement(Badge, {
      tone: v.status === "active" ? "ok" : "secondary",
      dot: true
    }, statusZh(v.status))))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u7F16\u8F91\u8BBE\u5907"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u8BBE\u5907\u7F16\u53F7"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      value: row.code,
      disabled: true
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u8BBE\u5907\u540D\u79F0",
      required: true,
      error: errors.name
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      value: v.name,
      onChange: e => setField({
        name: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u6240\u5C5E\u5DE5\u79CD",
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: v.op_type,
      onChange: e => setV({
        ...v,
        op_type: e.target.value
      })
    }, intTypes.map(n => /*#__PURE__*/React.createElement("option", {
      key: n,
      value: n
    }, n)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u8BBE\u5907\u7EC4"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u7559\u7A7A=\u672A\u5206\u7EC4",
      value: v.group,
      onChange: e => setV({
        ...v,
        group: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u72B6\u6001",
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: v.status,
      onChange: e => setV({
        ...v,
        status: e.target.value
      })
    }, STATUS_OPTS.map(o => /*#__PURE__*/React.createElement("option", {
      key: o.value,
      value: o.value
    }, o.label))))), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")
    }, Object.keys(errors).length ? /*#__PURE__*/React.createElement("span", {
      className: "bd-form-error"
    }, "\u8BF7\u586B\u5199\u6807\u7EA2\u7684\u5FC5\u586B\u9879") : null, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "md",
      onClick: onBack
    }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: save
    }, "\u4FDD\u5B58"))));
  }
  window.EquipmentModule = EquipmentModule;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/BaseEquipment.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/BaseMaterial.jsx
try { (() => {
// APS Workbench · 基础资料 › 物料 tab — 二级 tab：物料主数据（整表行内编辑）/ 批次物料需求（齐套判定）
(function () {
  const {
    useState
  } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;
  const SEED_MATERIALS = [{
    material_id: "MAT001",
    name: "45# 圆钢",
    spec: "Φ30",
    unit: "kg",
    stock: 1200,
    status: "active",
    remark: ""
  }, {
    material_id: "MAT002",
    name: "铸铝件",
    spec: "ZL104",
    unit: "件",
    stock: 80,
    status: "active",
    remark: "外购"
  }, {
    material_id: "MAT003",
    name: "密封圈",
    spec: "Φ25×3",
    unit: "件",
    stock: 0,
    status: "active",
    remark: "缺料"
  }, {
    material_id: "MAT004",
    name: "不锈钢板",
    spec: "δ5",
    unit: "kg",
    stock: 540,
    status: "disabled",
    remark: "停用中"
  }];
  const STATUS_OPTS = [{
    value: "active",
    label: "可用"
  }, {
    value: "disabled",
    label: "停用"
  }];
  const SEED_BATCHES = [{
    id: "B202605-018",
    part: "T-1008",
    qty: 12,
    ready: "partial",
    ready_date: "—",
    reqs: [{
      id: 1,
      material_id: "MAT001",
      name: "45# 圆钢",
      spec: "Φ30",
      unit: "kg",
      required: 120,
      received: 120
    }, {
      id: 2,
      material_id: "MAT002",
      name: "铸铝件",
      spec: "ZL104",
      unit: "件",
      required: 12,
      received: 6
    }, {
      id: 3,
      material_id: "MAT003",
      name: "密封圈",
      spec: "Φ25×3",
      unit: "件",
      required: 24,
      received: 0
    }]
  }, {
    id: "B202605-021",
    part: "T-1009",
    qty: 8,
    ready: "yes",
    ready_date: "06-09",
    reqs: [{
      id: 1,
      material_id: "MAT001",
      name: "45# 圆钢",
      spec: "Φ30",
      unit: "kg",
      required: 80,
      received: 80
    }]
  }, {
    id: "B202605-019",
    part: "T-1006",
    qty: 6,
    ready: "no",
    ready_date: "—",
    reqs: []
  }];
  function readyState(required, received) {
    const req = Number(required) || 0,
      rec = Number(received);
    if (req <= 0) return {
      key: "yes",
      label: "齐套",
      tone: "ok"
    };
    if (rec >= req) return {
      key: "yes",
      label: "齐套",
      tone: "ok"
    };
    if (rec > 0) return {
      key: "partial",
      label: "部分齐套",
      tone: "notice"
    };
    return {
      key: "no",
      label: "未齐套",
      tone: "danger"
    };
  }
  function MaterialTab({
    sub,
    onSub,
    flashFn
  }) {
    const {
      SubTabs
    } = B();
    const tabs = [{
      id: "materials",
      label: "物料主数据"
    }, {
      id: "batch",
      label: "批次物料需求"
    }];
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(SubTabs, {
      tabs: tabs,
      value: sub,
      onChange: onSub
    }), sub === "batch" ? /*#__PURE__*/React.createElement(BatchMaterials, {
      flashFn: flashFn
    }) : /*#__PURE__*/React.createElement(MaterialMaster, {
      flashFn: flashFn
    }));
  }

  /* ============================================================ 2A 物料主数据 */
  function MaterialMaster({
    flashFn
  }) {
    const {
      Panel,
      Button,
      Badge,
      Table
    } = DS();
    const {
      Field,
      ConfirmButton,
      Pager,
      Empty
    } = B();
    const [rows, setRows] = useState(SEED_MATERIALS);
    const [edits, setEdits] = useState({});
    const [form, setForm] = useState({
      material_id: "",
      name: "",
      spec: "",
      unit: "",
      stock: "0",
      status: "active",
      remark: ""
    });
    const [errors, setErrors] = useState({});
    const setField = patch => {
      setForm(f => ({
        ...f,
        ...patch
      }));
      setErrors(e => {
        const n = {
          ...e
        };
        Object.keys(patch).forEach(k => delete n[k]);
        return n;
      });
    };
    const [page, setPage] = useState(1);
    const perPage = 8;
    const getVal = (r, k) => edits[r.material_id] && k in edits[r.material_id] ? edits[r.material_id][k] : r[k];
    const isDirty = r => edits[r.material_id] && Object.keys(edits[r.material_id]).some(k => String(edits[r.material_id][k]) !== String(r[k]));
    const setCell = (id, k, v) => setEdits(e => ({
      ...e,
      [id]: {
        ...(e[id] || {}),
        [k]: v
      }
    }));
    const saveRow = r => {
      const patch = edits[r.material_id] || {};
      if (Number(patch.stock ?? r.stock) < 0) {
        return;
      } // 负库存已在单元格就近标红提示
      setRows(arr => arr.map(x => x.material_id === r.material_id ? {
        ...x,
        ...patch
      } : x));
      setEdits(e => {
        const n = {
          ...e
        };
        delete n[r.material_id];
        return n;
      });
      flashFn("ok", "已保存物料 " + r.material_id + "。");
    };
    const cols = [{
      key: "material_id",
      title: "物料编号",
      width: 120,
      render: r => /*#__PURE__*/React.createElement("code", {
        className: "bd-code"
      }, r.material_id)
    }, {
      key: "name",
      title: "名称",
      width: 160,
      render: r => /*#__PURE__*/React.createElement("input", {
        className: "bd-cell-input",
        value: getVal(r, "name"),
        onChange: e => setCell(r.material_id, "name", e.target.value)
      })
    }, {
      key: "spec",
      title: "规格",
      width: 120,
      render: r => /*#__PURE__*/React.createElement("input", {
        className: "bd-cell-input",
        value: getVal(r, "spec"),
        onChange: e => setCell(r.material_id, "spec", e.target.value)
      })
    }, {
      key: "unit",
      title: "单位",
      width: 90,
      render: r => /*#__PURE__*/React.createElement("input", {
        className: "bd-cell-input",
        value: getVal(r, "unit"),
        onChange: e => setCell(r.material_id, "unit", e.target.value)
      })
    }, {
      key: "stock",
      title: "库存",
      width: 110,
      align: "right",
      render: r => {
        const neg = Number(getVal(r, "stock")) < 0;
        return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("input", {
          className: "bd-cell-input num" + (neg ? " is-error" : ""),
          type: "number",
          min: "0",
          step: "0.01",
          value: getVal(r, "stock"),
          onChange: e => setCell(r.material_id, "stock", e.target.value)
        }), neg ? /*#__PURE__*/React.createElement("span", {
          className: "bd-cell-error"
        }, "\u5E93\u5B58\u4E0D\u80FD\u4E3A\u8D1F\u6570") : null);
      }
    }, {
      key: "status",
      title: "状态",
      width: 120,
      render: r => /*#__PURE__*/React.createElement("select", {
        className: "bd-cell-input",
        value: getVal(r, "status"),
        onChange: e => setCell(r.material_id, "status", e.target.value)
      }, STATUS_OPTS.map(o => /*#__PURE__*/React.createElement("option", {
        key: o.value,
        value: o.value
      }, o.label)))
    }, {
      key: "remark",
      title: "备注",
      render: r => /*#__PURE__*/React.createElement("input", {
        className: "bd-cell-input",
        placeholder: "\u53EF\u9009",
        value: getVal(r, "remark"),
        onChange: e => setCell(r.material_id, "remark", e.target.value)
      })
    }, {
      key: "act",
      title: "操作",
      width: 150,
      render: r => /*#__PURE__*/React.createElement("div", {
        className: "bd-cell-actions"
      }, /*#__PURE__*/React.createElement(Button, {
        variant: isDirty(r) ? "primary" : "secondary",
        size: "sm",
        disabled: !isDirty(r),
        onClick: () => saveRow(r)
      }, "\u4FDD\u5B58"), /*#__PURE__*/React.createElement(ConfirmButton, {
        label: "\u5220\u9664",
        title: "删除物料 " + r.material_id + "？",
        body: "\u82E5\u8BE5\u7269\u6599\u5DF2\u88AB\u6279\u6B21\u7269\u6599\u9700\u6C42\u5F15\u7528\uFF0C\u5220\u9664\u5C06\u5931\u8D25\u3002\u786E\u8BA4\u5220\u9664\u5417\uFF1F",
        onConfirm: () => {
          setRows(arr => arr.filter(x => x.material_id !== r.material_id));
          flashFn("ok", "已删除物料 " + r.material_id + "。");
        }
      }))
    }];
    const submit = () => {
      const errs = {};
      if (!form.material_id) errs.material_id = "请填写物料编号。";else if (rows.some(r => r.material_id === form.material_id)) errs.material_id = "物料编号 " + form.material_id + " 已存在。";
      if (!form.name) errs.name = "请填写名称。";
      if (Object.keys(errs).length) {
        setErrors(errs);
        return;
      }
      setErrors({});
      setRows(arr => [{
        ...form,
        stock: Number(form.stock) || 0
      }, ...arr]);
      flashFn("ok", "已创建物料 " + form.material_id + "。");
      setForm({
        material_id: "",
        name: "",
        spec: "",
        unit: "",
        stock: "0",
        status: "active",
        remark: ""
      });
    };
    const totalPages = Math.ceil(rows.length / perPage);
    const pageRows = rows.slice((page - 1) * perPage, page * perPage);
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(Panel, {
      title: "\u7269\u6599\u4E3B\u6570\u636E",
      description: "\u7EF4\u62A4\u7269\u6599\u7F16\u53F7\u3001\u540D\u79F0\u3001\u89C4\u683C\u3001\u5E93\u5B58\u548C\u72B6\u6001\u3002\u5217\u8868\u6574\u8868\u884C\u5185\u7F16\u8F91\uFF0C\u6539\u5B8C\u70B9\u5BF9\u5E94\u884C\u7684\u300C\u4FDD\u5B58\u300D\u3002"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u7269\u6599\u7F16\u53F7",
      required: true,
      error: errors.material_id
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1AMAT001",
      value: form.material_id,
      onChange: e => setField({
        material_id: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u540D\u79F0",
      required: true,
      error: errors.name
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1A\u5706\u94A2",
      value: form.name,
      onChange: e => setField({
        name: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u89C4\u683C"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1A\u03A630",
      value: form.spec,
      onChange: e => setForm({
        ...form,
        spec: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5355\u4F4D"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1Akg / \u4EF6",
      value: form.unit,
      onChange: e => setForm({
        ...form,
        unit: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5E93\u5B58",
      hint: "\u9ED8\u8BA4 0\uFF0C\u4E0D\u80FD\u4E3A\u8D1F\u3002"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input num",
      type: "number",
      min: "0",
      step: "0.01",
      value: form.stock,
      onChange: e => setForm({
        ...form,
        stock: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u72B6\u6001",
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: form.status,
      onChange: e => setForm({
        ...form,
        status: e.target.value
      })
    }, STATUS_OPTS.map(o => /*#__PURE__*/React.createElement("option", {
      key: o.value,
      value: o.value
    }, o.label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u5907\u6CE8",
      wide: true
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u53EF\u9009\u5907\u6CE8",
      value: form.remark,
      onChange: e => setForm({
        ...form,
        remark: e.target.value
      })
    }))), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")
    }, Object.keys(errors).length ? /*#__PURE__*/React.createElement("span", {
      className: "bd-form-error"
    }, "\u8BF7\u586B\u5199\u6807\u7EA2\u7684\u5FC5\u586B\u9879") : null, /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: submit
    }, "\u521B\u5EFA"))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u7269\u6599\u5217\u8868"
    }, /*#__PURE__*/React.createElement(Pager, {
      page: page,
      totalPages: totalPages,
      total: rows.length,
      onPrev: () => setPage(p => p - 1),
      onNext: () => setPage(p => p + 1)
    }), rows.length ? /*#__PURE__*/React.createElement("div", {
      className: "bd-table-scroll"
    }, /*#__PURE__*/React.createElement(Table, {
      columns: cols,
      rows: pageRows,
      rowKey: "material_id"
    })) : /*#__PURE__*/React.createElement(Empty, {
      title: "\u6682\u65E0\u7269\u6599\u6570\u636E",
      desc: "\u53EF\u5728\u4E0A\u65B9\u624B\u52A8\u65B0\u589E\u3002"
    })));
  }

  /* ============================================================ 2B 批次物料需求 */
  function BatchMaterials({
    flashFn
  }) {
    const {
      Panel,
      Button,
      Badge,
      Table
    } = DS();
    const {
      Field,
      SummaryGrid,
      InfoStrip,
      ConfirmButton,
      Empty
    } = B();
    const [batches, setBatches] = useState(SEED_BATCHES);
    const [picked, setPicked] = useState("");
    const [opened, setOpened] = useState(null);
    const [add, setAdd] = useState({
      material_id: "",
      required: "",
      received: ""
    });
    const [addErr, setAddErr] = useState({});
    const setAddField = patch => {
      setAdd(a => ({
        ...a,
        ...patch
      }));
      setAddErr(e => {
        const n = {
          ...e
        };
        Object.keys(patch).forEach(k => delete n[k]);
        return n;
      });
    };
    const overview = batches.reduce((a, b) => {
      a[b.ready] = (a[b.ready] || 0) + 1;
      return a;
    }, {});
    const batch = batches.find(b => b.id === opened);
    const setReq = (bid, rid, patch) => setBatches(arr => arr.map(b => b.id === bid ? {
      ...b,
      reqs: b.reqs.map(r => r.id === rid ? {
        ...r,
        ...patch
      } : r)
    } : b));
    const reqCols = [{
      key: "id",
      title: "编号",
      width: 64,
      align: "right",
      render: r => /*#__PURE__*/React.createElement("span", {
        style: {
          fontVariantNumeric: "tabular-nums"
        }
      }, r.id)
    }, {
      key: "material_id",
      title: "物料编号",
      width: 120,
      render: r => /*#__PURE__*/React.createElement("code", {
        className: "bd-code"
      }, r.material_id)
    }, {
      key: "name",
      title: "名称",
      width: 130
    }, {
      key: "spec",
      title: "规格",
      width: 100,
      render: r => r.spec || "-"
    }, {
      key: "unit",
      title: "单位",
      width: 80,
      render: r => r.unit || "-"
    }, {
      key: "required",
      title: "需求数量",
      width: 120,
      align: "right",
      render: r => /*#__PURE__*/React.createElement("input", {
        className: "bd-cell-input num",
        type: "number",
        min: "0.000001",
        step: "0.01",
        value: r.required,
        onChange: e => setReq(batch.id, r.id, {
          required: e.target.value
        })
      })
    }, {
      key: "received",
      title: "到料数量",
      width: 120,
      align: "right",
      render: r => /*#__PURE__*/React.createElement("input", {
        className: "bd-cell-input num",
        type: "number",
        min: "0",
        step: "0.01",
        value: r.received,
        onChange: e => setReq(batch.id, r.id, {
          received: e.target.value
        })
      })
    }, {
      key: "ready",
      title: "齐套状态",
      width: 110,
      render: r => {
        const s = readyState(r.required, r.received);
        return /*#__PURE__*/React.createElement(Badge, {
          tone: s.tone,
          dot: true
        }, s.label);
      }
    }, {
      key: "act",
      title: "操作",
      width: 150,
      render: r => /*#__PURE__*/React.createElement("div", {
        className: "bd-cell-actions"
      }, /*#__PURE__*/React.createElement(Button, {
        variant: "secondary",
        size: "sm",
        onClick: () => flashFn("ok", "已保存需求 #" + r.id + "，齐套状态已重算。")
      }, "\u4FDD\u5B58"), /*#__PURE__*/React.createElement(ConfirmButton, {
        label: "\u5220\u9664",
        title: "\u5220\u9664\u8BE5\u7269\u6599\u9700\u6C42\uFF1F",
        body: "\u5220\u9664\u540E\u6279\u6B21\u9F50\u5957\u72B6\u6001\u4F1A\u81EA\u52A8\u6309\u5269\u4F59\u9700\u6C42\u91CD\u7B97\u3002\u786E\u8BA4\u5220\u9664\u5417\uFF1F",
        onConfirm: () => {
          setBatches(arr => arr.map(b => b.id === batch.id ? {
            ...b,
            reqs: b.reqs.filter(x => x.id !== r.id)
          } : b));
          flashFn("ok", "已删除该物料需求。");
        }
      }))
    }];
    const doAdd = () => {
      const errs = {};
      if (!add.material_id) errs.material_id = "请选择物料。";
      if (!add.required || Number(add.required) <= 0) errs.required = "需求数量必须大于 0。";
      if (Object.keys(errs).length) {
        setAddErr(errs);
        return;
      }
      setAddErr({});
      const mat = SEED_MATERIALS.find(m => m.material_id === add.material_id) || {};
      const nid = (batch.reqs.reduce((m, r) => Math.max(m, r.id), 0) || 0) + 1;
      const received = add.received === "" ? Number(add.required) : Number(add.received);
      setBatches(arr => arr.map(b => b.id === batch.id ? {
        ...b,
        reqs: [...b.reqs, {
          id: nid,
          material_id: add.material_id,
          name: mat.name || "",
          spec: mat.spec || "",
          unit: mat.unit || "",
          required: Number(add.required),
          received
        }]
      } : b));
      flashFn("ok", "已新增物料需求。");
      setAdd({
        material_id: "",
        required: "",
        received: ""
      });
    };
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(Panel, {
      title: "\u9009\u62E9\u6279\u6B21",
      description: "\u9009\u4E00\u4E2A\u6279\u6B21\u67E5\u770B\u5E76\u7BA1\u7406\u5176\u7269\u6599\u9700\u6C42\uFF1B\u5B58\u5728\u7269\u6599\u9700\u6C42\u8BB0\u5F55\u65F6\uFF0C\u7CFB\u7EDF\u6309\u5230\u6599\u60C5\u51B5\u81EA\u52A8\u66F4\u65B0\u9F50\u5957\u72B6\u6001\u3002"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-search"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u6279\u6B21"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      style: {
        minWidth: 280
      },
      value: picked,
      onChange: e => setPicked(e.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\uFF08\u8BF7\u9009\u62E9\u6279\u6B21\uFF09"), batches.map(b => /*#__PURE__*/React.createElement("option", {
      key: b.id,
      value: b.id
    }, b.id, "\uFF08", b.part, "\xD7", b.qty, "\uFF09")))), /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      disabled: !picked,
      onClick: () => setOpened(picked)
    }, "\u67E5\u770B"))), !batch ? /*#__PURE__*/React.createElement(Panel, {
      title: "\u9F50\u5957\u6982\u89C8"
    }, /*#__PURE__*/React.createElement(SummaryGrid, {
      items: [{
        label: "齐套",
        value: overview.yes || 0,
        sev: "ok"
      }, {
        label: "部分齐套",
        value: overview.partial || 0,
        sev: "notice"
      }, {
        label: "未齐套",
        value: overview.no || 0,
        sev: "danger"
      }]
    }), /*#__PURE__*/React.createElement("p", {
      className: "bd-sec-sub",
      style: {
        marginTop: 14
      }
    }, "\u8BF7\u5728\u4E0A\u65B9\u9009\u62E9\u4E00\u4E2A\u6279\u6B21\uFF0C\u67E5\u770B\u5E76\u7BA1\u7406\u5176\u7269\u6599\u9700\u6C42\u3002\u67D0\u6279\u6B21\u5B58\u5728\u7269\u6599\u9700\u6C42\u8BB0\u5F55\u65F6\uFF0C\u7CFB\u7EDF\u4F1A\u6309\u5230\u6599\u60C5\u51B5\u81EA\u52A8\u66F4\u65B0\u9F50\u5957\u663E\u793A\u3002")) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Panel, {
      title: "\u6279\u6B21\u4FE1\u606F",
      headerRight: /*#__PURE__*/React.createElement(Button, {
        variant: "secondary",
        size: "sm"
      }, "\u6253\u5F00\u6279\u6B21\u8BE6\u60C5")
    }, /*#__PURE__*/React.createElement(InfoStrip, {
      cells: [{
        k: "批次号",
        v: batch.id
      }, {
        k: "图号",
        v: batch.part
      }, {
        k: "数量",
        v: batch.qty
      }, {
        k: "当前齐套状态",
        v: /*#__PURE__*/React.createElement(Badge, {
          tone: readyStateOfBatch(batch).tone,
          dot: true
        }, readyStateOfBatch(batch).label)
      }, {
        k: "齐套日期",
        v: batch.ready_date || "暂无"
      }]
    })), /*#__PURE__*/React.createElement(Panel, {
      title: "\u65B0\u589E\u7269\u6599\u9700\u6C42"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u7269\u6599",
      required: true,
      error: addErr.material_id
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: add.material_id,
      onChange: e => setAddField({
        material_id: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\uFF08\u8BF7\u9009\u62E9\uFF09"), SEED_MATERIALS.map(m => /*#__PURE__*/React.createElement("option", {
      key: m.material_id,
      value: m.material_id
    }, m.material_id, " \xB7 ", m.name)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u9700\u6C42\u6570\u91CF",
      required: true,
      hint: "\u5FC5\u987B\u5927\u4E8E 0\u3002",
      error: addErr.required
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input num",
      type: "number",
      min: "0.000001",
      step: "0.01",
      placeholder: "\u5982\uFF1A10",
      value: add.required,
      onChange: e => setAddField({
        required: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5230\u6599\u6570\u91CF",
      hint: "\u7559\u7A7A = \u5DF2\u5230\u9F50\uFF1B\u586B\u4E0D\u8DB3\u6570\u91CF\u624D\u663E\u793A\u672A\u9F50\u5957\u3002"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input num",
      type: "number",
      min: "0",
      step: "0.01",
      placeholder: "\u7559\u7A7A=\u5DF2\u5230\u9F50",
      value: add.received,
      onChange: e => setAdd({
        ...add,
        received: e.target.value
      })
    }))), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer" + (Object.keys(addErr).length ? " has-error" : "")
    }, Object.keys(addErr).length ? /*#__PURE__*/React.createElement("span", {
      className: "bd-form-error"
    }, "\u8BF7\u4FEE\u6B63\u6807\u7EA2\u7684\u5FC5\u586B\u9879") : null, /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: doAdd
    }, "\u65B0\u589E"))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u7269\u6599\u9700\u6C42\u5217\u8868",
      description: "\u6539\u52A8\u9700\u6C42\u6570\u91CF\u6216\u5230\u6599\u6570\u91CF\u540E\uFF0C\u9F50\u5957\u72B6\u6001\u4F1A\u81EA\u52A8\u91CD\u7B97\u3002"
    }, batch.reqs.length ? /*#__PURE__*/React.createElement("div", {
      className: "bd-table-scroll"
    }, /*#__PURE__*/React.createElement(Table, {
      columns: reqCols,
      rows: batch.reqs,
      rowKey: "id"
    })) : /*#__PURE__*/React.createElement(Empty, {
      title: "\u8BE5\u6279\u6B21\u8FD8\u6CA1\u6709\u7269\u6599\u9700\u6C42",
      desc: "\u6CA1\u6709\u7269\u6599\u660E\u7EC6\u65F6\u9ED8\u8BA4\u6309\u9F50\u5957\u663E\u793A\u3002\u65B0\u589E\u540E\u7CFB\u7EDF\u4F1A\u6309\u5230\u6599\u6570\u91CF\u66F4\u65B0\u9F50\u5957\u663E\u793A\u3002"
    }))));
  }
  function readyStateOfBatch(batch) {
    if (!batch.reqs.length) return {
      label: "齐套",
      tone: "ok"
    };
    const states = batch.reqs.map(r => readyState(r.required, r.received).key);
    if (states.every(s => s === "yes")) return {
      label: "齐套",
      tone: "ok"
    };
    if (states.some(s => s === "yes" || s === "partial")) return {
      label: "部分齐套",
      tone: "notice"
    };
    return {
      label: "未齐套",
      tone: "danger"
    };
  }
  window.MaterialTab = MaterialTab;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/BaseMaterial.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/BaseOpTypes.jsx
try { (() => {
// APS Workbench · 基础资料 › 工种配置模块（可复用）
// scope: "internal" 自制工种 | "external" 外协工种 | "all" 全部工种(带归属列+筛选)
// 列表 + 内联新增 + 主从详情编辑 + Excel 批量维护 + 引用保护删除
(function () {
  const {
    useState
  } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;

  // 每个 scope 独立维护一份种子（含引用锁定演示）
  const SEED = [{
    op_type_id: "OT001",
    name: "数铣",
    category: "internal",
    remark: "",
    refs: ["工序", "设备"]
  }, {
    op_type_id: "OT002",
    name: "数车",
    category: "internal",
    remark: "",
    refs: ["工序", "设备"]
  }, {
    op_type_id: "OT003",
    name: "钳工",
    category: "internal",
    remark: "",
    refs: ["工序", "人员"]
  }, {
    op_type_id: "OT004",
    name: "精磨",
    category: "internal",
    remark: "",
    refs: []
  }, {
    op_type_id: "OT005",
    name: "钻孔",
    category: "internal",
    remark: "",
    refs: []
  }, {
    op_type_id: "OT006",
    name: "总检",
    category: "internal",
    remark: "关键工序",
    refs: ["工序", "人员"]
  }, {
    op_type_id: "OT007",
    name: "标印",
    category: "internal",
    remark: "",
    refs: []
  }, {
    op_type_id: "OT008",
    name: "表处理",
    category: "internal",
    remark: "",
    refs: ["工序"]
  }, {
    op_type_id: "OT051",
    name: "电镀",
    category: "external",
    remark: "",
    refs: ["工序", "供应商"]
  }, {
    op_type_id: "OT052",
    name: "发黑",
    category: "external",
    remark: "",
    refs: ["供应商"]
  }, {
    op_type_id: "OT053",
    name: "热处理",
    category: "external",
    remark: "",
    refs: ["工序", "供应商"]
  }, {
    op_type_id: "OT054",
    name: "喷涂",
    category: "external",
    remark: "",
    refs: []
  }];
  const catZh = c => c === "external" ? "外协" : "自制";
  const catTone = c => c === "external" ? "warning" : "notice";
  function OpTypesModule({
    scope = "internal",
    flashFn
  }) {
    const init = scope === "all" ? SEED : SEED.filter(o => o.category === scope);
    const [rows, setRows] = useState(init);
    const [view, setView] = useState("list");
    const [openId, setOpenId] = useState(null);
    const [wiz, setWiz] = useState(null);
    const open = id => {
      setOpenId(id);
      setView("detail");
      window.scrollTo({
        top: 0
      });
    };
    const back = () => {
      setView("list");
      setOpenId(null);
      window.scrollTo({
        top: 0
      });
    };
    const patch = (id, p) => setRows(arr => arr.map(r => r.op_type_id === id ? {
      ...r,
      ...p
    } : r));
    if (wiz) {
      const W = B().ExcelWizard;
      return /*#__PURE__*/React.createElement(W, {
        wiz: wiz,
        onClose: () => setWiz(null),
        onDone: s => flashFn("ok", "Excel 导入完成：" + s + "。")
      });
    }
    if (view === "detail") {
      const row = rows.find(r => r.op_type_id === openId);
      return /*#__PURE__*/React.createElement(OpTypeDetail, {
        row: row,
        scope: scope,
        onBack: back,
        onSave: patch,
        flashFn: flashFn
      });
    }
    return /*#__PURE__*/React.createElement(OpTypesList, {
      rows: rows,
      setRows: setRows,
      scope: scope,
      onOpen: open,
      onWiz: setWiz,
      flashFn: flashFn
    });
  }

  /* ============================================================ LIST */
  function OpTypesList({
    rows,
    setRows,
    scope,
    onOpen,
    onWiz,
    flashFn
  }) {
    const {
      Panel,
      Button,
      Badge,
      Table
    } = DS();
    const {
      Field,
      ActionCards,
      ConfirmButton,
      Pager,
      Empty
    } = B();
    const [q, setQ] = useState("");
    const [filter, setFilter] = useState("all");
    const [page, setPage] = useState(1);
    const perPage = 8;
    const defCat = scope === "external" ? "external" : "internal";
    const [form, setForm] = useState({
      op_type_id: "",
      name: "",
      category: defCat,
      remark: ""
    });
    const [errors, setErrors] = useState({});
    const setField = patch => {
      setForm(f => ({
        ...f,
        ...patch
      }));
      setErrors(e => {
        const n = {
          ...e
        };
        Object.keys(patch).forEach(k => delete n[k]);
        return n;
      });
    };
    const cards = [{
      title: "批量维护工种",
      desc: "下载模板、上传检查、确认写入或导出" + (scope === "all" ? "全部" : catZh(scope)) + "工种配置；手工新增继续用下方表单。",
      maintainLabel: "批量维护工种",
      exportLabel: "导出当前工种",
      cycle: scope === "external",
      wizard: {
        kind: "op_types",
        title: "批量维护工种配置",
        desc: "维护工种编号、名称、归属（自制/外协）与备注；写入前会逐行检查。",
        sampleRows: [{
          row_num: 2,
          status: "update",
          message: "已存在，更新名称",
          data: {
            工种编号: "OT003",
            名称: "钳工",
            归属: "自制"
          }
        }, {
          row_num: 3,
          status: "new",
          message: "新增工种",
          data: {
            工种编号: "OT009",
            名称: "去毛刺",
            归属: "自制"
          }
        }, {
          row_num: 4,
          status: "error",
          message: "归属只能是 自制 / 外协",
          data: {
            工种编号: "OT010",
            归属: "委外"
          }
        }]
      }
    }];
    const list = rows.filter(r => scope !== "all" || filter === "all" || r.category === filter).filter(r => !q || (r.op_type_id + r.name + (r.remark || "")).toLowerCase().includes(q.toLowerCase()));
    const totalPages = Math.ceil(list.length / perPage);
    const pageRows = list.slice((page - 1) * perPage, page * perPage);
    const tryDelete = r => {
      if (r.refs && r.refs.length) {
        flashFn("danger", "无法删除工种 " + r.name + "：仍被" + r.refs.join("、") + "引用，请先解除引用。");
        return;
      }
      setRows(arr => arr.filter(x => x.op_type_id !== r.op_type_id));
      flashFn("ok", "已删除工种 " + r.name + "。");
    };
    const cols = [{
      key: "op_type_id",
      title: "工种编号",
      width: 130,
      render: r => /*#__PURE__*/React.createElement("a", {
        className: "bd-link",
        onClick: () => onOpen(r.op_type_id)
      }, r.op_type_id)
    }, {
      key: "name",
      title: "工种名称",
      width: 160
    }, scope === "all" ? {
      key: "category",
      title: "归属",
      width: 100,
      render: r => /*#__PURE__*/React.createElement(Badge, {
        tone: catTone(r.category),
        dot: true
      }, catZh(r.category))
    } : null, {
      key: "remark",
      title: "备注",
      render: r => r.remark || /*#__PURE__*/React.createElement("span", {
        className: "muted"
      }, "-")
    }, {
      key: "act",
      title: "操作",
      width: 170,
      render: r => /*#__PURE__*/React.createElement("div", {
        className: "bd-cell-actions"
      }, /*#__PURE__*/React.createElement(Button, {
        variant: "secondary",
        size: "sm",
        onClick: () => onOpen(r.op_type_id)
      }, "\u67E5\u770B/\u7F16\u8F91"), /*#__PURE__*/React.createElement(ConfirmButton, {
        label: "\u5220\u9664",
        title: "删除工种 " + r.name + "？",
        body: r.refs && r.refs.length ? /*#__PURE__*/React.createElement(React.Fragment, null, "\u8BE5\u5DE5\u79CD\u5DF2\u88AB ", /*#__PURE__*/React.createElement("strong", null, r.refs.join("、")), " \u5F15\u7528\uFF0C\u5220\u9664\u4F1A\u88AB\u62D2\u7EDD\u4EE5\u4FDD\u62A4\u6392\u4EA7\u6570\u636E\u3002\u4ECD\u8981\u5C1D\u8BD5\u5417\uFF1F") : /*#__PURE__*/React.createElement(React.Fragment, null, "\u786E\u8BA4\u5220\u9664\u5DE5\u79CD ", /*#__PURE__*/React.createElement("strong", null, r.name), "\uFF08", r.op_type_id, "\uFF09\u5417\uFF1F"),
        onConfirm: () => tryDelete(r)
      }))
    }].filter(Boolean);
    const submit = () => {
      const errs = {};
      if (!form.op_type_id) errs.op_type_id = "请填写工种编号。";else if (rows.some(r => r.op_type_id === form.op_type_id)) errs.op_type_id = "工种编号 " + form.op_type_id + " 已存在。";
      if (!form.name) errs.name = "请填写工种名称。";
      if (Object.keys(errs).length) {
        setErrors(errs);
        return;
      }
      setErrors({});
      setRows(arr => [{
        ...form,
        refs: []
      }, ...arr]);
      flashFn("ok", "已添加" + catZh(form.category) + "工种 " + form.name + "。");
      setForm({
        op_type_id: "",
        name: "",
        category: defCat,
        remark: ""
      });
    };
    const title = scope === "internal" ? "自制工种" : scope === "external" ? "外协工种" : "工种配置";
    const desc = scope === "all" ? "工种是一张表，按归属（自制 / 外协）区分；自制工种供自制链使用，外协工种供外协链使用。" : "本 tab 只显示「" + catZh(scope) + "」工种；新建时归属预设为" + catZh(scope) + "，供路线文字生成工序与下游资源绑定时使用。";
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(ActionCards, {
      title: "\u6279\u91CF\u7EF4\u62A4",
      subtitle: "\u9002\u5408 Excel \u4E0B\u53D1\u6216\u6574\u6279\u590D\u6838\uFF1B\u624B\u5DE5\u65B0\u589E\u7EE7\u7EED\u4F7F\u7528\u4E0B\u65B9\u8868\u5355\u3002",
      cards: cards,
      onOpen: onWiz
    }), /*#__PURE__*/React.createElement(Panel, {
      title: "新增" + (scope === "all" ? "工种" : catZh(scope) + "工种")
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u5DE5\u79CD\u7F16\u53F7",
      required: true,
      error: errors.op_type_id
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1AOT001",
      value: form.op_type_id,
      onChange: e => setField({
        op_type_id: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5DE5\u79CD\u540D\u79F0",
      required: true,
      error: errors.name
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1A\u6570\u8F66 / \u6570\u94E3 / \u94B3 / \u7535\u9540",
      value: form.name,
      onChange: e => setField({
        name: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5F52\u5C5E",
      required: true,
      hint: scope === "all" ? "决定它进入自制链还是外协链。" : "本 tab 固定为" + catZh(scope) + "。"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: form.category,
      disabled: scope !== "all",
      onChange: e => setForm({
        ...form,
        category: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "internal"
    }, "\u81EA\u5236"), /*#__PURE__*/React.createElement("option", {
      value: "external"
    }, "\u5916\u534F"))), /*#__PURE__*/React.createElement(Field, {
      label: "\u5907\u6CE8"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u53EF\u9009",
      value: form.remark,
      onChange: e => setForm({
        ...form,
        remark: e.target.value
      })
    }))), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")
    }, Object.keys(errors).length ? /*#__PURE__*/React.createElement("span", {
      className: "bd-form-error"
    }, "\u8BF7\u586B\u5199\u6807\u7EA2\u7684\u5FC5\u586B\u9879") : null, /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: submit
    }, "\u6DFB\u52A0\u5DE5\u79CD"))), /*#__PURE__*/React.createElement(Panel, {
      title: title + "列表",
      description: desc
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-search"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u641C\u7D22"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u8F93\u5165\u5DE5\u79CD\u7F16\u53F7\u3001\u540D\u79F0\u2026",
      value: q,
      onChange: e => {
        setQ(e.target.value);
        setPage(1);
      }
    })), scope === "all" ? /*#__PURE__*/React.createElement(Field, {
      label: "\u5F52\u5C5E\u7B5B\u9009"
    }, /*#__PURE__*/React.createElement(B_Seg, {
      options: [{
        value: "all",
        label: "全部"
      }, {
        value: "internal",
        label: "自制"
      }, {
        value: "external",
        label: "外协"
      }],
      value: filter,
      onChange: v => {
        setFilter(v);
        setPage(1);
      },
      ariaLabel: "\u6309\u5F52\u5C5E\u7B5B\u9009\u5DE5\u79CD"
    })) : null), list.length ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Pager, {
      page: page,
      totalPages: totalPages,
      total: list.length,
      onPrev: () => setPage(p => p - 1),
      onNext: () => setPage(p => p + 1)
    }), /*#__PURE__*/React.createElement("div", {
      className: "bd-table-scroll"
    }, /*#__PURE__*/React.createElement(Table, {
      columns: cols,
      rows: pageRows,
      rowKey: "op_type_id"
    }))) : /*#__PURE__*/React.createElement(Empty, {
      title: "\u6682\u65E0\u5DE5\u79CD\u6570\u636E",
      desc: "\u53EF\u5728\u4E0A\u65B9\u624B\u52A8\u65B0\u589E\uFF0C\u6216\u7528 Excel \u6279\u91CF\u7EF4\u62A4\u5BFC\u5165\u3002"
    })));
  }

  /* ============================================================ DETAIL */
  function OpTypeDetail({
    row,
    scope,
    onBack,
    onSave,
    flashFn
  }) {
    const {
      Panel,
      Button,
      Badge
    } = DS();
    const {
      Field
    } = B();
    const [v, setV] = useState({
      name: row.name,
      category: row.category,
      remark: row.remark || ""
    });
    const [errors, setErrors] = useState({});
    const setField = patch => {
      setV(s => ({
        ...s,
        ...patch
      }));
      setErrors(e => {
        const n = {
          ...e
        };
        Object.keys(patch).forEach(k => delete n[k]);
        return n;
      });
    };
    const save = () => {
      if (!v.name) {
        setErrors({
          name: "请填写工种名称。"
        });
        return;
      }
      setErrors({});
      onSave(row.op_type_id, v);
      flashFn("ok", "已保存工种 " + v.name + "。");
      onBack();
    };
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(Panel, {
      title: "\u5DE5\u79CD\u914D\u7F6E \xB7 \u8BE6\u60C5",
      description: "\u7EF4\u62A4\u5DE5\u79CD\u540D\u79F0\u3001\u5F52\u5C5E\u4E0E\u5907\u6CE8\u3002\u5DE5\u79CD\u7F16\u53F7\u521B\u5EFA\u540E\u4E0D\u53EF\u66F4\u6539\u3002",
      headerRight: /*#__PURE__*/React.createElement(Button, {
        variant: "ghost",
        size: "sm",
        onClick: onBack
      }, "\u2190 \u8FD4\u56DE\u5217\u8868")
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-meta-row"
    }, /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u5DE5\u79CD\u7F16\u53F7\uFF1A"), /*#__PURE__*/React.createElement("strong", null, row.op_type_id)), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u5F52\u5C5E\uFF1A"), /*#__PURE__*/React.createElement(Badge, {
      tone: catTone(v.category),
      dot: true
    }, catZh(v.category))), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u5F15\u7528\uFF1A"), row.refs && row.refs.length ? /*#__PURE__*/React.createElement(Badge, {
      tone: "secondary"
    }, row.refs.join(" / ")) : /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "\u65E0")))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u7F16\u8F91\u5DE5\u79CD"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u5DE5\u79CD\u7F16\u53F7"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      value: row.op_type_id,
      disabled: true
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5DE5\u79CD\u540D\u79F0",
      required: true,
      error: errors.name
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      value: v.name,
      onChange: e => setField({
        name: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5F52\u5C5E",
      required: true,
      hint: scope === "all" ? "改归属会切换它所属的产能链。" : "本 tab 固定为" + catZh(scope) + "。"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: v.category,
      disabled: scope !== "all",
      onChange: e => setField({
        category: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "internal"
    }, "\u81EA\u5236"), /*#__PURE__*/React.createElement("option", {
      value: "external"
    }, "\u5916\u534F"))), /*#__PURE__*/React.createElement(Field, {
      label: "\u5907\u6CE8",
      wide: true
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u53EF\u9009",
      value: v.remark,
      onChange: e => setV({
        ...v,
        remark: e.target.value
      })
    }))), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")
    }, Object.keys(errors).length ? /*#__PURE__*/React.createElement("span", {
      className: "bd-form-error"
    }, "\u8BF7\u586B\u5199\u6807\u7EA2\u7684\u5FC5\u586B\u9879") : null, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "md",
      onClick: onBack
    }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: save
    }, "\u4FDD\u5B58"))));
  }
  function B_Seg(props) {
    const S = window.BD.Seg;
    return /*#__PURE__*/React.createElement(S, props);
  }
  window.OpTypesModule = OpTypesModule;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/BaseOpTypes.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/BasePersonnel.jsx
try { (() => {
// APS Workbench · 基础资料 › 自制 › 人员模块（可复用）
// 列表 + 内联新增（多技能复选）+ 主从编辑页 + 双 Excel（① 批量维护人员 ② 技能矩阵）
// 自制链资源：人员掌握多个自制工种（技能矩阵，多对多）。
(function () {
  const {
    useState
  } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;
  const SEED = [{
    code: "P-021",
    name: "张三",
    skills: ["数铣", "数车"],
    status: "active",
    refs: ["排班"]
  }, {
    code: "P-024",
    name: "李四",
    skills: ["钳工", "总检"],
    status: "active",
    refs: []
  }, {
    code: "P-030",
    name: "王五",
    skills: ["数车", "精磨", "钻孔"],
    status: "active",
    refs: ["排班"]
  }, {
    code: "P-033",
    name: "赵六",
    skills: ["总检"],
    status: "leave",
    refs: []
  }, {
    code: "P-040",
    name: "钱七",
    skills: ["数铣", "钳工", "标印"],
    status: "active",
    refs: []
  }];
  const STATUS_OPTS = [{
    value: "active",
    label: "在岗"
  }, {
    value: "leave",
    label: "请假"
  }, {
    value: "disabled",
    label: "停用"
  }];
  const statusZh = s => s === "leave" ? "请假" : s === "disabled" ? "停用" : "在岗";
  const statusTone = s => s === "leave" ? "danger" : s === "disabled" ? "secondary" : "ok";
  function PersonnelModule({
    flashFn
  }) {
    const [rows, setRows] = useState(SEED);
    const [view, setView] = useState("list");
    const [openId, setOpenId] = useState(null);
    const [wiz, setWiz] = useState(null);
    const open = id => {
      setOpenId(id);
      setView("detail");
      window.scrollTo({
        top: 0
      });
    };
    const back = () => {
      setView("list");
      setOpenId(null);
      window.scrollTo({
        top: 0
      });
    };
    const patch = (id, p) => setRows(arr => arr.map(r => r.code === id ? {
      ...r,
      ...p
    } : r));
    if (wiz) {
      const W = B().ExcelWizard;
      return /*#__PURE__*/React.createElement(W, {
        wiz: wiz,
        onClose: () => setWiz(null),
        onDone: s => flashFn("ok", "Excel 导入完成：" + s + "。")
      });
    }
    if (view === "detail") {
      const row = rows.find(r => r.code === openId);
      return /*#__PURE__*/React.createElement(PersonnelDetail, {
        row: row,
        onBack: back,
        onSave: patch,
        flashFn: flashFn
      });
    }
    return /*#__PURE__*/React.createElement(PersonnelList, {
      rows: rows,
      setRows: setRows,
      onOpen: open,
      onWiz: setWiz,
      flashFn: flashFn
    });
  }

  /* ============================================================ LIST */
  function PersonnelList({
    rows,
    setRows,
    onOpen,
    onWiz,
    flashFn
  }) {
    const {
      Panel,
      Button,
      Badge,
      Table
    } = DS();
    const {
      Field,
      ActionCards,
      ConfirmButton,
      Pager,
      Empty,
      Chips,
      CheckGroup,
      opTypeNames
    } = B();
    const intTypes = opTypeNames("internal");
    const [q, setQ] = useState("");
    const [page, setPage] = useState(1);
    const perPage = 8;
    const [form, setForm] = useState({
      code: "",
      name: "",
      skills: [],
      status: "active"
    });
    const [errors, setErrors] = useState({});
    const setField = patch => {
      setForm(f => ({
        ...f,
        ...patch
      }));
      setErrors(e => {
        const n = {
          ...e
        };
        Object.keys(patch).forEach(k => delete n[k]);
        return n;
      });
    };
    const [showMatrix, setShowMatrix] = useState(false);
    const cards = [{
      title: "批量维护人员",
      desc: "下载模板、上传检查、确认写入或导出人员台账；含工号、姓名、状态。",
      maintainLabel: "批量维护人员",
      exportLabel: "导出当前人员",
      wizard: {
        kind: "operator",
        title: "批量维护人员",
        desc: "维护工号、姓名与在岗状态；技能工种在「技能矩阵」里单独维护。",
        sampleRows: [{
          row_num: 2,
          status: "update",
          message: "更新状态 在岗→请假",
          data: {
            工号: "P-033",
            状态: "请假"
          }
        }, {
          row_num: 3,
          status: "new",
          message: "新增人员",
          data: {
            工号: "P-041",
            姓名: "孙八"
          }
        }]
      }
    }, {
      title: "批量维护技能矩阵",
      desc: "维护人员 ↔ 自制工种的多对多技能矩阵，独立三步流；决定谁能上哪道工序。",
      maintainLabel: "批量维护技能矩阵",
      exportLabel: "导出技能矩阵",
      wizard: {
        kind: "skill_matrix",
        title: "批量维护技能矩阵",
        desc: "每行 = 一个人对一个工种是否掌握；工号、工种必须已存在。",
        modeOptions: [{
          value: "overwrite",
          label: "更新已有，新增缺少"
        }, {
          value: "replace",
          label: "清空矩阵后重导"
        }],
        sampleRows: [{
          row_num: 2,
          status: "new",
          message: "张三 + 钳工",
          data: {
            工号: "P-021",
            工种: "钳工",
            掌握: "是"
          }
        }, {
          row_num: 3,
          status: "update",
          message: "李四 − 总检",
          data: {
            工号: "P-024",
            工种: "总检",
            掌握: "否"
          }
        }, {
          row_num: 4,
          status: "error",
          message: "工种「车铣复合」不是自制工种",
          data: {
            工号: "P-030",
            工种: "车铣复合"
          }
        }]
      }
    }];
    const list = rows.filter(r => !q || (r.code + r.name + r.skills.join("")).toLowerCase().includes(q.toLowerCase()));
    const totalPages = Math.ceil(list.length / perPage);
    const pageRows = list.slice((page - 1) * perPage, page * perPage);
    const tryDelete = r => {
      if (r.refs && r.refs.length) {
        flashFn("danger", "无法删除人员 " + r.name + "：仍被" + r.refs.join("、") + "引用，请先解除引用。");
        return;
      }
      setRows(arr => arr.filter(x => x.code !== r.code));
      flashFn("ok", "已删除人员 " + r.name + "。");
    };
    const cols = [{
      key: "code",
      title: "工号",
      width: 110,
      render: r => /*#__PURE__*/React.createElement("a", {
        className: "bd-link",
        onClick: () => onOpen(r.code)
      }, r.code)
    }, {
      key: "name",
      title: "姓名",
      width: 120
    }, {
      key: "skills",
      title: "技能工种（可多个）",
      render: r => /*#__PURE__*/React.createElement(Chips, {
        items: r.skills,
        tone: "internal"
      })
    }, {
      key: "status",
      title: "状态",
      width: 100,
      render: r => /*#__PURE__*/React.createElement(Badge, {
        tone: statusTone(r.status),
        dot: true
      }, statusZh(r.status))
    }, {
      key: "act",
      title: "操作",
      width: 170,
      render: r => /*#__PURE__*/React.createElement("div", {
        className: "bd-cell-actions"
      }, /*#__PURE__*/React.createElement(Button, {
        variant: "secondary",
        size: "sm",
        onClick: () => onOpen(r.code)
      }, "\u67E5\u770B/\u7F16\u8F91"), /*#__PURE__*/React.createElement(ConfirmButton, {
        label: "\u5220\u9664",
        title: "删除人员 " + r.name + "？",
        body: r.refs && r.refs.length ? /*#__PURE__*/React.createElement(React.Fragment, null, "\u8BE5\u4EBA\u5458\u5DF2\u88AB ", /*#__PURE__*/React.createElement("strong", null, r.refs.join("、")), " \u5F15\u7528\uFF0C\u5220\u9664\u4F1A\u88AB\u62D2\u7EDD\u3002\u4ECD\u8981\u5C1D\u8BD5\u5417\uFF1F") : /*#__PURE__*/React.createElement(React.Fragment, null, "\u786E\u8BA4\u5220\u9664\u4EBA\u5458 ", /*#__PURE__*/React.createElement("strong", null, r.name), "\uFF08", r.code, "\uFF09\u5417\uFF1F"),
        onConfirm: () => tryDelete(r)
      }))
    }];
    const submit = () => {
      const errs = {};
      if (!form.code) errs.code = "请填写工号。";else if (rows.some(r => r.code === form.code)) errs.code = "工号 " + form.code + " 已存在。";
      if (!form.name) errs.name = "请填写姓名。";
      if (Object.keys(errs).length) {
        setErrors(errs);
        return;
      }
      setErrors({});
      setRows(arr => [{
        ...form,
        refs: []
      }, ...arr]);
      flashFn("ok", "已添加人员 " + form.name + (form.skills.length ? "（技能：" + form.skills.join("、") + "）" : "") + "。");
      setForm({
        code: "",
        name: "",
        skills: [],
        status: "active"
      });
    };
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(ActionCards, {
      title: "\u6279\u91CF\u7EF4\u62A4",
      subtitle: "\u4EBA\u5458\u53F0\u8D26\u4E0E\u6280\u80FD\u77E9\u9635\u5404\u8D70\u4E00\u5957\u72EC\u7ACB\u7684 Excel \u4E09\u6B65\u6D41\uFF1B\u624B\u5DE5\u65B0\u589E\u7EE7\u7EED\u4F7F\u7528\u4E0B\u65B9\u8868\u5355\u3002",
      cards: cards,
      onOpen: onWiz
    }), /*#__PURE__*/React.createElement(Panel, {
      title: "\u4EBA\u5458\u5217\u8868",
      description: "\u4EBA\u5458\u53EF\u638C\u63E1\u591A\u4E2A\u81EA\u5236\u5DE5\u79CD\uFF08\u6280\u80FD\u77E9\u9635\uFF09\uFF0C\u51B3\u5B9A\u4ED6\u80FD\u4E0A\u54EA\u9053\u81EA\u5236\u5DE5\u5E8F\u3002"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u5DE5\u53F7",
      required: true,
      error: errors.code
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1AP-021",
      value: form.code,
      onChange: e => setField({
        code: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u59D3\u540D",
      required: true,
      error: errors.name
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1A\u5F20\u4E09",
      value: form.name,
      onChange: e => setField({
        name: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u72B6\u6001",
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: form.status,
      onChange: e => setForm({
        ...form,
        status: e.target.value
      })
    }, STATUS_OPTS.map(o => /*#__PURE__*/React.createElement("option", {
      key: o.value,
      value: o.value
    }, o.label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u6280\u80FD\u5DE5\u79CD\uFF08\u53EF\u591A\u9009\uFF09",
      wide: true,
      hint: "\u4ECE\u81EA\u5236\u5DE5\u79CD\u91CC\u52FE\u9009\uFF1B\u4E5F\u53EF\u7A0D\u540E\u5728\u300C\u6280\u80FD\u77E9\u9635\u300D\u91CC\u6279\u91CF\u7EF4\u62A4\u3002"
    }, /*#__PURE__*/React.createElement(CheckGroup, {
      options: intTypes,
      value: form.skills,
      onChange: v => setForm({
        ...form,
        skills: v
      })
    }))), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")
    }, Object.keys(errors).length ? /*#__PURE__*/React.createElement("span", {
      className: "bd-form-error"
    }, "\u8BF7\u586B\u5199\u6807\u7EA2\u7684\u5FC5\u586B\u9879") : null, /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: submit
    }, "\u65B0\u589E\u4EBA\u5458"))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u4EBA\u5458\u53F0\u8D26",
      headerRight: /*#__PURE__*/React.createElement(Button, {
        variant: "secondary",
        size: "sm",
        onClick: () => setShowMatrix(s => !s)
      }, showMatrix ? "收起技能矩阵" : "查看技能矩阵")
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-search"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u641C\u7D22"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u8F93\u5165\u5DE5\u53F7\u3001\u59D3\u540D\u3001\u6280\u80FD\u2026",
      value: q,
      onChange: e => {
        setQ(e.target.value);
        setPage(1);
      }
    }))), showMatrix ? /*#__PURE__*/React.createElement(SkillMatrix, {
      rows: rows,
      types: intTypes
    }) : null, list.length ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Pager, {
      page: page,
      totalPages: totalPages,
      total: list.length,
      onPrev: () => setPage(p => p - 1),
      onNext: () => setPage(p => p + 1)
    }), /*#__PURE__*/React.createElement("div", {
      className: "bd-table-scroll"
    }, /*#__PURE__*/React.createElement(Table, {
      columns: cols,
      rows: pageRows,
      rowKey: "code"
    }))) : /*#__PURE__*/React.createElement(Empty, {
      title: "\u6682\u65E0\u4EBA\u5458\u6570\u636E",
      desc: "\u53EF\u5728\u4E0A\u65B9\u624B\u52A8\u65B0\u589E\uFF0C\u6216\u7528 Excel \u6279\u91CF\u7EF4\u62A4\u5BFC\u5165\u3002"
    })));
  }

  /* ---------- 技能矩阵（只读，人员 × 工种） ---------- */
  function SkillMatrix({
    rows,
    types
  }) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        marginBottom: 16
      }
    }, /*#__PURE__*/React.createElement("p", {
      className: "bd-sec-sub"
    }, "\u4EBA\u5458 \xD7 \u81EA\u5236\u5DE5\u79CD\u638C\u63E1\u60C5\u51B5\uFF08\u53EA\u8BFB\u89C6\u56FE\uFF0C\u7EF4\u62A4\u8D70\u300C\u6279\u91CF\u7EF4\u62A4\u6280\u80FD\u77E9\u9635\u300D\uFF09\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "bd-matrix-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "bd-matrix"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u4EBA\u5458"), types.map(t => /*#__PURE__*/React.createElement("th", {
      key: t
    }, t)))), /*#__PURE__*/React.createElement("tbody", null, rows.map(r => /*#__PURE__*/React.createElement("tr", {
      key: r.code
    }, /*#__PURE__*/React.createElement("th", null, r.name, " ", /*#__PURE__*/React.createElement("span", {
      className: "muted",
      style: {
        fontWeight: 400
      }
    }, r.code)), types.map(t => /*#__PURE__*/React.createElement("td", {
      key: t,
      className: r.skills.includes(t) ? "mx-on" : "mx-off"
    }, r.skills.includes(t) ? "●" : "·"))))))));
  }

  /* ============================================================ DETAIL */
  function PersonnelDetail({
    row,
    onBack,
    onSave,
    flashFn
  }) {
    const {
      Panel,
      Button,
      Badge
    } = DS();
    const {
      Field,
      CheckGroup,
      opTypeNames
    } = B();
    const intTypes = opTypeNames("internal");
    const [v, setV] = useState({
      name: row.name,
      skills: row.skills.slice(),
      status: row.status
    });
    const [errors, setErrors] = useState({});
    const setField = patch => {
      setV(s => ({
        ...s,
        ...patch
      }));
      setErrors(e => {
        const n = {
          ...e
        };
        Object.keys(patch).forEach(k => delete n[k]);
        return n;
      });
    };
    const save = () => {
      if (!v.name) {
        setErrors({
          name: "请填写姓名。"
        });
        return;
      }
      setErrors({});
      onSave(row.code, v);
      flashFn("ok", "已保存人员 " + v.name + "。");
      onBack();
    };
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(Panel, {
      title: "\u4EBA\u5458 \xB7 \u8BE6\u60C5",
      description: "\u7EF4\u62A4\u59D3\u540D\u3001\u6280\u80FD\u5DE5\u79CD\u4E0E\u5728\u5C97\u72B6\u6001\u3002\u5DE5\u53F7\u521B\u5EFA\u540E\u4E0D\u53EF\u66F4\u6539\u3002",
      headerRight: /*#__PURE__*/React.createElement(Button, {
        variant: "ghost",
        size: "sm",
        onClick: onBack
      }, "\u2190 \u8FD4\u56DE\u5217\u8868")
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-meta-row"
    }, /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u5DE5\u53F7\uFF1A"), /*#__PURE__*/React.createElement("strong", null, row.code)), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u72B6\u6001\uFF1A"), /*#__PURE__*/React.createElement(Badge, {
      tone: statusTone(v.status),
      dot: true
    }, statusZh(v.status))), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u6280\u80FD\u6570\uFF1A"), /*#__PURE__*/React.createElement("strong", {
      style: {
        fontVariantNumeric: "tabular-nums"
      }
    }, v.skills.length)))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u7F16\u8F91\u4EBA\u5458"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u5DE5\u53F7"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      value: row.code,
      disabled: true
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u59D3\u540D",
      required: true,
      error: errors.name
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      value: v.name,
      onChange: e => setField({
        name: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u72B6\u6001",
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: v.status,
      onChange: e => setV({
        ...v,
        status: e.target.value
      })
    }, STATUS_OPTS.map(o => /*#__PURE__*/React.createElement("option", {
      key: o.value,
      value: o.value
    }, o.label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u6280\u80FD\u5DE5\u79CD\uFF08\u53EF\u591A\u9009\uFF09",
      wide: true,
      hint: "\u4ECE\u81EA\u5236\u5DE5\u79CD\u91CC\u52FE\u9009\u3002"
    }, /*#__PURE__*/React.createElement(CheckGroup, {
      options: intTypes,
      value: v.skills,
      onChange: s => setV({
        ...v,
        skills: s
      })
    }))), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")
    }, Object.keys(errors).length ? /*#__PURE__*/React.createElement("span", {
      className: "bd-form-error"
    }, "\u8BF7\u586B\u5199\u6807\u7EA2\u7684\u5FC5\u586B\u9879") : null, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "md",
      onClick: onBack
    }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: save
    }, "\u4FDD\u5B58"))));
  }
  window.PersonnelModule = PersonnelModule;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/BasePersonnel.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/BaseProcess.jsx
try { (() => {
// APS Workbench · 基础资料 › 工艺 tab — 零件工艺模板（主从工作区）
// List → master-detail (5 zones): 基础信息 / 重新生成 / 工序概况 / 工序清单(自制行内编辑) / 连续外协工序组
(function () {
  const {
    useState
  } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;

  // 零件工艺模板的数据来自 BaseShared 的共享零件库（window.BD.usePartsStore），
  // 与批次管理的图号下拉是同一份数据源。

  const sourceZh = s => s === "external" ? "外协" : "自制";
  function ProcessTab({
    flashFn
  }) {
    const [parts, setParts] = window.BD.usePartsStore();
    const [view, setView] = useState("list");
    const [openPart, setOpenPart] = useState(null);
    const [wiz, setWiz] = useState(null);
    const openDetail = pn => {
      setOpenPart(pn);
      setView("detail");
      window.scrollTo({
        top: 0
      });
    };
    const back = () => {
      setView("list");
      setOpenPart(null);
      window.scrollTo({
        top: 0
      });
    };
    const updatePart = (pn, patch) => setParts(arr => arr.map(p => p.part_no === pn ? {
      ...p,
      ...patch
    } : p));
    if (wiz) {
      const W = B().ExcelWizard;
      return /*#__PURE__*/React.createElement(W, {
        wiz: wiz,
        onClose: () => setWiz(null),
        onDone: s => flashFn("ok", "Excel 导入完成：" + s + "。")
      });
    }
    if (view === "detail") {
      const part = parts.find(p => p.part_no === openPart);
      return /*#__PURE__*/React.createElement(ProcessDetail, {
        part: part,
        onBack: back,
        onUpdate: updatePart,
        flashFn: flashFn
      });
    }
    return /*#__PURE__*/React.createElement(ProcessList, {
      parts: parts,
      setParts: setParts,
      onOpen: openDetail,
      onWiz: setWiz,
      flashFn: flashFn
    });
  }

  /* ============================================================ LIST */
  function ProcessList({
    parts,
    setParts,
    onOpen,
    onWiz,
    flashFn
  }) {
    const {
      Panel,
      Button,
      Badge,
      Table
    } = DS();
    const {
      Field,
      ActionCards,
      Toggle,
      ConfirmButton
    } = B();
    const [q, setQ] = useState("");
    const [sel, setSel] = useState({});
    const [form, setForm] = useState({
      part_no: "",
      part_name: "",
      route_raw: "",
      remark: "",
      strict: false
    });
    const [errors, setErrors] = useState({});
    const setField = patch => {
      setForm(f => ({
        ...f,
        ...patch
      }));
      setErrors(e => {
        const n = {
          ...e
        };
        Object.keys(patch).forEach(k => delete n[k]);
        return n;
      });
    };
    const cards = [{
      title: "批量维护路线文字",
      desc: "维护图号、名称和路线文字，系统会按路线生成零件工序清单和连续外协工序组。",
      maintainLabel: "批量维护路线",
      exportLabel: "导出当前路线",
      wizard: {
        kind: "routes",
        title: "批量维护路线文字",
        desc: "确认写入后按路线文字生成工序清单；生成失败的行计为错误，不写入。",
        strict: true
      }
    }, {
      title: "批量维护工序工时",
      desc: "维护自制工序的换型时间和单件工时；可选择只补空工时。",
      maintainLabel: "批量维护工时",
      exportLabel: "导出当前工时",
      wizard: {
        kind: "hours",
        title: "批量维护工序工时",
        desc: "维护自制工序换型/单件工时。",
        modeOptions: [{
          value: "overwrite",
          label: "更新已有工时"
        }, {
          value: "fill",
          label: "只补空工时"
        }],
        sampleRows: [{
          row_num: 2,
          status: "update",
          message: "更新换型/单件工时",
          data: {
            图号: "T-1008",
            工序: 5,
            换型: 0.5,
            单件: 1.2
          }
        }, {
          row_num: 3,
          status: "unchanged",
          message: "工时一致，跳过",
          data: {
            图号: "T-1009",
            工序: 10
          }
        }, {
          row_num: 4,
          status: "skip",
          message: "外协工序无工时，跳过",
          data: {
            图号: "T-1008",
            工序: 30
          }
        }]
      }
    }, {
      title: "导出工序清单",
      desc: "导出当前零件工序、归属、供应商和外协周期，用于复核。",
      exportLabel: "导出工序清单"
    }];
    const list = parts.filter(p => !q || (p.part_no + p.part_name + p.route_raw).toLowerCase().includes(q.toLowerCase()));
    const selCount = Object.values(sel).filter(Boolean).length;
    const toggleAll = on => {
      const m = {};
      if (on) list.forEach(p => m[p.part_no] = true);
      setSel(m);
    };
    const cols = [{
      key: "sel",
      title: /*#__PURE__*/React.createElement("input", {
        type: "checkbox",
        "aria-label": "\u5168\u9009",
        checked: list.length > 0 && selCount === list.length,
        onChange: e => toggleAll(e.target.checked)
      }),
      width: 44,
      render: r => /*#__PURE__*/React.createElement("input", {
        type: "checkbox",
        "aria-label": "选择 " + r.part_no,
        checked: !!sel[r.part_no],
        onChange: e => setSel(s => ({
          ...s,
          [r.part_no]: e.target.checked
        }))
      })
    }, {
      key: "part_no",
      title: "图号",
      width: 130,
      render: r => /*#__PURE__*/React.createElement("a", {
        className: "bd-link",
        onClick: () => onOpen(r.part_no)
      }, r.part_no)
    }, {
      key: "part_name",
      title: "名称",
      width: 150
    }, {
      key: "route_raw",
      title: "路线文字",
      render: r => r.route_raw ? /*#__PURE__*/React.createElement("span", {
        title: r.route_raw,
        style: {
          display: "block",
          maxWidth: 320,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap"
        }
      }, r.route_raw) : /*#__PURE__*/React.createElement("span", {
        className: "muted"
      }, "-")
    }, {
      key: "parsed",
      title: "工序清单",
      width: 110,
      render: r => /*#__PURE__*/React.createElement(Badge, {
        tone: r.parsed ? "ok" : "warning",
        dot: true
      }, r.parsed ? "已解析" : "未解析")
    }, {
      key: "act",
      title: "操作",
      width: 160,
      render: r => /*#__PURE__*/React.createElement("div", {
        className: "bd-cell-actions"
      }, /*#__PURE__*/React.createElement(Button, {
        variant: "secondary",
        size: "sm",
        onClick: () => onOpen(r.part_no)
      }, "\u67E5\u770B/\u7F16\u8F91"), /*#__PURE__*/React.createElement(ConfirmButton, {
        label: "\u5220\u9664",
        title: "删除零件 " + r.part_no + "？",
        body: /*#__PURE__*/React.createElement(React.Fragment, null, "\u5982\u679C\u8BE5\u96F6\u4EF6\u5DF2\u88AB\u6279\u6B21\u5F15\u7528\uFF0C\u5C06", /*#__PURE__*/React.createElement("strong", null, "\u62D2\u7EDD\u5220\u9664"), "\u4EE5\u4FDD\u62A4\u5DF2\u6709\u6392\u4EA7\u6570\u636E\u3002\u786E\u8BA4\u5220\u9664\u5417\uFF1F"),
        onConfirm: () => {
          setParts(arr => arr.filter(p => p.part_no !== r.part_no));
          flashFn("ok", "已删除零件 " + r.part_no + "。");
        }
      }))
    }];
    const submit = () => {
      const errs = {};
      if (!form.part_no) errs.part_no = "请填写图号。";else if (parts.some(p => p.part_no === form.part_no)) errs.part_no = "图号 " + form.part_no + " 已存在。";
      if (!form.part_name) errs.part_name = "请填写名称。";
      if (Object.keys(errs).length) {
        setErrors(errs);
        return;
      }
      setErrors({});
      setParts(arr => [{
        part_no: form.part_no,
        part_name: form.part_name,
        route_raw: form.route_raw,
        remark: form.remark,
        parsed: !!form.route_raw,
        ops: [],
        groups: []
      }, ...arr]);
      flashFn("ok", "已添加零件 " + form.part_no + (form.route_raw ? "，并尝试生成工序清单。" : "。"));
      setForm({
        part_no: "",
        part_name: "",
        route_raw: "",
        remark: "",
        strict: false
      });
    };
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(ActionCards, {
      title: "\u6279\u91CF\u7EF4\u62A4",
      subtitle: "\u9002\u5408 Excel \u4E0B\u53D1\u6216\u6574\u6279\u590D\u6838\uFF1B\u624B\u5DE5\u65B0\u589E\u7EE7\u7EED\u4F7F\u7528\u4E0B\u65B9\u8868\u5355\u3002",
      cards: cards,
      onOpen: onWiz
    }), /*#__PURE__*/React.createElement(Panel, {
      title: "\u65B0\u589E\u96F6\u4EF6"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u56FE\u53F7",
      required: true,
      error: errors.part_no
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1AA1234",
      value: form.part_no,
      onChange: e => setField({
        part_no: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u540D\u79F0",
      required: true,
      error: errors.part_name
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1A\u58F3\u4F53-\u5927",
      value: form.part_name,
      onChange: e => setField({
        part_name: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u8DEF\u7EBF\u6587\u5B57",
      hint: "\u53EF\u9009\uFF0C\u586B\u5199\u540E\u4F1A\u5C1D\u8BD5\u751F\u6210\u5DE5\u5E8F\u6E05\u5355\u3002",
      wide: true
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1A5\u6570\u94E310\u94B320\u6570\u8F6635\u6807\u537040\u603B\u68C045\u8868\u5904\u7406",
      value: form.route_raw,
      onChange: e => setForm({
        ...form,
        route_raw: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5907\u6CE8"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u53EF\u9009",
      value: form.remark,
      onChange: e => setForm({
        ...form,
        remark: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Toggle, {
      checked: form.strict,
      onChange: v => setForm({
        ...form,
        strict: v
      }),
      label: "\u8D44\u6599\u4E0D\u5B8C\u6574\u5C31\u505C\u4E0B\uFF08\u4E25\u683C\u6A21\u5F0F\uFF09",
      help: "\u52FE\u9009\u540E\uFF1A\u8DEF\u7EBF\u91CC\u6709\u4E0D\u8BA4\u8BC6\u7684\u5DE5\u79CD\u3001\u6CA1\u6709\u542F\u7528\u7684\u5916\u534F\u4F9B\u5E94\u5546\uFF0C\u6216\u5916\u534F\u5468\u671F\u65E0\u6548\u65F6\uFF0C\u4F1A\u76F4\u63A5\u63D0\u793A\u9519\u8BEF\u5E76\u505C\u6B62\u521B\u5EFA\u3002\u4E0D\u52FE\u9009\uFF1A\u96F6\u4EF6\u4F1A\u5148\u4FDD\u5B58\uFF0C\u7F3A\u5468\u671F\u7B49\u53EF\u8865\u9879\u5148\u6309 1 \u5929\u8BB0\u5F55\u5E76\u63D0\u9192\u8865\u6B63\u3002"
    })), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")
    }, Object.keys(errors).length ? /*#__PURE__*/React.createElement("span", {
      className: "bd-form-error"
    }, "\u8BF7\u586B\u5199\u6807\u7EA2\u7684\u5FC5\u586B\u9879") : null, /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: submit
    }, "\u6DFB\u52A0\u96F6\u4EF6"))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u96F6\u4EF6\u5DE5\u827A\u6A21\u677F",
      description: "\u6279\u91CF\u64CD\u4F5C\u53EF\u6279\u91CF\u5220\u9664\u96F6\u4EF6\uFF1B\u82E5\u96F6\u4EF6\u5DF2\u88AB\u6279\u6B21\u5F15\u7528\uFF0C\u5C06\u7981\u6B62\u5220\u9664\u4EE5\u907F\u514D\u5F71\u54CD\u5DF2\u6709\u6392\u4EA7\u6570\u636E\u3002"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-search"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u641C\u7D22"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u8F93\u5165\u56FE\u53F7\u3001\u540D\u79F0\u2026",
      value: q,
      onChange: e => setQ(e.target.value)
    }))), list.length ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "bd-table-scroll"
    }, /*#__PURE__*/React.createElement(Table, {
      columns: cols,
      rows: list,
      rowKey: "part_no"
    })), /*#__PURE__*/React.createElement("div", {
      className: "bd-action-bar"
    }, /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "\u5DF2\u9009 ", /*#__PURE__*/React.createElement("strong", {
      style: {
        fontVariantNumeric: "tabular-nums"
      }
    }, selCount), " \u4E2A\u96F6\u4EF6"), /*#__PURE__*/React.createElement(ConfirmButton, {
      label: "\u6279\u91CF\u5220\u9664",
      title: "\u6279\u91CF\u5220\u9664\u6240\u9009\u96F6\u4EF6\uFF1F",
      body: "\u82E5\u6240\u9009\u96F6\u4EF6\u5B58\u5728\u6279\u6B21\u5F15\u7528\uFF0C\u5BF9\u5E94\u884C\u5C06\u5220\u9664\u5931\u8D25\u5E76\u63D0\u793A\u3002\u786E\u8BA4\u7EE7\u7EED\u5417\uFF1F",
      onConfirm: () => {
        setParts(arr => arr.filter(p => !sel[p.part_no]));
        setSel({});
        flashFn("ok", "已批量删除 " + selCount + " 个零件。");
      }
    }))) : /*#__PURE__*/React.createElement(B_Empty, {
      title: "\u8FD8\u6CA1\u6709\u96F6\u4EF6\u6570\u636E",
      desc: "\u53EF\u4EE5\u624B\u52A8\u65B0\u589E\uFF0C\u6216\u7528\u4E0A\u65B9 Excel \u6279\u91CF\u7EF4\u62A4\u5BFC\u5165\u3002"
    })));
  }

  /* ============================================================ DETAIL */
  function ProcessDetail({
    part,
    onBack,
    onUpdate,
    flashFn
  }) {
    const {
      Panel,
      Button,
      Badge,
      Table
    } = DS();
    const {
      Field,
      Toggle,
      ConfirmButton
    } = B();
    const [base, setBase] = useState({
      part_name: part.part_name,
      route_raw: part.route_raw,
      remark: part.remark
    });
    const [reparse, setReparse] = useState({
      route_raw: part.route_raw,
      strict: false
    });
    const internal = part.ops.filter(o => o.source === "internal").length;
    const external = part.ops.filter(o => o.source === "external").length;
    const opCols = [{
      key: "seq",
      title: "工序",
      width: 80,
      align: "right",
      render: r => /*#__PURE__*/React.createElement("span", {
        style: {
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          fontVariantNumeric: "tabular-nums"
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          width: 3,
          height: 16,
          borderRadius: 2,
          background: r.source === "external" ? "var(--ui-warning)" : "var(--ui-primary)"
        }
      }), r.seq)
    }, {
      key: "op_type",
      title: "工种",
      width: 110
    }, {
      key: "source",
      title: "归属",
      width: 90,
      render: r => /*#__PURE__*/React.createElement(Badge, {
        tone: r.source === "external" ? "warning" : "notice",
        dot: true
      }, sourceZh(r.source))
    }, {
      key: "config",
      title: "配置",
      render: r => r.source === "internal" ? /*#__PURE__*/React.createElement(InternalHoursCell, {
        op: r,
        part: part,
        onUpdate: onUpdate,
        flashFn: flashFn
      }) : /*#__PURE__*/React.createElement("span", {
        className: "bd-cell-note"
      }, "\u5468\u671F\u7531\u8FDE\u7EED\u5916\u534F\u5DE5\u5E8F\u7EC4\u7EDF\u4E00\u7BA1\u7406")
    }, {
      key: "ext",
      title: "外协信息",
      width: 220,
      render: r => r.source === "external" ? /*#__PURE__*/React.createElement("div", {
        className: "bd-cell-note"
      }, /*#__PURE__*/React.createElement("div", null, "\u4F9B\u5E94\u5546\uFF1A", r.supplier || "-"), r.group ? /*#__PURE__*/React.createElement("div", null, "\u8FDE\u7EED\u5916\u534F\u5DE5\u5E8F\u7EC4\uFF1A", r.group) : null, /*#__PURE__*/React.createElement("div", null, "\u5468\u671F\uFF1A", r.ext_days != null ? r.ext_days + " 天" : /*#__PURE__*/React.createElement("span", {
        style: {
          color: "var(--ui-warning-text)"
        }
      }, "\u5F85\u8865"))) : /*#__PURE__*/React.createElement("span", {
        className: "muted"
      }, "-")
    }];
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(Panel, {
      title: "\u96F6\u4EF6\u5DE5\u827A\u6A21\u677F \xB7 \u8BE6\u60C5",
      description: "\u7EF4\u62A4\u5355\u4E2A\u96F6\u4EF6\u7684\u8DEF\u7EBF\u6587\u5B57\u3001\u5DE5\u5E8F\u6E05\u5355\u3001\u81EA\u5236\u5DE5\u65F6\u548C\u8FDE\u7EED\u5916\u534F\u5DE5\u5E8F\u5468\u671F\u3002",
      headerRight: /*#__PURE__*/React.createElement(Button, {
        variant: "ghost",
        size: "sm",
        onClick: onBack
      }, "\u2190 \u8FD4\u56DE\u5217\u8868")
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-meta-row"
    }, /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u56FE\u53F7\uFF1A"), /*#__PURE__*/React.createElement("strong", null, part.part_no)), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u540D\u79F0\uFF1A"), /*#__PURE__*/React.createElement("strong", null, part.part_name)), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u5DE5\u5E8F\u6E05\u5355\uFF1A"), /*#__PURE__*/React.createElement(Badge, {
      tone: part.parsed ? "ok" : "warning",
      dot: true
    }, part.parsed ? "已解析" : "未解析")))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u2460 \u96F6\u4EF6\u57FA\u7840\u4FE1\u606F"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u56FE\u53F7"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      value: part.part_no,
      disabled: true
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u540D\u79F0",
      required: true
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      value: base.part_name,
      onChange: e => setBase({
        ...base,
        part_name: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u8DEF\u7EBF\u6587\u5B57",
      wide: true,
      hint: "\u53EF\u542B\u7A7A\u683C\u3001\u9017\u53F7\u3001\u987F\u53F7\u3001\u7834\u6298\u53F7\u7B49\u5206\u9694\u7B26\uFF1B\u751F\u6210\u5DE5\u5E8F\u6E05\u5355\u65F6\u4F1A\u7EDF\u4E00\u5904\u7406\u3002"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      value: base.route_raw,
      onChange: e => setBase({
        ...base,
        route_raw: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5907\u6CE8"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u53EF\u9009",
      value: base.remark,
      onChange: e => setBase({
        ...base,
        remark: e.target.value
      })
    }))), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer"
    }, /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: () => {
        onUpdate(part.part_no, base);
        flashFn("ok", "已保存基础信息。");
      }
    }, "\u4FDD\u5B58"))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u2461 \u6309\u8DEF\u7EBF\u91CD\u65B0\u751F\u6210\u5DE5\u5E8F\u6E05\u5355",
      description: "\u4FDD\u5B58\u540E\u7CFB\u7EDF\u4F1A\u6309\u8FD9\u6BB5\u8DEF\u7EBF\u6587\u5B57\u91CD\u65B0\u751F\u6210\u5DE5\u5E8F\u6E05\u5355\uFF1B\u82E5\u751F\u6210\u5931\u8D25\uFF0C\u539F\u5DE5\u5E8F\u6E05\u5355\u4E0D\u4F1A\u88AB\u6539\u52A8\u3002"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u7528\u4E8E\u751F\u6210\u5DE5\u5E8F\u6E05\u5355\u7684\u8DEF\u7EBF\u6587\u5B57",
      wide: true
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      value: reparse.route_raw,
      onChange: e => setReparse({
        ...reparse,
        route_raw: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Toggle, {
      checked: reparse.strict,
      onChange: v => setReparse({
        ...reparse,
        strict: v
      }),
      label: "\u8D44\u6599\u4E0D\u5B8C\u6574\u5C31\u505C\u4E0B\uFF08\u4E25\u683C\u6A21\u5F0F\uFF09",
      help: "\u52FE\u9009\u540E\uFF1A\u4E0D\u8BA4\u8BC6\u7684\u5DE5\u79CD\u3001\u672A\u542F\u7528\u5916\u534F\u4F9B\u5E94\u5546\u6216\u5916\u534F\u5468\u671F\u65E0\u6548\u65F6\u76F4\u63A5\u62A5\u9519\u5E76\u505C\u6B62\u751F\u6210\u3002\u4E0D\u52FE\u9009\uFF1A\u80FD\u786E\u8BA4\u7684\u5DE5\u5E8F\u7EE7\u7EED\u5904\u7406\uFF0C\u7F3A\u5468\u671F\u5148\u6309 1 \u5929\u8BB0\u5F55\u5E76\u63D0\u9192\u8865\u6B63\u3002"
    })), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer"
    }, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "md",
      onClick: () => {
        onUpdate(part.part_no, {
          route_raw: reparse.route_raw,
          parsed: true
        });
        flashFn("ok", "已按路线重新生成工序清单。");
      }
    }, "\u6309\u8DEF\u7EBF\u91CD\u65B0\u751F\u6210\u5DE5\u5E8F\u6E05\u5355"))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u2462 \u5DE5\u5E8F\u6982\u51B5"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-summary-grid"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-summary-item sev-notice"
    }, /*#__PURE__*/React.createElement("span", {
      className: "si-label"
    }, "\u5DE5\u5E8F\u603B\u6570"), /*#__PURE__*/React.createElement("span", {
      className: "si-value"
    }, part.ops.length)), /*#__PURE__*/React.createElement("div", {
      className: "bd-summary-item sev-notice"
    }, /*#__PURE__*/React.createElement("span", {
      className: "si-label"
    }, "\u81EA\u5236\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("span", {
      className: "si-value"
    }, internal)), /*#__PURE__*/React.createElement("div", {
      className: "bd-summary-item sev-notice"
    }, /*#__PURE__*/React.createElement("span", {
      className: "si-label"
    }, "\u5916\u534F\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("span", {
      className: "si-value"
    }, external))), part.ops.length === 0 ? /*#__PURE__*/React.createElement("p", {
      className: "bd-sec-sub",
      style: {
        marginTop: 12
      }
    }, "\u8FD8\u6CA1\u6709\u5DE5\u5E8F\uFF1A\u8BF7\u5728\u4E0A\u65B9\u586B\u5199\u8DEF\u7EBF\u6587\u5B57\u5E76\u70B9\u51FB\u201C\u6309\u8DEF\u7EBF\u91CD\u65B0\u751F\u6210\u5DE5\u5E8F\u6E05\u5355\u201D\u3002") : null), /*#__PURE__*/React.createElement(Panel, {
      title: "\u2463 \u5DE5\u5E8F\u6E05\u5355",
      description: "\u84DD\u8272=\u81EA\u5236\u5DE5\u5E8F\uFF0C\u6A59\u8272=\u5916\u534F\u5DE5\u5E8F\u3002\u81EA\u5236\u5DE5\u5E8F\u53EF\u9010\u884C\u7F16\u8F91\u6362\u578B/\u5355\u4EF6\u5DE5\u65F6\u3002"
    }, part.ops.length ? /*#__PURE__*/React.createElement("div", {
      className: "bd-table-scroll"
    }, /*#__PURE__*/React.createElement(Table, {
      columns: opCols,
      rows: part.ops.map(o => ({
        ...o,
        id: o.seq
      })),
      rowKey: "seq"
    })) : /*#__PURE__*/React.createElement(B_Empty, {
      title: "\u6682\u65E0\u5DE5\u5E8F\u6E05\u5355",
      desc: "\u5148\u5728\u4E0A\u65B9\u6309\u8DEF\u7EBF\u751F\u6210\u5DE5\u5E8F\u6E05\u5355\u3002"
    })), /*#__PURE__*/React.createElement(Panel, {
      title: "\u2464 \u8FDE\u7EED\u5916\u534F\u5DE5\u5E8F\u5468\u671F",
      description: "\u6BCF\u4E2A\u8FDE\u7EED\u5916\u534F\u5DE5\u5E8F\u7EC4\u5355\u72EC\u8BBE\u7F6E\u5468\u671F\u6A21\u5F0F\u4E0E\u5468\u671F\uFF08\u5929\uFF09\u3002"
    }, part.groups.length ? part.groups.map(g => /*#__PURE__*/React.createElement(ExternalGroup, {
      key: g.id,
      group: g,
      part: part,
      onUpdate: onUpdate,
      flashFn: flashFn
    })) : /*#__PURE__*/React.createElement(B_Empty, {
      title: "\u6682\u65E0\u5916\u534F\u5DE5\u5E8F\u7EC4",
      desc: "\u5F53\u524D\u6A21\u677F\u4E2D\u6CA1\u6709\u8FDE\u7EED\u5916\u534F\u5DE5\u5E8F\u3002"
    })));
  }
  function InternalHoursCell({
    op,
    part,
    onUpdate,
    flashFn
  }) {
    const {
      Button
    } = DS();
    const {
      Field
    } = B();
    const [v, setV] = useState({
      setup: op.setup,
      unit: op.unit
    });
    const dirty = String(v.setup) !== String(op.setup) || String(v.unit) !== String(op.unit);
    const save = () => {
      onUpdate(part.part_no, {
        ops: part.ops.map(o => o.seq === op.seq ? {
          ...o,
          setup: Number(v.setup) || 0,
          unit: Number(v.unit) || 0
        } : o)
      });
      flashFn("ok", "已保存工序 " + op.seq + " 的工时。");
    };
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-inline-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u6362\u578B\uFF08\u5C0F\u65F6\uFF09"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-cell-input num" + (dirty ? " bd-cell-dirty" : ""),
      style: {
        width: 90
      },
      value: v.setup,
      onChange: e => setV({
        ...v,
        setup: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5355\u4EF6\uFF08\u5C0F\u65F6\uFF09"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-cell-input num" + (dirty ? " bd-cell-dirty" : ""),
      style: {
        width: 90
      },
      value: v.unit,
      onChange: e => setV({
        ...v,
        unit: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Button, {
      variant: dirty ? "primary" : "secondary",
      size: "sm",
      disabled: !dirty,
      onClick: save
    }, "\u4FDD\u5B58"));
  }
  function ExternalGroup({
    group,
    part,
    onUpdate,
    flashFn
  }) {
    const {
      Button,
      Table
    } = DS();
    const {
      Field,
      ConfirmButton
    } = B();
    const gops = part.ops.filter(o => o.group === group.id && o.source === "external");
    const [g, setG] = useState({
      mode: group.mode,
      total: group.total ?? "",
      strict: group.strict
    });
    const [days, setDays] = useState(() => {
      const m = {};
      gops.forEach(o => m[o.seq] = o.ext_days ?? "");
      return m;
    });
    const saveGroup = () => {
      onUpdate(part.part_no, {
        groups: part.groups.map(x => x.id === group.id ? {
          ...x,
          mode: g.mode,
          total: g.total === "" ? null : Number(g.total),
          strict: g.strict
        } : x),
        ops: part.ops.map(o => o.group === group.id ? {
          ...o,
          ext_days: days[o.seq] === "" ? null : Number(days[o.seq])
        } : o)
      });
      flashFn("ok", "已保存外协组 " + group.id + " 设置。");
    };
    const cols = [{
      key: "seq",
      title: "工序",
      width: 70,
      align: "right",
      render: r => /*#__PURE__*/React.createElement("span", {
        style: {
          fontVariantNumeric: "tabular-nums"
        }
      }, r.seq)
    }, {
      key: "op_type",
      title: "工种",
      width: 110
    }, {
      key: "ext_days",
      title: "周期（天，仅分别设置使用）",
      align: "right",
      render: r => /*#__PURE__*/React.createElement("input", {
        className: "bd-cell-input num",
        style: {
          width: 120
        },
        placeholder: "\u5982\uFF1A1",
        value: days[r.seq],
        disabled: g.mode === "merged",
        onChange: e => setDays({
          ...days,
          [r.seq]: e.target.value
        })
      })
    }, {
      key: "hint",
      title: "提示",
      render: () => /*#__PURE__*/React.createElement("span", {
        className: "bd-cell-note"
      }, g.mode === "merged" ? "合并设置：此处周期不生效，以整组周期为准。" : "分别设置：每道外协工序单独计时。")
    }];
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-group-box"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-group-head"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "gh-title"
    }, "\u8FDE\u7EED\u5916\u534F\u5DE5\u5E8F\u7EC4\uFF1A", group.id, "\uFF08", group.start, " \u2013 ", group.end, "\uFF09"), /*#__PURE__*/React.createElement("div", {
      className: "gh-meta"
    }, "\u6A21\u5F0F\uFF1A", g.mode === "merged" ? "合并设置" : "分别设置")), group.deletable ? /*#__PURE__*/React.createElement(ConfirmButton, {
      label: "\u5220\u9664\u6B64\u7EC4",
      title: "删除外协工序组 " + group.id + "？",
      body: "\u5220\u9664\u540E\u8BE5\u7EC4\u5DE5\u5E8F\u5C06\u56DE\u5230\u672A\u914D\u7F6E\u5468\u671F\u72B6\u6001\u3002\u786E\u8BA4\u5220\u9664\u5417\uFF1F",
      onConfirm: () => {
        onUpdate(part.part_no, {
          groups: part.groups.filter(x => x.id !== group.id)
        });
        flashFn("ok", "已删除外协组 " + group.id + "。");
      }
    }) : /*#__PURE__*/React.createElement("span", {
      className: "muted",
      style: {
        fontSize: 12.5
      }
    }, "\u4E0D\u53EF\u5220\u9664\uFF08\u53EA\u6709\u6392\u5728\u6700\u524D\u6216\u6700\u540E\u7684\u5916\u534F\u7EC4\u624D\u80FD\u5220\u9664\uFF09")), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u5468\u671F\u6A21\u5F0F"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: g.mode,
      onChange: e => setG({
        ...g,
        mode: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "separate"
    }, "\u5206\u522B\u8BBE\u7F6E"), /*#__PURE__*/React.createElement("option", {
      value: "merged"
    }, "\u5408\u5E76\u8BBE\u7F6E"))), /*#__PURE__*/React.createElement(Field, {
      label: "\u6574\u7EC4\u5468\u671F\uFF08\u5929\uFF0C\u4EC5\u5408\u5E76\u8BBE\u7F6E\u4F7F\u7528\uFF09",
      hint: "\u9009\u201C\u5408\u5E76\u8BBE\u7F6E\u201D\u540E\u6574\u7EC4\u53EA\u6309\u8FD9\u91CC\u8BA1\u7B97\uFF1B\u9009\u201C\u5206\u522B\u8BBE\u7F6E\u201D\u65F6\u6B64\u5904\u4E0D\u751F\u6548\u3002"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input num",
      style: {
        maxWidth: 130
      },
      placeholder: "\u5982\uFF1A3",
      value: g.total,
      disabled: g.mode !== "merged",
      onChange: e => setG({
        ...g,
        total: e.target.value
      })
    })), /*#__PURE__*/React.createElement(window.BD.Toggle, {
      checked: g.strict,
      onChange: v => setG({
        ...g,
        strict: v
      }),
      label: "\u8D44\u6599\u4E0D\u5B8C\u6574\u5C31\u505C\u4E0B\uFF08\u4E25\u683C\u6A21\u5F0F\uFF09",
      help: "\u52FE\u9009\u540E\uFF1A\u5206\u522B\u8BBE\u7F6E\u65F6\u6BCF\u9053\u5916\u534F\u5DE5\u5E8F\u90FD\u5FC5\u987B\u586B\u6B63\u786E\u5468\u671F\uFF0C\u586B\u7A7A/\u975E\u6570\u5B57/\u22640 \u4F1A\u62A5\u9519\u3002\u4E0D\u52FE\u9009\uFF1A\u7EE7\u7EED\u4FDD\u5B58\u5E76\u628A\u6CA1\u586B\u597D\u7684\u5468\u671F\u5148\u6309 1 \u5929\u8BB0\u5F55\u3002"
    })), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer"
    }, /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: saveGroup
    }, "\u4FDD\u5B58\u5916\u534F\u7EC4\u8BBE\u7F6E")), gops.length ? /*#__PURE__*/React.createElement("div", {
      className: "bd-table-scroll",
      style: {
        marginTop: 14
      }
    }, /*#__PURE__*/React.createElement(Table, {
      columns: cols,
      rows: gops.map(o => ({
        ...o,
        id: o.seq
      })),
      rowKey: "seq"
    })) : /*#__PURE__*/React.createElement("p", {
      className: "bd-sec-sub",
      style: {
        marginTop: 12
      }
    }, "\u8BE5\u7EC4\u6682\u65E0\u5916\u534F\u5DE5\u5E8F\u3002"));
  }
  function B_Empty(props) {
    const E = window.BD.Empty;
    return /*#__PURE__*/React.createElement(E, props);
  }
  window.ProcessTab = ProcessTab;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/BaseProcess.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/BaseShared.jsx
try { (() => {
// APS Workbench · 基础资料 shared primitives  →  window.BD.*
// Reusable design-system pieces: tabs, fields, toggle, Excel 三步流向导,
// inline-edit helpers, flash, confirm dialog, empty state, pager, summary.
(function () {
  const {
    useState,
    useRef,
    useEffect
  } = React;
  const DS = () => window.APSDesignSystem_edbc5d;

  /* ---------- canonical 工种 seed (shared across 工艺 / 自制 / 外协 / 设备 / 人员 / 供应商) ---------- */
  const OP_TYPES_SEED = [{
    op_type_id: "OT001",
    name: "数铣",
    category: "internal",
    remark: ""
  }, {
    op_type_id: "OT002",
    name: "数车",
    category: "internal",
    remark: ""
  }, {
    op_type_id: "OT003",
    name: "钳工",
    category: "internal",
    remark: ""
  }, {
    op_type_id: "OT004",
    name: "精磨",
    category: "internal",
    remark: ""
  }, {
    op_type_id: "OT005",
    name: "钻孔",
    category: "internal",
    remark: ""
  }, {
    op_type_id: "OT006",
    name: "总检",
    category: "internal",
    remark: "关键工序"
  }, {
    op_type_id: "OT007",
    name: "标印",
    category: "internal",
    remark: ""
  }, {
    op_type_id: "OT008",
    name: "表处理",
    category: "internal",
    remark: ""
  }, {
    op_type_id: "OT051",
    name: "电镀",
    category: "external",
    remark: ""
  }, {
    op_type_id: "OT052",
    name: "发黑",
    category: "external",
    remark: ""
  }, {
    op_type_id: "OT053",
    name: "热处理",
    category: "external",
    remark: ""
  }, {
    op_type_id: "OT054",
    name: "喷涂",
    category: "external",
    remark: ""
  }];
  const opTypeNames = cat => OP_TYPES_SEED.filter(o => !cat || o.category === cat).map(o => o.name);

  /* ---------- segmented control (结构切换 / 二选一) ---------- */
  function Seg({
    options,
    value,
    onChange,
    ariaLabel
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-seg",
      role: "group",
      "aria-label": ariaLabel
    }, options.map(o => /*#__PURE__*/React.createElement("button", {
      key: o.value,
      type: "button",
      className: "bd-seg-btn",
      "aria-pressed": value === o.value,
      onClick: () => onChange(o.value)
    }, o.label)));
  }

  /* ---------- status chips list (技能工种 / 多标签) ---------- */
  function Chips({
    items,
    tone
  }) {
    if (!items || !items.length) return /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "-");
    return /*#__PURE__*/React.createElement("span", {
      className: "bd-chips"
    }, items.map(t => /*#__PURE__*/React.createElement("span", {
      key: t,
      className: "bd-chip" + (tone ? " tone-" + tone : "")
    }, t)));
  }

  /* ---------- multi-select checkbox group (人员技能工种) ---------- */
  function CheckGroup({
    options,
    value,
    onChange
  }) {
    const set = new Set(value || []);
    const toggle = v => {
      const n = new Set(set);
      n.has(v) ? n.delete(v) : n.add(v);
      onChange(Array.from(n));
    };
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-check-group"
    }, options.map(o => /*#__PURE__*/React.createElement("label", {
      key: o,
      className: "bd-check" + (set.has(o) ? " is-on" : "")
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: set.has(o),
      onChange: () => toggle(o)
    }), o)));
  }

  /* ---------- 一级 / 二级 tab ---------- */
  function PrimaryTabs({
    tabs,
    value,
    onChange
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-tabs",
      role: "tablist",
      "aria-label": "\u57FA\u7840\u8D44\u6599\u5206\u6BB5"
    }, tabs.map(t => /*#__PURE__*/React.createElement("button", {
      key: t.id,
      type: "button",
      role: "tab",
      className: "bd-tab",
      "data-chain": t.chain || undefined,
      "aria-current": value === t.id ? "page" : undefined,
      onClick: () => onChange(t.id)
    }, t.label, t.chain ? /*#__PURE__*/React.createElement("span", {
      className: "bd-tab-dot"
    }) : null)));
  }
  function SubTabs({
    tabs,
    value,
    onChange
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-subtabs",
      role: "tablist"
    }, tabs.map(t => /*#__PURE__*/React.createElement("button", {
      key: t.id,
      type: "button",
      role: "tab",
      className: "bd-subtab",
      "aria-current": value === t.id ? "true" : undefined,
      onClick: () => onChange(t.id)
    }, t.label)));
  }

  /* ---------- form field ---------- */
  function Field({
    label,
    required,
    hint,
    wide,
    error,
    children
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-field" + (wide ? " bd-wide" : "") + (error ? " is-error" : "")
    }, label ? /*#__PURE__*/React.createElement("label", null, label, required ? /*#__PURE__*/React.createElement("span", {
      className: "req"
    }, "*") : null) : null, children, error ? /*#__PURE__*/React.createElement("span", {
      className: "bd-field-error"
    }, error) : hint ? /*#__PURE__*/React.createElement("span", {
      className: "bd-hint"
    }, hint) : null);
  }
  function StrictSeg({
    checked,
    onChange,
    onText,
    offText,
    disabled,
    ariaLabel
  }) {
    const on = onText || "严格拦截";
    const off = offText || "宽松放行";
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-seg",
      role: "group",
      "aria-label": ariaLabel
    }, /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "bd-seg-btn",
      "aria-pressed": checked,
      disabled: disabled,
      style: {
        "--bd-seg-accent": "var(--ui-warning)"
      },
      onClick: () => !disabled && onChange(true)
    }, /*#__PURE__*/React.createElement("span", {
      className: "bd-seg-dot"
    }), on), /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "bd-seg-btn",
      "aria-pressed": !checked,
      disabled: disabled,
      style: {
        "--bd-seg-accent": "var(--ui-primary)"
      },
      onClick: () => !disabled && onChange(false)
    }, /*#__PURE__*/React.createElement("span", {
      className: "bd-seg-dot"
    }), off));
  }

  /* outcome accents for the 数据校验 preview line */
  const STRICT_OC = {
    wrap: {
      "--oc-bg": "var(--ui-warning-bg)",
      "--oc-border": "var(--ui-warning-border)",
      "--oc-text": "var(--ui-warning-text)",
      "--oc-accent": "var(--ui-warning)"
    },
    ico: "!",
    lead: "严格拦截。",
    desc: "数据不正确就停下并提示原因，不生成工序。"
  };
  const LOOSE_OC = {
    wrap: {
      "--oc-bg": "var(--ui-info-bg)",
      "--oc-border": "var(--ui-info-border)",
      "--oc-text": "var(--ui-info-text)",
      "--oc-accent": "var(--ui-primary)"
    },
    ico: "i",
    lead: "宽松放行。",
    desc: "能确认的工序先生成，缺项按默认值记录并提醒补正。"
  };
  function Toggle({
    checked,
    onChange,
    label,
    help,
    onText,
    offText
  }) {
    const oc = checked ? STRICT_OC : LOOSE_OC;
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-toggle-field"
    }, /*#__PURE__*/React.createElement("label", null, "\u6570\u636E\u6821\u9A8C"), /*#__PURE__*/React.createElement(StrictSeg, {
      checked: checked,
      onChange: onChange,
      onText: onText,
      offText: offText,
      ariaLabel: label || "数据校验"
    }), /*#__PURE__*/React.createElement("div", {
      className: "bd-seg-outcome",
      style: oc.wrap
    }, /*#__PURE__*/React.createElement("span", {
      className: "oc-ico"
    }, oc.ico), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("b", null, oc.lead), oc.desc)), help ? /*#__PURE__*/React.createElement("details", {
      className: "bd-toggle-help"
    }, /*#__PURE__*/React.createElement("summary", null, "\u67E5\u770B\u8BE6\u7EC6\u89C4\u5219"), /*#__PURE__*/React.createElement("div", null, help)) : null);
  }

  /* ---------- date input wired to the page's APSDatePicker (not the native control) ---------- */
  function DateInput({
    value,
    onChange,
    className,
    placeholder,
    disabled,
    min,
    max
  }) {
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
    return /*#__PURE__*/React.createElement("input", {
      ref: ref,
      type: "date",
      className: className || "bd-input",
      placeholder: placeholder,
      disabled: disabled,
      min: min,
      max: max,
      defaultValue: value || "",
      onChange: e => onChange(e.target.value)
    });
  }

  /* ---------- flash ---------- */
  function useFlash() {
    const [flash, setFlash] = useState(null);
    const show = (tone, msg) => setFlash({
      tone,
      msg,
      id: Date.now()
    });
    return [flash, show, () => setFlash(null)];
  }
  function Flash({
    flash
  }) {
    const [closedId, setClosedId] = useState(null);
    useEffect(() => {
      if (!flash) return;
      const ms = flash.tone === "danger" || flash.tone === "warning" ? 6000 : 3600;
      const t = setTimeout(() => setClosedId(flash.id), ms);
      return () => clearTimeout(t);
    }, [flash && flash.id]);
    if (!flash || closedId === flash.id) return null;
    // Portal to <body> so the fixed-position toast never sits as a flow sibling
    // (otherwise `.bd-card-gap > * + *` would push the page content down 16px).
    return ReactDOM.createPortal(/*#__PURE__*/React.createElement("div", {
      className: "bd-toast",
      role: "status",
      "aria-live": "polite",
      key: flash.id
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-flash tone-" + flash.tone
    }, /*#__PURE__*/React.createElement("span", {
      className: "bd-flash-dot"
    }), /*#__PURE__*/React.createElement("span", null, flash.msg), /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "bd-toast-close",
      "aria-label": "\u5173\u95ED",
      onClick: () => setClosedId(flash.id)
    }, "\xD7"))), document.body);
  }

  /* ---------- empty state ---------- */
  function Empty({
    title,
    desc
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-empty"
    }, /*#__PURE__*/React.createElement("div", {
      className: "be-title"
    }, title), desc ? /*#__PURE__*/React.createElement("div", {
      className: "be-desc"
    }, desc) : null);
  }

  /* ---------- confirm dialog ---------- */
  function ConfirmButton({
    label,
    variant = "danger",
    size = "sm",
    title,
    body,
    confirmLabel = "确认删除",
    onConfirm,
    btnStyle
  }) {
    const {
      Button
    } = DS();
    const [open, setOpen] = useState(false);
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      variant: variant,
      size: size,
      style: btnStyle,
      onClick: () => setOpen(true)
    }, label), open ? /*#__PURE__*/React.createElement("div", {
      className: "bd-modal-backdrop",
      onClick: () => setOpen(false)
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-modal",
      role: "dialog",
      "aria-modal": "true",
      onClick: e => e.stopPropagation()
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-modal-head"
    }, /*#__PURE__*/React.createElement("h4", null, title || "确认删除")), /*#__PURE__*/React.createElement("div", {
      className: "bd-modal-body"
    }, body), /*#__PURE__*/React.createElement("div", {
      className: "bd-modal-foot"
    }, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "md",
      onClick: () => setOpen(false)
    }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
      variant: "danger",
      size: "md",
      onClick: () => {
        setOpen(false);
        onConfirm && onConfirm();
      }
    }, confirmLabel)))) : null);
  }

  /* ---------- pager (display only) ---------- */
  function Pager({
    page,
    totalPages,
    total,
    onPrev,
    onNext
  }) {
    if (!totalPages || totalPages <= 1) return null;
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-info-line"
    }, /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "\u7B2C ", page, " / ", totalPages, " \u9875\uFF08\u5171 ", total, " \u6761\uFF09"), page > 1 ? /*#__PURE__*/React.createElement("a", {
      className: "bd-link",
      onClick: onPrev
    }, "\u4E0A\u4E00\u9875") : null, page < totalPages ? /*#__PURE__*/React.createElement("a", {
      className: "bd-link",
      onClick: onNext
    }, "\u4E0B\u4E00\u9875") : null);
  }

  /* ---------- summary cards ---------- */
  function SummaryGrid({
    items
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-summary-grid"
    }, items.map(it => /*#__PURE__*/React.createElement("div", {
      className: "bd-summary-item sev-" + it.sev,
      key: it.label
    }, /*#__PURE__*/React.createElement("span", {
      className: "si-label"
    }, it.label), /*#__PURE__*/React.createElement("span", {
      className: "si-value"
    }, it.value))));
  }
  function InfoStrip({
    cells
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-info-strip"
    }, cells.map(c => /*#__PURE__*/React.createElement("div", {
      className: "is-cell",
      key: c.k
    }, /*#__PURE__*/React.createElement("span", {
      className: "is-k"
    }, c.k), /*#__PURE__*/React.createElement("span", {
      className: "is-v"
    }, c.v))));
  }

  /* ---------- Excel action cards ---------- */
  function ActionCards({
    title,
    subtitle,
    cards,
    onOpen
  }) {
    const {
      Button
    } = DS();
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-section"
    }, /*#__PURE__*/React.createElement("h3", {
      className: "bd-sec-title"
    }, title), /*#__PURE__*/React.createElement("p", {
      className: "bd-sec-sub"
    }, subtitle), /*#__PURE__*/React.createElement("div", {
      className: "bd-action-cards"
    }, cards.map(c => /*#__PURE__*/React.createElement("div", {
      className: "bd-action-card" + (c.cycle ? " tone-cycle" : ""),
      key: c.title
    }, /*#__PURE__*/React.createElement("div", {
      className: "ac-title"
    }, c.title), /*#__PURE__*/React.createElement("div", {
      className: "ac-desc"
    }, c.desc), /*#__PURE__*/React.createElement("div", {
      className: "ac-actions"
    }, c.wizard ? /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "sm",
      onClick: () => onOpen(c.wizard)
    }, c.maintainLabel || "批量维护") : null, c.exportLabel ? /*#__PURE__*/React.createElement(Button, {
      variant: c.wizard ? "ghost" : "secondary",
      size: "sm"
    }, c.exportLabel) : null)))));
  }

  /* ---------- Excel 三步流向导 ---------- */
  const STATUS_META = {
    new: {
      label: "新增",
      tone: "success"
    },
    update: {
      label: "更新",
      tone: "primary"
    },
    unchanged: {
      label: "无变化",
      tone: "secondary"
    },
    skip: {
      label: "跳过",
      tone: "warning"
    },
    error: {
      label: "错误",
      tone: "danger"
    }
  };
  function ExcelWizard({
    wiz,
    onClose,
    onDone
  }) {
    const {
      Button,
      Panel,
      Table,
      Badge
    } = DS();
    const [step, setStep] = useState(1);
    const [fileName, setFileName] = useState("");
    const [mode, setMode] = useState(wiz.modeOptions && wiz.modeOptions[0].value || "overwrite");
    const [strict, setStrict] = useState(false);
    const rows = wiz.sampleRows || DEFAULT_SAMPLE;
    const hasError = rows.some(r => r.status === "error");
    const checkCols = [{
      key: "row_num",
      title: "行号",
      width: 70,
      align: "right",
      render: r => /*#__PURE__*/React.createElement("span", {
        style: {
          fontVariantNumeric: "tabular-nums"
        }
      }, r.row_num)
    }, {
      key: "status",
      title: "结果",
      width: 90,
      render: r => /*#__PURE__*/React.createElement(Badge, {
        tone: STATUS_META[r.status].tone,
        dot: true
      }, STATUS_META[r.status].label)
    }, {
      key: "message",
      title: "问题或说明",
      render: r => /*#__PURE__*/React.createElement("span", {
        style: {
          color: r.status === "error" ? "var(--ui-danger-text)" : "inherit"
        }
      }, r.message)
    }, {
      key: "detail",
      title: "详情",
      width: 90,
      render: r => /*#__PURE__*/React.createElement(RowDetail, {
        r: r
      })
    }];
    return /*#__PURE__*/React.createElement(Panel, {
      title: wiz.title,
      description: wiz.desc,
      headerRight: /*#__PURE__*/React.createElement(Button, {
        variant: "ghost",
        size: "sm",
        onClick: onClose
      }, "\u2190 \u8FD4\u56DE\u5217\u8868")
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-wizard-steps"
    }, ["选择并上传", "检查结果", "写入系统"].map((s, i) => {
      const n = i + 1;
      const cls = step > n ? "is-done" : step === n ? "is-active" : "";
      return /*#__PURE__*/React.createElement("div", {
        className: "bd-wstep " + cls,
        key: s
      }, /*#__PURE__*/React.createElement("span", {
        className: "ws-num"
      }, step > n ? "✓" : n), s);
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        gap: 10,
        flexWrap: "wrap",
        marginBottom: 14
      }
    }, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "sm"
    }, "\u4E0B\u8F7D\u6A21\u677F\uFF08.xlsx\uFF09"), /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      size: "sm"
    }, "\u5BFC\u51FA\u5F53\u524D\u6570\u636E")), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid",
      style: {
        marginBottom: 14
      }
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u5BFC\u5165\u6A21\u5F0F"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: mode,
      onChange: e => setMode(e.target.value),
      disabled: step > 1
    }, (wiz.modeOptions || DEFAULT_MODES).map(o => /*#__PURE__*/React.createElement("option", {
      key: o.value,
      value: o.value
    }, o.label)))), wiz.strict ? /*#__PURE__*/React.createElement(Field, {
      label: "\u6570\u636E\u6821\u9A8C",
      hint: "\u4E25\u683C\uFF1A\u4E0D\u8BA4\u8BC6\u7684\u5DE5\u79CD/\u7F3A\u5468\u671F\u7B49\u4F1A\u76F4\u63A5\u62A5\u9519\u5E76\u505C\u6B62\uFF1B\u5BBD\u677E\u4F1A\u5C3D\u91CF\u5199\u5165\u5E76\u63D0\u793A\u8865\u6B63\u3002"
    }, /*#__PURE__*/React.createElement(StrictSeg, {
      checked: strict,
      onChange: setStrict,
      disabled: step > 1,
      ariaLabel: "\u6570\u636E\u6821\u9A8C"
    })) : null), /*#__PURE__*/React.createElement("div", {
      className: "bd-upload",
      style: {
        marginBottom: 16
      }
    }, /*#__PURE__*/React.createElement("input", {
      type: "file",
      accept: ".xlsx",
      disabled: step > 1,
      onChange: e => setFileName(e.target.files && e.target.files[0] ? e.target.files[0].name : ""),
      "aria-label": "\u9009\u62E9 Excel \u6587\u4EF6"
    }), /*#__PURE__*/React.createElement("span", {
      className: "up-file"
    }, fileName ? fileName : /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "\u4EC5\u652F\u6301 .xlsx\uFF0C\u8868\u5934\u4E0D\u8981\u6539\uFF0C\u53EA\u8BFB\u7B2C\u4E00\u4E2A\u5DE5\u4F5C\u8868")), step === 1 ? /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      disabled: !fileName,
      onClick: () => setStep(2),
      style: {
        marginLeft: "auto"
      }
    }, "\u4E0A\u4F20\u5E76\u68C0\u67E5") : null), step >= 2 ? /*#__PURE__*/React.createElement("div", {
      style: {
        marginBottom: 16
      }
    }, /*#__PURE__*/React.createElement("h3", {
      className: "bd-sec-title",
      style: {
        fontSize: 15
      }
    }, "\u68C0\u67E5\u7ED3\u679C"), /*#__PURE__*/React.createElement("p", {
      className: "bd-sec-sub"
    }, "\u884C\u53F7\u5BF9\u5E94 Excel \u4E2D\u7684\u5B9E\u9645\u884C\u6570\uFF1B\u628A\u9519\u8BEF\u884C\u5168\u90E8\u4FEE\u5B8C\u624D\u80FD\u5199\u5165\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "bd-table-scroll"
    }, /*#__PURE__*/React.createElement(Table, {
      columns: checkCols,
      rows: rows,
      rowKey: "row_num"
    })), hasError ? /*#__PURE__*/React.createElement("div", {
      className: "bd-flash tone-danger",
      style: {
        marginTop: 12
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "bd-flash-dot"
    }), /*#__PURE__*/React.createElement("span", null, "\u4ECD\u6709\u9519\u8BEF\u884C\uFF0C\u8BF7\u4FEE\u6B63\u540E\u91CD\u65B0\u4E0A\u4F20\uFF1B\u68C0\u67E5\u9636\u6BB5\u6709\u9519\u8BEF\u65F6\u4E0D\u80FD\u5199\u5165\u7CFB\u7EDF\u3002")) : null, step === 2 ? /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer"
    }, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "md",
      onClick: () => setStep(1)
    }, "\u91CD\u65B0\u4E0A\u4F20"), /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      disabled: hasError,
      onClick: () => {
        setStep(3);
      }
    }, "\u786E\u8BA4\u5199\u5165\u7CFB\u7EDF")) : null) : null, step >= 3 ? /*#__PURE__*/React.createElement("div", {
      className: "bd-flash tone-ok",
      style: {
        marginBottom: 4
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "bd-flash-dot"
    }), /*#__PURE__*/React.createElement("span", null, summarize(rows), " \u5DF2\u5199\u5165\u7CFB\u7EDF\u5E76\u8BB0\u5F55\u64CD\u4F5C\u7559\u75D5\u3002\u5EFA\u8BAE\u518D\u5BFC\u51FA\u4E00\u6B21\u5F53\u524D\u6570\u636E\u590D\u6838\u3002")) : null, step >= 3 ? /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer"
    }, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "md",
      onClick: () => {
        setStep(1);
        setFileName("");
      }
    }, "\u518D\u5BFC\u5165\u4E00\u6279"), /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: () => {
        onDone && onDone(summarize(rows));
        onClose();
      }
    }, "\u5B8C\u6210\uFF0C\u8FD4\u56DE\u5217\u8868")) : null);
  }
  function summarize(rows) {
    const c = {
      new: 0,
      update: 0,
      skip: 0
    };
    rows.forEach(r => {
      if (c[r.status] != null) c[r.status]++;
    });
    const parts = [];
    if (c.new) parts.push("新增 " + c.new + " 条");
    if (c.update) parts.push("更新 " + c.update + " 条");
    if (c.skip) parts.push("跳过 " + c.skip + " 条");
    return parts.length ? parts.join("、") : "无变化";
  }
  function RowDetail({
    r
  }) {
    const [open, setOpen] = useState(false);
    return /*#__PURE__*/React.createElement("details", {
      className: "bd-row-detail",
      open: open,
      onToggle: e => setOpen(e.target.open)
    }, /*#__PURE__*/React.createElement("summary", {
      className: "bd-link",
      style: {
        fontSize: 12
      }
    }, "\u67E5\u770B\u6570\u636E"), /*#__PURE__*/React.createElement("pre", {
      style: {
        margin: "6px 0 0",
        fontSize: 11.5,
        background: "var(--ui-surface-muted)",
        border: "1px solid var(--ui-border)",
        borderRadius: 6,
        padding: 8,
        lineHeight: 1.6,
        whiteSpace: "pre-wrap"
      }
    }, JSON.stringify(r.data || {}, null, 2)));
  }
  const DEFAULT_MODES = [{
    value: "overwrite",
    label: "更新已有，新增缺少"
  }, {
    value: "append",
    label: "只导入新编号"
  }, {
    value: "replace",
    label: "清空本类数据后重导"
  }];
  const DEFAULT_SAMPLE = [{
    row_num: 2,
    status: "update",
    message: "已存在，更新 2 个字段",
    data: {
      图号: "T-1008",
      名称: "回转壳体 A"
    }
  }, {
    row_num: 3,
    status: "new",
    message: "新增记录",
    data: {
      图号: "T-1020",
      名称: "端盖 E"
    }
  }, {
    row_num: 4,
    status: "unchanged",
    message: "与系统一致，跳过",
    data: {
      图号: "T-1009",
      名称: "回转壳体 B"
    }
  }, {
    row_num: 5,
    status: "skip",
    message: "模式为“只导入新编号”，已存在故跳过",
    data: {
      图号: "T-1011"
    }
  }];

  /* ============================================================ */
  /* 零件 / 图号 共享数据源 — 排产基础资料（工艺模板）与批次管理共用同一份  */
  /* 在工艺模板里新增/编辑/删除零件，批次的图号下拉会实时同步。            */
  /* ============================================================ */
  const PARTS_SEED = [{
    part_no: "T-1008",
    part_name: "回转壳体 A",
    remark: "主力件",
    route_raw: "5数铣 10钳 20数车 30外协电镀 35外协发黑 40总检 45表处理",
    parsed: true,
    ops: [{
      seq: 5,
      op_type: "数铣",
      source: "internal",
      setup: 0.5,
      unit: 1.2
    }, {
      seq: 10,
      op_type: "钳工",
      source: "internal",
      setup: 0.3,
      unit: 0.8
    }, {
      seq: 20,
      op_type: "数车",
      source: "internal",
      setup: 0.4,
      unit: 1.0
    }, {
      seq: 30,
      op_type: "电镀",
      source: "external",
      supplier: "华表面处理",
      group: "G1",
      ext_days: 3
    }, {
      seq: 35,
      op_type: "发黑",
      source: "external",
      supplier: "华表面处理",
      group: "G1",
      ext_days: 2
    }, {
      seq: 40,
      op_type: "总检",
      source: "internal",
      setup: 0.2,
      unit: 0.3
    }, {
      seq: 45,
      op_type: "表处理",
      source: "internal",
      setup: 0.3,
      unit: 0.6
    }],
    groups: [{
      id: "G1",
      start: 30,
      end: 35,
      mode: "separate",
      total: null,
      strict: false,
      deletable: true
    }]
  }, {
    part_no: "T-1009",
    part_name: "回转壳体 B",
    remark: "",
    route_raw: "5数铣 10钳 20数车 30精磨 40总检",
    parsed: true,
    ops: [{
      seq: 5,
      op_type: "数铣",
      source: "internal",
      setup: 0.5,
      unit: 1.1
    }, {
      seq: 10,
      op_type: "钳工",
      source: "internal",
      setup: 0.3,
      unit: 0.7
    }, {
      seq: 20,
      op_type: "数车",
      source: "internal",
      setup: 0.4,
      unit: 1.0
    }, {
      seq: 30,
      op_type: "精磨",
      source: "internal",
      setup: 0.6,
      unit: 1.3
    }, {
      seq: 40,
      op_type: "总检",
      source: "internal",
      setup: 0.2,
      unit: 0.3
    }],
    groups: []
  }, {
    part_no: "T-1011",
    part_name: "端盖 C",
    remark: "待复核外协周期",
    route_raw: "5数车 10钻孔 20外协热处理 25外协喷涂 30总检",
    parsed: false,
    ops: [{
      seq: 5,
      op_type: "数车",
      source: "internal",
      setup: 0.3,
      unit: 0.5
    }, {
      seq: 10,
      op_type: "钻孔",
      source: "internal",
      setup: 0.2,
      unit: 0.4
    }, {
      seq: 20,
      op_type: "热处理",
      source: "external",
      supplier: "金鼎热处理",
      group: "G1",
      ext_days: 4
    }, {
      seq: 25,
      op_type: "喷涂",
      source: "external",
      supplier: "—",
      group: "G1",
      ext_days: null
    }, {
      seq: 30,
      op_type: "总检",
      source: "internal",
      setup: 0.2,
      unit: 0.3
    }],
    groups: [{
      id: "G1",
      start: 20,
      end: 25,
      mode: "merged",
      total: 6,
      strict: false,
      deletable: true
    }]
  }, {
    part_no: "T-1014",
    part_name: "法兰 D",
    remark: "草稿",
    route_raw: "",
    parsed: false,
    ops: [],
    groups: []
  }];
  let _parts = PARTS_SEED;
  const _partsSubs = new Set();
  const setParts = updater => {
    _parts = typeof updater === "function" ? updater(_parts) : updater;
    _partsSubs.forEach(fn => fn());
  };
  // React hook: every screen that calls this re-renders when the shared list changes.
  const usePartsStore = () => {
    const [, force] = React.useState(0);
    React.useEffect(() => {
      const fn = () => force(n => n + 1);
      _partsSubs.add(fn);
      return () => _partsSubs.delete(fn);
    }, []);
    return [_parts, setParts];
  };
  const partName = pn => (_parts.find(p => p.part_no === pn) || {}).part_name || "";
  const findPart = pn => _parts.find(p => p.part_no === pn) || null;
  window.BD = {
    PrimaryTabs,
    SubTabs,
    Field,
    Toggle,
    Seg,
    StrictSeg,
    DateInput,
    Flash,
    useFlash,
    Empty,
    ConfirmButton,
    Pager,
    SummaryGrid,
    InfoStrip,
    ActionCards,
    ExcelWizard,
    STATUS_META,
    DEFAULT_MODES,
    Chips,
    CheckGroup,
    OP_TYPES_SEED,
    opTypeNames,
    usePartsStore,
    partName,
    findPart,
    PARTS_SEED
  };
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/BaseShared.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/BaseSuppliers.jsx
try { (() => {
// APS Workbench · 基础资料 › 外协 › 供应商配置模块（可复用）
// 列表 + 内联新增 + 主从详情编辑 + Excel 批量维护 + 引用保护删除
// 外协链口径 = 周期（天）：供应商绑外协工种，给默认周期。
(function () {
  const {
    useState
  } = React;
  const DS = () => window.APSDesignSystem_edbc5d;
  const B = () => window.BD;
  const SEED = [{
    supplier_id: "S001",
    name: "华表面处理厂",
    op_type: "电镀",
    default_days: 3,
    status: "active",
    remark: "主力外协",
    refs: ["工序"]
  }, {
    supplier_id: "S002",
    name: "金鼎热处理",
    op_type: "热处理",
    default_days: 4,
    status: "active",
    remark: "",
    refs: ["工序"]
  }, {
    supplier_id: "S003",
    name: "恒发发黑",
    op_type: "发黑",
    default_days: 2,
    status: "active",
    remark: "",
    refs: []
  }, {
    supplier_id: "S004",
    name: "蓝盾喷涂",
    op_type: "喷涂",
    default_days: 5,
    status: "disabled",
    remark: "停用整顿",
    refs: []
  }];
  const STATUS_OPTS = [{
    value: "active",
    label: "启用"
  }, {
    value: "disabled",
    label: "停用"
  }];
  const statusZh = s => s === "disabled" ? "停用" : "启用";
  function SuppliersModule({
    flashFn
  }) {
    const [rows, setRows] = useState(SEED);
    const [view, setView] = useState("list");
    const [openId, setOpenId] = useState(null);
    const [wiz, setWiz] = useState(null);
    const open = id => {
      setOpenId(id);
      setView("detail");
      window.scrollTo({
        top: 0
      });
    };
    const back = () => {
      setView("list");
      setOpenId(null);
      window.scrollTo({
        top: 0
      });
    };
    const patch = (id, p) => setRows(arr => arr.map(r => r.supplier_id === id ? {
      ...r,
      ...p
    } : r));
    if (wiz) {
      const W = B().ExcelWizard;
      return /*#__PURE__*/React.createElement(W, {
        wiz: wiz,
        onClose: () => setWiz(null),
        onDone: s => flashFn("ok", "Excel 导入完成：" + s + "。")
      });
    }
    if (view === "detail") {
      const row = rows.find(r => r.supplier_id === openId);
      return /*#__PURE__*/React.createElement(SupplierDetail, {
        row: row,
        onBack: back,
        onSave: patch,
        flashFn: flashFn
      });
    }
    return /*#__PURE__*/React.createElement(SuppliersList, {
      rows: rows,
      setRows: setRows,
      onOpen: open,
      onWiz: setWiz,
      flashFn: flashFn
    });
  }

  /* ============================================================ LIST */
  function SuppliersList({
    rows,
    setRows,
    onOpen,
    onWiz,
    flashFn
  }) {
    const {
      Panel,
      Button,
      Badge,
      Table
    } = DS();
    const {
      Field,
      ActionCards,
      ConfirmButton,
      Pager,
      Empty,
      opTypeNames
    } = B();
    const extTypes = opTypeNames("external");
    const [q, setQ] = useState("");
    const [page, setPage] = useState(1);
    const perPage = 8;
    const [form, setForm] = useState({
      supplier_id: "",
      name: "",
      op_type: "",
      default_days: "1",
      status: "active",
      remark: ""
    });
    const [errors, setErrors] = useState({});
    const setField = patch => {
      setForm(f => ({
        ...f,
        ...patch
      }));
      setErrors(e => {
        const n = {
          ...e
        };
        Object.keys(patch).forEach(k => delete n[k]);
        return n;
      });
    };
    const cards = [{
      title: "批量维护供应商",
      desc: "下载模板、上传检查、确认写入或导出供应商配置；手工新增继续用下方表单。",
      maintainLabel: "批量维护供应商",
      exportLabel: "导出当前供应商",
      cycle: true,
      wizard: {
        kind: "suppliers",
        title: "批量维护供应商配置",
        desc: "维护供应商编号、名称、对应工种、默认周期（天）与状态；默认周期必须大于 0。",
        sampleRows: [{
          row_num: 2,
          status: "update",
          message: "更新默认周期 3→4 天",
          data: {
            供应商编号: "S001",
            默认周期: 4
          }
        }, {
          row_num: 3,
          status: "new",
          message: "新增供应商",
          data: {
            供应商编号: "S005",
            名称: "鑫达阳极",
            对应工种: "电镀"
          }
        }, {
          row_num: 4,
          status: "error",
          message: "默认周期必须大于 0",
          data: {
            供应商编号: "S006",
            默认周期: 0
          }
        }]
      }
    }];
    const list = rows.filter(r => !q || (r.supplier_id + r.name + (r.op_type || "") + (r.remark || "")).toLowerCase().includes(q.toLowerCase()));
    const totalPages = Math.ceil(list.length / perPage);
    const pageRows = list.slice((page - 1) * perPage, page * perPage);
    const tryDelete = r => {
      if (r.refs && r.refs.length) {
        flashFn("danger", "无法删除供应商 " + r.name + "：仍被" + r.refs.join("、") + "引用，请先解除引用。");
        return;
      }
      setRows(arr => arr.filter(x => x.supplier_id !== r.supplier_id));
      flashFn("ok", "已删除供应商 " + r.name + "。");
    };
    const cols = [{
      key: "supplier_id",
      title: "供应商编号",
      width: 130,
      render: r => /*#__PURE__*/React.createElement("a", {
        className: "bd-link",
        onClick: () => onOpen(r.supplier_id)
      }, r.supplier_id)
    }, {
      key: "name",
      title: "名称",
      width: 170
    }, {
      key: "op_type",
      title: "对应工种",
      width: 120,
      render: r => r.op_type ? /*#__PURE__*/React.createElement(Badge, {
        tone: "warning"
      }, r.op_type) : /*#__PURE__*/React.createElement("span", {
        className: "muted"
      }, "\u4E0D\u7ED1\u5B9A")
    }, {
      key: "default_days",
      title: "默认周期",
      width: 110,
      align: "right",
      render: r => /*#__PURE__*/React.createElement("span", {
        style: {
          fontVariantNumeric: "tabular-nums"
        }
      }, r.default_days, " \u5929")
    }, {
      key: "status",
      title: "状态",
      width: 100,
      render: r => /*#__PURE__*/React.createElement(Badge, {
        tone: r.status === "active" ? "ok" : "secondary",
        dot: true
      }, statusZh(r.status))
    }, {
      key: "remark",
      title: "备注",
      render: r => r.remark || /*#__PURE__*/React.createElement("span", {
        className: "muted"
      }, "-")
    }, {
      key: "act",
      title: "操作",
      width: 170,
      render: r => /*#__PURE__*/React.createElement("div", {
        className: "bd-cell-actions"
      }, /*#__PURE__*/React.createElement(Button, {
        variant: "secondary",
        size: "sm",
        onClick: () => onOpen(r.supplier_id)
      }, "\u67E5\u770B/\u7F16\u8F91"), /*#__PURE__*/React.createElement(ConfirmButton, {
        label: "\u5220\u9664",
        title: "删除供应商 " + r.name + "？",
        body: r.refs && r.refs.length ? /*#__PURE__*/React.createElement(React.Fragment, null, "\u8BE5\u4F9B\u5E94\u5546\u5DF2\u88AB ", /*#__PURE__*/React.createElement("strong", null, r.refs.join("、")), " \u5F15\u7528\uFF0C\u5220\u9664\u4F1A\u88AB\u62D2\u7EDD\u3002\u4ECD\u8981\u5C1D\u8BD5\u5417\uFF1F") : /*#__PURE__*/React.createElement(React.Fragment, null, "\u786E\u8BA4\u5220\u9664\u4F9B\u5E94\u5546 ", /*#__PURE__*/React.createElement("strong", null, r.name), "\uFF08", r.supplier_id, "\uFF09\u5417\uFF1F"),
        onConfirm: () => tryDelete(r)
      }))
    }];
    const submit = () => {
      const errs = {};
      if (!form.supplier_id) errs.supplier_id = "请填写供应商编号。";else if (rows.some(r => r.supplier_id === form.supplier_id)) errs.supplier_id = "供应商编号 " + form.supplier_id + " 已存在。";
      if (!form.name) errs.name = "请填写名称。";
      if (Number(form.default_days) <= 0) errs.default_days = "默认周期必须大于 0。";
      if (Object.keys(errs).length) {
        setErrors(errs);
        return;
      }
      setErrors({});
      setRows(arr => [{
        ...form,
        default_days: Number(form.default_days),
        refs: []
      }, ...arr]);
      flashFn("ok", "已添加供应商 " + form.name + "。");
      setForm({
        supplier_id: "",
        name: "",
        op_type: "",
        default_days: "1",
        status: "active",
        remark: ""
      });
    };
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(ActionCards, {
      title: "\u6279\u91CF\u7EF4\u62A4",
      subtitle: "\u9002\u5408 Excel \u4E0B\u53D1\u6216\u6574\u6279\u590D\u6838\uFF1B\u624B\u5DE5\u65B0\u589E\u7EE7\u7EED\u4F7F\u7528\u4E0B\u65B9\u8868\u5355\u3002",
      cards: cards,
      onOpen: onWiz
    }), /*#__PURE__*/React.createElement(Panel, {
      title: "\u65B0\u589E\u4F9B\u5E94\u5546"
    }, /*#__PURE__*/React.createElement("div", {
      className: "field-help bd-chain-note tone-external"
    }, /*#__PURE__*/React.createElement("span", {
      className: "cn-bar"
    }), /*#__PURE__*/React.createElement("span", null, "\u9ED8\u8BA4\u5468\u671F\u5FC5\u987B\u586B\u5927\u4E8E 0 \u7684\u5929\u6570\u3002\u82E5\u4E00\u4E2A\u5916\u534F\u5DE5\u79CD\u6709\u591A\u4E2A\u542F\u7528\u4F9B\u5E94\u5546\uFF0C\u8BF7\u505C\u7528\u591A\u4F59\u7684\uFF0C\u6216\u786E\u8BA4\u7F16\u53F7\u6392\u5E8F\u540E\u7CFB\u7EDF\u4F1A\u9009\u5230\u4F60\u60F3\u8981\u7684\u90A3\u4E00\u4E2A\u3002")), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u4F9B\u5E94\u5546\u7F16\u53F7",
      required: true,
      error: errors.supplier_id
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1AS001",
      value: form.supplier_id,
      onChange: e => setField({
        supplier_id: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u540D\u79F0",
      required: true,
      error: errors.name
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u5982\uFF1A\u5916\u534F-\u8868\u5904\u7406\u5382",
      value: form.name,
      onChange: e => setField({
        name: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5BF9\u5E94\u5DE5\u79CD",
      hint: "\u4ECE\u5916\u534F\u5DE5\u79CD\u91CC\u9009\uFF1B\u53EF\u4E0D\u7ED1\u5B9A\u3002"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: form.op_type,
      onChange: e => setForm({
        ...form,
        op_type: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\uFF08\u4E0D\u7ED1\u5B9A\uFF09"), extTypes.map(n => /*#__PURE__*/React.createElement("option", {
      key: n,
      value: n
    }, n)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u9ED8\u8BA4\u5468\u671F\uFF08\u5929\uFF09",
      required: true,
      error: errors.default_days
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input num",
      style: {
        maxWidth: 120
      },
      value: form.default_days,
      onChange: e => setField({
        default_days: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u72B6\u6001",
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: form.status,
      onChange: e => setForm({
        ...form,
        status: e.target.value
      })
    }, STATUS_OPTS.map(o => /*#__PURE__*/React.createElement("option", {
      key: o.value,
      value: o.value
    }, o.label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u5907\u6CE8",
      wide: true
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u53EF\u9009",
      value: form.remark,
      onChange: e => setForm({
        ...form,
        remark: e.target.value
      })
    }))), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")
    }, Object.keys(errors).length ? /*#__PURE__*/React.createElement("span", {
      className: "bd-form-error"
    }, "\u8BF7\u4FEE\u6B63\u6807\u7EA2\u7684\u5FC5\u586B\u9879") : null, /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: submit
    }, "\u6DFB\u52A0\u4F9B\u5E94\u5546"))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u4F9B\u5E94\u5546\u5217\u8868",
      description: "\u5916\u534F\u8BA1\u91CF\u53E3\u5F84\u662F\u300C\u5468\u671F\uFF08\u5929\uFF09\u300D\uFF1A\u4F9B\u5E94\u5546\u7ED9\u9ED8\u8BA4\u5468\u671F\uFF0C\u96F6\u4EF6\u7684\u8FDE\u7EED\u5916\u534F\u5DE5\u5E8F\u7EC4\u5728\u300C\u5DE5\u827A\u300D\u8BE6\u60C5\u91CC\u6309\u6B64\u8BBE/\u8C03\u5468\u671F\u3002"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-search"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u641C\u7D22"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u8F93\u5165\u4F9B\u5E94\u5546\u7F16\u53F7\u3001\u540D\u79F0\u3001\u5DE5\u79CD\u2026",
      value: q,
      onChange: e => {
        setQ(e.target.value);
        setPage(1);
      }
    }))), list.length ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Pager, {
      page: page,
      totalPages: totalPages,
      total: list.length,
      onPrev: () => setPage(p => p - 1),
      onNext: () => setPage(p => p + 1)
    }), /*#__PURE__*/React.createElement("div", {
      className: "bd-table-scroll"
    }, /*#__PURE__*/React.createElement(Table, {
      columns: cols,
      rows: pageRows,
      rowKey: "supplier_id"
    }))) : /*#__PURE__*/React.createElement(Empty, {
      title: "\u6682\u65E0\u4F9B\u5E94\u5546\u6570\u636E",
      desc: "\u53EF\u5728\u4E0A\u65B9\u624B\u52A8\u65B0\u589E\uFF0C\u6216\u7528 Excel \u6279\u91CF\u7EF4\u62A4\u5BFC\u5165\u3002"
    })));
  }

  /* ============================================================ DETAIL */
  function SupplierDetail({
    row,
    onBack,
    onSave,
    flashFn
  }) {
    const {
      Panel,
      Button,
      Badge
    } = DS();
    const {
      Field,
      opTypeNames
    } = B();
    const extTypes = opTypeNames("external");
    const [v, setV] = useState({
      name: row.name,
      op_type: row.op_type || "",
      default_days: String(row.default_days),
      status: row.status,
      remark: row.remark || ""
    });
    const [errors, setErrors] = useState({});
    const setField = patch => {
      setV(s => ({
        ...s,
        ...patch
      }));
      setErrors(e => {
        const n = {
          ...e
        };
        Object.keys(patch).forEach(k => delete n[k]);
        return n;
      });
    };
    const save = () => {
      const errs = {};
      if (!v.name) errs.name = "请填写名称。";
      if (Number(v.default_days) <= 0) errs.default_days = "默认周期必须大于 0。";
      if (Object.keys(errs).length) {
        setErrors(errs);
        return;
      }
      setErrors({});
      onSave(row.supplier_id, {
        ...v,
        default_days: Number(v.default_days)
      });
      flashFn("ok", "已保存供应商 " + v.name + "。");
      onBack();
    };
    return /*#__PURE__*/React.createElement("div", {
      className: "bd-card-gap"
    }, /*#__PURE__*/React.createElement(Panel, {
      title: "\u4F9B\u5E94\u5546\u914D\u7F6E \xB7 \u8BE6\u60C5",
      description: "\u7EF4\u62A4\u4F9B\u5E94\u5546\u540D\u79F0\u3001\u5BF9\u5E94\u5DE5\u79CD\u3001\u9ED8\u8BA4\u5468\u671F\u4E0E\u72B6\u6001\u3002\u4F9B\u5E94\u5546\u7F16\u53F7\u521B\u5EFA\u540E\u4E0D\u53EF\u66F4\u6539\u3002",
      headerRight: /*#__PURE__*/React.createElement(Button, {
        variant: "ghost",
        size: "sm",
        onClick: onBack
      }, "\u2190 \u8FD4\u56DE\u5217\u8868")
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-meta-row"
    }, /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u4F9B\u5E94\u5546\u7F16\u53F7\uFF1A"), /*#__PURE__*/React.createElement("strong", null, row.supplier_id)), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u72B6\u6001\uFF1A"), /*#__PURE__*/React.createElement(Badge, {
      tone: v.status === "active" ? "ok" : "secondary",
      dot: true
    }, statusZh(v.status))), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("span", {
      className: "bd-meta-label"
    }, "\u5F15\u7528\uFF1A"), row.refs && row.refs.length ? /*#__PURE__*/React.createElement(Badge, {
      tone: "secondary"
    }, row.refs.join(" / ")) : /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "\u65E0")))), /*#__PURE__*/React.createElement(Panel, {
      title: "\u7F16\u8F91\u4F9B\u5E94\u5546"
    }, /*#__PURE__*/React.createElement("div", {
      className: "bd-form-grid"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u4F9B\u5E94\u5546\u7F16\u53F7"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      value: row.supplier_id,
      disabled: true
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u540D\u79F0",
      required: true,
      error: errors.name
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      value: v.name,
      onChange: e => setField({
        name: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u5BF9\u5E94\u5DE5\u79CD",
      hint: "\u4ECE\u5916\u534F\u5DE5\u79CD\u91CC\u9009\uFF1B\u53EF\u4E0D\u7ED1\u5B9A\u3002"
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: v.op_type,
      onChange: e => setV({
        ...v,
        op_type: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\uFF08\u4E0D\u7ED1\u5B9A\uFF09"), extTypes.map(n => /*#__PURE__*/React.createElement("option", {
      key: n,
      value: n
    }, n)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u9ED8\u8BA4\u5468\u671F\uFF08\u5929\uFF09",
      required: true,
      error: errors.default_days
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input num",
      style: {
        maxWidth: 120
      },
      value: v.default_days,
      onChange: e => setField({
        default_days: e.target.value
      })
    })), /*#__PURE__*/React.createElement(Field, {
      label: "\u72B6\u6001",
      required: true
    }, /*#__PURE__*/React.createElement("select", {
      className: "bd-select",
      value: v.status,
      onChange: e => setV({
        ...v,
        status: e.target.value
      })
    }, STATUS_OPTS.map(o => /*#__PURE__*/React.createElement("option", {
      key: o.value,
      value: o.value
    }, o.label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u5907\u6CE8",
      wide: true
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-input",
      placeholder: "\u53EF\u9009",
      value: v.remark,
      onChange: e => setV({
        ...v,
        remark: e.target.value
      })
    }))), /*#__PURE__*/React.createElement("div", {
      className: "bd-form-footer" + (Object.keys(errors).length ? " has-error" : "")
    }, Object.keys(errors).length ? /*#__PURE__*/React.createElement("span", {
      className: "bd-form-error"
    }, "\u8BF7\u4FEE\u6B63\u6807\u7EA2\u7684\u5FC5\u586B\u9879") : null, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "md",
      onClick: onBack
    }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "md",
      onClick: save
    }, "\u4FDD\u5B58"))));
  }
  window.SuppliersModule = SuppliersModule;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/BaseSuppliers.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/BasicDataScreen.jsx
try { (() => {
// APS Workbench · 基础资料列表 archetype (equipment / process / personnel / material / system)
// One list pattern, parameterised by module — search + status badges + right-aligned tabular numbers.
const BD_MODULES = {
  batches: {
    title: "批次管理",
    desc: "批次列表：图号 + 数量（右对齐 tabular）+ 交期 + 状态徽标，列表/详情同款 archetype。",
    add: "新增批次",
    count: "个",
    cols: [{
      key: "code",
      title: "批次号",
      nowrap: true,
      strong: true
    }, {
      key: "part",
      title: "图号",
      nowrap: true
    }, {
      key: "qty",
      title: "数量",
      align: "right"
    }, {
      key: "due",
      title: "交期",
      nowrap: true
    }, {
      key: "prog",
      title: "工序进度",
      nowrap: true
    }, {
      key: "state",
      title: "状态",
      kind: "badge"
    }, {
      key: "act",
      title: "操作",
      kind: "act"
    }],
    rows: [{
      id: 1,
      code: "B202605-018",
      part: "T-1008",
      qty: 12,
      due: "05-24 12:00",
      prog: "30 / 60",
      state: "超期",
      tone: "danger"
    }, {
      id: 2,
      code: "B202605-021",
      part: "T-1009",
      qty: 8,
      due: "05-25 08:00",
      prog: "20 / 50",
      state: "接近满载",
      tone: "warning"
    }, {
      id: 3,
      code: "B202605-019",
      part: "T-1006",
      qty: 6,
      due: "05-25 14:00",
      prog: "40 / 50",
      state: "正常",
      tone: "success"
    }, {
      id: 4,
      code: "B202605-017",
      part: "T-1004",
      qty: 10,
      due: "05-26 10:00",
      prog: "10 / 40",
      state: "外协在途",
      tone: "notice"
    }, {
      id: 5,
      code: "B202605-024",
      part: "T-1011",
      qty: 4,
      due: "05-26 16:00",
      prog: "待排",
      state: "待排",
      tone: "secondary"
    }]
  },
  field: {
    title: "现场记录",
    desc: "排产计划对应工序的实际开工 / 完工时间与工时回填（不接 MES）：计划列只读，实际三列就地填，供工时校准与执行复盘。",
    add: "导入实际工时",
    count: "道",
    cols: [{
      key: "batch",
      title: "批次",
      nowrap: true,
      strong: true
    }, {
      key: "op",
      title: "工序"
    }, {
      key: "res",
      title: "资源",
      nowrap: true
    }, {
      key: "actStart",
      title: "实际开工",
      nowrap: true
    }, {
      key: "actEnd",
      title: "实际完工",
      nowrap: true
    }, {
      key: "hours",
      title: "工时",
      align: "right"
    }, {
      key: "state",
      title: "状态",
      kind: "badge"
    }],
    rows: [{
      id: 1,
      batch: "B202605-019",
      op: "50 检验",
      res: "M-12 / 王五",
      actStart: "06-11 08:05",
      actEnd: "06-11 09:18",
      hours: "1.2",
      state: "已回填",
      tone: "success"
    }, {
      id: 2,
      batch: "B202605-018",
      op: "30 精加工",
      res: "M-03 / 张三",
      actStart: "06-11 08:10",
      actEnd: "—",
      hours: "—",
      state: "进行中",
      tone: "notice"
    }, {
      id: 3,
      batch: "B202605-024",
      op: "30 精加工",
      res: "M-03 / 张三",
      actStart: "—",
      actEnd: "—",
      hours: "—",
      state: "待回填",
      tone: "secondary"
    }, {
      id: 4,
      batch: "B202605-017",
      op: "50 检验",
      res: "M-12 / 王五",
      actStart: "—",
      actEnd: "—",
      hours: "—",
      state: "待回填",
      tone: "secondary"
    }]
  },
  equipment: {
    title: "设备管理",
    desc: "基础资料的列表 archetype：搜索 + 状态徽标 + 数字列右对齐（tabular），与全站表格规范一致。",
    add: "新增设备",
    count: "台",
    cols: [{
      key: "code",
      title: "设备编号",
      nowrap: true,
      strong: true
    }, {
      key: "name",
      title: "设备名称"
    }, {
      key: "group",
      title: "工序组",
      nowrap: true
    }, {
      key: "tasks",
      title: "本周任务",
      align: "right"
    }, {
      key: "util",
      title: "利用率",
      align: "right",
      kind: "util"
    }, {
      key: "state",
      title: "状态",
      kind: "badge"
    }, {
      key: "act",
      title: "操作",
      kind: "act"
    }],
    rows: [{
      id: 1,
      code: "M-03",
      name: "五轴加工中心",
      group: "精加工",
      tasks: 12,
      util: 96,
      state: "接近满载",
      tone: "warning"
    }, {
      id: 2,
      code: "M-05",
      name: "卧式加工中心",
      group: "预加工",
      tasks: 9,
      util: 89,
      state: "接近满载",
      tone: "warning"
    }, {
      id: 3,
      code: "M-07",
      name: "立式加工中心",
      group: "组装",
      tasks: 7,
      util: 72,
      state: "正常",
      tone: "success"
    }, {
      id: 4,
      code: "M-12",
      name: "三坐标检测",
      group: "检验",
      tasks: 5,
      util: 58,
      state: "正常",
      tone: "success"
    }, {
      id: 5,
      code: "M-18",
      name: "数控车床",
      group: "车加工",
      tasks: 3,
      util: 34,
      state: "有余量",
      tone: "secondary"
    }, {
      id: 6,
      code: "M-21",
      name: "线切割",
      group: "特种加工",
      tasks: 0,
      util: 0,
      state: "停机维护",
      tone: "danger"
    }]
  },
  process: {
    title: "工艺管理",
    desc: "工艺路线列表：图号 + 工序数 + 标准工时（右对齐 tabular）+ 外协标识，列表/详情同款 archetype。",
    add: "新增工艺",
    count: "项",
    cols: [{
      key: "code",
      title: "图号",
      nowrap: true,
      strong: true
    }, {
      key: "name",
      title: "零件名称"
    }, {
      key: "ops",
      title: "工序数",
      align: "right"
    }, {
      key: "hours",
      title: "标准工时",
      align: "right"
    }, {
      key: "out",
      title: "外协",
      kind: "badge"
    }, {
      key: "state",
      title: "状态",
      kind: "badge2"
    }, {
      key: "act",
      title: "操作",
      kind: "act"
    }],
    rows: [{
      id: 1,
      code: "T-1008",
      name: "回转壳体 A",
      ops: 6,
      hours: "42.5h",
      out: "含外协",
      outTone: "notice",
      state: "已确认",
      tone: "success"
    }, {
      id: 2,
      code: "T-1009",
      name: "回转壳体 B",
      ops: 5,
      hours: "38.0h",
      out: "无",
      outTone: "secondary",
      state: "已确认",
      tone: "success"
    }, {
      id: 3,
      code: "T-1011",
      name: "端盖 C",
      ops: 4,
      hours: "21.0h",
      out: "含外协",
      outTone: "notice",
      state: "待复核",
      tone: "warning"
    }, {
      id: 4,
      code: "T-1014",
      name: "法兰 D",
      ops: 3,
      hours: "12.5h",
      out: "无",
      outTone: "secondary",
      state: "草稿",
      tone: "secondary"
    }]
  },
  personnel: {
    title: "人员管理",
    desc: "人员与班组列表：本周排班工时右对齐，技能与在岗状态以徽标呈现。",
    add: "新增人员",
    count: "人",
    cols: [{
      key: "code",
      title: "工号",
      nowrap: true,
      strong: true
    }, {
      key: "name",
      title: "姓名"
    }, {
      key: "team",
      title: "班组",
      nowrap: true
    }, {
      key: "hours",
      title: "本周排班",
      align: "right"
    }, {
      key: "skill",
      title: "主技能",
      nowrap: true
    }, {
      key: "state",
      title: "状态",
      kind: "badge"
    }, {
      key: "act",
      title: "操作",
      kind: "act"
    }],
    rows: [{
      id: 1,
      code: "P-021",
      name: "张三",
      team: "一班",
      hours: "42h",
      skill: "精加工",
      state: "接近满载",
      tone: "warning"
    }, {
      id: 2,
      code: "P-024",
      name: "李四",
      team: "一班",
      hours: "31h",
      skill: "组装",
      state: "有余量",
      tone: "success"
    }, {
      id: 3,
      code: "P-030",
      name: "王五",
      team: "二班",
      hours: "38h",
      skill: "检验",
      state: "正常",
      tone: "success"
    }, {
      id: 4,
      code: "P-033",
      name: "赵六",
      team: "二班",
      hours: "0h",
      skill: "车加工",
      state: "请假",
      tone: "danger"
    }]
  },
  material: {
    title: "物料管理",
    desc: "物料齐套列表：齐套率右对齐着色，未齐套的批次结果不可信，需先补料。",
    add: "登记物料",
    count: "项",
    cols: [{
      key: "code",
      title: "物料号",
      nowrap: true,
      strong: true
    }, {
      key: "name",
      title: "名称"
    }, {
      key: "batch",
      title: "关联批次",
      nowrap: true
    }, {
      key: "rate",
      title: "齐套率",
      align: "right",
      kind: "util"
    }, {
      key: "state",
      title: "状态",
      kind: "badge"
    }, {
      key: "act",
      title: "操作",
      kind: "act"
    }],
    rows: [{
      id: 1,
      code: "WL-2201",
      name: "45# 钢棒料",
      batch: "B202605-018",
      rate: 100,
      state: "已齐套",
      tone: "success"
    }, {
      id: 2,
      code: "WL-2208",
      name: "铸铝件",
      batch: "B202605-021",
      rate: 80,
      state: "待补料",
      tone: "warning"
    }, {
      id: 3,
      code: "WL-2215",
      name: "密封圈",
      batch: "B202605-017",
      rate: 60,
      state: "缺料",
      tone: "danger"
    }]
  },
  system: {
    title: "系统管理",
    desc: "系统操作记录：备份 / 历史 / 日志同款列表，时间与状态固定列位，便于追溯。",
    add: "立即备份",
    count: "条",
    cols: [{
      key: "time",
      title: "时间",
      nowrap: true,
      strong: true
    }, {
      key: "type",
      title: "类型",
      nowrap: true
    }, {
      key: "detail",
      title: "说明"
    }, {
      key: "state",
      title: "状态",
      kind: "badge"
    }, {
      key: "act",
      title: "操作",
      kind: "act"
    }],
    rows: [{
      id: 1,
      time: "05-23 18:40",
      type: "排产生成",
      detail: "生成 v12，覆盖 86 个批次",
      state: "成功",
      tone: "success"
    }, {
      id: 2,
      time: "05-23 12:00",
      type: "数据备份",
      detail: "自动备份 aps_20260523.db",
      state: "成功",
      tone: "success"
    }, {
      id: 3,
      time: "05-22 22:10",
      type: "Excel 导入",
      detail: "导入批次 24 条，跳过 2 条",
      state: "有跳过",
      tone: "warning"
    }]
  }
};
function BasicDataScreen({
  module = "equipment"
}) {
  const {
    Panel,
    Badge,
    Button,
    Table
  } = window.APSDesignSystem_edbc5d;
  const [q, setQ] = React.useState("");
  const m = BD_MODULES[module] || BD_MODULES.equipment;
  const D = window.APSDetail;
  const codeKey = {
    batches: "code",
    field: "batch",
    equipment: "code",
    process: "code",
    personnel: "code",
    material: "code"
  }[module];
  const openRow = r => {
    const code = codeKey ? r[codeKey] : null;
    if (code && D && D.has(code)) D.open(code);else if (D) D.toast((code || "该记录") + " · 明细在正式系统中按编号联动展示（示例界面）");
  };
  const cols = m.cols.map(c => ({
    key: c.key,
    title: c.title,
    align: c.align,
    nowrap: c.nowrap,
    render: r => {
      if (c.strong) {
        if (D && D.has(r[c.key])) return /*#__PURE__*/React.createElement("a", {
          href: "#",
          onClick: e => {
            e.preventDefault();
            D.open(r[c.key]);
          },
          style: {
            color: "var(--ui-primary)",
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums",
            textDecoration: "none"
          }
        }, r[c.key]);
        return /*#__PURE__*/React.createElement("strong", null, r[c.key]);
      }
      if (c.kind === "util") {
        const v = r[c.key];
        const col = v >= 90 ? "var(--ui-danger)" : v >= 75 ? "var(--ui-warning)" : v < 75 && v > 0 ? "var(--ui-text)" : "var(--ui-danger)";
        return /*#__PURE__*/React.createElement("span", {
          style: {
            color: v === 0 ? "var(--ui-danger)" : col,
            fontVariantNumeric: "tabular-nums"
          }
        }, v, "%");
      }
      if (c.kind === "badge") return /*#__PURE__*/React.createElement(Badge, {
        tone: r.tone,
        dot: true
      }, r[c.key]);
      if (c.kind === "badge2") return /*#__PURE__*/React.createElement(Badge, {
        tone: r.tone
      }, r[c.key]);
      if (c.key === "out") return /*#__PURE__*/React.createElement(Badge, {
        tone: r.outTone
      }, r.out);
      if (c.kind === "act") return /*#__PURE__*/React.createElement("a", {
        href: "#",
        onClick: e => {
          e.preventDefault();
          openRow(r);
        },
        style: {
          color: "var(--ui-primary)",
          fontSize: 13
        }
      }, "\u8BE6\u60C5");
      return r[c.key];
    }
  }));
  const rows = m.rows.filter(r => !q || Object.values(r).join("").toLowerCase().includes(q.toLowerCase()));
  return /*#__PURE__*/React.createElement(Panel, {
    title: m.title,
    description: m.desc,
    headerRight: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "sm",
      onClick: () => D && D.toast("批量导入 " + m.title + " · 示例操作")
    }, "\u5BFC\u5165 Excel"), /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "sm",
      onClick: () => D && D.toast(m.add + " · 示例操作（演示界面）")
    }, m.add))
  }, /*#__PURE__*/React.createElement("div", {
    className: "table-tools"
  }, /*#__PURE__*/React.createElement("input", {
    className: "tool-input",
    placeholder: "\u641C\u7D22\u2026",
    value: q,
    onChange: e => setQ(e.target.value)
  }), /*#__PURE__*/React.createElement("div", {
    className: "tool-right"
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: "secondary"
  }, "\u5171 ", m.rows.length, " ", m.count))), /*#__PURE__*/React.createElement(Table, {
    columns: cols,
    rows: rows,
    rowKey: "id"
  }));
}
window.BasicDataScreen = BasicDataScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/BasicDataScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/CalibScreen.jsx
try { (() => {
// APS Workbench · 统计分析 › 工时定额校准
// Compares 现场实际单件工时 (近N次中位数) vs 定额单件工时, sorted by deviation.
// NEVER auto-edits the 定额 — 采纳 is an explicit human action that writes back
// to the 工艺 工序定额 and leaves a 留痕 marker. Lives in the 统计分析 layer
// alongside 执行复盘, NOT under 工艺 (工艺 only shows a small 实际校准 marker).
function CalibScreen({
  onNav
}) {
  const {
    Panel,
    Badge,
    Button,
    Table
  } = window.APSDesignSystem_edbc5d;
  const {
    useState
  } = React;
  const SEED = [{
    id: "P-1042-20",
    part: "P-1042",
    op: "20 数铣",
    type: "数铣",
    quota: "8.5",
    actual: "11.8",
    n: 8,
    dev: 39,
    state: "up",
    suggest: "11.8"
  }, {
    id: "P-1042-30",
    part: "P-1042",
    op: "30 钳工",
    type: "钳工",
    quota: null,
    actual: "1.2",
    n: 6,
    dev: null,
    state: "seed",
    suggest: "1.2"
  }, {
    id: "T-1009-10",
    part: "T-1009",
    op: "10 数铣",
    type: "数铣",
    quota: "9.0",
    actual: "9.4",
    n: 15,
    dev: 4,
    state: "ok",
    suggest: null
  }, {
    id: "P-1042-50",
    part: "P-1042",
    op: "50 总检",
    type: "总检",
    quota: "0.0",
    actual: null,
    n: 2,
    dev: null,
    state: "few",
    suggest: null
  }, {
    id: "T-1021-20",
    part: "T-1021",
    op: "20 钻孔",
    type: "钻孔",
    quota: "1.5",
    actual: "1.1",
    n: 11,
    dev: -27,
    state: "down",
    suggest: "1.1"
  }];
  const [adopted, setAdopted] = useState({});
  const [onlyDev, setOnlyDev] = useState(false);
  const [q, setQ] = useState("");
  const devColor = d => Math.abs(d) > 20 ? "var(--ui-danger)" : Math.abs(d) > 8 ? "var(--ui-warning)" : "var(--ui-success)";
  const devText = r => r.dev == null ? "—" : (r.dev > 0 ? "+" : "") + r.dev + "%";
  const STATE_META = {
    up: {
      tone: "danger",
      label: "建议上调"
    },
    down: {
      tone: "danger",
      label: "建议下调"
    },
    seed: {
      tone: "warning",
      label: "缺定额 · 可建种子"
    },
    ok: {
      tone: "ok",
      label: "在容差内"
    },
    few: {
      tone: "secondary",
      label: "样本积累中"
    }
  };
  let rows = SEED.filter(r => !q || (r.part + r.op + r.type).toLowerCase().includes(q.toLowerCase()));
  if (onlyDev) rows = rows.filter(r => r.dev != null && Math.abs(r.dev) > 20);
  const summary = [{
    sev: "notice",
    label: "在产工序",
    value: 126,
    helper: "正在排产、有实际工时回流的工序"
  }, {
    sev: "danger",
    label: "偏差 > 20%",
    value: 14,
    helper: "实际与定额差距大，建议复核"
  }, {
    sev: "ok",
    label: "可采纳",
    value: 9,
    helper: "样本充足且偏差明确，可一键写回"
  }, {
    sev: "warning",
    label: "样本不足",
    value: 23,
    helper: "实际次数太少，先继续积累"
  }];
  const cols = [{
    key: "part",
    title: "图号 / 工序",
    width: 150,
    render: r => /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("a", {
      className: "bd-link",
      href: "#",
      onClick: e => {
        e.preventDefault();
        window.APSDetail && window.APSDetail.open(r.part);
      },
      style: {
        color: "var(--ui-primary)",
        fontWeight: 600,
        cursor: "pointer",
        textDecoration: "none"
      }
    }, r.part), " ", /*#__PURE__*/React.createElement("span", {
      className: "muted",
      style: {
        color: "var(--ui-muted)"
      }
    }, "\xB7 ", r.op))
  }, {
    key: "type",
    title: "工种",
    width: 90
  }, {
    key: "quota",
    title: "定额单件",
    width: 110,
    render: r => r.quota != null ? /*#__PURE__*/React.createElement("span", {
      style: {
        fontVariantNumeric: "tabular-nums"
      }
    }, r.quota, /*#__PURE__*/React.createElement("span", {
      className: "muted",
      style: {
        color: "var(--ui-muted)",
        marginLeft: 4
      }
    }, "h")) : /*#__PURE__*/React.createElement("span", {
      style: {
        color: "var(--ui-muted)"
      }
    }, "\u7F3A\u5B9A\u989D")
  }, {
    key: "actual",
    title: "实际中位数",
    width: 160,
    render: r => r.actual != null ? /*#__PURE__*/React.createElement("span", {
      style: {
        fontVariantNumeric: "tabular-nums"
      }
    }, r.actual, " ", /*#__PURE__*/React.createElement("span", {
      className: "muted",
      style: {
        color: "var(--ui-muted)"
      }
    }, "h \xB7 ", r.n, " \u6B21")) : /*#__PURE__*/React.createElement("span", {
      style: {
        color: "var(--ui-muted)"
      }
    }, "\u6837\u672C\u4E0D\u8DB3 \xB7 ", r.n, " \u6B21")
  }, {
    key: "dev",
    title: "偏差",
    width: 90,
    render: r => /*#__PURE__*/React.createElement("strong", {
      style: {
        color: r.dev == null ? "var(--ui-muted)" : devColor(r.dev),
        fontVariantNumeric: "tabular-nums"
      }
    }, devText(r))
  }, {
    key: "state",
    title: "状态",
    width: 150,
    render: r => {
      const m = STATE_META[r.state];
      return /*#__PURE__*/React.createElement(Badge, {
        tone: m.tone,
        dot: true
      }, m.label);
    }
  }, {
    key: "act",
    title: "操作",
    width: 150,
    render: r => {
      if (adopted[r.id]) return /*#__PURE__*/React.createElement(Badge, {
        tone: "ok",
        dot: true
      }, "\u5DF2\u91C7\u7EB3 \xB7 \u5DF2\u7559\u75D5");
      if (r.state === "ok") return /*#__PURE__*/React.createElement("span", {
        className: "muted",
        style: {
          fontSize: 12,
          color: "var(--ui-muted)"
        }
      }, "\u65E0\u9700\u8C03\u6574");
      if (r.state === "few") return /*#__PURE__*/React.createElement(Button, {
        variant: "secondary",
        size: "sm",
        disabled: true
      }, "\u91C7\u7EB3");
      return /*#__PURE__*/React.createElement(Button, {
        variant: "secondary",
        size: "sm",
        onClick: () => setAdopted(a => ({
          ...a,
          [r.id]: true
        }))
      }, "\u91C7\u7EB3 ", r.suggest);
    }
  }];
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "dash-head"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "eyebrow"
  }, "\u7EDF\u8BA1\u5206\u6790 \xB7 \u4E0E\u6267\u884C\u590D\u76D8\u540C\u5C42"), /*#__PURE__*/React.createElement("h3", null, "\u5DE5\u65F6\u5B9A\u989D\u6821\u51C6"), /*#__PURE__*/React.createElement("p", {
    className: "dash-note",
    style: {
      maxWidth: 560
    }
  }, "\u5BF9\u6BD4\u73B0\u573A\u5B9E\u9645\u5355\u4EF6\u5DE5\u65F6\uFF08\u8FD1 N \u6B21\u4E2D\u4F4D\u6570\uFF0C\u5DF2\u5254\u6682\u505C / \u5F02\u5E38\uFF09\u4E0E\u5B9A\u989D\u5355\u4EF6\u5DE5\u65F6\uFF0C\u6309\u504F\u5DEE\u6392\u5E8F\u3002", /*#__PURE__*/React.createElement("strong", null, "\u6C38\u4E0D\u81EA\u52A8\u6539\u5B9A\u989D"), "\uFF1A\u91C7\u7EB3\u540E\u624D\u5199\u56DE\u5DE5\u5E8F\u5B9A\u989D\u5E76\u8BB0\u6765\u6E90 / \u91C7\u7EB3\u4EBA / \u65E5\u671F\u3002"))), /*#__PURE__*/React.createElement("div", {
    className: "delay-summary"
  }, summary.map((s, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "ds-card sev-" + s.sev
  }, /*#__PURE__*/React.createElement("div", {
    className: "ds-label"
  }, s.label), /*#__PURE__*/React.createElement("div", {
    className: "ds-value"
  }, s.value), /*#__PURE__*/React.createElement("div", {
    className: "ds-helper"
  }, s.helper)))), /*#__PURE__*/React.createElement(Panel, {
    title: "\u6821\u51C6\u660E\u7EC6",
    description: "\u91C7\u7EB3\u5199\u56DE\u5DE5\u5E8F\u5B9A\u989D\uFF0C\u8BB0\u6765\u6E90 / \u91C7\u7EB3\u4EBA / \u65E5\u671F\uFF1B\u4E0B\u6B21\u5B9A\u989D\u5BA4\u5BFC\u5165\u53EA\u8986\u76D6\u672A\u9501\u5B9A\u9879\u3002\u5DE5\u827A\u4FA7\u53EA\u5728\u503C\u65C1\u6302\u300C\u5B9E\u9645\u6821\u51C6\u300D\u5C0F\u6807\u8BB0\uFF0C\u4E0D\u653E\u6570\u5B57\u4E0E\u6309\u94AE\u3002"
  }, /*#__PURE__*/React.createElement("div", {
    className: "table-tools"
  }, /*#__PURE__*/React.createElement("input", {
    className: "tool-input",
    placeholder: "\u641C\u7D22\u56FE\u53F7\u3001\u5DE5\u5E8F\u3001\u5DE5\u79CD\u2026",
    value: q,
    onChange: e => setQ(e.target.value)
  }), /*#__PURE__*/React.createElement("div", {
    className: "tool-right"
  }, /*#__PURE__*/React.createElement(Button, {
    variant: onlyDev ? "primary" : "secondary",
    size: "sm",
    onClick: () => setOnlyDev(v => !v)
  }, "\u4EC5\u770B\u504F\u5DEE > 20%"), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "sm",
    onClick: () => window.APSDetail && window.APSDetail.toast("导出工时校准明细 · 示例操作")
  }, "\u5BFC\u51FA"))), /*#__PURE__*/React.createElement("div", {
    className: "bd-table-scroll"
  }, /*#__PURE__*/React.createElement(Table, {
    columns: cols,
    rows: rows,
    rowKey: "id"
  })), /*#__PURE__*/React.createElement("p", {
    className: "bd-sec-sub",
    style: {
      marginTop: 12,
      fontSize: 12.5,
      color: "var(--ui-muted)"
    }
  }, "\u6309\u504F\u5DEE\u7EDD\u5BF9\u503C\u6392\u5E8F \xB7 \u5171 126 \u9053\u5728\u4EA7\u5DE5\u5E8F\uFF08\u793A\u4F8B\u6570\u636E\uFF09")));
}
window.CalibScreen = CalibScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/CalibScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/DashboardScreen.jsx
try { (() => {
// APS Workbench · 首页驾驶舱 (dashboard) — context → hero → 7-cell risk grid → rest todos

// inline data-token primitives for the rest-todo cards (方案 C-3 · 因果双通道):
// quantities / durations read as coloured numerals; resource & batch codes
// read as monospace neutral pills; 因 / 故 conjunctions carry the causality.
function HLnum({
  accent,
  children
}) {
  return /*#__PURE__*/React.createElement("strong", {
    style: {
      fontWeight: 700,
      color: accent,
      fontVariantNumeric: "tabular-nums",
      whiteSpace: "nowrap"
    }
  }, children);
}
function CodeTok({
  children
}) {
  return /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      fontSize: "0.88em",
      color: "var(--ui-text)",
      background: "var(--ui-surface-soft)",
      border: "1px solid var(--ui-border)",
      borderRadius: 4,
      padding: "1px 5px",
      whiteSpace: "nowrap"
    }
  }, children);
}
function Conj({
  children
}) {
  return /*#__PURE__*/React.createElement("b", {
    style: {
      color: "var(--ui-muted)",
      fontWeight: 700
    }
  }, children);
}
function DashboardScreen({
  onNav
}) {
  const {
    HeroCard,
    RiskCard,
    Button,
    Badge
  } = window.APSDesignSystem_edbc5d;
  const SEV_ACCENT = {
    ok: "var(--ui-success)",
    notice: "var(--ui-primary)",
    warning: "var(--ui-warning)",
    danger: "var(--ui-danger)"
  };
  const risks = [{
    sev: "danger",
    label: "超期批次",
    value: 3,
    unit: "个",
    helper: "先进入“为什么晚了”说明，再决定怎么改。",
    to: "delay"
  }, {
    sev: "warning",
    label: "接近满载资源",
    value: 2,
    unit: "项",
    helper: "M-03 / M-05 本周利用率 ≥ 90%。",
    to: "gantt"
  }, {
    sev: "warning",
    label: "停机影响工序",
    value: 4,
    unit: "道",
    helper: "周三 08:00–12:00 计划停机牵动 4 道工序。",
    to: "gantt"
  }, {
    sev: "notice",
    label: "外协在途",
    value: 5,
    unit: "单",
    helper: "等待外协回厂，回厂前不可开工。",
    to: "gantt"
  }, {
    sev: "notice",
    label: "待复核方案",
    value: 2,
    unit: "套",
    helper: "两套备选方案尚未复核确认。",
    to: "analysis"
  }, {
    sev: "ok",
    label: "今日完工反馈",
    value: 18,
    unit: "条",
    helper: "车间已回报，正常推进。",
    to: null
  }, {
    sev: "ok",
    label: "待排批次",
    value: 12,
    unit: "个",
    helper: "尚未进入正式计划，可从执行排产进入。",
    to: "run"
  }];

  // structured fields — the key facts pulled out of prose; `detail` renders
  // the 因→故 sentence with coloured numbers + monospace code tokens.
  const todos = [{
    sev: "warning",
    state: "待处理",
    resource: "M-05",
    batch: "B202605-021",
    lead: {
      num: 3,
      unit: "个",
      caption: "批次后移"
    },
    title: "周三停机，预加工批次需后移",
    detail: a => /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Conj, null, "\u56E0"), " ", /*#__PURE__*/React.createElement(CodeTok, null, "M-05"), " \u5468\u4E09\u505C\u673A ", /*#__PURE__*/React.createElement(HLnum, {
      accent: a
    }, "4h"), "\uFF0805-25 08:00\u201312:00\uFF09\uFF0C", /*#__PURE__*/React.createElement(Conj, null, "\u6545"), " ", /*#__PURE__*/React.createElement(HLnum, {
      accent: a
    }, "3"), " \u4E2A\u6279\u6B21\uFF08", /*#__PURE__*/React.createElement(CodeTok, null, "B202605-021"), " \u7B49\uFF09\u5F00\u5DE5\u540E\u79FB\u3002")
  }, {
    sev: "notice",
    state: "待复核",
    resource: "外协 A-02",
    batch: "B202605-017",
    lead: {
      num: 1,
      unit: "个",
      caption: "批次待锁定"
    },
    title: "下料回厂时间未确认，后续工序无法锁定",
    detail: a => /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Conj, null, "\u56E0"), " ", /*#__PURE__*/React.createElement(CodeTok, null, "\u5916\u534F A-02"), " \u56DE\u5382\u672A\u786E\u8BA4\uFF08\u627F\u8BFA ", /*#__PURE__*/React.createElement(HLnum, {
      accent: a
    }, "05-26 08:00"), " \u672A\u56DE\u7B7E\uFF09\uFF0C", /*#__PURE__*/React.createElement(Conj, null, "\u6545"), " ", /*#__PURE__*/React.createElement(HLnum, {
      accent: a
    }, "1"), " \u4E2A\u6279\u6B21\uFF08", /*#__PURE__*/React.createElement(CodeTok, null, "B202605-017"), "\uFF09\u65E0\u6CD5\u9501\u5B9A\u5F00\u5DE5\u3002")
  }];
  return /*#__PURE__*/React.createElement("section", {
    className: "dash"
  }, /*#__PURE__*/React.createElement("div", {
    className: "dash-head"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "eyebrow"
  }, "\u8BA1\u5212\u5458\u503C\u73ED\u53F0"), /*#__PURE__*/React.createElement("h3", null, "\u4ECA\u65E5\u5F85\u5904\u7406"), /*#__PURE__*/React.createElement("div", {
    className: "muted"
  }, "\u6700\u8FD1\u6392\u4EA7 v12 \xB7 \u751F\u6210\u4E8E 05-23 18:40")), /*#__PURE__*/React.createElement("div", {
    className: "dash-note"
  }, "\u672C\u9875\u4E3A\u793A\u4F8B\u6570\u636E\uFF1B\u6B63\u5F0F\u4F7F\u7528\u4EE5\u7CFB\u7EDF\u5B9E\u65F6\u6570\u636E\u4E3A\u51C6\u3002")), /*#__PURE__*/React.createElement(HeroCard, {
    severity: "danger",
    eyebrow: "\u5F53\u524D\u6700\u8981\u7D27",
    lead: {
      caption: "会晚于交期",
      value: 3,
      unit: "个批次",
      sub: "最晚 B202605-018"
    },
    anchor: {
      caption: "最长拖期",
      value: 14,
      unit: "h"
    },
    title: /*#__PURE__*/React.createElement(React.Fragment, null, "\u5361\u70B9\u90FD\u6307\u5411 ", /*#__PURE__*/React.createElement("strong", {
      style: {
        fontWeight: 700,
        color: "var(--ui-text)",
        fontVariantNumeric: "tabular-nums"
      }
    }, "M-03"), "\uFF0C\u672C\u5468\u5229\u7528\u7387 ", /*#__PURE__*/React.createElement("span", {
      style: {
        fontWeight: 700,
        color: "var(--ui-warning)",
        fontVariantNumeric: "tabular-nums"
      }
    }, "96%")),
    evidence: "\u5173\u952E\u5DE5\u5E8F\u6392\u4E0D\u8FDB\u7A7A\u6863\u3002\u5148\u770B\u201C\u4E3A\u4EC0\u4E48\u665A\u4E86\u201D\u7684\u56E0\u679C\u8BF4\u660E\uFF0C\u518D\u51B3\u5B9A\u662F\u63D0\u524D\u5173\u952E\u5DE5\u5E8F\u3001\u8FD8\u662F\u628A\u8D1F\u8377\u632A\u7ED9 M-05\u3002",
    actions: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      onClick: () => onNav("delay")
    }, "\u5EF6\u671F\u8BF4\u660E"), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      onClick: () => window.APSFocusBatchInGantt ? window.APSFocusBatchInGantt("B202605-018") : onNav("gantt")
    }, "\u8F6C\u5230\u7518\u7279\u56FE")),
    style: {
      marginBottom: 8
    }
  }), /*#__PURE__*/React.createElement("div", {
    className: "sec-head"
  }, /*#__PURE__*/React.createElement("h4", null, "\u9700\u8981\u5173\u6CE8"), /*#__PURE__*/React.createElement("span", {
    className: "sec-meta"
  }, "\u5171 ", risks.length, " \u9879 \xB7 \u70B9\u51FB\u8FDB\u5165\u5BF9\u5E94\u89C6\u56FE")), /*#__PURE__*/React.createElement("div", {
    className: "risk-grid"
  }, risks.map((r, i) => /*#__PURE__*/React.createElement(RiskCard, {
    key: i,
    severity: r.sev,
    label: r.label,
    value: r.value,
    unit: r.unit,
    helper: r.helper,
    href: r.to ? "#" : undefined,
    disabled: !r.to,
    onClick: r.to ? e => {
      e.preventDefault();
      onNav(r.to);
    } : undefined
  }))), /*#__PURE__*/React.createElement("div", {
    className: "sec-head"
  }, /*#__PURE__*/React.createElement("h4", null, "\u5176\u4F59\u5F85\u5904\u7406"), /*#__PURE__*/React.createElement("span", {
    className: "sec-meta"
  }, todos.length, " \u9879 \xB7 \u5DF2\u6309\u5F71\u54CD\u6392\u5E8F")), /*#__PURE__*/React.createElement("div", {
    className: "rest-list"
  }, todos.map((t, i) => /*#__PURE__*/React.createElement("article", {
    key: i,
    className: "rest-item sev-" + t.sev,
    style: {
      gap: "12px 22px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: "none",
      width: 96,
      paddingRight: 22,
      borderRight: "1px solid var(--ui-border)",
      display: "flex",
      flexDirection: "column",
      alignItems: "flex-start"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: "flex",
      alignItems: "baseline",
      gap: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 40,
      fontWeight: 700,
      color: SEV_ACCENT[t.sev],
      fontVariantNumeric: "tabular-nums",
      lineHeight: 1
    }
  }, t.lead.num), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 14,
      fontWeight: 600,
      color: "var(--ui-muted)"
    }
  }, t.lead.unit)), /*#__PURE__*/React.createElement("span", {
    style: {
      marginTop: 7,
      fontSize: 12,
      color: "var(--ui-muted)",
      whiteSpace: "nowrap"
    }
  }, t.lead.caption)), /*#__PURE__*/React.createElement("div", {
    className: "rest-body"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      marginBottom: 8,
      flexWrap: "wrap"
    }
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: t.sev,
    dot: true
  }, t.state), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      fontWeight: 700,
      color: "var(--ui-muted)",
      fontVariantNumeric: "tabular-nums",
      whiteSpace: "nowrap"
    }
  }, t.resource)), /*#__PURE__*/React.createElement("h4", null, t.title), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: "8px 0 0",
      fontSize: 13.5,
      lineHeight: 1.7,
      color: "var(--ui-muted)",
      textWrap: "pretty"
    }
  }, t.detail(SEV_ACCENT[t.sev]))), /*#__PURE__*/React.createElement("div", {
    className: "rest-actions"
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "sm",
    onClick: () => window.APSFocusBatchInGantt ? window.APSFocusBatchInGantt(t.batch) : onNav("gantt")
  }, "\u8F6C\u5230\u7518\u7279\u56FE"))))));
}
window.DashboardScreen = DashboardScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/DashboardScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/DelayScreen.jsx
try { (() => {
// APS Workbench · 延期说明 (scheduler/delay)
function DelayScreen({
  onNav
}) {
  const {
    Panel,
    Badge,
    Button,
    Kpi
  } = window.APSDesignSystem_edbc5d;
  const summary = [{
    sev: "danger",
    label: "晚交风险",
    value: 3,
    helper: "完成时间晚于交期的批次",
    chip: ["danger", "优先级高"]
  }, {
    sev: "warning",
    label: "资源冲突",
    value: 2,
    helper: "同一资源同段时间被多次占用",
    chip: ["warning", "需关注"]
  }, {
    sev: "notice",
    label: "停机影响",
    value: 1,
    helper: "计划停机导致工序后移",
    chip: ["notice", "已知"]
  }, {
    sev: "ok",
    label: "物料待齐",
    value: 2,
    helper: "缺料或未齐套，结果不可信",
    chip: ["secondary", "基础数据"]
  }];
  const timeline = [{
    tone: "danger",
    time: "05-24 12:00",
    title: "超过交期",
    desc: "B202605-018 计划完成 18:00，晚于交期 12:00。"
  }, {
    tone: "warning",
    time: "05-24 08:00",
    title: "卡在 M-03",
    desc: "M-03 本周利用率 96%，第 30 工序需等待空档。"
  }, {
    tone: "notice",
    time: "05-23 18:40",
    title: "排产生成 v12",
    desc: "采用关键工序优先，超期批次 2 个。"
  }, {
    tone: "success",
    time: "建议",
    title: "怎么改",
    desc: "把 30 工序提前到周一空档，或将部分负荷挪给 M-05。"
  }];
  return /*#__PURE__*/React.createElement(Panel, {
    title: "\u5EF6\u671F\u8BF4\u660E",
    description: "\u4E0D\u662F\u9519\u8BEF\u6E05\u5355\uFF0C\u800C\u662F\u628A\u201C\u4E3A\u4EC0\u4E48\u665A\u3001\u5361\u5728\u54EA\u3001\u5F71\u54CD\u8C01\u3001\u600E\u4E48\u6539\u201D\u8BB2\u6E05\u695A \u2014\u2014 \u70B9\u8FDB\u6765\u5C31\u77E5\u9053\u4E0B\u4E00\u6B65\u505A\u4EC0\u4E48\u3002",
    headerRight: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Badge, {
      tone: "danger"
    }, "\u665A\u4EA4"), /*#__PURE__*/React.createElement(Badge, {
      tone: "warning"
    }, "\u51B2\u7A81"), /*#__PURE__*/React.createElement(Badge, {
      tone: "notice"
    }, "\u505C\u673A"))
  }, /*#__PURE__*/React.createElement("div", {
    className: "delay-summary"
  }, summary.map((s, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "ds-card sev-" + s.sev
  }, /*#__PURE__*/React.createElement("div", {
    className: "ds-label"
  }, s.label), /*#__PURE__*/React.createElement("div", {
    className: "ds-value"
  }, s.value), /*#__PURE__*/React.createElement("div", {
    className: "ds-helper"
  }, s.helper), /*#__PURE__*/React.createElement(Badge, {
    tone: s.chip[0]
  }, s.chip[1])))), /*#__PURE__*/React.createElement("div", {
    className: "delay-body"
  }, /*#__PURE__*/React.createElement("div", {
    className: "delay-story"
  }, /*#__PURE__*/React.createElement("h4", null, "B202605-018 \xB7 \u4E3A\u4EC0\u4E48\u665A\u4E86"), /*#__PURE__*/React.createElement("p", null, "\u8FD9\u4E2A\u6279\u6B21\u7684\u5173\u952E\u5DE5\u5E8F\u6392\u5728\u4E86\u6700\u5FD9\u7684\u8BBE\u5907\u4E0A\uFF0C\u53C8\u8D76\u4E0A\u4EA4\u671F\u6700\u7D27\uFF0C\u6240\u4EE5\u88AB\u6807\u6210\u8D85\u671F\u3002\u4E0B\u9762\u628A\u201C\u665A\u591A\u4E45\u3001\u5361\u5728\u54EA\u3001\u600E\u4E48\u6539\u201D\u62C6\u5F00\u8BB2\u3002"), /*#__PURE__*/React.createElement("div", {
    className: "story-stats"
  }, /*#__PURE__*/React.createElement(Kpi, {
    label: "\u665A\u591A\u4E45",
    value: "6h"
  }), /*#__PURE__*/React.createElement(Kpi, {
    label: "\u5361\u70B9\u8D44\u6E90",
    value: "M-03",
    valueColor: "var(--ui-danger)"
  }), /*#__PURE__*/React.createElement(Kpi, {
    label: "\u5F71\u54CD\u6279\u6B21",
    value: 2
  })), /*#__PURE__*/React.createElement("div", {
    className: "story-actions"
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    onClick: () => window.APSFocusBatchInGantt ? window.APSFocusBatchInGantt("B202605-018") : onNav("gantt")
  }, "\u8F6C\u5230\u7518\u7279\u56FE"), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    onClick: () => onNav("analysis")
  }, "\u5BF9\u6BD4\u5907\u9009\u65B9\u6848"), /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    onClick: () => window.APSDetail && window.APSDetail.toast("已复制交接说明到剪贴板（示例）")
  }, "\u590D\u5236\u4EA4\u63A5\u8BF4\u660E"))), /*#__PURE__*/React.createElement("div", {
    className: "delay-timeline"
  }, /*#__PURE__*/React.createElement("h4", null, "\u56E0\u679C\u65F6\u95F4\u7EBF"), /*#__PURE__*/React.createElement("div", {
    className: "tl"
  }, timeline.map((e, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "tl-item"
  }, /*#__PURE__*/React.createElement("span", {
    className: "tl-dot tone-" + e.tone
  }), /*#__PURE__*/React.createElement("div", {
    className: "tl-card"
  }, /*#__PURE__*/React.createElement("div", {
    className: "tl-row"
  }, /*#__PURE__*/React.createElement("strong", null, e.title), /*#__PURE__*/React.createElement("span", null, e.time)), /*#__PURE__*/React.createElement("div", {
    className: "tl-desc"
  }, e.desc))))))));
}
window.DelayScreen = DelayScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/DelayScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/FieldGanttScreen.jsx
try { (() => {
// APS Workbench · 现场实际甘特（看结果 · 计划 vs 实际）
// 把「现场记录」里回填的实际开工/完工时间画成甘特，与排产计划逐道工序对照。
// 同一份工序数据：设备 / 人员 / 批次三视图只是不同透视。本页为 06-11 当天，
// 时间口径来自现场记录回填（非实时 MES）。每道工序两条：上为计划（虚线），
// 下为实际（实色，按完工偏差着色）；虚竖线为该工序的计划完工参考。
// 看板外框（gb-board / gb-scale / gb-res / gb-tip）复用「设备/人员/批次甘特」。
// 时间颗粒度（缩放）：单日小时轴——hourw 控制每小时列宽，sub 控制辅助网格细分。
// − 越看越粗（紧凑全天）· + 越看越细（精确到 15 分钟）
// 与「设备/人员/批次甘特」一致的四档颗粒度：周 / 日 / 半天 / 时。
// 本页为单日小时轴，故由粗到细映射到小时列宽 + 辅助网格细分。
const FG_GRAN = [{
  key: "week",
  label: "周",
  hourw: 46,
  sub: 1,
  tip: "全天概览"
}, {
  key: "day",
  label: "日",
  hourw: 78,
  sub: 1,
  tip: "每格 1 小时"
}, {
  key: "halfday",
  label: "半天",
  hourw: 120,
  sub: 2,
  tip: "每格 30 分钟"
}, {
  key: "hour",
  label: "时",
  hourw: 184,
  sub: 4,
  tip: "每格 15 分钟"
}];
function FieldGanttScreen() {
  const {
    Panel
  } = window.APSDesignSystem_edbc5d;
  const [view, setView] = React.useState("device");
  const [zoom, setZoom] = React.useState(1); // 颗粒度索引，默认「标准」
  const [filterOn, setFilterOn] = React.useState(false); // 仅看完工晚于计划的工序
  const [tip, setTip] = React.useState(null);
  const gran = FG_GRAN[zoom];
  const H0 = 6,
    H1 = 16,
    SPAN = H1 - H0; // 06:00–16:00
  const NOW = 11 + 40 / 60; // 现在 ≈ 11:40

  const toMin = s => {
    const m = /(\d{1,2}):(\d{2})/.exec(s || "");
    return m ? +m[1] * 60 + +m[2] : null;
  };
  const toH = s => {
    const v = toMin(s);
    return v == null ? null : v / 60;
  };
  const hToStr = h => {
    const hh = Math.floor(h);
    const mm = Math.round((h - hh) * 60);
    return String(hh).padStart(2, "0") + ":" + String(mm).padStart(2, "0");
  };
  const L = s => (toH(s) - H0) / SPAN * 100;
  const W = (a, b) => (toH(b) - toH(a)) / SPAN * 100;
  const fmtDelta = m => (m > 0 ? "+" : m < 0 ? "−" : "±") + Math.abs(Math.round(m)) + "m";
  const DEVNAME = {
    "M-03": "五轴加工中心",
    "M-05": "卧式加工中心",
    "M-07": "立式加工中心",
    "M-12": "三坐标检测",
    "M-18": "数控车床"
  };
  const PARTNAME = {
    "B202605-019": "轴套 F",
    "B202605-020": "法兰 D",
    "B202605-018": "回转壳体 A",
    "B202605-021": "回转壳体 B",
    "B202605-024": "端盖 C",
    "B202605-022": "回转壳体 B",
    "B202605-017": "连接板 G"
  };

  // 每行 = 现场记录里的一道工序；plan* 来自排产计划，act* 为回填实际（与 FieldRecordScreen 对齐）。
  const ROWS = [{
    batch: "B202605-019",
    op: "50 检验",
    dev: "M-12",
    person: "王五",
    planStart: "08:00",
    planEnd: "09:30",
    actStart: "08:05",
    actEnd: "09:18"
  }, {
    batch: "B202605-019",
    op: "40 组装",
    dev: "M-07",
    person: "李四",
    planStart: "06:30",
    planEnd: "08:30",
    actStart: "06:35",
    actEnd: "08:40"
  }, {
    batch: "B202605-020",
    op: "10 下料",
    dev: "M-18",
    person: "赵六",
    planStart: "07:30",
    planEnd: "08:15",
    actStart: "07:40",
    actEnd: "08:25"
  }, {
    batch: "B202605-018",
    op: "30 精加工",
    dev: "M-03",
    person: "张三",
    planStart: "08:00",
    planEnd: "11:00",
    actStart: "08:10",
    actEnd: ""
  }, {
    batch: "B202605-021",
    op: "20 预加工",
    dev: "M-05",
    person: "李四",
    planStart: "09:00",
    planEnd: "11:00",
    actStart: "09:05",
    actEnd: "11:20"
  }, {
    batch: "B202605-024",
    op: "30 精加工",
    dev: "M-03",
    person: "张三",
    planStart: "11:30",
    planEnd: "14:30",
    actStart: "",
    actEnd: ""
  }, {
    batch: "B202605-022",
    op: "10 下料",
    dev: "M-18",
    person: "赵六",
    planStart: "13:00",
    planEnd: "13:50",
    actStart: "",
    actEnd: ""
  }, {
    batch: "B202605-017",
    op: "50 检验",
    dev: "M-12",
    person: "王五",
    planStart: "14:00",
    planEnd: "15:30",
    actStart: "",
    actEnd: ""
  }];
  const statusOf = r => !r.actStart ? "todo" : !r.actEnd ? "doing" : "done";
  const endDelta = r => r.actEnd ? toMin(r.actEnd) - toMin(r.planEnd) : null;
  const toneOf = r => {
    const st = statusOf(r);
    if (st === "todo") return "todo";
    if (st === "doing") return "doing";
    const d = endDelta(r);
    if (d <= 10) return "ok";
    if (d <= 30) return "warn";
    return "bad";
  };
  const TONE_BG = {
    ok: "var(--ui-success)",
    warn: "var(--ui-warning)",
    bad: "var(--ui-danger)",
    doing: "var(--ui-primary)"
  };
  const ICON = {
    device: '<path d="M3 20h18M5 20V9l5 3V9l5 3V6l4 2v12"/>',
    person: '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 3-5 6-5s6 1.7 6 5"/><path d="M16 5.5a3 3 0 010 6"/>',
    batch: '<path d="M3 7l9-4 9 4v10l-9 4-9-4V7z"/><path d="M3 7l9 4 9-4M12 11v10"/>'
  };
  const Svg = ({
    d
  }) => /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.7",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    dangerouslySetInnerHTML: {
      __html: d
    }
  });

  // 筛选：仅看完工晚于计划（>10m）的工序——可切换的真实筛选，非提示
  const lateOf = r => statusOf(r) === "done" && endDelta(r) > 10;
  const lateCount = ROWS.filter(lateOf).length;
  const visRows = filterOn ? ROWS.filter(lateOf) : ROWS;
  function lanesFor() {
    if (view === "device") {
      const keys = [...new Set(visRows.map(r => r.dev))];
      return keys.map(k => ({
        kind: "device",
        code: k,
        name: k,
        sub: DEVNAME[k] || "设备",
        tasks: visRows.filter(r => r.dev === k)
      }));
    }
    if (view === "person") {
      const keys = [...new Set(visRows.map(r => r.person))];
      return keys.map(k => ({
        kind: "person",
        code: k,
        name: k,
        sub: "操作工",
        tasks: visRows.filter(r => r.person === k)
      }));
    }
    const keys = [...new Set(visRows.map(r => r.batch))];
    return keys.map(k => ({
      kind: "batch",
      code: k,
      name: k,
      sub: PARTNAME[k] || "",
      tasks: visRows.filter(r => r.batch === k)
    }));
  }
  const lanes = lanesFor();
  const visDone = visRows.filter(r => statusOf(r) !== "todo").length;
  const viewUnit = view === "device" ? "台设备" : view === "person" ? "名人员" : "个批次";
  const done = ROWS.filter(r => statusOf(r) === "done").length;
  const doing = ROWS.filter(r => statusOf(r) === "doing").length;
  const todo = ROWS.filter(r => statusOf(r) === "todo").length;
  const ds = ROWS.filter(r => statusOf(r) === "done").map(endDelta);
  const avg = ds.length ? ds.reduce((a, b) => a + b, 0) / ds.length : null;
  const late = ROWS.filter(r => statusOf(r) === "done" && endDelta(r) > 10).length;
  const stats = [{
    sev: "ok",
    label: "已回填工序",
    value: done,
    helper: "开工 / 完工齐全，可对比计划"
  }, {
    sev: "notice",
    label: "进行中",
    value: doing,
    helper: "已开工，尚未完工"
  }, {
    sev: "warning",
    label: "待回填",
    value: todo,
    helper: "仅有计划，缺实际记录"
  }, {
    sev: late ? "warning" : "ok",
    label: "平均完工偏差",
    value: avg == null ? "—" : fmtDelta(avg),
    helper: late ? late + " 道工序晚于计划完工" : "整体贴合计划"
  }];
  const tailOf = b => b.slice(-3);
  const HOURS = Array.from({
    length: SPAN
  }, (_, i) => H0 + i);
  const openBatch = b => {
    if (window.APSDetail && window.APSDetail.has(b)) window.APSDetail.open(b, "batch", {
      from: "field-gantt"
    });
  };

  // 每条泳道：回填进度（已开工 / 全部）+ 是否有延后，用于资源格底部进度条着色
  const laneStat = ln => {
    const total = ln.tasks.length;
    const filled = ln.tasks.filter(r => r.actStart).length;
    const lateN = ln.tasks.filter(r => statusOf(r) === "done" && endDelta(r) > 10).length;
    const sv = lateN ? ln.tasks.some(r => statusOf(r) === "done" && endDelta(r) > 30) ? "danger" : "warn" : filled === total ? "" : "off";
    return {
      total,
      filled,
      lateN,
      pct: total ? Math.round(filled / total * 100) : 0,
      sv
    };
  };
  const onBarEnter = (r, e) => setTip({
    r,
    x: e.clientX,
    y: e.clientY
  });
  const onBarLeave = () => setTip(null);
  return /*#__PURE__*/React.createElement(Panel, {
    title: "\u73B0\u573A\u5B9E\u9645\u7518\u7279 \xB7 \u8BA1\u5212 vs \u5B9E\u9645",
    description: "\u628A\u73B0\u573A\u8BB0\u5F55\u91CC\u56DE\u586B\u7684\u5B9E\u9645\u5F00\u5DE5 / \u5B8C\u5DE5\u65F6\u95F4\u753B\u6210\u7518\u7279\uFF0C\u4E0E\u6392\u4EA7\u8BA1\u5212\u9010\u9053\u5DE5\u5E8F\u5BF9\u7167\uFF1A\u6BCF\u9053\u5DE5\u5E8F\u4E0A\u4E3A\u8BA1\u5212\uFF08\u865A\u7EBF\u8F6E\u5ED3\uFF09\uFF0C\u4E0B\u4E3A\u5B9E\u9645\uFF08\u5B9E\u8272\uFF0C\u6309\u5B8C\u5DE5\u504F\u5DEE\u7740\u8272\uFF09\uFF0C\u770B\u5F97\u89C1\u5F00\u5DE5\u62D6\u5EF6\u3001\u5DE5\u65F6\u8D85\u8017\u4E0E\u5B8C\u5DE5\u504F\u5DEE\u3002\u672C\u9875\u4E3A 06-11 \u5F53\u5929\uFF0C\u65F6\u95F4\u53E3\u5F84\u6765\u81EA\u73B0\u573A\u8BB0\u5F55\u56DE\u586B\uFF0C\u975E\u5B9E\u65F6 MES \u4FE1\u53F7\u3002"
  }, /*#__PURE__*/React.createElement("div", {
    className: "delay-summary"
  }, stats.map((s, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "ds-card sev-" + s.sev
  }, /*#__PURE__*/React.createElement("div", {
    className: "ds-label"
  }, s.label), /*#__PURE__*/React.createElement("div", {
    className: "ds-value"
  }, s.value), /*#__PURE__*/React.createElement("div", {
    className: "ds-helper"
  }, s.helper)))), /*#__PURE__*/React.createElement("div", {
    className: "gb-toolbar"
  }, /*#__PURE__*/React.createElement("div", {
    className: "gb-tb-group"
  }, /*#__PURE__*/React.createElement("span", {
    className: "gb-tb-label"
  }, "\u89C6\u56FE"), /*#__PURE__*/React.createElement("div", {
    className: "seg"
  }, [["device", "设备"], ["person", "人员"], ["batch", "批次"]].map(([k, l]) => /*#__PURE__*/React.createElement("button", {
    key: k,
    className: "seg-btn" + (view === k ? " on" : ""),
    onClick: () => setView(k)
  }, l)))), /*#__PURE__*/React.createElement("div", {
    className: "gb-tb-group"
  }, /*#__PURE__*/React.createElement("span", {
    className: "gb-tb-label"
  }, "\u9897\u7C92\u5EA6"), /*#__PURE__*/React.createElement("div", {
    className: "gb-zoom-ctl"
  }, /*#__PURE__*/React.createElement("button", {
    className: "gb-zoom-btn",
    disabled: zoom <= 0,
    onClick: () => setZoom(z => Math.max(0, z - 1)),
    title: "\u7F29\u5C0F\xB7\u65F6\u95F4\u53D8\u7C97",
    "aria-label": "\u7F29\u5C0F\u9897\u7C92\u5EA6"
  }, "\u2212"), /*#__PURE__*/React.createElement("span", {
    className: "gb-zoom-lvl"
  }, gran.label), /*#__PURE__*/React.createElement("button", {
    className: "gb-zoom-btn",
    disabled: zoom >= FG_GRAN.length - 1,
    onClick: () => setZoom(z => Math.min(FG_GRAN.length - 1, z + 1)),
    title: "\u653E\u5927\xB7\u65F6\u95F4\u53D8\u7EC6",
    "aria-label": "\u653E\u5927\u9897\u7C92\u5EA6"
  }, "+"))), /*#__PURE__*/React.createElement("span", {
    className: "gb-tb-summary"
  }, "\u672C\u89C6\u56FE ", /*#__PURE__*/React.createElement("b", null, lanes.length), " ", viewUnit, " \xB7 ", /*#__PURE__*/React.createElement("b", null, visRows.length), " \u9053\u5DE5\u5E8F \xB7 ", /*#__PURE__*/React.createElement("b", null, visDone), " \u5DF2\u56DE\u586B"), /*#__PURE__*/React.createElement("div", {
    className: "gb-tb-actions"
  }, /*#__PURE__*/React.createElement("button", {
    className: "gb-tb-btn" + (filterOn ? " on" : ""),
    onClick: () => setFilterOn(v => !v),
    title: "\u53EA\u770B\u5B8C\u5DE5\u665A\u4E8E\u8BA1\u5212\u7684\u5DE5\u5E8F"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M3 5h18l-7 8v5l-4 2v-7z"
  })), "\u4EC5\u5EF6\u540E", /*#__PURE__*/React.createElement("span", {
    className: "gb-tb-count"
  }, lateCount)), /*#__PURE__*/React.createElement("button", {
    className: "gb-tb-btn",
    onClick: () => window.APSDetail && window.APSDetail.toast("导出现场实际甘特 · 示例操作")
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M12 3v11m0 0l-4-4m4 4l4-4M5 19h14"
  })), "\u5BFC\u51FA"))), /*#__PURE__*/React.createElement("div", {
    className: "fg-legend"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fg-lg"
  }, /*#__PURE__*/React.createElement("i", {
    className: "fg-sw-plan"
  }), "\u8BA1\u5212\uFF08\u865A\u7EBF\uFF09"), /*#__PURE__*/React.createElement("span", {
    className: "fg-lg"
  }, /*#__PURE__*/React.createElement("i", {
    className: "fg-sw-act",
    style: {
      background: "var(--ui-success)"
    }
  }), "\u51C6\u65F6 / \u63D0\u524D"), /*#__PURE__*/React.createElement("span", {
    className: "fg-lg"
  }, /*#__PURE__*/React.createElement("i", {
    className: "fg-sw-act",
    style: {
      background: "var(--ui-warning)"
    }
  }), "\u5EF6\u540E \u226430m"), /*#__PURE__*/React.createElement("span", {
    className: "fg-lg"
  }, /*#__PURE__*/React.createElement("i", {
    className: "fg-sw-act",
    style: {
      background: "var(--ui-danger)"
    }
  }), "\u5EF6\u540E >30m"), /*#__PURE__*/React.createElement("span", {
    className: "fg-lg"
  }, /*#__PURE__*/React.createElement("i", {
    className: "fg-sw-act",
    style: {
      background: "var(--ui-primary)"
    }
  }), "\u8FDB\u884C\u4E2D"), /*#__PURE__*/React.createElement("span", {
    className: "fg-lg"
  }, /*#__PURE__*/React.createElement("i", {
    className: "fg-sw-ref"
  }), "\u8BA1\u5212\u5B8C\u5DE5\u53C2\u8003\u7EBF")), /*#__PURE__*/React.createElement("div", {
    className: "gb fg-scope",
    style: {
      "--fg-hourw": gran.hourw + "px",
      "--fg-sub": gran.sub
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "gb-board"
  }, /*#__PURE__*/React.createElement("div", {
    className: "gb-scale"
  }, /*#__PURE__*/React.createElement("div", {
    className: "gb-corner"
  }, view === "batch" ? "批次 / 工序" : view === "person" ? "人员 / 任务" : "设备 / 任务", /*#__PURE__*/React.createElement("span", {
    className: "gb-corner-sub"
  }, "\xB7 06:00\u201316:00 \xB7 ", gran.tip)), /*#__PURE__*/React.createElement("div", {
    className: "fg-hours"
  }, HOURS.map(h => /*#__PURE__*/React.createElement("div", {
    key: h,
    className: "fg-hour"
  }, String(h).padStart(2, "0"), ":00")))), /*#__PURE__*/React.createElement("div", {
    className: "gb-grid"
  }, lanes.map(ln => {
    const st = laneStat(ln);
    return /*#__PURE__*/React.createElement("div", {
      className: "gb-row",
      key: ln.code
    }, /*#__PURE__*/React.createElement("div", {
      className: "gb-res"
    }, /*#__PURE__*/React.createElement("span", {
      className: "gb-res-ico"
    }, /*#__PURE__*/React.createElement(Svg, {
      d: ICON[ln.kind]
    })), /*#__PURE__*/React.createElement("div", {
      className: "gb-res-main"
    }, /*#__PURE__*/React.createElement("div", {
      className: "gb-res-name"
    }, ln.name), /*#__PURE__*/React.createElement("div", {
      className: "gb-res-sub"
    }, ln.sub, " \xB7 ", ln.tasks.length, " \u9053\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("div", {
      className: "fg-res-foot"
    }, /*#__PURE__*/React.createElement("span", {
      className: "gb-loadbar " + st.sv
    }, /*#__PURE__*/React.createElement("i", {
      style: {
        width: Math.max(st.pct, 2) + "%"
      }
    })), /*#__PURE__*/React.createElement("span", {
      className: "fg-fillnum"
    }, "\u56DE\u586B ", /*#__PURE__*/React.createElement("b", null, st.filled), "/", st.total)))), /*#__PURE__*/React.createElement("div", {
      className: "fg-track"
    }, /*#__PURE__*/React.createElement("span", {
      className: "fg-now",
      style: {
        left: (NOW - H0) / SPAN * 100 + "%"
      }
    }), ln.tasks.map((r, i) => {
      const stt = statusOf(r),
        tone = toneOf(r);
      const planL = L(r.planStart),
        planW = W(r.planStart, r.planEnd);
      const tag = view === "batch" ? r.dev : tailOf(r.batch);
      if (stt === "todo") {
        return /*#__PURE__*/React.createElement("div", {
          key: i,
          className: "fg-plan is-pending",
          style: {
            left: planL + "%",
            width: planW + "%"
          },
          onMouseEnter: e => onBarEnter(r, e),
          onMouseMove: e => onBarEnter(r, e),
          onMouseLeave: onBarLeave
        }, /*#__PURE__*/React.createElement("span", {
          className: "fg-plan-lab"
        }, r.op, /*#__PURE__*/React.createElement("em", null, tag)), /*#__PURE__*/React.createElement("span", {
          className: "fg-todo-tag"
        }, "\u5F85\u56DE\u586B"));
      }
      const actEndStr = r.actEnd || hToStr(NOW);
      const actL = L(r.actStart),
        actW = W(r.actStart, actEndStr);
      const d = endDelta(r);
      return /*#__PURE__*/React.createElement(React.Fragment, {
        key: i
      }, /*#__PURE__*/React.createElement("div", {
        className: "fg-plan",
        style: {
          left: planL + "%",
          width: planW + "%"
        },
        onMouseEnter: e => onBarEnter(r, e),
        onMouseMove: e => onBarEnter(r, e),
        onMouseLeave: onBarLeave
      }, /*#__PURE__*/React.createElement("span", {
        className: "fg-plan-lab"
      }, r.op, /*#__PURE__*/React.createElement("em", null, tag))), /*#__PURE__*/React.createElement("span", {
        className: "fg-ref",
        style: {
          left: L(r.planEnd) + "%"
        },
        title: "计划完工 " + r.planEnd
      }), /*#__PURE__*/React.createElement("div", {
        className: "fg-act tone-" + tone,
        style: {
          left: actL + "%",
          width: Math.max(actW, 1.5) + "%",
          background: TONE_BG[tone]
        },
        onClick: () => openBatch(r.batch),
        onMouseEnter: e => onBarEnter(r, e),
        onMouseMove: e => onBarEnter(r, e),
        onMouseLeave: onBarLeave
      }, /*#__PURE__*/React.createElement("span", {
        className: "fg-act-lab"
      }, r.op), /*#__PURE__*/React.createElement("span", {
        className: "fg-act-badge"
      }, stt === "doing" ? "进行中" : d == null ? "" : fmtDelta(d))));
    })));
  })))), tip ? (() => {
    const r = tip.r,
      stt = statusOf(r),
      d = endDelta(r);
    return /*#__PURE__*/React.createElement("div", {
      className: "gb-tip on",
      style: {
        left: Math.min(tip.x + 14, window.innerWidth - 296),
        top: tip.y + 16
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        marginBottom: 4
      }
    }, /*#__PURE__*/React.createElement("b", null, r.batch), " \xB7 ", PARTNAME[r.batch] || ""), /*#__PURE__*/React.createElement("div", {
      className: "gb-tip-row"
    }, /*#__PURE__*/React.createElement("span", null, "\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("span", null, r.op)), /*#__PURE__*/React.createElement("div", {
      className: "gb-tip-row"
    }, /*#__PURE__*/React.createElement("span", null, view === "person" ? "设备" : "人员"), /*#__PURE__*/React.createElement("span", null, view === "person" ? r.dev + " " + (DEVNAME[r.dev] || "") : r.person)), /*#__PURE__*/React.createElement("div", {
      className: "gb-tip-row"
    }, /*#__PURE__*/React.createElement("span", null, "\u8BA1\u5212"), /*#__PURE__*/React.createElement("span", null, r.planStart, " \u2192 ", r.planEnd)), /*#__PURE__*/React.createElement("div", {
      className: "gb-tip-row"
    }, /*#__PURE__*/React.createElement("span", null, "\u5B9E\u9645"), /*#__PURE__*/React.createElement("span", null, stt === "todo" ? "待回填" : r.actStart + " → " + (r.actEnd || "进行中"))), /*#__PURE__*/React.createElement("div", {
      className: "gb-tip-row"
    }, /*#__PURE__*/React.createElement("span", null, "\u5B8C\u5DE5\u504F\u5DEE"), /*#__PURE__*/React.createElement("span", null, stt === "done" ? fmtDelta(d) + (d > 10 ? " · 延后" : "") : stt === "doing" ? "进行中" : "—")));
  })() : null, /*#__PURE__*/React.createElement("p", {
    style: {
      marginTop: 12,
      fontSize: 12.5,
      color: "var(--ui-muted)",
      lineHeight: 1.6
    }
  }, "\u6BCF\u9053\u5DE5\u5E8F\u4E24\u6761\uFF1A\u4E0A\u4E3A", /*#__PURE__*/React.createElement("strong", null, "\u8BA1\u5212"), "\uFF08\u865A\u7EBF\u8F6E\u5ED3\uFF09\uFF0C\u4E0B\u4E3A", /*#__PURE__*/React.createElement("strong", null, "\u5B9E\u9645"), "\uFF08\u5B9E\u8272\uFF09\uFF0C\u5B9E\u8272\u6309\u5B8C\u5DE5\u504F\u5DEE\u7740\u8272\u2014\u2014", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--ui-success)",
      fontWeight: 700
    }
  }, "\u7EFF"), " \u51C6\u65F6 / \u63D0\u524D\u3001", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--ui-warning-text, var(--ui-warning))",
      fontWeight: 700
    }
  }, "\u9EC4"), " \u5EF6\u540E \u226430m\u3001", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--ui-danger)",
      fontWeight: 700
    }
  }, "\u7EA2"), " \u5EF6\u540E >30m\u3002\u865A\u7AD6\u7EBF\u4E3A\u8BE5\u5DE5\u5E8F\u7684", /*#__PURE__*/React.createElement("strong", null, "\u8BA1\u5212\u5B8C\u5DE5"), "\u53C2\u8003\uFF0C\u5B9E\u9645\u6761\u8D8A\u8FC7\u5373\u4E3A\u5EF6\u540E\u3002\u70B9\u5B9E\u9645\u6761\u53EF\u5F00\u5DE5\u5E8F\u8BE6\u60C5\uFF08\u793A\u4F8B\u6570\u636E\uFF09\u3002"));
}
window.FieldGanttScreen = FieldGanttScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/FieldGanttScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/FieldRecordScreen.jsx
try { (() => {
// APS Workbench · 现场记录 (field) — 实际执行回填工作台。
// 这里不接 MES，没有真实的现场开工 / 完工信号。所谓"现场"指的是排产计划
// 对应工序的「实际」开工时间、完工时间和工时，由计划员 / 工艺员事后照计划
// 与实际情况回填。回填结果不是实时现场状态，而是供「工时定额校准」「执行
// 复盘」做后续处理的实绩数据。
//   · 顶部 — 回填进度概览（待回填 / 进行中 / 已回填 / 工时合计 / 完工偏差）
//   · 主体 — 可就地编辑的工序回填表：计划列只读，实际三列（开工/完工/工时）可填

const FR_STATE_META = {
  done: {
    tone: "success",
    label: "已回填"
  },
  doing: {
    tone: "notice",
    label: "进行中"
  },
  todo: {
    tone: "secondary",
    label: "待回填"
  }
};

// "MM-DD HH:MM" → 绝对分钟数（同年内比较即可）；非法返回 null
function frParseT(s) {
  const m = /^\s*(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})\s*$/.exec(s || "");
  if (!m) return null;
  return (+m[1] * 31 + +m[2]) * 1440 + +m[3] * 60 + +m[4];
}
function frCalcHours(a, b) {
  const x = frParseT(a),
    y = frParseT(b);
  if (x == null || y == null || y <= x) return "";
  return ((y - x) / 60).toFixed(1);
}
function frFmtMin(m) {
  if (m == null || isNaN(m)) return "—";
  const a = Math.abs(Math.round(m));
  const sign = m > 0 ? "+" : m < 0 ? "−" : "±";
  return a >= 60 ? sign + (a / 60).toFixed(1) + "h" : sign + a + "m";
}

// 绝对分钟数 → "MM-DD HH:MM"（frParseT 的逆运算，仅同年内有效）
function frMinToDT(total) {
  if (total == null || isNaN(total) || total < 0) return "";
  total = Math.round(total);
  const mm = total % 60;
  const ht = (total - mm) / 60;
  const hh = ht % 24;
  let days = Math.floor(ht / 24);
  let mo = Math.floor(days / 31);
  let d = days % 31;
  if (d === 0) {
    d = 31;
    mo -= 1;
  }
  if (mo < 1) return "";
  return frFmtDT(mo, d, hh, mm);
}

// 由另外两项推算 target（实际开工 actStart / 实际完工 actEnd / 工时 hours）；
// 推不出（缺值或非法）返回 null，调用方据此保留原值，不强行覆盖。
function frDerive(target, r) {
  if (target === "hours") {
    const h = frCalcHours(r.actStart, r.actEnd);
    return h !== "" ? h : null;
  }
  if (target === "actEnd") {
    const x = frParseT(r.actStart);
    const h = parseFloat(r.hours);
    if (x == null || !(h > 0)) return null;
    return frMinToDT(x + h * 60) || null;
  }
  if (target === "actStart") {
    const y = frParseT(r.actEnd);
    const h = parseFloat(r.hours);
    if (y == null || !(h > 0)) return null;
    return frMinToDT(y - h * 60) || null;
  }
  return null;
}

// 三联动字段，按「最近编辑」记录优先级
const FR_LINKED = ["actStart", "actEnd", "hours"];

// ---- 现场记录专用 日期+时间 选择器 ----
// 复用全站 APSDatePicker 的日历视觉（.apsdp-* 样式），但因本页字段是
// 「MM-DD HH:MM」日期+时间，原生只认 YYYY-MM-DD，故自带一套日历弹层并补一行时间。
const FR_WEEK = ["一", "二", "三", "四", "五", "六", "日"];
const FR_MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];
const frPad2 = n => String(n).padStart(2, "0");
function frParseDT(s) {
  const m = /^\s*(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?\s*$/.exec(s || "");
  if (!m) return {
    mo: null,
    d: null,
    hh: null,
    mm: null
  };
  return {
    mo: +m[1],
    d: +m[2],
    hh: m[3] != null ? +m[3] : null,
    mm: m[4] != null ? +m[4] : null
  };
}
function frFmtDT(mo, d, hh, mm) {
  if (mo == null || d == null) return "";
  let s = frPad2(mo) + "-" + frPad2(d);
  if (hh != null && mm != null) s += " " + frPad2(hh) + ":" + frPad2(mm);
  return s;
}
const FR_ICON_CAL = /*#__PURE__*/React.createElement("svg", {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: "2",
  strokeLinecap: "round",
  strokeLinejoin: "round"
}, /*#__PURE__*/React.createElement("rect", {
  x: "4",
  y: "5",
  width: "16",
  height: "16",
  rx: "2.5"
}), /*#__PURE__*/React.createElement("path", {
  d: "M4 10h16M8 3v4M16 3v4"
}));
const FR_ICON_PREV = /*#__PURE__*/React.createElement("svg", {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: "2.2",
  strokeLinecap: "round",
  strokeLinejoin: "round"
}, /*#__PURE__*/React.createElement("polyline", {
  points: "14 6 8 12 14 18"
}));
const FR_ICON_NEXT = /*#__PURE__*/React.createElement("svg", {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: "2.2",
  strokeLinecap: "round",
  strokeLinejoin: "round"
}, /*#__PURE__*/React.createElement("polyline", {
  points: "10 6 16 12 10 18"
}));

// 自定义时间选择器（小时 / 分钟两列）。原生 <input type=time> 的下拉用浏览器
// 自带样式（亮蓝方块），与全站日历不一致且无法用 CSS 接管，故改为令牌化两列选择。
const FR_ICON_CLOCK = /*#__PURE__*/React.createElement("svg", {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: "2",
  strokeLinecap: "round",
  strokeLinejoin: "round"
}, /*#__PURE__*/React.createElement("circle", {
  cx: "12",
  cy: "12",
  r: "9"
}), /*#__PURE__*/React.createElement("path", {
  d: "M12 7v5l3 2"
}));
function FRTimePicker({
  value,
  onChange
}) {
  const {
    useState,
    useRef,
    useEffect,
    useLayoutEffect
  } = React;
  const wrapRef = useRef(null);
  const hRef = useRef(null);
  const mRef = useRef(null);
  const [open, setOpen] = useState(false);
  const tm = /^(\d{1,2}):(\d{2})$/.exec(value || "");
  const hh = tm ? +tm[1] : null;
  const mm = tm ? +tm[2] : null;
  useEffect(() => {
    if (!open) return;
    const onDown = e => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown, true);
    return () => document.removeEventListener("mousedown", onDown, true);
  }, [open]);
  useLayoutEffect(() => {
    if (!open) return;
    const center = (col, idx) => {
      if (!col) return;
      const el = col.children[idx];
      if (el) col.scrollTop = el.offsetTop - col.clientHeight / 2 + el.clientHeight / 2;
    };
    center(hRef.current, hh == null ? 8 : hh);
    center(mRef.current, mm == null ? 0 : mm);
  }, [open]);
  const pick = (nh, nm) => onChange(frPad2(nh) + ":" + frPad2(nm));
  const hours = Array.from({
    length: 24
  }, (_, i) => i);
  const mins = Array.from({
    length: 60
  }, (_, i) => i);
  return /*#__PURE__*/React.createElement("span", {
    ref: wrapRef,
    className: "fr-tp"
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "fr-tp-btn" + (open ? " is-open" : ""),
    onClick: () => setOpen(o => !o)
  }, /*#__PURE__*/React.createElement("span", {
    className: "fr-tp-val" + (value ? "" : " is-empty")
  }, value || "选择时间"), /*#__PURE__*/React.createElement("span", {
    className: "fr-tp-ic"
  }, FR_ICON_CLOCK)), open ? /*#__PURE__*/React.createElement("div", {
    className: "fr-tp-pop",
    role: "dialog",
    "aria-label": "\u9009\u62E9\u65F6\u95F4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fr-tp-col",
    ref: hRef
  }, hours.map(h => /*#__PURE__*/React.createElement("button", {
    key: h,
    type: "button",
    className: "fr-tp-opt" + (h === hh ? " is-on" : ""),
    onClick: () => pick(h, mm == null ? 0 : mm)
  }, frPad2(h)))), /*#__PURE__*/React.createElement("div", {
    className: "fr-tp-col",
    ref: mRef
  }, mins.map(m => /*#__PURE__*/React.createElement("button", {
    key: m,
    type: "button",
    className: "fr-tp-opt" + (m === mm ? " is-on" : ""),
    onClick: () => pick(hh == null ? 8 : hh, m)
  }, frPad2(m))))) : null);
}
function FRDateTimeField({
  value,
  onChange,
  need
}) {
  const {
    useState,
    useRef,
    useEffect,
    useLayoutEffect
  } = React;
  const fieldRef = useRef(null);
  const popRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [showMonths, setShowMonths] = useState(false);
  const [pos, setPos] = useState({
    top: 0,
    left: 0,
    flipUp: false
  });
  const today = new Date();
  const REF_YEAR = today.getFullYear();
  const parsed = frParseDT(value);
  const [view, setView] = useState(() => ({
    y: REF_YEAR,
    m: parsed.mo != null ? parsed.mo - 1 : today.getMonth()
  }));
  useEffect(() => {
    if (!open) return;
    const p = frParseDT(value);
    setView({
      y: REF_YEAR,
      m: p.mo != null ? p.mo - 1 : today.getMonth()
    });
    setShowMonths(false);
  }, [open]);
  useLayoutEffect(() => {
    if (!open) return;
    const f = fieldRef.current;
    if (f) {
      const r = f.getBoundingClientRect();
      const pw = 268,
        ph = 374;
      const vw = document.documentElement.clientWidth,
        vh = window.innerHeight;
      let left = r.left;
      if (left + pw > vw - 8) left = vw - pw - 8;
      if (left < 8) left = 8;
      const flipUp = r.bottom + 6 + ph > vh && r.top - 6 - ph > 0;
      setPos({
        top: flipUp ? r.top - 6 - ph : r.bottom + 6,
        left,
        flipUp
      });
    }
    const onScroll = e => {
      // 时间选择器在列内滚动（含程序化 scrollTop 居中）会冒泡到此捕获监听，
      // 不能因此把整个日历关掉——仅当滚动发生在弹层之外时才收起。
      if (e && e.target && e.target.nodeType && popRef.current && popRef.current.contains(e.target)) return;
      setOpen(false);
    };
    const onDown = e => {
      if (fieldRef.current && fieldRef.current.contains(e.target)) return;
      if (popRef.current && popRef.current.contains(e.target)) return;
      setOpen(false);
    };
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onScroll, true);
    document.addEventListener("mousedown", onDown, true);
    return () => {
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onScroll, true);
      document.removeEventListener("mousedown", onDown, true);
    };
  }, [open]);
  const step = dir => setView(v => {
    let m = v.m + dir,
      y = v.y;
    if (m < 0) {
      m = 11;
      y--;
    } else if (m > 11) {
      m = 0;
      y++;
    }
    return {
      y,
      m
    };
  });
  const pickDay = (mo, d) => {
    const p = frParseDT(value);
    onChange(frFmtDT(mo, d, p.hh != null ? p.hh : 8, p.mm != null ? p.mm : 0));
  };
  const setTime = t => {
    const tm = /^(\d{1,2}):(\d{2})$/.exec(t || "");
    const p = frParseDT(value);
    let mo = p.mo,
      d = p.d;
    if (mo == null) {
      mo = today.getMonth() + 1;
      d = today.getDate();
    }
    onChange(tm ? frFmtDT(mo, d, +tm[1], +tm[2]) : frFmtDT(mo, d, null, null));
  };
  const clear = () => {
    onChange("");
    setOpen(false);
  };
  const pickToday = () => pickDay(today.getMonth() + 1, today.getDate());

  // 42 格日历（周一起），末行整周在下月则裁掉
  const first = new Date(view.y, view.m, 1);
  const offset = (first.getDay() + 6) % 7;
  const start = new Date(view.y, view.m, 1 - offset);
  const tY = today.getFullYear(),
    tMo = today.getMonth() + 1,
    tD = today.getDate();
  let allCells = [];
  for (let i = 0; i < 42; i++) {
    const cur = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
    const out = cur.getMonth() !== view.m;
    allCells.push({
      day: cur.getDate(),
      mo: cur.getMonth() + 1,
      d: cur.getDate(),
      out,
      wknd: cur.getDay() === 0 || cur.getDay() === 6,
      isToday: cur.getFullYear() === tY && cur.getMonth() === tMo - 1 && cur.getDate() === tD,
      isSel: !out && view.y === REF_YEAR && parsed.mo === cur.getMonth() + 1 && parsed.d === cur.getDate()
    });
  }
  const cells = allCells.slice(35).every(c => c.out) ? allCells.slice(0, 35) : allCells;
  const timeVal = parsed.hh != null && parsed.mm != null ? frPad2(parsed.hh) + ":" + frPad2(parsed.mm) : "";
  const popover = /*#__PURE__*/React.createElement("div", {
    ref: popRef,
    className: "apsdp-pop is-anim" + (showMonths ? " show-months" : "") + (pos.flipUp ? " flip-up" : ""),
    role: "dialog",
    "aria-label": "\u9009\u62E9\u65E5\u671F\u4E0E\u65F6\u95F4",
    style: {
      position: "fixed",
      top: pos.top,
      left: pos.left,
      width: 268
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "apsdp-head"
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "apsdp-nav",
    "aria-label": "\u4E0A\u4E2A\u6708",
    onClick: () => step(-1)
  }, FR_ICON_PREV), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "apsdp-title",
    onClick: () => setShowMonths(s => !s)
  }, /*#__PURE__*/React.createElement("span", {
    className: "apsdp-title-txt"
  }, view.y, " \u5E74 ", view.m + 1, " \u6708"), /*#__PURE__*/React.createElement("span", {
    className: "caret"
  })), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "apsdp-nav",
    "aria-label": "\u4E0B\u4E2A\u6708",
    onClick: () => step(1)
  }, FR_ICON_NEXT)), /*#__PURE__*/React.createElement("div", {
    className: "apsdp-week"
  }, FR_WEEK.map((w, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "apsdp-wd" + (i >= 5 ? " is-weekend" : "")
  }, w))), /*#__PURE__*/React.createElement("div", {
    className: "apsdp-grid"
  }, cells.map((c, i) => /*#__PURE__*/React.createElement("button", {
    key: i,
    type: "button",
    className: "apsdp-day" + (c.out ? " is-out" : "") + (c.wknd ? " is-weekend" : "") + (c.isToday ? " is-today" : "") + (c.isSel ? " is-selected" : ""),
    onClick: () => pickDay(c.mo, c.d)
  }, c.day))), /*#__PURE__*/React.createElement("div", {
    className: "apsdp-months"
  }, FR_MONTHS.map((mn, i) => /*#__PURE__*/React.createElement("button", {
    key: i,
    type: "button",
    className: "apsdp-month" + (i === view.m ? " is-current" : ""),
    onClick: () => {
      setView(v => ({
        ...v,
        m: i
      }));
      setShowMonths(false);
    }
  }, mn))), /*#__PURE__*/React.createElement("div", {
    className: "apsdp-foot"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fr-dt-timewrap"
  }, /*#__PURE__*/React.createElement("span", {
    className: "fr-dt-timelbl"
  }, "\u65F6\u95F4"), /*#__PURE__*/React.createElement(FRTimePicker, {
    value: timeVal,
    onChange: setTime
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      gap: 4,
      marginLeft: "auto"
    }
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "apsdp-link clear",
    onClick: clear
  }, "\u6E05\u9664"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "apsdp-link today",
    onClick: pickToday
  }, "\u4ECA\u5929"))));
  return /*#__PURE__*/React.createElement("span", {
    ref: fieldRef,
    className: "apsdp-field" + (need ? " is-need" : "") + (open ? " is-open" : ""),
    style: {
      height: 32
    }
  }, /*#__PURE__*/React.createElement("input", {
    className: "apsdp-input",
    style: {
      width: 104
    },
    value: value,
    placeholder: "MM-DD HH:MM",
    autoComplete: "off",
    onChange: e => onChange(e.target.value),
    onFocus: () => setOpen(true)
  }), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "apsdp-trigger",
    "aria-label": "\u6253\u5F00\u65E5\u5386",
    onMouseDown: e => e.preventDefault(),
    onClick: () => setOpen(o => !o)
  }, FR_ICON_CAL), open ? ReactDOM.createPortal(popover, document.body) : null);
}

// 批量导入实际工时 —— 弹出式卡片，单步直接导入：不做检查预览、不做二次确认写入。
function FieldHoursImportModal({
  wiz,
  onClose,
  onDone
}) {
  const {
    Button
  } = window.APSDesignSystem_edbc5d;
  const B = window.BD;
  const Field = B && B.Field;
  const modeOptions = wiz && wiz.modeOptions || [{
    value: "overwrite",
    label: "覆盖回填（按表格重填）"
  }, {
    value: "fill",
    label: "只补空缺（不动已填）"
  }];
  const [mode, setMode] = React.useState(modeOptions[0].value);
  const [fileName, setFileName] = React.useState("");
  React.useEffect(() => {
    const onKey = e => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);
  const doImport = () => {
    if (!fileName) return;
    onDone(fileName + " · 回填 4 道工序（新增 1 / 更新 3）");
  };
  const modeSelect = /*#__PURE__*/React.createElement("select", {
    className: "bd-select",
    value: mode,
    onChange: e => setMode(e.target.value)
  }, modeOptions.map(o => /*#__PURE__*/React.createElement("option", {
    key: o.value,
    value: o.value
  }, o.label)));
  return /*#__PURE__*/React.createElement("div", {
    className: "bd-modal-backdrop",
    onClick: onClose
  }, /*#__PURE__*/React.createElement("div", {
    className: "bd-modal",
    role: "dialog",
    "aria-modal": "true",
    style: {
      width: "min(560px, 100%)"
    },
    onClick: e => e.stopPropagation()
  }, /*#__PURE__*/React.createElement("div", {
    className: "bd-modal-head",
    style: {
      display: "flex",
      alignItems: "flex-start",
      gap: 12,
      padding: "16px 18px 14px",
      borderBottom: "1px solid var(--ui-border)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 38,
      height: 38,
      borderRadius: 10,
      background: "var(--ui-primary-soft)",
      color: "var(--ui-primary)",
      display: "grid",
      placeItems: "center",
      flex: "none"
    },
    "aria-hidden": "true"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 24 24",
    width: "20",
    height: "20",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M12 4v12m0 0l-4-4m4 4l4-4"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M5 18v2h14v-2"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("h4", {
    style: {
      margin: 0,
      fontSize: 16,
      fontWeight: 600
    }
  }, wiz && wiz.title || "批量导入实际工时"), /*#__PURE__*/React.createElement("div", {
    className: "muted",
    style: {
      fontSize: 12.5,
      marginTop: 2,
      lineHeight: 1.5
    }
  }, "\u6309\u300C\u6279\u6B21\u53F7 + \u5DE5\u5E8F\u300D\u5339\u914D\u6392\u4EA7\u5DE5\u5E8F\u540E\u56DE\u586B\uFF1B\u5339\u914D\u4E0D\u5230\u6216\u65F6\u95F4\u975E\u6CD5\u7684\u884C\u4E0D\u5199\u5165\u3002")), /*#__PURE__*/React.createElement("button", {
    className: "bd-modal-x",
    onClick: onClose,
    "aria-label": "\u5173\u95ED",
    style: {
      flex: "none",
      width: 30,
      height: 30,
      border: "none",
      background: "transparent",
      color: "var(--ui-muted)",
      cursor: "pointer",
      borderRadius: 8,
      display: "grid",
      placeItems: "center",
      fontSize: 18,
      lineHeight: 1
    }
  }, "\xD7")), /*#__PURE__*/React.createElement("div", {
    className: "bd-modal-body",
    style: {
      padding: "16px 18px",
      color: "var(--ui-text)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      padding: "12px 14px",
      border: "1px solid var(--ui-border)",
      borderRadius: 10,
      background: "var(--ui-surface-muted)",
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 32,
      height: 32,
      borderRadius: 8,
      background: "var(--ui-card-bg)",
      border: "1px solid var(--ui-border)",
      display: "grid",
      placeItems: "center",
      color: "var(--ui-success)",
      flex: "none"
    },
    "aria-hidden": "true"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 24 24",
    width: "17",
    height: "17",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M7 3h7l5 5v13H7z"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M14 3v5h5"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M9.5 13l1.8 1.8L15 11"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      fontWeight: 600
    }
  }, "\u56DE\u586B\u8868\u6A21\u677F.xlsx"), /*#__PURE__*/React.createElement("div", {
    className: "muted",
    style: {
      fontSize: 11.5,
      marginTop: 2
    }
  }, "\u6279\u6B21\u53F7 + \u5DE5\u5E8F + \u5B9E\u9645\u5F00\u5DE5 / \u5B8C\u5DE5 / \u5DE5\u65F6\uFF0C\u6309\u6A21\u677F\u586B\u5199\u540E\u4E0A\u4F20")), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "sm"
  }, "\u4E0B\u8F7D\u6A21\u677F")), /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 14
    }
  }, Field ? /*#__PURE__*/React.createElement(Field, {
    label: "\u5BFC\u5165\u6A21\u5F0F",
    hint: "\u51B3\u5B9A\u8868\u683C\u4E0E\u73B0\u6709\u5B9E\u9645\u51B2\u7A81\u65F6\u600E\u4E48\u529E\uFF1A\u662F\u4E00\u5F8B\u4EE5\u8868\u683C\u4E3A\u51C6\uFF0C\u8FD8\u662F\u53EA\u8865\u7A7A\u3001\u4E0D\u52A8\u5DF2\u586B\u7684\u3002"
  }, modeSelect) : /*#__PURE__*/React.createElement("label", {
    style: {
      display: "block"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: "block",
      fontSize: 12.5,
      fontWeight: 600,
      marginBottom: 6
    }
  }, "\u5BFC\u5165\u6A21\u5F0F"), modeSelect)), /*#__PURE__*/React.createElement("div", {
    className: "bd-upload"
  }, /*#__PURE__*/React.createElement("input", {
    type: "file",
    accept: ".xlsx",
    "aria-label": "\u9009\u62E9 Excel \u6587\u4EF6",
    onChange: e => setFileName(e.target.files && e.target.files[0] ? e.target.files[0].name : "")
  }), /*#__PURE__*/React.createElement("span", {
    className: "up-file"
  }, fileName ? fileName : /*#__PURE__*/React.createElement("span", {
    className: "muted"
  }, "\u4EC5\u652F\u6301 .xlsx\uFF0C\u8868\u5934\u4E0D\u8981\u6539\uFF0C\u53EA\u8BFB\u7B2C\u4E00\u4E2A\u5DE5\u4F5C\u8868"))), /*#__PURE__*/React.createElement("p", {
    className: "muted",
    style: {
      fontSize: 12,
      lineHeight: 1.6,
      margin: "13px 2px 0"
    }
  }, "\u4E0A\u4F20\u540E", /*#__PURE__*/React.createElement("strong", {
    style: {
      color: "var(--ui-text)",
      fontWeight: 600
    }
  }, "\u76F4\u63A5\u56DE\u586B"), "\uFF0C\u6309\u6240\u9009\u6A21\u5F0F\u5199\u5165\uFF1B\u5339\u914D\u4E0D\u5230\u300C\u6279\u6B21\u53F7 + \u5DE5\u5E8F\u300D\u6216\u65F6\u95F4\u975E\u6CD5\u7684\u884C\u81EA\u52A8\u8DF3\u8FC7\u3002")), /*#__PURE__*/React.createElement("div", {
    className: "bd-modal-foot"
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "md",
    onClick: onClose
  }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    size: "md",
    disabled: !fileName,
    onClick: doImport
  }, "\u5BFC\u5165"))));
}
function FieldRecordScreen() {
  const {
    Panel,
    Badge,
    Button,
    Table
  } = window.APSDesignSystem_edbc5d;
  const D = window.APSDetail;
  const B = window.BD;
  const [wiz, setWiz] = React.useState(null);
  // 三联动字段的「最近编辑」顺序，id → [键名，最新在前]。填任意两项后，
  // 第三项（最旧的那项）自动推算；后续修改以最新填写为准，只重算一次，不成环。
  const orderRef = React.useRef({});

  // 每行 = 排产计划里的一道工序。plan* 来自排产结果（只读），act* / hours 待回填。
  const [rows, setRows] = React.useState([{
    id: "o1",
    batch: "B202605-019",
    op: "50 检验",
    res: "M-12 / 王五",
    type: "检验",
    planStart: "06-11 08:00",
    planEnd: "06-11 09:30",
    actStart: "06-11 08:05",
    actEnd: "06-11 09:18",
    hours: "1.2"
  }, {
    id: "o2",
    batch: "B202605-019",
    op: "40 组装",
    res: "M-07 / 李四",
    type: "组装",
    planStart: "06-11 06:30",
    planEnd: "06-11 08:30",
    actStart: "06-11 06:35",
    actEnd: "06-11 08:40",
    hours: "2.1"
  }, {
    id: "o3",
    batch: "B202605-020",
    op: "10 下料",
    res: "M-18 / 赵六",
    type: "下料",
    planStart: "06-11 07:30",
    planEnd: "06-11 08:15",
    actStart: "06-11 07:40",
    actEnd: "06-11 08:25",
    hours: "0.8"
  }, {
    id: "o4",
    batch: "B202605-018",
    op: "30 精加工",
    res: "M-03 / 张三",
    type: "精加工",
    planStart: "06-11 08:00",
    planEnd: "06-11 11:00",
    actStart: "06-11 08:10",
    actEnd: "",
    hours: ""
  }, {
    id: "o5",
    batch: "B202605-021",
    op: "20 预加工",
    res: "M-05 / 李四",
    type: "预加工",
    planStart: "06-11 09:00",
    planEnd: "06-11 11:00",
    actStart: "06-11 09:05",
    actEnd: "06-11 11:20",
    hours: ""
  }, {
    id: "o6",
    batch: "B202605-024",
    op: "30 精加工",
    res: "M-03 / 张三",
    type: "精加工",
    planStart: "06-11 11:30",
    planEnd: "06-11 14:30",
    actStart: "",
    actEnd: "",
    hours: ""
  }, {
    id: "o7",
    batch: "B202605-022",
    op: "10 下料",
    res: "M-18 / 赵六",
    type: "下料",
    planStart: "06-11 13:00",
    planEnd: "06-11 13:50",
    actStart: "",
    actEnd: "",
    hours: ""
  }, {
    id: "o8",
    batch: "B202605-017",
    op: "50 检验",
    res: "M-12 / 王五",
    type: "检验",
    planStart: "06-11 14:00",
    planEnd: "06-11 15:30",
    actStart: "",
    actEnd: "",
    hours: ""
  }]);
  const [filter, setFilter] = React.useState("全部");
  const [q, setQ] = React.useState("");
  // 回填改动未保存标记 + 上次保存时间（给计划员明确反馈）
  const [dirty, setDirty] = React.useState(false);
  const [savedAt, setSavedAt] = React.useState(null);
  const statusOf = r => r.actStart && r.actEnd && r.hours ? "done" : r.actStart ? "doing" : "todo";
  const setField = (id, key, val) => {
    // 联动字段：先把本次编辑的键提到最近，再重算最旧的那项。
    if (FR_LINKED.includes(key)) {
      let ord = orderRef.current[id] ? orderRef.current[id].slice() : [];
      ord = [key, ...ord.filter(k => k !== key)];
      for (const k of FR_LINKED) if (!ord.includes(k)) ord.push(k);
      orderRef.current[id] = ord;
    }
    setRows(rs => rs.map(r => {
      if (r.id !== id) return r;
      const nr = {
        ...r,
        [key]: val
      };
      if (FR_LINKED.includes(key)) {
        const stale = orderRef.current[id][2]; // 最旧的一项
        const d = frDerive(stale, nr);
        if (d != null) nr[stale] = d; // 两项均有效才推算，否则保留
      }
      return nr;
    }));
    setDirty(true);
  };
  const fillPlan = r => {
    delete orderRef.current[r.id];
    setRows(rs => rs.map(x => x.id === r.id ? {
      ...x,
      actStart: x.planStart,
      actEnd: x.planEnd,
      hours: frCalcHours(x.planStart, x.planEnd)
    } : x));
    setDirty(true);
    D && D.toast(r.batch + " · " + r.op + " 已按计划回填实际（示例，可再改）");
  };
  const clearRow = r => {
    delete orderRef.current[r.id];
    setRows(rs => rs.map(x => x.id === r.id ? {
      ...x,
      actStart: "",
      actEnd: "",
      hours: ""
    } : x));
    setDirty(true);
  };
  const saveRecords = () => {
    setDirty(false);
    const t = new Date();
    setSavedAt(String(t.getHours()).padStart(2, "0") + ":" + String(t.getMinutes()).padStart(2, "0"));
    D && D.toast("已保存 " + done + " 道已回填工序的实际开工 / 完工 / 工时（示例）。");
  };

  // 顶部进度统计（随回填实时变化）
  const todo = rows.filter(r => statusOf(r) === "todo").length;
  const doing = rows.filter(r => statusOf(r) === "doing").length;
  const done = rows.filter(r => statusOf(r) === "done").length;
  const hoursSum = rows.reduce((s, r) => s + (parseFloat(r.hours) || 0), 0);
  const devs = rows.filter(r => statusOf(r) === "done").map(r => frParseT(r.actEnd) - frParseT(r.planEnd)).filter(d => !isNaN(d));
  const avgDev = devs.length ? devs.reduce((a, b) => a + b, 0) / devs.length : null;
  const stats = [{
    sev: "warning",
    label: "待回填",
    value: todo,
    helper: "计划已排，等待录入实际",
    chip: ["warning", todo ? "需录入" : "已清空"]
  }, {
    sev: "notice",
    label: "进行中",
    value: doing,
    helper: "已填开工，待补完工 / 工时",
    chip: ["notice", "在制"]
  }, {
    sev: "ok",
    label: "已回填",
    value: done,
    helper: "开工 / 完工 / 工时齐全",
    chip: ["success", "可校准"]
  }, {
    sev: "notice",
    label: "本期工时合计",
    value: hoursSum.toFixed(1),
    helper: "已回填工序工时之和 · h",
    chip: ["secondary", "实绩"]
  }, {
    sev: "ok",
    label: "平均完工偏差",
    value: frFmtMin(avgDev),
    helper: "实际完工相对计划",
    chip: ["secondary", avgDev == null ? "暂无样本" : "vs 计划"]
  }];
  const codeLink = code => {
    if (D && D.has(code)) return /*#__PURE__*/React.createElement("a", {
      href: "#",
      onClick: e => {
        e.preventDefault();
        D.open(code);
      },
      style: {
        color: "var(--ui-primary)",
        fontWeight: 700,
        fontVariantNumeric: "tabular-nums",
        textDecoration: "none"
      }
    }, code);
    return /*#__PURE__*/React.createElement("span", {
      style: {
        fontWeight: 700,
        fontVariantNumeric: "tabular-nums"
      }
    }, code);
  };
  const FILTERS = [{
    k: "全部",
    n: rows.length
  }, {
    k: "待回填",
    n: todo
  }, {
    k: "进行中",
    n: doing
  }, {
    k: "已回填",
    n: done
  }];
  const STATE_BY_LABEL = {
    "待回填": "todo",
    "进行中": "doing",
    "已回填": "done"
  };
  const shown = rows.filter(r => (filter === "全部" || statusOf(r) === STATE_BY_LABEL[filter]) && (!q || (r.batch + r.op + r.res).toLowerCase().includes(q.toLowerCase())));

  // 批量回填：复用基础资料各页同款 Excel 三步流（ExcelWizard），按「批次号 + 工序」
  // 匹配排产工序后回填实际。导入 / 导出入口收到 Panel 头部，不再单独占一整块。
  const importCards = [{
    title: "批量导入实际工时",
    maintainLabel: "批量导入工时",
    exportLabel: "导出回填表",
    desc: "现场实际常先在 Excel 里汇总：按模板一次回填多道工序的实际开工 / 完工 / 工时，系统按「批次号 + 工序」匹配排产计划，匹配不到或时间非法的行不写入。",
    wizard: {
      kind: "field_hours",
      title: "批量导入实际工时",
      strict: true,
      desc: "按模板上传现场记录（批次号 + 工序 + 实际开工 / 完工 / 工时），按「批次号 + 工序」匹配排产工序后回填；匹配不到或时间非法的行计为错误，不写入。",
      modeOptions: [{
        value: "overwrite",
        label: "覆盖回填（按表格重填）"
      }, {
        value: "fill",
        label: "只补空缺（不动已填）"
      }],
      sampleRows: [{
        row_num: 2,
        status: "update",
        message: "匹配 B202605-019 · 50 检验，回填开工 / 完工 / 工时",
        data: {
          批次号: "B202605-019",
          工序: "50 检验",
          实际开工: "06-11 08:05",
          实际完工: "06-11 09:18",
          工时: 1.2
        }
      }, {
        row_num: 3,
        status: "update",
        message: "匹配 B202605-019 · 40 组装，更新工时",
        data: {
          批次号: "B202605-019",
          工序: "40 组装",
          工时: 2.1
        }
      }, {
        row_num: 4,
        status: "new",
        message: "匹配 B202605-021 · 20 预加工，首次回填",
        data: {
          批次号: "B202605-021",
          工序: "20 预加工",
          实际开工: "06-11 09:05",
          实际完工: "06-11 11:20"
        }
      }, {
        row_num: 5,
        status: "skip",
        message: "模式为「只补未填工序」，该工序已填，跳过",
        data: {
          批次号: "B202605-018",
          工序: "30 精加工"
        }
      }, {
        row_num: 6,
        status: "error",
        message: "批次号 + 工序在当前排产计划中不存在，无法匹配",
        data: {
          批次号: "B202605-099",
          工序: "10 下料"
        }
      }, {
        row_num: 7,
        status: "error",
        message: "实际完工早于实际开工，时间非法",
        data: {
          批次号: "B202605-020",
          工序: "10 下料",
          实际开工: "06-11 08:25",
          实际完工: "06-11 07:40"
        }
      }]
    }
  }];
  const timeInput = (r, key) => /*#__PURE__*/React.createElement(FRDateTimeField, {
    value: r[key],
    need: !r[key],
    onChange: v => setField(r.id, key, v)
  });
  const cols = [{
    key: "batch",
    title: "批次 / 工序",
    nowrap: true,
    render: r => /*#__PURE__*/React.createElement("div", {
      className: "fr-cellname"
    }, /*#__PURE__*/React.createElement("span", null, codeLink(r.batch)), /*#__PURE__*/React.createElement("span", {
      className: "fr-sub"
    }, r.op, " \xB7 ", r.res))
  }, {
    key: "plan",
    title: "计划 开工 → 完工",
    nowrap: true,
    sortFacets: [{
      key: "ps",
      label: "开工",
      value: r => {
        const t = frParseT(r.planStart);
        return isNaN(t) ? Infinity : t;
      }
    }, {
      key: "pe",
      label: "完工",
      value: r => {
        const t = frParseT(r.planEnd);
        return isNaN(t) ? Infinity : t;
      }
    }],
    filterFacets: [{
      key: "ps",
      label: "开工",
      value: r => r.planStart
    }, {
      key: "pe",
      label: "完工",
      value: r => r.planEnd
    }],
    render: r => /*#__PURE__*/React.createElement("span", {
      className: "fr-plan"
    }, /*#__PURE__*/React.createElement("span", {
      className: "lab"
    }, "\u5F00\u5DE5"), /*#__PURE__*/React.createElement("span", {
      className: "val"
    }, r.planStart), /*#__PURE__*/React.createElement("span", {
      className: "lab"
    }, "\u5B8C\u5DE5"), /*#__PURE__*/React.createElement("span", {
      className: "val"
    }, r.planEnd))
  }, {
    key: "as",
    title: "实际开工",
    nowrap: true,
    sortValue: r => {
      const t = frParseT(r.actStart);
      return isNaN(t) ? Infinity : t;
    },
    filterValue: r => r.actStart || "",
    render: r => timeInput(r, "actStart")
  }, {
    key: "ae",
    title: "实际完工",
    nowrap: true,
    sortValue: r => {
      const t = frParseT(r.actEnd);
      return isNaN(t) ? Infinity : t;
    },
    filterValue: r => r.actEnd || "",
    render: r => timeInput(r, "actEnd")
  }, {
    key: "hours",
    title: "工时 (h)",
    nowrap: true,
    render: r => /*#__PURE__*/React.createElement("span", {
      className: "fr-hcell"
    }, /*#__PURE__*/React.createElement("input", {
      className: "bd-cell-input num",
      style: {
        width: 64
      },
      value: r.hours,
      placeholder: "\u2014",
      inputMode: "decimal",
      onChange: e => setField(r.id, "hours", e.target.value)
    }))
  }, {
    key: "state",
    title: "状态",
    nowrap: true,
    sortValue: r => ({
      todo: 0,
      doing: 1,
      done: 2
    })[statusOf(r)],
    filterValue: r => FR_STATE_META[statusOf(r)].label,
    render: r => {
      const m = FR_STATE_META[statusOf(r)];
      return /*#__PURE__*/React.createElement(Badge, {
        tone: m.tone,
        dot: true
      }, m.label);
    }
  }, {
    key: "act",
    title: "操作",
    nowrap: true,
    render: r => /*#__PURE__*/React.createElement("div", {
      className: "bd-cell-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "sm",
      onClick: () => fillPlan(r)
    }, "\u6309\u8BA1\u5212\u586B"), r.actStart || r.actEnd || r.hours ? /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      size: "sm",
      onClick: () => clearRow(r)
    }, "\u6E05\u9664") : null)
  }];
  return /*#__PURE__*/React.createElement(Panel, {
    title: "\u73B0\u573A\u8BB0\u5F55",
    description: "\u6392\u4EA7\u8BA1\u5212\u5BF9\u5E94\u5DE5\u5E8F\u7684\u5B9E\u9645\u5F00\u5DE5\u3001\u5B8C\u5DE5\u65F6\u95F4\u4E0E\u5DE5\u65F6\uFF0C\u7531\u8BA1\u5212\u5458 / \u5DE5\u827A\u5458\u56DE\u586B \u2014\u2014 \u4E0D\u63A5 MES\uFF0C\u975E\u5B9E\u65F6\u73B0\u573A\u72B6\u6001\u3002\u8BA1\u5212\u5217\u53EA\u8BFB\uFF0C\u53F3\u4FA7\u4E09\u5217\u5C31\u5730\u586B\u5199\uFF1B\u56DE\u586B\u7ED3\u679C\u7528\u4E8E\u5DE5\u65F6\u5B9A\u989D\u6821\u51C6\u4E0E\u6267\u884C\u590D\u76D8\u3002"
  }, /*#__PURE__*/React.createElement("div", {
    className: "fr-stats"
  }, stats.map((s, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "ds-card sev-" + s.sev
  }, /*#__PURE__*/React.createElement("div", {
    className: "ds-label"
  }, s.label), /*#__PURE__*/React.createElement("div", {
    className: "ds-value"
  }, s.value), /*#__PURE__*/React.createElement("div", {
    className: "ds-helper"
  }, s.helper), /*#__PURE__*/React.createElement(Badge, {
    tone: s.chip[0]
  }, s.chip[1])))), /*#__PURE__*/React.createElement("div", {
    className: "fr-records-tools",
    style: {
      marginTop: 4
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "seg"
  }, FILTERS.map(f => /*#__PURE__*/React.createElement("button", {
    key: f.k,
    className: "seg-btn" + (filter === f.k ? " on" : ""),
    onClick: () => setFilter(f.k)
  }, f.k, /*#__PURE__*/React.createElement("span", {
    style: {
      marginLeft: 6,
      opacity: .7,
      fontVariantNumeric: "tabular-nums"
    }
  }, f.n)))), /*#__PURE__*/React.createElement("div", {
    className: "tool-right",
    style: {
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("input", {
    className: "tool-input",
    placeholder: "\u641C\u7D22\u6279\u6B21 / \u5DE5\u5E8F / \u8D44\u6E90\u2026",
    value: q,
    onChange: e => setQ(e.target.value)
  }), /*#__PURE__*/React.createElement(Badge, {
    tone: "secondary"
  }, "\u5171 ", shown.length, " \u9053\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 7,
      fontSize: 12,
      color: dirty ? "var(--ui-warning-text)" : "var(--ui-muted)",
      whiteSpace: "nowrap"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 7,
      height: 7,
      borderRadius: "50%",
      background: dirty ? "var(--ui-warning)" : "var(--ui-success)",
      flex: "none"
    }
  }), dirty ? "有未保存改动" : savedAt ? "已保存 " + savedAt : "全部已保存"), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 1,
      alignSelf: "stretch",
      minHeight: 20,
      background: "var(--ui-border)",
      margin: "0 2px",
      flex: "none"
    }
  }), /*#__PURE__*/React.createElement("div", {
    className: "fr-btngroup"
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "sm",
    leadingIcon: /*#__PURE__*/React.createElement("svg", {
      viewBox: "0 0 24 24",
      width: "15",
      height: "15",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "1.7",
      strokeLinecap: "round",
      strokeLinejoin: "round"
    }, /*#__PURE__*/React.createElement("path", {
      d: "M12 15V3m0 0l-4 4m4-4l4 4"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"
    })),
    style: {
      borderTopRightRadius: 0,
      borderBottomRightRadius: 0
    },
    onClick: () => D && D.toast("已导出回填表模板（批次号 + 工序 + 实际开工 / 完工 / 工时），可在 Excel 汇总后回传。")
  }, "\u5BFC\u51FA\u56DE\u586B\u8868"), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "sm",
    leadingIcon: /*#__PURE__*/React.createElement("svg", {
      viewBox: "0 0 24 24",
      width: "15",
      height: "15",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "1.7",
      strokeLinecap: "round",
      strokeLinejoin: "round"
    }, /*#__PURE__*/React.createElement("path", {
      d: "M12 3v12m0 0l-4-4m4 4l4-4"
    }), /*#__PURE__*/React.createElement("path", {
      d: "M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"
    })),
    style: {
      borderTopLeftRadius: 0,
      borderBottomLeftRadius: 0,
      marginLeft: -1
    },
    onClick: () => setWiz(importCards[0].wizard)
  }, "\u6279\u91CF\u5BFC\u5165\u5DE5\u65F6")), /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    size: "sm",
    onClick: saveRecords
  }, "\u4FDD\u5B58\u56DE\u586B"))), /*#__PURE__*/React.createElement("div", {
    className: "bd-table-scroll"
  }, /*#__PURE__*/React.createElement(Table, {
    columns: cols,
    rows: shown,
    rowKey: "id"
  })), /*#__PURE__*/React.createElement("p", {
    style: {
      marginTop: 12,
      fontSize: 12.5,
      color: "var(--ui-muted)",
      lineHeight: 1.6
    }
  }, "\u5C31\u5730\u7F16\u8F91\u540E\u70B9\u53F3\u4E0A\u89D2\u300C\u4FDD\u5B58\u56DE\u586B\u300D\u63D0\u4EA4\uFF0C\u672A\u4FDD\u5B58\u65F6\u6309\u94AE\u4F1A\u9AD8\u4EAE\u63D0\u793A\u3002\u65F6\u95F4\u683C\u5F0F ", /*#__PURE__*/React.createElement("span", {
    className: "fr-code"
  }, "MM-DD HH:MM"), "\u3002\u5B9E\u9645\u5F00\u5DE5\u3001\u5B9E\u9645\u5B8C\u5DE5\u3001\u5DE5\u65F6\u4E09\u9879\u586B\u4EFB\u610F", /*#__PURE__*/React.createElement("strong", {
    style: {
      color: "var(--ui-primary)"
    }
  }, "\u4E24\u9879"), "\uFF0C\u7B2C\u4E09\u9879\u81EA\u52A8\u7B97\u51FA\uFF1B\u4E4B\u540E\u4FEE\u6539\u5176\u4E2D\u4EFB\u4E00\u9879\uFF0C\u4EE5\u6700\u65B0\u586B\u5199\u4E3A\u51C6\u91CD\u7B97\u53E6\u4E00\u9879\u3002\u300C\u6309\u8BA1\u5212\u586B\u300D\u628A\u5B9E\u9645\u586B\u6210\u4E0E\u8BA1\u5212\u4E00\u81F4\uFF0C\u518D\u6309\u73B0\u573A\u5B9E\u9645\u5FAE\u8C03\u5373\u53EF\uFF08\u793A\u4F8B\u6570\u636E\uFF09\u3002"), wiz ? /*#__PURE__*/React.createElement(FieldHoursImportModal, {
    wiz: wiz,
    onClose: () => setWiz(null),
    onDone: s => {
      setWiz(null);
      D && D.toast("实际工时导入完成：" + s + "。");
    }
  }) : null);
}
window.FieldRecordScreen = FieldRecordScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/FieldRecordScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/GanttBoard.jsx
try { (() => {
// APS Workbench · 甘特看板（看结果）重设计
// 三方案共享一份"真时间轴"数据：每条工序有起始(day,hour)与时长(小时)，
// 设备 / 人员 / 批次三视图只是对同一批工序做不同的透视。
// 方案 A 精密时间轴 · 方案 B 负载泳道 · 方案 C 关键链巡检。
// 保留两件用户喜欢的事：① 点条目开统一详情抽屉 ② 左侧资源/任务列。
(function () {
  const {
    useState,
    useRef,
    useLayoutEffect,
    useEffect
  } = React;

  /* ---------------- 主数据（与 detail-drawer 的记录编号对齐，点开即有富抽屉） ---------------- */
  const DAYS = [["周一", "05-23"], ["周二", "05-24"], ["周三", "05-25"], ["周四", "05-26"], ["周五", "05-27"], ["周六", "05-28"], ["周日", "05-29"]];
  const DAYH = 10; // 每个工作日窗口 08:00–18:00 = 10h
  const TOTAL = 7 * DAYH;
  const TODAY = 2; // 周三为"今天"
  const NOW = 2.5; // 周三 ≈13:00（天坐标）

  const DEV = {
    "M-03": {
      name: "五轴加工中心",
      group: "设备组 A",
      load: 96
    },
    "M-05": {
      name: "卧式加工中心",
      group: "设备组 A",
      load: 89
    },
    "M-07": {
      name: "立式加工中心",
      group: "设备组 B",
      load: 72
    },
    "M-12": {
      name: "三坐标检测",
      group: "设备组 C",
      load: 58
    },
    "M-18": {
      name: "数控车床",
      group: "设备组 A",
      load: 64
    },
    "M-21": {
      name: "线切割",
      group: "设备组 D",
      load: 0,
      down: true
    }
  };
  const PERSON = {
    "P-021": {
      name: "张三",
      skill: "精加工",
      load: 96
    },
    "P-024": {
      name: "李四",
      skill: "组装 / 数铣",
      load: 84
    },
    "P-101": {
      name: "张伟",
      skill: "数铣 / 数车",
      load: 70
    },
    "P-030": {
      name: "王五",
      skill: "检验",
      load: 72
    },
    "P-118": {
      name: "李娜",
      skill: "精磨 / 总检",
      load: 58
    }
  };
  const PART = {
    "B202605-018": "回转壳体 A",
    "B202605-021": "回转壳体 B",
    "B202605-019": "轴套 F",
    "B202605-017": "连接板 G",
    "B202605-024": "端盖 C",
    "B202605-016": "轴套 F",
    "B202605-013": "回转壳体 B"
  };
  const DUE = {
    "B202605-018": "05-24",
    "B202605-021": "05-25",
    "B202605-019": "05-25",
    "B202605-017": "05-26",
    "B202605-024": "05-26",
    "B202605-016": "05-24",
    "B202605-013": "05-23"
  };

  // 工序：batch 批次 / op 工序 / dev 设备 / person 人员 / d 起始(天,0–7) / w 时长(天) / status 颜色 / prog 进度% / seq 链序
  const TASKS = [
  // —— B202605-018 关键链（含超期精加工）——
  {
    batch: "B202605-018",
    op: "10 下料",
    dev: "M-18",
    person: "P-101",
    d: 0.1,
    w: 0.7,
    status: "normal",
    prog: 100,
    seq: 1
  }, {
    batch: "B202605-018",
    op: "20 预加工",
    dev: "M-05",
    person: "P-024",
    d: 0.9,
    w: 0.9,
    status: "urgent",
    prog: 100,
    seq: 2
  }, {
    batch: "B202605-018",
    op: "30 精加工",
    dev: "M-03",
    person: "P-021",
    d: 1.9,
    w: 1.3,
    status: "critical",
    prog: 55,
    overdue: true,
    critical: true,
    seq: 3
  }, {
    batch: "B202605-018",
    op: "50 检验",
    dev: "M-12",
    person: "P-030",
    d: 3.3,
    w: 0.6,
    status: "primary",
    prog: 0,
    critical: true,
    seq: 4
  },
  // —— B202605-021 ——
  {
    batch: "B202605-021",
    op: "20 预加工",
    dev: "M-05",
    person: "P-024",
    d: 0.0,
    w: 0.7,
    status: "urgent",
    prog: 100,
    seq: 1
  }, {
    batch: "B202605-021",
    op: "20 数车",
    dev: "M-18",
    person: "P-101",
    d: 1.0,
    w: 0.9,
    status: "normal",
    prog: 40,
    seq: 2
  }, {
    batch: "B202605-021",
    op: "40 钻孔",
    dev: "M-03",
    person: "P-021",
    d: 3.4,
    w: 0.8,
    status: "urgent",
    prog: 0,
    seq: 3
  },
  // —— B202605-019 ——
  {
    batch: "B202605-019",
    op: "40 组装",
    dev: "M-07",
    person: "P-030",
    d: 1.0,
    w: 1.1,
    status: "success",
    prog: 100,
    seq: 1
  }, {
    batch: "B202605-019",
    op: "50 总检",
    dev: "M-12",
    person: "P-118",
    d: 4.2,
    w: 0.6,
    status: "success",
    prog: 0,
    seq: 2
  },
  // —— B202605-017 外协 ——
  {
    batch: "B202605-017",
    op: "10 下料",
    dev: "M-07",
    person: "P-030",
    d: 0.0,
    w: 0.9,
    status: "normal",
    external: true,
    prog: 100,
    seq: 1
  }, {
    batch: "B202605-017",
    op: "30 电镀",
    dev: "M-07",
    person: "P-030",
    d: 4.0,
    w: 0.8,
    status: "normal",
    external: true,
    prog: 0,
    seq: 2
  },
  // —— 其余 ——
  {
    batch: "B202605-024",
    op: "10 钻孔",
    dev: "M-03",
    person: "P-021",
    d: 5.0,
    w: 0.8,
    status: "urgent",
    prog: 0,
    seq: 1
  }, {
    batch: "B202605-016",
    op: "50 检验",
    dev: "M-12",
    person: "P-118",
    d: 0.2,
    w: 0.5,
    status: "primary",
    prog: 100,
    seq: 2
  }, {
    batch: "B202605-016",
    op: "20 数铣",
    dev: "M-07",
    person: "P-024",
    d: 3.0,
    w: 0.9,
    status: "normal",
    prog: 0,
    seq: 1
  }, {
    batch: "B202605-013",
    op: "50 检验",
    dev: "M-12",
    person: "P-118",
    d: 5.2,
    w: 0.6,
    status: "success",
    prog: 0,
    seq: 1
  }].map((t, i) => ({
    ...t,
    id: "t" + i
  }));
  const COLOR = {
    normal: "var(--gantt-normal)",
    urgent: "var(--gantt-urgent)",
    critical: "var(--gantt-critical)",
    success: "var(--ui-success)",
    primary: "var(--ui-primary)"
  };

  // 时间颗粒度（缩放）：dayw = 每天列宽（px），sub = 每天的细分格数（辅助网格）
  // − 越看越粗（周概览）· + 越看越细（精确到小时）
  const ZOOMS = [{
    key: "week",
    label: "周",
    dayw: 88,
    sub: 1,
    tip: "概览 · 每格 1 天"
  }, {
    key: "day",
    label: "日",
    dayw: 132,
    sub: 1,
    tip: "每格 1 天"
  }, {
    key: "halfday",
    label: "半天",
    dayw: 208,
    sub: 2,
    tip: "每格 半天（5h）"
  }, {
    key: "hour",
    label: "时",
    dayw: 340,
    sub: 10,
    tip: "每格 1 小时"
  }];
  const sev = v => v >= 90 ? "danger" : v >= 75 ? "warn" : v <= 0 ? "off" : "";
  const pad = n => n < 10 ? "0" + n : "" + n;
  const clock = frac => {
    const b = 8 + frac * DAYH;
    const hh = Math.floor(b);
    const mm = Math.round((b - hh) * 60 / 5) * 5;
    return pad(hh) + ":" + pad(mm % 60 === 60 ? 0 : mm);
  };
  const leftPct = t => t.d / 7 * 100;
  const widPct = t => t.w / 7 * 100;
  const ICON = {
    device: '<path d="M3 20h18M5 20V9l5 3V9l5 3V6l4 2v12"/>',
    person: '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 3-5 6-5s6 1.7 6 5"/><path d="M16 5.5a3 3 0 010 6"/>',
    batch: '<path d="M3 7l9-4 9 4v10l-9 4-9-4V7z"/><path d="M3 7l9 4 9-4M12 11v10"/>'
  };
  const Svg = ({
    d
  }) => /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.7",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    dangerouslySetInnerHTML: {
      __html: d
    }
  });

  /* ---------------- 透视：把工序聚成泳道 ---------------- */
  function buildLanes(view) {
    if (view === "device") {
      return Object.keys(DEV).map(k => {
        const d = DEV[k];
        const tasks = TASKS.filter(t => t.dev === k);
        return {
          kind: "device",
          code: k,
          name: k,
          sub: d.name,
          meta: d.group + " · 任务 " + tasks.length,
          load: d.load,
          down: d.down,
          tasks
        };
      });
    }
    if (view === "person") {
      return Object.keys(PERSON).map(k => {
        const p = PERSON[k];
        const tasks = TASKS.filter(t => t.person === k);
        return {
          kind: "person",
          code: k,
          name: p.name,
          sub: k + " · " + p.skill,
          meta: "技能 " + p.skill + " · 任务 " + tasks.length,
          load: p.load,
          tasks
        };
      });
    }
    // batch：一行就是一个批次的工序链（横向看流程）
    return Object.keys(PART).map(k => {
      const tasks = TASKS.filter(t => t.batch === k);
      const prog = Math.round(tasks.reduce((a, t) => a + t.prog, 0) / Math.max(tasks.length, 1));
      return {
        kind: "batch",
        code: k,
        name: k,
        sub: PART[k],
        meta: tasks.length + " 道工序 · 交期 " + DUE[k],
        load: prog,
        loadLabel: "完成",
        tasks
      };
    });
  }

  /* ---------------- 单条甘特 ---------------- */
  function Bar({
    t,
    variant,
    view,
    dayw,
    focusOn,
    inChain,
    isHead,
    onEnter,
    onLeave,
    onClick
  }) {
    // 按「实际渲染像素宽」分三档，避免窄条只剩一个孤零零的工序号、看起来"没填东西"：
    // full ≥92px：工序名 + 资源 + 完成度% + 进度条 · mid ≥48px：工序名 + 进度条 · min：仅工序号（居中）
    const pxW = t.w * dayw;
    const tier = pxW >= 92 ? "full" : pxW >= 48 ? "mid" : "min";
    // 批次视图里条上同时标资源，否则标批次尾号
    const tail = t.batch.slice(-3);
    const tailText = view === "batch" ? t.dev : tail;
    const opShort = tier === "min" ? t.op.split(" ")[0] : t.op;
    const dimmed = variant === "c" && focusOn && !inChain;
    const cls = ["gb-bar"];
    if (tier !== "full") cls.push("is-narrow");
    if (tier === "min") cls.push("is-min");
    if (t.external) cls.push("is-external");
    if (t.overdue) cls.push("is-overdue");
    if (t.critical) cls.push("is-critical");
    if (variant === "c" && inChain) cls.push("is-in-chain");
    if (variant === "c" && isHead) cls.push("is-chain-head");
    return /*#__PURE__*/React.createElement("div", {
      className: cls.join(" "),
      "data-bar": t.id,
      title: t.batch + " · " + t.op + " · " + t.prog + "%",
      style: {
        left: leftPct(t) + "%",
        width: widPct(t) + "%",
        "--c": COLOR[t.status],
        opacity: dimmed ? 0.24 : 1,
        filter: dimmed ? "grayscale(0.35)" : "none"
      },
      onMouseEnter: e => onEnter(t, e),
      onMouseMove: e => onEnter(t, e),
      onMouseLeave: onLeave,
      onClick: e => {
        e.stopPropagation();
        onClick(t);
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "gb-bar-label"
    }, opShort, tier === "full" ? /*#__PURE__*/React.createElement("span", {
      style: {
        opacity: .65,
        marginLeft: 5
      }
    }, tailText) : null), tier === "full" ? /*#__PURE__*/React.createElement("span", {
      className: "gb-bar-pct"
    }, t.prog, "%") : null, tier !== "min" ? /*#__PURE__*/React.createElement("span", {
      className: "gb-bar-ptrack"
    }, /*#__PURE__*/React.createElement("span", {
      className: "gb-bar-pfill",
      style: {
        width: t.prog + "%"
      }
    })) : null);
  }

  /* ---------------- 主组件 ---------------- */
  function GanttBoard({
    onNav
  }) {
    const {
      Panel,
      Badge,
      Button
    } = window.APSDesignSystem_edbc5d;
    const variant = "c"; // 仅保留「关键链巡检」看板
    const [view, setView] = useState("device");
    const [zoom, setZoom] = useState(1); // 时间颗粒度索引，默认「日」
    const [onlyOverdue, setOnlyOverdue] = useState(false); // 仅超期：可切换的真实筛选
    const gran = ZOOMS[zoom];
    const [focusBatch, setFocusBatch] = useState(null); // 默认不聚焦任何链路：全部高亮；悬浮预览、点击锁定
    const [hoverBatch, setHoverBatch] = useState(null);
    const [tip, setTip] = useState(null);
    const [segs, setSegs] = useState([]);
    const gridRef = useRef(null);
    const lanes = buildLanes(view);
    const overdueCount = TASKS.filter(t => t.overdue).length;
    const dispLanes = onlyOverdue ? lanes.map(l => ({
      ...l,
      tasks: l.tasks.filter(t => t.overdue)
    })) : lanes;
    const viewUnit = view === "device" ? "台设备" : view === "person" ? "名人员" : "个批次";
    const activeBatch = hoverBatch || focusBatch;
    const chainTasks = activeBatch ? TASKS.filter(t => t.batch === activeBatch).sort((a, b) => a.d - b.d) : [];
    // 面包屑跟随 activeBatch（悬浮优先、其次已锁定）实时切换；容器恒高，所以切换内容不会撑动看板。

    const openDetail = (code, type) => {
      if (window.APSDetail) window.APSDetail.open(code, type, {
        from: "gantt"
      });
    };
    const onBarEnter = (t, e) => {
      setTip({
        t,
        x: e.clientX,
        y: e.clientY
      });
      setHoverBatch(t.batch);
    };
    const onBarLeave = () => {
      setTip(null);
      setHoverBatch(null);
    };
    const onBarClick = t => {
      setFocusBatch(t.batch);
      openDetail(t.batch, "batch");
    };
    const clearFocus = () => {
      setFocusBatch(null);
      setHoverBatch(null);
    };

    // 接受“从详情抽屉跳过来定位某批次”：进页时读取挂起的目标，并监听后续跳转事件
    useEffect(() => {
      const apply = b => {
        if (b) {
          setFocusBatch(b);
          setHoverBatch(null);
        }
      };
      if (window.__apsPendingGanttFocus) {
        apply(window.__apsPendingGanttFocus);
        window.__apsPendingGanttFocus = null;
      }
      const onFocus = e => {
        apply(e.detail);
        window.__apsPendingGanttFocus = null;
      };
      window.addEventListener("aps-gantt-focus", onFocus);
      return () => window.removeEventListener("aps-gantt-focus", onFocus);
    }, []);

    // 方案 C：测量被聚焦链路各工序条的位置，连线
    useLayoutEffect(() => {
      // 「仅超期」开启时，链路里的非超期工序条已从 DOM 移除，连线若仍按全链测量会指向空白格 —— 此时不画链路连线。
      if (variant !== "c" || !gridRef.current || chainTasks.length < 2 || onlyOverdue) {
        setSegs([]);
        return;
      }
      const compute = () => {
        const grid = gridRef.current;
        if (!grid) return;
        const gb = grid.getBoundingClientRect();
        const pts = [];
        for (const t of chainTasks) {
          const el = grid.querySelector('[data-bar="' + t.id + '"]');
          if (!el) return;
          const r = el.getBoundingClientRect();
          pts.push({
            x1: r.left - gb.left,
            x2: r.right - gb.left,
            y: r.top - gb.top + r.height / 2,
            crit: t.critical
          });
        }
        const out = [];
        for (let i = 0; i < pts.length - 1; i++) {
          const a = pts[i],
            b = pts[i + 1];
          const sx = a.x2,
            sy = a.y,
            ex = b.x1,
            ey = b.y;
          const mx = sx + Math.max(14, (ex - sx) / 2);
          const d = "M" + sx + "," + sy + " H" + mx + " V" + ey + " H" + ex;
          out.push({
            d,
            crit: a.crit && b.crit,
            sx,
            sy,
            ex,
            ey
          });
        }
        setSegs(out);
      };
      const raf1 = requestAnimationFrame(() => {
        rafId = requestAnimationFrame(compute);
      });
      let rafId = 0;
      const t1 = setTimeout(compute, 90);
      const t2 = setTimeout(compute, 260);
      window.addEventListener("resize", compute);
      return () => {
        cancelAnimationFrame(raf1);
        cancelAnimationFrame(rafId);
        clearTimeout(t1);
        clearTimeout(t2);
        window.removeEventListener("resize", compute);
      };
    }, [variant, view, activeBatch, zoom, onlyOverdue]);
    return /*#__PURE__*/React.createElement(Panel, {
      title: "\u8BBE\u5907 / \u4EBA\u5458 / \u6279\u6B21\u7518\u7279",
      description: "\u672C\u5468\u6392\u7A0B\u8BA1\u5212 \xB7 05-23 \u5468\u4E00 \u2192 05-29 \u5468\u65E5 \xB7 \u4ECA\u5929\u5468\u4E09",
      headerRight: null
    }, /*#__PURE__*/React.createElement("div", {
      className: "gb-toolbar"
    }, /*#__PURE__*/React.createElement("div", {
      className: "gb-tb-group"
    }, /*#__PURE__*/React.createElement("span", {
      className: "gb-tb-label"
    }, "\u89C6\u56FE"), /*#__PURE__*/React.createElement("div", {
      className: "seg"
    }, [["device", "设备"], ["person", "人员"], ["batch", "批次"]].map(([k, l]) => /*#__PURE__*/React.createElement("button", {
      key: k,
      className: "seg-btn" + (view === k ? " on" : ""),
      onClick: () => setView(k)
    }, l)))), /*#__PURE__*/React.createElement("div", {
      className: "gb-tb-group"
    }, /*#__PURE__*/React.createElement("span", {
      className: "gb-tb-label"
    }, "\u9897\u7C92\u5EA6"), /*#__PURE__*/React.createElement("div", {
      className: "gb-zoom-ctl"
    }, /*#__PURE__*/React.createElement("button", {
      className: "gb-zoom-btn",
      disabled: zoom <= 0,
      onClick: () => setZoom(z => Math.max(0, z - 1)),
      title: "\u7F29\u5C0F\xB7\u65F6\u95F4\u53D8\u7C97",
      "aria-label": "\u7F29\u5C0F\u9897\u7C92\u5EA6"
    }, "\u2212"), /*#__PURE__*/React.createElement("span", {
      className: "gb-zoom-lvl"
    }, gran.label), /*#__PURE__*/React.createElement("button", {
      className: "gb-zoom-btn",
      disabled: zoom >= ZOOMS.length - 1,
      onClick: () => setZoom(z => Math.min(ZOOMS.length - 1, z + 1)),
      title: "\u653E\u5927\xB7\u65F6\u95F4\u53D8\u7EC6",
      "aria-label": "\u653E\u5927\u9897\u7C92\u5EA6"
    }, "+"))), /*#__PURE__*/React.createElement("span", {
      className: "gb-tb-summary"
    }, "\u672C\u89C6\u56FE ", /*#__PURE__*/React.createElement("b", null, lanes.length), " ", viewUnit, " \xB7 ", /*#__PURE__*/React.createElement("b", null, TASKS.length), " \u9053\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("div", {
      className: "gb-tb-actions"
    }, /*#__PURE__*/React.createElement("button", {
      className: "gb-tb-btn" + (onlyOverdue ? " on" : ""),
      onClick: () => setOnlyOverdue(v => !v),
      title: "\u53EA\u770B\u5DF2\u8D85\u671F\u7684\u5DE5\u5E8F"
    }, /*#__PURE__*/React.createElement("svg", {
      viewBox: "0 0 24 24",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "1.8",
      strokeLinecap: "round",
      strokeLinejoin: "round"
    }, /*#__PURE__*/React.createElement("path", {
      d: "M3 5h18l-7 8v5l-4 2v-7z"
    })), "\u4EC5\u8D85\u671F", /*#__PURE__*/React.createElement("span", {
      className: "gb-tb-count"
    }, overdueCount)), /*#__PURE__*/React.createElement("button", {
      className: "gb-tb-btn",
      onClick: () => window.APSDetail && window.APSDetail.toast("导出本周计划 · 示例操作")
    }, /*#__PURE__*/React.createElement("svg", {
      viewBox: "0 0 24 24",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "1.8",
      strokeLinecap: "round",
      strokeLinejoin: "round"
    }, /*#__PURE__*/React.createElement("path", {
      d: "M12 3v11m0 0l-4-4m4 4l4-4M5 19h14"
    })), "\u5BFC\u51FA\u5468\u8BA1\u5212"))), /*#__PURE__*/React.createElement("div", {
      className: "gb-legend"
    }, /*#__PURE__*/React.createElement("span", {
      className: "gb-lg",
      style: {
        color: "var(--gantt-critical)"
      }
    }, /*#__PURE__*/React.createElement("i", {
      style: {
        background: "var(--gantt-critical)"
      }
    }), "\u8D85\u671F"), /*#__PURE__*/React.createElement("span", {
      className: "gb-lg",
      style: {
        color: "var(--gantt-urgent)"
      }
    }, /*#__PURE__*/React.createElement("i", {
      style: {
        background: "var(--gantt-urgent)"
      }
    }), "\u7D27\u6025"), /*#__PURE__*/React.createElement("span", {
      className: "gb-lg gold"
    }, "\u5173\u952E\u94FE\uFF08\u91D1\u8FB9\uFF09"), /*#__PURE__*/React.createElement("span", {
      className: "gb-lg dash"
    }, "\u5916\u534F\uFF08\u865A\u7EBF\uFF09"), /*#__PURE__*/React.createElement("span", {
      className: "gb-lg",
      style: {
        color: "var(--ui-success)"
      }
    }, /*#__PURE__*/React.createElement("i", {
      style: {
        background: "var(--ui-success)"
      }
    }), "\u6B63\u5E38 / \u5B8C\u6210"), /*#__PURE__*/React.createElement("span", {
      className: "gb-lg down"
    }, "\u505C\u673A"), /*#__PURE__*/React.createElement("span", {
      className: "gb-lg",
      style: {
        color: "var(--ui-text)"
      }
    }, /*#__PURE__*/React.createElement("i", {
      style: {
        background: "var(--ui-surface-soft)",
        border: "1px solid var(--ui-border)",
        position: "relative",
        overflow: "hidden"
      }
    }, /*#__PURE__*/React.createElement("b", {
      style: {
        position: "absolute",
        left: 0,
        top: 0,
        bottom: 0,
        width: "60%",
        background: "var(--ui-primary)"
      }
    })), "\u5E95\u90E8\u8FDB\u5EA6\u6761 = \u5B8C\u6210\u5EA6")), /*#__PURE__*/React.createElement("div", {
      className: "gb-chain" + (activeBatch ? "" : " is-empty")
    }, activeBatch ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
      className: "gb-chain-k"
    }, "\u5173\u952E\u94FE \xB7 ", /*#__PURE__*/React.createElement("b", null, activeBatch), " ", PART[activeBatch]), chainTasks.map((t, i) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: t.id
    }, i > 0 ? /*#__PURE__*/React.createElement("span", {
      className: "gb-chain-arrow"
    }, "\u2192") : null, /*#__PURE__*/React.createElement("span", {
      className: "gb-chain-node" + (t.critical ? " crit" : "") + (t.external ? " ext" : "") + (t.overdue ? " over" : ""),
      style: {
        "--c": COLOR[t.status]
      }
    }, t.op, /*#__PURE__*/React.createElement("span", {
      className: "cn-res"
    }, view === "person" ? PERSON[t.person].name : t.dev), /*#__PURE__*/React.createElement("span", {
      className: "cn-pct"
    }, t.prog, "%")))), /*#__PURE__*/React.createElement("span", {
      className: "gb-chain-hint"
    }, hoverBatch ? "悬浮预览中 · 点击锁定并开详情" : "已锁定 · 悬浮下方工序实时切换 · 点空白处清除")) : /*#__PURE__*/React.createElement("span", {
      className: "gb-chain-empty"
    }, "\u60AC\u6D6E\u4E0B\u65B9\u4EFB\u610F\u5DE5\u5E8F\uFF0C\u5373\u53EF\u67E5\u770B\u5176\u6240\u5728\u6279\u6B21\u7684\u5173\u952E\u94FE\u8DEF")), /*#__PURE__*/React.createElement("div", {
      className: "gb gb--" + variant + (activeBatch ? " has-focus" : ""),
      style: {
        "--gb-dayw": gran.dayw + "px",
        "--gb-sub": gran.sub
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "gb-board",
      onClick: clearFocus
    }, /*#__PURE__*/React.createElement("div", {
      className: "gb-scale"
    }, /*#__PURE__*/React.createElement("div", {
      className: "gb-corner"
    }, view === "batch" ? "批次 / 工序链" : view === "person" ? "人员 / 任务" : "资源 / 任务", /*#__PURE__*/React.createElement("span", {
      className: "gb-corner-sub"
    }, "\xB7 08:00\u201318:00 \xB7 ", gran.tip)), /*#__PURE__*/React.createElement("div", {
      className: "gb-days"
    }, DAYS.map(([d, dt], i) => {
      const weekend = i >= 5;
      return /*#__PURE__*/React.createElement("div", {
        key: dt,
        className: "gb-day" + (weekend ? " is-weekend" : "") + (i === TODAY ? " is-today" : "")
      }, /*#__PURE__*/React.createElement("b", null, d), /*#__PURE__*/React.createElement("span", null, dt), i === TODAY ? /*#__PURE__*/React.createElement("span", {
        className: "gb-day-tag"
      }, "\u4ECA\u5929") : null);
    }))), /*#__PURE__*/React.createElement("div", {
      className: "gb-grid",
      ref: gridRef
    }, dispLanes.map(ln => {
      const sv = sev(ln.load);
      const lc = sv === "danger" ? "var(--ui-danger)" : sv === "warn" ? "var(--ui-warning)" : sv === "off" ? "var(--ui-muted)" : "var(--ui-success)";
      return /*#__PURE__*/React.createElement("div", {
        className: "gb-row" + (ln.down ? " is-down" : ""),
        key: ln.code
      }, /*#__PURE__*/React.createElement("div", {
        className: "gb-res"
      }, /*#__PURE__*/React.createElement("span", {
        className: "gb-res-ico"
      }, /*#__PURE__*/React.createElement(Svg, {
        d: ICON[ln.kind]
      })), /*#__PURE__*/React.createElement("div", {
        className: "gb-res-main"
      }, /*#__PURE__*/React.createElement("div", {
        className: "gb-res-name"
      }, /*#__PURE__*/React.createElement("a", {
        onClick: e => {
          e.preventDefault();
          openDetail(ln.code, ln.kind === "device" ? "equip" : ln.kind === "person" ? "people" : "batch");
        }
      }, ln.name)), /*#__PURE__*/React.createElement("div", {
        className: "gb-res-sub"
      }, ln.sub), variant !== "b" ? /*#__PURE__*/React.createElement("div", {
        className: "gb-res-foot"
      }, /*#__PURE__*/React.createElement("span", {
        className: "gb-loadbar " + sv
      }, /*#__PURE__*/React.createElement("i", {
        style: {
          width: Math.max(ln.load, 2) + "%"
        }
      })), /*#__PURE__*/React.createElement("span", {
        className: "gb-loadnum"
      }, ln.load, "%")) : null), variant === "b" ? /*#__PURE__*/React.createElement("div", {
        className: "gb-res-stat"
      }, /*#__PURE__*/React.createElement("span", {
        className: "gb-res-pct " + sv
      }, ln.load, /*#__PURE__*/React.createElement("span", {
        style: {
          fontSize: 11,
          fontWeight: 700
        }
      }, "%")), /*#__PURE__*/React.createElement("span", {
        className: "gb-res-pctlabel"
      }, ln.loadLabel || "负载")) : null), /*#__PURE__*/React.createElement("div", {
        className: "gb-track"
      }, variant === "b" ? /*#__PURE__*/React.createElement("span", {
        className: "gb-loadband",
        style: {
          width: ln.load + "%",
          "--lc": lc
        }
      }) : null, /*#__PURE__*/React.createElement("span", {
        className: "gb-today",
        style: {
          left: TODAY / 7 * 100 + "%"
        }
      }), variant === "a" ? /*#__PURE__*/React.createElement("span", {
        className: "gb-nowline",
        style: {
          left: NOW / 7 * 100 + "%"
        }
      }) : null, ln.down ? /*#__PURE__*/React.createElement("span", {
        className: "gb-down-band"
      }, "\u505C\u673A\u7EF4\u62A4 \xB7 \u5168\u5929\u4E0D\u53EF\u7528") : ln.tasks.map(t => /*#__PURE__*/React.createElement(Bar, {
        key: t.id,
        t: t,
        variant: variant,
        view: view,
        dayw: gran.dayw,
        focusOn: !!activeBatch,
        inChain: activeBatch === t.batch,
        isHead: variant === "c" && chainTasks.length && chainTasks[0].id === t.id,
        onEnter: onBarEnter,
        onLeave: onBarLeave,
        onClick: onBarClick
      }))));
    }), variant === "c" && segs.length ? /*#__PURE__*/React.createElement("svg", {
      className: "gb-overlay"
    }, segs.map((s, i) => /*#__PURE__*/React.createElement("path", {
      key: "p" + i,
      d: s.d,
      className: s.crit ? "crit" : ""
    })), segs.map((s, i) => /*#__PURE__*/React.createElement("circle", {
      key: "c" + i,
      cx: s.ex,
      cy: s.ey,
      r: "3.5",
      className: s.crit ? "crit" : ""
    }))) : null))), tip ? /*#__PURE__*/React.createElement("div", {
      className: "gb-tip on",
      style: {
        left: Math.min(tip.x + 14, window.innerWidth - 296),
        top: tip.y + 16
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        marginBottom: 4
      }
    }, /*#__PURE__*/React.createElement("b", null, tip.t.batch), " \xB7 ", PART[tip.t.batch]), /*#__PURE__*/React.createElement("div", {
      className: "gb-tip-row"
    }, /*#__PURE__*/React.createElement("span", null, "\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("span", null, tip.t.op)), /*#__PURE__*/React.createElement("div", {
      className: "gb-tip-row"
    }, /*#__PURE__*/React.createElement("span", null, view === "person" ? "设备" : "人员"), /*#__PURE__*/React.createElement("span", null, view === "person" ? tip.t.dev + " " + DEV[tip.t.dev].name : PERSON[tip.t.person].name)), /*#__PURE__*/React.createElement("div", {
      className: "gb-tip-row"
    }, /*#__PURE__*/React.createElement("span", null, "\u65F6\u6BB5"), /*#__PURE__*/React.createElement("span", null, DAYS[Math.floor(tip.t.d)][0], " ", clock(tip.t.d - Math.floor(tip.t.d)), " \u8D77 \xB7 \u7EA6 ", Math.round(tip.t.w * DAYH), "h")), /*#__PURE__*/React.createElement("div", {
      className: "gb-tip-row"
    }, /*#__PURE__*/React.createElement("span", null, "\u8FDB\u5EA6"), /*#__PURE__*/React.createElement("span", null, tip.t.prog, "%", tip.t.external ? " · 外协" : "", tip.t.overdue ? " · 超期" : ""))) : null);
  }
  window.GanttBoard = GanttBoard;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/GanttBoard.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/GanttScreen.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
// APS Workbench · 排产前检查 (run preflight) — 复用 批次管理 / 基础资料 的 Panel / 分组 / 选项 / 校验范式
// 一道闸门：① 就绪概览 ② 排产开关 ③ 就绪检查清单 ④ 开始排产。开关仅对本次排产生效。
function PreflightCheck({
  onNav
}) {
  const {
    Panel,
    Badge,
    Button
  } = window.APSDesignSystem_edbc5d;
  const {
    StrictSeg,
    DateInput
  } = window.BD;
  const {
    useState
  } = React;
  const [readyCheck, setReadyCheck] = useState(true); // 齐套检查
  const [autoFill, setAutoFill] = useState(true); // 缺资源工序处理：自动分配 / 暂不排
  const [lockStarted, setLockStarted] = useState(true); // 锁定已开工工序
  const [ran, setRan] = useState(false);

  // —— 排产范围 · 时间窗口：选预设或自定义起止日期 ——
  const WIN = {
    week: {
      label: "本周",
      start: "05-23",
      end: "05-29",
      days: 7
    },
    twoweek: {
      label: "未来两周",
      start: "05-23",
      end: "06-05",
      days: 14
    },
    month: {
      label: "本月",
      start: "05-01",
      end: "05-31",
      days: 31
    }
  };
  const [winMode, setWinMode] = useState("week"); // week | twoweek | month | custom
  const [winStart, setWinStart] = useState("2026-05-23");
  const [winEnd, setWinEnd] = useState("2026-06-06");
  const md = iso => (iso || "").slice(5).replace("-", "-"); // 2026-05-23 → 05-23
  // 这些派生值与「就绪概览 / 检查清单 / 底部摘要」共用同一份状态——摘要条只是它们的一处回显，不另存数据。
  const winStartMd = winMode === "custom" ? md(winStart) : WIN[winMode].start;
  const winEndMd = winMode === "custom" ? md(winEnd) : WIN[winMode].end;
  const winRange = winStartMd + " ~ " + winEndMd;
  const winLabel = winMode === "custom" ? "自定义" : WIN[winMode].label;
  const winDays = winMode === "custom" ? Math.max(0, Math.round((new Date(winEnd + "T00:00") - new Date(winStart + "T00:00")) / 86400000) + 1) : WIN[winMode].days;

  // —— 排产范围 · 纳入批次：示例批次池（口径合计 = 126 道工序 / 7 道缺资源 / 3 批未齐套）——
  const BATCHES = [{
    id: "B202605-016",
    part: "端盖 C",
    due: "05-26",
    ops: 12,
    gaps: 0,
    ready: true,
    tag: ""
  }, {
    id: "B202605-017",
    part: "法兰 D",
    due: "05-27",
    ops: 18,
    gaps: 2,
    ready: true,
    tag: "外协在途"
  }, {
    id: "B202605-018",
    part: "回转壳体 A",
    due: "05-24",
    ops: 22,
    gaps: 1,
    ready: true,
    tag: "超期风险"
  }, {
    id: "B202605-019",
    part: "回转壳体 B",
    due: "05-28",
    ops: 16,
    gaps: 0,
    ready: false,
    tag: ""
  }, {
    id: "B202605-021",
    part: "端盖 C",
    due: "05-29",
    ops: 14,
    gaps: 2,
    ready: true,
    tag: ""
  }, {
    id: "B202605-022",
    part: "回转壳体 B",
    due: "06-02",
    ops: 15,
    gaps: 0,
    ready: false,
    tag: ""
  }, {
    id: "B202605-024",
    part: "回转壳体 A",
    due: "06-03",
    ops: 17,
    gaps: 1,
    ready: true,
    tag: ""
  }, {
    id: "B202605-025",
    part: "法兰 D",
    due: "06-05",
    ops: 12,
    gaps: 1,
    ready: false,
    tag: ""
  }];
  const [pickMode, setPickMode] = useState("all"); // all | pick
  const [picked, setPicked] = useState(() => BATCHES.map(b => b.id));
  const togglePick = id => setPicked(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id]);
  const selected = pickMode === "all" ? BATCHES : BATCHES.filter(b => picked.includes(b.id));

  // 指定批次：展开 / 收起 + 确定 / 取消（点「确定」后自动收起面板，下方回显摘要）
  const [pickOpen, setPickOpen] = useState(false);
  const pickSnap = React.useRef(picked);
  const openPicker = () => {
    pickSnap.current = picked;
    setPickMode("pick");
    setPickOpen(true);
  };
  const confirmPick = () => setPickOpen(false);
  const cancelPick = () => {
    setPicked(pickSnap.current);
    setPickOpen(false);
  };
  const nBatch = selected.length;
  const nOps = selected.reduce((a, b) => a + b.ops, 0);
  const GAPS = selected.reduce((a, b) => a + b.gaps, 0);
  const UNREADY = selected.filter(b => !b.ready).length;
  // 缺资源是否构成阻断：只有「关掉自动补齐」且仍有缺口时，必须先手工补齐才能排产。
  const blockGaps = !autoFill && GAPS > 0;
  const noBatch = nBatch === 0;
  const summary = [{
    sev: noBatch ? "danger" : "notice",
    label: "在排批次",
    value: nBatch,
    helper: pickMode === "all" ? "范围内全部待排批次" : "已手动勾选 " + nBatch + " / " + BATCHES.length + " 个批次"
  }, {
    sev: "notice",
    label: "参与工序",
    value: nOps,
    helper: "选中批次需排入的工序合计"
  }, {
    sev: GAPS ? autoFill ? "notice" : "warning" : "ok",
    label: "缺资源工序",
    value: GAPS,
    helper: autoFill ? "排产时按规则自动分配设备/人员" : "需先到批次管理手工补齐"
  }, {
    sev: UNREADY ? readyCheck ? "warning" : "secondary" : "ok",
    label: "未齐套批次",
    value: UNREADY,
    helper: !UNREADY ? "选中批次均已齐套" : readyCheck ? "开启齐套检查，将不排入计划" : "已关闭齐套检查，照常排入"
  }];
  const STATE = {
    pass: {
      dot: "var(--ui-success)",
      tone: "ok",
      label: "通过"
    },
    warn: {
      dot: "var(--ui-warning)",
      tone: "warning",
      label: "提醒"
    },
    block: {
      dot: "var(--ui-danger)",
      tone: "danger",
      label: "需处理"
    },
    skip: {
      dot: "var(--ui-muted)",
      tone: "secondary",
      label: "不校验"
    }
  };
  const link = (label, msg) => /*#__PURE__*/React.createElement("a", {
    className: "bd-link",
    href: "#",
    onClick: e => {
      e.preventDefault();
      window.APSDetail && window.APSDetail.toast(msg);
    },
    style: {
      fontSize: 12.5,
      whiteSpace: "nowrap"
    }
  }, label);
  const checks = [{
    state: "pass",
    title: "工艺路线完整",
    detail: "18 个在排图号均已在工艺模板登记路线，无缺工序的批次。"
  }, {
    state: autoFill ? "warn" : GAPS ? "block" : "pass",
    title: "缺资源工序",
    detail: autoFill ? GAPS + " 道工序缺设备/人员，将按「人员-设备关联」规则自动分配。" : GAPS ? GAPS + " 道工序缺设备/人员，已设为暂不排，需手工指定设备/人员后方可排产。" : "全部工序已指定设备与人员。",
    action: GAPS ? link("去补齐", "跳转到批次管理 · 待补资源工序（示例）") : null
  }, {
    state: readyCheck ? "warn" : "skip",
    title: "齐套检查",
    detail: readyCheck ? UNREADY + " 个批次未齐套，本次将跳过、不排入计划，可在批次管理调整齐套日期。" : "已关闭：不校验齐套，齐套显示与齐套日期仅作记录。",
    action: readyCheck ? link("查看批次", "筛选未齐套批次（示例）") : null
  }, {
    state: "pass",
    title: "工时定额",
    detail: "在排工序定额已覆盖；近 N 次实际偏差大的工序见「排产分析 · 工时校准」。"
  }, {
    state: "pass",
    title: "工作日历与产能",
    detail: "本周设备日历、停机与班次已加载，无冲突区段。"
  }];
  const blocking = checks.filter(c => c.state === "block").length;
  const opts = [{
    label: "齐套检查",
    checked: readyCheck,
    onChange: setReadyCheck,
    on: "开启",
    off: "关闭",
    note: readyCheck ? "排产时校验齐套日期：未齐套的批次不会排入计划。" : "不校验齐套；齐套显示与齐套日期仅作记录。"
  }, {
    label: "缺资源工序处理",
    checked: autoFill,
    onChange: setAutoFill,
    on: "自动分配",
    off: "暂不排",
    note: autoFill ? "缺设备/人员的工序按「人员-设备关联」规则自动分配，排产不被缺口卡住。" : "缺设备/人员的工序本次暂不排入计划，留待手工指定后再排。"
  }, {
    label: "已开工工序",
    checked: lockStarted,
    onChange: setLockStarted,
    on: "锁定",
    off: "可重排",
    note: lockStarted ? "保持加工中/已完工工序的现有计划，仅排后续工序。" : "允许重排全部工序（含加工中），可能打乱现场进度。"
  }];
  return /*#__PURE__*/React.createElement(Panel, {
    title: "\u6392\u4EA7\u524D\u68C0\u67E5",
    description: "\u5F00\u59CB\u6392\u4EA7\u524D\u7684\u4E00\u9053\u95F8\u95E8\uFF1A\u786E\u8BA4\u8303\u56F4\u4E0E\u5F00\u5173\u3001\u8FC7\u4E00\u904D\u5C31\u7EEA\u6E05\u5355\uFF0C\u518D\u5F00\u59CB\u3002\u5F00\u5173\u4EC5\u5BF9\u672C\u6B21\u6392\u4EA7\u751F\u6548\uFF0C\u4E0D\u6539\u57FA\u7840\u8D44\u6599\u3002",
    headerRight: /*#__PURE__*/React.createElement("span", {
      className: "muted",
      style: {
        fontSize: 12.5,
        whiteSpace: "nowrap"
      }
    }, "\u4E0A\u6B21\u6392\u4EA7\uFF1A\u4ECA\u5929 09:12 \xB7 \u5F20\u4E09"),
    style: {
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "bd-fieldset"
  }, /*#__PURE__*/React.createElement("p", {
    className: "bd-fieldset-label"
  }, "\u6392\u4EA7\u8303\u56F4"), /*#__PURE__*/React.createElement("div", {
    className: "scope-bar"
  }, /*#__PURE__*/React.createElement("span", {
    className: "scope-k"
  }, "\u65F6\u95F4\u7A97\u53E3"), /*#__PURE__*/React.createElement("div", {
    className: "seg"
  }, [["week", "本周"], ["twoweek", "两周"], ["month", "本月"], ["custom", "自定义"]].map(([k, l]) => /*#__PURE__*/React.createElement("button", {
    key: k,
    type: "button",
    className: "seg-btn" + (winMode === k ? " on" : ""),
    onClick: () => setWinMode(k)
  }, l))), /*#__PURE__*/React.createElement("span", {
    className: "scope-badge",
    title: "计划覆盖区间 " + winRange + " · 共 " + winDays + " 天"
  }, /*#__PURE__*/React.createElement("span", null, winStartMd), /*#__PURE__*/React.createElement("span", {
    className: "sb-arrow"
  }, "\u2192"), /*#__PURE__*/React.createElement("span", null, winEndMd), /*#__PURE__*/React.createElement("span", {
    className: "sb-days"
  }, winDays, " \u5929")), /*#__PURE__*/React.createElement("span", {
    className: "scope-div"
  }), /*#__PURE__*/React.createElement("span", {
    className: "scope-k"
  }, "\u7EB3\u5165\u6279\u6B21"), /*#__PURE__*/React.createElement("div", {
    className: "seg"
  }, [["all", "全部待排"], ["pick", "指定批次"]].map(([k, l]) => /*#__PURE__*/React.createElement("button", {
    key: k,
    type: "button",
    className: "seg-btn" + (pickMode === k ? " on" : ""),
    onClick: () => k === "pick" ? openPicker() : setPickMode("all")
  }, l))), /*#__PURE__*/React.createElement("span", {
    className: "scope-count"
  }, nBatch, " \u6279 / ", nOps, " \u5DE5\u5E8F")), winMode === "custom" ? /*#__PURE__*/React.createElement("div", {
    className: "scope-expand"
  }, /*#__PURE__*/React.createElement("span", {
    className: "scope-expand-k"
  }, "\u81EA\u5B9A\u4E49\u533A\u95F4"), /*#__PURE__*/React.createElement(DateInput, {
    value: winStart,
    onChange: setWinStart
  }), /*#__PURE__*/React.createElement("span", {
    className: "muted",
    style: {
      fontSize: 12,
      flex: "none"
    }
  }, "\u81F3"), /*#__PURE__*/React.createElement(DateInput, {
    value: winEnd,
    onChange: setWinEnd
  }), /*#__PURE__*/React.createElement("span", {
    className: "bd-option-note",
    style: {
      flex: "none"
    }
  }, "\u5171 ", winDays, " \u5929 \xB7 \u7A97\u53E3\u5916\u5DE5\u5E8F\u4E0D\u6392\u5165\u672C\u6B21\u8BA1\u5212\u3002")) : null, pickMode === "pick" && pickOpen ? /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 14,
      border: "1px solid var(--ui-border)",
      borderRadius: 8,
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      padding: "9px 14px",
      background: "var(--ui-surface-muted)",
      borderBottom: "1px solid var(--ui-border)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12.5,
      fontWeight: 600
    }
  }, "\u5DF2\u9009 ", /*#__PURE__*/React.createElement("strong", {
    style: {
      fontVariantNumeric: "tabular-nums"
    }
  }, nBatch), " / ", BATCHES.length), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: "auto",
      display: "flex",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "bd-chipbtn",
    onClick: () => setPicked(BATCHES.map(b => b.id))
  }, "\u5168\u9009"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "bd-chipbtn",
    onClick: () => setPicked(BATCHES.filter(b => b.ready).map(b => b.id))
  }, "\u4EC5\u5DF2\u9F50\u5957"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "bd-chipbtn",
    onClick: () => setPicked([])
  }, "\u6E05\u7A7A"))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column"
    }
  }, BATCHES.map((b, i) => {
    const on = picked.includes(b.id);
    return /*#__PURE__*/React.createElement("label", {
      key: b.id,
      style: {
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "10px 14px",
        borderBottom: i === BATCHES.length - 1 ? "0" : "1px solid var(--ui-border)",
        cursor: "pointer",
        background: on ? "var(--ui-primary-soft)" : "transparent"
      }
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: on,
      onChange: () => togglePick(b.id),
      style: {
        accentColor: "var(--ui-primary)",
        width: 15,
        height: 15,
        margin: 0,
        flex: "none"
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: "var(--font-mono, ui-monospace)",
        fontSize: 12.5,
        fontWeight: 600,
        width: 116,
        flex: "none"
      }
    }, b.id), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 13,
        flex: 1,
        minWidth: 0,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap"
      }
    }, b.part), /*#__PURE__*/React.createElement("span", {
      className: "muted",
      style: {
        fontSize: 12,
        fontVariantNumeric: "tabular-nums",
        width: 72,
        flex: "none"
      }
    }, "\u4EA4\u671F ", b.due), /*#__PURE__*/React.createElement("span", {
      className: "muted",
      style: {
        fontSize: 12,
        fontVariantNumeric: "tabular-nums",
        width: 60,
        flex: "none",
        textAlign: "right"
      }
    }, b.ops, " \u5DE5\u5E8F"), /*#__PURE__*/React.createElement("span", {
      style: {
        display: "flex",
        gap: 6,
        width: 150,
        flex: "none",
        justifyContent: "flex-end"
      }
    }, !b.ready ? /*#__PURE__*/React.createElement(Badge, {
      tone: "warning",
      dot: true
    }, "\u672A\u9F50\u5957") : null, b.gaps ? /*#__PURE__*/React.createElement(Badge, {
      tone: "notice",
      dot: true
    }, "\u7F3A", b.gaps) : null, b.tag ? /*#__PURE__*/React.createElement(Badge, {
      tone: "secondary"
    }, b.tag) : null));
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      padding: "10px 14px",
      borderTop: "1px solid var(--ui-border)",
      background: "var(--ui-surface-muted)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "muted",
    style: {
      fontSize: 12,
      fontVariantNumeric: "tabular-nums"
    }
  }, "\u5DF2\u9009 ", nBatch, " \u4E2A\u6279\u6B21 \xB7 ", nOps, " \u5DE5\u5E8F"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: "auto",
      display: "flex",
      gap: 10
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "sm",
    onClick: cancelPick
  }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    size: "sm",
    onClick: confirmPick
  }, "\u786E\u5B9A")))) : pickMode === "pick" ? /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12,
      marginTop: 14,
      padding: "11px 14px",
      border: "1px solid var(--ui-border)",
      borderRadius: 8,
      background: "var(--ui-surface-muted)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 7,
      height: 7,
      borderRadius: "50%",
      background: "var(--ui-primary)",
      flex: "none"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 13,
      fontWeight: 600,
      whiteSpace: "nowrap"
    }
  }, "\u5DF2\u6307\u5B9A ", nBatch, " \u4E2A\u6279\u6B21"), /*#__PURE__*/React.createElement("span", {
    className: "muted",
    style: {
      fontSize: 12.5,
      whiteSpace: "nowrap"
    }
  }, "\xB7 ", nOps, " \u5DE5\u5E8F\u7EB3\u5165\u672C\u6B21\u6392\u4EA7"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "bd-chipbtn",
    style: {
      marginLeft: "auto"
    },
    onClick: () => setPickOpen(true)
  }, "\u7F16\u8F91\u6279\u6B21")) : null), /*#__PURE__*/React.createElement("div", {
    className: "bd-fieldset"
  }, /*#__PURE__*/React.createElement("p", {
    className: "bd-fieldset-label"
  }, "\u5C31\u7EEA\u6982\u89C8"), /*#__PURE__*/React.createElement("div", {
    className: "delay-summary"
  }, summary.map((s, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "ds-card sev-" + s.sev
  }, /*#__PURE__*/React.createElement("div", {
    className: "ds-label"
  }, s.label), /*#__PURE__*/React.createElement("div", {
    className: "ds-value"
  }, s.value), /*#__PURE__*/React.createElement("div", {
    className: "ds-helper"
  }, s.helper))))), /*#__PURE__*/React.createElement("div", {
    className: "bd-fieldset"
  }, /*#__PURE__*/React.createElement("p", {
    className: "bd-fieldset-label"
  }, "\u6392\u4EA7\u5F00\u5173 \xB7 \u4EC5\u672C\u6B21\u751F\u6548"), /*#__PURE__*/React.createElement("div", {
    className: "bd-switch-list"
  }, opts.map(o => /*#__PURE__*/React.createElement("div", {
    className: "bd-switch-row",
    key: o.label
  }, /*#__PURE__*/React.createElement("div", {
    className: "bd-switch-main"
  }, /*#__PURE__*/React.createElement("span", {
    className: "bd-switch-label"
  }, o.label), /*#__PURE__*/React.createElement("span", {
    className: "bd-switch-note"
  }, o.note)), /*#__PURE__*/React.createElement("div", {
    className: "bd-switch-ctrl"
  }, /*#__PURE__*/React.createElement(StrictSeg, {
    checked: o.checked,
    onChange: o.onChange,
    onText: o.on,
    offText: o.off,
    ariaLabel: o.label
  })))))), /*#__PURE__*/React.createElement("div", {
    className: "bd-fieldset"
  }, /*#__PURE__*/React.createElement("p", {
    className: "bd-fieldset-label"
  }, "\u5C31\u7EEA\u68C0\u67E5"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 8
    }
  }, checks.map((c, i) => {
    const m = STATE[c.state];
    return /*#__PURE__*/React.createElement("div", {
      key: i,
      style: {
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        padding: "11px 14px",
        border: "1px solid var(--ui-border)",
        borderLeft: "3px solid " + m.dot,
        borderRadius: 8,
        background: "var(--ui-surface-muted)"
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: m.dot,
        marginTop: 6,
        flex: "none"
      }
    }), /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1,
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        alignItems: "center",
        gap: 8,
        flexWrap: "wrap"
      }
    }, /*#__PURE__*/React.createElement("strong", {
      style: {
        fontSize: 13.5
      }
    }, c.title), /*#__PURE__*/React.createElement(Badge, {
      tone: m.tone,
      dot: true
    }, m.label)), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 12.5,
        color: "var(--ui-muted)",
        lineHeight: 1.6,
        marginTop: 4
      }
    }, c.detail)), c.action ? /*#__PURE__*/React.createElement("div", {
      style: {
        flex: "none",
        paddingTop: 1
      }
    }, c.action) : null);
  }))), ran ? /*#__PURE__*/React.createElement("div", {
    className: "bd-flash tone-ok",
    style: {
      marginTop: 16,
      marginBottom: 0
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "bd-flash-dot"
  }), /*#__PURE__*/React.createElement("span", null, "\u6392\u4EA7\u5B8C\u6210\uFF1A", nBatch, " \u4E2A\u6279\u6B21\u3001", nOps, " \u9053\u5DE5\u5E8F\u5DF2\u6392\u5165\u8BA1\u5212", readyCheck && UNREADY ? "（跳过 " + UNREADY + " 个未齐套批次）" : "", "\u3002\u53EF\u5230\u300C\u770B\u7ED3\u679C \xB7 \u8BBE\u5907/\u4EBA\u5458/\u6279\u6B21\u7518\u7279\u300D\u9010\u6761\u5DE1\u68C0\u540E\u4E0B\u53D1\u3002")) : noBatch ? /*#__PURE__*/React.createElement("div", {
    className: "bd-flash tone-danger",
    style: {
      marginTop: 16,
      marginBottom: 0
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "bd-flash-dot"
  }), /*#__PURE__*/React.createElement("span", null, "\u5F53\u524D\u672A\u7EB3\u5165\u4EFB\u4F55\u6279\u6B21\u3002\u8BF7\u5728\u300C\u6392\u4EA7\u8303\u56F4 \xB7 \u7EB3\u5165\u6279\u6B21\u300D\u52FE\u9009\u81F3\u5C11\u4E00\u4E2A\u6279\u6B21\uFF0C\u6216\u5207\u56DE\u300C\u5168\u90E8\u5F85\u6392\u300D\u3002")) : blocking ? /*#__PURE__*/React.createElement("div", {
    className: "bd-flash tone-danger",
    style: {
      marginTop: 16,
      marginBottom: 0
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "bd-flash-dot"
  }), /*#__PURE__*/React.createElement("span", null, "\u6709 ", blocking, " \u9879\u9700\u5148\u5904\u7406\uFF1A", GAPS, " \u9053\u5DE5\u5E8F\u7F3A\u8D44\u6E90\u4E14\u5DF2\u8BBE\u4E3A\u6682\u4E0D\u6392\u3002\u8BF7\u624B\u5DE5\u6307\u5B9A\u8BBE\u5907/\u4EBA\u5458\uFF0C\u6216\u5C06\u300C\u7F3A\u8D44\u6E90\u5DE5\u5E8F\u5904\u7406\u300D\u5207\u56DE\u81EA\u52A8\u5206\u914D\u3002")) : null, /*#__PURE__*/React.createElement("div", {
    className: "bd-form-footer"
  }, /*#__PURE__*/React.createElement("div", {
    className: "bd-run-meta"
  }, /*#__PURE__*/React.createElement("span", {
    className: "bd-run-meta-item"
  }, /*#__PURE__*/React.createElement("i", null, "\u8303\u56F4"), " ", winLabel, "\uFF08", winRange, "\uFF09"), /*#__PURE__*/React.createElement("span", {
    className: "bd-run-meta-item"
  }, /*#__PURE__*/React.createElement("b", null, nBatch), " \u6279 / ", /*#__PURE__*/React.createElement("b", null, nOps), " \u5DE5\u5E8F"), /*#__PURE__*/React.createElement("span", {
    className: "bd-run-meta-item"
  }, /*#__PURE__*/React.createElement("i", null, "\u9F50\u5957\u68C0\u67E5"), " ", readyCheck ? "开启" : "关闭"), /*#__PURE__*/React.createElement("span", {
    className: "bd-run-meta-item"
  }, /*#__PURE__*/React.createElement("i", null, "\u81EA\u52A8\u8865\u9F50"), " ", autoFill ? "开" : "关")), ran ? /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "md",
    onClick: () => setRan(false)
  }, "\u91CD\u65B0\u68C0\u67E5") : null, ran ? /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "md",
    onClick: () => {
      setRan(true);
      window.APSDetail && window.APSDetail.toast("已重新排产 · 示例操作");
    }
  }, "\u91CD\u65B0\u6392\u4EA7") : null, ran ? /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    size: "md",
    onClick: () => onNav && onNav("gantt")
  }, "\u53BB\u770B\u7ED3\u679C \u2192") : /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    size: "md",
    disabled: blocking > 0 || noBatch,
    onClick: () => {
      setRan(true);
      window.APSDetail && window.APSDetail.toast("已开始排产 · 示例操作");
    }
  }, "\u5F00\u59CB\u6392\u4EA7")));
}

// APS Workbench · 设备甘特图 (scheduler/gantt)
function GanttScreen({
  mode,
  onNav
}) {
  const {
    Panel,
    Badge,
    Button,
    Meter
  } = window.APSDesignSystem_edbc5d;
  const [view, setView] = React.useState("device");

  // 执行排产页只做「闸门 + 动作 + 回执」，整张甘特移到「看结果」避免重复。
  if (mode === "run") return /*#__PURE__*/React.createElement(PreflightCheck, {
    onNav: onNav
  });

  // 看结果 · 甘特看板已重做为三方案对比版（GanttBoard.jsx）。
  if (window.GanttBoard) return /*#__PURE__*/React.createElement(window.GanttBoard, {
    onNav: onNav
  });
  const DAYS = [["周一", "05-23"], ["周二", "05-24"], ["周三", "05-25"], ["周四", "05-26"], ["周五", "05-27"], ["周六", "05-28"], ["周日", "05-29"]];
  const lanes = [{
    name: "M-03",
    meta: "设备 · 任务 12 · 96%",
    v: 96,
    bars: [{
      status: "critical",
      overdue: true,
      critical: true,
      left: "8%",
      width: "30%",
      label: "B202605-018 · 30 精加工"
    }, {
      status: "normal",
      dim: true,
      left: "42%",
      width: "14%",
      label: "切换 / 清理"
    }, {
      status: "urgent",
      left: "58%",
      width: "20%",
      label: "B202605-024 · 20 钻孔"
    }]
  }, {
    name: "M-05",
    meta: "设备 · 任务 9 · 89%",
    v: 89,
    bars: [{
      status: "urgent",
      left: "4%",
      width: "22%",
      label: "B202605-021 · 20 预加工"
    }, {
      status: "normal",
      dim: true,
      left: "28%",
      width: "18%",
      label: "停机 08:00–12:00"
    }, {
      status: "success",
      left: "50%",
      width: "24%",
      label: "B202605-019 · 40 组装"
    }]
  }, {
    name: "M-07",
    meta: "设备 · 任务 7 · 72%",
    v: 72,
    bars: [{
      status: "success",
      left: "8%",
      width: "20%",
      label: "B202605-019 · 40 组装"
    }, {
      status: "normal",
      external: true,
      left: "32%",
      width: "24%",
      label: "B202605-017 · 10 下料（外协）"
    }]
  }, {
    name: "M-12",
    meta: "设备 · 任务 5 · 58%",
    v: 58,
    bars: [{
      status: "primary",
      left: "12%",
      width: "18%",
      label: "B202605-016 · 50 检验"
    }, {
      status: "success",
      left: "40%",
      width: "16%",
      label: "B202605-013 · 50 检验"
    }]
  }];
  return /*#__PURE__*/React.createElement(Panel, {
    title: "\u8BBE\u5907 / \u4EBA\u5458 / \u6279\u6B21\u7518\u7279 \xB7 \u672C\u5468\u8BA1\u5212",
    description: "\u6309\u8D44\u6E90\u6392\u5E03\u7684\u672C\u5468\u8BA1\u5212\u3002\u73B0\u573A\u7740\u8272\uFF1A\u7EA2\u8FB9\u8D85\u671F\u3001\u91D1\u8FB9\u5173\u952E\u94FE\u3001\u865A\u7EBF\u5916\u534F\u3001\u7070\u5E26\u505C\u673A\u3002\u70B9\u6761\u76EE\u53EF\u6CBF\u94FE\u5DE1\u68C0\u3002",
    headerRight: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "seg"
    }, [["device", "设备"], ["person", "人员"], ["batch", "批次"]].map(([k, l]) => /*#__PURE__*/React.createElement("button", {
      key: k,
      className: "seg-btn" + (view === k ? " on" : ""),
      onClick: () => setView(k)
    }, l))), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "sm",
      onClick: () => window.APSDetail && window.APSDetail.toast("已筛选：仅超期任务（示例）")
    }, "\u4EC5\u8D85\u671F"), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "sm",
      onClick: () => window.APSDetail && window.APSDetail.toast("导出本周计划 · 示例操作")
    }, "\u5BFC\u51FA\u5468\u8BA1\u5212"))
  }, /*#__PURE__*/React.createElement("div", {
    className: "legend"
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: "danger",
    dot: true
  }, "\u8D85\u671F"), /*#__PURE__*/React.createElement(Badge, {
    tone: "warning",
    dot: true
  }, "\u63A5\u8FD1\u6EE1\u8F7D"), /*#__PURE__*/React.createElement(Badge, {
    tone: "notice",
    dot: true
  }, "\u5916\u534F\uFF08\u865A\u7EBF\uFF09"), /*#__PURE__*/React.createElement(Badge, {
    tone: "primary",
    dot: true
  }, "\u5173\u952E\u94FE\uFF08\u91D1\u8FB9\uFF09"), /*#__PURE__*/React.createElement(Badge, {
    tone: "secondary",
    dot: true
  }, "\u505C\u673A / \u4E0D\u53EF\u7528"), /*#__PURE__*/React.createElement(Badge, {
    tone: "success",
    dot: true
  }, "\u6B63\u5E38")), /*#__PURE__*/React.createElement("div", {
    className: "gantt"
  }, /*#__PURE__*/React.createElement("div", {
    className: "gantt-head"
  }, /*#__PURE__*/React.createElement("div", {
    className: "gantt-corner"
  }, "\u8D44\u6E90 / \u4EFB\u52A1"), /*#__PURE__*/React.createElement("div", {
    className: "gantt-days"
  }, DAYS.map(([d, dt]) => /*#__PURE__*/React.createElement("div", {
    key: dt,
    className: "gantt-day"
  }, d, /*#__PURE__*/React.createElement("span", null, dt))))), lanes.map(ln => /*#__PURE__*/React.createElement("div", {
    className: "gantt-row",
    key: ln.name
  }, /*#__PURE__*/React.createElement("div", {
    className: "gantt-label"
  }, /*#__PURE__*/React.createElement("div", {
    className: "gl-name"
  }, /*#__PURE__*/React.createElement("a", {
    href: "#",
    onClick: e => {
      e.preventDefault();
      window.APSDetail && window.APSDetail.open(ln.name);
    },
    style: {
      color: "var(--ui-text)",
      textDecoration: "none",
      cursor: "pointer"
    }
  }, ln.name)), /*#__PURE__*/React.createElement("div", {
    className: "gl-meta"
  }, ln.meta), /*#__PURE__*/React.createElement(Meter, {
    value: ln.v,
    style: {
      marginTop: 7
    }
  })), /*#__PURE__*/React.createElement("div", {
    className: "gantt-lane"
  }, ln.bars.map((b, i) => {
    const mb = (b.label || "").match(/B\d{6}-\d{3}/);
    const code = mb ? mb[0] : null;
    return /*#__PURE__*/React.createElement(window.APSDesignSystem_edbc5d.GanttBar, _extends({
      key: i
    }, b, {
      style: {
        cursor: code ? "pointer" : "default"
      },
      onClick: () => {
        if (code && window.APSDetail) window.APSDetail.open(code);
      }
    }), b.label);
  }))))));
}
window.GanttScreen = GanttScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/GanttScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/ProcessNative.jsx
try { (() => {
// APS Workbench · 工艺 / 物料 / 日历（流程主线 · 方案A）— native screen.
// Replaces the old iframe embed. React renders ONLY the empty .plana root;
// plana-logic.js paints the page into it as real light-DOM nodes, so every
// element is individually selectable / annotatable (the iframe used to expose
// the whole page as a single opaque element) and the screen loads instantly.
function ProcessNative({
  onNav
}) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    const root = ref.current;
    if (root && window.APSPlanAInit) window.APSPlanAInit(root, onNav);
    // No cleanup: React unmounts the .plana subtree (and its modals/toast) wholesale.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return /*#__PURE__*/React.createElement("div", {
    className: "plana",
    ref: ref
  });
}
window.ProcessNative = ProcessNative;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/ProcessNative.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/ReportsScreen.jsx
try { (() => {
// APS Workbench · 统计报表 (reports index) — KPI strip + overdue report table
function ReportsScreen({
  onNav
}) {
  const {
    Panel,
    Badge,
    Button,
    Table,
    Kpi,
    Meter
  } = window.APSDesignSystem_edbc5d;
  const D = window.APSDetail;
  const openLink = code => e => {
    e.preventDefault();
    if (D && D.has(code)) D.open(code);
  };
  const linkStyle = {
    color: "var(--ui-primary)",
    textDecoration: "none",
    cursor: "pointer"
  };
  const cols = [{
    key: "batch",
    title: "批次",
    nowrap: true,
    render: r => /*#__PURE__*/React.createElement("a", {
      href: "#",
      onClick: openLink(r.batch),
      style: {
        ...linkStyle,
        fontWeight: 700,
        fontVariantNumeric: "tabular-nums"
      }
    }, r.batch)
  }, {
    key: "part",
    title: "零件",
    nowrap: true,
    render: r => D && D.has(r.part) ? /*#__PURE__*/React.createElement("a", {
      href: "#",
      onClick: openLink(r.part),
      style: linkStyle
    }, r.part) : r.part
  }, {
    key: "due",
    title: "交期",
    nowrap: true
  }, {
    key: "finish",
    title: "计划完成",
    nowrap: true
  }, {
    key: "late",
    title: "晚交",
    align: "right",
    render: r => /*#__PURE__*/React.createElement("span", {
      style: {
        color: "var(--ui-danger)",
        fontVariantNumeric: "tabular-nums"
      }
    }, r.late, "h")
  }, {
    key: "res",
    title: "卡点资源",
    nowrap: true,
    render: r => D && D.has(r.res) ? /*#__PURE__*/React.createElement("a", {
      href: "#",
      onClick: openLink(r.res),
      style: linkStyle
    }, r.res) : r.res
  }, {
    key: "state",
    title: "状态",
    render: r => /*#__PURE__*/React.createElement(Badge, {
      tone: r.tone,
      dot: true
    }, r.state)
  }];
  const rows = [{
    id: 1,
    batch: "B202605-018",
    part: "P-1008",
    due: "05-24 12:00",
    finish: "05-24 18:00",
    late: 6,
    res: "M-03",
    state: "超期",
    tone: "danger"
  }, {
    id: 2,
    batch: "B202605-024",
    part: "P-1011",
    due: "05-25 16:00",
    finish: "05-26 02:00",
    late: 10,
    res: "M-03",
    state: "超期",
    tone: "danger"
  }, {
    id: 3,
    batch: "B202605-021",
    part: "P-1009",
    due: "05-25 08:00",
    finish: "05-25 09:30",
    late: 1.5,
    res: "M-05",
    state: "接近",
    tone: "warning"
  }];
  const util = [{
    name: "M-03",
    v: 96
  }, {
    name: "M-05",
    v: 89
  }, {
    name: "M-07",
    v: 72
  }, {
    name: "M-12",
    v: 58
  }];
  return /*#__PURE__*/React.createElement(Panel, {
    title: "\u7EDF\u8BA1\u62A5\u8868 \xB7 \u8D85\u671F\u4E0E\u8D1F\u8377",
    description: "\u62A5\u8868\u5165\u53E3\uFF1A\u5148\u7528\u6307\u6807\u5361\u7ED9\u603B\u89C8\uFF0C\u518D\u7528\u660E\u7EC6\u8868\u652F\u6491\u8FFD\u67E5\u3002\u6240\u6709\u6570\u5B57 tabular \u5BF9\u9F50\uFF0C\u53EF\u5BFC\u51FA\u3002",
    headerRight: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "sm",
      onClick: () => D && D.toast("导出超期与负荷报表 · 示例操作")
    }, "\u5BFC\u51FA Excel"), /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      size: "sm",
      onClick: () => onNav("delay")
    }, "\u67E5\u770B\u5EF6\u671F\u8BF4\u660E"))
  }, /*#__PURE__*/React.createElement("div", {
    className: "report-kpis"
  }, /*#__PURE__*/React.createElement(Kpi, {
    label: "\u8D85\u671F\u6279\u6B21",
    value: 3,
    valueColor: "var(--ui-danger)",
    helper: "\u672C\u5468 \xB7 \u8F83\u4E0A\u5468 +1",
    badge: /*#__PURE__*/React.createElement(Badge, {
      tone: "danger",
      dot: true
    }, "\u5173\u6CE8")
  }), /*#__PURE__*/React.createElement(Kpi, {
    label: "\u603B\u62D6\u671F",
    value: "18h",
    helper: "\u7D2F\u8BA1\u665A\u4EA4\u5C0F\u65F6"
  }), /*#__PURE__*/React.createElement(Kpi, {
    label: "\u8D44\u6E90\u5229\u7528\u7387\u5CF0\u503C",
    value: "96%",
    valueColor: "var(--ui-warning)",
    helper: "M-03"
  }), /*#__PURE__*/React.createElement(Kpi, {
    label: "\u6309\u65F6\u5B8C\u6210\u7387",
    value: "86%",
    valueColor: "var(--ui-success)",
    helper: "\u5DF2\u6392\u6279\u6B21\u53E3\u5F84"
  })), /*#__PURE__*/React.createElement("div", {
    className: "report-split"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "sub-title"
  }, "\u8D85\u671F\u660E\u7EC6 ", /*#__PURE__*/React.createElement("span", null, "\xB7 \u6309\u665A\u4EA4\u5C0F\u65F6\u6392\u5E8F")), /*#__PURE__*/React.createElement(Table, {
    columns: cols,
    rows: rows,
    rowKey: "id"
  })), /*#__PURE__*/React.createElement("div", {
    className: "report-load"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sub-title"
  }, "\u8D44\u6E90\u8D1F\u8377"), /*#__PURE__*/React.createElement("div", {
    className: "load-list"
  }, util.map(u => /*#__PURE__*/React.createElement("div", {
    key: u.name,
    className: "load-row"
  }, /*#__PURE__*/React.createElement("div", {
    className: "load-top"
  }, /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("a", {
    href: "#",
    onClick: openLink(u.name),
    style: linkStyle
  }, u.name)), /*#__PURE__*/React.createElement("b", null, u.v, "%")), /*#__PURE__*/React.createElement(Meter, {
    value: u.v
  })))))));
}
window.ReportsScreen = ReportsScreen;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/ReportsScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/app.jsx
try { (() => {
// APS Workbench · router + readiness gate + theme
const TITLES = {
  dashboard: "值班台",
  gantt: "设备 / 人员 / 批次甘特",
  run: "执行排产",
  analysis: "选择排产方案",
  delay: "延期说明",
  reports: "报表中心",
  calib: "工时定额校准",
  batches: "批次管理",
  process: "基础资料",
  field: "现场记录",
  fieldgantt: "现场实际甘特 · 计划 vs 实际",
  basedata: "主数据总览",
  system: "系统管理"
};
function App() {
  const ready = useBundleReady();
  const [view, setView] = React.useState("dashboard");
  const [theme, setTheme] = React.useState(() => document.documentElement.getAttribute("data-theme") || "light");
  const nav = v => {
    setView(v);
    window.scrollTo({
      top: 0
    });
  };

  // 详情抽屉调用：跳到甘特图并高亮指定批次的关键链
  React.useEffect(() => {
    window.APSFocusBatchInGantt = batch => {
      window.__apsPendingGanttFocus = batch || null;
      nav("gantt");
      requestAnimationFrame(() => window.dispatchEvent(new CustomEvent("aps-gantt-focus", {
        detail: batch
      })));
    };
    return () => {
      try {
        delete window.APSFocusBatchInGantt;
      } catch (e) {}
    };
  }, []);
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("aps_kit_theme", next);
    } catch (e) {}
  };
  if (!ready) return /*#__PURE__*/React.createElement(BootScreen, null);

  // Active sidebar highlight: contextual drill-ins map to their parent.
  const activeId = view === "delay" ? "dashboard" : view;
  let screen;
  switch (view) {
    case "dashboard":
      screen = /*#__PURE__*/React.createElement(DashboardScreen, {
        onNav: nav
      });
      break;
    case "gantt":
      screen = /*#__PURE__*/React.createElement(GanttScreen, {
        onNav: nav,
        mode: "gantt"
      });
      break;
    case "run":
      screen = /*#__PURE__*/React.createElement(GanttScreen, {
        onNav: nav,
        mode: "run"
      });
      break;
    case "analysis":
      screen = /*#__PURE__*/React.createElement(AnalysisScreen, {
        onNav: nav
      });
      break;
    case "delay":
      screen = /*#__PURE__*/React.createElement(DelayScreen, {
        onNav: nav
      });
      break;
    case "reports":
      screen = /*#__PURE__*/React.createElement(ReportsScreen, {
        onNav: nav
      });
      break;
    case "calib":
      screen = /*#__PURE__*/React.createElement(CalibScreen, {
        onNav: nav
      });
      break;
    case "batches":
      screen = /*#__PURE__*/React.createElement(BatchesScreen, null);
      break;
    case "process":
      screen = /*#__PURE__*/React.createElement(ProcessNative, {
        onNav: nav
      });
      break;
    case "field":
      screen = /*#__PURE__*/React.createElement(FieldRecordScreen, null);
      break;
    case "fieldgantt":
      screen = /*#__PURE__*/React.createElement(FieldGanttScreen, null);
      break;
    case "basedata":
      screen = /*#__PURE__*/React.createElement(BasicDataScreen, {
        module: "equipment"
      });
      break;
    case "system":
      screen = /*#__PURE__*/React.createElement(BasicDataScreen, {
        module: "system"
      });
      break;
    default:
      screen = /*#__PURE__*/React.createElement(DashboardScreen, {
        onNav: nav
      });
  }
  const flush = view === "process";
  return /*#__PURE__*/React.createElement(AppShell, {
    active: activeId,
    onNav: nav,
    theme: theme,
    onToggleTheme: toggleTheme,
    title: TITLES[view] || "值班台",
    showCapsule: view !== "process",
    flush: flush
  }, screen, flush ? null : /*#__PURE__*/React.createElement("footer", {
    className: "kit-foot"
  }, "\u672C\u9875\u9762\u4F7F\u7528\u793A\u4F8B\u6570\u636E\uFF0C\u4E0D\u4EE3\u8868\u771F\u5B9E\u751F\u4EA7\u7ED3\u679C\uFF1B\u6B63\u5F0F\u4F7F\u7528\u4EE5\u7CFB\u7EDF\u5B9E\u65F6\u6570\u636E\u4E3A\u51C6\u3002"));
}
function useBundleReady() {
  const [ready, setReady] = React.useState(!!(window.APSDesignSystem_edbc5d && window.APSDesignSystem_edbc5d.Panel));
  React.useEffect(() => {
    if (ready) return;
    const id = setInterval(() => {
      if (window.APSDesignSystem_edbc5d && window.APSDesignSystem_edbc5d.Panel) {
        setReady(true);
        clearInterval(id);
      }
    }, 120);
    return () => clearInterval(id);
  }, [ready]);
  return ready;
}
function BootScreen() {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: "70vh",
      display: "grid",
      placeItems: "center",
      color: "var(--ui-muted)",
      fontFamily: "var(--font-family)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 40,
      height: 40,
      margin: "0 auto 12px",
      borderRadius: 10,
      background: "var(--ui-primary)",
      display: "grid",
      placeItems: "center"
    }
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 24 24",
    width: "24",
    height: "24",
    fill: "#fff",
    "aria-hidden": "true"
  }, /*#__PURE__*/React.createElement("rect", {
    x: "4",
    y: "6",
    width: "10",
    height: "3.2",
    rx: "1.6"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "7",
    y: "10.4",
    width: "12",
    height: "3.2",
    rx: "1.6",
    fillOpacity: "0.92"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "4",
    y: "14.8",
    width: "8",
    height: "3.2",
    rx: "1.6",
    fillOpacity: "0.78"
  }))), /*#__PURE__*/React.createElement("div", null, "\u6B63\u5728\u52A0\u8F7D\u8BBE\u8BA1\u7CFB\u7EDF\u7EC4\u4EF6\u2026")));
}
ReactDOM.createRoot(document.getElementById("root")).render(/*#__PURE__*/React.createElement(App, null));
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/app.jsx", error: String((e && e.message) || e) }); }

// ui_kits/workbench/datepicker/aps-datepicker.js
try { (() => {
/* ============================================================
   APS 排产系统 · 日期选择器逻辑（无第三方库）
   - 自动接管页面里所有 <input type="date">（除 [data-aps-skip]），
     以及任何带 [data-aps-date] 的文本输入框。
   - 把原生 type=date 改为 text，挂自定义弹层；value 仍是
     YYYY-MM-DD，选/清后派发 input+change 事件，旧监听照常触发。
   - 读取 min / max / required / disabled / value，越界日期禁用。
   - data-aps-marked="2026-06-19,2026-06-22" 可高亮“已配置”日期。
   - ES6 语法，避免可选链 / 空值合并，兼容旧版 Chrome。
   ============================================================ */
(function () {
  "use strict";

  if (window.APSDatePicker) return;
  var WEEK = ["一", "二", "三", "四", "五", "六", "日"]; // 周一起，与产品口径一致
  var MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];
  var ICON_CAL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + '<rect x="4" y="5" width="16" height="16" rx="2.5"/><path d="M4 10h16M8 3v4M16 3v4"/></svg>';
  var ICON_PREV = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="14 6 8 12 14 18"/></svg>';
  var ICON_NEXT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="10 6 16 12 10 18"/></svg>';
  function pad2(n) {
    return String(n).padStart(2, "0");
  }
  function iso(y, m, d) {
    return y + "-" + pad2(m + 1) + "-" + pad2(d);
  }
  function isoOf(dt) {
    return iso(dt.getFullYear(), dt.getMonth(), dt.getDate());
  }
  function parseISO(s) {
    if (!s || typeof s !== "string") return null;
    var m = s.trim().match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    if (!m) return null;
    var y = +m[1],
      mo = +m[2],
      d = +m[3];
    var dt = new Date(y, mo - 1, d);
    if (dt.getFullYear() !== y || dt.getMonth() !== mo - 1 || dt.getDate() !== d) return null;
    return dt;
  }
  function cmp(a, b) {
    return a < b ? -1 : a > b ? 1 : 0;
  } // ISO 字符串可直接比较

  /* ---------- 单例弹层 ---------- */
  var pop,
    titleEl,
    gridEl,
    weekEl,
    monthsEl,
    target = null,
    view = null,
    repos = null;
  function buildPop() {
    pop = document.createElement("div");
    pop.className = "apsdp-pop";
    pop.setAttribute("role", "dialog");
    pop.setAttribute("aria-label", "选择日期");
    pop.hidden = true;
    pop.innerHTML = '<div class="apsdp-head">' + '<button type="button" class="apsdp-nav" data-nav="-1" aria-label="上个月">' + ICON_PREV + '</button>' + '<button type="button" class="apsdp-title"><span class="apsdp-title-txt"></span><span class="caret"></span></button>' + '<button type="button" class="apsdp-nav" data-nav="1" aria-label="下个月">' + ICON_NEXT + '</button>' + '</div>' + '<div class="apsdp-week"></div>' + '<div class="apsdp-grid"></div>' + '<div class="apsdp-months"></div>' + '<div class="apsdp-foot">' + '<button type="button" class="apsdp-link clear">清除</button>' + '<button type="button" class="apsdp-link today">今天</button>' + '</div>';
    document.body.appendChild(pop);
    titleEl = pop.querySelector(".apsdp-title-txt");
    gridEl = pop.querySelector(".apsdp-grid");
    weekEl = pop.querySelector(".apsdp-week");
    monthsEl = pop.querySelector(".apsdp-months");

    // 星期表头
    var wh = "";
    for (var i = 0; i < 7; i++) wh += '<div class="apsdp-wd' + (i >= 5 ? " is-weekend" : "") + '">' + WEEK[i] + "</div>";
    weekEl.innerHTML = wh;

    // 月份快选
    var mh = "";
    for (var j = 0; j < 12; j++) mh += '<button type="button" class="apsdp-month" data-m="' + j + '">' + MONTHS[j] + "</button>";
    monthsEl.innerHTML = mh;

    // 事件代理
    pop.addEventListener("mousedown", function (e) {
      e.preventDefault();
    }); // 不抢输入框焦点
    pop.addEventListener("click", onPopClick);
  }
  function onPopClick(e) {
    var t = e.target;
    var nav = t.closest ? t.closest("[data-nav]") : null;
    if (nav) {
      stepMonth(+nav.getAttribute("data-nav"));
      return;
    }
    if (t.closest && t.closest(".apsdp-title")) {
      pop.classList.toggle("show-months");
      return;
    }
    var mo = t.closest ? t.closest("[data-m]") : null;
    if (mo) {
      view.m = +mo.getAttribute("data-m");
      pop.classList.remove("show-months");
      render();
      return;
    }
    var day = t.closest ? t.closest(".apsdp-day") : null;
    if (day && !day.disabled) {
      pick(day.getAttribute("data-d"));
      return;
    }
    if (t.closest && t.closest(".apsdp-link.today")) {
      onToday();
      return;
    }
    if (t.closest && t.closest(".apsdp-link.clear")) {
      commit("");
      close();
      return;
    }
  }
  function stepMonth(dir) {
    var m = view.m + dir,
      y = view.y;
    if (m < 0) {
      m = 11;
      y--;
    } else if (m > 11) {
      m = 0;
      y++;
    }
    view.y = y;
    view.m = m;
    render();
  }
  function onToday() {
    var now = new Date();
    var s = isoOf(now);
    if (inRange(s)) {
      commit(s);
      close();
    } else {
      view.y = now.getFullYear();
      view.m = now.getMonth();
      pop.classList.remove("show-months");
      render();
    }
  }
  function inRange(s) {
    var min = target.getAttribute("min"),
      max = target.getAttribute("max");
    if (min && parseISO(min) && cmp(s, min) < 0) return false;
    if (max && parseISO(max) && cmp(s, max) > 0) return false;
    return true;
  }

  // 把日期夹到 [min, max] 内（用于键盘移动，保证总能落在合法日期上）
  function clampISO(s) {
    var min = target.getAttribute("min"),
      max = target.getAttribute("max");
    if (min && parseISO(min) && cmp(s, min) < 0) return min;
    if (max && parseISO(max) && cmp(s, max) > 0) return max;
    return s;
  }
  function pick(s) {
    commit(s);
    close();
  }
  function commit(s) {
    if (!target) return;
    target.value = s;
    target.dispatchEvent(new Event("input", {
      bubbles: true
    }));
    target.dispatchEvent(new Event("change", {
      bubbles: true
    }));
  }
  function markedSet() {
    var raw = target.getAttribute("data-aps-marked");
    var set = {};
    if (raw) raw.split(",").forEach(function (x) {
      var v = x.trim();
      if (v) set[v] = 1;
    });
    return set;
  }
  function render() {
    titleEl.textContent = view.y + " 年 " + (view.m + 1) + " 月";

    // 月份快选当前态
    var mbs = monthsEl.children;
    for (var k = 0; k < mbs.length; k++) mbs[k].classList.toggle("is-current", +mbs[k].getAttribute("data-m") === view.m);
    var first = new Date(view.y, view.m, 1);
    var offset = (first.getDay() + 6) % 7; // 周一起
    var start = new Date(view.y, view.m, 1 - offset);
    var selected = parseISO(target.value);
    var selStr = selected ? isoOf(selected) : "";
    var today = isoOf(new Date());
    var marks = markedSet();
    var html = "";
    for (var i = 0; i < 42; i++) {
      var cur = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
      var s = isoOf(cur);
      var out = cur.getMonth() !== view.m;
      var wknd = cur.getDay() === 0 || cur.getDay() === 6;
      var disabled = !inRange(s);
      var cls = "apsdp-day";
      if (out) cls += " is-out";
      if (wknd) cls += " is-weekend";
      if (s === today) cls += " is-today";
      if (s === selStr) cls += " is-selected";
      if (marks[s]) cls += " is-marked";
      html += '<button type="button" class="' + cls + '" data-d="' + s + '"' + (disabled ? " disabled" : "") + ">" + cur.getDate() + "</button>";
    }
    gridEl.innerHTML = html;

    // 6 行 / 5 行自适应：末行整周都在下月则隐藏，避免空跑一行
    if (gridEl.children.length === 42) {
      var lastRowAllOut = true;
      for (var r = 35; r < 42; r++) if (!gridEl.children[r].classList.contains("is-out")) {
        lastRowAllOut = false;
        break;
      }
      for (var rr = 35; rr < 42; rr++) gridEl.children[rr].style.display = lastRowAllOut ? "none" : "";
    }
  }
  function position() {
    var f = target.__apsdpField || target;
    var r = f.getBoundingClientRect();
    var sx = window.pageXOffset,
      sy = window.pageYOffset;
    var pw = pop.offsetWidth,
      ph = pop.offsetHeight;
    var vw = document.documentElement.clientWidth,
      vh = window.innerHeight;
    var left = r.left + sx;
    if (left + pw > sx + vw - 8) left = sx + vw - pw - 8;
    if (left < sx + 8) left = sx + 8;
    var below = r.bottom + 6,
      above = r.top - 6 - ph;
    var flipUp = r.bottom + 6 + ph > vh && r.top - 6 - ph > 0;
    pop.classList.toggle("flip-up", flipUp);
    pop.style.left = Math.round(left) + "px";
    pop.style.top = Math.round((flipUp ? above : below) + sy) + "px";
  }
  function open(input) {
    target = input;
    var d = parseISO(input.value) || new Date();
    view = {
      y: d.getFullYear(),
      m: d.getMonth()
    };
    pop.classList.remove("show-months");
    pop.hidden = false;
    render();
    position();
    pop.classList.remove("is-anim");
    void pop.offsetWidth;
    pop.classList.add("is-anim");
    if (input.__apsdpField) input.__apsdpField.classList.add("is-open");
    bindDismiss();
  }
  function close() {
    if (pop.hidden) return;
    pop.hidden = true;
    pop.classList.remove("show-months");
    if (target && target.__apsdpField) target.__apsdpField.classList.remove("is-open");
    unbindDismiss();
    target = null;
  }
  function onDocDown(e) {
    if (pop.contains(e.target)) return;
    if (target && target.__apsdpField && target.__apsdpField.contains(e.target)) return;
    close();
  }
  function onKey(e) {
    if (e.key === "Escape") {
      e.stopPropagation();
      close();
      return;
    }
    if (!view) return;
    var step = {
      ArrowLeft: -1,
      ArrowRight: 1,
      ArrowUp: -7,
      ArrowDown: 7
    }[e.key];
    if (step) {
      e.preventDefault();
      var cur = parseISO(target.value);
      var s;
      if (!cur) {
        // 还没选日期：首次按方向键，落在今天（被夹进 min/max 范围内）
        s = clampISO(isoOf(new Date()));
      } else {
        var nx = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + step);
        s = clampISO(isoOf(nx));
      }
      target.value = s;
      var d = parseISO(s);
      view.y = d.getFullYear();
      view.m = d.getMonth();
      render();
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (parseISO(target.value)) {
        commit(target.value);
        close();
      }
    }
  }
  function bindDismiss() {
    document.addEventListener("mousedown", onDocDown, true);
    document.addEventListener("keydown", onKey, true);
    window.addEventListener("resize", reposSoon, true);
    window.addEventListener("scroll", reposSoon, true);
  }
  function unbindDismiss() {
    document.removeEventListener("mousedown", onDocDown, true);
    document.removeEventListener("keydown", onKey, true);
    window.removeEventListener("resize", reposSoon, true);
    window.removeEventListener("scroll", reposSoon, true);
  }
  function reposSoon() {
    if (pop.hidden) return;
    if (repos) return;
    repos = window.requestAnimationFrame(function () {
      repos = null;
      if (!pop.hidden) position();
    });
  }

  /* ---------- 接管输入框 ---------- */
  function enhance(input) {
    if (!input || input.__apsdp) return;
    input.__apsdp = true;
    var field = document.createElement("span");
    field.className = "apsdp-field";
    input.parentNode.insertBefore(field, input);
    field.appendChild(input);
    input.__apsdpField = field;
    input.classList.add("apsdp-input");
    input.setAttribute("autocomplete", "off");
    try {
      input.type = "text";
    } catch (e) {} // 关掉原生日历
    if (!input.getAttribute("placeholder")) input.setAttribute("placeholder", "YYYY-MM-DD");
    var trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "apsdp-trigger";
    trigger.setAttribute("aria-label", "打开日历");
    trigger.innerHTML = ICON_CAL;
    field.appendChild(trigger);
    var toggle = function (e) {
      if (input.disabled || input.readOnly) return;
      if (e) e.preventDefault();
      if (!pop.hidden && target === input) {
        close();
        return;
      }
      open(input);
    };
    trigger.addEventListener("click", toggle);
    // 点击字段任意处（输入框本体或留白）都打开日历，而不仅是图标
    field.addEventListener("click", function (e) {
      if (input.disabled || input.readOnly) return;
      if (e.target.closest && e.target.closest(".apsdp-trigger")) return; // 图标自带开/关
      if (pop.hidden || target !== input) open(input);
    });
    input.addEventListener("focus", function () {
      if (pop.hidden || target !== input) open(input);
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" && (pop.hidden || target !== input)) {
        e.preventDefault();
        open(input);
      }
    });
    // 手输合法日期时同步面板
    input.addEventListener("input", function () {
      if (!pop.hidden && target === input) {
        var d = parseISO(input.value);
        if (d) {
          view.y = d.getFullYear();
          view.m = d.getMonth();
          render();
        }
      }
    });
  }
  function enhanceAll(root) {
    if (!pop) buildPop();
    var scope = root || document;
    var nodes = scope.querySelectorAll('input[type="date"]:not([data-aps-skip]), input[data-aps-date]:not([data-aps-skip])');
    for (var i = 0; i < nodes.length; i++) enhance(nodes[i]);
  }
  window.APSDatePicker = {
    enhance: enhance,
    enhanceAll: enhanceAll
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      enhanceAll();
    });
  } else {
    enhanceAll();
  }
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/datepicker/aps-datepicker.js", error: String((e && e.message) || e) }); }

// ui_kits/workbench/detail-drawer.js
try { (() => {
// APS Workbench · 统一详情抽屉 + 轻提示
// One shared, framework-agnostic right-side drawer for every clickable code/record
// across the app (物料 / 零件 / 工种 / 设备 / 人员 / 供应商 / 批次 / 方案 …).
// Both plana-logic.js (light DOM) and the React screens call window.APSDetail.open(code).
// Styling uses the same --ui-* tokens as the rest of the kit so light/dark both work.
(function () {
  if (window.APSDetail) return;
  var GANTT_LOCATE_LABEL = '在甘特图中定位此批次';

  /* ---------------- one-time CSS ---------------- */
  var CSS = `
  .apsd-backdrop { position: fixed; inset: 0; background: rgb(15 23 42 / .42); z-index: 240; opacity: 0; transition: opacity .18s ease; }
  .apsd-backdrop.on { opacity: 1; }
  .apsd-panel { position: fixed; top: 50%; left: 50%; width: min(516px, 94vw); max-height: min(88vh, 860px); background: var(--ui-card-bg); border: 1px solid var(--ui-border); border-radius: 16px; box-shadow: 0 32px 80px -28px rgb(15 23 42 / .55), 0 8px 24px -16px rgb(15 23 42 / .4); z-index: 241; display: flex; flex-direction: column; overflow: hidden; transform: translate(-50%, -48%) scale(.96); opacity: 0; transition: transform .22s cubic-bezier(.32,.72,0,1), opacity .18s ease; font-family: var(--font-family); color: var(--ui-text); }
  .apsd-panel.on { transform: translate(-50%, -50%) scale(1); opacity: 1; }
  @media (prefers-reduced-motion: reduce) { .apsd-backdrop, .apsd-panel { transition: none; } }

  .apsd-head { display: flex; align-items: flex-start; gap: 13px; padding: 20px 20px 16px; border-bottom: 1px solid var(--ui-border); }
  .apsd-ico { width: 40px; height: 40px; border-radius: 10px; background: var(--ui-primary-soft, var(--ui-surface-muted)); color: var(--ui-primary); display: grid; place-items: center; flex: none; }
  .apsd-htext { flex: 1; min-width: 0; }
  .apsd-kicker { font-size: 11.5px; font-weight: 600; letter-spacing: .03em; color: var(--ui-muted); }
  .apsd-code { font-size: 19px; font-weight: 700; line-height: 1.25; font-variant-numeric: tabular-nums; word-break: break-all; }
  .apsd-name { font-size: 13.5px; color: var(--ui-muted); margin-top: 2px; }
  .apsd-x { flex: none; width: 32px; height: 32px; border: 1px solid var(--ui-border); border-radius: 8px; background: var(--ui-card-bg); color: var(--ui-muted); font-size: 17px; line-height: 1; cursor: pointer; display: grid; place-items: center; transition: background-color .15s, color .15s; }
  .apsd-x:hover { background: var(--ui-surface-muted); color: var(--ui-text); }

  .apsd-statusrow { display: flex; flex-wrap: wrap; gap: 8px; padding: 14px 20px 0; }
  .apsd-body { flex: 1; overflow-y: auto; padding: 16px 20px 22px; }
  .apsd-sec { margin-top: 18px; }
  .apsd-sec:first-child { margin-top: 8px; }
  .apsd-sec-t { font-size: 12px; font-weight: 700; letter-spacing: .04em; color: var(--ui-muted); text-transform: none; margin-bottom: 10px; }
  .apsd-rows { display: grid; grid-template-columns: 104px 1fr; gap: 9px 14px; }
  .apsd-rl { font-size: 13px; color: var(--ui-muted); }
  .apsd-rv { font-size: 13.5px; color: var(--ui-text); font-variant-numeric: tabular-nums; line-height: 1.5; }
  .apsd-rv .apsd-strong { font-weight: 700; }

  .apsd-pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 11px; border-radius: 999px; font-size: 12px; font-weight: 700; border: 1px solid transparent; white-space: nowrap; }
  .apsd-pill .d { width: 6px; height: 6px; border-radius: 50%; flex: none; }
  .apsd-pill.ok { background: var(--ui-success-bg); border-color: var(--ui-success-border); color: var(--ui-success-text); } .apsd-pill.ok .d { background: var(--ui-success); }
  .apsd-pill.warn { background: var(--ui-warning-bg); border-color: var(--ui-warning-border); color: var(--ui-warning-text); } .apsd-pill.warn .d { background: var(--ui-warning); }
  .apsd-pill.danger { background: var(--ui-danger-bg); border-color: var(--ui-danger-border); color: var(--ui-danger-text); } .apsd-pill.danger .d { background: var(--ui-danger); }
  .apsd-pill.info { background: var(--ui-info-bg); border-color: var(--ui-info-border); color: var(--ui-info-text); } .apsd-pill.info .d { background: var(--ui-primary); }
  .apsd-pill.off { background: var(--ui-surface-muted); border-color: var(--ui-border); color: var(--ui-muted); } .apsd-pill.off .d { background: var(--ui-muted); }

  .apsd-chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .apsd-chip { display: inline-flex; align-items: center; padding: 2px 9px; border-radius: 6px; font-size: 12px; font-weight: 600; background: var(--ui-surface-muted); border: 1px solid var(--ui-border); color: var(--ui-text); }
  .apsd-chip.a { background: var(--ui-info-bg); border-color: var(--ui-info-border); color: var(--ui-info-text); }
  .apsd-link { color: var(--ui-primary); font-weight: 600; cursor: pointer; text-decoration: none; font-variant-numeric: tabular-nums; }
  .apsd-link:hover { text-decoration: underline; }

  .apsd-relrow { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 9px 0; border-bottom: 1px solid var(--ui-border); }
  .apsd-relrow:last-child { border-bottom: 0; }
  .apsd-relmeta { font-size: 12.5px; color: var(--ui-muted); }

  .apsd-mini { border: 1px solid var(--ui-border); border-radius: 8px; overflow: hidden; }
  .apsd-mini table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  .apsd-mini th { text-align: left; font-weight: 600; color: var(--ui-muted); background: var(--ui-surface-muted); padding: 7px 10px; border-bottom: 1px solid var(--ui-border); white-space: nowrap; }
  .apsd-mini td { padding: 7px 10px; border-bottom: 1px solid var(--ui-border); color: var(--ui-text); }
  .apsd-mini tr:last-child td { border-bottom: 0; }
  .apsd-mini td.r, .apsd-mini th.r { text-align: right; font-variant-numeric: tabular-nums; }

  .apsd-note { font-size: 12.5px; color: var(--ui-muted); line-height: 1.65; background: var(--ui-surface-muted); border: 1px solid var(--ui-border); border-radius: 8px; padding: 11px 13px; }

  .apsd-meter { height: 8px; border-radius: 999px; background: var(--ui-surface-muted); overflow: hidden; margin-top: 6px; }
  .apsd-meter i { display: block; height: 100%; border-radius: 999px; background: var(--ui-primary); }
  .apsd-meter.warn i { background: var(--ui-warning); } .apsd-meter.danger i { background: var(--ui-danger); } .apsd-meter.ok i { background: var(--ui-success); }

  .apsd-foot { display: flex; gap: 10px; padding: 14px 20px; border-top: 1px solid var(--ui-border); background: var(--ui-surface-muted); }
  .apsd-btn { flex: 1; min-height: 38px; padding: 0 14px; border: 1px solid var(--ui-border); border-radius: 8px; background: var(--ui-card-bg); color: var(--ui-text); font-family: inherit; font-size: 13.5px; font-weight: 600; cursor: pointer; transition: background-color .15s, border-color .15s; }
  .apsd-btn:hover { background: var(--ui-surface-muted); }
  .apsd-btn.primary { background: var(--ui-primary); border-color: var(--ui-primary); color: #fff; }
  .apsd-btn.primary:hover { filter: brightness(.96); background: var(--ui-primary); }

  .apsd-toast { position: fixed; left: 50%; bottom: 28px; transform: translate(-50%, 16px); z-index: 260; display: flex; align-items: center; gap: 9px; max-width: min(440px, 90vw); padding: 11px 16px; border-radius: 10px; background: var(--ui-text); color: var(--ui-bg); font-family: var(--font-family); font-size: 13px; box-shadow: 0 12px 30px -10px rgb(15 23 42 / .5); opacity: 0; pointer-events: none; transition: opacity .2s ease, transform .2s ease; }
  .apsd-toast.on { opacity: 1; transform: translate(-50%, 0); }
  .apsd-toast .d { width: 7px; height: 7px; border-radius: 50%; background: var(--ui-success); flex: none; }
  `;
  var st = document.createElement('style');
  st.id = 'apsd-style';
  st.textContent = CSS;
  document.head.appendChild(st);

  /* ---------------- icons ---------------- */
  var ICO = {
    cube: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
    route: '<circle cx="6" cy="6" r="2.4"/><circle cx="18" cy="18" r="2.4"/><path d="M8.4 6H15a3 3 0 010 6H9a3 3 0 000 6h6.6"/>',
    wrench: '<path d="M15 5.2a3.6 3.6 0 00-4.7 4.6L4 16.1 7.9 20l6.3-6.3A3.6 3.6 0 0018.8 9l-2.2 2.2-2-2L16.8 7z"/>',
    machine: '<path d="M3 20h18"/><path d="M5 20V9l5 3V9l5 3V6l4 2v12"/>',
    users: '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 3-5 6-5s6 1.7 6 5"/><path d="M16 5.5a3 3 0 010 6M21.5 20c0-2.2-1.2-3.6-3.2-4.3"/>',
    truck: '<path d="M3 6h11v9H3z"/><path d="M14 9h3.5L21 12.2V15h-7z"/><circle cx="7" cy="18" r="1.9"/><circle cx="17" cy="18" r="1.9"/>',
    box: '<path d="M3 7l9-4 9 4v10l-9 4-9-4V7z"/><path d="M3 7l9 4 9-4M12 11v10"/>',
    chart: '<path d="M4 5v15h16"/><path d="M7 14l4-4 3 3 5-6"/>',
    scale: '<path d="M12 4v16M7 21h10"/><path d="M5 8h14M12 4l7 4M12 4L5 8"/><path d="M5 8l-2.6 5h5.2zM19 8l-2.6 5h5.2z"/>'
  };
  function svg(name) {
    return '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICO[name] || ICO.box) + '</svg>';
  }

  /* ---------------- helpers ---------------- */
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function pill(tone, label) {
    return '<span class="apsd-pill ' + tone + '"><span class="d"></span>' + esc(label) + '</span>';
  }
  function chips(arr, cls) {
    return '<span class="apsd-chips">' + (arr || []).map(function (x) {
      return '<span class="apsd-chip ' + (cls || '') + '">' + esc(x) + '</span>';
    }).join('') + '</span>';
  }
  function rows(pairs) {
    return '<div class="apsd-rows">' + pairs.filter(Boolean).map(function (p) {
      return '<div class="apsd-rl">' + esc(p[0]) + '</div><div class="apsd-rv">' + (p[1] == null ? '<span style="color:var(--ui-muted)">—</span>' : p[1]) + '</div>';
    }).join('') + '</div>';
  }
  function sec(title, html) {
    return '<div class="apsd-sec">' + (title ? '<div class="apsd-sec-t">' + esc(title) + '</div>' : '') + html + '</div>';
  }
  function relList(items) {
    // items: {code, meta} -> clickable cross-links
    return '<div>' + items.map(function (it) {
      var right = it.meta ? '<span class="apsd-relmeta">' + esc(it.meta) + '</span>' : '';
      var left = RECORDS[it.code] ? '<a class="apsd-link" data-apsd-go="' + esc(it.code) + '">' + esc(it.label || it.code) + '</a>' : '<span class="apsd-strong">' + esc(it.label || it.code) + '</span>';
      return '<div class="apsd-relrow">' + left + right + '</div>';
    }).join('') + '</div>';
  }
  function miniTable(head, body) {
    return '<div class="apsd-mini"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>';
  }

  /* ---------------- type config ---------------- */
  var TYPES = {
    material: {
      icon: 'cube',
      kicker: '物料主数据'
    },
    part: {
      icon: 'route',
      kicker: '零件工艺'
    },
    op_int: {
      icon: 'wrench',
      kicker: '自制工种 · 工时口径'
    },
    op_ext: {
      icon: 'wrench',
      kicker: '外协工种 · 周期口径'
    },
    equip: {
      icon: 'machine',
      kicker: '设备资源'
    },
    people: {
      icon: 'users',
      kicker: '人员资源'
    },
    supplier: {
      icon: 'truck',
      kicker: '外协供应商'
    },
    batch: {
      icon: 'box',
      kicker: '生产批次'
    },
    plan: {
      icon: 'chart',
      kicker: '排产方案'
    },
    calib: {
      icon: 'scale',
      kicker: '工时定额校准'
    }
  };

  /* ---------------- records ---------------- */
  // status: [tone, label]; body(rec) returns inner HTML; foot optional.
  function R(o) {
    RECORDS[o.code] = o;
  }
  var RECORDS = {};

  // —— 物料 ——
  [['M-2001', '45# 圆钢 Ø120', ['ok', '启用'], 'Ø120 × 2000', '1,240 kg', 'kg', ['T-1008', 'T-1009']], ['M-2008', '6061 铝板 12mm', ['ok', '启用'], '1220 × 2440', '86 张', '张', ['T-1021']], ['M-2015', '40Cr 锻件毛坯', ['warn', '低库存'], 'Ø200 锻坯', '32 件', '件', ['T-1011']], ['M-2031', '不锈钢 304 棒', ['ok', '启用'], 'Ø60 × 3000', '410 kg', 'kg', []], ['M-2044', '紧固件套件 A', ['off', '停用'], 'M8 / M10 混装', '2,300 套', '套', []], ['WL-2201', '45# 钢棒料', ['ok', '已齐套'], 'Ø120 棒料', '齐套率 100%', 'kg', ['T-1008']], ['WL-2208', '铸铝件', ['warn', '待补料'], '铸铝毛坯', '齐套率 80%', '件', ['T-1009']], ['WL-2215', '密封圈', ['danger', '缺料'], '橡胶密封', '齐套率 60%', '件', ['T-1004']]].forEach(function (m) {
    R({
      type: 'material',
      code: m[0],
      name: m[1],
      status: m[2],
      body: function () {
        return rows([['规格', esc(m[3])], ['库存', '<span class="apsd-strong">' + esc(m[4]) + '</span>'], ['计量单位', esc(m[5])], ['状态', pill(m[2][0], m[2][1])]]) + (m[6].length ? sec('被以下零件引用', relList(m[6].map(function (c) {
          return {
            code: c,
            meta: PARTNAME[c] || ''
          };
        }))) : '') + sec('', '<div class="apsd-note">物料主数据；批次物料需求在「批次管理」里按批引用这里的主数据。低库存 / 缺料会影响批次齐套结果。</div>');
      },
      foot: ['编辑物料', '调整库存']
    });
  });

  // —— 零件 / 工艺 ——
  var PARTNAME = {
    'T-1008': '回转壳体 A',
    'T-1009': '回转壳体 B',
    'T-1011': '端盖 C',
    'T-1014': '法兰 D',
    'T-1021': '支座 E',
    'T-1006': '轴套 F',
    'T-1004': '连接板 G',
    'P-1042': '泵体 H',
    'P-1008': '回转壳体 A',
    'P-1009': '回转壳体 B',
    'P-1011': '端盖 C'
  };
  var PART_ROUTE = {
    'T-1008': [['5', '数铣', '自制'], ['10', '钳工', '自制'], ['20', '数车', '自制'], ['30', '电镀', '外协'], ['35', '发黑', '外协'], ['40', '总检', '自制']],
    'T-1009': [['5', '数铣', '自制'], ['10', '钳工', '自制'], ['20', '数车', '自制'], ['30', '精磨', '自制'], ['40', '总检', '自制']],
    'T-1011': [['5', '数车', '自制'], ['10', '钻孔', '自制'], ['20', '热处理', '外协'], ['25', '喷涂', '外协'], ['30', '总检', '自制']],
    'T-1021': [['5', '数铣', '自制'], ['10', '数车', '自制'], ['20', '钻孔', '自制'], ['30', '发黑', '外协'], ['40', '总检', '自制'], ['45', '表处理', '自制']],
    'P-1042': [['20', '数铣', '自制'], ['30', '钳工', '自制'], ['50', '总检', '自制']]
  };
  [['T-1008', ['ok', '已解析'], '42.5h', '自制 5 · 外协 2'], ['T-1009', ['ok', '已解析'], '38.0h', '自制 5'], ['T-1011', ['warn', '待复核'], '21.0h', '自制 3 · 外协 2'], ['T-1014', ['warn', '未解析'], '—', '待生成'], ['T-1021', ['ok', '已解析'], '36.0h', '自制 4 · 外协 1'], ['T-1006', ['ok', '已解析'], '28.0h', '自制 4'], ['T-1004', ['notice', '草稿'], '12.5h', '待生成'], ['P-1042', ['ok', '已解析'], '32.0h', '自制 3']].forEach(function (p) {
    var rt = PART_ROUTE[p[0]];
    R({
      type: 'part',
      code: p[0],
      name: PARTNAME[p[0]] || '',
      status: p[1],
      body: function () {
        var info = rows([['名称', esc(PARTNAME[p[0]] || '—')], ['标准工时', '<span class="apsd-strong">' + esc(p[2]) + '</span>'], ['自制 / 外协', esc(p[3])], ['解析状态', pill(p[1][0], p[1][1])]]);
        var routeSec = rt ? sec('工艺路线 · ' + rt.length + ' 道工序', miniTable('<th style="width:54px">工序</th><th>工种</th><th class="r" style="width:70px">归属</th>', rt.map(function (o) {
          var attr = o[2] === '外协' ? '<span class="apsd-chip a">外协</span>' : '<span class="apsd-chip">自制</span>';
          return '<tr><td class="r"><b>' + o[0] + '</b></td><td>' + esc(o[1]) + '</td><td class="r">' + attr + '</td></tr>';
        }).join(''))) : sec('', '<div class="apsd-note">该零件尚未导入工艺路线，按 ① 路线 → ② 归属 → ③ 工时 三步推进后即可参与排产。</div>');
        return info + routeSec;
      },
      foot: ['打开工艺详情', '导出清单']
    });
  });

  // —— 自制工种 ——
  [['OT001', '数铣', '6', '14', '主力工序，设备充足', ['EQ-01'], ['P-101', 'P-133']], ['OT002', '数车', '5', '11', '—', ['EQ-04'], ['P-101', 'P-133']], ['OT003', '钳工', '3', '9', '瓶颈工序，人员偏紧', ['EQ-12'], ['P-126', 'P-133']], ['OT004', '精磨', '2', '6', '关键工序', ['EQ-09'], ['P-118']], ['OT006', '总检', '1', '4', '关键工序 · 必检', [], ['P-118']]].forEach(function (o) {
    R({
      type: 'op_int',
      code: o[0],
      name: o[1],
      status: ['info', '自制'],
      body: function () {
        return rows([['工种名称', '<span class="apsd-strong">' + esc(o[1]) + '</span>'], ['可用设备', esc(o[2]) + ' 台'], ['可用人员', esc(o[3]) + ' 人'], ['排产口径', '工时（换型 + 单件）'], ['产能备注', o[4] === '—' ? null : esc(o[4])]]) + (o[5].length ? sec('关联设备', relList(o[5].map(function (c) {
          return {
            code: c,
            meta: EQUIPNAME[c] || ''
          };
        }))) : '') + (o[6].length ? sec('可承接人员', relList(o[6].map(function (c) {
          return {
            code: c,
            meta: PEOPLENAME[c] || ''
          };
        }))) : '');
      },
      foot: ['查看绑定', '编辑工种']
    });
  });

  // —— 外协工种 ——
  [['OT051', '电镀', '分别设置', '常用表面处理，多家供应商', ['S-01', 'S-07']], ['OT052', '发黑', '分别设置', '—', ['S-01']], ['OT053', '热处理', '合并设置', '需炉前确认整组周期', ['S-02']], ['OT054', '喷涂', '分别设置', '单一供应商', ['S-05']]].forEach(function (o) {
    R({
      type: 'op_ext',
      code: o[0],
      name: o[1],
      status: ['info', '外协'],
      body: function () {
        return rows([['工种名称', '<span class="apsd-strong">' + esc(o[1]) + '</span>'], ['周期策略', esc(o[2])], ['排产口径', '周期（天）'], ['备注', o[3] === '—' ? null : esc(o[3])]]) + (o[4].length ? sec('可承接供应商', relList(o[4].map(function (c) {
          return {
            code: c,
            meta: SUPNAME[c] || ''
          };
        }))) : '');
      },
      foot: ['查看供应商', '编辑工种']
    });
  });

  // —— 设备 ——
  var EQUIPNAME = {
    'EQ-01': '立式加工中心 VMC-850',
    'EQ-04': '数控车床 CK-6150',
    'EQ-09': '平面磨床 M7140',
    'EQ-12': '钳工台 · 联合',
    'M-03': '五轴加工中心',
    'M-05': '卧式加工中心',
    'M-07': '立式加工中心',
    'M-12': '三坐标检测',
    'M-18': '数控车床',
    'M-21': '线切割'
  };
  [['EQ-01', '立式加工中心 VMC-850', '数铣', '设备组 A', ['ok', '可用'], null, null], ['EQ-04', '数控车床 CK-6150', '数车', '设备组 A', ['ok', '可用'], null, null], ['EQ-09', '平面磨床 M7140', '精磨', '设备组 B', ['warn', '检修'], null, null], ['EQ-12', '钳工台 · 联合', '钳工', '设备组 C', ['ok', '可用'], null, null], ['M-03', '五轴加工中心', '精加工', '设备组 A', ['warn', '接近满载'], 12, 96], ['M-05', '卧式加工中心', '预加工', '设备组 A', ['warn', '接近满载'], 9, 89], ['M-07', '立式加工中心', '组装', '设备组 B', ['ok', '正常'], 7, 72], ['M-12', '三坐标检测', '检验', '设备组 C', ['ok', '正常'], 5, 58], ['M-18', '数控车床', '车加工', '设备组 A', ['off', '有余量'], 3, 34], ['M-21', '线切割', '特种加工', '设备组 D', ['danger', '停机维护'], 0, 0]].forEach(function (e) {
    R({
      type: 'equip',
      code: e[0],
      name: e[1],
      status: e[4],
      body: function () {
        var util = e[6] != null ? '<div><span class="apsd-strong">' + e[6] + '%</span><div class="apsd-meter ' + (e[6] >= 90 ? 'danger' : e[6] >= 75 ? 'warn' : e[6] === 0 ? 'danger' : 'ok') + '"><i style="width:' + Math.max(e[6], 3) + '%"></i></div></div>' : null;
        return rows([['设备名称', '<span class="apsd-strong">' + esc(e[1]) + '</span>'], ['绑定工序', '<span class="apsd-chip">' + esc(e[2]) + '</span>'], ['设备组', esc(e[3])], ['状态', pill(e[4][0], e[4][1])], e[5] != null ? ['本周任务', e[5] + ' 项'] : null, util ? ['本周利用率', util] : null]) + sec('', '<div class="apsd-note">每台设备绑定一个自制工种，提供该工种的可用产能时段。利用率 ≥ 90% 视为接近满载，排产时优先避让。</div>');
      },
      foot: ['查看甘特', '编辑设备']
    });
  });

  // —— 人员 ——
  var PEOPLENAME = {
    'P-101': '张伟',
    'P-118': '李娜',
    'P-126': '王强',
    'P-133': '赵敏',
    'P-021': '张三',
    'P-024': '李四',
    'P-030': '王五',
    'P-033': '赵六'
  };
  [['P-101', '张伟', ['数铣', '数车'], '白班', ['ok', '在岗'], '40h'], ['P-118', '李娜', ['精磨', '总检'], '白班', ['ok', '在岗'], '38h'], ['P-126', '王强', ['钳工'], '两班倒', ['warn', '请假'], '0h'], ['P-133', '赵敏', ['数车', '钻孔', '钳工'], '白班', ['ok', '在岗'], '42h'], ['P-021', '张三', ['精加工'], '一班', ['warn', '接近满载'], '42h'], ['P-024', '李四', ['组装'], '一班', ['ok', '有余量'], '31h'], ['P-030', '王五', ['检验'], '二班', ['ok', '正常'], '38h'], ['P-033', '赵六', ['车加工'], '二班', ['danger', '请假'], '0h']].forEach(function (p) {
    R({
      type: 'people',
      code: p[0],
      name: p[1],
      status: p[4],
      body: function () {
        return rows([['姓名', '<span class="apsd-strong">' + esc(p[1]) + '</span>'], ['技能工种', chips(p[2])], ['班次', esc(p[3])], ['本周排班', '<span class="apsd-strong">' + esc(p[5]) + '</span>'], ['状态', pill(p[4][0], p[4][1])]]) + sec('', '<div class="apsd-note">人员按多技能矩阵参与排产，一人可覆盖多个自制工种。请假 / 异常状态会从当班产能中剔除。</div>');
      },
      foot: ['查看排班', '编辑人员']
    });
  });

  // —— 供应商 ——
  var SUPNAME = {
    'S-01': '华表面处理',
    'S-02': '金鼎热处理',
    'S-05': '宏达喷涂',
    'S-07': '精工电镀'
  };
  [['S-01', '华表面处理', ['电镀', '发黑'], '3 天', ['ok', '启用']], ['S-02', '金鼎热处理', ['热处理'], '4 天', ['ok', '启用']], ['S-05', '宏达喷涂', ['喷涂'], '2 天', ['warn', '待复核']], ['S-07', '精工电镀', ['电镀'], '3 天', ['off', '停用']]].forEach(function (s) {
    R({
      type: 'supplier',
      code: s[0],
      name: s[1],
      status: s[4],
      body: function () {
        return rows([['供应商', '<span class="apsd-strong">' + esc(s[1]) + '</span>'], ['可做外协工种', chips(s[2], 'a')], ['默认周期', '<span class="apsd-strong">' + esc(s[3]) + '</span>'], ['状态', pill(s[4][0], s[4][1])]]) + sec('', '<div class="apsd-note">供应商绑定外协工种并给出默认周期（天）；连续外协工序可按整组周期计。待复核 / 停用的不参与排产。</div>');
      },
      foot: ['查看承接工种', '编辑供应商']
    });
  });

  // —— 批次 ——
  [['B202605-018', 'T-1008', 12, '05-24 12:00', '30 / 60', ['danger', '超期'], 'M-03'], ['B202605-021', 'T-1009', 8, '05-25 08:00', '20 / 50', ['warn', '接近满载'], 'M-05'], ['B202605-019', 'T-1006', 6, '05-25 14:00', '40 / 50', ['ok', '正常'], 'M-07'], ['B202605-017', 'T-1004', 10, '05-26 10:00', '10 / 40', ['notice', '外协在途'], 'M-07'], ['B202605-024', 'T-1011', 4, '05-26 16:00', '待排', ['off', '待排'], 'M-03'], ['B202605-016', 'T-1006', 5, '05-24 09:00', '50 / 50', ['ok', '正常'], 'M-12'], ['B202605-013', 'T-1009', 7, '05-23 16:00', '50 / 50', ['ok', '正常'], 'M-12']].forEach(function (b) {
    var tone = b[5][0] === 'notice' ? 'info' : b[5][0];
    R({
      type: 'batch',
      code: b[0],
      name: (PARTNAME[b[1]] || '') + ' · ' + b[2] + ' 件',
      status: [tone, b[5][1]],
      body: function () {
        return rows([['图号', RECORDS[b[1]] ? '<a class="apsd-link" data-apsd-go="' + b[1] + '">' + b[1] + '</a> <span style="color:var(--ui-muted)">' + esc(PARTNAME[b[1]] || '') + '</span>' : esc(b[1])], ['数量', '<span class="apsd-strong">' + b[2] + ' 件</span>'], ['交期', esc(b[3])], ['工序进度', esc(b[4])], ['卡点资源', RECORDS[b[6]] ? '<a class="apsd-link" data-apsd-go="' + b[6] + '">' + b[6] + '</a>' : esc(b[6])], ['状态', pill(tone, b[5][1])]]) + sec('执行时间线', miniTable('<th>节点</th><th class="r" style="width:120px">时间</th>', '<tr><td>下料 / 备料</td><td class="r">05-22 08:00</td></tr><tr><td>预加工</td><td class="r">05-23 14:00</td></tr><tr><td>精加工（卡点）</td><td class="r" style="color:var(--ui-danger)">05-24 排队</td></tr><tr><td>计划完成</td><td class="r">05-24 18:00</td></tr>')) + sec('', '<div class="apsd-note">批次沿工序链推进；卡点资源决定能否按期完成。点击图号 / 资源可继续巡检。</div>');
      },
      foot: [GANTT_LOCATE_LABEL, '查看延期说明']
    });
  });

  // —— 方案 ——
  [['关键工序优先', ['ok', '已采用'], 0, 2, '18 小时', '5.8 天', 12, '把超期批次压到最低、总拖期更短；代价是 M-03 更忙、换型多 2 次。'], ['基准方案', ['off', '对照'], 0, 3, '24 小时', '5.6 天', 10, '系统默认算法的代表结果，作为对照基线。'], ['保交期优先', ['info', '备选'], 0, 2, '18 小时', '5.9 天', 13, '进一步压交期风险，但总工期略长、换型最多。']].forEach(function (p) {
    R({
      type: 'plan',
      code: p[0],
      name: '排产方案',
      status: p[1],
      body: function () {
        return rows([['方案标签', pill(p[1][0], p[1][1])], ['失败工序', p[2] + ' 道'], ['超期批次', '<span class="apsd-strong">' + p[3] + ' 个</span>'], ['总拖期', esc(p[4])], ['总工期', esc(p[5])], ['换型次数', p[6] + ' 次']]) + sec('结论', '<div class="apsd-note">' + esc(p[7]) + '</div>');
      },
      foot: ['查看甘特', '查看延期说明']
    });
  });

  /* ---------------- render / open / close ---------------- */
  var cur = null;
  function buildPanel(rec) {
    var t = TYPES[rec.type] || {
      icon: 'box',
      kicker: ''
    };
    var statusPill = rec.status ? pill(rec.status[0], rec.status[1]) : '';
    var footItems = (rec.foot || []).filter(function (label) {
      // 从甘特图点开的批次卡：隐藏“定位此批次”（你本就在甘特图上）
      return !(label === GANTT_LOCATE_LABEL && cur && cur.from === 'gantt');
    });
    var foot = footItems.map(function (label, i) {
      return '<button class="apsd-btn' + (i === 0 ? ' primary' : '') + '" data-apsd-act="' + esc(label) + '">' + esc(label) + '</button>';
    }).join('');
    return '<div class="apsd-head">' + '<span class="apsd-ico">' + svg(t.icon) + '</span>' + '<div class="apsd-htext"><div class="apsd-kicker">' + esc(t.kicker) + '</div>' + '<div class="apsd-code">' + esc(rec.code) + '</div>' + (rec.name ? '<div class="apsd-name">' + esc(rec.name) + '</div>' : '') + '</div>' + '<button class="apsd-x" data-apsd-close aria-label="关闭">✕</button>' + '</div>' + (statusPill ? '<div class="apsd-statusrow">' + statusPill + '</div>' : '') + '<div class="apsd-body">' + rec.body() + '</div>' + (foot ? '<div class="apsd-foot">' + foot + '</div>' : '');
  }
  function close() {
    if (!cur) return;
    var c = cur;
    cur = null;
    c.panel.classList.remove('on');
    c.bg.classList.remove('on');
    document.removeEventListener('keydown', onKey);
    setTimeout(function () {
      if (c.bg.parentNode) c.bg.parentNode.removeChild(c.bg);
      if (c.panel.parentNode) c.panel.parentNode.removeChild(c.panel);
    }, 230);
  }
  function onKey(e) {
    if (e.key === 'Escape') close();
  }
  function render(rec) {
    cur.panel.innerHTML = buildPanel(rec);
    cur.panel.querySelector('[data-apsd-close]').addEventListener('click', close);
    cur.panel.querySelectorAll('[data-apsd-go]').forEach(function (a) {
      a.addEventListener('click', function (e) {
        e.preventDefault();
        var code = a.getAttribute('data-apsd-go');
        if (RECORDS[code]) {
          cur.code = code;
          cur.from = null;
          render(RECORDS[code]);
          cur.panel.querySelector('.apsd-body').scrollTop = 0;
        }
      });
    });
    cur.panel.querySelectorAll('[data-apsd-act]').forEach(function (b) {
      b.addEventListener('click', function () {
        var act = b.getAttribute('data-apsd-act');
        if (act === GANTT_LOCATE_LABEL) {
          var batch = cur.code;
          close();
          if (window.APSFocusBatchInGantt) window.APSFocusBatchInGantt(batch);else toast(act + ' · 示例操作（演示界面）');
          return;
        }
        toast(act + ' · 示例操作（演示界面）');
      });
    });
  }
  function open(codeOrRec, typeHint, opts) {
    var rec = typeof codeOrRec === 'string' ? RECORDS[codeOrRec] : codeOrRec;
    if (!rec) rec = genericRecord(codeOrRec, typeHint);
    if (!rec) return;
    var from = opts && opts.from || null;
    if (cur) {
      cur.code = rec.code;
      cur.from = from;
      render(rec);
      cur.panel.querySelector('.apsd-body').scrollTop = 0;
      return;
    }
    var bg = document.createElement('div');
    bg.className = 'apsd-backdrop';
    var panel = document.createElement('aside');
    panel.className = 'apsd-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    document.body.appendChild(bg);
    document.body.appendChild(panel);
    cur = {
      bg: bg,
      panel: panel,
      code: rec.code,
      from: from
    };
    render(rec);
    bg.addEventListener('click', close);
    document.addEventListener('keydown', onKey);
    requestAnimationFrame(function () {
      bg.classList.add('on');
      panel.classList.add('on');
    });
  }

  // fallback for any code we don't have a rich record for
  function genericRecord(code, typeHint) {
    if (!code) return null;
    var type = typeHint || 'batch';
    return {
      type: type,
      code: String(code),
      name: '',
      status: null,
      body: function () {
        return rows([['编号', '<span class="apsd-strong">' + esc(code) + '</span>']]) + sec('', '<div class="apsd-note">该条目的明细在正式系统中按编号联动展示。当前为示例界面。</div>');
      },
      foot: ['知道了']
    };
  }

  /* ---------------- toast ---------------- */
  var _toastEl, _toastT;
  function toast(msg) {
    if (!_toastEl) {
      _toastEl = document.createElement('div');
      _toastEl.className = 'apsd-toast';
      document.body.appendChild(_toastEl);
    }
    _toastEl.innerHTML = '<span class="d"></span><span>' + esc(msg) + '</span>';
    _toastEl.classList.add('on');
    clearTimeout(_toastT);
    _toastT = setTimeout(function () {
      _toastEl.classList.remove('on');
    }, 2600);
  }
  window.APSDetail = {
    open: open,
    close: close,
    toast: toast,
    has: function (c) {
      return !!RECORDS[c];
    },
    RECORDS: RECORDS
  };
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/detail-drawer.js", error: String((e && e.message) || e) }); }

// ui_kits/workbench/plana-logic.js
try { (() => {
// APS Workbench · 基础资料（流程主线 · 方案A）native logic
// Ported from PlanAEmbed.html — runs in the page's own light DOM (no iframe),
// so every node inside is real and individually selectable/annotatable.
// window.APSPlanAInit(root, onNav): paints the page shell into `root` (a .plana
// element React renders empty), then wires the rail + content + modals. Modals
// and the toast are appended INTO `root` so their .plana-scoped CSS applies.
// Theme is handled globally by the app (html[data-theme]); the embed's own theme
// toggle / postMessage plumbing was dropped.

window.APSPlanAInit = function (root, onNav) {
  if (!root) return;
  root.innerHTML = "<section class=\"rail\" aria-label=\"产能链主线\"><div class=\"rail-bar\"><span class=\"rail-cap\">产能链主线</span><span class=\"rail-hint\">点击任一环节进入维护</span><span class=\"rail-status\" id=\"railStatus\"></span></div><div class=\"flow\" id=\"flow\"></div><div class=\"rail-foot\" id=\"railFoot\"></div></section><section class=\"content\" id=\"content\"></section>";

  /* ---------------- icons ---------------- */
  var IP = {
    box: '<path d="M3 7l9-4 9 4v10l-9 4-9-4V7z"/><path d="M3 7l9 4 9-4M12 11v10"/>',
    database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.6 3.6 3 8 3s8-1.4 8-3V5"/><path d="M4 12c0 1.6 3.6 3 8 3s8-1.4 8-3"/>',
    play: '<circle cx="12" cy="12" r="9"/><path d="M10 8.5l6 3.5-6 3.5v-7z"/>',
    home: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>',
    gantt: '<path d="M4 7h10M4 12h15M4 17h7"/>',
    chart: '<path d="M4 5v15h16"/><path d="M7 14l4-4 3 3 5-6"/>',
    users: '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 3-5 6-5s6 1.7 6 5"/><path d="M16 5.5a3 3 0 010 6M21.5 20c0-2.2-1.2-3.6-3.2-4.3"/>',
    clipboard: '<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9.5 4V3.2h5V4"/><path d="M9 10.5h6M9 14.5h4"/>',
    file: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/><path d="M10 13h6M10 17h6"/>',
    grid: '<rect x="4" y="4" width="7" height="7" rx="1.2"/><rect x="13" y="4" width="7" height="7" rx="1.2"/><rect x="4" y="13" width="7" height="7" rx="1.2"/><rect x="13" y="13" width="7" height="7" rx="1.2"/>',
    settings: '<path d="M4 7h9M18 7h2M4 17h2M11 17h9"/><circle cx="15" cy="7" r="2.2"/><circle cx="8" cy="17" r="2.2"/>',
    calendar: '<rect x="4" y="5" width="16" height="16" rx="2.5"/><path d="M4 10h16M8 3v4M16 3v4"/>',
    cube: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
    route: '<circle cx="6" cy="6" r="2.4"/><circle cx="18" cy="18" r="2.4"/><path d="M8.4 6H15a3 3 0 010 6H9a3 3 0 000 6h6.6"/>',
    wrench: '<path d="M15 5.2a3.6 3.6 0 00-4.7 4.6L4 16.1 7.9 20l6.3-6.3A3.6 3.6 0 0018.8 9l-2.2 2.2-2-2L16.8 7z"/>',
    machine: '<path d="M3 20h18"/><path d="M5 20V9l5 3V9l5 3V6l4 2v12"/>',
    truck: '<path d="M3 6h11v9H3z"/><path d="M14 9h3.5L21 12.2V15h-7z"/><circle cx="7" cy="18" r="1.9"/><circle cx="17" cy="18" r="1.9"/>',
    import: '<path d="M12 3v11M8 10l4 4 4-4M5 20h14"/>',
    export: '<path d="M12 14V3M8 7l4-4 4 4M5 20h14"/>'
  };
  function svg(name, cls) {
    return '<svg class="' + (cls || '') + '" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (IP[name] || '') + '</svg>';
  }

  /* ---------------- sidebar ---------------- */
  var NAV_GROUPS = [{
    title: "① 数据准备",
    items: [{
      id: "process",
      label: "基础资料",
      icon: "database"
    }, {
      id: "batches",
      label: "批次管理",
      icon: "box"
    }]
  }, {
    title: "② 执行排产",
    items: [{
      id: "run",
      label: "执行排产",
      icon: "play"
    }]
  }, {
    title: "③ 看结果",
    items: [{
      id: "dashboard",
      label: "值班台（首页）",
      icon: "home"
    }, {
      id: "gantt",
      label: "设备 / 人员甘特",
      icon: "gantt"
    }, {
      id: "analysis",
      label: "排产分析 · 周计划",
      icon: "chart"
    }]
  }, {
    title: "④ 现场",
    items: [{
      id: "field",
      label: "现场记录",
      icon: "clipboard"
    }]
  }, {
    title: "⑤ 统计分析",
    items: [{
      id: "reports",
      label: "执行复盘 · 报表中心",
      icon: "file"
    }, {
      id: "calib",
      label: "工时定额校准",
      icon: "scale"
    }]
  }, {
    title: "基础数据 · 系统",
    items: [{
      id: "basedata",
      label: "主数据总览",
      icon: "grid"
    }, {
      id: "system",
      label: "系统管理",
      icon: "settings"
    }]
  }];

  /* ---------------- rail model ---------------- */
  var CHAINS = {
    internal: {
      name: '自制链',
      meas: '工时口径',
      tone: 'int',
      icon: 'machine',
      subs: [{
        id: 'op',
        name: '自制工种',
        n: 8,
        unit: '个',
        icon: 'wrench'
      }, {
        id: 'eq',
        name: '设备',
        n: 14,
        unit: '台',
        icon: 'machine'
      }, {
        id: 'pp',
        name: '人员',
        n: 23,
        unit: '人',
        icon: 'users'
      }]
    },
    external: {
      name: '外协链',
      meas: '周期口径',
      tone: 'ext',
      icon: 'truck',
      subs: [{
        id: 'op',
        name: '外协工种',
        n: 4,
        unit: '个',
        icon: 'wrench'
      }, {
        id: 'sup',
        name: '供应商',
        n: 6,
        unit: '家',
        icon: 'truck'
      }]
    }
  };
  var state = {
    node: 'process',
    sub: {
      internal: 'op',
      external: 'op'
    },
    openPart: null,
    opView: 'full',
    stageFilter: 'all',
    openStage: null
  };
  var partModal = null; // { code, repaint, close } — 零件工艺详情以弹出卡片呈现

  /* ---------------- calendar model ---------------- */
  /* cfg keyed "Y-M-D" (M 0-indexed). record: { type:'work'|'rest', hours, eff, prio, note } */
  var calState = {
    y: 2026,
    m: 5,
    cfg: {
      '2026-5-2': {
        type: 'work',
        hours: 8,
        eff: 100,
        prio: '普通'
      },
      '2026-5-4': {
        type: 'work',
        hours: 8,
        eff: 100,
        allowNormal: 'yes',
        allowUrgent: 'yes'
      },
      '2026-5-9': {
        type: 'work',
        hours: 8,
        eff: 100,
        allowNormal: 'yes',
        allowUrgent: 'yes'
      },
      '2026-5-11': {
        type: 'work',
        hours: 8,
        eff: 100,
        allowNormal: 'yes',
        allowUrgent: 'yes'
      },
      '2026-5-16': {
        type: 'work',
        hours: 8,
        eff: 100,
        allowNormal: 'yes',
        allowUrgent: 'yes'
      },
      '2026-5-18': {
        type: 'work',
        hours: 8,
        eff: 100,
        allowNormal: 'yes',
        allowUrgent: 'yes'
      },
      '2026-5-23': {
        type: 'work',
        hours: 8,
        eff: 100,
        allowNormal: 'yes',
        allowUrgent: 'yes'
      },
      '2026-5-25': {
        type: 'work',
        hours: 8,
        eff: 100,
        allowNormal: 'yes',
        allowUrgent: 'yes'
      },
      '2026-5-6': {
        type: 'work',
        hours: 4,
        eff: 100,
        allowNormal: 'no',
        allowUrgent: 'yes',
        note: '周末仅急件加班'
      },
      '2026-5-19': {
        type: 'rest',
        note: '调休'
      }
    }
  };
  var MONTH_ZH = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二'];
  function calKey(d) {
    return calState.y + '-' + calState.m + '-' + d;
  }
  function calDayMeta(d) {
    var dow = new Date(calState.y, calState.m, d).getDay();
    var weekend = dow === 0 || dow === 6;
    var c = calState.cfg[calKey(d)];
    var cls = '',
      tag = '',
      working = !weekend;
    if (c) {
      if (c.type === 'work') {
        var an = c.allowNormal !== 'no'; // default 允许
        var au = c.allowUrgent !== 'no';
        if (!an && !au) {
          // 两项都不允许 = 这天不排产
          working = false;
          cls = weekend ? 'we' : 'rest';
          tag = '停排';
        } else {
          working = true;
          if (weekend) {
            cls = 'rest';
            tag = '加班';
          } else {
            cls = 'cfg';
            tag = (c.hours != null ? c.hours : 8) + 'h';
          }
          if (an && !au) tag += ' 普'; // 仅普通件
          else if (!an && au) tag += ' 急'; // 仅急件
        }
      } else {
        // rest
        working = false;
        if (weekend) {
          cls = 'we';
          tag = '休';
        } else {
          cls = 'rest';
          tag = '调休';
        }
      }
    } else if (weekend) {
      cls = 'we';
      tag = '休';
    }
    return {
      dow: dow,
      weekend: weekend,
      cfg: c,
      cls: cls,
      tag: tag,
      working: working
    };
  }
  function calStats() {
    var dim = new Date(calState.y, calState.m + 1, 0).getDate();
    var workDays = 0,
      configured = 0,
      overrides = 0,
      weekendRest = 0;
    for (var d = 1; d <= dim; d++) {
      var meta = calDayMeta(d);
      if (meta.working) workDays++;
      if (meta.cfg && meta.cfg.type === 'work') configured++;
      if (meta.cls === 'rest') overrides++;
      if (meta.cls === 'we') weekendRest++;
    }
    return {
      workDays: workDays,
      configured: configured,
      overrides: overrides,
      weekendRest: weekendRest
    };
  }
  function renderRail() {
    var f = document.getElementById('flow');
    // 中心枢纽（方案 3）：数据输入 → 工序(两条链) → 工作日历，箭头串联。
    var ARROW = '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6"/></svg>';
    var ARROW15 = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6"/></svg>';
    var CAL_ICO = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + IP.calendar + '</svg>';
    var CHECK = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12.5l5 5 11-11"/></svg>';
    function ioTile(d) {
      var on = state.node === d.node;
      return '<button class="hb-tile io' + (on ? ' on' : '') + '" data-node="' + d.node + '">' + (d.warn ? '<span class="hb-nstat warn"></span>' : '') + '<span class="hb-tico io">' + svg(d.icon) + '</span>' + '<span class="hb-tbody"><span class="hb-tname">' + d.name + '</span>' + '<span class="hb-tmeta">' + d.meta + '</span></span></button>';
    }
    function laneBlock(laneId) {
      var c = CHAINS[laneId];
      var tone = laneId === 'internal' ? 'int' : 'ext';
      var cls = laneId === 'internal' ? 'intl' : 'extl';
      var tiles = c.subs.map(function (s) {
        var on = state.node === laneId && state.sub[laneId] === s.id;
        return '<button class="hb-tile ' + tone + (on ? ' on' : '') + '" data-node="' + laneId + '" data-sub="' + s.id + '">' + '<span class="hb-tico ' + tone + '">' + svg(s.icon) + '</span>' + '<span class="hb-tbody"><span class="hb-tname">' + s.name + '</span>' + '<span class="hb-tmeta">' + s.n + ' ' + s.unit + '</span></span></button>';
      }).join('');
      return '<div class="hb-lane ' + cls + '">' + '<div class="hb-lane-head"><span class="hb-lane-dot"></span><span class="hb-lane-name">' + c.name + '</span>' + '<span class="hb-lane-meas">' + c.meas + '</span>' + '<span class="hb-lane-count">' + c.subs.length + ' 项</span></div>' + '<div class="hb-lane-row">' + tiles + '</div></div>';
    }
    var blkData = '<div class="hb-block hero">' + '<div class="hb-bhead"><span class="hb-bdot io"></span><span class="hb-bname">数据输入</span><span class="hb-bmeas">2 源</span></div>' + '<div class="hb-bbody">' + ioTile({
      node: 'process',
      icon: 'database',
      name: '工艺',
      meta: '12 模板 · 1 待解析',
      warn: true
    }) + ioTile({
      node: 'material',
      icon: 'cube',
      name: '物料',
      meta: '86 条主数据'
    }) + '</div></div>';
    var blkOps = '<div class="hb-block hero hb-ops">' + '<div class="hb-bhead"><span class="hb-bdot fk"></span><span class="hb-bname">工序 · 两条链</span><span class="hb-bnum">5 环节</span></div>' + '<div class="hb-bbody">' + laneBlock('internal') + laneBlock('external') + '</div></div>';
    var WEEK = [['一'], ['二'], ['三'], ['四'], ['五'], ['六', 'rest'], ['日', 'rest']];
    var strip = WEEK.map(function (d) {
      return '<span class="hb-seg ' + (d[1] || '') + '"><span class="hb-sl">' + d[0] + '</span><span class="hb-sb"></span></span>';
    }).join('');
    var blkCal = '<div class="hb-block hero hb-cal-block' + (state.node === 'calendar' ? ' on' : '') + '" data-node="calendar" role="button" tabindex="0">' + '<div class="hb-bhead"><span class="hb-bdot cal"></span><span class="hb-bname">工作日历</span><span class="hb-bmeas">全局</span></div>' + '<div class="hb-bbody">' + '<div class="hb-cal-top"><span class="hb-cal-ico">' + CAL_ICO + '</span>' + '<span class="hb-cal-lead"><span class="hb-cl1">工时 / 调休 / 加班</span><span class="hb-cl2">统一作用于上方两条链口径</span></span></div>' + '<div class="hb-cal-stats">' + '<span class="hb-cs"><span class="hb-csv">8 h</span><span class="hb-csl">标准工时 / 日</span></span>' + '<span class="hb-cs"><span class="hb-csv">5 天</span><span class="hb-csl">本周工作日</span></span>' + '<span class="hb-cs"><span class="hb-csv">六 · 日</span><span class="hb-csl">休息 / 调休</span></span>' + '</div>' + '<div class="hb-cal-strip-cap"><span>本周排班</span>' + '<span class="hb-csc-key"><span class="hb-csc-dot work"></span>工作</span>' + '<span class="hb-csc-key"><span class="hb-csc-dot rest"></span>休息</span></div>' + '<div class="hb-cal-strip">' + strip + '</div>' + '</div></div>';
    f.innerHTML = '<div class="hb-hub">' + blkData + '<div class="hb-flowarr">' + ARROW + '</div>' + blkOps + '<div class="hb-flowarr">' + ARROW + '</div>' + blkCal + '</div>';

    // ---- 状态徽标（标题右侧）----
    var st = document.getElementById('railStatus');
    if (st) st.innerHTML = '<span class="rail-pill warn">1 项待处理</span>';

    // ---- 页脚：产能就绪度 + 下一步 ----
    var foot = document.getElementById('railFoot');
    if (foot) {
      foot.innerHTML = '<div class="hb-ready">' + '<div class="hb-r-top">' + '<span class="hb-r-ico">' + CHECK + '</span>' + '<span class="hb-rl1">产能就绪度</span>' + '<span class="hb-rl2">4 / 5 项就绪</span>' + '<span class="hb-r-tag">工艺路线 1 项待解析</span>' + '<span class="hb-r-spacer"></span>' + '<button class="hb-r-next" data-go="batches">下一步 · 批次管理 ' + ARROW15 + '</button>' + '</div>' + '<div class="hb-r-floor"><i style="width:80%"></i></div>' + '</div>';
      var nx = foot.querySelector('[data-go]');
      if (nx) nx.addEventListener('click', function (e) {
        e.stopPropagation();
        if (onNav) onNav('batches');
      });
    }

    // ---- 环节点击 ----
    var scope = document.querySelector('.rail') || f;
    scope.querySelectorAll('[data-node]').forEach(function (el) {
      el.addEventListener('click', function () {
        var nd = el.getAttribute('data-node');
        var sub = el.getAttribute('data-sub');
        state.node = nd;
        if (sub) state.sub[nd] = sub;
        render();
      });
      if (el.getAttribute('role') === 'button') {
        el.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            el.click();
          }
        });
      }
    });
  }

  /* ---------------- table helper ---------------- */
  function table(cols, rows) {
    var head = '<th class="cbx"><input type="checkbox" class="ck-all" aria-label="全选"></th>' + cols.map(function (c) {
      return '<th class="' + (c.r ? 'r' : '') + (c.act ? ' actcol' : '') + '"' + (c.w ? ' style="width:' + c.w + 'px"' : '') + '>' + c.t + '</th>';
    }).join('');
    var body = rows.map(function (r) {
      return '<tr><td class="cbx"><input type="checkbox" class="ck-row"></td>' + r.map(function (cell, i) {
        return '<td class="' + (cols[i].r ? 'r' : '') + (cols[i].act ? ' actcol' : '') + '">' + cell + '</td>';
      }).join('') + '</tr>';
    }).join('');
    return '<div class="card"><div class="card-scroll"><table class="tbl"><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div></div>';
  }
  function actBtns(extra) {
    return '<div class="rowact"><button class="mini">' + (extra || '查看/编辑') + '</button><button class="mini danger">删除</button></div>';
  }
  function pager(total) {
    return '<div class="pager"><span>共 <b class="pgtotal" style="font-variant-numeric:tabular-nums">' + total + '</b> 条</span><span class="grow"></span>' + '<button class="pg">‹</button><span>第 1 / 1 页</span><button class="pg">›</button></div>';
  }
  function statline(items) {
    return '<div class="statline">' + items.map(function (s) {
      return '<div class="stat ' + (s.tone || '') + '"><span class="sv">' + s.v + '</span><span class="sl">' + s.l + '</span></div>';
    }).join('') + '</div>';
  }
  function toolbar(ph, primary, icon, entity) {
    return '<div class="toolbar"><div class="search"><span class="ic">' + svg(icon || 'route').replace('width="18" height="18"', 'width="15" height="15"') + '</span>' + '<input placeholder="' + ph + '"></div><div class="tb-spacer"></div>' + '<span class="selcount" hidden>已选 <b class="selN">0</b> 项</span>' + '<button class="linkbtn clear-sel" hidden>取消</button>' + '<button class="btn danger batch-del"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 7h14M10 7V5h4v2M7 7l1 13h8l1-13"/></svg>批量删除</button>' + '<span class="tb-div"></span>' + '<button class="btn io-btn io-imp" data-entity="' + (entity || '') + '" data-mode="imp"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v11M8 10l4 4 4-4M5 20h14"/></svg>导入</button>' + '<button class="btn io-btn io-exp" data-entity="' + (entity || '') + '" data-mode="exp"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 14V3M8 7l4-4 4 4M5 20h14"/></svg>导出</button>' + '<button class="btn primary add-btn" data-entity="' + (entity || '') + '"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>' + primary + '</button></div>';
  }

  /* ---------------- datasets ---------------- */
  var PARTS = [['<a class="lnk">T-1008</a>', '回转壳体 A', '<span class="route" title="5数铣 10钳 20数车 30外协电镀 35外协发黑 40总检">5数铣 10钳 20数车 30外协电镀 35外协发黑 40总检</span>', '<span class="chipline"><span class="chip b">自制 5</span><span class="chip a">外协 2</span></span>', '<span class="pill ok"><span class="dot"></span>已解析</span>', actBtns()], ['<a class="lnk">T-1009</a>', '回转壳体 B', '<span class="route">5数铣 10钳 20数车 30精磨 40总检</span>', '<span class="chipline"><span class="chip b">自制 5</span></span>', '<span class="pill ok"><span class="dot"></span>已解析</span>', actBtns()], ['<a class="lnk">T-1011</a>', '端盖 C', '<span class="route">5数车 10钻孔 20外协热处理 25外协喷涂 30总检</span>', '<span class="chipline"><span class="chip b">自制 3</span><span class="chip a">外协 2</span></span>', '<span class="pill ok"><span class="dot"></span>已解析</span>', actBtns()], ['<a class="lnk">T-1014</a>', '法兰 D', '<span class="muted">—</span>', '<span class="muted" style="font-size:12px">待生成</span>', '<span class="pill warn"><span class="dot"></span>未解析</span>', actBtns()], ['<a class="lnk">T-1021</a>', '支座 E', '<span class="route">5数铣 10数车 20钻孔 30外协发黑 40总检 45表处理</span>', '<span class="chipline"><span class="chip b">自制 4</span><span class="chip a">外协 1</span></span>', '<span class="pill ok"><span class="dot"></span>已解析</span>', actBtns()]];
  var MATERIALS = [['<a class="lnk">M-2001</a>', '45# 圆钢 Ø120', 'Ø120 × 2000', '1,240 kg', '<span class="pill ok"><span class="dot"></span>启用</span>', actBtns()], ['<a class="lnk">M-2008</a>', '6061 铝板 12mm', '1220 × 2440', '86 张', '<span class="pill ok"><span class="dot"></span>启用</span>', actBtns()], ['<a class="lnk">M-2015</a>', '40Cr 锻件毛坯', 'Ø200 锻坯', '32 件', '<span class="pill warn"><span class="dot"></span>低库存</span>', actBtns()], ['<a class="lnk">M-2031</a>', '不锈钢 304 棒', 'Ø60 × 3000', '410 kg', '<span class="pill ok"><span class="dot"></span>启用</span>', actBtns()], ['<a class="lnk">M-2044</a>', '紧固件套件 A', 'M8 / M10 混装', '2,300 套', '<span class="pill off"><span class="dot"></span>停用</span>', actBtns()]];
  var OP_INT = [['<a class="lnk">OT001</a>', '数铣', '6', '14', '主力工序，设备充足', actBtns('查看绑定')], ['<a class="lnk">OT002</a>', '数车', '5', '11', '<span class="muted">—</span>', actBtns('查看绑定')], ['<a class="lnk">OT003</a>', '钳工', '3', '9', '瓶颈工序，人员偏紧', actBtns('查看绑定')], ['<a class="lnk">OT004</a>', '精磨', '2', '6', '关键工序', actBtns('查看绑定')], ['<a class="lnk">OT006</a>', '总检', '1', '4', '关键工序 · 必检', actBtns('查看绑定')]];
  var EQUIP = [['<a class="lnk">EQ-01</a>', '立式加工中心 VMC-850', '<span class="chip b">数铣</span>', '设备组 A', '<span class="pill ok"><span class="dot"></span>可用</span>', actBtns()], ['<a class="lnk">EQ-04</a>', '数控车床 CK-6150', '<span class="chip b">数车</span>', '设备组 A', '<span class="pill ok"><span class="dot"></span>可用</span>', actBtns()], ['<a class="lnk">EQ-09</a>', '平面磨床 M7140', '<span class="chip b">精磨</span>', '设备组 B', '<span class="pill warn"><span class="dot"></span>检修</span>', actBtns()], ['<a class="lnk">EQ-12</a>', '钳工台 ·联合', '<span class="chip b">钳工</span>', '设备组 C', '<span class="pill ok"><span class="dot"></span>可用</span>', actBtns()]];
  var PEOPLE = [['<a class="lnk">P-101</a>', '张伟', '<span class="chipline"><span class="chip b">数铣</span><span class="chip b">数车</span></span>', '白班', '<span class="pill ok"><span class="dot"></span>在岗</span>', actBtns()], ['<a class="lnk">P-118</a>', '李娜', '<span class="chipline"><span class="chip b">精磨</span><span class="chip b">总检</span></span>', '白班', '<span class="pill ok"><span class="dot"></span>在岗</span>', actBtns()], ['<a class="lnk">P-126</a>', '王强', '<span class="chipline"><span class="chip b">钳工</span></span>', '两班倒', '<span class="pill warn"><span class="dot"></span>请假</span>', actBtns()], ['<a class="lnk">P-133</a>', '赵敏', '<span class="chipline"><span class="chip b">数车</span><span class="chip b">钻孔</span><span class="chip b">钳工</span></span>', '白班', '<span class="pill ok"><span class="dot"></span>在岗</span>', actBtns()]];
  var OP_EXT = [['<a class="lnk">OT051</a>', '电镀', '分别设置', '常用表面处理，多家供应商', actBtns('查看供应商')], ['<a class="lnk">OT052</a>', '发黑', '分别设置', '<span class="muted">—</span>', actBtns('查看供应商')], ['<a class="lnk">OT053</a>', '热处理', '合并设置', '需炉前确认整组周期', actBtns('查看供应商')], ['<a class="lnk">OT054</a>', '喷涂', '分别设置', '单一供应商', actBtns('查看供应商')]];
  var SUPPLIERS = [['<a class="lnk">S-01</a>', '华表面处理', '<span class="chipline"><span class="chip a">电镀</span><span class="chip a">发黑</span></span>', '3 天', '<span class="pill ok"><span class="dot"></span>启用</span>', actBtns()], ['<a class="lnk">S-02</a>', '金鼎热处理', '<span class="chipline"><span class="chip a">热处理</span></span>', '4 天', '<span class="pill ok"><span class="dot"></span>启用</span>', actBtns()], ['<a class="lnk">S-05</a>', '宏达喷涂', '<span class="chipline"><span class="chip a">喷涂</span></span>', '2 天', '<span class="pill warn"><span class="dot"></span>待复核</span>', actBtns()], ['<a class="lnk">S-07</a>', '精工电镀', '<span class="chipline"><span class="chip a">电镀</span></span>', '3 天', '<span class="pill off"><span class="dot"></span>停用</span>', actBtns()]];

  /* ---------------- content views ---------------- */
  function crumb(parts) {
    return '<div class="crumb">' + parts.map(function (p, i) {
      var last = i === parts.length - 1;
      return (i ? '<span class="sep">›</span>' : '') + '<span class="' + (last ? 'cur' : '') + '">' + p + '</span>';
    }).join('') + '</div>';
  }
  function chead(title, desc) {
    return '<div class="chead"><div><h2>' + title + '</h2><p class="cdesc">' + desc + '</p></div></div>';
  }
  function subtabsFor(chainId) {
    var c = CHAINS[chainId];
    return '<div class="subtabs">' + c.subs.map(function (s) {
      var on = state.sub[chainId] === s.id;
      return '<button class="subtab' + (on ? ' on' : '') + '" data-chain="' + chainId + '" data-sub="' + s.id + '">' + s.name + ' <span class="cnt">' + s.n + '</span></button>';
    }).join('') + '</div>';
  }

  /* ---- 工艺 part detail · 工时录入（工序清单 换型/单件两列） ---- */
  var PART_META = {
    'T-1008': {
      name: '回转壳体 A',
      parsed: true
    },
    'T-1009': {
      name: '回转壳体 B',
      parsed: true
    },
    'T-1011': {
      name: '端盖 C',
      parsed: true
    },
    'T-1014': {
      name: '法兰 D',
      parsed: false
    },
    'T-1021': {
      name: '支座 E',
      parsed: true
    }
  };
  var PART_OPS = {
    'T-1008': [{
      seq: 5,
      op: '数铣',
      dev: 'M-03 加工中心',
      src: 'int',
      setup: '30',
      unit: '11.8'
    }, {
      seq: 10,
      op: '钳工',
      dev: '钳工台',
      src: 'int',
      setup: '0',
      unit: ''
    }, {
      seq: 20,
      op: '数车',
      dev: 'CK-6150 数控车',
      src: 'int',
      setup: '15',
      unit: '2.0'
    }, {
      seq: 30,
      op: '电镀',
      dev: '华表面处理（外协）',
      src: 'ext',
      ext: '周期 3 天（外协链维护）'
    }, {
      seq: 35,
      op: '发黑',
      dev: '华表面处理（外协）',
      src: 'ext',
      ext: '周期 2 天（外协链维护）'
    }, {
      seq: 40,
      op: '总检',
      dev: '检测台',
      src: 'int',
      setup: '0',
      unit: '0',
      bad: true
    }],
    'T-1009': [{
      seq: 5,
      op: '数铣',
      dev: 'M-01 加工中心',
      src: 'int',
      setup: '30',
      unit: '9.4'
    }, {
      seq: 10,
      op: '钳工',
      dev: '钳工台',
      src: 'int',
      setup: '0',
      unit: '1.2'
    }, {
      seq: 20,
      op: '数车',
      dev: 'CK-6150',
      src: 'int',
      setup: '15',
      unit: '2.4'
    }, {
      seq: 30,
      op: '精磨',
      dev: 'M7140 平磨',
      src: 'int',
      setup: '20',
      unit: '3.1'
    }, {
      seq: 40,
      op: '总检',
      dev: '检测台',
      src: 'int',
      setup: '0',
      unit: '0.6'
    }],
    'T-1011': [{
      seq: 5,
      op: '数车',
      dev: 'CK-6150',
      src: 'int',
      setup: '15',
      unit: '1.8'
    }, {
      seq: 10,
      op: '钻孔',
      dev: 'Z-3050 摇臂钻',
      src: 'int',
      setup: '10',
      unit: ''
    }, {
      seq: 20,
      op: '热处理',
      dev: '金鼎热处理（外协）',
      src: 'ext',
      ext: '整组周期 6 天（合并设置）'
    }, {
      seq: 25,
      op: '喷涂',
      dev: '外协 · 待定供应商',
      src: 'ext',
      ext: '整组周期 6 天（合并设置）'
    }, {
      seq: 30,
      op: '总检',
      dev: '检测台',
      src: 'int',
      setup: '0',
      unit: '0.5'
    }],
    'T-1021': [{
      seq: 5,
      op: '数铣',
      dev: 'M-03 加工中心',
      src: 'int',
      setup: '30',
      unit: '8.0'
    }, {
      seq: 10,
      op: '数车',
      dev: 'CK-6150',
      src: 'int',
      setup: '15',
      unit: '2.2'
    }, {
      seq: 20,
      op: '钻孔',
      dev: 'Z-3050 摇臂钻',
      src: 'int',
      setup: '10',
      unit: '1.1'
    }, {
      seq: 30,
      op: '发黑',
      dev: '华表面处理（外协）',
      src: 'ext',
      ext: '周期 2 天（外协链维护）'
    }, {
      seq: 40,
      op: '总检',
      dev: '检测台',
      src: 'int',
      setup: '0',
      unit: '0.4'
    }, {
      seq: 45,
      op: '表处理',
      dev: '表处理工位',
      src: 'int',
      setup: '5',
      unit: '0.9'
    }]
  };
  var PART_CODES = ['T-1008', 'T-1009', 'T-1011', 'T-1014', 'T-1021'];
  function partHoursSummary(code) {
    var meta = PART_META[code];
    var ops = PART_OPS[code] || [];
    var internal = ops.filter(function (o) {
      return o.src === 'int';
    });
    if (!meta || !meta.parsed || !internal.length) return null;
    var filled = internal.filter(function (o) {
      return o.unit !== '' && Number(o.unit) !== 0;
    }).length;
    var missing = internal.filter(function (o) {
      return o.unit === '';
    }).length;
    var bad = internal.filter(function (o) {
      return o.unit !== '' && Number(o.unit) === 0;
    }).length;
    var sumUnit = internal.reduce(function (a, o) {
      return a + (o.unit !== '' ? Number(o.unit) || 0 : 0);
    }, 0);
    var sumSetup = internal.reduce(function (a, o) {
      return a + (o.setup !== '' ? Number(o.setup) || 0 : 0);
    }, 0);
    return {
      total: internal.length,
      filled: filled,
      missing: missing,
      bad: bad,
      sumUnit: sumUnit,
      sumSetup: sumSetup
    };
  }
  function hoursCell(code) {
    var s = partHoursSummary(code);
    if (!s) return '<span class="muted">—</span>';
    var pill, todo;
    if (s.missing) {
      pill = '<span class="pill warn"><span class="dot"></span>缺 ' + s.missing + ' 项</span>';
      todo = '去填 →';
    } else if (s.bad) {
      pill = '<span class="pill danger"><span class="dot"></span>异常 ' + s.bad + '</span>';
      todo = '复核 →';
    } else {
      pill = '<span class="pill ok"><span class="dot"></span>已填 ' + s.filled + '/' + s.total + '</span>';
      todo = '查看 →';
    }
    return '<div class="wt-sum">' + '<div class="wt-sum-top">' + pill + '<a class="lnk wt-go">' + todo + '</a></div>' + '<div class="wt-sum-h">单件合计 <b>' + s.sumUnit.toFixed(1) + '</b> h · 换型 ' + s.sumSetup.toFixed(1) + ' h</div>' + '</div>';
  }
  function partRows() {
    return PARTS.map(function (r, i) {
      var row = r.slice();
      row.splice(5, 0, hoursCell(PART_CODES[i]));
      return row;
    });
  }

  /* ===== 工艺三步流程：阶段模型 + 列表管线 + 详情 stepper + 归属分拣 + 已就绪 ===== */
  var CHK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
  var LCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>';
  var ARR = '<span class="pp-arr"></span>';

  /* 每个零件三步进度：route/attr/hours = done|pending|partial|locked|todo */
  var PART_STAGE = {
    'T-1008': {
      route: 'done',
      attr: 'pending',
      hours: 'locked'
    },
    'T-1009': {
      route: 'done',
      attr: 'done',
      hours: 'done'
    },
    'T-1011': {
      route: 'done',
      attr: 'done',
      hours: 'partial'
    },
    'T-1014': {
      route: 'todo',
      attr: 'locked',
      hours: 'locked'
    },
    'T-1021': {
      route: 'done',
      attr: 'done',
      hours: 'done'
    }
  };
  function partStageOf(code) {
    return PART_STAGE[code] || {
      route: 'todo',
      attr: 'locked',
      hours: 'locked'
    };
  }

  /* ---- 工种库（识别用）+ 路线引入的「待归类·待建」工种 ---- */
  var KNOWN_INT = ['数铣', '数车', '钳工', '精磨', '钻孔', '总检'];
  var KNOWN_EXT = ['电镀', '发黑', '热处理', '喷涂'];
  function classifyOp(name) {
    name = (name || '').trim();
    if (!name) return 'empty';
    if (KNOWN_INT.indexOf(name) >= 0) return 'int';
    if (KNOWN_EXT.indexOf(name) >= 0) return 'ext';
    return 'unknown';
  }
  /* 在路线里出现、但工种库还没有的工种：自制 / 外协未定，挂在两条链的「待归类」区 */
  var PENDING_OPTYPES = [{
    name: '表处理',
    from: 'T-1014 法兰 D'
  }, {
    name: '标印',
    from: 'T-1014 法兰 D'
  }];
  function pendingHas(name) {
    return PENDING_OPTYPES.some(function (p) {
      return p.name === name;
    });
  }
  function addPending(name, from) {
    if (!pendingHas(name) && classifyOp(name) === 'unknown') PENDING_OPTYPES.push({
      name: name,
      from: from
    });
  }

  /* 整条文本 → 工序行：支持「5数铣 10钳 20数车」「5数铣10钳…」「换行 / 逗号分隔」等写法（模块级，新增零件与手工新建路线共用） */
  function parseRouteText(text) {
    function clean(s) {
      return (s || '').replace(/^(外协|自制)/, '').trim();
    }
    var out = [];
    if (!text) return out;
    var norm = text.replace(/[，,、;；\n\r\t]+/g, ' ').replace(/([^\d\s])(\d)/g, '$1 $2');
    var toks = norm.split(/\s+/).filter(Boolean);
    var autoSeq = 0,
      pendSeq = null;
    toks.forEach(function (t) {
      var dm = t.match(/^(\d+)(.*)$/);
      if (dm) {
        if (dm[2]) {
          out.push({
            seq: dm[1],
            op: clean(dm[2])
          });
          pendSeq = null;
        } else {
          pendSeq = dm[1];
        }
      } else {
        var op = clean(t);
        if (!op) return;
        if (pendSeq !== null) {
          out.push({
            seq: pendSeq,
            op: op
          });
          pendSeq = null;
        } else {
          autoSeq += 10;
          out.push({
            seq: String(autoSeq),
            op: op
          });
        }
      }
    });
    return out;
  }
  var UP_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M7 10l5 5 5-5M5 21h14"/></svg>';
  var PEN_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L18.5 9.5a2 2 0 0 0-3-3L5 17v3z"/><path d="M13.5 6.5l3 3"/></svg>';

  /* 归属分拣的逐工序建议（自动只"建议"，人确认才作数） */
  var PART_SORT = {
    'T-1008': [{
      seq: 5,
      op: '数铣',
      sug: 'int',
      conf: 'hi',
      basis: '命中 <b>"数铣"→自制</b> · 与本图号历史一致'
    }, {
      seq: 10,
      op: '钳工',
      sug: 'int',
      conf: 'hi',
      basis: '命中 <b>"钳工"→自制</b> · 与本图号历史一致'
    }, {
      seq: 20,
      op: '数车',
      sug: 'int',
      conf: 'hi',
      basis: '命中 <b>"数车"→自制</b> · 与本图号历史一致'
    }, {
      seq: 40,
      op: '总检',
      sug: 'int',
      conf: 'hi',
      basis: '命中 <b>"总检"→自制</b> · 与本图号历史一致'
    }, {
      seq: 30,
      op: '电镀',
      sug: 'ext',
      conf: 'lo',
      basis: '命中关键词 <b>"电镀"→外协</b>，但本厂 2025 年曾自制过此序 · 与历史冲突',
      attn: true
    }, {
      seq: 35,
      op: '发黑',
      sug: null,
      conf: 'none',
      basis: '<b>无规则命中</b>："发黑"不在规则库 → 不替你猜，请人工指定',
      attn: 'bad'
    }]
  };
  function deriveSort(code) {
    return (PART_OPS[code] || []).map(function (o) {
      return {
        seq: o.seq,
        op: o.op,
        sug: o.src,
        conf: 'hi',
        basis: '命中 <b>"' + o.op + '"→' + (o.src === 'int' ? '自制' : '外协') + '</b> · 与本图号历史一致'
      };
    });
  }
  function sortList(code) {
    return PART_SORT[code] || deriveSort(code);
  }
  function hoursStateAfter(code) {
    var s = partHoursSummary(code);
    if (!s) return 'done';
    return s.missing || s.bad ? 'partial' : 'done';
  }
  function stageBucket(code) {
    var s = partStageOf(code);
    if (s.route !== 'done') return 'route';
    if (s.attr !== 'done') return 'sort';
    if (s.hours !== 'done') return 'hours';
    return 'ready';
  }
  function effStage(code) {
    if (state.openStage) return state.openStage;
    var b = stageBucket(code);
    return b === 'sort' ? 'attr' : b;
  }

  /* 列表行内三段管线 */
  function pp(label, st) {
    var ico = st === 'done' ? CHK : st === 'lock' ? LCK : '';
    return '<span class="pp ' + st + '">' + ico + label + '</span>';
  }
  function pipelineCell(code) {
    var s = partStageOf(code);
    var r = s.route === 'done' ? pp('路线', 'done') : pp('路线 · 待导入', 'warn');
    var a;
    if (s.route !== 'done') a = pp('归属', 'todo');else if (s.attr === 'done') a = pp('归属', 'done');else {
      var sl = sortList(code);
      var attnN = sl.filter(function (o) {
        return o.attn;
      }).length;
      a = pp('归属 · 待分拣 ' + attnN + ' / 共 ' + sl.length, 'warn');
    }
    var h;
    if (s.hours === 'locked' || s.attr !== 'done') h = pp('工时', 'lock');else if (s.hours === 'done') h = pp('工时', 'done');else {
      var sum = partHoursSummary(code);
      var miss = sum ? sum.missing + sum.bad : 0;
      var tot = sum ? sum.total : 0;
      h = pp('工时 · 缺 ' + miss + ' / 共 ' + tot, 'warn');
    }
    return '<div class="pipe">' + r + ARR + a + ARR + h + '</div>';
  }
  function nextActionCell(code) {
    var b = stageBucket(code);
    if (b === 'route') return '<button class="lnk pl-route-menu" data-code="' + code + '">录入路线 ▾</button>';
    if (b === 'sort') return '<a class="lnk pl-act">去分拣 →</a>';
    if (b === 'hours') return '<a class="lnk pl-act">填工时 →</a>';
    return '<span class="muted" style="font-size:12.5px">已就绪</span>';
  }

  /* 详情 stepper */
  function stepperHtml(code, eff) {
    var s = partStageOf(code);
    var routeC = s.route === 'done' ? 'done' : 'active';
    var attrC = s.route !== 'done' ? 'lock' : s.attr === 'done' ? 'done' : 'active';
    var hoursC = s.attr !== 'done' ? 'lock' : s.hours === 'done' ? 'done' : 'active';
    if (eff === 'route') routeC = 'active';
    if (eff === 'attr') attrC = 'active';
    if (eff === 'hours') hoursC = 'active';
    var ops = PART_OPS[code] || [];
    var intN = ops.filter(function (o) {
      return o.src === 'int';
    }).length;
    var extN = ops.filter(function (o) {
      return o.src === 'ext';
    }).length;
    var sum = partHoursSummary(code);
    var routeSub = s.route === 'done' ? '已导入 · ' + ops.length + ' 道工序' : '待导入路线';
    var attrSub = s.route !== 'done' ? '待路线完成' : s.attr === 'done' ? '自制 ' + intN + ' · 外协 ' + extN + ' · 已确认' : '进行中 · 待分拣';
    var hoursSub = s.attr !== 'done' ? '待归属确认后解锁' : s.hours === 'done' ? intN + ' 道自制序全填' : '缺 ' + (sum ? sum.missing + sum.bad : 0) + ' 项';
    function node(c, num, title, sub, reopen) {
      var ico = c === 'done' ? CHK : c === 'lock' ? LCK : num;
      var edit = c === 'done' && reopen ? '<span class="stp-edit" data-reopen="' + reopen + '">重新打开</span>' : '';
      return '<div class="stp ' + c + '"><div class="stp-n">' + ico + '</div><div class="stp-b"><span class="stp-t">' + title + edit + '</span><span class="stp-s">' + sub + '</span></div></div>';
    }
    return '<div class="stepper">' + node(routeC, '1', '① 工艺路线', routeSub, null) + node(attrC, '2', '② 工序归属', attrSub, 'attr') + node(hoursC, '3', '③ 工时定额', hoursSub, 'hours') + '</div>';
  }
  var GATE_NOTE = '<div class="gate-note">' + LCK + '<span><b>闸门：</b>③ 工时定额在本页「待确认 / 待定」清零前保持锁定。归属判错 = 整道工序走错链（自制漏排产能、外协空等填工时），所以必须人工确认才放行。</span></div>';
  function sortRowHtml(o, preStaged) {
    var attnCls = preStaged ? ' staged' : o.attn === 'bad' ? ' attn-bad' : o.attn ? ' attn' : '';
    var seg = '<span class="segm"><button data-attr="int"' + (o.sug === 'int' ? ' class="on int"' : '') + '>自制</button><button data-attr="ext"' + (o.sug === 'ext' ? ' class="on ext"' : '') + '>外协</button></span>';
    var sug = o.sug ? '<span class="sug">建议</span>' : '';
    var conf = o.conf === 'hi' ? '<div class="conf hi" style="margin-top:5px">置信高</div>' : o.conf === 'lo' ? '<div class="conf lo" style="margin-top:5px">置信中 · 请复核</div>' : '<div class="conf none" style="margin-top:5px">无建议 · 需人工</div>';
    var pill = preStaged ? '<span class="pill info"><span class="dot"></span>建议 · 已采纳</span>' : o.attn === 'bad' ? '<span class="pill danger"><span class="dot"></span>待定 · 需人工</span>' : '<span class="pill warn"><span class="dot"></span>待确认</span>';
    return '<tr class="sort-row' + attnCls + '" data-conf="' + o.conf + '">' + '<td class="num"><b>' + o.seq + '</b> ' + o.op + '</td>' + '<td>' + o.op + '</td>' + '<td><div class="attr-cell">' + seg + sug + '</div></td>' + '<td><div class="basis">' + o.basis + '</div>' + conf + '</td>' + '<td><span class="attr-status">' + pill + '</span></td></tr>';
  }
  function sortBody(code) {
    var list = sortList(code);
    var attn = list.filter(function (o) {
      return o.attn;
    });
    var hi = list.filter(function (o) {
      return !o.attn;
    });
    var total = list.length;
    var rows = attn.map(function (o) {
      return sortRowHtml(o, false);
    }).join('');
    if (hi.length) rows += '<tr class="grp-row"><td colspan="5">高置信 · ' + hi.length + ' 道工序已默认采纳（关键词明确命中，且与本图号历史一致）· 可点行内按钮改动</td></tr>' + hi.map(function (o) {
      return sortRowHtml(o, true);
    }).join('');
    return GATE_NOTE + '<div class="statline">' + '<div class="stat anchor"><span class="sv">' + total + '</span><span class="sl">工序</span></div>' + '<div class="stat ok"><span class="sv sort-confirmed">' + hi.length + '</span><span class="sl">已选定</span></div>' + '<div class="stat warn"><span class="sv sort-todo">' + (total - hi.length) + '</span><span class="sl">待办</span></div>' + '</div>' + '<div class="toolbar"><div class="search"><span class="ic">' + svg('route').replace('width="18" height="18"', 'width="15" height="15"') + '</span>' + '<input placeholder="搜索工序、工种…"></div><div class="tb-spacer"></div></div>' + '<div class="card"><div class="card-scroll"><table class="tbl" style="min-width:1020px;table-layout:auto"><thead><tr>' + '<th style="width:150px">工序</th><th style="width:96px">工种</th><th style="width:200px">归属 <small style="font-weight:500;color:var(--ui-muted)">建议 → 确认</small></th><th>判断依据 / 置信</th><th style="width:118px">状态</th>' + '</tr></thead><tbody>' + rows + '</tbody></table></div></div>' + '<div class="pd-foot sticky"><div class="muted">确认后写入工序归属并留痕（确认人 / 时间 / 依据）。下次重导路线时，<b>已人工确认的不被自动判断覆盖</b>。</div>' + '<button class="btn primary sort-finish"' + (total - hi.length > 0 ? ' disabled' : '') + '>' + (total - hi.length > 0 ? '完成归属 · 解锁工时（还剩 ' + (total - hi.length) + '）' : '完成归属 · 解锁工时（' + total + ' 道）') + '</button></div>';
  }
  function readyBody(code) {
    var ops = PART_OPS[code] || [];
    var sum = partHoursSummary(code) || {
      sumUnit: 0,
      sumSetup: 0
    };
    var rows = ops.map(function (o) {
      var attr = o.src === 'ext' ? '<span class="chip a">外协</span>' : '<span class="chip b">自制</span>';
      if (o.src === 'ext') return '<tr><td class="num"><b>' + o.seq + '</b> ' + o.op + '</td><td>' + o.op + '</td><td class="muted">' + o.dev + '</td><td>' + attr + '</td><td class="r wt-col" colspan="2" style="text-align:center"><span class="muted" style="font-size:12px">外协工序无工时 · ' + o.ext + '</span></td></tr>';
      var unitCell = '<span class="wt-val">' + o.unit + '</span>';
      return '<tr><td class="num"><b>' + o.seq + '</b> ' + o.op + '</td><td>' + o.op + '</td><td class="muted">' + o.dev + '</td><td>' + attr + '</td><td class="r wt-col"><span class="wt-val">' + o.setup + '</span></td><td class="r wt-col">' + unitCell + '</td></tr>';
    }).join('');
    var intN = ops.filter(function (o) {
      return o.src === 'int';
    }).length;
    var extN = ops.filter(function (o) {
      return o.src === 'ext';
    }).length;
    return '<div class="ready-note"><div class="rn-ico">' + CHK + '</div><div><div class="rn-t">已就绪 · 可参与排产</div><div class="rn-s">路线 / 归属 / 工时三项齐备，本零件已纳入下次执行排产的可调度池。</div></div><div class="rn-act"><button class="btn ready-export">导出工序清单</button></div></div>' + '<div class="card"><div class="card-scroll"><table class="tbl op-tbl" style="min-width:720px;table-layout:auto"><thead><tr><th style="width:120px">工序</th><th style="width:90px">工种</th><th>设备 / 资源</th><th style="width:84px">归属</th><th class="r wt-col" style="width:124px">换型工时<small>定额·h</small></th><th class="r wt-col" style="width:124px">单件工时<small>定额·h</small></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' + '<div class="pd-foot"><div class="wt-sum"><div class="wt-sum-top"><span class="muted" style="font-size:12.5px">汇总</span></div><div class="wt-sum-h">自制 <b>' + intN + '</b> 序 · 外协 <b>' + extN + '</b> 序 · 换型合计 <b>' + sum.sumSetup.toFixed(1) + ' h</b> · 单件合计 <b>' + sum.sumUnit.toFixed(1) + ' h</b></div></div><button class="btn ready-edit">编辑（重新打开某步）</button></div>';
  }
  var IMPORT_PROMPT = '<div class="card" style="padding:34px;text-align:center"><div class="muted" style="margin-bottom:16px;line-height:1.7">该零件还没有工艺路线。可<b>导入</b>工艺室给的路线，也可<b>手工逐行新建</b>；完成后再进行<b>工序归属</b>与<b>工时定额</b>两步。</div><div style="display:flex;gap:10px;justify-content:center"><button class="btn primary pd-manual-route">' + PEN_SVG + '手工新建路线</button><button class="btn pd-import-route">' + UP_SVG + '导入工艺路线</button></div></div>';
  function hoursBody(code) {
    var ops = PART_OPS[code] || [];
    var focus = false;
    var internal = ops.filter(function (o) {
      return o.src === 'int';
    });
    var filled = internal.filter(function (o) {
      return o.unit !== '' && Number(o.unit) !== 0;
    }).length;
    var missing = internal.filter(function (o) {
      return o.unit === '';
    }).length;
    var bad = internal.filter(function (o) {
      return o.unit !== '' && Number(o.unit) === 0;
    }).length;
    var rows = ops.map(function (o) {
      return opRow(o, focus);
    }).join('');
    var minw = focus ? 640 : 880;
    return statline([{
      v: ops.length,
      l: '工序',
      tone: 'anchor'
    }, {
      v: filled,
      l: '已填',
      tone: 'ok'
    }, {
      v: missing,
      l: '缺工时',
      tone: 'warn'
    }, {
      v: bad,
      l: '异常',
      tone: 'danger'
    }]) + '<div class="toolbar"><div class="search"><span class="ic">' + svg('route').replace('width="18" height="18"', 'width="15" height="15"') + '</span>' + '<input placeholder="搜索工序、工种…"></div><div class="tb-spacer"></div>' + impButtons(true) + '</div>' + '<div class="match-note">⚠ 上次工时导入：匹配 <b>312 / 320</b> · <b>8 条未匹配</b>（图号 + 工序在路线中不存在）<a class="lnk" style="margin-left:auto">查看未匹配 →</a></div>' + '<div class="card"><div class="card-scroll"><table class="tbl op-tbl" style="min-width:' + minw + 'px;table-layout:auto"><thead><tr>' + opTableHead(focus) + '</tr></thead><tbody>' + rows + '</tbody></table></div></div>' + '<div class="pd-foot"><span class="muted">填好换型 / 单件工时后点保存；外协工序无需填写，缺工时或单件为 0 会标黄 / 标红提示。</span><button class="btn primary pd-save"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>保存工时</button></div>' + '<div class="pager"><span class="grow"></span><span class="muted">' + code + ' · 共 ' + ops.length + ' 道工序</span></div>';
  }
  function headDescFor(stage) {
    if (stage === 'route') return '导入工艺路线后，按 <b>① 路线 → ② 归属 → ③ 工时</b> 三步推进。';
    if (stage === 'attr') return '逐道工序确认走 <b class="bi">自制</b> 还是 <b class="be">外协</b>。系统按工序名给<b>建议</b>，确认才作数；外协工序不进工时、走周期。';
    if (stage === 'hours') return '右侧两列填 <b class="be">定额室</b> 的换型 / 单件工时；外协工序无需填写。';
    return '三步齐备的只读汇总，可参与排产。任一步需修改点 stepper 上「重新打开」。';
  }
  function processListToolbar() {
    return '<div class="toolbar"><div class="search"><span class="ic">' + svg('route').replace('width="18" height="18"', 'width="15" height="15"') + '</span>' + '<input placeholder="搜索图号、名称、路线…"></div><div class="tb-spacer"></div>' + impButtons(false) + '<span class="tb-div"></span>' + expButtons() + '<button class="btn primary add-btn" data-entity="part"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>新增零件</button></div>';
  }
  function statlineProcess(counts) {
    return '<div class="statline">' + '<div class="stat anchor"><span class="sv">' + PART_CODES.length + '</span><span class="sl">零件总数</span></div>' + '<div class="stat warn"><span class="sv">' + counts.sort + '</span><span class="sl">待分拣</span></div>' + '<div class="stat warn"><span class="sv">' + counts.hours + '</span><span class="sl">待填工时</span></div>' + '<div class="stat ok"><span class="sv">' + counts.ready + '</span><span class="sl">已就绪</span></div>' + '</div>';
  }
  function impButtons(primaryHours) {
    var up = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M7 10l5 5 5-5M5 21h14"/></svg>';
    return '<button class="btn imp-route">' + up + '导入工艺路线</button>' + '<button class="btn ' + (primaryHours ? 'primary ' : '') + 'imp-hours">' + up + '导入工时定额</button>';
  }
  function expButtons() {
    var dn = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 14V3M8 7l4-4 4 4M5 20h14"/></svg>';
    return '<button class="btn io-btn io-exp" data-entity="route" data-mode="exp">' + dn + '导出工艺路线</button>' + '<button class="btn io-btn io-exp" data-entity="hours" data-mode="exp">' + dn + '导出工时定额</button>';
  }
  function processToolbar() {
    return '<div class="toolbar"><div class="search"><span class="ic">' + svg('route').replace('width="18" height="18"', 'width="15" height="15"') + '</span>' + '<input placeholder="搜索图号、名称、路线…"></div><div class="tb-spacer"></div>' + '<span class="selcount" hidden>已选 <b class="selN">0</b> 项</span>' + '<button class="linkbtn clear-sel" hidden>取消</button>' + '<button class="btn danger batch-del"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 7h14M10 7V5h4v2M7 7l1 13h8l1-13"/></svg>批量删除</button>' + '<span class="tb-div"></span>' + impButtons(false) + '<button class="btn primary add-btn" data-entity="part"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>新增零件</button></div>';
  }
  function opTableHead(focus) {
    if (focus) return '<th style="width:120px">工序</th><th style="width:90px">工种</th>' + '<th class="wt-col" style="width:150px">换型工时<small>定额·h</small></th>' + '<th class="wt-col">单件工时<small>定额·h</small></th>';
    return '<th style="width:120px">工序</th><th style="width:90px">工种</th>' + '<th>设备 / 资源</th><th style="width:84px">归属</th>' + '<th class="wt-col" style="width:140px">换型工时<small>定额·h</small></th>' + '<th class="wt-col" style="width:190px">单件工时<small>定额·h</small></th>';
  }
  function opRow(o, focus) {
    var seqCell = '<td class="num"><b>' + o.seq + '</b> ' + o.op + '</td><td>' + o.op + '</td>';
    if (o.src === 'ext') {
      var lead = seqCell + (focus ? '' : '<td class="muted">' + o.dev + '</td><td><span class="chip a">外协</span></td>');
      return '<tr>' + lead + '<td class="wt-col" colspan="2" style="text-align:center"><span class="muted" style="font-size:12px">外协工序无工时 · ' + o.ext + '</span></td></tr>';
    }
    var mid = focus ? '' : '<td class="muted">' + o.dev + '</td><td><span class="chip b">自制</span></td>';
    var isEmpty = o.unit === '';
    var isBad = !isEmpty && Number(o.unit) === 0;
    var setup = '<td class="wt-col"><input class="wt-in" data-seq="' + o.seq + '" data-field="setup" value="' + o.setup + '"></td>';
    var unitCls = isBad ? 'wt-in bad' : isEmpty ? 'wt-in empty' : 'wt-in';
    var marker = isBad ? '<span class="prov bad-note">单件为 0 · 请复核</span>' : '';
    var unit = '<td class="wt-col"><div class="wt-cell">' + marker + '<input class="' + unitCls + '" data-seq="' + o.seq + '" data-field="unit" value="' + o.unit + '"' + (isEmpty ? ' placeholder="待填"' : '') + '></div></td>';
    return '<tr>' + seqCell + mid + setup + unit + '</tr>';
  }
  function viewPartDetail(code) {
    var meta = PART_META[code] || {
      name: code,
      parsed: false
    };
    var stage = effStage(code);
    var crumbLast = stage === 'attr' ? '工序归属' : stage === 'hours' ? '工时' : stage === 'ready' ? '汇总' : '路线';
    var head = '<button class="linkbtn pd-back" style="margin-bottom:10px">← 返回零件列表</button>' + crumb(['产能链', '输入', '工艺', code, crumbLast]) + '<div class="chead"><div><h2>' + code + ' ' + meta.name + '</h2><p class="cdesc">' + headDescFor(stage) + '</p></div></div>' + stepperHtml(code, stage);
    var body;
    if (stage === 'route') body = IMPORT_PROMPT;else if (stage === 'attr') body = sortBody(code);else if (stage === 'hours') body = hoursBody(code);else body = readyBody(code);
    return head + body;
  }
  function partBodyFor(code, stage) {
    if (stage === 'route') return IMPORT_PROMPT;
    if (stage === 'attr') return sortBody(code);
    if (stage === 'hours') return hoursBody(code);
    return readyBody(code);
  }

  /* 零件工艺详情 · 弹出卡片（替代整页下钻） */
  function openPartModal(code) {
    state.openPart = code;
    state.opView = 'full';
    state.openStage = null;
    var bg = document.createElement('div');
    bg.className = 'modal-bg';
    function close() {
      if (bg.parentNode) bg.parentNode.removeChild(bg);
      document.removeEventListener('keydown', onKey);
      partModal = null;
      state.openPart = null;
      state.openStage = null;
    }
    function onKey(e) {
      if (e.key === 'Escape') close();
    }
    bg.addEventListener('click', function (e) {
      if (e.target === bg) close();
    });
    function repaint() {
      var meta = PART_META[code] || {
        name: code
      };
      var stage = effStage(code);
      bg.innerHTML = '<div class="modal xl pd-modal" role="dialog" aria-modal="true">' + modalHead('route', code + ' ' + (meta.name || ''), headDescFor(stage)) + '<div class="modal-b scroll pd-modal-b">' + stepperHtml(code, stage) + partBodyFor(code, stage) + '</div></div>';
      bg.querySelectorAll('[data-close]').forEach(function (b) {
        b.addEventListener('click', close);
      });
      var modalEl = bg.querySelector('.pd-modal');
      wirePartModal(code, modalEl, stage);
    }
    partModal = {
      code: code,
      repaint: repaint,
      close: close
    };
    document.addEventListener('keydown', onKey);
    repaint();
    root.appendChild(bg);
  }
  function wirePartModal(code, scope, stage) {
    scope.querySelectorAll('.stp-edit[data-reopen]').forEach(function (e) {
      e.addEventListener('click', function () {
        state.openStage = e.getAttribute('data-reopen');
        render();
      });
    });
    if (stage === 'route') {
      var pir = scope.querySelector('.pd-import-route');
      if (pir) pir.addEventListener('click', function () {
        showImportExport('route', 'imp');
      });
      var pmr = scope.querySelector('.pd-manual-route');
      if (pmr) pmr.addEventListener('click', function () {
        showRouteEntry(code);
      });
    } else if (stage === 'attr') {
      wireSort(code, scope);
    } else if (stage === 'hours') {
      wireHours(code, scope);
    } else {
      var re = scope.querySelector('.ready-edit');
      if (re) re.addEventListener('click', function () {
        state.openStage = 'attr';
        render();
      });
      var rx = scope.querySelector('.ready-export');
      if (rx) rx.addEventListener('click', function () {
        showFlash('已导出 ' + code + ' 工序清单（示例）。');
      });
    }
  }
  function viewProcess() {
    var filter = state.stageFilter || 'all';
    var counts = {
      route: 0,
      sort: 0,
      hours: 0,
      ready: 0
    };
    PART_CODES.forEach(function (c) {
      counts[stageBucket(c)]++;
    });
    var tabs = [{
      id: 'all',
      label: '全部',
      n: PART_CODES.length
    }, {
      id: 'route',
      label: '待导入路线',
      n: counts.route
    }, {
      id: 'sort',
      label: '待分拣',
      n: counts.sort
    }, {
      id: 'hours',
      label: '待填工时',
      n: counts.hours
    }, {
      id: 'ready',
      label: '已就绪',
      n: counts.ready
    }];
    var subtabs = '<div class="subtabs">' + tabs.map(function (t) {
      return '<button class="subtab' + (filter === t.id ? ' on' : '') + '" data-stage="' + t.id + '">' + t.label + ' <span class="cnt">' + t.n + '</span></button>';
    }).join('') + '</div>';
    var visible = PART_CODES.filter(function (c) {
      return filter === 'all' || stageBucket(c) === filter;
    });
    var rows = visible.map(function (c) {
      var meta = PART_META[c] || {
        name: c
      };
      var ops = (PART_OPS[c] || []).length;
      var opsCell = ops ? '<span class="num">' + ops + '</span>' : '<span class="muted">—</span>';
      return '<tr data-code="' + c + '"><td><a class="lnk">' + c + '</a> <span class="pl-name">' + (meta.name || '') + '</span></td><td class="r">' + opsCell + '</td><td>' + pipelineCell(c) + '</td><td>' + nextActionCell(c) + '</td></tr>';
    }).join('');
    if (!rows) rows = '<tr><td colspan="4" style="text-align:center;padding:28px" class="muted">该阶段暂无零件。</td></tr>';
    var tableHtml = '<div class="card"><div class="card-scroll"><table class="tbl" style="min-width:920px;table-layout:auto"><thead><tr><th style="width:230px">图号 / 零件</th><th class="r" style="width:70px">工序数量</th><th>进度</th><th style="width:130px">下一步</th></tr></thead><tbody>' + rows + '</tbody></table></div></div>';
    return crumb(['产能链', '输入', '工艺']) + chead('零件工艺', '每个零件按 <b>① 导入路线 → ② 工序归属（自制 / 外协）→ ③ 工时定额</b> 三步推进；后一步在前一步完成前锁定。工序归属由系统按工序名给<b>建议</b>，需人工确认才放行。') + statlineProcess(counts) + (PENDING_OPTYPES.length ? '<div class="match-note">⚠ 本批路线有 <b>' + PENDING_OPTYPES.length + '</b> 个工种未识别，已登记到工种库「待归类 · 待建」<a class="lnk go-pending" style="margin-left:auto">去工种库 →</a></div>' : '') + subtabs + processListToolbar() + tableHtml + pager(PART_CODES.length);
  }
  function viewMaterial() {
    return crumb(['产能链', '输入', '物料']) + chead('物料 · 物料主数据', '维护物料编号、规格、库存与状态；批次物料需求在「批次管理」里按批引用这里的主数据。') + statline([{
      v: 86,
      l: '物料主数据',
      tone: 'anchor'
    }, {
      v: 78,
      l: '启用',
      tone: 'ok'
    }, {
      v: 5,
      l: '低库存',
      tone: 'warn'
    }, {
      v: 3,
      l: '停用'
    }]) + toolbar('搜索物料编号、名称…', '新增物料', 'cube', 'material') + table([{
      t: '物料编号',
      w: 120
    }, {
      t: '名称',
      w: 180
    }, {
      t: '规格'
    }, {
      t: '库存',
      w: 120,
      r: true
    }, {
      t: '状态',
      w: 110
    }, {
      t: '操作',
      w: 190,
      act: true
    }], MATERIALS) + pager(86);
  }
  function viewCalendar() {
    var s = calStats();
    return crumb(['产能链', '全局', '工作日历']) + chead('工作日历', '设置排产用的工作时间、效率与可排产优先级；未配置的日期按默认规则处理，可在此配置调休或加班。') + statline([{
      v: s.workDays,
      l: '本月工作日',
      tone: 'anchor'
    }, {
      v: s.configured,
      l: '已配工时',
      tone: 'ok'
    }, {
      v: s.overrides,
      l: '调休 / 加班',
      tone: 'warn'
    }, {
      v: s.weekendRest,
      l: '周末休息'
    }]) + '<div style="margin-top:18px" class="cal-wrap">' + '<div class="cal-panel">' + '<div class="cal-top"><button class="cal-nav" data-dir="-1" aria-label="上一月">‹</button><span class="cal-title">' + calState.y + ' 年 ' + (calState.m + 1) + ' 月</span><button class="cal-nav" data-dir="1" aria-label="下一月">›</button><button class="cal-nav cal-today-btn" title="回到本月" style="width:auto;padding:0 10px;font-size:12px;font-weight:600">今天</button><span class="tb-spacer" style="flex:1"></span><button class="btn cal-batch">批量维护</button></div>' + calGrid() + '</div>' + '<div class="cal-panel cal-side">' + '<h3>图例</h3>' + '<div class="cal-leg">' + '<div><span class="sw cfg"></span> 已配置工时</div>' + '<div><span class="sw rest"></span> 调休 / 加班</div>' + '<div><span class="sw we"></span> 周末（默认非工作）</div>' + '</div>' + '<h3>默认规则</h3>' + '<p>未单独配置的日期：工作日按 8 小时、效率 100% 排产，普通件 / 急件都允许；周末默认不排产。点任一日期可单独覆盖工时、效率，或单独关掉普通件 / 急件（如只留急件加班）。</p>' + '</div>' + '</div>';
  }
  function calGrid() {
    var wd = ['一', '二', '三', '四', '五', '六', '日'];
    var html = '<div class="cal-grid">' + wd.map(function (d) {
      return '<div class="cal-wd">' + d + '</div>';
    }).join('');
    var first = new Date(calState.y, calState.m, 1).getDay(); // 0=Sun
    var lead = (first + 6) % 7; // Monday-first offset
    var dim = new Date(calState.y, calState.m + 1, 0).getDate();
    var now = new Date();
    for (var i = 0; i < lead; i++) html += '<div class="cal-cell empty"></div>';
    for (var d = 1; d <= dim; d++) {
      var meta = calDayMeta(d);
      var cls = 'cal-cell' + (meta.cls ? ' ' + meta.cls : '');
      if (now.getFullYear() === calState.y && now.getMonth() === calState.m && now.getDate() === d) cls += ' today';
      html += '<div class="' + cls + '" data-d="' + d + '" role="button" tabindex="0"><span class="d">' + d + '</span><span class="tag">' + meta.tag + '</span></div>';
    }
    return html + '</div>';
  }
  /* ---------------- calendar interactions ---------------- */
  function wireCalendar() {
    var root = document.getElementById('content');
    root.querySelectorAll('.cal-nav[data-dir]').forEach(function (b) {
      b.addEventListener('click', function () {
        calState.m += parseInt(b.getAttribute('data-dir'), 10);
        if (calState.m < 0) {
          calState.m = 11;
          calState.y--;
        } else if (calState.m > 11) {
          calState.m = 0;
          calState.y++;
        }
        renderContent();
      });
    });
    var todayBtn = root.querySelector('.cal-today-btn');
    if (todayBtn) todayBtn.addEventListener('click', function () {
      var n = new Date();
      calState.y = n.getFullYear();
      calState.m = n.getMonth();
      renderContent();
    });
    root.querySelectorAll('.cal-cell[data-d]').forEach(function (cell) {
      var open = function () {
        openDayModal(parseInt(cell.getAttribute('data-d'), 10));
      };
      cell.addEventListener('click', open);
      cell.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          open();
        }
      });
    });
    var batch = root.querySelector('.cal-batch');
    if (batch) batch.addEventListener('click', showCalBatchModal);
  }
  function openDayModal(d) {
    var dow = new Date(calState.y, calState.m, d).getDay();
    var weekend = dow === 0 || dow === 6;
    var wdZh = ['日', '一', '二', '三', '四', '五', '六'][dow];
    var rec = calState.cfg[calKey(d)];
    var type = rec ? rec.type : weekend ? 'rest' : 'work';
    var typeLabel = type === 'work' ? '工作日' : '休息日';
    var hours = rec && rec.hours != null ? rec.hours : 8;
    var eff = rec && rec.eff != null ? rec.eff : 100;
    var allowNormal = rec && rec.allowNormal === 'no' ? '否' : '是';
    var allowUrgent = rec && rec.allowUrgent === 'no' ? '否' : '是';
    var note = rec && rec.note || '';
    var seg = function (name, val, opts) {
      return '<div class="seg" data-seg="' + name + '">' + opts.map(function (o) {
        return '<button type="button" class="' + (o === val ? 'on' : '') + '" data-v="' + o + '">' + o + '</button>';
      }).join('') + '</div>';
    };
    var m = openModal('<div class="modal lg" role="dialog" aria-modal="true">' + modalHead('calendar', calState.m + 1 + ' 月 ' + d + ' 日 · 周' + wdZh, '设置这一天的工作时间、效率与可排产范围' + (weekend ? ' · 默认周末不排产' : '')) + '<div class="modal-b form">' + '<div class="field full"><label>这一天是否排产</label>' + seg('type', typeLabel, ['工作日', '休息日']) + '<span class="fhint">休息日不参与排产；工作日按下方工时与效率计算可用产能。</span></div>' + '<div class="fgrid cal-work-fields">' + '<div class="field"><label>可排工时（小时）</label><input class="cal-hours" type="number" min="0" max="24" step="0.5" value="' + hours + '"></div>' + '<div class="field"><label>效率（%）</label><input class="cal-eff" type="number" min="0" max="200" step="5" value="' + eff + '"></div>' + '<div class="field"><label>允许普通件排产</label>' + seg('allowNormal', allowNormal, ['是', '否']) + '</div>' + '<div class="field"><label>允许急件排产</label>' + seg('allowUrgent', allowUrgent, ['是', '否']) + '</div>' + '<div class="field full"><span class="fhint">两项相互独立、默认都为「是」；可单独关掉某一类，例如只留急件加班。两项都为「否」则这天不排产。</span></div>' + '</div>' + '<div class="field full"><label>备注</label><input class="cal-note" placeholder="如 节前加班 / 设备检修调休" value="' + note.replace(/"/g, '&quot;') + '"></div>' + '</div>' + '<div class="modal-f">' + '<button class="btn" data-close>取消</button>' + (rec ? '<button class="btn cal-clear">清除配置</button>' : '') + '<button class="btn primary cal-save">保存配置</button>' + '</div></div>');

    // segmented controls
    m.bg.querySelectorAll('.seg').forEach(function (s) {
      s.querySelectorAll('button').forEach(function (b) {
        b.addEventListener('click', function () {
          s.querySelectorAll('button').forEach(function (x) {
            x.classList.toggle('on', x === b);
          });
          if (s.getAttribute('data-seg') === 'type') syncType();
        });
      });
    });
    function curType() {
      return m.bg.querySelector('.seg[data-seg="type"] button.on').getAttribute('data-v');
    }
    function syncType() {
      var work = curType() === '工作日';
      var fields = m.bg.querySelector('.cal-work-fields');
      fields.style.opacity = work ? '' : '.45';
      fields.style.pointerEvents = work ? '' : 'none';
    }
    syncType();
    if (rec) m.bg.querySelector('.cal-clear').addEventListener('click', function () {
      delete calState.cfg[calKey(d)];
      m.close();
      renderContent();
      showFlash('已清除 ' + (calState.m + 1) + ' 月 ' + d + ' 日 的配置，恢复默认规则。');
    });
    m.bg.querySelector('.cal-save').addEventListener('click', function () {
      var work = curType() === '工作日';
      var noteV = (m.bg.querySelector('.cal-note').value || '').trim();
      if (work) {
        var an = m.bg.querySelector('.seg[data-seg="allowNormal"] button.on').getAttribute('data-v');
        var au = m.bg.querySelector('.seg[data-seg="allowUrgent"] button.on').getAttribute('data-v');
        calState.cfg[calKey(d)] = {
          type: 'work',
          hours: Number(m.bg.querySelector('.cal-hours').value) || 0,
          eff: Number(m.bg.querySelector('.cal-eff').value) || 0,
          allowNormal: an === '否' ? 'no' : 'yes',
          allowUrgent: au === '否' ? 'no' : 'yes',
          note: noteV
        };
      } else {
        calState.cfg[calKey(d)] = {
          type: 'rest',
          note: noteV
        };
      }
      m.close();
      renderContent();
      showFlash('已保存 ' + (calState.m + 1) + ' 月 ' + d + ' 日 的工作日历（示例数据，刷新后恢复）。');
    });
  }
  function showCalBatchModal() {
    var m = openModal('<div class="modal lg" role="dialog" aria-modal="true">' + modalHead('calendar', '批量维护工作日历', '对一段日期范围统一设置工时、效率或调休 / 加班。') + '<div class="modal-b form">' + '<div class="fgrid">' + '<div class="field"><label>开始日期<span class="req">*</span></label><input class="cb-from" type="date" value="' + calState.y + '-' + String(calState.m + 1).padStart(2, '0') + '-01"></div>' + '<div class="field"><label>结束日期<span class="req">*</span></label><input class="cb-to" type="date" value="' + calState.y + '-' + String(calState.m + 1).padStart(2, '0') + '-07"></div>' + '</div>' + '<div class="field full"><label>应用到</label><div class="seg" data-seg="scope"><button type="button" class="on" data-v="all">范围内每天</button><button type="button" data-v="weekday">仅工作日</button><button type="button" data-v="weekend">仅周末</button></div></div>' + '<div class="field full"><label>设置类型</label><div class="seg" data-seg="type"><button type="button" class="on" data-v="工作日">工作日</button><button type="button" data-v="休息日">休息日</button></div></div>' + '<div class="fgrid cb-work">' + '<div class="field"><label>可排工时（小时）</label><input class="cb-hours" type="number" min="0" max="24" step="0.5" value="8"></div>' + '<div class="field"><label>效率（%）</label><input class="cb-eff" type="number" min="0" max="200" step="5" value="100"></div>' + '<div class="field"><label>允许普通件排产</label><div class="seg" data-seg="allowNormal"><button type="button" class="on" data-v="是">是</button><button type="button" data-v="否">否</button></div></div>' + '<div class="field"><label>允许急件排产</label><div class="seg" data-seg="allowUrgent"><button type="button" class="on" data-v="是">是</button><button type="button" data-v="否">否</button></div></div>' + '</div>' + '</div>' + '<div class="modal-f"><button class="btn" data-close>取消</button><button class="btn primary cb-apply">应用到所选范围</button></div></div>');
    if (window.APSDatePicker) APSDatePicker.enhanceAll(m.bg);
    m.bg.querySelectorAll('.seg').forEach(function (s) {
      s.querySelectorAll('button').forEach(function (b) {
        b.addEventListener('click', function () {
          s.querySelectorAll('button').forEach(function (x) {
            x.classList.toggle('on', x === b);
          });
          if (s.getAttribute('data-seg') === 'type') {
            var work = m.bg.querySelector('.seg[data-seg="type"] button.on').getAttribute('data-v') === '工作日';
            var w = m.bg.querySelector('.cb-work');
            w.style.opacity = work ? '' : '.45';
            w.style.pointerEvents = work ? '' : 'none';
          }
        });
      });
    });
    m.bg.querySelector('.cb-apply').addEventListener('click', function () {
      var from = m.bg.querySelector('.cb-from').value,
        to = m.bg.querySelector('.cb-to').value;
      if (!from || !to || from > to) {
        showFlash('请选择正确的开始 / 结束日期。');
        return;
      }
      var scope = m.bg.querySelector('.seg[data-seg="scope"] button.on').getAttribute('data-v');
      var work = m.bg.querySelector('.seg[data-seg="type"] button.on').getAttribute('data-v') === '工作日';
      var hours = Number(m.bg.querySelector('.cb-hours').value) || 0;
      var eff = Number(m.bg.querySelector('.cb-eff').value) || 0;
      var an = m.bg.querySelector('.seg[data-seg="allowNormal"] button.on').getAttribute('data-v') === '否' ? 'no' : 'yes';
      var au = m.bg.querySelector('.seg[data-seg="allowUrgent"] button.on').getAttribute('data-v') === '否' ? 'no' : 'yes';
      var start = new Date(from),
        end = new Date(to),
        n = 0;
      for (var dt = new Date(start); dt <= end; dt.setDate(dt.getDate() + 1)) {
        var dow = dt.getDay(),
          weekend = dow === 0 || dow === 6;
        if (scope === 'weekday' && weekend) continue;
        if (scope === 'weekend' && !weekend) continue;
        var key = dt.getFullYear() + '-' + dt.getMonth() + '-' + dt.getDate();
        calState.cfg[key] = work ? {
          type: 'work',
          hours: hours,
          eff: eff,
          allowNormal: an,
          allowUrgent: au,
          note: '批量设置'
        } : {
          type: 'rest',
          note: '批量设置'
        };
        n++;
      }
      m.close();
      renderContent();
      showFlash('已批量' + (work ? '设置工时' : '设为休息') + ' ' + n + ' 天（示例数据，刷新后恢复）。');
    });
  }
  var SUBDESC = {
    internal: {
      op: '自制链 · 按 <b class="bi">工时口径</b>（换型 + 单件小时）排产。维护工序所需的自制工种，下接<b>设备</b>（绑 1 个工种）与<b>人员</b>（多技能矩阵）。',
      eq: '自制链 · <b class="bi">工时口径</b>。每台设备绑定一个自制工种，提供该工种的可用产能时段。',
      pp: '自制链 · <b class="bi">工时口径</b>。人员按多技能矩阵参与排产，一人可覆盖多个自制工种。'
    },
    external: {
      op: '外协链 · 按 <b class="be">周期口径</b>（天）排产。维护外协工序工种，由供应商承接；连续外协工序可按整组周期计。',
      sup: '外协链 · <b class="be">周期口径</b>。供应商绑定外协工种并给出默认周期（天）。'
    }
  };
  function viewChain(chainId) {
    var c = CHAINS[chainId],
      sub = state.sub[chainId];
    var subObj = c.subs.filter(function (s) {
      return s.id === sub;
    })[0];
    var tagCls = chainId === 'internal' ? 'tag-int' : 'tag-ext';
    var head = crumb(['产能链', '<span class="' + tagCls + '">' + c.name + ' · ' + c.meas + '</span>', subObj.name]);
    var desc = SUBDESC[chainId][sub];
    var stats, body;
    if (chainId === 'internal') {
      if (sub === 'op') {
        stats = statline([{
          v: 8,
          l: '自制工种',
          tone: 'anchor'
        }, {
          v: 14,
          l: '关联设备'
        }, {
          v: 23,
          l: '可用人员',
          tone: 'ok'
        }, {
          v: 1,
          l: '未绑设备',
          tone: 'warn'
        }]);
        body = toolbar('搜索自制工种…', '新增工种', 'wrench', 'op_int') + table([{
          t: '工种编号',
          w: 120
        }, {
          t: '名称',
          w: 130
        }, {
          t: '可用设备',
          w: 100,
          r: true
        }, {
          t: '可用人员',
          w: 100,
          r: true
        }, {
          t: '产能备注'
        }, {
          t: '操作',
          w: 190,
          act: true
        }], OP_INT) + pager(8);
      } else if (sub === 'eq') {
        stats = statline([{
          v: 14,
          l: '设备总数',
          tone: 'anchor'
        }, {
          v: 12,
          l: '可用',
          tone: 'ok'
        }, {
          v: 2,
          l: '检修',
          tone: 'warn'
        }, {
          v: 3,
          l: '设备组'
        }]);
        body = toolbar('搜索设备…', '新增设备', 'machine', 'equip') + table([{
          t: '设备编号',
          w: 110
        }, {
          t: '名称'
        }, {
          t: '绑定工种',
          w: 120
        }, {
          t: '设备组',
          w: 110
        }, {
          t: '状态',
          w: 110
        }, {
          t: '操作',
          w: 190,
          act: true
        }], EQUIP) + pager(14);
      } else {
        stats = statline([{
          v: 23,
          l: '人员总数',
          tone: 'anchor'
        }, {
          v: 20,
          l: '在岗',
          tone: 'ok'
        }, {
          v: 3,
          l: '请假 / 异常',
          tone: 'warn'
        }, {
          v: 41,
          l: '技能认证'
        }]);
        body = toolbar('搜索人员…', '新增人员', 'users', 'people') + table([{
          t: '工号',
          w: 100
        }, {
          t: '姓名',
          w: 110
        }, {
          t: '技能工种'
        }, {
          t: '班次',
          w: 100
        }, {
          t: '状态',
          w: 110
        }, {
          t: '操作',
          w: 190,
          act: true
        }], PEOPLE) + pager(23);
      }
    } else {
      if (sub === 'op') {
        stats = statline([{
          v: 4,
          l: '外协工种',
          tone: 'anchor'
        }, {
          v: 6,
          l: '可用供应商',
          tone: 'ok'
        }, {
          v: 1,
          l: '合并设置'
        }, {
          v: 3,
          l: '分别设置'
        }]);
        body = toolbar('搜索外协工种…', '新增外协工种', 'wrench', 'op_ext') + table([{
          t: '工种编号',
          w: 120
        }, {
          t: '名称',
          w: 150
        }, {
          t: '默认周期策略',
          w: 150
        }, {
          t: '备注'
        }, {
          t: '操作',
          w: 190,
          act: true
        }], OP_EXT) + pager(4);
      } else {
        stats = statline([{
          v: 6,
          l: '供应商总数',
          tone: 'anchor'
        }, {
          v: 4,
          l: '启用',
          tone: 'ok'
        }, {
          v: 1,
          l: '待复核',
          tone: 'warn'
        }, {
          v: 1,
          l: '停用'
        }]);
        body = toolbar('搜索供应商…', '新增供应商', 'truck', 'supplier') + table([{
          t: '编号',
          w: 90
        }, {
          t: '供应商',
          w: 160
        }, {
          t: '可做外协工种'
        }, {
          t: '默认周期',
          w: 110,
          r: true
        }, {
          t: '状态',
          w: 110
        }, {
          t: '操作',
          w: 190,
          act: true
        }], SUPPLIERS) + pager(6);
      }
    }
    return head + chead(subObj.name, desc) + stats + (sub === 'op' ? pendingCard() : '') + body;
  }
  function pendingCard() {
    if (!PENDING_OPTYPES.length) return '';
    var rows = PENDING_OPTYPES.map(function (p, i) {
      return '<tr data-pi="' + i + '"><td><b>' + p.name + '</b></td>' + '<td><span class="pill warn"><span class="dot"></span>待归类</span></td>' + '<td class="muted" style="font-size:12px">路线引入 · ' + p.from + '</td>' + '<td class="r"><div class="rowact" style="justify-content:flex-end"><button class="mini pend-int" data-pi="' + i + '">建为自制</button><button class="mini pend-ext" data-pi="' + i + '">建为外协</button></div></td></tr>';
    }).join('');
    return '<div class="pend-card"><div class="pend-head"><span class="pill warn"><span class="dot"></span>待归类工种 · 由路线引入</span>' + '<span class="muted" style="font-size:12px">这些工种在路线里出现、但工种库里还没有。建库时选自制 / 外协，归位后对应工序自动可排产。</span></div>' + '<div class="card"><div class="card-scroll"><table class="tbl"><thead><tr><th style="width:160px">工种名</th><th style="width:110px">状态</th><th>来源</th><th class="r" style="width:210px">建库</th></tr></thead><tbody>' + rows + '</tbody></table></div></div></div>';
  }
  function renderContent() {
    var el = document.getElementById('content');
    if (state.node === 'process') el.innerHTML = viewProcess();else if (state.node === 'material') el.innerHTML = viewMaterial();else if (state.node === 'calendar') el.innerHTML = viewCalendar();else el.innerHTML = viewChain(state.node);
    el.querySelectorAll('.subtab[data-chain]').forEach(function (b) {
      b.addEventListener('click', function () {
        state.sub[b.getAttribute('data-chain')] = b.getAttribute('data-sub');
        render();
      });
    });
    wireList();
    wireToolbar();
    document.querySelectorAll('#content .pend-int, #content .pend-ext').forEach(function (b) {
      b.addEventListener('click', function () {
        var i = +b.getAttribute('data-pi');
        var p = PENDING_OPTYPES[i];
        if (!p) return;
        var asInt = b.classList.contains('pend-int');
        if (asInt) KNOWN_INT.push(p.name);else KNOWN_EXT.push(p.name);
        PENDING_OPTYPES.splice(i, 1);
        showFlash('已建为' + (asInt ? '自制' : '外协') + '工种「' + p.name + '」·引用它的工序已转可排产。');
        render();
      });
    });
    if (state.node === 'process') wireProcess();
    if (state.node === 'calendar') wireCalendar();
  }

  /* new / import-export buttons */
  function wireToolbar() {
    var add = document.querySelector('#content .add-btn');
    if (add) add.addEventListener('click', function () {
      var en = add.getAttribute('data-entity');
      if (en === 'part') showAddPartModal();else showFormModal(en);
    });
    document.querySelectorAll('#content .io-btn').forEach(function (io) {
      io.addEventListener('click', function () {
        showImportExport(io.getAttribute('data-entity'), io.getAttribute('data-mode'));
      });
    });
  }

  /* 工艺：双导入按钮 + 零件下钻 + 三步 stepper + 归属分拣 */
  function wireProcess() {
    var ir = document.querySelector('#content .imp-route');
    if (ir) ir.addEventListener('click', function () {
      showImportExport('route', 'imp');
    });
    var ih = document.querySelector('#content .imp-hours');
    if (ih) ih.addEventListener('click', function () {
      showImportExport('hours', 'imp');
    });
    document.querySelectorAll('#content .subtab[data-stage]').forEach(function (b) {
      b.addEventListener('click', function () {
        state.stageFilter = b.getAttribute('data-stage');
        render();
      });
    });
    var gp = document.querySelector('#content .go-pending');
    if (gp) gp.addEventListener('click', function () {
      state.node = 'internal';
      state.sub.internal = 'op';
      render();
    });
    document.querySelectorAll('#content .tbl tbody tr[data-code]').forEach(function (tr) {
      var code = tr.getAttribute('data-code');
      var open = function (e) {
        if (e) e.preventDefault();
        openPartModal(code);
      };
      var lnk = tr.querySelector('.lnk');
      if (lnk) lnk.addEventListener('click', open);
      var act = tr.querySelector('.pl-act');
      if (act) act.addEventListener('click', open);
      var menu = tr.querySelector('.pl-route-menu');
      if (menu) menu.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        openMenu(menu, [{
          icon: UP_SVG,
          label: '导入工艺路线',
          onClick: function () {
            showImportExport('route', 'imp');
          }
        }, {
          icon: PEN_SVG,
          label: '手工新建路线',
          onClick: function () {
            showRouteEntry(code);
          }
        }]);
      });
    });
  }
  function wireHours(code, scope) {
    scope = scope || document.getElementById('content');
    scope.querySelectorAll('.subtab[data-opview]').forEach(function (b) {
      b.addEventListener('click', function () {
        state.opView = b.getAttribute('data-opview');
        render();
      });
    });
    scope.querySelectorAll('.wt-in[data-field="unit"]').forEach(function (inp) {
      inp.addEventListener('input', function () {
        var v = inp.value.trim();
        inp.classList.toggle('empty', v === '');
        inp.classList.toggle('bad', v !== '' && Number(v) === 0);
      });
    });
    var save = scope.querySelector('.pd-save');
    if (save) save.addEventListener('click', function () {
      var ops = PART_OPS[code] || [];
      scope.querySelectorAll('.wt-in').forEach(function (inp) {
        var seq = Number(inp.getAttribute('data-seq')),
          f = inp.getAttribute('data-field');
        var op = ops.find(function (o) {
          return o.seq === seq;
        });
        if (op) op[f] = inp.value.trim();
      });
      var s = partStageOf(code);
      s.hours = hoursStateAfter(code);
      render();
      showFlash('已保存 ' + code + ' 的工序工时（示例数据，刷新后恢复）。');
    });
  }
  function wireSort(code, scope) {
    var content = scope || document.getElementById('content');
    var rows = [].slice.call(content.querySelectorAll('.sort-row'));
    var total = rows.length;
    var confEl = content.querySelector('.sort-confirmed');
    var todoEl = content.querySelector('.sort-todo');
    var finish = content.querySelector('.sort-finish');
    function refresh() {
      var c = rows.filter(function (r) {
        return r.classList.contains('staged');
      }).length;
      if (confEl) confEl.textContent = c;
      if (todoEl) todoEl.textContent = total - c;
      if (finish) {
        finish.disabled = c < total;
        finish.textContent = c < total ? '完成归属 · 解锁工时（还剩 ' + (total - c) + '）' : '完成归属 · 解锁工时（' + total + ' 道）';
      }
    }
    function stage(tr) {
      tr.classList.add('staged');
      tr.classList.remove('attn', 'attn-bad');
      var st = tr.querySelector('.attr-status');
      if (st) st.innerHTML = '<span class="pill info"><span class="dot"></span>已选 · 待提交</span>';
      refresh();
    }
    rows.forEach(function (tr) {
      tr.querySelectorAll('.segm button').forEach(function (b) {
        b.addEventListener('click', function () {
          tr.querySelectorAll('.segm button').forEach(function (x) {
            x.classList.remove('on', 'int', 'ext');
          });
          b.classList.add('on');
          b.classList.add(b.getAttribute('data-attr') === 'int' ? 'int' : 'ext');
          stage(tr);
        });
      });
    });
    if (finish) finish.addEventListener('click', function () {
      if (finish.disabled) return;
      var s = partStageOf(code);
      s.attr = 'done';
      if (s.hours === 'locked') s.hours = hoursStateAfter(code);
      state.openStage = null;
      render();
      showFlash(code + ' 工序归属已确认，工时录入已解锁（示例）。');
    });
    refresh();
  }

  /* selection + batch delete (toolbar-contextual) */
  var currentUpd = null;
  function wireList() {
    var all = document.querySelector('#content .ck-all');
    if (!all) return;
    var selgrp = null;
    var del = document.querySelector('#content .batch-del');
    var selN = document.querySelector('#content .selN');
    var selcount = document.querySelector('#content .selcount');
    var clear = document.querySelector('#content .clear-sel');
    var pgt = document.querySelector('#content .pgtotal');
    function rowsNow() {
      return [].slice.call(document.querySelectorAll('#content .ck-row'));
    }
    function upd() {
      var rows = rowsNow();
      var sel = rows.filter(function (r) {
        return r.checked;
      });
      var has = sel.length > 0;
      selN.textContent = sel.length;
      if (selcount) selcount.hidden = !has;
      if (clear) clear.hidden = !has;
      all.checked = rows.length > 0 && sel.length === rows.length;
      all.indeterminate = has && sel.length < rows.length;
    }
    all.addEventListener('change', function () {
      rowsNow().forEach(function (r) {
        r.checked = all.checked;
      });
      upd();
    });
    rowsNow().forEach(function (r) {
      r.addEventListener('change', upd);
    });
    currentUpd = upd;
    if (clear) clear.addEventListener('click', function () {
      rowsNow().forEach(function (r) {
        r.checked = false;
      });
      upd();
    });
    if (del) del.addEventListener('click', function () {
      var sel = rowsNow().filter(function (r) {
        return r.checked;
      });
      if (!sel.length) {
        showConfirm({
          title: '请先选择要删除的行',
          body: '在列表左侧勾选一个或多个行后，再点击「批量删除」。你也可以勾选表头复选框全选。',
          ok: '知道了',
          info: true
        });
        return;
      }
      showConfirm({
        title: '批量删除所选 ' + sel.length + ' 项？',
        body: '若所选项目存在引用（被<b>工序 / 批次 / 资源</b>引用），对应行将删除失败并提示。确认继续吗？',
        ok: '确认删除 ' + sel.length + ' 项',
        onOk: function () {
          sel.forEach(function (r) {
            var tr = r.closest('tr');
            if (tr) tr.parentNode.removeChild(tr);
          });
          if (pgt) {
            var n = parseInt((pgt.textContent || '0').replace(/[^0-9]/g, ''), 10) || 0;
            pgt.textContent = Math.max(0, n - sel.length);
          }
          upd();
          showFlash('已删除 ' + sel.length + ' 项（示例数据，刷新或切换后恢复）。');
        }
      });
    });
    upd();
  }
  function showConfirm(o) {
    var bg = document.createElement('div');
    bg.className = 'modal-bg';
    var foot = o.info ? '<button class="btn primary ok">' + (o.ok || '知道了') + '</button>' : '<button class="btn cancel">取消</button><button class="btn dangerfill ok">' + (o.ok || '确认') + '</button>';
    bg.innerHTML = '<div class="modal" role="dialog" aria-modal="true">' + '<div class="modal-h">' + o.title + '</div>' + '<div class="modal-b">' + o.body + '</div>' + '<div class="modal-f">' + foot + '</div></div>';
    function close() {
      if (bg.parentNode) bg.parentNode.removeChild(bg);
      document.removeEventListener('keydown', onKey);
    }
    function onKey(e) {
      if (e.key === 'Escape') close();
    }
    bg.addEventListener('click', function (e) {
      if (e.target === bg) close();
    });
    var cancel = bg.querySelector('.cancel');
    if (cancel) cancel.addEventListener('click', close);
    bg.querySelector('.ok').addEventListener('click', function () {
      close();
      if (o.onOk) o.onOk();
    });
    document.addEventListener('keydown', onKey);
    root.appendChild(bg);
  }

  /* ---------------- generic modal shell ---------------- */
  function openModal(html) {
    var bg = document.createElement('div');
    bg.className = 'modal-bg';
    bg.innerHTML = html;
    function close() {
      if (bg.parentNode) bg.parentNode.removeChild(bg);
      document.removeEventListener('keydown', onKey);
    }
    function onKey(e) {
      if (e.key === 'Escape') close();
    }
    bg.addEventListener('click', function (e) {
      if (e.target === bg) close();
    });
    document.addEventListener('keydown', onKey);
    root.appendChild(bg);
    bg.querySelectorAll('[data-close]').forEach(function (b) {
      b.addEventListener('click', close);
    });
    return {
      bg: bg,
      close: close
    };
  }
  function modalHead(icon, title, sub) {
    return '<div class="modal-head"><span class="modal-ico">' + svg(icon) + '</span>' + '<div><div class="modal-h2">' + title + '</div><div class="modal-hs">' + sub + '</div></div>' + '<button class="modal-x" data-close aria-label="关闭">✕</button></div>';
  }

  /* ---------------- 轻量下拉菜单 ---------------- */
  function closeMenu() {
    var m = root.querySelector('.pl-menu');
    if (m) m.parentNode.removeChild(m);
    document.removeEventListener('mousedown', _menuOut);
  }
  function _menuOut(e) {
    var m = root.querySelector('.pl-menu');
    if (m && !m.contains(e.target)) closeMenu();
  }
  function openMenu(anchor, items) {
    closeMenu();
    var m = document.createElement('div');
    m.className = 'pl-menu';
    m.innerHTML = items.map(function (it, i) {
      return '<button class="pl-menu-item" data-i="' + i + '"><span class="pl-menu-ic">' + it.icon + '</span><span>' + it.label + '</span></button>';
    }).join('');
    root.appendChild(m);
    var r = anchor.getBoundingClientRect();
    m.style.top = r.bottom + 6 + 'px';
    m.style.left = Math.max(8, Math.min(r.left, window.innerWidth - 230)) + 'px';
    m.querySelectorAll('.pl-menu-item').forEach(function (b) {
      b.addEventListener('click', function () {
        var i = +b.getAttribute('data-i');
        closeMenu();
        items[i].onClick();
      });
    });
    setTimeout(function () {
      document.addEventListener('mousedown', _menuOut);
    }, 0);
  }

  /* ---------------- 手工新建工艺路线 ---------------- */
  function showRouteEntry(code) {
    var meta = PART_META[code] || {
      name: ''
    };
    var opts = KNOWN_INT.concat(KNOWN_EXT);
    var dataList = '<datalist id="re-oplist">' + opts.map(function (o) {
      return '<option value="' + o + '">' + (KNOWN_INT.indexOf(o) >= 0 ? '自制' : '外协') + '</option>';
    }).join('') + '</datalist>';
    var rows = [{
      seq: '5',
      op: ''
    }, {
      seq: '10',
      op: ''
    }, {
      seq: '20',
      op: ''
    }];
    function attrCellHtml(op) {
      var k = classifyOp(op);
      if (k === 'int') return '<span class="chip b">自制</span>';
      if (k === 'ext') return '<span class="chip a">外协</span>';
      if (k === 'unknown') return '<span class="pill warn"><span class="dot"></span>未识别 · 待归类</span>';
      return '<span class="muted">—</span>';
    }
    function rowHtml(r, i) {
      return '<tr data-i="' + i + '">' + '<td class="r"><input class="wt-in re-seq" style="width:62px;text-align:right" value="' + r.seq + '"></td>' + '<td><input class="wt-in re-op" list="re-oplist" placeholder="选择或输入工种" style="width:172px" value="' + r.op + '"></td>' + '<td class="re-attr">' + attrCellHtml(r.op) + '</td>' + '<td class="r"><button class="mini danger re-del" data-i="' + i + '" aria-label="删除">删除</button></td></tr>';
    }
    function tableHtml() {
      return dataList + '<div class="card"><div class="card-scroll"><table class="tbl re-tbl" style="min-width:470px"><thead><tr><th class="r" style="width:78px">工序号</th><th style="width:192px">工种</th><th style="width:150px">归属</th><th class="r" style="width:70px">操作</th></tr></thead><tbody class="re-body">' + rows.map(rowHtml).join('') + '</tbody></table></div></div>' + '<button class="mini re-add" style="margin-top:10px">+ 添加工序</button>';
    }
    function summaryHtml() {
      var named = rows.filter(function (r) {
        return r.op.trim();
      });
      var names = [];
      named.forEach(function (r) {
        if (classifyOp(r.op) === 'unknown') {
          var n = r.op.trim();
          if (names.indexOf(n) < 0) names.push(n);
        }
      });
      if (!named.length) return '<div class="iohint">至少录入一道工序。</div>';
      if (!names.length) return '<div class="re-ok">✓ ' + named.length + ' 道工序，工种全部识别，保存后可直接进入下一步。</div>';
      return '<div class="match-note">⚠ ' + named.length + ' 道工序中 <b>' + names.length + ' 个工种未识别</b>（' + names.join('、') + '）。保存照常，未识别工种将登记到工种库「待归类 · 待建」，补建后这些工序自动转可排产。</div>';
    }
    function serializeRows() {
      return rows.filter(function (r) {
        return r.op.trim();
      }).map(function (r) {
        return r.seq + ' ' + r.op.trim();
      }).join('   ');
    }
    function previewHtml() {
      var named = rows.filter(function (r) {
        return r.op.trim();
      });
      if (!named.length) return '<div class="iohint">按上面的格式整条粘贴或输入，系统会在这里按工序号自动拆行预览，并标出每道工序的归属。</div>';
      return '<div class="seclabel" style="margin:14px 2px 9px">解析预览 · ' + named.length + ' 道工序</div>' + '<div class="card"><div class="card-scroll"><table class="tbl re-tbl" style="min-width:380px"><thead><tr><th class="r" style="width:78px">工序号</th><th style="width:188px">工种</th><th style="width:160px">归属</th></tr></thead><tbody>' + named.map(function (r) {
        return '<tr><td class="r">' + (r.seq || '—') + '</td><td>' + r.op.trim() + '</td><td class="re-attr">' + attrCellHtml(r.op) + '</td></tr>';
      }).join('') + '</tbody></table></div></div>';
    }
    function textPaneHtml() {
      return '<div class="field full" style="margin:0">' + '<label>路线文字</label>' + '<textarea class="re-text" placeholder="如：5数铣10钳工20数车30外协电镀40总检" style="min-height:104px;line-height:1.7"></textarea>' + '<span class="fhint">工序号与工种可直接连写、不用空格（如 <b>5数铣10钳工20数车</b>），系统按工序号自动拆行；也兼容空格 / 逗号 / 换行分隔，或直接粘贴工艺卡文字。带「外协」前缀或库内外协工种自动归到外协链；库里没有的工种保存后登记为「待归类 · 待建」。</span>' + '</div>' + '<div class="re-prev" style="margin-top:6px"></div>';
    }
    var m = openModal('<div class="modal lg re-modal" role="dialog" aria-modal="true">' + modalHead('route', '手工新建工艺路线' + (code ? ' · ' + code + ' ' + (meta.name || '') : ''), '整条录入：直接粘贴 / 输入一整条路线文字，按工序号自动拆行；也可切到逐行表格逐道编辑。工种优先匹配库内，库里没有的可直接写。') + '<div class="modal-b scroll">' + '<div class="seg re-mode" data-seg="mode" style="margin:2px 0 16px">' + '<button type="button" class="on" data-v="text">整条录入</button>' + '<button type="button" data-v="table">逐行表格</button>' + '</div>' + '<div class="re-pane-text">' + textPaneHtml() + '</div>' + '<div class="re-pane-table" style="display:none">' + tableHtml() + '</div>' + '<div class="re-sum">' + summaryHtml() + '</div>' + '</div>' + '<div class="modal-f"><button class="btn" data-close>取消</button><button class="btn primary re-save">保存路线</button></div></div>');
    var mode = 'text';
    function refreshSum() {
      m.bg.querySelector('.re-sum').innerHTML = summaryHtml();
    }
    function renderPreview() {
      var p = m.bg.querySelector('.re-prev');
      if (p) p.innerHTML = previewHtml();
    }
    function rebuild() {
      m.bg.querySelector('.re-pane-table').innerHTML = tableHtml();
      refreshSum();
      wireTable();
    }
    function wireTable() {
      m.bg.querySelectorAll('.re-op').forEach(function (inp) {
        inp.addEventListener('input', function () {
          var i = +inp.closest('tr').getAttribute('data-i');
          rows[i].op = inp.value;
          inp.closest('tr').querySelector('.re-attr').innerHTML = attrCellHtml(inp.value);
          refreshSum();
        });
      });
      m.bg.querySelectorAll('.re-seq').forEach(function (inp) {
        inp.addEventListener('input', function () {
          rows[+inp.closest('tr').getAttribute('data-i')].seq = inp.value;
        });
      });
      m.bg.querySelectorAll('.re-del').forEach(function (b) {
        b.addEventListener('click', function () {
          rows.splice(+b.getAttribute('data-i'), 1);
          if (!rows.length) rows.push({
            seq: '5',
            op: ''
          });
          rebuild();
        });
      });
      var add = m.bg.querySelector('.re-add');
      if (add) add.addEventListener('click', function () {
        var last = rows.length ? parseInt(rows[rows.length - 1].seq, 10) : 0;
        var nx = (isNaN(last) ? rows.length * 10 : last) + 10;
        rows.push({
          seq: String(nx),
          op: ''
        });
        rebuild();
      });
    }
    function wireText() {
      var ta = m.bg.querySelector('.re-text');
      if (!ta) return;
      ta.value = serializeRows();
      ta.addEventListener('input', function () {
        rows = parseRouteText(ta.value);
        renderPreview();
        refreshSum();
      });
      renderPreview();
    }
    m.bg.querySelectorAll('.re-mode button').forEach(function (b) {
      b.addEventListener('click', function () {
        var v = b.getAttribute('data-v');
        if (v === mode) return;
        mode = v;
        m.bg.querySelectorAll('.re-mode button').forEach(function (x) {
          x.classList.toggle('on', x === b);
        });
        m.bg.querySelector('.re-pane-text').style.display = v === 'text' ? '' : 'none';
        m.bg.querySelector('.re-pane-table').style.display = v === 'table' ? '' : 'none';
        if (v === 'table') {
          rebuild();
        } else {
          var ta = m.bg.querySelector('.re-text');
          if (ta) ta.value = serializeRows();
          renderPreview();
        }
        refreshSum();
      });
    });
    wireTable();
    wireText();
    m.bg.querySelector('.re-save').addEventListener('click', function () {
      var named = rows.filter(function (r) {
        return r.op.trim();
      });
      if (!named.length) {
        showFlash('请至少录入一道工序。');
        return;
      }
      var unk = [];
      named.forEach(function (r) {
        if (classifyOp(r.op) === 'unknown') {
          var n = r.op.trim();
          if (unk.indexOf(n) < 0) unk.push(n);
        }
      });
      if (code) {
        PART_OPS[code] = named.map(function (r) {
          var k = classifyOp(r.op);
          return {
            seq: r.seq,
            op: r.op.trim(),
            dev: '—',
            src: k === 'ext' ? 'ext' : 'int',
            setup: '',
            unit: '',
            ext: k === 'ext' ? '外协' : ''
          };
        });
        PART_STAGE[code] = PART_STAGE[code] || {};
        PART_STAGE[code].route = 'done';
        if (PART_STAGE[code].attr === 'locked' || !PART_STAGE[code].attr) PART_STAGE[code].attr = 'pending';
        if (!PART_STAGE[code].hours) PART_STAGE[code].hours = 'locked';
        var pm = PART_META[code] || (PART_META[code] = {
          name: meta.name || code
        });
        pm.parsed = true;
      }
      unk.forEach(function (n) {
        addPending(n, code ? code + ' ' + (meta.name || '') : '手工录入');
      });
      m.close();
      var msg = '已保存' + (code ? ' ' + code : '') + '路线 · ' + named.length + ' 道工序';
      if (unk.length) msg += '；' + unk.length + ' 个工种未识别，已登记到工种库待建';
      showFlash(msg + '。');
      if (state.openPart === code) state.openStage = null;
      render();
    });
  }

  /* ---------------- 新增 / 编辑 表单 ---------------- */
  var FORMS = {
    part: {
      title: '新增零件',
      icon: 'route',
      sub: '工艺零件模板，保存后加入列表。',
      cols: 6,
      fields: [{
        k: 'code',
        l: '图号',
        ph: '如 T-1024',
        req: true,
        w: 'half'
      }, {
        k: 'name',
        l: '名称',
        ph: '如 回转壳体 F',
        req: true,
        w: 'half'
      }, {
        k: 'route',
        l: '路线文字',
        ph: '如 5数铣 10钳 20数车 30外协电镀 40总检',
        type: 'textarea',
        full: true,
        hint: '每道工序在解析后按归属自动分流到自制 / 外协两条链。'
      }]
    },
    material: {
      title: '新增物料',
      icon: 'cube',
      sub: '物料主数据，供批次按主数据引用。',
      cols: 6,
      fields: [{
        k: 'code',
        l: '物料编号',
        ph: '如 M-2050',
        req: true,
        w: 'half'
      }, {
        k: 'name',
        l: '名称',
        ph: '如 45# 圆钢',
        req: true,
        w: 'half'
      }, {
        k: 'spec',
        l: '规格',
        ph: '如 Ø120 × 2000',
        w: 'half'
      }, {
        k: 'stock',
        l: '库存',
        ph: '如 1,200 kg',
        w: 'half'
      }, {
        k: 'status',
        l: '状态',
        type: 'select',
        opts: ['启用', '低库存', '停用'],
        w: 'half'
      }]
    },
    op_int: {
      title: '新增自制工种',
      icon: 'wrench',
      sub: '自制链工种，按工时口径排产。',
      cols: 6,
      fields: [{
        k: 'code',
        l: '工种编号',
        ph: '如 OT007',
        req: true,
        w: 'half'
      }, {
        k: 'name',
        l: '名称',
        ph: '如 钻孔',
        req: true,
        w: 'half'
      }, {
        k: 'note',
        l: '产能备注',
        ph: '如 瓶颈工序，人员偏紧',
        type: 'textarea',
        full: true
      }]
    },
    equip: {
      title: '新增设备',
      icon: 'machine',
      sub: '每台设备绑定一个自制工种。',
      cols: 6,
      fields: [{
        k: 'code',
        l: '设备编号',
        ph: '如 EQ-15',
        req: true,
        w: 'half'
      }, {
        k: 'name',
        l: '名称',
        ph: '如 立式加工中心 VMC-650',
        req: true,
        w: 'half'
      }, {
        k: 'op',
        l: '绑定工种',
        type: 'select',
        opts: ['数铣', '数车', '钳工', '精磨', '总检'],
        w: 'half',
        hint: '一台设备只绑定一个工种。'
      }, {
        k: 'group',
        l: '设备组',
        type: 'select',
        opts: ['设备组 A', '设备组 B', '设备组 C'],
        w: 'half'
      }, {
        k: 'status',
        l: '状态',
        type: 'select',
        opts: ['可用', '检修'],
        w: 'half'
      }]
    },
    people: {
      title: '新增人员',
      icon: 'users',
      sub: '人员按多技能矩阵参与排产。',
      cols: 6,
      fields: [{
        k: 'code',
        l: '工号',
        ph: '如 P-140',
        req: true,
        w: 'half'
      }, {
        k: 'name',
        l: '姓名',
        ph: '如 孙明',
        req: true,
        w: 'half'
      }, {
        k: 'skills',
        l: '技能工种',
        type: 'chips',
        opts: ['数铣', '数车', '钳工', '精磨', '钻孔', '总检'],
        full: true,
        hint: '可多选，构成多技能矩阵。'
      }, {
        k: 'shift',
        l: '班次',
        type: 'select',
        opts: ['白班', '两班倒', '夜班'],
        w: 'half'
      }, {
        k: 'status',
        l: '状态',
        type: 'select',
        opts: ['在岗', '请假'],
        w: 'half'
      }]
    },
    op_ext: {
      title: '新增外协工种',
      icon: 'wrench',
      sub: '外协链工种，按周期口径排产。',
      cols: 5,
      fields: [{
        k: 'code',
        l: '工种编号',
        ph: '如 OT055',
        req: true,
        w: 'half'
      }, {
        k: 'name',
        l: '名称',
        ph: '如 阳极氧化',
        req: true,
        w: 'half'
      }, {
        k: 'policy',
        l: '默认周期策略',
        type: 'select',
        opts: ['分别设置', '合并设置'],
        w: 'half',
        hint: '合并设置：连续外协工序按整组周期计。'
      }, {
        k: 'note',
        l: '备注',
        ph: '如 需炉前确认整组周期',
        type: 'textarea',
        full: true
      }]
    },
    supplier: {
      title: '新增供应商',
      icon: 'truck',
      sub: '供应商绑外协工种并给默认周期。',
      cols: 6,
      fields: [{
        k: 'code',
        l: '编号',
        ph: '如 S-09',
        req: true,
        w: 'half'
      }, {
        k: 'name',
        l: '供应商',
        ph: '如 华表面处理',
        req: true,
        w: 'half'
      }, {
        k: 'ops',
        l: '可做外协工种',
        type: 'chips',
        opts: ['电镀', '发黑', '热处理', '喷涂'],
        full: true
      }, {
        k: 'lead',
        l: '默认周期',
        ph: '如 3 天',
        w: 'half'
      }, {
        k: 'status',
        l: '状态',
        type: 'select',
        opts: ['启用', '待复核', '停用'],
        w: 'half'
      }]
    }
  };
  function fieldHtml(f) {
    var inner;
    if (f.type === 'textarea') inner = '<textarea data-k="' + f.k + '" placeholder="' + (f.ph || '') + '"></textarea>';else if (f.type === 'select') {
      var car = '<span class="selcar"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg></span>';
      var ck = '<span class="ck"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L19 7"/></svg></span>';
      inner = '<div class="selbox" data-k="' + f.k + '" data-val="' + f.opts[0] + '"><button type="button" class="selbtn"><span class="selval">' + f.opts[0] + '</span>' + car + '</button><div class="selpop">' + f.opts.map(function (o, i) {
        return '<div class="selopt' + (i === 0 ? ' on' : '') + '" data-v="' + o + '">' + o + ck + '</div>';
      }).join('') + '</div></div>';
    } else if (f.type === 'chips') inner = '<div class="fchips" data-k="' + f.k + '">' + f.opts.map(function (o) {
      return '<span class="fchip" data-v="' + o + '">' + o + '</span>';
    }).join('') + '</div>';else inner = '<input data-k="' + f.k + '" placeholder="' + (f.ph || '') + '">';
    return '<div class="field' + (f.full ? ' full' : '') + '">' + '<label>' + f.l + (f.req ? '<span class="req">*</span>' : '') + '</label>' + inner + (f.hint ? '<span class="fhint">' + f.hint + '</span>' : '') + '</div>';
  }
  function pillFor(s) {
    var map = {
      '启用': 'ok',
      '已解析': 'ok',
      '可用': 'ok',
      '在岗': 'ok',
      '低库存': 'warn',
      '检修': 'warn',
      '请假': 'warn',
      '待复核': 'warn',
      '待解析': 'warn',
      '未解析': 'warn',
      '停用': 'off'
    };
    return '<span class="pill ' + (map[s] || 'info') + '"><span class="dot"></span>' + s + '</span>';
  }
  function chipsOf(arr, cls) {
    return arr && arr.length ? '<span class="chipline">' + arr.map(function (x) {
      return '<span class="chip ' + cls + '">' + x + '</span>';
    }).join('') + '</span>' : '<span class="muted">—</span>';
  }
  function buildRow(entity, v) {
    var lnk = '<a class="lnk">' + (v.code || '—') + '</a>';
    if (entity === 'part') return [lnk, v.name || '—', '<span class="route">' + (v.route || '—') + '</span>', '<span class="muted" style="font-size:12px">待生成</span>', pillFor(v.status || '待解析'), actBtns()];
    if (entity === 'material') return [lnk, v.name || '—', v.spec || '<span class="muted">—</span>', v.stock || '<span class="muted">—</span>', pillFor(v.status || '启用'), actBtns()];
    if (entity === 'op_int') return [lnk, v.name || '—', '0', '0', v.note || '<span class="muted">—</span>', actBtns('查看绑定')];
    if (entity === 'equip') return [lnk, v.name || '—', v.op ? '<span class="chip b">' + v.op + '</span>' : '<span class="muted">—</span>', v.group || '—', pillFor(v.status || '可用'), actBtns()];
    if (entity === 'people') return [lnk, v.name || '—', chipsOf(v.skills, 'b'), v.shift || '白班', pillFor(v.status || '在岗'), actBtns()];
    if (entity === 'op_ext') return [lnk, v.name || '—', v.policy || '分别设置', v.note || '<span class="muted">—</span>', actBtns('查看供应商')];
    if (entity === 'supplier') return [lnk, v.name || '—', chipsOf(v.ops, 'a'), v.lead || '—', pillFor(v.status || '启用'), actBtns()];
    return [];
  }
  function addRowToTable(cells) {
    var tbody = document.querySelector('#content tbody');
    if (!tbody) return;
    var ths = [].slice.call(document.querySelectorAll('#content thead th')).slice(1);
    var tr = document.createElement('tr');
    var html = '<td class="cbx"><input type="checkbox" class="ck-row"></td>';
    cells.forEach(function (c, i) {
      var th = ths[i];
      var cls = th && th.classList.contains('r') ? 'r' : th && th.classList.contains('actcol') ? 'actcol' : '';
      html += '<td class="' + cls + '">' + c + '</td>';
    });
    tr.innerHTML = html;
    tr.style.animation = 'fade .2s ease';
    tbody.insertBefore(tr, tbody.firstChild);
    var ck = tr.querySelector('.ck-row');
    if (ck) ck.addEventListener('change', function () {
      if (currentUpd) currentUpd();
    });
    var pgt = document.querySelector('#content .pgtotal');
    if (pgt) {
      var n = parseInt((pgt.textContent || '0').replace(/[^0-9]/g, ''), 10) || 0;
      pgt.textContent = n + 1;
    }
    if (currentUpd) currentUpd();
  }
  function closeAllSel(root) {
    (root || document).querySelectorAll('.selbox.open').forEach(function (x) {
      x.classList.remove('open');
      var p = x.querySelector('.selpop');
      if (p) {
        p.style.position = '';
        p.style.left = '';
        p.style.top = '';
        p.style.bottom = '';
        p.style.width = '';
      }
    });
  }
  function openSel(box) {
    box.classList.add('open');
    var pop = box.querySelector('.selpop');
    var r = box.querySelector('.selbtn').getBoundingClientRect();
    var ph = Math.min(pop.scrollHeight, 220);
    pop.style.position = 'fixed';
    pop.style.left = r.left + 'px';
    pop.style.width = r.width + 'px';
    if (window.innerHeight - r.bottom < ph + 16) {
      pop.style.top = '';
      pop.style.bottom = window.innerHeight - r.top + 5 + 'px';
    } else {
      pop.style.bottom = '';
      pop.style.top = r.bottom + 5 + 'px';
    }
  }
  /* ---------------- 新增零件 · 一次填完（路线 + 归属 + 工时） ---------------- */
  function showAddPartModal() {
    var rows = []; // {seq, op, src, setup, unit}
    function sugOf(op) {
      var k = classifyOp(op);
      return k === 'ext' ? 'ext' : k === 'int' ? 'int' : null;
    }
    function reparse(text) {
      var snap = {};
      rows.forEach(function (r) {
        snap[r.seq + '|' + r.op] = r;
      });
      rows = parseRouteText(text).map(function (p) {
        var prev = snap[p.seq + '|' + p.op];
        if (prev) return prev;
        var s = sugOf(p.op);
        return {
          seq: p.seq,
          op: p.op,
          src: s === 'ext' ? 'ext' : 'int',
          setup: '',
          unit: ''
        };
      });
    }
    function stats() {
      var intRows = rows.filter(function (r) {
        return r.src === 'int';
      });
      var missing = intRows.filter(function (r) {
        return r.unit === '' || Number(r.unit) === 0;
      }).length;
      var unk = [];
      rows.forEach(function (r) {
        if (classifyOp(r.op) === 'unknown' && unk.indexOf(r.op) < 0) unk.push(r.op);
      });
      return {
        total: rows.length,
        intN: intRows.length,
        extN: rows.length - intRows.length,
        missing: missing,
        unk: unk
      };
    }
    function summaryHtml() {
      if (!rows.length) return '';
      var s = stats();
      var line = '<div class="statline" style="margin-top:2px">' + '<div class="stat anchor"><span class="sv">' + s.total + '</span><span class="sl">工序</span></div>' + '<div class="stat"><span class="sv ap-intn">' + s.intN + '</span><span class="sl">自制</span></div>' + '<div class="stat"><span class="sv ap-extn">' + s.extN + '</span><span class="sl">外协</span></div>' + '<div class="stat ' + (s.missing ? 'warn' : 'ok') + '"><span class="sv ap-miss">' + s.missing + '</span><span class="sl">缺工时</span></div>' + '</div>';
      var note = s.unk.length ? '<div class="match-note" style="margin-top:10px">⚠ <b>' + s.unk.length + ' 个工种未识别</b>（' + s.unk.join('、') + '）：已默认归到自制，可在「归属」列改；保存后登记到工种库「待归类 · 待建」。</div>' : s.missing ? '<div class="iohint" style="margin-top:10px">自制工序的换型 / 单件工时现在就能填；留空则该零件保存后停在 <b>「待填工时」</b>，仍可稍后补。</div>' : '<div class="re-ok" style="margin-top:10px">✓ 路线、归属、工时已齐备，保存后<b>直接就绪</b>，可参与排产。</div>';
      return line + note;
    }
    function rowHtml(r, i) {
      var sug = sugOf(r.op);
      var seg = '<span class="segm ap-seg" data-i="' + i + '"><button type="button" data-attr="int"' + (r.src === 'int' ? ' class="on int"' : '') + '>自制</button><button type="button" data-attr="ext"' + (r.src === 'ext' ? ' class="on ext"' : '') + '>外协</button></span>';
      var tag = sug ? '<span class="sug">建议 ' + (sug === 'int' ? '自制' : '外协') + '</span>' : '<span class="conf none" style="margin-left:7px">未识别 · 请指定</span>';
      var wt;
      if (r.src === 'ext') wt = '<td class="wt-col" colspan="2" style="text-align:center"><span class="muted" style="font-size:12px">外协工序无工时 · 走周期</span></td>';else wt = '<td class="r wt-col"><input class="wt-in ap-setup" data-i="' + i + '" inputmode="decimal" placeholder="0" style="width:74px;text-align:right" value="' + r.setup + '"></td>' + '<td class="r wt-col"><input class="wt-in ap-unit" data-i="' + i + '" inputmode="decimal" placeholder="必填" style="width:74px;text-align:right" value="' + r.unit + '"></td>';
      return '<tr data-i="' + i + '">' + '<td class="num"><b>' + r.seq + '</b></td>' + '<td>' + r.op + '</td>' + '<td><div class="attr-cell">' + seg + tag + '</div></td>' + wt + '</tr>';
    }
    function tableHtml() {
      if (!rows.length) return '<div class="iohint">在上面整条输入路线（如 <b>5数铣10钳20数车30外协电镀40总检</b>），系统按工序号自动拆行，并为每道工序给出<b>自制 / 外协</b>建议；自制工序可直接填工时。</div>';
      return '<div class="seclabel" style="margin:16px 2px 9px">工序明细 · 归属与工时 <small style="font-weight:500;color:var(--ui-muted)">建议 → 确认，自制填工时</small></div>' + '<div class="card"><div class="card-scroll"><table class="tbl op-tbl" style="min-width:560px;table-layout:auto"><thead><tr>' + '<th class="num" style="width:64px">工序号</th><th style="width:120px">工种</th><th style="width:210px">归属</th>' + '<th class="r wt-col" style="width:118px">换型工时<small>定额·h</small></th><th class="r wt-col" style="width:118px">单件工时<small>定额·h</small></th>' + '</tr></thead><tbody>' + rows.map(rowHtml).join('') + '</tbody></table></div></div>';
    }
    var m = openModal('<div class="modal lg" role="dialog" aria-modal="true">' + modalHead('route', '新增零件', '一处填完<b>图号 / 名称 + 路线 + 归属 + 工时</b>，保存即按完成度落到对应阶段，无需再逐步操作。') + '<div class="modal-b form scroll">' + '<div class="fgrid">' + '<div class="field"><label>图号<span class="req">*</span></label><input class="ap-code" placeholder="如 T-1024"></div>' + '<div class="field"><label>名称<span class="req">*</span></label><input class="ap-name" placeholder="如 回转壳体 F"></div>' + '<div class="field full"><label>路线文字<span class="req">*</span></label><textarea class="ap-route" placeholder="如：5数铣10钳20数车30外协电镀40总检" style="min-height:88px;line-height:1.7"></textarea>' + '<span class="fhint">工序号与工种可直接连写、不用空格，系统按工序号自动拆行；也兼容空格 / 逗号 / 换行。带「外协」前缀或库内外协工种自动归到外协链。</span></div>' + '</div>' + '<div class="ap-parsed"></div>' + '<div class="ap-sum"></div>' + '</div>' + '<div class="modal-f"><button class="btn" data-close>取消</button><button class="btn primary ap-save"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>保存并加入列表</button></div></div>');
    function wireRows() {
      m.bg.querySelectorAll('.ap-seg button').forEach(function (b) {
        b.addEventListener('click', function () {
          var i = +b.closest('.ap-seg').getAttribute('data-i');
          rows[i].src = b.getAttribute('data-attr');
          renderParsed();
        });
      });
      m.bg.querySelectorAll('.ap-setup').forEach(function (inp) {
        inp.addEventListener('input', function () {
          rows[+inp.getAttribute('data-i')].setup = inp.value.trim();
        });
      });
      m.bg.querySelectorAll('.ap-unit').forEach(function (inp) {
        inp.addEventListener('input', function () {
          rows[+inp.getAttribute('data-i')].unit = inp.value.trim();
          refreshSum();
        });
      });
    }
    function refreshSum() {
      var s = stats(),
        sum = m.bg.querySelector('.ap-sum');
      var iN = sum.querySelector('.ap-intn'),
        eN = sum.querySelector('.ap-extn'),
        mS = sum.querySelector('.ap-miss');
      if (iN) iN.textContent = s.intN;
      if (eN) eN.textContent = s.extN;
      if (mS) {
        mS.textContent = s.missing;
        var st = mS.closest('.stat');
        if (st) {
          st.classList.toggle('warn', !!s.missing);
          st.classList.toggle('ok', !s.missing);
        }
      }
    }
    function renderParsed() {
      m.bg.querySelector('.ap-parsed').innerHTML = tableHtml();
      m.bg.querySelector('.ap-sum').innerHTML = summaryHtml();
      wireRows();
    }
    var ta = m.bg.querySelector('.ap-route');
    ta.addEventListener('input', function () {
      reparse(ta.value);
      ta.closest('.field').classList.remove('err');
      renderParsed();
    });
    renderParsed();
    m.bg.querySelector('.ap-save').addEventListener('click', function () {
      var codeEl = m.bg.querySelector('.ap-code'),
        nameEl = m.bg.querySelector('.ap-name');
      var code = (codeEl.value || '').trim(),
        name = (nameEl.value || '').trim(),
        bad = null;
      [[codeEl, code], [nameEl, name]].forEach(function (p) {
        p[0].closest('.field').classList.toggle('err', !p[1]);
        if (!p[1] && !bad) bad = p[0];
      });
      if (bad) {
        bad.focus();
        showFlash('请先填写图号与名称。');
        return;
      }
      if (!rows.length) {
        ta.closest('.field').classList.add('err');
        ta.focus();
        showFlash('请先录入工艺路线。');
        return;
      }
      if (PART_META[code]) {
        codeEl.closest('.field').classList.add('err');
        codeEl.focus();
        showFlash('图号 ' + code + ' 已存在。');
        return;
      }
      var ops = rows.map(function (r) {
        var ext = r.src === 'ext';
        return {
          seq: r.seq,
          op: r.op,
          dev: ext ? '外协 · 待定供应商' : '—',
          src: r.src,
          setup: ext ? '' : r.setup || '0',
          unit: ext ? '' : r.unit,
          ext: ext ? '外协 · 待定周期' : ''
        };
      });
      rows.forEach(function (r) {
        if (classifyOp(r.op) === 'unknown') addPending(r.op, code + ' ' + name);
      });
      var intRows = ops.filter(function (o) {
        return o.src === 'int';
      });
      var allFilled = intRows.length > 0 && intRows.every(function (o) {
        return o.unit !== '' && Number(o.unit) !== 0;
      });
      PART_META[code] = {
        name: name,
        parsed: true
      };
      PART_OPS[code] = ops;
      PART_STAGE[code] = {
        route: 'done',
        attr: 'done',
        hours: allFilled ? 'done' : 'pending'
      };
      PART_CODES.unshift(code);
      state.stageFilter = 'all';
      m.close();
      render();
      showFlash('已新增「' + code + ' ' + name + '」· ' + ops.length + ' 道工序，' + (allFilled ? '三步齐备，已就绪' : '待补工时') + '（示例数据，刷新后恢复）。');
    });
    var f = m.bg.querySelector('.ap-code');
    if (f) f.focus();
  }
  function showFormModal(entity) {
    var cfg = FORMS[entity];
    if (!cfg) return;
    var grid = '<div class="fgrid">' + cfg.fields.map(fieldHtml).join('') + '</div>';
    var m = openModal('<div class="modal lg" role="dialog" aria-modal="true">' + modalHead(cfg.icon, cfg.title, cfg.sub) + '<div class="modal-b form">' + grid + '</div>' + '<div class="modal-f"><button class="btn" data-close>取消</button><button class="btn primary save">保存并加入列表</button></div></div>');
    m.bg.querySelectorAll('.fchip').forEach(function (c) {
      c.addEventListener('click', function () {
        c.classList.toggle('on');
      });
    });
    m.bg.querySelectorAll('.selbox').forEach(function (box) {
      box.querySelector('.selbtn').addEventListener('click', function (e) {
        e.stopPropagation();
        var wasOpen = box.classList.contains('open');
        closeAllSel(m.bg);
        if (!wasOpen) openSel(box);
      });
      box.querySelectorAll('.selopt').forEach(function (opt) {
        opt.addEventListener('click', function (e) {
          e.stopPropagation();
          var v = opt.getAttribute('data-v');
          box.setAttribute('data-val', v);
          box.querySelector('.selval').textContent = v;
          box.querySelectorAll('.selopt').forEach(function (o) {
            o.classList.toggle('on', o === opt);
          });
          closeAllSel(m.bg);
        });
      });
    });
    m.bg.querySelector('.modal-b').addEventListener('click', function () {
      closeAllSel(m.bg);
    });
    m.bg.querySelector('.save').addEventListener('click', function () {
      var vals = {},
        bad = null;
      cfg.fields.forEach(function (f) {
        var wrap, val;
        if (f.type === 'chips') {
          wrap = m.bg.querySelector('[data-k="' + f.k + '"]');
          val = [].slice.call(wrap.querySelectorAll('.fchip.on')).map(function (x) {
            return x.getAttribute('data-v');
          });
        } else if (f.type === 'select') {
          val = m.bg.querySelector('[data-k="' + f.k + '"]').getAttribute('data-val');
        } else {
          var elx = m.bg.querySelector('[data-k="' + f.k + '"]');
          val = (elx.value || '').trim();
          if (f.req && !val) {
            if (!bad) bad = elx;
            elx.closest('.field').classList.add('err');
          } else {
            elx.closest('.field').classList.remove('err');
          }
        }
        vals[f.k] = val;
      });
      if (bad) {
        bad.focus();
        showFlash('请先填写带 * 的必填项。');
        return;
      }
      addRowToTable(buildRow(entity, vals));
      m.close();
      showFlash('已新增「' + (vals.name || vals.code) + '」（示例数据，刷新后恢复）。');
    });
    var first = m.bg.querySelector('input, textarea, select');
    if (first) first.focus();
  }

  /* ---------------- 批量导入 / 导出 ---------------- */
  var IO_LABEL = {
    part: '零件工艺',
    material: '物料',
    op_int: '自制工种',
    equip: '设备',
    people: '人员',
    op_ext: '外协工种',
    supplier: '供应商',
    route: '工艺路线（工艺室）',
    hours: '工时定额（定额室）'
  };
  function showImportExport(entity, mode) {
    mode = mode === 'exp' ? 'exp' : 'imp';
    var label = IO_LABEL[entity] || '数据';
    var isImp = mode === 'imp';
    var body = isImp ? '<div class="iopane on" data-pane="imp">' + '<div class="tmpl-row"><span class="tmpl-ico"><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/><path d="M9.5 13l1.8 1.8L15 11"/></svg></span>' + '<div><div class="tmpl-t">' + label + '导入模板.xlsx</div><div class="tmpl-s">含字段说明与示例行，按模板填写后上传</div></div>' + '<button class="mini dl-tmpl">下载模板</button></div>' + '<div class="drop" id="io-drop"><div class="di"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4M7 9l5-5 5 5"/><path d="M5 16v4h14v-4"/></svg></div>' + '<div class="dt">点击选择文件，或拖拽到此处</div><div class="ds">支持 .xlsx / .csv，单次最多 2,000 行</div></div>' + '<div class="iohint">导入采用<b>「按编号增量更新」</b>：编号已存在则更新，不存在则新增。被引用项的关键字段变更会二次确认。</div>' + '</div>' : '<div class="iopane on" data-pane="exp">' + '<div class="seclabel">导出范围</div>' + '<div class="iorow on" data-scope="cur"><span class="radio"></span><div><div class="iotitle">当前筛选结果</div><div class="iosub">按当前搜索 / 子页范围导出</div></div><span class="iotag">本页</span></div>' + '<div class="iorow" data-scope="all"><span class="radio"></span><div><div class="iotitle">全部 ' + label + '</div><div class="iosub">忽略筛选，导出整张表</div></div></div>' + '<div class="seclabel" style="margin-top:14px">文件格式</div>' + '<div class="seg"><button class="on" data-fmt="xlsx">Excel (.xlsx)</button><button data-fmt="csv">CSV (.csv)</button></div>' + '</div>';
    var m = openModal('<div class="modal' + (isImp ? ' lg' : '') + '" role="dialog" aria-modal="true">' + modalHead(isImp ? 'import' : 'export', (isImp ? '批量导入 · ' : '批量导出 · ') + label, isImp ? '从 Excel / CSV 成批导入' + label + '数据。' : '把' + label + '导出为 Excel / CSV 文件。') + '<div class="modal-b scroll">' + body + '</div>' + '<div class="modal-f"><button class="btn" data-close>取消</button><button class="btn primary io-do">' + (isImp ? '确认导入' : '导出文件') + '</button></div></div>');
    if (isImp) {
      m.bg.querySelector('.dl-tmpl').addEventListener('click', function (e) {
        e.stopPropagation();
        showFlash('已下载「' + label + '导入模板.xlsx」（示例）。');
      });
      var drop = m.bg.querySelector('#io-drop');
      drop.addEventListener('click', function () {
        drop.classList.add('has');
        drop.querySelector('.dt').innerHTML = '<b>' + label + '_示例.xlsx</b> · 128 行待导入';
        drop.querySelector('.ds').textContent = '校验通过：可导入 126 行，2 行编号冲突将更新';
      });
    } else {
      m.bg.querySelectorAll('.iorow').forEach(function (r) {
        r.addEventListener('click', function () {
          m.bg.querySelectorAll('.iorow').forEach(function (x) {
            x.classList.toggle('on', x === r);
          });
        });
      });
      m.bg.querySelectorAll('.seg button').forEach(function (b) {
        b.addEventListener('click', function () {
          m.bg.querySelectorAll('.seg button').forEach(function (x) {
            x.classList.toggle('on', x === b);
          });
        });
      });
    }
    m.bg.querySelector('.io-do').addEventListener('click', function () {
      m.close();
      if (isImp) showFlash('已导入 ' + label + ' 126 行 · 更新 2 行（示例）。');else {
        var fmt = m.bg.querySelector('.seg button.on').getAttribute('data-fmt');
        showFlash('已导出 ' + label + ' 列表（.' + fmt + '，示例）。');
      }
    });
  }
  var _toastT;
  function showFlash(msg) {
    var t = document.getElementById('toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'toast';
      t.className = 'toast';
      root.appendChild(t);
    }
    t.innerHTML = '<span class="tdot"></span><span>' + msg + '</span>';
    t.classList.add('on');
    clearTimeout(_toastT);
    _toastT = setTimeout(function () {
      t.classList.remove('on');
    }, 2800);
  }
  function render() {
    renderRail();
    renderContent();
    if (partModal) partModal.repaint();
  }
  render();

  /* ---- 统一详情：表格内编号 / 行内「查看」按钮 → 详情抽屉；「删除」→ 确认 ---- */
  var contentEl = root.querySelector('#content') || document.getElementById('content');
  if (contentEl && window.APSDetail) {
    contentEl.addEventListener('click', function (e) {
      // 编号链接（排除工艺零件列表，那里点编号进三步详情）
      var lnk = e.target.closest('a.lnk');
      if (lnk && !e.target.closest('tr[data-code]')) {
        var code = (lnk.textContent || '').trim();
        if (window.APSDetail.has(code)) {
          e.preventDefault();
          e.stopPropagation();
          window.APSDetail.open(code);
          return;
        }
      }
      // 行内操作按钮
      var mini = e.target.closest('.rowact .mini');
      if (mini) {
        var tr = mini.closest('tr');
        var lk = tr && tr.querySelector('.lnk');
        var rc = lk ? (lk.textContent || '').trim() : '';
        if (mini.classList.contains('danger')) {
          if (rc) {
            e.preventDefault();
            showConfirm({
              title: '删除「' + rc + '」？',
              body: '若该项被<b>工序 / 批次 / 资源</b>引用，将删除失败并提示。确认继续吗？',
              ok: '确认删除',
              onOk: function () {
                if (tr && tr.parentNode) tr.parentNode.removeChild(tr);
                if (currentUpd) currentUpd();
                showFlash('已删除「' + rc + '」（示例数据，刷新后恢复）。');
              }
            });
          }
          return;
        }
        if (rc && window.APSDetail.has(rc)) {
          e.preventDefault();
          e.stopPropagation();
          window.APSDetail.open(rc);
        }
      }
    });
  }
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/plana-logic.js", error: String((e && e.message) || e) }); }

// ui_kits/workbench/table-enhance.js
try { (() => {
/* APS Workbench · table-enhance.js
 * Progressive enhancer for the plana-native plain-DOM tables (`.plana table.tbl`).
 * Adds click-to-sort, per-column filter, and column resize — matching the
 * React <Table> tools visually (shared `aps-*` classes). React-managed tables
 * carry data-aps-rtable and have their own logic, so they are never touched.
 *
 * plana-logic.js repaints its root via innerHTML, replacing table nodes; a
 * MutationObserver re-enhances any fresh `.tbl` (sort/filter state resets with
 * the repaint, which is expected).
 */
(function () {
  "use strict";

  var CSS_ID = "aps-table-tools-css";
  var SHARED_CSS = [".aps-th{position:relative}", ".aps-th-inner{display:inline-flex;align-items:center;gap:6px;max-width:100%}", ".aps-th-sortable{cursor:pointer}", ".aps-th-label{overflow:hidden;text-overflow:ellipsis}", ".aps-sortglyph{display:inline-block;width:7px;height:13px;position:relative;color:currentColor;opacity:.3;transition:opacity .12s;flex:none}", ".aps-sortglyph::before,.aps-sortglyph::after{content:'';position:absolute;left:0;border-left:3.5px solid transparent;border-right:3.5px solid transparent}", ".aps-sortglyph::before{top:2px;border-bottom:4px solid currentColor}", ".aps-sortglyph::after{bottom:2px;border-top:4px solid currentColor}", ".aps-th:hover .aps-sortglyph{opacity:.55}", ".aps-sortglyph.asc,.aps-sortglyph.desc{opacity:1}", ".aps-sortglyph.asc::after{opacity:.2}", ".aps-sortglyph.desc::before{opacity:.2}", ".aps-filter-btn{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:0;background:transparent;border-radius:4px;cursor:pointer;color:inherit;opacity:0;padding:0;flex:none;transition:opacity .12s,background-color .12s,color .12s}", ".aps-th:hover .aps-filter-btn{opacity:.55}", ".aps-filter-btn:hover{background:var(--ui-surface-muted);opacity:1}", ".aps-filter-btn.on{opacity:1;color:var(--ui-primary);background:var(--ui-primary-soft)}", ".aps-th-resize{position:absolute;top:0;right:0;height:100%;width:10px;cursor:col-resize;user-select:none;touch-action:none;z-index:4}", ".aps-th-resize::after{content:'';position:absolute;right:3px;top:22%;height:56%;width:2px;border-radius:2px;background:transparent;transition:background-color .12s}", ".aps-th-resize:hover::after,.aps-th-resize.dragging::after{background:var(--ui-primary)}", ".aps-filter-pop{position:fixed;z-index:9999;background:var(--ui-card-bg);border:1px solid var(--ui-border);border-radius:8px;box-shadow:var(--ui-shadow-md);padding:8px;width:240px;box-sizing:border-box}", ".aps-filter-pop input[type=checkbox]{width:15px;height:15px;flex:none;margin:0;padding:0;accent-color:var(--ui-primary);cursor:pointer}", ".aps-fp-list{max-height:220px;overflow:auto;margin-top:7px;display:flex;flex-direction:column;gap:1px;border-top:1px solid var(--ui-border);padding-top:6px}", ".aps-fp-opt{display:flex;align-items:center;gap:8px;padding:5px 6px;border-radius:5px;cursor:pointer;font-size:13px;color:var(--ui-text);user-select:none}", ".aps-fp-opt:hover{background:var(--ui-surface-muted)}", ".aps-fp-opt-label{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}", ".aps-fp-opt-count{flex:none;color:var(--ui-muted);font-size:11.5px;font-variant-numeric:tabular-nums}", ".aps-fp-all{font-weight:600;border-bottom:1px solid var(--ui-border);border-radius:0;margin-bottom:2px;padding-bottom:7px}", ".aps-fp-empty{padding:14px 6px;text-align:center;color:var(--ui-muted);font-size:12px}", ".aps-filter-pop input{width:100%;height:32px;padding:0 10px;border:1px solid var(--ui-border);border-radius:6px;background:var(--ui-card-bg);font-family:inherit;font-size:13px;color:var(--ui-text);box-sizing:border-box}", ".aps-filter-pop input:focus{outline:none;border-color:var(--ui-primary);box-shadow:var(--ui-focus-ring)}", ".aps-fp-foot{display:flex;justify-content:space-between;align-items:center;margin-top:7px}", ".aps-fp-clear{border:0;background:transparent;color:var(--ui-muted);font-size:12px;cursor:pointer;font-family:inherit;padding:2px 4px;border-radius:4px}", ".aps-fp-clear:hover{color:var(--ui-text);background:var(--ui-surface-muted)}", ".aps-fp-count{font-size:11.5px;color:var(--ui-muted);font-variant-numeric:tabular-nums}", /* plana th: defeat the scoped overflow:hidden + give a positioning context */
  ".plana table.tbl th.aps-th{overflow:visible;position:relative}"].join("");
  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    var el = document.createElement("style");
    el.id = CSS_ID;
    el.textContent = SHARED_CSS;
    document.head.appendChild(el);
  }
  var FUNNEL_SVG = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 5h18l-7 8v5l-4 2v-7z"/></svg>';
  function cmpVals(a, b) {
    var sa = a == null ? "" : String(a);
    var sb = b == null ? "" : String(b);
    return sa.localeCompare(sb, "zh-Hans-CN", {
      numeric: true,
      sensitivity: "base"
    });
  }
  function cellText(tr, idx) {
    var c = tr.cells[idx];
    return c ? (c.textContent || "").trim() : "";
  }

  // ---- single shared filter popover ----
  var CURRENT_POP = null;
  function closePop() {
    if (CURRENT_POP && CURRENT_POP.parentNode) CURRENT_POP.parentNode.removeChild(CURRENT_POP);
    CURRENT_POP = null;
  }
  document.addEventListener("mousedown", function (e) {
    if (!CURRENT_POP) return;
    if (e.target.closest("[data-aps-fpop]") || e.target.closest("[data-aps-fbtn]")) return;
    closePop();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closePop();
  });
  window.addEventListener("scroll", closePop, true);
  function dataRowsOf(table) {
    return (table.__apsOrig || []).filter(function (tr) {
      return tr.parentNode && tr.parentNode.tagName === "TBODY" && tr.closest("table") === table;
    });
  }
  function visibleCount(table) {
    return dataRowsOf(table).filter(function (tr) {
      return tr.style.display !== "none";
    }).length;
  }
  function applyFilters(table) {
    var f = table.__apsFilters || {};
    var entries = Object.keys(f).map(function (k) {
      return [parseInt(k, 10), f[k]];
    }).filter(function (e) {
      return Array.isArray(e[1]);
    });
    dataRowsOf(table).forEach(function (tr) {
      var ok = entries.every(function (e) {
        return e[1].indexOf(cellText(tr, e[0])) !== -1;
      });
      tr.style.display = ok ? "" : "none";
    });
  }
  function distinctForCol(table, idx) {
    var m = {};
    var order = [];
    (table.__apsOrig || []).forEach(function (tr) {
      var t = cellText(tr, idx);
      if (!Object.prototype.hasOwnProperty.call(m, t)) {
        m[t] = 0;
        order.push(t);
      }
      m[t] += 1;
    });
    order.sort(cmpVals);
    return order.map(function (v) {
      return {
        value: v,
        count: m[v]
      };
    });
  }
  function applyOrder(table) {
    var tbody = table.tBodies[0];
    if (!tbody) return;
    var s = table.__apsSort;
    var order = (table.__apsOrig || []).slice();
    if (s) {
      order.sort(function (a, b) {
        return cmpVals(cellText(a, s.idx), cellText(b, s.idx));
      });
      if (s.dir === "desc") order.reverse();
    }
    order.forEach(function (tr) {
      tbody.appendChild(tr);
    });
  }
  function doSort(table, idx, glyph) {
    var cur = table.__apsSort;
    var dir;
    if (!cur || cur.idx !== idx) dir = "asc";else if (cur.dir === "asc") dir = "desc";else dir = null;
    table.__apsSort = dir ? {
      idx: idx,
      dir: dir
    } : null;
    var glyphs = table.querySelectorAll(".aps-sortglyph");
    for (var i = 0; i < glyphs.length; i++) glyphs[i].classList.remove("asc", "desc");
    if (dir) glyph.classList.add(dir);
    applyOrder(table);
  }
  function openPop(table, idx, btn) {
    closePop();
    var options = distinctForCol(table, idx);
    var allValues = options.map(function (o) {
      return o.value;
    });
    var current = table.__apsFilters[idx];
    var checkedSet = {};
    (current || allValues).forEach(function (v) {
      checkedSet[v] = true;
    });
    function checkedCount() {
      return Object.keys(checkedSet).length;
    }
    var pop = document.createElement("div");
    pop.className = "aps-filter-pop";
    pop.setAttribute("data-aps-fpop", "1");
    var th = btn.closest("th");
    var lbl = th && th.querySelector(".aps-th-label");
    var title = lbl ? lbl.textContent.trim() : "本列";
    var search = document.createElement("input");
    search.type = "text";
    search.placeholder = "搜索 " + title + "…";
    var list = document.createElement("div");
    list.className = "aps-fp-list";
    var foot = document.createElement("div");
    foot.className = "aps-fp-foot";
    var count = document.createElement("span");
    count.className = "aps-fp-count";
    var clear = document.createElement("button");
    clear.type = "button";
    clear.className = "aps-fp-clear";
    clear.textContent = "清除";
    foot.appendChild(count);
    foot.appendChild(clear);
    pop.appendChild(search);
    pop.appendChild(list);
    pop.appendChild(foot);
    document.body.appendChild(pop);
    var r = btn.getBoundingClientRect();
    var w = 240;
    var left = r.left;
    if (left + w > window.innerWidth - 8) left = window.innerWidth - 8 - w;
    pop.style.left = Math.max(8, left) + "px";
    pop.style.top = r.bottom + 6 + "px";
    function labelOf(v) {
      return v === "" ? "(空白)" : v;
    }
    function commit() {
      if (checkedCount() >= allValues.length) {
        delete table.__apsFilters[idx];
        btn.classList.remove("on");
      } else {
        table.__apsFilters[idx] = Object.keys(checkedSet);
        btn.classList.add("on");
      }
      applyFilters(table);
      count.textContent = visibleCount(table) + " 行匹配";
    }
    function renderList() {
      var ql = search.value.trim().toLowerCase();
      var shown = ql ? options.filter(function (o) {
        return labelOf(o.value).toLowerCase().indexOf(ql) !== -1;
      }) : options;
      var scroll = list.scrollTop;
      list.innerHTML = "";
      var shownChecked = shown.filter(function (o) {
        return checkedSet[o.value];
      }).length;
      var allOn = shown.length > 0 && shownChecked === shown.length;
      var someOn = shownChecked > 0 && shownChecked < shown.length;
      var allLab = document.createElement("label");
      allLab.className = "aps-fp-opt aps-fp-all";
      var allCk = document.createElement("input");
      allCk.type = "checkbox";
      allCk.checked = allOn;
      allCk.indeterminate = someOn;
      var allTxt = document.createElement("span");
      allTxt.className = "aps-fp-opt-label";
      allTxt.textContent = "(全选)";
      var allCnt = document.createElement("span");
      allCnt.className = "aps-fp-opt-count";
      allCnt.textContent = options.length;
      allLab.appendChild(allCk);
      allLab.appendChild(allTxt);
      allLab.appendChild(allCnt);
      allCk.addEventListener("change", function () {
        shown.forEach(function (o) {
          if (allOn) delete checkedSet[o.value];else checkedSet[o.value] = true;
        });
        commit();
        renderList();
      });
      list.appendChild(allLab);
      if (!shown.length) {
        var empty = document.createElement("div");
        empty.className = "aps-fp-empty";
        empty.textContent = "无匹配项";
        list.appendChild(empty);
      }
      shown.forEach(function (o) {
        var lab = document.createElement("label");
        lab.className = "aps-fp-opt";
        var ck = document.createElement("input");
        ck.type = "checkbox";
        ck.checked = !!checkedSet[o.value];
        ck.addEventListener("change", function () {
          if (ck.checked) checkedSet[o.value] = true;else delete checkedSet[o.value];
          commit();
          renderList();
        });
        var t = document.createElement("span");
        t.className = "aps-fp-opt-label";
        t.textContent = labelOf(o.value);
        t.title = labelOf(o.value);
        var c = document.createElement("span");
        c.className = "aps-fp-opt-count";
        c.textContent = o.count;
        lab.appendChild(ck);
        lab.appendChild(t);
        lab.appendChild(c);
        list.appendChild(lab);
      });
      list.scrollTop = scroll;
    }
    search.addEventListener("input", renderList);
    clear.addEventListener("click", function () {
      checkedSet = {};
      allValues.forEach(function (v) {
        checkedSet[v] = true;
      });
      commit();
      closePop();
    });
    renderList();
    count.textContent = visibleCount(table) + " 行匹配";
    CURRENT_POP = pop;
    setTimeout(function () {
      search.focus();
    }, 0);
  }
  function startResize(e, th, handle) {
    e.preventDefault();
    e.stopPropagation();
    var startX = e.clientX;
    var startW = th.getBoundingClientRect().width;
    handle.classList.add("dragging");
    function move(ev) {
      var w = Math.max(56, Math.round(startW + ev.clientX - startX));
      th.style.width = w + "px";
    }
    function up() {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
      handle.classList.remove("dragging");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }
  function enhanceTable(table) {
    if (table.__apsTx) return;
    table.__apsTx = true;
    var thead = table.tHead;
    var tbody = table.tBodies[0];
    if (!thead || !thead.rows[0] || !tbody) return;
    var ths = Array.prototype.slice.call(thead.rows[0].cells);
    var bodyRows = Array.prototype.slice.call(tbody.rows);
    var isDataRow = function (tr) {
      return tr.cells.length === ths.length && !tr.querySelector("td[colspan]");
    };
    table.__apsOrig = bodyRows.filter(isDataRow);
    table.__apsFilters = {};
    table.__apsSort = null;
    ths.forEach(function (th, idx) {
      if (th.classList.contains("cbx")) return;
      var colCells = table.__apsOrig.map(function (tr) {
        return tr.cells[idx];
      });
      var isAction = colCells.some(function (td) {
        return td && (td.classList.contains("actcol") || td.querySelector(".rowact, button"));
      });
      th.classList.add("aps-th");
      var inner = document.createElement("span");
      inner.className = "aps-th-inner";
      var label = document.createElement("span");
      label.className = "aps-th-label";
      while (th.firstChild) label.appendChild(th.firstChild);
      inner.appendChild(label);
      if (th.classList.contains("r")) inner.style.justifyContent = "flex-end";
      th.appendChild(inner);
      if (!isAction) {
        inner.classList.add("aps-th-sortable");
        var glyph = document.createElement("span");
        glyph.className = "aps-sortglyph";
        inner.appendChild(glyph);
        var fbtn = document.createElement("button");
        fbtn.type = "button";
        fbtn.className = "aps-filter-btn";
        fbtn.setAttribute("data-aps-fbtn", "1");
        fbtn.title = "筛选";
        fbtn.innerHTML = FUNNEL_SVG;
        inner.appendChild(fbtn);
        inner.addEventListener("click", function (e) {
          if (e.target.closest("[data-aps-fbtn]")) return;
          doSort(table, idx, glyph);
        });
        fbtn.addEventListener("click", function (e) {
          e.stopPropagation();
          openPop(table, idx, fbtn);
        });
      }
      var rh = document.createElement("span");
      rh.className = "aps-th-resize";
      rh.addEventListener("mousedown", function (e) {
        startResize(e, th, rh);
      });
      th.appendChild(rh);
    });
  }
  function scan() {
    var tables = document.querySelectorAll(".plana table.tbl");
    for (var i = 0; i < tables.length; i++) {
      var t = tables[i];
      if (t.hasAttribute("data-aps-rtable")) continue;
      try {
        enhanceTable(t);
      } catch (err) {
        /* never let one table break the page */
        // eslint-disable-next-line no-console
        console.warn("table-enhance: skip", err);
      }
    }
  }
  var scheduled = false;
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    setTimeout(function () {
      scheduled = false;
      injectCSS();
      scan();
    }, 30);
  }
  function init() {
    injectCSS();
    scan();
    var obs = new MutationObserver(function (records) {
      for (var i = 0; i < records.length; i++) {
        if (records[i].addedNodes && records[i].addedNodes.length) {
          schedule();
          return;
        }
      }
    });
    obs.observe(document.body, {
      childList: true,
      subtree: true
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/workbench/table-enhance.js", error: String((e && e.message) || e) }); }

__ds_ns.GanttBar = __ds_scope.GanttBar;

__ds_ns.Kpi = __ds_scope.Kpi;

__ds_ns.RiskCard = __ds_scope.RiskCard;

__ds_ns.Table = __ds_scope.Table;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.HeroCard = __ds_scope.HeroCard;

__ds_ns.Meter = __ds_scope.Meter;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Panel = __ds_scope.Panel;

})();
