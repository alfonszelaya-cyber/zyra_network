"""AGRO HTTP surface (menus + operations)."""
from __future__ import annotations

import json
import uuid
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from typing import Any, ClassVar
from urllib.parse import urlparse

from apps.agro.infrastructure.persistence.agro_store import (
    AgroStore,
)
from apps.agro.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.agro.modules.comercializacion.alertas_de_mercado.market_alert_service import (
    MarketAlertService,
)
from apps.agro.services.zyra_link import ZyraLink


class AgroApiHandler(
    BaseHTTPRequestHandler
):
    store: ClassVar[AgroStore]
    link: ClassVar[ZyraLink]
    client: ClassVar[NetworkClient]
    alerts: ClassVar[MarketAlertService] = (
        MarketAlertService()
    )

    def log_message(
        self, format: str, *args: object
    ) -> None:
        return None

    def do_GET(self) -> None:
        self._safe("GET")

    def do_POST(self) -> None:
        self._safe("POST")

    def _safe(self, method: str) -> None:
        try:
            self._route(method)
        except LookupError as exc:
            self._send(
                404,
                {
                    "ok": False,
                    "error": {
                        "type":
                        "not_found",
                        "message": str(
                            exc
                        ),
                    },
                },
            )
        except ValueError as exc:
            self._send(
                400,
                {
                    "ok": False,
                    "error": {
                        "type":
                        "invalid_request",
                        "message": str(
                            exc
                        ),
                    },
                },
            )
        except Exception as exc:
            self._send(
                500,
                {
                    "ok": False,
                    "error": {
                        "type":
                        "internal_error",
                        "message": str(
                            exc
                        ),
                    },
                },
            )

    def _route(self, method: str) -> None:
        path = urlparse(self.path).path
        segments = [
            s
            for s in path.split("/")
            if s
        ]
        if segments[:1] != ["agro"]:
            self._send(
                404,
                {
                    "ok": False,
                    "error": {
                        "type":
                        "not_found",
                        "message":
                        "outside /agro",
                    },
                },
            )
            return
        tail = segments[1:]
        if method == "GET":
            self._get(tail)
        else:
            self._post(tail)

    def _get(self, s: list[str]) -> None:
        store = type(self).store
        if s == ["health"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": {
                        "app": "agro",
                        "status":
                        "operational",
                    },
                },
            )
            return
        if s == ["menu"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": {
                        "title": "AGRO",
                        "subtitle": (
                            "Tu cosecha,"
                            " tus precios,"
                            " tu ayuda"
                            " del gobierno"
                        ),
                        "actions": [
                            {
                                "label":
                                "Vender mi"
                                " cosecha",
                                "route":
                                "/agro/production",
                            },
                            {
                                "label":
                                "Mi historial",
                                "route":
                                "/agro/government/summary",
                            },
                        ],
                    },
                },
            )
            return
        if s == ["producers"]:
            self._ok(
                list(store.list_producers())
            )
            return
        if s == ["productions"]:
            self._ok(
                list(
                    store.list_productions()
                )
            )
            return
        if s == ["government", "summary"]:
            self._ok(store.summary())
            return
        self._not_found()

    def _post(self, s: list[str]) -> None:
        store = type(self).store
        link = type(self).link
        doc = self._read_json()
        if s == ["producers"]:
            name = self._req(
                doc, "name"
            )
            producer_type = self._req(
                doc, "producer_type"
            )
            location = doc.get("location")
            location = (
                str(location)
                if location is not None
                else None
            )
            producer_id = (
                "PRD-"
                + uuid.uuid4().hex[:12]
            )
            zid: str | None = None
            synced = False
            ok, data, _error = (
                link.register_producer_zid(
                    name
                )
            )
            if ok and data is not None:
                zid = str(data.get("zid"))
                synced = True
            row = store.add_producer(
                producer_id=producer_id,
                zid=zid,
                name=name,
                producer_type=(
                    producer_type
                ),
                location=location,
                synced=synced,
            )
            self._send(
                201,
                {
                    "ok": True,
                    "data": row,
                },
            )
            return
        if s == ["producers", "verify"]:
            producer_id = self._req(
                doc, "producer_id"
            )
            row = store.get_producer(
                producer_id
            )
            zid = row.get("zid")
            if zid is None:
                raise ValueError(
                    "producer has no"
                    " network ZID yet"
                )
            ok, data, _error = (
                link.complete_trust(
                    str(zid)
                )
            )
            if not ok:
                raise ValueError(
                    "network trust failed"
                )
            store.mark_verified(
                producer_id=producer_id
            )
            updated = store.get_producer(
                producer_id
            )
            self._ok(updated)
            return
        if s == ["production"]:
            producer_id = self._req(
                doc, "producer_id"
            )
            producer = store.get_producer(
                producer_id
            )
            product = self._req(
                doc, "product"
            )
            quantity = float(
                doc.get("quantity", 0)
            )
            if quantity <= 0:
                raise ValueError(
                    "quantity must be"
                    " positive"
                )
            unit = self._req(
                doc, "unit"
            )
            network_seq: int | None = None
            zid = producer.get("zid")
            if zid is not None:
                ok, data, _error = (
                    link.record_agro_event(
                        str(zid),
                        "production",
                        f"{product}:"
                        f" {quantity}"
                        f" {unit}",
                    )
                )
                if (
                    ok
                    and data is not None
                ):
                    network_seq = int(
                        data.get(
                            "seq", 0
                        )
                    )
            row = store.add_production(
                production_id=(
                    "PRO-"
                    + uuid.uuid4()
                    .hex[:12]
                ),
                producer_id=producer_id,
                product=product,
                quantity=quantity,
                unit=unit,
                network_seq=network_seq,
            )
            self._send(
                201,
                {
                    "ok": True,
                    "data": row,
                },
            )
            return
        if s == ["alerts", "evaluate"]:
            previous = float(
                doc.get(
                    "previous_price", 0
                )
            )
            current = float(
                doc.get("current_price", 0)
            )
            result = (
                type(self).alerts.evaluate(
                    previous,
                    current,
                )
            )
            self._ok(result)
            return
        self._not_found()

    def _read_json(
        self,
    ) -> dict[str, Any]:
        length_header = self.headers.get(
            "Content-Length"
        )
        if length_header is None:
            raise ValueError(
                "Content-Length required"
            )
        raw = self.rfile.read(
            int(length_header)
        )
        parsed: Any = json.loads(
            raw.decode("utf-8")
        )
        if not isinstance(parsed, dict):
            raise ValueError(
                "body must be a JSON"
                " object"
            )
        return {
            str(k): v
            for k, v in parsed.items()
        }

    @staticmethod
    def _req(
        doc: dict[str, Any], key: str
    ) -> str:
        value: Any = doc.get(key)
        if isinstance(value, int) and not isinstance(
            value, bool
        ):
            value = str(value)
        if not isinstance(value, str):
            raise ValueError(
                f"missing field: {key}"
            )
        if not value.strip():
            raise ValueError(
                f"missing field: {key}"
            )
        return value

    def _ok(self, data: Any) -> None:
        self._send(
            200,
            {"ok": True, "data": data},
        )

    def _not_found(self) -> None:
        self._send(
            404,
            {
                "ok": False,
                "error": {
                    "type": "not_found",
                    "message":
                    "unknown route",
                },
            },
        )

    def _send(
        self,
        status: int,
        payload: dict[str, Any],
    ) -> None:
        body = json.dumps(payload).encode(
            "utf-8"
        )
        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.end_headers()
        self.wfile.write(body)


class AgroServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self, address: tuple[str, int]
    ) -> None:
        super().__init__(
            address, AgroApiHandler
        )

    @property
    def bound_port(self) -> int:
        return int(
            self.server_address[1]
        )


def serve_agro(
    store: AgroStore,
    client: NetworkClient,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
) -> AgroServer:
    AgroApiHandler.store = store
    AgroApiHandler.link = ZyraLink(client)
    AgroApiHandler.client = client
    return AgroServer((host, port))
