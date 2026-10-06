
"""Library Engine - biblioteca escolar (SM7)."""
from __future__ import annotations
from decimal import (Decimal as _D,
                     ROUND_HALF_UP as _UP)
from typing import List, Optional
import uuid
from shared_engines.common.clocks import Clock
from shared_engines.storage.database import (
    Database)
from shared_engines.storage.migrations import (
    Migration, MigrationRunner)

_Q = "0.01"

_MIGRATIONS = (
    Migration(1, "sm_library_books", (
        "CREATE TABLE IF NOT EXISTS sm_library_books (book_id TEXT PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL DEFAULT '', copies_total INTEGER NOT NULL DEFAULT 1, copies_available INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL)",
    )),
    Migration(2, "sm_library_loans", (
        "CREATE TABLE IF NOT EXISTS sm_library_loans (loan_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, student_id TEXT NOT NULL, returned INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, returned_at REAL)",
    )),
)

class LibraryEngine:
    """Biblioteca escolar (persistente)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock
        MigrationRunner(db, "sm.library",
                        _MIGRATIONS).run(clock)

    def add_book(self, *, title, author="",
                 copies=1) -> dict:
        if not str(title).strip():
            raise ValueError("title requerido")
        if int(copies) <= 0:
            raise ValueError("copies > 0")
        bid = "SMBOOK-" + str(uuid.uuid4())
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO sm_library_books"
                " (book_id, title, author,"
                " copies_total,"
                " copies_available, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (bid, str(title).strip(),
                 str(author), int(copies),
                 int(copies), now))
        return self.get_book(bid)

    def get_book(self, book_id
                 ) -> Optional[dict]:
        row = self._db.query_one(
            "SELECT * FROM sm_library_books WHERE"
            " book_id = ?", (book_id,))
        if not row:
            return None
        return {"book_id": str(row["book_id"]),
                "title": str(row["title"]),
                "author": str(row["author"]),
                "copies_total":
                    int(row["copies_total"]),
                "copies_available":
                    int(row["copies_available"])}

    def checkout(self, *, book_id,
                 student_id) -> dict:
        with self._db.transaction() as cursor:
            row = cursor.execute(
                "SELECT copies_available FROM"
                " sm_library_books WHERE book_id"
                " = ?", (book_id,)).fetchone()
            if row is None:
                raise KeyError(book_id)
            if int(row["copies_available"]) <= 0:
                raise ValueError(
                    "sin copias disponibles")
            cursor.execute(
                "UPDATE sm_library_books SET"
                " copies_available ="
                " copies_available - 1 WHERE"
                " book_id = ?", (book_id,))
            lid = "SMLOAN-" + str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO sm_library_loans"
                " (loan_id, book_id, student_id,"
                " returned, created_at)"
                " VALUES (?, ?, ?, 0, ?)",
                (lid, book_id, student_id,
                 self._clock.now()))
        return {"loan_id": lid,
                "book_id": book_id,
                "student_id": student_id,
                "status": "CHECKED_OUT"}

    def return_book(self, loan_id) -> dict:
        row = self._db.query_one(
            "SELECT * FROM sm_library_loans WHERE"
            " loan_id = ? AND returned = 0",
            (loan_id,))
        if not row:
            raise KeyError(loan_id)
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE sm_library_loans SET"
                " returned = 1, returned_at = ?"
                " WHERE loan_id = ?",
                (self._clock.now(), loan_id))
            cursor.execute(
                "UPDATE sm_library_books SET"
                " copies_available ="
                " copies_available + 1 WHERE"
                " book_id = ?",
                (str(row["book_id"]),))
        return {"loan_id": str(loan_id),
                "status": "RETURNED"}

    def search(self, term) -> List[dict]:
        rows = self._db.query_all(
            "SELECT * FROM sm_library_books")
        t = str(term).lower()
        out = []
        for r in rows:
            if (t in str(r["title"]).lower()
                    or t in str(
                        r["author"]).lower()):
                out.append(self.get_book(
                    str(r["book_id"])))
        return out
