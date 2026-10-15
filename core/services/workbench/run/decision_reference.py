"""Business facts available in the admission's assembled official arrangement."""


from core.services.workbench.facts.decision_metrics import project_official_core_metrics


def reference_delivery(source):
    return source.completion.delivery("reference")


def official_reference_metrics(source, *, metric_keys=None):
    if not source.official_changed:
        values = source.memberships.expand(source.official["core_metrics"])
        if metric_keys is not None:
            values = {key: value for key, value in values.items() if key in metric_keys}
        return values, source.memberships.expand(source.official["coverage"])
    return project_official_core_metrics(source.analysis_tasks("reference"), source.scope["operation_refs"],
        source.reference_deferred_refs, source.baseline["state"] == "available", reference_delivery(source), metric_keys=metric_keys)
