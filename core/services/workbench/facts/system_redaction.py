"""Bounded public system text. Never export raw configuration or raw log files."""


def public_system_text(text, limit=8192):
    result = str(text or "")
    return result[:limit] + ("\n[展示长度已截断]" if len(result) > limit else "")
