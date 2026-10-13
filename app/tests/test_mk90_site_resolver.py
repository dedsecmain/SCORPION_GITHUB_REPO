"""MK90 name-resolution and browser approval regression tests."""
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from scorpion.app import ScorpionController
from scorpion.mk90_browser import BrowserPreview
from scorpion.mk90_site_resolver import (
    WebsiteLookupError,
    WebsiteMatch,
    WebsiteResolver,
    requested_website_name,
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


def test_known_sites_work_offline_and_do_not_need_a_search():
    def refuse_search(_name):
        raise AssertionError("No search for known site")
    resolver = WebsiteResolver(search=refuse_search)
    result = resolver.known("Netflix")
    assert result.url == "https://www.netflix.com/"
    assert result.source == "known"
    assert resolver.known("  SPOTIFY ").url == "https://open.spotify.com/"
    assert resolver.known("unknown zoo") is None


def test_search_result_parser_unwraps_redirect_and_drops_private_http_and_duplicates():
    redirected = (
        "https://duckduckgo.com/l/?uddg="
        + quote("https://zoo.example.org/some/page")
    )
    markup = (
        '<a class="result__a" href="' + redirected + '">Zoo – Website</a>'
        '<a class="result-link" href="http://insecure.example.com/">Ignore</a>'
        '<a class="result-link" href="https://127.0.0.1/">Private</a>'
        '<a class="result__a" href="https://zoo.example.org/other">Duplicate</a>'
        '<a class="result-link" href="https://www.other-example.org/foo">Other</a>'
    )
    hits = search_result_candidates(markup)
    assert [(hit.url, hit.title) for hit in hits] == [
        ("https://zoo.example.org/", "Zoo – Website"),
        ("https://www.other-example.org/", "Other"),
    ]


class _FakeBrowser:
    def __init__(self):
        self.calls = []

    def preview(self, url):
        self.calls.append(url)
        return BrowserPreview(url=url, title="Example", body="Public website")


def controller_with_browser(*, approved=True):
    controller = object.__new__(ScorpionController)
    controller.settings = SimpleNamespace(
        mk90_browser_enabled=True, mk90_scanners_enabled=False
    )
    controller.mk90_browser = _FakeBrowser()
    controller.audit = None
    controller.local_ai = None
    reasons = []
    def approval(reason):
        reasons.append(reason)
        return approved
    controller.action_approval_callback = approval
    return controller, reasons


def test_netflix_name_skips_ollama_and_opens_only_after_domain_approval():
    controller, reasons = controller_with_browser()
    controller.mk90_resolver = WebsiteResolver(
        search=lambda _: (_ for _ in ()).throw(AssertionError("no search"))
    )
    result = controller.handle("lies die webseite von Netflix")
    assert "MK90 WEB" in result
    assert controller.mk90_browser.calls == ["https://www.netflix.com/"]
    assert len(reasons) == 1
    assert "www.netflix.com" in reasons[0]


def test_netflix_name_cannot_open_without_confirmation():
    controller, reasons = controller_with_browser(approved=False)
    controller.mk90_resolver = WebsiteResolver()
    result = controller.handle("lies die webseite von Netflix")
    assert "abgelehnt" in result
    assert controller.mk90_browser.calls == []
    assert len(reasons) == 1


def test_unknown_site_search_needs_prior_consent_and_destination_consent():
    controller, reasons = controller_with_browser()
    names = []
    controller.mk90_resolver = WebsiteResolver(
        search=lambda name: (names.append(name) or [
            WebsiteMatch("https://some-public-example.org/", "Zoo Example", "search")
        ])
    )
    result = controller.handle("lies die Webseite vom Zoo Beispiel")
    assert "MK90 WEB" in result
    assert names == ["Zoo Beispiel"]
    assert len(reasons) == 2
    assert "DuckDuckGo" in reasons[0]
    assert "some-public-example.org" in reasons[1]


def test_unknown_name_denied_search_never_uses_network():
    controller, reasons = controller_with_browser(approved=False)
    controller.mk90_resolver = WebsiteResolver(
        search=lambda name: (_ for _ in ()).throw(AssertionError("unexpected external lookup"))
    )
    assert "nicht freigegeben" in controller.handle("lies die Webseite vom Zoo Beispiel")
    assert len(reasons) == 1
    assert controller.mk90_browser.calls == []


def test_unknown_name_handles_search_provider_failure():
    controller, reasons = controller_with_browser()
    def failed(name):
        raise WebsiteLookupError("Websuche nicht erreichbar")
    controller.mk90_resolver = WebsiteResolver(search=failed)
    assert "Websuche nicht erreichbar" in controller.handle("lies die Webseite vom Zoo Beispiel")
    assert controller.mk90_browser.calls == []
    assert len(reasons) == 1
