"""Execute one real XLSX owner through a bound factory, without route/service mocks."""

import argparse
import io
import json
import traceback
import zipfile
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from factory_runtime import FactoryCase
from import_cases import CASES


class Fields(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values, self.textarea = {}, None
        self.active = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form":
            self.active = urlsplit(values.get("action", "")).path.endswith("/confirm")
        if not self.active:
            return
        name = values.get("name")
        if tag == "input" and name and values.get("type") == "hidden":
            self.values[name] = values.get("value", "")
        elif tag == "textarea" and name:
            self.textarea = name
            self.values[name] = ""

    def handle_data(self, data):
        if self.textarea:
            self.values[self.textarea] += data

    def handle_endtag(self, tag):
        if tag == "textarea":
            self.textarea = None
        elif tag == "form":
            self.active = False


def preview(case, spec, label, rows=None):
    from core.services.common.excel_templates import build_xlsx_bytes, get_template_definition
    headers = get_template_definition(spec["template"])["headers"]
    workbook = build_xlsx_bytes(headers, rows or [spec["row"]])
    data = workbook.getvalue()
    (case.root / (label + ".xlsx")).write_bytes(data)
    values = {"mode": spec.get("mode", "append"), **spec.get("extra", {}),
              "file": (io.BytesIO(data), spec["template"])}
    response = case.client.post(spec["prefix"] + "/preview", data=values, content_type="multipart/form-data")
    case.save_response(label, response)
    return response


def extract(response):
    parser = Fields()
    parser.feed(response.get_data(as_text=True))
    return parser.values


def assert_saved(case, spec):
    with case.db() as conn:
        row = conn.execute(spec["sql"]).fetchone()
        assert row is not None and list(row) == spec["expected"], (dict(row) if row else None, spec["expected"])
        assert list(conn.execute("PRAGMA foreign_key_check")) == []
    return list(row)


def follow_result(case, response, expected_messages):
    chain, last_url = [], None
    for index in range(5):
        if response.status_code not in (301, 302, 303, 307, 308):
            break
        last_url = response.headers["Location"]
        assert last_url.startswith("/") and not last_url.startswith("//"), last_url
        response = case.client.get(last_url)
        chain.append(case.save_response("after-confirm-" + str(index), response))
    body = response.get_data(as_text=True)
    assert all(message in body for _category, message in expected_messages), expected_messages
    if last_url:
        refreshed = case.client.get(last_url)
        case.save_response("after-confirm-refresh", refreshed)
        fresh_html = refreshed.get_data(as_text=True)
        assert all(message not in fresh_html for _category, message in expected_messages), "Old success message replayed on refresh"
        refreshed.close()
    return chain


def check_files(case, spec):
    import openpyxl
    routes = {rule.rule for rule in case.app.url_map.iter_rules() if "GET" in rule.methods}
    results = []
    for suffix in ("template", "export"):
        url = spec["prefix"] + "/" + suffix
        if url not in routes:
            continue
        response = case.client.get(url)
        info = case.save_response(suffix, response)
        assert response.status_code == 200 and "attachment" in response.headers.get("Content-Disposition", ""), info
        data = response.get_data()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert archive.testzip() is None
        workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        try:
            sheet = workbook.active
            rows = [list(row) for row in sheet.iter_rows(values_only=True)]
        finally:
            workbook.close()
        assert rows and rows[0]
        if suffix == "template":
            assert data == (Path(case.app.config["EXCEL_TEMPLATE_DIR"]) / spec["template"]).read_bytes()
            info["equals_factory_template_bytes"] = True
        else:
            key = spec["row"][0]
            cells = [cell.isoformat()[:10] if isinstance(cell, (date, datetime)) else cell for row in rows[1:] for cell in row]
            assert key in cells, "Confirmed business record missing from actual export"
            info["confirmed_record_in_export"] = True
        info["workbook_rows"] = rows
        results.append(info)
        response.close()
    return results


def run_import(case, spec):
    before = case.business_state()
    first = preview(case, spec, "preview")
    assert first.status_code == 200, case.responses[-1]
    fields = extract(first)
    assert fields.get("raw_rows_json") and fields.get("preview_baseline"), "Valid real preview did not expose original confirmation payload"
    assert fields["mode"] == spec.get("mode", "append")
    assert fields["filename"] == spec["template"]
    for name, value in spec.get("extra", {}).items():
        assert fields.get(name) == value, (name, fields.get(name), value)
    assert case.business_state() == before, "Preview changed business data"
    repeat = preview(case, spec, "preview-refresh")
    assert extract(repeat) == fields, "Preview refresh changed its baseline or opaque payload"
    assert case.business_state() == before
    invalid_row = list(spec["row"])
    invalid_row[0] = ""
    invalid_preview = preview(case, spec, "preview-invalid-row", [invalid_row])
    assert invalid_preview.status_code in (200, 400, 422), case.responses[-1]
    assert case.business_state() == before, "Invalid preview changed business data"
    if case.candidate:
        assert not extract(invalid_preview).get("raw_rows_json"), "Invalid rows must not expose an enabled confirmation form"
    bad = case.client.post(spec["prefix"] + "/confirm", data={**fields, "preview_baseline": "stale"})
    case.save_response("confirm-stale", bad)
    assert bad.status_code in (200, 400, 409), case.responses[-1]
    assert "重新" in bad.get_data(as_text=True)
    assert case.business_state() == before, "Rejected baseline changed business data"
    malformed = case.client.post(spec["prefix"] + "/confirm", data={**fields, "raw_rows_json": "not-a-payload"})
    case.save_response("confirm-malformed", malformed)
    assert malformed.status_code in (400, 422), case.responses[-1]
    assert case.business_state() == before
    # Clear messages already consumed by rejected responses, not success state.
    response = case.client.post(spec["prefix"] + "/confirm", data=fields)
    case.save_response("confirm", response)
    assert response.status_code in (200, 302, 303), case.responses[-1]
    saved = assert_saved(case, spec)
    with case.client.session_transaction() as session:
        messages = list(session.get("_flashes", ()))
    if response.status_code in (302, 303):
        assert messages, "Successful original redirect has no result message"
    chain = follow_result(case, response, messages)
    assert_saved(case, spec)
    after = case.business_state()
    replay = case.client.post(spec["prefix"] + "/confirm", data=fields)
    case.save_response("confirm-replay", replay)
    assert replay.status_code in (200, 400, 409), case.responses[-1]
    assert case.business_state() == after, "Old confirmation replay changed business data"
    files = check_files(case, spec)
    return {"passed": True, "stored_row": saved, "preview_no_business_write": True,
            "refresh_payload_equal": True, "stale_rejected_no_business_write": True,
            "malformed_rejected_no_business_write": True, "confirm_persisted_after_reopen": True,
            "invalid_rows_rejected_no_business_write": True,
            "confirmation_replay_no_business_write": True, "messages": messages, "redirect_chain": chain,
            "files": files, "business_state_excludes": ["OperationLogs", "SystemJobState", "sqlite_sequence"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("case", choices=tuple(CASES))
    parser.add_argument("--candidate", action="store_true")
    args = parser.parse_args()
    fixture = FactoryCase(args.source, args.runtime, candidate=args.candidate)
    try:
        result = run_import(fixture, CASES[args.case])
    except Exception as exc:
        result = {"passed": False, "error": str(exc), "traceback": traceback.format_exc()}
    fixture.write_result({"case": args.case, **result})
    print(json.dumps({"case": args.case, "passed": result["passed"], "runtime": str(fixture.root), "error": result.get("error")}, ensure_ascii=False), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
