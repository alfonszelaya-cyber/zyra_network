
class ProducerProfile:
    def update(self, producer, **data):
        for key, value in data.items():
            if hasattr(producer, key):
                setattr(producer, key, value)

        producer.touch()
        return producer


# ---- additive PLUS (GPT-1): validacion e historial ----
def _agro_valid_phone(phone):
    digits = "".join(
        c for c in str(phone or "") if c.isdigit()
    )
    return 7 <= len(digits) <= 15


def get_profile_db(db, producer_id):
    for name in ("query_one", "query"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                row = fn(
                    "SELECT producer_id, phone,"
                    " location, notes, updated_at"
                    " FROM agro_producer_profiles"
                    " WHERE producer_id = ?",
                    (producer_id,),
                )
            except Exception:
                row = None
            if row:
                return dict(row)
    return {
        "producer_id": producer_id,
        "phone": "", "location": "",
        "notes": "",
    }


def update_profile_db(
    db, *, producer_id,
    phone="", location="",
    notes="", actor="anon",
):
    import time as _t
    if phone and not _agro_valid_phone(phone):
        raise ValueError(
            "telefono invalido (7-15 digitos)"
        )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_producer_profiles ("
        " producer_id TEXT PRIMARY KEY,"
        " phone TEXT, location TEXT,"
        " notes TEXT, updated_at TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_profile_history ("
        " hid INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " producer_id TEXT NOT NULL,"
        " actor TEXT NOT NULL,"
        " changed TEXT NOT NULL,"
        " at TEXT NOT NULL)"
    )
    prev = get_profile_db(db, producer_id)
    changed = []
    for field in ("phone", "location", "notes"):
        if str(prev.get(field) or "") != str(
            locals().get(field) or ""
        ):
            changed.append(field)
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    db.execute(
        "INSERT INTO"
        " agro_producer_profiles ("
        " producer_id, phone, location,"
        " notes, updated_at)"
        " VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(producer_id)"
        " DO UPDATE SET phone ="
        " excluded.phone, location ="
        " excluded.location, notes ="
        " excluded.notes, updated_at ="
        " excluded.updated_at",
        (producer_id, phone, location,
         notes, ts),
    )
    db.execute(
        "INSERT INTO agro_profile_history ("
        " producer_id, actor, changed, at)"
        " VALUES (?, ?, ?, ?)",
        (producer_id, str(actor),
         ",".join(changed) or "none", ts),
    )
    return {
        "producer_id": producer_id,
        "phone": phone,
        "location": location,
        "notes": notes,
        "updated_at": ts,
        "changed": changed,
    }


def get_profile_history_db(
    db, producer_id, limit=50,
):
    for name in ("query_all", "query", "fetchall"):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT hid, producer_id,"
                    " actor, changed, at FROM"
                    " agro_profile_history WHERE"
                    " producer_id = ? ORDER BY"
                    " hid DESC LIMIT ?",
                    (producer_id, int(limit)),
                )
            except Exception:
                got = None
            if got:
                return [dict(r) for r in got]
    return []
