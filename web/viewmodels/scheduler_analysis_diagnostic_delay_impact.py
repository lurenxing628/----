from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .scheduler_analysis_diagnostic_helpers import (
    SAMPLE_LIMIT,
    build_item,
    build_section,
    format_count,
    format_hours,
    format_minutes,
    safe_dict,
    safe_float,
    safe_int,
    safe_list,
    safe_text,
    sample_text_values,
    section_status_from_levels,
    status_label,
    summary_counts,
)


def _delay_risk_state(
    *,
    failed_ops: int,
    unscheduled_batch_count: int,
    effective_overdue_count: int,
    tardiness_hours: float,
    invalid_due_count: int,
    critical_path_minutes: int,
) -> Dict[str, str]:
    if failed_ops > 0:
        return {"status": "danger", "summary": f"有 {failed_ops} 道工序没有成功排入结果，需要优先处理。"}
    if unscheduled_batch_count > 0:
        return {"status": "warning", "summary": f"有 {unscheduled_batch_count} 个批次未排入结果，需要确认原因。"}
    if effective_overdue_count > 0:
        return {"status": "warning", "summary": f"当前结果里有 {effective_overdue_count} 个批次超期，需要结合交期处理。"}
    if tardiness_hours > 0:
        return {"status": "warning", "summary": f"当前结果记录了 {format_hours(tardiness_hours)} 总拖期，需要结合交期处理。"}
    if invalid_due_count > 0:
        return {"status": "warning", "summary": f"有 {invalid_due_count} 个批次交期异常，超期判断可能不完整。"}
    if critical_path_minutes > 0:
        return {"status": "notice", "summary": "本次没有看到失败、未排或超期批次；仍要结合交期看看哪些工序最影响完工时间。"}
    return {"status": "ok", "summary": "本次没有看到明显延期风险。"}


def _delay_risk_items(
    *,
    failed_ops: int,
    unscheduled_batch_count: int,
    effective_overdue_count: int,
    tardiness_hours: float,
    critical_path_minutes: int,
    critical_path_node_count: int,
    invalid_due_count: int,
) -> List[Dict[str, Any]]:
    items = [
        build_item(
            key="failed_ops",
            label="失败工序",
            value=format_count(failed_ops, "道"),
            level="danger" if failed_ops > 0 else "ok",
            message="没有排入结果的工序会直接影响交付。",
        ),
        build_item(
            key="unscheduled_batch_count",
            label="未排批次",
            value=format_count(unscheduled_batch_count, "个"),
            level="warning" if unscheduled_batch_count > 0 else "ok",
            message="未排批次需要先确认是否缺工序、缺资源或被过滤。",
        ),
        build_item(
            key="overdue_count",
            label="超期批次",
            value=format_count(effective_overdue_count, "个"),
            level="warning" if effective_overdue_count > 0 else "ok",
            message="超期批次来自当前排产结果和算法指标中的可用计数。",
        ),
        build_item(
            key="total_tardiness_hours",
            label="总拖期",
            value=format_hours(tardiness_hours),
            level="warning" if tardiness_hours > 0 else "ok",
            message="总拖期越高，说明超期批次离交期越远。",
        ),
        build_item(
            key="critical_path_minutes",
            label="影响完工的工序时长",
            value=format_minutes(critical_path_minutes),
            level="notice" if critical_path_minutes > 0 else "ok",
            message="这里不自行设危险阈值，需要结合实际交期判断。",
        ),
        build_item(
            key="critical_path_node_count",
            label="影响完工的工序数",
            value=format_count(critical_path_node_count, "道"),
            level="notice" if critical_path_node_count > 0 else "ok",
            message="这些工序越多，后面被带着一起变化的地方通常越多。",
        ),
    ]
    if invalid_due_count > 0:
        items.append(
            build_item(
                key="invalid_due_count",
                label="交期异常批次",
                value=format_count(invalid_due_count, "个"),
                level="warning",
                message="交期异常会让延期判断不完整。",
            )
        )
    return items


