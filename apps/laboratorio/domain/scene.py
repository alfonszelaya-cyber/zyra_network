"""Escena 3D: el mundo que se renderiza y se genera.

Arquitectura invertida: primero el mundo (SCENE/WORLD), despues
el render y el destino. Los objetos se validan contra lo que el
motor SVG real puede dibujar (rect, circle, texto).
"""
import re
from dataclasses import dataclass, field
from typing import List

from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador

PATRON_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
FORMAS_VALIDAS = ("rect", "circle", "texto")
MIN_DIM = 16
MAX_DIM = 4096
MAX_OBJETOS = 200


@dataclass
class Escena3D(EntidadBase):
    """Mundo con objetos: base de imagen, pagina, modelo y animacion."""

    prefijo_id = "scn"

    proyecto_id: Identificador = None
    nombre: str = ""
    ancho: int = 800
    alto: int = 600
    objetos: List[dict] = field(default_factory=list)

    def __post_init__(self):
        if self.proyecto_id is None:
            raise ValueError("La escena requiere el id de su proyecto.")
        if not self.nombre.strip():
            raise ValueError("La escena requiere nombre.")
        self.nombre = self.nombre.strip()
        if not (MIN_DIM <= self.ancho <= MAX_DIM):
            raise ValueError("ancho fuera de rango 16-4096.")
        if not (MIN_DIM <= self.alto <= MAX_DIM):
            raise ValueError("alto fuera de rango 16-4096.")

    def agregar_objeto(self, objeto: dict) -> dict:
        """Agrega un objeto validado; devuelve el objeto limpio."""
        if not isinstance(objeto, dict):
            raise ValueError("El objeto debe ser un objeto JSON.")
        forma = str(objeto.get("forma", "")).strip().lower()
        if forma not in FORMAS_VALIDAS:
            raise ValueError(
                "Forma no soportada: " + repr(forma)
                + ". Validas: " + ", ".join(FORMAS_VALIDAS)
            )
        color = str(objeto.get("color", "#64748B")).strip()
        if not PATRON_HEX.match(color):
            raise ValueError("Color invalido: " + repr(color))
        limpio = {"forma": forma, "color": color}
        try:
            if forma == "rect":
                limpio.update(
                    x=float(objeto.get("x", 0)), y=float(objeto.get("y", 0)),
                    w=float(objeto.get("w", 10)), h=float(objeto.get("h", 10)),
                )
                if limpio["w"] <= 0 or limpio["h"] <= 0:
                    raise ValueError("rect requiere w y h positivos.")
            elif forma == "circle":
                limpio.update(
                    cx=float(objeto.get("cx", 0)), cy=float(objeto.get("cy", 0)),
                    r=float(objeto.get("r", 10)),
                )
                if limpio["r"] <= 0:
                    raise ValueError("circle requiere r positivo.")
            else:
                contenido = str(objeto.get("contenido", "")).strip()
                if not contenido:
                    raise ValueError("texto requiere contenido.")
                limpio.update(
                    x=float(objeto.get("x", 0)), y=float(objeto.get("y", 20)),
                    contenido=contenido[:300],
                )
        except (TypeError, ValueError) as exc:
            if "rect" in str(exc) or "circle" in str(exc) or "texto" in str(exc):
                raise
            raise ValueError("Coordenadas del objeto invalidas.") from exc
        if len(self.objetos) >= MAX_OBJETOS:
            raise ValueError("La escena alcanzo el maximo de " + str(MAX_OBJETOS) + " objetos.")
        self.objetos.append(limpio)
        self.marcar_actualizacion()
        return limpio

    @property
    def es_renderizable(self) -> bool:
        return len(self.objetos) > 0

    def a_especificacion(self) -> dict:
        """Especificacion que consume el MotorRenderSVG (puerto real)."""
        return {
            "ancho": self.ancho, "alto": self.alto,
            "fondo": "#0F172A", "objetos": list(self.objetos),
        }
