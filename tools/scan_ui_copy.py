#!/usr/bin/env python3
"""扫描工作台用户可见文案里的内部词、英文单位和纯英文提示。

词表来源：tools/ui_copy_glossary.json（决策见 .codestable/compound/2026-09-13-decision-ui-copy-glossary.md）。

用法：
  python3 -m tools.scan_ui_copy                  # 明细 + 按词统计，有残留则退出码 1
  python3 -m tools.scan_ui_copy --summary        # 只看统计
  python3 -m tools.scan_ui_copy --paths frontend/workbench/app/Run core/services/workbench/run_
  python3 -m tools.scan_ui_copy --json           # 机器可读输出

扫描范围（按词表 scan 段）：
  frontend：.js/.jsx 里的字符串字面量与 JSX 文本（去掉注释）
  templates：模板文本行（去掉 Jinja 注释）
  backend：Python 字符串常量（去掉 docstring、assert、日志调用与开发者异常的参数）
  docs：页内说明书 Markdown 行
"""
import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLOSSARY_PATH = ROOT / "tools" / "ui_copy_glossary.json"
CJK = re.compile(r"[一-鿿]")
JS_STRING = re.compile(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"")
JS_TEMPLATE = re.compile(r"`((?:[^`\\]|\\.)*)`")
JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.S)
SQL_START = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|PRAGMA|WITH|ALTER|DROP|BEGIN|COMMIT)\b", re.I)
ENGLISH_SENTENCE = re.compile(r"^[A-Z][^一-鿿]*\.$")
DEV_CALLS = {
    "ValueError", "TypeError", "RuntimeError", "AssertionError", "KeyError", "NotImplementedError",
    "AttributeError", "LookupError", "info", "debug", "warning", "error", "exception", "critical", "log",
}


class Rule:
    def __init__(self, item, kind):
        self.term = item["term"]
        self.pattern = re.compile(item["pattern"])
        self.replace = item.get("replace", "")
        self.scope = item.get("scope", "cjk")
        self.kinds = set(item.get("kinds", ("frontend", "templates", "backend", "docs")))
        self.kind = kind


def load_glossary(path=GLOSSARY_PATH):
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = [Rule(item, "banned") for item in data["banned"]] + [Rule(item, "unit") for item in data["units"]]
    allow = [(item["path"], item.get("term"), re.compile(item["text"]) if item.get("text") else None)
             for item in data.get("allow", [])]
    return data["scan"], rules, allow


def strip_js_comments(source):
    out = []
    i = 0
    n = len(source)
    quote = None
    while i < n:
        char = source[i]
        if quote:
            out.append(char)
            if char == "\\" and i + 1 < n:
                out.append(source[i + 1])
                i += 2
                continue
            if char == quote or (char == "\n" and quote != "`"):
                quote = None
            i += 1
            continue
        if char in "'\"`":
            quote = char
            out.append(char)
            i += 1
            continue
        if char == "/" and i + 1 < n and source[i + 1] == "/":
            end = source.find("\n", i)
            if end < 0:
                break
            i = end
            continue
        if char == "/" and i + 1 < n and source[i + 1] == "*":
            end = source.find("*/", i + 2)
            if end < 0:
                break
            out.append("\n" * source.count("\n", i, end + 2))
            i = end + 2
            continue
        out.append(char)
        i += 1
    return "".join(out)


def frontend_texts(path):
    source = strip_js_comments(path.read_text(encoding="utf-8"))
    for match in JS_TEMPLATE.finditer(source):
        line = source.count("\n", 0, match.start()) + 1
        yield line, match.group(1)
    for number, line in enumerate(source.split("\n"), 1):
        for match in JS_STRING.finditer(line):
            yield number, match.group(1) if match.group(1) is not None else match.group(2)
        rest = JS_STRING.sub(" ", line)
        for segment in re.split(r"[<>{}]", rest):
            if CJK.search(segment):
                yield number, segment.strip()


