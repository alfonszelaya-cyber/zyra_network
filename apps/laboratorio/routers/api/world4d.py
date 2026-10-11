"""Rutas 4D: timeline, luz, interacciones + ciudadanos + fisica."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo
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


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_cuatro_d")
    ciudadanos = app.contenedor.obtener("motor_ciudadanos")
    fisica = app.contenedor.obtener("motor_fisico")

    def _crear_timeline(ctx):
        return manejador.crear_timeline(ctx.identidad, ctx.ruta_params["escena_id"], ctx.json())

    def _obtener_timeline(ctx):
        return manejador.obtener_timeline(ctx.identidad, ctx.ruta_params["escena_id"])

    def _crear_luz(ctx):
        return manejador.crear_luz(ctx.identidad, ctx.ruta_params["escena_id"], ctx.json())

    def _obtener_luz(ctx):
        return manejador.obtener_luz(ctx.identidad, ctx.ruta_params["escena_id"])

    def _crear_interaccion(ctx):
        return manejador.crear_interaccion(ctx.identidad, ctx.ruta_params["escena_id"], ctx.json())

    def _listar_interacciones(ctx):
        return manejador.listar_interacciones(ctx.identidad, ctx.ruta_params["escena_id"])

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
        return exito(fisica.agregar(
            datos.get("id", "cuerpo-1"), datos.get("x", 0.0), datos.get("y", 0.0),
            datos.get("w", 10.0), datos.get("h", 10.0),
            datos.get("masa", 1.0), datos.get("rebote", 0.5)))

    def _fis_impulso(ctx):
        datos = ctx.json()
        return exito(fisica.impulso(ctx.ruta_params["cuerpo_id"], datos.get("vx", 0.0), datos.get("vy", 0.0)))

    def _fis_paso(ctx):
        cuerpo = ctx.json_opcional()
        return exito(fisica.paso(float((cuerpo or {}).get("dt", 0.016))))

    def _fis_estado(ctx):
        return exito(fisica.estado())

    app.registrar("POST", RUTA_TIMELINE, _crear_timeline, PermisoCodigo.EDITAR_4D, "Crear linea de tiempo")
    app.registrar("GET", RUTA_TIMELINE, _obtener_timeline, PermisoCodigo.VER, "Obtener linea de tiempo")
    app.registrar("POST", RUTA_LIGHTING, _crear_luz, PermisoCodigo.EDITAR_4D, "Crear programa de luz")
    app.registrar("GET", RUTA_LIGHTING, _obtener_luz, PermisoCodigo.VER, "Obtener programa de luz")
    app.registrar("POST", RUTA_INTERACCIONES, _crear_interaccion, PermisoCodigo.EDITAR_4D, "Crear zona de interaccion")
    app.registrar("GET", RUTA_INTERACCIONES, _listar_interacciones, PermisoCodigo.VER, "Listar interacciones")
    app.registrar("POST", RUTA_CIT_POBLAR, _poblar, PermisoCodigo.EDITAR_4D, "Poblar gemelo con ciudadanos (foto/descripcion/escaneo)")
    app.registrar("POST", RUTA_CIT_PASO, _paso_cit, PermisoCodigo.EDITAR_4D, "Paso de simulacion social")
    app.registrar("GET", RUTA_CIT_ESTADO, _estado_cit, PermisoCodigo.VER, "Estado de la poblacion")
    app.registrar("POST", RUTA_CIT_EVACUAR, _evacuar, PermisoCodigo.EDITAR_4D, "Evacuacion hacia salidas")
    app.registrar("POST", RUTA_FIS_AGREGAR, _fis_agregar, PermisoCodigo.EDITAR_4D, "Agregar cuerpo fisico")
    app.registrar("POST", RUTA_FIS_IMPULSO, _fis_impulso, PermisoCodigo.EDITAR_4D, "Impulso a un cuerpo")
    app.registrar("POST", RUTA_FIS_PASO, _fis_paso, PermisoCodigo.EDITAR_4D, "Paso de fisica")
    app.registrar("GET", RUTA_FIS_ESTADO, _fis_estado, PermisoCodigo.VER, "Estado del mundo fisico")
