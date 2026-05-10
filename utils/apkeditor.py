import os
import subprocess
import requests
import shutil
import json
import zipfile

from .env_loader import get_github_token

QUIET = "CI" in os.environ or "GITHUB_ACTIONS" in os.environ

GITHUB_API_URL = "https://api.github.com/repos/REAndroid/APKEditor/releases/latest"
BIN_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin")
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp")


def github_get(url: str, **kwargs) -> requests.Response:
    token = get_github_token()
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"token {token}"
    return requests.get(url, headers=headers, **kwargs)


class APKEditor:
    def __init__(self):
        pass

    def ensure_bin(self):
        os.makedirs(BIN_DIR, exist_ok=True)

    def ensure_temp(self):
        os.makedirs(TEMP_DIR, exist_ok=True)

    def get_latest_version(self) -> tuple[str, str]:
        print(f"[+] Checking latest APKEditor version...")
        response = github_get(GITHUB_API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        for asset in data.get("assets", []):
            if asset["name"].endswith(".jar"):
                jar_url = asset["browser_download_url"]
                version = asset["name"].replace("APKEditor-", "").replace(".jar", "")
                print(f"[+] Latest: APKEditor-{version}.jar ({asset['size'] / 1024:.1f} KB)")
                return version, jar_url

        raise Exception("No JAR found in latest release")

    def get_local_version(self) -> str | None:
        jar_files = [f for f in os.listdir(BIN_DIR) if f.startswith("APKEditor") and f.endswith(".jar")]
        if not jar_files:
            return None
        version = jar_files[0].replace("APKEditor-", "").replace(".jar", "")
        return version

    def get_jar_path(self) -> str:
        self.ensure_bin()
        local_version = self._get_local_version()

        try:
            latest_version, latest_url = self.get_latest_version()
        except Exception as e:
            if local_version:
                jar_file = f"APKEditor-{local_version}.jar"
                jar_path = os.path.join(BIN_DIR, jar_file)
                if os.path.exists(jar_path):
                    print(f"[+] Using cached (offline): {jar_file}")
                    return jar_path
            raise e

        if local_version == latest_version:
            jar_file = f"APKEditor-{local_version}.jar"
            print(f"[+] Using cached: {jar_file}")
            return os.path.join(BIN_DIR, jar_file)

        print(f"[+] Updating APKEditor to {latest_version}...")
        return self.download_jar(latest_url)

    def _get_local_version(self) -> str | None:
        jar_files = [f for f in os.listdir(BIN_DIR) if f.startswith("APKEditor") and f.endswith(".jar")]
        if not jar_files:
            return None
        return jar_files[0].replace("APKEditor-", "").replace(".jar", "")

    def download_jar(self, jar_url: str):
        self.ensure_bin()
        filename = os.path.basename(jar_url)
        filepath = os.path.join(BIN_DIR, filename)

        if os.path.exists(filepath):
            print(f"[+] JAR already exists: {filepath}")
            return filepath

        if not QUIET:
            print(f"[+] Downloading JAR...")
        response = requests.get(jar_url, stream=True, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if not QUIET and total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r[>] Downloading: {percent:.1f}%", end="", flush=True)

        if not QUIET:
            print(f"\n[+] JAR saved to: {filepath}")
        else:
            print(f"[+] JAR saved: {filepath}")
        return filepath

    def extract_xapk(self, xapk_path: str, output_dir: str):
        print(f"[>] Extracting XAPK: {xapk_path}")
        os.makedirs(output_dir, exist_ok=True)

        with zipfile.ZipFile(xapk_path, "r") as zip_ref:
            zip_ref.extractall(output_dir)

        print(f"[+] Extracted to: {output_dir}")

    def merge_apk(self, extract_dir: str, output_apk: str):
        jar_path = self.get_jar_path()
        print(f"[>] Merging APKs...")

        apk_files = [f for f in os.listdir(extract_dir) if f.endswith(".apk")]
        if not apk_files:
            raise Exception("No APK files found in extracted XAPK")

        print(f"[+] Found {len(apk_files)} split APKs")

        cmd = ["java", "-jar", jar_path, "m", "-i", extract_dir, "-o", output_apk]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"[-] Error: {result.stderr}")
            raise Exception("APKEditor merge failed")

        print(f"[+] Merged APK: {output_apk}")

    def convert_xapk_to_apk(self, xapk_path: str, output_dir: str, filename: str):
        self.ensure_temp()

        extract_dir = os.path.join(TEMP_DIR, "extract")
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)

        self.extract_xapk(xapk_path, extract_dir)

        output_apk = os.path.join(output_dir, filename)
        if os.path.exists(output_apk):
            os.remove(output_apk)

        self.merge_apk(extract_dir, output_apk)

        if os.path.exists(xapk_path):
            os.remove(xapk_path)

        shutil.rmtree(extract_dir)
        return output_apk


def get_local_version() -> str | None:
    jar_files = [f for f in os.listdir(BIN_DIR) if f.startswith("APKEditor") and f.endswith(".jar")]
    if not jar_files:
        return None
    version = jar_files[0].replace("APKEditor-", "").replace(".jar", "")
    return version