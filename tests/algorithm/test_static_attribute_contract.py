"""The fast static attribute reader must agree with ``inspect.getattr_static`` on every subject."""

import abc
import inspect
from types import MethodType, SimpleNamespace

import pytest

from core.algorithm_runtime import static_attribute as module
from core.algorithm_runtime.static_attribute import static_attribute, static_class_attribute
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.run.schedule_execution_reservations import ExecutionResourceCalendar
from tests._support.busy_block_case import native_calendar


class Plain:
    certified_slot_window = None
    value = 1

    def method(self):
        return "class"

    @property
    def prop(self):
        return "class property"


class Slotted:
    __slots__ = ("slot",)

    def __init__(self):
        self.slot = "slot value"


class DictSlotted:
    __slots__ = ("__dict__",)


class Forwarding:
    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)


class Abstract(abc.ABC):
    def method(self):
        return "abstract"


class Meta(type):
    extra = "metaclass attribute"


class WithMeta(metaclass=Meta):
    pass


def _shadowing_instance():
    subject = Plain()
    subject.method = MethodType(lambda self: "instance", subject)
    vars(subject)["prop"] = "instance shadow of a data descriptor"
    subject.value = 2
    return subject


def _subjects():
    with native_calendar() as calendar:
        overlay = ExecutionResourceCalendar(calendar, [])
        yield calendar
        yield overlay
    yield Plain()
    yield _shadowing_instance()
    yield Slotted()
    yield DictSlotted()
    yield Forwarding(Plain())
    yield Abstract()
    yield WithMeta()
    yield SimpleNamespace(certified_slot_window="namespace", id=3)
    yield Plain
    yield WithMeta
    yield 5
    yield None


NAMES = ("certified_slot_window", "method", "prop", "value", "slot", "extra", "id", "missing", "__dict__", "__getattribute__")


@pytest.mark.parametrize("name", NAMES)
def test_instance_reads_match_inspect(name):
    for subject in _subjects():
        expected = inspect.getattr_static(subject, name, module._MISSING)
        actual = static_attribute(subject, name, module._MISSING)
        assert actual is expected, (subject, name)


@pytest.mark.parametrize("name", NAMES)
def test_class_reads_match_inspect(name):
    for klass in (Plain, Slotted, DictSlotted, Forwarding, Abstract, WithMeta, Meta, CalendarService, ExecutionResourceCalendar,
                  SimpleNamespace, int, type):
        expected = inspect.getattr_static(klass, name, module._MISSING)
        assert static_class_attribute(klass, name, module._MISSING) is expected, (klass, name)


def test_default_is_returned_for_forwarded_and_missing_attributes():
    sentinel = object()
    assert static_attribute(Forwarding(Plain()), "value", sentinel) is sentinel
    assert static_attribute(Plain(), "missing") is None
    assert static_attribute(Plain(), "certified_slot_window", sentinel) is None


def test_lineage_memo_follows_class_mutation_and_rebasing():
    class Base:
        pass

    class Child(Base):
        pass

    subject = Child()
    assert static_attribute(subject, "late") is None
    Base.late = "added later"
    assert static_attribute(subject, "late") == "added later"
    Child.late = "child wins"
    assert static_attribute(subject, "late") == "child wins"

    class Other:
        late = "rebased"

    Child.__bases__ = (Other,)
    del Child.late
    assert static_attribute(subject, "late") == "rebased"
    assert inspect.getattr_static(subject, "late") == "rebased"


def test_non_dict_instance_dictionary_raises_like_inspect():
    class Weird:
        pass

    subject = Weird()
    object.__setattr__(subject, "__dict__", {"ok": 1})
    assert static_attribute(subject, "ok") == 1

    class Mapping(dict):
        pass

    subject.__dict__ = Mapping(ok=2)
    assert static_attribute(subject, "ok") == inspect.getattr_static(subject, "ok") == 2
