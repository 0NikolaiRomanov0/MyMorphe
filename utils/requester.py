import requests
from fake_useragent import UserAgent


class Requester:
    def __init__(self):
        self.ua = UserAgent(platforms="desktop")

    def get(self, url: str, timeout: int = 10) -> requests.Response:
        headers = {"User-Agent": self.ua.random}
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response

    def get_text(self, url: str, timeout: int = 10) -> str:
        return self.get(url, timeout).text

    def get_stream(self, url: str, timeout: int = 10) -> requests.Response:
        headers = {"User-Agent": self.ua.random}
        return requests.get(url, headers=headers, stream=True, timeout=timeout)