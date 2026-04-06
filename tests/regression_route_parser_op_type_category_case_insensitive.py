import os
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from typing import List


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


@dataclass
class _StubOpTypesRepo:
    op_types: List[object]

    def list(self):
        return list(self.op_types)

    def get(self, op_type_id: str):
        for ot in self.op_types:
            if getattr(ot, "op_type_id", None) == op_type_id:
                return ot
        return None


@dataclass
class _StubSuppliersRepo:
    def list(self):
        return []


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.process.route_parser import ParseStatus, RouteParser

    # 关键：category 为大写/带空格时，仍应被识别为 internal
    ot = SimpleNamespace(op_type_id="OT001", name="数铣", category=" INTERNAL ")
    op_repo = _StubOpTypesRepo(op_types=[ot])
    sup_repo = _StubSuppliersRepo()

    parser = RouteParser(op_types_repo=op_repo, suppliers_repo=sup_repo, logger=None)
    result = parser.parse("5数铣", part_no="P001")

    assert result.status == ParseStatus.SUCCESS.value or result.status == ParseStatus.SUCCESS, f"解析状态异常：{result.status!r}"
    assert result.operations and result.operations[0].source == "internal", f"category 大小写容错失败：{result.operations!r}"
    assert result.stats.get("internal") == 1 and result.stats.get("external") == 0, f"统计异常：{result.stats!r}"

    print("OK")


if __name__ == "__main__":
    main()

