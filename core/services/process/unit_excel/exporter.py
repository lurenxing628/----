from __future__ import annotations

import os
from typing import Any, Dict, Sequence

import openpyxl

from .template_builder import ConvertedTemplates


class UnitTemplateExporter:
    def write_templates(self, converted: ConvertedTemplates, output_dir: str) -> Dict[str, str]:
        os.makedirs(output_dir, exist_ok=True)
        output_paths: Dict[str, str] = {}
        for filename, headers, field_name in ConvertedTemplates.output_specs():
            rows = list(getattr(converted, field_name))
            path = os.path.join(output_dir, filename)
            self._write_xlsx(path=path, headers=headers, rows=rows)
            output_paths[filename] = path
        return output_paths

    @staticmethod
    def _write_xlsx(path: str, headers: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        wb = openpyxl.Workbook()
        try:
            ws = wb.active
            ws.title = "Sheet1"
            ws.append(list(headers))
            for row in rows:
                ws.append([row.get(h) for h in headers])
            wb.save(path)
        finally:
            try:
                wb.close()
            except Exception:
                pass

