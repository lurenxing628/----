"""One evaluation per instance and one sample group per exact template identity."""

from collections import defaultdict
from fractions import Fraction
from typing import Dict

from core.models.workbench_calibration import CalibrationCandidate, issue

from .method import build_suggestion, summarize_samples
from .samples import review_sample


def _merge_exclusion_reasons(first, second):
    counts, messages = defaultdict(int), {}
    for row in first + second:
        code = row["code"]
        counts[code] += row["count"]
        messages[code] = row["message"]
    return [{"code": code, "message": messages[code], "count": count} for code, count in sorted(counts.items())]


def project_lineage_calibration(
    templates,
    instances,
    projections,
    lineage,
    *,
    as_of,
):
    by_ref = {row.operation_ref: row for row in templates}
    samples_by_template, unbound = defaultdict(list), defaultdict(list)
    exact_unit_hours: Dict[str, Fraction] = {}
    for row in instances:
        ref = row["operation_ref"]
        origin = lineage["lineages"].get(ref)
        template = by_ref.get(origin.template_operation_ref) if origin else None
        candidate = CalibrationCandidate(projections[ref], row["part_no"], row["batch_id"], row["op_code"], row["source"], origin)
        sample, exact_ratio = review_sample(
            candidate,
            template=template,
            as_of=as_of,
            lineage_origin=lineage["origins"].get(ref),
            lineage_events=lineage["events"].get(ref, ()),
        )
        problems = lineage["problems"].get(ref, [])
        sample["exclusion_reasons"].extend(problems)
        sample["eligible"] = sample["eligible"] and not problems
        if exact_ratio is not None and not problems:
            exact_unit_hours[sample["sample_ref"]] = exact_ratio
        if origin:
            samples_by_template[origin.template_operation_ref].append(sample)
        else:
            unbound[row["part_no"]].append(sample)
    unbound_summaries = {key: summarize_samples(values, exact_unit_hours) for key, values in unbound.items()}
    empty = summarize_samples([], exact_unit_hours)
    rows = []
    generated_at = as_of.isoformat(timespec="seconds")
    for template in templates:
        template_samples = samples_by_template[template.operation_ref]
        summary = summarize_samples(template_samples, exact_unit_hours)
        missing = unbound_summaries.get(template.part_no, empty)
        summary.public["candidate_count"] += missing.public["candidate_count"]
        summary.public["excluded_count"] += missing.public["excluded_count"]
        if missing.public["exclusion_reasons"]:
            summary.public["exclusion_reasons"] = _merge_exclusion_reasons(
                summary.public["exclusion_reasons"], missing.public["exclusion_reasons"]
            )
        rows.append(build_suggestion(template, summary, generated_at=generated_at))
    unbound_count = sum(map(len, unbound.values()))
    constraints = ([issue("template_lineage_missing", "部分完工记录未关联工艺模板，未参与校准。")]
                   if unbound_count else [])
    return {"rows": rows, "samples_by_template": dict(samples_by_template),
            "unbound_samples_by_part": dict(unbound), "unbound_instance_count": unbound_count,
            "source_constraints": constraints, "lineage_available": lineage["available"]}
