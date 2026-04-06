(function () {
  "use strict";

  var ns = window.__APS_COMMON__;
  if (!ns) {
    return;
  }
  if (!ns._inited) {
    ns._inited = {};
  }
  if (ns._inited.manualPopover) {
    return;
  }
  ns._inited.manualPopover = true;

  var openWrapper = null;

  function findTrigger(el) {
    return el && el.closest
      ? el.closest('.floating-manual-btn[data-manual-popover="1"]')
      : null;
  }

  function findWrapper(el) {
    return el && el.closest ? el.closest(".floating-manual-wrapper") : null;
  }

  function findPopover(wrapper) {
    return wrapper ? wrapper.querySelector(".manual-popover") : null;
  }

  function findCloseBtn(el) {
    return el && el.closest ? el.closest(".manual-popover__close") : null;
  }

  function closeOpen(restoreFocus) {
    if (!openWrapper) {
      return;
    }
    var trigger = openWrapper.querySelector(
      '.floating-manual-btn[data-manual-popover="1"]'
    );
    var pop = findPopover(openWrapper);
    if (pop) {
      pop.hidden = true;
    }
    if (trigger) {
      trigger.setAttribute("aria-expanded", "false");
      if (restoreFocus && trigger.focus) {
        trigger.focus();
      }
    }
    openWrapper = null;
  }

  function openForTrigger(trigger) {
    var wrapper = findWrapper(trigger);
    var pop = findPopover(wrapper);
    if (!wrapper || !pop) {
      return;
    }
    if (openWrapper && openWrapper !== wrapper) {
      closeOpen(false);
    }
    var wasOpen = !pop.hidden;
    pop.hidden = wasOpen;
    trigger.setAttribute("aria-expanded", wasOpen ? "false" : "true");
    openWrapper = wasOpen ? null : wrapper;
    if (!wasOpen) {
      var focusTarget = wrapper.querySelector(
        ".manual-popover__close, .manual-popover a, .manual-popover button"
      );
      if (focusTarget && focusTarget.focus) {
        focusTarget.focus();
      }
    }
  }

  document.addEventListener("click", function (e) {
    if (findCloseBtn(e.target)) {
      closeOpen(true);
      return;
    }

    var trigger = findTrigger(e.target);
    if (
      trigger &&
      e.button === 0 &&
      !e.metaKey &&
      !e.ctrlKey &&
      !e.shiftKey &&
      !e.altKey
    ) {
      e.preventDefault();
      openForTrigger(trigger);
      return;
    }

    if (openWrapper) {
      var curPop = findPopover(openWrapper);
      var curTrigger = openWrapper.querySelector(
        '.floating-manual-btn[data-manual-popover="1"]'
      );
      if (
        curPop &&
        !curPop.contains(e.target) &&
        curTrigger &&
        !curTrigger.contains(e.target)
      ) {
        closeOpen(false);
      }
    }
  });

  document.addEventListener("focusin", function (e) {
    if (openWrapper && !openWrapper.contains(e.target)) {
      closeOpen(false);
    }
  });

  document.addEventListener("keydown", function (e) {
    if ((e.key || "") === "Escape" && openWrapper) {
      closeOpen(true);
    }
  });
})();
