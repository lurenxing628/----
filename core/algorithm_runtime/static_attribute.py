"""Exact static attribute reads for ordinary instances without inspect's generic machinery.

``inspect.getattr_static`` re-derives the shape of a class on every call: it walks the
metaclass lineage to prove the instance ``__dict__`` is trustworthy, then walks the MRO
again for the attribute itself. Slot estimation asks the same question about the same
calendar object once per avoidance hop, so that generic work dominated the hop. This
module keeps ``getattr_static`` semantics but remembers, per class lineage, the one
fact that cannot change without replacing the lineage: whether instance dictionaries
may be consulted. Anything unusual (classes as subjects, custom metaclasses, shadowed
``__dict__`` descriptors) is delegated to ``inspect.getattr_static`` unchanged.
"""

import inspect
import types
from typing import Any, Dict, Tuple

_MISSING = object()
_TYPE_DICT = type.__dict__["__dict__"]
_TYPE_MRO = type.__dict__["__mro__"]
# class -> (its MRO when inspected, instance dictionaries are honoured)
_LINEAGES: Dict[type, Tuple[Tuple[type, ...], bool]] = {}


def _static_mro(klass: type) -> Tuple[type, ...]:
    return _TYPE_MRO.__get__(klass)


def _shadowed_dict(klass: type) -> Any:
    """A ``__dict__`` member that hides the plain instance dictionary, or ``_MISSING``."""
    for entry in _static_mro(klass):
        try:
            class_dict = _TYPE_DICT.__get__(entry)["__dict__"]
        except KeyError:
            continue
        if not (type(class_dict) is types.GetSetDescriptorType and class_dict.__name__ == "__dict__"
                and class_dict.__objclass__ is entry):
            return class_dict
    return _MISSING


def _class_attribute(klass: type, name: str) -> Any:
    for entry in _static_mro(klass):
        if _shadowed_dict(type(entry)) is _MISSING:
            try:
                return entry.__dict__[name]
            except KeyError:
                pass
    return _MISSING


def _lineage(klass: type) -> Tuple[Tuple[type, ...], bool]:
    mro = klass.__mro__
    lineage = _LINEAGES.get(klass)
    if lineage is None or lineage[0] is not mro:
        shadow = _shadowed_dict(klass)
        lineage = _LINEAGES[klass] = (mro, shadow is _MISSING or type(shadow) is types.MemberDescriptorType)
    return lineage


def static_attribute(obj: Any, name: str, default: Any = None) -> Any:
    """``inspect.getattr_static(obj, name, default)`` for instances of plain-metaclass classes."""
    klass = type(obj)
    if type(klass) is not type or isinstance(obj, type):
        return inspect.getattr_static(obj, name, default)
    mro, instance_dict_honoured = _lineage(klass)
    instance_result = _MISSING
    if instance_dict_honoured:
        try:
            instance_dict = object.__getattribute__(obj, "__dict__")
        except AttributeError:
            instance_dict = {}
        instance_result = dict.get(instance_dict, name, _MISSING)
    klass_result = _MISSING
    for entry in mro:
        entry_dict = entry.__dict__
        if name in entry_dict:
            klass_result = entry_dict[name]
            break
    if instance_result is not _MISSING and klass_result is not _MISSING:
        descriptor = type(klass_result)
        if _class_attribute(descriptor, "__get__") is not _MISSING and _class_attribute(descriptor, "__set__") is not _MISSING:
            return klass_result
    if instance_result is not _MISSING:
        return instance_result
    if klass_result is not _MISSING:
        return klass_result
    return default


def static_class_attribute(klass: Any, name: str, default: Any = None) -> Any:
    """``inspect.getattr_static(klass, name, default)`` for classes with the plain ``type`` metaclass."""
    if type(klass) is not type:
        return inspect.getattr_static(klass, name, default)
    for entry in klass.__mro__:
        entry_dict = entry.__dict__
        if name in entry_dict:
            return entry_dict[name]
    for entry in type.__mro__:
        if name in entry.__dict__:
            return entry.__dict__[name]
    return default


__all__ = ["static_attribute", "static_class_attribute"]
