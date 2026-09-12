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
      await withTimeout(new Promise((resolve, reject) => {
        const check = () => {
          const state = document.querySelector('#root')?.dataset.workbenchBoot;
          if (state === 'ready') resolve();
          else if (state === 'failed') reject(new Error('React boot failed'));
          else setTimeout(check, 25);
        };
        check();
      }), 5000, "workbench boot timeout");
      if (document.fonts && document.fonts.ready) {
        await withTimeout(document.fonts.ready, 3000, "fonts timeout");
      }
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const first = Math.max(
        document.body ? document.body.scrollWidth : 0,
        document.documentElement ? document.documentElement.scrollWidth : 0
      );
      await withTimeout((async () => {
        for (;;) {
          const transitions = document.getAnimations().filter(animation => animation instanceof CSSTransition
            && (animation.playState === 'running' || animation.pending));
          if (!transitions.length) break;
          await Promise.all(transitions.map(animation => animation.finished.catch(error => {
            if (error.name !== 'AbortError') throw error;
          })));
        }
      })(), 5000, 'CSS transition timeout');
      const second = Math.max(
        document.body ? document.body.scrollWidth : 0,
        document.documentElement ? document.documentElement.scrollWidth : 0
      );
      return { readyState: document.readyState, first, second };
    })()
