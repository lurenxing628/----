from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple


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
        _classify_body(statement.body, "typeonly" if context == "typeonly" else "lazy", out)
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
    if isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
        _classify_body(statement.body, context, out)
        _classify_body(statement.orelse, context, out)
        return
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        _classify_body(statement.body, context, out)


def _classify_body(statements: Sequence[ast.AST], context: str, out: List[Tuple[ast.AST, str]]) -> None:
    for statement in statements:
        _classify_statement(statement, context, out)


def _is_type_checking_test(test: ast.AST) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _conditional_context(context: str) -> str:
    return context if context in ("lazy", "typeonly") else "cond"


def _classify_if(statement: ast.If, context: str, out: List[Tuple[ast.AST, str]]) -> None:
    if _is_type_checking_test(statement.test):
        _classify_body(statement.body, "typeonly", out)
        _classify_body(statement.orelse, context, out)
        return
    branch_context = _conditional_context(context)
    _classify_body(statement.body, branch_context, out)
    _classify_body(statement.orelse, branch_context, out)


def _classify_try(statement: ast.Try, context: str, out: List[Tuple[ast.AST, str]]) -> None:
    branch_context = _conditional_context(context)
    _classify_body(statement.body, branch_context, out)
    for handler in statement.handlers:
        _classify_body(handler.body, branch_context, out)
    _classify_body(statement.orelse, branch_context, out)
    _classify_body(statement.finalbody, context, out)


ResolvedDynamicImport = Tuple[str, Optional[str], str, int]
UnresolvedDynamicImport = Tuple[str, int, str]
LoaderCandidates = Dict[str, Set[str]]
LoaderScope = Tuple[Set[str], LoaderCandidates, Dict[str, str]]


def _bound_names(target: ast.AST) -> Set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Starred):
        return _bound_names(target.value)
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(_bound_names(item) for item in target.elts)) if target.elts else set()
    return set()


def _loader_import_bindings(node: ast.AST) -> List[Tuple[str, Optional[str]]]:
    rows: List[Tuple[str, Optional[str]]] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            bound = alias.asname or alias.name.split(".")[0]
            kind = None
            if alias.name == "importlib":
                kind = "importlib"
            elif alias.name == "importlib.util":
                kind = "importlib.util" if alias.asname else "importlib"
            elif alias.name.startswith("importlib.") and alias.asname is None:
                kind = "importlib"
            rows.append((bound, kind))
    elif isinstance(node, ast.ImportFrom):
        module = str(node.module or "")
        kinds = {
            ("importlib", "import_module"): "import_module",
            ("importlib", "util"): "importlib.util",
            ("importlib.util", "spec_from_file_location"): "spec_from_file_location",
        }
        for alias in node.names:
            if alias.name != "*":
                rows.append((alias.asname or alias.name, kinds.get((module, alias.name))))
    return rows


def _scope_nodes(scope: ast.AST) -> List[ast.AST]:
    roots = [scope.body] if isinstance(scope, ast.Lambda) else list(getattr(scope, "body", []))
    pending = list(reversed(roots))
    nodes: List[ast.AST] = []
    while pending:
        node = pending.pop()
        nodes.append(node)
        children = list(ast.iter_child_nodes(node))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body_ids = {id(child) for child in node.body}
            children = [child for child in children if id(child) not in body_ids]
        elif isinstance(node, ast.Lambda):
            children = [child for child in children if child is not node.body]
        pending.extend(reversed(children))
    return nodes


