"""Emit review text and preimage hashes to stdout; never applies the patch."""

import hashlib
import json
from difflib import unified_diff

from candidate_sources import PAYLOAD, RENDER_TARGETS, REPO, render_source


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def replacement(path, before, after):
    if before is None:
        return "*** Add File: " + path + "\n" + "".join("+" + line + "\n" for line in after.splitlines())
    diff = list(unified_diff(before.splitlines(), after.splitlines(), n=3))[2:]
    body = "".join(("@@" if line.startswith("@@") else line) + "\n" for line in diff)
    return "*** Update File: " + path + "\n" + body


def build():
    entries, chunks = [], ["*** Begin Patch\n"]
    for path, old, new in RENDER_TARGETS:
        before, after, line = render_source(path, old, new)
        entries.append({"path": path, "kind": "template_target_only", "before_sha256": sha(before),
                        "after_sha256": sha(after), "old_template": old, "new_template": new, "line": line,
                        "ast_equal_after_restoring_template_literal": True})
        chunks.append(replacement(path, before, after))
    for source in sorted(PAYLOAD.rglob("*")):
        if not source.is_file() or source.suffix not in (".py", ".html"):
            continue
        path = source.relative_to(PAYLOAD).as_posix()
        before = (REPO / path).read_text(encoding="utf-8") if (REPO / path).is_file() else None
        after = source.read_text(encoding="utf-8")
        entries.append({"path": path, "kind": "new_file" if before is None else "replace_error_presentation",
                        "before_sha256": sha(before) if before is not None else None, "after_sha256": sha(after)})
        chunks.append(replacement(path, before, after))
    chunks.append("*** End Patch\n")
    return {"patch": "".join(chunks), "index": entries, "status": "not_applied",
            "not_included": ["factory/pages/JS registration", "actual navigation helper files already present",
                             "source/asset deletion", "business services and 113 POST handler logic", "schemas and data", "build inputs"]}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
