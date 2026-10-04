
"""Tests conectores on-chain (mockeados)."""
from __future__ import annotations

import json

from shared_engines.integrations.rates_onchain import (
    BlockstreamConnector,
    MempoolConnector,
)


class _R:
    def __init__(self, p):
        self._p = p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._p


TXID = "a" * 64


def _patch(monkeypatch, payload):
    body = json.dumps(payload).encode()
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: _R(body))


def test_blockstream_tx_confirmed(
    tmp_path, monkeypatch) -> None:
    _patch(monkeypatch, {
        "status": {"confirmed": True,
                   "block_height": 812345},
        "fee": 1500, "vsize": 141})
    r = BlockstreamConnector().tx_status(
        TXID)
    assert r["on_chain"] is True
    assert r["confirmed"] is True
    assert r["block_height"] == 812345
    assert r["sha256"]
    print("OK on-chain: blockstream tx"
          " confirmada en bloque 812345")


def test_blockstream_txid_invalido(
    tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: (
            (_ for _ in ()).throw(
                AssertionError(
                    "no debe llamar red"))))
    r = BlockstreamConnector().tx_status(
        "mal-txid")
    assert r["on_chain"] is False
    assert "error" in r
    print("OK on-chain: txid invalido"
          " rechazado sin tocar red")


def test_blockstream_balance(
    tmp_path, monkeypatch) -> None:
    _patch(monkeypatch, {
        "chain_stats": {
            "funded_txo_sum": 1_500_000_000,
            "spent_txo_sum": 500_000_000},
        "mempool_stats": {
            "funded_txo_sum": 0,
            "spent_txo_sum": 0}})
    r = BlockstreamConnector().address_balance(
        "bc1qexample")
    assert r["confirmed_sats"] == 1_000_000_000
    assert r["confirmed_btc"] == 10.0
    print("OK on-chain: balance 10 BTC")


def test_mempool_fees(
    tmp_path, monkeypatch) -> None:
    _patch(monkeypatch, {
        "fastestFee": 12,
        "hourFee": 8,
        "economyFee": 5,
        "minimumFee": 2})
    r = MempoolConnector().recommended_fees()
    assert r["fastest"] == 12
    assert r["economy"] == 5
    print("OK on-chain: mempool fees 12/8/5/2")


def test_mempool_tx_status(
    tmp_path, monkeypatch) -> None:
    _patch(monkeypatch, {
        "status": {"confirmed": True,
                   "block_height": 812346},
        "fee": 1400})
    r = MempoolConnector().tx_status(TXID)
    assert r["confirmed"] is True
    assert r["source"] == "mempool"
    print("OK on-chain: mempool tx"
          " confirmada (fuente 2a)")
