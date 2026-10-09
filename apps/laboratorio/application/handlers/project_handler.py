"""Manejador de proyectos: comandos y consultas (sin HTTP)."""

from apps.laboratorio.application.commands.project_commands import (
    ComandoCrearProyecto,
)
from apps.laboratorio.application.dto.project_dtos import proyecto_a_dict
from apps.laboratorio.application.queries.project_queries import (
    ConsultaListarProyectos,
)
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.schemas.responses.envelopes import exito
from apps.laboratorio.validators.shared.common_validators import validar_paginacion


class ManejadorProyectos:
    def __init__(self, caso_crear, repo_proyectos, auditoria):
        self._caso_crear = caso_crear
        self._repo = repo_proyectos
        self._auditoria = auditoria

    def crear(self, identidad, datos: dict) -> tuple:
        comando = ComandoCrearProyecto.desde_request(datos, identidad.zid)
        datos_caso = self._caso_crear.ejecutar(comando, identidad)
        return exito(datos_caso, 201)

    def listar(self, identidad, query: dict) -> tuple:
        pagina, por_pagina = validar_paginacion(query or {})
        consulta = ConsultaListarProyectos(identidad.zid, pagina, por_pagina)
        proyectos = self._repo.listar(
            {"propietario_zid": consulta.propietario_zid},
            consulta.por_pagina,
            (consulta.pagina - 1) * consulta.por_pagina,
        )
        return exito({
            "proyectos": [proyecto_a_dict(p) for p in proyectos],
            "pagina": consulta.pagina,
            "por_pagina": consulta.por_pagina,
            "total_pagina": len(proyectos),
        })

    def obtener(self, identidad, proyecto_id: str) -> tuple:
        proyecto = self._repo.obtener_exigir(proyecto_id)
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        return exito({"proyecto": proyecto_a_dict(proyecto)})
