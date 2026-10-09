"""Contenedor de servicios: unico punto que construye y conecta todo."""
import os
import secrets

from apps.laboratorio.application.handlers.project_handler import ManejadorProyectos
from apps.laboratorio.application.handlers.scenario_handler import ManejadorEscenarios
from apps.laboratorio.application.use_cases.create_project import CasoCrearProyecto
from apps.laboratorio.application.handlers.document_handler import ManejadorDocumentos
from apps.laboratorio.application.use_cases.create_project_from_document import CasoCrearProyectoDesdeDocumento
from apps.laboratorio.application.use_cases.evaluate_scenario import CasoEvaluarEscenario
from apps.laboratorio.config.application.app_config import AppConfig
from apps.laboratorio.config.database.db_config import DbConfig
from apps.laboratorio.config.events.events_config import EventsConfig
from apps.laboratorio.config.network.network_config import NetworkConfig
from apps.laboratorio.config.permissions.permissions_config import PermissionsConfig
from apps.laboratorio.config.security.security_config import SecurityConfig
from apps.laboratorio.infrastructure.database.connection import ConexionBD
from apps.laboratorio.infrastructure.database.migrations import aplicar_migraciones
from apps.laboratorio.infrastructure.messaging.event_bus import BusEventos
from apps.laboratorio.infrastructure.messaging.outbox import Outbox
from apps.laboratorio.infrastructure.messaging.subscribers import SuscriptorZyra
from apps.laboratorio.infrastructure.network.health import EstadoSalud
from apps.laboratorio.infrastructure.network.zyra_client import ClienteZyra
from apps.laboratorio.infrastructure.persistence.audit_store import AuditStore
from apps.laboratorio.infrastructure.persistence.evaluation_store import EvaluationStore
from apps.laboratorio.infrastructure.persistence.history_store import HistoryStore
from apps.laboratorio.infrastructure.persistence.project_store import ProyectoStore
from apps.laboratorio.infrastructure.persistence.scenario_store import ScenarioStore
from apps.laboratorio.infrastructure.providers.display_holo3d import MotorHolo3D
from apps.laboratorio.infrastructure.providers.renderer_svg import MotorRenderSVG
from apps.laboratorio.infrastructure.repositories.audit_repository import AuditoriaRepository
from apps.laboratorio.infrastructure.repositories.evaluation_repository import EvaluationRepository
from apps.laboratorio.infrastructure.repositories.history_repository import HistorialRepository
from apps.laboratorio.infrastructure.repositories.project_repository import ProyectoRepository
from apps.laboratorio.infrastructure.repositories.scenario_repository import ScenarioRepository
from apps.laboratorio.infrastructure.security.audit_sink import AuditoriaSink
from apps.laboratorio.infrastructure.security.signing import Firmador
from apps.laboratorio.registry.engines.capabilities import (
    Capacidad,
    DisponibilidadCapacidades,
)
from apps.laboratorio.registry.engines.engine_registry import RegistroMotores
from apps.laboratorio.registry.modules.register import RegistroModulos
from apps.laboratorio.registry.templates.template_registry import RegistroPlantillas


class Contenedor:
    def __init__(self):
        self._fabricas = {}
        self._instancias = {}

    def registrar(self, nombre, fabrica, unico=True):
        if not nombre or not callable(fabrica):
            raise ValueError("Servicio requiere nombre y fabrica callable.")
        if nombre in self._fabricas:
            raise ValueError("Servicio duplicado: " + nombre)
        self._fabricas[nombre] = (fabrica, bool(unico))

    def obtener(self, nombre):
        if nombre not in self._fabricas:
            raise ValueError("Servicio no registrado: " + nombre)
        fabrica, unico = self._fabricas[nombre]
        if unico and nombre in self._instancias:
            return self._instancias[nombre]
        instancia = fabrica(self)
        if unico:
            self._instancias[nombre] = instancia
        return instancia

    def contiene(self, nombre) -> bool:
        return nombre in self._fabricas

    def nombres(self) -> tuple:
        return tuple(sorted(self._fabricas))


def _capacidades_honestas() -> DisponibilidadCapacidades:
    capacidades = DisponibilidadCapacidades()
    capacidades.declarar(Capacidad.RENDER_SVG, True)
    capacidades.declarar(Capacidad.RENDER_RASTER, False, "motor raster llega en fase 6")
    capacidades.declarar(Capacidad.RENDER_3D, False, "motor 3D llega en fase 6")
    capacidades.declarar(Capacidad.PROFUNDIDAD, False, "canal de profundidad llega en fase 4")
    capacidades.declarar(Capacidad.PROYECCION_WARP, False, "pipeline de proyeccion llega en fase 8")
    capacidades.declarar(Capacidad.HOLO_3D, False, "hardware holografico no conectado")
    capacidades.declarar(Capacidad.LIGHT_FIELD, False, "hardware light-field no conectado")
    capacidades.declarar(Capacidad.AR_VR, False, "hardware AR/VR no conectado")
    return capacidades


