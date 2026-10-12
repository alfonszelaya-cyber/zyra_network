"""Rutas de decisiones + gemelo en vivo + GOV-DATA panel nacional."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo
from apps.laboratorio.schemas.responses.envelopes import exito

RUTA_SIMULAR = "/laboratorio/api/v1/projects/{proyecto_id}/simulate"
RUTA_SIMS = "/laboratorio/api/v1/projects/{proyecto_id}/simulations"
RUTA_COMPARAR = "/laboratorio/api/v1/projects/{proyecto_id}/compare"
RUTA_COMPARACION = "/laboratorio/api/v1/comparisons/{comparacion_id}"
RUTA_INFORME = RUTA_COMPARACION + "/report.html"
RUTA_OPTIMIZAR = "/laboratorio/api/v1/scenarios/{escenario_id}/optimize"
RUTA_APLICAR = "/laboratorio/api/v1/optimizations/{optimizacion_id}/apply"
RUTA_MONTE = "/laboratorio/api/v1/projects/{proyecto_id}/monte-carlo"
RUTA_MONTE_COMPARA = "/laboratorio/api/v1/projects/{proyecto_id}/monte-carlo/comparar"
RUTA_GEMELO_FUENTES = "/laboratorio/api/v1/twin/sources"
RUTA_GEMELO_FUENTE = "/laboratorio/api/v1/twin/sources/{fuente_id}"
RUTA_GEMELO_HISTORICO = "/laboratorio/api/v1/twin/sources/{fuente_id}/history"
RUTA_GEMELO_ESTADO = "/laboratorio/api/v1/twin"
RUTA_GOV_INGESTAR = "/laboratorio/api/v1/gov/eventos"
RUTA_GOV_CAPA_A = "/laboratorio/api/v1/gov/capa-a"
RUTA_GOV_CAPA_B = "/laboratorio/api/v1/gov/capa-b"
RUTA_GOV_HISTORIAL = "/laboratorio/api/v1/gov/historial"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_decisiones")
    motor_mc = app.contenedor.obtener("motor_monte_carlo")
    gemelo = app.contenedor.obtener("gemelo_vivo")
    gov = app.contenedor.obtener("gov_data")

    def _simular(ctx):
        return manejador.simular(ctx.identidad, ctx.ruta_params["proyecto_id"], ctx.json())

    def _sims(ctx):
        return manejador.listar_simulaciones(ctx.identidad, ctx.ruta_params["proyecto_id"])

    def _comparar(ctx):
        return manejador.comparar(ctx.identidad, ctx.ruta_params["proyecto_id"])

    def _comparacion(ctx):
        return manejador.obtener_comparacion(ctx.identidad, ctx.ruta_params["comparacion_id"])

    def _informe(ctx):
        return manejador.informe_comparacion(ctx.identidad, ctx.ruta_params["comparacion_id"])

    def _optimizar(ctx):
        return manejador.optimizar(ctx.identidad, ctx.ruta_params["escenario_id"])

    def _aplicar(ctx):
        return manejador.aplicar(ctx.identidad, ctx.ruta_params["optimizacion_id"], ctx.json_opcional())

    def _monte(ctx):
        return exito(motor_mc.simular(ctx.json()))

    def _monte_compara(ctx):
        return exito(motor_mc.comparar(ctx.json()))

    def _gem_registrar(ctx):
        datos = ctx.json()
        return exito(gemelo.registrar_fuente(
            datos.get("id", ""), str(datos.get("tipo", "sensor")).strip(),
            datos.get("valor", 0.0), datos.get("umbral_alto"),
            datos.get("umbral_bajo"), str(datos.get("etiqueta", ""))))

    def _gem_actualizar(ctx):
        datos = ctx.json()
        return exito(gemelo.actualizar(ctx.ruta_params["fuente_id"], datos.get("valor")))

    def _gem_historico(ctx):
        return exito(gemelo.historico(ctx.ruta_params["fuente_id"]))

    def _gem_estado(ctx):
        return exito(gemelo.estado())

    def _gov_ingestar(ctx):
        datos = ctx.json()
        return exito(gov.ingestar(datos.get("evento", ""),
                                  datos.get("datos", {}), datos.get("app")))

    def _gov_capa_a(ctx):
        return exito(gov.capa_a())

    def _gov_capa_b(ctx):
        return exito(gov.capa_b())

    def _gov_historial(ctx):
        return exito(gov.historial(int(ctx.query.get("limite", "100"))))

    app.registrar("POST", RUTA_SIMULAR, _simular, PermisoCodigo.SIMULAR, "Simular evolucion temporal")
    app.registrar("GET", RUTA_SIMS, _sims, PermisoCodigo.VER, "Listar simulaciones")
    app.registrar("POST", RUTA_COMPARAR, _comparar, PermisoCodigo.COMPARAR, "Comparar escenarios evaluados")
    app.registrar("GET", RUTA_COMPARACION, _comparacion, PermisoCodigo.VER, "Obtener comparacion")
    app.registrar("GET", RUTA_INFORME, _informe, PermisoCodigo.VER, "Informe HTML de la comparacion")
    app.registrar("POST", RUTA_OPTIMIZAR, _optimizar, PermisoCodigo.OPTIMIZAR, "Sugerir optimizacion")
    app.registrar("POST", RUTA_APLICAR, _aplicar, PermisoCodigo.OPTIMIZAR, "Aplicar optimizacion como escenario nuevo")
    app.registrar("POST", RUTA_MONTE, _monte, PermisoCodigo.SIMULAR, "Monte Carlo reproducible")
    app.registrar("POST", RUTA_MONTE_COMPARA, _monte_compara, PermisoCodigo.COMPARAR, "Comparar con Monte Carlo")
    app.registrar("POST", RUTA_GEMELO_FUENTES, _gem_registrar, PermisoCodigo.SIMULAR, "Registrar fuente real del gemelo")
    app.registrar("POST", RUTA_GEMELO_FUENTE, _gem_actualizar, PermisoCodigo.SIMULAR, "Actualizar valor real de una fuente")
    app.registrar("GET", RUTA_GEMELO_HISTORICO, _gem_historico, PermisoCodigo.VER, "Historico real de una fuente")
    app.registrar("GET", RUTA_GEMELO_ESTADO, _gem_estado, PermisoCodigo.VER, "Estado del gemelo digital en vivo")
    app.registrar("POST", RUTA_GOV_INGESTAR, _gov_ingestar, PermisoCodigo.VER, "Ingestar evento real al panel nacional")
    app.registrar("GET", RUTA_GOV_CAPA_A, _gov_capa_a, PermisoCodigo.VER, "GOV-DATA capa A: panel operativo por app")
    app.registrar("GET", RUTA_GOV_CAPA_B, _gov_capa_b, PermisoCodigo.VER, "GOV-DATA capa B: inteligencia nacional con recomendaciones")
    app.registrar("GET", RUTA_GOV_HISTORIAL, _gov_historial, PermisoCodigo.VER, "Historial de eventos del panel")
