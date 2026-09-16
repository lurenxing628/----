"""Sparse file values to existing domain DTOs, with explicit code resolution."""

import math
from dataclasses import asdict

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_resource_file import (
    LABELS,
    MULTI_CODES,
    NULLABLE,
    NUMERIC_FIELDS,
    RELATIONS,
    WRITABLE,
)
from core.services.workbench.resource_states import WorkbenchResourceStateService


def _column(field):
    """提示里按“列 英文名（中文说明）”称呼文件里的列，英文名是文件格式的一部分，必须留。"""
    label = LABELS.get(field)
    return "列 " + field + "（" + label + "）" if label else "列 " + field


def same_value(left, right, field):
    if field in NUMERIC_FIELDS and type(left) in (int, float) and type(right) in (int, float):
        return math.isfinite(left) and math.isfinite(right) and left == right
    return canonical_json(left) == canonical_json(right)


def _same_column(field, value, previous):
    if field in MULTI_CODES and type(value) is list and type(previous) is list:
        return sorted(value) == sorted(previous)
    return same_value(value, previous, field)


class ResourceFileInput:
    def __init__(self, reader, repo):
        self.reader, self.repo, self.kind = reader, repo, reader.kind
        self.state = WorkbenchResourceStateService(reader.conn)

    def normalize(self, action, code, values, before, scope):
        changes = self._changes(values, before, scope)
        self._clear_fields(changes)
        payload, related = {"fields": {}}, {}
        if action == "create":
            payload["business_code"] = code
            self._new_fields(changes, scope)
        for key, value in changes.items():
            if key == "label":
                payload["label"] = value
            elif key in RELATIONS[self.kind]:
                target, target_kind, category = RELATIONS[self.kind][key]
                selected, evidence = self._relation(value, key, target_kind, category)
                payload.setdefault("relationships", {})[target] = selected
                related[key] = evidence
            else:
                payload["fields"][key] = value
        normalized = self.reader.domain.normalize_input(action, payload)
        self._unique_name(code, normalized)
        self._policy(normalized, scope)
        return normalized, related

    def _changes(self, values, before, scope):
        if self.kind == "op_type" and "category" in values and values["category"] != scope["category"]:
            raise ValidationError("文件里的归属和这次导入选的归属不一样，这一行没有导入。请分开导入自制和外协工种。", field="category")
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
            changes["category"] = scope["category"]
        elif "status" not in changes:
            raise ValidationError("新增的记录必须填状态，这一行没有导入。请在" + _column("status") + "里填好状态。", field="status")

    def _clear_fields(self, changes):
        for key, value in changes.items():
            if value is None and key not in NULLABLE:
                raise ValidationError(_column(key) + "不能用 \\N 清除，这一行没有导入。要改成一组空编号请填 []。", field=key)
            if type(value) is str and not value.strip():
                raise ValidationError(_column(key) + "只填了空格，这不算清除，这一行没有导入。要清除请填 \\N（大写），要留着原值请把格子空着。", field=key)

    def _relation(self, value, field, kind, category):
        multiple = field in MULTI_CODES
        if multiple and (type(value) is not list or any(type(code) is not str for code in value)):
            raise ValidationError(_column(field) + "要填一组用引号括起来的编号，这一行没有导入。请按 [\"A\",\"B\"] 这样填。", field=field)
        if multiple and len(value) != len(set(value)):
            raise ValidationError(_column(field) + "里的编号有重复，这一行没有导入。请去掉重复的编号。", field=field)
        if not multiple and value is None:
            return None, None
        refs, evidence = [], []
        for code in value if multiple else [value]:
            identity, raw = self._selected_code(code, kind, category, field)
            refs.append(identity.ref)
            evidence.append({"identity": asdict(identity), "record": raw})
        return (refs, evidence) if multiple else (refs[0], evidence[0])

    def _selected_code(self, code, kind, category, field):
        if type(code) is not str or not code or code != code.strip():
            raise ValidationError(_column(field) + "要填准确的编号，不能填空格或名称，这一行没有导入。请改填编号。", field=field)
        identity = self.reader.identities.find_active(kind, code)
        if identity is None:
            raise ValidationError(_column(field) + "里的编号 " + code + " 在资料里找不到，这一行没有导入。请先在资料总览新增它，或者改填已有编号。", field=field)
        self.state.selected(kind, identity.ref, category=category)
        return identity, self.repo.raw(kind, code)

    def _unique_name(self, code, payload):
        if self.kind == "op_type" and "label" in payload:
            owner = self.repo.name_owner(self.kind, payload["label"])
            if owner and owner["business_code"] != code:
                raise ValidationError("这个工种名称已经被另一个编号用了，这一行没有导入。请换一个名称。", field="label")

    @staticmethod
    def _policy(payload, scope):
        mode = payload["fields"].get("default_merge_mode")
        if mode is not None and scope["category"] != "external":
            raise WorkbenchCommandRejected("constraint_conflict", "自制工种不能设置外协周期规则，没有导入。请把归属改成外协，或者清掉" + _column("default_merge_mode") + "。")


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
    if before is not None:
        # Server-generated timestamp and changed relation provenance are not known until commit.
        after.pop("updated_at", None)
        if "skill_codes" in related:
            after["skills_declared"] = True
            after.pop("skill_details", None)
        if "op_type_codes" in related:
            after.pop("legacy_op_type_code", None)
            after.pop("explicit_op_type_codes", None)
        if "status" in payload["fields"]:
            status = payload["fields"]["status"]
            if kind in ("operator", "supplier"):
                after["legacy_status"] = "active" if status == "active" else "inactive"
                after["inactive_reason"] = {"active": None, "inactive": "disabled"}.get(status, status)
            else:
                after["legacy_status"] = status
    return after
