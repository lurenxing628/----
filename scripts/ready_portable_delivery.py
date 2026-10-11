"""Package a prepared Win7 application and one initial database as ready-to-extract ZIPs.

Run with ``python -m scripts.ready_portable_delivery PAYLOAD DATABASE README OUTPUT``.
"""
from __future__ import annotations

import argparse
import filecmp
import tempfile
import zipfile
from pathlib import Path
from typing import List, Sequence, Tuple

from scripts.portable_release import ACCEPTANCE, LAUNCHER, MARKER, README, payload_files

MAXIMUM_BYTES = 80_000_000
ARCHIVE_ROOT = "APS"
PayloadFile = Tuple[Path, str]
RENAMED_FILES = {"排产系统.exe": "APS.exe", LAUNCHER: "Start.cmd"}
OLD_DELIVERY_FILES = {"install.cmd", "install.ps1", "sampleon.cmd", "sampleoff.cmd", "7z.exe", "7za.exe"}


def write_archive(output: Path, files: Sequence[PayloadFile], maximum_bytes: int) -> int:
    """Write a normal Deflate ZIP and enforce the exclusive limit on its actual bytes."""
    with zipfile.ZipFile(str(output), "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=False) as archive:
        for source, relative in files:
            archive.write(str(source), relative)
    size = output.stat().st_size
    if size >= maximum_bytes:
        raise ValueError("ZIP reaches or exceeds the byte limit: " + str(output))
    return size


def delivery_files(payload: Path, database: Path) -> List[PayloadFile]:
    """Keep the existing pure-program boundary; only the named database crosses it."""
    files = payload_files(payload)
    for name in (MARKER, LAUNCHER):
        path = payload / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("Portable directory is not prepared: " + name)
    if (payload / "sample-context").exists():
        raise ValueError("Portable payload contains a sample context")
    if not database.is_file() or database.stat().st_size == 0:
        raise ValueError("Missing or empty initial database: " + str(database))
    result = []
    names = set()
    for source in files:
        relative = source.relative_to(payload).as_posix()
        if relative in (README, ACCEPTANCE):
            continue
        if source.name.lower() in OLD_DELIVERY_FILES or any(suffix.lower() == ".7z" for suffix in source.suffixes):
            raise ValueError("Portable payload contains an old installation/sample entry: " + relative)
        relative = ARCHIVE_ROOT + "/" + RENAMED_FILES.get(relative, relative)
        if not relative.isascii():
            raise ValueError("ZIP entry is not ASCII for the Win7 built-in extractor: " + relative)
        if relative.lower() in names:
            raise ValueError("Portable entry name collides after mapping: " + relative)
        names.add(relative.lower())
        result.append((source, relative))
    result.append((database, ARCHIVE_ROOT + "/user-data/db/aps.db"))
    return result


def archive_groups(files: Sequence[PayloadFile], temporary: Path, maximum_bytes: int) -> List[List[PayloadFile]]:
    """Measure real per-file ZIPs, then pack their conservative sizes largest first."""
    measured = []
    probe = temporary / "entry.zip"
    for entry in files:
        try:
            size = write_archive(probe, [entry], maximum_bytes)
        except (ValueError, zipfile.LargeZipFile) as exc:
            raise ValueError("A single file could not be packaged: " + entry[1] + ": " + str(exc)) from exc
        measured.append((size, entry))
    groups: List[List[PayloadFile]] = []
    sizes: List[int] = []
    for size, entry in sorted(measured, key=lambda item: item[0], reverse=True):
        for index, used in enumerate(sizes):
            if used + size < maximum_bytes:
                groups[index].append(entry)
                sizes[index] += size
                break
        else:
            groups.append([entry])
            sizes.append(size)
    return groups


def verify_extracted(archives: Sequence[Path], files: Sequence[PayloadFile], destination: Path) -> None:
    """Replay the user's extraction and compare its actual files directly to the inputs."""
    for path in archives:
        with zipfile.ZipFile(str(path)) as archive:
            archive.extractall(str(destination))
    extracted = {path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()}
    if extracted != {relative for _, relative in files}:
        raise ValueError("Extracted files do not match the complete delivery")
    for source, relative in files:
        if not filecmp.cmp(str(source), str(destination / relative), shallow=False):
            raise ValueError("Extracted content differs from its source: " + relative)


def write_ready_portable_delivery(payload: Path, database: Path, readme: Path, output: Path,
                                  name: str = "APS_Win7_x64", maximum_bytes: int = MAXIMUM_BYTES) -> List[Path]:
    """Produce all ordinary ZIP parts and their common Win7-readable instructions."""
    payload, database, readme, output = (path.resolve() for path in (payload, database, readme, output))
    if not 0 < maximum_bytes <= MAXIMUM_BYTES:
        raise ValueError("ZIP byte limit must be positive and at most 80,000,000")
    if not name or not name.isascii() or any(character in name for character in "/\\"):
        raise ValueError("Delivery name must be a single ASCII filename prefix")
    if payload == output or payload in output.parents:
        raise ValueError("ZIP output must be outside the portable payload directory")
    if output.exists():
        raise ValueError("Delivery output already exists: " + str(output))
    files = delivery_files(payload, database)
    text = readme.read_text(encoding="utf-8-sig")
    if not text.strip():
        raise ValueError("Ready-to-extract instructions are empty: " + str(readme))
    readme_bytes = text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8-sig")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aps_ready_delivery_", dir=str(output.parent)) as temp_name:
        temporary = Path(temp_name)
        prepared = temporary / "delivery"
        prepared.mkdir()
        instructions = prepared / "README.txt"
        instructions.write_bytes(readme_bytes)
        if any(relative.lower() == ARCHIVE_ROOT.lower() + "/readme.txt" for _, relative in files):
            raise ValueError("The payload already contains README.txt; supply only the independent instructions")
        files.append((instructions, ARCHIVE_ROOT + "/README.txt"))
        groups = archive_groups(files, temporary, maximum_bytes)
        archives = []
        for index, group in enumerate(groups, 1):
            path = prepared / (name + f"_{index:02d}.zip")
            write_archive(path, sorted(group, key=lambda entry: entry[1]), maximum_bytes)
            archives.append(path)
        verify_extracted(archives, files, temporary / "extracted")
        # Publish the completed set together; failed compression/extraction leaves no partial delivery.
        prepared.rename(output)
    return [output / path.name for path in archives]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("readme", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--name", default="APS_Win7_x64")
    parser.add_argument("--maximum-bytes", type=int, default=MAXIMUM_BYTES)
    args = parser.parse_args()
    try:
        archives = write_ready_portable_delivery(args.payload, args.database, args.readme, args.output,
                                                  args.name, args.maximum_bytes)
    except (OSError, ValueError, zipfile.LargeZipFile) as exc:
        parser.exit(1, "[ready portable] " + str(exc) + "\n")
    for path in archives:
        print(str(path) + " (" + str(path.stat().st_size) + " bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
