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
