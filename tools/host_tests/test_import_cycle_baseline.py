from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools import scan_import_cycles
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
from tools.scan_import_cycles import PRODUCTION_SCOPE_ROLES, WITH_TESTS_SCOPE_ROLES, scan


def _write_module(repo: Path, module: str, source: str) -> Path:
    """按模块名写夹具源码（包写成 `<包>.__init__`），返回写入的文件。"""
    target = repo.joinpath(*module.split(".")).with_suffix(".py")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    return target


def _scan(repo: Path) -> dict:
    return scan(PRODUCTION_SCOPE_ROLES, repo_root=str(repo))


def test_scan_scope_follows_path_roles_and_host_tests_count_only_with_tests(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    # 宿主工具函数体内导入宿主测试辅助模块，后者顶层导回工具：只有把测试角色纳入扫描时这个环才存在。
    _write_module(repo, "tools.runner", "def run():\n    from tools.host_tests.helper import VALUE\n    return VALUE\n")
    _write_module(repo, "tools.host_tests.helper", "from tools.runner import run\nVALUE = 1\n")
    _write_module(repo, "tests.test_runner", "from tools.runner import run\n")

    production = scan(PRODUCTION_SCOPE_ROLES, repo_root=str(repo))
    assert production["module_count"] == 1
    assert production["runtime_file_cycles"] == []

    with_tests = scan(WITH_TESTS_SCOPE_ROLES, repo_root=str(repo))
    assert with_tests["module_count"] == 3
    assert [record["members"] for record in with_tests["runtime_file_cycles"]] == [
        ["tools.host_tests.helper", "tools.runner"]
    ]


def test_line_drift_keeps_semantic_identity_clean_and_duplicate_call_ratchets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _write_module(
        repo,
        "core.loader",
        "import importlib.util\n"
        "def load_item(module_name, path):\n"
        "    return importlib.util.spec_from_file_location(module_name, path)\n",
    )
    monkeypatch.chdir(tmp_path)
    baseline_path = "bare_baseline.json"
    initial = _scan(repo)
    write_baseline(baseline_path, initial, scope=SCOPE_PRODUCTION)
    assert load_baseline(baseline_path, expected_scope=SCOPE_PRODUCTION) is not None

    # 1. Inserting unrelated lines above shifts physical line numbers without changing semantic identity.
    _write_module(
        repo,
        "core.loader",
        "# header comment\n"
        "import importlib.util\n"
        "\n"
        "X = 1\n"
        "def load_item(module_name, path):\n"
        "    return importlib.util.spec_from_file_location(module_name, path)\n",
    )
    shifted = _scan(repo)
    assert shifted["unresolved_dynamic_imports"][0]["line"] != initial["unresolved_dynamic_imports"][0]["line"]
    shifted_cmp = compare_with_baseline(baseline_path, shifted, expected_scope=SCOPE_PRODUCTION)
    assert shifted_cmp.clean is True
    assert not shifted_cmp.new_unresolved_dynamic_imports

    # 2. Adding a second identical call in the same lexical scope increments count (1 -> 2) and fails closed.
    _write_module(
        repo,
        "core.loader",
        "import importlib.util\n"
        "def load_item(module_name, path):\n"
        "    first = importlib.util.spec_from_file_location(module_name, path)\n"
        "    second = importlib.util.spec_from_file_location(module_name, path)\n"
        "    return first or second\n",
    )
    duplicated = _scan(repo)
    dup_cmp = compare_with_baseline(baseline_path, duplicated, expected_scope=SCOPE_PRODUCTION)
    assert dup_cmp.has_new is True
    assert any("(count 1 -> 2)" in item and "core/loader.py:3,4" in item for item in dup_cmp.new_unresolved_dynamic_imports)

    # 3. Two calls on the same line with different second arguments produce 2 distinct diagnostic entries.
    _write_module(
        repo,
        "core.loader",
        "import importlib.util\n"
        "def load_item(module_name, a, b):\n"
        "    return importlib.util.spec_from_file_location(module_name, a), importlib.util.spec_from_file_location(module_name, b)\n",
    )
    same_line_distinct = _scan(repo)
    distinct_cmp = compare_with_baseline(baseline_path, same_line_distinct, expected_scope=SCOPE_PRODUCTION)
    assert distinct_cmp.has_new is True
    assert len(distinct_cmp.new_unresolved_dynamic_imports) == 2


def test_function_body_back_edge_closes_delayed_cycles_that_the_baseline_blocks(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    for package in ("core", "core.a", "core.b"):
        _write_module(repo, f"{package}.__init__", "")
    _write_module(repo, "core.a.x", "from core.b.y import helper\nTHING = helper()\n")
    _write_module(repo, "core.b.y", "def helper():\n    return 1\n")
    baseline_path = str(tmp_path / "baseline.json")
    write_baseline(baseline_path, _scan(repo), scope=SCOPE_PRODUCTION)

    # 1. 函数体内导入只推迟加载：硬加载期图无环，延迟目录环与运行时文件环照样闭合并被拦下。
    _write_module(repo, "core.b.y", "def helper():\n    from core.a.x import THING\n    return THING\n")
    closed = _scan(repo)
    assert closed["hard_dir_cycles"] == [] and closed["hard_file_cycles"] == []
    blocked = compare_with_baseline(baseline_path, closed, expected_scope=SCOPE_PRODUCTION)
    assert blocked.has_new is True
    assert blocked.new_cycles == {
        "hard_dir_cycles": set(),
        "hard_file_cycles": set(),
        "delayed_dir_cycles": {"core/a|core/b"},
        "runtime_file_cycles": {"core.a.x|core.b.y"},
    }

    # 2. 接受现状后，同一对目录之间再加一条函数体内导入回边也算圈内新增锁定边（锁每条 lazy 模块边，不只每对目录的第一条）。
    write_baseline(baseline_path, closed, scope=SCOPE_PRODUCTION)
    late_module = _write_module(repo, "core.b.z", "def late():\n    from core.a.x import THING\n    return THING\n")
    widened = compare_with_baseline(baseline_path, _scan(repo), expected_scope=SCOPE_PRODUCTION)
    assert {name: edges for name, edges in widened.new_edges.items() if edges} == {
        "delayed_dir_cycles": {("core/a|core/b", "core.b.z -> core.a.x")},
    }
    assert not any(widened.new_cycles.values())

    # 3. 拆掉回边、环消失只减不增，相对基线干净。
    late_module.unlink()
    _write_module(repo, "core.b.y", "def helper():\n    return 1\n")
    assert compare_with_baseline(baseline_path, _scan(repo), expected_scope=SCOPE_PRODUCTION).clean


def _write_delayed_cycle_repo(repo: Path) -> None:
    # core.a.x -> core.b.y -> core.b.z 都是顶层导入，只有 core.b.z -> core.a.x 是函数体内导入：
    # 硬加载期图无环，运行时文件环 {x, y, z} 与延迟目录环 {core/a, core/b} 都靠这一条 lazy 边闭合。
    for package in ("core", "core.a", "core.b", "core.c"):
        _write_module(repo, f"{package}.__init__", "")
    _write_module(repo, "core.a.x", "from core.b.y import Y\nX = Y\n")
    _write_module(repo, "core.b.y", "from core.b.z import Z\nY = Z\n")
    _write_module(repo, "core.b.z", "Z = 1\ndef late():\n    from core.a.x import X\n    return X\n")


def test_delayed_cycles_lock_members_and_deferred_edges_but_not_top_level_imports(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_delayed_cycle_repo(repo)
    baseline_path = str(tmp_path / "baseline.json")
    write_baseline(baseline_path, _scan(repo), scope=SCOPE_PRODUCTION)
    file_cycle, dir_cycle = "core.a.x|core.b.y|core.b.z", "core/a|core/b"
    payload = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    assert payload["runtime_file_cycles"] == [
        {"members": file_cycle.split("|"), "edges": ["core.b.z -> core.a.x"]}
    ]
    assert payload["delayed_dir_cycles"] == [{"members": dir_cycle.split("|"), "edges": ["core.b.z -> core.a.x"]}]

    # 1. 反例：延迟环成员之间新增普通顶层导入（没闭合硬环）进了圈内边，但不锁，相对基线干净。
    _write_module(repo, "core.a.x", "from core.b.y import Y\nfrom core.b.z import Z\nX = Y + Z\n")
    widened = _scan(repo)
    for category, members in (("runtime_file_cycles", file_cycle), ("delayed_dir_cycles", dir_cycle)):
        [record] = widened[category]
        assert "|".join(record["members"]) == members
        assert [edge["kind"] for edge in record["edges"] if (edge["source"], edge["target"]) == ("core.a.x", "core.b.z")] == [
            "hard"
        ]
    assert compare_with_baseline(baseline_path, widened, expected_scope=SCOPE_PRODUCTION).clean

    # 2. 正例：圈内新增函数体内导入回边，两类延迟/运行时环都报圈内新增锁定边。
    _write_module(repo, "core.b.y", "from core.b.z import Z\nY = Z\ndef back():\n    from core.a.x import X\n    return X\n")
    back_edge = compare_with_baseline(baseline_path, _scan(repo), expected_scope=SCOPE_PRODUCTION)
    assert not any(back_edge.new_cycles.values())
    assert {name: edges for name, edges in back_edge.new_edges.items() if edges} == {
        "delayed_dir_cycles": {(dir_cycle, "core.b.y -> core.a.x")},
        "runtime_file_cycles": {(file_cycle, "core.b.y -> core.a.x")},
    }

    # 3. 正例：新目录/新模块经顶层导入 + 函数体内回边并进环，成员超集不再成立，报新增环。
    _write_module(repo, "core.b.y", "from core.b.z import Z\nfrom core.c.q import Q\nY = Z + Q\n")
    _write_module(repo, "core.c.q", "Q = 1\ndef late():\n    from core.a.x import X\n    return X\n")
    joined = compare_with_baseline(baseline_path, _scan(repo), expected_scope=SCOPE_PRODUCTION)
    assert joined.new_cycles == {
        "hard_dir_cycles": set(),
        "hard_file_cycles": set(),
        "delayed_dir_cycles": {"core/a|core/b|core/c"},
        "runtime_file_cycles": {"core.a.x|core.b.y|core.b.z|core.c.q"},
    }


def test_update_baseline_refuses_growth_without_allow_growth(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = tmp_path / "repo"
    _write_delayed_cycle_repo(repo)
    baseline_file = tmp_path / "baseline.json"
    repo_args = ["--repo-root", str(repo), "--baseline", str(baseline_file)]
    update = ["--update-baseline", *repo_args]
    assert scan_import_cycles.main(update) == 0
    accepted = baseline_file.read_text(encoding="utf-8")

    # 新增函数体内导入回边：默认拒绝写入，基线原样不动。
    _write_module(repo, "core.b.y", "from core.b.z import Z\nY = Z\ndef back():\n    from core.a.x import X\n    return X\n")
    capsys.readouterr()
    assert scan_import_cycles.main(update) == 1
    output = capsys.readouterr()
    assert "core.b.y -> core.a.x" in output.out
    assert "--allow-growth" in output.err
    assert baseline_file.read_text(encoding="utf-8") == accepted

    # 人工核对后加 --allow-growth 才写入；之后相对基线干净。
    assert scan_import_cycles.main([*update, "--allow-growth"]) == 0
    assert scan_import_cycles.main(["--fail-on-new-cycle", "--quiet-when-clean", *repo_args]) == 0

    # 只减不增的刷新不需要 --allow-growth。
    _write_module(repo, "core.b.y", "from core.b.z import Z\nY = Z\n")
    assert scan_import_cycles.main(update) == 0
    assert baseline_file.read_text(encoding="utf-8") == accepted

    # 扫描范围变化（旧基线 scan_roots 不同）：默认刷新要读旧基线比较，退出 2；
    # --allow-growth 与共用棘轮同一语义，人工核对后整份重写、不读旧基线。
    stale_roots = {**json.loads(accepted), "scan_roots": ["core", "tests"]}
    baseline_file.write_text(json.dumps(stale_roots), encoding="utf-8")
    capsys.readouterr()
    assert scan_import_cycles.main(update) == 2
    assert "scan_roots" in capsys.readouterr().err
    assert scan_import_cycles.main([*update, "--allow-growth"]) == 0
    assert baseline_file.read_text(encoding="utf-8") == accepted


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
    _write_module(
        repo,
        "core.loader",
        "import importlib.util\n"
        "def load_item(module_name, path):\n"
        "    return importlib.util.spec_from_file_location(module_name, path)\n",
    )
    baseline_path = str(tmp_path / "baseline.json")
    write_baseline(baseline_path, _scan(repo), scope=SCOPE_PRODUCTION)

    _write_module(repo, "core.loader", mutated_source)
    cmp_result = compare_with_baseline(
        baseline_path,
        _scan(repo),
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
    _write_module(
        repo,
        "core.loader",
        "import importlib\n"
        "def load_item(name):\n"
        "    return importlib.import_module(name)\n",
    )
    baseline_file = tmp_path / "baseline.json"
    write_baseline(str(baseline_file), _scan(repo), scope=SCOPE_PRODUCTION)

    # Scope mismatch
    with pytest.raises(CycleBaselineError, match="scope"):
        load_baseline(str(baseline_file), expected_scope=SCOPE_WITH_TESTS)

    base_payload = json.loads(baseline_file.read_text(encoding="utf-8"))

    # Schema version 3 (hard cycles only) rejected; v4 delayed/runtime cycle fields are required
    v3_payload = {**base_payload, "schema_version": 3}
    baseline_file.write_text(json.dumps(v3_payload), encoding="utf-8")
    with pytest.raises(CycleBaselineError, match="schema_version"):
        load_baseline(str(baseline_file), expected_scope=SCOPE_PRODUCTION)
    missing_delayed = {key: value for key, value in base_payload.items() if key != "delayed_dir_cycles"}
    baseline_file.write_text(json.dumps(missing_delayed), encoding="utf-8")
    with pytest.raises(CycleBaselineError, match="delayed_dir_cycles"):
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
