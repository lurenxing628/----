"""Read-only complete selection and dependency evidence for resource actions."""

import json
from datetime import date

from core.shared.strict_json import canonical_json

from .base_repo import BaseRepository
from .workbench_resource_dependencies import DEPENDENCIES, report_revision_rows
from .workbench_resource_state_repo import RESOURCE_KEYS

TABLES = dict(RESOURCE_KEYS, supplier=("Suppliers", "supplier_id"))


class WorkbenchResourceFileRepository(BaseRepository):
    def raw_many(self, kind, codes):
        table, key = TABLES[kind]
        if not codes:
            return {}
        rows = self.fetchall(
            f'SELECT * FROM "{table}" WHERE "{key}" IN (SELECT value FROM json_each(?))',
            (json.dumps(list(codes)),),
        )
        return {row[key]: row for row in rows}

    def identity_histories(self, kind, codes):
        result = {code: [] for code in codes}
        if not result:
            return result
        for row in self.fetchall(
            "SELECT entity_key,ref,revision,active FROM WorkbenchEntityRefs "
            "WHERE kind=? AND entity_key IN (SELECT value FROM json_each(?)) ORDER BY entity_key,ref",
            (kind, json.dumps(list(result))),
        ):
            code = row.pop("entity_key")
            result[code].append(row)
        return result

    def references_many(self, kind, codes):
        result = {code: {dependency.source: [] for dependency in DEPENDENCIES[kind]} for code in codes}
        # 空选择（全新资源导入 existing=[]）不发查询：依赖列多数没有索引，空键集仍会整表扫描。
        if not result:
            return result
        encoded = json.dumps(list(result))
        for dependency in DEPENDENCIES[kind]:
            if dependency.table == "WorkbenchProductionReportRevisions":
                for code, rows in report_revision_rows(self.conn, kind, dependency.column, encoded).items():
                    result[code][dependency.source] = rows
                continue
            for row in self.fetchall(
                f"SELECT * FROM {dependency.table} WHERE {dependency.column} IN (SELECT value FROM json_each(?))",
                (encoded,),
            ):
                values = {name: value.isoformat() if type(value) is date else value for name, value in row.items()}
                result[row[dependency.column]][dependency.source].append(values)
        for references in result.values():
            for rows in references.values():
                rows.sort(key=canonical_json)
        return result
