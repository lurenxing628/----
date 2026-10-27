"""Application JSON provider: every ``request.get_json()`` body decodes through the strict reader.

Duplicate keys and ``NaN``/``Infinity`` fail exactly like a malformed body: the ``ValueError`` becomes
Flask's JSON ``BadRequest``, which each JSON boundary already reports with its existing wording.
Output is strict too: ``jsonify`` and ``app.json.dumps`` raise ``ValueError`` instead of writing
``NaN``/``Infinity``, which is not JSON.
"""

from flask.json.provider import DefaultJSONProvider

from core.shared.strict_json import load_strict_json


def _not_strict_json():
    raise ValueError("request body is not strict JSON")


class StrictJSONProvider(DefaultJSONProvider):
    def loads(self, s, **kwargs):
        # Strict decoding takes no keyword options; nothing in the application passes any.
        return load_strict_json(s, on_malformed=_not_strict_json)

    def dumps(self, obj, **kwargs):
        # 固定拒绝非有限数；调用方再传 allow_nan 会因重复参数直接报错。
        return super().dumps(obj, allow_nan=False, **kwargs)
