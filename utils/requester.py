import requests


class Requester:
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

        APKPure and APKMirror both require a Referer header on certain
        endpoints to bypass anti-bot protections.
        """
        return {
            "User-Agent": self._ua.random,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }

    def get(self, url: str, timeout: int = 60) -> requests.Response:
        response = requests.get(url, headers=self._headers(url), timeout=timeout)
        response.raise_for_status()
        return response

    def get_text(self, url: str, timeout: int = 10) -> str:
        return self.get(url, timeout).text

    def get_stream(self, url: str, timeout: int = 10) -> requests.Response:
        return requests.get(url, headers=self._headers(url),
                            stream=True, timeout=timeout)

    def get_with_referer(self, url: str, referer: str,
                         timeout: int = 15) -> requests.Response:
        """GET with an explicit Referer header (needed for APKMirror
        download.php redirects)."""
        headers = self._headers(url)
        headers["Referer"] = referer
        return requests.get(url, headers=headers, timeout=timeout,
                            allow_redirects=True)
