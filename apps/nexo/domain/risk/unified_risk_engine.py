
"""Unified Risk Engine (N-7) - scoring
unificado sobre los MOTORES REALES de NEXO
(regla 69: los compone, no los duplica):
compliance, financial, operational, country,
supply chain, geopolitical, fraud, sanctions.

v2 (contrato del docstring cumplido):
- components: componentes EVALUADOS (motor
  real corrio y devolvio score)
- skipped: intentos FALLIDOS (excepcion o
  respuesta sin score) con razon
- not_evaluated: puertas NO INTENTADAS por
  falta de datos, con razon exacta
  ("FINANCIAL: sin datos (accounting_data
  +finance_data requeridos)") — la omision
  tambien es visible y honesta (regla 66)
- ValueError si nada evaluable, listando
  fallos y omisiones.

score unificado = promedio ponderado 0..100;
level CRITICAL>=80/HIGH>=60/MEDIUM>=30/LOW;
cross-check con RiskScoringEngine real via
_fit_kwargs; historial persistente
nexo_risk_history por entity_ref;
RiskMonitorEngine.register; worst_entities.
Regla 76: ORDER BY rowid."""
from __future__ import annotations
import inspect as _insp
import json as _j
import uuid
from typing import Dict, List, Optional
from shared_engines.common.clocks import (
    Clock)
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)
from apps.nexo.domain.risk.compliance_risk_engine import (
    ComplianceRiskEngine)
from apps.nexo.domain.risk.country_risk_engine import (
    CountryRiskEngine)
from apps.nexo.domain.risk.financial_risk_engine import (
    FinancialRiskEngine)
from apps.nexo.domain.risk.fraud_detection_engine import (
    FraudDetectionEngine)
from apps.nexo.domain.risk.geopolitical_risk_engine import (
    GeopoliticalRiskEngine)
from apps.nexo.domain.risk.operational_risk_engine import (
    OperationalRiskEngine)
from apps.nexo.domain.risk.risk_monitor_engine import (
    RiskMonitorEngine)
from apps.nexo.domain.risk.risk_scoring_engine import (
    RiskScoringEngine)
from apps.nexo.domain.risk.sanctions_engine import (
    SanctionsEngine)
from apps.nexo.domain.risk.supply_chain_risk_engine import (
    SupplyChainRiskEngine)

_PK = _insp.Parameter

def _fit_kwargs(func, desired):
    """Solo pasa los kwargs que la firma REAL
    acepta. ValueError si falta un
    requerido."""
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
        if p.kind in (
                _PK.POSITIONAL_OR_KEYWORD,
                _PK.KEYWORD_ONLY):
            ok.add(n)
    res = {k: v for k, v in
           desired.items() if k in ok}
    for n, p in params.items():
        if (n != "self" and n not in res
                and p.default is _PK.empty
                and p.kind in (
                    _PK.POSITIONAL_OR_KEYWORD,
                    _PK.KEYWORD_ONLY)):
            raise ValueError(
                "firma incompatible:"
                " falta " + str(n))
    return res

_MIGRATIONS = (
    Migration(1, "nexo_risk_history", (
        "CREATE TABLE IF NOT EXISTS"
        " nexo_risk_history (risk_id TEXT"
        " PRIMARY KEY, entity_ref TEXT NOT"
        " NULL, kind TEXT NOT NULL DEFAULT"
        " 'UNIFIED', score INTEGER NOT NULL"
        " DEFAULT 0, level TEXT NOT NULL"
        " DEFAULT 'LOW', components_json"
        " TEXT NOT NULL DEFAULT '{}',"
        " payload_json TEXT NOT NULL DEFAULT"
        " '{}', created_at REAL NOT NULL)",
    )),
)

