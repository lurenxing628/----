#!/usr/bin/env python3
"""零依赖 AST 测试体检扫描器(唯一真相源)。

只读分析 tests/ 下真实测试文件,输出每个测试函数/文件的可疑信号,
用于人工判断哪些测试"无意义"或"大量重合"。不导入、不运行任何测试。

借鉴: falsegreen / exspec / pytest-review / testless 的静态启发式 +
学术界 test-suite-minimization 的"结构等价 -> 冗余"思路。

输出 JSON 到 out/ 目录;不修改任何被扫描文件。
"""
import ast
import hashlib
import json
import os
import re
import sys
from collections import defaultdict

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
TESTS_DIR = os.path.join(ROOT, "tests")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT_DIR, exist_ok=True)

# 排除非测试/辅助目录
EXCLUDE_PARTS = {"_support", "_scripts_e2e", "_data", "__pycache__"}

# 断言名启发式: 调用名命中即视为"委托断言"(项目自定义 helper)
ASSERT_NAME_RE = re.compile(r"(?:^|_)(assert|expect|verify|ensure|check|require|must)(?:_|$)", re.I)
# 隔离/打桩调用
MOCK_ATTRS = {"setattr", "setitem", "setenv", "delattr", "delitem", "delenv"}


def is_test_func(name):
    return name.startswith("test_") or name == "test"


def iter_test_funcs(tree):
    """产出 (func_node, class_name_or_None)。"""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and is_test_func(node.name):
            yield node, None
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and is_test_func(sub.name):
                    yield sub, node.name


def strip_docstring(body):
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def call_name(node):
    """取 Call 的可读名: foo / obj.bar -> 'foo' / 'bar'(末段)。"""
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def full_attr_chain(node):
    """obj.attr.attr -> 'obj.attr.attr'(尽量)。"""
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


class FuncAnalysis:
    __slots__ = ("asserts", "raises", "raise_stmt", "delegated_assert", "mock_calls", "mock_targets",
                 "calls", "stmt_count", "has_pass_only", "skip", "trivial_assert", "called_local")

    def __init__(self):
        self.asserts = 0
        self.raises = 0
        self.raise_stmt = 0       # raise RuntimeError(...) 等,测试里等价于断言失败
        self.delegated_assert = 0
        self.mock_calls = 0
        self.mock_targets = []
        self.calls = 0
        self.stmt_count = 0
        self.has_pass_only = False
        self.skip = False
        self.trivial_assert = 0
        self.called_local = set()  # 本函数直接调用的"裸函数名"(可能是同文件 helper)

    def self_signal(self):
        return self.asserts + self.raises + self.raise_stmt + self.delegated_assert


def _const_truthy(node):
    """判断 assert 的测试表达式是否平凡为真(assert True / assert 1 / assert 'x' / x==x)。"""
    t = node.test
    if isinstance(t, ast.Constant):
        return True  # assert <常量>
    if isinstance(t, ast.Compare) and len(t.ops) == 1:
        left, right = t.left, t.comparators[0]
        try:
            if ast.dump(left) == ast.dump(right):
                return True  # assert x == x 之类
        except Exception:
            pass
    return False


def analyze_func(func):
    a = FuncAnalysis()
    body = strip_docstring(func.body)
    # 仅 pass / ... 的空体
    if all(isinstance(s, ast.Pass) or (isinstance(s, ast.Expr) and isinstance(getattr(s, "value", None), ast.Constant)
                                       and s.value.value is Ellipsis) for s in body) and body:
        a.has_pass_only = True
    if not body:
        a.has_pass_only = True
    a.stmt_count = len(body)

    # 装饰器里的 skip/xfail
    for dec in func.decorator_list:
        src = ast.dump(dec)
        if "skip" in src or "xfail" in src:
            a.skip = True

    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            a.asserts += 1
            if _const_truthy(node):
                a.trivial_assert += 1
        elif isinstance(node, ast.Raise):
            if node.exc is not None:        # raise X(...) 在测试里等价断言失败;裸 raise 重抛不算
                a.raise_stmt += 1
        elif isinstance(node, ast.Call):
            a.calls += 1
            if isinstance(node.func, ast.Name):
                a.called_local.add(node.func.id)   # 可能是同文件 helper,后面做闭包
            cn = call_name(node)
            if cn:
                # pytest.raises / warns / self.assertXxx / fail
                if cn in ("raises", "warns") or cn.startswith("assert") or cn == "fail":
                    a.raises += 1
                elif ASSERT_NAME_RE.search(cn):
                    a.delegated_assert += 1
                # monkeypatch.setattr 等
                if isinstance(node.func, ast.Attribute) and cn in MOCK_ATTRS:
                    a.mock_calls += 1
                    if node.args:
                        tgt = node.args[0]
                        if isinstance(tgt, (ast.Attribute, ast.Name)):
                            a.mock_targets.append(full_attr_chain(tgt))
                        elif isinstance(tgt, ast.Constant) and isinstance(tgt.value, str):
                            a.mock_targets.append(tgt.value)
                if cn in ("Mock", "MagicMock", "patch", "create_autospec", "AsyncMock"):
                    a.mock_calls += 1
        elif isinstance(node, ast.With):
            # with pytest.raises(...) 已在 Call 里计数;此处不重复
            pass
    return a


