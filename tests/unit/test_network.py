"""Network boundary tests; all DNS and sockets are controlled locally."""

import socket
import threading
import time

import httpx
import pytest

from research_agent.adapters.web import network
from research_agent.adapters.web.http import HttpSourceRetriever, SourceRetrievalError
from research_agent.ports.retrieval import SourceTarget


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "255.255.255.255",
        "192.0.2.1",
        "::",
        "::1",
        "fc00::1",
        "fe80::1",
        "ff02::1",
        "2001:db8::1",
        "::ffff:8.8.8.8",
        "2002:0808:0808::1",
        "64:ff9b::808:808",
        "fe80::1%3",
    ],
)
def test_non_public_and_transition_addresses_are_blocked(address: str) -> None:
    with pytest.raises(httpx.ConnectError):
        network.public_addresses([address])


def test_mixed_dns_answer_fails_closed() -> None:
    with pytest.raises(httpx.ConnectError):
        network.public_addresses(["8.8.8.8", "127.0.0.1"])
    with pytest.raises(httpx.ConnectError):
        network.public_addresses([])
    assert network.public_addresses(["8.8.8.8", "2606:4700:4700::1111"]) == [
        "8.8.8.8",
        "2606:4700:4700::1111",
    ]


class FakeSocket:
    def __init__(self, response: list[bytes]) -> None:
        self.response = iter(response)
        self.connected = None
        self.sent = b""
        self.closed = False
        self.timeouts = []

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def setsockopt(self, *args):
        pass

    def connect(self, address):
        self.connected = address

    def sendall(self, data):
        self.sent += data

    def recv(self, count):
        return next(self.response, b"")

    def close(self):
        self.closed = True


