"""Read-only SQLite snapshots shared by independent regression domains."""


def schema_snapshot(conn):
    return {
        row[0]: (row[1], row[2], " ".join((row[3] or "").split()))
        for row in conn.execute("SELECT name, type, tbl_name, sql FROM sqlite_master")
    }


def table_rows(conn, table):
    return [tuple(row) for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid')]


def stored_state(conn):
    names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    return schema_snapshot(conn), {name: table_rows(conn, name) for name in names}
