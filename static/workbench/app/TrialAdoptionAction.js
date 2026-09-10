(function () {
  'use strict';

  // ResourceControls -> TrialAdoptionAPI -> TrialAdoptionState -> TrialAdoptionControls -> this file.
  // Main hook: renderAdoption(props); onAdopted receives the verified command receipt, not current-plan evidence.
  function Session(props) {
    const U = window.TrialAdoptionControls,
      s = window.TrialAdoptionState.useSession(props);
    const label = s.result ? '查看场景采用回执' : s.saved ? s.saved.phase === 'pending' ? '核实场景采用结果' : '重新核对场景采用' : '正式采用';
    const reason = s.saved ? '' : s.storageError || s.sourceError || (props.disabled ? '原场景正在读取或有待核实操作，新的采用已暂停。' : '');
    return /*#__PURE__*/React.createElement("span", {
      className: "plana trial-adoption-action",
      "data-trial-adoption-action": true
    }, /*#__PURE__*/React.createElement(U.Styles, null), /*#__PURE__*/React.createElement(U.Button, {
      icon: s.saved ? 'refresh-cw' : 'check',
      reason: reason,
      busy: s.busy && !s.saved,
      "aria-expanded": s.open,
      onClick: () => {
        if (s.saved) s.setOpen(true);else s.inspect();
      }
    }, label), !s.open && s.saved && /*#__PURE__*/React.createElement("span", {
      className: "ta-inline"
    }, s.result ? '提交时的采用回执已恢复。' : '原场景请求已保留，请先核实。'), !s.open && s.storageError && /*#__PURE__*/React.createElement("span", {
      className: "ta-inline",
      role: "alert"
    }, s.storageError, /*#__PURE__*/React.createElement(U.Button, {
      icon: "refresh-cw",
      onClick: s.sync
    }, "\u91CD\u8BFB\u6062\u590D\u8BB0\u5F55")), !s.open && !s.saved && s.notice && /*#__PURE__*/React.createElement("span", {
      className: "ta-inline",
      role: "status"
    }, s.notice), s.open && /*#__PURE__*/React.createElement(U.Dialog, {
      session: s,
      scenarioRef: props.scenarioRef,
      onNavigate: props.onNavigate
    }));
  }
  window.TrialAdoptionAction = function TrialAdoptionAction(props) {
    return /*#__PURE__*/React.createElement(Session, {
      key: props.scenarioRef || 'missing',
      ...props
    });
  };
})();
