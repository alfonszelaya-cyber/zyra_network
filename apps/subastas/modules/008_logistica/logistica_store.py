"""ZYRA MARKET - Modulo Logistica (completo).

Transportistas, aduana, incidencias, etiquetas."""
from __future__ import annotations

import threading
import time
import traceback
import uuid


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _nid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


class LogisticaStore:
    def __init__(self, db, clock) -> None:
        self._db = db
        self._clock = clock
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_carriers ("
            " car_id TEXT PRIMARY KEY,"
            " name TEXT NOT NULL,"
            " coverage TEXT NOT NULL,"
            " base_cost REAL NOT NULL,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_customs ("
            " cus_id TEXT PRIMARY KEY,"
            " shipment_id TEXT NOT NULL,"
            " doc_ref TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " created_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_ship_incidents ("
            " shi_id TEXT PRIMARY KEY,"
            " shipment_id TEXT NOT NULL,"
            " reported_by TEXT NOT NULL,"
            " detail TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " resolution TEXT,"
            " created_at TEXT NOT NULL,"
            " resolved_at TEXT)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_labels ("
            " lbl_id TEXT PRIMARY KEY,"
            " shipment_id TEXT NOT NULL,"
            " carrier_id TEXT NOT NULL,"
            " tracking_number TEXT NOT NULL,"
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
            assembled += LogisticaStore._literal(v)
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

    @staticmethod
    def _req(value, name):
        text = str(value or "").strip()
        if not text:
            raise ValueError("%s es obligatorio" % name)
        return text

    def add_carrier(self, *, name, coverage, base_cost):
        name = self._req(name, "name")
        coverage = self._req(coverage, "coverage")
        cost = float(base_cost)
        if cost < 0:
            raise ValueError("costo no puede ser negativo")
        with self._lock:
            car_id = _nid("CAR-")
            self._run(
                "INSERT INTO sbs_carriers (car_id, name, coverage,"
                " base_cost, created_at) VALUES (?, ?, ?, ?, ?)",
                (car_id, name, coverage, cost, _now()),
            )
            return {"car_id": car_id, "name": name,
                    "coverage": coverage, "base_cost": cost}

    def list_carriers(self):
        out = []
        for row in self._rows(
            "SELECT car_id, name, coverage, base_cost, created_at"
            " FROM sbs_carriers ORDER BY created_at ASC"
        ):
            out.append({
                "car_id": self._field(row, "a", 0),
                "name": self._field(row, "b", 1),
                "coverage": self._field(row, "c", 2),
                "base_cost": self._field(row, "d", 3),
            })
        return out

    def declare_customs(self, shipment_id, *, doc_ref):
        shipment_id = self._req(shipment_id, "shipment_id")
        doc_ref = self._req(doc_ref, "doc_ref")
        with self._lock:
            cus_id = _nid("CUS-")
            self._run(
                "INSERT INTO sbs_customs (cus_id, shipment_id,"
                " doc_ref, status, created_at)"
                " VALUES (?, ?, ?, 'declarado', ?)",
                (cus_id, shipment_id, doc_ref, _now()),
            )
            return {"cus_id": cus_id, "shipment_id": shipment_id,
                    "status": "declarado"}

    def customs_clear(self, cus_id):
        cus_id = self._req(cus_id, "cus_id")
        with self._lock:
            self._run(
                "UPDATE sbs_customs SET status = 'despachado'"
                " WHERE cus_id = " + self._literal(cus_id)
            )
            return {"cus_id": cus_id, "status": "despachado"}

    def label(self, shipment_id, *, carrier_id):
        shipment_id = self._req(shipment_id, "shipment_id")
        carrier_id = self._req(carrier_id, "carrier_id")
        with self._lock:
            rows = self._rows(
                "SELECT name FROM sbs_carriers WHERE car_id = "
                + self._literal(carrier_id)
            )
            if not rows:
                raise LookupError("transportista no encontrado")
            cname = str(self._field(rows[0], "a", 0))
            lbl_id = _nid("LBL-")
            tracking = "ZY-" + uuid.uuid4().hex[:10].upper()
            self._run(
                "INSERT INTO sbs_labels (lbl_id, shipment_id,"
                " carrier_id, tracking_number, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (lbl_id, shipment_id, carrier_id, tracking, _now()),
            )
            return {"lbl_id": lbl_id, "shipment_id": shipment_id,
                    "carrier": cname, "tracking_number": tracking}

    def incident(self, shipment_id, *, reported_by, detail):
        shipment_id = self._req(shipment_id, "shipment_id")
        self._req(reported_by, "reported_by")
        detail = self._req(detail, "detail")
        with self._lock:
            shi_id = _nid("SHI-")
            self._run(
                "INSERT INTO sbs_ship_incidents (shi_id, shipment_id,"
                " reported_by, detail, status, resolution,"
                " created_at, resolved_at)"
                " VALUES (?, ?, ?, ?, 'open', NULL, ?, NULL)",
                (shi_id, shipment_id, reported_by, detail, _now()),
            )
            return {"shi_id": shi_id, "status": "open"}

    def resolve_incident(self, shi_id, *, resolution):
        shi_id = self._req(shi_id, "shi_id")
        resolution = self._req(resolution, "resolution")
        with self._lock:
            self._run(
                "UPDATE sbs_ship_incidents SET status = 'resolved',"
                " resolution = " + self._literal(resolution)
                + ", resolved_at = " + self._literal(_now())
                + " WHERE shi_id = " + self._literal(shi_id)
            )
            return {"shi_id": shi_id, "status": "resolved"}


def market_logistica_api(self) -> None:
    try:
        user = self._sess_user()
        if user is None:
            self._send_json(401, {"ok": False, "error": "sesion requerida"})
            return
        account = user["username"]
        doc = self._read_json()
        if doc is None:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return
        action = str(doc.get("action", ""))
        if action == "add_carrier":
            r = self.log.add_carrier(
                name=str(doc.get("name", "")),
                coverage=str(doc.get("coverage", "")),
                base_cost=doc.get("base_cost", 0))
            self._send_json(201, {"ok": True, "data": r})
            return
        if action == "list_carriers":
            r = self.log.list_carriers()
            self._send_json(200, {"ok": True, "data": {"carriers": r}})
            return
        if action == "customs":
            r = self.log.declare_customs(
                str(doc.get("shipment_id", "")),
                doc_ref=str(doc.get("doc_ref", "")))
            self._send_json(201, {"ok": True, "data": r})
            return
        if action == "customs_clear":
            r = self.log.customs_clear(str(doc.get("cus_id", "")))
            self._send_json(200, {"ok": True, "data": r})
            return
        if action == "label":
            r = self.log.label(
                str(doc.get("shipment_id", "")),
                carrier_id=str(doc.get("carrier_id", "")))
            self._send_json(201, {"ok": True, "data": r})
            return
        if action == "incident":
            r = self.log.incident(
                str(doc.get("shipment_id", "")),
                reported_by=account, detail=str(doc.get("detail", "")))
            self._send_json(201, {"ok": True, "data": r})
            return
        if action == "resolve_incident":
            r = self.log.resolve_incident(
                str(doc.get("shi_id", "")),
                resolution=str(doc.get("resolution", "")))
            self._send_json(200, {"ok": True, "data": r})
            return
        if action == "list_incidents":
            r = self.log.list_incidents(doc.get("shipment_id"))
            self._send_json(200, {"ok": True, "data": {"incidents": r}})
            return
        self._send_json(
            400, {"ok": False, "error": "accion desconocida"}
        )
    except Exception:
        import traceback as _tb
        self._send_json(500, {
            "ok": False, "error": "server error",
            "trace": _tb.format_exc(),
        })
