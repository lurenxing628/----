"""
回归测试：Excel 路由层不直接调用 *_no_tx（C02 收口）。
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _assert_no_tx_hidden(path: Path) -> None:
    txt = path.read_text(encoding="utf-8")
    if "_no_tx(" in txt:
        raise RuntimeError(f"检测到路由层仍直接调用 *_no_tx：{path}")


def test_excel_routes_no_tx_surface_hidden() -> None:
    repo_root = REPO_ROOT
    targets = [
        repo_root / "web" / "routes" / "domains" / "scheduler" / "scheduler_excel_batches.py",
        repo_root / "web" / "routes" / "personnel_excel_operator_calendar.py",
    ]
    for p in targets:
        _assert_no_tx_hidden(p)
