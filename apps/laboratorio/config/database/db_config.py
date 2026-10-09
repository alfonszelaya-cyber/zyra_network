"""Configuracion de base de datos de LABORATORIO."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DbConfig:
    """Parametros de conexion SQLite de produccion."""

    ruta_archivo: str = "data/laboratorio.db"
    timeout_segundos: float = 30.0
    journal_mode: str = "WAL"
    foreign_keys: bool = True

    @classmethod
    def cargar(cls) -> "DbConfig":
        """Carga desde entorno; la ruta debe existir como directorio padre."""
        return cls(
            ruta_archivo=os.environ.get("LAB_DB_RUTA", cls.ruta_archivo),
            timeout_segundos=float(os.environ.get("LAB_DB_TIMEOUT", cls.timeout_segundos)),
            journal_mode=os.environ.get("LAB_DB_JOURNAL", cls.journal_mode),
            foreign_keys=os.environ.get("LAB_DB_FK", "1") == "1",
        )
