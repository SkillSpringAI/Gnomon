import httpx
import pytest

from research_agent.adapters.llm.rule_based import RuleBasedClaimExtractor
from research_agent.adapters.web.http import HttpSourceRetriever, SourceRetrievalError
from research_agent.domain.research import SourceResponse, SourceType
from research_agent.ports.retrieval import SourceTarget


def test_http_retriever_normalizes_text_source() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/plain; charset=utf-8"},
            text="A bounded source body.",
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = HttpSourceRetriever(client=client).fetch(
        SourceTarget(uri="https://example.test/research")
    )

    assert result.content == "A bounded source body."
    assert result.content_type == "text/plain"
    assert result.title == "example.test/research"


def test_http_retriever_rejects_unsupported_scheme() -> None:
    with pytest.raises(SourceRetrievalError, match=r"HTTP\(S\)"):
        HttpSourceRetriever().fetch(SourceTarget(uri="file:///secret.txt"))


def test_rule_based_extractor_keeps_claims_unverified() -> None:
    source = SourceResponse(
        id="00000000-0000-0000-0000-000000000001",
        task_id="00000000-0000-0000-0000-000000000002",
        source_type=SourceType.WEB_PAGE,
        title="Test source",
        uri="https://example.test",
        publisher="Test publisher",
        content="Institutions adapt unevenly. This requires further corroboration.",
        reliability_score=0.5,
        observed_at="2026-01-01T00:00:00Z",
    )

    claims = RuleBasedClaimExtractor().extract(source)

    assert len(claims) == 2
    assert all(claim.status.value == "unverified" for claim in claims)
    assert all(claim.source_links[0].source_id == source.id for claim in claims)


class CountingStream(httpx.SyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.read_count = 0
        self.closed = False

    def __iter__(self):
        for chunk in self.chunks:
            self.read_count += 1
            yield chunk

    def close(self) -> None:
        self.closed = True


def test_redirect_policy_checks_every_hop_before_contact() -> None:
    from research_agent.application.source_registry import UntrustedSourceError

    contacted = []
    checked = []
    stream = CountingStream([b"redirect body must not be consumed"])

    def policy(uri: str) -> None:
        checked.append(uri)
        if httpx.URL(uri).host != "approved.test":
            raise UntrustedSourceError("Not approved")

    def handler(request: httpx.Request) -> httpx.Response:
        contacted.append(str(request.url))
        return httpx.Response(
            302, headers={"location": "https://other.test/private"}, stream=stream
        )

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        with pytest.raises(UntrustedSourceError):
            HttpSourceRetriever(client, url_policy=policy).fetch(
                SourceTarget(uri="https://approved.test/start")
            )
    assert contacted == ["https://approved.test/start"]
    assert checked == ["https://approved.test/start", "https://other.test/private"]
    assert stream.closed and stream.read_count == 0


def test_relative_redirect_and_html_normalization() -> None:
    checked = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/paper"})
        return httpx.Response(
            200,
            headers={"content-type": "Text/HTML; charset=utf-8"},
            text=(
                "<html><head><title>Research &amp; evidence</title><style>bad css</style></head>"
                "<body><p>One <b>important</b> result.</p><script>bad code</script>"
                "<template>hidden claim</template><p>Counterevidence &amp; uncertainty.</p>"
                "</body></html>"
            ),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = HttpSourceRetriever(client, url_policy=checked.append).fetch(
            SourceTarget(uri="https://approved.test/start")
        )
    assert checked == ["https://approved.test/start", "https://approved.test/paper"]
    assert result.uri == "https://approved.test/paper"
    assert result.title == "Research & evidence"
    assert result.content == "One important result.\nCounterevidence & uncertainty."


@pytest.mark.parametrize(
    "headers",
    [
        {"content-type": "text/plain"},
        {"content-type": "text/plain", "content-length": "1"},
    ],
)
def test_stream_limit_stops_consumption_and_closes_response(headers: dict) -> None:
    stream = CountingStream([b"1234", b"5678", b"must not read"])
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, headers=headers, stream=stream)
        )
    ) as client:
        with pytest.raises(SourceRetrievalError, match="maximum allowed size"):
            HttpSourceRetriever(client, max_bytes=6).fetch(SourceTarget(uri="https://example.test"))
    assert stream.read_count == 2
    assert stream.closed


