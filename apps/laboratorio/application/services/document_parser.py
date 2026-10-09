"""Parser de documentos: convierte texto libre en datos de proyecto.

Produccion real y deterministica: recibe cualquier documento pegado
(una ley, una idea de negocio, una finca, un edificio, una app),
extrae el titulo (primera linea), la descripcion (el resto) y
detecta el tipo de creacion oficial por palabras clave del dominio.
"""

import re

from apps.laboratorio.shared.enums.creation_type import CreationType

MINIMO_CARACTERES = 20
MAXIMO_CARACTERES = 50000
TITULO_MAX = 200
DESCRIPCION_MAX = 2000

PALABRAS_POR_TIPO = {
    "ley": ("ley", "decreto", "articulo", "reforma", "legislativo", "legislacion", "jurisdiccion"),
    "arquitectura": ("edificio", "construccion", "arquitectura", "fachada", "planta baja", "planos", "vivienda", "estructura"),
    "negocio": ("negocio", "tienda", "comercio", "ventas", "clientes", "emprendimiento", "sucursal"),
    "app": ("app", "aplicacion", "software", "plataforma", "pantalla", "usuarios", "movil", "sistema"),
    "agro": ("finca", "cultivo", "ganado", "cosecha", "siembra", "parcela", "agricola", "riego", "ganadera", "manzanas"),
    "empleo": ("empleo", "trabajador", "vacante", "contratacion", "candidato", "salario", "puesto de trabajo"),
    "educacion": ("escuela", "estudiante", "educacion", "beca", "universidad", "maestro", "clases", "colegio", "prekinder"),
    "producto": ("producto", "maquina", "invento", "prototipo", "fabricar", "manufactura", "piezas"),
    "gobierno": ("gobierno", "politica", "ministerio", "alcaldia", "municipal", "plan nacional", "publico"),
    "infraestructura": ("carretera", "puente", "infraestructura", "obra civil", "autopista", "drenaje", "camino", "alcantarillado"),
    "presentacion": ("presentacion", "diapositiva", "exposicion", "inversionistas", "pitch", "audiencia"),
}


def _detectar_tipo(texto: str) -> tuple:
    minusculas = texto.lower()
    conteo = {}
    for tipo, palabras in PALABRAS_POR_TIPO.items():
        total = 0
        for palabra in palabras:
            total += len(re.findall(r"\b" + re.escape(palabra) + r"\b", minusculas))
        if total:
            conteo[tipo] = total
    if not conteo:
        return CreationType.PRESENTACION.value, False, 0
    mejor = max(conteo, key=lambda k: conteo[k])
    return mejor, True, conteo[mejor]


def parsear_documento(texto) -> dict:
    """Convierte un documento en titulo + descripcion + tipo detectado."""
    if not isinstance(texto, str):
        raise ValueError("El documento debe ser texto.")
    limpio = texto.strip()
    if len(limpio) < MINIMO_CARACTERES:
        raise ValueError(
            "Documento demasiado corto: se requieren al menos "
            + str(MINIMO_CARACTERES) + " caracteres."
        )
    if len(limpio) > MAXIMO_CARACTERES:
        raise ValueError(
            "Documento demasiado largo: maximo "
            + str(MAXIMO_CARACTERES) + " caracteres."
        )
    lineas = [l.strip() for l in limpio.splitlines() if l.strip()]
    if not lineas:
        raise ValueError("Documento vacio.")
    titulo = lineas[0][:TITULO_MAX].strip()
    if not titulo:
        raise ValueError("No se pudo extraer un titulo del documento.")
    descripcion = " ".join(lineas[1:])[:DESCRIPCION_MAX].strip()
    tipo, detectado, coincidencias = _detectar_tipo(limpio)
    return {
        "titulo": titulo,
        "descripcion": descripcion,
        "tipo": tipo,
        "tipo_detectado": detectado,
        "coincidencias": coincidencias,
        "palabras": len(limpio.split()),
        "lineas": len(lineas),
    }
