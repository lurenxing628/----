from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

from core.models.part import Part

from .base_repo import BaseRepository

_PROCESS_READINESS_SQL = """
WITH part_flags AS (
    SELECT
        p.workflow_origin AS origin,
        (p.route_confirmed_at IS NOT NULL) AS r_conf,
        (p.source_confirmed_at IS NOT NULL) AS s_conf,
        (p.hours_confirmed_at IS NOT NULL) AS h_conf,
        (p.workflow_origin = 'legacy' AND EXISTS (
            SELECT 1 FROM PartOperations o
            WHERE o.part_no = p.part_no AND o.status = 'active'
        )) AS legacy_present
    FROM Parts p
)
SELECT
    COALESCE(SUM(CASE WHEN NOT h_conf AND NOT s_conf AND NOT (r_conf OR legacy_present) THEN 1 ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN NOT h_conf AND NOT s_conf AND (r_conf OR legacy_present) THEN 1 ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN NOT h_conf AND s_conf THEN 1 ELSE 0 END), 0),
    COALESCE(SUM(h_conf), 0),
    COALESCE(SUM(origin = 'legacy'), 0),
    COALESCE(SUM(origin = 'managed'), 0),
    COALESCE(SUM(legacy_present), 0),
    COALESCE(SUM(r_conf), 0),
    COALESCE(SUM(s_conf), 0),
    COALESCE(SUM(h_conf), 0)
FROM part_flags
"""


class PartRepository(BaseRepository):
    """零件仓库（Parts）。"""

    def _dict_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        if row is None:
            return None
        names = [column[0] for column in cursor.description]
        return dict(zip(names, row))

    def exists(self, part_no: str) -> bool:
        """检查指定图号是否已存在。"""
        return self.fetchone("SELECT 1 FROM Parts WHERE part_no = ?", (part_no,)) is not None

    def part_with_ref(self, part_no: str) -> Optional[Dict[str, Any]]:
        return self._dict_one(
            """SELECT p.*, r.ref FROM Parts p
               LEFT JOIN WorkbenchEntityRefs r
                 ON r.kind='part' AND r.active=1 AND r.entity_key=p.part_no
               WHERE p.part_no=?""",
            (part_no,),
        )

    def create(self, part: Part) -> None:
        self.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark, workflow_origin) "
            "VALUES (?, ?, ?, ?, ?, 'managed')",
            (part.part_no, part.part_name, part.route_raw, part.route_parsed, part.remark),
        )

    def update(self, part_no: str, updates: Dict[str, Any]) -> None:
        set_parts = [f"{k} = ?" for k in updates] + ["updated_at = CURRENT_TIMESTAMP"]
        params = [*updates.values(), part_no]
        sql = f"UPDATE Parts SET {', '.join(set_parts)} WHERE part_no = ?"
        self.execute(sql, tuple(params))

    def delete(self, part_no: str) -> None:
        self.execute("DELETE FROM Parts WHERE part_no = ?", (part_no,))

    def set_stage_confirmed_at(self, part_no: str, stage: str, stamp: str) -> None:
        if stage == "route":
            self.execute(
                "UPDATE Parts SET workflow_origin='managed', route_confirmed_at=? WHERE part_no=?",
                (stamp, part_no),
            )
        elif stage == "source":
            self.execute("UPDATE Parts SET source_confirmed_at=? WHERE part_no=?", (stamp, part_no))
        elif stage == "hours":
            self.execute("UPDATE Parts SET hours_confirmed_at=? WHERE part_no=?", (stamp, part_no))
        else:
            raise ValueError(f"Unsupported stage: {stage}")

    def reset_confirmations_from(self, part_no: str, stage: str) -> None:
        if stage == "route":
            self.execute(
                """UPDATE Parts
                   SET route_confirmed_at=NULL, source_confirmed_at=NULL, hours_confirmed_at=NULL
                   WHERE part_no=?
                     AND (route_confirmed_at IS NOT NULL
                          OR source_confirmed_at IS NOT NULL
                          OR hours_confirmed_at IS NOT NULL)""",
                (part_no,),
            )
        elif stage == "source":
            self.execute(
                """UPDATE Parts
                   SET source_confirmed_at=NULL, hours_confirmed_at=NULL
                   WHERE part_no=? AND (source_confirmed_at IS NOT NULL OR hours_confirmed_at IS NOT NULL)""",
                (part_no,),
            )
        elif stage == "hours":
            self.execute(
                "UPDATE Parts SET hours_confirmed_at=NULL WHERE part_no=? AND hours_confirmed_at IS NOT NULL",
                (part_no,),
            )
        else:
            raise ValueError(f"Unsupported stage: {stage}")

    def process_readiness_counts(self) -> Tuple[int, ...]:
        row = self.execute(_PROCESS_READINESS_SQL).fetchone()
        return tuple(int(value) for value in row)
