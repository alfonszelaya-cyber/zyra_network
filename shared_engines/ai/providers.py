
"""RED-9: IA plugable de la Red.

Contrato AIProvider + 3 fuentes con
fallback (AIChain, patron ProviderChain):
Gemini -> OpenAI -> Ollama. Keys por env
del dueno (GEMINI_API_KEY, OPENAI_API_KEY);
Ollama local en VPS (sin key). Sin key
configurada: falla HONESTO not_configured.
Cada analisis ejecutado queda registrado
por AIEngine (provenance firmado: modelo,
version, sha256 del contenido, veredicto,
confianza)."""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class AIResult:
    provider: str
    model: str
    verdict: str
    confidence: float
    raw: str


class AIProvider:
    """Contrato base de proveedor de IA."""

    name = "base"

    def analyze(self, prompt: str,
                content: str) -> AIResult:
        raise NotImplementedError


class _HttpJson:
    """POST JSON comun a los providers."""

    def __init__(self, *,
                 timeout_seconds: float = 60.0):
        self._timeout = timeout_seconds

    def _post(self, url: str,
              payload: dict,
              headers: dict) -> dict:
        body = json.dumps(
            payload).encode("utf-8")
        h = {"Content-Type":
             "application/json"}
        h.update(headers)
        req = urllib.request.Request(
            url,
            data=body,
            headers=h,
            method="POST")
        with urllib.request.urlopen(
                req,
                timeout=self._timeout) as r:
            return json.loads(
                r.read().decode("utf-8"))


class GeminiProvider(_HttpJson, AIProvider):
    """1a fuente: Gemini API (key del dueno)."""

    name = "gemini"

    def __init__(self, *,
                 api_key: str = "",
                 model: str = "gemini-1.5-flash",
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self._key = (api_key
                     or os.environ.get(
                         "GEMINI_API_KEY", ""))
        self._model = model

    def is_configured(self) -> bool:
        return bool(self._key)

    def analyze(self, prompt: str,
                content: str) -> AIResult:
        if not self.is_configured():
            raise RuntimeError(
                "not_configured:"
                " define GEMINI_API_KEY")
        url = ("https://generativelanguage"
               ".googleapis.com/v1beta/models/"
               + self._model
               + ":generateContent?key="
               + self._key)
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt + "\n\n"
                            + content}]}],
            "generationConfig": {
                "temperature": 0.1},
        }
        try:
            d = self._post(
                url, payload, {})
        except Exception as exc:
            raise RuntimeError(
                "gemini unavailable: "
                + type(exc).__name__) from exc
        try:
            text = (d["candidates"][0]
                    ["content"]["parts"][0]
                    ["text"])
        except (KeyError, IndexError):
            raise RuntimeError(
                "gemini respuesta inesperada")
        verdict = text.strip()[:200]
        return AIResult(
            provider=self.name,
            model=self._model,
            verdict=verdict,
            confidence=0.8,
            raw=text)


class OpenaiProvider(_HttpJson, AIProvider):
    """2a fuente: OpenAI API (key del dueno)."""

    name = "openai"

    def __init__(self, *,
                 api_key: str = "",
                 model: str = "gpt-4o-mini",
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self._key = (api_key
                     or os.environ.get(
                         "OPENAI_API_KEY", ""))
        self._model = model

    def is_configured(self) -> bool:
        return bool(self._key)

    def analyze(self, prompt: str,
                content: str) -> AIResult:
        if not self.is_configured():
            raise RuntimeError(
                "not_configured:"
                " define OPENAI_API_KEY")
        url = ("https://api.openai.com"
               "/v1/chat/completions")
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system",
                 "content": prompt},
                {"role": "user",
                 "content": content}],
            "temperature": 0.1,
        }
        try:
            d = self._post(
                url, payload, headers={
                    "Authorization":
                    "Bearer "
                    + self._key})
        except Exception as exc:
            raise RuntimeError(
                "openai unavailable: "
                + type(exc).__name__) from exc
        try:
            text = (d["choices"][0]
                    ["message"]["content"])
        except (KeyError, IndexError):
            raise RuntimeError(
                "openai respuesta inesperada")
        verdict = text.strip()[:200]
        return AIResult(
            provider=self.name,
            model=self._model,
            verdict=verdict,
            confidence=0.8,
            raw=text)


class OllamaProvider(_HttpJson, AIProvider):
    """3a fuente: IA local via Ollama en
    el VPS (localhost:11434). Sin key,
    sin costo, soberania total."""

    name = "ollama"

    def __init__(self, *,
                 host: str = "",
                 model: str = "llama3.2",
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self._host = (host
                      or os.environ.get(
                          "OLLAMA_HOST",
                          "http://localhost:11434"))
        self._model = model

    def is_configured(self) -> bool:
        return True

    def analyze(self, prompt: str,
                content: str) -> AIResult:
        url = (self._host
               + "/api/generate")
        payload = {
            "model": self._model,
            "prompt": prompt + "\n\n"
                      + content,
            "stream": False,
        }
        try:
            d = self._post(url, payload, {})
        except Exception as exc:
            raise RuntimeError(
                "ollama unavailable: "
                + type(exc).__name__) from exc
        text = d.get("response", "")
        verdict = text.strip()[:200]
        return AIResult(
            provider=self.name,
            model=self._model,
            verdict=verdict,
            confidence=0.6,
            raw=text)


class AIChain:
    """Fallback en orden: el primer
    provider configurado y disponible
    gana; los errores pasan al siguiente.
    Si todos fallan: error honesto."""

    def __init__(self,
                 providers: list) -> None:
        self._providers = list(providers)

    def analyze(self, prompt: str,
                content: str) -> AIResult:
        errores = []
        for p in self._providers:
            try:
                return p.analyze(
                    prompt, content)
            except Exception as exc:
                errores.append(
                    p.name + ": "
                    + type(exc).__name__)
        raise RuntimeError(
            "todos los providers de IA"
            " fallaron ("
            + "; ".join(errores) + ")")
