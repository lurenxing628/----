export const WAIT_FOR_PAGE_STABLE_EXPRESSION = String.raw`
    (async () => {
      const withTimeout = (promise, ms, label) => new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error(label)), ms);
        Promise.resolve(promise).then(
          (value) => { clearTimeout(timer); resolve(value); },
          (error) => { clearTimeout(timer); reject(error); }
        );
      });
      if (document.readyState !== "complete") {
        await withTimeout(new Promise((resolve) => {
          window.addEventListener("load", resolve, { once: true });
        }), 5000, "load timeout");
      }
      if (document.fonts && document.fonts.ready) {
        await withTimeout(document.fonts.ready, 3000, "fonts timeout");
      }
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const first = Math.max(
        document.body ? document.body.scrollWidth : 0,
        document.documentElement ? document.documentElement.scrollWidth : 0
      );
      await new Promise((resolve) => setTimeout(resolve, 100));
      const second = Math.max(
        document.body ? document.body.scrollWidth : 0,
        document.documentElement ? document.documentElement.scrollWidth : 0
      );
      return { readyState: document.readyState, first, second };
    })()
`;

export function buildPageInspectionExpression(httpStatus) {
  return String.raw`
    (() => {
      const maxScrollWidth = Math.max(
        document.body ? document.body.scrollWidth : 0,
        document.documentElement ? document.documentElement.scrollWidth : 0
      );
      const bodyOverflow = maxScrollWidth > window.innerWidth + 1;
      const toggleRows = [...document.querySelectorAll('.aps-toggle-row')];
      const toggleOverlapCount = toggleRows.filter((row) => {
        const track = row.querySelector('.aps-toggle-track');
        const title = row.querySelector('.aps-toggle-title');
        if (!track || !title) return false;
        const a = track.getBoundingClientRect();
        const b = title.getBoundingClientRect();
        return !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top);
      }).length;
      const visibleNotices = [...document.querySelectorAll('.aps-notice,.aps-summary-item')]
        .filter((el) => {
          const rect = el.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0;
        }).length;
      document.documentElement.setAttribute('data-theme', 'dark');
      const darkSummaryBadCount = [...document.querySelectorAll('.aps-summary-item')]
        .filter((el) => {
          const style = getComputedStyle(el);
          return style.backgroundColor.includes('255, 255, 255') || style.color === style.backgroundColor;
        }).length;
      const logsTable = document.querySelector('#systemLogsTable');
      const bodyText = document.body ? document.body.innerText || "" : "";
      const titleText = document.title || "";
      const hasAppShell = Boolean(document.querySelector('header nav, header.top-header, nav.sidebar-nav'))
        && Boolean(document.getElementById('apsThemeToggle'));
      function includesKeyword(value, keyword) {
        return String(value || "").toLowerCase().includes(String(keyword || "").toLowerCase());
      }
      const errorKeywords = window.__APS_ERROR_PAGE_KEYWORDS__ || [];
      const matchedTitleErrorKeyword = errorKeywords.find((keyword) => includesKeyword(titleText, keyword)) || "";
      const matchedBodyErrorKeyword = errorKeywords.find((keyword) => includesKeyword(bodyText, keyword)) || "";
      const matchedErrorKeyword = matchedTitleErrorKeyword || (!hasAppShell ? matchedBodyErrorKeyword : "");
      const pageLooksError = ${httpStatus} >= 500 || Boolean(matchedErrorKeyword);
      const expectedTexts = window.__APS_EXPECTED_SIGNALS__?.texts || [];
      const expectedIds = window.__APS_EXPECTED_SIGNALS__?.ids || [];
      const expectedPath = window.__APS_EXPECTED_SIGNALS__?.path || "";
      const finalPath = location.pathname + location.search;
      const missingExpectedTexts = expectedTexts.filter((text) => !bodyText.includes(text));
      const missingExpectedIds = expectedIds.filter((id) => !document.getElementById(id));
      const pathMismatch = Boolean(expectedPath && finalPath !== expectedPath);
      function parseRgb(value) {
        const text = String(value || "");
        const start = text.indexOf("(");
        const end = text.indexOf(")");
        if (start < 0 || end <= start) return null;
        const parts = text.slice(start + 1, end).split(",");
        const alpha = parts.length >= 4 ? Number(String(parts[3] || "").trim()) : 1;
        if (Number.isFinite(alpha) && alpha === 0) return null;
        const channels = parts.slice(0, 3)
          .map((part) => Number(String(part || "").trim()));
        return channels.every((item) => Number.isFinite(item)) ? channels : null;
      }
      function channelToLinear(value) {
        const normalized = value / 255;
        return normalized <= 0.03928
          ? normalized / 12.92
          : Math.pow((normalized + 0.055) / 1.055, 2.4);
      }
      function luminance(rgb) {
        return 0.2126 * channelToLinear(rgb[0])
          + 0.7152 * channelToLinear(rgb[1])
          + 0.0722 * channelToLinear(rgb[2]);
      }
      function contrastRatio(a, b) {
        const high = Math.max(luminance(a), luminance(b));
        const low = Math.min(luminance(a), luminance(b));
        return (high + 0.05) / (low + 0.05);
      }
      function isVisible(el) {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
      }
      function selectorFor(el) {
        if (!el) return "";
        const tag = String(el.tagName || "").toLowerCase();
        const id = el.id ? "#" + el.id : "";
        const classes = String(el.className || "").trim().split(/\s+/).filter(Boolean).slice(0, 3).join(".");
        return tag + id + (classes ? "." + classes : "");
      }
      function horizontalScrollerAncestor(el) {
        let node = el.parentElement;
        while (node && node !== document.documentElement) {
          const style = getComputedStyle(node);
          if ((style.overflowX === "auto" || style.overflowX === "scroll") && node.scrollWidth > node.clientWidth + 1) {
            return selectorFor(node);
          }
          node = node.parentElement;
        }
        return "";
      }
      const overflowOffenders = [...document.querySelectorAll("body *")]
        .filter((el) => isVisible(el))
        .map((el) => {
          const rect = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          const outside = rect.right > window.innerWidth + 1 || rect.left < -1;
          return {
            outside,
            tagName: String(el.tagName || ""),
            id: el.id || "",
            className: String(el.className || "").slice(0, 160),
            selector: selectorFor(el),
            rect: { left: rect.left, right: rect.right, width: rect.width, height: rect.height },
            position: style.position,
            overflowX: style.overflowX,
            whiteSpace: style.whiteSpace,
            textSample: String(el.innerText || el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 80),
            insideHorizontalScroller: Boolean(horizontalScrollerAncestor(el)),
            horizontalScroller: horizontalScrollerAncestor(el),
          };
        })
        .filter((row) => row.outside)
        .slice(0, 20);
      const scrollMetrics = {
        bodyScrollWidth: document.body ? document.body.scrollWidth : 0,
        documentScrollWidth: document.documentElement ? document.documentElement.scrollWidth : 0,
        innerWidth: window.innerWidth,
      }
      function nearestBackground(el) {
        let node = el;
        while (node && node !== document.documentElement) {
          const bg = parseRgb(getComputedStyle(node).backgroundColor);
          if (bg) {
            return bg;
          }
          node = node.parentElement;
        }
        return parseRgb(getComputedStyle(document.body || document.documentElement).backgroundColor);
      }
      function lowContrastTextCount(selectors) {
        return selectors.flatMap((selector) => [...document.querySelectorAll(selector)])
          .filter((el) => isVisible(el))
          .filter((el) => {
            const fg = parseRgb(getComputedStyle(el).color);
            const bg = nearestBackground(el);
            return fg && bg && contrastRatio(fg, bg) < 3;
          }).length;
      }
      function multilineTableComputedOk(selector) {
        const table = document.querySelector(selector);
        if (!table) {
          return true;
        }
        if (!table.classList.contains('aps-table--multiline')) {
          return false;
        }
        const cells = [...table.querySelectorAll('thead th, tbody td')].filter((cell) => isVisible(cell));
        if (!cells.length) {
          return false;
        }
        return cells.slice(0, 12).every((cell) => {
          const style = getComputedStyle(cell);
          const wrapOk = style.overflowWrap === 'anywhere' || style.wordBreak !== 'normal';
          return (
            style.whiteSpace === 'normal'
            && style.textOverflow !== 'ellipsis'
            && style.overflow !== 'hidden'
            && wrapOk
          );
        });
      }
      const requiredToggleByPath = {
        "/scheduler/": ["runEnforceReady", "runStrictMode"],
        "/scheduler/batches": ["batchManageStrictMode"],
        "/scheduler/excel/batches": ["batchImportAutoOps", "batchImportStrictMode"],
        "/process/": ["processCreateStrictMode"],
      };
      const requiredToggleIds = requiredToggleByPath[location.pathname] || [];
      const missingRequiredToggleIds = requiredToggleIds
        .filter((id) => !document.getElementById(id));
      const darkLowContrastSummaryCount = [...document.querySelectorAll('.aps-summary-item')]
        .filter((el) => {
          const style = getComputedStyle(el);
          const fg = parseRgb(style.color);
          const bg = parseRgb(style.backgroundColor);
          return fg && bg && contrastRatio(fg, bg) < 3;
        }).length;
      const darkLowContrastTextCount = lowContrastTextCount([
        '.aps-summary-label',
        '.aps-summary-value',
        '.aps-summary-desc',
        '.aps-notice-title',
        '.aps-notice-body',
        '.aps-toggle-title',
        '.aps-toggle-desc',
      ]);
      const darkNoticeBadCount = [...document.querySelectorAll('.aps-notice')]
        .filter((el) => {
          const style = getComputedStyle(el);
          return style.backgroundColor.includes('255, 255, 255');
        }).length;
      const multilineTableChecks = {
        systemLogsTable: multilineTableComputedOk('#systemLogsTable'),
        pluginStatusTable: multilineTableComputedOk('#pluginStatusTable'),
        systemHistoryTable: multilineTableComputedOk('#systemHistoryTable'),
      };
      return JSON.stringify({
        path: finalPath,
        expectedPath,
        pathMismatch,
        httpStatus: ${httpStatus},
        url: location.href,
        title: document.title || "",
        hasAppShell,
        pageLooksError,
        matchedErrorKeyword,
        missingExpectedTexts,
        missingExpectedIds,
        width: window.innerWidth,
        bodyOverflow,
        maxScrollWidth,
        scrollMetrics,
        overflowOffenders,
        toggleCount: toggleRows.length,
        toggleOverlapCount,
        visibleNotices,
        darkSummaryBadCount,
        darkLowContrastSummaryCount,
        darkLowContrastTextCount,
        darkNoticeBadCount,
        multilineTableChecks,
        logsTableMultiline: multilineTableChecks.systemLogsTable,
        requiredToggleIds,
        missingRequiredToggleIds,
      });
    })()
`;
}
