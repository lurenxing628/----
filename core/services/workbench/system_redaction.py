"""Bounded public system text. Never export raw configuration or raw log files."""

import re

from core.models.public_identifier_redaction import redact_internal_text

_SENSITIVE = re.compile(r"(?i)(authorization|bearer\s|api[_-]?key|secret|password|passwd|access[_-]?token|refresh[_-]?token|cookie|private[_-]?key)")
_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|(?<![\w:])/(?!/)|\\\\)[^\s\"'<>，。；]*")


def public_system_text(value, limit=8192):
    text = str(value or "")
    lines = []
    private_block = False
    for line in text.splitlines():
        if "-----BEGIN " in line:
            private_block = True
        sensitive = private_block or _SENSITIVE.search(line)
        lines.append("[敏感内容已隐藏]" if sensitive else _PATH.sub("[本机路径]", line))
        if "-----END " in line:
            private_block = False
    result = redact_internal_text("\n".join(lines))
    return result[:limit] + ("\n[展示长度已截断]" if len(result) > limit else "")
