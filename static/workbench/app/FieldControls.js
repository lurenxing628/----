(function () {
  'use strict';

  const {
    Icon,
    ErrorBox,
    Modal,
    Issues
  } = window.ResourceControls;
  const iconAliases = {
    'arrow-left': 'chevron-left',
    'file-spreadsheet': 'file-input',
    'file-plus': 'plus',
    info: 'history',
    'chevron-up': 'fold-vertical'
  };
  function Button({
    icon,
    ...props
  }) {
    return /*#__PURE__*/React.createElement(window.ResourceControls.Button, {
      ...props,
      icon: iconAliases[icon] || icon
    });
  }
  function Styles() {
    return /*#__PURE__*/React.createElement("style", null, `
    .plana.field-workspace{--text:var(--ui-text);--surface:var(--ui-card-bg);--surface-2:var(--ui-surface-muted);--border:var(--ui-border);--muted:var(--ui-info-muted);--accent:var(--ui-primary);--accent-soft:var(--ui-primary-soft);display:flex;flex-direction:column;min-width:0;max-width:none;padding:0;color:var(--text);background:var(--surface);font-size:13px;letter-spacing:0}
    .field-workspace *{box-sizing:border-box;letter-spacing:0}.field-workspace h2{font-size:18px;margin:0}.field-workspace h3{font-size:15px;margin:0}.field-workspace h4{font-size:12px;margin:0 0 10px;color:var(--muted)}
    .field-toolbar,.field-filters,.field-footer,.field-detail-heading{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:14px 18px;border-bottom:1px solid var(--border)}
    .field-workspace .field-space{flex:1}.field-workspace label{display:flex;flex-direction:column;gap:6px;min-width:0}.field-workspace input,.field-workspace select,.field-workspace textarea{min-width:0;max-width:100%;border:1px solid var(--border);background:var(--surface);color:var(--text);border-radius:4px;padding:7px 9px;font:inherit}
    .field-workspace input,.field-workspace select{height:34px}.field-workspace textarea{resize:vertical;min-height:68px}.field-filters input[type=search]{width:260px}.field-filters label{font-size:12px;color:var(--muted)}
    .field-states{display:flex;gap:4px;flex-wrap:wrap}.field-states button{border:0;border-radius:4px;padding:7px 12px;background:transparent;color:var(--muted);cursor:pointer}.field-states button[aria-pressed=true]{background:var(--accent-soft);color:var(--accent);font-weight:600}
    .field-metrics{display:flex;gap:28px;padding:12px 18px;background:var(--surface-2);border-bottom:1px solid var(--border);flex-wrap:wrap}.field-metrics span{color:var(--muted)}.field-metrics b{margin-left:8px;color:var(--text);font-variant-numeric:tabular-nums}
    .field-scroll{overflow:auto;min-width:0}.field-table{width:100%;border-collapse:collapse;table-layout:fixed}.field-table th{background:var(--surface-2);font-size:12px;color:var(--muted);text-align:left;font-weight:500}.field-table td,.field-table th{padding:11px 12px;border-bottom:1px solid var(--border);overflow-wrap:anywhere;vertical-align:middle}.field-table td{font-variant-numeric:tabular-nums}.field-table small{display:block;color:var(--muted);margin-top:4px}.field-table .field-selected>td{background:var(--accent-soft)}
    .field-workspace .field-link{border:0;background:none;color:var(--accent);padding:0;font:inherit;cursor:pointer;text-align:left}.field-state{display:inline-flex;align-items:center;padding:4px 7px;border-radius:4px;background:var(--surface-2);white-space:nowrap}.field-state.complete{color:var(--ui-success-text);background:var(--ui-success-bg)}.field-state.partial{color:var(--accent);background:var(--accent-soft)}.field-state.exception,.field-state.paused{color:var(--ui-warning-text);background:var(--ui-warning-bg)}
    .field-detail{background:var(--surface);border-left:3px solid var(--accent);padding:0 16px 16px}.field-detail-heading{padding:12px 0}.field-detail .field-table{font-size:12px}.field-note{color:var(--muted);padding:10px 0;overflow-wrap:anywhere}.field-empty{padding:38px 18px;color:var(--muted);text-align:center}.field-error{padding:12px 18px}
    .field-editor{border-top:1px solid var(--border);background:var(--surface-2);padding:18px;margin-top:12px}.field-entry-grid{display:grid;grid-template-columns:minmax(150px,1fr) minmax(320px,2fr) minmax(150px,1fr);gap:20px;margin:16px 0}.field-entry-grid section+section{border-left:1px solid var(--border);padding-left:20px}.field-time-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.field-extra{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}.field-editor details{border-top:1px solid var(--border);padding-top:12px}.field-editor summary{cursor:pointer}.field-editor .field-footer{justify-content:flex-end;padding:14px 0 0;border:0}.field-quantity-tools{display:flex;gap:6px;align-items:center;margin-top:8px}
    .field-workspace .modal-bg{position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;padding:24px}.field-workspace .modal{display:flex;flex-direction:column;width:760px;max-width:100%;max-height:calc(100vh - 48px);background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:8px;box-shadow:0 12px 44px #0003}.field-workspace .modal-head{display:flex;gap:12px;align-items:center;padding:18px;border-bottom:1px solid var(--border)}.field-workspace .modal-h2{font-size:17px;font-weight:600}.field-workspace .modal-b{padding:18px;overflow:auto;min-height:0}.field-workspace .modal-f{display:flex;gap:10px;justify-content:flex-end;padding:16px 18px;border-top:1px solid var(--border)}.field-workspace .modal-x{border:0;background:none;color:inherit;padding:6px;cursor:pointer}.field-files-summary{display:flex;gap:22px;flex-wrap:wrap;padding:16px 0}.field-workspace button:disabled{cursor:not-allowed;opacity:.55}.field-history{padding:12px 18px;background:var(--surface-2);overflow-wrap:anywhere}.field-history dl{display:grid;grid-template-columns:120px minmax(0,1fr);gap:6px}.field-history dd{margin:0}.field-history>div{padding:8px 0;border-top:1px solid var(--border)}
    @media(max-width:900px){.field-entry-grid{grid-template-columns:1fr}.field-entry-grid section+section{border:0;padding:0}.field-time-grid,.field-extra{grid-template-columns:1fr}.field-table{min-width:850px}.field-toolbar{gap:8px}.field-workspace .modal-bg{padding:12px}}
    .field-workspace .modal.lg{width:min(760px,100%)}
    .field-workspace [hidden]{display:none!important}.field-upload{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.field-upload>span{overflow-wrap:anywhere;min-width:0}
    .field-timeline{border-bottom:1px solid var(--border);padding:12px 0;max-height:300px;overflow:auto}.field-timeline-axis{display:flex;justify-content:space-between;margin:0 80px 10px 180px;color:var(--muted);font-size:12px}.field-timeline-row{display:grid;grid-template-columns:170px minmax(100px,1fr) 70px;gap:10px;align-items:center;min-height:32px;font-size:12px}.field-timeline-row>span{overflow-wrap:anywhere}.field-timeline-track{position:relative;height:22px;background:var(--surface-2);border-left:1px solid var(--border);border-right:1px solid var(--border)}.field-timeline-track i{position:absolute;top:5px;height:12px;display:block;min-width:2px}.field-timeline-track .planned{background:var(--ui-info-border)}.field-timeline-track .actual{background:var(--ui-success)}
  `);
  }
  function State({
    value
  }) {
    return /*#__PURE__*/React.createElement("span", {
      className: 'field-state ' + value
    }, window.FieldContract.states[value] || '未读取');
  }
  function Feedback({
    command,
    onDone
  }) {
    return /*#__PURE__*/React.createElement("div", {
      "aria-live": "polite"
    }, /*#__PURE__*/React.createElement(ErrorBox, {
      error: command.error
    }), command.locked && /*#__PURE__*/React.createElement("div", {
      className: "field-note"
    }, command.phase === 'sending' ? '正在保存，请保留当前页面。' : '结果待核实，已保留原请求。', " ", /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: command.phase !== 'pending',
      onClick: command.check
    }, "\u6838\u5B9E\u539F\u8BF7\u6C42")), command.phase === 'done' && /*#__PURE__*/React.createElement("div", {
      className: "field-note"
    }, command.result.result === 'unchanged' ? '内容未变化。' : '已保存。', " ", /*#__PURE__*/React.createElement(Button, {
      icon: "check",
      onClick: onDone
    }, "\u91CD\u8BFB\u5DF2\u786E\u8BA4\u7ED3\u679C")));
  }
  window.FieldControls = {
    Styles,
    Button,
    Icon,
    ErrorBox,
    Modal,
    Issues,
    State,
    Feedback
  };
})();
