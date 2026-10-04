
"""Tests conectores clima (mockeados)."""
from __future__ import annotations

import json

from shared_engines.integrations.rates_clima import (
    OpenMeteoConnector,
    NasapowerConnector,
    UsgsConnector,
    OpenAqConnector,
    ReliefwebConnector,
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


def _patch(monkeypatch, payload):
    body = json.dumps(payload).encode()
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: _R(body))


def test_open_meteo(tmp_path, monkeypatch) -> None:
    _patch(monkeypatch, {
        "current": {
            "temperature_2m": 31.2,
            "relative_humidity_2m": 60,
            "wind_speed_10m": 8.1},
        "daily": {
            "temperature_2m_max": [33.0]}})
    r = OpenMeteoConnector().fetch(
        lat=13.69, lon=-89.19)
    assert r["source"] == "open-meteo"
    assert r["temperature"] == 31.2
    assert r["sha256"]
    print("OK clima: open-meteo 31.2C")


def test_nasa_power(tmp_path, monkeypatch) -> None:
    _patch(monkeypatch, {
        "properties": {"parameter": {
            "T2M": {"JAN": 26.1},
            "PRECTOTCORR": {"JAN": 5.2}}}})
    r = NasapowerConnector().fetch(
        lat=13.69, lon=-89.19)
    assert r["source"] == "nasa-power"
    assert r["t2m"]["JAN"] == 26.1
    print("OK clima: nasa-power")


def test_usgs(tmp_path, monkeypatch) -> None:
    _patch(monkeypatch, {
        "features": [
            {"properties": {
                "mag": 5.1,
                "place": "El Salvador",
                "time": 1700000000000}}]})
    r = UsgsConnector().fetch(
        min_lat=12.5, max_lat=14.5,
        min_lon=-91.0, max_lon=-88.0)
    assert r["count"] == 1
    assert r["events"][0]["mag"] == 5.1
    print("OK clima: usgs sismos")


def test_openaq(tmp_path, monkeypatch) -> None:
    _patch(monkeypatch, {
        "results": [
            {"location": "San Salvador",
             "measurements": [
                 {"parameter": "pm25",
                  "value": 22.5}]}]})
    r = OpenAqConnector().fetch(
        lat=13.69, lon=-89.19)
    assert r["count"] == 1
    assert r["stations"][0]["location"] == "San Salvador"
    print("OK clima: openaq aire")


def test_reliefweb(tmp_path, monkeypatch) -> None:
    _patch(monkeypatch, {
        "data": [
            {"id": 12345,
             "fields": {
                 "name": "Flood SV"}}]})
    r = ReliefwebConnector().fetch(
        country_iso3="SLV")
    assert r["count"] == 1
    assert r["disasters"][0]["fields"]["name"] == "Flood SV"
    print("OK clima: reliefweb emergencias")
