
"""Conectores cripto on-chain de la Red
(Blockstream Esplora + mempool.space,
ambos publicos sin key, falla honesta).
Cierran el circuito BTC: el hold_ref del
motor de pagos puede ser un txid real
verificado en la cadena."""
from __future__ import annotations

import hashlib
import json
import urllib.request


class _HttpBase:
    """GET con UA de la Red + parse JSON."""

    name = "base"

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._timeout = timeout_seconds

    def _get_json(self, url: str):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent":
                "zyra-network/1.0"
            })
        with urllib.request.urlopen(
                req,
                timeout=self._timeout) as r:
            return json.loads(
                r.read().decode("utf-8"))

    def _sha(self, data) -> str:
        return hashlib.sha256(
            json.dumps(
                data,
                sort_keys=True,
                default=str).encode(
                "utf-8")).hexdigest()


class BlockstreamConnector(_HttpBase):
    """Verificacion de txid BTC via
    Esplora (blockstream.info/api)."""

    name = "blockstream"

    def tx_status(self, txid: str) -> dict:
        """Estado on-chain de una
        transaccion: confirmada y
        en que bloque."""
        txid = txid.strip()
        if len(txid) != 64:
            return {
                "source": self.name,
                "txid": txid,
                "on_chain": False,
                "error": "txid must be 64 hex chars",
            }
        url = ("https://blockstream.info"
               "/api/tx/" + txid)
        try:
            d = self._get_json(url)
        except Exception as exc:
            return {
                "source": self.name,
                "txid": txid,
                "on_chain": False,
                "error":
                type(exc).__name__,
            }
        resumen = {
            "source": self.name,
            "txid": txid,
            "on_chain": True,
            "confirmed": (
                d.get("status", {})
                .get("confirmed", False)),
            "block_height": (
                d.get("status", {})
                .get("block_height")),
            "fee": d.get("fee"),
            "vsize": d.get("vsize"),
        }
        resumen["sha256"] = self._sha(
            resumen)
        return resumen

    def address_balance(
        self, address: str) -> dict:
        """Saldo on-chain de una
        direccion BTC (chain stats)."""
        address = address.strip()
        url = ("https://blockstream.info"
               "/api/address/" + address)
        try:
            d = self._get_json(url)
        except Exception as exc:
            return {
                "source": self.name,
                "address": address,
                "error":
                type(exc).__name__,
            }
        cs = d.get(
            "chain_stats", {})
        ms = d.get(
            "mempool_stats", {})
        received = (
            cs.get("funded_txo_sum", 0)
            - cs.get("spent_txo_sum", 0))
        pending = (
            ms.get("funded_txo_sum", 0)
            - ms.get("spent_txo_sum", 0))
        resumen = {
            "source": self.name,
            "address": address,
            "confirmed_sats": received,
            "pending_sats": pending,
            "confirmed_btc": (
                received / 100_000_000),
        }
        resumen["sha256"] = self._sha(
            resumen)
        return resumen


class MempoolConnector(_HttpBase):
    """Fees recomendados y estado
    de la mempool (mempool.space/api)."""

    name = "mempool"

    def recommended_fees(self) -> dict:
        """Satoshi/vByte por urgencia."""
        url = ("https://mempool.space"
               "/api/v1/fees/recommended")
        d = self._get_json(url)
        resumen = {
            "source": self.name,
            "fastest": d.get(
                "fastestFee"),
            "hour": d.get(
                "hourFee"),
            "economy": d.get(
                "economyFee"),
            "minimum": d.get(
                "minimumFee"),
        }
        resumen["sha256"] = self._sha(
            resumen)
        return resumen

    def tx_status(self, txid: str) -> dict:
        """Estado confirmacion via
        mempool.space (fuente 2a)."""
        txid = txid.strip()
        if len(txid) != 64:
            return {
                "source": self.name,
                "txid": txid,
                "on_chain": False,
                "error": "txid must be 64 hex chars",
            }
        url = ("https://mempool.space"
               "/api/tx/" + txid)
        try:
            d = self._get_json(url)
        except Exception as exc:
            return {
                "source": self.name,
                "txid": txid,
                "on_chain": False,
                "error":
                type(exc).__name__,
            }
        resumen = {
            "source": self.name,
            "txid": txid,
            "on_chain": True,
            "confirmed": (
                d.get("status", {})
                .get("confirmed", False)),
            "block_height": (
                d.get("status", {})
                .get("block_height")),
            "fee": d.get("fee"),
        }
        resumen["sha256"] = self._sha(
            resumen)
        return resumen
