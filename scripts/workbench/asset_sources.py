"""Local entry discovery and content checks; no application imports."""

import json
import re
from html.parser import HTMLParser
from pathlib import Path
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


class EntryParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scripts = []
        self.styles = []
        self.icons = []
        self.inline_styles = []
        self.inline_scripts = []
        self.capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src"):
            self.scripts.append({"url": attrs["src"], "type": attrs.get("type", "text/javascript")})
        elif tag == "script" or tag == "style":
            self.capture = {"tag": tag, "line": self.getpos()[0], "text": ""}
        elif tag == "link":
            rel = attrs.get("rel", "").split()
            if "stylesheet" in rel:
                self.styles.append(attrs["href"])
            elif "icon" in rel:
                self.icons.append(attrs["href"])

    def handle_data(self, data):
        if self.capture is not None:
            self.capture["text"] += data

    def handle_endtag(self, tag):
        if self.capture is not None and self.capture["tag"] == tag:
            target = self.inline_styles if tag == "style" else self.inline_scripts
            target.append(self.capture)
            self.capture = None


def parse_entry(path, root, data=None):
    parser = EntryParser()
    parser.feed(path.read_text(encoding="utf-8") if data is None else data.decode("utf-8"))
    parser.close()
    def relative(ref):
        return local_path(root, path.parent, ref).relative_to(root).as_posix()

    return {
        "path": path.relative_to(root).as_posix(),
        "scripts": [{"path": relative(item["url"]), "type": item["type"]} for item in parser.scripts],
        "styles": [relative(url) for url in parser.styles],
        "icons": [relative(url) for url in parser.icons],
        "inline_styles": parser.inline_styles,
        "inline_scripts": parser.inline_scripts,
    }


def css_references(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    urls = re.findall(r"url\(\s*['\"]?([^'\")]+?)['\"]?\s*\)", text, flags=re.I)
    urls += re.findall(r"@import\s+['\"]([^'\"]+)['\"]", text, flags=re.I)
    return [url.strip() for url in urls if not url.strip().lower().startswith(("data:", "#"))]


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
