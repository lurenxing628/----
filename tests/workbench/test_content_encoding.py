"""Lossless SQLite values retain their canonical wire representation."""

from datetime import date, datetime

import pytest

from core.models.content import content_text, unpacked


@pytest.mark.parametrize(("value", "expected"), [
    ({"rows": [None, True, False, 0, 1, -1, "中文", 1.0]},
     '{"rows":[null,true,false,0,1,-1,"中文",1.0]}'),
    (b"\x00\xff", '{"$sqlite_blob":"AP8="}'),
    (date(2026, 10, 18), '{"iso":"2026-10-18","storage_type":"date"}'),
    (datetime(2026, 10, 18, 8, 30), '{"iso":"2026-10-18T08:30:00","storage_type":"datetime"}'),
])
def test_canonical_content_preserves_scalar_types_and_reserved_dictionaries(value, expected):
    import json

    assert content_text(value) == expected
    restored = unpacked(json.loads(expected))
    assert type(restored) is type(value) and restored == value


@pytest.mark.parametrize(("value", "error"), [
    (date(2026, 10, 18), TypeError), (datetime(2026, 10, 18), TypeError),
])
def test_json_input_rejects_sqlite_only_values_inside_collections(value, error):
    with pytest.raises(error):
        content_text({"rows": [value]}, json_input=True)


def test_encoding_reuses_unchanged_paths(monkeypatch):
    from core.models import content

    unchanged = {"rows": [{"values": [None, True, 1, 1.0]}]}
    source = {"unchanged": unchanged, "changed": {"blob": b"x", "kept": unchanged},
              "literal": {"$sqlite_dict": "original"}, "tuple": (1, True)}
    expected = content.json.dumps(content.packed(source), ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":"), allow_nan=False)
    encoded, dump = [], content.json.dumps

    def capture(value, **kwargs):
        encoded.append(value)
        return dump(value, **kwargs)

    monkeypatch.setattr(content.json, "dumps", capture)
    assert content.content_text(source) == expected
    value = encoded[0]
    assert value is not source and value["changed"] is not source["changed"]
    assert value["unchanged"] is unchanged and value["changed"]["kept"] is unchanged
    assert value["tuple"] is source["tuple"]
    assert source["changed"]["blob"] == b"x" and source["literal"] == {"$sqlite_dict": "original"}
    content.content_text(unchanged)
    assert encoded[1] is unchanged
