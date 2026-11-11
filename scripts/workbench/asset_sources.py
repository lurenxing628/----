"""Local entry discovery and content checks; no application imports."""

import json
import re
from urllib.parse import unquote, urlsplit


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if not path.is_file() or path.read_bytes() != data:
        path.write_bytes(data)


def local_path(root, parent, reference):
    url = urlsplit(reference)
    if url.scheme or url.netloc or url.path.startswith("/"):
        raise ValueError("External/absolute asset reference: " + reference)
    target = (parent / unquote(url.path)).resolve()
    target.relative_to(root.resolve())
    if not target.is_file():
        raise ValueError("Missing local asset: " + str(target))
    return target


def css_references(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    urls = re.findall(r"url\(\s*['\"]?([^'\")]+?)['\"]?\s*\)", text, flags=re.I)
    urls += re.findall(r"@import\s+['\"]([^'\"]+)['\"]", text, flags=re.I)
    return [url.strip() for url in urls if not url.strip().lower().startswith(("data:", "#"))]
