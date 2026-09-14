window.APSFieldReports = window.APSFieldReports || {};
;
/* Component-only projection of the pinned DS bundle. */
(() => {
  const __ds_ns = window.APSDesignSystem_edbc5d = window.APSDesignSystem_edbc5d || {};
  const __ds_scope = {};
  __ds_ns.__errors = __ds_ns.__errors || [];
  try {
    (() => {
      function _extends() {
        return _extends = Object.assign ? Object.assign.bind() : function (n) {
          for (var e = 1; e < arguments.length; e++) {
            var t = arguments[e];
            for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
          }
          return n;
        }, _extends.apply(null, arguments);
      }
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
      Object.assign(__ds_scope, {
        GanttBar
      });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/data/GanttBar.jsx",
      error: String(e && e.message || e)
    });
  }
  try {
    (() => {
      function _extends() {
        return _extends = Object.assign ? Object.assign.bind() : function (n) {
          for (var e = 1; e < arguments.length; e++) {
            var t = arguments[e];
            for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
          }
          return n;
        }, _extends.apply(null, arguments);
      }
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
      Object.assign(__ds_scope, {
        Kpi
      });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/data/Kpi.jsx",
      error: String(e && e.message || e)
    });
  }
  try {
    (() => {
      function _extends() {
        return _extends = Object.assign ? Object.assign.bind() : function (n) {
          for (var e = 1; e < arguments.length; e++) {
            var t = arguments[e];
            for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
          }
          return n;
        }, _extends.apply(null, arguments);
      }
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
      Object.assign(__ds_scope, {
        RiskCard
      });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/data/RiskCard.jsx",
      error: String(e && e.message || e)
    });
  }
  try {
    (() => {
      function _extends() {
        return _extends = Object.assign ? Object.assign.bind() : function (n) {
          for (var e = 1; e < arguments.length; e++) {
            var t = arguments[e];
            for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
          }
          return n;
        }, _extends.apply(null, arguments);
      }
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
      Object.assign(__ds_scope, {
        injectTableToolsCSS,
        Table
      });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/data/Table.jsx",
      error: String(e && e.message || e)
    });
  }
  try {
    (() => {
      function _extends() {
        return _extends = Object.assign ? Object.assign.bind() : function (n) {
          for (var e = 1; e < arguments.length; e++) {
            var t = arguments[e];
            for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
          }
          return n;
        }, _extends.apply(null, arguments);
      }
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
      Object.assign(__ds_scope, {
        Badge
      });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/feedback/Badge.jsx",
      error: String(e && e.message || e)
    });
  }
  try {
    (() => {
      function _extends() {
        return _extends = Object.assign ? Object.assign.bind() : function (n) {
          for (var e = 1; e < arguments.length; e++) {
            var t = arguments[e];
            for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
          }
          return n;
        }, _extends.apply(null, arguments);
      }
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
      Object.assign(__ds_scope, {
        HeroCard
      });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/feedback/HeroCard.jsx",
      error: String(e && e.message || e)
    });
  }
  try {
    (() => {
      function _extends() {
        return _extends = Object.assign ? Object.assign.bind() : function (n) {
          for (var e = 1; e < arguments.length; e++) {
            var t = arguments[e];
            for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
          }
          return n;
        }, _extends.apply(null, arguments);
      }
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
      Object.assign(__ds_scope, {
        Meter
      });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/feedback/Meter.jsx",
      error: String(e && e.message || e)
    });
  }
  try {
    (() => {
      function _extends() {
        return _extends = Object.assign ? Object.assign.bind() : function (n) {
          for (var e = 1; e < arguments.length; e++) {
            var t = arguments[e];
            for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
          }
          return n;
        }, _extends.apply(null, arguments);
      }
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
      Object.assign(__ds_scope, {
        Button
      });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/forms/Button.jsx",
      error: String(e && e.message || e)
    });
  }
  try {
    (() => {
      function _extends() {
        return _extends = Object.assign ? Object.assign.bind() : function (n) {
          for (var e = 1; e < arguments.length; e++) {
            var t = arguments[e];
            for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
          }
          return n;
        }, _extends.apply(null, arguments);
      }
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
      Object.assign(__ds_scope, {
        Panel
      });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/layout/Panel.jsx",
      error: String(e && e.message || e)
    });
  }
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
;
// Generated local Lucide subset. See lucide-LICENSE.
window.APSFieldReports.iconNodes = {
  "calendar-days": [["path", {
    "d": "M8 2v4"
  }], ["path", {
    "d": "M16 2v4"
  }], ["rect", {
    "width": "18",
    "height": "18",
    "x": "3",
    "y": "4",
    "rx": "2"
  }], ["path", {
    "d": "M3 10h18"
  }], ["path", {
    "d": "M8 14h.01"
  }], ["path", {
    "d": "M12 14h.01"
  }], ["path", {
    "d": "M16 14h.01"
  }], ["path", {
    "d": "M8 18h.01"
  }], ["path", {
    "d": "M12 18h.01"
  }], ["path", {
    "d": "M16 18h.01"
  }]],
  "chevron-left": [["path", {
    "d": "m15 18-6-6 6-6"
  }]],
  "chevron-right": [["path", {
    "d": "m9 18 6-6-6-6"
  }]],
  "chevron-down": [["path", {
    "d": "m6 9 6 6 6-6"
  }]],
  "clock-3": [["circle", {
    "cx": "12",
    "cy": "12",
    "r": "10"
  }], ["path", {
    "d": "M12 6v6h4"
  }]],
  "search": [["path", {
    "d": "m21 21-4.34-4.34"
  }], ["circle", {
    "cx": "11",
    "cy": "11",
    "r": "8"
  }]],
  "upload": [["path", {
    "d": "M12 3v12"
  }], ["path", {
    "d": "m17 8-5-5-5 5"
  }], ["path", {
    "d": "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
  }]],
  "download": [["path", {
    "d": "M12 15V3"
  }], ["path", {
    "d": "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
  }], ["path", {
    "d": "m7 10 5 5 5-5"
  }]],
  "plus": [["path", {
    "d": "M5 12h14"
  }], ["path", {
    "d": "M12 5v14"
  }]],
  "square-pen": [["path", {
    "d": "M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"
  }], ["path", {
    "d": "M18.375 2.625a1 1 0 0 1 3 3l-9.013 9.014a2 2 0 0 1-.853.505l-2.873.84a.5.5 0 0 1-.62-.62l.84-2.873a2 2 0 0 1 .506-.852z"
  }]],
  "check": [["path", {
    "d": "M20 6 9 17l-5-5"
  }]],
  "check-check": [["path", {
    "d": "M18 6 7 17l-5-5"
  }], ["path", {
    "d": "m22 10-7.5 7.5L13 16"
  }]],
  "x": [["path", {
    "d": "M18 6 6 18"
  }], ["path", {
    "d": "m6 6 12 12"
  }]],
  "folder-open": [["path", {
    "d": "m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"
  }]],
  "circle-alert": [["circle", {
    "cx": "12",
    "cy": "12",
    "r": "10"
  }], ["line", {
    "x1": "12",
    "x2": "12",
    "y1": "8",
    "y2": "12"
  }], ["line", {
    "x1": "12",
    "x2": "12.01",
    "y1": "16",
    "y2": "16"
  }]],
  "circle-check": [["circle", {
    "cx": "12",
    "cy": "12",
    "r": "10"
  }], ["path", {
    "d": "m9 12 2 2 4-4"
  }]],
  "chart-gantt": [["path", {
    "d": "M10 6h8"
  }], ["path", {
    "d": "M12 16h6"
  }], ["path", {
    "d": "M3 3v16a2 2 0 0 0 2 2h16"
  }], ["path", {
    "d": "M8 11h7"
  }]],
  "history": [["path", {
    "d": "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"
  }], ["path", {
    "d": "M3 3v5h5"
  }], ["path", {
    "d": "M12 7v5l4 2"
  }]]
};
Object.assign(window.APSFieldReports.iconNodes, {
  "file-input": [["path", {
    "d": "M4 11V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.706.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-1"
  }], ["path", {
    "d": "M14 2v5a1 1 0 0 0 1 1h5"
  }], ["path", {
    "d": "M2 15h10"
  }], ["path", {
    "d": "m9 18 3-3-3-3"
  }]],
  "file-output": [["path", {
    "d": "M4.226 20.925A2 2 0 0 0 6 22h12a2 2 0 0 0 2-2V8a2.4 2.4 0 0 0-.706-1.706l-3.588-3.588A2.4 2.4 0 0 0 14 2H6a2 2 0 0 0-2 2v3.127"
  }], ["path", {
    "d": "M14 2v5a1 1 0 0 0 1 1h5"
  }], ["path", {
    "d": "m5 11-3 3"
  }], ["path", {
    "d": "m5 17-3-3h10"
  }]],
  "file-down": [["path", {
    "d": "M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"
  }], ["path", {
    "d": "M14 2v5a1 1 0 0 0 1 1h5"
  }], ["path", {
    "d": "M12 18v-6"
  }], ["path", {
    "d": "m9 15 3 3 3-3"
  }]]
});
// Lucide 1.8.0: dist/esm/icons/{unfold-vertical,fold-vertical,minus}.js; see lucide-LICENSE.
Object.assign(window.APSFieldReports.iconNodes, {
  "unfold-vertical": [["path", {
    d: "M12 22v-6"
  }], ["path", {
    d: "M12 8V2"
  }], ["path", {
    d: "M4 12H2"
  }], ["path", {
    d: "M10 12H8"
  }], ["path", {
    d: "M16 12h-2"
  }], ["path", {
    d: "M22 12h-2"
  }], ["path", {
    d: "m15 19-3 3-3-3"
  }], ["path", {
    d: "m15 5-3-3-3 3"
  }]],
  "fold-vertical": [["path", {
    d: "M12 22v-6"
  }], ["path", {
    d: "M12 8V2"
  }], ["path", {
    d: "M4 12H2"
  }], ["path", {
    d: "M10 12H8"
  }], ["path", {
    d: "M16 12h-2"
  }], ["path", {
    d: "M22 12h-2"
  }], ["path", {
    d: "m15 19-3-3-3 3"
  }], ["path", {
    d: "m15 5-3 3-3-3"
  }]],
  "minus": [["path", {
    d: "M5 12h14"
  }]]
});
;
(function () {
  'use strict';

  const h = React.createElement;
  const transferIcons = {
    import: 'file-input',
    export: 'file-output',
    template: 'file-down'
  };
  const readableColors = {
    'var(--ui-primary)': 'var(--ui-info-text)',
    'var(--ui-danger)': 'var(--ui-danger-text)',
    'var(--ui-warning)': 'var(--ui-warning-text)',
    'var(--ui-success)': 'var(--ui-success-text)',
    'var(--ui-muted)': 'var(--ui-info-muted)'
  };
  function iconName(kind) {
    if (!transferIcons[kind]) throw new Error('Unknown workbench transfer kind: ' + kind);
    return transferIcons[kind];
  }
  function TransferIcon({
    kind
  }) {
    const name = iconName(kind),
      nodes = window.APSFieldReports.iconNodes[name];
    return h('svg', {
      className: 'lucide wb-transfer-icon',
      'data-wb-icon': name,
      viewBox: '0 0 24 24',
      width: 16,
      height: 16,
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: 2,
      strokeLinecap: 'round',
      strokeLinejoin: 'round',
      'aria-hidden': true
    }, nodes.map(([tag, attributes], index) => h(tag, {
      ...attributes,
      key: index
    })));
  }
  function iconMarkup(kind) {
    const host = document.createElement('span'),
      placeholder = document.createElement('i');
    placeholder.dataset.lucide = iconName(kind);
    host.appendChild(placeholder);
    window.APSFieldReports.paintIcons(host);
    host.firstElementChild.classList.add('wb-transfer-icon');
    host.firstElementChild.dataset.wbIcon = iconName(kind);
    return host.innerHTML;
  }
  function TransferButton({
    kind,
    variant = 'secondary',
    className = '',
    children,
    type = 'button',
    ...props
  }) {
    return h('button', {
      ...props,
      type,
      className: 'wb-action wb-transfer' + (variant === 'primary' ? ' wb-primary' : '') + (className ? ' ' + className : ''),
      'data-wb-transfer': kind
    }, h(TransferIcon, {
      kind
    }), h('span', {
      className: 'wb-action-label'
    }, children));
  }
  function ControlButton({
    className = '',
    ...props
  }) {
    return h(window.APSDesignSystem_edbc5d.Button, {
      ...props,
      className: 'wb-control' + (className ? ' ' + className : '')
    });
  }
  function DataMeter({
    style = {},
    ...props
  }) {
    return h(window.APSDesignSystem_edbc5d.Meter, {
      ...props,
      style: {
        ...style,
        borderRadius: 'var(--wb-radius-control)'
      }
    });
  }
  function MetricStrip({
    children,
    columns,
    className = '',
    style = {},
    ...props
  }) {
    return h('div', {
      ...props,
      className: 'wb-metrics' + (className ? ' ' + className : ''),
      style: {
        '--wb-columns': columns || React.Children.count(children) || 1,
        ...style
      }
    }, children);
  }
  function Metric({
    label,
    value,
    unit,
    helper,
    badge,
    tone = 'neutral',
    valueColor,
    className = '',
    valueClassName = '',
    style = {},
    ...props
  }) {
    const color = valueColor ? {
      '--wb-metric-color': readableColors[valueColor] || valueColor
    } : {};
    return h('div', {
      ...props,
      className: 'wb-metric' + (className ? ' ' + className : ''),
      'data-tone': tone,
      style: {
        ...color,
        ...style
      }
    }, h('div', {
      className: 'wb-metric-heading'
    }, h('span', {
      className: 'wb-metric-label'
    }, label), badge || null), h('div', {
      className: 'wb-metric-line'
    }, h('span', {
      className: 'wb-metric-value' + (valueClassName ? ' ' + valueClassName : '')
    }, value), unit ? h('span', {
      className: 'wb-metric-unit'
    }, unit) : null), helper ? h('div', {
      className: 'wb-metric-helper'
    }, helper) : null);
  }
  function DataTable({
    className = '',
    ...props
  }) {
    return h('div', {
      className: 'wb-table-shell'
    }, h(window.APSDesignSystem_edbc5d.Table, {
      ...props,
      className: 'wb-table' + (className ? ' ' + className : '')
    }));
  }
  window.APSWorkbenchUI = {
    TransferButton,
    TransferIcon,
    iconMarkup,
    ControlButton,
    DataMeter,
    MetricStrip,
    Metric,
    DataTable
  };
})();
;
(function (root) {
  'use strict';

  const SAMPLE_DATE = '2026-09-07';
  const STATES = Object.freeze({
    available: ['可用', 'success'],
    unavailable: ['不可用', 'danger'],
    unknown: ['未知', 'neutral'],
    disconnected: ['未连接', 'neutral'],
    failed: ['失败', 'danger'],
    blocked: ['受阻', 'warning'],
    pending: ['待执行', 'notice'],
    skipped: ['已跳过', 'warning'],
    verified: ['校验通过', 'success'],
    unverified: ['未校验', 'warning'],
    recorded: ['已记录', 'neutral']
  });
  const TYPES = Object.freeze({
    manual: '手动备份',
    auto: '自动备份',
    restore: '数据库恢复',
    before_restore: '恢复前备份',
    cleanup: '备份清理',
    runtime: '运行日志',
    operation: '操作日志'
  });
  const LEVELS = Object.freeze({
    INFO: '信息',
    WARNING: '警告',
    ERROR: '错误',
    DEBUG: '调试',
    CRITICAL: '严重'
  });
  const SOURCES = Object.freeze({
    'aps.log': '主日志（aps.log）',
    'aps_error.log': '错误日志（aps_error.log）',
    'launcher.log': '启动日志（launcher.log）',
    OperationLogs: '操作记录'
  });
  const CHECKS = Object.freeze({
    runtime: '页面运行依赖',
    localScripts: '本地脚本文件',
    ui: '工作台组件',
    icons: '本地图标',
    styles: '系统管理样式',
    model: '管理资源模型',
    download: '本地文件导出',
    theme: '主题控制'
  });
  // Boundaries mirror SystemConfigService; these are sample values, not a production snapshot.
  const CONFIG_FIELDS = Object.freeze([{
    key: 'auto_backup_enabled',
    label: '自动备份',
    group: 'backup',
    kind: 'switch'
  }, {
    key: 'auto_backup_interval_minutes',
    label: '备份检查间隔',
    group: 'backup',
    unit: '分钟',
    min: 1,
    max: 1440
  }, {
    key: 'auto_backup_cleanup_enabled',
    label: '清理过期备份',
    group: 'backup',
    kind: 'switch'
  }, {
    key: 'auto_backup_keep_days',
    label: '备份保留时间',
    group: 'backup',
    unit: '天',
    min: 1,
    max: 365
  }, {
    key: 'auto_backup_cleanup_interval_minutes',
    label: '备份清理检查间隔',
    group: 'backup',
    unit: '分钟',
    min: 1,
    max: 1440
  }, {
    key: 'auto_log_cleanup_enabled',
    label: '清理操作日志',
    group: 'logs',
    kind: 'switch'
  }, {
    key: 'auto_log_cleanup_keep_days',
    label: '操作日志保留时间',
    group: 'logs',
    unit: '天',
    min: 1,
    max: 365
  }, {
    key: 'auto_log_cleanup_interval_minutes',
    label: '日志清理检查间隔',
    group: 'logs',
    unit: '分钟',
    min: 1,
    max: 1440
  }].map(Object.freeze));
  const SAMPLE_CONFIG = Object.freeze({
    auto_backup_enabled: 'yes',
    auto_backup_interval_minutes: '60',
    auto_backup_cleanup_enabled: 'yes',
    auto_backup_keep_days: '30',
    auto_backup_cleanup_interval_minutes: '1440',
    auto_log_cleanup_enabled: 'no',
    auto_log_cleanup_keep_days: '30',
    auto_log_cleanup_interval_minutes: '60'
  });
  const SAMPLE_NOTE = '这里显示的是样例数据，不是本机真实日志。';
  const scenarios = [['auto', 'failed', '自动备份写入失败，本次未生成备份', '磁盘空间不足，临时副本没有成为正式备份。\n样例备份文件夹：C:\\APS-SAMPLE\\backups\\2026\\09\\设备产能数据归档\\aps_20260907_auto.db\n下一步：清理磁盘空间后重新备份。\n' + SAMPLE_NOTE], ['cleanup', 'skipped', '自动备份失败，本轮清理已跳过', '这一轮自动备份失败，所以清理没有执行，旧备份没有被删除。\n' + SAMPLE_NOTE], ['restore', 'failed', '恢复后结构检查没通过，已还原', '样例恢复出来的副本没通过数据表检查，已经回到恢复前的副本。\n这不是恢复成功的记录。\n' + SAMPLE_NOTE], ['restore', 'blocked', '数据库正在维护，恢复未执行', '数据库维护还没结束，本次操作没有改动数据库。\n' + SAMPLE_NOTE], ['auto', 'pending', '到期检查待触发', '打开页面时系统才会检查一次自动维护，没有后台定时任务。\n这一行是待执行的样例，不是排队中的任务。\n' + SAMPLE_NOTE], ['manual', 'verified', '手动备份完成完整性检查', '样例副本的完整性检查已通过。\n检查通过不等于已经演练过恢复。\n' + SAMPLE_NOTE], ['before_restore', 'verified', '恢复前保护副本已生成', '正式恢复前会先存一份恢复前副本。这条样例没有实际文件。\n' + SAMPLE_NOTE], ['manual', 'unverified', '历史副本只有文件基本信息', '还没有完整性检查证据，文件存在不等于副本可用。\n' + SAMPLE_NOTE], ['restore', 'failed', '结构检查和自动还原都失败', '请不要再操作数据库，联系维护人员并查看正式日志。\n' + SAMPLE_NOTE], ['cleanup', 'recorded', '过期副本按保底规则保留', '按保留天数清理时仍留下最新副本，这条没有执行删除。\n' + SAMPLE_NOTE]];
  function sampleTime(index) {
    return new Date(Date.UTC(2026, 8, 7, 18, 0) - index * 3 * 3600000).toISOString().slice(0, 19).replace('T', ' ');
  }
  function buildSamples() {
    const backups = Array.from({
      length: 24
    }, (_, i) => {
      const [type, status, summary, body] = scenarios[i % scenarios.length];
      const hasFile = ['verified', 'unverified'].includes(status);
      return Object.freeze({
        id: 'sample-backup-' + (i + 1),
        source: 'sample',
        time: sampleTime(i),
        type,
        status,
        summary,
        body,
        filename: hasFile ? 'aps_sample_' + String(i + 1).padStart(3, '0') + '_' + type + '.db' : null,
        sizeBytes: hasFile ? (82 + i) * 1024 * 1024 : null
      });
    });
    const logs = Array.from({
      length: 64
    }, (_, i) => {
      const [action, status, summary, body] = scenarios[i % scenarios.length];
      const type = i % 3 === 0 ? 'operation' : 'runtime';
      const level = status === 'failed' ? 'ERROR' : ['blocked', 'skipped', 'unverified'].includes(status) ? 'WARNING' : 'INFO';
      return Object.freeze({
        id: 'sample-log-' + (i + 1),
        source: 'sample',
        time: sampleTime(i),
        type,
        status,
        level,
        file: type === 'operation' ? 'OperationLogs' : level === 'ERROR' ? 'aps_error.log' : i % 4 === 0 ? 'launcher.log' : 'aps.log',
        action,
        summary,
        body: '[管理样例] ' + body + (i === 8 ? '\n' + '恢复后的检查项没通过，这段样例说明需要完整显示。'.repeat(150) : '')
      });
    });
    return Object.freeze({
      source: 'sample',
      backups: Object.freeze(backups),
      logs: Object.freeze(logs)
    });
  }
  const SAMPLES = buildSamples();
  const CURRENT = Object.freeze({
    source: 'current',
    backups: null,
    logs: null
  });
  function dataset(source) {
    if (source === 'current') return CURRENT;
    if (source === 'sample') return SAMPLES;
    throw new Error('Unknown system workbench source');
  }
  function validateConfig(draft) {
    const errors = {},
      value = {};
    CONFIG_FIELDS.forEach(field => {
      const raw = String(draft[field.key] == null ? '' : draft[field.key]).trim();
      if (field.kind === 'switch') {
        if (!['yes', 'no'].includes(raw)) errors[field.key] = '请选择启用或关闭';else value[field.key] = raw;
      } else if (!/^\d+$/.test(raw) || !Number.isSafeInteger(Number(raw))) errors[field.key] = '请输入整数';else if (Number(raw) < field.min || Number(raw) > field.max) errors[field.key] = '允许 ' + field.min + '–' + field.max + ' ' + field.unit;else value[field.key] = Number(raw);
    });
    return {
      valid: !Object.keys(errors).length,
      errors,
      value
    };
  }
  function dateError(filters) {
    for (const key of ['start', 'end']) {
      const date = filters[key];
      if (!date) continue;
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return '请按 2026-09-13 这样填日期';
      const stamp = new Date(date + 'T00:00:00Z');
      if (!Number.isFinite(stamp.getTime()) || stamp.toISOString().slice(0, 10) !== date) return '日期无效';
    }
    return filters.start && filters.end && filters.start > filters.end ? '开始日期不能晚于结束日期' : '';
  }
  function filterRows(rows, filters = {}) {
    if (rows === null) return {
      rows: null,
      error: ''
    };
    const error = dateError(filters);
    if (error) return {
      rows: [],
      error
    };
    const query = String(filters.query || '').trim().toLowerCase();
    const filtered = rows.filter(row => {
      if (['status', 'type', 'level', 'file'].some(key => filters[key] && row[key] !== filters[key])) return false;
      const day = row.time.slice(0, 10);
      if (filters.start && day < filters.start || filters.end && day > filters.end) return false;
      return !query || [row.time, row.summary, row.body, row.filename, row.file, row.action, TYPES[row.type]].join(' ').toLowerCase().includes(query);
    }).sort((a, b) => b.time.localeCompare(a.time) || a.id.localeCompare(b.id));
    return {
      rows: filtered,
      error: ''
    };
  }
  function paginate(rows, page, pageSize) {
    const size = [10, 25, 50].includes(Number(pageSize)) ? Number(pageSize) : 10;
    if (rows === null) return {
      rows: null,
      total: null,
      pages: null,
      page: 1,
      start: null,
      end: null,
      pageSize: size
    };
    const pages = Math.max(1, Math.ceil(rows.length / size));
    const safe = Number.isFinite(Number(page)) ? Math.trunc(Number(page)) : 1;
    const current = Math.max(1, Math.min(pages, safe));
    return {
      rows: rows.slice((current - 1) * size, current * size),
      total: rows.length,
      pages,
      page: current,
      start: rows.length ? (current - 1) * size + 1 : 0,
      end: Math.min(current * size, rows.length),
      pageSize: size
    };
  }
  function canDownload(w) {
    return typeof w.Blob === 'function' && !!w.URL && typeof w.URL.createObjectURL === 'function' && typeof w.URL.revokeObjectURL === 'function' && !!w.document && 'download' in w.document.createElement('a');
  }
  function inspectEnvironment(w, themeProps = {}) {
    const checks = [];
    const check = (id, test, good, bad) => {
      try {
        const ok = !!test();
        checks.push({
          id,
          label: CHECKS[id],
          status: ok ? 'available' : 'unavailable',
          detail: ok ? good : bad
        });
      } catch (_) {
        checks.push({
          id,
          label: CHECKS[id],
          status: 'unavailable',
          detail: bad
        });
      }
    };
    check('runtime', () => w.React && typeof w.React.createElement === 'function' && w.ReactDOM && typeof w.ReactDOM.createRoot === 'function', 'React 与 ReactDOM 已加载；只代表当前页面可渲染。', 'React 或 ReactDOM 未加载。');
    check('localScripts', () => {
      const sources = Array.from(w.document.querySelectorAll('script[src]')).map(script => script.getAttribute('src'));
      return sources.length > 0 && sources.every(src => src && !/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(src));
    }, '页面用到的脚本都在本机；这不等于逐个文件都做过完整性检查。', '页面用到了外部脚本，或者没有可核对的脚本清单。');
    check('ui', () => ['MetricStrip', 'Metric', 'DataTable', 'TransferButton', 'ControlButton'].every(key => w.APSWorkbenchUI && typeof w.APSWorkbenchUI[key] === 'function'), '指标、表格与操作组件已加载。', '工作台公共组件缺失。');
    check('icons', () => ['file-output', 'chevron-left', 'chevron-right', 'x', 'search', 'history'].every(key => w.APSFieldReports && Array.isArray(w.APSFieldReports.iconNodes && w.APSFieldReports.iconNodes[key])), '页面使用的本地 Lucide 图标已加载。', '本地图标资源缺失。');
    check('styles', () => {
      const node = w.document.querySelector('.sm-workbench');
      return node && w.getComputedStyle(node).getPropertyValue('--sm-workbench-ready').trim() === '1';
    }, '系统管理样式标记已生效；未进行像素或布局验收。', '未检测到系统管理样式标记。');
    check('model', () => w.APSSystemWorkbench === API && SAMPLES.logs.every(row => row.source === 'sample' && STATES[row.status]) && CURRENT.logs === null, '当前环境与固定管理样例分开；本机运行数据尚未读取。', '管理资源模型没有加载，或者读到的数据不完整。请刷新重试。');
    check('download', () => canDownload(w), '浏览器支持把文件存到本机；是否保存以浏览器下载结果为准。', '当前浏览器不支持下载文件，请用 Chrome 打开。');
    check('theme', () => ['light', 'dark'].includes(themeProps.theme) && (typeof themeProps.onToggleTheme === 'function' || typeof themeProps.onSetTheme === 'function'), '深色与浅色切换可用。', '本页暂时不能切换深色浅色。');
    return {
      schemaVersion: 1,
      scope: 'current-prototype',
      checkedAt: new Date().toISOString(),
      protocol: ['file:', 'http:', 'https:'].includes(w.location.protocol) ? w.location.protocol : 'other',
      service: 'disconnected',
      database: 'unknown',
      backupHealth: 'unknown',
      checks
    };
  }
  function diagnosticJSON(report) {
    // Explicit projection: never serialize location, storage, DOM, props, or raw exception messages.
    return JSON.stringify({
      schemaVersion: 1,
      scope: 'current-prototype',
      checkedAt: report.checkedAt,
      protocol: report.protocol,
      service: 'disconnected',
      database: 'unknown',
      backupHealth: 'unknown',
      checks: report.checks.filter(item => CHECKS[item.id]).map(item => ({
        id: item.id,
        status: item.status
      })),
      excluded: ['production-data', 'logs', 'paths', 'storage', 'credentials', 'management-samples']
    }, null, 2);
  }
  function csvCell(value) {
    let text = String(value == null ? '' : value);
    if (/^[\s\uFEFF]*[=+@-]/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  }
  function sampleLogCSV(filters) {
    const result = filterRows(SAMPLES.logs, filters);
    if (result.error) throw new Error(result.error);
    const header = ['数据来源', '时间', '类型', '级别', '状态', '日志来源', '摘要', '详情'];
    const rows = result.rows.map(row => ['管理样例', row.time, TYPES[row.type], LEVELS[row.level] || row.level, STATES[row.status][0], SOURCES[row.file] || row.file, row.summary, row.body]);
    return '\uFEFF' + [header].concat(rows).map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
  }
  function download(w, filename, mime, text) {
    if (!canDownload(w)) throw new Error('当前浏览器不支持本地文件导出');
    let url, anchor;
    try {
      url = w.URL.createObjectURL(new w.Blob([text], {
        type: mime
      }));
      anchor = w.document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      anchor.hidden = true;
      w.document.body.appendChild(anchor);
      anchor.click();
    } finally {
      if (anchor) anchor.remove();
      if (url) w.setTimeout(() => w.URL.revokeObjectURL(url), 1000);
    }
  }
  const API = Object.freeze({
    schemaVersion: 1,
    SAMPLE_DATE,
    STATES,
    TYPES,
    LEVELS,
    SOURCES,
    CONFIG_FIELDS,
    SAMPLE_CONFIG,
    dataset,
    validateConfig,
    filterRows,
    paginate,
    inspectEnvironment,
    diagnosticJSON,
    canDownload,
    sampleLogCSV,
    csvCell,
    download
  });
  if (typeof module === 'object' && module.exports) module.exports = API;else root.APSSystemWorkbench = API;
})(typeof window === 'object' ? window : globalThis);
;
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
    id: "trial",
    label: "方案试调",
    icon: "gantt",
    href: "trial-sample.html"
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
    id: "review",
    label: "执行复盘",
    icon: "chart"
  }, {
    id: "reports",
    label: "报表中心",
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
  dashboard = false,
  field = false,
  operations = false,
  planContext = {},
  children
}) {
  const analysisWorkspace = active === "reports" || active === "review";
  return /*#__PURE__*/React.createElement("div", {
    className: "app-container" + (dashboard ? " dashboard-shell" : "") + (field ? " field-shell" : "") + (operations ? " operations-shell" : "") + (analysisWorkspace ? " analysis-workspace" : "")
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
    fillOpacity: "0.92"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "4",
    y: "14.8",
    width: "8",
    height: "3.2",
    rx: "1.6",
    fillOpacity: "0.78"
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
    href: it.href || "#" + it.id,
    title: it.label,
    onClick: e => {
      if (!it.href) {
        e.preventDefault();
        onNav(it.id);
      }
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
      display: "none"
    }
  }, /*#__PURE__*/React.createElement("strong", null, planContext.label), /*#__PURE__*/React.createElement("i", {
    className: "cap-sep"
  }, "\xB7"), /*#__PURE__*/React.createElement("span", null, planContext.name), /*#__PURE__*/React.createElement("span", {
    className: planContext.status === '已采用' ? 'cap-ok' : 'cap-preview'
  }, planContext.status), /*#__PURE__*/React.createElement("i", {
    className: "cap-sep"
  }, "\xB7"), /*#__PURE__*/React.createElement("span", {
    className: "cap-muted"
  }, "\u6B63\u5F0F v", planContext.version), /*#__PURE__*/React.createElement("i", {
    className: "cap-sep"
  }, "\xB7"), /*#__PURE__*/React.createElement("span", {
    className: "cap-muted"
  }, "\u8303\u56F4 ", planContext.range)), /*#__PURE__*/React.createElement("div", {
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
;
const SM_TOOL_ICONS = {
  'refresh-cw': [['path', {
    d: 'M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8'
  }], ['path', {
    d: 'M21 3v5h-5'
  }], ['path', {
    d: 'M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16'
  }], ['path', {
    d: 'M8 16H3v5'
  }]],
  'rotate-ccw': [['path', {
    d: 'M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8'
  }], ['path', {
    d: 'M3 3v5h5'
  }]]
};
function SMIcon({
  name
}) {
  const nodes = SM_TOOL_ICONS[name] || window.APSFieldReports && window.APSFieldReports.iconNodes && window.APSFieldReports.iconNodes[name];
  if (!nodes) return null;
  return /*#__PURE__*/React.createElement("svg", {
    className: "sm-icon",
    "data-sm-icon": name,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true"
  }, nodes.map(([tag, attrs], index) => React.createElement(tag, {
    ...attrs,
    key: index
  })));
}
function SMStatus({
  state
}) {
  const [label, tone] = window.APSSystemWorkbench.STATES[state] || ['未知', 'neutral'];
  return /*#__PURE__*/React.createElement("span", {
    className: 'sm-status sm-tone-' + tone,
    "data-state": state
  }, label);
}
function SMUnavailable({
  title,
  children
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "sm-empty"
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "folder-open"
  }), /*#__PURE__*/React.createElement("h4", null, title), /*#__PURE__*/React.createElement("p", null, children));
}
function SMDisabled({
  label,
  reason
}) {
  const {
    ControlButton
  } = window.APSWorkbenchUI;
  return /*#__PURE__*/React.createElement("span", {
    className: "sm-disabled",
    title: reason
  }, /*#__PURE__*/React.createElement(ControlButton, {
    className: "sm-button",
    size: "sm",
    disabled: true,
    "aria-label": label + '：' + reason
  }, label));
}
function SMExport({
  disabled,
  onClick,
  children
}) {
  const {
    TransferButton,
    ControlButton
  } = window.APSWorkbenchUI;
  const ready = window.APSFieldReports && window.APSFieldReports.iconNodes && window.APSFieldReports.iconNodes['file-output'];
  return ready ? /*#__PURE__*/React.createElement(TransferButton, {
    className: "sm-button",
    kind: "export",
    disabled: disabled,
    onClick: onClick
  }, children) : /*#__PURE__*/React.createElement(ControlButton, {
    className: "sm-button",
    disabled: true,
    title: "\u7F3A\u5C11\u5BFC\u51FA\u56FE\u6807\uFF0C\u6682\u65F6\u4E0D\u80FD\u5BFC\u51FA"
  }, children);
}
function SMOverview({
  report,
  source,
  onTab
}) {
  const {
    DataTable
  } = window.APSWorkbenchUI;
  const items = [{
    tab: 'backups',
    icon: 'folder-open',
    title: '备份与恢复',
    action: '查看备份与恢复',
    status: source === 'sample' ? '自动备份失败，清理已跳过' : '备份状态未知',
    description: source === 'sample' ? '写入失败未生成副本；旧备份未清理。' : '备份清单、文件大小与最近执行结果尚未读取。'
  }, {
    tab: 'logs',
    icon: 'history',
    title: '运行日志',
    action: '查看运行日志',
    status: source === 'sample' ? '恢复检查失败，需要保留故障证据' : '运行日志未读取',
    description: source === 'sample' ? '部分记录已还原成功，另有还原失败的记录待排查。' : '运行文件日志与操作记录分开查询。'
  }, {
    tab: 'config',
    icon: 'square-pen',
    title: '自动维护规则',
    action: '查看自动维护规则',
    description: source === 'sample' ? '样例：备份间隔 60 分钟，保留 30 天；操作日志清理关闭。' : '自动备份与清理开关、检查间隔、保留天数未知。'
  }];
  const columns = [{
    key: 'label',
    title: '检查项'
  }, {
    key: 'status',
    title: '结果',
    render: row => /*#__PURE__*/React.createElement(SMStatus, {
      state: row.status
    })
  }, {
    key: 'detail',
    title: '检查范围'
  }].map(column => ({
    ...column,
    sortable: false,
    filterable: false
  }));
  return /*#__PURE__*/React.createElement("div", {
    className: "sm-overview-layout"
  }, /*#__PURE__*/React.createElement("section", {
    className: "sm-section sm-maintenance"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sm-section-head"
  }, /*#__PURE__*/React.createElement("h3", null, source === 'sample' ? '管理样例 · 待处理事项' : '本机维护事项'), /*#__PURE__*/React.createElement("span", {
    className: "sm-meta"
  }, "\u5907\u4EFD\u3001\u65E5\u5FD7\u4E0E\u7EF4\u62A4\u89C4\u5219")), items.map(item => /*#__PURE__*/React.createElement("button", {
    key: item.tab,
    type: "button",
    className: "sm-work-row",
    "data-sm-destination": item.tab,
    title: item.action,
    "aria-label": item.action,
    "aria-describedby": 'sm-work-summary-' + item.tab,
    onClick: () => onTab(item.tab)
  }, /*#__PURE__*/React.createElement("span", {
    className: "sm-work-icon"
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: item.icon
  })), /*#__PURE__*/React.createElement("span", {
    className: "sm-work-copy"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sm-work-title"
  }, item.title), /*#__PURE__*/React.createElement("span", {
    className: "sm-work-summary",
    id: 'sm-work-summary-' + item.tab
  }, item.status && /*#__PURE__*/React.createElement("strong", {
    className: source === 'sample' ? 'sm-tone-danger' : 'sm-meta'
  }, item.status), /*#__PURE__*/React.createElement("span", {
    className: "sm-work-description"
  }, item.description))), /*#__PURE__*/React.createElement("span", {
    className: "sm-work-arrow",
    "aria-hidden": "true"
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "chevron-right"
  }))))), /*#__PURE__*/React.createElement("details", {
    className: "sm-section sm-environment"
  }, /*#__PURE__*/React.createElement("summary", null, "\u9875\u9762\u73AF\u5883\u81EA\u68C0"), /*#__PURE__*/React.createElement("p", {
    className: "sm-meta"
  }, report ? '检查时间 ' + new Date(report.checkedAt).toLocaleString('zh-CN', {
    hour12: false
  }) : '尚未检查', " \xB7 \u4E0D\u4EE3\u8868\u6570\u636E\u5E93\u6216\u5907\u4EFD\u5065\u5EB7"), /*#__PURE__*/React.createElement(DataTable, {
    className: "sm-table sm-check-table",
    columns: columns,
    rows: report ? report.checks : [],
    rowKey: "id"
  })));
}
function SMFilters({
  kind,
  filters,
  onChange,
  disabled
}) {
  const model = window.APSSystemWorkbench;
  const {
    ControlButton
  } = window.APSWorkbenchUI;
  const select = (key, label, entries) => /*#__PURE__*/React.createElement("label", {
    className: "sm-field",
    key: key
  }, /*#__PURE__*/React.createElement("span", null, label), /*#__PURE__*/React.createElement("select", {
    name: 'sm-' + key,
    value: filters[key],
    disabled: disabled,
    onChange: e => onChange({
      [key]: e.target.value
    })
  }, /*#__PURE__*/React.createElement("option", {
    value: ""
  }, "\u5168\u90E8", label), entries.map(([value, title]) => /*#__PURE__*/React.createElement("option", {
    key: value,
    value: value
  }, title))));
  return /*#__PURE__*/React.createElement("div", {
    className: "sm-filters"
  }, /*#__PURE__*/React.createElement("label", {
    className: "sm-field sm-search"
  }, /*#__PURE__*/React.createElement("span", null, "\u641C\u7D22"), /*#__PURE__*/React.createElement("span", {
    className: "sm-search-input"
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "search"
  }), /*#__PURE__*/React.createElement("input", {
    name: "sm-query",
    type: "search",
    value: filters.query,
    disabled: disabled,
    placeholder: kind === 'logs' ? '摘要、完整详情、文件' : '文件名、故障原因',
    onChange: e => onChange({
      query: e.target.value
    })
  }))), select('type', '类型', (kind === 'logs' ? ['runtime', 'operation'] : ['manual', 'auto', 'before_restore', 'restore', 'cleanup']).map(key => [key, model.TYPES[key]])), select('status', '状态', ['failed', 'blocked', 'pending', 'skipped', 'verified', 'unverified', 'recorded'].map(key => [key, model.STATES[key][0]])), kind === 'logs' && select('level', '级别', ['ERROR', 'WARNING', 'INFO'].map(key => [key, model.LEVELS[key] || key])), kind === 'logs' && select('file', '来源', ['aps_error.log', 'aps.log', 'launcher.log', 'OperationLogs'].map(key => [key, model.SOURCES[key] || key])), /*#__PURE__*/React.createElement("label", {
    className: "sm-field"
  }, /*#__PURE__*/React.createElement("span", null, "\u5F00\u59CB\u65E5\u671F"), /*#__PURE__*/React.createElement("input", {
    type: "date",
    "data-aps-skip": "true",
    name: "sm-start",
    value: filters.start,
    disabled: disabled,
    onChange: e => onChange({
      start: e.target.value
    })
  })), /*#__PURE__*/React.createElement("label", {
    className: "sm-field"
  }, /*#__PURE__*/React.createElement("span", null, "\u7ED3\u675F\u65E5\u671F"), /*#__PURE__*/React.createElement("input", {
    type: "date",
    "data-aps-skip": "true",
    name: "sm-end",
    value: filters.end,
    disabled: disabled,
    onChange: e => onChange({
      end: e.target.value
    })
  })), /*#__PURE__*/React.createElement(ControlButton, {
    className: "sm-button sm-icon-button",
    size: "sm",
    disabled: disabled,
    title: "\u6E05\u9664\u7B5B\u9009",
    "aria-label": "\u6E05\u9664\u7B5B\u9009",
    onClick: () => onChange({
      query: '',
      status: '',
      type: '',
      level: '',
      file: '',
      start: '',
      end: ''
    })
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "x"
  })));
}
function SMPager({
  pager,
  onPage,
  pageSize,
  onPageSize
}) {
  const {
    ControlButton
  } = window.APSWorkbenchUI;
  return /*#__PURE__*/React.createElement("div", {
    className: "sm-pager"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sm-meta"
  }, pager.total === null ? '总数未知 · 未连接' : '第 ' + pager.start + '–' + pager.end + ' 条 / 共 ' + pager.total + ' 条管理样例'), /*#__PURE__*/React.createElement("div", {
    className: "sm-actions"
  }, /*#__PURE__*/React.createElement("label", {
    className: "sm-inline-label"
  }, "\u6BCF\u9875", /*#__PURE__*/React.createElement("select", {
    name: "sm-page-size",
    value: pageSize,
    onChange: e => onPageSize(Number(e.target.value))
  }, [10, 25, 50].map(n => /*#__PURE__*/React.createElement("option", {
    key: n,
    value: n
  }, n, " \u6761")))), /*#__PURE__*/React.createElement(ControlButton, {
    className: "sm-button sm-icon-button",
    size: "sm",
    title: "\u4E0A\u4E00\u9875",
    "aria-label": "\u4E0A\u4E00\u9875",
    disabled: pager.total === null || pager.page <= 1,
    onClick: () => onPage(pager.page - 1)
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "chevron-left"
  })), /*#__PURE__*/React.createElement("span", {
    className: "sm-page-number"
  }, pager.total === null ? '未知' : pager.page + ' / ' + pager.pages), /*#__PURE__*/React.createElement(ControlButton, {
    className: "sm-button sm-icon-button",
    size: "sm",
    title: "\u4E0B\u4E00\u9875",
    "aria-label": "\u4E0B\u4E00\u9875",
    disabled: pager.total === null || pager.page >= pager.pages,
    onClick: () => onPage(pager.page + 1)
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "chevron-right"
  }))));
}
function SMRecordDetail({
  row,
  onClose,
  kind
}) {
  const model = window.APSSystemWorkbench,
    {
      ControlButton
    } = window.APSWorkbenchUI;
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (ref.current) ref.current.focus();
  }, [row.id]);
  return /*#__PURE__*/React.createElement("section", {
    id: "sm-record-detail",
    className: "sm-detail",
    tabIndex: "-1",
    ref: ref,
    "aria-label": "\u7BA1\u7406\u6837\u4F8B\u8BE6\u60C5",
    onKeyDown: event => {
      if (event.key === 'Escape') onClose();
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "sm-section-head"
  }, /*#__PURE__*/React.createElement("h3", null, "\u7BA1\u7406\u6837\u4F8B \xB7 ", kind === 'logs' ? '日志详情' : '备份恢复详情'), /*#__PURE__*/React.createElement(ControlButton, {
    className: "sm-button sm-icon-button",
    size: "sm",
    title: "\u5173\u95ED\u8BE6\u60C5",
    "aria-label": "\u5173\u95ED\u8BE6\u60C5",
    onClick: onClose
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "x"
  }))), /*#__PURE__*/React.createElement("div", {
    className: "sm-detail-meta"
  }, /*#__PURE__*/React.createElement("time", null, row.time), /*#__PURE__*/React.createElement(SMStatus, {
    state: row.status
  }), /*#__PURE__*/React.createElement("span", null, model.SOURCES[row.file] || row.file || row.filename || '未生成文件')), /*#__PURE__*/React.createElement("h4", null, row.summary), /*#__PURE__*/React.createElement("pre", null, row.body), kind === 'backups' && /*#__PURE__*/React.createElement("details", {
    className: "sm-rules"
  }, /*#__PURE__*/React.createElement("summary", null, "\u6062\u590D\u8981\u505A\u7684\u68C0\u67E5"), /*#__PURE__*/React.createElement("p", null, "\u6B63\u5F0F\u6062\u590D\u4F1A\u5148\u5B58\u4E00\u4EFD\u6062\u590D\u524D\u526F\u672C\uFF0C\u518D\u68C0\u67E5\u6062\u590D\u540E\u7684\u6570\u636E\u8868\uFF1B\u6062\u590D\u5931\u8D25\u548C\u8FD8\u539F\u5931\u8D25\u5206\u522B\u7559\u8BB0\u5F55\u3002\u8FD9\u91CC\u663E\u793A\u7684\u662F\u6837\u4F8B\u6570\u636E\uFF0C\u4E0D\u4F1A\u771F\u7684\u6267\u884C\u6062\u590D\u3002")));
}
function SMRecords({
  kind,
  source,
  pageSize,
  onPageSize,
  exportLogs,
  downloadReady
}) {
  const model = window.APSSystemWorkbench,
    {
      DataTable,
      ControlButton
    } = window.APSWorkbenchUI;
  const [filters, setFilters] = React.useState({
    query: '',
    type: '',
    status: '',
    level: '',
    file: '',
    start: '',
    end: ''
  });
  const [page, setPage] = React.useState(1),
    [selected, setSelected] = React.useState(null);
  const opener = React.useRef(null);
  const results = React.useMemo(() => model.filterRows(model.dataset(source)[kind], filters), [source, kind, filters]);
  const pager = model.paginate(results.rows, page, pageSize),
    connected = source === 'sample';
  const changeFilters = patch => {
    setFilters(previous => ({
      ...previous,
      ...patch
    }));
    setPage(1);
    setSelected(null);
  };
  const closeDetail = () => {
    setSelected(null);
    if (opener.current && opener.current.isConnected) opener.current.focus();
  };
  const columns = [{
    key: 'time',
    title: '时间',
    render: row => /*#__PURE__*/React.createElement("time", {
      className: "sm-time"
    }, row.time)
  }, {
    key: 'type',
    title: '类型',
    render: row => model.TYPES[row.type]
  }, {
    key: 'status',
    title: '状态',
    render: row => /*#__PURE__*/React.createElement(SMStatus, {
      state: row.status
    })
  }, ...(kind === 'logs' ? [{
    key: 'level',
    title: '级别',
    render: row => /*#__PURE__*/React.createElement("span", {
      className: 'sm-level sm-level-' + row.level
    }, model.LEVELS[row.level] || row.level)
  }] : []), {
    key: 'summary',
    title: kind === 'logs' ? '摘要 / 来源' : '记录 / 文件',
    render: row => /*#__PURE__*/React.createElement("div", {
      className: "sm-summary"
    }, /*#__PURE__*/React.createElement("strong", null, row.summary), /*#__PURE__*/React.createElement("small", null, kind === 'logs' ? model.SOURCES[row.file] || row.file : row.filename || '未生成文件'))
  }, ...(kind === 'backups' ? [{
    key: 'sizeBytes',
    title: '大小',
    align: 'right',
    render: row => row.sizeBytes === null ? '不适用' : (row.sizeBytes / 1024 / 1024).toFixed(1) + ' MB'
  }] : []), {
    key: 'detail',
    title: '详情',
    render: row => /*#__PURE__*/React.createElement(ControlButton, {
      className: "sm-button sm-icon-button sm-quiet-button",
      size: "sm",
      title: "\u67E5\u770B\u8BE6\u60C5",
      "aria-label": '查看详情 ' + row.id,
      "data-sm-detail": row.id,
      "aria-controls": "sm-record-detail",
      "aria-expanded": !!selected && selected.id === row.id,
      onClick: e => {
        opener.current = e.currentTarget;
        setSelected(row);
      }
    }, /*#__PURE__*/React.createElement(SMIcon, {
      name: "chevron-right"
    }))
  }].map(column => ({
    ...column,
    sortable: false,
    filterable: false
  }));
  return /*#__PURE__*/React.createElement("section", {
    className: "sm-section"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sm-section-head"
  }, /*#__PURE__*/React.createElement("h3", null, kind === 'logs' ? '运行日志与操作记录' : '备份与维护记录'), /*#__PURE__*/React.createElement("span", {
    className: "sm-meta"
  }, connected ? '固定样例截至 ' + model.SAMPLE_DATE + ' 18:00' : '本机记录尚未读取')), /*#__PURE__*/React.createElement("div", {
    className: "sm-toolbar"
  }, /*#__PURE__*/React.createElement(SMFilters, {
    kind: kind,
    filters: filters,
    onChange: changeFilters,
    disabled: !connected
  }), /*#__PURE__*/React.createElement("div", {
    className: "sm-actions sm-record-actions"
  }, kind === 'logs' ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(SMExport, {
    disabled: !connected || !downloadReady || !!results.error || !results.rows.length,
    onClick: () => exportLogs(filters, results.rows.length)
  }, "\u5BFC\u51FA\u6837\u4F8B\u65E5\u5FD7 CSV"), /*#__PURE__*/React.createElement(SMDisabled, {
    label: "\u6B63\u5F0F\u8BCA\u65AD\u5305",
    reason: "\u6B64\u529F\u80FD\u5C1A\u672A\u5F00\u901A\u3002\u5F53\u524D\u53EA\u80FD\u5BFC\u51FA\u4E0A\u9762\u7684\u6837\u4F8B\u65E5\u5FD7 CSV\u3002"
  })) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(SMDisabled, {
    label: "\u65B0\u589E\u5907\u4EFD",
    reason: "\u6B64\u529F\u80FD\u5C1A\u672A\u5F00\u901A\u3002\u5F53\u524D\u53EA\u663E\u793A\u6837\u4F8B\u8BB0\u5F55\u3002"
  }), /*#__PURE__*/React.createElement(SMDisabled, {
    label: "\u6062\u590D\u5907\u4EFD",
    reason: "\u6B64\u529F\u80FD\u5C1A\u672A\u5F00\u901A\u3002\u5F53\u524D\u53EA\u663E\u793A\u6837\u4F8B\u8BB0\u5F55\u3002"
  }), /*#__PURE__*/React.createElement(SMDisabled, {
    label: "\u5220\u9664\u5907\u4EFD",
    reason: "\u6B64\u529F\u80FD\u5C1A\u672A\u5F00\u901A\u3002\u5F53\u524D\u53EA\u663E\u793A\u6837\u4F8B\u8BB0\u5F55\u3002"
  })))), /*#__PURE__*/React.createElement("p", {
    className: "sm-note"
  }, kind === 'logs' ? '运行文件日志只读；操作记录单独归类。' : connected ? '含待执行、受阻情境，不等同于已有备份文件清单。' : '文件清单与完整性校验结果尚未读取。'), results.error && /*#__PURE__*/React.createElement("p", {
    className: "sm-error",
    role: "alert"
  }, results.error), !connected ? /*#__PURE__*/React.createElement(SMUnavailable, {
    title: kind === 'logs' ? '本机日志尚未读取' : '本机备份记录尚未读取'
  }, "\u672C\u539F\u578B\u4E0D\u8BFB\u53D6\u672C\u673A\u8BB0\u5F55\uFF0C\u6240\u4EE5\u603B\u6570\u672A\u77E5\u3002\u73B0\u5728\u65E0\u6CD5\u5224\u65AD\u662F\u6CA1\u6709\u8BB0\u5F55\uFF0C\u8FD8\u662F\u8BFB\u53D6\u5931\u8D25\u3002") : results.rows.length === 0 ? /*#__PURE__*/React.createElement(SMUnavailable, {
    title: results.error ? '筛选条件无效' : '没有符合条件的管理样例'
  }, results.error || '调整日期或清除筛选条件。') : /*#__PURE__*/React.createElement(DataTable, {
    className: 'sm-table sm-record-table sm-' + kind + '-table',
    columns: columns,
    rows: pager.rows,
    rowKey: "id"
  }), /*#__PURE__*/React.createElement(SMPager, {
    pager: pager,
    pageSize: pageSize,
    onPage: next => {
      setPage(next);
      setSelected(null);
    },
    onPageSize: size => {
      onPageSize(size);
      setPage(1);
      setSelected(null);
    }
  }), selected && /*#__PURE__*/React.createElement(SMRecordDetail, {
    row: selected,
    onClose: closeDetail,
    kind: kind
  }));
}
function SMConfiguration({
  source,
  theme,
  onToggleTheme,
  onSetTheme,
  pageSize,
  onPageSize,
  compact,
  onCompact
}) {
  const model = window.APSSystemWorkbench,
    {
      ControlButton
    } = window.APSWorkbenchUI;
  const [draft, setDraft] = React.useState(() => ({
    ...model.SAMPLE_CONFIG
  }));
  const [preview, setPreview] = React.useState(null),
    [validated, setValidated] = React.useState(false);
  const [themeError, setThemeError] = React.useState('');
  const validation = model.validateConfig(draft);
  const themeReady = ['light', 'dark'].includes(theme) && (typeof onSetTheme === 'function' || typeof onToggleTheme === 'function');
  const changeTheme = next => {
    if (next === theme || !themeReady) return;
    setThemeError('');
    try {
      if (typeof onSetTheme === 'function') onSetTheme(next);else onToggleTheme();
    } catch (_) {
      setThemeError('主题没有切换成功，页面其他内容没有改动。请刷新页面后重试。');
    }
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "sm-configuration"
  }, /*#__PURE__*/React.createElement("section", {
    className: "sm-section sm-preferences"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sm-section-head"
  }, /*#__PURE__*/React.createElement("h3", null, "\u5373\u65F6\u9875\u9762\u504F\u597D"), /*#__PURE__*/React.createElement("span", {
    className: "sm-meta"
  }, "\u4E3B\u9898\u6CBF\u7528\u5DE5\u4F5C\u53F0\uFF1B\u5217\u8868\u8BBE\u7F6E\u53EA\u5728\u5F53\u524D\u9875\u9762\u6709\u6548")), /*#__PURE__*/React.createElement("div", {
    className: "sm-session-settings"
  }, /*#__PURE__*/React.createElement("fieldset", {
    className: "sm-choice"
  }, /*#__PURE__*/React.createElement("legend", null, "\u4E3B\u9898"), [['light', '浅色'], ['dark', '深色']].map(([value, label]) => /*#__PURE__*/React.createElement("label", {
    key: value
  }, /*#__PURE__*/React.createElement("input", {
    type: "radio",
    name: "sm-theme",
    value: value,
    checked: theme === value,
    disabled: !themeReady,
    onChange: () => changeTheme(value)
  }), label))), /*#__PURE__*/React.createElement("label", {
    className: "sm-inline-label"
  }, "\u6BCF\u9875\u6761\u6570", /*#__PURE__*/React.createElement("select", {
    name: "sm-config-page-size",
    value: pageSize,
    onChange: e => onPageSize(Number(e.target.value))
  }, [10, 25, 50].map(n => /*#__PURE__*/React.createElement("option", {
    key: n,
    value: n
  }, n, " \u6761")))), /*#__PURE__*/React.createElement("label", {
    className: "sm-inline-label"
  }, /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    name: "sm-compact",
    checked: compact,
    onChange: e => onCompact(e.target.checked)
  }), "\u7D27\u51D1\u884C\u8DDD")), !themeReady && /*#__PURE__*/React.createElement("p", {
    className: "sm-note"
  }, "\u672C\u9875\u6682\u65F6\u4E0D\u80FD\u5207\u6362\u4E3B\u9898\uFF0C\u8BF7\u5230\u5DE5\u4F5C\u53F0\u5207\u6362\u6DF1\u8272\u6216\u6D45\u8272\u3002"), themeError && /*#__PURE__*/React.createElement("p", {
    className: "sm-error",
    role: "alert"
  }, themeError)), /*#__PURE__*/React.createElement("section", {
    className: "sm-section sm-maintenance-config"
  }, /*#__PURE__*/React.createElement("div", {
    className: "sm-section-head"
  }, /*#__PURE__*/React.createElement("h3", null, source === 'sample' ? '样例草稿 · 自动维护参数' : '本机自动维护配置'), /*#__PURE__*/React.createElement(SMDisabled, {
    label: "\u4FDD\u5B58\u6B63\u5F0F\u914D\u7F6E",
    reason: "\u6B64\u529F\u80FD\u5C1A\u672A\u5F00\u901A\u3002\u5F53\u524D\u53EA\u80FD\u68C0\u67E5\u6837\u4F8B\u8349\u7A3F\u3002"
  })), /*#__PURE__*/React.createElement("div", {
    className: "sm-config-main"
  }, source !== 'sample' ? /*#__PURE__*/React.createElement(SMUnavailable, {
    title: "\u672C\u673A\u6B63\u5F0F\u914D\u7F6E\u5C1A\u672A\u8BFB\u53D6"
  }, "\u81EA\u52A8\u5907\u4EFD\u5F00\u5173\u3001\u68C0\u67E5\u95F4\u9694\u3001\u4FDD\u7559\u65F6\u95F4\u53CA\u65E7\u914D\u7F6E\u5F02\u5E38\u5747\u672A\u77E5\u3002") : /*#__PURE__*/React.createElement("form", {
    className: "sm-config-form",
    noValidate: true,
    onSubmit: event => {
      event.preventDefault();
      setValidated(true);
      setPreview(validation.valid ? validation.value : null);
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "sm-config-groups"
  }, [['backup', '备份规则'], ['logs', '操作日志规则']].map(([group, label]) => /*#__PURE__*/React.createElement("fieldset", {
    className: "sm-config-group",
    key: group
  }, /*#__PURE__*/React.createElement("legend", null, label), model.CONFIG_FIELDS.filter(field => field.group === group).map(field => /*#__PURE__*/React.createElement("div", {
    className: "sm-config-row",
    key: field.key
  }, /*#__PURE__*/React.createElement("label", {
    htmlFor: 'sm-' + field.key
  }, field.label), /*#__PURE__*/React.createElement("div", null, field.kind === 'switch' ? /*#__PURE__*/React.createElement("label", {
    className: "sm-draft-checkbox"
  }, /*#__PURE__*/React.createElement("input", {
    id: 'sm-' + field.key,
    name: field.key,
    type: "checkbox",
    checked: draft[field.key] === 'yes',
    onChange: e => {
      setDraft({
        ...draft,
        [field.key]: e.target.checked ? 'yes' : 'no'
      });
      setPreview(null);
    }
  }), /*#__PURE__*/React.createElement("span", null, draft[field.key] === 'yes' ? '启用' : '关闭')) : /*#__PURE__*/React.createElement("div", {
    className: "sm-number"
  }, /*#__PURE__*/React.createElement("input", {
    id: 'sm-' + field.key,
    name: field.key,
    type: "number",
    step: "1",
    min: field.min,
    max: field.max,
    value: draft[field.key],
    "aria-invalid": validated && !!validation.errors[field.key],
    "aria-describedby": 'sm-help-' + field.key,
    onChange: e => {
      setDraft({
        ...draft,
        [field.key]: e.target.value
      });
      setPreview(null);
    }
  }), /*#__PURE__*/React.createElement("span", null, field.unit)), field.kind !== 'switch' && /*#__PURE__*/React.createElement("small", {
    id: 'sm-help-' + field.key,
    className: validated && validation.errors[field.key] ? 'sm-error' : 'sm-meta'
  }, validated && validation.errors[field.key] || field.min + '–' + field.max + ' ' + field.unit))))))), /*#__PURE__*/React.createElement("div", {
    className: "sm-form-footer"
  }, /*#__PURE__*/React.createElement("span", {
    className: "sm-meta"
  }, "\u6837\u4F8B\u8349\u7A3F \xB7 \u672A\u4FDD\u5B58"), /*#__PURE__*/React.createElement("div", {
    className: "sm-actions"
  }, /*#__PURE__*/React.createElement(ControlButton, {
    className: "sm-button",
    size: "sm",
    onClick: () => {
      setDraft({
        ...model.SAMPLE_CONFIG
      });
      setValidated(false);
      setPreview(null);
    }
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "rotate-ccw"
  }), "\u8FD8\u539F\u6837\u4F8B"), /*#__PURE__*/React.createElement(ControlButton, {
    className: "sm-button sm-primary-button",
    variant: "primary",
    size: "sm",
    type: "submit"
  }, /*#__PURE__*/React.createElement(SMIcon, {
    name: "check"
  }), "\u68C0\u67E5\u53C2\u6570"))), validated && !validation.valid && /*#__PURE__*/React.createElement("p", {
    className: "sm-error",
    role: "alert"
  }, "\u6837\u4F8B\u914D\u7F6E\u68C0\u67E5\u672A\u901A\u8FC7\uFF0C\u586B\u5199\u5185\u5BB9\u5DF2\u4FDD\u7559\u3002\u8BF7\u4FEE\u6B63\u6807\u51FA\u7684\u9879\u3002"), preview && /*#__PURE__*/React.createElement("div", {
    className: "sm-preview",
    role: "status"
  }, /*#__PURE__*/React.createElement("h4", {
    className: "sm-tone-success"
  }, "\u6837\u4F8B\u8349\u7A3F\u68C0\u67E5\u901A\u8FC7 \xB7 \u672A\u4FDD\u5B58"), /*#__PURE__*/React.createElement("dl", null, model.CONFIG_FIELDS.map(field => /*#__PURE__*/React.createElement(React.Fragment, {
    key: field.key
  }, /*#__PURE__*/React.createElement("dt", null, field.label), /*#__PURE__*/React.createElement("dd", null, field.kind === 'switch' ? preview[field.key] === 'yes' ? '启用' : '关闭' : preview[field.key] + ' ' + field.unit))))))), /*#__PURE__*/React.createElement("details", {
    className: "sm-rules sm-config-help"
  }, /*#__PURE__*/React.createElement("summary", null, "\u751F\u6548\u8303\u56F4\u4E0E\u81EA\u52A8\u7EF4\u62A4\u89C4\u5219"), /*#__PURE__*/React.createElement("dl", null, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5F53\u524D\u7F16\u8F91"), /*#__PURE__*/React.createElement("dd", null, source === 'sample' ? '独立管理样例' : '本机正式配置未读取')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u89E6\u53D1\u65B9\u5F0F"), /*#__PURE__*/React.createElement("dd", null, "\u6253\u5F00\u9875\u9762\u65F6\u68C0\u67E5\u4E00\u6B21")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u65E5\u5FD7\u6E05\u7406\u8303\u56F4"), /*#__PURE__*/React.createElement("dd", null, "\u64CD\u4F5C\u8BB0\u5F55\uFF0C\u4E0D\u542B\u8FD0\u884C\u6587\u4EF6\u65E5\u5FD7"))), /*#__PURE__*/React.createElement("p", null, "\u6253\u5F00\u9875\u9762\u65F6\u7CFB\u7EDF\u624D\u4F1A\u68C0\u67E5\u4E00\u6B21\u5907\u4EFD\u548C\u6E05\u7406\uFF0C\u6CA1\u6709\u540E\u53F0\u5B9A\u65F6\u4EFB\u52A1\u3002\u95F4\u9694\u53EA\u662F\u68C0\u67E5\u5468\u671F\uFF0C\u4E0D\u4FDD\u8BC1\u5728\u6307\u5B9A\u65F6\u523B\u6267\u884C\uFF1B\u6B63\u5E38\u9000\u51FA\u65F6\u7684\u5907\u4EFD\u4E5F\u53D7\u81EA\u52A8\u5907\u4EFD\u5F00\u5173\u63A7\u5236\u3002"), /*#__PURE__*/React.createElement("p", null, "\u65E5\u5FD7\u6E05\u7406\u53EA\u6E05\u64CD\u4F5C\u8BB0\u5F55\uFF0C\u4E0D\u6E05\u9664\u8FD0\u884C\u6587\u4EF6\u65E5\u5FD7\u3002\u5907\u4EFD\u5931\u8D25\u65F6\u4F1A\u8DF3\u8FC7\u672C\u8F6E\u5907\u4EFD\u6E05\u7406\uFF0C\u4FDD\u5E95\u89C4\u5219\u4E0D\u4F1A\u5220\u6389\u5168\u90E8\u8FD1\u671F\u526F\u672C\u3002"))));
}