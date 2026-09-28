"""回归测试：守护系统使用说明书（static/docs/scheduler_manual.md）与说明书页的契约——必备口径在场（本次排产规则、排产检查五种结果、采用即锁定、试调不影响正式计划、备份恢复要重启等）、逐表指南 12 张表逐一给出工作台入口、内部锚点全部命中、旧 Excel 入口叫法和已退役页面不再出现，且真实请求下整本 / 页面级两种说明书形态渲染正确、恶意 Markdown 被转义、文件读不到时给出明确错误。"""

from __future__ import annotations

import re
from typing import Any, List, Set, Tuple

from flask import url_for

from tests._support.paths import REPO_ROOT_STR

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

#: 第 1 章逐表指南必须逐张给出进入方式。名字与顺序跟 core.models.workbench_table_catalog 的表目录一致，
#: 少一张就说明新增了能导入的表却没写进说明书。报工记录两个格式版本合一节，所以这里是 12 项。
MANUAL_TABLE_GUIDE_SECTIONS = (
    "工种",
    "供应商",
    "零件工艺路线",
    "零件工序工时",
    "人员",
    "设备",
    "可操作设备",
    "物料",
    "工作日历",
    "个人日历",
    "批次信息",
    "报工记录",
)


def _find_repo_root() -> str:
    return REPO_ROOT_STR


