from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


def classify(tree: ast.AST) -> List[Tuple[ast.AST, str]]:
    out: List[Tuple[ast.AST, str]] = []
    for statement in tree.body:  # type: ignore[attr-defined]
        _classify_statement(statement, "hard", out)
    return out


def _classify_statement(statement: ast.AST, context: str, out: List[Tuple[ast.AST, str]]) -> None:
    if isinstance(statement, (ast.Import, ast.ImportFrom)):
        out.append((statement, context))
        return
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
        _classify_body(statement.body, "lazy", out)
        return
    if isinstance(statement, ast.ClassDef):
        _classify_body(statement.body, context, out)
        return
    if isinstance(statement, ast.If):
        _classify_if(statement, context, out)
        return
    if isinstance(statement, ast.Try):
        _classify_try(statement, context, out)
        return
    if isinstance(statement, ast.With):
        _classify_body(statement.body, context, out)


def _classify_body(statements: List[ast.AST], context: str, out: List[Tuple[ast.AST, str]]) -> None:
    for statement in statements:
        _classify_statement(statement, context, out)


def _is_type_checking_test(test: ast.AST) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _classify_if(statement: ast.If, context: str, out: List[Tuple[ast.AST, str]]) -> None:
    if _is_type_checking_test(statement.test):
        _classify_body(statement.body, "typeonly", out)
        _classify_body(statement.orelse, context, out)
        return
    _classify_body(statement.body, "cond", out)
    _classify_body(statement.orelse, "cond", out)


def _classify_try(statement: ast.Try, context: str, out: List[Tuple[ast.AST, str]]) -> None:
    _classify_body(statement.body, "cond", out)
    for handler in statement.handlers:
        _classify_body(handler.body, "cond", out)
    _classify_body(statement.orelse, "cond", out)
    _classify_body(statement.finalbody, context, out)


def dyn_imports(tree: ast.AST) -> List[Tuple[str, bool, int]]:
    res: List[Tuple[str, bool, int]] = []
    _collect_dynamic_imports(tree, False, res)
    return res


def _collect_dynamic_imports(node: ast.AST, in_function: bool, res: List[Tuple[str, bool, int]]) -> None:
    for child in ast.iter_child_nodes(node):
        child_in_function = in_function or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        if isinstance(child, ast.Call):
            _record_dynamic_import(child, child_in_function, res)
        _collect_dynamic_imports(child, child_in_function, res)


def _record_dynamic_import(call: ast.Call, in_function: bool, res: List[Tuple[str, bool, int]]) -> None:
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else None)
    if name != "import_module" or not call.args:
        return
    first_arg = call.args[0]
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        res.append((first_arg.value, in_function, call.lineno))


def resolve_targets(node: ast.AST, pkg: List[str], mod_to_file: Dict[str, str]) -> List[str]:
    if isinstance(node, ast.ImportFrom):
        return _import_from_targets(node, pkg, mod_to_file)
    return _direct_import_targets(node, mod_to_file)


def _resolve_rel(pkg: List[str], level: int, module: Optional[str]) -> str:
    base = pkg[: len(pkg) - (level - 1)]
    return ".".join(base + module.split(".")) if module else ".".join(base)


def _import_from_base(node: ast.ImportFrom, pkg: List[str]) -> Optional[str]:
    return _resolve_rel(pkg, node.level, node.module) if (node.level and node.level > 0) else node.module


def _import_from_targets(node: ast.ImportFrom, pkg: List[str], mod_to_file: Dict[str, str]) -> List[str]:
    base = _import_from_base(node, pkg)
    if not base:
        return []
    names = [alias.name for alias in node.names]
    targets = [base + "." + name for name in names if (base + "." + name) in mod_to_file]
    if base in mod_to_file and not _all_names_are_child_modules(base, names, mod_to_file):
        targets.append(base)
    return targets


def _all_names_are_child_modules(base: str, names: List[str], mod_to_file: Dict[str, str]) -> bool:
    return bool(names) and all((base + "." + name) in mod_to_file for name in names)


def _direct_import_targets(node: ast.AST, mod_to_file: Dict[str, str]) -> List[str]:
    if not isinstance(node, ast.Import):
        return []
    return [alias.name for alias in node.names if alias.name in mod_to_file]


@dataclass
class _TarjanState:
    graph: Dict[str, List[str]]
    index: Dict[str, int] = field(default_factory=dict)
    low: Dict[str, int] = field(default_factory=dict)
    on_stack: Dict[str, bool] = field(default_factory=dict)
    stack: List[str] = field(default_factory=list)
    components: List[List[str]] = field(default_factory=list)
    counter: int = 0

    def nodes(self) -> List[str]:
        all_nodes = set(self.graph) | {target for targets in self.graph.values() for target in targets}
        return list(all_nodes)


def tarjan(graph: Dict[str, List[str]]) -> List[List[str]]:
    state = _TarjanState(graph=graph)
    for node in state.nodes():
        if node not in state.index:
            _strongconnect_iterative(state, node)
    return state.components


def _strongconnect_iterative(state: _TarjanState, root: str) -> None:
    work: List[Tuple[str, int]] = [(root, 0)]
    while work:
        node, next_index = work[-1]
        if node not in state.index:
            _visit_node(state, node)
        child, updated_index = _next_unvisited_child(state, node, next_index)
        if child is not None:
            work[-1] = (node, updated_index)
            work.append((child, 0))
            continue
        _finish_node(state, node)
        work.pop()
        if work:
            parent = work[-1][0]
            state.low[parent] = min(state.low[parent], state.low[node])


def _visit_node(state: _TarjanState, node: str) -> None:
    state.index[node] = state.low[node] = state.counter
    state.counter += 1
    state.stack.append(node)
    state.on_stack[node] = True


def _next_unvisited_child(state: _TarjanState, node: str, start_index: int) -> Tuple[Optional[str], int]:
    neighbors = state.graph.get(node, ())
    index = start_index
    while index < len(neighbors):
        child = neighbors[index]
        if child not in state.index:
            return child, index + 1
        if state.on_stack.get(child):
            state.low[node] = min(state.low[node], state.index[child])
        index += 1
    return None, index


def _finish_node(state: _TarjanState, node: str) -> None:
    if state.low[node] != state.index[node]:
        return
    component: List[str] = []
    while state.stack:
        member = state.stack.pop()
        state.on_stack[member] = False
        component.append(member)
        if member == node:
            break
    if len(component) > 1:
        state.components.append(component)
