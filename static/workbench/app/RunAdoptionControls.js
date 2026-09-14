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
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, saved ? '上次提交时核对的正式计划' : '当前正式计划（本次预检）'), /*#__PURE__*/React.createElement("dd", null, value.baseline.version === null ? '尚无正式计划' : 'v' + value.baseline.version)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u76EE\u6807\u5019\u9009\u65B9\u6848"), /*#__PURE__*/React.createElement("dd", null, "\u5F53\u524D\u6838\u5BF9\u7684\u5B8C\u6574\u5019\u9009\u65B9\u6848", /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      value: value.candidate_ref
    }))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u91C7\u7528\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("dd", null, value.task_count, " \u9053")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u91C7\u7528\u8303\u56F4"), /*#__PURE__*/React.createElement("dd", null, "\u5B8C\u6574\u5019\u9009\u65B9\u6848\u53CA\u5168\u90E8\u5F53\u524D\u6B63\u5F0F\u5B89\u6392"))), /*#__PURE__*/React.createElement("p", {
      className: "ra-note"
    }, "\u91C7\u7528\u4F1A\u65B0\u589E\u4E00\u7248\u6B63\u5F0F\u8BA1\u5212\uFF1B\u4E0D\u662F\u53EA\u91C7\u7528\u5F53\u524D\u7B5B\u9009\u51FA\u7684\u5DE5\u5E8F\u3002\u65E7\u7248\u672C\u548C\u62A5\u5DE5\u8BB0\u5F55\u90FD\u4F1A\u4FDD\u7559\uFF0C\u53EF\u5728\u8BA1\u5212\u5217\u8868\u67E5\u770B\u548C\u5BFC\u51FA\uFF1B\u5982\u9700\u6062\u590D\u65E7\u5B89\u6392\uFF0C\u9700\u8981\u91CD\u65B0\u6392\u4EA7\u5E76\u518D\u91C7\u7528\u4E00\u7248\u3002"));
  }
  function Records({
    value,
    intent,
    result
  }) {
    return /*#__PURE__*/React.createElement("details", {
      className: "ra-records wb-ref"
    }, /*#__PURE__*/React.createElement("summary", null, "\u7F16\u53F7"), /*#__PURE__*/React.createElement("div", null, "\u5019\u9009\u65B9\u6848\u7F16\u53F7\uFF1A", value.candidate_ref), value.run_ref && /*#__PURE__*/React.createElement("div", null, "\u6392\u4EA7\u7F16\u53F7\uFF1A", value.run_ref), value.baseline && value.baseline.plan_ref && /*#__PURE__*/React.createElement("div", null, "\u539F\u6B63\u5F0F\u8BA1\u5212\u7F16\u53F7\uFF1A", value.baseline.plan_ref), intent && /*#__PURE__*/React.createElement("div", null, "\u64CD\u4F5C\u7F16\u53F7\uFF1A", intent.request_key), result && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, "\u7ED3\u679C\u7F16\u53F7\uFF1A", result.receipt_ref), /*#__PURE__*/React.createElement("div", null, "\u65B0\u6B63\u5F0F\u8BA1\u5212\u7F16\u53F7\uFF1A", result.data.official_plan.plan_ref)));
  }
  function Fields({
    draft,
    onChange,
    consent,
    onConsent,
    readOnly,
    busy
  }) {
    const id = React.useId(),
      memoryHint = window.WorkbenchHandlerMemory.hint(draft.declared_operator);
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
    }, window.WorkbenchTerms.handler), /*#__PURE__*/React.createElement("input", {
      id: id + '-operator',
      maxLength: 100,
      value: draft.declared_operator,
      readOnly: readOnly,
      disabled: busy,
      onChange: e => onChange({
        ...draft,
        declared_operator: e.target.value
      })
    }), /*#__PURE__*/React.createElement("small", null, "\u586B\u5199\u8FD9\u6B21\u7531\u8C01\u7ECF\u529E\uFF0C\u4E0D\u662F\u767B\u5F55\u8D26\u53F7\u3002", !readOnly && memoryHint && ' ' + memoryHint)), !readOnly && /*#__PURE__*/React.createElement("label", {
      className: "ra-consent"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: consent,
      disabled: busy,
      onChange: e => onConsent(e.target.checked)
    }), /*#__PURE__*/React.createElement("span", null, "\u6211\u5DF2\u6838\u5BF9\u6B63\u5F0F\u8BA1\u5212\u3001\u76EE\u6807\u5019\u9009\u65B9\u6848\u548C\u5B8C\u6574\u8303\u56F4\uFF0C\u786E\u8BA4\u6B63\u5F0F\u91C7\u7528\u3002")));
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
      title: result ? '正式采用结果' : pending ? '查询上次采用结果' : '确认正式采用',
      icon: "check",
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: onClose
      }, pending ? '关闭并保留上次操作' : result ? '关闭' : '取消'), intent && intent.phase === 'rejected' && /*#__PURE__*/React.createElement(Button, {
        disabled: busy || !!storageError,
        onClick: onCancelRejected
      }, "\u7ED3\u675F\u672C\u6B21\u672A\u91C7\u7528"), result ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        onClick: onFinish
      }, "\u5B8C\u6210"), /*#__PURE__*/React.createElement(Button, {
        icon: "arrow-right",
        className: "btn primary",
        reason: typeof onNavigate === 'function' ? '' : window.WorkbenchTerms.outcomes.unavailable,
        onClick: () => onNavigate('analysis', {
          plan_ref: result.data.official_plan.plan_ref
        })
      }, "\u8FDB\u5165\u6B63\u5F0F\u8BA1\u5212")) : pending ? /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        busy: busy,
        onClick: onLookup
      }, window.WorkbenchTerms.actions.query_result) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        busy: busy,
        disabled: !!storageError,
        onClick: onPreview
      }, "\u91CD\u65B0\u9884\u68C0"), /*#__PURE__*/React.createElement(Button, {
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
    }, "\u5237\u65B0\u4E0A\u6B21\u64CD\u4F5C\u8BB0\u5F55"), result && /*#__PURE__*/React.createElement("div", {
      className: "ra-result",
      role: "status"
    }, "\u5DF2\u786E\u8BA4\uFF1A\u672C\u6B21\u751F\u6210\u7B2C ", result.data.official_plan.version, " \u7248\u6B63\u5F0F\u8BA1\u5212\uFF0C\u5171 ", result.data.row_count, " \u9053\u5DE5\u5E8F\u3002", /*#__PURE__*/React.createElement("p", null, "\u8FD9\u662F\u63D0\u4EA4\u65F6\u7684\u7ED3\u679C\uFF1B\u5F53\u524D\u72B6\u6001\u8BF7\u91CD\u65B0\u6253\u5F00\u6B63\u5F0F\u8BA1\u5212\u6838\u5BF9\u3002")), value.baseline && /*#__PURE__*/React.createElement(Scope, {
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
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u91C7\u7528\u539F\u56E0"), /*#__PURE__*/React.createElement("dd", null, draft.reason)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, window.WorkbenchTerms.handler), /*#__PURE__*/React.createElement("dd", null, draft.declared_operator))), /*#__PURE__*/React.createElement(Records, {
      value: value,
      intent: intent,
      result: result
    })));
  }
  function Styles() {
    return null;
  }
  window.RunAdoptionControls = {
    Button,
    Dialog,
    Styles
  };
})();
