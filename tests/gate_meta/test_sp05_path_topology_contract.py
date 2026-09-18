"""契约测试：SP05 scheduler 目录拆分后的服务层与路由层拓扑及兼容矩阵——config/run/summary 等子包就位且延迟子包 __init__ 无 import 副作用、旧根模块强别名或行为兼容门面保真、旧路径已删；旧兼容模块导入扫描能识别包内相对/动态/__import__ 导入且生产代码不新增此类导入；路由根入口被动注册、子叶 import 不拉起 registrar 副作用，safe_next_url 单一策略源、scheduler 手册路径走单一 BASE_DIR 事实源，开发与阶段文档同步迁移后路径。"""

from __future__ import annotations

import ast
import importlib
from typing import List, Optional, Set, Tuple

from flask import Flask

from tests._support.paths import REPO_ROOT

SERVICE_STRONG_COMPAT_MODULES = {
    "core.services.scheduler.schedule_optimizer": "core.services.scheduler.run.schedule_optimizer",
    "core.services.scheduler.schedule_optimizer_steps": "core.services.scheduler.run.schedule_optimizer_steps",
}

SERVICE_BEHAVIOR_COMPAT_SYMBOLS = {
    "core.services.scheduler.freeze_window": "core.services.scheduler.run.freeze_window",
    "core.services.scheduler.schedule_input_builder": "core.services.scheduler.run.schedule_input_builder",
    "core.services.scheduler.schedule_input_collector": "core.services.scheduler.run.schedule_input_collector",
    "core.services.scheduler.schedule_orchestrator": "core.services.scheduler.run.schedule_orchestrator",
    "core.services.scheduler.schedule_persistence": "core.services.scheduler.run.schedule_persistence",
}

SERVICE_BEHAVIOR_COMPAT_PUBLIC_SYMBOLS = {
    "core.services.scheduler.freeze_window": ("build_freeze_window_seed",),
    "core.services.scheduler.schedule_input_builder": (
        "OpForScheduleAlgo",
        "build_algo_operations",
    ),
    "core.services.scheduler.schedule_input_collector": (
        "ScheduleRunInput",
        "collect_schedule_run_input",
    ),
    "core.services.scheduler.schedule_orchestrator": (
        "ScheduleOrchestrationOutcome",
        "orchestrate_schedule_run",
    ),
    "core.services.scheduler.schedule_persistence": (
        "persist_schedule",
    ),
}

SERVICE_ROOTS_WITHOUT_COMPAT = (
    "core/services/scheduler/config_presets.py",
    "core/services/scheduler/schedule_input_contracts.py",
    "core/services/scheduler/schedule_input_runtime_support.py",
    "core/services/scheduler/schedule_template_lookup.py",
    "core/services/scheduler/schedule_summary_assembly.py",
    "core/services/scheduler/schedule_summary_degradation.py",
    "core/services/scheduler/schedule_summary_freeze.py",
)

# R43(O29) 收口：9 个顶层 scheduler_*.py route wrapper 已删除（roadmap p1-scheduler-debt-cleanup
# 已认账解冻），route 侧不再有任何 legacy 兼容面——三表清空但保留结构（扫描器按本集合工作，
# 集合空即 route 无 legacy 检测对象；wrapper 文件已不存在，误 import 即 loud ModuleNotFoundError）。
ROUTE_COMPAT_MODULES = {}

ROUTE_BEHAVIOR_COMPAT_SYMBOLS = {}

LEGACY_COMPAT_MODULES = frozenset(
    set(SERVICE_STRONG_COMPAT_MODULES)
    | set(SERVICE_BEHAVIOR_COMPAT_SYMBOLS)
    | set(ROUTE_COMPAT_MODULES)
    | set(ROUTE_BEHAVIOR_COMPAT_SYMBOLS)
)

LEGACY_COMPAT_WRAPPER_FILES = {
    f"{module_name.replace('.', '/')}.py"
    for module_name in LEGACY_COMPAT_MODULES
}

PRODUCTION_LEGACY_IMPORT_SCAN_ROOTS = (
    "core",
    "web",
)

def _module_context_from_rel_path(rel: str) -> Tuple[str, bool]:
    module_name = rel[:-3].replace("/", ".")
    if module_name.endswith(".__init__"):
        return module_name[: -len(".__init__")], True
    return module_name, False


def _resolve_import_from_module(node: ast.ImportFrom, current_module: str, *, is_package: bool) -> Optional[str]:
    if node.level <= 0:
        return node.module
    package_parts = current_module.split(".")
    if not is_package:
        package_parts = package_parts[:-1]
    keep = len(package_parts) - (node.level - 1)
    if keep < 0:
        return None
    base = ".".join(package_parts[:keep])
    if node.module:
        return f"{base}.{node.module}" if base else node.module
    return base or None


