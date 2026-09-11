"""Static repo-owned Python inventory, independent of what a test happened to load."""

import ast
from pathlib import Path

ASSET_ROOTS = ("core", "data", "web", "templates", "static", "frontend", "scripts", "tools", "tests", "plugins", "vendor", "desktop", "installer", "assets")
EXCLUDED_PARTS = frozenset(("__pycache__", "node_modules", ".git", ".pytest_cache", ".ruff_cache", ".DS_Store"))
RUNTIME_DATA_ROOTS = frozenset(("db", "logs", "backups", "output", "tmp", "evidence", "reports", "templates_excel"))
ROOT_SUFFIXES = (".py", ".sql", ".json", ".toml", ".ini", ".txt", ".cfg", ".lock", ".bat", ".spec")


def usable(path, root):
    relative = path.relative_to(root)
    return not EXCLUDED_PARTS.intersection(relative.parts) and path.suffix not in (".pyc", ".pyo", ".db", ".sqlite", ".sqlite3")


def discover(root, extra_paths=()):
    python_roots = []
    for path in root.iterdir():
        if not path.is_dir() or path.name.startswith(".") or path.name in RUNTIME_DATA_ROOTS | EXCLUDED_PARTS:
            continue
        if any(usable(item, root) for item in path.rglob("*.py")):
            python_roots.append(path.name)
    roots = sorted(set(ASSET_ROOTS) | set(python_roots))
    paths = [path for path in root.iterdir() if path.is_file() and path.suffix in ROOT_SUFFIXES]
    for name in roots:
        paths.extend(path for path in (root / name).rglob("*") if path.is_file())
    for name in extra_paths:
        path = root / name
        if path.is_absolute() and (root != path.resolve() and root not in path.resolve().parents):
            raise ValueError("Extra source must stay inside the declared origin.")
        if not path.exists():
            raise ValueError("Extra source is missing: " + name)
        paths.extend([path] if path.is_file() else [item for item in path.rglob("*") if item.is_file()])
    names = []
    for path in paths:
        if not usable(path, root):
            continue
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents):
            raise ValueError("Snapshot must not keep live symlinks: " + str(path.relative_to(root)))
        names.append(path.relative_to(root).as_posix())
    owners = sorted(set(python_roots) | {Path(name).stem for name in names if "/" not in name and name.endswith(".py")})
    return sorted(set(names)), {"mode": "repo-code-local-assets-and-tests", "roots": roots,
                               "discovered_python_roots": sorted(python_roots), "owned_import_roots": owners,
                               "excluded_runtime_data_roots": sorted(RUNTIME_DATA_ROOTS),
                               "excluded_parts": sorted(EXCLUDED_PARTS),
                               "extra_paths": list(extra_paths),
                               "absent_declared_asset_roots": [name for name in ASSET_ROOTS if not (root / name).exists()]}


def _module_exists(root, module):
    relative = Path(*module.split("."))
    return (root / relative).is_dir() or (root / relative).with_suffix(".py").is_file()


def inspect_imports(root, names, owners):
    missing, unparsed = [], []
    for name in names:
        if not name.endswith(".py"):
            continue
        try:
            tree = ast.parse((root / name).read_text(encoding="utf-8-sig"), filename=name)
        except SyntaxError as exc:
            unparsed.append({"path": name, "line": exc.lineno, "error": exc.msg})
            continue
        package = Path(name).parts[:-1]
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    prefix = package[:len(package) - node.level + 1]
                    modules = [".".join(prefix + tuple((node.module or "").split("."))).strip(".")]
                elif node.module:
                    modules = [node.module]
            for module in modules:
                if module.split(".", 1)[0] in owners and not _module_exists(root, module):
                    missing.append({"path": name, "line": node.lineno, "module": module})
    return {"missing_repo_modules": missing, "unparsed_python": unparsed,
            "python_files": sum(name.endswith(".py") for name in names)}
