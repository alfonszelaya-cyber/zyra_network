"""MPE durable store."""
from __future__ import annotations

from shared_engines.storage.database import (
    Database,
)
from shared_engines.storage.migrations import (
    Migration,
    MigrationRunner,
)

_MIGRATIONS = (
    Migration(
        1,
        "mpe",
        (
            "CREATE TABLE mpe_accounts ("
            " account_id TEXT PRIMARY KEY,"
            " zid TEXT,"
            " name TEXT NOT NULL,"
            " role TEXT NOT NULL,"
            " profession TEXT,"
            " verified INTEGER NOT NULL"
            " DEFAULT 0,"
            " created_at REAL NOT NULL)",
            "CREATE TABLE mpe_jobs ("
            " job_id TEXT PRIMARY KEY,"
            " company_account TEXT NOT NULL,"
            " title TEXT NOT NULL,"
            " profession TEXT NOT NULL,"
            " openings INTEGER NOT NULL,"
            " status TEXT NOT NULL"
            " DEFAULT 'open',"
            " created_at REAL NOT NULL)",
            "CREATE TABLE mpe_applications ("
            " application_id TEXT PRIMARY"
            " KEY,"
            " job_id TEXT NOT NULL,"
            " worker_account TEXT NOT NULL,"
            " status TEXT NOT NULL"
            " DEFAULT 'submitted',"
            " created_at REAL NOT NULL)",
        ),
    ),
)


