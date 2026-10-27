from __future__ import annotations

from typing import Any, Tuple

from core.errors import ValidationError
from core.shared.field_labels import display_field_label
from core.shared.strict_parse import parse_required_float, parse_required_int

from .schedule_config_runtime_fields import RuntimeConfigFieldSpec, get_field_spec

_YES_TEXTS = {"yes", "y", "true", "1", "on"}
_NO_TEXTS = {"no", "n", "false", "0", "off"}


def _required_text(raw_value: Any, *, field_name: str) -> str:
    text = "" if raw_value is None else str(raw_value).strip().lower()
    if text == "":
        raise ValidationError(f"“{display_field_label(field_name, fallback='配置项')}”不能为空", field=field_name)
    return text


def _coerce_choice(raw_value: Any, *, field_name: str, choices: Tuple[str, ...]) -> str:
    text = _required_text(raw_value, field_name=field_name)
    if text not in choices:
        label = display_field_label(field_name, fallback="配置项")
        raise ValidationError(f"“{label}”填写不正确：{raw_value}（可填写：{' / '.join(choices)}）", field=field_name)
    return text


def _coerce_yes_no(raw_value: Any, *, field_name: str) -> str:
    text = _required_text(raw_value, field_name=field_name)
    if text in _YES_TEXTS:
        return "yes"
    if text in _NO_TEXTS:
        return "no"
    label = display_field_label(field_name, fallback="配置项")
    raise ValidationError(f"“{label}”填写不正确：{raw_value}（请填写：是 / 否）", field=field_name)


def _coerce_number(spec: RuntimeConfigFieldSpec, value: Any, *, label: str) -> Any:
    # 解析提示用页面字段名，错误归属用配置键。
    try:
        if spec.field_type == "float":
            return parse_required_float(value, field=label, min_value=spec.min_value,
                                        min_inclusive=bool(spec.min_inclusive))
        return parse_required_int(value, field=label,
                                  min_value=(None if spec.min_value is None else int(spec.min_value)))
    except ValidationError as exc:
        raise ValidationError(exc.message, field=spec.key) from exc


def coerce_config_field(key: str, value: Any, *, missing: bool, field_label: str) -> Any:
    """Strictly coerce one stored configuration value; a missing, blank or invalid value is an error."""
    spec = get_field_spec(key)
    if missing:
        raise ValidationError(f"缺少“{display_field_label(spec.key, fallback='配置项')}”配置", field=spec.key)
    if spec.field_type == "enum":
        return _coerce_choice(value, field_name=spec.key, choices=spec.choices)
    if spec.field_type == "yes_no":
        return _coerce_yes_no(value, field_name=spec.key)
    if spec.field_type in ("float", "int"):
        return _coerce_number(spec, value, label=field_label)
    raise TypeError(f"不支持的运行期配置字段类型：{spec.field_type!r}")


__all__ = ["coerce_config_field"]
