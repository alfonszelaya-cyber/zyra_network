"""Casos de uso de presentaciones: crear, reproducir y sellar.

Reproducir genera un slideshow SVG real (auto-avanzado) a partir
de las escenas reales. Sellar encola el documento en el outbox
existente hacia ZYRA (flujo LAB-CORE, cero duplicacion).
"""
from apps.laboratorio.application.workflows.presentation_workflow import slideshow_svg
from apps.laboratorio.domain.history import EntradaHistorial
from apps.laboratorio.domain.presentation import Presentacion
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.shared.helpers.hashing import sha256_texto
from apps.laboratorio.shared.models.identifiers import nuevo_id


class CasoCrearPresentacion:
    def __init__(self, repo_presentaciones, repo_proyectos, repo_historial, auditoria):
        self._presentaciones = repo_presentaciones
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._auditoria = auditoria

    def ejecutar(self, identidad, proyecto_id: str, datos: dict) -> dict:
        proyecto = self._proyectos.obtener_exigir(proyecto_id)
        PoliticaProyecto.exigir_editar(proyecto, identidad)
        if not isinstance(datos, dict):
            raise ValueError("Cuerpo invalido.")
        titulo = str(datos.get("titulo", "")).strip()
        if not titulo:
            raise ValueError("La presentacion requiere titulo.")
        pasos = datos.get("pasos", [])
        if not isinstance(pasos, list) or not pasos:
            raise ValueError("La presentacion requiere al menos un paso.")
        presentacion = Presentacion(
            id=nuevo_id("prs"), proyecto_id=proyecto.id, titulo=titulo[:200],
        )
        for paso in pasos:
            if not isinstance(paso, dict):
                raise ValueError("Cada paso debe ser un objeto.")
            presentacion.agregar_paso(
                str(paso.get("escena_id", "")),
                paso.get("duracion_s", 5),
                str(paso.get("transicion", "corte")),
                str(paso.get("narracion", "")),
            )
        self._presentaciones.agregar(presentacion)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="presentacion.creada",
            detalle={"presentacion_id": str(presentacion.id),
                     "pasos": len(presentacion.pasos),
                     "duracion": presentacion.duracion_total},
        ))
        self._auditoria.registrar(
            identidad, "presentacion.crear", str(presentacion.id), "exito",
            {"pasos": len(presentacion.pasos)},
        )
        return {"presentacion": self._a_dict(presentacion)}

    @staticmethod
    def _a_dict(presentacion) -> dict:
        return {
            "id": str(presentacion.id),
            "proyecto_id": str(presentacion.proyecto_id),
            "titulo": presentacion.titulo,
            "pasos": list(presentacion.pasos),
            "sellada": presentacion.sellada,
            "sello_zid": presentacion.sello_zid,
            "duracion_total": presentacion.duracion_total,
            "creado_en": presentacion.creado_en.isoformat(),
        }


class CasoReproducirPresentacion:
    def __init__(self, repo_presentaciones, repo_escenas, repo_proyectos, auditoria):
        self._presentaciones = repo_presentaciones
        self._escenas = repo_escenas
        self._proyectos = repo_proyectos
        self._auditoria = auditoria

    def ejecutar(self, identidad, presentacion_id: str) -> tuple:
        presentacion = self._presentaciones.obtener_exigir(presentacion_id)
        proyecto = self._proyectos.obtener_exigir(str(presentacion.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        diapositivas = []
        for paso in presentacion.pasos:
            escena = self._escenas.obtener_exigir(paso["escena_id"])
            diapositivas.append({
                "svg": escena.a_especificacion(),
                "duracion_s": paso["duracion_s"],
                "transicion": paso["transicion"],
                "narracion": paso["narracion"],
                "nombre": escena.nombre,
            })
        svg = slideshow_svg(presentacion.titulo, diapositivas)
        self._auditoria.registrar(
            identidad, "presentacion.reproducir", str(presentacion.id), "exito",
            {"pasos": len(diapositivas), "duracion": presentacion.duracion_total},
        )
        return 200, svg, {
            "Content-Type": "image/svg+xml",
            "Content-Disposition": "inline; filename=presentacion_" + str(presentacion.id) + ".svg",
        }


class CasoSellarPresentacion:
    def __init__(self, repo_presentaciones, repo_proyectos, repo_historial, bus, outbox, cliente_zyra, auditoria):
        self._presentaciones = repo_presentaciones
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._bus = bus
        self._outbox = outbox
        self._cliente = cliente_zyra
        self._auditoria = auditoria

    def ejecutar(self, identidad, presentacion_id: str) -> dict:
        presentacion = self._presentaciones.obtener_exigir(presentacion_id)
        proyecto = self._proyectos.obtener_exigir(str(presentacion.proyecto_id))
        PoliticaProyecto.exigir_editar(proyecto, identidad)
        contenido = {
            "proyecto_id": str(proyecto.id),
            "presentacion_id": str(presentacion.id),
            "titulo": presentacion.titulo,
            "pasos": len(presentacion.pasos),
            "duracion_total": presentacion.duracion_total,
            "narraciones": [p["narracion"] for p in presentacion.pasos if p["narracion"]],
            "sello_zid": identidad.zid,
            "hash": sha256_texto(presentacion.titulo + "|" + str(len(presentacion.pasos))),
        }
        self._outbox.encolar(
            "laboratorio.presentacion.sellada",
            "zyra/documents/seal",
            {"titulo": "Presentacion: " + presentacion.titulo,
             "contenido": contenido},
        )
        self._outbox.procesar(self._cliente.entregar)
        estadisticas = self._outbox.estadisticas()
        if estadisticas.get("pendiente", 0) > 0:
            estado_sello = "pendiente_red"
        elif estadisticas.get("error", 0) > 0:
            estado_sello = "error_red"
        else:
            estado_sello = "sellado_en_zyra"
        presentacion.marcar_sellada(identidad.zid)
        self._presentaciones.actualizar_sello(presentacion)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="presentacion.sellada",
            detalle={"presentacion_id": str(presentacion.id),
                     "estado_sello": estado_sello},
        ))
        self._auditoria.registrar(
            identidad, "presentacion.sellar", str(presentacion.id), "exito",
            {"estado_sello": estado_sello},
        )
        return {
            "presentacion": CasoCrearPresentacion._a_dict(presentacion),
            "sello": {"estado": estado_sello, "outbox": estadisticas},
        }
