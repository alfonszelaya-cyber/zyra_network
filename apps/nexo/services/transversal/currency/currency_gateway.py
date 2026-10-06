
"""Gateway NEXO -> CurrencyEngine transversal.

Regla 69: el motor vive en shared_engines.currency;
este gateway solo adapta. Firma real del engine:
quote(*, base, quote_ccy, requester_zid) -> SignedQuote
y convert(*, subject_zid, base, quote_ccy, amount).
Si el motor esta inyectado se delega con esas firmas;
si no, tasas estaticas de degradacion marcada.
Montos Decimal (regla 61)."""
from __future__ import annotations
from decimal import Decimal as _D

STATIC_RATES = {
    "USD": {"USD": "1", "EUR": "0.92", "GTQ": "7.75",
            "SVC": "8.75", "BTC": "0.0000152"},
    "EUR": {"EUR": "1", "USD": "1.0870",
            "GTQ": "8.4239", "SVC": "9.5109"},
    "GTQ": {"GTQ": "1", "USD": "0.1290",
            "EUR": "0.1187"},
    "BTC": {"BTC": "1", "USD": "65789.47"},
}

def _rate(base, quote) -> _D:
    if base == quote:
        return _D("1")
    direct = STATIC_RATES.get(base, {}).get(quote)
    if direct:
        return _D(direct)
    inv = STATIC_RATES.get(quote, {}).get(base)
    if inv:
        return (_D("1") / _D(inv)).quantize(_D("0.000001"))
    raise ValueError("par no soportado en degradacion: "
                     + base + "/" + quote)

def _extraer_rate(r) -> str:
    for attr in ("rate", "price", "value"):
        v = getattr(r, attr, None)
        if v is not None:
            return str(v)
    if isinstance(r, dict):
        for k in ("rate", "price", "value"):
            if k in r:
                return str(r[k])
    return str(r)

class NexoCurrencyGateway:
    """Cotizacion y conversion multi-moneda para NEXO."""

    def __init__(self, engine=None):
        self._engine = engine

    @property
    def mode(self) -> str:
        return ("shared_engine"
                if self._engine is not None
                else "static_fallback")

    def quote(self, base, quote) -> dict:
        if self._engine is not None:
            try:
                r = self._engine.quote(
                    base=base, quote_ccy=quote,
                    requester_zid="nexo-gateway")
                return {"rate": _extraer_rate(r),
                        "source": "shared_engine"}
            except Exception:
                pass
            for name in ("get_quote", "rate", "get_rate"):
                m = getattr(self._engine, name, None)
                if callable(m):
                    try:
                        r = m(base, quote)
                        return {"rate": _extraer_rate(r),
                                "source":
                                    "shared_engine"}
                    except Exception:
                        continue
        return {"rate": str(_rate(base, quote)),
                "source": self.mode}

    def convert(self, amount, base, quote) -> dict:
        amt = _D(str(amount))
        q = self.quote(base, quote)
        converted = (amt * _D(q["rate"])).quantize(
            _D("0.01"))
        return {"amount": str(amt), "from": base,
                "to": quote, "rate": q["rate"],
                "converted": str(converted),
                "source": q["source"]}

    def supported(self):
        if self._engine is not None:
            for name in ("supported", "currencies",
                         "list_currencies"):
                m = getattr(self._engine, name, None)
                if callable(m):
                    try:
                        return list(m())
                    except Exception:
                        continue
        todas = set(STATIC_RATES.keys())
        for d in STATIC_RATES.values():
            todas.update(d.keys())
        return sorted(todas)
