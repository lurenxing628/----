"""回归测试：守护系统使用说明书（static/docs/scheduler_manual.md 及其 web_new_test v2 镜像）与 config_manual.js/模板的契约——主副本逐字一致、必备口径与边界说明在场（排产历史不承诺导出/恢复、资源排班现场记录当前直接导入、截止日期是严格限制等）、入口统一叫批量维护、内部锚点全部命中、JS 过滤危险协议并对数字前缀 hash 不崩，且 v1/v2 真实请求下整本/页面级双模式的 JSON 数据块与 noscript 回退正确。"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Dict, List, Set, Tuple

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


def _extract_heading_ids(markdown_text: str) -> Set[str]:
    ids: Set[str] = set()
    for line in markdown_text.splitlines():
        m = re.match(r"^(#{2,4})\s+(.+)$", line.strip())
        if not m:
            continue
        ids.add(_slugify_heading(m.group(2)))
    return ids


def _extract_internal_hashes(markdown_text: str) -> List[str]:
    refs: List[str] = []
    for _label, href in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", markdown_text):
        link = (href or "").strip()
        if link.startswith("#"):
            refs.append(link[1:])
    return refs


def _find_legacy_excel_entry_terms(markdown_text: str) -> List[str]:
    hits: List[str] = []
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


def _mode_headers(ui_mode: str) -> Dict[str, str]:
    return {"Cookie": f"aps_ui_mode={ui_mode}"}


def _build_url(app, endpoint: str, **values: Any) -> str:
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


def _extract_section(markdown_text: str, heading: str) -> str:
    start = markdown_text.find(heading)
    assert start >= 0, f"说明书缺少章节：{heading}"
    heading_level = len(heading) - len(heading.lstrip("#"))
    rest = markdown_text[start + len(heading) :]

    def _same_or_higher_heading(match: re.Match) -> bool:
        return len(match.group(1)) <= heading_level

    next_heading = None
    for candidate in re.finditer(r"^(#{1,6})\s+", rest, flags=re.M):
        if _same_or_higher_heading(candidate):
            next_heading = candidate
            break
    end = start + len(heading) + next_heading.start() if next_heading else len(markdown_text)
    return markdown_text[start:end]


def _assert_ordered_phrases(markdown_text: str, label: str, phrases: Tuple[str, ...]) -> None:
    cursor = -1
    for phrase in phrases:
        idx = markdown_text.find(phrase, cursor + 1)
        assert idx >= 0, f"{label} 缺少流程节点：{phrase}"
        assert idx > cursor, f"{label} 流程节点顺序错误：{phrase}"
        cursor = idx


def _assert_history_section_does_not_claim_export_or_restore(markdown_text: str, label: str) -> None:
    section = _extract_section(markdown_text, "### 10.3 排产历史")
    for needle in ("不能导出版本", "不能恢复某个排产版本"):
        assert needle in section, f"{label} 排产历史章节缺少边界说明：{needle}"
    forbidden_positive_phrases = (
        "用来查看、导出、恢复这些版本",
        "可以导出排产历史",
        "可以恢复排产历史",
        "支持导出排产历史",
        "支持恢复排产历史",
        "导出历史版本",
        "恢复此版本",
    )
    for phrase in forbidden_positive_phrases:
        assert phrase not in section, f"{label} 排产历史章节仍像是在承诺导出/恢复能力：{phrase}"


def _assert_resource_dispatch_site_record_section(markdown_text: str, label: str) -> None:
    section = _extract_section(markdown_text, "### 6.6 资源排班")
    for needle in (
        "任务明细/日历矩阵/甘特图/现场记录",
        "页面里有任务明细、日历矩阵、甘特图和现场记录四个视图",
        "资源排班里的现场记录只对当前最新的正式采用方案开放",
        "填写实际情况",
        "下载填写模板",
        "导入实际情况 Excel",
        "查看现场记录",
        "查看计划和实际",
        "当前是直接导入，不走预览/二次确认",
    ):
        assert needle in section, f"{label} 资源排班章节缺少现场记录当前口径：{needle}"

    for forbidden in (
        "现场反馈常用动作",
        "| 开工 |",
        "| 暂停 |",
        "| 继续生产 |",
        "| 报异常 |",
        "| 完工 |",
        "继续生产",
        "报异常",
    ):
        assert forbidden not in section, f"{label} 资源排班章节不应继续误导旧实时动作：{forbidden}"


def _assert_scheduler_manual_closeout_contracts(markdown_text: str, label: str) -> None:
    for needle in (
        "页面上的 **本页说明** 按钮",
        "只打开操作说明",
        "设备 Excel 真实模板只有这 5 列：设备编号、设备名称、工种、班组、状态",
    ):
        assert needle in markdown_text, f"{label} 缺少本轮说明书收口内容：{needle}"

    resource_load_section = _extract_section(markdown_text, "### 9.2 资源负荷与利用率")
    for needle in (
        "设备、人员的负荷",
        "设备和人员两个工作表",
        "设备负荷",
        "人员负荷",
    ):
        assert needle in resource_load_section, f"{label} 资源负荷章节缺少设备/人员两张表口径：{needle}"

    config_section = _extract_section(markdown_text, "## 7. 高级设置：每个开关的作用")
    for needle in (
        "优化目标",
        "最少超期",
        "最少拖期小时",
        "最少加权拖期小时",
        "最少换型次数",
    ):
        assert needle in config_section, f"{label} 高级设置章节缺少优化目标口径：{needle}"

    scheduler_section = _extract_section(markdown_text, "### 6.3 执行排产与模拟排产")
    for needle in ("排产截止日期", "这是严格限制，不是普通备注"):
        assert needle in scheduler_section, f"{label} 执行排产章节缺少截止日期严格限制口径：{needle}"
    for forbidden in (
        "超过截止日期就一定失败",
        "超过截止日期必然失败",
        "截止日期一定会导致排产失败",
        "截止日期必然导致失败",
        "排产截止日期不是严格限制",
        "截止日期不是严格限制",
        "不算严格限制",
    ):
        assert forbidden not in scheduler_section, f"{label} 截止日期说明写得过死或写反：{forbidden}"

    gantt_section = _extract_section(markdown_text, "### 6.4 甘特图")
    assert "版本留空或版本为空字符串，都表示看最新排产历史" in gantt_section, f"{label} 甘特图章节缺少版本留空口径"
    assert "`latest` 是英文，意思就是“最新”" not in gantt_section, f"{label} 甘特图章节不能再教用户填写 latest"


def _assert_scheduler_manual_required_content(markdown_text: str, label: str) -> None:
    for needle in (
        "旧模板中已有数据行不会被系统擅自改写",
        "新填数据请使用 `自制`/`外协`",
        "批次自动生成工序时的模板提醒，是当前页局部提醒",
        "正式排产或模拟排产成功后的排产结果提醒",
        "可以到排产历史查看这次排产的详细提醒",
        "版本留空或版本为空字符串，都表示看最新排产历史",
        "输入不存在的数字版本时",
        "输入 `abc` 这类不是数字的版本号",
        "空工时按 0 小时处理",
        "日历类型空着按工作日理解",
        "连续外协周期示例",
        "系统管理 → 排产历史** 只看版本摘要、提醒和结果概况",
        "选择查看最近 10 条、50 条这类记录",
        "首页统计卡怎么看",
        "如果停机时间填错，先取消原停机，再按正确时间新建",
        "保存补齐资源",
        "报表首页的两个数字只做快速速览",
        "同一批次里，同一个物料只能新增一次",
        "物料下拉框只显示状态为“可用”的物料",
        "批次齐套日期会自动清空",
        "趋势图只使用有排产指标的版本",
        "只有历史摘要读取失败时，页面才会提示读取失败的版本数量",
        "正式排产和模拟排产都算",
        "按这个最新版本的超期清单口径重新计算",
        "查询结果表包含 10 列",
        "任务明细表有 14 列",
        "| 现场状态 | 显示待开工、生产中、暂停中、异常中、已完工等现场记录状态 |",
        "| 最近异常 | 显示最近一次异常的中文摘要；没有异常时显示暂无异常 |",
        "| 影响资源 | 显示异常影响到的设备或人员；没有填写时显示未填写 |",
        "任务明细/日历矩阵/甘特图/现场记录",
        "页面里有任务明细、日历矩阵、甘特图和现场记录四个视图",
        "填写实际情况",
        "导入实际情况 Excel",
        "查看现场记录",
        "| 查询对象 | 当前视角正在看的人员、设备或班组 |",
        "| 日志序号 | 当前查询结果里的顺序，不是固定不变的数据库编号 |",
        "导入批次时“自动生成工序”覆盖了手工补的数据怎么办？",
        "版本下拉为空或提示“暂无排产历史”怎么办？",
        "恢复备份后数据和之前不一样？",
        "排产成功但甘特图上看不到任务？",
        "系统默认按待排批次查看",
        "先确认状态筛选是 **待排**",
        "模拟排产后网页不会记住上一次表单里的临时勾选，所以正式排产前一定要重新勾选",
        "备份/恢复",
        "深度优化 + 深度优化尝试时间",
    ):
        assert needle in markdown_text, f"{label} 缺少说明书必备内容：{needle}"
    assert "用来查看、导出、恢复这些版本" not in markdown_text, f"{label} 不应再写排产历史可以导出或恢复版本"
    assert "模拟方案报表只能在页面上查看" not in markdown_text, f"{label} 不应再写模拟方案报表不能导出"
    assert "导出的 Excel 也会按这个模拟方案生成" in markdown_text, f"{label} 缺少模拟预览导出口径"
    for forbidden in (
        "备份与恢复",
        "默认是全部",
        "默认选中\"（全部）\"",
        "默认选中“（全部）”",
        "单件时间",
        "换型工时",
        "均匀程度 CV",
        "启用 OR-Tools",
        "OR-Tools 尝试时间",
        "贪心",
    ):
        assert forbidden not in markdown_text, f"{label} 不应继续出现旧说明口径：{forbidden}"
    _assert_scheduler_manual_closeout_contracts(markdown_text, label)
    _assert_resource_dispatch_site_record_section(markdown_text, label)

    batch_warning_paragraph = _extract_paragraph_containing(markdown_text, "自动生成批次工序时产生提醒")
    assert "当前页面确认写入后只会展示去重后的前 3 条提醒" in batch_warning_paragraph
    assert "另有 X 条提醒" in batch_warning_paragraph or "剩余提醒" in batch_warning_paragraph
    assert "系统历史" not in batch_warning_paragraph, f"{label} 的批次剩余提醒口径不应再要求去系统历史：{batch_warning_paragraph}"

    full_flow_section = _extract_section(markdown_text, "## 6. 排产操作：完整指南")
    _assert_ordered_phrases(
        full_flow_section,
        f"{label} 完整排产流程",
        (
            "先建基础资料",
            "再建批次",
            "生成并补齐批次工序",
            "先模拟排产",
            "再正式排产",
            "最后复盘和下发",
        ),
    )
    _assert_history_section_does_not_claim_export_or_restore(markdown_text, label)


def test_config_manual_markdown_contract(app_client) -> None:
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
    app = app_client.application
    client = app_client
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
