from __future__ import annotations

import importlib
import os
import re
import sys
import tempfile
from pathlib import Path


def _find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _prepare_env(tmpdir: str) -> None:
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(Path(tmpdir) / "aps_test.db")
    os.environ["APS_LOG_DIR"] = str(Path(tmpdir) / "logs")
    os.environ["APS_BACKUP_DIR"] = str(Path(tmpdir) / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(Path(tmpdir) / "templates_excel")
    os.environ["SECRET_KEY"] = "aps-page-manual-registry"


def _load_app(repo_root: str):
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("app", None)
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


def _extract_heading_ids(markdown_text: str) -> set[str]:
    ids: set[str] = set()
    for line in markdown_text.splitlines():
        m = re.match(r"^(#{2,4})\s+(.+)$", line.strip())
        if not m:
            continue
        ids.add(_slugify_heading(m.group(2)))
    return ids


def _build_payload_text(payload: dict) -> str:
    parts: list[str] = []
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
    "process.excel_op_type_page": ("excel_op_types", "批量维护工种", "工种配置——填写速查"),
    "process.excel_supplier_page": ("excel_suppliers", "批量维护供应商", "供应商配置——填写速查"),
    "process.excel_routes_page": ("excel_routes", "批量维护路线文字", "批量维护路线文字——填写速查"),
    "process.excel_part_op_hours_page": (
        "excel_part_op_hours",
        "批量维护工序工时",
        "批量维护工序工时——填写速查",
    ),
    "process.excel_part_ops_page": ("excel_part_ops_export", "导出工序清单", "这里导出工序清单，不是导入"),
}


