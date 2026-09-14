(function () {
  'use strict';

  const {
    Button,
    Modal
  } = window.ResourceControls;
  function Scope({
    value,
    label,
    name
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dl", {
      className: "ta-scope"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, value.baseline.version === null ? '尚无正式计划' : '第 ' + value.baseline.version + ' 版')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u91C7\u7528\u5B8C\u6574\u8303\u56F4"), /*#__PURE__*/React.createElement("dd", null, "\u5B8C\u6574\u8BD5\u8C03\u65B9\u6848\uFF0C\u5171 ", value.task_count, " \u9053\u5DE5\u5E8F")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u8BD5\u8C03\u65B9\u6848"), /*#__PURE__*/React.createElement("dd", null, name || '未命名试调方案'))), /*#__PURE__*/React.createElement("p", {
      className: "ta-note"
    }, "\u91C7\u7528\u5B8C\u6574\u7684\u8BD5\u8C03\u65B9\u6848\uFF0C\u4E0D\u53D7\u5F53\u524D\u7B5B\u9009\u6216\u663E\u793A\u8303\u56F4\u5F71\u54CD\uFF1B\u4F1A\u65B0\u589E\u4E00\u7248\u6B63\u5F0F\u8BA1\u5212\u3002\u65E7\u7248\u672C\u548C\u62A5\u5DE5\u8BB0\u5F55\u90FD\u4F1A\u4FDD\u7559\uFF0C\u53EF\u5728\u8BA1\u5212\u5217\u8868\u67E5\u770B\u548C\u5BFC\u51FA\uFF1B\u5982\u9700\u6062\u590D\u65E7\u5B89\u6392\uFF0C\u9700\u8981\u91CD\u65B0\u6392\u4EA7\u5E76\u518D\u91C7\u7528\u4E00\u7248\u3002"));
  }
  function Fields({
    session: s
  }) {
    const id = React.useId(),
      frozen = !!s.saved,
      memoryHint = window.WorkbenchHandlerMemory.hint(s.draft.declared_operator);
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
    }, window.WorkbenchTerms.handler), /*#__PURE__*/React.createElement("input", {
      id: id + '-operator',
      maxLength: 100,
      value: s.draft.declared_operator,
      readOnly: frozen,
      disabled: s.busy,
      onChange: e => s.change({
        ...s.draft,
        declared_operator: e.target.value
      })
    }), /*#__PURE__*/React.createElement("small", null, "\u586B\u5199\u8FD9\u6B21\u7531\u8C01\u7ECF\u529E\uFF0C\u4E0D\u662F\u767B\u5F55\u8D26\u53F7\u3002", !frozen && memoryHint && ' ' + memoryHint)), (!s.saved || s.saved.phase === 'rejected') && /*#__PURE__*/React.createElement("label", {
      className: "ta-consent"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: s.consent,
      disabled: s.busy || s.disabled || !s.preview || !s.preview.validation.can_adopt || !!s.storageError,
      onChange: e => s.setConsent(e.target.checked)
    }), /*#__PURE__*/React.createElement("span", null, "\u6211\u5DF2\u6838\u5BF9\u8BD5\u8C03\u65B9\u6848\u3001\u8BD5\u8C03\u8349\u7A3F\u3001\u6B63\u5F0F\u8BA1\u5212\u548C\u5B8C\u6574\u8303\u56F4\uFF0C\u786E\u8BA4\u6B63\u5F0F\u91C7\u7528\u3002")), frozen && /*#__PURE__*/React.createElement("small", null, "\u8FD9\u6B21\u63D0\u4EA4\u5DF2\u7ED1\u5B9A\u4E0A\u9762\u7684\u8BD5\u8C03\u65B9\u6848\u548C\u786E\u8BA4\u5185\u5BB9\uFF0C\u6539\u52A8\u540E\u4E0D\u80FD\u6CBF\u7528\u3002"));
  }
  function Records({
    value,
    saved,
    result
  }) {
    return /*#__PURE__*/React.createElement("details", {
      className: "ta-records wb-ref"
    }, /*#__PURE__*/React.createElement("summary", null, "\u7F16\u53F7\u4E0E\u4FDD\u5B58\u8BB0\u5F55"), /*#__PURE__*/React.createElement("div", null, "\u8BD5\u8C03\u65B9\u6848\u7F16\u53F7\uFF1A", value.scenario_ref), value.draft_ref && /*#__PURE__*/React.createElement("div", null, "\u8BD5\u8C03\u8349\u7A3F\u7F16\u53F7\uFF1A", value.draft_ref), value.baseline && value.baseline.plan_ref && /*#__PURE__*/React.createElement("div", null, "\u5F53\u65F6\u7684\u6B63\u5F0F\u8BA1\u5212\u7F16\u53F7\uFF1A", value.baseline.plan_ref), saved && /*#__PURE__*/React.createElement("div", null, "\u64CD\u4F5C\u7F16\u53F7\uFF1A", saved.request_key), result && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, "\u7ED3\u679C\u7F16\u53F7\uFF1A", result.receipt_ref), /*#__PURE__*/React.createElement("div", null, "\u65B0\u6B63\u5F0F\u8BA1\u5212\u7F16\u53F7\uFF1A", result.data.official_plan.plan_ref)));
  }
  function Dialog({
    session: s,
    scenarioRef,
    onNavigate,
    name
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
      title: s.result ? '试调方案采用结果' : pending ? '查询上次采用结果' : '确认正式采用试调方案',
      icon: "check",
      onClose: s.close,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: s.close
      }, pending ? '关闭并保留这次操作' : s.result ? '关闭' : '取消'), rejected && /*#__PURE__*/React.createElement(Button, {
        disabled: s.busy || !!s.storageError,
        onClick: s.finish
      }, "\u7ED3\u675F\u672C\u6B21\u672A\u91C7\u7528"), s.result ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        busy: s.busy,
        disabled: !!s.storageError,
        onClick: s.lookup
      }, "\u67E5\u8BE2\u7ED3\u679C"), /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        disabled: s.busy || !!s.storageError,
        onClick: s.finish
      }, "\u5B8C\u6210"), /*#__PURE__*/React.createElement(Button, {
        icon: "arrow-right",
        className: "btn primary",
        reason: typeof onNavigate === 'function' ? '' : window.WorkbenchTerms.outcomes.unavailable,
        onClick: () => onNavigate('analysis', {
          plan_ref: s.result.data.official_plan.plan_ref
        })
      }, "\u8FDB\u5165\u6B63\u5F0F\u8BA1\u5212")) : pending ? /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        busy: s.busy,
        disabled: !!s.storageError,
        onClick: s.lookup
      }, "\u67E5\u8BE2\u7ED3\u679C") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        busy: s.busy,
        disabled: blocked,
        onClick: s.inspect
      }, "\u91CD\u65B0\u9884\u68C0"), /*#__PURE__*/React.createElement(Button, {
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
    }, "\u5237\u65B0\u4E0A\u6B21\u64CD\u4F5C\u8BB0\u5F55"), other && /*#__PURE__*/React.createElement("div", {
      className: "ta-notice",
      role: "status"
    }, "\u4E0A\u6B21\u64CD\u4F5C\u5C5E\u4E8E\u53E6\u4E00\u4E2A\u8BD5\u8C03\u65B9\u6848\uFF0C\u8BF7\u5148\u67E5\u8BE2\u90A3\u6761\u8BB0\u5F55\u7684\u7ED3\u679C\uFF1B\u4E0D\u80FD\u7528\u5728\u5F53\u524D\u8BD5\u8C03\u65B9\u6848\u4E0A\u3002"), s.notice && /*#__PURE__*/React.createElement("div", {
      className: "ta-notice",
      role: "status"
    }, s.notice), !pending && !s.result && (s.disabled || s.sourceError) && /*#__PURE__*/React.createElement("div", {
      className: "ta-notice",
      role: "status"
    }, s.sourceError || '试调方案正在读取，或还有操作没确认结果，暂时不能开始采用。'), s.result && /*#__PURE__*/React.createElement("div", {
      className: "ta-result",
      role: "status"
    }, "\u5DF2\u786E\u8BA4\uFF1A\u8FD9\u6B21\u751F\u6210\u6B63\u5F0F\u8BA1\u5212\u7B2C ", s.result.data.official_plan.version, " \u7248\uFF0C\u5171 ", s.result.data.row_count, " \u9053\u5DE5\u5E8F\u3002", /*#__PURE__*/React.createElement("p", null, "\u8FD9\u662F\u63D0\u4EA4\u65F6\u7684\u7ED3\u679C\uFF0C\u4E0D\u4EE3\u8868\u73B0\u5728\u7684\u6B63\u5F0F\u8BA1\u5212\u3002\u6700\u65B0\u60C5\u51B5\u8BF7\u91CD\u65B0\u6253\u5F00\u6B63\u5F0F\u8BA1\u5212\u67E5\u770B\u3002"), s.result.replayed && /*#__PURE__*/React.createElement("p", null, "\u6309\u540C\u4E00\u4E2A\u64CD\u4F5C\u7F16\u53F7\u8BFB\u5230\u7684\u662F\u4E0A\u6B21\u7684\u7ED3\u679C\uFF0C\u6CA1\u6709\u65B0\u589E\u6B63\u5F0F\u8BA1\u5212\u7248\u672C\u3002")), value.baseline && /*#__PURE__*/React.createElement(Scope, {
      value: value,
      name: name,
      label: valid ? '这次预检核对的正式计划' : s.saved ? '上次提交核对的正式计划' : '试调方案保存时的正式计划'
    }), s.preview && !valid && /*#__PURE__*/React.createElement("div", {
      className: "ta-notice",
      role: "status"
    }, s.preview.validation.issues.map((v, i) => /*#__PURE__*/React.createElement("div", {
      key: i
    }, v.message))), rejected && !s.preview && /*#__PURE__*/React.createElement("p", {
      className: "ta-note"
    }, "\u4E0A\u6B21\u63D0\u4EA4\u88AB\u62D2\u7EDD\uFF0C\u6CA1\u6709\u91C7\u7528\u3002\u8BF7\u91CD\u65B0\u9884\u68C0\u5E76\u518D\u6B21\u52FE\u9009\u786E\u8BA4\uFF0C\u4ECD\u7136\u7528\u540C\u4E00\u4E2A\u64CD\u4F5C\u7F16\u53F7\u548C\u786E\u8BA4\u5185\u5BB9\u3002"), !s.result ? /*#__PURE__*/React.createElement(Fields, {
      session: s
    }) : /*#__PURE__*/React.createElement("dl", {
      className: "ta-scope"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u91C7\u7528\u539F\u56E0"), /*#__PURE__*/React.createElement("dd", null, s.saved.input.reason)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u7ECF\u529E\u4EBA"), /*#__PURE__*/React.createElement("dd", null, s.saved.input.declared_operator))), /*#__PURE__*/React.createElement(Records, {
      value: value,
      saved: s.saved,
      result: s.result
    })));
  }
  function Styles() {
    return null;
  }
  window.TrialAdoptionControls = {
    Button,
    Dialog,
    Styles
  };
})();
