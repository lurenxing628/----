"""Additional read-only facts for material batch preflight and complete exports."""

from __future__ import annotations

from .base_repo import BaseRepository


class WorkbenchMaterialFileRepository(BaseRepository):
    def capture(self, *, codes=(), refs=()):
        """Capture current facts in chunks; identity history is only for new import codes."""
        identities, histories, materials, requirements = {}, {}, {}, {}
        codes = set(codes)
        capture_history = bool(codes)
        refs = list(dict.fromkeys(refs))
        for start in range(0, len(refs), 400):
            chunk = refs[start:start + 400]
            marks = ",".join("?" for _ in chunk)
            for row in self.fetchall("SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs WHERE ref IN (" + marks + ")", chunk):
                identities[row["ref"]] = row
        codes = sorted(codes | {row["entity_key"] for row in identities.values()
                                if row["kind"] == "material" and row["active"] == 1})
        for start in range(0, len(codes), 400):
            chunk = codes[start:start + 400]
            marks = ",".join("?" for _ in chunk)
            for row in self.fetchall("SELECT m.*,r.ref,r.revision FROM Materials m LEFT JOIN WorkbenchEntityRefs r "
                                     "ON r.kind='material' AND r.entity_key=m.material_id AND r.active=1 WHERE m.material_id IN (" + marks + ")", chunk):
                materials[row["material_id"]] = row
                if row["ref"] is not None and row["ref"] not in identities:
                    identities[row["ref"]] = {"ref": row["ref"], "kind": "material", "entity_key": row["material_id"],
                                              "revision": row["revision"], "active": 1}
            if capture_history:
                missing = [code for code in chunk if code not in materials]
                if missing:
                    missing_marks = ",".join("?" for _ in missing)
                    for row in self.fetchall("SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs WHERE kind='material' "
                                             "AND entity_key IN (" + missing_marks + ") ORDER BY ref", missing):
                        identities[row["ref"]] = row
                        histories.setdefault(row["entity_key"], []).append({key: row[key] for key in ("ref", "revision", "active")})
            existing_chunk = [code for code in chunk if code in materials]
            if existing_chunk:
                existing_marks = ",".join("?" for _ in existing_chunk)
                for row in self.fetchall("SELECT * FROM BatchMaterials WHERE material_id IN (" + existing_marks + ") ORDER BY id", existing_chunk):
                    requirements.setdefault(row["material_id"], []).append(row)
        for code, row in materials.items():
            row["requirement_count"] = len(requirements.get(code, ()))
        return {"materials": materials, "identities": identities, "identity_history": histories, "requirements": requirements}
