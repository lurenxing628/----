"""回归测试：页面级说明注册表（web.viewmodels.page_manuals）的完整性与文案不漂移——ENDPOINT_TO_MANUAL_ID 与已注册路由、MANUAL_TOPICS/MANUAL_ENTRY_ENDPOINTS 一一对应且无共享 manual_id，各页 title/help_card 标题与 full_manual_anchor 锚点稳定命中 scheduler_manual.md，并守护齐套检查、留空默认值、首次使用路线图等用户纠偏文案的必含/禁含口径。"""

from __future__ import annotations

import importlib
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Set

from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT_STR


def _find_repo_root() -> str:
    return REPO_ROOT_STR


def _prepare_env(tmpdir: str, monkeypatch) -> None:
    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(Path(tmpdir) / "aps_test.db"))
    monkeypatch.setenv("APS_LOG_DIR", str(Path(tmpdir) / "logs"))
    monkeypatch.setenv("APS_BACKUP_DIR", str(Path(tmpdir) / "backups"))
    point_env_at_shared(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", "aps-page-manual-registry")


def _load_app(repo_root: str, monkeypatch):
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    monkeypatch.delitem(sys.modules, "app", raising=False)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


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


def _build_payload_text(payload: dict) -> str:
    parts: List[str] = []
    parts.append(str(payload.get("title") or ""))
    parts.append(str(payload.get("summary") or ""))
    help_card = payload.get("help_card") or {}
    parts.append(str(help_card.get("title") or ""))
    parts.extend(str(item or "") for item in (help_card.get("items") or []))
    for section in payload.get("sections") or []:
        parts.append(str(section.get("title") or ""))
        parts.append(str(section.get("body_md") or ""))
    return "\n".join(part for part in parts if part)


PROCESS_PAGE_MANUAL_TITLE_CASES = {
    "process.list_parts": ("process_parts", "零件工艺模板", "零件工艺模板是排产计算的起点"),
    "process.part_detail": ("process_part_detail", "零件工艺模板", "先把这张零件工艺模板看完整"),
    "process.op_types_page": ("process_op_types", "工种配置", "工种是最先要配好的基础字典"),
    "process.op_type_detail": ("process_op_type_detail", "工种详情", "这个工种的归属一定要看准"),
    "process.suppliers_page": ("process_suppliers", "供应商配置", "供应商管外协工序的周期和归属"),
    "process.supplier_detail": ("process_supplier_detail", "供应商详情", "先确认这个供应商到底负责哪类外协"),
}


LEGACY_PAGE_TITLE_TERMS = (
    "（Excel导入/导出）",
    "（Excel）",
    "Excel 导入/导出",
    "Excel导入/导出",
    "Excel 导入导出",
    "Excel导入导出",
)


USER_CORRECTED_TOPIC_SEMANTIC_CASES = {
    "material_batch": [
        "齐套概览",
        "无需求行默认齐套",
        "齐套日期：它不是到料数量",
        "只有启用“齐套检查”时，它才会影响排产",
        "新增时到料数量留空",
        "更新已有行时，到料数量留空",
        "系统不会自动跳过未齐套或部分齐套批次继续排其它批次",
    ],
    "scheduler_gantt": [
        "空白甘特图",
        "版本不存在",
        "不要把版本不存在当成普通空白",
    ],
    "scheduler_batches_manage": [
        "自动生成批次工序只处理新增和更新行",
        "无变化或跳过的批次不会刷新工序",
    ],
    "scheduler_calendar": [
        "旧批量文件里填过“周末”或“节假日”的，系统会按假期兼容处理",
        "新模板仍建议填工作日或假期",
        "系统会当成 `假期` 兼容保存",
        "班次开始/结束",
    ],
    "scheduler_dispatch": [
        "自定义日期范围最多 62 天",
        "最多只能查 62 天",
        "查询对象、对应资源",
    ],
    "scheduler_week_plan": [
        "页面只预览前 50 行",
        "完整周计划以点击页面上的“导出周计划表.xlsx”按钮后下载的表格为准",
        "导出周计划表.xlsx",
        "没有单独的起止日期输入框",
    ],
    "reports_overdue": [
        "超期(天)按当前实现显示小数天",
        "不是向上取整",
        "当前页面显示的是小数天",
        "查看为什么晚了",
        "诊断依据",
        "不会直接断定唯一原因",
    ],
    "reports_utilization": [
        "完全没有任务的设备或人员不会显示成 0",
        "这张表不是设备/人员主数据清单",
    ],
    "equipment_downtime_batch": [
        "选“设备类别”或“全部设备”时，系统默认只给可用设备创建停机计划",
        "默认只给状态为“可用”的设备",
    ],
    "system_backup": [
        "已从备份恢复并完成结构校验",
        "结构校验失败",
    ],
}


USER_CORRECTED_FULL_MANUAL_PHRASES = [
    "齐套日期只有在启用齐套检查时才影响排产",
    "系统不会自动跳过这些批次继续排其它批次",
    "齐套日期只对齐套批次作为最早开工日",
    "旧 Excel 里如果已经手填 `周末` 或 `节假日`，系统也会按假期处理",
    "新模板不要故意写旧叫法",
    "自定义日期范围最多 62 天；查更长时间要分段查",
    "页面只显示前 50 行，并给出总行数",
    "完整周计划以点击 **导出周计划表.xlsx** 按钮后下载的 Excel 为准",
    "报表里的超期天数是小数天，不是只取整天",
    "每条超期批次都可以点开 **查看为什么晚了**",
    "“诊断依据”工作表会写本次诊断编号",
    "只统计当前版本、当前日期范围内有任务的资源",
    "按类别或全部批量停机时，默认只包含状态为 **可用** 的设备",
    "已从备份恢复并完成结构校验",
]


PAGE_MANUAL_REFUSAL_CONDITION_CASES = {
}


SCHEDULER_PAGE_MANUAL_TITLE_CASES = {
    "scheduler.batches_page": ("scheduler_batches", "排产调度", "排产调度页先看这 5 点"),
    "scheduler.batch_detail": ("scheduler_batch_detail", "批次详情/批次工序", "批次工序不完整就排不出正确结果"),
}


HOME_PAGE_MANUAL_REQUIRED_PHRASES = [
    "第一次使用路线图",
    "先准备基础资料，再做模拟和正式排产",
    "不要一上来只导批次",
    # 2026-09 起工时/类型留空一律表示保持原样，不再自动补 0 或按工作日。
    "工时留空表示保持原样，不会自动补 0",
    "类型留空表示保持原样",
    "先模拟排产",
    "确认没问题再执行排产",
    "甘特图",
    "周计划导出",
    "资源排班",
    "排产优化分析",
    "排产历史只看版本摘要、提醒和结果概况",
    "查看最近 10 条、50 条这类记录",
    "首页驾驶舱怎么看",
    "计划上下文胶囊",
    "hero 指令卡",
    "当前没有必须马上处理的排产风险",
    "7 格体检表",
    "超期批次",
    "待排批次",
    "方案待确认",
    "现场情况",
    "资源负荷",
    "基础数据",
    "临期批次",
    "不是所有历史版本累计",
    "不在这里导出或恢复版本",
    "运行提醒只展示前 5 条",
]


SCHEDULER_PAGE_MANUAL_FORBIDDEN_PHRASES = {
    "scheduler_batches": ["未齐套批次不排", "未齐套批次不进入排产", "不参与排产"],
    "scheduler_config": ["未齐套批次不排", "未齐套批次不进入排产"],
    "scheduler_week_plan": ["导出维度"],
    "system_history": ["导出、恢复这些版本"],
}


PAGE_MANUAL_CLOSEOUT_FORBIDDEN_PHRASES = (
    "改工种名或工种编号前",
    "先用筛选缩小范围",
    "需要找少量记录时，可以用筛选缩小范围",
    "可以用筛选缩小范围；只是新增资料",
    "右下角“本页说明”",
    "CV值",
    "均匀程度 CV",
    "系统历史",
    "备份与恢复",
    "OR-Tools",
    "贪心",
    "单件时间",
    "换型工时",
    "版本分析",
    "step-by-step",
)

PAGE_MANUAL_CLOSEOUT_FORBIDDEN_TEMPLATE_PHRASES = (
    "类型可填“工作日、假期、周末、节假日”",
    "可填写：工作日 / 假期 / 周末 / 节假日",
)


PAGE_MANUAL_LIST_BASICS_REQUIRED_COPY = (
    "可以用筛选或翻页缩小范围",
    "具体筛选方式因页面而异",
    "有些页面有搜索框和下拉筛选，有些只有翻页",
)


READY_CHECK_REQUIRED_COPY = (
    "本次排产会报错并停止",
    "系统不会自动跳过这些批次继续排其它批次",
    "齐套日期只对齐套批次作为最早开工日",
)


READY_CHECK_LEGACY_FILTER_COPY = (
    "未齐套批次不进入排产",
    "未齐套批次不排",
    "打开后未齐套不排",
    "未齐套和部分齐套批次才不会进入排产",
    "齐套状态只有在启用齐套检查时才会拦排产",
)


PROCESS_USER_CORRECTED_REQUIRED_PHRASES = {
    "scheduler_analysis": [
        "不填版本或版本为空，都会看最新历史版本",
        "输入不存在的版本时，页面会显示该版本不存在的占位，不会自动选最新",
    ],
}


PROCESS_USER_CORRECTED_FORBIDDEN_PHRASES = {
    "process_suppliers": [
        "外协工序会自动从这里取供应商和天数",
    ],
    "process_supplier_detail": [
        "外协工序就会自动带错供应商和天数",
    ],
}


MATERIAL_UNSUPPORTED_BATCH_COPY_TERMS = (
    "Excel",
    "批量维护",
)


def _ensure_repo_on_path(repo_root: str) -> None:
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def main(monkeypatch) -> None:
    repo_root = _find_repo_root()
    tmpdir = tempfile.mkdtemp(prefix="aps_page_manual_registry_")
    _prepare_env(tmpdir, monkeypatch)
    app = _load_app(repo_root, monkeypatch)

    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    _assert_process_page_manual_title_contracts(page_manuals)
    _assert_process_user_corrected_wording_contracts(page_manuals)
    _assert_scheduler_page_manual_title_contracts(page_manuals)
    _assert_home_page_manual_contract(page_manuals)
    manual_path = os.path.join(repo_root, "static", "docs", "scheduler_manual.md")
    manual_text = _read(manual_path)
    _assert_user_corrected_semantic_contracts(page_manuals, manual_text)
    _assert_ready_check_visible_copy_contract(repo_root, page_manuals, manual_text)
    _assert_page_manual_refusal_conditions(page_manuals)
    _assert_material_manual_scope_contracts(page_manuals)
    _assert_page_manual_closeout_forbidden_phrases(page_manuals)
    manual_heading_ids = _extract_heading_ids(manual_text)

    endpoint_to_manual_id = dict(page_manuals.ENDPOINT_TO_MANUAL_ID)
    manual_entry_endpoints = dict(page_manuals.MANUAL_ENTRY_ENDPOINTS)
    endpoint_overrides = dict(page_manuals.ENDPOINT_OVERRIDES)
    manual_topics = dict(page_manuals.MANUAL_TOPICS)
    shared_fragments = dict(page_manuals.SHARED_FRAGMENTS)

    registered_endpoints = set(app.view_functions.keys())
    legacy_endpoints = {
        "personnel.list_page",
        "personnel.detail_page",
        "personnel.teams_page",
        "personnel.operator_calendar_page",
        "equipment.list_page",
        "equipment.detail_page",
        "equipment.downtime_batch_page",
        "process.list_parts",
        "process.part_detail",
        "process.op_types_page",
        "process.op_type_detail",
        "process.suppliers_page",
        "process.supplier_detail",
        "scheduler.batches_page",
        "scheduler.batches_manage_page",
        "scheduler.batch_detail",
        "scheduler.config_page",
        "scheduler.calendar_page",
        "scheduler.gantt_page",
        "scheduler.resource_dispatch_page",
        "scheduler.analysis_page",
        "scheduler.week_plan_page",
        "material.materials_page",
        "material.batch_materials_page",
        "reports.index",
        "reports.overdue_page",
        "reports.utilization_page",
        "reports.execution_review_page",
        "reports.downtime_page",
        "system.backup_page",
        "system.logs_page",
        "system.history_page",
        "dashboard.index",
    }
    assert len(endpoint_to_manual_id) == len(legacy_endpoints), f"页面级说明 endpoint 数量异常：{len(endpoint_to_manual_id)}"

    # 1) Registry endpoint 有效性
    invalid_endpoints = sorted(set(endpoint_to_manual_id) - registered_endpoints)
    assert not invalid_endpoints, f"ENDPOINT_TO_MANUAL_ID 存在未注册 endpoint：{invalid_endpoints}"

    # 2) 全覆盖性：旧 manual_anchor_map + 新增 process.excel_part_ops_page
    missing_legacy = sorted(legacy_endpoints - set(endpoint_to_manual_id))
    assert not missing_legacy, f"页面级说明 registry 漏配 endpoint：{missing_legacy}"
    assert len(set(endpoint_to_manual_id.values())) == len(endpoint_to_manual_id), "页面级说明不应再让多个 endpoint 共用同一 manual_id"

    # 3) mapping 和 topic 基本完整性
    missing_topic_ids = sorted({manual_id for manual_id in endpoint_to_manual_id.values() if manual_id not in manual_topics})
    assert not missing_topic_ids, f"ENDPOINT_TO_MANUAL_ID 引用了不存在的 manual_id：{missing_topic_ids}"
    assert set(manual_topics) == set(manual_entry_endpoints), "MANUAL_ENTRY_ENDPOINTS 必须与 MANUAL_TOPICS 一一对应"
    assert manual_topics["system_backup"]["title"] == "备份/恢复"
    assert manual_topics["system_history"]["title"] == "排产历史"
    invalid_entry_endpoints = sorted(
        manual_id for manual_id, endpoint in manual_entry_endpoints.items() if endpoint not in registered_endpoints
    )
    assert not invalid_entry_endpoints, f"MANUAL_ENTRY_ENDPOINTS 存在未注册 endpoint：{invalid_entry_endpoints}"
    mismatched_entry_endpoints = sorted(
        manual_id
        for manual_id, endpoint in manual_entry_endpoints.items()
        if endpoint_to_manual_id.get(endpoint) != manual_id
    )
    assert not mismatched_entry_endpoints, f"MANUAL_ENTRY_ENDPOINTS 与 ENDPOINT_TO_MANUAL_ID 不一致：{mismatched_entry_endpoints}"

    for manual_id, topic in manual_topics.items():
        assert str(topic.get("title") or "").strip(), f"{manual_id} 缺少 title"
        assert str(topic.get("summary") or "").strip(), f"{manual_id} 缺少 summary"
        sections = list(topic.get("sections") or [])
        assert sections, f"{manual_id} 缺少 sections"
        for section in sections:
            assert str(section.get("title") or "").strip(), f"{manual_id} 存在空 section.title"
            assert str(section.get("body_md") or "").strip(), f"{manual_id} 存在空 section.body_md"
            fragment_keys = re.findall(r"\{\{([^{}]+)\}\}", str(section.get("body_md") or ""))
            for key in fragment_keys:
                assert key in shared_fragments, f"{manual_id} 引用了不存在的共享片段：{key}"
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建 payload"
        assert str(payload.get("full_manual_label") or "").strip(), f"{manual_id} 缺少 full_manual_label"
        help_card = payload.get("help_card")
        if help_card:
            assert str(help_card.get("title") or "").strip(), f"{manual_id} 的 help_card 缺少 title"
            help_items = list(help_card.get("items") or [])
            assert help_items, f"{manual_id} 的 help_card 缺少 items"
            for item in help_items:
                assert str(item or "").strip(), f"{manual_id} 的 help_card 存在空白 item"
        for section in payload.get("sections") or []:
            assert "{{" not in section["body_md"] and "}}" not in section["body_md"], f"{manual_id} 存在未展开的共享片段"

    # 4) full_manual_anchor 有效性
    for manual_id, topic in manual_topics.items():
        anchor = str(topic.get("full_manual_anchor") or "").strip()
        assert anchor.startswith("#"), f"{manual_id} 的 full_manual_anchor 必须以 # 开头"
        assert anchor[1:] in manual_heading_ids, f"{manual_id} 的 full_manual_anchor 未命中说明书标题：{anchor}"

    # 5) Registry 内部一致性
    invalid_override_keys = sorted(set(endpoint_overrides) - set(endpoint_to_manual_id))
    assert not invalid_override_keys, f"ENDPOINT_OVERRIDES 存在未映射 endpoint：{invalid_override_keys}"

    for endpoint, override in endpoint_overrides.items():
        related_ids = list((override or {}).get("related_manual_ids") or [])
        assert len(set(related_ids)) == len(related_ids), f"{endpoint} override 的 related_manual_ids 存在重复"
        for related_id in related_ids:
            assert related_id in manual_topics, f"{endpoint} override 引用了不存在的 related_manual_id：{related_id}"

    for manual_id, topic in manual_topics.items():
        related_ids = list(topic.get("related_manual_ids") or [])
        assert len(related_ids) <= 4, f"{manual_id} 的 related_manual_ids 超过 4 个"
        assert len(set(related_ids)) == len(related_ids), f"{manual_id} 的 related_manual_ids 存在重复"
        assert manual_id not in related_ids, f"{manual_id} 不允许自引用"
        for related_id in related_ids:
            assert related_id in manual_topics, f"{manual_id} 引用了不存在的 related_manual_id：{related_id}"

    bundle = page_manuals.build_page_manual_bundle("material.materials_page")
    assert bundle is not None, "material.materials_page 应可构建页面级说明 bundle"
    related_manuals = list(bundle.get("related_manuals") or [])
    assert related_manuals, "material.materials_page 应包含 related_manuals"
    for item in related_manuals:
        preview_sections = list(item.get("preview_sections") or [])
        assert preview_sections, f"{item.get('manual_id')} 缺少 preview_sections"
        assert len(preview_sections) <= 2, f"{item.get('manual_id')} 的 preview_sections 超过 2 个"
        assert "sections" not in item, f"{item.get('manual_id')} 不应向 related_manuals 暴露完整 sections"

    # 6) 语义真值护栏：页面级说明必须写出真实允许值、默认值和危险边界
    manual_semantic_cases = {
        "scheduler_batches": ["当前页只展示前 5 条", "如果排产成功但有运行提醒，页面只列前 5 条"],
        "scheduler_batches_manage": ["当前页只展示前 3 条模板提醒"],
        "scheduler_batch_detail": ["生成或刷新后如果看到前 3 条提醒"],
        "material_batch": ["需求数量必须大于 0", "到料数量不填会按已到齐处理", "明确填 0 或不足数量才会显示未齐套"],
        "system_backup": ["恢复前自动备份", "回滚到恢复前自动备份"],
        "system_history": [
            "排产历史",
            "只展示普通用户需要看的结果、完成状态和提醒",
            "不会生成、删除或恢复排产历史",
        ],
    }
    for manual_id, phrases in manual_semantic_cases.items():
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建语义校验 payload"
        payload_text = _build_payload_text(payload)
        for phrase in phrases:
            assert phrase in payload_text, f"{manual_id} 缺少已核实语义片段：{phrase}"

    full_manual_phrases = [
        # 2026-09 第 1 章按工作台重写：固定选项不再一律中文，工时留空不再按 0 算，
        # 假期效率也改成按百分比填。这三条换成重写后的口径，别把旧说法钉回来。
        "工种、供应商、人员、设备这四张资源表的状态和归属填英文代号",
        "工时留空不会自动补零",
        "效率按 **百分比** 填：正常效率写 `100`，不是 `1`",
        "库存数量可以为 0，但不能为负数",
        '"需求数量"必须大于 0',
        "看页面提示，系统会尽量还原",
        "批量删除前先确认筛选条件、已选条数和本次删除范围",
        "最后更新：2026年9月",
        "执行排产 → 排产记录** 只看版本摘要、提醒和结果概况",
        "选择查看最近 10 条、50 条这类记录",
        "备份文件名由系统自动按时间和用途生成",
        "如果停机时间填错，先取消原来的停机，再按正确时间新增一条",
        "保存补齐资源",
        "最新排产版本",
        "值班台怎么看",
        "当前没有必须马上处理的排产风险",
        "部分报表导出可能只是直接下载文件，不一定都有操作日志",
    ]
    for phrase in full_manual_phrases:
        assert phrase in manual_text, f"总说明书缺少已核实语义片段：{phrase}"
    assert "用来查看、导出、恢复这些版本" not in manual_text, "总说明书不应再把排产历史写成可导出或恢复版本"

    print("OK")


def _assert_material_manual_scope_contracts(page_manuals) -> None:
    for manual_id in ("material_master", "material_batch"):
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建物料说明 payload"
        payload_text = _build_payload_text(payload)
        for term in MATERIAL_UNSUPPORTED_BATCH_COPY_TERMS:
            assert term not in payload_text, f"{manual_id} 不应出现当前物料页面不支持的说法：{term}"


def _assert_user_corrected_semantic_contracts(page_manuals, manual_text: str) -> None:
    for manual_id, phrases in USER_CORRECTED_TOPIC_SEMANTIC_CASES.items():
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建用户纠偏语义校验 payload"
        payload_text = _build_payload_text(payload)
        for phrase in phrases:
            assert phrase in payload_text, f"{manual_id} 缺少用户点名纠偏语义片段：{phrase}"

    for manual_id, phrases in SCHEDULER_PAGE_MANUAL_FORBIDDEN_PHRASES.items():
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建禁用旧文案校验 payload"
        payload_text = _build_payload_text(payload)
        for phrase in phrases:
            assert phrase not in payload_text, f"{manual_id} 不应继续使用旧文案：{phrase}"

    for phrase in USER_CORRECTED_FULL_MANUAL_PHRASES:
        assert phrase in manual_text, f"总说明书缺少用户点名纠偏语义片段：{phrase}"


def _assert_page_manual_closeout_forbidden_phrases(page_manuals) -> None:
    surfaces: Dict[str, str] = {}
    for key, fragment in dict(page_manuals.SHARED_FRAGMENTS).items():
        surfaces[f"shared_fragment:{key}"] = str(fragment or "")

    for manual_id in dict(page_manuals.MANUAL_TOPICS):
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建页面说明禁用文案校验 payload"
        surfaces[f"page_manual:{manual_id}"] = _build_payload_text(payload)

    repo_root = _find_repo_root()
    surfaces["static/docs/scheduler_manual.md"] = _read(os.path.join(repo_root, "static", "docs", "scheduler_manual.md"))

    for source_name, text in surfaces.items():
        for phrase in PAGE_MANUAL_CLOSEOUT_FORBIDDEN_PHRASES:
            assert phrase not in text, f"{source_name} 仍包含本轮明确禁用的页面帮助文案：{phrase}"

    visible_sources = {
        "frontend/workbench/app/CalendarFields.jsx": _read(
            os.path.join(repo_root, "frontend", "workbench", "app", "CalendarFields.jsx")
        ),
        "core/services/common/excel_validators.py": _read(
            os.path.join(repo_root, "core", "services", "common", "excel_validators.py")
        ),
    }
    for source_name, text in visible_sources.items():
        for phrase in PAGE_MANUAL_CLOSEOUT_FORBIDDEN_TEMPLATE_PHRASES:
            assert phrase not in text, f"{source_name} 仍包含工作日历旧推荐文案：{phrase}"

    list_basics = str(dict(page_manuals.SHARED_FRAGMENTS).get("list_page_basics") or "")
    for phrase in PAGE_MANUAL_LIST_BASICS_REQUIRED_COPY:
        assert phrase in list_basics, f"list_page_basics 缺少按页面差异收窄后的列表说明：{phrase}"


def _assert_ready_check_visible_copy_contract(repo_root: str, page_manuals, manual_text: str) -> None:
    visible_sources = {
        "static/docs/scheduler_manual.md": manual_text,
        "core/services/scheduler/config/config_field_spec.py": _read(
            os.path.join(repo_root, "core", "services", "scheduler", "config", "config_field_spec.py")
        ),
        "frontend/workbench/app/BatchFiles.jsx": _read(
            os.path.join(repo_root, "frontend", "workbench", "app", "BatchFiles.jsx")
        ),
    }
    for manual_id in ("material_batch", "scheduler_batches", "scheduler_config"):
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建齐套检查文案校验 payload"
        visible_sources[f"page_manual:{manual_id}"] = _build_payload_text(payload)

    for source_name, text in visible_sources.items():
        for forbidden in READY_CHECK_LEGACY_FILTER_COPY:
            assert forbidden not in text, f"{source_name} 仍有容易误解成自动过滤的齐套检查旧文案：{forbidden}"

    for source_name in (
        "static/docs/scheduler_manual.md",
        "core/services/scheduler/config/config_field_spec.py",
    ):
        text = visible_sources[source_name]
        for phrase in READY_CHECK_REQUIRED_COPY:
            assert phrase in text, f"{source_name} 缺少齐套检查真实口径：{phrase}"


def _assert_no_legacy_page_title_terms(endpoint: str, current_manual: dict) -> None:
    help_card = current_manual.get("help_card") or {}
    title_text = "\n".join([str(current_manual.get("title") or ""), str(help_card.get("title") or "")])
    for term in LEGACY_PAGE_TITLE_TERMS:
        assert term not in title_text, f"{endpoint} 页面级说明标题仍包含旧 Excel 入口叫法：{term}"


def _assert_page_manual_refusal_conditions(page_manuals) -> None:
    for manual_id, phrases in PAGE_MANUAL_REFUSAL_CONDITION_CASES.items():
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建页面级详细说明 payload"
        payload_text = _build_payload_text(payload)
        for phrase in phrases:
            assert phrase in payload_text, f"{manual_id} 缺少页面级拒绝条件说明：{phrase}"


def _assert_process_page_manual_title_contracts(page_manuals) -> None:
    for endpoint, (expected_manual_id, expected_title, _expected_help_title) in PROCESS_PAGE_MANUAL_TITLE_CASES.items():
        bundle = page_manuals.build_page_manual_bundle(endpoint)
        assert bundle is not None, f"{endpoint} 应可构建页面级说明 bundle"
        current_manual = bundle.get("current_manual") or {}
        assert current_manual.get("manual_id") == expected_manual_id, (
            f"{endpoint} 的说明注册不应漂移："
            f"期望 manual_id={expected_manual_id}，实际 manual_id={current_manual.get('manual_id')}"
        )
        assert current_manual.get("title") == expected_title, (
            f"{endpoint} 的页面说明标题不应漂移："
            f"期望 {expected_title!r}，实际 {current_manual.get('title')!r}"
        )
        _assert_no_legacy_page_title_terms(endpoint, current_manual)


def _assert_process_user_corrected_wording_contracts(page_manuals) -> None:
    for manual_id, phrases in PROCESS_USER_CORRECTED_REQUIRED_PHRASES.items():
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建工艺说明纠偏 payload"
        payload_text = _build_payload_text(payload)
        for phrase in phrases:
            assert phrase in payload_text, f"{manual_id} 缺少工艺说明纠偏片段：{phrase}"

    for manual_id, phrases in PROCESS_USER_CORRECTED_FORBIDDEN_PHRASES.items():
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建工艺说明旧口径校验 payload"
        payload_text = _build_payload_text(payload)
        for phrase in phrases:
            assert phrase not in payload_text, f"{manual_id} 仍包含工艺说明旧口径：{phrase}"


def _assert_scheduler_page_manual_title_contracts(page_manuals) -> None:
    for endpoint, (expected_manual_id, expected_title, _expected_help_title) in SCHEDULER_PAGE_MANUAL_TITLE_CASES.items():
        bundle = page_manuals.build_page_manual_bundle(endpoint)
        assert bundle is not None, f"{endpoint} 应可构建页面级说明 bundle"
        current_manual = bundle.get("current_manual") or {}
        assert current_manual.get("manual_id") == expected_manual_id, (
            f"{endpoint} 的说明注册不应漂移："
            f"期望 manual_id={expected_manual_id}，实际 manual_id={current_manual.get('manual_id')}"
        )
        assert current_manual.get("title") == expected_title, (
            f"{endpoint} 的页面说明标题不应漂移："
            f"期望 {expected_title!r}，实际 {current_manual.get('title')!r}"
        )
        _assert_no_legacy_page_title_terms(endpoint, current_manual)


def _assert_home_page_manual_contract(page_manuals) -> None:
    bundle = page_manuals.build_page_manual_bundle("dashboard.index")
    assert bundle is not None, "dashboard.index 应可构建首页页面级说明 bundle"
    current_manual = bundle.get("current_manual") or {}
    assert current_manual.get("manual_id") == "dashboard_first_run", "首页说明 manual_id 不应漂移"
    assert current_manual.get("title") == "第一次使用路线图", "首页说明标题不应漂移"
    payload_text = _build_payload_text(current_manual)
    for phrase in HOME_PAGE_MANUAL_REQUIRED_PHRASES:
        assert phrase in payload_text, f"首页第一次使用路线图缺少关键文案：{phrase}"
    related_manuals = list(bundle.get("related_manuals") or [])
    assert related_manuals, "首页说明应提供相关页面说明，方便新用户继续看"
    related_ids = {str(item.get("manual_id") or "") for item in related_manuals}
    # 旧 Excel 页说明 2026-09 随启动期模板一起退役，首页只剩批次这一条后续指引；
    # 各张表怎么填改由说明书第 1 章的逐表指南承担，见 tests/gate_meta/test_table_doc_generation.py。
    assert {"scheduler_batches"} <= related_ids, f"首页说明 related_manuals 不完整：{sorted(related_ids)}"


def test_page_manual_registry_contract(monkeypatch) -> None:
    main(monkeypatch)


def test_process_page_manual_title_contracts() -> None:
    repo_root = _find_repo_root()
    _ensure_repo_on_path(repo_root)
    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    _assert_process_page_manual_title_contracts(page_manuals)


def test_process_user_corrected_wording_contracts() -> None:
    repo_root = _find_repo_root()
    _ensure_repo_on_path(repo_root)
    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    _assert_process_user_corrected_wording_contracts(page_manuals)


def test_scheduler_page_manual_title_contracts() -> None:
    repo_root = _find_repo_root()
    _ensure_repo_on_path(repo_root)
    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    _assert_scheduler_page_manual_title_contracts(page_manuals)


def test_home_page_manual_contract() -> None:
    repo_root = _find_repo_root()
    _ensure_repo_on_path(repo_root)
    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    _assert_home_page_manual_contract(page_manuals)


def test_page_manual_closeout_forbidden_phrases() -> None:
    repo_root = _find_repo_root()
    _ensure_repo_on_path(repo_root)
    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    _assert_page_manual_closeout_forbidden_phrases(page_manuals)


def test_user_corrected_manual_semantic_contracts() -> None:
    repo_root = _find_repo_root()
    _ensure_repo_on_path(repo_root)
    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    manual_text = _read(os.path.join(repo_root, "static", "docs", "scheduler_manual.md"))
    _assert_user_corrected_semantic_contracts(page_manuals, manual_text)


def test_page_manual_refusal_conditions() -> None:
    repo_root = _find_repo_root()
    _ensure_repo_on_path(repo_root)
    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    _assert_page_manual_refusal_conditions(page_manuals)


def test_material_manual_scope_contracts() -> None:
    repo_root = _find_repo_root()
    _ensure_repo_on_path(repo_root)
    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    _assert_material_manual_scope_contracts(page_manuals)


if __name__ == "__main__":
    from _pytest.monkeypatch import MonkeyPatch

    _mp = MonkeyPatch()
    try:
        main(_mp)
    finally:
        _mp.undo()
