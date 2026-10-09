"""Exercise complete delivery parts, byte limits, and user-data exclusions."""
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts import portable_delivery, portable_release

ROOT = Path(__file__).resolve().parents[2]
TOOL_DIR = ROOT / "output/delivery-20261007/tools/extra"
POWERSHELL = Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")


def fixture_payload(tmp_path):
    payload = tmp_path / "APS_Portable"
    for name in portable_release.REQUIRED_FILES:
        target = payload / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"offline delivery fixture")
    (payload / portable_release.LAUNCHER).write_bytes(b"@echo off\r\nexit /b 0\r\n")
    (payload / portable_release.MARKER).write_bytes(b"APS portable directory\n")
    return payload


def invoke_delivery(monkeypatch, payload, volumes, tool_dir, output):
    monkeypatch.setattr(sys, "argv", ["portable_delivery", str(payload), str(volumes), str(tool_dir), str(output)])
    portable_delivery.main()


def test_archive_byte_limit_is_exclusive_and_contents_roundtrip(tmp_path):
    source = tmp_path / "input.bin"
    source.write_bytes(b"complete payload")
    package = tmp_path / "good.zip"
    portable_delivery.archive(package, [(source, "payload/input.bin")], 80_000_000)
    with zipfile.ZipFile(str(package)) as archive:
        assert archive.testzip() is None
        assert archive.read("payload/input.bin") == source.read_bytes()
    with pytest.raises(ValueError, match="reaches or exceeds"):
        portable_delivery.archive(tmp_path / "at-limit.zip", [(source, "payload/input.bin")], package.stat().st_size)


def test_crc_metadata_uses_standard_noncryptographic_crc(tmp_path):
    source = tmp_path / "input.bin"
    source.write_bytes(b"123456789")
    assert portable_delivery.record(source, "input.bin") == {"Path": "input.bin", "CRC32": "cbf43926", "Bytes": 9}


@pytest.mark.parametrize("runtime_name", ["user-data", "sample-context"])
def test_runtime_context_is_not_packaged(tmp_path, monkeypatch, runtime_name):
    payload = fixture_payload(tmp_path)
    (payload / runtime_name).mkdir()
    with pytest.raises(ValueError, match="runtime/user data|sample context"):
        invoke_delivery(monkeypatch, payload, tmp_path / "volumes", tmp_path / "tools", tmp_path / "release")


def test_parts_keep_switches_and_can_be_recovered_without_password_manifest(tmp_path, monkeypatch):
    payload = fixture_payload(tmp_path)
    packaging = tmp_path / "source/packaging/win7"
    packaging.mkdir(parents=True)
    for name in ("Install.cmd", "Install.ps1", "Start.cmd", "Start.ps1", "SampleOn.cmd", "SampleOff.cmd"):
        (packaging / name).write_text("fixture " + name + "\n", encoding="ascii")
    monkeypatch.setattr(portable_delivery, "REPO", tmp_path / "source")
    tools = tmp_path / "tools"
    (tools / "x64").mkdir(parents=True)
    for name in ("x64/7za.exe", "License.txt", "readme.txt"):
        (tools / name).write_bytes(b"delivery tool fixture")
    volumes = tmp_path / "volumes"
    volumes.mkdir()
    (volumes / "APS_Portable.7z.001").write_bytes(b"first payload part")
    (volumes / "APS_Portable.7z.002").write_bytes(b"second payload part")
    output = tmp_path / "release"
    invoke_delivery(monkeypatch, payload, volumes, tools, output)
    assert not (output / "SHA256SUMS.txt").exists()
    for index in (1, 2):
        with zipfile.ZipFile(str(output / f"APS_Win7_x64_{index:02d}.zip")) as archive:
            assert archive.testzip() is None
            assert archive.read(f"payload/APS_Portable.7z.{index:03d}") == (volumes / f"APS_Portable.7z.{index:03d}").read_bytes()
            assert all(item.filename.isascii() for item in archive.infolist())
            if index == 1:
                for name in ("Start.cmd", "Start.ps1", "SampleOn.cmd", "SampleOff.cmd"):
                    assert archive.read(name).endswith(b"\r\n")
                manifest = list(csv.DictReader(io.StringIO(archive.read("files.csv").decode("utf-8-sig"))))
                assert len(manifest) == len(portable_release.payload_files(payload))
                assert all("CRC32" in row and "SHA256" not in row for row in manifest)
    info = json.loads((output / "delivery.json").read_text(encoding="utf-8"))
    assert all(entry["Bytes"] < 80_000_000 for entry in info["archives"])
    assert all("CRC32" in entry for entry in info["archives"])


