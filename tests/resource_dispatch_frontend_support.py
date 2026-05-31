from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DISPATCH_TEMPLATE = REPO_ROOT / "templates" / "scheduler" / "resource_dispatch.html"
UI_CONTRACT_CSS = REPO_ROOT / "static" / "css" / "ui_contract.css"

_SCRIPT_RE = re.compile(r"filename='js/([^']+)'")
_SCRIPT_TAG_RE = re.compile(r"(<script\b[^>]*filename='js/([^']+)'[^>]*>\s*</script>)")
_RESOURCE_DISPATCH_SCRIPTS = {
    "resource_dispatch_shared.js",
    "resource_dispatch_core.js",
    "resource_execution.js",
    "resource_dispatch_boot.js",
}


def resource_dispatch_script_paths() -> Tuple[Path, ...]:
    template = RESOURCE_DISPATCH_TEMPLATE.read_text(encoding="utf-8")
    names = [
        name
        for name in _SCRIPT_RE.findall(template)
        if name in _RESOURCE_DISPATCH_SCRIPTS
    ]
    return tuple(REPO_ROOT / "static" / "js" / name for name in names)


def resource_dispatch_script_tags() -> Tuple[Tuple[str, str], ...]:
    template = RESOURCE_DISPATCH_TEMPLATE.read_text(encoding="utf-8")
    return tuple(
        (name, tag)
        for tag, name in _SCRIPT_TAG_RE.findall(template)
        if name in _RESOURCE_DISPATCH_SCRIPTS
    )


def read_resource_dispatch_script_bundle() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in resource_dispatch_script_paths())


def extract_js_function(source: str, function_name: str) -> str:
    marker = "function " + function_name
    start = source.index(marker)
    match = re.search(r"\n  function\s+", source[start + len(marker):])
    if not match:
        return source[start:]
    end = start + len(marker) + match.start()
    return source[start:end]
