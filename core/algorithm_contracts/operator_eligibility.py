"""Per-operation skill filtering when a machine supports several work types."""

from collections.abc import Mapping

from core.errors import ValidationError


def qualified_operators(pool, candidates, op_type_id):
    if pool is None or "operator_skills" not in pool:
        return list(candidates)
    skills = pool["operator_skills"]
    if not isinstance(skills, Mapping):
        raise ValidationError("排产资源池的人员技能资料无效。", field="operator_qualification")
    result = []
    for operator_id in candidates:
        if operator_id not in skills:
            raise ValidationError("排产资源池缺少候选人员的技能资料。", field="operator_qualification")
        types = skills[operator_id]
        if types is not None and (not isinstance(types, (list, tuple, set, frozenset))
                                  or any(not isinstance(value, str) for value in types)):
            raise ValidationError("排产资源池的人员技能资料无效。", field="operator_qualification")
        if types is None or op_type_id in types:
            result.append(operator_id)
    return result
