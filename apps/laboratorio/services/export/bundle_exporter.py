"""Exportador de bundle verificable: ZIP real + manifiesto con hashes.

Incluye datos del proyecto, escenas, artefactos, evaluaciones,
presentaciones y un manifiesto.json con SHA-256 por pieza y del
conjunto. Todo con stdlib (zipfile) y el hashing existente.
"""
import json
import zipfile
from io import BytesIO

from apps.laboratorio.shared.helpers.hashing import sha256_bytes


def _pieza(nombre: str, contenido: bytes) -> dict:
    """Pieza del manifiesto con hash real."""
    return {
        "nombre": nombre,
        "bytes": len(contenido),
        "sha256": sha256_bytes(contenido),
    }


def construir_bundle(datos_proyecto: dict, piezas: list) -> tuple:
    """Construye el ZIP verificable; devuelve (zip, piezas, sello)."""
    if not isinstance(datos_proyecto, dict) or not datos_proyecto.get("proyecto_id"):
        raise ValueError("Faltan los datos del proyecto.")
    if not isinstance(piezas, list) or not piezas:
        raise ValueError("El bundle requiere al menos una pieza.")
    manifiesto_piezas = []
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as paquete:
        for pieza in piezas:
            if not isinstance(pieza, dict) or "nombre" not in pieza or "contenido" not in pieza:
                raise ValueError("Cada pieza requiere nombre y contenido.")
            nombre = str(pieza["nombre"]).strip()
            if not nombre or "/" in nombre or "\\" in nombre or ".." in nombre:
                raise ValueError("Nombre de pieza inseguro: " + repr(nombre))
            if isinstance(pieza["contenido"], str):
                contenido = pieza["contenido"].encode("utf-8")
            else:
                contenido = bytes(pieza["contenido"])
            manifiesto_piezas.append(_pieza(nombre, contenido))
            paquete.writestr(nombre, contenido)
        registro = {
            "proyecto_id": str(datos_proyecto["proyecto_id"]),
            "titulo": str(datos_proyecto.get("titulo", "")),
            "tipo": str(datos_proyecto.get("tipo", "")),
            "generado_por": "ZYRA LABORATORIO - bundle verificable",
        }
        paquete.writestr("proyecto.json", json.dumps(registro, ensure_ascii=True, indent=2))
        manifiesto = {
            "formato": "zyra-lab-bundle/1",
            "piezas": manifiesto_piezas,
            "total_piezas": len(manifiesto_piezas),
        }
        paquete.writestr("manifiesto.json", json.dumps(manifiesto, ensure_ascii=True, indent=2))
    zip_bytes = buffer.getvalue()
    sello = {
        "total_piezas": len(manifiesto_piezas),
        "tamano_total": len(zip_bytes),
        "hash_sha256": sha256_bytes(zip_bytes),
    }
    return zip_bytes, manifiesto_piezas, sello
