"""Registro unico de motores con estado honesto (Ley 1)."""

from apps.laboratorio.shared.dto.engine_dto import MotorInfo


class RegistroMotores:
    def __init__(self):
        self._motores = {}

    def registrar(self, id_motor: str, adaptador) -> None:
        if not id_motor or not isinstance(id_motor, str):
            raise ValueError("id_motor invalido.")
        if id_motor in self._motores:
            raise ValueError("Motor duplicado: " + id_motor)
        if not hasattr(adaptador, "reporte"):
            raise ValueError("El motor debe extender AdaptadorMotor.")
        self._motores[id_motor] = adaptador

    def obtener(self, id_motor: str):
        return self._motores.get(id_motor)

    def reporte_todos(self) -> list:
        return [
            MotorInfo.desde_reporte(m.reporte(), id_m).to_dict()
            for id_m, m in sorted(self._motores.items())
        ]

    def contar_por_estado(self) -> dict:
        conteo = {}
        for m in self._motores.values():
            estado = m.reporte()["estado"]
            conteo[estado] = conteo.get(estado, 0) + 1
        return conteo

    def total(self) -> int:
        return len(self._motores)
