"""Command envelopes share one structural check: media type, exact keys, request key form and write-token shape.

These requests are hand-built bad requests; the browser always sends JSON, a request key and the token it was given.
Rejecting them is the route's own 400, before any token is resolved or any business fact is read.
"""

import json

import pytest

KEY = "envelope-contract-0001"
TOKEN = "T" * 32
REF = "0" * 48
V1 = "/api/workbench/v1"


@pytest.mark.parametrize("path, subject", [
    ("/trial/drafts", "试调还没有保存"),
    ("/trial/scenarios/" + REF + "/adopt", "试调方案还没有采用"),
    ("/scheduling/candidates/" + REF + "/adopt", "还没有采用"),
    ("/calibration/" + REF + "/adopt", "还没有采用"),
])
def test_non_json_command_is_a_400_in_the_route_wording(app_client, path, subject):
    response = app_client.post(V1 + path, data="{}", content_type="text/plain")
    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == "invalid_input" and subject in error["message"]


@pytest.mark.parametrize("path, body, message", [
    ("/execution/tasks/" + REF + "/reports", {"input": {}}, "本页数据已过期，报工还没有保存。请点「刷新资料」后重新填写。"),
    ("/entities/machine/" + REF + "/downtimes/create", {"input": {}}, "本页数据已过期，数据没有改动。请刷新页面后重新填写。"),
    ("/process/parts/create", {"input": {}}, "本页数据已过期，零件还没有新增。请点「刷新资料」后重新填写。"),
    ("/dashboard/items/" + REF + "/transition", {"input": {}}, "本页数据已过期，处置还没有保存。请刷新页面后重新填写。"),
    ("/scheduling/preferences", {"input": {}}, "本页数据已过期，排产范围还没有保存。请刷新页面后重新选择。"),
    ("/scheduling/runs", {"input_ref": "x" * 32}, "还没有确认开始排产，这次排产没有开始。请在排产检查页点「开始排产」。"),
    ("/outsourcing/receipts", {"input": {}}, "本页数据已过期，外协登记还没有保存。请刷新页面后重新填写。"),
    ("/trial/drafts", {"input": {}}, "本页数据已过期，试调还没有保存。请刷新页面后重新填写。"),
    ("/system/config/save", {"input": {}}, "本页数据已过期，数据没有改动。请刷新页面后重试。"),
])
@pytest.mark.parametrize("token", ["", 123])
def test_write_token_that_is_not_a_non_empty_string_is_rejected_before_any_lookup(app_client, path, body, message, token):
    response = app_client.post(V1 + path, json={"request_key": KEY, "write_token": token, **body})
    assert response.status_code == 400
    error = response.get_json()["error"]
    assert (error["code"], error["message"]) == ("invalid_input", message)


def test_preview_confirmation_checks_the_opaque_token_before_its_input(app_client):
    response = app_client.post(V1 + "/entities/operator/" + REF + "/machine-permissions/confirm",
                               json={"request_key": KEY, "write_token": "short", "input": {"preview_ref": "y" * 32}})
    assert response.status_code == 400
    assert response.get_json()["error"]["message"] == "这次操作的编号已失效，数据没有改动。请关掉弹窗后重新打开。"


def test_system_commands_take_only_application_json(app_client):
    body = json.dumps({"request_key": KEY, "write_token": TOKEN, "input": {}})
    response = app_client.post(V1 + "/system/config/save", data=body, content_type="application/merge-patch+json")
    assert response.status_code == 400
    assert response.get_json()["error"]["message"] == "提交的内容格式不正确，数据没有改动。请刷新页面后重新填写。"


@pytest.mark.parametrize("path, wording", [
    ("/entities/batch", "筛选条件有重复或不支持的项，列表没有变化。"),
    ("/entities/batch/" + REF, "详情的查询条件不对，详情没有打开。"),
    ("/system/logs", "筛选条件有重复或不支持的项，当前筛选没有变化。"),
])
def test_unknown_url_argument_is_rejected_by_the_route_whitelist(app_client, path, wording):
    response = app_client.get(V1 + path, query_string={"unknown": "1"})
    assert response.status_code == 400
    assert wording in response.get_json()["error"]["message"]
