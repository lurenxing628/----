"""Current legacy HTTP contracts without restoring retired pages or error forms."""

import io
import json
from contextlib import contextmanager
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import openpyxl
from flask import template_rendered


class LegacyHTML(HTMLParser):
    """Read only the current confirmation form, public notices and workbench boot."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.forms, self.notices, self.field_names, self.boot = [], [], [], []
        self.links = []
        self.legacy_response = False
        self._form, self._textarea, self._notice, self._boot = None, None, None, False
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "main" and attrs.get("data-workbench-legacy-response") == "true":
            self.legacy_response = True
        if tag == "form" and attrs.get("data-legacy-confirmation") == "true":
            assert self._form is None, "Nested confirmation forms are invalid"
            self._form = {"action": attrs.get("action"), "method": attrs.get("method"), "fields": {}}
        if tag in ("input", "textarea") and attrs.get("name"):
            name = attrs["name"]
            self.field_names.append(name)
            if self._form is not None:
                assert name not in self._form["fields"], "Duplicate confirmation field: " + name
                self._form["fields"][name] = attrs.get("value", "") if tag == "input" else ""
                if tag == "textarea":
                    self._textarea = name
        if tag == "p" and "notice" in attrs.get("class", "").split():
            self._notice = [attrs.get("data-level"), []]
        if tag == "script" and attrs.get("id") == "workbench-boot":
            self._boot = True

    def handle_data(self, value):
        if self._textarea is not None and self._form is not None:
            self._form["fields"][self._textarea] += value
        if self._notice is not None:
            self._notice[1].append(value)
        if self._boot:
            self.boot.append(value)

    def handle_endtag(self, tag):
        if tag == "textarea":
            self._textarea = None
        if tag == "form" and self._form is not None:
            self.forms.append(self._form)
            self._form = None
        if tag == "p" and self._notice is not None:
            level, parts = self._notice
            self.notices.append((level, " ".join("".join(parts).split())))
            self._notice = None
        if tag == "script":
            self._boot = False


def confirmation_inputs(html, confirm_path):
    """Return the exact payload of one valid, explicitly confirmable preview."""
    parsed = LegacyHTML(html)
    assert parsed.legacy_response and len(parsed.forms) == 1, "Expected one valid legacy confirmation form"
    form = parsed.forms[0]
    assert form["action"] == confirm_path and form["method"].lower() == "post", form
    fields = form["fields"]
    assert all(fields.get(key) for key in ("mode", "filename", "preview_baseline", "raw_rows_json")), fields
    assert fields["raw_rows_json"].startswith("aps-preview-json-b64:"), "Keep the encoded payload contract"
    return dict(fields)


def notice_messages(html, level):
    """Read categorized notices from the current legacy_base presentation."""
    return [message for category, message in LegacyHTML(html).notices if category == level]


def assert_no_confirmation(html):
    """A rejected preview must not expose a form or a reusable hidden payload."""
    parsed = LegacyHTML(html)
    assert parsed.legacy_response and not parsed.forms
    assert not {"raw_rows_json", "preview_baseline"}.intersection(parsed.field_names)


def assert_retired_response(response, reason=None):
    """Check an explicit retirement response, not merely its status number."""
    html = response.get_data(as_text=True)
    assert response.status_code == 410, html[:500]
    assert response.headers.get("Cache-Control") == "no-store"
    assert "Location" not in response.headers
    assert "旧入口已退役" in html and "原业务数据、保存的配置和历史记录仍保留" in html
    assert_no_confirmation(html)
    assert "Traceback" not in html
    if reason is not None:
        assert reason in html, html
    return html


def follow_legacy_post_redirect(client, response, expected_path):
    """Verify one original POST redirect and then the exact retired GET target."""
    assert response.status_code == 302, response.get_data(as_text=True)[:500]
    location = response.headers["Location"]
    parts = urlsplit(location)
    assert not parts.scheme and not parts.netloc and not parts.fragment and not parts.query
    assert parts.path == expected_path, location
    return assert_retired_response(client.get(location))


def assert_followed_confirmation(response, expected_path):
    """Validate an already-followed POST through its full 302-to-retired-GET chain."""
    assert len(response.history) == 1, response.history
    original = response.history[0]
    assert original.request.method == "POST" and original.request.path == expected_path + "/confirm"
    assert original.status_code == 302 and original.headers["Location"] == expected_path
    assert response.request.method == "GET" and response.request.path == expected_path
    return assert_retired_response(response)


def canonical_navigation(client, response, view):
    """Verify a legacy redirect and canonical boot retain the same explicit scope."""
    assert response.status_code == 302, response.get_data(as_text=True)[:500]
    parts = urlsplit(response.headers["Location"])
    assert not parts.scheme and not parts.netloc and not parts.fragment and parts.path == "/workbench"
    query = parse_qs(parts.query, keep_blank_values=True)
    assert set(query) == {"view", "nav"} and all(len(values) == 1 for values in query.values())
    navigation = json.loads(query["nav"][0])
    assert set(navigation) == {"version", "view", "context"}
    assert navigation["version"] == 1 and navigation["view"] == view and query["view"] == [view]
    page = client.get(response.headers["Location"])
    assert page.status_code == 200, page.get_data(as_text=True)[:500]
    boot = json.loads("".join(LegacyHTML(page.get_data(as_text=True)).boot))
    assert boot["navigation"] == navigation
    return navigation["context"]


def xlsx_download_rows(response):
    """Read real attachment rows, retaining exact public column names and values."""
    assert response.status_code == 200, response.get_data(as_text=True)[:500] if response.status_code != 200 else ""
    assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert response.headers["Content-Disposition"].startswith("attachment;")
    workbook = openpyxl.load_workbook(io.BytesIO(response.data), read_only=True, data_only=True)
    try:
        sheet = workbook.active
        assert sheet is not None
        values = sheet.iter_rows(values_only=True)
        headers = next(values)
        assert headers and all(headers) and len(set(headers)) == len(headers)
        # Templates format unused rows; only wholly empty cells are not records.
        return [dict(zip(headers, row)) for row in values if any(value is not None for value in row)]
    finally:
        workbook.close()


def canonical_resource(client, response, kind, business_code):
    """Resolve only the original resource identity through the real canonical API."""
    context = canonical_navigation(client, response, "process")
    assert set(context) == {"kind", "entity_ref", "source"}
    assert context["kind"] == kind and context["source"] == "production"
    detail = client.get("/api/workbench/v1/entities/" + kind + "/" + context["entity_ref"])
    assert detail.status_code == 200, detail.get_data(as_text=True)
    payload = detail.get_json()
    assert payload["ok"] is True
    entity = payload["data"]
    assert entity["business_code"] == business_code and entity["ref"] == context["entity_ref"]
    return entity


@contextmanager
def capture_legacy_preview(app):
    """Observe real preview data for deliberate invalid POSTs; never change HTML."""
    captured = []
    keys = ("preview_rows", "raw_rows_json", "preview_baseline", "mode", "filename", "strict_mode", "auto_generate_ops")

    def received(sender, template, context, **unused):
        if template.name == "workbench/legacy_result.html":
            captured.append({key: context[key] for key in keys if key in context})

    template_rendered.connect(received, app)
    try:
        yield captured
    finally:
        template_rendered.disconnect(received, app)


def rejected_preview_payload(captured, html):
    """Forge a blocked confirmation from its actual producer state, not a UI form."""
    assert_no_confirmation(html)
    assert len(captured) == 1, captured
    context = captured[0]
    assert any(row.status.value == "error" for row in context["preview_rows"]), "Only rejected previews use this helper"
    fields = {key: context[key] for key in ("mode", "filename", "raw_rows_json", "preview_baseline")}
    assert all(fields.values()) and fields["raw_rows_json"].startswith("aps-preview-json-b64:")
    for key in ("strict_mode", "auto_generate_ops"):
        if key in context:
            fields[key] = ("yes" if context[key] else "no") if key == "strict_mode" else ("1" if context[key] else "0")
    return fields
