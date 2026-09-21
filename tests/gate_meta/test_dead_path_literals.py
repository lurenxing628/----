"""合同测试：失效仓库路径字面量棘轮（dead_path_literal）。

锁定三件事：
1. 扫描器口径——什么算仓库路径字面量，运行时产物目录和散文不算。
2. 退役回归锁——删掉一个被字符串引用的文件，相对基线必须出现 new 条目。
   这正是 2026-09-18 删旧路由层时没人发现的那类腐烂：
   `tests/web_pages/test_frontend_ui_language_polish.py` 的 `_read("web/routes/...")`
   指向了不存在的文件，而该文件整体被标 perf 不进任何门禁。
3. 当前仓库相对基线无新增债务；基线条目引用的源文件本身必须存在。

存量 269 处是已知债务，多数是门禁元测试在临时目录里合成的假仓库路径
（core/services/example.py 之类），进基线当存量不阻断；基线只减不增，
所以任何新删的真文件都会报红。
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

from tests._support.paths import REPO_ROOT_STR as REPO_ROOT
from tools import scan_dead_path_literals
from tools.boundary_baseline import (
    compare_counts,
    default_baseline_path,
    entries_to_counts,
    load_baseline,
)

RULE = scan_dead_path_literals.RULE


# ---------------------------------------------------------------------------
# 扫描器口径
# ---------------------------------------------------------------------------


def test_repo_path_literal_accepts_source_paths_under_repo_top_dirs() -> None:
    for value in (
        "web/routes/material.py",
        "core/services/workbench/resource/files.py",
        "tests/web_pages/test_page_manual_registry.py",
        "templates/workbench/legacy_result.html",
        "static/docs/scheduler_manual.md",
        "开发文档/技术债务治理台账.md",
        "tools/baselines/private_import_baseline.json",
    ):
        assert scan_dead_path_literals.is_repo_path_literal(value), value


def test_repo_path_literal_rejects_runtime_artifacts_and_non_paths() -> None:
    for value in (
        # 运行时才生成，源码里写它们的路径是正常的
        "evidence/QualityGate/collect_nodeids.json",
        "db/aps-live.db",
        "logs/aps_runtime.json",
        "output/workbench-migration/baselines/x.py",
        # 不是一条确定路径
        "scripts/workbench/build.py, all live sources including main.jsx",
        "core/services/**/*.py",
        "tests/{name}.py",
        "/abs/path/file.py",
        "https://example.com/a.py",
        # 首段不是仓库顶层目录
        "somewhere/else/file.py",
        # 没有扩展名
        "core/services/workbench",
        # 没有斜杠
        "app.py",
    ):
        assert not scan_dead_path_literals.is_repo_path_literal(value), value


def test_scanner_counts_each_dead_literal_separately_and_records_lines() -> None:
    source = textwrap.dedent(
        '''
        A = "web/routes/gone.py"
        B = "web/routes/gone.py"
        C = "web/routes/alive.py"
        D = "evidence/QualityGate/x.json"
        '''
    )
    hits = scan_dead_path_literals.scan_dead_path_literals_file(
        "tests/sample.py", source, lambda value: value == "web/routes/alive.py"
    )
    assert [hit["kind"] for hit in hits] == ["web/routes/gone.py", "web/routes/gone.py"]
    assert sorted(int(hit["line"]) for hit in hits) == [2, 3]


# ---------------------------------------------------------------------------
# 退役回归锁
# ---------------------------------------------------------------------------


def _write(root: Path, rel: str, source: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")


def test_deleting_a_referenced_file_shows_up_as_new_debt(tmp_path: Path) -> None:
    """建一个假仓库：测试引用某个路由文件；删掉该文件后必须出现 new 条目。"""
    _write(tmp_path, "web/routes/material.py", "VALUE = 1\n")
    _write(
        tmp_path,
        "tests/web_pages/test_copy.py",
        '''
        def test_copy():
            assert _read("web/routes/material.py")
        ''',
    )

    before = entries_to_counts(list(scan_dead_path_literals.scan(str(tmp_path))["entries"]))
    assert before == {}, "路由文件还在时不该有任何失效字面量"

    os.remove(str(tmp_path / "web/routes/material.py"))
    after = entries_to_counts(list(scan_dead_path_literals.scan(str(tmp_path))["entries"]))

    comparison = compare_counts(after, before)
    assert ("tests/web_pages/test_copy.py", "web/routes/material.py") in comparison.new
    assert comparison.has_debt


def test_fixing_a_dead_literal_requires_baseline_refresh(tmp_path: Path) -> None:
    """反向：把失效引用删掉后条目变 stale，门禁仍拦，逼迫受控刷新基线。"""
    _write(
        tmp_path,
        "tests/web_pages/test_copy.py",
        '''
        def test_copy():
            assert _read("web/routes/material.py")
        ''',
    )
    baseline = entries_to_counts(list(scan_dead_path_literals.scan(str(tmp_path))["entries"]))
    assert ("tests/web_pages/test_copy.py", "web/routes/material.py") in baseline

    _write(tmp_path, "tests/web_pages/test_copy.py", "def test_copy():\n    assert True\n")
    comparison = compare_counts(
        entries_to_counts(list(scan_dead_path_literals.scan(str(tmp_path))["entries"])), baseline
    )
    assert ("tests/web_pages/test_copy.py", "web/routes/material.py") in comparison.stale
    assert comparison.has_debt


# ---------------------------------------------------------------------------
# 当前仓库棘轮：只减不增
# ---------------------------------------------------------------------------


def test_repo_dead_path_literals_have_no_new_debt() -> None:
    current = entries_to_counts(list(scan_dead_path_literals.scan(REPO_ROOT)["entries"]))
    baseline = load_baseline(default_baseline_path(REPO_ROOT, RULE), expected_rule=RULE)
    comparison = compare_counts(current, baseline)
    assert comparison.clean, (
        f"{RULE} 相对基线有变化：new={sorted(comparison.new)} increased={sorted(comparison.increased)} "
        f"stale={sorted(comparison.stale)}；new/increased 说明有字符串指向刚被删掉的文件，"
        f"请改掉引用而不是刷基线；stale 说明债务已还，请 python -m tools.scan_dead_path_literals --refresh"
    )


def test_baseline_entries_point_at_existing_source_files() -> None:
    path = default_baseline_path(REPO_ROOT, RULE)
    assert os.path.exists(path), path
    for source_path, _literal in load_baseline(path, expected_rule=RULE) or {}:
        assert os.path.exists(os.path.join(REPO_ROOT, source_path)), (
            f"基线引用的源文件不存在：{source_path}（请 --refresh）"
        )


def test_forbidden_generated_documents_are_outputs_not_missing_sources() -> None:
    from tools.git_hook_blocked_paths import BLOCKED_PATH_RULES

    for pattern, _reason in BLOCKED_PATH_RULES:
        if pattern.startswith("docs/"):
            example = pattern.replace("**", "generated").replace("*", "generated")
            assert not scan_dead_path_literals.is_repo_path_literal(example)
    assert scan_dead_path_literals.is_repo_path_literal("docs/dev/product-tooling.md")


def test_missing_shared_document_is_still_reported(tmp_path: Path) -> None:
    name = "docs/dev/product-tooling.md"
    _write(tmp_path, name, "# Shared tooling")
    _write(tmp_path, "tools/scan_dead_path_literals.py", 'DOC = "' + name + '"\n')
    assert scan_dead_path_literals.scan(str(tmp_path))["entries"] == []
    (tmp_path / name).unlink()
    entries = scan_dead_path_literals.scan(str(tmp_path))["entries"]
    assert len(entries) == 1 and entries[0]["kind"] == name
