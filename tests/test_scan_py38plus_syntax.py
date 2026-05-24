from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

from tools import scan_py38plus_syntax as py38scan

REPO_ROOT = Path(__file__).resolve().parents[1]
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
    assert rules.count("PEP585_GENERIC_ALIAS") == 4
    assert rules.count("PEP604_UNION_TYPE") == 2
    assert all(finding.future_annotations for finding in findings)


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
    target.write_text("from __future__ import annotations\nVALUE: list[str] = []\n", encoding="utf-8")

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