EXCEL_PAGE_MANUAL_TITLE_CASES = {
    "personnel.excel_operator_page": ("excel_personnel", "批量维护人员", "批量维护人员——填写速查"),
    "personnel.excel_link_page": ("excel_personnel_link", "批量维护人员设备关系", "批量维护人员设备关系——填写速查"),
    "personnel.excel_operator_calendar_page": ("excel_personnel_calendar", "批量维护个人日历", "批量维护个人日历——填写速查"),
    "equipment.excel_machine_page": ("excel_equipment", "批量维护设备", "批量维护设备——填写速查"),
    "equipment.excel_link_page": ("excel_equipment_link", "批量维护设备人员关系", "批量维护设备人员关系——填写速查"),
    "scheduler.excel_batches_page": ("excel_batches", "批量维护批次", "批次信息——填写速查"),
    "scheduler.excel_calendar_page": ("excel_calendar", "批量维护工作日历", "工作日历——填写速查"),
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
    "excel_suppliers": [
        "对应工种",
        "启用/停用",
    ],
    "excel_batches": [
        "齐套和齐套日期默认只是显示信息",
        "只有执行排产时启用“齐套检查”",
        "发现未齐套或部分齐套批次",
        "报错并停止",
        "系统不会自动跳过这些批次继续排其它批次",
        "齐套日期只对齐套批次作为最早开工日",
    ],
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
    "excel_calendar": [
        "类型模板下拉推荐填：工作日 / 假期",
        "以前文件里写过 周末 / 节假日 的，系统会按假期理解",
    ],
    "excel_personnel_calendar": [
        "类型建议填：工作日 / 假期",
        "以前写过周末 / 节假日的，系统会按假期理解",
        "允许普通件/急件模板下拉优先填 是/否",
        "以前文件里写过 1/0 的，系统会尽量读懂",
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
        "完整周计划以导出的表格为准",
        "导出周计划表.xlsx",
        "没有单独的起止日期输入框",
    ],
    "reports_overdue": [
        "超期(天)按当前实现显示小数天",
        "不是向上取整",
        "当前页面显示的是小数天",
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
    "页面只预览前 50 行，并显示总行数",
    "完整周计划以 **导出周计划表.xlsx** 为准",
    "报表里的超期天数是小数天，不是只取整天",
    "资源负荷与利用率不展示完全没任务的资源",
    "按类别或全部批量停机时，默认只作用于状态为 **可用** 的设备",
    "恢复成功的完整口径是 **已从备份恢复并完成结构校验**",
]


PAGE_MANUAL_REFUSAL_CONDITION_CASES = {
    "excel_calendar": [
        "同一天不能重复",
        "可用工时和效率只接受有限数字",
        "TRUE/FALSE、NaN、Inf、Infinity 都会报错",
    ],
    "excel_personnel_calendar": [
        "工号必须已存在",
        "同一人同一天不能重复",
        "可用工时和效率只接受有限数字",
        "TRUE/FALSE、NaN、Inf、Infinity 都会报错",
        "效率小于等于 0",
        "系统会拒绝确认写入",
    ],
    "excel_suppliers": [
        "默认周期必须填写大于 0 的有限数字(天)",
        "留空、0、负数、文字、TRUE/FALSE、NaN、Inf、Infinity 都会报错",
        "如果供应商已被零件工序清单、批次工序或连续外协工序组引用，会拒绝导入",
    ],
    "excel_part_op_hours": [
        "换型时间和单件工时填非负的有限数字(小时)",
        "TRUE/FALSE、NaN、Inf、Infinity 或文字都会报错",
        "不支持“清空本类数据后重导”",
        "会直接报错",
        "图号和工序号找不到，就无法补工时",
    ],
}


SCHEDULER_PAGE_MANUAL_TITLE_CASES = {
    "scheduler.batches_page": ("scheduler_batches", "排产调度", "排产调度页先看这 5 点"),
    "scheduler.batch_detail": ("scheduler_batch_detail", "批次详情/批次工序", "批次工序不完整就排不出正确结果"),
}


HOME_PAGE_MANUAL_REQUIRED_PHRASES = [
    "第一次使用路线图",
    "先准备基础资料，再做模拟和正式排产",
    "不要一上来只导批次",
    "空工时按 0 小时处理",
    "日历类型空着按工作日理解",
    "先模拟排产",
    "确认没问题再执行排产",
    "甘特图",
    "周计划导出",
    "资源排班",
    "排产优化分析",
    "排产历史只看版本摘要、提醒和结果概况",
    "查看最近 10 条、50 条这类记录",
    "待排批次",
    "已排批次",
    "模拟排产只生成版本，不会把这里的批次改成已排",
    "超期批次",
    "最近排产版本",
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
    "excel_op_types": [
        "列：工种ID(必填不重复)、工种名称(必填)、归属。",
        "工种ID就是系统里的工种编号",
        "Excel 表头必须写“工种ID”，不要改成“工种编号”",
    ],
    "excel_suppliers": [
        "列：供应商ID（必填不重复）、名称（必填）、对应工种、默认周期、状态、备注。",
        "供应商ID就是系统里的供应商编号",
        "Excel 表头必须写“供应商ID”，不要改成“供应商编号”",
        "旧模板中已有数据行不会被系统擅自改写",
    ],
    "excel_routes": [
        "5数铣10钳20数车35标印",
        "只有匹配到启用且绑定工种的供应商时",
        "严格模式会停下并提示你补资料",
        "放宽模式会先处理能确认的内容",
    ],
    "excel_part_op_hours": [
        "只补空工时",
        "只补自制工序里“换型时间和单件工时都为 0”的行",
    ],
    "scheduler_analysis": [
        "不填版本、版本为空或填 latest，都会看最新历史版本",
        "输入不存在的版本时，页面会显示该版本不存在的占位，不会自动选最新",
    ],
}


PROCESS_USER_CORRECTED_FORBIDDEN_PHRASES = {
    "excel_op_types": [
        "列：工种编号",
        "`工种编号`：唯一且稳定",
    ],
    "excel_suppliers": [
        "列：供应商编号",
        "`供应商编号` 和 `名称` 必填",
        "新填数据请使用自制/外协",
        "新填数据请使用 `自制`/`外协`",
    ],
    "process_suppliers": [
        "外协工序会自动从这里取供应商和天数",
    ],
    "process_supplier_detail": [
        "外协工序就会自动带错供应商和天数",
    ],
    "excel_routes": [
        "外协工序会自动关联启用供应商与默认周期",
    ],
}


MATERIAL_UNSUPPORTED_BATCH_COPY_TERMS = (
    "Excel",
    "批量维护",
)


EXCEL_BLANK_DEFAULT_PAGE_CONTRACTS = {
    "excel_op_types": [
        "归属可留空",
        "留空默认自制",
    ],
    "excel_batches": [
        "不填默认普通",
        "不填默认齐套",
    ],
    "excel_calendar": [
        "工作日不填默认8",
        "假期不填默认0",
        "工作日默认1.0",
    ],
    "excel_personnel_calendar": [
        "班次开始写 08:00 这种格式，留空按 08:00",
        "不填默认是",
    ],
    "excel_part_op_hours": [
        "留空默认 0",
        "空单元格按 0 处理",
    ],
}


EXCEL_COMMON_ERROR_BLANK_CONFLICT_COPY = (
    "数量、工时、周期这类数字如果填成文字、负数、空值或无穷大",
)


def _ensure_repo_on_path(repo_root: str) -> None:
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def main() -> None:
    repo_root = _find_repo_root()
    tmpdir = tempfile.mkdtemp(prefix="aps_page_manual_registry_")
    _prepare_env(tmpdir)
    app = _load_app(repo_root)

    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    _assert_process_page_manual_title_contracts(page_manuals)
    _assert_excel_page_manual_title_contracts(page_manuals)
    _assert_process_user_corrected_wording_contracts(page_manuals)
    _assert_scheduler_page_manual_title_contracts(page_manuals)
    _assert_home_page_manual_contract(page_manuals)
    manual_path = os.path.join(repo_root, "static", "docs", "scheduler_manual.md")
    manual_text = _read(manual_path)
    _assert_user_corrected_semantic_contracts(page_manuals, manual_text)
    _assert_ready_check_visible_copy_contract(repo_root, page_manuals, manual_text)
    _assert_excel_common_fragment_contracts(page_manuals)
    _assert_page_manual_refusal_conditions(page_manuals)
    _assert_material_manual_scope_contracts(page_manuals)
    _assert_blank_default_pages_do_not_conflict_with_common_errors(page_manuals)
    _assert_page_manual_closeout_forbidden_phrases(page_manuals)
    manual_heading_ids = _extract_heading_ids(manual_text)

    endpoint_to_manual_id = dict(page_manuals.ENDPOINT_TO_MANUAL_ID)
    manual_entry_endpoints = dict(page_manuals.MANUAL_ENTRY_ENDPOINTS)
    endpoint_overrides = dict(page_manuals.ENDPOINT_OVERRIDES)
    manual_topics = dict(page_manuals.MANUAL_TOPICS)
    shared_fragments = dict(page_manuals.SHARED_FRAGMENTS)

    registered_endpoints = set(app.view_functions.keys())
    legacy_endpoints = {
        "excel_demo.index",
        "personnel.list_page",
        "personnel.detail_page",
        "personnel.teams_page",
        "personnel.operator_calendar_page",
        "personnel.excel_operator_page",
        "personnel.excel_link_page",
        "personnel.excel_operator_calendar_page",
        "equipment.list_page",
        "equipment.detail_page",
        "equipment.downtime_batch_page",
        "equipment.excel_machine_page",
        "equipment.excel_link_page",
        "process.list_parts",
        "process.part_detail",
        "process.op_types_page",
        "process.op_type_detail",
        "process.suppliers_page",
        "process.supplier_detail",
        "process.excel_op_type_page",
        "process.excel_supplier_page",
        "process.excel_routes_page",
        "process.excel_part_op_hours_page",
        "scheduler.batches_page",
        "scheduler.batches_manage_page",
        "scheduler.batch_detail",
        "scheduler.config_page",
        "scheduler.calendar_page",
        "scheduler.excel_batches_page",
        "scheduler.excel_calendar_page",
        "scheduler.gantt_page",
        "scheduler.resource_dispatch_page",
        "scheduler.analysis_page",
        "scheduler.week_plan_page",
        "material.materials_page",
        "material.batch_materials_page",
        "reports.index",
        "reports.overdue_page",
        "reports.utilization_page",
        "reports.downtime_page",
        "system.backup_page",
        "system.logs_page",
        "system.history_page",
        "process.excel_part_ops_page",
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
        "excel_personnel": ["在岗/启用/可用/正常", "停用 / 休假 / 停用/休假 / 离岗"],
        "excel_personnel_link": ["新手/一般/中级/高级/专家", "主/非主"],
        "excel_op_types": ["自制 / 外协", "新文件请只填这两个中文选项"],
        "excel_suppliers": ["留空、`0`、负数、文字、`TRUE/FALSE`、`NaN`、`Inf`、`Infinity`", "在用/正常/禁用", "状态和备注列"],
        "excel_calendar": ["留空按 `工作日` 处理", "高级设置中的“假期工作效率”"],
        "excel_part_op_hours": ["留空默认 0", "只补空工时"],
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
        "固定选项字段请填写中文值",
        "假期不填默认高级设置中的“假期工作效率”",
        "库存数量可以为 0，但不能为负数",
        '"需求数量"必须大于 0',
        "如果恢复过程失败，系统会尽最大努力恢复到这份备份",
        "批量删除前先确认筛选条件、已选条数和本次删除范围",
        "最后更新：2026年5月",
        "空工时按 0 小时处理",
        "日历类型空着按工作日理解",
        "系统管理 → 排产历史** 只看版本摘要、提醒和结果概况",
        "选择查看最近 10 条、50 条这类记录",
        "备份文件名由系统自动按时间和用途生成",
        "如果停机时间填错，先取消原停机，再按正确时间新建",
        "保存补齐资源",
        "最新排产版本",
        "模拟排产会留下版本记录，但不会把这里的批次状态改成已排",
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


def _assert_blank_default_pages_do_not_conflict_with_common_errors(page_manuals) -> None:
    for manual_id, required_phrases in EXCEL_BLANK_DEFAULT_PAGE_CONTRACTS.items():
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建允许留空默认值页面 payload"
        payload_text = _build_payload_text(payload)
        for phrase in required_phrases:
            assert phrase in payload_text, f"{manual_id} 缺少允许留空默认值说明：{phrase}"
        for forbidden in EXCEL_COMMON_ERROR_BLANK_CONFLICT_COPY:
            assert forbidden not in payload_text, f"{manual_id} 不能套用会否定留空默认值的通用错误说明：{forbidden}"


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
    surfaces: dict[str, str] = {}
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
        "templates/scheduler/excel_import_calendar.html": _read(
            os.path.join(repo_root, "templates", "scheduler", "excel_import_calendar.html")
        ),
        "core/services/common/excel_validators.py": _read(
            os.path.join(repo_root, "core", "services", "common", "excel_validators.py")
        ),
        "web/routes/domains/scheduler/scheduler_excel_calendar_rows.py": _read(
            os.path.join(repo_root, "web", "routes", "domains", "scheduler", "scheduler_excel_calendar_rows.py")
        ),
    }
    for source_name, text in visible_sources.items():
        for phrase in PAGE_MANUAL_CLOSEOUT_FORBIDDEN_TEMPLATE_PHRASES:
            assert phrase not in text, f"{source_name} 仍包含工作日历旧推荐文案：{phrase}"

    list_basics = str(dict(page_manuals.SHARED_FRAGMENTS).get("list_page_basics") or "")
    for phrase in PAGE_MANUAL_LIST_BASICS_REQUIRED_COPY:
        assert phrase in list_basics, f"list_page_basics 缺少按页面差异收窄后的列表说明：{phrase}"


def _assert_ready_check_visible_copy_contract(repo_root: str, page_manuals, manual_text: str) -> None:
    mirror_manual_path = os.path.join(repo_root, "web_new_test", "static", "docs", "scheduler_manual.md")
    mirror_manual_text = _read(mirror_manual_path)
    assert mirror_manual_text == manual_text, "V1/V2 两份 scheduler_manual.md 必须完全一致"

    visible_sources = {
        "static/docs/scheduler_manual.md": manual_text,
        "web_new_test/static/docs/scheduler_manual.md": mirror_manual_text,
        "web/viewmodels/scheduler_run_options.py": _read(
            os.path.join(repo_root, "web", "viewmodels", "scheduler_run_options.py")
        ),
        "core/services/scheduler/config/config_field_spec.py": _read(
            os.path.join(repo_root, "core", "services", "scheduler", "config", "config_field_spec.py")
        ),
        "web/routes/domains/scheduler/scheduler_config_display_state.py": _read(
            os.path.join(repo_root, "web", "routes", "domains", "scheduler", "scheduler_config_display_state.py")
        ),
        "templates/scheduler/excel_import_batches.html": _read(
            os.path.join(repo_root, "templates", "scheduler", "excel_import_batches.html")
        ),
    }
    for manual_id in ("excel_batches", "material_batch", "scheduler_batches", "scheduler_config"):
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建齐套检查文案校验 payload"
        visible_sources[f"page_manual:{manual_id}"] = _build_payload_text(payload)

    for source_name, text in visible_sources.items():
        for forbidden in READY_CHECK_LEGACY_FILTER_COPY:
            assert forbidden not in text, f"{source_name} 仍有容易误解成自动过滤的齐套检查旧文案：{forbidden}"

    for source_name in (
        "static/docs/scheduler_manual.md",
        "web_new_test/static/docs/scheduler_manual.md",
        "web/viewmodels/scheduler_run_options.py",
        "core/services/scheduler/config/config_field_spec.py",
        "web/routes/domains/scheduler/scheduler_config_display_state.py",
    ):
        text = visible_sources[source_name]
        for phrase in READY_CHECK_REQUIRED_COPY:
            assert phrase in text, f"{source_name} 缺少齐套检查真实口径：{phrase}"


def _assert_no_legacy_page_title_terms(endpoint: str, current_manual: dict) -> None:
    help_card = current_manual.get("help_card") or {}
    title_text = "\n".join([str(current_manual.get("title") or ""), str(help_card.get("title") or "")])
    for term in LEGACY_PAGE_TITLE_TERMS:
        assert term not in title_text, f"{endpoint} 页面级说明标题仍包含旧 Excel 入口叫法：{term}"


def _assert_excel_common_fragment_contracts(page_manuals) -> None:
    shared_fragments = dict(page_manuals.SHARED_FRAGMENTS)
    import_modes = str(shared_fragments.get("excel_import_modes") or "")
    check_result = str(shared_fragments.get("excel_check_result_meaning") or "")
    recheck = str(shared_fragments.get("excel_recheck_before_confirm") or "")
    write_result = str(shared_fragments.get("excel_write_result_meaning") or "")

    assert "检查阶段仍可能显示更新或无变化" in import_modes, "清空重导说明必须写清检查阶段仍可能显示更新或无变化"
    assert "确认写入不是“不动旧数据”" in import_modes, "清空重导说明必须避免用户把无变化理解成不动旧数据"
    assert "先删除这一类旧数据，再按 Excel 文件重新建立" in import_modes, "清空重导说明必须写清确认写入会重建数据"
    assert "检查阶段仍可能显示更新或无变化" in check_result, "检查结果说明也要提醒清空重导的更新/无变化口径"
    assert "重新按当前库数据和页面选项检查" in recheck, "重新检查说明不能只讲文件本身，必须包含当前库数据和页面选项"
    assert "导入模式、是否清空重导等检查条件变了" in recheck, "重新检查说明必须写清检查条件变化会要求重新检查"
    assert "行数据签名" not in recheck and "签名" not in recheck, "重新检查说明不应承诺行数据签名这类过强机制"
    assert "新增、更新、跳过、错误" in write_result, "导入完成统计必须写新增/更新/跳过/错误"
    assert "预览里的“无变化”常会并入跳过" in write_result, "导入完成统计必须写清无变化可能并入跳过"
    assert "新增、更新、无变化、跳过" not in write_result, "导入完成统计不应再承诺一定单独显示无变化"
    for forbidden in EXCEL_COMMON_ERROR_BLANK_CONFLICT_COPY:
        assert forbidden not in str(shared_fragments.get("excel_common_errors") or ""), (
            f"通用错误说明不能把允许留空默认值的字段一概说成会报错：{forbidden}"
        )


def _assert_page_manual_refusal_conditions(page_manuals) -> None:
    for manual_id, phrases in PAGE_MANUAL_REFUSAL_CONDITION_CASES.items():
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建页面级详细说明 payload"
        payload_text = _build_payload_text(payload)
        for phrase in phrases:
            assert phrase in payload_text, f"{manual_id} 缺少页面级拒绝条件说明：{phrase}"


def _assert_excel_page_manual_title_contracts(page_manuals) -> None:
    for endpoint, (expected_manual_id, expected_title, expected_help_title) in EXCEL_PAGE_MANUAL_TITLE_CASES.items():
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
        help_card = current_manual.get("help_card") or {}
        assert help_card.get("title") == expected_help_title, (
            f"{endpoint} 的“本页说明”弹层标题不应漂移："
            f"期望 {expected_help_title!r}，实际 {help_card.get('title')!r}"
        )
        _assert_no_legacy_page_title_terms(endpoint, current_manual)


def _assert_process_page_manual_title_contracts(page_manuals) -> None:
    for endpoint, (expected_manual_id, expected_title, expected_help_title) in PROCESS_PAGE_MANUAL_TITLE_CASES.items():
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
        help_card = current_manual.get("help_card") or {}
        assert help_card.get("title") == expected_help_title, (
            f"{endpoint} 的“本页说明”弹层标题不应漂移："
            f"期望 {expected_help_title!r}，实际 {help_card.get('title')!r}"
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
    for endpoint, (expected_manual_id, expected_title, expected_help_title) in SCHEDULER_PAGE_MANUAL_TITLE_CASES.items():
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
        help_card = current_manual.get("help_card") or {}
        assert help_card.get("title") == expected_help_title, (
            f"{endpoint} 的“本页说明”弹层标题不应漂移："
            f"期望 {expected_help_title!r}，实际 {help_card.get('title')!r}"
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
    assert {"excel_routes", "excel_part_op_hours", "excel_calendar", "scheduler_batches"} <= related_ids, (
        f"首页说明 related_manuals 不完整：{sorted(related_ids)}"
    )


def test_page_manual_registry_contract() -> None:
    main()


def test_process_page_manual_title_contracts() -> None:
    repo_root = _find_repo_root()
    _ensure_repo_on_path(repo_root)
    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    _assert_process_page_manual_title_contracts(page_manuals)


def test_excel_page_manual_title_contracts() -> None:
    repo_root = _find_repo_root()
    _ensure_repo_on_path(repo_root)
    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    _assert_excel_page_manual_title_contracts(page_manuals)


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


def test_blank_default_pages_do_not_conflict_with_common_errors() -> None:
    repo_root = _find_repo_root()
    _ensure_repo_on_path(repo_root)
    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    _assert_blank_default_pages_do_not_conflict_with_common_errors(page_manuals)


if __name__ == "__main__":
    main()
