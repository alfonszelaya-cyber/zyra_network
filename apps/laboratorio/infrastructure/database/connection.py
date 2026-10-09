"""Conexion SQLite de produccion: WAL, claves foraneas y bloqueo."""
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path


class ConexionBD:
    """Unica puerta de acceso a la base de LABORATORIO."""

    def __init__(self, ruta: str, timeout_segundos: float = 30.0, journal_mode: str = "WAL"):
        if not ruta or not str(ruta).strip():
            raise ValueError("ConexionBD requiere ruta.")
        self._ruta = str(ruta)
        self._timeout = float(timeout_segundos)
        self._bloqueo = threading.RLock()
        if self._ruta != ":memory:":
            Path(self._ruta).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            self._ruta, timeout=self._timeout, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        if self._ruta != ":memory:":
            self._conn.execute("PRAGMA journal_mode=" + journal_mode)
        self._conn.execute("PRAGMA foreign_keys=ON")

    @property
    def crudo(self) -> sqlite3.Connection:
        """Conexion cruda para casos avanzados controlados."""
        return self._conn

    def ejecutar(self, sql: str, parametros=()):
        """Ejecuta escritura con commit y devuelve el cursor."""
        if not sql or not sql.strip():
            raise ValueError("SQL vacio.")
        with self._bloqueo:
            cursor = self._conn.execute(sql, parametros)
            self._conn.commit()
            return cursor

    def consultar(self, sql: str, parametros=()) -> list:
        """Ejecuta lectura y devuelve todas las filas."""
        if not sql or not sql.strip():
            raise ValueError("SQL vacio.")
        with self._bloqueo:
            return self._conn.execute(sql, parametros).fetchall()

    def consultar_uno(self, sql: str, parametros=()):
        """Ejecuta lectura y devuelve la primera fila o None."""
        with self._bloqueo:
            return self._conn.execute(sql, parametros).fetchone()

    @contextmanager
    def transaccion(self):
        """Bloque atomico: commit o rollback completo."""
        with self._bloqueo:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def cerrar(self) -> None:
        """Cierra la conexion de forma ordenada."""
        with self._bloqueo:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, tipo_exc, valor_exc, traza):
        self.cerrar()
        return False
