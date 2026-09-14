"""Archive contracts use synthetic files; these are not Windows executable tests."""
from __future__ import annotations

import hashlib
import zipfile

import pytest

from scripts import portable_release as release


@pytest.fixture
def payload(tmp_path):
    root = tmp_path / "打包 目录"
    for relative in (
        "排产系统.exe", "python38.dll", "base_library.zip", "schema.sql",
        "static/workbench/prototype/styles.css", "static/workbench/app/main.js",
        "tools/chrome109/chrome.exe", "tools/chrome109/locales/zh-CN.pak",
        "tools/chrome109/locales/en-US.pak",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic payload, not executable")
    return root


def test_archive_preserves_complete_payload_and_publishes_verified_checksum(payload, tmp_path):
    release.prepare_portable_directory(payload)
    output = tmp_path / "output" / "APS_Portable_Win7_x64.zip"
    checksum = release.write_portable_archive(payload, output)
    assert hashlib.sha256(output.read_bytes()).hexdigest() == checksum
    assert output.with_suffix(".zip.sha256").read_text(encoding="ascii") == checksum + "  " + output.name + "\n"
    with zipfile.ZipFile(str(output)) as archive:
        expected = {"APS_Portable/" + p.relative_to(payload).as_posix(): p.read_bytes()
                    for p in payload.rglob("*") if p.is_file()}
        assert set(archive.namelist()) == set(expected)
        for name, contents in expected.items():
            assert archive.read(name) == contents
        readme = archive.read("APS_Portable/README_PORTABLE.txt")
        assert readme.startswith(b"\xef\xbb\xbf")
        assert "绿色便携版" in readme.decode("utf-8-sig")
        assert archive.testzip() is None


@pytest.mark.parametrize("relative", ["user-data/db/aps.db", "logs/aps_secret_key.txt",
                                     "backups/snapshot.zip", "tools/chrome109/Default/Preferences",
                                     "stray.db-wal", "chrome109_profile/Preferences"])
def test_archive_rejects_user_data_without_deleting_it(payload, tmp_path, relative):
    release.prepare_portable_directory(payload)
    data = payload / relative
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_bytes(b"preserve me")
    output = tmp_path / "portable.zip"
    with pytest.raises(ValueError, match="runtime/user data"):
        release.write_portable_archive(payload, output)
    assert data.read_bytes() == b"preserve me"
    assert not output.exists()


@pytest.mark.parametrize("relative", ["tools/chrome109/chrome.exe", "python38.dll",
                                     "tools/chrome109/locales/zh-CN.pak", "aps-portable.txt"])
def test_archive_refuses_incomplete_portable_payload(payload, tmp_path, relative):
    release.prepare_portable_directory(payload)
    (payload / relative).unlink()
    with pytest.raises(ValueError):
        release.write_portable_archive(payload, tmp_path / "portable.zip")


def test_archive_output_cannot_be_inside_payload(payload):
    release.prepare_portable_directory(payload)
    with pytest.raises(ValueError, match="outside"):
        release.write_portable_archive(payload, payload / "recursive.zip")


def test_archive_rejects_symlink_without_packaging_external_file(payload, tmp_path):
    release.prepare_portable_directory(payload)
    external = tmp_path / "external.txt"
    external.write_text("private", encoding="ascii")
    try:
        (payload / "linked.txt").symlink_to(external)
    except OSError:
        pytest.skip("symlinks unavailable on this host")
    with pytest.raises(ValueError, match="symlink"):
        release.write_portable_archive(payload, tmp_path / "portable.zip")
