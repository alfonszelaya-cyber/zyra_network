"""AGRO routers (CONSOL-3 fase A, regla 77)
- metodos extraidos de server.py
- cada funcion recibe handler_self como primer parametro
- comportamiento identico, codigo reubicado"""
from __future__ import annotations


def _aid_payload(self) -> dict:
    content_type = self.headers.get(
        "Content-Type", ""
    )
    if "application/json" in content_type:
        return self._read_json()
    return self._read_form()

def _aid_network_seq(
    self,
    zid: str | None,
    event: str,
    detail: str,
) -> int | None:
    if zid is None:
        return None
    ok, data, _error = type(self).link.record_agro_event(
        str(zid), event, detail
    )
    if ok and data is not None:
        try:
            return int(data.get("seq", 0))
        except Exception:
            return None
    return None

def _aid_request(self) -> None:
    store = type(self).store
    doc = self._aid_payload()
    producer_id = self._req(doc, "producer_id")
    producer = store.get_producer(producer_id)
    program = self._req(doc, "program")
    item = self._req(doc, "item")
    quantity = float(doc.get("quantity", 1))
    if quantity <= 0:
        raise ValueError(
            "quantity must be positive"
        )
    network_seq = self._aid_network_seq(
        producer.get("zid"),
        "AID_REQUESTED",
        program + ": " + item,
    )
    aid = store.create_aid_request(
        aid_id="AID-" + uuid.uuid4().hex[:10],
        producer_id=producer_id,
        program=program,
        item=item,
        quantity=quantity,
        network_seq=network_seq,
    )
    self._send(201, {"ok": True, "data": aid})

def _aid_eligibility(self) -> None:
    store = type(self).store
    doc = self._aid_payload()
    aid_id = self._req(doc, "aid_id")
    aid = store.get_aid(aid_id)
    producer = store.get_producer(
        str(aid["producer_id"])
    )
    eligible = bool(producer.get("verified"))
    reason = (
        "productor verificado"
        if eligible
        else "productor sin verificar"
    )
    network_seq = self._aid_network_seq(
        aid.get("zid"),
        "AID_ELIGIBILITY_EVALUATED",
        reason,
    )
    result = store.evaluate_aid(
        aid_id=aid_id,
        eligible=eligible,
        reason=reason,
        network_seq=network_seq,
    )
    self._send(200, {"ok": True, "data": result})

def _aid_approve(self) -> None:
    store = type(self).store
    doc = self._aid_payload()
    aid_id = self._req(doc, "aid_id")
    aid = store.get_aid(aid_id)
    network_seq = self._aid_network_seq(
        aid.get("zid"),
        "AID_APPROVED",
        str(aid["program"]),
    )
    result = store.approve_aid(
        aid_id=aid_id, network_seq=network_seq
    )
    self._send(200, {"ok": True, "data": result})

def _aid_assign(self) -> None:
    store = type(self).store
    doc = self._aid_payload()
    aid_id = self._req(doc, "aid_id")
    detail = str(doc.get("detail") or "").strip() or None
    aid = store.get_aid(aid_id)
    network_seq = self._aid_network_seq(
        aid.get("zid"),
        "AID_ASSIGNED",
        detail or str(aid["program"]),
    )
    result = store.assign_aid(
        aid_id=aid_id,
        detail=detail,
        network_seq=network_seq,
    )
    self._send(200, {"ok": True, "data": result})

def _aid_deliver(self) -> None:
    store = type(self).store
    doc = self._aid_payload()
    aid_id = self._req(doc, "aid_id")
    detail = str(doc.get("detail") or "").strip() or None
    aid = store.get_aid(aid_id)
    network_seq = self._aid_network_seq(
        aid.get("zid"),
        "AID_DELIVERED",
        detail or str(aid["item"]),
    )
    result = store.deliver_aid(
        aid_id=aid_id,
        detail=detail,
        network_seq=network_seq,
    )
    self._send(200, {"ok": True, "data": result})

def _aid_confirm(self) -> None:
    store = type(self).store
    doc = self._aid_payload()
    aid_id = self._req(doc, "aid_id")
    aid = store.get_aid(aid_id)
    network_seq = self._aid_network_seq(
        aid.get("zid"),
        "AID_DELIVERY_CONFIRMED",
        str(aid["program"]),
    )
    result = store.confirm_aid(
        aid_id=aid_id, network_seq=network_seq
    )
    self._send(200, {"ok": True, "data": result})

def _screen_ayudas(
    self, producer_id: str,
) -> None:
    store = type(self).store
    row = store.get_producer(producer_id)
    aids = store.list_aid(
        producer_id=producer_id
    )
    rows = "".join(
        "<li>- "
        + str(a["program"])
        + ": "
        + str(a["item"])
        + " - "
        + str(a["status"])
        + "</li>"
        for a in aids
    )
    if not rows:
        rows = (
            "<li>Sin ayudas todavia</li>"
        )
    body = (
        "<h1>Mis ayudas del Gobierno</h1>"
        "<p>"
        + str(row.get("name"))
        + "</p>"
        "<ul>"
        + rows
        + "</ul>"
        "<a href='/agro'><button"
        " class='gray'>Inicio"
        "</button></a>"
    )
    self._html(
        200,
        _page("AGRO - Ayudas", body),
    )

def _screen_ayudas_gobierno(
    self,
) -> None:
    store = type(self).store
    summary = store.aid_summary()
    rows = "".join(
        "<li>- "
        + str(program)
        + ": "
        + str(info["requests"])
        + " solicitudes, cantidad "
        + str(info["quantity"])
        + "</li>"
        for program, info in summary["aid_by_program"].items()
    )
    if not rows:
        rows = (
            "<li>Sin solicitudes de ayuda</li>"
        )
    body = (
        "<h1>Ayudas gubernamentales</h1>"
        "<p>Total: "
        + str(summary["aid_total"])
        + "</p>"
        "<h2>Por programa</h2><ul>"
        + rows
        + "</ul>"
        "<a href='/agro'><button"
        " class='gray'>Inicio"
        "</button></a>"
    )
    self._html(
        200,
        _page("AGRO - Ayudas", body),
    )