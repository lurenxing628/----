"""回归测试：DeletionValidator 对工序 source 的判定大小写与空白不敏感——INTERNAL/带空格的 EXTERNAL 等混写仍能正确识别内/外部工序，从而 can_delete 拒删内部工序、get_deletion_groups 正确切出首部连续外部组。"""


def test_deletion_validator_source_case_insensitive() -> None:

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
