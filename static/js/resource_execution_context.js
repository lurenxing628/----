(function () {
  const ns = window.__APS_RESOURCE_DISPATCH__;
  ns.execution = ns.execution || {};
  const state = ns.state;
  const $ = ns.$;
  const trim = ns.trim;
  const show = ns.show;

  function currentQueryString() {
    return ns.core.currentQueryString();
  }

  function executionNotice(message) {
    const notice = $("rdExecutionNotice");
    if (!notice) return;
    notice.textContent = trim(message);
    show(notice, !!trim(message));
  }

  function executionCreatedBy() {
    const input = $("rdExecutionCreatedBy");
    return input ? trim(input.value) : "";
  }

  function actualRecordUrl(taskKey) {
    const template = trim(state && state.cfg && state.cfg.actualRecordUrlTemplate);
    if (!template || !taskKey) return "";
    const path = template.replace("__TASK_KEY__", encodeURIComponent(taskKey));
    if (path.indexOf("?") >= 0) return path;
    const query = currentQueryString();
    if (!query) return path;
    return path + query;
  }

  Object.assign(ns.execution, {
    actualRecordUrl: actualRecordUrl,
    executionCreatedBy: executionCreatedBy,
    executionNotice: executionNotice
  });
})();