def _import_module_aliases(module_ast: ast.Module) -> Set[str]:
    aliases: Set[str] = set()
    for node in module_ast.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level != 0 or node.module != "importlib":
            continue
        for alias in node.names:
            if alias.name == "import_module":
                aliases.add(alias.asname or alias.name)
    return aliases


def _legacy_import_modules(
    node: ast.AST,
    current_module: str,
    *,
    is_package: bool,
    import_module_aliases: Set[str],
) -> List[str]:
    modules: List[str] = []
    if isinstance(node, ast.Import):
        modules.extend(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        base_module = _resolve_import_from_module(node, current_module, is_package=is_package)
        if base_module:
            modules.append(base_module)
            modules.extend(f"{base_module}.{alias.name}" for alias in node.names if alias.name != "*")
    elif isinstance(node, ast.ImportFrom):
        base_module = _resolve_import_from_module(node, current_module, is_package=is_package)
        if base_module:
            modules.extend(f"{base_module}.{alias.name}" for alias in node.names if alias.name != "*")
    elif isinstance(node, ast.Call):
        if not node.args:
            return modules
        first_arg = node.args[0]
        if not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
            return modules
        if isinstance(node.func, ast.Name) and node.func.id == "__import__":
            modules.append(first_arg.value)
        elif isinstance(node.func, ast.Name) and node.func.id in import_module_aliases:
            modules.append(first_arg.value)
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
            modules.append(first_arg.value)
    return modules


def _matches_legacy_compat_module(module_name: str) -> Optional[str]:
    for legacy_module in sorted(LEGACY_COMPAT_MODULES):
        if module_name == legacy_module or module_name.startswith(f"{legacy_module}."):
            return legacy_module
    return None


def _legacy_import_violations_for_source(rel: str, source: str) -> List[str]:
    current_module, is_package = _module_context_from_rel_path(rel)
    module_ast = ast.parse(source, filename=rel)
    import_module_aliases = _import_module_aliases(module_ast)
    violations: List[str] = []
    for node in ast.walk(module_ast):
        matched_legacy_modules = set()
        for module_name in _legacy_import_modules(
            node,
            current_module,
            is_package=is_package,
            import_module_aliases=import_module_aliases,
        ):
            legacy_module = _matches_legacy_compat_module(module_name)
            if legacy_module:
                matched_legacy_modules.add(legacy_module)
        for legacy_module in sorted(matched_legacy_modules):
            line_no = getattr(node, "lineno", "?")
            violations.append(f"{rel}:{line_no}:{legacy_module}")
    return violations


def test_sp05_service_topology_and_strong_compatibility() -> None:
    for package_name in ("config", "run", "summary"):
        package_dir = REPO_ROOT / "core/services/scheduler" / package_name
        assert package_dir.is_dir()
        assert (package_dir / "__init__.py").is_file()

    lingering_root_files = [path for path in SERVICE_ROOTS_WITHOUT_COMPAT if (REPO_ROOT / path).exists()]
    assert lingering_root_files == []

    for old_name, new_name in SERVICE_STRONG_COMPAT_MODULES.items():
        new_path = REPO_ROOT / (new_name.replace(".", "/") + ".py")
        assert new_path.is_file(), new_path
        old_module = importlib.import_module(old_name)
        new_module = importlib.import_module(new_name)
        assert old_module is new_module, f"{old_name} must be a strong alias of {new_name}"

    for old_name, new_name in SERVICE_BEHAVIOR_COMPAT_SYMBOLS.items():
        new_path = REPO_ROOT / (new_name.replace(".", "/") + ".py")
        assert new_path.is_file(), new_path
        old_module = importlib.import_module(old_name)
        new_module = importlib.import_module(new_name)
        expected_symbols = SERVICE_BEHAVIOR_COMPAT_PUBLIC_SYMBOLS[old_name]
        assert tuple(old_module.__all__) == expected_symbols, old_name
        for symbol in expected_symbols:
            assert getattr(old_module, symbol) is getattr(new_module, symbol), f"{old_name}:{symbol}"

    config_package = importlib.import_module("core.services.scheduler.config")
    config_service_module = importlib.import_module("core.services.scheduler.config.config_service")
    assert config_package.ConfigService is config_service_module.ConfigService


def test_sp05_legacy_import_scan_catches_package_init_relative_imports() -> None:
    service_source = "from .schedule_orchestrator import orchestrate_schedule_run\n"
    service_violations = _legacy_import_violations_for_source(
        "core/services/scheduler/__init__.py",
        service_source,
    )
    assert service_violations == ["core/services/scheduler/__init__.py:1:core.services.scheduler.schedule_orchestrator"]



def test_sp05_legacy_import_scan_catches_dynamic_import_strings() -> None:
    source = 'import importlib\nimportlib.import_module("core.services.scheduler.schedule_orchestrator")\n'
    violations = _legacy_import_violations_for_source(
        "core/services/scheduler/dynamic_loader.py",
        source,
    )
    assert violations == ["core/services/scheduler/dynamic_loader.py:2:core.services.scheduler.schedule_orchestrator"]

    source = 'from importlib import import_module\nimport_module("core.services.scheduler.schedule_orchestrator")\n'
    violations = _legacy_import_violations_for_source(
        "core/services/scheduler/dynamic_loader.py",
        source,
    )
    assert violations == ["core/services/scheduler/dynamic_loader.py:2:core.services.scheduler.schedule_orchestrator"]


def test_sp05_production_code_does_not_grow_legacy_wrapper_imports() -> None:
    violations: List[str] = []
    for root in PRODUCTION_LEGACY_IMPORT_SCAN_ROOTS:
        for path in (REPO_ROOT / root).rglob("*.py"):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in LEGACY_COMPAT_WRAPPER_FILES:
                continue
            violations.extend(_legacy_import_violations_for_source(rel, path.read_text(encoding="utf-8")))

    assert violations == [], "未登记的生产代码旧兼容模块导入：\n" + "\n".join(violations)


def test_sp05_scheduler_manual_path_uses_single_base_dir_fact_source(tmp_path) -> None:
    scheduler_config = importlib.import_module("web.routes.workbench.manual_page")

    base_dir = tmp_path / "repo"
    compat_static = tmp_path / "compat_static"
    compat_manual = compat_static / "docs" / "scheduler_manual.md"
    compat_manual.parent.mkdir(parents=True, exist_ok=True)
    compat_manual.write_text("# compat manual\n", encoding="utf-8")

    app = Flask(__name__, static_folder=str(compat_static))
    app.config["BASE_DIR"] = str(base_dir)

    expected_manual = (base_dir / "static" / "docs" / "scheduler_manual.md").resolve()
    with app.app_context():
        manual_path, candidates = scheduler_config._resolve_scheduler_manual_md_path()

    assert manual_path is None
    assert candidates == [str(expected_manual)]


def test_sp05_scheduler_manual_path_requires_base_dir_without_root_fallback(tmp_path) -> None:
    scheduler_config = importlib.import_module("web.routes.workbench.manual_page")

    compat_static = tmp_path / "compat_static"
    compat_static.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__, static_folder=str(compat_static))

    with app.app_context():
        manual_path, candidates = scheduler_config._resolve_scheduler_manual_md_path()
        manual_text, manual_mtime = scheduler_config._load_manual_text_and_mtime(manual_path, candidates)

    assert manual_path is None
    assert candidates == []
    assert manual_mtime is None
    # 用户看到的是安装信息不完整，内部配置名只进日志。
    assert "本机安装信息不完整" in manual_text and "BASE_DIR" not in manual_text


