import re
from bs4 import BeautifulSoup
from .requester import Requester


class Scraper:
    """APKMirror + APKPure CDN scraper for fetching app versions and downloads.

    Strategy:
      1. APKMirror version listing (reliable, no CAPTCHA)
      2. APKMirror download flow (3-step: version page -> download page -> file)
      3. Fallback to APKPure CDN links if APKMirror is Cloudflare-blocked

    The public interface (search_version, get_versions, get_download_link)
    is preserved so app.py and check_and_patch.py require no changes.
    """

    # Base URL for APKMirror app pages
    _APKMIRROR_BASE = "https://www.apkmirror.com"

    # APKPure CDN base — bypasses main-site Cloudflare protection
    _APKPURE_CDN = "https://d.apkpure.com/b"

    def __init__(self):
        self.requester = Requester()
        self._active_source = "apkmirror"  # or "apkpure"

    # ------------------------------------------------------------------
    # Public interface — same signatures as before
    # ------------------------------------------------------------------

    def search_version(self, app_url: str, target_version: str,
                       app_name: str = None,
                       max_pages: int = 15) -> dict | None:
        """Find *target_version* and return download metadata.

        Returns ``{"version", "type", "fileID", "url", "_download_page"}``
        where **url** is the direct CDN download link (for APKPure fallback)
        and **_download_page** is the APKMirror variant page URL (for the
        APKMirror download flow).
        """
        # Try APKMirror first
        result = self._search_version_apkmirror(app_url, target_version)
        if result:
            self._active_source = "apkmirror"
            return result

        # Fallback: APKPure CDN
        result = self._search_version_apkpure(app_url, target_version)
        if result:
            self._active_source = "apkpure"
            return result

        return None

    def get_download_link(self, detail_url: str | None) -> str | None:
        """Return the direct APK download URL.

        For APKPure CDN links: return as-is.
        For APKMirror variant pages: extract the download.php link.
        For None URLs (APKMirror lazy resolution): return None.
        """
        if not detail_url:
            return None

        if detail_url.startswith("https://d.apkpure.com/"):
            return detail_url

        # APKMirror variant page -> extract download.php link
        if self._APKMIRROR_BASE in detail_url:
            return self._extract_apkmirror_download_link(detail_url)

        return None

    def get_versions(self, app_url: str, app_name: str = None,
                     max_pages: int = 10) -> list[dict]:
        """Return all versions for an app (from APKMirror)."""
        return self._fetch_apkmirror_versions(app_url, max_versions=max_pages)

    # ------------------------------------------------------------------
    # APKMirror implementation
    # ------------------------------------------------------------------

    def _search_version_apkmirror(self, app_base_url: str,
                                  target_version: str) -> dict | None:
        """Search for target_version on APKMirror's version listing."""
        apkmirror_url = self._to_apkmirror_url(app_base_url)
        versions_page = f"{apkmirror_url}/"

        print(f"[APKMirror] Searching for {target_version} at {versions_page}")

        # Check multiple pages for older versions
        for page_num in range(1, 16):
            if page_num == 1:
                url = versions_page
            else:
                url = f"{versions_page}page/{page_num}/"

            try:
                html = self.requester.get_text(url)
            except Exception as e:
                print(f"[APKMirror] Page {page_num} failed: {e}")
                break

            version_map = self._parse_apkmirror_version_links(html)
            if not version_map:
                print(f"[APKMirror] No versions on page {page_num}")
                break

            if target_version in version_map:
                release_url = version_map[target_version]
                print(f"[APKMirror] Found {target_version}: {release_url}")

                # Fetch the release page to find APK/XAPK variant links
                variant_url = self._find_apkmirror_variant(release_url)
                if not variant_url:
                    print(f"[APKMirror] No variant found for {target_version}")
                    return None

                file_type = "xapk" if "xapk" in variant_url.lower() else "apk"

                return {
                    "version": target_version,
                    "type": file_type,
                    "url": None,
                    "_download_page": variant_url,
                }

            print(f"[APKMirror] Page {page_num}: {len(version_map)} versions, "
                  f"target not found")

        print(f"[APKMirror] {target_version} not found after checking pages")
        return None

    def _search_version_apkpure(self, app_base_url: str,
                                target_version: str) -> dict | None:
        """Fallback: try to find version on APKPure and resolve CDN link."""
        print(f"[APKPure CDN] Searching for {target_version}")

        # APKPure download page might still work (less protected than /versions)
        try:
            download_page_url = f"{app_base_url}/download/{target_version}"
            html = self.requester.get_text(download_page_url)
            cdn_link = self._extract_cdn_link(html)
            if cdn_link:
                print(f"[APKPure CDN] Found CDN link: {cdn_link[:80]}...")
                return {
                    "version": target_version,
                    "type": "apk",
                    "url": cdn_link,
                    "_download_page": download_page_url,
                }
        except Exception as e:
            print(f"[APKPure CDN] Failed: {e}")

        return None

    def _fetch_apkmirror_versions(self, app_base_url: str,
                                  max_versions: int = 100) -> list[dict]:
        """Fetch version list from APKMirror."""
        apkmirror_url = self._to_apkmirror_url(app_base_url)
        versions_page = f"{apkmirror_url}/"

        print(f"[APKMirror] Fetching versions from {versions_page}")
        results: list[dict] = []
        seen: set[str] = set()

        for page_num in range(1, 20):
            if page_num == 1:
                url = versions_page
            else:
                url = f"{versions_page}page/{page_num}/"

            try:
                html = self.requester.get_text(url)
            except Exception:
                break

            version_map = self._parse_apkmirror_version_links(html)
            if not version_map:
                break

            for version, variant_url in version_map.items():
                if version in seen:
                    continue
                seen.add(version)
                results.append({
                    "version": version,
                    "type": "apk",  # refined lazily
                    "fileID": len(results) + 1,
                    "url": None,
                    "_download_page": variant_url,
                })
                if max_versions and len(results) >= max_versions:
                    return results

        print(f"[APKMirror] Found {len(results)} versions total")
        return results

    # ------------------------------------------------------------------
    # APKMirror helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_apkmirror_url(apkpure_url: str) -> str:
        """Convert an APKPure app URL to an APKMirror URL.

        Example:
          https://apkpure.com/youtube-app/com.google.android.youtube
          -> https://www.apkmirror.com/apk/google-inc/youtube
        """
        # Package name extraction works for all apps
        # The mapping between APKPure slugs and APKMirror paths
        APKMIRROR_MAP = {
            "com.google.android.youtube": "apk/google-inc/youtube",
            "com.google.android.apps.youtube.music": "apk/google-inc/youtube-music",
            "com.reddit.frontpage": "apk/redditinc/reddit",
        }

        pkg = apkpure_url.rstrip("/").split("/")[-1]
        if pkg in APKMIRROR_MAP:
            return f"https://www.apkmirror.com/{APKMIRROR_MAP[pkg]}"

        # Fallback: assume package name matches
        return f"https://www.apkmirror.com/apk/{pkg}"

    @staticmethod
    def _parse_apkmirror_version_links(html: str) -> dict[str, str]:
        """Parse an APKMirror version listing page.

        Returns {version: version_page_url} mapping.
        These are release pages like ``/apk/.../youtube-21-13-164-release/``
        which we later fetch to find individual APK/XAPK variant links.
        """
        soup = BeautifulSoup(html, "html.parser")
        result: dict[str, str] = {}

        version_re = re.compile(
            r'/([a-z][\w-]*?)-([\d]+(?:-[\d]+)+)-release'
        )

        for a in soup.select("a[href]"):
            href = str(a.get("href") or "")
            match = version_re.search(href)
            if not match:
                continue

            raw_ver = match.group(2)  # e.g. 21-13-164
            version_str = raw_ver.replace("-", ".")

            # Skip SECONDARY and beta variants
            if "secondary" in href.lower():
                continue

            full_url = f"https://www.apkmirror.com{href}"
            if version_str not in result:
                result[version_str] = full_url

        return result

    @staticmethod
    def _extract_cdn_link(html: str) -> str | None:
        """Extract d.apkpure.com CDN link from APKPure HTML."""
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href*='d.apkpure.com']"):
            href = str(link.get("href") or "")
            if "/b/APK/" in href or "/b/XAPK/" in href:
                return href
        return None

    def _find_apkmirror_variant(self, release_url: str) -> str | None:
        """From an APKMirror release page, find the first APK or XAPK variant URL.

        APKMirror release pages list individual variants as links like:
            /apk/.../youtube-21-13-164-android-apk-download/
        We pick the first one that mentions APK or XAPK.
        """
        try:
            html = self.requester.get_text(release_url)
            soup = BeautifulSoup(html, "html.parser")

            for a in soup.select("a[href]"):
                href = str(a.get("href") or "")
                text = a.get_text(strip=True).upper()
                if ("android-apk-download" in href
                        and ("APK" in text or "XAPK" in text)):
                    full_url = (f"https://www.apkmirror.com{href}"
                                if href.startswith("/") else href)
                    print(f"[APKMirror] Variant: {full_url[:100]}")
                    return full_url
        except Exception as e:
            print(f"[APKMirror] Error finding variant: {e}")

        return None

    def _detect_apkmirror_file_type(self, variant_url: str) -> str:
        """Fetch an APKMirror variant page and detect if it's APK or XAPK."""
        try:
            html = self.requester.get_text(variant_url)
            if "XAPK" in html.upper() and "APK Bundle" in html:
                return "xapk"
            return "apk"
        except Exception:
            return "apk"

    def _extract_apkmirror_download_link(self, variant_url: str) -> str | None:
        """Extract the actual APK file URL from an APKMirror variant page.

        The APKMirror download flow is:
          variant page -> download button with key -> download.php -> 302 to CDN
        We follow the full redirect chain here and return the final CDN URL
        so the Downloader can fetch it without needing custom headers.
        """
        try:
            # Step 1: Fetch variant page
            html = self.requester.get_text(variant_url)
            soup = BeautifulSoup(html, "html.parser")

            # Step 2: Find download button with key
            dl_key_url = None
            for a in soup.select("a"):
                href = str(a.get("href") or "")
                text = a.get_text(strip=True)
                if ("download" in text.lower() and "apk" in text.lower()
                        and "key=" in href):
                    dl_key_url = href
                    break

            if not dl_key_url:
                print("[APKMirror] No download button found")
                return None

            # Step 3: Fetch the download page to get download.php link
            full_dl_url = (f"https://www.apkmirror.com{dl_key_url}"
                           if dl_key_url.startswith("/") else dl_key_url)
            html2 = self.requester.get_text(full_dl_url)
            soup2 = BeautifulSoup(html2, "html.parser")

            # Step 4: Find the download.php link
            dl_php_url = None
            for a in soup2.select("a"):
                href = str(a.get("href") or "")
                if "download.php" in href:
                    dl_php_url = (f"https://www.apkmirror.com{href}"
                                  if href.startswith("/") else href)
                    break

            if not dl_php_url:
                print("[APKMirror] No download.php link found")
                return None

            # Step 5: Follow the download.php redirect to get the final CDN URL
            # We use the correct Referer (the download page) to pass validation.
            # The final URL (Cloudflare R2 or similar) can then be fetched by
            # the Downloader without special headers.
            resp = self.requester.get_with_referer(dl_php_url, full_dl_url)
            final_url = resp.url

            if resp.status_code in (200, 206) or "cloudflarestorage" in final_url:
                print(f"[APKMirror] Resolved download URL: {final_url[:100]}...")
                return final_url

            print(f"[APKMirror] Unexpected status {resp.status_code} "
                  f"from download.php")
            return None

        except Exception as e:
            print(f"[APKMirror] Error extracting download link: {e}")
            return None
