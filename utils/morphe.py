import os
import re
import subprocess
import shutil

from .common import (
    QUIET, github_get, stream_download, github_download,
    BIN_DIR, OUTPUT_DIR, PATCHED_DIR,
    APP_YOUTUBE, APP_YOUTUBE_MUSIC, APP_REDDIT
)

MORPHE_CLI_URL = "https://api.github.com/repos/MorpheApp/morphe-cli/releases/latest"
MORPHE_PATCHES_URL = "https://api.github.com/repos/MorpheApp/morphe-patches/releases/latest"
MICROG_RE_URL = "https://api.github.com/repos/MorpheApp/MicroG-RE/releases/latest"

PACKAGE_YOUTUBE = "com.google.android.youtube"
PACKAGE_YOUTUBE_MUSIC = "com.google.android.apps.youtube.music"
PACKAGE_REDDIT = "com.reddit.frontpage"


class Morphe:
    def __init__(self):
        pass

    def ensure_bin(self):
        os.makedirs(BIN_DIR, exist_ok=True)

    def get_latest_cli_version(self) -> tuple[str, str]:
        print(f"[+] Checking latest morphe-cli...")
        response = github_get(MORPHE_CLI_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        for asset in data.get("assets", []):
            if asset["name"].endswith(".jar"):
                jar_url = asset["browser_download_url"]
                version = asset["name"].replace("morphe-cli-", "").replace(".jar", "")
                print(f"[+] Latest: morphe-cli-{version}.jar ({asset['size'] / 1024:.1f} KB)")
                return version, jar_url

        raise Exception("No CLI JAR found in latest release")

    def get_latest_patches_version(self) -> tuple[str, str]:
        print(f"[+] Checking latest morphe-patches...")
        response = github_get(MORPHE_PATCHES_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        tag_name = data.get("tag_name", "")
        for asset in data.get("assets", []):
            if asset["name"].endswith(".mpp"):
                mpp_url = asset["browser_download_url"]
                print(f"[+] Latest: {asset['name']} ({asset['size'] / 1024:.1f} KB)")
                return tag_name.replace("v", ""), mpp_url

        raise Exception("No patches MPP found in latest release")

    def get_local_cli_version(self) -> str | None:
        jar_files = [f for f in os.listdir(BIN_DIR) if f.startswith("morphe-cli-") and f.endswith(".jar")]
        if not jar_files:
            return None
        version = jar_files[0].replace("morphe-cli-", "").replace(".jar", "")
        return version

    def get_local_patches_version(self) -> str | None:
        mpp_files = [f for f in os.listdir(BIN_DIR) if f.startswith("patches-") and f.endswith(".mpp")]
        if not mpp_files:
            return None
        version = mpp_files[0].replace("patches-", "").replace(".mpp", "")
        return version

    def get_cli_path(self) -> str:
        self.ensure_bin()
        local_version = self.get_local_cli_version()

        try:
            latest_version, latest_url = self.get_latest_cli_version()
        except Exception as e:
            if local_version:
                jar_file = f"morphe-cli-{local_version}.jar"
                cli_path = os.path.join(BIN_DIR, jar_file)
                if os.path.exists(cli_path):
                    print(f"[+] Using cached CLI (offline): {jar_file}")
                    return cli_path
            raise e

        if local_version == latest_version:
            jar_file = f"morphe-cli-{local_version}.jar"
            print(f"[+] Using cached CLI: {jar_file}")
            return os.path.join(BIN_DIR, jar_file)

        print(f"[+] Updating morphe-cli to {latest_version}...")
        return self.download_cli(latest_url, latest_version)

    def get_patches_path(self) -> str:
        self.ensure_bin()
        local_version = self.get_local_patches_version()

        try:
            latest_version, latest_url = self.get_latest_patches_version()
        except Exception as e:
            if local_version:
                mpp_file = f"patches-{local_version}.mpp"
                mpp_path = os.path.join(BIN_DIR, mpp_file)
                if os.path.exists(mpp_path):
                    print(f"[+] Using cached patches (offline): {mpp_file}")
                    return mpp_path
            raise e

        mpp_file = f"patches-{latest_version}.mpp"
        mpp_path = os.path.join(BIN_DIR, mpp_file)

        if local_version == latest_version and os.path.exists(mpp_path):
            print(f"[+] Using cached patches: {mpp_file}")
            return mpp_path

        print(f"[+] Downloading morphe-patches v{latest_version}...")
        return self.download_patches(latest_url, latest_version)

    def download_cli(self, url: str, version: str):
        filename = f"morphe-cli-{version}.jar"
        filepath = os.path.join(BIN_DIR, filename)
        stream_download(url, filepath, "CLI")
        return filepath

    def download_patches(self, url: str, version: str):
        mpp_path = os.path.join(BIN_DIR, f"patches-{version}.mpp")
        stream_download(url, mpp_path, "Patches")
        return mpp_path

    def setup(self):
        cli_path = self.get_cli_path()
        patches_path = self.get_patches_path()
        return cli_path, patches_path

    def list_versions(self, patches_path: str | None = None, cli_path: str | None = None) -> dict:
        if patches_path is None:
            patches_path = self.get_patches_path()

        if cli_path is None:
            cli_path = self.get_cli_path()

        cmd = ["java", "-jar", cli_path, "list-versions", f"--patches={patches_path}"]
        print(f"[+] Running: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=BIN_DIR)

        output = result.stdout
        print(output)

        versions = {
            APP_YOUTUBE: [],
            APP_YOUTUBE_MUSIC: [],
            APP_REDDIT: []
        }

        current_package = None
        for line in output.splitlines():
            if "Package name:" in line:
                pkg = line.split("Package name:")[1].strip()
                if pkg == PACKAGE_YOUTUBE:
                    current_package = APP_YOUTUBE
                elif pkg == PACKAGE_YOUTUBE_MUSIC:
                    current_package = APP_YOUTUBE_MUSIC
                elif pkg == PACKAGE_REDDIT:
                    current_package = APP_REDDIT
                else:
                    current_package = None
            elif current_package and line.strip():
                match = re.match(r"\s+(\S+)\s+\(\d+ patches\)", line)
                if match:
                    version = match.group(1)
                    versions[current_package].append(version)

        return versions

    def check_missing_versions(self) -> dict:
        patches_path = self.get_patches_path()
        versions = self.list_versions(patches_path)

        missing = {}

        for app, version_list in versions.items():
            if not version_list:
                continue

            for version in version_list:
                apk_name = f"{app}-{version}.apk"
                apk_path = os.path.join(OUTPUT_DIR, apk_name)
                if not os.path.exists(apk_path):
                    missing.setdefault(app, []).append(version)
                    print(f"[-] {app} {version} not found in output folder")
                else:
                    print(f"[+] {app} {version} already exists")

        return missing

    def get_missing(self) -> dict:
        return self.check_missing_versions()

    def get_app_url(self, app: str) -> str:
        return {
            APP_YOUTUBE: "https://youtube.en.uptodown.com/android/apps/16906",
            APP_YOUTUBE_MUSIC: "https://youtube-music.en.uptodown.com/android/apps/146929",
            APP_REDDIT: "https://reddit-official-app.en.uptodown.com/android/apps/179119"
        }[app]

    def patch_apk(self, input_apk: str, app: str, version: str, output_dir: str = OUTPUT_DIR) -> str | None:
        cli_path = self.get_cli_path()
        patches_path = self.get_patches_path()

        patched_dir = PATCHED_DIR
        os.makedirs(patched_dir, exist_ok=True)

        mpp_version = os.path.basename(patches_path).replace("patches-", "").replace(".mpp", "")
        output_name = f"{app}-morphe-v{version}-mpp{mpp_version}.apk"
        output_path = os.path.join(patched_dir, output_name)

        temp_base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp")
        temp_dir = os.path.join(temp_base, f"morphe-{app}-{version}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)

        cmd = [
            "java", "-jar", cli_path,
            "patch",
            "--patches", patches_path,
            "--keystore", os.path.join(os.path.dirname(os.path.dirname(__file__)), "morphe.keystore"),
            "--keystore-entry-alias", "Morphe",
            "--keystore-entry-password", "Morphe",
            "--keystore-password", "Morphe",
            "-o", output_path,
            "-t", temp_dir,
            "--purge",
            input_apk
        ]

        print(f"[+] Running: java -jar ... patch --patches ... -o {output_name}")

        result = subprocess.run(cmd)

        if result.returncode != 0:
            print(f"[-] Patch failed")
            return None

        print(f"[+] Patched APK: {output_path}")
        return output_path

    def get_microg_re(self) -> str | None:
        print(f"[+] Checking MicroG-RE...")

        existing_apk = None
        if os.path.exists(PATCHED_DIR):
            for f in os.listdir(PATCHED_DIR):
                if f.startswith("microg") and f.endswith(".apk"):
                    existing_apk = os.path.join(PATCHED_DIR, f)
                    break

        try:
            response = github_get(MICROG_RE_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            apk_name = None
            apk_url = None
            for asset in data.get("assets", []):
                if asset["name"].endswith(".apk"):
                    apk_name = asset["name"]
                    apk_url = asset["browser_download_url"]
                    break

            if not apk_name or not apk_url:
                print("[-] No APK found in MicroG-RE release")
                return existing_apk

            print(f"[+] Latest: {apk_name}")

            os.makedirs(PATCHED_DIR, exist_ok=True)
            output_path = os.path.join(PATCHED_DIR, apk_name)

            if os.path.exists(output_path):
                print(f"[+] MicroG-RE already exists: {apk_name}")
                return output_path

            if existing_apk:
                print(f"[+] Using existing (offline): {os.path.basename(existing_apk)}")
                return existing_apk

            github_download(apk_url, output_path, "MicroG-RE")
            return output_path

        except Exception as e:
            if existing_apk:
                print(f"[+] Using existing (offline): {os.path.basename(existing_apk)}")
                return existing_apk
            raise e
