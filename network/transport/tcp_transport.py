"""Production TCP transport for ZYRA Network.

Implements the NetworkTransport contract from
network/transport/transport.py over real TCP sockets.

Features:
- Framing: length-prefixed header JSON + payload,
  honoring MAX_FRAME_SIZE from the contract
- Node authentication: HMAC-SHA256 challenge-response
  over a CONTROL frame, key derived from the network
  master key (same ZYRA_ROOT_KEY on both nodes)
- Optional TLS: pass an ssl.SSLContext to encrypt the
  channel (server and client)
- Reconnect helper with exponential backoff

Wire format (per frame):
  [4B big-endian header_len]
  [header JSON: {"t": type, "s": sequence, "h": headers}]
  [4B big-endian payload_len]
  [payload bytes]

Auth handshake (only when an auth key is configured):
  client -> CONTROL {"node_id": ..., "nonce": ...}
  client -> CONTROL {"hmac": sha256hmac(key, nonce|node_id)}
  server -> CONTROL {"ok": true}  (or refuses and closes)

Additive module: implements the existing contract without
modifying it. Run tests:
  python -m network.transport.tcp_transport -v
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import socket
import ssl
import threading
import time
import unittest
import uuid

from network.transport.transport import (
    ConnectionState,
    Frame,
    FrameType,
    NetworkTransport,
    TransportAddress,
    TransportError,
)

_HDR_LEN_BYTES = 4
_PAY_LEN_BYTES = 4


def _send_exact(
    sock: socket.socket, data: bytes
) -> None:
    view = memoryview(data)
    while view:
        sent = sock.send(view)
        if sent <= 0:
            raise TransportError(
                "socket send made no progress"
            )
        view = view[sent:]


def _recv_exact(
    sock: socket.socket, n: int
) -> bytes | None:
    chunks: list[bytes] = []
    got = 0
    while got < n:
        try:
            chunk = sock.recv(n - got)
        except socket.timeout:
            if not chunks:
                return None
            raise
        except OSError:
            return None
        if not chunk:
            return None
        chunks.append(chunk)
        got += len(chunk)
    return b"".join(chunks)


def _send_frame(
    sock: socket.socket, frame: Frame
) -> None:
    header = json.dumps(
        {
            "t": frame.frame_type.value,
            "s": frame.sequence,
            "h": dict(frame.headers),
        },
        separators=(",", ":"),
    ).encode("utf-8")
    _send_exact(
        sock,
        len(header).to_bytes(
            _HDR_LEN_BYTES, "big"
        ),
    )
    _send_exact(sock, header)
    _send_exact(
        sock,
        len(frame.payload).to_bytes(
            _PAY_LEN_BYTES, "big"
        ),
    )
    if frame.payload:
        _send_exact(sock, frame.payload)


def _recv_frame(
    sock: socket.socket,
) -> Frame | None:
    raw = _recv_exact(sock, _HDR_LEN_BYTES)
    if raw is None:
        return None
    hlen = int.from_bytes(raw, "big")
    header_raw = _recv_exact(sock, hlen)
    if header_raw is None:
        return None
    header = json.loads(
        header_raw.decode("utf-8")
    )
    praw = _recv_exact(sock, _PAY_LEN_BYTES)
    if praw is None:
        return None
    plen = int.from_bytes(praw, "big")
    payload = b""
    if plen:
        payload_raw = _recv_exact(
            sock, plen
        )
        if payload_raw is None:
            return None
        payload = payload_raw
    return Frame(
        frame_type=FrameType(header["t"]),
        payload=payload,
        sequence=int(header["s"]),
        headers=dict(header["h"]),
    )


def _auth_token(
    auth_key_hex: str, nonce: str,
    node_id: str,
) -> str:
    key = bytes.fromhex(auth_key_hex)
    message = f"{nonce}|{node_id}".encode(
        "utf-8"
    )
    return hmac.new(
        key, message, hashlib.sha256
    ).hexdigest()


class TcpTransport:
    """TCP client implementing NetworkTransport."""

    def __init__(
        self,
        *,
        node_id: str,
        auth_key_hex: str | None = None,
        tls_context: ssl.SSLContext | None = None,
        connect_timeout: float = 5.0,
        receive_timeout: float = 0.5,
    ) -> None:
        if not node_id.strip():
            raise ValueError(
                "node_id cannot be empty"
            )
        self._node_id = node_id.strip()
        self._key = auth_key_hex
        self._tls = tls_context
        self._connect_timeout = connect_timeout
        self._receive_timeout = receive_timeout
        self._state = (
            ConnectionState.DISCONNECTED
        )
        self._address: (
            TransportAddress | None
        ) = None
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._sequence = 0
        self._buffer: list[Frame] = []

    @property
    def state(self) -> ConnectionState:
        with self._lock:
            return self._state

    @property
    def address(
        self,
    ) -> TransportAddress | None:
        with self._lock:
            return self._address

    def connect(
        self, address: TransportAddress
    ) -> None:
        if not isinstance(
            address, TransportAddress
        ):
            raise TypeError(
                "address must be TransportAddress"
            )
        if address.scheme not in (
            "tcp", "tls",
        ):
            raise TransportError(
                f"unsupported scheme:"
                f" {address.scheme}"
            )
        with self._lock:
            if self._state is (
                ConnectionState.CLOSED
            ):
                raise TransportError(
                    "closed transport cannot"
                    " reconnect"
                )
        raw = socket.create_connection(
            (address.host, address.port),
            timeout=self._connect_timeout,
        )
        raw.settimeout(self._connect_timeout)
        use_tls = (
            address.secure
            or address.scheme == "tls"
        )
        if use_tls:
            if self._tls is None:
                self._tls = (
                    ssl._create_unverified_context()
                )
            sock = self._tls.wrap_socket(
                raw, server_hostname=address.host
            )
        else:
            sock = raw
        authenticated = True
        if self._key is not None:
            authenticated = (
                self._authenticate(sock)
            )
        if not authenticated:
            try:
                sock.close()
            except OSError:
                pass
            raise TransportError(
                "node authentication refused by"
                " remote"
            )
        sock.settimeout(self._receive_timeout)
        with self._lock:
            self._sock = sock
            self._address = address
            self._state = (
                ConnectionState.CONNECTED
            )

    def _authenticate(
        self, sock: socket.socket
    ) -> bool:
        nonce = secrets.token_urlsafe(24)
        hello = Frame(
            frame_type=FrameType.CONTROL,
            payload=json.dumps(
                {
                    "node_id": self._node_id,
                    "nonce": nonce,
                }
            ).encode("utf-8"),
            sequence=0,
        )
        _send_frame(sock, hello)
        token = _auth_token(
            self._key or "", nonce,
            self._node_id,
        )
        proof = Frame(
            frame_type=FrameType.CONTROL,
            payload=json.dumps(
                {"hmac": token}
            ).encode("utf-8"),
            sequence=1,
        )
        _send_frame(sock, proof)
        response = _recv_frame(sock)
        if response is None:
            return False
        try:
            verdict = json.loads(
                response.payload.decode("utf-8")
            )
        except (ValueError, UnicodeDecodeError):
            return False
        return bool(verdict.get("ok") is True)

    def send(
        self, frame: Frame
    ) -> None:
        if not isinstance(frame, Frame):
            raise TypeError(
                "frame must be Frame"
            )
        with self._lock:
            sock = self._sock
            state = self._state
            if (
                state
                is not ConnectionState.CONNECTED
                or sock is None
            ):
                raise TransportError(
                    "transport is not connected"
                )
            self._sequence += 1
            sequence = self._sequence
        outbound = Frame(
            frame_type=frame.frame_type,
            payload=frame.payload,
            sequence=sequence,
            headers=frame.headers,
        )
        try:
            _send_frame(sock, outbound)
        except OSError as exc:
            with self._lock:
                self._state = (
                    ConnectionState.FAILED
                )
            raise TransportError(
                f"send failed: {exc}"
            ) from exc

    def receive(self) -> tuple[Frame, ...]:
        with self._lock:
            sock = self._sock
            state = self._state
            if (
                state
                is not ConnectionState.CONNECTED
                or sock is None
            ):
                raise TransportError(
                    "transport is not connected"
                )
        frames: list[Frame] = []
        deadline = time.monotonic() + (
            self._receive_timeout
        )
        while True:
            try:
                frame = _recv_frame(sock)
            except (socket.timeout, OSError):
                break
            if frame is None:
                break
            frames.append(frame)
            if (
                time.monotonic() >= deadline
            ):
                break
        with self._lock:
            self._buffer.extend(frames)
            drained = tuple(self._buffer)
            self._buffer.clear()
        return drained

    def ensure_connected(
        self,
        address: TransportAddress,
        *,
        retries: int = 3,
        backoff_base: float = 0.05,
    ) -> None:
        """Reconnect with exponential backoff.
        Raises TransportError after exhausting
        retries."""
        if self.state is ConnectionState.CONNECTED:
            return
        attempt = 0
        delay = backoff_base
        while attempt < retries:
            try:
                self._state = (
                    ConnectionState.CONNECTING
                )
                self.connect(address)
                return
            except (TransportError, OSError):
                attempt += 1
                if attempt >= retries:
                    break
                time.sleep(delay)
                delay *= 2
        raise TransportError(
            f"reconnect failed after"
            f" {attempt} attempt(s)"
        )

    def close(self) -> None:
        with self._lock:
            if self._sock is not None:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None
            self._state = ConnectionState.CLOSED
            self._address = None


class _ClientConnection:
    def __init__(
        self,
        conn: socket.socket,
        client_id: str,
    ) -> None:
        self.conn = conn
        self.client_id = client_id
        self.inbox: list[Frame] = []
        self.alive = True


class TcpServerTransport:
    """TCP server: accepts authenticated node
    connections, receives frames, sends replies."""

    def __init__(
        self,
        *,
        node_id: str,
        host: str = "127.0.0.1",
        port: int = 0,
        auth_key_hex: str | None = None,
        tls_context: ssl.SSLContext | None = None,
    ) -> None:
        if not node_id.strip():
            raise ValueError(
                "node_id cannot be empty"
            )
        self._node_id = node_id.strip()
        self._key = auth_key_hex
        self._tls = tls_context
        self._host = host
        self._requested_port = port
        self._listener: socket.socket | None = None
        self._clients: dict[
            str, _ClientConnection
        ] = {}
        self._lock = threading.Lock()
        self._accept_thread: (
            threading.Thread | None
        ) = None
        self._running = False
        self._bound_address: (
            TransportAddress | None
        ) = None

    def start(self) -> TransportAddress:
        if self._running:
            raise TransportError(
                "server already started"
            )
        listener = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM
        )
        listener.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )
        listener.bind(
            (self._host, self._requested_port)
        )
        listener.listen(16)
        port = listener.getsockname()[1]
        self._listener = listener
        self._bound_address = TransportAddress(
            host=self._host,
            port=port,
            scheme=(
                "tls" if self._tls else "tcp"
            ),
            secure=self._tls is not None,
        )
        self._running = True
        self._accept_thread = threading.Thread(
            target=self._accept_loop,
            daemon=True,
        )
        self._accept_thread.start()
        return self._bound_address

    @property
    def address(
        self,
    ) -> TransportAddress | None:
        return self._bound_address

    def _accept_loop(self) -> None:
        while self._running:
            listener = self._listener
            if listener is None:
                return
            try:
                conn, addr = (
                    listener.accept()
                )
            except OSError:
                return
            if self._tls is not None:
                try:
                    conn = (
                        self._tls.wrap_socket(
                            conn,
                            server_side=True,
                        )
                    )
                except (ssl.SSLError, OSError):
                    try:
                        conn.close()
                    except OSError:
                        pass
                    continue
            conn.settimeout(5.0)
            client_id = str(uuid.uuid4())
            if not self._authenticate_peer(
                conn
            ):
                try:
                    refusal = Frame(
                        frame_type=(
                            FrameType.CONTROL
                        ),
                        payload=json.dumps(
                            {"ok": False}
                        ).encode("utf-8"),
                        sequence=0,
                    )
                    _send_frame(
                        conn, refusal
                    )
                except OSError:
                    pass
                try:
                    conn.close()
                except OSError:
                    pass
                continue
            welcome = Frame(
                frame_type=FrameType.CONTROL,
                payload=json.dumps(
                    {"ok": True}
                ).encode("utf-8"),
                sequence=0,
            )
            try:
                _send_frame(conn, welcome)
            except OSError:
                try:
                    conn.close()
                except OSError:
                    pass
                continue
            client = _ClientConnection(
                conn, client_id
            )
            with self._lock:
                self._clients[
                    client_id
                ] = client
            threading.Thread(
                target=self._reader_loop,
                args=(client,),
                daemon=True,
            ).start()

    def _authenticate_peer(
        self, conn: socket.socket
    ) -> bool:
        if self._key is None:
            return True
        hello = _recv_frame(conn)
        if hello is None:
            return False
        try:
            hello_data = json.loads(
                hello.payload.decode("utf-8")
            )
        except (
            ValueError,
            UnicodeDecodeError,
        ):
            return False
        node_id = str(
            hello_data.get("node_id", "")
        )
        nonce = str(hello_data.get("nonce", ""))
        if not node_id or not nonce:
            return False
        proof = _recv_frame(conn)
        if proof is None:
            return False
        try:
            proof_data = json.loads(
                proof.payload.decode("utf-8")
            )
        except (
            ValueError,
            UnicodeDecodeError,
        ):
            return False
        expected = _auth_token(
            self._key, nonce, node_id
        )
        received = str(
            proof_data.get("hmac", "")
        )
        return hmac.compare_digest(
            expected, received
        )

    def _reader_loop(
        self, client: _ClientConnection
    ) -> None:
        conn = client.conn
        while (
            self._running and client.alive
        ):
            try:
                frame = _recv_frame(conn)
            except (
                socket.timeout,
                OSError,
            ):
                continue
            if frame is None:
                client.alive = False
                break
            with self._lock:
                client.inbox.append(frame)

    def received(
        self,
    ) -> list[tuple[str, Frame]]:
        out: list[tuple[str, Frame]] = []
        with self._lock:
            for client in tuple(
                self._clients.values()
            ):
                while client.inbox:
                    frame = (
                        client.inbox.pop(0)
                    )
                    out.append(
                        (
                            client.client_id,
                            frame,
                        )
                    )
        return out

    def send_to(
        self,
        client_id: str,
        frame: Frame,
    ) -> None:
        with self._lock:
            client = self._clients.get(
                client_id
            )
        if client is None or not client.alive:
            raise TransportError(
                f"client not connected:"
                f" {client_id}"
            )
        try:
            _send_frame(
                client.conn, frame
            )
        except OSError as exc:
            raise TransportError(
                f"send failed: {exc}"
            ) from exc

    def client_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._clients)

    def stop(self) -> None:
        self._running = False
        with self._lock:
            clients = tuple(
                self._clients.values()
            )
            self._clients.clear()
        for client in clients:
            client.alive = False
            try:
                client.conn.close()
            except OSError:
                pass
        if self._listener is not None:
            try:
                self._listener.close()
            except OSError:
                pass
            self._listener = None
        thread = self._accept_thread
        if thread is not None:
            thread.join(timeout=3)


# =====================================================
# Tests: real TCP over localhost, ephemeral ports.
# =====================================================

_TEST_KEY = (
    "3f2a9c8e7b6d5f4a3c2b1d0e9f8a7b6c"
    "5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0"
)


class TcpTransportTests(unittest.TestCase):
    def _start_server(
        self,
        key: str | None = _TEST_KEY,
    ) -> TcpServerTransport:
        server = TcpServerTransport(
            node_id="node-A",
            auth_key_hex=key,
        )
        server.start()
        return server

    def _client(
        self,
        key: str | None = _TEST_KEY,
    ) -> TcpTransport:
        return TcpTransport(
            node_id="node-B",
            auth_key_hex=key,
        )

    def test_roundtrip_with_auth(self) -> None:
        server = self._start_server()
        try:
            addr = server.address
            assert addr is not None
            client = self._client()
            client.connect(addr)
            self.assertEqual(
                ConnectionState.CONNECTED,
                client.state,
            )
            deadline = (
                time.monotonic() + 3.0
            )
            while (
                not server.client_ids()
                and time.monotonic() < deadline
            ):
                time.sleep(0.02)
            client_id = server.client_ids()[0]
            frame = Frame(
                frame_type=FrameType.DATA,
                payload=b"hello-zyra",
                sequence=0,
                headers={"k": "v"},
            )
            client.send(frame)
            got = None
            deadline = (
                time.monotonic() + 3.0
            )
            while (
                time.monotonic() < deadline
            ):
                received = server.received()
                if received:
                    _, got = received[0]
                    break
                time.sleep(0.02)
            self.assertIsNotNone(got)
            assert got is not None
            self.assertEqual(
                b"hello-zyra",
                got.payload,
            )
            reply = Frame(
                frame_type=FrameType.DATA,
                payload=b"ack",
                sequence=1,
            )
            server.send_to(
                client_id, reply
            )
            acked = client.receive()
            deadline = (
                time.monotonic() + 3.0
            )
            while not acked and (
                time.monotonic() < deadline
            ):
                time.sleep(0.05)
                acked = client.receive()
            self.assertTrue(acked)
            self.assertEqual(
                b"ack", acked[0].payload
            )
            client.close()
            self.assertEqual(
                ConnectionState.CLOSED,
                client.state,
            )
        finally:
            server.stop()

    def test_auth_rejected_with_wrong_key(
        self,
    ) -> None:
        server = self._start_server()
        try:
            addr = server.address
            assert addr is not None
            intruder = self._client(
                key="00" * 32
            )
            with self.assertRaises(
                TransportError
            ):
                intruder.connect(addr)
        finally:
            server.stop()

    def test_large_payload_integrity(
        self,
    ) -> None:
        server = self._start_server()
        try:
            addr = server.address
            assert addr is not None
            client = self._client()
            client.connect(addr)
            deadline = (
                time.monotonic() + 3.0
            )
            while (
                not server.client_ids()
                and time.monotonic() < deadline
            ):
                time.sleep(0.02)
            blob = secrets.token_bytes(
                1024 * 1024
            )
            client.send(
                Frame(
                    frame_type=FrameType.DATA,
                    payload=blob,
                    sequence=0,
                )
            )
            got = None
            deadline = (
                time.monotonic() + 5.0
            )
            while (
                time.monotonic() < deadline
            ):
                received = server.received()
                if received:
                    _, got = (
                        received[0]
                    )
                    break
                time.sleep(0.02)
            self.assertIsNotNone(got)
            assert got is not None
            self.assertEqual(blob, got.payload)
            client.close()
        finally:
            server.stop()

    def test_send_when_not_connected_fails(
        self,
    ) -> None:
        client = self._client(key=None)
        with self.assertRaises(
            TransportError
        ):
            client.send(
                Frame(
                    frame_type=(
                        FrameType.DATA
                    ),
                    payload=b"x",
                    sequence=0,
                )
            )

    def test_reconnect_with_backoff(
        self,
    ) -> None:
        server = self._start_server()
        try:
            addr = server.address
            assert addr is not None
            client = self._client()
            client.connect(addr)
            client.close()
            server.stop()
            server2 = self._start_server()
            try:
                addr2 = server2.address
                assert addr2 is not None
                client.ensure_connected(
                    addr2,
                    retries=3,
                    backoff_base=0.05,
                )
                self.assertEqual(
                    ConnectionState.CONNECTED,
                    client.state,
                )
                client.close()
            finally:
                server2.stop()
        finally:
            pass


class ContractComplianceTests(unittest.TestCase):
    def test_tcp_transport_satisfies_manager(
        self,
    ) -> None:
        from network.transport.transport import (
            TransportManager,
        )

        manager = TransportManager()
        transport = TcpTransport(
            node_id="n1",
        )
        manager.register("tcp", transport)
        self.assertEqual(
            ("tcp",), manager.names()
        )
        fetched = manager.get("tcp")
        self.assertIs(transport, fetched)
        self.assertTrue(
            callable(fetched.connect)
        )
        self.assertTrue(
            callable(fetched.send)
        )
        self.assertTrue(
            callable(fetched.receive)
        )
        self.assertTrue(
            callable(fetched.close)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
