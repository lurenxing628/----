"""Build tracked workbench sources offline; Python 3.8 and Node on the build host only."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from asset_sources import css_references, load_json, local_path, parse_entry
from entry_bundle import bundle_styles

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
FOUNDATION_ASSET = re.compile(r"foundation-[a-f0-9]{16}\.js\Z")


def read_snapshot(root, manifest):
    # The source manifest enumerates inputs; compilation and local-path checks
    # validate their use. Do not re-hash each file on every UI build.
    return {item["path"]: local_path(root, root, item["path"]).read_bytes() for item in manifest["files"]}


def compile_sources(node, prototype, order, sources, combined=False, captured=None):
    request = {"babel_path": str(prototype / order["babel"]["path"]),
               "sources": sources, "check_combined": combined}
    if captured is not None:
        request["babel_code"] = captured[order["babel"]["path"]].decode("utf-8")
    result = subprocess.run([node, str(TOOLS / "compile.cjs")], input=json.dumps(request),
                            text=True, encoding="utf-8", capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Node compiler failed")
    return json.loads(result.stdout)["outputs"]


def read_inputs(root, order_bytes=None):
    prototype = root / "frontend/workbench/prototype"
    snapshot = load_json(prototype / "source-manifest.json")
    paths = read_snapshot(prototype, snapshot)
    order = json.loads((TOOLS / "build-order.json").read_bytes() if order_bytes is None else order_bytes)
    if order["target"] != "chrome109" or order["babel"]["version"] != "7.29.0":
        raise ValueError("Build target/compiler must remain pinned")
    if order["babel"]["path"] not in paths:
        raise ValueError("Compiler is missing from the imported snapshot")
    for entry in snapshot["entries"].values():
        if parse_entry(prototype / entry["path"], prototype, paths[entry["path"]]) != entry:
            raise ValueError("Imported entry manifest no longer matches HTML: " + entry["path"])
    return prototype, snapshot, paths, order


def check_prototype(root, node):
    prototype, snapshot, paths, order = read_inputs(root)
    sources = [{"path": name, "code": paths[name].decode("utf-8"),
                "source_type": "module" if name.startswith("components/") else "script"}
               for name in sorted(paths) if Path(name).suffix in (".js", ".jsx") and "/vendor/" not in name]
    outputs = compile_sources(node, prototype, order, sources, captured=paths)
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
    return [{"path": "app/" + name, "code": local_path(app, app, name).read_bytes().decode("utf-8")}
            for name in required]


def live_style_inputs(root, order):
    """Keep stylesheet publication and cascade order explicit and reproducible."""
    styles = root / "frontend/workbench/app/styles"
    required = order.get("styles")
    if (not isinstance(required, list) or any(type(name) is not str
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.css", name) for name in required)
            or len(required) != len(set(required))):
        raise ValueError("Live styles must be explicit unique CSS filenames")
    found = {file.relative_to(styles).as_posix() for file in styles.rglob("*")
             if file.is_file() and file.suffix.lower() == ".css"}
    missing, extra = sorted(set(required) - found), sorted(found - set(required))
    if missing or extra:
        raise ValueError("Live styles not ready; missing=" + ",".join(missing) + "; unlisted=" + ",".join(extra))
    return [{"path": "app/styles/" + name, "data": local_path(styles, styles, name).read_bytes()}
            for name in required]


def retired_generated_assets(output, payload):
    """Return only stale files in namespaces wholly generated by this builder.

    The static tree also contains imported fonts, icons, notices and prototype resources. Never infer
    ownership from the old manifest: an interrupted or older build may already have omitted an orphan.
    Clean only the JS/CSS namespaces published by this builder; keep fonts, images and notices.
    """
    expected = {Path(name[len("workbench/"):]).as_posix() for name in payload
                if name.startswith("workbench/")}
    candidates = []
    candidates.extend((output / "app").glob("*.js"))
    candidates.extend((output / "app" / "styles").glob("*.css"))
    candidates.extend((output / "app").glob("*.css"))
    candidates.extend((output / "prototype").rglob("*.css"))
    assets = output / "assets"
    if assets.is_dir():
        candidates.extend(path for path in assets.iterdir()
                          if path.is_file() and FOUNDATION_ASSET.fullmatch(path.name))
    return sorted(path for path in candidates
                  if path.relative_to(output).as_posix() not in expected)


def style_assets(prototype, snapshot, captured):
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
        payload[public] = captured[name]
        if file.suffix == ".css":
            pending += [local_path(prototype, file.parent, ref).relative_to(prototype).as_posix()
                        for ref in css_references(payload[public].decode("utf-8"))]
    return payload, ordered


def build(root, output, node):
    order_bytes = (TOOLS / "build-order.json").read_bytes()
    prototype, snapshot, paths, order = read_inputs(root, order_bytes)
    live = live_inputs(root, order)
    live_styles = live_style_inputs(root, order)
    forbidden = set(order["never_live"])
    sources = [{"path": "foundation-bootstrap.js", "code": order["bootstrap"]}]
    for item in order["foundation"]:
        if item["path"] in forbidden or item["path"] not in paths:
            raise ValueError("Forbidden or unimported foundation source: " + item["path"])
        sources.append(dict(item, code=paths[item["path"]].decode("utf-8")))
    compiled = compile_sources(node, prototype, order, sources + live, combined=True, captured=paths)
    foundation = "\n;\n".join(item["code"] for item in compiled[:len(sources)]).encode("utf-8")
    payload, styles = style_assets(prototype, snapshot, paths)
    for item in live_styles:
        public = "workbench/" + item["path"]
        payload[public] = item["data"]
        styles.append(public)
    vendor = root / "frontend/workbench/vendor"
    vendor_manifest_bytes = (vendor / "vendor-manifest.json").read_bytes()
    vendor_manifest = json.loads(vendor_manifest_bytes)
    vendor_bytes = read_snapshot(vendor, vendor_manifest)
    if [(item["name"], item["version"]) for item in vendor_manifest["packages"]] != [
            ("react", "18.3.1"), ("react-dom", "18.3.1")]:
        raise ValueError("React packages must remain pinned to 18.3.1")
    for item in vendor_manifest["files"]:
        if item["path"].endswith((".js", ".LICENSE")):
            payload["workbench/vendor/" + item["path"]] = vendor_bytes[item["path"]]
    scripts = ["workbench/vendor/" + name for name in vendor_manifest["scripts"]]
    application = [foundation]
    theme_script = "workbench/app/theme.js"
    for item in compiled[len(sources):]:
        public = "workbench/" + Path(item["path"]).with_suffix(".js").as_posix()
        code = (item["code"] + "\n").encode("utf-8")
        if public == theme_script:
            payload[public] = code
        else:
            application.append(code)
    scripts.append("workbench/app/main.js")
    payload[scripts[-1]] = b"\n;\n".join(application)
    stylesheet = "workbench/app/workbench.css"
    combined_styles = bundle_styles(payload, styles, stylesheet)
    payload = {name: data for name, data in payload.items() if not name.endswith(".css")}
    payload[stylesheet] = combined_styles
    styles = [stylesheet]
    lucide = "ui_kits/workbench/assets/lucide-LICENSE"
    payload["workbench/prototype/" + lucide] = paths[lucide]
    manifest = {"schema_version": 1, "target": "chrome109", "entry": order["entry"],
                "styles": styles, "scripts": scripts, "theme_script": theme_script,
                "icon": "workbench/prototype/" + snapshot["entries"]["index"]["icons"][0],
                "notices": ["workbench/vendor/react.LICENSE", "workbench/vendor/react-dom.LICENSE",
                            "workbench/prototype/" + lucide]}
    if live_inputs(root, order) != live:
        raise ValueError("Live sources changed during compilation; retry the build")
    if live_style_inputs(root, order) != live_styles:
        raise ValueError("Live styles changed during compilation; retry the build")
    if (TOOLS / "build-order.json").read_bytes() != order_bytes:
        raise ValueError("Build order changed during compilation; retry the build")
    # Compile and validate every input before touching the published payload; commit marker is last.
    for name, data in payload.items():
        target = output / name[len("workbench/"):]
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or target.read_bytes() != data:
            temp = target.with_name(target.name + ".building")
            temp.write_bytes(data)
            os.replace(str(temp), str(target))
    for retired in retired_generated_assets(output, payload):
        retired.unlink()
    output.mkdir(parents=True, exist_ok=True)
    marker = output / "asset-manifest.json.building"
    marker.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    os.replace(str(marker), str(output / "asset-manifest.json"))
    return {"status": "built", "manifest": str(output / "asset-manifest.json"),
            "files": len(payload), "target": manifest["target"]}


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
