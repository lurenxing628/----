from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_v2_mirror_templates_stay_in_sync_for_shared_pages() -> None:
    pairs = (
        ("templates/dashboard.html", "web_new_test/templates/dashboard.html"),
        ("templates/scheduler/batches.html", "web_new_test/templates/scheduler/batches.html"),
        ("templates/scheduler/batches_manage.html", "web_new_test/templates/scheduler/batches_manage.html"),
        ("templates/scheduler/config.html", "web_new_test/templates/scheduler/config.html"),
        ("templates/scheduler/gantt.html", "web_new_test/templates/scheduler/gantt.html"),
    )
    for left, right in pairs:
        assert _read(left) == _read(right), f"{left} 和 {right} 已经不同步"


def main() -> None:
    test_v2_mirror_templates_stay_in_sync_for_shared_pages()
    print("OK")


if __name__ == "__main__":
    main()
