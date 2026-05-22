from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

TEMPLATE_PATHS = (
    REPO_ROOT / "templates/scheduler/gantt.html",
    REPO_ROOT / "web_new_test/templates/scheduler/gantt.html",
)

RUNTIME_GANTT_PATHS = tuple(sorted((REPO_ROOT / "static/js").glob("gantt*.js"))) + (
    REPO_ROOT / "static/js/frappe-gantt.min.js",
)

SAVE_REQUEST_PATTERNS = (
    re.compile(r"\b(?:fetch|axios\.(?:post|put|patch))\s*\(", re.IGNORECASE),
    re.compile(r"\bmethod\s*:\s*['\"]?\s*(?:POST|PUT|PATCH)\b", re.IGNORECASE),
    re.compile(r"\b(save|submit|publish)[-_]?(?:draft|scenario|adjustment)\b", re.IGNORECASE),
    re.compile(r"\badjustments\s*/\s*(?:save|publish|draft)", re.IGNORECASE),
    re.compile(r"\bScheduleHistory\b|\bnew\s+Schedule\b"),
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_simulation_entry_shell_is_disabled_in_both_templates() -> None:
    for path in TEMPLATE_PATHS:
        text = _read(path)

        assert 'id="ganttSimulationEntryShell"' in text, path
        assert 'data-simulation-state="disabled"' in text, path
        assert 'id="ganttSimulationEntry"' in text, path
        assert "模拟调整（后续开放）" in text, path
        assert "disabled" in text, path
        assert 'aria-disabled="true"' in text, path
        assert "aps_gantt_simulation.css" in text, path
        assert 'data-gantt-mode="view"' in text, path
        assert 'data-gantt-mode="simulate"' not in text, path


def test_simulation_shell_has_no_save_or_publish_entry() -> None:
    forbidden = (
        "保存为模拟方案",
        "保存成功",
        "正式采用",
        "提交调整",
        "adjustments/save-draft",
        "save-draft",
        'method="post"',
        "method='post'",
    )
    for path in TEMPLATE_PATHS:
        text = _read(path)
        for marker in forbidden:
            assert marker not in text, f"{path} unexpectedly contains {marker!r}"


def test_gantt_runtime_does_not_add_adjustment_save_request() -> None:
    for path in RUNTIME_GANTT_PATHS:
        text = _read(path)
        if path.name == "gantt_boot.js":
            text = re.sub(r"function _withFetchTimeout[\s\S]*?async function loadAndRender", "async function loadAndRender", text)
        for pattern in SAVE_REQUEST_PATTERNS:
            assert not pattern.search(text), f"{path} unexpectedly matches {pattern.pattern!r}"


def test_manuals_explain_entry_is_placeholder_only() -> None:
    manual = _read(REPO_ROOT / "static/docs/scheduler_manual.md")
    help_model = _read(REPO_ROOT / "web/viewmodels/page_manuals_scheduler_outputs.py")

    for text in (manual, help_model):
        assert "模拟调整（后续开放）" in text
        assert "不能点击" in text
        assert "不会产生草稿" in text
        assert "正式新版本" in text