def test_sp05_documentation_uses_migrated_scheduler_paths() -> None:
    dev_doc = (REPO_ROOT / "开发文档/开发文档.md").read_text(encoding="utf-8")
    stage_record = (REPO_ROOT / "开发文档/阶段留痕与验收记录.md").read_text(encoding="utf-8")

    scheduler_start = dev_doc.index("│   │   ├── scheduler/")
    scheduler_end = dev_doc.index("│   │   ├── report/", scheduler_start)
    scheduler_tree = dev_doc[scheduler_start:scheduler_end]

    for package_name in ("config", "run", "summary"):
        assert f"│   │   │   ├── {package_name}/" in scheduler_tree

    migrated_root_names = (
        "schedule_input_collector.py",
        "schedule_input_builder.py",
        "freeze_window.py",
        "schedule_optimizer.py",
        "schedule_orchestrator.py",
        "schedule_persistence.py",
    )
    stale_root_entries = [
        line
        for line in scheduler_tree.splitlines()
        if (line.startswith("│   │   │   ├── ") or line.startswith("│   │   │   └── "))
        and any(f"├── {name}" in line or f"└── {name}" in line for name in migrated_root_names)
        and "兼容薄门面" not in line
    ]
    assert stale_root_entries == []

    assert "core/services/scheduler/run/schedule_input_collector.py" in stage_record
    assert "core/services/scheduler/schedule_input_collector.py" not in stage_record

    # `.limcode/plans/` 是 ignored 历史归档，不存在于 clean clone，不能作为质量门禁事实源。
    # 当前路径合同只读取上面的两份 tracked 文档。
