from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.infrastructure.errors import ValidationError

from .tabular_backend import TabularBackend


class ImportMode(Enum):
    APPEND = "append"  # 追加，不影响已有
    OVERWRITE = "overwrite"  # 相同ID覆盖
    REPLACE = "replace"  # 清空后导入（Phase1 只做预览，真正清空落库在各模块实现）


class RowStatus(Enum):
    NEW = "new"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    ERROR = "error"
    SKIP = "skip"


@dataclass
class ImportPreviewRow:
    """导入预览行（row_num 为 Excel 行号：标题行+1）。"""

    row_num: int
    status: RowStatus
    data: Dict[str, Any]
    message: str = ""
    changes: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)  # {field: (old, new)}


@dataclass
class ImportResult:
    """导入结果（Phase1 主要用于留痕统计字段）。"""

    success: bool
    total: int
    new_count: int
    update_count: int
    skip_count: int
    error_count: int
    errors: List[Dict[str, Any]]  # [{row: int, field: str, message: str}]
    warnings: List[str]


class ExcelService:
    """通用 Excel 导入导出服务（V1：openpyxl-only + backend）。"""

    def __init__(self, backend: TabularBackend, logger=None, op_logger=None, template_dir: str = "templates_excel"):
        self.backend = backend
        self.logger = logger
        self.op_logger = op_logger
        self.template_dir = template_dir

    def preview_import(
        self,
        rows: List[Dict[str, Any]],
        id_column: str,
        existing_data: Dict[str, Any],
        validators: List[Callable[[Dict[str, Any]], Optional[str]]] = None,
        mode: ImportMode = ImportMode.OVERWRITE,
    ) -> List[ImportPreviewRow]:
        if not id_column or not str(id_column).strip():
            raise ValidationError("id_column 不能为空")

        preview: List[ImportPreviewRow] = []

        for idx, row_dict in enumerate(rows):
            row_num = idx + 2  # Excel 行号（标题行+1）
            row_id = row_dict.get(id_column)

            if row_id is None or str(row_id).strip() == "":
                preview.append(
                    ImportPreviewRow(
                        row_num=row_num,
                        status=RowStatus.ERROR,
                        data=row_dict,
                        message=f"“{id_column}”不能为空",
                    )
                )
                continue

            row_id = str(row_id).strip()
            row_dict[id_column] = row_id

            # 执行验证（返回中文提示）
            validation_error = None
            if validators:
                for validator in validators:
                    err = validator(row_dict)
                    if err:
                        validation_error = err
                        break

            if validation_error:
                preview.append(
                    ImportPreviewRow(
                        row_num=row_num,
                        status=RowStatus.ERROR,
                        data=row_dict,
                        message=validation_error,
                    )
                )
                continue

            if row_id in existing_data:
                if mode == ImportMode.APPEND:
                    preview.append(
                        ImportPreviewRow(
                            row_num=row_num,
                            status=RowStatus.SKIP,
                            data=row_dict,
                            message="已存在，按“追加”模式将跳过",
                        )
                    )
                else:
                    existing = existing_data[row_id]
                    changes = self._calc_changes(existing, row_dict)
                    if changes:
                        preview.append(
                            ImportPreviewRow(
                                row_num=row_num,
                                status=RowStatus.UPDATE,
                                data=row_dict,
                                message="将更新现有记录",
                                changes=changes,
                            )
                        )
                    else:
                        preview.append(
                            ImportPreviewRow(
                                row_num=row_num,
                                status=RowStatus.UNCHANGED,
                                data=row_dict,
                                message="无变更",
                            )
                        )
            else:
                preview.append(
                    ImportPreviewRow(
                        row_num=row_num,
                        status=RowStatus.NEW,
                        data=row_dict,
                        message="新增记录",
                    )
                )

        return preview

    @staticmethod
    def _normalize_for_compare(value: Any) -> Any:
        """
        用于 _calc_changes 的弱类型标准化，避免类型差异导致幻影 UPDATE。

        目标：让 ('1', 1, 1.0) 等价；空白字符串视为 None；日期按 ISO；其它保持原样。
        """
        if value is None:
            return None
        if isinstance(value, str):
            s = value.strip()
            if s == "":
                return None
            # 数字字符串："1" / "1.0" / "1e3" 等视作数值（用于等价比较）
            try:
                return ("__num__", Decimal(s))
            except Exception:
                return s
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, bool):
            return ("__num__", Decimal(1 if value else 0))
        if isinstance(value, (int, float, Decimal)):
            try:
                return ("__num__", Decimal(str(value)))
            except Exception:
                return float(value) if isinstance(value, float) else value
        return value

    def _calc_changes(self, existing: Any, new_data: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
        changes: Dict[str, Tuple[Any, Any]] = {}
        existing_dict: Dict[str, Any] = {}
        if existing is None:
            existing_dict = {}
        elif isinstance(existing, dict):
            existing_dict = existing
        else:
            # 兼容 sqlite3.Row / Mapping-like：支持 keys() + 下标访问
            try:
                keys = getattr(existing, "keys", None)
                if callable(keys):
                    ks = list(keys())
                    existing_dict = {k: existing[k] for k in ks}
                else:
                    existing_dict = {}
            except Exception:
                existing_dict = {}
            # 兜底：普通对象（含 dataclass / model）通过 __dict__ 取值
            if not existing_dict:
                try:
                    existing_dict = vars(existing)  # type: ignore[arg-type]
                except Exception:
                    existing_dict = {}

        for key, new_val in new_data.items():
            if key in existing_dict:
                old_val = existing_dict[key]
                if self._normalize_for_compare(old_val) != self._normalize_for_compare(new_val):
                    changes[key] = (old_val, new_val)
        return changes

