"""Current raw production rows for piece adoption proof; every table is a fixed literal."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_repo import BaseRepository

TEMPLATE_TABLES = ("PartOperations", "ExternalGroups")
PREFLIGHT_TABLES = ("Machines", "Operators", "Suppliers", "OpTypes", "OperatorMachine", "OperatorSkill",
                    "WorkbenchOperatorProfiles", "WorkbenchSupplierOpTypes", "PartOperations", "ExternalGroups", "BatchMaterials")


class WorkbenchPieceAdoptionRepository(BaseRepository):
    def template_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        """Whole PartOperations / ExternalGroups rows for the template cache."""
        return {name: self.fetchall('SELECT * FROM "' + name + '"') for name in TEMPLATE_TABLES}

    def preflight_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        """Whole rows of every table the preflight checks read."""
        return {name: self.fetchall('SELECT * FROM "' + name + '"') for name in PREFLIGHT_TABLES}

    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT * FROM Batches WHERE batch_id=?", (batch_id,))

    def active_batch_refs(self, batch_id: str) -> List[Any]:
        """Every active permanent ref of one batch (exactly one is expected)."""
        return [row[0] for row in self.execute(
            "SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND active=1 AND entity_key=?", (batch_id,))]

    def list_batch_operations(self, batch_id: str) -> List[Dict[str, Any]]:
        return self.fetchall("SELECT * FROM BatchOperations WHERE batch_id=? ORDER BY id", (batch_id,))

    def get_schedule_row(self, schedule_id: Any) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT * FROM Schedule WHERE id=?", (schedule_id,))
