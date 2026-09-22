"""Python 3.8 checks distinguish runtime errors, deferred hints and unevaluated locals."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests._support.paths import REPO_ROOT
from tools import scan_py38plus_syntax as py38scan

SCAN_TOOL = REPO_ROOT / "tools" / "scan_py38plus_syntax.py"


def test_scan_source_reports_py310_match_as_py38_parse_rejected() -> None:
    findings = py38scan.scan_source(
        "sample.py",
        textwrap.dedent(
            """
            def classify(value):
                match value:
                    case 1:
                        return "one"
            """
        ).lstrip(),
        include_annotation_runtime=False,
    )

    assert len(findings) == 1
    assert findings[0].rule == "PY38_PARSE_REJECTED"
    assert findings[0].host_parser_accepts is (sys.version_info >= (3, 10))
    assert findings[0].introduced_in in {"", "3.10 / PEP 634"}
    assert findings[0].line == 2


def test_scan_source_reports_common_new_annotation_runtime_risks() -> None:
    findings = py38scan.scan_source(
        "sample.py",
        textwrap.dedent(
            """
            from __future__ import annotations
            from collections.abc import Sequence

            def normalize(items: list[str] | Sequence[int]) -> dict[str, int] | None:
                cache: tuple[str, int] = ("x", 1)
                return None
            """
        ).lstrip(),
    )

    rules = [finding.rule for finding in findings]
    assert rules.count("PEP585_GENERIC_ALIAS") == 3
    assert rules.count("PEP604_UNION_TYPE") == 2
    assert all(finding.future_annotations for finding in findings)
    assert all(finding.annotation_evaluation_required for finding in findings)
    assert py38scan.ScanResult(1, 0, findings).blocking_findings == ()


@pytest.mark.parametrize("prefix", ["", "from __future__ import annotations\n"])
def test_function_local_annotations_are_not_runtime_expressions(prefix) -> None:
    source = prefix + textwrap.dedent("""\
        def collect():
            cache: set[str] = set()
            if True:
                rows: list[int] = [1]
            return cache, rows
    """)
    assert py38scan.scan_source("sample.py", source) == ()
    namespace = {}
    exec(compile(source, "sample.py", "exec", dont_inherit=True), namespace)
    assert namespace["collect"]() == (set(), [1])


@pytest.mark.parametrize("source", [
    "def collect(items: set[str]) -> list[int]:\n    return []\n",
    "ROWS: list[int] = []\n",
    "class C:\n    rows: list[int] = []\n",
    "def outer():\n    class C:\n        rows: list[int] = []\n",
    "def outer():\n    def inner(rows: list[int]):\n        return rows\n",
])
def test_eager_annotations_still_block_in_their_own_lexical_scope(source) -> None:
    findings = py38scan.scan_source("sample.py", source)
    assert findings
    assert all(not finding.annotation_evaluation_required for finding in findings)
    assert all(finding.rule == "PEP585_GENERIC_ALIAS" for finding in findings)


def test_eager_union_annotation_remains_blocking() -> None:
    findings = py38scan.scan_source("sample.py", "def normalize(value: int | str):\n    return value\n")
    assert len(findings) == 1
    assert findings[0].rule == "PEP604_UNION_TYPE"
    assert not findings[0].annotation_evaluation_required


def test_read_failure_remains_blocking(tmp_path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("value = 1\n", encoding="utf-8")

    def fail_read(_path):
        raise OSError("cannot read source")

    monkeypatch.setattr(py38scan, "read_python_source", fail_read)
    result = py38scan.scan_paths(str(tmp_path), [source.name])
    assert result.skipped_files == len(result.blocking_findings) == 1
    assert result.blocking_findings[0].rule == "READ_ERROR"


@pytest.mark.parametrize("expression", [
    "Alias = list[str]", "value = set[str]()", "value: set[str] = set[str]()",
    "from collections.abc import Sequence as Seq\nAlias = Seq[int]",
    "from typing import cast\nvalue = cast(list[str], [])",
    "class C(list[str]):\n    pass",
])
def test_future_annotations_do_not_hide_runtime_generic_expressions(expression) -> None:
    source = "from __future__ import annotations\n" + expression + "\n"
    findings = py38scan.scan_source("sample.py", source)
    blockers = py38scan.ScanResult(1, 0, findings).blocking_findings
    assert len(blockers) == 1
    assert blockers[0].rule == "PEP585_GENERIC_ALIAS"


def test_scan_source_reports_non_parser_new_runtime_semantics() -> None:
    findings = py38scan.scan_source(
        "sample.py",
        textwrap.dedent(
            """
            CONFIG = {"a": 1} | {"b": 2}
            CONFIG |= {"c": 3}
            ok = isinstance(value, int | str)
            """
        ).lstrip(),
    )

    rules = [finding.rule for finding in findings]
    assert rules == [
        "PEP584_DICT_MERGE_OPERATOR",
        "PEP584_DICT_UPDATE_OPERATOR",
        "PEP604_RUNTIME_UNION_TYPE",
    ]
    assert [finding.introduced_in for finding in findings] == [
        "3.9 / PEP 584",
        "3.9 / PEP 584",
        "3.10 / PEP 604",
    ]


def test_scan_source_reports_pep646_variadic_generic_annotations_when_parser_supports_it() -> None:
    findings = py38scan.scan_source(
        "sample.py",
        "from __future__ import annotations\nShape: tuple[*Ts]\n",
    )

    if sys.version_info >= (3, 11):
        assert [finding.rule for finding in findings] == ["PEP646_VARIADIC_GENERIC"]
        assert findings[0].introduced_in == "3.11 / PEP 646"
    else:
        assert [finding.rule for finding in findings] == ["PY38_PARSE_REJECTED"]


def test_scan_source_reports_py311_py312_py314_parser_rejected_syntax_when_host_supports_it() -> None:
    samples = [
        ("except* ValueError", "3.11 / PEP 654"),
        ("def identity[T](value: T) -> T", "3.12 / PEP 695"),
        ("type Name = str", "3.12 / PEP 695 or 3.13 / PEP 696"),
        ("type Name[T = str] = T", "3.12 / PEP 695 or 3.13 / PEP 696"),
        ("t'hello {name}'", "3.14 / PEP 750"),
    ]
    for source, introduced_in in samples:
        findings = py38scan.scan_source("sample.py", source + "\n", include_annotation_runtime=False)
        assert [finding.rule for finding in findings] == ["PY38_PARSE_REJECTED"]
        if findings[0].host_parser_accepts:
            assert findings[0].introduced_in == introduced_in


def test_syntax_only_suppresses_runtime_semantic_risks() -> None:
    findings = py38scan.scan_source(
        "sample.py",
        "from __future__ import annotations\nVALUE: list[str] | None = None\nCONFIG = {'a': 1} | {'b': 2}\n",
        include_annotation_runtime=False,
    )

    assert findings == ()


def test_cli_json_output_and_fail_on_hit(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("VALUE: list[str] = []\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCAN_TOOL), "--root", str(tmp_path), "--json", "--fail-on-hit"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["scanned_files"] == 1
    assert payload["by_rule"] == {"PEP585_GENERIC_ALIAS": 1}
    assert payload["findings"][0]["rel_path"] == "sample.py"
    assert payload["findings"][0]["introduced_in"] == "3.9 / PEP 585"
    assert payload["blocking_findings"] == 1
    assert payload["annotation_evaluation_risks"] == 0


def test_cli_reports_deferred_risks_without_treating_them_as_runtime_failures(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("from __future__ import annotations\ndef rows() -> list[str]:\n    return []\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCAN_TOOL), "--root", str(tmp_path), "--json", "--fail-on-hit"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["total_findings"] == payload["annotation_evaluation_risks"] == 1
    assert payload["blocking_findings"] == 0
    assert payload["findings"][0]["annotation_evaluation_required"] is True
