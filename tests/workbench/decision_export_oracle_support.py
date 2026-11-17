"""Independent expectations for decision exports, read only from public API fields.

The field tables below are this oracle's own copy of the export contract; no product row writer is imported.
"""

import json
from urllib.parse import urlencode

from tests.workbench.run_candidate_support import BASE

UNIFIED_PROCESS_VERSION = "unified-optimization-process-v1"
PROCESS_EXPORT_COMMON = ("排产编号", "归档编号", "读取编号", "读取时间", "保存推荐候选编号", "当前查看候选编号", "比较模式",
    "查看基准编号", "查看基准类型", "范围起点（含）", "范围终点（不含）", "资源视角", "推荐版本")
PROCESS_EXPORT_DIRECTION_FIELDS = ("优化方向", "优化方向名称", "主指标key", "主指标", "主指标单位")
PROCESS_EXPORT_COUNT_FIELDS = (
    ("actual_decoder_calls", "共同实际排程调用数"),
    ("new_decisions", "共同新增决策数"),
    ("decision_reuses", "共同决策复用数"),
    ("skipped_requests", "共同跳过执行次数"),
    ("failed_decoder_calls", "共同排程失败数"),
    ("request_count", "共同不同决策请求数"),
)
PROCESS_EXPORT_GOAL_FIELDS = (
    ("objective_status", "方向状态"),
    ("weight", "方向预算权重"),
    ("elapsed_seconds", "方向实际耗时（秒）"),
    ("charged_seconds", "方向计入预算耗时（秒）"),
    ("preparation_seconds", "方向准备耗时（秒）"),
    ("action_count", "方向动作数"),
    ("new_decisions", "方向新增决策数"),
    ("reused_decisions", "方向复用决策数"),
    ("probe_decisions", "方向探测决策数"),
    ("minimum_opportunity", "方向已取得最小机会"),
    ("improvement_action_count", "方向改善动作数"),
    ("has_gain", "方向已有改善"),
    ("feedback_rate", "方向改善反馈率"),
    ("feedback_bonus", "方向预算反馈增量"),
    ("unavailable_reason", "方向无机会原因"),
    ("budget_reason", "方向预算原因"),
)
PROCESS_EXPORT_ACTION_FIELDS = (
    ("action_id", "动作编号"),
    ("phase", "阶段"),
    ("initial_construction", "共同首次构造"),
    ("started_elapsed_ms", "动作起点（毫秒）"),
    ("finished_elapsed_ms", "动作终点（毫秒）"),
    ("elapsed_ms", "动作实际耗时（毫秒）"),
    ("evaluation_count", "动作评估数"),
    ("verified_evaluation_count", "动作已验证评估数"),
    ("new_decisions", "动作新增决策数"),
    ("reused_decisions", "动作复用决策数"),
    ("skip_reason", "动作跳过原因"),
)
PROCESS_EXPORT_STAGE_FIELDS = (
    ("phase", "阶段"),
    ("start_elapsed_ms", "阶段动作起点（毫秒）"),
    ("end_elapsed_ms", "阶段动作终点（毫秒）"),
    ("elapsed_ms", "阶段预算累计耗时（毫秒）"),
    ("action_count", "阶段动作数"),
    ("evaluation_count", "阶段评估数"),
    ("verified_evaluation_count", "阶段已验证评估数"),
    ("new_decisions", "阶段新增决策数"),
    ("reused_decisions", "阶段复用决策数"),
)
PROCESS_EXPORT_BRIDGE_FIELDS = (
    ("search_objective", "实际搜索方向"),
    ("phase", "阶段"),
    ("before_entry_id", "桥接前条目编号"),
    ("after_entry_id", "桥接后条目编号"),
    ("source_event_id", "来源事件编号"),
    ("started_elapsed_ms", "桥接起点（毫秒）"),
    ("finished_elapsed_ms", "桥接终点（毫秒）"),
    ("elapsed_ms", "桥接实际耗时（毫秒）"),
    ("same_arrangement", "桥接安排相同"),
    ("decoder_executed", "桥接实际调用排程"),
    ("reference_kind", "桥接来源类型"),
)
PROCESS_EXPORT_SCORE_FIELDS = tuple("评分分量" + str(index) for index in range(6))
PROCESS_EXPORT_SCORE_UNITS = tuple("评分分量" + str(index) + "单位" for index in range(6))
PROCESS_EXPORT_SCORE_KEYS = tuple("评分分量" + str(index) + "指标key" for index in range(6))
PROCESS_EXPORT_TABLE_FIELDS = {
    "共同计算": ("record_kind", "过程版本", "共同计时来源", "共同总耗时（毫秒）", "首次完整解（毫秒）", "停止原因", "主目标",
              "目标方向目录", "查看过程候选编号", "查看过程候选名称", "查看过程来源事件编号", "共同候选来源目录",
              "共同执行类型计数", "共同预算") + tuple(label for _, label in PROCESS_EXPORT_COUNT_FIELDS),
    "目标预算": ("record_kind",) + PROCESS_EXPORT_DIRECTION_FIELDS + tuple(label for _, label in PROCESS_EXPORT_GOAL_FIELDS)
              + ("首次真实评分改善（毫秒）", "最后真实评分改善（毫秒）", "进步采样记录"),
    "进步事件": ("record_kind",) + PROCESS_EXPORT_DIRECTION_FIELDS + (
        "累计共同耗时（毫秒）", "档案条目编号", "来源事件编号", "实际搜索方向", "实际来源",
        "阶段", "已验证", "评价范围编号", "连续段", "进步标记", "业务主值")
        + PROCESS_EXPORT_SCORE_FIELDS + PROCESS_EXPORT_SCORE_UNITS + PROCESS_EXPORT_SCORE_KEYS,
    "搜索动作": ("record_kind",) + PROCESS_EXPORT_DIRECTION_FIELDS + tuple(label for _, label in PROCESS_EXPORT_ACTION_FIELDS)
              + ("动作改善方向",),
    "搜索阶段": ("record_kind",) + PROCESS_EXPORT_DIRECTION_FIELDS + tuple(label for _, label in PROCESS_EXPORT_STAGE_FIELDS),
    "评价范围": ("record_kind", "评价范围编号", "目标评价范围", "评分分量已知", "本次工序已排齐", "已排工序成员数", "排齐批次成员数"),
    "范围成员": ("record_kind", "评价范围编号", "成员类型", "成员顺序", "成员永久编号"),
    "真实桥接": ("record_kind",) + tuple(label for _, label in PROCESS_EXPORT_BRIDGE_FIELDS),
}
PROCESS_EXPORT_HEADERS = {title: PROCESS_EXPORT_COMMON + fields for title, fields in PROCESS_EXPORT_TABLE_FIELDS.items()}
# The public process view's default sort for each record kind; the default order is ascending.
PROCESS_DEFAULT_SORTS = {"attempts": "rank", "progress": "elapsed_ms"}


