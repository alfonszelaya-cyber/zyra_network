"""Casos de uso de salidas: registrar destinos y probar frames."""
from apps.laboratorio.domain.display import DestinoSalida
from apps.laboratorio.infrastructure.providers.test_pattern import patron_prueba
from apps.laboratorio.shared.enums.display_kind import DisplayKind
from apps.laboratorio.shared.models.identifiers import nuevo_id


class CasoRegistrarSalida:
    def __init__(self, repo_salidas, auditoria):
        self._repo = repo_salidas
        self._auditoria = auditoria

    def ejecutar(self, identidad, datos: dict) -> dict:
        if not isinstance(datos, dict):
            raise ValueError("Cuerpo invalido.")
        nombre = str(datos.get("nombre", "")).strip()
        if not nombre:
            raise ValueError("La salida requiere nombre.")
        destino = DestinoSalida(
            id=nuevo_id("dsp"),
            propietario_zid=identidad.zid,
            nombre=nombre[:200],
            kind=DisplayKind.validar(str(datos.get("kind", "pantalla"))),
        )
        self._repo.agregar(destino)
        self._auditoria.registrar(
            identidad, "salida.registrar", str(destino.id), "exito",
            {"kind": destino.kind.value, "disponible": destino.disponible},
        )
        return {"salida": self._a_dict(destino)}

    @staticmethod
    def _a_dict(destino) -> dict:
        return {
            "id": str(destino.id),
            "nombre": destino.nombre,
            "kind": destino.kind.value,
            "disponible": destino.disponible,
            "motivo": destino.motivo_estado,
            "creado_en": destino.creado_en.isoformat(),
        }


class CasoProbarSalida:
    def __init__(self, repo_salidas, auditoria):
        self._repo = repo_salidas
        self._auditoria = auditoria

    def ejecutar(self, identidad, salida_id: str) -> tuple:
        destino = self._repo.obtener_exigir_de(identidad.zid, salida_id)
        if not destino.disponible:
            raise ValueError(
                "La salida " + destino.kind.value + " no puede presentar: "
                + destino.motivo_estado
            )
        frame = patron_prueba(320, 180)
        self._auditoria.registrar(
            identidad, "salida.probar", str(destino.id), "exito",
            {"kind": destino.kind.value, "frame": "320x180"},
        )
        return 200, frame, {
            "Content-Type": "image/png",
            "Content-Disposition": "inline; filename=test_" + str(destino.id) + ".png",
            "X-Test-Destino": destino.kind.value,
        }
