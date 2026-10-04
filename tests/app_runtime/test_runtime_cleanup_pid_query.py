"""Native process discovery needs ASCII CSV fields, not localized text decoding."""

import os
from types import SimpleNamespace

import pytest

from tests.app_runtime import runtime_cleanup_helper

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows tasklist byte output")


@pytest.mark.parametrize("output, expected", [
    (b'"\xc5\xc5\xb2\xfa.exe","3456","Console","1","123 K"\r\n', True),
    (b'"aps.exe","34560","Console","1","123 K"\r\n', False),
    (b'\xd0\xc5\xcf\xa2: no matching tasks\r\n', False),
])
def test_pid_query_reads_exact_ascii_fields_without_decoding_localized_output(monkeypatch, output, expected):
    def query(args, **kwargs):
        assert args == ["tasklist", "/FI", "PID eq 3456", "/NH", "/FO", "CSV"]
        assert not kwargs.get("text", False)
        assert kwargs["capture_output"] is True
        return SimpleNamespace(stdout=output, returncode=0)

    monkeypatch.setattr(runtime_cleanup_helper.subprocess, "run", query)
    assert runtime_cleanup_helper._pid_exists(3456) is expected
