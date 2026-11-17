"""One evaluation per instance and one sample group per exact template identity."""

from collections import defaultdict
from fractions import Fraction
from typing import Dict

from core.models.workbench_calibration import CalibrationCandidate, CalibrationLineage, issue
from core.services.scheduler.template_lineage_query import lineage_problems

from .method import build_suggestion, summarize_samples
from .samples import ensure_sample_revision, review_sample, review_state_sample, template_snapshot_text


def _merge_exclusion_reasons(first, second):
    counts, messages = defaultdict(int), {}
    for row in first + second:
        code = row["code"]
        counts[code] += row["count"]
        messages[code] = row["message"]
    return [{"code": code, "message": messages[code], "count": count} for code, count in sorted(counts.items())]


def _build_template_rows(templates, samples_by_template, unbound, exact_unit_hours, *, as_of):
    unbound_summaries = {key: summarize_samples(values, exact_unit_hours) for key, values in unbound.items()}
    empty = summarize_samples([], exact_unit_hours)
    rows = []
    generated_at = as_of.isoformat(timespec="seconds")
    for template in templates:
        template_samples = samples_by_template.get(template.operation_ref, [])
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
    constraints = (
        [issue("template_lineage_missing", "部分完工记录未关联工艺模板，未参与校准。")]
        if unbound_count
        else []
    )
    return rows, unbound_count, constraints


def project_state_calibration(templates, instances, *, as_of):
    by_ref = {row.operation_ref: row for row in templates}
    samples_by_template, unbound = defaultdict(list), defaultdict(list)
    samples_by_ref = {}
    exact_unit_hours: Dict[str, Fraction] = {}
    for row in instances:
        template = by_ref.get(row["template_operation_ref"]) if row["lineage_ref"] is not None else None
        sample, exact_ratio = review_state_sample(row, template=template, as_of=as_of)
        samples_by_ref[sample["sample_ref"]] = sample
        if exact_ratio is not None:
            exact_unit_hours[sample["sample_ref"]] = exact_ratio
        if row["lineage_ref"] is not None:
            samples_by_template[row["template_operation_ref"]].append(sample)
        else:
            unbound[row["part_no"]].append(sample)
    rows, unbound_count, constraints = _build_template_rows(
        templates, samples_by_template, unbound, exact_unit_hours, as_of=as_of
    )
    return {
        "rows": rows,
        "samples_by_ref": samples_by_ref,
        "unbound_instance_count": unbound_count,
        "source_constraints": constraints,
        "lineage_available": True,
    }


def project_single_template_calibration(template, instances, projections, *, as_of):
    linked, unbound = [], []
    exact_unit_hours: Dict[str, Fraction] = {}
    for row in instances:
        ref = row["operation_ref"]
        has_lineage = row["lineage_ref"] is not None
        origin = (
            CalibrationLineage(row["template_operation_ref"], row["template_revision"], row["lineage_ref"])
            if has_lineage
            else None
        )
        problems = (
            lineage_problems(
                source_eligible=bool(row["source_eligible"]),
                operation_active=bool(row["identity_active"]),
                instance_modified=bool(row["instance_modified"]),
            )
            if has_lineage
            else []
        )
        candidate = CalibrationCandidate(
            projections[ref],
            row["part_no"],
            row["batch_id"],
            row["op_code"],
            row["source"],
            origin,
        )
        sample, exact_ratio = review_sample(
            candidate,
            template=template if (origin and origin.template_operation_ref == template.operation_ref) else None,
            as_of=as_of,
            lineage_origin=row if has_lineage else None,
            problems=problems,
        )
        if exact_ratio is not None:
            exact_unit_hours[sample["sample_ref"]] = exact_ratio
        if has_lineage:
            linked.append(sample)
        else:
            unbound.append(sample)
    rows, _, constraints = _build_template_rows(
        [template],
        {template.operation_ref: linked},
        {template.part_no: unbound} if unbound else {},
        exact_unit_hours,
        as_of=as_of,
    )
    row = rows[0]
    linked_by_ref = {sample["sample_ref"]: sample for sample in linked}
    selected_samples = [ensure_sample_revision(linked_by_ref[ref]) for ref in row["sample_refs"]]
    row["template_snapshot"] = template_snapshot_text(template.operation_ref, template.revision)
    row["sample_revisions"] = [
        {
            "sample_ref": sample["sample_ref"],
            "sample_revision": sample["sample_revision"],
            "template_revision": sample["template_revision"],
            "report_revision_refs": sample["report_revision_refs"],
        }
        for sample in selected_samples
    ]
    return {
        "row": row,
        "linked_samples": linked,
        "unbound_samples": unbound,
        "source_constraints": constraints,
        "lineage_available": True,
    }
