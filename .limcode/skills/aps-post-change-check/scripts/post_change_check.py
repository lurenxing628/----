"""
APS 改动后一键质量检查脚本。
检查项：ruff lint（仅改动文件）、架构分层合规、变更范围、联动更新提醒。
"""
import os
import re
import subprocess
import sys


def find_repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.exists(os.path.join(here, "app.py")) and os.path.exists(os.path.join(here, "schema.sql")):
            return here
        here = os.path.dirname(here)
    raise RuntimeError("未找到项目根目录")


def get_changed_files(repo_root):
    """获取 git 已改动文件列表（staged + unstaged + untracked）。"""
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_root, capture_output=True, text=True, encoding="utf-8"
    )
    files = []
    for line in result.stdout.strip().splitlines():
        if len(line) > 3:
            fpath = line[3:].strip().strip('"')
            if " -> " in fpath:
                fpath = fpath.split(" -> ")[-1]
            files.append(fpath)
    return files


def check_ruff(repo_root, py_files):
    """对指定 Python 文件运行 ruff check。"""
    if not py_files:
        return True, []
    abs_files = [os.path.join(repo_root, f) for f in py_files if os.path.exists(os.path.join(repo_root, f))]
    if not abs_files:
        return True, []
    try:
        result = subprocess.run(
            ["ruff", "check", "--output-format", "concise"] + abs_files,
            cwd=repo_root, capture_output=True, text=True, encoding="utf-8"
        )
        issues = [line for line in result.stdout.strip().splitlines() if line and not line.startswith("Found")]
        return result.returncode == 0, issues
    except FileNotFoundError:
        return True, ["⚠ ruff 未安装，跳过 lint 检查"]


