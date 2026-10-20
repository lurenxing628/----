"""Full selected-template facts, including hidden fields and retained history."""

import math
from collections import defaultdict
from datetime import date, datetime

from core.infrastructure.connection_guards import foreign_keys_enabled, schema_contract_memo
from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.infrastructure.workbench_process_workflow_schema import workbench_process_workflow_contract_issues
from core.models.workbench_command import WorkbenchCommandRejected
from data.repositories.workbench_process_part_facts_repo import WorkbenchProcessPartFactsRepository

from .projection import require_ref


def check_process_template(operations, groups, part_no, group_parts):
    group_keys = {row["group_id"] for row in groups}
    for row in operations:
        require_ref(row["ref"], "模板工序")
        if row["status"] not in ("active", "deleted") or type(row["seq"]) is not int or row["seq"] <= 0:
            raise WorkbenchCommandRejected("template_invalid", "原工序的序号或状态说不清。请到基础资料核对工序。", 422)
        if row["ext_group_id"] is not None and row["ext_group_id"] not in group_keys:
            raise WorkbenchCommandRejected("group_invalid", "原工序关联外协组不存在或属于其他零件，请先核对资料。", 422)
    for row in groups:
        require_ref(row["ref"], "模板外协组")
        if type(row["start_seq"]) is not int or type(row["end_seq"]) is not int or not 0 < row["start_seq"] <= row["end_seq"]:
            raise WorkbenchCommandRejected("group_invalid", "原外协组的工序范围说不清，算不准影响面。请到基础资料核对外协组起止序。", 422)
    if any(owner != part_no for group_id in group_keys for owner in group_parts.get(group_id, ())):
        raise WorkbenchCommandRejected("group_invalid", "这个外协组还被别的零件工序用着，不能在当前零件解除。请先到那些零件上解除。", 422)


def checked_process_facts(identity, facts):
    """Select the current template once for both review and its actual change."""
    part_no = identity.entity_key
    part = next((row for row in facts["parts"] if row["part_no"] == part_no), None)
    if part is None:
        raise WorkbenchCommandRejected("entity_not_found", "这个零件不存在。请刷新列表后重新选择。", 404)
    groups = [row for row in facts["groups"] if row["part_no"] == part_no]
    operations, group_parts = [], defaultdict(set)
    for row in facts["operations"]:
        if row["part_no"] == part_no:
            operations.append(row)
        if groups and row["ext_group_id"] is not None:
            group_parts[row["ext_group_id"]].add(row["part_no"])
    check_process_template(operations, groups, part_no, group_parts)
    return identity, part, operations, groups, facts["workflow"][part_no]["workflow"]


def check_part_action_storage(conn, contracts=None):
    # 本命令不执行 DDL、不改外键设置；逐行写入共用首次入口的检查结果。
    contracts = contracts if contracts is not None else schema_contract_memo(conn)
    issues = (contracts.get_schema(workbench_metadata_contract_issues)
              + contracts.get_schema(workbench_process_contract_issues)
              + contracts.get_schema(workbench_process_workflow_contract_issues))
    if not contracts.get(foreign_keys_enabled) or issues:
        raise WorkbenchCommandRejected("storage_failure", "工艺数据的保存设置不完整，这次没有改动任何资料。请刷新重试；仍不行请联系维护人员。", 500)


def plain_part_action_facts(value):
    if isinstance(value, dict):
        return {key: plain_part_action_facts(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain_part_action_facts(item) for item in value]
    if isinstance(value, (date, datetime)):
        return {"storage_type": type(value).__name__, "iso": value.isoformat()}
    if isinstance(value, bytes):
        return {"storage_type": "blob", "hex": value.hex()}
    if isinstance(value, float) and not math.isfinite(value):
        return {"storage_type": "float", "value": str(value)}
    return value


class ProcessPartActionFacts:
    def __init__(self, conn, logger=None):
        self.repo = WorkbenchProcessPartFactsRepository(conn, logger)

    def capture(self, refs):
        return self.repo.capture(refs)

    @staticmethod
    def snapshot(identity, captured):
        code = identity.entity_key
        snapshot = captured["parts"].get(code)
        if snapshot is None:
            raise WorkbenchCommandRejected("entity_not_found", "零件已不存在，请返回列表重新选择。", 404)
        return dict(snapshot, identity=captured["identities"].get(identity.ref))
