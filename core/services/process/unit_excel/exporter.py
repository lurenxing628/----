from __future__ import annotations

import os
from typing import Any, Dict, Sequence

from core.services.common.excel_templates import build_xlsx_bytes, get_template_definition

from .template_builder import ConvertedTemplates


class UnitTemplateExporter:
    def write_templates(self, converted: ConvertedTemplates, output_dir: str) -> Dict[str, str]:
        os.makedirs(output_dir, exist_ok=True)
        output_paths: Dict[str, str] = {}
        for filename, headers, field_name in ConvertedTemplates.output_specs():
            rows = list(getattr(converted, field_name))
            path = os.path.join(output_dir, filename)
            self._write_xlsx(path=path, filename=filename, headers=headers, rows=rows)
            output_paths[filename] = path
        return output_paths

    @staticmethod
    def _write_xlsx(path: str, *, filename: str, headers: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        template_def = get_template_definition(filename)
        effective_headers = list(template_def.get("headers") or headers)
        output = build_xlsx_bytes(
            effective_headers,
            [[row.get(h) for h in effective_headers] for row in rows],
            format_spec=template_def.get("format_spec"),
        )
        with open(path, "wb") as f:
            f.write(output.getvalue())

