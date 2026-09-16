import re
from bs4 import BeautifulSoup
from .requester import Requester


class Scraper:
    """APKMirror + APKPure CDN scraper for fetching app versions and downloads.

    Strategy:
      1. APKMirror: construct direct version page URL (no pagination needed),
         then follow release -> variant -> download button -> download.php
      2. APKPure CDN fallback: scrape the download page to extract versionCode,
         then construct d.apkpure.com CDN URL directly.

    The revanced-morphe-builder project proved this approach works:
    - APKMirror release pages have predictable URLs
    - APKPure CDN links can be extracted from download pages
    - Both work from GitHub Actions with curl_cffi TLS fingerprint impersonation
    """

    # Base URL for APKMirror app pages
    _APKMIRROR_BASE = "https://www.apkmirror.com"

    # APKPure CDN base -- bypasses main-site Cloudflare protection
    _APKPURE_CDN = "https://d.apkpure.com/b"

    # Maps package names to their APKMirror URL path segments.
    # These are used to construct direct version page URLs without
    # needing to scrape or paginate through version listings.
    _APKMIRROR_APP_PATH = {
        "com.google.android.youtube": "apk/google-inc/youtube",
        "com.google.android.apps.youtube.music": "apk/google-inc/youtube-music",
        "com.reddit.frontpage": "apk/redditinc/reddit",
    }

    def __init__(self):
        self.requester = Requester()
        self._active_source = "apkmirror"  # or "apkpure"
        self._active_variant_type = "apk"  # set by _find_apkmirror_variant

    # ------------------------------------------------------------------
    # Public interface -- same signatures as before
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
        # Try APKMirror first (direct version page URL, no pagination)
        result = self._search_version_apkmirror(app_url, target_version)
        if result:
            self._active_source = "apkmirror"
            return result

        # Fallback: APKPure CDN (extract version code from download page)
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
        """Search for target_version on APKMirror.

        Instead of paginating through version listings (which gets 403'd
        after page 1), we construct the direct version page URL from the
        version name.  APKMirror URLs follow a predictable pattern:
          /apk/{org}/{app}/{app}-{ver}-release/

        This is the same approach used by revanced-morphe-builder.
        """
        # Extract package name from the APKPure URL
        pkg = app_base_url.rstrip("/").split("/")[-1]
        app_path = self._APKMIRROR_APP_PATH.get(pkg)
        if not app_path:
            print(f"[APKMirror] Unknown package: {pkg}")
            return None

        # Convert version dots to dashes for the URL
        version_dashes = target_version.replace(".", "-")
        app_slug = app_path.split("/")[-1]  # e.g. "youtube"

        release_url = (
            f"{self._APKMIRROR_BASE}/{app_path}/"
            f"{app_slug}-{version_dashes}-release/"
        )

        print(f"[APKMirror] Trying direct URL: {release_url}")

        try:
            html = self.requester.get_text(release_url)
        except Exception as e:
            print(f"[APKMirror] Direct URL failed: {e}")
            return None

        # Find APK or XAPK variant link from the release page
        variant_url = self._find_apkmirror_variant(html)
        if not variant_url:
            print(f"[APKMirror] No variant found for {target_version}")
            return None

        # Determine file type from the variant we selected
        file_type = getattr(self, "_active_variant_type", "apk")
        if "xapk" in variant_url.lower():
            file_type = "xapk"

        print(f"[APKMirror] Found {target_version}: {variant_url[:80]}...")

        return {
            "version": target_version,
            "type": file_type,
            "url": None,
            "_download_page": variant_url,
        }

    def _search_version_apkpure(self, app_base_url: str,
                                target_version: str) -> dict | None:
        """Fallback: extract download info from APKPure.

        Instead of hardcoding version codes, we scrape the APKPure
        download page for the target version and extract the versionCode
        from the CDN link or page content.  This works because the
        download page (unlike /versions) is a single page that may not
        trigger Cloudflare's pagination blocks.
        """
        # Extract package name
        url_path = app_base_url.rstrip("/").split("apkpure.com/")[-1]
        parts = url_path.split("/")
        slug = parts[0] if parts else ""

        # Map APKPure slugs to package names
        SLUG_TO_PKG = {
            "youtube-app": "com.google.android.youtube",
            "youtube-music": "com.google.android.apps.youtube.music",
            "reddit-app": "com.reddit.frontpage",
        }
        package_name = SLUG_TO_PKG.get(slug)
        if not package_name:
            package_name = parts[-1] if parts else ""

        print(f"[APKPure CDN] Searching for {target_version} "
              f"(package={package_name})")

        # Strategy 1: Scrape the download page for this version to get
        # the CDN link directly.
        try:
            download_page_url = f"{app_base_url}/download/{target_version}"
            html = self.requester.get_text(download_page_url)

            # Try to extract CDN link from the page
            cdn_link = self._extract_cdn_link(html)
            if cdn_link:
                print(f"[APKPure CDN] Found CDN link: {cdn_link[:80]}...")
                file_type = ("xapk" if "/XAPK/" in cdn_link else "apk")
                return {
                    "version": target_version,
                    "type": file_type,
                    "url": cdn_link,
                    "_download_page": download_page_url,
                }

            # If no CDN link in HTML, try to extract versionCode
            # from the page and construct CDN URL
            version_code = self._extract_version_code(html)
            if version_code and package_name:
                cdn_url = (
                    f"{self._APKPURE_CDN}/APK/"
                    f"{package_name}?versionCode={version_code}"
                )
                print(f"[APKPure CDN] Constructed CDN URL: {cdn_url[:80]}...")
                return {
                    "version": target_version,
                    "type": "apk",
                    "url": cdn_url,
                    "_download_page": cdn_url,
                }
        except Exception as e:
            print(f"[APKPure CDN] Download page scrape failed: {e}")

        # Strategy 2: Try the versions page to find versionCode
        try:
            versions_page_url = f"{app_base_url}/versions"
            html = self.requester.get_text(versions_page_url)
            version_code = self._extract_version_code_for_version(
                html, target_version
            )
            if version_code and package_name:
                cdn_url = (
                    f"{self._APKPURE_CDN}/APK/"
                    f"{package_name}?versionCode={version_code}"
                )
                print(f"[APKPure CDN] CDN URL from versions: {cdn_url[:80]}...")
                return {
                    "version": target_version,
                    "type": "apk",
                    "url": cdn_url,
                    "_download_page": cdn_url,
                }
        except Exception as e:
            print(f"[APKPure CDN] Versions page scrape failed: {e}")

        print(f"[APKPure CDN] No CDN URL found for {target_version}")
        return None

    def _fetch_apkmirror_versions(self, app_base_url: str,
                                  max_versions: int = 100) -> list[dict]:
        """Fetch version list from APKMirror (paginated)."""
        app_path = None
        pkg = app_base_url.rstrip("/").split("/")[-1]
        for key, path in self._APKMIRROR_APP_PATH.items():
            if key == pkg:
                app_path = path
                break
        if not app_path:
            return []

        versions_page = f"{self._APKMIRROR_BASE}/{app_path}/"
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
                    "type": "apk",
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
    def _parse_apkmirror_version_links(html: str) -> dict[str, str]:
        """Parse an APKMirror version listing page.

        Returns {version: version_page_url} mapping.
        These are release pages like ``/apk/.../youtube-21-13-164-release/``
        which we later fetch to find individual APK/XAPK variant links.
        """
        soup = BeautifulSoup(html, "html.parser")
        result: dict[str, str] = {}

        version_re = re.compile(
            r'/([a-z][\w-]*?)-([\d]+(?:-[[\d]+)+)-release'
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

    @staticmethod
    def _extract_version_code(html: str) -> str | None:
        """Extract versionCode from APKPure download page HTML.

        Looks for patterns like:
          - data-code="1561063732"
          - /b/APK/...?versionCode=1561063732
          - download/{version_code}
        """
        # Pattern 1: data-code attribute
        match = re.search(r'data-code=["\'](\d+)["\']', html)
        if match:
            return match.group(1)

        # Pattern 2: versionCode in CDN URL
        match = re.search(r'versionCode=(\d+)', html)
        if match:
            return match.group(1)

        # Pattern 3: /download/{code} in href
        match = re.search(r'/download/(\d+)', html)
        if match:
            return match.group(1)

        return None

    @staticmethod
    def _extract_version_code_for_version(html: str,
                                          target_version: str) -> str | None:
        """Extract versionCode for a specific version from APKPure HTML.

        Parses download links that look like:
          /youtube-app/com.google.android.youtube/download/1561063732
        """
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("a[href]"):
            href = str(a.get("href") or "")
            text = a.get_text(strip=True)
            # Match by version number in the link text
            if target_version in text:
                match = re.search(r'/download/(\d+)', href)
                if match:
                    return match.group(1)
        return None

    def _find_apkmirror_variant(self, html: str) -> str | None:
        """From APKMirror release page HTML, find the best APK variant URL.

        APKMirror lists variants in a table with type (APK vs BUNDLE),
        architecture, and DPI.  We MUST pick the standalone APK variant,
        NOT the BUNDLE (split APK).  Bundles don't have a root-level
        AndroidManifest.xml, which causes morphe-cli NPE.

        Priority: universal/nodpi APK > arm64-v8a APK > any APK.
        Never pick a BUNDLE variant.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Build a list of (row_text, href, row_index) for all variant rows
        rows = soup.select("div.table-row")
        variants = []
        for row in rows:
            text = row.get_text(strip=True, separator=" ")
            link = row.select_one("a[href*='android-apk-download']")
            if not link:
                continue
            href = str(link.get("href") or "")
            if not href:
                continue
            full_url = (f"https://www.apkmirror.com{href}"
                        if href.startswith("/") else href)
            variants.append((text, full_url, len(variants)))

        if not variants:
            return None

        # Classify each variant: APK vs BUNDLE
        standalone_apks = []
        bundle_apks = []
        for text, url, idx in variants:
            text_upper = text.upper()
            if "BUNDLE" in text_upper:
                bundle_apks.append((text, url, idx))
            else:
                standalone_apks.append((text, url, idx))

        if standalone_apks:
            # Rank standalone APKs: universal/nodpi first, then by arch
            def apk_priority(item):
                text = item[0].lower()
                score = 0
                if "universal" in text:
                    score += 100
                if "nodpi" in text:
                    score += 50
                if "arm64" in text:
                    score += 10
                return -score  # negative so highest score sorts first

            standalone_apks.sort(key=apk_priority)
            best = standalone_apks[0]
            print(f"[APKMirror] Variant: {best[1][:100]}")
            print(f"[APKMirror] Variant info: {best[0][:100]}")
            self._active_variant_type = "apk"
            return best[1]

        if bundle_apks:
            # All variants are bundles (e.g. Reddit only has XAPK).
            # The caller must use XAPK→APK conversion (apkeditor.py).
            print("[APKMirror] Only BUNDLE variants found, "
                  "downloading as XAPK")
            self._active_variant_type = "xapk"
            return bundle_apks[0][1]

        return None

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

            # Step 4: Find the actual download link.
            # APKMirror shows the download URL in different formats:
            #   - Old: <a href="/wp-content/themes/APKMirror/download.php?id=...">
            #   - New: <a href="..." rel="nofollow"> under a span
            # We search for both patterns.  Use the revanced-morphe-builder
            # approach: find ``span > a[rel=nofollow]`` first.
            dl_php_url = None
            # Pattern 1: span > a with rel=nofollow (revanced-morphe-builder)
            for span in soup2.select("span"):
                link = span.select_one("a[rel=nofollow]")
                if link:
                    dl_php_url = str(link.get("href") or "")
                    if dl_php_url:
                        dl_php_url = (f"https://www.apkmirror.com{dl_php_url}"
                                      if dl_php_url.startswith("/") else dl_php_url)
                        break
            # Pattern 2: fallback — look for download.php link
            if not dl_php_url:
                for a in soup2.select("a"):
                    href = str(a.get("href") or "")
                    if "download.php" in href:
                        dl_php_url = (f"https://www.apkmirror.com{href}"
                                      if href.startswith("/") else href)
                        break
            # Pattern 3: any prominent link to the actual file
            if not dl_php_url:
                for a in soup2.select("a.downloadLink, a[href*=download]"):
                    href = str(a.get("href") or "")
                    if href and href.startswith("http"):
                        dl_php_url = href
                        break

            if not dl_php_url:
                print("[APKMirror] No download.php link found")
                return None

            # Step 5: Follow the redirect chain to get the final CDN URL.
            # APKMirror's download.php returns a 302 redirect to the actual
            # CDN file.  We use allow_redirects=False and follow the
            # Location header manually to avoid downloading multi-GB APKs.
            resp = self.requester._session.get(
                dl_php_url,
                headers={"Referer": full_dl_url,
                         "User-Agent": self.requester._FIREFOX_UA},
                timeout=15,
                impersonate="chrome",
                allow_redirects=False,
            )
            final_url = dl_php_url
            redirect_count = 0
            while resp.is_redirect and redirect_count < 5:
                location = resp.headers.get("Location", "")
                if location:
                    if location.startswith("/"):
                        location = f"https://www.apkmirror.com{location}"
                    final_url = location
                resp = self.requester._session.get(
                    final_url,
                    headers={"Referer": dl_php_url,
                             "User-Agent": self.requester._FIREFOX_UA},
                    timeout=15,
                    impersonate="chrome",
                    allow_redirects=False,
                )
                redirect_count += 1

            # If we ended up on a cloudflarestorage URL, that's our CDN link.
            if "cloudflarestorage" in final_url:
                print(f"[APKMirror] Resolved download URL: {final_url[:100]}...")
                return final_url

            print(f"[APKMirror] Unexpected status {resp.status_code} "
                  f"from download.php")
            return None

        except Exception as e:
            print(f"[APKMirror] Error extracting download link: {e}")
            return None
