"""用户可见文案词表守卫：扫描器残留必须为 0。

词表决策：.codestable/compound/2026-09-13-decision-ui-copy-glossary.md
机器可读词表：tools/ui_copy_glossary.json（例外只能通过 allow 段加白名单，并写明理由）。
"""
import json
from pathlib import Path

from tools.scan_ui_copy import GLOSSARY_PATH, collect, load_glossary

ROOT = Path(__file__).resolve().parents[2]


def test_ui_copy_has_no_banned_terms():
    scan, rules, allow = load_glossary(GLOSSARY_PATH)
    hits = collect(scan, rules, allow)
    lines = [f"{h['file']}:{h['line']} [{h['term']}] {h['replace']} | {h['text']}" for h in hits]
    assert not hits, "用户可见文案里还有词表停用词（详见 python3 -m tools.scan_ui_copy）：\n" + "\n".join(lines[:40])


def test_backend_scan_covers_execution_gap_messages():
    """core/services/execution 的 gap(...) 提示原样进界面，词表必须扫它。

    2026-09-21 真机截图证实：现场记录详情的提示条、报表中心“数据完整性”页签的“数据缺口”列、
    报表详情抽屉、“统计说明与待补资料”折叠区显示的就是这些 message；但 scan.backend 只列了
    core/services/workbench 等目录，“旧事实 / 证据 / 引用 / 核实”这类停用词一直没被扫到。
    """
    scan, _rules, _allow = load_glossary(GLOSSARY_PATH)
    assert "core/services/execution" in scan["backend"], (
        "tools/ui_copy_glossary.json 的 scan.backend 少了 core/services/execution，"
        "现场记录 / 报表中心显示的数据缺口提示不会再被词表扫到")


def test_backend_scan_covers_shared_policy_messages_lifted_into_workbench():
    """工艺定额锁定与模板来源的拒绝文案写在 core/services 共享策略模块里，词表必须扫它们。

    core/services/workbench/process/quota_protection.py、calibration/template_lineage.py、
    calibration/template_lineage_query.py 只是转发导入；真正的句子在 core/services/process 与
    core/services/scheduler 下，WorkbenchCommandRejected 经 web/routes/workbench/api_responses.py
    的 api_endpoint 原样 str(exc) 返回给界面，_problems 的 issue(...) 进校准明细的排除原因列表。
    2026-09-21 之前 scan.backend 只列了 core/services/workbench，“引用 / 采纳 / 实例 / 对象 / 样本”
    这类停用词一直没被扫到（临时词表试扫 30 处）。
    """
    scan, _rules, _allow = load_glossary(GLOSSARY_PATH)
    for path in ("core/services/process/quota_protection.py",
                 "core/services/scheduler/template_lineage.py",
                 "core/services/scheduler/template_lineage_query.py"):
        assert path in scan["backend"], (
            "tools/ui_copy_glossary.json 的 scan.backend 少了 " + path +
            "，工艺定额锁定 / 模板来源的拒绝提示不会再被词表扫到")


def test_backend_scan_covers_domain_service_rejections_surfaced_by_workbench():
    """工种 / 供应商 / 零件 / 批次领域服务的拒绝文案与执行记录适配器的提示直接上屏，词表必须扫它们。

    core/services/workbench/resource/entities.py、resource/suppliers.py、process/part_actions.py、
    batch/service.py 直接调用 OpTypeService / SupplierService / PartService / BatchService 的
    create / delete；它们抛的 BusinessError 被 WorkbenchCommandService.execute 原样放行，再由
    web/routes/workbench/api_responses.py 的 _domain_failure 把 exc.message 返回给界面。
    core/services/scheduler/execution/execution_ledger_adapter.py 的 AppError 经
    trial/execution_anchors.anchor_issue 与 run/input_admission.piece_admission_issues 取 exc.message
    进试调问题列表和排产阻断项（2026-09-21 之前是 str(exc)，会把“[6003] ”这类错误码前缀带上屏）。2026-09-21 之前这五个文件都不在 scan.backend 里，
    “引用 / 添加 / 清空 / 台账 / 对象”这类停用词一直没被扫到（临时词表试扫 30 处）。
    """
    scan, _rules, _allow = load_glossary(GLOSSARY_PATH)
    for path in ("core/services/process/op_type_service.py",
                 "core/services/process/supplier_service.py",
                 "core/services/process/part_service.py",
                 "core/services/batch/service.py",
                 "core/services/scheduler/execution/execution_ledger_adapter.py"):
        assert path in scan["backend"], (
            "tools/ui_copy_glossary.json 的 scan.backend 少了 " + path +
            "，重复编号 / 还在用不能删 / 报工记录未就绪这些提示不会再被词表扫到")


