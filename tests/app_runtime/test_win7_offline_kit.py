"""Offline kit integrity, Windows dependency completeness and build preflight failures."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess

import pytest

from scripts import check_win7_build as preflight
from scripts import prepare_win7_offline as offline
from tests._support.paths import REPO_ROOT


def _entry(contents=b"offline artifact"):
    return {"path": "wheels/example.whl", "size": len(contents),
            "sha256": hashlib.sha256(contents).hexdigest(), "url": "https://example.com/example.whl"}


def test_verify_is_offline_and_detects_same_size_corruption(tmp_path, monkeypatch):
    entry = _entry()
    target = tmp_path / entry["path"]
    target.parent.mkdir()
    target.write_bytes(b"offline artifact")
    monkeypatch.setattr(offline.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("verification used network"))
    offline.prepare("verify", tmp_path, [entry])
    target.write_bytes(b"corrupt artifact")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        offline.prepare("verify", tmp_path, [entry])
    target.unlink()
    with pytest.raises(ValueError, match="Missing"):
        offline.prepare("verify", tmp_path, [entry])


def test_download_rejects_bad_response_and_removes_partial_file(tmp_path, monkeypatch):
    import io

    entry = _entry()
    monkeypatch.setattr(offline.urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(b"wrong download"))
    with pytest.raises(ValueError, match="Size mismatch"):
        offline.prepare("download", tmp_path, [entry])
    assert not (tmp_path / entry["path"]).exists()
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.parametrize("path", ["../outside.whl", "/outside.whl", "C:/outside.whl", "wheels\\outside.whl"])
def test_manifest_rejects_paths_outside_kit(tmp_path, path):
    entry = dict(_entry(), path=path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"format_version": 1, "files": [entry]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsafe"):
        offline.load_manifest(manifest)


def test_manifest_and_build_lock_include_runtime_and_windows_dependencies():
    entries = {entry["name"].lower(): entry for entry in offline.load_manifest() if entry["path"].startswith("wheels/")}
    lock = (REPO_ROOT / "requirements-win7-build.txt").read_text(encoding="ascii")
    for filename in ("requirements.txt", "requirements-optimizer-lite-win7.txt"):
        for name, version in re.findall(r"^([\w-]+)==([\w.]+)", (REPO_ROOT / filename).read_text(), re.M):
            assert entries[name.lower()]["version"] == version
    assert entries["pyinstaller"]["version"] == "4.10"
    for name in ("pefile", "pywin32-ctypes", "colorama", "pyinstaller-hooks-contrib", "setuptools", "pip"):
        assert name in entries
    for entry in entries.values():
        assert entry["name"] + "==" + entry["version"] + " --hash=sha256:" + entry["sha256"] in lock
    assert len([line for line in lock.splitlines() if line and not line.startswith("#")]) == len(entries)


def test_preflight_reports_missing_and_mismatched_dependencies(monkeypatch):
    def version(name):
        if name == "Flask":
            raise preflight.metadata.PackageNotFoundError(name)
        return "6.0"
    monkeypatch.setattr(preflight.metadata, "version", version)
    entries = [{"name": "Flask", "version": "2.3.3", "path": "wheels/flask.whl"},
               {"name": "PyInstaller", "version": "4.10", "path": "wheels/pyinstaller.whl"}]
    errors = preflight.dependency_errors(entries)
    assert errors == ["Flask: expected 2.3.3, found missing", "PyInstaller: expected 4.10, found 6.0"]


def test_packaging_entrypoint_is_tracked_not_only_present_locally():
    if not (REPO_ROOT / ".git").exists():
        pytest.skip("Source archive has no Git index; file existence is covered by script contract tests")
    result = subprocess.run(["git", "ls-files", "--error-unmatch", "--",
                             ".limcode/skills/aps-package-win7/scripts/package_win7.ps1"],
                            cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert result.returncode == 0, "Win7 build entrypoint must be tracked in Git, not only present locally"


def test_download_existing_artifact_is_verified_once(tmp_path, monkeypatch):
    entry = _entry()
    target = tmp_path / entry['path']
    target.parent.mkdir()
    target.write_bytes(b'offline artifact')
    calls = []
    original = offline.verify_file
    def verify(path, metadata):
        calls.append(path)
        original(path, metadata)
    monkeypatch.setattr(offline, 'verify_file', verify)
    monkeypatch.setattr(offline.urllib.request, 'urlopen', lambda *args, **kwargs: pytest.fail('existing download used network'))
    offline.prepare('download', tmp_path, [entry])
    assert calls == [target]


def test_delivery_reuses_archive_and_tool_records(tmp_path, monkeypatch):
    from scripts import portable_delivery as delivery
    payload, volumes, sevenzip = (tmp_path / name for name in ('app', 'volumes', '7zip'))
    payload.mkdir()
    (payload / 'app.exe').write_bytes(b'payload')
    volumes.mkdir()
    for index in (1, 2):
        (volumes / f'APS_Portable.7z.{index:03d}').write_bytes(b'volume')
    (sevenzip / 'x64').mkdir(parents=True)
    (sevenzip / 'x64/7za.exe').write_bytes(b'tool')
    for name in ('License.txt', 'readme.txt'):
        (sevenzip / name).write_text('tool notice')
    monkeypatch.setattr(delivery, 'payload_files', lambda root: [payload / 'app.exe'])
    calls = []
    original = delivery.digest
    def digest(path):
        calls.append(path.name)
        return original(path)
    monkeypatch.setattr(delivery, 'digest', digest)
    monkeypatch.setattr('sys.argv', ['portable_delivery', str(payload), str(volumes), str(sevenzip), str(tmp_path / 'delivery')])
    delivery.main()
    assert calls.count('7za.exe') == 1
    assert calls.count('APS_Win7_x64_02.zip') == 1


def test_delivery_readme_keeps_acceptance_with_its_own_release():
    from scripts.portable_delivery import README_TEXT

    assert 'Install.cmd' in README_TEXT and 'tools 目录' in README_TEXT
    assert '本次交付记录' in README_TEXT
    assert not any(value in README_TEXT for value in ('d1307cb8', '2026-09-27', '2026-09-28', '26.03', '完全相同', '验收覆盖'))
