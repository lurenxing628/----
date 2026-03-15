"""
APS 全项目架构合规审计脚本。
检查项：分层违反、文件大小、禁止模式、命名规范、
       裸字符串枚举、future annotations、类型注解、
       循环依赖、Route→Repository 越层、死代码公开方法。
输出 Markdown 报告到 evidence/ArchAudit/。
"""
import ast
import os
import re
import sys
import time
from typing import Dict, List, Set, Tuple


def find_repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.exists(os.path.join(here, "app.py")) and os.path.exists(os.path.join(here, "schema.sql")):
            return here
        here = os.path.dirname(here)
    raise RuntimeError("未找到项目根目录")


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def scan_layer_violations(repo_root) -> List[str]:
    """扫描分层架构违反。"""
    violations = []

    route_dir = os.path.join(repo_root, "web", "routes")
    route_db_re = re.compile(r"\b(cursor|conn)\.(execute|fetchone|fetchall)\b")
    if os.path.isdir(route_dir):
        for dirpath, _, filenames in os.walk(route_dir):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                txt = _read(fpath)
                rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
                for i, line in enumerate(txt.splitlines(), 1):
                    s = line.strip()
                    if s.startswith("#"):
                        continue
                    m = route_db_re.search(s)
                    if m:
                        violations.append(
                            f"[LAYER] {rel}:{i} - route 直接操作 DB ({m.group(1)}.{m.group(2)})"
                        )

    svc_base = os.path.join(repo_root, "core", "services")
    if os.path.isdir(svc_base):
        for dirpath, _, filenames in os.walk(svc_base):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                txt = _read(fpath)
                rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
                for i, line in enumerate(txt.splitlines(), 1):
                    s = line.strip()
                    if s.startswith("#"):
                        continue
                    if re.search(r"from\s+flask\s+import\s+.*\brequest\b", s):
                        violations.append(f"[LAYER] {rel}:{i} - service 导入 flask.request")

    return violations


