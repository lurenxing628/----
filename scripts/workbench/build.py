"""Build tracked workbench sources offline; Python 3.8 and Node on the build host only."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from asset_sources import (
    asset_mime,
    css_references,
    digest,
    license_origin,
    load_json,
    local_path,
    parse_entry,
    script_dependencies,
    stylesheet_dependencies,
    unknown_license,
    verify_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent


def compile_sources(node, prototype, order, sources, combined=False):
    request = {"babel_path": str(prototype / order["babel"]["path"]),
               "sources": sources, "check_combined": combined}
    result = subprocess.run([node, str(TOOLS / "compile.cjs")], input=json.dumps(request),
                            text=True, encoding="utf-8", capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Node compiler failed")
    return json.loads(result.stdout)["outputs"]


def read_inputs(root):
    prototype = root / "frontend/workbench/prototype"
    snapshot = load_json(prototype / "source-manifest.json")
    paths = verify_snapshot(prototype, snapshot)
    order = load_json(TOOLS / "build-order.json")
    if order["target"] != "chrome109" or order["babel"]["version"] != "7.29.0":
        raise ValueError("Build target/compiler must remain pinned")
    if order["babel"]["path"] not in paths:
        raise ValueError("Compiler is missing from the imported snapshot")
    for entry in snapshot["entries"].values():
        if parse_entry(prototype / entry["path"], prototype) != entry:
            raise ValueError("Imported entry manifest no longer matches HTML: " + entry["path"])
    return prototype, snapshot, paths, order


def check_prototype(root, node):
    prototype, snapshot, paths, order = read_inputs(root)
    sources = [{"path": name, "code": (prototype / name).read_text(encoding="utf-8"),
                "source_type": "module" if name.startswith("components/") else "script"}
               for name in sorted(paths) if Path(name).suffix in (".js", ".jsx") and "/vendor/" not in name]
    outputs = compile_sources(node, prototype, order, sources)
    return {"status": "prototype_compile_checked", "target": "chrome109", "compiled": len(outputs),
            "snapshot_files": len(snapshot["files"]), "live_published": False}


def live_inputs(root, order):
    app = root / "frontend/workbench/app"
    required = [order["theme"]] + order["live"]
    if len(required) != len(set(required)):
        raise ValueError("Duplicate live source in explicit build order")
    pending = order.get("pending_live", [])
    if (not isinstance(pending, list) or any(type(name) is not str or Path(name).name != name
            or "\\" in name or Path(name).suffix not in (".js", ".jsx") for name in pending)
            or len(pending) != len(set(pending)) or set(pending) & set(required)):
        raise ValueError("Pending live sources must be explicit unique unpublished script names")
    found = {file.name for file in app.glob("*") if file.suffix in (".js", ".jsx")}
    missing, extra = sorted(set(required) - found), sorted(found - set(required) - set(pending))
    if missing or extra:
        raise ValueError("Live sources not ready; missing=" + ",".join(missing) + "; unlisted=" + ",".join(extra))
    return [{"path": "app/" + name, "code": local_path(app, app, name).read_text(encoding="utf-8")}
            for name in required]


def style_assets(prototype, snapshot):
    payload, ordered = {}, []
    pending = []
    for entry in snapshot["entries"].values():
        for name in entry["styles"]:
            public = "workbench/prototype/" + name
            if public not in ordered:
                ordered.append(public)
            pending.append(name)
        # CSS originally followed the link list. Inline theme scripts are not published.
        if entry["inline_styles"]:
            name = Path(entry["path"]).with_suffix(".inline.css").as_posix()
            text = "\n".join(style["text"] for style in entry["inline_styles"])
            public = "workbench/prototype/" + name
            ordered.append(public)
            payload[public] = text.encode("utf-8")
            pending += [local_path(prototype, (prototype / name).parent, ref).relative_to(prototype).as_posix()
                        for ref in css_references(text)]
    pending += snapshot["entries"]["index"]["icons"]
    while pending:
        name = pending.pop()
        public = "workbench/prototype/" + name
        if public in payload:
            continue
        file = local_path(prototype, prototype, name)
        payload[public] = file.read_bytes()
        if file.suffix == ".css":
            pending += [local_path(prototype, file.parent, ref).relative_to(prototype).as_posix()
                        for ref in css_references(payload[public].decode("utf-8"))]
    return payload, ordered


def asset_records(root, payload, scripts, theme_script, foundation_path, order, snapshot, vendor_manifest, node):
    prototype = root / "frontend/workbench/prototype"

    def source_hash(source):
        file = TOOLS / source[len("scripts/workbench/"):] if source.startswith("scripts/workbench/") else root / source
        return digest(file.read_bytes())

    script_refs = script_dependencies(node, prototype / order["babel"]["path"], payload,
                                      [theme_script] + scripts, scripts[:2])
    inline_origins = {"workbench/prototype/" + Path(entry["path"]).with_suffix(".inline.css").as_posix():
                      ["frontend/workbench/prototype/" + entry["path"]]
                      for entry in snapshot["entries"].values() if entry["inline_styles"]}
    live_origins = {"workbench/app/" + Path(name).with_suffix(".js").as_posix(): ["frontend/workbench/app/" + name]
                    for name in [order["theme"]] + order["live"]}
    foundation_origins = ["frontend/workbench/prototype/" + item["path"] for item in order["foundation"]]
    foundation_origins.append("scripts/workbench/build-order.json")
    vendor_source = "frontend/workbench/vendor/vendor-manifest.json"
    vendor_licenses = {}
    for package, public in zip(vendor_manifest["packages"], scripts[:2]):
        name = package["name"]
        if public != f"workbench/vendor/{name}-{package['version']}.production.min.js":
            raise ValueError("Pinned UMD filename/package order mismatch")
        notice = license_origin(root, name, ["MIT"], "frontend/workbench/vendor/" + name + ".LICENSE",
                                "workbench/vendor/" + name + ".LICENSE", f"Distributed {name} package payload/notice only.",
                                {"path": vendor_source, "sha256": digest((root / vendor_source).read_bytes()),
                                 "package": name, "version": package["version"], "integrity": package["integrity"]})
        vendor_licenses[public] = notice
        vendor_licenses[notice["source"]["asset_path"]] = notice
    lucide_path = "workbench/prototype/ui_kits/workbench/assets/lucide-LICENSE"
    lucide = license_origin(root, "Lucide icon subset", ["ISC", "MIT"],
                            "frontend/workbench/prototype/ui_kits/workbench/assets/lucide-LICENSE", lucide_path,
                            "Embedded Lucide icon data only. The local notice also retains Feather-derived icon MIT terms; it does not license project code.")
    records = []
    for name, data in sorted(payload.items()):
        mime = asset_mime(name)
        dependencies = [item["path"] for item in script_refs.get(name, [])]
        if mime == "text/css":
            dependencies = stylesheet_dependencies(name, data, payload)
        if name == foundation_path:
            origins = foundation_origins
        elif name in live_origins:
            origins = live_origins[name]
        elif name in inline_origins:
            origins = inline_origins[name]
        else:
            origins = ["frontend/workbench/" + name[len("workbench/"):]]
        sources = [{"path": source, "sha256": source_hash(source)} for source in origins]
        if name in vendor_licenses:
            licenses = [vendor_licenses[name]]
        elif name == lucide_path:
            licenses = [lucide]
        else:
            font = mime.startswith("font/")
            licenses = [unknown_license("Imported font" if font else "Workbench project content", sources,
                         "No font redistribution license is recorded with this imported font; confirm rights separately."
                         if font else "No applicable project license is recorded in the imported source manifests; confirm the project grant separately.")]
            if name == foundation_path:
                licenses.append(lucide)
        records.append({"path": name, "sha256": digest(data), "bytes": len(data), "mime": mime,
                        "dependencies": dependencies, "dependency_symbols": script_refs.get(name, []),
                        "license_sources": licenses, "source_files": sources})
    for row in records:
        for origin in row["license_sources"]:
            source = origin["source"]
            if source and (source["asset_path"] not in payload or digest(payload[source["asset_path"]]) != source["sha256"]):
                raise ValueError("Published license notice missing or different: " + source["path"])
    return records


def build(root, output, node):
    prototype, snapshot, paths, order = read_inputs(root)
    live = live_inputs(root, order)
    forbidden = set(order["never_live"])
    sources = [{"path": "foundation-bootstrap.js", "code": order["bootstrap"]}]
    for item in order["foundation"]:
        if item["path"] in forbidden or item["path"] not in paths:
            raise ValueError("Forbidden or unimported foundation source: " + item["path"])
        sources.append(dict(item, code=(prototype / item["path"]).read_text(encoding="utf-8")))
    compiled = compile_sources(node, prototype, order, sources + live, combined=True)
    foundation = "\n;\n".join(item["code"] for item in compiled[:len(sources)]).encode("utf-8")
    foundation_path = "workbench/assets/foundation-" + digest(foundation)[:16] + ".js"
    payload, styles = style_assets(prototype, snapshot)
    vendor = root / "frontend/workbench/vendor"
    vendor_manifest = load_json(vendor / "vendor-manifest.json")
    verify_snapshot(vendor, vendor_manifest)
    if [(item["name"], item["version"]) for item in vendor_manifest["packages"]] != [
            ("react", "18.3.1"), ("react-dom", "18.3.1")]:
        raise ValueError("React packages must remain pinned to 18.3.1")
    for item in vendor_manifest["files"]:
        if item["path"].endswith((".js", ".LICENSE")):
            payload["workbench/vendor/" + item["path"]] = (vendor / item["path"]).read_bytes()
    scripts = ["workbench/vendor/" + name for name in vendor_manifest["scripts"]] + [foundation_path]
    payload[foundation_path] = foundation
    theme_script = "workbench/app/theme.js"
    for item in compiled[len(sources):]:
        public = "workbench/" + Path(item["path"]).with_suffix(".js").as_posix()
        payload[public] = (item["code"] + "\n").encode("utf-8")
        if public != theme_script:
            scripts.append(public)
    lucide = "ui_kits/workbench/assets/lucide-LICENSE"
    payload["workbench/prototype/" + lucide] = (prototype / lucide).read_bytes()
    files = asset_records(root, payload, scripts, theme_script, foundation_path, order, snapshot, vendor_manifest, node)
    input_records = [{"path": item["target"], "sha256": item["sha256"]} for item in snapshot["files"]]
    input_records += [{"path": "frontend/workbench/" + item["path"],
                       "sha256": digest(item["code"].encode("utf-8"))} for item in live]
    input_records += [{"path": "frontend/workbench/vendor/" + item["path"],
                       "sha256": item["sha256"]} for item in vendor_manifest["files"]]
    input_records += [{"path": "scripts/workbench/" + name, "sha256": digest((TOOLS / name).read_bytes())}
                      for name in ("build.py", "asset_sources.py", "build-order.json", "compile.cjs", "ds-projection.cjs")]
    manifest = {"schema_version": 1, "target": "chrome109", "entry": order["entry"],
                "styles": styles, "scripts": scripts, "theme_script": theme_script,
                "icon": "workbench/prototype/" + snapshot["entries"]["index"]["icons"][0],
                "files": files, "inputs": input_records, "babel_version": "7.29.0",
                "react_version": "18.3.1", "foundation_sources": order["foundation"],
                "live_source_order": [order["theme"]] + order["live"],
                "asset_metadata": {
                    "dependency_scope": "Direct local CSS references and classic-script global providers. Browser built-ins and guarded module exports are not assets; scripts/theme_script remain the execution order contract.",
                    "script_analysis": "Local Babel AST free bindings/global members; root/w denote the imported window-host model contracts. Pinned ReactDOM UMD requires the separately loaded React UMD, not npm build-time dependencies.",
                    "license_scope": "Local notice evidence applies only to its named component, not to callers or an entire mixed bundle. Unknown entries require rights review, not an inferred license grant.",
                    "requires_license_review": [row["path"] for row in files if any(item["requires_review"] for item in row["license_sources"])]}}
    manifest["build_id"] = digest(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    if live_inputs(root, order) != live:
        raise ValueError("Live sources changed during compilation; retry the build")
    # Compile and validate every input before touching the published payload; commit marker is last.
    for name, data in payload.items():
        target = output / name[len("workbench/"):]
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + ".building")
        temp.write_bytes(data)
        os.replace(str(temp), str(target))
    output.mkdir(parents=True, exist_ok=True)
    marker = output / "asset-manifest.json.building"
    marker.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(str(marker), str(output / "asset-manifest.json"))
    return {"status": "built", "manifest": str(output / "asset-manifest.json"),
            "build_id": manifest["build_id"], "files": len(files), "target": manifest["target"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default=os.environ.get("WORKBENCH_NODE") or shutil.which("node"))
    parser.add_argument("--output-dir", type=Path, default=ROOT / "static/workbench")
    parser.add_argument("--check-prototype", action="store_true", help="Compile all imported pages, publish nothing")
    args = parser.parse_args()
    try:
        if not args.node:
            raise ValueError("Node is required on the build host; pass --node or WORKBENCH_NODE")
        result = check_prototype(ROOT, args.node) if args.check_prototype else build(ROOT, args.output_dir, args.node)
        print(json.dumps(result))
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print("Workbench build failed: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
