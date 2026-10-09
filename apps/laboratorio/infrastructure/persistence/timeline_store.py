"""Store SQL de lineas de tiempo."""
import json


class TimelineStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("TimelineStore requiere conexion.")
        self._cx = conexion

    def insertar(self, linea) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_timelines (id, escena_id, duracion, fps, pistas, "
            "creado_en, actualizado_en) VALUES (?,?,?,?,?,?,?)",
            (str(linea.id), str(linea.escena_id), float(linea.duracion_s),
             int(linea.fps), json.dumps(linea.pistas, ensure_ascii=True),
             linea.creado_en.isoformat(), linea.actualizado_en.isoformat()),
        )

    def obtener_por_escena(self, escena_id: str):
        fila = self._cx.consultar_uno(
            "SELECT * FROM lab_timelines WHERE escena_id = ? ORDER BY creado_en DESC LIMIT 1",
            (escena_id,),
        )
        return self._fila_a_entidad(fila) if fila else None

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.timeline import LineaTiempo
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        linea = LineaTiempo(
            id=id_desde_texto("tln", f["id"]),
            escena_id=id_desde_texto("scn", f["escena_id"]),
            duracion_s=float(f["duracion"]),
            fps=int(f["fps"]),
            pistas=json.loads(f["pistas"] or "[]"),
        )
        linea.creado_en = datetime.fromisoformat(f["creado_en"])
        linea.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return linea
