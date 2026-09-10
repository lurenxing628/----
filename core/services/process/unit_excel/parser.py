from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .cell_parsing import (
    parse_step_seq_detail,
    part_no_cell_coercion_issue,
    step_cell_date_issue,
    to_float_with_diagnostic,
    to_text,
)

_LOGGER = logging.getLogger(__name__)

# 站位（设备）列块从第 9 列（0 基 8）开始，每 4 列一块：表头、换型、单件、批次。
_STATION_REGION_START = 8
_STATION_BLOCK_WIDTH = 4


def _close_workbook_best_effort(wb: Any) -> None:
    try:
        wb.close()
    except Exception as exc:
        _LOGGER.warning("关闭工艺单元 Excel 工作簿失败：%s", exc)


class SheetNotFoundError(ValueError):
    """指定的工作表在源 Excel 中不存在。携带可用工作表清单，供 CLI 给出可自助排错的中文提示。"""

    def __init__(self, sheet_name: str, available_sheets: Sequence[str]):
        self.sheet_name = str(sheet_name)
        self.available_sheets = [str(name) for name in available_sheets]
        super().__init__(
            "找不到指定的工作表：{}；当前文件可用工作表：{}".format(
                self.sheet_name, "、".join(self.available_sheets) or "（无）"
            )
        )


@dataclass
class StationMeta:
    col_start: int
    machine_id: str
    machine_label: str
    operators: List[str] = field(default_factory=list)


@dataclass
class StepRecord:
    part_no: str
    seq: Optional[int]
    step_text: str
    has_step_code: bool
    machine_id: str
    operators: List[str]
    setup_min: Optional[float]
    unit_min: Optional[float]
    batch_min: Optional[float]
    row_num: int = 0
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PartContext:
    part_no: str
    part_name: str
    route_raw: str
    route_map: Dict[int, str] = field(default_factory=dict)
    step_records: List[StepRecord] = field(default_factory=list)
    # 与 route_raw/route_map 配套：解析当前工艺路线时被丢弃/合并的片段留痕，转换侧必须逐条出诊断。
    route_diagnostics: List[Dict[str, Any]] = field(default_factory=list)


def _column_range_label(col_start: int, col_end: int) -> str:
    return f"{get_column_letter(col_start + 1)}-{get_column_letter(col_end + 1)}"


