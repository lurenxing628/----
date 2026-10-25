"""Host-only contracts for tools.scan_over_defense; these tests do not enter the product gate."""

from __future__ import annotations

import json
import textwrap

from tools import scan_over_defense as scanner

PROD_SAMPLE = '''
import os
from copy import copy


class Holder:
    def __init__(self):
        self._value = 1

    def derive(self):
        derived = Holder()
        derived._value = 2
        return derived

    @classmethod
    def build(cls):
        built = cls.__new__(cls)
        built._value = 3
        return built

    def zz_unused_method(self):
        return self._value


def reflect_examples(obj, settings, name):
    first = getattr(obj, "zz_attr", None)
    second = hasattr(settings, "flag")
    third = getattr(os, "sep")
    fourth = getattr(obj, name)
    return first, second, third, fourth


def overwrite(value, keep):
    """The docstring is skipped before looking at the first statement."""
    value = compute_default()
    return value, keep


def reuse(value):
    value = value + 1
    return value


def read_first(value):
    print(value)
    value = 2
    return value


def compute_default():
    return 0


def smuggle(target, payload):
    target._cache = payload
    target._count += 1
    target._left, target._right = payload
    target.public = payload
    target.__mangled = payload
    os._zz_patch = payload
    cloned = copy(target)
    cloned._cache = None
    return cloned


module_holder = Holder()
module_holder._value = 9


def zz_dead_helper():
    return 1


def zz_only_tested_helper():
    return 2


def zz_tool_used_helper():
    return 3


def zz_frontend_used_helper():
    return 4


def register(func):
    return func


@register
def zz_decorated_hook():
    return 5


def outer():
    def zz_nested_unused():
        return 6
    return 7


def abc():
    return 8


EXAMPLE = Holder().derive()
__all__ = ["reflect_examples", "overwrite", "reuse", "read_first", "smuggle", "outer"]
'''

FRONTEND_COMPONENT = """
// backend helper mentioned by a contract string: zz_frontend_used_helper
export function Comp({ command, adapter }) {
  if (command.phase === 'rejected' && typeof command.reset === 'function') command.reset();
  if (typeof command.reset === "function") command.reset();
  if (typeof adapter.lookup === 'function') adapter.lookup();
}
"""


def _write(root, rel_path, text):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")


def _mini_repo(root):
    _write(root, "core/__init__.py", "")
    _write(root, "core/sample.py", PROD_SAMPLE)
    _write(root, "core/dup_a.py", "def zz_duplicate_name():\n    return 1\n")
    _write(root, "core/dup_b.py", "def zz_duplicate_name():\n    return 2\n")
    _write(root, "tests/test_sample.py", """
        from core.sample import zz_only_tested_helper


        def test_helper():
            assert zz_only_tested_helper() == 2
    """)
    _write(root, "tools/gen_doc.py", """
        from core.sample import zz_tool_used_helper

        print(zz_tool_used_helper())
    """)
    _write(root, "frontend/workbench/app/Comp.jsx", FRONTEND_COMPONENT)
    _write(root, "frontend/workbench/prototype/Proto.jsx", "if (typeof command.reset === 'function') command.reset();\n")


def _by_kind(result):
    grouped = {}
    for entry in result["entries"]:
        grouped.setdefault(entry["kind"], []).append(entry)
    return grouped


def _symbols(grouped, kind):
    return sorted(symbol for entry in grouped.get(kind, []) for symbol in entry["symbols"])


def test_scan_hits_each_signal_and_skips_exemptions(tmp_path):
    _mini_repo(tmp_path)
    result = scanner.scan(str(tmp_path))
    grouped = _by_kind(result)

    assert result["kind_totals"] == {
        "internal_reflect_literal": 2,
        "param_overwritten": 1,
        "zero_ref_func": 2,
        "test_only_func": 1,
        "foreign_private_attr_assign": 4,
        "js_typeof_command_reset": 2,
    }
    assert _symbols(grouped, "internal_reflect_literal") == ["getattr:zz_attr", "hasattr:flag"]
    assert _symbols(grouped, "param_overwritten") == ["overwrite(value)"]
    assert _symbols(grouped, "zero_ref_func") == ["zz_dead_helper", "zz_unused_method"]
    assert _symbols(grouped, "test_only_func") == ["zz_only_tested_helper"]
    assert _symbols(grouped, "foreign_private_attr_assign") == [
        "target._cache", "target._count", "target._left", "target._right",
    ]
    assert [(entry["path"], entry["lines"]) for entry in grouped["js_typeof_command_reset"]] == [
        ("frontend/workbench/app/Comp.jsx", [3, 4]),
    ]
    assert {entry["path"] for entry in grouped["internal_reflect_literal"]} == {"core/sample.py"}


def test_cli_refresh_then_fail_on_new_ratchet(tmp_path, capsys):
    _mini_repo(tmp_path)
    root = ["--repo-root", str(tmp_path)]

    assert scanner.main(root + ["--fail-on-new"]) == 2
    assert "基线缺失" in capsys.readouterr().err

    assert scanner.main(root + ["--refresh"]) == 0
    baseline_path = tmp_path / ".codestable" / "checkup" / "over_defense_baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert baseline["rule"] == "over_defense"
    assert sum(entry["count"] for entry in baseline["entries"]) == 12
    capsys.readouterr()

    assert scanner.main(root + ["--fail-on-new", "--quiet-when-clean"]) == 0
    assert capsys.readouterr().out == ""
    assert scanner.main(root + ["--fail-on-new"]) == 0
    assert "相对基线无新增债务" in capsys.readouterr().out

    _write(tmp_path, "core/extra.py", 'def run_extra(obj):\n    return getattr(obj, "late")\n\n\n__all__ = ["run_extra"]\n')
    with (tmp_path / "frontend/workbench/app/Comp.jsx").open("a", encoding="utf-8") as handle:
        handle.write("if (typeof command.reset === 'function') command.reset();\n")
    assert scanner.main(root + ["--fail-on-new"]) == 1
    out = capsys.readouterr().out
    assert "新增债务：core/extra.py kind=internal_reflect_literal count=1" in out
    assert "债务增加：frontend/workbench/app/Comp.jsx kind=js_typeof_command_reset 2 -> 3" in out

    assert scanner.main(root + ["--refresh"]) == 1
    assert "刷新被拒绝" in capsys.readouterr().err
    assert scanner.main(root + ["--refresh", "--allow-growth"]) == 0
    capsys.readouterr()
    assert scanner.main(root + ["--fail-on-new"]) == 0


def test_cli_json_and_parse_failure(tmp_path, capsys):
    _mini_repo(tmp_path)
    assert scanner.main(["--repo-root", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rule"] == "over_defense"
    assert payload["total"] == 12

    _write(tmp_path, "core/broken.py", "def broken(:\n    pass\n")
    assert scanner.main(["--repo-root", str(tmp_path), "--fail-on-new"]) == 2
    assert "源码解析失败" in capsys.readouterr().err
