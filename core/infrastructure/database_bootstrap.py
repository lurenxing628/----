from __future__ import annotations

import re


def build_schema_exec_script(sql: str) -> str:
    if re.search(r"(?im)^\s*BEGIN(?:\s+(?:DEFERRED|IMMEDIATE|EXCLUSIVE))?(?:\s+TRANSACTION)?\s*;", sql):
        return sql
    # PRAGMA foreign_keys cannot be changed inside a transaction.
    clean_sql = re.sub(r"(?im)^\s*PRAGMA\s+foreign_keys\s*=\s*\w+;?", "", sql)
    return "BEGIN;\n" + clean_sql + "\nCOMMIT;\n"
