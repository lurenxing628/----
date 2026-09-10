"""Full selected-template facts, including hidden fields and retained history."""

import math
from datetime import date, datetime

from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.infrastructure.workbench_process_workflow_schema import workbench_process_workflow_contract_issues
from core.models.workbench_command import WorkbenchCommandRejected
from data.repositories.base_repo import BaseRepository


def check_part_action_storage(conn):
    issues = (workbench_metadata_contract_issues(conn) + workbench_process_contract_issues(conn)
              + workbench_process_workflow_contract_issues(conn))
    if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1 or issues:
        raise WorkbenchCommandRejected("storage_failure", "工艺数据保存设置不完整，请检查本机数据库；未修改资料。", 500)


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


class ProcessPartActionFacts(BaseRepository):
    def snapshot(self, identity):
        code = identity.entity_key
        part = self.fetchone("SELECT * FROM Parts WHERE part_no=?", (code,))
        if part is None:
            raise WorkbenchCommandRejected("entity_not_found", "零件已不存在，请返回列表重新选择。", 404)
        return {
            "identity": self.fetchone("SELECT * FROM WorkbenchEntityRefs WHERE ref=?", (identity.ref,)),
            "part": part,
            "operations": self.fetchall("SELECT * FROM PartOperations WHERE part_no=? ORDER BY id", (code,)),
            "groups": self.fetchall("SELECT * FROM ExternalGroups WHERE part_no=? ORDER BY group_id", (code,)),
            "batches": self.fetchall("SELECT * FROM Batches WHERE part_no=? ORDER BY batch_id", (code,)),
            "foreign_group_members": self.fetchall("""SELECT o.* FROM PartOperations o
                JOIN ExternalGroups g ON g.group_id=o.ext_group_id
                WHERE g.part_no=? AND o.part_no<>? ORDER BY o.id""", (code, code)),
            "template_identities": self._template_identities(code),
            "workflow": self.fetchall("SELECT * FROM WorkbenchProcessWorkflow WHERE part_ref=?", (identity.ref,)),
            "confirmations": self.fetchall("""SELECT * FROM WorkbenchProcessOperationConfirmations
                WHERE part_ref=? ORDER BY operation_ref,stage""", (identity.ref,)),
        }

    def _template_identities(self, code):
        return self.fetchall("""SELECT * FROM WorkbenchEntityRefs WHERE active=1 AND (
            (kind='template_operation' AND entity_key IN (
                SELECT CAST(id AS TEXT) FROM PartOperations WHERE part_no=?)) OR
            (kind='template_external_group' AND entity_key IN (
                SELECT group_id FROM ExternalGroups WHERE part_no=?))) ORDER BY ref""", (code, code))
