from __future__ import annotations

from typing import Dict, Optional

from .unit_excel.exporter import UnitTemplateExporter
from .unit_excel.parser import PartContext as _PartContext
from .unit_excel.parser import StationMeta as _StationMeta
from .unit_excel.parser import StepRecord as _StepRecord
from .unit_excel.parser import UnitExcelParser
from .unit_excel.template_builder import ConvertedTemplates as _PipelineConvertedTemplates
from .unit_excel.template_builder import UnitTemplateBuilder


class UnitExcelConverter:
    """
    对外兼容 façade：
    - convert(...) -> ConvertedTemplates
    - write_templates(...) -> Dict[str, str]
    """

    def __init__(self) -> None:
        self._parser = UnitExcelParser()
        self._builder = UnitTemplateBuilder()
        self._exporter = UnitTemplateExporter()

    def convert(self, input_path: str, sheet_name: Optional[str] = None) -> _PipelineConvertedTemplates:
        parts, stations = self._parser.parse(input_path=input_path, sheet_name=sheet_name)
        return self._builder.build(parts=parts, stations=stations)

    def write_templates(self, converted: _PipelineConvertedTemplates, output_dir: str) -> Dict[str, str]:
        return self._exporter.write_templates(converted=converted, output_dir=output_dir)


# 保持向后兼容：模块级类型名继续可见
ConvertedTemplates = _PipelineConvertedTemplates
StationMeta = _StationMeta
StepRecord = _StepRecord
PartContext = _PartContext
