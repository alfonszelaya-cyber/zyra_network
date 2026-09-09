"""AI engine: model registry + analysis
provenance. Honest by design: real models are
registered at the composition root; the engine
durably records WHAT model (id, version)
analyzed WHAT content (sha256) with WHAT result
(verdict + confidence). No fake detection."""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.errors import (
    NotFoundError,
)
from shared_engines.common.identifiers import (
    new_id,
)
from shared_engines.common.serialization import (
    canonical_json_dumps,
)
from shared_engines.common.validation import (
    require_non_empty_str,
)
from shared_engines.events.outbox import Outbox
from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

EVENT_ANALYSIS = "ai.analysis.recorded"

_MIGRATIONS = (
    Migration(
        1,
        "ai",
        (
            "CREATE TABLE ai_models ("
            " model_id TEXT PRIMARY KEY,"
            " provider TEXT NOT NULL,"
            " model_version TEXT NOT"
            " NULL,"
            " capabilities TEXT NOT"
            " NULL,"
            " active INTEGER NOT NULL,"
            " registered_at REAL NOT"
            " NULL)",
            "CREATE TABLE ai_analyses ("
            " analysis_id TEXT PRIMARY"
            " KEY,"
            " model_id TEXT NOT NULL,"
            " model_version TEXT NOT"
            " NULL,"
            " content_sha256 TEXT NOT"
            " NULL,"
            " verdict TEXT NOT NULL,"
            " confidence REAL NOT NULL,"
            " analyzed_at REAL NOT"
            " NULL)",
            "CREATE INDEX ai_content"
            " ON ai_analyses"
            " (content_sha256)",
        ),
    ),
)


class UnknownModelError(NotFoundError):
    """Model not registered or inactive."""


@dataclass(frozen=True)
class ModelRecord:
    model_id: str
    provider: str
    model_version: str
    capabilities: tuple[str, ...]
    active: bool


@dataclass(frozen=True)
class AnalysisRecord:
    analysis_id: str
    model_id: str
    model_version: str
    content_sha256: str
    verdict: str
    confidence: float
    analyzed_at: float


