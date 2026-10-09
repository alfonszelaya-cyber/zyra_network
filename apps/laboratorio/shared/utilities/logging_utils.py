"""Logging estructurado JSON por modulo, sin handlers duplicados."""
import json
import logging
import sys


class FormatoEstructurado(logging.Formatter):
    """Emite cada linea de log como objeto JSON plano."""

    def format(self, record: logging.LogRecord) -> str:
        datos = {
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
        }
        if record.exc_info:
            datos["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=True)


_cache_loggers = {}


def obtener_logger(nombre: str) -> logging.Logger:
    """Devuelve el logger del modulo con formato estructurado."""
    if not nombre or not nombre.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Nombre de logger invalido.")
    clave = "laboratorio." + nombre
    if clave in _cache_loggers:
        return _cache_loggers[clave]
    logger = logging.getLogger(clave)
    if not logger.handlers:
        manejador = logging.StreamHandler(sys.stdout)
        manejador.setFormatter(FormatoEstructurado())
        logger.addHandler(manejador)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    _cache_loggers[clave] = logger
    return logger
