"""Application JSON provider: every ``request.get_json()`` body decodes through the strict reader.

Duplicate keys and ``NaN``/``Infinity`` fail exactly like a malformed body: the ``ValueError`` becomes
Flask's JSON ``BadRequest``, which each JSON boundary already reports with its existing wording.
"""

from flask.json.provider import DefaultJSONProvider

from core.shared.strict_json import load_strict_json


def _not_strict_json():
    raise ValueError("request body is not strict JSON")


class StrictJSONProvider(DefaultJSONProvider):
    def loads(self, s, **kwargs):
        # Strict decoding takes no keyword options; nothing in the application passes any.
        return load_strict_json(s, on_malformed=_not_strict_json)