def construir_contenedor(ruta_bd: str = ":memory:") -> Contenedor:
    """Compone TODA la aplicacion en un unico lugar (composition root)."""
    c = Contenedor()
    cfg_app = AppConfig.cargar()
    cfg_ev = EventsConfig.cargar()
    cfg_red = NetworkConfig.cargar()
    cfg_seg = SecurityConfig.cargar()
    cfg_perm = PermissionsConfig.cargar()
    cfg_db = DbConfig(ruta_archivo=ruta_bd) if ruta_bd else DbConfig.cargar()
    c.registrar("config_app", lambda _c: cfg_app)
    c.registrar("config_permisos", lambda _c: cfg_perm)
    destino = ":memory:" if ruta_bd == ":memory:" else cfg_db.ruta_archivo
    conexion = ConexionBD(destino, cfg_db.timeout_segundos, cfg_db.journal_mode)
    aplicar_migraciones(conexion)
    c.registrar("conexion", lambda _c: conexion)
    c.registrar("proyecto_store", lambda _c: ProyectoStore(conexion))
    c.registrar("scenario_store", lambda _c: ScenarioStore(conexion))
    c.registrar("evaluation_store", lambda _c: EvaluationStore(conexion))
    c.registrar("history_store", lambda _c: HistoryStore(conexion))
    c.registrar("audit_store", lambda _c: AuditStore(conexion))
    c.registrar("repo_proyectos", lambda _c: ProyectoRepository(_c.obtener("proyecto_store")))
    c.registrar("repo_escenarios", lambda _c: ScenarioRepository(_c.obtener("scenario_store")))
    c.registrar("repo_evaluaciones", lambda _c: EvaluationRepository(_c.obtener("evaluation_store")))
    c.registrar("repo_historial", lambda _c: HistorialRepository(_c.obtener("history_store")))
    c.registrar("repo_auditoria", lambda _c: AuditoriaRepository(_c.obtener("audit_store")))
    c.registrar("bus", lambda _c: BusEventos())
    c.registrar("outbox", lambda _c: Outbox(conexion, cfg_ev.reintentos))

    def _suscriptor(_c):
        suscriptor = SuscriptorZyra(_c.obtener("bus"), _c.obtener("outbox"))
        suscriptor.conectar()
        return suscriptor

    c.registrar("suscriptor_zyra", _suscriptor)
    c.registrar("cliente_zyra", lambda _c: ClienteZyra(cfg_red))

    def _motores(_c):
        registro = RegistroMotores()
        registro.registrar("renderer_svg", MotorRenderSVG())
        registro.registrar("display_holo3d", MotorHolo3D())
        return registro

    c.registrar("registro_motores", _motores)
    c.registrar("estado_salud", lambda _c: EstadoSalud(conexion, cfg_red, _c.obtener("registro_motores")))
    clave = os.environ.get("LAB_SIGNING_KEY") or secrets.token_hex(32)
    c.registrar("firmador", lambda _c: Firmador(clave))
    c.registrar("auditoria_sink", lambda _c: AuditoriaSink(_c.obtener("repo_auditoria")))
    c.registrar("registro_modulos", lambda _c: RegistroModulos())
    c.registrar("registro_plantillas", lambda _c: RegistroPlantillas())
    c.registrar("capacidades", lambda _c: _capacidades_honestas())
    c.registrar("caso_crear_proyecto", lambda _c: CasoCrearProyecto(
        _c.obtener("repo_proyectos"), _c.obtener("repo_historial"),
        _c.obtener("bus"), _c.obtener("auditoria_sink"),
    ))
    c.registrar("caso_evaluar_escenario", lambda _c: CasoEvaluarEscenario(
        _c.obtener("repo_escenarios"), _c.obtener("repo_evaluaciones"),
        _c.obtener("repo_proyectos"), _c.obtener("repo_historial"),
        _c.obtener("bus"), _c.obtener("outbox"),
        _c.obtener("cliente_zyra"), _c.obtener("auditoria_sink"),
    ))
    c.registrar("manejador_proyectos", lambda _c: ManejadorProyectos(
        _c.obtener("caso_crear_proyecto"), _c.obtener("repo_proyectos"),
        _c.obtener("auditoria_sink"),
    ))
    c.registrar("manejador_escenarios", lambda _c: ManejadorEscenarios(
        _c.obtener("repo_escenarios"), _c.obtener("repo_evaluaciones"),
        _c.obtener("repo_proyectos"), _c.obtener("caso_evaluar_escenario"),
        _c.obtener("auditoria_sink"),
    ))
    c.registrar("caso_crear_desde_documento", lambda _c: CasoCrearProyectoDesdeDocumento(_c.obtener("caso_crear_proyecto")))
    c.registrar("manejador_documentos", lambda _c: ManejadorDocumentos(_c.obtener("caso_crear_desde_documento"), _c.obtener("auditoria_sink")))
    c.obtener("suscriptor_zyra")
    return c
