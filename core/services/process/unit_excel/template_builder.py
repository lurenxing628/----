from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

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
            ("零件工艺路线.xlsx", ["图号", "名称", "工艺路线字符串"], "routes_rows"),
            ("零件工序工时.xlsx", ["图号", "工序", "换型时间(h)", "单件工时(h)"], "part_operation_hours_rows"),
            ("人员基本信息.xlsx", ["工号", "姓名", "状态", "备注"], "operators_rows"),
            ("设备信息.xlsx", ["设备编号", "设备名称", "工种", "状态"], "machines_rows"),
            ("人员设备关联.xlsx", ["工号", "设备编号"], "operator_machine_rows"),
            ("工种配置.xlsx", ["工种ID", "工种名称", "归属"], "op_types_rows"),
            ("供应商配置.xlsx", ["供应商ID", "名称", "对应工种", "默认周期"], "suppliers_rows"),
        ]

    def rows_by_filename(self) -> Dict[str, List[Dict[str, Any]]]:
        result: Dict[str, List[Dict[str, Any]]] = {}
        for filename, _headers, field_name in self.output_specs():
            result[filename] = list(getattr(self, field_name))
        return result


class UnitTemplateBuilder:
    def build(self, parts: Dict[str, PartContext], stations: List[StationMeta]) -> ConvertedTemplates:
        machine_label_map = {s.machine_id: s.machine_label for s in stations}

        machine_op_hint: Dict[str, Counter] = defaultdict(Counter)
        for ctx in parts.values():
            for rec in ctx.step_records:
                if rec.seq is None:
                    continue
                op_name = ctx.route_map.get(rec.seq)
                if op_name:
                    machine_op_hint[rec.machine_id][op_name] += 1

        op_records: List[Dict[str, Any]] = []
        machine_internal_counter: Dict[str, Counter] = defaultdict(Counter)
        operator_names: Set[str] = set()
        used_machine_ids: Set[str] = set()
        links: Set[Tuple[str, str]] = set()

        for part_no in sorted(parts.keys()):
            ctx = parts[part_no]
            seq_to_records: Dict[int, List[StepRecord]] = defaultdict(list)
            internal_seq_set: Set[int] = set()

            for rec in ctx.step_records:
                if rec.seq is None:
                    continue
                seq_to_records[int(rec.seq)].append(rec)
                if rec.has_step_code and rec.operators:
                    internal_seq_set.add(int(rec.seq))

            inferred_missing_name: Dict[int, str] = {}
            for seq in sorted(internal_seq_set):
                if seq in ctx.route_map:
                    continue
                inferred_missing_name[seq] = self._infer_op_name_for_missing_seq(
                    seq=seq,
                    records=seq_to_records.get(seq, []),
                    machine_op_hint=machine_op_hint,
                )

            all_seqs = sorted(set(ctx.route_map.keys()) | internal_seq_set)
            for seq in all_seqs:
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
                    for rec in seq_records:
                        if not rec.has_step_code or not rec.operators:
                            continue
                        used_machine_ids.add(rec.machine_id)
                        machine_internal_counter[rec.machine_id][base_name] += 1
                        for name in rec.operators:
                            operator_names.add(name)
                            links.add((name, rec.machine_id))

        name_states: Dict[str, Set[str]] = defaultdict(set)
        for rec in op_records:
            state = "internal" if rec["source_internal"] else "external"
            name_states[str(rec["base_name"])].add(state)
        conflict_names = {name for name, states in name_states.items() if len(states) > 1}

        for rec in op_records:
            base_name = str(rec["base_name"])
            if rec["source_internal"]:
                final_name = base_name
            else:
                final_name = self._external_alias(base_name) if base_name in conflict_names else base_name
            rec["final_name"] = final_name

        route_rows: List[Dict[str, Any]] = []
        by_part: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for rec in op_records:
            by_part[str(rec["part_no"])].append(rec)
        for part_no in sorted(by_part.keys()):
            recs = sorted(by_part[part_no], key=lambda x: int(x["seq"]))
            part_name = str(recs[0]["part_name"] or part_no)
            route_string = "".join([f"{int(r['seq'])}{str(r['final_name'])}" for r in recs])
            route_rows.append({"图号": part_no, "名称": part_name, "工艺路线字符串": route_string})

        part_operation_hours_rows: List[Dict[str, Any]] = []
        for part_no in sorted(by_part.keys()):
            recs = sorted(by_part[part_no], key=lambda x: int(x["seq"]))
            for rec in recs:
                if not rec["source_internal"]:
                    continue
                part_operation_hours_rows.append(
                    {
                        "图号": part_no,
                        "工序": int(rec["seq"]),
                        "换型时间(h)": float(rec.get("setup_hours") or 0.0),
                        "单件工时(h)": float(rec.get("unit_hours") or 0.0),
                    }
                )

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
            operators_rows.append({"工号": op_id, "姓名": name, "状态": "active", "备注": None})

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
                    "状态": "active",
                }
            )

        operator_machine_rows: List[Dict[str, Any]] = []
        for operator_name, machine_id in sorted(links, key=lambda x: (operator_id_map.get(x[0], x[0]), x[1])):
            op_id = operator_id_map.get(operator_name)
            if not op_id:
                continue
            operator_machine_rows.append({"工号": op_id, "设备编号": machine_id})

        op_type_states: Dict[str, Set[str]] = defaultdict(set)
        for rec in op_records:
            nm = str(rec["final_name"])
            op_type_states[nm].add("internal" if rec["source_internal"] else "external")

        op_types_rows: List[Dict[str, Any]] = []
        for idx, op_name in enumerate(sorted(op_type_states.keys()), start=1):
            cat = "internal" if "internal" in op_type_states[op_name] else "external"
            op_types_rows.append({"工种ID": f"OT{idx:03d}", "工种名称": op_name, "归属": cat})

        external_days_by_name: Dict[str, List[float]] = defaultdict(list)
        for rec in op_records:
            if rec["source_internal"]:
                continue
            name = str(rec["final_name"])
            hint = rec.get("ext_days_hint")
            if isinstance(hint, (int, float)) and float(hint) > 0:
                external_days_by_name[name].append(float(hint))

        external_names = [r["工种名称"] for r in op_types_rows if str(r["归属"]).strip().lower() == "external"]
        suppliers_rows: List[Dict[str, Any]] = []
        for idx, op_name in enumerate(sorted(external_names), start=1):
            days_list = external_days_by_name.get(op_name) or []
            default_days = round(sum(days_list) / len(days_list), 4) if days_list else 1.0
            if default_days <= 0:
                default_days = 1.0
            suppliers_rows.append(
                {
                    "供应商ID": f"S{idx:03d}",
                    "名称": f"外协-{op_name}",
                    "对应工种": op_name,
                    "默认周期": default_days,
                }
            )

        return ConvertedTemplates(
            routes_rows=route_rows,
            part_operation_hours_rows=part_operation_hours_rows,
            operators_rows=operators_rows,
            machines_rows=machines_rows,
            operator_machine_rows=operator_machine_rows,
            op_types_rows=op_types_rows,
            suppliers_rows=suppliers_rows,
        )

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

