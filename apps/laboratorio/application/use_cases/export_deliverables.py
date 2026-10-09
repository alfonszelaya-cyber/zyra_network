"""Caso de uso: exportar bundle verificable o enviar a app ZYRA."""
from apps.laboratorio.domain.export_bundle import Exportacion
from apps.laboratorio.domain.history import EntradaHistorial
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.services.export.bundle_exporter import construir_bundle
from apps.laboratorio.shared.models.identifiers import nuevo_id


def json_a_texto(datos: dict) -> str:
    """Serializa a JSON estable para piezas del bundle."""
    import json as _json
    return _json.dumps(datos, ensure_ascii=True, sort_keys=True, default=str)


class CasoExportarBundle:
    def __init__(
        self, repo_exportaciones, repo_proyectos, repo_escenas,
        repo_artefactos, repo_evaluaciones, repo_presentaciones,
        repo_historial, outbox, cliente_zyra, auditoria,
    ):
        self._exportaciones = repo_exportaciones
        self._proyectos = repo_proyectos
        self._escenas = repo_escenas
        self._artefactos = repo_artefactos
        self._evaluaciones = repo_evaluaciones
        self._presentaciones = repo_presentaciones
        self._historial = repo_historial
        self._outbox = outbox
        self._cliente = cliente_zyra
        self._auditoria = auditoria

    def ejecutar(self, identidad, proyecto_id: str, datos: dict) -> dict:
        proyecto = self._proyectos.obtener_exigir(proyecto_id)
        PoliticaProyecto.exigir_editar(proyecto, identidad)
        if not isinstance(datos, dict):
            raise ValueError("Cuerpo invalido.")
        tipo = str(datos.get("tipo", "bundle_verificable")).strip().lower()
        destino = str(datos.get("destino", "")).strip()
        piezas = self._recolectar(proyecto)
        zip_bytes, manifiesto_piezas, sello = construir_bundle(
            {
                "proyecto_id": str(proyecto.id),
                "titulo": proyecto.titulo,
                "tipo": proyecto.tipo_creacion.value,
            },
            piezas,
        )
        exportacion = Exportacion(
            id=nuevo_id("exp"), proyecto_id=proyecto.id,
            tipo=tipo, destino=destino,
            piezas=manifiesto_piezas,
            tamano_total=sello["tamano_total"],
            hash_sha256=sello["hash_sha256"],
        )
        self._exportaciones.agregar(exportacion)
        if exportacion.es_envio:
            self._outbox.encolar(
                "laboratorio.export.enviada",
                "zyra/documents/seal",
                {
                    "titulo": "Export a " + exportacion.destino + ": " + proyecto.titulo,
                    "contenido": {
                        "proyecto_id": str(proyecto.id),
                        "destino": exportacion.destino,
                        "hash_bundle": exportacion.hash_sha256,
                        "total_piezas": sello["total_piezas"],
                        "sello_zid": identidad.zid,
                    },
                },
            )
            self._outbox.procesar(self._cliente.entregar)
            estadisticas = self._outbox.estadisticas()
            estado_envio = (
                "pendiente_red" if estadisticas.get("pendiente", 0) > 0
                else ("error_red" if estadisticas.get("error", 0) > 0 else "enviado")
            )
        else:
            estadisticas = self._outbox.estadisticas()
            estado_envio = "bundle_local"
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="export.generado",
            detalle={"export_id": str(exportacion.id),
                     "tipo": exportacion.tipo,
                     "piezas": sello["total_piezas"],
                     "hash": exportacion.hash_sha256[:16]},
        ))
        self._auditoria.registrar(
            identidad, "export.generar", str(exportacion.id), "exito",
            {"tipo": exportacion.tipo, "piezas": sello["total_piezas"],
             "estado_envio": estado_envio},
        )
        return {
            "exportacion": self._a_dict(exportacion),
            "estado_envio": estado_envio,
            "outbox": estadisticas,
        }

    def _recolectar(self, proyecto) -> list:
        """Recolecta piezas reales del proyecto."""
        piezas = []
        escenas = self._escenas.listar_por_proyecto(proyecto.id)
        for e in escenas:
            piezas.append({
                "nombre": "escena_" + str(e.id) + ".json",
                "contenido": json_a_texto({
                    "nombre": e.nombre,
                    "ancho": e.ancho, "alto": e.alto,
                    "objetos": e.objetos,
                }),
            })
        artefactos = self._artefactos.listar_por_proyectos([proyecto.id])
        for a in artefactos:
            piezas.append({
                "nombre": "artefacto_" + str(a.id) + ".txt",
                "contenido": str(a.contenido)[:200000],
            })
        evaluaciones = self._evaluaciones.listar({"proyecto_id": proyecto.id}, 200, 0)
        for ev in evaluaciones:
            piezas.append({
                "nombre": "evaluacion_" + str(ev.id) + ".json",
                "contenido": json_a_texto({
                    "escenario_id": str(ev.escenario_id),
                    "metricas": ev.metricas,
                    "puntaje_total": ev.puntaje_total,
                }),
            })
        presentaciones = self._presentaciones.listar_por_proyectos([proyecto.id])
        for p in presentaciones:
            piezas.append({
                "nombre": "presentacion_" + str(p.id) + ".json",
                "contenido": json_a_texto({
                    "titulo": p.titulo,
                    "pasos": p.pasos,
                    "sellada": p.sellada,
                    "duracion_total": p.duracion_total,
                }),
            })
        return piezas

    @staticmethod
    def _a_dict(exportacion) -> dict:
        return {
            "id": str(exportacion.id),
            "proyecto_id": str(exportacion.proyecto_id),
            "tipo": exportacion.tipo,
            "destino": exportacion.destino,
            "piezas": list(exportacion.piezas),
            "total_piezas": len(exportacion.piezas),
            "tamano_total": exportacion.tamano_total,
            "hash_sha256": exportacion.hash_sha256,
            "creado_en": exportacion.creado_en.isoformat(),
        }
