"""Structure facts shared only within one validation, before any DDL change."""

from typing import Dict


class SchemaStructure:
    def __init__(self, conn):
        self.conn = conn
        self.objects = {row[1]: (row[0], row[2], row[3]) for row in conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master")}
        self.sql = {name: value[2] for name, value in self.objects.items()}
        self._columns: Dict[str, tuple] = {}
        self._indexes: Dict[str, tuple] = {}
        self._index_columns: Dict[str, tuple] = {}
        self._index_details: Dict[str, tuple] = {}
        self._foreign_keys: Dict[str, tuple] = {}

    def has_table(self, name):
        return name in self.objects and self.objects[name][0] == "table"

    def index_table(self, name):
        obj = self.objects.get(name)
        return obj[1] if obj is not None and obj[0] == "index" else ""

    def _pragma(self, cache, command, name):
        if name not in cache:
            quoted = '"' + name.replace('"', '""') + '"'
            cache[name] = tuple(self.conn.execute("PRAGMA " + command + "(" + quoted + ")"))
        return cache[name]

    def table_info(self, name):
        return self._pragma(self._columns, "table_info", name)

    def index_list(self, name):
        return self._pragma(self._indexes, "index_list", name)

    def index_info(self, name):
        return self._pragma(self._index_columns, "index_info", name)

    def index_xinfo(self, name):
        return self._pragma(self._index_details, "index_xinfo", name)

    def foreign_keys(self, name):
        return self._pragma(self._foreign_keys, "foreign_key_list", name)

    def has_unique_key(self, table, columns):
        expected = tuple(columns)
        return any(row[2] and not row[4] and tuple(col[2] for col in self.index_info(row[1])) == expected
                   for row in self.index_list(table))


def schema_objects(conn, *, structure=None):
    """Independent checks stay fresh; an aggregate check supplies its capture."""
    if structure is not None:
        return structure.sql
    return {row[0]: row[1] for row in conn.execute("SELECT name, sql FROM sqlite_master")}
