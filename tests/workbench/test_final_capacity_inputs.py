"""Small file-only checks for full-build freezing and product-input drift guards."""

import json

import pytest

from tests.workbench import final_capacity_assets
from tests.workbench.final_capacity_sources import ProductSourceFreeze, source_hashes
from tests.workbench.live_environment import sha256, write_json


@pytest.fixture
def asset_case(tmp_path, monkeypatch):
    repo, source, output = tmp_path / "repo", tmp_path / "main-build/static/workbench", tmp_path / "owned"
    for path in (repo / "templates/workbench", repo / "frontend/workbench/app", source / "app", output):
        path.mkdir(parents=True)
    data = b"window.capacity = true;"
    (source / "app/main.js").write_bytes(data)
    (repo / "frontend/workbench/app/main.js").write_bytes(data)
    (repo / "templates/workbench/index.html").write_text("<main></main>", encoding="utf-8")
    manifest = {"schema_version": 1, "target": "chrome109", "build_id": "known-build",
                "files": [{"path": "workbench/app/main.js", "bytes": len(data), "sha256": sha256(data)}],
                "inputs": [{"path": "frontend/workbench/app/main.js", "sha256": sha256(data)}]}
    write_json(source / "asset-manifest.json", manifest)
    monkeypatch.setattr(final_capacity_assets, "REPO", repo)
    return repo, source, output


def freeze(case, session="one"):
    _repo, source, output = case
    return final_capacity_assets.freeze_named_assets(output, session, asset_root=source,
        manifest_sha256=sha256((source / "asset-manifest.json").read_bytes()))


def test_asset_root_freezes_every_manifest_file_without_modifying_main_build(asset_case):
    _repo, source, _output = asset_case
    before = {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    result = freeze(asset_case)
    assert result["verified_file_count"] == result["verified_input_count"] == 1
    assert result["build_id"] == "known-build" and result["source_differences"] == []
    assert before == {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()}


@pytest.mark.parametrize("damage", ["bytes", "missing", "duplicate", "escape", "manifest_changed"])
def test_asset_root_rejects_incomplete_changed_or_escaping_build(asset_case, damage):
    _repo, source, output = asset_case
    path = source / "asset-manifest.json"
    expected = sha256(path.read_bytes())
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if damage == "bytes":
        (source / "app/main.js").write_bytes(b"different")
    elif damage == "missing":
        (source / "app/main.js").unlink()
    elif damage == "duplicate":
        manifest["files"].append(manifest["files"][0])
    elif damage == "escape":
        manifest["files"][0]["path"] = "../outside.js"
    else:
        manifest["build_id"] = "different-build"
    if damage in ("duplicate", "escape", "manifest_changed"):
        write_json(path, manifest)
        if damage != "manifest_changed":
            expected = sha256(path.read_bytes())
    with pytest.raises((ValueError, FileNotFoundError)):
        final_capacity_assets.freeze_named_assets(output, "rejected", asset_root=source, manifest_sha256=expected)


def test_product_input_freeze_rejects_even_content_restored_edits(tmp_path):
    repo, output = tmp_path / "repo", tmp_path / "output"
    (repo / "core").mkdir(parents=True)
    output.mkdir()
    (repo / "schema.sql").write_text("SELECT 1;", encoding="utf-8")
    path = repo / "core/code.py"
    path.write_text("value = 1\n", encoding="utf-8")
    before = source_hashes(repo)
    observer = ProductSourceFreeze(output, repo=repo)
    observer.start()
    path.write_text("value = 2\n", encoding="utf-8")
    path.write_text("value = 1\n", encoding="utf-8")
    proof = observer.finish()
    assert source_hashes(repo) == before
    assert proof["differences"] == [] and not proof["unchanged"]
    assert proof["watch_failure"]["paths"] == ["core/code.py"]
