(function () {
  'use strict';
  // The shared report workspace publishes the real review plan once, without competing hooks.
  function Workspace(props) { return <window.ReportWorkspace {...props} mode="review" />; }
  window.ReviewWorkspace = Workspace;
})();
