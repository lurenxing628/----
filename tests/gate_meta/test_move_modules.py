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
        GLOBS = ["pkg/run_*.py"]
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
        GLOBS = ["pkg/run_*.py", "pkg/run/**/*.py"]
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


def test_redirect_retires_a_forwarding_shim_and_points_callers_at_the_real_module(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    (root / "pkg/legacy_helper.py").write_text("from .helper import H  # noqa: F401\n", encoding="utf-8")
    (root / "tests_dir/test_shim.py").write_text(
        "import pkg.legacy_helper as shim\nfrom pkg.legacy_helper import H\nTARGET = \"pkg.legacy_helper.H\"\n",
        encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(root), check=True)
    plan = move_modules.Plan({}, redirects={"pkg.legacy_helper": "pkg.helper"})
    assert move_modules.run(plan, apply=True) == 0
    assert not (root / "pkg/legacy_helper.py").exists()
    assert _read(root, "tests_dir/test_shim.py") == (
        "import pkg.helper as shim\nfrom pkg.helper import H\n\nTARGET = \"pkg.helper.H\"\n")
    tracked = subprocess.run(["git", "ls-files"], cwd=str(root), capture_output=True, text=True).stdout
    assert "pkg/legacy_helper.py" not in tracked


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


@pytest.mark.parametrize("redirects,message", [
    ({"pkg.missing": "pkg.helper"}, "垫片不存在"),
    ({"pkg.run_jobs": "pkg.missing"}, "垫片目标不存在"),
    ({"pkg.helper": "pkg.helper"}, "垫片指向自己"),
])
def test_invalid_redirects_fail_loudly(tmp_path, monkeypatch, redirects, message):
    _repo(tmp_path, monkeypatch)
    with pytest.raises(SystemExit, match=message):
        move_modules.Plan({}, redirects=redirects)


def _plan_jobs(root):
    return move_modules.Plan({"pkg.run_jobs": "pkg.run.jobs"}, {"pkg/run_*.py": ["pkg/run_*.py", "pkg/run/**/*.py"]})


def test_formfeed_and_unicode_line_separators_do_not_shift_rewrites(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    (root / "pkg/odd.py").write_text("TEXT = \"第一行\u2028第二行\"\n\x0c\nfrom pkg.run_jobs import Job\n\nX = Job\n", encoding="utf-8")
    subprocess.run(["git", "add", "pkg/odd.py"], cwd=str(root), check=True)
    assert move_modules.run(_plan_jobs(root), apply=True) == 0
    assert _read(root, "pkg/odd.py") == "TEXT = \"第一行\u2028第二行\"\n\x0c\nfrom .run.jobs import Job\n\nX = Job\n"


def test_glob_literal_outside_a_list_blocks_apply_and_writes_nothing(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, monkeypatch)
    (root / "pkg/reg.py").write_text('KEY = "pkg/run_*.py"\nFOUND = glob_files("pkg/run_*.py")\n', encoding="utf-8")
    subprocess.run(["git", "add", "pkg/reg.py"], cwd=str(root), check=True)
    before = {name: _read(root, name) for name in list(FILES) + ["pkg/reg.py"]}
    with pytest.raises(SystemExit, match="阻断项"):
        move_modules.run(_plan_jobs(root), apply=True)
    assert {name: _read(root, name) for name in before} == before
    assert (root / "pkg/run_jobs.py").exists() and not (root / "pkg/run").exists()
    out = capsys.readouterr().out
    assert "pkg/reg.py:1 glob 字面量 \"pkg/run_*.py\" 不是 list/tuple 的元素" in out
    assert "pkg/reg.py:2 glob 字面量" in out


def test_new_package_that_would_shadow_an_unmoved_module_is_refused(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    (root / "pkg/run.py").write_text("RUN = 1\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="同名模块会被新包遮蔽：pkg.run"):
        move_modules.Plan({"pkg.run_jobs": "pkg.run.jobs"})
    move_modules.Plan({"pkg.run_jobs": "pkg.run.jobs", "pkg.run": "pkg.run.service"})


def test_rewritten_source_that_fails_to_parse_aborts_before_any_write(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    before = {name: _read(root, name) for name in FILES}
    monkeypatch.setattr(move_modules, "rewrite_imports", lambda source, rewriter, where: (source + "def (\n", []))
    with pytest.raises(SystemExit, match="改写结果无法解析"):
        move_modules.run(_plan_jobs(root), apply=True)
    assert {name: _read(root, name) for name in FILES} == before
    assert (root / "pkg/run_jobs.py").exists() and not (root / "pkg/run").exists()


def test_crlf_files_keep_their_line_endings(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    with (root / "pkg/crlf.py").open("w", encoding="utf-8", newline="") as handle:
        handle.write("from pkg.run_jobs import Job\r\n\r\nX = Job\r\n")
    subprocess.run(["git", "add", "pkg/crlf.py"], cwd=str(root), check=True)
    assert move_modules.run(_plan_jobs(root), apply=True) == 0
    with (root / "pkg/crlf.py").open(encoding="utf-8", newline="") as handle:
        assert handle.read() == "from .run.jobs import Job\r\n\r\nX = Job\r\n"


@pytest.mark.parametrize("text,body", [('"pkg/run_*/conf"', "pkg/run_*/conf"), ("r'a/b*f'", "a/b*f"), ('rb"x"', "x"), ("plain", "plain")])
def test_literal_body_strips_prefixes_and_quotes_without_eating_the_glob(text, body):
    assert move_modules._literal_body(text) == body
