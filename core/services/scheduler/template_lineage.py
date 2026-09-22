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
        raise WorkbenchCommandRejected("template_lineage_unavailable", "这道批次工序或它所属的批次、零件缺少记录，模板来源没有自动补上，这次没有保存。请刷新后重试；仍不行请联系维护人员。")
    return row


class TemplateLineageWriter:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchTemplateLineageRepository(conn)

    def require_ready(self):
        if not self.conn.in_transaction:
            raise RuntimeError("Template lineage writes require a caller transaction.")
        if not lineage_available(self.repo):
            raise WorkbenchCommandRejected("template_lineage_schema_missing", "模板来源记录的数据表还没安装，这次复制没有执行。请先完成统一版本升级后重试。")
        if self.repo.identity_schema_broken():
            raise WorkbenchCommandRejected("template_lineage_unavailable", "来源模板或批次的记录结构已损坏，这次复制没有执行，系统没有用不可靠的版本继续。请联系维护人员。")

    def template(self, template_id):
        row = self.repo.template(template_id)
        if row is None or row["template_operation_ref"] is None or row["part_ref"] is None:
            raise WorkbenchCommandRejected("template_lineage_unavailable", "来源模板的记录已失效或找不到了，系统不会按图号或工序号猜着匹配，这次没有复制。请刷新后重新选择。")
        return row

    def instance(self, operation_id):
        return _instance_row(self.repo.instance(operation_id))

    def copy_template(self, batch_id, template_id):
        self.require_ready()
        with TransactionManager(self.conn).transaction():
            template = self.template(template_id)
            instance = _instance_row(self.repo.insert_instance(copy_payload(template, batch_id, from_template=True)))
            if instance["part_ref"] != template["part_ref"]:
                raise WorkbenchCommandRejected("template_lineage_mismatch", "目标批次不是这个来源模板的零件，系统没有按图号猜着匹配，这次没有复制。请重新选择批次。")
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
                    raise WorkbenchCommandRejected("template_lineage_mismatch", "目标批次不是原来源模板的零件，这次没有复制。请重新选择批次。")
                self.record_origin(instance, template, origin["template_snapshot"], source=origin,
                    source_event_id=facts["events"][original["operation_ref"]][-1]["event_id"],
                    source_eligible=not facts["problems"][original["operation_ref"]])
            return instance["id"]

    def _require_unexecuted(self, instance):
        if self.repo.has_execution_facts(instance["operation_ref"]):
            raise WorkbenchCommandRejected("template_lineage_not_new", "已开工的工序不能再补上或改动模板来源，这次没有保存。")
        if self.repo.has_legacy_execution_events(instance["id"]):
            raise WorkbenchCommandRejected("template_lineage_not_new", "有历史报工记录的工序不能再往前补模板来源，这次没有保存。")

    def record_origin(self, instance, template, template_snapshot, *, source=None, source_event_id=None, source_eligible=True):
        self._require_unexecuted(instance)
        events = read_events(self.repo, [instance["operation_ref"]]).get(instance["operation_ref"], [])
        if len(events) != 1 or events[0]["event_type"] != "created" or state_snapshot(events[0]) != state_snapshot(instance):
            raise WorkbenchCommandRejected("template_lineage_not_new", "只有这次新增、还没改过的工序才能记录模板来源，原有的工序不能往前补，这次没有保存。")
        check_evidence_size(len(template_snapshot.encode("ascii")) + len(state_snapshot(instance).encode("ascii")))
        return self.repo.append_origin(instance, template, template_snapshot, birth_event_id=events[0]["event_id"],
                                       source=source, source_event_id=source_event_id, source_eligible=source_eligible)

    def withdraw(self, operation_ref, reason):
        self.require_ready()
        if not isinstance(reason, str) or not reason.strip():
            raise WorkbenchCommandRejected("invalid_input", "撤回模板来源必须填写原因，这次没有撤回。请填好原因后重新提交。", 400)
        rows = read_events(self.repo, [operation_ref]).get(operation_ref, [])
        if not read_origins(self.repo, [operation_ref]) or not rows:
            raise WorkbenchCommandRejected("entity_not_found", "这道工序没有可撤回的模板来源。请刷新后重新选择。", 404)
        if any(row["event_type"] == "withdrawn" for row in rows):
            return False
        self.repo.append_withdrawn_event(operation_ref, reason.strip(), rows[-1])
        return True
