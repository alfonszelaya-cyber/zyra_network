"""SALIDA UNIVERSAL: UN protocolo, TODOS los destinos.

Conectable en caliente a cualquier dispositivo sin codigo nuevo:
  - pantalla_local / hdmi / proyector : framebuffer real
    (/dev/fb0 o LAB_DISPLAY_FB); el frame PNG se convierte a
    RGB crudo y se escribe en el framebuffer
  - udp : stream de frames a cualquier receptor (TV box,
    Raspberry, decodificador, otro server) con fragmentacion
    [total][seq][partes] + payload
  - web : telefonos y navegadores SIN instalar nada: el frame
    actual se sirve por HTTP en
    GET /laboratorio/api/v1/displays/targets/{id}/frame
  - hypervsn / looking_glass / openxr : dispositivos por URL
    (env LAB_HYPERVSN_URL / LAB_LOOKINGGLASS_URL /
    LAB_OPENXR_ENDPOINT o registrados en caliente)
  - auto : elige el mejor destino detectado

Ley 1: sin destino registrado, presentar() lo dice con motivo
real. Nunca finge entrega.
"""
import os
import socket
import struct
import threading
import time
import urllib.request

from apps.laboratorio.infrastructure.providers.png_decoder import (
    decodificar_png_rgb,
)
from apps.laboratorio.shared.adapters.engine_adapter import AdaptadorMotor
from apps.laboratorio.shared.exceptions.pipeline_errors import (
    DestinoNoDisponibleError,
)
from apps.laboratorio.shared.interfaces.display_adapter import DisplayAdapter

TIPOS_VALIDOS = (
    "pantalla_local", "hdmi", "proyector", "udp", "web",
    "hypervsn", "looking_glass", "openxr", "auto",
)
TIPOS_LOCALES = ("pantalla_local", "hdmi", "proyector")
TIPOS_URL = ("hypervsn", "looking_glass", "openxr")
UDP_CHUNK = 60000


