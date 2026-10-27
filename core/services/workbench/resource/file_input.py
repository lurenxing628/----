"""Sparse file values to existing domain DTOs, with explicit code resolution."""

import math
from dataclasses import asdict
from typing import Any, Dict

from core.errors import ValidationError
from core.models.resource_capabilities import supports_source
from core.models.workbench_resource_file import (
    MULTI_CODES,
    NULLABLE,
    NUMERIC_FIELDS,
    RELATIONS,
    WRITABLE,
    column_label,
)


def _column(kind, field):
    """提示里按文件表头上的中文列名称呼这一列。"""
    return "「" + column_label(kind, field) + "」这一列"


def same_value(left, right, field):
    if field in NUMERIC_FIELDS and type(left) in (int, float) and type(right) in (int, float):
        return math.isfinite(left) and math.isfinite(right) and left == right
    return type(left) is type(right) and left == right


def _same_column(field, value, previous):
    if field in MULTI_CODES and type(value) is list and type(previous) is list:
        return sorted(value) == sorted(previous)
    return same_value(value, previous, field)


class ResourceFileInput:
    def __init__(self, reader, preparation):
        self.reader, self.preparation, self.kind = reader, preparation, reader.kind

    def normalize(self, action, code, values, before, scope):
        changes = self._changes(values, before, scope)
        self._clear_fields(changes)
        payload: Dict[str, Any] = {"fields": {}}
        related = {}
        if action == "create":
            payload["business_code"] = code
            self._new_fields(changes, scope)
        for key, value in changes.items():
            if key == "label":
                payload["label"] = value
            elif key in RELATIONS[self.kind]:
                target, target_kind, _ = RELATIONS[self.kind][key]
                selected, evidence = self._relation(value, key, target_kind)
                payload.setdefault("relationships", {})[target] = selected
                related[key] = evidence
            else:
                payload["fields"][key] = value
        return self.reader.domain.normalize_input(action, payload), related

    def _changes(self, values, before, scope):
        if self.kind == "op_type" and "category" in values and not supports_source(values["category"], scope["category"]):
            raise ValidationError("文件里的归属和这次导入选的归属不一样，这一行没有导入。请分开导入自制和外协工种。", field="category")
        # 状态在解码时已换成代号（页面叫法「在岗」「启用」也一样），和原值一样就是没改。
        changes = {key: value for key, value in values.items() if key in WRITABLE[self.kind]
                   and key != "business_code" and (before is None or not _same_column(key, value, before[key]))}
        if self._declares_empty_skills(values, before):
            changes["skill_codes"] = []
        return changes

    def _declares_empty_skills(self, values, before):
        # An exported provenance column keeps an unchanged empty skill list unchanged.
        # A bare writable [] remains an explicit request to declare no skills.
        return (self.kind == "operator" and before is not None and not before["skills_declared"]
                and values.get("skill_codes") == [] and "skills_declared" not in values)

    def _new_fields(self, changes, scope):
        if self.kind == "op_type":
            changes.setdefault("category", scope["category"])
        elif "status" not in changes:
            raise ValidationError("新增的记录必须填状态，这一行没有导入。请在" + _column(self.kind, "status") + "里填好状态。", field="status")

    def _clear_fields(self, changes):
        for key, value in changes.items():
            if value is None and key not in NULLABLE:
                raise ValidationError(_column(self.kind, key) + "不能用 \\N 清除，这一行没有导入。要移除全部工种请填清除。", field=key)
            if type(value) is str and not value.strip():
                raise ValidationError(_column(self.kind, key) + "只填了空格，这不算清除，这一行没有导入。要清除请填 \\N（大写），要留着原值请把格子空着。", field=key)

    def _relation(self, value, field, kind):
        multiple = field in MULTI_CODES
        if not multiple and value is None:
            return None, None
        refs, evidence = [], []
        for code in value if multiple else [value]:
            identity, raw = self._selected_code(code, kind, field)
            refs.append(identity.ref)
            evidence.append({"identity": asdict(identity), "record": raw})
        return (refs, evidence) if multiple else (refs[0], evidence[0])

    def _selected_code(self, code, kind, field):
        if type(code) is not str or not code or code != code.strip():
            raise ValidationError(_column(self.kind, field) + "要填准确的编号，不能填空格或名称，这一行没有导入。请改填编号。", field=field)
        identity = self.preparation.find_identity(kind, code)
        if identity is None:
            raise ValidationError(_column(self.kind, field) + "里的编号 " + code + " 在资料里找不到，这一行没有导入。请先在资料总览新增它，或者改填已有编号。", field=field)
        return identity, self.preparation.facts.raw_record(kind, identity.entity_key)


def proposed_fields(kind, code, before, payload, related):
    after = dict(before or {"business_code": code})
    after.update(payload["fields"])
    if "label" in payload:
        after["label"] = payload["label"]
    for field, facts in related.items():
        if type(facts) is list:
            after[field] = sorted(item["identity"]["entity_key"] for item in facts)
        else:
            after[field] = facts["identity"]["entity_key"] if facts else None
    if kind == "op_type" and not supports_source(after.get("category"), "external") and "default_merge_mode" not in payload["fields"]:
        after["default_merge_mode"] = None
    if before is not None:
        # Server-generated timestamp and changed relation provenance are not known until commit.
        after.pop("updated_at", None)
        if "skill_codes" in related:
            after["skills_declared"] = True
            after.pop("skill_details", None)
        if "status" in payload["fields"] and kind in ("operator", "supplier"):
            status = payload["fields"]["status"]
            after["inactive_reason"] = {"active": None, "inactive": "disabled"}.get(status, status)
    return after
