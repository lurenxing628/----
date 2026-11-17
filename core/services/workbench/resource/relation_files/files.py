"""可操作设备关系的文件预检与确认。只做增量更新，文件里没有列出的关系一律不动。

技能等级和主操设备都是每一行关联自己的属性：填了用文件值，留空保持原值，新增按普通、非主操。
一个人可以有多台主操设备，改一行不牵动同一个人的其他设备。
"""

from dataclasses import asdict
from typing import Any, Dict, List, Tuple

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.enums import SkillLevel, YesNo
from core.models.operator_machine import OperatorMachine
from core.models.workbench_action_values import AtomicActionPreview
from core.models.workbench_command import WorkbenchCommandOutcome
from core.models.workbench_relation_file import (
    EXPORT_LABELS,
    READONLY,
    REQUIRED,
    row_identity,
)
from core.models.workbench_resource_action import (
    action_row,
    reject_action_row,
    resource_refs,
)
from core.models.workbench_resource_file_source import PreparedImportSource
from core.models.workbench_resource_input import resource_text
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.personnel.operator_machine_service import OperatorMachineService
from data.repositories.operator_machine_repo import OperatorMachineRepository
from data.repositories.workbench_resource_file_repo import WorkbenchResourceFileRepository

from ..queries import WorkbenchResourceQueryService
from ..scope import ResourceFactScope
from .file_codec import read_relation_file

#: 导入只认导出写出的中文，反查同一张表。
_IMPORT_CODES = {key: {label: code for code, label in labels.items()} for key, labels in EXPORT_LABELS.items()}
_ENTITY_OF = {"operator_code": "operator", "machine_code": "machine"}
#: 新增关联时没填的列取这里的值。
_NEW_LINK = {"skill_level": SkillLevel.NORMAL.value, "is_primary": YesNo.NO.value}


def _blocked(row) -> bool:
    """这一行是不是已经出错、不该再参与后续计算。

    预检行的初始状态就是 rejected（默认不放行），所以判据只能是错误列表，不能看 result。
    """
    return bool(row["errors"])


