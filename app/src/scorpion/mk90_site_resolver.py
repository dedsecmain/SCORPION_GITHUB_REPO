"""MK90 website-name lookup.

Known destinations use an offline, reviewed address list. Unknown names
can be looked up through a non-JavaScript public search page *after user
approval*. Search links are suggestions, never trusted instructions.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, unquote, urlsplit
from urllib.request import Request, urlopen

from .mk90_browser import BrowserAccessDenied, require_public_https_url


# Only use unambiguous, stable official homepages here.
_OFFICIAL_SITES = {
    "netflix": "https://www.netflix.com/",
    "steam": "https://store.steampowered.com/",
    "youtube": "https://www.youtube.com/",
    "google": "https://www.google.com/",
    "github": "https://github.com/",
    "openai": "https://openai.com/",
    "wikipedia": "https://de.wikipedia.org/",
    "roblox": "https://www.roblox.com/",
    "twitch": "https://www.twitch.tv/",
    "spotify": "https://open.spotify.com/",
    "reddit": "https://www.reddit.com/",
    "discord": "https://discord.com/",
}

_ALIASES = {"net flix": "netflix", "you tube": "youtube", "wiki": "wikipedia"}
_NAME_PATTERN = re.compile(r"(?iu)^[\wÀ-ÿ][\wÀ-ÿ .&+\-']{0,79}$")
_PREFIX = re.compile(
    r"(?iu)^(?:bitte\s+)?"
    r"(?:lies(?:\s+mir)?|zeige(?:\s+mir)?|öffne|oeffne|besuche|"
    r"schau(?:\s+dir)?)\s+"
    r"(?:die\s+|das\s+)?"
    r"(?:webseite|website|homepage|internetseite|seite)\s+"
    r"(?:von\s+|vom\s+|für\s+|fuer\s+)?"
    r"(?P<name>.+?)\s*[.!?]?\s*$"
)
_TRAILING = re.compile(r"(?iu)\s+(?:vorlesen|vor|bitte|an)$")
_QUICK_KNOWN = re.compile(
    r"(?iu)^(?:öffne|oeffne|besuche|geh(?:e)? auf)\s+(?P<name>.+?)\s*[.!?]?\s*$"
)


def requested_website_name(text: str) -> str | None:
    """Parse a natural German website-reading command, never arbitrary prose."""
    raw = " ".join(str(text or "").strip().split())
    match = _PREFIX.fullmatch(raw)
    if match:
        name = _TRAILING.sub("", match.group("name").strip()).strip()
    else:
        # Shorter commands work only for names in the reviewed offline
        # directory; otherwise app commands such as "öffne den Rechner"
        # must continue to use the existing Windows action policy.
        quick = _QUICK_KNOWN.fullmatch(raw)
        if not quick:
            return None
        name = quick.group("name").strip()
        key = _ALIASES.get(name.casefold(), name.casefold())
        if key not in _OFFICIAL_SITES:
            return None
    if (
        not _NAME_PATTERN.fullmatch(name)
        or name.casefold().startswith(("http", "www."))
        or "password" in name.casefold()
        or "token" in name.casefold()
    ):
        return None
    return name


@dataclass(frozen=True)
class WebsiteMatch:
    url: str
    title: str
    source: str  # "known" or "search"


class WebsiteLookupError(RuntimeError):
    pass


def _unwrap_result_link(link: str) -> str | None:
    """Accept a plain HTTPS result or DDG's redirect, but never visit it."""
    link = html.unescape(link.strip())
    if link.startswith("//"):
        link = "https:" + link
    try:
        parsed = urlsplit(link)
        if parsed.hostname in {"duckduckgo.com", "www.duckduckgo.com"} and parsed.path.startswith("/l/"):
            embedded = parse_qs(parsed.query).get("uddg", [])
            link = embedded[0] if embedded else ""
    except ValueError:
        return None
    try:
        require_public_https_url(link)
    except BrowserAccessDenied:
        return None
    return link


class _ResultsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.current_href: str | None = None
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        data = dict(attrs)
        classes = set((data.get("class") or "").split())
        if classes & {"result-link", "result__a"}:
            self.current_href = data.get("href")
            self.parts = []

    def handle_data(self, data):
        if self.current_href is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current_href is not None:
            self.links.append((self.current_href, " ".join(self.parts).strip()[:120]))
            self.current_href = None
            self.parts = []


def search_result_candidates(markup: str) -> list[WebsiteMatch]:
    parser = _ResultsParser()
    parser.feed(markup[:350000])
    matches = []
    seen = set()
    for link, title in parser.links:
        target = _unwrap_result_link(link)
        if target is None:
            continue
        parsed = urlsplit(target)
        host = (parsed.hostname or "").lower()
        if host in seen:
            continue
        seen.add(host)
        # Search result paths, cookies and query parameters are untrusted.
        homepage = require_public_https_url("https://" + host + "/")
        matches.append(WebsiteMatch(homepage, title or host, "search"))
        if len(matches) >= 5:
            break
    return matches


def _search_public(query: str) -> list[WebsiteMatch]:
    """No API key or JS required; failure is safe and should be shown."""
    target = "https://html.duckduckgo.com/html/?q=" + quote(query + " offizielle website")
    req = Request(target, headers={"User-Agent": "Mozilla/5.0 (compatible; ScorpionMK90/1.0)"})
    try:
        with urlopen(req, timeout=9) as response:
            if response.geturl().split("?")[0] != "https://html.duckduckgo.com/html/":
                raise WebsiteLookupError("Suchanbieter hat unerwartet weitergeleitet.")
            markup = response.read(350001)
            if len(markup) > 350000:
                raise WebsiteLookupError("Suchergebnis ist zu groß.")
            return search_result_candidates(markup.decode("utf-8", errors="replace"))
    except WebsiteLookupError:
        raise
    except Exception as exc:
        raise WebsiteLookupError("Die Websuche ist momentan nicht verfügbar.") from exc


class WebsiteResolver:
    def __init__(self, *, search=None):
        self._search = search or _search_public

    def known(self, name: str) -> WebsiteMatch | None:
        key = " ".join(name.casefold().strip().split())
        key = _ALIASES.get(key, key)
        url = _OFFICIAL_SITES.get(key)
        return WebsiteMatch(url, name, "known") if url else None

    def search(self, name: str) -> WebsiteMatch:
        """Return a *suggestion*; the caller must show it for confirmation."""
        results = self._search(name)
        if not results:
            raise WebsiteLookupError("Keine passende Webseite gefunden. Bitte gib die URL an.")
        return results[0]


class WebsiteSearchDenied(WebsiteLookupError):
    """The user did not approve transmitting this name to a search service."""


def resolve_with_consent(name: str, resolver: WebsiteResolver, approve_search) -> WebsiteMatch:
    """Return a site without unnecessary queries; unknown names require consent."""
    known = resolver.known(name)
    if known is not None:
        return known
    if not approve_search(name):
        raise WebsiteSearchDenied("Websuche nicht freigegeben.")
    return resolver.search(name)
