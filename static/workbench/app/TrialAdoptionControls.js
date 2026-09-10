(function () {
  'use strict';

  const {
    Button,
    Modal
  } = window.ResourceControls;
  function Scope({
    value,
    label
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dl", {
      className: "ta-scope"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, value.baseline.version === null ? '尚无正式计划' : 'v' + value.baseline.version)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u91C7\u7528\u5B8C\u6574\u8303\u56F4"), /*#__PURE__*/React.createElement("dd", null, "\u5B8C\u6574\u573A\u666F\uFF0C\u5171 ", value.task_count, " \u9053\u5DE5\u5E8F")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u539F\u573A\u666F"), /*#__PURE__*/React.createElement("dd", null, "\u573A\u666F \xB7 ", value.scenario_ref.slice(-8))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u539F\u8349\u7A3F"), /*#__PURE__*/React.createElement("dd", null, "\u8349\u7A3F \xB7 ", value.draft_ref.slice(-8)))), /*#__PURE__*/React.createElement("p", {
      className: "ta-note"
    }, "\u91C7\u7528\u5B8C\u6574\u5DF2\u5B58\u573A\u666F\uFF0C\u4E0D\u9650\u5F53\u524D\u7B5B\u9009\u6216\u663E\u793A\u8303\u56F4\uFF1B\u65B0\u589E\u6B63\u5F0F\u7248\u672C\uFF0C\u4FDD\u7559\u539F\u573A\u666F\u3001\u65E7\u6B63\u5F0F\u8BA1\u5212\u548C\u5DF2\u6709\u6267\u884C\u8BB0\u5F55\u3002"));
  }
  function Fields({
    session: s
  }) {
    const id = React.useId(),
      frozen = !!s.saved;
    return /*#__PURE__*/React.createElement("div", {
      className: "ta-fields"
    }, /*#__PURE__*/React.createElement("div", {
      className: "field"
    }, /*#__PURE__*/React.createElement("label", {
      htmlFor: id + '-reason'
    }, "\u91C7\u7528\u539F\u56E0"), /*#__PURE__*/React.createElement("textarea", {
      id: id + '-reason',
      rows: 3,
      maxLength: 1000,
      value: s.draft.reason,
      readOnly: frozen,
      disabled: s.busy,
      onChange: e => s.change({
        ...s.draft,
        reason: e.target.value
      })
    })), /*#__PURE__*/React.createElement("div", {
      className: "field"
    }, /*#__PURE__*/React.createElement("label", {
      htmlFor: id + '-operator'
    }, "\u58F0\u660E\u4EBA"), /*#__PURE__*/React.createElement("input", {
      id: id + '-operator',
      maxLength: 100,
      value: s.draft.declared_operator,
      readOnly: frozen,
      disabled: s.busy,
      onChange: e => s.change({
        ...s.draft,
        declared_operator: e.target.value
      })
    }), /*#__PURE__*/React.createElement("small", null, "\u4E1A\u52A1\u58F0\u660E\uFF0C\u4E0D\u4EE3\u8868\u767B\u5F55\u6216\u8BA4\u8BC1\u8EAB\u4EFD\u3002")), (!s.saved || s.saved.phase === 'rejected') && /*#__PURE__*/React.createElement("label", {
      className: "ta-consent"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: s.consent,
      disabled: s.busy || s.disabled || !s.preview || !s.preview.validation.can_adopt || !!s.storageError,
      onChange: e => s.setConsent(e.target.checked)
    }), /*#__PURE__*/React.createElement("span", null, "\u6211\u5DF2\u6838\u5BF9\u539F\u573A\u666F\u3001\u539F\u8349\u7A3F\u3001\u6B63\u5F0F\u57FA\u7EBF\u53CA\u5B8C\u6574\u8303\u56F4\uFF0C\u786E\u8BA4\u6B63\u5F0F\u91C7\u7528\u3002")), frozen && /*#__PURE__*/React.createElement("small", null, "\u539F key \u5DF2\u7ED1\u5B9A\u4EE5\u4E0A\u573A\u666F\u53CA\u786E\u8BA4\u5185\u5BB9\uFF0C\u4E0D\u53EF\u4FEE\u6539\u540E\u590D\u7528\u3002"));
  }
  function Records({
    value,
    saved,
    result
  }) {
    return /*#__PURE__*/React.createElement("details", {
      className: "ta-records"
    }, /*#__PURE__*/React.createElement("summary", null, "\u539F\u8EAB\u4EFD\u4E0E\u56DE\u6267\u8BB0\u5F55"), /*#__PURE__*/React.createElement("div", null, "\u539F\u573A\u666F\u7F16\u53F7\uFF1A", value.scenario_ref), value.draft_ref && /*#__PURE__*/React.createElement("div", null, "\u539F\u8349\u7A3F\u7F16\u53F7\uFF1A", value.draft_ref), value.baseline && value.baseline.plan_ref && /*#__PURE__*/React.createElement("div", null, "\u539F\u6B63\u5F0F\u57FA\u7EBF\u7F16\u53F7\uFF1A", value.baseline.plan_ref), saved && /*#__PURE__*/React.createElement("div", null, "\u539F\u8BF7\u6C42\u7F16\u53F7\uFF1A", saved.request_key), result && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, "\u56DE\u6267\u7F16\u53F7\uFF1A", result.receipt_ref), /*#__PURE__*/React.createElement("div", null, "\u65B0\u6B63\u5F0F\u65B9\u6848\u7F16\u53F7\uFF1A", result.data.official_plan.plan_ref)));
  }
  function Dialog({
    session: s,
    scenarioRef,
    onNavigate
  }) {
    const pending = s.saved && s.saved.phase === 'pending',
      rejected = s.saved && s.saved.phase === 'rejected',
      valid = s.preview && s.preview.validation.can_adopt;
    const value = valid ? s.preview : s.saved ? s.saved.preview : s.original || {
      scenario_ref: scenarioRef || '未指定'
    };
    const other = s.saved && s.saved.scenario_ref !== scenarioRef;
    const blocked = s.disabled || !!s.sourceError || !!s.storageError || !!other;
    const canConfirm = valid && s.consent && s.draft.reason.trim() && s.draft.declared_operator.trim() && !pending && !blocked;
    return /*#__PURE__*/React.createElement(Modal, {
      title: s.result ? '场景正式采用回执' : pending ? '核实原场景采用请求' : '确认场景正式采用',
      icon: "check",
      onClose: s.close,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: s.close
      }, pending ? '关闭并保留请求' : s.result ? '关闭' : '取消'), rejected && /*#__PURE__*/React.createElement(Button, {
        disabled: s.busy || !!s.storageError,
        onClick: s.finish
      }, "\u7ED3\u675F\u672C\u6B21\u672A\u91C7\u7528"), s.result ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        busy: s.busy,
        disabled: !!s.storageError,
        onClick: s.lookup
      }, "\u67E5\u8BE2\u539F\u8BF7\u6C42"), /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        disabled: s.busy || !!s.storageError,
        onClick: s.finish
      }, "\u5B8C\u6210\u6838\u5B9E"), /*#__PURE__*/React.createElement(Button, {
        icon: "arrow-right",
        className: "btn primary",
        reason: typeof onNavigate === 'function' ? '' : '正式方案导航尚未接入。',
        onClick: () => onNavigate('analysis', {
          plan_ref: s.result.data.official_plan.plan_ref
        })
      }, "\u8FDB\u5165\u6B63\u5F0F\u65B9\u6848")) : pending ? /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        busy: s.busy,
        disabled: !!s.storageError,
        onClick: s.lookup
      }, "\u67E5\u8BE2\u539F\u8BF7\u6C42") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        busy: s.busy,
        disabled: blocked,
        onClick: s.inspect
      }, "\u91CD\u65B0\u9884\u89C8"), /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        className: "btn primary",
        busy: s.busy,
        disabled: !canConfirm,
        onClick: s.submit
      }, "\u786E\u8BA4\u6B63\u5F0F\u91C7\u7528")))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-body ta-body"
    }, (s.storageError || s.error) && /*#__PURE__*/React.createElement("div", {
      className: "ta-notice",
      role: "alert"
    }, s.storageError || s.error), s.storageError && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: s.busy,
      onClick: s.sync
    }, "\u91CD\u8BFB\u6062\u590D\u8BB0\u5F55"), other && /*#__PURE__*/React.createElement("div", {
      className: "ta-notice",
      role: "status"
    }, "\u539F\u8BF7\u6C42\u5C5E\u4E8E\u53E6\u4E00\u573A\u666F\uFF0C\u8BF7\u5148\u6838\u5B9E\u8BE5\u539F\u8BB0\u5F55\uFF1B\u4E0D\u80FD\u7528\u4E8E\u5F53\u524D\u573A\u666F\u3002"), s.notice && /*#__PURE__*/React.createElement("div", {
      className: "ta-notice",
      role: "status"
    }, s.notice), !pending && !s.result && (s.disabled || s.sourceError) && /*#__PURE__*/React.createElement("div", {
      className: "ta-notice",
      role: "status"
    }, s.sourceError || '原场景正在读取或有待核实操作，新的采用已暂停。'), s.result && /*#__PURE__*/React.createElement("div", {
      className: "ta-result",
      role: "status"
    }, "\u5DF2\u6838\u5B9E\uFF1A\u672C\u6B21\u751F\u6210\u6B63\u5F0F\u7248\u672C v", s.result.data.official_plan.version, "\uFF0C\u5171 ", s.result.data.row_count, " \u9053\u5DE5\u5E8F\u3002", /*#__PURE__*/React.createElement("p", null, "\u8FD9\u662F\u63D0\u4EA4\u65F6\u7684\u56DE\u6267\u7248\u672C\uFF0C\u4E0D\u4EE3\u8868\u5F53\u524D\u6B63\u5F0F\u7248\u672C\u3002\u5F53\u524D\u72B6\u6001\u4EE5\u91CD\u65B0\u6253\u5F00\u7684\u6B63\u5F0F\u65B9\u6848\u4E3A\u51C6\u3002"), s.result.replayed && /*#__PURE__*/React.createElement("p", null, "\u5DF2\u6309\u539F key \u8BFB\u53D6\u539F\u56DE\u6267\uFF0C\u672A\u65B0\u589E\u6B63\u5F0F\u7248\u672C\u3002")), value.baseline && /*#__PURE__*/React.createElement(Scope, {
      value: value,
      label: valid ? '本次预览核对的正式基线' : s.saved ? '原请求核对的正式基线' : '原场景保存时的正式基线'
    }), s.preview && !valid && /*#__PURE__*/React.createElement("div", {
      className: "ta-notice",
      role: "status"
    }, s.preview.validation.issues.map((v, i) => /*#__PURE__*/React.createElement("div", {
      key: i
    }, v.message))), rejected && !s.preview && /*#__PURE__*/React.createElement("p", {
      className: "ta-note"
    }, "\u4E0A\u6B21\u5DF2\u660E\u786E\u62D2\u7EDD\uFF0C\u672A\u6267\u884C\u91C7\u7528\uFF1B\u987B\u91CD\u65B0\u9884\u89C8\u5E76\u518D\u6B21\u52FE\u9009\uFF0C\u4ECD\u4F7F\u7528\u539F key \u4E0E\u539F\u786E\u8BA4\u5185\u5BB9\u3002"), !s.result ? /*#__PURE__*/React.createElement(Fields, {
      session: s
    }) : /*#__PURE__*/React.createElement("dl", {
      className: "ta-scope"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u91C7\u7528\u539F\u56E0"), /*#__PURE__*/React.createElement("dd", null, s.saved.input.reason)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u58F0\u660E\u4EBA"), /*#__PURE__*/React.createElement("dd", null, s.saved.input.declared_operator))), /*#__PURE__*/React.createElement(Records, {
      value: value,
      saved: s.saved,
      result: s.result
    })));
  }
  function Styles() {
    return /*#__PURE__*/React.createElement("style", null, `
      .plana.trial-adoption-action{display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap;max-width:100%;width:auto;padding:0;min-width:0;color:var(--ui-text);letter-spacing:0}
      .trial-adoption-action *{box-sizing:border-box;letter-spacing:0}.trial-adoption-action .modal-bg{z-index:1100}
      .trial-adoption-action .modal.lg{width:760px;max-width:calc(100vw - 48px);max-height:calc(100vh - 48px);display:flex;flex-direction:column;min-width:0;color:var(--ui-text);background:var(--ui-card-bg)}
      .trial-adoption-action .modal-head,.trial-adoption-action .modal-f{flex-shrink:0}.trial-adoption-action .modal-f{gap:8px;padding:14px 20px}
      .trial-adoption-action .ta-body{padding:16px 22px;overflow:auto;min-height:0;max-height:65vh;font-size:13px;line-height:1.7;color:var(--ui-text)}
      .trial-adoption-action .ta-scope{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 20px;padding:12px 0;margin:0;border-bottom:1px solid var(--ui-border)}
      .trial-adoption-action dt,.trial-adoption-action small,.trial-adoption-action .ta-note{color:var(--ui-info-muted);font-size:12px}
      .trial-adoption-action dd{margin:3px 0 0;overflow-wrap:anywhere;color:var(--ui-text)}.trial-adoption-action .ta-fields{display:grid;gap:12px;padding:12px 0}
      .trial-adoption-action .field{min-width:0;margin:0;display:grid;gap:5px}.trial-adoption-action .field label{color:var(--ui-text)}
      .trial-adoption-action .field input,.trial-adoption-action textarea{width:100%;min-width:0;color:var(--ui-text);background:var(--ui-card-bg);font:inherit;border:1px solid var(--ui-border);border-radius:4px;padding:8px 10px}
      .trial-adoption-action textarea{resize:vertical;min-height:84px;max-height:220px}.trial-adoption-action .ta-consent{display:flex;gap:9px;align-items:flex-start;color:var(--ui-text);line-height:1.7}
      .trial-adoption-action .ta-consent input{flex:none;width:16px;height:16px;margin-top:4px;accent-color:var(--ui-info-text)}
      .trial-adoption-action .ta-notice{padding:10px 12px;margin:8px 0;border-left:3px solid var(--ui-warning);background:var(--ui-surface-muted);overflow-wrap:anywhere}
      .trial-adoption-action .ta-records{padding-top:10px;color:var(--ui-info-muted);font-size:12px;overflow-wrap:anywhere}.trial-adoption-action .ta-result{color:var(--ui-success-text);padding:10px 0}
      .trial-adoption-action .ta-result p{color:var(--ui-info-muted);font-size:12px;margin:4px 0}.trial-adoption-action button{white-space:normal;max-width:100%}
      .trial-adoption-action .ta-inline{font-size:12px;color:var(--ui-info-muted);max-width:460px;overflow-wrap:anywhere}
      @media(max-width:600px){.trial-adoption-action .ta-body{padding:12px}.trial-adoption-action .ta-scope{grid-template-columns:1fr}.trial-adoption-action .modal-f{padding:12px}}
    `);
  }
  window.TrialAdoptionControls = {
    Button,
    Dialog,
    Styles
  };
})();