def test_production_transport_pins_ip_and_preserves_host_and_tls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dns_calls = []
    tls_names = []
    sock = FakeSocket(
        [b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK"]
    )

    def dns(host, port, **kwargs):
        dns_calls.append(host)
        # A second hostname resolution would redirect the connection to loopback.
        ip = "8.8.8.8" if len(dns_calls) == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    class TLSContext:
        def set_alpn_protocols(self, protocols):
            pass

        def wrap_socket(self, original, server_hostname):
            tls_names.append(server_hostname)
            return original

    monkeypatch.setattr(network.socket, "getaddrinfo", dns)
    monkeypatch.setattr(network.socket, "socket", lambda *args: sock)
    monkeypatch.setattr(network.ssl, "create_default_context", TLSContext)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")
    retriever = HttpSourceRetriever()
    try:
        result = retriever.fetch(SourceTarget(uri="https://public.test/evidence"))
    finally:
        retriever.client.close()
    assert result.content == "OK"
    assert dns_calls == ["public.test"]
    assert sock.connected == ("8.8.8.8", 443)
    assert tls_names == ["public.test"]
    assert b"Host: public.test\r\n" in sock.sent
    assert sock.closed


def test_private_dns_never_opens_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(network, "resolve_addresses", lambda *args: ["8.8.8.8", "10.0.0.1"])
    retriever = HttpSourceRetriever()

    def forbidden_socket(*args):
        pytest.fail("A socket must not be opened for a mixed/private DNS answer")

    monkeypatch.setattr(network.socket, "socket", forbidden_socket)
    try:
        with pytest.raises(SourceRetrievalError):
            retriever.fetch(SourceTarget(uri="https://approved.test"))
    finally:
        retriever.client.close()


def test_dns_wait_is_bounded_and_releases_worker_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()
    completed = threading.Event()
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(network, "_dns_slots", slots)

    def dns(*args, **kwargs):
        release.wait(1)
        completed.set()
        return []

    monkeypatch.setattr(network.socket, "getaddrinfo", dns)
    try:
        with pytest.raises(httpx.TimeoutException):
            network.resolve_addresses("slow.test", 80, network.Deadline(time.monotonic() + 0.02))
        with pytest.raises(httpx.ConnectError, match="capacity"):
            network.resolve_addresses("other.test", 80, network.Deadline(time.monotonic() + 1))
    finally:
        release.set()
    assert completed.wait(1)
    assert slots.acquire(timeout=1)
    slots.release()


def test_total_deadline_spans_redirects_and_closes_stream() -> None:
    now = [0.0]
    contacted = []

    def handler(request):
        contacted.append(str(request.url))
        now[0] += 2
        return httpx.Response(302, headers={"location": f"/{len(contacted)}"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        retriever = HttpSourceRetriever(client, total_timeout_seconds=3, clock=lambda: now[0])
        with pytest.raises(SourceRetrievalError):
            retriever.fetch(SourceTarget(uri="https://public.test/start"))
    assert len(contacted) == 2
    with pytest.raises(LookupError):
        network.current_deadline.get()


def test_slow_headers_cannot_reset_socket_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [0.0]

    class SlowSocket(FakeSocket):
        def recv(self, count):
            now[0] += 1
            return b"X-Partial: value\r\n"

    sock = SlowSocket([])
    monkeypatch.setattr(network, "resolve_addresses", lambda *args: ["8.8.8.8"])
    monkeypatch.setattr(network.socket, "socket", lambda *args: sock)
    retriever = HttpSourceRetriever(total_timeout_seconds=3, clock=lambda: now[0])
    try:
        with pytest.raises(SourceRetrievalError):
            retriever.fetch(SourceTarget(uri="http://public.test"))
    finally:
        retriever.client.close()
    assert now[0] == 3
    assert sock.closed
    assert sock.timeouts[-3:] == [3, 2, 1]


def test_tls_failure_closes_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    sock = FakeSocket([])
    stream = network.DeadlineStream(sock, network.Deadline(time.monotonic() + 1))

    class FailedTLS:
        def wrap_socket(self, *args, **kwargs):
            raise network.ssl.SSLCertVerificationError("Invalid certificate")

    with pytest.raises(network.ssl.SSLCertVerificationError):
        stream.start_tls(FailedTLS(), "public.test")
    assert sock.closed


def test_redirect_resolves_again_and_blocks_private_destination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved = []
    opened = []
    sock = FakeSocket(
        [
            b"HTTP/1.1 302 Found\r\nLocation: http://second.test/secret\r\n"
            b"Content-Length: 0\r\n\r\n",
        ]
    )

    def resolve(host, port, deadline):
        resolved.append(host)
        return ["8.8.8.8"] if host == "first.test" else ["127.0.0.1"]

    def create_socket(*args):
        opened.append(sock)
        return sock

    monkeypatch.setattr(network, "resolve_addresses", resolve)
    monkeypatch.setattr(network.socket, "socket", create_socket)
    retriever = HttpSourceRetriever()
    try:
        with pytest.raises(SourceRetrievalError):
            retriever.fetch(SourceTarget(uri="http://first.test/start"))
    finally:
        retriever.client.close()
    assert resolved == ["first.test", "second.test"]
    assert len(opened) == 1
    assert sock.closed


def test_slow_body_cannot_reset_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [0.0]

    class SlowBody(FakeSocket):
        def recv(self, count):
            if self.response is not None:
                self.response = None
                return b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 100\r\n\r\n"
            now[0] += 1
            return b"x"

    sock = SlowBody([])
    monkeypatch.setattr(network, "resolve_addresses", lambda *args: ["8.8.8.8"])
    monkeypatch.setattr(network.socket, "socket", lambda *args: sock)
    retriever = HttpSourceRetriever(total_timeout_seconds=3, clock=lambda: now[0])
    try:
        with pytest.raises(SourceRetrievalError):
            retriever.fetch(SourceTarget(uri="http://public.test"))
    finally:
        retriever.client.close()
    assert now[0] == 3
    assert sock.closed
    assert sock.timeouts[-3:] == [3, 2, 1]
