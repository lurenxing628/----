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

    from core.infrastructure.errors import BusinessError, ValidationError
    from core.services.equipment.machine_service import MachineService
    from core.services.personnel.operator_service import OperatorService
    from core.services.process.op_type_service import OpTypeService
    from core.services.process.supplier_service import SupplierService
    from core.services.scheduler.operation_edit_service import _validate_machine_available, _validate_operator_available

    # -------------------------
    # MachineService._normalize_status
    # -------------------------
    assert MachineService._normalize_status("Active") == "active"
    assert MachineService._normalize_status("INACTIVE") == "inactive"
    assert MachineService._normalize_status("Maintain") == "maintain"
    assert MachineService._normalize_status("可用") == "active"
    assert MachineService._normalize_status("维修中") == "maintain"
    assert_raises(ValidationError, MachineService._normalize_status, "bad_status")

    # -------------------------
    # OperatorService._validate_operator_fields
    # -------------------------
    op_svc = OperatorService(conn=None, logger=None, op_logger=None)
    op_id, op_name, op_status, op_team_id = op_svc._validate_operator_fields(
        operator_id="OP1", name="张三", status="Active"
    )
    assert op_id == "OP1"
    assert op_name == "张三"
    assert op_status == "active"
    assert op_team_id is None
    assert_raises(
        ValidationError, op_svc._validate_operator_fields, operator_id="OP1", name="张三", status="bad_status"
    )

    # allow_partial=True：不应把缺失 status 强行默认（避免 update 时误写）
    _id, _name, st, team = op_svc._validate_operator_fields(
        operator_id="OP1", name=None, status=None, allow_partial=True
    )
    assert st is None
    assert team is None

    # -------------------------
    # SupplierService._validate_fields
    # -------------------------
    sup_svc = SupplierService(conn=None, logger=None, op_logger=None)
    sid, sname, sdays, sstatus = sup_svc._validate_fields("S1", "供应商A", 1.0, "Active")
    assert sid == "S1"
    assert sname == "供应商A"
    assert float(sdays) == 1.0
    assert sstatus == "active"
    assert_raises(ValidationError, sup_svc._validate_fields, "S1", "供应商A", 1.0, "bad_status")
    # 默认值保持：create/非 partial 时 status 为空 -> active
    _sid, _sname, _sdays, st2 = sup_svc._validate_fields("S1", "供应商A", 1.0, None)
    assert st2 == "active"
    # allow_partial=True：不默认
    _sid, _sname, _sdays, st3 = sup_svc._validate_fields("S1", None, None, None, allow_partial=True)
    assert st3 is None

    # -------------------------
    # OpTypeService._validate_fields
    # -------------------------
    ot_svc = OpTypeService(conn=None, logger=None, op_logger=None)
    ot_id, ot_name, cat = ot_svc._validate_fields("OT1", "工种A", "Internal")
    assert ot_id == "OT1"
    assert ot_name == "工种A"
    assert cat == "internal"
    assert_raises(ValidationError, ot_svc._validate_fields, "OT1", "工种A", "bad_cat")
    # allow_partial=True：不默认
    _ot_id, _ot_name, cat2 = ot_svc._validate_fields("OT1", None, None, allow_partial=True)
    assert cat2 is None

    # -------------------------
    # operation_edit_service：资源可用性比较（DB 混合大小写容错）
    # -------------------------
    class _Obj:
        def __init__(self, status):
            self.status = status

    class _Repo:
        def __init__(self, obj):
            self._obj = obj

        def get(self, _id):
            return self._obj

    class _Svc:
        def __init__(self, mc_status, op_status):
            self.machine_repo = _Repo(_Obj(mc_status))
            self.operator_repo = _Repo(_Obj(op_status))

    svc_ok = _Svc(mc_status="Active", op_status="ACTIVE")
    _validate_machine_available(svc_ok, "M1")
    _validate_operator_available(svc_ok, "OP1")

    svc_bad_mc = _Svc(mc_status="Maintain", op_status="ACTIVE")
    assert_raises(BusinessError, _validate_machine_available, svc_bad_mc, "M1")

    svc_bad_op = _Svc(mc_status="Active", op_status="Inactive")
    assert_raises(BusinessError, _validate_operator_available, svc_bad_op, "OP1")

    # -------------------------
    # list()：校验后的归一化值必须用于 repo 查询（避免 mixed-case 静默查不到）
    # -------------------------
    class _StubOperatorRepo:
        def __init__(self):
            self.last = ("__unset__", "__unset__")

        def list(self, status: str = None, team_id: str = None):
            self.last = (status, team_id)
            return []

    op_svc.repo = _StubOperatorRepo()
    op_svc.list(status=" Active ")
    assert op_svc.repo.last[0] == "active"
    assert op_svc.repo.last[1] is None
    assert_raises(ValidationError, op_svc.list, status="   ")

    class _StubMachineRepo:
        def __init__(self):
            self.last = ("__unset__", "__unset__", "__unset__", "__unset__")

        def list(self, status: str = None, op_type_id: str = None, category: str = None, team_id: str = None):
            self.last = (status, op_type_id, category, team_id)
            return []

    mc_svc = MachineService(conn=None, logger=None, op_logger=None)
    mc_svc.repo = _StubMachineRepo()
    mc_svc.list(status=" ACTIVE ")
    assert mc_svc.repo.last[0] == "active"
    assert mc_svc.repo.last[3] is None
    assert_raises(ValidationError, mc_svc.list, status="   ")

    class _StubSupplierRepo:
        def __init__(self):
            self.last = ("__unset__", "__unset__")

        def list(self, status: str = None, op_type_id: str = None):
            self.last = (status, op_type_id)
            return []

    sup_svc.repo = _StubSupplierRepo()
    sup_svc.list(status=" Inactive ")
    assert sup_svc.repo.last[0] == "inactive"

    class _StubOpTypeRepo:
        def __init__(self):
            self.last_category = "__unset__"

        def list(self, category: str = None):
            self.last_category = category
            return []

    ot_svc.repo = _StubOpTypeRepo()
    ot_svc.list(category=" Internal ")
    assert ot_svc.repo.last_category == "internal"

    print("OK")


if __name__ == "__main__":
    main()

