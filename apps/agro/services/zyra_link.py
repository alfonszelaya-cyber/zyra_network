"""ZyraLink: high-level AGRO operations on the
Network. Never raises - resilience rule."""
from __future__ import annotations

from apps.agro.infrastructure.network.network_client import (
    NetworkClient,
)


class ZyraLink:
    def __init__(
        self, client: NetworkClient
    ) -> None:
        self._client = client

    def register_app(
        self,
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        return self._client.post(
            "/apps/register",
            {
                "app_id": "agro",
                "display_name": (
                    "AGRO - Productores"
                ),
                "scopes": [
                    "display_name",
                    "contact",
                    "address",
                ],
            },
        )

    def register_producer_zid(
        self, display_name: str
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        raise ValueError(
            "registro de productor requiere"
            " biometria: use enroll_producer"
            " con documento y selfie"
        )

    def enroll_producer(
        self,
        *,
        display_name: str,
        doc_image_b64: str,
        selfie_image_b64: str,
        doc_kind: str | None = None,
        doc_country: str | None = None,
        doc_number: str | None = None,
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        payload: dict = {
            "kind": "person",
            "display_name": display_name,
            "actor": "agro",
            "doc_image_b64": doc_image_b64,
            "selfie_image_b64": (
                selfie_image_b64
            ),
        }
        if doc_kind:
            payload["doc_kind"] = doc_kind
        if doc_country:
            payload["doc_country"] = (
                doc_country
            )
        if doc_number:
            payload["doc_number"] = (
                doc_number
            )
        return self._client.post(
            "/identity/enroll", payload
        )

    def complete_trust(
        self, zid: str
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        return self._client.post(
            "/trust/complete",
            {"zid": zid, "actor": "agro"},
        )

    def is_trusted(
        self, zid: str
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        return self._client.get(
            f"/trust/{zid}"
        )

    def record_agro_event(
        self,
        zid: str,
        event: str,
        detail: str,
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        return self._client.post(
            "/history/append",
            {
                "zid": zid,
                "entry_type": "other",
                "actor_app": "agro",
                "payload": {
                    "event": event,
                    "detail": detail,
                },
            },
        )

    def quote_to_usd(
        self,
        *,
        requester_zid: str,
        amount: str,
        currency: str,
    ) -> tuple[
        bool, dict | None, str | None
    ]:
        return self._client.post(
            "/currency/quote",
            {
                "base": str(
                    currency or "USD"
                ).upper(),
                "quote_ccy": "USD",
                "requester_zid": (
                    requester_zid
                ),
            },
        )

    def network_status(self) -> dict:
        ok, data, err = (
            self._client.get("/health")
        )
        return {
            "reachable": bool(ok),
            "error": (
                str(err)
                if err
                else None
            ),
            "catalog_events": len(
                AGRO_EVENT_CATALOG
            ),
    }


AGRO_EVENT_CATALOG = {
    "producer.registered": ("producer_id",),
    "producer.verified": ("producer_id",),
    "asset.registered": (
        "producer_id",
        "asset_type",
        "asset_id",
    ),
    "unit.created": (
        "producer_id",
        "unit_id",
    ),
    "plan.created": (
        "producer_id",
        "plan_id",
    ),
    "plan.harvested": (
        "producer_id",
        "plan_id",
    ),
    "sale.created": (
        "producer_id",
        "sale_id",
    ),
    "sale.completed": (
        "producer_id",
        "sale_id",
    ),
    "risk.detected": (
        "producer_id",
        "risk_type",
    ),
    "incident.created": (
        "producer_id",
        "incident_id",
    ),
    "aid.requested": (
        "producer_id",
        "aid_id",
    ),
    "aid.delivered": (
        "producer_id",
        "aid_id",
    ),
}


def validate_agro_event(
    event_type, payload,
):
    if str(event_type) not in (
        AGRO_EVENT_CATALOG
    ):
        raise ValueError(
            "evento desconocido: "
            + str(event_type)
        )
    required = AGRO_EVENT_CATALOG[
        str(event_type)
    ]
    missing = []
    for field in required:
        if not str(
            (payload or {}).get(field)
            or ""
        ).strip():
            missing.append(field)
    if missing:
        raise ValueError(
            "campos faltantes: "
            + ", ".join(missing)
        )
    return True


def _event_key(event_type, payload):
    import hashlib as _hl
    import json as _json
    canonical = _json.dumps(
        payload or {}, sort_keys=True
    )
    return _hl.sha256(
        (
            str(event_type)
            + "|"
            + canonical
        ).encode("utf-8")
    ).hexdigest()


def _outbox_db(db):
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_event_outbox ("
        " event_key TEXT PRIMARY KEY,"
        " event_type TEXT NOT NULL,"
        " payload TEXT NOT NULL,"
        " zid TEXT,"
        " status TEXT NOT NULL,"
        " attempts INTEGER NOT NULL"
        " DEFAULT 0,"
        " last_error TEXT,"
        " created_at TEXT,"
        " updated_at TEXT)"
    )


def emit_event_db(
    db, link, *,
    zid, event_type, payload,
):
    import json as _json
    import time as _t
    validate_agro_event(
        event_type, payload
    )
    key = _event_key(event_type, payload)
    _outbox_db(db)
    row = None
    for fname in ("query_one", "query"):
        fn = getattr(db, fname, None)
        if callable(fn):
            try:
                row = fn(
                    "SELECT status FROM"
                    " agro_event_outbox"
                    " WHERE event_key = ?",
                    (key,),
                )
            except Exception:
                row = None
            if row:
                break
    if row:
        try:
            prior = str(row["status"])
        except Exception:
            prior = str(row[0])
        if prior == "sent":
            return {
                "event_key": key,
                "deduplicated": True,
                "status": "sent",
            }
    payload_json = _json.dumps(
        payload or {}, sort_keys=True
    )
    detail = _json.dumps(
        {
            "event_type": str(event_type),
            **(payload or {}),
        },
        sort_keys=True,
    )
    ok, data, err = link.record_agro_event(
        zid, str(event_type), detail
    )
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    status = "sent" if ok else "failed"
    if row:
        db.execute(
            "UPDATE"
            " agro_event_outbox SET"
            " status = ?, attempts ="
            " attempts + 1,"
            " last_error = ?, zid = ?,"
            " updated_at = ? WHERE"
            " event_key = ?",
            (status, str(err or ""),
             str(zid), ts, key),
        )
    else:
        db.execute(
            "INSERT INTO"
            " agro_event_outbox ("
            " event_key, event_type,"
            " payload, zid, status,"
            " attempts, last_error,"
            " created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, 1,"
            " ?, ?, ?)",
            (key, str(event_type),
             payload_json, str(zid),
             status, str(err or ""),
             ts, ts),
        )
    return {
        "event_key": key,
        "sent": bool(ok),
        "status": status,
        "error": (
            str(err) if err else None
        ),
    }


def outbox_stats_db(db):
    rows = []
    for name in (
        "query_all", "query", "fetchall"
    ):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT status,"
                    " COUNT(*) AS n FROM"
                    " agro_event_outbox"
                    " GROUP BY status"
                )
            except Exception:
                got = None
            if got:
                rows = list(got)
                break
    by_status = {}
    total = 0
    for r in rows:
        try:
            st = str(r["status"])
            n = int(r["n"])
        except Exception:
            continue
        by_status[st] = n
        total += n
    return {
        "total": total,
        "by_status": by_status,
    }


def outbox_pending_db(db, limit=20):
    for name in (
        "query_all", "query", "fetchall"
    ):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT event_key,"
                    " event_type, payload,"
                    " zid, status, attempts,"
                    " last_error, updated_at"
                    " FROM"
                    " agro_event_outbox"
                    " WHERE status !="
                    " 'sent' ORDER BY"
                    " updated_at LIMIT ?",
                    (int(limit),),
                )
            except Exception:
                got = None
            if got:
                return [
                    dict(r) for r in got
                ]
    return []


def retry_pending_db(
    db, link, zid, limit=10,
):
    rows = outbox_pending_db(
        db, limit=limit
    )
    results = []
    for r in rows:
        import json as _json
        try:
            payload = _json.loads(
                str(r.get("payload"))
            )
        except Exception:
            payload = {}
        res = emit_event_db(
            db, link,
            zid=str(
                r.get("zid") or zid
            ),
            event_type=str(
                r.get("event_type")
            ),
            payload=payload,
        )
        results.append(res)
    return {
        "retried": len(results),
        "results": results,
    }