class UnitExcelParser:
    _SEPARATORS_RE = re.compile(r"[\s,，、\-—–→>＞]+")
    _CJK_RE = re.compile(r"[\u4e00-\u9fff]")

    def parse(
        self, input_path: str, sheet_name: Optional[str] = None
    ) -> Tuple[Dict[str, PartContext], List[StationMeta], List[Dict[str, Any]]]:
        wb = openpyxl.load_workbook(input_path, data_only=True)
        try:
            parse_diagnostics: List[Dict[str, Any]] = []
            ws = self._select_worksheet(wb, sheet_name=sheet_name, parse_diagnostics=parse_diagnostics)

            headers = [to_text(v) for v in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
            stations, dropped_blocks = self._build_station_columns(headers, parse_diagnostics=parse_diagnostics)

            parts: Dict[str, PartContext] = {}
            current_part_no: Optional[str] = None

            for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                if row is None:
                    continue
                row_values = list(row)

                self._record_dropped_block_data(
                    row_values=row_values,
                    dropped_blocks=dropped_blocks,
                    row_num=row_num,
                    parse_diagnostics=parse_diagnostics,
                )
                current_part_no = self._maybe_update_part_context(
                    parts,
                    current_part_no=current_part_no,
                    row_values=row_values,
                    row_num=row_num,
                    parse_diagnostics=parse_diagnostics,
                )
                if not current_part_no:
                    continue

                ctx = parts[current_part_no]
                self._append_station_step_records(ctx, row_values=row_values, stations=stations, row_num=row_num)
            return parts, stations, parse_diagnostics
        finally:
            _close_workbook_best_effort(wb)

    def _select_worksheet(
        self, wb: Any, *, sheet_name: Optional[str], parse_diagnostics: List[Dict[str, Any]]
    ) -> Worksheet:
        if sheet_name:
            if sheet_name not in wb.sheetnames:
                raise SheetNotFoundError(sheet_name, list(wb.sheetnames))
            ws = wb[sheet_name]
        else:
            # 与转换脚本对外承诺一致：默认解析第一个工作表。
            # 不用 wb.active：它是 Excel 上次保存时停留的标签页，用户停在说明页时会解析错表。
            worksheets = list(wb.worksheets)
            if not worksheets:
                raise ValueError("Workbook 缺少工作表")
            ws = worksheets[0]
        if not isinstance(ws, Worksheet):
            raise ValueError("Workbook 工作表类型不受支持")
        if len(wb.sheetnames) > 1:
            parse_diagnostics.append(
                {
                    "code": "multiple_sheets_notice",
                    "scope": "unit_excel.workbook",
                    "field": "工作表",
                    "message": "源 Excel 含多个工作表，本次只解析了其中一个，请确认解析的工作表是产品数据表。",
                    "used_sheet": str(ws.title),
                    "sheet_names": [str(name) for name in wb.sheetnames],
                }
            )
        return ws

    def _maybe_update_part_context(
        self,
        parts: Dict[str, PartContext],
        *,
        current_part_no: Optional[str],
        row_values: Sequence[Any],
        row_num: int,
        parse_diagnostics: List[Dict[str, Any]],
    ) -> Optional[str]:
        raw_part_no = self._pick_cell(row_values, 0)
        part_no = to_text(raw_part_no)
        if not part_no:
            return current_part_no if current_part_no in parts else None

        part_no_issue = part_no_cell_coercion_issue(raw_part_no, row_num=row_num)
        if part_no_issue is not None:
            parse_diagnostics.append(part_no_issue)

        part_name = to_text(self._pick_cell(row_values, 1))
        route_raw = to_text(self._pick_cell(row_values, 4))
        route_map, route_diagnostics = self._parse_route_map(route_raw, row_num=row_num)

        existing_ctx = parts.get(part_no)
        if existing_ctx is None:
            parts[part_no] = PartContext(
                part_no=part_no,
                part_name=part_name or part_no,
                route_raw=route_raw,
                route_map=route_map,
                route_diagnostics=route_diagnostics,
            )
        else:
            if part_name:
                existing_ctx.part_name = part_name
            if route_raw:
                existing_ctx.route_raw = route_raw
                existing_ctx.route_diagnostics = route_diagnostics
            if route_map:
                existing_ctx.route_map = route_map

        return part_no

    def _append_station_step_records(self, ctx: PartContext, *, row_values: Sequence[Any], stations: Sequence[StationMeta], row_num: int) -> None:
        for station in stations:
            raw_step_value = self._pick_cell(row_values, station.col_start)
            step_text = to_text(raw_step_value)
            if not step_text:
                continue

            diagnostics: List[Dict[str, Any]] = []
            date_issue = step_cell_date_issue(raw_step_value, row_num=row_num)
            if date_issue is not None:
                # 工序号被 Excel 存成了日期：不做猜测恢复，按无法识别处理并留痕。
                seq, has_step_code = None, False
                diagnostics.append(date_issue)
            else:
                seq, has_step_code, seq_issue = parse_step_seq_detail(step_text, row_num=row_num)
                if seq_issue:
                    diagnostics.append(seq_issue)
            rec = StepRecord(
                part_no=ctx.part_no,
                seq=seq,
                step_text=step_text,
                has_step_code=has_step_code,
                machine_id=station.machine_id,
                operators=list(station.operators),
                setup_min=to_float_with_diagnostic(
                    self._pick_cell(row_values, station.col_start + 1),
                    row_num=row_num,
                    field="换型时间(min)",
                    diagnostics=diagnostics,
                ),
                unit_min=to_float_with_diagnostic(
                    self._pick_cell(row_values, station.col_start + 2),
                    row_num=row_num,
                    field="单件加工时间(min)",
                    diagnostics=diagnostics,
                ),
                batch_min=to_float_with_diagnostic(
                    self._pick_cell(row_values, station.col_start + 3),
                    row_num=row_num,
                    field="批次加工时间(min)",
                    diagnostics=diagnostics,
                ),
                row_num=int(row_num),
                diagnostics=diagnostics,
            )
            ctx.step_records.append(rec)

    def _build_station_columns(
        self, headers: Sequence[str], *, parse_diagnostics: List[Dict[str, Any]]
    ) -> Tuple[List[StationMeta], List[Tuple[int, int]]]:
        """识别站位（设备）列块；被丢弃的列块必须留痕并返回列范围，供数据行检查是否有内容被吃掉。"""
        stations: List[StationMeta] = []
        dropped_blocks: List[Tuple[int, int]] = []
        idx = _STATION_REGION_START
        while idx + _STATION_BLOCK_WIDTH - 1 < len(headers):
            block_texts = [to_text(h) for h in headers[idx : idx + _STATION_BLOCK_WIDTH]]
            raw_header = block_texts[0]
            station: Optional[StationMeta] = None
            if raw_header:
                machine_id, machine_label, operators = self._parse_station_header(raw_header)
                if machine_id:
                    station = StationMeta(
                        col_start=idx,
                        machine_id=machine_id,
                        machine_label=machine_label or machine_id,
                        operators=operators,
                    )
            if station is not None:
                stations.append(station)
            else:
                dropped_blocks.append((idx, idx + _STATION_BLOCK_WIDTH - 1))
                if any(block_texts):
                    reason = (
                        "设备列表头无法识别出设备编号"
                        if raw_header
                        else "设备列块首格表头为空（可能是合并单元格锚点不在块首）"
                    )
                    parse_diagnostics.append(
                        self._station_header_dropped_diagnostic(
                            col_start=idx,
                            col_end=idx + _STATION_BLOCK_WIDTH - 1,
                            block_texts=block_texts,
                            reason=reason,
                        )
                    )
            idx += _STATION_BLOCK_WIDTH
        if idx < len(headers):
            tail_texts = [to_text(h) for h in headers[idx:]]
            dropped_blocks.append((idx, len(headers) - 1))
            if any(tail_texts):
                parse_diagnostics.append(
                    self._station_header_dropped_diagnostic(
                        col_start=idx,
                        col_end=len(headers) - 1,
                        block_texts=tail_texts,
                        reason="表头末尾的设备列块不足 4 列",
                    )
                )
        return stations, dropped_blocks

    @staticmethod
    def _station_header_dropped_diagnostic(
        *, col_start: int, col_end: int, block_texts: Sequence[str], reason: str
    ) -> Dict[str, Any]:
        return {
            "code": "station_header_dropped",
            "scope": "unit_excel.station",
            "field": "设备列表头",
            "message": f"{reason}，这一块设备工时列已整块跳过、未进入转换结果，请核对第一行表头。",
            "columns": _column_range_label(col_start, col_end),
            "headers": list(block_texts),
        }

    @staticmethod
    def _record_dropped_block_data(
        *,
        row_values: Sequence[Any],
        dropped_blocks: Sequence[Tuple[int, int]],
        row_num: int,
        parse_diagnostics: List[Dict[str, Any]],
    ) -> None:
        """数据行落在被丢弃列块里的内容不许无声消失：逐行留痕，计数反映丢了多少行。"""
        for col_start, col_end in dropped_blocks:
            non_empty = [
                text
                for text in (
                    to_text(UnitExcelParser._pick_cell(row_values, col)) for col in range(col_start, col_end + 1)
                )
                if text
            ]
            if not non_empty:
                continue
            parse_diagnostics.append(
                {
                    "code": "station_block_data_dropped",
                    "scope": "unit_excel.station",
                    "field": "设备列数据",
                    "message": "数据行在未识别的设备列块里有内容，这些数据没有被转换，请核对第一行表头。",
                    "row_num": int(row_num),
                    "columns": _column_range_label(col_start, col_end),
                    "values": non_empty[:_STATION_BLOCK_WIDTH],
                }
            )

    def _parse_station_header(self, raw_header: str) -> Tuple[str, str, List[str]]:
        text = to_text(raw_header)
        lines = [x.strip() for x in re.split(r"[\r\n]+", text) if x and x.strip()]
        if not lines:
            return "", "", []

        machine_label = lines[0]
        machine_id = self._extract_machine_id(machine_label)

        operator_names: List[str] = []
        if len(lines) > 1:
            for ln in lines[1:]:
                operator_names.extend(self._extract_names(ln))
        else:
            tokens = [t for t in re.split(r"[、,，/\s]+", machine_label) if t]
            if tokens:
                first = tokens[0]
                machine_label = first
                machine_id = self._extract_machine_id(first) or first
                operator_names.extend(self._extract_names(" ".join(tokens[1:])))

        operator_names = self._dedupe_keep_order(operator_names)
        return machine_id, machine_label, operator_names

    @staticmethod
    def _extract_machine_id(text: str) -> str:
        s = (text or "").strip()
        if not s:
            return ""
        m = re.search(r"(\d{4,})", s)
        if m:
            return m.group(1)
        s = re.sub(r"[（(].*?[）)]", "", s).strip()
        return s

    def _extract_names(self, text: str) -> List[str]:
        tokens = [x.strip() for x in re.split(r"[、,，/\s]+", to_text(text)) if x and x.strip()]
        result: List[str] = []
        for tk in tokens:
            if tk.isdigit():
                continue
            if not self._CJK_RE.search(tk):
                continue
            cleaned = re.sub(r"[（(].*?[）)]", "", tk).strip()
            if cleaned:
                result.append(cleaned)
        return result

    def _parse_route_map(self, route_raw: str, *, row_num: int) -> Tuple[Dict[int, str], List[Dict[str, Any]]]:
        normalized = self._normalize_route(route_raw)
        route: Dict[int, str] = {}
        diagnostics: List[Dict[str, Any]] = []

        def _dropped_segment(segment: str, *, seq: Optional[int] = None) -> None:
            diagnostics.append(
                {
                    "code": "route_segment_dropped",
                    "field": "工艺路线",
                    "message": "工艺路线中有无法识别的片段，系统已跳过，请核对工艺路线写法。",
                    "row_num": row_num,
                    "raw_value": route_raw,
                    "segment": segment,
                    "seq": seq,
                }
            )

        consumed_end = 0
        for m in re.finditer(r"(\d+)([^\d]+)", normalized):
            if m.start() > consumed_end:
                _dropped_segment(normalized[consumed_end : m.start()])
            consumed_end = m.end()
            seq_s, op_name = m.group(1), m.group(2)
            try:
                seq = int(seq_s)
            except Exception:
                _dropped_segment(m.group(0))
                continue
            name = (op_name or "").strip()
            if not name:
                _dropped_segment(m.group(0), seq=seq)
                continue
            if seq in route:
                diagnostics.append(
                    {
                        "code": "route_duplicate_step_seq",
                        "field": "工艺路线",
                        "message": "工艺路线中同一工序号出现多次，系统只按第一次出现的名称转换，请核对该工序号的工时归属。",
                        "row_num": row_num,
                        "raw_value": route_raw,
                        "seq": seq,
                        "kept_name": route[seq],
                        "dropped_name": name,
                    }
                )
                continue
            route[seq] = name
        tail = normalized[consumed_end:]
        if tail:
            _dropped_segment(tail)
        return route, diagnostics

    @staticmethod
    def _pick_cell(row_values: Sequence[Any], idx: int) -> Any:
        return row_values[idx] if 0 <= idx < len(row_values) else None

    @staticmethod
    def _dedupe_keep_order(items: Iterable[str]) -> List[str]:
        seen: Set[str] = set()
        out: List[str] = []
        for it in items:
            v = (it or "").strip()
            if not v or v in seen:
                continue
            seen.add(v)
            out.append(v)
        return out

    def _normalize_route(self, route_raw: str) -> str:
        s = to_text(route_raw)
        if not s:
            return ""
        s = self._SEPARATORS_RE.sub("", s)
        s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        return s
