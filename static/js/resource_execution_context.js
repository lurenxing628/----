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

  function actualRecordUrl(opId) {
    const template = trim(state && state.cfg && state.cfg.actualRecordUrlTemplate);
    if (!template || !opId) return "";
    const path = template.replace("__OP_ID__", encodeURIComponent(opId));
    const query = currentQueryString();
    if (!query) return path;
    return path.indexOf("?") >= 0 ? path + "&" + query.slice(1) : path + query;
  }

  Object.assign(ns.execution, {
    actualRecordUrl: actualRecordUrl,
    executionCreatedBy: executionCreatedBy,
    executionNotice: executionNotice
  });
})();
