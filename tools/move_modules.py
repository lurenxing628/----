#!/usr/bin/env python3
"""把模块搬到新位置，并一次改写全仓所有引用（导入语句、字符串与注释里的模块点名、路径字面量）。

用法：
  .venv/bin/python -m tools.move_modules plan.json          # 预演：只打印将要改的内容
  .venv/bin/python -m tools.move_modules plan.json --apply  # 真改：git mv + 改写文件 + ruff 排导入

plan.json 形如：
  {"moves": {"core.services.workbench.run_jobs": "core.services.workbench.run.jobs"},
   "globs": {"core/services/workbench/run_*.py": ["core/services/workbench/run/**/*.py"]}}
  globs 可选：注册表等处的 glob 字面量按表原样替换成一串字面量（可含原 glob 本身）。

规则：
- 只搬普通模块（*.py），不搬包目录；目标目录缺 __init__.py 时补一个只有 docstring 的门面。
- 导入改写只动引用了被搬模块的语句（以及被搬文件自己的相对导入）；渲染时同包或子包用相对导入，
  其余用绝对导入，与仓库现有写法一致。
- 模块改名时调用方的本地绑定名保持不变：`from pkg import run_jobs` 变成 `from pkg.run import jobs as run_jobs`。
- 字符串里的模块点名（monkeypatch 目标、importlib）和 `x/y.py` 路径字面量一并改写；含 * 的 glob 按 globs 表替换，
  没列进表又失去覆盖的只报告。
- `import a.b.c`（无 as 别名）引用被搬模块时直接报错，避免漏改属性链。
"""

import argparse
import ast
import io
import json
import re
import subprocess
import sys
import tokenize
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("core", "data", "web", "tests", "tools", "scripts")
SKIP_PARTS = {".venv", "__pycache__", ".git", "node_modules", ".pytest_cache", ".ruff_cache"}
INIT_DOC = '"""按簇分包的门面：只放显式导入，不做懒导出。"""\n'


def iter_python_files() -> Iterable[Path]:
    for path in sorted(ROOT.glob("*.py")):
        yield path
    for name in SCAN_DIRS:
        for path in sorted((ROOT / name).rglob("*.py")):
            if not SKIP_PARTS & set(path.parts):
                yield path


