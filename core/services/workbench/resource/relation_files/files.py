"""可操作设备关系的文件预检与确认。只做增量更新，文件里没有列出的关系一律不动。

主操连带是这里最容易写错的地方：把某台设备设为主操，底层会把同一个人其他设备的主操标记清掉。
所以预检阶段先按人算出"最终主操是哪一台"，每一行的结果都据此得出，确认阶段直接照这个结果写，
不依赖写入顺序，也不会出现"后一行把前一行刚设好的主操又翻回去"。
"""

from typing import Any, Dict, List, Optional, Set

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
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
    resource_refs,
    resource_scope,
)
from core.models.workbench_resource_input import resource_text
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.personnel.operator_machine_normalizers import (
    normalize_skill_level_optional,
    normalize_skill_level_stored,
    normalize_yes_no_optional,
    normalize_yes_no_stored,
)
from core.services.personnel.operator_machine_service import OperatorMachineService
from data.repositories.operator_machine_repo import OperatorMachineRepository
from data.repositories.workbench_resource_file_repo import WorkbenchResourceFileRepository

from ..queries import WorkbenchResourceQueryService
from .file_codec import read_relation_file
from .file_writer import check_capacity, write_relation_file

_ENTITY_OF = {"operator_code": "operator", "machine_code": "machine"}


def _blocked(row) -> bool:
    """这一行是不是已经出错、不该再参与后续计算。

    预检行的初始状态就是 rejected（默认不放行），所以判据只能是错误列表，不能看 result。
    """
    return bool(row["errors"])


