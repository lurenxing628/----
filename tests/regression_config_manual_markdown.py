from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from flask import url_for

LEGACY_EXCEL_ENTRY_TERMS = (
    "零件工艺路线（Excel导入/导出）",
    "零件工序工时（Excel导入/导出）",
    "人员基本信息（Excel导入/导出）",
    "设备信息（Excel导入/导出）",
    "人员设备关联（Excel）",
    "设备人员关联（Excel）",
    "Excel 导入/导出",
    "Excel导入/导出",
    "Excel 导入导出",
    "Excel导入导出",
)

MANUAL_BATCH_MAINTENANCE_SECTIONS = (
    "工种配置",
    "供应商配置",
    "零件工艺路线",
    "零件工序工时",
    "人员基本信息",
    "设备信息",
    "人员设备关联",
    "工作日历",
    "个人工作日历",
    "批次信息",
)


def _find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _slugify_heading(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    t = re.sub(r"^(\d+)\s*[\.．。]\s*", r"\1-", t)
    t = t.lower()
    t = re.sub(r"[^\w\u4e00-\u9fa5-]+", "", t)
    t = re.sub(r"-+", "-", t).strip("-")
    return t or "section"


def _extract_heading_ids(markdown_text: str) -> set[str]:
    ids: set[str] = set()
    for line in markdown_text.splitlines():
        m = re.match(r"^(#{2,4})\s+(.+)$", line.strip())
        if not m:
            continue
        ids.add(_slugify_heading(m.group(2)))
    return ids


def _extract_internal_hashes(markdown_text: str) -> list[str]:
    refs: list[str] = []
    for _label, href in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", markdown_text):
        link = (href or "").strip()
        if link.startswith("#"):
            refs.append(link[1:])
    return refs


def _find_legacy_excel_entry_terms(markdown_text: str) -> list[str]:
    hits: list[str] = []
    for line_no, line in enumerate(markdown_text.splitlines(), start=1):
        for term in LEGACY_EXCEL_ENTRY_TERMS:
            if _is_historical_legacy_entry_note(line, term):
                continue
            if term in line:
                hits.append(f"{line_no}: {term} -> {line.strip()}")
                break
    return hits


def _is_historical_legacy_entry_note(line: str, term: str) -> bool:
    if term not in ("Excel 导入导出", "Excel导入导出"):
        return False
    return "老资料" in line and "旧入口" in line and "批量维护" in line


def _find_heading_entry_line(markdown_text: str, section_name: str) -> str:
    lines = markdown_text.splitlines()
    for idx, line in enumerate(lines):
        if not re.match(r"^####\s+", line):
            continue
        heading_text = re.sub(r"^####\s+\d+(?:\.\d+)*\s+", "", line).strip()
        is_target_heading = heading_text == section_name or heading_text.startswith(f"{section_name}（")
        if not is_target_heading:
            continue
        for next_line in lines[idx + 1 :]:
            if re.match(r"^####\s+", next_line):
                break
            if re.match(r"^(?:\*\*进入方式\*\*|进入方式|入口)[:：]", next_line):
                return next_line.strip()
    raise RuntimeError(f"说明书缺少“{section_name}”章节的进入方式")


def _assert_manual_uses_batch_maintenance_entry_names(markdown_text: str) -> None:
    legacy_hits = _find_legacy_excel_entry_terms(markdown_text)
    assert not legacy_hits, "说明书仍出现旧 Excel 入口叫法：\n" + "\n".join(legacy_hits[:20])

    missing_batch_maintenance = []
    for section_name in MANUAL_BATCH_MAINTENANCE_SECTIONS:
        entry_line = _find_heading_entry_line(markdown_text, section_name)
        if "批量维护" not in entry_line:
            missing_batch_maintenance.append(f"{section_name}: {entry_line}")
    assert not missing_batch_maintenance, "说明书主流程入口必须叫“批量维护”：\n" + "\n".join(missing_batch_maintenance)


def _run_hash_runtime_check(js_path: str, mode: str) -> dict:
    node_code = r"""
const fs = require("fs");

const jsPath = String(process.env.APS_CONFIG_MANUAL_JS || "");
const runtimeMode = String(process.env.APS_CONFIG_MANUAL_RUNTIME_MODE || "full");
if (!jsPath) {
  console.error("APS_CONFIG_MANUAL_JS missing");
  process.exit(2);
}
const src = fs.readFileSync(jsPath, "utf8");
const config = runtimeMode === "page"
  ? {
      mode: "page",
      manualText: "",
      currentManual: {
        title: "甘特图",
        summary: "页面模式摘要",
        sections: [
          { title: "进入前准备", body_md: "- 先选版本\n- 再选视角" },
          { title: "视图切换", body_md: "- 设备视角看负荷\n- 人员视角看排班" },
        ],
      },
      relatedManuals: [],
    }
  : {
      mode: "full",
      manualText: "## 1. 测试标题\n\n段落内容",
      currentManual: null,
      relatedManuals: [],
    };

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
    if (selector !== "h2, h3, h4" && selector !== "h2, h3") return [];
    const nodes = [];
    const re = /<h([234])\s+id="([^"]+)">([\s\S]*?)<\/h\1>/g;
    let m;
    while ((m = re.exec(this.innerHTML))) {
      const level = String(m[1] || "");
      const id = String(m[2] || "");
      const text = String(m[3] || "").replace(/<[^>]+>/g, "");
      let el = headingById[id];
      if (!el) {
        el = {
          id,
          tagName: level === "2" ? "H2" : (level === "3" ? "H3" : "H4"),
          textContent: text,
          scrollIntoView() {
            runtime.scrolled = true;
          },
        };
        headingById[id] = el;
      } else {
        el.tagName = level === "2" ? "H2" : (level === "3" ? "H3" : "H4");
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
    if (key === "aps-config-manual-data") {
      return { id: key, textContent: JSON.stringify(config) };
    }
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
  __APS_CONFIG_MANUAL__: config,
  location: {
    hash: runtimeMode === "page" ? "#%E8%BF%9B%E5%85%A5%E5%89%8D%E5%87%86%E5%A4%87" : "#1-%E6%B5%8B%E8%AF%95%E6%A0%87%E9%A2%98",
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
const contentOk = runtimeMode === "page"
  ? contentEl.innerHTML.includes("甘特图") && contentEl.innerHTML.includes("页面模式摘要")
  : contentEl.innerHTML.includes("测试标题");
const ok = (!errorMsg) && targetExists && runtime.scrolled && activeMatched;
process.stdout.write(JSON.stringify({
  ok: ok && contentOk,
  errorMsg,
  targetExists,
  scrolled: runtime.scrolled,
  activeMatched,
  querySelectorCalls: runtime.querySelectorCalls,
  contentOk,
}));
"""
    env = dict(os.environ)
    env["APS_CONFIG_MANUAL_JS"] = js_path
    env["APS_CONFIG_MANUAL_RUNTIME_MODE"] = mode
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


def _prepare_env(tmpdir: str) -> None:
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(Path(tmpdir) / "aps_test.db")
    os.environ["APS_LOG_DIR"] = str(Path(tmpdir) / "logs")
    os.environ["APS_BACKUP_DIR"] = str(Path(tmpdir) / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(Path(tmpdir) / "templates_excel")
    os.environ["SECRET_KEY"] = "aps-config-manual-markdown"


def _load_app(repo_root: str):
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def _mode_headers(ui_mode: str) -> dict[str, str]:
    return {"Cookie": f"aps_ui_mode={ui_mode}"}


def _build_url(app, endpoint: str, **values: str) -> str:
    with app.test_request_context():
        return url_for(endpoint, **values)


def _extract_json_config(html_text: str) -> dict:
    m = re.search(
        r'<script id="aps-config-manual-data" type="application/json">([\s\S]*?)</script>',
        html_text,
        flags=re.S,
    )
    if not m:
        raise RuntimeError("页面缺少 aps-config-manual-data JSON 数据块")
    raw = (m.group(1) or "").strip()
    if not raw:
        raise RuntimeError("aps-config-manual-data JSON 数据块为空")
    return json.loads(raw)


def _extract_paragraph_containing(markdown_text: str, needle: str) -> str:
    for paragraph in re.split(r"\n\s*\n", markdown_text):
        if needle in paragraph:
            return paragraph.strip()
    raise AssertionError(f"说明书缺少段落：{needle}")


def _assert_scheduler_manual_required_content(markdown_text: str, label: str) -> None:
    for needle in ("TRUE/FALSE", "NaN", "Inf", "Infinity", "5e0", "1E2", "最后更新：2026年4月"):
        assert needle in markdown_text, f"{label} 缺少说明书必备内容：{needle}"

    for needle in (
        "旧模板中已有数据行不会被系统擅自改写",
        "新填数据请使用 `自制`/`外协`",
        "批次自动生成工序时的模板提醒，是当前页局部提醒",
        "正式排产或模拟排产成功后的排产结果提醒",
        "可以到系统历史查看",
        "不填版本、版本为空，或版本填 `latest`",
        "输入不存在的数字版本时",
        "输入 `abc` 这类不是数字的版本号",
    ):
        assert needle in markdown_text, f"{label} 缺少说明书必备内容：{needle}"

    batch_warning_paragraph = _extract_paragraph_containing(markdown_text, "自动生成批次工序时产生提醒")
    assert "当前页面确认写入后只会展示去重后的前 3 条提醒" in batch_warning_paragraph
    assert "另有 X 条提醒" in batch_warning_paragraph or "剩余提醒" in batch_warning_paragraph
    assert "系统历史" not in batch_warning_paragraph, f"{label} 的批次剩余提醒口径不应再要求去系统历史：{batch_warning_paragraph}"


def main() -> None:
    repo_root = _find_repo_root()
    js_path = os.path.join(repo_root, "static", "js", "config_manual.js")
    tpl_path = os.path.join(repo_root, "templates", "scheduler", "config_manual.html")
    tpl_v2_path = os.path.join(repo_root, "web_new_test", "templates", "scheduler", "config_manual.html")
    manual_path = os.path.join(repo_root, "static", "docs", "scheduler_manual.md")
    manual_v2_path = os.path.join(repo_root, "web_new_test", "static", "docs", "scheduler_manual.md")

    js = _read(js_path)
    tpl = _read(tpl_path)
    tpl_v2 = _read(tpl_v2_path)
    manual_text = _read(manual_path)
    manual_v2_text = _read(manual_v2_path) if os.path.exists(manual_v2_path) else None

    # 1) 模板-脚本契约（V1/V2 必须一致）
    for template_src, label in ((tpl, "v1"), (tpl_v2, "v2")):
        for needle in (
            'id="aps-config-manual-data"',
            'type="application/json"',
            '"mode": manual_mode',
            '"currentManual": current_manual',
            '"relatedManuals": related_manuals',
            "js/config_manual.js",
            'id="tocToggleBtn"',
            'id="toc-list"',
            'id="content"',
            "manual-main-column",
            "manual-related-panel",
            "manual_mode == 'page'",
            "fallback_text if manual_mode == 'page' else manual_text",
            "查看完整原文对应章节",
            "返回刚才页面",
        ):
            assert needle in template_src, f"{label} 模板缺少契约片段: {needle}"
    assert "相关模块说明" in tpl and "相关模块说明" in tpl_v2, "V1/V2 模板缺少相关模块区块"

    # 2) Markdown 解析核心能力
    for needle in (
        "function readConfig(",
        "function escapeHtml(",
        "function slugifyHeading(",
        "function isSafeHref(",
        "function renderInline(",
        "function renderMarkdown(",
        "function buildPageMarkdown(",
            "function renderEmbeddedMarkdownBlocks(",
        "function renderToc(",
        "function setupScrollSpy(",
        "function initManual(",
    ):
        assert needle in js, f"config_manual.js 缺少核心函数: {needle}"
    assert 'const dataEl = document.getElementById("aps-config-manual-data");' in js, "JS 缺少 JSON 数据块读取入口"
    assert "return JSON.parse(raw);" in js, "JS 缺少 JSON 配置解析"
    assert "return window.__APS_CONFIG_MANUAL__ || {};" in js, "JS 缺少旧 window 契约兜底"
    assert 'const manualMode = cfg.mode === "page" ? "page" : "full";' in js, "JS 缺少双模式判定"
    assert "const currentManual = cfg.currentManual" in js, "JS 缺少 currentManual 契约"
    assert 'const markdownSource = manualMode === "page" ? buildPageMarkdown(currentManual) : rawMarkdown;' in js, "JS 缺少双模式渲染分支"

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
    runtime_full = _run_hash_runtime_check(js_path, mode="full")
    if not runtime_full.get("ok"):
        raise RuntimeError(f"整本模式 hash 运行时回归失败：{runtime_full}")
    runtime_page = _run_hash_runtime_check(js_path, mode="page")
    if not runtime_page.get("ok"):
        raise RuntimeError(f"页面模式 hash 运行时回归失败：{runtime_page}")

    # 6) Markdown 一致性：事实源标题、镜像副本、内部锚点
    assert manual_text.startswith("# 系统使用说明"), "主说明书标题未更新为“系统使用说明”"
    assert manual_v2_text is not None, f"未找到 v2 说明书镜像副本：{manual_v2_path}"
    assert manual_text == manual_v2_text, "主说明书与 v2 镜像副本必须完全同步"
    _assert_scheduler_manual_required_content(manual_text, "主说明书")
    _assert_scheduler_manual_required_content(manual_v2_text, "v2 说明书镜像副本")
    _assert_manual_uses_batch_maintenance_entry_names(manual_text)
    heading_ids = _extract_heading_ids(manual_text)
    internal_hashes = _extract_internal_hashes(manual_text)
    missing_hashes = [item for item in internal_hashes if item not in heading_ids]
    assert not missing_hashes, f"说明书存在未命中的内部锚点：{missing_hashes[:10]}"

    # 7) 行为契约：真实请求验证双模式、JSON 数据块与 noscript 回退
    tmpdir = tempfile.mkdtemp(prefix="aps_regression_config_manual_")
    _prepare_env(tmpdir)
    app = _load_app(repo_root)
    client = app.test_client()
    material_src = _build_url(app, "material.materials_page") + "?"

    for ui_mode in ("v1", "v2"):
        full_url = _build_url(app, "scheduler.config_manual_page", src=material_src)
        full_resp = client.get(full_url, headers=_mode_headers(ui_mode))
        if full_resp.status_code != 200:
            raise RuntimeError(f"{ui_mode} 模式整本说明书请求失败：{full_resp.status_code}")
        full_html = full_resp.get_data(as_text=True)
        full_cfg = _extract_json_config(full_html)
        assert full_cfg.get("mode") == "full", f"{ui_mode} 模式整本说明书 JSON mode 异常"
        assert full_cfg.get("manualText") == manual_text, f"{ui_mode} 模式整本说明书 JSON 应保留完整 manualText"
        assert full_cfg.get("currentManual") is None, f"{ui_mode} 模式整本说明书不应包含 currentManual"
        assert full_cfg.get("relatedManuals") == [], f"{ui_mode} 模式整本说明书不应包含 relatedManuals"
        assert "当前页面主题：" not in full_html, f"{ui_mode} 模式整本说明书不应出现页面级主题"
        assert "manual-main-column" not in full_html, f"{ui_mode} 模式整本说明书不应渲染页面级右列容器"
        assert "manual-related-panel" not in full_html, f"{ui_mode} 模式整本说明书不应渲染相关模块面板"

        page_url = _build_url(
            app,
            "scheduler.config_manual_page",
            page="material.materials_page",
            src=material_src,
        )
        page_resp = client.get(page_url, headers=_mode_headers(ui_mode))
        if page_resp.status_code != 200:
            raise RuntimeError(f"{ui_mode} 模式页面级说明书请求失败：{page_resp.status_code}")
        page_html = page_resp.get_data(as_text=True)
        page_cfg = _extract_json_config(page_html)
        assert page_cfg.get("mode") == "page", f"{ui_mode} 模式页面级说明 JSON mode 异常"
        assert page_cfg.get("manualText") == "", f"{ui_mode} 模式页面级说明 JSON 不应继续注入整本 manualText"
        assert (page_cfg.get("currentManual") or {}).get("title") == "物料主数据", f"{ui_mode} 模式页面级说明主题异常"
        related_manuals = list(page_cfg.get("relatedManuals") or [])
        assert related_manuals, f"{ui_mode} 模式页面级说明缺少 relatedManuals"
        assert any(item.get("preview_sections") for item in related_manuals), f"{ui_mode} 模式 relatedManuals 缺少 preview_sections"
        assert all(len(item.get("preview_sections") or []) <= 2 for item in related_manuals), f"{ui_mode} 模式 preview_sections 超过 2 个"
        assert '<div class="aps-summary-label">当前页面主题</div>' in page_html, f"{ui_mode} 模式页面级说明缺少当前页主题标签"
        assert '<div class="aps-summary-value">物料主数据</div>' in page_html, f"{ui_mode} 模式页面级说明缺少当前页主题值"
        assert '<div class="aps-summary-label">对应整本章节</div>' in page_html, f"{ui_mode} 模式页面级说明缺少整本章节标签"
        assert "相关模块说明" in page_html, f"{ui_mode} 模式页面级说明缺少 related 区块"
        assert "manual-main-column" in page_html, f"{ui_mode} 模式页面级说明缺少右列容器"
        assert "manual-related-panel" in page_html, f"{ui_mode} 模式页面级说明缺少相关模块面板类"
        assert page_html.count('id="content"') == 1, f"{ui_mode} 模式页面级说明应只保留一个 #content"
        assert page_html.index("manual-main-column") < page_html.index('id="content"') < page_html.index("manual-related-panel"), (
            f"{ui_mode} 模式页面级说明右列结构顺序异常"
        )
        assert 'data-manual-markdown="' in page_html, f"{ui_mode} 模式页面级说明缺少 related Markdown 渲染占位"
        assert "## 物料主数据" in page_html, f"{ui_mode} 模式 noscript 缺少当前页 fallback 标题"
        current_sections = list((page_cfg.get("currentManual") or {}).get("sections") or [])
        assert current_sections, f"{ui_mode} 模式页面级说明缺少当前页章节"
        first_section_title = str(current_sections[0].get("title") or "").strip()
        assert first_section_title and f"### {first_section_title}" in page_html, f"{ui_mode} 模式 noscript 缺少当前页关键说明 fallback"

    print("OK")


if __name__ == "__main__":
    main()
