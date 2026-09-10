import React from "react";

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

export function injectTableToolsCSS() {
  if (typeof document === "undefined" || document.getElementById(CSS_ID)) return;
  const el = document.createElement("style");
  el.id = CSS_ID;
  el.textContent = TABLE_TOOLS_CSS;
  document.head.appendChild(el);
}

const FUNNEL = (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 5h18l-7 8v5l-4 2v-7z" />
  </svg>
);

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
  return sa.localeCompare(sb, "zh-Hans-CN", { numeric: true, sensitivity: "base" });
}

export function Table({ columns = [], rows = [], rowKey = "id", style = {}, ...rest }) {
  React.useEffect(injectTableToolsCSS, []);

  const [sort, setSort] = React.useState(null); // { key, dir: "asc"|"desc" }
  const [filters, setFilters] = React.useState({}); // { key: string[] } selected values — absent = all shown
  const [widths, setWidths] = React.useState({}); // { key: px }
  const [openFilter, setOpenFilter] = React.useState(null); // key
  const [popPos, setPopPos] = React.useState(null); // {left, top}

  const meta = React.useMemo(
    () =>
      columns.map((c) => {
        const hasData = rows.some((r) => {
          const v = r[c.key];
          return v != null && typeof v !== "object";
        });
        const declaredFacets = c.filterFacets && c.filterFacets.length ? c.filterFacets : null;
        const declaredSortFacets = c.sortFacets && c.sortFacets.length ? c.sortFacets : null;
        const filterable = c.filterable != null ? c.filterable : hasData || !!c.filterValue || !!declaredFacets;
        let facets = null;
        if (filterable) {
          facets = declaredFacets
            ? declaredFacets.map((f) => ({
                fkey: c.key + "::" + f.key,
                label: f.label,
                value: (row) => {
                  const v = f.value ? f.value(row) : row[f.key];
                  return v == null ? "" : String(v);
                },
              }))
            : [{ fkey: c.key, label: typeof c.title === "string" ? c.title : "本列", value: (row) => textOf(c, row) }];
        }
        const sortFacets = declaredSortFacets
          ? declaredSortFacets.map((f) => ({
              skey: c.key + "::" + f.key,
              label: f.label,
              value: (row) => (f.value ? f.value(row) : row[f.key]),
            }))
          : null;
        return {
          ...c,
          _sortable: c.sortable != null ? c.sortable : hasData || !!c.sortValue || !!sortFacets,
          _sortFacets: sortFacets,
          _filterable: !!facets,
          _facets: facets,
        };
      }),
    [columns, rows]
  );

  // facet lookup by its unique key
  const facetByKey = React.useMemo(() => {
    const m = {};
    meta.forEach((c) => c._facets && c._facets.forEach((f) => (m[f.fkey] = f)));
    return m;
  }, [meta]);

  // distinct values per facet (for the Excel-style checkbox filter)
  const distinct = React.useMemo(() => {
    const out = {};
    meta.forEach((c) => {
      if (!c._facets) return;
      c._facets.forEach((f) => {
        const m = new Map();
        rows.forEach((r) => {
          const t = f.value(r);
          m.set(t, (m.get(t) || 0) + 1);
        });
        out[f.fkey] = [...m.entries()]
          .map(([value, count]) => ({ value, count }))
          .sort((a, b) => cmpVals(a.value, b.value));
      });
    });
    return out;
  }, [meta, rows]);

  // ---- derive view (filter then sort) ----
  let view = rows;
  const active = Object.entries(filters).filter(([, arr]) => Array.isArray(arr));
  if (active.length) {
    view = view.filter((row) =>
      active.every(([fk, arr]) => {
        const f = facetByKey[fk];
        return f ? arr.indexOf(f.value(row)) !== -1 : true;
      })
    );
  }
  if (sort) {
    const col = meta.find((c) => c.key === sort.key);
    if (col) {
      const sf = col._sortFacets && col._sortFacets[sort.sfi || 0];
      const valOf = sf ? (row) => sf.value(row) : (row) => rawOf(col, row);
      view = [...view].sort((ra, rb) => cmpVals(valOf(ra), valOf(rb)));
      if (sort.dir === "desc") view.reverse();
    }
  }

  function toggleSort(key) {
    const col = meta.find((c) => c.key === key);
    const facets = col && col._sortFacets;
    setSort((s) => {
      // Facet columns cycle: f0 asc → f0 desc → f1 asc → … → off
      if (facets && facets.length > 1) {
        if (!s || s.key !== key) return { key, sfi: 0, dir: "asc" };
        if (s.dir === "asc") return { key, sfi: s.sfi, dir: "desc" };
        if (s.sfi < facets.length - 1) return { key, sfi: s.sfi + 1, dir: "asc" };
        return null;
      }
      if (!s || s.key !== key) return { key, sfi: 0, dir: "asc" };
      if (s.dir === "asc") return { key, sfi: 0, dir: "desc" };
      return null;
    });
  }

  // Facet sort buttons (开工 / 完工): each is an independent sort toggle —
  // first click sorts asc by that sub-field, second desc, third clears.
  function toggleSortFacet(key, sfi) {
    setSort((s) => {
      if (!s || s.key !== key || (s.sfi || 0) !== sfi) return { key, sfi, dir: "asc" };
      if (s.dir === "asc") return { key, sfi, dir: "desc" };
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
    setPopPos({ left: Math.max(8, left), top: r.bottom + 6 });
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
    const move = (ev) => {
      const w = Math.max(56, Math.round(startW + ev.clientX - startX));
      setWidths((prev) => ({ ...prev, [key]: w }));
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
    const onDown = (e) => {
      if (!e.target.closest("[data-aps-fpop]") && !e.target.closest("[data-aps-fbtn]")) setOpenFilter(null);
    };
    const onKey = (e) => {
      if (e.key === "Escape") setOpenFilter(null);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [openFilter]);

  const activeCol = openFilter ? meta.find((c) => c.key === openFilter) : null;

  return (
    <div style={{ overflow: "auto", border: "1px solid var(--ui-border)", borderRadius: 8, background: "var(--ui-card-bg)" }}>
      <table data-aps-rtable="1" style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--font-family)", fontSize: 14, ...style }} {...rest}>
        <thead>
          <tr>
            {meta.map((c) => {
              const w = widths[c.key] != null ? widths[c.key] : c.width;
              const pinned = widths[c.key] != null;
              const justify = c.align === "right" ? "flex-end" : c.align === "center" ? "center" : "flex-start";
              const sorted = sort && sort.key === c.key ? sort.dir : null;
              const facetSort = c._sortable && c._sortFacets;
              const plainSortable = c._sortable && !facetSort;
              const hasFilter = c._facets && c._facets.some((f) => Array.isArray(filters[f.fkey]));
              return (
                <th
                  key={c.key}
                  className="aps-th"
                  style={{
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
                    maxWidth: pinned ? w : undefined,
                  }}
                >
                  <span
                    className={"aps-th-inner" + (plainSortable ? " aps-th-sortable" : "")}
                    style={{ justifyContent: justify, width: "100%" }}
                    onClick={plainSortable ? () => toggleSort(c.key) : undefined}
                  >
                    <span className="aps-th-label">{c.title}</span>
                    {facetSort ? (
                      <span className="aps-sort-facets">
                        {c._sortFacets.map((f, fi) => {
                          const on = sorted && (sort.sfi || 0) === fi;
                          return (
                            <button
                              type="button"
                              key={f.skey}
                              className={"aps-sort-facetbtn" + (on ? " on" : "")}
                              title={"按" + f.label + "排序"}
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleSortFacet(c.key, fi);
                              }}
                            >
                              {f.label}
                              {on ? <span className="aps-sort-facetarrow">{sort.dir === "desc" ? "↓" : "↑"}</span> : null}
                            </button>
                          );
                        })}
                      </span>
                    ) : null}
                    {plainSortable ? <span className={"aps-sortglyph" + (sorted ? " " + sorted : "")} /> : null}
                    {c._filterable ? (
                      <button
                        type="button"
                        data-aps-fbtn="1"
                        className={"aps-filter-btn" + (hasFilter ? " on" : "")}
                        title="筛选"
                        onClick={(e) => openFilterAt(e, c.key)}
                      >
                        {FUNNEL}
                      </button>
                    ) : null}
                  </span>
                  <span className="aps-th-resize" onMouseDown={(e) => startResize(e, c.key)} />
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {view.map((row, i) => (
            <Row key={row[rowKey] ?? i} row={row} columns={meta} even={i % 2 === 1} />
          ))}
        </tbody>
      </table>

      {activeCol && popPos ? (
        <FilterPop
          key={activeCol.key}
          facets={activeCol._facets}
          distinctMap={distinct}
          filters={filters}
          pos={popPos}
          matches={view.length}
          onChange={(fkey, arr) => {
            const all = distinct[fkey] || [];
            setFilters((f) => {
              const n = { ...f };
              if (!arr || arr.length >= all.length) delete n[fkey];
              else n[fkey] = arr;
              return n;
            });
          }}
          onClear={() => {
            setFilters((f) => {
              const n = { ...f };
              activeCol._facets.forEach((ff) => delete n[ff.fkey]);
              return n;
            });
            setOpenFilter(null);
          }}
        />
      ) : null}
    </div>
  );
}

function FilterPop({ facets, distinctMap, filters, pos, matches, onChange, onClear }) {
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

  const allValues = options.map((o) => o.value);
  const checkedSet = selected ? new Set(selected) : new Set(allValues);
  const ql = q.trim().toLowerCase();
  const labelOf = (v) => (v === "" ? "(空白)" : v);
  const shown = ql ? options.filter((o) => labelOf(o.value).toLowerCase().includes(ql)) : options;
  const shownChecked = shown.filter((o) => checkedSet.has(o.value)).length;
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
    if (next.has(value)) next.delete(value);
    else next.add(value);
    onChange(facet.fkey, [...next]);
  }
  function toggleAll() {
    const next = new Set(checkedSet);
    if (allOn) shown.forEach((o) => next.delete(o.value));
    else shown.forEach((o) => next.add(o.value));
    onChange(facet.fkey, [...next]);
  }

  return (
    <div data-aps-fpop="1" className="aps-filter-pop" style={{ left: pos.left, top: pos.top }}>
      {facets.length > 1 ? (
        <div className="aps-fp-tabs">
          {facets.map((f, i) => (
            <button
              type="button"
              key={f.fkey}
              className={"aps-fp-tab" + (i === fi ? " on" : "")}
              onClick={() => selectFacet(i)}
            >
              {f.label}
              {Array.isArray(filters[f.fkey]) ? <span className="aps-fp-tab-dot" /> : null}
            </button>
          ))}
        </div>
      ) : null}
      <input ref={searchRef} type="text" placeholder={"搜索 " + facet.label + "…"} value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="aps-fp-list">
        <label className="aps-fp-opt aps-fp-all">
          <input ref={allRef} type="checkbox" checked={allOn} onChange={toggleAll} />
          <span className="aps-fp-opt-label">(全选)</span>
          <span className="aps-fp-opt-count">{options.length}</span>
        </label>
        {shown.length === 0 ? (
          <div className="aps-fp-empty">无匹配项</div>
        ) : (
          shown.map((o) => (
            <label className="aps-fp-opt" key={o.value}>
              <input type="checkbox" checked={checkedSet.has(o.value)} onChange={() => toggle(o.value)} />
              <span className="aps-fp-opt-label" title={labelOf(o.value)}>{labelOf(o.value)}</span>
              <span className="aps-fp-opt-count">{o.count}</span>
            </label>
          ))
        )}
      </div>
      <div className="aps-fp-foot">
        <span className="aps-fp-count">{matches} 行匹配</span>
        <button type="button" className="aps-fp-clear" onClick={onClear}>清除</button>
      </div>
    </div>
  );
}

function Row({ row, columns, even }) {
  const [hover, setHover] = React.useState(false);
  const bg = hover ? "var(--ui-table-row-hover-bg)" : even ? "var(--ui-table-row-even-bg)" : "transparent";
  return (
    <tr onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)} style={{ background: bg, transition: "background-color .12s ease" }}>
      {columns.map((c) => {
        const num = c.align === "right";
        return (
          <td
            key={c.key}
            style={{
              textAlign: c.align || "left",
              padding: "10px 12px",
              borderBottom: "1px solid var(--ui-border)",
              color: "var(--ui-text)",
              verticalAlign: "middle",
              fontVariantNumeric: num ? "tabular-nums" : "normal",
              whiteSpace: c.nowrap ? "nowrap" : "normal",
            }}
          >
            {c.render ? c.render(row) : row[c.key]}
          </td>
        );
      })}
    </tr>
  );
}
