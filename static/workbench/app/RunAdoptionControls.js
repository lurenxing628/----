(function () {
  'use strict';

  const {
    Button,
    Modal
  } = window.ResourceControls;
  function Scope({
    value,
    saved
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dl", {
      className: "ra-scope"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, saved ? '原请求核对的正式版本' : '当前正式版本（本次预览）'), /*#__PURE__*/React.createElement("dd", null, value.baseline.version === null ? '尚无正式计划' : 'v' + value.baseline.version)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u76EE\u6807\u5019\u9009"), /*#__PURE__*/React.createElement("dd", null, "\u5019\u9009 \xB7 ", value.candidate_ref.slice(-8))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u91C7\u7528\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("dd", null, value.task_count, " \u9053")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u91C7\u7528\u8303\u56F4"), /*#__PURE__*/React.createElement("dd", null, "\u5B8C\u6574\u5019\u9009\u53CA\u5168\u90E8\u5F53\u524D\u6B63\u5F0F\u5B89\u6392"))), /*#__PURE__*/React.createElement("p", {
      className: "ra-note"
    }, "\u91C7\u7528\u4F1A\u65B0\u589E\u6B63\u5F0F\u7248\u672C\uFF0C\u4FDD\u7559\u65E7\u7248\u672C\u548C\u5DF2\u6709\u6267\u884C\u8BB0\u5F55\uFF1B\u4E0D\u662F\u53EA\u91C7\u7528\u5F53\u524D\u7B5B\u9009\u51FA\u7684\u5DE5\u5E8F\u3002"));
  }
  function Records({
    value,
    intent,
    result
  }) {
    return /*#__PURE__*/React.createElement("details", {
      className: "ra-records"
    }, /*#__PURE__*/React.createElement("summary", null, "\u8BB0\u5F55\u4FE1\u606F"), /*#__PURE__*/React.createElement("div", null, "\u5019\u9009\u7F16\u53F7\uFF1A", value.candidate_ref), value.run_ref && /*#__PURE__*/React.createElement("div", null, "\u8FD0\u884C\u7F16\u53F7\uFF1A", value.run_ref), value.baseline && value.baseline.plan_ref && /*#__PURE__*/React.createElement("div", null, "\u539F\u6B63\u5F0F\u65B9\u6848\u7F16\u53F7\uFF1A", value.baseline.plan_ref), intent && /*#__PURE__*/React.createElement("div", null, "\u8BF7\u6C42\u7F16\u53F7\uFF1A", intent.request_key), result && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, "\u56DE\u6267\u7F16\u53F7\uFF1A", result.receipt_ref), /*#__PURE__*/React.createElement("div", null, "\u65B0\u6B63\u5F0F\u65B9\u6848\u7F16\u53F7\uFF1A", result.data.official_plan.plan_ref)));
  }
  function Fields({
    draft,
    onChange,
    consent,
    onConsent,
    readOnly,
    busy
  }) {
    const id = React.useId();
    return /*#__PURE__*/React.createElement("div", {
      className: "ra-fields"
    }, /*#__PURE__*/React.createElement("div", {
      className: "field"
    }, /*#__PURE__*/React.createElement("label", {
      htmlFor: id + '-reason'
    }, "\u91C7\u7528\u539F\u56E0"), /*#__PURE__*/React.createElement("textarea", {
      id: id + '-reason',
      rows: 3,
      maxLength: 1000,
      value: draft.reason,
      readOnly: readOnly,
      disabled: busy,
      onChange: e => onChange({
        ...draft,
        reason: e.target.value
      })
    })), /*#__PURE__*/React.createElement("div", {
      className: "field"
    }, /*#__PURE__*/React.createElement("label", {
      htmlFor: id + '-operator'
    }, "\u58F0\u660E\u4EBA"), /*#__PURE__*/React.createElement("input", {
      id: id + '-operator',
      maxLength: 100,
      value: draft.declared_operator,
      readOnly: readOnly,
      disabled: busy,
      onChange: e => onChange({
        ...draft,
        declared_operator: e.target.value
      })
    }), /*#__PURE__*/React.createElement("small", null, "\u8BB0\u5F55\u672C\u6B21\u4E1A\u52A1\u58F0\u660E\uFF0C\u4E0D\u4EE3\u8868\u767B\u5F55\u6216\u8BA4\u8BC1\u8EAB\u4EFD\u3002")), !readOnly && /*#__PURE__*/React.createElement("label", {
      className: "ra-consent"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: consent,
      disabled: busy,
      onChange: e => onConsent(e.target.checked)
    }), /*#__PURE__*/React.createElement("span", null, "\u6211\u5DF2\u6838\u5BF9\u6B63\u5F0F\u7248\u672C\u3001\u76EE\u6807\u5019\u9009\u548C\u5B8C\u6574\u8303\u56F4\uFF0C\u786E\u8BA4\u6B63\u5F0F\u91C7\u7528\u3002")));
  }
  function Dialog({
    value,
    intent,
    result,
    preview,
    draft,
    consent,
    busy,
    error,
    storageError,
    notice,
    onReadStorage,
    onChange,
    onConsent,
    onClose,
    onPreview,
    onConfirm,
    onLookup,
    onFinish,
    onCancelRejected,
    onNavigate
  }) {
    const pending = intent && intent.phase === 'pending' && !result,
      valid = preview && preview.validation.can_adopt === true;
    const canConfirm = valid && consent && draft.reason.trim() && draft.declared_operator.trim() && !pending && !storageError;
    return /*#__PURE__*/React.createElement(Modal, {
      title: result ? '正式采用回执' : pending ? '核实原采用请求' : '确认正式采用',
      icon: "check",
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: onClose
      }, pending ? '关闭并保留请求' : result ? '关闭' : '取消'), intent && intent.phase === 'rejected' && /*#__PURE__*/React.createElement(Button, {
        disabled: busy || !!storageError,
        onClick: onCancelRejected
      }, "\u7ED3\u675F\u672C\u6B21\u672A\u91C7\u7528"), result ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        onClick: onFinish
      }, "\u5B8C\u6210\u6838\u5B9E"), /*#__PURE__*/React.createElement(Button, {
        icon: "arrow-right",
        className: "btn primary",
        reason: typeof onNavigate === 'function' ? '' : '正式方案页面尚未接入。',
        onClick: () => onNavigate('analysis', {
          plan_ref: result.data.official_plan.plan_ref
        })
      }, "\u8FDB\u5165\u6B63\u5F0F\u65B9\u6848")) : pending ? /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        busy: busy,
        onClick: onLookup
      }, "\u67E5\u8BE2\u539F\u8BF7\u6C42") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        busy: busy,
        disabled: !!storageError,
        onClick: onPreview
      }, "\u91CD\u65B0\u9884\u89C8"), /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        className: "btn primary",
        busy: busy,
        disabled: !canConfirm,
        onClick: onConfirm
      }, "\u786E\u8BA4\u6B63\u5F0F\u91C7\u7528")))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-body ra-body"
    }, error && /*#__PURE__*/React.createElement("div", {
      className: "ra-notice",
      role: "alert"
    }, error), notice && /*#__PURE__*/React.createElement("div", {
      className: "ra-notice",
      role: "status"
    }, notice), storageError && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: busy,
      onClick: onReadStorage
    }, "\u91CD\u8BFB\u6062\u590D\u8BB0\u5F55"), result && /*#__PURE__*/React.createElement("div", {
      className: "ra-result",
      role: "status"
    }, "\u5DF2\u6838\u5B9E\uFF1A\u672C\u6B21\u751F\u6210\u6B63\u5F0F\u7248\u672C v", result.data.official_plan.version, "\uFF0C\u5171 ", result.data.row_count, " \u9053\u5DE5\u5E8F\u3002", /*#__PURE__*/React.createElement("p", null, "\u8FD9\u662F\u63D0\u4EA4\u65F6\u7684\u56DE\u6267\uFF1B\u5F53\u524D\u6B63\u5F0F\u72B6\u6001\u4EE5\u91CD\u65B0\u6253\u5F00\u7684\u6B63\u5F0F\u65B9\u6848\u4E3A\u51C6\u3002")), value.baseline && /*#__PURE__*/React.createElement(Scope, {
      value: value,
      saved: !!intent && !valid
    }), preview && !valid && /*#__PURE__*/React.createElement("div", {
      className: "ra-notice",
      role: "status"
    }, preview.validation.issues.map((item, index) => /*#__PURE__*/React.createElement("div", {
      key: index
    }, item.message))), !result && /*#__PURE__*/React.createElement(Fields, {
      draft: draft,
      onChange: onChange,
      consent: consent,
      onConsent: onConsent,
      readOnly: !!pending,
      busy: busy
    }), result && /*#__PURE__*/React.createElement("dl", {
      className: "ra-scope"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u91C7\u7528\u539F\u56E0"), /*#__PURE__*/React.createElement("dd", null, draft.reason)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u58F0\u660E\u4EBA"), /*#__PURE__*/React.createElement("dd", null, draft.declared_operator))), /*#__PURE__*/React.createElement(Records, {
      value: value,
      intent: intent,
      result: result
    })));
  }
  function Styles() {
    return /*#__PURE__*/React.createElement("style", null, `
      .plana.run-adoption-action{display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap;max-width:100%;width:auto;padding:0;min-width:0;color:var(--ui-text);letter-spacing:0}
      .run-adoption-action .modal-bg{z-index:1100}
      .run-adoption-action .modal.lg{width:760px;max-width:calc(100vw - 48px);max-height:calc(100vh - 48px);display:flex;flex-direction:column;min-width:0;color:var(--ui-text);background:var(--ui-card-bg)}
      .run-adoption-action .modal-head,.run-adoption-action .modal-f{flex-shrink:0}
      .run-adoption-action .modal-f{gap:8px;padding:14px 20px}
      .run-adoption-action .ra-body{padding:16px 22px;overflow:auto;min-height:0;max-height:65vh;font-size:13px;line-height:1.7;color:var(--ui-text)}
      .run-adoption-action *{box-sizing:border-box;letter-spacing:0}
      .run-adoption-action .ra-scope{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 20px;padding:12px 0;margin:0;border-bottom:1px solid var(--ui-border)}
      .run-adoption-action dt,.run-adoption-action small,.run-adoption-action .ra-note{color:var(--ui-info-muted);font-size:12px}
      .run-adoption-action dd{margin:3px 0 0;overflow-wrap:anywhere;color:var(--ui-text)}
      .run-adoption-action .ra-fields{display:grid;gap:12px;padding:12px 0}
      .run-adoption-action .field{min-width:0;margin:0;display:grid;gap:5px}
      .run-adoption-action .field label{color:var(--ui-text)}
      .run-adoption-action .field input,.run-adoption-action textarea{width:100%;min-width:0;color:var(--ui-text);background:var(--ui-card-bg);font:inherit;border:1px solid var(--ui-border);border-radius:4px;padding:8px 10px}
      .run-adoption-action textarea{resize:vertical;min-height:84px;max-height:220px}
      .run-adoption-action .ra-consent{display:flex;gap:9px;align-items:flex-start;color:var(--ui-text);line-height:1.7}
      .run-adoption-action .ra-consent input{flex:none;width:16px;height:16px;margin-top:4px;accent-color:var(--ui-info-text)}
      .run-adoption-action .ra-notice{padding:10px 12px;margin:8px 0;border-left:3px solid var(--ui-warning);background:var(--ui-surface-muted);overflow-wrap:anywhere}
      .run-adoption-action .ra-records{padding-top:10px;color:var(--ui-info-muted);font-size:12px;overflow-wrap:anywhere}
      .run-adoption-action .ra-result{color:var(--ui-success-text);padding:10px 0}.run-adoption-action .ra-result p{color:var(--ui-info-muted);font-size:12px;margin:4px 0}
      .run-adoption-action button{white-space:normal;max-width:100%}.run-adoption-action .ra-inline{font-size:12px;color:var(--ui-info-muted);max-width:480px;overflow-wrap:anywhere}
      @media(max-width:600px){.run-adoption-action .ra-body{padding:12px}.run-adoption-action .ra-scope{grid-template-columns:1fr}.run-adoption-action .modal-f{padding:12px}}
    `);
  }
  window.RunAdoptionControls = {
    Button,
    Dialog,
    Styles
  };
})();
