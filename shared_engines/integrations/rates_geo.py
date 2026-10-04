
"""Conectores GEO de la Red
(OpenStreetMap: Nominatim geocoding
+ Overpass consultas, sin key,
falla honesta). Nominatim publico:
max 1 req/seg - para produccion
nacional, self-host (punto 11)."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
import urllib.parse


class _HttpBase:
    """GET con UA de la Red + parse JSON."""

    name = "base"

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._timeout = timeout_seconds

    def _get_json(self, url: str):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent":
                "zyra-network/1.0"
            })
        with urllib.request.urlopen(
                req,
                timeout=self._timeout) as r:
            return json.loads(
                r.read().decode("utf-8"))

    def _sha(self, data) -> str:
        return hashlib.sha256(
            json.dumps(
                data,
                sort_keys=True,
                default=str).encode(
                "utf-8")).hexdigest()


class NominatimConnector(_HttpBase):
    """Geocoding: direccion ->
    coordenadas (y reversa)."""

    name = "nominatim"

    def __init__(
        self,
        *,
        min_interval_seconds: float = 1.1,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._min_interval = (
            min_interval_seconds)
        self._last_call = 0.0

    def _throttle(self) -> None:
        now = time.time()
        espera = (
            self._min_interval
            - (now - self._last_call))
        if espera > 0:
            time.sleep(espera)
        self._last_call = time.time()

    def geocode(
        self,
        query: str,
        *,
        country_codes: str = "sv",
        limit: int = 5,
    ) -> dict:
        """Direccion -> lista de
        coordenadas candidatas."""
        self._throttle()
        q = urllib.parse.quote(query)
        url = (
            "https://nominatim.openstreetmap.org"
            "/search?q=" + q
            + "&countrycodes="
            + country_codes
            + "&format=json&limit="
            + str(limit))
        d = self._get_json(url)
        resultados = []
        for it in d[:limit]:
            resultados.append({
                "display_name": it.get(
                    "display_name"),
                "lat": it.get("lat"),
                "lon": it.get("lon"),
                "type": it.get("type"),
            })
        resumen = {
            "source": self.name,
            "query": query,
            "count": len(resultados),
            "results": resultados,
        }
        resumen["sha256"] = self._sha(
            resumen)
        return resumen

    def reverse(
        self, *, lat: float,
        lon: float) -> dict:
        """Coordenadas -> direccion."""
        self._throttle()
        url = (
            "https://nominatim.openstreetmap.org"
            "/reverse?lat=" + str(lat)
            + "&lon=" + str(lon)
            + "&format=json")
        d = self._get_json(url)
        resumen = {
            "source": self.name,
            "lat": lat,
            "lon": lon,
            "display_name": d.get(
                "display_name"),
            "address": d.get("address"),
        }
        resumen["sha256"] = self._sha(
            resumen)
        return resumen


class OverpassConnector(_HttpBase):
    """Consultas de objetos OSM
    (amenities, caminos, areas)."""

    name = "overpass"

    def fetch(self, *, query: str) -> dict:
        """Ejecuta una query Overpass QL
        (ej: escuelas en un bounding box)."""
        q = urllib.parse.quote(query)
        url = (
            "https://overpass-api.de"
            "/api/interpreter?data=" + q)
        d = self._get_json(url)
        elems = d.get("elements", [])
        resumen = {
            "source": self.name,
            "count": len(elems),
            "elements": elems[:20],
        }
        resumen["sha256"] = self._sha(
            resumen)
        return resumen

    def amenities_in_bbox(
        self, *,
        south: float, west: float,
        north: float, east: float,
        amenity: str = "school",
    ) -> dict:
        """Atajos comunes: amenidades
        en un bounding box (ej: SV)."""
        query = (
            "[out:json][timeout:25];"
            "node[amenity=" + amenity + "]"
            "(" + str(south) + ","
            + str(west) + ","
            + str(north) + ","
            + str(east) + ");out 20;")
        return self.fetch(query=query)
