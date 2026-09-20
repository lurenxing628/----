"""合同测试：三条边界棘轮规则——服务层不写 SQL（sql_boundary）、仓储层不做裁决（data_policy）、禁跨模块导入私有符号（private_import）。

锁定：扫描器对各 kind 的判定口径；基线比较的 new / stale / increased / decreased 语义；--refresh 默认拒绝总命中数增长；
以及当前仓库相对三份基线无新增债务（基线只减不增，退役条目必须同步 --refresh）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from textwrap import dedent

import pytest

from tests._support.paths import REPO_ROOT_STR as REPO_ROOT
from tools import scan_private_imports, scan_sql_boundary
from tools.boundary_baseline import (
    BoundaryBaselineError,
    compare_counts,
    default_baseline_path,
    entries_to_counts,
    load_baseline,
    write_baseline,
)


def _write(root: Path, rel: str, source: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(source), encoding="utf-8")


# ---------------------------------------------------------------------------
# 扫描器口径
# ---------------------------------------------------------------------------


def test_sql_boundary_scanner_flags_conn_execute_literal_probe_and_connect() -> None:
    source = dedent(
        '''
        import sqlite3

        def read(conn, svc):
            rows = conn.execute("SELECT 1 FROM Parts WHERE id=?", (1,)).fetchall()
            svc.conn.executemany("UPDATE Parts SET x=? WHERE id=?", [])
            names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
            conn.execute("PRAGMA foreign_keys")
            other = sqlite3.connect(":memory:")
            action = "update"
            label = "delete"
            return rows, names, other, action, label
        '''
    )
    hits = scan_sql_boundary.scan_sql_boundary_file("core/services/x.py", source)
    kinds = sorted(str(hit["kind"]) for hit in hits)
    assert kinds.count("conn_execute") == 4
    assert kinds.count("sqlite_connect") == 1
    assert kinds.count("schema_probe") == 2
    # 两条 SQL 字面量；小写的动作名 "update"/"delete" 不算 SQL
    assert kinds.count("sql_literal") == 2


def test_sql_boundary_scanner_ignores_repository_style_self_calls_without_sql_text() -> None:
    source = dedent(
        """
        class Reader:
            def load(self):
                return self.fetchall(_SQL)
        """
    )
    assert scan_sql_boundary.scan_sql_boundary_file("core/services/x.py", source) == []


def test_data_policy_scanner_flags_import_raise_call_and_identifier_param() -> None:
    source = dedent(
        '''
        from core.models.workbench_command import WorkbenchCommandRejected
        from core.models.workbench_trial import reject

        def lookup(self, table, column, value):
            row = self.conn.execute('SELECT 1 FROM "' + table + '" WHERE "' + column + '"=?', (value,)).fetchone()
            if row is None:
                raise WorkbenchCommandRejected("entity_not_found", "所选零件已失效。", 404)
            reject("query_too_large", "范围超过上限")
            return row

        def safe(self, part_no):
            return self.fetchall("SELECT * FROM Parts WHERE part_no=?", (part_no,))
        '''
    )
    hits = scan_sql_boundary.scan_data_policy_file("data/repositories/x.py", source)
    kinds = sorted(str(hit["kind"]) for hit in hits)
    assert kinds.count("policy_import") == 2
    assert kinds.count("policy_raise") == 2
    # 同一条拼接语句只计一次，即使嵌套了多个 BinOp
    assert kinds.count("identifier_param") == 1


def test_data_policy_scanner_flags_fstring_identifier_param() -> None:
    source = dedent(
        '''
        def dump(conn, name):
            return conn.execute(f"SELECT * FROM {name}").fetchall()
        '''
    )
    hits = scan_sql_boundary.scan_data_policy_file("data/repositories/x.py", source)
    assert [str(hit["kind"]) for hit in hits] == ["identifier_param"]


def test_private_import_scanner_flags_private_symbols_but_not_private_modules() -> None:
    source = dedent(
        """
        from __future__ import annotations
        from core.services.workbench.process.queries import _plain, public_name
        from .plan_baseline import _complete_rows
        from core.services.scheduler import _frozen_import_anchor
        from core.services.scheduler._frozen_import_anchor import _anything
        """
    )
    hits = scan_private_imports.scan_private_imports_file("core/services/x.py", source)
    assert sorted(str(hit["symbol"]) for hit in hits) == ["_complete_rows", "_plain"]


# ---------------------------------------------------------------------------
# 基线比较语义
# ---------------------------------------------------------------------------


def test_compare_counts_reports_new_stale_increased_and_decreased() -> None:
    baseline = {("a.py", "k"): 2, ("b.py", "k"): 1, ("c.py", "k"): 3}
    current = {("a.py", "k"): 3, ("c.py", "k"): 1, ("d.py", "k"): 1}
    comparison = compare_counts(current, baseline)
    assert comparison.new == {("d.py", "k"): 1}
    assert comparison.stale == {("b.py", "k"): 1}
    assert comparison.increased == {("a.py", "k"): (2, 3)}
    assert comparison.decreased == {("c.py", "k"): (3, 1)}
    assert comparison.has_debt
    assert not compare_counts({("a.py", "k"): 1}, {("a.py", "k"): 1}).has_debt


def test_compare_counts_with_missing_baseline_is_not_clean() -> None:
    comparison = compare_counts({}, None)
    assert comparison.baseline_missing
    assert not comparison.clean


def test_load_baseline_rejects_wrong_rule_and_bad_schema(tmp_path: Path) -> None:
    path = tmp_path / "x_baseline.json"
    write_baseline(str(path), rule="sql_boundary", scan_roots=["core"], note="n", counts={("a.py", "k"): 1})
    assert load_baseline(str(path), expected_rule="sql_boundary") == {("a.py", "k"): 1}
    with pytest.raises(BoundaryBaselineError):
        load_baseline(str(path), expected_rule="data_policy")
    path.write_text(json.dumps({"schema_version": 99, "rule": "sql_boundary", "entries": []}), encoding="utf-8")
    with pytest.raises(BoundaryBaselineError):
        load_baseline(str(path), expected_rule="sql_boundary")


def test_refresh_refuses_growth_unless_allowed(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    _write(repo, "core/services/a.py", 'def f(conn):\n    return conn.execute("SELECT 1")\n')
    assert scan_sql_boundary.main(["--rule", "sql_boundary", "--refresh", "--repo-root", str(repo)]) == 0
    _write(repo, "core/services/b.py", 'def g(conn):\n    return conn.execute("SELECT 2")\n')
    assert scan_sql_boundary.main(["--rule", "sql_boundary", "--fail-on-new", "--repo-root", str(repo)]) == 1
    assert "新增债务" in capsys.readouterr().out
    assert scan_sql_boundary.main(["--rule", "sql_boundary", "--refresh", "--repo-root", str(repo)]) == 1
    assert "刷新被拒绝" in capsys.readouterr().err
    assert scan_sql_boundary.main(["--rule", "sql_boundary", "--refresh", "--allow-growth", "--repo-root", str(repo)]) == 0
    assert scan_sql_boundary.main(["--rule", "sql_boundary", "--fail-on-new", "--quiet-when-clean", "--repo-root", str(repo)]) == 0


def test_stale_entry_fails_until_baseline_refreshed(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    _write(repo, "core/services/a.py", 'from x import _y\n')
    assert scan_private_imports.main(["--refresh", "--repo-root", str(repo)]) == 0
    _write(repo, "core/services/a.py", 'from x import y\n')
    assert scan_private_imports.main(["--fail-on-new", "--repo-root", str(repo)]) == 1
    assert "请从基线移除" in capsys.readouterr().out
    assert scan_private_imports.main(["--refresh", "--repo-root", str(repo)]) == 0
    assert scan_private_imports.main(["--fail-on-new", "--quiet-when-clean", "--repo-root", str(repo)]) == 0


def test_missing_baseline_fails_closed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "data/repositories/a.py", "x = 1\n")
    assert scan_sql_boundary.main(["--rule", "data_policy", "--fail-on-new", "--repo-root", str(repo)]) == 2


# ---------------------------------------------------------------------------
# 当前仓库棘轮：只减不增
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rule", [scan_sql_boundary.RULE_SQL_BOUNDARY, scan_sql_boundary.RULE_DATA_POLICY])
def test_repo_sql_boundary_rules_have_no_new_debt(rule: str) -> None:
    result = scan_sql_boundary.scan(rule, REPO_ROOT)
    current = entries_to_counts(list(result["entries"]))
    baseline = load_baseline(default_baseline_path(REPO_ROOT, rule), expected_rule=rule)
    comparison = compare_counts(current, baseline)
    assert comparison.clean, (
        f"{rule} 相对基线有变化：new={sorted(comparison.new)} increased={sorted(comparison.increased)} "
        f"stale={sorted(comparison.stale)}；新增请改回仓储/基础设施，退役请 python -m tools.scan_sql_boundary --refresh"
    )


def test_repo_private_imports_have_no_new_debt() -> None:
    result = scan_private_imports.scan(REPO_ROOT)
    current = entries_to_counts(list(result["entries"]))
    baseline = load_baseline(default_baseline_path(REPO_ROOT, scan_private_imports.RULE), expected_rule=scan_private_imports.RULE)
    comparison = compare_counts(current, baseline)
    assert comparison.clean, (
        f"private_import 相对基线有变化：new={sorted(comparison.new)} increased={sorted(comparison.increased)} "
        f"stale={sorted(comparison.stale)}；新增请给共享部分起公开名字，退役请 python -m tools.scan_private_imports --refresh"
    )


def test_baseline_files_are_tracked_and_paths_exist() -> None:
    for rule in (scan_sql_boundary.RULE_SQL_BOUNDARY, scan_sql_boundary.RULE_DATA_POLICY, scan_private_imports.RULE):
        path = default_baseline_path(REPO_ROOT, rule)
        assert os.path.exists(path), path
        for key in load_baseline(path, expected_rule=rule) or {}:
            assert os.path.exists(os.path.join(REPO_ROOT, key[0])), f"基线引用的文件不存在：{key[0]}（请 --refresh）"
