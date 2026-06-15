(function () {
  "use strict";

  function scenarioInputFor(form) {
    return form && form.querySelector ? form.querySelector('input[name="scenario_id"]') : null;
  }

  function scenarioInputsFor(form) {
    if (!form || !form.querySelectorAll) return [];
    var inputs = form.querySelectorAll('input[name="scenario_id"], input[name="plan_context_token"]');
    return Array.prototype.slice.call(inputs || []);
  }

  function initialScenarioValue(input) {
    if (!input) return "";
    var attr = input.getAttribute("name") === "plan_context_token" ? "data-initial-plan-context-token" : "data-initial-scenario-id";
    if (!input.hasAttribute(attr)) {
      input.setAttribute(attr, input.value || "");
    }
    return input.getAttribute(attr) || "";
  }

  function initialPlanValue(control) {
    if (control.hasAttribute("data-initial-plan-role")) return control.getAttribute("data-initial-plan-role") || "";
    return control.getAttribute("data-initial-version") || "";
  }

  function isPlanIdentityControl(control) {
    return control && control.matches && control.matches("[data-report-plan-role-select], [data-report-plan-version-select]");
  }

  function hasChangedPlanIdentity(form) {
    if (!form || !form.querySelectorAll) return false;
    return Array.prototype.some.call(
      form.querySelectorAll("[data-report-plan-role-select], [data-report-plan-version-select]"),
      function (control) {
        return (control.value || "") !== initialPlanValue(control);
      }
    );
  }

  function syncScenarioId(form) {
    var changed = hasChangedPlanIdentity(form);
    var inputs = scenarioInputsFor(form);
    if (!inputs.length) {
      var legacyInput = scenarioInputFor(form);
      if (legacyInput) inputs = [legacyInput];
    }
    inputs.forEach(function (input) {
      var originalValue = initialScenarioValue(input);
      input.value = changed ? "" : originalValue;
    });
  }

  document.addEventListener("change", function (event) {
    var control = event.target;
    if (isPlanIdentityControl(control)) syncScenarioId(control.form);
  });

  document.addEventListener("submit", function (event) {
    syncScenarioId(event.target);
  });
})();
