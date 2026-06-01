(function () {
  const ns = window.__APS_RESOURCE_DISPATCH__;
  ns.execution = ns.execution || {};
  const state = ns.state;
  const $ = ns.$;
  const trim = ns.trim;

  function currentQueryString() {
    return ns.core.currentQueryString();
  }

  function executionRequestUrl() {
    const url = state.cfg.executionUrl || "";
    if (!url) return "";
    return url.indexOf("?") >= 0 ? url : url + currentQueryString();
  }

  async function loadExecutionData() {
    if (!state.cfg.hasHistory || !state.cfg.canQuery || !state.cfg.executionUrl) {
      ns.execution.renderExecutionCards(null);
      return;
    }
    try {
      const resp = await fetch(executionRequestUrl(), { headers: { Accept: "application/json" } });
      const payload = await resp.json();
      if (!resp.ok || !payload || payload.success !== true) {
        const message = payload && payload.error && payload.error.message ? payload.error.message : "现场记录任务卡加载失败，请稍后重试。";
        throw new Error(message);
      }
      state.execution = payload.data || {};
      ns.execution.renderExecutionCards(state.execution);
    } catch (err) {
      state.execution = null;
      ns.execution.renderExecutionCards({ disabled_reason: err && err.message ? err.message : "现场记录任务卡加载失败，请稍后重试。", tasks: [] });
    }
  }

  function bindExecutionActionClicks() {
    const wrap = $("rdExecutionCards");
    if (!wrap) return;
    wrap.addEventListener("click", function (event) {
      const cancelTarget = event.target && event.target.closest ? event.target.closest(".aps-execution-inline-cancel") : null;
      if (cancelTarget && wrap.contains(cancelTarget)) {
        event.preventDefault();
        ns.execution.clearExecutionInlineForms(cancelTarget.closest(".aps-execution-card"));
        return;
      }
      const submitTarget = event.target && event.target.closest ? event.target.closest(".aps-execution-inline-submit") : null;
      if (submitTarget && wrap.contains(submitTarget)) {
        event.preventDefault();
        ns.execution.postExecutionAction(submitTarget);
        return;
      }
      const eventsTarget = event.target && event.target.closest ? event.target.closest(".aps-execution-events") : null;
      if (eventsTarget && wrap.contains(eventsTarget)) {
        event.preventDefault();
        ns.execution.loadExecutionRecords(eventsTarget);
        return;
      }
      const target = event.target && event.target.closest ? event.target.closest(".aps-execution-action") : null;
      if (!target || !wrap.contains(target)) return;
      event.preventDefault();
      if (trim(target.getAttribute("data-action")) === "fill_actual") {
        ns.execution.renderActualInlineForm(target);
      }
    });
  }

  Object.assign(ns.execution, {
    bindExecutionActionClicks: bindExecutionActionClicks,
    loadExecutionData: loadExecutionData
  });
})();