def _dynamic_loader_aliases(scope: ast.AST) -> LoaderScope:
    trusted: Dict[str, List[str]] = {}
    rebound: Set[str] = set()
    bound: Set[str] = set()
    args = getattr(scope, "args", None)
    if args is not None:
        parameters = list(getattr(args, "posonlyargs", [])) + list(args.args) + list(args.kwonlyargs)
        parameters += [arg for arg in (args.vararg, args.kwarg) if arg is not None]
        rebound.update(arg.arg for arg in parameters)
        bound.update(rebound)
    for node in _scope_nodes(scope):
        import_rows = _loader_import_bindings(node)
        if import_rows:
            for name, kind in import_rows:
                bound.add(name)
                if kind is None:
                    rebound.add(name)
                else:
                    trusted.setdefault(name, []).append(kind)
            continue
        names: Set[str] = set()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(*(_bound_names(target) for target in node.targets))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            names.update(_bound_names(node.target))
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            names.update(_bound_names(node.target))
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    names.update(_bound_names(item.optional_vars))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                names.update(_bound_names(target))
        rebound.update(names)
        bound.update(names)
    candidates = {name: set(kinds) for name, kinds in trusted.items()}
    safe = {name: kinds[0] for name, kinds in trusted.items() if len(set(kinds)) == 1 and name not in rebound}
    return bound, candidates, safe


def _dynamic_loader_kind(func: ast.AST, aliases: Dict[str, str]) -> Optional[str]:
    if isinstance(func, ast.Name):
        alias_kind = aliases.get(func.id)
        if alias_kind in {"__import__", "import_module", "spec_from_file_location"}:
            return alias_kind
        return None
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr == "import_module" and isinstance(func.value, ast.Name):
        return "import_module" if aliases.get(func.value.id) == "importlib" else None
    if func.attr != "spec_from_file_location":
        return None
    if isinstance(func.value, ast.Name):
        return "spec_from_file_location" if aliases.get(func.value.id) == "importlib.util" else None
    if (
        isinstance(func.value, ast.Attribute)
        and func.value.attr == "util"
        and isinstance(func.value.value, ast.Name)
        and aliases.get(func.value.value.id) == "importlib"
    ):
        return "spec_from_file_location"
    return None


def _is_unproven_dynamic_loader(func: ast.AST, candidates: LoaderCandidates) -> bool:
    if isinstance(func, ast.Name):
        return bool(candidates.get(func.id, set()) & {"__import__", "import_module", "spec_from_file_location"})
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr == "import_module" and isinstance(func.value, ast.Name):
        return "importlib" in candidates.get(func.value.id, set())
    if func.attr != "spec_from_file_location":
        return False
    if isinstance(func.value, ast.Name):
        return "importlib.util" in candidates.get(func.value.id, set())
    return bool(
        isinstance(func.value, ast.Attribute)
        and func.value.attr == "util"
        and isinstance(func.value.value, ast.Name)
        and "importlib" in candidates.get(func.value.value.id, set())
    )


def _dynamic_argument_text(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Attribute):
        return f"{_dynamic_argument_text(node.value)}.{node.attr}"
    if isinstance(node, ast.BinOp):
        operator = node.op.__class__.__name__
        return f"{_dynamic_argument_text(node.left)} {operator} {_dynamic_argument_text(node.right)}"
    if isinstance(node, ast.Call):
        return f"{_dynamic_argument_text(node.func)}(...)"
    return f"<{node.__class__.__name__}>"


