"""Real boot/retirement assertions shared by migrated web entry tests."""

import json
from urllib.parse import parse_qs, urlsplit

from tests._support.gantt_retirement import _Boot


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


def canonical_boot(client, path, view, context):
    """Check the complete redirect and refresh without changing explicit scope."""
    response = client.get(path)
    assert response.status_code == 302, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    target = urlsplit(response.headers["Location"])
    assert not target.scheme and not target.netloc and not target.fragment
    assert target.path == ("/workbench/trial" if view == "trial" else "/workbench")
    query = parse_qs(target.query, strict_parsing=True)
    expected = {"version": 1, "view": view, "context": context}
    assert set(query) == {"view", "nav"} and query["view"] == [view]
    assert len(query["nav"]) == 1 and json.loads(query["nav"][0]) == expected
    boot = boot_payload(client.get(response.headers["Location"]))
    assert boot["view"] == view and boot["navigation"] == expected
    assert boot_payload(client.get(response.headers["Location"]))["navigation"] == expected
    return boot


def retired_response(response, *, post_result=False):
    """Assert explicit retirement while retaining POST receipt visibility."""
    body = response.get_data(as_text=True)
    assert response.status_code == 410, body
    assert response.headers["Cache-Control"] == "no-store"
    assert "Location" not in response.headers
    assert 'data-workbench-legacy-response="true"' in body
    assert "旧入口已退役" in body and "原业务数据、保存的配置和历史记录仍保留" in body
    assert "未忽略" in body or "未改用" in body or "未沿用" in body or "未改写原条件" in body
    if post_result:
        assert len(response.history) == 1
        assert response.history[0].status_code == 302
        assert response.history[0].request.method == "POST"
        assert response.request.method == "GET"
    return body
