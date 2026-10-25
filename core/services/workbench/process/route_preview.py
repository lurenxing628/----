"""Read-only route interpretation; the caller owns the reference snapshot transaction."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from contextlib import contextmanager
from types import SimpleNamespace

from core.models.process_route_text import serialize_route_rows
from core.models.resource_capabilities import supplier_capability_rows, supports_source
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_route import (
    append_duplicate_diagnostics,
    check_route_capacity,
    normalize_route_preview_input,
    route_diagnostic,
    route_sequence,
)
from core.services.process.route_parser import RouteParser
from core.services.process.route_parser_tokens import (
    compact_name_ambiguities,
    parse_explicit_route,
    preprocess_route_string,
    route_format_errors,
    route_tokens,
)


def _segment_ambiguities(segment):
    # Validate BEFORE the legacy normalizer can erase a sign or join two numbers/names.
    spacing = re.sub(r"[\-—–→>＞]", "", segment)
    return (re.search(r"^\s*[+\-−]\s*\d|\s[+\-−]\d|\d[.．]\d|\d[eE][+\-]?\d", segment) is not None
            or re.search(r"\d\s+\d|[^\d\s]\s+[^\d\s]", spacing) is not None)


def _explicit_rows(explicit, diagnostics):
    check_route_capacity(len(explicit))
    result, sequences = [], []
    for raw_seq, name in explicit:
        seq = route_sequence(raw_seq)
        if seq is None:
            diagnostics.append(route_diagnostic("invalid_sequence", "工序号必须是正整数，而且不能超出可用范围。"))
            continue
        sequences.append(seq)
        if not name.strip():
            diagnostics.append(route_diagnostic("missing_operation_name", f"工序{seq}缺少工种名称。", sequence=seq))
        else:
            result.append((seq, name))
    append_duplicate_diagnostics(sequences, diagnostics)
    return result


def _segment_diagnostics(segment, normalized, tail, diagnostics):
    errors = route_format_errors(normalized)
    for message in errors:
        is_tail = tail is not None and message == errors[-1]
        diagnostics.append(route_diagnostic(
            "missing_operation_name" if is_tail else "missing_sequence", message,
            sequence=route_sequence(tail.group(1)) if is_tail else None))
    if _segment_ambiguities(segment):
        diagnostics.append(route_diagnostic("ambiguous_route_format", "工艺路线里有符号、小数、指数或空格，拼不出明确的工序。请改用逐行填工序号和工种名。"))


def _append_compact_tokens(tokens, operations, sequences, diagnostics):
    for seq, name in tokens:
        sequence = route_sequence(seq)
        if sequence is None:
            diagnostics.append(route_diagnostic("invalid_sequence", "工序号必须是正整数，而且不能超出可用范围。"))
        else:
            sequences.append(sequence)
            operations.append((sequence, name.strip()))


def _append_compact_tail(tail, sequences, diagnostics):
    if tail is None:
        return
    sequence = route_sequence(tail.group(1))
    if sequence is None:
        diagnostics.append(route_diagnostic("invalid_sequence", "最后一道工序号必须是正整数，而且不能超出可用范围。"))
    else:
        sequences.append(sequence)


def _compact_rows(raw, diagnostics):
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
        _segment_diagnostics(segment, normalized, tail, diagnostics)
        _append_compact_tokens(tokens, operations, sequences, diagnostics)
        _append_compact_tail(tail, sequences, diagnostics)
    append_duplicate_diagnostics(sequences, diagnostics)
    return operations


def _text_rows(raw, diagnostics):
    try:
        explicit = parse_explicit_route(raw)
    except ValueError as exc:
        diagnostics.append(route_diagnostic("explicit_route_invalid", str(exc)))
        return [], False
    return (_explicit_rows(explicit, diagnostics), False) if explicit is not None else (_compact_rows(raw, diagnostics), True)


def _structured_name_warnings(rows, diagnostics):
    for seq, name in rows:
        normalized = preprocess_route_string(str(seq) + name)
        if any(char.isdecimal() for char in name) or route_tokens(normalized) != [(str(seq), name)] or \
                route_format_errors(normalized) or ";" in name or "；" in name:
            diagnostics.append(route_diagnostic("structured_name_preserved", "工种名称已原样保留；系统会在整条路线中保留工序号和名称的边界，可直接导出后继续维护。", severity="warning", sequence=seq))


def _persisted_refs(identities, keys):
    keys = set(keys)
    if any(key not in identities or type(identities[key].ref) is not str or
           re.fullmatch(r"[0-9a-f]{48}", identities[key].ref) is None for key in keys):
        raise WorkbenchCommandRejected("storage_failure", "工艺参考资料找不到编号，或者编号无效，请联系维护人员核对资料。", 500)
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
    def __init__(self, conn, logger=None, *, facts):
        self.conn, self.logger = conn, logger
        self._batch = None
        self._facts = facts

    @contextmanager
    def reference_snapshot(self):
        """Reuse reference reads only within the caller's existing transaction."""
        if not self.conn.in_transaction:
            raise RuntimeError("Batch route previews require a caller-owned read transaction.")
        previous = self._batch
        facts = self._reference_facts()
        self._batch = {"facts": facts, "candidates": self._candidates(facts[0], facts[1]), "refs": ({}, {})}
        try:
            yield self
        finally:
            self._batch = previous

    def _reference_facts(self):
        references = self._facts.references
        types = {row["op_type_id"]: SimpleNamespace(**row) for row in references["OpTypes"]}
        capabilities = supplier_capability_rows(references["Suppliers"], references["WorkbenchSupplierOpTypes"], "active")
        parser = RouteParser(types, capabilities, logger=self.logger)
        return types, capabilities, parser.build_parse_context(), {row["supplier_id"]: row for row in references["Suppliers"]}

    def preview(self, body):
        request = normalize_route_preview_input(body)
        diagnostics = list(request.diagnostics)
        rows, compact = _text_rows(request.route_raw, diagnostics) if request.mode == "text" else (request.rows, False)
        if request.mode == "rows":
            _structured_name_warnings(rows, diagnostics)
        if not rows:
            diagnostics.append(route_diagnostic("empty_route", "这条工艺路线里没有可检查的工序。请先填写工序。"))
        operations = self._interpret_operations(rows, diagnostics, compact=compact)
        _append_operation_diagnostics(operations, diagnostics)
        recognized = sum(op["op_type_ref"] is not None for op in operations)
        return {"mode": request.mode, "route_raw": request.route_raw,
                "normalized_input": serialize_route_rows(rows),
                "operations": operations, "diagnostics": diagnostics,
                "can_confirm_route": bool(operations) and not any(d["severity"] == "error" for d in diagnostics),
                "counts": {"operations": len(operations), "recognized": recognized, "unknown": len(operations) - recognized}}

    def _interpret_operations(self, rows, diagnostics, compact):
        types, capabilities, context, suppliers = self._reference_facts() if self._batch is None else self._batch["facts"]
        if compact:
            diagnostics.extend(route_diagnostic("ambiguous_numeric_name", message, sequence=seq)
                               for seq, message in compact_name_ambiguities(rows, context.numeric_names))
        op_refs, supplier_refs = self._route_refs(context, {name for _, name in rows})
        candidates = self._candidates(types, capabilities) if self._batch is None else self._batch["candidates"]
        for issue in context.supplier_global_issues:
            ot = types.get(issue.op_type_id)
            label = "工种“" + ot.name + "”" if ot else "供应商承接能力资料"
            diagnostics.append(route_diagnostic("supplier_capability_invalid", label + "的承接能力关系无效。请到资料总览核对。", severity="warning"))
        return [self._operation(seq, name, context, candidates, suppliers, op_refs, supplier_refs)
                for seq, name in sorted(rows, key=lambda row: row[0])]

    def _route_refs(self, context, names):
        op_ids = [context.op_types[name].op_type_id for name in names if name in context.op_types]
        sup_ids = [context.suppliers[name] for name in names
                   if name in context.suppliers and context.op_types[name].category == "external"]
        if self._batch is not None:
            cached_ops, cached_suppliers = self._batch["refs"]
            op_keys = [op_id for op_id in op_ids if op_id not in cached_ops]
            if op_keys:
                cached_ops.update(_persisted_refs(self._facts.identities_by_kind["op_type"], op_keys))
            sup_keys = [supplier_id for supplier_id in sup_ids if supplier_id not in cached_suppliers]
            if sup_keys:
                cached_suppliers.update(_persisted_refs(self._facts.identities_by_kind["supplier"], sup_keys))
            return cached_ops, cached_suppliers
        op_refs = _persisted_refs(self._facts.identities_by_kind["op_type"], op_ids)
        supplier_refs = _persisted_refs(self._facts.identities_by_kind["supplier"], sup_ids)
        return op_refs, supplier_refs

    @staticmethod
    def _candidates(types, capabilities):
        candidates = {}
        for row in capabilities:
            ot = types.get(row["op_type_id"])
            if ot is not None and supports_source(ot.category, "external") and not row["missing_supplier"]:
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
        if ot.category not in ("internal", "external", "both"):
            result["basis"] = "已登记工种的类别无效，系统不猜是自制还是外协。"
            result["issues"].append({"code": "invalid_op_type_category", "message": "工种类别既不是自制也不是外协，归属还要核对。"})
            return result
        result["source_suggestion"] = "internal" if ot.category == "both" else ot.category
        result["basis"] = "该工种自制和外协都可，当前建议自制，请在归属步骤确认。" if ot.category == "both" else "按工种类别匹配；可在归属步骤修改。"
        if ot.category == "external":
            ProcessRoutePreviewService._supplier_suggestion(result, context, candidates, suppliers, supplier_refs)
        return result

    @staticmethod
    def _supplier_suggestion(result, context, candidates, suppliers, supplier_refs):
        name = result["op_type_name"]
        key = context.suppliers.get(name)
        if key is None:
            result["issues"].append({"code": "supplier_missing", "message": "没有能承接这个工种的供应商，供应商和外协周期还要确认。"})
            return
        raw = candidates[name][key]
        if key not in suppliers or type(suppliers[key]["name"]) is not str:
            raise WorkbenchCommandRejected("storage_failure", "建议的供应商名称缺失或无效。请到资料总览核对。", 500)
        result.update(supplier_ref=supplier_refs[key], supplier_label=suppliers[key]["name"],
                      external_days=_positive_days(raw["default_days"]))
        if len(candidates[name]) > 1:
            result["basis"] += "供应商按编号排序选择最后一家。"
            result["issues"].append({"code": "multiple_supplier_candidates",
                                     "message": f"有 {len(candidates[name])} 家供应商可承接，可在归属步骤改选。"})
        if result["external_days"] is None:
            result["issues"].append({"code": "external_days_missing_or_invalid", "message": "外协周期未填写或无效。请到基础资料补填周期。"})
