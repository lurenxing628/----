"""Data-driven final navigation cases; preparation is not a browser PASS."""

import hashlib
import json
from copy import deepcopy
from urllib.parse import urlencode

VIEWS = ("gantt", "analysis", "delay")
TRANSITIONS = ("direct_url", "copy_url_new_tab", "same_tab_f5", "same_tab_same_port_new_host_pid")
MATRIX = ("1392x924-light", "1392x924-dark", "1920x1080-light", "1920x1080-dark")
GROUPS = {"legacy": {"first_view": 56, "interaction": 16, "fault": 16, "host_restart": 4},
          "canonical": {"canonical_navigation": 212}, "boot": {"boot_contract_fault": 40}}


def execution_plan(groups):
    groups = tuple(groups)
    if groups == ("all",):
        groups = tuple(GROUPS)
    if not groups or len(set(groups)) != len(groups) or set(groups) - set(GROUPS):
        raise ValueError("Groups must be unique legacy,canonical,boot or all")
    counts = {kind: count for name in groups for kind, count in GROUPS[name].items()}
    return {"groups": list(groups), "case_kinds": counts, "total_cases": sum(counts.values()),
            "restart_pages": (4 if "legacy" in groups else 0) + (24 if "canonical" in groups else 0),
            "navigation_seed": "canonical" in groups,
            "browser_timeout_seconds": 1800 if "canonical" in groups else 1200 if "boot" in groups else 600}


def _target(view, context):
    payload = {"version": 1, "view": view, "context": deepcopy(context)}
    pairs = [] if view == "trial" else [("view", view)]
    pairs.append(("nav", json.dumps(payload, ensure_ascii=False, separators=(",", ":"))))
    path = "/workbench/trial" if view == "trial" else "/workbench"
    return {"view": view, "path": path, "query_pairs": pairs, "url_suffix": path + "?" + urlencode(pairs), "payload": payload}


def _valid(name, view, context, dto, caption):
    return {"id": name, "group": "canonical-positive", "status": "planned_not_executed",
            **_target(view, context), "transitions": list(TRANSITIONS), "html_status": 200,
            "dto": dto, "caption": caption,
            "checks": ["server boot.navigation equals parsed URL object", "real workspace consumes the original context",
                       "no history writes, product hooks, fake API responses, or default-plan substitution",
                       "save original/copied page and browser context identities across host restart"]}


def _bad(name, path, pairs):
    return {"id": name, "group": "canonical-http400", "status": "planned_not_executed", "path": path,
            "query_pairs": pairs, "url_suffix": path + "?" + urlencode(pairs), "html_status": 400,
            "checks": ["no workbench-boot script or domain success DTO", "new-style offline alert page",
                       "visible recovery navigation", "actual open-workbench link recovers to Main",
                       "record expected HTTP errors separately from normal business reads"]}


