"""Additional read-only facts for material batch preflight and complete exports."""

from __future__ import annotations

import json

from .base_repo import BaseRepository


class WorkbenchMaterialFileRepository(BaseRepository):
    def capture(self, *, codes=(), refs=()):
        """Capture current facts; identity history is only for new import codes."""
        identities, histories, materials, requirements = {}, {}, {}, {}
        codes = set(codes)
        capture_history = bool(codes)
        if refs:
            for row in self.fetchall(
                "SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs "
                "WHERE ref IN (SELECT value FROM json_each(?))",
                (json.dumps(list(refs)),),
            ):
                identities[row["ref"]] = row
        all_codes = codes | {row["entity_key"] for row in identities.values()
                             if row["kind"] == "material" and row["active"] == 1}
        if all_codes:
            for row in self.fetchall(
                "SELECT m.*,r.ref,r.revision FROM Materials m LEFT JOIN WorkbenchEntityRefs r "
                "ON r.kind='material' AND r.entity_key=m.material_id AND r.active=1 "
                "WHERE m.material_id IN (SELECT value FROM json_each(?)) ORDER BY m.material_id",
                (json.dumps(list(all_codes)),),
            ):
                materials[row["material_id"]] = row
                if row["ref"] is not None and row["ref"] not in identities:
                    identities[row["ref"]] = {"ref": row["ref"], "kind": "material", "entity_key": row["material_id"],
                                              "revision": row["revision"], "active": 1}
            if capture_history:
                missing = [code for code in all_codes if code not in materials]
                if missing:
                    for row in self.fetchall(
                        "SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs WHERE kind='material' "
                        "AND entity_key IN (SELECT value FROM json_each(?)) ORDER BY entity_key,ref",
                        (json.dumps(missing),),
                    ):
                        identities[row["ref"]] = row
                        histories.setdefault(row["entity_key"], []).append(
                            {key: row[key] for key in ("ref", "revision", "active")}
                        )
            existing = [code for code in all_codes if code in materials]
            if existing:
                for row in self.fetchall(
                    "SELECT * FROM BatchMaterials WHERE material_id IN (SELECT value FROM json_each(?)) ORDER BY id",
                    (json.dumps(existing),),
                ):
                    requirements.setdefault(row["material_id"], []).append(row)
        for code, row in materials.items():
            row["requirement_count"] = len(requirements.get(code, ()))
        return {"materials": materials, "identities": identities, "identity_history": histories, "requirements": requirements}
