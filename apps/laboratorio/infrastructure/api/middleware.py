"""Intermediario: excepciones tipificadas -> sobre HTTP + auditoria."""
import json

from apps.laboratorio.schemas.responses.envelopes import desde_excepcion
from apps.laboratorio.schemas.shared.common import MIME_JSON
from apps.laboratorio.shared.utilities.logging_utils import obtener_logger


class Intermediario:
    def __init__(self, despachar_base, auditoria):
        self._base = despachar_base
        self._auditoria = auditoria
        self._logger = obtener_logger("http")

    def servir(self, metodo: str, ruta: str, headers: dict, cuerpo: bytes) -> tuple:
        try:
            status, headers_out, cuerpo_out = self._base(metodo, ruta, headers, cuerpo)
            self._logger.info(metodo + " " + ruta + " -> " + str(status))
            return status, headers_out, cuerpo_out
        except Exception as exc:
            status, sobre = desde_excepcion(exc)
            if self._auditoria is not None:
                try:
                    self._auditoria.registrar(
                        None, "http." + metodo.lower(), ruta, "error",
                        {"codigo": sobre["error"]["codigo"], "mensaje": str(exc)[:300]},
                    )
                except Exception:
                    pass
            self._logger.error(
                metodo + " " + ruta + " -> "
                + sobre["error"]["codigo"] + ": " + str(exc)
            )
            return status, {"Content-Type": MIME_JSON}, json.dumps(sobre, ensure_ascii=True).encode("utf-8")
