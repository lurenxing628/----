"""Structure facts shared only within one validation, before any DDL change."""

from typing import Dict


class SchemaStructure:
    def __init__(self, conn):
        self.conn = conn
        self.objects = {row[1]: (row[0], row[2], row[3]) for row in conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master")}
        self.sql = {name: value[2] for name, value in self.objects.items()}
        self._columns: Dict[str, tuple] = {}

    def has_table(self, name):
        return name in self.objects and self.objects[name][0] == "table"

    def table_info(self, name):
        if name not in self._columns:
            quoted = '"' + name.replace('"', '""') + '"'
            self._columns[name] = tuple(self.conn.execute("PRAGMA table_info(" + quoted + ")"))
        return self._columns[name]
