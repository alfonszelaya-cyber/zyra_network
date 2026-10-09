"""ZID Vault Engine (ID-4) - bodega de secretos por
ZID: sellado con cifrado de flujo stdlib (sha256
keystream) + HMAC de integridad. JAMAS en claro
(regla 63). Reglas 63/66/76."""
from __future__ import annotations
import hashlib, hmac, os, uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import Database
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_MIGRATIONS = (
    Migration(1, "zid_vault", (
        "CREATE TABLE IF NOT EXISTS zid_vault ("
        " zid TEXT NOT NULL, skey TEXT NOT NULL,"
        " sealed TEXT NOT NULL, nonce TEXT NOT NULL,"
        " mac TEXT NOT NULL, created_at REAL NOT"
        " NULL, PRIMARY KEY (zid, skey))",
    )),
)


def _keystream(master_key, nonce, length):
    out = b""
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(
            (str(master_key) + "|" + str(nonce)
             + "|" + str(counter)).encode()).digest()
        counter += 1
    return out[:length]


def _seal(master_key, nonce, plaintext):
    pt = plaintext.encode("utf-8")
    ks = _keystream(master_key, nonce, len(pt))
    return bytes(a ^ b for a, b in
                 zip(pt, ks)).hex()


def _open_sealed(master_key, nonce, sealed_hex):
    ct = bytes.fromhex(sealed_hex)
    ks = _keystream(master_key, nonce, len(ct))
    return bytes(a ^ b for a, b in
                 zip(ct, ks)).decode("utf-8")


def _mac(master_key, zid, skey, sealed):
    return hmac.new(
        str(master_key).encode(),
        (str(zid) + "|" + str(skey) + "|"
         + str(sealed)).encode(),
        hashlib.sha256).hexdigest()


class ZidVaultEngine:
    """Bodega de secretos por ZID (ID-4)."""

    def __init__(self, db: Database, clock: Clock,
                 master_key=None):
        self._db = db
        self._clock = clock
        self._master = (str(master_key)
                        if master_key
                        else os.environ.get(
                            "ZYRA_ROOT_KEY", "")
                        or "zyra-default-dev-key")
        MigrationRunner(db, "zid.vault",
                        _MIGRATIONS).run(clock)

    def store_secret(self, *, zid, skey, plaintext):
        if not str(zid).strip() or \
                not str(skey).strip():
            raise ValueError(
                "zid y skey requeridos")
        if not str(plaintext).strip():
            raise ValueError(
                "plaintext requerido (regla 66)")
        nonce = os.urandom(16).hex()
        sealed = _seal(self._master, nonce,
                       str(plaintext))
        mac = _mac(self._master, str(zid),
                   str(skey), sealed)
        self._db.execute(
            "INSERT OR REPLACE INTO zid_vault (zid,"
            " skey, sealed, nonce, mac, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (str(zid), str(skey), sealed, nonce,
             mac, self._clock.now()))
        return {"zid": str(zid), "skey": str(skey)}

    def read_secret(self, *, zid, skey):
        row = self._db.query_one(
            "SELECT sealed, nonce, mac FROM zid_vault"
            " WHERE zid = ? AND skey = ?",
            (str(zid), str(skey)))
        if row is None:
            return {"found": False}
        mac = _mac(self._master, str(zid),
                   str(skey), str(row["sealed"]))
        if mac != str(row["mac"]):
            return {"found": True,
                    "tampered": True}
        pt = _open_sealed(self._master,
                          str(row["nonce"]),
                          str(row["sealed"]))
        return {"found": True, "plaintext": pt,
                "tampered": False}

    def delete_secret(self, *, zid, skey):
        row = self._db.query_one(
            "SELECT skey FROM zid_vault WHERE zid ="
            " ? AND skey = ?",
            (str(zid), str(skey)))
        if row is None:
            raise KeyError(skey)
        self._db.execute(
            "DELETE FROM zid_vault WHERE zid = ? AND"
            " skey = ?", (str(zid), str(skey)))
        return {"deleted": str(skey)}

    def keys_of(self, zid):
        rows = self._db.query_all(
            "SELECT skey FROM zid_vault WHERE zid ="
            " ? ORDER BY rowid", (str(zid),))
        return [str(r["skey"]) for r in rows]
