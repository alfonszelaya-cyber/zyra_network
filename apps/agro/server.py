"""AGRO HTTP surface v4: role screens + JSON API
dual mode."""
from __future__ import annotations
from apps.agro.routers.aid_mixin import AidMixin
from apps.agro.routers.screens_mixin import ScreensMixin

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

class AgroApiHandler(AidMixin, ScreensMixin, BaseHTTPRequestHandler):
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
        if s == ["audit", "verify"]:
            self._send(
                200,
                {
                    "ok": True,
                    "data": (
                        self._ZYRA_AUDIT_VERIFY_V6()
                    ),
                },
            )
            return
        if s == ["audit", "list"]:
            from apps.agro.modules.seguridad.auditoria.audit_service import (
                _agro_audit_chain_list,
            )
            from urllib.parse import (
                parse_qs, urlparse as _up6,
            )
            qs = parse_qs(_up6(self.path).query)
            limit = int(qs.get("limit", ["50"])[0])
            offset = int(qs.get("offset", ["0"])[0])
            rows = _agro_audit_chain_list(
                type(self).store._db,
                limit=limit, offset=offset,
            )
            self._send(
                200,
                {
                    "ok": True,
                    "data": {
                        "entries": rows,
                        "limit": limit,
                        "offset": offset,
                    },
                },
            )
            return
        if len(s) == 2 and s[0] == "perfil":
            row = self._ZYRA_FN_V6(
                "apps.agro.modules.productores.perfil.profile_service",
                "get_profile_db",
            )(type(self).store._db, s[1])
            self._send(200, {"ok": True, "data": row})
            return
        if len(s) == 3 and s[0] == "perfil" and s[2] == "history":
            rows = self._ZYRA_FN_V6(
                "apps.agro.modules.productores.perfil.profile_service",
                "get_profile_history_db",
            )(type(self).store._db, s[1])
            self._send(
                200,
                {"ok": True, "data": {"history": rows}},
            )
            return
        if len(s) == 2 and s[0] == "units":
            units = self._ZYRA_FN_V6(
                "apps.agro.modules.productores.unidades_productivas.unit_service",
                "units_of_db",
            )(type(self).store._db, s[1])
            self._send(
                200,
                {"ok": True, "data": {"units": units}},
            )
            return
        if len(s) == 3 and s[0] == "units" and s[2] == "capacity":
            rep = self._ZYRA_FN_V6(
                "apps.agro.modules.productores.unidades_productivas.unit_service",
                "unit_capacity_report_db",
            )(type(self).store._db, s[1])
            self._send(200, {"ok": True, "data": rep})
            return
        if len(s) == 2 and s[0] == "docs":
            docs = self._ZYRA_FN_V6(
                "apps.agro.modules.productores.documentos.document_service",
                "documents_plus_of_db",
            )(type(self).store._db, s[1])
            self._send(
                200,
                {"ok": True, "data": {"documents": docs}},
            )
            return
        if len(s) == 2 and s[0] == "plans":
            plans = self._ZYRA_FN_V6(
                "apps.agro.modules.produccion.planificacion.planning_service",
                "plans_plus_of_db",
            )(type(self).store._db, s[1])
            self._send(
                200,
                {"ok": True, "data": {"plans": plans}},
            )
            return
        if len(s) == 3 and s[0] == "plans" and s[2] == "timeline":
            tl = self._ZYRA_FN_V6(
                "apps.agro.modules.produccion.seguimiento.tracking_service",
                "timeline_of_db",
            )(type(self).store._db, s[1])
            self._send(
                200,
                {"ok": True, "data": {"timelines": tl}},
            )
            return
        if len(s) == 3 and s[0] == "plans" and s[2] == "costs":
            cs = self._ZYRA_FN_V6(
                "apps.agro.modules.produccion.planificacion.planning_service",
                "plan_costs_summary_db",
            )(type(self).store._db, s[1])
            self._send(200, {"ok": True, "data": cs})
            return
        if len(s) == 2 and s[0] == "incidents":
            inc = self._ZYRA_FN_V6(
                "apps.agro.modules.operaciones.incidencias.incident_service",
                "open_incidents_plus_db",
            )(type(self).store._db, s[1])
            self._send(
                200,
                {"ok": True, "data": {"incidents": inc}},
            )
            return
        if len(s) == 3 and s[0] == "incidents" and s[2] == "stats":
            st = self._ZYRA_FN_V6(
                "apps.agro.modules.operaciones.incidencias.incident_service",
                "incident_stats_db",
            )(type(self).store._db, s[1])
            self._send(200, {"ok": True, "data": st})
            return
        if len(s) == 2 and s[0] == "yield":
            rep = self._ZYRA_FN_V6(
                "apps.agro.modules.produccion.rendimiento.yield_service",
                "report_plus_db",
            )(
                type(self).store._db,
                type(self).store,
                s[1],
            )
            self._send(200, {"ok": True, "data": rep})
            return
        if s == ["production", "report"]:
            from apps.agro.modules.produccion.reportes.production_report import (
                national_report,
            )
            rep = national_report(type(self).store)
            self._send(200, {"ok": True, "data": rep})
            return
        if len(s) == 2 and s[0] == "sales" and s[1] != "all":
            rows = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.venta_simple.simple_sale_service",
                "sales_of_db",
            )(type(self).store._db, s[1])
            self._send(
                200,
                {"ok": True, "data": {"sales": rows}},
            )
            return
        if s == ["sales", "all"]:
            rows = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.venta_simple.simple_sale_service",
                "sales_of_db",
            )(type(self).store._db, None)
            self._send(
                200,
                {"ok": True, "data": {"sales": rows}},
            )
            return
        if len(s) == 3 and s[0] == "sales" and s[2] == "offers":
            rows = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.venta_simple.simple_sale_service",
                "offers_of_db",
            )(type(self).store._db, s[1])
            self._send(
                200,
                {"ok": True, "data": {"offers": rows}},
            )
            return
        if len(s) == 2 and s[0] == "inventory":
            rows = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.venta_simple.simple_sale_service",
                "inventory_of_db",
            )(type(self).store._db, s[1])
            self._send(
                200,
                {"ok": True, "data": {"inventory": rows}},
            )
            return
        if len(s) == 2 and s[0] == "exports":
            rows = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.exportacion.export_service",
                "exports_of_db",
            )(type(self).store._db, s[1])
            self._send(
                200,
                {"ok": True, "data": {"exports": rows}},
            )
            return
        if len(s) == 2 and s[0] == "results":
            rep = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.resultados.commercial_results",
                "results_for_db",
            )(type(self).store._db, s[1])
            self._send(200, {"ok": True, "data": rep})
            return
        if len(s) == 3 and s[0] == "market" and s[1] == "price":
            from apps.agro.modules.comercializacion.mercado.market_service import (
                market_snapshot_db,
            )
            try:
                snap = market_snapshot_db(
                    type(self).store._db, s[2]
                )
            except LookupError as exc:
                raise ValueError(str(exc))
            self._send(200, {"ok": True, "data": snap})
            return
        if len(s) == 3 and s[0] == "asset" and s[1] == "history":
            from apps.agro.modules.recursos_y_activos.inventarios.inventory_service import (
                asset_history_of_db,
            )
            rows = asset_history_of_db(
                type(self).store._db, s[2]
            )
            self._send(
                200,
                {"ok": True, "data": {"history": rows}},
            )
            return
        if len(s) == 3 and s[0] == "asset" and s[1] == "values":
            from apps.agro.modules.recursos_y_activos.valoracion.valuation_service import (
                valuations_of_db,
            )
            rows = valuations_of_db(
                type(self).store._db, s[2]
            )
            self._send(
                200,
                {"ok": True, "data": {"valuations": rows}},
            )
            return
        if len(s) == 2 and s[0] == "equipment":
            from apps.agro.modules.recursos_y_activos.equipos.equipment_service import (
                equipment_of_db,
            )
            rows = equipment_of_db(
                type(self).store._db, s[1]
            )
            self._send(
                200,
                {"ok": True, "data": {"equipment": rows}},
            )
            return
        if len(s) == 2 and s[0] == "infrastructure":
            from apps.agro.modules.recursos_y_activos.infraestructura.infrastructure_service import (
                infrastructure_of_db,
            )
            rows = infrastructure_of_db(
                type(self).store._db, s[1]
            )
            self._send(
                200,
                {"ok": True, "data": {"infrastructure": rows}},
            )
            return
        if len(s) == 3 and s[0] == "risk" and s[1] == "climate":
            from apps.agro.modules.riesgo.riesgo_climatico.climate_risk_service import (
                climate_events_of_db,
            )
            rows = climate_events_of_db(
                type(self).store._db, s[2]
            )
            self._send(
                200,
                {"ok": True, "data": {"events": rows}},
            )
            return
        if len(s) == 2 and s[0] == "alerts":
            from apps.agro.modules.riesgo.alertas.risk_alert_service import (
                open_alerts_of_db,
            )
            rows = open_alerts_of_db(
                type(self).store._db, s[1]
            )
            self._send(
                200,
                {"ok": True, "data": {"alerts": rows}},
            )
            return
        if len(s) == 2 and s[0] == "responses":
            from apps.agro.modules.riesgo.respuesta.response_service import (
                responses_of_db,
            )
            rows = responses_of_db(
                type(self).store._db, s[1]
            )
            self._send(
                200,
                {"ok": True, "data": {"responses": rows}},
            )
            return
        if len(s) == 3 and s[0] == "risk" and s[1] == "evals":
            from apps.agro.modules.riesgo.riesgo_productivo.productive_risk_service import (
                evals_of_db,
            )
            rows = evals_of_db(
                type(self).store._db, s[2]
            )
            self._send(
                200,
                {"ok": True, "data": {"evals": rows}},
            )
            return
        if s == ["network", "status"]:
            st_row = type(self).link.network_status()
            from apps.agro.services.zyra_link import (
                outbox_stats_db,
            )
            st_row["outbox"] = outbox_stats_db(
                type(self).store._db
            )
            self._send(200, {"ok": True, "data": st_row})
            return
        if s == ["network", "outbox"]:
            from apps.agro.services.zyra_link import (
                outbox_pending_db,
            )
            rows = outbox_pending_db(
                type(self).store._db, limit=20
            )
            self._send(
                200,
                {"ok": True, "data": {"pending": rows}},
            )
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

    def _ZYRA_MATRIX_V6(self):
        from apps.agro.security.operation_matrix import (
            OperationMatrix,
        )
        return OperationMatrix()

    def _ZYRA_FN_V6(self, dotted, fn_name):
        mod = __import__(
            dotted, fromlist=[fn_name]
        )
        return getattr(mod, fn_name)

    def _ZYRA_AUDIT_V6(self, operation, outcome, detail=""):
        from apps.agro.modules.seguridad.auditoria.audit_service import (
            _agro_audit_chain_record,
        )
        try:
            _agro_audit_chain_record(
                type(self).store._db,
                actor_id=(
                    self.headers.get(
                        "X-ZYRA-Actor-Id"
                    ) or "anon"
                ),
                role=(
                    self.headers.get(
                        "X-ZYRA-Actor-Role"
                    ) or "-"
                ),
                operation=operation,
                outcome=outcome,
                detail=detail,
            )
        except Exception:
            pass

    def _ZYRA_AUDIT_VERIFY_V6(self):
        from apps.agro.modules.seguridad.auditoria.audit_service import (
            _agro_audit_chain_verify,
        )
        return _agro_audit_chain_verify(
            type(self).store._db
        )

    def _ZYRA_RATE_V6(self, actor):
        import time as _t
        table = getattr(
            type(self), "_zyra_rate_v6", None
        )
        if table is None:
            table = {}
            type(self)._zyra_rate_v6 = table
        now = _t.time()
        hits = [
            x for x in table.get(actor, [])
            if now - x < 3600.0
        ]
        hits.append(now)
        table[actor] = hits
        return len(hits)

    def _ZYRA_IS_BLOCKED_V6(self, actor):
        db = type(self).store._db
        for name in ("query_one", "query"):
            fn = getattr(db, name, None)
            if callable(fn):
                try:
                    row = fn(
                        "SELECT reason FROM"
                        " agro_blocked_actors"
                        " WHERE actor = ?",
                        (actor,),
                    )
                except Exception:
                    row = None
                if row:
                    try:
                        return str(row["reason"])
                    except Exception:
                        try:
                            return str(row[0])
                        except Exception:
                            return "bloqueado"
        return None

    def _ZYRA_BLOCK_V6(self, actor, reason):
        import time as _t
        db = type(self).store._db
        db.execute(
            "CREATE TABLE IF NOT EXISTS"
            " agro_blocked_actors ("
            " actor TEXT PRIMARY KEY,"
            " reason TEXT NOT NULL,"
            " at TEXT NOT NULL)"
        )
        ts = _t.strftime(
            "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
        )
        db.execute(
            "INSERT OR REPLACE INTO"
            " agro_blocked_actors (actor,"
            " reason, at) VALUES (?, ?, ?)",
            (actor, str(reason), ts),
        )

    def _ZYRA_UNBLOCK_V6(self, actor):
        db = type(self).store._db
        db.execute(
            "CREATE TABLE IF NOT EXISTS"
            " agro_blocked_actors ("
            " actor TEXT PRIMARY KEY,"
            " reason TEXT NOT NULL,"
            " at TEXT NOT NULL)"
        )
        db.execute(
            "DELETE FROM agro_blocked_actors"
            " WHERE actor = ?",
            (actor,),
        )

    def _ZYRA_COM_D(self, dotted, fn_name):
        mod = __import__(
            dotted, fromlist=[fn_name]
        )
        return getattr(mod, fn_name)

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
        _ZV6_ACTOR = (
            self.headers.get("X-ZYRA-Actor-Id")
            or "anon"
        )
        _ZV6_PATH = "/agro/" + "/".join(s)
        _ZV6_OP = {
            ("producers", "verify"): "producers.verify",
            ("aid", "eligibility"): "aid.eligibility",
            ("government", "approve"): "aid.approve",
            ("government", "assign"): "aid.assign",
            ("government", "deliver"): "aid.deliver",
            ("land",): "land.create",
            ("machinery",): "machinery.create",
            ("inventory",): "inventory.create",
            ("water",): "water.create",
            ("unit",): "unit.create",
            ("unit", "close"): "unit.close",
            ("perfil",): "profile.update",
            ("document",): "document.register",
            ("document", "verify"): "document.verify",
            ("plan",): "plan.create",
            ("plan", "advance"): "plan.advance",
            ("plan", "cancel"): "plan.cancel",
            ("plan", "cost"): "plan.cost.add",
            ("incident",): "incident.report",
            ("incident", "resolve"): "incident.resolve",
            ("sale",): "sale.create",
            ("sale", "complete"): "sale.complete",
            ("risk",): "risk.report",
            ("risk", "resolve"): "risk.resolve",
            ("security", "unblock"): "security.unblock",
            ("sale", "publish"): "sale.publish",
            ("sale", "offer"): "sale.offer",
            ("sale", "accept"): "sale.accept",
            ("sale", "pay"): "sale.pay",
            ("sale", "deliver"): "sale.deliver",
            ("inventory", "add"): "inventory.add",
            ("export",): "export.create",
            ("shipment",): "shipment.create",
            ("shipment", "update"): "shipment.update",
            ("market", "price"): "market.price.add",
            ("equipment",): "equipment.create",
            ("infrastructure",): "infrastructure.create",
            ("asset", "log"): "asset.log",
            ("asset", "value"): "asset.value",
            ("risk", "climate"): "risk.climate.evaluate",
            ("risk", "productive"): "risk.productive.evaluate",
            ("risk", "impact"): "risk.impact.calculate",
            ("risk", "recovery"): "risk.recovery",
            ("alert", "resolve"): "alert.resolve",
            ("response",): "response.create",
            ("response", "update"): "response.update",
            ("network", "emit"): "network.emit",
            ("production",): "production.register",
        }.get(tuple(s))
        if _ZV6_OP is not None:
            _ZV6_BLOCKED = None
            if _ZV6_OP != "security.unblock":
                _ZV6_BLOCKED = (
                    self._ZYRA_IS_BLOCKED_V6(
                        _ZV6_ACTOR
                    )
                )
            if _ZV6_BLOCKED is not None:
                self._send(
                    403,
                    {
                        "ok": False,
                        "error": {
                            "type": "actor_blocked",
                            "message": (
                                "actor bloqueado: "
                                + _ZV6_BLOCKED
                            ),
                        },
                    },
                )
                return
            _ZV6_ROLE_RAW = (
                self.headers.get(
                    "X-ZYRA-Actor-Role"
                ) or ""
            ).strip()
            _ZV6_MAP = {
                "agricultor": "producer",
                "ganadero": "producer",
                "productor": "producer",
                "gobierno": "government",
                "banco": "company",
                "institucion": "company",
                "empresa": "company",
                "operador": "operator",
                "admin": "administrator",
            }
            _ZV6_ROLE = _ZV6_MAP.get(
                _ZV6_ROLE_RAW, _ZV6_ROLE_RAW
            )
            try:
                _ZV6_OK = self._ZYRA_MATRIX_V6().check(
                    operation=_ZV6_OP,
                    role=_ZV6_ROLE,
                    subject_id=_ZV6_ACTOR,
                )
                _ZV6_MSG = (
                    "rol sin permiso: " + _ZV6_ROLE
                    + " / " + _ZV6_OP
                )
            except ValueError:
                _ZV6_OK = False
                _ZV6_MSG = (
                    "operacion desconocida: "
                    + _ZV6_OP
                )
            if not _ZV6_OK:
                _denies = self._ZYRA_RATE_V6(
                    _ZV6_ACTOR
                )
                self._ZYRA_AUDIT_V6(
                    _ZV6_PATH, "denied",
                    detail=(
                        "role=" + _ZV6_ROLE
                        + " denies="
                        + str(_denies)
                    ),
                )
                if _denies >= 10:
                    self._ZYRA_BLOCK_V6(
                        _ZV6_ACTOR,
                        "10+ denegados en 1h",
                    )
                    self._ZYRA_AUDIT_V6(
                        _ZV6_PATH,
                        "actor_blocked",
                    )
                self._send(
                    403,
                    {
                        "ok": False,
                        "error": {
                            "type": "forbidden",
                            "message": _ZV6_MSG,
                        },
                    },
                )
                return
        self._ZYRA_AUDIT_V6(_ZV6_PATH, "allowed")
        if s == ["equipment"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            from apps.agro.modules.recursos_y_activos.equipos.equipment_service import (
                register_equipment_db,
            )
            row = register_equipment_db(
                type(self).store._db,
                producer_id=pid,
                kind=self._req(doc, "kind"),
                identifier=doc.get("identifier"),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["infrastructure"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            from apps.agro.modules.recursos_y_activos.infraestructura.infrastructure_service import (
                register_infrastructure_db,
            )
            row = register_infrastructure_db(
                type(self).store._db,
                producer_id=pid,
                kind=self._req(doc, "kind"),
                location=doc.get("location"),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["asset", "log"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            from apps.agro.modules.recursos_y_activos.inventarios.inventory_service import (
                asset_log_db,
            )
            row = asset_log_db(
                type(self).store._db,
                producer_id=pid,
                asset_kind=self._req(doc, "asset_kind"),
                asset_id=self._req(doc, "asset_id"),
                action=self._req(doc, "action"),
                detail=str(doc.get("detail") or ""),
                actor=_ZV6_ACTOR,
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["asset", "value"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            from apps.agro.modules.recursos_y_activos.valoracion.valuation_service import (
                value_asset_db,
            )
            row = value_asset_db(
                type(self).store._db,
                producer_id=pid,
                asset_kind=self._req(doc, "asset_kind"),
                asset_id=self._req(doc, "asset_id"),
                amount=float(doc.get("amount") or 0),
                currency=self._req(doc, "currency"),
                actor=_ZV6_ACTOR,
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["risk", "climate"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            from apps.agro.modules.riesgo.riesgo_climatico.climate_risk_service import (
                evaluate_climate_db,
            )
            row = evaluate_climate_db(
                type(self).store._db,
                producer_id=pid,
                event_type=self._req(doc, "event_type"),
                severity=self._req(doc, "severity"),
                detail=str(doc.get("detail") or ""),
            )
            if row["alert"]:
                from apps.agro.modules.riesgo.alertas.risk_alert_service import (
                    create_alert_db,
                )
                alert = create_alert_db(
                    type(self).store._db,
                    producer_id=pid,
                    risk_type=str(row["event_type"]),
                    severity=str(row["severity"]),
                    target=pid,
                    detail="auto: clima " + str(row["event_id"]),
                )
                row["alert_id"] = alert["alert_id"]
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["risk", "productive"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            from apps.agro.modules.riesgo.riesgo_productivo.productive_risk_service import (
                evaluate_productive_db,
            )
            row = evaluate_productive_db(
                type(self).store._db,
                producer_id=pid,
                losses=float(doc.get("losses") or 0),
                production=float(doc.get("production") or 0),
            )
            if row["level"] == "high":
                from apps.agro.modules.riesgo.alertas.risk_alert_service import (
                    create_alert_db,
                )
                alert = create_alert_db(
                    type(self).store._db,
                    producer_id=pid,
                    risk_type="productive",
                    severity="high",
                    target=pid,
                    detail="auto: perdidas " + str(row["eval_id"]),
                )
                row["alert_id"] = alert["alert_id"]
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["risk", "impact"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            from apps.agro.modules.riesgo.impacto.impact_service import (
                calculate_impact_db,
            )
            row = calculate_impact_db(
                type(self).store._db,
                producer_id=pid,
                affected_units=float(doc.get("affected_units") or 0),
                total_units=float(doc.get("total_units") or 0),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["risk", "recovery"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            from apps.agro.modules.riesgo.resiliencia.resilience_service import (
                recovery_score_db,
            )
            row = recovery_score_db(
                type(self).store._db,
                producer_id=pid,
                risk_id=str(doc.get("risk_id") or ""),
                recovered=float(doc.get("recovered") or 0),
                affected=float(doc.get("affected") or 0),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["alert", "resolve"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            from apps.agro.modules.riesgo.alertas.risk_alert_service import (
                resolve_alert_db,
            )
            row = resolve_alert_db(
                type(self).store._db,
                alert_id=self._req(doc, "alert_id"),
                resolution=str(doc.get("resolution") or ""),
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["response"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            from apps.agro.modules.riesgo.respuesta.response_service import (
                create_response_db,
            )
            row = create_response_db(
                type(self).store._db,
                producer_id=pid,
                risk_id=self._req(doc, "risk_id"),
                actions=list(doc.get("actions") or []),
                actor=_ZV6_ACTOR,
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["response", "update"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            from apps.agro.modules.riesgo.respuesta.response_service import (
                update_response_db,
            )
            row = update_response_db(
                type(self).store._db,
                response_id=self._req(doc, "response_id"),
                status=self._req(doc, "status"),
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["network", "emit"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            zid = self._req(doc, "zid")
            et = self._req(doc, "event_type")
            payload = doc.get("payload")
            if not isinstance(payload, dict):
                raise ValueError(
                    "payload debe ser objeto"
                )
            row = self._ZYRA_COM_D(
                "apps.agro.services.zyra_link",
                "emit_event_db",
            )(
                type(self).store._db,
                type(self).link,
                zid=zid,
                event_type=et,
                payload=payload,
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["sale", "publish"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            row = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.venta_simple.simple_sale_service",
                "publish_sale_db",
            )(
                type(self).store._db,
                producer_id=pid,
                product=self._req(doc, "product"),
                quantity=float(doc.get("quantity") or 0),
                unit=str(doc.get("unit") or "quintal"),
                currency=str(doc.get("currency") or "USD"),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["sale", "offer"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.venta_simple.simple_sale_service",
                "place_offer_db",
            )(
                type(self).store._db,
                sale_id=self._req(doc, "sale_id"),
                buyer=self._req(doc, "buyer"),
                amount=float(doc.get("amount") or 0),
                currency=str(doc.get("currency") or "USD"),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["sale", "accept"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.venta_simple.simple_sale_service",
                "accept_offer_db",
            )(
                type(self).store._db,
                offer_id=self._req(doc, "offer_id"),
                actor=_ZV6_ACTOR,
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["sale", "pay"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.venta_simple.simple_sale_service",
                "pay_sale_db",
            )(
                type(self).store._db,
                sale_id=self._req(doc, "sale_id"),
                actor=_ZV6_ACTOR,
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["sale", "deliver"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.venta_simple.simple_sale_service",
                "deliver_sale_db",
            )(
                type(self).store._db,
                sale_id=self._req(doc, "sale_id"),
                actor=_ZV6_ACTOR,
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["sale", "close"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.venta_simple.simple_sale_service",
                "close_sale_db",
            )(
                type(self).store._db,
                sale_id=self._req(doc, "sale_id"),
                actor=_ZV6_ACTOR,
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["inventory", "add"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            row = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.venta_simple.simple_sale_service",
                "inventory_add_db",
            )(
                type(self).store._db,
                producer_id=pid,
                product=self._req(doc, "product"),
                quantity=float(doc.get("quantity") or 0),
                unit=str(doc.get("unit") or "quintal"),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["export"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            row = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.exportacion.export_service",
                "create_export_db",
            )(
                type(self).store._db,
                producer_id=pid,
                product=self._req(doc, "product"),
                destination=self._req(doc, "destination"),
                quantity=float(doc.get("quantity") or 0),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["shipment"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.logistica.logistics_adapter",
                "create_shipment_db",
            )(
                type(self).store._db,
                sale_id=self._req(doc, "sale_id"),
                origin=self._req(doc, "origin"),
                destination=self._req(doc, "destination"),
                cargo=self._req(doc, "cargo"),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["shipment", "update"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.logistica.logistics_adapter",
                "mark_shipment_db",
            )(
                type(self).store._db,
                shipment_id=self._req(doc, "shipment_id"),
                status=self._req(doc, "status"),
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["market", "price"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_COM_D(
                "apps.agro.modules.comercializacion.mercado.market_service",
                "add_price_db",
            )(
                type(self).store._db,
                product=self._req(doc, "product"),
                price=float(doc.get("price") or 0),
                actor=_ZV6_ACTOR,
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["perfil"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            row = self._ZYRA_FN_V6(
                "apps.agro.modules.productores.perfil.profile_service",
                "update_profile_db",
            )(
                type(self).store._db,
                producer_id=pid,
                phone=str(doc.get("phone") or ""),
                location=str(doc.get("location") or ""),
                notes=str(doc.get("notes") or ""),
                actor=_ZV6_ACTOR,
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["unit"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            row = self._ZYRA_FN_V6(
                "apps.agro.modules.productores.unidades_productivas.unit_service",
                "register_unit_db",
            )(
                type(self).store._db,
                producer_id=pid,
                name=self._req(doc, "name"),
                unit_type=str(
                    doc.get("unit_type") or "agricola"
                ),
                land_id=doc.get("land_id"),
            )
            self._ZYRA_EVENTS_V2().asset_registered(
                producer_id=pid,
                asset_type="unidad",
                detail=str(row["unit_id"]),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["unit", "close"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_FN_V6(
                "apps.agro.modules.productores.unidades_productivas.unit_service",
                "close_unit_db",
            )(
                type(self).store._db,
                unit_id=self._req(doc, "unit_id"),
                reason=str(doc.get("reason") or ""),
                closed_by=(
                    str(doc.get("producer_id") or "anon")
                ),
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["document"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            row = self._ZYRA_FN_V6(
                "apps.agro.modules.productores.documentos.document_service",
                "register_doc_plus_db",
            )(
                type(self).store._db,
                producer_id=pid,
                doc_kind=self._req(doc, "doc_kind"),
                content_b64=str(
                    doc.get("content_b64") or ""
                ),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["document", "verify"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_FN_V6(
                "apps.agro.modules.productores.documentos.document_service",
                "verify_doc_plus_db",
            )(
                type(self).store._db,
                doc_id=self._req(doc, "doc_id"),
                reviewer=str(
                    doc.get("reviewer") or "gobierno"
                ),
                approve=str(
                    doc.get("approve", "true")
                ).lower() == "true",
                note=str(doc.get("note") or ""),
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["plan"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            row = self._ZYRA_FN_V6(
                "apps.agro.modules.produccion.planificacion.planning_service",
                "create_plan_db",
            )(
                type(self).store._db,
                producer_id=pid,
                unit_id=self._req(doc, "unit_id"),
                crop=self._req(doc, "crop"),
                target=float(
                    doc.get("planned_quantity") or 0
                ),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["plan", "advance"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_FN_V6(
                "apps.agro.modules.produccion.planificacion.planning_service",
                "advance_plan_plus_db",
            )(
                type(self).store._db,
                plan_id=self._req(doc, "plan_id"),
                detail=str(doc.get("detail") or ""),
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["plan", "cancel"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_FN_V6(
                "apps.agro.modules.produccion.planificacion.planning_service",
                "cancel_plan_db",
            )(
                type(self).store._db,
                plan_id=self._req(doc, "plan_id"),
                reason=str(doc.get("reason") or ""),
                actor=_ZV6_ACTOR,
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["plan", "cost"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_FN_V6(
                "apps.agro.modules.produccion.planificacion.planning_service",
                "add_plan_cost_db",
            )(
                type(self).store._db,
                plan_id=self._req(doc, "plan_id"),
                concept=self._req(doc, "concept"),
                amount=float(doc.get("amount") or 0),
                currency=self._req(doc, "currency"),
                actor=_ZV6_ACTOR,
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["incident"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            pid = self._req(doc, "producer_id")
            row = self._ZYRA_FN_V6(
                "apps.agro.modules.operaciones.incidencias.incident_service",
                "report_incident_plus_db",
            )(
                type(self).store._db,
                producer_id=pid,
                unit_id=doc.get("unit_id"),
                kind=self._req(doc, "kind"),
                severity=str(
                    doc.get("severity") or "media"
                ),
                detail=str(doc.get("detail") or ""),
            )
            self._ZYRA_EVENTS_V2().incident_created(
                producer_id=pid,
                incident_id=str(row["incident_id"]),
                detail=str(row.get("kind", "")),
            )
            self._send(201, {"ok": True, "data": row})
            return
        if s == ["incident", "resolve"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            row = self._ZYRA_FN_V6(
                "apps.agro.modules.operaciones.incidencias.incident_service",
                "resolve_incident_plus_db",
            )(
                type(self).store._db,
                incident_id=self._req(doc, "incident_id"),
                action=str(doc.get("action") or ""),
            )
            self._send(200, {"ok": True, "data": row})
            return
        if s == ["security", "unblock"]:
            doc = self._ZYRA_PAYLOAD_V2(is_json)
            self._ZYRA_UNBLOCK_V6(
                self._req(doc, "actor")
            )
            self._ZYRA_AUDIT_V6(
                "/agro/security/unblock",
                "allowed",
                detail=str(doc.get("actor")),
            )
            self._send(
                200,
                {
                    "ok": True,
                    "data": {"unblocked": True},
                },
            )
            return
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
