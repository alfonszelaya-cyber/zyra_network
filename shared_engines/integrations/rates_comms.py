
"""Conectores de comunicacion de la Red
(Brevo email + Firebase push). Las keys
viven en variables de entorno del dueno:
BREVO_API_KEY / FCM_SERVER_KEY. Sin key,
fallan HONESTO con not_configured —
nunca crash, nunca inventan envios."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request


class _HttpBase:
    """POST JSON con headers."""

    name = "base"

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._timeout = timeout_seconds

    def _post_json(self, url: str,
                   payload: dict,
                   headers: dict):
        body = json.dumps(
            payload).encode("utf-8")
        h = {
            "Content-Type":
            "application/json"}
        h.update(headers)
        req = urllib.request.Request(
            url,
            data=body,
            headers=h,
            method="POST")
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


class BrevoConnector(_HttpBase):
    """Email transaccional (300/dia
    en el plan gratuito de Brevo)."""

    name = "brevo"

    def __init__(
        self,
        *,
        api_key: str = "",
        timeout_seconds: float = 15.0,
    ) -> None:
        super().__init__(
            timeout_seconds=timeout_seconds)
        self._api_key = (
            api_key
            or os.environ.get(
                "BREVO_API_KEY", ""))

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def send_email(
        self, *,
        to_email: str,
        to_name: str = "",
        subject: str,
        html: str,
        sender_email: str,
        sender_name: str = "ZYRA Network",
    ) -> dict:
        """Envia un email. Sin key:
        {'sent': False, 'reason':
        'not_configured'} — honesto."""
        if not self.is_configured():
            return {
                "source": self.name,
                "sent": False,
                "reason":
                "not_configured",
                "hint": "define BREVO_API_KEY",
            }
        url = ("https://api.brevo.com"
               "/v3/smtp/email")
        payload = {
            "sender": {
                "email": sender_email,
                "name": sender_name},
            "to": [{"email": to_email,
                    "name": to_name}],
            "subject": subject,
            "htmlContent": html,
        }
        try:
            d = self._post_json(
                url,
                payload,
                headers={
                    "api-key":
                    self._api_key})
        except Exception as exc:
            return {
                "source": self.name,
                "sent": False,
                "error":
                type(exc).__name__,
            }
        resumen = {
            "source": self.name,
            "sent": True,
            "message_id": d.get(
                "messageId"),
            "to": to_email,
        }
        resumen["sha256"] = self._sha(
            resumen)
        return resumen


class FcmConnector(_HttpBase):
    """Push notifications via
    Firebase Cloud Messaging (HTTP v1
    legacy: server key)."""

    name = "fcm"

    def __init__(
        self,
        *,
        server_key: str = "",
        timeout_seconds: float = 15.0,
    ) -> None:
        super().__init__(
            timeout_seconds=timeout_seconds)
        self._key = (
            server_key
            or os.environ.get(
                "FCM_SERVER_KEY", ""))

    def is_configured(self) -> bool:
        return bool(self._key)

    def send_push(
        self, *,
        device_token: str,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> dict:
        """Envia push a un dispositivo.
        Sin key: honesto not_configured."""
        if not self.is_configured():
            return {
                "source": self.name,
                "sent": False,
                "reason":
                "not_configured",
                "hint":
                "define FCM_SERVER_KEY",
            }
        url = ("https://fcm.googleapis.com"
               "/fcm/send")
        payload = {
            "to": device_token,
            "notification": {
                "title": title,
                "body": body},
            "data": data or {},
        }
        try:
            d = self._post_json(
                url,
                payload,
                headers={
                    "Authorization":
                    "key="
                    + self._key})
        except Exception as exc:
            return {
                "source": self.name,
                "sent": False,
                "error":
                type(exc).__name__,
            }
        resumen = {
            "source": self.name,
            "sent": (d.get("success", 0)
                     == 1),
            "message_id": d.get(
                "message_id"),
        }
        resumen["sha256"] = self._sha(
            resumen)
        return resumen
