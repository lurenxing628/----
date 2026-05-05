from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_batch_materials_batch_info_uses_summary_cards() -> None:
    source = _read("templates/material/batch_materials.html")
    block = source[source.index("{% set batch_actions %}") : source.index("新增物料需求")]

    assert "ui.aps_card_header('批次信息'" in block
    assert "aps-summary-grid aps-batch-info-grid" in block
    assert "打开批次详情" in block
    for label in ("批次号", "图号", "数量", "当前齐套状态", "齐套日期"):
        assert f"ui.summary_item('{label}'" in block

    assert "info-sep" not in block
    assert "当前齐套状态：<strong>" not in block
    assert "批次：<strong>" not in block