@pytest.mark.parametrize(
    "headers, message",
    [
        ({"content-type": "text/plain", "content-length": "100"}, "maximum allowed size"),
        ({"content-type": "application/pdf"}, "Unsupported source content type"),
        ({"content-type": "application/json"}, "Unsupported source content type"),
        ({}, "Unsupported source content type"),
        ({"content-type": "text/plain", "content-encoding": "gzip"}, "Compressed"),
        ({"content-type": "text/plain", "content-length": "bad"}, "Invalid source content length"),
    ],
)
def test_unsupported_headers_reject_before_reading(headers: dict, message: str) -> None:
    stream = CountingStream([b"never read"])
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, headers=headers, stream=stream)
        )
    ) as client:
        with pytest.raises(SourceRetrievalError, match=message):
            HttpSourceRetriever(client, max_bytes=10).fetch(
                SourceTarget(uri="https://example.test")
            )
    assert stream.read_count == 0 and stream.closed


@pytest.mark.parametrize(
    "location, message",
    [
        ("/start", "loop"),
        ("file:///private", r"HTTP\(S\)"),
        ("https://user:secret@example.test", "credentials"),
        (None, "missing"),
    ],
)
def test_invalid_redirects_are_not_followed(location: str | None, message: str) -> None:
    contacted = []

    def handler(request: httpx.Request) -> httpx.Response:
        contacted.append(request.url)
        return httpx.Response(302, headers={"location": location} if location else {})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceRetrievalError, match=message):
            HttpSourceRetriever(client).fetch(SourceTarget(uri="https://example.test/start"))
    assert len(contacted) == 1


def test_redirect_limit() -> None:
    contacted = []

    def handler(request: httpx.Request) -> httpx.Response:
        contacted.append(request.url)
        return httpx.Response(302, headers={"location": f"/{len(contacted)}"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceRetrievalError, match="redirect limit"):
            HttpSourceRetriever(client, max_redirects=2).fetch(
                SourceTarget(uri="https://example.test/start")
            )
    assert len(contacted) == 3


@pytest.mark.parametrize(
    "body, content_type, message",
    [
        (b"   ", "text/plain", "no usable text"),
        (b"<script>Only code</script>", "text/html", "no usable text"),
        (b"\xff", "text/plain; charset=utf-8", "decoded"),
        (b"abc\x00", "text/plain", "binary"),
        (b"12345", "text/plain", "character count"),
    ],
)
def test_unusable_text_is_rejected(body: bytes, content_type: str, message: str) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={"content-type": content_type}, content=body
            )
        )
    ) as client:
        with pytest.raises(SourceRetrievalError, match=message):
            HttpSourceRetriever(client, max_characters=4).fetch(
                SourceTarget(uri="https://example.test")
            )


def test_exact_byte_limit_is_accepted() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={"content-type": "text/plain"}, content=b"1234"
            )
        )
    ) as client:
        assert (
            HttpSourceRetriever(client, max_bytes=4)
            .fetch(SourceTarget(uri="https://example.test"))
            .content
            == "1234"
        )


def test_stream_timeout_closes_response() -> None:
    class TimeoutStream(CountingStream):
        def __iter__(self):
            yield b"partial"
            raise httpx.ReadTimeout("Timed out")

    stream = TimeoutStream([])
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={"content-type": "text/plain"}, stream=stream
            )
        )
    ) as client:
        with pytest.raises(SourceRetrievalError, match="HTTP request failed"):
            HttpSourceRetriever(client).fetch(SourceTarget(uri="https://example.test"))
    assert stream.closed
