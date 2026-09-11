"""Current plan asset admission errors; inputs are a client and missing path."""

import json
from pathlib import Path

from tests._support.gantt_current import prepare_read_state
from tests._support.gantt_retirement import _business_state
from tests._support.paths import REPO_ROOT


def assert_missing_asset(client, monkeypatch, relative):
    """Simulate only one missing declared asset, without changing any file."""
    before = prepare_read_state(client)
    root = Path(client.application.static_folder).resolve()
    assert root == (REPO_ROOT / "static").resolve()
    manifest = json.loads((root / "workbench/asset-manifest.json").read_text(encoding="utf-8"))
    assert relative in manifest["scripts"]
    target = (root / relative).resolve()
    assert target.is_file()
    assert client.get("/workbench?view=gantt").status_code == 200
    original = Path.is_file
    hits = []

    def exists(path):
        if path.resolve() == target:
            hits.append(str(path))
            return False
        return original(path)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "is_file", exists)
        response = client.get("/workbench?view=gantt")
    text = response.get_data(as_text=True)
    assert hits
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"
    assert "工作台资源文件缺失，请重新构建资源。" in text
    assert "workbench-boot" not in text
    assert relative not in text
    assert str(target) not in text
    assert client.get("/workbench?view=gantt").status_code == 200
    assert _business_state(client) == before