def module_of(path: Path) -> Tuple[str, bool]:
    parts = list(path.resolve().relative_to(ROOT).with_suffix("").parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    return ".".join(parts), is_package


def rel_path(module: str) -> str:
    return module.replace(".", "/") + ".py"


def parent_of(module: str) -> str:
    return module.rpartition(".")[0]


def base_of(module: str) -> str:
    return module.rpartition(".")[2]


class Plan:
    def __init__(self, moves: Dict[str, str], globs: Optional[Dict[str, List[str]]] = None):
        self.moves = dict(moves)
        self.globs = {key: list(value) for key, value in (globs or {}).items()}
        targets = list(self.moves.values())
        problems = []
        for old, new in self.moves.items():
            if old == new:
                problems.append("原地不动：" + old)
            if not (ROOT / rel_path(old)).is_file():
                problems.append("源模块不存在：" + old)
            if (ROOT / rel_path(new)).exists():
                problems.append("目标已存在：" + new)
            if (ROOT / old.replace(".", "/") / "__init__.py").exists():
                problems.append("不支持搬包目录：" + old)
            if targets.count(new) > 1:
                problems.append("目标重复：" + new)
        if problems:
            raise SystemExit("plan 无效：\n  " + "\n  ".join(sorted(set(problems))))

    def new_module(self, module: str) -> Optional[str]:
        return self.moves.get(module)

    def new_packages(self) -> List[str]:
        seen = []
        for new in self.moves.values():
            package = parent_of(new)
            while package and package not in seen and not (ROOT / package.replace(".", "/") / "__init__.py").exists():
                seen.append(package)
                package = parent_of(package)
        return sorted(seen)


def render_from(module: str, package: str) -> str:
    """`from X import` 里的 X：同包写 .、子模块写 .x、子包写 .sub.x，其余绝对。"""
    if module == package:
        return "."
    if package and module.startswith(package + "."):
        return "." + module[len(package) + 1:]
    return module


def render_alias(name: str, asname: Optional[str]) -> str:
    return name if asname in (None, name) else name + " as " + asname


class ImportRewriter:
    def __init__(self, plan: Plan, old_module: str, new_module: str, is_package: bool):
        self.plan = plan
        self.moved = old_module != new_module
        self.old_package = old_module if is_package else parent_of(old_module)
        self.new_package = new_module if is_package else parent_of(new_module)

    def _absolute(self, node: ast.ImportFrom) -> str:
        if node.level == 0:
            return node.module or ""
        package = self.old_package
        for _ in range(node.level - 1):
            package = parent_of(package)
        return package + ("." + node.module if node.module else "")

    def import_from(self, node: ast.ImportFrom) -> Optional[List[str]]:
        absolute = self._absolute(node)
        target = self.plan.new_module(absolute)
        if target is not None:
            names = ", ".join(render_alias(alias.name, alias.asname) for alias in node.names)
            return ["from " + render_from(target, self.new_package) + " import " + names]
        moved_children = {alias.name: self.plan.new_module(absolute + "." + alias.name) for alias in node.names}
        if not any(moved_children.values()) and not (self.moved and node.level > 0):
            return None
        kept, out = [], []
        for alias in node.names:
            child = moved_children[alias.name]
            if child is None:
                kept.append(render_alias(alias.name, alias.asname))
                continue
            local = alias.asname or alias.name
            out.append("from " + render_from(parent_of(child), self.new_package) + " import "
                       + render_alias(base_of(child), local))
        if kept:
            out.insert(0, "from " + render_from(absolute, self.new_package) + " import " + ", ".join(kept))
        return out

    def plain_import(self, node: ast.Import, where: str) -> Optional[List[str]]:
        if not any(self.plan.new_module(alias.name) for alias in node.names):
            return None
        out = []
        for alias in node.names:
            target = self.plan.new_module(alias.name)
            if target is None:
                out.append("import " + render_alias(alias.name, alias.asname))
            elif alias.asname is None:
                raise SystemExit(where + "：`import " + alias.name + "` 没有 as 别名，属性链无法自动改写，请先手工处理")
            else:
                out.append("import " + target + " as " + alias.asname)
        return out


def rewrite_imports(source: str, rewriter: ImportRewriter, where: str) -> Tuple[str, List[str]]:
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    edits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            rendered = rewriter.import_from(node)
        elif isinstance(node, ast.Import):
            rendered = rewriter.plain_import(node, where + ":" + str(node.lineno))
        else:
            continue
        if rendered is None:
            continue
        first, last = lines[node.lineno - 1], lines[node.end_lineno - 1]
        indent = first[:len(first) - len(first.lstrip())]
        tail = last[node.end_col_offset:].strip()
        if tail and not tail.startswith("#"):
            raise SystemExit(where + ":" + str(node.lineno) + "：导入语句后面还有别的代码，请先手工拆开")
        text = "\n".join(indent + line for line in rendered)
        if tail:
            text += "  " + tail
        edits.append((node.lineno, node.end_lineno, text + "\n"))
    notes = []
    for start, end, text in sorted(edits, reverse=True):
        notes.append(where + ":" + str(start) + " " + "".join(lines[start - 1:end]).strip().replace("\n", " ⏎ ")
                     + "  →  " + text.strip().replace("\n", " ⏎ "))
        lines[start - 1:end] = [text]
    return "".join(lines), notes


def _string_spans(source: str) -> List[Tuple[int, int]]:
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    spans = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type in (tokenize.STRING, tokenize.COMMENT):
            spans.append((offsets[token.start[0] - 1] + token.start[1], offsets[token.end[0] - 1] + token.end[1]))
    return spans


def _glob_regex(pattern: str) -> "re.Pattern":
    escaped = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*", "[^/]*")
    return re.compile("^" + escaped + "$")


class StringRewriter:
    def __init__(self, plan: Plan):
        ordered = sorted(plan.moves.items(), key=lambda item: -len(item[0]))
        self.dotted = [(re.compile(r"(?<![\w.])" + re.escape(old) + r"(?!\w)"), new) for old, new in ordered]
        self.paths = [(re.compile(r"(?<![\w/])" + re.escape(rel_path(old)) + r"(?!\w)"), rel_path(new))
                      for old, new in ordered]
        self.moved_paths = {rel_path(old): rel_path(new) for old, new in ordered}
        self.package_dirs = sorted({parent_of(old).replace(".", "/") for old in plan.moves}
                                   | {parent_of(old) for old in plan.moves})
        self.globs = plan.globs

    def apply(self, source: str, where: str) -> Tuple[str, List[str], List[str]]:
        out, notes, warnings, cursor = [], [], [], 0
        for start, end in _string_spans(source):
            text = source[start:end]
            new_text = self._glob_literal(text)
            if new_text is None:
                new_text = text
                for pattern, replacement in self.dotted + self.paths:
                    new_text = pattern.sub(replacement, new_text)
                self._warn(text, where + ":" + str(source.count("\n", 0, start) + 1), warnings)
            if new_text != text:
                notes.append(where + ":" + str(source.count("\n", 0, start) + 1) + " " + text + "  →  " + new_text)
            out.append(source[cursor:start])
            out.append(new_text)
            cursor = end
        out.append(source[cursor:])
        return "".join(out), notes, warnings

    def _glob_literal(self, text: str) -> Optional[str]:
        quote = text[:1]
        if quote not in ("'", '"') or text[-1:] != quote or text[1:-1] not in self.globs:
            return None
        return ", ".join(quote + item + quote for item in self.globs[text[1:-1]])

    def _warn(self, text: str, where: str, warnings: List[str]) -> None:
        body = text.strip("'\"rbfRBF")
        if "*" in body and "/" in body:
            regex = _glob_regex(body)
            lost = [old for old, new in self.moved_paths.items() if regex.match(old) and not regex.match(new)]
            if lost:
                warnings.append(where + " glob " + body + " 搬后不再覆盖：" + ", ".join(sorted(lost)))
        elif body in self.package_dirs:
            warnings.append(where + " 目录字面量 " + body + "：请确认是否按目录遍历模块")


def run(plan: Plan, apply: bool) -> int:
    strings = StringRewriter(plan)
    changed: Dict[Path, str] = {}
    all_notes: List[str] = []
    all_warnings: List[str] = []
    for path in iter_python_files():
        old_module, is_package = module_of(path)
        new_module = plan.new_module(old_module) or old_module
        where = str(path.relative_to(ROOT))
        source = path.read_text(encoding="utf-8")
        text, notes = rewrite_imports(source, ImportRewriter(plan, old_module, new_module, is_package), where)
        text, string_notes, warnings = strings.apply(text, where)
        all_notes.extend(notes + string_notes)
        all_warnings.extend(warnings)
        if text != source:
            changed[path] = text
    for note in all_notes:
        print(note)
    packages = plan.new_packages()
    print(f"\n改写 {len(changed)} 个文件，{len(all_notes)} 处引用；搬 {len(plan.moves)} 个模块，"
          f"新建 {len(packages)} 个包：{', '.join(packages)}")
    if all_warnings:
        print("\n需要人工确认：")
        for warning in all_warnings:
            print("  " + warning)
    if not apply:
        print("\n（预演，未改动任何文件；加 --apply 执行）")
        return 0
    for package in plan.new_packages():
        directory = ROOT / package.replace(".", "/")
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "__init__.py").write_text(INIT_DOC, encoding="utf-8")
        subprocess.run(["git", "add", str(directory / "__init__.py")], cwd=str(ROOT), check=True)
    moved_paths = []
    for old, new in plan.moves.items():
        (ROOT / rel_path(new)).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "mv", rel_path(old), rel_path(new)], cwd=str(ROOT), check=True)
        moved_paths.append(rel_path(new))
    touched = []
    for path, text in changed.items():
        old_module, _ = module_of(path)
        target = plan.new_module(old_module)
        destination = ROOT / rel_path(target) if target else path
        destination.write_text(text, encoding="utf-8")
        touched.append(str(destination.relative_to(ROOT)))
    ruff = subprocess.run([sys.executable, "-m", "ruff", "check", "--fix", "--select", "I", "--quiet"]
                          + sorted(set(touched) | set(moved_paths)), cwd=str(ROOT))
    if ruff.returncode != 0:
        print("ruff 导入排序返回非零，请检查上面的输出")
    print(f"\n已执行：git mv {len(plan.moves)} 个模块，写回 {len(changed)} 个文件")
    return ruff.returncode


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="搬模块并改写全仓引用")
    parser.add_argument("plan", help="JSON 文件，含 moves: {旧模块点名: 新模块点名}")
    parser.add_argument("--apply", action="store_true", help="真正执行 git mv 与改写；默认只预演")
    args = parser.parse_args(argv)
    data = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    return run(Plan(data["moves"], data.get("globs")), args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
