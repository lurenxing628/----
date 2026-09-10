"""Read explicit skill facts without changing equipment authorization semantics."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from .base_repo import BaseRepository


class OperatorQualificationRepository(BaseRepository):
    def read_skill_facts(self, operator_ids: Sequence[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        profiles: List[Dict[str, Any]] = []
        skills: List[Dict[str, Any]] = []
        ids = sorted(set(operator_ids))
        # Even an empty candidate set must not disguise a missing qualification table.
        for offset in range(0, max(len(ids), 1), 400):
            chunk = ids[offset:offset + 400]
            marks = ",".join("?" for _ in chunk) or "NULL"
            profiles.extend(self.fetchall(f"""
                SELECT o.operator_id, p.operator_id AS profile_operator_id, p.skills_declared
                FROM Operators AS o
                LEFT JOIN WorkbenchOperatorProfiles AS p ON p.operator_id = o.operator_id
                WHERE o.operator_id IN ({marks})
            """, chunk))
            skills.extend(self.fetchall(f"""
                SELECT s.operator_id, s.op_type_id, t.category
                FROM OperatorSkill AS s
                LEFT JOIN OpTypes AS t ON t.op_type_id = s.op_type_id
                WHERE s.operator_id IN ({marks})
            """, chunk))
        return profiles, skills
