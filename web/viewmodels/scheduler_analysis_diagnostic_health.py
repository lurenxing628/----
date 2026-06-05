from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .scheduler_analysis_diagnostic_helpers import (
    build_item,
    build_section,
    detail_from_samples,
    error_count,
    format_count,
    format_minutes,
    graph_status_value,
    level_if,
    safe_dict,
    safe_int,
    sample_text_values,
    status_label,
    summary_warning_count,
    text_if,
)


def _overall_health_status(
    *,
    graph_status: str,
    has_cycle: bool,
    error_total: int,
    warning_total: int,
) -> Dict[str, str]:
    if graph_status in {"input_error", "build_error"}:
        return {
            "status": "error",
            "graph_level": "danger",
            "summary": "图分析输入或构图异常，本次诊断需要先处理图分析错误。",
        }
    if graph_status == "unavailable":
        return {
            "status": "unavailable",
            "graph_level": "warning",
            "summary": "本版本记录了图分析不可用，诊断摘要只展示能确认的信息。",
        }
    if graph_status != "available":
        return {
            "status": "unknown",
            "graph_level": "unknown",
            "summary": "本版本的图分析状态未知，诊断摘要只展示能确认的信息。",
        }
    if has_cycle:
        return {
            "status": "danger",
            "graph_level": "danger",
            "summary": "这版排产发现工序关系循环，需要先确认工序先后关系。",
        }
    if error_total > 0:
        return {
            "status": "danger",
            "graph_level": "danger",
            "summary": "这版排产记录了错误信息，需要先确认错误原因。",
        }
    if warning_total > 0:
        return {
            "status": "warning",
            "graph_level": "warning",
            "summary": "这版排产有提醒信息，需要关注后再使用结果。",
        }
    return {
        "status": "ok",
        "graph_level": "ok",
        "summary": "这版排产没有发现明显结构问题。",
    }


def _overall_health_extra_items(*, error_total: int, warning_total: int) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if error_total > 0:
        items.append(
            build_item(
                key="error_count",
                label="错误信息",
                value=format_count(error_total, "条"),
                level="danger",
                message="本次结果里记录了错误信息。",
            )
        )
    if warning_total > 0:
        items.append(
            build_item(
                key="warning_count",
                label="提醒信息",
                value=format_count(warning_total, "条"),
                level="warning",
                message="本次结果里记录了提醒信息。",
            )
        )
    return items


