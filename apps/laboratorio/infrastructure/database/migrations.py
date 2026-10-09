"""Migraciones versionadas del esquema de LABORATORIO."""
import sqlite3
from datetime import datetime, timezone

from apps.laboratorio.infrastructure.database.tables import ESQUEMA_V1

MIGRACIONES = ((1, ESQUEMA_V1),)


def version_actual(conexion) -> int:
    """Version vigente; 0 si el esquema aun no existe."""
    try:
        fila = conexion.consultar_uno(
            "SELECT MAX(version) AS v FROM lab_schema_version"
        )
    except sqlite3.OperationalError:
        return 0
    if fila is None or fila["v"] is None:
        return 0
    return int(fila["v"])


def aplicar_migraciones(conexion) -> int:
    """Aplica en orden las migraciones pendientes; devuelve cuantas."""
    aplicadas = 0
    for version, sql in MIGRACIONES:
        if version <= version_actual(conexion):
            continue
        marca = datetime.now(timezone.utc).isoformat()
        conexion.crudo.executescript(sql)
        conexion.crudo.execute(
            "INSERT INTO lab_schema_version (version, aplicada_en) VALUES (?, ?)",
            (version, marca),
        )
        conexion.crudo.commit()
        aplicadas += 1
    return aplicadas
