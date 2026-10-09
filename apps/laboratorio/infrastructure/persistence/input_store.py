"""Store SQL de entradas de captura."""


class InputStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("InputStore requiere conexion.")
        self._cx = conexion

    def insertar(self, entrada) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_inputs (id, proyecto_id, tipo, titulo, contenido, hash, "
            "tamano, creado_en, actualizado_en) VALUES (?,?,?,?,?,?,?,?,?)",
            (str(entrada.id), str(entrada.proyecto_id), entrada.tipo.value,
             entrada.titulo, entrada.contenido, entrada.hash_sha256,
             int(entrada.tamano_bytes), entrada.creado_en.isoformat(),
             entrada.actualizado_en.isoformat()),
        )

    def obtener(self, id_texto: str):
        fila = self._cx.consultar_uno("SELECT * FROM lab_inputs WHERE id = ?", (id_texto,))
        return self._fila_a_entidad(fila) if fila else None

    def listar_por_proyecto(self, proyecto_id: str, limite: int = 50, offset: int = 0) -> list:
        filas = self._cx.consultar(
            "SELECT * FROM lab_inputs WHERE proyecto_id = ? ORDER BY creado_en, id LIMIT ? OFFSET ?",
            (proyecto_id, int(limite), int(offset)),
        )
        return [self._fila_a_entidad(f) for f in filas]

    def listar_por_proyectos(self, proyecto_ids: list, limite: int = 100) -> list:
        if not proyecto_ids:
            return []
        marcadores = ",".join("?" * len(proyecto_ids))
        filas = self._cx.consultar(
            "SELECT * FROM lab_inputs WHERE proyecto_id IN (" + marcadores + ") "
            "ORDER BY creado_en DESC, id LIMIT ?",
            ([str(p) for p in proyecto_ids] + [int(limite)]),
        )
        return [self._fila_a_entidad(f) for f in filas]

    def contar_por_proyecto(self, proyecto_id: str) -> int:
        fila = self._cx.consultar_uno(
            "SELECT COUNT(*) AS n FROM lab_inputs WHERE proyecto_id = ?", (proyecto_id,)
        )
        return int(fila["n"])

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.input_capture import EntradaCaptura
        from apps.laboratorio.shared.enums.input_kind import InputKind
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        entrada = EntradaCaptura(
            id=id_desde_texto("inp", f["id"]),
            proyecto_id=id_desde_texto("proy", f["proyecto_id"]),
            tipo=InputKind(f["tipo"]),
            titulo=f["titulo"],
            contenido=f["contenido"],
            hash_sha256=f["hash"],
            tamano_bytes=int(f["tamano"]),
        )
        entrada.creado_en = datetime.fromisoformat(f["creado_en"])
        entrada.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return entrada
