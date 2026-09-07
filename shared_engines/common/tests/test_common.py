from __future__ import annotations

import pytest

from shared_engines.common.clocks import FrozenClock
from shared_engines.common.errors import (
    ConfigurationError,
    SerializationError,
    ValidationError,
)
from shared_engines.common.pagination import Page
from shared_engines.common.result import Result
from shared_engines.common.serialization import canonical_json_dumps
from shared_engines.common.validation import (
    require_int_range,
    require_non_empty_str,
    require_one_of,
    require_positive_number,
)


def test_canonical_json_stable() -> None:
    assert canonical_json_dumps({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    with pytest.raises(SerializationError):
        canonical_json_dumps({"x": object()})


def test_frozen_clock() -> None:
    clock = FrozenClock(start=100.0)
    clock.sleep(5.0)
    assert clock.now() == 105.0


def test_result() -> None:
    ok: Result[int] = Result.ok(3)
    assert ok.is_ok and ok.value == 3
    err: Result[int] = Result.err(ConfigurationError("bad"))
    assert not err.is_ok
    assert err.error is not None
    with pytest.raises(ConfigurationError):
        _ = err.value
    with pytest.raises(ConfigurationError):
        Result[int](None, None)
    with pytest.raises(ConfigurationError):
        Result[int](1, ConfigurationError("bad"))


def test_page() -> None:
    page: Page[int] = Page(items=(1, 2), offset=0, limit=2, total=5)
    assert page.has_more and page.next_offset == 2
    last: Page[int] = Page(items=(1,), offset=4, limit=2, total=5)
    assert not last.has_more and last.next_offset is None
    with pytest.raises(ValidationError):
        Page(items=(), offset=-1, limit=2, total=0)


def test_validators() -> None:
    assert require_non_empty_str("x", "v") == "x"
    with pytest.raises(ValidationError):
        require_non_empty_str("  ", "v")
    with pytest.raises(ValidationError):
        require_int_range(-1, "o", 0, 10)
    with pytest.raises(ValidationError):
        require_positive_number(-1.0, "t")
    with pytest.raises(ValidationError):
        require_positive_number(float("inf"), "t")
    assert require_one_of("A", ("A", "B"), "m") == "A"
    with pytest.raises(ValidationError):
        require_one_of("C", ("A", "B"), "m")
