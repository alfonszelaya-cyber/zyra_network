"""Store SQL de programas de luz."""
import json


class LightingStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("LightingStore requiere conexion.")
        self._cx = conexion

    def insertar(self, programa) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_lightprograms (id, escena_id, pasos, ambientar, "
            "creado_en, actualizado_en) VALUES (?,?,?,?,?,?)",
            (str(programa.id), str(programa.escena_id),
             json.dumps(programa.pasos, ensure_ascii=True),
             1 if programa.ambientar_fondo else 0,
             programa.creado_en.isoformat(), programa.actualizado_en.isoformat()),
        )

    def obtener_por_escena(self, escena_id: str):
        fila = self._cx.consultar_uno(
            "SELECT * FROM lab_lightprograms WHERE escena_id = ? ORDER BY creado_en DESC LIMIT 1",
            (escena_id,),
        )
        return self._fila_a_entidad(fila) if fila else None

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.lighting import ProgramaLuz
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        programa = ProgramaLuz(
            id=id_desde_texto("luz", f["id"]),
            escena_id=id_desde_texto("scn", f["escena_id"]),
            pasos=json.loads(f["pasos"] or "[]"),
            ambientar_fondo=bool(f["ambientar"]),
        )
        programa.creado_en = datetime.fromisoformat(f["creado_en"])
        programa.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return programa
