"""Politica de calidad: preset oficial por nivel de la escalera."""
from apps.laboratorio.shared.enums.render_quality import RenderQuality
from apps.laboratorio.shared.value_objects.resolution import Resolucion


class PoliticaCalidad:
    """Dueña unica de los presets de render de LABORATORIO."""

    PRESETS = {
        RenderQuality.BORRADOR: {"ancho": 640, "alto": 360, "muestras": 1, "profundidad": False},
        RenderQuality.ALTA: {"ancho": 1920, "alto": 1080, "muestras": 4, "profundidad": True},
        RenderQuality.TRES_D: {"ancho": 1920, "alto": 1080, "muestras": 8, "profundidad": True},
        RenderQuality.FOTORREAL: {"ancho": 3840, "alto": 2160, "muestras": 16, "profundidad": True},
    }

    @classmethod
    def preset(cls, calidad) -> dict:
        """Devuelve una copia del preset oficial de la calidad."""
        if isinstance(calidad, str):
            calidad_enum = RenderQuality.validar(calidad)
        elif isinstance(calidad, RenderQuality):
            calidad_enum = calidad
        else:
            raise ValueError("Calidad invalida.")
        return dict(cls.PRESETS[calidad_enum])

    @classmethod
    def resolucion_para(cls, calidad) -> Resolucion:
        """Resolucion oficial de la calidad pedida."""
        p = cls.preset(calidad)
        return Resolucion(p["ancho"], p["alto"])

    @classmethod
    def exige_profundidad(cls, calidad) -> bool:
        """Regla 4D: alta, 3d y fotorreal exigen canal de profundidad."""
        return bool(cls.preset(calidad)["profundidad"])
