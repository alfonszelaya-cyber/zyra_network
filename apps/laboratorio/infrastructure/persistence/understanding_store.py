"""Store SQL de comprensiones de entradas."""
import json


class UnderstandingStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("UnderstandingStore requiere conexion.")
        self._cx = conexion

    def insertar(self, comprension) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_understandings (id, entrada_id, proyecto_id, resumen, "
            "hallazgos, entidades, dominio, confianza, creado_en, actualizado_en) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (str(comprension.id), str(comprension.entrada_id), str(comprension.proyecto_id),
             comprension.resumen, json.dumps(comprension.hallazgos, ensure_ascii=True),
             json.dumps(comprension.entidades, ensure_ascii=True),
             comprension.dominio, float(comprension.confianza),
             comprension.creado_en.isoformat(), comprension.actualizado_en.isoformat()),
        )

    def obtener(self, id_texto: str):
        fila = self._cx.consultar_uno("SELECT * FROM lab_understandings WHERE id = ?", (id_texto,))
        return self._fila_a_entidad(fila) if fila else None

    def obtener_por_entrada(self, entrada_id: str):
        fila = self._cx.consultar_uno(
            "SELECT * FROM lab_understandings WHERE entrada_id = ? ORDER BY creado_en DESC LIMIT 1",
            (entrada_id,),
        )
        return self._fila_a_entidad(fila) if fila else None

    def listar_por_proyectos(self, proyecto_ids: list, limite: int = 100) -> list:
        if not proyecto_ids:
            return []
        marcadores = ",".join("?" * len(proyecto_ids))
        filas = self._cx.consultar(
            "SELECT * FROM lab_understandings WHERE proyecto_id IN (" + marcadores + ") "
            "ORDER BY creado_en DESC, id LIMIT ?",
            ([str(p) for p in proyecto_ids] + [int(limite)]),
        )
        return [self._fila_a_entidad(f) for f in filas]

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.understanding import Comprension
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        comp = Comprension(
            id=id_desde_texto("und", f["id"]),
            entrada_id=id_desde_texto("inp", f["entrada_id"]),
            proyecto_id=id_desde_texto("proy", f["proyecto_id"]),
            resumen=f["resumen"],
            hallazgos=json.loads(f["hallazgos"] or "[]"),
            entidades=json.loads(f["entidades"] or "{}"),
            dominio=f["dominio"],
            confianza=float(f["confianza"]),
        )
        comp.creado_en = datetime.fromisoformat(f["creado_en"])
        comp.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return comp
