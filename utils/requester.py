from curl_cffi import requests


class Requester:
    """HTTP client that impersonates a real browser via TLS fingerprint.

    Uses curl_cffi (curl-impersonate) instead of plain ``requests`` so that
    APKMirror and APKPure don't block us with Cloudflare's TLS/JA3
    fingerprint detection.  The API is intentionally kept identical to the
    old ``requests``-based class so callers don't need any changes.
    """

    _ua = None

    def __init__(self):
        if Requester._ua is None:
            from fake_useragent import UserAgent
            Requester._ua = UserAgent(platforms="desktop")

    def get_ua(self) -> str:
        """Return a random User-Agent string for use by other classes."""
        return self._ua.random

    def _headers(self, url: str) -> dict:
        """Build a header dict with a fresh random UA and standard fields.

        Mirrors what a real desktop Chrome browser sends so Cloudflare
        doesn't flag the request as automated.
        """
        return {
            "User-Agent": self._ua.random,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    def get(self, url: str, timeout: int = 60) -> requests.Response:
        response = requests.get(
            url,
            headers=self._headers(url),
            timeout=timeout,
            impersonate="chrome",
        )
        response.raise_for_status()
        return response

    def get_text(self, url: str, timeout: int = 10) -> str:
        return self.get(url, timeout).text

    def get_stream(self, url: str, timeout: int = 10) -> requests.Response:
        return requests.get(
            url,
            headers=self._headers(url),
            stream=True,
            timeout=timeout,
            impersonate="chrome",
        )

    def get_with_referer(self, url: str, referer: str,
                         timeout: int = 15) -> requests.Response:
        """GET with an explicit Referer header (needed for APKMirror
        download.php redirects)."""
        headers = self._headers(url)
        headers["Referer"] = referer
        return requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            impersonate="chrome",
        )
