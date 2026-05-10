import os
import time
import sys
from .requester import Requester

QUIET = "CI" in os.environ or "GITHUB_ACTIONS" in os.environ


class Downloader:
    def __init__(self):
        self.requester = Requester()

    def download(self, url: str, output_dir: str, filename: str):
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)

        if not QUIET:
            print(f"[>] Connecting to: {url[:60]}...")
        response = self.requester.get_stream(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "unknown")
        total_size = int(response.headers.get("content-length", 0))
        file_size_mb = total_size / 1024 / 1024

        if not QUIET:
            print(f"[>] Content-Type: {content_type}")
            print(f"[>] File Size: {file_size_mb:.2f} MB")
            print(f"[>] Saving to: {filepath}")

        downloaded = 0
        start_time = time.time()

        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if not QUIET and total_size > 0:
                        percent = (downloaded / total_size) * 100
                        elapsed = time.time() - start_time
                        speed = downloaded / 1024 / 1024 / elapsed if elapsed > 0 else 0
                        print(f"\r[>] {percent:.1f}% | {speed:.2f} MB/s | {downloaded/1024/1024:.1f}/{file_size_mb:.1f} MB", end="", flush=True)

        elapsed = time.time() - start_time
        avg_speed = file_size_mb / elapsed if elapsed > 0 else 0
        if not QUIET:
            print(f"\n[+] Download complete in {elapsed:.1f}s (avg {avg_speed:.2f} MB/s)")
            print(f"[+] File saved: {filepath}")
        else:
            print(f"[+] Downloaded: {filepath}")