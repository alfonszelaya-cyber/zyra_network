from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any


_WHITESPACE = re.compile(r"\s+")


def normalize_text(
    value: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError(
            "value must be a string"
        )

    normalized = unicodedata.normalize(
        "NFKC",
        value,
    )

    return _WHITESPACE.sub(
        " ",
        normalized,
    ).strip()


def normalize_identifier(
    value: str,
) -> str:
    normalized = normalize_text(
        value
    ).lower()

    normalized = re.sub(
        r"[^a-z0-9._:-]",
        "-",
        normalized,
    )

    normalized = re.sub(
        r"-{2,}",
        "-",
        normalized,
    )

    return normalized.strip("-")


def deep_copy_mapping(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(
            "value must be a mapping"
        )

    def copy_item(item: Any) -> Any:
        if isinstance(item, Mapping):
            return {
                str(key): copy_item(val)
                for key, val in item.items()
            }

        if isinstance(item, list):
            return [
                copy_item(val)
                for val in item
            ]

        if isinstance(item, tuple):
            return tuple(
                copy_item(val)
                for val in item
            )

        if isinstance(item, set):
            return {
                copy_item(val)
                for val in item
            }

        return item

    return copy_item(value)


def compact_dict(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item is not None
    }


def chunks(
    values: Iterable[Any],
    size: int,
) -> Iterable[list[Any]]:
    if size <= 0:
        raise ValueError(
            "size must be positive"
        )

    batch: list[Any] = []

    for value in values:
        batch.append(value)

        if len(batch) == size:
            yield batch
            batch = []

    if batch:
        yield batch


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    if minimum > maximum:
        raise ValueError(
            "minimum cannot exceed maximum"
        )

    return max(
        minimum,
        min(value, maximum),
    )
