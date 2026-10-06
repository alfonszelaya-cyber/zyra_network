
"""Soporte: errores de dominio."""
from __future__ import annotations


class SupportError(Exception):
    pass


class UnknownTicketError(SupportError):
    pass


class UnknownCaseError(SupportError):
    pass
