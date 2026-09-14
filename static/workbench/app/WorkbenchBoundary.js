(function () {
  'use strict';

  class WorkbenchBoundary extends React.Component {
    constructor(props) {
      super(props);
      this.state = {
        failed: false,
        attempt: 0
      };
    }
    static getDerivedStateFromError() {
      return {
        failed: true
      };
    }
    componentDidCatch(error, details) {
      console.error('工作区渲染失败', error, details.componentStack);
    }
    render() {
      if (this.state.failed) return /*#__PURE__*/React.createElement("section", {
        className: "wb-render-failure",
        "aria-label": "\u5DE5\u4F5C\u533A\u8BFB\u53D6\u5931\u8D25"
      }, /*#__PURE__*/React.createElement("h2", null, "\u5DE5\u4F5C\u533A\u6682\u65F6\u65E0\u6CD5\u663E\u793A"), /*#__PURE__*/React.createElement("p", {
        role: "alert"
      }, "\u9875\u9762\u663E\u793A\u51FA\u9519\uFF0C\u6570\u636E\u6CA1\u6709\u6539\u52A8\u3002\u8BF7\u70B9\u300C\u91CD\u65B0\u6253\u5F00\u6B64\u5DE5\u4F5C\u533A\u300D\uFF1B\u4ECD\u4E0D\u884C\u8BF7\u5237\u65B0\u9875\u9762\u3002"), /*#__PURE__*/React.createElement("button", {
        type: "button",
        className: "btn",
        onClick: () => this.setState(previous => ({
          failed: false,
          attempt: previous.attempt + 1
        }))
      }, /*#__PURE__*/React.createElement(Ico, {
        name: "refresh-cw"
      }), "\u91CD\u65B0\u6253\u5F00\u6B64\u5DE5\u4F5C\u533A"));
      return /*#__PURE__*/React.createElement(React.Fragment, {
        key: this.state.attempt
      }, this.props.children);
    }
  }
  window.WorkbenchBoundary = WorkbenchBoundary;
})();