def scan_file_sizes(repo_root) -> List[str]:
    """扫描超大文件。"""
    issues = []
    for check_dir in ["web/routes", "web/viewmodels", "core/services", "data/repositories", "core/infrastructure", "core/models"]:
        base = os.path.join(repo_root, check_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                line_count = len(_read(fpath).splitlines())
                if line_count > 500:
                    rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
                    issues.append(f"[SIZE] {rel} - {line_count} 行（超过 500 行限制）")
    return issues


def scan_forbidden_patterns(repo_root) -> List[str]:
    """扫描禁止模式。"""
    issues = []
    for check_dir in ["web/routes", "web/viewmodels", "core/services", "data/repositories"]:
        base = os.path.join(repo_root, check_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                txt = _read(fpath)
                rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
                for i, line in enumerate(txt.splitlines(), 1):
                    s = line.strip()
                    if s.startswith("#"):
                        continue
                    if re.match(r"from\s+\S+\s+import\s+\*", s):
                        issues.append(f"[FORBIDDEN] {rel}:{i} - import * 禁止使用")
                    if re.match(r"except\s+Exception(?:\s+as\s+\w+)?\s*:\s*pass\b", s):
                        issues.append(f"[FORBIDDEN] {rel}:{i} - except Exception: pass 静默吞异常")
                    if re.match(r"except\s*:\s*pass\b", s):
                        issues.append(f"[FORBIDDEN] {rel}:{i} - except: pass 静默吞异常（更严重）")
    return issues


def scan_naming(repo_root) -> List[str]:
    """扫描文件命名是否为 snake_case。"""
    issues = []
    snake_re = re.compile(r"^[a-z][a-z0-9_]*$")
    for check_dir in ["web/routes", "web/viewmodels", "core/services", "data/repositories"]:
        base = os.path.join(repo_root, check_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for fname in filenames:
                if not fname.endswith(".py") or fname.startswith("__"):
                    continue
                name_part = fname[:-3]
                if not snake_re.match(name_part):
                    rel = os.path.relpath(os.path.join(dirpath, fname), repo_root).replace("\\", "/")
                    issues.append(f"[NAMING] {rel} - 文件名不是 snake_case")
    return issues


# --- 以下为 V2 新增检查 ---

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


def scan_bare_enum_strings(repo_root) -> Tuple[List[str], List[str]]:
    """扫描业务代码中直接用裸字符串比较状态值（应使用 enums.py 枚举）。"""
    issues = []
    info = []
    skip_dirs = {"tests", "evidence", ".cursor", "backups", "static"}
    for check_dir in ["web/routes", "core/services", "data/repositories"]:
        base = os.path.join(repo_root, check_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            if any(sd in dirpath.replace("\\", "/").split("/") for sd in skip_dirs):
                continue
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                txt = _read(fpath)
                rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
                for i, line in enumerate(txt.splitlines(), 1):
                    s = line.strip()
                    if s.startswith("#"):
                        continue
                    m = _ENUM_RE.search(s)
                    if m:
                        issues.append(
                            f"[ENUM] {rel}:{i} - 裸字符串比较 '{m.group(0).strip()}'，应使用 enums.py 枚举"
                        )
                        continue
                    if _ENUM_IN_RE.search(s):
                        quoted = _QUOTED_STR_RE.findall(s)
                        hits = [v for v in quoted if v in _ENUM_BARE_STRINGS]
                        if hits:
                            uniq = list(dict.fromkeys(hits))
                            info.append(
                                f"[ENUM-INFO] {rel}:{i} - 枚举集合比较 {uniq}（可能是输入校验），建议使用 enums.py/normalize"
                            )
    return issues, info


def scan_future_annotations(repo_root) -> List[str]:
    """扫描核心代码文件是否缺少 from __future__ import annotations。"""
    issues = []
    for check_dir in ["web/routes", "core/services", "data/repositories", "core/models", "core/infrastructure"]:
        base = os.path.join(repo_root, check_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                txt = _read(fpath)
                if not txt.strip():
                    continue
                rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
                if "from __future__ import annotations" not in txt:
                    issues.append(f"[FUTURE] {rel} - 缺少 from __future__ import annotations")
    return issues


def scan_public_func_annotations(repo_root) -> Tuple[List[str], List[str]]:
    """扫描 Service/Repository 公开方法是否缺少返回类型注解。返回 (issues, skipped)。"""
    issues = []
    skipped = []
    for check_dir in ["core/services", "data/repositories"]:
        base = os.path.join(repo_root, check_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
                try:
                    txt = _read(fpath)
                    tree = ast.parse(txt, filename=rel)
                except SyntaxError as e:
                    skipped.append(
                        f"[TYPEHINT-SKIP] {rel}:{getattr(e, 'lineno', '?')} - SyntaxError，无法检查返回类型注解"
                    )
                    continue
                except Exception as e:
                    skipped.append(f"[TYPEHINT-SKIP] {rel} - 解析失败：{type(e).__name__}: {e}")
                    continue

                for node in tree.body:
                    if not isinstance(node, ast.ClassDef):
                        continue
                    cls_name = node.name
                    for item in node.body:
                        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            continue
                        func_name = item.name
                        if func_name.startswith("_") or func_name == "__init__":
                            continue
                        if item.returns is None:
                            issues.append(
                                f"[TYPEHINT] {rel}:{item.lineno} - 公开方法 {cls_name}.{func_name}() 缺少返回类型注解"
                            )
    return issues, skipped


# --- 以下为 V3 新增：引用链级检查 ---


def _extract_imports(filepath: str) -> List[str]:
    """提取文件的 import/from...import 语句（简化版，不做 AST 解析）。"""
    lines = []
    txt = _read(filepath)
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("import ") or s.startswith("from "):
            lines.append(s)
    return lines


def scan_circular_dependencies(repo_root) -> List[str]:
    """检测 Service 模块之间的循环导入。

    规则：如果 service_a 导入了 service_b，同时 service_b 也导入了 service_a，
    则标记为循环依赖。
    """
    issues = []
    svc_base = os.path.join(repo_root, "core", "services")
    if not os.path.isdir(svc_base):
        return issues

    module_imports: Dict[str, Set[str]] = {}

    for dirpath, _, filenames in os.walk(svc_base):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            package = os.path.relpath(dirpath, svc_base).replace("\\", "/").replace("/", ".")
            if package == ".":
                package = fname[:-3]
            else:
                package = package + "." + fname[:-3]

            imports = _extract_imports(fpath)
            targets: Set[str] = set()
            for imp_line in imports:
                if "core.services." in imp_line:
                    m = re.search(r"core\.services\.(\w+(?:\.\w+)*)", imp_line)
                    if m:
                        targets.add(m.group(1))
            module_imports[package] = targets

    checked: Set[str] = set()
    for mod_a, deps_a in module_imports.items():
        pkg_a = mod_a.split(".")[0]
        for dep in deps_a:
            pkg_dep = dep.split(".")[0]
            if pkg_a == pkg_dep:
                continue
            pair_key = tuple(sorted([pkg_a, pkg_dep]))
            if pair_key in checked:
                continue
            for mod_b, deps_b in module_imports.items():
                pkg_b = mod_b.split(".")[0]
                if pkg_b != pkg_dep:
                    continue
                for dep_b in deps_b:
                    if dep_b.split(".")[0] == pkg_a:
                        issues.append(
                            f"[CIRCULAR] core/services/{pkg_a}/ <-> core/services/{pkg_dep}/ "
                            f"（{mod_a} 导入 {dep}，{mod_b} 导入 {dep_b}）"
                        )
                        checked.add(pair_key)
                        break

    return issues


def scan_route_imports_repository(repo_root) -> List[str]:
    """检测 Route 文件是否直接 import 了 Repository 类（应通过 Service 中转）。

    白名单：ScheduleHistoryRepository 在 route 中有合理的直接使用场景（只读查询）。
    """
    issues = []
    whitelist = {"ScheduleHistoryRepository"}
    route_dir = os.path.join(repo_root, "web", "routes")
    if not os.path.isdir(route_dir):
        return issues

    repo_class_re = re.compile(r"\b(\w+Repository)\b")

    for dirpath, _, filenames in os.walk(route_dir):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
            imports = _extract_imports(fpath)
            for imp_line in imports:
                if "repositories" not in imp_line:
                    continue
                matches = repo_class_re.findall(imp_line)
                for repo_name in matches:
                    if repo_name in whitelist:
                        continue
                    issues.append(
                        f"[CROSS-LAYER] {rel} - 直接导入了 {repo_name}（应通过 Service 中转）"
                    )
    return issues


def scan_dead_public_methods(repo_root) -> List[str]:
    """检测 Service 层的公开方法中有无外部调用者为 0 的（潜在死代码）。

    只检查 core/services/ 下的公开方法（不含 __init__、不含 _ 前缀）。
    搜索范围：web/routes + core/services + core/algorithms + scripts（跨文件）。
    """
    issues = []
    svc_base = os.path.join(repo_root, "core", "services")
    if not os.path.isdir(svc_base):
        return issues

    search_dirs = [
        os.path.join(repo_root, "web", "routes"),
        os.path.join(repo_root, "core", "services"),
        os.path.join(repo_root, "core", "algorithms"),
        os.path.join(repo_root, "scripts"),
    ]

    all_code = ""
    for sd in search_dirs:
        if not os.path.isdir(sd):
            continue
        for dirpath, _, filenames in os.walk(sd):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                all_code += _read(os.path.join(dirpath, fname)) + "\n"

    func_re = re.compile(r"^\s{4}def ([a-z]\w+)\(self", re.MULTILINE)

    for dirpath, _, filenames in os.walk(svc_base):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            txt = _read(fpath)
            lines = txt.splitlines()
            rel = os.path.relpath(fpath, repo_root).replace("\\", "/")

            for m in func_re.finditer(txt):
                func_name = m.group(1)
                if func_name.startswith("_") or func_name == "__init__":
                    continue
                if len(func_name) <= 3:
                    continue

                line_no = txt[:m.start()].count("\n") + 1
                is_property = False
                try:
                    j = line_no - 2  # 0-based index of previous line
                    while j >= 0:
                        prev = lines[j].strip()
                        if prev == "":
                            j -= 1
                            continue
                        if prev.startswith("@"):
                            if prev == "@property" or prev.startswith("@property("):
                                is_property = True
                            j -= 1
                            continue
                        break
                except Exception:
                    is_property = False

                if is_property:
                    # 属性访问：wr.start_str（而不是 wr.start_str()）
                    search_pat = re.compile(r"\." + re.escape(func_name) + r"\b(?!\s*\()")
                else:
                    search_pat = re.compile(r"\." + re.escape(func_name) + r"\s*\(")

                matches = search_pat.findall(all_code)
                file_matches = search_pat.findall(txt)
                external_calls = len(matches) - len(file_matches)
                if external_calls <= 0:
                    issues.append(
                        f"[DEAD-CODE] {rel}:{line_no} - 公开方法 {func_name}() 无外部调用者（潜在死代码）"
                    )
    return issues


def scan_cyclomatic_complexity(repo_root) -> Tuple[List[str], Dict, List[str]]:
    """扫描圈复杂度，返回 (超标项, 分布统计, 扫描跳过项)。"""
    try:
        from radon.complexity import cc_rank, cc_visit
    except ImportError:
        return [], {}, ["[COMPLEXITY] radon 未安装，跳过复杂度检查"]

    issues = []
    skipped = []
    stats = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}
    threshold = 15  # 项目门禁：单函数复杂度 > 15 即超标

    for check_dir in ["web/routes", "core/services", "data/repositories", "core/models", "core/infrastructure"]:
        base = os.path.join(repo_root, check_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
                try:
                    source = _read(fpath)
                    blocks = cc_visit(source)
                    for block in blocks:
                        rank = cc_rank(block.complexity)
                        if rank in stats:
                            stats[rank] += 1
                        if block.complexity > threshold:
                            issues.append(
                                f"[COMPLEXITY] {rel}:{block.lineno} "
                                f"{block.name} complexity={block.complexity} "
                                f"(rank {rank})"
                            )
                except SyntaxError as e:
                    skipped.append(
                        f"[COMPLEXITY-SKIP] {rel} - SyntaxError: {getattr(e, 'msg', str(e))} "
                        f"(line {getattr(e, 'lineno', '?')})"
                    )
                except Exception as e:
                    skipped.append(f"[COMPLEXITY-SKIP] {rel} - {type(e).__name__}: {e}")
    return issues, stats, skipped


VULTURE_MIN_CONFIDENCE = 80


def scan_vulture_dead_code(repo_root) -> Tuple[List[str], List[str]]:
    """运行 Vulture 死代码检测。返回 (issues, skipped)。"""
    import subprocess as sp

    issues = []
    skipped = []
    try:
        result = sp.run(
            ["vulture", "core/", "data/", "web/", "--min-confidence", str(int(VULTURE_MIN_CONFIDENCE))],
            cwd=repo_root, capture_output=True, text=True, encoding="utf-8",
        )
        for line in result.stdout.strip().splitlines():
            if line.strip():
                issues.append(f"[VULTURE] {line.strip()}")
    except FileNotFoundError:
        skipped.append("[VULTURE] vulture 未安装，跳过死代码检测")
    return issues, skipped


def generate_report(repo_root) -> Tuple[str, int]:
    layer = scan_layer_violations(repo_root)
    sizes = scan_file_sizes(repo_root)
    forbidden = scan_forbidden_patterns(repo_root)
    naming = scan_naming(repo_root)
    enums, enums_info = scan_bare_enum_strings(repo_root)
    future = scan_future_annotations(repo_root)
    typehints, typehint_skipped = scan_public_func_annotations(repo_root)
    circular = scan_circular_dependencies(repo_root)
    cross_layer = scan_route_imports_repository(repo_root)
    dead_code = scan_dead_public_methods(repo_root)
    complexity, complexity_stats, complexity_skipped = scan_cyclomatic_complexity(repo_root)
    vulture, vulture_skipped = scan_vulture_dead_code(repo_root)

    all_issues = (
        layer + sizes + forbidden + naming + enums + future + typehints
        + circular + cross_layer + dead_code + complexity + vulture
    )
    total = len(all_issues)
    all_skipped = typehint_skipped + complexity_skipped + vulture_skipped
    skip_total = len(all_skipped)

    lines = []
    lines.append("# APS 架构合规审计报告")
    lines.append("")
    lines.append(f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 仓库根目录：`{repo_root}`")
    lines.append("")
    lines.append("## 总结")
    lines.append(f"- 总问题数：{total}")
    lines.append(f"  - 分层违反：{len(layer)}")
    lines.append(f"  - 文件超限：{len(sizes)}")
    lines.append(f"  - 禁止模式：{len(forbidden)}")
    lines.append(f"  - 命名问题：{len(naming)}")
    lines.append(f"  - 裸字符串枚举：{len(enums)}")
    lines.append(f"  - 枚举集合比较（INFO）：{len(enums_info)}")
    lines.append(f"  - 缺少 future annotations：{len(future)}")
    lines.append(f"  - 公开方法缺返回类型注解：{len(typehints)}")
    lines.append(f"  - Service 循环依赖：{len(circular)}")
    lines.append(f"  - Route 越层导入 Repository：{len(cross_layer)}")
    lines.append(f"  - 潜在死代码公开方法：{len(dead_code)}")
    lines.append(f"  - 圈复杂度超标（>15）：{len(complexity)}")
    lines.append(f"  - 圈复杂度扫描跳过：{len(complexity_skipped)}")
    lines.append(f"  - 类型注解扫描跳过：{len(typehint_skipped)}")
    lines.append(f"  - Vulture 死代码（min_confidence={int(VULTURE_MIN_CONFIDENCE)}）：{len(vulture)}")
    lines.append(f"  - Vulture 扫描跳过：{len(vulture_skipped)}")
    lines.append(f"- 跳过/信息项总计：{skip_total}（不影响 PASS/FAIL）")
    lines.append(f"- 结论：{'PASS' if total == 0 else 'FAIL（存在违反项）'}")
    lines.append("")

    if complexity_stats:
        lines.append("## 圈复杂度分布")
        for rank in ["A", "B", "C", "D", "E", "F"]:
            count = complexity_stats.get(rank, 0)
            label = {
                "A": "简单(1-5)",
                "B": "低(6-10)",
                "C": "中(11-20)",
                "D": "高(21-30)",
                "E": "很高(31-40)",
                "F": "极高(41+)",
            }
            bar = "#" * min(count, 50)
            lines.append(f"- {rank} {label[rank]}: {count} {bar}")
        lines.append("")

    sections = [
        ("分层违反", layer),
        ("文件超限", sizes),
        ("禁止模式", forbidden),
        ("命名问题", naming),
        ("裸字符串枚举", enums),
        ("枚举集合比较（INFO）", enums_info),
        ("缺少 future annotations", future),
        ("公开方法缺返回类型注解", typehints),
        ("Service 循环依赖", circular),
        ("Route 越层导入 Repository", cross_layer),
        ("潜在死代码公开方法", dead_code),
        ("圈复杂度超标", complexity),
        ("圈复杂度扫描跳过", complexity_skipped),
        ("类型注解扫描跳过", typehint_skipped),
        ("Vulture 死代码", vulture),
        ("Vulture 扫描跳过", vulture_skipped),
    ]
    for title, items in sections:
        lines.append(f"## {title}")
        if items:
            for item in items:
                lines.append(f"- {item}")
        else:
            lines.append("- 无")
        lines.append("")

    return "\n".join(lines) + "\n", total


def main():
    repo_root = find_repo_root()
    content, total = generate_report(repo_root)

    out_dir = os.path.join(repo_root, "evidence", "ArchAudit")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "arch_audit_report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    try:
        print(content)
    except UnicodeEncodeError:
        # Windows 默认控制台编码可能不是 UTF-8（如 GBK），避免因个别字符导致脚本崩溃
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(content.encode(enc, errors="replace").decode(enc, errors="replace"))
    print(f"报告已输出到：{out_path}")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
