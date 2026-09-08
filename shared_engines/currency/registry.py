"""Currency registry: known codes, asset types, minor units.

Minor units drive presentation rounding (2 for most fiat,
0 for JPY/CLP, 8 for BTC). The baseline covers the
Americas, Europe and Asia fiat plus crypto/metals.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from shared_engines.common.errors import ConfigurationError
from shared_engines.common.validation import require_int_range
from shared_engines.currency.errors import UnknownCurrencyError


class CurrencyAssetType(Enum):
    FIAT = "fiat"
    CRYPTO = "crypto"
    COMMODITY = "commodity"


@dataclass(frozen=True)
class CurrencySpec:
    code: str
    asset_type: CurrencyAssetType
    minor_units: int


_BASELINE: dict[str, tuple[CurrencyAssetType, int]] = {
    "USD": (CurrencyAssetType.FIAT, 2),
    "EUR": (CurrencyAssetType.FIAT, 2),
    "GBP": (CurrencyAssetType.FIAT, 2),
    "CHF": (CurrencyAssetType.FIAT, 2),
    "JPY": (CurrencyAssetType.FIAT, 0),
    "CNY": (CurrencyAssetType.FIAT, 2),
    "GTQ": (CurrencyAssetType.FIAT, 2),
    "MXN": (CurrencyAssetType.FIAT, 2),
    "COP": (CurrencyAssetType.FIAT, 2),
    "BRL": (CurrencyAssetType.FIAT, 2),
    "ARS": (CurrencyAssetType.FIAT, 2),
    "CLP": (CurrencyAssetType.FIAT, 0),
    "BTC": (CurrencyAssetType.CRYPTO, 8),
    "ETH": (CurrencyAssetType.CRYPTO, 8),
    "USDT": (CurrencyAssetType.CRYPTO, 6),
    "XAU": (CurrencyAssetType.COMMODITY, 3),
}


class CurrencyRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, CurrencySpec] = {
            code: CurrencySpec(
                code=code,
                asset_type=asset_type,
                minor_units=minor_units,
            )
            for code, (asset_type, minor_units) in _BASELINE.items()
        }

    def register(
        self,
        code: str,
        asset_type: CurrencyAssetType,
        minor_units: int,
    ) -> None:
        code = code.upper().strip()
        if len(code) < 2 or len(code) > 8:
            raise ConfigurationError(
                "currency code must be 2-8 characters"
            )
        require_int_range(
            minor_units, "minor_units", 0, 8, config=True
        )
        self._specs[code] = CurrencySpec(
            code=code,
            asset_type=asset_type,
            minor_units=minor_units,
        )

    def require(self, code: str) -> CurrencySpec:
        spec = self._specs.get(code.upper().strip())
        if spec is None:
            raise UnknownCurrencyError(
                f"unknown currency: {code}"
            )
        return spec

    def is_known(self, code: str) -> bool:
        return code.upper().strip() in self._specs

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))
