"""Build tracked workbench sources offline; Python 3.8 and Node on the build host only."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.workbench.asset_sources import css_references, local_path  # noqa: E402
from scripts.workbench.entry_bundle import bundle_styles  # noqa: E402

FOUNDATION_ASSET = re.compile(r"foundation-[a-f0-9]{16}\.js\Z")
INDEX_IMPORT_RE = re.compile(
    r'@import\s+(?:url\(\s*)?["\'](?:\./)?([^"\')]+)["\']\s*\)?\s*;'
)
COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)


def read_snapshot(root, manifest):
    return {
        item["path"]: local_path(root, root, item["path"]).read_bytes()
        for item in manifest["files"]
    }


def compile_production(node, root):
    app_dir = root / "frontend/workbench/app"
    if not (app_dir / "theme.js").is_file() or not (app_dir / "shell/main.jsx").is_file():
        raise ValueError("Live entrypoints theme.js and shell/main.jsx must exist")
    result = subprocess.run(
        [node, str(TOOLS / "compile.cjs")],
        input=json.dumps({"mode": "production", "appDir": str(app_dir)}),
        cwd=str(root),
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Node compiler failed")
    return json.loads(result.stdout)


def verify_js_module_graph(app_dir, compiled_inputs):
    expected = set(compiled_inputs)
    found = {
        f.relative_to(app_dir).as_posix()
        for f in app_dir.rglob("*")
        if f.is_file() and f.suffix in (".js", ".jsx")
    }
    missing, extra = sorted(expected - found), sorted(found - expected)
    if missing or extra:
        raise ValueError(f"JS module graph out of sync; missing={','.join(missing)}; unlisted={','.join(extra)}")


def live_style_inputs(root):
    """Keep stylesheet publication and cascade order explicit via app/styles/index.css."""
    app_dir = root / "frontend/workbench/app"
    styles = app_dir / "styles"
    index_file = styles / "index.css"
    if not index_file.is_file():
        raise ValueError("Live style entrypoint index.css is missing")
    required = INDEX_IMPORT_RE.findall(COMMENT_RE.sub("", index_file.read_text(encoding="utf-8")))
    if (
        not required
        or any(n == "index.css" or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.css", n) for n in required)
        or len(required) != len(set(required))
    ):
        raise ValueError("Live styles in index.css must be explicit unique CSS filenames")
    found = {
        f.relative_to(styles).as_posix()
        for f in styles.rglob("*")
        if f.is_file() and f.name != "index.css"
    }
    missing, extra = sorted(set(required) - found), sorted(found - set(required))
    if missing or extra:
        raise ValueError(f"Live styles not ready; missing={','.join(missing)}; unlisted={','.join(extra)}")
    entries, css_asset_paths = [], set()
    for name in required:
        style_file = local_path(styles, styles, name)
        data = style_file.read_bytes()
        entries.append({"path": "app/styles/" + name, "data": data})
        for ref in css_references(data.decode("utf-8")):
            target = local_path(app_dir, style_file.parent, ref)
            if target.suffix.lower() != ".css":
                css_asset_paths.add("app/" + target.relative_to(app_dir).as_posix())
    return entries, css_asset_paths


def app_asset_inputs(root, css_asset_paths):
    app_dir = root / "frontend/workbench/app"
    assets_dir = app_dir / "assets"
    if not assets_dir.is_dir():
        raise ValueError("Live assets directory app/assets is missing")
    expected = {"app/assets/logo-mark.svg", "app/assets/lucide-LICENSE"} | set(css_asset_paths)
    found = {
        "app/assets/" + f.relative_to(assets_dir).as_posix()
        for f in assets_dir.rglob("*")
        if f.is_file()
    }
    missing, extra = sorted(expected - found), sorted(found - expected)
    if missing or extra:
        raise ValueError(f"App assets out of sync; missing={','.join(missing)}; unlisted={','.join(extra)}")
    return {"workbench/" + rel: local_path(app_dir, app_dir, rel[len("app/"):]).read_bytes() for rel in sorted(expected)}


def retired_generated_assets(output, payload):
    """Return stale files in namespaces managed by this builder."""
    expected = {
        Path(name[len("workbench/"):]).as_posix()
        for name in payload
        if name.startswith("workbench/")
    }
    candidates = set()
    for item in (output / "app").glob("*.js"):
        if item.is_file():
            candidates.add(item)
    for item in (output / "app").glob("*.css"):
        if item.is_file():
            candidates.add(item)
    for managed_dir in (output / "app" / "styles", output / "app" / "assets", output / "prototype"):
        if managed_dir.is_dir():
            candidates.update(p for p in managed_dir.rglob("*") if p.is_file())
    assets = output / "assets"
    if assets.is_dir():
        candidates.update(
            p for p in assets.iterdir() if p.is_file() and FOUNDATION_ASSET.fullmatch(p.name)
        )
    return sorted(
        path for path in candidates if path.relative_to(output).as_posix() not in expected
    )


def prune_empty_dirs(*roots):
    for root_dir in roots:
        if not root_dir.is_dir():
            continue
        dirs = sorted(
            (p for p in root_dir.rglob("*") if p.is_dir()),
            key=lambda p: len(p.parts),
            reverse=True,
        )
        dirs.append(root_dir)
        for directory in dirs:
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()


def build(root, output, node):
    app_dir = root / "frontend/workbench/app"
    live_styles, css_asset_paths = live_style_inputs(root)
    payload = app_asset_inputs(root, css_asset_paths)
    compiled = compile_production(node, root)
    verify_js_module_graph(app_dir, compiled["inputs"])
    styles = []
    for item in live_styles:
        public = "workbench/" + item["path"]
        payload[public] = item["data"]
        styles.append(public)
    vendor = root / "frontend/workbench/vendor"
    vendor_manifest = json.loads((vendor / "vendor-manifest.json").read_bytes())
    vendor_bytes = read_snapshot(vendor, vendor_manifest)
    if [(item["name"], item["version"]) for item in vendor_manifest["packages"]] != [
        ("react", "18.3.1"),
        ("react-dom", "18.3.1"),
    ]:
        raise ValueError("React packages must remain pinned to 18.3.1")
    for item in vendor_manifest["files"]:
        if item["path"].endswith((".js", ".LICENSE")):
            payload["workbench/vendor/" + item["path"]] = vendor_bytes[item["path"]]
    scripts = ["workbench/vendor/" + name for name in vendor_manifest["scripts"]]
    theme_script, main_script = "workbench/app/theme.js", "workbench/app/main.js"
    for item in compiled["outputs"]:
        public = "workbench/" + Path(item["path"]).with_suffix(".js").as_posix()
        payload[public] = (item["code"].rstrip("\n") + "\n").encode("utf-8")
    scripts.append(main_script)
    stylesheet = "workbench/app/workbench.css"
    combined_styles = bundle_styles(payload, styles, stylesheet)
    payload = {name: data for name, data in payload.items() if not name.endswith(".css")}
    payload[stylesheet] = combined_styles
    manifest = {
        "schema_version": 1,
        "target": "chrome109",
        "entry": "wb-foundation-read-loop",
        "styles": [stylesheet],
        "scripts": scripts,
        "theme_script": theme_script,
        "icon": "workbench/app/assets/logo-mark.svg",
        "notices": [
            "workbench/vendor/react.LICENSE",
            "workbench/vendor/react-dom.LICENSE",
            "workbench/app/assets/lucide-LICENSE",
        ],
    }
    for name, data in payload.items():
        target = output / name[len("workbench/"):]
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or target.read_bytes() != data:
            temp = target.with_name(target.name + ".building")
            temp.write_bytes(data)
            os.replace(str(temp), str(target))
    for retired in retired_generated_assets(output, payload):
        retired.unlink()
    prune_empty_dirs(output / "prototype", output / "assets", output / "app" / "styles", output / "app" / "assets")
    output.mkdir(parents=True, exist_ok=True)
    marker = output / "asset-manifest.json.building"
    marker.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    os.replace(str(marker), str(output / "asset-manifest.json"))
    return {"status": "built", "manifest": str(output / "asset-manifest.json"), "files": len(payload), "target": manifest["target"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default=os.environ.get("WORKBENCH_NODE") or shutil.which("node"))
    parser.add_argument("--output-dir", type=Path, default=ROOT / "static/workbench")
    args = parser.parse_args()
    try:
        if not args.node:
            raise ValueError("Node is required on the build host; pass --node or WORKBENCH_NODE")
        print(json.dumps(build(ROOT, args.output_dir, args.node)))
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print("Workbench build failed: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
