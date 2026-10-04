
"""Tests RED-9: IA plugable (mockeada + honesta)."""
from __future__ import annotations

import json

import pytest

from shared_engines.ai.providers import (
    AIChain,
    GeminiProvider,
    OllamaProvider,
    OpenaiProvider,
)
from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import FrozenClock
from shared_engines.events.outbox import Outbox
from shared_engines.ai.engine import AIEngine
from shared_engines.storage.database import SQLiteAdapter


class _R:
    def __init__(self, p):
        self._p = p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._p


def _engine(tmp_path):
    db = SQLiteAdapter(tmp_path / "ai9.db")
    clock = FrozenClock()
    audit = AuditTrail(db, clock)
    outbox = Outbox(db, clock)
    outbox.ensure_schema()
    return AIEngine(
        db, clock, audit=audit, outbox=outbox)


def test_gemini_sin_key_honesto(
    tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(
        "GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: (
            (_ for _ in ()).throw(
                AssertionError(
                    "sin key no llama red"))))
    with pytest.raises(
            RuntimeError,
            match="not_configured"):
        GeminiProvider().analyze(
            "analiza", "contenido")
    print("OK RED-9: gemini sin key ="
          " not_configured, cero llamada")


def test_gemini_analiza_mock(
    tmp_path, monkeypatch) -> None:
    body = json.dumps({
        "candidates": [{"content": {
            "parts": [{"text":
                "documento autentico"}]}}]}).encode()
    monkeypatch.setenv(
        "GEMINI_API_KEY", "AIza-test")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: _R(body))
    r = GeminiProvider().analyze(
        "clasifica", "contenido-x")
    assert r.provider == "gemini"
    assert "autentico" in r.verdict
    print("OK RED-9: gemini analiza (mock)")


def test_openai_analiza_mock(
    tmp_path, monkeypatch) -> None:
    body = json.dumps({
        "choices": [{"message": {
            "content":
            "posible fraude detectado"}}]}).encode()
    monkeypatch.setenv(
        "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: _R(body))
    r = OpenaiProvider().analyze(
        "clasifica", "contenido-y")
    assert r.provider == "openai"
    assert "fraude" in r.verdict
    print("OK RED-9: openai analiza (mock)")


def test_chain_fallback_gemini_a_openai(
    tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(
        "GEMINI_API_KEY", "AIza-test")
    monkeypatch.setenv(
        "OPENAI_API_KEY", "sk-test")
    body_openai = json.dumps({
        "choices": [{"message": {
            "content":
            "openai respondio"}}]}).encode()

    def fake(req, timeout=None):
        url = req.full_url
        if "generativelanguage" in url:
            raise OSError("gemini caido")
        if "api.openai.com" in url:
            return _R(body_openai)
        raise OSError(url[:60])

    monkeypatch.setattr(
        "urllib.request.urlopen", fake)
    chain = AIChain([
        GeminiProvider(),
        OpenaiProvider()])
    r = chain.analyze("x", "y")
    assert r.provider == "openai"
    print("OK RED-9: gemini cae ->"
          " openai responde solo")


def test_provenance_registrado(
    tmp_path, monkeypatch) -> None:
    """RED-9 completo: chain ejecuta y
    AIEngine registra el provenance."""
    body = json.dumps({
        "candidates": [{"content": {
            "parts": [{"text":
                "autentico"}]}}]}).encode()
    monkeypatch.setenv(
        "GEMINI_API_KEY", "AIza-test")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: _R(body))
    engine = _engine(tmp_path)
    engine.register_model(
        model_id="gemini-1.5-flash",
        provider="gemini",
        model_version="1.5",
        capabilities=("document",))
    r = GeminiProvider().analyze(
        "clasifica", "doc")
    rec = engine.record_analysis(
        model_id="gemini-1.5-flash",
        content_sha256=(
            "b" * 64),
        verdict=r.verdict,
        confidence=r.confidence)
    assert rec.model_version == "1.5"
    evs = engine._db.query_all(
        "SELECT event_type FROM"
        " events_outbox WHERE"
        " aggregate_id = ?",
        (rec.analysis_id,))
    tipos = [str(x["event_type"])
             for x in evs]
    assert ("ai.analysis.recorded"
            in tipos)
    print("OK RED-9: analisis ejecutado y"
          " registrado con provenance firmado")
