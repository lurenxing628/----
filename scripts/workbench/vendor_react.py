"""Explicit, pinned npm tarball import. Never invoked by an offline build."""

import base64
import hashlib
import io
import json
import tarfile
from pathlib import Path
from urllib.request import urlopen

from asset_sources import digest, write_json

ROOT = Path(__file__).resolve().parents[2]
VERSION = "18.3.1"
PINS = {
    "react": "sha512-wS+hAgJShR0KhEvPJArfuPVN1+Hz1t0Y6n5jLrGQbkb4urgPE/0Rve+1kMB1v/oWgHgm4WIcV+i7F2pTVj+2iQ==",
    "react-dom": "sha512-5m4nQKp+rZRb09LNH59GM4BxTh9251/ylbKIbpe7TpGxfJ+9kv6BLkLBXIjjspbgbnIBNqlI23tRnTWT0snUIw==",
}


def read_url(url):
    with urlopen(url, timeout=45) as response:
        if response.geturl() != url:
            raise ValueError("Unexpected registry redirect")
        return response.read()


def checked_payload(name):
    metadata_url = f"https://registry.npmjs.org/{name}/{VERSION}"
    metadata = json.loads(read_url(metadata_url))
    tarball = f"https://registry.npmjs.org/{name}/-/{name}-{VERSION}.tgz"
    if (metadata["name"], metadata["version"], metadata["license"], metadata["dist"]["integrity"],
            metadata["dist"]["tarball"]) != (name, VERSION, "MIT", PINS[name], tarball):
        raise ValueError("Pinned npm metadata mismatch: " + name)
    data = read_url(tarball)
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")
    if integrity != PINS[name]:
        raise ValueError("npm tarball integrity mismatch: " + name)
    members = {"umd/" + name + ".production.min.js": name + "-" + VERSION + ".production.min.js",
               "LICENSE": name + ".LICENSE", "package.json": name + ".package.json"}
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member, destination in members.items():
            entry = archive.getmember("package/" + member)
            if not entry.isfile():
                raise ValueError("Not a regular package member: " + member)
            files[destination] = archive.extractfile(entry).read()
    package = json.loads(files[name + ".package.json"])
    if package["version"] != VERSION or package["name"] != name or package["license"] != "MIT":
        raise ValueError("Package payload identity mismatch")
    if b"Permission is hereby granted" not in files[name + ".LICENSE"]:
        raise ValueError("Missing MIT license text")
    return {"name": name, "version": VERSION, "license": "MIT", "metadata_url": metadata_url,
            "tarball": tarball, "integrity": integrity, "tarball_sha256": digest(data)}, files


def main():
    destination = ROOT / "frontend/workbench/vendor"
    packages, files = [], {}
    for name in PINS:
        package, payload = checked_payload(name)
        packages.append(package)
        files.update(payload)
    records = []
    for name, data in sorted(files.items()):
        target = destination / name
        if target.exists() and target.read_bytes() != data:
            raise ValueError("Existing pinned vendor differs; refusing overwrite: " + name)
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in sorted(files.items()):
        (destination / name).write_bytes(data)
        records.append({"path": name, "sha256": digest(data), "size": len(data)})
    manifest = {"schema_version": 1, "packages": packages, "files": records,
                "scripts": [name + "-" + VERSION + ".production.min.js" for name in PINS]}
    write_json(destination / "vendor-manifest.json", manifest)
    print(json.dumps({"status": "verified_and_imported", "versions": [p["version"] for p in packages]}))


if __name__ == "__main__":
    main()
