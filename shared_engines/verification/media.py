"""Media registry: photos, videos, audio, documents.

A media record stores the SHA-256 fingerprint of the
ORIGINAL content plus its kind. Later, presenting the
content again re-hashes against the registry: mismatch
means tampering and is audited + evented. The registry
never stores raw content, only fingerprints and metadata.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from enum import Enum

from shared_engines.audit.chain import AuditTrail
from shared_engines.common.clocks import Clock
from shared_engines.common.errors import IntegrityError
from shared_engines.common.identifiers import new_id
from shared_engines.common.validation import require_non_empty_str
from shared_engines.events.contracts import EventCatalog
from shared_engines.events.outbox import Outbox
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)
from shared_engines.verification.errors import (
    MediaNotFoundError,
    TamperDetectedError,
)

EVENT_MEDIA_REGISTERED = "verification.media.registered"
EVENT_MEDIA_TAMPER = "verification.media.tamper_detected"

MEDIA_MIGRATIONS = (
    Migration(
        1,
        "media",
        (
            "CREATE TABLE media ("
            " media_id TEXT PRIMARY KEY,"
            " owner_zid TEXT NOT NULL,"
            " kind TEXT NOT NULL,"
            " title TEXT NOT NULL,"
            " content_sha256 TEXT NOT NULL,"
            " content_size INTEGER NOT NULL,"
            " content_type TEXT NOT NULL,"
            " created_at REAL NOT NULL,"
            " contract_version INTEGER NOT NULL)",
            "CREATE INDEX media_owner ON media (owner_zid)",
            "CREATE INDEX media_kind ON media (kind)",
        ),
    ),
)


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class MediaKind(Enum):
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


@dataclass(frozen=True)
class MediaRecord:
    media_id: str
    owner_zid: str
    kind: MediaKind
    title: str
    content_sha256: str
    content_size: int
    content_type: str
    created_at: float
    contract_version: int


@dataclass(frozen=True)
class MediaPage:
    items: tuple[MediaRecord, ...]
    offset: int
    limit: int
    total: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


class MediaRegistry:
    """Durable registry of content fingerprints, any media kind."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        audit: AuditTrail,
        outbox: Outbox,
        catalog: EventCatalog,
    ) -> None:
        self._db = db
        self._clock = clock
        self._audit = audit
        self._outbox = outbox
        self._catalog = catalog
        MigrationRunner(
            db, "verification.media", MEDIA_MIGRATIONS
        ).run(clock)

    def register(
        self,
        *,
        owner_zid: str,
        kind: MediaKind,
        title: str,
        content: bytes,
        content_type: str,
        actor: str,
    ) -> MediaRecord:
        require_non_empty_str(owner_zid, "owner_zid")
        require_non_empty_str(title, "title")
        require_non_empty_str(content_type, "content_type")
        require_non_empty_str(actor, "actor")
        sha = content_sha256(content)
        media_id = f"MED-{new_id()}"
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO media"
                " (media_id, owner_zid, kind, title,"
                "  content_sha256, content_size, content_type,"
                "  created_at, contract_version)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    media_id,
                    owner_zid,
                    kind.value,
                    title,
                    sha,
                    len(content),
                    content_type,
                    now,
                    1,
                ),
            )
            event = self._catalog.build(
                EVENT_MEDIA_REGISTERED,
                aggregate_id=media_id,
                payload={
                    "media_id": media_id,
                    "owner_zid": owner_zid,
                    "kind": kind.value,
                    "content_sha256": sha,
                    "content_type": content_type,
                },
                clock=self._clock,
            )
            self._outbox.enqueue_in_transaction(cursor, event)
        self._audit.append(
            event_type=EVENT_MEDIA_REGISTERED,
            actor=actor,
            subject=media_id,
            payload={
                "content_sha256": sha,
                "owner_zid": owner_zid,
            },
        )
        record = self.get(media_id)
        if record is None:
            raise IntegrityError("media vanished after insert")
        return record

    def get(self, media_id: str) -> MediaRecord | None:
        row = self._db.query_one(
            "SELECT * FROM media WHERE media_id = ?", (media_id,)
        )
        if row is None:
            return None
        return self._record_from_row(row)

    def verify_content(
        self, media_id: str, content: bytes
    ) -> MediaRecord:
        record = self.get(media_id)
        if record is None:
            raise MediaNotFoundError(
                f"unknown media: {media_id}"
            )
        current = content_sha256(content)
        if current != record.content_sha256:
            self._audit.append(
                event_type=EVENT_MEDIA_TAMPER,
                actor="verification-engine",
                subject=media_id,
                payload={
                    "expected_sha256": record.content_sha256,
                    "observed_sha256": current,
                },
            )
            event = self._catalog.build(
                EVENT_MEDIA_TAMPER,
                aggregate_id=media_id,
                payload={
                    "expected_sha256": record.content_sha256,
                    "observed_sha256": current,
                },
                clock=self._clock,
            )
            self._outbox.enqueue(event)
            raise TamperDetectedError(
                f"content hash mismatch for {media_id}:"
                " the media does not match the registry"
            )
        return record

    def list_by_owner(
        self,
        owner_zid: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> MediaPage:
        total_row = self._db.query_one(
            "SELECT COUNT(*) AS n FROM media WHERE owner_zid = ?",
            (owner_zid,),
        )
        total = int(total_row["n"]) if total_row is not None else 0
        rows = self._db.query_all(
            "SELECT * FROM media WHERE owner_zid = ?"
            " ORDER BY created_at, media_id LIMIT ? OFFSET ?",
            (owner_zid, limit, offset),
        )
        items = tuple(self._record_from_row(row) for row in rows)
        return MediaPage(
            items=items, offset=offset, limit=limit, total=total
        )

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> MediaRecord:
        return MediaRecord(
            media_id=str(row["media_id"]),
            owner_zid=str(row["owner_zid"]),
            kind=MediaKind(str(row["kind"])),
            title=str(row["title"]),
            content_sha256=str(row["content_sha256"]),
            content_size=int(row["content_size"]),
            content_type=str(row["content_type"]),
            created_at=float(row["created_at"]),
            contract_version=int(row["contract_version"]),
        )
