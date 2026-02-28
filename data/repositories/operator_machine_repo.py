from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from core.models import OperatorMachine

from .base_repo import BaseRepository


class OperatorMachineRepository(BaseRepository):
    """人员-设备关联仓库（OperatorMachine）。"""

    def get(self, link_id: int) -> Optional[OperatorMachine]:
        row = self.fetchone(
            "SELECT id, operator_id, machine_id, skill_level, is_primary, created_at FROM OperatorMachine WHERE id = ?",
            (link_id,),
        )
        return OperatorMachine.from_row(row) if row else None

    def exists(self, operator_id: str, machine_id: str) -> bool:
        return bool(
            self.fetchvalue(
                "SELECT 1 FROM OperatorMachine WHERE operator_id = ? AND machine_id = ? LIMIT 1",
                (operator_id, machine_id),
            )
        )

    def list_by_operator(self, operator_id: str) -> List[OperatorMachine]:
        rows = self.fetchall(
            "SELECT id, operator_id, machine_id, skill_level, is_primary, created_at FROM OperatorMachine WHERE operator_id = ? ORDER BY id",
            (operator_id,),
        )
        return [OperatorMachine.from_row(r) for r in rows]

    def list_by_machine(self, machine_id: str) -> List[OperatorMachine]:
        rows = self.fetchall(
            "SELECT id, operator_id, machine_id, skill_level, is_primary, created_at FROM OperatorMachine WHERE machine_id = ? ORDER BY id",
            (machine_id,),
        )
        return [OperatorMachine.from_row(r) for r in rows]

    def list_simple_rows(self) -> List[Dict[str, Any]]:
        """
        轻量查询：仅返回 algorithm/页面联动所需字段。
        """
        return self.fetchall("SELECT operator_id, machine_id, skill_level, is_primary FROM OperatorMachine", None)

    def list_with_names_by_machine(self) -> List[Dict[str, Any]]:
        """
        Excel/页面展示用：返回 machine_name/operator_name（按 machine_id, operator_id 排序）。
        """
        return self.fetchall(
            """
            SELECT
              om.machine_id, m.name AS machine_name,
              om.operator_id, o.name AS operator_name,
              om.skill_level, om.is_primary
            FROM OperatorMachine om
            LEFT JOIN Machines m ON m.machine_id = om.machine_id
            LEFT JOIN Operators o ON o.operator_id = om.operator_id
            ORDER BY om.machine_id, om.operator_id
            """
        )

    def list_with_names_by_operator(self) -> List[Dict[str, Any]]:
        """
        Excel/页面展示用：返回 operator_name/machine_name（按 operator_id, machine_id 排序）。
        """
        return self.fetchall(
            """
            SELECT
              om.operator_id, o.name AS operator_name,
              om.machine_id, m.name AS machine_name,
              om.skill_level, om.is_primary
            FROM OperatorMachine om
            LEFT JOIN Operators o ON o.operator_id = om.operator_id
            LEFT JOIN Machines m ON m.machine_id = om.machine_id
            ORDER BY om.operator_id, om.machine_id
            """
        )

    def list_links_with_machine_names(self) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT om.operator_id, om.machine_id, m.name AS machine_name
            FROM OperatorMachine om
            JOIN Machines m ON m.machine_id = om.machine_id
            ORDER BY om.operator_id, om.machine_id
            """
        )

    def list_links_with_operator_info(self) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT om.machine_id, om.operator_id, o.name AS operator_name, o.status AS operator_status
            FROM OperatorMachine om
            LEFT JOIN Operators o ON o.operator_id = om.operator_id
            ORDER BY om.machine_id, om.operator_id
            """
        )

    def list_simple_rows_for_machine_operator_sets(self, machine_ids: Sequence[str], operator_ids: Sequence[str]) -> List[Dict[str, Any]]:
        """
        给“批次详情页的人机联动”使用：限定 machine_id/operator_id 集合，返回 skill_level/is_primary 元信息。
        """
        m_list = [str(x).strip() for x in (machine_ids or []) if str(x).strip()]
        o_list = [str(x).strip() for x in (operator_ids or []) if str(x).strip()]
        if not m_list or not o_list:
            return []
        m_placeholders = ",".join(["?"] * len(m_list))
        o_placeholders = ",".join(["?"] * len(o_list))
        sql = f"""
        SELECT machine_id, operator_id, skill_level, is_primary
        FROM OperatorMachine
        WHERE machine_id IN ({m_placeholders}) AND operator_id IN ({o_placeholders})
        ORDER BY machine_id, operator_id
        """
        return self.fetchall(sql, tuple(m_list + o_list))

    def add(
        self,
        operator_id: str,
        machine_id: str,
        skill_level: str = "normal",
        is_primary: str = "no",
    ) -> OperatorMachine:
        cur = self.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            (operator_id, machine_id, skill_level, is_primary),
        )
        return OperatorMachine(
            id=int(cur.lastrowid) if cur.lastrowid is not None else None,
            operator_id=operator_id,
            machine_id=machine_id,
            skill_level=skill_level,
            is_primary=is_primary,
        )

    def remove(self, operator_id: str, machine_id: str) -> None:
        self.execute(
            "DELETE FROM OperatorMachine WHERE operator_id = ? AND machine_id = ?",
            (operator_id, machine_id),
        )

    def delete(self, link_id: int) -> None:
        self.execute("DELETE FROM OperatorMachine WHERE id = ?", (link_id,))

    def update_fields(self, operator_id: str, machine_id: str, *, skill_level: str, is_primary: str) -> int:
        cur = self.execute(
            """
            UPDATE OperatorMachine
            SET skill_level = ?, is_primary = ?
            WHERE operator_id = ? AND machine_id = ?
            """,
            (skill_level, is_primary, operator_id, machine_id),
        )
        return int(getattr(cur, "rowcount", 0) or 0)

    def clear_primary_for_operator(self, operator_id: str) -> int:
        cur = self.execute("UPDATE OperatorMachine SET is_primary = 'no' WHERE operator_id = ?", (operator_id,))
        return int(getattr(cur, "rowcount", 0) or 0)

