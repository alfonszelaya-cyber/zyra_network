"""AGRO HTTP surface v4: role screens + JSON API
dual mode."""
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
    ROLES,
    AgroStore,
)
from apps.agro.infrastructure.network.network_client import (
    NetworkClient,
)
from apps.agro.modules.comercializacion.alertas_de_mercado.market_alert_service import (
    MarketAlertService,
)
from apps.agro.services.zyra_link import ZyraLink

_CSS = (
    "body{font-family:system-ui,sans-serif;"
    "background:#0d1117;color:#e6edf3;"
    "display:flex;justify-content:center;"
    "padding:20px;margin:0}"
    ".wrap{max-width:680px;width:100%}"
    "h1{font-size:1.3rem}"
    "h2{font-size:1rem;margin-top:20px;"
    "color:#58a6ff}"
    ".card{background:#161b22;border:1px solid"
    " #30363d;border-radius:10px;padding:14px;"
    "margin-top:10px}"
    "button{background:#238636;color:#fff;"
    "border:none;padding:12px 18px;border-radius:8px;"
    "font-size:1rem;cursor:pointer;margin:6px 4px"
    " 0 0;width:100%;text-align:left}"
    "button.gray{background:#30363d}"
    "input,select{width:100%;box-sizing:border-box;"
    "background:#0d1117;color:#e6edf3;"
    "border:1px solid #30363d;border-radius:6px;"
    "padding:8px;margin:4px 0;font-size:0.95rem}"
)


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html><html lang='es'><head>"
        "<meta charset='utf-8'>"
        "<meta name='viewport' content='width="
        "device-width, initial-scale=1'>"
        f"<title>{title}</title>"
        f"<style>{_CSS}</style></head><body>"
        f"<div class='wrap'>{body}</div></body>"
        "</html>"
    )


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
            self._send(
                200,
                {
                    "ok": True,
                    "data": list(
                        store.list_producers()
                    ),
                },
            )
            return
        if s == ["aid"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": list(
                        store.list_aid()
                    ),
                },
            )
            return
        if len(s) == 2 and s[0] == "aid":
            self._send(
                200,
                {
                    "ok": True,
                    "data": store.get_aid(
                        s[1]
                    ),
                },
            )
            return
        if s == ["ayudas"]:
            self._screen_ayudas_gobierno()
            return
        if len(s) == 2 and s[0] == "ayudas":
            self._screen_ayudas(s[1])
            return
        if s == ["government", "summary"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": store.summary(),
                },
            )
            return
        if s == ["gobierno", "seguridad"]:
            from apps.agro.modules.gobierno.seguridad_alimentaria.food_security_service import (
                FoodSecurityService,
            )
            st_data = FoodSecurityService(
                type(self).store
            ).national_status()
            rows = ""
            for x in st_data["products"]:
                rows = rows + "<li>" + x["product"] + ": " + str(x["quantity"]) + " producidas</li>"
            if not rows:
                rows = "<li>Sin produccion registrada</li>"
            body = (
                "<h1>Seguridad alimentaria</h1>"
                "<p>Productores: " + str(st_data["producers_total"])
                + " - verificados: " + str(st_data["producers_verified"]) + "</p>"
                "<ul>" + rows + "</ul>"
                "<a href='/agro/gobierno'><button>Volver</button></a>"
            )
            self._html(200, _page("AGRO - Seguridad alimentaria", body))
            return
        if s == ["gobierno", "beneficiados"]:
            from apps.agro.modules.gobierno.apoyos.government_aid_service import (
                GovernmentAidService,
            )
            rep = GovernmentAidService(
                type(self).store
            ).beneficiaries_report()
            b = ""
            for r in rep["beneficiados"]:
                b = b + "<li>" + r["name"] + " (" + str(r["aid_count"]) + " ayudas)</li>"
            if not b:
                b = "<li>Ninguno aun</li>"
            nb = ""
            for r in rep["no_beneficiados"]:
                nb = nb + "<li>" + r["name"] + " - sin ayudas (" + r["role"] + ")</li>"
            if not nb:
                nb = "<li>Todos beneficiados</li>"
            body = (
                "<h1>Ayudas: beneficiados y pendientes</h1>"
                "<p>Total ayudas: " + str(rep["aid_total"]) + "</p>"
                "<h2>Beneficiados</h2><ul>" + b + "</ul>"
                "<h2>No beneficiados (a quienes ayudar)</h2><ul>" + nb + "</ul>"
                "<a href='/agro/gobierno'><button>Volver</button></a>"
            )
            self._html(200, _page("AGRO - Beneficiarios", body))
            return
        if s == ["gobierno", "riesgos"]:
            areas = self._ZYRA_AREAS_V2()
            rows = ""
            for p in type(self).store.list_producers():
                for r in areas.open_risks(
                    producer_id=str(p.get("producer_id"))
                ):
                    rows = rows + "<li>" + str(p.get("name")) + ": " + str(r.get("risk_type")) + " (" + str(r.get("severity")) + ")</li>"
            if not rows:
                rows = "<li>Sin riesgos abiertos</li>"
            body = (
                "<h1>Riesgos abiertos</h1>"
                "<ul>" + rows + "</ul>"
                "<a href='/agro/gobierno'><button>Volver</button></a>"
            )
            self._html(200, _page("AGRO - Riesgos", body))
            return
        if s == ["mercado"]:
            prods = type(self).store.list_productions()
            rows = ""
            for p in prods:
                rows = rows + "<li>" + str(p.get("product")) + " - " + str(p.get("quantity")) + " " + str(p.get("unit")) + "</li>"
            if not rows:
                rows = "<li>Sin produccion disponible</li>"
            body = (
                "<h1>Mercado AGRO</h1>"
                "<h2>Produccion disponible</h2><ul>" + rows + "</ul>"
                "<h2>Comprar / exportar</h2>"
                "<p>Registre su empresa en la Red (ZID de organizacion) y contacte al productor.</p>"
                "<a href='/agro'><button>Inicio</button></a>"
            )
            self._html(200, _page("AGRO - Mercado", body))
            return
        if len(s) == 2 and s[0] == "areas":
            a = self._ZYRA_AREAS_V2()
            self._send(200, {"ok": True, "data": {
                "lands": a.lands_of(producer_id=s[1]),
                "sales": a.sales_of(producer_id=s[1]),
                "risks": a.open_risks(producer_id=s[1]),
                "machinery": a.machinery_of(producer_id=s[1]),
                "inventory": a.inventory_of(producer_id=s[1]),
                "water": a.water_sources_of(producer_id=s[1]),
            }})
            return
        if not s or s == ["home"]:
            self._home()
            return
        if s[0] == "productor":
            self._screen_producer(s)
            return
        if s[0] == "gobierno":
            self._screen_government()
            return
        if s[0] == "banco":
            self._screen_bank()
            return
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

    def _ZYRA_AREAS_V2(self):
        store = type(self).store
        from apps.agro.infrastructure.persistence.agro_area_store import (
            AgroAreaStore,
        )
        return AgroAreaStore(store._db, store._clock)

    def _ZYRA_EVENTS_V2(self):
        store = type(self).store
        from apps.agro.services.agro_events import (
            AgroEventService,
        )
        return AgroEventService(
            store=store,
            link=type(self).link,
        )

    def _ZYRA_PAYLOAD_V2(self, is_json):
        if is_json:
            return self._read_json()
        return self._read_form()

    def _ZYRA_MENUS_V2(self):
        items = []
        names = (
            "atencion_al_cliente",
            "comercializacion",
            "ejecutivo",
            "gobierno",
            "insumos_y_apoyos",
            "operaciones",
            "produccion",
            "productores",
            "recursos_y_activos",
            "riesgo",
            "seguridad",
        )
        for name in names:
            try:
                mod = __import__(
                    "apps.agro.modules." + name + ".menu",
                    fromlist=["menu"],
                )
                fn = getattr(mod, "menu", None)
                if callable(fn):
                    items.append(fn())
            except Exception:
                continue
        return items

    def _post(self, s: list[str]) -> None:
        store = type(self).store
        link = type(self).link
        content_type = self.headers.get(
            "Content-Type", ""
        )
        is_json = (
            "application/json"
            in content_type
        )
        if s == ["land"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            row = self._ZYRA_AREAS_V2().add_land(
                producer_id=pid,
                location=self._req(doc, "location"),
                size_hectares=float(doc.get("size_hectares") or 0),
                land_use=str(doc.get("land_use") or ""),
            )
            self._ZYRA_EVENTS_V2().asset_registered(
                producer_id=pid,
                asset_type="tierra",
                detail=str(row["land_id"]),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["machinery"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            row = self._ZYRA_AREAS_V2().add_machinery(
                producer_id=pid,
                machine_type=self._req(doc, "machine_type"),
                description=str(doc.get("description") or ""),
            )
            self._ZYRA_EVENTS_V2().asset_registered(
                producer_id=pid,
                asset_type="maquinaria",
                detail=str(row["machine_id"]),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["inventory"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            row = self._ZYRA_AREAS_V2().add_inventory_item(
                producer_id=pid,
                item_name=self._req(doc, "item_name"),
                quantity=float(doc.get("quantity") or 0),
                unit=str(doc.get("unit") or ""),
            )
            self._ZYRA_EVENTS_V2().asset_registered(
                producer_id=pid,
                asset_type="inventario",
                detail=str(doc.get("item_name", "")),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["water"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            row = self._ZYRA_AREAS_V2().add_water_source(
                producer_id=pid,
                source_type=self._req(doc, "source_type"),
                capacity_liters=float(doc.get("capacity_liters") or 0),
            )
            self._ZYRA_EVENTS_V2().asset_registered(
                producer_id=pid,
                asset_type="agua",
                detail=str(doc.get("source_type", "")),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["sale"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            row = self._ZYRA_AREAS_V2().create_sale(
                producer_id=pid,
                buyer=self._req(doc, "buyer"),
                product=self._req(doc, "product"),
                quantity=float(doc.get("quantity") or 0),
                unit=str(doc.get("unit") or ""),
                price=float(doc.get("price") or 0),
            )
            seq = self._ZYRA_EVENTS_V2().sale_created(
                producer_id=pid,
                sale_id=str(row["sale_id"]),
                detail=str(row.get("product", "")),
            )
            out = dict(row)
            out["network_seq"] = seq
            self._send(201, {"ok": True, "data": out})
            return
        if s == ["sale", "complete"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            sid = self._req(doc, "sale_id")
            row = self._ZYRA_AREAS_V2().complete_sale(sale_id=sid)
            self._ZYRA_EVENTS_V2().sale_completed(
                producer_id=str(row.get("producer_id", "")),
                sale_id=sid,
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["risk"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            row = self._ZYRA_AREAS_V2().report_risk(
                producer_id=pid,
                risk_type=self._req(doc, "risk_type"),
                severity=str(doc.get("severity") or "media"),
                detail=str(doc.get("detail") or ""),
            )
            self._ZYRA_EVENTS_V2().risk_detected(
                producer_id=pid,
                risk_type=str(row.get("risk_type", "")),
                detail=str(row.get("detail", "")),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["risk", "resolve"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_AREAS_V2().resolve_risk(
                risk_id=self._req(doc, "risk_id"),
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["producers"]:
            if is_json:
                doc = self._read_json()
            else:
                doc = self._read_form()
            name = self._req(doc, "name")
            producer_type = self._req(
                doc, "producer_type"
            )
            role = str(
                doc.get("role", "agricultor")
            )
            if role not in ROLES:
                raise ValueError(
                    f"unknown role: {role}"
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
            doc_b64 = str(
                doc.get("doc_image_b64") or ""
            )
            selfie_b64 = str(
                doc.get("selfie_image_b64") or ""
            )
            if not doc_b64 or not selfie_b64:
                if is_json:
                    raise ValueError(
                        "por ley se requiere"
                        " doc_image_b64 y selfie_image_b64"
                    )
                self._html(
                    400,
                    _page(
                        "AGRO - Registro",
                        "<h1>Faltan las fotos</h1>"
                        "<p>Por ley el registro requiere"
                        " foto del documento y selfie en vivo.</p>"
                        "<a href='/agro/home'>"
                        "<button>Volver</button></a>",
                    ),
                )
                return

            def _prd_find_zid(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if (
                            str(k).lower() == "zid"
                            and isinstance(v, str)
                            and v.startswith("ZID-")
                        ):
                            return v
                    for v in obj.values():
                        found = _prd_find_zid(v)
                        if found is not None:
                            return found
                elif isinstance(obj, list):
                    for item in obj:
                        found = _prd_find_zid(item)
                        if found is not None:
                            return found
                return None
            zid: str | None = None
            synced = False
            ok, data, _error = (
                link.enroll_producer(
                    display_name=name,
                    doc_image_b64=doc_b64,
                    selfie_image_b64=selfie_b64,
                )
            )
            if not ok:
                _errtxt = str(_error or "")
                _low = _errtxt.lower()
                _ZYRA_OFFLINE_ = any(
                    m in _low
                    for m in (
                        "urlopen error",
                        "connection refused",
                        "connection reset",
                        "timed out",
                        "timeout",
                        "unreachable",
                        "errno",
                        "max retries",
                    )
                )
                if not _ZYRA_OFFLINE_:
                    if is_json:
                        raise ValueError(
                            "registro rechazado: " + _errtxt
                        )
                    self._html(
                        400,
                        _page(
                            "AGRO - Registro rechazado",
                            "<h1>Registro rechazado</h1>"
                            "<p>" + _errtxt + "</p>"
                            "<a href='/agro/home'>"
                            "<button>Volver</button></a>",
                        ),
                    )
                    return
                # Resiliencia (principio de la Red, probado
                # en AGRO y NEXO): red inalcanzable -> la app
                # vive por si sola. Registro local sin ZID;
                # el ZID se vincula despues via super-app.
                # Un rechazo ACTIVO de la red (biometria,
                # duplicado) sigue rechazando: la ley no se
                # abre.
                row = store.add_producer(
                    producer_id=producer_id,
                    zid=None,
                    name=name,
                    producer_type=(
                        producer_type
                    ),
                    role=role,
                    location=location,
                    synced=False,
                )
                if is_json:
                    self._send(
                        201,
                        {
                            "ok": True,
                            "data": row,
                        },
                    )
                else:
                    self._html(
                        200,
                        _page(
                            "Registro listo",
                            "<h1>Registro listo"
                            "</h1><p>Tu ID: <b>"
                            + producer_id
                            + "</b></p>"
                            "<a href='/agro/productor/"
                            + producer_id
                            + "'><button>Ir a mi"
                            " panel</button></a>",
                        ),
                    )
                return
            if data is not None:
                zid = _prd_find_zid(data)
                synced = zid is not None
            row = store.add_producer(
                producer_id=producer_id,
                zid=zid,
                name=name,
                producer_type=(
                    producer_type
                ),
                role=role,
                location=location,
                synced=synced,
            )
            if is_json:
                self._send(
                    201,
                    {
                        "ok": True,
                        "data": row,
                    },
                )
            else:
                self._html(
                    200,
                    _page(
                        "Registro listo",
                        "<h1>Registro listo"
                        "</h1><p>Tu ID: <b>"
                        + producer_id
                        + "</b></p>"
                        "<a href='/agro/productor/"
                        + producer_id
                        + "'><button>Ir a mi"
                        " panel</button></a>",
                    ),
                )
            return
        if s == ["producers", "verify"]:
            if is_json:
                doc = self._read_json()
            else:
                doc = self._read_form()
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
            ok, _data, _error = (
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
            if is_json:
                self._send(
                    200,
                    {
                        "ok": True,
                        "data": updated,
                    },
                )
            else:
                self._html(
                    200,
                    _page(
                        "Verificado",
                        "<h1>Productor"
                        " VERIFICADO</h1>",
                    ),
                )
            return
        if s == ["production"]:
            if is_json:
                doc = self._read_json()
            else:
                doc = self._read_form()
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
            unit = self._req(doc, "unit")
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
                        data.get("seq", 0)
                    )
            row = store.add_production(
                production_id=(
                    "PRO-"
                    + uuid.uuid4().hex[:12]
                ),
                producer_id=producer_id,
                product=product,
                quantity=quantity,
                unit=unit,
                network_seq=network_seq,
            )
            if is_json:
                self._send(
                    201,
                    {
                        "ok": True,
                        "data": row,
                    },
                )
            else:
                self._html(
                    200,
                    _page(
                        "Cosecha"
                        " registrada",
                        "<h1>Guardado en la"
                        " Red</h1><a href="
                        "'/agro'><button>"
                        "Inicio</button></a>",
                    ),
                )
            return
        if s == ["aid", "request"]:
            self._aid_request()
            return
        if s == ["aid", "eligibility"]:
            self._aid_eligibility()
            return
        if s == ["government", "approve"]:
            self._aid_approve()
            return
        if s == ["government", "assign"]:
            self._aid_assign()
            return
        if s == ["government", "deliver"]:
            self._aid_deliver()
            return
        if s == ["government", "confirm"]:
            self._aid_confirm()
            return
        if s == ["alerts", "evaluate"]:
            doc = self._read_json()
            previous = float(
                doc.get(
                    "previous_price", 0
                )
            )
            current = float(
                doc.get(
                    "current_price", 0
                )
            )
            result = (
                type(self).alerts.evaluate(
                    previous, current
                )
            )
            self._send(
                200,
                {
                    "ok": True,
                    "data": result,
                },
            )
            return
        if s == ["register"]:
            doc = self._read_form()
            name = self._req(doc, "name")
            producer_type = self._req(
                doc, "producer_type"
            )
            role = str(
                doc.get("role", "agricultor")
            )
            if role not in ROLES:
                raise ValueError(
                    f"unknown role: {role}"
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
            if not (
                str(doc.get("doc_image_b64") or "")
                and str(doc.get("selfie_image_b64") or "")
            ):
                self._html(
                    400,
                    _page(
                        "AGRO - Registro",
                        "<h1>Faltan las fotos</h1>"
                        "<p>Por ley el registro requiere"
                        " foto del documento y selfie en vivo.</p>"
                        "<a href='/agro/home'>"
                        "<button>Volver</button></a>",
                    ),
                )
                return

            def _agro_find_zid(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if (
                            str(k).lower() == "zid"
                            and isinstance(v, str)
                            and v.startswith("ZID-")
                        ):
                            return v
                    for v in obj.values():
                        found = _agro_find_zid(v)
                        if found is not None:
                            return found
                elif isinstance(obj, list):
                    for item in obj:
                        found = _agro_find_zid(item)
                        if found is not None:
                            return found
                return None

            ok, data, _error = (
                link.enroll_producer(
                    display_name=name,
                    doc_image_b64=str(
                        doc.get("doc_image_b64") or ""
                    ),
                    selfie_image_b64=str(
                        doc.get("selfie_image_b64") or ""
                    ),
                )
            )
            if not ok:
                _errtxt = str(_error or "")
                _low = _errtxt.lower()
                _ZYRA_OFFLINE_ = any(
                    m in _low
                    for m in (
                        "urlopen error",
                        "connection refused",
                        "connection reset",
                        "timed out",
                        "timeout",
                        "unreachable",
                        "errno",
                        "max retries",
                    )
                )
                if not _ZYRA_OFFLINE_:
                    if is_json:
                        raise ValueError(
                            "registro rechazado: " + _errtxt
                        )
                    self._html(
                        400,
                        _page(
                            "AGRO - Registro rechazado",
                            "<h1>Registro rechazado</h1>"
                            "<p>" + _errtxt + "</p>"
                            "<a href='/agro/home'>"
                            "<button>Volver</button></a>",
                        ),
                    )
                    return
                # Resiliencia (principio de la Red, probado
                # en AGRO y NEXO): red inalcanzable -> la app
                # vive por si sola. Registro local sin ZID;
                # el ZID se vincula despues via super-app.
                # Un rechazo ACTIVO de la red (biometria,
                # duplicado) sigue rechazando: la ley no se
                # abre.
                row = store.add_producer(
                    producer_id=producer_id,
                    zid=None,
                    name=name,
                    producer_type=(
                        producer_type
                    ),
                    role=role,
                    location=location,
                    synced=False,
                )
                if is_json:
                    self._send(
                        201,
                        {
                            "ok": True,
                            "data": row,
                        },
                    )
                else:
                    self._html(
                        200,
                        _page(
                            "Registro listo",
                            "<h1>Registro listo"
                            "</h1><p>Tu ID: <b>"
                            + producer_id
                            + "</b></p>"
                            "<a href='/agro/productor/"
                            + producer_id
                            + "'><button>Ir a mi"
                            " panel</button></a>",
                        ),
                    )
                return
            if data is not None:
                zid = _agro_find_zid(data)
            store.add_producer(
                producer_id=producer_id,
                zid=zid,
                name=name,
                producer_type=(
                    producer_type
                ),
                role=role,
                location=location,
                synced=(
                    zid is not None
                ),
            )
            self._html(
                200,
                _page(
                    "Bienvenido a AGRO",
                    "<h1>Registro listo"
                    "</h1><p>Tu ID: <b>"
                    + producer_id
                    + "</b></p>"
                    "<a href='/agro/productor/"
                    + producer_id
                    + "'><button>Ir a mi"
                    " panel</button></a>",
                ),
            )
            return
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

    def _read_form(
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
        ).decode("utf-8")
        doc: dict[str, Any] = {}
        for pair in raw.split("&"):
            if "=" in pair:
                key, value = pair.split(
                    "=", 1
                )
                doc[key] = value.replace(
                    "+", " "
                )
        return doc

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

    def _home(self) -> None:
        body = (
            "<h1>🛡️ AGRO</h1>"
            "<p>La Red de confianza"
            " para agricultores y"
            " ganaderos.</p>"
            "<h2>Soy productor</h2>"
            "<div class='card'>"
            "<form method='POST'"
            " action='/agro/register'>"
            "<input name='name'"
            " placeholder='Mi nombre'>"
            "<select name='role'>"
            "<option value='agricultor'>"
            "Agricultor</option>"
            "<option value='ganadero'>"
            "Ganadero</option>"
            "</select>"
            "<input name='producer_type'"
            " placeholder='Que produzco"
            " (maiz, ganado...)'>"
            "<input name='location'"
            " placeholder='Mi zona'>"
            "<fieldset><legend>1) Foto del documento (por ley)</legend><input type='file' id='agroDoc' accept='image/*' capture='environment'></fieldset>"
            "<fieldset><legend>2) Selfie en vivo</legend>"
            "<video id='agroCam' width='240' height='180' autoplay playsinline muted></video><br>"
            "<button type='button' id='agroSnap'>Capturar selfie</button><br>"
            "o desde archivo: <input type='file' id='agroSelfie' accept='image/*' capture='user'>"
            "</fieldset>"
            "<input type='hidden' name='doc_image_b64' id='agroDocB64'>"
            "<input type='hidden' name='selfie_image_b64' id='agroSelfieB64'>"
            "<canvas id='agroCv' style='display:none'></canvas>"
            "<p id='agroSt'>Estado: pendiente</p>"
            "<script>"
            "(function(){"
            "var doc=document.getElementById('agroDoc');"
            "var slf=document.getElementById('agroSelfie');"
            "var vid=document.getElementById('agroCam');"
            "var cvv=document.getElementById('agroCv');"
            "var cx=cvv.getContext('2d');"
            "var st=document.getElementById('agroSt');"
            "function upd(){st.textContent='Estado: doc='+(document.getElementById('agroDocB64').value?'OK':'falta')+' | selfie='+(document.getElementById('agroSelfieB64').value?'OK':'falta');}"
            "function process(file,target){if(!file){return;}var r=new FileReader();r.onload=function(){var im=new Image();im.onload=function(){var max=800;var k=Math.min(1,max/Math.max(im.width,im.height));cvv.width=Math.round(im.width*k);cvv.height=Math.round(im.height*k);cx.drawImage(im,0,0,cvv.width,cvv.height);var d=cvv.toDataURL('image/jpeg',0.72);document.getElementById(target).value=d.split(',')[1];upd();};im.src=r.result;};r.readAsDataURL(file);}"
            "doc.addEventListener('change',function(){process(doc.files[0],'agroDocB64');});"
            "slf.addEventListener('change',function(){process(slf.files[0],'agroSelfieB64');});"
            "if(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia){navigator.mediaDevices.getUserMedia({video:{facingMode:'user'}}).then(function(s){vid.srcObject=s;}).catch(function(){st.textContent='Camara no disponible: use el archivo.';});}"
            "document.getElementById('agroSnap').addEventListener('click',function(){if(!vid.videoWidth){st.textContent='Camara aun no lista.';return;}var w=480;var k=w/vid.videoWidth;cvv.width=w;cvv.height=Math.round(vid.videoHeight*k);cx.drawImage(vid,0,0,cvv.width,cvv.height);var d=cvv.toDataURL('image/jpeg',0.72);document.getElementById('agroSelfieB64').value=d.split(',')[1];upd();});"
            "})();"
            "</script>"
            "<button>Registrarme en la"
            " Red</button>"
            "</form></div>"
            "<h2>Soy Gobierno / Banco"
            "</h2>"
            "<div class='card'>"
            "<a href='/agro/gobierno'>"
            "<button>Vista Gobierno"
            "</button></a>"
            "<a href='/agro/banco'>"
            "<button class='gray'>Vista"
            " Banco</button></a>"
            "</div>"
        )
        self._html(200, _page("AGRO", body))

    def _screen_producer(
        self, s: list[str]
    ) -> None:
        store = type(self).store
        producer_id = (
            s[1] if len(s) > 1 else ""
        )
        row = store.get_producer(
            producer_id
        )
        if not row or not row.get("name"):
            self._html(
                404,
                _page(
                    "AGRO - Productor",
                    "<h1>Productor no encontrado</h1>"
                    "<a href='/agro'><button>Volver</button></a>",
                ),
            )
            return
        if row.get("verified"):
            badge = "✅ VERIFICADO"
        else:
            badge = "⚠️ Sin verificar (sin bonos)"
        body = (
            "<h1>Mi Panel — " + str(row.get("name")) + "</h1>"
            "<p>" + badge + " · Rol: " + str(row.get("role")) + "</p>"
            "<div class='card'><h2>1) Registrar mi cosecha</h2>"
            "<form method='POST' action='/agro/production'>"
            "<input type='hidden' name='producer_id' value='" + producer_id + "'>"
            "<input name='product' placeholder='Producto (maiz, frijol...)'>"
            "<input name='quantity' placeholder='Cantidad'>"
            "<select name='unit'><option value='quintal'>quintal</option>"
            "<option value='libra'>libra</option></select>"
            "<button>Guardar</button>"
            "</form></div>"
            "<div class='card'><h2>2) Vender mi producto</h2>"
            "<form method='POST' action='/agro/sale'>"
            "<input type='hidden' name='producer_id' value='" + producer_id + "'>"
            "<input name='buyer' placeholder='Comprador'>"
            "<input name='product' placeholder='Producto'>"
            "<input name='quantity' placeholder='Cantidad'>"
            "<select name='unit'><option value='quintal'>quintal</option>"
            "<option value='libra'>libra</option></select>"
            "<input name='price' placeholder='Precio total'>"
            "<button>Vender</button>"
            "</form></div>"
            "<div class='card'><h2>3) Ayuda del Gobierno</h2>"
            "<a href='/agro/ayudas/" + producer_id + "'><button>Ver mis ayudas</button></a>"
            "</div>"
            "<a href='/agro'><button class='gray'>Inicio</button></a>"
        )
        self._html(
            200,
            _page("AGRO - Mi panel", body),
        )

    def _screen_government(self) -> None:
        store = type(self).store
        summary = store.summary()
        from apps.agro.modules.gobierno.seguridad_alimentaria.food_security_service import (
            FoodSecurityService,
        )
        from apps.agro.modules.gobierno.apoyos.government_aid_service import (
            GovernmentAidService,
        )
        fs = FoodSecurityService(store).national_status()
        ay = GovernmentAidService(store).beneficiaries_report()
        areas = self._ZYRA_AREAS_V2()
        riesgos = ""
        for p in store.list_producers():
            for r in areas.open_risks(
                producer_id=str(p.get("producer_id"))
            ):
                riesgos = riesgos + "<li>" + str(p.get("name")) + ": " + str(r.get("risk_type")) + " (" + str(r.get("severity")) + ")</li>"
        if not riesgos:
            riesgos = "<li>Sin riesgos abiertos</li>"
        prod_rows = ""
        for x in fs["products"]:
            prod_rows = prod_rows + "<li>" + x["product"] + ": " + str(x["quantity"]) + "</li>"
        if not prod_rows:
            prod_rows = "<li>Sin cosechas registradas</li>"
        roles_html = ""
        for k, v in (summary.get("producers_by_role") or {}).items():
            roles_html = roles_html + "<li>" + str(k) + ": " + str(v) + "</li>"
        ben = ""
        for r in ay["beneficiados"]:
            ben = ben + "<li>" + r["name"] + " (" + str(r["aid_count"]) + ")</li>"
        if not ben:
            ben = "<li>Ninguno aun</li>"
        noben = ""
        for r in ay["no_beneficiados"]:
            noben = noben + "<li>" + r["name"] + "</li>"
        if not noben:
            noben = "<li>Todos beneficiados</li>"
        modulos = ""
        for m in self._ZYRA_MENUS_V2():
            modulos = modulos + "<li><b>" + str(m.get("title")) + "</b>:"
            for it in m.get("items", []):
                modulos = modulos + " <a href='" + str(it.get("path")) + "'>" + str(it.get("label")) + "</a>"
            modulos = modulos + "</li>"
        body = (
            "<h1>🏛️ AGRO — Vista Gobierno</h1>"
            "<h2>Soberania alimentaria nacional</h2>"
            "<div class='card'>"
            "<span class='big'>" + str(summary.get("producers_total")) + "</span> productores<br>"
            "<span class='big'>" + str(summary.get("producers_verified")) + "</span> verificados"
            "</div>"
            "<div class='card'><h2>Seguridad alimentaria</h2><ul>" + prod_rows + "</ul>"
            "<a href='/agro/gobierno/seguridad'><button>Ver detalle</button></a></div>"
            "<div class='card'><h2>Ayudas (" + str(ay["aid_total"]) + " total)</h2>"
            "<h3>Beneficiados</h3><ul>" + ben + "</ul>"
            "<h3>No beneficiados (a quienes ayudar)</h3><ul>" + noben + "</ul>"
            "<a href='/agro/gobierno/beneficiados'><button>Ver detalle</button></a></div>"
            "<div class='card'><h2>Riesgos abiertos</h2><ul>" + riesgos + "</ul>"
            "<a href='/agro/gobierno/riesgos'><button>Ver detalle</button></a></div>"
            "<div class='card'><h2>Por rol</h2><ul>" + roles_html + "</ul></div>"
            "<div class='card'><h2>Modulos de la Red AGRO</h2><ul>" + modulos + "</ul></div>"
            "<a href='/agro'><button class='gray'>Inicio</button></a>"
        )
        self._html(
            200,
            _page("AGRO - Gobierno", body),
        )

    def _screen_bank(self) -> None:
        store = type(self).store
        producers = store.list_producers()
        total = len(producers)
        verified = 0
        for p in producers:
            if p.get("verified"):
                verified = verified + 1
        prods = store.list_productions()
        rows = ""
        for p in prods:
            rows = rows + "<li>" + str(p.get("product")) + " - " + str(p.get("quantity")) + " " + str(p.get("unit")) + "</li>"
        if not rows:
            rows = "<li>Sin produccion disponible</li>"
        body = (
            "<h1>Banco AGRO</h1>"
            "<p>Productores: " + str(total) + " - verificados: " + str(verified) + "</p>"
            "<div class='card'><h2>Credito agricola</h2>"
            "<p>credito para productores verificados con ZID en la Red.</p>"
            "<a href='/agro/gobierno/beneficiados'><button>Beneficiarios de apoyo</button></a>"
            "</div>"
            "<div class='card'><h2>Produccion para compra / exportacion</h2>"
            "<ul>" + rows + "</ul>"
            "<a href='/agro/mercado'><button>Ir al mercado</button></a>"
            "</div>"
            "<a href='/agro'><button class='gray'>Inicio</button></a>"
        )
        self._html(
            200,
            _page("AGRO - Banco", body),
        )

    def _html(
        self, status: int, html: str
    ) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.end_headers()
        self.wfile.write(body)

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
