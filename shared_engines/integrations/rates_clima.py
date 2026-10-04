
"""Conectores clima/geo/riesgo de la Red
(fuentes publicas sin key, falla honesta).
Cada fetch devuelve resumen normalizado
+ sha256 (Red ligera: transporta
confianza, no carga)."""
from __future__ import annotations

import hashlib
import json
import urllib.request


class _HttpBase:
    """GET con UA de la Red + parse JSON."""

    name = "base"

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
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


class OpenMeteoConnector(_HttpBase):
    """Clima/pronostico por lat/lon."""

    name = "open-meteo"

    def fetch(self, *, lat: float,
              lon: float) -> dict:
        url = (
            "https://api.open-meteo.com"
            "/v1/forecast"
            "?latitude=" + str(lat)
            + "&longitude=" + str(lon)
            + "&current=temperature_2m,"
            "relative_humidity_2m,"
            "wind_speed_10m"
            + "&daily=temperature_2m_max,"
            "temperature_2m_min,"
            "precipitation_sum"
            + "&timezone=auto")
        d = self._get_json(url)
        cur = d.get("current", {})
        resumen = {
            "source": self.name,
            "lat": lat,
            "lon": lon,
            "temperature": cur.get(
                "temperature_2m"),
            "humidity": cur.get(
                "relative_humidity_2m"),
            "wind_speed": cur.get(
                "wind_speed_10m"),
            "daily": d.get("daily"),
        }
        resumen["sha256"] = self._sha(
            resumen)
        return resumen


class NasapowerConnector(_HttpBase):
    """Agroclimatico historico."""

    name = "nasa-power"

    def fetch(self, *, lat: float,
              lon: float) -> dict:
        url = (
            "https://power.larc.nasa.gov"
            "/api/temporal/climatology"
            "?point"
            "&latitude=" + str(lat)
            + "&longitude=" + str(lon)
            + "&community=AG"
            + "&parameters=T2M,"
            "PRECTOTCORR,WS2M"
            + "&format=JSON")
        d = self._get_json(url)
        prop = d.get(
            "properties", {}).get(
            "parameter", {})
        resumen = {
            "source": self.name,
            "lat": lat,
            "lon": lon,
            "t2m": prop.get("T2M"),
            "precip": prop.get(
                "PRECTOTCORR"),
            "wind": prop.get("WS2M"),
        }
        resumen["sha256"] = self._sha(
            resumen)
        return resumen


class UsgsConnector(_HttpBase):
    """Sismos recientes por region."""

    name = "usgs"

    def fetch(self, *, min_lat: float,
              max_lat: float,
              min_lon: float,
              max_lon: float,
              min_magnitude: float = 4.0,
              days: int = 30) -> dict:
        url = (
            "https://earthquake.usgs.gov"
            "/fdsnws/event/1/query"
            "?format=geojson"
            "&minlatitude="
            + str(min_lat)
            + "&maxlatitude="
            + str(max_lat)
            + "&minlongitude="
            + str(min_lon)
            + "&maxlongitude="
            + str(max_lon)
            + "&minmagnitude="
            + str(min_magnitude)
            + "&starttime="
            + self._iso(days))
        d = self._get_json(url)
        feats = d.get("features", [])
        sismos = []
        for f in feats[:20]:
            pr = f.get(
                "properties", {})
            sismos.append({
                "mag": pr.get("mag"),
                "place": pr.get(
                    "place"),
                "time": pr.get(
                    "time"),
            })
        resumen = {
            "source": self.name,
            "count": len(feats),
            "events": sismos,
        }
        resumen["sha256"] = self._sha(
            resumen)
        return resumen

    def _iso(self, days: int) -> str:
        import datetime as _dt
        d = _dt.datetime.now(
            _dt.timezone.utc)
        d = d - _dt.timedelta(
            days=days)
        return d.strftime(
            "%Y-%m-%d")


class OpenAqConnector(_HttpBase):
    """Calidad del aire."""

    name = "openaq"

    def fetch(self, *, lat: float,
              lon: float,
              radius_m: int = 25000) -> dict:
        url = (
            "https://api.openaq.org"
            "/v2/latest"
            "?coordinates=" + str(lat)
            + "," + str(lon)
            + "&radius="
            + str(radius_m)
            + "&limit=20")
        d = self._get_json(url)
        results = d.get(
            "results", [])
        mediciones = []
        for r in results[:10]:
            mediciones.append({
                "location": r.get(
                    "location"),
                "measurements": r.get(
                    "measurements"),
            })
        resumen = {
            "source": self.name,
            "count": len(results),
            "stations": mediciones,
        }
        resumen["sha256"] = self._sha(
            resumen)
        return resumen


class ReliefwebConnector(_HttpBase):
    """Emergencias ONU por pais."""

    name = "reliefweb"

    def fetch(self, *,
              country_iso3: str = "SLV",
              limit: int = 10) -> dict:
        url = (
            "https://api.reliefweb.int"
            "/v1/disasters"
            "?appname=zyra-network"
            "&profile=list"
            "&limit=" + str(limit)
            + "&filter[field]=country.iso3"
            + "&filter[value]="
            + country_iso3)
        d = self._get_json(url)
        items = d.get("data", [])
        resumen = {
            "source": self.name,
            "count": len(items),
            "disasters": [],
        }
        for it in items[:limit]:
            resumen["disasters"].append({
                "id": it.get("id"),
                "fields": it.get(
                    "fields"),
            })
        resumen["sha256"] = self._sha(
            resumen)
        return resumen
