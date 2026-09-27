
"""Seguridad alimentaria nacional para la vista
Gobierno de AGRO. Lee del store; no modifica la
logica de negocio del store."""
from __future__ import annotations


class FoodSecurityService:
    def __init__(self, store) -> None:
        self._store = store

    def national_status(self) -> dict:
        summary = self._store.summary()
        by_product = dict(
            summary.get("productions_by_product") or {}
        )
        products = []
        for name, qty in sorted(by_product.items()):
            products.append(
                {
                    "product": str(name),
                    "quantity": float(qty or 0),
                    "produced": float(qty or 0) > 0,
                }
            )
        return {
            "producers_total": int(
                summary.get("producers_total") or 0
            ),
            "producers_verified": int(
                summary.get("producers_verified") or 0
            ),
            "products": products,
            "soberania_alimentaria": (
                len(products) > 0
            ),
        }
