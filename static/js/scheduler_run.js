(function () {
  "use strict";

  function checkedBatchCount() {
    return document.querySelectorAll(".js-batch-check:checked").length;
  }

  function ensureRunPanelError() {
    var panel = document.querySelector(".aps-run-panel");
    if (!panel) return null;
    var existing = panel.querySelector(".aps-run-panel-error");
    if (existing) return existing;
    var err = document.createElement("div");
    err.className = "aps-field-error aps-run-panel-error is-hidden";
    err.setAttribute("role", "alert");
    err.setAttribute("aria-live", "polite");
    var actions = panel.querySelector(".aps-run-panel-actions");
    if (actions && actions.parentNode) {
      actions.parentNode.insertBefore(err, actions);
    } else {
      panel.appendChild(err);
    }
    return err;
  }

  function setRunPanelError(message) {
    var err = ensureRunPanelError();
    if (!err) return;
    err.textContent = message || "";
    err.classList.toggle("is-hidden", !message);
  }

  var preset = document.getElementById("schedulerPresetSelect");
  if (preset && preset.form) {
    var previousValue = preset.value;

    preset.addEventListener("change", function () {
      var count = checkedBatchCount();

      if (count > 0) {
        var ok = confirm("切换排产方案会清空当前已选的 " + count + " 个批次。确定切换吗？");
        if (!ok) {
          preset.value = previousValue;
          return;
        }
      }

      previousValue = preset.value;

      if (typeof preset.form.requestSubmit === "function") {
        preset.form.requestSubmit();
      } else {
        preset.form.submit();
      }
    });
  }

  var runForm = document.getElementById("jsRunScheduleForm");
  if (!runForm) return;

  function blockEmptyRunSubmit(event) {
    if (checkedBatchCount() > 0) {
      setRunPanelError("");
      return false;
    }
    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === "function") {
      event.stopImmediatePropagation();
    }
    setRunPanelError("请先勾选至少一个待排批次。");
    return true;
  }

  function isRunSubmitControl(target) {
    if (!target || !target.closest) return false;
    var trigger = target.closest("button[type='submit'], input[type='submit'], input[type='image']");
    return !!(trigger && trigger.form === runForm);
  }

  document.addEventListener("click", function (event) {
    if (isRunSubmitControl(event.target)) {
      blockEmptyRunSubmit(event);
    }
  }, true);

  document.addEventListener("keydown", function (event) {
    var key = event.key || event.code || "";
    if (key !== "Enter" && key !== "NumpadEnter") return;
    var target = event.target;
    if (target && target.form === runForm) {
      blockEmptyRunSubmit(event);
    }
  }, true);

  runForm.addEventListener("submit", function (event) {
    blockEmptyRunSubmit(event);
  });
})();
