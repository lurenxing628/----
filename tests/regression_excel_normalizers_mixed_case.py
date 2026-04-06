import os
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def assert_raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    except Exception as e:
        raise AssertionError(f"期望抛 {exc_type.__name__}，实际抛 {type(e).__name__}: {e}") from e
    raise AssertionError(f"期望抛 {exc_type.__name__}，但未抛异常")


def main():
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.errors import ValidationError
    from core.services.common.excel_validators import (
        _normalize_batch_priority as core_batch_priority,
    )
    from core.services.common.excel_validators import (
        _normalize_operator_calendar_day_type as core_op_day_type,
    )
    from core.services.common.excel_validators import (
        _normalize_ready_status as core_ready_status,
    )
    from core.services.common.excel_validators import (
        _normalize_yesno as core_yesno,
    )
    from core.services.personnel.operator_machine_normalizers import (
        normalize_skill_level_optional as om_skill_optional,
    )
    from core.services.personnel.operator_machine_normalizers import (
        normalize_skill_level_stored as om_skill_stored,
    )
    from core.services.personnel.operator_machine_normalizers import (
        normalize_yes_no_optional as om_yes_no_optional,
    )
    from core.services.personnel.operator_machine_normalizers import (
        normalize_yes_no_stored as om_yes_no_stored,
    )
    from core.services.scheduler.calendar_admin import CalendarAdmin
    from web.routes.normalizers import (
        _normalize_batch_priority as route_batch_priority,
    )
    from web.routes.normalizers import (
        _normalize_day_type as route_day_type,
    )
    from web.routes.normalizers import (
        _normalize_operator_calendar_day_type as route_op_day_type,
    )
    from web.routes.normalizers import (
        _normalize_ready_status as route_ready_status,
    )
    from web.routes.normalizers import (
        _normalize_yesno as route_yesno,
    )

    # -------------------------
    # core/services/common/excel_validators.py
    # -------------------------
    for raw, expected in [
        ("Normal", "normal"),
        ("URGENT", "urgent"),
        ("cRiTiCaL", "critical"),
        ("普通", "normal"),
        ("急件", "urgent"),
        ("特急", "critical"),
        (None, "normal"),
        ("", "normal"),
        ("  ", "normal"),
    ]:
        got = core_batch_priority(raw)
        assert got == expected, f"core_batch_priority({raw!r}) 期望 {expected!r}，实际 {got!r}"

    # 未知值保持原样（用于上层 not in(...) 校验报错时展示用户输入）
    assert core_batch_priority("MiXeD_Unknown") == "MiXeD_Unknown"

    for raw, expected in [
        ("Yes", "yes"),
        ("NO", "no"),
        ("Partial", "partial"),
        ("齐套", "yes"),
        ("未齐套", "no"),
        ("部分齐套", "partial"),
        ("是", "yes"),
        ("否", "no"),
        (None, "yes"),
        ("", "yes"),
    ]:
        got = core_ready_status(raw)
        assert got == expected, f"core_ready_status({raw!r}) 期望 {expected!r}，实际 {got!r}"

    assert core_ready_status("Maybe") == "Maybe"

    for raw, expected in [
        ("Workday", "workday"),
        ("WEEKEND", "holiday"),  # weekend 统一为 holiday
        ("Holiday", "holiday"),
        ("工作日", "workday"),
        ("周末", "holiday"),
        ("节假日", "holiday"),
        ("假期", "holiday"),
        (None, "workday"),
        ("", "workday"),
    ]:
        got = core_op_day_type(raw)
        assert got == expected, f"core_op_day_type({raw!r}) 期望 {expected!r}，实际 {got!r}"

    assert core_op_day_type("WorkDayX") == "WorkDayX"

    for raw, expected in [
        ("Yes", "yes"),
        ("No", "no"),
        ("YES", "yes"),
        ("no", "no"),
        ("  Yes  ", "yes"),
        ("  n  ", "no"),
        ("是", "yes"),
        ("否", "no"),
        (None, "yes"),
        ("", "yes"),
    ]:
        got = core_yesno(raw)
        assert got == expected, f"core_yesno({raw!r}) 期望 {expected!r}，实际 {got!r}"

    assert core_yesno("maybe") == "maybe"

    # -------------------------
    # web/routes/scheduler_utils.py
    # -------------------------
    assert route_batch_priority("Normal") == "normal"
    assert route_ready_status("Partial") == "partial"
    assert route_day_type("Workday") == "workday"
    assert route_day_type("Weekend") == "holiday"
    assert route_yesno("Yes") == "yes"
    assert route_yesno("NO") == "no"
    assert route_yesno("Maybe") == "Maybe"

    # -------------------------
    # web/routes/personnel_bp.py
    # -------------------------
    assert route_op_day_type("Workday") == "workday"
    assert route_op_day_type("Weekend") == "holiday"
    assert route_yesno("Yes") == "yes"
    assert route_yesno("NO") == "no"

    # -------------------------
    # core/services/scheduler/calendar_admin.py (静态方法)
    # -------------------------
    assert CalendarAdmin._validate_day_type(None) == "workday"
    assert CalendarAdmin._validate_day_type("Workday") == "workday"
    assert CalendarAdmin._validate_day_type("Weekend") == "holiday"
    assert CalendarAdmin._validate_day_type("HOLIDAY") == "holiday"
    assert_raises(ValidationError, CalendarAdmin._validate_day_type, "bad_day_type")
    # 中文映射（与 _normalize_yesno 对齐）
    assert CalendarAdmin._validate_day_type("工作日") == "workday"
    assert CalendarAdmin._validate_day_type("周末") == "holiday"
    assert CalendarAdmin._validate_day_type("节假日") == "holiday"
    assert CalendarAdmin._validate_day_type("假期") == "holiday"

    assert CalendarAdmin._normalize_yesno(None, field="允许普通件") == "yes"
    assert CalendarAdmin._normalize_yesno("Yes", field="允许普通件") == "yes"
    assert CalendarAdmin._normalize_yesno("NO", field="允许普通件") == "no"
    assert CalendarAdmin._normalize_yesno("是", field="允许普通件") == "yes"
    assert CalendarAdmin._normalize_yesno("否", field="允许普通件") == "no"
    assert_raises(ValidationError, CalendarAdmin._normalize_yesno, "maybe", field="允许普通件")

    # -------------------------
    # core/services/common/enum_normalizers.py + Excel 链路新增点
    # -------------------------
    from core.services.common.enum_normalizers import (
        normalize_machine_status,
        normalize_op_type_category,
        normalize_operator_status,
        normalize_supplier_status,
    )

    assert normalize_machine_status(None) == ""
    assert normalize_machine_status("Active") == "active"
    assert normalize_machine_status("INACTIVE") == "inactive"
    assert normalize_machine_status("Maintain") == "maintain"
    assert normalize_machine_status("可用") == "active"
    assert normalize_machine_status("维修中") == "maintain"
    assert normalize_machine_status("MiXeD_Unknown") == "MiXeD_Unknown"

    assert normalize_supplier_status(None) == "active"
    assert normalize_supplier_status("") == "active"
    assert normalize_supplier_status("Active") == "active"
    assert normalize_supplier_status("INACTIVE") == "inactive"
    assert normalize_supplier_status("启用") == "active"
    assert normalize_supplier_status("停用") == "inactive"
    assert normalize_supplier_status("WeirdStatus") == "WeirdStatus"

    assert normalize_op_type_category(None) == "internal"
    assert normalize_op_type_category("") == "internal"
    assert normalize_op_type_category("Internal") == "internal"
    assert normalize_op_type_category("EXTERNAL") == "external"
    assert normalize_op_type_category("内部") == "internal"
    assert normalize_op_type_category("外") == "external"
    assert normalize_op_type_category("BadCat") == "BadCat"

    assert normalize_operator_status(None) == ""
    assert normalize_operator_status("") == ""
    assert normalize_operator_status("Active") == "active"
    assert normalize_operator_status("INACTIVE") == "inactive"
    assert normalize_operator_status("BadStatus") == "BadStatus"

    # route/service 侧 delegate（确保导入链路一致）
    from core.services.equipment.machine_excel_import_service import MachineExcelImportService
    from core.services.personnel.operator_excel_import_service import OperatorExcelImportService
    from core.services.process.op_type_excel_import_service import OpTypeExcelImportService  # noqa: F401
    from core.services.process.supplier_excel_import_service import SupplierExcelImportService
    from web.routes.equipment_excel_machines import (
        _normalize_machine_status_for_excel as route_machine_status,
    )
    from web.routes.equipment_excel_machines import (
        _validate_machine_excel_row as route_machine_row,
    )
    from web.routes.excel_demo import _validate_operator_row as demo_operator_row
    from web.routes.personnel_excel_operators import _validate_operator_excel_row as route_operator_row
    from web.routes.process_excel_op_types import _normalize_op_type_category as route_op_type_cat
    from web.routes.process_excel_suppliers import _normalize_supplier_status as route_supplier_status

    assert route_machine_status("Active") == "active"
    assert MachineExcelImportService._normalize_machine_status_for_excel("Maintain") == "maintain"
    row = {"设备编号": "M001", "设备名称": "设备A", "状态": "Active"}
    assert route_machine_row(row) is None
    assert row["状态"] == "active"

    assert route_supplier_status("INACTIVE") == "inactive"
    assert SupplierExcelImportService._normalize_supplier_status_for_excel("Active") == "active"

    assert route_op_type_cat("Internal") == "internal"

    op_row = {"工号": "OP001", "姓名": "张三", "状态": "Active"}
    assert route_operator_row(op_row) is None
    assert op_row["状态"] == "active"
    assert OperatorExcelImportService  # import smoke

    demo_row = {"工号": "OP002", "姓名": "李四", "状态": "INACTIVE"}
    assert demo_operator_row(demo_row) is None
    assert demo_row["状态"] == "inactive"

    # -------------------------
    # core/services/personnel/operator_machine_normalizers.py
    # -------------------------
    for raw, expected in [
        (None, None),
        ("", None),
        ("  ", None),
        ("beginner", "beginner"),
        ("low", "beginner"),
        ("初级", "beginner"),
        ("新手", "beginner"),
        ("normal", "normal"),
        ("普通", "normal"),
        ("一般", "normal"),
        ("中级", "normal"),
        ("expert", "expert"),
        ("high", "expert"),
        ("skilled", "expert"),
        ("熟练", "expert"),
        ("高级", "expert"),
        ("专家", "expert"),
    ]:
        got = om_skill_optional(raw)
        assert got == expected, f"om_skill_optional({raw!r}) 期望 {expected!r}，实际 {got!r}"

    assert_raises(ValidationError, om_skill_optional, "unknown_skill")

    for raw, expected in [
        (None, "normal"),
        ("", "normal"),
        ("  ", "normal"),
        ("beginner", "beginner"),
        ("low", "beginner"),
        ("初级", "beginner"),
        ("新手", "beginner"),
        ("normal", "normal"),
        ("普通", "normal"),
        ("一般", "normal"),
        ("中级", "normal"),
        ("expert", "expert"),
        ("high", "expert"),
        ("skilled", "expert"),
        ("熟练", "expert"),
        ("高级", "expert"),
        ("专家", "expert"),
        ("unknown_skill", "normal"),
    ]:
        got = om_skill_stored(raw)
        assert got == expected, f"om_skill_stored({raw!r}) 期望 {expected!r}，实际 {got!r}"

    for raw, expected in [
        (None, None),
        ("", None),
        ("  ", None),
        ("yes", "yes"),
        ("Yes", "yes"),
        ("YES", "yes"),
        ("y", "yes"),
        ("Y", "yes"),
        ("true", "yes"),
        ("True", "yes"),
        ("1", "yes"),
        ("on", "yes"),
        ("ON", "yes"),
        ("是", "yes"),
        ("主操", "yes"),
        ("主", "yes"),
        ("no", "no"),
        ("No", "no"),
        ("NO", "no"),
        ("n", "no"),
        ("N", "no"),
        ("false", "no"),
        ("False", "no"),
        ("0", "no"),
        ("off", "no"),
        ("OFF", "no"),
        ("否", "no"),
        ("非主操", "no"),
        ("非主", "no"),
    ]:
        got = om_yes_no_optional(raw, field="主操设备")
        assert got == expected, f"om_yes_no_optional({raw!r}) 期望 {expected!r}，实际 {got!r}"

    assert_raises(ValidationError, om_yes_no_optional, "maybe", field="主操设备")

    for raw, expected in [
        (None, "no"),
        ("", "no"),
        ("  ", "no"),
        ("yes", "yes"),
        ("Yes", "yes"),
        ("YES", "yes"),
        ("y", "yes"),
        ("Y", "yes"),
        ("true", "yes"),
        ("True", "yes"),
        ("1", "yes"),
        ("on", "yes"),
        ("ON", "yes"),
        ("是", "yes"),
        ("主操", "yes"),
        ("主", "yes"),
        ("no", "no"),
        ("No", "no"),
        ("NO", "no"),
        ("n", "no"),
        ("N", "no"),
        ("false", "no"),
        ("False", "no"),
        ("0", "no"),
        ("off", "no"),
        ("OFF", "no"),
        ("否", "no"),
        ("非主操", "no"),
        ("非主", "no"),
        ("maybe", "no"),
        ("主操设备", "no"),
    ]:
        got = om_yes_no_stored(raw)
        assert got == expected, f"om_yes_no_stored({raw!r}) 期望 {expected!r}，实际 {got!r}"

    print("OK")


if __name__ == "__main__":
    main()

