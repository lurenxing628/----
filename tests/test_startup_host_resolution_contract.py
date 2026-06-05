"""单元测试：launcher_network 主机解析契约——pick_bind_host 把 None/空/localhost/::1/非法主机统一归一化为 127.0.0.1 而保留合法 IPv4，pick_port 在请求的 IPv4 无法绑定时回退到 127.0.0.1 同端口。"""

from __future__ import annotations

from typing import List, Optional

import pytest

import web.bootstrap.launcher_network as launcher_network


@pytest.mark.parametrize(
    ("raw_host", "expected"),
    [
        (None, "127.0.0.1"),
        ("", "127.0.0.1"),
        ("localhost", "127.0.0.1"),
        ("::1", "127.0.0.1"),
        ("not_a_host", "127.0.0.1"),
        ("127.0.0.1", "127.0.0.1"),
        ("192.0.2.123", "192.0.2.123"),
    ],
)
def test_pick_bind_host_normalizes_non_ipv4_values(raw_host: Optional[str], expected: str) -> None:
    assert launcher_network.pick_bind_host(raw_host) == expected


def test_pick_port_falls_back_to_loopback_when_requested_ipv4_cannot_bind(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[str] = []

    def fake_can_bind(host: str, port: int, **_kwargs: object) -> bool:
        calls.append(f"{host}:{port}")
        return host == "127.0.0.1"

    monkeypatch.setattr(launcher_network, "_can_bind", fake_can_bind)

    host, port = launcher_network.pick_port("192.0.2.123", 5705)

    assert host == "127.0.0.1"
    assert port == 5705
    assert "192.0.2.123:5705" in calls
    assert "127.0.0.1:5705" in calls
