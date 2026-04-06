from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import ResourceTeam

from .base_repo import BaseRepository


class ResourceTeamRepository(BaseRepository):
    def get(self, team_id: str) -> Optional[ResourceTeam]:
        row = self.fetchone(
            "SELECT team_id, name, status, remark, created_at, updated_at FROM ResourceTeams WHERE team_id = ?",
            (team_id,),
        )
        return ResourceTeam.from_row(row) if row else None

    def get_by_name(self, name: str) -> Optional[ResourceTeam]:
        row = self.fetchone(
            "SELECT team_id, name, status, remark, created_at, updated_at FROM ResourceTeams WHERE name = ?",
            (name,),
        )
        return ResourceTeam.from_row(row) if row else None

    def list(self, status: Optional[str] = None) -> List[ResourceTeam]:
        if status:
            rows = self.fetchall(
                "SELECT team_id, name, status, remark, created_at, updated_at FROM ResourceTeams WHERE status = ? ORDER BY team_id",
                (status,),
            )
        else:
            rows = self.fetchall(
                "SELECT team_id, name, status, remark, created_at, updated_at FROM ResourceTeams ORDER BY team_id"
            )
        return [ResourceTeam.from_row(r) for r in rows]

    def list_with_counts(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = """
        SELECT
            rt.team_id,
            rt.name,
            rt.status,
            rt.remark,
            rt.created_at,
            rt.updated_at,
            COALESCE(op.operator_count, 0) AS operator_count,
            COALESCE(mc.machine_count, 0) AS machine_count
        FROM ResourceTeams rt
        LEFT JOIN (
            SELECT team_id, COUNT(*) AS operator_count
            FROM Operators
            WHERE team_id IS NOT NULL AND TRIM(team_id) <> ''
            GROUP BY team_id
        ) op ON op.team_id = rt.team_id
        LEFT JOIN (
            SELECT team_id, COUNT(*) AS machine_count
            FROM Machines
            WHERE team_id IS NOT NULL AND TRIM(team_id) <> ''
            GROUP BY team_id
        ) mc ON mc.team_id = rt.team_id
        """
        params: List[Any] = []
        if status:
            sql += " WHERE rt.status = ?"
            params.append(status)
        sql += " ORDER BY rt.team_id"
        return self.fetchall(sql, tuple(params))

    def exists(self, team_id: str) -> bool:
        return bool(self.fetchvalue("SELECT 1 FROM ResourceTeams WHERE team_id = ? LIMIT 1", (team_id,)))

    def create(self, team: Union[ResourceTeam, Dict[str, Any]]) -> ResourceTeam:
        item = team if isinstance(team, ResourceTeam) else ResourceTeam.from_row(team)
        self.execute(
            "INSERT INTO ResourceTeams (team_id, name, status, remark) VALUES (?, ?, ?, ?)",
            (item.team_id, item.name, item.status, item.remark),
        )
        return item

    def update(self, team_id: str, updates: Dict[str, Any]) -> None:
        if not updates:
            return

        allowed = {"name", "status", "remark"}
        set_parts: List[str] = []
        params: List[Any] = []

        for key in ("name", "status", "remark"):
            if key in allowed and key in updates:
                set_parts.append(f"{key} = ?")
                params.append(updates.get(key))

        if not set_parts:
            return

        set_parts.append("updated_at = CURRENT_TIMESTAMP")
        params.append(team_id)
        sql = f"UPDATE ResourceTeams SET {', '.join(set_parts)} WHERE team_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, team_id: str) -> None:
        self.execute("DELETE FROM ResourceTeams WHERE team_id = ?", (team_id,))

    def count_operator_refs(self, team_id: str) -> int:
        return int(
            self.fetchvalue(
                "SELECT COUNT(*) FROM Operators WHERE team_id IS NOT NULL AND TRIM(team_id) <> '' AND team_id = ?",
                (team_id,),
                default=0,
            )
            or 0
        )

    def count_machine_refs(self, team_id: str) -> int:
        return int(
            self.fetchvalue(
                "SELECT COUNT(*) FROM Machines WHERE team_id IS NOT NULL AND TRIM(team_id) <> '' AND team_id = ?",
                (team_id,),
                default=0,
            )
            or 0
        )
