"""Grupos de etapas de la cadena D1.

Dueno de la cadena: shared/enums/pipeline_stage.py (sin duplicacion).
Este modulo solo la agrupa para reportes y navegacion.
"""

from apps.laboratorio.shared.enums.pipeline_stage import PipelineStage

CAPTURA = (
    PipelineStage.DESCRIBIR.value,
    PipelineStage.FOTOGRAFIAR.value,
    PipelineStage.ESCANEAR.value,
    PipelineStage.MEDIR.value,
    PipelineStage.IMPORTAR.value,
)

CREACION = (
    PipelineStage.COMPRENDER.value,
    PipelineStage.DISENAR.value,
    PipelineStage.CREAR.value,
)

DECISION = (
    PipelineStage.SIMULAR.value,
    PipelineStage.PROBAR.value,
    PipelineStage.COMPARAR.value,
    PipelineStage.OPTIMIZAR.value,
)

VISUAL = (
    PipelineStage.TRES_D.value,
    PipelineStage.CUATRO_D.value,
    PipelineStage.FOTORREALISMO.value,
    PipelineStage.PRESENTACION.value,
)

ENTREGA = (
    PipelineStage.PROYECCION.value,
    PipelineStage.LIGHT_FIELD.value,
    PipelineStage.HOLOGRAFIA.value,
    PipelineStage.AR_VR.value,
)

GRUPOS = {
    "captura": CAPTURA,
    "creacion": CREACION,
    "decision": DECISION,
    "visual": VISUAL,
    "entrega": ENTREGA,
}


def validar_cobertura_total() -> bool:
    """Comprueba que los grupos cubren TODA la cadena sin repetir."""
    union = []
    for grupo in GRUPOS.values():
        for etapa in grupo:
            if etapa in union:
                return False
            union.append(etapa)
    return set(union) == set(PipelineStage.cadena_completa())
