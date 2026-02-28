/* APS common_prefetch.js — 原生页面预取（Win7 + Chrome 109） */
(function () {
  "use strict";

  var ns = window.__APS_COMMON__;
  if (!ns) {
    return;
  }
  if (!ns._inited) {
    ns._inited = {};
  }
  if (ns._inited.prefetch) {
    return;
  }
  ns._inited.prefetch = true;

  var requestIdle = ns.requestIdle;
  var normalizePrefetchUrl = ns.normalizePrefetchUrl;
  var NATIVE_PREFETCH_ENABLED = ns.NATIVE_PREFETCH_ENABLED;
  if (typeof requestIdle !== "function" || typeof normalizePrefetchUrl !== "function") {
    return;
  }

  /* --- 7. 原生页面预取（白名单 GET） --- */
  if (NATIVE_PREFETCH_ENABLED && document.head) {
    var prefetched = {};
    function prefetchPath(pathname) {
      if (!pathname || prefetched[pathname]) {
        return;
      }
      prefetched[pathname] = true;
      requestIdle(function () {
        try {
          var link = document.createElement("link");
          link.rel = "prefetch";
          link.href = pathname;
          link.as = "document";
          document.head.appendChild(link);
        } catch (_e13) {
          // ignore prefetch failures
        }
      }, 1200);
    }

    var navObserver = null;
    if ("IntersectionObserver" in window) {
      try {
        navObserver = new IntersectionObserver(function (entries) {
          entries.forEach(function (entry) {
            if (!entry || !entry.isIntersecting) {
              return;
            }
            var a = entry.target;
            if (!a || !a.getAttribute) {
              return;
            }
            var p = normalizePrefetchUrl(a.getAttribute("href") || "");
            if (p) {
              prefetchPath(p);
            }
            try {
              navObserver.unobserve(a);
            } catch (_e14) {
              // ignore
            }
          });
        }, { root: null, rootMargin: "120px 0px", threshold: 0.01 });
      } catch (_e15) {
        navObserver = null;
      }
    }

    var prefetchLinks = document.querySelectorAll("header nav a[href], .sidebar .nav-item[href], .scheduler-subnav a[href]");
    var observed = 0;
    prefetchLinks.forEach(function (a) {
      if (observed >= 24) {
        return;
      }
      var p = normalizePrefetchUrl(a.getAttribute("href") || "");
      if (!p) {
        return;
      }
      if (p === window.location.pathname) {
        return;
      }
      observed += 1;
      if (navObserver) {
        try {
          navObserver.observe(a);
        } catch (_e16) {
          // ignore
        }
      } else {
        prefetchPath(p);
      }
    });
  }
})();

