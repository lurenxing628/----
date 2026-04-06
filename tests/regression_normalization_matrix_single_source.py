import os
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import core.services.common.normalization_matrix as matrix
    import web.routes.equipment_pages as equipment_pages
    import web.routes.personnel_pages as personnel_pages
    from core.models.enums import SkillLevel
    from core.services.common.enum_normalizers import normalize_skill_level, skill_rank
    from core.services.common.excel_validators import (
        _normalize_batch_priority as excel_batch_priority,
    )
    from core.services.common.excel_validators import (
        _normalize_operator_calendar_day_type as excel_day_type,
    )
    from core.services.common.excel_validators import (
        _normalize_ready_status as excel_ready_status,
    )
    from core.services.common.excel_validators import (
        _normalize_yesno as excel_yes_no,
    )
    from core.services.personnel.operator_machine_normalizers import (
        normalize_skill_level_optional,
        normalize_yes_no_optional,
    )
    from web.routes.normalizers import (
        _normalize_batch_priority as route_batch_priority,
    )
    from web.routes.normalizers import (
        _normalize_day_type as route_day_type,
    )
    from web.routes.normalizers import (
        _normalize_ready_status as route_ready_status,
    )
    from web.routes.normalizers import (
        _normalize_yesno as route_yes_no,
    )

    if personnel_pages.skill_level_options is not matrix.skill_level_options:
        raise RuntimeError("人员详情页未直接复用 normalization_matrix.skill_level_options")
    if equipment_pages.skill_level_options is not matrix.skill_level_options:
        raise RuntimeError("设备详情页未直接复用 normalization_matrix.skill_level_options")

    expected_options = [
        (SkillLevel.BEGINNER.value, "初级"),
        (SkillLevel.NORMAL.value, "普通"),
        (SkillLevel.EXPERT.value, "熟练"),
    ]
    if list(matrix.skill_level_options()) != expected_options:
        raise RuntimeError(f"技能等级选项口径异常：{list(matrix.skill_level_options())!r}")
    if list(matrix.iter_skill_level_values()) != [SkillLevel.BEGINNER.value, SkillLevel.NORMAL.value, SkillLevel.EXPERT.value]:
        raise RuntimeError(f"技能等级 canonical 值域异常：{list(matrix.iter_skill_level_values())!r}")

    for raw, expected in (("普通", "normal"), ("urgent", "urgent"), ("特急", "critical")):
        if matrix.normalize_batch_priority_value(raw) != expected:
            raise RuntimeError(f"归一化矩阵批次优先级异常：raw={raw!r}")
        if route_batch_priority(raw) != expected:
            raise RuntimeError(f"路由批次优先级未对齐矩阵：raw={raw!r}")
        if excel_batch_priority(raw) != expected:
            raise RuntimeError(f"校验器批次优先级未对齐矩阵：raw={raw!r}")

    for raw, expected in (("齐套", "yes"), ("partial", "partial"), ("否", "no")):
        if matrix.normalize_ready_status_value(raw) != expected:
            raise RuntimeError(f"归一化矩阵齐套状态异常：raw={raw!r}")
        if route_ready_status(raw) != expected:
            raise RuntimeError(f"路由齐套状态未对齐矩阵：raw={raw!r}")
        if excel_ready_status(raw) != expected:
            raise RuntimeError(f"校验器齐套状态未对齐矩阵：raw={raw!r}")

    for raw, expected in (("工作日", "workday"), ("weekend", "holiday"), ("节假日", "holiday")):
        if matrix.normalize_calendar_day_type_value(raw) != expected:
            raise RuntimeError(f"归一化矩阵日历类型异常：raw={raw!r}")
        if route_day_type(raw) != expected:
            raise RuntimeError(f"路由日历类型未对齐矩阵：raw={raw!r}")
        if excel_day_type(raw) != expected:
            raise RuntimeError(f"校验器日历类型未对齐矩阵：raw={raw!r}")

    for raw, expected in ((None, "yes"), ("true", "yes"), ("0", "no"), ("是", "yes"), ("否", "no")):
        if matrix.normalize_yes_no_narrow_value(raw) != expected:
            raise RuntimeError(f"归一化矩阵 yes/no 异常：raw={raw!r}")
        if route_yes_no(raw) != expected:
            raise RuntimeError(f"路由 yes/no 未对齐矩阵：raw={raw!r}")
        if excel_yes_no(raw) != expected:
            raise RuntimeError(f"校验器 yes/no 未对齐矩阵：raw={raw!r}")

    for raw, expected in (("beginner", "beginner"), ("普通", "normal"), ("熟练", "expert"), ("skilled", "expert")):
        got = matrix.normalize_skill_level_value(raw, default="normal", allow_none=False, unknown_policy="raise")
        if got != expected:
            raise RuntimeError(f"归一化矩阵技能等级异常：raw={raw!r} got={got!r} expected={expected!r}")
        if normalize_skill_level(raw, default="normal", allow_none=False) != expected:
            raise RuntimeError(f"enum_normalizers.normalize_skill_level 未对齐矩阵：raw={raw!r}")

    if skill_rank("高级") != matrix.skill_level_rank("高级"):
        raise RuntimeError("skill_rank 未对齐 normalization_matrix.skill_level_rank")
    if normalize_skill_level_optional("熟练") != "expert":
        raise RuntimeError("人员设备关联技能等级归一化未对齐矩阵")
    if normalize_yes_no_optional("主操", field="主操设备") != "yes":
        raise RuntimeError("人员设备关联主操设备归一化未对齐矩阵")
    if normalize_yes_no_optional("非主操", field="主操设备") != "no":
        raise RuntimeError("人员设备关联主操设备否值归一化未对齐矩阵")

    print("OK")


if __name__ == "__main__":
    main()
