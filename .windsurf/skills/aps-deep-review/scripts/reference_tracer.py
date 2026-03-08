"""
引用链追踪器：从 git diff 提取变更函数/方法，向上追踪所有调用者，向下追踪被调用者。
输出引用图（Markdown 格式），供 Agent 做深度 review 时使用。

用法：
    python reference_tracer.py                    # 分析当前 git 未提交的变更
    python reference_tracer.py --commit HEAD~1    # 分析最近一次提交的变更
    python reference_tracer.py --file core/services/scheduler/batch_service.py  # 分析指定文件
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Set, Tuple


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        if os.path.exists(os.path.join(here, "app.py")) and os.path.exists(os.path.join(here, "schema.sql")):
            return here
        here = os.path.dirname(here)
    raise RuntimeError("未找到项目根目录")


# ---------------------------------------------------------------------------
# Phase 1: 提取变更中的函数/方法定义
# ---------------------------------------------------------------------------

def get_changed_files_from_git(repo_root: str, commit: Optional[str] = None) -> List[str]:
    """获取 git 变更的 Python 文件列表。"""
    def _untracked_py_files() -> Set[str]:
        files: Set[str] = set()
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except Exception:
            return files
        for line in (result.stdout or "").splitlines():
            if not line.startswith("??"):
                continue
            fpath = line[3:].strip().strip('"')
            if " -> " in fpath:
                fpath = fpath.split(" -> ")[-1]
            if fpath.endswith(".py"):
                files.add(fpath)
        return files

    base = commit or "HEAD"
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        files = {f.strip() for f in (result.stdout or "").splitlines() if f.strip().endswith(".py")}
    except Exception:
        files = set()

    # 关键修复：即使 diff 非空，也要纳入 untracked 新增文件，避免漏分析
    files |= _untracked_py_files()
    return sorted(files)


def extract_definitions(filepath: str) -> List[Dict]:
    """用 AST 从 Python 文件提取所有函数/方法定义。"""
    defs = []
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, Exception):
        return defs

    # 仅提取“顶层 def/class”与“class 内的方法”，避免把嵌套函数误当成模块级函数
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                args = [a.arg for a in item.args.args]
                if args and args[0] in ("self", "cls"):
                    args = args[1:]
                defs.append(
                    {
                        "type": "method",
                        "class": class_name,
                        "name": item.name,
                        "qualified": f"{class_name}.{item.name}",
                        "line": item.lineno,
                        "end_line": getattr(item, "end_lineno", item.lineno),
                        "args": args,
                        "returns": _get_return_annotation(item),
                    }
                )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.append(
                {
                    "type": "function",
                    "class": None,
                    "name": node.name,
                    "qualified": node.name,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "args": [a.arg for a in node.args.args],
                    "returns": _get_return_annotation(node),
                }
            )
    return defs


def _get_return_annotation(node) -> Optional[str]:
    if node.returns:
        try:
            return ast.dump(node.returns)
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Phase 2: 引用链追踪
# ---------------------------------------------------------------------------

_GENERIC_METHOD_NAMES = {"get", "list", "set", "create", "update", "delete", "remove", "add", "count", "exists"}


def grep_callers(
    repo_root: str,
    func_name: str,
    class_name: Optional[str] = None,
    skip_self_file: Optional[str] = None,
) -> List[Dict]:
    """在全项目中搜索 func_name 的调用者。

    对通用方法名（get/list/create 等），使用类名衍生的变量名做精确匹配，
    避免匹配到 dict.get() / repo.list() 等无关调用。
    """
    callers = []
    search_dirs = ["web/routes", "core/services", "data/repositories", "core/models",
                   "core/infrastructure", "core/algorithms"]

    is_generic = func_name in _GENERIC_METHOD_NAMES
    patterns = _build_search_patterns(func_name, class_name, is_generic)
    if not patterns:
        return callers

    for sd in search_dirs:
        base = os.path.join(repo_root, sd)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
                if skip_self_file and rel == skip_self_file.replace("\\", "/"):
                    continue
                try:
                    with open(fpath, encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                except Exception:
                    continue
                for i, line in enumerate(lines, 1):
                    s = line.strip()
                    if s.startswith("#") or s.startswith("def ") or s.startswith("async def ") or s.startswith("class "):
                        continue
                    for pat in patterns:
                        if pat.search(s):
                            callers.append({
                                "file": rel,
                                "line": i,
                                "code": s[:120],
                                "layer": _classify_layer(rel),
                            })
                            break
    return callers


def _build_search_patterns(func_name: str, class_name: Optional[str], is_generic: bool) -> List[re.Pattern]:
    """根据函数名和类名构建搜索正则。"""
    if not is_generic:
        return [
            re.compile(r"\b" + re.escape(func_name) + r"\s*\("),
            re.compile(r"\." + re.escape(func_name) + r"\s*\("),
        ]

    if not class_name:
        return [re.compile(r"\b" + re.escape(func_name) + r"\s*\(")]

    var_names = _class_to_variable_patterns(class_name)
    patterns = []
    for vn in var_names:
        patterns.append(re.compile(r"\b" + re.escape(vn) + r"\." + re.escape(func_name) + r"\s*\("))
    patterns.append(re.compile(re.escape(class_name) + r"\s*\([^)]*\)\s*\." + re.escape(func_name) + r"\s*\("))
    return patterns


def _class_to_variable_patterns(class_name: str) -> List[str]:
    """从 PascalCase 类名推导常见的变量名。

    BatchService → batch_svc, batch_service
    PartRepository → part_repo
    GanttService → gantt_svc, gantt_service
    """
    words = re.findall(r"[A-Z][a-z0-9]*", class_name)
    if not words:
        return [class_name.lower()]

    results = []
    kind = words[-1].lower()
    prefix_words = words[:-1]
    prefix = "_".join(w.lower() for w in prefix_words) if prefix_words else ""

    abbrevs = {"Service": "svc", "Repository": "repo"}
    if kind in [k.lower() for k in abbrevs]:
        for full_kind, short in abbrevs.items():
            if kind == full_kind.lower():
                if prefix:
                    results.append(f"{prefix}_{short}")
                    results.append(f"{prefix}_{kind}")
                else:
                    results.append(short)
                    results.append(kind)
    else:
        full_name = "_".join(w.lower() for w in words)
        results.append(full_name)

    if not results:
        results.append("_".join(w.lower() for w in words))

    return results


def _classify_layer(filepath: str) -> str:
    if filepath.startswith("web/routes/"):
        return "Route"
    if filepath.startswith("core/services/"):
        return "Service"
    if filepath.startswith("data/repositories/"):
        return "Repository"
    if filepath.startswith("core/models/"):
        return "Model"
    if filepath.startswith("core/infrastructure/"):
        return "Infrastructure"
    if filepath.startswith("core/algorithms/"):
        return "Algorithm"
    return "Other"


def extract_callees(filepath: str, func_name: str) -> List[str]:
    """从函数体中提取它调用的其他函数/方法。"""
    callees = []
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, Exception):
        return callees

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != func_name:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = _get_call_name(child)
                if call_name and call_name != func_name:
                    callees.append(call_name)
        break
    return list(dict.fromkeys(callees))


def _get_call_name(call_node: ast.Call) -> Optional[str]:
    func = call_node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name):
            return f"{func.value.id}.{func.attr}"
        return func.attr
    return None


# ---------------------------------------------------------------------------
# Phase 3: 跨层边界类型检查
# ---------------------------------------------------------------------------

def check_cross_layer_boundaries(repo_root: str, changed_file: str, definitions: List[Dict]) -> List[str]:
    """检查变更函数的跨层调用边界是否一致。"""
    warnings = []
    file_layer = _classify_layer(changed_file.replace("\\", "/"))

    for defn in definitions:
        if defn["name"].startswith("_"):
            continue

        callers = grep_callers(repo_root, defn["name"], class_name=defn.get("class"), skip_self_file=changed_file)
        caller_layers = set(c["layer"] for c in callers)

        if file_layer == "Repository" and "Route" in caller_layers:
            warnings.append(
                f"⚠ {defn['qualified']}() 在 Repository 层，但被 Route 层直接调用（应通过 Service 中转）"
            )

        if file_layer == "Service":
            for c in callers:
                if c["layer"] == "Repository":
                    warnings.append(
                        f"⚠ {defn['qualified']}() 在 Service 层，但被 Repository 层调用（反向依赖）"
                    )

        if defn["returns"] and "Optional" in str(defn["returns"]):
            for c in callers:
                try:
                    with open(os.path.join(repo_root, c["file"]), encoding="utf-8", errors="replace") as f:
                        ctx_lines = f.readlines()
                    start = max(0, c["line"] - 1)
                    end = min(len(ctx_lines), c["line"] + 5)
                    context = "".join(ctx_lines[start:end])
                    if "if " not in context and " is None" not in context and " is not None" not in context:
                        if "None" not in context.split(defn["name"])[-1][:80]:
                            warnings.append(
                                f"⚠ {defn['qualified']}() 返回 Optional，但 {c['file']}:{c['line']} 的调用者未做 None 检查"
                            )
                except Exception:
                    pass

    return warnings


# ---------------------------------------------------------------------------
# Phase 4: 生成报告
# ---------------------------------------------------------------------------

def generate_reference_report(repo_root: str, changed_files: List[str]) -> str:
    """生成完整的引用链追踪报告。"""
    lines = []
    lines.append("# 引用链追踪报告（深度 Review 辅助）")
    lines.append("")
    lines.append("> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。")
    lines.append("> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。")
    lines.append("> 建议：对每条调用关系回到源码上下文手工核对。")
    lines.append("")

    total_defs = 0
    total_callers = 0
    all_warnings: List[str] = []

    for changed_file in changed_files:
        abs_path = os.path.join(repo_root, changed_file)
        if not os.path.exists(abs_path):
            continue

        norm = changed_file.replace("\\", "/")
        skip = any(norm.startswith(p) for p in ["tests/", ".cursor/", "evidence/", "backups/"])
        if skip:
            continue

        defs = extract_definitions(abs_path)
        if not defs:
            continue

        file_layer = _classify_layer(norm)
        lines.append(f"## {norm}（{file_layer} 层）")
        lines.append("")

        for defn in defs:
            total_defs += 1
            is_public = not defn["name"].startswith("_")
            visibility = "公开" if is_public else "私有"
            ret_str = "无注解" if not defn["returns"] else defn["returns"][:60]

            lines.append(f"### `{defn['qualified']}()` [{visibility}]")
            lines.append(f"- 位置：第 {defn['line']}-{defn['end_line']} 行")
            lines.append(f"- 参数：{', '.join(defn['args']) if defn['args'] else '无'}")
            lines.append(f"- 返回类型：{ret_str}")

            if is_public:
                callers = grep_callers(repo_root, defn["name"], class_name=defn.get("class"), skip_self_file=changed_file)
                total_callers += len(callers)
                lines.append(f"- **调用者**（{len(callers)} 处）：")
                if callers:
                    for c in callers:
                        lines.append(f"  - `{c['file']}:{c['line']}` [{c['layer']}] `{c['code'][:80]}`")
                else:
                    lines.append("  - （无外部调用者）")

                callees = extract_callees(abs_path, defn["name"])
                if callees:
                    lines.append(f"- **被调用者**（{len(callees)} 个）：{', '.join(f'`{c}`' for c in callees[:15])}")

            lines.append("")

        boundary_warnings = check_cross_layer_boundaries(repo_root, changed_file, defs)
        all_warnings.extend(boundary_warnings)

    if all_warnings:
        lines.insert(2, "## ⚠ 跨层边界风险")
        lines.insert(3, "")
        for i, w in enumerate(all_warnings):
            lines.insert(4 + i, f"- {w}")
        lines.insert(4 + len(all_warnings), "")

    lines.append("---")
    lines.append(f"- 分析函数/方法数：{total_defs}")
    lines.append(f"- 找到调用关系：{total_callers} 处")
    lines.append(f"- 跨层边界风险：{len(all_warnings)} 项")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="引用链追踪器")
    parser.add_argument("--commit", help="分析指定 commit 的变更")
    parser.add_argument("--file", action="append", help="分析指定文件（可多次使用）")
    args = parser.parse_args()

    repo_root = find_repo_root()

    if args.file:
        changed_files = args.file
    else:
        changed_files = get_changed_files_from_git(repo_root, commit=args.commit)

    if not changed_files:
        print("未找到变更的 Python 文件。")
        return 0

    print(f"分析 {len(changed_files)} 个变更文件的引用链...")
    for f in changed_files:
        print(f"  - {f}")
    print()

    report = generate_reference_report(repo_root, changed_files)

    out_dir = os.path.join(repo_root, "evidence", "DeepReview")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "reference_trace.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)

    try:
        print(report)
    except UnicodeEncodeError:
        print(report.encode("utf-8", errors="replace").decode("ascii", errors="replace"))
    print(f"报告已输出到：{out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
