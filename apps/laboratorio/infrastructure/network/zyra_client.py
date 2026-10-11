"""LAB-CORE: cliente de ZYRA Network (registro, sellado, confianza).

Ley 1: si la Red no esta configurada, lo reporta; nunca simula exito.
Reintentos reales con espera progresiva solo sobre fallos de
transporte; los rechazos definitivos (HTTP 4xx) no se reintentan.
"""
import json as _json
import time
import urllib.error
import urllib.request

from apps.laboratorio.constants.system.system_constants import SistemaConstantes
from apps.laboratorio.shared.exceptions.network_errors import (
    RedNoDisponibleError,
    RespuestaInvalidaError,
)

DESTINO_SELLO = "zyra/documents/seal"
ESPERA_BASE = 0.4


class ClienteZyra:
    """Unica puerta HTTP hacia ZYRA Network."""

    def __init__(self, config_red):
        if config_red is None:
            raise ValueError("ClienteZyra requiere su configuracion.")
        self._cfg = config_red

    @property
    def configurado(self) -> bool:
        return self._cfg.configurada

    def estado_conexion(self) -> dict:
        """Estado real y honesto del enlace con ZYRA Network."""
        if not self.configurado:
            return {
                "configurada": False,
                "conectada": False,
                "motivo": "URL de ZYRA Network no configurada",
            }
        try:
            self._peticion("GET", "/health")
            return {
                "configurada": True,
                "conectada": True,
                "motivo": "",
            }
        except RedNoDisponibleError as exc:
            return {
                "configurada": True,
                "conectada": False,
                "motivo": str(exc)[:300],
            }

    def _peticion(self, metodo: str, ruta: str, carga: dict = None) -> dict:
        if not self.configurado:
            raise RedNoDisponibleError(
                "URL de ZYRA Network no configurada."
            )
        url = self._cfg.url_zyra_core.rstrip("/") + ruta
        intentos_max = max(1, int(getattr(self._cfg, "reintentos", 1)))
        ultimo_error = ""
        for intento in range(1, intentos_max + 1):
            datos = _json.dumps(carga or {}).encode("utf-8")
            peticion = urllib.request.Request(
                url,
                data=datos if metodo != "GET" else None,
                method=metodo,
            )
            peticion.add_header("Content-Type", "application/json")
            peticion.add_header("X-ZYRA-APP", self._cfg.app_id)
            if self._cfg.api_token:
                peticion.add_header(
                    "Authorization", "Bearer " + self._cfg.api_token
                )
            try:
                with urllib.request.urlopen(
                    peticion, timeout=self._cfg.timeout_segundos
                ) as respuesta:
                    crudo = respuesta.read()
                return self._procesar(crudo)
            except urllib.error.HTTPError as exc:
                cuerpo = b""
                try:
                    cuerpo = exc.read()
                except Exception:
                    pass
                if exc.code >= 500:
                    ultimo_error = (
                        "ZYRA Network respondio HTTP " + str(exc.code)
                    )
                else:
                    raise RedNoDisponibleError(
                        "ZYRA Network rechazo la peticion (HTTP "
                        + str(exc.code) + "): "
                        + cuerpo.decode("utf-8", "replace")[:200]
                    ) from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                ultimo_error = "ZYRA Network inalcanzable: " + str(exc)
            if intento < intentos_max:
                espera = ESPERA_BASE * (2 ** (intento - 1))
                time.sleep(espera)
        raise RedNoDisponibleError(
            ultimo_error or "ZYRA Network inalcanzable."
        )

    @staticmethod
    def _procesar(crudo: bytes) -> dict:
        try:
            cuerpo = _json.loads(crudo.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise RespuestaInvalidaError(
                "Respuesta de ZYRA Network no es JSON valido."
            ) from exc
        if not isinstance(cuerpo, dict):
            raise RespuestaInvalidaError(
                "Respuesta de ZYRA Network debe ser un objeto JSON."
            )
        return cuerpo

    def registrar_app(self) -> dict:
        if not self.configurado:
            return {
                "registrado": False,
                "motivo": "URL de ZYRA Network no configurada",
            }
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
            return {
                "sellado": False,
                "motivo": "URL de ZYRA Network no configurada",
            }
        return self._peticion(
            "POST", "/documents/seal",
            {"titulo": titulo, "contenido": contenido},
        )

    def verificar_documento(self, documento_id: str) -> dict:
        if not documento_id:
            raise ValueError("documento_id requerido.")
        return self._peticion(
            "GET", "/documents/" + documento_id + "/verify"
        )

    def entregar(self, destino: str, carga: dict) -> dict:
        if not self.configurado:
            raise RedNoDisponibleError(
                "URL de ZYRA Network no configurada."
            )
        if destino == DESTINO_SELLO:
            return self.sellar_documento(
                str(carga.get("titulo", "")),
                str(carga.get("contenido", "")),
            )
        raise RespuestaInvalidaError(
            "Destino de entrega desconocido: " + destino
        )
