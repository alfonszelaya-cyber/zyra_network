"""Store SQL de zonas de interaccion."""
class InteractionStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("InteractionStore requiere conexion.")
        self._cx = conexion

    def insertar(self, zona) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_interactions (id, escena_id, x, y, w, h, accion, titulo, "
            "creado_en, actualizado_en) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (str(zona.id), str(zona.escena_id), float(zona.x), float(zona.y),
             float(zona.w), float(zona.h), zona.accion, zona.titulo,
             zona.creado_en.isoformat(), zona.actualizado_en.isoformat()),
        )

    def listar_por_escena(self, escena_id: str) -> list:
        filas = self._cx.consultar(
            "SELECT * FROM lab_interactions WHERE escena_id = ? ORDER BY creado_en, id",
            (escena_id,),
        )
        return [self._fila_a_entidad(f) for f in filas]

    def contar_por_escena(self, escena_id: str) -> int:
        fila = self._cx.consultar_uno(
            "SELECT COUNT(*) AS n FROM lab_interactions WHERE escena_id = ?",
            (escena_id,),
        )
        return int(fila["n"])

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.interaction import ZonaInteraccion
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        zona = ZonaInteraccion(
            id=id_desde_texto("int", f["id"]),
            escena_id=id_desde_texto("scn", f["escena_id"]),
            x=float(f["x"]), y=float(f["y"]),
            w=float(f["w"]), h=float(f["h"]),
            accion=f["accion"], titulo=f["titulo"],
        )
        zona.creado_en = datetime.fromisoformat(f["creado_en"])
        zona.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return zona
