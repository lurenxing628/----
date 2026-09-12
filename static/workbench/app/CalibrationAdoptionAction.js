(function () {
  'use strict';

  function CalibrationAdoptionAction({
    detail,
    stale = false,
    onRefresh,
    adapter
  }) {
    const U = window.CalibrationAdoptionControls,
      s = window.CalibrationAdoptionState.useSession({
        detail,
        stale,
        adapter
      });
    const label = s.saved ? s.saved.phase === 'committed' ? '查看采用回执' : s.saved.phase === 'pending' ? '核实原采纳请求' : '重新核对采用' : '预览采用';
    return /*#__PURE__*/React.createElement("div", {
      className: "plana calibration-adoption",
      "data-calibration-adoption": "true"
    }, /*#__PURE__*/React.createElement(U.Styles, null), /*#__PURE__*/React.createElement(U.Button, {
      icon: s.saved ? 'refresh-cw' : 'check',
      "aria-label": label,
      reasonDisplay: "tooltip",
      reason: !s.saved && (!detail || stale) ? '请先读取有效的所选模板和样本。' : '',
      onClick: () => s.setOpen(true),
      "aria-expanded": s.open
    }, label), s.saved && !s.open && /*#__PURE__*/React.createElement("span", {
      className: "cad-inline"
    }, s.saved.phase === 'committed' ? '采用与锁定回执已恢复。' : '原请求已保留，请先核实。'), s.storageError && !s.open && /*#__PURE__*/React.createElement("span", {
      className: "cad-inline",
      role: "alert"
    }, s.storageError, /*#__PURE__*/React.createElement(U.Button, {
      icon: "refresh-cw",
      onClick: s.sync
    }, "\u91CD\u8BFB\u6062\u590D\u8BB0\u5F55")), s.open && /*#__PURE__*/React.createElement(U.Dialog, {
      session: s,
      detail: detail,
      stale: stale,
      onRefresh: onRefresh
    }));
  }
  window.CalibrationAdoptionAction = CalibrationAdoptionAction;
})();