def skeleton(node):
    """生成归一化结构签名: 变量名/常量归一,保留方法名与控制流 -> 近似重复聚类。"""
    out = []

    def rec(n):
        if isinstance(n, ast.Name):
            out.append("N")
            return
        if isinstance(n, ast.Constant):
            out.append("C")
            return
        if isinstance(n, ast.arg):
            out.append("a")
            return
        out.append(type(n).__name__)
        if isinstance(n, ast.Attribute):
            out.append("." + n.attr)
        if isinstance(n, ast.keyword) and n.arg:
            out.append("=" + n.arg)
        for child in ast.iter_child_nodes(n):
            rec(child)
        out.append("/")

    for s in node:
        rec(s)
    return "".join(out)


def exact_dump(body):
    return "|".join(ast.dump(s, include_attributes=False) for s in body)


def effective_body(func, local_nodes):
    """重复检测用的有效体: test 体仅单行委托本地 helper 时,展开成 helper 体。

    项目大量用 `def test_x(mp): main(mp)` 双层结构,直接哈希委托行会让
    完全不同的 test 误判为重复。展开一层即可消除该假阳性。
    """
    body = strip_docstring(func.body)
    if len(body) == 1:
        s = body[0]
        cn = None
        if isinstance(s, ast.Expr) and isinstance(getattr(s, "value", None), ast.Call):
            cn = s.value
        elif isinstance(s, ast.Return) and isinstance(getattr(s, "value", None), ast.Call):
            cn = s.value
        if cn is not None and isinstance(cn.func, ast.Name):
            tgt = local_nodes.get(cn.func.id)
            if tgt is not None and tgt is not func:
                return strip_docstring(tgt.body)
    return body


def module_imports(tree):
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top in ("core", "web", "tools", "desktop", "app", "scripts"):
                mods.add(node.module)
        elif isinstance(node, ast.Import):
            for n in node.names:
                top = n.name.split(".")[0]
                if top in ("core", "web", "tools", "desktop", "app", "scripts"):
                    mods.add(n.name)
    return sorted(mods)


