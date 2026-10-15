"""Complete selected-template facts, captured together before a batch change."""

from .base_repo import BaseRepository


class WorkbenchProcessPartFactsRepository(BaseRepository):
    def capture(self, refs):
        identities, snapshots = {}, {}
        refs = list(dict.fromkeys(refs))
        for start in range(0, len(refs), 400):
            selected = refs[start:start + 400]
            marks = ",".join("?" for _ in selected)
            rows = self.fetchall("SELECT * FROM WorkbenchEntityRefs WHERE ref IN (" + marks + ")", selected)
            identities.update({row["ref"]: row for row in rows})
            codes = list(dict.fromkeys(row["entity_key"] for row in rows if row["kind"] == "part" and row["active"]))
            if not codes:
                continue
            code_marks = ",".join("?" for _ in codes)
            for row in self.fetchall("SELECT * FROM Parts WHERE part_no IN (" + code_marks + ")", codes):
                snapshots[row["part_no"]] = {"part": row, "operations": [], "groups": [], "batches": [],
                    "foreign_group_members": [], "template_identities": [], "workflow": [], "confirmations": []}
            for field, table, order in (("operations", "PartOperations", "id"), ("groups", "ExternalGroups", "group_id"),
                                         ("batches", "Batches", "batch_id")):
                for row in self.fetchall("SELECT * FROM " + table + " WHERE part_no IN (" + code_marks + ") ORDER BY " + order, codes):
                    if row["part_no"] in snapshots:
                        snapshots[row["part_no"]][field].append(row)
            for row in self.fetchall("SELECT g.part_no AS _owner,o.* FROM PartOperations o JOIN ExternalGroups g "
                                     "ON g.group_id=o.ext_group_id WHERE g.part_no IN (" + code_marks + ") "
                                     "AND o.part_no<>g.part_no ORDER BY o.id", codes):
                owner = row.pop("_owner")
                snapshots[owner]["foreign_group_members"].append(row)
            owners = {("template_operation", str(row["id"])): code for code in codes if code in snapshots
                      for row in snapshots[code]["operations"]}
            owners.update({("template_external_group", row["group_id"]): code for code in codes if code in snapshots
                           for row in snapshots[code]["groups"]})
            templates = self.fetchall("SELECT * FROM WorkbenchEntityRefs WHERE active=1 AND "
                "((kind='template_operation' AND entity_key IN (SELECT CAST(id AS TEXT) FROM PartOperations WHERE part_no IN (" + code_marks + "))) "
                "OR (kind='template_external_group' AND entity_key IN (SELECT group_id FROM ExternalGroups WHERE part_no IN (" + code_marks + ")))) ORDER BY ref", codes + codes)
            for row in templates:
                snapshots[owners[(row["kind"], row["entity_key"])]]["template_identities"].append(row)
            for field, table, order in (("workflow", "WorkbenchProcessWorkflow", "part_ref"),
                                        ("confirmations", "WorkbenchProcessOperationConfirmations", "operation_ref,stage")):
                for row in self.fetchall("SELECT * FROM " + table + " WHERE part_ref IN (" + marks + ") ORDER BY " + order, selected):
                    code = identities[row["part_ref"]]["entity_key"]
                    if code in snapshots:
                        snapshots[code][field].append(row)
        return {"identities": identities, "parts": snapshots}