class _DynamicImportVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.context = "hard"
        self.aliases = {"__import__": "__import__"}
        self.candidates: LoaderCandidates = {"__import__": {"__import__"}}
        self.scope_safe: Dict[str, str] = {}
        self.scope_kind = "root"
        self.class_outer_aliases: Dict[str, str] = {}
        self.class_outer_candidates: LoaderCandidates = {}
        self.resolved: List[ResolvedDynamicImport] = []
        self.unresolved: List[UnresolvedDynamicImport] = []

    def _visit_in_context(self, nodes: Sequence[ast.AST], context: str, *, isolate: bool = False) -> None:
        previous_context = self.context
        previous_aliases = dict(self.aliases) if isolate else None
        self.context = context
        try:
            for node in nodes:
                self.visit(node)
        finally:
            self.context = previous_context
            if previous_aliases is not None:
                self.aliases = previous_aliases

    def _visit_scope(
        self,
        scope: ast.AST,
        nodes: Sequence[ast.AST],
        context: str,
        kind: str,
        inherited_aliases: Dict[str, str],
        inherited_candidates: LoaderCandidates,
    ) -> None:
        previous = (
            self.aliases,
            self.candidates,
            self.scope_safe,
            self.scope_kind,
            self.class_outer_aliases,
            self.class_outer_candidates,
        )
        bound, local_candidates, safe = _dynamic_loader_aliases(scope)
        aliases = dict(inherited_aliases)
        for name in bound:
            aliases.pop(name, None)
        candidates = {name: set(kinds) for name, kinds in inherited_candidates.items()}
        for name, kinds in local_candidates.items():
            candidates.setdefault(name, set()).update(kinds)
        self.aliases, self.candidates, self.scope_safe, self.scope_kind = aliases, candidates, safe, kind
        if kind == "class":
            self.class_outer_aliases = dict(inherited_aliases)
            self.class_outer_candidates = {
                name: set(kinds) for name, kinds in inherited_candidates.items()
            }
        try:
            self._visit_in_context(nodes, context)
        finally:
            (
                self.aliases,
                self.candidates,
                self.scope_safe,
                self.scope_kind,
                self.class_outer_aliases,
                self.class_outer_candidates,
            ) = previous

    def _nested_scope_sources(self) -> Tuple[Dict[str, str], LoaderCandidates]:
        if self.scope_kind == "class":
            return self.class_outer_aliases, self.class_outer_candidates
        return self.aliases, self.candidates

    def _activate_loader_imports(self, node: ast.AST) -> None:
        for name, kind in _loader_import_bindings(node):
            if kind is not None and self.scope_safe.get(name) == kind:
                self.aliases[name] = kind

    def visit_Module(self, node: ast.Module) -> None:
        self._visit_scope(node, node.body, "hard", "module", self.aliases, self.candidates)

    def _visit_function_header(self, node: ast.AST) -> None:
        args = node.args  # type: ignore[attr-defined]
        for decorator in list(getattr(node, "decorator_list", [])):
            self.visit(decorator)
        for default in list(args.defaults) + [value for value in args.kw_defaults if value is not None]:
            self.visit(default)
        for arg in list(getattr(args, "posonlyargs", [])) + list(args.args) + list(args.kwonlyargs):
            if arg.annotation is not None:
                self.visit(arg.annotation)
        returns = getattr(node, "returns", None)
        if returns is not None:
            self.visit(returns)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_header(node)
        body_context = "typeonly" if self.context == "typeonly" else "lazy"
        aliases, candidates = self._nested_scope_sources()
        self._visit_scope(node, node.body, body_context, "function", aliases, candidates)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in list(node.args.defaults) + [value for value in node.args.kw_defaults if value is not None]:
            self.visit(default)
        body_context = "typeonly" if self.context == "typeonly" else "lazy"
        aliases, candidates = self._nested_scope_sources()
        self._visit_scope(node, [node.body], body_context, "function", aliases, candidates)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for expression in list(node.decorator_list) + list(node.bases):
            self.visit(expression)
        for keyword in node.keywords:
            self.visit(keyword.value)
        aliases, candidates = self._nested_scope_sources()
        self._visit_scope(node, node.body, self.context, "class", aliases, candidates)

    def visit_Import(self, node: ast.Import) -> None:
        self._activate_loader_imports(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._activate_loader_imports(node)

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        if _is_type_checking_test(node.test):
            self._visit_in_context(node.body, "typeonly", isolate=True)
            self._visit_in_context(node.orelse, self.context, isolate=True)
            return
        branch_context = _conditional_context(self.context)
        self._visit_in_context(node.body, branch_context, isolate=True)
        self._visit_in_context(node.orelse, branch_context, isolate=True)

    def visit_Try(self, node: ast.Try) -> None:
        branch_context = _conditional_context(self.context)
        self._visit_in_context(node.body, branch_context, isolate=True)
        for handler in node.handlers:
            if handler.type is not None:
                self._visit_in_context([handler.type], branch_context, isolate=True)
            self._visit_in_context(handler.body, branch_context, isolate=True)
        self._visit_in_context(node.orelse, branch_context, isolate=True)
        self._visit_in_context(node.finalbody, self.context)

    def visit_For(self, node: ast.For) -> None:
        self.visit(node.target)
        self.visit(node.iter)
        self._visit_in_context(node.body, self.context, isolate=True)
        self._visit_in_context(node.orelse, self.context, isolate=True)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.visit_For(node)  # type: ignore[arg-type]

    def visit_While(self, node: ast.While) -> None:
        self.visit(node.test)
        self._visit_in_context(node.body, self.context, isolate=True)
        self._visit_in_context(node.orelse, self.context, isolate=True)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self.visit(item.optional_vars)
        self._visit_in_context(node.body, self.context, isolate=True)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self.visit_With(node)  # type: ignore[arg-type]

    def visit_Call(self, node: ast.Call) -> None:
        loader_kind = _dynamic_loader_kind(node.func, self.aliases)
        first_arg = _call_argument(node, 0, "name")
        if loader_kind:
            if first_arg is None:
                self.unresolved.append((self.context, node.lineno, f"{loader_kind}(<missing name>)"))
            elif loader_kind == "spec_from_file_location":
                expression = f"spec_from_file_location({_dynamic_argument_text(first_arg)})"
                self.unresolved.append((self.context, node.lineno, expression))
            elif isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                target = first_arg.value
                package = _dynamic_package_argument(node) if target.startswith(".") else None
                if not target.startswith(".") or package is not None:
                    self.resolved.append((target, package, self.context, node.lineno))
                else:
                    expression = f"relative target {target!r} with unresolved package"
                    self.unresolved.append((self.context, node.lineno, expression))
            else:
                argument = _dynamic_argument_text(first_arg)
                expression = argument if loader_kind == "import_module" else f"{loader_kind}({argument})"
                self.unresolved.append((self.context, node.lineno, expression))
        elif _is_unproven_dynamic_loader(node.func, self.candidates):
            argument = "<missing name>" if first_arg is None else _dynamic_argument_text(first_arg)
            expression = f"unproven loader binding: {_dynamic_argument_text(node.func)}({argument})"
            self.unresolved.append((self.context, node.lineno, expression))
        self.generic_visit(node)


def _call_argument(call: ast.Call, position: int, *keyword_names: str) -> Optional[ast.AST]:
    if len(call.args) > position:
        return call.args[position]
    allowed = set(keyword_names)
    for keyword in call.keywords:
        if keyword.arg in allowed:
            return keyword.value
    return None


def _dynamic_package_argument(call: ast.Call) -> Optional[str]:
    package = _call_argument(call, 1, "package")
    if package is None:
        return None
    if isinstance(package, ast.Name) and package.id in {"__package__", "__name__"}:
        return package.id
    if isinstance(package, ast.Constant) and isinstance(package.value, str):
        return package.value
    return None


def dyn_imports(tree: ast.AST) -> Tuple[List[ResolvedDynamicImport], List[UnresolvedDynamicImport]]:
    visitor = _DynamicImportVisitor()
    visitor.visit(tree)
    return visitor.resolved, visitor.unresolved


def resolve_targets(
    node: ast.AST,
    pkg: List[str],
    mod_to_file: Dict[str, str],
    *,
    include_parent_packages: bool = True,
) -> List[str]:
    if isinstance(node, ast.ImportFrom):
        targets = _import_from_targets(node, pkg, mod_to_file)
    else:
        targets = _direct_import_targets(node, mod_to_file)
    return expand_parent_packages(targets, mod_to_file) if include_parent_packages else targets


def expand_parent_packages(targets: Sequence[str], mod_to_file: Dict[str, str]) -> List[str]:
    expanded: List[str] = []
    for target in targets:
        parts = target.split(".")
        for length in range(1, len(parts)):
            parent = ".".join(parts[:length])
            if parent in mod_to_file and parent not in expanded:
                expanded.append(parent)
        if target not in expanded:
            expanded.append(target)
    return expanded


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
