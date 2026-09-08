from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_MASTER_KEY = "aa" * 32


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _boot(tmp_path: Path) -> tuple[subprocess.Popen[bytes], str]:
    port = _free_port()
    env = dict(os.environ)
    env["ZYRA_PORT"] = str(port)
    env["ZYRA_DATA_DIR"] = str(tmp_path / "data")
    env["ZYRA_ROOT_KEY"] = TEST_MASTER_KEY
    env.pop("ZYRA_API_TOKEN", None)
    proc = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "main.py")],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30.0
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
                    return proc, base
        except Exception:
            time.sleep(0.3)
    proc.kill()
    raise RuntimeError("server never became healthy")


def test_production_server_serves_health(tmp_path: Path) -> None:
    proc, base = _boot(tmp_path)
    try:
        with urllib.request.urlopen(
            f"{base}/health", timeout=5
        ) as resp:
            assert resp.status == 200
        assert proc.poll() is None
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_health_shape(tmp_path: Path) -> None:
    proc, base = _boot(tmp_path)
    try:
        with urllib.request.urlopen(
            f"{base}/health", timeout=5
        ) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload["ok"] is True
        names = {
            c["component"]
            for c in payload["data"]["components"]
        }
        assert {
            "storage",
            "identity",
            "verification",
            "tokenization",
            "currency",
        } <= names
        assert payload["data"]["overall"]["status"] == "healthy"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_fails_closed_without_master_key(
    tmp_path: Path,
) -> None:
    port = _free_port()
    env = dict(os.environ)
    env["ZYRA_PORT"] = str(port)
    env["ZYRA_DATA_DIR"] = str(tmp_path / "data")
    env.pop("ZYRA_ROOT_KEY", None)
    proc = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "main.py")],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        out = (
            proc.communicate(timeout=15)[0].decode("utf-8")
            if proc.stdout
            else ""
        )
        assert proc.returncode != 0
        assert "ZYRA_ROOT_KEY is required" in out
    finally:
        if proc.poll() is None:
            proc.kill()


def test_key_file_persists_across_boots(
    tmp_path: Path,
) -> None:
    import hashlib

    data_dir = tmp_path / "persistent"
    fingerprints: list[str] = []
    for _ in range(2):
        port = _free_port()
        env = dict(os.environ)
        env["ZYRA_PORT"] = str(port)
        env["ZYRA_DATA_DIR"] = str(data_dir)
        env["ZYRA_ROOT_KEY"] = TEST_MASTER_KEY
        proc = subprocess.Popen(
            [sys.executable, str(REPO_ROOT / "main.py")],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        base = f"http://127.0.0.1:{port}"
        deadline = time.time() + 30.0
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(
                    f"{base}/health", timeout=2
                ) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(0.3)
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        key_file = data_dir / "root.key"
        assert key_file.exists()
        fingerprints.append(
            hashlib.sha256(
                key_file.read_text(encoding="utf-8").encode(
                    "utf-8"
                )
            ).hexdigest()[:16]
        )
    assert fingerprints[0] == fingerprints[1]