def build_delay_risk_section(
    selected_summary: Dict[str, Any],
    graph_public: Dict[str, Any],
) -> Dict[str, Any]:
    counts = summary_counts(selected_summary)
    algo = safe_dict(selected_summary.get("algo"))
    metrics = safe_dict(algo.get("metrics"))
    overdue_batches = safe_dict(selected_summary.get("overdue_batches"))

    failed_ops = safe_int(counts.get("failed_ops", selected_summary.get("failed_ops")))
    unscheduled_batch_count = safe_int(selected_summary.get("unscheduled_batch_count"))
    invalid_due_count = safe_int(selected_summary.get("invalid_due_count"))
    overdue_count = safe_int(metrics.get("overdue_count"))
    effective_overdue_count = max(overdue_count, safe_int(overdue_batches.get("count")))
    tardiness_hours = safe_float(metrics.get("total_tardiness_hours"))
    critical_path_minutes = safe_int(graph_public.get("critical_path_minutes"))
    critical_path_node_count = safe_int(graph_public.get("critical_path_node_count"))
    state = _delay_risk_state(
        failed_ops=failed_ops,
        unscheduled_batch_count=unscheduled_batch_count,
        effective_overdue_count=effective_overdue_count,
        tardiness_hours=tardiness_hours,
        invalid_due_count=invalid_due_count,
        critical_path_minutes=critical_path_minutes,
    )

    return build_section(
        key="delay_risk",
        title="延期风险",
        status=state["status"],
        status_label=status_label(state["status"]),
        summary=state["summary"],
        items=_delay_risk_items(
            failed_ops=failed_ops,
            unscheduled_batch_count=unscheduled_batch_count,
            effective_overdue_count=effective_overdue_count,
            tardiness_hours=tardiness_hours,
            critical_path_minutes=critical_path_minutes,
            critical_path_node_count=critical_path_node_count,
            invalid_due_count=invalid_due_count,
        ),
    )


def _format_node_metric_sample(value: Any) -> str:
    item = safe_dict(value)
    node_id = safe_text(item.get("node_id"))
    if not node_id:
        return ""
    details: List[str] = []
    rank = item.get("critical_path_rank")
    if rank is not None:
        details.append(f"影响顺序 {rank}")
    impact_count = item.get("impact_count")
    if impact_count is not None:
        details.append(f"影响 {impact_count} 个后续")
    generation_index = item.get("generation_index")
    if generation_index is not None:
        details.append(f"层级 {generation_index}")
    downstream_minutes = item.get("downstream_critical_minutes")
    if downstream_minutes is not None:
        details.append(f"后续关键时长 {safe_int(downstream_minutes)} 分钟")
    if details:
        return f"{node_id}（{'，'.join(details)}）"
    return node_id


def _format_graph_score_sample(value: Any) -> str:
    item = safe_dict(value)
    op_id = safe_text(item.get("op_id"))
    if not op_id:
        return ""
    details: List[str] = []
    impact_count = item.get("impact_count")
    if impact_count is not None:
        details.append(f"影响 {impact_count} 个后续")
    downstream_minutes = item.get("downstream_critical_minutes")
    if downstream_minutes is not None:
        details.append(f"后续关键时长 {safe_int(downstream_minutes)} 分钟")
    bonus = item.get("bonus")
    if bonus is not None:
        details.append(f"排法参考值 {bonus}")
    if details:
        return f"工序 {op_id}（{'，'.join(details)}）"
    return f"工序 {op_id}"


def _format_warning_sample(value: Any) -> str:
    item = safe_dict(value)
    code = safe_text(item.get("code"))
    message = safe_text(item.get("message"))
    if not code and not message:
        return ""
    lowered = (message or code).lower()
    if "networkx" in lowered:
        text = "图分析组件暂不可用，请检查应用安装包或联系维护人员。"
    elif any(token in (message or code) for token in ("candidate_machine_ids", "graph_ready_context", "predecessor_op_ids_by_op_id")):
        text = "图分析数据暂时无法读取，请到排产历史查看本次排产提醒。"
    elif "internal/external" in (message or code) or "internal / external" in (message or code):
        text = "工序归属数据不完整，请检查工艺路线里的自制/外协设置。"
    else:
        text = message or "有一条图分析提醒，详细信息请到排产历史查看。"
    if item.get("message_truncated"):
        text = f"{text}（已截断）"
    return text


def _formatted_samples(values: Sequence[Any], formatter: Any) -> List[str]:
    out: List[str] = []
    for value in values:
        text = str(formatter(value) or "").strip()
        if text:
            out.append(text)
        if len(out) >= SAMPLE_LIMIT:
            break
    return out


