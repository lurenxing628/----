"""Read explicit skill facts without changing equipment authorization semantics."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from .base_repo import BaseRepository


class OperatorQualificationRepository(BaseRepository):
    def read_skill_facts(self, operator_ids: Sequence[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        profiles: List[Dict[str, Any]] = []
        skills: List[Dict[str, Any]] = []
        for start in range(0, len(operator_ids), 400):
            chunk = operator_ids[start:start + 400]
            placeholders = ",".join("?" for _ in chunk)
            profiles.extend(self.fetchall(f"""
                SELECT o.operator_id, p.operator_id AS profile_operator_id, p.skills_declared
                FROM Operators AS o
                LEFT JOIN WorkbenchOperatorProfiles AS p ON p.operator_id = o.operator_id
                WHERE o.operator_id IN ({placeholders})
            """, chunk))
            skills.extend(self.fetchall(f"""
                SELECT s.operator_id, s.op_type_id, t.category
                FROM OperatorSkill AS s
                LEFT JOIN OpTypes AS t ON t.op_type_id = s.op_type_id
                WHERE s.operator_id IN ({placeholders})
            """, chunk))
        return profiles, skills
