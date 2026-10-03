
"""Pagos: errores de dominio."""
from __future__ import annotations


class PaymentError(Exception):
    """Base del dominio de pagos."""


class UnknownPaymentError(PaymentError):
    pass


class UnknownInstrumentError(PaymentError):
    pass


class InstrumentInactiveError(PaymentError):
    pass


class PaymentStateError(PaymentError):
    pass


class DisputeWindowClosedError(PaymentError):
    pass


class QRRequestUnavailableError(PaymentError):
    pass