def _impact_samples(graph_diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    resource_diagnostics = safe_dict(graph_diagnostics.get("resource_matching"))
    return {
        "critical_path": sample_text_values(graph_diagnostics.get("critical_path_sample")),
        "node_metrics": _formatted_samples(safe_list(graph_diagnostics.get("node_metrics_sample")), _format_node_metric_sample),
        "graph_score": _formatted_samples(safe_list(graph_diagnostics.get("graph_score_sample")), _format_graph_score_sample),
        "warnings": _formatted_samples(safe_list(graph_diagnostics.get("warnings_sample")), _format_warning_sample),
        "unmatched": sample_text_values(resource_diagnostics.get("unmatched_operation_ids_sample")),
        "bottlenecks": sample_text_values(resource_diagnostics.get("bottleneck_machine_ids_sample")),
        "node_metrics_status": str(graph_diagnostics.get("node_metrics_status") or ""),
    }


def _has_impact_samples(samples: Dict[str, Any]) -> bool:
    return any(
        [
            samples["critical_path"],
            samples["node_metrics"],
            samples["graph_score"],
            samples["warnings"],
            samples["unmatched"],
            samples["bottlenecks"],
        ]
    )


def _node_metrics_item(samples: Dict[str, Any], sample_note: str) -> Dict[str, Any]:
    if samples["node_metrics_status"] == "skipped_basic_report":
        return build_item(
            key="node_metrics_status",
            label="影响范围指标",
            value="未生成",
            level="notice",
            message="本次未生成完整影响范围指标，只展示重点工序和设备安排样本。",
        )
    node_metric_samples = samples["node_metrics"]
    return build_item(
        key="node_metrics_sample",
        label="影响范围样本",
        value=format_count(len(node_metric_samples), "条"),
        level="notice" if node_metric_samples else "ok",
        message=sample_note,
        details=node_metric_samples,
    )


def _resource_sample_details(samples: Dict[str, Any]) -> List[str]:
    details: List[str] = []
    if samples["unmatched"]:
        details.append(f"这轮还没排上的工序样本：{'、'.join(samples['unmatched'])}")
    if samples["bottlenecks"]:
        details.append(f"可能不够用的设备样本：{'、'.join(samples['bottlenecks'])}")
    return details


def _impact_items(samples: Dict[str, Any], sample_note: str) -> List[Dict[str, Any]]:
    graph_score_samples = samples["graph_score"]
    resource_details = _resource_sample_details(samples)
    warning_samples = samples["warnings"]
    items = [
        build_item(
            key="critical_path_sample",
            label="重点工序样本",
            value=format_count(len(samples["critical_path"]), "条"),
            level="notice" if samples["critical_path"] else "ok",
            message=sample_note,
            details=samples["critical_path"],
        ),
        _node_metrics_item(samples, sample_note),
    ]
    if graph_score_samples:
        items.append(
            build_item(
                key="graph_score_sample",
                label="排法参考样本",
                value=format_count(len(graph_score_samples), "条"),
                level="notice",
                message="这里只展示部分系统参考信息，不代表完整排序清单。",
                details=graph_score_samples,
            )
        )
    items.extend(
        [
            build_item(
                key="resource_samples",
                label="资源异常样本",
                value=format_count(len(resource_details), "类"),
                level="warning" if resource_details else "ok",
                message=sample_note if resource_details else "暂未看到资源异常样本。",
                details=resource_details,
            ),
            build_item(
                key="warnings_sample",
                label="图分析提醒样本",
                value=format_count(len(warning_samples), "条"),
                level="warning" if warning_samples else "ok",
                message=sample_note if warning_samples else "暂未看到图分析提醒样本。",
                details=warning_samples,
            ),
        ]
    )
    return items


def _impact_status(graph_public: Dict[str, Any], items: Sequence[Dict[str, Any]]) -> str:
    status = section_status_from_levels([str(item.get("level") or "") for item in items])
    if status == "ok" and safe_int(graph_public.get("critical_path_minutes")) > 0:
        return "notice"
    return status


def build_impact_explanation_section(
    graph_public: Dict[str, Any],
    graph_diagnostics: Dict[str, Any],
) -> Dict[str, Any]:
    sample_note = "以下只是样本，不是完整清单。"
    samples = _impact_samples(graph_diagnostics)
    if not _has_impact_samples(samples):
        return build_section(
            key="impact_explanation",
            title="影响解释",
            status="unknown",
            status_label=status_label("unknown"),
            summary="本次缺少可展示的影响解释样本。",
            empty_reason="本次未记录可展示的影响解释样本。",
        )

    items = _impact_items(samples, sample_note)
    status = _impact_status(graph_public, items)
    return build_section(
        key="impact_explanation",
        title="影响解释",
        status=status,
        status_label=status_label(status),
        summary="以下只展示本次诊断采样，不是完整清单。",
        items=items,
    )


__all__ = [
    "build_delay_risk_section",
    "build_impact_explanation_section",
]
