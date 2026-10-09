"""Store SQL de comparaciones."""
import json


class ComparisonStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("ComparisonStore requiere conexion.")
        self._cx = conexion

    def insertar(self, comparacion) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_comparisons (id, proyecto_id, participantes, ganador, "
            "brecha, detalle, informe, creado_en, actualizado_en) VALUES (?,?,?,?,?,?,?,?,?)",
            (str(comparacion.id), str(comparacion.proyecto_id),
             json.dumps(comparacion.participantes, ensure_ascii=True),
             comparacion.ganador, float(comparacion.brecha),
             json.dumps(comparacion.detalle, ensure_ascii=True),
             comparacion.informe,
             comparacion.creado_en.isoformat(), comparacion.actualizado_en.isoformat()),
        )

    def obtener(self, id_texto: str):
        fila = self._cx.consultar_uno("SELECT * FROM lab_comparisons WHERE id = ?", (id_texto,))
        return self._fila_a_entidad(fila) if fila else None

    def listar_por_proyectos(self, proyecto_ids: list, limite: int = 100) -> list:
        if not proyecto_ids:
            return []
        marcadores = ",".join("?" * len(proyecto_ids))
        filas = self._cx.consultar(
            "SELECT * FROM lab_comparisons WHERE proyecto_id IN (" + marcadores + ") "
            "ORDER BY creado_en DESC, id LIMIT ?",
            ([str(p) for p in proyecto_ids] + [int(limite)]),
        )
        return [self._fila_a_entidad(f) for f in filas]

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.comparison import Comparacion
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        cmp_obj = Comparacion(
            id=id_desde_texto("cmp", f["id"]),
            proyecto_id=id_desde_texto("proy", f["proyecto_id"]),
            participantes=json.loads(f["participantes"] or "[]"),
            ganador=f["ganador"],
            brecha=float(f["brecha"]),
            detalle=json.loads(f["detalle"] or "{}"),
            informe=f["informe"],
        )
        cmp_obj.creado_en = datetime.fromisoformat(f["creado_en"])
        cmp_obj.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return cmp_obj
