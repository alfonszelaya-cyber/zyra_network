"""Entrada de captura: cualquier material que alimenta un proyecto.

Produccion real: el texto se guarda integro; la foto/escaneo llega
en base64, se decodifica y se sella con SHA-256 (integridad ZYRA).
"""
import base64
import binascii
from dataclasses import dataclass

from apps.laboratorio.shared.enums.input_kind import InputKind
from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador

MAX_BYTES_FOTO = 5 * 1024 * 1024
MIN_TEXTO = 20
MAX_TEXTO = 200000


@dataclass
class EntradaCaptura(EntidadBase):
    """Material capturado para un proyecto."""

    prefijo_id = "inp"

    proyecto_id: Identificador = None
    tipo: InputKind = InputKind.TEXTO
    titulo: str = ""
    contenido: str = ""
    hash_sha256: str = ""
    tamano_bytes: int = 0

    def __post_init__(self):
        if self.proyecto_id is None:
            raise ValueError("La entrada requiere el id de su proyecto.")
        if not self.titulo.strip():
            raise ValueError("La entrada requiere titulo.")
        self.titulo = self.titulo.strip()

    @classmethod
    def desde_texto(cls, id_ent, proyecto_id, titulo, texto):
        if not isinstance(texto, str) or not texto.strip():
            raise ValueError("El texto de la entrada esta vacio.")
        limpio = texto.strip()
        if len(limpio) < MIN_TEXTO:
            raise ValueError("Entrada demasiado corta (min " + str(MIN_TEXTO) + " caracteres).")
        if len(limpio) > MAX_TEXTO:
            raise ValueError("Entrada demasiado larga (max " + str(MAX_TEXTO) + " caracteres).")
        from apps.laboratorio.shared.helpers.hashing import sha256_texto
        return cls(
            id=id_ent, proyecto_id=proyecto_id, tipo=InputKind.TEXTO,
            titulo=titulo, contenido=limpio,
            hash_sha256=sha256_texto(limpio), tamano_bytes=len(limpio.encode("utf-8")),
        )

    @classmethod
    def desde_base64(cls, id_ent, proyecto_id, titulo, datos_b64, tipo=InputKind.FOTO):
        if not isinstance(datos_b64, str) or not datos_b64.strip():
            raise ValueError("Los datos base64 estan vacios.")
        crudo = datos_b64.strip()
        if "," in crudo and crudo.startswith("data:"):
            crudo = crudo.split(",", 1)[1]
        try:
            binario = base64.b64decode(crudo, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Base64 invalido.") from exc
        if not binario:
            raise ValueError("Los datos decodificados estan vacios.")
        if len(binario) > MAX_BYTES_FOTO:
            raise ValueError("La imagen excede el maximo de 5 MB.")
        from apps.laboratorio.shared.helpers.hashing import sha256_bytes
        import base64 as b64
        return cls(
            id=id_ent, proyecto_id=proyecto_id, tipo=tipo,
            titulo=titulo, contenido=b64.b64encode(binario).decode("ascii"),
            hash_sha256=sha256_bytes(binario), tamano_bytes=len(binario),
        )
