#!/usr/bin/env python3
"""callgraph_extract 的类型感知 attr 消解 leaf helper(拆出以免主文件触 500 行门禁)。

复用主扫描已解析的函数 AST(all_funcs[*]["node"])与类继承信息,做保守的"变量->类"推断,
把 recv.method() 定位到唯一真实方法(含沿基类查找)。对外只暴露 resolve_all():
返回可转实线的 typed 边集 + 整组已定位的 (函数,方法名)->真目标 映射(供主扫描删假候选)。

纯标准库、Py3.8、只读 AST 无副作用。保守优先:推不准就不动,宁可少消解也不画错边。
"""
from __future__ import annotations

import ast
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

_STR_ANN = re.compile(r"([A-Za-z_][\w.]*)")
_OPTIONAL = re.compile(r"^Optional\[(.+)\]$")

# all_funcs[qual] = {"rel","line","end","cls","name","node",...};  class_bases = [(rel, clsname, [base简名])]
ClassBases = List[Tuple[str, str, List[str]]]


class TypeIndex:
    """全项目类/方法/返回类型登记册。跨文件同名类视为不可判,保守跳过。"""

    def __init__(self) -> None:
        self.class_defs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.func_return: Dict[str, Optional[str]] = {}
        self.name_to_quals: Dict[str, List[str]] = defaultdict(list)
        self.local_funcs: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

    def class_info(self, name: Optional[str]) -> Optional[Dict[str, Any]]:
        infos = self.class_defs.get(name or "")
        return infos[0] if infos and len(infos) == 1 else None

    def resolve_method(self, class_name: Optional[str], method: str, depth: int = 0) -> Optional[str]:
        if depth > 5:
            return None
        info = self.class_info(class_name)
        if info is None:
            return None
        if method in info["methods"]:
            return f"{info['rel']}::{class_name}.{method}"
        for base in info["bases"]:
            found = self.resolve_method(base, method, depth + 1)
            if found:
                return found
        return None


def _parse_str_ann(text: str) -> Optional[str]:
    text = text.strip()
    matched = _OPTIONAL.match(text)
    if matched:
        text = matched.group(1).strip()
    found = _STR_ANN.match(text)
    return found.group(1).split(".")[-1] if found else None


def _ann_class_name(node: Optional[ast.AST]) -> Optional[str]:
    """从注解 AST 抽出核心类简名;只认 Name/Attribute/Optional[...]/字符串注解,List[X] 等放弃。"""
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _parse_str_ann(node.value)
    if isinstance(node, ast.Subscript):
        base = node.value
        base_name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
        if base_name == "Optional":
            sliced = node.slice
            inner = sliced.value if isinstance(sliced, ast.Index) else sliced  # py3.8 ast.Index
            return _ann_class_name(inner)
        return None
    return None


def build_index(all_funcs: Dict[str, Dict[str, Any]], class_bases: ClassBases) -> TypeIndex:
    index = TypeIndex()
    methods_by: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    for qual, info in all_funcs.items():
        name, cls, rel = info["name"], info["cls"], info["rel"]
        index.name_to_quals[name].append(qual)
        index.func_return[qual] = _ann_class_name(getattr(info["node"], "returns", None))
        if cls is None:
            index.local_funcs[rel][name].append(qual)
        else:
            methods_by[(rel, cls)].add(name)
    for rel, clsname, bases in class_bases:
        index.class_defs[clsname].append({"rel": rel, "methods": methods_by.get((rel, clsname), set()), "bases": bases})
    return index


def _value_type(value: ast.AST, rel: str, index: TypeIndex) -> Optional[str]:
    """赋值右值若是 `Class(...)`(构造)或 `f(...)`(f 有唯一返回注解)则推出实例类型。"""
    if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name):
        return None
    name = value.func.id
    if index.class_info(name) is not None:
        return name
    quals = index.local_funcs[rel].get(name) or index.name_to_quals.get(name)
    if quals and len(quals) == 1:
        return index.func_return.get(quals[0])
    return None


def _infer_var_types(fnode: ast.AST, cls: Optional[str], rel: str, index: TypeIndex) -> Dict[str, str]:
    candidates: Dict[str, Set[str]] = defaultdict(set)

    def remember(var: str, cname: Optional[str]) -> None:
        if cname:
            candidates[var].add(cname)

    if cls:
        remember("self", cls)
    args = fnode.args  # type: ignore[attr-defined]
    for arg in list(getattr(args, "posonlyargs", [])) + list(args.args) + list(args.kwonlyargs):
        remember(arg.arg, _ann_class_name(arg.annotation))
    for node in ast.walk(fnode):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            remember(node.target.id, _ann_class_name(node.annotation))
        elif isinstance(node, ast.Assign):
            cname = _value_type(node.value, rel, index)
            if cname:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        remember(target.id, cname)
    return {var: next(iter(types)) for var, types in candidates.items() if len(types) == 1}


def _resolve_attr_calls(fnode: ast.AST, var_types: Dict[str, str], from_qual: str,
                        index: TypeIndex) -> Dict[str, Tuple[Set[str], int, int]]:
    """方法名 -> (定位到的真目标集, 该方法名的 attr 调用点总数, 其中类型可定位的调用点数)。

    total 计入【全部】attr 调用点(含 self.x.m() / f().m() 等复杂接收者),只有 total==resolved
    才算整组已定位、可安全删假候选——否则复杂接收者那条真候选会被误删。
    """
    out: Dict[str, Tuple[Set[str], int, int]] = {}
    for node in ast.walk(fnode):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        method = node.func.attr
        targets, total, resolved = out.get(method, (set(), 0, 0))
        total += 1
        recv = node.func.value
        if isinstance(recv, ast.Name):
            cname = var_types.get(recv.id)
            if cname:
                target = index.resolve_method(cname, method)
                if target and target != from_qual:
                    targets = targets | {target}
                    resolved += 1
        out[method] = (targets, total, resolved)
    return out


def resolve_all(all_funcs: Dict[str, Dict[str, Any]],
                class_bases: ClassBases) -> Tuple[Set[Tuple[str, str]], Dict[Tuple[str, str], Set[str]]]:
    """主入口:返回 (typed 确信边集合, 整组已定位的 (from_qual, 方法名)->真目标集)。"""
    index = build_index(all_funcs, class_bases)
    typed: Set[Tuple[str, str]] = set()
    fully: Dict[Tuple[str, str], Set[str]] = {}
    for qual, info in all_funcs.items():
        var_types = _infer_var_types(info["node"], info["cls"], info["rel"], index)
        if not var_types:
            continue
        for method, (targets, total, resolved) in _resolve_attr_calls(info["node"], var_types, qual, index).items():
            for target in targets:
                typed.add((qual, target))
            if targets and total == resolved:
                fully[(qual, method)] = set(targets)
    return typed, fully
