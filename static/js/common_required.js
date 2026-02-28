/* APS common_required.js — required label auto-mark（Win7 + Chrome 109） */
(function () {
  "use strict";

  var ns = window.__APS_COMMON__;
  if (!ns) {
    return;
  }
  if (!ns._inited) {
    ns._inited = {};
  }
  if (ns._inited.required) {
    return;
  }
  ns._inited.required = true;

  var requestIdle = ns.requestIdle;
  if (typeof requestIdle !== "function") {
    return;
  }

  function markRequiredLabels(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll(".form-field").forEach(function (field) {
      var label = field.querySelector("label");
      if (!label) {
        return;
      }
      var requiredControl = field.querySelector("input[required], select[required], textarea[required]");
      label.classList.toggle("required-label", !!requiredControl);
    });
  }

  var requiredLabelRefreshTimer = 0;
  function scheduleRequiredLabelRefresh(root) {
    if (requiredLabelRefreshTimer) {
      clearTimeout(requiredLabelRefreshTimer);
    }
    requiredLabelRefreshTimer = setTimeout(function () {
      requiredLabelRefreshTimer = 0;
      markRequiredLabels(root && root.querySelectorAll ? root : document);
    }, 80);
  }

  ns.scheduleRequiredLabelRefresh = scheduleRequiredLabelRefresh;

  requestIdle(function () {
    markRequiredLabels(document);
  }, 1000);
  if ("MutationObserver" in window) {
    var requiredLabelObserver = new MutationObserver(function (mutations) {
      var refreshRoot = null;
      for (var i = 0; i < mutations.length; i++) {
        var m = mutations[i];
        if (!m) {
          continue;
        }
        if (m.type === "attributes") {
          var target = m.target;
          if (target && target.closest) {
            refreshRoot = target.closest(".form-field") || target.closest("form") || document;
          } else {
            refreshRoot = document;
          }
        }
      }
      if (refreshRoot) {
        scheduleRequiredLabelRefresh(refreshRoot);
      }
    });
    try {
      requiredLabelObserver.observe(document.body, {
        attributes: true,
        subtree: true,
        attributeFilter: ["required"],
      });
    } catch (_e2) {
      // ignore
    }
  }
  // 动态表单兜底：在交互时按表单维度刷新，避免大范围扫描
  document.addEventListener("focusin", function (e) {
    var target = e.target;
    var form = target && target.form ? target.form : (target && target.closest ? target.closest("form") : null);
    if (form) {
      scheduleRequiredLabelRefresh(form);
    }
  }, true);
  document.addEventListener("change", function (e) {
    var target = e.target;
    var form = target && target.form ? target.form : (target && target.closest ? target.closest("form") : null);
    if (form) {
      scheduleRequiredLabelRefresh(form);
    }
  }, true);
})();