class WorkbenchRelationFileService:
    def __init__(self, conn, kind, logger=None):
        self.conn, self.kind = conn, relation_kind(kind)
        self.logger = logger
        self.repo = WorkbenchResourceFileRepository(conn, logger)
        self.links = OperatorMachineRepository(conn, logger)
        self.domain = OperatorMachineService(conn, logger)
        self.tx = TransactionManager(conn)

    # ---------- 导入 ----------

    def preview_import(self, content, *, file_format, mode="upsert"):
        request = import_request(self.kind, content, file_format, mode)
        source, notices = read_relation_file(self.kind, content, file_format)
        with self.tx.transaction():
            return ResourceActionPreview.build(self.kind + ".import", request, self._build_rows(source), notices)

    def _build_rows(self, source) -> List[Dict[str, Any]]:
        rows = [self._parse_row(item) for item in source]
        self._reject_duplicate_pairs(rows)
        entities = self._load_entities(rows)
        for row in rows:
            self._resolve_entities(row, entities)
        current = self._load_current_links(rows)
        primaries = self._final_primaries(rows, current)
        for row in rows:
            self._classify(row, current, primaries)
        return rows

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
                if code is None:
                    raise ValidationError("这一项必须填写。", field=key)
                if raw != code:
                    raise ValidationError("编号不能有首尾空格，请修正后重新导入。", field=key)
                parsed[key] = code
            except ValidationError as exc:
                reject_action_row(row, exc.message, field=exc.field or key)
        try:
            if "skill_level" in values:
                parsed["skill_level"] = normalize_skill_level_optional(values["skill_level"])
            if "is_primary" in values:
                parsed["is_primary"] = normalize_yes_no_optional(values["is_primary"], "is_primary")
        except ValidationError as exc:
            reject_action_row(row, exc.message, field="skill_level" if "技能" in exc.message else "is_primary")
        row["business_code"] = row_identity(parsed)
        row["values"] = parsed
        return row

    def _reject_duplicate_pairs(self, rows) -> None:
        seen: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            code = row["business_code"]
            if code is not None:
                seen.setdefault(code, []).append(row)
        for repeated in seen.values():
            if len(repeated) > 1:
                numbers = ", ".join(str(item["row"]) for item in repeated)
                for item in repeated:
                    reject_action_row(item, "文件里有重复的工号和设备编号组合，这些行都没有导入：第 " + numbers
                                      + " 行。请去掉重复项后重新上传。", field="machine_code", code="duplicate_entry")

    def _load_entities(self, rows) -> Dict[str, Dict[str, Any]]:
        """按去重后的编号取实体，避免逐行查库。"""
        wanted: Dict[str, set] = {"operator": set(), "machine": set()}
        for row in rows:
            for key, entity in _ENTITY_OF.items():
                code = row["values"].get(key)
                if code is not None:
                    wanted[entity].add(code)
        loaded: Dict[str, Dict[str, Any]] = {"operator": {}, "machine": {}}
        for entity, codes in wanted.items():
            for code in sorted(codes):
                raw = self.repo.raw(entity, code)
                loaded[entity][code] = dict(raw) if raw is not None else None
        return loaded

    def _resolve_entities(self, row, entities) -> None:
        if _blocked(row):
            return
        for key, entity in _ENTITY_OF.items():
            code = row["values"].get(key)
            raw = entities[entity].get(code)
            if raw is None:
                reject_action_row(row, "系统里找不到这个编号，这一行没有导入。请先在基础资料里维护好再导入。", field=key)
                return
        operator = entities["operator"][row["values"]["operator_code"]]
        machine = entities["machine"][row["values"]["machine_code"]]
        row["expected"] = {"operator": operator, "machine": machine}
        row["values"]["operator_label"] = operator.get("name")
        row["values"]["machine_label"] = machine.get("name")

    def _load_current_links(self, rows) -> Dict[str, Dict[str, Dict[str, str]]]:
        """一次取回涉及人员的全部现有关联；连带影响要看整组，不能只看文件里这几行。"""
        codes = sorted({row["values"].get("operator_code") for row in rows
                        if not _blocked(row) and row["values"].get("operator_code")})
        current: Dict[str, Dict[str, Dict[str, str]]] = {code: {} for code in codes}
        if not codes:
            return current
        for link in self.links.list_simple_rows_for_operators(codes):
            current.setdefault(link["operator_id"], {})[link["machine_id"]] = {
                "skill_level": normalize_skill_level_stored(link.get("skill_level")),
                "is_primary": normalize_yes_no_stored(link.get("is_primary")),
            }
        return current

    def _final_primaries(self, rows, current) -> Dict[str, Set[str]]:
        """每个人确认后的主操设备。文件显式指定优先，其次保持原样，显式取消则变成没有主操。"""
        kept = {operator for operator, links in current.items() if self._unchanged_operator(operator, links, rows)}
        claimed = self._claimed_primaries(rows, kept)
        return {operator: self._primary_for(operator, links, rows, claimed, operator in kept)
                for operator, links in current.items()}

    @staticmethod
    def _unchanged_operator(operator, links, rows) -> bool:
        """文件里这个人的每一行都和现有关系一样：技能等级、主操标记要么没填，要么就是原值。"""
        for row in rows:
            if _blocked(row) or row["values"].get("operator_code") != operator:
                continue
            before = links.get(row["values"]["machine_code"])
            if before is None or any(row["values"].get(key) not in (None, before[key]) for key in ("skill_level", "is_primary")):
                return False
        return True

    @staticmethod
    def _claimed_primaries(rows, kept=()) -> Dict[str, List[Dict[str, Any]]]:
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
    def _current_primary(links) -> Optional[str]:
        return next((code for code, value in sorted(links.items()) if value["is_primary"] == "yes"), None)

    @classmethod
    def _primary_for(cls, operator, links, rows, claimed, kept=False) -> Set[str]:
        if kept:
            return {code for code, value in links.items() if value["is_primary"] == "yes"}  # 原样保留，旧数据多台也不动
        existing = cls._current_primary(links)
        items = claimed.get(operator) or []
        if len(items) == 1:
            return {items[0]["values"]["machine_code"]}
        # 多行抢主操的那一组已经整批拒绝，主操保持原样；没人抢时只看原主操有没有被显式取消。
        dropped = not items and any(row["values"].get("is_primary") == "no" and row["values"]["machine_code"] == existing
                                    for row in rows if not _blocked(row) and row["values"].get("operator_code") == operator)
        return set() if dropped or existing is None else {existing}

    def _classify(self, row, current, primaries) -> None:
        if _blocked(row):
            return
        links = current.get(row["values"]["operator_code"], {})
        before = links.get(row["values"]["machine_code"])
        row["after"] = row["input"] = self._after_values(row, before, primaries)
        row["action"] = "create" if before is None else "update"
        row["result"] = "new" if before is None else self._diff(row, before)
        row["reference_count"] = len(links)
        self._add_primary_notes(row, links)

    @staticmethod
    def _after_values(row, before, primaries) -> Dict[str, Any]:
        machine = row["values"]["machine_code"]
        return {
            "operator_code": row["values"]["operator_code"],
            "machine_code": machine,
            "skill_level": row["values"].get("skill_level") or (before or {}).get("skill_level") or "normal",
            "is_primary": "yes" if machine in primaries.get(row["values"]["operator_code"], ()) else "no",
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
    def _add_primary_notes(row, links) -> None:
        """主操连带必须在预检就说清楚：会顶掉谁，以及没填的行为什么会变成非主操。

        不变的行确认时不写，也就顶不掉谁，不提示。
        """
        if row["after"]["is_primary"] == "yes" and row["result"] != "unchanged":
            replaced = [code for code, value in sorted(links.items())
                        if value["is_primary"] == "yes" and code != row["after"]["machine_code"]]
            if replaced:
                row["notes"].append("确认后 " + "、".join(replaced) + " 不再是这个人的主操设备。")
                row["requires_confirmation"] = True
        if row["result"] == "update" and "is_primary" in row["changes"] and "is_primary" not in row["values"]:
            row["notes"].append("这一行没有填主操设备，但同一份文件把主操给了别的设备，所以这里会变成非主操。")
            row["requires_confirmation"] = True

    def confirm_import(self, preview, content, *, file_format, mode="upsert"):
        if not self.conn.in_transaction:
            raise RuntimeError("关系导入确认必须在外层工作台写事务中执行。")
        with self.tx.transaction():
            try:
                current = self.preview_import(content, file_format=file_format, mode=mode)
            except ValidationError as exc:
                raise WorkbenchCommandRejected(
                    "stale_write", "文件或相关资料已经变了，没有导入。请点「重新预检」后再确认。") from exc
            check_resource_preview(preview, current)
            body = current.as_dict()
            if body["summary"]["rejected"]:
                # 整批原子：只要还有一行不能提交，就一行都不写，不靠调用方记得看 can_confirm。
                raise WorkbenchCommandRejected(
                    "constraint_conflict", "这一批里有不能导入的行，一行都没有导入。请修好标红的行后重新预检。")
            rows = body["rows"]
            # 主操那一行最后写：底层写入主操时会清掉同一个人其他设备的主操标记。
            for row in sorted(rows, key=lambda item: (item.get("after") or {}).get("is_primary") == "yes"):
                if row["result"] in ("unchanged", "rejected"):
                    continue
                after = row["after"]
                writer = self.domain.add_link if row["action"] == "create" else self.domain.update_link_fields
                writer(after["operator_code"], after["machine_code"], skill_level=after["skill_level"],
                       is_primary=after["is_primary"], preserve_unchanged=True)
            results = [{"row": row["row"], "business_code": row["business_code"],
                        "result": "unchanged" if row["result"] == "unchanged" else "committed"} for row in rows]
            changed = any(item["result"] == "committed" for item in results)
            return WorkbenchCommandOutcome("committed" if changed else "unchanged",
                                           {"rows": results, "summary": body["summary"]})

    # ---------- 导出 ----------

    def _reader(self):
        return WorkbenchResourceQueryService(self.conn, "operator", self.logger)

    def preview_export(self, selection, *, scope, selected_refs=None):
        if not self.conn.in_transaction:
            raise RuntimeError("关系导出预览必须在已验证的查询快照事务中执行。")
        if selection not in ("all", "filtered", "selected") or (selection != "selected" and selected_refs is not None):
            raise WorkbenchCommandRejected(
                "invalid_input", "导出前要先选清楚是全部、当前筛选还是勾选的人员，没有开始下载。请重新选择导出范围。", 400)
        scope = resource_scope("operator", scope)
        if selection == "selected":
            refs = resource_refs(selected_refs, allow_empty=True)
            codes = [self._reader().resolve(ref).entity_key for ref in refs]
            return {"scope": scope, "selected_refs": refs}, len(self._rows_for(codes))
        effective = resource_scope("operator", {}) if selection == "all" else scope
        codes = self._codes_for_scope(effective)
        return {"scope": effective}, len(self._rows_for(codes))

    def _codes_for_scope(self, scope) -> List[str]:
        reader = self._reader()
        matching = reader.matching_rows(ResourcePageRequest(kind="operator", **scope))
        codes = []
        for row in matching:
            if row["ref"] is None:
                raise WorkbenchCommandRejected(
                    "storage_failure", "有人员在资料里查不到编号，没有开始下载，资料也没有被改动。请到资料总览核对后重试。", 500)
            codes.append(reader.resolve(row["ref"]).entity_key)
        return codes

    def _rows_for(self, codes) -> List[Dict[str, Any]]:
        if not codes:
            return []
        names = {"operator": {}, "machine": {}}
        rows = []
        for link in self.links.list_simple_rows_for_operators(sorted(set(codes))):
            # 导出写中文：文件里的下拉和填写说明都是中文，格子里却留英文代号的话，
            # 用户点一下下拉就改了值，想照原样填回 normal 又会被数据校验拒掉。
            # 直接下标不兜底：normalize_*_stored 保证给的是规范值，取不到说明契约破了，
            # 应当当场暴露而不是悄悄写一个默认档位。
            rows.append({
                "operator_code": link["operator_id"],
                "machine_code": link["machine_id"],
                "skill_level": EXPORT_LABELS["skill_level"][normalize_skill_level_stored(link.get("skill_level"))],
                "is_primary": EXPORT_LABELS["is_primary"][normalize_yes_no_stored(link.get("is_primary"))],
            })
        for row in rows:
            for key, entity in _ENTITY_OF.items():
                code = row[key]
                if code not in names[entity]:
                    raw = self.repo.raw(entity, code)
                    names[entity][code] = (dict(raw).get("name") if raw is not None else None)
            row["operator_label"] = names["operator"][row["operator_code"]]
            row["machine_label"] = names["machine"][row["machine_code"]]
        rows.sort(key=lambda item: (item["operator_code"], item["machine_code"]))
        return rows

    def export(self, file_format, *, scope, selected_refs=None):
        if not self.conn.in_transaction:
            raise RuntimeError("关系导出必须在已验证的查询快照事务中执行。")
        scope = resource_scope("operator", scope)
        if selected_refs is None:
            codes = self._codes_for_scope(scope)
        else:
            reader = self._reader()
            codes = [reader.resolve(ref).entity_key for ref in resource_refs(selected_refs, allow_empty=True)]
        rows = self._rows_for(codes)
        check_capacity(len(rows), file_format)
        return write_relation_file(self.kind, rows, file_format)

    @staticmethod
    def template(kind, file_format="xlsx"):
        return write_relation_file(relation_kind(kind), [], file_format, template=True)
