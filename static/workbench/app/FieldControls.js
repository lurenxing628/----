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
    return null;
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
    onDone,
    excludePaths = []
  }) {
    return /*#__PURE__*/React.createElement("div", {
      "aria-live": "polite"
    }, /*#__PURE__*/React.createElement(ErrorBox, {
      error: command.error,
      excludePaths: excludePaths
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
