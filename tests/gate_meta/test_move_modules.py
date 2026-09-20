"""tools.move_modules 合同：搬模块后所有导入、字符串点名与路径字面量一次改完，不留垫片。"""

import subprocess
import textwrap

import pytest

from tools import move_modules

FILES = {
    "pkg/__init__.py": '"""facade"""\n',
    "pkg/commands.py": "X = 1\n",
    "pkg/helper.py": "H = 2\n",
    "pkg/run_jobs.py": textwrap.dedent("""\
        from . import helper
        from .commands import X
        from .run_jobs_facts import F

        Job = (helper.H, X, F)
        """),
    "pkg/run_jobs_facts.py": "F = 3\n",
    "pkg/user.py": textwrap.dedent("""\
        from pkg import run_jobs, helper
        from .run_jobs import Job  # noqa: F401


        def inner():
            from .run_jobs_facts import (
                F,
            )
            return F
        """),
    "tests_dir/test_user.py": textwrap.dedent("""\
        import pkg.run_jobs as rj

        TARGET = "pkg.run_jobs.Job"
        PATH = "pkg/run_jobs.py"
        GLOB = "pkg/run_*.py"
        # 注释里也提到 pkg.run_jobs
        """),
}


def _repo(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    for name, text in FILES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    subprocess.run(["git", "add", "."], cwd=str(root), check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init"],
                   cwd=str(root), check=True)
    monkeypatch.setattr(move_modules, "ROOT", root)
    monkeypatch.setattr(move_modules, "SCAN_DIRS", ("pkg", "tests_dir"))
    return root


def _read(root, name):
    return (root / name).read_text(encoding="utf-8")


def test_move_rewrites_every_reference_form_and_keeps_local_names(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, monkeypatch)
    plan = move_modules.Plan({"pkg.run_jobs": "pkg.run.jobs", "pkg.run_jobs_facts": "pkg.run.jobs_facts"},
                             {"pkg/run_*.py": ["pkg/run_*.py", "pkg/run/**/*.py"]})
    assert move_modules.run(plan, apply=True) == 0
    assert not (root / "pkg/run_jobs.py").exists()
    assert _read(root, "pkg/run/__init__.py") == move_modules.INIT_DOC
    assert "__getattr__" not in _read(root, "pkg/run/__init__.py")
    assert _read(root, "pkg/run/jobs.py") == textwrap.dedent("""\
        from pkg import helper
        from pkg.commands import X

        from .jobs_facts import F

        Job = (helper.H, X, F)
        """)
    assert _read(root, "pkg/user.py") == textwrap.dedent("""\
        from . import helper
        from .run import jobs as run_jobs
        from .run.jobs import Job  # noqa: F401


        def inner():
            from .run.jobs_facts import F
            return F
        """)
    assert _read(root, "tests_dir/test_user.py") == textwrap.dedent("""\
        import pkg.run.jobs as rj

        TARGET = "pkg.run.jobs.Job"
        PATH = "pkg/run/jobs.py"
        GLOB = "pkg/run_*.py", "pkg/run/**/*.py"
        # 注释里也提到 pkg.run.jobs
        """)
    out = capsys.readouterr().out
    assert "搬后不再覆盖" not in out
    staged = subprocess.run(["git", "status", "--short"], cwd=str(root), capture_output=True, text=True).stdout
    assert "RM pkg/run_jobs.py -> pkg/run/jobs.py" in staged
    assert "A  pkg/run/__init__.py" in staged


def test_dry_run_changes_nothing_and_reports_globs_that_lose_coverage(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, monkeypatch)
    before = {name: _read(root, name) for name in FILES}
    assert move_modules.run(move_modules.Plan({"pkg.run_jobs": "pkg.run.jobs"}), apply=False) == 0
    assert {name: _read(root, name) for name in FILES} == before
    assert not (root / "pkg/run").exists()
    assert "tests_dir/test_user.py:5 glob pkg/run_*.py 搬后不再覆盖：pkg/run_jobs.py" in capsys.readouterr().out


def test_plain_import_without_alias_is_refused(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    (root / "tests_dir/test_plain.py").write_text("import pkg.run_jobs\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="没有 as 别名"):
        move_modules.run(move_modules.Plan({"pkg.run_jobs": "pkg.run.jobs"}), apply=False)


def test_string_rewrite_never_reapplies_to_its_own_output(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    (root / "pkg/trial.py").write_text("T = 1\n", encoding="utf-8")
    (root / "pkg/trial_catalog.py").write_text("C = 2\n", encoding="utf-8")
    (root / "tests_dir/test_names.py").write_text(
        'A = "pkg.trial_catalog"\nB = "pkg.trial.T"\nC = "pkg/trial.py"\nD = "pkg/trial_catalog.py"\n', encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(root), check=True)
    plan = move_modules.Plan({"pkg.trial": "pkg.trial.service", "pkg.trial_catalog": "pkg.trial.catalog"})
    assert move_modules.run(plan, apply=True) == 0
    assert _read(root, "tests_dir/test_names.py") == (
        'A = "pkg.trial.catalog"\nB = "pkg.trial.service.T"\nC = "pkg/trial/service.py"\nD = "pkg/trial/catalog.py"\n')


@pytest.mark.parametrize("moves,message", [
    ({"pkg.missing": "pkg.run.missing"}, "源模块不存在"),
    ({"pkg.run_jobs": "pkg.commands"}, "目标已存在"),
    ({"pkg.run_jobs": "pkg.run_jobs"}, "原地不动"),
    ({"pkg.run_jobs": "pkg.a", "pkg.helper": "pkg.a"}, "目标重复"),
])
def test_invalid_plans_fail_loudly(tmp_path, monkeypatch, moves, message):
    _repo(tmp_path, monkeypatch)
    with pytest.raises(SystemExit, match=message):
        move_modules.Plan(moves)
