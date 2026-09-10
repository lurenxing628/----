(function () {
  'use strict';
  function Styles() { return <style>{`
    .outsourcing-live {width:100%;min-width:0;color:var(--ui-text);font:13px/1.55 var(--font-family);letter-spacing:0;}
    .outsourcing-live * {box-sizing:border-box;letter-spacing:0;}
    .outsourcing-live h3,.outsourcing-live h4,.outsourcing-live p {margin:0;} .outsourcing-live h3 {font-size:16px;} .outsourcing-live h4 {font-size:14px;}
    .outsourcing-live button,.outsourcing-live input,.outsourcing-live select,.outsourcing-live textarea {font:inherit;}
    .outsourcing-live .os-heading,.outsourcing-live .os-tools,.outsourcing-live .os-pager,.outsourcing-live .os-modes {display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
    .outsourcing-live .os-heading {justify-content:space-between;margin-bottom:10px;}
    .outsourcing-live .os-muted {color:var(--ui-info-muted);font-size:12px;overflow-wrap:anywhere;}
    .outsourcing-live .os-scroll {max-width:100%;overflow:auto;}
    .outsourcing-live table {width:100%;border-collapse:collapse;text-align:left;table-layout:fixed;font-size:13px;}
    .outsourcing-live th,.outsourcing-live td {border-bottom:1px solid var(--ui-border);padding:10px 8px;vertical-align:top;overflow-wrap:anywhere;}
    .outsourcing-live th {background:var(--ui-surface-muted);color:var(--ui-info-muted);font-weight:500;}
    .outsourcing-live .os-table {min-width:680px;} .outsourcing-live .os-table th:first-child {width:24%;} .outsourcing-live .os-table th:last-child {width:88px;}
    .outsourcing-live tr[data-selected=true] {background:var(--ui-primary-soft);}
    .outsourcing-live .os-note {padding:10px 12px;margin:10px 0;background:var(--ui-surface-muted);overflow-wrap:anywhere;}
    .outsourcing-live .os-note.warning,.outsourcing-live .os-state.warning {color:var(--ui-warning-text);background:var(--ui-warning-bg);}
    .outsourcing-live .os-note.success,.outsourcing-live .os-state.success {color:var(--ui-success-text);background:var(--ui-success-bg);}
    .outsourcing-live .os-state {display:inline-block;color:var(--ui-info-text);background:var(--ui-primary-soft);padding:2px 6px;border-radius:var(--wb-radius-control);}
    .outsourcing-live .os-state.danger {color:var(--ui-danger-text);background:var(--ui-danger-bg);}
    .outsourcing-live .os-empty {padding:24px 8px;color:var(--ui-info-muted);}
    .outsourcing-live .os-pager {justify-content:flex-end;padding:10px 0;} .outsourcing-live .os-pager label {display:flex;align-items:center;gap:6px;}
    .outsourcing-live .os-pager select {width:72px;}
    .outsourcing-live .os-detail {border-top:1px solid var(--ui-border);margin-top:18px;padding-top:16px;}
    .outsourcing-live .os-members,.outsourcing-live .os-selected {display:flex;gap:8px;flex-wrap:wrap;overflow-wrap:anywhere;}
    .outsourcing-live .os-members>span {padding-right:12px;border-right:1px solid var(--ui-border);}
    .outsourcing-live .os-selected {margin:10px 0;align-items:center;}.outsourcing-live .os-selected>span {display:inline-flex;align-items:center;gap:5px;}
    .outsourcing-live .os-target {padding:10px 0;}
    .outsourcing-live .os-facts {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 22px;margin:12px 0;}
    .outsourcing-live .os-facts>div {display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid var(--ui-border);padding-bottom:7px;min-width:0;}
    .outsourcing-live dt {color:var(--ui-info-muted);flex-shrink:0;}.outsourcing-live dd {margin:0;min-width:0;max-width:75%;overflow-wrap:anywhere;white-space:pre-wrap;}
    .outsourcing-live dd del {display:block;color:var(--ui-info-muted);}
    .outsourcing-live .os-history {border-bottom:1px solid var(--ui-border);padding:10px 0;}
    .outsourcing-live summary {cursor:pointer;color:var(--ui-info-text);overflow-wrap:anywhere;}
    .outsourcing-live .os-form {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:16px;}
    .outsourcing-live .os-form label {display:flex;flex-direction:column;gap:5px;min-width:0;}.outsourcing-live .os-form .wide {grid-column:1/-1;}
    .outsourcing-live input,.outsourcing-live select,.outsourcing-live textarea {color:var(--ui-text);background:var(--ui-card-bg);border:1px solid var(--ui-border);border-radius:var(--wb-radius-control);min-width:0;max-width:100%;padding:6px 9px;}
    .outsourcing-live input,.outsourcing-live select {height:34px;}.outsourcing-live textarea {min-height:76px;resize:vertical;}
    .outsourcing-live input[type=radio],.outsourcing-live input[type=checkbox] {height:16px;width:16px;padding:0;flex:none;vertical-align:middle;}
    .outsourcing-live .os-modes label {display:flex;align-items:center;gap:6px;cursor:pointer;}.outsourcing-live .os-clear {display:flex;align-items:flex-end;}
    .outsourcing-live .os-pick-scroll {max-height:248px;}.outsourcing-live .os-pick-table {min-width:570px;}.outsourcing-live .os-pick-table th:first-child {width:52px;}.outsourcing-live .os-pick-table th:last-child {width:145px;}
    .outsourcing-live .modal {display:flex;flex-direction:column;width:850px;max-width:calc(100vw - 32px);max-height:calc(100vh - 32px);color:var(--ui-text);background:var(--ui-card-bg);}
    .outsourcing-live .modal-head {flex:none;background:var(--ui-surface-soft);}.outsourcing-live .modal-f {flex:none;background:var(--ui-surface-muted);}
    .outsourcing-live .os-dialog-body {padding:18px 22px;overflow-y:auto;min-height:0;}
    .outsourcing-live :focus-visible {outline:2px solid var(--ui-primary);outline-offset:2px;}
    @media(max-width:650px) {.outsourcing-live .os-form,.outsourcing-live .os-facts {grid-template-columns:minmax(0,1fr);}.outsourcing-live .os-dialog-body {padding:12px;}}
  `}</style>; }
  window.OutsourcingStyles = Styles;
})();
