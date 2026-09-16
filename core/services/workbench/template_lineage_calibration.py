"""One evaluation per instance and one sample group per exact template identity."""

from collections import defaultdict

from core.models.workbench_calibration import CalibrationCandidate, issue
from core.models.workbench_command import input_fingerprint

from .calibration_method import build_suggestion, summarize_samples
from .calibration_samples import review_sample


def project_lineage_calibration(templates, instances, projections, lineage, *, as_of):
    by_ref = {row.operation_ref: row for row in templates}
    samples_by_part, samples_by_template, unbound = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in instances:
        ref = row["operation_ref"]
        origin = lineage["lineages"].get(ref)
        template = by_ref.get(origin.template_operation_ref) if origin else None
        candidate = CalibrationCandidate(projections[ref], row["part_no"], row["batch_id"], row["op_code"], row["source"], origin)
        sample = review_sample(candidate, template=template, as_of=as_of)
        problems = lineage["problems"].get(ref, [])
        sample["exclusion_reasons"].extend(problems)
        sample["eligible"] = sample["eligible"] and not problems
        if origin:
            sample["sample_revision"] = input_fingerprint({"execution": sample["sample_revision"],
                "origin": lineage["origins"][ref]["instance_fingerprint"], "events": [event["event_id"] for event in lineage["events"][ref]]})
            samples_by_template[origin.template_operation_ref].append(sample)
        else:
            unbound[row["part_no"]].append(sample)
        samples_by_part[row["part_no"]].append(sample)
    unbound_summaries = {key: summarize_samples(values) for key, values in unbound.items()}
    empty = summarize_samples([])
    rows = []
    for template in templates:
        summary = summarize_samples(samples_by_template[template.operation_ref])
        missing = unbound_summaries.get(template.part_no, empty)
        summary["candidate_count"] += missing["candidate_count"]
        summary["excluded_count"] += missing["excluded_count"]
        summary["exclusion_reasons"] += missing["exclusion_reasons"]
        rows.append(build_suggestion(template, summary, generated_at=as_of.isoformat(timespec="seconds")))
    unbound_count = sum(map(len, unbound.values()))
    constraints = ([issue("template_lineage_missing", "部分完工记录未关联工艺模板，未参与校准。")]
                   if unbound_count else [])
    return {"rows": rows, "samples_by_part": dict(samples_by_part), "samples_by_template": dict(samples_by_template),
            "unbound_samples_by_part": dict(unbound), "unbound_instance_count": unbound_count,
            "source_constraints": constraints, "lineage_available": lineage["available"]}
