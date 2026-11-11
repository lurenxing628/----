"""Explicit, pinned npm tarball import and esbuild vendor verification. Never invoked by an offline build."""

import argparse
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from urllib.request import urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.workbench.asset_sources import write_json  # noqa: E402

VERSION = "18.3.1"
PACKAGES = ("react", "react-dom")
ESBUILD_VERSION = "0.25.12"
ESBUILD_MANIFEST_PATH = SCRIPT_DIR / "esbuild-manifest.json"
ESBUILD_PLATFORMS = ("darwin-arm64", "darwin-x64", "win32-x64", "linux-x64")


def read_url(url):
    with urlopen(url, timeout=45) as response:
        if response.geturl() != url:
            raise ValueError("Unexpected registry redirect")
        return response.read()


def checked_payload(name):
    metadata_url = f"https://registry.npmjs.org/{name}/{VERSION}"
    metadata = json.loads(read_url(metadata_url))
    tarball = f"https://registry.npmjs.org/{name}/-/{name}-{VERSION}.tgz"
    if (metadata["name"], metadata["version"], metadata["license"], metadata["dist"]["tarball"]) != (
        name,
        VERSION,
        "MIT",
        tarball,
    ):
        raise ValueError("Pinned npm metadata mismatch: " + name)
    data = read_url(tarball)
    members = {"umd/" + name + ".production.min.js": name + "-" + VERSION + ".production.min.js",
               "LICENSE": name + ".LICENSE", "package.json": name + ".package.json"}
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member, destination in members.items():
            entry = archive.getmember("package/" + member)
            if not entry.isfile():
                raise ValueError("Not a regular package member: " + member)
            member_stream = archive.extractfile(entry)
            if member_stream is None:
                raise ValueError("Unable to extract package member: " + member)
            files[destination] = member_stream.read()
    package = json.loads(files[name + ".package.json"])
    if package["version"] != VERSION or package["name"] != name or package["license"] != "MIT":
        raise ValueError("Package payload identity mismatch")
    if b"Permission is hereby granted" not in files[name + ".LICENSE"]:
        raise ValueError("Missing MIT license text")
    return {
        "name": name,
        "version": VERSION,
        "license": "MIT",
        "metadata_url": metadata_url,
        "tarball": tarball,
    }, files