def check_architecture(repo_root, changed_files):
    """检查改动文件是否存在架构分层违反。"""
    violations = []
    skipped = []
    for fpath in changed_files:
        abs_path = os.path.join(repo_root, fpath)
        if not fpath.endswith(".py") or not os.path.exists(abs_path):
            continue
        try:
            with open(abs_path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            skipped.append(f"{fpath} - read failed: {type(e).__name__}: {e}")
            continue
        norm = fpath.replace("\\", "/")

        if norm.startswith("web/routes/"):
            route_db_re = re.compile(r"\b(cursor|conn)\.(execute|fetchone|fetchall)\b")
            for i, line in enumerate(content.splitlines(), 1):
                s = line.strip()
                if s.startswith("#"):
                    continue
                m = route_db_re.search(s)
                if m:
                    violations.append(f"{fpath}:{i} - route 层直接操作 DB ({m.group(1)}.{m.group(2)})")

        if norm.startswith("core/services/"):
            for i, line in enumerate(content.splitlines(), 1):
                s = line.strip()
                if s.startswith("#"):
                    continue
                if re.search(r"from\s+flask\s+import\s+.*\brequest\b", s):
                    violations.append(f"{fpath}:{i} - service 层导入了 flask.request")

    return violations, skipped


_ENUM_BARE_STRINGS = [
    "pending", "scheduled", "processing", "completed", "cancelled",
    "active", "inactive", "maintain",
    "normal", "urgent", "critical",
    "internal", "external",
    "workday", "weekend", "holiday",
    "yes", "no", "partial",
    "separate", "merged", "skipped",
]
_ENUM_RE = re.compile(
    r"""(?:==|!=)\s*["']({values})["']"""
    .format(values="|".join(re.escape(v) for v in _ENUM_BARE_STRINGS))
)
_ENUM_IN_RE = re.compile(r"\b(?:not\s+in|in)\s*[\(\[]")
_QUOTED_STR_RE = re.compile(r"""["']([^"']+)["']""")


def check_code_quality(repo_root, changed_files):
    """检查改动文件的代码质量（枚举裸字符串、future annotations）。"""
    issues = []
    info = []
    skipped = []
    for fpath in changed_files:
        abs_path = os.path.join(repo_root, fpath)
        if not fpath.endswith(".py") or not os.path.exists(abs_path):
            continue
        norm = fpath.replace("\\", "/")
        if norm.startswith("tests/") or norm.startswith(".limcode/"):
            continue
        try:
            with open(abs_path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            skipped.append(f"{fpath} - read failed: {type(e).__name__}: {e}")
            continue

        if not content.strip():
            continue

        if "from __future__ import annotations" not in content:
            is_core = any(norm.startswith(p) for p in [
                "web/routes/", "core/services/", "data/repositories/",
                "core/models/", "core/infrastructure/",
            ])
            if is_core:
                issues.append(f"{fpath} - 缺少 from __future__ import annotations")

        for i, line in enumerate(content.splitlines(), 1):
            s = line.strip()
            if s.startswith("#"):
                continue
            m = _ENUM_RE.search(s)
            if m:
                issues.append(f"{fpath}:{i} - 裸字符串枚举 '{m.group(0).strip()}'，应使用 enums.py")
                continue
            if _ENUM_IN_RE.search(s):
                quoted = _QUOTED_STR_RE.findall(s)
                hits = [v for v in quoted if v in _ENUM_BARE_STRINGS]
                if hits:
                    uniq = list(dict.fromkeys(hits))
                    info.append(
                        f"{fpath}:{i} - （INFO）枚举集合比较 {uniq}，建议使用 enums.py（或先统一 normalize）"
                    )
    return issues, info, skipped


def check_complexity(repo_root, changed_files):
    """对改动的 Python 文件做圈复杂度检查（仅改动文件）。"""
    try:
        from radon.complexity import cc_rank, cc_visit  # pyright: ignore[reportMissingImports]
    except ImportError:
        return [], ["⚠ radon 未安装，跳过复杂度检查"]

    threshold = 15
    issues = []
    skipped = []
    for fpath in changed_files:
        abs_path = os.path.join(repo_root, fpath)
        if not fpath.endswith(".py") or not os.path.exists(abs_path):
            continue
        norm = fpath.replace("\\", "/")
        if norm.startswith("tests/") or norm.startswith(".limcode/"):
            continue
        try:
            with open(abs_path, encoding="utf-8", errors="replace") as f:
                source = f.read()
            blocks = cc_visit(source)
            for block in blocks:
                if block.complexity > threshold:
                    rank = cc_rank(block.complexity)
                    issues.append(
                        f"{fpath}:{block.lineno} {block.name} "
                        f"complexity={block.complexity} (rank {rank})"
                    )
        except SyntaxError as e:
            skipped.append(
                f"{fpath} - SyntaxError: {getattr(e, 'msg', str(e))} (line {getattr(e, 'lineno', '?')})"
            )
        except Exception as e:
            skipped.append(f"{fpath} - {type(e).__name__}: {e}")
    return issues, skipped


def check_linkage_reminders(changed_files):
    """根据改动文件类型生成联动更新提醒。"""
    reminders = []
    has_route = any(f.replace("\\", "/").startswith("web/routes/") and f.endswith(".py") for f in changed_files)
    has_schema = any("schema.sql" in f or "migrations/" in f.replace("\\", "/") for f in changed_files)
    has_scheduler = any(f.replace("\\", "/").startswith("core/services/scheduler/") for f in changed_files)
    has_excel = any("excel" in f.lower() and f.endswith(".py") for f in changed_files)
    has_template = any(f.replace("\\", "/").startswith("templates/") and f.endswith(".html") for f in changed_files)

    if has_route:
        reminders.append("改了 route → 检查对应 template 是否需要同步；检查 面板与接口清单.md")
    if has_schema:
        reminders.append("改了 schema/migration → 必须更新：开发文档数据模型章节 + 速查表字段字典")
    if has_scheduler:
        reminders.append("改了 scheduler 服务 → 检查速查表 ScheduleConfig 部分是否需要更新")
    if has_excel:
        reminders.append("改了 Excel 相关代码 → 检查速查表 Excel 模板清单是否需要更新")
    if has_template:
        reminders.append("改了 template → 检查 面板与接口清单.md 是否需要更新")
    return reminders


def _safe_print(text: str = "") -> None:
    s = str(text)
    try:
        print(s)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(s.encode(enc, errors="replace").decode(enc, errors="replace"))


def main():
    repo_root = find_repo_root()
    changed = get_changed_files(repo_root)

    _safe_print("=" * 60)
    _safe_print("APS 改动后一键检查")
    _safe_print("=" * 60)

    # 1) 变更范围
    _safe_print(f"\n## 变更范围：{len(changed)} 个文件")
    for f in changed:
        _safe_print(f"  - {f}")

    # 2) Ruff lint
    py_files = [f for f in changed if f.endswith(".py")]
    lint_ok, lint_issues = check_ruff(repo_root, py_files)
    ruff_skipped = any("ruff 未安装" in x for x in lint_issues)
    lint_label = "SKIP（ruff 未安装）" if ruff_skipped else ("PASS" if lint_ok else "FAIL")
    _safe_print(f"\n## Ruff Lint：{lint_label}")
    if lint_issues:
        for issue in lint_issues[:20]:
            _safe_print(f"  {issue}")
        if len(lint_issues) > 20:
            _safe_print(f"  ...（共 {len(lint_issues)} 个问题）")

    # 3) 架构合规
    arch_violations, arch_skipped = check_architecture(repo_root, changed)
    _safe_print(f"\n## 架构分层合规：{'PASS' if not arch_violations else 'FAIL'}")
    if arch_violations:
        for v in arch_violations:
            _safe_print(f"  ✗ {v}")
    if arch_skipped:
        _safe_print(f"  ⚠ 跳过 {len(arch_skipped)} 个文件（读取失败）：")
        for s in arch_skipped[:10]:
            _safe_print(f"    - {s}")
        if len(arch_skipped) > 10:
            _safe_print(f"    ...（共 {len(arch_skipped)} 个）")

    # 4) 代码质量检查（枚举、annotations）
    quality_issues, quality_info, quality_skipped = check_code_quality(repo_root, changed)
    _safe_print(f"\n## 代码质量检查：{'PASS' if not quality_issues else f'WARN（{len(quality_issues)} 项）'}")
    if quality_issues:
        for q in quality_issues[:15]:
            _safe_print(f"  ⚠ {q}")
        if len(quality_issues) > 15:
            _safe_print(f"  ...（共 {len(quality_issues)} 项）")
    if quality_info:
        _safe_print(f"  INFO：枚举集合比较 {len(quality_info)} 项（可能是输入校验，建议统一 normalize/enums）")
        for q in quality_info[:15]:
            _safe_print(f"    - {q}")
        if len(quality_info) > 15:
            _safe_print(f"    ...（共 {len(quality_info)} 项）")
    if quality_skipped:
        _safe_print(f"  ⚠ 跳过 {len(quality_skipped)} 个文件（读取失败）：")
        for s in quality_skipped[:10]:
            _safe_print(f"    - {s}")
        if len(quality_skipped) > 10:
            _safe_print(f"    ...（共 {len(quality_skipped)} 个）")

    # 5) 圈复杂度检查（改动文件）
    complexity_issues, complexity_skipped = check_complexity(repo_root, changed)
    radon_skipped = any("radon 未安装" in x for x in complexity_skipped)
    if radon_skipped:
        complexity_label = "SKIP（radon 未安装）"
    else:
        complexity_label = "PASS" if not complexity_issues else f"WARN（{len(complexity_issues)} 个超标函数）"
    _safe_print(f"\n## 圈复杂度检查：{complexity_label}")
    if complexity_issues:
        for ci in complexity_issues[:10]:
            _safe_print(f"  ⚠ {ci}")
        if len(complexity_issues) > 10:
            _safe_print(f"  ...（共 {len(complexity_issues)} 个）")
    if complexity_skipped:
        _safe_print(f"  ⚠ 跳过 {len(complexity_skipped)} 个文件（未检查）：")
        for s in complexity_skipped[:10]:
            _safe_print(f"    - {s}")
        if len(complexity_skipped) > 10:
            _safe_print(f"    ...（共 {len(complexity_skipped)} 个）")

    # 6) 联动更新提醒
    reminders = check_linkage_reminders(changed)
    _safe_print(f"\n## 联动更新提醒：{len(reminders)} 项")
    if reminders:
        for r in reminders:
            _safe_print(f"  → {r}")
    else:
        _safe_print("  无需额外联动更新")

    # 7) 总结
    all_ok = lint_ok and not arch_violations
    _safe_print(f"\n{'=' * 60}")
    warnings = []
    if any("ruff 未安装" in x for x in lint_issues):
        warnings.append("ruff 未安装：Ruff Lint 未执行")
    if arch_skipped:
        warnings.append(f"架构检查跳过 {len(arch_skipped)} 个文件（读取失败）")
    if quality_skipped:
        warnings.append(f"代码质量检查跳过 {len(quality_skipped)} 个文件（读取失败）")
    if any("radon 未安装" in x for x in complexity_skipped):
        warnings.append("radon 未安装：圈复杂度检查未执行")
    elif complexity_skipped:
        warnings.append(f"圈复杂度检查跳过 {len(complexity_skipped)} 个文件")

    if all_ok and warnings:
        summary = "PASS（有警告）- 可提交，但建议先处理/确认警告项"
    else:
        summary = "PASS - 可以提交" if all_ok else "FAIL - 请先修复上述问题"
    _safe_print(f"总结：{summary}")
    if warnings:
        for w in warnings:
            _safe_print(f"  ⚠ {w}")
    if reminders:
        _safe_print("（注意：请确认联动更新提醒项已处理）")
    _safe_print("=" * 60)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