class MotorHolo3D(AdaptadorMotor, DisplayAdapter):
    """Enrutador universal de salidas visuales."""

    def __init__(self):
        AdaptadorMotor.__init__(self, "display_holo3d", "display", "1.0.0")
        self.marcar_disponible()
        self._lock = threading.Lock()
        self._destinos = {}
        self._frames = {}
        self._tipos_frame = {}
        self._contador = 0

    def kind(self) -> str:
        return "universal"

    def disponible(self) -> bool:
        return self.estado.value == "disponible"

    def capacidades(self) -> dict:
        return {
            "protocolo": "universal multi-destino",
            "tipos": TIPOS_VALIDOS,
            "deteccion": "pantalla_local, hypervsn, looking_glass, openxr",
            "web_pull": "/laboratorio/api/v1/displays/targets/{id}/frame",
            "nota": "conecte cualquier dispositivo registrandolo en caliente",
        }

    def detectar_dispositivos(self) -> dict:
        """Dispositivos visibles AHORA en el entorno real."""
        encontrados = {}
        fb = os.environ.get("LAB_DISPLAY_FB", "").strip()
        if fb and os.path.exists(fb):
            encontrados["pantalla_local"] = fb
        elif os.path.exists("/dev/fb0"):
            encontrados["pantalla_local"] = "/dev/fb0"
        pares = (
            ("LAB_HYPERVSN_URL", "hypervsn"),
            ("LAB_LOOKINGGLASS_URL", "looking_glass"),
            ("LAB_OPENXR_ENDPOINT", "openxr"),
        )
        for env, tipo in pares:
            valor = os.environ.get(env, "").strip()
            if valor:
                encontrados[tipo] = valor
        return encontrados

    def registrar_destino(
        self, tipo: str, direccion: str = "", nombre: str = ""
    ) -> dict:
        if tipo not in TIPOS_VALIDOS:
            raise ValueError(
                "Tipo de destino desconocido: " + repr(tipo)
                + ". Validos: " + ", ".join(TIPOS_VALIDOS)
            )
        direccion = str(direccion or "").strip()
        if tipo in ("udp",) + TIPOS_URL and not direccion:
            raise ValueError(
                "El tipo " + tipo + " requiere direccion."
            )
        if tipo == "auto":
            deteccion = self.detectar_dispositivos()
            if not deteccion:
                raise DestinoNoDisponibleError(
                    "auto no encontro ningun dispositivo: registre uno "
                    "explicito o declare su variable de entorno."
                )
            primer = sorted(deteccion.items())[0]
            tipo = primer[0]
            direccion = primer[1]
        with self._lock:
            self._contador += 1
            id_destino = "disp-" + str(self._contador).zfill(4)
            self._destinos[id_destino] = {
                "id": id_destino,
                "tipo": tipo,
                "direccion": direccion,
                "nombre": str(nombre or "")[:80],
                "creado_en": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                ),
            }
            self._frames[id_destino] = None
            self._tipos_frame[id_destino] = "image/png"
        return {
            "id": id_destino, "tipo": tipo, "direccion": direccion
        }

    def quitar_destino(self, id_destino: str) -> bool:
        with self._lock:
            if id_destino in self._destinos:
                del self._destinos[id_destino]
                self._frames.pop(id_destino, None)
                self._tipos_frame.pop(id_destino, None)
                return True
        return False

    def listar_destinos(self) -> dict:
        with self._lock:
            destinos = [dict(d) for d in self._destinos.values()]
            estados = {
                d["id"]: (self._frames.get(d["id"]) is not None)
                for d in destinos
            }
        return {
            "destinos": destinos,
            "con_frame": estados,
            "deteccion": self.detectar_dispositivos(),
        }

    def _destino(self, id_destino: str) -> dict:
        with self._lock:
            destino = self._destinos.get(id_destino)
        if destino is None:
            raise ValueError("Destino desconocido: " + id_destino)
        return destino

    def _resolver_auto(self, destino: dict) -> dict:
        if destino["tipo"] != "auto":
            return destino
        deteccion = self.detectar_dispositivos()
        if not deteccion:
            raise DestinoNoDisponibleError(
                "auto sin dispositivos detectados en este momento."
            )
        primer = sorted(deteccion.items())[0]
        return {
            "id": destino["id"],
            "tipo": primer[0],
            "direccion": primer[1],
            "nombre": destino["nombre"],
        }

    def _volcar_framebuffer(
        self, destino: dict, frame_bytes: bytes
    ) -> dict:
        ruta = destino.get("direccion") or (
            self.detectar_dispositivos().get("pantalla_local", "")
        )
        if not ruta:
            return {
                "id": destino["id"], "entregado": False,
                "motivo": "sin framebuffer disponible en el sistema",
            }
        try:
            ancho, alto, pixeles = decodificar_png_rgb(frame_bytes)
            with open(ruta, "wb") as manejador:
                manejador.seek(0)
                manejador.write(pixeles)
            return {
                "id": destino["id"], "entregado": True,
                "canal": "framebuffer", "ruta": ruta,
                "resolucion": [ancho, alto],
            }
        except Exception as exc:
            return {
                "id": destino["id"], "entregado": False,
                "motivo": "framebuffer fallo: " + str(exc)[:200],
            }

    def _enviar_udp(self, destino: dict, frame_bytes: bytes) -> dict:
        direccion = destino.get("direccion", "")
        partes = direccion.rsplit(":", 1)
        if len(partes) != 2:
            return {
                "id": destino["id"], "entregado": False,
                "motivo": "udp requiere host:puerto",
            }
        host = partes[0].strip()
        try:
            puerto = int(partes[1].strip())
        except ValueError:
            return {
                "id": destino["id"], "entregado": False,
                "motivo": "puerto udp invalido",
            }
        total = len(frame_bytes)
        partes_n = max(1, (total + UDP_CHUNK - 1) // UDP_CHUNK)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                for seq in range(partes_n):
                    trozo = frame_bytes[
                        seq * UDP_CHUNK:(seq + 1) * UDP_CHUNK
                    ]
                    encabezado = struct.pack("!IIH", total, seq, partes_n)
                    sock.sendto(encabezado + trozo, (host, puerto))
            finally:
                sock.close()
        except Exception as exc:
            return {
                "id": destino["id"], "entregado": False,
                "motivo": "udp fallo: " + str(exc)[:200],
            }
        return {
            "id": destino["id"], "entregado": True,
            "canal": "udp", "destino": direccion,
            "bytes": total, "partes": partes_n,
        }

    def _enviar_dispositivo_url(
        self, destino: dict, frame_bytes: bytes
    ) -> dict:
        url = destino.get("direccion", "")
        if not url:
            return {
                "id": destino["id"], "entregado": False,
                "motivo": "el dispositivo no tiene URL configurada",
            }
        try:
            peticion = urllib.request.Request(
                url,
                data=frame_bytes,
                method="POST",
                headers={"Content-Type": "application/octet-stream"},
            )
            with urllib.request.urlopen(peticion, timeout=15) as resp:
                cuerpo = resp.read()[:400]
            return {
                "id": destino["id"], "entregado": True,
                "canal": destino["tipo"], "url": url,
                "respuesta": cuerpo.decode("utf-8", "replace"),
            }
        except Exception as exc:
            return {
                "id": destino["id"], "entregado": False,
                "motivo": destino["tipo"] + " fallo: " + str(exc)[:200],
            }

    def presentar(
        self, frame_bytes, config=None,
        content_type: str = "image/png",
    ) -> dict:
        """Entrega el frame a TODOS los destinos registrados."""
        if not isinstance(frame_bytes, (bytes, bytearray)) or not frame_bytes:
            raise ValueError("Frame vacio o invalido.")
        config = dict(config or {})
        filtro = str(config.get("tipo", "")).strip()
        frame = bytes(frame_bytes)
        with self._lock:
            seleccion = [
                dict(d) for d in self._destinos.values()
                if not filtro or d["tipo"] == filtro
            ]
            if not seleccion:
                return {
                    "entregado": False,
                    "destinos": 0,
                    "motivo": (
                        "sin destino registrado: registre uno con POST "
                        "/laboratorio/api/v1/displays/targets"
                    ),
                }
            for destino in seleccion:
                self._frames[destino["id"]] = frame
                self._tipos_frame[destino["id"]] = content_type
        resultados = []
        for destino in seleccion:
            try:
                real = self._resolver_auto(destino)
                tipo = real["tipo"]
                if tipo in TIPOS_LOCALES:
                    resultado = self._volcar_framebuffer(real, frame)
                elif tipo == "udp":
                    resultado = self._enviar_udp(real, frame)
                elif tipo in TIPOS_URL:
                    resultado = self._enviar_dispositivo_url(real, frame)
                else:
                    resultado = {
                        "id": real["id"], "entregado": True,
                        "canal": "pull",
                        "url": (
                            "/laboratorio/api/v1/displays/targets/"
                            + real["id"] + "/frame"
                        ),
                    }
            except Exception as exc:
                resultado = {
                    "id": destino["id"], "entregado": False,
                    "motivo": type(exc).__name__ + ": " + str(exc)[:200],
                }
            resultados.append(resultado)
        entregados = sum(1 for r in resultados if r.get("entregado"))
        return {
            "entregado": entregados > 0,
            "destinos": len(resultados),
            "entregados": entregados,
            "resultados": resultados,
        }

    def frame_actual(self, id_destino: str):
        """Frame vigente para web/moviles (pull). Devuelve (bytes, mime)."""
        self._destino(id_destino)
        with self._lock:
            frame = self._frames.get(id_destino)
            mime = self._tipos_frame.get(id_destino, "image/png")
        if frame is None:
            raise ValueError(
                "El destino " + id_destino
                + " no tiene frame presentado aun."
            )
        return frame, mime
