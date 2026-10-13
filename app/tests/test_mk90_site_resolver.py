"""MK90 website discovery tests run without installing desktop dependencies."""
from urllib.parse import quote

import pytest

from scorpion.mk90_site_resolver import (
    WebsiteLookupError,
    WebsiteSearchDenied,
    WebsiteMatch,
    WebsiteResolver,
    requested_website_name,
    resolve_with_consent,
    search_result_candidates,
)


@pytest.mark.parametrize("phrase,name", [
    ("lies die webseite von Netflix", "Netflix"),
    ("Lies mir die Website von Netflix vor", "Netflix"),
    ("öffne die Webseite von Spotify", "Spotify"),
    ("zeige mir die Homepage von GitHub", "GitHub"),
    ("lies die Website vom Zoo Zürich", "Zoo Zürich"),
    ("besuche die Webseite von Wikipedia", "Wikipedia"),
    ("schau dir die Seite von example AG an", "example AG"),
])
def test_natural_name_commands(phrase, name):
    assert requested_website_name(phrase) == name


@pytest.mark.parametrize("phrase", [
    "was ist netflix",
    "öffne den rechner",
    "ich finde netflix gut",
    "lies webseite https://example.com",
    "erkläre die Webseite",
    "lies die Webseite von password=secret",
])
def test_unrelated_text_does_not_trigger_name_search(phrase):
    assert requested_website_name(phrase) is None


def test_known_sites_work_offline_and_do_not_need_search():
    resolver = WebsiteResolver(search=lambda _: (_ for _ in ()).throw(AssertionError("no search")))
    result = resolver.known("Netflix")
    assert result.url == "https://www.netflix.com/"
    assert result.source == "known"
    assert resolver.known("  SPOTIFY ").url == "https://open.spotify.com/"
    assert resolver.known("unknown zoo") is None


def test_search_result_parser_unwraps_redirect_and_drops_unsafe_links():
    redirect = "https://duckduckgo.com/l/?uddg=" + quote("https://zoo.example.org/some/page")
    markup = (
        '<a class="result__a" href="' + redirect + '">Zoo Website</a>'
        '<a class="result-link" href="http://insecure.example.com/">HTTP</a>'
        '<a class="result-link" href="https://127.0.0.1/">Private</a>'
        '<a class="result__a" href="https://zoo.example.org/other">Duplicate</a>'
        '<a class="result-link" href="https://www.other-example.org/foo">Other</a>'
    )
    results = search_result_candidates(markup)
    assert [(hit.url, hit.title) for hit in results] == [
        ("https://zoo.example.org/", "Zoo Website"),
        ("https://www.other-example.org/", "Other"),
    ]


def test_resolver_known_site_does_not_request_external_permission():
    lookups = []
    def approval(_name):
        raise AssertionError("known websites must not trigger search permission")
    resolver = WebsiteResolver(search=lambda name: lookups.append(name))
    match = resolve_with_consent("Netflix", resolver, approval)
    assert match.url == "https://www.netflix.com/"
    assert not lookups


def test_unknown_site_requires_explicit_search_permission():
    search_calls = []
    resolver = WebsiteResolver(search=lambda name: search_calls.append(name) or [
        WebsiteMatch("https://public-zoo.example.org/", "Public Zoo", "search")
    ])
    with pytest.raises(WebsiteSearchDenied):
        resolve_with_consent("Zürcher Tiergarten", resolver, lambda _: False)
    assert search_calls == []
    match = resolve_with_consent("Zürcher Tiergarten", resolver, lambda _: True)
    assert match.url == "https://public-zoo.example.org/"
    assert match.source == "search"
    assert search_calls == ["Zürcher Tiergarten"]


def test_search_error_does_not_guess_domain():
    resolver = WebsiteResolver(search=lambda _name: [])
    with pytest.raises(WebsiteLookupError):
        resolve_with_consent("Nonexistent Private Club", resolver, lambda _: True)
