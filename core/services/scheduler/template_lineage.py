"""Shared template/instance copies; origin evidence never uses heuristic matches.

The repository only reads identity rows and appends evidence; every ruling about
missing storage, broken identities, executed instances and withdrawal inputs is here.
"""

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_template_lineage import copy_payload, snapshot, state_snapshot
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository

from .template_lineage_query import (
    TemplateLineageQuery,
    check_evidence_size,
    lineage_available,
    read_events,
    read_origins,
    validate_origin,
)


def _instance_row(row):
    if row is None or any(row[key] is None for key in ("operation_ref", "batch_ref", "part_ref")):
        raise WorkbenchCommandRejected("template_lineage_unavailable", "批次实例或所属对象缺少永久引用，来源没有补配。")
    return row


class TemplateLineageWriter:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchTemplateLineageRepository(conn)

    def require_ready(self):
        if not self.conn.in_transaction:
            raise RuntimeError("Template lineage writes require a caller transaction.")
        if not lineage_available(self.repo):
            raise WorkbenchCommandRejected("template_lineage_schema_missing", "模板来源记录结构尚未安装，已阻止新复制；请先完成统一版本升级。")
        if self.repo.identity_schema_broken():
            raise WorkbenchCommandRejected("template_lineage_unavailable", "来源模板或批次永久身份结构损坏，已阻止复制，未使用不可靠修订。")

    def template(self, template_id):
        row = self.repo.template(template_id)
        if row is None or row["template_operation_ref"] is None or row["part_ref"] is None:
            raise WorkbenchCommandRejected("template_lineage_unavailable", "来源模板或永久引用已失效，不能按图号或工序号补配。")
        return row

    def instance(self, operation_id):
        return _instance_row(self.repo.instance(operation_id))

    def copy_template(self, batch_id, template_id):
        self.require_ready()
        with TransactionManager(self.conn).transaction():
            template = self.template(template_id)
            instance = _instance_row(self.repo.insert_instance(copy_payload(template, batch_id, from_template=True)))
            if instance["part_ref"] != template["part_ref"]:
                raise WorkbenchCommandRejected("template_lineage_mismatch", "目标批次并不属于此来源模板零件，未按图号猜配。")
            self.record_origin(instance, template, snapshot(template))
            return instance["id"]

    def copy_instance(self, batch_id, operation_id):
        self.require_ready()
        with TransactionManager(self.conn).transaction():
            original = self.instance(operation_id)
            facts = TemplateLineageQuery(self.conn).read([original["operation_ref"]])
            instance = _instance_row(self.repo.insert_instance(copy_payload(original, batch_id, from_template=False)))
            origin = facts["origins"].get(original["operation_ref"])
            # Known but polluted origins remain known and polluted after copying.
            if origin is not None:
                template, _ = validate_origin(origin, facts["events"][original["operation_ref"]])
                if instance["part_ref"] != template["part_ref"]:
                    raise WorkbenchCommandRejected("template_lineage_mismatch", "目标批次不属于原来源模板零件。")
                self.record_origin(instance, template, origin["template_snapshot"], source=origin,
                    source_event_id=facts["events"][original["operation_ref"]][-1]["event_id"],
                    source_eligible=not facts["problems"][original["operation_ref"]])
            return instance["id"]

    def _require_unexecuted(self, instance):
        if self.repo.has_execution_facts(instance["operation_ref"]):
            raise WorkbenchCommandRejected("template_lineage_not_new", "已发生执行的工序不能补配或重绑定模板来源。")
        if self.repo.has_legacy_execution_events(instance["id"]):
            raise WorkbenchCommandRejected("template_lineage_not_new", "存在旧执行记录的工序不能追溯补配模板来源。")

    def record_origin(self, instance, template, template_snapshot, *, source=None, source_event_id=None, source_eligible=True):
        self._require_unexecuted(instance)
        events = read_events(self.repo, [instance["operation_ref"]]).get(instance["operation_ref"], [])
        if len(events) != 1 or events[0]["event_type"] != "created" or state_snapshot(events[0]) != state_snapshot(instance):
            raise WorkbenchCommandRejected("template_lineage_not_new", "只能为本次新建且未发生变更的工序保存来源，旧实例不得追溯补填。")
        check_evidence_size(len(template_snapshot.encode("ascii")) + len(state_snapshot(instance).encode("ascii")))
        return self.repo.append_origin(instance, template, template_snapshot, birth_event_id=events[0]["event_id"],
                                       source=source, source_event_id=source_event_id, source_eligible=source_eligible)

    def withdraw(self, operation_ref, reason):
        self.require_ready()
        if not isinstance(reason, str) or not reason.strip():
            raise WorkbenchCommandRejected("invalid_input", "撤回来源必须填写明确原因。", 400)
        rows = read_events(self.repo, [operation_ref]).get(operation_ref, [])
        if not read_origins(self.repo, [operation_ref]) or not rows:
            raise WorkbenchCommandRejected("entity_not_found", "没有可撤回的模板来源。", 404)
        if any(row["event_type"] == "withdrawn" for row in rows):
            return False
        self.repo.append_withdrawn_event(operation_ref, reason.strip(), rows[-1])
        return True
