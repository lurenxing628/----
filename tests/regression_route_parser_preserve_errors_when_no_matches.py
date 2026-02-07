import os
import sys
from dataclasses import dataclass
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

    parser = RouteParser(op_types_repo=_StubOpTypesRepo(op_types=[]), suppliers_repo=_StubSuppliersRepo(), logger=None)
    result = parser.parse("ABC5", part_no="P_ERRS")

    assert result.status == ParseStatus.FAILED.value or result.status == ParseStatus.FAILED, f"解析状态异常：{result.status!r}"
    errs = list(result.errors or [])

    assert any("必须以工序号开头" in e for e in errs), f"缺少“必须以工序号开头”错误：{errs!r}"
    assert any("尾部工序号 5 缺少工种名" in e for e in errs), f"缺少“尾部工序号 5 缺少工种名”错误：{errs!r}"
    assert any("无法识别工艺路线格式" in e for e in errs), f"缺少“无法识别工艺路线格式”通用错误：{errs!r}"

    print("OK")


if __name__ == "__main__":
    main()

