"""Eight-domain graph, table queries, exact lookup and complete CSV projection."""

import csv
import io
from contextlib import contextmanager

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_master_overview import DOMAINS, STATUS, MasterOverviewScope, public_ref

from .master_overview_calendar import add_calendar
from .master_overview_facts import SOURCES, MasterOverviewFacts
from .master_overview_graph import MasterOverviewGraph, text
from .master_overview_process import add_process
from .master_overview_relations import batch_relations, resource_profile_fields
from .master_overview_resources import add_resources, resource_links

LABELS = dict(DOMAINS)
BASIS = "基础资料与关联检查"


def cell(row, column):
    value = row.get(column)
    if column == "domain":
        return LABELS.get(value, "暂无数据")
    if column == "status":
        return STATUS.get(value, "暂无数据")
    return "暂无数据" if value is None else text(value)


def brief(entity):
    return {key: value for key, value in entity.items() if key not in ("fields", "relations", "issues")}


class MasterOverviewService:
    def __init__(self, conn):
        self.facts = MasterOverviewFacts(conn)
        self.graph = None
        self.entities, self.issues = [], []

    @contextmanager
    def read_snapshot(self):
        with self.facts.read_snapshot() as fingerprint:
            self.graph = MasterOverviewGraph(self.facts)
            add_resources(self.graph)
            add_process(self.graph)
            add_calendar(self.graph)
            resource_links(self.graph)
            resource_profile_fields(self.graph)
            batch_relations(self.graph)
            self.entities = self.graph.finalize()
            self.issues = [{**issue, "issue_count": entity["issue_count"], "relation_count": entity["relation_count"]}
                           for entity in self.entities for issue in entity["issues"]]
            yield fingerprint

    def overview(self):
        if self.graph is None:
            raise RuntimeError("Master overview requires an explicit read snapshot.")
        domains = []
        for domain, label in DOMAINS:
            rows = [entity for entity in self.entities if entity["domain"] == domain]
            loaded = self.facts.available(*SOURCES[domain], "WorkbenchEntityRefs")
            domains.append({"id": domain, "label": label, "loaded": loaded, "count": len(rows) if loaded else None,
                            "attention": sum(bool(row["issue_count"]) for row in rows) if loaded else None,
                            "unknown": sum(not row["checks_complete"] for row in rows) if loaded else None})
        complete = all(row["loaded"] for row in domains)
        relation_complete = complete and all(row["relations_complete"] for row in self.entities)
        return {"domains": domains, "complete": complete, "basis": BASIS, "gaps": self.facts.gaps,
                "stats": {"entities": len(self.entities), "issues": len(self.issues),
                          "affected": sum(bool(row["issue_count"]) for row in self.entities),
                          "relations": len(self.graph.edges) if relation_complete else None,
                          "known_relation_pairs": len(self.graph.edges)}}

    def matched(self, scope):
        rows = self.issues if scope.view == "issues" else self.entities
        needle = scope.query.casefold()
        def match(row):
            if scope.domain != "all" and row["domain"] != scope.domain:
                return False
            if scope.status != "all" and not (row["issue_count"] > 0 if scope.status == "attention" else row["status"] == scope.status):
                return False
            if any(value.casefold() not in cell(row, key).casefold() for key, value in scope.column_filters.items()):
                return False
            searchable = [row.get(key) for key in ("business_code", "label", "title", "evidence", "summary", "rule")]
            searchable.extend(field["value"] for field in row.get("fields", []))
            return not needle or any(needle in text(value).casefold() for value in searchable if value is not None)
        matched = [row for row in rows if match(row)]
        matched.sort(key=lambda row: (row["business_code"], row["key"]))
        known = [row for row in matched if row.get(scope.sort) is not None]
        unknown = [row for row in matched if row.get(scope.sort) is None]
        known.sort(key=lambda row: row[scope.sort], reverse=scope.direction == "desc")
        return known + unknown

    def page(self, scope, number=1):
        rows = self.matched(scope)
        pages = max(1, (len(rows) + scope.size - 1) // scope.size)
        if number > pages:
            raise WorkbenchCommandRejected("snapshot_stale", "翻页位置已失效，请回到第 1 页重新查询。")
        start = (number - 1) * scope.size
        return {"rows": [brief(row) for row in rows[start:start + scope.size]], "scope": scope.values(), "overview": self.overview(),
                "page": {"number": number, "size": scope.size, "total": len(rows), "pages": pages}}

    def resolve(self, domain, ref):
        if domain not in LABELS or not public_ref(ref):
            raise WorkbenchCommandRejected("entity_not_found", "这条记录已失效，请重新选择。", 404)
        entity = next((row for row in self.entities if row["domain"] == domain and row["ref"] == ref), None)
        if entity is None:
            raise WorkbenchCommandRejected("entity_not_found", "这条资料已经不在了，或者来源还没读取。请刷新后重新选择。", 404)
        return entity

    def detail(self, scope, domain, ref, section, page):
        entity = self.resolve(domain, ref)
        if not any(row["domain"] == domain and (row.get("entity_ref") or row.get("ref")) == ref for row in self.matched(scope)):
            raise WorkbenchCommandRejected("scope_mismatch", "这条资料不在当前筛选范围里。请先清除筛选，或者从相关项里点进去。", 409)
        rows = entity[section]
        pages = max(1, (len(rows) + 9) // 10)
        if page > pages:
            raise WorkbenchCommandRejected("snapshot_stale", "翻页位置已失效，请回到第 1 页重新查询。")
        return {"entity": brief(entity), "scope": scope.values(), "section": section, "rows": rows[(page - 1) * 10:page * 10],
                "counts": {name: len(entity[name]) for name in ("issues", "relations", "fields")},
                "page": {"number": page, "size": 10, "total": len(rows), "pages": pages}}

    def locate(self, old_scope, domain, ref):
        entity = self.resolve(domain, ref)
        scope = MasterOverviewScope(view="entities", domain=domain, sort="business_code", direction="asc", size=old_scope.size)
        rows = self.matched(scope)
        number = next(index for index, row in enumerate(rows) if row["ref"] == ref) // scope.size + 1
        result = self.page(scope, number)
        result["selected"] = {"domain": domain, "entity_ref": entity["ref"]}
        return scope, result

    def csv(self, scope):
        rows = self.matched(scope)
        columns = (("domain", "资料类别"), ("business_code", "编号"), ("label", "名称"))
        columns += (("title", "待维护项"), ("evidence", "当前记录"), ("action", "维护建议"), ("rule", "检查规则编号")) if scope.view == "issues" else (
            ("status", "检查状态"), ("filled_fields", "已填项"), ("checked_fields", "检查项"),
            ("relation_count", "关联项"), ("issue_count", "待维护项"), ("summary", "检查结果"))
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\r\n", quoting=csv.QUOTE_ALL)
        writer.writerow([label for _, label in columns])
        for row in rows:
            writer.writerow([_csv_cell(cell(row, key)) for key, _ in columns])
        return ("\ufeff" + output.getvalue()).encode("utf-8"), len(rows)


def _csv_cell(value):
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value
