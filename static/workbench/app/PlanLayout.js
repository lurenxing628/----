(function () {
  'use strict';

  function PlanLayout() {
    return /*#__PURE__*/React.createElement("style", null, `
      .plana.plan-workspace { padding:0; max-width:none; width:100%; min-width:0; color:var(--ui-text); font:13px/1.55 var(--font-family); font-variant-numeric:tabular-nums; }
      .plan-workspace * { box-sizing:border-box; letter-spacing:0; }
      .plan-workspace h2,.plan-workspace h3,.plan-workspace p { margin:0; }
      .plan-workspace h2 { font-size:17px; line-height:24px; font-weight:600; }
      .plan-workspace h3 { font-size:14px; line-height:22px; font-weight:600; }
      .plan-workspace button,.plan-workspace input { font-family:inherit; }
      .plan-workspace :focus-visible { outline:2px solid var(--ui-primary); outline-offset:2px; }
      .plan-workspace .plan-muted { color:var(--ui-info-muted); font-size:12px; }
      .plan-workspace .plan-danger { color:var(--ui-danger-text); }
      .plan-heading,.plan-toolbar,.plan-footer,.plan-pager { display:flex; align-items:center; flex-wrap:wrap; gap:8px 12px; }
      .plan-heading { justify-content:space-between; margin-bottom:12px; }
      .plan-heading > div { min-width:0; overflow-wrap:anywhere; }
      .plan-toolbar { padding:8px 12px; background:var(--ui-surface-muted); border-bottom:1px solid var(--ui-border); }
      .plan-workspace .plan-actions { display:flex; align-items:center; flex-wrap:wrap; gap:6px; margin-left:auto; }
      .plan-workspace .plan-icon { width:32px; height:32px; min-width:32px; padding:5px; display:inline-flex; align-items:center; justify-content:center; }
      .plan-workspace .plan-up svg { transform:rotate(180deg); }.plan-workspace .plan-fit svg { transform:rotate(90deg); }
      .plan-workspace .plan-segment { display:inline-flex; flex-wrap:wrap; border:1px solid var(--ui-border); border-radius:var(--wb-radius-control); padding:2px; gap:2px; }
      .plan-workspace .plan-segment button { min-width:52px; height:28px; padding:2px 10px; border:1px solid transparent; border-radius:var(--wb-radius-control); background:transparent; color:var(--ui-info-muted); font:inherit; }
      .plan-workspace .plan-segment button[aria-pressed=true] { color:var(--wb-gantt-primary-ink); background:var(--wb-gantt-primary-fill); border-color:var(--wb-gantt-primary-edge); }
      .plan-workspace .plan-segment > span { display:contents !important; }
      .plan-state { display:inline-flex; align-items:center; white-space:normal; padding:2px 6px; font-size:12px; border-radius:var(--wb-radius-control); background:var(--ui-info-bg); color:var(--ui-info-text); }
      .plan-state.official { color:var(--ui-success-text); background:var(--ui-success-bg); }
      .plan-state.unavailable { color:var(--ui-warning-text); background:var(--ui-warning-bg); }
      .plan-catalog { margin-bottom:14px; border-block:1px solid var(--ui-border); }
      .plan-catalog-scroll { max-height:180px; overflow:auto; }
      .plan-workspace table { width:100%; border-collapse:collapse; font:inherit; text-align:left; }
      .plan-workspace th { background:var(--ui-surface-muted); color:var(--ui-info-muted); font-weight:500; }
      .plan-workspace th,.plan-workspace td { padding:8px 12px; border-bottom:1px solid var(--ui-border); overflow-wrap:anywhere; }
      .plan-catalog th { position:sticky; top:0; z-index:1; }
      .plan-catalog tr[aria-selected=true] { background:var(--ui-info-bg); }
      .plan-catalog td:first-child { width:34%; }
      .plan-catalog label { display:flex; gap:10px; align-items:center; cursor:pointer; }
      .plan-workspace input[type=radio],.plan-workspace input[type=checkbox] { width:14px; height:14px; margin:0; accent-color:var(--ui-primary); flex:none; }
      .plan-pager { min-height:40px; padding:5px 12px; background:var(--ui-card-bg); }
      .plan-check { display:inline-flex; align-items:center; gap:6px; }
      .plan-workspace .plan-search { position:relative; display:block; width:220px; min-width:140px; max-width:100%; height:32px; }
      .plan-workspace .plan-search .ic { position:absolute; left:10px; top:50%; transform:translateY(-50%); pointer-events:none; display:flex; align-items:center; color:var(--ui-info-muted); }
      .plan-workspace .plan-search input { width:100%; min-width:0; }
      .plan-range { display:flex; align-items:end; flex-wrap:wrap; gap:10px; padding:10px 0; }
      .plan-range .field { margin:0; width:210px; max-width:100%; }
      .plan-main { display:grid; grid-template-columns:minmax(0,1fr) 290px; gap:18px; align-items:start; }
      .plan-main > div,.plan-inspector { min-width:0; }
      .plan-board-frame { border:1px solid var(--ui-border); background:var(--ui-card-bg); overflow:hidden; }
      .plan-board { overflow:auto; height:440px; position:relative; overscroll-behavior:contain; }
      .plan-board-inner { position:relative; min-height:100%; }
      .plan-axis { position:sticky; top:0; height:52px; z-index:5; display:flex; background:var(--ui-surface-muted); border-bottom:1px solid var(--ui-border); }
      .plan-corner { position:sticky; left:0; z-index:7; width:var(--plan-label); min-width:var(--plan-label); height:52px; background:var(--ui-surface-muted); border-right:1px solid var(--ui-border); padding:7px 12px; }
      .plan-corner small { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
      .plan-ticks { position:relative; overflow:hidden; flex:none; }
      .plan-tick { position:absolute; top:0; height:52px; width:124px; padding:4px 7px; border-left:1px solid var(--ui-border); font-size:12px; }
      .plan-tick small { display:block; font-size:11px; color:var(--ui-info-muted); }
      .plan-lane { position:absolute; left:0; display:flex; border-bottom:1px solid var(--ui-border); }
      .plan-resource { position:sticky; left:0; z-index:3; width:var(--plan-label); min-width:var(--plan-label); height:100%; border-right:1px solid var(--ui-border); padding:7px 12px; background:var(--ui-surface-muted); overflow:hidden; }
      .plan-resource strong { display:block; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
      .plan-resource small { display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:11px; color:var(--ui-info-muted); }
      .plan-lane.baseline .plan-resource { padding-block:3px; }
      .plan-track { position:relative; height:100%; overflow:hidden; flex:none; }
      .plan-gridline { position:absolute; top:0; bottom:0; border-left:1px solid var(--ui-border); pointer-events:none; }
      .plan-workspace .plan-bar { position:absolute; top:7px; height:40px; min-width:0; border:0; background:transparent; padding:0; color:var(--wb-gantt-primary-ink); cursor:pointer; overflow:hidden; }
      .plan-bar-face { position:absolute; inset:0 min(2px,10%); border:1px solid var(--wb-gantt-primary-edge); background:var(--wb-gantt-primary-fill); border-radius:var(--wb-gantt-radius-bar); padding:2px; overflow:hidden; display:flex; flex-direction:column; justify-content:center; pointer-events:none; }
      .plan-bar strong { flex:none; font-size:12px; line-height:18px; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
      .plan-bar small { flex:none; font-size:11px; line-height:15px; white-space:nowrap; overflow:hidden; }
      .plan-workspace .plan-bar.critical { color:var(--wb-gantt-critical-ink); }
      .plan-bar.critical .plan-bar-face { background:var(--wb-gantt-critical-fill); border-color:var(--wb-gantt-critical-edge); }
      .plan-workspace .plan-bar.success { color:var(--wb-gantt-success-ink); }
      .plan-bar.success .plan-bar-face { background:var(--wb-gantt-success-fill); border-color:var(--wb-gantt-success-edge); }
      .plan-bar.conflict .plan-bar-face { border-style:dashed; }
      .plan-bar[aria-pressed=true] .plan-bar-face,.plan-bar:focus-visible .plan-bar-face { box-shadow:inset 0 0 0 2px var(--wb-gantt-gold); }
      .plan-workspace .plan-bar:focus-visible { outline:0 !important; }
      .plan-workspace .plan-bar.before { top:9px; height:8px; }
      .plan-bar.before .plan-bar-face { background:var(--wb-gantt-plan-fill); border:1px dashed var(--wb-gantt-plan-edge); padding:0; }
      .plan-row-canvas { position:absolute; top:0; height:100%; }
      .plan-row-canvas:focus-visible { outline-offset:-2px !important; }
      .plan-global { padding:8px 12px; background:var(--ui-card-bg); border-bottom:1px solid var(--ui-border); }
      .plan-global-labels { display:flex; justify-content:space-between; gap:10px; font-size:11px; color:var(--ui-info-muted); }
      .plan-global canvas { display:block; width:100%; height:26px; cursor:crosshair; }
      .plan-global input { display:block; width:100%; height:10px; padding:0; accent-color:var(--ui-primary); }
      .plan-footer { padding:8px 12px; border-top:1px solid var(--ui-border); font-size:12px; color:var(--ui-info-muted); }
      .plan-legend { display:inline-flex; align-items:center; gap:5px; }
      .plan-swatch { display:inline-block; width:20px; height:9px; background:var(--wb-gantt-primary-fill); border:1px solid var(--wb-gantt-primary-edge); }
      .plan-swatch.critical { background:var(--wb-gantt-critical-fill); border-color:var(--wb-gantt-critical-edge); }
      .plan-swatch.before { height:6px; background:var(--wb-gantt-plan-fill); border:1px dashed var(--wb-gantt-plan-edge); }
      .plan-inspector { position:sticky; top:76px; background:var(--ui-card-bg); padding:14px; border-left:1px solid var(--ui-border); max-height:calc(100vh - 96px); overflow:auto; }
      .plan-facts { display:grid; grid-template-columns:76px minmax(0,1fr); gap:7px 8px; margin:12px 0; }
      .plan-facts dt { color:var(--ui-info-muted); }.plan-facts dd { margin:0; overflow-wrap:anywhere; }
      .plan-inspector section + section { margin-top:16px; padding-top:12px; border-top:1px solid var(--ui-border); }
      .plan-projections { margin-top:12px; }.plan-projection-table { overflow:auto; max-height:270px; }
      .plan-projections th { position:sticky; top:0; z-index:1; }.plan-projections .plan-segment { border:0; padding:4px 0; gap:12px; }
      .plan-projections .plan-segment button { border-radius:0; padding:5px 0; min-width:70px; height:34px; }
      .plan-projections .plan-segment button[aria-pressed=true] { background:transparent; border-color:transparent transparent var(--ui-primary); }
      .plan-meter { display:block; width:100%; height:4px; background:var(--ui-border); margin-top:4px; }
      .plan-meter i { display:block; height:100%; background:var(--wb-gantt-primary-progress); }
      .plan-empty { padding:30px 16px; text-align:center; color:var(--ui-info-muted); }
      .plan-note { padding:8px 12px; font-size:12px; overflow-wrap:anywhere; background:var(--ui-surface-muted); }
      .plan-workspace .wb-metric { min-height:60px; padding:8px 12px; }.plan-workspace .wb-metric-value { font-size:22px; }
      .plan-tooltip { position:fixed; z-index:100; pointer-events:none; max-width:320px; padding:9px 12px; background:var(--ui-card-bg); color:var(--ui-text); border:1px solid var(--ui-border); border-radius:4px; box-shadow:var(--ui-shadow-md); white-space:pre-line; font-size:12px; overflow-wrap:anywhere; }
      .plan-export-summary { white-space:normal; padding:16px; }.plan-export-summary p + p { margin-top:10px; }
      @media (max-width:1500px) { .plan-main { grid-template-columns:minmax(0,1fr) 250px; gap:14px; }.plan-board { height:390px; }.plan-catalog-scroll { max-height:155px; } }
      @media (max-width:1050px) { .plan-main { grid-template-columns:minmax(0,1fr); }.plan-inspector { position:static; border-left:0; border-top:1px solid var(--ui-border); max-height:none; }.plan-workspace .plan-actions { margin-left:0; } }
      @media (max-width:620px) { .plan-catalog table { min-width:570px; }.plan-heading { align-items:start; }.plan-range .field { width:100%; }.plan-global-labels { flex-wrap:wrap; }.plan-projection-table table { min-width:620px; } }
      .plan-workspace .plan-expanded { position:fixed; inset:16px; z-index:40; background:var(--ui-card-bg); padding:12px; display:flex; flex-direction:column; }
      .plan-workspace .plan-expanded .plan-board-frame { flex:1; min-height:0; display:flex; flex-direction:column; }
      .plan-workspace .plan-expanded .plan-board { flex:1; min-height:0; height:auto; }
      .plan-workspace .plan-expanded .plan-toolbar,.plan-workspace .plan-expanded .plan-note,.plan-workspace .plan-expanded .plan-global,.plan-workspace .plan-expanded .plan-footer { flex:none; }
    `);
  }
  window.PlanLayout = PlanLayout;
})();
