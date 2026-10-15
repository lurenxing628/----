"""Additional read-only facts for material batch preflight and complete exports."""

from __future__ import annotations

from .base_repo import BaseRepository


class WorkbenchMaterialFileRepository(BaseRepository):
    def capture(self, *, codes=(), refs=()):
        """Read selected material rows, identities and requirements in bounded chunks."""
        identities, histories, materials, requirements = {}, {}, {}, {}
        codes = set(codes)
        refs = list(dict.fromkeys(refs))
        for start in range(0, len(refs), 400):
            chunk = refs[start:start + 400]
            marks = ",".join("?" for _ in chunk)
            for row in self.fetchall("SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs WHERE ref IN (" + marks + ")", chunk):
                identities[row["ref"]] = row
                if row["kind"] == "material":
                    codes.add(row["entity_key"])
        codes = sorted(codes)
        for start in range(0, len(codes), 400):
            chunk = codes[start:start + 400]
            marks = ",".join("?" for _ in chunk)
            for row in self.fetchall("SELECT m.*,r.ref,r.revision FROM Materials m LEFT JOIN WorkbenchEntityRefs r "
                                     "ON r.kind='material' AND r.entity_key=m.material_id AND r.active=1 WHERE m.material_id IN (" + marks + ")", chunk):
                materials[row["material_id"]] = row
            for row in self.fetchall("SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs WHERE kind='material' "
                                     "AND entity_key IN (" + marks + ") ORDER BY ref", chunk):
                identities[row["ref"]] = row
                histories.setdefault(row["entity_key"], []).append({key: row[key] for key in ("ref", "revision", "active")})
            for row in self.fetchall("SELECT * FROM BatchMaterials WHERE material_id IN (" + marks + ") ORDER BY id", chunk):
                requirements.setdefault(row["material_id"], []).append(row)
        for code, row in materials.items():
            row["requirement_count"] = len(requirements.get(code, ()))
        return {"materials": materials, "identities": identities, "identity_history": histories, "requirements": requirements}