class UnifiedRiskEngine:
    """Scoring unificado (N-7)."""

    def __init__(self, db, clock,
                 engines=None):
        self._db = db
        self._clock = clock
        e = engines or {}
        self._compliance = (
            e.get("compliance")
            or ComplianceRiskEngine())
        self._sanctions = (
            e.get("sanctions")
            or SanctionsEngine())
        self._financial = (
            e.get("financial")
            or FinancialRiskEngine())
        self._operational = (
            e.get("operational")
            or OperationalRiskEngine())
        self._country = (
            e.get("country")
            or CountryRiskEngine())
        self._supply = (
            e.get("supply")
            or SupplyChainRiskEngine())
        self._geo = (
            e.get("geo")
            or GeopoliticalRiskEngine())
        self._fraud = (
            e.get("fraud")
            or FraudDetectionEngine())
        self._scoring = (
            e.get("scoring")
            or RiskScoringEngine())
        self._monitor = (
            e.get("monitor")
            or RiskMonitorEngine())
        MigrationRunner(
            db, "nexo.unifiedrisk",
            _MIGRATIONS).run(clock)

    @staticmethod
    def level_of(score) -> str:
        s = int(score)
        if s >= 80:
            return "CRITICAL"
        if s >= 60:
            return "HIGH"
        if s >= 30:
            return "MEDIUM"
        return "LOW"

    def _run(self, kind, engine, method,
             desired, reasons):
        try:
            fn = getattr(engine, method)
            kw = _fit_kwargs(
                fn, dict(desired))
            res = fn(**kw)
        except Exception as exc:
            reasons.append(
                kind + ": "
                + str(exc)[:80])
            return None
        if (not isinstance(res, dict)) \
                or ("score" not in res):
            reasons.append(
                kind + ": respuesta sin"
                " score")
            return None
        sc = int(res["score"])
        return {"kind": kind,
                "score": sc,
                "level": str(res.get(
                    "level",
                    self.level_of(sc))),
                "risk_id": str(res.get(
                    "risk_id", ""))}

    def evaluate_entity(self, *,
                        entity_ref,
                        compliance_record=None,
                        sanctions_result=None,
                        entity_data=None,
                        accounting_data=None,
                        finance_data=None,
                        logistics_data=None,
                        operations_data=None,
                        supplier_data=None,
                        client_data=None,
                        country_code="",
                        geopolitical_data=None,
                        geopolitical_events=None,
                        weights=None) -> dict:
        reasons = []
        not_evaluated = []
        comps = []

        def note_skip(kind, req):
            not_evaluated.append(
                kind + ": sin datos ("
                + req + " requeridos)")

        def run(kind, engine, method,
                desired):
            r = self._run(
                kind, engine, method,
                desired, reasons)
            if r is not None:
                comps.append(r)

        sr = sanctions_result
        if compliance_record is not None:
            if (sr is None
                    and entity_data
                    is not None):
                try:
                    fn = \
                        self._sanctions \
                        .evaluate
                    sr = fn(**_fit_kwargs(
                        fn,
                        {"entity_data":
                         entity_data}))
                except Exception:
                    sr = {}
            if not isinstance(sr, dict):
                sr = {}
            run("COMPLIANCE",
                self._compliance,
                "evaluate",
                {"compliance_record":
                     compliance_record,
                 "sanctions_result": sr})
        else:
            note_skip("COMPLIANCE",
                      "compliance_record")
        if (accounting_data is not None
                and finance_data
                is not None):
            run("FINANCIAL",
                self._financial,
                "evaluate",
                {"accounting_data":
                     accounting_data,
                 "finance_data":
                     finance_data})
        else:
            note_skip("FINANCIAL",
                      "accounting_data"
                      "+finance_data")
        if (logistics_data is not None
                and operations_data
                is not None):
            run("OPERATIONAL",
                self._operational,
                "evaluate",
                {"logistics_data":
                     logistics_data,
                 "operations_data":
                     operations_data})
        else:
            note_skip("OPERATIONAL",
                      "logistics_data"
                      "+operations_data")
        if str(country_code).strip():
            gd = (geopolitical_data
                  if geopolitical_data
                  is not None else {})
            sd = {"risk_score": 0}
            if (isinstance(sr, dict)
                    and "risk_score"
                    in sr):
                sd = sr
            run("COUNTRY",
                self._country, "evaluate",
                {"country_code":
                     str(country_code),
                 "geopolitical_data": gd,
                 "sanctions_data": sd})
        else:
            note_skip("COUNTRY",
                      "country_code")
        if (logistics_data is not None
                and supplier_data
                is not None):
            run("SUPPLY_CHAIN",
                self._supply, "evaluate",
                {"logistics_data":
                     logistics_data,
                 "supplier_data":
                     supplier_data})
        else:
            note_skip("SUPPLY_CHAIN",
                      "logistics_data"
                      "+supplier_data")
        if (str(country_code).strip()
                and geopolitical_events
                is not None):
            run("GEOPOLITICAL",
                self._geo, "evaluate",
                {"country_code":
                     str(country_code),
                 "geopolitical_events":
                     geopolitical_events})
        else:
            note_skip("GEOPOLITICAL",
                      "country_code"
                      "+geopolitical_"
                      "events")
        if (client_data is not None
                and accounting_data
                is not None
                and operations_data
                is not None):
            run("FRAUD", self._fraud,
                "detect",
                {"client_data":
                     client_data,
                 "accounting_data":
                     accounting_data,
                 "operations_data":
                     operations_data})
        else:
            note_skip("FRAUD",
                      "client_data"
                      "+accounting_data"
                      "+operations_data")

        if not comps:
            raise ValueError(
                "sin componentes"
                " evaluables: "
                + ("; ".join(
                    reasons
                    + not_evaluated)
                   if (reasons
                       or not_evaluated)
                   else "sin datos de"
                        " entrada"))

        wmap = {str(k): float(v)
                for k, v in (
                    weights
                    or {}).items()}
        acc = 0.0
        tot = 0.0
        for c in comps:
            w = wmap.get(c["kind"], 1.0)
            acc += float(c["score"]) * w
            tot += w
        score = (int(round(acc / tot))
                 if tot else 0)
        score = max(0, min(100, score))
        level = self.level_of(score)

        engine_score = None
        try:
            desired = {}
            for c in comps:
                desired[str(
                    c["kind"]).lower()
                    + "_risk"] = int(
                    c["score"])
            fn = self._scoring.calculate
            kw = _fit_kwargs(fn, desired)
            r2 = fn(**kw)
            if (isinstance(r2, dict)
                    and "score"
                    in r2):
                engine_score = int(
                    r2["score"])
        except Exception:
            engine_score = None

        risk_id = ("UNI-"
                   + uuid.uuid4()
                   .hex[:12])
        result = {
            "risk_id": risk_id,
            "entity_ref":
                str(entity_ref),
            "score": score,
            "level": level,
            "components": comps,
            "skipped": reasons,
            "not_evaluated":
                not_evaluated,
            "engine_score":
                engine_score,
            "generated_at":
                self._clock.now()}
        self._db.execute(
            "INSERT INTO"
            " nexo_risk_history"
            " (risk_id, entity_ref,"
            " kind, score, level,"
            " components_json,"
            " payload_json, created_at)"
            " VALUES (?, ?, 'UNIFIED',"
            " ?, ?, ?, ?, ?)",
            (risk_id,
             str(entity_ref), score,
             level,
             _j.dumps(comps,
                      default=str),
             _j.dumps(
                 {"skipped": reasons,
                  "not_evaluated":
                      not_evaluated,
                  "engine_score":
                      engine_score},
                 default=str),
             self._clock.now()))
        try:
            fn = self._monitor.register
            fn(**_fit_kwargs(
                fn,
                {"risk_result":
                 result}))
            result["monitor_ok"] = True
        except Exception:
            result["monitor_ok"] = False
        return result

    def history_of(self,
                   entity_ref) -> List[dict]:
        rows = self._db.query_all(
            "SELECT risk_id, kind, score,"
            " level, components_json,"
            " created_at FROM"
            " nexo_risk_history WHERE"
            " entity_ref = ? ORDER BY"
            " rowid", (str(entity_ref),))
        out = []
        for r in rows:
            try:
                comps = _j.loads(str(
                    r["components_json"]))
            except Exception:
                comps = []
            out.append({
                "risk_id": str(
                    r["risk_id"]),
                "kind": str(r["kind"]),
                "score": int(r["score"]),
                "level": str(r["level"]),
                "components": comps,
                "created_at": float(
                    r["created_at"])})
        return out

    def worst_entities(self,
                       limit=10) -> List[dict]:
        rows = self._db.query_all(
            "SELECT entity_ref,"
            " MAX(score) AS worst,"
            " COUNT(*) AS n FROM"
            " nexo_risk_history GROUP BY"
            " entity_ref ORDER BY worst"
            " DESC, entity_ref LIMIT ?",
            (int(limit),))
        return [{
            "entity_ref": str(
                r["entity_ref"]),
            "worst": int(r["worst"]),
            "n": int(r["n"])}
            for r in rows]
