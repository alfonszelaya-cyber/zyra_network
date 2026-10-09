"""Store SQL de propuestas de optimizacion."""
import json


class OptimizationStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("OptimizationStore requiere conexion.")
        self._cx = conexion

    def insertar(self, propuesta) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_optimizations (id, proyecto_id, escenario_id, "
            "recomendaciones, parametros_optimizados, puntaje_actual, "
            "puntaje_proyectado, estado, aplicado_como, creado_en, actualizado_en) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (str(propuesta.id), str(propuesta.proyecto_id), str(propuesta.escenario_id),
             json.dumps(propuesta.recomendaciones, ensure_ascii=True),
             json.dumps(propuesta.parametros_optimizados, ensure_ascii=True),
             float(propuesta.puntaje_actual), float(propuesta.puntaje_proyectado),
             propuesta.estado, propuesta.aplicado_como,
             propuesta.creado_en.isoformat(), propuesta.actualizado_en.isoformat()),
        )

    def obtener(self, id_texto: str):
        fila = self._cx.consultar_uno("SELECT * FROM lab_optimizations WHERE id = ?", (id_texto,))
        return self._fila_a_entidad(fila) if fila else None

    def actualizar_aplicada(self, propuesta) -> bool:
        """Persiste el estado aplicada y el escenario creado."""
        cursor = self._cx.ejecutar(
            "UPDATE lab_optimizations SET estado = ?, aplicado_como = ?, "
            "actualizado_en = ? WHERE id = ?",
            (propuesta.estado, propuesta.aplicado_como,
             propuesta.actualizado_en.isoformat(), str(propuesta.id)),
        )
        return cursor.rowcount > 0

    def listar_por_proyectos(self, proyecto_ids: list, limite: int = 100) -> list:
        if not proyecto_ids:
            return []
        marcadores = ",".join("?" * len(proyecto_ids))
        filas = self._cx.consultar(
            "SELECT * FROM lab_optimizations WHERE proyecto_id IN (" + marcadores + ") "
            "ORDER BY creado_en DESC, id LIMIT ?",
            ([str(p) for p in proyecto_ids] + [int(limite)]),
        )
        return [self._fila_a_entidad(f) for f in filas]

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.optimization import PropuestaOptimizacion
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        prop = PropuestaOptimizacion(
            id=id_desde_texto("opt", f["id"]),
            proyecto_id=id_desde_texto("proy", f["proyecto_id"]),
            escenario_id=id_desde_texto("esc", f["escenario_id"]),
            recomendaciones=json.loads(f["recomendaciones"] or "[]"),
            parametros_optimizados=json.loads(f["parametros_optimizados"] or "{}"),
            puntaje_actual=float(f["puntaje_actual"]),
            puntaje_proyectado=float(f["puntaje_proyectado"]),
            estado=f["estado"],
            aplicado_como=f["aplicado_como"],
        )
        prop.creado_en = datetime.fromisoformat(f["creado_en"])
        prop.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return prop
