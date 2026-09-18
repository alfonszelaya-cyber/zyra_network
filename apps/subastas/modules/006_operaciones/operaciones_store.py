"""ZYRA MARKET - Modulo Operaciones (completo).

Estados extendidos de orden + tareas operativas."""
from __future__ import annotations

import threading
import time
import uuid


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _nid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:10]


EXTRA_STATES = ("preparando", "lista", "cancelada", "cerrada")


class OperacionesStore:
    def __init__(self, db, clock) -> None:
        self._db = db
        self._clock = clock
        self._lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_order_ops ("
            " order_id TEXT PRIMARY KEY,"
            " extra_state TEXT NOT NULL,"
            " updated_by TEXT NOT NULL,"
            " updated_at TEXT NOT NULL)"
        )
        self._run(
            "CREATE TABLE IF NOT EXISTS sbs_op_tasks ("
            " task_id TEXT PRIMARY KEY,"
            " order_id TEXT NOT NULL,"
            " task TEXT NOT NULL,"
            " done INTEGER NOT NULL DEFAULT 0,"
            " created_by TEXT NOT NULL,"
            " created_at TEXT NOT NULL)"
        )

    def _run(self, sql, params=()):
        if not params:
            self._db.execute(sql)
            return
        try:
            self._db.execute(sql, params)
            return
        except TypeError:
            self._db.execute(self._inline(sql, params))

    @staticmethod
    def _inline(sql, params):
        parts = sql.split("?")
        if len(parts) != len(params) + 1:
            return sql
        assembled = parts[0]
        for i, v in enumerate(params):
            assembled += OperacionesStore._literal(v)
            assembled += parts[i + 1]
        return assembled

    @staticmethod
    def _literal(value):
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return repr(value)
        return "'" + str(value).replace("'", "''") + "'"

    def _rows(self, sql):
        for name in ("query", "fetchall", "fetch_all", "fetch", "select"):
            fn = getattr(self._db, name, None)
            if callable(fn):
                try:
                    rows = fn(sql)
                    if rows is not None:
                        return list(rows)
                except Exception:
                    continue
        try:
            cur = self._db.execute(sql)
        except Exception:
            return []
        if cur is None:
            return []
        try:
            return list(cur.fetchall())
        except Exception:
            return []

    @staticmethod
    def _field(row, key, index):
        if isinstance(row, dict):
            return row.get(key)
        try:
            return row[index]
        except Exception:
            return None

    @staticmethod
    def _req(value, name):
        text = str(value or "").strip()
        if not text:
            raise ValueError("%s es obligatorio" % name)
        return text

    def set_state(self, order_id, *, account, state):
        order_id = self._req(order_id, "order_id")
        self._req(account, "account")
        state = str(state or "").strip()
        if state not in EXTRA_STATES:
            raise ValueError("estado debe ser: %s" % ", ".join(EXTRA_STATES))
        with self._lock:
            self._run(
                "INSERT INTO sbs_order_ops (order_id, extra_state,"
                " updated_by, updated_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(order_id) DO UPDATE SET"
                " extra_state = excluded.extra_state,"
                " updated_by = excluded.updated_by,"
                " updated_at = excluded.updated_at",
                (order_id, state, account, _now()),
            )
            return {"order_id": order_id, "extra_state": state}

    def get_state(self, order_id):
        order_id = self._req(order_id, "order_id")
        rows = self._rows(
            "SELECT extra_state, updated_by, updated_at"
            " FROM sbs_order_ops WHERE order_id = "
            + self._literal(order_id)
        )
        if not rows:
            return None
        return {
            "order_id": order_id,
            "extra_state": self._field(rows[0], "a", 0),
            "updated_by": self._field(rows[0], "b", 1),
            "updated_at": self._field(rows[0], "c", 2),
        }

    def add_task(self, order_id, *, account, task):
        order_id = self._req(order_id, "order_id")
        self._req(account, "account")
        task = self._req(task, "task")
        with self._lock:
            task_id = _nid("TSK-")
            self._run(
                "INSERT INTO sbs_op_tasks (task_id, order_id, task,"
                " done, created_by, created_at)"
                " VALUES (?, ?, ?, 0, ?, ?)",
                (task_id, order_id, task, account, _now()),
            )
            return {"task_id": task_id, "task": task, "done": False}

    def done_task(self, task_id, *, account):
        task_id = self._req(task_id, "task_id")
        self._req(account, "account")
        with self._lock:
            self._run(
                "UPDATE sbs_op_tasks SET done = 1"
                " WHERE task_id = " + self._literal(task_id)
            )
            return {"task_id": task_id, "done": True}

    def list_tasks(self, order_id):
        order_id = self._req(order_id, "order_id")
        out = []
        for row in self._rows(
            "SELECT task_id, task, done, created_by, created_at"
            " FROM sbs_op_tasks WHERE order_id = "
            + self._literal(order_id)
            + " ORDER BY created_at ASC"
        ):
            out.append({
                "task_id": self._field(row, "a", 0),
                "task": self._field(row, "b", 1),
                "done": bool(self._field(row, "c", 2)),
            })
        return out


def market_ops_api(self) -> None:
    try:
        user = self._sess_user()
        if user is None:
            self._send_json(401, {"ok": False, "error": "sesion requerida"})
            return
        account = user["username"]
        doc = self._read_json()
        if doc is None:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return
        action = str(doc.get("action", ""))
        if action == "set_state":
            r = self.ops.set_state(
                str(doc.get("order_id", "")),
                account=account, state=str(doc.get("state", "")))
            self._send_json(200, {"ok": True, "data": r})
            return
        if action == "get_state":
            r = self.ops.get_state(str(doc.get("order_id", "")))
            self._send_json(200, {"ok": True, "data": r})
            return
        if action == "add_task":
            r = self.ops.add_task(
                str(doc.get("order_id", "")), account=account,
                task=str(doc.get("task", "")))
            self._send_json(201, {"ok": True, "data": r})
            return
        if action == "done_task":
            r = self.ops.done_task(
                str(doc.get("task_id", "")), account=account)
            self._send_json(200, {"ok": True, "data": r})
            return
        if action == "list_tasks":
            r = self.ops.list_tasks(str(doc.get("order_id", "")))
            self._send_json(200, {"ok": True, "data": {"tasks": r}})
            return
        self._send_json(
            400, {"ok": False, "error": "accion desconocida"}
        )
    except Exception:
        import traceback as _tb
        self._send_json(500, {
            "ok": False, "error": "server error",
            "trace": _tb.format_exc(),
        })
