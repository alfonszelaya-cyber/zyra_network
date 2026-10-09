"""Aplicacion HTTP de LABORATORIO sobre stdlib."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from apps.laboratorio.infrastructure.api.middleware import Intermediario
from apps.laboratorio.infrastructure.security.zid_auth import (
    anonimo,
    extraer_identidad,
)
from apps.laboratorio.registry.routes.route_registry import RegistroRutas
from apps.laboratorio.registry.services.service_registry import construir_contenedor
from apps.laboratorio.schemas.responses.envelopes import error as sobre_error
from apps.laboratorio.schemas.shared.common import MIME_JSON
from apps.laboratorio.shared.exceptions.domain_errors import PermisoDenegadoError
from apps.laboratorio.validators.shared.common_validators import validar_cuerpo_json


class ContextoPeticion:
    def __init__(self, identidad, ruta_params: dict, query: dict, cuerpo: bytes):
        self.identidad = identidad
        self.ruta_params = ruta_params
        self.query = query
        self._cuerpo = cuerpo
        self._json = None

    def json(self) -> dict:
        if self._json is None:
            self._json = validar_cuerpo_json(self._cuerpo)
        return self._json

    def json_opcional(self) -> dict:
        if not self._cuerpo:
            return {}
        return self.json()


class AplicacionLab:
    def __init__(self, contenedor):
        self.contenedor = contenedor
        self._rutas = RegistroRutas()
        self._rol_defecto = contenedor.obtener("config_permisos").rol_defecto
        self._intermediario = None

    def registrar(self, metodo, patron, handler, permiso=None, descripcion="", publica=False):
        self._rutas.registrar(metodo, patron, handler, permiso, descripcion, publica)

    def listar_rutas(self) -> list:
        return self._rutas.listar()

    def despachar_base(self, metodo, ruta, headers, cuerpo):
        metodo = str(metodo).upper()
        ruta_limpia, query = self._partir_ruta(ruta)
        headers_norm = {str(k).lower(): v for k, v in (headers or {}).items()}
        handler, params, permiso, publica = self._rutas.resolver(metodo, ruta_limpia)
        if publica:
            identidad = anonimo()
        else:
            try:
                identidad = extraer_identidad(headers_norm, self._rol_defecto)
            except ValueError as exc:
                estado, sobre = sobre_error("zid_ausente", str(exc))
                return estado, {"Content-Type": MIME_JSON}, self._json_bytes(sobre)
        if handler is None:
            estado, sobre = sobre_error(
                "entidad_no_encontrada",
                "Ruta no encontrada: " + metodo + " " + ruta_limpia,
            )
            return estado, {"Content-Type": MIME_JSON}, self._json_bytes(sobre)
        if permiso:
            try:
                identidad.exigir_permiso(permiso)
            except PermisoDenegadoError as exc:
                estado, sobre = sobre_error("permiso_denegado", str(exc))
                return estado, {"Content-Type": MIME_JSON}, self._json_bytes(sobre)
        ctx = ContextoPeticion(identidad, params, query, cuerpo or b"")
        resultado = handler(ctx)
        if len(resultado) == 3:
            status, carga, headers_extra = resultado
        else:
            status, carga = resultado[0], resultado[1]
            headers_extra = {}
        if isinstance(carga, bytes):
            headers_out = dict(headers_extra)
            headers_out.setdefault("Content-Type", "application/octet-stream")
            return int(status), headers_out, carga
        headers_out = {"Content-Type": MIME_JSON}
        headers_out.update(headers_extra)
        return int(status), headers_out, self._json_bytes(carga)

    def despachar(self, metodo, ruta, headers, cuerpo):
        if self._intermediario is not None:
            return self._intermediario.servir(metodo, ruta, headers, cuerpo)
        return self.despachar_base(metodo, ruta, headers, cuerpo)

    def activar_intermediario(self, auditoria):
        self._intermediario = Intermediario(self.despachar_base, auditoria)

    @staticmethod
    def _partir_ruta(ruta: str) -> tuple:
        partes = urlsplit(ruta)
        camino = partes.path or "/"
        query = {k: v[0] for k, v in parse_qs(partes.query).items()}
        return camino, query

    @staticmethod
    def _json_bytes(carga) -> bytes:
        return json.dumps(carga, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")

    def ejecutar(self, host: str = "0.0.0.0", puerto: int = 8090):
        app = self

        class _Manejador(BaseHTTPRequestHandler):
            def _atender(self):
                largo = int(self.headers.get("Content-Length", 0) or 0)
                cuerpo = self.rfile.read(largo) if largo else b""
                status, headers_out, salida = app.despachar(
                    self.command, self.path, dict(self.headers), cuerpo
                )
                self.send_response(int(status))
                for clave, valor in headers_out.items():
                    self.send_header(clave, valor)
                self.send_header("Content-Length", str(len(salida)))
                self.end_headers()
                self.wfile.write(salida)

            def do_GET(self):
                self._atender()

            def do_POST(self):
                self._atender()

            def do_PUT(self):
                self._atender()

            def do_PATCH(self):
                self._atender()

            def do_DELETE(self):
                self._atender()

            def log_message(self, formato, *args):
                return

        servidor = ThreadingHTTPServer((host, int(puerto)), _Manejador)
        servidor.serve_forever()


def montar_aplicacion(ruta_bd: str = ":memory:") -> AplicacionLab:
    """Compone TODA la app: contenedor + modulo + routers + intermediario."""
    from apps.laboratorio.modules.simulation_module import conectar as conectar_simulacion
    from apps.laboratorio.routers.public.health import registrar_rutas as registrar_salud
    from apps.laboratorio.modules.library_module import conectar as conectar_biblioteca
    from apps.laboratorio.modules.creation_module import conectar as conectar_creacion
    from apps.laboratorio.modules.design_module import conectar as conectar_diseno
    from apps.laboratorio.modules.understanding_module import conectar as conectar_comprension
    from apps.laboratorio.modules.capture_module import conectar as conectar_captura
    from apps.laboratorio.routers.public.ui import registrar_rutas as registrar_ui

    contenedor = construir_contenedor(ruta_bd)
    app = AplicacionLab(contenedor)
    conectar_simulacion(app)
    registrar_salud(app)
    conectar_biblioteca(app)
    conectar_creacion(app)
    conectar_diseno(app)
    conectar_comprension(app)
    conectar_captura(app)
    registrar_ui(app)
    app.activar_intermediario(contenedor.obtener("auditoria_sink"))
    return app
