"""Motor de plantillas minimo y seguro: sustitucion con auto-escape.

Convencion: {{clave}} escapa el valor; {{clave!raw}} inserta HTML
ya construido con escape interno (nav, tablas, botones). Una clave
ausente aborta el render: nunca se publica una pagina incompleta.
"""
import re

from apps.laboratorio.infrastructure.security.html_sanitizer import escapar

PATRON = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)(!raw)?\s*\}\}")


def render(plantilla: str, contexto: dict) -> str:
    if not isinstance(plantilla, str) or not plantilla.strip():
        raise ValueError("Plantilla vacia o invalida.")
    if not isinstance(contexto, dict):
        raise ValueError("El contexto debe ser un dict.")

    def _reemp(m):
        clave = m.group(1)
        crudo = bool(m.group(2))
        if clave not in contexto:
            raise ValueError("Falta clave de plantilla: " + clave)
        valor = contexto[clave]
        texto = valor if isinstance(valor, str) else str(valor)
        return texto if crudo else escapar(texto)

    return PATRON.sub(_reemp, plantilla)


def validar_plantilla(plantilla: str) -> list:
    """Devuelve las claves que la plantilla requiere."""
    return sorted({m.group(1) for m in PATRON.finditer(plantilla)})
