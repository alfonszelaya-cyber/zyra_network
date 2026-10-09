"""Store SQL de simulaciones de evolucion."""
import json


class SimulationStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("SimulationStore requiere conexion.")
        self._cx = conexion

    def insertar(self, sim) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_simulations (id, proyecto_id, escenario_id, horizonte, "
            "crecimiento, serie, metricas, creado_en, actualizado_en) VALUES (?,?,?,?,?,?,?,?,?)",
            (str(sim.id), str(sim.proyecto_id), str(sim.escenario_id),
             int(sim.horizonte_anios), float(sim.crecimiento_pct),
             json.dumps(sim.serie, ensure_ascii=True),
             json.dumps(sim.metricas, ensure_ascii=True),
             sim.creado_en.isoformat(), sim.actualizado_en.isoformat()),
        )

    def obtener(self, id_texto: str):
        fila = self._cx.consultar_uno("SELECT * FROM lab_simulations WHERE id = ?", (id_texto,))
        return self._fila_a_entidad(fila) if fila else None

    def listar_por_proyectos(self, proyecto_ids: list, limite: int = 100) -> list:
        if not proyecto_ids:
            return []
        marcadores = ",".join("?" * len(proyecto_ids))
        filas = self._cx.consultar(
            "SELECT * FROM lab_simulations WHERE proyecto_id IN (" + marcadores + ") "
            "ORDER BY creado_en DESC, id LIMIT ?",
            ([str(p) for p in proyecto_ids] + [int(limite)]),
        )
        return [self._fila_a_entidad(f) for f in filas]

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.simulation import SimulacionEvolucion
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        sim = SimulacionEvolucion(
            id=id_desde_texto("sim", f["id"]),
            proyecto_id=id_desde_texto("proy", f["proyecto_id"]),
            escenario_id=id_desde_texto("esc", f["escenario_id"]),
            horizonte_anios=int(f["horizonte"]),
            crecimiento_pct=float(f["crecimiento"]),
            serie=json.loads(f["serie"] or "[]"),
            metricas=json.loads(f["metricas"] or "{}"),
        )
        sim.creado_en = datetime.fromisoformat(f["creado_en"])
        sim.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return sim
