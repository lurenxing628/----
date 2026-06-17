"""回归测试：priority_constants 优先级权重契约——normalize_priority 把 None/空白/未知归一为 normal、大小写不敏感（如 Urgent→urgent），priority_weight_scaled 与 PRIORITY_WEIGHT×100 一致、critical>urgent>normal 严格递减，且 scale 参数按比例生效（如 Urgent,scale=10→20）。"""


def test_ortools_priority_weight_contract() -> None:

    from core.algorithms.priority_constants import PRIORITY_WEIGHT, normalize_priority, priority_weight_scaled

    cases = [
        (None, "normal"),
        ("", "normal"),
        ("   ", "normal"),
        ("Urgent", "urgent"),
        ("critical", "critical"),
        ("unknown", "normal"),
    ]

    for raw, expected_priority in cases:
        pr = normalize_priority(raw)
        assert pr == expected_priority, f"priority 归一化异常：raw={raw!r}, actual={pr!r}, expected={expected_priority!r}"
        expected_scaled = int(round(float(PRIORITY_WEIGHT[pr]) * 100))
        actual_scaled = priority_weight_scaled(raw)
        assert actual_scaled == expected_scaled, (
            f"priority_weight_scaled 与 PRIORITY_WEIGHT 不一致：raw={raw!r}, "
            f"actual={actual_scaled}, expected={expected_scaled}"
        )

    assert priority_weight_scaled("critical") > priority_weight_scaled("urgent") > priority_weight_scaled("normal"), (
        "priority_weight_scaled 排序异常：critical/urgent/normal 应严格递减"
    )
    assert priority_weight_scaled("Urgent", scale=10) == 20, "scale 参数未按预期生效"
