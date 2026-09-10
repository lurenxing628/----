"""Import the two prototype entry closures, preserving their relative paths."""

import argparse
import json
from pathlib import Path

from asset_sources import css_references, digest, local_path, parse_entry, write_json

REPO = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO / "前端设计"
DESTINATION = REPO / "frontend/workbench/prototype"
ENTRIES = {"index": "ui_kits/workbench/index.html", "trial": "ui_kits/workbench/trial-sample.html"}
LICENSES = ["ui_kits/workbench/assets/lucide-LICENSE"] + [
    "ui_kits/workbench/assets/vendor/" + name for name in
    ("react.LICENSE", "react-dom.LICENSE", "@babel-standalone.LICENSE")
]


def collect(source):
    entries = {key: parse_entry(source / name, source) for key, name in ENTRIES.items()}
    pending = list(ENTRIES.values()) + LICENSES
    for entry in entries.values():
        pending += entry["styles"] + entry["icons"]
        pending += [item["path"] for item in entry["scripts"]]
        for style in entry["inline_styles"]:
            pending += [local_path(source, (source / entry["path"]).parent, ref).relative_to(source).as_posix()
                        for ref in css_references(style["text"])]
    # DS embeds executable components; retain their sources as well as the exact bundle.
    first_line = (source / "_ds_bundle.js").read_text(encoding="utf-8").splitlines()[0]
    metadata = json.loads(first_line.split("@ds-bundle: ", 1)[1].rsplit(" */", 1)[0])
    pending += [item["sourcePath"] for item in metadata["components"]]
    files = {}
    while pending:
        name = pending.pop()
        if name in files:
            continue
        file = local_path(source, source, name)
        files[name] = file.read_bytes()
        if file.suffix == ".css":
            pending += [local_path(source, file.parent, ref).relative_to(source).as_posix()
                        for ref in css_references(files[name].decode("utf-8"))]
    return entries, files


def import_snapshot(source, destination, update=False):
    entries, files = collect(source.resolve())
    conflicts = [name for name, data in files.items()
                 if (destination / name).exists() and (destination / name).read_bytes() != data]
    if conflicts and not update:
        raise ValueError("Imported files changed; inspect before --update: " + ", ".join(conflicts))
    records = []
    for name, data in sorted(files.items()):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != data:
            target.write_bytes(data)
        records.append({"path": name, "source": "前端设计/" + name,
                        "target": "frontend/workbench/prototype/" + name,
                        "sha256": digest(data), "size": len(data)})
    manifest = {"schema_version": 1, "source_root": "前端设计", "entries": entries, "files": records,
                "inline_script_policy": "Archived for provenance only; never emitted into the live entry.",
                "rebuild_policy": "Normal builds read this snapshot only, never the ignored design directory."}
    write_json(destination / "source-manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    result = import_snapshot(args.source_root, DESTINATION, args.update)
    print(json.dumps({"status": "imported", "files": len(result["files"]),
                      "manifest": "frontend/workbench/prototype/source-manifest.json"}))


if __name__ == "__main__":
    main()