def main():
    files = []
    for dirpath, _dirnames, filenames in os.walk(TESTS_DIR):
        parts = set(dirpath.split(os.sep))
        if parts & EXCLUDE_PARTS:
            continue
        for fn in filenames:
            if fn.startswith("test_") and fn.endswith(".py"):
                files.append(os.path.join(dirpath, fn))
    files.sort()

    per_file = {}
    exact_groups = defaultdict(list)   # hash -> [func_id]
    skel_groups = defaultdict(list)
    func_index = {}                    # func_id -> meta
    module_to_files = defaultdict(set)
    parse_errors = []

    for path in files:
        rel = os.path.relpath(path, ROOT)
        try:
            with open(path, encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src)
        except Exception as e:
            parse_errors.append({"file": rel, "error": str(e)})
            continue

        lines = src.count("\n") + 1
        mods = module_imports(tree)
        for m in mods:
            module_to_files[m].add(rel)

        finfo = {
            "file": rel,
            "dir": os.path.relpath(os.path.dirname(path), TESTS_DIR),
            "lines": lines,
            "modules": mods,
            "n_tests": 0,
            "assertion_free": [],
            "trivial_assert": [],
            "empty_body": [],
            "skipped": [],
            "mock_heavy_noassert": [],
            "tot_assert": 0,
            "tot_raises": 0,
            "tot_mock": 0,
        }

        # 文件内所有顶层函数(含 helper)的分析,供断言/打桩调用闭包跟进
        local_funcs = {}
        local_func_nodes = {}
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_funcs[n.name] = analyze_func(n)
                local_func_nodes[n.name] = n

        def closure(a, local_funcs=local_funcs):
            """沿 test 调用的本地 helper 累加断言/打桩信号,消除双层结构假阳性。"""
            seen = set()
            stack = list(a.called_local)
            sig = a.self_signal()
            mock = a.mock_calls
            while stack:
                nm = stack.pop()
                if nm in seen:
                    continue
                seen.add(nm)
                h = local_funcs.get(nm)
                if h is None:
                    continue
                sig += h.self_signal()
                mock += h.mock_calls
                stack.extend(h.called_local - seen)
            return sig, mock

        for func, cls in iter_test_funcs(tree):
            finfo["n_tests"] += 1
            a = analyze_func(func)
            fid = "{}::{}{}".format(rel, (cls + "." if cls else ""), func.name)
            line = func.lineno
            func_index[fid] = {"file": rel, "line": line, "name": func.name, "class": cls}

            assert_sig, mock_sig = closure(a)

            finfo["tot_assert"] += a.asserts
            finfo["tot_raises"] += a.raises + a.raise_stmt
            finfo["tot_mock"] += mock_sig

            if a.skip:
                finfo["skipped"].append({"id": fid, "line": line})
            if a.has_pass_only:
                finfo["empty_body"].append({"id": fid, "line": line})
            elif assert_sig == 0:
                finfo["assertion_free"].append({
                    "id": fid, "line": line, "stmts": a.stmt_count,
                    "calls": a.calls, "mock": mock_sig,
                })
            if a.trivial_assert and a.asserts == a.trivial_assert and a.raises == 0 \
                    and a.raise_stmt == 0 and a.delegated_assert == 0:
                finfo["trivial_assert"].append({"id": fid, "line": line, "n": a.trivial_assert})
            if mock_sig >= 3 and assert_sig == 0 and not a.has_pass_only:
                finfo["mock_heavy_noassert"].append({
                    "id": fid, "line": line, "mock": mock_sig,
                    "targets": a.mock_targets[:8],
                })

            # 重复检测;单行委托本地 helper 的 test 展开成 helper 体,避免委托行假性重复
            body = effective_body(func, local_func_nodes)
            if body and not a.has_pass_only:
                try:
                    eh = hashlib.md5(exact_dump(body).encode("utf-8")).hexdigest()
                    sh = hashlib.md5(skeleton(body).encode("utf-8")).hexdigest()
                    exact_groups[eh].append(fid)
                    skel_groups[sh].append((fid, a.stmt_count))
                except Exception:
                    pass

        per_file[rel] = finfo

    # 整理重复组(>=2 才算)
    exact_dups = []
    for h, ids in exact_groups.items():
        if len(ids) >= 2:
            exact_dups.append({"hash": h, "count": len(ids), "members": ids})
    exact_dups.sort(key=lambda x: -x["count"])

    skel_dups = []
    for h, items in skel_groups.items():
        if len(items) >= 2:
            stmts = items[0][1]
            if stmts < 3:   # 跳过过短(易误报)
                continue
            skel_dups.append({"hash": h, "count": len(items), "stmts": stmts,
                              "members": [i[0] for i in items]})
    skel_dups.sort(key=lambda x: (-x["count"], -x["stmts"]))

    # 模块测试集中度
    mod_conc = [{"module": m, "n_files": len(fs), "files": sorted(fs)}
                for m, fs in module_to_files.items() if len(fs) >= 4]
    mod_conc.sort(key=lambda x: -x["n_files"])

    # 汇总计数
    def count(field):
        return sum(len(v[field]) for v in per_file.values())

    summary = {
        "n_files": len(per_file),
        "n_tests": sum(v["n_tests"] for v in per_file.values()),
        "total_lines": sum(v["lines"] for v in per_file.values()),
        "assertion_free_funcs": count("assertion_free"),
        "empty_body_funcs": count("empty_body"),
        "trivial_assert_funcs": count("trivial_assert"),
        "skipped_funcs": count("skipped"),
        "mock_heavy_noassert_funcs": count("mock_heavy_noassert"),
        "exact_duplicate_groups": len(exact_dups),
        "exact_duplicate_funcs": sum(d["count"] for d in exact_dups),
        "skeleton_duplicate_groups": len(skel_dups),
        "skeleton_duplicate_funcs": sum(d["count"] for d in skel_dups),
        "parse_errors": len(parse_errors),
    }

    with open(os.path.join(OUT_DIR, "per_file.json"), "w", encoding="utf-8") as f:
        json.dump(per_file, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT_DIR, "func_index.json"), "w", encoding="utf-8") as f:
        json.dump(func_index, f, ensure_ascii=False)
    with open(os.path.join(OUT_DIR, "findings.json"), "w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            "exact_duplicates": exact_dups,
            "skeleton_duplicates": skel_dups[:200],
            "module_concentration": mod_conc,
            "parse_errors": parse_errors,
            "func_index_size": len(func_index),
        }, f, ensure_ascii=False, indent=1)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n=== 模块测试集中度 TOP15 (被>=4个测试文件 import) ===")
    for m in mod_conc[:15]:
        print(f"  {m['n_files']:3d}  {m['module']}")
    print("\n=== 完全重复测试组 TOP10 ===")
    for d in exact_dups[:10]:
        print(f"  x{d['count']}  {d['members'][0]}")
        for mem in d["members"][1:]:
            print(f"        = {mem}")


if __name__ == "__main__":
    main()
