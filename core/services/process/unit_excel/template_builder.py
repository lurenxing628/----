from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from core.models.enums import MachineStatus, OperatorStatus, SourceType, SupplierStatus, YesNo
from core.services.common.excel_templates import get_template_definition

from .parser import PartContext, StationMeta, StepRecord


@dataclass
class ConvertedTemplates:
    routes_rows: List[Dict[str, Any]]
    part_operation_hours_rows: List[Dict[str, Any]]
    operators_rows: List[Dict[str, Any]]
    machines_rows: List[Dict[str, Any]]
    operator_machine_rows: List[Dict[str, Any]]
    op_types_rows: List[Dict[str, Any]]
    suppliers_rows: List[Dict[str, Any]]

    @staticmethod
    def output_specs() -> List[Tuple[str, List[str], str]]:
        return [
            ("零件工艺路线.xlsx", list(get_template_definition("零件工艺路线.xlsx")["headers"]), "routes_rows"),
            ("零件工序工时.xlsx", list(get_template_definition("零件工序工时.xlsx")["headers"]), "part_operation_hours_rows"),
            ("人员基本信息.xlsx", list(get_template_definition("人员基本信息.xlsx")["headers"]), "operators_rows"),
            ("设备信息.xlsx", list(get_template_definition("设备信息.xlsx")["headers"]), "machines_rows"),
            ("人员设备关联.xlsx", list(get_template_definition("人员设备关联.xlsx")["headers"]), "operator_machine_rows"),
            ("工种配置.xlsx", list(get_template_definition("工种配置.xlsx")["headers"]), "op_types_rows"),
            ("供应商配置.xlsx", list(get_template_definition("供应商配置.xlsx")["headers"]), "suppliers_rows"),
        ]


