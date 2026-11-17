"""Complete selected-template facts, captured together before a batch change."""

import json

from .base_repo import BaseRepository
from .sqlite_rows import raw_table_select_sql


class WorkbenchProcessPartFactsRepository(BaseRepository):
    def capture(self, refs):
        rows = self.fetchall(
            "SELECT * FROM WorkbenchEntityRefs WHERE ref IN (SELECT value FROM json_each(?))",
            (json.dumps(list(refs)),),
        )
        identities = {row["ref"]: row for row in rows}
        codes = [row["entity_key"] for row in rows if row["kind"] == "part" and row["active"]]
        if not codes:
            return {"identities": identities, "parts": {}}
        snapshots = {}
        encoded_codes = json.dumps(codes)
        for row in self.fetchall(
            "SELECT * FROM Parts WHERE part_no IN (SELECT value FROM json_each(?))",
            (encoded_codes,),
        ):
            snapshots[row["part_no"]] = {"part": row, "operations": [], "groups": [], "batches": [],
                "foreign_group_members": [], "template_identities": []}
        for field, table, order in (("operations", "PartOperations", "id"), ("groups", "ExternalGroups", "group_id"),
                                     ("batches", "Batches", "batch_id")):
            for row in self.fetchall(
                raw_table_select_sql(table) + " WHERE part_no IN (SELECT value FROM json_each(?)) ORDER BY " + order,
                (encoded_codes,),
            ):
                if row["part_no"] in snapshots:
                    snapshots[row["part_no"]][field].append(row)
        for row in self.fetchall(
            "SELECT g.part_no AS _owner,o.* FROM PartOperations o JOIN ExternalGroups g "
            "ON g.group_id=o.ext_group_id WHERE g.part_no IN (SELECT value FROM json_each(?)) "
            "AND o.part_no<>g.part_no ORDER BY o.id",
            (encoded_codes,),
        ):
            owner = row.pop("_owner")
            snapshots[owner]["foreign_group_members"].append(row)
        owners = {("template_operation", str(row["id"])): code for code in codes if code in snapshots
                  for row in snapshots[code]["operations"]}
        owners.update({("template_external_group", row["group_id"]): code for code in codes if code in snapshots
                       for row in snapshots[code]["groups"]})
        templates = self.fetchall(
            "SELECT * FROM WorkbenchEntityRefs WHERE active=1 AND "
            "((kind='template_operation' AND entity_key IN (SELECT CAST(id AS TEXT) FROM PartOperations WHERE part_no IN (SELECT value FROM json_each(?)))) "
            "OR (kind='template_external_group' AND entity_key IN (SELECT group_id FROM ExternalGroups WHERE part_no IN (SELECT value FROM json_each(?))))) ORDER BY ref",
            (encoded_codes, encoded_codes),
        )
        for row in templates:
            snapshots[owners[(row["kind"], row["entity_key"])]]["template_identities"].append(row)
        return {"identities": identities, "parts": snapshots}
