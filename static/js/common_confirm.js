/* APS common_confirm.js — confirm/auto-submit/防双击（Win7 + Chrome 109） */
(function () {
  "use strict";

  var ns = window.__APS_COMMON__;
  if (!ns) {
    return;
  }
  if (!ns._inited) {
    ns._inited = {};
  }
  if (ns._inited.confirm) {
    return;
  }
  ns._inited.confirm = true;

  /* --- 2. 确认对话框：提交路径统一判定 + 去重 --- */
  // 回归契约关键字（tests/regression_frontend_common_interactions.py）
  var FORM_CONFIRM_SELECTOR = "form[data-confirm]";
  var CONFIRM_TRIGGER_SELECTOR = "button[data-confirm], input[type='submit'][data-confirm], a[data-confirm], input[type='image'][data-confirm]";

  function getConfirmText(el) {
    if (!el || !el.getAttribute) {
      return "";
    }
    var msg = el.getAttribute("data-confirm") || "";
    return String(msg).trim();
  }

  function isSubmitControl(el) {
    if (!el || !el.tagName) {
      return false;
    }
    var tag = String(el.tagName).toUpperCase();
    if (tag === "BUTTON") {
      var btnType = (el.getAttribute("type") || "submit").toLowerCase();
      return btnType === "submit";
    }
    if (tag === "INPUT") {
      var inputType = (el.getAttribute("type") || "").toLowerCase();
      return inputType === "submit" || inputType === "image";
    }
    return false;
  }

  function trackSubmitter(trigger) {
    if (!trigger || !trigger.form) {
      return;
    }
    var form = trigger.form;
    try {
      form._apsLastSubmitter = trigger;
      if (form._apsLastSubmitterTimer) {
        clearTimeout(form._apsLastSubmitterTimer);
      }
      form._apsLastSubmitterTimer = setTimeout(function () {
        if (!form) {
          return;
        }
        form._apsLastSubmitter = null;
        form._apsLastSubmitterTimer = 0;
      }, 1500);
    } catch (_e) {
      // ignore
    }
  }

  document.addEventListener("click", function (e) {
    var target = e.target;
    if (!target || !target.closest) {
      return;
    }
    var trigger = target.closest(CONFIRM_TRIGGER_SELECTOR);
    if (!trigger) {
      return;
    }

    var tag = String(trigger.tagName || "").toUpperCase();
    if (tag === "A") {
      if (!confirm(getConfirmText(trigger) || "确定继续吗？")) {
        e.preventDefault();
        e.stopPropagation();
      }
      return;
    }

    // submit 按钮统一在 submit 阶段确认，避免 click + submit 双重弹窗
    if (isSubmitControl(trigger) && trigger.form) {
      trackSubmitter(trigger);
      return;
    }

    // 非提交按钮（如 data-confirm + onclick）仍在 click 阶段确认
    if (!confirm(getConfirmText(trigger) || "确定继续吗？")) {
      e.preventDefault();
      e.stopPropagation();
    }
  });

  // Enter 触发隐式提交时，尽量补齐 submitter 信息，保证优先读取按钮级 data-confirm
  document.addEventListener("keydown", function (e) {
    var key = e.key || e.code || "";
    if (key !== "Enter" && key !== "NumpadEnter") {
      return;
    }
    var target = e.target;
    if (!target || !target.form) {
      return;
    }
    var form = target.form;
    if (!form || form._apsLastSubmitter) {
      return;
    }
    var guessed = form.querySelector("button[type='submit'][data-confirm], input[type='submit'][data-confirm]");
    if (!guessed) {
      guessed = form.querySelector("button[type='submit'], input[type='submit']");
    }
    if (guessed) {
      trackSubmitter(guessed);
    }
  });

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form || !form.getAttribute) {
      return;
    }

    var submitter = e.submitter || form._apsLastSubmitter || null;
    if (submitter && submitter.form !== form) {
      submitter = null;
    }

    var msg = getConfirmText(submitter);
    if (!msg && form.matches && form.matches(FORM_CONFIRM_SELECTOR)) {
      msg = getConfirmText(form);
    }
    if (!msg) {
      msg = getConfirmText(form);
    }
    if (!msg) {
      if (form._apsLastSubmitterTimer) {
        clearTimeout(form._apsLastSubmitterTimer);
        form._apsLastSubmitterTimer = 0;
      }
      form._apsLastSubmitter = null;
      return;
    }

    // 去重：同一提交链路（click -> submit）只确认一次
    var token = "form";
    if (submitter && submitter.id) {
      token = "s#" + submitter.id;
    } else if (submitter && submitter.name) {
      token = "n#" + submitter.name + "::" + String(submitter.value || "");
    }
    if (form.dataset && form.dataset.apsConfirmPending === "1" && form.dataset.apsConfirmToken === token) {
      return;
    }

    if (!confirm(msg || "确定继续吗？")) {
      e.preventDefault();
      if (form.dataset) {
        form.dataset.apsConfirmPending = "";
        form.dataset.apsConfirmToken = "";
      }
      if (form._apsLastSubmitterTimer) {
        clearTimeout(form._apsLastSubmitterTimer);
        form._apsLastSubmitterTimer = 0;
      }
      form._apsLastSubmitter = null;
      return;
    }

    if (form.dataset) {
      form.dataset.apsConfirmPending = "1";
      form.dataset.apsConfirmToken = token;
      setTimeout(function () {
        if (!form || !form.dataset) {
          return;
        }
        form.dataset.apsConfirmPending = "";
        form.dataset.apsConfirmToken = "";
      }, 0);
    }
    if (form._apsLastSubmitterTimer) {
      clearTimeout(form._apsLastSubmitterTimer);
      form._apsLastSubmitterTimer = 0;
    }
    form._apsLastSubmitter = null;
  }, true);
  document.querySelectorAll("select[data-auto-submit='1']").forEach(function (sel) {
    sel.addEventListener("change", function () {
      var form = sel.form;
      if (form && typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else if (form) {
        var canContinue = true;
        try {
          if ("Event" in window) {
            var submitEvt = new Event("submit", { bubbles: true, cancelable: true });
            canContinue = form.dispatchEvent(submitEvt);
          }
        } catch (_e2) {
          canContinue = true;
        }
        if (canContinue) {
          form.submit();
        }
      }
    });
  });

  /* --- 3. 防双击 + Loading --- */
  document.addEventListener("submit", function (e) {
    if (e.defaultPrevented) {
      return;
    }
    var form = e.target;
    if (!form || !form.tagName || String(form.tagName).toUpperCase() !== "FORM") {
      return;
    }
    var method = (form.method || "").toLowerCase();
    if (method !== "post") {
      return;
    }
    if (form.dataset && form.dataset.submitted === "1") {
      e.preventDefault();
      return;
    }
    if (form.dataset) {
      form.dataset.submitted = "1";
    }
    var submitter = e.submitter || form._apsLastSubmitter || null;
    if (submitter && submitter.form !== form) {
      submitter = null;
    }
    var btns = form.querySelectorAll("button[type='submit'], input[type='submit']");
    btns.forEach(function (b) {
      if (submitter && b === submitter) {
        // 关键：不要禁用/改写 submitter，避免 Win7/Chrome109 丢失 name/value
        return;
      }
      b.disabled = true;
      if (b.tagName === "BUTTON") {
        b.dataset.originalText = b.textContent;
        b.classList.add("btn-loading");
        b.textContent = "处理中...";
      } else if (b.tagName === "INPUT") {
        b.dataset.originalValue = b.value;
        b.value = "处理中...";
      }
    });
  });
})();