class AIEngine:
    """Traceable AI provenance."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        audit: AuditTrail,
        outbox: Outbox,
    ) -> None:
        self._db = db
        self._clock = clock
        self._audit = audit
        self._outbox = outbox
        MigrationRunner(
            db, "ai", _MIGRATIONS
        ).run(clock)

    def _emit(
        self,
        cursor: sqlite3.Cursor,
        *,
        aggregate: str,
        payload: dict[str, object],
    ) -> None:
        uid = hashlib.sha256(
            canonical_json_dumps(
                {
                    "a": aggregate,
                    "u": new_id(),
                }
            ).encode("utf-8")
        ).hexdigest()[:32]
        fp = hashlib.sha256(
            canonical_json_dumps(
                {
                    "id": uid,
                    "ty": EVENT_ANALYSIS,
                }
            ).encode("utf-8")
        ).hexdigest()
        cursor.execute(
            "INSERT INTO events_outbox"
            " (event_id, event_type,"
            " aggregate_id, schema_version,"
            " envelope_version, created_at,"
            " payload, fingerprint,"
            " published_at)"
            " VALUES (?, ?, ?, 1, 1, ?, ?,"
            " ?, NULL)",
            (
                uid,
                EVENT_ANALYSIS,
                aggregate,
                self._clock.now(),
                canonical_json_dumps(
                    payload
                ),
                fp,
            ),
        )

    def register_model(
        self,
        *,
        model_id: str,
        provider: str,
        model_version: str,
        capabilities: tuple[str, ...],
    ) -> ModelRecord:
        require_non_empty_str(
            model_id, "model_id"
        )
        require_non_empty_str(
            provider, "provider"
        )
        require_non_empty_str(
            model_version,
            "model_version",
        )
        clean: list[str] = []
        for cap in capabilities:
            require_non_empty_str(
                cap, "capability"
            )
            if cap not in clean:
                clean.append(cap)
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO ai_models"
                " (model_id, provider,"
                "  model_version,"
                "  capabilities,"
                "  active, registered_at)"
                " VALUES (?, ?, ?, ?, 1, ?)"
                " ON CONFLICT(model_id)"
                " DO UPDATE SET provider"
                " = excluded.provider,"
                " model_version ="
                " excluded"
                ".model_version,"
                " capabilities ="
                " excluded.capabilities,"
                " active = 1",
                (
                    model_id,
                    provider,
                    model_version,
                    ",".join(clean),
                    self._clock.now(),
                ),
            )
        return ModelRecord(
            model_id=model_id,
            provider=provider,
            model_version=(
                model_version
            ),
            capabilities=tuple(clean),
            active=True,
        )

    def _model_version(
        self, model_id: str
    ) -> str:
        row = self._db.query_one(
            "SELECT model_version,"
            " active FROM ai_models"
            " WHERE model_id = ?",
            (model_id,),
        )
        if row is None:
            raise UnknownModelError(
                "unknown model:"
                f" {model_id}"
            )
        if int(row["active"]) != 1:
            raise UnknownModelError(
                "model deactivated:"
                f" {model_id}"
            )
        return str(
            row["model_version"]
        )

    def record_analysis(
        self,
        *,
        model_id: str,
        content_sha256: str,
        verdict: str,
        confidence: float,
    ) -> AnalysisRecord:
        model_version = (
            self._model_version(model_id)
        )
        require_non_empty_str(
            content_sha256,
            "content_sha256",
        )
        require_non_empty_str(
            verdict, "verdict"
        )
        if not (
            0.0 <= confidence <= 1.0
        ):
            raise ValueError(
                "confidence must be"
                " within [0, 1]"
            )
        analysis_id = (
            f"AI-{new_id()[:12]}"
        )
        now = self._clock.now()
        with (
            self._db.transaction()
            as cursor
        ):
            cursor.execute(
                "INSERT INTO ai_analyses"
                " (analysis_id, model_id,"
                "  model_version,"
                "  content_sha256, verdict,"
                "  confidence, analyzed_at)"
                " VALUES (?, ?, ?, ?, ?, ?,"
                "  ?)",
                (
                    analysis_id,
                    model_id,
                    model_version,
                    content_sha256,
                    verdict,
                    confidence,
                    now,
                ),
            )
            self._emit(
                cursor,
                aggregate=analysis_id,
                payload={
                    "model": model_id,
                    "verdict": verdict,
                },
            )
        self._audit.append(
            event_type=EVENT_ANALYSIS,
            actor=model_id,
            subject=analysis_id,
            payload={
                "verdict": verdict
            },
        )
        return AnalysisRecord(
            analysis_id=analysis_id,
            model_id=model_id,
            model_version=(
                model_version
            ),
            content_sha256=(
                content_sha256
            ),
            verdict=verdict,
            confidence=confidence,
            analyzed_at=now,
        )

    def analysis_history(
        self, *, content_sha256: str
    ) -> tuple[AnalysisRecord, ...]:
        require_non_empty_str(
            content_sha256,
            "content_sha256",
        )
        rows = self._db.query_all(
            "SELECT * FROM ai_analyses"
            " WHERE content_sha256 = ?"
            " ORDER BY analyzed_at",
            (content_sha256,),
        )
        return tuple(
            AnalysisRecord(
                analysis_id=str(
                    r["analysis_id"]
                ),
                model_id=str(
                    r["model_id"]
                ),
                model_version=str(
                    r["model_version"]
                ),
                content_sha256=str(
                    r["content_sha256"]
                ),
                verdict=str(
                    r["verdict"]
                ),
                confidence=float(
                    r["confidence"]
                ),
                analyzed_at=float(
                    r["analyzed_at"]
                ),
            )
            for r in rows
        )
