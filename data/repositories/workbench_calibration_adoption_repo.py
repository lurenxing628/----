"""Quota-lock read interface and atomic audit writes on the caller connection."""

import secrets

from core.infrastructure.workbench_calibration_adoption_schema import contract_issues
from core.models.workbench_calibration import MAX_TEMPLATES
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_execution_input import public_ref
from core.models.workbench_template_lineage import snapshot

from .base_repo import BaseRepository
from .workbench_execution_repo import chunks


class WorkbenchCalibrationAdoptionRepository(BaseRepository):
    def require_schema(self):
        if contract_issues(self.conn):
            raise WorkbenchCommandRejected("adoption_schema_unavailable", "采纳存储尚未安装或结构不完整，本次没有自动补表。", 503)

    def template(self, template_operation_ref):
        public_ref(template_operation_ref)
        row = self.fetchone("""SELECT o.*, r.ref AS template_operation_ref, r.revision AS template_revision,
            p.ref AS part_ref FROM WorkbenchEntityRefs r JOIN PartOperations o ON r.entity_key=CAST(o.id AS TEXT)
            LEFT JOIN WorkbenchEntityRefs p ON p.kind='part' AND p.active=1 AND p.entity_key=o.part_no
            WHERE r.ref=? AND r.kind='template_operation' AND r.active=1 AND o.status='active'""", (template_operation_ref,))
        if row is None:
            raise WorkbenchCommandRejected("entity_not_found", "模板永久引用已失效或不存在，不能按图号和序号重新绑定。", 404)
        if row["part_ref"] is None:
            raise WorkbenchCommandRejected("calibration_source_unavailable", "模板所属零件的永久身份缺失，未按图号补配。")
        return row

    def read_locks(self, template_operation_refs):
        """Return {permanent_ref: lock}; absent key means unlocked only with valid DDL.

        Ordinary writes/imports must call inside their own write transaction. This
        method never starts/commits a transaction, installs storage, or resolves codes.
        """
        self.require_schema()
        if isinstance(template_operation_refs, (str, bytes)):
            raise WorkbenchCommandRejected("invalid_input", "定额锁查询必须提供模板永久引用集合。", 400)
        refs = sorted({public_ref(ref) for ref in template_operation_refs})
        if len(refs) > MAX_TEMPLATES:
            raise WorkbenchCommandRejected("query_too_large", "定额锁查询最多10000个模板引用，未截断。", 413)
        result = {}
        for chunk in chunks(refs):
            marks = ",".join("?" for _ in chunk)
            audits = self.fetchall("SELECT template_operation_ref,adoption_ref FROM WorkbenchCalibrationAdoptions "
                                   "WHERE template_operation_ref IN (" + marks + ")", chunk)
            rows = self.fetchall("""SELECT l.*, a.template_operation_ref AS audit_template_ref,
                a.new_unit_hours, a.adopted_at, a.reason, a.declared_operator, a.confirmed, a.application_operator, a.method_version,
                a.sample_count, a.template_revision_after, a.request_key
                FROM WorkbenchCalibrationQuotaLocks l LEFT JOIN WorkbenchCalibrationAdoptions a
                ON a.adoption_ref=l.adoption_ref WHERE l.template_operation_ref IN (""" + marks + ")", chunk)
            if {row["template_operation_ref"] for row in audits} != {row["template_operation_ref"] for row in rows}:
                raise WorkbenchCommandRejected("calibration_lock_corrupt", "采纳审计与定额锁不成对，未按未锁定处理。", 500)
            for row in rows:
                if (row["audit_template_ref"] != row["template_operation_ref"] or row["new_unit_hours"] != row["locked_unit_hours"]
                        or row["adopted_at"] != row["locked_at"]):
                    raise WorkbenchCommandRejected("calibration_lock_corrupt", "定额锁内容与采纳审计不一致，未按未锁定处理。", 500)
                result[row["template_operation_ref"]] = {key: value for key, value in row.items()
                    if key not in ("audit_template_ref", "new_unit_hours", "adopted_at")}
                result[row["template_operation_ref"]]["locked"] = True
                result[row["template_operation_ref"]]["confirmed"] = row["confirmed"] == 1
        return result

    def require_unlocked(self, template_operation_refs):
        if not self.conn.in_transaction:
            raise RuntimeError("Quota write protection requires the caller write transaction.")
        locks = self.read_locks(template_operation_refs)
        if locks:
            raise WorkbenchCommandRejected("calibration_quota_locked", "已采纳的模板定额已锁定，不能覆盖。")

    def update_quota(self, template, value):
        if not self.conn.in_transaction:
            raise RuntimeError("Quota adoption requires the caller write transaction.")
        self.require_unlocked([template["template_operation_ref"]])
        if template["unit_hours"] != value:
            cursor = self.conn.execute("""UPDATE PartOperations SET unit_hours=? WHERE id=? AND unit_hours IS ?
                AND EXISTS (SELECT 1 FROM WorkbenchEntityRefs WHERE kind='template_operation' AND active=1
                AND ref=? AND revision=? AND entity_key=CAST(PartOperations.id AS TEXT))""",
                (value, template["id"], template["unit_hours"], template["template_operation_ref"], template["template_revision"]))
            if cursor.rowcount != 1:
                raise WorkbenchCommandRejected("stale_write", "模板定额在采纳前已变化，请重新预览核对。")
        after = self.template(template["template_operation_ref"])
        expected = {**template, "unit_hours": after["unit_hours"], "template_revision": after["template_revision"]}
        revision = template["template_revision"] + int(template["unit_hours"] != value)
        if snapshot(after) != snapshot(expected) or after["unit_hours"] != value or after["template_revision"] != revision:
            raise RuntimeError("Template adoption changed unexpected facts or failed to advance identity revision.")
        return after

    def append(self, evidence, after, intent, *, request_key, actor, adopted_at):
        if not self.conn.in_transaction:
            raise RuntimeError("Calibration audit requires the caller write transaction.")
        before, suggestion = evidence.template, evidence.suggestion
        row = {"adoption_ref": secrets.token_hex(24), "template_operation_ref": before["template_operation_ref"],
               "request_key": request_key, "template_revision_before": before["template_revision"],
               "template_revision_after": after["template_revision"], "old_unit_hours": before["unit_hours"],
               "new_unit_hours": after["unit_hours"], "reason": intent["reason"],
               "declared_operator": intent["declared_operator"], "confirmed": intent["confirm"], "application_operator": actor,
               "adopted_at": adopted_at, "generated_at": evidence.generated_at,
               "method_version": suggestion["method_version"], "sample_count": suggestion["sample_count"],
               "evidence_json": canonical_json({"snapshot": evidence.snapshot, "suggestion": suggestion, "samples": evidence.samples}),
               "template_before": snapshot(before), "template_after": snapshot(after)}
        self.conn.execute("INSERT INTO WorkbenchCalibrationAdoptions (" + ",".join(row) + ") VALUES (" +
                          ",".join("?" for _ in row) + ")", tuple(row.values()))
        self.conn.execute("""INSERT INTO WorkbenchCalibrationQuotaLocks
            (template_operation_ref,adoption_ref,locked_unit_hours,locked_at) VALUES (?,?,?,?)""",
            (row["template_operation_ref"], row["adoption_ref"], row["new_unit_hours"], adopted_at))
        return {key: value for key, value in row.items() if key not in ("evidence_json", "template_before", "template_after")}