def _public_graph_status_message(graph_public: Dict[str, Any]) -> str:
    raw = str(graph_public.get("message") or graph_public.get("reason") or "").strip()
    reason = str(graph_public.get("reason") or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if "networkx" in lowered or reason == "networkx_unavailable":
        return "图分析组件暂不可用，请检查应用安装包或联系维护人员。"
    if reason in {"graph_resource_matching_contract_error", "input_error", "build_error"}:
        return "图分析数据暂时无法读取，请到排产历史查看本次排产提醒。"
    if any(token in raw for token in ("candidate_machine_ids", "graph_ready_context", "predecessor_op_ids_by_op_id")):
        return "图分析数据暂时无法读取，请到排产历史查看本次排产提醒。"
    if "internal/external" in raw or "internal / external" in raw:
        return "工序归属数据不完整，请检查工艺路线里的自制/外协设置。"
    return "图分析状态记录异常，请到排产历史查看本次排产提醒。"


def build_overall_health_section(
    selected_summary: Optional[Dict[str, Any]],
    graph_public: Dict[str, Any],
) -> Dict[str, Any]:
    graph_status = str(graph_public.get("status") or "unknown")
    node_count = safe_int(graph_public.get("node_count"))
    edge_count = safe_int(graph_public.get("edge_count"))
    critical_path_minutes = safe_int(graph_public.get("critical_path_minutes"))
    cycle_edge_count = safe_int(graph_public.get("cycle_edge_count"))
    warning_total = safe_int(graph_public.get("warning_count")) + summary_warning_count(selected_summary)
    error_total = error_count(selected_summary)
    time_cost_ms = safe_int(graph_public.get("time_cost_ms"))
    state = _overall_health_status(
        graph_status=graph_status,
        has_cycle=graph_public.get("is_dag") is False or cycle_edge_count > 0,
        error_total=error_total,
        warning_total=warning_total,
    )

    items = [
        build_item(
            key="graph_status",
            label="图分析状态",
            value=graph_status_value(graph_public),
            level=state["graph_level"],
            message=_public_graph_status_message(graph_public),
        ),
        build_item(
            key="node_count",
            label="工序节点",
            value=format_count(node_count, "个"),
            level=level_if(node_count > 0, "ok", "notice"),
            message="本次进入工序图分析的工序数量。",
        ),
        build_item(
            key="edge_count",
            label="工序关系",
            value=format_count(edge_count, "条"),
            level=level_if(edge_count > 0, "ok", "notice"),
            message="本次识别到的工序先后关系数量。",
        ),
        build_item(
            key="critical_path_minutes",
            label="影响完工的工序时长",
            value=format_minutes(critical_path_minutes),
            level=level_if(critical_path_minutes > 0, "notice", "ok"),
            message="这些工序只是帮助解释当前结果，仍要结合交期一起看。",
        ),
        build_item(
            key="cycle_edge_count",
            label="循环关系",
            value=format_count(cycle_edge_count, "条"),
            level=level_if(cycle_edge_count > 0, "danger", "ok"),
            message="循环关系会让工序先后顺序无法可靠解释。",
        ),
        build_item(
            key="time_cost_ms",
            label="图分析耗时",
            value=f"{time_cost_ms} 毫秒",
            level="ok",
            message="只表示本次图分析本身的计算耗时。",
        ),
    ]
    items.extend(_overall_health_extra_items(error_total=error_total, warning_total=warning_total))

    return build_section(
        key="schedule_health",
        title="排产体检",
        status=state["status"],
        status_label=status_label(state["status"]),
        summary=state["summary"],
        items=items,
    )


def _resource_matching_summary(
    *,
    status: str,
    reason: str,
    ready_count: int,
    with_candidate_count: int,
    unmatched_count: int,
) -> str:
    no_candidate_count, waiting_count = _resource_gap_counts(
        ready_count=ready_count,
        with_candidate_count=with_candidate_count,
        unmatched_count=unmatched_count,
    )
    if status == "available" and unmatched_count > 0:
        if no_candidate_count > 0 and waiting_count > 0:
            return (
                f"第一批可排工序里有 {no_candidate_count} 道还没配可用设备，"
                f"另有 {waiting_count} 道能找到设备，但这轮设备不够同时安排。"
            )
        if no_candidate_count > 0:
            return f"第一批可排工序里有 {no_candidate_count} 道还没配可用设备，请先检查工序设备配置。"
        return f"第一批可排工序里有 {waiting_count} 道能找到设备，但这轮设备不够同时安排，后面还要继续排。"
    if status == "available":
        return "第一批可排工序都能找到设备。"
    if status == "empty":
        return "本次没有第一批可排工序可检查设备。"
    if status == "skipped" and reason == "graph_not_dag":
        return "工序先后关系有问题，本次先不检查设备安排。"
    if status == "skipped":
        return "本次先不检查设备安排，只展示跳过原因。"
    if status == "error":
        return "检查设备安排时出错，本次不展示设备检查结果。"
    return "本次设备检查状态不明确。"


def _resource_gap_counts(
    *,
    ready_count: int,
    with_candidate_count: int,
    unmatched_count: int,
) -> Tuple[int, int]:
    no_candidate_count = max(ready_count - with_candidate_count, 0)
    no_candidate_count = min(no_candidate_count, max(unmatched_count, 0))
    waiting_count = max(unmatched_count - no_candidate_count, 0)
    return no_candidate_count, waiting_count


def _unmatched_operation_message(
    *,
    unmatched_count: int,
    no_candidate_count: int,
    waiting_count: int,
) -> str:
    if unmatched_count <= 0:
        return "第一批可排工序这轮都能安排上设备。"
    if no_candidate_count > 0 and waiting_count > 0:
        return (
            f"这轮还有 {unmatched_count} 道没排上："
            f"{no_candidate_count} 道还没配可用设备，{waiting_count} 道能找到设备但要等后面继续排。"
        )
    if no_candidate_count > 0:
        return f"这轮还有 {no_candidate_count} 道没排上，主要是还没配可用设备。"
    return f"这轮还有 {waiting_count} 道没排上，不是没有设备能做，而是同一时间能用的设备不够。"


def _resource_matching_status(
    *,
    status: str,
    reason: str,
    unmatched_count: int,
) -> str:
    if status == "available" and unmatched_count > 0:
        return "warning"
    if status == "available":
        return "ok"
    if status == "empty":
        return "empty"
    if status == "skipped" and reason == "graph_not_dag":
        return "warning"
    if status == "skipped":
        return "notice"
    if status == "error":
        return "error"
    return "unknown"


def _build_resource_bottleneck_items(
    *,
    ready_count: int,
    with_candidate_count: int,
    machine_count: int,
    edge_count: int,
    matched_count: int,
    unmatched_count: int,
    bottleneck_count: int,
    unmatched_samples: Sequence[str],
    bottleneck_samples: Sequence[str],
) -> List[Dict[str, Any]]:
    no_candidate_count, waiting_count = _resource_gap_counts(
        ready_count=ready_count,
        with_candidate_count=with_candidate_count,
        unmatched_count=unmatched_count,
    )
    return [
        build_item(
            key="ready_operation_count",
            label="第一批可排工序",
            value=format_count(ready_count, "道"),
            level=level_if(ready_count == 0, "notice", "ok"),
            message="当前第一批可以先安排的工序数量。",
        ),
        build_item(
            key="operation_with_candidate_count",
            label="能找到设备的工序",
            value=format_count(with_candidate_count, "道"),
            level=level_if(with_candidate_count == ready_count, "ok", "warning"),
            message="这些工序已经能找到可安排的设备。",
        ),
        build_item(
            key="machine_count",
            label="可选设备数",
            value=format_count(machine_count, "台"),
            level=level_if(machine_count > 0, "ok", "notice"),
            message=f"本次共找到 {edge_count} 条“工序可以用哪台设备做”的记录。",
        ),
        build_item(
            key="matched_operation_count",
            label="这轮最多能先排",
            value=format_count(matched_count, "道"),
            level=level_if(matched_count >= ready_count and ready_count > 0, "ok", "notice"),
            message="这里按“一台设备这轮先排一道工序”来估算，看看第一批最多能先安排多少道。",
        ),
        build_item(
            key="unmatched_operation_count",
            label="这轮还没排上的工序",
            value=format_count(unmatched_count, "道"),
            level=level_if(unmatched_count > 0, "warning", "ok"),
            message=_unmatched_operation_message(
                unmatched_count=unmatched_count,
                no_candidate_count=no_candidate_count,
                waiting_count=waiting_count,
            ),
            details=detail_from_samples("这轮还没排上的工序样本：", unmatched_samples),
        ),
        build_item(
            key="bottleneck_machine_count",
            label="可能不够用的设备",
            value=format_count(bottleneck_count, "台"),
            level=level_if(bottleneck_count > 0, "warning", "ok"),
            message=text_if(
                bottleneck_count > 0,
                f"有 {bottleneck_count} 台设备同一时间被多道工序需要，后面可能要排队。",
                "暂时没看到明显不够用的设备。",
            ),
            details=detail_from_samples("可能不够用的设备样本：", bottleneck_samples),
        ),
    ]


def build_resource_bottleneck_section(
    graph_public: Dict[str, Any],
    graph_diagnostics: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    raw_resource_public = graph_public.get("resource_matching")
    if raw_resource_public is not None and not isinstance(raw_resource_public, dict):
        return build_section(
            key="resource_bottleneck",
            title="设备安排情况",
            status="error",
            status_label=status_label("error"),
            summary="本版本的设备安排诊断数据格式异常，暂时不能展示第一批可排工序和设备匹配情况。",
            empty_reason="请到排产历史查看本次排产提醒，或重新排产后再查看设备安排诊断。",
        )
    resource_public = safe_dict(raw_resource_public)
    if not resource_public:
        return build_section(
            key="resource_bottleneck",
            title="设备安排情况",
            status="empty",
            status_label=status_label("empty"),
            summary="本版本没有生成设备安排诊断，不能判断第一批可排工序有没有足够设备。",
            empty_reason="可先查看甘特图和资源排班；后续重新排产后，如果诊断数据生成成功，这里会显示设备安排情况。",
        )
    resource_diagnostics = safe_dict(graph_diagnostics.get("resource_matching"))

    status = str(resource_public.get("status") or "unknown")
    reason = str(resource_public.get("reason") or "")
    ready_count = safe_int(resource_public.get("ready_operation_count"))
    with_candidate_count = safe_int(resource_public.get("operation_with_candidate_count"))
    machine_count = safe_int(resource_public.get("machine_count"))
    edge_count = safe_int(resource_public.get("edge_count"))
    matched_count = safe_int(resource_public.get("matched_operation_count"))
    unmatched_count = safe_int(resource_public.get("unmatched_operation_count"))
    bottleneck_count = safe_int(resource_public.get("bottleneck_machine_count"))
    unmatched_samples = sample_text_values(resource_diagnostics.get("unmatched_operation_ids_sample"))
    bottleneck_samples = sample_text_values(resource_diagnostics.get("bottleneck_machine_ids_sample"))

    section_status = _resource_matching_status(
        status=status,
        reason=reason,
        unmatched_count=unmatched_count,
    )
    return build_section(
        key="resource_bottleneck",
        title="设备安排情况",
        status=section_status,
        status_label=status_label(section_status),
        summary=_resource_matching_summary(
            status=status,
            reason=reason,
            ready_count=ready_count,
            with_candidate_count=with_candidate_count,
            unmatched_count=unmatched_count,
        ),
        items=_build_resource_bottleneck_items(
            ready_count=ready_count,
            with_candidate_count=with_candidate_count,
            machine_count=machine_count,
            edge_count=edge_count,
            matched_count=matched_count,
            unmatched_count=unmatched_count,
            bottleneck_count=bottleneck_count,
            unmatched_samples=unmatched_samples,
            bottleneck_samples=bottleneck_samples,
        ),
        empty_reason=text_if(status == "empty", "本次没有第一批可排工序，因此没有设备安排情况可分析。", ""),
    )


__all__ = [
    "build_overall_health_section",
    "build_resource_bottleneck_section",
]
