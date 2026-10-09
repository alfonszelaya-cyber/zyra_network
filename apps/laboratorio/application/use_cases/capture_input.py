"""Caso de uso: capturar una entrada real en un proyecto."""
from apps.laboratorio.application.commands.input_commands import ComandoCapturarEntrada
from apps.laboratorio.domain.input_capture import EntradaCaptura
from apps.laboratorio.domain.history import EntradaHistorial
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.shared.enums.input_kind import InputKind
from apps.laboratorio.shared.models.identifiers import nuevo_id


class CasoCapturarEntrada:
    def __init__(self, repo_inputs, repo_proyectos, repo_historial, auditoria):
        self._inputs = repo_inputs
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._auditoria = auditoria

    def ejecutar(self, comando: ComandoCapturarEntrada, identidad) -> dict:
        if not isinstance(comando, ComandoCapturarEntrada):
            raise ValueError("Se esperaba ComandoCapturarEntrada.")
        proyecto = self._proyectos.obtener_exigir(comando.proyecto_id)
        PoliticaProyecto.exigir_editar(proyecto, identidad)
        tipo = InputKind.validar(comando.tipo)
        id_nuevo = nuevo_id("inp")
        if tipo is InputKind.TEXTO:
            entrada = EntradaCaptura.desde_texto(
                id_nuevo, proyecto.id, comando.titulo, comando.contenido
            )
        elif tipo in (InputKind.FOTO, InputKind.ESCANEO):
            entrada = EntradaCaptura.desde_base64(
                id_nuevo, proyecto.id, comando.titulo, comando.contenido, tipo
            )
        else:
            raise ValueError("Tipo de entrada aun no soportado: " + tipo.value)
        self._inputs.agregar(entrada)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="entrada.capturada",
            detalle={"entrada_id": str(entrada.id), "tipo": tipo.value,
                     "hash": entrada.hash_sha256[:16]},
        ))
        self._auditoria.registrar(
            identidad, "entrada.capturar", str(entrada.id), "exito",
            {"tipo": tipo.value, "tamano": entrada.tamano_bytes},
        )
        return {"entrada": self._a_dict(entrada)}

    @staticmethod
    def _a_dict(entrada) -> dict:
        es_media = entrada.tipo.value in ("foto", "escaneo")
        return {
            "id": str(entrada.id),
            "proyecto_id": str(entrada.proyecto_id),
            "tipo": entrada.tipo.value,
            "titulo": entrada.titulo,
            "contenido": ("[binario base64 sellado]" if es_media else entrada.contenido),
            "hash_sha256": entrada.hash_sha256,
            "tamano_bytes": entrada.tamano_bytes,
            "creado_en": entrada.creado_en.isoformat(),
        }
