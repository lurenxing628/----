import os
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main():
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.common.excel_validators import _normalize_yesno

    cases = [
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
    ]

    for raw, expected in cases:
        got = _normalize_yesno(raw)
        assert got == expected, f"_normalize_yesno({raw!r}) 期望 {expected!r}，实际 {got!r}"

    # 未知值仍保持原样（交由上层校验）
    assert _normalize_yesno("maybe") == "maybe"

    # 调用侧契约：这些常见输入必须可归一化到 yes/no，避免后续 not in 校验误报
    for raw in ("Yes", "No", "YES", "no", "是", "否", None, "", "  yes  ", "  N  "):
        normalized = _normalize_yesno(raw)
        assert normalized in ("yes", "no"), f"输入 {raw!r} 归一化后仍非法：{normalized!r}"

    print("OK")


if __name__ == "__main__":
    main()
