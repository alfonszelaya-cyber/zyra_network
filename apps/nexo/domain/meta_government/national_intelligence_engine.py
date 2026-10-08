
"""National Intelligence Engine (GOV-DATA) - Panel
Nacional en 3 capas (Meta Gobierno NEXO EXISTENTE):
A) indicadores vivos por app · B) alertas con
IMPACTO+RECOMENDACION+RESPONSABLE · C) cadena causal
cross-app · ALARMAS ZYRA_AMBER (exige ZID del menor,
regla 78)/SISMO/CRISIS. Reglas 66/68/76/78."""
from __future__ import annotations
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "nx_gov_indicators", (
        "CREATE TABLE IF NOT EXISTS"
        " nx_gov_indicators (ind_id TEXT PRIMARY"
        " KEY, app TEXT NOT NULL, module TEXT NOT"
        " NULL DEFAULT '', indicator TEXT NOT NULL,"
        " value REAL NOT NULL, unit TEXT NOT NULL"
        " DEFAULT '', territory TEXT NOT NULL"
        " DEFAULT '', severity TEXT NOT NULL DEFAULT"
        " 'INFO', trend TEXT NOT NULL DEFAULT"
        " 'estable', event_id TEXT NOT NULL DEFAULT"
        " '', status TEXT NOT NULL DEFAULT 'activo',"
        " updated_at REAL NOT NULL)",
        "CREATE INDEX IF NOT EXISTS ix_gov_ind ON"
        " nx_gov_indicators (app, indicator)",
    )),
    Migration(2, "nx_gov_national", (
        "CREATE TABLE IF NOT EXISTS nx_gov_national ("
        " alert_id TEXT PRIMARY KEY, domain TEXT NOT"
        " NULL, indicator TEXT NOT NULL, current"
        "_value REAL NOT NULL, impact TEXT NOT NULL,"
        " recommendation TEXT NOT NULL, responsible"
        " TEXT NOT NULL DEFAULT '', severity TEXT"
        " NOT NULL DEFAULT 'ALTA', status TEXT NOT"
        " NULL DEFAULT 'activa', resolved_note TEXT"
        " NOT NULL DEFAULT '', created_at REAL NOT"
        " NULL, resolved_at REAL)",
    )),
    Migration(3, "nx_gov_events", (
        "CREATE TABLE IF NOT EXISTS nx_gov_events ("
        " ev_id TEXT PRIMARY KEY, source_app TEXT"
        " NOT NULL, event_type TEXT NOT NULL, ref"
        " TEXT NOT NULL DEFAULT '', detail TEXT NOT"
        " NULL DEFAULT '', prev_event TEXT NOT NULL"
        " DEFAULT '', severity TEXT NOT NULL DEFAULT"
        " 'INFO', created_at REAL NOT NULL)",
    )),
    Migration(4, "nx_gov_alarms", (
        "CREATE TABLE IF NOT EXISTS nx_gov_alarms ("
        " alarm_id TEXT PRIMARY KEY, kind TEXT NOT"
        " NULL, zone TEXT NOT NULL DEFAULT '', target"
        " TEXT NOT NULL DEFAULT '', subject TEXT NOT"
        " NULL, body TEXT NOT NULL DEFAULT '', status"
        " TEXT NOT NULL DEFAULT 'activa', created_at"
        " REAL NOT NULL, cleared_at REAL)",
    )),
)
_SEV = ("INFO", "MEDIA", "ALTA", "CRITICA")
_TRENDS = ("subiendo", "bajando", "estable")
_ALARMS = ("ZYRA_AMBER", "SISMO", "CRISIS",
           "EPIDEMIA", "OTRO")


