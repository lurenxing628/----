(function () {
  'use strict';
  function MasterOverviewStyles() {
    return <style>{`
      .master-overview {min-width:0;color:var(--ui-text);background:var(--ui-card-bg);font:13px/1.55 var(--font-family);letter-spacing:0;}
      .master-overview * {box-sizing:border-box;letter-spacing:0;}
      .master-overview h2 {font-size:20px;line-height:28px;margin:0;font-weight:600;}
      .master-overview h3 {font-size:16px;line-height:24px;margin:4px 0;overflow-wrap:anywhere;}
      .master-overview p {margin:5px 0;overflow-wrap:anywhere;}
      .master-overview .mo-heading,.master-overview .mo-actions,.master-overview .mo-tools,.master-overview .mo-pager {display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-width:0;}
      .master-overview .mo-heading {justify-content:space-between;margin-bottom:16px;gap:12px;}
      .master-overview .mo-heading p,.master-overview .mo-muted {font-size:12px;color:var(--ui-info-muted);}
      .master-overview .mo-metrics {--wb-columns:4;display:grid;margin-bottom:0;}
      .master-overview .mo-domains {--wb-columns:8;display:grid;border-top:0;}
      .master-overview .mo-domains .wb-metric {padding:8px 10px!important;min-height:72px;}
      .master-overview .mo-domains .wb-metric-value {font-size:20px!important;line-height:28px!important;}
      .master-overview .mo-domain {cursor:pointer;text-align:left;}
      .master-overview .mo-domain[aria-pressed=true] {outline:2px solid var(--ui-info-text);outline-offset:-2px;}
      .master-overview .mo-basis {margin:10px 0;color:var(--ui-info-muted);font-size:12px;line-height:1.7;}
      .master-overview .mo-gaps {border-bottom:1px solid var(--ui-border);padding:8px 0;color:var(--ui-warning-text);}
      .master-overview .mo-gaps ul {padding-left:20px;max-height:140px;overflow:auto;}
      .master-overview .mo-tools {padding:10px 0;align-items:flex-end;}
      .master-overview label {display:flex;align-items:center;gap:6px;min-width:0;font-size:12px;}
      .master-overview input,.master-overview select {border:1px solid var(--ui-border);border-radius:var(--wb-radius-control);background:var(--ui-card-bg);color:var(--ui-text);height:32px;padding:5px 8px;font:13px var(--font-family);max-width:100%;min-width:0;}
      .master-overview .mo-search {flex:1 1 220px;}
      .master-overview .mo-search input {width:100%;}
      .master-overview .mo-tabs {display:flex;gap:18px;flex-wrap:wrap;border-bottom:1px solid var(--ui-border);}
      .master-overview .mo-tabs button {border:0;border-bottom:2px solid transparent;padding:9px 0;background:transparent;color:var(--ui-info-muted);font:inherit;cursor:pointer;}
      .master-overview .mo-tabs button[aria-selected=true] {border-bottom-color:var(--ui-info-text);color:var(--ui-info-text);font-weight:600;}
      .master-overview .mo-tabs button span {font-size:12px;margin-left:6px;}
      .master-overview .mo-workspace {display:grid;grid-template-columns:minmax(0,1fr) 312px;gap:20px;align-items:start;}
      .master-overview .mo-list {min-width:0;}
      .master-overview .mo-table {table-layout:fixed;}
      .master-overview .mo-table td {white-space:normal!important;overflow-wrap:anywhere;padding:9px 8px!important;vertical-align:top;}
      .master-overview .mo-table th {vertical-align:top;}
      .master-overview .mo-column {display:flex;align-items:center;justify-content:space-between;gap:2px;}
      .master-overview .mo-column span {overflow-wrap:anywhere;}
      .master-overview .mo-link {padding:0;border:0;background:transparent;font:inherit;color:var(--ui-info-text);text-align:left;cursor:pointer;white-space:normal;overflow-wrap:anywhere;max-width:100%;}
      .master-overview button.btn:not(.wb-action) {display:inline-flex;align-items:center;gap:6px;min-height:30px;padding:5px 8px;background:var(--ui-card-bg);color:var(--ui-text);border:1px solid var(--ui-border);border-radius:var(--wb-radius-control);font:13px/18px var(--font-family);box-shadow:none;}
      .master-overview button.btn:not(.wb-action):hover:not(:disabled) {background:var(--ui-surface-muted);}
      .master-overview button.btn:disabled {color:var(--ui-info-muted);background:var(--ui-surface-muted);}
      .master-overview .mo-icon {height:30px;width:30px;min-width:30px;padding:5px!important;justify-content:center;}
      .master-overview .mo-sort-asc svg {transform:rotate(180deg);}
      .master-overview .mo-table button.btn.mo-icon {background:transparent;border:0;}
      .master-overview .mo-status[data-status=attention],.master-overview .mo-status[data-status=unknown] {color:var(--ui-warning-text);}
      .master-overview .mo-status[data-status=checked] {color:var(--ui-info-muted);}
      .master-overview .mo-detail {min-width:0;border-left:1px solid var(--ui-border);padding-left:18px;}
      .master-overview .mo-detail-head {display:flex;align-items:flex-start;gap:8px;justify-content:space-between;}
      .master-overview .mo-detail-head>div {min-width:0;}
      .master-overview .mo-detail .mo-tabs {gap:12px;font-size:12px;margin:10px 0;}
      .master-overview .mo-detail-list {list-style:none;padding:0;margin:0;}
      .master-overview .mo-detail-list li {padding:10px 0;border-bottom:1px solid var(--ui-border);overflow-wrap:anywhere;}
      .master-overview .mo-detail-list strong {font-weight:500;font-size:13px;}
      .master-overview .mo-field {margin:0;padding:8px 0;border-bottom:1px solid var(--ui-border);}
      .master-overview .mo-field dt {font-size:12px;color:var(--ui-info-muted);overflow-wrap:anywhere;}
      .master-overview .mo-field dd {margin:3px 0 0;white-space:pre-wrap;overflow-wrap:anywhere;}
      .master-overview .mo-source {font-size:11px;color:var(--ui-info-muted);overflow-wrap:anywhere;}
      .master-overview .mo-focus {border-left:2px solid var(--ui-warning-text);padding:6px 10px;margin-top:10px;}
      .master-overview .mo-focus strong {font-size:13px;color:var(--ui-warning-text);}
      .master-overview .mo-pager {justify-content:flex-end;padding:12px 0;font-size:12px;color:var(--ui-info-muted);font-variant-numeric:tabular-nums;}
      .master-overview .mo-empty {min-height:180px;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;border-top:1px solid var(--ui-border);gap:10px;color:var(--ui-info-muted);padding:20px 0;}
      .master-overview .mo-filter-band {padding:10px 0;display:flex;align-items:center;gap:8px;flex-wrap:wrap;border-top:1px solid var(--ui-border);}
      .master-overview .mo-filter-band input {width:250px;}
      .master-overview .mo-message {padding:8px 0;color:var(--ui-info-muted);overflow-wrap:anywhere;}
      .master-overview button:disabled {cursor:default;}
      .master-overview button:focus-visible,.master-overview input:focus-visible,.master-overview select:focus-visible,.master-overview .mo-detail:focus-visible {outline:2px solid var(--ui-info-text);outline-offset:2px;}
      @media(max-width:1100px){.master-overview .mo-workspace {grid-template-columns:minmax(0,1fr);}.master-overview .mo-detail {border-left:0;border-top:1px solid var(--ui-border);padding:16px 0 0;}.master-overview .mo-domains {--wb-columns:4;}}
      @media(max-width:600px){.master-overview .mo-metrics,.master-overview .mo-domains {--wb-columns:2;}.master-overview .mo-heading>.mo-actions {width:100%;}.master-overview .mo-filter-band input {width:100%;}}
    `}</style>;
  }
  window.MasterOverviewStyles = MasterOverviewStyles;
})();
