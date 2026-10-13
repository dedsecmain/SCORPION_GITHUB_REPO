import pytest

from scorpion.mk90_commands import requested_browser_url


@pytest.mark.parametrize("raw,expected", [
    ("https://store.steampowered.com", "https://store.steampowered.com"),
    ("https://example.com/path?a=1", "https://example.com/path?a=1"),
    ("store.steampowered.com", "https://store.steampowered.com"),
    ("lies webseite store.steampowered.com", "https://store.steampowered.com"),
    ("lies webseite https://example.com", "https://example.com"),
    ("ÖFFNE DIE WEBSEITE https://example.com", "https://example.com"),
    ("http://example.com", "http://example.com"),
    ("lies webseite http://localhost", "http://localhost"),
])
def test_mk90_browser_command_goes_directly_to_browser_preflight(raw, expected):
    assert requested_browser_url(raw) == expected


@pytest.mark.parametrize("raw", [
    "Hallo, was ist Steam?",
    "Erkläre mir https://example.com",
    "öffne browser",
    "lies webseite",
    "https://example.com hacked",
    "https://example.com\nsecret",
])
def test_mk90_does_not_mistake_prose_for_browser_command(raw):
    assert requested_browser_url(raw) is None
