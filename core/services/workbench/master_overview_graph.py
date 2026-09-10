"""Public graph primitives; SQL keys stay inside the graph's private index."""

import hashlib
import json
import math

from .master_overview_facts import plain

KINDS = {"part": "part", "route": "part", "opType": "op_type", "equipment": "machine",
         "personnel": "operator", "material": "material", "supplier": "supplier", "calendar": "calendar"}


def text(value):
    value = plain(value)
    if value is None:
        return "未填"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def number(value, positive=False):
    return type(value) in (int, float) and math.isfinite(value) and (value > 0 if positive else value >= 0)


class MasterOverviewGraph:
    def __init__(self, facts):
        self.facts = facts
        self.entities, self.by_key, self.edges = [], {}, set()
        self._issue_index, self._link_keys = {}, set()

    def add(self, domain, key, code, label, *, category=None):
        ref = self.facts.ref(KINDS[domain], key)
        context = {"source": "production", "kind": KINDS[domain], "entity_ref": ref}
        if category in ("internal", "external"):
            context["category"] = category
        if domain == "calendar":
            context = {"source": "production", "kind": "calendar", "month": text(code)[:7], "date": text(code)}
        entity = {"key": domain + ":" + ref, "ref": ref, "domain": domain, "business_code": text(code),
                  "label": "" if label is None else text(label), "fields": [], "issues": [], "relations": [],
                  "checks_complete": True, "relations_complete": True, "inactive": False,
                  "target": {"view": "process", "context": context}}
        self.entities.append(entity)
        self.by_key[(domain, key)] = entity
        return entity

    def field(self, entity, label, value, source, *, valid=None, required=True):
        filled = value is not None and value != ""
        state = "known" if filled else "missing"
        if valid is False and filled:
            state = "invalid"
        entity["fields"].append({"label": label, "value": plain(value), "source": source, "state": state,
                                  "checked": required, "filled": filled and valid is not False})

    def issue(self, entity, rule, title, evidence, *, action="核对原始资料", stage=None, operation_ref=None, group_ref=None, related_ref=None):
        context = dict(entity["target"]["context"])
        if stage:
            context["stage"] = stage
        if operation_ref:
            context["template_operation_ref"] = operation_ref
        if group_ref:
            context["template_external_group_ref"] = group_ref
        signature = "|".join((entity["key"], rule, operation_ref or "", group_ref or "", related_ref or ""))
        ref = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:48]
        existing = self._issue_index.get(ref)
        if existing is not None:
            return existing
        item = {"key": "issue:" + ref, "issue_ref": ref, "entity_ref": entity["ref"], "domain": entity["domain"],
                "business_code": entity["business_code"], "label": entity["label"], "rule": rule,
                "title": title, "evidence": evidence, "action": action, "status": "attention",
                "target": {"view": "process", "context": context}}
        entity["issues"].append(item)
        self._issue_index[ref] = item
        return item

    def unknown(self, entity, label, source, *, relation=False):
        entity["checks_complete"] = False
        if relation:
            entity["relations_complete"] = False
        entity["fields"].append({"label": label, "value": None, "source": source, "state": "unknown", "checked": False, "filled": False})

    def link(self, entity, other, label, source, reverse=None):
        if entity is None or other is None or entity["key"] == other["key"]:
            return
        marker = (entity["key"], other["key"], label)
        if marker in self._link_keys:
            return
        self._link_keys.add(marker)
        self.edges.add(tuple(sorted((entity["key"], other["key"]))))
        entity["relations"].append({"key": other["key"], "ref": other["ref"], "domain": other["domain"],
                                    "business_code": other["business_code"], "label": other["label"],
                                    "relation": label, "source": source, "target": other["target"]})
        if reverse:
            self.link(other, entity, reverse, source)

    def related(self, entity, domain, key, label, source, reverse, *, required=False, operation_ref=None, stage=None):
        if key is None or key == "":
            if required:
                self.issue(entity, source + ".unbound", label + "未绑定", "原记录为空；未按名称猜测关系。", operation_ref=operation_ref, stage=stage)
            return None
        target = self.by_key.get((domain, key))
        if target is None:
            from .master_overview_facts import SOURCES

            if not self.facts.available(*SOURCES[domain]):
                self.unknown(entity, label, source, relation=True)
            else:
                self.issue(entity, source + ".missing", label + "指向缺失记录", "关系来源：" + source + "；关联对象不存在，未按同号或同名替代。", operation_ref=operation_ref, stage=stage)
                entity["relations_complete"] = False
            return None
        self.link(entity, target, label, source, reverse)
        return target

    def finalize(self):
        for entity in self.entities:
            if entity["target"].get("unavailable_reason"):
                for item in entity["issues"]:
                    item["target"]["unavailable_reason"] = entity["target"]["unavailable_reason"]
            checks = [row for row in entity["fields"] if row["checked"]]
            entity.update(filled_fields=sum(row["filled"] for row in checks), checked_fields=len(checks),
                          issue_count=len(entity["issues"]), known_relation_count=len(entity["relations"]),
                          relation_count=len(entity["relations"]) if entity["relations_complete"] else None)
            entity["status"] = "inactive" if entity.pop("inactive") else "attention" if entity["issues"] else "checked" if entity["checks_complete"] else "unknown"
            entity["summary"] = (entity["issues"][0]["title"] + (" 等{}项".format(len(entity["issues"])) if len(entity["issues"]) > 1 else "")) if entity["issues"] else "已检查字段未发现待维护项" if entity["checks_complete"] else "部分来源或检查无法核实"
        return self.entities