def _slugify_heading(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    t = re.sub(r"^(\d+)\s*[\.．。]\s*", r"\1-", t)
    t = t.lower()
    t = re.sub(r"[^\w一-龥-]+", "", t)
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


def _is_historical_legacy_entry_note(line: str, term: str) -> bool:
    if term not in ("Excel 导入导出", "Excel导入导出"):
        return False
    # 「老资料」「旧入口」两个词就足以认出这是历史说明那一行。
    return "老资料" in line and "旧入口" in line


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
            if re.match(r"^(?:\*\*从哪里进\*\*|\*\*进入方式\*\*|进入方式|入口)[:：]", next_line):
                return next_line.strip()
    raise RuntimeError(f"说明书缺少“{section_name}”章节的进入方式")


def _assert_manual_table_guide_entries(markdown_text: str) -> None:
    legacy_hits = _find_legacy_excel_entry_terms(markdown_text)
    assert not legacy_hits, "说明书仍出现旧 Excel 入口叫法：\n" + "\n".join(legacy_hits[:20])

    # 入口一律从工作台的导航写起：批次从批次管理进，报工从现场记录进，其余都从基础资料的产能链进。
    missing_entry = []
    for section_name in MANUAL_TABLE_GUIDE_SECTIONS:
        entry_line = _find_heading_entry_line(markdown_text, section_name)
        if not any(term in entry_line for term in ("基础资料", "批次管理", "现场记录")):
            missing_entry.append(f"{section_name}: {entry_line}")
    assert not missing_entry, "逐表指南的进入方式必须从工作台导航写起：\n" + "\n".join(missing_entry)


def _build_url(app, endpoint: str, **values: Any) -> str:
    with app.test_request_context():
        return url_for(endpoint, **values)


def _extract_section(markdown_text: str, heading: str) -> str:
    start = markdown_text.find(heading + "\n")
    assert start >= 0, f"说明书缺少章节：{heading}"
    heading_level = len(heading) - len(heading.lstrip("#"))
    rest = markdown_text[start + len(heading) :]
    next_heading = None
    for candidate in re.finditer(r"^(#{1,6})\s+", rest, flags=re.M):
        if len(candidate.group(1)) <= heading_level:
            next_heading = candidate
            break
    end = start + len(heading) + next_heading.start() if next_heading else len(markdown_text)
    return markdown_text[start:end]


def _rendered_pieces(line: str) -> Tuple[str, ...]:
    """Drop the Markdown markers the manual page now renders away."""
    raw = line.strip()
    if not raw or re.match(r"^(?:\|[\s:|-]+\|$|-{3,}$|\*{3,}$|_{3,}$|```)", raw):
        return ()
    body = re.sub(r"^(?:#{1,6}\s+|>\s?|[-*+]\s+|\d+[.)]\s+)", "", raw)
    cells = body.strip("|").split("|") if raw.startswith("|") else [body]
    return tuple(cell.strip().replace("**", "").replace("`", "") for cell in cells)


def _assert_rendered_text_covers_source(parsed: Any, markdown_text: str) -> None:
    """No retained manual line may disappear while the source symbols are hidden."""
    text = "".join(parsed.body)
    missing = [piece for line in markdown_text.splitlines()
               for piece in _rendered_pieces(line) if piece and piece not in text]
    assert not missing, f"渲染后丢失说明书内容：{missing[:10]}"


def _assert_ordered_phrases(markdown_text: str, label: str, phrases: Tuple[str, ...]) -> None:
    cursor = -1
    for phrase in phrases:
        idx = markdown_text.find(phrase, cursor + 1)
        assert idx >= 0, f"{label} 缺少流程节点：{phrase}"
        assert idx > cursor, f"{label} 流程节点顺序错误：{phrase}"
        cursor = idx


def _assert_section_contracts(markdown_text: str, label: str) -> None:
    run_section = _extract_section(markdown_text, "### 6.2 执行排产")
    for needle in ("选批次和日期", "开始排产检查", "核对并开始排产", "本次跳过", "已开工保护", "自动分配待补",
                   "采用方案", "确认正式采用", "试调不影响正式计划", "不能导出，也不能把某次排产恢复成当前数据"):
        assert needle in run_section, f"{label} 执行排产章节缺少：{needle}"
    for forbidden in ("本次排产会报错并停止", "排产截止日期", "发现参数问题就停止排产", "先做一次 **试调**"):
        assert forbidden not in run_section, f"{label} 执行排产章节仍是旧口径：{forbidden}"

    rules_section = _extract_section(markdown_text, "## 7. 排产规则：每个开关的作用")
    for needle in ("齐套检查", "开启 / 关闭", "缺资源工序", "自动分配 / 暂不排", "保留记录（不可修改）", "规则仅用于本次排产"):
        assert needle in rules_section, f"{label} 排产规则章节缺少本次排产规则口径：{needle}"
    for forbidden in ("保存为方案", "恢复默认", "优先级权重 0.4"):
        assert forbidden not in rules_section, f"{label} 排产规则章节仍在讲已退役的设置页：{forbidden}"

    field_section = _extract_section(markdown_text, "### 9.1 现场记录")
    for needle in ("新增本次报工", "补齐", "更正", "撤销这次报工", "报工文件", "开始预检", "确认导入", "保存并继续", "复制上一条"):
        assert needle in field_section, f"{label} 现场记录章节缺少：{needle}"
    for forbidden in ("继续生产", "报异常", "任务明细", "日历矩阵", "排布图"):
        assert forbidden not in field_section, f"{label} 现场记录章节仍在讲旧页面：{forbidden}"

    calib_section = _extract_section(markdown_text, "### 10.4 工时定额校准")
    for needle in ("预检并采用模板定额", "确认采用并锁定", "不能撤销", "不能重复采用", "只用于以后新增的工序", "已有批次"):
        assert needle in calib_section, f"{label} 工时定额校准章节缺少锁定口径：{needle}"
    assert "解除锁定" not in markdown_text, f"{label} 定额锁定后没有解锁动作，说明书不能再写解除锁定"

    system_section = _extract_section(markdown_text, "## 11. 系统管理")
    for needle in ("概况", "备份恢复", "运行日志", "配置", "新增备份", "输入“恢复”", "关闭整个软件再启动", "脱敏诊断 ZIP"):
        assert needle in system_section, f"{label} 系统管理章节缺少：{needle}"
    assert "管理样例" not in markdown_text, f"{label} 管理样例已下线，说明书不能写它"

    for heading in ("### 5.8 资料总览", "### 6.5 交付风险", "### 6.6 试调排产方案", "### 9.2 现场实际甘特", "### 10.2 执行复盘"):
        assert len(_extract_section(markdown_text, heading).strip().splitlines()) >= 5, f"{label} 新增章节内容过少：{heading}"


def _assert_scheduler_manual_required_content(markdown_text: str, label: str) -> None:
    for needle in (
        "“导出 → 改 → 导回”是最稳的改法",
        "归属和外协周期策略使用与页面相同的中文",
        "工时留空不会自动补零",
        "这一天原来没配置过、类型又留空时，按这个日期的默认规则定",
        "合并周期在每组第一道工序填一次",
        "值班台怎么看",
        "顶栏“帮助”打开的 **本页说明**",
        "阅读整本说明书",
        "下载整本说明书",
        "产能链",
        "预检工序更新",
        "清除单独设置",
        "确认清除，恢复默认",
        "本次排产规则",
        "排产检查",
        "候选方案",
        "采用后这个模板工序的单件工时就锁定了",
        "基础资料待维护项.csv",
        "**从哪里进**：",
    ):
        assert needle in markdown_text, f"{label} 缺少说明书必备内容：{needle}"
    for forbidden in (
        "备份与恢复",
        "默认是全部",
        "单件时间",
        "均匀程度 CV",
        "启用 OR-Tools",
        "OR-Tools 尝试时间",
        "贪心",
        "证据",
        "导出周计划",
        "停机计划",
        "批次物料需求",
        "班组管理",
        "管理样例",
        "常用方案",
        "只打开当前页面的速览卡片",
        "系统管理 → 使用说明",
        "个人工作日历",
        "批量维护批次",
    ):
        assert forbidden not in markdown_text, f"{label} 不应继续出现旧说明口径：{forbidden}"
    _assert_section_contracts(markdown_text, label)

    full_flow_section = _extract_section(markdown_text, "## 6. 排产操作：完整指南")
    _assert_ordered_phrases(
        full_flow_section,
        f"{label} 完整排产流程",
        ("先建基础资料", "再建批次", "补齐批次工序", "执行排产生成候选方案", "采用为正式计划", "微调和复盘"),
    )


def test_config_manual_markdown_contract(app_client, monkeypatch, tmp_path) -> None:
    from html.parser import HTMLParser
    from pathlib import Path

    from flask import template_rendered

    import web.routes.workbench.manual_page as route_mod

    class Manual(HTMLParser):
        def __init__(self, text):
            super().__init__(convert_charrefs=True)
            self.ids, self.hrefs, self.tags, self.pre, self.active = set(), [], [], [], False
            self.scripts, self.in_script = [], False
            self.body, self.in_style = [], False
            self.feed(text)
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            self.tags.append((tag, attrs))
            if attrs.get("id"):
                self.ids.add(attrs["id"])
            if tag == "a":
                self.hrefs.append(attrs.get("href", ""))
            if tag == "pre":
                self.active = True
                self.pre.append("")
            if tag == "script":
                self.in_script = True
                self.scripts.append("")
            if tag == "style":
                self.in_style = True
        def handle_endtag(self, tag):
            if tag == "pre":
                self.active = False
            if tag == "script":
                self.in_script = False
            if tag == "style":
                self.in_style = False
        def handle_data(self, text):
            if self.active:
                self.pre[-1] += text
            if self.in_script:
                self.scripts[-1] += text
            if not self.in_script and not self.in_style:
                self.body.append(text)

    root = Path(_find_repo_root())
    manual_path = root / "static/docs/scheduler_manual.md"
    manual_text = manual_path.read_text(encoding="utf-8")
    assert manual_text.startswith("# 系统使用说明")
    _assert_scheduler_manual_required_content(manual_text, "主说明书")
    _assert_manual_table_guide_entries(manual_text)
    heading_ids = _extract_heading_ids(manual_text)
    internal_hashes = _extract_internal_hashes(manual_text)
    missing_hashes = [item for item in internal_hashes if item not in heading_ids]
    assert not missing_hashes, f"说明书存在未命中的内部锚点：{missing_hashes[:10]}"
    assert not (root / "static/js/config_manual.js").exists()
    assert not (root / "templates/scheduler/config_manual.html").exists()

    app, client, captured = app_client.application, app_client, []
    def rendered(sender, template, context, **extra):
        captured.append((template.name, context))
    template_rendered.connect(rendered, app, weak=False)
    try:
        def read(url):
            captured.clear()
            response = client.get(url)
            assert response.status_code == 200, response.get_data(as_text=True)
            assert len(captured) == 1 and captured[0][0] == "workbench/manual.html"
            html = response.get_data(as_text=True)
            parsed = Manual(html)
            # Only the shared theme initializer remains; manual text has no executable renderer.
            assert len(parsed.scripts) == 1 and "aps_kit_theme" in parsed.scripts[0]
            assert not [attrs for tag, attrs in parsed.tags if tag == "script" and attrs.get("src")]
            assert not any(href.lower().startswith(("javascript:", "data:")) for href in parsed.hrefs)
            assert all(href[1:] in parsed.ids for href in parsed.hrefs if href.startswith("#"))
            assert "说明书正文" in html and "说明书章节" in html
            return html, parsed, captured[0][1]

        process_src = _build_url(app, "workbench.index", view="process")
        full_url = _build_url(app, "scheduler.config_manual_page", src=process_src)
        full_html, full, state = read(full_url)
        assert state["manual_mode"] == "full" and state["manual_text"] == manual_text and state["manual_available"] is True
        assert state["current_manual"] is None and state["related_manuals"] == []
        assert process_src in full.hrefs
        assert heading_ids <= full.ids and set(internal_hashes) <= full.ids
        # The manual is rendered: every source line stays readable, the markers do not.
        _assert_rendered_text_covers_source(full, manual_text)
        assert "<table>" in full_html and "<strong>" in full_html and "<li>" in full_html
        assert "|---|" not in "".join(full.body) and "**" not in "".join(full.body)
        assert "相关说明" not in full_html

        page_url = _build_url(app, "scheduler.config_manual_page", page="process", src=process_src)
        page_html, page, page_state = read(page_url)
        assert page_state["manual_mode"] == "page" and page_state["manual_available"] is True
        assert page_state["current_manual"]["title"] == "基础资料" and page_state["current_manual"]["view"] == "process"
        assert page_state["fallback_text"].startswith("## 5. 数据准备：排产前必须做的事\n")
        assert "## 6. 排产操作" not in page_state["fallback_text"] and "### 5.8 资料总览" in page_state["fallback_text"]
        related = page_state["related_manuals"]
        assert [item["view"] for item in related] == ["basedata", "batches"]
        assert "本页说明 - 基础资料" in page_html and "相关说明" in page_html
        assert process_src in page.hrefs and page_state["full_manual_section_url"] in page.hrefs
        assert page_state["full_manual_section_url"].endswith("#" + _slugify_heading("5. 数据准备：排产前必须做的事"))
        assert _slugify_heading("5. 数据准备：排产前必须做的事") in page.ids and _slugify_heading("5.8 资料总览") in page.ids
        assert _slugify_heading("6. 排产操作：完整指南") not in page.ids
        _assert_rendered_text_covers_source(page, page_state["fallback_text"])
        for item in related:
            assert item["url"] in page.hrefs and item["title"] in page_html and item["preview_sections"] == []
        for url in (state["download_url"], page_state["download_url"]):
            download = client.get(url)
            assert download.status_code == 200 and "attachment" in download.headers["Content-Disposition"]
            assert download.data == manual_path.read_bytes()
            download.close()

        malicious = "# 1. 数字章节\n[危险](javascript:alert(1))\n<img src=x onerror=alert(1)>\n"
        with monkeypatch.context() as patch:
            patch.setattr(route_mod, "_load_manual_source", lambda *_: (malicious, None, True))
            html, parsed, _ = read(full_url)
            assert "1-数字章节" in parsed.ids
            assert "[危险](javascript:alert(1))" in "".join(parsed.body)
            assert "<img" not in html and "&lt;img" in html
            assert not [tag for tag, attrs in parsed.tags if tag in ("img", "iframe")]
            assert len(parsed.scripts) == 1 and "alert(1)" not in parsed.scripts[0]
        # A real open failure remains an explicit readable error and tells the template the manual is unavailable.
        blocked = tmp_path / "unreadable-manual.md"
        blocked.mkdir()
        with monkeypatch.context() as patch:
            patch.setattr(route_mod, "_resolve_scheduler_manual_md_path", lambda: (str(blocked), [str(blocked)]))
            failed, parsed, failed_state = read(full_url)
            assert "说明书加载失败" in failed and parsed.body
            assert failed_state["manual_available"] is False and failed_state["download_url"] is not None
    finally:
        template_rendered.disconnect(rendered, app)
