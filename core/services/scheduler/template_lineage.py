"""Shared template/instance copies; origin evidence never uses heuristic matches."""

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_template_lineage import copy_payload, snapshot
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository

from .template_lineage_query import TemplateLineageQuery, validate_origin


class TemplateLineageWriter:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchTemplateLineageRepository(conn)

    def require_ready(self):
        self.repo.require_write()

    def copy_template(self, batch_id, template_id):
        self.require_ready()
        with TransactionManager(self.conn).transaction():
            template = self.repo.template(template_id)
            instance = self.repo.insert_instance(copy_payload(template, batch_id, from_template=True))
            if instance["part_ref"] != template["part_ref"]:
                raise WorkbenchCommandRejected("template_lineage_mismatch", "目标批次并不属于此来源模板零件，未按图号猜配。")
            self.repo.append_origin(instance, template, snapshot(template))
            return instance["id"]

    def copy_instance(self, batch_id, operation_id):
        self.require_ready()
        with TransactionManager(self.conn).transaction():
            original = self.repo.instance(operation_id)
            facts = TemplateLineageQuery(self.conn).read([original["operation_ref"]])
            instance = self.repo.insert_instance(copy_payload(original, batch_id, from_template=False))
            origin = facts["origins"].get(original["operation_ref"])
            # Known but polluted origins remain known and polluted after copying.
            if origin is not None:
                template, _ = validate_origin(origin, facts["events"][original["operation_ref"]])
                if instance["part_ref"] != template["part_ref"]:
                    raise WorkbenchCommandRejected("template_lineage_mismatch", "目标批次不属于原来源模板零件。")
                self.repo.append_origin(instance, template, origin["template_snapshot"], source=origin,
                    source_event_id=facts["events"][original["operation_ref"]][-1]["event_id"],
                    source_eligible=not facts["problems"][original["operation_ref"]])
            return instance["id"]

    def withdraw(self, operation_ref, reason):
        return self.repo.withdraw(operation_ref, reason)
