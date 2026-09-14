(function () {
  'use strict';

  // EmptyState / Pager 的实现在 ResourceControls.jsx（与 Button、ErrorBox 同层，避免和 Choice 形成循环依赖）。
  // 这里只保留两个既有入口名，调用方继续用 window.WorkbenchListControls.* 或 window.WorkbenchControls.*。
  const {
    EmptyState,
    Pager
  } = window.ResourceControls;
  window.WorkbenchListControls = {
    EmptyState,
    Pager
  };
  Object.assign(window.WorkbenchControls, window.WorkbenchListControls);
})();
