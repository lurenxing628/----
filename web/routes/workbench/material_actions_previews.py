"""Immutable material previews retained directly by the public token registry."""

from dataclasses import dataclass
from typing import Optional, Union

from core.models.workbench_material_file import MaterialPreview
from core.models.workbench_resource_file_source import PreparedImportSource


@dataclass(frozen=True)
class RetainedPreview:
    preview: MaterialPreview
    content: Optional[Union[bytes, PreparedImportSource]]
