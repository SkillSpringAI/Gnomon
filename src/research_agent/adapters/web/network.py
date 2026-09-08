"""Public-address-only transport with a shared retrieval deadline."""

from __future__ import annotations

import ipaddress
import socket
import ssl
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

import httpcore
import httpx


@dataclass
class Deadline:
    expires_at: float
    clock: Callable[[], float] = time.monotonic

    def remaining(self, timeout: float | None = None) -> float:
        remaining = self.expires_at - self.clock()
        if remaining <= 0:
            raise httpx.TimeoutException("Source exceeded its total retrieval deadline")
        return remaining if timeout is None else min(remaining, timeout)


current_deadline: ContextVar[Deadline] = ContextVar("retrieval_deadline")
_dns_slots = threading.BoundedSemaphore(4)
SocketOption = tuple[int, int, int | bytes | bytearray] | tuple[int, int, None, int]


def resolve_addresses(host: str, port: int, deadline: Deadline) -> list[str]:
    """Bound caller wait and the number of uncancellable OS resolver calls."""
    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        pass
    if not _dns_slots.acquire(blocking=False):
        raise httpx.ConnectError("Source DNS resolver capacity exhausted")
    done = threading.Event()
    addresses: list[str] = []
    errors: list[Exception] = []

    def resolve() -> None:
        try:
            addresses.extend(
                str(row[4][0]) for row in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            )
        except Exception as exc:
            errors.append(exc)
        finally:
            _dns_slots.release()
            done.set()

    worker = threading.Thread(target=resolve, daemon=True, name="source-dns")
    try:
        worker.start()
    except Exception:
        _dns_slots.release()
        raise
    if not done.wait(deadline.remaining()):
        raise httpx.TimeoutException("Source DNS resolution exceeded its deadline")
    deadline.remaining()
    if errors:
        raise httpx.ConnectError("Source DNS resolution failed") from errors[0]
    return addresses


def public_addresses(addresses: list[str]) -> list[str]:
    """Reject the whole answer if any destination is non-public or ambiguous."""
    if not addresses:
        raise httpx.ConnectError("Source DNS returned no addresses")
    approved = []
    for value in addresses:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise httpx.ConnectError("Invalid source network address") from exc
        # Reject scoped, multicast and transition addresses, even where is_global
        # considers a mapped/translated public destination globally reachable.
        if (
            not address.is_global
            or address.is_multicast
            or "%" in value
            or isinstance(address, ipaddress.IPv6Address)
            and (
                address.ipv4_mapped is not None
                or address.sixtofour is not None
                or address.teredo is not None
                or address in ipaddress.ip_network("64:ff9b::/96")
                or address in ipaddress.ip_network("64:ff9b:1::/48")
            )
        ):
            raise httpx.ConnectError("Source destination must use public network addresses")
        if str(address) not in approved:
            approved.append(str(address))
    return approved


class DeadlineStream(httpcore.NetworkStream):
    def __init__(self, sock: socket.socket, deadline: Deadline) -> None:
        self.sock = sock
        self.deadline = deadline

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        try:
            self.sock.settimeout(self.deadline.remaining(timeout))
            result = self.sock.recv(max_bytes)
            self.deadline.remaining()
            return result
        except OSError as exc:
            raise httpx.ReadError("Source socket read failed") from exc

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        try:
            self.sock.settimeout(self.deadline.remaining(timeout))
            self.sock.sendall(buffer)
            self.deadline.remaining()
        except OSError as exc:
            raise httpx.WriteError("Source socket write failed") from exc

    def close(self) -> None:
        self.sock.close()

    def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> DeadlineStream:
        try:
            self.sock.settimeout(self.deadline.remaining(timeout))
            self.sock = ssl_context.wrap_socket(self.sock, server_hostname=server_hostname)
            self.deadline.remaining()
            return self
        except Exception:
            self.close()
            raise

    def get_extra_info(self, info: str) -> Any:
        if info == "ssl_object" and isinstance(self.sock, ssl.SSLSocket):
            return self.sock
        if info == "socket":
            return self.sock
        return None


class PublicNetworkBackend(httpcore.NetworkBackend):
    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[SocketOption] | None = None,
    ) -> DeadlineStream:
        deadline = current_deadline.get()
        addresses = public_addresses(resolve_addresses(host, port, deadline))
        for address in addresses:
            deadline.remaining()
            family = socket.AF_INET6 if ":" in address else socket.AF_INET
            sock = socket.socket(family, socket.SOCK_STREAM)
            try:
                sock.settimeout(deadline.remaining(timeout))
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                # Connect directly to the validated numeric IP: no second DNS lookup.
                sock.connect((address, port))
                deadline.remaining()
                return DeadlineStream(sock, deadline)
            except OSError:
                sock.close()
            except Exception:
                sock.close()
                raise
        raise httpx.ConnectError("Source connection failed")


class CoreResponseStream(httpx.SyncByteStream):
    def __init__(self, response: httpcore.Response) -> None:
        self.response = response

    def __iter__(self) -> Iterator[bytes]:
        yield from self.response.iter_stream()

    def close(self) -> None:
        self.response.close()


class PublicHTTPTransport(httpx.BaseTransport):
    """Keep Host and TLS identity intact while controlling actual socket destinations."""

    def __init__(self) -> None:
        self.pool = httpcore.ConnectionPool(
            ssl_context=ssl.create_default_context(),
            network_backend=PublicNetworkBackend(),
            max_keepalive_connections=0,
            retries=0,
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.pool.handle_request(
            httpcore.Request(
                method=request.method,
                url=httpcore.URL(
                    scheme=request.url.raw_scheme,
                    host=request.url.raw_host,
                    port=request.url.port,
                    target=request.url.raw_path,
                ),
                headers=request.headers.raw,
                content=request.stream,
                extensions=request.extensions,
            )
        )
        return httpx.Response(
            response.status,
            headers=response.headers,
            stream=CoreResponseStream(response),
            extensions=response.extensions,
        )

    def close(self) -> None:
        self.pool.close()
