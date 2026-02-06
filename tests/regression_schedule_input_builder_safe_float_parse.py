import os
import sys
from types import SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


class _StubSvc:
    def __init__(self):
        self.called = False

    def _get_template_and_group_for_op(self, op):
        self.called = True
        return None, None


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.scheduler.schedule_input_builder import build_algo_operations

    svc = _StubSvc()

    internal = SimpleNamespace(
        id=1,
        op_code="OP_INT_01",
        batch_id="B001",
        seq=1,
        op_type_id="OT01",
        op_type_name="车削",
        source="internal",
        machine_id="M001",
        operator_id="O001",
        supplier_id=None,
        setup_hours="   ",  # 空白字符串：应回退为 0.0，不应抛异常
        unit_hours="abc",  # 非数字：应回退为 0.0
        ext_days=None,
    )
    external = SimpleNamespace(
        id=2,
        op_code="OP_EXT_01",
        batch_id="B001",
        seq=2,
        op_type_id="OT_EXT",
        op_type_name="外协",
        source="External",  # 大小写混用：仍应识别为 external
        machine_id=None,
        operator_id=None,
        supplier_id="SUP01",
        setup_hours=None,
        unit_hours=None,
        ext_days="  ",  # 空白字符串：应回退为 None（不应抛异常）
    )

    out = build_algo_operations(svc, [internal, external])
    assert len(out) == 2, f"build_algo_operations 输出数量异常：{len(out)}"
    assert svc.called is True, "external 工序应触发 _get_template_and_group_for_op（source 大小写需容错）"

    op0 = out[0]
    op1 = out[1]

    assert float(op0.setup_hours) == 0.0, f"setup_hours 解析异常：{op0.setup_hours!r}"
    assert float(op0.unit_hours) == 0.0, f"unit_hours 解析异常：{op0.unit_hours!r}"
    assert op1.ext_days is None, f"ext_days 解析异常：{op1.ext_days!r}"

    print("OK")


if __name__ == "__main__":
    main()

