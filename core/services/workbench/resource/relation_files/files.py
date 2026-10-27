"""可操作设备关系的文件预检与确认。只做增量更新，文件里没有列出的关系一律不动。

主操连带是这里最容易写错的地方：把某台设备设为主操，底层会把同一个人其他设备的主操标记清掉。
所以预检阶段先按人算出"最终主操是哪一台"，每一行的结果都据此得出，确认阶段直接照这个结果写，
不依赖写入顺序，也不会出现"后一行把前一行刚设好的主操又翻回去"。
"""

from dataclasses import asdict
from typing import Any, Dict, List, Set, Tuple

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.operator_machine import OperatorMachine
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_relation_file import (
    EXPORT_LABELS,
    READONLY,
    REQUIRED,
    import_request,
    relation_kind,
    row_identity,
)
from core.models.workbench_resource_action import (
    ResourceActionPreview,
    action_row,
    check_resource_preview,
    reject_action_row,
    resource_page_scope,
    resource_refs,
)
from core.models.workbench_resource_file_source import PreparedImportSource
from core.models.workbench_resource_input import resource_text
from core.models.workbench_resource_table_query import table_query_required
from core.services.personnel.operator_machine_normalizers import (
    normalize_skill_level_stored,
    normalize_yes_no_stored,
)
from core.services.personnel.operator_machine_service import OperatorMachineService
from data.repositories.operator_machine_repo import OperatorMachineRepository
from data.repositories.workbench_resource_file_repo import WorkbenchResourceFileRepository

from ..queries import WorkbenchResourceQueryService
from .file_codec import read_relation_file
from .file_writer import check_capacity, write_relation_file

#: 导入只认导出写出的中文，反查同一张表。
_IMPORT_CODES = {key: {label: code for code, label in labels.items()} for key, labels in EXPORT_LABELS.items()}
_ENTITY_OF = {"operator_code": "operator", "machine_code": "machine"}


def _blocked(row) -> bool:
    """这一行是不是已经出错、不该再参与后续计算。

    预检行的初始状态就是 rejected（默认不放行），所以判据只能是错误列表，不能看 result。
    """
    return bool(row["errors"])


