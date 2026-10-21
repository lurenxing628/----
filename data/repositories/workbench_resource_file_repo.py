"""Read-only complete selection and dependency evidence for resource actions."""

from datetime import date

from core.models.workbench_command import canonical_json

from .base_repo import BaseRepository
from .workbench_resource_dependencies import DEPENDENCIES
from .workbench_resource_state_repo import RESOURCE_KEYS

TABLES = dict(RESOURCE_KEYS, supplier=("Suppliers", "supplier_id"))


class WorkbenchResourceFileRepository(BaseRepository):
    def raw_many(self, kind, codes):
        table, key = TABLES[kind]
        codes, result = list(dict.fromkeys(codes)), {}
        for offset in range(0, len(codes), 400):
            chunk = codes[offset:offset + 400]
            marks = ",".join("?" for _ in chunk)
            for row in self.fetchall(f'SELECT * FROM "{table}" WHERE "{key}" IN ({marks})', chunk):
                result[row[key]] = row
        return result

    def identity_histories(self, kind, codes):
        result = {code: [] for code in codes}
        for offset in range(0, len(codes), 400):
            chunk = codes[offset:offset + 400]
            marks = ",".join("?" for _ in chunk)
            for row in self.fetchall("SELECT entity_key,ref,revision,active FROM WorkbenchEntityRefs "
                    f"WHERE kind=? AND entity_key IN ({marks}) ORDER BY ref", [kind] + chunk):
                code = row.pop("entity_key")
                result[code].append(row)
        return result

    def references_many(self, kind, codes):
        result = {code: {table + "." + key: [] for table, key in DEPENDENCIES[kind]} for code in codes}
        for offset in range(0, len(codes), 400):
            chunk = codes[offset:offset + 400]
            marks = ",".join("?" for _ in chunk)
            for table, key in DEPENDENCIES[kind]:
                for row in self.fetchall(f"SELECT * FROM {table} WHERE {key} IN ({marks})", chunk):
                    values = {name: value.isoformat() if type(value) is date else value for name, value in row.items()}
                    result[row[key]][table + "." + key].append(values)
        for references in result.values():
            for rows in references.values():
                rows.sort(key=canonical_json)
        return result
