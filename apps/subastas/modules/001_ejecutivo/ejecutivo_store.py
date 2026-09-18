"""ZYRA MARKET - Modulo 001 Ejecutivo.

Dashboard real por usuario + inteligencia ZYRA (reglas
sobre datos reales) + alertas personales. Patron join."""
from __future__ import annotations

import threading
import time
import uuid


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _nid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


class EjecutivoStore:
    def __init__(self, db, clock) -> None:
        self._db = db
        self._clock = clock
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_personal_alerts ("
            " pal_id TEXT PRIMARY KEY,"
            " account TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " detail TEXT NOT NULL,"
            " read_flag INTEGER NOT NULL DEFAULT 0,"
            " created_at TEXT NOT NULL)"
        )

    def _run(self, sql, params=()):
        if not params:
            self._db.execute(sql)
            return
        try:
            self._db.execute(sql, params)
            return
        except TypeError:
            self._db.execute(self._inline(sql, params))

    @staticmethod
    def _inline(sql, params):
        parts = sql.split("?")
        if len(parts) != len(params) + 1:
            return sql
        assembled = parts[0]
        for i, v in enumerate(params):
            assembled += EjecutivoStore._literal(v)
            assembled += parts[i + 1]
        return assembled

    @staticmethod
    def _literal(value):
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return repr(value)
        return "'" + str(value).replace("'", "''") + "'"

    def _rows(self, sql):
        for name in ("query", "fetchall", "fetch_all", "fetch", "select"):
            fn = getattr(self._db, name, None)
            if callable(fn):
                try:
                    rows = fn(sql)
                    if rows is not None:
                        return list(rows)
                except Exception:
                    continue
        try:
            cur = self._db.execute(sql)
        except Exception:
            return []
        if cur is None:
            return []
        try:
            return list(cur.fetchall())
        except Exception:
            return []

    @staticmethod
    def _field(row, key, index):
        if isinstance(row, dict):
            return row.get(key)
        try:
            return row[index]
        except Exception:
            return None

    def _count(self, sql):
        rows = self._rows(sql)
        if not rows:
            return 0
        row = rows[0]
        if isinstance(row, dict):
            for v in row.values():
                return int(v or 0)
            return 0
        try:
            return int(row[0] or 0)
        except Exception:
            return 0

    def stats_for(self, account):
        account = str(account or "").strip()
        if not account:
            raise ValueError("account es obligatorio")
        q = EjecutivoStore._literal(account)
        return {
            "listings_total": self._count(
                "SELECT COUNT(*) FROM sbs_listings WHERE seller_account = " + q),
            "listings_open": self._count(
                "SELECT COUNT(*) FROM sbs_listings WHERE seller_account = "
                + q + " AND status = 'open'"),
            "bids_made": self._count(
                "SELECT COUNT(*) FROM sbs_bids WHERE bidder_account = " + q),
            "bids_received": self._count(
                "SELECT COUNT(*) FROM sbs_bids b JOIN sbs_listings l"
                " ON b.listing_id = l.listing_id"
                " WHERE l.seller_account = " + q),
            "orders_buyer": self._count(
                "SELECT COUNT(*) FROM sbs_orders WHERE buyer_account = " + q),
            "orders_seller": self._count(
                "SELECT COUNT(*) FROM sbs_orders o JOIN sbs_listings l"
                " ON o.listing_id = l.listing_id"
                " WHERE l.seller_account = " + q),
            "disputes": self._count(
                "SELECT COUNT(*) FROM sbs_disputes WHERE opener_account = " + q),
            "risk_alerts": self._count(
                "SELECT COUNT(*) FROM sbs_fraud_alerts WHERE subject_account = " + q),
            "reputation": self._count(
                "SELECT COUNT(*) FROM sbs_reputation_events WHERE subject_zid = " + q),
        }

    def add_alert(self, *, account, kind, detail):
        account = str(account or "").strip()
        kind = str(kind or "").strip() or "info"
        detail = str(detail or "").strip() or "-"
        with self._lock:
            pal_id = _nid("PAL-")
            self._run(
                "INSERT INTO sbs_personal_alerts (pal_id, account,"
                " kind, detail, read_flag, created_at)"
                " VALUES (?, ?, ?, ?, 0, ?)",
                (pal_id, account, kind, detail, _now()),
            )
            return {"pal_id": pal_id, "account": account,
                    "kind": kind, "detail": detail}

    def alerts_for(self, account):
        account = str(account or "").strip()
        if not account:
            return []
        out = []
        for row in self._rows(
            "SELECT pal_id, kind, detail, read_flag, created_at"
            " FROM sbs_personal_alerts WHERE account = "
            + EjecutivoStore._literal(account)
            + " ORDER BY created_at DESC LIMIT 20"
        ):
            out.append({
                "pal_id": self._field(row, "a", 0),
                "kind": self._field(row, "b", 1),
                "detail": self._field(row, "c", 2),
                "read": bool(self._field(row, "d", 3)),
                "created_at": self._field(row, "e", 4),
            })
        return out

    def zyra_intelligence(self, stats):
        """Reglas deterministas sobre datos reales del usuario."""
        tips = []
        total = stats.get("listings_total", 0)
        open_l = stats.get("listings_open", 0)
        rec = stats.get("bids_received", 0)
        sold = stats.get("orders_seller", 0)
        bought = stats.get("orders_buyer", 0)
        disp = stats.get("disputes", 0)
        alerts = stats.get("risk_alerts", 0)
        rep = stats.get("reputation", 0)
        if total == 0 and stats.get("bids_made", 0) == 0:
            tips.append({
                "tipo": "inicio",
                "texto": "Bienvenido a ZYRA MARKET. Publica tu primer"
                " articulo como vendedor o explora como comprador.",
            })
        if open_l > 0 and rec == 0:
            tips.append({
                "tipo": "recomendacion",
                "texto": "Tienes %s publicaciones abiertas sin ofertas."
                " Revisa el precio base y mejora la descripcion."
                % str(open_l),
            })
        if sold > 0:
            tips.append({
                "tipo": "analisis",
                "texto": "Tienes %s ventas como vendedor. Manten tu"
                " reputacion calificando en Operaciones." % str(sold),
            })
        if bought > 0:
            tips.append({
                "tipo": "analisis",
                "texto": "Has hecho %s compras. Rastrea tus envios"
                " en Ordenes y envios." % str(bought),
            })
        if disp > 0:
            tips.append({
                "tipo": "alerta",
                "texto": "Tienes %s disputas. Resuelvelas en Proteccion." % str(disp),
            })
        if alerts > 0:
            tips.append({
                "tipo": "alerta",
                "texto": "Hay %s alertas de riesgo en tu cuenta."
                " Revisalas en Riesgo." % str(alerts),
            })
        if rep > 0:
            tips.append({
                "tipo": "positivo",
                "texto": "Tu reputacion tiene %s eventos en la Red."
                " Eso da confianza a tus publicaciones." % str(rep),
            })
        if not tips:
            tips.append({
                "tipo": "resumen",
                "texto": "Actividad tranquila. Publica o oferta para crecer.",
            })
        resumen = (
            "Resumen: %s publicaciones (%s abiertas), %s ofertas recibidas,"
            " %s ventas, %s compras, %s disputas, reputacion %s."
            % (
                str(total), str(open_l), str(rec),
                str(sold), str(bought), str(disp), str(rep),
            )
        )
        return {"resumen": resumen, "tips": tips}


