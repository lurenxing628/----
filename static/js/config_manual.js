(() => {
  "use strict";

  const cfg = window.__APS_CONFIG_MANUAL__ || {};
  const rawMarkdown = typeof cfg.manualText === "string" ? cfg.manualText : "";

  function normalizeNewlines(s) {
    return (s || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  }

  function escapeHtml(text) {
    const s = ("" + (text == null ? "" : text));
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // HTML 属性值转义（避免 href 等属性拼接注入）
  // - 保留既有实体（&amp; / &#39; / &#x22; ...），避免二次转义导致 URL 变化
  function escapeHtmlAttr(text) {
    const s = ("" + (text == null ? "" : text));
    return s
      .replace(/&(?![a-zA-Z]+;|#\d+;|#x[0-9a-fA-F]+;)/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // 生成与 Markdown 目录链接兼容的锚点 id：
  // - "1. 标题" -> "1-标题"
  // - 去掉空格/标点（保留字母数字/中文/下划线/连字符）
  function slugifyHeading(text) {
    let t = (text || "").trim();
    // 去掉可能出现在标题里的行内标记（以免影响 id）
    t = t.replace(/`([^`]+)`/g, "$1");
    t = t.replace(/\*\*([^*]+)\*\*/g, "$1");
    t = t.replace(/\*([^*]+)\*/g, "$1");
    // 处理常见的序号前缀：1. / 1． / 1。
    t = t.replace(/^(\d+)\s*[\.．。]\s*/g, "$1-");
    t = t.toLowerCase();
    // 仅保留：字母数字下划线、中文、连字符
    t = t.replace(/[^\w\u4e00-\u9fa5-]+/g, "");
    // 连字符收敛 + 去首尾
    t = t.replace(/-+/g, "-").replace(/^-+/, "").replace(/-+$/, "");
    return t || "section";
  }

  // 链接协议白名单：只把安全 href 渲染成 <a>（防止 javascript: 等注入）
  function isSafeHref(href) {
    const h = (href || "").trim();
    if (!h) return false;
    const lower = h.toLowerCase();
    if (lower.startsWith("#")) return true;
    if (lower.startsWith("http://") || lower.startsWith("https://")) return true;
    // 避免协议相对 URL：//example.com
    if (lower.startsWith("//")) return false;
    if (lower.startsWith("/")) return true;
    if (lower.startsWith("./") || lower.startsWith("../")) return true;
    if (lower.startsWith("mailto:")) return true;
    return false;
  }

  function renderInline(text) {
    let s = escapeHtml(text);

    // 行内代码
    s = s.replace(/`([^`]+)`/g, function (_m, code) {
      return "<code>" + code + "</code>";
    });

    // 加粗
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    // 斜体（尽量保守，避免吞掉加粗等结构）
    s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");

    // 链接（内部/外部）
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_m, label, url) {
      const href = (url || "").trim();
      const text = label || "";
      if (!isSafeHref(href)) {
        return text;
      }
      const hrefEscaped = escapeHtmlAttr(href);
      if (href.startsWith("#")) {
        return '<a href="' + hrefEscaped + '">' + text + "</a>";
      }
      return '<a href="' + hrefEscaped + '" target="_blank" rel="noopener noreferrer">' + text + "</a>";
    });

    return s;
  }

  function isHrLine(line) {
    return (line || "").trim() === "---";
  }

  function isFenceStart(line) {
    return (line || "").trim().startsWith("```");
  }

  function isHeadingLine(line) {
    return /^(#{1,3})\s+/.test(line || "");
  }

  function parseHeadingLine(line) {
    const m = (line || "").match(/^(#{1,3})\s+(.+)$/);
    if (!m) return null;
    return { level: m[1].length, text: (m[2] || "").trim() };
  }

  function isBlockquoteLine(line) {
    return /^\s*>\s?/.test(line || "");
  }

  function stripBlockquotePrefix(line) {
    return (line || "").replace(/^\s*>\s?/, "");
  }

  function isTableRowLine(line) {
    const t = (line || "").trim();
    return t.startsWith("|") && t.endsWith("|") && t.includes("|");
  }

  function isTableSeparatorLine(line) {
    // 形如：|---|---| 或 |:---|---:|
    return /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/.test(line || "");
  }

  function splitTableRow(line) {
    const t = (line || "").trim().replace(/^\|/, "").replace(/\|$/, "");
    return t.split("|").map((c) => (c || "").trim());
  }

  function parseListItem(line) {
    const mOl = (line || "").match(/^(\s*)(\d+)\.\s+(.+)$/);
    if (mOl) {
      const indent = (mOl[1] || "").length;
      return { type: "ol", indentLevel: Math.floor(indent / 2), text: (mOl[3] || "").trim() };
    }
    const mUl = (line || "").match(/^(\s*)[-+*]\s+(.+)$/);
    if (mUl) {
      const indent = (mUl[1] || "").length;
      return { type: "ul", indentLevel: Math.floor(indent / 2), text: (mUl[2] || "").trim() };
    }
    return null;
  }

  function closeAllLists(state) {
    while (state.listStack.length > 0) {
      const cur = state.listStack[state.listStack.length - 1];
      if (cur.liOpen) {
        state.out.push("</li>");
        cur.liOpen = false;
      }
      state.out.push("</" + cur.type + ">");
      state.listStack.pop();
    }
  }

  function ensureList(state, level, type) {
    // 收缩到目标层级
    while (state.listStack.length > level + 1) {
      const cur = state.listStack[state.listStack.length - 1];
      if (cur.liOpen) {
        state.out.push("</li>");
        cur.liOpen = false;
      }
      state.out.push("</" + cur.type + ">");
      state.listStack.pop();
    }

    // 同层类型不一致：关闭并重开
    if (state.listStack.length === level + 1) {
      const cur = state.listStack[level];
      if (cur.type !== type) {
        if (cur.liOpen) {
          state.out.push("</li>");
          cur.liOpen = false;
        }
        state.out.push("</" + cur.type + ">");
        state.listStack.pop();
      }
    }

    // 扩展到目标层级
    while (state.listStack.length < level + 1) {
      // 嵌套 list 必须放在父级 li 内
      if (state.listStack.length > 0) {
        const parent = state.listStack[state.listStack.length - 1];
        if (!parent.liOpen) {
          state.out.push("<li>");
          parent.liOpen = true;
        }
      }
      state.out.push("<" + type + ">");
      state.listStack.push({ type: type, liOpen: false });
    }

    // 开始新 item 前，关闭同层上一条 li
    const cur = state.listStack[level];
    if (cur.liOpen) {
      state.out.push("</li>");
      cur.liOpen = false;
    }
  }

  function renderMarkdown(md) {
    const text = normalizeNewlines(md);
    const lines = text.split("\n");
    const state = { out: [], listStack: [] };
    let paragraph = [];
    let i = 0;

    function flushParagraph() {
      if (paragraph.length > 0) {
        const joined = paragraph.join(" ").trim();
        if (joined) state.out.push("<p>" + renderInline(joined) + "</p>");
        paragraph = [];
      }
    }

    while (i < lines.length) {
      const line = lines[i] == null ? "" : lines[i];

      // fenced code block
      if (isFenceStart(line)) {
        flushParagraph();
        closeAllLists(state);
        const fence = (line || "").trim();
        // language is optional: ```js
        const lang = fence.replace(/^```/, "").trim();
        const codeLines = [];
        i += 1;
        while (i < lines.length && !isFenceStart(lines[i])) {
          codeLines.push(lines[i] || "");
          i += 1;
        }
        // consume ending fence if present
        if (i < lines.length && isFenceStart(lines[i])) i += 1;
        const code = escapeHtml(codeLines.join("\n"));
        state.out.push('<pre><code class="' + escapeHtml(lang) + '">' + code + "</code></pre>");
        continue;
      }

      // blank line
      if ((line || "").trim() === "") {
        flushParagraph();
        closeAllLists(state);
        i += 1;
        continue;
      }

      // horizontal rule
      if (isHrLine(line)) {
        flushParagraph();
        closeAllLists(state);
        state.out.push("<hr>");
        i += 1;
        continue;
      }

      // heading
      if (isHeadingLine(line)) {
        const h = parseHeadingLine(line);
        if (h) {
          flushParagraph();
          closeAllLists(state);
          const id = slugifyHeading(h.text);
          state.out.push("<h" + h.level + ' id="' + id + '">' + renderInline(h.text) + "</h" + h.level + ">");
          i += 1;
          continue;
        }
      }

      // table
      if (isTableRowLine(line) && i + 1 < lines.length && isTableSeparatorLine(lines[i + 1])) {
        flushParagraph();
        closeAllLists(state);
        const headerCells = splitTableRow(line);
        i += 2; // skip header + separator
        const bodyRows = [];
        while (i < lines.length && isTableRowLine(lines[i])) {
          bodyRows.push(splitTableRow(lines[i]));
          i += 1;
        }
        let tableHtml = "<table><thead><tr>";
        headerCells.forEach((c) => {
          tableHtml += "<th>" + renderInline(c) + "</th>";
        });
        tableHtml += "</tr></thead>";
        if (bodyRows.length > 0) {
          tableHtml += "<tbody>";
          bodyRows.forEach((r) => {
            tableHtml += "<tr>";
            r.forEach((c) => {
              tableHtml += "<td>" + renderInline(c) + "</td>";
            });
            tableHtml += "</tr>";
          });
          tableHtml += "</tbody>";
        }
        tableHtml += "</table>";
        state.out.push(tableHtml);
        continue;
      }

      // blockquote (group consecutive lines)
      if (isBlockquoteLine(line)) {
        flushParagraph();
        closeAllLists(state);
        const quoteLines = [];
        while (i < lines.length && isBlockquoteLine(lines[i])) {
          quoteLines.push(stripBlockquotePrefix(lines[i]));
          i += 1;
        }
        const inner = quoteLines
          .map((x) => (x || "").trim())
          .filter((x) => x !== "")
          .map((x) => "<p>" + renderInline(x) + "</p>")
          .join("");
        state.out.push("<blockquote>" + inner + "</blockquote>");
        continue;
      }

      // list item
      const li = parseListItem(line);
      if (li) {
        flushParagraph();
        ensureList(state, li.indentLevel, li.type);
        const cur = state.listStack[li.indentLevel];
        state.out.push("<li>" + renderInline(li.text));
        cur.liOpen = true;
        i += 1;
        continue;
      }

      // normal text line -> paragraph
      closeAllLists(state);
      paragraph.push((line || "").trim());
      i += 1;
    }

    flushParagraph();
    closeAllLists(state);
    return state.out.join("\n");
  }

  // 渲染目录
  function renderToc(headings) {
    const tocList = document.getElementById("toc-list");
    if (!tocList) return;
    tocList.textContent = "";

    const frag = document.createDocumentFragment();
    headings.forEach((h) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = "#" + h.id;
      a.textContent = h.title; // 使用纯文本
      a.className = h.level === 3 ? "toc-h3" : "";
      a.addEventListener("click", function (e) {
        e.preventDefault();
        const target = document.getElementById(h.id);
        if (target) {
          try {
            target.scrollIntoView({ behavior: "smooth", block: "start" });
          } catch (_e2) {
            try {
              target.scrollIntoView();
            } catch (_e3) {
              // ignore
            }
          }
          // 更新 URL hash
          history.pushState(null, null, "#" + h.id);
          // 更新激活状态
          updateActiveLink(h.id);
        }
      });
      li.appendChild(a);
      frag.appendChild(li);
    });
    tocList.appendChild(frag);
  }

  // 更新激活状态
  function updateActiveLink(activeId) {
    document.querySelectorAll(".manual-toc a").forEach((a) => {
      a.classList.remove("active");
      if (a.getAttribute("href") === "#" + activeId) {
        a.classList.add("active");
      }
    });
  }

  // 滚动监听
  function setupScrollSpy(headings) {
    if (!("IntersectionObserver" in window)) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) updateActiveLink(entry.target.id);
        });
      },
      { rootMargin: "-20% 0px -70% 0px" }
    );
    headings.forEach((h) => {
      const el = document.getElementById(h.id);
      if (el) observer.observe(el);
    });
  }

  // 初始化
  function initManual() {
    const contentEl = document.getElementById("content");
    if (!contentEl) return;

    const tocToggleBtn = document.getElementById("tocToggleBtn");
    if (tocToggleBtn) {
      tocToggleBtn.addEventListener("click", function () {
        const toc = document.getElementById("toc");
        if (toc) toc.classList.toggle("show");
      });
    }

    const html = renderMarkdown(rawMarkdown);
    contentEl.innerHTML = html;

    // 基于 DOM 生成目录（更稳健）
    const nodes = contentEl.querySelectorAll("h2, h3");
    const headings = Array.prototype.slice.call(nodes).map((n) => ({
      id: n.id,
      title: (n.textContent || "").trim(),
      level: n.tagName === "H2" ? 2 : 3,
    }));
    renderToc(headings);
    setupScrollSpy(headings);

    // 如果 URL 有 hash，跳转到对应位置
    if (window.location.hash) {
      const hash = decodeURIComponent(window.location.hash);
      const hashId = hash.startsWith("#") ? hash.slice(1) : hash;
      let target = null;
      // 优先按 id 精确定位（支持数字开头的锚点）
      if (hashId) {
        target = document.getElementById(hashId);
      }
      // 回退到 querySelector，并兜底非法选择器异常
      if (!target && hash.startsWith("#")) {
        try {
          target = document.querySelector(hash);
        } catch (_eHashSelector) {
          target = null;
        }
      }
      if (target) {
        setTimeout(() => {
          try {
            target.scrollIntoView({ behavior: "smooth", block: "start" });
          } catch (_e2) {
            try {
              target.scrollIntoView();
            } catch (_e3) {
              // ignore
            }
          }
          updateActiveLink(hashId);
        }, 100);
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initManual);
  } else {
    initManual();
  }
})();

