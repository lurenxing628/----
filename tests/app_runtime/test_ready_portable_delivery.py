"""Verify ready-to-run ZIP parts, exclusive byte limits, and pure-payload boundaries."""
import os
import sqlite3
import zipfile

import pytest

from scripts import portable_release, ready_portable_delivery
from tests.app_runtime.test_portable_delivery import fixture_payload


def ready_inputs(tmp_path):
    payload = fixture_payload(tmp_path)
    for name in (portable_release.README, portable_release.ACCEPTANCE):
        (payload / name).write_text("obsolete portable instructions\n", encoding="utf-8-sig")
    database = tmp_path / "business" / "aps.db"
    database.parent.mkdir()
    with sqlite3.connect(str(database)) as conn:
        conn.execute("CREATE TABLE delivery_example (name TEXT)")
        conn.execute("INSERT INTO delivery_example VALUES (?)", ("五分厂交付资料",))
    readme = tmp_path / "ready-instructions.txt"
    readme.write_bytes("排产系统离线版\n解压全部 ZIP 到同一目录。\r\n双击 APS\\Start.cmd。\n".encode())
    return payload, database, readme


def test_ready_parts_restore_complete_ascii_application_database_readme_and_licenses(tmp_path):
    payload, database, readme = ready_inputs(tmp_path)
    for name in ("LICENSE.txt", "tools/chrome109/LICENSE.chromium.html"):
        (payload / name).write_bytes(b"offline redistribution license\n")
    for index in range(3):
        (payload / f"library-part-{index}.bin").write_bytes(os.urandom(2048))
    sources = portable_release.payload_files(payload)
    mapped = {"排产系统.exe": "APS.exe", portable_release.LAUNCHER: "Start.cmd"}
    expected = {}
    for source in sources:
        relative = source.relative_to(payload).as_posix()
        if relative not in (portable_release.README, portable_release.ACCEPTANCE):
            expected["APS/" + mapped.get(relative, relative)] = source.read_bytes()
    readme_bytes = readme.read_text(encoding="utf-8-sig").replace("\n", "\r\n").encode("utf-8-sig")
    expected["APS/README.txt"] = readme_bytes
    expected["APS/user-data/db/aps.db"] = database.read_bytes()

    output = tmp_path / "ready-delivery"
    maximum = 3000
    parts = ready_portable_delivery.write_ready_portable_delivery(
        payload, database, readme, output, maximum_bytes=maximum)
    assert len(parts) > 1
    assert set(output.iterdir()) == set(parts) | {output / "README.txt"}
    assert (output / "README.txt").read_bytes() == readme_bytes
    restored = tmp_path / "direct-extract"
    seen = set()
    for part in parts:
        assert part.parent == output and part.suffix == ".zip"
        assert part.stat().st_size < maximum
        with zipfile.ZipFile(str(part)) as archive:
            assert archive.testzip() is None
            for entry in archive.infolist():
                assert entry.filename.isascii() and entry.filename.startswith("APS/")
                assert entry.compress_type == zipfile.ZIP_DEFLATED
                assert entry.filename not in seen, "Each source must occur in exactly one part"
                seen.add(entry.filename)
                assert archive.read(entry) == expected[entry.filename]
            archive.extractall(str(restored))
    assert seen == set(expected)
    assert {file.relative_to(restored).as_posix() for file in restored.rglob("*") if file.is_file()} == seen
    for name, content in expected.items():
        assert (restored / name).read_bytes() == content
    with sqlite3.connect(str(restored / "APS/user-data/db/aps.db")) as conn:
        assert conn.execute("SELECT name FROM delivery_example").fetchall() == [("五分厂交付资料",)]
    assert (payload / "排产系统.exe").is_file() and (payload / portable_release.LAUNCHER).is_file()
    assert not (payload / "user-data").exists()


def test_archive_byte_limit_uses_closed_zip_size_and_is_exclusive(tmp_path):
    source = tmp_path / "input.bin"
    source.write_bytes(b"complete deflated archive contents" * 10)
    output = tmp_path / "good.zip"
    actual_size = ready_portable_delivery.write_archive(output, [(source, "APS/input.bin")], 80_000_000)
    assert actual_size == output.stat().st_size
    with zipfile.ZipFile(str(output)) as archive:
        assert archive.getinfo("APS/input.bin").compress_type == zipfile.ZIP_DEFLATED
        assert archive.read("APS/input.bin") == source.read_bytes()
    with pytest.raises(ValueError):
        ready_portable_delivery.write_archive(tmp_path / "at-limit.zip", [(source, "APS/input.bin")], actual_size)
    assert ready_portable_delivery.write_archive(
        tmp_path / "below-limit.zip", [(source, "APS/input.bin")], actual_size + 1) == actual_size


def test_oversized_single_file_and_limit_above_80mb_never_publish_a_delivery(tmp_path):
    payload, database, readme = ready_inputs(tmp_path)
    source = payload / "oversized.bin"
    source.write_bytes(os.urandom(8192))
    single_size = ready_portable_delivery.write_archive(
        tmp_path / "single-file.zip", [(source, "APS/oversized.bin")], 80_000_000)
    for maximum, name in ((single_size, "at-single-file-limit"), (80_000_001, "above-delivery-limit")):
        output = tmp_path / name
        with pytest.raises(ValueError):
            ready_portable_delivery.write_ready_portable_delivery(
                payload, database, readme, output, maximum_bytes=maximum)
        assert not output.exists(), "A rejected delivery must not publish partial ZIPs"
    assert source.stat().st_size == 8192


def test_ready_delivery_reuses_runtime_rejections_and_requires_prepared_entries(tmp_path):
    cases = ("user-data", "assets/nested/history.DB", "tools/chrome109/User Data/Default/Preferences",
             "missing-marker", "empty-launcher")
    for index, name in enumerate(cases):
        case = tmp_path / str(index)
        case.mkdir()
        payload, database, readme = ready_inputs(case)
        if name == "missing-marker":
            (payload / portable_release.MARKER).unlink()
        elif name == "empty-launcher":
            (payload / portable_release.LAUNCHER).write_bytes(b"")
        elif name == "user-data":
            (payload / name).mkdir()
        else:
            target = payload / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"existing runtime state")
        output = case / "delivery"
        message = "runtime/user data" if index < 3 else "prepared|launcher"
        with pytest.raises(ValueError, match=message):
            ready_portable_delivery.write_ready_portable_delivery(payload, database, readme, output)
        assert not output.exists()


def test_windows_entry_mapping_collisions_and_unmapped_unicode_paths_are_rejected(tmp_path):
    for index, name in enumerate(("aps.EXE", "START.cmd", "说明.txt")):
        case = tmp_path / str(index)
        case.mkdir()
        payload, database, readme = ready_inputs(case)
        (payload / name).write_bytes(b"must not overwrite a mapped entry")
        output = case / "delivery"
        with pytest.raises(ValueError):
            ready_portable_delivery.write_ready_portable_delivery(payload, database, readme, output)
        assert not output.exists()
        assert (payload / name).read_bytes() == b"must not overwrite a mapped entry"
