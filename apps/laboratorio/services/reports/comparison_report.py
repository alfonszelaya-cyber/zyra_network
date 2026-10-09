"""Informe HTML real de una comparacion (descargable y sellable)."""

from apps.laboratorio.domain.comparison import Comparacion
from apps.laboratorio.infrastructure.security.html_sanitizer import escapar


def informe_html(comparacion: Comparacion, titulo_proyecto: str) -> bytes:
    """Genera el informe HTML del veredicto con tabla y ganador."""
    filas = []
    for i, p in enumerate(comparacion.participantes, 1):
        es_ganador = str(p.get("escenario_id", "")) == comparacion.ganador
        marca = ' <span class="pill">Ganador</span>' if es_ganador else ""
        metricas = p.get("metricas") or {}
        filas.append(
            "<tr><td>" + str(i) + "</td>"
            + "<td><b>" + escapar(p.get("titulo", "")) + "</b>" + marca + "</td>"
            + '<td><span class="pill">' + escapar(p.get("tipo", "")) + "</span></td>"
            + "<td>" + escapar(round(float(p.get("puntaje", 0.0)), 2)) + "</td>"
            + "<td>" + escapar(metricas.get("costo", "-")) + "</td>"
            + "<td>" + escapar(metricas.get("beneficio", "-")) + "</td>"
            + "<td>" + escapar(metricas.get("riesgo", "-")) + "</td></tr>"
        )
    partes_detalle = []
    for dimension, info in sorted((comparacion.detalle or {}).items()):
        partes_detalle.append(
            "<li><b>" + escapar(dimension) + "</b>: mejor " + escapar(info.get("mejor", ""))
            + " (" + escapar(info.get("valor", "")) + ")</li>"
        )
    html = (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<title>Informe de comparacion</title>"
        "<style>body{background:#0B1220;color:#E2E8F0;font-family:system-ui,sans-serif;padding:24px}"
        "h1{font-size:22px}h2{font-size:16px;margin-top:20px}.pill{background:rgba(5,150,105,.2);color:#34D399;border-radius:999px;padding:2px 10px;font-size:12px}"
        "table{border-collapse:collapse;width:100%;max-width:900px}td,th{border-bottom:1px solid #1E293B;padding:8px;text-align:left;font-size:14px}"
        "th{color:#94A3B8;font-size:12px;text-transform:uppercase}li{margin:6px 0}</style></head><body>"
        "<h1>Informe de comparacion</h1>"
        "<p style='color:#94A3B8'>Proyecto: " + escapar(titulo_proyecto) + "</p>"
        "<p>Ganador: <b>" + escapar(comparacion.ganador) + "</b> con una brecha de "
        + escapar(comparacion.brecha) + " puntos sobre el segundo.</p>"
        "<table><thead><tr><th>#</th><th>Escenario</th><th>Tipo</th><th>Puntaje</th>"
        "<th>Costo</th><th>Beneficio</th><th>Riesgo</th></tr></thead><tbody>"
        + "\n".join(filas) + "</tbody></table>"
        "<h2>Desglose por dimension</h2><ul>" + "\n".join(partes_detalle) + "</ul>"
        "<p style='color:#94A3B8;font-size:12px'>Generado por ZYRA LABORATORIO - comparacion "
        + escapar(str(comparacion.id)) + "</p></body></html>"
    )
    return html.encode("utf-8")
