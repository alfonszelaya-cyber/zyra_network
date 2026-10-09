"""Serializacion oficial de proyectos para API y UI."""


def proyecto_a_dict(proyecto) -> dict:
    return {
        "id": str(proyecto.id),
        "titulo": proyecto.titulo,
        "descripcion": proyecto.descripcion,
        "tipo": proyecto.tipo_creacion.value,
        "etapa": proyecto.etapa_actual.value,
        "estado": proyecto.estado.value,
        "propietario_zid": proyecto.propietario_zid,
        "etiquetas": list(proyecto.etiquetas),
        "creado_en": proyecto.creado_en.isoformat(),
        "actualizado_en": proyecto.actualizado_en.isoformat(),
    }
