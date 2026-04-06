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

    print("OK")


if __name__ == "__main__":
    main()
