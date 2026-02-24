from __future__ import annotations

import json
import os
import re
import subprocess


def _find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _run_hash_runtime_check(js_path: str) -> dict:
    node_code = r"""
const fs = require("fs");

const jsPath = String(process.env.APS_CONFIG_MANUAL_JS || "");
if (!jsPath) {
  console.error("APS_CONFIG_MANUAL_JS missing");
  process.exit(2);
}
const src = fs.readFileSync(jsPath, "utf8");

function makeClassList() {
  const bucket = new Set();
  return {
    add(cls) { bucket.add(String(cls)); },
    remove(cls) { bucket.delete(String(cls)); },
    contains(cls) { return bucket.has(String(cls)); },
  };
}

const runtime = {
  querySelectorCalls: 0,
  scrolled: false,
};
const headingById = Object.create(null);
const tocAnchors = [];

const contentEl = {
  id: "content",
  innerHTML: "",
  querySelectorAll(selector) {
    if (selector !== "h2, h3") return [];
    const nodes = [];
    const re = /<h([23])\s+id="([^"]+)">([\s\S]*?)<\/h\1>/g;
    let m;
    while ((m = re.exec(this.innerHTML))) {
      const level = String(m[1] || "");
      const id = String(m[2] || "");
      const text = String(m[3] || "").replace(/<[^>]+>/g, "");
      let el = headingById[id];
      if (!el) {
        el = {
          id,
          tagName: level === "2" ? "H2" : "H3",
          textContent: text,
          scrollIntoView() {
            runtime.scrolled = true;
          },
        };
        headingById[id] = el;
      } else {
        el.tagName = level === "2" ? "H2" : "H3";
        el.textContent = text;
      }
      nodes.push(el);
    }
    return nodes;
  },
};

function createElement(tagName) {
  const tag = String(tagName || "").toUpperCase();
  const el = {
    tagName: tag,
    children: [],
    attributes: {},
    textContent: "",
    className: "",
    classList: makeClassList(),
    addEventListener() {},
    appendChild(child) {
      this.children.push(child);
    },
    setAttribute(name, value) {
      const k = String(name || "");
      const v = String(value || "");
      this.attributes[k] = v;
      this[k] = v;
    },
    getAttribute(name) {
      const k = String(name || "");
      if (Object.prototype.hasOwnProperty.call(this, k)) return this[k];
      if (Object.prototype.hasOwnProperty.call(this.attributes, k)) return this.attributes[k];
      return null;
    },
  };
  if (tag === "A") tocAnchors.push(el);
  return el;
}

const tocListEl = {
  id: "toc-list",
  textContent: "",
  children: [],
  appendChild(child) {
    this.children.push(child);
  },
};
const tocToggleBtn = { id: "tocToggleBtn", addEventListener() {} };
const tocEl = { id: "toc", classList: { toggle() {} } };

const documentStub = {
  readyState: "complete",
  getElementById(id) {
    const key = String(id || "");
    if (key === "content") return contentEl;
    if (key === "toc-list") return tocListEl;
    if (key === "tocToggleBtn") return tocToggleBtn;
    if (key === "toc") return tocEl;
    return headingById[key] || null;
  },
  querySelector(selector) {
    runtime.querySelectorCalls += 1;
    if (String(selector || "") === "#1-测试标题") {
      throw new SyntaxError("invalid selector for leading digit id");
    }
    return null;
  },
  querySelectorAll(selector) {
    if (String(selector || "") === ".manual-toc a") return tocAnchors;
    return [];
  },
  createElement,
  createDocumentFragment() {
    return {
      children: [],
      appendChild(child) {
        this.children.push(child);
      },
    };
  },
  addEventListener(_evt, cb) {
    if (typeof cb === "function") cb();
  },
};

global.document = documentStub;
global.window = {
  __APS_CONFIG_MANUAL__: {
    manualText: "## 1. 测试标题\n\n段落内容",
  },
  location: {
    hash: "#1-%E6%B5%8B%E8%AF%95%E6%A0%87%E9%A2%98",
  },
};
global.history = { pushState() {} };
global.setTimeout = function (fn) {
  if (typeof fn === "function") fn();
  return 1;
};

let errorMsg = "";
try {
  eval(src);
} catch (err) {
  errorMsg = String((err && err.message) || err || "");
}

const hashId = decodeURIComponent(global.window.location.hash || "").slice(1);
const activeMatched = tocAnchors.some((a) => {
  return a.getAttribute("href") === ("#" + hashId) && a.classList.contains("active");
});
const targetExists = Boolean(headingById[hashId]);
const ok = (!errorMsg) && targetExists && runtime.scrolled && activeMatched;
process.stdout.write(JSON.stringify({
  ok,
  errorMsg,
  targetExists,
  scrolled: runtime.scrolled,
  activeMatched,
  querySelectorCalls: runtime.querySelectorCalls,
}));
"""
    env = dict(os.environ)
    env["APS_CONFIG_MANUAL_JS"] = js_path
    p = subprocess.run(
        ["node", "-"],
        input=node_code,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if p.returncode != 0:
        raise RuntimeError(f"node 执行失败：rc={p.returncode} stderr={p.stderr[:500]!r}")
    try:
        return json.loads(p.stdout or "{}")
    except Exception as e:
        raise RuntimeError(f"node 输出解析失败：{e} stdout={p.stdout[:500]!r}")


def main() -> None:
    repo_root = _find_repo_root()
    js_path = os.path.join(repo_root, "static", "js", "config_manual.js")
    tpl_path = os.path.join(repo_root, "templates", "scheduler", "config_manual.html")

    js = _read(js_path)
    tpl = _read(tpl_path)

    # 1) 模板-脚本契约
    assert "window.__APS_CONFIG_MANUAL__" in tpl, "模板缺少 manual 配置注入"
    assert "manualText" in tpl, "模板缺少 manualText 注入字段"
    assert "js/config_manual.js" in tpl, "模板未加载 config_manual.js"
    assert 'id="tocToggleBtn"' in tpl, "模板缺少目录切换按钮 ID"
    assert 'id="toc-list"' in tpl, "模板缺少目录容器"
    assert 'id="content"' in tpl, "模板缺少正文容器"

    # 2) Markdown 解析核心能力
    for needle in (
        "function escapeHtml(",
        "function slugifyHeading(",
        "function isSafeHref(",
        "function renderInline(",
        "function renderMarkdown(",
        "function renderToc(",
        "function setupScrollSpy(",
        "function initManual(",
    ):
        assert needle in js, f"config_manual.js 缺少核心函数: {needle}"

    # 3) 安全约束：危险协议应被过滤（允许注释提及 javascript:）
    assert 'if (!isSafeHref(href))' in js, "链接白名单过滤缺失"
    assert 'if (lower.startsWith("http://") || lower.startsWith("https://")) return true;' in js, "http/https 白名单缺失"
    assert 'if (lower.startsWith("mailto:")) return true;' in js, "mailto 白名单缺失"
    assert "return false;" in js, "危险协议默认拒绝逻辑缺失"
    assert 'startsWith("javascript:")) return true' not in js, "错误地放开了 javascript: 协议"
    assert "noopener noreferrer" in js, "外链安全属性缺失"

    # 4) 兼容性降级约束
    assert 'if (!("IntersectionObserver" in window)) return;' in js, "缺少 IntersectionObserver 降级"
    assert re.search(r"scrollIntoView\(\{ behavior: \"smooth\", block: \"start\" \}\)", js), "缺少平滑滚动主路径"
    assert "target.scrollIntoView();" in js, "缺少滚动降级路径"

    # 5) hash 初始化约束：数字前缀锚点不应导致初始化中断
    assert "if (window.location.hash)" in js, "缺少 hash 初始化分支"
    assert "decodeURIComponent(window.location.hash)" in js, "缺少 hash 解码逻辑"
    assert "document.getElementById(hashId)" in js, "hash 分支应优先使用 getElementById"
    assert "document.querySelector(hash)" in js, "hash 分支应保留 querySelector 降级"
    runtime_ret = _run_hash_runtime_check(js_path)
    if not runtime_ret.get("ok"):
        raise RuntimeError(f"hash 运行时回归失败：{runtime_ret}")

    print("OK")


if __name__ == "__main__":
    main()