class MpeStore:
    def __init__(
        self, db: Database, clock
    ) -> None:
        self._db = db
        self._clock = clock
        MigrationRunner(
            db, "mpe", _MIGRATIONS
        ).run(clock)

    def add_account(
        self,
        *,
        account_id: str,
        zid: str | None,
        name: str,
        role: str,
        profession: str | None,
    ) -> dict[str, object]:
        if role not in (
            "trabajador",
            "empresa",
        ):
            raise ValueError(
                f"unknown role: {role}"
            )
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO mpe_accounts"
                " (account_id, zid, name,"
                "  role, profession, verified,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, ?, 0, ?)",
                (
                    account_id,
                    zid,
                    name,
                    role,
                    profession,
                    now,
                ),
            )
        return self.get_account(account_id)

    def mark_verified(
        self, *, account_id: str
    ) -> None:
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE mpe_accounts SET"
                " verified = 1"
                " WHERE account_id = ?",
                (account_id,),
            )

    def get_account(
        self, account_id: str
    ) -> dict[str, object]:
        row = self._db.query_one(
            "SELECT * FROM mpe_accounts"
            " WHERE account_id = ?",
            (account_id,),
        )
        if row is None:
            raise LookupError(
                "unknown account:"
                f" {account_id}"
            )
        return self._account_row(row)

    def list_workers(
        self, *, profession: str | None = None
    ) -> tuple[dict[str, object], ...]:
        if profession is not None:
            rows = self._db.query_all(
                "SELECT * FROM mpe_accounts"
                " WHERE role = 'trabajador'"
                " AND profession = ?"
                " ORDER BY created_at",
                (profession,),
            )
        else:
            rows = self._db.query_all(
                "SELECT * FROM mpe_accounts"
                " WHERE role = 'trabajador'"
                " ORDER BY created_at"
            )
        return tuple(
            self._account_row(r)
            for r in rows
        )

    def list_companies(
        self,
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM mpe_accounts"
            " WHERE role = 'empresa'"
            " ORDER BY created_at"
        )
        return tuple(
            self._account_row(r)
            for r in rows
        )

    def post_job(
        self,
        *,
        job_id: str,
        company_account: str,
        title: str,
        profession: str,
        openings: int,
    ) -> dict[str, object]:
        company = self.get_account(
            company_account
        )
        if company.get("role") != "empresa":
            raise ValueError(
                "only companies can post"
                " jobs"
            )
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO mpe_jobs"
                " (job_id, company_account,"
                "  title, profession,"
                "  openings, status,"
                "  created_at)"
                " VALUES (?, ?, ?, ?, ?,"
                "  'open', ?)",
                (
                    job_id,
                    company_account,
                    title,
                    profession,
                    openings,
                    now,
                ),
            )
        row = self._db.query_one(
            "SELECT * FROM mpe_jobs"
            " WHERE job_id = ?",
            (job_id,),
        )
        assert row is not None
        return self._job_row(row)

    def list_jobs(
        self, *, profession: str | None = None
    ) -> tuple[dict[str, object], ...]:
        if profession is not None:
            rows = self._db.query_all(
                "SELECT * FROM mpe_jobs"
                " WHERE status = 'open'"
                " AND profession = ?"
                " ORDER BY created_at",
                (profession,),
            )
        else:
            rows = self._db.query_all(
                "SELECT * FROM mpe_jobs"
                " WHERE status = 'open'"
                " ORDER BY created_at"
            )
        return tuple(
            self._job_row(r)
            for r in rows
        )

    def apply(
        self,
        *,
        application_id: str,
        job_id: str,
        worker_account: str,
    ) -> dict[str, object]:
        worker = self.get_account(
            worker_account
        )
        if (
            worker.get("role")
            != "trabajador"
        ):
            raise ValueError(
                "only workers can apply"
            )
        row = self._db.query_one(
            "SELECT * FROM mpe_jobs"
            " WHERE job_id = ?"
            " AND status = 'open'",
            (job_id,),
        )
        if row is None:
            raise LookupError(
                "job not open:"
                f" {job_id}"
            )
        dup = self._db.query_one(
            "SELECT 1 FROM"
            " mpe_applications WHERE"
            " job_id = ? AND"
            " worker_account = ?",
            (job_id, worker_account),
        )
        if dup is not None:
            raise ValueError(
                "already applied"
            )
        now = self._clock.now()
        with self._db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO"
                " mpe_applications"
                " (application_id, job_id,"
                "  worker_account, status,"
                "  created_at)"
                " VALUES (?, ?, ?,"
                "  'submitted', ?)",
                (
                    application_id,
                    job_id,
                    worker_account,
                    now,
                ),
            )
        return {
            "application_id": (
                application_id
            ),
            "job_id": job_id,
            "worker": worker_account,
            "status": "submitted",
        }

    def applications_for(
        self, *, job_id: str
    ) -> tuple[dict[str, object], ...]:
        rows = self._db.query_all(
            "SELECT * FROM"
            " mpe_applications"
            " WHERE job_id = ?"
            " ORDER BY created_at",
            (job_id,),
        )
        return tuple(
            {
                "application_id": str(
                    r["application_id"]
                ),
                "job_id": str(
                    r["job_id"]
                ),
                "worker_account": str(
                    r["worker_account"]
                ),
                "status": str(
                    r["status"]
                ),
            }
            for r in rows
        )

    def summary(self) -> dict[str, object]:
        accounts = self._db.query_one(
            "SELECT COUNT(*) AS total,"
            " SUM(verified) AS verified"
            " FROM mpe_accounts"
        )
        roles = self._db.query_all(
            "SELECT role, COUNT(*) AS n"
            " FROM mpe_accounts"
            " GROUP BY role"
        )
        jobs = self._db.query_one(
            "SELECT COUNT(*) AS open_jobs"
            " FROM mpe_jobs"
            " WHERE status = 'open'"
        )
        apps = self._db.query_one(
            "SELECT COUNT(*) AS total"
            " FROM mpe_applications"
        )
        by_role = {
            str(r["role"]): int(r["n"])
            for r in roles
        }
        total = 0
        verified = 0
        if accounts is not None:
            total = int(
                accounts["total"]
            )
            if (
                accounts["verified"]
                is not None
            ):
                verified = int(
                    accounts["verified"]
                )
        return {
            "accounts_total": total,
            "accounts_verified": (
                verified
            ),
            "by_role": by_role,
            "open_jobs": int(
                jobs["open_jobs"]
            )
            if jobs is not None
            else 0,
            "applications_total": int(
                apps["total"]
            )
            if apps is not None
            else 0,
        }

    @staticmethod
    def _account_row(row) -> dict[str, object]:
        return {
            "account_id": str(
                row["account_id"]
            ),
            "zid": (
                str(row["zid"])
                if row["zid"] is not None
                else None
            ),
            "name": str(row["name"]),
            "role": str(row["role"]),
            "profession": (
                str(row["profession"])
                if row["profession"]
                is not None
                else None
            ),
            "verified": bool(
                int(row["verified"])
            ),
            "created_at": float(
                row["created_at"]
            ),
        }

    @staticmethod
    def _job_row(row) -> dict[str, object]:
        return {
            "job_id": str(row["job_id"]),
            "company_account": str(
                row["company_account"]
            ),
            "title": str(row["title"]),
            "profession": str(
                row["profession"]
            ),
            "openings": int(
                row["openings"]
            ),
            "status": str(row["status"]),
            "created_at": float(
                row["created_at"]
            ),
        }
