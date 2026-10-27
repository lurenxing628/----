"""Per-operation skill filtering when a machine supports several work types."""


def qualified_operators(pool, candidates, op_type_id):
    if pool is None or "operator_skills" not in pool:
        return candidates if isinstance(candidates, list) else list(candidates)
    skills = pool["operator_skills"]
    return [oid for oid in candidates if skills[oid] is None or op_type_id in skills[oid]]