class WorkbenchRelationFileService:
    def __init__(self, conn, kind, logger=None, *, reader=None):
        self.conn, self.kind = conn, relation_kind(kind)
        self.repo = WorkbenchResourceFileRepository(conn, logger)
        self.links = OperatorMachineRepository(conn, logger)
        self.domain = OperatorMachineService(conn, logger)
        self.tx = TransactionManager(conn)
        self.reader = reader if reader is not None else WorkbenchResourceQueryService(conn, "operator", logger)

    # ---------- 导入 ----------

    def _prepare_source(self, content, *, file_format, mode):
        request = import_request(self.kind, content, file_format, mode)
        source, notices = read_relation_file(self.kind, content, file_format)
        prepared = PreparedImportSource.build(self.kind + ".import", request, source, notices, content=content)
        request["actual_source_ref"] = prepared.source_ref
        return prepared, request, source, notices

    def preview_import(self, content, *, file_format, mode="upsert"):
        prepared, request, source, notices = self._prepare_source(content, file_format=file_format, mode=mode)
        with self.tx.transaction():
            return self._prepare_import(prepared, request, source, notices)[0]

    def _prepare_import(self, prepared, request, source, notices):
        codes = {entity: {item["values"][field] for item in source
                          if type(item["values"].get(field)) is str} for field, entity in _ENTITY_OF.items()}
        preparation = self.reader.preparation(codes=codes)
        rows, primaries = self._build_rows(source, preparation)
        operators = sorted({row["values"]["operator_code"] for row in rows if not _blocked(row)})
        current_rows = [link for code in operators for link in preparation.authorizations("operator", code)]
        raw_links = {(link["operator_id"], link["machine_id"]): link for link in current_rows}
        targets = []
        for row in rows:
            if row["result"] not in ("new", "update"):
                continue
            after = row["after"]
            raw_link = raw_links.get((after["operator_code"], after["machine_code"]))
            skill_level = (
                raw_link["skill_level"]
                if raw_link is not None and "skill_level" not in row["changes"]
                else after["skill_level"]
            )
            is_primary = (
                raw_link["is_primary"]
                if raw_link is not None and "is_primary" not in row["changes"]
                else after["is_primary"]
            )
            targets.append(OperatorMachine(after["operator_code"], after["machine_code"], skill_level, is_primary))
        changes = self.domain.prepare_changes(current_rows, targets, primaries=primaries)
        return ResourceActionPreview.build(self.kind + ".import", request, rows, notices, source=prepared), changes

    def _build_rows(self, source, preparation) -> Tuple[List[Dict[str, Any]], Dict[str, Set[str]]]:
        rows = [self._parse_row(item) for item in source]
        self._reject_duplicate_pairs(rows)
        for row in rows:
            self._resolve_entities(row, preparation)
        current = self._load_current_links(rows, preparation)
        primaries = self._final_primaries(rows, current)
        replaced_by_operator = {
            operator: [
                code for code, value in sorted(links.items())
                if value["is_primary"] == "yes" and code not in primaries[operator]
            ]
            for operator, links in current.items()
        }
        for row in rows:
            self._classify(row, current, primaries, replaced_by_operator)
        return rows, primaries

    def _parse_row(self, source) -> Dict[str, Any]:
        row = action_row(source["row"])
        row["errors"] = list(source["errors"])
        row["notes"] = []
        values = source["values"]
        row["reference_fields"] = [key for key in READONLY[self.kind] if key in values]
        row["input"] = None
        parsed: Dict[str, Any] = {}
        for key in REQUIRED[self.kind]:
            try:
                raw = values.get(key)
                code = resource_text(raw, key)
                if raw != code:
                    raise ValidationError("编号不能有首尾空格，请修正后重新导入。", field=key)
                parsed[key] = code
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
                reject_action_row(row, "系统里找不到这个编号，这一行没有导入。请先在基础资料里维护好再导入。", field=key)
                return
            identity = preparation.identity_by_code(entity, code)
            expected[entity] = {"record": raw, "identity": asdict(identity)}
        row["expected"] = expected
        row["values"]["operator_label"] = expected["operator"]["record"]["name"]
        row["values"]["machine_label"] = expected["machine"]["record"]["name"]

    def _load_current_links(self, rows, preparation) -> Dict[str, Dict[str, Dict[str, str]]]:
        """一次取回涉及人员的全部现有关联；连带影响要看整组，不能只看文件里这几行。"""
        codes = sorted({row["values"]["operator_code"] for row in rows if not _blocked(row)})
        current: Dict[str, Dict[str, Dict[str, str]]] = {code: {} for code in codes}
        for code in codes:
            for link in preparation.authorizations("operator", code):
                current[code][link["machine_id"]] = {
                    "skill_level": normalize_skill_level_stored(link["skill_level"]),
                    "is_primary": normalize_yes_no_stored(link["is_primary"]),
                }
        return current

    def _final_primaries(self, rows, current) -> Dict[str, Set[str]]:
        """每个人确认后的主操设备。文件显式指定优先，其次保持原样，显式取消则变成没有主操。"""
        by_operator: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            if not _blocked(row):
                by_operator.setdefault(row["values"]["operator_code"], []).append(row)
        kept = {operator for operator, links in current.items()
                if self._unchanged_operator(links, by_operator[operator])}
        claimed = self._claimed_primaries(rows, kept)
        return {operator: self._primary_for(operator, links, by_operator[operator], claimed, operator in kept)
                for operator, links in current.items()}

    @staticmethod
    def _unchanged_operator(links, rows) -> bool:
        """文件里这个人的每一行都和现有关系一样：技能等级、主操标记要么没填，要么就是原值。"""
        for row in rows:
            before = links.get(row["values"]["machine_code"])
            if before is None or any(row["values"].get(key) not in (None, before[key]) for key in ("skill_level", "is_primary")):
                return False
        return True

    @staticmethod
    def _claimed_primaries(rows, kept) -> Dict[str, List[Dict[str, Any]]]:
        """把填了"是"的行按人归拢；同一个人占了多行就整组拒绝，不替用户挑一台。

        旧数据里一人本来就有多台主操、文件又原样导回（kept）时不拒绝：这些行确认时都不写，
        不会多出主操；只要这个人有一行真要改，仍按一人一台主操的规则拒绝。
        """
        claimed: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            if not _blocked(row) and row["values"].get("is_primary") == "yes":
                claimed.setdefault(row["values"]["operator_code"], []).append(row)
        for operator, items in claimed.items():
            if len(items) > 1 and operator not in kept:
                numbers = ", ".join(str(item["row"]) for item in items)
                for item in items:
                    reject_action_row(item, "同一个人最多只能有一台主操设备，这些行都没有导入：第 " + numbers
                                      + " 行。请只把其中一台填成是。", field="is_primary")
        return claimed

    @staticmethod
    def _primary_for(operator, links, rows, claimed, kept) -> Set[str]:
        existing = {code for code, value in links.items() if value["is_primary"] == "yes"}
        if kept:
            return existing  # 原样保留，旧数据多台也不动
        items = claimed.get(operator, [])
        if len(items) == 1:
            return {items[0]["values"]["machine_code"]}
        if len(items) > 1:
            return existing
        # 多行抢主操的那一组已经整批拒绝，主操保持原样；没人抢时只看原主操有没有被显式取消。
        dropped = {row["values"]["machine_code"] for row in rows
                   if not _blocked(row) and row["values"].get("is_primary") == "no"}
        return existing - dropped

    def _classify(self, row, current, primaries, replaced_by_operator) -> None:
        if _blocked(row):
            return
        operator = row["values"]["operator_code"]
        links = current[operator]
        before = links.get(row["values"]["machine_code"])
        row["after"] = row["input"] = self._after_values(row, before, primaries)
        row["action"] = "create" if before is None else "update"
        row["result"] = "new" if before is None else self._diff(row, before)
        row["reference_count"] = len(links)
        self._add_primary_notes(row, primaries[operator], replaced_by_operator[operator])

    @staticmethod
    def _after_values(row, before, primaries) -> Dict[str, Any]:
        machine = row["values"]["machine_code"]
        return {
            "operator_code": row["values"]["operator_code"],
            "machine_code": machine,
            "skill_level": row["values"].get("skill_level") or (before or {}).get("skill_level") or "normal",
            "is_primary": "yes" if machine in primaries[row["values"]["operator_code"]] else "no",
        }

    @staticmethod
    def _diff(row, before) -> str:
        after = row["after"]
        row["before"] = {"operator_code": after["operator_code"], "machine_code": after["machine_code"],
                         "skill_level": before["skill_level"], "is_primary": before["is_primary"]}
        row["changes"] = {key: {"before": row["before"][key], "after": after[key]}
                          for key in ("skill_level", "is_primary") if row["before"][key] != after[key]}
        return "update" if row["changes"] else "unchanged"

    @staticmethod
    def _add_primary_notes(row, primaries, replaced) -> None:
        """主操连带必须在预检就说清楚：会顶掉谁，以及没填的行为什么会变成非主操。

        不变的组确认时不写，也就顶不掉谁，不提示。
        """
        if row["values"].get("is_primary") == "yes":
            removed = [code for code in replaced if code != row["after"]["machine_code"]]
            if removed:
                row["notes"].append("确认后 " + "、".join(removed) + " 不再是这个人的主操设备。")
                row["requires_confirmation"] = True
        if (row["result"] == "update" and "is_primary" in row["changes"]
                and row["values"].get("is_primary") is None and primaries):
            row["notes"].append("这一行没有填主操设备，但同一份文件把主操给了别的设备，所以这里会变成非主操。")
            row["requires_confirmation"] = True

    def confirm_import(self, preview, content, *, file_format, mode="upsert"):
        if not self.conn.in_transaction:
            raise RuntimeError("关系导入确认必须在外层工作台写事务中执行。")
        try:
            prepared = PreparedImportSource.confirmation(preview, content)
            request = prepared.request_for(self.kind + ".import", file_format, mode)
            source, notices = prepared.parsed()
            current, changes = self._prepare_import(prepared, request, source, notices)
        except ValidationError as exc:
            raise WorkbenchCommandRejected(
                "stale_write", "文件或相关资料已经变了，没有导入。请点「重新预检」后再确认。") from exc
        body = check_resource_preview(preview, current)
        rows = body["rows"]
        self.domain.apply_changes(changes)
        results = [{"row": row["row"], "business_code": row["business_code"],
                    "result": "unchanged" if row["result"] == "unchanged" else "committed"} for row in rows]
        changed = any(item["result"] == "committed" for item in results)
        return WorkbenchCommandOutcome("committed" if changed else "unchanged",
                                       {"rows": results, "summary": body["summary"]})

    # ---------- 导出 ----------

    def preview_export(self, selection, *, scope, selected_refs=None):
        if not self.conn.in_transaction:
            raise RuntimeError("关系导出预览必须在已验证的查询快照事务中执行。")
        if selection not in ("all", "filtered", "selected") or (selection != "selected" and selected_refs is not None):
            raise WorkbenchCommandRejected(
                "invalid_input", "导出前要先选清楚是全部、当前筛选还是勾选的人员，没有开始下载。请重新选择导出范围。", 400)
        scope, query = resource_page_scope("operator", scope)
        if selection == "selected":
            refs = resource_refs(selected_refs, allow_empty=True)
            codes = [identity.entity_key for identity in self.reader.resolve_refs(refs)]
            return {"scope": scope, "selected_refs": refs}, len(self._links_for(codes))
        if selection == "all":
            all_scope = {"query": "", "status": None, "category": None, "sort": "business_code", "direction": "asc"}
            if scope != all_scope:
                effective, query = resource_page_scope("operator", {})
            else:
                effective = scope
        else:
            effective = scope
        codes = self._codes_for_scope(query)
        return {"scope": effective}, len(self._links_for(codes))

    def _codes_for_scope(self, query) -> List[str]:
        return self.reader.matching_keys(query) if table_query_required(query) else self.reader.toolbar_matching_keys(query)

    def _links_for(self, codes) -> List[Dict[str, Any]]:
        if not codes:
            return []
        if self.reader._snapshot_metrics is not None:
            grouped = self.reader._table_reader().grouped("authorizations", "operator_id")
            return [link for code in sorted({x for x in codes if x}) for link in grouped[code]]
        return self.links.list_simple_rows_for_operators(codes)

    def _rows_for(self, codes) -> List[Dict[str, Any]]:
        links = self._links_for(codes)
        if not links:
            return []
        rows = []
        for link in links:
            # 导出写中文：文件里的下拉和填写说明都是中文，格子里却留英文代号的话，
            # 用户点一下下拉就改了值，想照原样填回 normal 又会被数据校验拒掉。
            # 直接下标不兜底：normalize_*_stored 保证给的是规范值，取不到说明契约破了，
            # 应当当场暴露而不是悄悄写一个默认档位。
            rows.append({
                "operator_code": link["operator_id"],
                "machine_code": link["machine_id"],
                "skill_level": EXPORT_LABELS["skill_level"][normalize_skill_level_stored(link["skill_level"])],
                "is_primary": EXPORT_LABELS["is_primary"][normalize_yes_no_stored(link["is_primary"])],
            })
        if self.reader._snapshot_metrics is not None:
            metrics = self.reader._table_reader().metrics
            operators = metrics.kind_records("operator")
            machines = metrics.kind_records("machine")
        else:
            operators = self.repo.raw_many("operator", (row["operator_code"] for row in rows))
            machines = self.repo.raw_many("machine", (row["machine_code"] for row in rows))
        for row in rows:
            operator = operators.get(row["operator_code"])
            machine = machines.get(row["machine_code"])
            row["operator_label"] = operator["name"] if operator is not None else None
            row["machine_label"] = machine["name"] if machine is not None else None
        return rows

    def export_rows(self, file_format, *, scope, selected_refs=None):
        """在已验证的读快照里读完整份导出行；编码文件交给 write_export，在读事务结束后做。"""
        if not self.conn.in_transaction:
            raise RuntimeError("关系导出必须在已验证的查询快照事务中执行。")
        _, query = resource_page_scope("operator", scope)
        if selected_refs is None:
            codes = self._codes_for_scope(query)
        else:
            codes = [identity.entity_key for identity in self.reader.resolve_refs(resource_refs(selected_refs, allow_empty=True))]
        rows = self._rows_for(codes)
        check_capacity(len(rows), file_format)
        return rows

    def write_export(self, rows, file_format):
        """只用 export_rows 读出的行生成 CSV/XLSX，不再查库，可在读事务之外调用。"""
        return write_relation_file(self.kind, rows, file_format)

    @staticmethod
    def template(kind, file_format="xlsx"):
        return write_relation_file(relation_kind(kind), [], file_format, template=True)
