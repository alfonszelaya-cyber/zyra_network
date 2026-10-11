"""EX-4: curso con evaluacion real + certificado firmado y sellado."""
import json

import pytest

from apps.laboratorio.infrastructure.providers.presentation_remote import ModoCurso
from apps.laboratorio.infrastructure.security.signing import Firmador
from apps.laboratorio.tests.conftest import OBJETOS, assert_2xx


class _PresFalsa:
    id = "pres-x"
    titulo = "Curso de prueba"
    pasos = []


class _RepoFalso:
    @staticmethod
    def obtener_exigir(pid):
        return _PresFalsa()


class _OutboxFalso:
    def __init__(self):
        self.items = []
        self.enviadas = []

    def encolar(self, ev, dest, carga):
        self.items.append((ev, dest, carga))
        return len(self.items)

    def procesar(self, entregador):
        for it in self.items:
            self.enviadas.append(it)
            entregador(it[1], it[2])
        n = len(self.items)
        self.items = []
        return {"procesados": n, "enviados": n, "reprogramados": 0, "abandonados": 0}

    def estadisticas(self):
        return {"pendiente": len(self.items), "enviado": len(self.enviadas), "error": 0}


class _ClienteFalso:
    @staticmethod
    def entregar(destino, carga):
        return {"sellado": True}


PREGUNTAS = [
    {"texto": "Que es ZYRA?", "opciones": ["Una red", "Un coche"], "correcta": 0},
    {"texto": "2+2?", "opciones": ["3", "4"], "correcta": 1},
]


def _modo():
    return ModoCurso(_RepoFalso(), _OutboxFalso(),
                     Firmador("clave-de-test-1234567890abcd"), cliente=_ClienteFalso())


def test_crear_curso_valida_preguntas():
    assert _modo().crear_curso("pres-x", PREGUNTAS, 0.7)["preguntas"] == 2
    with pytest.raises(ValueError):
        _modo().crear_curso("pres-x", [{"texto": "mala", "opciones": ["a"], "correcta": 0}])


def test_responder_califica_automatico():
    modo = _modo()
    curso = modo.crear_curso("pres-x", PREGUNTAS)["curso"]
    r1 = modo.responder(curso, "a1", [0, 1])
    assert r1["puntaje"] == 1.0 and r1["aprobado"] is True
    r2 = modo.responder(curso, "a2", [1, 0])
    assert r2["puntaje"] == 0.0 and r2["aprobado"] is False


def test_certificar_exige_aprobado():
    modo = _modo()
    curso = modo.crear_curso("pres-x", PREGUNTAS)["curso"]
    with pytest.raises(ValueError):
        modo.certificar(curso, "nadie")
    modo.responder(curso, "a2", [1, 0])
    with pytest.raises(ValueError):
        modo.certificar(curso, "a2")


def test_certificado_firmado_y_sellado():
    modo = _modo()
    curso = modo.crear_curso("pres-x", PREGUNTAS)["curso"]
    modo.responder(curso, "a1", [0, 1])
    res = modo.certificar(curso, "a1")
    assert res["certificado"]["algoritmo"] == "hmac-sha256"
    assert res["estado_red"] == "sellado_en_zyra"


def test_curso_completo_por_http(app, despachar):
    _s, _h, datos = despachar("POST", "/laboratorio/api/v1/projects", json.dumps({
        "titulo": "Proy curso", "tipo": "negocio"}).encode("utf-8"))
    assert_2xx(_s, datos)
    proyecto_id = datos["datos"]["proyecto"]["id"]
    _ss, _hsc, datos_sc = despachar(
        "POST", "/laboratorio/api/v1/projects/" + proyecto_id + "/scenes",
        json.dumps({"nombre": "S", "objetos": OBJETOS}).encode("utf-8"))
    assert_2xx(_ss, datos_sc)
    escena_id = datos_sc["datos"]["escena"]["id"]
    status, _h2, datos2 = despachar(
        "POST", "/laboratorio/api/v1/projects/" + proyecto_id + "/presentations",
        json.dumps({"titulo": "Capacitacion", "pasos": [
            {"titulo": "P1", "contenido": "c", "duracion_segundos": 10, "escena_id": escena_id},
        ]}).encode("utf-8"))
    assert_2xx(status, datos2)
    pid = datos2["datos"]["presentacion"]["id"]
    status3, _h3, datos3 = despachar(
        "POST", "/laboratorio/api/v1/presentations/" + pid + "/curso",
        json.dumps({"preguntas": PREGUNTAS}).encode("utf-8"))
    assert_2xx(status3, datos3)
    curso_id = datos3["datos"]["curso"]
    status4, _h4, datos4 = despachar(
        "POST", "/laboratorio/api/v1/presentations/curso/" + curso_id + "/responder",
        json.dumps({"respuestas": [0, 1]}).encode("utf-8"))
    assert_2xx(status4, datos4)
    assert datos4["datos"]["aprobado"] is True
    status5, _h5, datos5 = despachar(
        "POST", "/laboratorio/api/v1/presentations/curso/" + curso_id + "/certificar", b"")
    assert_2xx(status5, datos5)
    assert datos5["datos"]["certificado"]["firma"]
    outbox = app.contenedor.obtener("outbox")
    stats = outbox.estadisticas()
    assert stats["pendiente"] >= 1 or stats["error"] >= 1
