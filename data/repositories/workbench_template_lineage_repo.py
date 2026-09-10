"""Exact identity lookups and append-only copy evidence in the caller transaction."""

import secrets

from core.infrastructure.workbench_metadata_schema import workbench_metadata_contract_issues
from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues
from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
from core.infrastructure.workbench_template_lineage_schema import contract_issues, objects
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_template_lineage import (
    COPY_COLUMNS,
    EVIDENCE_VERSION,
    STATE_COLUMNS,
    fingerprint,
    state_snapshot,
)

from .base_repo import BaseRepository
from .workbench_execution_repo import chunks

MAX_EVIDENCE_BYTES = 16 * 1024 * 1024


class WorkbenchTemplateLineageRepository(BaseRepository):
    def available(self):
        names = {row[0] for row in self.conn.execute("SELECT name FROM sqlite_master")}
        if not names & set(objects()):
            return False
        if contract_issues(self.conn):
            raise WorkbenchCommandRejected("template_lineage_unavailable", "模板来源结构不完整，请恢复完整资料；本次没有自动补表。")
        return True

    def require_write(self):
        if not self.conn.in_transaction:
            raise RuntimeError("Template lineage writes require a caller transaction.")
        if not self.available():
            raise WorkbenchCommandRejected("template_lineage_schema_missing", "模板来源记录结构尚未安装，已阻止新复制；请先完成统一版本升级。")
        if (workbench_metadata_contract_issues(self.conn) or workbench_process_contract_issues(self.conn) or
                workbench_plan_identity_contract_issues(self.conn)):
            raise WorkbenchCommandRejected("template_lineage_unavailable", "来源模板或批次永久身份结构损坏，已阻止复制，未使用不可靠修订。")

    def template(self, template_id):
        row = self.fetchone("""SELECT o.*, r.ref AS template_operation_ref, r.revision AS template_revision,
            p.ref AS part_ref FROM PartOperations o LEFT JOIN WorkbenchEntityRefs r
            ON r.kind='template_operation' AND r.active=1 AND r.entity_key=CAST(o.id AS TEXT)
            LEFT JOIN WorkbenchEntityRefs p ON p.kind='part' AND p.active=1 AND p.entity_key=o.part_no
            WHERE o.id=? AND o.status='active'""", (template_id,))
        if row is None or row["template_operation_ref"] is None or row["part_ref"] is None:
            raise WorkbenchCommandRejected("template_lineage_unavailable", "来源模板或永久引用已失效，不能按图号或工序号补配。")
        return row

    def current_templates(self, refs):
        result = {}
        for chunk in chunks(refs):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall("""SELECT o.*, r.ref AS template_operation_ref, r.revision AS template_revision,
                p.ref AS part_ref FROM WorkbenchEntityRefs r LEFT JOIN PartOperations o ON r.entity_key=CAST(o.id AS TEXT)
                LEFT JOIN WorkbenchEntityRefs p ON p.kind='part' AND p.active=1 AND p.entity_key=o.part_no
                WHERE r.kind='template_operation' AND r.active=1 AND r.ref IN (""" + marks + ")", chunk)
            result.update((row["template_operation_ref"], row) for row in rows)
        return result

    def instance(self, operation_id):
        row = self.fetchone("""SELECT o.*, r.ref AS operation_ref, br.ref AS batch_ref, pr.ref AS part_ref, b.quantity
            FROM BatchOperations o JOIN Batches b ON b.batch_id=o.batch_id
            LEFT JOIN WorkbenchPlanSourceRefs r ON r.kind='operation' AND r.active=1 AND r.source_key=CAST(o.id AS TEXT)
            LEFT JOIN WorkbenchEntityRefs br ON br.kind='batch' AND br.active=1 AND br.entity_key=b.batch_id
            LEFT JOIN WorkbenchEntityRefs pr ON pr.kind='part' AND pr.active=1 AND pr.entity_key=b.part_no
            WHERE o.id=?""", (operation_id,))
        if row is None or any(row[key] is None for key in ("operation_ref", "batch_ref", "part_ref")):
            raise WorkbenchCommandRejected("template_lineage_unavailable", "批次实例或所属对象缺少永久引用，来源没有补配。")
        return row

    def current_instances(self, refs):
        result = {}
        for chunk in chunks(refs):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall("""SELECT o.*, r.ref AS operation_ref, br.ref AS batch_ref, pr.ref AS part_ref, b.quantity
                FROM WorkbenchPlanSourceRefs r JOIN BatchOperations o ON r.source_key=CAST(o.id AS TEXT)
                JOIN Batches b ON b.batch_id=o.batch_id
                LEFT JOIN WorkbenchEntityRefs br ON br.kind='batch' AND br.active=1 AND br.entity_key=b.batch_id
                LEFT JOIN WorkbenchEntityRefs pr ON pr.kind='part' AND pr.active=1 AND pr.entity_key=b.part_no
                WHERE r.kind='operation' AND r.active=1 AND r.ref IN (""" + marks + ")", chunk)
            result.update((row["operation_ref"], row) for row in rows)
        return result

    def insert_instance(self, payload):
        cursor = self.execute("INSERT INTO BatchOperations (" + ",".join(COPY_COLUMNS) + ") VALUES (" +
                              ",".join("?" for _ in COPY_COLUMNS) + ")", tuple(payload[key] for key in COPY_COLUMNS))
        return self.instance(cursor.lastrowid)

    def origins(self, refs):
        result = {}
        size = 0
        for chunk in chunks(refs):
            marks = ",".join("?" for _ in chunk)
            size += self._evidence_size("WorkbenchTemplateLineageOrigins", ("template_snapshot", "instance_snapshot"), chunk)
            self._check_size(size)
            for row in self.fetchall("SELECT * FROM WorkbenchTemplateLineageOrigins WHERE operation_ref IN (" + marks + ")", chunk):
                result[row["operation_ref"]] = row
        return result

    def events(self, refs):
        result = {}
        size = 0
        for chunk in chunks(refs):
            marks = ",".join("?" for _ in chunk)
            size += self._evidence_size("WorkbenchTemplateLineageEvents", STATE_COLUMNS + ("operation_ref", "reason", "recorded_at_utc"), chunk)
            self._check_size(size)
            rows = self.fetchall("SELECT * FROM WorkbenchTemplateLineageEvents WHERE operation_ref IN (" + marks +
                                 ") ORDER BY event_id LIMIT 50001", chunk)
            if len(rows) > 50000:
                raise WorkbenchCommandRejected("query_too_large", "模板来源变更超过50000条，请缩小范围；未截断证据。", 413)
            for row in rows:
                result.setdefault(row["operation_ref"], []).append(row)
        if sum(map(len, result.values())) > 50000:
            raise WorkbenchCommandRejected("query_too_large", "模板来源变更超过50000条，请缩小范围。", 413)
        return result

    def _evidence_size(self, table, columns, refs):
        sizes = "+".join('COALESCE(length(CAST("' + column + '" AS BLOB)),0)' for column in columns)
        row = self.fetchone("SELECT COALESCE(sum(" + sizes + "),0) AS bytes FROM " + table +
                            " WHERE operation_ref IN (" + ",".join("?" for _ in refs) + ")", refs)
        if row is None:
            raise RuntimeError("Cannot read lineage evidence size.")
        return row["bytes"]

    @staticmethod
    def _check_size(size):
        if size > MAX_EVIDENCE_BYTES:
            raise WorkbenchCommandRejected("query_too_large", "模板来源证据超过16MB，请缩小范围；未截断原始内容。", 413)

    def append_origin(self, instance, template, template_snapshot, *, source=None, source_event_id=None, source_eligible=True):
        self._require_unexecuted(instance)
        events = self.events([instance["operation_ref"]]).get(instance["operation_ref"], [])
        if len(events) != 1 or events[0]["event_type"] != "created" or state_snapshot(events[0]) != state_snapshot(instance):
            raise WorkbenchCommandRejected("template_lineage_not_new", "只能为本次新建且未发生变更的工序保存来源，旧实例不得追溯补填。")
        encoded = state_snapshot(instance)
        self._check_size(len(template_snapshot.encode("ascii")) + len(encoded.encode("ascii")))
        row = dict(lineage_ref=secrets.token_hex(24), operation_ref=instance["operation_ref"],
                   template_operation_ref=template["template_operation_ref"], template_revision=template["template_revision"],
                   source_operation_ref=source["operation_ref"] if source else None,
                   source_lineage_ref=source["lineage_ref"] if source else None, source_event_id=source_event_id,
                   source_eligible=int(source_eligible), birth_event_id=events[0]["event_id"],
                   evidence_version=EVIDENCE_VERSION, template_snapshot=template_snapshot,
                   template_fingerprint=fingerprint(template_snapshot), instance_snapshot=encoded, instance_fingerprint=fingerprint(encoded))
        self.conn.execute("INSERT INTO WorkbenchTemplateLineageOrigins (" + ",".join(row) + ") VALUES (" +
                          ",".join("?" for _ in row) + ")", tuple(row.values()))
        return row

    def _require_unexecuted(self, instance):
        names = {row[0] for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ("WorkbenchProductionReports", "WorkbenchExecutionLegacyFacts"):
            if table in names and self.fetchone("SELECT 1 FROM " + table + " WHERE operation_ref=? LIMIT 1", (instance["operation_ref"],)):
                raise WorkbenchCommandRejected("template_lineage_not_new", "已发生执行的工序不能补配或重绑定模板来源。")
        if "OperationExecutionEvents" in names and self.fetchone(
                "SELECT 1 FROM OperationExecutionEvents WHERE op_id=? LIMIT 1", (instance["id"],)):
            raise WorkbenchCommandRejected("template_lineage_not_new", "存在旧执行记录的工序不能追溯补配模板来源。")

    def withdraw(self, operation_ref, reason):
        self.require_write()
        if not isinstance(reason, str) or not reason.strip():
            raise WorkbenchCommandRejected("invalid_input", "撤回来源必须填写明确原因。", 400)
        rows = self.events([operation_ref]).get(operation_ref, [])
        if not self.origins([operation_ref]) or not rows:
            raise WorkbenchCommandRejected("entity_not_found", "没有可撤回的模板来源。", 404)
        if any(row["event_type"] == "withdrawn" for row in rows):
            return False
        row = rows[-1]
        self.conn.execute("INSERT INTO WorkbenchTemplateLineageEvents(operation_ref,event_type,affects_calibration,reason," +
                          ",".join(STATE_COLUMNS) + ") VALUES (?,'withdrawn',1,?," + ",".join("?" for _ in STATE_COLUMNS) + ")",
                          (operation_ref, reason.strip()) + tuple(row[key] for key in STATE_COLUMNS))
        return True
