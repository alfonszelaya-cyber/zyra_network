"""Capacidades con disponibilidad honesta (Ley 1)."""


class Capacidad:
    RENDER_SVG = "render_svg"
    RENDER_RASTER = "render_raster"
    RENDER_3D = "render_3d"
    PROFUNDIDAD = "profundidad"
    PROYECCION_WARP = "proyeccion_warp"
    HOLO_3D = "holo_3d"
    LIGHT_FIELD = "light_field"
    AR_VR = "ar_vr"
    TODAS = (RENDER_SVG, RENDER_RASTER, RENDER_3D, PROFUNDIDAD, PROYECCION_WARP, HOLO_3D, LIGHT_FIELD, AR_VR)


class DisponibilidadCapacidades:
    def __init__(self):
        self._estado = {
            c: {"disponible": False, "motivo": "capacidad aun no implementada"}
            for c in Capacidad.TODAS
        }

    def declarar(self, capacidad: str, disponible: bool, motivo: str = "") -> None:
        if capacidad not in Capacidad.TODAS:
            raise ValueError("Capacidad desconocida: " + repr(capacidad))
        if disponible and motivo:
            raise ValueError("Una capacidad disponible no requiere motivo.")
        if not disponible and not motivo:
            raise ValueError("Ley 1: capacidad no disponible exige motivo honesto.")
        self._estado[capacidad] = {"disponible": bool(disponible), "motivo": motivo}

    def estado(self) -> dict:
        return {c: dict(v) for c, v in self._estado.items()}

    def disponible(self, capacidad: str) -> bool:
        return self._estado[capacidad]["disponible"]
