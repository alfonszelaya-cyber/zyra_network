
from __future__ import annotations

class ValidateIdentityRecordUseCase:
    """Validacion pura de referencia."""

    def __init__(self, validation):
        self._val = validation

    def execute(self, *, zid, provider,
                expires_at=None) -> dict:
        return self._val.validate_reference(
            zid=zid, provider=provider,
            expires_at=expires_at)
