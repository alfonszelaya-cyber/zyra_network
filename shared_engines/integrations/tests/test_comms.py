
"""Tests comunicacion (mockeados + honesto sin key)."""
from __future__ import annotations

import json

from shared_engines.integrations.rates_comms import (
    BrevoConnector,
    FcmConnector,
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


def test_brevo_sin_key_honesto(
    tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(
        "BREVO_API_KEY", raising=False)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: (
            (_ for _ in ()).throw(
                AssertionError(
                    "no debe llamar red sin key"))))
    r = BrevoConnector().send_email(
        to_email="a@b.com",
        subject="x", html="<p>y</p>",
        sender_email="no@reply.zyra")
    assert r["sent"] is False
    assert r["reason"] == "not_configured"
    print("OK comms: brevo sin key ="
          " not_configured, cero llamada")


def test_brevo_envia_con_key(
    tmp_path, monkeypatch) -> None:
    body = json.dumps({
        "messageId": "<abc@brevo>"}).encode()
    monkeypatch.setenv(
        "BREVO_API_KEY", "xkeys-test-123")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: _R(body))
    r = BrevoConnector().send_email(
        to_email="pedro@sv.com",
        to_name="Pedro",
        subject="Tu remesa llego",
        html="<b>775 GTQ</b>",
        sender_email="no@reply.zyra")
    assert r["sent"] is True
    assert r["message_id"] == "<abc@brevo>"
    assert r["sha256"]
    print("OK comms: brevo email de"
          " remesa enviado con key")


def test_fcm_sin_key_honesto(
    tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(
        "FCM_SERVER_KEY", raising=False)
    r = FcmConnector().send_push(
        device_token="tok123",
        title="Pago",
        body="Recibiste 100 USD")
    assert r["sent"] is False
    assert r["reason"] == "not_configured"
    print("OK comms: fcm sin key ="
          " not_configured")


def test_fcm_envia_con_key(
    tmp_path, monkeypatch) -> None:
    body = json.dumps({
        "success": 1,
        "message_id": 98765}).encode()
    monkeypatch.setenv(
        "FCM_SERVER_KEY", "AAAA-test")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: _R(body))
    r = FcmConnector().send_push(
        device_token="tok123",
        title="Remesa",
        body="Llego tu dinero",
        data={"payment_id": "PAY-1"})
    assert r["sent"] is True
    assert r["message_id"] == 98765
    print("OK comms: fcm push de"
          " remesa enviado con key")
