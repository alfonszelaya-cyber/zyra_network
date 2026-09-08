from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def live_server(tmp_path: Path) -> subprocess.Popen[bytes]:
    port = _free_port()
    env = dict(os.environ)
    env["ZYRA_PORT"] = str(port)
    env["ZYRA_DATA_DIR"] = str(tmp_path / "data")
    env.pop("ZYRA_API_TOKEN", None)
    proc = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "main.py")],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20.0
    ready = False
    while time.time() < deadline:
        if proc.poll() is not None:
            out = (
                proc.stdout.read().decode("utf-8")
                if proc.stdout
                else ""
            )
            raise RuntimeError(f"server died early: {out}")
        try:
            with urllib.request.urlopen(
                f"{base}/health", timeout=2
            ) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(0.3)
    if not ready:
        proc.kill()
        raise RuntimeError("server did not become healthy")
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_production_server_serves_health(
    live_server: subprocess.Popen[bytes],
) -> None:
    port_env = None
    # The fixture does not expose the port directly; recover it
    # by hitting health through a retry loop is complex, so we
    # re-derive it from the same strategy: scan is unnecessary
    # because the fixture binds a free port that we stored in
    # the process environment.
    env_port = live_server.pid  # placeholder, replaced below
    del env_port
    # The server prints its port via ZYRA_PORT env var we set.
    # We recover the listening port by scanning /proc-free ways:
    # simplest reliable approach: the fixture returned after a
    # successful /health hit, so we just probe common temp via
    # the recorded env of the child is not portable; instead
    # the fixture stores it through the server's startup time.
    # For determinism, we re-request using the port saved at
    # generation time by re-running the same free-port logic
    # is impossible; therefore this test asserts on the fact
    # that the fixture succeeded (health was 200 before yield).
    assert live_server.poll() is None


def test_health_shape_via_env_port(
    tmp_path: Path,
) -> None:
    """Boots with a KNOWN port to assert the payload shape."""
    port = _free_port()
    env = dict(os.environ)
    env["ZYRA_PORT"] = str(port)
    env["ZYRA_DATA_DIR"] = str(tmp_path / "data")
    env.pop("ZYRA_API_TOKEN", None)
    proc = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "main.py")],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        deadline = time.time() + 20.0
        payload = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"{base}/health", timeout=2
                ) as resp:
                    if resp.status == 200:
                        payload = json.loads(
                            resp.read().decode("utf-8")
                        )
                        break
            except Exception:
                time.sleep(0.3)
        assert payload is not None, "server never became healthy"
        assert payload["ok"] is True
        data = payload["data"]
        components = {
            c["component"] for c in data["components"]
        }
        assert {
            "storage",
            "identity",
            "verification",
            "tokenization",
            "currency",
        } <= components
        assert data["overall"]["status"] == "healthy"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
