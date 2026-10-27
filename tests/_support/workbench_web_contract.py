"""Real boot assertions shared by migrated web entry tests."""

import json
from html.parser import HTMLParser


class _Boot(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active, self.parts = False, []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "workbench-boot":
            self.active = True

    def handle_data(self, value):
        if self.active:
            self.parts.append(value)

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False


def boot_payload(response):
    """Require the actual offline host response and decode its JSON boot node."""
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    body = response.get_data(as_text=True)
    assert '<body class="aps-workbench">' in body
    assert 'id="root"' in body and 'id="workbench-boot"' in body
    assert "https://" not in body and "http://" not in body
    parser = _Boot()
    parser.feed(body)
    payload = json.loads("".join(parser.parts))
    assert payload["schema_version"] == 1
    return payload