def check_overview_export_rows(data, rows, fmt):
    """Every overview export row equals the screen's candidate metric and delta for that row."""
    definitions = {item["label"]: item for item in data["metric_definitions"]}
    candidates = {item["candidate_ref"]: item for item in data["candidates"]}
    for row in rows:
        candidate = candidates[row["候选编号"]]
        definition = definitions[row["指标"]]
        key = definition["key"]
        metric, delta = candidate["metrics"][key], candidate["deltas"][key]
        expected = {"排产编号": data["run"]["run_ref"], "归档编号": data["capture_ref"],
                    "候选名称": candidate["label"], "查看基准名称": data["baseline"]["label"],
                    "查看基准编号": (data["baseline"]["candidate_ref"] if data["baseline"]["kind"] == "candidate"
                                     else data["baseline"]["baseline_ref"]),
                    "所选方案编号": data["scope"]["selected_candidate_ref"],
                    "推荐方案编号": data["recommendation"]["candidate_ref"], "单位": definition["unit"],
                    "缺项说明": None if metric["reason"] is None else metric["reason"]["message"],
                    "范围起点（含）": data["scope"]["range_start"], "范围终点（不含）": data["scope"]["range_end"],
                    "数值": metric["value"], "已知小计": metric["known_subtotal"],
                    "基准数值": delta["reference_value"], "差值（候选减基准）": delta["value"]}
        if definition["unit"] == "%":
            for field in ("数值", "已知小计", "基准数值", "差值（候选减基准）"):
                if expected[field] is not None:
                    expected[field] *= 100
        for field, value in expected.items():
            actual = row[field]
            if fmt == "xlsx" and type(value) in (int, float) and type(actual) not in (int, float):
                raise RuntimeError("XLSX 数字字段被写成文本：{} / {} / {}".format(row["候选编号"], key, field))
            if value is None:
                equal = actual == ("" if fmt == "csv" else None)
            elif type(value) in (int, float):
                # openpyxl writes numeric cells with sixteen significant digits.
                expected_number = float(format(value, ".16g")) if fmt == "xlsx" else float(value)
                equal = actual not in (None, "") and float(actual) == expected_number
            else:
                equal = actual == value
            if not equal:
                raise RuntimeError("导出与屏幕字段不同：{} / {} / {}".format(row["候选编号"], key, field))