def build_navigation_cases(prepared):
    if prepared.get("kind") != "navigation_condition_preparation" or prepared.get("created_before_business_baseline") is not True:
        raise ValueError("Navigation cases require actual pre-baseline service evidence")
    workspace, draft = prepared["workspace"], prepared["draft"]
    plan, scope = workspace["plan"], prepared["input"]["scope"]
    if prepared["receipt"]["data"]["draft_ref"] != draft["draft_ref"] or draft["base"] != {"plan_ref": plan["plan_ref"]}:
        raise ValueError("Case references must come from the real preparation receipt")
    context = {"plan_ref": plan["plan_ref"], **scope}
    caption = {"reference": plan["plan_ref"], "name": plan["display_name"], "kind": plan["kind"],
               "version": plan["version"], "is_current_official": plan["is_current_official"], "range": scope}
    cases = [_valid(view + "-explicit-plan-range", view, context,
                    {"method": "GET", "path": "/api/workbench/v1/plans/" + plan["plan_ref"] + "/workspace",
                     "request_query": scope, "response_fields": {"data.plan.plan_ref": plan["plan_ref"],
                     "data.scope.plan_ref": plan["plan_ref"], "data.scope.range_start": scope["range_start"],
                     "data.scope.range_end": scope["range_end"]}}, caption) for view in VIEWS]
    task = workspace["tasks"][0]
    batch = next(row for row in workspace["projections"]["delivery_risks"]["items"] if row["batch_id"] == task["batch_id"])
    report_scope = {"source": "production", "plan_ref": plan["plan_ref"], "batch_ref": batch["batch_ref"],
                    "plan_finish_date_from": scope["range_start"][:10], "plan_finish_date_to": scope["range_end"][:10],
                    "query": task["batch_id"], "focus": "all"}
    cases.append(_valid("reports-explicit-plan-cohort", "reports", {"scope": report_scope, "topic": "records", "catalogOpen": False},
                        {"method": "GET", "path": "/api/workbench/v1/analytics", "request_query": {**report_scope, "topic": "records"},
                         "response_scope": report_scope, "response_fields": {"data.plan.plan_ref": plan["plan_ref"], "data.topic": "records"}},
                        {**caption, "range": {key: report_scope[key] for key in ("plan_finish_date_from", "plan_finish_date_to")}}))
    cases.append(_valid("trial-base-scope-preview", "trial", prepared["input"],
                        {"method": "POST", "path": "/api/workbench/v1/trial/drafts/preview", "trigger": "click real 核对原来源",
                         "request_json": prepared["input"], "response_fields": {"data.base": prepared["input"]["base"],
                         "data.scope": scope, "data.tasks_complete": True, "data.task_count": workspace["task_count"]}},
                        {"applicable": False, "reason": "Base preview is not an existing draft; never claim a fabricated draft caption",
                         "check": "no invented draft identity; preview does not satisfy the existing-draft caption case"}))
    cases.append(_valid("trial-existing-real-draft", "trial", {"draft_ref": draft["draft_ref"]},
                        {"method": "GET", "path": "/api/workbench/v1/trial/drafts/" + draft["draft_ref"],
                         "response_fields": {"data.draft_ref": draft["draft_ref"], "data.base": draft["base"],
                         "data.scope": draft["scope"], "data.tasks_complete": True, "data.task_count": draft["task_count"]}},
                        {"reference": draft["draft_ref"], "name_from": "data.name or real data.base_identity.display_name + version",
                         "identity": "draft", "status": draft["status"], "baseline": draft["baseline"], "range": draft["time_scope"]}))
    target = _target("gantt", context)
    pairs = target["query_pairs"]
    cases.extend([
        _bad("duplicate-nav-identical", target["path"], pairs + [pairs[-1]]),
        _bad("duplicate-view-identical", target["path"], pairs + [("view", "gantt")]),
        _bad("duplicate-view-different", target["path"], pairs + [("view", "analysis")]),
        _bad("empty-nav", target["path"], [("view", "gantt"), ("nav", "")]),
        _bad("malformed-nav-json", target["path"], [("view", "gantt"), ("nav", "{")]),
    ])
    invalid_contexts = [
        ("plan-unknown-scope", "gantt", {**context, "scope": {"all": True}}),
        ("plan-unsupported-query", "analysis", {**context, "query": task["batch_id"]}),
        ("plan-short-ref", "gantt", {**context, "plan_ref": "invalid-short-ref"}),
        ("plan-uppercase-ref", "delay", {**context, "plan_ref": "A" + plan["plan_ref"][1:]}),
        ("plan-half-range", "delay", {"plan_ref": plan["plan_ref"], "range_start": scope["range_start"]}),
        ("plan-reversed-range", "analysis", {"plan_ref": plan["plan_ref"], "range_start": scope["range_end"], "range_end": scope["range_start"]}),
        ("plan-ephemeral-url-token", "gantt", {**context, "snapshot_ref": "not-a-durable-navigation-field"}),
        ("reports-unknown-scope", "reports", {"scope": {**report_scope, "date_from": scope["range_start"][:10]}}),
        ("reports-empty-scope", "reports", {"scope": {}}),
        ("reports-wrong-ref-format", "reports", {"scope": {**report_scope, "plan_ref": "invalid-short-ref"}}),
        ("trial-mixed-base", "trial", {"base": {"plan_ref": plan["plan_ref"], "candidate_ref": plan["plan_ref"]}}),
        ("trial-unknown-scope", "trial", {"base": {"plan_ref": plan["plan_ref"]}, "scope": {"unknown": True}}),
    ]
    for name, view, value in invalid_contexts:
        invalid = _target(view, value)
        cases.append(_bad(name, invalid["path"], invalid["query_pairs"]))
    for name, payload in (("nav-view-mismatch", {**target["payload"], "view": "analysis"}),
                          ("nav-unknown-outer-field", {**target["payload"], "extra": True})):
        cases.append(_bad(name, target["path"], [("view", "gantt"), ("nav", json.dumps(payload))]))
    duplicate = '{"version":1,"view":"gantt","context":{"plan_ref":"' + plan["plan_ref"] + '","plan_ref":"' + plan["plan_ref"] + '"}}'
    cases.append(_bad("duplicate-json-context-key", target["path"], [("view", "gantt"), ("nav", duplicate)]))
    for name, extra in (("legacy-version-no-nav", [("version", str(plan["version"]))]),
                        ("legacy-role-no-nav", [("plan_role", "adopted")]),
                        ("legacy-identity-no-nav", [("version", str(plan["version"])), ("plan_role", "adopted")])):
        cases.append(_bad(name, "/workbench", [("view", "gantt")] + extra))
    cases.append(_bad("trial-path-view-mismatch-no-nav", "/workbench/trial", [("view", "reports")]))
    unknown = hashlib.sha256(("foundation-navigation-unknown:" + plan["plan_ref"]).encode("ascii")).hexdigest()[:48]
    for view in VIEWS + ("reports", "trial"):
        value = {"plan_ref": unknown, **scope} if view in VIEWS else {"scope": {**report_scope, "plan_ref": unknown}} if view == "reports" else {"base": {"plan_ref": unknown}, "scope": scope}
        cases.append({"id": view + "-unknown-well-formed-ref", "group": "canonical-domain-failure", "status": "planned_not_executed",
                      **_target(view, value), "html_status": 200, "domain_status": 404,
                      "domain_error_code": "entity_not_found", "missing_ref": unknown,
                      "precondition": "Before using this derived ref, verify an actual missing-object response in this new private fixture",
                      "checks": ["boot retains the exact explicit unknown reference", "real domain request carries that reference",
                                 "no 200 plan DTO for another plan and no fabricated caption", "real retry retains the failed object"],
                      "trigger": "click real 核对原来源" if view == "trial" else "initial domain read"})
    return {"schema_version": 1, "status": "prepared_not_live_verified", "groups": ["canonical-positive", "canonical-http400", "canonical-domain-failure"],
            "matrix": list(MATRIX), "source": {"kind": prepared["kind"], "root": prepared["root"],
            "plan_ref": plan["plan_ref"], "draft_ref": draft["draft_ref"], "receipt_ref": prepared["receipt"]["receipt_ref"]},
            "cases": cases, "writes_after_baseline": "none; POST trial preview is a read, never commit another draft",
            "execution_gate": "Use Main/F authorized frozen full-source snapshot and matching full build; historical 92 remains separate",
            "restart_policy": "Keep each tested original page alive. Never clear history or rewrite URL to hide stale context; report initial failure and any explicit recovery separately."}
