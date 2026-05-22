import requests


class Requester:
    _ua = None

    def __init__(self):
        if Requester._ua is None:
            from fake_useragent import UserAgent
            Requester._ua = UserAgent(platforms="desktop")

    def get(self, url: str, timeout: int = 60) -> requests.Response:
        headers = {"User-Agent": self._ua.random}
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response

    def get_text(self, url: str, timeout: int = 10) -> str:
        return self.get(url, timeout).text

    def get_stream(self, url: str, timeout: int = 10) -> requests.Response:
        headers = {"User-Agent": self._ua.random}
        return requests.get(url, headers=headers, stream=True, timeout=timeout)