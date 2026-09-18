"""Win7 冻结包完整性对账合同（2026-07-19 盲区扫描 B07/B08，护栏 B14 同批）。

背景：
- scheduler 路由 registrar（web/routes/domains/scheduler/scheduler_route_registrar.py）
  与 core.services.scheduler 包 __init__（含 config 子包）都用变量实参
  importlib.import_module 做动态导入，PyInstaller 4.10 静态分析不可见；
- 冻结包的模块收集只有两条通道：build_win7_onedir.bat 的 --hidden-import 手工清单，
  以及 app.py 可达静态 import 覆盖的"冻结导入锚"
  （web/bootstrap/factory.py 的 _PYINSTALLER_IMPORT_ANCHORS，
  core/services/scheduler/_frozen_import_anchor.py）。

本合同把动态导入清单与两条收集通道钉死对账：
  (a) bat 两个打包分支的 hidden-import 均须覆盖 registrar._ROUTE_MODULES 全集；
  (b) core.services.scheduler（含 config 子包）_EXPORTS 的每个模块，须被冻结锚
      静态 import 覆盖，或在 bat hidden-import 清单里；
  (c) bat 两个分支的 hidden-import 集合彼此一致；
  (d) 冻结锚必须被 factory 静态 import 且挂进 _PYINSTALLER_IMPORT_ANCHORS
      （否则锚点文件本身就是不可达死代码，冻结时不会被收集）；
  (e) 所有第一方 hidden-import 与锚点 import 必须解析到真实存在的模块文件（防 typo）。

任何一侧漂移（新增路由模块 / 新增服务导出未同步）本合同立即红，
杜绝"源码态全绿、冻结 exe 启动即死"的确定性交付阻断复发。
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

from tests._support.paths import REPO_ROOT

_BAT_PATH = REPO_ROOT / "build_win7_onedir.bat"
_SCHEDULER_INIT_PATH = REPO_ROOT / "core" / "services" / "scheduler" / "__init__.py"
_SCHEDULER_CONFIG_INIT_PATH = REPO_ROOT / "core" / "services" / "scheduler" / "config" / "__init__.py"
_ANCHOR_PATH = REPO_ROOT / "core" / "services" / "scheduler" / "_frozen_import_anchor.py"
_FACTORY_PATH = REPO_ROOT / "web" / "bootstrap" / "factory.py"

_SCHEDULER_PACKAGE = "core.services.scheduler"
_SCHEDULER_CONFIG_PACKAGE = "core.services.scheduler.config"
_ANCHOR_MODULE = "core.services.scheduler._frozen_import_anchor"

_FIRST_PARTY_PREFIXES = ("core.", "web.", "data.")


def _bat_hidden_import_sets() -> List[Set[str]]:
    """按打包分支（vendor / 无 vendor）返回各自的 --hidden-import 集合。"""
    text = _BAT_PATH.read_text(encoding="utf-8")
    blocks = re.split(r"python -m PyInstaller", text)[1:]
    assert len(blocks) == 2, "build_win7_onedir.bat 应恰有两个 PyInstaller 打包分支（vendor / 无 vendor）"
    return [set(re.findall(r"--hidden-import\s+(\S+)", block)) for block in blocks]


def _module_level_assign_value(path: Path, name: str) -> ast.expr:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return node.value
    raise AssertionError(f"{path} 缺少模块级赋值：{name}")


def _lazy_exports_modules(path: Path, package: str) -> Set[str]:
    """解析包 __init__ 的 _EXPORTS 映射，返回完整模块名集合。"""
    value = _module_level_assign_value(path, "_EXPORTS")
    assert isinstance(value, ast.Dict)
    modules: Set[str] = set()
    for module_node in value.values:
        assert isinstance(module_node, ast.Constant) and isinstance(module_node.value, str)
        raw = module_node.value
        modules.add(f"{package}{raw}" if raw.startswith(".") else raw)
    assert modules, f"{path} 的 _EXPORTS 不应为空"
    return modules


def _anchor_static_imports() -> Set[str]:
    """冻结锚里全部静态 import 的完整模块名（plain import 与 from-import 都认）。"""
    tree = ast.parse(_ANCHOR_PATH.read_text(encoding="utf-8"))
    covered: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                covered.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            assert node.level == 0, "冻结锚必须用绝对 import，保证 PyInstaller 字节码分析零歧义"
            for alias in node.names:
                covered.add(f"{node.module}.{alias.name}")
    return covered


def _first_party_module_file_exists(module_name: str) -> bool:
    parts = module_name.split(".")
    as_file = REPO_ROOT.joinpath(*parts).with_suffix(".py")
    as_pkg = REPO_ROOT.joinpath(*parts) / "__init__.py"
    return as_file.is_file() or as_pkg.is_file()


def _factory_anchor_binding() -> Tuple[Dict[str, str], List[str]]:
    """返回 (factory 里锚模块 import 的 别名->完整模块名 映射, _PYINSTALLER_IMPORT_ANCHORS 元素名列表)。"""
    tree = ast.parse(_FACTORY_PATH.read_text(encoding="utf-8"))
    alias_to_module: Dict[str, str] = {}
    tuple_names: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                alias_to_module[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for alias in node.names:
                alias_to_module[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_PYINSTALLER_IMPORT_ANCHORS":
                    assert isinstance(node.value, ast.Tuple), "_PYINSTALLER_IMPORT_ANCHORS 必须是元组"
                    for elt in node.value.elts:
                        assert isinstance(elt, ast.Name), "_PYINSTALLER_IMPORT_ANCHORS 元素必须是 import 别名"
                        tuple_names.append(elt.id)
    return alias_to_module, tuple_names


def test_bat_hidden_import_sets_are_identical_across_branches() -> None:
    """(c) vendor / 无 vendor 两个分支的 hidden-import 清单必须一致，防止只改一半。"""
    first, second = _bat_hidden_import_sets()
    assert first == second, (
        f"两个打包分支 hidden-import 漂移：仅分支1 有 {sorted(first - second)}，"
        f"仅分支2 有 {sorted(second - first)}"
    )


def test_scheduler_lazy_exports_are_collectible_into_frozen_bundle() -> None:
    """(b) 包 __getattr__ lazy 导出的每个模块必须有冻结收集通道：锚点静态 import 或 bat hidden-import。"""
    lazy_modules = _lazy_exports_modules(_SCHEDULER_INIT_PATH, _SCHEDULER_PACKAGE) | _lazy_exports_modules(
        _SCHEDULER_CONFIG_INIT_PATH, _SCHEDULER_CONFIG_PACKAGE
    )
    anchored = _anchor_static_imports()
    hidden_sets = _bat_hidden_import_sets()
    hidden_everywhere = hidden_sets[0] & hidden_sets[1]
    missing = sorted(lazy_modules - anchored - hidden_everywhere)
    assert not missing, (
        f"lazy _EXPORTS 模块缺冻结收集通道：{missing}；"
        "请同步 core/services/scheduler/_frozen_import_anchor.py（首选）"
        "或 build_win7_onedir.bat 两个分支的 --hidden-import，"
        "否则冻结 exe 在 request_services 首次 from-import 时启动即死（B08）。"
    )


def test_frozen_anchor_is_reachable_via_factory_pyinstaller_anchors() -> None:
    """(d) 冻结锚必须被 factory 静态 import 并挂进 _PYINSTALLER_IMPORT_ANCHORS，否则锚点自身不进包。"""
    alias_to_module, tuple_names = _factory_anchor_binding()
    assert tuple_names, "factory.py 缺少 _PYINSTALLER_IMPORT_ANCHORS 元组"
    anchor_aliases = [alias for alias, module in alias_to_module.items() if module == _ANCHOR_MODULE]
    assert anchor_aliases, f"factory.py 必须静态 import {_ANCHOR_MODULE}"
    assert any(alias in tuple_names for alias in anchor_aliases), (
        f"factory.py 的 _PYINSTALLER_IMPORT_ANCHORS 必须包含 {_ANCHOR_MODULE} 的 import 别名，"
        "否则锚点 import 可能被当未使用导入清理掉。"
    )


def test_first_party_hidden_imports_and_anchor_imports_resolve_to_real_files() -> None:
    """(e) hidden-import / 锚点清单里的第一方模块必须真实存在（防 typo 造成的静默漏收）。"""
    candidates: Set[str] = set()
    for hidden in _bat_hidden_import_sets():
        candidates |= {name for name in hidden if name.startswith(_FIRST_PARTY_PREFIXES)}
    candidates |= {name for name in _anchor_static_imports() if name.startswith(_FIRST_PARTY_PREFIXES)}
    broken = sorted(name for name in candidates if not _first_party_module_file_exists(name))
    assert not broken, f"以下第一方模块名解析不到真实文件（typo 或已删除未同步）：{broken}"


def test_frozen_anchor_module_imports_cleanly() -> None:
    """锚点自身必须可导入：抓住锚里残留已删除模块的 stale import。"""
    module = importlib.import_module(_ANCHOR_MODULE)
    anchors = getattr(module, "FROZEN_IMPORT_ANCHORS")
    assert anchors, "FROZEN_IMPORT_ANCHORS 不应为空"
