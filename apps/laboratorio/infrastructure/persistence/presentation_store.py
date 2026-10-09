"""Store SQL de presentaciones."""
import json


class PresentationStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("PresentationStore requiere conexion.")
        self._cx = conexion

    def insertar(self, presentacion) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_presentations (id, proyecto_id, titulo, pasos, sellada, "
            "sello_zid, duracion_total, creado_en, actualizado_en) VALUES (?,?,?,?,?,?,?,?,?)",
            (str(presentacion.id), str(presentacion.proyecto_id), presentacion.titulo,
             json.dumps(presentacion.pasos, ensure_ascii=True),
             1 if presentacion.sellada else 0, presentacion.sello_zid,
             float(presentacion.duracion_total),
             presentacion.creado_en.isoformat(), presentacion.actualizado_en.isoformat()),
        )

    def actualizar_sello(self, presentacion) -> bool:
        """Persiste el sellado de la presentacion."""
        cursor = self._cx.ejecutar(
            "UPDATE lab_presentations SET sellada = ?, sello_zid = ?, "
            "actualizado_en = ? WHERE id = ?",
            (1 if presentacion.sellada else 0, presentacion.sello_zid,
             presentacion.actualizado_en.isoformat(), str(presentacion.id)),
        )
        return cursor.rowcount > 0

    def obtener(self, id_texto: str):
        fila = self._cx.consultar_uno(
            "SELECT * FROM lab_presentations WHERE id = ?", (id_texto,)
        )
        return self._fila_a_entidad(fila) if fila else None

    def listar_por_proyectos(self, proyecto_ids: list, limite: int = 100) -> list:
        if not proyecto_ids:
            return []
        marcadores = ",".join("?" * len(proyecto_ids))
        filas = self._cx.consultar(
            "SELECT * FROM lab_presentations WHERE proyecto_id IN (" + marcadores + ") "
            "ORDER BY creado_en DESC, id LIMIT ?",
            ([str(p) for p in proyecto_ids] + [int(limite)]),
        )
        return [self._fila_a_entidad(f) for f in filas]

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.presentation import Presentacion
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        prs = Presentacion(
            id=id_desde_texto("prs", f["id"]),
            proyecto_id=id_desde_texto("proy", f["proyecto_id"]),
            titulo=f["titulo"],
            pasos=json.loads(f["pasos"] or "[]"),
            sellada=bool(f["sellada"]),
            sello_zid=f["sello_zid"],
            duracion_total=float(f["duracion_total"]),
        )
        prs.creado_en = datetime.fromisoformat(f["creado_en"])
        prs.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return prs
