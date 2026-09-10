"""Additional read-only facts for material batch preflight and complete exports."""

from __future__ import annotations

from .base_repo import BaseRepository


class WorkbenchMaterialFileRepository(BaseRepository):
    def identity_history(self, business_code):
        return self.fetchall("SELECT ref, revision, active FROM WorkbenchEntityRefs WHERE kind = 'material' AND entity_key = ? ORDER BY ref",
                             (business_code,))

    def raw_material(self, business_code):
        # Include existing columns even if they are absent from the public form.
        return self.fetchone("SELECT * FROM Materials WHERE material_id = ?", (business_code,))

    def requirements(self, business_code):
        return self.fetchall("SELECT * FROM BatchMaterials WHERE material_id = ? ORDER BY id", (business_code,))
