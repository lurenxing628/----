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


def main() -> None:
    repo_root = _find_repo_root()
    tmpdir = tempfile.mkdtemp(prefix="aps_page_manual_registry_")
    _prepare_env(tmpdir)
    app = _load_app(repo_root)

    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    manual_path = os.path.join(repo_root, "static", "docs", "scheduler_manual.md")
    manual_text = _read(manual_path)
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
        "excel_personnel": ["在岗/启用/可用/正常/active", "停用/休假/停用/休假/离岗/inactive"],
        "excel_personnel_link": ["新手/一般/中级/高级/专家/low/high/skilled", "主/非主"],
        "excel_op_types": ["内部/外部", "internal/external", "内/外"],
        "excel_suppliers": ["填 `0`、负数或文字都会报错", "在用/正常/禁用", "状态和备注两列"],
        "excel_calendar": ["留空按 `工作日/workday` 处理", "高级设置中的“假期默认效率”"],
        "material_batch": ["需求数量必须大于 0", "已到数量允许为 0，但不能为负数"],
        "system_backup": ["恢复前自动备份", "自动回滚"],
    }
    for manual_id, phrases in manual_semantic_cases.items():
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建语义校验 payload"
        payload_text = _build_payload_text(payload)
        for phrase in phrases:
            assert phrase in payload_text, f"{manual_id} 缺少已核实语义片段：{phrase}"

    full_manual_phrases = [
        "非 yes/no 枚举列填了 TRUE/FALSE",
        '假期不填默认高级设置中的"假期默认效率"',
        "库存数量可以为 0，但不能为负数",
        '"需求数量"必须大于 0',
        "恢复过程失败，系统会尽最大努力回滚到这份备份",
        "批量删除前先确认筛选条件、已选条数和本次删除范围",
    ]
    for phrase in full_manual_phrases:
        assert phrase in manual_text, f"总说明书缺少已核实语义片段：{phrase}"

    print("OK")


if __name__ == "__main__":
    main()
