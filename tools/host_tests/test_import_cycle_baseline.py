from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.import_cycle_analysis import dyn_imports
from tools.import_cycle_baseline import (
    SCOPE_PRODUCTION,
    SCOPE_WITH_TESTS,
    CycleBaselineError,
    compare_with_baseline,
    load_baseline,
    write_baseline,
)
from tools.import_cycle_graph import canonical_call_ast
from tools.scan_import_cycles import scan


def _write_pkg_file(repo: Path, rel: str, source: str) -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")


def test_line_drift_keeps_semantic_identity_clean_and_duplicate_call_ratchets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _write_pkg_file(
        repo,
        "pkg/loader.py",
        "import importlib.util\n"
        "def load_item(module_name, path):\n"
        "    return importlib.util.spec_from_file_location(module_name, path)\n",
    )
    monkeypatch.chdir(tmp_path)
    baseline_path = "bare_baseline.json"
    initial = scan(["pkg"], repo_root=str(repo))
    write_baseline(baseline_path, initial, scope=SCOPE_PRODUCTION)
    assert load_baseline(baseline_path, expected_scope=SCOPE_PRODUCTION) is not None

    # 1. Inserting unrelated lines above shifts physical line numbers without changing semantic identity.
    _write_pkg_file(
        repo,
        "pkg/loader.py",
        "# header comment\n"
        "import importlib.util\n"
        "\n"
        "X = 1\n"
        "def load_item(module_name, path):\n"
        "    return importlib.util.spec_from_file_location(module_name, path)\n",
    )
    shifted = scan(["pkg"], repo_root=str(repo))
    assert shifted["unresolved_dynamic_imports"][0]["line"] != initial["unresolved_dynamic_imports"][0]["line"]
    shifted_cmp = compare_with_baseline(baseline_path, shifted, expected_scope=SCOPE_PRODUCTION)
    assert shifted_cmp.clean is True
    assert not shifted_cmp.new_unresolved_dynamic_imports

    # 2. Adding a second identical call in the same lexical scope increments count (1 -> 2) and fails closed.
    _write_pkg_file(
        repo,
        "pkg/loader.py",
        "import importlib.util\n"
        "def load_item(module_name, path):\n"
        "    first = importlib.util.spec_from_file_location(module_name, path)\n"
        "    second = importlib.util.spec_from_file_location(module_name, path)\n"
        "    return first or second\n",
    )
    duplicated = scan(["pkg"], repo_root=str(repo))
    dup_cmp = compare_with_baseline(baseline_path, duplicated, expected_scope=SCOPE_PRODUCTION)
    assert dup_cmp.has_new is True
    assert any("(count 1 -> 2)" in item and "pkg/loader.py:3,4" in item for item in dup_cmp.new_unresolved_dynamic_imports)

    # 3. Two calls on the same line with different second arguments produce 2 distinct diagnostic entries.
    _write_pkg_file(
        repo,
        "pkg/loader.py",
        "import importlib.util\n"
        "def load_item(module_name, a, b):\n"
        "    return importlib.util.spec_from_file_location(module_name, a), importlib.util.spec_from_file_location(module_name, b)\n",
    )
    same_line_distinct = scan(["pkg"], repo_root=str(repo))
    distinct_cmp = compare_with_baseline(baseline_path, same_line_distinct, expected_scope=SCOPE_PRODUCTION)
    assert distinct_cmp.has_new is True
    assert len(distinct_cmp.new_unresolved_dynamic_imports) == 2


@pytest.mark.parametrize(
    "mutated_source",
    [
        # Second path argument changed
        "import importlib.util\n"
        "def load_item(module_name, other_path):\n"
        "    return importlib.util.spec_from_file_location(module_name, other_path)\n",
        # Keyword argument changed
        "import importlib.util\n"
        "def load_item(module_name, path):\n"
        "    return importlib.util.spec_from_file_location(module_name, location=path)\n",
        # Lexical scope changed
        "import importlib.util\n"
        "def other_scope(module_name, path):\n"
        "    return importlib.util.spec_from_file_location(module_name, path)\n",
        # Context changed from lazy (function) to hard (module top-level)
        "import importlib.util\n"
        "SPEC = importlib.util.spec_from_file_location(module_name, path)\n",
    ],
)
def test_argument_keyword_scope_or_context_mutation_is_blocked(tmp_path: Path, mutated_source: str) -> None:
    repo = tmp_path / "repo"
    _write_pkg_file(
        repo,
        "pkg/loader.py",
        "import importlib.util\n"
        "def load_item(module_name, path):\n"
        "    return importlib.util.spec_from_file_location(module_name, path)\n",
    )
    baseline_path = str(tmp_path / "baseline.json")
    write_baseline(baseline_path, scan(["pkg"], repo_root=str(repo)), scope=SCOPE_PRODUCTION)

    _write_pkg_file(repo, "pkg/loader.py", mutated_source)
    cmp_result = compare_with_baseline(
        baseline_path,
        scan(["pkg"], repo_root=str(repo)),
        expected_scope=SCOPE_PRODUCTION,
    )
    assert cmp_result.has_new is True
    assert any("(count 0 -> 1)" in item for item in cmp_result.new_unresolved_dynamic_imports)


