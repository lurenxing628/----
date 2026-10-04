"""Full selected-template facts, including hidden fields and retained history."""

import math
from datetime import date, datetime

from core.infrastructure.connection_guards import foreign_keys_enabled
from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.infrastructure.workbench_process_workflow_schema import workbench_process_workflow_contract_issues
from core.models.workbench_command import WorkbenchCommandRejected
from data.repositories.workbench_process_part_facts_repo import WorkbenchProcessPartFactsRepository


def _storage_issues(conn):
    return tuple(workbench_metadata_contract_issues(conn) + workbench_process_contract_issues(conn)
                 + workbench_process_workflow_contract_issues(conn))


def check_part_action_storage(conn, contracts=None):
    # 表结构校验可按 schema 版本复用（contracts）；foreign_keys 是连接设置，每次现查。
    issues = _storage_issues(conn) if contracts is None else contracts.get(_storage_issues)
    if not foreign_keys_enabled(conn) or issues:
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

    def snapshot(self, identity):
        code = identity.entity_key
        part = self.repo.part(code)
        if part is None:
            raise WorkbenchCommandRejected("entity_not_found", "零件已不存在，请返回列表重新选择。", 404)
        return {
            "identity": self.repo.identity(identity.ref),
            "part": part,
            "operations": self.repo.operations(code),
            "groups": self.repo.groups(code),
            "batches": self.repo.batches(code),
            "foreign_group_members": self.repo.foreign_group_members(code),
            "template_identities": self.repo.template_identities(code),
            "workflow": self.repo.workflow(identity.ref),
            "confirmations": self.repo.confirmations(identity.ref),
        }
