(function () {
  'use strict';
  function Styles() { return <style>{`
    .dashboard-live {width:100%;max-width:none;min-width:0;color:var(--ui-text);font:13px/1.55 var(--font-family);letter-spacing:0;}
    .dashboard-live * {box-sizing:border-box;letter-spacing:0;}
    .dashboard-live h2,.dashboard-live h3,.dashboard-live p {margin:0;}
    .dashboard-live h2 {font-size:22px;font-weight:600;} .dashboard-live h3 {font-size:15px;font-weight:600;}
    .dashboard-live button,.dashboard-live input,.dashboard-live select,.dashboard-live textarea {font:inherit;letter-spacing:0;}
    .dashboard-live .dy-heading,.dashboard-live .dy-tools,.dashboard-live .dy-context,.dashboard-live .dy-pager {display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
    .dashboard-live .dy-heading {justify-content:space-between;margin-bottom:8px;} .dashboard-live .dy-context {color:var(--ui-info-muted);font-size:12px;margin-bottom:20px;}
    .dashboard-live .dy-muted {color:var(--ui-info-muted);} .dashboard-live .dy-danger {color:var(--ui-danger-text);} .dashboard-live .dy-warning {color:var(--ui-warning-text);}
    .dashboard-live .dy-metrics {display:grid;grid-template-columns:repeat(7,minmax(0,1fr));margin-bottom:24px;background:var(--ui-card-bg);}
    .dashboard-live .dy-metric {border:0;border-right:1px solid var(--ui-border);padding:14px 18px;text-align:left;background:transparent;color:var(--ui-text);cursor:pointer;min-height:100px;}
    .dashboard-live .dy-metric:last-child {border-right:0;} .dashboard-live .dy-metric:hover {background:var(--ui-surface-muted);}
    .dashboard-live .dy-metric strong {display:block;font-size:25px;line-height:34px;font-weight:600;} .dashboard-live .dy-metric small {display:block;color:var(--ui-info-muted);}
    .dashboard-live .dy-work {display:grid;grid-template-columns:228px minmax(0,1fr);min-height:590px;background:var(--ui-card-bg);}
    .dashboard-live .dy-rail {border-right:1px solid var(--ui-border);min-width:0;} .dashboard-live .dy-rail h3 {padding:14px 16px;background:var(--ui-surface-soft);}
    .dashboard-live .dy-category {display:block;width:100%;padding:13px 14px;border:0;border-bottom:1px solid var(--ui-border);border-left:3px solid transparent;background:transparent;color:var(--ui-text);text-align:left;cursor:pointer;}
    .dashboard-live .dy-category[aria-pressed=true] {border-left-color:var(--ui-primary);background:var(--ui-primary-soft);}
    .dashboard-live .dy-category small {display:block;color:var(--ui-info-muted);margin-top:5px;} .dashboard-live .dy-main {min-width:0;}
    .dashboard-live .dy-section-head {padding:17px 20px;background:var(--ui-surface-soft);display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;}
    .dashboard-live .dy-tabs {display:flex;flex-wrap:wrap;border-bottom:1px solid var(--ui-border);background:var(--ui-surface-muted);padding:0 12px;}
    .dashboard-live .dy-tab {border:0;border-bottom:2px solid transparent;background:transparent;padding:11px 14px;color:var(--ui-text);cursor:pointer;}
    .dashboard-live .dy-tab[aria-selected=true] {border-bottom-color:var(--ui-primary);color:var(--ui-info-text);font-weight:600;}
    .dashboard-live .dy-panel {padding:20px;min-width:0;} .dashboard-live .dy-filters {display:flex;align-items:flex-end;gap:10px;flex-wrap:wrap;margin-bottom:16px;}
    .dashboard-live .dy-filters label {display:flex;flex-direction:column;gap:4px;min-width:130px;} .dashboard-live .dy-filters .dy-search {flex:1;min-width:200px;}
    .dashboard-live input,.dashboard-live textarea,.dashboard-live select {color:var(--ui-text);background:var(--ui-card-bg);border:1px solid var(--ui-border);border-radius:var(--wb-radius-control);padding:6px 9px;min-width:0;max-width:100%;}
    .dashboard-live input,.dashboard-live select {height:34px;} .dashboard-live textarea {min-height:74px;resize:vertical;}
    .dashboard-live .dy-scroll {max-width:100%;overflow-x:auto;} .dashboard-live table {border-collapse:collapse;width:100%;font-size:13px;text-align:left;}
    .dashboard-live th {background:var(--ui-surface-muted);color:var(--ui-info-muted);font-weight:500;} .dashboard-live th,.dashboard-live td {padding:10px 9px;border-bottom:1px solid var(--ui-border);vertical-align:top;overflow-wrap:anywhere;}
    .dashboard-live .dy-table {table-layout:fixed;min-width:720px;} .dashboard-live .dy-table th:first-child {width:26%;} .dashboard-live .dy-table th:nth-child(2) {width:27%;}
    .dashboard-live .dy-table th:last-child {width:120px;} .dashboard-live tr[data-selected=true] {background:var(--ui-primary-soft);}
    .dashboard-live .dy-badge {display:inline-flex;align-items:center;gap:5px;padding:2px 7px;border-radius:var(--wb-radius-control);font-size:12px;white-space:normal;}
    .dashboard-live .dy-badge.danger {color:var(--ui-danger-text);background:var(--ui-danger-bg);} .dashboard-live .dy-badge.warning {color:var(--ui-warning-text);background:var(--ui-warning-bg);}
    .dashboard-live .dy-badge.info {color:var(--ui-info-text);background:var(--ui-primary-soft);} .dashboard-live .dy-badge.success {color:var(--ui-success-text);background:var(--ui-success-bg);}
    .dashboard-live .dy-badge.neutral {color:var(--ui-text);background:var(--ui-surface-muted);} .dashboard-live .dy-empty {padding:36px 8px;color:var(--ui-info-muted);}
    .dashboard-live .dy-note {padding:10px 12px;background:var(--ui-surface-muted);margin:10px 0;overflow-wrap:anywhere;}
    .dashboard-live .dy-note.warning {background:var(--ui-warning-bg);color:var(--ui-warning-text);} .dashboard-live .dy-note.success {background:var(--ui-success-bg);color:var(--ui-success-text);}
    .dashboard-live .dy-pager {justify-content:flex-end;padding-top:12px;} .dashboard-live .dy-detail {margin-top:22px;border-top:1px solid var(--ui-border);padding-top:18px;}
    .dashboard-live .dy-detail h3 {margin-bottom:10px;} .dashboard-live .dy-facts {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 24px;margin:12px 0;}
    .dashboard-live .dy-facts>div {min-width:0;display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid var(--ui-border);padding-bottom:7px;}
    .dashboard-live dt {color:var(--ui-info-muted);} .dashboard-live dd {margin:0;overflow-wrap:anywhere;max-width:75%;white-space:pre-wrap;}
    .dashboard-live .dy-evidence summary {cursor:pointer;color:var(--ui-info-text);padding:8px 0;} .dashboard-live .dy-evidence pre {white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;max-height:320px;overflow:auto;}
    .dashboard-live .dy-history {padding:14px 0;border-bottom:1px solid var(--ui-border);} .dashboard-live .dy-history time {color:var(--ui-info-muted);font-size:12px;}
    .dashboard-live .dy-form {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;} .dashboard-live .dy-form label {display:flex;flex-direction:column;gap:5px;min-width:0;}
    .dashboard-live .dy-form .wide {grid-column:1/-1;} .dashboard-live .dy-dialog-body {padding:18px 22px;overflow-y:auto;min-height:0;}
    .dashboard-live .modal {display:flex;flex-direction:column;max-height:calc(100vh - 40px);color:var(--ui-text);background:var(--ui-card-bg);}
    .dashboard-live .modal-head {flex:none;background:var(--ui-surface-soft);} .dashboard-live .modal-f {flex:none;background:var(--ui-surface-muted);}
    .dashboard-live .dy-meter {width:110px;height:7px;background:var(--ui-surface-muted);margin-top:6px;} .dashboard-live .dy-meter i {display:block;height:100%;background:var(--ui-info-text);}
    .dashboard-live .dy-meter.hot i {background:var(--ui-danger-text);} .dashboard-live .dy-resource {min-width:860px;}
    .dashboard-live .dy-footer {display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;color:var(--ui-info-muted);font-size:12px;margin-top:12px;}
    .dashboard-live :focus-visible {outline:2px solid var(--ui-primary);outline-offset:2px;}
    .dashboard-live .dy-sort-asc svg {transform:rotate(180deg);}
    .dashboard-live .dy-category-picker {display:flex;align-items:center;gap:8px;margin-left:auto;min-width:0;}
    .dashboard-live .dy-category-picker select {max-width:220px;}
    .dashboard-live .dy-panel section+section,.dashboard-live [data-dashboard-candidates]+section {margin-top:24px;padding-top:18px;border-top:1px solid var(--ui-border);}
    .dashboard-live .dy-analysis-table {min-width:650px;} .dashboard-live .dy-analysis-table small {display:block;color:var(--ui-info-muted);}
    .dashboard-live .dy-timeline-board {position:relative;overflow:auto;max-width:100%;border:1px solid var(--ui-border);background:var(--ui-card-bg);}
    .dashboard-live .dy-timeline-inner {position:relative;}
    .dashboard-live .dy-timeline-axis {position:sticky;top:0;z-index:4;display:flex;height:48px;background:var(--ui-surface-soft);border-bottom:1px solid var(--ui-border);}
    .dashboard-live .dy-timeline-corner {position:sticky;left:0;z-index:5;width:var(--dy-label-width);flex-shrink:0;padding:12px;background:var(--ui-surface-soft);border-right:1px solid var(--ui-border);}
    .dashboard-live .dy-timeline-ticks {position:relative;flex-shrink:0;} .dashboard-live .dy-timeline-ticks>div {position:absolute;top:5px;padding-left:5px;font-size:11px;white-space:nowrap;}
    .dashboard-live .dy-timeline-ticks small {display:block;}
    .dashboard-live .dy-timeline-row {position:absolute;display:flex;border-bottom:1px solid var(--ui-border);}
    .dashboard-live .dy-timeline-label {position:sticky;left:0;z-index:3;width:var(--dy-label-width);flex-shrink:0;padding:5px 10px;background:var(--ui-card-bg);border-right:1px solid var(--ui-border);overflow:hidden;}
    .dashboard-live .dy-timeline-label b,.dashboard-live .dy-timeline-label small {display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
    .dashboard-live .dy-timeline-label small {font-size:11px;color:var(--ui-info-muted);}
    .dashboard-live .dy-timeline-track {position:relative;flex-shrink:0;}
    .dashboard-live .dy-timeline-grid {position:absolute;top:0;bottom:0;border-left:1px solid var(--ui-border);pointer-events:none;}
    .dashboard-live .dy-downtime-window {position:absolute;top:2px;bottom:2px;background:var(--ui-danger-bg);border:1px dashed var(--ui-danger-text);opacity:.75;}
    .dashboard-live .dy-analysis-bar {position:absolute;top:14px;height:28px;padding:0 6px;border:1px solid var(--ui-info-text);border-radius:3px;background:var(--ui-primary-soft);color:var(--ui-text);cursor:pointer;overflow:hidden;white-space:nowrap;text-align:left;}
    .dashboard-live .dy-analysis-bar span {display:block;overflow:hidden;text-overflow:ellipsis;}
    .dashboard-live .dy-analysis-bar.selected {background:var(--ui-info-text);color:var(--ui-card-bg);outline:2px solid var(--ui-warning-text);outline-offset:1px;}
    .dashboard-live .dy-analysis-bar.point {height:10px;top:22px;padding:0;transform:rotate(45deg);border-radius:0;}
    .dashboard-live .dy-analysis-tooltip {position:fixed;z-index:1800;width:360px;max-width:calc(100vw - 16px);max-height:210px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;padding:10px 12px;background:var(--ui-card-bg);color:var(--ui-text);border:1px solid var(--ui-border);box-shadow:0 4px 16px #0002;font-size:12px;pointer-events:none;}
    .dashboard-live .dy-run-picker {display:flex;align-items:center;gap:10px;margin:12px 0;} .dashboard-live .dy-run-picker select {max-width:100%;min-width:0;flex:1;}
    .dashboard-live .dy-candidate-options {display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;padding:10px 0;border:0;max-height:240px;overflow:auto;margin:0;}
    .dashboard-live .dy-candidate-options legend {padding:0;font-weight:600;} .dashboard-live .dy-candidate-options label {display:flex;align-items:center;gap:10px;padding:8px;border-bottom:1px solid var(--ui-border);min-height:65px;min-width:0;cursor:pointer;}
    .dashboard-live .dy-candidate-options input {flex:none;width:16px;height:16px;padding:0;} .dashboard-live .dy-candidate-options b,.dashboard-live .dy-candidate-options small {display:block;overflow-wrap:anywhere;}
    .dashboard-live .dy-candidate-options small {color:var(--ui-info-muted);} .dashboard-live .dy-compare-range {display:flex;align-items:flex-end;gap:10px;flex-wrap:wrap;margin:14px 0;}
    .dashboard-live .dy-compare-range label {display:flex;flex-direction:column;gap:4px;min-width:0;max-width:100%;}
    .dashboard-live .dy-candidate-summary {overflow:auto;min-height:0;overflow-wrap:anywhere;}
    @media(max-width:1050px) {.dashboard-live .dy-work {grid-template-columns:minmax(0,1fr);} .dashboard-live .dy-rail {border-right:0;display:flex;flex-wrap:wrap;} .dashboard-live .dy-rail h3 {width:100%;} .dashboard-live .dy-category {width:33.333%;}}
    @media(max-width:600px) {.dashboard-live .dy-metrics {grid-template-columns:repeat(2,minmax(0,1fr));} .dashboard-live .dy-metric {padding:10px;} .dashboard-live .dy-panel {padding:12px;} .dashboard-live .dy-form,.dashboard-live .dy-facts {grid-template-columns:minmax(0,1fr);} .dashboard-live .dy-tab {padding:10px;} .dashboard-live .dy-filters label {min-width:0;max-width:100%;}}
  `}</style>; }
  window.DashboardStyles = Styles;
})();
