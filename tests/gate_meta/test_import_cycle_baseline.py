from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import pytest

from tools import scan_import_cycles
from tools.import_cycle_baseline import (
    SCOPE_PRODUCTION,
    SCOPE_WITH_TESTS,
    CycleBaselineError,
    compare_with_baseline,
    load_baseline,
    write_baseline,
)

ModuleEdge = Tuple[str, str]


def _cycle_record(members: Sequence[str], edges: Iterable[ModuleEdge]) -> dict:
    return {
        "members": list(members),
        "edges": [
            {
                "source": source,
                "target": target,
                "src": source.replace(".", "/") + ".py",
                "line": index,
                "extra": 0,
            }
            for index, (source, target) in enumerate(edges, start=1)
        ],
    }


def _result(
    *,
    dir_cycles: Sequence[Tuple[Sequence[str], Sequence[ModuleEdge]]] = (),
    file_cycles: Sequence[Tuple[Sequence[str], Sequence[ModuleEdge]]] = (),
    parse_errors: Sequence[dict] = (),
    unresolved_dynamic_imports: Sequence[dict] = (),
) -> dict:
    dir_records = [_cycle_record(members, edges) for members, edges in dir_cycles]
    file_records = [_cycle_record(members, edges) for members, edges in file_cycles]
    return {
        "module_count": 4,
        "scan_roots": ["pkg"],
        "file_cycle_semantics": scan_import_cycles.FILE_CYCLE_SEMANTICS,
        "parse_errors": list(parse_errors),
        "edge_counts": {"hard": 4, "cond": 0, "lazy": 0, "typeonly": 0},
        "hard_dir_cycles": dir_records,
        "hard_file_cycles": [list(members) for members, _edges in file_cycles],
        "hard_file_cycle_records": file_records,
        "explicit_hard_file_cycles": file_records,
        "delayed_dir_cycles": [],
        "runtime_file_cycle_count": len(file_records),
        "runtime_file_cycles": file_records,
        "explicit_runtime_file_cycles": file_records,
        "parent_package_init_edges": [],
        "unresolved_dynamic_imports": list(unresolved_dynamic_imports),
    }


def _base_cycle(extra_edges: Sequence[ModuleEdge] = ()) -> dict:
    return _result(
        dir_cycles=[
            (
                ["pkg/a", "pkg/b"],
                [
                    ("pkg.a.service", "pkg.b.contract"),
                    ("pkg.b.adapter", "pkg.a.contract"),
                    *extra_edges,
                ],
            )
        ]
    )


