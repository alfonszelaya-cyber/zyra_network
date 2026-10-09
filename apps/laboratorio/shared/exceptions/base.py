"""Jerarquia base de errores de LABORATORIO."""


class LaboratorioError(Exception):
    """Error raiz de toda la aplicacion LABORATORIO."""

    codigo = "laboratorio_error"

    def __init__(self, mensaje: str, detalle: str = ""):
        self.mensaje = mensaje
        self.detalle = detalle
        super().__init__(mensaje)

    def to_dict(self) -> dict:
        """Representacion serializable del error."""
        datos = {"error": self.codigo, "mensaje": self.mensaje}
        if self.detalle:
            datos["detalle"] = self.detalle
        return datos
