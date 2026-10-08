from datetime import timezone

class ProducerDocumentService:
    def register(self, producer_id, document):
        return {
            "producer_id": producer_id,
            "document": document,
            "status": "registered"
        }


# ---- additive PLUS (GPT-1): tipos, rechazo, vigencia ----
VALID_DOC_KINDS = (
    "dui", "nit", "licencia",
    "titulo", "rtn", "carnet",
)
DOC_EXPIRY_DAYS = 365


def register_doc_plus_db(
    db, *, producer_id, doc_kind,
    content_b64,
):
    import hashlib as _hl
    import time as _t
    import uuid as _u
    if str(doc_kind) not in VALID_DOC_KINDS:
        raise ValueError(
            "tipo de documento invalido: "
            + str(doc_kind)
        )
    if not str(content_b64 or "").strip():
        raise ValueError(
            "contenido del documento obligatorio"
        )
    digest = _hl.sha256(
        str(content_b64).encode("utf-8")
    ).hexdigest()
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_docs_plus ("
        " doc_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " doc_kind TEXT NOT NULL,"
        " content_sha256 TEXT NOT NULL,"
        " status TEXT NOT NULL,"
        " reviewer TEXT, review_note TEXT,"
        " verified_at TEXT, expiry_at TEXT,"
        " created_at TEXT)"
    )
    doc_id = "DOCAG-" + _u.uuid4().hex[:10]
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO agro_docs_plus (doc_id,"
        " producer_id, doc_kind,"
        " content_sha256, status, reviewer,"
        " review_note, verified_at, expiry_at,"
        " created_at) VALUES (?, ?, ?, ?,"
        " 'pending', NULL, NULL, NULL, NULL, ?)",
        (doc_id, producer_id, doc_kind,
         digest, ts),
    )
    return {
        "doc_id": doc_id,
        "producer_id": producer_id,
        "doc_kind": doc_kind,
        "content_sha256": digest,
        "status": "pending",
    }


def verify_doc_plus_db(
    db, *, doc_id, reviewer,
    approve=True, note="",
):
    import time as _t
    from datetime import datetime, timedelta
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    if approve:
        exp = (
            datetime.now(timezone.utc)
            + timedelta(days=DOC_EXPIRY_DAYS)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.execute(
            "UPDATE agro_docs_plus SET"
            " status = 'verified',"
            " reviewer = ?, review_note = ?,"
            " verified_at = ?, expiry_at = ?"
            " WHERE doc_id = ?",
            (reviewer, str(note or ""), ts,
             exp, doc_id),
        )
        return {
            "doc_id": doc_id,
            "status": "verified",
            "verified_at": ts,
            "expiry_at": exp,
        }
    if not str(note or "").strip():
        raise ValueError(
            "rechazo requiere motivo"
        )
    db.execute(
        "UPDATE agro_docs_plus SET"
        " status = 'rejected', reviewer = ?,"
        " review_note = ? WHERE doc_id = ?",
        (reviewer, str(note), doc_id),
    )
    return {
        "doc_id": doc_id,
        "status": "rejected",
        "note": str(note),
    }


def documents_plus_of_db(db, producer_id):
    import time as _t
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT doc_id, producer_id,"
                    " doc_kind, content_sha256,"
                    " status, reviewer,"
                    " review_note, verified_at,"
                    " expiry_at, created_at FROM"
                    " agro_docs_plus WHERE"
                    " producer_id = ?"
                    " ORDER BY created_at",
                    (producer_id,),
                )
            except Exception:
                got = None
            if got:
                now = _t.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    _t.gmtime(),
                )
                out = []
                for r in got:
                    d = dict(r)
                    exp = str(
                        d.get("expiry_at") or ""
                    )
                    d["expired"] = bool(
                        d.get("status")
                        == "verified"
                        and exp and exp < now
                    )
                    out.append(d)
                return out
    return []
