"""Rutas 4D + ciudadanos + fisica + camara orbital + desastres."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo
from apps.laboratorio.infrastructure.providers.renderer_3d import CamaraOrbital
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.schemas.responses.envelopes import exito

RUTA_TIMELINE = "/laboratorio/api/v1/scenes/{escena_id}/timeline"
RUTA_LIGHTING = "/laboratorio/api/v1/scenes/{escena_id}/lighting"
RUTA_INTERACCIONES = "/laboratorio/api/v1/scenes/{escena_id}/interactions"
RUTA_CIT_POBLAR = "/laboratorio/api/v1/scenes/{escena_id}/citizens/populate"
RUTA_CIT_PASO = "/laboratorio/api/v1/scenes/{escena_id}/citizens/step"
RUTA_CIT_ESTADO = "/laboratorio/api/v1/scenes/{escena_id}/citizens"
RUTA_CIT_EVACUAR = "/laboratorio/api/v1/scenes/{escena_id}/citizens/evacuate"
RUTA_FIS_AGREGAR = "/laboratorio/api/v1/scenes/{escena_id}/physics/bodies"
RUTA_FIS_IMPULSO = "/laboratorio/api/v1/scenes/{escena_id}/physics/bodies/{cuerpo_id}/impulse"
RUTA_FIS_PASO = "/laboratorio/api/v1/scenes/{escena_id}/physics/step"
RUTA_FIS_ESTADO = "/laboratorio/api/v1/scenes/{escena_id}/physics"
RUTA_CAMARA = "/laboratorio/api/v1/scenes/{escena_id}/camara/orbital"
RUTA_DESASTRE = "/laboratorio/api/v1/scenes/{escena_id}/desastre/simular"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_cuatro_d")
    ciudadanos = app.contenedor.obtener("motor_ciudadanos")
    fisica = app.contenedor.obtener("motor_fisico")
    motor_orbital = app.contenedor.obtener("motor_orbital")
    repo_escenas = app.contenedor.obtener("repo_escenas")
    repo_proyectos = app.contenedor.obtener("repo_proyectos")

    def _escena_verificada(ctx):
        escena = repo_escenas.obtener_exigir(ctx.ruta_params["escena_id"])
        proyecto = repo_proyectos.obtener_exigir(str(escena.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, ctx.identidad)
        return escena

    def _poblar(ctx):
        datos = ctx.json()
        return exito(ciudadanos.poblar(datos.get("ciudadanos", []), datos.get("salidas", [])))

    def _paso_cit(ctx):
        cuerpo = ctx.json_opcional()
        return exito(ciudadanos.paso(float((cuerpo or {}).get("dt", 1.0))))

    def _estado_cit(ctx):
        return exito(ciudadanos.estado_poblacion())

    def _evacuar(ctx):
        return exito(ciudadanos.evacuar())

    def _fis_agregar(ctx):
        datos = ctx.json()
        return exito(fisica.agregar(datos.get("id", "cuerpo-1"), datos.get("x", 0.0),
                                    datos.get("y", 0.0), datos.get("w", 10.0),
                                    datos.get("h", 10.0), datos.get("masa", 1.0),
                                    datos.get("rebote", 0.5)))

    def _fis_impulso(ctx):
        datos = ctx.json()
        return exito(fisica.impulso(ctx.ruta_params["cuerpo_id"], datos.get("vx", 0.0), datos.get("vy", 0.0)))

    def _fis_paso(ctx):
        cuerpo = ctx.json_opcional()
        return exito(fisica.paso(float((cuerpo or {}).get("dt", 0.016))))

    def _fis_estado(ctx):
        return exito(fisica.estado())

    def _camara(ctx):
        escena = _escena_verificada(ctx)
        datos = ctx.json()
        camara = CamaraOrbital(distancia=datos.get("distancia", 3.0))
        camara.girar(float(datos.get("azimut", 0.0)), float(datos.get("elevacion", 35.0)))
        resultado = motor_orbital.renderizar_orbital(
            escena, {"ancho": int(datos.get("ancho", 400)),
                     "alto": int(datos.get("alto", 300))}, camara)
        return 200, resultado.imagen_bytes, {"Content-Type": "image/png", "Cache-Control": "no-store"}

    def _desastre(ctx):
        _escena_verificada(ctx)
        datos = ctx.json()
        plan = ciudadanos.simular_desastre(
            str(datos.get("tipo", "")), datos.get("epicentro", [0, 0]),
            datos.get("radio", 50.0), datos.get("zonas_seguras", []))
        outbox = app.contenedor.obtener("outbox")
        outbox.encolar("laboratorio.desastre.simulado", "zyra/documents/seal",
                       {"titulo": "Simulacion de desastre: " + str(plan["tipo"]),
                        "contenido": {"plan": plan, "escena": ctx.ruta_params["escena_id"]}})
        return exito({"plan": plan, "red": {"evento": "laboratorio.desastre.simulado",
                                            "estado": outbox.estadisticas()}})

    app.registrar("POST", RUTA_TIMELINE, lambda c: manejador.crear_timeline(c.identidad, c.ruta_params["escena_id"], c.json()), PermisoCodigo.EDITAR_4D, "Crear linea de tiempo")
    app.registrar("GET", RUTA_TIMELINE, lambda c: manejador.obtener_timeline(c.identidad, c.ruta_params["escena_id"]), PermisoCodigo.VER, "Obtener linea de tiempo")
    app.registrar("POST", RUTA_LIGHTING, lambda c: manejador.crear_luz(c.identidad, c.ruta_params["escena_id"], c.json()), PermisoCodigo.EDITAR_4D, "Crear programa de luz")
    app.registrar("GET", RUTA_LIGHTING, lambda c: manejador.obtener_luz(c.identidad, c.ruta_params["escena_id"]), PermisoCodigo.VER, "Obtener programa de luz")
    app.registrar("POST", RUTA_INTERACCIONES, lambda c: manejador.crear_interaccion(c.identidad, c.ruta_params["escena_id"], c.json()), PermisoCodigo.EDITAR_4D, "Crear zona de interaccion")
    app.registrar("GET", RUTA_INTERACCIONES, lambda c: manejador.listar_interacciones(c.identidad, c.ruta_params["escena_id"]), PermisoCodigo.VER, "Listar interacciones")
    app.registrar("POST", RUTA_CIT_POBLAR, _poblar, PermisoCodigo.EDITAR_4D, "Poblar gemelo con ciudadanos")
    app.registrar("POST", RUTA_CIT_PASO, _paso_cit, PermisoCodigo.EDITAR_4D, "Paso de simulacion social")
    app.registrar("GET", RUTA_CIT_ESTADO, _estado_cit, PermisoCodigo.VER, "Estado de la poblacion")
    app.registrar("POST", RUTA_CIT_EVACUAR, _evacuar, PermisoCodigo.EDITAR_4D, "Evacuacion hacia salidas")
    app.registrar("POST", RUTA_FIS_AGREGAR, _fis_agregar, PermisoCodigo.EDITAR_4D, "Agregar cuerpo fisico")
    app.registrar("POST", RUTA_FIS_IMPULSO, _fis_impulso, PermisoCodigo.EDITAR_4D, "Impulso a un cuerpo")
    app.registrar("POST", RUTA_FIS_PASO, _fis_paso, PermisoCodigo.EDITAR_4D, "Paso de fisica")
    app.registrar("GET", RUTA_FIS_ESTADO, _fis_estado, PermisoCodigo.VER, "Estado del mundo fisico")
    app.registrar("POST", RUTA_CAMARA, _camara, PermisoCodigo.VER, "Vista orbital (PNG real)")
    app.registrar("POST", RUTA_DESASTRE, _desastre, PermisoCodigo.EDITAR_4D, "Simular desastre: zonas seguras + ayuda + evento a la Red")
