"""Casos de uso del 4D: TIEMPO, LUZ e INTERACCION con evidencia."""
from apps.laboratorio.application.commands.world4d_commands import (
    ComandoCrearInteraccion,
    ComandoCrearLineaTiempo,
    ComandoCrearProgramaLuz,
)
from apps.laboratorio.domain.history import EntradaHistorial
from apps.laboratorio.domain.interaction import ZonaInteraccion
from apps.laboratorio.domain.lighting import ProgramaLuz
from apps.laboratorio.domain.timeline import LineaTiempo
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.shared.models.identifiers import nuevo_id


class CasoCrearLineaTiempo:
    def __init__(self, repo_timelines, repo_escenas, repo_proyectos, repo_historial, auditoria):
        self._timelines = repo_timelines
        self._escenas = repo_escenas
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._auditoria = auditoria

    def ejecutar(self, comando: ComandoCrearLineaTiempo, identidad) -> dict:
        if not isinstance(comando, ComandoCrearLineaTiempo):
            raise ValueError("Se esperaba ComandoCrearLineaTiempo.")
        escena = self._escenas.obtener_exigir(comando.escena_id)
        proyecto = self._proyectos.obtener_exigir(str(escena.proyecto_id))
        PoliticaProyecto.exigir_editar(proyecto, identidad)
        linea = LineaTiempo(
            id=nuevo_id("tln"), escena_id=escena.id,
            duracion_s=float(comando.duracion_s), fps=int(comando.fps),
        )
        for pista in comando.pistas:
            if not isinstance(pista, dict):
                raise ValueError("Cada pista debe ser un objeto.")
            linea.agregar_pista(
                str(pista.get("objetivo", "")),
                str(pista.get("propiedad", "")),
                list(pista.get("keyframes", [])),
            )
        self._timelines.agregar(linea)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="timeline.creada",
            detalle={"escena_id": str(escena.id),
                     "pistas": len(linea.pistas),
                     "keyframes": linea.total_keyframes},
        ))
        self._auditoria.registrar(
            identidad, "timeline.crear", str(linea.id), "exito",
            {"duracion": linea.duracion_s, "pistas": len(linea.pistas)},
        )
        return {"timeline": self._a_dict(linea)}

    @staticmethod
    def _a_dict(linea) -> dict:
        return {
            "id": str(linea.id),
            "escena_id": str(linea.escena_id),
            "duracion_s": linea.duracion_s,
            "fps": linea.fps,
            "pistas": list(linea.pistas),
            "total_keyframes": linea.total_keyframes,
            "creado_en": linea.creado_en.isoformat(),
        }


class CasoCrearProgramaLuz:
    def __init__(self, repo_luces, repo_escenas, repo_proyectos, repo_historial, auditoria):
        self._luces = repo_luces
        self._escenas = repo_escenas
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._auditoria = auditoria

    def ejecutar(self, comando: ComandoCrearProgramaLuz, identidad) -> dict:
        if not isinstance(comando, ComandoCrearProgramaLuz):
            raise ValueError("Se esperaba ComandoCrearProgramaLuz.")
        escena = self._escenas.obtener_exigir(comando.escena_id)
        proyecto = self._proyectos.obtener_exigir(str(escena.proyecto_id))
        PoliticaProyecto.exigir_editar(proyecto, identidad)
        programa = ProgramaLuz(
            id=nuevo_id("luz"), escena_id=escena.id,
            ambientar_fondo=bool(comando.ambientar_fondo),
        )
        for paso in comando.pasos:
            if not isinstance(paso, dict):
                raise ValueError("Cada paso debe ser un objeto.")
            programa.agregar_paso(
                float(paso.get("t", 0)),
                str(paso.get("color", "#FFFFFF")),
                float(paso.get("intensidad", 1.0)),
            )
        self._luces.agregar(programa)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="luz.programada",
            detalle={"escena_id": str(escena.id), "pasos": len(programa.pasos)},
        ))
        self._auditoria.registrar(
            identidad, "luz.crear", str(programa.id), "exito",
            {"pasos": len(programa.pasos)},
        )
        return {"lighting": self._a_dict(programa)}

    @staticmethod
    def _a_dict(programa) -> dict:
        return {
            "id": str(programa.id),
            "escena_id": str(programa.escena_id),
            "pasos": list(programa.pasos),
            "ambientar_fondo": programa.ambientar_fondo,
            "color_dominate": programa.color_dominate,
            "creado_en": programa.creado_en.isoformat(),
        }


class CasoCrearInteraccion:
    def __init__(self, repo_interacciones, repo_escenas, repo_proyectos, repo_historial, auditoria):
        self._interacciones = repo_interacciones
        self._escenas = repo_escenas
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._auditoria = auditoria

    def ejecutar(self, comando: ComandoCrearInteraccion, identidad) -> dict:
        if not isinstance(comando, ComandoCrearInteraccion):
            raise ValueError("Se esperaba ComandoCrearInteraccion.")
        escena = self._escenas.obtener_exigir(comando.escena_id)
        proyecto = self._proyectos.obtener_exigir(str(escena.proyecto_id))
        PoliticaProyecto.exigir_editar(proyecto, identidad)
        zona = ZonaInteraccion(
            id=nuevo_id("int"), escena_id=escena.id,
            x=comando.x, y=comando.y, w=comando.w, h=comando.h,
            accion=comando.accion, titulo=comando.titulo,
        )
        self._interacciones.agregar(zona)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="interaccion.creada",
            detalle={"escena_id": str(escena.id), "titulo": zona.titulo},
        ))
        self._auditoria.registrar(
            identidad, "interaccion.crear", str(zona.id), "exito",
            {"accion": zona.accion},
        )
        return {"interaccion": self._a_dict(zona)}

    @staticmethod
    def _a_dict(zona) -> dict:
        return {
            "id": str(zona.id),
            "escena_id": str(zona.escena_id),
            "x": zona.x, "y": zona.y, "w": zona.w, "h": zona.h,
            "accion": zona.accion,
            "titulo": zona.titulo,
            "creado_en": zona.creado_en.isoformat(),
        }
