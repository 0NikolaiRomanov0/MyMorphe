import os
import requests


def _get_token():
    from .env_loader import get_github_token
    return get_github_token()


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(PROJECT_ROOT, "bin")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
PATCHED_DIR = os.path.join(PROJECT_ROOT, "patched")
TEMP_DIR = os.path.join(PROJECT_ROOT, "temp")

QUIET = "CI" in os.environ or "GITHUB_ACTIONS" in os.environ

APP_YOUTUBE = "youtube"
APP_YOUTUBE_MUSIC = "youtube-music"
APP_REDDIT = "reddit"


def github_get(url, **kwargs):
    token = _get_token()
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"token {token}"
    return requests.get(url, headers=headers, **kwargs)


def stream_download(url, filepath, description="Downloading", headers=None):
    if not QUIET:
        print(f"[+] Downloading {description}...")
    req_headers = headers or {}
    response = requests.get(url, stream=True, timeout=60, headers=req_headers)
    response.raise_for_status()
    total_size = int(response.headers.get("content-length", 0))
    downloaded = 0
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if not QUIET and total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\r[>] {description}: {percent:.1f}%", end="", flush=True)
    if not QUIET:
        print()
    file_size = os.path.getsize(filepath)
    print(f"[+] Saved: {os.path.basename(filepath)} ({file_size / 1024:.1f} KB)")
    return filepath


def github_download(url, filepath, description="Downloading"):
    token = _get_token()
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    return stream_download(url, filepath, description, headers=headers)