def _process_export_common(document):
    data, meta = document["data"], document["meta"]
    scope, baseline = data["scope"], data["baseline"]
    return dict(zip(PROCESS_EXPORT_COMMON, [data["run"]["run_ref"], data["capture_ref"], meta["snapshot_ref"], meta["as_of"],
        data["recommendation"]["candidate_ref"], scope["selected_candidate_ref"], scope["comparison_mode"],
        baseline["candidate_ref"] if baseline["kind"] == "candidate" else baseline["baseline_ref"], baseline["kind"],
        scope["range_start"], scope["range_end"], scope["resource_view"], data["recommendation"]["recommendation_version"]]))


def _process_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _process_public_pages(client, path, query):
    """One record kind read at page sizes 20 and 50; both complete row unions must match on one snapshot."""
    kind, bound = query["record_kind"], dict(query)
    combined, heads, first = {}, {}, None
    for size in (20, 50):
        items, number = [], 1
        while True:
            public = client.get(path + "/process?" + urlencode(dict(bound, page=number, size=size))).get_json()
            data, meta = public["data"], public["meta"]
            if first is None:
                first = public
                bound["snapshot_ref"] = meta["snapshot_ref"]
            if number == 1:
                heads[size] = data
            if (meta["snapshot_ref"] != first["meta"]["snapshot_ref"] or meta["as_of"] != first["meta"]["as_of"]
                    or data["page"]["number"] != number or data["page"]["size"] != size
                    or data["page"]["total"] != first["data"]["page"]["total"]):
                raise RuntimeError("计算过程分页的快照、读取时间或页码不同。")
            if data["filters"] != first["data"]["filters"] or data["candidate"] != first["data"]["candidate"]:
                raise RuntimeError("计算过程翻页改变了锚点或筛选条件。")
            items.extend(data["items"])
            expected_more = number * size < data["page"]["total"]
            if len(data["items"]) != min(size, max(0, data["page"]["total"] - (number - 1) * size)) or data["page"]["has_more"] is not expected_more:
                raise RuntimeError("计算过程分页条数或下一页状态与完整总数不同。")
            if not data["page"]["has_more"]:
                break
            number += 1
        combined[size] = items
    if combined[20] != combined[50] or len(combined[20]) != first["data"]["page"]["total"]:
        raise RuntimeError("计算过程20/50全页原始对象或顺序不同。")
    if "actions" in first["data"]:
        raise RuntimeError("计算过程分页响应不应包含未分页完整搜索动作数组。")
    raw_points = first["data"]["progress"]["points"]
    if kind == "progress" and sorted(combined[20], key=lambda row: json.dumps(row, sort_keys=True)) != sorted(raw_points, key=lambda row: json.dumps(row, sort_keys=True)):
        raise RuntimeError("计算过程分页遗漏或增加了公开完整进步事件。")
    selected_objective = first["data"]["selected_objective"]["name"]
    action_count = first["data"]["budget"]["objectives"][selected_objective]["action_count"]
    if kind == "attempts" and (
        len(combined[20]) != action_count
        or len({row["action_id"] for row in combined[20]}) != len(combined[20])
        or any(row["search_objective"] != selected_objective for row in combined[20])
    ):
        raise RuntimeError("计算过程分页遗漏或增加了公开完整搜索动作。")
    return dict(heads[50], items=combined[50])


