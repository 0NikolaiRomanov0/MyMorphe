import os
import shutil
import argparse
from utils import Scraper, Downloader, APKEditor, Morphe
from utils.common import TEMP_DIR, PATCHED_DIR, OUTPUT_DIR


def clean_temp():
    errors = False
    if os.path.exists(TEMP_DIR):
        for item in os.listdir(TEMP_DIR):
            item_path = os.path.join(TEMP_DIR, item)
            try:
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except Exception as e:
                print(f"[-] Could not remove {item}: {e}")
                errors = True
    if errors:
        print(f"[-] Temp folder cleaned with errors: {TEMP_DIR}")
    else:
        print(f"[+] Temp folder cleaned: {TEMP_DIR}")


def main():
    parser = argparse.ArgumentParser(description="Auto-sync YouTube APKs with Morphe patcher")
    parser.add_argument("--all", action="store_true", help="Download and patch all compatible versions")
    args = parser.parse_args()

    clean_temp()

    print("[+] Auto-sync: checking morphe compatible versions...")

    scraper = Scraper()
    downloader = Downloader()
    apk_editor = APKEditor()
    morphe = Morphe()

    print("[+] Checking APKEditor JAR...")
    apk_editor.get_jar_path()

    cli_path = morphe.get_cli_path()
    patches_path = morphe.get_patches_path()
    mpp_version = os.path.basename(patches_path).replace("patches-", "").replace(".mpp", "")
    print(f"[+] CLI: {cli_path}")
    print(f"[+] Patches: {patches_path} (v{mpp_version})")
    print()

    morphe.get_microg_re()
    print()

    versions = morphe.list_versions(patches_path, cli_path)

    to_download = {}
    to_patch = {}

    for app, version_list in versions.items():
        if not version_list:
            continue

        if args.all:
            for version in version_list:
                patched_name = f"{app}-morphe-v{version}-mpp{mpp_version}.apk"
                patched_path = os.path.join(PATCHED_DIR, patched_name)

                if os.path.exists(patched_path):
                    continue

                apk_name = f"{app}-{version}.apk"
                apk_path = os.path.join(OUTPUT_DIR, apk_name)

                if os.path.exists(apk_path):
                    if app not in to_patch:
                        to_patch[app] = []
                    to_patch[app].append((version, apk_path))
                    print(f"[+] {app} {version} needs patch (APK already exists)")
                else:
                    if app not in to_download:
                        to_download[app] = []
                    to_download[app].append(version)
                    print(f"[+] {app} {version} needs download + patch")
        else:
            version_to_use = None
            apk_path_to_use = None

            for version in version_list:
                patched_name = f"{app}-morphe-v{version}-mpp{mpp_version}.apk"
                patched_path = os.path.join(PATCHED_DIR, patched_name)

                if os.path.exists(patched_path):
                    version_to_use = None
                    break

                apk_name = f"{app}-{version}.apk"
                apk_path = os.path.join(OUTPUT_DIR, apk_name)

                if os.path.exists(apk_path):
                    version_to_use = version
                    apk_path_to_use = apk_path
                    break
                else:
                    if version_to_use is None:
                        version_to_use = version

            if version_to_use is None:
                continue

            if apk_path_to_use:
                to_patch[app] = [(version_to_use, apk_path_to_use)]
                print(f"[+] {app} {version_to_use} needs patch (APK already exists)")
            else:
                to_download[app] = [version_to_use]
                print(f"[+] {app} {version_to_use} needs download + patch")

    if not to_download and not to_patch:
        print("[+] All morphe compatible versions are already patched")
        print()
        print("[+] Cleaning up temp folder...")
        clean_temp()
        return

    if to_download:
        print()
        print("[+] Phase 1: Downloading all APKs...")
        for app, version_list in to_download.items():
            app_url = morphe.get_app_url(app)

            for version in version_list:
                print(f"[+] Trying {app} {version}...")

                apk_name = f"{app}-{version}.apk"
                apk_path = os.path.join(OUTPUT_DIR, apk_name)

                if os.path.exists(apk_path):
                    if app not in to_patch:
                        to_patch[app] = []
                    to_patch[app].append((version, apk_path))
                    print(f"[+] Using existing: {apk_path}")
                    continue

                target = scraper.search_version(app_url, version, app, max_pages=15)
                if not target:
                    print(f"[-] {app} {version} not found, skipping")
                    continue

                download_url = scraper.get_download_link(target["url"])
                if not download_url:
                    print(f"[-] Could not get download URL for {app} {version}, skipping")
                    continue

                file_type = target["type"]
                filename = f"{app}-{version}.{file_type}"

                try:
                    if file_type == "xapk":
                        downloader.download(download_url, TEMP_DIR, filename)
                        xapk_path = os.path.join(TEMP_DIR, filename)
                        apk_filename = f"{app}-{version}.apk"
                        apk_path = apk_editor.convert_xapk_to_apk(xapk_path, OUTPUT_DIR, apk_filename)
                    else:
                        downloader.download(download_url, OUTPUT_DIR, filename)
                        apk_path = os.path.join(OUTPUT_DIR, filename)

                    if app not in to_patch:
                        to_patch[app] = []
                    to_patch[app].append((version, apk_path))
                    print(f"[+] Downloaded: {apk_path}")
                except Exception as e:
                    print(f"[-] Error downloading {app} {version}: {e}")

    if to_patch:
        print()
        print("[+] Phase 2: Patching all APKs...")
        for app, patch_list in to_patch.items():
            for version, apk_path in patch_list:
                print(f"[+] Patching {app} {version}...")
                patched_path = morphe.patch_apk(apk_path, app, version)
                if patched_path:
                    print(f"[+] Patched: {patched_path}")

    print()
    print("[+] Sync complete!")

    print()
    print("[+] Cleaning up temp folder...")
    clean_temp()


if __name__ == "__main__":
    main()