`;


function inspectCurrentPage(httpStatus) {
  const expected = window.__APS_EXPECTED_SIGNALS__;
  const visible = element => {
    if (!element) return false;
    const box = element.getBoundingClientRect(), style = getComputedStyle(element);
    return box.width > 0 && box.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };
  const nodes = selectors => [...new Set(selectors.flatMap(selector => [...document.querySelectorAll(selector)]))].filter(visible);
  const overlaps = (a, b) => !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top);
  const textRects = label => {
    const walker = document.createTreeWalker(label, NodeFilter.SHOW_TEXT), boxes = [];
    while (walker.nextNode()) {
      if (!walker.currentNode.textContent.trim()) continue;
      const range = document.createRange(); range.selectNodeContents(walker.currentNode);
      boxes.push(...range.getClientRects()); range.detach();
    }
    return boxes;
  };
  const requiredControls = expected.controls || {}, missingRequiredToggleIds = [], toggleChecks = [];
  for (const [selector, count] of Object.entries(requiredControls)) {
    const inputs = [...document.querySelectorAll(selector)];
    if (inputs.length !== count) missingRequiredToggleIds.push(selector + ': expected ' + count + ', got ' + inputs.length);
    inputs.forEach(input => {
      const label = input.closest('label'), segment = input.closest('.pf-segment');
      let ok = ['radio', 'checkbox'].includes(input.type), evidence;
      if (segment) {
        const face = label && label.querySelector('span'), other = [...segment.querySelectorAll('label > span')].filter(node => node !== face);
        const box = face && face.getBoundingClientRect(), text = face && textRects(face);
        ok = ok && !!input.name && visible(face) && text.length > 0
          && other.every(node => !overlaps(box, node.getBoundingClientRect()))
          && text.every(rect => rect.left >= box.left - 1 && rect.right <= box.right + 1);
        evidence = { presentation: 'native-radio-with-segment-label', inputType: input.type, labelText: face?.textContent,
          inputOpacity: getComputedStyle(input).opacity, labelWidth: box?.width };
      } else {
        const labels = [...(input.labels || [])].filter(visible), box = input.getBoundingClientRect();
        const rectangles = labels.flatMap(textRects);
        ok = ok && visible(input) && labels.length > 0 && rectangles.length > 0
          && rectangles.every(rect => !overlaps(box, rect));
        evidence = { presentation: 'native-input-and-label', inputType: input.type, labels: labels.map(node => node.textContent.trim()),
          inputWidth: box.width };
      }
      if (!ok) missingRequiredToggleIds.push(selector + ': missing/invalid visible label geometry');
      toggleChecks.push({ selector, ok, checked: input.checked, disabled: input.disabled, ...evidence });
    });
  }
  const summarySelectors = expected.summaries || [], noticeSelectors = expected.notices || [];
  const summaries = nodes(summarySelectors);
  const notices = nodes(['.pf-alert', '.sm-note', '.plan-note', '.rw-basis', '.sm-notice', ...noticeSelectors]);
  const missingVisualSamples = summarySelectors.filter(selector => !nodes([selector]).length)
    .concat(noticeSelectors.filter(selector => !nodes([selector]).length));
  function parseRgb(value) {
    const text = String(value || ''), start = text.indexOf('('), end = text.indexOf(')');
    if (start < 0 || end <= start) return null;
    const parts = text.slice(start + 1, end).split(',');
    if (parts.length >= 4 && Number(parts[3]) === 0) return null;
    const channels = parts.slice(0, 3).map(Number);
    return channels.length === 3 && channels.every(Number.isFinite) ? channels : null;
  }
  function background(element) {
    for (let node = element; node; node = node.parentElement) {
      const value = parseRgb(getComputedStyle(node).backgroundColor);
      if (value) return value;
    }
    return null;
  }
  function luminance(rgb) {
    const linear = rgb.map(value => value / 255 <= 0.03928 ? value / 255 / 12.92 : Math.pow((value / 255 + 0.055) / 1.055, 2.4));
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
  }
  function lowContrast(element) {
    const foreground = parseRgb(getComputedStyle(element).color), bg = background(element);
    if (!foreground || !bg) return true;
    const values = [luminance(foreground), luminance(bg)];
    return (Math.max(...values) + 0.05) / (Math.min(...values) + 0.05) < 3;
  }
  function badDarkBackground(element) {
    const bg = background(element), fg = parseRgb(getComputedStyle(element).color);
    return !bg || !fg || bg.every(value => value === 255) || bg.every((value, index) => value === fg[index]);
  }
  function textNodes(roots) {
    return [...new Set(roots.flatMap(root => [root, ...root.querySelectorAll('*')]))]
      .filter(node => visible(node) && [...node.childNodes].some(child => child.nodeType === Node.TEXT_NODE && child.textContent.trim()));
  }
  const multilineTableDetails = [];
  function multilineTableComputedOk(selector) {
    const table = document.querySelector(selector);
    if (!visible(table)) return false;
    const logHeaders = ['工厂本地时间', '类型', '状态', '级别', '摘要 / 来源', '详情'];
    const headers = [...table.querySelectorAll('thead th')];
    const fixedLogHeaders = selector === '.sm-logs-table' && headers.length === logHeaders.length
      && headers.every((cell, index) => cell.textContent.trim() === logHeaders[index]);
    const cells = [...table.querySelectorAll('thead th, tbody td')].filter(visible);
    if (!cells.length || !table.querySelector('tbody td')) return false;
    const inspected = cells.slice(0, 12).map(cell => {
      const style = getComputedStyle(cell);
      const wrapOk = style.overflowWrap === 'anywhere' || style.wordBreak !== 'normal';
      const box = cell.getBoundingClientRect(), texts = textRects(cell);
      const textWithinCell = texts.every(rect => rect.width > 0 && rect.height > 0
        && rect.left >= box.left - 1 && rect.right <= box.right + 1
        && rect.top >= box.top - 1 && rect.bottom <= box.bottom + 1);
      const fixedHeader = fixedLogHeaders && headers.includes(cell);
      const fixedAction = fixedLogHeaders && cell.cellIndex === logHeaders.length - 1
        && cell.classList.contains('wb-col-actions') && style.position === 'sticky' && parseFloat(style.right) === 0;
      const actions = [...cell.querySelectorAll('button')];
      const actionGeometry = fixedAction && textWithinCell && box.left >= -1 && box.right <= innerWidth + 1
        && box.top >= -1 && box.bottom <= innerHeight + 1
        && (fixedHeader ? texts.length > 0 : actions.length === 1 && actions.every(action => {
          const rect = action.getBoundingClientRect();
          const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
          return visible(action) && !action.disabled && !!action.getAttribute('aria-label') && action.contains(hit)
            && rect.left >= box.left - 1 && rect.right <= box.right + 1
            && rect.top >= box.top - 1 && rect.bottom <= box.bottom + 1
            && action.scrollWidth <= action.clientWidth + 1 && action.scrollHeight <= action.clientHeight + 1;
        }));
      // The fixed detail action has no multiline record text; inspect its real bounds instead of requiring wrapping.
      const multiline = fixedAction ? actionGeometry : fixedHeader ? texts.length > 0 && textWithinCell : wrapOk;
      const whiteSpaceOk = style.whiteSpace === 'normal' || fixedAction && actionGeometry && style.whiteSpace === 'nowrap';
      return { tag: cell.tagName, text: cell.textContent, whiteSpace: style.whiteSpace, textOverflow: style.textOverflow,
        overflow: style.overflow, overflowWrap: style.overflowWrap, wordBreak: style.wordBreak,
        textWithinCell, fixedHeaderGeometry: fixedHeader, fixedActionGeometry: fixedAction ? actionGeometry : null,
        ok: whiteSpaceOk && style.textOverflow !== 'ellipsis' && style.overflow !== 'hidden' && multiline };
    });
    multilineTableDetails.push({ selector, fixedLogHeaders, headerTexts: headers.map(cell => cell.textContent.trim()), cells: inspected });
    return (selector !== '.sm-logs-table' || fixedLogHeaders) && inspected.every(cell => cell.ok);
  }
  const multilineTableChecks = Object.fromEntries((expected.tables || []).map(selector => [selector, multilineTableComputedOk(selector)]));
  const multilineTextDetails = (expected.multiline || []).map(selector => {
    const element = document.querySelector(selector), style = element && getComputedStyle(element), lines = element ? textRects(element) : [];
    const count = new Set(lines.map(rect => Math.round(rect.top))).size;
    return { selector, visible: visible(element), lines: count, chars: element?.textContent.length || 0,
      ok: visible(element) && count >= 2 && element.textContent.length > 0
        && ['pre-wrap', 'pre-line', 'normal'].includes(style.whiteSpace) && style.textOverflow !== 'ellipsis'
        && style.overflowX !== 'hidden' && style.overflowY !== 'hidden'
        && element.scrollWidth <= element.clientWidth + 1 && !lowContrast(element) };
  });
  function selectorFor(element) {
    const classes = String(element.className || '').trim().split(/\s+/).filter(Boolean).slice(0, 3).join('.');
    return element.tagName.toLowerCase() + (element.id ? '#' + element.id : '') + (classes ? '.' + classes : '');
  }
  function scroller(element) {
    for (let parent = element.parentElement; parent; parent = parent.parentElement) {
      const style = getComputedStyle(parent);
      if (['auto', 'scroll'].includes(style.overflowX) && parent.scrollWidth > parent.clientWidth + 1) return selectorFor(parent);
    }
    return '';
  }
  const overflowOffenders = [...document.querySelectorAll('body *')].filter(visible).map(element => {
    const rect = element.getBoundingClientRect(), style = getComputedStyle(element), ancestor = scroller(element);
    return { outside: rect.right > innerWidth + 1 || rect.left < -1, selector: selectorFor(element),
      rect: { left: rect.left, right: rect.right, width: rect.width, height: rect.height },
      overflowX: style.overflowX, whiteSpace: style.whiteSpace, position: style.position,
      insideHorizontalScroller: !!ancestor, horizontalScroller: ancestor,
      textSample: String(element.innerText || element.textContent || '').replace(/\s+/g, ' ').slice(0, 80) };
  }).filter(row => row.outside).slice(0, 20);
  const scrollMetrics = { bodyScrollWidth: document.body.scrollWidth, documentScrollWidth: document.documentElement.scrollWidth, innerWidth };
  const maxScrollWidth = Math.max(scrollMetrics.bodyScrollWidth, scrollMetrics.documentScrollWidth);
  const hasAppShell = document.querySelector('#root')?.dataset.workbenchBoot === 'ready'
    && !!document.querySelector('.operations-shell .sidebar-nav') && !!document.querySelector('.operations-shell .top-header')
    && [...document.querySelectorAll('#root[data-workbench-boot="ready"] .top-header button')]
      .filter(node => visible(node) && /^切换(?:深色|浅色)$/.test(node.textContent.replace(/^[☀☾]/, '').trim())).length === 1;
  const bodyText = document.body.innerText, title = document.title || '';
  const includesKeyword = (value, keyword) => value.toLowerCase().includes(keyword.toLowerCase());
  const keywords = window.__APS_ERROR_PAGE_KEYWORDS__;
  const matchedErrorKeyword = keywords.find(keyword => includesKeyword(title, keyword))
    || (!hasAppShell && keywords.find(keyword => includesKeyword(bodyText, keyword))) || '';
  const finalPath = location.pathname + location.search;
  const missingExpectedTexts = expected.texts.filter(text => !bodyText.includes(text));
  const missingExpectedIds = expected.selectors.filter(selector => !visible(document.querySelector(selector)));
  const labelNodes = Object.keys(requiredControls).flatMap(selector => [...document.querySelectorAll(selector)].flatMap(input => [...(input.labels || [])]));
  const contrastText = textNodes([...summaries, ...notices, ...labelNodes, ...nodes(expected.multiline || [])]);
  const pluginBody = expected.plugin_audit ? document.querySelector('.sm-detail pre')?.textContent : null;
  return JSON.stringify({
    case: expected.case, path: finalPath, expectedPath: expected.path, pathMismatch: finalPath !== expected.path,
    httpStatus, url: location.href, title, hasAppShell, pageLooksError: httpStatus >= 500 || !!matchedErrorKeyword,
    matchedErrorKeyword, missingExpectedTexts, missingExpectedIds, width: innerWidth, bodyOverflow: maxScrollWidth > innerWidth + 1,
    maxScrollWidth, scrollMetrics, overflowOffenders, toggleCount: toggleChecks.length,
    toggleOverlapCount: toggleChecks.filter(row => !row.ok).length, toggleChecks, visibleNotices: notices.length,
    darkTheme: document.documentElement.dataset.theme === 'dark', darkSummaryCount: summaries.length,
    darkSummaryBadCount: summaries.filter(badDarkBackground).length, darkLowContrastSummaryCount: summaries.filter(lowContrast).length,
    darkLowContrastTextCount: contrastText.filter(lowContrast).length, darkNoticeBadCount: notices.filter(badDarkBackground).length,
    missingVisualSamples, multilineTableChecks, multilineTableDetails, multilineTextDetails, requiredToggleIds: Object.keys(requiredControls), missingRequiredToggleIds,
    pluginAudit: expected.plugin_audit ? { publicBodyMatches: pluginBody === expected.identity.startup_public_body,
      privateCanaryAbsent: !!pluginBody && !pluginBody.includes(expected.identity.private_path_canary),
      truncationMarkerAbsent: !!pluginBody && !document.querySelector('.sm-detail').textContent.includes('本条详情已截断'),
      claim: 'persisted public startup diagnostic, not plugin health' } : null,
  });
}

export function buildPageInspectionExpression(httpStatus) {
  return '(' + inspectCurrentPage.toString() + ')(' + JSON.stringify(httpStatus) + ')';
}
