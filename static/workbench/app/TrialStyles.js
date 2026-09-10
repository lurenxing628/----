(function () {
  'use strict';

  function Styles() {
    return /*#__PURE__*/React.createElement("style", null, `
    .plana.trial-workspace{width:100%;max-width:none;padding:0}
    .trial-workspace,.trial-modal-body{color:var(--ui-text);font-size:13px;line-height:1.55;letter-spacing:0;min-width:0}
    .trial-workspace *,.trial-modal-body *{box-sizing:border-box;letter-spacing:0}
    .trial-workspace h2{font-size:20px;margin:0}.trial-workspace h3,.trial-modal-body h3{font-size:15px;margin:0}
    .trial-workspace h4,.trial-modal-body h4{font-size:13px;margin:8px 0}.trial-workspace p,.trial-modal-body p{margin:8px 0}
    .trial-workspace .btn,.trial-modal-body .btn{min-height:32px;gap:6px;max-width:100%}
    .trial-workspace input:not([type=checkbox]):not([type=radio]),.trial-workspace select,.trial-modal-body input:not([type=checkbox]):not([type=radio]),.trial-modal-body select{
      background:var(--ui-card-bg);color:var(--ui-text);border:1px solid var(--ui-border);border-radius:var(--wb-radius-control,4px);min-height:32px;padding:5px 8px;font:inherit;min-width:0;max-width:100%}
    .trial-workspace input[type=checkbox],.trial-modal-body input[type=checkbox],.trial-modal-body input[type=radio]{width:15px;height:15px;flex:none;accent-color:var(--ui-primary)}
    .tt-heading,.tt-tools,.tt-pager{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.tt-heading{justify-content:space-between;margin:10px 0}
    .tt-tools label{display:inline-flex;align-items:center;gap:6px}.tt-tools input[type=search]{width:186px}
    .tt-muted,.tt-pager{font-size:12px;color:var(--ui-info-muted)}.tt-pager{justify-content:flex-end;padding:6px 0}
    .tt-empty{padding:20px;color:var(--ui-info-muted);text-align:center}.tt-error,.tt-notice{padding:9px 12px;margin:8px 0;overflow-wrap:anywhere}
    .tt-error{background:var(--ui-danger-bg);color:var(--ui-danger-text);border-left:3px solid var(--ui-danger)}
    .tt-notice{background:var(--ui-info-bg);color:var(--ui-info-text);border-left:3px solid var(--ui-info-border)}
    .tt-check{display:inline-flex;gap:7px;align-items:center;max-width:100%}.tt-tabs{display:flex;gap:15px;border-bottom:1px solid var(--ui-border);max-width:100%;flex-wrap:wrap}
    .tt-tabs button{border:0;border-bottom:2px solid transparent;background:transparent;color:var(--ui-info-muted);padding:7px 0;font:inherit;white-space:nowrap}
    .tt-tabs button[aria-selected=true]{border-bottom-color:var(--ui-primary);color:var(--ui-info-text);font-weight:600}
    .tt-directory{border-block:1px solid var(--ui-border);padding-bottom:8px;margin-bottom:12px}.tt-directory-scroll{max-height:170px;overflow:auto}
    .tt-directory th{position:sticky;top:0;z-index:1}.tt-table-scroll{overflow:auto;max-width:100%}
    .tt-table{border-collapse:collapse;width:100%;font-size:12px;line-height:1.6;text-align:left;background:var(--ui-card-bg)}
    .tt-table th{background:var(--ui-surface-muted);color:var(--ui-info-muted);font-weight:500;white-space:nowrap;padding:7px 9px}
    .tt-table td{border-bottom:1px solid var(--ui-border);padding:7px 9px;vertical-align:top;overflow-wrap:anywhere}
    .tt-table .btn{font-size:12px;white-space:normal;text-align:left;justify-content:flex-start}
    .tt-source-list{max-height:220px;overflow:auto;border-block:1px solid var(--ui-border);margin:8px 0}.tt-source-row{padding:8px;display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid var(--ui-border)}
    .tt-source-row label{display:flex;align-items:center;gap:8px;overflow-wrap:anywhere}.tt-source-row .tt-muted{flex:none}
    .trial-modal-body{padding:16px 20px;overflow:auto;max-height:calc(100vh - 220px)}
    .trial-modal-body .tt-table{table-layout:fixed}.trial-modal-body .tt-table th:first-child{width:55px}.trial-modal-body .tt-table th:last-child{width:70px}
    .tt-naming{display:flex;flex-direction:column;gap:6px;margin:14px 0}.tt-naming input{width:100%}
    .tt-summary{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border-block:1px solid var(--ui-border);margin:12px 0;padding:10px 0}
    .tt-summary>div{padding:0 14px;border-right:1px solid var(--ui-border)}.tt-summary>div:last-child{border:0}.tt-summary span{display:block;font-size:12px;color:var(--ui-info-muted)}
    .tt-summary strong{display:block;font-size:20px;line-height:1.5;font-weight:600}.tt-main{display:grid;grid-template-columns:minmax(0,1fr) 292px;gap:18px;align-items:start}
    .tt-main>div{min-width:0}.tt-detail{padding:0 8px 8px 16px;border-left:1px solid var(--ui-border);min-width:0;overflow-wrap:anywhere;max-height:min(680px,calc(100vh - 160px));overflow:auto;position:sticky;top:20px}
    .tt-detail section{margin-top:16px}.tt-detail .tt-table{table-layout:fixed}.tt-detail .tt-table th:first-child{width:40px}.tt-detail .tt-table th:last-child{width:65px}
    .tt-facts{display:grid;grid-template-columns:76px minmax(0,1fr);gap:5px 8px;margin:12px 0}.tt-facts dt{color:var(--ui-info-muted)}.tt-facts dd{margin:0}
    .tt-editor{border-block:1px solid var(--ui-border);padding:12px 0;margin:10px 0}.tt-editor>label{display:flex;flex-direction:column;gap:5px;margin-bottom:10px}.tt-editor .tt-check{flex-direction:row}
    .tt-editor .tt-tools{margin-top:10px}.tt-editor select,.tt-editor input{width:100%}.tt-refs{margin-top:12px;font-size:12px}.tt-refs dl{margin:8px 0}.tt-refs dd{margin:0 0 7px}
    .tt-ref,.tt-refs dd{overflow-wrap:anywhere;font-family:monospace;font-size:11px}.tt-results{margin-top:14px}.tt-subtable{min-width:370px;margin-top:8px}
    .tt-gantt{min-width:0}.tt-gantt-tools{background:var(--ui-surface-muted);padding:6px 8px;border:1px solid var(--ui-border);gap:8px 12px}
    .tt-point-tooltip{position:fixed;z-index:10030;pointer-events:none;max-width:320px;padding:10px 12px;border:1px solid var(--ui-border);border-radius:4px;background:var(--ui-surface);color:var(--ui-text);white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;line-height:1.6}
    .tt-gantt-tools .tt-tabs{gap:12px;border:0}.tt-board{max-height:380px;overflow:auto;border:1px solid var(--ui-border);border-top:0;background:var(--ui-card-bg)}
    .tt-timeline{--tt-label:230px;min-width:720px}.tt-axis,.tt-gantt-row{display:grid;grid-template-columns:var(--tt-label) minmax(0,1fr)}
    .tt-axis{position:sticky;top:0;z-index:5;height:38px;background:var(--ui-surface-muted);border-bottom:1px solid var(--ui-border);font-size:11px}
    .tt-corner{position:sticky;left:0;z-index:6;background:var(--ui-surface-muted);padding:10px;border-right:1px solid var(--ui-border)}
    .tt-ticks{display:flex;justify-content:space-between;align-items:center;padding:0 6px;color:var(--ui-info-muted);gap:6px}.tt-ticks span{white-space:nowrap}
    .tt-group{height:28px;line-height:28px;padding-left:10px;background:var(--ui-surface-muted);color:var(--ui-info-muted);font-size:12px;white-space:nowrap}
    .tt-gantt-row{height:62px;border-bottom:1px solid var(--ui-border)}.tt-task-label{position:sticky;left:0;z-index:3;padding:7px 10px;background:var(--ui-card-bg);border:0;border-right:1px solid var(--ui-border);color:var(--ui-text);text-align:left;overflow:hidden;min-width:0}
    .tt-task-label strong,.tt-task-label small{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:20px;font-size:12px;font-weight:500}.tt-task-label small{color:var(--ui-info-muted)}
    .tt-gantt-row.selected .tt-task-label{background:var(--ui-info-bg);box-shadow:inset 3px 0 var(--ui-primary)}
    .tt-track{position:relative;overflow:hidden;min-width:0;background-image:linear-gradient(to right,var(--ui-border) 1px,transparent 1px);background-size:10% 100%}
    .tt-bar{position:absolute;top:10px;height:24px;min-width:0;padding:0;border:0;border-radius:3px;overflow:hidden;background:var(--wb-gantt-primary-fill);box-shadow:inset 0 0 0 1px var(--wb-gantt-primary-edge)}
    .tt-bar.conflict{background:var(--wb-gantt-critical-fill);box-shadow:inset 0 0 0 1px var(--wb-gantt-critical-edge)}
    .tt-bar.locked{background:var(--wb-gantt-success-fill);box-shadow:inset 0 0 0 1px var(--wb-gantt-success-edge)}
    .tt-bar[aria-pressed=true]{box-shadow:inset 0 0 0 2px var(--wb-gantt-gold)}.tt-baseline{position:absolute;top:44px;height:6px;background:var(--wb-gantt-plan-fill);box-shadow:inset 0 0 0 1px var(--wb-gantt-plan-edge);border-radius:2px;pointer-events:none}
    .tt-legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--ui-info-muted)}.tt-legend span{display:inline-flex;align-items:center;gap:6px}.tt-legend i{display:inline-block;width:20px;height:10px;background:var(--wb-gantt-primary-fill);border:1px solid var(--wb-gantt-primary-edge);border-radius:2px}
    .tt-legend i.baseline{height:6px;background:var(--wb-gantt-plan-fill);border-color:var(--wb-gantt-plan-edge)}.tt-legend i.conflict{background:var(--wb-gantt-critical-fill);border-color:var(--wb-gantt-critical-edge)}
    .tt-expanded{position:fixed;inset:16px;z-index:40;background:var(--ui-card-bg);padding:12px}.tt-expanded .tt-board{max-height:calc(100vh - 225px);height:calc(100vh - 225px)}
    .tt-footer{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:10px 0;margin-top:12px;border-top:1px solid var(--ui-border)}
    .trial-workspace :focus-visible,.trial-modal-body :focus-visible{outline:2px solid var(--ui-primary);outline-offset:2px}
    @media(max-width:1500px){.tt-main{grid-template-columns:minmax(0,1fr) 268px;gap:14px}.tt-timeline{--tt-label:210px}.tt-board{max-height:350px}.tt-directory-scroll{max-height:145px}}
    @media(max-width:1000px){.tt-main{grid-template-columns:minmax(0,1fr)}.tt-detail{border-left:0;border-top:1px solid var(--ui-border);padding:12px 0;position:static;max-height:none}.tt-summary{grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.tt-subtable{min-width:300px}}
  `);
  }
  window.TrialStyles = Styles;
})();
