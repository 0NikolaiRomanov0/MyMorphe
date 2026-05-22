import json
from bs4 import BeautifulSoup
from .requester import Requester


class Scraper:
    def __init__(self):
        self.requester = Requester()

    def get_versions(self, app_url: str, app_name: str = None, max_pages: int = 10) -> list[dict]:
        results = []

        from urllib.parse import urlparse
        parsed = urlparse(app_url)
        domain = parsed.netloc

        def make_url(version_id):
            #suffix = "-x" if app_name == "reddit" else ""
            suffix = "-x"
            return f"https://{domain}/android/download/{version_id}{suffix}"

        def deduplicate(items: list[dict]) -> list[dict]:
            seen = {}
            for item in items:
                version = item["version"]
                file_id = item.get("fileID", 0)
                if version not in seen or file_id > seen[version].get("fileID", 0):
                    seen[version] = item
            return list(seen.values())

        for page in range(1, max_pages + 1):
            page_url = f"{app_url}/versions/{page}"
            print(f"[+] Fetching page {page}: {page_url}")

            try:
                html = self.requester.get_text(page_url)

                try:
                    data = json.loads(html)
                    if data.get("success") == 1 and data.get("data"):
                        for item in data["data"]:
                            version_id = item.get("fileID")
                            version = item.get("version")
                            file_type = item.get("kindFile", "apk")
                            if version and version_id:
                                results.append({
                                    "version": version,
                                    "type": file_type,
                                    "fileID": version_id,
                                    "url": make_url(version_id)
                                })
                        print(f"[+] Got {len(data['data'])} versions from page {page}")
                    else:
                        print(f"[+] No more versions found on page {page}")
                        break
                except json.JSONDecodeError:
                    soup = BeautifulSoup(html, "html.parser")
                    container = soup.select_one("#versions-items-list")
                    if not container:
                        break

                    for div in container.find_all("div", attrs={"data-version-id": True}):
                        version = div.select_one(".version")
                        version_id = div.get("data-version-id")
                        type_el = div.select_one(".type")
                        file_type = type_el.get_text(strip=True) if type_el else "apk"
                        if version and version_id:
                            results.append({
                                "version": version.get_text(strip=True),
                                "type": file_type,
                                "fileID": int(version_id),
                                "url": make_url(version_id)
                            })

            except Exception as e:
                print(f"[-] Error on page {page}: {e}")
                break

        return deduplicate(results)

    def get_download_link(self, detail_url: str) -> str | None:
        html = self.requester.get_text(detail_url)
        soup = BeautifulSoup(html, "html.parser")
        button = soup.select_one("#detail-download-button")
        if button:
            data_url = button.get("data-url")
            if data_url:
                return f"https://dw.uptodown.net/dwn/{data_url}"
        return None

    def find_version(self, versions: list[dict], target: str) -> dict | None:
        for v in versions:
            if v["version"] == target:
                return v
        return None

    def search_version(self, app_url: str, target_version: str, app_name: str = None, max_pages: int = 15) -> dict | None:
        from urllib.parse import urlparse
        parsed = urlparse(app_url)
        domain = parsed.netloc

        def make_url(version_id):
            #suffix = "-x" if app_name == "reddit" else ""
            suffix = "-x"
            return f"https://{domain}/android/download/{version_id}{suffix}"

        best_match = None

        for page in range(1, max_pages + 1):
            page_url = f"{app_url}/versions/{page}"
            print(f"[+] Checking page {page}: {page_url}")

            try:
                html = self.requester.get_text(page_url)
                data = json.loads(html)

                if data.get("success") != 1 or not data.get("data"):
                    print(f"[+] No more versions found on page {page}")
                    break

                for item in data["data"]:
                    version_id = item.get("fileID")
                    version = item.get("version")
                    file_type = item.get("kindFile", "apk")

                    if version == target_version:
                        current_match = {
                            "version": version,
                            "type": file_type,
                            "fileID": version_id,
                            "url": make_url(version_id)
                        }
                        if best_match is None or version_id > best_match.get("fileID", 0):
                            best_match = current_match

                if best_match is not None:
                    break

                print(f"[+] Version {target_version} not on page {page}, checking next...")

            except json.JSONDecodeError:
                print(f"[+] Invalid JSON on page {page}")
                break
            except Exception as e:
                print(f"[-] Error on page {page}: {e}")
                break

        if best_match:
            print(f"[+] Found version {target_version} (fileID: {best_match.get('fileID')})")
            return best_match

        print(f"[-] Version {target_version} not found after {max_pages} pages")
        return None
