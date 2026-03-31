"""Tests for request-scoped tracker dependencies."""

from starlette.requests import Request

from app.deps import get_write_source



def _request(headers=None):
    headers = headers or {}
    return Request(
        {
            "type": "http",
            "headers": [
                (key.lower().encode("latin-1"), value.encode("latin-1"))
                for key, value in headers.items()
            ],
        }
    )



def test_get_write_source_defaults_to_manual():
    assert get_write_source(_request()) == "manual"



def test_get_write_source_normalizes_legacy_aliases():
    assert get_write_source(_request({"X-Write-Source": "human"})) == "manual"
    assert (
        get_write_source(_request({"X-Write-Source": "fr_pipeline"}))
        == "federal_register"
    )



def test_get_write_source_allows_known_sources_and_falls_back_for_unknown():
    assert get_write_source(_request({"X-Write-Source": "ai"})) == "ai"
    assert get_write_source(_request({"X-Write-Source": "custom-app"})) == "manual"
