(function () {
  'use strict';

  const {
      Button
    } = window.ResourceControls,
    P = window.APSProcessContract;
  function ProcessFileButtons({
    capabilities,
    disabled,
    hoursOnly = false,
    routeOnly = false,
    onAction
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, (hoursOnly ? [['hours', '工时定额']] : routeOnly ? [['route', '工艺路线']] : [['route', '工艺路线'], ['hours', '工时定额']]).map(([kind, label]) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: kind
    }, /*#__PURE__*/React.createElement(Button, {
      transfer: "import",
      reason: P.reason(capabilities, 'import', typeof onAction === 'function'),
      disabled: disabled,
      onClick: () => onAction(kind, 'import')
    }, '导入' + label), /*#__PURE__*/React.createElement(Button, {
      transfer: "export",
      reason: P.reason(capabilities, 'export', typeof onAction === 'function'),
      disabled: disabled,
      onClick: () => onAction(kind, 'export')
    }, '导出' + label))));
  }
  window.ProcessFileButtons = ProcessFileButtons;
})();