def market_dashboard_page(self) -> str:
    user = self._sess_user()
    if user is None:
        body = "".join([
            "<div class='card'><h2>Mi Dashboard</h2>",
            "<p>Necesitas una sesion para ver tu dashboard.</p>",
            "<p><a href='/subastas/inscripcion'><button>Entrar / Crear cuenta</button></a></p>",
            "</div>",
        ])
        return self._page_wrap("ZYRA MARKET - Dashboard", body)
    account = user["username"]
    stats = self.eje.stats_for(account)
    intel = self.eje.zyra_intelligence(stats)
    alerts = self.eje.alerts_for(account)
    a_rows = []
    for a in alerts:
        a_rows.append(
            "<p>- <b>%s</b>: %s</p>" % (a["kind"], a["detail"]))
    if not a_rows:
        a_rows.append("<p>Sin alertas personales.</p>")
    t_rows = []
    for t in intel["tips"]:
        t_rows.append(
            "<p><b>[%s]</b> %s</p>" % (t["tipo"], t["texto"]))
    body = "".join([
        "<div class='card'><h2>Hola, %s</h2>" % user["display_name"],
        "<p>Rol: <b>%s</b> | Cuenta: <code>%s</code></p>" % (
            user["role"], account),
        "<p>%s</p>" % intel["resumen"],
        "</div>",
        "<div class='card'><h2>Mis numeros</h2>",
        "<p>Publicaciones: %s (%s abiertas)</p>" % (
            str(stats["listings_total"]), str(stats["listings_open"])),
        "<p>Ofertas recibidas: %s | Ofertas hechas: %s</p>" % (
            str(stats["bids_received"]), str(stats["bids_made"])),
        "<p>Ventas: %s | Compras: %s</p>" % (
            str(stats["orders_seller"]), str(stats["orders_buyer"])),
        "<p>Disputas: %s | Alertas de riesgo: %s | Reputacion: %s</p>" % (
            str(stats["disputes"]), str(stats["risk_alerts"]),
            str(stats["reputation"])),
        "</div>",
        "<div class='card'><h2>Inteligencia ZYRA</h2>",
        "".join(t_rows),
        "</div>",
        "<div class='card'><h2>Mis alertas</h2>",
        "".join(a_rows),
        "</div>",
    ])
    return self._page_wrap("ZYRA MARKET - Dashboard", body)


def market_dashboard_api(self) -> None:
    user = self._sess_user()
    if user is None:
        self._send_json(401, {"ok": False, "error": "sesion requerida"})
        return
    account = user["username"]
    stats = self.eje.stats_for(account)
    intel = self.eje.zyra_intelligence(stats)
    alerts = self.eje.alerts_for(account)
    self._send_json(200, {
        "ok": True,
        "data": {
            "account": account,
            "stats": stats,
            "intelligence": intel,
            "alerts": alerts,
        },
    })
