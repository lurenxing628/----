(function () {
  'use strict';

  const G = window.WorkbenchGuards,
    {
      Modal,
      Button
    } = window.ResourceControls;
  function WorkbenchGuardHost() {
    const [prompt, setPrompt] = React.useState(G.getPrompt);
    React.useLayoutEffect(() => G.subscribe(setPrompt), []);
    if (!prompt) return null;
    const close = () => G.resolvePrompt(prompt.id, false);
    return ReactDOM.createPortal(/*#__PURE__*/React.createElement("div", {
      className: "plana wb-guard-host"
    }, /*#__PURE__*/React.createElement(Modal, {
      title: prompt.locked ? '上次操作还没有确认结果' : '离开前确认',
      icon: "circle-alert",
      guardBypass: true,
      onClose: close,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: close
      }, "\u7559\u5728\u5F53\u524D\u9875\u9762"), !prompt.locked && /*#__PURE__*/React.createElement(Button, {
        className: "btn danger",
        onClick: () => G.resolvePrompt(prompt.id, true)
      }, "\u653E\u5F03\u672A\u4FDD\u5B58\u5185\u5BB9\u5E76\u7EE7\u7EED"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b"
    }, prompt.locked && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u4E0A\u6B21\u64CD\u4F5C\u7684\u7ED3\u679C\u8FD8\u6CA1\u67E5\u5230\uFF0C\u8BF7\u7559\u5728\u672C\u9875\u70B9\u300C\u67E5\u8BE2\u7ED3\u679C\u300D\uFF0C\u4E0D\u8981\u653E\u5F03\u6216\u91CD\u590D\u63D0\u4EA4\u3002"), /*#__PURE__*/React.createElement("ul", null, prompt.messages.map(message => /*#__PURE__*/React.createElement("li", {
      key: message
    }, message))), !prompt.locked && /*#__PURE__*/React.createElement("p", null, "\u7EE7\u7EED\u540E\uFF0C\u8FD9\u4E9B\u5C1A\u672A\u4FDD\u5B58\u7684\u8F93\u5165\u5C06\u4E22\u5931\u3002\u5DF2\u7ECF\u4FDD\u5B58\u7684\u8BB0\u5F55\u4E0D\u4F1A\u5220\u9664\u3002")))), document.body);
  }
  window.WorkbenchGuardHost = WorkbenchGuardHost;
})();
