
"""Tests GEO (mockeados)."""
from __future__ import annotations

import json

from shared_engines.integrations.rates_geo import (
    NominatimConnector,
    OverpassConnector,
)


class _R:
    def __init__(self, p):
        self._p = p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._p


def test_nominatim_geocode(
    tmp_path, monkeypatch) -> None:
    body = json.dumps([
        {"display_name":
         "San Salvador, SV",
         "lat": "13.69",
         "lon": "-89.19",
         "type": "city"}]).encode()
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: _R(body))
    r = NominatimConnector().geocode(
        "San Salvador")
    assert r["count"] == 1
    assert r["results"][0]["lat"] == "13.69"
    assert r["sha256"]
    print("OK geo: nominatim geocoding SV")


def test_nominatim_reverse(
    tmp_path, monkeypatch) -> None:
    body = json.dumps({
        "display_name":
        "Colon, La Libertad, SV",
        "address": {"city": "Colon"}}).encode()
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: _R(body))
    r = NominatimConnector().reverse(
        lat=13.68, lon=-89.20)
    assert "Colon" in r["display_name"]
    print("OK geo: nominatim reverse")


def test_overpass_amenities(
    tmp_path, monkeypatch) -> None:
    body = json.dumps({
        "elements": [
            {"type": "node",
             "id": 1,
             "lat": 13.7,
             "lon": -89.2},
            {"type": "node",
             "id": 2,
             "lat": 13.8,
             "lon": -89.3}]}).encode()
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: _R(body))
    r = OverpassConnector().amenities_in_bbox(
        south=13.0, west=-90.0,
        north=14.0, east=-88.0,
        amenity="school")
    assert r["count"] == 2
    assert r["elements"][0]["id"] == 1
    print("OK geo: overpass escuelas SV")