@pytest.mark.skipif(os.name != "nt" or not (TOOL_DIR / "x64/7za.exe").exists() or not POWERSHELL.exists(),
                    reason="Actual Windows PowerShell and cached offline 7-Zip are required")
def test_windows_installer_deploys_intact_parts_and_refuses_corruption(tmp_path, monkeypatch):
    if any(not (ROOT / "packaging/win7" / name).exists()
           for name in ("Start.cmd", "Start.ps1", "SampleOn.cmd", "SampleOff.cmd")):
        pytest.skip("Sample entrypoints are not yet available")
    payload = fixture_payload(tmp_path)
    (payload / "data.bin").write_bytes(os.urandom(9000))
    volumes = tmp_path / "volumes"
    volumes.mkdir()
    subprocess.run([str(TOOL_DIR / "x64/7za.exe"), "a", "-t7z", "-mx=0", "-v4096b",
                    str(volumes / "APS_Portable.7z"), payload.name], cwd=str(payload.parent),
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    release = tmp_path / "release"
    invoke_delivery(monkeypatch, payload, volumes, TOOL_DIR, release)
    archives = sorted(release.glob("*.zip"))
    assert len(archives) > 1

    def deploy_case(name, fault):
        case = tmp_path / name
        case.mkdir()
        for archive in archives:
            shutil.copyfile(str(archive), str(case / archive.name))
        bootstrap = case / "extract"
        with zipfile.ZipFile(str(archives[0])) as archive:
            archive.extractall(str(bootstrap))
        fault(case, bootstrap)
        result = subprocess.run([str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                 str(bootstrap / "Install.ps1"), "-NoOpen"], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=60)
        return result, bootstrap / "Application"

    result, application = deploy_case("用户 部署 !", lambda *_: None)
    assert result.returncode == 0, result.stdout.decode(errors="replace")
    for original in portable_release.payload_files(payload):
        assert (application / "APS_Portable" / original.relative_to(payload)).read_bytes() == original.read_bytes()
    for name in ("Start.cmd", "Start.ps1", "SampleOn.cmd", "SampleOff.cmd", "files.csv"):
        assert (application / name).is_file()
    assert not (application / "APS_Portable/user-data").exists()
    assert not (application / "sample-context").exists()

    def damage_zip(case, bootstrap):
        path = case / archives[1].name
        data = bytearray(path.read_bytes())
        with zipfile.ZipFile(str(path)) as archive:
            item = archive.infolist()[0]
            offset = item.header_offset + 30 + len(item.filename.encode("ascii")) + len(item.extra)
        data[offset] ^= 1
        path.write_bytes(data)

    result, application = deploy_case("damaged-same-size-zip", damage_zip)
    assert result.returncode == 1
    assert not application.exists()

    def existing_destination(case, bootstrap):
        (bootstrap / "Application").mkdir()
        (bootstrap / "Application/user-data.txt").write_bytes(b"keep original business data")

    result, application = deploy_case("existing-destination", existing_destination)
    assert result.returncode == 1
    assert (application / "user-data.txt").read_bytes() == b"keep original business data"
    assert list(application.iterdir()) == [application / "user-data.txt"]
