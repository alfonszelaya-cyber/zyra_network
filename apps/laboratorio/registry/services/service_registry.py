"""Contenedor de servicios: unico punto que construye y conecta todo."""
import os
import secrets

from apps.laboratorio.application.handlers.project_handler import ManejadorProyectos
from apps.laboratorio.application.handlers.scenario_handler import ManejadorEscenarios
from apps.laboratorio.application.use_cases.create_project import CasoCrearProyecto
from apps.laboratorio.application.handlers.input_handler import ManejadorCapturas
from apps.laboratorio.application.handlers.understanding_handler import ManejadorComprension
from apps.laboratorio.application.handlers.scene_handler import ManejadorCreacion
from apps.laboratorio.application.handlers.world4d_handler import ManejadorCuatroD
from apps.laboratorio.application.use_cases.world4d import (
    CasoCrearLineaTiempo,
    CasoCrearProgramaLuz,
    CasoCrearInteraccion,
)
from apps.laboratorio.infrastructure.providers.naked3d_engine import MotorNaked3D
from apps.laboratorio.infrastructure.providers.hologram_engine import MotorHolograma
from apps.laboratorio.infrastructure.providers.oligram_engine import MotorOligrama
from apps.laboratorio.infrastructure.persistence.timeline_store import TimelineStore
from apps.laboratorio.infrastructure.persistence.lighting_store import LightingStore
from apps.laboratorio.infrastructure.persistence.interaction_store import InteractionStore
from apps.laboratorio.infrastructure.repositories.timeline_repository import TimelineRepository
from apps.laboratorio.infrastructure.repositories.lighting_repository import LightingRepository
from apps.laboratorio.infrastructure.repositories.interaction_repository import InteractionRepository
from apps.laboratorio.application.handlers.library_handler import ManejadorBiblioteca
from apps.laboratorio.application.use_cases.create_scene import CasoCrearEscena
from apps.laboratorio.application.use_cases.generate_artifact import CasoGenerarArtefacto
from apps.laboratorio.application.use_cases.create_asset import CasoCrearActivo
from apps.laboratorio.infrastructure.providers.generation_engine import MotorGeneracionReal
from apps.laboratorio.infrastructure.persistence.scene_store import SceneStore
from apps.laboratorio.infrastructure.persistence.artifact_store import ArtifactStore
from apps.laboratorio.infrastructure.persistence.asset_store import AssetStore
from apps.laboratorio.infrastructure.repositories.scene_repository import SceneRepository
from apps.laboratorio.infrastructure.repositories.artifact_repository import ArtifactRepository
from apps.laboratorio.infrastructure.repositories.asset_repository import AssetRepository
from apps.laboratorio.application.handlers.design_handler import ManejadorDisenos
from apps.laboratorio.application.use_cases.capture_input import CasoCapturarEntrada
from apps.laboratorio.application.use_cases.understand_input import CasoComprenderEntrada
from apps.laboratorio.application.use_cases.create_blueprint import CasoCrearBlueprint
from apps.laboratorio.infrastructure.providers.understanding_engine import MotorComprensionTextual
from apps.laboratorio.infrastructure.persistence.input_store import InputStore
from apps.laboratorio.infrastructure.persistence.understanding_store import UnderstandingStore
from apps.laboratorio.infrastructure.persistence.design_store import DesignStore
from apps.laboratorio.infrastructure.repositories.input_repository import InputRepository
from apps.laboratorio.infrastructure.repositories.understanding_repository import UnderstandingRepository
from apps.laboratorio.infrastructure.repositories.design_repository import DesignRepository
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
    c.registrar("input_store", lambda _c: InputStore(conexion))
    c.registrar("understanding_store", lambda _c: UnderstandingStore(conexion))
    c.registrar("design_store", lambda _c: DesignStore(conexion))
    c.registrar("repo_inputs", lambda _c: InputRepository(_c.obtener("input_store")))
    c.registrar("repo_comprensiones", lambda _c: UnderstandingRepository(_c.obtener("understanding_store")))
    c.registrar("repo_disenos", lambda _c: DesignRepository(_c.obtener("design_store")))
    c.registrar("motor_comprension", lambda _c: MotorComprensionTextual())
    c.registrar("caso_capturar", lambda _c: CasoCapturarEntrada(_c.obtener("repo_inputs"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("auditoria_sink")))
    c.registrar("caso_comprender", lambda _c: CasoComprenderEntrada(_c.obtener("repo_inputs"), _c.obtener("repo_comprensiones"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("motor_comprension"), _c.obtener("auditoria_sink")))
    c.registrar("caso_disenar", lambda _c: CasoCrearBlueprint(_c.obtener("repo_disenos"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_capturas", lambda _c: ManejadorCapturas(_c.obtener("caso_capturar"), _c.obtener("repo_inputs"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_comprension", lambda _c: ManejadorComprension(_c.obtener("caso_comprender"), _c.obtener("repo_inputs"), _c.obtener("repo_comprensiones"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_disenos", lambda _c: ManejadorDisenos(_c.obtener("caso_disenar"), _c.obtener("repo_disenos"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.registrar("scene_store", lambda _c: SceneStore(conexion))
    c.registrar("artifact_store", lambda _c: ArtifactStore(conexion))
    c.registrar("asset_store", lambda _c: AssetStore(conexion))
    c.registrar("repo_escenas", lambda _c: SceneRepository(_c.obtener("scene_store")))
    c.registrar("repo_artefactos", lambda _c: ArtifactRepository(_c.obtener("artifact_store")))
    c.registrar("repo_activos", lambda _c: AssetRepository(_c.obtener("asset_store")))
    c.registrar("motor_generacion", lambda _c: MotorGeneracionReal())
    c.registrar("caso_crear_escena", lambda _c: CasoCrearEscena(_c.obtener("repo_escenas"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("auditoria_sink")))
    c.registrar("caso_generar", lambda _c: CasoGenerarArtefacto(_c.obtener("repo_escenas"), _c.obtener("repo_artefactos"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("motor_generacion"), _c.obtener("auditoria_sink")))
    c.registrar("caso_crear_activo", lambda _c: CasoCrearActivo(_c.obtener("repo_activos"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_creacion", lambda _c: ManejadorCreacion(_c.obtener("caso_crear_escena"), _c.obtener("caso_generar"), _c.obtener("repo_escenas"), _c.obtener("repo_artefactos"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_biblioteca", lambda _c: ManejadorBiblioteca(_c.obtener("caso_crear_activo"), _c.obtener("repo_activos"), _c.obtener("auditoria_sink")))
    c.registrar("timeline_store", lambda _c: TimelineStore(conexion))
    c.registrar("lighting_store", lambda _c: LightingStore(conexion))
    c.registrar("interaction_store", lambda _c: InteractionStore(conexion))
    c.registrar("repo_timelines", lambda _c: TimelineRepository(_c.obtener("timeline_store")))
    c.registrar("repo_luces", lambda _c: LightingRepository(_c.obtener("lighting_store")))
    c.registrar("repo_interacciones", lambda _c: InteractionRepository(_c.obtener("interaction_store")))
    c.registrar("motor_naked3d", lambda _c: MotorNaked3D())
    c.registrar("motor_holograma", lambda _c: MotorHolograma())
    c.registrar("motor_oligrama", lambda _c: MotorOligrama())
    c.registrar("caso_timeline", lambda _c: CasoCrearLineaTiempo(_c.obtener("repo_timelines"), _c.obtener("repo_escenas"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("auditoria_sink")))
    c.registrar("caso_luz", lambda _c: CasoCrearProgramaLuz(_c.obtener("repo_luces"), _c.obtener("repo_escenas"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("auditoria_sink")))
    c.registrar("caso_interaccion", lambda _c: CasoCrearInteraccion(_c.obtener("repo_interacciones"), _c.obtener("repo_escenas"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_cuatro_d", lambda _c: ManejadorCuatroD(_c.obtener("caso_timeline"), _c.obtener("caso_luz"), _c.obtener("caso_interaccion"), _c.obtener("repo_timelines"), _c.obtener("repo_luces"), _c.obtener("repo_interacciones"), _c.obtener("repo_escenas"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.obtener("suscriptor_zyra")
    return c
