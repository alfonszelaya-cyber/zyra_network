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
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,Arial;background:#12162e;color:#e8eaf6;padding:16px;max-width:520px;margin:0 auto}
h1{font-size:22px;text-align:center;margin:8px 0 4px;color:#fff}
.sub{text-align:center;color:#9aa0c3;font-size:13px;margin-bottom:14px}
label{display:block;color:#9aa0c3;font-size:14px;margin:14px 0 6px}
input,select{width:100%;padding:12px;border-radius:10px;border:1px solid #2a2f55;background:#0d1126;color:#fff;font-size:16px}
input[type=file]{padding:9px;font-size:13px}
.estado{text-align:center;font-size:13px;color:#9aa0c3;padding:6px;min-height:20px}
.preview{display:none;width:100%;border-radius:10px;margin-top:6px}
.videozona{position:relative;border-radius:12px;overflow:hidden;margin-top:6px;background:#000}
video{width:100%;display:block;transform:scaleX(-1)}
.ov{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none}
#zonaEdit{display:none;margin-top:8px;background:#0d1126;border:1px solid #2a2f55;border-radius:12px;padding:10px}
#cvEdit{width:100%;touch-action:none;border-radius:8px;display:block}
button{width:100%;margin-top:8px;padding:12px;border:0;border-radius:10px;font-size:15px;font-weight:700;color:#fff;background:#262b52}
button.ok{background:#1f6f43}
button.big{margin-top:18px;padding:14px;font-size:17px;font-weight:800;background:linear-gradient(90deg,#7c5cff,#ff5c8a)}
.fila{display:flex;gap:8px}
.fila button{flex:1;margin-top:8px;font-size:13px;padding:10px}
a{color:#a78bfa}
#resp{margin-top:14px}
.zid{font-size:20px;font-weight:800;color:#3fb950;letter-spacing:1px}
</style>
</head>
<body>
<h1>Crear mi ZID</h1>
<p class="sub">Red de confianza digital</p>
<form onsubmit="return enviar(event)">
<label>Nombre completo</label>
<input id="nombre" required>
<label>Tipo de documento</label>
<select id="tipoDoc" onchange="cambioTipo()">
<option value="dui">DUI (2 lados)</option>
<option value="pasaporte">Pasaporte (1 cara)</option>
</select>
<label>1) Documento: lado frontal</label>
<input type="file" accept="image/*" capture="environment" onchange="cargarDoc(this,'F')">
<div class="estado" id="stF"></div>
<img class="preview" id="pF" alt="" onclick="reeditar('F')">
<label id="lbA">2) Documento: lado de atras (solo DUI)</label>
<input type="file" accept="image/*" capture="environment" onchange="cargarDoc(this,'A')">
<div class="estado" id="stA"></div>
<img class="preview" id="pA" alt="" onclick="reeditar('A')">
<div id="zonaEdit">
<p style="color:#9aa0c3;font-size:13px;text-align:center">Ajusta el recuadro verde hasta cubrir TODA la tarjeta. Arrastralo con el dedo. La bola verde lo agranda.</p>
<canvas id="cvEdit"></canvas>
<div class="fila">
<button type="button" onclick="masGrande(1.18)">+ Grande</button>
<button type="button" onclick="masGrande(0.85)">- Chico</button>
<button type="button" onclick="centrarFrame()">Centrar</button>
</div>
<button type="button" class="ok" onclick="recortarDoc()">Recortar y GUARDAR documento</button>
<button type="button" onclick="usarFotoCompleta()">Usar foto completa sin recortar</button>
</div>
<label>3) Selfie en vivo con prueba de vida</label>
<div class="videozona"><video id="v" autoplay playsinline muted></video><canvas class="ov" id="ov"></canvas></div>
<div class="estado" id="stV">Abriendo camara y preparando detector...</div>
<button type="button" id="bSelfie" onclick="capturarSelfie()">Capturar selfie</button>
<img class="preview" id="pS" alt="">
<label>4) Crea tu clave de acceso (min 8)</label>
<input type="password" id="clave">
<label>Repite la clave</label>
<input type="password" id="clave2">
<button class="big" type="submit">Crear mi ZID</button>
</form>
<div id="resp"></div>
<p style="text-align:center;margin-top:14px"><a href="/">Volver</a> | <a href="/entrar">Ya tengo ZID</a></p>
<script>
var DF="",DA="",DS="";
var docImg=null,docLado="",docCrudoF="",docCrudoA="";
var fr={x:0,y:0,w:0,h:0},editListo=false;
var cam=null,cara=null,ultimoEAR=null,hayLandmarks=false,detTipo="",apiCara=null,capturando=false;
function R(id){return document.getElementById(id)}
function kb(s){return Math.round(s.length*3/4/1024)}
function dormir(ms){return new Promise(function(res){setTimeout(res,ms)})}
function zyComprimir(dataUrl,maxLado,calidad){return new Promise(function(res){var im=new Image();im.onload=function(){var w=im.width,h=im.height,e=Math.min(1,maxLado/Math.max(w,h)),c=document.createElement("canvas");c.width=Math.round(w*e);c.height=Math.round(h*e);c.getContext("2d").drawImage(im,0,0,c.width,c.height);res(c.toDataURL("image/jpeg",calidad).split(",").pop())};im.onerror=function(){res(dataUrl.split(",").pop())};im.src=dataUrl})}
function luma(dataUrl){return new Promise(function(res){var im=new Image();im.onload=function(){var c=document.createElement("canvas");c.width=40;c.height=40;c.getContext("2d").drawImage(im,0,0,40,40);var d=c.getContext("2d").getImageData(0,0,40,40).data,t=0;for(var i=0;i<d.length;i+=4){t+=0.299*d[i]+0.587*d[i+1]+0.114*d[i+2]}res(t/(d.length/4))};im.onerror=function(){res(99)};im.src=dataUrl})}
function cargarScript(s){return new Promise(function(res,rej){var e=document.createElement("script");e.src=s;e.onload=res;e.onerror=rej;document.head.appendChild(e)})}
async function ensureCara(){
if(detTipo){return detTipo}
try{
await cargarScript("https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js");
await faceapi.nets.tinyFaceDetector.loadFromUri("https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@0.22.2/weights");
detTipo="faceapi";
try{await faceapi.nets.faceLandmark68TinyNet.loadFromUri("https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@0.22.2/weights");hayLandmarks=true}catch(e2){hayLandmarks=false}
return detTipo;
}catch(e){}
try{if(window.FaceDetector){apiCara=new FaceDetector({fastMode:true,maxDetectedFaces:1});detTipo="nativo";return detTipo}}catch(e2){}
return "";
}
function ear6(p){var d=function(a,b){return Math.hypot(a.x-b.x,a.y-b.y)};return (d(p[1],p[5])+d(p[2],p[4]))/(2*d(p[0],p[3]))}
async function cajaEnVideo(v){
var t=await ensureCara();if(!t){return null}
try{
if(t=="faceapi"){
var op=new faceapi.TinyFaceDetectorOptions({inputSize:320,scoreThreshold:0.3});
if(hayLandmarks){
var r2=await faceapi.detectSingleFace(v,op).withFaceLandmarks(true);
if(r2){try{ultimoEAR=(ear6(r2.landmarks.getLeftEye())+ear6(r2.landmarks.getRightEye()))/2}catch(e3){ultimoEAR=null}var b=r2.detection.box;return {x:b.x,y:b.y,w:b.width,h:b.height}}
ultimoEAR=null;return null;
}
ultimoEAR=null;
var r3=await faceapi.detectSingleFace(v,op);
if(r3){var b3=r3.box;return {x:b3.x,y:b3.y,w:b3.width,h:b3.height}}
return null;
}
if(t=="nativo"){var fs=await apiCara.detect(v);if(fs.length){var b=fs[0].boundingBox;return {x:b.x,y:b.y,w:b.width,h:b.height}}}
}catch(e){}
return null;
}
async function cajaEnEscalada(im){
var t=await ensureCara();if(!t){return null}
var MAXD=640;
var sc=Math.min(1,MAXD/Math.max(im.width,im.height));
var c=document.createElement("canvas");
c.width=Math.round(im.width*sc);c.height=Math.round(im.height*sc);
c.getContext("2d").drawImage(im,0,0,c.width,c.height);
try{
if(t=="faceapi"){
var r=await faceapi.detectSingleFace(c,new faceapi.TinyFaceDetectorOptions({inputSize:416,scoreThreshold:0.25}));
if(r){var b=r.box;return {x:b.x/sc,y:b.y/sc,w:b.width/sc,h:b.height/sc}}
}else if(t=="nativo"){
var fs=await apiCara.detect(c);
if(fs.length){var b2=fs[0].boundingBox;return {x:b2.x/sc,y:b2.y/sc,w:b2.width/sc,h:b2.height/sc}}
}
}catch(e){}
return null;
}
async function loop(){
var v=R("v"),ov=R("ov");
setInterval(async function(){
if(v.readyState<2){return}
var vw=v.videoWidth,vh=v.videoHeight;if(!vw){return}
if(ov.width!=vw){ov.width=vw;ov.height=vh}
var g=ov.getContext("2d");g.clearRect(0,0,ov.width,ov.height);
try{
var caja=await cajaEnVideo(v);
cara=caja;
if(caja){
var grande=(caja.w/vw)>0.12;
var cx=caja.x+caja.w/2,cy=caja.y+caja.h/2,rx=caja.w*0.62,ry=caja.h*0.74;
g.strokeStyle=grande?"#3fb950":"#f0b429";g.lineWidth=4;
g.beginPath();g.ellipse(cx,cy,rx,ry,0,0,6.3);g.stroke();
if(!capturando){R("stV").innerHTML=grande?"Rostro detectado: pulsa Capturar selfie":"Acerca tu rostro";R("stV").style.color=grande?"#3fb950":"#f0b429"}
}else{
ultimoEAR=null;
g.strokeStyle="#f85149";g.lineWidth=3;g.beginPath();g.ellipse(ov.width/2,ov.height/2,ov.width*0.22,ov.height*0.32,0,0,6.3);g.stroke();
if(!capturando){R("stV").innerHTML="Buscando tu rostro...";R("stV").style.color="#9aa0c3"}
}
}catch(e){}
},200);
}
async function abrirCam(){
try{
cam=await navigator.mediaDevices.getUserMedia({video:{facingMode:"user",width:{ideal:640},height:{ideal:480}}});
var v=R("v");v.srcObject=cam;
R("stV").innerHTML="Camara activa. Espera el ovalo verde.";
loop();
}catch(e){R("stV").innerHTML="No se pudo abrir la camara: "+e}
}
function esperarParpadeo(ms){
return new Promise(function(res){
var t0=Date.now(),cerrado=false;
var iv=setInterval(function(){
var e=ultimoEAR;
var quedan=Math.ceil((ms-(Date.now()-t0))/1000);
if(e!=null){
if(e<0.19){cerrado=true}
if(cerrado&&e>0.23){clearInterval(iv);res(true);return}
}
if(Date.now()-t0>ms){clearInterval(iv);res(false);return}
R("stV").innerHTML=(cerrado?"Abre los ojos...":"PARPADEA AHORA... ")+quedan+"s";
R("stV").style.color="#f0b429";
},150);
});
}
async function capturarSelfie(){
var st=R("stV"),v=R("v");
if(capturando){return false}
if(!cam){R("resp").innerHTML="<p style='color:#f85149'>La camara no esta activa.</p>";return false}
if(v.videoWidth<=0){st.innerHTML="La camara aun esta abriendo, espera 2 segundos.";st.style.color="#f0b429";return false}
capturando=true;R("bSelfie").disabled=true;
try{
if(cara==null){
st.innerHTML="Buscando tu rostro...";st.style.color="#f0b429";
for(var i=0;i<10&&!cara;i++){await dormir(300)}
}
if(cara==null){st.innerHTML="No veo tu rostro: colocate frente a la camara con buena luz.";st.style.color="#f85149";capturando=false;R("bSelfie").disabled=false;return false}
if((cara.w/v.videoWidth)<=0.12){st.innerHTML="Acerca tu rostro al ovalo.";st.style.color="#f0b429";capturando=false;R("bSelfie").disabled=false;return false}
var vida="sin confirmar";
if(hayLandmarks){
var ok=await esperarParpadeo(5000);
if(ok){vida="parpadeo confirmado"}else{vida="capturada sin parpadeo visible"}
}else{
st.innerHTML="Mantente quieto...";st.style.color="#f0b429";
await dormir(800);
}
var c=document.createElement("canvas");c.width=v.videoWidth;c.height=v.videoHeight;
var g=c.getContext("2d");g.translate(c.width,0);g.scale(-1,1);g.drawImage(v,0,0);
var crudo=c.toDataURL("image/jpeg",0.85);
var comp=await zyComprimir(crudo,720,0.65);
DS=comp;var pv=R("pS");pv.src="data:image/jpeg;base64,"+comp;pv.style.display="block";
st.innerHTML="SELFIE GUARDADA: "+kb(comp)+" KB ("+vida+")";st.style.color="#3fb950";
}catch(e){
st.innerHTML="Error al capturar: "+e;st.style.color="#f85149";
}
capturando=false;R("bSelfie").disabled=false;
return true;
}
async function cargarDoc(inp,lado){
var f=inp.files&&inp.files[0];if(!f){return}
var fr2=new FileReader();
fr2.onload=async function(){
var crudo=fr2.result;
var L=await luma(crudo);
if(L<45){R("st"+lado).innerHTML="Foto muy oscura (luz "+Math.round(L)+"/100). Repitela con buena luz.";R("st"+lado).style.color="#f85149";inp.value="";return}
var comp=await zyComprimir(crudo,1200,0.78);
abrirEditor(lado,comp);
};
fr2.readAsDataURL(f);
}
function abrirEditor(lado,comp){
docLado=lado;
if(lado=="F"){docCrudoF=comp}else{docCrudoA=comp}
var im=new Image();
R("st"+lado).innerHTML="Abriendo editor...";
im.onload=async function(){
docImg=im;
var fw=im.width*0.78,fh=fw/1.586;
if(fh>im.height*0.9){fh=im.height*0.9;fw=fh*1.586}
fr={x:(im.width-fw)/2,y:(im.height-fh)/2,w:fw,h:fh};
R("st"+lado).innerHTML="Analizando documento...";
try{
var caja=await cajaEnEscalada(im);
if(caja){
var fw2=Math.max(im.width*0.5,Math.min(im.width*0.96,caja.w*3.9));
var fh2=fw2/1.586;
if(fh2>im.height*0.95){fh2=im.height*0.95;fw2=fh2*1.586}
var nx=(caja.x+caja.w/2)-fw2*0.26;
var ny=(caja.y+caja.h/2)-fh2*0.45;
if(nx<4){nx=4}
if(ny<4){ny=4}
if(nx+fw2>im.width-4){nx=im.width-4-fw2}
if(ny+fh2>im.height-4){ny=im.height-4-fh2}
fr={x:nx,y:ny,w:fw2,h:fh2};
R("st"+lado).innerHTML="Rostro de la tarjeta visto. AJUSTA el recuadro si no cubre la tarjeta COMPLETA.";
}else{
R("st"+lado).innerHTML="Coloca el recuadro sobre la tarjeta completa (arrastra, o usa + Grande).";
}
}catch(e){}
clampFrame();
pintarEditor();
R("zonaEdit").style.display="block";
if(!editListo){iniciarEdit();editListo=true}
};
im.src="data:image/jpeg;base64,"+comp;
}
function pintarEditor(){
var cv=R("cvEdit"),g=cv.getContext("2d"),im=docImg;
if(!im){return}
var maxW=Math.min(480,im.width);
cv.width=maxW;cv.height=Math.round(maxW*im.height/im.width);
var e=cv.width/im.width;
g.clearRect(0,0,cv.width,cv.height);
g.drawImage(im,0,0,cv.width,cv.height);
g.fillStyle="rgba(0,0,0,0.45)";
g.fillRect(0,0,cv.width,fr.y*e);
g.fillRect(0,(fr.y+fr.h)*e,cv.width,cv.height-(fr.y+fr.h)*e);
g.fillRect(0,fr.y*e,fr.x*e,fr.h*e);
g.fillRect((fr.x+fr.w)*e,fr.y*e,cv.width-(fr.x+fr.w)*e,fr.h*e);
g.strokeStyle="#3fb950";g.lineWidth=3;
g.strokeRect(fr.x*e,fr.y*e,fr.w*e,fr.h*e);
g.fillStyle="#3fb950";
g.beginPath();g.arc((fr.x+fr.w)*e,(fr.y+fr.h)*e,14,0,6.3);g.fill();
}
function clampFrame(){
if(!docImg){return}
if(fr.w>docImg.width){fr.w=docImg.width;fr.h=fr.w/1.586}
if(fr.h>docImg.height){fr.h=docImg.height;fr.w=fr.h*1.586}
if(fr.x<0){fr.x=0}
if(fr.y<0){fr.y=0}
if(fr.x+fr.w>docImg.width){fr.x=docImg.width-fr.w}
if(fr.y+fr.h>docImg.height){fr.y=docImg.height-fr.h}
}
function masGrande(f){
if(!docImg){return}
var cx=fr.x+fr.w/2,cy=fr.y+fr.h/2;
var nw=Math.max(80,Math.min(docImg.width,fr.w*f));
fr.w=nw;fr.h=nw/1.586;
fr.x=cx-nw/2;fr.y=cy-fr.h/2;
clampFrame();pintarEditor();
}
function centrarFrame(){
if(!docImg){return}
var fw=docImg.width*0.78,fh=fw/1.586;
if(fh>docImg.height*0.9){fh=docImg.height*0.9;fw=fh*1.586}
fr={x:(docImg.width-fw)/2,y:(docImg.height-fh)/2,w:fw,h:fh};
clampFrame();pintarEditor();
}
function iniciarEdit(){
var cv=R("cvEdit");
var arr=null,base=null;
function pos(ev){var r=cv.getBoundingClientRect();var t=(ev.touches&&ev.touches[0])||ev;return {x:(t.clientX-r.left)*cv.width/r.width,y:(t.clientY-r.top)*cv.height/r.height}}
function abajo(ev){
if(!docImg){return}
var p=pos(ev);var e=cv.width/docImg.width;
var hx=(fr.x+fr.w)*e,hy=(fr.y+fr.h)*e;
arr=(Math.hypot(p.x-hx,p.y-hy)<48)?"s":"m";
base={px:p.x,py:p.y,fx:fr.x,fy:fr.y,fw:fr.w};
ev.preventDefault();
}
function mover(ev){
if(!arr||!docImg){return}
var p=pos(ev);var dx=p.x-base.px,dy=p.y-base.py;
if(arr=="m"){fr.x=base.fx+dx;fr.y=base.fy+dy}
else{var w=Math.max(80,base.fw+dx);fr.w=w;fr.h=w/1.586}
clampFrame();pintarEditor();ev.preventDefault();
}
cv.addEventListener("pointerdown",abajo,false);
cv.addEventListener("pointermove",mover,false);
["pointerup","pointercancel","pointerleave"].forEach(function(t){cv.addEventListener(t,function(){arr=null},false)});
}
function guardarEn(docLadoSel,comp,txt){
if(docLadoSel=="F"){DF=comp}else{DA=comp}
var pv=R(docLadoSel=="F"?"pF":"pA");
pv.src="data:image/jpeg;base64,"+comp;pv.style.display="block";
var st=R("st"+docLadoSel);
st.innerHTML=txt+" — toca la foto para corregir el marco";st.style.color="#3fb950";
R("zonaEdit").style.display="none";docImg=null;
}
function recortarDoc(){
if(!docImg){return}
var c=document.createElement("canvas");
c.width=Math.round(fr.w);c.height=Math.round(fr.h);
c.getContext("2d").drawImage(docImg,fr.x,fr.y,fr.w,fr.h,0,0,c.width,c.height);
var comp=c.toDataURL("image/jpeg",0.8).split(",").pop();
guardarEn(docLado,comp,"GUARDADO: "+kb(comp)+" KB (documento completo)");
}
function usarFotoCompleta(){
var comp=docLado=="F"?docCrudoF:docCrudoA;
if(!comp){return}
guardarEn(docLado,comp,"GUARDADO COMPLETO: "+kb(comp)+" KB (sin recortar)");
}
function reeditar(lado){
var comp=lado=="F"?docCrudoF:docCrudoA;
if(comp){abrirEditor(lado,comp)}
}
function cambioTipo(){var d=R("tipoDoc").value=="dui";R("lbA").style.display=d?"block":"none";if(!d){DA="";docCrudoA="";R("stA").innerHTML="";R("pA").style.display="none"}}
async function enviar(ev){ev.preventDefault();var Rr=R("resp");
var c1=R("clave").value,c2=R("clave2").value;
if(c1!==c2){Rr.innerHTML="<p style='color:#f85149'>Las claves no coinciden.</p>";return false}
if(R("nombre").value.trim().length<3){Rr.innerHTML="<p style='color:#f85149'>Falta tu nombre completo.</p>";return false}
if(c1.length<8){Rr.innerHTML="<p style='color:#f85149'>La clave necesita minimo 8 caracteres.</p>";return false}
if(!DF){Rr.innerHTML="<p style='color:#f85149'>Falta GUARDAR el documento frontal (Recortar y GUARDAR, o Usar foto completa).</p>";return false}
if(R("tipoDoc").value=="dui"&&!DA){Rr.innerHTML="<p style='color:#f85149'>Falta GUARDAR el lado de atras del DUI.</p>";return false}
if(!DS){Rr.innerHTML="<p style='color:#f85149'>Falta la selfie: pulsa Capturar selfie (guarada SIEMPRE que vea tu rostro).</p>";return false}
Rr.innerHTML="<p style='color:#8b949e'>Enviando a la Red ("+kb(DF)+" y "+kb(DS)+" KB) y verificando biometria...</p>";
try{var r=await fetch("/registro/nuevo",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({nombre:R("nombre").value.trim(),clave:c1,doc_image_b64:DF,doc_back_b64:DA,selfie_image_b64:DS,doc_type:R("tipoDoc").value})});
var j=await r.json();
if(j.ok&&j.zid){Rr.innerHTML="<div style='background:#0f2a1a;border:1px solid #238636;border-radius:12px;padding:14px'><p style='color:#3fb950;font-weight:800;font-size:17px'>REGISTRO EXITOSO</p><p>Tu ZID unico fue creado:</p><p class='zid'>"+j.zid+"</p><p>Guarda tu ZID y tu clave. Nadie mas puede crearlo.</p><p><a href='/entrar'>ENTRAR AHORA</a></p></div>";}
else if(j.codigo==="mantenimiento"){Rr.innerHTML="<div style='background:#2a2410;border:1px solid #f0b429;border-radius:12px;padding:14px'><p style='color:#f0b429;font-weight:800'>BIOMETRIA EN MANTENIMIENTO</p><p>"+(j.error||"")+"</p><p>Tu solicitud quedo guardada.</p><p><a href='/registro'>Volver a intentar</a></p></div>";}
else{Rr.innerHTML="<p style='color:#f85149;font-weight:700'>NO SE PUDO CREAR EL ZID</p><p>"+(j.error||"Motivo desconocido")+"</p>";}}
catch(e){Rr.innerHTML="<div style='background:#2a1414;border:1px solid #f85149;border-radius:12px;padding:14px'><p style='color:#f85149;font-weight:700'>La Red no respondio</p><p>Detalle tecnico: "+e+"</p><p style='color:#8b949e'>Envia este detalle para corregirlo.</p></div>";}
return false}
abrirCam();
</script>
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
            payload_e = json.dumps({"kind": "person", "name": nombre, "display_name": nombre, "actor": os.environ.get("ZYRA_ENROLL_ACTOR", "superapp"), "doc_image_b64": db64, "selfie_image_b64": sb64}).encode("utf-8")
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
