
"""Agro Risk Unified (A-13): riesgo agrícola
unificado del productor con formula TRANSPARENTE
(regla 66): clima (alta 60/media 30/baja 10) +
productivo (losses/production*100 tope 100) +
impacto (affected/total*100 tope 100) - resiliencia
(recovery/affected*20 tope 20). Componentes omitidos
con razon en not_evaluated. Los services duenos
(climate/productive/impact/resilience) se invocan
via _fit_kwargs y su respuesta cruda viaja en
components (trazabilidad, regla 69). Historial
persistente. Patron _DDL + ensure_db DIRECTO
(unificado con los demas: sin MigrationRunner)."""
from __future__ import annotations
import inspect as _insp
import json as _j
import uuid
from shared_engines.storage.database import (
    Database)
from apps.agro.modules.riesgo.riesgo_climatico.climate_risk_service import (
    ClimateRiskService)
from apps.agro.modules.riesgo.riesgo_productivo.productive_risk_service import (
    ProductiveRiskService)
from apps.agro.modules.riesgo.impacto.impact_service import (
    ImpactService)
from apps.agro.modules.riesgo.resiliencia.resilience_service import (
    ResilienceService)

_PK = _insp.Parameter

def _fit_kwargs(func, desired):
    try:
        params = _insp.signature(
            func).parameters
    except (TypeError, ValueError):
        return dict(desired)
    if any(p.kind == _PK.VAR_KEYWORD
           for p in params.values()):
        return dict(desired)
    ok = set()
    for n, p in params.items():
        if p.kind in (_PK.POSITIONAL_OR_KEYWORD,
                      _PK.KEYWORD_ONLY):
            ok.add(n)
    return {k: v for k, v in desired.items()
            if k in ok}

_DDL = (
    "CREATE TABLE IF NOT EXISTS agro_risk_unified ("
    " risk_id TEXT PRIMARY KEY, producer_id TEXT"
    " NOT NULL, score INTEGER NOT NULL, level TEXT"
    " NOT NULL, components_json TEXT NOT NULL"
    " DEFAULT '{}', not_evaluated_json TEXT NOT"
    " NULL DEFAULT '[]', created_at REAL NOT NULL)",
)
_SEV = {"alta": 60, "media": 30, "baja": 10}


def ensure_db(db):
    for stmt in _DDL:
        db.execute(stmt)


def level_of(score):
    s = int(score)
    if s >= 80:
        return "CRITICAL"
    if s >= 60:
        return "HIGH"
    if s >= 30:
        return "MEDIUM"
    return "LOW"


def evaluate_db(db, *, producer_id,
                event_type=None, severity=None,
                losses=None, production=None,
                affected_units=None,
                total_units=None,
                recovered=None, created_at=0.0):
    pts = 0
    bonus = 0
    comps = []
    ne = []
    if event_type is not None:
        sev = str(severity or "media").lower()
        cpts = _SEV.get(sev)
        if cpts is None:
            ne.append("CLIMA: severidad"
                      " invalida")
        else:
            pts += cpts
            raw = None
            try:
                svc = ClimateRiskService()
                fn = svc.evaluate
                raw = fn(**_fit_kwargs(
                    fn,
                    {"event_type":
                         str(event_type),
                     "severity": sev}))
            except Exception:
                raw = None
            comps.append({"kind": "CLIMA",
                          "points": cpts,
                          "raw": _j.dumps(
                              raw,
                              default=str)[:200]})
    else:
        ne.append("CLIMA: sin evento")
    if losses is not None and production:
        if float(production) <= 0:
            ne.append("PRODUCTIVO: production"
                      " debe ser > 0")
        else:
            ratio = min(100.0, float(losses)
                        * 100.0
                        / float(production))
            pts += int(ratio)
            raw = None
            try:
                svc = ProductiveRiskService()
                fn = svc.evaluate
                raw = fn(**_fit_kwargs(
                    fn,
                    {"losses": float(losses),
                     "production": float(
                         production)}))
            except Exception:
                raw = None
            comps.append({"kind":
                          "PRODUCTIVO",
                          "points": int(ratio),
                          "raw": _j.dumps(
                              raw,
                              default=str)[:200]})
    else:
        ne.append("PRODUCTIVO: sin losses/"
                  "production")
    if (affected_units is not None
            and total_units):
        if float(total_units) <= 0:
            ne.append("IMPACTO: total debe ser"
                      " > 0")
        else:
            ipct = min(100.0, float(
                affected_units) * 100.0
                / float(total_units))
            pts += int(ipct)
            raw = None
            try:
                svc = ImpactService()
                fn = svc.calculate
                raw = fn(**_fit_kwargs(
                    fn,
                    {"affected_units": float(
                        affected_units),
                     "total_units": float(
                         total_units)}))
            except Exception:
                raw = None
            comps.append({"kind": "IMPACTO",
                          "points": int(ipct),
                          "raw": _j.dumps(
                              raw,
                              default=str)[:200]})
    else:
        ne.append("IMPACTO: sin unidades")
    if recovered is not None and affected_units:
        if float(affected_units) <= 0:
            ne.append("RESILIENCIA: affected"
                      " debe ser > 0")
        else:
            bonus = min(20, int(float(
                recovered) * 20.0
                / float(affected_units)))
            raw = None
            try:
                svc = ResilienceService()
                fn = svc.recovery_score
                raw = fn(**_fit_kwargs(
                    fn,
                    {"recovered": float(
                        recovered),
                     "affected": float(
                         affected_units)}))
            except Exception:
                raw = None
            comps.append({"kind":
                          "RESILIENCIA",
                          "points": -bonus,
                          "raw": _j.dumps(
                              raw,
                              default=str)[:200]})
    else:
        ne.append("RESILIENCIA: sin recovery")
    score = max(0, min(100, pts - bonus))
    rid = ("AGRK-"
           + uuid.uuid4().hex[:10])
    ensure_db(db)
    db.execute(
        "INSERT INTO agro_risk_unified (risk_id,"
        " producer_id, score, level, components"
        "_json, not_evaluated_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (rid, str(producer_id), score,
         level_of(score),
         _j.dumps(comps, default=str),
         _j.dumps(ne, default=str),
         float(created_at)))
    return {"risk_id": rid,
            "producer_id": str(producer_id),
            "score": score,
            "level": level_of(score),
            "components": comps,
            "not_evaluated": ne}


def history_of_db(db, producer_id):
    ensure_db(db)
    rows = db.query_all(
        "SELECT risk_id, score, level, created_at"
        " FROM agro_risk_unified WHERE producer_id"
        " = ? ORDER BY rowid",
        (str(producer_id),))
    return [{"risk_id": str(r["risk_id"]),
             "score": int(r["score"]),
             "level": str(r["level"]),
             "created_at": float(
                 r["created_at"])}
            for r in rows]


def worst_of_db(db, limit=10):
    ensure_db(db)
    rows = db.query_all(
        "SELECT producer_id, MAX(score) AS worst,"
        " COUNT(*) AS n FROM agro_risk_unified"
        " GROUP BY producer_id ORDER BY worst DESC"
        " LIMIT ?", (int(limit),))
    return [{"producer_id": str(
                 r["producer_id"]),
             "worst": int(r["worst"]),
             "n": int(r["n"])}
            for r in rows]
