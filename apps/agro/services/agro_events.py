"""AGRO events - connect all important flows
to the Network via ZyraLink. Never raises."""
from __future__ import annotations

from apps.agro.services.zyra_link import (
    ZyraLink,
)


class AgroEventService:
    def __init__(self, *, store, link):
        self._store = store
        self._link = link

    def _emit(self, producer_id, event, detail):
        try:
            producer = self._store.get_producer(
                producer_id
            )
        except LookupError:
            return None
        zid = producer.get("zid")
        if not zid:
            return None
        try:
            ok, data, _err = (
                self._link.record_agro_event(
                    str(zid), event, detail
                )
            )
        except Exception:
            return None
        if not ok or data is None:
            return None
        for key in (
            "seq",
            "sequence",
            "network_seq",
            "entry_seq",
        ):
            value = data.get(key)
            if isinstance(value, int):
                return value
        return None

    def producer_registered(
        self, *, producer_id, producer_type,
    ):
        return self._emit(
            producer_id,
            "producer.registered",
            "type=" + producer_type,
        )

    def producer_verified(
        self, *, producer_id,
    ):
        return self._emit(
            producer_id,
            "producer.verified",
            "verified=True",
        )

    def production_registered(
        self,
        *,
        producer_id,
        product,
        quantity,
        unit,
    ):
        return self._emit(
            producer_id,
            "production.registered",
            f"{product}: {quantity} {unit}",
        )

    def sale_created(
        self, *, producer_id, sale_id, detail,
    ):
        return self._emit(
            producer_id,
            "sale.created",
            f"{sale_id}: {detail}",
        )

    def sale_completed(
        self, *, producer_id, sale_id,
    ):
        return self._emit(
            producer_id,
            "sale.completed",
            sale_id,
        )

    def aid_transition(
        self, *, producer_id, aid_id, transition,
    ):
        clean = transition.lower()
        if clean.startswith("aid_"):
            clean = clean[4:]
        return self._emit(
            producer_id,
            "aid." + clean,
            aid_id,
        )

    def risk_detected(
        self, *, producer_id, risk_type, detail,
    ):
        return self._emit(
            producer_id,
            "risk.detected",
            f"{risk_type}: {detail}",
        )

    def incident_created(
        self,
        *,
        producer_id,
        incident_id,
        detail,
    ):
        return self._emit(
            producer_id,
            "incident.created",
            f"{incident_id}: {detail}",
        )

    def asset_registered(
        self, *, producer_id, asset_type, detail,
    ):
        return self._emit(
            producer_id,
            "asset.registered",
            f"{asset_type}: {detail}",
        )
