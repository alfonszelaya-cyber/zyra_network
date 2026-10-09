"""Motor de comprension textual: analisis REAL y deterministico.

Extrae mediciones, montos, porcentajes, anos y dominio del texto.
Cada hallazgo declara su certeza. Sin IA externa: reglas
verificables, mismo estandar que el parser de documentos.
"""
import re

from apps.laboratorio.application.services.document_parser import PALABRAS_POR_TIPO
from apps.laboratorio.shared.enums.certainty import Certainty

RX_MEDICION = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(manzanas?|hectareas?|tareas?|kilometros?|km|m2|metros?|cuadras?)\b",
    re.IGNORECASE,
)
RX_MONTO = re.compile(
    r"\b(\d[\d,]*(?:\.\d+)?)\s*(dolares?|colones?|usd|euros?)\b",
    re.IGNORECASE,
)
RX_PORCENTAJE = re.compile(r"(\d+(?:\.\d+)?)\s*%(?!\w)")
RX_ANIO = re.compile(r"\b(19\d{2}|20\d{2})\b")
MAX_HALLAZGOS = 50


class MotorComprensionTextual:
    """Analiza texto y produce hallazgos con certeza declarada."""

    def capacidades(self) -> dict:
        return {
            "entidades": ["mediciones", "montos", "porcentajes", "anios"],
            "dominios": sorted(PALABRAS_POR_TIPO.keys()),
            "certeza": [Certainty.EVIDENCIA_ENCONTRADA.value, Certainty.INFERENCIA.value],
        }

    def analizar(self, texto: str) -> dict:
        if not isinstance(texto, str) or not texto.strip():
            raise ValueError("El motor de comprension requiere texto no vacio.")
        limpio = texto.strip()
        hallazgos = []
        mediciones = []
        for m in RX_MEDICION.finditer(limpio):
            contenido = m.group(0).strip()
            mediciones.append(contenido)
            hallazgos.append({
                "tipo": "medicion",
                "contenido": contenido,
                "certeza": Certainty.EVIDENCIA_ENCONTRADA.value,
                "razon": "coincidencia literal de numero + unidad en el texto",
            })
        montos = []
        for m in RX_MONTO.finditer(limpio):
            contenido = m.group(0).strip()
            montos.append(contenido)
            hallazgos.append({
                "tipo": "monto",
                "contenido": contenido,
                "certeza": Certainty.EVIDENCIA_ENCONTRADA.value,
                "razon": "coincidencia literal de cantidad monetaria",
            })
        porcentajes = []
        for m in RX_PORCENTAJE.finditer(limpio):
            contenido = m.group(0).strip()
            porcentajes.append(contenido)
            hallazgos.append({
                "tipo": "porcentaje",
                "contenido": contenido,
                "certeza": Certainty.EVIDENCIA_ENCONTRADA.value,
                "razon": "coincidencia literal de porcentaje",
            })
        anios = []
        for m in RX_ANIO.finditer(limpio):
            anios.append(m.group(0))
        anios_unicos = sorted(set(anios))
        for anio in anios_unicos:
            hallazgos.append({
                "tipo": "anio",
                "contenido": anio,
                "certeza": Certainty.EVIDENCIA_ENCONTRADA.value,
                "razon": "coincidencia literal de ano",
            })
        dominio, detectado, coincidencias = self._dominio(limpio)
        if detectado:
            hallazgos.append({
                "tipo": "dominio",
                "contenido": dominio,
                "certeza": Certainty.INFERENCIA.value,
                "razon": str(coincidencias) + " terminos del dominio " + dominio + " presentes",
            })
        hallazgos = hallazgos[:MAX_HALLAZGOS]
        peso = {
            Certainty.EVIDENCIA_ENCONTRADA.value: 1.0,
            Certainty.INFERENCIA.value: 0.6,
        }
        if hallazgos:
            confianza = sum(peso.get(h["certeza"], 0.5) for h in hallazgos) / len(hallazgos)
        else:
            confianza = 0.0
        return {
            "resumen": limpio[:200],
            "hallazgos": hallazgos,
            "entidades": {
                "mediciones": mediciones[:20],
                "montos": montos[:20],
                "porcentajes": porcentajes[:20],
                "anios": anios_unicos[:20],
            },
            "dominio": dominio,
            "confianza": round(confianza, 4),
        }

    @staticmethod
    def _dominio(texto: str) -> tuple:
        minusculas = texto.lower()
        conteo = {}
        for tipo, palabras in PALABRAS_POR_TIPO.items():
            total = 0
            for palabra in palabras:
                total += len(re.findall(r"\b" + re.escape(palabra) + r"\b", minusculas))
            if total:
                conteo[tipo] = total
        if not conteo:
            return "general", False, 0
        mejor = max(conteo, key=lambda k: conteo[k])
        return mejor, True, conteo[mejor]
