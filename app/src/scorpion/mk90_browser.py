"""MK90: isolated, read-only Playwright browser preview.

Deliberately does not support forms, clicks, downloads, saved profiles or logins.
Web content is data and must never be interpreted as an agent instruction.
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit


class BrowserAccessDenied(ValueError):
    pass


class BrowserLoadError(RuntimeError):
    """Sanitized browser navigation error suitable for the Scorpion UI."""



def require_public_https_url(url: str) -> str:
    url = str(url).strip()
    if len(url) > 2048 or any(ord(char) < 32 for char in url):
        raise BrowserAccessDenied("Ungültige oder zu lange URL.")
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").rstrip(".").lower()
        port = parsed.port
    except ValueError as exc:
        raise BrowserAccessDenied("Ungültige URL.") from exc

    if (
        parsed.scheme != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or "%" in host
        or "\\" in host
    ):
        raise BrowserAccessDenied("Nur öffentliche HTTPS-Webseiten ohne Zugangsdaten sind erlaubt.")
    if (
        host in {"localhost", "localhost.localdomain"}
        or host.endswith((".localhost", ".local", ".internal", ".test"))
        or "." not in host
    ):
        raise BrowserAccessDenied("Lokale und interne Ziele sind gesperrt.")
    # Disallow browser-interpreted shorthand addresses such as 127.1 or 0x7f.1.
    if re.fullmatch(r"[0-9.]+", host) or any(part.startswith("0x") for part in host.split(".")):
        raise BrowserAccessDenied("Verschleierte IP-Adressen sind gesperrt.")
    if re.search(r"(?i)(?:^|[?&])(?:password|passwd|token|api[_-]?key|secret)=", parsed.query):
        raise BrowserAccessDenied("Zugangsdaten in URLs sind gesperrt.")
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not addr.is_global:
            raise BrowserAccessDenied("Private und lokale IP-Adressen sind gesperrt.")
    return url


@dataclass(frozen=True)
class BrowserPreview:
    url: str
    title: str
    body: str


class ReadOnlyBrowser:
    def __init__(self, *, max_chars: int = 3500, playwright_factory=None):
        self.max_chars = max(100, min(10000, int(max_chars)))
        self._factory = playwright_factory

    def preview(self, url: str) -> BrowserPreview:
        url = require_public_https_url(url)
        if self._factory is None:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError as exc:
                raise RuntimeError(
                    "Playwright fehlt in der Scorpion-Umgebung. Siehe docs/MK90.md."
                ) from exc
            factory = sync_playwright
        else:
            factory = self._factory

        with factory() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    accept_downloads=False,
                    permissions=[],
                    service_workers="block",
                    java_script_enabled=False,
                )
                try:
                    # Block local IP literals, unsafe schemes and internal hostnames,
                    # including during redirects and subresource loading.
                    allowed_host = urlsplit(url).hostname

                    def check_request(route):
                        try:
                            require_public_https_url(route.request.url)
                            if urlsplit(route.request.url).hostname != allowed_host:
                                raise BrowserAccessDenied("Weiterleitung auf eine andere Domain gesperrt.")
                        except BrowserAccessDenied:
                            route.abort()
                        else:
                            route.continue_()

                    context.route("**/*", check_request)
                    page = context.new_page()
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    except Exception as exc:
                        # Playwright's raw navigation errors can include verbose
                        # internal call logs and whole URLs. Show a concise reason.
                        detail = str(exc)
                        if "ERR_NAME_NOT_RESOLVED" in detail:
                            raise BrowserLoadError(
                                "Domain nicht gefunden. Prüfe die vollständige HTTPS-Adresse."
                            ) from None
                        if "Timeout" in detail or "timed out" in detail.lower():
                            raise BrowserLoadError(
                                "Webseite antwortet nicht rechtzeitig."
                            ) from None
                        raise BrowserLoadError(
                            "Webseite konnte nicht geladen werden."
                        ) from None
                    require_public_https_url(page.url)
                    if urlsplit(page.url).hostname != allowed_host:
                        raise BrowserAccessDenied("Weiterleitung auf eine andere Domain gesperrt.")
                    title = page.title()[:160]
                    body = page.locator("body").inner_text(timeout=5000)[: self.max_chars]
                    return BrowserPreview(url=page.url, title=title, body=body)
                finally:
                    context.close()
            finally:
                browser.close()
