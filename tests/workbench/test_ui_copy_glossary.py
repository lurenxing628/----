"""用户可见文案词表守卫：扫描器残留必须为 0。

词表决策：.codestable/compound/2026-09-13-decision-ui-copy-glossary.md
机器可读词表：tools/ui_copy_glossary.json（例外只能通过 allow 段加白名单，并写明理由）。
"""
import json
from pathlib import Path

from tools.scan_ui_copy import GLOSSARY_PATH, collect, load_glossary

ROOT = Path(__file__).resolve().parents[2]


def test_ui_copy_has_no_banned_terms():
    scan, rules, allow = load_glossary(GLOSSARY_PATH)
    hits = collect(scan, rules, allow)
    lines = [f"{h['file']}:{h['line']} [{h['term']}] {h['replace']} | {h['text']}" for h in hits]
    assert not hits, "用户可见文案里还有词表停用词（详见 python3 -m tools.scan_ui_copy）：\n" + "\n".join(lines[:40])


def test_allowlist_entries_explain_themselves():
    data = json.loads((ROOT / "tools" / "ui_copy_glossary.json").read_text(encoding="utf-8"))
    for item in data["allow"]:
        assert item.get("why") or item["path"].endswith("Outsourcing") or "outsourcing" in item["path"], item


def test_every_scanned_path_triggers_this_gate():
    """词表扫哪里，必跑组就得把哪里列进 input_file_scopes。

    这条门禁只有在被它守的文件触发时才会跑。2026-09-21 之前组里只覆盖了 frontend 一类，
    改说明书、改工作台服务层的提示语都不会触发它——一个停用词写进说明书第 14 章，
    跑到整目录全量才发现。词表以后扩范围，这条会先红。
    """
    import fnmatch

    from tools.test_registry_workbench_ui import WORKBENCH_UI_REQUIRED_REGRESSION_GROUPS

    group = next(item for item in WORKBENCH_UI_REQUIRED_REGRESSION_GROUPS
                 if item["group_id"] == "workbench_ui_refinement")
    scopes = group["input_file_scopes"]
    scan, _rules, _allow = load_glossary(GLOSSARY_PATH)

    uncovered = []
    for entry in (item for paths in scan.values() for item in paths):
        candidates = [str(path.relative_to(ROOT)) for path in ROOT.glob(entry)] or [entry]
        for candidate in candidates:
            files = ([str(path.relative_to(ROOT)) for path in (ROOT / candidate).rglob("*") if path.is_file()]
                     if (ROOT / candidate).is_dir() else [candidate])
            if not any(fnmatch.fnmatch(name, pattern) for name in files for pattern in scopes):
                uncovered.append(candidate)
    assert not uncovered, ("词表扫这些路径，但 workbench_ui_refinement 组的 input_file_scopes 没覆盖，"
                           "改它们不会触发文案门禁：\n  " + "\n  ".join(sorted(set(uncovered))))
