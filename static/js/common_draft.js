/* APS common_draft.js — 表单草稿自动保存（Win7 + Chrome 109） */
(function () {
  "use strict";

  var ns = window.__APS_COMMON__;
  if (!ns) {
    return;
  }
  if (!ns._inited) {
    ns._inited = {};
  }
  if (ns._inited.draft) {
    return;
  }
  ns._inited.draft = true;

  var serializeForm = ns.serializeForm;
  var restoreForm = ns.restoreForm;
  var getOrCreateTabToken = ns.getOrCreateTabToken;
  var debounce = ns.debounce;
  if (
    typeof serializeForm !== "function"
    || typeof restoreForm !== "function"
    || typeof getOrCreateTabToken !== "function"
    || typeof debounce !== "function"
  ) {
    return;
  }

  /* --- 6.5 表单草稿自动保存（仅 data-autosave=true） --- */
  document.querySelectorAll('form[data-autosave="true"]').forEach(function (form) {
    var autosaveKey = String(form.getAttribute("data-autosave-key") || "").trim();
    if (!autosaveKey) {
      return;
    }
    var key = "aps_draft:v1:" + autosaveKey;
    var submitMarkKey = "aps_draft_submit:v1:" + autosaveKey;
    var tabToken = getOrCreateTabToken();
    var clearOnSuccess = String(form.getAttribute("data-autosave-clear-on-success") || "1").trim() !== "0";
    function snapshotsEqual(a, b) {
      try {
        return JSON.stringify(a || {}) === JSON.stringify(b || {});
      } catch (_e5) {
        return false;
      }
    }

    function hasSuccessFlash() {
      return !!document.querySelector(".flash-card.flash-success, .alert.alert-success");
    }

    function hasErrorFlash() {
      return !!document.querySelector(".flash-card.flash-error, .alert.alert-error");
    }

    function hasWarningFlash() {
      return !!document.querySelector(".flash-card.flash-warning, .alert.alert-warning");
    }

    var submitMarkTs = 0;
    var submitMarkToken = "";
    try {
      var rawSubmitMark = String(sessionStorage.getItem(submitMarkKey) || "").trim();
      if (rawSubmitMark.indexOf("|") > 0) {
        var parts = rawSubmitMark.split("|");
        submitMarkTs = Number(parts[0] || 0);
        submitMarkToken = String(parts[1] || "");
      } else {
        submitMarkTs = Number(rawSubmitMark || 0);
        submitMarkToken = "";
      }
    } catch (_e6) {}

    var submitOwnedByCurrentTab = !submitMarkToken || submitMarkToken === tabToken;
    if (submitMarkTs > 0 && submitOwnedByCurrentTab) {
      var elapsed = Date.now() - submitMarkTs;
      var hasSuccess = hasSuccessFlash();
      var hasError = hasErrorFlash();
      var hasWarning = hasWarningFlash();
      var currentSnapshot = serializeForm(form);
      var draftSnapshot = null;
      try {
        draftSnapshot = JSON.parse(localStorage.getItem(key) || "null");
      } catch (_e7) {
        draftSnapshot = null;
      }
      var canClearDraft = clearOnSuccess
        && hasSuccess
        && !hasError
        && snapshotsEqual(draftSnapshot, currentSnapshot);
      if (canClearDraft) {
        try {
          localStorage.removeItem(key);
        } catch (_e8) {}
      }
      if (hasSuccess || hasError || hasWarning || elapsed > 10 * 60 * 1000) {
        try {
          sessionStorage.removeItem(submitMarkKey);
        } catch (_e9) {}
      }
    }

    var saveDraft = debounce(function () {
      try {
        localStorage.setItem(key, JSON.stringify(serializeForm(form)));
      } catch (_e10) {}
    }, 1000);

    form.addEventListener("input", saveDraft, true);
    form.addEventListener("change", saveDraft, true);
    form.addEventListener("submit", function () {
      try {
        localStorage.setItem(key, JSON.stringify(serializeForm(form)));
      } catch (_e11) {}
      try {
        sessionStorage.setItem(submitMarkKey, String(Date.now()) + "|" + tabToken);
      } catch (_e12) {}
    });

    var saved = null;
    try {
      saved = JSON.parse(localStorage.getItem(key) || "null");
    } catch (_e13) {
      saved = null;
    }
    if (saved && Object.keys(saved).length > 0) {
      var notice = document.createElement("div");
      notice.className = "flash-card flash-warning alert alert-warning";
      notice.innerHTML = '检测到未保存的草稿。'
        + ' <span class="aps-draft-actions">'
        + '<button type="button" class="btn btn-sm btn-secondary" data-draft-action="restore">恢复草稿</button>'
        + '<button type="button" class="btn btn-sm btn-ghost" data-draft-action="clear">清除</button>'
        + '<button type="button" class="btn btn-sm btn-ghost" data-draft-action="close" data-draft-notice-close="1" title="只关闭提示，不删除草稿">关闭</button>'
        + '</span>';
      if (form.parentNode) {
        form.parentNode.insertBefore(notice, form);
      }
      var restoreBtn = notice.querySelector('[data-draft-action="restore"]');
      var clearBtn = notice.querySelector('[data-draft-action="clear"]');
      var closeBtn = notice.querySelector('[data-draft-action="close"]');
      if (restoreBtn) {
        restoreBtn.addEventListener("click", function () {
          restoreForm(form, saved);
          try {
            localStorage.removeItem(key);
          } catch (_e14) {}
          try {
            sessionStorage.removeItem(submitMarkKey);
          } catch (_e15) {}
          if (notice.parentNode) {
            notice.parentNode.removeChild(notice);
          }
        });
      }
      if (clearBtn) {
        clearBtn.addEventListener("click", function () {
          try {
            localStorage.removeItem(key);
          } catch (_e16) {}
          try {
            sessionStorage.removeItem(submitMarkKey);
          } catch (_e17) {}
          if (notice.parentNode) {
            notice.parentNode.removeChild(notice);
          }
        });
      }
      if (closeBtn) {
        closeBtn.addEventListener("click", function () {
          if (notice.parentNode) {
            notice.parentNode.removeChild(notice);
          }
        });
      }
    }
  });
})();
