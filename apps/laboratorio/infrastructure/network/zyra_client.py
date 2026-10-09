"""LAB-CORE: cliente de ZYRA Core (registro, sellado, confianza).

Ley 1: si la red no esta configurada, lo reporta; nunca simula exito.
"""
import json as _json
import urllib.error
import urllib.request

from apps.laboratorio.constants.system.system_constants import SistemaConstantes
from apps.laboratorio.shared.exceptions.network_errors import (
    RedNoDisponibleError,
    RespuestaInvalidaError,
)

DESTINO_SELLO = "zyra/documents/seal"


class ClienteZyra:
    """Unica puerta HTTP hacia ZYRA Core."""

    def __init__(self, config_red):
        if config_red is None:
            raise ValueError("ClienteZyra requiere su configuracion.")
        self._cfg = config_red

    @property
    def configurado(self) -> bool:
        return self._cfg.configurada

    def _peticion(self, metodo: str, ruta: str, carga: dict = None) -> dict:
        if not self.configurado:
            raise RedNoDisponibleError("URL de ZYRA Core no configurada.")
        url = self._cfg.url_zyra_core.rstrip("/") + ruta
        datos = _json.dumps(carga or {}).encode("utf-8")
        peticion = urllib.request.Request(
            url, data=datos if metodo != "GET" else None, method=metodo
        )
        peticion.add_header("Content-Type", "application/json")
        peticion.add_header("X-ZYRA-APP", self._cfg.app_id)
        if self._cfg.api_token:
            peticion.add_header("Authorization", "Bearer " + self._cfg.api_token)
        try:
            with urllib.request.urlopen(
                peticion, timeout=self._cfg.timeout_segundos
            ) as respuesta:
                crudo = respuesta.read()
        except urllib.error.HTTPError as exc:
            raise RedNoDisponibleError(
                "ZYRA Core respondio HTTP " + str(exc.code)
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RedNoDisponibleError(
                "ZYRA Core inalcanzable: " + str(exc)
            ) from exc
        try:
            cuerpo = _json.loads(crudo.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise RespuestaInvalidaError(
                "Respuesta de ZYRA Core no es JSON valido."
            ) from exc
        if not isinstance(cuerpo, dict):
            raise RespuestaInvalidaError(
                "Respuesta de ZYRA Core debe ser un objeto JSON."
            )
        return cuerpo

    def registrar_app(self) -> dict:
        if not self.configurado:
            return {"registrado": False, "motivo": "URL de ZYRA Core no configurada"}
        return self._peticion(
            "POST",
            "/apps/register",
            {
                "app_id": self._cfg.app_id,
                "nombre": SistemaConstantes.NOMBRE_APP,
                "version": SistemaConstantes.VERSION_APP,
            },
        )

    def sellar_documento(self, titulo: str, contenido: str) -> dict:
        if not self.configurado:
            return {"sellado": False, "motivo": "URL de ZYRA Core no configurada"}
        return self._peticion(
            "POST", "/documents/seal", {"titulo": titulo, "contenido": contenido}
        )

    def verificar_documento(self, documento_id: str) -> dict:
        if not documento_id:
            raise ValueError("documento_id requerido.")
        return self._peticion("GET", "/documents/" + documento_id + "/verify")

    def entregar(self, destino: str, carga: dict) -> dict:
        if not self.configurado:
            raise RedNoDisponibleError("URL de ZYRA Core no configurada.")
        if destino == DESTINO_SELLO:
            return self.sellar_documento(
                str(carga.get("titulo", "")), str(carga.get("contenido", ""))
            )
        raise RespuestaInvalidaError("Destino de entrega desconocido: " + destino)
