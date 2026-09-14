(function () {
  'use strict';
  class WorkbenchBoundary extends React.Component {
    constructor(props) { super(props); this.state = { failed: false, attempt: 0 }; }
    static getDerivedStateFromError() { return { failed: true }; }
    componentDidCatch(error, details) { console.error('工作区渲染失败', error, details.componentStack); }
    render() {
      if (this.state.failed) return <section className="wb-render-failure" aria-label="工作区读取失败">
        <h2>工作区暂时无法显示</h2><p role="alert">页面显示出错，数据没有改动。请点「重新打开此工作区」；仍不行请刷新页面。</p>
        <button type="button" className="btn" onClick={() => this.setState(previous => ({ failed: false, attempt: previous.attempt + 1 }))}>
          <Ico name="refresh-cw" />重新打开此工作区</button>
      </section>;
      return <React.Fragment key={this.state.attempt}>{this.props.children}</React.Fragment>;
    }
  }
  window.WorkbenchBoundary = WorkbenchBoundary;
})();