class UnitTemplateBuilder:
    def build(self, parts: Dict[str, PartContext], stations: List[StationMeta]) -> ConvertedTemplates:
        machine_label_map = {s.machine_id: s.machine_label for s in stations}
        machine_op_hint = self._build_machine_op_hint(parts)

        op_records, machine_internal_counter, operator_names, used_machine_ids, links = self._collect_op_records(
            parts, machine_op_hint
        )

        conflict_names = self._conflict_names(op_records)
        self._apply_final_names(op_records, conflict_names)

        by_part = self._group_op_records_by_part(op_records)
        route_rows = self._build_route_rows(by_part)
        part_operation_hours_rows = self._build_part_operation_hours_rows(by_part)

        operator_id_map, operators_rows = self._build_operator_rows(operator_names)
        machines_rows = self._build_machines_rows(
            used_machine_ids=used_machine_ids,
            machine_label_map=machine_label_map,
            machine_internal_counter=machine_internal_counter,
        )
        operator_machine_rows = self._build_operator_machine_rows(links, operator_id_map)

        op_types_rows = self._build_op_types_rows(op_records)
        suppliers_rows = self._build_suppliers_rows(op_records, op_types_rows)

        return ConvertedTemplates(
            routes_rows=route_rows,
            part_operation_hours_rows=part_operation_hours_rows,
            operators_rows=operators_rows,
            machines_rows=machines_rows,
            operator_machine_rows=operator_machine_rows,
            op_types_rows=op_types_rows,
            suppliers_rows=suppliers_rows,
        )

    @staticmethod
    def _build_machine_op_hint(parts: Dict[str, PartContext]) -> Dict[str, Counter]:
        machine_op_hint: Dict[str, Counter] = defaultdict(Counter)
        for ctx in parts.values():
            for rec in ctx.step_records:
                if rec.seq is None:
                    continue
                op_name = ctx.route_map.get(rec.seq)
                if op_name:
                    machine_op_hint[rec.machine_id][op_name] += 1
        return machine_op_hint

    @staticmethod
    def _build_seq_maps(ctx: PartContext) -> Tuple[Dict[int, List[StepRecord]], Set[int]]:
        seq_to_records: Dict[int, List[StepRecord]] = defaultdict(list)
        internal_seq_set: Set[int] = set()
        for rec in ctx.step_records:
            if rec.seq is None:
                continue
            seq = int(rec.seq)
            seq_to_records[seq].append(rec)
            if rec.has_step_code and rec.operators:
                internal_seq_set.add(seq)
        return seq_to_records, internal_seq_set

    def _infer_missing_name_map(
        self,
        ctx: PartContext,
        *,
        internal_seq_set: Set[int],
        seq_to_records: Dict[int, List[StepRecord]],
        machine_op_hint: Dict[str, Counter],
    ) -> Dict[int, str]:
        inferred_missing_name: Dict[int, str] = {}
        for seq in sorted(internal_seq_set):
            if seq in ctx.route_map:
                continue
            inferred_missing_name[seq] = self._infer_op_name_for_missing_seq(
                seq=seq,
                records=seq_to_records.get(seq, []),
                machine_op_hint=machine_op_hint,
            )
        return inferred_missing_name

    @staticmethod
    def _all_seqs(ctx: PartContext, internal_seq_set: Set[int]) -> List[int]:
        return sorted(set(ctx.route_map.keys()) | set(internal_seq_set))

    def _collect_op_records(
        self, parts: Dict[str, PartContext], machine_op_hint: Dict[str, Counter]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Counter], Set[str], Set[str], Set[Tuple[str, str]]]:
        op_records: List[Dict[str, Any]] = []
        machine_internal_counter: Dict[str, Counter] = defaultdict(Counter)
        operator_names: Set[str] = set()
        used_machine_ids: Set[str] = set()
        links: Set[Tuple[str, str]] = set()

        for part_no in sorted(parts.keys()):
            ctx = parts[part_no]
            seq_to_records, internal_seq_set = self._build_seq_maps(ctx)
            inferred_missing_name = self._infer_missing_name_map(
                ctx,
                internal_seq_set=internal_seq_set,
                seq_to_records=seq_to_records,
                machine_op_hint=machine_op_hint,
            )

            for seq in self._all_seqs(ctx, internal_seq_set):
                base_name = (ctx.route_map.get(seq) or inferred_missing_name.get(seq) or f"工序{seq}").strip()
                source_internal = seq in internal_seq_set

                seq_records = seq_to_records.get(seq, [])
                setup_h, unit_h = self._aggregate_internal_hours(seq_records) if source_internal else (0.0, 0.0)
                ext_days_hint = None if source_internal else self._estimate_external_days(seq_records)

                op_records.append(
                    {
                        "part_no": ctx.part_no,
                        "part_name": ctx.part_name,
                        "seq": int(seq),
                        "base_name": base_name,
                        "source_internal": bool(source_internal),
                        "ext_days_hint": ext_days_hint,
                        "setup_hours": float(setup_h),
                        "unit_hours": float(unit_h),
                    }
                )

                if source_internal:
                    self._append_internal_links_and_counters(
                        seq_records=seq_records,
                        base_name=base_name,
                        used_machine_ids=used_machine_ids,
                        machine_internal_counter=machine_internal_counter,
                        operator_names=operator_names,
                        links=links,
                    )

        return op_records, machine_internal_counter, operator_names, used_machine_ids, links

    @staticmethod
    def _append_internal_links_and_counters(
        *,
        seq_records: Sequence[StepRecord],
        base_name: str,
        used_machine_ids: Set[str],
        machine_internal_counter: Dict[str, Counter],
        operator_names: Set[str],
        links: Set[Tuple[str, str]],
    ) -> None:
        for rec in seq_records:
            if not rec.has_step_code or not rec.operators:
                continue
            used_machine_ids.add(rec.machine_id)
            machine_internal_counter[rec.machine_id][base_name] += 1
            for name in rec.operators:
                operator_names.add(name)
                links.add((name, rec.machine_id))

    @staticmethod
    def _conflict_names(op_records: Sequence[Dict[str, Any]]) -> Set[str]:
        name_states: Dict[str, Set[str]] = defaultdict(set)
        for rec in op_records:
            state = SourceType.INTERNAL.value if rec.get("source_internal") else SourceType.EXTERNAL.value
            name_states[str(rec.get("base_name") or "")].add(state)
        return {name for name, states in name_states.items() if len(states) > 1}

    def _apply_final_names(self, op_records: List[Dict[str, Any]], conflict_names: Set[str]) -> None:
        for rec in op_records:
            base_name = str(rec.get("base_name") or "")
            if rec.get("source_internal"):
                final_name = base_name
            else:
                final_name = self._external_alias(base_name) if base_name in conflict_names else base_name
            rec["final_name"] = final_name

    @staticmethod
    def _group_op_records_by_part(op_records: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        by_part: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for rec in op_records:
            by_part[str(rec.get("part_no") or "")].append(rec)
        return by_part

    @staticmethod
    def _build_route_rows(by_part: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        route_rows: List[Dict[str, Any]] = []
        for part_no in sorted(by_part.keys()):
            recs = sorted(by_part[part_no], key=lambda x: int(x["seq"]))
            part_name = str(recs[0].get("part_name") or part_no)
            route_string = "".join([f"{int(r['seq'])}{str(r.get('final_name') or '')}" for r in recs])
            route_rows.append({"图号": part_no, "名称": part_name, "工艺路线字符串": route_string})
        return route_rows

    @staticmethod
    def _build_part_operation_hours_rows(by_part: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for part_no in sorted(by_part.keys()):
            recs = sorted(by_part[part_no], key=lambda x: int(x["seq"]))
            for rec in recs:
                if not rec.get("source_internal"):
                    continue
                rows.append(
                    {
                        "图号": part_no,
                        "工序": int(rec["seq"]),
                        "换型时间(h)": float(rec.get("setup_hours") or 0.0),
                        "单件工时(h)": float(rec.get("unit_hours") or 0.0),
                    }
                )
        return rows

    @staticmethod
    def _build_operator_rows(operator_names: Set[str]) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        operator_id_map: Dict[str, str] = {}
        used_operator_ids: Set[str] = set()
        operators_rows: List[Dict[str, Any]] = []
        next_operator_no = 900001
        for name in sorted(operator_names):
            while f"{next_operator_no:06d}" in used_operator_ids:
                next_operator_no += 1
            op_id = f"{next_operator_no:06d}"
            used_operator_ids.add(op_id)
            next_operator_no += 1
            operator_id_map[name] = op_id
            operators_rows.append({"工号": op_id, "姓名": name, "状态": OperatorStatus.ACTIVE.value, "班组": None, "备注": None})
        return operator_id_map, operators_rows

    def _build_machines_rows(
        self,
        *,
        used_machine_ids: Set[str],
        machine_label_map: Dict[str, str],
        machine_internal_counter: Dict[str, Counter],
    ) -> List[Dict[str, Any]]:
        machines_rows: List[Dict[str, Any]] = []
        for machine_id in sorted(used_machine_ids):
            display = machine_label_map.get(machine_id) or machine_id
            machine_name = self._build_machine_name(machine_id=machine_id, machine_label=display)
            op_name = self._most_common_key(machine_internal_counter.get(machine_id))
            machines_rows.append(
                {
                    "设备编号": machine_id,
                    "设备名称": machine_name,
                    "工种": op_name,
                    "班组": None,
                    "状态": MachineStatus.ACTIVE.value,
                }
            )
        return machines_rows

    @staticmethod
    def _build_operator_machine_rows(links: Set[Tuple[str, str]], operator_id_map: Dict[str, str]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for operator_name, machine_id in sorted(links, key=lambda x: (operator_id_map.get(x[0], x[0]), x[1])):
            op_id = operator_id_map.get(operator_name)
            if not op_id:
                continue
            rows.append({"工号": op_id, "设备编号": machine_id, "技能等级": "normal", "主操设备": YesNo.NO.value})
        return rows

    @staticmethod
    def _build_op_types_rows(op_records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        op_type_states: Dict[str, Set[str]] = defaultdict(set)
        for rec in op_records:
            nm = str(rec.get("final_name") or "")
            st = SourceType.INTERNAL.value if rec.get("source_internal") else SourceType.EXTERNAL.value
            op_type_states[nm].add(st)

        op_types_rows: List[Dict[str, Any]] = []
        for idx, op_name in enumerate(sorted(op_type_states.keys()), start=1):
            cat = SourceType.INTERNAL.value if SourceType.INTERNAL.value in op_type_states[op_name] else SourceType.EXTERNAL.value
            op_types_rows.append({"工种ID": f"OT{idx:03d}", "工种名称": op_name, "归属": cat})
        return op_types_rows

    @staticmethod
    def _build_suppliers_rows(op_records: Sequence[Dict[str, Any]], op_types_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        external_days_by_name: Dict[str, List[float]] = defaultdict(list)
        for rec in op_records:
            if rec.get("source_internal"):
                continue
            name = str(rec.get("final_name") or "")
            hint = rec.get("ext_days_hint")
            if isinstance(hint, (int, float)) and float(hint) > 0:
                external_days_by_name[name].append(float(hint))

        external_names = [
            str(r.get("工种名称") or "")
            for r in op_types_rows
            if str(r.get("归属") or "").strip() == SourceType.EXTERNAL.value
        ]
        suppliers_rows: List[Dict[str, Any]] = []
        for idx, op_name in enumerate(sorted([n for n in external_names if n]), start=1):
            days_list = external_days_by_name.get(op_name) or []
            default_days = round(sum(days_list) / len(days_list), 4) if days_list else 1.0
            suppliers_rows.append(
                {
                    "供应商ID": f"S{idx:03d}",
                    "名称": f"外协-{op_name}",
                    "对应工种": op_name,
                    "默认周期": default_days,
                    "状态": SupplierStatus.ACTIVE.value,
                    "备注": None,
                }
            )
        return suppliers_rows

    def _infer_op_name_for_missing_seq(
        self,
        seq: int,
        records: Iterable[StepRecord],
        machine_op_hint: Dict[str, Counter],
    ) -> str:
        rec_list = list(records)
        for rec in rec_list:
            c = machine_op_hint.get(rec.machine_id)
            name = self._most_common_key(c)
            if name:
                return name

        merged_text = " ".join([r.step_text for r in rec_list])
        if "铣" in merged_text:
            return "数铣"
        if "车" in merged_text or "镗" in merged_text:
            return "数车"
        if any(k in merged_text for k in ("攻丝", "修锉", "制钝", "去毛刺", "钳")):
            return "钳工"
        if "检" in merged_text:
            return "检验"
        return f"工序{seq}"

    def _aggregate_internal_hours(self, records: Sequence[StepRecord]) -> Tuple[float, float]:
        step_time: Dict[str, Dict[str, float]] = {}
        for rec in records:
            if not rec.has_step_code:
                continue
            step_key = self._extract_step_key(rec.step_text)
            if not step_key:
                continue
            if step_key not in step_time:
                step_time[step_key] = {"setup_min": 0.0, "unit_min": 0.0}
            if isinstance(rec.setup_min, (int, float)) and float(rec.setup_min) > 0:
                step_time[step_key]["setup_min"] = max(step_time[step_key]["setup_min"], float(rec.setup_min))
            if isinstance(rec.unit_min, (int, float)) and float(rec.unit_min) > 0:
                step_time[step_key]["unit_min"] = max(step_time[step_key]["unit_min"], float(rec.unit_min))

        setup_min_sum = sum(v.get("setup_min", 0.0) for v in step_time.values())
        unit_min_sum = sum(v.get("unit_min", 0.0) for v in step_time.values())
        return round(setup_min_sum / 60.0, 6), round(unit_min_sum / 60.0, 6)

    @staticmethod
    def _extract_step_key(step_text: str) -> str:
        s = (step_text or "").strip()
        if not s:
            return ""
        m = re.match(r"^(\d{1,3}-[0-9A-Za-z]+)", s)
        return m.group(1) if m else ""

    @staticmethod
    def _estimate_external_days(records: Sequence[StepRecord]) -> Optional[float]:
        vals: List[float] = []
        for rec in records:
            candidate = None
            if isinstance(rec.batch_min, (int, float)) and rec.batch_min > 0:
                candidate = float(rec.batch_min)
            elif isinstance(rec.setup_min, (int, float)) and isinstance(rec.unit_min, (int, float)):
                total = float(rec.setup_min) + float(rec.unit_min)
                if total > 0:
                    candidate = total
            elif isinstance(rec.unit_min, (int, float)) and rec.unit_min > 0:
                candidate = float(rec.unit_min)
            if candidate and candidate > 0:
                vals.append(candidate / 480.0)
        if not vals:
            return None
        avg = sum(vals) / len(vals)
        return round(max(avg, 0.0001), 6)

    @staticmethod
    def _external_alias(name: str) -> str:
        s = (name or "").strip()
        if not s:
            return "外协工序"
        return s if s.endswith("（外协）") else f"{s}（外协）"

    @staticmethod
    def _most_common_key(counter: Optional[Counter]) -> Optional[str]:
        if not counter:
            return None
        try:
            return counter.most_common(1)[0][0]
        except Exception:
            return None

    @staticmethod
    def _build_machine_name(machine_id: str, machine_label: str) -> str:
        label = (machine_label or "").strip()
        label = re.sub(r"[（(].*?[）)]", "", label).strip()
        mid = (machine_id or "").strip()
        if label and label != mid:
            return label
        return mid or label

