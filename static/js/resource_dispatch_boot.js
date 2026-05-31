(function () {
  const ns = window.__APS_RESOURCE_DISPATCH__;
  if (!ns.pageEl) return;

  ns.core.bindFieldToggles();
  ns.core.bindTabs();
  ns.execution.bindExecutionActionClicks();
  ns.execution.bindActualImportButtons();
  ns.core.loadData();
})();
