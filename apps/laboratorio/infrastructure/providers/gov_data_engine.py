"""GOV-DATA: Panel Nacional en Tiempo Real (capas A y B)."""
import time
from collections import deque

MAX_EVENTOS = 2000
UMBRAL_ALERTA = 10.0
DOMINIOS = {
    "educacion": ("SEMILLA",),
    "agro": ("AGRO",),
    "salud_justicia": ("AXIS",),
    "economia": ("NEXO",),
    "comercio": ("SUBASTAS",),
    "laboratorio": ("LABORATORIO",),
}


class MotorGovData:
    def __init__(self):
        self._eventos = deque(maxlen=MAX_EVENTOS)
        self._indicadores = {}
        self._secuencia = 0

    def capacidades(self):
        return {"capa_a": "panel operativo por app",
                "capa_b": "inteligencia nacional con recomendacion",
                "fuente": "eventos reales de la Red",
                "dominios": sorted(DOMINIOS.keys())}

    def _app_de_evento(self, nombre_evento):
        prefijo = str(nombre_evento).split(".")[0].upper()
        for dominio, apps in DOMINIOS.items():
            if prefijo in apps:
                return dominio
        return "otro"

    def ingestar(self, nombre_evento, datos=None, app=None):
        if not nombre_evento or not str(nombre_evento).strip():
            raise ValueError("nombre_evento requerido.")
        datos = dict(datos or {})
        self._secuencia += 1
        registro = {"seq": self._secuencia,
                    "evento": str(nombre_evento)[:150],
                    "app": str(app or self._app_de_evento(nombre_evento)),
                    "datos": datos,
                    "momento": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        self._eventos.append(registro)
        clave = registro["app"] + "." + str(nombre_evento)
        actual = self._indicadores.get(clave)
        if actual is None:
            self._indicadores[clave] = {"app": registro["app"],
                                        "indicador": str(nombre_evento)[:150],
                                        "conteo": 1, "ultimo_valor": None,
                                        "anterior_valor": None,
                                        "momento": registro["momento"]}
        else:
            actual["anterior_valor"] = actual["ultimo_valor"]
            actual["conteo"] += 1
            actual["momento"] = registro["momento"]
        valor = datos.get("valor")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            actual = self._indicadores[clave]
            actual["anterior_valor"] = actual["ultimo_valor"]
            actual["ultimo_valor"] = float(valor)
        return registro

    def capa_a(self):
        filas = []
        for clave in sorted(self._indicadores):
            ind = dict(self._indicadores[clave])
            delta = None
            if ind["ultimo_valor"] is not None and ind["anterior_valor"] is not None:
                delta = round(ind["ultimo_valor"] - ind["anterior_valor"], 4)
            gravedad = "normal"
            if delta is not None and abs(delta) >= UMBRAL_ALERTA:
                gravedad = "alerta"
            ind["delta"] = delta
            ind["gravedad"] = gravedad
            filas.append(ind)
        return {"indicadores": filas, "total": len(filas),
                "eventos_ingestados": self._secuencia}

    def capa_b(self):
        dominios = {}
        for clave, ind in self._indicadores.items():
            dominios.setdefault(ind["app"], []).append(ind)
        consolidado = []
        for dominio in sorted(dominios):
            indicadores = dominios[dominio]
            alertas = 0
            for i in indicadores:
                if i["ultimo_valor"] is not None and i["anterior_valor"] is not None:
                    if abs(i["ultimo_valor"] - i["anterior_valor"]) >= UMBRAL_ALERTA:
                        alertas += 1
            if alertas >= 3:
                gravedad = "critica"
                recomendacion = "Intervencion inmediata en " + dominio + ": " + str(alertas) + " indicadores con cambio brusco."
            elif alertas >= 1:
                gravedad = "alerta"
                recomendacion = "Monitorear " + dominio + ": " + str(alertas) + " indicador(es) con cambio significativo."
            else:
                gravedad = "normal"
                recomendacion = dominio + " estable: sin accion requerida."
            consolidado.append({"dominio": dominio, "indicadores": len(indicadores),
                                "eventos": sum(i["conteo"] for i in indicadores),
                                "alertas": alertas, "gravedad": gravedad,
                                "recomendacion": recomendacion})
        return {"dominios": consolidado, "total_dominios": len(consolidado),
                "dominios_en_alerta": sum(1 for d in consolidado if d["gravedad"] != "normal")}

    def historial(self, limite=100):
        limite = max(1, min(1000, int(limite)))
        eventos = list(self._eventos)
        return {"total": len(eventos), "eventos": eventos[-limite:]}