def test_backend_scan_covers_equipment_personnel_team_service_rejections_surfaced_by_workbench():
    """设备 / 人员 / 班组领域服务的拒绝文案走同一条上屏路径，词表必须扫它们。

    core/services/workbench/resource/entities.py 按 kind 直接构造 MachineService / OperatorService，
    apply 里调用它们的 create / delete；重复编号、还有批次工序或排产结果在用不能删这些 BusinessError
    被 WorkbenchCommandService.execute 原样放行，再由 web/routes/workbench/api_responses.py 的
    _domain_failure 把 exc.message 返回给界面。ResourceTeamService 目前只被已退役的资源派工页只读构造，
    纳入是为了整文件扫描归零。2026-09-21 之前这三个文件不在 scan.backend 里，
    “引用 / 添加 / 清空”这类停用词一直没被扫到（临时词表试扫 17 处）。
    """
    scan, _rules, _allow = load_glossary(GLOSSARY_PATH)
    for path in ("core/services/equipment/machine_service.py",
                 "core/services/personnel/operator_service.py",
                 "core/services/personnel/resource_team_service.py"):
        assert path in scan["backend"], (
            "tools/ui_copy_glossary.json 的 scan.backend 少了 " + path +
            "，重复编号 / 还在用不能删这些提示不会再被词表扫到")


def test_allowlist_entries_explain_themselves():
    data = json.loads((ROOT / "tools" / "ui_copy_glossary.json").read_text(encoding="utf-8"))
    for item in data["allow"]:
        assert item.get("why") or item["path"].endswith("Outsourcing") or "outsourcing" in item["path"], item


def test_every_scanned_path_triggers_this_gate():
    """词表扫哪里，必跑组就得把哪里列进 input_file_scopes。

    这条门禁只有在被它守的文件触发时才会跑。2026-09-21 之前组里只覆盖了 frontend 一类，
    改说明书、改工作台服务层的提示语都不会触发它——一个停用词写进说明书第 14 章，
    跑到整目录全量才发现。词表以后扩范围，这条会先红。
    """
    import fnmatch

    from tools.test_registry_workbench_ui import WORKBENCH_UI_REQUIRED_REGRESSION_GROUPS

    group = next(item for item in WORKBENCH_UI_REQUIRED_REGRESSION_GROUPS
                 if item["group_id"] == "workbench_ui_refinement")
    scopes = group["input_file_scopes"]
    scan, _rules, _allow = load_glossary(GLOSSARY_PATH)

    uncovered = []
    for entry in (item for paths in scan.values() for item in paths):
        candidates = [str(path.relative_to(ROOT)) for path in ROOT.glob(entry)] or [entry]
        for candidate in candidates:
            files = ([str(path.relative_to(ROOT)) for path in (ROOT / candidate).rglob("*") if path.is_file()]
                     if (ROOT / candidate).is_dir() else [candidate])
            if not any(fnmatch.fnmatch(name, pattern) for name in files for pattern in scopes):
                uncovered.append(candidate)
    assert not uncovered, ("词表扫这些路径，但 workbench_ui_refinement 组的 input_file_scopes 没覆盖，"
                           "改它们不会触发文案门禁：\n  " + "\n  ".join(sorted(set(uncovered))))