def python_texts(path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                skip.add(id(body[0].value))
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
            if name in DEV_CALLS:
                for arg in node.args:
                    skip.update(id(sub) for sub in ast.walk(arg))
            for keyword in node.keywords:
                if keyword.arg and "log" in keyword.arg.lower():
                    skip.update(id(sub) for sub in ast.walk(keyword.value))
        elif isinstance(node, ast.Assert):
            skip.update(id(sub) for sub in ast.walk(node))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            text = node.value
            if SQL_START.match(text):
                continue
            yield node.lineno, text


def line_texts(path, strip_jinja=False):
    source = path.read_text(encoding="utf-8")
    if strip_jinja:
        source = JINJA_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), source)
    for number, line in enumerate(source.split("\n"), 1):
        if CJK.search(line):
            yield number, line.strip()


def iter_files(root_paths, suffixes):
    for entry in root_paths:
        if "*" in entry:
            for child in sorted(ROOT.glob(entry)):
                if child.is_file() and child.suffix in suffixes:
                    yield child
            continue
        path = ROOT / entry
        if path.is_file():
            yield path
            continue
        for child in sorted(path.rglob("*")):
            if child.is_file() and child.suffix in suffixes:
                yield child


def collect(scan, rules, allow, prefixes=None):
    sources = (
        ("frontend", iter_files(scan["frontend"], {".js", ".jsx"}), frontend_texts),
        ("templates", iter_files(scan["templates"], {".html"}), lambda p: line_texts(p, strip_jinja=True)),
        ("backend", iter_files(scan["backend"], {".py"}), python_texts),
        ("docs", iter_files(scan["docs"], {".md"}), line_texts),
    )
    hits = []
    for kind, files, extractor in sources:
        for path in files:
            rel = path.relative_to(ROOT).as_posix()
            if prefixes and not any(rel.startswith(prefix) for prefix in prefixes):
                continue
            for line, text in extractor(path):
                if not text:
                    continue
                has_cjk = bool(CJK.search(text))
                for rule in rules:
                    if kind not in rule.kinds or (rule.scope == "cjk" and not has_cjk):
                        continue
                    if not rule.pattern.search(text):
                        continue
                    if any(rel.startswith(prefix) and (term is None or term == rule.term)
                           and (pattern is None or pattern.search(text)) for prefix, term, pattern in allow):
                        continue
                    hits.append({"file": rel, "line": line, "kind": rule.kind, "term": rule.term,
                                 "replace": rule.replace, "text": text.strip()[:160]})
                if kind == "backend" and not has_cjk and ENGLISH_SENTENCE.match(text.strip()) \
                        and len(text.split()) >= 3:
                    if any(rel.startswith(prefix) and term in (None, "英文提示")
                           and (pattern is None or pattern.search(text)) for prefix, term, pattern in allow):
                        continue
                    hits.append({"file": rel, "line": line, "kind": "english", "term": "英文提示",
                                 "replace": "改成中文", "text": text.strip()[:160]})
    return hits


def summarize(hits):
    by_term = {}
    by_file = {}
    for hit in hits:
        by_term[hit["term"]] = by_term.get(hit["term"], 0) + 1
        by_file[hit["file"]] = by_file.get(hit["file"], 0) + 1
    return by_term, by_file


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--paths", nargs="*", default=None, help="只扫这些仓库相对路径前缀")
    parser.add_argument("--summary", action="store_true", help="只输出统计")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--glossary", default=str(GLOSSARY_PATH))
    args = parser.parse_args(argv)
    scan, rules, allow = load_glossary(Path(args.glossary))
    hits = collect(scan, rules, allow, args.paths)
    by_term, by_file = summarize(hits)
    if args.json:
        json.dump({"hits": hits, "by_term": by_term, "by_file": by_file}, sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    else:
        if not args.summary:
            for hit in hits:
                sys.stdout.write(f'{hit["file"]}:{hit["line"]} [{hit["kind"]}] {hit["term"]} → {hit["replace"]} | {hit["text"]}\n')
        sys.stdout.write(f"按词统计（共 {len(hits)} 处，{len(by_file)} 个文件）：\n")
        for term, count in sorted(by_term.items(), key=lambda item: -item[1]):
            sys.stdout.write(f"  {term:<8} {count}\n")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
