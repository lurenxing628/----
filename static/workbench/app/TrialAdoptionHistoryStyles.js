(function () {
  'use strict';

  window.TrialAdoptionHistoryStyles = function TrialAdoptionHistoryStyles() {
    return /*#__PURE__*/React.createElement("style", null, `
      .tah-toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:8px 14px;padding:8px 0;border-bottom:1px solid var(--ui-border)}
      .tah-toolbar label{display:flex;gap:6px;align-items:center;font-size:12px}
      .tah-toolbar select{max-width:160px;min-height:30px;border:1px solid var(--ui-border);border-radius:4px;background:var(--ui-card-bg);color:var(--ui-text);padding:3px 6px}
      .tah-meta{font-size:12px;color:var(--ui-info-muted);margin:8px 0;overflow-wrap:anywhere}
      .tah-list{list-style:none;margin:0;padding:0}
      .tah-list>li{padding:10px 0;border-bottom:1px solid var(--ui-border);font-size:12px;line-height:20px;min-width:0}
      .tah-head{display:flex;align-items:center;flex-wrap:wrap;gap:8px}
      .tah-head strong{font-size:13px;font-weight:600}
      .tah-head .btn{margin-left:auto}
      .tah-state{padding:1px 5px;border-radius:3px;color:var(--ui-info-muted);background:var(--ui-surface-muted)}
      .tah-current{color:var(--ui-success-text);background:var(--ui-success-bg)}
      .tah-unavailable{color:var(--ui-warning-text);background:var(--ui-warning-bg)}
      .tah-list p{margin:4px 0;overflow-wrap:anywhere;white-space:pre-wrap}
      .tah-list details{margin-top:4px;overflow-wrap:anywhere}
      .tah-refs{display:grid;grid-template-columns:92px minmax(0,1fr);gap:4px 8px;margin:6px 0}
      .tah-refs dt{color:var(--ui-info-muted)}.tah-refs dd{margin:0;overflow-wrap:anywhere}
      .tah-gap{color:var(--ui-warning-text)}
      .trial-workspace .tt-tabs{flex-wrap:wrap;row-gap:0}
    `);
  };
})();