def collect_process_export_sources(client, run_ref, query, overview, *, scope_members):
    """Every retained process record of the default process view for all target objectives, read from public pages.

    ``query`` is the comparison view. The default process view anchors on its selected candidate and reads each record
    kind in its default ascending sort. ``scope_members`` are the archived scope member refs, which the public view only counts.
    """
    ref = overview["data"]["scope"]["selected_candidate_ref"]
    basis = overview["data"]["selection_basis"]
    path = BASE + "/runs/" + run_ref + "/decision"
    shared_keys = ("process_version", "summary", "counts", "budget", "stop_reason", "bridges",
                   "objectives", "selected_objective", "scopes", "stages", "candidate", "candidates",
                   "source_event", "scope", "baseline")
    first, by_objective = None, {}
    for name in basis["target_objectives"]:
        attempts, progress = (_process_public_pages(client, path, dict(
            query, process_candidate_ref=ref, objective=name, record_kind=kind, sort=sort, order="asc"))
            for kind, sort in PROCESS_DEFAULT_SORTS.items())
        for key in shared_keys:
            if attempts[key] != progress[key]:
                raise RuntimeError("进步事件与搜索动作的保存过程来源不同：" + key)
        if first is None:
            first = attempts
            if (attempts["candidate"]["candidate_ref"] != ref or attempts["run_ref"] != run_ref
                    or attempts["scope"] != overview["data"]["scope"]
                    or any(value != overview["data"]["baseline"][key] for key, value in attempts["baseline"].items())):
                raise RuntimeError("计算过程的锚点、查看方案、基准或共同窗口不同。")
            if attempts["process_version"] != UNIFIED_PROCESS_VERSION:
                raise RuntimeError("计算过程公共版本与本轮验收契约不同。")
            if [row["name"] for row in attempts["objectives"]] != basis["target_objectives"]:
                raise RuntimeError("计算过程目标方向目录与推荐依据不一致。")
        else:
            for key in ("process_version", "counts", "budget", "stop_reason", "bridges", "objectives",
                        "scopes", "candidate", "candidates", "source_event", "scope", "baseline"):
                if attempts[key] != first[key]:
                    raise RuntimeError("不同优化方向的共同计算过程事实不同：" + key)
        if (len(attempts["items"]) != attempts["budget"]["objectives"][name]["action_count"]
                or len(progress["items"]) != progress["progress"]["sampling"]["retained_point_count"]):
            raise RuntimeError("计算过程全部保存条数与采样记录不同。")
        if len(progress["items"]) > 200:
            raise RuntimeError("计算过程超过本轮保留上限。")
        by_objective[name] = {
            "selected_objective": attempts["selected_objective"],
            "summary": attempts["summary"],
            "budget": attempts["budget"]["objectives"][name],
            "stages": attempts["stages"],
            "actions": attempts["items"],
            "progress": dict(progress["progress"], points=progress["items"]),
        }
    return {
        "process_version": first["process_version"],
        "primary_objective": basis["primary_objective"],
        "target_objectives": basis["target_objectives"],
        "summary": first["summary"],
        "counts": first["counts"],
        "budget": first["budget"],
        "stop_reason": first["stop_reason"],
        "bridges": first["bridges"],
        "scopes": first["scopes"],
        "scope_members": scope_members,
        "candidate": first["candidate"],
        "candidates": first["candidates"],
        "source_event": first["source_event"],
        "objectives": by_objective,
    }


