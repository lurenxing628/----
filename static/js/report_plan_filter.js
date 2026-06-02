(function () {
  "use strict";

  function scenarioInputFor(form) {
    return form && form.querySelector ? form.querySelector('input[name="scenario_id"]') : null;
  }

  function initialScenarioId(input) {
    if (!input) return "";
    if (!input.hasAttribute("data-initial-scenario-id")) {
      input.setAttribute("data-initial-scenario-id", input.value || "");
    }
    return input.getAttribute("data-initial-scenario-id") || "";
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
    var scenarioInput = scenarioInputFor(form);
    var originalScenarioId = initialScenarioId(scenarioInput);
    if (scenarioInput) scenarioInput.value = hasChangedPlanIdentity(form) ? "" : originalScenarioId;
  }

  document.addEventListener("change", function (event) {
    var control = event.target;
    if (isPlanIdentityControl(control)) syncScenarioId(control.form);
  });

  document.addEventListener("submit", function (event) {
    syncScenarioId(event.target);
  });
})();