def current_esbuild_platform_key(node_executable=None):
    raw_node = node_executable or os.environ.get("WORKBENCH_NODE")
    node_bin = str(raw_node).strip() if raw_node is not None else ""
    if not node_bin:
        node_bin = shutil.which("node")
    if node_bin:
        try:
            completed = subprocess.run(
                [node_bin, "-p", "process.platform + '-' + process.arch"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            completed = None
        if completed is not None and completed.returncode == 0:
            detected = completed.stdout.strip()
            if detected not in ESBUILD_PLATFORMS:
                raise ValueError(f"Unsupported esbuild Node platform: {detected!r}")
            return detected
    plat = sys.platform.lower()
    arch = platform.machine().lower()
    if plat == "darwin":
        if arch in ("arm64", "aarch64"):
            return "darwin-arm64"
        if arch in ("x86_64", "amd64"):
            return "darwin-x64"
    elif plat in ("win32", "cygwin", "msys"):
        if arch in ("amd64", "x86_64"):
            return "win32-x64"
    elif plat.startswith("linux"):
        if arch in ("x86_64", "amd64"):
            return "linux-x64"
    raise ValueError(f"Unsupported esbuild host platform: {plat}/{arch}")


def load_esbuild_manifest(manifest_path=ESBUILD_MANIFEST_PATH):
    path = Path(manifest_path)
    if not path.is_file():
        raise ValueError(f"Missing esbuild manifest: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("Invalid esbuild manifest schema_version")
    if manifest.get("version") != ESBUILD_VERSION:
        raise ValueError(f"Pinned esbuild manifest version must be {ESBUILD_VERSION}, got {manifest.get('version')!r}")
    pkg = manifest.get("package")
    if not isinstance(pkg, dict) or pkg.get("name") != "esbuild" or pkg.get("version") != ESBUILD_VERSION:
        raise ValueError("Invalid esbuild package entry in manifest")
    if pkg.get("install_dir") != "vendor/node_modules/esbuild":
        raise ValueError("Unexpected esbuild install_dir in manifest")
    platforms = manifest.get("platforms")
    if not isinstance(platforms, dict):
        raise ValueError("Missing esbuild platforms mapping in manifest")
    for key in ESBUILD_PLATFORMS:
        entry = platforms.get(key)
        if not isinstance(entry, dict):
            raise ValueError(f"Missing esbuild platform entry in manifest: {key}")
        expected_name = f"@esbuild/{key}"
        expected_dir = f"vendor/node_modules/@esbuild/{key}"
        if entry.get("name") != expected_name or entry.get("version") != ESBUILD_VERSION:
            raise ValueError(f"Invalid esbuild platform identity for {key}")
        if entry.get("install_dir") != expected_dir:
            raise ValueError(f"Invalid esbuild platform install_dir for {key}")
    return manifest


def verify_esbuild_vendor(root=ROOT, platform_key=None, manifest_path=ESBUILD_MANIFEST_PATH, node_executable=None):
    repo_root = Path(root)
    manifest = load_esbuild_manifest(manifest_path)
    host_platform = current_esbuild_platform_key(node_executable=node_executable)
    target_platform = platform_key or host_platform
    platforms = manifest["platforms"]
    if target_platform not in platforms:
        raise ValueError(f"Unsupported esbuild platform key: {target_platform}")

    pkg_spec = manifest["package"]
    pkg_json_path = repo_root / pkg_spec["package_json"]
    main_js_path = repo_root / pkg_spec["main"]
    bin_path = repo_root / pkg_spec["bin"]
    for required_path in (pkg_json_path, main_js_path, bin_path):
        if not required_path.is_file():
            raise ValueError(f"Missing pinned esbuild file: {required_path.relative_to(repo_root).as_posix()}")

    pkg_payload = json.loads(pkg_json_path.read_text(encoding="utf-8"))
    if pkg_payload.get("name") != "esbuild" or pkg_payload.get("version") != ESBUILD_VERSION:
        raise ValueError(
            f"vendor/node_modules/esbuild/package.json must be esbuild@{ESBUILD_VERSION}, "
            f"got {pkg_payload.get('name')}@{pkg_payload.get('version')}"
        )
    optional_deps = pkg_payload.get("optionalDependencies") or {}
    for key in ESBUILD_PLATFORMS:
        dep_name = f"@esbuild/{key}"
        if optional_deps.get(dep_name) != ESBUILD_VERSION:
            raise ValueError(f"esbuild optionalDependencies[{dep_name!r}] must be {ESBUILD_VERSION}")

    for file_meta in (pkg_spec.get("files") or {}).values():
        rel_file = repo_root / file_meta["path"]
        if not rel_file.is_file():
            raise ValueError(f"Missing esbuild core file: {file_meta['path']}")
        expected_size = file_meta.get("size")
        if expected_size is not None and rel_file.stat().st_size != int(expected_size):
            raise ValueError(
                f"esbuild core file size mismatch for {file_meta['path']}: "
                f"expected {expected_size}, got {rel_file.stat().st_size}"
            )

    platform_spec = platforms[target_platform]
    platform_pkg_json_path = repo_root / platform_spec["package_json"]
    platform_binary_path = repo_root / platform_spec["binary"]
    if not platform_pkg_json_path.is_file():
        raise ValueError(f"Missing esbuild platform package.json: {platform_spec['package_json']}")
    if not platform_binary_path.is_file():
        raise ValueError(f"Missing esbuild platform binary: {platform_spec['binary']}")

    platform_pkg = json.loads(platform_pkg_json_path.read_text(encoding="utf-8"))
    if platform_pkg.get("name") != platform_spec["name"] or platform_pkg.get("version") != ESBUILD_VERSION:
        raise ValueError(
            f"{platform_spec['package_json']} must be {platform_spec['name']}@{ESBUILD_VERSION}, "
            f"got {platform_pkg.get('name')}@{platform_pkg.get('version')}"
        )
    expected_bin_size = platform_spec.get("binary_size")
    if expected_bin_size is not None and platform_binary_path.stat().st_size != int(expected_bin_size):
        raise ValueError(
            f"esbuild binary size mismatch for {platform_spec['binary']}: "
            f"expected {expected_bin_size}, got {platform_binary_path.stat().st_size}"
        )

    if target_platform == host_platform:
        completed = subprocess.run(
            [str(platform_binary_path), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        actual_version = completed.stdout.strip()
        if completed.returncode != 0 or actual_version != ESBUILD_VERSION:
            raise ValueError(
                f"esbuild binary version check failed for {platform_spec['binary']}: "
                f"returncode={completed.returncode} version={actual_version!r}"
            )

    return {
        "status": "verified",
        "version": ESBUILD_VERSION,
        "platform": target_platform,
        "package_json": pkg_spec["package_json"],
        "platform_package_json": platform_spec["package_json"],
        "binary": platform_spec["binary"],
    }


def _extract_npm_tarball_to_dir(tarball_bytes, expected_name, expected_version, target_dir):
    extracted_files = {}
    with tarfile.open(fileobj=io.BytesIO(tarball_bytes), mode="r:gz") as archive:
        for entry in archive.getmembers():
            if not entry.isfile() or not entry.name.startswith("package/"):
                continue
            rel_name = entry.name[len("package/"):].lstrip("/")
            if not rel_name or ".." in Path(rel_name).parts:
                raise ValueError(f"Unsafe archive member path: {entry.name}")
            member_stream = archive.extractfile(entry)
            if member_stream is None:
                raise ValueError(f"Unable to extract archive member: {entry.name}")
            extracted_files[rel_name] = (member_stream.read(), entry.mode)
    if "package.json" not in extracted_files:
        raise ValueError(f"Tarball for {expected_name} is missing package.json")
    pkg = json.loads(extracted_files["package.json"][0].decode("utf-8"))
    if pkg.get("name") != expected_name or pkg.get("version") != expected_version:
        raise ValueError(
            f"Tarball identity mismatch: expected {expected_name}@{expected_version}, "
            f"got {pkg.get('name')}@{pkg.get('version')}"
        )
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)
    for rel_name, (data, mode) in sorted(extracted_files.items()):
        dest = target_path / rel_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        if rel_name.startswith("bin/") or rel_name.endswith(".exe") or (mode & 0o111):
            os.chmod(dest, 0o755)


def install_esbuild_vendor(root=ROOT, platform_key=None, manifest_path=ESBUILD_MANIFEST_PATH, node_executable=None):
    repo_root = Path(root)
    manifest = load_esbuild_manifest(manifest_path)
    target_platform = platform_key or current_esbuild_platform_key(node_executable=node_executable)
    if target_platform not in manifest["platforms"]:
        raise ValueError(f"Unsupported esbuild platform key: {target_platform}")
    try:
        already_verified = verify_esbuild_vendor(
            root=repo_root,
            platform_key=target_platform,
            manifest_path=manifest_path,
            node_executable=node_executable,
        )
    except ValueError:
        already_verified = None
    if already_verified is not None:
        return {**already_verified, "status": "already_installed"}
    pkg_spec = manifest["package"]
    platform_spec = manifest["platforms"][target_platform]
    pkg_bytes = read_url(pkg_spec["tarball"])
    platform_bytes = read_url(platform_spec["tarball"])
    _extract_npm_tarball_to_dir(
        pkg_bytes,
        pkg_spec["name"],
        ESBUILD_VERSION,
        repo_root / pkg_spec["install_dir"],
    )
    _extract_npm_tarball_to_dir(
        platform_bytes,
        platform_spec["name"],
        ESBUILD_VERSION,
        repo_root / platform_spec["install_dir"],
    )
    verified = verify_esbuild_vendor(
        root=repo_root,
        platform_key=target_platform,
        manifest_path=manifest_path,
        node_executable=node_executable,
    )
    return {**verified, "status": "installed"}


def import_react_vendor(root=ROOT):
    destination = Path(root) / "frontend/workbench/vendor"
    packages, files = [], {}
    for name in PACKAGES:
        package, payload = checked_payload(name)
        packages.append(package)
        files.update(payload)
    records, existing = [], set()
    for name, data in sorted(files.items()):
        target = destination / name
        if target.exists():
            if target.read_bytes() != data:
                raise ValueError("Existing pinned vendor differs; refusing overwrite: " + name)
            existing.add(name)
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in sorted(files.items()):
        if name not in existing:
            (destination / name).write_bytes(data)
        records.append({"path": name, "size": len(data)})
    manifest = {"schema_version": 1, "packages": packages, "files": records,
                "scripts": [name + "-" + VERSION + ".production.min.js" for name in PACKAGES]}
    write_json(destination / "vendor-manifest.json", manifest)
    return {"status": "imported", "versions": [p["version"] for p in packages]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manage pinned workbench frontend vendor assets.")
    parser.add_argument("--check-esbuild", action="store_true", help="verify pinned esbuild vendor installation")
    parser.add_argument("--install-esbuild", action="store_true", help="download and install pinned esbuild vendor")
    parser.add_argument("--platform", default=None, help="optional esbuild platform key override")
    args = parser.parse_args(argv)
    if args.check_esbuild:
        print(json.dumps(verify_esbuild_vendor(ROOT, platform_key=args.platform)))
        return
    if args.install_esbuild:
        print(json.dumps(install_esbuild_vendor(ROOT, platform_key=args.platform)))
        return
    print(json.dumps(import_react_vendor(ROOT)))


if __name__ == "__main__":
    main()
