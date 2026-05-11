(function () {
  "use strict";

  function toNumber(value, fallback) {
    var parsed = Number(value);
    return isFinite(parsed) ? parsed : fallback;
  }

  function normalizedOptions(options) {
    var opts = options || {};
    return {
      gap: toNumber(opts.gap, 12),
      maxWidth: toNumber(opts.maxWidth, 420),
      minWidth: toNumber(opts.minWidth, 160),
    };
  }

  function getPopupWidth(popup, targetWidth, availableWidth) {
    var rectWidth = 0;
    try {
      var rect = popup.getBoundingClientRect ? popup.getBoundingClientRect() : null;
      rectWidth = rect ? Number(rect.width || 0) : 0;
    } catch (_err) {
      rectWidth = 0;
    }
    var measured = Number(popup.offsetWidth || 0) || rectWidth || targetWidth;
    if (!isFinite(measured) || measured <= 0) {
      measured = targetWidth;
    }
    if (availableWidth > 0 && measured > availableWidth) {
      return availableWidth;
    }
    return measured;
  }

  function computeFitGeometry(input, options) {
    var opts = normalizedOptions(options);
    var gap = opts.gap;
    var clientWidth = Math.max(0, toNumber(input && input.clientWidth, 0));
    var scrollLeft = toNumber(input && input.scrollLeft, 0);
    var availableWidth = Math.max(opts.minWidth, clientWidth - gap * 2);
    var targetWidth = Math.min(opts.maxWidth, availableWidth);
    var popupWidth = Math.min(Math.max(0, toNumber(input && input.popupWidth, targetWidth)), availableWidth);
    if (!popupWidth) {
      popupWidth = targetWidth;
    }

    var visibleLeft = scrollLeft + gap;
    var visibleRight = scrollLeft + clientWidth - gap;
    var left = toNumber(input && input.left, 0);
    var rightMostLeft = visibleRight - popupWidth;
    if (left + popupWidth > visibleRight) {
      left = Math.max(visibleLeft, rightMostLeft);
    }
    if (left < visibleLeft) {
      left = visibleLeft;
    }
    return {
      gap: gap,
      availableWidth: availableWidth,
      targetWidth: targetWidth,
      popupWidth: popupWidth,
      visibleLeft: visibleLeft,
      visibleRight: visibleRight,
      left: Math.round(left),
    };
  }

  function fitContainer(container, options) {
    if (!container) return null;
    var popup = container.querySelector ? container.querySelector(".popup-wrapper") : null;
    if (!popup) return null;

    try {
      var opacity = Number(window.getComputedStyle(popup).opacity || "0");
      if (!opacity) return null;
    } catch (_err) {
      // 如果测试环境没有 getComputedStyle，继续按可见处理。
    }

    var opts = normalizedOptions(options);
    var clientWidth = Math.max(0, toNumber(container.clientWidth, 0));
    if (!clientWidth) return null;
    var availableWidth = Math.max(opts.minWidth, clientWidth - opts.gap * 2);
    var targetWidth = Math.min(opts.maxWidth, availableWidth);

    popup.style.width = targetWidth + "px";
    popup.style.maxWidth = availableWidth + "px";
    popup.style.minWidth = Math.min(targetWidth, availableWidth) + "px";
    popup.style.boxSizing = "border-box";

    var popupWidth = getPopupWidth(popup, targetWidth, availableWidth);
    var left = parseFloat(popup.style.left || "0");
    var geometry = computeFitGeometry(
      {
        scrollLeft: container.scrollLeft,
        clientWidth: clientWidth,
        left: left,
        popupWidth: popupWidth,
      },
      opts
    );
    popup.style.left = geometry.left + "px";
    return geometry;
  }

  function scheduleFit(container, options) {
    if (typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(function () {
        fitContainer(container, options);
      });
    } else {
      window.setTimeout(function () {
        fitContainer(container, options);
      }, 0);
    }
  }

  function install(gantt, options) {
    var container = gantt && gantt.$container;
    if (!container || container.__apsPopupAutoFitInstalled) return;
    container.__apsPopupAutoFitInstalled = true;

    var onScheduleFit = function () {
      scheduleFit(container, options);
    };
    var onFit = function () {
      fitContainer(container, options);
    };

    container.addEventListener("click", onScheduleFit);
    container.addEventListener("focusin", onScheduleFit);
    container.addEventListener("scroll", onFit);
    if (window && window.addEventListener) {
      window.addEventListener("resize", onScheduleFit);
    }
    if (typeof window.ResizeObserver === "function") {
      try {
        var observer = new window.ResizeObserver(onScheduleFit);
        observer.observe(container);
        container.__apsPopupAutoFitResizeObserver = observer;
      } catch (_err) {
        // 旧浏览器或测试环境不支持时，依赖 resize/click/scroll 兜底。
      }
    }
  }

  window.__APS_GANTT_POPUP_FIT__ = {
    computeFitGeometry: computeFitGeometry,
    fit: fitContainer,
    install: install,
  };
})();
