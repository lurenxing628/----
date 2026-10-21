"""Business facts available in the admission's assembled official arrangement."""


from core.services.workbench.facts.decision_metrics import project_official_core_metrics


def official_reference_metrics(source, *, metric_keys=None):
    if not source.official_changed:
        raw_metrics = source.official["core_metrics"] if metric_keys is None else {
            key: value for key, value in source.official["core_metrics"].items() if key in metric_keys}
        return source.memberships.expand(raw_metrics), source.memberships.expand(source.official["coverage"])
    return project_official_core_metrics(source.analysis_tasks("reference"), source.scope["operation_refs"],
        source.reference_deferred_refs, source.baseline["state"] == "available",
        source.completion.delivery("reference"), metric_keys=metric_keys)
