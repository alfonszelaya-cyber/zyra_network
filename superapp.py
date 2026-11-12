"""ZYRA SuperApp: una sola entrada bonita.

Arranca los servidores internos (cada uno con su
store y su cliente de red, independientes entre si)
y los expone bajo UNA sola entrada publica:
/             portal
/verificar    verificador publico (gratis)
/verify       proxy a la Red
/mpe /agro /axis /semilla /nexo /subastas /ciclo /laboratorio
/health       estado del servicio
"""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = Path(
    os.environ.get("SUPERAPP_DATA_DIR") or (ROOT / "data")
)
DATA_DIR.mkdir(parents=True, exist_ok=True)

PORT = int(
    os.environ.get("PORT")
    or os.environ.get("SUPERAPP_PORT")
    or 8080
)

if os.environ.get("ZYRA_URL"):
    ZYRA_URL = os.environ["ZYRA_URL"].strip().strip('"\'()').rstrip("/")
elif os.environ.get("ZYRA_HOST"):
    _h = os.environ["ZYRA_HOST"].strip().strip('"\'()').rstrip("/")
    if _h and "." not in _h:
        _h = _h + ".onrender.com"
    ZYRA_URL = ("https://" + _h).rstrip("/")
else:
    ZYRA_URL = ""

APPS = {}

class _SimpleClient:
    """Fallback client, same never-raises contract."""

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._token = (
            os.environ.get("ZYRA_API_TOKEN", "") or ""
        ).strip()

    def get(self, path: str):
        return self._call("GET", path)

    def post(self, path: str, payload: dict):
        return self._call("POST", path, payload)

    def _call(self, method, path, payload=None):
        if not self._base:
            return (False, None, "ZYRA_URL not configured")
        data = (
            json.dumps(payload).encode("utf-8")
            if payload is not None
            else None
        )
        try:
            headers = {"Content-Type": "application/json"}
            if self._token:
                headers["Authorization"] = "Bearer " + self._token
            request = urllib.request.Request(
                self._base + path,
                data=data,
                method=method,
                headers=headers,
            )
            with urllib.request.urlopen(request, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            if body.get("ok") is True:
                return (True, body.get("data"), None)
            error = body.get("error", {})
            return (False, None, str(error.get("message", "rejected")))
        except Exception as exc:
            return (False, None, str(exc))

def _db(name: str):
    from shared_engines.storage.database import SQLiteAdapter
    return SQLiteAdapter(
        str(DATA_DIR / name), busy_timeout_ms=10_000
    )

def _clock():
    from shared_engines.common.clocks import SystemClock
    return SystemClock()

def _start_mpe():
    from apps.mi_primer_empleo.infrastructure.persistence.mpe_store import MpeStore
    from apps.mi_primer_empleo.infrastructure.network.network_client import NetworkClient
    from apps.mi_primer_empleo.server import serve_mpe
    store = MpeStore(_db("mpe.db"), _clock())
    client = NetworkClient(ZYRA_URL)
    server = serve_mpe(store, client, host="127.0.0.1", port=0)
    return server, "Mi Primer Empleo"

def _start_agro():
    from apps.agro.infrastructure.persistence.agro_store import AgroStore
    from apps.agro.infrastructure.network.network_client import NetworkClient
    from apps.agro.server import serve_agro
    store = AgroStore(_db("agro.db"), _clock())
    client = NetworkClient(ZYRA_URL)
    server = serve_agro(store, client, host="127.0.0.1", port=0)
    return server, "AGRO"

def _start_axis():
    from apps.axis.infrastructure.persistence.axis_store import AxisStore
    from apps.axis.infrastructure.network.network_client import NetworkClient
    from apps.axis.life_history.integration import build_life_history
    from apps.axis.server import serve_axis
    db = _db("axis.db")
    clock = _clock()
    store = AxisStore(db, clock)
    client = NetworkClient(ZYRA_URL)
    lh = build_life_history(db=db, clock=clock, network_client=client)
    server = serve_axis(
        store, client, host="127.0.0.1", port=0,
        life_history_service=lh,
    )
    return server, "AXIS"

def _start_semilla():
    from apps.semilla.infrastructure.persistence.semilla_store import SemillaStore
    from apps.semilla.infrastructure.network.network_client import NetworkClient
    from apps.semilla.server import serve_semilla
    store = SemillaStore(_db("semilla.db"), _clock())
    client = NetworkClient(ZYRA_URL)
    server = serve_semilla(store, client, host="127.0.0.1", port=0)
    return server, "SEMILLA"

def _start_nexo():
    from apps.nexo.infrastructure.persistence.nexo_store import NexoStore
    from apps.nexo.infrastructure.network.network_client import NetworkClient
    from apps.nexo.server import serve_nexo
    store = NexoStore(_db("nexo.db"), _clock())
    client = NetworkClient(ZYRA_URL)
    server = serve_nexo(store, client, host="127.0.0.1", port=0)
    try:
        from apps.nexo.services.startup import attach_live_runtime as _ng_attach
        _ng_attach(server)
    except Exception:
        pass
    return server, "NEXO"

def _start_subastas():
    from apps.subastas.infrastructure.persistence.subastas_store import SubastasStore
    from apps.subastas.server import serve_subastas
    try:
        from apps.subastas.infrastructure.network.network_client import NetworkClient
        client = NetworkClient(ZYRA_URL)
    except Exception:
        client = _SimpleClient(ZYRA_URL)
    store = SubastasStore(_db("subastas.db"), _clock())
    server = serve_subastas(store, client, host="127.0.0.1", port=0)
    return server, "SUBASTAS"

def _start_ciclo():
    from apps.ciclo_digital.infrastructure.persistence.ciclo_store import CicloStore
    from apps.ciclo_digital.infrastructure.network.network_client import NetworkClient
    from apps.ciclo_digital.server import serve_ciclo
    store = CicloStore(_db("ciclo.db"), _clock())
    client = NetworkClient(ZYRA_URL)
    server = serve_ciclo(store, client, host="127.0.0.1", port=0)
    return server, "CICLO-DIGITAL"

def _start_laboratorio():
    from apps.laboratorio.infrastructure.api.app import montar_aplicacion
    app_lab = montar_aplicacion(str(DATA_DIR / "laboratorio.db"))

    class _ManejadorLab(BaseHTTPRequestHandler):
        def _atender(self):
            largo = int(self.headers.get("Content-Length", 0) or 0)
            cuerpo = self.rfile.read(largo) if largo else b""
            status, headers_out, salida = app_lab.despachar(
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

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _ManejadorLab)
    return servidor, "LABORATORIO"

STARTERS = [
    ("/mpe", _start_mpe),
    ("/agro", _start_agro),
    ("/axis", _start_axis),
    ("/semilla", _start_semilla),
    ("/nexo", _start_nexo),
    ("/subastas", _start_subastas),
    ("/ciclo", _start_ciclo),
    ("/laboratorio", _start_laboratorio),
]

def boot_apps():
    errors = []
    for prefix, starter in STARTERS:
        try:
            server, label = starter()
            port = int(server.server_address[1])
            threading.Thread(
                target=server.serve_forever, daemon=True
            ).start()
            APPS[prefix] = {"port": port, "label": label}
            print(
                "[superapp] " + label + " up on 127.0.0.1:"
                + str(port) + " at " + prefix + "/*"
            )
        except Exception as exc:
            errors.append(prefix + ": " + str(exc))
            print("[superapp] " + prefix + " FAILED: " + str(exc))
    return errors

ERROR_PAGE = (
    "<html><head><meta charset='utf-8'>"
    "<title>ZYRA</title></head>"
    "<body style='font-family:sans-serif;background:#0d1117;"
    "color:#e6edf3;padding:32px'>"
    "<h1>ZYRA</h1><p>__MSG__</p>"
    "<p><a href='/' style='color:#8b949e'>Volver al portal</a></p>"
    "</body></html>"
)

NOT_FOUND_PAGE = ERROR_PAGE.replace("__MSG__", "Ruta desconocida.")

class PortalHandler(BaseHTTPRequestHandler):
    server_version = "ZYRA-SuperApp/1.0"

    def _send(self, status, content_type, payload):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, status, html):
        self._send(
            status, "text/html; charset=utf-8",
            html.encode("utf-8"),
        )

    def _read_portal(self, name):
        return (ROOT / "portal" / name).read_bytes()

    def _sesion(self):
        cruda = self.headers.get("Cookie", "") or ""
        for parte in cruda.split(";"):
            if "=" in parte:
                k, v = parte.split("=", 1)
                if k.strip() == "zyra_zid":
                    return v.strip()
        return None

    def _pagina_entrar(self, mensaje):
        aviso = ""
        if mensaje:
            aviso = "<p style='color:#f85149'>" + mensaje + "</p>"
        html = (
            "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Entrar a ZYRA</title>"
            "<style>body{font-family:system-ui,sans-serif;background:#0d1117;"
            "color:#e6edf3;max-width:520px;margin:0 auto;padding:32px 16px}"
            "input,button{width:100%;padding:12px;margin:6px 0;border-radius:8px;"
            "border:1px solid #30363d;background:#161b22;color:#e6edf3;"
            "box-sizing:border-box;font-size:16px}"
            "button{background:#238636;border:none;font-weight:700}"
            "</style></head><body>"
            "<h1>Entrar a ZYRA</h1>"
            + aviso +
            "<form method='POST' action='/entrar'>"
            "<input name='zid' placeholder='Tu ZID' required>"
            "<input name='clave' type='password' placeholder='Tu clave'>"
            "<button>Entrar</button></form>"
            "<p><a href='/' style='color:#8b949e'>Volver al portal</a></p>"
            "</body></html>"
        )
        return html

    def _proxy(self, target):
        length = int(
            self.headers.get("Content-Length", 0) or 0
        )
        body = self.rfile.read(length) if length > 0 else None
        headers = {}
        zid_s = self._sesion()
        if zid_s:
            headers["x-zyra-zid"] = zid_s
            ruta_obj = (self.path or "").split("?", 1)[0]
            if ruta_obj.startswith("/laboratorio"):
                if zid_s == os.environ.get("ZYRA_OWNER_ZID", "Z-OWNER-ALFONSZELAYA"):
                    headers["x-zyra-roles"] = os.environ.get(
                        "ZYRA_ROLES_DUENO", "LAB_GOBERNADOR")
                else:
                    headers["x-zyra-roles"] = "LAB_ESPECTADOR"
        ct = self.headers.get("Content-Type")
        if ct:
            headers["Content-Type"] = ct
        request = urllib.request.Request(
            target, data=body, method=self.command,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as resp:
                payload = resp.read()
                self._send(
                    resp.status,
                    resp.headers.get(
                        "Content-Type",
                        "text/html; charset=utf-8",
                    ),
                    payload,
                )
        except urllib.error.HTTPError as exc:
            try:
                payload = exc.read()
            except Exception:
                payload = b""
            ct2 = (
                exc.headers.get(
                    "Content-Type",
                    "text/html; charset=utf-8",
                )
                if exc.headers
                else "text/html; charset=utf-8"
            )
            self._send(exc.code, ct2, payload)
        except Exception as exc:
            self._send_html(
                502,
                ERROR_PAGE.replace(
                    "__MSG__",
                    "La app no esta disponible ahora: " + str(exc),
                ),
            )

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            base = self._read_portal("index.html").decode("utf-8")
            zid_s = self._sesion()
            if zid_s:
                estado = (
                    '<p class="estado ok">Conectado: ' + zid_s
                    + ' &middot; <a href="/salir" style="color:#f85149">Salir</a></p>')
                DESCRIPCIONES = {
                    "/mpe": "Empleos, propuestas y credenciales laborales",
                    "/agro": "Productores, ayudas y precios justos",
                    "/axis": "Salud, justicia y seguridad",
                    "/semilla": "Educacion con historial verificado",
                    "/nexo": "Nucleo contable y fiscal",
                    "/subastas": "Marketplace con confianza",
                    "/ciclo": "Reciclaje y arqueologia",
                    "/laboratorio": "Experimentos, simulaciones y proyecciones",
                }
                tarjetas = ""
                for _pref, _inf in APPS.items():
                    _ic = "/icon-app" + _pref.replace("/", "-") + ".png"
                    _desc = DESCRIPCIONES.get(_pref, "Abrir aplicacion")
                    tarjetas += (
                        '<a class="opcion" href="' + _pref + '/">'
                        + '<div style="display:flex;align-items:center;gap:16px">'
                        + '<img src="' + _ic + '" alt="" style="width:60px;height:60px;border-radius:16px;flex-shrink:0">'
                        + '<div><b style="font-size:20px">' + _inf["label"] + '</b>'
                        + '<span style="display:block;font-size:13px;color:#8b949e;margin-top:3px">' + _desc + '</span></div>'
                        + '</div></a>')
                seccion = (
                    '<div class="menu">' + tarjetas + '</div>'
                    + '<p class="tag" style="margin-top:22px;margin-bottom:8px">Verificador publico</p>'
                    + '<div class="menu">'
                    + '<a class="opcion" href="/verificar"><b style="font-size:19px">Verificar</b>'
                    + '<span>Confirma la autenticidad de un documento</span></a>'
                    + '</div>')
                i1 = base.find('<div class="menu">')
                i2 = base.find('</div>', i1) + len('</div>')
                base = base[:i1] + seccion + base[i2:]
                base = base.replace('.opcion{display:flex;flex-direction:column;gap:2px;text-decoration:none;background:#11162b;',
                    '.opcion{display:block;text-decoration:none;background:#11162b;')
            else:
                estado = ""
            base = base.replace("__ESTADO__", estado, 1)
            self._send_html(200, base)
            return

        if path == "/inicio":
            try:
                d_i = self._read_portal("inicio.html")
            except Exception:
                d_i = b"<html><body></body></html>"
            self._send(200, "text/html; charset=utf-8", d_i)
            return

        if path == "/registro":
            _reg_html = '''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ZYRA - Crear mi ZID</title>
<script src="https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,Arial;background:#12162e;color:#e8eaf6;padding:16px;max-width:520px;margin:0 auto}
h1{font-size:22px;text-align:center;margin:8px 0 4px;color:#fff}
.sub{text-align:center;color:#9aa0c3;font-size:13px;margin-bottom:8px}
.prog{text-align:center;color:#7c8cf8;font-weight:800;font-size:13px;margin-bottom:12px;letter-spacing:1px}
.paso{display:none}
.paso.act{display:block}
label{display:block;color:#9aa0c3;font-size:14px;margin:14px 0 6px}
input,select{width:100%;padding:12px;border-radius:10px;border:1px solid #2a2f55;background:#0d1126;color:#fff;font-size:16px}
.estado{text-align:center;font-size:13px;color:#9aa0c3;padding:6px;min-height:20px}
.preview{display:none;width:100%;max-width:330px;border-radius:10px;margin:6px auto 0;border:1px solid #2a2f55}
button{width:100%;margin-top:10px;padding:13px;border:0;border-radius:10px;font-size:15px;font-weight:700;color:#fff;background:#262b52}
button.ok{background:#1f6f43}
button.big{margin-top:16px;padding:15px;font-size:16px;font-weight:800;background:linear-gradient(90deg,#7c5cff,#ff5c8a)}
button:disabled{opacity:.45}
.mini{background:none;color:#a78bfa;font-size:13px;padding:8px;width:auto;margin:4px auto;display:block;border:none;cursor:pointer}
.videozona{display:none;position:relative;border-radius:12px;overflow:hidden;margin-top:8px;margin-left:auto;margin-right:auto;background:#000;max-width:330px;border:1px solid #2a2f55;box-shadow:0 6px 24px rgba(0,0,0,0.5)}
video{width:100%;display:block}
.ov{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none}
a{color:#a78bfa}
#desglose{margin-top:14px;font-size:13px}
#resp{margin-top:14px}
#jserr{display:none;background:#2a1414;border:1px solid #f85149;color:#f85149;border-radius:10px;padding:10px;margin-top:10px;font-size:12px;word-break:break-all}
.zid{font-size:20px;font-weight:800;color:#3fb950;letter-spacing:1px}
.chk{color:#3fb950!important;font-weight:700}
.mal{color:#f85149!important}
.titulopaso{font-size:17px;font-weight:800;color:#fff;text-align:center;margin-bottom:6px}
.bloc{background:#2a1414;border:1px solid #f85149;color:#f85149;border-radius:10px;padding:10px;margin-top:8px;font-weight:700;text-align:center}
</style>
</head>
<body>
<h1>Crear mi ZID</h1>
<p class="sub">Red de confianza digital</p>
<div class="prog" id="prog">PASO 1 DE 5</div>
<form onsubmit="return enviar(event)">
<div class="paso act" id="ps1">
<label>Nombre completo (1 o 2 nombres y 1 o 2 apellidos)</label>
<input id="nombre" autocomplete="name">
<label>Tipo de documento legal</label>
<select id="tipoDoc">
<option value="dui">DUI El Salvador (2 lados)</option>
<option value="pasaporte">Pasaporte (1 lado)</option>
<option value="licencia">Licencia de conducir (2 lados)</option>
<option value="id_usa">ID de estado / EAD USA (2 lados)</option>
<option value="permiso">Permiso legal / otro documento</option>
</select>
<button type="button" class="big" onclick="irDe1()">Continuar</button>
</div>
<div class="paso" id="ps2">
<div class="titulopaso">PASO 2: LADO FRONTAL (la cara con tu foto)</div>
<div class="videozona" id="vzF"><video id="vdF" autoplay playsinline muted></video><canvas class="ov" id="ovF"></canvas></div>
<div class="estado" id="stF">Pulsa ABRIR CAMARA. La primera vez carga el escaner (~10 seg), luego es instantaneo.</div>
<button type="button" class="big" id="bAbrirF" onclick="abrirCamF()">ABRIR CAMARA</button>
<button type="button" class="ok" id="bCapF" style="display:none" onclick="capturarF()">CAPTURAR FOTO</button>
<input type="file" id="galF" accept="image/*" style="display:none" onchange="desdeArchivo(this,'F')">
<button type="button" class="mini" onclick="R('galF').click()">o elegir archivo existente</button>
<img class="preview" id="pF" alt="" onclick="rehacer('F')">
<div id="blocF"></div>
<button type="button" class="mini" onclick="irAPaso(1)">Volver</button>
</div>
<div class="paso" id="ps3">
<div class="titulopaso">PASO 3: LADO DE ATRAS (REVERSO)</div>
<div class="videozona" id="vzA"><video id="vdA" autoplay playsinline muted></video><canvas class="ov" id="ovA"></canvas></div>
<div class="estado" id="stA">Pulsa ABRIR CAMARA. El escaner buscara las 4 esquinas del documento.</div>
<button type="button" class="big" id="bAbrirA" onclick="abrirCamA()">ABRIR CAMARA</button>
<button type="button" class="ok" id="bCapA" style="display:none" onclick="capturarA()">CAPTURAR FOTO</button>
<input type="file" id="galA" accept="image/*" style="display:none" onchange="desdeArchivo(this,'A')">
<button type="button" class="mini" onclick="R('galA').click()">o elegir archivo existente</button>
<img class="preview" id="pA" alt="" onclick="rehacer('A')">
<div id="blocA"></div>
<div class="estado" id="notaRev"></div>
<button type="button" class="ok" id="bIr4" disabled onclick="irAPaso(4)">Continuar</button>
<button type="button" class="mini" onclick="saltarReverso()">Mi documento no tiene reverso: continuar sin el</button>
<button type="button" class="mini" onclick="irAPaso(2)">Volver</button>
</div>
<div class="paso" id="ps4">
<div class="titulopaso">PASO 4: BIOMETRIA — tu rostro en vivo</div>
<div class="videozona" id="vzS"><video id="v" autoplay playsinline muted style="transform:scaleX(-1)"></video><canvas class="ov" id="ovS"></canvas></div>
<div class="estado" id="stProv">Motor de deteccion: preparando...</div>
<div class="estado" id="stV">Pulsa ABRIR CAMARA</div>
<button type="button" class="big" id="bAbrirCam" onclick="abrirCamara()">ABRIR CAMARA</button>
<button type="button" class="ok" id="bSelfie" style="display:none" onclick="capturarSelfie()">CAPTURAR SELFIE</button>
<button type="button" id="bRepSelfie" style="display:none" onclick="abrirCamara()">REPETIR SELFIE</button>
<img class="preview" id="pS" alt="">
<div id="blocS"></div>
<button type="button" class="ok" id="bIr5" style="display:none" onclick="irAPaso(5)">Continuar</button>
<button type="button" class="mini" onclick="irAPaso(3)">Volver</button>
</div>
<div class="paso" id="ps5">
<label>8) Crea tu clave de acceso (min 8)</label>
<input type="password" id="clave">
<label>Repite la clave</label>
<input type="password" id="clave2">
<button class="big" type="submit">Crear mi ZID</button>
<button type="button" class="mini" onclick="irAPaso(4)">Volver</button>
</div>
<div id="desglose"></div>
<div id="jserr"></div>
<div id="resp"></div>
</form>
<p style="text-align:center;margin-top:14px"><a href="/">Volver</a> | <a href="/entrar">Ya tengo ZID</a></p>
<p style="text-align:center;color:#4a4f7a;font-size:11px;margin-top:10px">ZYRA registro v37 - control de nombre + captura compacta</p>
<script>
window.onerror=function(m,u,l){try{var b=document.getElementById("jserr");if(b){b.style.display="block";b.innerHTML="Error interno (linea "+l+"): "+m}}catch(e){}};
var DF="",DA="",DS="";
var datosDocF=null,datosDocA=null;
var minorBloqueado=false,docVencido=false,nombreNoCoincide=false,bioRechazada=false;
var camF=null,camA=null,cam=null,cara=null,alineado=false,detTipo="",apiCara=null,mpDetector=null,capturando=false;
var promesaCara=null,faListo=false;
var ivF=null,ivA=null,quadF=null,quadA=null,ocvListo=false;
function R(id){return document.getElementById(id)}
function kb(s){return Math.round(s.length*3/4/1024)}
function dormir(ms){return new Promise(function(res){setTimeout(res,ms)})}
function partesNombre(v){return (v||"").trim().split(/\s+/).filter(function(x){return x.length>1})}
function propIdeal(){return R("tipoDoc").value=="pasaporte"?1.41:1.586}
function saveSes(){try{sessionStorage.setItem("zyraReg",JSON.stringify({DF:DF,DA:DA,DS:DS,nm:R("nombre").value,td:R("tipoDoc").value,paso:(document.querySelector(".paso.act")||{}).id}))}catch(e){}}
function loadSes(){try{var s=sessionStorage.getItem("zyraReg");if(!s)return null;return JSON.parse(s)}catch(e){return null}}
function zyComprimir(dataUrl,maxLado,calidad){return new Promise(function(res){var im=new Image();im.onload=function(){var w=im.width,h=im.height,e=Math.min(1,maxLado/Math.max(w,h)),c=document.createElement("canvas");c.width=Math.round(w*e);c.height=Math.round(h*e);c.getContext("2d").drawImage(im,0,0,c.width,c.height);res(c.toDataURL("image/jpeg",calidad).split(",").pop())};im.onerror=function(){res(dataUrl.split(",").pop())};im.src=dataUrl})}
function luma(dataUrl){return new Promise(function(res){var im=new Image();im.onload=function(){var c=document.createElement("canvas");c.width=40;c.height=40;c.getContext("2d").drawImage(im,0,0,40,40);var d=c.getContext("2d").getImageData(0,0,40,40).data,t=0;for(var i=0;i<d.length;i+=4){t+=0.299*d[i]+0.587*d[i+1]+0.114*d[i+2]}res(t/(d.length/4))};im.onerror=function(){res(99)};im.src=dataUrl})}
function cargarScript(s){return new Promise(function(res,rej){var e=document.createElement("script");e.src=s;e.onload=res;e.onerror=rej;document.head.appendChild(e)})}
function setProv(t){var e=R("stProv");if(e)e.innerHTML="Motor de deteccion: "+t}
function conTimeout(p,ms,msg){return Promise.race([p,dormir(ms).then(function(){throw new Error(msg)})])}
function cargarOpenCV(){
if(window.cv&&window.cv.Mat)return Promise.resolve();
return new Promise(function(res,rej){
if(!document.getElementById("ocvjs")){
var s=document.createElement("script");
s.id="ocvjs";s.src="https://docs.opencv.org/4.9.0/opencv.js";
s.onerror=function(){rej(new Error("no cargo opencv"))};
document.head.appendChild(s);
}
var iv=setInterval(function(){
if(window.cv&&window.cv.Mat){clearInterval(iv);res()}
},120);
setTimeout(function(){clearInterval(iv);rej(new Error("opencv timeout"))},60000);
});
}
function ensureCara(){
if(detTipo)return Promise.resolve(detTipo);
if(!promesaCara){
promesaCara=(async function(){
try{
await cargarScript("https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js");
await faceapi.nets.tinyFaceDetector.loadFromUri("https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@0.22.2/weights");
try{await faceapi.nets.faceLandmark68TinyNet.loadFromUri("https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@0.22.2/weights");await faceapi.nets.faceRecognitionNet.loadFromUri("https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@0.22.2/weights");faListo=true}catch(e2){}
detTipo="faceapi";setProv("face-api.js"+(faListo?" (con comparador)":""));
return detTipo;
}catch(e3){}
try{
var m=await import("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs");
var fs=await m.FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm");
var dels=["GPU","CPU"];
for(var i=0;i<dels.length;i++){
try{
mpDetector=await m.FaceDetector.createFromOptions(fs,{baseOptions:{modelAssetPath:"https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",delegate:dels[i]},runningMode:"IMAGE",minDetectionConfidence:0.25});
detTipo="mediapipe";setProv("MediaPipe (Google, "+dels[i]+")");return detTipo;
}catch(e4){}
}
}catch(e5){}
try{if(window.FaceDetector){apiCara=new FaceDetector({fastMode:true,maxDetectedFaces:1});detTipo="nativo";setProv("nativo del navegador");return detTipo}}catch(e6){}
setProv("NO disponible");return "";
})();
}
return promesaCara;
}
function cajaMP(fuente){
try{
var res=mpDetector.detect(fuente);
if(res&&res.detections&&res.detections.length){
var b=res.detections[0].boundingBox;
return {x:b.originX,y:b.originY,w:b.width,h:b.height};
}
}catch(e){}
return null;
}
async function cajaEnVideo(v){
var t=await ensureCara();if(!t)return null;
try{
if(t=="faceapi"){
var r=await faceapi.detectSingleFace(v,new faceapi.TinyFaceDetectorOptions({inputSize:320,scoreThreshold:0.3}));
if(r){return {x:r.box.x,y:r.box.y,w:r.box.width,h:r.box.height}}
return null;
}
if(t=="mediapipe")return cajaMP(v);
if(t=="nativo"){var fs2=await apiCara.detect(v);if(fs2.length){var b4=fs2[0].boundingBox;return {x:b4.x,y:b4.y,w:b4.width,h:b4.height}}}
}catch(e){}
return null;
}
async function rostroEnImagen(dataUrl){
try{
var im=new Image();
var ok=await new Promise(function(res){im.onload=function(){res(true)};im.onerror=function(){res(false)};im.src="data:image/jpeg;base64,"+dataUrl});
if(!ok)return null;
var sc=Math.min(1,800/Math.max(im.width,im.height));
var c=document.createElement("canvas");
c.width=Math.round(im.width*sc);c.height=Math.round(im.height*sc);
c.getContext("2d").drawImage(im,0,0,c.width,c.height);
var t=await ensureCara();
if(t=="faceapi"){
var r=await faceapi.detectSingleFace(c,new faceapi.TinyFaceDetectorOptions({inputSize:416,scoreThreshold:0.35}));
return r?{x:r.box.x/sc,y:r.box.y/sc,w:r.box.width/sc,h:r.box.height/sc}:null;
}
if(t=="mediapipe"){
var b=cajaMP(c);
if(b)return {x:b.x/sc,y:b.y/sc,w:b.w/sc,h:b.h/sc};
}
if(t=="nativo"){var fs3=await apiCara.detect(c);if(fs3.length){var b5=fs3[0].boundingBox;return {x:b5.x/sc,y:b5.y/sc,w:b5.width/sc,h:b5.height/sc}}}
}catch(e){}
return null;
}
function edadDe(iso){try{var f=new Date(iso+"T00:00:00");if(isNaN(f))return -1;var h=new Date();var e=h.getFullYear()-f.getFullYear();var m=h.getMonth()-f.getMonth();if(m<0||(m===0&&h.getDate()<f.getDate()))e--;return e}catch(e){return -1}}
function nombresCoinciden(a,b){
try{
a=(a||"").toLowerCase().replace(/[^a-z ]/g," ").split(/\s+/).filter(function(x){return x.length>2});
b=(b||"").toLowerCase().replace(/[^a-z ]/g," ").split(/\s+/).filter(function(x){return x.length>2});
if(!a.length||!b.length)return true;
var hit=0;
for(var i=0;i<a.length;i++){if(b.indexOf(a[i])>=0)hit++}
return hit>=1;
}catch(e){return true}
}
function parseAAMVA(raw){
try{
var claves=["DAB","DAC","DAD","DCS","DBB","DBA","DAQ","DAG","DAI","DAJ","DAK","DCF","DAU"];
var fnd=[];
for(var c=0;c<claves.length;c++){
var ix=raw.indexOf(claves[c]);
while(ix>=0){fnd.push([ix,claves[c]]);ix=raw.indexOf(claves[c],ix+1)}
}
fnd.sort(function(a,b){return a[0]-b[0]});
if(fnd.length<3)return null;
var res={};
for(var i=0;i<fnd.length;i++){
var fin=(i+1<fnd.length)?fnd[i+1][0]:Math.min(fnd[i][0]+70,raw.length);
var valor=raw.slice(fnd[i][0]+3,fin).split(String.fromCharCode(10))[0].trim();
res[fnd[i][1]]=valor;
}
var nac="",venc="";
if(res.DBB&&res.DBB.length===8)nac=res.DBB.slice(4,8)+"-"+res.DBB.slice(0,2)+"-"+res.DBB.slice(2,4);
if(res.DBA&&res.DBA.length===8)venc=res.DBA.slice(4,8)+"-"+res.DBA.slice(0,2)+"-"+res.DBA.slice(2,4);
var nombre=((res.DAC||"")+" "+(res.DAD||"")+" "+(res.DCS||res.DAB||"")).trim();
return {nombre:(nombre&&nombre.length>3)?nombre:null,nacimiento:nac,edad:(nac?edadDe(nac):-1),numero:(res.DAQ||res.DCF||""),direccion:((res.DAI||"")+" "+(res.DAG||"")+" "+(res.DAJ||"")+" "+(res.DAK||"")).trim(),vencimiento:venc,confiable:true};
}catch(e){return null}
}
function fechasDeTexto(t){
var venc="",nac="";
var T=t.toUpperCase();
var lineas=T.split(String.fromCharCode(10));
for(var i=0;i<lineas.length;i++){
var LN=lineas[i];
var tieneVenc=(LN.indexOf("EXP")>=0||LN.indexOf("VENC")>=0||LN.indexOf("CADU")>=0);
var tieneNac=(LN.indexOf("NACIMIENTO")>=0||LN.indexOf("BIRTH")>=0||LN.indexOf("DOB")>=0);
if(!tieneVenc&&!tieneNac)continue;
var ventana=LN;
for(var w=1;w<=2;w++){if(lineas[i+w])ventana=ventana+" "+lineas[i+w]}
var mfechas=ventana.match(/(\d{1,2})[\/\.\-](\d{1,2})[\/\.\-](\d{4})/g);
if(!mfechas)continue;
var p=mfechas[0].split(/[\/\.\-]/);
var iso=p[2]+"-"+("0"+p[1]).slice(-2)+"-"+("0"+p[0]).slice(-2);
if(tieneVenc&&!venc)venc=iso;
if(tieneNac&&!nac)nac=iso;
}
return {vencimiento:venc,nacimiento:nac};
}

function nombreDeTexto(t){
try{
var T=t.toUpperCase();
var etiquetas=["GIVEN NAME","NOMBRES","NOMBRE /"];
var idx=-1,usada="";
for(var e2=0;e2<etiquetas.length;e2++){
var ix2=T.indexOf(etiquetas[e2]);
if(ix2>=0){idx=ix2;usada=etiquetas[e2];break}
}
if(idx<0)return null;
var misma=T.substring(idx+usada.length);
var finL=misma.indexOf(String.fromCharCode(10));
var enMisma=(finL>=0?misma.substring(0,finL):misma).replace(/[^A-Z ]/g," ").trim();
var cand=[];
var pp1=enMisma.split(/\s+/).filter(function(x){return x.length>2});
if(pp1.length>=1)cand.push(pp1.join(" "));
if(!cand.length){
var resto=(finL>=0?misma.substring(finL):"");
var ls=resto.split(String.fromCharCode(10));
for(var k=0;k<ls.length&&k<3;k++){
var cln=ls[k].replace(/[^A-Z ]/g," ").trim();
var pp=cln.split(/\s+/).filter(function(x){return x.length>2});
if(pp.length>=1){cand.push(pp.join(" "));break}
}
}
if(cand.length){var nm=cand.join(" ");return (nm.length>3)?nm:null}
return null;
}catch(e){return null}
}

async function ocrPatrones(dataUrl){
try{
if(!window.Tesseract)return null;
var ret=await conTimeout(Tesseract.recognize("data:image/jpeg;base64,"+dataUrl,"eng"),25000,"ocr lento");
var t=(ret&&ret.data&&ret.data.text)?ret.data.text:"";
if(t.length<15)return null;
var TU=t.toUpperCase();
var esReverso=(TU.indexOf("IDSLV")>=0)||(TU.indexOf("<<<<")>=0);
var esFrontalTexto=(TU.indexOf("IDENTIDAD")>=0)||(TU.indexOf("IDENTIFICATION")>=0);
var fe=fechasDeTexto(t);
var nm=nombreDeTexto(t);
return {esReverso:esReverso,esFrontalTexto:esFrontalTexto,vencimiento:fe.vencimiento,nacimiento:fe.nacimiento,nombre:nm,texto:TU.trim().substring(0,300)};
}catch(e){return null}
}
async function leerCodigoDeCanvas(cv){
try{
if(window.BarcodeDetector){
var bd=new BarcodeDetector({formats:["pdf417","qr_code","code_128","code_39"]});
var fs=await bd.detect(cv);
if(fs&&fs.length){var rv=fs[0].rawValue||"";if(rv.length>20)return parseAAMVA(rv)}
}
}catch(e){}
return null;
}
async function leerCodigo(dataUrl){
try{
var im=new Image();
var ok=await new Promise(function(res){im.onload=function(){res(true)};im.onerror=function(){res(false)};im.src="data:image/jpeg;base64,"+dataUrl});
if(!ok)return null;
var cv=document.createElement("canvas");cv.width=im.width;cv.height=im.height;
cv.getContext("2d").drawImage(im,0,0);
var d1=await leerCodigoDeCanvas(cv);
if(d1)return d1;
var cv2=document.createElement("canvas");
cv2.width=Math.round(im.width/2);cv2.height=Math.round(im.height/2);
cv2.getContext("2d").drawImage(im,0,0,cv2.width,cv2.height);
return await leerCodigoDeCanvas(cv2);
}catch(e){}
return null;
}
async function clasificarLado(comp){
var rostro=await rostroEnImagen(comp);
var ocr=null;
try{ocr=await conTimeout(ocrPatrones(comp),25000,"lectura lenta")}catch(e1){}
var cod=await leerCodigo(comp);
var fuente=cod||null;
var esFrontal=null,motivo="";
if(rostro){esFrontal=true;motivo="rostro del titular visible"}
else if(cod){esFrontal=false;motivo="codigo de barras detectado"}
else if(ocr&&ocr.esReverso){esFrontal=false;motivo="zona MRZ leida"}
else if(ocr&&ocr.esFrontalTexto){esFrontal=true;motivo="encabezado del frontal"}
else{motivo="no se pudo identificar el lado: repite con buena luz y el documento llenando el recuadro"}
return {esFrontal:esFrontal,motivo:motivo,rostro:rostro,codigo:fuente,ocr:ocr};
}
function irAPaso(n){
var i;
for(i=1;i<=5;i++){var e=R("ps"+i);if(e)e.className="paso"+(i==n?" act":"")}
R("prog").innerHTML="PASO "+n+" DE 5";
stopCamF();stopCamA();stopCam();
if(n==2){R("stF").innerHTML=DF?("LADO FRONTAL guardado ("+kb(DF)+" KB) — toca la foto para rehacer"):"Pulsa ABRIR CAMARA: el recuadro verde buscara las esquinas del documento.";}
if(n==3){
var t=R("tipoDoc").value;
R("stA").innerHTML=DA?("LADO REVERSO guardado ("+kb(DA)+" KB) — toca la foto para rehacer"):"Pulsa ABRIR CAMARA: el recuadro verde buscara las esquinas.";
if(t=="pasaporte"){R("notaRev").innerHTML="Pasaporte: no tiene reverso. Continua.";R("notaRev").className="estado chk";R("bIr4").disabled=false}
else if(t=="permiso"){R("notaRev").innerHTML="Si tu permiso tiene reverso, tomale foto. Si no, usa el boton de abajo.";R("notaRev").className="estado";R("bIr4").disabled=!DA}
else{R("notaRev").innerHTML="Este documento SI requiere reverso.";R("notaRev").className="estado";R("bIr4").disabled=!DA}
}
saveSes();
window.scrollTo(0,0);
}
function saltarReverso(){
DA="";datosDocA=null;R("stA").innerHTML="";R("pA").style.display="none";
irAPaso(4);
}
function irDe1(){
var nm=R("nombre").value.trim();
var ps=partesNombre(nm);
if(nm.length<3||ps.length<2){R("resp").innerHTML="<p style='color:#f85149'>Escribe tu nombre y apellido (1 o 2 de cada uno).</p>";window.scrollTo(0,document.body.scrollHeight);return}
R("resp").innerHTML="";
irAPaso(2);
}
function mostrarDesglose(){
var d=R("desglose");if(!d)return;
var h="";var nom=R("nombre").value.trim();
minorBloqueado=false;docVencido=false;nombreNoCoincide=false;
var fuenteF=datosDocF,fuenteA=datosDocA;
if(!fuenteF&&!fuenteA){
h="<p style='color:#9aa0c3'>Sin datos automaticos legibles. El motor verificara tu rostro contra el documento.</p>";
d.innerHTML=h;return;
}
if(fuenteF){
if(fuenteF.confiable&&fuenteF.nombre){
h+="<p style='color:#3fb950'>FRONTAL (leido): "+fuenteF.nombre+" | Nac: "+(fuenteF.nacimiento||"?")+" | Edad: "+fuenteF.edad+"</p>";
if(nom.length>=3&&!nombresCoinciden(fuenteF.nombre,nom)){nombreNoCoincide=true;h+="<p style='color:#f85149;font-weight:700'>NO COINCIDE: el nombre escrito difiere del documento. Corrigelo.</p>";}
else{h+="<p style='color:#3fb950'>Cruce de nombre: coincide</p>";}
}
}
var venc="";
if(fuenteA&&fuenteA.vencimiento)venc=fuenteA.vencimiento;
if(!venc&&fuenteF&&fuenteF.vencimiento)venc=fuenteF.vencimiento;
if(venc){
var hoy=new Date();hoy.setHours(0,0,0,0);
var fvd=new Date(venc+"T00:00:00");
if(fvd&&fvd<hoy){docVencido=true;h+="<p style='color:#f85149;font-weight:700'>DOCUMENTO VENCIDO ("+venc+"): NO SE ACEPTA.</p>";}
else{h+="<p style='color:#3fb950'>Vencimiento: "+venc+" — valido</p>";}
}
if(fuenteF&&fuenteF.nacimiento){
var ed2=edadDe(fuenteF.nacimiento);
if(ed2>=0&&ed2<18){minorBloqueado=true;h+="<p style='color:#f85149;font-weight:700'>MENOR DE EDAD ("+ed2+"): se registra con tutor.</p>";}
}
if(fuenteA){
var pa=[];
if(fuenteA.numero)pa.push("No.: "+fuenteA.numero);
if(fuenteA.direccion)pa.push("Dir: "+fuenteA.direccion);
if(pa.length)h+="<p style='color:#3fb950'>REVERSO: "+pa.join(" | ")+"</p>";
}
if(fuenteF&&fuenteF.texto){h+="<p style='color:#7c8cf8'>OCR: "+fuenteF.texto.split("<").join("&lt;")+"</p>";}
d.innerHTML=h;
}
function bloquear(lado,mensaje){
var b=R("bloc"+lado);
if(b){b.className="bloc";b.innerHTML=mensaje}
}
function limpiarBloc(lado){
var b=R("bloc"+lado);
if(b){b.innerHTML=""}
}
function aplicarFiltros(lado){
if(lado=="F"){limpiarBloc("F");limpiarBloc("A")}
var f=datosDocF;
if(f){
if(f.confiable&&f.nombre){
var nom=R("nombre").value.trim();
if(nom.length>=3&&!nombresCoinciden(f.nombre,nom)){
nombreNoCoincide=true;
bloquear("F","BLOQUEADO: el nombre escrito no coincide con el documento. Corrigelo y vuelve a guardar.");
return false;
}
}
var venc=(datosDocA&&datosDocA.vencimiento)||(f.vencimiento)||"";
if(venc){
var hoy=new Date();hoy.setHours(0,0,0,0);
var fvd=new Date(venc+"T00:00:00");
if(fvd&&fvd<hoy){
docVencido=true;
bloquear(lado,"BLOQUEADO: DOCUMENTO VENCIDO ("+venc+"). NO puedes continuar.");
return false;
}
}
if(f.nacimiento){
var ed2=edadDe(f.nacimiento);
if(ed2>=0&&ed2<18){
minorBloqueado=true;
bloquear(lado,"BLOQUEADO: MENOR DE EDAD ("+ed2+"). Los menores se registran con tutor.");
return false;
}
}
}
return true;
}
function cargarOpenCV(){
if(window.cv&&window.cv.Mat)return Promise.resolve();
return new Promise(function(res,rej){
if(!document.getElementById("ocvjs")){
var s=document.createElement("script");
s.id="ocvjs";s.src="https://docs.opencv.org/4.9.0/opencv.js";
s.onerror=function(){rej(new Error("no cargo opencv"))};
document.head.appendChild(s);
}
var iv=setInterval(function(){
if(window.cv&&window.cv.Mat){clearInterval(iv);res()}
},120);
setTimeout(function(){clearInterval(iv);rej(new Error("opencv timeout"))},60000);
});
}
function ordenarPts(pts){
pts.sort(function(a,b){return a.y-b.y});
var t=pts.slice(0,2),b2=pts.slice(2);
t.sort(function(a,b){return a.x-b.x});
b2.sort(function(a,b){return a.x-b.x});
return {tl:t[0],tr:t[1],br:b2[1],bl:b2[0]};
}
function detectarQuadPro(vid){
if(!window.cv||!window.cv.Mat)return null;
var v=R(vid);
if(!v.videoWidth)return null;
var SW=320;
var sc=Math.min(1,SW/v.videoWidth);
var cw=Math.round(v.videoWidth*sc),ch=Math.round(v.videoHeight*sc);
var c=document.createElement("canvas");c.width=cw;c.height=ch;
c.getContext("2d").drawImage(v,0,0,cw,ch);
var src=cv.imread(c);
var gray=new cv.Mat(),blur=new cv.Mat(),edg=new cv.Mat();
cv.cvtColor(src,gray,cv.COLOR_RGBA2GRAY);
cv.GaussianBlur(gray,blur,new cv.Size(5,5),0);
cv.Canny(blur,edg,50,150);
try{cv.dilate(edg,edg,new cv.Mat(),new cv.Point(-1,-1),2)}catch(e){}
var cont=new cv.MatVector(),hier=new cv.Mat();
cv.findContours(edg,cont,hier,cv.RETR_LIST,cv.CHAIN_APPROX_SIMPLE);
var best=null,bestA=0;
for(var i=0;i<cont.size();i++){
var cnt=cont.get(i);
var area=Math.abs(cv.contourArea(cnt));
if(area<cw*ch*0.08||area>cw*ch*0.97){cnt.delete();continue}
var per=cv.arcLength(cnt,true);
var ap=new cv.Mat();
cv.approxPolyDP(cnt,ap,0.02*per,true);
if(ap.rows===4&&cv.isContourConvex(ap)){
if(area>bestA){
var pts=[];
for(var p=0;p<4;p++)pts.push({x:ap.data32S[p*2],y:ap.data32S[p*2+1]});
best=ordenarPts(pts);
bestA=area;
}
}
ap.delete();cnt.delete();
}
cont.delete();hier.delete();edg.delete();blur.delete();gray.delete();src.delete();
if(!best)return null;
var inv=1/sc;
return {tl:{x:best.tl.x*inv,y:best.tl.y*inv},tr:{x:best.tr.x*inv,y:best.tr.y*inv},br:{x:best.br.x*inv,y:best.br.y*inv},bl:{x:best.bl.x*inv,y:best.bl.y*inv}};
}
function warpPro(vid,q){
var v=R(vid);
var cw=v.videoWidth,ch=v.videoHeight;
var c=document.createElement("canvas");c.width=cw;c.height=ch;
c.getContext("2d").drawImage(v,0,0);
var src=cv.imread(c);
var d1=Math.hypot(q.tr.x-q.tl.x,q.tr.y-q.tl.y),d2=Math.hypot(q.br.x-q.bl.x,q.br.y-q.bl.y);
var dw=Math.max(d1,d2);
var d3=Math.hypot(q.bl.x-q.tl.x,q.bl.y-q.tl.y),d4=Math.hypot(q.br.x-q.tr.x,q.br.y-q.tr.y);
var dh=Math.max(d3,d4);
var srcTri=cv.matFromArray(4,1,cv.CV_32FC2,[q.tl.x,q.tl.y,q.tr.x,q.tr.y,q.br.x,q.br.y,q.bl.x,q.bl.y]);
var dstTri=cv.matFromArray(4,1,cv.CV_32FC2,[0,0,dw,0,dw,dh,0,dh]);
var M=cv.getPerspectiveTransform(srcTri,dstTri);
var dst=new cv.Mat();
cv.warpPerspective(src,dst,M,new cv.Size(Math.round(dw),Math.round(dh)));
var out=document.createElement("canvas");
cv.imshow(out,dst);
src.delete();dst.delete();M.delete();srcTri.delete();dstTri.delete();
return out.toDataURL("image/jpeg",0.9).split(",").pop();
}
async function abrirCamF(){
stopCamA();
R("stF").innerHTML="Cargando escaner profesional (solo la primera vez)...";
try{await cargarOpenCV();ocvListo=true}catch(e){R("stF").innerHTML="El escaner profesional no cargo: usa 'elegir archivo existente'.";R("stF").className="estado mal";return}
await abrirCamGen("vdF","vzF","bAbrirF","bCapF","stF",function(c){camF=c;ivF=setInterval(function(){loopSeguir("vdF","ovF",function(q){quadF=q})},450)});
}
async function abrirCamA(){
stopCamF();
R("stA").innerHTML="Cargando escaner profesional (solo la primera vez)...";
try{await cargarOpenCV();ocvListo=true}catch(e){R("stA").innerHTML="El escaner profesional no cargo: usa 'elegir archivo existente'.";R("stA").className="estado mal";return}
await abrirCamGen("vdA","vzA","bAbrirA","bCapA","stA",function(c){camA=c;ivA=setInterval(function(){loopSeguir("vdA","ovA",function(q){quadA=q})},450)});
}
async function abrirCamGen(vid,zn,bAbrir,bCap,st,cb){
try{
R(zn).style.display="block";
R(bAbrir).style.display="none";
R(bCap).style.display="none";
var c=await navigator.mediaDevices.getUserMedia({video:{facingMode:"environment",width:{ideal:1280},height:{ideal:720}}});
var v=R(vid);v.srcObject=c;
R(bCap).style.display="block";
R(st).innerHTML="El recuadro verde buscara las 4 esquinas del documento. Acerca el documento hasta llenarlo.";
cb(c);
}catch(e){
R(st).innerHTML="No se pudo abrir la camara: "+e;R(st).className="estado mal";
R(bAbrir).style.display="block";
}
}
function stopCamGen(c,iv,zn,bCap,bAbrir){
if(iv){clearInterval(iv)}
if(c){try{c.getTracks().forEach(function(t){t.stop()})}catch(e){}}
R(zn).style.display="none";
R(bCap).style.display="none";
R(bAbrir).style.display="block";
}
function stopCamF(){stopCamGen(camF,ivF,"vzF","bCapF","bAbrirF");camF=null;ivF=null;quadF=null}
function stopCamA(){stopCamGen(camA,ivA,"vzA","bCapA","bAbrirA");camA=null;ivA=null;quadA=null}
function stopCam(){
if(cam){try{cam.getTracks().forEach(function(t){t.stop()})}catch(e){}}
cam=null;R("vzS").style.display="none";R("bSelfie").style.display="none";
}
function loopSeguir(vid,ovId,cb){
var q=detectarQuadPro(vid);
cb(q);
var v=R(vid),ov=R(ovId);
if(!v.videoWidth)return;
var vw=v.videoWidth,vh=v.videoHeight;
if(ov.width!=vw){ov.width=vw;ov.height=vh}
var g=ov.getContext("2d");
g.clearRect(0,0,vw,vh);
if(q){
g.strokeStyle="#3fb950";g.lineWidth=5;
g.beginPath();
g.moveTo(q.tl.x,q.tl.y);g.lineTo(q.tr.x,q.tr.y);g.lineTo(q.br.x,q.br.y);g.lineTo(q.bl.x,q.bl.y);g.closePath();
g.stroke();
var pts=[q.tl,q.tr,q.br,q.bl];
for(var i=0;i<4;i++){
g.fillStyle="#3fb950";
g.beginPath();g.arc(pts[i].x,pts[i].y,11,0,6.3);g.fill();
}
if(vid=="vdF"){R("stF").innerHTML="DOCUMENTO ENMARCADO: pulsa CAPTURAR";R("stF").className="estado chk"}
else{R("stA").innerHTML="DOCUMENTO ENMARCADO: pulsa CAPTURAR";R("stA").className="estado chk"}
}else{
if(vid=="vdF"){R("stF").innerHTML="Buscando las esquinas del documento...";R("stF").className="estado"}
else{R("stA").innerHTML="Buscando las esquinas del documento...";R("stA").className="estado"}
}
}
async function capturarF(){await capturarDocGen("vdF","F",function(){return quadF},function(){stopCamF()})}
async function capturarA(){await capturarDocGen("vdA","A",function(){return quadA},function(){stopCamA()})}
async function capturarDocGen(vid,lado,getQ,stopFn){
var v=R(vid);
if(!v.videoWidth){return}
var st=R("st"+lado);
var q=getQ();
if(!q){
st.innerHTML="El escaner no vio el documento: acercalo hasta que el recuadro lo enmarque y captura.";
st.className="estado mal";
return;
}
st.innerHTML="Recortando con correccion de perspectiva y leyendo...";
st.className="estado";st.style.color="#f0b429";
var comp=null;
try{
if(window.cv&&window.cv.Mat){
comp=warpPro(vid,q);
comp=(await zyComprimir("data:image/jpeg;base64,"+comp,1200,0.78));
}else{
var c=document.createElement("canvas");
var wq=Math.round(Math.max(q.tr.x-q.tl.x,q.br.x-q.bl.x));
var hq=Math.round(Math.max(q.bl.y-q.tl.y,q.br.y-q.tr.y));
c.width=wq;c.height=hq;
c.getContext("2d").drawImage(v,q.tl.x,q.tl.y,wq,hq,0,0,wq,hq);
var crudo=c.toDataURL("image/jpeg",0.9);
stopFn();
comp=await zyComprimir("data:image/jpeg;base64,"+crudo,1200,0.78);
}
}catch(e){
st.innerHTML="Error recortando: "+e;st.className="estado mal";
return;
}
stopFn();
var st2=R("st"+lado);
st2.innerHTML="Verificando el lado y leyendo (OCR puede tardar unos segundos)...";
var cl=await clasificarLado(comp);
var quieroFrontal=(lado=="F");
if(cl.esFrontal===null){
st2.innerHTML=cl.motivo;st2.className="estado mal";
return;
}
if(quieroFrontal&&!cl.esFrontal){
st2.innerHTML="ESTA FOTO ES EL REVERSO. Este paso es para el FRONTAL. Tomala de nuevo.";st2.className="estado mal";
bloquear(lado,"BLOQUEADO: tomaste el reverso en el paso del frontal.");
return;
}
if(!quieroFrontal&&cl.esFrontal){
st2.innerHTML="ESTA FOTO ES EL FRONTAL. Este paso es para el REVERSO. Tomala de nuevo.";st2.className="estado mal";
bloquear(lado,"BLOQUEADO: tomaste el frontal en el paso del reverso.");
return;
}
var fuente=cl.codigo||null;
if(!fuente&&cl.ocr){
fuente={nombre:cl.ocr.nombre||null,nacimiento:cl.ocr.nacimiento||"",edad:(cl.ocr.nacimiento?edadDe(cl.ocr.nacimiento):-1),numero:"",direccion:"",vencimiento:cl.ocr.vencimiento||"",confiable:!!(cl.ocr.nombre||cl.ocr.vencimiento),texto:cl.ocr.texto};
}
if(lado=="F"){datosDocF=fuente;DF=comp}else{datosDocA=fuente;DA=comp}
var pv=R(lado=="F"?"pF":"pA");
pv.src="data:image/jpeg;base64,"+comp;pv.style.display="block";
mostrarDesglose();
saveSes();
var ok=aplicarFiltros(lado);
if(!ok){
st2.innerHTML="FILTRO DE BLOQUEO ACTIVO — mira el mensaje en rojo.";
st2.className="estado mal";
return;
}
limpiarBloc(lado);
st2.innerHTML="LADO "+(lado=="F"?"FRONTAL":"REVERSO")+" guardado y VERIFICADO ("+kb(comp)+" KB)";
st2.className="estado chk";
if(lado=="F"){irAPaso(3)}else{R("bIr4").disabled=false;irAPaso(4)}
}
async function desdeArchivo(inp,lado){
var f=inp.files&&inp.files[0];if(!f)return;
var st=R("st"+lado);
st.innerHTML="PROCESANDO...";
st.className="estado";st.style.color="#f0b429";
try{
var fr2=new FileReader();
var pfr=new Promise(function(res,rej){fr2.onload=function(){res(fr2.result)};fr2.onerror=function(){rej(new Error("lectura"))}});
fr2.readAsDataURL(f);
var crudo=await conTimeout(pfr,15000,"lectura lenta");
var comp=await conTimeout(zyComprimir(crudo,1200,0.75),15000,"compresion lenta");
var cl=await clasificarLado(comp);
var quieroFrontal=(lado=="F");
if(cl.esFrontal===null){
st.innerHTML=cl.motivo;st.className="estado mal";return;
}
if(quieroFrontal&&!cl.esFrontal){
st.innerHTML="ESTA FOTO ES EL REVERSO. Este paso es para el FRONTAL.";st.className="estado mal";
bloquear(lado,"BLOQUEADO: tomaste el reverso en el paso del frontal.");
return;
}
if(!quieroFrontal&&cl.esFrontal){
st.innerHTML="ESTA FOTO ES EL FRONTAL. Este paso es para el REVERSO.";st.className="estado mal";
bloquear(lado,"BLOQUEADO: tomaste el frontal en el paso del reverso.");
return;
}
var fuente=cl.codigo||null;
if(!fuente&&cl.ocr){
fuente={nombre:cl.ocr.nombre||null,nacimiento:cl.ocr.nacimiento||"",edad:(cl.ocr.nacimiento?edadDe(cl.ocr.nacimiento):-1),numero:"",direccion:"",vencimiento:cl.ocr.vencimiento||"",confiable:!!(cl.ocr.nombre||cl.ocr.vencimiento),texto:cl.ocr.texto};
}
if(lado=="F"){datosDocF=fuente;DF=comp}else{datosDocA=fuente;DA=comp}
var pv=R(lado=="F"?"pF":"pA");
pv.src="data:image/jpeg;base64,"+comp;pv.style.display="block";
mostrarDesglose();
saveSes();
var ok=aplicarFiltros(lado);
if(!ok){
st.innerHTML="FILTRO DE BLOQUEO ACTIVO — mira el mensaje en rojo.";
st.className="estado mal";
inp.value="";
return;
}
limpiarBloc(lado);
st.innerHTML="LADO "+(lado=="F"?"FRONTAL":"REVERSO")+" guardado y VERIFICADO ("+kb(comp)+" KB)";
st.className="estado chk";
inp.value="";
if(lado=="F"){irAPaso(3)}else{R("bIr4").disabled=false;irAPaso(4)}
}catch(e){
st.innerHTML="Error: "+e;st.className="estado mal";
}
}
function rehacer(lado){
if(lado=="F"){DF="";datosDocF=null;R("pF").style.display="none";limpiarBloc("F");irAPaso(2)}
else{DA="";datosDocA=null;R("pA").style.display="none";R("bIr4").disabled=true;limpiarBloc("A");irAPaso(3)}
}
async function abrirCamara(){
var st=R("stV");
try{
R("vzS").style.display="block";
R("bAbrirCam").style.display="none";
R("bRepSelfie").style.display="none";
cam=await navigator.mediaDevices.getUserMedia({video:{facingMode:"user",width:{ideal:640},height:{ideal:480}}});
var v=R("v");v.srcObject=cam;
R("bSelfie").style.display="block";
st.innerHTML="Centra tu rostro dentro de la guia con buena luz.";
ensureCara();loop();
}catch(e){
st.innerHTML="No se pudo abrir la camara: "+e;st.className="estado mal";
R("bAbrirCam").style.display="block";
}
}
async function loop(){
var v=R("v"),ov=R("ovS");
setInterval(async function(){
if(!cam||v.readyState<2)return;
var vw=v.videoWidth,vh=v.videoHeight;if(!vw)return;
if(ov.width!=vw){ov.width=vw;ov.height=vh}
var g=ov.getContext("2d");g.clearRect(0,0,ov.width,ov.height);
var o={cx:vw/2,cy:vh*0.46,rx:vw*0.22,ry:vh*0.31};
try{
var caja=await cajaEnVideo(v);
cara=caja;
alineado=false;
if(caja){
var fcx=caja.x+caja.w/2,fcy=caja.y+caja.h/2;
var nx=(fcx-o.cx)/(o.rx*0.55),ny=(fcy-o.cy)/(o.ry*0.55);
var wr=caja.w/vw;
alineado=((nx*nx+ny*ny)<=1&&wr>0.16&&wr<0.60);
var col=alineado?"#3fb950":"#f0b429";
g.strokeStyle="rgba(63,185,80,0.25)";if(!alineado)g.strokeStyle="rgba(240,180,41,0.25)";
g.lineWidth=9;
g.beginPath();g.ellipse(o.cx,o.cy,o.rx,o.ry,0,0,6.3);g.stroke();
g.strokeStyle=col;g.lineWidth=1.6;
g.beginPath();g.ellipse(o.cx,o.cy,o.rx,o.ry,0,0,6.3);g.stroke();
g.lineWidth=4;
var angs=[0.785,2.356,3.927,5.498];
for(var a2=0;a2<4;a2++){
g.beginPath();
g.ellipse(o.cx,o.cy,o.rx,o.ry,0,angs[a2]-0.38,angs[a2]+0.38);
g.stroke();
}
if(!capturando){
if(alineado){R("stV").innerHTML="Encuadre perfecto: pulsa CAPTURAR";R("stV").style.color="#3fb950"}
else{R("stV").innerHTML="Centra tu rostro dentro de la guia";R("stV").style.color="#f0b429"}
}
}else{
g.strokeStyle="#f85149";g.lineWidth=3;
g.beginPath();g.ellipse(o.cx,o.cy,o.rx,o.ry,0,0,6.3);g.stroke();
if(!capturando){R("stV").innerHTML="No veo tu rostro. Busca buena luz.";R("stV").style.color="#9aa0c3"}
}
}catch(e){}
},250);
}
async function capturarSelfie(){
if(capturando)return false;
var st=R("stV"),v=R("v");
var bl=R("blocS");
if(bl)bl.innerHTML="";
if(!cam||!v.videoWidth){st.innerHTML="Abre la camara primero.";st.className="estado mal";return false}
capturando=true;R("bSelfie").disabled=true;
st.innerHTML="Verificando luz, rostro y encuadre...";st.style.color="#f0b429";
var i=0;while(!cara&&i<10){await dormir(300);i++}
var c=document.createElement("canvas");c.width=v.videoWidth;c.height=v.videoHeight;
var g=c.getContext("2d");g.translate(c.width,0);g.scale(-1,1);g.drawImage(v,0,0);
var crudo=c.toDataURL("image/jpeg",0.85);
var L=await luma(crudo);
if(L<60){
st.innerHTML="LUZ INSUFICIENTE ("+Math.round(L)+"/100). NO se guardo.";
st.className="estado mal";
capturando=false;R("bSelfie").disabled=false;
return false;
}
if(detTipo!=""&&!cara){
st.innerHTML="NO VEO TU ROSTRO con claridad. NO se guardo.";
st.className="estado mal";
capturando=false;R("bSelfie").disabled=false;
return false;
}
if(detTipo!=""&&!alineado){
st.innerHTML="ENCUADRE INCOMPLETO: rostro entero dentro de la guia. NO se guardo.";
st.className="estado mal";
capturando=false;R("bSelfie").disabled=false;
return false;
}
var comp=await zyComprimir(crudo,640,0.6);
DS=comp;
stopCam();
R("bAbrirCam").style.display="none";
R("bRepSelfie").style.display="block";
R("pS").src="data:image/jpeg;base64,"+comp;R("pS").style.display="block";
st.innerHTML="SELFIE GUARDADA: "+kb(comp)+" KB (luz "+Math.round(L)+"/100)";st.className="estado chk";
capturando=false;R("bSelfie").disabled=false;
var stB=R("blocS");
bioRechazada=false;
if(faListo&&DF){
if(stB)stB.innerHTML="<p style='color:#f0b429;text-align:center'>COMPARANDO tu rostro con el del documento...</p>";
try{
var im1=new Image(),im2=new Image();
var p1=new Promise(function(res){im1.onload=res;im1.onerror=res;im1.src="data:image/jpeg;base64,"+DF});
var p2=new Promise(function(res){im2.onload=res;im2.onerror=res;im2.src="data:image/jpeg;base64,"+DS});
await Promise.all([p1,p2]);
var r1=await faceapi.detectSingleFace(im1,new faceapi.TinyFaceDetectorOptions({inputSize:416})).withFaceDescriptor();
var r2b=await faceapi.detectSingleFace(im2,new faceapi.TinyFaceDetectorOptions({inputSize:416})).withFaceDescriptor();
if(r1&&r2b){
var dist=faceapi.euclideanDistance(r1.descriptor,r2b.descriptor);
if(dist>0.66){
bioRechazada=true;
if(stB)stB.innerHTML="<p class='bloc'>BLOQUEADO: tu rostro NO coincide con el del documento (distancia "+dist.toFixed(2)+" — maximo 0.66). NO puedes pasar a la clave. Usa tu propio documento.</p>";
R("bIr5").style.display="none";
capturando=false;R("bSelfie").disabled=false;
saveSes();
return false;
}else{
if(stB)stB.innerHTML="<p style='color:#3fb950;text-align:center;font-weight:700'>Biometria local APROBADA (dist "+dist.toFixed(2)+").</p>";
}
}else{
if(stB)stB.innerHTML="<p style='color:#9aa0c3;text-align:center'>Pre-chequeo no disponible: el motor de la Red hara la comparacion al crear el ZID.</p>";
}
}catch(e){if(stB)stB.innerHTML=""}
}
R("bIr5").style.display="block";
saveSes();
setTimeout(function(){irAPaso(5)},900);
return true;
}
async function enviar(ev){ev.preventDefault();var Rr=R("resp");
var c1=R("clave").value,c2=R("clave2").value;
var tipo=R("tipoDoc").value;
var nmv=R("nombre").value.trim();
var reqRev=(tipo=="dui"||tipo=="licencia"||tipo=="id_usa");
if(nmv.length<3||partesNombre(nmv).length<2){Rr.innerHTML="<p style='color:#f85149'>Escribe tu nombre y apellido.</p>";window.scrollTo(0,document.body.scrollHeight);return false}
if(docVencido){Rr.innerHTML="<p style='color:#f85149;font-weight:700'>DOCUMENTO VENCIDO: NO se crea el ZID.</p>";return false}
if(minorBloqueado){Rr.innerHTML="<p style='color:#f85149;font-weight:700'>MENOR DE EDAD: los menores se registran con tutor.</p>";return false}
if(nombreNoCoincide){Rr.innerHTML="<p style='color:#f85149;font-weight:700'>El nombre no coincide con el documento. Corrigelo.</p>";return false}
if(bioRechazada){Rr.innerHTML="<p style='color:#f85149;font-weight:700'>Biometria rechazada en el paso 4: tu rostro no coincide con el documento.</p>";return false}
if(c1!==c2){Rr.innerHTML="<p style='color:#f85149'>Las claves no coinciden.</p>";return false}
if(c1.length<8){Rr.innerHTML="<p style='color:#f85149'>La clave necesita minimo 8 caracteres.</p>";return false}
if(!DF){Rr.innerHTML="<p style='color:#f85149'>Falta el documento frontal (paso 2).</p>";return false}
if(reqRev&&!DA){Rr.innerHTML="<p style='color:#f85149'>Este documento requiere el reverso (paso 3).</p>";return false}
if(!DS){Rr.innerHTML="<p style='color:#f85149'>Falta la selfie (paso 4).</p>";return false}
Rr.innerHTML="<p style='color:#8b949e'>Enviando a la Red ("+kb(DF)+" y "+kb(DS)+" KB). El motor comparara tu rostro con el documento...</p>";
window.scrollTo(0,document.body.scrollHeight);
try{var r=await fetch("/registro/nuevo",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({nombre:nmv,clave:c1,doc_image_b64:DF,doc_back_b64:DA,selfie_image_b64:DS,doc_type:tipo,doc_number:((datosDocA&&datosDocA.numero)||(datosDocF&&datosDocF.numero)||"")})});
var txt=await r.text();
var j=null;
try{j=JSON.parse(txt)}catch(e2){}
if(j&&j.ok&&j.zid){Rr.innerHTML="<div style='background:#0f2a1a;border:1px solid #238636;border-radius:12px;padding:14px'><p style='color:#3fb950;font-weight:800;font-size:17px'>REGISTRO EXITOSO</p><p>Tu ZID unico fue creado:</p><p class='zid'>"+j.zid+"</p><p>Guarda tu ZID y tu clave. Nadie mas puede crearlo.</p><p><a href='/entrar'>ENTRAR AHORA</a></p></div>";}
else if(j&&j.codigo==="mantenimiento"){Rr.innerHTML="<div style='background:#2a2410;border:1px solid #f0b429;border-radius:12px;padding:14px'><p style='color:#f0b429;font-weight:800'>BIOMETRIA EN MANTENIMIENTO</p><p>"+(j.error||"")+"</p><p><a href='/registro'>Volver a intentar</a></p></div>";}
else if(j&&j.error){
var em="HTTP "+r.status;
if(j.error.message)em+=" | "+j.error.message;
if(j.error.reason)em+=" | razon: "+j.error.reason;
if(j.error.doc_match_score!==undefined&&j.error.doc_match_score!==null)em+=" | puntaje: "+String(j.error.doc_match_score).substring(0,6)+" (auto>=0.40)";
if(j.error.case_status)em+=" | estado: "+j.error.case_status;
Rr.innerHTML="<p style='color:#f85149;font-weight:700'>NO SE PUDO CREAR EL ZID</p><p>"+em+"</p>";}
else{
var em2="HTTP "+r.status+" | respuesta: "+txt.substring(0,300);
if(r.status===502){em2+=" — la Red se esta reiniciando (Render): espera 2 minutos y vuelve a intentar."}
Rr.innerHTML="<p style='color:#f85149;font-weight:700'>NO SE PUDO CREAR EL ZID</p><p>"+em2+"</p>";}}
catch(e){Rr.innerHTML="<div style='background:#2a1414;border:1px solid #f85149;border-radius:12px;padding:14px'><p style='color:#f85149;font-weight:700'>La Red no respondio</p><p>Detalle: "+e+"</p></div>";}
window.scrollTo(0,document.body.scrollHeight);
return false}
(function(){var s=loadSes();if(s&&(s.DF||s.DA||s.DS)){
DF=s.DF||"";DA=s.DA||"";DS=s.DS||"";
if(s.nm)R("nombre").value=s.nm;
if(s.td)R("tipoDoc").value=s.td;
var dest=2;
if(DS){dest=5}else if(DA){dest=4}else if(DF){dest=3}
irAPaso(dest);
if(DF){var pF2=R("pF");pF2.src="data:image/jpeg;base64,"+DF;pF2.style.display="block"}
if(DA){var pA2=R("pA");pA2.src="data:image/jpeg;base64,"+DA;pA2.style.display="block"}
if(DS){var pS2=R("pS");pS2.src="data:image/jpeg;base64,"+DS;pS2.style.display="block";R("bIr5").style.display="block"}
if(DA&&R("tipoDoc").value!="pasaporte"){R("bIr4").disabled=false}
mostrarDesglose();
var rst=R("resp");if(rst)rst.innerHTML="<p style='color:#7c8cf8'>Sesion restaurada: tus fotos siguen aqui.</p>";
}})();
setTimeout(function(){ensureCara()},800);
</script>
<script>

(function(){
  if (window.__zyraPuertaV37) { return; }
  window.__zyraPuertaV37 = true;
  function R(id){ return document.getElementById(id); }
  function toast(msg, mal){
    var t = document.getElementById("toastv37");
    if (!t) {
      t = document.createElement("div");
      t.id = "toastv37";
      t.style.cssText = "position:fixed;left:12px;right:12px;bottom:18px;z-index:99999;padding:12px 14px;border-radius:12px;font-size:14px;font-weight:700;color:#fff;box-shadow:0 6px 24px rgba(0,0,0,0.5);display:none";
      document.body.appendChild(t);
    }
    t.style.background = mal ? "#b62324" : "#1f6f3f";
    t.textContent = msg;
    t.style.display = "block";
    if (t.__h) { clearTimeout(t.__h); }
    t.__h = setTimeout(function(){ t.style.display = "none"; }, 7000);
  }
  function normTokens(s){
    var v = (s || "").toUpperCase();
    var de = "ÁÀÄÂÃÉÈËÊÍÌÏÎÓÒÖÔÕÚÙÜÛÑÇ";
    var aa = "AAAAAEEEEIIIIOOOOOUUUUNC";
    var i = 0;
    for (i = 0; i < de.length; i++) { v = v.split(de.charAt(i)).join(aa.charAt(i)); }
    v = v.replace(/[^A-Z ]/g, " ");
    var parts = v.split(" ");
    var out = [];
    var j = 0;
    for (j = 0; j < parts.length; j++) { if (parts[j].length > 1) { out.push(parts[j]); } }
    return out;
  }
  function coincide(nombreDoc, nombreReg){
    var d = normTokens(nombreDoc);
    var r = normTokens(nombreReg);
    if (d.length === 0 || r.length === 0) { return false; }
    if (r.length === 1) { return (d.length === 1 && d[0] === r[0]); }
    var k = 0;
    for (k = 0; k < r.length; k++) { if (d.indexOf(r[k]) === -1) { return false; } }
    return true;
  }
  function sesion(){
    try { return JSON.parse(sessionStorage.getItem("zyraReg") || "null"); } catch (e) { return null; }
  }
  function nombreRegistro(){
    var el = R("nombre");
    if (el && el.value) { return el.value; }
    var s = sesion();
    return (s && s.nm) ? s.nm : "";
  }
  function imagenFrente(){
    var s = sesion();
    return (s && s.DF) ? s.DF : "";
  }
  async function verificarNombre(){
    var reg = nombreRegistro();
    if (normTokens(reg).length < 2) {
      toast("Escribe tu nombre completo (1 o 2 nombres y 1 o 2 apellidos) en el PASO 1.", true);
      return false;
    }
    if (window.nombreNoCoincide === true) {
      toast("EL NOMBRE NO COINCIDE con el documento. No puedes pasar a la biometría.", true);
      return false;
    }
    var df = imagenFrente();
    if (!df) {
      toast("No encuentro la foto del documento. Vuelve al PASO 2 y toma la foto del frente.", true);
      return false;
    }
    toast("Verificando que tu nombre coincida con el documento...", false);
    var texto = "";
    try {
      if (typeof Tesseract === "undefined") {
        if (typeof cargarScript === "function") {
          await cargarScript("https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js");
        }
      }
      var imgArg = (df.indexOf("data:") === 0) ? df : ("data:image/jpeg;base64," + df);
      var r = await Tesseract.recognize(imgArg, "eng");
      texto = (r && r.data && r.data.text) ? r.data.text : "";
    } catch (e) { texto = ""; }
    if (!texto) {
      toast("No pudimos leer el documento. Toma la foto de nuevo: buena luz, sin reflejos, documento llenando la guía.", true);
      return false;
    }
    var nombreDoc = (typeof nombreDeTexto === "function") ? nombreDeTexto(texto) : null;
    if (!nombreDoc) {
      toast("No pudimos leer el NOMBRE del documento. Vuelve al PASO 2 y reescanea con buena luz.", true);
      return false;
    }
    if (!coincide(nombreDoc, reg)) {
      toast("EL NOMBRE NO COINCIDE: el documento dice '" + nombreDoc + "'. No puedes pasar a la biometría.", true);
      return false;
    }
    return true;
  }
  var original = window.irAPaso;
  if (typeof original !== "function") { return; }
  window.irAPaso = function(n){
    if (n === 4) {
      verificarNombre().then(function(ok){
        if (ok) { toast("Nombre verificado: coincide con el documento.", false); original(4); }
      });
      return;
    }
    return original(n);
  };
})();

/*ZYRA-V6-BEGIN*/eval(atob('LypaWVJBLVJFVkYgdjE4IC0gbnVjbGVvIGRlIHJlZ2lzdHJvIHJldkYgKGNvbnNlcnZhIFRPRE8gdjEzLi52MTc6IDQgZXNxdWluYXMgY29uIG1hc2NhcmEKYW50aS10ZWxhLCBtb3RvciBmYWNpYWwgRU4gVklWTywgT0NSIG11bHRpLXBhc2UgY29uIGxlY3R1cmEgY29uZmlybWFibGUsIGZvdG8gZGVsIGRvY3VtZW50bwpyZWNvcnRhZGEgYWwgY3VhZHJvLCBzZWxmaWUgZGUgcm9zdHJvLCBsZWN0dXJhIGZ1ZXJ0ZSBjb24gcG9jYSBsdXosIGVudmlvIGZhaWwtY2xvc2VkLAphbnRpLWJsb3F1ZW8gbGVnYWRvLCBib3RvbiAiaSIsIG1vdG9yIGRlIG5vbWJyZXMgZmxleGlibGUsIHJlc3BhbGRvIGF1dG9tYXRpY28sIGNsYXZlCnJlc3BhbGRhZGEgZW4gc2VzaW9uIGNvbiByZXB1ZXN0YSBzb2xhLCBlbnZpbyBwcm90ZWdpZG8gcG9yIGZldGNoIHkgcGFudGFsbGEgZGUgZXhpdG87Ck5VRVZPIGVuIHYxOCwgcG9yIGxvIHJlcG9ydGFkbyBlbCAxMS8xMSBjb24gY2FwdHVyYXMgKHBhc28gNS81IGNvcnJlY3RvLCBjbGF2ZSBsaXN0YSk6CjEpIEVMIFNFUlZJRE9SIFFVRSBQSURFICJSRUNVUEVSQVIgQ09OVFJBU0VOQSIgWUEgTk8gU0UgQ09ORlVOREUgQ09OIEVYSVRPOiBlbiB2MTcgdW5hCiAgIHJlc3B1ZXN0YSBhc2kgc2UgdG9tYWJhIGNvbW8gY3JlYWNpb24gZSBpbmNsdXNvIHNlIHJlZXNjcmliaWEgbGEgcGFnaW5hIGNvbiBlbGxhCiAgIChwb3IgZXNvIHZlaWFzIFJlY3VwZXJhciBjb250cmFzZW5hIGVuIHZleiBkZSB0dSBaSUQpLiBBaG9yYSBsYSByZXNwdWVzdGEgZGVsCiAgIHNlcnZpZG9yIHNlIENMQVNJRklDQTogZXhpdG8gcmVhbCAodGV4dG8gZGUgZXhpdG8gbyBjb2RpZ28gZGUgWklEKSAtPiBwYW50YWxsYQogICB2ZXJkZTsgcGV0aWNpb24gZGUgcmVjdXBlcmFyIGNsYXZlIC0+IHBhbmVsIGFtYmFyIHF1ZSBleHBsaWNhIFFVRSBIQUNFUiAodHUgWklECiAgIHByb2JhYmxlbWVudGUgeWEgZXhpc3RlOiBlbnRyYSBjb24gdHUgY2xhdmUgZW4gIllhIHRlbmdvIFpJRCIpIFNJTiBib3JyYXIgbmFkYTsKICAgcmVzcHVlc3RhIGRlc2Nvbm9jaWRhIC0+IGF2aXNvIGFtYmFyIHkgdG9kbyBxdWVkYSBpbnRhY3RvLiBMYSBwYWdpbmEgU09MTyBzZQogICByZWVzY3JpYmUgc2kgaGF5IGV4aXRvIGRlbW9zdHJhZG8uIExhIG1hcmNhIGRlIGV4aXRvIGZhbHNhIGRlIHYxNyBzZSBsaW1waWEgc29sYS4KMikgRUwgQk9UT04gQ1JFQVIgRlVOQ0lPTkEgRU4gVE9ET1MgTE9TIENBTUlOT1M6IHNpIGVsIGNvZGlnbyB2aWVqbyBsbGFtYQogICBmb3JtLnN1Ym1pdCgpIGRpcmVjdG8gKHNpbiBldmVudG8pLCBlbCBlbnZvbHZlbnRlIHYxOCBsbyB0b21hIGlndWFsIHBvciBlbCBjYW5hbAogICBwcm90ZWdpZG87IHkgc2kgdHJhcyB0b2NhciBlbCBib3RvbiBuYWRhIGVtcGllemEgZW4gNjAwIG1zLCBlbCBudWNsZW8gbGFuemEgZWwKICAgZW52aW8gcHJvdGVnaWRvIGVsIG1pc21vLiBMb3Mgb25jbGljayB2aWVqb3MgeWEgbm8gc2UgY29ydGFuOiBwdWVkZW4gcmVsbGVuYXIKICAgY2FtcG9zIG9jdWx0b3MgYW50ZXMgZGVsIGVudmlvLgozKSBWT0xWRVIgVlVFTFZFIERFIFZFUkRBRDogYWwgdG9jYXIgVm9sdmVyL0F0cmFzL1JlZ3Jlc2FyL0NhbmNlbGFyIGxhIGd1YXJkaWEKICAgYW50aS1wYXRhZGEgc2UgUEFVU0EgaGFzdGEgcXVlIFRVIGF2YW56YXMgZGUgbnVldm8uIEFudGVzIGxhIHBhdXNhIGVyYSBkZSAzCiAgIHNlZ3VuZG9zIHkgZWwgYmFycmlkbyBhdXRvbWF0aWNvIGRlIG1lbnNhamVzIChxdWUgbXV0YSBlbCBET00pIGRpc3BhcmFiYSBsYQogICBndWFyZGlhIHkgdGUgcGF0ZWFiYSBkZWwgcGFzbyAxIGFsIHBhc28gNSBqdXN0byBhbCBlc2NyaWJpciB0dSBub21icmUuIEFkZW1hcywKICAgbWllbnRyYXMgZXNjcmliZXMgZW4gZWwgY2FtcG8gZGVsIG5vbWJyZSwgbGEgZ3VhcmRpYSBudW5jYSB0ZSBtdWV2ZS4KNCkgTlVOQ0EgSEFZIERPQkxFIEVOVklPOiBtYXJjYSBkZSB0aWVtcG8gZGVsIHVsdGltbyBlbnZpbyArIGJhbmRlcmFzOyBlbCByZWVudmlvCiAgIGRlbCBib3RvbiBvIGRlbCBjb2RpZ28gdmllam8gc2UgaWdub3JhIG1pZW50cmFzIGVsIGNhbmFsIHByb3RlZ2lkbyBlc3RhIGVuIHZ1ZWxvLiovCihmdW5jdGlvbigpewondXNlIHN0cmljdCc7CnZhciBXID0gKHR5cGVvZiB3aW5kb3chPT0ndW5kZWZpbmVkJyk/d2luZG93OnRoaXM7CmlmIChXLl9fWllSQV9SRVZFX18pIHsgcmV0dXJuOyB9ClcuX19aWVJBX1JFVkVfXyA9ICdGJzsKCi8qID09PT09PT09PT09PT09PT09IHV0aWxpZGFkZXMgZGUgdGV4dG8gPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gJChpZCl7IHRyeXsgcmV0dXJuICh0eXBlb2YgZG9jdW1lbnQhPT0ndW5kZWZpbmVkJyk/ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoaWQpOm51bGw7IH1jYXRjaChlKXsgcmV0dXJuIG51bGw7IH0gfQpmdW5jdGlvbiBsb2coKXsgdHJ5eyB2YXIgYT1bJ1taWVJBLVJFVkVdJ107IGZvcih2YXIgaT0wO2k8YXJndW1lbnRzLmxlbmd0aDtpKyspeyBhLnB1c2goYXJndW1lbnRzW2ldKTsgfSBjb25zb2xlLmxvZy5hcHBseShjb25zb2xlLGEpOyB9Y2F0Y2goZSl7fSB9CgpmdW5jdGlvbiBub3JtKHMpewogIHZhciB0PShzPT1udWxsPycnOlN0cmluZyhzKSkudG9VcHBlckNhc2UoKTsKICB0PXQucmVwbGFjZSgvW1x1MDBDMVx1MDBDMFx1MDBDNFx1MDBDMl0vZywnQScpLnJlcGxhY2UoL1tcdTAwQzlcdTAwQzhcdTAwQ0JcdTAwQ0FdL2csJ0UnKS5yZXBsYWNlKC9bXHUwMENEXHUwMENDXHUwMENGXHUwMENFXS9nLCdJJykucmVwbGFjZSgvW1x1MDBEM1x1MDBEMlx1MDBENlx1MDBENF0vZywnTycpLnJlcGxhY2UoL1tcdTAwREFcdTAwRDlcdTAwRENcdTAwREJdL2csJ1UnKS5yZXBsYWNlKC9cdTAwRDEvZywnTicpOwogIHJldHVybiB0LnJlcGxhY2UoL1teQS1aIF0vZywnICcpLnJlcGxhY2UoL1xzKy9nLCcgJykudHJpbSgpOwp9CmZ1bmN0aW9uIGxldihhLGIpewogIGE9KGE9PW51bGw/Jyc6U3RyaW5nKGEpKTsgYj0oYj09bnVsbD8nJzpTdHJpbmcoYikpOwogIHZhciBuPWEubGVuZ3RoLCBtPWIubGVuZ3RoOwogIGlmKCFuKXsgcmV0dXJuIG07IH0gaWYoIW0peyByZXR1cm4gbjsgfQogIHZhciBpLGoscHJldj1uZXcgQXJyYXkobSsxKSxjdXI9bmV3IEFycmF5KG0rMSk7CiAgZm9yKGo9MDtqPD1tO2orKyl7IHByZXZbal09ajsgfQogIGZvcihpPTE7aTw9bjtpKyspewogICAgY3VyWzBdPWk7CiAgICBmb3Ioaj0xO2o8PW07aisrKXsKICAgICAgdmFyIGM9KGEuY2hhckF0KGktMSk9PT1iLmNoYXJBdChqLTEpKT8wOjE7CiAgICAgIHZhciB2PXByZXZbal0rMTsKICAgICAgaWYoY3VyW2otMV0rMTx2KXsgdj1jdXJbai0xXSsxOyB9CiAgICAgIGlmKHByZXZbai0xXStjPHYpeyB2PXByZXZbai0xXStjOyB9CiAgICAgIGN1cltqXT12OwogICAgfQogICAgZm9yKGo9MDtqPD1tO2orKyl7IHByZXZbal09Y3VyW2pdOyB9CiAgfQogIHJldHVybiBwcmV2W21dOwp9CmZ1bmN0aW9uIHNpbVBhcihhLGIpeyBhPW5vcm0oYSk7IGI9bm9ybShiKTsgaWYoIWF8fCFiKXsgcmV0dXJuIDA7IH0gcmV0dXJuIDEtKGxldihhLGIpL01hdGgubWF4KGEubGVuZ3RoLGIubGVuZ3RoKSk7IH0KZnVuY3Rpb24gc2ltTm9tYnJlcyhhLGIpewogIGE9bm9ybShhKTsgYj1ub3JtKGIpOwogIGlmKCFhfHwhYil7IHJldHVybiAwOyB9CiAgdmFyIHMxPXNpbVBhcihhLGIpOwogIHZhciB0YT1hLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7CiAgdmFyIHRiPWIuc3BsaXQoJyAnKS5maWx0ZXIoZnVuY3Rpb24oeCl7IHJldHVybiB4Lmxlbmd0aD4xOyB9KTsKICB2YXIgczI9MDsKICBpZih0YS5sZW5ndGgmJnRiLmxlbmd0aCl7CiAgICB2YXIgY29ydG89KHRhLmxlbmd0aDw9dGIubGVuZ3RoKT90YTp0YjsKICAgIHZhciBsYXJnbz0odGEubGVuZ3RoPD10Yi5sZW5ndGgpP3RiOnRhOwogICAgdmFyIHRvdD0wLGksajsKICAgIGZvcihpPTA7aTxjb3J0by5sZW5ndGg7aSsrKXsKICAgICAgdmFyIG1lam9yPTA7CiAgICAgIGZvcihqPTA7ajxsYXJnby5sZW5ndGg7aisrKXsgdmFyIHY9c2ltUGFyKGNvcnRvW2ldLGxhcmdvW2pdKTsgaWYodj5tZWpvcil7IG1lam9yPXY7IH0gfQogICAgICB0b3QrPW1lam9yOwogICAgfQogICAgczI9dG90L2NvcnRvLmxlbmd0aDsKICB9CiAgcmV0dXJuIE1hdGgubWF4KHMxLHMyKTsKfQoKLyogPT09PT09PT09PT09PT09PT0gTVJaIHkgbm9tYnJlID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIG1yekxpbmVhcyh0KXsKICB2YXIgb3V0PVtdLCBsaW5lcz0odHx8JycpLnNwbGl0KC9bXHJcbl0rLyksIGk7CiAgZm9yKGk9MDtpPGxpbmVzLmxlbmd0aDtpKyspewogICAgdmFyIGw9bGluZXNbaV0ucmVwbGFjZSgvW1xzLl0vZywnJykudG9VcHBlckNhc2UoKTsKICAgIGlmKGwubGVuZ3RoPj0yMCAmJiAvXltBLVowLTk8XSskLy50ZXN0KGwpICYmIGwuaW5kZXhPZignPDwnKT49MCl7IG91dC5wdXNoKGwpOyB9CiAgfQogIHJldHVybiBvdXQ7Cn0KZnVuY3Rpb24gbXJ6Tm9tYnJlcyh0KXsKICB2YXIgcmVzPVtdLCB2aXN0b3M9e30sIGxzPW1yekxpbmVhcyh0KSwgaTsKICBmdW5jdGlvbiBwdXNoKG5vbWJyZSl7CiAgICBub21icmU9bm9ybShub21icmUpOwogICAgaWYobm9tYnJlICYmIG5vbWJyZS5sZW5ndGg+PTMgJiYgIXZpc3Rvc1tub21icmVdKXsgdmlzdG9zW25vbWJyZV09MTsgcmVzLnB1c2gobm9tYnJlKTsgfQogIH0KICBmb3IoaT0wO2k8bHMubGVuZ3RoO2krKyl7CiAgICB2YXIgbD1sc1tpXSwgbTsKICAgIG09bC5tYXRjaCgvXlA8KFtBLVpdezAsM30pKFtBLVpdezIsfSk8PChbQS1aPF0qKS8pOwogICAgaWYobSl7IHB1c2gobVsyXSsnICcrKG1bM118fCcnKSk7IH0KICAgIG09bC5tYXRjaCgvXlA8KFtBLVpdezAsM30/KShbQS1aXXsyLH0pPDwoW0EtWjxdKikvKTsKICAgIGlmKG0peyBwdXNoKG1bMl0rJyAnKyhtWzNdfHwnJykpOyB9CiAgICBtPWwubWF0Y2goL14oW0EtWjxdezQsfSk8PChbQS1aPF17Mix9KS8pOwogICAgaWYobSl7IHB1c2gobVsxXSsnICcrKG1bMl18fCcnKSk7IH0KICAgIG09bC5tYXRjaCgvXihbQS1aXXsyLH0pPDwoW0EtWjxdKikvKTsKICAgIGlmKG0peyBwdXNoKG1bMV0rJyAnKyhtWzJdfHwnJykpOyB9CiAgICBtPWwubWF0Y2goLyhbQS1aXXsyLH0pPDwoW0EtWjxdezIsfSkvKTsKICAgIGlmKG0peyBwdXNoKG1bMV0rJyAnKyhtWzJdfHwnJykpOyB9CiAgfQogIHJldHVybiByZXM7Cn0KZnVuY3Rpb24gbm9tYnJlRGVUZXh0byh0KXsKICB2YXIgVD0odHx8JycpLnRvVXBwZXJDYXNlKCksIGNhbmQ9W10sIG0sIGk7CiAgdmFyIHJlPS8oTk9NQlJFUz98QVBFTExJRE9TP3xOQU1FUz98U1VSTkFNRSlccypbOlwuXC1dP1xzKigoPzpbQS1aXHUwMEMxXHUwMEM5XHUwMENEXHUwMEQzXHUwMERBXHUwMERDXHUwMEQxXVtBLVpcdTAwQzFcdTAwQzlcdTAwQ0RcdTAwRDNcdTAwREFcdTAwRENcdTAwRDFdezEsMTV9KSg/Oltcc1wuXStbQS1aXHUwMEMxXHUwMEM5XHUwMENEXHUwMEQzXHUwMERBXHUwMERDXHUwMEQxXVtBLVpcdTAwQzFcdTAwQzlcdTAwQ0RcdTAwRDNcdTAwREFcdTAwRENcdTAwRDFdezEsMTV9KXswLDR9KS9nOwogIHdoaWxlKChtPXJlLmV4ZWMoVCkpIT09bnVsbCl7IGlmKG1bMl0peyBjYW5kLnB1c2gobVsyXSk7IH0gfQogIGNhbmQ9Y2FuZC5jb25jYXQobXJ6Tm9tYnJlcyhUKSk7CiAgdmFyIGxpbmVzPVQuc3BsaXQoL1tcclxuXSsvKTsKICBmb3IoaT0wO2k8bGluZXMubGVuZ3RoO2krKyl7CiAgICB2YXIgdz1saW5lc1tpXS5yZXBsYWNlKC9bXkEtWlx1MDBDMVx1MDBDOVx1MDBDRFx1MDBEM1x1MDBEQVx1MDBEQ1x1MDBEMSBdL2csJyAnKS50cmltKCkuc3BsaXQoL1xzKy8pLmZpbHRlcihmdW5jdGlvbih4KXsgcmV0dXJuIHgubGVuZ3RoPj0zOyB9KTsKICAgIGlmKHcubGVuZ3RoPj0yICYmIHcubGVuZ3RoPD00KXsgY2FuZC5wdXNoKHcuam9pbignICcpKTsgfQogIH0KICByZXR1cm4gY2FuZDsKfQpmdW5jdGlvbiB0b2tlbnNEZShzKXsgcmV0dXJuIG5vcm0ocykuc3BsaXQoJyAnKS5maWx0ZXIoZnVuY3Rpb24oeCl7IHJldHVybiB4Lmxlbmd0aD4xOyB9KTsgfQovKiB2MTY6IGNvbmZ1c2lvbmVzIHRpcGljYXMgZGVsIE9DUiBlbiBkb2N1bWVudG9zICgwL08vUS9EL0MsIDEvSS9ML1QsCiAgIDUvUy9aLCA4L0IsIDYvRywgMi9aLCBWL1UsIFIvTCwgTS9OL0gsIFAvRik6IFVOIGNhcmFjdGVyIGRpc3RpbnRvIGRlCiAgIGVzZSBncnVwbyBjdWVudGEgY29tbyBsYSBNSVNNQSBsZXRyYSBhbCBjb21wYXJhciB0dSBub21icmUgY29uIGxvCiAgIHF1ZSBsZXlvIGVsIE9DUi4gKi8KdmFyIENPTkZfT0NSPXsnTyc6JzBRRENFRycsJzAnOidPUURDRUcnLCdRJzonTzBERycsJ0QnOidPMFFDQicsJ0MnOidPMFFHRUInLCdHJzonQzBPUTYnLCdFJzonRkJHTzAnLCdCJzonOEVSM08wJywnOCc6J0JSMycsJzMnOidCOCcsJ0knOicxTEpUJywnMSc6J0lMSlQ3JywnTCc6JzFJSlRSJywnSic6JzFMSVQnLCdUJzonMUlMNycsJ1MnOic1WkcnLCc1JzonU1onLCdaJzonMjVTJywnMic6J1pTJywnNic6J0dCJywnVSc6J1YnLCdWJzonVScsJ00nOidOSCcsJ04nOidNSCcsJ0gnOidOTScsJ0snOidYJywnWCc6J0snLCdQJzonRlInLCdGJzonUFRFJywnUic6J1BMRksnfTsKZnVuY3Rpb24gY29uZnVzb3MoYSxiKXsKICBpZihhPT09Yil7IHJldHVybiB0cnVlOyB9CiAgaWYoIWF8fCFifHxhLmxlbmd0aCE9PWIubGVuZ3RoKXsgcmV0dXJuIGZhbHNlOyB9CiAgdmFyIGQ9MCwgcG9zPS0xLCBpOwogIGZvcihpPTA7aTxhLmxlbmd0aDtpKyspeyBpZihhW2ldIT09YltpXSl7IGQrKzsgcG9zPWk7IGlmKGQ+MSl7IHJldHVybiBmYWxzZTsgfSB9IH0KICBpZihkIT09MSl7IHJldHVybiBmYWxzZTsgfQogIHZhciB4PWFbcG9zXSwgeT1iW3Bvc107CiAgcmV0dXJuICEhKENPTkZfT0NSW3hdJiZDT05GX09DUlt4XS5pbmRleE9mKHkpPj0wKTsKfQpmdW5jdGlvbiBwYXJQYXJlY2lkbyh0MSx0Mil7CiAgaWYodDE9PT10Mil7IHJldHVybiB0cnVlOyB9CiAgaWYoc2ltUGFyKHQxLHQyKT49MC43OCl7IHJldHVybiB0cnVlOyB9CiAgaWYodDEubGVuZ3RoPj00JiZ0Mi5sZW5ndGg+PTQmJih0MS5pbmRleE9mKHQyKT09PTB8fHQyLmluZGV4T2YodDEpPT09MCkpeyByZXR1cm4gdHJ1ZTsgfQogIGlmKHQxLmxlbmd0aD49NCYmdDIubGVuZ3RoPj00JiZjb25mdXNvcyh0MSx0MikpeyByZXR1cm4gdHJ1ZTsgfQogIHJldHVybiBmYWxzZTsKfQovKiA9PT09PT09PT09PT0gZ3VhcmRpYW5hcyBkZSBsYSBsZWN0dXJhIGNvbmZpcm1hZGEgKHBhc28gMikgPT09PT09PT09PT09ICovCmZ1bmN0aW9uIHRva2Vuc05vbWJyZURlKHRleHRvKXsKICB2YXIgVD1ub3JtKHRleHRvKS5zcGxpdCgnICcpLCBvdXQ9W10sIGksIGo7CiAgZm9yKGk9MDtpPFQubGVuZ3RoO2krKyl7CiAgICB2YXIgdD1UW2ldOwogICAgaWYodC5sZW5ndGg8M3x8dC5sZW5ndGg+MTUpeyBjb250aW51ZTsgfQogICAgaWYoIS9eW0EtWl0rJC8udGVzdCh0KSl7IGNvbnRpbnVlOyB9CiAgICB2YXIgbWFsYT1mYWxzZTsKICAgIGZvcihqPTA7ajxQQUxBQlJBU19OT19OT01CUkUubGVuZ3RoO2orKyl7IGlmKHQuaW5kZXhPZihQQUxBQlJBU19OT19OT01CUkVbal0pPT09MCl7IG1hbGE9dHJ1ZTsgYnJlYWs7IH0gfQogICAgaWYoIW1hbGEpeyBvdXQucHVzaCh0KTsgfQogIH0KICByZXR1cm4gb3V0Owp9CmZ1bmN0aW9uIGVkaWNpb25BY2VwdGFibGUodGV4dG9FZGl0YWRvLCBvY3JUb2tzKXsKICB2YXIgdG9rcz10b2tlbnNEZSh0ZXh0b0VkaXRhZG8pLCBpLCBqOwogIGlmKCF0b2tzLmxlbmd0aHx8IW9jclRva3N8fCFvY3JUb2tzLmxlbmd0aCl7IHJldHVybiBmYWxzZTsgfQogIGZvcihpPTA7aTx0b2tzLmxlbmd0aDtpKyspewogICAgdmFyIHBhc2E9ZmFsc2U7CiAgICBmb3Ioaj0wO2o8b2NyVG9rcy5sZW5ndGg7aisrKXsKICAgICAgaWYocGFyUGFyZWNpZG8odG9rc1tpXSxvY3JUb2tzW2pdKSl7IHBhc2E9dHJ1ZTsgYnJlYWs7IH0KICAgICAgaWYodG9rc1tpXS5sZW5ndGg+PTUmJm9jclRva3Nbal0ubGVuZ3RoPj01JiZsZXYodG9rc1tpXSxvY3JUb2tzW2pdKTw9Mil7IHBhc2E9dHJ1ZTsgYnJlYWs7IH0KICAgIH0KICAgIGlmKCFwYXNhKXsgcmV0dXJuIGZhbHNlOyB9CiAgfQogIHJldHVybiB0cnVlOwp9CnZhciBQQUxBQlJBU19OT19OT01CUkU9WydET01JQ0lMSU8nLCdESVJFQ0NJT04nLCdDT0xPTklBJywnQkFSUklPJywnUkVTSURFTkNJQScsJ0NBU0VSSU8nLCdDQU5UT04nLCdBTERFQScsJ1NFQ1RPUicsJ09CU0VSVkFDSU9OJywnRVNUQURPJywnRE9OQU5URScsJ0dSVVBPJywnU0FOR1JFJywnU0FORycsJ01VTklDSVBJTycsJ0RFUEFSVEFNRU5UTycsJ0ZFQ0hBJywnTkFDSU1JRU5UTycsJ1NFWE8nLCdOQUNJT05BTElEQUQnLCdGT0xJTycsJ05VTUVSTycsJ0RPQ1VNRU5UTycsJ0NFRFVMQScsJ0lERU5USURBRCcsJ0xJQ0VOQ0lBJywnUkVQVUJMSScsJ1NFQ1JFVEFSSUEnLCdFTUlTSU9OJywnVkVOQ0lNSUVOVE8nLCdDTEFTRScsJ0NBVEVHT1JJQScsJ0VORE9SU0VNRU5UJywnUkVTVFJJQ1RJT04nLCdBRERSRVNTJywnTFVHQVInLCdFREFEJywnUEFSRU4nLCdGSUxJQUNJT04nLCdGSUxJQUNJT04nLCdNQVJDQScsJ1NQRUNJTUVOJywnU0FNUExFJywnVk9UQUNJT04nLCdUT01BRE9SJywnTkFDSU8nLCdET00nLCdOT01CUkVTJywnTk9NQlJFJywnQVBFTExJRE9TJywnQVBFTExJRE8nLCdDSVVEQUQnLCdBVkVOSURBJywnQk9VTEVWQVJEJywnRFVJJywnRFBJJ107CmZ1bmN0aW9uIHBhcmVjZU5vbWJyZUxpbmVhKGMpewogIHZhciB3PShjfHwnJykuc3BsaXQoJyAnKS5maWx0ZXIoZnVuY3Rpb24oeCl7IHJldHVybiB4Lmxlbmd0aD4xOyB9KTsKICBpZih3Lmxlbmd0aDwyfHx3Lmxlbmd0aD41KXsgcmV0dXJuIGZhbHNlOyB9CiAgdmFyIG1hbG9zPXsnRUwnOjEsJ0xBJzoxLCdMT1MnOjEsJ0xBUyc6MSwnREUnOjEsJ0RFTCc6MX07CiAgZm9yKHZhciBpPTA7aTx3Lmxlbmd0aDtpKyspewogICAgaWYobWFsb3Nbd1tpXV0peyByZXR1cm4gZmFsc2U7IH0KICAgIGZvcih2YXIgaj0wO2o8UEFMQUJSQVNfTk9fTk9NQlJFLmxlbmd0aDtqKyspeyBpZih3W2ldLmluZGV4T2YoUEFMQUJSQVNfTk9fTk9NQlJFW2pdKT09PTApeyByZXR1cm4gZmFsc2U7IH0gfQogIH0KICByZXR1cm4gdHJ1ZTsKfQpmdW5jdGlvbiBub21icmVDb2luY2lkZShlc2NyaXRvLCB0ZXh0b0RvYywgZXN0cmljdG8pewogIHZhciB2YWNpbz17b2s6ZmFsc2UsIGxlaWRvOicnLCBwdW50OjAsIGhheTpmYWxzZX07CiAgdmFyIFU9dG9rZW5zRGUoZXNjcml0byk7CiAgaWYoVS5sZW5ndGg8Mil7IHJldHVybiB2YWNpbzsgfQogIHZhciBjYW5kPW5vbWJyZURlVGV4dG8odGV4dG9Eb2MpLCBsaW1waW9zPVtdLCBpLCBrOwogIGZvcihpPTA7aTxjYW5kLmxlbmd0aDtpKyspewogICAgdmFyIGM9bm9ybShjYW5kW2ldKTsKICAgIGlmKCFjKXsgY29udGludWU7IH0KICAgIHZhciB0b2tzPWMuc3BsaXQoJyAnKS5maWx0ZXIoZnVuY3Rpb24oeCl7IHJldHVybiB4Lmxlbmd0aD4xOyB9KTsKICAgIGlmKHRva3MubGVuZ3RoPDJ8fHRva3MubGVuZ3RoPjUpeyBjb250aW51ZTsgfQogICAgaWYoIXBhcmVjZU5vbWJyZUxpbmVhKGMpKXsgY29udGludWU7IH0KICAgIGxpbXBpb3MucHVzaCh0b2tzKTsKICB9CiAgdmFyIFQyPW5vcm0odGV4dG9Eb2MpLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7CiAgdmFyIHZpc3Rhcz17fSwgaTIsIEwyOwogIGZvcihpMj0wO2kyPGxpbXBpb3MubGVuZ3RoO2kyKyspeyB2aXN0YXNbbGltcGlvc1tpMl0uam9pbignICcpXT0xOyB9CiAgZm9yKGkyPTA7aTI8VDIubGVuZ3RoO2kyKyspewogICAgZm9yKEwyPTI7TDI8PTQgJiYgaTIrTDI8PVQyLmxlbmd0aDtMMisrKXsKICAgICAgdmFyIHdpbj1UMi5zbGljZShpMixpMitMMikuam9pbignICcpOwogICAgICBpZighdmlzdGFzW3dpbl0gJiYgcGFyZWNlTm9tYnJlTGluZWEod2luKSl7IHZpc3Rhc1t3aW5dPTE7IGxpbXBpb3MucHVzaCh3aW4uc3BsaXQoJyAnKSk7IH0KICAgIH0KICB9CiAgaWYoIWxpbXBpb3MubGVuZ3RoKXsgcmV0dXJuIHZhY2lvOyB9CiAgdmFyIHVuaW9uPXt9LCBjbGF2ZXM9W107CiAgZm9yKGk9MDtpPGxpbXBpb3MubGVuZ3RoO2krKyl7CiAgICBmb3Ioaz0wO2s8bGltcGlvc1tpXS5sZW5ndGg7aysrKXsKICAgICAgaWYoIXVuaW9uW2xpbXBpb3NbaV1ba11dKXsgdW5pb25bbGltcGlvc1tpXVtrXV09MTsgY2xhdmVzLnB1c2gobGltcGlvc1tpXVtrXSk7IH0KICAgIH0KICB9CiAgZnVuY3Rpb24gY3VhbnRvcyhsaXN0YSl7CiAgICB2YXIgbj0wLCBqLCB0OwogICAgZm9yKGo9MDtqPFUubGVuZ3RoO2orKyl7CiAgICAgIGZvcih0PTA7dDxsaXN0YS5sZW5ndGg7dCsrKXsgaWYocGFyUGFyZWNpZG8oVVtqXSxsaXN0YVt0XSkpeyBuKys7IGJyZWFrOyB9IH0KICAgIH0KICAgIHJldHVybiBuOwogIH0KICB2YXIgbWVqb3JDYW5kPScnLCBtZWpvckNvdj0wOwogIGZvcihpPTA7aTxsaW1waW9zLmxlbmd0aDtpKyspewogICAgdmFyIGNvdj1jdWFudG9zKGxpbXBpb3NbaV0pL1UubGVuZ3RoOwogICAgaWYoY292Pm1lam9yQ292KXsgbWVqb3JDb3Y9Y292OyBtZWpvckNhbmQ9bGltcGlvc1tpXS5qb2luKCcgJyk7IH0KICB9CiAgdmFyIGNvdlU9Y3VhbnRvcyhjbGF2ZXMpL1UubGVuZ3RoOwogIGlmKGNvdlU+bWVqb3JDb3YpeyBtZWpvckNvdj1jb3ZVOyB9CiAgdmFyIG5NYXRjaD1jdWFudG9zKGNsYXZlcyksIG1lam9yU2ltPTAsIGozLCB0MzsKICBmb3IoajM9MDtqMzxVLmxlbmd0aDtqMysrKXsKICAgIGZvcih0Mz0wO3QzPGNsYXZlcy5sZW5ndGg7dDMrKyl7CiAgICAgIGlmKHBhclBhcmVjaWRvKFVbajNdLGNsYXZlc1t0M10pKXsgdmFyIHN2PXNpbVBhcihVW2ozXSxjbGF2ZXNbdDNdKTsgaWYoc3Y+bWVqb3JTaW0peyBtZWpvclNpbT1zdjsgfSB9CiAgICB9CiAgfQogIC8qIHYxNjogcmVnbGFzIE5VRVZBUy4gQW50ZXMsIHNpIGVsIHRleHRvIHRyYWlhIE1SWiAocmV2ZXJzbyBvIHVuCiAgICAgZmFsc28gcG9zaXRpdm8pLCBzb2xvIHBhc2FiYSBjb24gVE9EQVMgdHVzIHBhbGFicmFzIGxlaWRhczogY29uCiAgICAgZWwgTVJaIGEgbWVkaWFzICgiTUlSQSBKT1NFIEFMRk9OU08iIHNpbiBaRUxBWUEpIHRlIGJvdGFiYSBhbAogICAgIHBhc28gMSB5IHNlIHBlcmRpYSB0b2RvLiBBaG9yYSBlbCBNUlogcGFyY2lhbCB5YSBubyBjYXN0aWdhOgogICAgIGJhc3RhIHF1ZSBVTkEgZGUgdHVzIHBhbGFicmFzIGVzdGUgYmllbiBsZWlkYSwgeSBsYXMgY29uZnVzaW9uZXMKICAgICB0aXBpY2FzIGRlbCBPQ1IgKE8vMCwgSS8xL0wsIFMvNSwgQi84LCBSL0wuLi4pIHZhbGVuIGNvbW8gbGEKICAgICBtaXNtYSBsZXRyYS4gTGEgaWRlbnRpZGFkIHJlYWwgbGEgY29uZmlybWEgZWwgbW90b3IgZmFjaWFsLiAqLwogIHZhciBvazsKICBpZihtZWpvckNvdj49MC45OTkpeyBvaz10cnVlOyB9CiAgZWxzZSBpZihuTWF0Y2g+PTIgJiYgY292VT49MC41KXsgb2s9dHJ1ZTsgfQogIGVsc2UgaWYobk1hdGNoPj0xICYmIGNvdlU+PTAuNSl7IG9rPXRydWU7IH0KICBlbHNlIGlmKG5NYXRjaD49MSAmJiBtZWpvclNpbT49MC45OCl7IG9rPXRydWU7IH0KICBlbHNleyBvaz1mYWxzZTsgfQogIHJldHVybiB7b2s6b2ssIGxlaWRvOm1lam9yQ2FuZCwgcHVudDptZWpvckNvdiwgaGF5OnRydWV9Owp9CgovKiA9PT09PT09PT09PT09PT09PSBkZXRlY2Npb24gZGUgbGFkbyA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBkZXRlY3RhckxhZG8odGV4dG8sIHRpZW5lQ2FyYSl7CiAgdmFyIHQ9KHRleHRvfHwnJykudG9VcHBlckNhc2UoKTsKICB2YXIgcmV2PTAsIGZyZT0wLCBpOwogIHZhciBsdD0odC5tYXRjaCgvPC9nKXx8W10pLmxlbmd0aDsKICBpZihsdD49Nil7IHJldHVybiAncmV2ZXJzbyc7IH0KICBpZigvUERGNEk/Ny8udGVzdCh0LnJlcGxhY2UoL1xzL2csJycpKSl7IHJldis9Mi41OyB9CiAgdmFyIFJWcz1bJ0RPTUlDSUxJTycsJ0RJUkVDQ0lPTicsJ0RJUkVDQ0lcdTAwRDNOJywnQ09MT05JQScsJ0JBUlJJTycsJ1JFU0lERU5DSUEnLCdDQVNFUklPJywnQ0FOVE9OJywnQUxERUEnLCdTRUNUT1InLCdPQlNFUlZBQ0lPTicsJ09CU0VSVkFDSVx1MDBEM04nLCdET05BTlRFJywnR1JVUE8gU0FORycsJ1RJUE8gREUgU0FORycsJ1NBTkdVSU5FTycsJ0VTVEFETyBDSVZJTCcsJ0VORE9SU0VNRU5UJywnUkVTVFJJQ1RJT04nLCdNVU5JQ0lQSU8nXTsKICB2YXIgUlZ3PVsnRU1JU0lPTicsJ0VNSVNJXHUwMEQzTicsJ1ZFTkNJTUlFTlRPJywnVkVOQ0UnLCdFWFBJUkVTJywnSVNTVUVEJywnVkFMSURFWicsJ0VYUElSQScsJ0NMQVNFJywnQ0FURUdPUklBJywnQ0FURUdPUlx1MDBDREEnLCdJU1MnLCdFWFAnXTsKICB2YXIgRlI9WydOT01CUkVTJywnQVBFTExJRE9TJywnTkFNRVMnLCdTVVJOQU1FJywnR0lWRU4nLCdEVUknLCdET0NVTUVOVE8gVU5JQ08nLCdET0NVTUVOVE8gXHUwMERBTklDTycsJ0NFRFVMQScsJ0NcdTAwQzlEVUxBJywnSURFTlRJREFEJywnTElDRU5DSUEnLCdEUklWRVInLCdOQUNJTUlFTlRPJywnQklSVEgnLCdTRVhPJywnU0VYJywnTkFDSU9OQUxJREFEJywnTkFDSU9OQUxJVFknLCdGT0xJTycsJ1JFUFVCTEknLCdOVU1FUk8nLCdOXHUwMERBTUVSTycsJ05VTUJFUicsJ0lEIE5PJ107CiAgZm9yKGk9MDtpPFJWcy5sZW5ndGg7aSsrKXsgaWYodC5pbmRleE9mKFJWc1tpXSk+PTApeyByZXYrPTI7IH0gfQogIGZvcihpPTA7aTxSVncubGVuZ3RoO2krKyl7IGlmKHQuaW5kZXhPZihSVndbaV0pPj0wKXsgcmV2Kz0wLjc1OyB9IH0KICBmb3IoaT0wO2k8RlIubGVuZ3RoO2krKyl7IGlmKHQuaW5kZXhPZihGUltpXSk+PTApeyBmcmUrPTE7IH0gfQogIGlmKHRpZW5lQ2FyYSl7IGZyZSs9NDsgfQogIGlmKHJldj49My41ICYmIHJldj5mcmUrMSl7IHJldHVybiAncmV2ZXJzbyc7IH0KICBpZihmcmU+PTMgJiYgZnJlPnJldisxKXsgcmV0dXJuICdmcmVudGUnOyB9CiAgaWYocmV2PmZyZSAmJiByZXY+PTIpeyByZXR1cm4gJ3JldmVyc28nOyB9CiAgaWYoZnJlPnJldiAmJiBmcmU+PTIpeyByZXR1cm4gJ2ZyZW50ZSc7IH0KICByZXR1cm4gJ2Rlc2Nvbm9jaWRvJzsKfQoKLyogPT09PT09PT09PT09PT09PT0gZ2FuY2hvIHBhcmEgcHJ1ZWJhcyAobm9kZSwgc2luIERPTSkgPT09PT09PT09PT09PT09PT0gKi8KaWYgKHR5cGVvZiBkb2N1bWVudD09PSd1bmRlZmluZWQnIHx8IHR5cGVvZiBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCE9PSdmdW5jdGlvbicpewogIFcuX19aWVJBX1RFU1RfXz17bm9ybTpub3JtLGxldjpsZXYsc2ltUGFyOnNpbVBhcixzaW1Ob21icmVzOnNpbU5vbWJyZXMsbXJ6TGluZWFzOm1yekxpbmVhcyxtcnpOb21icmVzOm1yek5vbWJyZXMsbm9tYnJlRGVUZXh0bzpub21icmVEZVRleHRvLG5vbWJyZUNvaW5jaWRlOm5vbWJyZUNvaW5jaWRlLGRldGVjdGFyTGFkbzpkZXRlY3RhckxhZG8sZXZhbHVhQ2FyYTpldmFsdWFDYXJhLGVhckRlOmVhckRlLGNlbnRyb0RlOmNlbnRyb0RlLHF1YWRWYWxpZG86cXVhZFZhbGlkbyxhcmVhUXVhZDphcmVhUXVhZCxldGlxdWV0YUNvbXBvbmVudGVzOmV0aXF1ZXRhQ29tcG9uZW50ZXMsZXNxdWluYXNEZU1hc2NhcmE6ZXNxdWluYXNEZU1hc2NhcmEsbWVkaWFuYVF1YWQ6bWVkaWFuYVF1YWQscXVhZEVzdGFibGU6cXVhZEVzdGFibGUsbml0b0RlOm5pdG9EZSxmcmFjY2lvbkJsYW5jbzpmcmFjY2lvbkJsYW5jbyx0b2tlbnNOb21icmVEZTp0b2tlbnNOb21icmVEZSxlZGljaW9uQWNlcHRhYmxlOmVkaWNpb25BY2VwdGFibGUsZWxlZ2lyVGV4dG86ZWxlZ2lyVGV4dG8scGFyUGFyZWNpZG86cGFyUGFyZWNpZG8sdG9rZW5zRGU6dG9rZW5zRGUsdG9kb09rUGFyYUNyZWFyOnRvZG9Pa1BhcmFDcmVhcixjYWphRGVRdWFkOmNhamFEZVF1YWR9OwogIHJldHVybjsKfQoKLyogPT09PT09PT09PT09PT09PT0gZ2FuY2hvIGRlIHBydWViYXMgY29uIERPTSBzaW11bGFkbyA9PT09PT09PT09PT09PT09PSAqLwpXLl9fWllSQV9SRVZGX1RFU1RfXz17fTsKCi8qID09PT09PT09PT09PT09PT09IGZldGNoIGNvbiByZWludGVudG9zICsgd2FybXVwID09PT09PT09PT09PT09PT09ICovCihmdW5jdGlvbigpewogIGlmKFcuX196eUZldGNoRml4KXsgcmV0dXJuOyB9CiAgVy5fX3p5RmV0Y2hGaXg9MTsKICB2YXIgX2Y9Vy5mZXRjaD9XLmZldGNoLmJpbmQoVyk6bnVsbDsKICBpZighX2YpeyByZXR1cm47IH0KICBXLmZldGNoPWZ1bmN0aW9uKCl7CiAgICB2YXIgYXJncz1hcmd1bWVudHMsIG49MDsKICAgIGZ1bmN0aW9uIG90cm8oKXsgcmV0dXJuIF9mLmFwcGx5KG51bGwsYXJncykudGhlbihmdW5jdGlvbihyKXsKICAgICAgaWYoWzUwMCw1MDIsNTAzLDUwNCw0MTNdLmluZGV4T2Yoci5zdGF0dXMpPj0wICYmIG48Myl7IG4rKzsgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7IHNldFRpbWVvdXQocmVzLDcwMCpuKTsgfSkudGhlbihvdHJvKTsgfQogICAgICByZXR1cm4gcjsKICAgIH0sIGZ1bmN0aW9uKGUpewogICAgICBpZihuPDMpeyBuKys7IHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpeyBzZXRUaW1lb3V0KHJlcyw3MDAqbik7IH0pLnRoZW4ob3Rybyk7IH0KICAgICAgdGhyb3cgZTsKICAgIH0pOyB9CiAgICByZXR1cm4gb3RybygpOwogIH07CiAgdHJ5eyBfZihXLmxvY2F0aW9uLnBhdGhuYW1lLHtjYWNoZTonbm8tc3RvcmUnLGhlYWRlcnM6eyd4LXp5LXdhcm11cCc6JzEnfX0pLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH1jYXRjaChlKXt9Cn0pKCk7CgovKiA9PT09PT09PT09PT09PT09PSBlc3RhZG8gZGVsIGZsdWpvID09PT09PT09PT09PT09PT09ICovCnZhciBFU1Q9e3Bhc286MSwgcGFzb01heDoxLCB0aXBvOidkZXNjb25vY2lkbycsIG5lY2VzaXRhUmV2ZXJzbzp0cnVlLCBub21icmVPazpmYWxzZSwgZnJlbnRlT2s6ZmFsc2UsIHJldmVyc29PazpmYWxzZSwgc2VsZmllT2s6ZmFsc2UsIGludGVudG9zOjUsIGZyZW50ZUltZzonJywgcmV2ZXJzb0ltZzonJywgc2VsZmllSW1nOicnLCBlc2NyaXRvOicnLCBmcmVudGVUZXh0bzonJywgcmV2ZXJzb1RleHRvOicnLCBjYXJhVml2YTpudWxsLCBjYXJhRG9jOm51bGx9Owp2YXIgc3RyZWFtcz17fTsKdmFyIEhJTlRTPXt9OwoKZnVuY3Rpb24gY2xhc2lmaWNhclRpcG8oKXsKICB2YXIgc2VsPSQoJ3RpcG9Eb2MnKSwgdHh0PScnOwogIGlmKHNlbCl7CiAgICB2YXIgb3A9c2VsLm9wdGlvbnMgJiYgc2VsLm9wdGlvbnNbc2VsLnNlbGVjdGVkSW5kZXhdOwogICAgdHh0PShvcCYmb3AudGV4dD9vcC50ZXh0OicnKSsnICcrKHNlbC52YWx1ZXx8JycpOwogIH0KICB0eHQ9dHh0LnRvTG93ZXJDYXNlKCk7CiAgaWYoL3Bhc2Fwb3J0ZXxwYXNzcG9ydC8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOidwYXNhcG9ydGUnLCByZXZlcnNvOmZhbHNlfTsgfQogIGlmKC9zYWx2YWRvcnxcYmR1aVxiLy50ZXN0KHR4dCkpeyByZXR1cm4ge2s6J2R1aScsIHJldmVyc286dHJ1ZX07IH0KICBpZigvZ3VhdGVtYWxhfGd1YXRlLy50ZXN0KHR4dCkpeyByZXR1cm4ge2s6J2d0JywgcmV2ZXJzbzp0cnVlfTsgfQogIGlmKC9uaWNhcmFndWEvLnRlc3QodHh0KSl7IHJldHVybiB7azonbmknLCByZXZlcnNvOnRydWV9OyB9CiAgaWYoL2hvbmR1cmFzLy50ZXN0KHR4dCkpeyByZXR1cm4ge2s6J2huJywgcmV2ZXJzbzp0cnVlfTsgfQogIGlmKC91c2F8ZXN0YWRvcyB1bmlkb3N8bGljZW5jaWF8bGljZW5zZXxkcml2ZXIvLnRlc3QodHh0KSl7IHJldHVybiB7azondXNhJywgcmV2ZXJzbzp0cnVlfTsgfQogIGlmKC9vdHJvfG90aGVyLy50ZXN0KHR4dCkpeyByZXR1cm4ge2s6J290cm8nLCByZXZlcnNvOnRydWV9OyB9CiAgcmV0dXJuIHtrOidkZXNjb25vY2lkbycsIHJldmVyc286dHJ1ZX07Cn0KCi8qID09PT09PT09PT09PT09PT09IG1lbnNhamVzIHkgYXl1ZGFzID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIG1zZyhpZCx0ZXh0byxjb2xvcil7CiAgdmFyIGVsPSQoaWQpOwogIGlmKCFlbCAmJiBISU5UU1tpZF0peyBlbD1ISU5UU1tpZF07IH0KICBpZighZWwpewogICAgdmFyIGFuY2xhPSQoJ3BzMScpOwogICAgZWw9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2Jyk7CiAgICBlbC5pZD1pZDsKICAgIGVsLnN0eWxlLmNzc1RleHQ9J2ZvbnQtc2l6ZToxM3B4O21hcmdpbjo2cHggMDtsaW5lLWhlaWdodDoxLjM1Oyc7CiAgICBpZihhbmNsYSAmJiBhbmNsYS5wYXJlbnROb2RlKXsgYW5jbGEucGFyZW50Tm9kZS5pbnNlcnRCZWZvcmUoZWwsYW5jbGEubmV4dFNpYmxpbmcpOyB9CiAgICBlbHNleyBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKGVsKTsgfQogICAgSElOVFNbaWRdPWVsOwogIH0KICBlbC50ZXh0Q29udGVudD10ZXh0b3x8Jyc7CiAgaWYoY29sb3IpeyBlbC5zdHlsZS5jb2xvcj1jb2xvcjsgfQp9CmZ1bmN0aW9uIGJ1c3kob24pewogIHZhciBpZHM9WydibG9jRicsJ2Jsb2NBJywnYmxvY1MnXSwgaTsKICBmb3IoaT0wO2k8aWRzLmxlbmd0aDtpKyspeyB2YXIgYj0kKGlkc1tpXSk7IGlmKGIpeyBiLnN0eWxlLmRpc3BsYXk9b24/J2ZsZXgnOidub25lJzsgfSB9Cn0KZnVuY3Rpb24gc2hvd0ltZyhpZCxkYXRhVXJsKXsKICB2YXIgcD0kKGlkKTsKICBpZihwKXsKICAgIHAuc3JjPWRhdGFVcmw7CiAgICBwLnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsKICAgIHAuc3R5bGUubWF4V2lkdGg9JzI0MHB4JzsKICAgIHAuc3R5bGUubWF4SGVpZ2h0PScyNDBweCc7CiAgICBwLnN0eWxlLndpZHRoPSdhdXRvJzsKICAgIHAuc3R5bGUuaGVpZ2h0PSdhdXRvJzsKICAgIHAuc3R5bGUuYm9yZGVyUmFkaXVzPScxMHB4JzsKICAgIHAuc3R5bGUubWFyZ2luPSc4cHggYXV0byc7CiAgICBwLnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsKICB9Cn0KCi8qID09PT09PT09PT09PT09PT09IGNhbWFyYTogcHJldmlldyBTSUVNUFJFIGNoaWNvID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIGxldHJhRGUocHNJZCl7IHJldHVybiAoeycyJzonRicsJzMnOidBJywnNCc6J1MnfSlbcHNJZF18fCdGJzsgfQpmdW5jdGlvbiBmaW5kVmlkZW8ocHNJZCl7CiAgdmFyIGxldHJhPWxldHJhRGUocHNJZCk7CiAgdmFyIGlkcz1bJ3Z6JytsZXRyYSwndmQnK2xldHJhLCd2JytsZXRyYV0sIGk7CiAgdmFyIGNvbnQ9JCgncHMnK3BzSWQpOwogIGZvcihpPTA7aTxpZHMubGVuZ3RoO2krKyl7CiAgICB2YXIgY2FuZD0kKGlkc1tpXSk7CiAgICBpZihjYW5kICYmIGNhbmQudGFnTmFtZT09PSdWSURFTycpeyByZXR1cm4gY2FuZDsgfQogIH0KICBpZihjb250KXsKICAgIHZhciB2PWNvbnQucXVlcnlTZWxlY3RvcigndmlkZW8nKTsKICAgIGlmKHYpeyByZXR1cm4gdjsgfQogIH0KICByZXR1cm4gbnVsbDsKfQpmdW5jdGlvbiBlc3RpbG9DaGljbyh2KXsKICBpZighdil7IHJldHVybjsgfQogIHYuc3R5bGUubWF4V2lkdGg9JzI4MHB4JzsKICB2LnN0eWxlLndpZHRoPScxMDAlJzsKICB2LnN0eWxlLm1heEhlaWdodD0nMzIwcHgnOwogIHRyeXsgdi5zdHlsZS5hc3BlY3RSYXRpbz0nMyAvIDQnOyB9Y2F0Y2goZSl7fQogIHYuc3R5bGUub2JqZWN0Rml0PSdjb3Zlcic7CiAgdi5zdHlsZS5ib3JkZXJSYWRpdXM9JzEycHgnOwogIHYuc3R5bGUuYmFja2dyb3VuZD0nIzAwMCc7CiAgdi5zdHlsZS5kaXNwbGF5PSdibG9jayc7CiAgdi5zdHlsZS5tYXJnaW49JzAgYXV0byc7Cn0KZnVuY3Rpb24gdmlicmFyKCl7IHRyeXsgaWYobmF2aWdhdG9yLnZpYnJhdGUpeyBuYXZpZ2F0b3IudmlicmF0ZSg3MCk7IH0gfWNhdGNoKGUpe30gfQpmdW5jdGlvbiBhbGluZWFyT3ZlcmxheShwc0lkLCB2KXsKICB0cnl7CiAgICB2YXIgT1Y9eycyJzonb3ZGJywnMyc6J292QScsJzQnOidvdlMnfTsKICAgIHZhciBvdj0kKE9WW3BzSWRdKTsgaWYoIW92fHwhdil7IHJldHVybjsgfQogICAgdmFyIHo9JCgndnonK2xldHJhRGUocHNJZCkpOyBpZigheil7IHJldHVybjsgfQogICAgdmFyIHZyPXYuZ2V0Qm91bmRpbmdDbGllbnRSZWN0KCksIHpyPXouZ2V0Qm91bmRpbmdDbGllbnRSZWN0KCk7CiAgICBpZighdnIud2lkdGh8fCF2ci5oZWlnaHQpeyByZXR1cm47IH0KICAgIG92LnN0eWxlLnBvc2l0aW9uPSdhYnNvbHV0ZSc7CiAgICBvdi5zdHlsZS5sZWZ0PU1hdGgucm91bmQodnIubGVmdC16ci5sZWZ0KSsncHgnOwogICAgb3Yuc3R5bGUudG9wPU1hdGgucm91bmQodnIudG9wLXpyLnRvcCkrJ3B4JzsKICAgIG92LnN0eWxlLndpZHRoPXZyLndpZHRoKydweCc7CiAgICBvdi5zdHlsZS5oZWlnaHQ9dnIuaGVpZ2h0KydweCc7CiAgICB0cnl7IG92LnN0eWxlLm9iamVjdEZpdD0nY292ZXInOyB9Y2F0Y2goZTIpe30KICAgIG92LnN0eWxlLmJvcmRlclJhZGl1cz0nMTJweCc7CiAgICBvdi5zdHlsZS56SW5kZXg9JzUnOwogIH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24genlEZXQoKXsgaWYoIVcuX196eURldCl7IFcuX196eURldD17fTsgfSByZXR1cm4gVy5fX3p5RGV0OyB9CmZ1bmN0aW9uIG90c3VVbWJyYWwoaGlzdCx0b3RhbCl7CiAgdmFyIHN1bT0wLGk7IGZvcihpPTA7aTwyNTY7aSsrKXsgc3VtKz1pKmhpc3RbaV07IH0KICB2YXIgc3VtQj0wLHdCPTAsYmVzdD0wLHRocj0xMjc7CiAgZm9yKGk9MDtpPDI1NjtpKyspewogICAgd0IrPWhpc3RbaV07IGlmKHdCPT09MCl7IGNvbnRpbnVlOyB9CiAgICB2YXIgd0Y9dG90YWwtd0I7IGlmKHdGPT09MCl7IGJyZWFrOyB9CiAgICBzdW1CKz1pKmhpc3RbaV07CiAgICB2YXIgbUI9c3VtQi93QiwgbUY9KHN1bS1zdW1CKS93Riwgdj13Qip3RioobUItbUYpKihtQi1tRik7CiAgICBpZih2PmJlc3QpeyBiZXN0PXY7IHRocj1pOyB9CiAgfQogIHJldHVybiB0aHI7Cn0KZnVuY3Rpb24gcmFuZ29Qcm95ZWNjaW9uKGFycixuLHVtYnJhbCl7CiAgdmFyIGE9LTEsYj0tMSxpOwogIGZvcihpPTA7aTxuO2krKyl7IGlmKGFycltpXT49dW1icmFsKXsgaWYoYTwwKXsgYT1pOyB9IGI9aTsgfSB9CiAgaWYoYTwwfHxiPD1hKXsgcmV0dXJuIG51bGw7IH0KICByZXR1cm4gW2EsYl07Cn0KLyogPT09PT09PT09PT09IGRldGVjY2lvbiBSRUFMIGRlbCBkb2N1bWVudG86IDQgZXNxdWluYXMgPT09PT09PT09PT09ICovCmZ1bmN0aW9uIGV0aXF1ZXRhQ29tcG9uZW50ZXMobWFzaywgdywgaCl7CiAgdmFyIGxhYj1uZXcgSW50MzJBcnJheSh3KmgpLCBwaWxhPW5ldyBJbnQzMkFycmF5KHcqaCk7CiAgdmFyIG1lam9yPXt0YW06MCxpZDowfSwgaWQ9MCwgaTsKICBmb3IoaT0wO2k8dypoO2krKyl7CiAgICBpZihtYXNrW2ldJiYhbGFiW2ldKXsKICAgICAgaWQrKzsgdmFyIHNwPTAsIHRhbT0wOwogICAgICBwaWxhW3NwKytdPWk7IGxhYltpXT1pZDsKICAgICAgd2hpbGUoc3A+MCl7CiAgICAgICAgdmFyIHA9cGlsYVstLXNwXTsgdGFtKys7CiAgICAgICAgdmFyIHg9cCV3LCB5PShwLXgpL3c7CiAgICAgICAgaWYoeD4wJiZtYXNrW3AtMV0mJiFsYWJbcC0xXSl7IGxhYltwLTFdPWlkOyBwaWxhW3NwKytdPXAtMTsgfQogICAgICAgIGlmKHg8dy0xJiZtYXNrW3ArMV0mJiFsYWJbcCsxXSl7IGxhYltwKzFdPWlkOyBwaWxhW3NwKytdPXArMTsgfQogICAgICAgIGlmKHk+MCYmbWFza1twLXddJiYhbGFiW3Atd10peyBsYWJbcC13XT1pZDsgcGlsYVtzcCsrXT1wLXc7IH0KICAgICAgICBpZih5PGgtMSYmbWFza1twK3ddJiYhbGFiW3Ard10peyBsYWJbcCt3XT1pZDsgcGlsYVtzcCsrXT1wK3c7IH0KICAgICAgfQogICAgICBpZih0YW0+bWVqb3IudGFtKXsgbWVqb3I9e3RhbTp0YW0saWQ6aWR9OyB9CiAgICB9CiAgfQogIHJldHVybiB7bGFiOmxhYiwgbWVqb3I6bWVqb3J9Owp9CmZ1bmN0aW9uIGVzcXVpbmFzRGVNYXNjYXJhKGxhYiwgaWQsIHcsIGgpewogIHZhciB0bD1udWxsLHRyPW51bGwsYnI9bnVsbCxibD1udWxsLCB4LHkscDsKICBmb3IoeT0wO3k8aDt5KyspewogICAgZm9yKHg9MDt4PHc7eCsrKXsKICAgICAgcD15KncreDsKICAgICAgaWYobGFiW3BdIT09aWQpeyBjb250aW51ZTsgfQogICAgICB2YXIgcz14K3ksIGQyPXgteTsKICAgICAgaWYoIXRsfHxzPHRsLnMpeyB0bD17eDp4LHk6eSxzOnN9OyB9CiAgICAgIGlmKCFicnx8cz5ici5zKXsgYnI9e3g6eCx5OnksczpzfTsgfQogICAgICBpZighdHJ8fGQyPnRyLmQpeyB0cj17eDp4LHk6eSxkOmQyfTsgfQogICAgICBpZighYmx8fGQyPGJsLmQpeyBibD17eDp4LHk6eSxkOmQyfTsgfQogICAgfQogIH0KICByZXR1cm4ge3RsOnRsLHRyOnRyLGJyOmJyLGJsOmJsfTsKfQpmdW5jdGlvbiBhcmVhUXVhZChxKXsKICBpZighcXx8IXEudGx8fCFxLnRyfHwhcS5icnx8IXEuYmwpeyByZXR1cm4gMDsgfQogIHZhciBwdHM9W3EudGwscS50cixxLmJyLHEuYmxdLCBhPTAsIGk7CiAgZm9yKGk9MDtpPDQ7aSsrKXsgdmFyIHA9cHRzW2ldLCByPXB0c1soaSsxKSU0XTsgYSs9cC54KnIueS1yLngqcC55OyB9CiAgcmV0dXJuIE1hdGguYWJzKGEpLzI7Cn0KZnVuY3Rpb24gcXVhZFZhbGlkbyhxLCBkdywgZGgpewogIGlmKCFxfHwhcS50bHx8IXEudHJ8fCFxLmJyfHwhcS5ibCl7IHJldHVybiB7b2s6ZmFsc2UsIG1vdGl2bzonZm9ybWEnfTsgfQogIHZhciBwdHM9W3EudGwscS50cixxLmJyLHEuYmxdLCBpLCBzaWc9MDsKICBmb3IoaT0wO2k8NDtpKyspewogICAgdmFyIGE9cHRzW2ldLCBiPXB0c1soaSsxKSU0XSwgYz1wdHNbKGkrMiklNF07CiAgICB2YXIgY3I9KGIueC1hLngpKihjLnktYi55KS0oYi55LWEueSkqKGMueC1iLngpOwogICAgaWYoTWF0aC5hYnMoY3IpPDAuNSl7IHJldHVybiB7b2s6ZmFsc2UsIG1vdGl2bzonZm9ybWEnfTsgfQogICAgdmFyIHM9Y3I+MD8xOi0xOwogICAgaWYoc2lnPT09MCl7IHNpZz1zOyB9IGVsc2UgaWYocyE9PXNpZyl7IHJldHVybiB7b2s6ZmFsc2UsIG1vdGl2bzonZm9ybWEnfTsgfQogIH0KICBmdW5jdGlvbiBkc3QoYSxiKXsgdmFyIGR4PWEueC1iLngsIGR5PWEueS1iLnk7IHJldHVybiBNYXRoLnNxcnQoZHgqZHgrZHkqZHkpOyB9CiAgdmFyIGFyPWRzdChxLnRsLHEudHIpLCBhYj1kc3QocS50cixxLmJyKSwgYWk9ZHN0KHEuYnIscS5ibCksIGF6PWRzdChxLmJsLHEudGwpOwogIHZhciBtbj1NYXRoLm1pbihhcixhYixhaSxheik7CiAgaWYobW48TWF0aC5tYXgoZHcsZGgpKjAuMDkpeyByZXR1cm4ge29rOmZhbHNlLCBtb3Rpdm86J3BlcXVlbm8nfTsgfQogIHZhciBmcj1hcmVhUXVhZChxKS8oZHcqZGgpOwogIGlmKGZyPjAuOTQpeyByZXR1cm4ge29rOmZhbHNlLCBtb3Rpdm86J2Zvcm1hJ307IH0KICB2YXIgYXNwPShhcithaSkvTWF0aC5tYXgoMSwoYWIrYXopKTsKICBpZihhc3A8MC40NXx8YXNwPjIuNSl7IHJldHVybiB7b2s6ZmFsc2UsIG1vdGl2bzonZm9ybWEnfTsgfQogIGlmKGZyPDAuMTApeyByZXR1cm4ge29rOmZhbHNlLCBtb3Rpdm86J3BlcXVlbm8nLCBmcmFjOmZyfTsgfQogIHJldHVybiB7b2s6dHJ1ZSwgZnJhYzpmciwgYXNwOmFzcH07Cn0KZnVuY3Rpb24gbml0b0RlKGx1bSwgZHcsIGRoLCBjYWphKXsKICB2YXIgeDA9MSx5MD0xLHgxPWR3LTEseTE9ZGgtMTsKICBpZihjYWphKXsgeDA9TWF0aC5tYXgoMSxjYWphLngrMSk7IHkwPU1hdGgubWF4KDEsY2FqYS55KzEpOyB4MT1NYXRoLm1pbihkdy0xLGNhamEueCtjYWphLnctMSk7IHkxPU1hdGgubWluKGRoLTEsY2FqYS55K2NhamEuaC0xKTsgfQogIHZhciBzPTAsczI9MCxrPTAseCx5OwogIGZvcih5PXkwO3k8eTE7eSsrKXsKICAgIGZvcih4PXgwO3g8eDE7eCsrKXsKICAgICAgdmFyIHA9eSpkdyt4OwogICAgICB2YXIgbHA9NCpsdW1bcF0tbHVtW3AtMV0tbHVtW3ArMV0tbHVtW3AtZHddLWx1bVtwK2R3XTsKICAgICAgcys9bHA7IHMyKz1scCpscDsgaysrOwogICAgfQogIH0KICBpZighayl7IHJldHVybiB7djowfTsgfQogIHZhciBtPXMvazsKICByZXR1cm4ge3Y6KHMyL2spLW0qbX07Cn0KZnVuY3Rpb24gZnJhY2Npb25CbGFuY28obHVtLCBkdywgZGgsIGNhamEpewogIHZhciB4MD0wLHkwPTAseDE9ZHcseTE9ZGgsaz0wLGI9MCx4LHk7CiAgaWYoY2FqYSl7IHgwPU1hdGgubWF4KDAsY2FqYS54KTsgeTA9TWF0aC5tYXgoMCxjYWphLnkpOyB4MT1NYXRoLm1pbihkdyxjYWphLngrY2FqYS53KTsgeTE9TWF0aC5taW4oZGgsY2FqYS55K2NhamEuaCk7IH0KICBmb3IoeT15MDt5PHkxO3krKyl7IGZvcih4PXgwO3g8eDE7eCsrKXsgaysrOyBpZihsdW1beSpkdyt4XT49MjQ2KXsgYisrOyB9IH0gfQogIHJldHVybiBrPyhiL2spOjA7Cn0KZnVuY3Rpb24gbWVkaWFuYU51bShhKXsKICBpZighYXx8IWEubGVuZ3RoKXsgcmV0dXJuIDA7IH0KICB2YXIgYj1hLnNsaWNlKCkuc29ydChmdW5jdGlvbih4LHkpeyByZXR1cm4geC15OyB9KTsKICByZXR1cm4gYltNYXRoLmZsb29yKGIubGVuZ3RoLzIpXTsKfQpmdW5jdGlvbiBtZWRpYW5hUXVhZChoaXN0KXsKICBpZighaGlzdHx8IWhpc3QubGVuZ3RoKXsgcmV0dXJuIG51bGw7IH0KICB2YXIgSz1bJ3RsJywndHInLCdicicsJ2JsJ10sIHJlcz17fSwgaSwgaywgeHMsIHlzOwogIGZvcihrPTA7azxLLmxlbmd0aDtrKyspewogICAgeHM9W107IHlzPVtdOwogICAgZm9yKGk9MDtpPGhpc3QubGVuZ3RoO2krKyl7IGlmKGhpc3RbaV0mJmhpc3RbaV1bS1trXV0peyB4cy5wdXNoKGhpc3RbaV1bS1trXV0ueCk7IHlzLnB1c2goaGlzdFtpXVtLW2tdXS55KTsgfSB9CiAgICBpZigheHMubGVuZ3RoKXsgcmV0dXJuIG51bGw7IH0KICAgIHJlc1tLW2tdXT17eDptZWRpYW5hTnVtKHhzKSwgeTptZWRpYW5hTnVtKHlzKX07CiAgfQogIHJldHVybiByZXM7Cn0KZnVuY3Rpb24gcXVhZEVzdGFibGUoaGlzdCl7CiAgdmFyIG1lZD1tZWRpYW5hUXVhZChoaXN0KSwgSz1bJ3RsJywndHInLCdicicsJ2JsJ10sIGksIGs7CiAgaWYoIW1lZHx8IWhpc3R8fGhpc3QubGVuZ3RoPDQpeyByZXR1cm4gZmFsc2U7IH0KIHZhciB0b2w9MC4wMipNYXRoLm1heChoaXN0WzBdLnZ3fHw2NDAsIGhpc3RbMF0udmh8fDQ4MCk7CiAgZm9yKGs9MDtrPEsubGVuZ3RoO2srKyl7CiAgICBmb3IoaT1NYXRoLm1heCgwLGhpc3QubGVuZ3RoLTQpO2k8aGlzdC5sZW5ndGg7aSsrKXsKICAgICAgdmFyIHE9aGlzdFtpXSYmaGlzdFtpXVtLW2tdXTsKICAgICAgaWYoIXF8fCFtZWRbS1trXV0peyByZXR1cm4gZmFsc2U7IH0KICAgICAgdmFyIGR4PXEueC1tZWRbS1trXV0ueCwgZHk9cS55LW1lZFtLW2tdXS55OwogICAgICBpZihNYXRoLnNxcnQoZHgqZHgrZHkqZHkpPnRvbCl7IHJldHVybiBmYWxzZTsgfQogICAgfQogIH0KICByZXR1cm4gdHJ1ZTsKfQpmdW5jdGlvbiBkZXRlY3RhckRvY1F1YWQodil7CiAgdHJ5ewogICAgdmFyIEQ9enlEZXQoKTsKICAgIHZhciB2dz12LnZpZGVvV2lkdGh8fDAsIHZoPXYudmlkZW9IZWlnaHR8fDA7CiAgICBpZighdnd8fCF2aCl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgZHc9MTYwLCBkaD1NYXRoLnJvdW5kKGR3KnZoL3Z3KTsKICAgIGlmKGRoPDgpeyByZXR1cm4gbnVsbDsgfQogICAgdmFyIGM9RC5jdlE7IGlmKCFjKXsgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsgRC5jdlE9YzsgfQogICAgaWYoYy53aWR0aCE9PWR3fHxjLmhlaWdodCE9PWRoKXsgYy53aWR0aD1kdzsgYy5oZWlnaHQ9ZGg7IH0KICAgIHZhciBnPWMuZ2V0Q29udGV4dCgnMmQnKTsgaWYoIWcpeyByZXR1cm4gbnVsbDsgfQogICAgZy5kcmF3SW1hZ2UodiwwLDAsZHcsZGgpOwogICAgdmFyIGQ9Zy5nZXRJbWFnZURhdGEoMCwwLGR3LGRoKS5kYXRhLCBuPWR3KmRoLCBpLCB4LCB5OwogICAgdmFyIGx1bT1uZXcgVWludDhBcnJheShuKSwgc3VtPTA7CiAgICBmb3IoaT0wO2k8bjtpKyspeyBsdW1baV09KGRbaSo0XSozK2RbaSo0KzFdKjQrZFtpKjQrMl0pPj4zOyBzdW0rPWx1bVtpXTsgfQogICAgdmFyIGx1ej1zdW0vbjsKICAgIC8qIGhlcmVkYWRvIHYxNDogbWFzY2FyYSBhbnRpLXRlbGEgZGUgY29sb3IuIEVuIGdyaXMsIHVuYSB0ZWxhIHJvc2Evcm9qYQogICAgICAgY2xhcmEgc2UgdmUgY2FzaSBpZ3VhbCBxdWUgbGEgdGFyamV0YSB5IGVsIHVtYnJhbCBkZSBPdHN1IG5vIHNlcGFyYToKICAgICAgIGxhIGd1aWEgbm8gYWdhcnJhIGxhcyA0IGVzcXVpbmFzLiBMYSBUQVJKRVRBIGVzIGNsYXJhIHkgUE9DTyBzYXR1cmFkYTsKICAgICAgIGxhIHRlbGEgZGUgY29sb3IgZXMgTVVZIHNhdHVyYWRhLiBQcnVlYm8gcHJpbWVybyBjb24gZXNhIG1hc2NhcmEgeSBzaQogICAgICAgbm8gZGEgdW4gY3VhZHJpbGF0ZXJvIHZhbGlkbyBjYWlnbyBhbCB1bWJyYWwgZGUgT3RzdSAoZm9uZG8gb3NjdXJvKS4gKi8KICAgIGZ1bmN0aW9uIHJlc3VsdGFkb0RlTWFzY2FyYShtYXNrQXJyKXsKICAgICAgdmFyIHRvdDI9MCwgaTI7CiAgICAgIGZvcihpMj0wO2kyPG47aTIrKyl7IGlmKG1hc2tBcnJbaTJdKXsgdG90MisrOyB9IH0KICAgICAgaWYodG90MjxuKjAuMDN8fHRvdDI+biowLjk2NSl7IHJldHVybiBudWxsOyB9CiAgICAgIHZhciBjYzI9ZXRpcXVldGFDb21wb25lbnRlcyhtYXNrQXJyLGR3LGRoKTsKICAgICAgaWYoIWNjMi5tZWpvci5pZHx8Y2MyLm1lam9yLnRhbTxuKjAuMDQpeyByZXR1cm4gbnVsbDsgfQogICAgICB2YXIgcTI9ZXNxdWluYXNEZU1hc2NhcmEoY2MyLmxhYixjYzIubWVqb3IuaWQsZHcsZGgpOwogICAgICBpZighcTIudGx8fCFxMi50cnx8IXEyLmJyfHwhcTIuYmwpeyByZXR1cm4gbnVsbDsgfQogICAgICB2YXIgdmFsMj1xdWFkVmFsaWRvKHEyLGR3LGRoKTsKICAgICAgaWYoIXZhbDIub2speyByZXR1cm4gbnVsbDsgfQogICAgICB2YXIgeGE9TWF0aC5tYXgoMCxNYXRoLm1pbihxMi50bC54LHEyLmJsLngpKSwgeGI9TWF0aC5taW4oZHcsTWF0aC5tYXgocTIudHIueCxxMi5ici54KSk7CiAgICAgIHZhciB5YT1NYXRoLm1heCgwLE1hdGgubWluKHEyLnRsLnkscTIudHIueSkpLCB5Yj1NYXRoLm1pbihkaCxNYXRoLm1heChxMi5ibC55LHEyLmJyLnkpKTsKICAgICAgdmFyIGNhamEyPXt4OnhhLHk6eWEsdzpNYXRoLm1heCgxLHhiLXhhKSxoOk1hdGgubWF4KDEseWIteWEpfTsKICAgICAgdmFyIG50Mj1uaXRvRGUobHVtLGR3LGRoLGNhamEyKTsKICAgICAgdmFyIGJsYTI9ZnJhY2Npb25CbGFuY28obHVtLGR3LGRoLGNhamEyKTsKICAgICAgdmFyIHN4Mj12dy9kdywgc3kyPXZoL2RoOwogICAgICByZXR1cm4ge3RsOnt4OnEyLnRsLngqc3gyLHk6cTIudGwueSpzeTJ9LCB0cjp7eDpxMi50ci54KnN4Mix5OnEyLnRyLnkqc3kyfSwgYnI6e3g6cTIuYnIueCpzeDIseTpxMi5ici55KnN5Mn0sIGJsOnt4OnEyLmJsLngqc3gyLHk6cTIuYmwueSpzeTJ9LCBsdXo6bHV6LCBuaXRvOm50Mi52LCBibGFuY286YmxhMiwgdnc6dncsIHZoOnZoLCBmcmFjOnZhbDIuZnJhY307CiAgICB9CiAgICB2YXIgbWFza1M9bmV3IFVpbnQ4QXJyYXkobiksIHRvdFM9MDsKICAgIGZvcihpPTA7aTxuO2krKyl7CiAgICAgIHZhciByND1kW2kqNF0sIGc0PWRbaSo0KzFdLCBiND1kW2kqNCsyXTsKICAgICAgdmFyIG14PShyND5nNCk/KHI0PmI0P3I0OmI0KTooZzQ+YjQ/ZzQ6YjQpLCBtbj0ocjQ8ZzQpPyhyNDxiND9yNDpiNCk6KGc0PGI0P2c0OmI0KTsKICAgICAgaWYoKG14LW1uKTw9ODUmJmx1bVtpXT49MTEyKXsgbWFza1NbaV09MTsgdG90UysrOyB9CiAgICB9CiAgICBpZih0b3RTPj1uKjAuMDMpewogICAgICB2YXIgclM9cmVzdWx0YWRvRGVNYXNjYXJhKG1hc2tTKTsKICAgICAgaWYoclMpeyByZXR1cm4gclM7IH0KICAgIH0KICAgIHZhciBsYj1uZXcgVWludDhBcnJheShuKTsKICAgIGZvcih5PTE7eTxkaC0xO3krKyl7IGZvcih4PTE7eDxkdy0xO3grKyl7IHZhciBwcD15KmR3K3g7IGxiW3BwXT0obHVtW3BwXSo0K2x1bVtwcC0xXStsdW1bcHArMV0rbHVtW3BwLWR3XStsdW1bcHArZHddKT4+MzsgfSB9CiAgICB2YXIgaGlzdD1uZXcgSW50MzJBcnJheSgyNTYpOyBmb3IoaT0wO2k8bjtpKyspeyBoaXN0W2xiW2ldXSsrOyB9CiAgICB2YXIgdGhyPW90c3VVbWJyYWwoaGlzdCxuKTsKICAgIHZhciBtYXNrPW5ldyBVaW50OEFycmF5KG4pLCB0b3Q9MDsKICAgIGZvcihpPTA7aTxuO2krKyl7IHZhciB2MT0obGJbaV0+dGhyKT8xOjA7IG1hc2tbaV09djE7IHRvdCs9djE7IH0KICAgIGlmKHRvdDxuKjAuMDMpeyByZXR1cm4gbnVsbDsgfQogICAgaWYodG90Pm4qMC45NjUpewogICAgICB2YXIgbnQwPW5pdG9EZShsdW0sZHcsZGgsbnVsbCk7CiAgICAgIHJldHVybiB7bGxlbm86dHJ1ZSwgbHV6Omx1eiwgbml0bzpudDAudiwgYmxhbmNvOmZyYWNjaW9uQmxhbmNvKGx1bSxkdyxkaCxudWxsKSwgdnc6dncsIHZoOnZofTsKICAgIH0KICAgIHZhciBjYz1ldGlxdWV0YUNvbXBvbmVudGVzKG1hc2ssZHcsZGgpOwogICAgaWYoIWNjLm1lam9yLmlkfHxjYy5tZWpvci50YW08biowLjA0KXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciBxPWVzcXVpbmFzRGVNYXNjYXJhKGNjLmxhYixjYy5tZWpvci5pZCxkdyxkaCk7CiAgICBpZighcS50bHx8IXEudHJ8fCFxLmJyfHwhcS5ibCl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgdmFsPXF1YWRWYWxpZG8ocSxkdyxkaCk7CiAgICB2YXIgeDA9TWF0aC5tYXgoMCxNYXRoLm1pbihxLnRsLngscS5ibC54KSksIHgxPU1hdGgubWluKGR3LE1hdGgubWF4KHEudHIueCxxLmJyLngpKTsKICAgIHZhciB5MD1NYXRoLm1heCgwLE1hdGgubWluKHEudGwueSxxLnRyLnkpKSwgeTE9TWF0aC5taW4oZGgsTWF0aC5tYXgocS5ibC55LHEuYnIueSkpOwogICAgdmFyIGNhamE9e3g6eDAseTp5MCx3Ok1hdGgubWF4KDEseDEteDApLGg6TWF0aC5tYXgoMSx5MS15MCl9OwogICAgdmFyIG50PW5pdG9EZShsdW0sZHcsZGgsY2FqYSk7CiAgICB2YXIgYmxhPWZyYWNjaW9uQmxhbmNvKGx1bSxkdyxkaCxjYWphKTsKICAgIHZhciBzeD12dy9kdywgc3k9dmgvZGg7CiAgICBmdW5jdGlvbiBlc2MocCl7IHJldHVybiB7eDpwLngqc3gsIHk6cC55KnN5fTsgfQogICAgdmFyIHJlcz17dGw6ZXNjKHEudGwpLCB0cjplc2MocS50ciksIGJyOmVzYyhxLmJyKSwgYmw6ZXNjKHEuYmwpLCBsdXo6bHV6LCBuaXRvOm50LnYsIGJsYW5jbzpibGEsIHZ3OnZ3LCB2aDp2aH07CiAgICBpZighdmFsLm9rKXsgcmVzLmRlc2NhcnRhZG89dmFsLm1vdGl2bzsgcmV0dXJuIHJlczsgfQogICAgcmVzLmZyYWM9dmFsLmZyYWM7CiAgICByZXR1cm4gcmVzOwogIH1jYXRjaChlKXsgcmV0dXJuIG51bGw7IH0KfQpmdW5jdGlvbiBkZXRlY3RhckRvY0JveCh2KXsKICB0cnl7CiAgICB2YXIgRD16eURldCgpOwogICAgdmFyIGM9RC5jdkRvYzsKICAgIGlmKCFjKXsgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsgRC5jdkRvYz1jOyB9CiAgICB2YXIgZHc9MTI4LCBkaD1NYXRoLm1heCg4LE1hdGgucm91bmQoMTI4Kigodi52aWRlb0hlaWdodHx8MykvKCh2LnZpZGVvV2lkdGh8fDQpKjEuMCkpKSk7CiAgICBpZihjLndpZHRoIT09ZHd8fGMuaGVpZ2h0IT09ZGgpeyBjLndpZHRoPWR3OyBjLmhlaWdodD1kaDsgfQogICAgdmFyIGc9Yy5nZXRDb250ZXh0KCcyZCcpOyBpZighZyl7IHJldHVybiBudWxsOyB9CiAgICBnLmRyYXdJbWFnZSh2LDAsMCxkdyxkaCk7CiAgICB2YXIgZD1nLmdldEltYWdlRGF0YSgwLDAsZHcsZGgpLmRhdGEsIG49ZHcqZGg7CiAgICB2YXIgaGlzdD1uZXcgSW50MzJBcnJheSgyNTYpLCBsdW09bmV3IFVpbnQ4QXJyYXkobiksIGkseCx5OwogICAgZm9yKGk9MDtpPG47aSsrKXsgdmFyIHI9ZFtpKjRdLCBnZz1kW2kqNCsxXSwgYj1kW2kqNCsyXTsgbHVtW2ldPShyKjMrZ2cqNCtiKT4+MzsgaGlzdFtsdW1baV1dKys7IH0KICAgIHZhciB0aHI9b3RzdVVtYnJhbChoaXN0LG4pOwogICAgdmFyIGZpbGFzPW5ldyBJbnQzMkFycmF5KGRoKSwgY29scz1uZXcgSW50MzJBcnJheShkdyksIHRvdD0wOwogICAgZm9yKHk9MDt5PGRoO3krKyl7IGZvcih4PTA7eDxkdzt4KyspeyBpZihsdW1beSpkdyt4XT50aHIpeyBmaWxhc1t5XSsrOyBjb2xzW3hdKys7IHRvdCsrOyB9IH0gfQogICAgaWYodG90PG4qMC4wNHx8dG90Pm4qMC45ODUpeyByZXR1cm4gbnVsbDsgfQogICAgdmFyIHJmPXJhbmdvUHJveWVjY2lvbihmaWxhcyxkaCxNYXRoLm1heCgyLE1hdGgucm91bmQoZHcqMC4xOCkpKTsKICAgIHZhciByYz1yYW5nb1Byb3llY2Npb24oY29scyxkdyxNYXRoLm1heCgyLE1hdGgucm91bmQoZGgqMC4xOCkpKTsKICAgIGlmKCFyZnx8IXJjKXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciBzeD0odi52aWRlb1dpZHRofHw2NDApL2R3LCBzeT0odi52aWRlb0hlaWdodHx8NDgwKS9kaDsKICAgIHZhciBieD1yY1swXSpzeCwgYnk9cmZbMF0qc3ksIGJ3PShyY1sxXSsxLXJjWzBdKSpzeCwgYmg9KHJmWzFdKzEtcmZbMF0pKnN5OwogICAgaWYoYnc8OHx8Ymg8OCl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgc3VtYT0wLCBpMjsKICAgIGZvcihpMj0wO2kyPG47aTIrKyl7IHN1bWErPWx1bVtpMl07IH0KICAgIHZhciBsdXo9c3VtYS9uOwogICAgdmFyIHN1bVY9MCwgc3VtVjI9MCwgbjI9MCwgeDIsIHkyOwogICAgZm9yKHkyPTE7eTI8ZGgtMTt5MisrKXsKICAgICAgZm9yKHgyPTE7eDI8ZHctMTt4MisrKXsKICAgICAgICB2YXIgaWk9eTIqZHcreDI7CiAgICAgICAgdmFyIGxhcD00Kmx1bVtpaV0tbHVtW2lpLTFdLWx1bVtpaSsxXS1sdW1baWktZHddLWx1bVtpaStkd107CiAgICAgICAgc3VtVis9bGFwOyBzdW1WMis9bGFwKmxhcDsgbjIrKzsKICAgICAgfQogICAgfQogICAgdmFyIG1lZGlhPXN1bVYvTWF0aC5tYXgoMSxuMik7CiAgICB2YXIgdmFyTD0oc3VtVjIvTWF0aC5tYXgoMSxuMikpLW1lZGlhKm1lZGlhOwogICAgcmV0dXJuIHt4OmJ4LCB5OmJ5LCB3OmJ3LCBoOmJoLCBsdXo6bHV6LCBuaXRvOih2YXJMPj00MCksIGZvY286TWF0aC5yb3VuZCh2YXJMKX07CiAgfWNhdGNoKGUpeyByZXR1cm4gbnVsbDsgfQp9CmZ1bmN0aW9uIGNlbnRyb0RlKHB1bnRvcyl7CiAgdmFyIHN4PTAsIHN5PTAsIGk7CiAgZm9yKGk9MDtpPHB1bnRvcy5sZW5ndGg7aSsrKXsgc3grPXB1bnRvc1tpXS54OyBzeSs9cHVudG9zW2ldLnk7IH0KICByZXR1cm4ge3g6c3gvcHVudG9zLmxlbmd0aCwgeTpzeS9wdW50b3MubGVuZ3RofTsKfQpmdW5jdGlvbiBlYXJEZShwdW50b3MpewogIGlmKCFwdW50b3N8fHB1bnRvcy5sZW5ndGg8Nil7IHJldHVybiAxOyB9CiAgZnVuY3Rpb24gZDIoYSxiKXsgdmFyIGR4PWEueC1iLngsIGR5PWEueS1iLnk7IHJldHVybiBNYXRoLnNxcnQoZHgqZHgrZHkqZHkpOyB9CiAgdmFyIGg9ZDIocHVudG9zWzBdLHB1bnRvc1szXSk7CiAgaWYoaDwxZS02KXsgcmV0dXJuIDE7IH0KICByZXR1cm4gKGQyKHB1bnRvc1sxXSxwdW50b3NbNV0pK2QyKHB1bnRvc1syXSxwdW50b3NbNF0pKS8oMipoKTsKfQpmdW5jdGlvbiBldmFsdWFDYXJhKGluZm8pewogIHZhciByPXt2aXN0YTp0cnVlLCBvazpmYWxzZSwgdGFtOidiaWVuJywgbW90aXZvOicnLCBjb2Q6Jyd9OwogIGlmKGluZm8ubHV6PDQ1KXsgci5jb2Q9J2x1eic7IHIubW90aXZvPSdQT0NBIExVWjogcG9uIHR1IGNhcmEgaGFjaWEgbGEgbHV6IG8gZW5jaWVuZGUgdW5hIGxhbXBhcmEuJzsgcmV0dXJuIHI7IH0KICBpZihpbmZvLm5pdG88MTUpeyByLmNvZD0nbml0byc7IHIubW90aXZvPSdObyBzZSB2ZSBOSVRJRE86IHNvc3RcdTAwRTluIGVsIHRlbGVmb25vIGZpcm1lIHkgZXNwZXJhIGVsIGVuZm9xdWUuJzsgcmV0dXJuIHI7IH0KICBpZihpbmZvLnRhbTwwLjMwKXsgci50YW09J2xlam9zJzsgci5jb2Q9J2xlam9zJzsgci5tb3Rpdm89J0FDRVJDQVRFOiB0dSBjYXJhIGRlYmUgbGxlbmFyIGVsIE9WQUxPIChmb3RvIGRlIHJvc3Rybywgbm8gbWVkaW8gY3VlcnBvKS4nOyByZXR1cm4gcjsgfQogIGlmKGluZm8udGFtPjAuODYpeyByLnRhbT0nY2VyY2EnOyByLmNvZD0nY2VyY2EnOyByLm1vdGl2bz0nQUxFSkFURSB1biBwb2NvIHBhcmEgcXVlIHR1IGNhcmEgcXVlcGEgZW50ZXJhIGVuIGVsIG92YWxvLic7IHJldHVybiByOyB9CiAgaWYoTWF0aC5hYnMoaW5mby5meC0wLjUpPjAuMTZ8fGluZm8uZnk8MC4zMHx8aW5mby5meT4wLjc0KXsgci5jb2Q9J2Z1ZXJhJzsgci5tb3Rpdm89J0NlbnRyYSB0dSBjYXJhIGRlbnRybyBkZWwgT1ZBTE8sIG1pcmFuZG8gYSBsYSBjYW1hcmEuJzsgcmV0dXJuIHI7IH0KICBpZihNYXRoLmFicyhpbmZvLnJvbGwpPjE2KXsgci5jb2Q9J3JvbGwnOyByLm1vdGl2bz0nRW5kZXJlemEgbGEgY2FiZXphOiBubyBsYSBpbmNsaW5lcyBhIGxvcyBsYWRvcy4nOyByZXR1cm4gcjsgfQogIGlmKE1hdGguYWJzKGluZm8ueWF3KT4wLjI0KXsgci5jb2Q9J3lhdyc7IHIubW90aXZvPSdNaXJhIERFIEZSRU5URSBhIGxhIGNhbWFyYSwgbm8gZGUgbGFkby4nOyByZXR1cm4gcjsgfQogIGlmKGluZm8ub2pvczwwLjEwKXsgci5jb2Q9J29qb3MnOyByLm1vdGl2bz0nQWJyZSBsb3Mgb2pvcyB5IG1pcmEgZmlqbyBhIGxhIGNhbWFyYS4nOyByZXR1cm4gcjsgfQogIHIub2s9dHJ1ZTsgci5tb3Rpdm89J1BlcmZlY3RvOiBzb3N0XHUwMEU5biBsYSBwb3NpY2lvbi4uLic7CiAgcmV0dXJuIHI7Cn0KZnVuY3Rpb24gbml0b0RlUmdiYShkYXRvcywgZHcsIGRoLCBjYWphKXsKICB2YXIgeDA9TWF0aC5tYXgoMSxjYWphLngrMSksIHkwPU1hdGgubWF4KDEsY2FqYS55KzEpOwogIHZhciB4MT1NYXRoLm1pbihkdy0xLGNhamEueCtjYWphLnctMSksIHkxPU1hdGgubWluKGRoLTEsY2FqYS55K2NhamEuaC0xKTsKICB2YXIgcz0wLHMyPTAsaz0wLHgseTsKICBmb3IoeT15MDt5PHkxO3krKyl7CiAgICBmb3IoeD14MDt4PHgxO3grKyl7CiAgICAgIHZhciBwPXkqZHcreDsKICAgICAgdmFyIGwxPShkYXRvc1twKjRdKjMrZGF0b3NbcCo0KzFdKjQrZGF0b3NbcCo0KzJdKT4+MzsKICAgICAgdmFyIGwyPShkYXRvc1socC0xKSo0XSozK2RhdG9zWyhwLTEpKjQrMV0qNCtkYXRvc1socC0xKSo0KzJdKT4+MzsKICAgICAgdmFyIGwzPShkYXRvc1socCsxKSo0XSozK2RhdG9zWyhwKzEpKjQrMV0qNCtkYXRvc1socCsxKSo0KzJdKT4+MzsKICAgICAgdmFyIGw0PShkYXRvc1socC1kdykqNF0qMytkYXRvc1socC1kdykqNCsxXSo0K2RhdG9zWyhwLWR3KSo0KzJdKT4+MzsKICAgICAgdmFyIGw1PShkYXRvc1socCtkdykqNF0qMytkYXRvc1socCtkdykqNCsxXSo0K2RhdG9zWyhwK2R3KSo0KzJdKT4+MzsKICAgICAgdmFyIGxwPTQqbDEtbDItbDMtbDQtbDU7CiAgICAgIHMrPWxwOyBzMis9bHAqbHA7IGsrKzsKICAgIH0KICB9CiAgaWYoIWspeyByZXR1cm4gMDsgfQogIHZhciBtPXMvazsKICByZXR1cm4gKHMyL2spLW0qbTsKfQpmdW5jdGlvbiBidXNjYXJDYXJhVml2YSh2LCBjYil7CiAgdHJ5ewogICAgaWYoIShXLmZhY2VhcGkmJlcuZmFjZWFwaS5uZXRzJiZXLmZhY2VhcGkubmV0cy50aW55RmFjZURldGVjdG9yJiZXLmZhY2VhcGkuVGlueUZhY2VEZXRlY3Rvck9wdGlvbnMpKXsgY2IobnVsbCk7IHJldHVybjsgfQogICAgdmFyIEQ9enlEZXQoKTsKICAgIHZhciB2dz12LnZpZGVvV2lkdGh8fDY0MCwgdmg9di52aWRlb0hlaWdodHx8NDgwOwogICAgdmFyIGR3PTIyNCwgZGg9TWF0aC5tYXgoODAsTWF0aC5yb3VuZChkdyp2aC92dykpOwogICAgdmFyIGM9RC5jdkNhcmE7CiAgICBpZighYyl7IGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7IEQuY3ZDYXJhPWM7IH0KICAgIGlmKGMud2lkdGghPT1kd3x8Yy5oZWlnaHQhPT1kaCl7IGMud2lkdGg9ZHc7IGMuaGVpZ2h0PWRoOyB9CiAgICB2YXIgZz1jLmdldENvbnRleHQoJzJkJyk7IGlmKCFnKXsgY2IobnVsbCk7IHJldHVybjsgfQogICAgZy5kcmF3SW1hZ2UodiwwLDAsZHcsZGgpOwogICAgdmFyIGRhdG9zPW51bGw7CiAgICB0cnl7IGRhdG9zPWcuZ2V0SW1hZ2VEYXRhKDAsMCxkdyxkaCkuZGF0YTsgfWNhdGNoKGUpeyBkYXRvcz1udWxsOyB9CiAgICB2YXIgb3B0PW5ldyBXLmZhY2VhcGkuVGlueUZhY2VEZXRlY3Rvck9wdGlvbnMoe2lucHV0U2l6ZToyMjQsIHNjb3JlVGhyZXNob2xkOjAuNDV9KTsKICAgIFcuZmFjZWFwaS5kZXRlY3RTaW5nbGVGYWNlKGMsb3B0KS53aXRoRmFjZUxhbmRtYXJrcygpLndpdGhGYWNlRGVzY3JpcHRvcigpLnRoZW4oZnVuY3Rpb24ocil7CiAgICAgIHRyeXsKICAgICAgICBpZighcnx8IXIuZGV0ZWN0aW9uKXsgY2Ioe3Zpc3RhOmZhbHNlLCBvazpmYWxzZSwgdDpEYXRlLm5vdygpfSk7IHJldHVybjsgfQogICAgICAgIHZhciBiPXIuZGV0ZWN0aW9uLmJveDsKICAgICAgICB2YXIgZng9KGIueCtiLndpZHRoLzIpL2R3LCBmeT0oYi55K2IuaGVpZ2h0LzIpL2RoOwogICAgICAgIHZhciB0YW09Yi5oZWlnaHQvZGg7CiAgICAgICAgdmFyIHJvbGw9MCwgeWF3PTAsIG9qb3M9MTsKICAgICAgICBpZihyLmxhbmRtYXJrcyl7CiAgICAgICAgICB2YXIgTD1yLmxhbmRtYXJrcy5nZXRMZWZ0RXllKCksIFI9ci5sYW5kbWFya3MuZ2V0UmlnaHRFeWUoKSwgTj1yLmxhbmRtYXJrcy5nZXROb3NlKCk7CiAgICAgICAgICBpZihMJiZSJiZMLmxlbmd0aD49NCYmUi5sZW5ndGg+PTQpewogICAgICAgICAgICB2YXIgbGM9Y2VudHJvRGUoTCksIHJjPWNlbnRyb0RlKFIpOwogICAgICAgICAgICByb2xsPU1hdGguYXRhbjIocmMueS1sYy55LCByYy54LWxjLngpKjE4MC9NYXRoLlBJOwogICAgICAgICAgICB2YXIgbXg9KGxjLngrcmMueCkvMjsKICAgICAgICAgICAgaWYoTiYmTi5sZW5ndGg+NCl7IHlhdz0oTls0XS54LW14KS9NYXRoLm1heCgxLGIud2lkdGgpOyB9CiAgICAgICAgICAgIG9qb3M9TWF0aC5taW4oZWFyRGUoTCksIGVhckRlKFIpKTsKICAgICAgICAgIH0KICAgICAgICB9CiAgICAgICAgdmFyIGNhamE9e3g6TWF0aC5yb3VuZChiLngqdncvZHcpLCB5Ok1hdGgucm91bmQoYi55KnZoL2RoKSwgdzpNYXRoLnJvdW5kKGIud2lkdGgqdncvZHcpLCBoOk1hdGgucm91bmQoYi5oZWlnaHQqdmgvZGgpfTsKICAgICAgICBjYWphLng9TWF0aC5tYXgoMCx2dy1jYWphLngtY2FqYS53KTsKICAgICAgICB2YXIgbHV6PTAsIG5pdG89MDsKICAgICAgICBpZihkYXRvcyl7CiAgICAgICAgICB2YXIgcngwPU1hdGgubWF4KDAsTWF0aC5yb3VuZChiLngpKSwgcnkwPU1hdGgubWF4KDAsTWF0aC5yb3VuZChiLnkpKTsKICAgICAgICAgIHZhciByeDE9TWF0aC5taW4oZHcsTWF0aC5yb3VuZChiLngrYi53aWR0aCkpLCByeTE9TWF0aC5taW4oZGgsTWF0aC5yb3VuZChiLnkrYi5oZWlnaHQpKTsKICAgICAgICAgIHZhciBzPTAsaz0wLHgseTsKICAgICAgICAgIGZvcih5PXJ5MDt5PHJ5MTt5KyspeyBmb3IoeD1yeDA7eDxyeDE7eCsrKXsgcys9KGRhdG9zWyh5KmR3K3gpKjRdKjMrZGF0b3NbKHkqZHcreCkqNCsxXSo0K2RhdG9zWyh5KmR3K3gpKjQrMl0pPj4zOyBrKys7IH0gfQogICAgICAgICAgbHV6PWs/KHMvayk6MDsKICAgICAgICAgIG5pdG89KHJ4MT5yeDArMiYmcnkxPnJ5MCsyKT9uaXRvRGVSZ2JhKGRhdG9zLGR3LGRoLHt4OnJ4MCx5OnJ5MCx3OnJ4MS1yeDAsaDpyeTEtcnkwfSk6MDsKICAgICAgICB9CiAgICAgICAgdmFyIGRlPWV2YWx1YUNhcmEoe2Z4OmZ4LGZ5OmZ5LHRhbTp0YW0scm9sbDpyb2xsLHlhdzp5YXcsb2pvczpvam9zLGx1ejpsdXosbml0bzpuaXRvfSk7CiAgICAgICAgY2Ioe3Zpc3RhOnRydWUsIG9rOmRlLm9rLCBjb2Q6ZGUuY29kLCBtb3Rpdm86ZGUubW90aXZvLCB0YW06ZGUudGFtLCBmeDpmeCwgZnk6ZnksIGNhamE6Y2FqYSwgbHV6Omx1eiwgbml0bzpuaXRvLCBvam9zOm9qb3MsIHJvbGw6cm9sbCwgeWF3OnlhdywgdDpEYXRlLm5vdygpfSk7CiAgICAgIH1jYXRjaChlKXsgY2IobnVsbCk7IH0KICAgIH0pLmNhdGNoKGZ1bmN0aW9uKCl7IGNiKG51bGwpOyB9KTsKICB9Y2F0Y2goZSl7IGNiKG51bGwpOyB9Cn0KZnVuY3Rpb24gZW5tYXJjYXJWZXJkZShwc0lkLCB2KXsKICAvKiB2MTE6IGNvbnRvcm5vIFBPTElHT05BTCByZWFsIHF1ZSBzaWd1ZSBhbCBkb2N1bWVudG8gKHBzIDIgeSAzKSB5IE9WQUxPIGNvbiBtb3RvciBmYWNpYWwgKHBzIDQpICovCiAgdHJ5ewogICAgdmFyIE9WPXsnMic6J292RicsJzMnOidvdkEnLCc0Jzonb3ZTJ307CiAgICB2YXIgb3ZJZD1PVltwc0lkXTsKICAgIGlmKCFvdklkKXsgcmV0dXJuOyB9CiAgICB2YXIgc3RJZD0ocHNJZD09PScyJyk/J3N0Ric6KChwc0lkPT09JzMnKT8nc3RBJzonc3RWJyk7CiAgICB2YXIgRD16eURldCgpOwogICAgdmFyIHN0PURbcHNJZF07CiAgICBpZighc3QpeyBzdD1EW3BzSWRdPXtjYWphOm51bGwsIHQ6LTFlOSwgZXN0YWRvOicnLCBpdjpudWxsfTsgfQogICAgc3QudDA9RGF0ZS5ub3coKTsgc3QuY2FqYT1udWxsOyBzdC5lc3RhZG89Jyc7IHN0LmF1dG89MDsgc3QuYXV0b0hlY2hvPWZhbHNlOyBzdC5jZD0wOyBzdC5oaXN0PVtdOwogICAgdmFyIHBpbnRhckRvYz1mdW5jdGlvbihjYWphLCBlc3RhZG8pewogICAgICB0cnl7CiAgICAgICAgdmFyIG92PSQob3ZJZCk7IGlmKCFvdil7IHJldHVybjsgfQogICAgICAgIHZhciB2dz0odiYmdi52aWRlb1dpZHRoKXx8MCwgdmg9KHYmJnYudmlkZW9IZWlnaHQpfHwwOwogICAgICAgIGlmKCF2d3x8IXZoKXsgcmV0dXJuOyB9CiAgICAgICAgaWYob3Yud2lkdGghPT12d3x8b3YuaGVpZ2h0IT09dmgpeyBvdi53aWR0aD12dzsgb3YuaGVpZ2h0PXZoOyB9CiAgICAgICAgdmFyIGc9b3YuZ2V0Q29udGV4dCgnMmQnKTsgaWYoIWcpeyByZXR1cm47IH0KICAgICAgICBnLmNsZWFyUmVjdCgwLDAsdncsdmgpOwogICAgICAgIHZhciB4LHksdyxoOwogICAgICAgIGlmKCFjYWphKXsgeD1NYXRoLnJvdW5kKHZ3KjAuMDcpOyB5PU1hdGgucm91bmQodmgqMC4wOSk7IHc9dncteCoyOyBoPXZoLXkqMjsgfQogICAgICAgIGVsc2V7IHg9Y2FqYS54OyB5PWNhamEueTsgdz1jYWphLnc7IGg9Y2FqYS5oOyB9CiAgICAgICAgaWYodzwxMHx8aDwxMCl7IHJldHVybjsgfQogICAgICAgIHZhciBjb2w9KGVzdGFkbz09PSdvaycpPycjM2ZiOTUwJzooKGVzdGFkbz09PSdtYWwnKT8nI2MwMzkyYic6JyNlM2IzNDEnKTsKICAgICAgICBnLnN0cm9rZVN0eWxlPWNvbDsgZy5saW5lV2lkdGg9NTsKICAgICAgICB2YXIgTD1NYXRoLnJvdW5kKE1hdGgubWluKHcsaCkqKGNhamE/MC4xNjowLjE0KSk7CiAgICAgICAgZy5iZWdpblBhdGgoKTsKICAgICAgICBnLm1vdmVUbyh4LHkrTCk7IGcubGluZVRvKHgseSk7IGcubGluZVRvKHgrTCx5KTsKICAgICAgICBnLm1vdmVUbyh4K3ctTCx5KTsgZy5saW5lVG8oeCt3LHkpOyBnLmxpbmVUbyh4K3cseStMKTsKICAgICAgICBnLm1vdmVUbyh4K3cseStoLUwpOyBnLmxpbmVUbyh4K3cseStoKTsgZy5saW5lVG8oeCt3LUwseStoKTsKICAgICAgICBnLm1vdmVUbyh4K0wseStoKTsgZy5saW5lVG8oeCx5K2gpOyBnLmxpbmVUbyh4LHkraC1MKTsKICAgICAgICBnLnN0cm9rZSgpOwogICAgICAgIGcuc2F2ZSgpOwogICAgICAgIGcuZ2xvYmFsQWxwaGE9Y2FqYT8wLjQ1OjAuMjA7CiAgICAgICAgZy5saW5lV2lkdGg9MS42OyBnLnN0cm9rZVJlY3QoeCx5LHcsaCk7CiAgICAgICAgZy5yZXN0b3JlKCk7CiAgICAgIH1jYXRjaChlKXt9CiAgICB9OwogICAgdmFyIHBpbnRhclF1YWQ9ZnVuY3Rpb24ocXVhZCwgZXN0YWRvLCBudW1lcm8pewogICAgICB0cnl7CiAgICAgICAgdmFyIG92PSQob3ZJZCk7IGlmKCFvdil7IHJldHVybjsgfQogICAgICAgIHZhciB2dz0odiYmdi52aWRlb1dpZHRoKXx8MCwgdmg9KHYmJnYudmlkZW9IZWlnaHQpfHwwOwogICAgICAgIGlmKCF2d3x8IXZoKXsgcmV0dXJuOyB9CiAgICAgICAgaWYob3Yud2lkdGghPT12d3x8b3YuaGVpZ2h0IT09dmgpeyBvdi53aWR0aD12dzsgb3YuaGVpZ2h0PXZoOyB9CiAgICAgICAgdmFyIGc9b3YuZ2V0Q29udGV4dCgnMmQnKTsgaWYoIWcpeyByZXR1cm47IH0KICAgICAgICBnLmNsZWFyUmVjdCgwLDAsdncsdmgpOwogICAgICAgIGlmKHF1YWQmJnF1YWQudGwmJnF1YWQudHImJnF1YWQuYnImJnF1YWQuYmwpewogICAgICAgICAgdmFyIGNvbD0oZXN0YWRvPT09J29rJyk/JyMzZmI5NTAnOigoZXN0YWRvPT09J21hbCcpPycjZTY3ZTIyJzonI2UzYjM0MScpOwogICAgICAgICAgdHJ5ewogICAgICAgICAgICBnLmZpbGxTdHlsZT0ncmdiYSgwLDAsMCwwLjQ1KSc7CiAgICAgICAgICAgIGcuYmVnaW5QYXRoKCk7CiAgICAgICAgICAgIGcucmVjdCgwLDAsdncsdmgpOwogICAgICAgICAgICBnLm1vdmVUbyhxdWFkLnRsLngscXVhZC50bC55KTsgZy5saW5lVG8ocXVhZC50ci54LHF1YWQudHIueSk7IGcubGluZVRvKHF1YWQuYnIueCxxdWFkLmJyLnkpOyBnLmxpbmVUbyhxdWFkLmJsLngscXVhZC5ibC55KTsgZy5jbG9zZVBhdGgoKTsKICAgICAgICAgICAgZy5maWxsKCdldmVub2RkJyk7CiAgICAgICAgICB9Y2F0Y2goZUYpeyBnLmZpbGxTdHlsZT0ncmdiYSgwLDAsMCwwLjIyKSc7IGcuZmlsbFJlY3QoMCwwLHZ3LHZoKTsgfQogICAgICAgICAgZy5zdHJva2VTdHlsZT1jb2w7IGcubGluZVdpZHRoPTU7IGcubGluZUpvaW49J3JvdW5kJzsKICAgICAgICAgIGcuYmVnaW5QYXRoKCk7CiAgICAgICAgICBnLm1vdmVUbyhxdWFkLnRsLngscXVhZC50bC55KTsgZy5saW5lVG8ocXVhZC50ci54LHF1YWQudHIueSk7IGcubGluZVRvKHF1YWQuYnIueCxxdWFkLmJyLnkpOyBnLmxpbmVUbyhxdWFkLmJsLngscXVhZC5ibC55KTsgZy5jbG9zZVBhdGgoKTsKICAgICAgICAgIGcuc3Ryb2tlKCk7CiAgICAgICAgICBnLmZpbGxTdHlsZT1jb2w7CiAgICAgICAgICB2YXIgcHRzPVtxdWFkLnRsLHF1YWQudHIscXVhZC5icixxdWFkLmJsXSwgaTsKICAgICAgICAgIGZvcihpPTA7aTw0O2krKyl7IGcuYmVnaW5QYXRoKCk7IGcuYXJjKHB0c1tpXS54LHB0c1tpXS55LDksMCxNYXRoLlBJKjIpOyBnLmZpbGwoKTsgfQogICAgICAgIH1lbHNlewogICAgICAgICAgdmFyIHgyPU1hdGgucm91bmQodncqMC4wNyksIHkyPU1hdGgucm91bmQodmgqMC4xMiksIHcyPXZ3LXgyKjIsIGgyPXZoLXkyKjI7CiAgICAgICAgICBnLnN0cm9rZVN0eWxlPShlc3RhZG89PT0nbWFsJyk/JyNlNjdlMjInOicjOWFhMGE2JzsKICAgICAgICAgIGcubGluZVdpZHRoPTQ7IGcuc2V0TGluZURhc2goWzE0LDEwXSk7CiAgICAgICAgICBnLnN0cm9rZVJlY3QoeDIseTIsdzIsaDIpOwogICAgICAgICAgZy5zZXRMaW5lRGFzaChbXSk7CiAgICAgICAgfQogICAgICAgIGlmKG51bWVybz4wKXsKICAgICAgICAgIGcuc2F2ZSgpOwogICAgICAgICAgZy5mb250PSdib2xkIDExMHB4IHNhbnMtc2VyaWYnOyBnLnRleHRBbGlnbj0nY2VudGVyJzsgZy50ZXh0QmFzZWxpbmU9J21pZGRsZSc7CiAgICAgICAgICBnLmxpbmVXaWR0aD0xMDsgZy5zdHJva2VTdHlsZT0ncmdiYSgwLDAsMCwwLjU1KSc7CiAgICAgICAgICBnLnN0cm9rZVRleHQoU3RyaW5nKG51bWVybyksdncvMix2aC8yKTsKICAgICAgICAgIGcuZmlsbFN0eWxlPScjM2ZiOTUwJzsgZy5maWxsVGV4dChTdHJpbmcobnVtZXJvKSx2dy8yLHZoLzIpOwogICAgICAgICAgZy5yZXN0b3JlKCk7CiAgICAgICAgfQogICAgICB9Y2F0Y2goZSl7fQogICAgfTsKICAgIHZhciBwaW50YXJPdmFsbz1mdW5jdGlvbihlc3RhZG8sIG51bWVybywgaW5mbyl7CiAgICAgIHRyeXsKICAgICAgICB2YXIgb3Y9JChvdklkKTsgaWYoIW92KXsgcmV0dXJuOyB9CiAgICAgICAgdmFyIHZ3PSh2JiZ2LnZpZGVvV2lkdGgpfHwwLCB2aD0odiYmdi52aWRlb0hlaWdodCl8fDA7CiAgICAgICAgaWYoIXZ3fHwhdmgpeyByZXR1cm47IH0KICAgICAgICBpZihvdi53aWR0aCE9PXZ3fHxvdi5oZWlnaHQhPT12aCl7IG92LndpZHRoPXZ3OyBvdi5oZWlnaHQ9dmg7IH0KICAgICAgICB2YXIgZz1vdi5nZXRDb250ZXh0KCcyZCcpOyBpZighZyl7IHJldHVybjsgfQogICAgICAgIGcuY2xlYXJSZWN0KDAsMCx2dyx2aCk7CiAgICAgICAgdmFyIGN4PXZ3KjAuNSwgY3k9dmgqMC41Miwgcng9dncqMC4zMCwgcnk9dmgqMC4zODsKICAgICAgICB2YXIgY29sPShlc3RhZG89PT0nb2snKT8nIzNmYjk1MCc6KChlc3RhZG89PT0nY2FyYScpPycjZTNiMzQxJzonIzlhYTBhNicpOwogICAgICAgIHRyeXsKICAgICAgICAgIGcuZmlsbFN0eWxlPSdyZ2JhKDAsMCwwLDAuNDApJzsKICAgICAgICAgIGcuYmVnaW5QYXRoKCk7CiAgICAgICAgICBnLnJlY3QoMCwwLHZ3LHZoKTsKICAgICAgICAgIGcubW92ZVRvKGN4K3J4LGN5KTsKICAgICAgICAgIGlmKGcuZWxsaXBzZSl7IGcuZWxsaXBzZShjeCxjeSxyeCxyeSwwLDAsTWF0aC5QSSoyKTsgfSBlbHNlIHsgZy5yZWN0KGN4LXJ4LGN5LXJ5LHJ4KjIscnkqMik7IH0KICAgICAgICAgIGcuZmlsbCgnZXZlbm9kZCcpOwogICAgICAgIH1jYXRjaChlRil7IGcuZmlsbFN0eWxlPSdyZ2JhKDAsMCwwLDAuMjIpJzsgZy5maWxsUmVjdCgwLDAsdncsdmgpOyB9CiAgICAgICAgZy5zYXZlKCk7CiAgICAgICAgZy5zdHJva2VTdHlsZT1jb2w7IGcubGluZVdpZHRoPTY7CiAgICAgICAgZy5iZWdpblBhdGgoKTsgaWYoZy5lbGxpcHNlKXsgZy5lbGxpcHNlKGN4LGN5LHJ4LHJ5LDAsMCxNYXRoLlBJKjIpOyB9IGVsc2UgeyBnLnN0cm9rZVJlY3QoY3gtcngsY3ktcnkscngqMixyeSoyKTsgfQogICAgICAgIGcuc3Ryb2tlKCk7CiAgICAgICAgZy5yZXN0b3JlKCk7CiAgICAgICAgaWYoaW5mbyYmaW5mby5jYWphJiZpbmZvLmNhamEudz40KXsKICAgICAgICAgIGcuc3Ryb2tlU3R5bGU9KGVzdGFkbz09PSdvaycpPycjM2ZiOTUwJzonI2UzYjM0MSc7IGcubGluZVdpZHRoPTM7CiAgICAgICAgICBnLnN0cm9rZVJlY3QoaW5mby5jYWphLngsaW5mby5jYWphLnksaW5mby5jYWphLncsaW5mby5jYWphLmgpOwogICAgICAgIH0KICAgICAgICB2YXIgcHJvZz0oc3QmJnN0LmF1dG8pP01hdGgubWluKDEsc3QuYXV0by80KTowOwogICAgICAgIGlmKHByb2c+MCl7CiAgICAgICAgICBnLnNhdmUoKTsgZy5zdHJva2VTdHlsZT0nIzNmYjk1MCc7IGcubGluZVdpZHRoPTg7CiAgICAgICAgICBnLmJlZ2luUGF0aCgpOwogICAgICAgICAgZy5hcmMoY3gsY3ksTWF0aC5tYXgocngscnkpKzE2LC1NYXRoLlBJLzIsLU1hdGguUEkvMitwcm9nKk1hdGguUEkqMik7CiAgICAgICAgICBnLnN0cm9rZSgpOyBnLnJlc3RvcmUoKTsKICAgICAgICB9CiAgICAgICAgaWYobnVtZXJvPjApewogICAgICAgICAgZy5zYXZlKCk7CiAgICAgICAgICBnLmZvbnQ9J2JvbGQgMTEwcHggc2Fucy1zZXJpZic7IGcudGV4dEFsaWduPSdjZW50ZXInOyBnLnRleHRCYXNlbGluZT0nbWlkZGxlJzsKICAgICAgICAgIGcubGluZVdpZHRoPTEwOyBnLnN0cm9rZVN0eWxlPSdyZ2JhKDAsMCwwLDAuNTUpJzsKICAgICAgICAgIGcuc3Ryb2tlVGV4dChTdHJpbmcobnVtZXJvKSx2dy8yLHZoLzIpOwogICAgICAgICAgZy5maWxsU3R5bGU9JyMzZmI5NTAnOyBnLmZpbGxUZXh0KFN0cmluZyhudW1lcm8pLHZ3LzIsdmgvMik7CiAgICAgICAgICBnLnJlc3RvcmUoKTsKICAgICAgICB9CiAgICAgIH1jYXRjaChlKXt9CiAgICB9OwogICAgdmFyIHVsdGltbz0nJzsKICAgIHZhciBhdmlzYXI9ZnVuY3Rpb24oY29kZSx0eHQsY29sb3IpeyBpZihjb2RlIT09dWx0aW1vKXsgdWx0aW1vPWNvZGU7IG1zZyhzdElkLHR4dCxjb2xvcik7IH0gfTsKICAgIGlmKHBzSWQ9PT0nNCcpewogICAgICBwaW50YXJPdmFsbygnJywwLG51bGwpOwogICAgICBhdmlzYXIoJ2luaScsJ1BvbiB0dSBjYXJhIGRlbnRybyBkZWwgT1ZBTE8uIExhIGNhcHR1cmEgZXMgQVVUT01BVElDQSBjdWFuZG8gdG9kbyBlc3RlIGNvcnJlY3RvLicsJyNhNjAnKTsKICAgICAgaWYoc3QuaXYpeyB0cnl7IGNsZWFySW50ZXJ2YWwoc3QuaXYpOyB9Y2F0Y2goZSl7fSB9CiAgICAgIHN0Lml2PXNldEludGVydmFsKGZ1bmN0aW9uKCl7CiAgICAgICAgdHJ5ewogICAgICAgICAgaWYoIXN0cmVhbXNbcHNJZF0peyByZXR1cm47IH0KICAgICAgICAgIGJ1c2NhckNhcmFWaXZhKHYsZnVuY3Rpb24oaW5mbyl7CiAgICAgICAgICAgIHRyeXsKICAgICAgICAgICAgICBFU1QuY2FyYVZpdmE9aW5mbzsKICAgICAgICAgICAgICBpZighaW5mb3x8IWluZm8udmlzdGEpewogICAgICAgICAgICAgICAgc3QuYXV0bz0wOyBzdC5jZD0wOwogICAgICAgICAgICAgICAgcGludGFyT3ZhbG8oJ2NhcmEnLDAsaW5mb3x8bnVsbCk7CiAgICAgICAgICAgICAgICBhdmlzYXIoKGluZm8mJmluZm8uY29kKXx8J25vZGV0JywoaW5mbyYmaW5mby5tb3Rpdm8pfHwnQnVzY2FuZG8gdHUgY2FyYS4uLiBidWVuYSBsdXosIHNpbiBnb3JyYSBuaSBsZW50ZXMgb3NjdXJvcy4nLCcjYTYwJyk7CiAgICAgICAgICAgICAgICByZXR1cm47CiAgICAgICAgICAgICAgfQogICAgICAgICAgICAgIHZhciBudW1lcm89MDsKICAgICAgICAgICAgICBpZihpbmZvLm9rKXsgc3QuYXV0bz0oc3QuYXV0b3x8MCkrMTsgfSBlbHNlIHsgc3QuYXV0bz0wOyBzdC5jZD0wOyB9CiAgICAgICAgICAgICAgaWYoc3QuYXV0bz49NCl7CiAgICAgICAgICAgICAgICBzdC5jZD0oc3QuY2R8fDApKzE7CiAgICAgICAgICAgICAgICBudW1lcm89TWF0aC5tYXgoMSw0LXN0LmNkKTsKICAgICAgICAgICAgICAgIHBpbnRhck92YWxvKCdvaycsbnVtZXJvLGluZm8pOwogICAgICAgICAgICAgICAgYXZpc2FyKCdjZCcrbnVtZXJvLCdDYXB0dXJhbmRvIGVuICcrbnVtZXJvKycuLi4gbm8gdGUgbXVldmFzLicsJyMwODAnKTsKICAgICAgICAgICAgICAgIGlmKHN0LmNkPj00JiYhc3QuYXV0b0hlY2hvKXsKICAgICAgICAgICAgICAgICAgc3QuYXV0b0hlY2hvPXRydWU7IHZpYnJhcigpOwogICAgICAgICAgICAgICAgICBwcm9jZXNhclNlbGZpZSgpOwogICAgICAgICAgICAgICAgfQogICAgICAgICAgICAgICAgcmV0dXJuOwogICAgICAgICAgICAgIH0KICAgICAgICAgICAgICBwaW50YXJPdmFsbyhpbmZvLm9rPydvayc6J2NhcmEnLDAsaW5mbyk7CiAgICAgICAgICAgICAgYXZpc2FyKGluZm8ub2s/J3ByZSc6aW5mby5jb2QsIGluZm8ubW90aXZvLCBpbmZvLm9rPycjMDgwJzonI2E2MCcpOwogICAgICAgICAgICB9Y2F0Y2goZTMpe30KICAgICAgICAgIH0pOwogICAgICAgIH1jYXRjaChlKXt9CiAgICAgIH0sNDMwKTsKICAgIH1lbHNlewogICAgICBwaW50YXJEb2MobnVsbCwnJyk7CiAgICAgIGF2aXNhcignaW5pJywnQnVzY2FuZG8gZWwgZG9jdW1lbnRvLi4uIHBvbmxvIHNvYnJlIGZvbmRvIE9TQ1VSTywgc2luIGJyaWxsby4gTGFzIDQgZXNxdWluYXMgc2UgbWFyY2FuIHNvbGFzLicsJyNhNjAnKTsKICAgICAgaWYoc3QuaXYpeyB0cnl7IGNsZWFySW50ZXJ2YWwoc3QuaXYpOyB9Y2F0Y2goZSl7fSB9CiAgICAgIHN0Lml2PXNldEludGVydmFsKGZ1bmN0aW9uKCl7CiAgICAgICAgdHJ5ewogICAgICAgICAgaWYoIXN0cmVhbXNbcHNJZF0peyByZXR1cm47IH0KICAgICAgICAgIHZhciBxPWRldGVjdGFyRG9jUXVhZCh2KTsKICAgICAgICAgIHZhciBlc3Q9J21hbCcsIGNvZD0nbm9uZScsIHR4dD0nQnVzY2FuZG8gZWwgZG9jdW1lbnRvLi4uIHBvbmxvIHNvYnJlIGZvbmRvIE9TQ1VSTywgbGxlbmFuZG8gZWwgbWFyY28sIHNpbiBicmlsbG8uJywgY29sPScjYTYwJywgcXVhZD1udWxsLCBudW1lcm89MDsKICAgICAgICAgIGlmKHEmJnEubGxlbm8pewogICAgICAgICAgICB2YXIgYjE9cS5sdXo+PTQ4LCBiMj1xLm5pdG8+PTM0LCBiMz0ocS5ibGFuY289PW51bGwpfHwocS5ibGFuY288PTAuMjIpOwogICAgICAgICAgICBzdC5hdXRvPTA7CiAgICAgICAgICAgIGlmKCFiMSl7IHN0LmNkPTA7IGVzdD0nbWFsJzsgY29kPSdsdXonOyB0eHQ9J1BPQ0EgTFVaOiBidXNjYSBtZWpvciBpbHVtaW5hY2lvbiBvIHVzYSBFbGVnaXIgYXJjaGl2byBjb24gdW5hIGZvdG8gZGUgY2VyY2EuJzsgY29sPScjYzAwJzsgfQogICAgICAgICAgICBlbHNlIGlmKCFiMil7IHN0LmNkPTA7IGVzdD0nbWFsJzsgY29kPSduaXRvJzsgdHh0PSdObyBzZSB2ZSBOSVRJRE86IHNvc3RcdTAwRTluIGZpcm1lLCBlc3BlcmEgZWwgZW5mb3F1ZSB5IGV2aXRhIGVsIGJyaWxsby4nOyBjb2w9JyNjMDAnOyB9CiAgICAgICAgICAgIGVsc2UgaWYoIWIzKXsgc3QuY2Q9MDsgZXN0PSdtYWwnOyBjb2Q9J2JsYSc7IHR4dD0nSGF5IFJFRkxFSk8gZW4gZWwgZG9jdW1lbnRvOiBpbmNsXHUwMEVEbmFsbyB1biBwb2NvIHBhcmEgcXVpdGFyIGVsIGJyaWxsby4nOyBjb2w9JyNjMDAnOyB9CiAgICAgICAgICAgIGVsc2V7CiAgICAgICAgICAgICAgLyogaGVyZWRhZG8gdjE0OiBzaSBlbCBkb2N1bWVudG8gbGxlbmEgZWwgY3VhZHJvIGNvbiBsdXogeSBuaXRpZGV6LAogICAgICAgICAgICAgICAgIHRhbWJpZW4gY2FwdHVyYSBTT0xPIGNvbiBjdWVudGEgYXRyYXMgKGFudGVzIG9ibGlnYWJhIGEgdG9jYXIKICAgICAgICAgICAgICAgICBDQVBUVVJBUikuIE1pc21vIDMtMi0xIHF1ZSBjdWFuZG8gaGF5IDQgZXNxdWluYXMuICovCiAgICAgICAgICAgICAgc3QuY2Q9KHN0LmNkfHwwKSsxOwogICAgICAgICAgICAgIG51bWVybz1NYXRoLm1heCgxLDQtc3QuY2QpOwogICAgICAgICAgICAgIGVzdD0nb2snOyBjb2Q9J2NkJytudW1lcm87IHR4dD0nQ2FwdHVyYW5kbyBlbiAnK251bWVybysnLi4uIG5vIHRlIG11ZXZhcy4nOyBjb2w9JyMwODAnOwogICAgICAgICAgICAgIGlmKHN0LmNkPj00JiYhc3QuYXV0b0hlY2hvKXsKICAgICAgICAgICAgICAgIHN0LmF1dG9IZWNobz10cnVlOyB2aWJyYXIoKTsKICAgICAgICAgICAgICAgIG1hbmVqYXIocHNJZD09PScyJz8nYkNhcEYnOidiQ2FwQScpOwogICAgICAgICAgICAgICAgcmV0dXJuOwogICAgICAgICAgICAgIH0KICAgICAgICAgICAgfQogICAgICAgICAgICBwaW50YXJEb2MobnVsbCwgZXN0KTsKICAgICAgICAgIH1lbHNlIGlmKHEpewogICAgICAgICAgICBxdWFkPXE7CiAgICAgICAgICAgIHN0Lmhpc3QucHVzaChxdWFkKTsgc3QudWx0UXVhZD1xdWFkOyBzdC51bHRRdWFkVD1EYXRlLm5vdygpOwogICAgICAgICAgICBpZihzdC5oaXN0Lmxlbmd0aD43KXsgc3QuaGlzdC5zaGlmdCgpOyB9CiAgICAgICAgICAgIHZhciBjMT1xLmx1ej49NDgsIGMyPXEubml0bz49MzQsIGMzPShxLmJsYW5jbz09bnVsbCl8fChxLmJsYW5jbzw9MC4yMCk7CiAgICAgICAgICAgIHN0LmF1dG89MDsgc3QuY2Q9MDsKICAgICAgICAgICAgaWYocS5kZXNjYXJ0YWRvPT09J3BlcXVlbm8nKXsgZXN0PSdtYWwnOyBjb2Q9J2Zhcic7IHR4dD0nQUNFUkNBVEU6IGVsIGRvY3VtZW50byBzZSB2ZSBtdXkgcGVxdWVcdTAwRjFvIGVuIGxhIGZvdG8uJzsgY29sPScjYTYwJzsgfQogICAgICAgICAgICBlbHNlIGlmKHEuZGVzY2FydGFkbz09PSdmb3JtYScpeyBlc3Q9J21hbCc7IGNvZD0nZm9ybWEnOyB0eHQ9J05vIHZlbyBiaWVuIGxhcyA0IGVzcXVpbmFzOiBhY1x1MDBFOXJjYXRlIHkgdXNhIHVuIGZvbmRvIG9zY3Vyby4nOyBjb2w9JyNhNjAnOyB9CiAgICAgICAgICAgIGVsc2UgaWYoIWMxKXsgZXN0PSdtYWwnOyBjb2Q9J2x1eic7IHR4dD0nUE9DQSBMVVo6IGJ1c2NhIG1lam9yIGlsdW1pbmFjaW9uIG8gdXNhIEVsZWdpciBhcmNoaXZvIGNvbiB1bmEgZm90byBkZSBjZXJjYS4nOyBjb2w9JyNjMDAnOyB9CiAgICAgICAgICAgIGVsc2UgaWYoIWMyKXsgZXN0PSdtYWwnOyBjb2Q9J25pdG8nOyB0eHQ9J05vIHNlIHZlIE5JVElETzogc29zdFx1MDBFOW4gZmlybWUsIGVzcGVyYSBlbCBlbmZvcXVlIHkgZXZpdGEgZWwgYnJpbGxvLic7IGNvbD0nI2MwMCc7IH0KICAgICAgICAgICAgZWxzZSBpZighYzMpeyBlc3Q9J21hbCc7IGNvZD0nYmxhJzsgdHh0PSdIYXkgUkVGTEVKTyBlbiBlbCBkb2N1bWVudG86IGluY2xcdTAwRURuYWxvIHVuIHBvY28gcGFyYSBxdWl0YXIgZWwgYnJpbGxvLic7IGNvbD0nI2MwMCc7IH0KICAgICAgICAgICAgZWxzZSBpZihxdWFkRXN0YWJsZShzdC5oaXN0KSl7CiAgICAgICAgICAgICAgc3QuYXV0bz0xOwogICAgICAgICAgICAgIHN0LmNkPShzdC5jZHx8MCkrMTsKICAgICAgICAgICAgICBudW1lcm89TWF0aC5tYXgoMSw0LXN0LmNkKTsKICAgICAgICAgICAgICBlc3Q9J29rJzsgY29kPSdjZCcrbnVtZXJvOyB0eHQ9J0NhcHR1cmFuZG8gZW4gJytudW1lcm8rJy4uLiBubyB0ZSBtdWV2YXMuJzsgY29sPScjMDgwJzsKICAgICAgICAgICAgICBpZihzdC5jZD49NCYmIXN0LmF1dG9IZWNobyl7CiAgICAgICAgICAgICAgICBzdC5hdXRvSGVjaG89dHJ1ZTsgdmlicmFyKCk7CiAgICAgICAgICAgICAgICBtYW5lamFyKHBzSWQ9PT0nMic/J2JDYXBGJzonYkNhcEEnKTsKICAgICAgICAgICAgICAgIHJldHVybjsKICAgICAgICAgICAgICB9CiAgICAgICAgICAgIH1lbHNlewogICAgICAgICAgICAgIGVzdD0nY2FzaSc7IGNvZD0nZXNwZXJhJzsgdHh0PSdEb2N1bWVudG8gZGV0ZWN0YWRvLiBTb3N0ZW5sbyBxdWlldG8gcGFyYSBjYXB0dXJhciBzb2xvLi4uJzsgY29sPScjMDgwJzsKICAgICAgICAgICAgfQogICAgICAgICAgICBwaW50YXJRdWFkKHF1YWQsIGVzdCwgbnVtZXJvKTsKICAgICAgICAgIH1lbHNlewogICAgICAgICAgICBzdC5hdXRvPTA7IHN0LmNkPTA7CiAgICAgICAgICAgIGlmKERhdGUubm93KCktc3QudD4xMjAwKXsgc3QuY2FqYT1udWxsOyB9CiAgICAgICAgICAgIHZhciBjYWphRj1kZXRlY3RhckRvY0JveCh2KTsKICAgICAgICAgICAgaWYoY2FqYUYpewogICAgICAgICAgICAgIHN0LmNhamE9Y2FqYUY7IHN0LnVsdENhamE9Y2FqYUY7IHN0LnVsdENhamFUPURhdGUubm93KCk7IHN0LnQ9RGF0ZS5ub3coKTsKICAgICAgICAgICAgICBlc3Q9KGNhamFGLm5pdG8mJmNhamFGLmx1ej49NDgpPydjYXNpJzonbWFsJzsKICAgICAgICAgICAgICBjb2Q9KGVzdD09PSdjYXNpJyk/J2Fwcm94JzonY2FsJzsKICAgICAgICAgICAgICB0eHQ9KGVzdD09PSdjYXNpJyk/J0Nhc2k6IHNvc3RcdTAwRTluIHF1aWV0by4gQ29uIGZvbmRvIG9zY3VybyBtYXJjbyBsYXMgNCBlc3F1aW5hcyB5IGNhcHR1cm8gc29sby4nOidTZSB2ZSBmbG9qbzogbVx1MDBFMXMgbHV6LCBmaXJtZSwgc2luIGJyaWxsby4nOwogICAgICAgICAgICAgIGNvbD0oZXN0PT09J2Nhc2knKT8nI2E2MCc6JyNjMDAnOwogICAgICAgICAgICB9ZWxzZSBpZihEYXRlLm5vdygpLXN0LnQ+MTIwMCl7CiAgICAgICAgICAgICAgY29kPSdub25lJzsgdHh0PSdCdXNjYW5kbyBlbCBkb2N1bWVudG8uLi4gcG9ubG8gc29icmUgZm9uZG8gT1NDVVJPLCBsbGVuYW5kbyBlbCBtYXJjbywgc2luIGJyaWxsby4nOwogICAgICAgICAgICB9CiAgICAgICAgICAgIHBpbnRhckRvYyhjYWphRnx8c3QuY2FqYXx8bnVsbCwgZXN0KTsKICAgICAgICAgIH0KICAgICAgICAgIGF2aXNhcihjb2QsdHh0LGNvbCk7CiAgICAgICAgfWNhdGNoKGUpe30KICAgICAgfSwzMDApOwogICAgfQogICAgaWYoIXYuX196eU1hcmNvKXsKICAgICAgdi5fX3p5TWFyY289MTsKICAgICAgdi5hZGRFdmVudExpc3RlbmVyKCdwbGF5aW5nJyxmdW5jdGlvbigpeyB0cnl7IGFsaW5lYXJPdmVybGF5KHBzSWQsIHYpOyBpZihwc0lkPT09JzQnKXsgcGludGFyT3ZhbG8oJycsMCxudWxsKTsgfSBlbHNlIHsgcGludGFyRG9jKG51bGwsJycpOyB9IH1jYXRjaChlKXt9IH0pOwogICAgICB2LmFkZEV2ZW50TGlzdGVuZXIoJ2xvYWRlZG1ldGFkYXRhJyxmdW5jdGlvbigpeyB0cnl7IGFsaW5lYXJPdmVybGF5KHBzSWQsIHYpOyBpZihwc0lkPT09JzQnKXsgcGludGFyT3ZhbG8oJycsMCxudWxsKTsgfSBlbHNlIHsgcGludGFyRG9jKG51bGwsJycpOyB9IH1jYXRjaChlKXt9IH0pOwogICAgfQogIH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gaW50ZW50YXJFbmZvcXVlKHN0KXsKICB0cnl7CiAgICB2YXIgdHI9KHN0JiZzdC5nZXRWaWRlb1RyYWNrcyk/c3QuZ2V0VmlkZW9UcmFja3MoKVswXTpudWxsOwogICAgaWYoIXRyKXsgcmV0dXJuOyB9CiAgICB2YXIgY2Fwcz10ci5nZXRDYXBhYmlsaXRpZXM/dHIuZ2V0Q2FwYWJpbGl0aWVzKCk6bnVsbDsKICAgIGlmKGNhcHMmJmNhcHMuZm9jdXNNb2RlJiZjYXBzLmZvY3VzTW9kZS5qb2luJiZjYXBzLmZvY3VzTW9kZS5qb2luKCcgJykuaW5kZXhPZignY29udGludW91cycpPj0wKXsKICAgICAgdmFyIHA9dHIuYXBwbHlDb25zdHJhaW50cyh7YWR2YW5jZWQ6W3tmb2N1c01vZGU6J2NvbnRpbnVvdXMnfV19KTsKICAgICAgaWYocCYmcC5jYXRjaCl7IHAuY2F0Y2goZnVuY3Rpb24oKXt9KTsgfQogICAgfQogIH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gYWJyaXJDYW0ocHNJZCwgZmFjaW5nLCBzdElkLCBjYXBJZCl7CiAgdmFyIHY9ZmluZFZpZGVvKHBzSWQpOwogIGlmKCF2KXsgbXNnKHN0SWQsJ05vIGVuY29udHJlIGVsIHZpZGVvIGRlIGxhIGNhbWFyYSBlbiBsYSBwYWdpbmEuJywgJyNjMDAnKTsgcmV0dXJuIFByb21pc2UucmVqZWN0KG5ldyBFcnJvcignc2luIHZpZGVvJykpOyB9CiAgaWYoIW5hdmlnYXRvci5tZWRpYURldmljZXMgfHwgIW5hdmlnYXRvci5tZWRpYURldmljZXMuZ2V0VXNlck1lZGlhKXsKICAgIG1zZyhzdElkLCdUdSBuYXZlZ2Fkb3Igbm8gcGVybWl0ZSBjYW1hcmEuIFVzYSBsYSBvcGNpb24gZGUgZ2FsZXJpYS4nLCAnI2MwMCcpOwogICAgcmV0dXJuIFByb21pc2UucmVqZWN0KG5ldyBFcnJvcignc2luIGNhbWFyYScpKTsKICB9CiAgcGFyYXJDYW0ocHNJZCk7CiAgdmFyIHpvbmE9JCgndnonK2xldHJhRGUocHNJZCkpOwogIGlmKHpvbmEpeyB6b25hLnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsgfQogIG1zZyhzdElkLCdQaWRpZW5kbyBwZXJtaXNvIGRlIGNhbWFyYS4uLicsJycpOwogIHZhciBkb2Nab25hPShwc0lkPT09JzInfHxwc0lkPT09JzMnKTsKICByZXR1cm4gbmF2aWdhdG9yLm1lZGlhRGV2aWNlcy5nZXRVc2VyTWVkaWEoe2F1ZGlvOmZhbHNlLCB2aWRlbzp7ZmFjaW5nTW9kZTpmYWNpbmcsIHdpZHRoOntpZGVhbDpkb2Nab25hPzE5MjA6MTI4MH0sIGhlaWdodDp7aWRlYWw6ZG9jWm9uYT8xMDgwOjcyMH19fSkudGhlbihmdW5jdGlvbihzdCl7CiAgICBzdHJlYW1zW3BzSWRdPXN0OwogICAgdi5zcmNPYmplY3Q9c3Q7CiAgICB0cnl7IHYuc2V0QXR0cmlidXRlKCdwbGF5c2lubGluZScsJ3BsYXlzaW5saW5lJyk7IH1jYXRjaChlKXt9CiAgICB2Lm11dGVkPXRydWU7CiAgICB0cnl7IHYuc3R5bGUudHJhbnNmb3JtPShwc0lkPT09JzQnKT8nc2NhbGVYKC0xKSc6Jyc7IH1jYXRjaChlTSl7fQogICAgaW50ZW50YXJFbmZvcXVlKHN0KTsKICAgIHZhciBwPXYucGxheSgpOyBpZihwJiZwLmNhdGNoKXsgcC5jYXRjaChmdW5jdGlvbigpe30pOyB9CiAgICBlc3RpbG9DaGljbyh2KTsKICAgIHZhciBjYXA9JChjYXBJZCk7CiAgICBpZihjYXApeyBjYXAuZGlzYWJsZWQ9ZmFsc2U7IGNhcC5zdHlsZS5kaXNwbGF5PScnOyBjYXAuc3R5bGUudmlzaWJpbGl0eT0ndmlzaWJsZSc7IGNhcC5zdHlsZS5wb2ludGVyRXZlbnRzPSdhdXRvJzsgY2FwLnN0eWxlLnBvc2l0aW9uPWNhcC5zdHlsZS5wb3NpdGlvbnx8J3JlbGF0aXZlJzsgY2FwLnN0eWxlLnpJbmRleD0nOTk5OSc7IH0KICAgIHZhciBPVj17JzInOidvdkYnLCczJzonb3ZBJywnNCc6J292Uyd9OwogICAgdmFyIG92PSQoT1ZbcHNJZF0pOwogICAgaWYob3YpeyBvdi5zdHlsZS5wb2ludGVyRXZlbnRzPSdub25lJzsgfQogICAgdmFyIHpvbmE9JCgndnonK2xldHJhRGUocHNJZCkpOwogICAgaWYoem9uYSl7IHpvbmEuc3R5bGUucG9zaXRpb249J3JlbGF0aXZlJzsgfQogICAgZW5tYXJjYXJWZXJkZShwc0lkLCB2KTsKICAgIGFsaW5lYXJPdmVybGF5KHBzSWQsIHYpOwogICAgc2V0VGltZW91dChmdW5jdGlvbigpeyB0cnl7IGFsaW5lYXJPdmVybGF5KHBzSWQsIHYpOyB9Y2F0Y2goZSl7fSB9LDI1MCk7CiAgICB2YXIgcT0ocHNJZD09PSc0Jyk7CiAgICBtc2coc3RJZCwgcT8nQ2FtYXJhIGxpc3RhLiBQb24gdHUgY2FyYSBlbiBlbCBPVkFMTzogc2UgY2FwdHVyYSBTT0xPIGN1YW5kbyB0b2RvIGVzdGUgY29ycmVjdG8uJzonQ2FtYXJhIGxpc3RhLiBCdXNjbyBsYXMgNCBlc3F1aW5hcyBkZWwgZG9jdW1lbnRvOiBzb3N0XHUwMEU5bmxvIHF1aWV0byB5IGNhcHR1cm8gc29sby4nLCcjMDgwJyk7CiAgICByZXR1cm4gdHJ1ZTsKICB9KS5jYXRjaChmdW5jdGlvbihlKXsKICAgIGlmKHpvbmEpeyB0cnl7IHpvbmEuc3R5bGUuZGlzcGxheT0nbm9uZSc7IH1jYXRjaChlMil7fSB9CiAgICBtc2coc3RJZCwnTm8gcHVkZSBhYnJpciBsYSBjYW1hcmEgKCcrKGUmJmUubmFtZT9lLm5hbWU6J2Vycm9yJykrJykuIFB1ZWRlcyB1c2FyIGxhIGdhbGVyaWEgbyByZXZpc2EgZWwgcGVybWlzby4nLCcjYzAwJyk7CiAgICB0aHJvdyBlOwogIH0pOwp9CmZ1bmN0aW9uIHBhcmFyQ2FtKHBzSWQpewogIHZhciBzdD1zdHJlYW1zW3BzSWRdOwogIGlmKHN0KXsKICAgIHRyeXsgc3QuZ2V0VHJhY2tzKCkuZm9yRWFjaChmdW5jdGlvbih0KXsgdHJ5eyB0LnN0b3AoKTsgfWNhdGNoKGUpe30gfSk7IH1jYXRjaChlKXt9CiAgfQogIHN0cmVhbXNbcHNJZF09bnVsbDsKICB0cnl7CiAgICB2YXIgdnY9ZmluZFZpZGVvKHBzSWQpOwogICAgaWYodnYpeyB2di5zdHlsZS50cmFuc2Zvcm09Jyc7IH0KICB9Y2F0Y2goZVQpe30KICB0cnl7CiAgICB2YXIgRD16eURldCgpLCBzdEQ9RFtwc0lkXTsKICAgIGlmKHN0RCYmc3RELml2KXsgY2xlYXJJbnRlcnZhbChzdEQuaXYpOyBzdEQuaXY9bnVsbDsgfQogICAgaWYocHNJZD09PSc0Jyl7IEVTVC5jYXJhVml2YT1udWxsOyB9CiAgfWNhdGNoKGUpe30KICB0cnl7CiAgICB2YXIgem9uYT0kKCd2eicrbGV0cmFEZShwc0lkKSk7CiAgICBpZih6b25hKXsgem9uYS5zdHlsZS5kaXNwbGF5PSdub25lJzsgfQogICAgdmFyIE9WPXsnMic6J292RicsJzMnOidvdkEnLCc0Jzonb3ZTJ307CiAgICB2YXIgb3Y9JChPVltwc0lkXSk7CiAgICBpZihvdil7IHZhciBnPW92LmdldENvbnRleHQoJzJkJyk7IGlmKGcpeyBnLmNsZWFyUmVjdCgwLDAsb3Yud2lkdGh8fDEsb3YuaGVpZ2h0fHwxKTsgfSB9CiAgfWNhdGNoKGUpe30KfQpmdW5jdGlvbiBwYXJhclRvZGFzKCl7IHZhciBrOyBmb3IoayBpbiBzdHJlYW1zKXsgcGFyYXJDYW0oayk7IH0gfQpmdW5jdGlvbiBjYXB0dXJhclZpZGVvKHBzSWQsIG1heERpbSl7CiAgdmFyIHY9ZmluZFZpZGVvKHBzSWQpOwogIGlmKCF2IHx8ICF2LnZpZGVvV2lkdGggfHwgIXN0cmVhbXNbcHNJZF0peyByZXR1cm4gbnVsbDsgfQogIHZhciB3PXYudmlkZW9XaWR0aCwgaD12LnZpZGVvSGVpZ2h0OwogIHZhciBzYz1NYXRoLm1pbigxLChtYXhEaW18fDEwMjQpL01hdGgubWF4KHcsaCkpOwogIHZhciBjPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2NhbnZhcycpOwogIGMud2lkdGg9TWF0aC5yb3VuZCh3KnNjKTsgYy5oZWlnaHQ9TWF0aC5yb3VuZChoKnNjKTsKICBjLmdldENvbnRleHQoJzJkJykuZHJhd0ltYWdlKHYsMCwwLGMud2lkdGgsYy5oZWlnaHQpOwogIHZhciBkPWMudG9EYXRhVVJMKCdpbWFnZS9qcGVnJywwLjkpOwogIHBhcmFyQ2FtKHBzSWQpOwogIHJldHVybiBkOwp9CmZ1bmN0aW9uIGRvd25zY2FsZShkYXRhVXJsLCBtYXhEaW0pewogIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpewogICAgdmFyIGltPW5ldyBJbWFnZSgpOwogICAgaW0ub25sb2FkPWZ1bmN0aW9uKCl7CiAgICAgIHZhciBzYz1NYXRoLm1pbigxLChtYXhEaW18fDEwMjQpL01hdGgubWF4KGltLndpZHRoLGltLmhlaWdodCkpOwogICAgICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICAgICAgYy53aWR0aD1NYXRoLm1heCgxLE1hdGgucm91bmQoaW0ud2lkdGgqc2MpKTsKICAgICAgYy5oZWlnaHQ9TWF0aC5tYXgoMSxNYXRoLnJvdW5kKGltLmhlaWdodCpzYykpOwogICAgICBjLmdldENvbnRleHQoJzJkJykuZHJhd0ltYWdlKGltLDAsMCxjLndpZHRoLGMuaGVpZ2h0KTsKICAgICAgcmVzKGMudG9EYXRhVVJMKCdpbWFnZS9qcGVnJywwLjkpKTsKICAgIH07CiAgICBpbS5vbmVycm9yPWZ1bmN0aW9uKCl7IHJlcyhkYXRhVXJsKTsgfTsKICAgIGltLnNyYz1kYXRhVXJsOwogIH0pOwp9CmZ1bmN0aW9uIGFyY2hpdm9BRGF0b3MoZmlsZSl7CiAgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyxyZWopewogICAgdmFyIGZyPW5ldyBGaWxlUmVhZGVyKCk7CiAgICBmci5vbmxvYWQ9ZnVuY3Rpb24oKXsgcmVzKFN0cmluZyhmci5yZXN1bHQpKTsgfTsKICAgIGZyLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVqKG5ldyBFcnJvcignbm8gcHVkZSBsZWVyIGVsIGFyY2hpdm8nKSk7IH07CiAgICBmci5yZWFkQXNEYXRhVVJMKGZpbGUpOwogIH0pOwp9CgovKiA9PT09PT09PT09PT09PT09PSBPQ1IgY29uIGNhY2hlICsgbWVqb3JhIGRlIGltYWdlbiA9PT09PT09PT09PT09PT09PSAqLwp2YXIgY2FjaGVPY3I9e30sIHByb21lc2FXb3JrZXI9bnVsbDsKZnVuY3Rpb24gYWJyaXJXb3JrZXJPY3IoKXsKICBpZihwcm9tZXNhV29ya2VyKXsgcmV0dXJuIHByb21lc2FXb3JrZXI7IH0KICB0cnl7CiAgICBpZih0eXBlb2YgVGVzc2VyYWN0IT09J3VuZGVmaW5lZCcgJiYgVGVzc2VyYWN0LmNyZWF0ZVdvcmtlcil7CiAgICAgIHByb21lc2FXb3JrZXI9VGVzc2VyYWN0LmNyZWF0ZVdvcmtlcignc3BhK2VuZycsMSx7bG9nZ2VyOmZ1bmN0aW9uKCl7fX0pLnRoZW4oZnVuY3Rpb24odyl7IHJldHVybiB3OyB9KS5jYXRjaChmdW5jdGlvbigpeyByZXR1cm4gbnVsbDsgfSk7CiAgICAgIHJldHVybiBwcm9tZXNhV29ya2VyOwogICAgfQogIH1jYXRjaChlKXt9CiAgcHJvbWVzYVdvcmtlcj1Qcm9taXNlLnJlc29sdmUobnVsbCk7CiAgcmV0dXJuIHByb21lc2FXb3JrZXI7Cn0KZnVuY3Rpb24gbWVqb3JhckltYWdlbihkYXRhVXJsKXsKICByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsKICAgIHZhciBpbT1uZXcgSW1hZ2UoKTsKICAgIGltLm9ubG9hZD1mdW5jdGlvbigpewogICAgICB0cnl7CiAgICAgICAgdmFyIGFuY2hvPWltLndpZHRoLCBhbHRvPWltLmhlaWdodDsKICAgICAgICB2YXIgZXNjMT1NYXRoLm1pbigzLCBNYXRoLm1heCgxLCAxNDAwL01hdGgubWF4KDEsTWF0aC5taW4oYW5jaG8sYWx0bykpKSk7CiAgICAgICAgdmFyIGVzYzI9TWF0aC5taW4oMSwgMjYwMC9NYXRoLm1heCgxLE1hdGgubWF4KGFuY2hvLGFsdG8pKSk7CiAgICAgICAgdmFyIHNjPU1hdGgubWluKGVzYzEsZXNjMik7CiAgICAgICAgaWYoIShzYz4wKSl7IHNjPTE7IH0KICAgICAgICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICAgICAgICBjLndpZHRoPU1hdGgubWF4KDEsTWF0aC5yb3VuZChhbmNobypzYykpOwogICAgICAgIGMuaGVpZ2h0PU1hdGgubWF4KDEsTWF0aC5yb3VuZChhbHRvKnNjKSk7CiAgICAgICAgdmFyIGc9Yy5nZXRDb250ZXh0KCcyZCcpOwogICAgICAgIGlmKCFnKXsgcmVzKG51bGwpOyByZXR1cm47IH0KICAgICAgICBnLmltYWdlU21vb3RoaW5nRW5hYmxlZD10cnVlOwogICAgICAgIHRyeXsgZy5pbWFnZVNtb290aGluZ1F1YWxpdHk9J2hpZ2gnOyB9Y2F0Y2goZTIpe30KICAgICAgICBnLmRyYXdJbWFnZShpbSwwLDAsYy53aWR0aCxjLmhlaWdodCk7CiAgICAgICAgdmFyIGlkZD1nLmdldEltYWdlRGF0YSgwLDAsYy53aWR0aCxjLmhlaWdodCksIHA9aWRkLmRhdGEsIG49cC5sZW5ndGgvNDsKICAgICAgICB2YXIgaGlzdD1uZXcgSW50MzJBcnJheSgyNTYpLCBpLCBrLCBzdW09MDsKICAgICAgICBmb3IoaT0wO2k8bjtpKyspeyB2YXIgcj1wW2kqNF0sIGdnPXBbaSo0KzFdLCBiPXBbaSo0KzJdOyB2YXIgbD0ociozK2dnKjQrYik+PjM7IHBbaSo0XT1sOyBwW2kqNCsxXT1sOyBwW2kqNCsyXT1sOyBoaXN0W2xdKys7IHN1bSs9bDsgfQogICAgICAgIHZhciBtZWRpYT1zdW0vTWF0aC5tYXgoMSxuKTsKICAgICAgICB2YXIgZ2FuPTE7CiAgICAgICAgaWYobWVkaWE8ODApeyBnYW49MC41ODsgfQogICAgICAgIGVsc2UgaWYobWVkaWE8MTA1KXsgZ2FuPTAuNzI7IH0KICAgICAgICBlbHNlIGlmKG1lZGlhPjE4NSl7IGdhbj0xLjI1OyB9CiAgICAgICAgdmFyIGFjYz0wLCBsbz0wLCBoaT0yNTU7CiAgICAgICAgZm9yKGs9MDtrPDI1NjtrKyspeyBhY2MrPWhpc3Rba107IGlmKGFjYz49biowLjAyKXsgbG89azsgYnJlYWs7IH0gfQogICAgICAgIGFjYz0wOwogICAgICAgIGZvcihrPTI1NTtrPj0wO2stLSl7IGFjYys9aGlzdFtrXTsgaWYoYWNjPj1uKjAuMDIpeyBoaT1rOyBicmVhazsgfSB9CiAgICAgICAgdmFyIGVzYz0oaGk+bG8pPzI1NS8oaGktbG8pOjE7CiAgICAgICAgZm9yKGk9MDtpPG47aSsrKXsgdmFyIHY9KHBbaSo0XS1sbykqZXNjOyB2PXY8MD8wOih2PjI1NT8yNTU6dik7IHY9MjU1Kk1hdGgucG93KHYvMjU1LGdhbik7IHBbaSo0XT12OyBwW2kqNCsxXT12OyBwW2kqNCsyXT12OyB9CiAgICAgICAgdmFyIHRtcD1uZXcgVWludDhBcnJheShuKTsKICAgICAgICBmb3IoaT0wO2k8bjtpKyspeyB0bXBbaV09cFtpKjRdOyB9CiAgICAgICAgdmFyIGFuY2hvMj1jLndpZHRoOwogICAgICAgIGZvcih2YXIgeT0xO3k8Yy5oZWlnaHQtMTt5KyspewogICAgICAgICAgZm9yKHZhciB4PTE7eDxhbmNobzItMTt4KyspewogICAgICAgICAgICB2YXIgcT15KmFuY2hvMit4OwogICAgICAgICAgICB2YXIgYmw9KHRtcFtxXSt0bXBbcS0xXSt0bXBbcSsxXSt0bXBbcS1hbmNobzJdK3RtcFtxK2FuY2hvMl0pKjAuMjsKICAgICAgICAgICAgdmFyIHYyPXRtcFtxXSswLjQqKHRtcFtxXS1ibCk7CiAgICAgICAgICAgIHYyPXYyPDA/MDoodjI+MjU1PzI1NTp2Mik7CiAgICAgICAgICAgIHZhciB3Mz1xKjQ7IHBbdzNdPXYyOyBwW3czKzFdPXYyOyBwW3czKzJdPXYyOwogICAgICAgICAgfQogICAgICAgIH0KICAgICAgICBnLnB1dEltYWdlRGF0YShpZGQsMCwwKTsKICAgICAgICByZXMoYyk7CiAgICAgIH1jYXRjaChlKXsgcmVzKG51bGwpOyB9CiAgICB9OwogICAgaW0ub25lcnJvcj1mdW5jdGlvbigpeyByZXMobnVsbCk7IH07CiAgICBpbS5zcmM9ZGF0YVVybDsKICB9KTsKfQpmdW5jdGlvbiByZWNvcnRlU3VwZXJpb3IoY3YpewogIHRyeXsKICAgIHZhciB3PWN2LndpZHRoLCBoPU1hdGgucm91bmQoY3YuaGVpZ2h0KjAuNjIpOwogICAgaWYodzw0MHx8aDw0MCl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICAgIGMud2lkdGg9dzsgYy5oZWlnaHQ9aDsKICAgIGMuZ2V0Q29udGV4dCgnMmQnKS5kcmF3SW1hZ2UoY3YsMCwwLHcsaCwwLDAsdyxoKTsKICAgIHJldHVybiBjOwogIH1jYXRjaChlKXsgcmV0dXJuIG51bGw7IH0KfQpmdW5jdGlvbiByZWNvbm9jZXJDb24oaW1nLCBwc20pewogIHJldHVybiBhYnJpcldvcmtlck9jcigpLnRoZW4oZnVuY3Rpb24odyl7CiAgICBmdW5jdGlvbiBjb25UZXNzKCl7CiAgICAgIHJldHVybiBUZXNzZXJhY3QucmVjb2duaXplKGltZywnc3BhK2VuZycse2xvZ2dlcjpmdW5jdGlvbigpe319KS50aGVuKGZ1bmN0aW9uKHIpeyByZXR1cm4gKHImJnIuZGF0YSYmci5kYXRhLnRleHQpP3IuZGF0YS50ZXh0OicnOyB9KS5jYXRjaChmdW5jdGlvbigpeyByZXR1cm4gJyc7IH0pOwogICAgfQogICAgaWYoISh3JiZ3LnJlY29nbml6ZSkpeyByZXR1cm4gY29uVGVzcygpOyB9CiAgICB2YXIgcHJlPSh3LnNldFBhcmFtZXRlcnMmJnBzbSk/dy5zZXRQYXJhbWV0ZXJzKHt0ZXNzZWRpdF9wYWdlc2VnX21vZGU6U3RyaW5nKHBzbSl9KTpQcm9taXNlLnJlc29sdmUoKTsKICAgIHJldHVybiBwcmUudGhlbihmdW5jdGlvbigpeyByZXR1cm4gdy5yZWNvZ25pemUoaW1nKTsgfSkudGhlbihmdW5jdGlvbihyKXsKICAgICAgaWYody5zZXRQYXJhbWV0ZXJzKXsgdHJ5eyB3LnNldFBhcmFtZXRlcnMoe3Rlc3NlZGl0X3BhZ2VzZWdfbW9kZTonMyd9KS5jYXRjaChmdW5jdGlvbigpe30pOyB9Y2F0Y2goZTIpe30gfQogICAgICByZXR1cm4gKHImJnIuZGF0YSYmci5kYXRhLnRleHQpP3IuZGF0YS50ZXh0OicnOwogICAgfSkuY2F0Y2goZnVuY3Rpb24oKXsgcmV0dXJuIGNvblRlc3MoKTsgfSk7CiAgfSkuY2F0Y2goZnVuY3Rpb24oKXsgcmV0dXJuICcnOyB9KTsKfQpmdW5jdGlvbiBvY3JNdWx0aShkYXRhVXJsLCBlc0J1ZW5vKXsKICBpZih0eXBlb2YgVGVzc2VyYWN0PT09J3VuZGVmaW5lZCcgfHwgIVRlc3NlcmFjdC5yZWNvZ25pemUpewogICAgcmV0dXJuIFByb21pc2UucmVzb2x2ZShbXSk7CiAgfQogIHJldHVybiBtZWpvcmFySW1hZ2VuKGRhdGFVcmwpLnRoZW4oZnVuY3Rpb24oY3YpewogICAgdmFyIHZhcnM9W107CiAgICBpZihjdil7CiAgICAgIHZhcnMucHVzaCh7aW1nOmN2LCBwc206JzMnfSk7CiAgICAgIHZhciByYz1yZWNvcnRlU3VwZXJpb3IoY3YpOwogICAgICBpZihyYyl7IHZhcnMucHVzaCh7aW1nOnJjLCBwc206JzYnfSk7IH0KICAgICAgLyogaGVyZWRhZG8gdjE0OiBwYXNlIGRpc3BlcnNvIChQU00gMTEpIHBhcmEgbG9zIGNhbXBvcyBzdWVsdG9zIGRlbAogICAgICAgICBkb2N1bWVudG8gKE5PTUJSRVMgLyBBUEVMTElET1MgdmFuIGVuIGxpbmVhcyBzZXBhcmFkYXMgeSBlbCBwYXNlCiAgICAgICAgIG5vcm1hbCBhIHZlY2VzIGxvcyBzYWx0YSkuIGVzQnVlbm8gY29ydGEgYXBlbmFzIGFjaWVydGEuICovCiAgICAgIHZhcnMucHVzaCh7aW1nOmN2LCBwc206JzExJ30pOwogICAgfQogICAgdmFycy5wdXNoKHtpbWc6ZGF0YVVybCwgcHNtOiczJ30pOwogICAgdmFyIGk9MCwgdGV4dG9zPVtdOwogICAgZnVuY3Rpb24gcGFzbygpewogICAgICBpZihpPj12YXJzLmxlbmd0aCl7IHJldHVybiBQcm9taXNlLnJlc29sdmUodGV4dG9zKTsgfQogICAgICB2YXIgcj12YXJzW2krK107CiAgICAgIHJldHVybiByZWNvbm9jZXJDb24oci5pbWcsIHIucHNtKS50aGVuKGZ1bmN0aW9uKHQpewogICAgICAgIGlmKHQpeyB0ZXh0b3MucHVzaCh0KTsgfQogICAgICAgIGlmKHQmJmVzQnVlbm8mJmVzQnVlbm8odCkpeyByZXR1cm4gdGV4dG9zOyB9CiAgICAgICAgcmV0dXJuIHBhc28oKTsKICAgICAgfSkuY2F0Y2goZnVuY3Rpb24oKXsgcmV0dXJuIHBhc28oKTsgfSk7CiAgICB9CiAgICByZXR1cm4gcGFzbygpOwogIH0pOwp9CmZ1bmN0aW9uIGVsZWdpclRleHRvKHRleHRvcywgZXNjcml0byl7CiAgdmFyIG1lam9yPScnLCBtaj0tMSwgaTsKICBmb3IoaT0wO2k8dGV4dG9zLmxlbmd0aDtpKyspewogICAgdmFyIHQ9dGV4dG9zW2ldfHwnJywgcD0wOwogICAgaWYoZXNjcml0byl7CiAgICAgIHZhciBuYz1ub21icmVDb2luY2lkZShlc2NyaXRvLHQsZmFsc2UpOwogICAgICBwPShuYy5vaz8xMDAwOjApKyhuYy5wdW50fHwwKSoxMDA7CiAgICB9CiAgICBwKz1NYXRoLm1pbig1MCwodC5yZXBsYWNlKC9bXkEtWjAtOV0vZ2ksJycpLmxlbmd0aCkvMzApOwogICAgaWYocD5tail7IG1qPXA7IG1lam9yPXQ7IH0KICB9CiAgcmV0dXJuIG1lam9yOwp9CmZ1bmN0aW9uIGhhY2VyT2NyKGRhdGFVcmwpewogIGlmKGNhY2hlT2NyW2RhdGFVcmxdKXsgcmV0dXJuIFByb21pc2UucmVzb2x2ZShjYWNoZU9jcltkYXRhVXJsXSk7IH0KICBpZih0eXBlb2YgVGVzc2VyYWN0PT09J3VuZGVmaW5lZCcgfHwgIVRlc3NlcmFjdC5yZWNvZ25pemUpewogICAgcmV0dXJuIFByb21pc2UucmVqZWN0KG5ldyBFcnJvcignT0NSIG5vIGRpc3BvbmlibGUsIHJldmlzYSB0dSBpbnRlcm5ldCcpKTsKICB9CiAgcmV0dXJuIG9jck11bHRpKGRhdGFVcmwsIGZ1bmN0aW9uKHQpeyByZXR1cm4gKHR8fCcnKS5yZXBsYWNlKC9bXkEtWjAtOV0vZ2ksJycpLmxlbmd0aD49MzQ7IH0pLnRoZW4oZnVuY3Rpb24odGV4dG9zKXsKICAgIHZhciB0PWVsZWdpclRleHRvKHRleHRvcywgbnVsbCk7CiAgICBjYWNoZU9jcltkYXRhVXJsXT10fHwnJzsKICAgIHJldHVybiB0fHwnJzsKICB9KTsKfQpmdW5jdGlvbiBvY3JGcmVudGUoZGF0YVVybCl7CiAgaWYoY2FjaGVPY3JbZGF0YVVybF0peyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKGNhY2hlT2NyW2RhdGFVcmxdKTsgfQogIHJldHVybiBvY3JNdWx0aShkYXRhVXJsLCBmdW5jdGlvbih0KXsgcmV0dXJuIG5vbWJyZUNvaW5jaWRlKEVTVC5lc2NyaXRvLCB0fHwnJywgZmFsc2UpLm9rOyB9KS50aGVuKGZ1bmN0aW9uKHRleHRvcyl7CiAgICB2YXIgdD1lbGVnaXJUZXh0byh0ZXh0b3MsIEVTVC5lc2NyaXRvKTsKICAgIGlmKHQpeyBjYWNoZU9jcltkYXRhVXJsXT10OyB9CiAgICByZXR1cm4gdHx8Jyc7CiAgfSk7Cn0KCi8qID09PT09PT09PT09PT09PT09IGJpb21ldHJpYSBmYWNpYWwgPT09PT09PT09PT09PT09PT0gKi8KdmFyIGZhY2VQPW51bGw7CmZ1bmN0aW9uIGNhcmdhckZhY2VBcGkoKXsKICBpZihmYWNlUCl7IHJldHVybiBmYWNlUDsgfQogIGZhY2VQPW5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyxyZWopewogICAgZnVuY3Rpb24gbGlzdG8oKXsgcmV0dXJuIFcuZmFjZWFwaSAmJiBXLmZhY2VhcGkubmV0cyAmJiBXLmZhY2VhcGkubmV0cy50aW55RmFjZURldGVjdG9yICYmIFcuZmFjZWFwaS5uZXRzLmZhY2VSZWNvZ25pdGlvbk5ldDsgfQogICAgZnVuY3Rpb24gbW9kZWxvcyhiYXNlKXsKICAgICAgcmV0dXJuIFByb21pc2UuYWxsKFsKICAgICAgICBXLmZhY2VhcGkubmV0cy50aW55RmFjZURldGVjdG9yLmxvYWRGcm9tVXJpKGJhc2UpLAogICAgICAgIFcuZmFjZWFwaS5uZXRzLmZhY2VMYW5kbWFyazY4TmV0LmxvYWRGcm9tVXJpKGJhc2UpLAogICAgICAgIFcuZmFjZWFwaS5uZXRzLmZhY2VSZWNvZ25pdGlvbk5ldC5sb2FkRnJvbVVyaShiYXNlKQogICAgICBdKTsKICAgIH0KICAgIGZ1bmN0aW9uIGluaWNpYXIoKXsKICAgICAgdmFyIGJhc2U9J2h0dHBzOi8vY2RuLmpzZGVsaXZyLm5ldC9naC9qdXN0YWR1ZGV3aG9oYWNrcy9mYWNlLWFwaS5qc0AwLjIyLjIvd2VpZ2h0cyc7CiAgICAgIG1vZGVsb3MoYmFzZSkudGhlbihmdW5jdGlvbigpeyByZXMoKTsgfSwgZnVuY3Rpb24oKXsgbW9kZWxvcygnaHR0cHM6Ly9qdXN0YWR1ZGV3aG9oYWNrcy5naXRodWIuaW8vZmFjZS1hcGkuanMvbW9kZWxzJykudGhlbihmdW5jdGlvbigpeyByZXMoKTsgfSwgcmVqKTsgfSk7CiAgICB9CiAgICBpZihsaXN0bygpKXsgaW5pY2lhcigpOyByZXR1cm47IH0KICAgIHZhciBzPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ3NjcmlwdCcpOwogICAgcy5zcmM9J2h0dHBzOi8vY2RuLmpzZGVsaXZyLm5ldC9ucG0vZmFjZS1hcGkuanNAMC4yMi4yL2Rpc3QvZmFjZS1hcGkubWluLmpzJzsKICAgIHMub25sb2FkPWZ1bmN0aW9uKCl7IGlmKGxpc3RvKCkpeyBpbmljaWFyKCk7IH0gZWxzZSB7IHJlaihuZXcgRXJyb3IoJ2ZhY2VhcGkgbm8gcXVlZG8gbGlzdG8nKSk7IH0gfTsKICAgIHMub25lcnJvcj1mdW5jdGlvbigpeyByZWoobmV3IEVycm9yKCdubyBzZSBwdWRvIGNhcmdhciBlbCB2ZXJpZmljYWRvciBmYWNpYWwnKSk7IH07CiAgICBkb2N1bWVudC5oZWFkLmFwcGVuZENoaWxkKHMpOwogIH0pOwogIHJldHVybiBmYWNlUDsKfQpmdW5jdGlvbiBjb25UaW1lb3V0KHAsIG1zKXsKICByZXR1cm4gUHJvbWlzZS5yYWNlKFtwLCBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpeyBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7IHJlcyhudWxsKTsgfSwgbXMpOyB9KV0pOwp9CmZ1bmN0aW9uIGRldGVjdGFyQ2FyYUVuKGRhdGFVcmwsIGludGVudG8pewogIHJldHVybiBjYXJnYXJGYWNlQXBpKCkudGhlbihmdW5jdGlvbigpewogICAgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7CiAgICAgIHZhciBpbT1uZXcgSW1hZ2UoKTsKICAgICAgaW0ub25sb2FkPWZ1bmN0aW9uKCl7CiAgICAgICAgdHJ5ewogICAgICAgICAgdmFyIHRhbT0oaW50ZW50bz09PTIpPzUxMjozMjA7CiAgICAgICAgICB2YXIgb3B0PW5ldyBXLmZhY2VhcGkuVGlueUZhY2VEZXRlY3Rvck9wdGlvbnMoe2lucHV0U2l6ZTp0YW0sIHNjb3JlVGhyZXNob2xkOihpbnRlbnRvPT09Mik/MC4zOjAuNH0pOwogICAgICAgICAgVy5mYWNlYXBpLmRldGVjdFNpbmdsZUZhY2UoaW0sb3B0KS53aXRoRmFjZUxhbmRtYXJrcygpLndpdGhGYWNlRGVzY3JpcHRvcigpLnRoZW4oZnVuY3Rpb24ocil7CiAgICAgICAgICAgIGlmKHImJnIuZGV0ZWN0aW9uKXsgcmVzKHIpOyByZXR1cm47IH0KICAgICAgICAgICAgaWYoaW50ZW50bz09PTIpeyByZXMobnVsbCk7IHJldHVybjsgfQogICAgICAgICAgICByZXMoZGV0ZWN0YXJDYXJhRW4oZGF0YVVybCwoaW50ZW50bz09PTEpPzI6MSkpOwogICAgICAgICAgfSkuY2F0Y2goZnVuY3Rpb24oKXsKICAgICAgICAgICAgaWYoaW50ZW50bz09PTIpeyByZXMobnVsbCk7IHJldHVybjsgfQogICAgICAgICAgICByZXMoZGV0ZWN0YXJDYXJhRW4oZGF0YVVybCwoaW50ZW50bz09PTEpPzI6MSkpOwogICAgICAgICAgfSk7CiAgICAgICAgfWNhdGNoKGUpeyByZXMobnVsbCk7IH0KICAgICAgfTsKICAgICAgaW0ub25lcnJvcj1mdW5jdGlvbigpeyByZXMobnVsbCk7IH07CiAgICAgIGltLnNyYz1kYXRhVXJsOwogICAgfSk7CiAgfSkuY2F0Y2goZnVuY3Rpb24oKXsgcmV0dXJuIG51bGw7IH0pOwp9CmZ1bmN0aW9uIHJlY29ydGVDYXJhKGRhdGFVcmwpewogIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpewogICAgdmFyIGltPW5ldyBJbWFnZSgpOwogICAgaW0ub25sb2FkPWZ1bmN0aW9uKCl7CiAgICAgIHRyeXsKICAgICAgICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICAgICAgICBjLndpZHRoPU1hdGgubWF4KDQwLE1hdGgucm91bmQoaW0ud2lkdGgqMC42MikpOwogICAgICAgIGMuaGVpZ2h0PU1hdGgubWF4KDQwLE1hdGgucm91bmQoaW0uaGVpZ2h0KjAuNjYpKTsKICAgICAgICBjLmdldENvbnRleHQoJzJkJykuZHJhd0ltYWdlKGltLDAsMCxpbS53aWR0aCxNYXRoLnJvdW5kKGltLmhlaWdodCowLjkpLDAsMCxjLndpZHRoLGMuaGVpZ2h0KTsKICAgICAgICByZXMoYy50b0RhdGFVUkwoJ2ltYWdlL2pwZWcnLDAuOSkpOwogICAgICB9Y2F0Y2goZSl7IHJlcyhudWxsKTsgfQogICAgfTsKICAgIGltLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVzKG51bGwpOyB9OwogICAgaW0uc3JjPWRhdGFVcmw7CiAgfSk7Cn0KZnVuY3Rpb24gZGV0ZWN0YXJDYXJhRG9jKGRhdGFVcmwpewogIGlmKCFkYXRhVXJsKXsgcmV0dXJuIFByb21pc2UucmVzb2x2ZShudWxsKTsgfQogIHJldHVybiBkZXRlY3RhckNhcmFFbihkYXRhVXJsKS50aGVuKGZ1bmN0aW9uKHIpewogICAgaWYociYmci5kZXRlY3Rpb24peyByZXR1cm4gcjsgfQogICAgcmV0dXJuIHJlY29ydGVDYXJhKGRhdGFVcmwpLnRoZW4oZnVuY3Rpb24ocmVjKXsKICAgICAgaWYoIXJlYyl7IHJldHVybiBudWxsOyB9CiAgICAgIHJldHVybiBkZXRlY3RhckNhcmFFbihyZWMsMSk7CiAgICB9KTsKICB9KTsKfQpmdW5jdGlvbiBkaXN0RihhLGIpewogIHZhciBzPTAsaTsKICBmb3IoaT0wO2k8YS5sZW5ndGg7aSsrKXsgdmFyIGQ9YVtpXS1iW2ldOyBzKz1kKmQ7IH0KICByZXR1cm4gTWF0aC5zcXJ0KHMpOwp9CgovKiA9PT09PT09PT09PT09PT09PSBndWFyZGlhbiBkZSBvcmRlbiAxLTItMy00LTUgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gcGVybWl0aWRvSGFzdGEoKXsKICB2YXIgcD0xOwogIGlmKEVTVC5ub21icmVPayl7IHA9MjsgfQogIGlmKEVTVC5ub21icmVPayAmJiBFU1QuZnJlbnRlT2speyBwPTM7IH0KICBpZihFU1Qubm9tYnJlT2sgJiYgRVNULmZyZW50ZU9rICYmIChFU1QucmV2ZXJzb09rIHx8ICFFU1QubmVjZXNpdGFSZXZlcnNvKSl7IHA9NDsgfQogIGlmKEVTVC5zZWxmaWVPayAmJiBwPj00KXsgcD01OyB9CiAgcmV0dXJuIHA7Cn0KdmFyIE1PVkxJQlJFPWZhbHNlOwovKiB2MTg6IGVsIHJlZ3Jlc28gdm9sdW50YXJpbyAoVm9sdmVyL0F0cmFzL1JlZ3Jlc2FyL0NhbmNlbGFyKSBkZXNhY3RpdmEgbGEgZ3VhcmRpYQogICBhbnRpLXBhdGFkYSBIQVNUQSBRVUUgZWwgdXN1YXJpbyBhdmFuemEgZGUgbnVldm8gcG9yIHN1IGN1ZW50YS4gQW50ZXMgbGEgcGF1c2EKICAgZHVyYWJhIHNvbG8gMyBzZWd1bmRvczogYWwgc2VndW5kbyAzLTUgZWwgYmFycmlkbyBhdXRvbWF0aWNvIGRlIG1lbnNhamVzIChxdWUKICAgbXV0YSBlbCBET00pIGRpc3BhcmFiYSB2ZXJpZmljYXIoKSB5IGxhIGd1YXJkaWEgcGF0ZWFiYSBkZWwgcGFzbyAxIGFsIHBhc28gNQogICBqdXN0byBjdWFuZG8gZWwgdXN1YXJpbyBxdWVyaWEgZXNjcmliaXIgc3Ugbm9tYnJlIHBhcmEgcmVnaXN0cmFyc2UgZGUgbnVldm8uICovCmZ1bmN0aW9uIHZvbHZlclRvY2FkbygpewogIHRyeXsKICAgIGlmKFcuX196eUxpYnJlU2VzaW9uMTgpeyByZXR1cm4gdHJ1ZTsgfQogICAgcmV0dXJuICEhKFcuX196eVZvbHZlclRvY2FkbyYmKChEYXRlLm5vdygpLVcuX196eVZvbHZlclRvY2Fkbyk8MzAwMCkpOwogIH1jYXRjaChlKXsgcmV0dXJuIGZhbHNlOyB9Cn0KLyogdjE4OiBtaWVudHJhcyBlbCB1c3VhcmlvIEVTQ1JJQkUgZW4gZWwgY2FtcG8gZGVsIG5vbWJyZSwgbGEgZ3VhcmRpYSBudW5jYSBtdWV2ZQogICBsYSBwYW50YWxsYSAoY2FwYSBleHRyYSBkZSBzZWd1cmlkYWQgcGFyYSBlbCBjYXNvIHJlcG9ydGFkbykuICovCmZ1bmN0aW9uIGVzY3JpYmllbmRvTm9tYnJlKCl7CiAgdHJ5eyB2YXIgYT1kb2N1bWVudC5hY3RpdmVFbGVtZW50OyByZXR1cm4gISEoYSYmYS5pZD09PSdub21icmUnKTsgfWNhdGNoKGUpeyByZXR1cm4gZmFsc2U7IH0KfQpmdW5jdGlvbiBtb3N0cmFyUGFzbyhuKXsKICAvKiB2MTY6IGd1YXJkaWEgYW50aS1wYXRhZGEuIFNpIGNvZGlnbyB2aWVqbyAodmFsaWRhY2lvbmVzIGxlZ2FkYXMgbwogICAgIHVuIHJlLXJlbmRlciBkZWwgc2Vydmlkb3IpIHRlIHRpcmEgaGFjaWEgYXRyYXMgZGVzZGUgZWwgcGFzbyA0LTUKICAgICBzaW4gcXVlIGhheWFzIHRvY2FkbyBWb2x2ZXIsIGVsIHNhbHRvIHNlIENBTkNFTEE6IHNpZ3VlcyBlbiB0dQogICAgIHBhc28gY29uIHRvZG8gaW50YWN0by4gTG9zIHJlZ3Jlc29zIHF1ZSBUVSBwaWRlcyAoYm90b24gUmVwZXRpcgogICAgIGZvdG8sIGJvdG9uIElyIGFsIHBhc28gMSwgVm9sdmVyKSBtYXJjYW4gTU9WTElCUkUgbyBlbCB0b3F1ZSB5CiAgICAgcGFzYW4gc2luIHByb2JsZW1hLiAqLwogIHRyeXsKICAgIHZhciBwbT1FU1QucGFzb01heHx8MTsKICAgIGlmKHBtPj00ICYmIG4+PTEgJiYgbjxwbSAmJiAhTU9WTElCUkUgJiYgIXZvbHZlclRvY2FkbygpICYmIHBlcm1pdGlkb0hhc3RhKCk+PXBtICYmICFlc2NyaWJpZW5kb05vbWJyZSgpKXsKICAgICAgbXNnKCd6eUd1YXJkaWEnLCdObyB0ZSByZWdyZXNhbW9zOiB0dSByZWdpc3RybyBzaWd1ZSBjb21wbGV0byBlbiBlbCBwYXNvICcrcG0rJy4gUGFyYSBjb3JyZWdpciBhbGdvIHVzYSBWb2x2ZXIuJywnI2E2MCcpOwogICAgICBuPXBtOwogICAgfQogIH1jYXRjaChlKXt9CiAgLyogdjE4OiBhbCBhdmFuemFyIGhhY2lhIGFkZWxhbnRlIHBvciBkZWNpc2lvbiBwcm9waWEsIGxhIGd1YXJkaWEgc2UgcmUtYXJtOiBlbAogICAgIHJlZ3Jlc28gdm9sdW50YXJpbyBzb2xvIHBlcm1hbmVjZSBsaWJyZSBtaWVudHJhcyBlbCB1c3VhcmlvIG5vIGF2YW5jZS4gKi8KICB0cnl7IGlmKG4+KEVTVC5wYXNvfHwxKSl7IFcuX196eUxpYnJlU2VzaW9uMTg9ZmFsc2U7IH0gfWNhdGNoKGVGMTgpe30KICBpZihuPihFU1QucGFzb01heHx8MSkpeyBFU1QucGFzb01heD1uOyB9CiAgdmFyIGksZWwsIHJiPSQoJ3p5QnRuUmVwRm90bycpOwogIGlmKHJiKXsgcmIuc3R5bGUuZGlzcGxheT0nbm9uZSc7IH0KICBmb3IoaT0xO2k8PTU7aSsrKXsKICAgIGVsPSQoJ3BzJytpKTsKICAgIGlmKGVsKXsKICAgICAgZWwuY2xhc3NOYW1lPSdwYXNvJysoaT09PW4/JyBhY3QnOicnKTsKICAgICAgZWwuc3R5bGUuZGlzcGxheT0nJzsKICAgIH0KICB9CiAgdmFyIHByPSQoJ3Byb2cnKTsKICBpZihwcil7IHByLnRleHRDb250ZW50PSdQQVNPICcrbisnIERFIDUnOyB9CiAgaWYoRVNULnBhc28+PTIgJiYgRVNULnBhc288PTQgJiYgRVNULnBhc28hPT1uKXsgdHJ5eyBwYXJhckNhbShFU1QucGFzbyk7IH1jYXRjaChlKXt9IH0KICBFU1QucGFzbz1uOwogIHRyeXsgcmVzcGFsZGEoKTsgfWNhdGNoKGUpe30KICBpZihuPT09NSl7CiAgICBkZXNjdWJyZUNsYXZlcyh0cnVlKTsKICAgIHZhciBhPUNMVi5hLCBiPUNMVi5iOwogICAgaWYoYSl7IGEuZGlzYWJsZWQ9ZmFsc2U7IH0KICAgIGlmKGIpeyBiLmRpc2FibGVkPWZhbHNlOyB9CiAgICB0cnl7IGlmKHJlc3RhdXJhckNsYXZlU2VzaW9uKCkpeyBsb2coJ3YxNzogY2xhdmUgcmVwdWVzdGEgZGVzZGUgbGEgc2VzaW9uJyk7IH0gfWNhdGNoKGVSYyl7fQogICAgdHJ5eyB2YWxpZGFyQ2xhdmVzKCk7IH1jYXRjaChlVmMpe30KICAgIHRyeXsgYmFycmVNZW5zYWplcygpOyB9Y2F0Y2goZSl7fQogICAgdHJ5eyBsaW1waWFMZWdhZG8oKTsgfWNhdGNoKGUpe30KICAgIHRyeXsgcGludGFEaWFnKCk7IH1jYXRjaChlKXt9CiAgICB2YXIgcmY9RVNULmZyZW50ZU9rPydGcmVudGUgT0snOidGQUxUQSBGUkVOVEUnOwogICAgdmFyIHJyPSghRVNULm5lY2VzaXRhUmV2ZXJzb3x8RVNULnJldmVyc29Payk/J1JldmVyc28gT0snOidGQUxUQSBSRVZFUlNPJzsKICAgIHZhciBycz1FU1Quc2VsZmllT2s/J1NlbGZpZSB2ZXJpZmljYWRhJzonU0VMRklFIFNJTiBWRVJJRklDQVInOwogICAgdmFyIHRvZG89KEVTVC5mcmVudGVPayYmRVNULnNlbGZpZU9rJiYoIUVTVC5uZWNlc2l0YVJldmVyc298fEVTVC5yZXZlcnNvT2spKTsKICAgIG1zZygnenlSZXN1bWVuNScsJ1ZlcmlmaWNhY2lvbiBmaW5hbDogJytyZisnIHwgJytycisnIHwgJytycysnLiBFc2NyaWJlIHR1IGNsYXZlIDIgdmVjZXMgeSBjcmVhIHR1IFpJRC4nLHRvZG8/JyMwODAnOicjYzAwJyk7CiAgfQogIHRyeXsgdmFyIGFjdD0kKCdwcycrbik7IGlmKGFjdCYmYWN0LnNjcm9sbEludG9WaWV3KXsgYWN0LnNjcm9sbEludG9WaWV3KHtiZWhhdmlvcjonc21vb3RoJyxibG9jazonc3RhcnQnfSk7IH0gfWNhdGNoKGUpe30KfQpmdW5jdGlvbiBhdmFuemFyKG4peyBtb3N0cmFyUGFzbyhuKTsgfQpmdW5jdGlvbiB2ZXJpZmljYXIoKXsKICB0cnl7CiAgICB2YXIgYWN0PWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoJy5wYXNvLmFjdCcpOwogICAgdmFyIHJuPWFjdCYmYWN0LmlkP3BhcnNlSW50KFN0cmluZyhhY3QuaWQpLnJlcGxhY2UoJ3BzJywnJyksMTApOjA7CiAgICBpZihybj49MSYmcm48PTUmJnJuIT09RVNULnBhc28pewogICAgICB2YXIgcGFzb0FudGVzMTg9RVNULnBhc287CiAgICAgIC8qIHYxODogcmVncmVzbyB2b2x1bnRhcmlvIGVuIGN1cnNvIChlbCB1c3VhcmlvIHRvY28gVm9sdmVyL0F0cmFzIHkgZWxpZ2lvIHN1CiAgICAgICAgIHBvc2ljaW9uLCBwLmVqLiBlbCBwYXNvIDEgcGFyYSByZWVzY3JpYmlyIHN1IG5vbWJyZSk6IHNpIGVsIGNvZGlnbyB2aWVqbyBsbwogICAgICAgICBFTVBVSkEgaGFjaWEgYWRlbGFudGUgcG9yIHN1IGN1ZW50YSAocmUtYWN0aXZhIGVsIHBhc28gNSBqdXN0byBhbCBlc2NyaWJpcgogICAgICAgICBlbCBub21icmUpLCBlbCBlbXB1am9uIHNlIENBTkNFTEEgeSBzZSBsZSBkZWphIGRvbmRlIHBpZGlvLiBVbiBjbGljayBzdXlvCiAgICAgICAgIGVuIHVuIGJvdG9uIGRlIGFjY2lvbiAoQ29udGludWFyLCBldGMuKSBsaWJlcmEgbGEgcGF1c2EgeSBkZWphIGF2YW56YXIuICovCiAgICAgIGlmKCFNT1ZMSUJSRSAmJiB2b2x2ZXJUb2NhZG8oKSAmJiBybj5wYXNvQW50ZXMxOCl7CiAgICAgICAgdHJ5ewogICAgICAgICAgbW9zdHJhclBhc28ocGFzb0FudGVzMTgpOwogICAgICAgICAgbXNnKCd6eUd1YXJkaWEnLCdUZSBkZWphbW9zIGVuIGVsIHBhc28gJytwYXNvQW50ZXMxOCsnIGNvbW8gcGVkaXN0ZS4gUGFyYSBhdmFuemFyIGRlIHZlcmRhZCwgdG9jYSBDb250aW51YXIgbyBlbCBib3RvbiBkZSB0dSBwYXNvLicsJyNhNjAnKTsKICAgICAgICB9Y2F0Y2goZUMxOCl7fQogICAgICAgIHJldHVybjsKICAgICAgfQogICAgICBFU1QucGFzbz1ybjsKICAgICAgdHJ5eyBpZihybj5wYXNvQW50ZXMxOCl7IFcuX196eUxpYnJlU2VzaW9uMTg9ZmFsc2U7IH0gfWNhdGNoKGVMMTgpe30KICAgICAgdmFyIHBtdj1FU1QucGFzb01heHx8MTsKICAgICAgaWYocG12Pj00ICYmIHJuPHBtdiAmJiAhTU9WTElCUkUgJiYgIXZvbHZlclRvY2FkbygpICYmIHBlcm1pdGlkb0hhc3RhKCk+PXBtdiAmJiAhZXNjcmliaWVuZG9Ob21icmUoKSl7CiAgICAgICAgbXNnKCd6eUd1YXJkaWEnLCdObyB0ZSByZWdyZXNhbW9zOiB0dSByZWdpc3RybyBzaWd1ZSBjb21wbGV0byBlbiBlbCBwYXNvICcrcG12KycuJywnI2E2MCcpOwogICAgICAgIG1vc3RyYXJQYXNvKHBtdik7CiAgICAgICAgcmV0dXJuOwogICAgICB9CiAgICB9CiAgfWNhdGNoKGUpe30KICB0cnl7IHZhbGlkYXJQYXNvMSh0cnVlKTsgfWNhdGNoKGUpe30KICB2YXIgcGVyPXBlcm1pdGlkb0hhc3RhKCk7CiAgaWYoRVNULnBhc28+cGVyKXsKICAgIGlmKHBlcj09PTEpeyBtc2coJ3p5R3VhcmRpYScsJ1BhcmEgc2VndWlyLCBlc2NyaWJlIHR1IG5vbWJyZSB5IGVsaWdlIGVsIHRpcG8gZGUgZG9jdW1lbnRvIGVuIGVsIHBhc28gMS4nLCcjYTYwJyk7IH0KICAgIGVsc2V7IG1zZygnenlHdWFyZGlhJywnVGUgcmVncmVzbyBhbCBwYXNvICcrcGVyKycgcGFyYSBzZWd1aXIgZW4gb3JkZW4uJywnI2E2MCcpOyB9CiAgICBtb3N0cmFyUGFzbyhwZXIpOwogIH0KICB2YXIgc2VsPSQoJ3RpcG9Eb2MnKTsKICBpZihzZWwgJiYgc2VsLnZhbHVlICYmIC9wYXNhcG9ydGV8cGFzc3BvcnQvaS50ZXN0KChzZWwub3B0aW9ucyYmc2VsLm9wdGlvbnNbc2VsLnNlbGVjdGVkSW5kZXhdJiZzZWwub3B0aW9uc1tzZWwuc2VsZWN0ZWRJbmRleF0udGV4dCl8fCcnKSl7CiAgICB2YXIgcHMzPSQoJ3BzMycpLCBucj0kKCdub3RhUmV2Jyk7CiAgICBpZihwczMpeyBwczMuc3R5bGUuZGlzcGxheT0nbm9uZSc7IH0KICAgIGlmKG5yKXsgbnIuc3R5bGUuZGlzcGxheT0nbm9uZSc7IH0KICB9Cn0KdmFyIHZ0aW1lcj1udWxsOwpmdW5jdGlvbiBwcm9ncmFtYXJWZXJpZmljYXIoKXsKICBpZih2dGltZXIpeyByZXR1cm47IH0KICB2dGltZXI9c2V0VGltZW91dChmdW5jdGlvbigpeyB2dGltZXI9bnVsbDsgdHJ5eyB2ZXJpZmljYXIoKTsgfWNhdGNoKGUpe30gfSwxMjApOwp9CnRyeXsKICBuZXcgTXV0YXRpb25PYnNlcnZlcihwcm9ncmFtYXJWZXJpZmljYXIpLm9ic2VydmUoZG9jdW1lbnQuYm9keSx7Y2hpbGRMaXN0OnRydWUsc3VidHJlZTp0cnVlLGF0dHJpYnV0ZXM6dHJ1ZSxhdHRyaWJ1dGVGaWx0ZXI6WydzdHlsZScsJ2NsYXNzJywnaGlkZGVuJywnZGlzYWJsZWQnXX0pOwp9Y2F0Y2goZSl7fQoKLyogPT09PT09PT09PT09PT09PT0gcGFzbyAxOiBzb2xvIGZvcm1hdG8gZGVsIG5vbWJyZSAodmFsaWRhIFNPTE8gYWwgY29udGludWFyLCBudW5jYSBtaWVudHJhcyBlc2NyaWJlcykgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gdmFsaWRhclBhc28xKHNpbGVuY2lvc28pewogIHZhciBpbnA9JCgnbm9tYnJlJyksIHNlbD0kKCd0aXBvRG9jJyk7CiAgdmFyIHY9aW5wPyhpbnAudmFsdWV8fCcnKS50cmltKCk6Jyc7CiAgdmFyIGxldHJhcz0vXltBLVphLXpcdTAwQzFcdTAwQzlcdTAwQ0RcdTAwRDNcdTAwREFcdTAwRENcdTAwRDFcdTAwRTFcdTAwRTlcdTAwRURcdTAwRjNcdTAwRkFcdTAwRkNcdTAwRjFdKyggW0EtWmEtelx1MDBDMVx1MDBDOVx1MDBDRFx1MDBEM1x1MDBEQVx1MDBEQ1x1MDBEMVx1MDBFMVx1MDBFOVx1MDBFRFx1MDBGM1x1MDBGQVx1MDBGQ1x1MDBGMV0rKSokLy50ZXN0KHYpOwogIHZhciBucD12P3Yuc3BsaXQoL1xzKy8pLmxlbmd0aDowOwogIHZhciBvaz0odi5sZW5ndGg+PTUgJiYgbGV0cmFzICYmIG5wPj0yKTsKICB2YXIgdD1jbGFzaWZpY2FyVGlwbygpOwogIEVTVC50aXBvPXQuazsKICBFU1QubmVjZXNpdGFSZXZlcnNvPXQucmV2ZXJzbzsKICB2YXIgdGlwb09rPSEhKHNlbCAmJiBTdHJpbmcoc2VsLnZhbHVlfHwnJykubGVuZ3RoPjApOwogIEVTVC5ub21icmVPaz1vazsKICBFU1QuZXNjcml0bz1ub3JtKHYpOwogIGlmKHNpbGVuY2lvc28peyByZXR1cm4gb2smJnRpcG9PazsgfQogIGlmKGlucCl7IGlucC5zdHlsZS5ib3JkZXJDb2xvcj1vaz8nJzonI2MwMCc7IH0KICB2YXIgbW5vPScnOwogIGlmKCFvayl7IG1ubz12PydFc2NyaWJlIHR1IG5vbWJyZSB5IHR1IGFwZWxsaWRvIChzb2xvIGxldHJhcyB5IGVzcGFjaW9zOyBzaXJ2ZSBjb24gMSBvIDIgbm9tYnJlcyB5IDEgbyAyIGFwZWxsaWRvcykuJzonRXNjcmliZSB0dSBub21icmUgeSB0dSBhcGVsbGlkbyBwYXJhIGNvbnRpbnVhci4nOyB9CiAgbXNnKCd6eUVyck5vbWJyZScsbW5vLG1ubz8nI2MwMCc6JycpOwogIHZhciBtdGk9dGlwb09rPycnOidFbGlnZSB0dSB0aXBvIGRlIGRvY3VtZW50byBlbiBsYSBsaXN0YS4nOwogIG1zZygnenlFcnJUaXBvJyxtdGksbXRpPycjYzAwJzonJyk7CiAgcmV0dXJuIG9rJiZ0aXBvT2s7Cn0KZnVuY3Rpb24gbGltcGlhckVycm9yZXNQYXNvMSgpewogIHZhciBlMT0kKCd6eUVyck5vbWJyZScpOyBpZihlMSAmJiBlMS50ZXh0Q29udGVudCl7IGUxLnRleHRDb250ZW50PScnOyBlMS5zdHlsZS5jb2xvcj0nJzsgfQogIHZhciBlMj0kKCd6eUVyclRpcG8nKTsgaWYoZTIgJiYgZTIudGV4dENvbnRlbnQpeyBlMi50ZXh0Q29udGVudD0nJzsgZTIuc3R5bGUuY29sb3I9Jyc7IH0KICB2YXIgaW5wPSQoJ25vbWJyZScpOyBpZihpbnAgJiYgaW5wLnN0eWxlLmJvcmRlckNvbG9yKXsgaW5wLnN0eWxlLmJvcmRlckNvbG9yPScnOyB9Cn0KZnVuY3Rpb24gcmVzZXRlYXJEb2N1bWVudG8oKXsKICBFU1QuZnJlbnRlT2s9ZmFsc2U7IEVTVC5yZXZlcnNvT2s9ZmFsc2U7IEVTVC5zZWxmaWVPaz1mYWxzZTsgRVNULmludGVudG9zPTU7IEVTVC5jYXJhRG9jPW51bGw7Cn0KCi8qID09PT09PT09PT09PT09PT09IHBhc28gMjogZnJlbnRlID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIGZhbGxvTGVjdHVyYUZyZW50ZShtKXsKICBidXN5KGZhbHNlKTsKICBtc2coJ3N0RicsbSsnIFRvY2EgQ0FQVFVSQVIgZGUgbnVldm8sIGNvbiBidWVuYSBsdXogeSBzaW4gYnJpbGxvLicsJyNjMDAnKTsKfQpmdW5jdGlvbiBhdmFuemFyVHJhc0ZyZW50ZSgpewogIGF2YW56YXIoRVNULm5lY2VzaXRhUmV2ZXJzbz8zOjQpOwogIGlmKEVTVC5uZWNlc2l0YVJldmVyc28pewogICAgc2V0VGltZW91dChmdW5jdGlvbigpeyB0cnl7IGFicmlyQ2FtKCczJywnZW52aXJvbm1lbnQnLCdzdEEnLCdiQ2FwQScpLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH1jYXRjaChlKXt9IH0sNTAwKTsKICB9Cn0KZnVuY3Rpb24gYWNlcHRhckZyZW50ZUNvbmZpcm1hZG8odGV4dG9PQ1IsIGxlY3R1cmEpewogIEVTVC5mcmVudGVPaz10cnVlOwogIEVTVC5mcmVudGVUZXh0bz0odGV4dG9PQ1J8fCcnKSsnXG5MRUNUVVJBIENPTkZJUk1BREE6ICcrbGVjdHVyYTsKICB0cnl7IHJlc3BhbGRhKCk7IH1jYXRjaChlKXt9CiAgb2N1bHRhckNvbmZpcm1hY2lvbkxlY3R1cmEoKTsKICBtc2coJ3N0RicsJ1x1MjcxMyBGcmVudGUgY29uZmlybWFkbzogJytsZWN0dXJhLCcjMDgwJyk7CiAgYXZhbnphclRyYXNGcmVudGUoKTsKfQpmdW5jdGlvbiBhYnJpckNvbmZpcm1hY2lvbkxlY3R1cmEodGV4dG9PQ1IsIGxlaWRvKXsKICB0cnl7CiAgICB2YXIgY29udD0kKCd6eUxlY0JveCcpOwogICAgaWYoIWNvbnQpewogICAgICBjb250PWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgICBjb250LmlkPSd6eUxlY0JveCc7CiAgICAgIGNvbnQuc3R5bGUuY3NzVGV4dD0nYm9yZGVyOjFweCBzb2xpZCAjN2MzYWVkO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjEwcHg7bWFyZ2luOjhweCAwO2JhY2tncm91bmQ6IzE3MTIyYjsnOwogICAgICB2YXIgcHMyPSQoJ3BzMicpOwogICAgICBpZihwczImJnBzMi5pbnNlcnRCZWZvcmUpeyBwczIuaW5zZXJ0QmVmb3JlKGNvbnQscHMyLmZpcnN0Q2hpbGQpOyB9IGVsc2UgeyBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKGNvbnQpOyB9CiAgICAgIHZhciB0MT1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgICAgdDEuc3R5bGUuY3NzVGV4dD0nZm9udC1zaXplOjEzcHg7Y29sb3I6I2U2ZTZmYTttYXJnaW4tYm90dG9tOjZweDtsaW5lLWhlaWdodDoxLjM1Oyc7CiAgICAgIHQxLnRleHRDb250ZW50PSdObyBwdWRlIGNvbmZpcm1hciBlbCBub21icmUgY29uIHNlZ3VyaWRhZC4gRXN0byBmdWUgbG8gcXVlIExFXHUwMENEIGRlbCBkb2N1bWVudG8uIENvcnJpZ2UgU09MTyBsYXMgbGV0cmFzIG1hbCBsZVx1MDBFRGRhcyB5IGNvbmZpcm1hOic7CiAgICAgIGNvbnQuYXBwZW5kQ2hpbGQodDEpOwogICAgICB2YXIgaW5wPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2lucHV0Jyk7CiAgICAgIGlucC5pZD0nenlMZWNJbic7CiAgICAgIGlucC50eXBlPSd0ZXh0JzsKICAgICAgaW5wLmF1dG9jb21wbGV0ZT0nb2ZmJzsKICAgICAgaW5wLnBsYWNlaG9sZGVyPSdOb21icmUgbGVpZG8gZGVsIGRvY3VtZW50byc7CiAgICAgIGlucC5zdHlsZS5jc3NUZXh0PSd3aWR0aDoxMDAlO2JveC1zaXppbmc6Ym9yZGVyLWJveDtwYWRkaW5nOjEwcHg7Ym9yZGVyLXJhZGl1czoxMHB4O2JvcmRlcjoxcHggc29saWQgIzQ0NDtiYWNrZ3JvdW5kOiMwZTBiMWU7Y29sb3I6I2ZmZjtmb250LXNpemU6MTVweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHg7JzsKICAgICAgY29udC5hcHBlbmRDaGlsZChpbnApOwogICAgICB2YXIgYjE9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnYnV0dG9uJyk7CiAgICAgIGIxLmlkPSd6eUxlY0J0bic7CiAgICAgIGIxLnR5cGU9J2J1dHRvbic7CiAgICAgIGIxLnRleHRDb250ZW50PSdDb25maXJtYXI6IGFzXHUwMEVEIHNlIGxlZSBlbiBtaSBkb2N1bWVudG8nOwogICAgICBiMS5zdHlsZS5jc3NUZXh0PSdkaXNwbGF5OmJsb2NrO3dpZHRoOjEwMCU7cGFkZGluZzoxMXB4O2JvcmRlcjowO2JvcmRlci1yYWRpdXM6MTBweDtiYWNrZ3JvdW5kOiM3YzNhZWQ7Y29sb3I6I2ZmZjtmb250LXNpemU6MTRweDtmb250LXdlaWdodDo2MDA7bWFyZ2luLWJvdHRvbTo2cHg7JzsKICAgICAgY29udC5hcHBlbmRDaGlsZChiMSk7CiAgICAgIHZhciBiMj1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdidXR0b24nKTsKICAgICAgYjIuaWQ9J3p5TGVjUmVwJzsKICAgICAgYjIudHlwZT0nYnV0dG9uJzsKICAgICAgYjIudGV4dENvbnRlbnQ9J01lam9yIHJlcGl0byBsYSBmb3RvJzsKICAgICAgYjIuc3R5bGUuY3NzVGV4dD0nZGlzcGxheTpibG9jazt3aWR0aDoxMDAlO3BhZGRpbmc6MTBweDtib3JkZXI6MDtib3JkZXItcmFkaXVzOjEwcHg7YmFja2dyb3VuZDojMmMyYzNjO2NvbG9yOiNkZGQ7Zm9udC1zaXplOjEzcHg7JzsKICAgICAgY29udC5hcHBlbmRDaGlsZChiMik7CiAgICAgIHZhciBtPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgICBtLmlkPSd6eUxlY01zZyc7CiAgICAgIG0uc3R5bGUuY3NzVGV4dD0nZm9udC1zaXplOjEzcHg7bWFyZ2luLXRvcDo2cHg7bGluZS1oZWlnaHQ6MS4zNTsnOwogICAgICBjb250LmFwcGVuZENoaWxkKG0pOwogICAgICBiMS5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oKXsKICAgICAgICB0cnl7CiAgICAgICAgICB2YXIgdj1ub3JtKCQoJ3p5TGVjSW4nKT8kKCd6eUxlY0luJykudmFsdWU6JycpOwogICAgICAgICAgdmFyIG9jclRva3M9dG9rZW5zTm9tYnJlRGUoY29udC5fX29jcnx8JycpOwogICAgICAgICAgaWYoIXRva2Vuc0RlKHYpLmxlbmd0aCl7IG1zZygnenlMZWNNc2cnLCdFc2NyaWJlIGxvIHF1ZSBzZSBsZWUgZW4gZWwgZG9jdW1lbnRvIChzb2xvIGxldHJhcykuJywnI2MwMCcpOyByZXR1cm47IH0KICAgICAgICAgIC8qIGhlcmVkYWRvIHYxNDogc2luIGNhbGxlam9uIHNpbiBzYWxpZGEuIEFudGVzLCBzaSBlbCBPQ1IgaGFiaWEKICAgICAgICAgICAgIHNhbHRhZG8gdW5hIHBhbGFicmEgKGVqLiBubyBsZXlvIEFMRk9OU08pLCBlbCBndWFyZGFycmFpbAogICAgICAgICAgICAgcmVjaGF6YWJhIGxhIGNvcnJlY2Npb24gYXVucXVlIGVzY3JpYmllcmFzIHR1cyBub21icmVzCiAgICAgICAgICAgICB2ZXJkYWRlcm9zIHkgZWwgcGFuZWwgdm9sdmlhIFNJRU1QUkUuIEFob3JhIHR1IG5vbWJyZSBkZWwKICAgICAgICAgICAgIHBhc28gMSBtYW5kYTogZWwgZ3VhcmRhcnJhaWwgc29sbyBleGlnZSBxdWUgbGEgY29ycmVjY2lvbgogICAgICAgICAgICAgZ3VhcmRlIGFsZ3VuYSByZWxhY2lvbiBjb24gbG8gcXVlIHNlIGxleW8gZGVsIGRvY3VtZW50by4gKi8KICAgICAgICAgIHZhciBuYz1ub21icmVDb2luY2lkZShFU1QuZXNjcml0bywgdiwgZmFsc2UpOwogICAgICAgICAgaWYoIW5jLm9rKXsKICAgICAgICAgICAgbXNnKCd6eUxlY01zZycsJ0NvbiBlc2EgbGVjdHVyYSB0dSBub21icmUgc2lndWUgc2luIGNvaW5jaWRpci4gUmV2aXNhIHR1IG5vbWJyZSBkZWwgcGFzbyAxIG8gcmVwaXRlIGxhIGZvdG8uJywnI2MwMCcpOwogICAgICAgICAgICByZXR1cm47CiAgICAgICAgICB9CiAgICAgICAgICBpZihvY3JUb2tzLmxlbmd0aD4wJiYhZWRpY2lvbkFjZXB0YWJsZSh2LCBvY3JUb2tzKSl7CiAgICAgICAgICAgIHZhciB2ZD10b2tlbnNEZSh2KSwgY29tcGFydGU9ZmFsc2UsIGkxLCBqMTsKICAgICAgICAgICAgZm9yKGkxPTA7aTE8dmQubGVuZ3RoJiYhY29tcGFydGU7aTErKyl7CiAgICAgICAgICAgICAgZm9yKGoxPTA7ajE8b2NyVG9rcy5sZW5ndGg7ajErKyl7IGlmKHBhclBhcmVjaWRvKHZkW2kxXSxvY3JUb2tzW2oxXSkpeyBjb21wYXJ0ZT10cnVlOyBicmVhazsgfSB9CiAgICAgICAgICAgIH0KICAgICAgICAgICAgaWYoIWNvbXBhcnRlKXsKICAgICAgICAgICAgICBtc2coJ3p5TGVjTXNnJywnRXNhIGxlY3R1cmEgbm8gc2UgcGFyZWNlIGEgbG8gcXVlIExFXHUwMENEIGRlbCBkb2N1bWVudG8uIENvcnJpZ2UgbGFzIGxldHJhcyBtYWwgbGVcdTAwRURkYXMgbyByZXBpdGUgbGEgZm90byBjb24gbWVqb3IgbHV6LicsJyNjMDAnKTsKICAgICAgICAgICAgICByZXR1cm47CiAgICAgICAgICAgIH0KICAgICAgICAgIH0KICAgICAgICAgIGFjZXB0YXJGcmVudGVDb25maXJtYWRvKGNvbnQuX19vY3J8fCcnLCB2KTsKICAgICAgICB9Y2F0Y2goZSl7fQogICAgICB9KTsKICAgICAgYjIuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKCl7CiAgICAgICAgdHJ5ewogICAgICAgICAgb2N1bHRhckNvbmZpcm1hY2lvbkxlY3R1cmEoKTsKICAgICAgICAgIG1zZygnc3RGJywnVG9jYSBDQVBUVVJBUiB5IHJlcGl0ZSBsYSBmb3RvOiBidWVuYSBsdXosIHNpbiBicmlsbG8sIHF1ZSBlbCBkb2N1bWVudG8gbGxlbmUgZWwgbWFyY28uJywnI2E2MCcpOwogICAgICAgIH1jYXRjaChlKXt9CiAgICAgIH0pOwogICAgfQogICAgY29udC5fX29jcj10ZXh0b09DUnx8Jyc7CiAgICB2YXIgaW5wMj0kKCd6eUxlY0luJyk7CiAgICBpZihpbnAyKXsgaW5wMi52YWx1ZT0obGVpZG98fCcnKTsgfQogICAgY29udC5zdHlsZS5kaXNwbGF5PSdibG9jayc7CiAgICBtc2coJ3p5TGVjTXNnJywnJywnJyk7CiAgICBtc2coJ3N0RicsJ1JldmlzYSBhYmFqbyBsbyBxdWUgbGVcdTAwRUQgZGVsIGRvY3VtZW50bzogcHVlZGVzIGNvcnJlZ2lyIGxhcyBsZXRyYXMgbWFsIGxlXHUwMEVEZGFzLicsJyNhNjAnKTsKICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIG9jdWx0YXJDb25maXJtYWNpb25MZWN0dXJhKCl7CiAgdmFyIGM9JCgnenlMZWNCb3gnKTsKICBpZihjKXsgYy5zdHlsZS5kaXNwbGF5PSdub25lJzsgfQp9CmZ1bmN0aW9uIHByb2Nlc2FyRnJlbnRlKGRhdGFVcmwpewogIEVTVC5mcmVudGVPaz1mYWxzZTsKICBFU1QuY2FyYURvYz1udWxsOwogIG9jdWx0YXJDb25maXJtYWNpb25MZWN0dXJhKCk7CiAgYnVzeSh0cnVlKTsKICBtc2coJ3N0RicsJ0xleWVuZG8gZWwgZG9jdW1lbnRvIChwYXNlIDEgZGUgMykuLi4nLCcnKTsKICBFU1QuZnJlbnRlSW1nPWRhdGFVcmw7CiAgc2hvd0ltZygncEYnLGRhdGFVcmwpOwogIHZhciBwQ2FyYT1jb25UaW1lb3V0KGRldGVjdGFyQ2FyYUVuKGRhdGFVcmwpLDE1MDAwKTsKICB2YXIgcFR4dD1vY3JGcmVudGUoZGF0YVVybCkuY2F0Y2goZnVuY3Rpb24oZSl7IHJldHVybiAnT0NSX0VSUjonKyhlJiZlLm1lc3NhZ2U/ZS5tZXNzYWdlOicnKTsgfSk7CiAgUHJvbWlzZS5hbGwoW3BDYXJhLHBUeHRdKS50aGVuKGZ1bmN0aW9uKHIpewogICAgdmFyIGNhcmE9clswXSwgdGV4dG89clsxXXx8Jyc7CiAgICBpZih0ZXh0by5pbmRleE9mKCdPQ1JfRVJSOicpPT09MCl7IGZhbGxvTGVjdHVyYUZyZW50ZSgnTm8gcHVkZSBsZWVyIGVsIGRvY3VtZW50byAoJyt0ZXh0by5zbGljZSg4KSsnKS4nKTsgcmV0dXJuOyB9CiAgICBpZih0ZXh0by5yZXBsYWNlKC9ccy9nLCcnKS5sZW5ndGg8MTUpeyBmYWxsb0xlY3R1cmFGcmVudGUoJ05vIGxlXHUwMEVEIHN1ZmljaWVudGUgdGV4dG8uIEFjXHUwMEU5cmNhdGUsIGJ1ZW5hIGx1eiwgcXVlIGVsIGRvY3VtZW50byBsbGVuZSBlbCBtYXJjby4nKTsgcmV0dXJuOyB9CiAgICB2YXIgbGFkbz1kZXRlY3RhckxhZG8odGV4dG8sISEoY2FyYSYmY2FyYS5kZXRlY3Rpb24pKTsKICAgIGlmKGxhZG89PT0ncmV2ZXJzbycpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbXNnKCdzdEYnLCdFc28gZXMgZWwgUkVWRVJTTyAoc2UgdmVuIGRpcmVjY2lvbmVzIG8gbGEgem9uYSBNUlopLiBOZWNlc2l0byBlbCBGUkVOVEU6IGRvbmRlIGVzdFx1MDBFMSB0dSBGT1RPIHkgdHVzIGRhdG9zLiBWdWVsdmUgYSBjYXB0dXJhci4nLCcjYzAwJyk7CiAgICAgIHJldHVybjsKICAgIH0KICAgIGlmKGxhZG8hPT0nZnJlbnRlJyAmJiAhKGNhcmEmJmNhcmEuZGV0ZWN0aW9uKSl7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBtc2coJ3N0RicsJ05vIHB1ZGUgY29uZmlybWFyIHF1ZSBzZWEgZWwgRlJFTlRFLiBBc2VnXHUwMEZBcmF0ZSBkZSBxdWUgc2UgdmVhIHR1IGZvdG8geSB0dXMgZGF0b3MsIHNpbiBicmlsbG8sIHkgdnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogICAgICByZXR1cm47CiAgICB9CiAgICBpZihjYXJhJiZjYXJhLmRldGVjdGlvbiYmY2FyYS5kZXNjcmlwdG9yKXsgRVNULmNhcmFEb2M9Y2FyYS5kZXNjcmlwdG9yOyB9CiAgICB2YXIgbmM9bm9tYnJlQ29pbmNpZGUoRVNULmVzY3JpdG8sdGV4dG8sbXJ6TGluZWFzKHRleHRvKS5sZW5ndGg+MCk7CiAgICBpZihuYy5oYXkgJiYgIW5jLm9rKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIGFicmlyQ29uZmlybWFjaW9uTGVjdHVyYSh0ZXh0bywgbmMubGVpZG8pOwogICAgICByZXR1cm47CiAgICB9CiAgICBFU1QuZnJlbnRlT2s9dHJ1ZTsKICAgIEVTVC5mcmVudGVUZXh0bz10ZXh0bzsKICAgIG1zZygnc3RGJywnXHUyNzEzIEZyZW50ZSBsZVx1MDBFRGRvIGNvcnJlY3RhbWVudGUuJysobmMub2s/KCcgTm9tYnJlOiAnK25jLmxlaWRvKycuJyk6JycpLCcjMDgwJyk7CiAgICBidXN5KGZhbHNlKTsKICAgIGF2YW56YXJUcmFzRnJlbnRlKCk7CiAgfSk7Cn0KLyogdjE2OiBOVU5DQSBzZSBib3JyYSB0dSB0cmFiYWpvIHkgTlVOQ0EgdGUgcmVncmVzYSBhbCBwYXNvIDEuIEFudGVzCiAgIGVzdGEgZnVuY2lvbiByZXNldGVhYmEgZWwgZG9jdW1lbnRvIHkgdGUgYm90YWJhIGFsIGluaWNpbyAoY29uIGVsCiAgIE1SWiBkZWwgcmV2ZXJzbyBsZWlkbyBhIG1lZGlhcyBlcmEgY2FzaSBzZWd1cm8gcXVlIHNhbHRhcmEpLiBBaG9yYQogICBzb2xvIGF2aXNhIGNvbiBjYWxtYSBhcXVpIG1pc21vOiBmb3RvcyB5IGF2YW5jZSBxdWVkYW4gaW50YWN0b3MuICovCmZ1bmN0aW9uIG5vbWJyZU5vQ29pbmNpZGVNc2codHh0KXsKICB2YXIgbm49JCgnbm9tYnJlTm9Db2luY2lkZScpOwogIGlmKG5uKXsgbm4udGV4dENvbnRlbnQ9dHh0OyBubi5zdHlsZS5kaXNwbGF5PSdibG9jayc7IG5uLnN0eWxlLmNvbG9yPScjYTYwJzsgfQogIG1zZygnc3RBJywnJyk7IG1zZygnc3RGJywnJyk7CiAgbXNnKCd6eUVyck5vbWJyZScsdHh0KycgU2kgdHUgbm9tYnJlIGVzdFx1MDBFMSBiaWVuIGVzY3JpdG8gcHVlZGVzIFNFR1VJUjogdG9jYSBDb250aW51YXIuIFR1IGF2YW5jZSB5IHR1cyBmb3RvcyBubyBzZSBib3JyYW4uJywnI2E2MCcpOwp9CmZ1bmN0aW9uIGJvdG9uUmVwZXRpckZvdG8oKXsKICB2YXIgYj0kKCd6eUJ0blJlcEZvdG8nKTsKICBpZighYil7CiAgICBiPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2J1dHRvbicpOwogICAgYi5pZD0nenlCdG5SZXBGb3RvJzsKICAgIGIudHlwZT0nYnV0dG9uJzsKICAgIGIudGV4dENvbnRlbnQ9J1JlcGV0aXIgbGEgZm90byBkZWwgZG9jdW1lbnRvJzsKICAgIGIuc3R5bGUuY3NzVGV4dD0nZGlzcGxheTpibG9jazttYXJnaW46OHB4IDA7cGFkZGluZzoxMXB4IDE0cHg7Ym9yZGVyOjA7Ym9yZGVyLXJhZGl1czoxMHB4O2JhY2tncm91bmQ6IzdjM2FlZDtjb2xvcjojZmZmO2ZvbnQtc2l6ZToxNHB4O2ZvbnQtd2VpZ2h0OjYwMDt3aWR0aDoxMDAlOyc7CiAgICBiLmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbigpeyB0cnl7IE1PVkxJQlJFPXRydWU7IFcuX196eUxpYnJlU2VzaW9uMTg9dHJ1ZTsgYXZhbnphcigyKTsgTU9WTElCUkU9ZmFsc2U7IH1jYXRjaChlKXsgTU9WTElCUkU9ZmFsc2U7IH0gfSk7CiAgICB2YXIgYW5jbGE9JCgnenlFcnJOb21icmUnKTsKICAgIGlmKGFuY2xhJiZhbmNsYS5wYXJlbnROb2RlKXsgYW5jbGEucGFyZW50Tm9kZS5pbnNlcnRCZWZvcmUoYixhbmNsYS5uZXh0U2libGluZyk7IH0KICAgIGVsc2V7IGRvY3VtZW50LmJvZHkuYXBwZW5kQ2hpbGQoYik7IH0KICB9CiAgYi5zdHlsZS5kaXNwbGF5PSdibG9jayc7Cn0KCi8qIHYxNjogYm90b24gVk9MVU5UQVJJTyBwYXJhIGlyIGFsIHBhc28gMSAobnVuY2EgdW4gbW92aW1pZW50byBmb3J6YWRvOgogICBzb2xvIGFwYXJlY2Ugc2kgZGUgdmVyZGFkIGZhbHRhIGVsIG5vbWJyZSB5IGVsIHVzdWFyaW8gZGVjaWRlKS4gKi8KZnVuY3Rpb24gYm90b25JclBhc28xKCl7CiAgdmFyIGI9JCgnenlCdG5JcjEnKTsKICBpZighYil7CiAgICBiPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2J1dHRvbicpOwogICAgYi5pZD0nenlCdG5JcjEnOwogICAgYi50eXBlPSdidXR0b24nOwogICAgYi50ZXh0Q29udGVudD0nSXIgYWwgcGFzbyAxIGEgZXNjcmliaXIgbWkgbm9tYnJlJzsKICAgIGIuc3R5bGUuY3NzVGV4dD0nZGlzcGxheTpibG9jazttYXJnaW46OHB4IDA7cGFkZGluZzoxMXB4IDE0cHg7Ym9yZGVyOjA7Ym9yZGVyLXJhZGl1czoxMHB4O2JhY2tncm91bmQ6IzJjMmMzYztjb2xvcjojZGRkO2ZvbnQtc2l6ZToxNHB4O2ZvbnQtd2VpZ2h0OjYwMDt3aWR0aDoxMDAlOyc7CiAgICBiLmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbigpeyB0cnl7IE1PVkxJQlJFPXRydWU7IFcuX196eUxpYnJlU2VzaW9uMTg9dHJ1ZTsgYXZhbnphcigxKTsgTU9WTElCUkU9ZmFsc2U7IH1jYXRjaChlKXsgTU9WTElCUkU9ZmFsc2U7IH0gfSk7CiAgICB2YXIgYW5jbGE9JCgnenlDbGF2ZU9rJyk7CiAgICBpZihhbmNsYSYmYW5jbGEucGFyZW50Tm9kZSl7IGFuY2xhLnBhcmVudE5vZGUuaW5zZXJ0QmVmb3JlKGIsYW5jbGEubmV4dFNpYmxpbmcpOyB9CiAgICBlbHNleyB2YXIgcHM1PSQoJ3BzNScpOyBpZihwczUpeyBwczUuYXBwZW5kQ2hpbGQoYik7IH0gZWxzZSB7IGRvY3VtZW50LmJvZHkuYXBwZW5kQ2hpbGQoYik7IH0gfQogIH0KICBiLnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsKfQoKLyogPT09PT09PT09PT09PT09PT0gcGFzbyAzOiByZXZlcnNvID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHJldmVyc29BY2VwdGFibGUodGV4dG8pewogIHZhciB0PSh0ZXh0b3x8JycpLnRvVXBwZXJDYXNlKCk7CiAgaWYoKHQubWF0Y2goLzwvZyl8fFtdKS5sZW5ndGg+PTYpeyByZXR1cm4gdHJ1ZTsgfQogIGlmKC9QREY0ST83Ly50ZXN0KHQucmVwbGFjZSgvXHMvZywnJykpKXsgcmV0dXJuIHRydWU7IH0KICB2YXIgZnVlcnRlcz1bJ0RPTUlDSUxJTycsJ0RJUkVDQ0lPTicsJ0RJUkVDQ0lcdTAwRDNOJywnQ09MT05JQScsJ0JBUlJJTycsJ1JFU0lERU5DSUEnLCdDQVNFUklPJywnQ0FOVE9OJywnQUxERUEnLCdPQlNFUlZBQ0lPTicsJ09CU0VSVkFDSVx1MDBEM04nLCdFU1RBRE8gQ0lWSUwnLCdET05BTlRFJywnR1JVUE8gU0FORycsJ1RJUE8gREUgU0FORycsJ0VORE9SU0VNRU5UJywnUkVTVFJJQ1RJT04nLCdBRERSRVNTJ107CiAgdmFyIGksYz0wOwogIGZvcihpPTA7aTxmdWVydGVzLmxlbmd0aDtpKyspeyBpZih0LmluZGV4T2YoZnVlcnRlc1tpXSk+PTApeyBjKys7IH0gfQogIGlmKGM+PTIpeyByZXR1cm4gdHJ1ZTsgfQogIGlmKEVTVC50aXBvPT09J3VzYScgJiYgL1xiKElTU3xFWFB8RER8NER8NEZ8UkVTVHxFTkR8REwpXGIvLnRlc3QodCkpeyByZXR1cm4gdHJ1ZTsgfQogIHJldHVybiBmYWxzZTsKfQpmdW5jdGlvbiBwcm9jZXNhclJldmVyc28oZGF0YVVybCl7CiAgRVNULnJldmVyc29Paz1mYWxzZTsKICBidXN5KHRydWUpOwogIG1zZygnc3RBJywnTGV5ZW5kbyBlbCByZXZlcnNvLi4uJywnJyk7CiAgRVNULnJldmVyc29JbWc9ZGF0YVVybDsKICBzaG93SW1nKCdwQScsZGF0YVVybCk7CiAgaGFjZXJPY3IoZGF0YVVybCkudGhlbihmdW5jdGlvbih0ZXh0byl7CiAgICBpZih0ZXh0by5yZXBsYWNlKC9ccy9nLCcnKS5sZW5ndGg8MTAgJiYgIXJldmVyc29BY2VwdGFibGUodGV4dG8pKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG1zZygnc3RBJywnTm8gbGVcdTAwRUQgc3VmaWNpZW50ZSB0ZXh0byBlbiBlbCByZXZlcnNvLiBBY1x1MDBFOXJjYXRlLCBidWVuYSBsdXosIHkgdnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogICAgICByZXR1cm47CiAgICB9CiAgICB2YXIgY2FyYVBlbmQ9bnVsbDsKICAgIHZhciBsYWRvPWRldGVjdGFyTGFkbyh0ZXh0byxmYWxzZSk7CiAgICBpZihsYWRvPT09J2ZyZW50ZScpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbXNnKCdzdEEnLCdFc28gZXMgZWwgRlJFTlRFIChzZSB2ZSBsYSBmb3RvIHkgbG9zIGRhdG9zKS4gTmVjZXNpdG8gZWwgUkVWRVJTTzogZGlyZWNjaW9uZXMgbyBsYSB6b25hIE1SWi4gVnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogICAgICByZXR1cm47CiAgICB9CiAgICBpZihsYWRvIT09J3JldmVyc28nICYmICFyZXZlcnNvQWNlcHRhYmxlKHRleHRvKSl7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBtc2coJ3N0QScsJ05vIHB1ZGUgY29uZmlybWFyIHF1ZSBzZWEgZWwgUkVWRVJTTy4gTXVlc3RyYSBsYXMgZGlyZWNjaW9uZXMgbyBsYSB6b25hIGRlIHJheWl0YXMvTVJaIHkgdnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogICAgICByZXR1cm47CiAgICB9CiAgICAvKiB2MTY6IGVsIHJldmVyc28gWUEgTk8gdmFsaWRhIGVsIG5vbWJyZS4gRWwgbm9tYnJlIHF1ZWRvCiAgICAgICBjb25maXJtYWRvIGNvbiBlbCBmcmVudGUgeSBzdSBwYW5lbCBkZSBsZWN0dXJhOyBlbCBNUlogZGVsCiAgICAgICByZXZlcnNvIHNhbGUgYSBtZWRpYXMgY29uIHBvY2EgbHV6IHkgaGFjaWEgcXVlIHRlIGJvdGFyYW4gYWwKICAgICAgIHBhc28gMSBjb24gdG9kbyBib3JyYWRvIChlbCByZWJvdGUgcXVlIHJlcG9ydGFzdGUpLiBBcXVpIHNvbG8KICAgICAgIHNlIHZhbGlkYSBxdWUgc2VhIGVsIHJldmVyc28uICovCiAgICBFU1QucmV2ZXJzb09rPXRydWU7CiAgICBFU1QucmV2ZXJzb1RleHRvPXRleHRvOwogICAgdHJ5eyByZXNwYWxkYSgpOyB9Y2F0Y2goZSl7fQogICAgbXNnKCdzdEEnLCdcdTI3MTMgUmV2ZXJzbyBsZVx1MDBFRGRvIGNvcnJlY3RhbWVudGUuJywnIzA4MCcpOwogICAgYnVzeShmYWxzZSk7CiAgICBhdmFuemFyKDQpOwogICAgc2V0VGltZW91dChmdW5jdGlvbigpeyB0cnl7IGFicmlyQ2FtKCc0JywndXNlcicsJ3N0VicsJ2JTZWxmaWUnKS5jYXRjaChmdW5jdGlvbigpe30pOyB9Y2F0Y2goZSl7fSB9LDUwMCk7CiAgfSkuY2F0Y2goZnVuY3Rpb24oZSl7CiAgICBidXN5KGZhbHNlKTsKICAgIG1zZygnc3RBJywnRXJyb3IgbGV5ZW5kbyBlbCByZXZlcnNvOiAnKyhlJiZlLm1lc3NhZ2U/ZS5tZXNzYWdlOicnKSsnLiBWdWVsdmUgYSBjYXB0dXJhci4nLCcjYzAwJyk7CiAgfSk7Cn0KCi8qID09PT09PT09PT09PT09PT09IHBhc28gNDogc2VsZmllID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHJlY29ydGVSb3N0cm8oZGF0YVVybCwgZGV0KXsKICB0cnl7CiAgICBpZighZGV0IHx8ICFkZXQuZGV0ZWN0aW9uIHx8ICFkZXQuZGV0ZWN0aW9uLmJveCl7IHJldHVybiBQcm9taXNlLnJlc29sdmUoZGF0YVVybCk7IH0KICAgIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpewogICAgICB2YXIgaW09bmV3IEltYWdlKCk7CiAgICAgIGltLm9ubG9hZD1mdW5jdGlvbigpewogICAgICAgIHRyeXsKICAgICAgICAgIHZhciBiPWRldC5kZXRlY3Rpb24uYm94LCBXMD1pbS53aWR0aCwgSDA9aW0uaGVpZ2h0OwogICAgICAgICAgdmFyIGN3PWIud2lkdGgqMi4yLCBjaD1iLmhlaWdodCoyLjY7CiAgICAgICAgICB2YXIgY3g9Yi54K2Iud2lkdGgvMiwgY3k9Yi55K2IuaGVpZ2h0KjAuNTI7CiAgICAgICAgICB2YXIgeDA9TWF0aC5tYXgoMCxNYXRoLnJvdW5kKGN4LWN3LzIpKSwgeTA9TWF0aC5tYXgoMCxNYXRoLnJvdW5kKGN5LWNoLzIpKTsKICAgICAgICAgIHZhciB3MD1NYXRoLm1pbihXMC14MCxNYXRoLnJvdW5kKGN3KSksIGgwPU1hdGgubWluKEgwLXkwLE1hdGgucm91bmQoY2gpKTsKICAgICAgICAgIGlmKHcwPDQwfHxoMDw0MCl7IHJlcyhkYXRhVXJsKTsgcmV0dXJuOyB9CiAgICAgICAgICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICAgICAgICAgIGMud2lkdGg9dzA7IGMuaGVpZ2h0PWgwOwogICAgICAgICAgdmFyIGc9Yy5nZXRDb250ZXh0KCcyZCcpOwogICAgICAgICAgaWYoIWcpeyByZXMoZGF0YVVybCk7IHJldHVybjsgfQogICAgICAgICAgZy5kcmF3SW1hZ2UoaW0sIHgwLCB5MCwgdzAsIGgwLCAwLCAwLCB3MCwgaDApOwogICAgICAgICAgcmVzKGMudG9EYXRhVVJMKCdpbWFnZS9qcGVnJywwLjkpKTsKICAgICAgICB9Y2F0Y2goZUUpeyByZXMoZGF0YVVybCk7IH0KICAgICAgfTsKICAgICAgaW0ub25lcnJvcj1mdW5jdGlvbigpeyByZXMoZGF0YVVybCk7IH07CiAgICAgIGltLnNyYz1kYXRhVXJsOwogICAgfSk7CiAgfWNhdGNoKGUpeyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKGRhdGFVcmwpOyB9Cn0KZnVuY3Rpb24gY2FqYURlUXVhZChxLCB2dywgdmgsIG1hcmcpewogIHRyeXsKICAgIGlmKCFxIHx8ICFxLnRsIHx8ICFxLnRyIHx8ICFxLmJyIHx8ICFxLmJsKXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciB4cz1bcS50bC54LHEudHIueCxxLmJyLngscS5ibC54XSwgeXM9W3EudGwueSxxLnRyLnkscS5ici55LHEuYmwueV07CiAgICB2YXIgeDA9TWF0aC5taW4uYXBwbHkobnVsbCx4cyksIHgxPU1hdGgubWF4LmFwcGx5KG51bGwseHMpOwogICAgdmFyIHkwPU1hdGgubWluLmFwcGx5KG51bGwseXMpLCB5MT1NYXRoLm1heC5hcHBseShudWxsLHlzKTsKICAgIHZhciBteD0oeDEteDApKm1hcmcsIG15PSh5MS15MCkqbWFyZzsKICAgIHgwPU1hdGgubWF4KDAsTWF0aC5mbG9vcih4MC1teCkpOyB5MD1NYXRoLm1heCgwLE1hdGguZmxvb3IoeTAtbXkpKTsKICAgIHgxPU1hdGgubWluKHZ3LE1hdGguY2VpbCh4MStteCkpOyB5MT1NYXRoLm1pbih2aCxNYXRoLmNlaWwoeTErbXkpKTsKICAgIGlmKHgxLXgwPDQwfHx5MS15MDw0MCl7IHJldHVybiBudWxsOyB9CiAgICByZXR1cm4ge3g6eDAsIHk6eTAsIHc6eDEteDAsIGg6eTEteTB9OwogIH1jYXRjaChlKXsgcmV0dXJuIG51bGw7IH0KfQpmdW5jdGlvbiBjYXB0dXJhclZpZGVvRG9jKHBzSWQsIG1heERpbSl7CiAgdmFyIHY9ZmluZFZpZGVvKHBzSWQpOwogIGlmKCF2IHx8ICF2LnZpZGVvV2lkdGggfHwgIXN0cmVhbXNbcHNJZF0peyByZXR1cm4gbnVsbDsgfQogIHZhciB2dz12LnZpZGVvV2lkdGgsIHZoPXYudmlkZW9IZWlnaHQ7CiAgdmFyIHN0PXp5RGV0KClbcHNJZF18fG51bGw7CiAgdmFyIHI9bnVsbCwgYWhvcmE9RGF0ZS5ub3coKTsKICBpZihzdCl7CiAgICBpZihzdC51bHRRdWFkICYmIChhaG9yYS0oc3QudWx0UXVhZFR8fDApKTwxNTAwKXsgcj1jYWphRGVRdWFkKHN0LnVsdFF1YWQsIHZ3LCB2aCwgMC4wNCk7IH0KICAgIGlmKCFyICYmIHN0LnVsdENhamEgJiYgKGFob3JhLShzdC51bHRDYWphVHx8MCkpPDIwMDApewogICAgICB2YXIgYj1zdC51bHRDYWphLCBteD1iLncqMC4wMywgbXk9Yi5oKjAuMDM7CiAgICAgIHZhciBieD1NYXRoLm1heCgwLE1hdGguZmxvb3IoYi54LW14KSksIGJ5PU1hdGgubWF4KDAsTWF0aC5mbG9vcihiLnktbXkpKTsKICAgICAgdmFyIGJ3PU1hdGgubWluKHZ3LWJ4LE1hdGguY2VpbChiLncrbXgqMikpLCBiaD1NYXRoLm1pbih2aC1ieSxNYXRoLmNlaWwoYi5oK215KjIpKTsKICAgICAgaWYoYnc+PTQwJiZiaD49NDApeyByPXt4OmJ4LCB5OmJ5LCB3OmJ3LCBoOmJofTsgfQogICAgfQogIH0KICBpZighcil7IHI9e3g6TWF0aC5yb3VuZCh2dyowLjA3KSwgeTpNYXRoLnJvdW5kKHZoKjAuMDkpLCB3Ok1hdGgucm91bmQodncqMC44NiksIGg6TWF0aC5yb3VuZCh2aCowLjgyKX07IH0KICBpZihyLng8MCl7IHIueD0wOyB9CiAgaWYoci55PDApeyByLnk9MDsgfQogIGlmKHIueCtyLnc+dncpeyByLnc9dnctci54OyB9CiAgaWYoci55K3IuaD52aCl7IHIuaD12aC1yLnk7IH0KICBpZihyLnc8NDB8fHIuaDw0MCl7IHJldHVybiBjYXB0dXJhclZpZGVvKHBzSWQsIG1heERpbSk7IH0KICB2YXIgc2M9TWF0aC5taW4oMSwgKG1heERpbXx8MTYwMCkvTWF0aC5tYXgoci53LCByLmgpKTsKICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICBjLndpZHRoPU1hdGgubWF4KDE2LE1hdGgucm91bmQoci53KnNjKSk7CiAgYy5oZWlnaHQ9TWF0aC5tYXgoMTYsTWF0aC5yb3VuZChyLmgqc2MpKTsKICB2YXIgZz1jLmdldENvbnRleHQoJzJkJyk7CiAgaWYoIWcpeyByZXR1cm4gY2FwdHVyYXJWaWRlbyhwc0lkLCBtYXhEaW0pOyB9CiAgZy5kcmF3SW1hZ2Uodiwgci54LCByLnksIHIudywgci5oLCAwLCAwLCBjLndpZHRoLCBjLmhlaWdodCk7CiAgdmFyIGQ9Yy50b0RhdGFVUkwoJ2ltYWdlL2pwZWcnLDAuOSk7CiAgcGFyYXJDYW0ocHNJZCk7CiAgcmV0dXJuIGQ7Cn0KZnVuY3Rpb24gcHJvY2VzYXJTZWxmaWUoKXsKICBFU1Quc2VsZmllT2s9ZmFsc2U7CiAgdmFyIGltZz1jYXB0dXJhclZpZGVvKCc0JywxMDQ4KTsKICBpZighaW1nKXsgbXNnKCdzdFYnLCdQcmltZXJvIGFicmUgbGEgY2FtYXJhIHkgcG9uIHR1IGNhcmEgZGVudHJvIGRlbCBtYXJjby4nLCcjYzAwJyk7IHJldHVybjsgfQogIGJ1c3kodHJ1ZSk7CiAgbXNnKCdzdFYnLCdCdXNjYW5kbyB0dSByb3N0cm8gcGFyYSBsYSBmb3RvIGRlIGNhcmEuLi4nLCcnKTsKICBjb25UaW1lb3V0KGRldGVjdGFyQ2FyYUVuKGltZyksMTIwMDApLnRoZW4oZnVuY3Rpb24oZDApewogICAgdmFyIHBSZWM9KGQwJiZkMC5kZXRlY3Rpb24pP3JlY29ydGVSb3N0cm8oaW1nLGQwKTpQcm9taXNlLnJlc29sdmUoaW1nKTsKICAgIHJldHVybiBwUmVjLmNhdGNoKGZ1bmN0aW9uKCl7IHJldHVybiBpbWc7IH0pOwogIH0pLmNhdGNoKGZ1bmN0aW9uKCl7IHJldHVybiBpbWc7IH0pLnRoZW4oZnVuY3Rpb24ocmVjKXsKICAgIEVTVC5zZWxmaWVJbWc9cmVjfHxpbWc7CiAgICBFU1Qucm9zdHJvUmVjb3J0YWRvPSEhKHJlYyYmcmVjIT09aW1nKTsKICAgIHNob3dJbWcoJ3BTJyxFU1Quc2VsZmllSW1nKTsKICAgIG1zZygnc3RWJywnQ29tcGFyYW5kbyB0dSBjYXJhIGNvbiBsYSBkZWwgZG9jdW1lbnRvLi4uJywnJyk7CiAgICB2YXIgcERvYz1FU1QuY2FyYURvYz9Qcm9taXNlLnJlc29sdmUoRVNULmNhcmFEb2MpOmNvblRpbWVvdXQoZGV0ZWN0YXJDYXJhRG9jKEVTVC5mcmVudGVJbWd8fEVTVC5yZXZlcnNvSW1nfHwnJyksMTUwMDApLnRoZW4oZnVuY3Rpb24ocil7IHJldHVybiAociYmci5kZXRlY3Rpb24mJnIuZGVzY3JpcHRvcik/ci5kZXNjcmlwdG9yOm51bGw7IH0pOwogICAgdmFyIHBTZWw9Y29uVGltZW91dChkZXRlY3RhckNhcmFFbihFU1Quc2VsZmllSW1nLDIpLDE1MDAwKS50aGVuKGZ1bmN0aW9uKHIwKXsKICAgICAgaWYocjAmJnIwLmRldGVjdGlvbil7IHJldHVybiByMDsgfQogICAgICByZXR1cm4gY29uVGltZW91dChkZXRlY3RhckNhcmFFbihFU1Quc2VsZmllSW1nKSwxNTAwMCk7CiAgICB9KTsKICAgIFByb21pc2UuYWxsKFtwRG9jLHBTZWxdKS50aGVuKGZ1bmN0aW9uKHIpewogICAgICB2YXIgZERvYz1yWzBdLCBlblNlbD1yWzFdOwogICAgICBpZighZERvYyl7IGJ1c3koZmFsc2UpOyBmYWxsb1NlbGZpZSgnTm8gcHVkZSB2ZXIgYmllbiBsYSBjYXJhIGVuIGxhIGZvdG8gZGVsIGRvY3VtZW50by4gVmFtb3MgYSByZXBldGlyIGxhIGZvdG8gZGVsIGRvY3VtZW50byBjb24gbWVqb3IgbHV6LicpOyByZXR1cm47IH0KICAgICAgaWYoIWVuU2VsIHx8ICFlblNlbC5kZXRlY3Rpb24peyBidXN5KGZhbHNlKTsgZmFsbG9TZWxmaWUoJ05vIHB1ZGUgdmVyIHR1IGNhcmEgZW4gbGEgc2VsZmllLiBNZWpvciBsYSBsdXosIHF1aXRhdGUgZ29ycmEgbyBsZW50ZXMgb3NjdXJvcy4nKTsgcmV0dXJuOyB9CiAgICAgIHZhciBkPWRpc3RGKGREb2MsZW5TZWwuZGVzY3JpcHRvcik7CiAgICAgIGlmKGQ8PTAuNjApewogICAgICAgIEVTVC5zZWxmaWVPaz10cnVlOyBFU1QuaW50ZW50b3M9NTsKICAgICAgICB0cnl7IHJlc3BhbGRhKCk7IH1jYXRjaChlKXt9CiAgICAgICAgbXNnKCdzdFYnLCdcdTI3MTMgVmVyaWZpY2FjaVx1MDBGM24gZmFjaWFsIHN1cGVyYWRhLiBQYXNhbmRvIGEgdHUgY2xhdmUuJywnIzA4MCcpOwogICAgICAgIGJ1c3koZmFsc2UpOyBhdmFuemFyKDUpOwogICAgICB9ZWxzZXsKICAgICAgICBidXN5KGZhbHNlKTsKICAgICAgICBmYWxsb1NlbGZpZSgnVHUgY2FyYSBubyBjb2luY2lkZSBjb24gbGEgZGVsIGRvY3VtZW50byAoZGlzdGFuY2lhICcrZC50b0ZpeGVkKDIpKycpLicrKEVTVC5yb3N0cm9SZWNvcnRhZG8/Jyc6JyBBY2VyY2F0ZTogdHUgY2FyYSBkZWJlIGxsZW5hciBlbCBvdmFsby4nKSk7CiAgICAgIH0KICAgIH0pLmNhdGNoKGZ1bmN0aW9uKGUpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgZmFsbG9TZWxmaWUoJ0VsIHZlcmlmaWNhZG9yIGZhY2lhbCBubyBjYXJnXHUwMEYzOiAnKyhlJiZlLm1lc3NhZ2U/ZS5tZXNzYWdlOicnKSsnLiBSZXZpc2EgdHUgaW50ZXJuZXQgeSByZWludGVudGEuJyk7CiAgICB9KTsKICB9KTsKfQpmdW5jdGlvbiBmYWxsb1NlbGZpZShtKXsKICBFU1QuaW50ZW50b3MtLTsKICBpZihFU1QuaW50ZW50b3M8PTApewogICAgRVNULmludGVudG9zPTU7CiAgICBFU1Quc2VsZmllT2s9ZmFsc2U7CiAgICBtc2coJ3N0VicsJ1NlIGFnb3Rhcm9uIGxvcyBpbnRlbnRvcyBkZSBsYSBzZWxmaWUsIHBlcm8gTk8gcGVyZGlzdGUgbmFkYTogbmkgdHUgbm9tYnJlIG5pIHR1cyBmb3RvcyBkZWwgZG9jdW1lbnRvIHNlIGJvcnJhbi4gTWVqb3JhIGxhIGx1eiBkZSB0dSBjYXJhLCBBQ0VSQ0FURSBoYXN0YSBxdWUgdHUgY2FyYSBsbGVuZSBlbCBvdmFsbyB5IHRvY2EgQ0FQVFVSQVIgZGUgbnVldm8uJywnI2E2MCcpOwogIH1lbHNlewogICAgbXNnKCdzdFYnLCdcdTI3MTcgJyttKycgVGUgcXVlZGFuICcrRVNULmludGVudG9zKycgaW50ZW50byhzKS4gVG9jYSBDQVBUVVJBUiBkZSBudWV2bzogeW8gcmVjb3J0byBzb2xvIHR1IHJvc3Ryby4nLCcjYzAwJyk7CiAgfQp9Ci8qID09PT09PT09PT09PT09PT09IHBhc28gNTogY2xhdmUgKyBaSUQgKHYxNykgPT09PT09PT09PT09PT09PT0KICAgdjE3OiBMQSBDTEFWRSBZQSBOTyBTRSBQSUVSREUgTkkgU0UgIk9MVklEQSIuIExvIHJlcG9ydGFkbyBjb24gY2FwdHVyYQogICBlbCA5LzExIChlc2NyaWJlcyBsYSBjbGF2ZSwgdG9jYXMgQ3JlYXIgbWkgWklELCBsYSBwYWdpbmEgdnVlbHZlIGNvbiBsYQogICBjbGF2ZSBCT1JSQURBIHkgcGFyZWNlIHF1ZSAibm8gcmVjb25vY2UgbGEgY2xhdmUiKSB0ZW5pYSBjYXVzYXMgY29uY3JldGFzLAogICB0b2RhcyBjb3JyZWdpZGFzIGFxdWk6CiAgIGEpIGxvcyBjYW1wb3Mgc2UgYnVzY2FiYW4gU09MTyBwb3IgaWQgZmlqbyAiY2xhdmUiLyJjbGF2ZTIiOiBzaSBlbAogICAgICBmb3JtdWxhcmlvIHJlYWwgdXNhIG90cm9zIGlkLCBsYSB2YWxpZGFjaW9uIG51bmNhIHZlIGxvIHF1ZSBlc2NyaWJlcy4KICAgICAgQWhvcmEgc2UgZGVzY3VicmVuIHBvciB0aXBvIChpbnB1dFt0eXBlPXBhc3N3b3JkXSkgeSBub21icmUvaWQgcGFyZWNpZG87CiAgIGIpIGVsIGF1dG9ycmVsbGVubyBkZWwgbmF2ZWdhZG9yIG5vIGRpc3BhcmEgImlucHV0IjogYWhvcmEgaGF5IHNvbmRlbwogICAgICBjYWRhIDYwMCBtcyArIGV2ZW50b3MgY2hhbmdlL2JsdXIgeSBzZSBzaW5jcm9uaXphIHNvbG87CiAgIGMpIGFsIHJlY2FyZ2Fyc2UgbGEgcGFnaW5hIGxhIGNsYXZlIG5vIHNlIGd1YXJkYWJhOiBhaG9yYSBxdWVkYSByZXNwYWxkYWRhCiAgICAgIGVuIHNlc3Npb25TdG9yYWdlIChzb2xvIGVuIHR1IHRlbGVmb25vLCBtdWVyZSBhbCBjZXJyYXIgZWwgbmF2ZWdhZG9yKQogICAgICB5IHNlIHJlcG9uZSBzb2xhIGVuIGxvcyBjdWFkcm9zIHF1ZSBlc3RlbiB2YWNpb3MgYWwgdm9sdmVyLiAqLwp2YXIgQ0xWPXthOm51bGwsYjpudWxsLG1vZG86MCx1MTp1bmRlZmluZWQsdTI6dW5kZWZpbmVkfTsKdmFyIEtTRVNNPSd6eUNsYXZlUzE3JzsKZnVuY3Rpb24gY2FtcG9zQ2xhdmUoKXsgcmV0dXJuIFtDTFYuYSxDTFYuYl07IH0KZnVuY3Rpb24gZGVzY3VicmVDbGF2ZXMoZm9yY2UpewogIGlmKCFmb3JjZSYmQ0xWLmEpewogICAgdHJ5eyBpZihDTFYuYS5vd25lckRvY3VtZW50JiZkb2N1bWVudC5jb250YWlucyhDTFYuYSkpeyByZXR1cm4gQ0xWOyB9IH1jYXRjaChlQyl7IH0KICB9CiAgdmFyIGxpc3RhPVtdLCBpLCBqOwogIGZ1bmN0aW9uIG1ldGUoZWwpewogICAgaWYoIWVsfHxsaXN0YS5pbmRleE9mKGVsKT49MCl7IHJldHVybjsgfQogICAgdmFyIHR5PSgoZWwudHlwZXx8JycpKycnKS50b0xvd2VyQ2FzZSgpOwogICAgaWYodHkhPT0ncGFzc3dvcmQnJiZ0eSE9PSd0ZXh0Jyl7IHJldHVybjsgfQogICAgbGlzdGEucHVzaChlbCk7CiAgfQogIG1ldGUoJCgnY2xhdmUnKSk7IG1ldGUoJCgnY2xhdmUyJykpOwogIHZhciBwczU9JCgncHM1Jyk7CiAgaWYobGlzdGEubGVuZ3RoPDImJnBzNSl7CiAgICB2YXIgaW5zPXBzNS5xdWVyeVNlbGVjdG9yQWxsKCdpbnB1dFt0eXBlPXBhc3N3b3JkXScpOwogICAgZm9yKGo9MDtqPGlucy5sZW5ndGgmJmxpc3RhLmxlbmd0aDwyO2orKyl7IG1ldGUoaW5zW2pdKTsgfQogIH0KICBpZihsaXN0YS5sZW5ndGg8MSl7CiAgICB2YXIgZj1udWxsOwogICAgdHJ5eyBmPWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoJ2Zvcm0nKTsgfWNhdGNoKGVRKXsgZj1udWxsOyB9CiAgICBpZihmKXsgdmFyIGluczI9Zi5xdWVyeVNlbGVjdG9yQWxsKCdpbnB1dFt0eXBlPXBhc3N3b3JkXScpOyBmb3Ioaj0wO2o8aW5zMi5sZW5ndGgmJmxpc3RhLmxlbmd0aDwyO2orKyl7IG1ldGUoaW5zMltqXSk7IH0gfQogIH0KICBpZihsaXN0YS5sZW5ndGg8MSl7CiAgICB2YXIgaW5zMz1kb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCdpbnB1dFt0eXBlPXBhc3N3b3JkXScpOwogICAgZm9yKGo9MDtqPGluczMubGVuZ3RoJiZsaXN0YS5sZW5ndGg8MjtqKyspeyBtZXRlKGluczNbal0pOyB9CiAgfQogIGlmKGxpc3RhLmxlbmd0aDwxKXsKICAgIHZhciBpbnM0PWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoJ2lucHV0W3R5cGU9dGV4dF0nKTsKICAgIGZvcihqPTA7ajxpbnM0Lmxlbmd0aCYmbGlzdGEubGVuZ3RoPDI7aisrKXsKICAgICAgdmFyIG5tPSgoKGluczRbal0uaWR8fCcnKSsnJykrJyAnKygoaW5zNFtqXS5uYW1lfHwnJykrJycpKS50b0xvd2VyQ2FzZSgpOwogICAgICBpZigvY2xhdmV8cGFzc3xjb250cmFzLy50ZXN0KG5tKSl7IG1ldGUoaW5zNFtqXSk7IH0KICAgIH0KICB9CiAgaWYobGlzdGEubGVuZ3RoPj0yKXsgQ0xWLmE9bGlzdGFbMF07IENMVi5iPWxpc3RhWzFdOyBDTFYubW9kbz0yOyB9CiAgZWxzZSBpZihsaXN0YS5sZW5ndGg9PT0xKXsgQ0xWLmE9bGlzdGFbMF07IENMVi5iPW51bGw7IENMVi5tb2RvPTE7IH0KICBlbHNleyBDTFYuYT1udWxsOyBDTFYuYj1udWxsOyBDTFYubW9kbz0wOyB9CiAgcmV0dXJuIENMVjsKfQpmdW5jdGlvbiBsZWVyQ2xhdmVzKCl7CiAgZGVzY3VicmVDbGF2ZXMoZmFsc2UpOwogIHJldHVybiB7IHYxOihDTFYuYT9DTFYuYS52YWx1ZTonJyksIHYyOihDTFYuYj9DTFYuYi52YWx1ZTonJyksIG1vZG86Q0xWLm1vZG8sIGE6Q0xWLmEsIGI6Q0xWLmIgfTsKfQpmdW5jdGlvbiBndWFyZGFyQ2xhdmVTZXNpb24oKXsKICB0cnl7CiAgICB2YXIgTD1sZWVyQ2xhdmVzKCk7CiAgICBpZighTC5hKXsgcmV0dXJuOyB9CiAgICBzZXNzaW9uU3RvcmFnZS5zZXRJdGVtKEtTRVNNLEpTT04uc3RyaW5naWZ5KHtjMTpMLnYxLGMyOkwudjIsdHM6RGF0ZS5ub3coKX0pKTsKICAgIENMVi51MT1MLnYxOyBDTFYudTI9TC52MjsKICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIHJlc3RhdXJhckNsYXZlU2VzaW9uKCl7CiAgdHJ5ewogICAgdmFyIHM9c2Vzc2lvblN0b3JhZ2UuZ2V0SXRlbShLU0VTTSk7CiAgICBpZighcyl7IHJldHVybiBmYWxzZTsgfQogICAgdmFyIGQ9SlNPTi5wYXJzZShzKXx8e307CiAgICBpZihEYXRlLm5vdygpLShkLnRzfHwwKT44NjQwMDAwMCl7IHNlc3Npb25TdG9yYWdlLnJlbW92ZUl0ZW0oS1NFU00pOyByZXR1cm4gZmFsc2U7IH0KICAgIGRlc2N1YnJlQ2xhdmVzKGZhbHNlKTsKICAgIHZhciBoZWNobz1mYWxzZTsKICAgIGlmKENMVi5hJiYhQ0xWLmEudmFsdWUmJmQuYzEpeyBDTFYuYS52YWx1ZT1kLmMxOyBoZWNobz10cnVlOyB9CiAgICBpZihDTFYuYiYmIUNMVi5iLnZhbHVlJiZkLmMyKXsgQ0xWLmIudmFsdWU9ZC5jMjsgaGVjaG89dHJ1ZTsgfQogICAgcmV0dXJuIGhlY2hvOwogIH1jYXRjaChlKXsgcmV0dXJuIGZhbHNlOyB9Cn0KZnVuY3Rpb24gbWVuc2FqZUNsYXZlKEwpewogIEw9THx8bGVlckNsYXZlcygpOwogIHZhciB2MT1MLnYxfHwnJywgdjI9TC52Mnx8Jyc7CiAgaWYoTC5tb2RvPT09MSl7CiAgICBpZighdjEpeyByZXR1cm4ge3Q6JycsYzonJyxvazpmYWxzZX07IH0KICAgIGlmKHYxLmxlbmd0aDw4KXsgcmV0dXJuIHt0OidcdTI3MTcgVHUgY2xhdmUgdGllbmUgJyt2MS5sZW5ndGgrJyBjYXJhY3Rlcihlcyk7IG5lY2VzaXRhIG1pbmltbyA4LicsYzonI2MwMCcsb2s6ZmFsc2V9OyB9CiAgICByZXR1cm4ge3Q6J1x1MjcxMyBDbGF2ZSBsaXN0YS4gVG9jYSBlbCBib3RcdTAwRjNuIHBhcmEgY3JlYXIgdHUgWklELicsYzonIzA4MCcsb2s6dHJ1ZX07CiAgfQogIGlmKCF2MSYmIXYyKXsgcmV0dXJuIHt0OicnLGM6Jycsb2s6ZmFsc2V9OyB9CiAgaWYoIXYxKXsgcmV0dXJuIHt0OidFc2NyaWJlIHR1IGNsYXZlIGVuIGVsIFBSSU1FUiBjdWFkcm8gKCJDcmVhIHR1IGNsYXZlIGRlIGFjY2VzbyIpLicsYzonI2MwMCcsb2s6ZmFsc2V9OyB9CiAgaWYoIXYyKXsgcmV0dXJuIHt0OidGYWx0YSBSRVBFVElSIGxhIGNsYXZlOiBlc2NyaWJlIGxhIE1JU01BIGNsYXZlIGVuIGVsIHNlZ3VuZG8gY3VhZHJvICgiUmVwaXRlIGxhIGNsYXZlIikuJyxjOicjYjQ1MzA5JyxvazpmYWxzZX07IH0KICBpZih2MS5sZW5ndGg8OCl7IHJldHVybiB7dDonXHUyNzE3IFR1IGNsYXZlIHRpZW5lICcrdjEubGVuZ3RoKycgY2FyYWN0ZXIoZXMpOyBuZWNlc2l0YSBtaW5pbW8gOCBlbiBsb3MgZG9zIGN1YWRyb3MuJyxjOicjYzAwJyxvazpmYWxzZX07IH0KICBpZih2MSE9PXYyKXsgcmV0dXJuIHt0OidcdTI3MTcgTGFzIGNsYXZlcyBOTyBjb2luY2lkZW46IGVsIHNlZ3VuZG8gY3VhZHJvIGRlYmUgc2VyIEVYQUNUQU1FTlRFIGlndWFsIGFsIHByaW1lcm8uJyxjOicjYzAwJyxvazpmYWxzZX07IH0KICByZXR1cm4ge3Q6J1x1MjcxMyBDbGF2ZXMgbGlzdGFzIGUgaWd1YWxlcy4gVG9jYSBlbCBib3RcdTAwRjNuIHBhcmEgY3JlYXIgdHUgWklELicsYzonIzA4MCcsb2s6dHJ1ZX07Cn0KZnVuY3Rpb24gdmFsaWRhckNsYXZlcygpewogIHZhciBMPWxlZXJDbGF2ZXMoKSwgZD0kKCdkZXNnbG9zZScpOwogIGlmKCFMLmEpeyByZXR1cm47IH0KICBndWFyZGFyQ2xhdmVTZXNpb24oKTsKICB2YXIgdD1tZW5zYWplQ2xhdmUoTCk7CiAgaWYoZCl7IGQudGV4dENvbnRlbnQ9dC50OyBkLnN0eWxlLmNvbG9yPXQuYzsgfQogIGlmKHQub2speyBoYWJpbGl0YXJTdWJtaXQoKTsgfQp9CmZ1bmN0aW9uIGhhYmlsaXRhclN1Ym1pdCgpewogIHZhciBwcz0kKCdwczUnKTsKICBpZighcHMpeyByZXR1cm47IH0KICB2YXIgYnRucz1wcy5xdWVyeVNlbGVjdG9yQWxsKCdidXR0b24sIGlucHV0W3R5cGU9YnV0dG9uXSwgaW5wdXRbdHlwZT1zdWJtaXRdLCBbcm9sZT1idXR0b25dJyksIGksIGhheT1mYWxzZTsKICBmb3IoaT0wO2k8YnRucy5sZW5ndGg7aSsrKXsKICAgIHZhciBlc1N1Ym1pdD1mYWxzZTsKICAgIHRyeXsgZXNTdWJtaXQ9KChidG5zW2ldLmdldEF0dHJpYnV0ZSgndHlwZScpfHwnJykudG9Mb3dlckNhc2UoKT09PSdzdWJtaXQnKTsgfWNhdGNoKGVUKXsgZXNTdWJtaXQ9ZmFsc2U7IH0KICAgIHZhciB0PSgoYnRuc1tpXS50ZXh0Q29udGVudHx8JycpKycgJysoYnRuc1tpXS52YWx1ZXx8JycpKS50b1VwcGVyQ2FzZSgpOwogICAgaWYoZXNTdWJtaXR8fC9DUkVBUnxSRUdJU1RSfEZJTkFMSVpBUnxDT05USU5VQVJ8RU5WSUFSfEFDRVBUQVJ8WklELy50ZXN0KHQpKXsgYnRuc1tpXS5kaXNhYmxlZD1mYWxzZTsgaGF5PXRydWU7IH0KICB9CiAgaWYoIWhheSl7IG1zZygnenlDbGF2ZU9rJywnU2kgbm8gdmVzIGVsIGJvdFx1MDBGM24gcGFyYSBjcmVhciB0dSBaSUQsIGF2XHUwMEVEc2FtZS4nLCcjYTYwJyk7IH0KfQoKLyogPT09PT09PT09PT09PT09PT0gcGFzbyA1OiBmaWx0cm8gZmluYWwgYW50ZXMgZGVsIGVudmlvID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIGNsYXZlc0xpc3RhcygpewogIHZhciBMPWxlZXJDbGF2ZXMoKTsKICBpZighTC5hKXsgcmV0dXJuIGZhbHNlOyB9CiAgaWYoIUwudjF8fEwudjEubGVuZ3RoPDgpeyByZXR1cm4gZmFsc2U7IH0KICBpZihMLm1vZG89PT0yJiZMLnYxIT09TC52Mil7IHJldHVybiBmYWxzZTsgfQogIHJldHVybiB0cnVlOwp9CmZ1bmN0aW9uIGZvdG9zQ29tcGxldGFzKCl7CiAgcmV0dXJuICEhKEVTVC5mcmVudGVPayYmRVNULnNlbGZpZU9rJiYoIUVTVC5uZWNlc2l0YVJldmVyc298fEVTVC5yZXZlcnNvT2spKTsKfQpmdW5jdGlvbiByZWxsZW5hckZvdG9zRm9ybXVsYXJpbygpewogIHZhciBwczU9JCgncHM1Jyk7CiAgdmFyIGY9cHM1PyhwczUucXVlcnlTZWxlY3RvcignZm9ybScpfHxudWxsKTpudWxsOwogIGlmKCFmKXsgdHJ5eyBmPWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoJ2Zvcm0nKTsgfWNhdGNoKGUpeyBmPW51bGw7IH0gfQogIGlmKCFmfHwhZi5lbGVtZW50cyl7IHJldHVybjsgfQogIHZhciBlbHM9Zi5lbGVtZW50cywgaTsKICBmb3IoaT0wO2k8ZWxzLmxlbmd0aDtpKyspewogICAgdmFyIGVsPWVsc1tpXTsKICAgIGlmKCFlbCl7IGNvbnRpbnVlOyB9CiAgICB2YXIgdGFnPWVsLnRhZ05hbWV8fCcnOwogICAgaWYodGFnIT09J0lOUFVUJyYmdGFnIT09J1RFWFRBUkVBJyl7IGNvbnRpbnVlOyB9CiAgICB2YXIgdD0oKGVsLnR5cGV8fCcnKSsnJykudG9Mb3dlckNhc2UoKTsKICAgIGlmKHRhZz09PSdJTlBVVCcmJnQhPT0naGlkZGVuJyYmdCE9PSd0ZXh0Jyl7IGNvbnRpbnVlOyB9CiAgICBpZigoZWwudmFsdWV8fCcnKS5sZW5ndGg+MTApeyBjb250aW51ZTsgfQogICAgdmFyIG5vbT0oKChlbC5uYW1lfHwnJykrJycpKycgJysoKGVsLmlkfHwnJykrJycpKS50b0xvd2VyQ2FzZSgpOwogICAgaWYoL2ZyZW50ZXxmcm9udGFsfGFudmVyc298Zm90b2Z8ZG9jMXxmb3RvMS8udGVzdChub20pKXsgaWYoRVNULmZyZW50ZUltZyl7IGVsLnZhbHVlPUVTVC5mcmVudGVJbWc7IH0gfQogICAgZWxzZSBpZigvcmV2ZXJzb3xkb3Jzb3x0cmFzZXJhfGZvdG9yZXZ8ZG9jMnxmb3RvMi8udGVzdChub20pKXsgaWYoRVNULnJldmVyc29JbWcpeyBlbC52YWx1ZT1FU1QucmV2ZXJzb0ltZzsgfSB9CiAgICBlbHNlIGlmKC9zZWxmaWV8cm9zdHJvfGZhY2lhbHxjYXJhfGZhY2V8Zm90bzN8Zm90b3MvLnRlc3Qobm9tKSl7IGlmKEVTVC5zZWxmaWVJbWcpeyBlbC52YWx1ZT1FU1Quc2VsZmllSW1nOyB9IH0KICB9Cn0KZnVuY3Rpb24gZ3VhcmRpYUVudmlvKGV2KXsKICBmdW5jdGlvbiBibG9xdWVhcigpewogICAgaWYoZXYpeyB0cnl7IGlmKGV2LnByZXZlbnREZWZhdWx0KXsgZXYucHJldmVudERlZmF1bHQoKTsgfSBpZihldi5zdG9wUHJvcGFnYXRpb24peyBldi5zdG9wUHJvcGFnYXRpb24oKTsgfSBpZihldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24peyBldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24oKTsgfSB9Y2F0Y2goZSl7fSB9CiAgICByZXR1cm4gZmFsc2U7CiAgfQogIGlmKCFjbGF2ZXNMaXN0YXMoKSl7CiAgICB2YXIgbWM9bWVuc2FqZUNsYXZlKCk7CiAgICBndWFyZGFyQ2xhdmVTZXNpb24oKTsKICAgIG1zZygnenlDbGF2ZU9rJywnQW50ZXMgZGUgY3JlYXIgdHUgWklEOiAnKyhtYy50fHwnZXNjcmliZSBsYSBjbGF2ZSAobWluIDgpIHkgcmVwaXRlbGEgaWd1YWwgZW4gbG9zIGRvcyBjdWFkcm9zLicpLG1jLmN8fCcjYzAwJyk7CiAgICByZXR1cm4gYmxvcXVlYXIoKTsKICB9CiAgLyogdjE2OiBlbCBub21icmUgWUEgTk8gcmVib3RhIGFxdWkuIEFudGVzLCBzaSBlbCBub21icmUgbm8gY2FsemFiYQogICAgIGFsIDEwMCUgY29uIGxhIGxlY3R1cmEgZGVsIGRvY3VtZW50bywgZXN0ZSBndWFyZGlhIHRlIGJvdGFiYSBhbAogICAgIHBhc28gMSBKVVNUTyBhbCBjcmVhciBlbCBaSUQgKHBlcmRpZW5kbyB0b2RvKS4gVHUgbm9tYnJlIHF1ZWRvCiAgICAgY29uZmlybWFkbyBlbiBlbCBwYXNvIDI6IGFxdWkgc29sbyBzZSBhdmlzYSwgbnVuY2Egc2UgcmVncmVzYS4KICAgICBTaSBmYWx0YSBlbCBub21icmUgZGUgdmVyZGFkLCB0ZSBkZWphbW9zIHVuIGJvdG9uIHBhcmEgaXIgZGUKICAgICBmb3JtYSBWT0xVTlRBUklBLCBzaW4gbW92ZXJ0ZSBhIGxhIGZ1ZXJ6YS4gKi8KICBpZighRVNULm5vbWJyZU9rKXsKICAgIG1zZygnenlDbGF2ZU9rJywnRmFsdGEgdHUgbm9tYnJlIGRlbCBwYXNvIDEuIE5vIHRlIG11ZXZvIGRlIGFxdWk6IHVzYSBlbCBib3RvbiBkZSBhYmFqbyBwYXJhIGlyIGEgZXNjcmliaXJsbyBjdWFuZG8gcXVpZXJhcy4nLCcjYTYwJyk7CiAgICBib3RvbklyUGFzbzEoKTsKICAgIHJldHVybiBibG9xdWVhcigpOwogIH0KICBpZihFU1QuZnJlbnRlVGV4dG8pewogICAgdmFyIG5jRj1ub21icmVDb2luY2lkZShFU1QuZXNjcml0bywgRVNULmZyZW50ZVRleHRvLCBmYWxzZSk7CiAgICBpZihuY0YuaGF5ICYmICFuY0Yub2spewogICAgICBtc2coJ3p5Q2xhdmVPaycsJ0F2aXNvOiB0dSBub21icmUgKCcrRVNULmVzY3JpdG8rJykgeSBlbCBkZWwgZG9jdW1lbnRvICgnK25jRi5sZWlkbysnKSBkaWZpZXJlbi4gWWEgbG8gY29uZmlybWFzdGUgZW4gZWwgcGFzbyAyLCBhc2kgcXVlIHNlZ3VpbW9zOiBzZSBjcmVhIHR1IFpJRCBjb24gdHUgbm9tYnJlLicsJyNhNjAnKTsKICAgIH0KICB9CiAgaWYoIUVTVC5mcmVudGVPayl7CiAgICBtc2coJ3N0RicsIEVTVC5mcmVudGVJbWc/J0xhIGZvdG8gZGVsIEZSRU5URSBubyBwYXNcdTAwRjMgbGEgbGVjdHVyYS4gVGUgbGxldm8gYWwgcGFzbyAyIHBhcmEgcmVwZXRpcmxhIChsYXMgZGVtYXMgZm90b3Mgc2UgY29uc2VydmFuKS4nOidGYWx0YSBsYSBmb3RvIGRlbCBGUkVOVEUgZGVsIGRvY3VtZW50by4gVGUgbGxldm8gYWwgcGFzbyAyIHBhcmEgdG9tYXJsYSAobGFzIGRlbWFzIGZvdG9zIHNlIGNvbnNlcnZhbikuJywnI2MwMCcpOwogICAgTU9WTElCUkU9dHJ1ZTsgVy5fX3p5TGlicmVTZXNpb24xOD10cnVlOyBhdmFuemFyKDIpOyBNT1ZMSUJSRT1mYWxzZTsKICAgIHJldHVybiBibG9xdWVhcigpOwogIH0KICBpZihFU1QubmVjZXNpdGFSZXZlcnNvJiYhRVNULnJldmVyc29Payl7CiAgICBtc2coJ3N0QScsIEVTVC5yZXZlcnNvSW1nPydMYSBmb3RvIGRlbCBSRVZFUlNPIG5vIHBhc1x1MDBGMyBsYSBsZWN0dXJhLiBUZSBsbGV2byBhbCBwYXNvIDMgcGFyYSByZXBldGlybGEuJzonRmFsdGEgbGEgZm90byBkZWwgUkVWRVJTTyBkZWwgZG9jdW1lbnRvLiBUZSBsbGV2byBhbCBwYXNvIDMgcGFyYSB0b21hcmxhLicsJyNjMDAnKTsKICAgIE1PVkxJQlJFPXRydWU7IFcuX196eUxpYnJlU2VzaW9uMTg9dHJ1ZTsgYXZhbnphcigzKTsgTU9WTElCUkU9ZmFsc2U7CiAgICByZXR1cm4gYmxvcXVlYXIoKTsKICB9CiAgaWYoIUVTVC5zZWxmaWVJbWcpewogICAgbXNnKCdzdFYnLCdGYWx0YSBsYSBzZWxmaWUuIFRlIGxsZXZvIGFsIHBhc28gNCBwYXJhIHRvbWFybGEuJywnI2MwMCcpOwogICAgTU9WTElCUkU9dHJ1ZTsgVy5fX3p5TGlicmVTZXNpb24xOD10cnVlOyBhdmFuemFyKDQpOyBNT1ZMSUJSRT1mYWxzZTsKICAgIHJldHVybiBibG9xdWVhcigpOwogIH0KICBpZighRVNULnNlbGZpZU9rKXsKICAgIG1zZygnc3RWJywnTGEgc2VsZmllIE5PIHBhc1x1MDBGMyBsYSB2ZXJpZmljYWNpXHUwMEYzbiBmYWNpYWwuIFRlIGxsZXZvIGFsIHBhc28gNCBwYXJhIHJlcGV0aXJsYTogYnVlbmEgbHV6IHkgY2FyYSBjZW50cmFkYSBlbiBlbCBcdTAwRjN2YWxvLicsJyNjMDAnKTsKICAgIE1PVkxJQlJFPXRydWU7IFcuX196eUxpYnJlU2VzaW9uMTg9dHJ1ZTsgYXZhbnphcig0KTsgTU9WTElCUkU9ZmFsc2U7CiAgICByZXR1cm4gYmxvcXVlYXIoKTsKICB9CiAgcmVsbGVuYXJGb3Rvc0Zvcm11bGFyaW8oKTsKICBtc2coJ3p5Q2xhdmVPaycsJ1RvZG8gdmVyaWZpY2FkbzogY3JlYW5kbyB0dSBaSUQuLi4nLCcjMDgwJyk7CiAgcmV0dXJuIHRydWU7Cn0KCi8qID09PT09PT09PT09PT09PT09IHYxMzogYW50aS1ibG9xdWVvIGxlZ2FkbyArIGRpYWdub3N0aWNvIGVuIHZpdm8gPT09PT09PT09PT09PT09PT0KICAgRWwgZXJyb3Igcm9qbyAiRmFsdGEgbGEgZm90byBmcm9udGFsIChwYXNvIDIpIiBOTyBlc3RhIGVuIGVzdGUgbnVjbGVvOiB2aWVuZSBkZQogICBjb2RpZ28gdmllam8gZGUgc3VwZXJhcHAucHkgZnVlcmEgZGVsIGJsb3F1ZSBtYXJjYWRvICh1biBzY3JpcHQgbGVnYWRvIHF1ZQogICByZS12YWxpZGEgYWwgZW52aWFyIHkgYmxvcXVlYSwgbyB0ZXh0byByZXNpZHVhbCBlbiBwYW50YWxsYSkuIEFxdWkgc2UgaGFjZToKICAgMSkgbGltcGlhTGVnYWRvKCk6IGRldGVjdGEgZnVuY2lvbmVzIGdsb2JhbGVzIGN1eW8gY29kaWdvIGNvbnRpZW5lIGVzZSB0ZXh0byB5CiAgICAgIGxhcyB2dWVsdmUgbm8tb3A7IGFkZW1hcyBzZSB0cmFnYSBsb3MgYWxlcnQvY29uZmlybSBjb24gZXNlIHRleHRvLgogICAyKSBwcmVlbXB0RW52aW8oKTogb3llbnRlIGVuIFdJTkRPVyBlbiBmYXNlIGNhcHR1cmEgKHdpbmRvdyBjb3JyZSBBTlRFUyBxdWUKICAgICAgZG9jdW1lbnQgeSBxdWUgZWwgZm9ybSkuIFNpIFRPRE8geWEgcGFzbywgcmVsbGVuYSBsYXMgZm90b3MsIGF2aXNhICJjcmVhbmRvCiAgICAgIHR1IFpJRCIgeSBjb3J0YSBhIGxvcyBveWVudGVzIGxlZ2Fkb3MgY29uIHN0b3BJbW1lZGlhdGVQcm9wYWdhdGlvbiwgZGVqYW5kbwogICAgICBxdWUgZWwgZW52aW8gbmF0aXZvIGRlbCBmb3JtdWxhcmlvIHNpZ2EuIFNpIGZhbHRhIGFsZ28sIG5vIHRvY2EgbmFkYS4KICAgMykgYmFycmVNZW5zYWplcygpOiBib3JyYSB0ZXh0b3Mgcm9qb3MgcmVzaWR1YWxlcyB5IHJlLWhhYmlsaXRhIGJvdG9uZXMKICAgICAgZGVzaGFiaWxpdGFkb3MgU09MTyBjdWFuZG8gdG9kbyB5YSBwYXNvLgogICA0KSBwYW5lbERpYWcoKTogYm90b24gImkiIGZpam8gYWJham8gYSBsYSBkZXJlY2hhOyBtdWVzdHJhIHF1ZSBibG9xdWVhLCBsb3MKICAgICAgY2FtcG9zIGRlbCBmb3JtdWxhcmlvLCBlbCBhY3Rpb24vbWV0aG9kIHkgbGFzIGZ1bmNpb25lcyBsZWdhZGFzIGhhbGxhZGFzLgoqLwp2YXIgRElBRz17bGVnYWRvOltdLGFsZXJ0YXM6MCx1bHRTdWJtaXQ6JycsdWx0Q2xpY2s6Jyd9OwovKiB2MTY6IFRYX1JPSkEgYW1wbGlhZGEuIEFkZW1hcyBkZWwgdGV4dG8gdmllam8gIkZhbHRhIGxhIGZvdG8gZnJvbnRhbAogICAocGFzbyAyKSIsIGFob3JhIGNhemEgbG9zIHRleHRvcyBkZWwgY29udHJvbCBkZSBub21icmUgZGVsIGNvZGlnbwogICBsZWdhZG8gKCJMb3Mgbm9tYnJlcyBkZWwgZG9jdW1lbnRvIC4uLiBubyBjb2luY2lkZW4gY29uIGVsIG5vbWJyZQogICAuLi4iLCAiY29ycmlnZSAuLi4gcGFzbyAxIikuIENvbiBlc28gbGltcGlhTGVnYWRvIHRhbWJpZW4gbmV1dHJhbGl6YQogICBsYXMgZnVuY2lvbmVzIGRlbCBsZWdhZG8gcXVlIGJvdGFiYW4gYWwgdXN1YXJpbyBhbCBpbmljaW8gcG9yIGVsCiAgIG5vbWJyZS4gKi8KdmFyIFRYX1JPSkE9L2ZhbHRhLnswLDI0fWZyb250YWx8ZnJvbnRhbC57MCwyNH1wYXNvXHMqMnxub21icmVzP1xzK2RlbFxzK2RvY3VtZW50b3xub1xzK2NvaW5jaWRlW25dP1xzK2NvblxzK2VsXHMrbm9tYnJlfGNvcnJpZ2UuezAsMjR9cGFzb1xzKjEvaTsKdmFyIE1JT1NfSURTPXsnenlSZXN1bWVuNSc6MSwnenlDbGF2ZU9rJzoxLCd6eUd1YXJkaWEnOjEsJ3p5RXJyTm9tYnJlJzoxLCd6eUVyclRpcG8nOjEsJ3p5TGVjTXNnJzoxLCd6eUxlY0JveCc6MSwnc3RGJzoxLCdzdEEnOjEsJ3N0Vic6MX07CmZ1bmN0aW9uIGhvcmExMygpewogIHRyeXsgcmV0dXJuIChuZXcgRGF0ZSgpKS50b0lTT1N0cmluZygpLnNsaWNlKDExLDE5KTsgfWNhdGNoKGUpeyByZXR1cm4gJyc7IH0KfQpmdW5jdGlvbiB0b2RvT2tQYXJhQ3JlYXIoKXsKICBpZighY2xhdmVzTGlzdGFzKCkpeyByZXR1cm4gZmFsc2U7IH0KICBpZighRVNULm5vbWJyZU9rKXsgcmV0dXJuIGZhbHNlOyB9CiAgaWYoIUVTVC5mcmVudGVPayl7IHJldHVybiBmYWxzZTsgfQogIGlmKEVTVC5uZWNlc2l0YVJldmVyc28mJiFFU1QucmV2ZXJzb09rKXsgcmV0dXJuIGZhbHNlOyB9CiAgaWYoIUVTVC5zZWxmaWVJbWd8fCFFU1Quc2VsZmllT2speyByZXR1cm4gZmFsc2U7IH0KICAvKiB2MTY6IHlhIE5PIHNlIHJlLXZhbGlkYSBlbCBub21icmUgYXF1aSAoZXJhIGxhIGNhdXNhIGV4YWN0YSBkZWwKICAgICByZWJvdGUganVzdG8gYWwgdG9jYXIgZWwgYm90b24gZGUgY3JlYXIgZWwgWklEKS4gRWwgbm9tYnJlIHF1ZWRvCiAgICAgY2VycmFkbyBlbiBlbCBwYXNvIDIgY29uIHN1IHBhbmVsIGRlIGxlY3R1cmEuICovCiAgcmV0dXJuIHRydWU7Cn0KZnVuY3Rpb24gbGltcGlhTGVnYWRvKCl7CiAgdmFyIG5vbWJyZXM9W107CiAgdHJ5ewogICAgdmFyIGtzPU9iamVjdC5nZXRPd25Qcm9wZXJ0eU5hbWVzKFcpOwogICAgZm9yKHZhciBpPTA7aTxrcy5sZW5ndGg7aSsrKXsKICAgICAgdmFyIGs9a3NbaV07CiAgICAgIHRyeXsKICAgICAgICB2YXIgdj1XW2tdOwogICAgICAgIGlmKHR5cGVvZiB2PT09J2Z1bmN0aW9uJyYmdi50b1N0cmluZyYmVFhfUk9KQS50ZXN0KHYudG9TdHJpbmcoKSkmJmshPT0nbGltcGlhTGVnYWRvJyl7CiAgICAgICAgICBub21icmVzLnB1c2goayk7CiAgICAgICAgICBXW2tdPWZ1bmN0aW9uKCl7fTsKICAgICAgICB9CiAgICAgIH1jYXRjaChlKXt9CiAgICB9CiAgfWNhdGNoKGUpe30KICB0cnl7CiAgICAgIGlmKHR5cGVvZiBXLmFsZXJ0PT09J2Z1bmN0aW9uJyYmIVcuX196eUFsZXJ0MTYpewogICAgICB2YXIgYTA9Vy5hbGVydDsKICAgICAgVy5hbGVydD1mdW5jdGlvbihtKXsgaWYoVFhfUk9KQS50ZXN0KFN0cmluZyhtPT1udWxsPycnOm0pKSl7IERJQUcuYWxlcnRhcysrOyByZXR1cm47IH0gcmV0dXJuIGEwLmFwcGx5KFcsYXJndW1lbnRzKTsgfTsKICAgICAgVy5fX3p5QWxlcnQxNj10cnVlOwogICAgfQogICAgaWYodHlwZW9mIFcuY29uZmlybT09PSdmdW5jdGlvbicmJiFXLl9fenlDb25maXJtMTYpewogICAgICB2YXIgYzA9Vy5jb25maXJtOwogICAgICBXLmNvbmZpcm09ZnVuY3Rpb24obSl7IGlmKFRYX1JPSkEudGVzdChTdHJpbmcobT09bnVsbD8nJzptKSkpeyBESUFHLmFsZXJ0YXMrKzsgcmV0dXJuIHRydWU7IH0gcmV0dXJuIGMwLmFwcGx5KFcsYXJndW1lbnRzKTsgfTsKICAgICAgVy5fX3p5Q29uZmlybTE2PXRydWU7CiAgICB9CiAgfWNhdGNoKGUpe30KICBESUFHLmxlZ2Fkbz1ub21icmVzOwogIGlmKG5vbWJyZXMubGVuZ3RoKXsgbG9nKCd2MTY6IGZ1bmNpb25lcyBsZWdhZGFzIG5ldXRyYWxpemFkYXM6Jywgbm9tYnJlcy5qb2luKCcsJykpOyB9Cn0KZnVuY3Rpb24gYmFycmVNZW5zYWplcygpewogIGlmKCF0b2RvT2tQYXJhQ3JlYXIoKSl7IHJldHVybjsgfQogIHRyeXsKICAgIHZhciBub2Rlcz1kb2N1bWVudC5ib2R5P2RvY3VtZW50LmJvZHkucXVlcnlTZWxlY3RvckFsbCgnZGl2LHNwYW4scCxsaSxzZWN0aW9uJyk6W107CiAgICBmb3IodmFyIGk9MDtpPG5vZGVzLmxlbmd0aCYmaTw4MDA7aSsrKXsKICAgICAgdmFyIGVsPW5vZGVzW2ldOwogICAgICBpZighZWx8fGVsLmlkPT09J3p5RGlhZzE2J3x8TUlPU19JRFNbZWwuaWRdKXsgY29udGludWU7IH0KICAgICAgLyogdjE2OiBDT1JSRUNDSU9OIElNUE9SVEFOVEUuIEFudGVzIHNlIGxpbXBpYWJhIGN1YWxxdWllciBjb250ZW5lZG9yCiAgICAgICAgIGN1eW8gdGV4dG8gZGlqZXJhICJGYWx0YSBsYSBmb3RvIGZyb250YWwuLi4iIC0geSBlbCBwcm9waW8gcHM1CiAgICAgICAgIChxdWUgY29udGllbmUgZWwgZm9ybXVsYXJpbyB5IGVsIGJvdG9uIGRlIGNyZWFyIGVsIFpJRCkgcG9kaWEKICAgICAgICAgcXVlZGFyIGJhcnJpZG86IHRleHRDb250ZW50PScnIEJPUlJBIGxvcyBoaWpvcywgbyBzZWEgcXVlIGVsCiAgICAgICAgIGZvcm11bGFyaW8gZGVzYXBhcmVjaWEganVzdG8gY3VhbmRvIHRvZG8gZXN0YWJhIGxpc3RvLiBBaG9yYSB1bgogICAgICAgICBjb250ZW5lZG9yIGNvbiBmb3JtdWxhcmlvL2lucHV0cy9ib3RvbmVzIE5VTkNBIHNlIHRvY2E6IHNvbG8gc2UKICAgICAgICAgbGltcGlhbiBsb3MgYXZpc29zIGhvamEgKGRpdnMgZGUgdGV4dG8gc3VlbHRvKS4gKi8KICAgICAgaWYoL15wc1sxLTVdJC8udGVzdChlbC5pZHx8JycpKXsgY29udGludWU7IH0KICAgICAgdHJ5eyBpZihlbC5xdWVyeVNlbGVjdG9yJiZlbC5xdWVyeVNlbGVjdG9yKCdmb3JtLGlucHV0LGJ1dHRvbixzZWxlY3QsdGV4dGFyZWEnKSl7IGNvbnRpbnVlOyB9IH1jYXRjaChlUSl7fQogICAgICB2YXIgdD1lbC50ZXh0Q29udGVudHx8Jyc7CiAgICAgIGlmKFRYX1JPSkEudGVzdCh0KSYmdC5sZW5ndGg8MzAwKXsKICAgICAgICBlbC50ZXh0Q29udGVudD0nJzsKICAgICAgICBpZihlbC5zdHlsZSl7IGVsLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9CiAgICAgIH0KICAgIH0KICB9Y2F0Y2goZSl7fQogIHRyeXsKICAgIHZhciBwczU9JCgncHM1Jyk7CiAgICBpZihwczUpewogICAgICB2YXIgYnM9cHM1LnF1ZXJ5U2VsZWN0b3JBbGwoJ2J1dHRvbiwgaW5wdXRbdHlwZT1zdWJtaXRdJyk7CiAgICAgIGZvcih2YXIgaz0wO2s8YnMubGVuZ3RoO2srKyl7IGlmKGJzW2tdLmRpc2FibGVkKXsgYnNba10uZGlzYWJsZWQ9ZmFsc2U7IH0gfQogICAgfQogIH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gcGludGFEaWFnKCl7CiAgdmFyIGI9JCgnenlEaWFnMTYnKTsKICBpZighYnx8Yi5zdHlsZS5kaXNwbGF5PT09J25vbmUnKXsgcmV0dXJuOyB9CiAgdmFyIEw9W107CiAgTC5wdXNoKCdudWNsZW86IFJFViBGIHYxOCBhY3Rpdm8nKTsKICBMLnB1c2goJ2VzdGFkbzogbm9tYnJlT2s9JytFU1Qubm9tYnJlT2srJyBmcmVudGVPaz0nK0VTVC5mcmVudGVPaysnIHJldmVyc29Paz0nK0VTVC5yZXZlcnNvT2srJyAobmVjZXNpdGFSZXZlcnNvPScrRVNULm5lY2VzaXRhUmV2ZXJzbysnKSBzZWxmaWVPaz0nK0VTVC5zZWxmaWVPaysnIHBhc289JytFU1QucGFzbysnIHBhc29NYXg9JysoRVNULnBhc29NYXh8fDEpKTsKICBMLnB1c2goJ3RvZG9Pa1BhcmFDcmVhcjogJysodG9kb09rUGFyYUNyZWFyKCk/J1NJJzonTk8nKSk7CiAgTC5wdXNoKCdjbGF2ZXM6IG1vZG89JysoQ0xWLm1vZG98fDApKycgY3VhZHJvMT0nKyhDTFYuYT8oKChDTFYuYS52YWx1ZXx8JycpLmxlbmd0aCk/KCdPSygnK0NMVi5hLnZhbHVlLmxlbmd0aCsnKScpOidWQUNJTycpOicobm8gaGFsbGFkbyknKSsnIGN1YWRybzI9JysoQ0xWLmI/KCgoQ0xWLmIudmFsdWV8fCcnKS5sZW5ndGgpPygnT0soJytDTFYuYi52YWx1ZS5sZW5ndGgrJyknKTonVkFDSU8nKTooQ0xWLm1vZG89PT0xPycobm8gcmVxdWVyaWRvKSc6JyhubyBoYWxsYWRvKScpKSk7CiAgTC5wdXNoKCdjbGF2ZSByZXNwYWxkYWRhIGVuIHNlc2lvbjogJysoZnVuY3Rpb24oKXsgdHJ5eyB2YXIgcz1zZXNzaW9uU3RvcmFnZS5nZXRJdGVtKEtTRVNNKTsgaWYoIXMpeyByZXR1cm4gJ05PJzsgfSB2YXIgZD1KU09OLnBhcnNlKHMpfHx7fTsgcmV0dXJuICdTSSAoJysoKGQuYzF8fCcnKS5sZW5ndGgpKycrJysoKGQuYzJ8fCcnKS5sZW5ndGgpKycgY2FyYWN0ZXJlcyknOyB9Y2F0Y2goZSl7IHJldHVybiAnPyc7IH0gfSkoKSk7CiAgTC5wdXNoKCdaSUQ6ICcrKGhheUV4aXRvKCk/KCdDUkVBRE8nKyhmdW5jdGlvbigpeyB0cnl7IHZhciBjPWxvY2FsU3RvcmFnZS5nZXRJdGVtKCd6eVppZENvZGlnbzE3Jyk7IHJldHVybiBjPygnICgnK2MrJyknKTonJzsgfWNhdGNoKGUyKXsgcmV0dXJuICcnOyB9IH0pKCkpOidwZW5kaWVudGUnKSk7CiAgTC5wdXNoKCdyZXNwYWxkbzogJysoVy5fX3p5UmVzY2F0YWRvMTY/J1JFQ1VQRVJBRE8gYWwgYWJyaXInOidndWFyZGFkbyBlbiBlc3RlIHRlbGVmb25vJykrJyB8IHJlZW52aW9zIHRyYXMgcmVib3RlOiAnKyhmdW5jdGlvbigpeyB0cnl7IHJldHVybiBsb2NhbFN0b3JhZ2UuZ2V0SXRlbSgnenlSZWJvdGVzMTYnKXx8JzAnOyB9Y2F0Y2goZSl7IHJldHVybiAnPyc7IH0gfSkoKSk7CiAgTC5wdXNoKCdsZWdhZG8gbmV1dHJhbGl6YWRvOiAnKyhESUFHLmxlZ2Fkby5sZW5ndGg/RElBRy5sZWdhZG8uam9pbignLCAnKTonKG5pbmd1bmEgZnVuY2lvbiBjb24gZWwgdGV4dG8gcm9qbyknKSk7CiAgTC5wdXNoKCdhbGVydGFzIHJvamFzIHRyYWdhZGFzOiAnK0RJQUcuYWxlcnRhcyk7CiAgdmFyIGY9bnVsbDsKICB0cnl7IHZhciBwczU9JCgncHM1Jyk7IGY9cHM1PyhwczUucXVlcnlTZWxlY3RvcignZm9ybScpfHxkb2N1bWVudC5xdWVyeVNlbGVjdG9yKCdmb3JtJykpOm51bGw7IH1jYXRjaChlKXt9CiAgaWYoZil7CiAgICBMLnB1c2goJ2Zvcm0gYWN0aW9uOiAnKyhmLmdldEF0dHJpYnV0ZSgnYWN0aW9uJyl8fCcoZXN0YSBtaXNtYSBwYWdpbmEpJykrJyAgbWV0aG9kOiAnKygoKGYubWV0aG9kfHwnZ2V0JykrJycpLnRvVXBwZXJDYXNlKCkpKTsKICAgIHRyeXsKICAgICAgdmFyIGVscz1mLmVsZW1lbnRzLCB2aXM9W107CiAgICAgIGZvcih2YXIgaT0wO2k8ZWxzLmxlbmd0aCYmdmlzLmxlbmd0aDwxNjtpKyspewogICAgICAgIHZhciBlbD1lbHNbaV07CiAgICAgICAgaWYoIWVsfHwhZWwubmFtZSl7IGNvbnRpbnVlOyB9CiAgICAgICAgdmlzLnB1c2goZWwubmFtZSsnPScrKCgoZWwudmFsdWV8fCcnKS5sZW5ndGg+MCk/KCdPSygnK2VsLnZhbHVlLmxlbmd0aCsnKScpOidWQUNJTycpKTsKICAgICAgfQogICAgICBMLnB1c2goJ2NhbXBvczogJysodmlzLmpvaW4oJyB8ICcpfHwnKG5pbmd1bm8gY29uIG5hbWUpJykpOwogICAgfWNhdGNoKGUpe30KICB9ZWxzZXsKICAgIEwucHVzaCgnZm9ybTogTk8gaGF5IDxmb3JtPiAoZWwgbGVnYWRvIGNyZWEgZWwgWklEIHBvciBKUy9mZXRjaCknKTsKICB9CiAgdHJ5ewogICAgdmFyIGNhbmQ9ZG9jdW1lbnQucXVlcnlTZWxlY3RvckFsbCgnW29uY2xpY2tdLFtvbnN1Ym1pdF0nKTsKICAgIHZhciBoaXRzPVtdOwogICAgZm9yKHZhciBqPTA7ajxjYW5kLmxlbmd0aCYmaGl0cy5sZW5ndGg8NDtqKyspewogICAgICB2YXIgYz1jYW5kW2pdOwogICAgICB2YXIgcz0oKGMuZ2V0QXR0cmlidXRlKCdvbmNsaWNrJyl8fCcnKSsnICcrKGMuZ2V0QXR0cmlidXRlKCdvbnN1Ym1pdCcpfHwnJykpLnRyaW0oKTsKICAgICAgaWYoVFhfUk9KQS50ZXN0KHMpKXsgaGl0cy5wdXNoKCgoYy5pZHx8Yy50YWdOYW1lKXx8Jz8nKSsnOiAnK3MucmVwbGFjZSgvXHMrL2csJyAnKS5zbGljZSgwLDE1MCkpOyB9CiAgICB9CiAgICBpZihoaXRzLmxlbmd0aCl7CiAgICAgIEwucHVzaCgndmFsaWRhY2lvbiBsZWdhZGEgZW4gYXRyaWJ1dG9zOicpOwogICAgICBmb3IodmFyIHE9MDtxPGhpdHMubGVuZ3RoO3ErKyl7IEwucHVzaCgnICAnK2hpdHNbcV0pOyB9CiAgICB9CiAgfWNhdGNoKGUpe30KICB0cnl7CiAgICB2YXIgVVI9bG9jYWxTdG9yYWdlLmdldEl0ZW0oJ3p5VWx0aW1hUmVzcHVlc3RhMTYnKTsKICAgIGlmKFVSKXsgTC5wdXNoKCdyZXNwdWVzdGEgZGVsIHNlcnZpZG9yIChpbmljaW8pOiAnK1VSLnNsaWNlKDAsMjYwKSk7IH0KICB9Y2F0Y2goZSl7fQogIGlmKERJQUcudWx0Q2xpY2speyBMLnB1c2goJ3VsdGltbyBjbGljazogJytESUFHLnVsdENsaWNrKTsgfQogIGlmKERJQUcudWx0U3VibWl0KXsgTC5wdXNoKCd1bHRpbW8gc3VibWl0OiAnK0RJQUcudWx0U3VibWl0KTsgfQogIGIudGV4dENvbnRlbnQ9TC5qb2luKCdcbicpOwp9CmZ1bmN0aW9uIHBhbmVsRGlhZygpewogIHRyeXsKICAgIGlmKCQoJ3p5RGlhZzE2JykpeyByZXR1cm47IH0KICAgIHZhciBjaGlwPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgY2hpcC5pZD0nenlEaWFnQ2hpcDE2JzsKICAgIGNoaXAuc3R5bGUuY3NzVGV4dD0ncG9zaXRpb246Zml4ZWQ7cmlnaHQ6MTBweDtib3R0b206MTBweDt6LWluZGV4OjIxNDc0ODM2NDY7d2lkdGg6MzBweDtoZWlnaHQ6MzBweDtib3JkZXItcmFkaXVzOjUwJTtiYWNrZ3JvdW5kOiMxMTE7Y29sb3I6IzBmMDtmb250OmJvbGQgMTVweC8zMHB4IG1vbm9zcGFjZTt0ZXh0LWFsaWduOmNlbnRlcjtjdXJzb3I6cG9pbnRlcjtvcGFjaXR5Oi41O2JveC1zaGFkb3c6MCAxcHggNHB4IHJnYmEoMCwwLDAsLjQpOyc7CiAgICBjaGlwLnRleHRDb250ZW50PSdpJzsKICAgIGNoaXAudGl0bGU9J2RpYWdub3N0aWNvIHYxOCc7CiAgICBjaGlwLmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbigpewogICAgICB2YXIgYj0kKCd6eURpYWcxNicpOwogICAgICBpZighYil7IHJldHVybjsgfQogICAgICB2YXIgdmlzaWJsZT0oYi5zdHlsZS5kaXNwbGF5PT09J25vbmUnKTsKICAgICAgYi5zdHlsZS5kaXNwbGF5PXZpc2libGU/J2Jsb2NrJzonbm9uZSc7CiAgICAgIGlmKHZpc2libGUpeyBwaW50YURpYWcoKTsgfQogICAgfSk7CiAgICB2YXIgYm94PWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ3ByZScpOwogICAgYm94LmlkPSd6eURpYWcxNic7CiAgICBib3guc3R5bGUuY3NzVGV4dD0nZGlzcGxheTpub25lO3Bvc2l0aW9uOmZpeGVkO2xlZnQ6OHB4O3JpZ2h0OjhweDtib3R0b206NDhweDt6LWluZGV4OjIxNDc0ODM2NDU7bWF4LWhlaWdodDo1NSU7b3ZlcmZsb3c6YXV0bztiYWNrZ3JvdW5kOiMwYjBiMGI7Y29sb3I6IzBmMDtmb250OjExcHgvMS40NSBtb25vc3BhY2U7cGFkZGluZzoxMHB4O2JvcmRlci1yYWRpdXM6OHB4O3doaXRlLXNwYWNlOnByZS13cmFwO3dvcmQtYnJlYWs6YnJlYWstYWxsO2JveC1zaGFkb3c6MCA0cHggMTZweCByZ2JhKDAsMCwwLC41KTttYXJnaW46MDsnOwogICAgYm94LnRleHRDb250ZW50PSdudWNsZW86IFJFViBGIHYxOCc7CiAgICBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKGJveCk7CiAgICBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKGNoaXApOwogIH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gcHJlZW1wdEVudmlvKCl7CiAgVy5hZGRFdmVudExpc3RlbmVyKCdzdWJtaXQnLGZ1bmN0aW9uKGV2KXsKICAgIHRyeXsKICAgICAgdmFyIGY9ZXYudGFyZ2V0OwogICAgICBpZighZnx8IWYudGFnTmFtZXx8Zi50YWdOYW1lIT09J0ZPUk0nKXsgcmV0dXJuOyB9CiAgICAgIERJQUcudWx0U3VibWl0PWhvcmExMygpKycgJysoZi5nZXRBdHRyaWJ1dGUoJ2FjdGlvbicpfHwnKGVzdGEgbWlzbWEgcGFnaW5hKScpKycgWycrKCgoZi5tZXRob2R8fCdnZXQnKSsnJykudG9VcHBlckNhc2UoKSkrJ10nOwogICAgICB2YXIgcHM1PSQoJ3BzNScpOwogICAgICBpZihwczUmJnBzNS5jb250YWlucyhmKSYmdG9kb09rUGFyYUNyZWFyKCkpewogICAgICAgIHJlbGxlbmFyRm90b3NGb3JtdWxhcmlvKCk7CiAgICAgICAgYmFycmVNZW5zYWplcygpOwogICAgICAgIGd1YXJkYXJDbGF2ZVNlc2lvbigpOwogICAgICAgIG1zZygnenlDbGF2ZU9rJywnVG9kbyB2ZXJpZmljYWRvOiBjcmVhbmRvIHR1IFpJRC4uLicsJyMwODAnKTsKICAgICAgICBwaW50YURpYWcoKTsKICAgICAgICAvKiB2MTc6IGVsIGVudmlvIHByb3RlZ2lkbyBwb3IgZmV0Y2ggdmEgREVTREUgRUwgUFJJTUVSIGludGVudG8KICAgICAgICAgICAoYW50ZXMgc29sbyB0cmFzIHVuIHJlYm90ZSkuIFNpIGVsIHNlcnZpZG9yIGRldnVlbHZlIGVsCiAgICAgICAgICAgZm9ybXVsYXJpbywgTk8gc2UgcmVjYXJnYSBsYSBwYWdpbmE6IHRlIHF1ZWRhcyBlbiBlbCBwYXNvIDUKICAgICAgICAgICBjb24gbGEgY2xhdmUgZXNjcml0YSB5IHRvZG8gaW50YWN0bywgeSBsYSByZXNwdWVzdGEgY3J1ZGEKICAgICAgICAgICBxdWVkYSBlbiBlbCBwYW5lbCAiaSIuIFNpIGVsIHNlcnZpZG9yIGNyZWEgZWwgWklELCBhcGFyZWNlCiAgICAgICAgICAgbGEgcGFudGFsbGEgZGUgZXhpdG8gY29uIHR1IFpJRC4gKi8KICAgICAgICBpZihXLmZldGNoKXsKICAgICAgICAgIC8qIHYxNzogZG9ibGUgdG9xdWUgcmFwaWRvIC0+IHNlIGlnbm9yYSBlbCBzZWd1bmRvIGVudmlvIChubwogICAgICAgICAgICAgaGF5IHNlZ3VuZG8gc3VibWl0IG5hdGl2byBtaWVudHJhcyBlbCBmZXRjaCBlc3RhIGVuIHZ1ZWxvKS4gKi8KICAgICAgICAgIGlmKFcuX196eUVudmlhbmRvMTcpewogICAgICAgICAgICB0cnl7IGlmKGV2LnByZXZlbnREZWZhdWx0KXsgZXYucHJldmVudERlZmF1bHQoKTsgfSB9Y2F0Y2goZVAyKXt9CiAgICAgICAgICAgIGlmKGV2LnN0b3BJbW1lZGlhdGVQcm9wYWdhdGlvbil7IGV2LnN0b3BJbW1lZGlhdGVQcm9wYWdhdGlvbigpOyB9CiAgICAgICAgICAgIHJldHVybjsKICAgICAgICAgIH0KICAgICAgICAgIFcuX196eUVudmlhbmRvMTc9dHJ1ZTsKICAgICAgICAgIHRyeXsgaWYoZXYucHJldmVudERlZmF1bHQpeyBldi5wcmV2ZW50RGVmYXVsdCgpOyB9IH1jYXRjaChlUCl7fQogICAgICAgICAgZW52aWFyUG9yRmV0Y2goZik7CiAgICAgICAgICBpZihldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24peyBldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24oKTsgfQogICAgICAgICAgcmV0dXJuOwogICAgICAgIH0KICAgICAgICBpZihldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24peyBldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24oKTsgfQogICAgICB9CiAgICB9Y2F0Y2goZSl7fQogIH0sdHJ1ZSk7CiAgVy5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oZXYpewogICAgdHJ5ewogICAgICB2YXIgcHM1PSQoJ3BzNScpLCBlbD1ldi50YXJnZXQ7CiAgICAgIGlmKCFwczV8fCFlbHx8IXBzNS5jb250YWlucyhlbCkpeyByZXR1cm47IH0KICAgICAgdmFyIGI9ZWwsIGVzQm90b249ZmFsc2UsIHByb2Y9MDsKICAgICAgd2hpbGUoYiYmYiE9PXBzNSYmcHJvZjw2KXsKICAgICAgICB2YXIgdGc9Yi50YWdOYW1lfHwnJzsKICAgICAgICBpZih0Zz09PSdCVVRUT04nfHwodGc9PT0nSU5QVVQnJiYoKChiLnR5cGV8fCcnKT09PSdzdWJtaXQnKXx8KChiLnR5cGV8fCcnKT09PSdpbWFnZScpKSl8fChiLmdldEF0dHJpYnV0ZSYmYi5nZXRBdHRyaWJ1dGUoJ3JvbGUnKT09PSdidXR0b24nKSl7IGVzQm90b249dHJ1ZTsgYnJlYWs7IH0KICAgICAgICBiPWIucGFyZW50Tm9kZTsgcHJvZisrOwogICAgICB9CiAgICAgIGlmKCFlc0JvdG9ufHwhYil7IHJldHVybjsgfQogICAgICB2YXIgdHk9KGIudGFnTmFtZT09PSdCVVRUT04nKT8oKChiLmdldEF0dHJpYnV0ZSgndHlwZScpKXx8J3N1Ym1pdCcpKycnKS50b0xvd2VyQ2FzZSgpOigoKGIudHlwZXx8JycpKycnKS50b0xvd2VyQ2FzZSgpKTsKICAgICAgdmFyIGVuRm9ybT1mYWxzZSwgcD1iOwogICAgICB3aGlsZShwKXsgaWYocC50YWdOYW1lPT09J0ZPUk0nKXsgZW5Gb3JtPXRydWU7IGJyZWFrOyB9IHA9cC5wYXJlbnROb2RlOyB9CiAgICAgIERJQUcudWx0Q2xpY2s9aG9yYTEzKCkrJyAnKyhiLmlkfHxiLnRhZ05hbWUpKycgdHlwZT0nK3R5KycgZm9ybT0nKyhlbkZvcm0/J3NpJzonbm8nKTsKICAgICAgaWYodHk9PT0nc3VibWl0JyYmZW5Gb3JtJiZ0b2RvT2tQYXJhQ3JlYXIoKSl7CiAgICAgICAgcmVsbGVuYXJGb3Rvc0Zvcm11bGFyaW8oKTsKICAgICAgICBiYXJyZU1lbnNhamVzKCk7CiAgICAgICAgZ3VhcmRhckNsYXZlU2VzaW9uKCk7CiAgICAgICAgLyogdjE4OiB5YSBOTyBjb3J0YW1vcyBlbCBjbGljayBjb24gc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uOiBlbCBjb2RpZ28KICAgICAgICAgICB2aWVqbyBwdWVkZSByZWxsZW5hciBjYW1wb3Mgb2N1bHRvcyBpbXBvcnRhbnRlcyBlbiBzdSBwcm9waW8gb25jbGljawogICAgICAgICAgICh5IHNpIGxsYW1hIGZvcm0uc3VibWl0KCksIGVsIGVudm9sdmVudGUgdjE4IGxvIHRvbWEgaWd1YWwpLiBTaSBlbgogICAgICAgICAgIDYwMCBtcyBuYWRhIGluaWNpbyBlbCBlbnZpbywgbG8gbGFuemFtb3Mgbm9zb3Ryb3MgcG9yIGVsIGNhbmFsCiAgICAgICAgICAgcHJvdGVnaWRvIChjdWJyZSBvbmNsaWNrIHF1ZSBoYWNlbiBwcmV2ZW50RGVmYXVsdCB5IG5vIGVudmlhbikuICovCiAgICAgICAgYXJtYXJSZWVudmlvMTgoKTsKICAgICAgfQogICAgfWNhdGNoKGUpe30KICB9LHRydWUpOwogIC8qIHYxODogZWwgY29kaWdvIHZpZWpvIGEgdmVjZXMgbGxhbWEgZm9ybS5zdWJtaXQoKSBESVJFQ1RPIChzaW4gZXZlbnRvIHN1Ym1pdCk6CiAgICAgZXNvIHNlIHNhbHRhYmEgVE9ETyBlbCBjYW5hbCBwcm90ZWdpZG8geSBlbCBlbnZpbyBzZSBpYmEgInBlbGFkbyIgYWwgc2Vydmlkb3IKICAgICAoY29uIGxhIHJlc3B1ZXN0YSBkZSByZWN1cGVyYXIgY2xhdmUgZW5jaW1hIGRlIHR1IHJlZ2lzdHJvKS4gQWhvcmEgZXNhIGxsYW1hZGEKICAgICB0YW1iaWVuIHBhc2EgcG9yIGVsIGNhbmFsIHByb3RlZ2lkbyBjdWFuZG8gdG9kbyBlc3RhIGxpc3RvLiAqLwogIHRyeXsKICAgIGlmKCFXLl9fenlTdWJtaXQxOCYmVy5IVE1MRm9ybUVsZW1lbnQmJlcuSFRNTEZvcm1FbGVtZW50LnByb3RvdHlwZSYmVy5IVE1MRm9ybUVsZW1lbnQucHJvdG90eXBlLnN1Ym1pdCl7CiAgICAgIHZhciBvcmlnU3VibWl0PVcuSFRNTEZvcm1FbGVtZW50LnByb3RvdHlwZS5zdWJtaXQ7CiAgICAgIFcuSFRNTEZvcm1FbGVtZW50LnByb3RvdHlwZS5zdWJtaXQ9ZnVuY3Rpb24oKXsKICAgICAgICB0cnl7CiAgICAgICAgICB2YXIgcHM1PSQoJ3BzNScpOwogICAgICAgICAgaWYodGhpcyYmdGhpcy50YWdOYW1lPT09J0ZPUk0nJiZwczUmJnBzNS5jb250YWlucyh0aGlzKSYmIXRoaXMuX196eU5hdGl2bzE4JiZ0b2RvT2tQYXJhQ3JlYXIoKSYmVy5mZXRjaCYmIVcuX196eUVudmlhbmRvMTcpewogICAgICAgICAgICByZWxsZW5hckZvdG9zRm9ybXVsYXJpbygpOwogICAgICAgICAgICBiYXJyZU1lbnNhamVzKCk7CiAgICAgICAgICAgIGd1YXJkYXJDbGF2ZVNlc2lvbigpOwogICAgICAgICAgICBtc2coJ3p5Q2xhdmVPaycsJ1RvZG8gdmVyaWZpY2FkbzogY3JlYW5kbyB0dSBaSUQuLi4nLCcjMDgwJyk7CiAgICAgICAgICAgIFcuX196eUVudmlhbmRvMTc9dHJ1ZTsKICAgICAgICAgICAgZW52aWFyUG9yRmV0Y2godGhpcyk7CiAgICAgICAgICAgIHJldHVybiB1bmRlZmluZWQ7CiAgICAgICAgICB9CiAgICAgICAgfWNhdGNoKGVXMil7fQogICAgICAgIHJldHVybiBvcmlnU3VibWl0LmFwcGx5KHRoaXMsYXJndW1lbnRzKTsKICAgICAgfTsKICAgICAgVy5fX3p5U3VibWl0MTg9dHJ1ZTsKICAgIH0KICB9Y2F0Y2goZVMzKXt9Cn0KLyogdjE4OiByZWVudmlvIGRlIHNlZ3VyaWRhZDogc2kgZWwgY2xpY2sgZGVsIGJvdG9uIG5vIGFjYWJvIGRlIGluaWNpYXIgTklOR1VOCiAgIGVudmlvIChuaSBmZXRjaCBlbiB2dWVsbywgbmkgcmVjaWVudGUpLCBsbyBsYW56YSBlbCBudWNsZW8gcG9yIGVsIGNhbmFsCiAgIHByb3RlZ2lkby4gQ3VicmUgb25jbGljayB2aWVqb3MgcXVlIGhhY2VuIHByZXZlbnREZWZhdWx0IHkgbm8gZW52aWFuLiAqLwpmdW5jdGlvbiBhcm1hclJlZW52aW8xOCgpewogIHRyeXsKICAgIGlmKFcuX196eUVudkZhbGxiYWNrMTgpeyByZXR1cm47IH0KICAgIFcuX196eUVudkZhbGxiYWNrMTg9dHJ1ZTsKICAgIHNldFRpbWVvdXQoZnVuY3Rpb24oKXsKICAgICAgdHJ5ewogICAgICAgIFcuX196eUVudkZhbGxiYWNrMTg9ZmFsc2U7CiAgICAgICAgaWYoVy5fX3p5RW52aWFuZG8xNyl7IHJldHVybjsgfQogICAgICAgIGlmKChEYXRlLm5vdygpLShXLl9fenlVbHRpbW9FbnZpbzE4fHwwKSk8NDAwMCl7IHJldHVybjsgfQogICAgICAgIGlmKCF0b2RvT2tQYXJhQ3JlYXIoKSl7IHJldHVybjsgfQogICAgICAgIHZhciBmNT0kKCdwczUnKTsKICAgICAgICB2YXIgZmY9ZjU/KGY1LnF1ZXJ5U2VsZWN0b3IoJ2Zvcm0nKXx8ZG9jdW1lbnQucXVlcnlTZWxlY3RvcignZm9ybScpKTpudWxsOwogICAgICAgIGlmKGZmJiZXLmZldGNoKXsKICAgICAgICAgIHJlbGxlbmFyRm90b3NGb3JtdWxhcmlvKCk7CiAgICAgICAgICBndWFyZGFyQ2xhdmVTZXNpb24oKTsKICAgICAgICAgIFcuX196eUVudmlhbmRvMTc9dHJ1ZTsKICAgICAgICAgIG1zZygnenlDbGF2ZU9rJywnVG9kbyB2ZXJpZmljYWRvOiBjcmVhbmRvIHR1IFpJRC4uLicsJyMwODAnKTsKICAgICAgICAgIGVudmlhclBvckZldGNoKGZmKTsKICAgICAgICB9CiAgICAgIH1jYXRjaChlVCl7IFcuX196eUVudkZhbGxiYWNrMTg9ZmFsc2U7IH0KICAgIH0sNjAwKTsKICB9Y2F0Y2goZUEpe30KfQoKLyogdjE3OiBlbnZpbyBwcm90ZWdpZG8gcG9yIGZldGNoIGRlc2RlIGVsIFBSSU1FUiBpbnRlbnRvICsgcGFudGFsbGEgZGUgZXhpdG8uCiAgIC0gcmVib3RlIGRlbCBzZXJ2aWRvciAtPiBOTyByZWNhcmdhOiBzaWd1ZXMgZW4gZWwgcGFzbyA1IGNvbiBUT0RPIChjbGF2ZSBpbmNsdWlkYSk7CiAgIC0gZXhpdG8gLT4gbWFyY2EgenlaaWRPSzE3ICsgY29kaWdvIGRlIFpJRCBzaSB2aWVuZSArIHBhbnRhbGxhIHZlcmRlOwogICAtIGZhbGxvIGRlbCBjYW5hbCAtPiByZWludGVudG8gbm9ybWFsIHkgbGEgY2xhdmUgc2UgcmVwb25lIHNvbGEgaWd1YWwuICovCmZ1bmN0aW9uIHF1aXRhQWNlbnRvcyhzKXsKICByZXR1cm4gKHN8fCcnKS5yZXBsYWNlKC9bXHUwMEMwLVx1MDBDNV0vZywnQScpLnJlcGxhY2UoL1tcdTAwQzgtXHUwMENCXS9nLCdFJykucmVwbGFjZSgvW1x1MDBDQy1cdTAwQ0ZdL2csJ0knKS5yZXBsYWNlKC9bXHUwMEQyLVx1MDBENl0vZywnTycpLnJlcGxhY2UoL1tcdTAwRDktXHUwMERDXS9nLCdVJykucmVwbGFjZSgvXHUwMEQxL2csJ04nKS5yZXBsYWNlKC9bXHUwMEUwLVx1MDBFNV0vZywnYScpLnJlcGxhY2UoL1tcdTAwRTgtXHUwMEVCXS9nLCdlJykucmVwbGFjZSgvW1x1MDBFQy1cdTAwRUZdL2csJ2knKS5yZXBsYWNlKC9bXHUwMEYyLVx1MDBGNl0vZywnbycpLnJlcGxhY2UoL1tcdTAwRjktXHUwMEZDXS9nLCd1JykucmVwbGFjZSgvXHUwMEYxL2csJ24nKTsKfQp2YXIgUlhfT0s9LyhjcmVhZG8gY29uIGV4aXRvfHppZCBjcmVhZG98emlkIGZ1ZSBjcmVhZG98YmllbnZlbmlkfGZlbGljaWRhZGVzfHJlZ2lzdHJvIGNvbXBsZXRhZG98YWNjZXNvIGNyZWFkb3x5YSBwdWVkZXMgZW50cmFyfGN1ZW50YSBjcmVhZGEpL2k7Ci8qIHYxODogZGV0ZWN0b3IgZGUgbGEgcmVzcHVlc3RhICJyZWN1cGVyYXIgY2xhdmUiIGRlbCBzZXJ2aWRvci4gQ29uIGxhcyBjYXB0dXJhcyBkZWwKICAgMTEvMTEgc2UgY29uZmlybW8gbGEgY2FkZW5hOiB0b2NhcyBDcmVhciBtaSBaSUQsIGVsIHNlcnZpZG9yIE5PIGNyZWEgbmFkYSB5IHJlc3BvbmRlCiAgIGNvbiBsYSBwYW50YWxsYSBkZSBSZWN1cGVyYXIgY29udHJhc2VuYSAoY2FzaSBzaWVtcHJlIHBvcnF1ZSB1biBaSUQgY29uIHR1cyBkYXRvcyBZQQogICBFWElTVEUgZGUgdW4gaW50ZW50byBhbnRlcmlvcikuIEVuIHYxNyBlc2EgcmVzcHVlc3RhIHNlIHRvbWFiYSBjb21vIGV4aXRvIHkgaGFzdGEgc2UKICAgcmVlc2NyaWJpYSBsYSBwYWdpbmEgY29uIGVsbGE6IHBvciBlc28gdmVpYXMgUmVjdXBlcmFyIGNvbnRyYXNlbmEgZW4gdmV6IGRlIHR1IFpJRC4gKi8KdmFyIFJYX1JFQ1VQPS8ocmVjdXBlcmFyXHMrKGNvbnRyYXNlbmF8Y2xhdmV8YWNjZXNvfHR1XHMrY2xhdmV8dHVccytjb250cmFzZW5hKSl8cmVjdXBlcmFjaW9ufHJlY3VwZXJhbGF8b2x2aWRcdypccysodHVccyt8c3VccyspPyhjbGF2ZXxjb250cmFzZW5hfGFjY2Vzbyl8KHlhXHMrKHRpZW5lcz98dGVuZXN8ZXhpc3RlfGVzdGFccytyZWdpc3RyYWR8c2VccytlbmN1ZW50cmFccytyZWdpc3RyYWR8Y3VlbnRhXHMrY29uXHMrdW4pKXxjdWVudGFccyt5YVxzK2V4aXN0ZXx5YVxzK2VzdGFccytyZWdpc3RyYWR8dXN1YXJpb1xzK3lhXHMrKGV4aXN0ZXxyZWdpc3RyYWQpfGluaWNpYVxzK3Nlc2l8aW5ncmVzYVxzK2NvblxzK3R1fGVudHJhclxzK2NvblxzK3R1fHlhXHMrdGllbmVzXHMrdW5ccyt6aWQvaTsKZnVuY3Rpb24gZXh0cmFlclppZCh0KXsKICB2YXIgbT0odHx8JycpLm1hdGNoKC9aSURbXkEtWmEtejAtOV17MCwxNn0oW0EtWjAtOV1bQS1aMC05XC1dezMsMTl9KS8pOwogIHJldHVybiBtP21bMV06Jyc7Cn0KZnVuY3Rpb24gc2luVGFncyh0KXsKICByZXR1cm4gU3RyaW5nKHR8fCcnKS5yZXBsYWNlKC88c2NyaXB0W1xzXFNdKj88XC9zY3JpcHQ+L2dpLCcgJykucmVwbGFjZSgvPHN0eWxlW1xzXFNdKj88XC9zdHlsZT4vZ2ksJyAnKS5yZXBsYWNlKC88W14+XSs+L2csJyAnKS5yZXBsYWNlKC8mbmJzcDsvZywnICcpLnJlcGxhY2UoL1xzKy9nLCcgJykudHJpbSgpLnNsaWNlKDAsMzAwKTsKfQpmdW5jdGlvbiBwYW5lbEV4aXRvKHppZCxleHRyYSl7CiAgdHJ5ewogICAgaWYoJCgnenlFeGl0bzE3JykpeyByZXR1cm47IH0KICAgIHZhciBvPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgby5pZD0nenlFeGl0bzE3JzsKICAgIG8uc3R5bGUuY3NzVGV4dD0ncG9zaXRpb246Zml4ZWQ7bGVmdDowO3JpZ2h0OjA7dG9wOjA7Ym90dG9tOjA7ei1pbmRleDoyMTQ3NDgzNjQ3O2JhY2tncm91bmQ6cmdiYSg0LDM0LDIwLC45Nyk7Y29sb3I6I2VhZmZmMDtwYWRkaW5nOjIycHggMThweDtvdmVyZmxvdzphdXRvO2ZvbnQtZmFtaWx5Oi1hcHBsZS1zeXN0ZW0sUm9ib3RvLEFyaWFsLHNhbnMtc2VyaWY7dGV4dC1hbGlnbjpjZW50ZXI7JzsKICAgIHZhciBoPScnOwogICAgaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZTo1NHB4O2xpbmUtaGVpZ2h0OjE7bWFyZ2luLXRvcDoxOHB4OyI+XHUyNzA1PC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6MjZweDtmb250LXdlaWdodDo4MDA7bWFyZ2luOjE0cHggMCA2cHg7Ij5cdTAwQTFUVSBaSUQgRlVFIENSRUFETyE8L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNXB4O29wYWNpdHk6LjkyOyI+WWEgZm9ybWFzIHBhcnRlIGRlIGxhIFJlZCBkZSBjb25maWFuemEgZGlnaXRhbC48L2Rpdj4nOwogICAgaWYoemlkKXsgaCs9JzxkaXYgc3R5bGU9Im1hcmdpbjoxOHB4IGF1dG8gNnB4O2Rpc3BsYXk6aW5saW5lLWJsb2NrO2JhY2tncm91bmQ6IzBhM2QyNDtib3JkZXI6MnB4IHNvbGlkICMzNGQzOTk7Y29sb3I6I2E3ZjNkMDtmb250OjcwMCAyMnB4LzEuMiBtb25vc3BhY2U7cGFkZGluZzoxMnB4IDE4cHg7Ym9yZGVyLXJhZGl1czoxMnB4O2xldHRlci1zcGFjaW5nOjFweDsiPicrU3RyaW5nKHppZCkucmVwbGFjZSgvW15BLVphLXowLTlcLV0vZywnJykrJzwvZGl2Pic7IH0KICAgIGgrPSc8ZGl2IHN0eWxlPSJtYXJnaW46MTZweCAwIDRweDtmb250LXNpemU6MTRweDtvcGFjaXR5Oi45O3RleHQtYWxpZ246bGVmdDttYXgtd2lkdGg6NDIwcHg7bWFyZ2luLWxlZnQ6YXV0bzttYXJnaW4tcmlnaHQ6YXV0bzsiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0ibWFyZ2luOjZweCAwOyI+MS4gQXB1bnRhIHR1IFpJRCcrKHppZD8nIChlbCBjb2RpZ28gZGUgYXJyaWJhKSc6JycpKycuPC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJtYXJnaW46NnB4IDA7Ij4yLiBUb2NhIExJU1RPIGFxdWkgYWJham8uPC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJtYXJnaW46NnB4IDA7Ij4zLiBFbnRyYSBjb24gdHUgY2xhdmUgZG9uZGUgZGljZSAiWWEgdGVuZ28gWklEIi48L2Rpdj4nOwogICAgaCs9JzwvZGl2Pic7CiAgICBpZihleHRyYSl7IGgrPSc8ZGl2IHN0eWxlPSJtYXJnaW46MTBweCBhdXRvO2ZvbnQtc2l6ZToxMnB4O29wYWNpdHk6Ljc1O21heC13aWR0aDo0MjBweDt0ZXh0LWFsaWduOmxlZnQ7Ij5SZXNwdWVzdGEgZGVsIHNlcnZpZG9yOiAnK1N0cmluZyhleHRyYSkucmVwbGFjZSgvJi9nLCcmYW1wOycpLnJlcGxhY2UoLzwvZywnJmx0OycpKyc8L2Rpdj4nOyB9CiAgICBoKz0nPGJ1dHRvbiBpZD0ienlFeGl0b0J0bjE3IiB0eXBlPSJidXR0b24iIHN0eWxlPSJtYXJnaW4tdG9wOjE4cHg7cGFkZGluZzoxNHB4IDQ0cHg7Ym9yZGVyOjA7Ym9yZGVyLXJhZGl1czoxMnB4O2JhY2tncm91bmQ6IzIyYzU1ZTtjb2xvcjojMDQyMjBmO2ZvbnQtc2l6ZToxN3B4O2ZvbnQtd2VpZ2h0OjgwMDsiPkxJU1RPPC9idXR0b24+JzsKICAgIG8uaW5uZXJIVE1MPWg7CiAgICBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKG8pOwogICAgdmFyIGJ0PSQoJ3p5RXhpdG9CdG4xNycpOwogICAgaWYoYnQpeyBidC5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oKXsgdHJ5eyBvLnBhcmVudE5vZGUucmVtb3ZlQ2hpbGQobyk7IH1jYXRjaChlWCl7fSB0cnl7IGxvY2FsU3RvcmFnZS5yZW1vdmVJdGVtKCd6eVppZE9LMTcnKTsgfWNhdGNoKGVZKXt9IH0pOyB9CiAgICBtc2coJ3p5Q2xhdmVPaycsJ1x1MjcxMyBaSUQgY3JlYWRvIGNvbiBleGl0by4gWWEgcHVlZGVzIGVudHJhciBjb24gdHUgY2xhdmUuJywnIzA4MCcpOwogIH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gaGF5RXhpdG8oKXsgdHJ5eyByZXR1cm4gISFsb2NhbFN0b3JhZ2UuZ2V0SXRlbSgnenlaaWRPSzE3Jyk7IH1jYXRjaChlKXsgcmV0dXJuIGZhbHNlOyB9IH0KZnVuY3Rpb24gbW9zdHJhckV4aXRvU2lIYXkoKXsKICBpZighaGF5RXhpdG8oKSl7IHJldHVybjsgfQogIHZhciB6aWQ9Jyc7CiAgdHJ5eyB6aWQ9bG9jYWxTdG9yYWdlLmdldEl0ZW0oJ3p5WmlkQ29kaWdvMTcnKXx8Jyc7IH1jYXRjaChlKXsgfQogIHBhbmVsRXhpdG8oemlkLCcnKTsKfQovKiB2MTg6IHBhbmVsIEhPTkVTVE8gY3VhbmRvIGVsIHNlcnZpZG9yIHJlc3BvbmRlIGNvbiBsYSBwYW50YWxsYSBkZSByZWN1cGVyYXIgY2xhdmUKICAgZW4gdmV6IGRlIGNyZWFyIGVsIFpJRC4gTk8gdG9jYSB0dXMgZGF0b3MsIE5PIGJvcnJhIGxhIGNsYXZlLCBOTyByZWVzY3JpYmUgbGEKICAgcGFnaW5hOiBleHBsaWNhIHF1ZSBjYXNpIHNlZ3VybyB0dSBaSUQgeWEgZXhpc3RlIHkgdGUgZGEgbG9zIHBhc29zIGV4YWN0b3MgcGFyYQogICBlbnRyYXIgY29uIGxhIGNsYXZlIHF1ZSBlc2NyaWJpc3RlIChwdWVkZXMgdmVybGEgY29uIGVsIGJvdG9uIFZFUiBNSSBDTEFWRSkuICovCmZ1bmN0aW9uIHBhbmVsUmVjdXBlcmEoZXh0cmEsaW50ZW50b3MpewogIHRyeXsKICAgIGlmKCQoJ3p5UmVjdXAxOCcpKXsgcmV0dXJuOyB9CiAgICB2YXIgbz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgIG8uaWQ9J3p5UmVjdXAxOCc7CiAgICBvLnN0eWxlLmNzc1RleHQ9J3Bvc2l0aW9uOmZpeGVkO2xlZnQ6MDtyaWdodDowO3RvcDowO2JvdHRvbTowO3otaW5kZXg6MjE0NzQ4MzY0NztiYWNrZ3JvdW5kOnJnYmEoNDYsMjAsNCwuOTcpO2NvbG9yOiNmZmY3ZWM7cGFkZGluZzoyMHB4IDE2cHg7b3ZlcmZsb3c6YXV0bztmb250LWZhbWlseTotYXBwbGUtc3lzdGVtLFJvYm90byxBcmlhbCxzYW5zLXNlcmlmOyc7CiAgICB2YXIgY2xhdmU9Jyc7CiAgICB0cnl7IHZhciBkPUpTT04ucGFyc2Uoc2Vzc2lvblN0b3JhZ2UuZ2V0SXRlbShLU0VTTSl8fCd7fScpOyBjbGF2ZT0oZCYmZC5jMSYmZC5jMS5sZW5ndGg+PTgpP2QuYzE6Jyc7IH1jYXRjaChlQyl7IGNsYXZlPScnOyB9CiAgICB2YXIgaD0nJzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJmb250LXNpemU6NDRweDtsaW5lLWhlaWdodDoxO21hcmdpbi10b3A6MTJweDsiPlx1MjZBMDwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjIxcHg7Zm9udC13ZWlnaHQ6ODAwO21hcmdpbjoxMnB4IDAgOHB4OyI+RUwgU0VSVklET1IgTk8gQ1JFTyBVTiBaSUQgTlVFVk88L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToxNHB4O29wYWNpdHk6Ljk1O2xpbmUtaGVpZ2h0OjEuNTsiPkFsIHRvY2FyIDxiPkNyZWFyIG1pIFpJRDwvYj4sIGVsIHNlcnZpZG9yIHJlc3BvbmRpbyBjb24gbGEgcGFudGFsbGEgZGUgPGI+UmVjdXBlcmFyIGNvbnRyYXNlJm50aWxkZTthPC9iPiAoaW50ZW50byAnK2ludGVudG9zKycpLiBFbCBzZXJ2aWRvciBoYWNlIGVzbyBjdWFuZG8gdW4gWklEIGNvbiB0dXMgZGF0b3MgPGI+WUEgRVhJU1RFPC9iPiBkZSB1biBpbnRlbnRvIGFudGVyaW9yOiBubyBkZWphIGNyZWFyIG90cm8uPC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJtYXJnaW46MTRweCAwIDRweDtmb250LXNpemU6MTRweDt0ZXh0LWFsaWduOmxlZnQ7bWF4LXdpZHRoOjQ2MHB4O21hcmdpbi1sZWZ0OmF1dG87bWFyZ2luLXJpZ2h0OmF1dG87bGluZS1oZWlnaHQ6MS42O2JhY2tncm91bmQ6cmdiYSgyNTUsMjU1LDI1NSwuMDcpO2JvcmRlci1yYWRpdXM6MTBweDtwYWRkaW5nOjEycHggMTRweDsiPic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZm9udC13ZWlnaHQ6NzAwO21hcmdpbi1ib3R0b206NnB4OyI+UVVFIEhBQ0VSIEFIT1JBIChubyBwaWVyZGVzIG5hZGEpOjwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0ibWFyZ2luOjVweCAwOyI+MS4gTGEgY2xhdmUgcXVlIGVzY3JpYmlzdGUgYXF1aSBTSSBTSVJWRSBwYXJhIGVudHJhcicrKGNsYXZlPycgPGJ1dHRvbiBpZD0ienlWZXJDbGF2ZTE4IiB0eXBlPSJidXR0b24iIHN0eWxlPSJtYXJnaW4tbGVmdDo2cHg7cGFkZGluZzo0cHggMTBweDtib3JkZXI6MDtib3JkZXItcmFkaXVzOjhweDtiYWNrZ3JvdW5kOiNmNTllMGI7Y29sb3I6IzNiMWQwMjtmb250LXdlaWdodDo3MDA7Zm9udC1zaXplOjEycHg7Ij5WRVIgTUkgQ0xBVkU8L2J1dHRvbj4nOicnKSsnPC9kaXY+JzsKICAgIGlmKGNsYXZlKXsgaCs9JzxkaXYgaWQ9Inp5Q2xhdmVWZXIxOCIgc3R5bGU9ImRpc3BsYXk6bm9uZTttYXJnaW46NnB4IDAgMnB4O2ZvbnQ6NzAwIDE2cHgvMS4zIG1vbm9zcGFjZTtjb2xvcjojZmRlNjhhO3dvcmQtYnJlYWs6YnJlYWstYWxsOyI+JytTdHJpbmcoY2xhdmUpLnJlcGxhY2UoLyYvZywnJmFtcDsnKS5yZXBsYWNlKC88L2csJyZsdDsnKSsnPC9kaXY+JzsgfQogICAgaCs9JzxkaXYgc3R5bGU9Im1hcmdpbjo1cHggMDsiPjIuIFRvY2EgTElTVE8gYXF1aSBhYmFqby48L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9Im1hcmdpbjo1cHggMDsiPjMuIFZ1ZWx2ZSBhbCBpbmljaW8geSB0b2NhIDxiPkVudHJhcjwvYj4gKG8gIllhIHRlbmdvIFpJRCIpLjwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0ibWFyZ2luOjVweCAwOyI+NC4gRXNjcmliZSB0dSBub21icmUgbyB0dSBaSUQgeSBFU0EgTUlTTUEgY2xhdmUuPC9kaXY+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJtYXJnaW46NXB4IDA7Ij41LiBTaSBubyBlbnRyYSwgdG9jYSA8Yj5SZWN1cGVyYXIgY29udHJhc2UmbnRpbGRlO2E8L2I+LCBzaWd1ZSBsb3MgcGFzb3MgeSBkZWphIGxhIE1JU01BIGNsYXZlLjwvZGl2Pic7CiAgICBoKz0nPC9kaXY+JzsKICAgIGlmKGV4dHJhKXsgaCs9JzxkaXYgc3R5bGU9Im1hcmdpbjoxMHB4IGF1dG87Zm9udC1zaXplOjExcHg7b3BhY2l0eTouNzttYXgtd2lkdGg6NDYwcHg7dGV4dC1hbGlnbjpsZWZ0OyI+UmVzcHVlc3RhIGNydWRhIGRlbCBzZXJ2aWRvcjogJytTdHJpbmcoZXh0cmEpLnJlcGxhY2UoLyYvZywnJmFtcDsnKS5yZXBsYWNlKC88L2csJyZsdDsnKSsnPC9kaXY+JzsgfQogICAgaCs9JzxidXR0b24gaWQ9Inp5UmVjdXBCdG4xOCIgdHlwZT0iYnV0dG9uIiBzdHlsZT0ibWFyZ2luLXRvcDoxNnB4O3BhZGRpbmc6MTRweCA0NHB4O2JvcmRlcjowO2JvcmRlci1yYWRpdXM6MTJweDtiYWNrZ3JvdW5kOiNmNTllMGI7Y29sb3I6IzNiMWQwMjtmb250LXNpemU6MTdweDtmb250LXdlaWdodDo4MDA7Ij5MSVNUTzwvYnV0dG9uPic7CiAgICBvLmlubmVySFRNTD1oOwogICAgZG9jdW1lbnQuYm9keS5hcHBlbmRDaGlsZChvKTsKICAgIHZhciB2Yz0kKCd6eVZlckNsYXZlMTgnKTsKICAgIGlmKHZjKXsgdmMuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKCl7IHZhciBjPSQoJ3p5Q2xhdmVWZXIxOCcpOyBpZihjKXsgYy5zdHlsZS5kaXNwbGF5PShjLnN0eWxlLmRpc3BsYXk9PT0nbm9uZScpPydibG9jayc6J25vbmUnOyB9IH0pOyB9CiAgICB2YXIgYnQ9JCgnenlSZWN1cEJ0bjE4Jyk7CiAgICBpZihidCl7IGJ0LmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbigpeyB0cnl7IG8ucGFyZW50Tm9kZS5yZW1vdmVDaGlsZChvKTsgfWNhdGNoKGVYKXt9IH0pOyB9CiAgICBtc2coJ3p5Q2xhdmVPaycsJ0VsIHNlcnZpZG9yIHBpZGUgcmVjdXBlcmFyIGxhIGNsYXZlIChubyBjcmVvIHVuIFpJRCBudWV2bykuIFR1cyBkYXRvcyB5IHR1IGNsYXZlIHNpZ3VlbiBpbnRhY3RvczogdXNhIEVudHJhciBjb24gdHUgY2xhdmUuJywnI2E2MCcpOwogIH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gZW52aWFyUG9yRmV0Y2goZil7CiAgdmFyIHVybD0oZi5nZXRBdHRyaWJ1dGUoJ2FjdGlvbicpfHwoVy5sb2NhdGlvbiYmVy5sb2NhdGlvbi5wYXRobmFtZSl8fCcnKTsKICB2YXIgbWV0b2RvPSgoKGYubWV0aG9kfHwncG9zdCcpKycnKS50b1VwcGVyQ2FzZSgpKXx8J1BPU1QnOwogIHZhciBmZD1udWxsOwogIHRyeXsgZmQ9bmV3IEZvcm1EYXRhKGYpOyB9Y2F0Y2goZUYpeyBXLl9fenlFbnZpYW5kbzE3PWZhbHNlOyByZXR1cm47IH0KICBpZighVy5mZXRjaHx8IWZkKXsgVy5fX3p5RW52aWFuZG8xNz1mYWxzZTsgcmV0dXJuOyB9CiAgZ3VhcmRhckNsYXZlU2VzaW9uKCk7CiAgVy5fX3p5VWx0aW1vRW52aW8xOD1EYXRlLm5vdygpOwogIG1zZygnenlDbGF2ZU9rJywnQ3JlYW5kbyB0dSBaSUQgKGVudmlvIHByb3RlZ2lkbywgc2luIHJlY2FyZ2FyKS4uLicsJyMwODAnKTsKICBXLmZldGNoLmNhbGwoVyx1cmwse21ldGhvZDptZXRvZG8sYm9keTpmZCxjcmVkZW50aWFsczonc2FtZS1vcmlnaW4nLHJlZGlyZWN0Oidmb2xsb3cnfSkudGhlbihmdW5jdGlvbihyKXsKICAgIHJldHVybiByLnRleHQoKTsKICB9KS50aGVuKGZ1bmN0aW9uKHQpewogICAgVy5fX3p5RW52aWFuZG8xNz1mYWxzZTsKICAgIHQ9dHx8Jyc7CiAgICB2YXIgdG49cXVpdGFBY2VudG9zKHQpOwogICAgdHJ5eyBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgnenlVbHRpbWFSZXNwdWVzdGExNicsdC5yZXBsYWNlKC9ccysvZywnICcpLnNsaWNlKDAsNDAwMCkpOyB9Y2F0Y2goZVMpe30KICAgIC8qIHYxODogY2xhc2lmaWNhY2lvbiBob25lc3RhIGRlIGxhIHJlc3B1ZXN0YSBkZWwgc2Vydmlkb3IuCiAgICAgICAtIGV4aXRvUmVhbDogcHJ1ZWJhIGRlIGV4aXRvICh0ZXh0byBkZSBleGl0byBvIGNvZGlnbyBkZSBaSUQpOyBtYW5kYSBzb2JyZQogICAgICAgICB0b2RvIGxvIGRlbWFzICh1bmEgcGFnaW5hIGRlIGV4aXRvIHB1ZWRlIHRyYWVyIHVuIGVubGFjZSAiUmVjdXBlcmFyCiAgICAgICAgIGNvbnRyYXNlbmEiIGVuIGVsIHBpZTogZXNvIE5PIGxhIGNvbnZpZXJ0ZSBlbiBmcmFjYXNvKTsKICAgICAgIC0gcGlkZVJlY3VwZXJhcjogU0lOIHBydWViYSBkZSBleGl0bywgZWwgc2Vydmlkb3IgcmVzcG9uZGUgY29uIGxhIHBhbnRhbGxhCiAgICAgICAgIGRlIFJlY3VwZXJhciBjb250cmFzZW5hIChlbCBjYXNvIGRlIHR1IGNhcHR1cmEgZGVsIDExLzExKTsKICAgICAgIC0gcmVzdG86IGVsIHNlcnZpZG9yIGRldm9sdmlvIGVsIGZvcm11bGFyaW8gdSBvdHJhIGNvc2Egc2luIGNvbmZpcm1hci4gKi8KICAgIHZhciB6aWQ9ZXh0cmFlclppZCh0bik7CiAgICB2YXIgZXhpdG9SZWFsPShSWF9PSy50ZXN0KHRuKXx8ISF6aWQpOwogICAgdmFyIHBpZGVSZWN1cGVyYXI9IWV4aXRvUmVhbCYmUlhfUkVDVVAudGVzdCh0bik7CiAgICB2YXIgcmVjYXJnYT10LmluZGV4T2YoJ1pZUkEtUkVWRicpPj0wOwogICAgaWYoZXhpdG9SZWFsKXsKICAgICAgdHJ5eyBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgnenlaaWRPSzE3JyxTdHJpbmcoRGF0ZS5ub3coKSkpOyBpZih6aWQpeyBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgnenlaaWRDb2RpZ28xNycsemlkKTsgfSB9Y2F0Y2goZUUpe30KICAgICAgdHJ5eyBsb2NhbFN0b3JhZ2UucmVtb3ZlSXRlbSgnenlSZWJvdGVzMTYnKTsgbG9jYWxTdG9yYWdlLnJlbW92ZUl0ZW0oJ3p5UmVzcGFsZG9GMTYnKTsgc2Vzc2lvblN0b3JhZ2UucmVtb3ZlSXRlbShLU0VTTSk7IH1jYXRjaChlQyl7fQogICAgICBwYW5lbEV4aXRvKHppZCxzaW5UYWdzKHQpKTsKICAgICAgLyogdjE4OiBsYSBwYWdpbmEgU09MTyBzZSByZWVzY3JpYmUgY29uIGxhIHJlc3B1ZXN0YSBkZWwgc2Vydmlkb3Igc2kgaGF5CiAgICAgICAgIGV4aXRvIERFTU9TVFJBRE8uIEVuIHYxNyBzZSByZWVzY3JpYmlhIGNvbiBjdWFscXVpZXIgcmVzcHVlc3RhIHNpbgogICAgICAgICBtYXJjYXMgZGUgcmVib3RlOiBjb24gbGEgcGFudGFsbGEgZGUgUmVjdXBlcmFyIGNvbnRyYXNlbmEgZXNvIHBpbnRhYmEKICAgICAgICAgbGEgcGFudGFsbGEgZGUgcmVjdXBlcmFyIEVOQ0lNQSBkZSB0dSByZWdpc3Ryby4gTnVuY2EgbWFzLiAqLwogICAgICBpZihyZWNhcmdhKXsgdHJ5eyBkb2N1bWVudC5vcGVuKCk7IGRvY3VtZW50LndyaXRlKHQpOyBkb2N1bWVudC5jbG9zZSgpOyB9Y2F0Y2goZVcpeyB0cnl7IFcubG9jYXRpb24uaHJlZj11cmw7IH1jYXRjaChlSCl7fSB9IH0KICAgIH1lbHNlIGlmKHBpZGVSZWN1cGVyYXIpewogICAgICB2YXIgbj0xOwogICAgICB0cnl7IG49KHBhcnNlSW50KGxvY2FsU3RvcmFnZS5nZXRJdGVtKCd6eVJlYm90ZXMxNicpfHwnMCcsMTApfHwwKSsxOyBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgnenlSZWJvdGVzMTYnLFN0cmluZyhuKSk7IH1jYXRjaChlTCl7fQogICAgICAvKiB2MTg6IGxpbXBpYSBsYSBtYXJjYSBkZSBleGl0byBmYWxzYSBxdWUgbGEgdjE3IHB1ZG8gZGVqYXIgZ3VhcmRhZGEgKi8KICAgICAgdHJ5eyBsb2NhbFN0b3JhZ2UucmVtb3ZlSXRlbSgnenlaaWRPSzE3Jyk7IH1jYXRjaChlWil7fQogICAgICBwYW5lbFJlY3VwZXJhKHNpblRhZ3ModCksbik7CiAgICAgIHRyeXsgdmFyIGJ4PSQoJ3p5RGlhZzE2Jyk7IGlmKGJ4KXsgYnguc3R5bGUuZGlzcGxheT0nYmxvY2snOyB9IHBpbnRhRGlhZygpOyB9Y2F0Y2goZUQpe30KICAgIH1lbHNlewogICAgICB2YXIgbjI9MTsKICAgICAgdHJ5eyBuMj0ocGFyc2VJbnQobG9jYWxTdG9yYWdlLmdldEl0ZW0oJ3p5UmVib3RlczE2Jyl8fCcwJywxMCl8fDApKzE7IGxvY2FsU3RvcmFnZS5zZXRJdGVtKCd6eVJlYm90ZXMxNicsU3RyaW5nKG4yKSk7IH1jYXRjaChlTDIpe30KICAgICAgbXNnKCd6eUNsYXZlT2snLCdFbCBzZXJ2aWRvciBubyBjb25maXJtbyBsYSBjcmVhY2lvbiAoaW50ZW50byAnK24yKycpLiBOTyB0b2Nhc3RlIG5hZGEgbWFsIHkgTk8gcGVyZGlzdGUgTkFEQTogc2lndWVzIGVuIGVsIHBhc28gNSBjb24gdHUgY2xhdmUgZXNjcml0YSB5IHR1cyBmb3Rvcy4gQWJyZSBlbCBwYW5lbCAiaSIgcGFyYSB2ZXIgcXVlIHJlc3BvbmRpbyBlbCBzZXJ2aWRvciB5IGF2aXNhbWUuJywnI2E2MCcpOwogICAgICB0cnl7IHZhciBieDI9JCgnenlEaWFnMTYnKTsgaWYoYngyKXsgYngyLnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsgfSBwaW50YURpYWcoKTsgfWNhdGNoKGVEMil7fQogICAgfQogIH0pLmNhdGNoKGZ1bmN0aW9uKGUpewogICAgVy5fX3p5RW52aWFuZG8xNz1mYWxzZTsKICAgIGd1YXJkYXJDbGF2ZVNlc2lvbigpOwogICAgbXNnKCd6eUNsYXZlT2snLCdFbCBjYW5hbCBwcm90ZWdpZG8gbm8gcmVzcG9uZGlvICgnKyhlJiZlLm1lc3NhZ2U/ZS5tZXNzYWdlOidlcnJvcicpKycpLiBSZWludGVudG8gbm9ybWFsOiBzaSBsYSBwYWdpbmEgc2UgcmVjYXJnYSwgdHUgY2xhdmUgc2UgcmVwb25lIHNvbGEuJywnI2E2MCcpOwogICAgLyogdjE4OiBlbCByZWludGVudG8gbmF0aXZvIHBhc2EgcG9yIGVsIGVudm9sdmVudGUgdjE4IGNvbiBsYSBiYW5kZXJhCiAgICAgICBfX3p5TmF0aXZvMTggcGFyYSBxdWUgTk8gdnVlbHZhIGEgZW50cmFyIGFsIGNhbmFsIHByb3RlZ2lkbyAoZXZpdGEgYnVjbGVzKS4gKi8KICAgIHRyeXsgZi5fX3p5TmF0aXZvMTg9dHJ1ZTsgZi5zdWJtaXQoKTsgfWNhdGNoKGVGMil7IH0KICB9KTsKfQoKZnVuY3Rpb24gZW5nYW5jaGFyRW52aW9GaW5hbCgpewogIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ3N1Ym1pdCcsZnVuY3Rpb24oZXYpewogICAgdHJ5ewogICAgICB2YXIgcHM1PSQoJ3BzNScpLCBmPWV2LnRhcmdldDsKICAgICAgaWYocHM1JiZmJiZwczUuY29udGFpbnMoZikpeyBndWFyZGlhRW52aW8oZXYpOyB9CiAgICB9Y2F0Y2goZSl7fQogIH0sdHJ1ZSk7CiAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKGV2KXsKICAgIHRyeXsKICAgICAgdmFyIHBzNT0kKCdwczUnKSwgZWw9ZXYudGFyZ2V0OwogICAgICBpZighcHM1fHwhZWx8fCFwczUuY29udGFpbnMoZWwpKXsgcmV0dXJuOyB9CiAgICAgIHZhciBiPWVsLCBlc0JvdG9uPWZhbHNlLCBwcm9mPTA7CiAgICAgIHdoaWxlKGImJmIhPT1wczUmJnByb2Y8Nil7CiAgICAgICAgdmFyIHRnPWIudGFnTmFtZXx8Jyc7CiAgICAgICAgaWYodGc9PT0nQlVUVE9OJ3x8KHRnPT09J0lOUFVUJyYmKChiLnR5cGV8fCcnKT09PSdzdWJtaXQnfHwoYi50eXBlfHwnJyk9PT0nYnV0dG9uJykpfHwoYi5nZXRBdHRyaWJ1dGUmJmIuZ2V0QXR0cmlidXRlKCdyb2xlJyk9PT0nYnV0dG9uJykpeyBlc0JvdG9uPXRydWU7IGJyZWFrOyB9CiAgICAgICAgYj1iLnBhcmVudE5vZGU7IHByb2YrKzsKICAgICAgfQogICAgICBpZighZXNCb3Rvbil7IHJldHVybjsgfQogICAgICBpZighY2xhdmVzTGlzdGFzKCl8fCFmb3Rvc0NvbXBsZXRhcygpKXsgZ3VhcmRpYUVudmlvKGV2KTsgfQogICAgICBlbHNleyByZWxsZW5hckZvdG9zRm9ybXVsYXJpbygpOyB9CiAgICB9Y2F0Y2goZSl7fQogIH0sdHJ1ZSk7Cn0KCi8qID09PT09PT09PT09PT09PT09IGludGVycnVwdG9yIGRlIGJvdG9uZXMgPT09PT09PT09PT09PT09PT0gKi8KdmFyIE1JTz17J2JBYnJpckYnOjEsJ2JDYXBGJzoxLCdiQWJyaXJBJzoxLCdiQ2FwQSc6MSwnYkFicmlyQ2FtJzoxLCdiU2VsZmllJzoxLCdiUmVwU2VsZmllJzoxLCdiSXI0JzoxLCdiSXI1JzoxfTsKZnVuY3Rpb24gbWFuZWphcihpZCl7CiAgc3dpdGNoKGlkKXsKICAgIGNhc2UgJ2JBYnJpckYnOiBhYnJpckNhbSgnMicsJ2Vudmlyb25tZW50Jywnc3RGJywnYkNhcEYnKS5jYXRjaChmdW5jdGlvbigpe30pOyBicmVhazsKICAgIGNhc2UgJ2JDYXBGJzogeyB2YXIgZj1jYXB0dXJhclZpZGVvRG9jKCcyJywxNjAwKTsgaWYoIWYpeyBtc2coJ3N0RicsJ0FicmUgbGEgY1x1MDBFMW1hcmEgcHJpbWVybyAoYm90XHUwMEYzbiBhYnJpciBjXHUwMEUxbWFyYSkuJywnI2MwMCcpOyB9IGVsc2UgeyBwcm9jZXNhckZyZW50ZShmKTsgfSBicmVhazsgfQogICAgY2FzZSAnYkFicmlyQSc6IGFicmlyQ2FtKCczJywnZW52aXJvbm1lbnQnLCdzdEEnLCdiQ2FwQScpLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IGJyZWFrOwogICAgY2FzZSAnYkNhcEEnOiB7IHZhciBhPWNhcHR1cmFyVmlkZW9Eb2MoJzMnLDE2MDApOyBpZighYSl7IG1zZygnc3RBJywnQWJyZSBsYSBjXHUwMEUxbWFyYSBwcmltZXJvIChib3RcdTAwRjNuIGFicmlyIGNcdTAwRTFtYXJhKS4nLCcjYzAwJyk7IH0gZWxzZSB7IHByb2Nlc2FyUmV2ZXJzbyhhKTsgfSBicmVhazsgfQogICAgY2FzZSAnZ2FsRic6IGNsaWNrQXJjaGl2bygnMicpOyBicmVhazsKICAgIGNhc2UgJ2dhbEEnOiBjbGlja0FyY2hpdm8oJzMnKTsgYnJlYWs7CiAgICBjYXNlICdiQWJyaXJDYW0nOiBFU1Quc2VsZmllT2s9ZmFsc2U7IEVTVC5jYXJhVml2YT1udWxsOyBhYnJpckNhbSgnNCcsJ3VzZXInLCdzdFYnLCdiU2VsZmllJykuY2F0Y2goZnVuY3Rpb24oKXt9KTsgYnJlYWs7CiAgICBjYXNlICdiU2VsZmllJzogewogICAgICB2YXIgY3Y9RVNULmNhcmFWaXZhLCB0MHM9KHp5RGV0KClbJzQnXSYmenlEZXQoKVsnNCddLnQwKXx8RGF0ZS5ub3coKTsKICAgICAgdmFyIGxpc3RvPWN2JiZjdi5vayYmKChEYXRlLm5vdygpLShjdi50fHwwKSk8MjUwMCk7CiAgICAgIHZhciBkZXRlY3RvclZpZWpvPShEYXRlLm5vdygpLXQwcyk+MTUwMDA7CiAgICAgIGlmKCFsaXN0byYmIWRldGVjdG9yVmllam8pewogICAgICAgIG1zZygnc3RWJywgKGN2JiZjdi52aXN0YSk/J0NlbnRyYSB0dSBjYXJhIGRlbnRybyBkZWwgT1ZBTE8gKGRlYmUgcG9uZXJzZSBWRVJERSkgeSBsdWVnbyB0b2NhIENBUFRVUkFSLic6J1ByZXBhcmFuZG8gZWwgZGV0ZWN0b3IgZmFjaWFsLi4uIGVzcGVyYSB1bm9zIHNlZ3VuZG9zLicsJyNhNjAnKTsKICAgICAgICBicmVhazsKICAgICAgfQogICAgICBwcm9jZXNhclNlbGZpZSgpOwogICAgICBicmVhazsKICAgIH0KICAgIGNhc2UgJ2JSZXBTZWxmaWUnOiBFU1Quc2VsZmllT2s9ZmFsc2U7IEVTVC5jYXJhVml2YT1udWxsOyBhYnJpckNhbSgnNCcsJ3VzZXInLCdzdFYnLCdiU2VsZmllJykuY2F0Y2goZnVuY3Rpb24oKXt9KTsgYnJlYWs7CiAgICBjYXNlICdiSXI0JzoKICAgICAgaWYocGVybWl0aWRvSGFzdGEoKT49NCl7IGF2YW56YXIoNCk7IH0KICAgICAgZWxzZXsgbXNnKCdzdEEnLCdBXHUwMEZBbiBubyBwdWVkZXMgcGFzYXI6IHByaW1lcm8gY29tcGxldGEgZWwgZG9jdW1lbnRvIChmcmVudGUnKyhFU1QubmVjZXNpdGFSZXZlcnNvPycgeSByZXZlcnNvJzonJykrJykuJywnI2MwMCcpOyB9CiAgICAgIGJyZWFrOwogICAgY2FzZSAnYklyNSc6CiAgICAgIGlmKHBlcm1pdGlkb0hhc3RhKCk+PTUpeyBhdmFuemFyKDUpOyB9CiAgICAgIGVsc2V7IG1zZygnc3RWJywnQVx1MDBGQW4gbm8gcHVlZGVzIHBhc2FyOiBwcmltZXJvIHBhc2EgbGEgdmVyaWZpY2FjaVx1MDBGM24gZmFjaWFsLicsJyNjMDAnKTsgfQogICAgICBicmVhazsKICB9Cn0KZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKGUpewogIHZhciBlbD1lLnRhcmdldDsKICB3aGlsZShlbCAmJiBlbCE9PWRvY3VtZW50ICYmICEoZWwuaWQgJiYgTUlPW2VsLmlkXSkpeyBlbD1lbC5wYXJlbnROb2RlOyB9CiAgaWYoIWVsIHx8IGVsPT09ZG9jdW1lbnQpeyByZXR1cm47IH0KICBpZihlLnByZXZlbnREZWZhdWx0KXsgZS5wcmV2ZW50RGVmYXVsdCgpOyB9CiAgaWYoZS5zdG9wUHJvcGFnYXRpb24peyBlLnN0b3BQcm9wYWdhdGlvbigpOyB9CiAgaWYoZS5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24peyBlLnN0b3BJbW1lZGlhdGVQcm9wYWdhdGlvbigpOyB9CiAgdHJ5eyBtYW5lamFyKGVsLmlkLGUpOyB9Y2F0Y2goZXJyKXsgbG9nKCdlcnJvciBlbicsZWwuaWQsZXJyKTsgfQp9LHRydWUpOwoKLyogPT09PT09PT09PT09PT09PT0gZ2FsZXJpYSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBjbGlja0FyY2hpdm8ocHNJZCl7CiAgdmFyIGNvbnQ9JCgncHMnK3BzSWQpOwogIHZhciBpbnA9Y29udD9jb250LnF1ZXJ5U2VsZWN0b3IoJ2lucHV0W3R5cGU9ZmlsZV0nKTpudWxsOwogIGlmKGlucCl7IGlucC5jbGljaygpOyB9CiAgZWxzZXsgbXNnKHBzSWQ9PT0nMic/J3N0Ric6J3N0QScsJ05vIGVuY29udHJcdTAwRTkgZWwgc2VsZWN0b3IgZGUgYXJjaGl2b3MuJywnI2MwMCcpOyB9Cn0KZnVuY3Rpb24gZW5nYW5jaGFyR2FsZXJpYShpZCxwc0lkKXsKICB2YXIgZWw9JChpZCk7CiAgaWYoIWVsKXsgcmV0dXJuOyB9CiAgaWYoZWwudGFnTmFtZT09PSdJTlBVVCcgJiYgKGVsLnR5cGV8fCcnKS50b0xvd2VyQ2FzZSgpPT09J2ZpbGUnKXsKICAgIGVsLmFkZEV2ZW50TGlzdGVuZXIoJ2NoYW5nZScsZnVuY3Rpb24oKXsKICAgICAgdmFyIGY9ZWwuZmlsZXMmJmVsLmZpbGVzWzBdOwogICAgICBpZighZil7IHJldHVybjsgfQogICAgICBhcmNoaXZvQURhdG9zKGYpLnRoZW4oZnVuY3Rpb24oZCl7IHJldHVybiBkb3duc2NhbGUoZCwocHNJZD09PScyJ3x8cHNJZD09PSczJyk/MTYwMDoxMDI0KTsgfSkudGhlbihmdW5jdGlvbihkKXsKICAgICAgICBpZihwc0lkPT09JzInKXsgcHJvY2VzYXJGcmVudGUoZCk7IH0gZWxzZSB7IHByb2Nlc2FyUmV2ZXJzbyhkKTsgfQogICAgICB9KS5jYXRjaChmdW5jdGlvbihlcil7IG1zZyhwc0lkPT09JzInPydzdEYnOidzdEEnLCdObyBwdWRlIGxlZXIgbGEgaW1hZ2VuOiAnKyhlciYmZXIubWVzc2FnZT9lci5tZXNzYWdlOicnKSwnI2MwMCcpOyB9KTsKICAgIH0pOwogIH1lbHNlewogICAgTUlPW2lkXT0xOwogIH0KfQoKLyogPT09PT09PT09PT09PT09PT0gZXZlbnRvcyBkZSBwYXNvcyAxIHkgNSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBlbmdhbmNoYXJQYXNvMSgpewogIHZhciBpbnA9JCgnbm9tYnJlJyksIHNlbD0kKCd0aXBvRG9jJyk7CiAgaWYoaW5wKXsKICAgIGlucC5hZGRFdmVudExpc3RlbmVyKCdpbnB1dCcsZnVuY3Rpb24oKXsKICAgICAgLyogdjE2OiBlZGl0YXIgdHUgbm9tYnJlIEpBTUFTIHRlIG11ZXZlIGRlIHBhc28gbmkgdGUgcmVncmVzYSBhbAogICAgICAgICBpbmljaW8uIFNpIHF1ZWRhIGludmFsaWRvIG8gZGlmaWVyZSBkZWwgZG9jdW1lbnRvIHNvbG8gc2UKICAgICAgICAgYXZpc2E7IHR1IGF2YW5jZSB5IHR1cyBmb3RvcyBzZSBjb25zZXJ2YW4uICovCiAgICAgIHZhciBhbnRlc09rPUVTVC5ub21icmVPazsKICAgICAgdmFsaWRhclBhc28xKHRydWUpOwogICAgICBpZighRVNULm5vbWJyZU9rICYmIGFudGVzT2sgJiYgRVNULnBhc28+MSl7CiAgICAgICAgbXNnKCd6eUVyck5vbWJyZScsJ0VsIG5vbWJyZSBxdWVkXHUwMEYzIGluY29tcGxldG8gbyBpbnZhbGlkby4gQ29yclx1MDBFRGdlbG8gYXF1XHUwMEVEIGN1YW5kbyBxdWllcmFzOiB0dXMgZm90b3MgeWEgdG9tYWRhcyBzZSBjb25zZXJ2YW4uJywnI2E2MCcpOwogICAgICAgIHJldHVybjsKICAgICAgfQogICAgICBpZihFU1Qubm9tYnJlT2sgJiYgRVNULnBhc28+MSAmJiBFU1QuZnJlbnRlVGV4dG8pewogICAgICAgIHZhciBuYz1ub21icmVDb2luY2lkZShFU1QuZXNjcml0bywgRVNULmZyZW50ZVRleHRvLCBmYWxzZSk7CiAgICAgICAgaWYobmMuaGF5ICYmICFuYy5vayl7CiAgICAgICAgICBtc2coJ3p5RXJyTm9tYnJlJywnQXZpc286IGVsIG5vbWJyZSBudWV2byBubyBjb2luY2lkZSBjb24gbG8gcXVlIGRpY2UgZWwgZG9jdW1lbnRvICgnK25jLmxlaWRvKycpLiBZYSBjb25maXJtYXN0ZSBsYSBsZWN0dXJhLCBhc2kgcXVlIHB1ZWRlcyBzZWd1aXIuJywnI2E2MCcpOwogICAgICAgICAgcmV0dXJuOwogICAgICAgIH0KICAgICAgfQogICAgICBsaW1waWFyRXJyb3Jlc1Bhc28xKCk7CiAgICB9KTsKICB9CiAgaWYoc2VsKXsKICAgIHNlbC5hZGRFdmVudExpc3RlbmVyKCdjaGFuZ2UnLGZ1bmN0aW9uKCl7CiAgICAgIHZhciBhbnRlcz1FU1QudGlwbzsKICAgICAgdmFsaWRhclBhc28xKHRydWUpOwogICAgICBpZihFU1QudGlwbyE9PWFudGVzKXsgcmVzZXRlYXJEb2N1bWVudG8oKTsgfQogICAgICBsaW1waWFyRXJyb3Jlc1Bhc28xKCk7CiAgICB9KTsKICB9Cn0KLyogdjE3OiBldmVudG9zIGRlIGxhIGNsYXZlIGEgcHJ1ZWJhIGRlIHRvZG86IGVubGFjZSBkaXJlY3RvIGEgbG9zIGNhbXBvcwogICBoYWxsYWRvcywgb3llbnRlIGRlbGVnYWRvIGVuIGRvY3VtZW50IHBhcmEgZWwgYXV0b3JyZWxsZW5vLCB5IHNvbmRlbyBkZQogICA2MDAgbXMgcXVlIGRldGVjdGEgQ1VBTFFVSUVSIGNhbWJpbyAoYXV0b2NvbXBsZXRhZG8sIGdlc3RvciBkZSBjbGF2ZXMsCiAgIHJlcHVlc3RvIGRlIGxhIHNlc2lvbikuICovCmZ1bmN0aW9uIGVuZ2FuY2hhclBhc281KCl7CiAgZnVuY3Rpb24gZW5nYW5jaGEoKXsKICAgIGRlc2N1YnJlQ2xhdmVzKCFDTFYuYSk7CiAgICB2YXIgY3M9Y2FtcG9zQ2xhdmUoKSwgaTsKICAgIGZvcihpPTA7aTxjcy5sZW5ndGg7aSsrKXsKICAgICAgdmFyIGVsPWNzW2ldOwogICAgICBpZighZWx8fGVsLl9fenkxNyl7IGNvbnRpbnVlOyB9CiAgICAgIGVsLl9fenkxNz0xOwogICAgICBlbC5hZGRFdmVudExpc3RlbmVyKCdpbnB1dCcsdmFsaWRhckNsYXZlcyk7CiAgICAgIGVsLmFkZEV2ZW50TGlzdGVuZXIoJ2NoYW5nZScsdmFsaWRhckNsYXZlcyk7CiAgICAgIGVsLmFkZEV2ZW50TGlzdGVuZXIoJ2JsdXInLGd1YXJkYXJDbGF2ZVNlc2lvbik7CiAgICB9CiAgfQogIGVuZ2FuY2hhKCk7CiAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignaW5wdXQnLGZ1bmN0aW9uKGV2KXsgdmFyIHQ9ZXYudGFyZ2V0OyBpZih0JiYoKHQudHlwZXx8JycpKycnKS50b0xvd2VyQ2FzZSgpPT09J3Bhc3N3b3JkJyl7IHZhbGlkYXJDbGF2ZXMoKTsgfSB9LHRydWUpOwogIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ2NoYW5nZScsZnVuY3Rpb24oZXYpeyB2YXIgdD1ldi50YXJnZXQ7IGlmKHQmJigodC50eXBlfHwnJykrJycpLnRvTG93ZXJDYXNlKCk9PT0ncGFzc3dvcmQnKXsgdmFsaWRhckNsYXZlcygpOyB9IH0sdHJ1ZSk7CiAgc2V0SW50ZXJ2YWwoZnVuY3Rpb24oKXsKICAgIHRyeXsKICAgICAgdmFyIEw9bGVlckNsYXZlcygpOwogICAgICBpZighTC5hKXsgcmV0dXJuOyB9CiAgICAgIGlmKEwudjEhPT1DTFYudTF8fEwudjIhPT1DTFYudTIpeyB2YWxpZGFyQ2xhdmVzKCk7IH0KICAgICAgZWxzZXsgZ3VhcmRhckNsYXZlU2VzaW9uKCk7IH0KICAgIH1jYXRjaChlKXt9CiAgfSw2MDApOwp9CgovKiA9PT09PT09PT09PT09PT09PSB2MTY6IHJlc3BhbGRvIHkgcmVzY2F0ZSBkZWwgcmVnaXN0cm8gPT09PT09PT09PT09PT09PT0KICAgVHUgcmVnaXN0cm8gc2UgZ3VhcmRhIFNPTE8gZW4gdHUgdGVsZWZvbm8gKGxvY2FsU3RvcmFnZSk6IG5vbWJyZSwKICAgdGlwbyBkZSBkb2N1bWVudG8sIGZvdG9zIHkgaGFzdGEgcXVlIHBhc28gbGxlZ2FzdGUuIFNpIGVsIHNlcnZpZG9yCiAgIHRlIGRldnVlbHZlIGVsIGZvcm11bGFyaW8geSBsYSBwYWdpbmEgc2UgdnVlbHZlIGEgY2FyZ2FyLCBhbCBhYnJpcgogICBkZSBudWV2byBTSUdVRVMgZG9uZGUgaWJhczogbm8gZW1waWV6YXMgZGVzZGUgY2VybyBudW5jYSBtYXMuCiAgIFNlIGJvcnJhIHNvbG8gc2kgcGFzYW4gMjQgaG9yYXMgbyBzaSBjcmVhcyBlbCBaSUQgZGUgdmVyZGFkLiAqLwp2YXIgS0VZUj0nenlSZXNwYWxkb0YxNic7CmZ1bmN0aW9uIHJlc3BhbGRhKCl7CiAgdHJ5ewogICAgaWYoIUVTVC5ub21icmVPayYmIUVTVC5mcmVudGVPayl7IHJldHVybjsgfQogICAgdmFyIGluTj0kKCdub21icmUnKSwgaW5UPSQoJ3RpcG9Eb2MnKTsKICAgIHZhciBkPXt2OjE2LCB0czpEYXRlLm5vdygpLCBub21icmU6KGluTiYmaW5OLnZhbHVlKT9pbk4udmFsdWU6JycsIHRpcG86KGluVCYmaW5ULnZhbHVlKT9pblQudmFsdWU6JycsIGVzY3JpdG86RVNULmVzY3JpdG98fCcnLCBwYXNvOkVTVC5wYXNvfHwxLCBwYXNvTWF4OkVTVC5wYXNvTWF4fHwxLCBmcmVudGVPazohIUVTVC5mcmVudGVPaywgcmV2ZXJzb09rOiEhRVNULnJldmVyc29Paywgc2VsZmllT2s6ISFFU1Quc2VsZmllT2ssIG5lY2VzaXRhUmV2ZXJzbzohIUVTVC5uZWNlc2l0YVJldmVyc28sIGZyZW50ZVRleHRvOkVTVC5mcmVudGVUZXh0b3x8JycsIGltZ3M6e319OwogICAgZnVuY3Rpb24gbWV0ZXIoKXsKICAgICAgdHJ5eyBsb2NhbFN0b3JhZ2Uuc2V0SXRlbShLRVlSLEpTT04uc3RyaW5naWZ5KGQpKTsgcmV0dXJuIHRydWU7IH1jYXRjaChlKXsgcmV0dXJuIGZhbHNlOyB9CiAgICB9CiAgICBtZXRlcigpOwogICAgdmFyIGZvdG9zPVtdOwogICAgaWYoRVNULmZyZW50ZUltZyl7IGZvdG9zLnB1c2goWydmcmVudGVJbWcnLEVTVC5mcmVudGVJbWddKTsgfQogICAgaWYoRVNULnJldmVyc29JbWcpeyBmb3Rvcy5wdXNoKFsncmV2ZXJzb0ltZycsRVNULnJldmVyc29JbWddKTsgfQogICAgaWYoRVNULnNlbGZpZUltZyl7IGZvdG9zLnB1c2goWydzZWxmaWVJbWcnLEVTVC5zZWxmaWVJbWddKTsgfQogICAgaWYoIWZvdG9zLmxlbmd0aCl7IHJldHVybjsgfQogICAgZnVuY3Rpb24gY29uRm90b3MoZGltKXsKICAgICAgdmFyIGhlY2hvcz0wOwogICAgICBmb3IodmFyIGk9MDtpPGZvdG9zLmxlbmd0aDtpKyspewogICAgICAgIChmdW5jdGlvbihwYXIpewogICAgICAgICAgdmFyIHByPWRpbT9kb3duc2NhbGUocGFyWzFdLGRpbSk6UHJvbWlzZS5yZXNvbHZlKHBhclsxXSk7CiAgICAgICAgICBwci50aGVuKGZ1bmN0aW9uKHYpeyBkLmltZ3NbcGFyWzBdXT12OyB9LGZ1bmN0aW9uKCl7fSkudGhlbihmdW5jdGlvbigpewogICAgICAgICAgICBoZWNob3MrKzsKICAgICAgICAgICAgaWYoaGVjaG9zPj1mb3Rvcy5sZW5ndGgpewogICAgICAgICAgICAgIGlmKCFtZXRlcigpJiZkaW0peyBpZihkaW0+ODAwKXsgY29uRm90b3MoODAwKTsgfSBlbHNlIHsgZC5pbWdzPXt9OyBtZXRlcigpOyB9IH0KICAgICAgICAgICAgfQogICAgICAgICAgfSk7CiAgICAgICAgfSkoZm90b3NbaV0pOwogICAgICB9CiAgICB9CiAgICBjb25Gb3RvcygxMTAwKTsKICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIHJlc2NhdGFyKCl7CiAgdHJ5ewogICAgaWYoaGF5RXhpdG8oKSl7IHJldHVybjsgfQogICAgaWYoRVNULmZyZW50ZU9rfHxFU1Quc2VsZmllT2t8fFcuX196eVJlc2NhdGFkbzE2KXsgcmV0dXJuOyB9CiAgICB2YXIgcz1sb2NhbFN0b3JhZ2UuZ2V0SXRlbShLRVlSKTsKICAgIGlmKCFzKXsgcmV0dXJuOyB9CiAgICB2YXIgZD1KU09OLnBhcnNlKHMpfHx7fTsKICAgIGlmKGQudiE9PTE2fHxEYXRlLm5vdygpLShkLnRzfHwwKT44NjQwMDAwMCl7IGxvY2FsU3RvcmFnZS5yZW1vdmVJdGVtKEtFWVIpOyByZXR1cm47IH0KICAgIHZhciBpbnA9JCgnbm9tYnJlJyk7CiAgICBpZihpbnAmJmlucC52YWx1ZSYmbm9ybShpbnAudmFsdWUpIT09bm9ybShkLmVzY3JpdG98fCcnKSl7IGxvY2FsU3RvcmFnZS5yZW1vdmVJdGVtKEtFWVIpOyByZXR1cm47IH0KICAgIGlmKGlucCYmIWlucC52YWx1ZSYmZC5ub21icmUpeyBpbnAudmFsdWU9ZC5ub21icmU7IH0KICAgIHZhciBzZWw9JCgndGlwb0RvYycpOwogICAgaWYoc2VsJiYhc2VsLnZhbHVlJiZkLnRpcG8peyBzZWwudmFsdWU9ZC50aXBvOyB9CiAgICB2YWxpZGFyUGFzbzEodHJ1ZSk7CiAgICBpZihkLmVzY3JpdG8peyBFU1QuZXNjcml0bz1kLmVzY3JpdG87IH0KICAgIEVTVC5mcmVudGVPaz0hIWQuZnJlbnRlT2s7IEVTVC5yZXZlcnNvT2s9ISFkLnJldmVyc29PazsgRVNULnNlbGZpZU9rPSEhZC5zZWxmaWVPazsgRVNULm5lY2VzaXRhUmV2ZXJzbz0hIWQubmVjZXNpdGFSZXZlcnNvOyBFU1QuZnJlbnRlVGV4dG89ZC5mcmVudGVUZXh0b3x8Jyc7CiAgICB2YXIgaW09ZC5pbWdzfHx7fTsKICAgIEVTVC5mcmVudGVJbWc9aW0uZnJlbnRlSW1nfHwnJzsgRVNULnJldmVyc29JbWc9aW0ucmV2ZXJzb0ltZ3x8Jyc7IEVTVC5zZWxmaWVJbWc9aW0uc2VsZmllSW1nfHwnJzsKICAgIEVTVC5wYXNvTWF4PU1hdGgubWF4KDEsZC5wYXNvTWF4fHwxKTsKICAgIGlmKEVTVC5mcmVudGVJbWcpeyBzaG93SW1nKCdwRicsRVNULmZyZW50ZUltZyk7IH0KICAgIGlmKEVTVC5yZXZlcnNvSW1nKXsgc2hvd0ltZygncEEnLEVTVC5yZXZlcnNvSW1nKTsgfQogICAgaWYoRVNULnNlbGZpZUltZyl7IHNob3dJbWcoJ3BTJyxFU1Quc2VsZmllSW1nKTsgfQogICAgVy5fX3p5UmVzY2F0YWRvMTY9dHJ1ZTsKICAgIHZhciBkZXN0aW5vPU1hdGgubWluKEVTVC5wYXNvTWF4LHBlcm1pdGlkb0hhc3RhKCkpOwogICAgaWYoZGVzdGlubz49Mil7CiAgICAgIG1vc3RyYXJQYXNvKGRlc3Rpbm8pOwogICAgICBtc2coJ3p5R3VhcmRpYScsJ1JlY3VwZXJhbW9zIHR1IHJlZ2lzdHJvOiBzaWd1ZXMgZW4gZWwgcGFzbyAnK2Rlc3Rpbm8rJyBjb24gdHVzIGRhdG9zIHkgdHVzIGZvdG9zLiBOTyBlbXBlemFzdGUgZGUgbnVldm8uJywnIzA4MCcpOwogICAgICBpZihkZXN0aW5vPT09NCYmIUVTVC5zZWxmaWVPayl7IHNldFRpbWVvdXQoZnVuY3Rpb24oKXsgdHJ5eyBhYnJpckNhbSgnNCcsJ3VzZXInLCdzdFYnLCdiU2VsZmllJykuY2F0Y2goZnVuY3Rpb24oKXt9KTsgfWNhdGNoKGUpe30gfSw2MDApOyB9CiAgICB9CiAgfWNhdGNoKGUpe30KfQoKLyogPT09PT09PT09PT09PT09PT0gYXJyYW5xdWUgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gaW5pdCgpewogIGVuZ2FuY2hhclBhc28xKCk7CiAgZW5nYW5jaGFyUGFzbzUoKTsKICBlbmdhbmNoYXJFbnZpb0ZpbmFsKCk7CiAgZW5nYW5jaGFyR2FsZXJpYSgnZ2FsRicsJzInKTsKICBlbmdhbmNoYXJHYWxlcmlhKCdnYWxBJywnMycpOwogIFsnb3ZGJywnb3ZBJywnb3ZTJ10uZm9yRWFjaChmdW5jdGlvbihvaWQpeyB2YXIgbz0kKG9pZCk7IGlmKG8peyBvLnN0eWxlLnBvaW50ZXJFdmVudHM9J25vbmUnOyB9IH0pOwogIHRyeXsKICAgIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbihlKXsKICAgICAgLyogdjE2OiBtYXJjYXIgbG9zIHRvcXVlcyBlbiBWb2x2ZXIvQXRyYXMvQ2FuY2VsYXI6IFNPTE8gYWhpIHNlCiAgICAgICAgIHBlcm1pdGUgdW4gcmVncmVzbyB2b2x1bnRhcmlvIGhhY2lhIGF0cmFzLiAqLwogICAgICAvKiB2MTg6IHkgc2kgZWwgdG9xdWUgTk8gZXMgZGUgcmVncmVzbyBzaW5vIHNvYnJlIHVuIGJvdG9uL2VubGFjZSBkZSBhY2Npb24sCiAgICAgICAgIHNlIGxpYmVyYSBsYSBwYXVzYSBkZSBsYSBndWFyZGlhIChlbCB1c3VhcmlvIGRlY2lkaW8gYXZhbnphciBvIGFjdHVhcikuCiAgICAgICAgIExvcyB0b3F1ZXMgc29icmUgY2FtcG9zIGRlIHRleHRvIChlbCBub21icmUpIE5PIGxpYmVyYW4gbmFkYTogc2lndWVuCiAgICAgICAgIHByb3RlZ2lkb3MgbWllbnRyYXMgZXNjcmliZS4gKi8KICAgICAgdmFyIGVsPWUudGFyZ2V0LCBuPTAsIHR4PScnOwogICAgICB2YXIgZWxCb3Rvbj1udWxsLCBwcm9mQj0wLCBiMj1lLnRhcmdldDsKICAgICAgd2hpbGUoYjImJmIyIT09ZG9jdW1lbnQmJnByb2ZCPDUpewogICAgICAgIHZhciB0Z0I9YjIudGFnTmFtZXx8Jyc7CiAgICAgICAgaWYodGdCPT09J0JVVFRPTid8fHRnQj09PSdBJ3x8KHRnQj09PSdJTlBVVCcmJigoYjIudHlwZXx8JycpPT09J3N1Ym1pdCd8fChiMi50eXBlfHwnJyk9PT0nYnV0dG9uJ3x8KGIyLnR5cGV8fCcnKT09PSdpbWFnZScpKXx8KGIyLmdldEF0dHJpYnV0ZSYmYjIuZ2V0QXR0cmlidXRlKCdyb2xlJyk9PT0nYnV0dG9uJykpeyBlbEJvdG9uPWIyOyBicmVhazsgfQogICAgICAgIGIyPWIyLnBhcmVudE5vZGU7IHByb2ZCKys7CiAgICAgIH0KICAgICAgdmFyIGVUeD1lbCwgbkI9MDsKICAgICAgd2hpbGUoZVR4JiZlVHghPT1kb2N1bWVudCYmbkI8NCl7IHR4PSgoZVR4LnRleHRDb250ZW50fHwnJykrJycpLnJlcGxhY2UoL1xzKy9nLCcgJykudHJpbSgpOyBpZih0eCl7IGJyZWFrOyB9IGVUeD1lVHgucGFyZW50Tm9kZTsgbkIrKzsgfQogICAgICBpZih0eCYmL14odm9sdmVyfGF0cmFzfGF0clx1MDBFMXN8cmVncmVzYXJ8Y2FuY2VsYXIpL2kudGVzdCh0eCkpeyB0cnl7IFcuX196eVZvbHZlclRvY2Fkbz1EYXRlLm5vdygpOyBXLl9fenlMaWJyZVNlc2lvbjE4PXRydWU7IGxvZygndjE4OiByZWdyZXNvIHZvbHVudGFyaW8sIGd1YXJkaWEgZW4gcGF1c2EnKTsgfWNhdGNoKGUyKXt9IH0KICAgICAgZWxzZSBpZihlbEJvdG9uKXsgdHJ5eyBpZihXLl9fenlMaWJyZVNlc2lvbjE4KXsgVy5fX3p5TGlicmVTZXNpb24xOD1mYWxzZTsgbG9nKCd2MTg6IGFjY2lvbiBwcm9waWEgZGVsIHVzdWFyaW8sIGd1YXJkaWEgcmUtYXJtYWRhJyk7IH0gfWNhdGNoKGUzKXt9IH0KICAgIH0sdHJ1ZSk7CiAgfWNhdGNoKGVMKXt9CiAgdHJ5eyBpZihoYXlFeGl0bygpKXsgbW9zdHJhckV4aXRvU2lIYXkoKTsgfSB9Y2F0Y2goZUUpe30KICB0cnl7IHJlc2NhdGFyKCk7IH1jYXRjaChlUil7fQogIHRyeXsgaWYocmVzdGF1cmFyQ2xhdmVTZXNpb24oKSl7IHZhbGlkYXJDbGF2ZXMoKTsgfSB9Y2F0Y2goZUspe30KICB2YWxpZGFyUGFzbzEodHJ1ZSk7CiAgdmVyaWZpY2FyKCk7CiAgdHJ5eyBsaW1waWFMZWdhZG8oKTsgfWNhdGNoKGUpe30KICB0cnl7IHByZWVtcHRFbnZpbygpOyB9Y2F0Y2goZSl7fQogIHRyeXsgcGFuZWxEaWFnKCk7IH1jYXRjaChlKXt9CiAgdHJ5eyBzZXRJbnRlcnZhbChmdW5jdGlvbigpeyB0cnl7IGJhcnJlTWVuc2FqZXMoKTsgfWNhdGNoKGUpe30gfSwxNTAwKTsgfWNhdGNoKGUpe30KICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7IGNhcmdhckZhY2VBcGkoKS5jYXRjaChmdW5jdGlvbigpe30pOyB9LDE1MDApOwogIHRyeXsgaWYoZG9jdW1lbnQudGl0bGUuaW5kZXhPZignUkVWIEYnKTwwKXsgZG9jdW1lbnQudGl0bGU9ZG9jdW1lbnQudGl0bGUrJyBcdTAwQjcgUkVWIEYgdjE4JzsgfSB9Y2F0Y2goZSl7fQogIGxvZygnbnVjbGVvIHJldkYgdjE4IGFjdGl2by4gRXN0YWRvOicsIEpTT04uc3RyaW5naWZ5KEVTVCkpOwp9CnRyeXsKICBXLl9fWllSQV9SRVZGX1RFU1RfXz17dmFsaWRhclBhc28xOnZhbGlkYXJQYXNvMSx2ZXJpZmljYXI6dmVyaWZpY2FyLG1vc3RyYXJQYXNvOm1vc3RyYXJQYXNvLHBlcm1pdGlkb0hhc3RhOnBlcm1pdGlkb0hhc3RhLGVuZ2FuY2hhclBhc28xOmVuZ2FuY2hhclBhc28xLGxpbXBpYXJFcnJvcmVzUGFzbzE6bGltcGlhckVycm9yZXNQYXNvMSxlc3RhZG86ZnVuY3Rpb24oKXsgcmV0dXJuIEpTT04ucGFyc2UoSlNPTi5zdHJpbmdpZnkoRVNUKSk7IH0sbm9ybTpub3JtLGRldGVjdGFyTGFkbzpkZXRlY3RhckxhZG8sbm9tYnJlQ29pbmNpZGU6bm9tYnJlQ29pbmNpZGUsc2ltTm9tYnJlczpzaW1Ob21icmVzLG1yek5vbWJyZXM6bXJ6Tm9tYnJlcyx0b2RvT2tQYXJhQ3JlYXI6dG9kb09rUGFyYUNyZWFyLGRpYWc6ZnVuY3Rpb24oKXsgcmV0dXJuIEpTT04ucGFyc2UoSlNPTi5zdHJpbmdpZnkoRElBRykpOyB9LGFicmlyQ29uZmlybWFjaW9uTGVjdHVyYTphYnJpckNvbmZpcm1hY2lvbkxlY3R1cmEscG9uRXNjcml0bzpmdW5jdGlvbihzKXsgRVNULmVzY3JpdG89czsgfSxwb25Fc3RhZG86ZnVuY3Rpb24oYyl7IGZvcih2YXIgayBpbiBjKXsgRVNUW2tdPWNba107IH0gfSxmYWxsb1NlbGZpZTpmYWxsb1NlbGZpZSxub21icmVOb0NvaW5jaWRlTXNnOm5vbWJyZU5vQ29pbmNpZGVNc2cscmVzcGFsZGE6cmVzcGFsZGEscmVzY2F0YXI6cmVzY2F0YXIsZGVzY3VicmVDbGF2ZXM6ZGVzY3VicmVDbGF2ZXMsbGVlckNsYXZlczpsZWVyQ2xhdmVzLG1lbnNhamVDbGF2ZTptZW5zYWplQ2xhdmUsdmFsaWRhckNsYXZlczp2YWxpZGFyQ2xhdmVzLGNsYXZlc0xpc3RhczpjbGF2ZXNMaXN0YXMsZ3VhcmRhckNsYXZlU2VzaW9uOmd1YXJkYXJDbGF2ZVNlc2lvbixyZXN0YXVyYXJDbGF2ZVNlc2lvbjpyZXN0YXVyYXJDbGF2ZVNlc2lvbixoYXlFeGl0bzpoYXlFeGl0byxwYW5lbEV4aXRvOnBhbmVsRXhpdG8scGFuZWxSZWN1cGVyYTpwYW5lbFJlY3VwZXJhLHZvbHZlclRvY2Fkbzp2b2x2ZXJUb2NhZG8sZXNjcmliaWVuZG9Ob21icmU6ZXNjcmliaWVuZG9Ob21icmUsZXh0cmFlclppZDpleHRyYWVyWmlkLHF1aXRhQWNlbnRvczpxdWl0YUFjZW50b3MsQ0xWOmZ1bmN0aW9uKCl7IHJldHVybiB7bW9kbzpDTFYubW9kbyx0MTooQ0xWLmE/Q0xWLmEudmFsdWU6bnVsbCksdDI6KENMVi5iP0NMVi5iLnZhbHVlOm51bGwpfTsgfX07Cn1jYXRjaChlKXt9CmlmKGRvY3VtZW50LnJlYWR5U3RhdGU9PT0nbG9hZGluZycpewogIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ0RPTUNvbnRlbnRMb2FkZWQnLGluaXQpOwp9ZWxzZXsKICBpbml0KCk7Cn0KVy5fX1pZUkFfUkVWRF9JTkZPPWZ1bmN0aW9uKCl7IHJldHVybiBKU09OLnBhcnNlKEpTT04uc3RyaW5naWZ5KEVTVCkpOyB9Owp9KSgpOwo='))/*ZYRA-V6-END*/</script>
</body>
</html>
'''
            self._send(200, "text/html; charset=utf-8", _reg_html.encode("utf-8"))
            return
        if path == "/version":
            try:
                d_v = self._read_portal("version.txt")
            except Exception:
                d_v = b"0"
            self._send(200, "text/plain; charset=utf-8", d_v)
            return

        if path.startswith("/icon-") and path.endswith(".png"):
            try:
                datos_i = self._read_portal(path[1:])
            except Exception:
                self._send_html(404, NOT_FOUND_PAGE)
                return
            self._send(200, "image/png", datos_i)
            return
        if path == "/health":
            apps = {
                p: {"label": v["label"], "port": v["port"]}
                for p, v in APPS.items()
            }
            payload = json.dumps(
                {
                    "ok": True,
                    "service": "zyra-superapp",
                    "apps": apps,
                }
            ).encode("utf-8")
            self._send(200, "application/json", payload)
            return
        if path == "/entrar":
            self._send_html(200, self._pagina_entrar(""))
            return
        if path == "/salir":
            self.send_response(303)
            self.send_header("Set-Cookie", "zyra_zid=; Max-Age=0; Path=/; HttpOnly")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Location", "/entrar")
            self.end_headers()
            return
        if path == "/version":
            try:
                dv = self._read_portal("version.txt")
            except Exception:
                dv = b"0"
            self._send(200, "text/plain; charset=utf-8", dv)
            return
        if path == "/verificar":
            self._send_html(
                200,
                self._read_portal("verificar.html").decode("utf-8"),
            )
            return
        if path == "/manifest.json":
            self._send(200, "application/manifest+json", self._read_portal("manifest.json"))
            return
        if path == "/sw.js":
            self._send(200, "application/javascript; charset=utf-8", self._read_portal("sw.js"))
            return
        if path == "/icon-192.png":
            self._send(200, "image/png", self._read_portal("icon-192.png"))
            return
        if path == "/icon-512.png":
            self._send(200, "image/png", self._read_portal("icon-512.png"))
            return

        if path == "/verificar.js":
            self._send(
                200,
                "application/javascript; charset=utf-8",
                self._read_portal("verificar.js"),
            )
            return
        if path == "/mpe/register":
            self._send_html(200, "<!doctype html><html lang='es'><head><meta charset='utf-8'><meta http-equiv='refresh' content='0;url=/registro'><title>ZYRA</title></head><body></body></html>")
            return
        if path.startswith("/icon-") and path.endswith(".png"):
            try:
                datos_i = self._read_portal(path[1:])
            except Exception:
                self._send_html(404, NOT_FOUND_PAGE)
                return
            self._send(200, "image/png", datos_i)
            return
        for prefix, info in APPS.items():
            if path == prefix or path.startswith(prefix + "/"):
                self._proxy(
                    "http://127.0.0.1:"
                    + str(info["port"]) + self.path
                )
                return
        self._send_html(404, NOT_FOUND_PAGE)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/entrar":
            largo = int(self.headers.get("Content-Length", 0) or 0)
            crudo = self.rfile.read(largo).decode("utf-8") if largo else ""
            from urllib.parse import unquote_plus as _uq
            zid = ""
            clave = ""
            for par in crudo.split("&"):
                if "=" in par:
                    k, v = par.split("=", 1)
                    if k == "zid":
                        zid = _uq(v).strip()
                    elif k == "clave":
                        clave = _uq(v).strip()
            owner = os.environ.get("ZYRA_OWNER_ZID", "")
            clave_req = os.environ.get("ZYRA_CLAVE_DUENO", "")
            if zid == owner and clave_req and clave == clave_req:
                self.send_response(303)
                self.send_header("Set-Cookie", "zyra_zid=" + zid + "; Path=/; Max-Age=604800; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
                return
            cred_ok = False
            try:
                import sqlite3 as _sq, hashlib as _hs
                con = _sq.connect(str(DATA_DIR / "credenciales.db"))
                fila = con.execute("SELECT sal, hash FROM credenciales WHERE zid = ?", (zid,)).fetchone()
                con.close()
                if fila:
                    cred_ok = (_hs.sha256((fila[0] + clave).encode()).hexdigest() == fila[1])
            except Exception:
                cred_ok = False
            if cred_ok:
                self.send_response(303)
                self.send_header("Set-Cookie", "zyra_zid=" + zid + "; Path=/; Max-Age=604800; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
                return
            self._send_html(403, self._pagina_entrar(
                "ZID o clave incorrectos. Si no tienes ZID, registrate en Registro."))
            return
        if path == "/registro/nuevo":
            if not ZYRA_URL:
                self._send(503, "application/json", json.dumps({"ok": False, "error": "Red no configurada"}).encode())
                return
            largo = int(self.headers.get("Content-Length", 0) or 0)
            crudo = self.rfile.read(largo).decode("utf-8") if largo else ""
            try:
                dd = json.loads(crudo or "{}")
            except Exception:
                dd = {}
            nombre = str(dd.get("nombre", "")).strip()
            clave = str(dd.get("clave", ""))
            db64 = str(dd.get("doc_image_b64", ""))
            sb64 = str(dd.get("selfie_image_b64", ""))
            if len(nombre) < 3 or len(clave) < 8 or not db64 or not sb64:
                self._send(400, "application/json", json.dumps({"ok": False, "error": "Falta nombre, clave (min 8), documento o selfie"}).encode())
                return
            _pe = {"kind": "person", "name": nombre, "display_name": nombre, "actor": os.environ.get("ZYRA_ENROLL_ACTOR", "superapp"), "doc_image_b64": db64, "selfie_image_b64": sb64}
            _tdoc = str(dd.get("doc_type", "")).strip()
            if _tdoc:
                _pe["doc_kind"] = _tdoc
                if _tdoc == "dui":
                    _pe["doc_country"] = "SV"
                elif _tdoc in ("licencia", "id_usa"):
                    _pe["doc_country"] = "US"
            _ndoc = str(dd.get("doc_number", "")).strip()
            if _ndoc:
                _pe["doc_number"] = _ndoc
            payload_e = json.dumps(_pe).encode("utf-8")
            q_e = urllib.request.Request(ZYRA_URL + "/identity/enroll", data=payload_e, method="POST")
            q_e.add_header("Content-Type", "application/json")
            q_e.add_header("Authorization", "Bearer " + os.environ.get("ZYRA_API_TOKEN", ""))
            cuerpo_e = ""
            status_e = None
            try:
                with urllib.request.urlopen(q_e, timeout=60) as re_:
                    status_e = re_.status
                    cuerpo_e = re_.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as he_:
                status_e = he_.code
                try:
                    cuerpo_e = he_.read().decode("utf-8", "replace")
                except Exception:
                    cuerpo_e = ""
            except Exception as ex_:
                self._send(502, "application/json", json.dumps({"ok": False, "error": "Sin conexion con la Red (host configurado: " + (ZYRA_URL.split("//")[-1].split("/")[0] if ZYRA_URL else "(vacio)") + "): " + str(ex_)[:180]}).encode())
                return
            try:
                je_ = json.loads(cuerpo_e or "{}")
            except Exception:
                je_ = {}
            if status_e in (200, 201) and je_.get("ok") is True:
                dx_ = je_.get("data") or je_
                if isinstance(dx_, dict):
                    zid = str(dx_.get("zid") or dx_.get("identity_id") or dx_.get("id") or "")
            elif "biometrics_unavailable" in cuerpo_e or "face engine not installed" in cuerpo_e:
                try:
                    import sqlite3 as _sq2
                    con2 = _sq2.connect(str(DATA_DIR / "credenciales.db"))
                    con2.execute("CREATE TABLE IF NOT EXISTS pendientes (nombre TEXT, doc_b64 TEXT, selfie_b64 TEXT, fecha TEXT)")
                    con2.execute("INSERT INTO pendientes VALUES (?, ?, ?, datetime('now'))", (nombre, db64, sb64))
                    con2.commit()
                    con2.close()
                except Exception:
                    pass
                self._send(200, "application/json", json.dumps({"ok": False, "codigo": "mantenimiento", "error": "Biometria en mantenimiento. Tu solicitud quedo guardada."}).encode())
                return
            else:
                emsg = ""
                if isinstance(je_.get("error"), dict):
                    emsg = str(je_["error"].get("message", ""))
            if je_["error"].get("reason"):
                emsg += " | razon: " + str(je_["error"].get("reason"))[:220]
            if je_["error"].get("case_status"):
                emsg += " | estado: " + str(je_["error"].get("case_status"))
                if not emsg:
                    emsg = cuerpo_e[:250] or ("HTTP " + str(status_e))
                self._send(502, "application/json", json.dumps({"ok": False, "error": emsg}).encode())
                return
            zid = locals().get("zid", "")
            if not zid and status_e in (200, 201) and isinstance(je_, dict):
                dx2 = je_.get("data") or je_
                if isinstance(dx2, dict):
                    zid = str(dx2.get("zid") or dx2.get("identity_id") or dx2.get("id") or "")
                    if not zid and isinstance(dx2.get("identity"), dict):
                        zid = str(dx2["identity"].get("zid") or "")
            if not zid:
                self._send(500, "application/json", json.dumps({"ok": False, "error": "La Red no devolvio ZID"}).encode())
                return
            import secrets as _sc, hashlib as _hs, sqlite3 as _sq
            sal = _sc.token_hex(16)
            hc = _hs.sha256((sal + clave).encode()).hexdigest()
            con = _sq.connect(str(DATA_DIR / "credenciales.db"))
            con.execute("CREATE TABLE IF NOT EXISTS credenciales (zid TEXT PRIMARY KEY, sal TEXT, hash TEXT)")
            con.execute("INSERT OR REPLACE INTO credenciales VALUES (?, ?, ?)", (zid, sal, hc))
            con.commit()
            con.close()
            self._send(200, "application/json", json.dumps({"ok": True, "zid": zid}).encode())
            return
        if path == "/verify":
            if not ZYRA_URL:
                self._send_html(
                    503,
                    ERROR_PAGE.replace(
                        "__MSG__", "ZYRA_URL no configurada"
                    ),
                )
                return
            self._proxy(ZYRA_URL + "/verify")
            return
        for prefix, info in APPS.items():
            if path == prefix or path.startswith(prefix + "/"):
                self._proxy(
                    "http://127.0.0.1:"
                    + str(info["port"]) + self.path
                )
                return
        self._send_html(404, NOT_FOUND_PAGE)

    def log_message(self, fmt, *args):
        print("[superapp] " + (fmt % args))

def main():
    print("[superapp] data dir: " + str(DATA_DIR))
    if not ZYRA_URL:
        print(
            "[superapp] WARNING: ZYRA_URL/ZYRA_HOST no configurada"
            " - apps degradadas"
        )
    errors = boot_apps()
    if errors:
        print("[superapp] STARTUP ERRORS: " + str(errors))
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), PortalHandler)
    print(
        "[superapp] LIVE on port " + str(PORT)
        + " - apps: " + str(list(APPS.keys()))
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    main()
