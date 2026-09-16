from curl_cffi import requests as curl_requests


class Requester:
    """HTTP client that impersonates a real browser via TLS fingerprint.

    Uses curl_cffi (curl-impersonate) instead of plain ``requests`` so that
    APKMirror and APKPure don't block us with Cloudflare's TLS/JA3
    fingerprint detection.

    Key design choices (learned from revanced-morphe-builder):
    - ``impersonate`` must be passed per-request, NOT to the Session
      constructor (constructor arg produces 403).
    - A FIXED User-Agent per session, not random per-request.  Cloudflare
      detects UA-switching within a session and flags it as bot traffic.
    - Persistent cookies via Session so Cloudflare's ``cf_clearance``
      cookie survives across requests (same as ``curl -c/-b cookie.txt``).
    """

    # Fixed User-Agent matching the Chrome TLS fingerprint.
    # MUST be consistent across all requests in a session.
    _FIREFOX_UA = (
        "Mozilla/5.0 (X11; Linux x86_64; rv:148.0) "
        "Gecko/20100101 Firefox/148.0"
    )

    def __init__(self):
        # Persistent session -- cookies survive across requests.
        # Do NOT pass impersonate= here -- it breaks TLS fingerprinting.
        self._session = curl_requests.Session()
        self._session.headers.update({
            "User-Agent": self._FIREFOX_UA,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })

    def get_ua(self) -> str:
        """Return the fixed User-Agent string for use by other classes."""
        return self._FIREFOX_UA

    def get(self, url: str, timeout: int = 60) -> curl_requests.Response:
        response = self._session.get(
            url,
            timeout=timeout,
            impersonate="chrome",
        )
        response.raise_for_status()
        return response

    def get_text(self, url: str, timeout: int = 10) -> str:
        return self.get(url, timeout).text

    def get_stream(self, url: str, timeout: int = 10) -> curl_requests.Response:
        return self._session.get(
            url,
            stream=True,
            timeout=timeout,
            impersonate="chrome",
        )

    def get_with_referer(self, url: str, referer: str,
                         timeout: int = 15) -> curl_requests.Response:
        """GET with an explicit Referer header (needed for APKMirror
        download.php redirects)."""
        return self._session.get(
            url,
            headers={"Referer": referer},
            timeout=timeout,
            allow_redirects=True,
            impersonate="chrome",
        )
