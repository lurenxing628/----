"""Use the exact common/split DAG for candidate scoring and real SGS dispatch."""

from core.algorithm_runtime.piece_input import operation_batch
from core.services.scheduler.graph.exporter import graph_summary_to_dict
from core.services.scheduler.graph.input_adapter import build_operation_nodes_from_rows
from core.services.scheduler.graph.metrics import build_node_metrics, get_critical_path, get_topological_generations
from core.services.scheduler.graph.precedence_builder import build_precedence_graph
from core.services.scheduler.graph.types import GraphAnalysisSummary, OperationGraphEdge
from core.services.scheduler.graph.validators import collect_graph_warnings
from core.services.scheduler.run.schedule_graph_dispatch_context import (
    build_graph_health_context,
    build_graph_ready_context,
    graph_input_scope,
)
from core.services.scheduler.run.schedule_graph_report import (
    ScheduleGraphDispatchPreparation,
    _project_graph_analysis_payload,
)
from core.services.scheduler.run.schedule_graph_score_projection import (
    build_available_graph_score_projection,
    graph_score_requested,
    graph_score_weights,
)

from .piece_adoption_scope import build_piece_adoption_scope


def piece_graph_preparer(prepared):
    scope = build_piece_adoption_scope(prepared.operations, prepared.batches)
    nodes = []
    for op in prepared.algo_ops:
        nodes.extend(build_operation_nodes_from_rows([op],
            batches={op.batch_id: operation_batch(op, prepared.batches[op.batch_id])},
            resource_pool=prepared.resource_pool, frozen_op_ids=prepared.frozen_op_ids))
    by_id = {node.raw["id"]: node.node_id for node in nodes}
    edges = [OperationGraphEdge(by_id[previous], by_id[work.op_id], "precedence")
             for work in scope.operations for previous in work.predecessor_op_ids]
    graph = build_precedence_graph(nodes, edges)
    generations = get_topological_generations(graph)
    order = [key for group in generations for key in group]
    critical, minutes = get_critical_path(graph)
    metrics = build_node_metrics(graph, topological_order=order, critical_path=critical,
                                 generation_index={key: index for index, group in enumerate(generations) for key in group})
    payload = graph_summary_to_dict(GraphAnalysisSummary(len(nodes), len(edges), True, [], order,
        critical, minutes, metrics, collect_graph_warnings(graph)))

    def prepare(candidate_input):
        weights = graph_score_weights(candidate_input.cfg)
        score, score_public, score_diagnostics = build_available_graph_score_projection(
            score_weights=weights, nodes=nodes, node_metrics=metrics,
            topological_order=order, schedule_input=candidate_input)
        score["score_enabled"] = graph_score_requested(weights)
        score_public["score_enabled"] = score["score_enabled"]
        context = build_graph_ready_context(candidate_input, nodes=nodes, edges=edges, enabled=True, score_context=score)
        if context is None:
            raise RuntimeError("Complete piece work requires its real dispatch graph.")
        context["piece_scope"] = True
        public, diagnostics = _project_graph_analysis_payload(mode="on", payload=payload, elapsed_ms=0,
            scope=graph_input_scope(candidate_input, nodes=nodes), score_public=score_public,
            score_diagnostics=score_diagnostics)
        return ScheduleGraphDispatchPreparation(public, diagnostics, context, "sgs",
            build_graph_health_context(nodes=nodes, payload=payload, schedule_input=candidate_input))

    return prepare
