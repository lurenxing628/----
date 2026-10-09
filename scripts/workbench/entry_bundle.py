"""Combine ordered local styles without changing their cascade or URL targets."""

import posixpath
import re
from urllib.parse import quote, unquote, urlsplit, urlunsplit

_CSS_TOKEN = re.compile(
    r"/\*.*?\*/|@import\s+(?:url\(\s*[\"']?([^\"')]+)[\"']?\s*\)|[\"']([^\"']+)[\"'])\s*;"
    r"|url\(\s*([\"']?)([^\"')]+)\3\s*\)", re.I | re.S)


def bundle_styles(payload, styles, destination):
    def target(source, reference):
        value = urlsplit(reference.strip())
        if value.scheme or value.netloc or value.path.startswith("/"):
            raise ValueError("Styles must use local assets: " + reference)
        path = posixpath.normpath(posixpath.join(posixpath.dirname(source), unquote(value.path)))
        if path not in payload:
            raise ValueError("Missing stylesheet dependency: " + path)
        return path, value

    def inline(source, parents):
        if source in parents:
            raise ValueError("Cyclic stylesheet import: " + source)

        def replace(match):
            if match[0].startswith("/*"):
                return match[0]
            imported = match[1] or match[2]
            if imported is not None:
                path, _ = target(source, imported)
                return inline(path, parents + (source,))
            reference = match[4].strip()
            if reference.lower().startswith(("data:", "#")):
                return match[0]
            path, url = target(source, reference)
            relative = posixpath.relpath(path, posixpath.dirname(destination))
            return 'url("' + urlunsplit(("", "", quote(relative, safe="/-._~"), url.query, url.fragment)) + '")'

        return _CSS_TOKEN.sub(replace, payload[source].decode("utf-8"))

    combined = "\n\n".join("/* " + name + " */\n" + inline(name, ()) for name in styles)
    return re.sub(r"[ \t]+\n", "\n", combined).encode("utf-8")