def test_canonical_call_ast_is_identical_across_python_versions() -> None:
    expressions = [
        "importlib.import_module(paths[0])",
        "importlib.import_module(paths[:, 0])",
        "importlib.util.spec_from_file_location('\\U00030000', path)",
    ]
    local_outputs = [canonical_call_ast(ast.parse(expr, mode="eval").body) for expr in expressions]
    assert local_outputs == [
        "Call(func=Attribute(value=Name(id='importlib'), attr='import_module'), "
        "args=[Subscript(value=Name(id='paths'), slice=Constant(value=0))], keywords=[])",
        "Call(func=Attribute(value=Name(id='importlib'), attr='import_module'), "
        "args=[Subscript(value=Name(id='paths'), slice=Tuple(elts=[Slice(lower=None, upper=None, step=None), "
        "Constant(value=0)]))], keywords=[])",
        "Call(func=Attribute(value=Attribute(value=Name(id='importlib'), attr='util'), "
        "attr='spec_from_file_location'), args=[Constant(value='\\U00030000'), Name(id='path')], keywords=[])",
    ]
    module_source = (
        "import importlib.util\n"
        "def load_ext(path):\n"
        "    return importlib.util.spec_from_file_location('\\U00030000', path)\n"
    )
    _, unresolved = dyn_imports(ast.parse(module_source))
    local_dyn = [(item.expression, item.call_ast) for item in unresolved]
    assert local_dyn == [
        (
            "spec_from_file_location('\\U00030000')",
            "Call(func=Attribute(value=Attribute(value=Name(id='importlib'), attr='util'), "
            "attr='spec_from_file_location'), args=[Constant(value='\\U00030000'), Name(id='path')], keywords=[])",
        )
    ]
    repo_root = Path(__file__).resolve().parents[2]
    venv_python = repo_root / ".venv" / "bin" / "python"
    if venv_python.is_file() and venv_python.resolve() != Path(sys.executable).resolve():
        code = (
            "import ast, json; "
            "from tools.import_cycle_analysis import dyn_imports; "
            "from tools.import_cycle_graph import canonical_call_ast; "
            f"exprs = {expressions!r}; "
            f"mod_src = {module_source!r}; "
            "_, unresolved = dyn_imports(ast.parse(mod_src)); "
            "print(json.dumps({"
            "'ast': [canonical_call_ast(ast.parse(e, mode='eval').body) for e in exprs], "
            "'dyn': [[u.expression, u.call_ast] for u in unresolved]"
            "}))"
        )
        raw = subprocess.check_output([str(venv_python), "-c", code], cwd=str(repo_root), text=True)
        payload = json.loads(raw)
        assert payload["ast"] == local_outputs
        assert [tuple(item) for item in payload["dyn"]] == local_dyn


def test_load_baseline_rejects_scope_mismatch_old_schema_invalid_count_and_duplicate_keys(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_pkg_file(
        repo,
        "pkg/loader.py",
        "import importlib\n"
        "def load_item(name):\n"
        "    return importlib.import_module(name)\n",
    )
    baseline_file = tmp_path / "baseline.json"
    write_baseline(str(baseline_file), scan(["pkg"], repo_root=str(repo)), scope=SCOPE_PRODUCTION)

    # Scope mismatch
    with pytest.raises(CycleBaselineError, match="scope"):
        load_baseline(str(baseline_file), expected_scope=SCOPE_WITH_TESTS)

    base_payload = json.loads(baseline_file.read_text(encoding="utf-8"))

    # Schema version 2 rejected
    v2_payload = {**base_payload, "schema_version": 2}
    baseline_file.write_text(json.dumps(v2_payload), encoding="utf-8")
    with pytest.raises(CycleBaselineError, match="schema_version"):
        load_baseline(str(baseline_file), expected_scope=SCOPE_PRODUCTION)

    # Invalid counts: 0 and True (bool)
    for invalid_count in (0, -1, True, False, "1"):
        bad_row = {**base_payload["unresolved_dynamic_imports"][0], "count": invalid_count}
        bad_payload = {**base_payload, "unresolved_dynamic_imports": [bad_row]}
        baseline_file.write_text(json.dumps(bad_payload), encoding="utf-8")
        with pytest.raises(CycleBaselineError, match="count"):
            load_baseline(str(baseline_file), expected_scope=SCOPE_PRODUCTION)

    # Duplicate identity keys rejected
    row = base_payload["unresolved_dynamic_imports"][0]
    dup_payload = {**base_payload, "unresolved_dynamic_imports": [row, row]}
    baseline_file.write_text(json.dumps(dup_payload), encoding="utf-8")
    with pytest.raises(CycleBaselineError, match="重复身份键"):
        load_baseline(str(baseline_file), expected_scope=SCOPE_PRODUCTION)
