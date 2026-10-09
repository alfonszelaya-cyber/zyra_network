"""Outbox con reintentos: ninguna entrega a la red se pierde."""
from apps.laboratorio.shared.helpers.json_helpers import (
    a_json,
    intentar_desde_json,
)
from apps.laboratorio.shared.models.base import ahora_utc

ESTADO_PENDIENTE = "pendiente"
ESTADO_ENVIADO = "enviado"
ESTADO_ERROR = "error"


class Outbox:
    def __init__(self, conexion, reintentos_max: int = 3):
        if conexion is None:
            raise ValueError("Outbox requiere conexion.")
        if reintentos_max < 1:
            raise ValueError("reintentos_max debe ser mayor o igual a 1.")
        self._cx = conexion
        self._max = int(reintentos_max)

    def encolar(self, evento: str, destino: str, carga: dict) -> int:
        if not evento or not destino:
            raise ValueError("encolar requiere evento y destino.")
        cursor = self._cx.ejecutar(
            "INSERT INTO lab_outbox (evento, destino, carga, intentos, estado, "
            "ultimo_error, creado_en) VALUES (?, ?, ?, 0, ?, '', ?)",
            (evento, destino, a_json(dict(carga or {})), ESTADO_PENDIENTE, ahora_utc().isoformat()),
        )
        return int(cursor.lastrowid)

    def pendientes(self, limite: int = 50) -> list:
        filas = self._cx.consultar(
            "SELECT * FROM lab_outbox WHERE estado = ? ORDER BY id LIMIT ?",
            (ESTADO_PENDIENTE, int(limite)),
        )
        return [self._fila_a_dict(f) for f in filas]

    def procesar(self, entregador) -> dict:
        if not callable(entregador):
            raise ValueError("entregador debe ser callable.")
        resumen = {"procesados": 0, "enviados": 0, "reprogramados": 0, "abandonados": 0}
        for fila in self._cx.consultar(
            "SELECT * FROM lab_outbox WHERE estado = ? ORDER BY id",
            (ESTADO_PENDIENTE,),
        ):
            resumen["procesados"] += 1
            try:
                entregador(fila["destino"], intentar_desde_json(fila["carga"]))
                self._cx.ejecutar(
                    "UPDATE lab_outbox SET estado = ?, enviado_en = ? WHERE id = ?",
                    (ESTADO_ENVIADO, ahora_utc().isoformat(), fila["id"]),
                )
                resumen["enviados"] += 1
            except Exception as exc:
                intentos = int(fila["intentos"]) + 1
                error = type(exc).__name__ + ": " + str(exc)[:500]
                if intentos >= self._max:
                    self._cx.ejecutar(
                        "UPDATE lab_outbox SET intentos = ?, estado = ?, "
                        "ultimo_error = ? WHERE id = ?",
                        (intentos, ESTADO_ERROR, error, fila["id"]),
                    )
                    resumen["abandonados"] += 1
                else:
                    self._cx.ejecutar(
                        "UPDATE lab_outbox SET intentos = ?, ultimo_error = ? WHERE id = ?",
                        (intentos, error, fila["id"]),
                    )
                    resumen["reprogramados"] += 1
        return resumen

    def estadisticas(self) -> dict:
        filas = self._cx.consultar(
            "SELECT estado, COUNT(*) AS n FROM lab_outbox GROUP BY estado"
        )
        base = {ESTADO_PENDIENTE: 0, ESTADO_ENVIADO: 0, ESTADO_ERROR: 0}
        for f in filas:
            base[f["estado"]] = int(f["n"])
        return base

    @staticmethod
    def _fila_a_dict(f) -> dict:
        return {
            "id": int(f["id"]),
            "evento": f["evento"],
            "destino": f["destino"],
            "carga": intentar_desde_json(f["carga"]),
            "intentos": int(f["intentos"]),
            "estado": f["estado"],
            "ultimo_error": f["ultimo_error"],
            "creado_en": f["creado_en"],
            "enviado_en": f["enviado_en"],
        }