def process_export_expected(document, saved):
    """The process export tables expected for ``document``'s read binding and the public sources ``saved``."""
    common = _process_export_common(document)
    groups = {title: [] for title in PROCESS_EXPORT_HEADERS}
    source_event, candidate = saved["source_event"], saved["candidate"]
    groups["共同计算"].append({
        "record_kind": "run_process_summary",
        "过程版本": saved["process_version"],
        "共同计时来源": "shared_monotonic",
        "共同总耗时（毫秒）": saved["summary"]["elapsed_ms"],
        "首次完整解（毫秒）": saved["summary"]["first_complete_elapsed_ms"],
        "停止原因": saved["stop_reason"],
        "主目标": saved["primary_objective"],
        "目标方向目录": _process_json(saved["target_objectives"]),
        "查看过程候选编号": candidate["candidate_ref"],
        "查看过程候选名称": candidate["label"],
        "查看过程来源事件编号": source_event["event_id"] if source_event is not None else None,
        "共同候选来源目录": _process_json(saved["candidates"]),
        "共同执行类型计数": _process_json(saved["counts"]["execution_counts"]),
        "共同预算": _process_json({key: value for key, value in saved["budget"].items()
                                 if key not in ("objectives", "objective_status")}),
        **{label: saved["counts"][key] for key, label in PROCESS_EXPORT_COUNT_FIELDS},
    })
    for name in saved["target_objectives"]:
        projected = saved["objectives"][name]
        objective = projected["selected_objective"]
        direction = {
            "优化方向": objective["name"],
            "优化方向名称": objective["label"],
            "主指标key": objective["primary_metric_key"],
            "主指标": objective["primary_metric_label"],
            "主指标单位": objective["unit"],
        }
        groups["目标预算"].append({
            "record_kind": "objective_budget",
            **direction,
            **{label: projected["budget"][key] for key, label in PROCESS_EXPORT_GOAL_FIELDS},
            "首次真实评分改善（毫秒）": projected["summary"]["first_improvement_elapsed_ms"],
            "最后真实评分改善（毫秒）": projected["summary"]["last_improvement_elapsed_ms"],
            "进步采样记录": _process_json(projected["progress"]["sampling"]),
        })
        score_units = {field["key"]: field["unit"] for field in objective["score_fields"]}
        for point in projected["progress"]["points"]:
            groups["进步事件"].append({
                "record_kind": "progress_point",
                **direction,
                "累计共同耗时（毫秒）": point["elapsed_ms"],
                "档案条目编号": point["entry_id"],
                "来源事件编号": point["source_event_id"],
                "实际搜索方向": point["search_objective"],
                "实际来源": point["origin"],
                "阶段": point["phase"],
                "已验证": point["verified"],
                "评价范围编号": point["scope_ref"],
                "连续段": point["segment"],
                "进步标记": _process_json(point["flags"]),
                "业务主值": point["primary_value"],
                **{label: point["score"][index] if index < len(point["score"]) else None
                   for index, label in enumerate(PROCESS_EXPORT_SCORE_FIELDS)},
                **{label: point["field_order"][index] if index < len(point["field_order"]) else None
                   for index, label in enumerate(PROCESS_EXPORT_SCORE_KEYS)},
                **{label: score_units[point["field_order"][index]] if index < len(point["field_order"]) else None
                   for index, label in enumerate(PROCESS_EXPORT_SCORE_UNITS)},
            })
        for action in projected["actions"]:
            groups["搜索动作"].append({
                "record_kind": "search_action",
                **direction,
                **{label: action[key] for key, label in PROCESS_EXPORT_ACTION_FIELDS},
                "动作改善方向": _process_json(action["improved_objectives"]),
            })
        for stage in projected["stages"]:
            groups["搜索阶段"].append({
                "record_kind": "stage",
                **direction,
                **{label: stage[key] for key, label in PROCESS_EXPORT_STAGE_FIELDS},
            })
    scope_members = saved["scope_members"]
    for scope_ref, scope in saved["scopes"].items():
        groups["评价范围"].append({
            "record_kind": "score_scope",
            "评价范围编号": scope_ref,
            "目标评价范围": scope["objective_scope"],
            "评分分量已知": scope["components_known"],
            "本次工序已排齐": scope["is_complete"],
            "已排工序成员数": scope["scheduled_operation_count"],
            "排齐批次成员数": scope["complete_batch_count"],
        })
        raw_scope = scope_members[scope_ref]
        for kind, members in (("scheduled_operation", raw_scope["scheduled_operation_refs"]),
                              ("complete_batch", raw_scope["complete_batch_refs"])):
            for index, member in enumerate(members, 1):
                groups["范围成员"].append({
                    "record_kind": "scope_member",
                    "评价范围编号": scope_ref,
                    "成员类型": kind,
                    "成员顺序": index,
                    "成员永久编号": member,
                })
    for bridge in saved["bridges"]:
        groups["真实桥接"].append({
            "record_kind": "bridge",
            **{label: bridge[key] for key, label in PROCESS_EXPORT_BRIDGE_FIELDS},
        })
    return {title: [{**dict.fromkeys(PROCESS_EXPORT_HEADERS[title]), **common, **values} for values in rows]
            for title, rows in groups.items()}


def check_process_export_sheet(sheet, expected, title):
    """One process export worksheet equals ``expected``: header order, row count, and each cell's value and native type."""
    headers = PROCESS_EXPORT_HEADERS[title]
    # Read-only rows stop at their last filled cell; max_col pads the rest with empty cells.
    rows = list(sheet.iter_rows(min_row=2, max_col=len(headers)))
    if next(sheet.iter_rows(max_row=1, values_only=True)) != headers or len(rows) != len(expected):
        raise RuntimeError("计算过程导出列或完整事实行数不同：" + title)
    for index, (cells, values) in enumerate(zip(rows, expected), 1):
        for header, cell in zip(headers, cells):
            value = values[header]
            if value is None:
                equal = cell.value is None
            elif type(value) is bool:
                equal = cell.value is value and cell.data_type == "b"
            elif type(value) in (int, float):
                # openpyxl writes numeric cells with sixteen significant digits.
                equal = (type(cell.value) in (int, float) and cell.data_type == "n"
                         and float(cell.value) == float(format(value, ".16g")))
            else:
                equal = cell.value == value and cell.data_type == "s"
            if not equal:
                raise RuntimeError(f"计算过程导出字段、单位或原生类型不同：{title} / 行{index} / {header} / 实际 {cell.value!r} / 期待 {value!r}")
