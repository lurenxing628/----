"""Read-only route interpretation; the caller owns the reference snapshot transaction."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from contextlib import contextmanager
from types import SimpleNamespace

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_route import (
    append_duplicate_diagnostics,
    check_route_capacity,
    normalize_route_preview_input,
    route_diagnostic,
    route_sequence,
)
from core.services.process.route_parser import RouteParser
from core.services.process.route_parser_tokens import preprocess_route_string, route_format_errors, route_tokens
from data.repositories.base_repo import BaseRepository
from data.repositories.supplier_repo import SupplierRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository


class _OpTypeSnapshot:
    def __init__(self, records):
        self.records = {row["op_type_id"]: SimpleNamespace(**row) for row in records}

    def list(self):
        return list(self.records.values())

    def get(self, key):
        return self.records.get(key)


class _CapabilitySnapshot:
    def __init__(self, records):
        self.records = records

    def list_capabilities(self, status=None):
        return self.records


def _segment_ambiguities(segment):
    # Validate BEFORE the legacy normalizer can erase a sign or join two numbers/names.
    spacing = re.sub(r"[\-—–→>＞]", "", segment)
    return (re.search(r"^\s*[+\-−]\s*\d|\s[+\-−]\d|\d[.．]\d|\d[eE][+\-]?\d", segment) is not None
            or re.search(r"\d\s+\d|[^\d\s]\s+[^\d\s]", spacing) is not None)


def _text_rows(raw, diagnostics):
    operations, sequences, input_count = [], [], 0
    # Hard boundaries must survive until each fragment's missing prefix/tail is diagnosed.
    for segment in re.split(r"[,，、;；\r\n]", raw):
        normalized = preprocess_route_string(segment)
        if not normalized:
            continue
        # Bound digit runs before the formal regexes; an invalid huge token becomes
        # a diagnosed invalid zero, never an expensive regex/int conversion.
        normalized = re.sub(r"\d{20,}", lambda match: str(route_sequence(match.group()) or 0), normalized)
        tokens = route_tokens(normalized)
        tail = re.search(r"(\d+)$", normalized)
        input_count += max(1, len(tokens) + bool(tail))
        check_route_capacity(input_count)
        errors = route_format_errors(normalized)
        for message in errors:
            is_tail = tail is not None and message == errors[-1]
            diagnostics.append(route_diagnostic(
                "missing_operation_name" if is_tail else "missing_sequence", message,
                sequence=route_sequence(tail.group(1)) if is_tail and tail is not None else None))
        if _segment_ambiguities(segment):
            diagnostics.append(route_diagnostic("ambiguous_route_format", "工艺路线里有符号、小数、指数或空格，拼不出明确的工序。请改用逐行填工序号和工种名。"))
        for seq, name in tokens:
            sequence = route_sequence(seq)
            if sequence is None:
                diagnostics.append(route_diagnostic("invalid_sequence", "工序号必须是正整数，而且不能超出可用范围。"))
            else:
                sequences.append(sequence)
                operations.append((sequence, name.strip()))
        if tail:
            sequence = route_sequence(tail.group(1))
            if sequence is None:
                diagnostics.append(route_diagnostic("invalid_sequence", "最后一道工序号必须是正整数，而且不能超出可用范围。"))
            else:
                sequences.append(sequence)
    append_duplicate_diagnostics(sequences, diagnostics)
    return operations


def _structured_name_warnings(rows, diagnostics):
    for seq, name in rows:
        normalized = preprocess_route_string(str(seq) + name)
        if any(char.isdecimal() for char in name) or route_tokens(normalized) != [(str(seq), name)] or \
                route_format_errors(normalized) or ";" in name or "；" in name:
            diagnostics.append(route_diagnostic("structured_name_preserved", "工种名称已按逐行输入原样保留；名称含空格、数字或分隔符时，请继续用逐行模式修改。", severity="warning", sequence=seq))


def _persisted_refs(repo, kind, keys, cached=None):
    keys = set(keys)
    identities = repo.active_map(kind, keys) if cached is None else cached
    if any(key not in identities or type(identities[key].ref) is not str or
           re.fullmatch(r"[0-9a-f]{48}", identities[key].ref) is None for key in keys):
        raise WorkbenchCommandRejected("storage_failure", "工艺参考资料找不到编号，或者编号无效，系统不会自动补建。请刷新重试；仍不行请联系维护人员。", 500)
    return {key: identities[key].ref for key in keys}


def _positive_days(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        days = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return days if math.isfinite(days) and days > 0 else None


def _append_operation_diagnostics(operations, diagnostics):
    errors_by_sequence = defaultdict(list)
    for diagnostic in diagnostics:
        if diagnostic["severity"] == "error" and "sequence" in diagnostic:
            errors_by_sequence[diagnostic["sequence"]].append({"code": diagnostic["code"], "message": diagnostic["message"]})
    for op in operations:
        for issue in op["issues"]:
            diagnostics.append(route_diagnostic(issue["code"], issue["message"], severity="warning", sequence=op["sequence"]))
        op["issues"].extend(errors_by_sequence[op["sequence"]])


class ProcessRoutePreviewService:
    def __init__(self, conn, logger=None):
        self.conn, self.logger = conn, logger
        self._batch = None

    @contextmanager
    def reference_snapshot(self):
        """Reuse reference reads only within the caller's existing transaction."""
        if not self.conn.in_transaction:
            raise RuntimeError("Batch route previews require a caller-owned read transaction.")
        previous = self._batch
        facts = self._reference_facts()
        types, capabilities, context, _ = facts
        identities = WorkbenchIdentityRepository(self.conn, self.logger)
        self._batch = {"facts": facts, "candidates": self._candidates(types, capabilities),
                       "op_refs": identities.active_map("op_type", [row.op_type_id for row in context.op_types.values()]),
                       "supplier_refs": identities.active_map("supplier", [value[0] for value in context.suppliers.values()])}
        try:
            yield self
        finally:
            self._batch = previous

    def _reference_facts(self):
        repo = BaseRepository(self.conn, self.logger)
        types = _OpTypeSnapshot(repo.fetchall("SELECT op_type_id, name, category FROM OpTypes"))
        capabilities = SupplierRepository(self.conn, self.logger).list_capabilities(status="active")
        parser = RouteParser(types, _CapabilitySnapshot(capabilities), logger=self.logger)
        context = parser.build_parse_context()
        suppliers = {row["supplier_id"]: row for row in repo.fetchall("SELECT supplier_id, name FROM Suppliers")}
        return types, capabilities, context, suppliers

    def preview(self, body):
        request = normalize_route_preview_input(body)
        diagnostics = list(request.diagnostics)
        rows = _text_rows(request.route_raw, diagnostics) if request.mode == "text" else request.rows
        if request.mode == "rows":
            _structured_name_warnings(rows, diagnostics)
        if not rows:
            diagnostics.append(route_diagnostic("empty_route", "这条工艺路线里没有可检查的工序。请先填写工序。"))
        operations = self._interpret_operations(rows, diagnostics)
        _append_operation_diagnostics(operations, diagnostics)
        recognized = sum(op["op_type_ref"] is not None for op in operations)
        return {"mode": request.mode, "route_raw": request.route_raw,
                "normalized_input": "\n".join(str(seq) + " " + name for seq, name in rows) if request.mode == "rows" else preprocess_route_string(re.sub(r"[;；]", "", request.route_raw)),
                "operations": operations, "diagnostics": diagnostics,
                "can_confirm_route": bool(operations) and not any(d["severity"] == "error" for d in diagnostics),
                "counts": {"operations": len(operations), "recognized": recognized, "unknown": len(operations) - recognized}}

    def _interpret_operations(self, rows, diagnostics):
        types, capabilities, context, suppliers = self._reference_facts() if self._batch is None else self._batch["facts"]
        op_refs, supplier_refs = self._route_refs(context, {name for _, name in rows})
        candidates = self._candidates(types, capabilities) if self._batch is None else self._batch["candidates"]
        for issue in context.supplier_global_issues:
            ot = types.get(issue.op_type_id)
            label = "工种“" + ot.name + "”" if ot else "供应商承接能力资料"
            diagnostics.append(route_diagnostic("supplier_capability_invalid", label + "的承接能力关系无效。请到资料总览核对。", severity="warning"))
        return [self._operation(seq, name, context, candidates, suppliers, op_refs, supplier_refs)
                for seq, name in sorted(rows, key=lambda row: row[0])]

    def _route_refs(self, context, names):
        identities = WorkbenchIdentityRepository(self.conn, self.logger)
        op_refs = _persisted_refs(identities, "op_type", [ot.op_type_id for name, ot in context.op_types.items() if name in names],
                                  None if self._batch is None else self._batch["op_refs"])
        supplier_refs = _persisted_refs(identities, "supplier", [value[0] for name, value in context.suppliers.items()
                                       if name in names and context.op_types[name].category == "external"],
                                        None if self._batch is None else self._batch["supplier_refs"])
        return op_refs, supplier_refs

    @staticmethod
    def _candidates(types, capabilities):
        candidates = {}
        for row in capabilities:
            ot = types.get(row["op_type_id"])
            if ot is not None and ot.category == "external" and not row["missing_supplier"]:
                candidates.setdefault(ot.name, {})[row["supplier_id"]] = row
        return candidates

    @staticmethod
    def _operation(seq, name, context, candidates, suppliers, op_refs, supplier_refs):
        ot = context.op_types.get(name)
        result = {"sequence": seq, "op_type_name": name, "op_type_ref": None, "source_suggestion": None,
                  "supplier_ref": None, "supplier_label": None, "external_days": None,
                  "basis": "没有匹配到已登记的工种，归属这一步还要先建档再确认。", "issues": []}
        if ot is None:
            result["issues"].append({"code": "unknown_op_type", "message": "这个工种还没登记，工艺路线可以先确认；归属要先建档，暂时不能据此排产。"})
            return result
        result["op_type_ref"] = op_refs[ot.op_type_id]
        if ot.category not in ("internal", "external"):
            result["basis"] = "已登记工种的类别无效，系统不猜是自制还是外协。"
            result["issues"].append({"code": "invalid_op_type_category", "message": "工种类别既不是自制也不是外协，归属还要核对。"})
            return result
        result["source_suggestion"] = ot.category
        result["basis"] = "这是按已登记的工种类别给出的归属建议，还不算人工确认。"
        if ot.category == "external":
            ProcessRoutePreviewService._supplier_suggestion(result, context, candidates, suppliers, supplier_refs)
        return result

    @staticmethod
    def _supplier_suggestion(result, context, candidates, suppliers, supplier_refs):
        name = result["op_type_name"]
        selected = context.suppliers.get(name)
        if selected is None:
            result["issues"].append({"code": "supplier_missing", "message": "没有能承接这个工种的供应商，供应商和外协周期还要确认。"})
            return
        key = selected[0]
        raw = candidates[name][key]
        if key not in suppliers or type(suppliers[key]["name"]) is not str:
            raise WorkbenchCommandRejected("storage_failure", "建议的供应商名称缺失或无效。请到资料总览核对。", 500)
        result.update(supplier_ref=supplier_refs[key], supplier_label=suppliers[key]["name"],
                      external_days=_positive_days(raw["default_days"]))
        result["basis"] += "供应商从当前能承接这个工种的记录里选；有多家时按编号排序取最后一家，仅供核对。"
        if len(candidates[name]) > 1:
            result["issues"].append({"code": "multiple_supplier_candidates", "message": "有多家供应商能承接，这里按系统既有规则给了一家建议，仍要人工确认。"})
        if result["external_days"] is None:
            result["issues"].append({"code": "external_days_missing_or_invalid", "message": "外协周期没填，或者不是正数，系统不会补成 1 天。请到基础资料补填周期。"})