class WorkbenchRelationFileService:
    def __init__(self, conn, kind, logger=None, *, reader=None):
        self.conn, self.kind = conn, kind
        self.repo = WorkbenchResourceFileRepository(conn, logger)
        self.links = OperatorMachineRepository(conn, logger)
        self.domain = OperatorMachineService(conn, logger)
        self.tx = TransactionManager(conn)
        self.reader = reader if reader is not None else WorkbenchResourceQueryService(conn, "operator", logger)

    # ---------- 导入 ----------

    def _prepare_source(self, content, *, file_format, mode):
        request = {"format": file_format, "mode": mode, "scope": {}}
        source, notices = read_relation_file(self.kind, content, file_format)
        return PreparedImportSource.build(request, source, notices)

    def preview_import(self, content, *, file_format, mode):
        prepared = self._prepare_source(content, file_format=file_format, mode=mode)
        with self.tx.transaction():
            return self._prepare_import(prepared)[0]

    def _prepare_import(self, prepared):
        request = prepared.request()
        source, notices = prepared.parsed()
        codes = {entity: {item["values"][field] for item in source
                          if type(item["values"].get(field)) is str} for field, entity in _ENTITY_OF.items()}
        preparation = self.reader.preparation(codes=codes)
        rows = self._build_rows(source, preparation)
        operators = sorted({row["values"]["operator_code"] for row in rows if not _blocked(row)})
        current_rows = [link for code in operators for link in preparation.authorizations("operator", code)]
        targets = [OperatorMachine(row["after"]["operator_code"], row["after"]["machine_code"],
                                   row["after"]["skill_level"], row["after"]["is_primary"])
                   for row in rows if row["result"] in ("new", "update")]
        changes = self.domain.prepare_changes(current_rows, targets)
        return AtomicActionPreview.build(self.kind + ".import", request, rows, notices, source=prepared), changes

    def _build_rows(self, source, preparation) -> List[Dict[str, Any]]:
        rows = [self._parse_row(item) for item in source]
        self._reject_duplicate_pairs(rows)
        for row in rows:
            self._resolve_entities(row, preparation)
        current = self._load_current_links(rows, preparation)
        for row in rows:
            self._classify(row, current)
        return rows

    def _parse_row(self, source) -> Dict[str, Any]:
        row = action_row(source["row"])
        row["errors"] = list(source["errors"])
        values = source["values"]
        row["reference_fields"] = [key for key in READONLY[self.kind] if key in values]
        parsed: Dict[str, Any] = {}
        for key in REQUIRED[self.kind]:
            try:
                raw = values.get(key)
                resource_text(raw, key)
                parsed[key] = raw
            except ValidationError as exc:
                reject_action_row(row, exc.message, field=exc.field or key)
        # 文件里只有填了 \N 才会带上值为 None 的列；这两列在库里不能为空，留空才表示保持原样。
        for key, label in (("skill_level", "技能等级"), ("is_primary", "主操设备")):
            if key not in values:
                continue
            if values[key] is None:
                reject_action_row(row, label + "不能为空，不能用 \\N 清除；留空表示保持原样。", field=key)
            elif values[key] not in _IMPORT_CODES[key]:
                reject_action_row(row, "“" + label + "”只能填：" + " / ".join(EXPORT_LABELS[key].values()) + "。", field=key)
            else:
                parsed[key] = _IMPORT_CODES[key][values[key]]
        row["business_code"] = row_identity(parsed)
        row["values"] = parsed
        return row

    def _reject_duplicate_pairs(self, rows) -> None:
        seen: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for row in rows:
            values = row["values"]
            if "operator_code" in values and "machine_code" in values:
                pair = (values["operator_code"], values["machine_code"])
                seen.setdefault(pair, []).append(row)
        for repeated in seen.values():
            if len(repeated) > 1:
                numbers = ", ".join(str(item["row"]) for item in repeated)
                for item in repeated:
                    reject_action_row(item, "文件里有重复的工号和设备编号组合，这些行都没有导入：第 " + numbers
                                      + " 行。请去掉重复项后重新上传。", field="machine_code", code="duplicate_entry")

    def _resolve_entities(self, row, preparation) -> None:
        if _blocked(row):
            return
        expected = {}
        for key, entity in _ENTITY_OF.items():
            code = row["values"][key]
            raw = preparation.raw(entity, code)
            if raw is None:
                message = (
                    "编号不能有首尾空格，请修正后重新导入。"
                    if code != code.strip()
                    else "系统里找不到这个编号，这一行没有导入。请先在基础资料里维护好再导入。"
                )
                reject_action_row(row, message, field=key)
                return
            identity = preparation.identity_by_code(entity, code)
            expected[entity] = {"record": raw, "identity": asdict(identity)}
        row["expected"] = expected
        row["values"]["operator_label"] = expected["operator"]["record"]["name"]
        row["values"]["machine_label"] = expected["machine"]["record"]["name"]

    def _load_current_links(self, rows, preparation) -> Dict[str, Dict[str, Dict[str, str]]]:
        """一次取回涉及人员的全部现有关联；关联数按人统计，不只看文件里这几行。"""
        codes = sorted({row["values"]["operator_code"] for row in rows if not _blocked(row)})
        current: Dict[str, Dict[str, Dict[str, str]]] = {code: {} for code in codes}
        for code in codes:
            for link in preparation.authorizations("operator", code):
                current[code][link["machine_id"]] = {"skill_level": link["skill_level"], "is_primary": link["is_primary"]}
        return current

    def _classify(self, row, current) -> None:
        if _blocked(row):
            return
        links = current[row["values"]["operator_code"]]
        before = links.get(row["values"]["machine_code"])
        row["after"] = row["input"] = self._after_values(row, before)
        row["action"] = "create" if before is None else "update"
        row["result"] = "new" if before is None else self._diff(row, before)
        row["reference_count"] = len(links)

    @staticmethod
    def _after_values(row, before) -> Dict[str, Any]:
        """填了的列用文件值，留空的列保持原值；新增关联留空按普通、非主操。"""
        values, kept = row["values"], before or _NEW_LINK
        return {
            "operator_code": values["operator_code"],
            "machine_code": values["machine_code"],
            "skill_level": values.get("skill_level", kept["skill_level"]),
            "is_primary": values.get("is_primary", kept["is_primary"]),
        }

    @staticmethod
    def _diff(row, before) -> str:
        after = row["after"]
        row["before"] = {"operator_code": after["operator_code"], "machine_code": after["machine_code"],
                         "skill_level": before["skill_level"], "is_primary": before["is_primary"]}
        row["changes"] = {key: {"before": row["before"][key], "after": after[key]}
                          for key in ("skill_level", "is_primary") if row["before"][key] != after[key]}
        return "update" if row["changes"] else "unchanged"

    def confirm_import(self, preview):
        if not self.conn.in_transaction:
            raise RuntimeError("关系导入确认必须在外层工作台写事务中执行。")
        current, changes = self._prepare_import(preview.source)
        body = preview.check_current(current)
        rows = body["rows"]
        self.domain.apply_changes(changes)
        results = [{"row": row["row"], "business_code": row["business_code"],
                    "result": "unchanged" if row["result"] == "unchanged" else "committed"} for row in rows]
        changed = any(item["result"] == "committed" for item in results)
        return WorkbenchCommandOutcome("committed" if changed else "unchanged",
                                       {"rows": results, "summary": body["summary"]})

    # ---------- 导出 ----------

    def preview_export(self, scope: ResourceFactScope, selection, *, request, selected_refs=None):
        """Export arguments holding the validated operator request (and any explicit refs), with their row count."""
        if not self.conn.in_transaction:
            raise RuntimeError("关系导出预览必须在已验证的查询快照事务中执行。")
        if selection == "selected":
            refs = resource_refs(selected_refs, allow_empty=True)
            codes = [identity.entity_key for identity in self.reader.resolve_refs(refs)]
            return {"request": request, "selected_refs": refs}, len(self._links_for(scope, codes))
        effective = ResourcePageRequest(kind="operator") if selection == "all" else request
        return {"request": effective}, len(self._links_for(scope, scope.matching_keys(effective)))

    def _links_for(self, scope: ResourceFactScope, codes) -> List[Dict[str, Any]]:
        if not codes:
            return []
        if scope.table_facts_instance is not None:
            grouped = scope.table_facts_instance.grouped("authorizations", "operator_id")
            return [link for code in sorted(set(codes)) for link in grouped[code]]
        return self.links.list_simple_rows_for_operators(codes)

    def _rows_for(self, scope: ResourceFactScope, codes) -> List[Dict[str, Any]]:
        links = self._links_for(scope, codes)
        if not links:
            return []
        rows = []
        for link in links:
            # 导出写中文：文件里的下拉和填写说明都是中文，格子里却留英文代号的话，
            # 用户点一下下拉就改了值，想照原样填回 normal 又会被数据校验拒掉。
            # 库里两列只存规范代号（值域约束），直接下标。
            rows.append({
                "operator_code": link["operator_id"],
                "machine_code": link["machine_id"],
                "skill_level": EXPORT_LABELS["skill_level"][link["skill_level"]],
                "is_primary": EXPORT_LABELS["is_primary"][link["is_primary"]],
            })
        if scope.table_facts_instance is not None:
            metrics = scope.table_facts_instance.metrics
            operators = metrics.kind_records("operator")
            machines = metrics.kind_records("machine")
        else:
            operators = self.repo.raw_many("operator", [row["operator_code"] for row in rows])
            machines = self.repo.raw_many("machine", [row["machine_code"] for row in rows])
        for row in rows:
            operator = operators.get(row["operator_code"])
            machine = machines.get(row["machine_code"])
            row["operator_label"] = operator["name"] if operator is not None else None
            row["machine_label"] = machine["name"] if machine is not None else None
        return rows

    def export_rows(self, scope: ResourceFactScope, *, request, selected_refs=None):
        """在已验证的读快照里读完整份导出行；编码文件交给 write_relation_file，在读事务结束后做。"""
        if not self.conn.in_transaction:
            raise RuntimeError("关系导出必须在已验证的查询快照事务中执行。")
        if selected_refs is None:
            codes = scope.matching_keys(request)
        else:
            codes = [identity.entity_key for identity in self.reader.resolve_refs(selected_refs)]
        return self._rows_for(scope, codes)
