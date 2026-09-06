"""Safe infrastructure template rendering."""

from .template_engine import (
    TemplateEngine,
    TemplateError,
)

__all__ = [
    "TemplateEngine",
    "TemplateError",
]