class NationalIntelligenceEngine:
    """Panel Nacional de 3 capas + alarmas."""

    def __init__(self, db: Database, clock: Clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "nx.gov",
                        _MIGRATIONS).run(clock)

    def _sev_ok(self, s):
        v = str(s).upper()
        if v not in _SEV:
            raise ValueError(
                "severity debe ser "
                + "/".join(_SEV))
        return v

    def _trend_ok(self, t):
        v = str(t).lower()
        if v not in _TRENDS:
            raise ValueError("trend debe ser "
                             + "/".join(_TRENDS))
        return v

    def report_indicator(self, *, app, indicator,
                         value, module="",
                         unit="", territory="",
                         severity="INFO",
                         trend="estable",
                         event_id=""):
        if not str(app).strip() or \
                not str(indicator).strip():
            raise ValueError(
                "app e indicator requeridos")
        if float(value) < 0:
            raise ValueError(
                "value no negativo")
        iid = ("NXGI-"
               + uuid.uuid4().hex[:10])
        self._db.execute(
            "INSERT INTO nx_gov_indicators (ind_id,"
            " app, module, indicator, value, unit,"
            " territory, severity, trend, event_id,"
            " status, updated_at) VALUES (?, ?, ?, ?,"
            " ?, ?, ?, ?, ?, ?, 'activo', ?)",
            (iid, str(app), str(module),
             str(indicator), float(value),
             str(unit), str(territory),
             self._sev_ok(severity),
             self._trend_ok(trend),
             str(event_id), self._clock.now()))
        return {"ind_id": iid, "capa": "A"}

    def indicators_of(self, app, only_active=True):
        if only_active:
            rows = self._db.query_all(
                "SELECT ind_id, module, indicator,"
                " value, unit, territory, severity,"
                " trend FROM nx_gov_indicators WHERE"
                " app = ? AND status = 'activo' ORDER"
                " BY rowid", (str(app),))
        else:
            rows = self._db.query_all(
                "SELECT ind_id, module, indicator,"
                " value, unit, territory, severity,"
                " trend, status FROM"
                " nx_gov_indicators WHERE app = ?"
                " ORDER BY rowid", (str(app),))
        return [{"ind_id": str(r["ind_id"]),
                 "module": str(r["module"]),
                 "indicator": str(
                     r["indicator"]),
                 "value": float(r["value"]),
                 "severity": str(r["severity"]),
                 "trend": str(r["trend"])}
                for r in rows]

    def deactivate_indicator(self, ind_id):
        row = self._db.query_one(
            "SELECT status FROM nx_gov_indicators"
            " WHERE ind_id = ?", (str(ind_id),))
        if row is None:
            raise KeyError(ind_id)
        self._db.execute(
            "UPDATE nx_gov_indicators SET status ="
            " 'inactivo' WHERE ind_id = ?",
            (str(ind_id),))
        return {"ind_id": str(ind_id)}

    def raise_national_alert(self, *, domain,
                             indicator, current_value,
                             impact, recommendation,
                             responsible="",
                             severity="ALTA"):
        if not str(domain).strip() or \
                not str(indicator).strip() or \
                not str(impact).strip() or \
                not str(recommendation).strip():
            raise ValueError(
                "domain/indicator/impact/"
                "recommendation requeridos")
        aid = ("NXNA-"
               + uuid.uuid4().hex[:10])
        self._db.execute(
            "INSERT INTO nx_gov_national (alert_id,"
            " domain, indicator, current_value,"
            " impact, recommendation, responsible,"
            " severity, status, resolved_note,"
            " created_at, resolved_at) VALUES (?, ?,"
            " ?, ?, ?, ?, ?, ?, 'activa', '', ?,"
            " NULL)",
            (aid, str(domain), str(indicator),
             float(current_value), str(impact),
             str(recommendation),
             str(responsible),
             self._sev_ok(severity),
             self._clock.now()))
        return {"alert_id": aid, "capa": "B",
                "severity": self._sev_ok(
                    severity)}

    def resolve_national_alert(self, alert_id, *,
                               note=""):
        row = self._db.query_one(
            "SELECT status FROM nx_gov_national"
            " WHERE alert_id = ?",
            (str(alert_id),))
        if row is None:
            raise KeyError(alert_id)
        if str(row["status"]) != "activa":
            raise ValueError("ya resuelta")
        self._db.execute(
            "UPDATE nx_gov_national SET status ="
            " 'resuelta', resolved_note = ?,"
            " resolved_at = ? WHERE alert_id = ?",
            (str(note), self._clock.now(),
             str(alert_id)))
        return {"alert_id": str(alert_id),
                "status": "resuelta"}

    def active_alerts_db(self):
        rows = self._db.query_all(
            "SELECT alert_id, domain, indicator,"
            " impact, recommendation, responsible,"
            " severity FROM nx_gov_national WHERE"
            " status = 'activa' ORDER BY rowid")
        return [{"alert_id": str(r["alert_id"]),
                 "domain": str(r["domain"]),
                 "indicator": str(
                     r["indicator"]),
                 "impact": str(r["impact"]),
                 "recommendation": str(
                     r["recommendation"]),
                 "responsible": str(
                     r["responsible"]),
                 "severity": str(
                     r["severity"])}
                for r in rows]

    def chain_event(self, *, source_app, event_type,
                    ref="", detail="",
                    prev_event="", severity="INFO"):
        if not str(source_app).strip() or \
                not str(event_type).strip():
            raise ValueError(
                "source_app y event_type"
                " requeridos")
        eid = ("NXGE-"
               + uuid.uuid4().hex[:10])
        pe = ""
        if str(prev_event).strip():
            prow = self._db.query_one(
                "SELECT ev_id FROM nx_gov_events"
                " WHERE ev_id = ?",
                (str(prev_event),))
            if prow is None:
                raise LookupError(
                    "prev_event no existe: "
                    + str(prev_event))
            pe = str(prev_event)
        self._db.execute(
            "INSERT INTO nx_gov_events (ev_id,"
            " source_app, event_type, ref, detail,"
            " prev_event, severity, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (eid, str(source_app),
             str(event_type), str(ref),
             str(detail), pe,
             self._sev_ok(severity),
             self._clock.now()))
        return {"ev_id": eid, "capa": "C",
                "prev_event": pe}

    def causal_chain(self, ev_id):
        row = self._db.query_one(
            "SELECT ev_id, source_app, event_type,"
            " detail, prev_event FROM nx_gov_events"
            " WHERE ev_id = ?", (str(ev_id),))
        if row is None:
            raise KeyError(ev_id)
        chain = [{"ev_id": str(row["ev_id"]),
                  "source_app": str(
                      row["source_app"]),
                  "event_type": str(
                      row["event_type"]),
                  "detail": str(row["detail"])}]
        prev = str(row["prev_event"])
        guard = 0
        while prev and guard < 50:
            guard += 1
            p = self._db.query_one(
                "SELECT ev_id, source_app,"
                " event_type, detail, prev_event"
                " FROM nx_gov_events WHERE ev_id ="
                " ?", (prev,))
            if p is None:
                break
            chain.insert(0, {
                "ev_id": str(p["ev_id"]),
                "source_app": str(
                    p["source_app"]),
                "event_type": str(
                    p["event_type"]),
                "detail": str(p["detail"])})
            prev = str(p["prev_event"])
        return {"chain": chain,
                "length": len(chain)}

    def raise_alarm(self, *, kind, subject,
                    zone="", target="", body=""):
        k = str(kind).upper()
        if k not in _ALARMS:
            raise ValueError("kind debe ser "
                             + "/".join(_ALARMS))
        if not str(subject).strip():
            raise ValueError(
                "subject requerido")
        if k == "ZYRA_AMBER" and \
                not str(target).strip():
            raise ValueError(
                "ZYRA_AMBER exige target = ZID"
                " del menor (regla 78)")
        aid = ("NXAL-"
               + uuid.uuid4().hex[:10])
        self._db.execute(
            "INSERT INTO nx_gov_alarms (alarm_id,"
            " kind, zone, target, subject, body,"
            " status, created_at, cleared_at)"
            " VALUES (?, ?, ?, ?, ?, ?, 'activa',"
            " ?, NULL)",
            (aid, k, str(zone), str(target),
             str(subject), str(body),
             self._clock.now()))
        return {"alarm_id": aid, "kind": k,
                "status": "activa"}

    def clear_alarm(self, alarm_id):
        row = self._db.query_one(
            "SELECT status FROM nx_gov_alarms WHERE"
            " alarm_id = ?", (str(alarm_id),))
        if row is None:
            raise KeyError(alarm_id)
        if str(row["status"]) != "activa":
            raise ValueError("ya despejada")
        self._db.execute(
            "UPDATE nx_gov_alarms SET status ="
            " 'despejada', cleared_at = ? WHERE"
            " alarm_id = ?",
            (self._clock.now(),
             str(alarm_id)))
        return {"alarm_id": str(alarm_id),
                "status": "despejada"}

    def alarms_active_db(self, kind=""):
        if str(kind).strip():
            rows = self._db.query_all(
                "SELECT alarm_id, kind, zone, target,"
                " subject FROM nx_gov_alarms WHERE"
                " status = 'activa' AND kind = ?"
                " ORDER BY rowid",
                (str(kind).upper(),))
        else:
            rows = self._db.query_all(
                "SELECT alarm_id, kind, zone, target,"
                " subject FROM nx_gov_alarms WHERE"
                " status = 'activa' ORDER BY rowid")
        return [{"alarm_id": str(r["alarm_id"]),
                 "kind": str(r["kind"]),
                 "zone": str(r["zone"]),
                 "target": str(r["target"]),
                 "subject": str(r["subject"])}
                for r in rows]

    def national_snapshot(self):
        apps = self._db.query_all(
            "SELECT app, COUNT(*) AS n, SUM(CASE"
            " WHEN severity IN ('ALTA','CRITICA')"
            " THEN 1 ELSE 0 END) AS criticos FROM"
            " nx_gov_indicators WHERE status ="
            " 'activo' GROUP BY app ORDER BY app")
        return {"capa_b_alertas":
                    self.active_alerts_db(),
                "alarmas":
                    self.alarms_active_db(),
                "apps": [{"app": str(
                    r["app"]),
                    "indicadores": int(r["n"]),
                    "criticos": int(r["criticos"]
                                    or 0)}
                    for r in apps]}
