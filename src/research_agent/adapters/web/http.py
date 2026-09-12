"""Bounded HTTP source retrieval with per-hop policy validation."""

import time
from collections.abc import Callable
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpcore
import httpx

from research_agent.adapters.web.network import Deadline, PublicHTTPTransport, current_deadline
from research_agent.ports.retrieval import RetrievedSource, SourceTarget


class SourceRetrievalError(Exception):
    """Raised when a source cannot be retrieved within the supported policy."""


class _HTMLText(HTMLParser):
    """Extract static text, excluding scripts, styles, and document metadata."""

    hidden_tags = {"script", "style", "head", "template", "noscript"}
    block_tags = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden: list[str] = []
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True
        if tag in self.hidden_tags:
            self.hidden.append(tag)
        if not self.hidden and tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag in self.hidden:
            # Close malformed nested hidden markup conservatively up to this tag.
            index = len(self.hidden) - 1 - self.hidden[::-1].index(tag)
            del self.hidden[index:]
        if not self.hidden and tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        elif not self.hidden:
            self.parts.append(data)


class HttpSourceRetriever:
    """Retrieve bounded plain text or static HTML; other formats are rejected."""

    allowed_content_types = {"text/html", "text/plain"}
    redirect_codes = {301, 302, 303, 307, 308}

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        timeout_seconds: float = 15.0,
        total_timeout_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
        max_bytes: int = 2_000_000,
        max_redirects: int = 5,
        max_characters: int = 500_000,
        url_policy: Callable[[str], object] | None = None,
    ) -> None:
        if (
            max_bytes < 1
            or max_characters < 1
            or max_redirects < 0
            or timeout_seconds <= 0
            or total_timeout_seconds <= 0
        ):
            raise ValueError("Retrieval limits must be positive (redirects may be zero)")
        self.client = client or httpx.Client(transport=PublicHTTPTransport(), trust_env=False)
        self.total_timeout_seconds = total_timeout_seconds
        self.clock = clock
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.max_characters = max_characters
        self.url_policy = url_policy

    def _validate_url(self, uri: str) -> httpx.URL:
        if len(uri) > 2000:
            raise SourceRetrievalError("Source URL exceeds the maximum length")
        try:
            url = httpx.URL(uri)
        except (httpx.InvalidURL, ValueError) as exc:
            raise SourceRetrievalError("Invalid HTTP(S) URL") from exc
        if url.scheme not in {"http", "https"} or not url.host:
            raise SourceRetrievalError("Only valid HTTP(S) URLs are permitted")
        if url.userinfo:
            raise SourceRetrievalError("URLs containing credentials are not permitted")
        if self.url_policy is not None:
            self.url_policy(str(url))
        return url

    def fetch(self, target: SourceTarget) -> RetrievedSource:
        deadline = Deadline(self.clock() + self.total_timeout_seconds, self.clock)
        token = current_deadline.set(deadline)
        try:
            return self._fetch(target)
        finally:
            current_deadline.reset(token)

    def _fetch(self, target: SourceTarget) -> RetrievedSource:
        try:
            url = self._validate_url(target.uri)
            visited: set[str] = set()
            for hop in range(self.max_redirects + 1):
                canonical = str(url.copy_with(fragment=None))
                if canonical in visited:
                    raise SourceRetrievalError("Source redirect loop detected")
                visited.add(canonical)
                with self.client.stream(
                    "GET",
                    url,
                    follow_redirects=False,
                    timeout=current_deadline.get().remaining(self.timeout_seconds),
                    headers={"Accept-Encoding": "identity"},
                ) as response:
                    current_deadline.get().remaining()
                    if response.status_code in self.redirect_codes:
                        location = response.headers.get("location")
                        if not location:
                            raise SourceRetrievalError("Source redirect is missing its location")
                        if hop == self.max_redirects:
                            raise SourceRetrievalError("Source exceeds the redirect limit")
                        url = self._validate_url(str(url.join(location)))
                        continue
                    response.raise_for_status()
                    return self._read_source(response)
        except (
            httpx.HTTPError,
            httpx.InvalidURL,
            httpcore.TimeoutException,
            httpcore.NetworkError,
            httpcore.ProtocolError,
            OSError,
        ) as exc:
            raise SourceRetrievalError("Source HTTP request failed") from exc
        raise SourceRetrievalError("Source exceeds the redirect limit")

    def _read_source(self, response: httpx.Response) -> RetrievedSource:
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type not in self.allowed_content_types:
            raise SourceRetrievalError(
                f"Unsupported source content type: {content_type or 'unknown'}"
            )
        # Request identity encoding and reject servers that ignore it. This avoids
        # unbounded decompression before the byte budget can be enforced.
        if response.headers.get("content-encoding", "identity").strip().lower() != "identity":
            raise SourceRetrievalError("Compressed source responses are not supported")
        length = response.headers.get("content-length")
        if length is not None:
            try:
                size = int(length)
            except ValueError as exc:
                raise SourceRetrievalError("Invalid source content length") from exc
            if size < 0:
                raise SourceRetrievalError("Invalid source content length")
            if size > self.max_bytes:
                raise SourceRetrievalError("Source exceeds the maximum allowed size")
        body = bytearray()
        # Do not buffer the entire response or trust Content-Length alone.
        for chunk in response.iter_bytes():
            current_deadline.get().remaining()
            if len(body) + len(chunk) > self.max_bytes:
                raise SourceRetrievalError("Source exceeds the maximum allowed size")
            body.extend(chunk)
        if body.startswith(b"%PDF-"):
            raise SourceRetrievalError("PDF source extraction is not supported")
        encoding = response.encoding or "utf-8"
        try:
            content = body.decode(encoding)
        except (LookupError, UnicodeDecodeError) as exc:
            raise SourceRetrievalError("Source text could not be decoded") from exc
        if "\x00" in content:
            raise SourceRetrievalError("Source contains binary content")
        parsed = urlparse(str(response.url))
        title = parsed.netloc + (parsed.path if parsed.path != "/" else "")
        if content_type == "text/html":
            parser = _HTMLText()
            parser.feed(content)
            parser.close()
            content = "\n".join(
                line
                for part in "".join(parser.parts).splitlines()
                if (line := " ".join(part.split()))
            )
            title = " ".join("".join(parser.title_parts).split()) or title
        content = content.strip()
        if not content:
            raise SourceRetrievalError("Source contains no usable text")
        if len(content) > self.max_characters:
            raise SourceRetrievalError("Source text exceeds the maximum character count")
        current_deadline.get().remaining()
        return RetrievedSource(
            uri=str(response.url),
            title=title[:500],
            content=content,
            content_type=content_type,
        )
