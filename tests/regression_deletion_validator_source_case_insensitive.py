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

    from core.services.process.deletion_validator import DeletionValidator, Operation, ValidationResult

    dv = DeletionValidator()

    # Case A：source=INTERNAL（大小写混用）时必须被识别为内部工序，禁止删除
    ops = [
        Operation(seq=1, source="INTERNAL", status="ACTIVE"),
        Operation(seq=2, source="external", status="active"),
    ]
    r = dv.can_delete(ops, [1])
    assert r.can_delete is False, f"内部工序不应可删：{r}"
    assert r.result == ValidationResult.DENIED, f"预期 DENIED，实际 {r.result}"

    # Case B：source=EXTERNAL（大小写混用）时仍应被识别为外部工序，用于组判定
    ops2 = [
        Operation(seq=1, source="EXTERNAL", status="active"),
        Operation(seq=2, source=" external ", status="active"),
        Operation(seq=3, source="internal", status="active"),
    ]
    groups = dv.get_deletion_groups(ops2)
    assert groups == [[1, 2]], f"首部连续外部组识别失败：{groups!r}"

    print("OK")


if __name__ == "__main__":
    main()

