"""
Non-evaluating template renderer.

Only explicit ``{{ variable }}`` substitution is supported.
No Python evaluation or arbitrary code execution is performed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping


class TemplateError(ValueError):
    """Raised when template rendering fails."""


class TemplateEngine:
    _TOKEN = re.compile(
        r"{{\s*"
        r"([A-Za-z_][A-Za-z0-9_.-]*)"
        r"\s*}}"
    )

    def render(
        self,
        template: str,
        values: Mapping[
            str,
            object,
        ],
    ) -> str:
        if not isinstance(
            template,
            str,
        ):
            raise TypeError(
                "template must be a string"
            )

        def replace(
            match: re.Match[str],
        ) -> str:
            key = match.group(1)

            if key not in values:
                raise TemplateError(
                    f"missing template variable: "
                    f"{key}"
                )

            value = values[key]

            if value is None:
                return ""

            return str(value)

        return self._TOKEN.sub(
            replace,
            template,
        )


__all__ = [
    "TemplateEngine",
    "TemplateError",
]
