"""The browser fixture guard must resolve SQLite file URIs on Windows too."""
import json
import os
import subprocess
import sys


def test_sqlite_file_uri_stays_inside_guard(tmp_path):
    root = tmp_path / "fixture 空格"
    root.mkdir()
    program = """
import json, sqlite3, sys
from pathlib import Path
from tests.workbench.live_environment import install_path_guard
root = Path(sys.argv[1])
outside = root.parent / 'outside-denied.db'
evidence = install_path_guard(root)
uri = (root / 'data 空格.db').as_uri()
with sqlite3.connect(uri + '?mode=rwc', uri=True) as conn:
    conn.execute('CREATE TABLE proof(value INTEGER)')
    conn.execute('INSERT INTO proof VALUES (42)')
with sqlite3.connect(uri + '?mode=ro', uri=True) as conn:
    assert conn.execute('SELECT value FROM proof').fetchone()[0] == 42
try:
    sqlite3.connect(outside.as_uri() + '?mode=rwc', uri=True)
except PermissionError:
    rejected = True
else:
    rejected = False
print(json.dumps({'rejected': rejected, 'outside_exists': outside.exists(),
                  'violations': len(evidence['violations'])}))
"""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, "-B", "-c", program, str(root)],
        capture_output=True, text=True, env=env, check=True,
    )
    assert json.loads(result.stdout) == {
        "rejected": True, "outside_exists": False, "violations": 1,
    }
