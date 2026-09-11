"""Real factory method matrix; each negative POST starts from the same private DB."""

import argparse
import io
import json
import sqlite3
import traceback
import zipfile
from pathlib import Path

from factory_runtime import FactoryCase

VALUES = {"machine_id": "M-BASE", "operator_id": "O-BASE", "part_no": "P-HOURS", "op_type_id": "OT-IN",
          "supplier_id": "S-BASE", "batch_id": "CAT-B", "id": 1, "op_id": 1, "seq": 5, "team_id": "missing",
          "date": "2026-09-09", "filename": "missing.zip", "backup_name": "missing.zip", "preset_name": "missing"}


def old_rules(app):
    return sorted((rule for rule in app.url_map.iter_rules()
                   if rule.endpoint != "static" and not rule.endpoint.startswith("workbench.")),
                  key=lambda rule: (rule.endpoint, rule.rule))


def path_for(app, rule):
    values = {name: VALUES.get(name, 1 if rule._converters[name].__class__.__name__ == "IntegerConverter" else "missing")
              for name in rule.arguments}
    return app.url_map.bind("localhost").build(rule.endpoint, values, method="GET" if "GET" in rule.methods else "POST")


def record(case, label, rule, method, response):
    row = case.save_response(label, response)
    row.update(endpoint=rule.endpoint, rule=rule.rule, method=method)
    if response.is_json:
        row["json"] = response.get_json()
    if response.status_code == 200 and "attachment" in response.headers.get("Content-Disposition", ""):
        payload = response.get_data()
        if zipfile.is_zipfile(io.BytesIO(payload)):
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                assert archive.testzip() is None
            row["zip_integrity"] = "passed"
    return row


def get_matrix(case, rules, policies):
    output = []
    for number, rule in enumerate(rule for rule in rules if "GET" in rule.methods):
        path = path_for(case.app, rule)
        first = case.client.get(path)
        row = record(case, "get-" + str(number), rule, "GET", first)
        if case.candidate and rule.endpoint in policies:
            row["page_policy"] = policies[rule.endpoint]
            html = first.get_data(as_text=True)
            assert "/static/js/" not in html and "/static/css/" not in html, (rule.endpoint, "Legacy asset in page response")
            assert first.status_code in (200, 302, 400, 404, 410), (rule.endpoint, first.status_code)
            if policies[rule.endpoint] == "retired":
                assert first.status_code == 410, (rule.endpoint, "Valid retired page path must not become malformed input")
        head = case.client.head(path)
        row["head_status"] = head.status_code
        row["head_bytes"] = len(head.get_data())
        assert head.status_code == first.status_code and head.get_data() == b"", (rule.endpoint, first.status_code, head.status_code)
        first.close()
        head.close()
        output.append(row)
    return output


def clone_db(source, destination):
    with sqlite3.connect(str(source)) as left, sqlite3.connect(str(destination)) as right:
        left.backup(right)
    left.close()
    right.close()


def post_matrix(case, rules):
    seed = case.root / "negative-post-seed.db"
    clone_db(case.path, seed)
    output = []
    for number, rule in enumerate(rule for rule in rules if "POST" in rule.methods):
        clone_db(seed, case.path)
        with case.client.session_transaction() as session:
            session.clear()
        response = case.client.post(path_for(case.app, rule), data={})
        row = record(case, "post-empty-" + str(number), rule, "POST", response)
        row["input_scope"] = "empty original form; real negative-input handling, not full command acceptance"
        row["function_identity_preserved"] = case.app.view_functions[rule.endpoint] is case.original[rule.endpoint]
        assert row["function_identity_preserved"]
        output.append(row)
        response.close()
    return output


def run(case):
    from tests.workbench.plan_read_support import seed_plans
    from web.routes.workbench.legacy_page_contract import PAGE_POLICIES
    with case.db() as conn:
        seed_plans(conn)
    rules = old_rules(case.app)
    pages = [rule for rule in rules if "GET" in rule.methods and rule.endpoint in PAGE_POLICIES]
    nonpages = [rule for rule in rules if "GET" in rule.methods and rule.endpoint not in PAGE_POLICIES]
    posts = [rule for rule in rules if "POST" in rule.methods]
    assert (len(pages), len(nonpages), len(posts)) == (51, 39, 113)
    untouched = all(case.app.view_functions[rule.endpoint] is case.original[rule.endpoint] for rule in nonpages + posts)
    assert untouched
    before = case.business_state()
    gets = get_matrix(case, rules, PAGE_POLICIES)
    after_get = case.business_state()
    results = post_matrix(case, rules)
    return {"passed": True, "counts": {"pages_get_and_head": len(pages), "nonpage_get_and_head": len(nonpages), "posts": len(posts)},
            "untouched_post_and_nonpage_functions": untouched, "get_business_state_equal": before == after_get,
            "gets": gets, "posts": results, "post_scope": "113 real empty-form negative requests; full transactions separately cover 24 import POSTs"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("--candidate", action="store_true")
    args = parser.parse_args()
    case = FactoryCase(args.source, args.runtime, candidate=args.candidate)
    try:
        result = run(case)
    except Exception as exc:
        result = {"passed": False, "error": str(exc), "traceback": traceback.format_exc()}
    case.write_result(result)
    print(json.dumps({"passed": result["passed"], "error": result.get("error"), "runtime": str(case.root)}, ensure_ascii=False), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