def test_v2_baseline_same_members_and_edges_passes(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    current = _base_cycle()
    write_baseline(str(path), current, scope=SCOPE_PRODUCTION)

    comparison = compare_with_baseline(str(path), current, expected_scope=SCOPE_PRODUCTION)

    assert comparison.clean
    assert not comparison.has_new


def test_same_members_with_new_internal_edge_fails(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    write_baseline(str(path), _base_cycle(), scope=SCOPE_PRODUCTION)
    current = _base_cycle(extra_edges=[("pkg.a.extra", "pkg.b.contract")])

    comparison = compare_with_baseline(str(path), current, expected_scope=SCOPE_PRODUCTION)

    assert comparison.has_new
    assert comparison.new_dir == set()
    assert comparison.new_dir_edges == {
        ("pkg/a|pkg/b", "pkg.a.extra -> pkg.b.contract")
    }


def test_deleted_internal_edge_is_allowed(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    write_baseline(
        str(path),
        _base_cycle(extra_edges=[("pkg.a.extra", "pkg.b.contract")]),
        scope=SCOPE_PRODUCTION,
    )

    comparison = compare_with_baseline(str(path), _base_cycle(), expected_scope=SCOPE_PRODUCTION)

    assert comparison.clean


def test_scc_shrinking_to_baseline_edge_subset_is_allowed_but_new_edge_fails(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    baseline = _result(
        dir_cycles=[
            (
                ["pkg/a", "pkg/b", "pkg/c"],
                [
                    ("pkg.a", "pkg.b"),
                    ("pkg.b", "pkg.a"),
                    ("pkg.b", "pkg.c"),
                    ("pkg.c", "pkg.b"),
                ],
            )
        ]
    )
    write_baseline(str(path), baseline, scope=SCOPE_PRODUCTION)
    smaller = _result(
        dir_cycles=[(["pkg/a", "pkg/b"], [("pkg.a", "pkg.b"), ("pkg.b", "pkg.a")])]
    )

    comparison = compare_with_baseline(str(path), smaller, expected_scope=SCOPE_PRODUCTION)
    assert comparison.clean

    smaller_with_new_edge = _result(
        dir_cycles=[
            (
                ["pkg/a", "pkg/b"],
                [("pkg.a", "pkg.b"), ("pkg.b", "pkg.a"), ("pkg.a.extra", "pkg.b")],
            )
        ]
    )
    new_edge = compare_with_baseline(
        str(path),
        smaller_with_new_edge,
        expected_scope=SCOPE_PRODUCTION,
    )
    assert new_edge.new_dir == set()
    assert new_edge.new_dir_edges == {
        ("pkg/a|pkg/b", "pkg.a.extra -> pkg.b")
    }


def test_new_cycle_fails_and_removed_cycle_passes(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    write_baseline(str(path), _base_cycle(), scope=SCOPE_PRODUCTION)
    added = _result(
        dir_cycles=[
            (["pkg/a", "pkg/b"], [("pkg.a.service", "pkg.b.contract"), ("pkg.b.adapter", "pkg.a.contract")]),
            (["pkg/c", "pkg/d"], [("pkg.c.service", "pkg.d.contract"), ("pkg.d.adapter", "pkg.c.contract")]),
        ]
    )

    added_comparison = compare_with_baseline(str(path), added, expected_scope=SCOPE_PRODUCTION)
    removed_comparison = compare_with_baseline(str(path), _result(), expected_scope=SCOPE_PRODUCTION)

    assert added_comparison.new_dir == {"pkg/c|pkg/d"}
    assert added_comparison.has_new
    assert removed_comparison.clean


def test_changed_scan_roots_and_new_unresolved_dynamic_import_fail(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    baseline_result = _base_cycle()
    write_baseline(str(path), baseline_result, scope=SCOPE_PRODUCTION)

    changed_roots = _base_cycle()
    changed_roots["scan_roots"] = ["different"]
    with pytest.raises(CycleBaselineError, match="scan_roots"):
        compare_with_baseline(str(path), changed_roots, expected_scope=SCOPE_PRODUCTION)

    current = _base_cycle()
    current["unresolved_dynamic_imports"] = [
        {
            "file": "pkg/loader.py",
            "line": 9,
            "context": "lazy",
            "expression": "module_name",
        }
    ]
    comparison = compare_with_baseline(str(path), current, expected_scope=SCOPE_PRODUCTION)
    assert comparison.new_unresolved_dynamic_imports == {
        "pkg/loader.py|9|lazy|module_name"
    }
    assert comparison.has_new


def test_second_unresolved_dynamic_callsite_with_same_expression_fails(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    baseline = _base_cycle()
    baseline["unresolved_dynamic_imports"] = [
        {"file": "pkg/loader.py", "line": 9, "context": "lazy", "expression": "module_name"}
    ]
    write_baseline(str(path), baseline, scope=SCOPE_PRODUCTION)
    current = _base_cycle()
    current["unresolved_dynamic_imports"] = [
        {"file": "pkg/loader.py", "line": 9, "context": "lazy", "expression": "module_name"},
        {"file": "pkg/loader.py", "line": 19, "context": "lazy", "expression": "module_name"},
    ]

    comparison = compare_with_baseline(str(path), current, expected_scope=SCOPE_PRODUCTION)

    assert comparison.new_unresolved_dynamic_imports == {
        "pkg/loader.py|19|lazy|module_name"
    }
    assert comparison.has_new


def test_old_corrupt_future_and_wrong_scope_baselines_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    path.write_text('{"schema_version": 1}', encoding="utf-8")
    with pytest.raises(CycleBaselineError, match="schema_version=1"):
        load_baseline(str(path), expected_scope=SCOPE_PRODUCTION)

    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(CycleBaselineError, match="无法读取循环依赖基线"):
        load_baseline(str(path), expected_scope=SCOPE_PRODUCTION)

    path.write_text(
        json.dumps(
            {
                "schema_version": 99,
                "scope": SCOPE_PRODUCTION,
                "hard_dir_cycles": [],
                "hard_file_cycles": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(CycleBaselineError, match="schema_version=99"):
        load_baseline(str(path), expected_scope=SCOPE_PRODUCTION)

    write_baseline(str(path), _base_cycle(), scope=SCOPE_WITH_TESTS)
    with pytest.raises(CycleBaselineError, match="生产与含测试基线不可混用"):
        load_baseline(str(path), expected_scope=SCOPE_PRODUCTION)


def test_missing_baseline_fails_closed_in_gate_mode(monkeypatch, tmp_path: Path, capsys) -> None:
    missing = tmp_path / "missing.json"
    monkeypatch.setattr(scan_import_cycles, "scan", lambda _roots: _base_cycle())

    exit_code = scan_import_cycles.main(["--fail-on-new-cycle", "--baseline", str(missing)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert str(missing) in captured.err
    assert "--update-baseline" in captured.err
    assert "跳过新增判定" not in captured.out


def test_corrupt_and_unsupported_baseline_return_tool_error_without_traceback(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    path = tmp_path / "baseline.json"
    monkeypatch.setattr(scan_import_cycles, "scan", lambda _roots: _base_cycle())

    path.write_text("{broken", encoding="utf-8")
    assert scan_import_cycles.main(["--fail-on-new-cycle", "--baseline", str(path)]) == 2
    corrupt = capsys.readouterr()
    assert "无法读取循环依赖基线" in corrupt.err
    assert "Traceback" not in corrupt.err

    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scope": SCOPE_PRODUCTION,
                "hard_dir_cycles": [],
                "hard_file_cycles": [],
            }
        ),
        encoding="utf-8",
    )
    assert scan_import_cycles.main(["--fail-on-new-cycle", "--baseline", str(path)]) == 2
    unsupported = capsys.readouterr()
    assert "schema_version=1" in unsupported.err
    assert "Traceback" not in unsupported.err


def test_parse_error_and_scan_exception_fail_closed(monkeypatch, tmp_path: Path, capsys) -> None:
    path = tmp_path / "baseline.json"
    write_baseline(str(path), _base_cycle(), scope=SCOPE_PRODUCTION)
    incomplete = _result(parse_errors=[{"file": "pkg/broken.py", "error": "invalid syntax"}])
    monkeypatch.setattr(scan_import_cycles, "scan", lambda _roots: incomplete)

    assert scan_import_cycles.main(["--fail-on-new-cycle", "--baseline", str(path)]) == 2
    parse_failure = capsys.readouterr()
    assert "pkg/broken.py" in parse_failure.err
    assert "正式循环门禁已阻断" in parse_failure.err

    def explode(_roots: List[str]) -> dict:
        raise RuntimeError("scanner exploded")

    monkeypatch.setattr(scan_import_cycles, "scan", explode)
    assert scan_import_cycles.main(["--fail-on-new-cycle", "--baseline", str(path)]) == 2
    scan_failure = capsys.readouterr()
    assert "扫描自身异常" in scan_failure.err
    assert "scanner exploded" in scan_failure.err


def test_valid_baseline_passes_quiet_gate_mode(monkeypatch, tmp_path: Path, capsys) -> None:
    path = tmp_path / "baseline.json"
    current = _base_cycle()
    write_baseline(str(path), current, scope=SCOPE_PRODUCTION)
    monkeypatch.setattr(scan_import_cycles, "scan", lambda _roots: current)

    exit_code = scan_import_cycles.main(
        ["--fail-on-new-cycle", "--quiet-when-clean", "--baseline", str(path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    assert captured.err == ""
