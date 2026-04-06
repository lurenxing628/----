"""T1: 验证 build_win7_onedir.bat 中引用的 vendor 目录是否存在。

审查发现 BUILD-MISSING-VENDOR 指出构建脚本硬编码了
--add-data "vendor;vendor"，但仓库中 vendor 目录可能不存在。
本脚本检查：
1. .gitignore 中是否有 vendor 排除规则
2. vendor 目录是否实际存在
3. vendor/.gitkeep 是否存在
4. build_win7_onedir.bat 中 vendor 引用是否有条件判断
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    has_vendor_conditional = False

    # 1. 检查 .gitignore
    gitignore = REPO_ROOT / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if "vendor" in content:
            print("[T1] .gitignore 中存在 vendor 排除规则 ✓")
        else:
            warnings.append(".gitignore 中没有 vendor 排除规则")
    else:
        errors.append(".gitignore 不存在")

    # 2. 检查 vendor 目录
    vendor_dir = REPO_ROOT / "vendor"
    vendor_gitkeep = vendor_dir / ".gitkeep"

    if vendor_dir.exists() and vendor_dir.is_dir():
        items = list(vendor_dir.iterdir())
        print(f"[T1] vendor 目录存在，包含 {len(items)} 项 ✓")
    else:
        warnings.append(
            "vendor 目录不存在。build_win7_onedir.bat 第35行的 "
            '--add-data "vendor;vendor" 在构建时会导致 PyInstaller 报错。'
        )

    if vendor_gitkeep.exists():
        print("[T1] vendor/.gitkeep 存在 ✓")
    else:
        warnings.append("vendor/.gitkeep 不存在")

    # 3. 检查 build_win7_onedir.bat 中是否对 vendor 做了条件判断
    bat_file = REPO_ROOT / "build_win7_onedir.bat"
    if bat_file.exists():
        bat_content = bat_file.read_text(encoding="utf-8", errors="replace")
        if "vendor" in bat_content:
            for line in bat_content.splitlines():
                lower = line.lower().strip()
                if "vendor" in lower and ("if exist" in lower or "if not exist" in lower):
                    has_vendor_conditional = True
                    break
            if has_vendor_conditional:
                print("[T1] build_win7_onedir.bat 中对 vendor 有条件判断 ✓")
            else:
                warnings.append(
                    "build_win7_onedir.bat 中无条件引用 vendor 目录，"
                    "当目录不存在时 PyInstaller 会直接报错。"
                )
    else:
        errors.append("build_win7_onedir.bat 不存在")

    # 输出总结
    print("\n" + "=" * 60)
    if errors:
        print(f"错误 ({len(errors)}):")
        for item in errors:
            print(f"  ✗ {item}")
    if warnings:
        print(f"警告 ({len(warnings)}):")
        for item in warnings:
            print(f"  ⚠ {item}")
    if not errors and not warnings:
        print("全部通过 ✓")

    # 结论
    print("\n结论:")
    if not vendor_dir.exists():
        print(
            "  vendor 目录不存在且构建脚本无条件引用，"
            "确认 BUILD-MISSING-VENDOR 问题存在。\n"
            "  建议：在 --add-data 前增加 if exist vendor 条件判断，"
            "或创建空的 vendor 目录。"
        )
        return 1

    if has_vendor_conditional:
        print("  vendor 目录当前存在，且构建脚本已具备条件保护。")
        print("  当前仓库/当前机器不会触发 BUILD-MISSING-VENDOR。")
    else:
        print("  vendor 目录当前存在，因此当前机器上的构建不会立即失败。")
        print("  但构建脚本仍缺少 if exist 保护，换一台缺少 vendor 的构建机会失败。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
